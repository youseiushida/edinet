# FEATURES

edinet ライブラリが目指す機能の全体像を定義する。
このドキュメントは「理想形」を記述するもので、実装順序やスケジュールは PLAN.LIVING.md や個別の計画に委ねる。
スコープの原則と境界線は SCOPE.md を参照。

## ステータス定義

- `[DONE]` — 実装済み・利用可能
- `[WIP]` — 実装中
- `[TODO]` — 未実装
- `[NEEDS_FEEDBACK]` — 設計判断が必要

---

## Data Access

- list: 書類一覧の取得・フィルタリング [DONE]
  - detail: `edinet.documents()` / `edinet.adocuments()` で Filing 一覧を取得
  - scope: 全 docType × 全会計基準。日付・docType・EDINET コード等でフィルタ可能
- fetch: ZIP ダウンロードと代表 .xbrl の抽出 [DONE]
  - detail: `Filing.fetch()` / `Filing.afetch()` → `(source_path, xbrl_bytes)`
  - scope: `has_xbrl=True` の全 docType。`has_xbrl=False` は対象外（データ特性）
- fetch_pdf: PDF ダウンロード [TODO]
  - detail: `has_pdf=True` の書類から PDF bytes を返す。XBRL が存在しない書類（適時開示、招集通知、古い年代のデータ等）へのアクセス手段。テキスト抽出はライブラリのスコープ外
  - note: Filing モデルの `has_pdf` フィールドは実装済み
- cache: ダウンロード済み ZIP のローカルキャッシュ [TODO]
  - detail: 同一 Filing の ZIP を再ダウンロードしない HTTP キャッシュ的な機構。繰り返しアクセス時の API コール削減
- revision_chain: 訂正報告書の自動解決 [TODO]
  - depends: list
  - detail: 原本→訂正→再訂正のチェーンを辿り、latest() は最終版を返す便利メソッド。原本と訂正版の個別取得は list + doc_type フィルタで既に可能（バックテスト用途）。バックテスト向けに `at_time(date)` で指定時点で入手可能だった版を取得可能にする（submit_date_time <= cutoff のフィルタ）
  - note: DocType の `original` / `is_correction` / `_CORRECTION_MAP`、Filing の `parent_doc_id` はモデル層で実装済み。訂正報告書は差分ではなく全体再提出（G-7）

## Company API

edgartools 的な企業起点のナビゲーションを提供する。

- company/lookup: 企業の検索・特定 [WIP]
  - detail: EDINET コード・銘柄コード・企業名・業種から Company オブジェクトを取得。`edinet.Company("トヨタ")` のような直感的アクセス。`edinet.companies(industry="輸送用機器")` で業種による一覧取得。業種情報は EDINET コード一覧（提出者コード CSV）から取得
- company/filings: 企業単位での書類一覧取得 [DONE]
  - depends: list
  - detail: `company.filings(doc_type="有価証券報告書")` のようなチェーン
- company/latest: 最新書類へのショートカット [DONE]
  - depends: company/filings
  - detail: `company.latest("有価証券報告書")` で最新の有報にアクセス

## XBRL Core

XBRL インスタンスから構造化オブジェクトを生成する基盤レイヤー。

- facts: XBRL インスタンスから Fact を抽出 [DONE]
  - depends: fetch
  - scope: 全会計基準 × 全 docType
  - detail: concept (Clark notation), value, value_inner_xml（mixed-content 保持用）, contextRef, unitRef, decimals, xsi:nil, id, xml:lang を RawFact として抽出。重複 Fact は文書順で保持（A-7）。各 Fact に元文書内の位置情報（行番号等）を保持し、source linking の基盤とする
- contexts: Context の解析 [DONE]
  - depends: facts
  - detail: instant / duration 期間、entity identifier、explicit/typed dimension を構造化。contextRef から期間・次元情報を引ける。`ContextCollection` で O(1) ルックアップ
- units: 単位の解析と正規化 [DONE]
  - depends: facts
  - detail: 通貨（JPY/USD/EUR）、株数、%、複合単位（per share 等）の型安全なハンドリング。`SimpleMeasure` / `DivideMeasure` の Union 型
- namespaces: 名前空間の解決 [DONE]
  - depends: facts
  - detail: 各 Fact が標準タクソノミか提出者別タクソノミかを判別。`resolve_prefix()` / `is_standard_prefix()` 提供
- dei: DEI（Document and Entity Information）要素の抽出 [DONE]
  - depends: facts
  - detail: 会計基準の判別（`AccountingStandardsDEI`）、報告期間、企業属性等の取得。`extract_dei()` → `DEI` dataclass
- eda/summary: Filing の概観サマリー [TODO]
  - depends: facts, contexts, namespaces, dei
  - detail: `filing.summary()` で Filing の全体像を返す。科目数、会計基準（dei 経由）、報告期間、連結/個別、主要科目トップ N、非標準科目の割合、セグメント数等。REPL / Jupyter での探索的データ分析の起点
- footnotes: 脚注リンクの解析 [WIP]
  - depends: facts
  - detail: XBRL の `footnoteLink` を解析し、Fact と脚注テキストの紐付けを提供（A-5）。BS上の「のれん」の数値と注記の「減損テストの仮定」のような関係を辿れる。Fact オブジェクトから `fact.footnotes` でアクセス可能にする
- source_linking: Fact から元文書位置への参照 [WIP]
  - depends: facts
  - detail: 抽出した Fact が元文書の何行目にあったかのポインタを提供。数字の正しさに疑問がある場合に原文を即座に確認できるようにする

## Financial Statements

Fact から財務諸表を組み立てる。会計基準ごとの差異を吸収し、統一的なオブジェクトで返す。

- statements/PL: 損益計算書 [DONE]
  - depends: facts, contexts, standards/normalize
  - scope: J-GAAP 一般事業会社 → IFRS → US-GAAP → 特定業種の順で拡張
- statements/BS: 貸借対照表 [DONE]
  - depends: facts, contexts, standards/normalize
  - note: 期末時点（instant）の Fact。期首時点のデータも含まれうる（E-3）
- statements/CF: キャッシュフロー計算書 [WIP]
  - depends: facts, contexts, standards/normalize
  - detail: 直接法/間接法の自動判別が必要。判別方法は role URI または concept の有無（E-1d）。日本の上場企業はほぼ間接法だが直接法も想定する
  - note: 一般事業会社(cns)には CF の Presentation Linkbase（_pre_cf）が存在しない（Z-2）。業種別ディレクトリ（銀行業 bk1 等）には存在する。taxonomy/concept_sets での自動導出時に業種別 _pre からの共通 concept 抽出か、calc_tree からの導出が必要
- statements/equity: 株主資本等変動計算書 [TODO]
  - depends: facts, contexts, def_links, standards/normalize
  - detail: 本質的に2次元テーブル（行=資本項目、列=期首残高/変動額/期末残高）。列方向の区別は period（instant vs duration）と dimension の組み合わせで表現される（E-1c）。definition linkbase の dimension 情報が必要
- statements/comprehensive_income: 包括利益計算書 [TODO]
  - depends: facts, contexts, standards/normalize

## Accounting Standard Normalization

会計基準（J-GAAP / IFRS / US-GAAP）の差異を吸収するレイヤー。

- standards/detect: 会計基準の自動判別 [DONE]
  - depends: dei, namespaces
  - detail: DEI 要素（`AccountingStandardsDEI`）を第一手段、名前空間（`jppfs_cor` → J-GAAP、`jpigp_cor` → IFRS）をフォールバックとして判別（D-3）。`DetectedStandard` に `detail_level`（DETAILED/BLOCK_ONLY）を含む
- standards/jgaap: 日本基準の科目マッピング [WIP]
  - depends: facts, namespaces
  - detail: jppfs_cor/jpcrp_cor 系タクソノミの主要科目 52 件（PL16+BS20+CF8+KPI8）の canonical_key マッピング
- standards/ifrs: IFRS の科目マッピング [WIP]
  - depends: facts, namespaces
  - detail: jpigp_cor 系タクソノミの主要科目 35 件（PL15+BS15+CF5）。J-GAAP との双方向マッピング。IFRS には「経常利益」がない等の構造的差異を吸収
- standards/usgaap: 米国基準の科目マッピング [WIP]
  - depends: facts, namespaces
  - detail: US-GAAP は包括タグ付け（BLOCK_ONLY）のため SummaryOfBusinessResults 19 科目 + TextBlock 14 個を専用型で提供
- standards/normalize: 会計基準横断の統一アクセス [WIP]
  - depends: standards/detect, standards/jgaap, standards/ifrs, standards/usgaap
  - detail: 「売上高」を指定すれば会計基準に依存せず値を取得できる抽象レイヤー。jquants が IFRS で経常利益を空欄にする問題を根本的に解決する
  - note: 会計基準間マッピング（J-GAAP `jppfs_cor:NetSales` ↔ IFRS `ifrs-full:Revenue` 等）は公式データが存在せず手動定義が不可避。主要指標 50-100 程度のため一度作成すれば年次メンテは軽微（Z-2）

## Taxonomy & Links

タクソノミのリンクベース（計算・表示・定義）を木構造として提供する。
非標準科目の横断比較を可能にする基盤。

- calc_tree: Calculation Linkbase の木構造解析 [DONE]
  - depends: facts, namespaces
  - detail: 科目間の計算関係（親子・加減・weight）を木構造で提供。weight は `1`（加算）または `-1`（減算）（C-7）。「売上高」の内訳として各社独自の科目がぶら下がる構造を辿れる
- pres_tree: Presentation Linkbase の木構造解析 [DONE]
  - depends: facts, namespaces
  - detail: 財務諸表の表示順序・階層構造。企業間の「構造の相同性」比較の基盤。提出者によるカスタマイズ（標準ツリーの並び替え・追加）を含む（I-3）。標準タクソノミの _pre ファイルは財務諸表セクション（売上区分・販管費区分等）ごとにバリアントファイルとして分割されており、role URI 単位でのマージが必要（Z-2）
- def_links: Definition Linkbase の解析 [DONE]
  - depends: facts, namespaces
  - detail: Dimension-Domain メンバー関係（hypercube-dimension, dimension-domain, domain-member 等の arcrole）。セグメント次元の正式な定義を取得（C-8）
- taxonomy/versioning: タクソノミバージョン間の concept マッピング [TODO]
  - depends: namespaces
  - detail: 名前空間 URI にバージョン年度が含まれるため、2024年版と2025年版で同一 concept の URI が異なる（H-3）。旧 concept → 新 concept のマッピングを提供し、年度横断の時系列分析でコンセプト名の不一致を吸収する。deprecated concept の検出と警告も含む。タクソノミの `deprecated/` ディレクトリに XSD（229 elements）とラベル（日英）が機械可読な形式で提供されており、自動抽出が可能。ただし deprecated → 代替先の機械可読な参照は XSD 内に明示されていないため、ラベル名の類似度による半自動推定が必要（Z-2）
- taxonomy/standard_mapping: 非標準科目→標準科目の祖先マッピング [TODO]
  - depends: calc_tree
  - detail: 計算リンクを遡り、提出者別タクソノミの科目が標準タクソノミのどの科目に集約されるかを辿る。「受注損失引当金」→「販管費」→「営業利益」のような推論。横断比較の核心
- taxonomy/concept_sets: リンクベースからの科目セット自動導出 [DONE]
  - depends: pres_tree
  - detail: Presentation Linkbase の role URI と親子関係から PL/BS/CF/SS/CI に属する標準 concept セットを自動導出。23 業種全カバー。PL バリアントのマージ、CF の業種間 fallback 実装済み
- taxonomy/custom_detection: 各 Fact の標準/非標準判定と分類 [TODO]
  - depends: namespaces, def_links
  - detail: 各 Fact に `is_standard` フラグを付与。非標準科目には `shadowing_target`（上書き先の標準タグ）を推定。拡張科目は通常、標準科目の子要素として定義される（E-6）。wider-narrower arcrole によるアンカリング情報があれば意味的位置づけの自動判定にも利用
- taxonomy/labels: ラベルリンクベースの解決 [DONE]
  - depends: namespaces
  - detail: concept の日本語/英語ラベルを取得。提出者別ラベル（拡張科目のラベル）は提出者別 `_lab.xml` からのみ取得可能（E-6）

## Dimensions

XBRL の Dimension（次元）を解析し、データの多次元的なスライスを可能にする。

- dimensions/consolidated: 連結・個別の切り分け [DONE]
  - depends: contexts, def_links
  - detail: 連結/非連結をフィルタ条件として指定可能にする。Context の segment 要素で判別。`Statements.has_consolidated_data` / `has_non_consolidated_data` プロパティ、`income_statement(consolidated=True/False)` のフィルタ、`strict=True` によるフォールバック抑止を提供
- dimensions/segments: 事業セグメント解析 [TODO]
  - depends: contexts, def_links
  - detail: セグメント別の売上・利益・資産を Dimension 次元から構造化。jquants のフラットな「全社合計」では見えない事業別モメンタムを取得可能にする（J-2）
- dimensions/geographic: 地域セグメント解析 [TODO]
  - depends: contexts, def_links
  - detail: 地域別売上・資産の構造化
- dimensions/period_variants: 期間バリアント（当期/前期/予想） [DONE]
  - depends: contexts, dei
  - detail: DEI の日付情報から当期/前期を分類。`income_statement(period="current")` / `period="prior"` で当期・前期を DEI ベースで自動選択。`classify_periods(dei)` → `PeriodClassification` で直接利用も可能
- dimensions/fiscal_year: 決算期・変則決算の判定 [TODO]
  - depends: contexts
  - detail: 1件の filing について、3月決算以外（12月決算等）や変則決算（決算期変更に伴う6ヶ月/15ヶ月決算等）を判定し、期間の長さ・種別をメタデータとして返す。Context の period は実際の期間がそのまま入る（E-3）
- dimensions/regulatory_transition: 四半期報告書と半期報告書のタクソノミ互換性情報 [TODO]
  - depends: contexts
  - detail: docType 140（四半期）と 160（半期）のタクソノミ構造が同一か、使用する concept set に差異があるかの情報を提供（G-1）
- dimensions/custom: 企業独自の Dimension 対応 [TODO]
  - depends: contexts, def_links
  - detail: 標準次元以外の企業固有次元（製品別、顧客別等）のハンドリング

## Text & Unstructured

XBRL の textBlockItemType タグおよび非構造化テキストへのアクセスを提供する。

- text_blocks: タグ単位でのテキストブロック抽出 [TODO]
  - depends: fetch
  - detail: XBRL の textBlockItemType を持つ全タグの内容を構造的に返す
- text_blocks/sections: 有報セクション名でのアクセス [TODO]
  - depends: text_blocks
  - detail: `filing.sections["事業等のリスク"]` のようなキーアクセス。対象セクション例:
    - 企業の概況（事業の内容）
    - 事業の状況（経営者による分析: MD&A）
    - 事業等のリスク
    - 経営上の重要な契約等
    - コーポレートガバナンスの状況
    - 経理の状況（注記事項）
    - 設備の状況
    - 株式の状況
- text_blocks/clean: テキストのクリーニング [TODO]
  - depends: text_blocks
  - detail: HTML タグ除去 → プレーンテキスト化。テーブル構造を保持するオプション付き。LLM 前処理用途

## Notes & Disclosure

有報の注記・附属情報から構造化データを抽出して返す。
法律で開示義務があるが jquants 等の API が提供しない情報を構造化する。
情報源はテキストブロック（テーブルパース）と `jpcrp_cor` 名前空間の数値 Fact の両方（E-1b）。

- notes/shareholders: 大株主の状況 [TODO]
  - depends: text_blocks, facts
  - detail: 株主名・持株数・持株比率のテーブルパース
- notes/customers: 主要な販売先（売上高 10% 超） [TODO]
  - depends: text_blocks, facts
  - detail: 顧客名・売上額・売上比率。サプライチェーン依存関係の分析基盤
- notes/related_parties: 関連当事者取引 [TODO]
  - depends: text_blocks, facts
  - detail: 取引先名・関係・取引内容・金額
- notes/subsidiaries: 子会社・関連会社情報 [TODO]
  - depends: text_blocks, facts
  - detail: 連結範囲の子会社一覧、持分比率、異動情報。Filing の `subsidiary_edinet_code` とも連携（J-4）
- notes/orders: 受注及び販売の状況 [TODO]
  - depends: text_blocks, facts
  - detail: 受注高・受注残高・販売実績をセグメント別テーブルでパース。受注生産型企業の先行指標
- notes/employees: 従業員の状況 [TODO]
  - depends: facts
  - detail: 従業員数・平均年齢・平均勤続年数・平均年間給与。`jpcrp_cor` の数値 Fact として構造化されている（E-1b）
- notes/executives: 役員の状況・報酬 [TODO]
  - depends: text_blocks, facts
  - detail: 役員報酬の総額・区分別内訳（固定/業績連動/株式）
- notes/capex: 設備投資の状況 [TODO]
  - depends: text_blocks, facts
  - detail: セグメント別の設備投資額・減価償却費・計画中の設備投資
- notes/accounting_policies: 会計方針の記述と変更 [TODO]
  - depends: text_blocks
  - detail: 会計方針の変更内容の抽出。jquants の `ChgByASRev` フラグだけではわからない「何がどう変わったか」の中身
- notes/appendix: 附属明細表 [NEEDS_FEEDBACK]
  - depends: text_blocks
  - detail: 有形固定資産等明細表、引当金明細表等。XBRL で構造化されているか要確認、PDF のみの可能性あり（E-1b）

## Sector-Specific

標準タクソノミにはない業種固有の勘定科目を明示的にサポートする。
calc_tree / taxonomy/standard_mapping と併用し、業種固有科目を標準科目の「部分集合」として位置づける。
業種ごとに使用する concept subset が異なるが、同じ `jppfs_cor` 名前空間内で定義される（E-5）。

- sector/banking: 銀行業 [WIP]
  - detail: 経常収益、経常費用、資金運用収支、役務取引等収支、特定取引収支、その他業務収支
- sector/insurance: 保険業 [WIP]
  - detail: 正味収入保険料、保険引受利益、資産運用収益
- sector/securities: 証券業 [WIP]
  - detail: 受入手数料、トレーディング損益、金融収益
- sector/construction: 建設業 [WIP]
  - detail: 完成工事高、完成工事原価、完成工事総利益
- sector/railway: 鉄道業 [WIP]
  - detail: 運輸収入、運輸雑収、運輸外収入

## Document-Type-Specific

有報以外の書類タイプ固有の構造化データ。

- doctype/tob: 公開買付関連書類 (240-340) [TODO]
  - detail: 買付価格、買付予定数、買付期間等の構造化
- doctype/large_holding: 大量保有報告書 (350-360) [TODO]
  - detail: 保有者名・保有割合・保有目的の構造化。アクティビスト動向の追跡基盤
- doctype/shelf_registration: 発行登録書 (080-110) [TODO]
  - detail: 発行予定額、調達目的等
- doctype/securities_notification: 有価証券届出書 (030-050) [TODO]
  - detail: 募集・売出の条件、資金使途
- doctype/funds: 投資信託・ETF 等の非事業法人の開示書類 [TODO]
  - detail: 事業法人とはタクソノミ体系が根本的に異なる。有価証券届出書（投資信託受益証券）、有価証券報告書（投資法人）等の構造化

## Filing Diff

2つのパース済み Filing オブジェクトを受け取り、構造的に比較するユーティリティ。

- diff/revision: 訂正前 vs 訂正後の差分 [TODO]
  - depends: facts, revision_chain
  - detail: 同一企業の原本と訂正版を Fact レベルで比較し、変更・追加・削除された科目を構造的に返す。訂正報告書は全体再提出のため全 Fact 比較で実装可能（G-7）
- diff/period: 前期 vs 当期の差分 [TODO]
  - depends: facts, contexts
  - detail: 同一企業の前期と当期を比較し、科目ごとの増減と新規出現・消滅した科目を返す。当期 filing 内の前期比較データと前年度 filing のデータは遡及修正時に不一致が生じうる（J-5, J-6）。どちらを「正」とするかの選択オプションを提供

## DataFrame API

1件の Filing のパース結果を DataFrame に変換する。複数 Filing の集約はユーザー側の責務（SCOPE.md 参照）。

- dataframe/facts: Fact の DataFrame 出力 [DONE]
  - depends: facts
  - detail: `Statements.to_dataframe()` で全 LineItem を 18 カラム DataFrame に変換。`FinancialStatement.to_dataframe(full=True)` で全カラム、`to_dataframe()` で従来 5 カラム（後方互換）
- dataframe/compare: 複数パース済み Filing の比較 DataFrame [TODO]
  - depends: facts, dimensions
  - detail: `edinet.compare(filings=[f1, f2, f3], dim_filter={"連結個別": "連結"}, include_custom_tags=True)`。パース済みオブジェクトを受け取るユーティリティ
- dataframe/export: エクスポート形式 [DONE]
  - depends: dataframe/facts
  - detail: `to_csv()` (UTF-8-sig)、`to_parquet()`、`to_excel()` を提供。`FinancialStatement` / `Statements` 両方に便利メソッドあり。pandas の既存機能を活用し独自シリアライザは持たない

## CLI

Jupyter 以外のユーザー（スクリプト連携、CI/CD パイプライン）向けのコマンドラインインターフェース。
1件の Filing に対する操作を提供する。

- cli/fetch: 書類の取得 [TODO]
  - detail: `edinet fetch --company トヨタ --doc-type 有報 --period 2024`
- cli/search: 書類の検索 [TODO]
  - detail: `edinet search --date 2025-06-20 --doc-type 大量保有報告書`
- cli/export: 1件の Filing のエクスポート [TODO]
  - depends: dataframe/export
  - detail: `edinet export --doc-id S100XXXX --format parquet --output toyota_2024.parquet`

## Validation

1件の Filing の XBRL データの整合性を検証する。

- validation/calc_check: 計算リンクに基づく加算チェック [TODO]
  - depends: calc_tree, facts
  - detail: 親科目の値が子科目の合計と一致するかを検証。`decimals` 属性に基づく丸め誤差の許容範囲を考慮（C-7）。不一致を警告付きで返す。実データでは丸め起因の軽微な不一致が一定割合で存在する
- validation/required_items: 必須科目の欠損検知 [TODO]
  - depends: facts, namespaces
  - detail: 書類タイプ・会計基準ごとに必須とされる科目が存在するかをチェック

## Display

Fact / Statement を人間が読みやすい形式で表示する。

- display/rich: ターミナル向けリッチ表示 [DONE]
  - detail: `display/rich.py` で Filing のリッチ表示を提供（実装済み）
- display/statements: 財務諸表の表形式表示 [DONE]
  - depends: statements, taxonomy/concept_sets
  - detail: ConceptSet の depth/is_abstract/is_total を使い階層表示。`DisplayRow` / `build_display_rows()` / `render_hierarchical_statement()` を提供。`FinancialStatement.__rich_console__` は ConceptSet がある場合に自動的に階層表示を使用
- display/html: HTML レンダリング [TODO]
  - depends: statements, source_linking
  - detail: Filing / list[Filing] / Statement に `_repr_html_` を実装し Jupyter でのインラインテーブル表示を提供。`edinet.view(filing)` でブラウザ上に詳細表示。Fact クリックで原文箇所にジャンプする source linking 連携

## Cross-Cutting Concerns

複数ドメインにまたがる設計方針・基盤機能。

- type_safety: Pydantic による型安全なモデル定義 [DONE]
  - detail: 金融データの型崩れ・単位誤認を開発時に排除。全モデルは frozen dataclass または Pydantic model
- async_support: 全 I/O 操作の async 対応 [DONE]
  - detail: `documents` / `adocuments`、`fetch` / `afetch` の同期・非同期ペア提供
- error_hierarchy: 構造化された例外体系 [DONE]
  - detail: `EdinetError` → `EdinetAPIError` / `EdinetParseError` / `EdinetConfigError`
- stubs: .pyi 型スタブの自動生成 [DONE]
  - detail: `uv run stubgen` でインターフェース定義を生成。新規開発時のコンテキスト圧縮に利用
- no_arelle: Arelle 非依存 [DONE]
  - detail: lxml ベースの軽量パーサー。依存を最小限に保つ


# EXTRA
## XBRL Core に関連
- kpi: 主要経営指標の抽出 [TODO]
  - depends: facts, contexts, dei
  - detail: jpcrp_cor:*SummaryOfBusinessResults の数値 Fact を構造化。
    BPS, EPS, PER, 配当, 配当性向, 自己資本比率, ROE, 従業員数,
    研究開発費, 設備投資額等。5期分の時系列データが1つの有報内に
    含まれるため、period_variants と同様の期間解決が必要。
    jpcrp_cor は jppfs_cor と同一 XBRL インスタンス内に
    存在するため、追加の fetch は不要
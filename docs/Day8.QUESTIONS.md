# Day 8 質問集 — XBRL 実装に必要な仕様情報

> **目的**: この質問集への回答が全て揃えば、PDF 仕様書やインターネット接続なしに、
> 既存のタクソノミファイル（ALL_20251101）と API ダウンロードファイルだけで
> 全書類型式 × 全社（全業種・全会計基準）の XBRL パース実装を完遂できる状態にする。
>
> **回答方法**: 各質問に対して、仕様書の該当箇所を引用しながら回答してください。
> 回答は `docs/Day8.ANSWERS.md` に記載してください。
>
> **回答の優先順位**: 以下の順で回答してください。特に ★ 付きの質問はパーサーのアーキテクチャを左右するため最優先です。
> 1. **★最優先**: K-2 (iXBRL)、K-3 (CSV代替可能性)、H-1b (DTS解決)、P-1 (実ファイル検証) — 回答次第でカテゴリ A 全体の前提が変わる
> 2. **高**: A-2, C-3, D-1, E-1, F-1 — パーサーの核心設計に直結
> 3. **中**: その他 — 実装品質・網羅性に影響
>
> **Day 9 着手に必要な最小回答セット**: 全問に回答する前に、以下の 5 問だけ先に回答すれば Day 9 のパーサー MVP に着手可能です。
> 1. **P-1a** + **P-2**（実ファイル）— iXBRL か従来型か、名前空間、Context 構造が一発で判明
> 2. **P-3**（提出者 .xsd）— DTS 解決の import URL が判明
> 3. **K-2**（iXBRL）— パーサーのアーキテクチャ決定
> 4. **K-3**（CSV）— XBRL パース自体の必要性判断
>
> **スコープ注記**: 各質問の末尾に `[v0.1.0]` / `[v0.2.0+]` の記載がある場合、回答の詳細度をそれに合わせて調整してください。

> **質問間の依存関係マップ**: 以下の質問は他の質問の前提を決定するため、最初に回答してください。
> ```
> K-2 (iXBRL) ──→ B-1.10, H-1, カテゴリ A 全体の前提, A-9/A-10 の回答前提
> K-3 (CSV)   ──→ XBRL パース自体の必要性
> H-1b (DTS)  ──→ カテゴリ C 全体のタクソノミ解決方法
> H-3 (バージョニング) ──→ H-1b の URL→ローカルパス変換, Q-2
> D-3 (会計基準判別) ──→ D-1, D-2 の調査範囲
> A-2 (Context) ──→ E-2 (連結/個別), E-3 (期間) の前提
> C-6 (Presentation) ──→ I-1, I-2, I-3 の前提
> I-1 (role URI) ──→ E-1 (財務諸表識別) に先行して回答すべき
> G-7 (訂正報告書) ──→ P-1e の回答後に検証
> J-6 (クロスフィリング) ──→ H-3 (バージョニング), J-5 (前期データ) に依存
> H-9b (キャッシュ戦略) ──→ C-11 (マージアルゴリズム), H-9 (規模感) に依存
> Q-2.4 (API提供期間) ──→ H-3 (対応すべきバージョン数)
> P-1 (実ファイル) ──→ A, B, K の多くの質問が自動回答
> P-6 (タクソノミサンプル) ──→ C, C-4 の多くの質問が自動回答
> ```
>
> **回答の粒度ガイダンス**: 表形式の質問（C-1, C-3 等）は表形式で簡潔に回答してください。XML 例を求めている質問は実際のファイルからコピー＆ペーストで構いません。
>
> **質問間の重複について**: 以下の質問は異なる文脈から同じ仕様を確認しています。重複する箇所は簡潔に「→ X-Y を参照」で済ませてください:
> - A-1 の IFRS 名前空間 → D-1.2 で詳述するため A-1 では簡潔でよい
> - B-1.10 の `find_primary_xbrl_path` → K-2.7 で詳述するため B-1.10 は簡潔でよい
> - H-1.3 のタクソノミ解決方法 → H-1b で詳述するため H-1.3 は要約のみでよい
>
> **回答不要の目安**: タクソノミファイル（ALL_20251101）や実際のダウンロード ZIP を直接読めば自明に回答できる質問は、**ファイルだけでは判断できない部分のみ回答してください**。特に P カテゴリの回答が得られると以下が自動回答されます:
> - **P-1** → B-1（ZIP構造）, K-2（iXBRL有無）, B-1.10（find_primary_xbrl_path 修正要否）
> - **P-2** → A-1（名前空間）, A-2（Context構造）, H-1（schemaRef）
> - **P-3** → H-1b（DTS解決, import URL）, E-6（拡張要素）, A-1（提出者名前空間URI）
> - **P-1f** → G-5（大量保有報告書構造）
> - **P-1g** → G-6（公開買付構造）
> - **P-1h** → G-8（特定有価証券構造）
> - **P-6** → C-3（業種一覧）, C-4（サフィックス体系）, C-9（concept属性）, C-10（XML構造）, C-5（ラベル構造）

---

## カテゴリ A: XBRL インスタンス文書の構造

### A-1. 名前空間宣言の全体像

実際の `.xbrl` ファイルのルート要素 `<xbrli:xbrl>` には、どのような名前空間が宣言されるか。
以下の各名前空間について、URI と用途を教えてください。

- `xbrli` — XBRL Instance 名前空間
- `xlink` — XLink
- `link` — XBRL Linkbase
- `xsi` — XML Schema Instance
- `iso4217` — 通貨コード
- `jppfs_cor` — 日本基準・財務諸表
- `jpcrp_cor` — 有報固有の報告項目
- `jpdei_cor` — 書類情報（DEI）
- `jpctl_cor` — 内部統制報告書（存在する場合）
- `jpsps_cor` — 特定有価証券（存在する場合）
- `jplvh_cor` — 大量保有報告書（存在する場合）
- `jptoi_cor`, `jptoo-*_cor` — 公開買付関連（存在する場合）
- `jpigp_cor` — 業種別勘定科目パッケージ
- 提出者別名前空間（例: `tse-acedjpfr-*`）

**補足質問（提出者別名前空間の URI パターンと検出アルゴリズム）:**
- 提出者別名前空間の URI パターンの具体例を複数示してください。提出者ごとに URI が異なるため、パターンマッチで検出するルールが必要です
- 例: `http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/xxxxx/...` のような形式か、完全に自由形式か
- **提出者名前空間の判定ルール**: 「この名前空間 URI は提出者固有である」と判定するルールは何か。`http://disclosure.edinet-fsa.go.jp/taxonomy/` で始まるものが標準、それ以外が提出者、で正しいか
- 提出者名前空間 URI の中に EDINET コード（例: `E02144`）が含まれるか

**特に知りたいこと:**
- IFRS 適用企業の場合、`jppfs_cor` の代わりにどの名前空間が使われるか（`ifrs-full`? `jppfs_cor` のまま?）
- US-GAAP 適用企業の場合はどうか
- IFRS/US-GAAP タクソノミは ALL_20251101 に含まれていないが、どこから取得するか。提出者 ZIP 内に同梱されるか

### A-2. Context 要素の構造

`<xbrli:context>` 要素の完全な構造を教えてください。

```xml
<xbrli:context id="???">
  <xbrli:entity>
    <xbrli:identifier scheme="???">???</xbrli:identifier>
    <xbrli:segment>???</xbrli:segment>  <!-- 存在する場合 -->
  </xbrli:entity>
  <xbrli:period>
    <!-- instant or duration -->
  </xbrli:period>
  <xbrli:scenario>???</xbrli:scenario>  <!-- 存在する場合 -->
</xbrli:context>
```

具体的に:

1. **`id` 属性の命名規則**: EDINET では Context ID に命名規則があるか。例: `CurrentYearDuration`, `Prior1YearDuration`, `CurrentYearInstant` 等の命名パターンは仕様で規定されているか、それとも企業が自由に命名できるか
2. **`entity/identifier`**: `scheme` 属性には何が入るか。EDINET コードか、法人番号か。値の形式は。`scheme` URI の全パターン一覧を示してください（例: `http://disclosure.edinet-fsa.go.jp` 以外の scheme はありうるか）
3. **`segment` vs `scenario`**: EDINET ではどちらを使うか。両方使う場合があるか
4. **`segment` の内部構造**: dimension（軸）とメンバーはどのように表現されるか。具体的な XML 例を示してほしい。特に:
   - 連結/個別の区別（`ConsolidatedMember` / `NonConsolidatedMember`）
   - セグメント情報（事業セグメント等）
   - その他の dimension（例: 前期/当期の修正再表示等）
5. **Typed Dimension vs Explicit Dimension**: EDINET で Typed Dimension（値が自由入力、例: セグメント名が文字列）は使われるか。Explicit Dimension のみか（member が taxonomy で事前定義）。Typed Dimension が使われる場合、値のデータ型は何か
6. **デフォルト dimension**: dimension が指定されていない Context のデフォルトメンバーは何か（例: 連結/個別軸のデフォルトは連結?）。XBRL Dimensions 仕様の default メカニズムとの関係
7. **Context の意味的等価性**: ID が異なるが内容（entity, period, segment）が同一の Context が複数存在するケースはあるか。ある場合、Fact の重複判定（A-7）でどう扱うか
8. **Context の総数の目安**: 1つの有報 XBRL に含まれる Context は何個程度か（10個? 50個? 100+?）。パース後のメモリ上の Context 管理方式（辞書で十分か）に影響
9. **period の形式**:
   - `instant`: `<xbrli:instant>2025-03-31</xbrli:instant>` の形式は固定か
   - `duration`: `startDate` / `endDate` の形式は固定か
   - 四半期決算の場合の period はどうなるか（3ヶ月 duration? 累計期間?）
   - 日付のフォーマット保証: 常に `xs:date`（`YYYY-MM-DD`）か。タイムゾーン情報が付くことはあるか（`2025-03-31+09:00` 等）。パーサーの `datetime.date` vs `datetime.datetime` の選択に直結
   - `<xbrli:forever/>` period（永久期間）は EDINET で使用されるか
10. **segment 内の dimension 要素の名前空間**: `xbrldi`（`http://xbrl.org/2006/xbrldi`）名前空間か。`<xbrldi:explicitMember dimension="...">...</xbrldi:explicitMember>` の `dimension` 属性は QName 形式（`prefix:localName`）か。この名前空間のスキーマは `ALL_20251101` 内に同梱されているか
11. **エンティティ識別子の変動**: 同一企業の EDINET コード変更、合併、社名変更時に `entity/identifier` の値は変わるか。`Company` モデルと XBRL の `entity` の紐付けに影響

### A-3. Fact 要素の構造

XBRL インスタンス内の個々の数値/テキスト Fact 要素について:

1. **数値 Fact の属性一覧**: `contextRef`, `unitRef`, `decimals`, `precision` — 全て必須か。`decimals` と `precision` は排他的か
2. **`decimals` の取りうる値**: `-6`（百万円）、`-3`（千円）、`0`、`INF` 以外にありうるか。仕様上の制約は
3. **`xsi:nil="true"` の扱い**: nil の場合、要素の内容は空か。`decimals` や `unitRef` は省略されるか
4. **テキスト Fact**: 非数値の要素（例: `jpdei_cor:FilerNameInJapaneseDEI`）はどのような属性を持つか。`unitRef` は省略されるか。`xml:lang` 属性は付与されるか（日本語/英語の区別に使われるか）
5. **非数値 Fact のデータ型バリエーション**:
   - `dateItemType`（日付型）の Fact は存在するか（例: `CurrentFiscalYearEndDateDEI` は日付型かテキスト型か）
   - `booleanItemType`（真偽値型）の Fact は存在するか（例: `WhetherConsolidatedFinancialStatementsArePreparedDEI` は `"true"`/`"false"` 文字列か）
   - `enumerationItemType`（列挙型）の Fact はあるか
   - これらの型情報は taxonomy の `.xsd` からどう取得するか（`xbrli:item` の `type` 属性?）
6. **空文字 Fact**: 要素は存在するが中身が空文字 `<jppfs_cor:SomeElement contextRef="..." unitRef="..." decimals="0"></jppfs_cor:SomeElement>` のケースは存在するか。その場合の解釈は
7. **符号の扱い**: 貸借対照表で負の値（例: マイナスの利益剰余金）はどう表現されるか。値がマイナス数値になるのか、`balance` 属性（debit/credit）で制御されるのか
8. **数値 Fact のテキスト内容のフォーマット**: 数値 Fact のテキスト内容に前後の空白やカンマ（例: `" 1,234,567 "`）が含まれるケースはあるか。パーサーで strip やカンマ除去を行うべきか。仕様上の数値のフォーマットルールは
9. **Fact の出現順序の意味**: インスタンス文書内での Fact 要素の出現順序に意味があるか（プレゼンテーション順と対応するか）。プレゼンテーションリンクベースが不完全な場合、出現順でフォールバック可能か
10. **`precision` vs `decimals` の実態**: EDINET の実際のインスタンス文書で `precision` 属性が使用されるケースはあるか。実態として `decimals` のみと考えてよいか
11. **XBRL 値と表示単位の関係（円 vs 百万円）**: 有報の表紙に「金額：百万円」と記載されている場合、XBRL の Fact 値は「円単位」か「百万円単位」か。例: 表示単位が百万円で売上高10億円の場合、Fact 値は `"1000"`（百万円単位）か `"1000000000"`（円単位）か。`decimals="-6"` は「百万円未満を丸めた」ことを示すが、Fact 値自体の単位は何か。Unit 要素の `iso4217:JPY` は「通貨が円」であることは示すがスケールファクターは示さない。これを誤ると全数値が6桁ずれるため、仕様上の明確な定義を教えてください。**iXBRL の場合**: `ix:nonFraction` の `scale` 属性（表示値 → XBRL値の 10^scale 変換）が関係するか。従来型 XBRL と iXBRL で値のスケールが異なる可能性はあるか
12. **Extensible Enumerations 2.0**: XBRL の Extensible Enumerations 2.0 仕様（`enum2:enumerationSetValueItemType` 等）の要素は EDINET で使用されるか。DEI の会計基準選択（`AccountingStandardsDEI`）等が列挙型の場合、パーサーで特別なハンドリング（列挙値の検証、QName 値の解決等）が必要か

### A-4. Unit 要素の構造

1. **通貨単位の表現**: `<xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>` が標準形式か
2. **株式数の単位**: 発行済株式数等の場合の unit 表現は。`xbrli:shares` のような標準的な measure が使われるか
3. **純粋数値（比率等）の単位**: `xbrli:pure` が使われるか
4. **複合単位（EPS/BPS 等）**: 1株当たり当期純利益（EPS）や1株当たり純資産（BPS）等の単位は `xbrli:divide` 要素（`unitNumerator` / `unitDenominator`）で表現されるか。実際の XBRL ファイルからの XML 例をコピー＆ペーストで示してください（推測ではなく実物）
5. **unit が存在しない Fact**: テキスト系の Fact には unit が不要と考えてよいか
6. **XBRL UTR（Unit Type Registry）準拠**: EDINET は XBRL UTR に準拠しているか。UTR に存在しない独自の unit measure が使われるケースはあるか。パーサーで UTR バリデーションを行うべきか
7. **複数通貨の共存**: 1つの XBRL インスタンスに `iso4217:JPY` 以外の通貨単位（例: `iso4217:USD`）の Fact が共存するケースはあるか（海外子会社のセグメント情報等）

### A-5. フットノート（footnoteLink） [v0.2.0+]

1. EDINET の `.xbrl` にフットノートリンクは含まれるか
2. 含まれる場合、パースする必要があるか（財務諸表の組み立てに影響するか）

### A-6. Tuple 型 Fact [v0.2.0+]

XBRL 2.1 では Fact を構造化するための Tuple（入れ子要素）がサポートされている。

1. EDINET の XBRL インスタンスで `xbrli:tuple` は使われるか
2. 使われる場合、どの書類型式・どのデータで使われるか（例: 大量保有報告書の保有銘柄リスト等）
3. Tuple 内の Fact は Context や Unit を親 Tuple から継承するか

### A-7. 重複 Fact

1. 同一の concept + 同一の context + 同一の unit で、複数の Fact が存在するケースはあるか（duplicate facts）
2. 存在する場合の処理方針（XBRL 仕様上は禁止か? EDINET の実態は?）
3. **Fact の一意性の厳密な定義**: XBRL 2.1 仕様上、2つの Fact が「重複」と判定される条件は何か（`concept` + `context` + `unit` + `xml:lang` の完全一致?）。consistent duplicate（同じ値）と inconsistent duplicate（異なる値）をパーサーでどう区別・処理すべきか

### A-8. Fact 要素の id 属性と xml:lang 属性

1. **`id` 属性**: 各 Fact 要素に `id` 属性は付与されるか。付与される場合、フットノートリンク（A-5）との紐付けに使われるか
2. **`xml:lang` 属性**: テキスト型 Fact に `xml:lang` 属性が付くケースはあるか。日本語と英語のテキスト Fact が同一 concept・同一 context で共存するか（例: 注記の日英両方）
3. **`xml:lang` の値の形式**: EDINET で使われる `xml:lang` の値は `ja`（ISO 639-1）か `ja-JP`（BCP 47）か `jpn`（ISO 639-2）か。英語の場合は `en` か `en-US` か。パーサーでの言語判定ロジックに影響

### A-9. テキスト Fact の HTML コンテンツ [v0.2.0+]

注記情報（J-3 と関連）のテキスト Fact について:

1. 注記のテキスト Fact は XHTML / HTML フラグメントとして格納されるか
2. エスケープされた HTML 文字列（`&lt;p&gt;...`）か、混合コンテンツ（XML 内に直接 XHTML 要素が入る）か
3. `xml:lang` 属性の存在有無

### A-10. テキスト Fact の空白正規化 [v0.2.0+]

1. テキスト型 Fact の改行・空白の扱い: XML の空白正規化ルール（`xs:string` vs `xs:normalizedString` vs `xs:token`）に従うか、raw 保存か
2. テキスト Fact の前後の空白は意味を持つか。パーサーで strip すべきか

---

## カテゴリ B: ZIP ファイルの内部構造

### B-1. ZIP 内のディレクトリ構造

`download_document(doc_id, file_type="1")` で取得される ZIP の完全なディレクトリ構造を教えてください。

```
XBRL_TO_CSV/              ← このプレフィックスディレクトリは常に存在するか?
  PublicDoc/                 それとも直接 PublicDoc/ か?
    *.xbrl          — XBRL インスタンス
    *.xsd           — 提出者別タクソノミスキーマ
    *_lab.xml       — 提出者別ラベルリンクベース（日本語）
    *_lab-en.xml    — 提出者別ラベルリンクベース（英語）
    *_pre.xml       — 提出者別プレゼンテーションリンクベース
    *_cal.xml       — 提出者別計算リンクベース
    *_def.xml       — 提出者別定義リンクベース
    *_ref.xml       — Reference Linkbase（法令条文への参照?）
    *.htm / *.html   — ???
  AuditDoc/
    ???
```

**ZIP ルート構造の確認**: 既存コードの `find_primary_xbrl_path` は `PublicDoc/` を前提としているが、`XBRL_TO_CSV/PublicDoc/` のような追加階層が存在する場合があるか。ZIP のルート構造のパターンを全て教えてください。

具体的に:

1. **`PublicDoc/` 内のファイル命名規則**: ファイル名の各パートの意味（例: `jpcrp030000-asr-001_E02144-000_2025-03-31_01_2025-06-26.xbrl` の各部分の意味）
2. **複数の `.xbrl` ファイルが存在するケース**: どのような場合に複数あるか。有報で「本体」と「監査報告書」が別ファイルになるか。連結用と個別用が別ファイルになるケースはあるか（1ファイルに連結・個別が混在するのが標準か）
3. **`.htm` / `.html` ファイル**: XBRL インライン（iXBRL）との関係は。EDINET では Inline XBRL は使われているか
4. **`AuditDoc/` の内容**: 監査報告書の XBRL か。パースすべきか。AuditDoc に XBRL が存在する場合、どのタクソノミモジュールが使われるか（`jpaud_cor` 等?）。`PublicDoc/` のタクソノミとの依存関係はあるか
5. **提出者別リンクベースファイル群**（`_lab.xml`, `_pre.xml`, `_cal.xml`, `_def.xml`）は必ず存在するか。省略されるケースはあるか
6. **`_ref.xml` ファイルの役割** [v0.2.0+]: Reference Linkbase の内容と用途（法令条文への参照?）。パースする必要があるか
7. **IFRS/US-GAAP 企業の ZIP 構造**: J-GAAP 企業と異なる点はあるか。IFRS タクソノミスキーマ（`.xsd`）は ZIP 内に同梱されるか
8. **空の ZIP / XBRL がない ZIP**: `file_type="1"` で取得した ZIP に `PublicDoc/` ディレクトリ自体が存在しないケースはあるか。ZIP 内に `.xbrl` も `.htm` も存在しないケースのハンドリング指針
9. **ZIP 内パスのエンコーディング**: ZIP 内のファイルパスに日本語が含まれるケースはあるか（Shift_JIS エンコーディングの可能性）
10. **既存コード `find_primary_xbrl_path` の前提の妥当性**: 現在のコードは `.xbrl` 拡張子を検索している。iXBRL のみの場合 `.htm` / `.xhtml` を探す必要があるが、既存コードの修正が必要か。K-2 の回答次第で判断が変わるため、K-2 と合わせて回答してほしい
11. **1つの ZIP 内の複数報告エンティティ**: 1つの ZIP 内に複数企業分の XBRL が含まれるケースはあるか（例: 公開買付の対象者と買付者の両方）。`find_primary_xbrl_path` のロジックに影響
12. **`file_type="1"` と `file_type="5"` の排他性**: 同一 `doc_id` で両方ダウンロード可能か。K-3（CSV代替）の判断材料
13. **ZIP 内の非 XBRL ファイル**: ZIP 内に `META-INF/` ディレクトリ（`manifest.xml`, `catalog.xml`, `taxonomyPackages.xml` 等）は存在するか。XBRL Report Package 仕様に準拠しているか。存在すれば H-1b の DTS 解決が大幅に簡素化される（H-1b.7 では ALL_20251101 側のパッケージ準拠を質問しているが、ここでは**提出者 ZIP 側**のパッケージ準拠を確認する）。画像ファイル（`.png`, `.jpg`）やその他の付随ファイルの有無・役割

### B-2. 提出者別タクソノミスキーマ（`.xsd`）

ZIP 内の `.xsd` ファイルについて:

1. このファイルの役割は何か。標準タクソノミ（ALL_20251101）との関係は
2. 企業独自の拡張要素（標準タクソノミにない勘定科目）はこのファイルで定義されるか
3. 拡張要素の名前空間はどうなるか（提出者固有の URI?）
4. インスタンス文書内の `schemaRef` 要素はこのファイルを指すか、標準タクソノミを指すか

### B-3. 書類型式ごとの ZIP の違い

以下の主要書類型式について、ZIP 内の `.xbrl` ファイルの有無と内容の違いを教えてください:

| doc_type_code | 書類 | XBRL の有無 | 財務諸表を含むか | 補足 |
|---|---|---|---|---|
| 120 | 有価証券報告書 | ? | ? | |
| 130 | 有価証券報告書（訂正） | ? | ? | |
| 140 | 四半期報告書 | ? | ? | |
| 150 | 四半期報告書（訂正） | ? | ? | |
| 160 | 半期報告書 | ? | ? | |
| 170 | 半期報告書（訂正） | ? | ? | |
| 030 | 有価証券届出書 | ? | ? | |
| 180 | 臨時報告書 | ? | ? | 財務諸表を含むケースはあるか。サブ分類（合併・子会社異動・代表者異動等）によって XBRL の内容が異なるか |
| 235 | 内部統制報告書 | ? | ? | |
| 240 | 公開買付届出書 | ? | ? | |
| 290 | 意見表明報告書 | ? | ? | |
| 350 | 大量保有報告書 | ? | ? | |

---

## カテゴリ C: タクソノミの構造

### C-1. タクソノミモジュール体系

ALL_20251101 内の各タクソノミモジュールについて、正式名称・対応する書類型式・含まれるデータの種類を教えてください。

| モジュール | 正式名称 | 対応する書類型式 (doc_type_code) | 主な内容 |
|---|---|---|---|
| `jppfs` | ? | ? | 財務諸表 |
| `jpcrp` | ? | ? | 有報の本体（企業情報等） |
| `jpcrp-esr` | ? | ? | ? |
| `jpcrp-sbr` | ? | ? | ? |
| `jpdei` | ? | ? | DEI（書類情報） |
| `jpctl` | ? | ? | 内部統制 |
| `jpsps` | ? | ? | 特定有価証券 |
| `jpsps-esr` | ? | ? | ? |
| `jpsps-sbr` | ? | ? | ? |
| `jpigp` | ? | ? | 業種別 GL（→ C-1b で詳細質問） |
| `jplvh` | ? | ? | 大量保有 |
| `jptoi` | ? | ? | 公開買付（発行者） |
| `jptoo-pst` | ? | ? | ? |
| `jptoo-toa` | ? | ? | ? |
| `jptoo-ton` | ? | ? | ? |
| `jptoo-tor` | ? | ? | ? |
| `jptoo-wto` | ? | ? | ? |
| `common` | ? | ? | ? |

### C-1b. jpigp（業種別勘定科目パッケージ）の使われ方

1. `jpigp_cor` 名前空間の要素はインスタンス文書内で直接使われるのか。それとも `jppfs_cor` のラベルを業種別に上書きするだけか
2. 企業の ZIP 内の `.xsd` が `jpigp` を import するパターンはあるか
3. `jpigp` と `jppfs` の業種カテゴリ（C-3）の関係は何か

### C-1c. common モジュールの役割

`ALL_20251101/taxonomy/common/2013-08-31/identificationAndOrdering_2013-08-31.xsd` について:

1. このファイルの役割は何か
2. 他のタクソノミモジュール（jppfs, jpcrp 等）からどのように参照されるか
3. パーサーで処理する必要があるか。DTS 解決の連鎖で到達する場合、無視してよいか

### C-2. エントリーポイントの命名規則

`samples/2025-11-01/` 内のエントリーポイントファイル名に含まれるサフィックスの意味:

| サフィックス | 正式名称 | 対応する doc_type_code |
|---|---|---|
| `srs` | ? | ? |
| `asr` | ? | ? |
| `ssr` | ? | ? |
| `esr` | ? | ? |
| `sbr` | ? | ? |
| `rst` | ? | ? |
| `rep` | ? | ? |
| `icr` | ? | ? |
| `lvh` | ? | ? |
| `ton` | ? | ? |
| `wto` | ? | ? |
| `tor` | ? | ? |
| `toa` | ? | ? |
| `pst` | ? | ? |
| `drs` | ? | ? |

**補足質問**: エントリーポイント名の数字部分（例: `jpcrp030000`）は様式コード（`form_code`）と対応するか。対応する場合、マッピングルールを教えてください。

**`samples/` ディレクトリの用途**: `samples/2025-11-01/` ディレクトリ自体の位置づけは何か。タクソノミのサンプルインスタンスか、エントリーポイントスキーマのリストか。パーサー実装で参照する必要があるか。

### C-3. 業種カテゴリコードの一覧

`jppfs/2025-11-01/r/` 配下の 23 の業種カテゴリコードについて:

| コード | 正式名称（日本語） | 英語名 | 適用する業種の具体例 |
|---|---|---|---|
| `bk1` | ? | ? | ? |
| `bk2` | ? | ? | ? |
| `cai` | ? | ? | ? |
| `cmd` | ? | ? | ? |
| `cna` | ? | ? | ? |
| `cns` | ? | ? | ? |
| `edu` | ? | ? | ? |
| `elc` | ? | ? | ? |
| `ele` | ? | ? | ? |
| `fnd` | ? | ? | ? |
| `gas` | ? | ? | ? |
| `hwy` | ? | ? | ? |
| `in1` | ? | ? | ? |
| `in2` | ? | ? | ? |
| `inv` | ? | ? | ? |
| `ivt` | ? | ? | ? |
| `lea` | ? | ? | ? |
| `liq` | ? | ? | ? |
| `med` | ? | ? | ? |
| `rwy` | ? | ? | ? |
| `sec` | ? | ? | ? |
| `spf` | ? | ? | ? |
| `wat` | ? | ? | ? |

**補足質問:**
- ある企業がどの業種カテゴリに属するかは、XBRL インスタンス文書のどこから判別できるか（schemaRef? DEI 要素? EDINET コード一覧 CSV の「提出者業種」?）
- EDINET コード一覧 CSV の「提出者業種」フィールドの値と、このタクソノミ業種コードの対応関係はあるか
- **一般事業会社コード**: `cns` が一般事業会社（製造業等）に対応するコードで正しいか。上場企業の大多数が `cns` に該当すると理解してよいか

### C-4. リンクベースファイルのサフィックス体系

各業種ディレクトリ内のファイル名に含まれるサフィックスの意味:

**連結/個別の区別:**

| サフィックス | 意味 |
|---|---|
| `ac` | ? (annual consolidated?) |
| `an` | ? (annual non-consolidated?) |
| `cm` | ? |
| `sc-t1` | ? (semi-annual consolidated type 1?) |
| `sc-t2` | ? (semi-annual consolidated type 2?) |
| `sn-t1` | ? (semi-annual non-consolidated type 1?) |
| `sn-t2` | ? (semi-annual non-consolidated type 2?) |

**補足質問**: `t1` と `t2` の違いは何か（type 1 / type 2? 具体的に何が異なるか）

**財務諸表の種類（ファイル名末尾）:**

| サフィックス | 意味 |
|---|---|
| `_bs` | 貸借対照表? |
| `_pl` | 損益計算書? |
| `_cf-di-*` | キャッシュフロー計算書（直接法）? |
| `_cf-in-*` | キャッシュフロー計算書（間接法）? |
| `_ss` | 株主資本等変動計算書? |

**BS のバリエーション（例: `_bs-1-BS-01-CA-Doubtful-2-ByGroup`）:**

ファイル名に含まれるバリエーション識別子の完全な意味を教えてください。例:
- `BS-01-CA-Doubtful-1-ByAccount` vs `BS-01-CA-Doubtful-2-ByGroup` vs `BS-01-CA-Doubtful-3-Direct`
- `BS-03-PPE-Dep-1-ByAccount` vs `BS-03-PPE-Dep-2-ByGroup` vs `BS-03-PPE-Dep-3-Direct`
- `PL-01-Sales-1-Net` vs `PL-01-Sales-3-ByType`
- `PL-04-SGA-1-ByAccount` vs `PL-04-SGA-2-OneLine`
- `PL-09-CI-1-SingleStatementNetOfTax` vs `PL-09-CI-2-SingleStatementBeforeTax`
- `CF-01-Method-Direct` vs `CF-03-Method-Indirect`

これらのバリエーションは、同一の財務諸表を異なる表示方式で表現するものか。ある企業がどのバリエーションを使用しているかは、XBRL インスタンスのどこから判別できるか。

### C-5. ラベルリンクベースの詳細構造

`jppfs_2025-11-01_lab.xml`（日本語ラベル）と `jppfs_2025-11-01_lab-en.xml`（英語ラベル）について:

1. **ラベルの role 一覧**: 仕様上定義されている role URI の完全なリスト。以下は推測だが、正確な URI と全種類を教えてください:
   - 標準ラベル: `http://www.xbrl.org/2003/role/label`
   - 冗長ラベル: `http://www.xbrl.org/2003/role/verboseLabel`
   - 他にあるか（`terseLabel`, `periodStartLabel`, `periodEndLabel`, `totalLabel`, `negatedLabel` 等）
2. **同一 concept に複数の role のラベルが存在する場合の優先順位**: EDINET の仕様で規定されているか
3. **`_gla.xml` ファイル**: `jppfs_2025-11-01_gla.xml` の役割は何か（Generic Label? 汎用ラベル?）。Generic Link は Label 以外にも使われるか（Generic Reference `_gra.xml` 等）。Generic Label と通常の Label Link の優先順位は。Generic Reference が存在する場合、パーサーで処理する必要があるか
4. **提出者別ラベル（ZIP 内の `_lab.xml`）と標準ラベル（ALL_20251101 内）の関係**: 同一 concept に対して両方にラベルがある場合、どちらが優先されるか。仕様で規定されているか
5. **ラベル解決の完全な優先順位アルゴリズム**: 以下の情報源とロールを組み合わせたとき、同一 concept に対してどのラベルを採用するかの完全なルールを教えてください:
   - 情報源: (a) 提出者別 `_lab.xml`（ZIP 内） (b) 標準タクソノミ `_lab.xml`（ALL_20251101/ 内） (c) Generic Label `_gla.xml`
   - role: 標準ラベル、冗長ラベル、`periodStartLabel`、`periodEndLabel`、`totalLabel` 等
   - 優先順位の例: 「同一 concept で提出者の標準ラベルがあればそれを使い、なければ標準タクソノミの標準ラベル、それもなければ Generic Label」のような完全なフォールバックチェーン
6. **ラベルが一切存在しない concept の扱い**: 提出者別にも標準タクソノミにも Generic Label にもラベルがない concept は存在するか。存在する場合、表示名として concept のローカル名（例: `NetSales`）をフォールバックに使ってよいか。また、日本語ラベルはあるが英語ラベルがない（またはその逆の）concept はどの程度存在するか
7. **ラベルリンクベースの extended link role**: ラベルリンクベースが `http://www.xbrl.org/2003/role/link`（デフォルト role）以外の role を使うケースはあるか。EDINET が独自 role を使っていると処理が変わる
8. **negatedLabel の使用状況**: 実際のプレゼンテーションリンクで `preferredLabel` に `negatedLabel` role が使われる頻度。これが使われると Fact の符号を反転して表示する必要があり、パーサーの数値処理に直接影響する

### C-6. プレゼンテーションリンクベースの詳細構造

`_pre.xml` ファイルについて:

1. **role URI**: プレゼンテーションリンクの role URI は何か。各財務諸表（BS/PL/CF/SS）はそれぞれ異なる role URI を持つか。その URI の完全なリストを教えてください
2. **親子関係（`order` 属性）**: 科目の並び順はどの属性で決まるか
3. **`preferredLabel` 属性**: 何を指定するか。具体的なユースケース（例: 「営業収益」という表示名の銀行 PL）
4. **抽象要素（abstract）**: プレゼンテーションツリーにのみ登場し Fact は持たない見出し要素があるか。例: 「流動資産」「固定資産」などの見出し
5. **提出者別 `_pre.xml`（ZIP 内）と標準 `_pre.xml`（タクソノミ内）の関係**: 提出者が並び順をカスタマイズしている場合、提出者の `_pre.xml` が標準を上書きするか、追加するか
6. **arc の override / prohibition メカニズム**: XBRL の `use="prohibited"` や `priority` 属性は EDINET で使われるか。提出者リンクベースが標準リンクベースと同一の extended link role を使った場合、同一 `from`/`to` の arc が複数ある場合の `priority` による解決ルールはどうなるか

### C-7. 計算リンクベースの詳細構造 [v0.1.0: 検算用、必須ではない]

`_cal.xml` ファイルについて:

1. **`weight` 属性**: `1` = 加算、`-1` = 減算 と理解してよいか。他の値はあるか
2. **計算ツリーの例**: 「営業利益 = 売上総利益 - 販管費」のような関係がどう表現されるか
3. **計算リンクの role URI**: プレゼンテーションと同じ role URI を使うか
4. **v0.1.0 での必要性**: 計算リンクベースをパースしなくても財務諸表の組み立ては可能か。検算用途のみか
5. **計算不一致の扱い**: 計算リンクベースに基づく検算で不一致（例: 子科目の合計 ≠ 親科目の値）が検出されるケースは実際にどの程度あるか。丸め誤差の許容範囲は仕様で定義されているか（`decimals` の値に基づく?）。不一致がある場合、Fact の値自体は信頼してよいか
6. **Calculations 1.1 仕様への対応**: EDINET は XBRL International が策定した Calculations 1.1 仕様（より厳密な計算検証）に対応しているか。従来の `summation-item` のみか

### C-8. 定義リンクベースの詳細構造 [v0.1.0: 連結/個別判別に必要な範囲のみ]

`_def.xml` ファイルについて:

1. **ディメンション（Hypercube）の構造**: `xbrldt:hypercubeItem`, `xbrldt:dimensionItem` はどう使われるか
2. **EDINET で使われる主な dimension 一覧**:
   - 連結/個別軸
   - セグメント軸
   - 他にあるか
3. **v0.1.0 での必要性**: 定義リンクベースをパースしなくても dimension の処理は可能か。Context の `segment` 要素だけで足りるか
4. **arcroleType の一覧**: Definition Linkbase で使われる arcrole の完全なリストと意味を教えてください（例: `all`, `notAll`, `hypercube-dimension`, `dimension-domain`, `domain-member`, `dimension-default` 等）

### C-9. Concept 定義の属性一覧

タクソノミ `.xsd` 内の concept 定義（`xs:element`）に付与される属性の完全なリストを教えてください。特に:

1. **`xbrli:periodType`**（`instant` / `duration`）: Context の period 型との整合性チェックに必須。BS 科目は `instant`、PL/CF 科目は `duration` と理解してよいか
2. **`xbrli:balance`**（`debit` / `credit`）: 符号の解釈に影響するか。A-3.7 の符号の扱いとの関係
3. **`abstract`**（`true` / `false`）: 見出し専用の要素か。Fact を持たない要素の識別に使うか
4. **`nillable`**（`true` / `false`）: `xsi:nil="true"` が許容される要素の識別
5. **`substitutionGroup`**（`xbrli:item` / `xbrli:tuple`）: item と tuple の区別方法
6. **`type`**（データ型）: `monetaryItemType`, `stringItemType`, `dateItemType` 等。A-3.5 の非数値型バリエーションの判定にこの属性を使うか
7. これらの属性がパーサー実装にどう影響するか（例: `periodType` の不一致は致命的エラーか警告か）
8. **concept ローカル名のキャラクタセット**: concept のローカル名（例: `NetSales`）は常に ASCII 文字のみか。日本語や全角文字がローカル名に含まれるケースはあるか。辞書キーやファイル名の設計に影響

### C-10. リンクベースの XML 構造（loc / arc / arcrole）

リンクベース（`_pre.xml`, `_cal.xml`, `_def.xml`, `_lab.xml`）の XML レベルの構造を教えてください。パーサーの実装に必須:

1. **`link:loc`（ロケーター）要素の構造**:
   - `xlink:href` の形式は相対 URI + フラグメント識別子か（例: `jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales`）
   - `xlink:label` 属性の命名規則はあるか（例: concept 名をそのまま使うか）
   - `xlink:label` のスコープは同一 `extendedLink` 要素内でユニークか
2. **`link:presentationArc` 要素の構造**:
   - `xlink:from` / `xlink:to` は `link:loc` の `xlink:label` 値を参照するか
   - `xlink:arcrole` の値は `http://www.xbrl.org/2003/arcrole/parent-child` で正しいか
   - `order`, `priority`, `use`, `preferredLabel` の各属性の詳細
3. **`link:calculationArc` 要素の構造**:
   - `xlink:arcrole` は `http://www.xbrl.org/2003/arcrole/summation-item` で正しいか
   - `weight` 属性の位置（arc 要素の属性か）
4. **`link:definitionArc` 要素の構造**:
   - `xlink:arcrole` の値一覧（C-8.4 と関連）
5. **`link:labelArc` 要素の構造**:
   - `link:loc`（concept への参照）と `link:label`（ラベルリソース）を結ぶ仕組み
   - `xlink:arcrole` は `http://www.xbrl.org/2003/arcrole/concept-label` で正しいか
6. **具体的な XML 例**: プレゼンテーションリンクベースの `extendedLink` 1つ分（`link:presentationLink` 要素全体）の完全な XML 例を示してください（3〜5 個の loc と arc を含む）

### C-12. XBRL Formula / Assertion Linkbase [v0.2.0+]

XBRL Formula 仕様（assertion によるバリデーション）について:

1. EDINET のタクソノミに Formula Linkbase / Assertion Linkbase は含まれるか
2. 含まれる場合、パーサーで処理（実行）する必要があるか。Calculation Linkbase（C-7）の検算で十分か
3. XBRL Formula の処理は Arelle 等の既存ツールに任せて、自前パーサーでは無視してよいか

### C-11. リンクベースのマージアルゴリズム（提出者 + 標準）

提出者の拡張リンクベース（ZIP 内）と標準タクソノミのリンクベース（ALL_20251101 内）の統合ルール:

1. **同一 role URI の extendedLink が両方に存在する場合**: arc は加算（追加）されるか、置換されるか
2. **同一 `from` / `to` の arc が複数ある場合**: `priority` 属性の値が高い方が勝つか。`priority` が同一の場合はどうなるか
3. **`use="prohibited"` の効果**: 同一 `from` / `to` かつ同等以下の `priority` の arc を無効化するか。prohibited arc 自体は結果ツリーから除外されるか
4. **適用範囲**: このマージルールはプレゼンテーション・計算・定義・ラベルの全リンクベースで共通か。リンクベースの種類によって異なるルールはあるか
5. **具体例**: 標準タクソノミの `_pre.xml` に「A → B (order=1)」「A → C (order=2)」があり、提出者の `_pre.xml` に「A → B (use=prohibited)」「A → D (order=1.5)」がある場合、最終的なツリーは「A → D (1.5), A → C (2)」になるか
6. **arc の等価性ルール**: 2つの arc が「同一」と見なされる条件は何か。XBRL 仕様では `from`, `to`, `arcrole` が同一の arc が等価と見なされるが、`order` 属性も等価性判定に含まれるか。この定義次第で prohibition の適用範囲が変わるため、正確な条件を教えてください

---

## カテゴリ D: 会計基準の差異

### D-1. IFRS 適用企業の XBRL [v0.2.0+]

1. **タクソノミの入手方法**: IFRS タクソノミ（`ifrs-full` 名前空間等）は ALL_20251101 に含まれていない。以下のどれか:
   - a. 提出者の ZIP に IFRS タクソノミファイルが同梱される
   - b. IFRS Foundation のサイトからダウンロードする必要がある
   - c. EDINET が独自に IFRS 拡張タクソノミを提供している
   - d. その他
2. **名前空間**: IFRS 企業の `.xbrl` で使われる名前空間は `ifrs-full` か。EDINET 独自のプレフィックスがあるか
3. **勘定科目の違い**: IFRS では `jppfs_cor:NetSales` の代わりに何が使われるか。主要科目（売上高、営業利益、経常利益、当期純利益、総資産、純資産）の IFRS 対応 concept 名
4. **「経常利益」の扱い**: J-GAAP 固有の「経常利益」（OrdinaryIncome）は IFRS には存在しないはず。IFRS 企業はこの科目をどう扱うか
5. **Context 構造の違い**: IFRS 企業でも Context の構造は J-GAAP と同じか
6. **ラベル**: IFRS の日本語ラベルはどこから取得するか

### D-2. US-GAAP 適用企業の XBRL [v0.2.0+]

1. D-1 と同じ質問群を US-GAAP について
2. **日本での US-GAAP 適用企業数**: 実際にどの程度存在するか（把握していれば）

### D-3. 会計基準の判別方法 [v0.1.0]

XBRL インスタンス文書から、その企業の会計基準（J-GAAP / IFRS / US-GAAP）を判別する方法:

1. **DEI 要素**: `jpdei_cor:AccountingStandardsDEI` のような要素が存在するか。存在する場合、取りうる値は
2. **名前空間による推定**: `jppfs_cor` → J-GAAP、`ifrs-full` → IFRS と推定できるか
3. **schemaRef による推定**: schemaRef が参照するタクソノミ URI から判別可能か

---

## カテゴリ E: 財務諸表の組み立てロジック

### E-1. 財務諸表の種類と識別

XBRL インスタンス内の Fact 群から、以下の 4 つの財務諸表に分類するルールは何か:

1. **損益計算書 (PL)** / 損益及び包括利益計算書
2. **貸借対照表 (BS)**
3. **キャッシュフロー計算書 (CF)**
4. **株主資本等変動計算書 (SS)**

具体的に:
- 分類の基準は concept の名前空間プレフィックスか、role URI か、それ以外か
- PL の concept は全て `jppfs_cor:` 名前空間か。`jpcrp_cor:` に属するものもあるか
- BS/CF/SS についても同様
- 「どの concept がどの財務諸表に属するか」を決定的に判断するための仕様上のルールは何か（プレゼンテーションリンクの role URI で判断すべきか）

### E-1b. 非財務構造化データの扱い

有報の XBRL には財務4表（BS/PL/CF/SS）以外にも `jpcrp_cor` で構造化された重要データが含まれる:

1. 財務4表に属さない Fact の割合はどの程度か（全 Fact 中）
2. `jpcrp_cor` 名前空間の Fact にはどのような情報が含まれるか（例: 従業員の状況、平均年間給与、設備投資額、配当の状況、大株主の状況、役員報酬 等）
3. これらの非財務 Fact を分類する role URI は存在するか（例: `rol_EmployeeInformation`, `rol_DividendInformation` のような role があるか）
4. v0.1.0 では財務4表のみを対象とするが、将来の拡張を考慮したデータモデル設計上、非財務 Fact を格納する汎用的な仕組みが必要か
5. **附属明細表**: 有報の附属明細表（有形固定資産等明細表、引当金明細表等）は XBRL で構造化されているか。されていない場合、PDF のみから取得する必要があるか

### E-1c. 株主資本等変動計算書（SS）の2次元構造

SS は本質的に2次元テーブル（行 = 資本金・資本剰余金等、列 = 当期首残高・変動額・当期末残高）である:

1. SS の2次元構造は XBRL 上どう表現されるか。列方向の区別は Context の period（instant vs duration）で行うのか、dimension で行うのか
2. presentation linkbase だけで SS を組み立てられるか。definition linkbase の dimension が必要か
3. H-7 の Table Linkbase が SS の組み立てに必須か
4. SS の行・列ヘッダーの取得方法（ラベルリンクベース? プレゼンテーションリンクベース?）

### E-1d. キャッシュフロー計算書（CF）の直接法 / 間接法の識別

1. CF の直接法 / 間接法の区別は XBRL 上どう表現されるか。使用する concept が異なるか（`CF-01-Method-Direct` vs `CF-03-Method-Indirect` のバリエーションに対応する異なる concept セット?）
2. 直接法か間接法かを判定する方法: DEI 要素か、role URI か、concept の有無か
3. 日本の上場企業で直接法を採用している企業はあるか（実態として間接法のみと仮定してよいか）

### E-2. 連結/個別の区別

1. **Context 内の dimension**: 連結/個別はどの dimension で区別されるか。dimension 名と member 名を教えてください
2. **dimension なしの Fact**: dimension が一切ない（segment 要素がない）Context に紐づく Fact は、連結か個別か。それとも「区別なし」か。XBRL Dimensions 仕様の「デフォルトメンバー」の概念と、EDINET でのデフォルト（連結がデフォルト?）との関係
3. **連結財務諸表がない企業**: 非上場企業等で連結財務諸表が存在しない場合、個別のみの Fact はどのような Context になるか

### E-3. 期間の取り扱い

1. **複数期間データ**: `.xbrl` には当期・前期（場合によっては前々期）のデータが含まれる。これらは全て別の Context で区別されるか
2. **四半期の期間表現**: 第1四半期の場合:
   - 累計期間（4月〜6月）の PL なのか、四半期単独（4月〜6月）なのか
   - 前年同期との比較データも含まれるか
3. **BS の期間**: 期末時点（instant）のみか。期首時点のデータも含まれるか
4. **CF の期間**: 累計期間（duration）か
5. **Filing.period_start / period_end と Context period の関係**: 既存の `Filing` モデルの `period_start` / `period_end` は EDINET API から取得される値。XBRL 内の Context の period とこれらが一致する保証はあるか。ずれるケースはあるか（例: 訂正報告書で API の期間と XBRL の期間が異なる等）
6. **変則的な会計期間**: 決算期変更に伴う変則的な会計期間（例: 15ヶ月間の移行期間、6ヶ月短縮決算）の XBRL 表現はどうなるか。Context の period は実際の期間（例: `2024-01-01` ~ `2025-03-31`）がそのまま入るか
7. **連結会計年度と個別会計年度のずれ**: 連結子会社の決算期が異なる場合、連結と個別で期間が異なる Context が混在するか
8. **非3月決算企業**: 12月決算企業（例: ソニー）や6月決算企業の場合、Context ID の命名パターンは3月決算企業と同じ規則か。period の日付以外に構造的な違いはあるか

### E-4. EPS・BPS 等の1株当たり情報

財務諸表の重要指標として:

1. **concept の所属**: EPS（1株当たり当期純利益）、BPS（1株当たり純資産）等の concept はどの名前空間に属するか（`jppfs_cor`? `jpcrp_cor`?）
2. **unit の表現**: 「円/株」のような複合単位は `xbrli:divide` で表現されるか。それとも通貨単位（`iso4217:JPY`）+ `decimals` で処理されるか
3. **潜在株式調整後 EPS**: 別の concept が存在するか

### E-5. 業種別の財務諸表の差異

23 の業種カテゴリごとに、財務諸表の構造がどう異なるか:

1. **銀行 (bk1, bk2) の PL**: 「売上高」の代わりに何が最上位科目か。主要科目の concept 名
2. **保険 (in1, in2) の PL**: 同上
3. **証券 (sec) の PL**: 同上
4. **一般事業会社 (cns 等) と上記特殊業種の BS の差異**: BS でも科目体系が異なるか
5. **同じ `jppfs_cor` 名前空間内で業種ごとに異なる concept が使われるのか**: それとも全業種共通の concept のうち、使用する subset が異なるだけか

### E-6. 提出者独自の拡張科目

1. **拡張科目の扱い**: 標準タクソノミにない企業独自の勘定科目が使われるケースはどの程度あるか
2. **拡張科目のラベル取得方法**: 提出者別 `_lab.xml` のみにラベルが存在するか
3. **拡張科目の PL/BS/CF への分類**: 拡張科目がどの財務諸表に属するかは、提出者別 `_pre.xml` の role URI で判断するか
4. **拡張科目の親子関係**: 拡張科目は標準科目の子要素として定義されるか。例: 標準の「その他」の下に企業独自の明細科目を追加する形
5. **拡張タクソノミの制約**: 提出者が標準タクソノミの concept を「再定義」（型の変更、`periodType` の変更等）することは禁止されているか。禁止されていない場合、提出者 `.xsd` の要素定義が標準タクソノミのそれを上書きするか
6. **拡張要素のアンカリング**: ESEF（欧州）ではタクソノミ拡張時に基盤タクソノミの concept への anchoring（wider-narrower 関係の宣言）が要求される。EDINET でも同様の制約があるか。ある場合、定義リンクベースに `wider-narrower` arcrole の arc が含まれるか。これにより拡張科目の意味的な位置付け（「この拡張科目は標準の○○に近い」）を自動判定可能か

### E-7. 主要勘定科目の concept 名辞書 [v0.1.0]

パーサー MVP に必要な主要勘定科目について、J-GAAP の concept 名（`namespace:localName`）と **期間型（`instant` / `duration`）** を教えてください。期間型は Context の period との整合性チェック（C-9.1）に必要です。

**BS（貸借対照表）** — 期間型は全て `instant` と推定:
流動資産合計、固定資産合計、資産合計、流動負債合計、固定負債合計、負債合計、純資産合計、資本金、利益剰余金

**PL（損益計算書）** — 期間型は全て `duration` と推定:
売上高、売上原価、売上総利益、販管費、営業利益、経常利益、税引前当期純利益、当期純利益、親会社株主に帰属する当期純利益

**CF（キャッシュフロー計算書）** — 期間型は `duration` と推定（期末残高は `instant`?）:
営業活動によるキャッシュフロー、投資活動によるキャッシュフロー、財務活動によるキャッシュフロー、現金及び現金同等物の期末残高

**SS（株主資本等変動計算書）** — 期間型は行項目により混在?:
主要な行項目の concept 名（資本金、資本剰余金、利益剰余金、自己株式、株主資本合計）

**DEI から取得すべきもの:**
F-1 で列挙した DEI 要素の正確な concept 名

---

## カテゴリ F: DEI（Document and Entity Information）

### F-1. DEI 要素の一覧

`jpdei_cor` 名前空間に含まれる主要な DEI 要素とその値の形式:

1. **`FilerNameInJapaneseDEI`**: 提出者名（日本語）
2. **`FilerNameInEnglishDEI`**: 提出者名（英語）
3. **`SecurityCodeDEI`**: 証券コード
4. **`EDINETCodeDEI`**: EDINET コード
5. **`AccountingStandardsDEI`**: 会計基準（存在するか? 値は?）
6. **`WhetherConsolidatedFinancialStatementsArePreparedDEI`**: 連結財務諸表の有無（存在するか?）
7. **`CurrentFiscalYearEndDateDEI`**: 決算日
8. **`TypeOfCurrentPeriodDEI`**: 報告期間の種別（通期/四半期等）
9. **`IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI`**: 業種コード（存在するか? C-3 の業種カテゴリコードとの対応は?）
10. **`DocumentIDDEI`（提出書類管理番号）**: XBRL インスタンス内に `doc_id`（EDINET API の `doc_id` フィールドに対応する値）を格納する DEI concept は存在するか。存在する場合の concept 名は。API レスポンスの `doc_id` と XBRL 内の値の一致は保証されるか
11. 他に実装上重要な DEI 要素があれば全て列挙してください

**各 DEI 要素のデータ型**: 上記の各要素について、タクソノミ `.xsd` 上のデータ型（`stringItemType`, `dateItemType`, `booleanItemType`, `enumerationItemType` 等）を明示してください。パーサーでの値変換ロジック（文字列→日付、文字列→真偽値 等）の実装に必要

### F-1b. DEI 要素の Context

1. DEI 要素の Fact はどの Context に紐づくか（例: `FilingDateInstant`? `CurrentYearDuration`?）
2. DEI 専用の Context パターンはあるか（他の財務データとは異なる期間の Context を使うか）
3. DEI の Fact に dimension（segment）は付与されるか

### F-2. DEI の利用シーン

DEI 要素をパースすることで、以下の判断に使えるか:
- 会計基準の判別（D-3 と関連）
- 業種カテゴリの判別（C-3 と関連）
- 連結/個別の有無の判別
- 報告期間の種別（通期/四半期/半期）の判別

---

## カテゴリ G: 書類型式ごとの XBRL 構造の差異

### G-1. 有報 (120) / 四半期報告書 (140) / 半期報告書 (160)

1. **XBRL の構造的差異**: 有報・四半期報告書・半期報告書で、XBRL の構造に根本的な違いはあるか。名前空間は同じか
2. **四半期の場合のタクソノミ**: 四半期決算用の別のタクソノミモジュールがあるか。それとも通期と同じ `jppfs` を使うか
3. **四半期の簡素化**: 四半期報告書では BS/PL/CF のうち省略されるものはあるか
4. **四半期報告書制度の廃止**: 2024年4月から四半期報告書制度が廃止され、半期報告書＋決算短信体制に移行した。これにより XBRL 提出の書類型式にどのような変化があったか。`doc_type=140`（四半期報告書）は2024年4月以降の新規提出がないか。半期報告書 (160) の提出頻度は増えたか。決算短信の XBRL は EDINET で取得可能か
5. **半期報告書と四半期報告書の構造同一性**: 半期報告書 (160) の XBRL 構造は四半期報告書 (140) と同一か。使用するタクソノミモジュール、名前空間、Context の期間パターンに違いはあるか

### G-2. 有価証券届出書 (030) [v0.2.0+]

1. 有価証券届出書に財務諸表の XBRL は含まれるか
2. 含まれる場合、有報 (120) と同じ構造か
3. 届出書固有の XBRL 要素（発行条件等）はあるか

### G-3. 臨時報告書 (180) [v0.2.0+]

1. 臨時報告書に XBRL は含まれるか（`has_xbrl` が true になるケース）
2. 含まれる場合、財務データを含むか。それとも DEI のみか

### G-4. 内部統制報告書 (235) [v0.2.0+]

1. `jpctl` タクソノミの概要
2. 内部統制報告書の XBRL に含まれるデータの種類（テキスト? 数値?）

### G-5. 大量保有報告書 (350) [v0.2.0+]

1. `jplvh` タクソノミの概要
2. 保有株式数、保有割合等の数値データは XBRL で構造化されているか
3. **データ表現方式**: 保有銘柄リストは Fact の羅列か、Tuple（A-6）か、Dimension で構造化されているか。共同保有者の表現方法は
4. **保有割合の Fact**: `decimals` / `unit` はどうなるか（パーセント表記? `xbrli:pure`?）

### G-6. 公開買付関連書類 (240, 260, 270, 290, 310, 330) [v0.2.0+]

1. `jptoi`, `jptoo-*` タクソノミの概要
2. 公開買付価格、買付期間等の情報は XBRL で構造化されているか
3. **対象者・買付者の関係表現**: 1つの ZIP 内に複数エンティティの Fact が含まれるか。エンティティの区別は Context の `entity` で行うか、Dimension で行うか

### G-7. 訂正報告書の XBRL

1. **訂正報告書 (130, 150, 170 等) の XBRL**: 訂正箇所のみを含むか、全体を再提出するか。訂正報告書提出後も、原本（訂正前）の `doc_id` でダウンロード可能か。API 上 `withdrawal_status` が変わるか
2. **訂正前との差分**: 訂正前の値との差分を取る仕組みはあるか。それとも全置換か
3. **訂正報告書の連鎖関係**: 訂正報告書の `.xbrl` 内に「訂正元の `doc_id`」への参照はあるか
4. **複数回訂正**: 原本 → 第1回訂正 → 第2回訂正の場合、XBRL 上の関係はどうなるか
5. **`parent_doc_id`（API で取得済み）と XBRL 内の参照の関係**: API レスポンスの `parent_doc_id` だけで訂正チェーンを辿れるか、それとも XBRL 内にも参照があるか

### G-8. 特定有価証券関連 [v0.2.0+]

1. `jpsps` タクソノミはどのような書類に使われるか（投資信託の報告書?）
2. 財務諸表を含むか
3. **基準価額 (NAV) の報告構造**: 基準価額は数値 Fact として構造化されているか。複数サブファンドの表現方法（Dimension?）
4. **信託報酬の構造**: 信託報酬率・金額は XBRL Fact として含まれるか

### G-8b. 外国企業のフォーマット差異 [v0.2.0+]

日本に上場する外国企業（外国会社報告書 `doc_type=380` 等）の XBRL について:

1. 外国企業の有報（`ordinance_code="020"` 等）の XBRL は国内企業と同じタクソノミ・名前空間構造か
2. 異なるタクソノミ（IFRS / US-GAAP ネイティブ等）を使用するか
3. v0.1.0 でパースを試みた際にエラーが出るか（スキップすべきか）

### G-9. ordinance_code / form_code → タクソノミモジュールのマッピング

既存の `Filing` モデルに `ordinance_code` と `form_code` がある。XBRL をダウンロードする前にタクソノミモジュールを予測するために:

1. `ordinance_code` と `form_code` の組み合わせから、XBRL で使用されるタクソノミモジュール（`jppfs`, `jpcrp`, `jpctl`, `jplvh` 等）を一意に特定できるか
2. 対応表があれば示してください（例: `ordinance_code="010"` + `form_code="030000"` → `jpcrp` + `jppfs`）
3. この情報はパーサーの事前準備（必要なタクソノミのプリロード等）に使えるか

---

## カテゴリ H: 実装上の重要な仕様詳細

### H-1. schemaRef と linkbaseRef

インスタンス文書内の以下の参照要素について:

```xml
<link:schemaRef xlink:type="simple" xlink:href="???"/>
<link:linkbaseRef xlink:type="simple" xlink:href="???" xlink:role="???"/>
```

1. **`schemaRef` の `href` の形式**: 相対パスか絶対 URL か。提出者別スキーマを指すか
2. **`linkbaseRef` の有無**: 存在する場合、何を指すか。ラベルリンクベースへの参照か
3. **タクソノミの解決方法**: `schemaRef` → 提出者別 `.xsd` → `import` で標準タクソノミ参照、という連鎖で正しいか
4. **`xsi:schemaLocation` 属性**: インスタンス文書のルート要素に `xsi:schemaLocation` 属性は付与されるか。付与される場合、名前空間 URI → スキーマ URL のペアが列挙される形式か。`schemaRef` との関係は（冗長? 補完?）。DTS 解決で `xsi:schemaLocation` も参照すべきか
5. **リンクベースの発見経路**: リンクベースファイルへの参照は、(a) インスタンス文書内の `link:linkbaseRef` (b) タクソノミスキーマ `.xsd` 内の `xs:appinfo/link:linkbaseRef` (c) その両方、のどれで発見されるか。提出者の拡張リンクベース（`_pre.xml` 等）はどちらの経路で参照されるか
6. **`schemaRef` の多重性**: XBRL 2.1 仕様では `schemaRef` は複数許容される。EDINET の実際のインスタンス文書で複数の `schemaRef` が存在するケースはあるか。ある場合、全てを DTS に含めるか
7. **`link:roleRef` / `link:arcroleRef` 要素**: インスタンス文書内に `link:roleRef` や `link:arcroleRef` 要素は含まれるか。フットノートリンク（A-5）やディメンション使用時に必要か。パーサーで処理すべきか

### H-1b. DTS（Discoverable Taxonomy Set）解決アルゴリズム ★パーサーのアーキテクチャに直結

タクソノミ参照の解決方法の具体的な詳細:

1. **提出者 `.xsd` 内の `xs:import` 要素の `schemaLocation`**: 相対パスか絶対 URL か
2. **URL → ローカルパスの変換規則**: 標準タクソノミの参照先が `http://disclosure.edinet-fsa.go.jp/taxonomy/...` のような URL の場合、ローカルの `ALL_20251101/` へのマッピングルールは何か。**具体的な URL 5〜10 個**とそれに対応する `ALL_20251101/` 内のローカルパスを列挙してください。例:
   ```
   http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd
   → ALL_20251101/taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd
   ```
   のような対応を、主要モジュール（jppfs, jpcrp, jpdei, jpigp, common 等）について示してください
3. **import の連鎖の深さ**: 提出者 `.xsd` → `jpcrp_cor.xsd` → `jppfs_cor.xsd` → `xbrl-instance.xsd` のような import 連鎖は何段階あるか。実際の提出者 `.xsd` の `xs:import` 要素を全て列挙した例を示してください
4. **各 import で参照される `.xsd` の `ALL_20251101/` 内での対応パス**: 具体的なパスマッピングの一覧
5. **URL のベース部分**: `http://disclosure.edinet-fsa.go.jp/taxonomy/` が固定プレフィックスで、これを `ALL_20251101/taxonomy/` に置換すれば全て解決できるか。例外はあるか（XBRL International の標準スキーマ等）
6. **XBRL International 標準スキーマの所在**: 提出者 `.xsd` の import 連鎖を辿ると、最終的に XBRL International の標準スキーマ（`http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd`, `http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd`, `http://www.xbrl.org/2003/xl-2003-12-31.xsd`, `http://www.xbrl.org/2005/xbrldt-2005.xsd` 等）および W3C スキーマ（`http://www.w3.org/2001/xml.xsd`）に到達する。これらは `ALL_20251101` 内に同梱されているか。同梱されている場合のローカルパスは。同梱されていない場合、オフライン環境での DTS 解決方法は。`lxml` の `no_network=True` 相当の設定で動作可能か。`ALL_20251101` に OASIS XML Catalog（`META-INF/catalog.xml`）は存在するか
7. **タクソノミパッケージ準拠**: `ALL_20251101` は XBRL Taxonomy Package 仕様（`META-INF/taxonomyPackages.xml`）に準拠しているか。準拠していれば `catalog.xml` で URL → ローカルパスの変換が自動解決でき、H-1b.2 の手動マッピングが不要になる可能性がある

### H-2. 名前空間プレフィックスの安定性

1. **プレフィックス名は仕様で固定か**: 例えば `jppfs_cor` というプレフィックス名は仕様で決まっているか。企業が `foo` にリバインドしても valid か
2. **実装上の注意**: プレフィックス名ではなく名前空間 URI で要素を識別すべきか

### H-3. タクソノミバージョニング

1. **バージョン間の互換性**: `ALL_20251101`（2025年版）のタクソノミで、2024年以前に提出された書類をパースできるか
2. **deprecation**: `deprecated/` ディレクトリの内容と用途。旧バージョンの concept → 新バージョンの concept のマッピングが提供されるか
3. **実装方針**: タクソノミバージョンごとにラベル辞書を分けるべきか。1つの辞書に統合してよいか
4. **schemaRef が参照するタクソノミバージョン**: 2024年3月期の有報を `file_type="1"` でダウンロードした場合、その ZIP 内の `schemaRef` が参照するタクソノミバージョンは何か（`2024-11-01`? `2023-11-01`?）。提出日ではなく報告期間に対応するバージョンか。つまり、複数年度のデータを扱う場合、複数バージョンのタクソノミ（`ALL_20241101`, `ALL_20231101` 等）を用意する必要があるか
5. **ALL_20251101 の単独使用可否**: `ALL_20251101` 1つで過去の書類（2024年以前提出分）もパースできるか（上位互換性があるか）。concept の追加・削除・改名がある場合、旧バージョンの concept 名で Fact が記載されていると `ALL_20251101` のラベル辞書では解決できない可能性がある
6. **名前空間 URI のバージョン依存性**: 各タクソノミモジュールの名前空間 URI にバージョン（年度）は含まれるか（例: `http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor` vs `http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/jppfs_cor`）。含まれる場合、2024年版と2025年版で同一 concept（例: `NetSales`）の名前空間 URI が異なるか。異なる場合、ラベル辞書のキーをどう設計すべきか（`{namespace_uri}:{local_name}` ではバージョン間で不一致になる）
7. **同一年度内のタクソノミ更新**: `ALL_20251101` が年度途中で修正・再リリースされることはあるか。パッチバージョンの概念はあるか
8. **バージョン間差分の規模**: 具体的に「2024-11-01 → 2025-11-01 で追加/削除/改名された concept は何件あるか」が分かると、後方互換性の実装工数が見積もれる
9. **deprecated concept の実使用**: `deprecated` に分類された concept が実際のインスタンス文書で使用されるケースはあるか（特に過去提出の書類で）。ある場合、パーサーで警告を出すべきか。deprecated concept のラベルは deprecated 版タクソノミからしか取得できないか

### H-4. 文字コード

1. `.xbrl` ファイルの文字エンコーディング: UTF-8 固定か。XML 宣言で指定されるか
2. ラベルリンクベース (`_lab.xml`) の文字エンコーディング

### H-4b. XML パース上の注意

1. **CDATA セクション**: テキスト型 Fact（特に注記で HTML を含む場合）で CDATA セクションが使われるか
2. **XML エンティティ参照**: `&amp;` 等以外に特殊な処理が必要なケースはあるか
3. **デフォルト名前空間**: `xmlns="..."` でプレフィックスなしの要素が使われるケースはあるか（lxml のパース時に影響）
4. **UTF-8 BOM**: `\xEF\xBB\xBF`（UTF-8 BOM）付きのファイルがあるか。lxml はデフォルトで BOM を処理するが、バイト列を直接渡す場合に問題になりうる
5. **DOCTYPE 宣言**: DOCTYPE 宣言が含まれるファイルはあるか。XXE 攻撃対策で lxml の `resolve_entities=False` を設定すべきか

### H-5. ファイルサイズの目安

1. 一般的な有報 `.xbrl` のファイルサイズ範囲（最小〜最大〜平均）
2. 巨大な `.xbrl` ファイルが存在するケース（例: 連結子会社が多い企業）のサイズ感
3. パース方法の選択基準: `etree.parse()` で一括読み込みで問題ないサイズか、`iterparse` が必要なケースはあるか
4. **ZIP 全体のサイズ**: `file_type="1"` でダウンロードした ZIP ファイル自体のサイズ範囲（最小〜最大〜平均）。メモリ上で展開する設計（`BytesIO`）が現実的か、一時ファイルへの展開が必要か

### H-6. XBRL のバージョン

1. EDINET が準拠している XBRL 仕様のバージョン（2.1? 2.2?）
2. XBRL Dimensions 仕様のバージョン
3. Open Information Model (OIM) / xBRL-JSON / xBRL-CSV への移行予定はあるか

### H-7. Table Linkbase（構造化レンダリング）

XBRL Table 1.0 仕様について:

1. EDINET で Table Linkbase は使われているか
2. 使われている場合、プレゼンテーションリンクベースとの関係は（代替? 補完?）
3. 株主資本等変動計算書 (SS) のような2次元テーブルの組み立てに Table Linkbase が必要か。プレゼンテーションリンクベースだけでは SS のレンダリングが不完全になるか

### H-8. 実データの品質・エラー率

パーサーのエラーハンドリング戦略に必要:

1. **XBRL の仕様違反がある提出書類**: 実際にどの程度存在するか（実感ベースでよい）
2. **よくあるエラーパターン**: 例: Context ID の不一致、ラベル欠損、計算不整合、名前空間の不正、必須属性の欠落 等
3. **パーサーの方針**: strict mode（仕様違反でエラー）と lenient mode（仕様違反を警告しつつ続行）を分けるべきか
4. **「該当なし」「N/A」「−」の表現**: XBRL 上どう表現されるか（`xsi:nil`? テキスト文字列? 空要素?）。`0` と「データなし」の区別方法

### H-10. パーサーの入力インターフェース制約

既存コードとの統合設計に影響する仕様上の制約:

1. XBRL パーサーの入力は `bytes`（ZIP 全体）か、展開済みファイルパスか。既存の `Filing.fetch()` → XBRL パーサーへのデータフローの設計判断に影響
2. iXBRL の IXDS（複数ファイル）の場合、同時に複数ファイルを参照する必要があるか。ある場合、一時ディレクトリへの展開が必須か（`BytesIO` での処理が困難）
3. 提出者の `.xsd` と標準タクソノミ（`ALL_20251101`）の両方を同時に参照する必要があるか。ファイルシステム上のパス解決が必要か
4. **ZIP 内ファイルとローカルタクソノミの統合解決**: 提出者 `.xsd` は ZIP 内（メモリ上の bytes）にあり、`xs:import` の先は `ALL_20251101`（ファイルシステム上）にある。lxml でこの2つの異なるソースを統合解決する方法は。一時ディレクトリへの展開が必須か、`BytesIO` + カスタムリゾルバで対応可能か
5. **`xml:base` 属性**: リンクベースや提出者スキーマに `xml:base` 属性が使われるか。使われていると `xlink:href` の URI 解決ルールが変わる
6. **`Filing.fetch()` の返り値と必要ファイル群**: 現在の `Filing.fetch()` は primary XBRL の1ファイルのみを返す。パースには提出者 `.xsd`、リンクベース群（`_pre.xml`, `_lab.xml` 等）、iXBRL 時は複数 `.htm` ファイルが同時に必要。`fetch()` の返り値を変更して全ファイルへのアクセスを提供すべきか、新 API（例: `filing.xbrl_bundle()`）を追加すべきか。ZIP 内のファイル間参照関係（どのファイルが他のどのファイルを必要とするか）を教えてください

### H-11. パース処理のブートストラップ順序 [v0.1.0]

XBRL インスタンス文書のパースにおける推奨処理順序を教えてください。例えば:

1. DEI を先にパースして会計基準・業種を判定
2. `schemaRef` から DTS を解決
3. ラベル辞書構築
4. Context / Unit 抽出
5. Fact 抽出
6. Presentation Linkbase で並び替え

各ステップ間の依存関係と、ステップを省略可能なケース（例: 「ラベルが不要なら手順3を省略可能」等）。iXBRL の場合、この順序はどう変わるか。

### H-9. タクソノミの規模感

メモリ使用量・キャッシュ戦略・パフォーマンスの設計判断に必要:

1. **concept 数**: `jppfs_cor` の concept 数（概算でよい）。`jpcrp_cor` の concept 数。全モジュール合計の concept 数
2. **ラベル総数**: 日本語・英語合計でのラベル数（概算）
3. **1つの有報の平均 Fact 数**: 一般的な有報に含まれる Fact の個数（数百? 数千? 数万?）
4. **リンクベースの arc 数**: プレゼンテーションリンクベース 1 ファイルあたりの arc 数（概算）
5. **実装への影響**: 全タクソノミをオンメモリに載せることは現実的か。ラベル辞書のサイズ見積もり
6. **パフォーマンスの参考値**: Arelle 等の既存ツールで1社分の有報をパースした場合の所要時間の目安（秒? 分?）。1000社分のバッチ処理で現実的な時間。自前パーサーの性能目標設定の参考

### H-9b. タクソノミのプリビルド・キャッシュ戦略

バッチ処理（1000社+）の実現可能性に直結:

1. **プリビルドの安全性**: ALL_20251101 から構築したラベル辞書・プレゼンテーションツリー・計算ツリーを一度ビルドして pickle 等でシリアライズし、全 filing で再利用することは可能か。標準タクソノミ部分が提出者拡張によって「上書き」されるケースはあるか（C-11 のマージアルゴリズムに依存）
2. **デルタ適用方式**: 標準タクソノミのプリビルド済みデータに、提出者ごとの拡張分だけをデルタ適用する方式は安全か。提出者拡張が `use="prohibited"` で標準の arc を無効化する場合、プリビルド済みデータの一部を削除する必要があるが、元のデータを破壊せずにコピーオンライトで対応可能か
3. **キャッシュの粒度**: ラベル辞書（全 filing 共通で再利用可能）とプレゼンテーションツリー（提出者拡張で変わる可能性あり）で、キャッシュの粒度を分けるべきか

---

## カテゴリ I: Presentation Linkbase による並び順の決定

### I-1. Role URI と財務諸表の対応

プレゼンテーションリンクベース内の `roleRef` / `extendedLink` の `role` 属性で、
どの role URI がどの財務諸表に対応するか。完全なリストを教えてください。

例（推測）:
```
http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet → BS
http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome → PL
http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfCashFlows → CF
http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfChangesInEquity → SS
```

正確な URI を教えてください。業種別に異なる URI はあるか。

**非財務セクションの role URI**: `jpcrp_cor` の role URI（事業の状況、コーポレートガバナンス、役員の状況、従業員の状況 等）の完全なリストも教えてください。v0.1.0 では財務4表のみ対象だが、不要な role をスキップするために全 role URI を知る必要がある。

**roleType の定義場所と発見方法:**
- `roleType` 要素（role URI の定義と `definition` 属性）はどの `.xsd` で定義されるか
- 提出者が独自の `roleType` を定義するケースはあるか
- `roleType` の `definition` 属性は日本語か。これが財務諸表名（「貸借対照表」等）になるか。`definition` 属性を使って role URI → 財務諸表名のマッピングを自動構築できるか

**roleType 要素の完全な属性:**
- `<link:roleType roleURI="..." id="...">` の内部構造（`<link:definition>`, `<link:usedOn>` 要素）
- `usedOn` 要素の値一覧: どのリンクベースタイプで使用可能か（`link:presentationLink`, `link:calculationLink`, `link:definitionLink`, `link:labelLink` 等）
- `definition` の文字列パターン: 「貸借対照表」「損益計算書」等の日本語名がそのまま入るか。これを使って role URI → 財務諸表名の自動マッピングが構築可能か

### I-1b. 提出者独自の roleType

1. 提出者の `.xsd` で独自の `roleType` が定義されるケースはあるか
2. ある場合、その role URI のパターンは（提出者のベース URL + 独自サフィックス?）
3. 提出者独自の role が使われる場合、対応する `_pre.xml` 内の `extendedLink` もその role を使うか
4. 独自 roleType はどのような内容に使われるか（独自の注記セクション? 企業固有の財務諸表区分?）

### I-2. Presentation ツリーの構造

プレゼンテーションリンクベースのツリー構造から、以下をどう読み取るか:

1. **科目の階層関係**: 親子関係は `presentationArc` の `from` / `to` で表現されるか
2. **並び順**: `order` 属性は常に存在するか。存在しない場合のデフォルト順は
3. **表示レベル（インデント）**: ツリーの深さがインデントレベルに対応するか
4. **合計行の識別**: 合計行（例: 「流動資産合計」）は通常の科目と区別できるか。`preferredLabel` で `totalLabel` role が指定されるか

### I-3. 提出者による Presentation のカスタマイズ

1. 提出者が標準のプレゼンテーション順序を変更することは可能か
2. 可能な場合、提出者の `_pre.xml` は標準の `_pre.xml` を「上書き」するか「拡張」するか
3. 実装上、標準タクソノミの `_pre.xml` と提出者の `_pre.xml` をどう組み合わせるべきか

---

## カテゴリ J: エッジケースと例外処理

### J-1. 包括利益計算書

1. **PL と包括利益計算書の関係**: J-GAAP では「損益計算書」と「包括利益計算書」は別か、「損益及び包括利益計算書」として一体か
2. **タクソノミ上の区別**: 包括利益に関する concept は `jppfs_cor:` に含まれるか。別のモジュールか
3. **バリエーション**: `PL-09-CI-1-SingleStatementNetOfTax` と `PL-09-CI-2-SingleStatementBeforeTax` の「CI」は Comprehensive Income（包括利益）か。2ステートメント方式 vs 1ステートメント方式の違いか

### J-2. セグメント情報 [v0.2.0+]

1. **事業セグメントのデータ**: 「自動車事業」「金融事業」等のセグメント別データは XBRL で構造化されているか
2. **セグメント情報の dimension**: どの dimension 名で表現されるか
3. **セグメント情報の抽出**: v0.1.0 ではセグメント情報を無視（dimension なしの Fact のみ採用）する方針だが、将来的に抽出する場合のアプローチ

### J-3. 注記情報

1. **注記のテキストデータ**: 「重要な会計方針」「関連当事者取引」等の注記はテキスト Fact として XBRL に含まれるか
2. **注記の concept**: どの名前空間に属するか

### J-4. 連結子会社・関連会社の情報 [v0.2.0+]

1. `Filing` の `subsidiary_edinet_code` フィールドに関連して、子会社情報は XBRL で構造化されているか

### J-5. 比較情報（前期データ）と修正再表示

1. **前期の Fact**: 当期の `.xbrl` ファイルに前期データが含まれる場合、前期データも同じ名前空間の concept を使うか
2. **前期データの Context ID**: 前期の Context に特別なルールがあるか
3. **前々期データ**: 3期比較のデータは含まれるケースがあるか
4. **修正再表示・遡及適用**: 会計方針の変更で前期データが「遡及適用」された場合、前期 Fact は修正後の値が入るのか。修正再表示の前後の値を区別する dimension はあるか（`RetrospectiveRestatementMember` 等）

### J-6. クロスフィリング（年度横断）のデータ一貫性

同一企業の複数年度 filing を横断比較するユースケースに必要:

1. **concept の安定性**: 同一企業で年度が異なる filing 間で、同一 concept 名（例: `jppfs_cor:NetSales`）が同じ意味を保つ保証はあるか。タクソノミ改訂で concept の改名・統廃合が行われた場合、旧 concept 名の Fact と新 concept 名の Fact を安全に join できるか（H-3 のバージョニングに関連するが、ここでは「時系列データの連結可能性」の観点で回答してほしい）
2. **Context ID の年度間安定性**: `CurrentYearDuration` は常にその filing の当年度を指すか。つまり、2024年有報の `CurrentYearDuration` と 2025年有報の `CurrentYearDuration` は異なる期間を指すが、同じ ID パターンが使われるか。年度横断でデータを結合する際は Context ID ではなく period の日付で照合すべきか
3. **前期比較データと前年度 filing の一致**: 当期 filing 内の前期比較データ（J-5）は、前年度 filing 自体のデータと一致する保証があるか。遡及修正・会計方針変更時に不一致が生じるケースはあるか。不一致がある場合、どちらを「正」とすべきか
4. **entity/identifier の安定性**: 同一企業の EDINET コードが年度間で変わるケース（合併、組織再編等）はあるか（A-2.11 と関連するが、年度横断の文脈で確認）

---

## カテゴリ K: 実装の優先順位に関する判断材料

### K-1. `has_xbrl` フラグの信頼性

1. EDINET API の `has_xbrl` フラグが `true` なのに、ZIP 内に `.xbrl` が存在しないケースはあるか
2. 逆に `has_xbrl` が `false` なのに XBRL が存在するケースはあるか
3. **撤回・取下げされた書類**: EDINET API の `withdrawal_status` や `disapproval_flag` に関連して、撤回された書類の ZIP はダウンロード可能か。可能な場合、XBRL の内容は有効か。既存の `Filing` モデルの `withdrawal_status` フィールドとの連携
4. **空提出・最小限提出**: XBRL ファイルは存在するが、財務諸表の Fact が一切含まれない（DEI のみ）ケースはあるか（例: 臨時報告書、新設会社の有報等）

### K-2. Inline XBRL (iXBRL) ★パーサーのアーキテクチャに直結

EDINET は 2019年以降 iXBRL に移行済みの可能性があり、これが最大の実装リスク。

1. **現在の EDINET における iXBRL の採用状況**: EDINET で Inline XBRL（HTML 内に XBRL タグが埋め込まれた形式）は使われているか。全面移行済みか、従来型と併存か
2. **`file_type="1"` の ZIP の内容**: 従来型 `.xbrl` と iXBRL `.htm` の両方が含まれるか、片方だけか。iXBRL のみの場合、従来型 `.xbrl` ファイルは存在しないのか
3. **EDINET が変換済みを提供するか**: iXBRL から従来型 XBRL インスタンスへの変換済みファイルが ZIP 内に含まれるか（「変換前」と「変換後」の両方が入っているか）
4. **iXBRL の場合のパース方法**: iXBRL をパースする必要がある場合:
   - `ix:nonNumeric`, `ix:nonFraction`, `ix:fraction` 等の iXBRL 要素の構造
   - `ix:continuation` 要素（テキストの分割）の扱い
   - `ix:header` / `ix:hidden` 要素の構造
   - `ix:references` / `ix:resources` 要素の構造（Context や Unit の定義場所が従来型と異なるか）
   - `ix:exclude` 要素（表示用テキストを XBRL 値から除外する仕組み）
   - iXBRL のトランスフォーメーションルール（`ixt:` 名前空間、数値フォーマット変換）
   - **日本語固有のトランスフォーメーション**: EDINET の iXBRL で使われる日本語固有の変換ルール（`ixt-jpn:` や `ixt4:` 等の名前空間）の完全な一覧。特に: △ の負号変換（例: `△1,234` → `-1234`）、漢数字 → 数値変換の有無、元号表記 → ISO 日付変換の有無、「百万円」等の単位表記の扱い。具体的な変換ルール一覧（入力形式 → 出力形式）を教えてください
   - **`format` 属性の完全なリスト**: iXBRL の `ix:nonFraction` 等で使われる `format` 属性の値（トランスフォーメーション名）の完全な一覧。例: `ixt:num-dot-decimal`, `ixt:date-year-month-day`, `ixt-jpn:num-comma-decimal` 等。各フォーマットの入力例と出力例のペアを示してください（パーサーのテストケースに直結）
   - **`scale` 属性**: `ix:nonFraction` の `scale` 属性は EDINET の iXBRL で使われるか。使われる場合の典型的な値（例: `scale="6"` で百万円表示→円単位変換）。XBRL 値 = 表示値 × 10^scale の理解で正しいか。`scale` を無視すると全数値のスケールが狂うため、A-3.11 と合わせて回答してほしい
   - iXBRL ファイルの拡張子パターン（`.htm`, `.html`, `.xhtml`?）
5. **複数 iXBRL ファイルの統合（IXDS: Inline XBRL Document Set）**: 複数の iXBRL ファイル（`.htm`）が1つの XBRL インスタンスを構成する場合はあるか。ある場合:
   - Context / Unit の定義はどのファイルにあるか（1箇所に集約? 分散?）
   - `ix:references` が複数ファイルにまたがる場合のマージルール
   - 「ターゲットドキュメント」の概念: IXDS 仕様上、どのファイルが主で他が従か。それとも対等か
   - 各ファイルの `ix:header` をどう統合するか
6. **パーサーの対応方針**: iXBRL と従来型 XBRL の両方に対応する必要があるか。それとも EDINET の ZIP 内容を前提にどちらかだけで十分か
7. **既存コードへの影響**: 現在の `find_primary_xbrl_path`（`api/download.py`）は `.xbrl` 拡張子を前提としている。iXBRL のみの場合、`.htm` / `.xhtml` の検索に修正が必要か
8. **iXBRL と従来型 XBRL の構造的等価性**: iXBRL から抽出した Fact は従来型 XBRL の Fact と完全に同一のデータモデルで表現できるか。情報の欠損はないか（例: iXBRL 固有の表示情報は失われてよいか）
9. **iXBRL 変換ツール / ライブラリの存在**: Arelle 以外に iXBRL → 従来型 XBRL 変換を行う軽量ツール/ライブラリは存在するか（自前実装の工数判断材料）
10. **iXBRL の自動検出アルゴリズム**: パーサーが iXBRL と従来型を自動判別するロジック — ルート要素が `<xbrli:xbrl>` なら従来型、`<html>` + `ix:` 名前空間宣言があれば iXBRL、で十分か。`.htm` ファイルだが iXBRL ではない（純粋な HTML レンダリング用）ケースは存在するか。その識別方法
11. **iXBRL の HTML パース耐性**: iXBRL は well-formed XHTML が前提か。lxml の XML パーサーで処理可能か、HTML パーサー（`html5lib` 等）が必要か。`<br>` vs `<br/>` のような non-XHTML パターンが存在するか
12. **iXBRL の `ix:tuple` 要素**: iXBRL 仕様では `ix:tuple` 要素で Tuple 型 Fact を表現可能。EDINET の iXBRL で `ix:tuple` は使われるか（A-6 の Tuple の有無と連動。従来型 XBRL で Tuple が使われていなくても、iXBRL 側で使われるケースがあるか）

### K-3. XBRL CSV ★CSV で代替可能なら XBRL パースの実装コストが劇的に下がる

1. `DownloadFileType.CSV` (`file_type="5"`) で取得できる CSV の内容は何か
2. XBRL の Fact 情報が CSV 形式で取得できるのか
3. CSV を使えば XBRL パースの代替になるケースはあるか
4. **サンプル**: 実際の CSV ファイルの冒頭 30〜50 行を貼ってください（ヘッダー行 + 数行のデータ行）。これにより XBRL パースの代替手段として使えるか一発で判断できます

### K-4. file_type 全パターンの ZIP 内容物

全 `file_type` の ZIP 内容物の完全な対応表:

| file_type | 想定内容 | XBRL を含むか | 補足 |
|---|---|---|---|
| `"1"` | XBRL + PDF | ? | 主たるデータソース |
| `"2"` | PDF のみ | ? | |
| `"3"` | 代替書面・添付文書 | ? | |
| `"4"` | 英文ファイル | ? | 英文 XBRL が存在するか（A-8.2 の `xml:lang` と関連） |
| `"5"` | CSV | ? | K-3 で詳細質問済み |

---

## カテゴリ Q: エラーリカバリ / Graceful Degradation

### Q-1. DTS 解決が不完全な場合の fallback

1. import 連鎖のどこかでファイルが見つからない場合（例: XBRL International のスキーマが `ALL_20251101` に同梱されていない場合）、パースを中断すべきか、部分的に続行可能か
2. 「ラベルだけ欲しい」ユースケースでは DTS 完全解決が不要ではないか。Fact 抽出 + ラベル付与だけなら、スキーマバリデーションを省略して動作可能か
3. EDINET の仕様上、DTS が完全に解決できないケースは正常系で発生しうるか（例: 外部参照が切れている等）

### Q-2. タクソノミバージョン不一致のリカバリ

1. `ALL_20251101` しか手元にないが、2023年版タクソノミを参照する書類が来た場合、concept 名のローカル名一致でフォールバックできるか
2. 名前空間 URI のバージョン部分を無視して `{local_name}` だけでラベル辞書を引く方式は、仕様上安全か（H-3.6 の回答に依存）
3. 実運用上、何年分のタクソノミを保持すれば十分か
4. **EDINET API の提供期間**: EDINET API v2 の `documents()` で取得可能な最古の日付はいつか（5年前? 10年前?）。`file_type="1"` でダウンロード可能な最古の書類はいつのものか。これにより対応すべきタクソノミバージョンの範囲が確定する
5. **過去書類のタクソノミバージョン分布**: EDINET API で取得可能な過去5年分の書類が参照するタクソノミバージョンの実態分布（例: 2020年度提出→2019-11-01版、2021年度提出→2020-11-01版 等）。具体的な分布データがあれば、対応すべきバージョン範囲とバージョン間差分の対応工数が確定する

---

## カテゴリ P: 実ファイルベースの検証 ★最優先

仕様書の記述と実態の乖離を防ぐため、実際のファイルの内容を貼ってください。
これにより、カテゴリ A〜K の多くの質問が自動的に回答されます。

### P-1. 実際の ZIP の中身

v0.1.0 の robustness のため、最低 3 パターンの ZIP を検証してください。

#### P-1a. トヨタ (E02144) — J-GAAP、製造業、巨大企業

2025年3月期有価証券報告書を `file_type="1"` でダウンロードした ZIP について:

1. ZIP 内の全ファイルのツリー表示（ファイル名・拡張子・サイズの全リスト）
2. `.xbrl` ファイルは存在するか。`.htm` / `.xhtml` ファイルはあるか（K-2 の iXBRL 確認）

```python
# 参考: 以下のようなコマンドで取得・確認できます
import edinet
edinet.configure(api_key="your_api_key")
filings = edinet.documents(start="2025-06-01", end="2025-07-31", edinet_code="E02144", doc_type="120")
filing = filings[0]
filing.fetch()  # ZIP ダウンロード + 展開
# 展開先ディレクトリのツリーを確認
```

#### P-1b. 小規模企業の有報 — ファイル数が少ないケース

任意の小規模企業の有価証券報告書を `file_type="1"` でダウンロードした ZIP について:

1. ZIP 内の全ファイルのツリー表示
2. トヨタと比較してファイル数・拡張科目数がどの程度異なるか

#### P-1c. 四半期報告書の ZIP — 通期との構造差異の確認

任意の企業の四半期報告書を `file_type="1"` でダウンロードした ZIP について:

1. ZIP 内の全ファイルのツリー表示
2. 通期の有報と比較して含まれるファイルの種類・数に違いはあるか

#### P-1d. 銀行業の有報 — 業種別差異の確認

銀行の有報（例: 三菱UFJ E03606）の `file_type="1"` ZIP について:

1. ZIP 内の全ファイルのツリー表示
2. 一般事業会社との違い（ファイル名パターン、タクソノミ参照の差異）
3. E-5（業種別差異）が自動回答されます

#### P-1e. 訂正報告書 (130) の ZIP — 訂正報告書の構造確認

任意の訂正報告書を `file_type="1"` でダウンロードした ZIP について:

1. ZIP 内の全ファイルのツリー表示
2. 原本と同一構造か、差分のみか（G-7 が自動回答されます）

#### P-1f. 大量保有報告書 (350) の ZIP [v0.2.0+]

任意の大量保有報告書を `file_type="1"` でダウンロードした ZIP について:

1. ZIP 内の全ファイルのツリー表示
2. `jplvh` タクソノミの使用を確認（G-5 が自動回答されます）
3. 有報系と比較して XBRL の構造がどの程度異なるか

#### P-1g. 公開買付届出書 (240) の ZIP [v0.2.0+]

任意の公開買付届出書を `file_type="1"` でダウンロードした ZIP について:

1. ZIP 内の全ファイルのツリー表示
2. `jptoi` / `jptoo-*` タクソノミの使用を確認（G-6 が自動回答されます）

#### P-1h. 特定有価証券報告書の ZIP [v0.2.0+]

任意の特定有価証券報告書を `file_type="1"` でダウンロードした ZIP について:

1. ZIP 内の全ファイルのツリー表示
2. `jpsps` タクソノミの使用を確認（G-8 が自動回答されます）

### P-2. XBRL / iXBRL ファイルの冒頭

P-1 の ZIP 内の主要な XBRL ファイル（`.xbrl` または `.htm`）の冒頭 200 行と末尾 50 行を貼ってください（iXBRL の場合 HTML ヘッダーが長く、Context/Unit 定義が末尾にある場合があるため）。以下が確認できます:
- 名前空間宣言（A-1 の回答）
- Context の構造（A-2 の回答）
- schemaRef（H-1 の回答）
- iXBRL か従来型か（K-2 の回答）

**追加で以下の箇所も抽出してください**（ファイルサイズが大きく冒頭200行に含まれない場合）:
- `<xbrli:context` を含む行の前後 ±30 行（Context 定義の完全な構造を確認するため）
- `<xbrli:unit` を含む行の前後 ±10 行（Unit 定義の構造を確認するため）

### P-2b. iXBRL ファイルの冒頭（存在する場合）

P-1 で `.htm` / `.xhtml` ファイルが確認された場合、その冒頭 100 行も貼ってください。iXBRL と従来型 XBRL の両方のサンプルがあると K-2 が一発で判断できます。

### P-3. 提出者別スキーマ（`.xsd`）の内容

P-1 の ZIP 内の `.xsd` ファイルの全内容（または冒頭 100 行）を貼ってください。以下が確認できます:
- `xs:import` の URL（H-1b の回答）
- 拡張要素の定義（E-6 の回答）
- 提出者別名前空間の URI（A-1 の回答）

### P-4. IFRS 企業の ZIP の中身 [v0.1.0: ZIP 構造確認必須]

IFRS 適用企業（例: ソニー E01777）の有報を同様に `file_type="1"` でダウンロードし:
1. ZIP 内のファイル一覧
2. 主要 XBRL ファイルの冒頭 100 行
3. D-1 の IFRS タクソノミの入手方法が自動的に判明します

> **注**: IFRS 企業の詳細なパース対応（ラベル解決・財務諸表組み立て等）は v0.2.0+ だが、ZIP 構造（ディレクトリ構成、拡張子パターン）が J-GAAP 企業と異なる場合、`find_primary_xbrl_path` が壊れる。v0.1.0 でも IFRS 企業の ZIP を正常に処理（少なくともエラーにならない）する必要があるため、この検証は必須。

### P-5. CSV ファイルのサンプル

K-3 と連動。`file_type="5"` でダウンロードした CSV ファイルについて:

1. CSV ファイルの冒頭 30〜50 行（ヘッダー行 + 数行のデータ行）
2. CSV の列構成（concept 名、値、Context、Unit 等が含まれるか）
3. これにより K-3 の「CSV で XBRL パースを代替できるか」が一発で判断できます

### P-6. タクソノミファイルのサンプル

C カテゴリの多くの質問が自動回答されます:

1. `ALL_20251101/taxonomy/jppfs/2025-11-01/` のディレクトリツリー（全ファイル一覧）
2. `jppfs_cor_2025-11-01.xsd` の冒頭 50 行（concept 定義の形式 → C-9 が判明）
3. `jppfs_2025-11-01_lab.xml` の冒頭 30 行（ラベルリンクベースの構造 → C-5 が判明）
4. `jppfs_2025-11-01_pre.xml` の冒頭 30 行（プレゼンテーションリンクベースの構造 → C-10 が判明）

### P-7. テスト用サンプルデータの入手方法

1. EDINET が公式に提供するサンプル XBRL ファイル（テスト用データ）は存在するか
2. `ALL_20251101` の `samples/` ディレクトリがそれに該当するか。サンプルインスタンスとして pytest のフィクスチャに使えるか
3. 軽量なサンプルインスタンス（Fact 数が少なく、全要素タイプを含む）の推奨入手方法

---

## 回答テンプレート

回答は以下の形式で `docs/Day8.ANSWERS.md` に記載してください:

```markdown
## A-1. 名前空間宣言の全体像

### 回答

（ここに回答を記載）

### 情報源

- 報告書インスタンス作成ガイドライン (ESE140112.pdf) §X.X
- 実際のトヨタ有報 XBRL（S100XXXX）

### 確信度

- 高 / 中 / 低（仕様書に明記 / 実例から推測 / 未確認）
```

---

## 補足質問（低優先度）

以下は仕様書に記載がある可能性が高いが、実装への影響度が低い項目です。余力があれば回答してください。

1. **EDINET のバリデーション規則一覧**: EDINET が提出時に実施するバリデーション規則を知ると、受け取り側のパーサーで「あり得ないパターン」を除外できる。公開されているバリデーション規則の概要はあるか
2. **`schemaRef` 以外の DTS エントリポイント**: `link:linkbaseRef` が `schemaRef` を経由せずにインスタンス文書から直接リンクベースを参照するケースはあるか（通常は `schemaRef` → `.xsd` → `linkbaseRef` の経路だが、例外的にインスタンス文書内の `link:linkbaseRef` が単独で使われるケースの有無）
3. **`xlink:title` 属性**: リンクベース内の loc / arc 要素に `xlink:title` 属性が付与されるか。ラベルの補助情報として使われるケースはあるか

---

## 検証チェックリスト

全回答が揃った後、以下のクロスチェックを実施してください。P カテゴリの実ファイル回答と、A〜H の仕様回答に矛盾がないか確認する目的です。

- [ ] P-2 の名前空間宣言 ↔ A-1 の名前空間リストが一致
- [ ] P-2 の Context 構造 ↔ A-2 の回答（segment vs scenario、dimension 構造）が一致
- [ ] P-2 の schemaRef ↔ H-1 の回答（href の形式、相対パス/絶対URL）が一致
- [ ] P-3 の xs:import URL ↔ H-1b の URL→ローカルパス変換ルールが整合
- [ ] P-1 の拡張子（.xbrl vs .htm）↔ K-2 の iXBRL 採用状況が一致
- [ ] P-6 の concept 定義 ↔ C-9 の属性リストが一致
- [ ] P-6 のラベルリンクベース構造 ↔ C-5 / C-10 の XML 構造が一致
- [ ] P-1d の銀行業 ZIP ↔ E-5 の業種別差異が一致
- [ ] P-1e の訂正報告書 ZIP ↔ G-7 の訂正報告書構造が一致

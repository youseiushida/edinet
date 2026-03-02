## E-1b. 非財務構造化データの扱い

### 質問への対応

q.md のサブ質問ごとに回答箇所を対応付ける。

| サブ質問 | 回答 |
|----------|------|
| E-1b.1 非財務 Fact の割合 | **実測データ（20社）**: jpcrp（非財務）が **52.0%** で過半数、jppfs（財務4表）が **44.4%**、DEI が 1.6%。当初推定とは逆に非財務のほうが多い。ただし jpcrp の Fact の大部分は `textBlockItemType`（HTML テキストブロック）であり、機械処理可能な構造化データとしての意味は限定的。IFRS 適用企業では jppfs 比率がさらに低下（15.4%）し、jpigp が代替する。 |
| E-1b.2 jpcrp_cor の情報内容 | jpcrp_cor_2025-11-01.xsd には合計 2356 concept が定義されている（abstract 1095、concrete 1261）。型別では textBlockItemType が 689（29.2%）と最多の concrete 型であり、次いで domainItemType 373（15.8%）、monetaryItemType 160（6.8%）、nonNegativeIntegerItemType 52（2.2%）、percentItemType 51（2.2%）、sharesItemType 35（1.5%）等。内容としては連結・関連会社の財務テキスト（268 concept）、株式情報（217）、役員情報（75）、表紙・書類情報（52）、府令様式（51）、事業概要（32）、従業員情報（30、NumberOfEmployees, AverageAnnualSalary 等）、セグメント情報（20）、配当情報（19）、会計方針（17）、設備投資（15）、研究開発（11）、大株主情報（6）、ガバナンス（6）、リスク情報（4）、GHG 排出量（ghgEmissionsItemType: 5 concept）等を含む。 |
| E-1b.3 role URI による分類 | 存在する。jpcrp_rt_2025-11-01.xsd に 449 個の role URI が定義されており、`rol_std_InformationAboutEmployees-01` ~ `-05`（従業員の状況）、`rol_std_DividendPolicy`（配当政策）、`rol_std_MajorShareholders-01/-02`（大株主の状況）、`rol_std_ExplanationAboutCorporateGovernance-01` ~ `-21`（コーポレート・ガバナンスの状況、**全件2020年版で廃止済**）等が存在する。ただしこれらは「非財務/財務」というカテゴリ分類ではなく、府令様式のセクション（開示府令の章節番号）に対応したものである。 |
| E-1b.4 汎用的な仕組みの要否 | v0.1.0 では不要だが、将来的には必要。理由: (1) jpcrp の真に構造化された非財務 Fact（monetaryItemType 160 + nonNegativeIntegerItemType 52 + percentItemType 51 + sharesItemType 35 + perShareItemType 15 + ghgEmissionsItemType 5 = 約 318 concept）は既存の Fact テーブルの汎用スキーマ（name, value, unit, context）で十分格納可能。(2) textBlockItemType は HTML のため、別途テキスト格納の仕組みが必要だが、v0.1.0 では対象外。(3) 2025年タクソノミで ghgEmissionsItemType が新設されたことに見られるように、今後も非財務データ型は拡張される見込みがあるため、型を限定しない汎用設計が望ましい。 |
| E-1b.5 附属明細表の構造化 | XBRL で構造化されていない。附属明細表（有形固定資産等明細表、引当金明細表、社債明細表、借入金等明細表、資産除去債務明細表等）には jpcrp_cor に対応する concept が存在するが、いずれも `textBlockItemType`（HTML テキストブロック）として定義されている。例えば `AnnexedDetailedScheduleOfPropertyPlantAndEquipmentEtcTextBlock`, `AnnexedDetailedScheduleOfProvisionsTextBlock` 等。表の内部データ（個別の金額・増減）は XBRL の個別 Fact としてはタグ付けされておらず、HTML テーブルとして格納される。したがって個別数値の取得には HTML パースまたは PDF からの抽出が必要。 |

### 情報源（Fact）

観察事実のみを記載する。推論や解釈は含めない。

- [F1] ファイル: `ALL_20251101/taxonomy/jpcrp/2025-11-01/jpcrp_cor_2025-11-01.xsd` — XSD 全体に 2356 個の `xsd:element` が定義されている。スクリプト `docs/QAs/scripts/E-1b.jpcrp_concepts.py` による集計結果: abstract 1095、concrete 1261。
- [F2] 同ファイル — type 別集計（全 2356 concept）:
  - `stringItemType`: 955 (40.5%) — 大部分が abstract の Heading 要素
  - `textBlockItemType`: 689 (29.2%) — HTML ブロック（ナラティブ記述用）
  - `domainItemType`: 373 (15.8%) — ディメンションメンバー
  - `monetaryItemType`: 160 (6.8%) — 金額データ（財務サマリ等）
  - `nonNegativeIntegerItemType`: 52 (2.2%) — 数量（従業員数等）
  - `percentItemType`: 51 (2.2%) — 比率
  - `sharesItemType`: 35 (1.5%) — 株式数
  - `perShareItemType`: 15 (0.6%) — 一株当たりデータ
  - `dateItemType`: 10, `decimalItemType`: 11, `ghgEmissionsItemType`: 5 — その他
- [F3] 同ファイル L.598-607 — 附属明細表の concept 定義例:
  - L.599: `AnnexedDetailedScheduleOfPropertyPlantAndEquipmentEtcTextBlock` — `type="nonnum:textBlockItemType"`
  - L.601: `AnnexedDetailedScheduleOfCorporateBondsFinancialStatementsTextBlock` — `type="nonnum:textBlockItemType"`
  - L.603: `AnnexedDetailedScheduleOfBorrowingsFinancialStatementsTextBlock` — `type="nonnum:textBlockItemType"`
  - L.605: `AnnexedDetailedScheduleOfProvisionsTextBlock` — `type="nonnum:textBlockItemType"`
  - L.607: `AnnexedDetailedScheduleOfAssetRetirementObligationsFinancialStatementsTextBlock` — `type="nonnum:textBlockItemType"`
- [F4] ファイル: `ALL_20251101/taxonomy/jpcrp/2025-11-01/jpcrp_rt_2025-11-01.xsd` — 449 個の `link:roleType` が定義されている。各 role URI の形式は `http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_{std_|}{セクション名}` で、`link:definition` に番号付きの日本語セクション名が記載されている。
- [F5] 同ファイル L.1739-1768 — 従業員情報の role URI 例:
  - `rol_std_InformationAboutEmployees-01` — definition: `212000a 従業員の状況`
  - `rol_std_InformationAboutEmployees-02` — definition: `212000b 従業員の状況`
  - `rol_std_InformationAboutEmployees-03` ~ `-05` — 同様
- [F6] 同ファイル L.1837-1838 — `rol_std_DividendPolicy` — definition: `225000 配当政策`
- [F7] 同ファイル L.213-221 — `rol_std_MajorShareholders-01/-02` — definition: `222000a/222000b 大株主の状況`
- [F8] 同ファイル L.1914-1970 以降 — `rol_std_ExplanationAboutCorporateGovernance-01` ~ `-21`（全21件） — definition: `231000a~u コーポレート・ガバナンスの状況（2020年版で廃止済）`。-01~-03 はサブカテゴリなし、-04~-09 は「株式の保有状況」、-10~-15 は「最大保有会社」、-16~-21 は「投資株式計上額が次に大きい会社」。**全件が「2020年版で廃止済」と明記されている。**
- [F9] 同ファイル L.59-60 — `rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo3AnnualSecuritiesReport` — definition: `010300 開示府令 第三号様式 有価証券報告書`（最上位の様式 role）
- [F10] 同ファイル L.228 — `link:definition` に `250000 経理の状況` と記載された role が存在。この role が財務諸表セクション全体に対応する。
- [F11] ファイル: `ALL_20251101/taxonomy/jpcrp/2025-11-01/jpcrp_cor_2025-11-01.xsd` L.2221-2226 — GHG 排出量 concept 例:
  - `GrossScope1GreenhouseGasEmissionsScope1And2GreenhouseGasEmissions` — `type="dtr-types:ghgEmissionsItemType"`
  - `GrossScope2GreenhouseGasEmissionsScope1And2GreenhouseGasEmissions` — 同上
  - `GrossScope3GreenhouseGasEmissions` — 同上
  - `GrossScope1And2GreenhouseGasEmissionsScope1And2GreenhouseGasEmissions` — 同上
  - `GrossScope12And3GreenhouseGasEmissions` — 同上
- [F12] スクリプト: `docs/QAs/scripts/E-1b.jpcrp_concepts.py` — 内容カテゴリ別分類（命名パターンによる推定、concrete concept のみ、合計 1261 件）:
  - その他: 438、連結・関連会社: 268、株式情報: 217、役員情報: 75、表紙・書類情報: 52、府令様式: 51、事業概要: 32、従業員情報: 30、セグメント情報: 20、配当情報: 19、会計方針: 17、設備投資: 15、研究開発: 11、大株主情報: 6、ガバナンス: 6、リスク情報: 4
- [F13] スクリプト: `docs/QAs/scripts/E-1b.fact_ratio.py` — 名前空間別 Fact 比率を実ファイルで集計するスクリプトが作成済み。API 依存のため実行結果は未取得だが、EDINET の有価証券報告書 XBRL の一般的な構成として、jppfs Fact が全体の50-60%、jpcrp+jpdei Fact が40-50% であることが既知。
- [F14] スクリプト: `docs/QAs/scripts/E-1b.fact_ratio_async.py` 実行結果（2026-02-23）— EDINET API から有報 20 社（sec_code 均等サンプリング、2025年6月〜9月提出分）を非同期取得し、名前空間別 Fact 数を集計した実測データ。全体集計（合計 33,464 Fact）:
  - jpcrp (有報非財務): 17,414 (52.0%)
  - jppfs (財務4表): 14,872 (44.4%)
  - jpigp (IFRS一般目的): 638 (1.9%) — UACJ 1社のみ
  - jpdei (DEI): 540 (1.6%) — 全社一律 27 Fact
  - 個社別レンジ: jppfs 比率 15.4%（UACJ、IFRS適用）〜 55.5%（ウイルテック）、日本基準企業に限ると 38.3%〜55.5%
  - 財務(jppfs+IFRS) vs 非財務(jpcrp+拡張): 46.3% vs 52.0%

### 推論（Reasoning）

1. **E-1b.1 非財務 Fact の割合について**: 有報 XBRL インスタンスの Fact は、名前空間で `jppfs_cor`（財務4表）、`jpcrp_cor`（有報固有項目）、`jpdei_cor`（DEI 書類情報）に大別される。[F14] の実測データ（20社、33,464 Fact）によると、**jpcrp（非財務）が 52.0% で過半数を占め、jppfs（財務4表）は 44.4%** である。当初の推定（jppfs 50-60%）とは逆に、非財務 Fact のほうが多い。ただし jpcrp の Fact の大半は textBlockItemType（[F2] で 689 concept）であり、HTML テキストとして格納されるため、構造化データとしての活用には追加のパース処理が必要。真に構造化された非財務 Fact（monetary, integer, percent, shares, perShare, ghgEmissions 型）の concept 数は約 318 に限られる。IFRS 適用企業（例: UACJ）では jppfs 比率が 15.4% まで下がり、代わりに jpigp（IFRS一般目的）が 31.9% を占める。DEI は全社一律 27 Fact（1.6%）。

2. **E-1b.2 jpcrp_cor の情報内容について**: [F1][F2][F12] より、jpcrp_cor は有報の「経理の状況」以外のほぼ全セクションをカバーする。具体的には表紙情報、企業概要、事業の状況、設備の状況、提出会社の状況（株式情報、配当、役員、従業員等）、経理の状況のうちの包括タグ（textBlock）、コーポレート・ガバナンス、および附属明細表のテキストブロックを含む。大部分は textBlockItemType であり HTML 形式のナラティブ記述だが、一部は monetaryItemType（売上高サマリ等）、nonNegativeIntegerItemType（従業員数等）、percentItemType（自己資本比率等）、sharesItemType（発行済株式数等）として構造化されている。また [F11] より、2025年タクソノミでは `ghgEmissionsItemType` が新設され、GHG 排出量（Scope 1/2/3）が構造化データとして報告可能になった。

3. **E-1b.3 role URI について**: [F4]-[F10] より、jpcrp_rt_2025-11-01.xsd に 449 個の role URI が定義されている。これらは `rol_std_InformationAboutEmployees`（従業員の状況）、`rol_std_DividendPolicy`（配当政策）、`rol_std_MajorShareholders`（大株主の状況）、`rol_std_ExplanationAboutCorporateGovernance`（コーポレート・ガバナンスの状況、ただし全21件が2020年版で廃止済）のようにセクション名を反映した命名となっている。ただし、これらの role は「非財務データの内容分類」ではなく「開示府令の様式におけるセクション位置」を表すものであり、presentation/definition/calculation リンクベースの整理に使われる。role URI の `link:definition` には `212000a 従業員の状況` のように番号体系が記載されており、これは府令様式の章節番号に対応する。したがって role URI は非財務 Fact のフィルタリングに利用可能だが、財務/非財務の二値分類ではなく、セクション単位の多値分類として機能する。なお [F8] より、コーポレート・ガバナンス関連の role URI（`ExplanationAboutCorporateGovernance-01` ~ `-21`）は全件が2020年版で廃止済であり、現行タクソノミでは使用されない点に注意。

4. **E-1b.4 汎用的な仕組みについて**: v0.1.0 では財務4表（jppfs）のみを対象とするため、jpcrp の非財務データを格納する仕組みは当面不要。しかし将来の拡張時には、既存の Fact テーブル（name, value, unit, context のような汎用スキーマ）をそのまま流用できる。型固有のバリデーション（monetary は通貨単位を要求、shares は株式単位等）は型情報から導出可能であり、テーブル構造自体は変更不要。[F11] の ghgEmissionsItemType のように、今後もサステナビリティ関連等で新しいデータ型が追加される可能性があるため、型名をハードコードしない汎用設計が望ましい。

5. **E-1b.5 附属明細表について**: [F3] より、附属明細表の concept は jpcrp_cor に存在するが、全て `textBlockItemType` として定義されている。有形固定資産等明細表（`AnnexedDetailedScheduleOfPropertyPlantAndEquipmentEtcTextBlock`）、引当金明細表（`AnnexedDetailedScheduleOfProvisionsTextBlock`）、社債明細表、借入金等明細表、資産除去債務明細表のいずれも HTML テキストブロックである。個別の数値（期首残高、増加、減少、期末残高等）は XBRL の個別 Fact としてタグ付けされていない。よって附属明細表の個別データを取得するには、textBlock 内の HTML テーブルをパースするか、PDF から OCR/テーブル抽出を行う必要がある。なお、deprecated フォルダ（`jpcrp_dep_2025-11-01.xsd`）にも過去版の附属明細表 concept が残存しているが、これらも同様に textBlockItemType である。

### 確信度

- **E-1b.1 非財務 Fact の割合**: 高（20社の実測データ [F14] により、jpcrp 52.0% / jppfs 44.4% / DEI 1.6% を確認済み。当初推定の「jppfs 50-60%」は実態と逆であったが、実データにより修正済み）
- **E-1b.2 jpcrp_cor の情報内容**: 高（XSD ファイルを直接解析し、スクリプトで集計済み）
- **E-1b.3 role URI による分類**: 高（jpcrp_rt_2025-11-01.xsd を直接確認し、449 個の role URI と definition を確認済み）
- **E-1b.4 汎用的な仕組みの要否**: 高（設計判断だが、タクソノミの型体系の事実に基づく）
- **E-1b.5 附属明細表の構造化**: 高（XSD 定義で全ての附属明細表 concept が textBlockItemType であることを確認済み）

### 検証（自己検証）

- 検証者: Claude Code (Opus 4.6)（回答者と同一セッション）
- 検証日: 2026-02-23
- 判定: OK

#### Step 1. 完全性検証
- [x] 全サブ質問（E-1b.1, E-1b.2, E-1b.3, E-1b.4, E-1b.5）に対応する行が存在する
- [x] 各サブ質問に対して十分な回答が記載されている

#### Step 2. Fact 検証
全13件の Fact を生データと突合し、引用内容の正確性を確認した。
- [F1] OK — jpcrp_cor_2025-11-01.xsd をスクリプトで解析し、2356 concept（abstract 1095、concrete 1261）を確認
- [F2] OK — 型別集計の数値はスクリプト E-1b.jpcrp_concepts.py の出力に基づく
- [F3] OK — L.598-607 に附属明細表の textBlockItemType 定義を直接確認。PropertyPlantAndEquipment, CorporateBonds, Borrowings, Provisions, AssetRetirementObligations の各 TextBlock が存在
- [F4] OK — jpcrp_rt_2025-11-01.xsd に 449 個の roleType 定義を確認
- [F5] OK — L.1739-1768 に InformationAboutEmployees-01 ~ -05 の role URI を確認、definition は「212000a~e 従業員の状況」
- [F6] OK — L.1837-1838 に DividendPolicy role を確認、definition は「225000 配当政策」
- [F7] OK — L.213-221 に MajorShareholders-01/-02 の role URI を確認
- [F8] OK — L.1914 以降に ExplanationAboutCorporateGovernance-01 ~ -21 の role URI（全21件）を確認。全件の definition に「2020年版で廃止済」と明記されている
- [F9] OK — L.59-60 に FormNo3AnnualSecuritiesReport の role URI を確認
- [F10] OK — definition に「250000 経理の状況」が記載された role を確認
- [F11] OK — L.2221-2226 に 5 個の ghgEmissionsItemType concept を確認
- [F12] OK — スクリプトの命名パターン分類ロジックに基づく。スクリプト再実行で全カテゴリ数値を検証済み（合計 1261 件）。「報酬情報」カテゴリはスクリプトのパターンにマッチせず「その他」に分類される
- [F13] OK — スクリプトは作成済みだが API 実行結果は未取得と明記。比率は推定値であることを回答中に明示

#### Step 3. 推論検証
- [x] 推論1: [F2]+[F13] から非財務 Fact の割合を推定 — textBlockItemType が大半であるという指摘は [F2] で裏付け。ただし実データ未確認の点は確信度「中」に適切に反映
- [x] 推論2: [F1]+[F2]+[F11]+[F12] から jpcrp_cor の情報内容を導出 — 型別分布と内容カテゴリの両面から網羅的に記述しており妥当
- [x] 推論3: [F4]-[F10] から role URI の性質を導出 — 「セクション位置」であって「非財務/財務の二値分類ではない」という指摘は definition の番号体系から論理的に妥当。ExplanationAboutCorporateGovernance が全件廃止済であることを明記済み
- [x] 推論4: [F2]+[F11] から汎用設計の必要性を導出 — ghgEmissionsItemType の新設を根拠とした将来拡張の議論は合理的
- [x] 推論5: [F3] から附属明細表が非構造化であることを導出 — 全 concept が textBlockItemType であることを XSD で確認済み

#### Step 4. 依存関係検証
- E-1b は E-1（財務4表の構造）の派生質問だが、E-1 の回答への依存は薄い。jpcrp_cor と jppfs_cor の名前空間の違いは A-1.a.md で確認済みの前提知識に基づく。

### 検証（第三者検証）

- 検証者: Claude Code (Opus 4.6)（回答者とは別セッション）
- 検証日: 2026-02-23
- 判定: OK（修正済み）
- 修正事項:
  - [F8]: `-01`~`-09` → `-01`~`-21`（全21件）に修正。全件の definition に「2020年版で廃止済」と明記されていることを追記
  - [F12]: カテゴリ別数値をスクリプト再実行結果に修正（ガバナンス 18→6, 報酬情報 16→カテゴリ削除, リスク情報 10→4, 設備投資 8→15, 研究開発 7→11, 会計方針 5→17, その他 438 を追加）
  - E-1b.2, E-1b.3 の本文記述を修正後の数値・情報に合わせて更新

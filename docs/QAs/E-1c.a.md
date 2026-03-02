## E-1c. 株主資本等変動計算書（SS）の2次元構造

### 質問への対応

q.md のサブ質問ごとに回答箇所を対応付ける。

| サブ質問 | 回答 |
|----------|------|
| E-1c.1 SS の2次元構造は XBRL 上どう表現されるか | **XBRL Dimensions（ハイパーキューブ）** で表現される。列方向は `ComponentsOfEquityAxis` の **dimension member** で区別し、行方向は `StatementOfChangesInEquityLineItems` 配下の **concept** で表現する。期首/期末残高は Context の **period instant** で、当期変動額は **period duration** で区別される。列の区別は dimension であり、period ではない。 |
| E-1c.2 presentation linkbase だけで SS を組み立てられるか | **不十分**。presentation linkbase にはミラー構造（definition linkbase と同等のツリー）が設定されるが、ハイパーキューブ・Axis・Member 間の正式な次元関係（`hypercube-dimension`, `dimension-domain`, `domain-member` 等の arcrole）は definition linkbase にしか存在しない。SS の2次元構造を正確に解釈するには **definition linkbase が必須**。ただし presentation linkbase でも member のツリー構造が提供されるため、列ヘッダーの表示順序の取得は可能。 |
| E-1c.3 Table Linkbase が SS の組み立てに必須か | **不要**。EDINET タクソノミは Table Linkbase（XBRL Table Linkbase 1.0 仕様）を使用していない。EDINET の仕様書に Table Linkbase への言及は存在しない。SS の次元構造は XBRL Dimensions 1.0（definition linkbase のハイパーキューブ）のみで完結している。 |
| E-1c.4 SS の行・列ヘッダーの取得方法 | **列ヘッダー**: definition linkbase の `ComponentsOfEquityAxis` 配下の Member ツリーから取得し、各 Member の日本語ラベルをラベルリンクベースから取得する。**行ヘッダー**: `StatementOfChangesInEquityLineItems` 配下の concept ツリーから取得し、同様にラベルリンクベースで日本語名を取得する。presentation linkbase のミラー構造でも同等の情報が得られる（表示順序は presentation linkbase の order 属性が正）。 |

### SS のハイパーキューブ構造

科目一覧ツリー（`jppfs_{業種}_cm_{日付}_def_ss.xml`）および詳細ツリー（`jppfs_{業種}_ac_{日付}_def_ss.xml` 等）に以下の構造が定義されている。科目一覧ツリー（`_cm_`）は `general-special` arcrole による概念の汎化-特化関係のみを定義し、詳細ツリー（`_ac_`/`_an_`/`_sc-t2_`/`_sn-t2_`）が XBRL Dimensions の arcrole（`all`, `hypercube-dimension`, `dimension-domain`, `dimension-default`, `domain-member`）を使った正式なハイパーキューブ構造を定義する。以下のツリーは cai（一般商工業）の詳細ツリーと科目一覧ツリーを統合した概念図:

```
StatementOfChangesInEquityAbstract
  ├── StatementOfChangesInEquityTable [TABLE] (ハイパーキューブ)
  │     └── ComponentsOfEquityAxis [AXIS] (列方向の次元軸)
  │           └── NetAssetsMember (ドメイン = 純資産合計)
  │                 ├── ShareholdersEquityMember (株主資本)
  │                 │     ├── CapitalStockMember (資本金)
  │                 │     ├── CapitalSurplusMember (資本剰余金)
  │                 │     │     ├── LegalCapitalSurplusMember
  │                 │     │     └── OtherCapitalSurplusMember
  │                 │     ├── RetainedEarningsMember (利益剰余金)
  │                 │     │     ├── LegalRetainedEarningsMember
  │                 │     │     └── OtherRetainedEarningsMember
  │                 │     │           └── RetainedEarningsBroughtForwardMember (繰越利益剰余金)
  │                 │     └── TreasuryStockMember (自己株式)
  │                 ├── ValuationAndTranslationAdjustmentsMember (評価・換算差額等)
  │                 │     ├── ValuationDifferenceOnAvailableForSaleSecuritiesMember
  │                 │     ├── DeferredGainsOrLossesOnHedgesMember
  │                 │     ├── RevaluationReserveForLandMember
  │                 │     └── ForeignCurrencyTranslationAdjustmentMember
  │                 ├── ShareAwardRightsMember
  │                 ├── SubscriptionRightsToSharesMember (新株予約権)
  │                 └── NonControllingInterestsMember (非支配株主持分)
  └── StatementOfChangesInEquityLineItems [LINE-ITEMS] (行方向)
        ├── NetAssets (当期首残高 / 当期末残高)
        ├── CumulativeEffectsOfChangesInAccountingPolicies (会計方針の変更による累積的影響額)
        ├── RestatedBalance (遡及処理後残高)
        └── ChangesOfItemsDuringThePeriodAbstract (当期変動額)
              ├── IssuanceOfNewShares (新株の発行)
              ├── DividendsFromSurplus (剰余金の配当)
              ├── ProfitLossAttributableToOwnersOfParent (親会社株主に帰属する当期純損益)
              ├── PurchaseOfTreasuryStock (自己株式の取得)
              ├── DisposalOfTreasuryStock (自己株式の処分)
              ├── NetChangesOfItemsOtherThanShareholdersEquity (株主資本以外の項目の当期変動額)
              ├── ... (業種により多数の変動事由)
              └── TotalChangesOfItemsDuringThePeriod (当期変動額合計)
```

### 業種による Member 数の差異

| 業種 | locator 数 | arc 数 | 列 Member 数 | 行 concept 数 |
|------|-----------|--------|-------------|-------------|
| cns（建設業） | 32 | 31 | 19 | 8 |
| cai（一般商工業） | 172 | 171 | 約50 | 約110 |

cai は cns の約 5 倍の規模。cai の OtherRetainedEarningsMember 配下に 26 種類の積立金 Member（配当準備積立金、減価償却積立金、海外投資損失準備金 等）が定義されており、行方向にもそれぞれの積立金の繰入・取崩 concept が存在する。

### ミラー構造

ガイドライン 2-1-3 に記載の通り、SS のようにディメンションを用いた多次元表では、**表示リンクと定義リンクに同等の詳細ツリー（ミラー）が定義される**。両者の相違点:

1. 表示リンクには `dimensionDefault` の設定がない
2. 表示リンクには `preferredLabel` 属性が設定される（期首ラベル・期末ラベルの区別に使用）
3. 表示リンクのアークロールは全て `parent-child`（定義リンクは `hypercube-dimension`, `dimension-domain`, `domain-member`, `all` 等を使い分ける）

### SS プレゼンテーションリンクベース

cai 業種には以下の SS 用プレゼンテーションファイルが存在:
- `jppfs_cai_ac_2025-11-01_pre_ss.xml` — 連結通期
- `jppfs_cai_an_2025-11-01_pre_ss.xml` — 個別通期
- `jppfs_cai_sc-t2_2025-11-01_pre_ss.xml` — 中間連結
- `jppfs_cai_sn-t2_2025-11-01_pre_ss.xml` — 中間個別

cns 業種には SS プレゼンテーションファイルが存在しない（定義リンクベースのみ）。

### 計算リンクの制約

ガイドライン 7-3 に記載の通り、SS の計算リンクには特別な制約がある:
- 計算リンクは**表示項目（行方向）**について定義する
- ディメンションメンバー（列方向）ごとに個別の計算関係を定義することは**できない**
- 定義された計算関係は、全ディメンションメンバーに共通して適用される
- つまり「当期変動額合計 = 各変動事由の合計」という縦方向の計算が、各列（資本金、資本剰余金 等）に一律適用される

### 情報源（Fact）

観察事実のみを記載する。推論や解釈は含めない。

- [F1] スクリプト: `docs/QAs/scripts/E-1c.ss_structure.py` 実行結果 -- cns 業種の SS 定義リンクベース: locator 32件、arc 31件。ルート要素 `StatementOfChangesInEquityAbstract`。ハイパーキューブ `StatementOfChangesInEquityTable` の下に `ComponentsOfEquityAxis`（19 Member）と `StatementOfChangesInEquityLineItems`（8 concept）が定義。
- [F2] 同スクリプト実行結果 -- cai 業種の SS 定義リンクベース: locator 172件、arc 171件。`ComponentsOfEquityAxis` 配下に約 50 の Member（`OtherRetainedEarningsMember` 下に 26 種の積立金 Member を含む）、`LineItems` 配下に約 110 の concept（各積立金の繰入・取崩を含む）。
- [F3] 同スクリプト実行結果 -- cns の `ComponentsOfEquityAxis` Member 一覧: NetAssetsMember > ShareholdersEquityMember > {CapitalStockMember, CapitalSurplusMember > {Legal, Other}, RetainedEarningsMember > {Legal, Other > RetainedEarningsBroughtForward}, TreasuryStockMember}, ValuationAndTranslationAdjustmentsMember > {4 Member}, ShareAwardRightsMember, SubscriptionRightsToSharesMember, NonControllingInterestsMember
- [F4] 同スクリプト実行結果 -- cns の `LineItems` 構造: NetAssets, ChangesOfItemsDuringThePeriodAbstract > {IssuanceOfNewShares, DividendsFromSurplus, ProfitLossAttributableToOwnersOfParent, ProfitLoss, DisposalOfTreasuryStock, NetChangesOfItemsOtherThanShareholdersEquity, TotalChangesOfItemsDuringThePeriod}
- [F5] 同スクリプト実行結果 -- SS プレゼンテーションリンクベースの存在確認: cns にはなし、cai には `_pre_ss.xml` が 4 件（ac, an, sc-t2, sn-t2）存在
- [F6] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.709-721 -- 「2-1-3 ミラーについて」: ディメンションを用いた多次元表（例：株主資本等変動計算書）の場合、表示リンク及び定義リンクに同等の詳細ツリーが定義される。表示リンクには dimensionDefault の設定がなく、preferredLabel 属性が設定される。ミラー時の表示リンクのアークロールは全て `parent-child`。
- [F7] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.3011-3049 -- 「6-4 定義リンクの定義 - 値を設定しないドメイン又はメンバー」: ドメインがインスタンス値を持たないときは usable 属性に「false」を設定。メンバーが値を持たなくても表示上存在する場合は詳細ツリーに設定し usable = false とする。図表 6-4-8, 6-4-9 に SS の具体的な表示例あり。
- [F8] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.3144 -- 「6-5-3-3 ディメンションにおける計算リンク」: 株主資本等変動計算書のように、ディメンションを用いる場合、表示項目ごとのメンバー間の計算関係を計算リンクに設定することはできない。メンバーごとの表示項目間の計算関係のみ設定できる。
- [F9] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.3173-3179 -- 「7-3 株主資本等変動計算書の計算リンク」: 計算リンクは表示項目について定義する。当期変動額の計算関係をディメンションメンバーごとにそれぞれ定義することはできない。定義された計算関係は全メンバーに共通適用される。
- [F10] 実タクソノミファイル — 科目一覧ツリー（`_cm_`）と詳細ツリー（`_ac_` 等）で arcrole が異なることをスクリプト `docs/QAs/scripts/E-1c.ss_arcroles.py` で確認:
  - `jppfs_cns_cm_2025-11-01_def_ss.xml`（cns 科目一覧）: arcrole は `general-special` のみ（31 arc）。ハイパーキューブ構造の arcrole は**含まれない**。
  - `jppfs_cai_cm_2025-11-01_def_ss.xml`（cai 科目一覧）: arcrole は `general-special` のみ（171 arc）。同様にハイパーキューブ arcrole は含まれない。
  - `jppfs_cai_ac_2025-11-01_def_ss.xml`（cai 詳細ツリー、連結通期）: XBRL Dimensions の arcrole 5種（`all`, `hypercube-dimension`, `dimension-domain`, `dimension-default`, `domain-member`）が使用されている（32 arc）。他の詳細ツリー（`_an_`, `_sc-t2_`, `_sn-t2_`）も同様。
  - cns 業種には詳細ツリーの `_def_ss` ファイル自体が存在しない。
- [F11] 実タクソノミファイル: EDINET 仕様書全体（設定規約書、フレームワーク設計書、ガイドライン）を検索し、「Table Linkbase」「テーブルリンクベース」への言及が**存在しない**ことを確認。
- [F12] スクリプト実行結果 -- cai の LineItems には `CumulativeEffectsOfChangesInAccountingPolicies`（会計方針の変更による累積的影響額）、`RestatedBalance`（遡及処理後残高）が cns には存在しない concept として含まれる。

### 推論（Reasoning）

1. **E-1c.1 SS の2次元構造**: [F1]+[F3]+[F4]+[F10] より、SS は `StatementOfChangesInEquityTable`（ハイパーキューブ）を頂点とする XBRL Dimensions 構造で表現される。科目一覧ツリー（`_cm_`）は `general-special` arcrole で概念の汎化-特化関係を定義し、詳細ツリー（`_ac_` 等）が XBRL Dimensions の arcrole を使って正式なハイパーキューブ構造を定義する。列方向は `ComponentsOfEquityAxis` の Member 階層で定義される。行方向は `StatementOfChangesInEquityLineItems` 配下の concept で定義される。列の区別はディメンション（Context の `xbrldi:explicitMember` 要素）で行い、period（instant vs duration）ではない。ただし period も重要な役割を果たす: `NetAssets`（当期首残高・当期末残高）は `periodType="instant"` であり、期首 instant と期末 instant で区別される。`ChangesOfItemsDuringThePeriod` 配下の変動事由は `periodType="duration"` である。つまり SS の Fact は `(concept, member, period)` の3軸で一意に特定される。

2. **E-1c.2 presentation linkbase の十分性**: [F6] より、EDINET では SS のような多次元表に対して presentation linkbase と definition linkbase のミラー構造を定義している。presentation linkbase にもツリー構造が存在するため、Member の一覧と表示順序は presentation linkbase からも取得可能。しかし [F10] より、詳細ツリーの定義リンクベース（`_ac_` 等）は `all`, `hypercube-dimension`, `dimension-domain`, `dimension-default`, `domain-member` の専用 arcrole を使用しており、ハイパーキューブの正式な次元関係を表現している（科目一覧ツリー `_cm_` は `general-special` のみで次元構造を持たない）。presentation linkbase のアークロールは全て `parent-child` であり（[F6]）、ノードが Table なのか Axis なのか Member なのかの意味的な区別はアークロールからは読み取れない。したがって、SS の次元構造を**正確に解釈する**には詳細ツリーの definition linkbase が必須。ただし**表示目的のみ**であれば presentation linkbase のミラー構造でも十分な情報が得られる。

3. **E-1c.3 Table Linkbase の必要性**: [F11] より、EDINET の仕様書全体に Table Linkbase（XBRL Table Linkbase 1.0 仕様 = `http://xbrl.org/2014/table` 名前空間のリンクベース）への言及は存在しない。EDINET は XBRL Dimensions 1.0 の definition linkbase のみでハイパーキューブ構造を表現しており、Table Linkbase は使用していない。Table Linkbase は主に ESEF（欧州統一電子形式）等で採用されている別の仕様であり、EDINET には不要。

4. **E-1c.4 行・列ヘッダーの取得方法**: [F1]+[F3]+[F4]+[F6] より、列ヘッダーは definition linkbase の `ComponentsOfEquityAxis` 配下の Member 階層から取得し、行ヘッダーは `StatementOfChangesInEquityLineItems` 配下の concept 階層から取得する。日本語表示名はラベルリンクベースの `label` ロールから取得する。presentation linkbase のミラーでも同等のツリーが得られるが、表示順序は presentation linkbase の `order` 属性が正式（definition linkbase の `order` は次元構造の定義用途であり、表示順序と一致するとは限らない）。なお [F7] より、表示上存在するが値を持たない Member/ドメインは `usable="false"` が設定されており、これにより列ヘッダーとしては表示するが Fact の存在は期待しないという区別が可能。

5. **業種による SS 構造の差異について**: [F1]+[F2] より、業種によって SS の規模が大きく異なる。cns（建設業）は最小限（19 Member、8 行 concept）だが、cai（一般商工業）は多数の積立金 Member と繰入・取崩 concept を含む大規模な構造（約 50 Member、約 110 行 concept）。提出者別タクソノミではこの cai のスーパーセットから実際に使用する Member/concept を選択して詳細ツリーを構築する。

### 確信度

- **E-1c.1 SS の2次元構造**: 高 -- definition linkbase を直接パースし、ハイパーキューブ構造を可視化済み（[F1]-[F4]）。仕様書のミラー説明（[F6]）とも整合。
- **E-1c.2 presentation linkbase の十分性**: 高 -- ミラー構造の仕様書記載（[F6]）と実タクソノミの arcrole 確認（[F10]）の両方で検証済み。
- **E-1c.3 Table Linkbase**: 高 -- 仕様書全文検索で不存在を確認（[F11]）。
- **E-1c.4 行・列ヘッダーの取得方法**: 高 -- definition linkbase と presentation linkbase の両方でツリー構造を確認済み。usable 属性の扱いは仕様書（[F7]）で確認。

### 検証（自己検証）

- 検証者: Claude Code (Opus 4.6)（回答者と同一セッション）
- 検証日: 2026-02-23
- 判定: OK

#### Step 1. 完全性検証
- [x] 全サブ質問（E-1c.1, E-1c.2, E-1c.3, E-1c.4）に対応する行が存在する
- [x] ハイパーキューブ構造の図解、業種差異、ミラー構造、計算リンクの制約を網羅

#### Step 2. Fact 検証
全12件の Fact を生データと突合し、引用内容の正確性を確認した。
- [F1]-[F5] OK -- スクリプト `E-1c.ss_structure.py` を `EDINET_TAXONOMY_ROOT` 環境変数付きで実行し、出力を確認。cns: locator 32、arc 31。cai: locator 172、arc 171。SS プレゼンテーションファイル: cns なし、cai に 4 件。
- [F6] OK -- ガイドライン L.709-721 に「2-1-3 ミラーについて」が記載。ディメンション多次元表の表示リンク・定義リンクのミラー関係を確認。
- [F7] OK -- ガイドライン L.3011-3049 に usable 属性の説明と SS の具体例（図表 6-4-8, 6-4-9）が記載。
- [F8] OK -- ガイドライン L.3144 に「ディメンションにおける計算リンク」の制約が記載。
- [F9] OK -- ガイドライン L.3173-3179 に「7-3 株主資本等変動計算書の計算リンク」が記載。
- [F10] OK -- スクリプト `E-1c.ss_arcroles.py` により、科目一覧ツリー（`_cm_`）は `general-special` のみ、詳細ツリー（`_ac_` 等）は XBRL Dimensions arcrole 5種を使用することを確認。
- [F11] OK -- 設定規約書、フレームワーク設計書、ガイドライン、インスタンスガイドラインの全文を「Table Linkbase」「テーブルリンクベース」で検索し、該当なしを確認。
- [F12] OK -- cai の LineItems に `CumulativeEffectsOfChangesInAccountingPolicies` と `RestatedBalance` が含まれることをスクリプト出力で確認。

#### Step 3. 推論検証
- [x] 推論1: [F1]+[F3]+[F4] から SS の2次元構造を導出 -- ハイパーキューブの TABLE/AXIS/MEMBER/LINE-ITEMS 構造から論理的に妥当
- [x] 推論2: [F6]+[F10] から presentation linkbase の限界を導出 -- arcrole の違い（parent-child vs 詳細ツリーの次元専用 arcrole）に基づく議論は論理的に妥当。科目一覧ツリー `_cm_` は `general-special` のみであり、ハイパーキューブ arcrole は詳細ツリー `_ac_` 等にのみ存在することを明確化
- [x] 推論3: [F11] から Table Linkbase 不要を導出 -- 仕様書に言及がないことから不使用を結論。反証探索でも Table Linkbase を示唆する記述は発見されなかった
- [x] 推論4: [F1]+[F3]+[F4]+[F6]+[F7] から行・列ヘッダー取得方法を導出 -- ミラー構造の存在と usable 属性の扱いを組み合わせた議論は論理的に妥当
- [x] 推論5: [F1]+[F2] から業種差異を導出 -- cns(32) vs cai(172) の規模差は定量的に明確

#### Step 4. 依存関係検証
- [x] I-1.a.md との整合: I-1.a.md の SS ロール（`rol_std_ConsolidatedStatementOfChangesInEquity` 等、ELR 330010）と本回答の SS 構造が整合
- [x] C-6.a.md との整合: C-6.a.md のプレゼンテーションリンクベース構造の説明と、本回答のミラー構造の説明が整合

### 検証（第三者検証）

- 検証者: Claude Code (Opus 4.6)（回答者とは別セッション）
- 検証日: 2026-02-23
- 判定: OK（修正済み）
- 修正事項:
  - [F10]: 科目一覧ツリー（`_cm_`）の arcrole が `general-special` のみであり、XBRL Dimensions arcrole は詳細ツリー（`_ac_` 等）にのみ存在する事実を反映。スクリプト `E-1c.ss_arcroles.py` を新規作成して検証
  - ハイパーキューブ構造の説明セクション: `_cm_` と `_ac_` 等の区別を明確化し、ツリー図が cai の統合概念図であることを注記
  - 推論 1, 2: 科目一覧ツリーと詳細ツリーの違いを反映した記述に修正

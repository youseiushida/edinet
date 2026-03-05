# CK 追加候補一覧（タクソノミ実在確認済み）

> **作成日**: 2026-03-05
> **対象タクソノミ**: ALL_20251101

---

## ユーザー提案（6 CK）

| CK | 日本語名 | JGAAP マッピング（優先度順） | IFRS マッピング（優先度順） | データ型 | period | balance | 備考 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `land` | 土地 | `Land` (jppfs) | `LandIFRS` (jpigp) | monetaryItemType | instant | debit | 1:1 でクリーン |
| `buildings_net` | 建物純額 | `BuildingsNet` (jppfs) | `BuildingsIFRS` (jpigp) | monetaryItemType | instant | debit | BS の簿価として最も標準的 |
| `investment_property` | 投資不動産 | `RealEstateForInvestmentNet` → `RealEstateForInvestment` (jppfs) | `InvestmentPropertyIFRS` (jpigp) | monetaryItemType | instant | debit | JGAAP の賃貸用不動産は IFRS 側に対応なし。投資不動産に絞るのが安全 |
| `real_estate_for_sale` | 販売用不動産 | `RealEstateForSale` (jppfs) | `RealEstateForSaleCAIFRS` (jpigp) | monetaryItemType | instant | debit | 1:1 でクリーン |
| `contract_assets` | 契約資産 | `ContractAssetsNet` → `ContractAssets` (jppfs) | `ContractAssetsCAIFRS` (jpigp) | monetaryItemType | instant | debit | 1:1 でクリーン |
| `contract_liabilities` | 契約負債 | `ContractLiabilities` → `AdvancesReceived` → `AdvancesReceivedOnUncompletedConstructionContractsCNS` → `AdvancesReceivedOnUncompletedContracts` (jppfs) | `ContractLiabilitiesCLIFRS` → `AdvancesReceivedCLIFRS` (jpigp) | monetaryItemType | instant | credit | JGAAP のレガシー科目（前受金、未成工事等）を契約負債の概念に巻き取る設計 |

---

## Tier 1: 強く追加推奨（4 CK）

| CK | 日本語名 | JGAAP マッピング（優先度順） | IFRS マッピング（優先度順） | データ型 | period | balance | 備考 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `construction_in_progress` | 建設仮勘定 | `ConstructionInProgress` (jppfs) | `ConstructionInProgressIFRS` (jpigp) | monetaryItemType | instant | debit | 1:1 でクリーン。設備投資の先行指標。既存 CK `capex` とのペア |
| `investment_securities` | 投資有価証券 | `InvestmentSecurities` (jppfs) | `InvestmentSecuritiesNCAIFRS` (jpigp) | monetaryItemType | instant | debit | 1:1。既存 CK `cross_shareholdings_amount` は上場株のみ、これは BS 全体の投資有価証券 |
| `impairment_loss_pl` | 減損損失（PL） | `ImpairmentLossEL` (jppfs) | `ImpairmentLossesPLIFRS` → `ImpairmentLossesOnNonFinancialAssetsPLIFRS` (jpigp) | monetaryItemType | duration | debit | CF 版 `impairment_loss_cf` は既存。PL 版が欠けている |
| `right_of_use_assets` | 使用権資産 | `RightOfUseAssetsNetPPE` → `RightOfUseAssetsNet` → `RightOfUseAssets` (jppfs) | `RightOfUseAssetsIFRS` (jpigp) | monetaryItemType | instant | debit | 既存 CK `lease_liabilities_cl/ncl` の資産側ペア |

---

## Tier 2: あると便利（5 CK）

| CK | 日本語名 | JGAAP マッピング（優先度順） | IFRS マッピング（優先度順） | データ型 | period | balance | 備考 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `current_portion_of_bonds` | 1年内償還社債 | `CurrentPortionOfBonds` (jppfs) | *(IFRS 該当なし — `BondsPayableLiabilitiesIFRS` に統合)* | monetaryItemType | instant | credit | 既存 CK `bonds_payable` は固定負債のみ。流動負債側がない |
| `current_portion_of_long_term_loans` | 1年内返済長期借入金 | `CurrentPortionOfLongTermLoansPayable` (jppfs) | `CurrentPortionOfLongTermBorrowingsCLIFRS` (jpigp) | monetaryItemType | instant | credit | 短期/長期の有利子負債分析に必須 |
| `notes_receivable` | 受取手形 | `NotesReceivableTrade` (jppfs) | *(IFRS では `TradeAndOtherReceivablesCAIFRS` に統合)* | monetaryItemType | instant | debit | 業種分析（建設・製造）で需要あり。IFRS 対応が弱い |
| `notes_payable` | 支払手形 | `NotesPayableTrade` (jppfs) | `TradePayablesCLIFRS` (jpigp) | monetaryItemType | instant | credit | 同上 |
| `subscription_rights` | 新株予約権 | `SubscriptionRightsToShares` (jppfs) | *(IFRS では equity の内訳)* | monetaryItemType | instant | credit | 純資産の内訳項目。JGAAP のみだが需要あり |

---

## Tier 3: 検討レベル（4 CK）

| CK | 日本語名 | JGAAP マッピング（優先度順） | IFRS マッピング（優先度順） | データ型 | period | balance | 備考 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `provisions_cl` | 引当金（流動） | `ProvisionCL` (jppfs) | `ProvisionsCLIFRS` (jpigp) | monetaryItemType | instant | credit | 受注損失引当金含む合計。ただし JGAAP の `ProvisionCL` は合計タグとして使われない企業もある |
| `provisions_ncl` | 引当金（固定） | `ProvisionNCL` (jppfs) | `ProvisionsNCLIFRS` (jpigp) | monetaryItemType | instant | credit | 同上 |
| `depreciation_sga` | 減価償却費（販管費） | `DepreciationSGA` (jppfs) | `DepreciationSGAIFRS` → `DepreciationAndAmortizationSGAIFRS` (jpigp) | monetaryItemType | duration | debit | CF 版 `depreciation_cf` はあるが PL 版がない |
| `prepaid_expenses` | 前払費用 | `PrepaidExpenses` (jppfs) | *(IFRS では `OtherFinancialAssetsCAIFRS` 等に統合)* | monetaryItemType | instant | debit | IFRS 対応が弱いため優先度低 |

---

## サマリ

| 優先度 | CK 数 | 累計 | 内容 |
|:---|---:|---:|:---|
| ユーザー提案 | 6 | 6 | 不動産・契約資産/負債 |
| **Tier 1（強く推奨）** | 4 | 10 | 建設仮勘定・投資有価証券・減損PL・使用権資産 |
| Tier 2（便利） | 5 | 15 | 有利子負債内訳・手形・新株予約権 |
| Tier 3（検討） | 4 | 19 | 引当金・販管費減価償却・前払費用 |
| **合計** | **19** | **既存 145 + 19 = 164** | |

## CK 化不向きと判定したもの（参考）

| テーマ | 理由 |
|:---|:---|
| 不動産の時価 | TextBlock 内の HTML 表に埋まっている。パース必要 |
| 主要顧客の売上詳細 | TextBlock（HTML 表） |
| 特定投資株式の個別銘柄 | Dimension テーブル構造（1銘柄 = 1メンバー） |
| 設備投資の計画 | TextBlock（HTML 表） |
| 受注高・受注残高 | TextBlock（HTML 表） |
| 外部顧客売上（セグメント別） | Dimension（`OperatingSegmentsAxis`）付き。`extract_segments` 向き |
| セグメント利益・資産 | 同上 |

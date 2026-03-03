# Lane 6 ディメンション軸調査結果


# 調査日: 2025-06-27

- 有報候補数: 369

## リーディング証券株式会社 (E23973) — S100W45Y
- 書類種別: 有価証券報告書－第77期(2024/04/01－2025/03/31)
- 提出日: 2025-06-27
- 提出者ラベル数: 48
- LineItem 総数: 671
- ディメンション付き LineItem 数: 553
- ユニーク軸数: 4

### ディメンション軸一覧

| # | 軸ローカル名 | 軸ラベル(ja) | 軸ラベル(en) | メンバー数 | LineItem数 | NS種別 |
|---|---|---|---|---|---|---|
| 1 | `ConsolidatedOrNonConsolidatedAxis` | 連結個別 [standard] | Consolidated or non-consolidated | 1 | 509 | standard_taxonomy (jppfs_cor) |
| 2 | `ComponentsOfEquityAxis` | 純資産の内訳項目 [standard] | Components of net assets | 10 | 56 | standard_taxonomy (jppfs_cor) |
| 3 | `MajorShareholdersAxis` | 大株主 [standard] | Major shareholders | 10 | 40 | standard_taxonomy (jpcrp_cor) |
| 4 | `SequentialNumbersAxis` | 連番 [standard] | Sequential numbers | 1 | 4 | standard_taxonomy (jpcrp_cor) |

### 軸: `ComponentsOfEquityAxis` (純資産の内訳項目) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `RetainedEarningsBroughtForwardMember` | 繰越利益剰余金 [standard] | Retained earnings brought forward | 8 | 標準 |
| 2 | `RetainedEarningsMember` | 利益剰余金 [standard] | Retained earnings | 8 | 標準 |
| 3 | `ShareholdersEquityMember` | 株主資本 [standard] | Shareholders' equity | 8 | 標準 |
| 4 | `ValuationDifferenceOnAvailableForSaleSecuritiesMember` | その他有価証券評価差額金 [standard] | Valuation difference on available-for-sale securities | 8 | 標準 |
| 5 | `CapitalStockMember` | 資本金 [standard] | Share capital | 4 | 標準 |
| 6 | `LegalCapitalSurplusMember` | 資本準備金 [standard] | Legal capital surplus | 4 | 標準 |
| 7 | `CapitalSurplusMember` | 資本剰余金 [standard] | Capital surplus | 4 | 標準 |
| 8 | `LegalRetainedEarningsMember` | 利益準備金 [standard] | Legal retained earnings | 4 | 標準 |
| 9 | `GeneralReserveMember` | 別途積立金 [standard] | General reserve | 4 | 標準 |
| 10 | `TreasuryStockMember` | 自己株式 [standard] | Treasury shares | 4 | 標準 |

### 軸: `MajorShareholdersAxis` (大株主) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `No1MajorShareholdersMember` | 第1位 [standard] | No. 1 | 4 | 標準 |
| 2 | `No2MajorShareholdersMember` | 第2位 [standard] | No. 2 | 4 | 標準 |
| 3 | `No3MajorShareholdersMember` | 第3位 [standard] | No. 3 | 4 | 標準 |
| 4 | `No4MajorShareholdersMember` | 第4位 [standard] | No. 4 | 4 | 標準 |
| 5 | `No5MajorShareholdersMember` | 第5位 [standard] | No. 5 | 4 | 標準 |
| 6 | `No6MajorShareholdersMember` | 第6位 [standard] | No. 6 | 4 | 標準 |
| 7 | `No7MajorShareholdersMember` | 第7位 [standard] | No. 7 | 4 | 標準 |
| 8 | `No8MajorShareholdersMember` | 第8位 [standard] | No. 8 | 4 | 標準 |
| 9 | `No9MajorShareholdersMember` | 第9位 [standard] | No. 9 | 4 | 標準 |
| 10 | `No10MajorShareholdersMember` | 第10位 [standard] | No. 10 | 4 | 標準 |

### Definition Linkbase 軸情報 (XBRL/PublicDoc/jpcrp030000-asr-001_E23973-000_2025-03-31_01_2025-06-27_def.xml)

| role_uri (末尾) | Table | Axis | デフォルトメンバー | ドメインメンバー数 |
|---|---|---|---|---|
| `rol_BusinessResultsOfReportingCompany` | `BusinessResultsOfReportingCompanyTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_DisclosureOfSustainabilityRelatedFinancialInformation-01` | `DescriptionOfMetricsRelatedToPolicyOnDevelopmentOfHumanResourcesAndInternalEnvironmentAndTargetsAndPerformanceUsingSuchMetricsTable` | `SequentialNumbersAxis` | `(なし)` | 1 |
| `rol_MajorShareholders-01` | `MajorShareholdersTable` | `MajorShareholdersAxis` | `MajorShareholdersMember` | 11 |
| `rol_BalanceSheet` | `BalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfIncome` | `StatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ComponentsOfEquityAxis` | `NetAssetsMember` | 13 |
| `rol_StatementOfCashFlows-indirect` | `StatementOfCashFlowsTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesBalanceSheet` | `NotesBalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesStatementOfIncome` | `NotesStatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesStatementOfChangesInEquity` | `NotesStatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesStatementOfCashFlows` | `NotesStatementOfCashFlowsTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesSegmentInformationEtcFinancialStatements-01` | `NotesSegmentInformationEtcFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesSegmentInformationEtcFinancialStatements-03` | `NotesSegmentInformationEtcFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesSegmentInformationEtcFinancialStatements-09` | `InformationAboutGainOnBargainPurchaseForEachReportableSegmentTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesSegmentInformationEtcFinancialStatements-09` | `InformationAboutGainOnBargainPurchaseForEachReportableSegmentTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 1 |

## トヨタファイナンス株式会社 (E05031) — S100W47T
- 書類種別: 有価証券報告書－第37期(2024/04/01－2025/03/31)
- 提出日: 2025-06-27
- 提出者ラベル数: 90
- LineItem 総数: 1131
- ディメンション付き LineItem 数: 528
- ユニーク軸数: 3

### ディメンション軸一覧

| # | 軸ローカル名 | 軸ラベル(ja) | 軸ラベル(en) | メンバー数 | LineItem数 | NS種別 |
|---|---|---|---|---|---|---|
| 1 | `ConsolidatedOrNonConsolidatedAxis` | 連結個別 [standard] | Consolidated or non-consolidated | 1 | 444 | standard_taxonomy (jppfs_cor) |
| 2 | `ComponentsOfEquityAxis` | 純資産の内訳項目 [standard] | Components of net assets | 14 | 172 | standard_taxonomy (jppfs_cor) |
| 3 | `MajorShareholdersAxis` | 大株主 [standard] | Major shareholders | 1 | 4 | standard_taxonomy (jpcrp_cor) |

### 軸: `ComponentsOfEquityAxis` (純資産の内訳項目) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `RetainedEarningsMember` | 利益剰余金 [standard] | Retained earnings | 22 | 標準 |
| 2 | `ShareholdersEquityMember` | 株主資本 [standard] | Shareholders' equity | 22 | 標準 |
| 3 | `ValuationDifferenceOnAvailableForSaleSecuritiesMember` | その他有価証券評価差額金 [standard] | Valuation difference on available-for-sale securities | 16 | 標準 |
| 4 | `DeferredGainsOrLossesOnHedgesMember` | 繰延ヘッジ損益 [standard] | Deferred gains or losses on hedges | 16 | 標準 |
| 5 | `ValuationAndTranslationAdjustmentsMember` | 評価・換算差額等 [standard] | Valuation and translation adjustments | 16 | 標準 |
| 6 | `CapitalStockMember` | 資本金 [standard] | Share capital | 12 | 標準 |
| 7 | `CapitalSurplusMember` | 資本剰余金 [standard] | Capital surplus | 12 | 標準 |
| 8 | `RetainedEarningsBroughtForwardMember` | 繰越利益剰余金 [standard] | Retained earnings brought forward | 12 | 標準 |
| 9 | `ForeignCurrencyTranslationAdjustmentMember` | 為替換算調整勘定 [standard] | Foreign currency translation adjustment | 8 | 標準 |
| 10 | `RemeasurementsOfDefinedBenefitPlansMember` | 退職給付に係る調整累計額 [standard] | Remeasurements of defined benefit plans | 8 | 標準 |
| 11 | `NonControllingInterestsMember` | 非支配株主持分 [standard] | Non-controlling interests | 8 | 標準 |
| 12 | `GeneralReserveMember` | 別途積立金 [standard] | General reserve | 8 | 標準 |
| 13 | `LegalCapitalSurplusMember` | 資本準備金 [standard] | Legal capital surplus | 6 | 標準 |
| 14 | `LegalRetainedEarningsMember` | 利益準備金 [standard] | Legal retained earnings | 6 | 標準 |

### Definition Linkbase 軸情報 (XBRL/PublicDoc/jpcrp030000-asr-001_E05031-000_2025-03-31_01_2025-06-27_def.xml)

| role_uri (末尾) | Table | Axis | デフォルトメンバー | ドメインメンバー数 |
|---|---|---|---|---|
| `rol_BusinessResultsOfGroup` | `BusinessResultsOfGroupTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_BusinessResultsOfReportingCompany` | `BusinessResultsOfReportingCompanyTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_MajorShareholders-01` | `MajorShareholdersTable` | `MajorShareholdersAxis` | `MajorShareholdersMember` | 2 |
| `rol_ConsolidatedBalanceSheet` | `BalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfIncome` | `StatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfComprehensiveIncome` | `StatementOfComprehensiveIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ComponentsOfEquityAxis` | `NetAssetsMember` | 11 |
| `rol_ConsolidatedStatementOfCashFlows-indirect` | `StatementOfCashFlowsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSignificantAccountingPoliciesForPreparationOfConsolidatedFinancialStatements` | `NotesSignificantAccountingPoliciesForPreparationOfConsolidatedFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedBalanceSheet` | `NotesConsolidatedBalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfIncome` | `NotesConsolidatedStatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfComprehensiveIncome` | `NotesConsolidatedStatementOfComprehensiveIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfChangesInEquity` | `NotesConsolidatedStatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfCashFlows` | `NotesConsolidatedStatementOfCashFlowsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-01` | `NotesSegmentInformationEtcConsolidatedFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-03` | `NotesSegmentInformationEtcConsolidatedFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-09` | `InformationAboutGainOnBargainPurchaseForEachReportableSegmentTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-09` | `InformationAboutGainOnBargainPurchaseForEachReportableSegmentTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 1 |
| `rol_BalanceSheet` | `BalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfIncome` | `StatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ComponentsOfEquityAxis` | `NetAssetsMember` | 13 |
| `rol_NotesBalanceSheet` | `NotesBalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |

## アセットマネジメントＯｎｅ株式会社 (E10677) — S100W0DL
- 書類種別: 有価証券報告書（内国投資信託受益証券）－第3期(2024/03/29－2025/03/28)
- 提出日: 2025-06-27
- 提出者ラベル数: 0
- LineItem 総数: 167
- ディメンション付き LineItem 数: 80
- ユニーク軸数: 1

### ディメンション軸一覧

| # | 軸ローカル名 | 軸ラベル(ja) | 軸ラベル(en) | メンバー数 | LineItem数 | NS種別 |
|---|---|---|---|---|---|---|
| 1 | `ConsolidatedOrNonConsolidatedAxis` | 連結個別 [standard] | Consolidated or non-consolidated | 1 | 80 | standard_taxonomy (jppfs_cor) |

### Definition Linkbase 軸情報 (XBRL/PublicDoc/jpsps070000-asr-001_G14133-000_2025-03-28_01_2025-06-27_def.xml)

| role_uri (末尾) | Table | Axis | デフォルトメンバー | ドメインメンバー数 |
|---|---|---|---|---|
| `rol_BalanceSheet` | `BalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfIncomeAndRetainedEarnings` | `StatementOfIncomeAndRetainedEarningsTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |

## 株式会社ＳＤＳホールディングス (E05452) — S100W7QE
- 書類種別: 有価証券報告書－第40期(2024/04/01－2025/03/31)
- 提出日: 2025-06-27
- 提出者ラベル数: 72
- LineItem 総数: 1417
- ディメンション付き LineItem 数: 749
- ユニーク軸数: 9

### ディメンション軸一覧

| # | 軸ローカル名 | 軸ラベル(ja) | 軸ラベル(en) | メンバー数 | LineItem数 | NS種別 |
|---|---|---|---|---|---|---|
| 1 | `ConsolidatedOrNonConsolidatedAxis` | 連結個別 [standard] | Consolidated or non-consolidated | 1 | 358 | standard_taxonomy (jppfs_cor) |
| 2 | `ComponentsOfEquityAxis` | 純資産の内訳項目 [standard] | Components of net assets | 12 | 165 | standard_taxonomy (jppfs_cor) |
| 3 | `DirectorsAndOtherOfficersAxis` | 役員 [standard] | Directors (and other officers) | 8 | 90 | standard_taxonomy (jpcrp_cor) |
| 4 | `OperatingSegmentsAxis` | 事業セグメント [standard] | Operating segments | 6 | 85 | standard_taxonomy (jpcrp_cor) |
| 5 | `MajorShareholdersAxis` | 大株主 [standard] | Major shareholders | 10 | 40 | standard_taxonomy (jpcrp_cor) |
| 6 | `SequentialNumbersAxis` | 連番 [standard] | Sequential numbers | 5 | 38 | standard_taxonomy (jpcrp_cor) |
| 7 | `ClassesOfSharesAxis` | 株式種類 [standard] | Classes of shares | 1 | 30 | standard_taxonomy (jpcrp_cor) |
| 8 | `CategoriesOfDirectorsAndOtherOfficersAxis` | 役員区分 [standard] | Categories of directors (and other officers) | 4 | 20 | standard_taxonomy (jpcrp_cor) |
| 9 | `CategoriesIssuedSharesAxis` | 区分 [standard] | Categories | 6 | 14 | standard_taxonomy (jpcrp_cor) |

### 軸: `ComponentsOfEquityAxis` (純資産の内訳項目) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `ShareholdersEquityMember` | 株主資本 [standard] | Shareholders' equity | 23 | 標準 |
| 2 | `SubscriptionRightsToSharesMember` | 新株予約権 [standard] | Share acquisition rights | 18 | 標準 |
| 3 | `CapitalStockMember` | 資本金 [standard] | Share capital | 16 | 標準 |
| 4 | `CapitalSurplusMember` | 資本剰余金 [standard] | Capital surplus | 16 | 標準 |
| 5 | `RetainedEarningsMember` | 利益剰余金 [standard] | Retained earnings | 16 | 標準 |
| 6 | `ValuationDifferenceOnAvailableForSaleSecuritiesMember` | その他有価証券評価差額金 [standard] | Valuation difference on available-for-sale securities | 16 | 標準 |
| 7 | `ValuationAndTranslationAdjustmentsMember` | 評価・換算差額等 [standard] | Valuation and translation adjustments | 16 | 標準 |
| 8 | `TreasuryStockMember` | 自己株式 [standard] | Treasury shares | 14 | 標準 |
| 9 | `NonControllingInterestsMember` | 非支配株主持分 [standard] | Non-controlling interests | 8 | 標準 |
| 10 | `LegalCapitalSurplusMember` | 資本準備金 [standard] | Legal capital surplus | 8 | 標準 |
| 11 | `RetainedEarningsBroughtForwardMember` | 繰越利益剰余金 [standard] | Retained earnings brought forward | 8 | 標準 |
| 12 | `OtherCapitalSurplusMember` | その他資本剰余金 [standard] | Other capital surplus | 6 | 標準 |

### 軸: `DirectorsAndOtherOfficersAxis` (役員) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `WatanabeYusukeMember` | 渡辺　悠介 [filer] | Watanabe, Yusuke | 12 | **提出者** |
| 2 | `YoshinoKatsuhideMember` | 吉野　勝秀 [filer] | Yoshino,katsuhide | 12 | **提出者** |
| 3 | `SekiharaTatsuyaMember` | 関原　竜也 [filer] | Sekihara, Tatsuya | 12 | **提出者** |
| 4 | `KasaharaHirokazuMember` | 笠原　弘和 [filer] | Kasahara,Hirokazu | 12 | **提出者** |
| 5 | `KawasakiShuichiMember` | 川崎　修一 [filer] | Kawasaki,Shuichi | 12 | **提出者** |
| 6 | `KondoYoujiMember` | 近藤　洋治 [filer] | Kondo,Youji | 12 | **提出者** |
| 7 | `MinagawaShigekiMember` | 皆川　茂基 [filer] | Minagawa, Shigeki | 12 | **提出者** |
| 8 | `TanakaKiyoshiMember` | 田中　圭 [filer] | Tanaka Kiyoshi | 6 | **提出者** |

### 軸: `OperatingSegmentsAxis` (事業セグメント) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `SavingEnergyRelatedReportableSegmentsMember` | 省エネルギー関連事業 [filer] | Saving energy related | 22 | **提出者** |
| 2 | `RinobeshonBuisinessReportableSegmentMember` | リノベーション事業 [filer] | Rinobeshon buisiness | 21 | **提出者** |
| 3 | `ReportableSegmentsMember` | 報告セグメント [standard] | Reportable segments | 20 | 標準 |
| 4 | `ReconcilingItemsMember` | 調整項目 [standard] | Reconciling items | 16 | 標準 |
| 5 | `UnallocatedAmountsAndEliminationMember` | 全社・消去 [standard] | Unallocated amounts and elimination | 4 | 標準 |
| 6 | `CorporateSharedMember` | 全社（共通） [standard] | Corporate (shared) | 2 | 標準 |

### 軸: `MajorShareholdersAxis` (大株主) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `No1MajorShareholdersMember` | 第1位 [standard] | No. 1 | 4 | 標準 |
| 2 | `No2MajorShareholdersMember` | 第2位 [standard] | No. 2 | 4 | 標準 |
| 3 | `No3MajorShareholdersMember` | 第3位 [standard] | No. 3 | 4 | 標準 |
| 4 | `No4MajorShareholdersMember` | 第4位 [standard] | No. 4 | 4 | 標準 |
| 5 | `No5MajorShareholdersMember` | 第5位 [standard] | No. 5 | 4 | 標準 |
| 6 | `No6MajorShareholdersMember` | 第6位 [standard] | No. 6 | 4 | 標準 |
| 7 | `No7MajorShareholdersMember` | 第7位 [standard] | No. 7 | 4 | 標準 |
| 8 | `No8MajorShareholdersMember` | 第8位 [standard] | No. 8 | 4 | 標準 |
| 9 | `No9MajorShareholdersMember` | 第9位 [standard] | No. 9 | 4 | 標準 |
| 10 | `No10MajorShareholdersMember` | 第10位 [standard] | No. 10 | 4 | 標準 |

### 軸: `SequentialNumbersAxis` (連番) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `Row1Member` | 1件目 [standard] | Row 1 | 20 | 標準 |
| 2 | `Row2Member` | 2件目 [standard] | Row 2 | 7 | 標準 |
| 3 | `Row3Member` | 3件目 [standard] | Row 3 | 7 | 標準 |
| 4 | `Row4Member` | 4件目 [standard] | Row 4 | 2 | 標準 |
| 5 | `Row5Member` | 5件目 [standard] | Row 5 | 2 | 標準 |

### 軸: `CategoriesOfDirectorsAndOtherOfficersAxis` (役員区分) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `DirectorsExcludingAuditAndSupervisoryCommitteeMembersAndOutsideDirectorsMember` | 取締役（監査等委員及び社外取締役を除く） [standard] | Directors excluding audit and supervisory committee members and outside directors | 5 | 標準 |
| 2 | `OutsideDirectorsMember` | 社外取締役 [standard] | Outside directors | 5 | 標準 |
| 3 | `DirectorsAppointedAsAuditAndSupervisoryCommitteeMembersExcludingOutsideDirectorsMember` | 監査等委員（社外取締役を除く） [standard] | Directors appointed as audit and supervisory committee members excluding outside directors | 5 | 標準 |
| 4 | `OutsideDirectorsAppointedAsAuditAndSupervisoryCommitteeMembersMember` | うち社外取締役 [filer] | Outside directors appointed as audit and supervisory committee members | 5 | **提出者** |

### 軸: `CategoriesIssuedSharesAxis` (区分) — メンバー詳細

| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |
|---|---|---|---|---|---|
| 1 | `SharesWithRestrictedVotingRightsOtherMember` | 議決権制限株式（その他） [standard] | Shares with restricted voting rights (Other) | 3 | 標準 |
| 2 | `OrdinarySharesSharesWithFullVotingRightsOtherMember` | 普通株式 [standard] | Ordinary shares | 3 | 標準 |
| 3 | `SharesWithNoVotingRightsMember` | 無議決権株式 [standard] | Shares with no voting rights | 2 | 標準 |
| 4 | `SharesWithRestrictedVotingRightsTreasurySharesEtcMember` | 議決権制限株式（自己株式等） [standard] | Shares with restricted voting rights (Treasury shares, etc.) | 2 | 標準 |
| 5 | `OrdinarySharesTreasurySharesSharesWithFullVotingRightsTreasurySharesEtcMember` | （自己保有株式）普通株式 [standard] | Ordinary shares - Treasury shares | 2 | 標準 |
| 6 | `OrdinarySharesSharesLessThanOneUnitMember` | 普通株式 [standard] | Ordinary shares | 2 | 標準 |

### Definition Linkbase 軸情報 (XBRL/PublicDoc/jpcrp030000-asr-001_E05452-000_2025-03-31_01_2025-06-27_def.xml)

| role_uri (末尾) | Table | Axis | デフォルトメンバー | ドメインメンバー数 |
|---|---|---|---|---|
| `rol_BusinessResultsOfGroup` | `BusinessResultsOfGroupTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_BusinessResultsOfReportingCompany` | `BusinessResultsOfReportingCompanyTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_InformationAboutEmployees-01` | `NumberOfEmployeesOfGroupTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_InformationAboutEmployees-01` | `NumberOfEmployeesOfGroupTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 5 |
| `rol_InformationAboutEmployees-02` | `InformationAboutEmployeesOfReportingCompanyTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_InformationAboutEmployees-03` | `NumberOfEmployeesOfReportingCompanyTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_InformationAboutEmployees-03` | `NumberOfEmployeesOfReportingCompanyTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 4 |
| `rol_InformationAboutEmployees-04` | `MetricsOfReportingCompanyTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_DisclosureOfSustainabilityRelatedFinancialInformation-01` | `DescriptionOfMetricsRelatedToPolicyOnDevelopmentOfHumanResourcesAndInternalEnvironmentAndTargetsAndPerformanceUsingSuchMetricsTable` | `SequentialNumbersAxis` | `(なし)` | 1 |
| `rol_OverviewOfCapitalExpendituresEtc` | `CapitalExpendituresOverviewOfCapitalExpendituresEtcTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 1 |
| `rol_IssuedSharesTotalNumberOfSharesEtc` | `IssuedSharesTotalNumberOfSharesEtcTable` | `ClassesOfSharesAxis` | `TotalClassesOfSharesMember` | 2 |
| `rol_ShareholdingByShareholderCategory` | `ShareholdingByShareholderCategoryTable` | `ClassesOfSharesAxis` | `TotalClassesOfSharesMember` | 2 |
| `rol_MajorShareholders-01` | `MajorShareholdersTable` | `MajorShareholdersAxis` | `MajorShareholdersMember` | 11 |
| `rol_IssuedSharesVotingRights` | `IssuedSharesVotingRightsTable` | `CategoriesIssuedSharesAxis` | `TotalNumberOfIssuedSharesNumberOfVotingRightsHeldByAllShareholdersMember` | 11 |
| `rol_TreasurySharesEtc` | `TreasurySharesEtcTable` | `SequentialNumbersAxis` | `TotalSequentialNumbersMember` | 2 |
| `rol_InformationAboutOfficers-02` | `InformationAboutDirectorsAndCorporateAuditorsTable` | `DirectorsAndOtherOfficersAxis` | `DirectorsAndOtherOfficersMember` | 8 |
| `rol_InformationAboutOfficers-03` | `FootnotesDirectorsAndCorporateAuditorsTable` | `SequentialNumbersAxis` | `(なし)` | 1 |
| `rol_InformationAboutOfficers-07` | `InformationAboutDirectorsAndCorporateAuditorsProposalTable` | `DirectorsAndOtherOfficersAxis` | `DirectorsAndOtherOfficersMember` | 9 |
| `rol_InformationAboutOfficers-08` | `FootnotesDirectorsAndCorporateAuditorsProposalTable` | `SequentialNumbersAxis` | `(なし)` | 1 |
| `rol_RemunerationForDirectorsAndOtherOfficers-01` | `RemunerationEtcByCategoryOfDirectorsAndOtherOfficersTable` | `CategoriesOfDirectorsAndOtherOfficersAxis` | `(なし)` | 1 |
| `rol_Shareholdings-02` | `DetailsOfSpecifiedInvestmentEquitySecuritiesHeldForPurposesOtherThanPureInvestmentReportingCompanyTable` | `SequentialNumbersAxis` | `(なし)` | 1 |
| `rol_ConsolidatedBalanceSheet` | `BalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfIncome` | `StatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfComprehensiveIncome` | `StatementOfComprehensiveIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_ConsolidatedStatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ComponentsOfEquityAxis` | `NetAssetsMember` | 10 |
| `rol_ConsolidatedStatementOfCashFlows-indirect` | `StatementOfCashFlowsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSignificantAccountingPoliciesForPreparationOfConsolidatedFinancialStatements` | `NotesSignificantAccountingPoliciesForPreparationOfConsolidatedFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedBalanceSheet` | `NotesConsolidatedBalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfIncome` | `NotesConsolidatedStatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfComprehensiveIncome` | `NotesConsolidatedStatementOfComprehensiveIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfChangesInEquity` | `NotesConsolidatedStatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesConsolidatedStatementOfCashFlows` | `NotesConsolidatedStatementOfCashFlowsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-01` | `NotesSegmentInformationEtcConsolidatedFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-02` | `DisclosureOfSalesProfitLossAssetLiabilityAndOtherItemsForEachReportableSegmentTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-02` | `DisclosureOfSalesProfitLossAssetLiabilityAndOtherItemsForEachReportableSegmentTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 6 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-03` | `NotesSegmentInformationEtcConsolidatedFinancialStatementsTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-06` | `AmortizationAndUnamortizedBalanceOfGoodwillForEachReportableSegmentTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-06` | `AmortizationAndUnamortizedBalanceOfGoodwillForEachReportableSegmentTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 5 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-09` | `InformationAboutGainOnBargainPurchaseForEachReportableSegmentTable` | `ConsolidatedOrNonConsolidatedAxis` | `ConsolidatedMember` | 1 |
| `rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-09` | `InformationAboutGainOnBargainPurchaseForEachReportableSegmentTable` | `OperatingSegmentsAxis` | `EntityTotalMember` | 1 |
| `rol_BalanceSheet` | `BalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfIncome` | `StatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfChangesInEquity` | `StatementOfChangesInEquityTable` | `ComponentsOfEquityAxis` | `NetAssetsMember` | 13 |
| `rol_NotesBalanceSheet` | `NotesBalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_NotesStatementOfIncome` | `NotesStatementOfIncomeTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |

## 野村アセットマネジメント株式会社 (E12460) — S100VSHA
- 書類種別: 有価証券報告書（内国投資信託受益証券）－第40期(2024/10/11－2025/04/10)
- 提出日: 2025-06-27
- 提出者ラベル数: 8
- LineItem 総数: 164
- ディメンション付き LineItem 数: 74
- ユニーク軸数: 1

### ディメンション軸一覧

| # | 軸ローカル名 | 軸ラベル(ja) | 軸ラベル(en) | メンバー数 | LineItem数 | NS種別 |
|---|---|---|---|---|---|---|
| 1 | `ConsolidatedOrNonConsolidatedAxis` | 連結個別 [standard] | Consolidated or non-consolidated | 1 | 74 | standard_taxonomy (jppfs_cor) |

### Definition Linkbase 軸情報 (XBRL/PublicDoc/jpsps070000-asr-001_G04357-000_2025-04-10_01_2025-06-27_def.xml)

| role_uri (末尾) | Table | Axis | デフォルトメンバー | ドメインメンバー数 |
|---|---|---|---|---|
| `rol_BalanceSheet` | `BalanceSheetTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
| `rol_StatementOfIncomeAndRetainedEarnings` | `StatementOfIncomeAndRetainedEarningsTable` | `ConsolidatedOrNonConsolidatedAxis` | `(なし)` | 1 |
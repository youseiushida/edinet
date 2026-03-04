"""PL/BS/CF 本体の concept → CK マッピング。

``income_statement()`` / ``balance_sheet()`` / ``cash_flow_statement()`` が返す
``FinancialStatement.items`` の ``local_name`` を CK にマッピングする。

``summary_mappings.py`` が SummaryOfBusinessResults を扱うのに対し、
このモジュールは PL/BS/CF 本体の科目を扱う。

設計原則:
    - J-GAAP / IFRS の主要科目を網羅
    - normalize.py のレガシー概念リストを統合・拡張
    - タクソノミ追従が必要なデータをこのファイルに集約

マッチング戦略（防御的 2 段）:
    1. 辞書完全一致: ``_CONCEPT_INDEX.get(concept)``
    2. 正規化フォールバック: EDINET サフィックス剥離後に辞書引き

典型的な使用例::

    from edinet.financial.standards.statement_mappings import lookup_statement

    ck = lookup_statement("OperatingIncome")
    assert ck == "operating_income"

    # 正規化フォールバック（辞書に "GoodwillIFRS" がなくても動く）
    ck = lookup_statement("GoodwillIFRS")
    assert ck == "goodwill"
"""

from __future__ import annotations

from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "lookup_statement",
    "lookup_statement_exact",
    "lookup_statement_normalized",
    "normalize_concept",
    "statement_concepts",
]


# ---------------------------------------------------------------------------
# J-GAAP PL
# ---------------------------------------------------------------------------

_JGAAP_PL: dict[str, str] = {
    "NetSales": CK.REVENUE,
    "CostOfSales": CK.COST_OF_SALES,
    "GrossProfit": CK.GROSS_PROFIT,
    "SellingGeneralAndAdministrativeExpenses": CK.SGA_EXPENSES,
    "OperatingIncome": CK.OPERATING_INCOME,
    "NonOperatingIncome": CK.NON_OPERATING_INCOME,
    "NonOperatingExpenses": CK.NON_OPERATING_EXPENSES,
    "InterestIncomeNOI": CK.INTEREST_INCOME_PL,
    "InterestExpensesNOE": CK.INTEREST_EXPENSE_PL,
    "ResearchAndDevelopmentExpensesSGA": CK.RD_EXPENSES,
    "OrdinaryIncome": CK.ORDINARY_INCOME,
    "ExtraordinaryIncome": CK.EXTRAORDINARY_INCOME,
    "ExtraordinaryLoss": CK.EXTRAORDINARY_LOSS,
    "IncomeBeforeIncomeTaxes": CK.INCOME_BEFORE_TAX,
    "IncomeTaxes": CK.INCOME_TAXES,
    "IncomeTaxesDeferred": CK.INCOME_TAXES_DEFERRED,
    "ProfitLoss": CK.NET_INCOME,
    "ProfitLossAttributableToOwnersOfParent": CK.NET_INCOME_PARENT,
    "ProfitLossAttributableToNonControllingInterests": CK.NET_INCOME_MINORITY,
    "ComprehensiveIncome": CK.COMPREHENSIVE_INCOME,
    "ComprehensiveIncomeAttributableToOwnersOfTheParent": CK.COMPREHENSIVE_INCOME_PARENT,
    "ComprehensiveIncomeAttributableToNonControllingInterests": CK.COMPREHENSIVE_INCOME_MINORITY,
    # --- 収益認識基準（2021年〜）: NetSales を使わない企業向け ---
    "Revenue": CK.REVENUE,
    "RevenueFromContractsWithCustomers": CK.REVENUE,
    # --- 持分法投資損益（営業外収益/費用に計上） ---
    "EquityInEarningsOfAffiliatesNOI": CK.EQUITY_METHOD_INCOME,
    "EquityInLossesOfAffiliatesNOE": CK.EQUITY_METHOD_INCOME,
}

# ---------------------------------------------------------------------------
# J-GAAP BS
# ---------------------------------------------------------------------------

_JGAAP_BS: dict[str, str] = {
    "CashAndDeposits": CK.CASH_AND_DEPOSITS,
    "CashAndCashEquivalents": CK.CASH_AND_EQUIVALENTS,
    "NotesAndAccountsReceivableTrade": CK.TRADE_RECEIVABLES,
    # --- 収益認識基準改正（2021年〜）: 契約資産を含む売掛金 ---
    "NotesAndAccountsReceivableTradeAndContractAssets": CK.TRADE_RECEIVABLES,
    "AccountsReceivableTrade": CK.TRADE_RECEIVABLES,
    "AccountsReceivableTradeAndContractAssets": CK.TRADE_RECEIVABLES,
    # --- ネット表示（貸倒引当金控除後） ---
    "NotesAndAccountsReceivableTradeAndContractAssetsNet": CK.TRADE_RECEIVABLES,
    "NotesAndAccountsReceivableTradeNet": CK.TRADE_RECEIVABLES,
    "AccountsReceivableTradeAndContractAssetsNet": CK.TRADE_RECEIVABLES,
    "AccountsReceivableTradeNet": CK.TRADE_RECEIVABLES,
    "Inventories": CK.INVENTORIES,
    "CurrentAssets": CK.CURRENT_ASSETS,
    "NoncurrentAssets": CK.NONCURRENT_ASSETS,
    "PropertyPlantAndEquipment": CK.PPE,
    "IntangibleAssets": CK.INTANGIBLE_ASSETS,
    "Goodwill": CK.GOODWILL,
    "InvestmentsAndOtherAssets": CK.INVESTMENTS_AND_OTHER,
    "DeferredAssets": CK.DEFERRED_ASSETS,
    "Assets": CK.TOTAL_ASSETS,
    "NotesAndAccountsPayableTrade": CK.TRADE_PAYABLES,
    "AccountsPayableTrade": CK.TRADE_PAYABLES,
    "ShortTermLoansPayable": CK.SHORT_TERM_LOANS,
    "CurrentLiabilities": CK.CURRENT_LIABILITIES,
    "LongTermLoansPayable": CK.LONG_TERM_LOANS,
    "BondsPayable": CK.BONDS_PAYABLE,
    "ShortTermBondsPayable": CK.BONDS_PAYABLE,
    "NoncurrentLiabilities": CK.NONCURRENT_LIABILITIES,
    "Liabilities": CK.TOTAL_LIABILITIES,
    "CapitalStock": CK.CAPITAL_STOCK,
    "CapitalSurplus": CK.CAPITAL_SURPLUS,
    "RetainedEarnings": CK.RETAINED_EARNINGS,
    "SpecialReserve": CK.RETAINED_EARNINGS,
    "VoluntaryRetainedEarnings": CK.RETAINED_EARNINGS,
    "TreasuryStock": CK.TREASURY_STOCK,
    "ShareholdersEquity": CK.SHAREHOLDERS_EQUITY,
    "ValuationAndTranslationAdjustments": CK.OCI_ACCUMULATED,
    "SubscriptionRightsToShares": CK.STOCK_OPTIONS,
    "NonControllingInterests": CK.MINORITY_INTERESTS,
    "NetAssets": CK.NET_ASSETS,
    "LiabilitiesAndNetAssets": CK.LIABILITIES_AND_NET_ASSETS,
    "DeferredTaxAssets": CK.DEFERRED_TAX_ASSETS,
    "DeferredTaxLiabilities": CK.DEFERRED_TAX_LIABILITIES,
    "ProvisionForRetirementBenefits": CK.RETIREMENT_BENEFIT_LIABILITY,
    "NetDefinedBenefitLiability": CK.RETIREMENT_BENEFIT_LIABILITY,
}

# ---------------------------------------------------------------------------
# J-GAAP CF
# ---------------------------------------------------------------------------

_JGAAP_CF: dict[str, str] = {
    "DepreciationAndAmortizationOpeCF": CK.DEPRECIATION_CF,
    "ImpairmentLossOpeCF": CK.IMPAIRMENT_LOSS_CF,
    "AmortizationOfGoodwillOpeCF": CK.GOODWILL_AMORTIZATION_CF,
    "IncreaseDecreaseInAllowanceForDoubtfulAccountsOpeCF": CK.ALLOWANCE_DOUBTFUL_CHANGE_CF,
    "InterestAndDividendsIncomeOpeCF": CK.INTEREST_DIVIDEND_INCOME_CF,
    "InterestExpensesOpeCF": CK.INTEREST_EXPENSE_CF,
    "InterestExpensesPaidOpeCFFinCF": CK.INTEREST_EXPENSE_CF,
    "ForeignExchangeLossesGainsOpeCF": CK.FX_LOSS_GAIN_CF,
    "EquityInEarningsLossesOfAffiliatesOpeCF": CK.EQUITY_METHOD_CF,
    "LossGainOnSalesOfPropertyPlantAndEquipmentOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    # --- 有形固定資産除売却損益のバリエーション（jppfs_cor） ---
    "LossGainOnDisposalOfPropertyPlantAndEquipmentOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSalesAndRetirementOfPropertyPlantAndEquipmentOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSalesOfPropertyPlantAndEquipmentAndIntangibleAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnDisposalOfPropertyPlantAndEquipmentAndIntangibleAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSalesAndRetirementOfPropertyPlantAndEquipmentAndIntangibleAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnDisposalOfNoncurrentAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    # --- 無形資産・固定資産（広義）の売却・除却損益 ---
    "LossGainOnSalesAndRetirementOfIntangibleAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSalesAndRetirementOfNoncurrentAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSalesOfIntangibleAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSalesOfLandOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSalesOfNoncurrentAssetsOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "DecreaseIncreaseInNotesAndAccountsReceivableTradeOpeCF": CK.TRADE_RECEIVABLES_CHANGE_CF,
    # --- 収益認識基準改正: 契約資産を含む売掛金増減 ---
    "DecreaseIncreaseInAccountsReceivableTradeAndContractAssetsOpeCF": CK.TRADE_RECEIVABLES_CHANGE_CF,
    "DecreaseIncreaseInInventoriesOpeCF": CK.INVENTORIES_CHANGE_CF,
    "IncreaseDecreaseInNotesAndAccountsPayableTradeOpeCF": CK.TRADE_PAYABLES_CHANGE_CF,
    "OtherNetOpeCF": CK.OTHER_OPERATING_CF,
    "SubtotalOpeCF": CK.SUBTOTAL_OPERATING_CF,
    "IncomeTaxesPaidOpeCF": CK.INCOME_TAXES_PAID_CF,
    "NetCashProvidedByUsedInOperatingActivities": CK.OPERATING_CF,
    "PurchaseOfPropertyPlantAndEquipmentInvCF": CK.PURCHASE_PPE_CF,
    "PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssetsInvCF": CK.PURCHASE_PPE_CF,
    "ProceedsFromSalesOfPropertyPlantAndEquipmentInvCF": CK.PROCEEDS_PPE_SALE_CF,
    "ProceedsFromSalesOfPropertyPlantAndEquipmentAndIntangibleAssetsInvCF": CK.PROCEEDS_PPE_SALE_CF,
    # --- 固定資産（広義）・無形資産の売却収入 ---
    "ProceedsFromSalesOfIntangibleAssetsInvCF": CK.PROCEEDS_PPE_SALE_CF,
    "ProceedsFromSalesOfNoncurrentAssetsInvCF": CK.PROCEEDS_PPE_SALE_CF,
    # --- 固定資産取得支出（広義） ---
    "PurchaseOfNoncurrentAssetsInvCF": CK.PURCHASE_PPE_CF,
    "PurchaseOfInvestmentSecuritiesInvCF": CK.PURCHASE_INVESTMENT_SECURITIES_CF,
    "PurchaseOfShortTermAndLongTermInvestmentSecuritiesInvCF": CK.PURCHASE_INVESTMENT_SECURITIES_CF,
    "ProceedsFromSalesOfInvestmentSecuritiesInvCF": CK.PROCEEDS_INVESTMENT_SECURITIES_CF,
    # --- 投資有価証券の売却＋償還バリエーション ---
    "ProceedsFromRedemptionOfInvestmentSecuritiesInvCF": CK.PROCEEDS_INVESTMENT_SECURITIES_CF,
    "ProceedsFromSalesAndRedemptionOfInvestmentSecuritiesInvCF": CK.PROCEEDS_INVESTMENT_SECURITIES_CF,
    "ProceedsFromSalesAndRedemptionOfSecuritiesInvCF": CK.PROCEEDS_INVESTMENT_SECURITIES_CF,
    "ProceedsFromSalesOfShortTermAndLongTermInvestmentSecuritiesInvCF": CK.PROCEEDS_INVESTMENT_SECURITIES_CF,
    "PaymentsOfLoansReceivableInvCF": CK.LOANS_PAID_CF,
    "PaymentsOfLongTermLoansReceivableInvCF": CK.LOANS_PAID_CF,
    "PaymentsOfShortTermLoansReceivableInvCF": CK.LOANS_PAID_CF,
    "CollectionOfLoansReceivableInvCF": CK.LOANS_COLLECTED_CF,
    "OtherNetInvCF": CK.OTHER_INVESTING_CF,
    "NetCashProvidedByUsedInInvestmentActivities": CK.INVESTING_CF,
    "ProceedsFromLongTermLoansPayableFinCF": CK.PROCEEDS_LONG_TERM_LOANS_CF,
    "RepaymentOfLongTermLoansPayableFinCF": CK.REPAYMENT_LONG_TERM_LOANS_CF,
    "ProceedsFromIssuanceOfBondsFinCF": CK.PROCEEDS_BONDS_CF,
    "ProceedsFromIssuanceOfBondsWithSubscriptionRightsToSharesFinCF": CK.PROCEEDS_BONDS_CF,
    "RedemptionOfBondsFinCF": CK.REDEMPTION_BONDS_CF,
    "RedemptionOfConvertibleBondsFinCF": CK.REDEMPTION_BONDS_CF,
    "RedemptionOfShortTermBondsFinCF": CK.REDEMPTION_BONDS_CF,
    "PurchaseOfTreasuryStockFinCF": CK.PURCHASE_TREASURY_STOCK_CF,
    "CashDividendsPaidFinCF": CK.DIVIDENDS_PAID_CF,
    "OtherNetFinCF": CK.OTHER_FINANCING_CF,
    "NetCashProvidedByUsedInFinancingActivities": CK.FINANCING_CF,
    "EffectOfExchangeRateChangeOnCashAndCashEquivalents": CK.FX_EFFECT_ON_CASH,
    "NetIncreaseDecreaseInCashAndCashEquivalents": CK.NET_CHANGE_IN_CASH,
    "IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeOfScopeOfConsolidationCCE": CK.CONSOLIDATION_SCOPE_CHANGE_CASH,
    # --- 連結範囲変動の細分化バリエーション ---
    "IncreaseInCashAndCashEquivalentsFromNewlyConsolidatedSubsidiaryCCE": CK.CONSOLIDATION_SCOPE_CHANGE_CASH,
    "IncreaseInCashAndCashEquivalentsResultingFromMergerCCE": CK.CONSOLIDATION_SCOPE_CHANGE_CASH,
    "IncreaseInCashAndCashEquivalentsResultingFromMergerWithUnconsolidatedSubsidiariesCCE": CK.CONSOLIDATION_SCOPE_CHANGE_CASH,
    # --- 株式報酬費用(CF調整項目) ---
    "ShareBasedCompensationExpensesOpeCF": CK.SBC_CF,
}

# ---------------------------------------------------------------------------
# IFRS PL
# ---------------------------------------------------------------------------

_IFRS_PL: dict[str, str] = {
    "NetSalesIFRS": CK.REVENUE,
    "RevenueIFRS": CK.REVENUE,
    # --- タクソノミ改定で追加された数値サフィックス付きバリエーション ---
    "Revenue2IFRS": CK.REVENUE,
    "CostOfSalesIFRS": CK.COST_OF_SALES,
    "GrossProfitIFRS": CK.GROSS_PROFIT,
    "SellingGeneralAndAdministrativeExpensesIFRS": CK.SGA_EXPENSES,
    "GeneralAndAdministrativeExpensesIFRS": CK.SGA_EXPENSES,
    "OtherIncomeIFRS": CK.OTHER_INCOME_IFRS,
    "OtherExpensesIFRS": CK.OTHER_EXPENSES_IFRS,
    "OperatingProfitLossIFRS": CK.OPERATING_INCOME,
    "FinanceIncomeIFRS": CK.FINANCE_INCOME,
    "FinanceCostsIFRS": CK.FINANCE_COSTS,
    "ShareOfProfitLossOfInvestmentsAccountedForUsingEquityMethodIFRS": CK.EQUITY_METHOD_INCOME_IFRS,
    "ProfitLossBeforeTaxIFRS": CK.INCOME_BEFORE_TAX,
    "IncomeTaxExpenseIFRS": CK.INCOME_TAXES,
    "ProfitLossIFRS": CK.NET_INCOME,
    "ProfitLossAttributableToOwnersOfParentIFRS": CK.NET_INCOME_PARENT,
    "ProfitLossAttributableToNonControllingInterestsIFRS": CK.NET_INCOME_MINORITY,
    "ComprehensiveIncomeAttributableToOwnersOfParentIFRS": CK.COMPREHENSIVE_INCOME_PARENT,
    "ComprehensiveIncomeAttributableToNonControllingInterestsIFRS": CK.COMPREHENSIVE_INCOME_MINORITY,
    # --- IFRS PL 追加概念 ---
    "ProfitLossFromContinuingOperationsIFRS": CK.CONTINUING_OPERATIONS_INCOME,
    "InterestIncomeIFRS": CK.INTEREST_INCOME_PL,
    "InterestExpensesIFRS": CK.INTEREST_EXPENSE_PL,
    # --- IFRS PL 配当収益 ---
    "DividendIncomeIFRS": CK.DIVIDEND_INCOME,
}

# ---------------------------------------------------------------------------
# IFRS BS
# ---------------------------------------------------------------------------

_IFRS_BS: dict[str, str] = {
    "CashAndCashEquivalentsIFRS": CK.CASH_AND_EQUIVALENTS,
    "TradeAndOtherReceivablesCAIFRS": CK.TRADE_RECEIVABLES,
    "InventoriesCAIFRS": CK.INVENTORIES,
    "CurrentAssetsIFRS": CK.CURRENT_ASSETS,
    "NonCurrentAssetsIFRS": CK.NONCURRENT_ASSETS,
    "PropertyPlantAndEquipmentIFRS": CK.PPE,
    "IntangibleAssetsIFRS": CK.INTANGIBLE_ASSETS,
    "GoodwillIFRS": CK.GOODWILL,
    "AssetsIFRS": CK.TOTAL_ASSETS,
    "TradeAndOtherPayablesCLIFRS": CK.TRADE_PAYABLES,
    "BondsPayableLiabilitiesIFRS": CK.BONDS_PAYABLE,
    # --- IFRS 借入金（short/long） ---
    "BorrowingsCLIFRS": CK.SHORT_TERM_LOANS,
    "CurrentPortionOfLongTermBorrowingsCLIFRS": CK.SHORT_TERM_LOANS,
    "BorrowingsNCLIFRS": CK.LONG_TERM_LOANS,
    "LongTermDebtNCLIFRS": CK.LONG_TERM_LOANS,
    "TotalCurrentLiabilitiesIFRS": CK.CURRENT_LIABILITIES,
    "NonCurrentLabilitiesIFRS": CK.NONCURRENT_LIABILITIES,
    "LiabilitiesIFRS": CK.TOTAL_LIABILITIES,
    "ShareCapitalIFRS": CK.CAPITAL_STOCK,
    "CapitalSurplusIFRS": CK.CAPITAL_SURPLUS,
    "RetainedEarningsIFRS": CK.RETAINED_EARNINGS,
    "TreasurySharesIFRS": CK.TREASURY_STOCK,
    "EquityAttributableToOwnersOfParentIFRS": CK.EQUITY_PARENT,
    "NonControllingInterestsIFRS": CK.MINORITY_INTERESTS,
    "EquityIFRS": CK.NET_ASSETS,
    # --- Trade Receivables: 数値サフィックス・ポジション違い ---
    "TradeAndOtherReceivables2CAIFRS": CK.TRADE_RECEIVABLES,
    "TradeAndOtherReceivables3CAIFRS": CK.TRADE_RECEIVABLES,
    "TradeAndOtherReceivablesAssetsIFRS": CK.TRADE_RECEIVABLES,
    "TradeAndOtherReceivables2AssetsIFRS": CK.TRADE_RECEIVABLES,
    "TradeAndOtherReceivables3AssetsIFRS": CK.TRADE_RECEIVABLES,
    "TradeAndOtherReceivablesNCAIFRS": CK.TRADE_RECEIVABLES,
    # --- Trade Receivables (Other 含まず): IFRS 独自概念 ---
    "TradeReceivablesCAIFRS": CK.TRADE_RECEIVABLES,
    "TradeReceivables2CAIFRS": CK.TRADE_RECEIVABLES,
    "TradeReceivablesAssetsIFRS": CK.TRADE_RECEIVABLES,
    "TradeReceivables2AssetsIFRS": CK.TRADE_RECEIVABLES,
    # --- Trade Payables: 数値サフィックス・ポジション違い ---
    "TradeAndOtherPayables2CLIFRS": CK.TRADE_PAYABLES,
    "TradeAndOtherPayables3CLIFRS": CK.TRADE_PAYABLES,
    "TradeAndOtherPayablesNCLIFRS": CK.TRADE_PAYABLES,
    "TradeAndOtherPayables2NCLIFRS": CK.TRADE_PAYABLES,
    "TradeAndOtherPayablesLiabilitiesIFRS": CK.TRADE_PAYABLES,
    # --- Trade Payables (Other 含まず): IFRS 独自概念 ---
    "TradePayablesCLIFRS": CK.TRADE_PAYABLES,
    "TradePayables2CLIFRS": CK.TRADE_PAYABLES,
    "TradePayables3CLIFRS": CK.TRADE_PAYABLES,
    "TradePayablesLiabilitiesIFRS": CK.TRADE_PAYABLES,
    "TradePayablesNCLIFRS": CK.TRADE_PAYABLES,
    # --- その他 IFRS BS ---
    "OtherComponentsOfEquityIFRS": CK.OCI_ACCUMULATED,
    "AccumulatedOtherComprehensiveIncomeIFRS": CK.OCI_ACCUMULATED,
    "LiabilitiesAndEquityIFRS": CK.LIABILITIES_AND_NET_ASSETS,
    "DeferredTaxAssetsIFRS": CK.DEFERRED_TAX_ASSETS,
    "DeferredTaxLiabilitiesIFRS": CK.DEFERRED_TAX_LIABILITIES,
    "RetirementBenefitLiabilityNCLIFRS": CK.RETIREMENT_BENEFIT_LIABILITY,
    "DefinedBenefitLiabilityNCLIFRS": CK.RETIREMENT_BENEFIT_LIABILITY,
    "RetirementBenefitLiabilityLiabilitiesIFRS": CK.RETIREMENT_BENEFIT_LIABILITY,
    # --- IFRS 有利子負債（社債及び借入金 集約） ---
    "BondsAndBorrowingsCLIFRS": CK.INTEREST_BEARING_DEBT_CL,
    "BondsAndBorrowingsNCLIFRS": CK.INTEREST_BEARING_DEBT_NCL,
    "BondsAndBorrowingsLiabilitiesIFRS": CK.INTEREST_BEARING_DEBT,
    "BorrowingsLiabilitiesIFRS": CK.INTEREST_BEARING_DEBT,
    # --- IFRS リース負債（IFRS 16） ---
    "LeaseLiabilitiesCLIFRS": CK.LEASE_LIABILITIES_CL,
    "LeaseLiabilitiesNCLIFRS": CK.LEASE_LIABILITIES_NCL,
    "LeaseLiabilitiesLiabilitiesIFRS": CK.LEASE_LIABILITIES,
    # --- IFRS 投資不動産 / 持分法投資 ---
    "InvestmentPropertyIFRS": CK.INVESTMENT_PROPERTY,
    "InvestmentsAccountedForUsingEquityMethodIFRS": CK.EQUITY_METHOD_INVESTMENTS,
}

# ---------------------------------------------------------------------------
# IFRS CF
# ---------------------------------------------------------------------------

_IFRS_CF: dict[str, str] = {
    "DepreciationAndAmortizationOpeCFIFRS": CK.DEPRECIATION_CF,
    "ImpairmentLossesReversalOfImpairmentLossesOpeCFIFRS": CK.IMPAIRMENT_LOSS_CF,
    "ShareOfLossProfitOfInvestmentsAccountedForUsingEquityMethodOpeCFIFRS": CK.EQUITY_METHOD_CF,
    "DecreaseIncreaseInTradeAndOtherReceivablesOpeCFIFRS": CK.TRADE_RECEIVABLES_CHANGE_CF,
    "DecreaseIncreaseInInventoriesOpeCFIFRS": CK.INVENTORIES_CHANGE_CF,
    "IncreaseDecreaseInTradeAndOtherPayablesOpeCFIFRS": CK.TRADE_PAYABLES_CHANGE_CF,
    "SubtotalOpeCFIFRS": CK.SUBTOTAL_OPERATING_CF,
    "IncomeTaxesPaidOpeCFIFRS": CK.INCOME_TAXES_PAID_CF,
    "NetCashProvidedByUsedInOperatingActivitiesIFRS": CK.OPERATING_CF,
    "PurchaseOfPropertyPlantAndEquipmentInvCFIFRS": CK.PURCHASE_PPE_CF,
    "NetCashProvidedByUsedInInvestingActivitiesIFRS": CK.INVESTING_CF,
    "RepaymentsOfLongTermBorrowingsFinCFIFRS": CK.REPAYMENT_LONG_TERM_LOANS_CF,
    "DividendsPaidFinCFIFRS": CK.DIVIDENDS_PAID_CF,
    "DividendsPaidToOwnersOfParentFinCFIFRS": CK.DIVIDENDS_PAID_CF,
    "NetCashProvidedByUsedInFinancingActivitiesIFRS": CK.FINANCING_CF,
    # --- 営業CF: J-GAAP と命名が異なる IFRS 概念 ---
    "ForeignExchangeLossGainOpeCFIFRS": CK.FX_LOSS_GAIN_CF,
    "InterestAndDividendIncomeOpeCFIFRS": CK.INTEREST_DIVIDEND_INCOME_CF,
    "InterestAndDividendsReceivedOpeCFIFRS": CK.INTEREST_DIVIDEND_INCOME_CF,
    "InterestReceivedOpeCFIFRS": CK.INTEREST_DIVIDEND_INCOME_CF,
    # --- IFRS 利息支払（営業CF/財務CF） ---
    "InterestPaidOpeCFIFRS": CK.INTEREST_EXPENSE_CF,
    "InterestPaidFinCFIFRS": CK.INTEREST_EXPENSE_CF,
    "LossGainOnSaleOfPropertyPlantAndEquipmentOpeCFIFRS": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSaleOfFixedAssetsOpeCFIFRS": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSaleAndRetirementOfFixedAssetsOpeCFIFRS": CK.PPE_SALE_LOSS_GAIN_CF,
    "LossGainOnSaleAndRetirementOfPropertyPlantAndEquipmentAndIntangibleAssetsOpeCFIFRS": CK.PPE_SALE_LOSS_GAIN_CF,
    # --- 投資CF: IFRS 独自命名（Sale 単数形） ---
    "ProceedsFromSaleOfPropertyPlantAndEquipmentInvCFIFRS": CK.PROCEEDS_PPE_SALE_CF,
    "ProceedsFromSaleOfPropertyPlantAndEquipmentAndIntangibleAssetsInvCFIFRS": CK.PROCEEDS_PPE_SALE_CF,
    "PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssetsInvCFIFRS": CK.PURCHASE_PPE_CF,
    "ProceedsFromSaleOfInvestmentSecuritiesInvCFIFRS": CK.PROCEEDS_INVESTMENT_SECURITIES_CF,
    # --- IFRS 貸付金支出 ---
    "PaymentsForLoansReceivableInvCFIFRS": CK.LOANS_PAID_CF,
    # --- 財務CF: J-GAAP と命名が異なる IFRS 概念 ---
    "ProceedsFromLongTermBorrowingsFinCFIFRS": CK.PROCEEDS_LONG_TERM_LOANS_CF,
    "PaymentsForPurchaseOfTreasurySharesFinCFIFRS": CK.PURCHASE_TREASURY_STOCK_CF,
    # --- Trade Receivables/Payables CF 変動: 数値サフィックスおよび Other 無し系 ---
    "DecreaseIncreaseInTradeAndOtherReceivables2OpeCFIFRS": CK.TRADE_RECEIVABLES_CHANGE_CF,
    "DecreaseIncreaseInTradeAndOtherReceivables3OpeCFIFRS": CK.TRADE_RECEIVABLES_CHANGE_CF,
    "DecreaseIncreaseInTradeReceivablesOpeCFIFRS": CK.TRADE_RECEIVABLES_CHANGE_CF,
    "DecreaseIncreaseInTradeReceivables2OpeCFIFRS": CK.TRADE_RECEIVABLES_CHANGE_CF,
    "IncreaseDecreaseInTradeAndOtherPayables2OpeCFIFRS": CK.TRADE_PAYABLES_CHANGE_CF,
    "IncreaseDecreaseInTradeAndOtherPayables3OpeCFIFRS": CK.TRADE_PAYABLES_CHANGE_CF,
    "IncreaseDecreaseInTradePayablesOpeCFIFRS": CK.TRADE_PAYABLES_CHANGE_CF,
    "IncreaseDecreaseInTradePayables2OpeCFIFRS": CK.TRADE_PAYABLES_CHANGE_CF,
    "IncreaseDecreaseInTradePayables3OpeCFIFRS": CK.TRADE_PAYABLES_CHANGE_CF,
    "EffectOfExchangeRateChangesOnCashAndCashEquivalentsIFRS": CK.FX_EFFECT_ON_CASH,
    "NetIncreaseDecreaseInCashAndCashEquivalentsIFRS": CK.NET_CHANGE_IN_CASH,
    # --- IFRS 配当金受取・非支配持分・短期借入金 ---
    "DividendIncomeOpeCFIFRS": CK.DIVIDENDS_RECEIVED_CF,
    "DividendsReceivedOpeCFIFRS": CK.DIVIDENDS_RECEIVED_CF,
    "DividendsPaidToNonControllingInterestsFinCFIFRS": CK.DIVIDENDS_PAID_NCI_CF,
    "CapitalContributionFromNonControllingInterestsFinCFIFRS": CK.NCI_CAPITAL_CONTRIBUTION_CF,
    "NetIncreaseDecreaseInShortTermBorrowingsFinCFIFRS": CK.SHORT_TERM_BORROWINGS_NET_CF,
}


# ---------------------------------------------------------------------------
# 注記・その他（PL/BS/CF に分類されない概念）
# ---------------------------------------------------------------------------

_OTHER: dict[str, str] = {
    "NumberOfEmployees": CK.EMPLOYEES,
    # --- 研究開発費（有報 研究開発活動セクション、jpcrp_cor） ---
    "ResearchAndDevelopmentExpensesResearchAndDevelopmentActivities": CK.RD_EXPENSES,
    # --- ESG / 人的資本（2023年有報義務化、jpcrp_cor） ---
    "RatioOfFemaleEmployeesInManagerialPositionsMetricsOfReportingCompany": CK.FEMALE_MANAGERS_RATIO,
    "AllEmployeesDifferencesInWagesBetweenMaleAndFemaleEmployeesMetricsOfReportingCompany": CK.GENDER_PAY_GAP,
    "AllEmployeesCalculatedBasedOnProvisionsOfArticle714Item1OfOrdinanceForEnforcementOfActOnChildcareLeaveCaregiverLeaveAndOtherMeasuresForTheWelfareOfWorkersCaringForChildrenOrOtherFamilyMembersRatioOfMaleEmployeesTakingChildcareLeaveMetricsOfReportingCompany": CK.MALE_CHILDCARE_LEAVE_RATE,
    "AllEmployeesCalculatedBasedOnProvisionsOfArticle714Item2OfOrdinanceForEnforcementOfActOnChildcareLeaveCaregiverLeaveAndOtherMeasuresForTheWelfareOfWorkersCaringForChildrenOrOtherFamilyMembersRatioOfMaleEmployeesTakingChildcareLeaveMetricsOfReportingCompany": CK.MALE_CHILDCARE_LEAVE_RATE,
    "AllEmployeesCalculatedBasedOnProvisionsOfActOnPromotionOfWomensActiveEngagementInProfessionalLifeRatioOfMaleEmployeesTakingChildcareLeaveMetricsOfReportingCompany": CK.MALE_CHILDCARE_LEAVE_RATE,
    "RatioOfFemaleDirectorsAndOtherOfficers": CK.FEMALE_DIRECTORS_RATIO,
    # --- ガバナンス（jpcrp_cor） ---
    "AuditFeesTotal": CK.AUDIT_FEES,
    "NumberOfIssuesSharesOtherThanThoseNotListedInvestmentSharesHeldForPurposesOtherThanPureInvestmentReportingCompany": CK.CROSS_SHAREHOLDINGS_COUNT,
    "CarryingAmountSharesOtherThanThoseNotListedInvestmentSharesHeldForPurposesOtherThanPureInvestmentReportingCompany": CK.CROSS_SHAREHOLDINGS_AMOUNT,
    # --- 持分法投資損益（jpcrp_cor） ---
    "EquityInEarningsLossesOfAffiliates": CK.EQUITY_METHOD_INCOME,
    # --- のれん相殺前（jpcrp_cor） ---
    "GoodwillBeforeOffsetting": CK.GOODWILL,
    # --- 法人税等（jpcrp版） ---
    "IncomeTaxExpense": CK.INCOME_TAXES,
    # --- 研究開発費（販管費+製造原価に含まれる版、jpcrp_cor） ---
    "ResearchAndDevelopmentExpensesIncludedInGeneralAndAdministrativeExpensesAndManufacturingCostForCurrentPeriod": CK.RD_EXPENSES,
    # --- 業種別 SGA（ガス業・電気事業附帯事業等） ---
    "SellingGeneralAndAdministrativeExpensesGAS": CK.SGA_EXPENSES,
    "SellingGeneralAndAdministrativeExpensesOEDevelopment": CK.SGA_EXPENSES,
    "SellingGeneralAndAdministrativeExpensesOEIncidental": CK.SGA_EXPENSES,
    "SellingGeneralAndAdministrativeExpensesOEOther": CK.SGA_EXPENSES,
    "SellingGeneralAndAdministrativeExpensesOERealEstate": CK.SGA_EXPENSES,
    "SellingGeneralAndAdministrativeExpensesOERelated": CK.SGA_EXPENSES,
    "SellingGeneralAndAdministrativeExpensesOESideLine": CK.SGA_EXPENSES,
    # --- 業種別概念（銀行・保険・学校法人・医療法人・投資法人） ---
    "DepositsLiabilitiesBNK": CK.DEPOSITS,
    "NetPremiumsWrittenOIINS": CK.NET_PREMIUMS_WRITTEN,
    "ShareholdersEquityShinkinBNK": CK.SHAREHOLDERS_EQUITY,
    "SubscriptionRightsToSharesINV": CK.STOCK_OPTIONS,
    "InterestAndDividendsIncomeOpeCFINSNonlife": CK.INTEREST_DIVIDEND_INCOME_CF,
    "InterestAndDividendsIncomeReceivedOpeCFINS": CK.INTEREST_DIVIDEND_INCOME_CF,
    "OtherNetOpeCFINS": CK.OTHER_OPERATING_CF,
    "OtherNetInvCFINS": CK.OTHER_INVESTING_CF,
    "OtherNetFinCFINS": CK.OTHER_FINANCING_CF,
    "NonOperatingIncomeEDU": CK.NON_OPERATING_INCOME,
    "NonOperatingIncomeMED": CK.NON_OPERATING_INCOME,
    "NonOperatingExpensesEDU": CK.NON_OPERATING_EXPENSES,
    "NonOperatingExpensesMED": CK.NON_OPERATING_EXPENSES,
    "NetCashProvidedByUsedInOperatingActivitiesEDU": CK.OPERATING_CF,
    "NetCashProvidedByUsedInOperatingActivitiesMED": CK.OPERATING_CF,
    "NetCashProvidedByUsedInFacilitiesMaintenanceAndInvestmentActivitiesEDU": CK.INVESTING_CF,
    # --- セグメント情報 / その他 ---
    "IncreaseInPropertyPlantAndEquipmentAndIntangibleAssets": CK.CAPEX,
    "WriteDownsOfInventories": CK.INVENTORY_WRITEDOWNS,
}

# ---------------------------------------------------------------------------
# 統合インデックス
# ---------------------------------------------------------------------------

_CONCEPT_INDEX: dict[str, str] = {
    **_JGAAP_PL, **_JGAAP_BS, **_JGAAP_CF,
    **_IFRS_PL, **_IFRS_BS, **_IFRS_CF,
    **_OTHER,
}

# レガシーフォールバック用: 基準×諸表 → 概念名順序タプル
_LEGACY_ORDER: dict[str, tuple[str, ...]] = {
    "jgaap_pl": tuple(_JGAAP_PL.keys()),
    "jgaap_bs": tuple(_JGAAP_BS.keys()),
    "jgaap_cf": tuple(_JGAAP_CF.keys()),
    "ifrs_pl": tuple(_IFRS_PL.keys()),
    "ifrs_bs": tuple(_IFRS_BS.keys()),
    "ifrs_cf": tuple(_IFRS_CF.keys()),
}


# ---------------------------------------------------------------------------
# 正規化レイヤー（EDINET サフィックス剥離）
# ---------------------------------------------------------------------------
# edinet_mcp の _strip_edinet_suffixes() を参考に実装。
# 長いサフィックスを先にマッチし、ポジションタグを 2 段目で剥離する。
# OpeCF / InvCF / FinCF は CF 科目名の一部なので剥離対象外。

_EDINET_SUFFIXES: tuple[str, ...] = (
    "IFRSSummaryOfBusinessResults",
    "JGAAPSummaryOfBusinessResults",
    "USGAAPSummaryOfBusinessResults",
    "SummaryOfBusinessResults",
    "IFRSKeyFinancialData",
    "KeyFinancialData",
    "IFRS",
    "JGAAP",
    "USGAAP",
)

_POSITION_TAGS: tuple[str, ...] = ("NCA", "NCL", "CA", "CL", "SS")


def normalize_concept(name: str) -> str:
    """EDINET 固有のサフィックスを剥離して基底概念名を返す。

    2 段階で剥離する:
        1. 会計基準サフィックス（``IFRS``, ``SummaryOfBusinessResults`` 等）
        2. BS ポジションタグ（``CA``, ``CL``, ``NCA``, ``NCL``, ``SS``）

    Args:
        name: XBRL element の ``local_name``。

    Returns:
        剥離後の基底概念名。サフィックスがなければそのまま返す。

    Example:
        >>> normalize_concept("GoodwillIFRS")
        'Goodwill'
        >>> normalize_concept("InventoriesCAIFRS")
        'Inventories'
        >>> normalize_concept("DepreciationAndAmortizationOpeCFIFRS")
        'DepreciationAndAmortizationOpeCF'
    """
    for suffix in _EDINET_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[: -len(suffix)]
            break

    for tag in _POSITION_TAGS:
        if name.endswith(tag) and len(name) > len(tag):
            name = name[: -len(tag)]
            break

    return name


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def lookup_statement_exact(concept: str) -> str | None:
    """辞書完全一致のみで CK を返す（Layer 1）。

    Args:
        concept: ``local_name``。

    Returns:
        正規化キー文字列。未登録なら ``None``。
    """
    return _CONCEPT_INDEX.get(concept)


def lookup_statement_normalized(concept: str) -> str | None:
    """正規化フォールバックのみで CK を返す（Layer 2）。

    サフィックス剥離後に辞書引きする。
    完全一致で引けるものはここでは返さない（Layer 1 で処理済みのため）。

    Args:
        concept: ``local_name``。

    Returns:
        正規化キー文字列。剥離しても未登録なら ``None``。
    """
    normalized = normalize_concept(concept)
    if normalized != concept:
        return _CONCEPT_INDEX.get(normalized)
    return None


def lookup_statement(concept: str) -> str | None:
    """PL/BS/CF 本体の concept から CK を返す。

    防御的 2 段マッチング:
        1. 辞書完全一致（信頼度 100%）
        2. 正規化フォールバック（サフィックス剥離後に辞書引き）

    単一の concept を解決する場合に使用する。
    ``_items`` 全体を走査する場合は信頼度を維持するため
    ``lookup_statement_exact`` → ``lookup_statement_normalized``
    の 2 パスで使い分けること。

    Args:
        concept: ``local_name``（例: ``"OperatingIncome"``）。

    Returns:
        正規化キー文字列。登録されていない concept の場合は ``None``。
    """
    return lookup_statement_exact(concept) or lookup_statement_normalized(concept)


def statement_concepts(standard: str, statement_type: str) -> tuple[str, ...]:
    """指定基準・諸表種別の概念名タプルを返す（表示順序順）。

    Args:
        standard: ``"jgaap"`` / ``"ifrs"``。
        statement_type: ``"pl"`` / ``"bs"`` / ``"cf"``。

    Returns:
        概念名のタプル。未知の組み合わせは空タプル。
    """
    key = f"{standard}_{statement_type}"
    return _LEGACY_ORDER.get(key, ())

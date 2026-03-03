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
}

# ---------------------------------------------------------------------------
# J-GAAP BS
# ---------------------------------------------------------------------------

_JGAAP_BS: dict[str, str] = {
    "CashAndDeposits": CK.CASH_AND_DEPOSITS,
    "NotesAndAccountsReceivableTrade": CK.TRADE_RECEIVABLES,
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
    "ShortTermLoansPayable": CK.SHORT_TERM_LOANS,
    "CurrentLiabilities": CK.CURRENT_LIABILITIES,
    "LongTermLoansPayable": CK.LONG_TERM_LOANS,
    "BondsPayable": CK.BONDS_PAYABLE,
    "NoncurrentLiabilities": CK.NONCURRENT_LIABILITIES,
    "Liabilities": CK.TOTAL_LIABILITIES,
    "CapitalStock": CK.CAPITAL_STOCK,
    "CapitalSurplus": CK.CAPITAL_SURPLUS,
    "RetainedEarnings": CK.RETAINED_EARNINGS,
    "TreasuryStock": CK.TREASURY_STOCK,
    "ShareholdersEquity": CK.SHAREHOLDERS_EQUITY,
    "ValuationAndTranslationAdjustments": CK.OCI_ACCUMULATED,
    "SubscriptionRightsToShares": CK.STOCK_OPTIONS,
    "NonControllingInterests": CK.MINORITY_INTERESTS,
    "NetAssets": CK.NET_ASSETS,
    "LiabilitiesAndNetAssets": CK.LIABILITIES_AND_NET_ASSETS,
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
    "ForeignExchangeLossesGainsOpeCF": CK.FX_LOSS_GAIN_CF,
    "EquityInEarningsLossesOfAffiliatesOpeCF": CK.EQUITY_METHOD_CF,
    "LossGainOnSalesOfPropertyPlantAndEquipmentOpeCF": CK.PPE_SALE_LOSS_GAIN_CF,
    "DecreaseIncreaseInNotesAndAccountsReceivableTradeOpeCF": CK.TRADE_RECEIVABLES_CHANGE_CF,
    "DecreaseIncreaseInInventoriesOpeCF": CK.INVENTORIES_CHANGE_CF,
    "IncreaseDecreaseInNotesAndAccountsPayableTradeOpeCF": CK.TRADE_PAYABLES_CHANGE_CF,
    "OtherNetOpeCF": CK.OTHER_OPERATING_CF,
    "SubtotalOpeCF": CK.SUBTOTAL_OPERATING_CF,
    "IncomeTaxesPaidOpeCF": CK.INCOME_TAXES_PAID_CF,
    "NetCashProvidedByUsedInOperatingActivities": CK.OPERATING_CF,
    "PurchaseOfPropertyPlantAndEquipmentInvCF": CK.PURCHASE_PPE_CF,
    "ProceedsFromSalesOfPropertyPlantAndEquipmentInvCF": CK.PROCEEDS_PPE_SALE_CF,
    "PurchaseOfInvestmentSecuritiesInvCF": CK.PURCHASE_INVESTMENT_SECURITIES_CF,
    "ProceedsFromSalesOfInvestmentSecuritiesInvCF": CK.PROCEEDS_INVESTMENT_SECURITIES_CF,
    "PaymentsOfLoansReceivableInvCF": CK.LOANS_PAID_CF,
    "CollectionOfLoansReceivableInvCF": CK.LOANS_COLLECTED_CF,
    "OtherNetInvCF": CK.OTHER_INVESTING_CF,
    "NetCashProvidedByUsedInInvestmentActivities": CK.INVESTING_CF,
    "ProceedsFromLongTermLoansPayableFinCF": CK.PROCEEDS_LONG_TERM_LOANS_CF,
    "RepaymentOfLongTermLoansPayableFinCF": CK.REPAYMENT_LONG_TERM_LOANS_CF,
    "ProceedsFromIssuanceOfBondsFinCF": CK.PROCEEDS_BONDS_CF,
    "RedemptionOfBondsFinCF": CK.REDEMPTION_BONDS_CF,
    "PurchaseOfTreasuryStockFinCF": CK.PURCHASE_TREASURY_STOCK_CF,
    "CashDividendsPaidFinCF": CK.DIVIDENDS_PAID_CF,
    "OtherNetFinCF": CK.OTHER_FINANCING_CF,
    "NetCashProvidedByUsedInFinancingActivities": CK.FINANCING_CF,
    "EffectOfExchangeRateChangeOnCashAndCashEquivalents": CK.FX_EFFECT_ON_CASH,
    "NetIncreaseDecreaseInCashAndCashEquivalents": CK.NET_CHANGE_IN_CASH,
    "IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeOfScopeOfConsolidationCCE": CK.CONSOLIDATION_SCOPE_CHANGE_CASH,
}

# ---------------------------------------------------------------------------
# IFRS PL
# ---------------------------------------------------------------------------

_IFRS_PL: dict[str, str] = {
    "NetSalesIFRS": CK.REVENUE,
    "RevenueIFRS": CK.REVENUE,
    "CostOfSalesIFRS": CK.COST_OF_SALES,
    "GrossProfitIFRS": CK.GROSS_PROFIT,
    "SellingGeneralAndAdministrativeExpensesIFRS": CK.SGA_EXPENSES,
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
    "NetCashProvidedByUsedInFinancingActivitiesIFRS": CK.FINANCING_CF,
    "EffectOfExchangeRateChangesOnCashAndCashEquivalentsIFRS": CK.FX_EFFECT_ON_CASH,
    "NetIncreaseDecreaseInCashAndCashEquivalentsIFRS": CK.NET_CHANGE_IN_CASH,
}


# ---------------------------------------------------------------------------
# 統合インデックス
# ---------------------------------------------------------------------------

_CONCEPT_INDEX: dict[str, str] = {
    **_JGAAP_PL, **_JGAAP_BS, **_JGAAP_CF,
    **_IFRS_PL, **_IFRS_BS, **_IFRS_CF,
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

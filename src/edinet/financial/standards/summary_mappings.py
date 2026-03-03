"""SummaryOfBusinessResults の正規化キーマッピング。

jpcrp_cor XSD に定義された SummaryOfBusinessResults concept を
CK（canonical key）にマッピングする。extract_values() の唯一のデータソース。

設計原則:
    - **提出者独自 concept ゼロ**: 全 concept が jpcrp_cor XSD に実在
    - **XSD 実在テスト 100%**: _FILER_SPECIFIC_CONCEPTS 除外リスト不要
    - **4 基準統合**: J-GAAP / IFRS / US-GAAP / JMIS を 1 ファイルで管理

典型的な使用例::

    from edinet.financial.standards.summary_mappings import lookup_summary

    ck = lookup_summary("NetSalesSummaryOfBusinessResults")
    assert ck == "revenue"
"""

from __future__ import annotations

from dataclasses import dataclass

from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "SummaryMapping",
    "all_summary_mappings",
    "lookup_summary",
    "summary_concepts_for_standard",
]


# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SummaryMapping:
    """SummaryOfBusinessResults concept の CK マッピング。

    Attributes:
        concept: jpcrp_cor のローカル名（例: ``"NetSalesSummaryOfBusinessResults"``）。
        canonical_key: 正規化キー（例: ``"revenue"``）。
        standard: 会計基準識別子。
            ``"jgaap"`` / ``"ifrs"`` / ``"usgaap"`` / ``"jmis"``。
    """

    concept: str
    canonical_key: str
    standard: str


# ---------------------------------------------------------------------------
# J-GAAP マッピング（jpcrp_cor XSD 実在）
# ---------------------------------------------------------------------------

_JGAAP: tuple[SummaryMapping, ...] = (
    # --- 売上高（業種別代替概念） ---
    SummaryMapping("NetSalesSummaryOfBusinessResults", CK.REVENUE, "jgaap"),
    # NOTE: OrdinaryIncome（経常収益）は銀行業の売上高相当。
    # OrdinaryIncomeLoss（経常利益/経常損失）とは別概念。
    SummaryMapping("OrdinaryIncomeSummaryOfBusinessResults", CK.REVENUE, "jgaap"),
    SummaryMapping("OperatingRevenue1SummaryOfBusinessResults", CK.REVENUE, "jgaap"),
    SummaryMapping("OperatingRevenue2SummaryOfBusinessResults", CK.REVENUE, "jgaap"),
    SummaryMapping("GrossOperatingRevenueSummaryOfBusinessResults", CK.REVENUE, "jgaap"),
    # --- 損益 ---
    SummaryMapping("OrdinaryIncomeLossSummaryOfBusinessResults", CK.ORDINARY_INCOME, "jgaap"),
    SummaryMapping("NetIncomeLossSummaryOfBusinessResults", CK.NET_INCOME, "jgaap"),
    SummaryMapping("ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults", CK.NET_INCOME_PARENT, "jgaap"),
    SummaryMapping("ComprehensiveIncomeSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME, "jgaap"),
    # --- BS ---
    SummaryMapping("TotalAssetsSummaryOfBusinessResults", CK.TOTAL_ASSETS, "jgaap"),
    SummaryMapping("NetAssetsSummaryOfBusinessResults", CK.NET_ASSETS, "jgaap"),
    SummaryMapping("CapitalStockSummaryOfBusinessResults", CK.CAPITAL_STOCK, "jgaap"),
    # --- CF ---
    SummaryMapping("NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults", CK.OPERATING_CF, "jgaap"),
    SummaryMapping("NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults", CK.INVESTING_CF, "jgaap"),
    SummaryMapping("NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults", CK.FINANCING_CF, "jgaap"),
    SummaryMapping("CashAndCashEquivalentsSummaryOfBusinessResults", CK.CASH_END, "jgaap"),
    # --- 1株当たり ---
    SummaryMapping("BasicEarningsLossPerShareSummaryOfBusinessResults", CK.EPS, "jgaap"),
    SummaryMapping("DilutedEarningsPerShareSummaryOfBusinessResults", CK.EPS_DILUTED, "jgaap"),
    SummaryMapping("NetAssetsPerShareSummaryOfBusinessResults", CK.BPS, "jgaap"),
    SummaryMapping("DividendPaidPerShareSummaryOfBusinessResults", CK.DPS, "jgaap"),
    # --- 比率 ---
    SummaryMapping("EquityToAssetRatioSummaryOfBusinessResults", CK.EQUITY_RATIO, "jgaap"),
    SummaryMapping("RateOfReturnOnEquitySummaryOfBusinessResults", CK.ROE, "jgaap"),
    SummaryMapping("PriceEarningsRatioSummaryOfBusinessResults", CK.PER, "jgaap"),
    # --- 一般（追加） ---
    SummaryMapping("EquityInEarningsLossesOfAffiliatesIfEquityMethodIsAppliedSummaryOfBusinessResults", CK.EQUITY_METHOD_INCOME, "jgaap"),
    SummaryMapping("InterimDividendPaidPerShareSummaryOfBusinessResults", CK.INTERIM_DPS, "jgaap"),
    SummaryMapping("PayoutRatioSummaryOfBusinessResults", CK.PAYOUT_RATIO, "jgaap"),
    SummaryMapping("TotalNumberOfIssuedSharesSummaryOfBusinessResults", CK.TOTAL_SHARES_ISSUED, "jgaap"),
    # --- 銀行業 ---
    SummaryMapping("CapitalAdequacyRatioBISStandardSummaryOfBusinessResults", CK.CAPITAL_ADEQUACY_RATIO_BIS, "jgaap"),
    SummaryMapping("CapitalAdequacyRatioDomesticStandardSummaryOfBusinessResults", CK.CAPITAL_ADEQUACY_RATIO_DOMESTIC, "jgaap"),
    SummaryMapping("CapitalAdequacyRatioDomesticStandard2SummaryOfBusinessResults", CK.CAPITAL_ADEQUACY_RATIO_DOMESTIC_2, "jgaap"),
    SummaryMapping("CapitalAdequacyRatioInternationalStandardSummaryOfBusinessResults", CK.CAPITAL_ADEQUACY_RATIO_INTERNATIONAL, "jgaap"),
    SummaryMapping("DepositsSummaryOfBusinessResults", CK.DEPOSITS, "jgaap"),
    SummaryMapping("LoansAndBillsDiscountedSummaryOfBusinessResults", CK.LOANS_AND_BILLS_DISCOUNTED, "jgaap"),
    SummaryMapping("SecuritiesSummaryOfBusinessResults", CK.SECURITIES_BANKING, "jgaap"),
    # --- 保険業 ---
    SummaryMapping("NetPremiumsWrittenSummaryOfBusinessResultsINS", CK.NET_PREMIUMS_WRITTEN, "jgaap"),
    SummaryMapping("InterestAndDividendIncomeSummaryOfBusinessResultsINS", CK.INTEREST_DIVIDEND_INCOME_INS, "jgaap"),
    SummaryMapping("InvestmentAssetsYieldIncomeYieldSummaryOfBusinessResultsINS", CK.INVESTMENT_YIELD_INCOME, "jgaap"),
    SummaryMapping("InvestmentYieldRealizedYieldSummaryOfBusinessResultsINS", CK.INVESTMENT_YIELD_REALIZED, "jgaap"),
    SummaryMapping("NetLossRatioSummaryOfBusinessResultsINS", CK.NET_LOSS_RATIO, "jgaap"),
    SummaryMapping("NetOperatingExpenseRatioSummaryOfBusinessResultsINS", CK.NET_OPERATING_EXPENSE_RATIO, "jgaap"),
)

# ---------------------------------------------------------------------------
# IFRS マッピング（jpcrp_cor XSD 実在）
# ---------------------------------------------------------------------------

_IFRS: tuple[SummaryMapping, ...] = (
    # --- 損益 ---
    SummaryMapping("RevenueIFRSSummaryOfBusinessResults", CK.REVENUE, "ifrs"),
    SummaryMapping("ProfitLossBeforeTaxIFRSSummaryOfBusinessResults", CK.INCOME_BEFORE_TAX, "ifrs"),
    SummaryMapping("ProfitLossIFRSSummaryOfBusinessResults", CK.NET_INCOME, "ifrs"),
    SummaryMapping("ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults", CK.NET_INCOME_PARENT, "ifrs"),
    SummaryMapping("ComprehensiveIncomeIFRSSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME, "ifrs"),
    SummaryMapping("ComprehensiveIncomeAttributableToOwnersOfParentIFRSSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME_PARENT, "ifrs"),
    # --- BS ---
    SummaryMapping("EquityAttributableToOwnersOfParentIFRSSummaryOfBusinessResults", CK.EQUITY_PARENT, "ifrs"),
    SummaryMapping("TotalAssetsIFRSSummaryOfBusinessResults", CK.TOTAL_ASSETS, "ifrs"),
    # --- 1株当たり ---
    SummaryMapping("BasicEarningsLossPerShareIFRSSummaryOfBusinessResults", CK.EPS, "ifrs"),
    SummaryMapping("DilutedEarningsLossPerShareIFRSSummaryOfBusinessResults", CK.EPS_DILUTED, "ifrs"),
    # --- 比率 ---
    SummaryMapping("RateOfReturnOnEquityIFRSSummaryOfBusinessResults", CK.ROE, "ifrs"),
    SummaryMapping("RatioOfOwnersEquityToGrossAssetsIFRSSummaryOfBusinessResults", CK.EQUITY_RATIO, "ifrs"),
    SummaryMapping("PriceEarningsRatioIFRSSummaryOfBusinessResults", CK.PER, "ifrs"),
    # --- CF ---
    SummaryMapping("CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults", CK.OPERATING_CF, "ifrs"),
    SummaryMapping("CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults", CK.INVESTING_CF, "ifrs"),
    SummaryMapping("CashFlowsFromUsedInFinancingActivitiesIFRSSummaryOfBusinessResults", CK.FINANCING_CF, "ifrs"),
    SummaryMapping("CashAndCashEquivalentsIFRSSummaryOfBusinessResults", CK.CASH_END, "ifrs"),
    # --- 比率（追加） ---
    SummaryMapping("EquityToAssetRatioIFRSSummaryOfBusinessResults", CK.EQUITY_RATIO, "ifrs"),
    # --- 損益（追加） ---
    SummaryMapping("ProfitLossFromContinuingOperationsIFRSSummaryOfBusinessResults", CK.CONTINUING_OPERATIONS_INCOME, "ifrs"),
)

# ---------------------------------------------------------------------------
# US-GAAP マッピング（jpcrp_cor XSD 実在）
# ---------------------------------------------------------------------------

_USGAAP: tuple[SummaryMapping, ...] = (
    # --- 損益 ---
    SummaryMapping("RevenuesUSGAAPSummaryOfBusinessResults", CK.REVENUE, "usgaap"),
    SummaryMapping("OperatingIncomeLossUSGAAPSummaryOfBusinessResults", CK.OPERATING_INCOME, "usgaap"),
    SummaryMapping("ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults", CK.INCOME_BEFORE_TAX, "usgaap"),
    SummaryMapping("NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults", CK.NET_INCOME_PARENT, "usgaap"),
    SummaryMapping("ComprehensiveIncomeUSGAAPSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME, "usgaap"),
    SummaryMapping("ComprehensiveIncomeAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME_PARENT, "usgaap"),
    # --- BS ---
    SummaryMapping("EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults", CK.SHAREHOLDERS_EQUITY, "usgaap"),
    SummaryMapping("EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults", CK.NET_ASSETS, "usgaap"),
    SummaryMapping("TotalAssetsUSGAAPSummaryOfBusinessResults", CK.TOTAL_ASSETS, "usgaap"),
    # --- 比率 ---
    SummaryMapping("EquityToAssetRatioUSGAAPSummaryOfBusinessResults", CK.EQUITY_RATIO, "usgaap"),
    SummaryMapping("RateOfReturnOnEquityUSGAAPSummaryOfBusinessResults", CK.ROE, "usgaap"),
    SummaryMapping("PriceEarningsRatioUSGAAPSummaryOfBusinessResults", CK.PER, "usgaap"),
    # --- CF ---
    SummaryMapping("CashFlowsFromUsedInOperatingActivitiesUSGAAPSummaryOfBusinessResults", CK.OPERATING_CF, "usgaap"),
    SummaryMapping("CashFlowsFromUsedInInvestingActivitiesUSGAAPSummaryOfBusinessResults", CK.INVESTING_CF, "usgaap"),
    SummaryMapping("CashFlowsFromUsedInFinancingActivitiesUSGAAPSummaryOfBusinessResults", CK.FINANCING_CF, "usgaap"),
    SummaryMapping("CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults", CK.CASH_END, "usgaap"),
    # --- 1株当たり ---
    SummaryMapping("BasicEarningsLossPerShareUSGAAPSummaryOfBusinessResults", CK.EPS, "usgaap"),
    SummaryMapping("DilutedEarningsLossPerShareUSGAAPSummaryOfBusinessResults", CK.EPS_DILUTED, "usgaap"),
    SummaryMapping("EquityAttributableToOwnersOfParentPerShareUSGAAPSummaryOfBusinessResults", CK.BPS, "usgaap"),
)

# ---------------------------------------------------------------------------
# JMIS マッピング（jpcrp_cor XSD 実在）
# ---------------------------------------------------------------------------

_JMIS: tuple[SummaryMapping, ...] = (
    # --- 損益 ---
    SummaryMapping("RevenueJMISSummaryOfBusinessResults", CK.REVENUE, "jmis"),
    SummaryMapping("ProfitLossBeforeTaxJMISSummaryOfBusinessResults", CK.INCOME_BEFORE_TAX, "jmis"),
    SummaryMapping("ProfitLossJMISSummaryOfBusinessResults", CK.NET_INCOME, "jmis"),
    SummaryMapping("ProfitLossAttributableToOwnersOfParentJMISSummaryOfBusinessResults", CK.NET_INCOME_PARENT, "jmis"),
    SummaryMapping("ComprehensiveIncomeJMISSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME, "jmis"),
    SummaryMapping("ComprehensiveIncomeAttributableToOwnersOfParentJMISSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME_PARENT, "jmis"),
    # --- BS ---
    SummaryMapping("EquityAttributableToOwnersOfParentJMISSummaryOfBusinessResults", CK.EQUITY_PARENT, "jmis"),
    SummaryMapping("TotalAssetsJMISSummaryOfBusinessResults", CK.TOTAL_ASSETS, "jmis"),
    # --- 1株当たり ---
    SummaryMapping("BasicEarningsLossPerShareJMISSummaryOfBusinessResults", CK.EPS, "jmis"),
    SummaryMapping("DilutedEarningsLossPerShareJMISSummaryOfBusinessResults", CK.EPS_DILUTED, "jmis"),
    # --- 比率 ---
    SummaryMapping("EquityToAssetRatioJMISSummaryOfBusinessResults", CK.EQUITY_RATIO, "jmis"),
    SummaryMapping("RateOfReturnOnEquityJMISSummaryOfBusinessResults", CK.ROE, "jmis"),
    SummaryMapping("RatioOfOwnersEquityToGrossAssetsJMISSummaryOfBusinessResults", CK.EQUITY_RATIO, "jmis"),
    SummaryMapping("PriceEarningsRatioJMISSummaryOfBusinessResults", CK.PER, "jmis"),
    # --- CF ---
    SummaryMapping("CashFlowsFromUsedInOperatingActivitiesJMISSummaryOfBusinessResults", CK.OPERATING_CF, "jmis"),
    SummaryMapping("CashFlowsFromUsedInInvestingActivitiesJMISSummaryOfBusinessResults", CK.INVESTING_CF, "jmis"),
    SummaryMapping("CashFlowsFromUsedInFinancingActivitiesJMISSummaryOfBusinessResults", CK.FINANCING_CF, "jmis"),
    SummaryMapping("CashAndCashEquivalentsJMISSummaryOfBusinessResults", CK.CASH_END, "jmis"),
    # --- 損益（追加） ---
    SummaryMapping("ProfitLossFromContinuingOperationsJMISSummaryOfBusinessResults", CK.CONTINUING_OPERATIONS_INCOME, "jmis"),
)


# ---------------------------------------------------------------------------
# 統合レジストリとインデックス
# ---------------------------------------------------------------------------

_ALL_MAPPINGS: tuple[SummaryMapping, ...] = (
    *_JGAAP,
    *_IFRS,
    *_USGAAP,
    *_JMIS,
)

# concept ローカル名 → SummaryMapping
_CONCEPT_INDEX: dict[str, SummaryMapping] = {
    m.concept: m for m in _ALL_MAPPINGS
}

# standard → tuple[SummaryMapping, ...]
_STANDARD_INDEX: dict[str, tuple[SummaryMapping, ...]] = {
    "jgaap": _JGAAP,
    "ifrs": _IFRS,
    "usgaap": _USGAAP,
    "jmis": _JMIS,
}


# ---------------------------------------------------------------------------
# レジストリ検証（モジュールロード時に実行）
# ---------------------------------------------------------------------------


def _validate_registry() -> None:
    """マッピングレジストリの整合性を検証する。

    Raises:
        ValueError: レジストリに不整合がある場合。
    """
    concepts = [m.concept for m in _ALL_MAPPINGS]
    if len(concepts) != len(set(concepts)):
        duplicates = [c for c in concepts if concepts.count(c) > 1]
        raise ValueError(f"concept が重複しています: {set(duplicates)}")

    for m in _ALL_MAPPINGS:
        if not m.concept:
            raise ValueError("空の concept が登録されています")
        if not m.canonical_key:
            raise ValueError(f"{m.concept} の canonical_key が空です")
        if m.standard not in ("jgaap", "ifrs", "usgaap", "jmis"):
            raise ValueError(
                f"{m.concept} の standard が不正です: {m.standard!r}"
            )


_validate_registry()


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def lookup_summary(concept: str) -> str | None:
    """SummaryOfBusinessResults concept から CK を返す。

    Args:
        concept: jpcrp_cor のローカル名
            （例: ``"NetSalesSummaryOfBusinessResults"``）。

    Returns:
        正規化キー文字列。登録されていない concept の場合は ``None``。
    """
    m = _CONCEPT_INDEX.get(concept)
    return m.canonical_key if m is not None else None


def all_summary_mappings() -> tuple[SummaryMapping, ...]:
    """全 SummaryMapping を返す。

    Returns:
        全マッピングのタプル（J-GAAP → IFRS → US-GAAP → JMIS 順）。
    """
    return _ALL_MAPPINGS


def summary_concepts_for_standard(standard: str) -> tuple[SummaryMapping, ...]:
    """指定基準の SummaryMapping を返す。

    Args:
        standard: ``"jgaap"`` / ``"ifrs"`` / ``"usgaap"`` / ``"jmis"``。

    Returns:
        該当基準のマッピングタプル。未知の基準は空タプル。
    """
    return _STANDARD_INDEX.get(standard, ())

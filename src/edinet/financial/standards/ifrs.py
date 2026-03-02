"""IFRS（国際財務報告基準）適用企業の科目定義と J-GAAP 対応マッピング。

EDINET の ``jpigp_cor`` タクソノミに基づく IFRS 科目の正規化マッピングを提供する。
``canonical_key`` による会計基準横断の統一アクセスを可能にし、
Wave 3 の ``standards/normalize`` が J-GAAP / IFRS を統一的に扱えるようにする。

典型的な使用例::

    from edinet.financial.standards.ifrs import lookup, canonical_key, reverse_lookup

    # concept → mapping 情報
    m = lookup("RevenueIFRS")
    assert m is not None
    assert m.canonical_key == "revenue"

    # canonical_key → mapping（逆引き）
    m2 = reverse_lookup("revenue")
    assert m2 is not None
    assert m2.concept == "RevenueIFRS"

    # concept → canonical_key（簡易版）
    key = canonical_key("RevenueIFRS")
    assert key == "revenue"
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

from edinet.models.financial import StatementType
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "IFRSConceptMapping",
    "IFRSProfile",
    "NAMESPACE_MODULE_GROUP",
    "lookup",
    "canonical_key",
    "reverse_lookup",
    "mappings_for_statement",
    "all_mappings",
    "all_canonical_keys",
    "ifrs_specific_concepts",
    "load_ifrs_pl_concepts",
    "load_ifrs_bs_concepts",
    "load_ifrs_cf_concepts",
    "get_ifrs_concept_set",
    "ifrs_to_jgaap_map",
    "jgaap_to_ifrs_map",
    "is_ifrs_module",
    "get_profile",
]

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

NAMESPACE_MODULE_GROUP: str = "jpigp"
"""IFRS 財務諸表の名前空間モジュールグループ。

Wave 1 L5 の ``classify_namespace()`` が返す
``NamespaceInfo.module_group`` と照合して IFRS 科目かどうかを
判定するために使用する。
"""

_IFRS_MODULE_GROUPS: frozenset[str] = frozenset({"jpigp"})
"""IFRS に関連するモジュールグループの集合。"""

# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IFRSConceptMapping:
    """IFRS 科目の正規化マッピング。

    Lane 3 の ``ConceptMapping`` と対称的な構造を持つ。
    ``canonical_key`` を共通キーとして、Wave 3 の normalize が
    会計基準横断の統一アクセスを提供する。

    Attributes:
        concept: ``jpigp_cor`` の concept ローカル名（例: ``"RevenueIFRS"``）。
            バージョン非依存。
        canonical_key: 正規化キー（例: ``"revenue"``）。
            会計基準間で共通の文字列識別子。Lane 3 §5.2-5.5 で定義
            された J-GAAP の正規化キーと同一値を使用する。
            IFRS 固有科目には新規キーを定義。小文字 snake_case。
        statement_type: 所属する財務諸表。``INCOME_STATEMENT`` /
            ``BALANCE_SHEET`` / ``CASH_FLOW_STATEMENT``。
        is_ifrs_specific: IFRS 固有の概念か。
            ``True`` の場合、J-GAAP に直接対応する概念がない。
        jgaap_concept: J-GAAP 側の対応 concept ローカル名。
            IFRS 固有の科目の場合は ``None``。
        mapping_note: マッピングに関する補足説明。
    """

    concept: str
    canonical_key: str
    statement_type: StatementType | None
    is_ifrs_specific: bool = False
    jgaap_concept: str | None = None
    mapping_note: str = ""


@dataclass(frozen=True, slots=True)
class IFRSProfile:
    """IFRS 会計基準のプロファイル（概要情報）。

    ``standards/normalize`` (Wave 3) が全会計基準のプロファイルを
    並列に保持し、ディスパッチに使用する。
    Lane 3 の ``JGAAPProfile`` と対称的な構造。

    Attributes:
        standard_id: 会計基準の識別子。``"ifrs"`` 固定。
        display_name_ja: 日本語表示名。
        display_name_en: 英語表示名。
        module_groups: この会計基準に **固有の**（他の会計基準では使用されない）
            タクソノミモジュールグループの集合。
            IFRS 企業でも ``jpcrp_cor`` / ``jpdei_cor`` は共通して使用されるが、
            ``jpigp_cor`` は IFRS 企業のみが使用するため、
            ``{"jpigp"}`` のみを含む。
        canonical_key_count: 定義されている正規化キーの総数（PL + BS + CF）。
        has_ordinary_income: 経常利益の概念を持つか（``False``: IFRS にはない）。
        has_extraordinary_items: 特別利益/特別損失の概念を持つか（``False``）。
    """

    standard_id: str
    display_name_ja: str
    display_name_en: str
    module_groups: frozenset[str]
    canonical_key_count: int
    has_ordinary_income: bool
    has_extraordinary_items: bool


# ---------------------------------------------------------------------------
# マッピングレジストリ（Python コードが主データソース）
# ---------------------------------------------------------------------------

# --- PL マッピング（15 concepts） ---
# XSD 検証済み: jpigp_cor_2025-11-01.xsd
_PL = StatementType.INCOME_STATEMENT
_PL_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    IFRSConceptMapping("RevenueIFRS", CK.REVENUE, _PL, jgaap_concept="NetSales"),
    IFRSConceptMapping("CostOfSalesIFRS", CK.COST_OF_SALES, _PL, jgaap_concept="CostOfSales"),
    IFRSConceptMapping("GrossProfitIFRS", CK.GROSS_PROFIT, _PL, jgaap_concept="GrossProfit"),
    IFRSConceptMapping("SellingGeneralAndAdministrativeExpensesIFRS", CK.SGA_EXPENSES, _PL, jgaap_concept="SellingGeneralAndAdministrativeExpenses"),
    IFRSConceptMapping("OtherIncomeIFRS", CK.OTHER_INCOME_IFRS, _PL, is_ifrs_specific=True, mapping_note="IFRS 固有。J-GAAP に直接対応する独立カテゴリなし"),
    IFRSConceptMapping("OtherExpensesIFRS", CK.OTHER_EXPENSES_IFRS, _PL, is_ifrs_specific=True, mapping_note="IFRS 固有。J-GAAP に直接対応する独立カテゴリなし"),
    IFRSConceptMapping("OperatingProfitLossIFRS", CK.OPERATING_INCOME, _PL, jgaap_concept="OperatingIncome", mapping_note="IFRS は損益を含む表記"),
    IFRSConceptMapping("FinanceIncomeIFRS", CK.FINANCE_INCOME, _PL, is_ifrs_specific=True, mapping_note="IFRS 固有。J-GAAP の営業外収益の一部に相当"),
    IFRSConceptMapping("FinanceCostsIFRS", CK.FINANCE_COSTS, _PL, is_ifrs_specific=True, mapping_note="IFRS 固有。J-GAAP の営業外費用の一部に相当"),
    IFRSConceptMapping("ShareOfProfitLossOfInvestmentsAccountedForUsingEquityMethodIFRS", CK.EQUITY_METHOD_INCOME_IFRS, _PL, is_ifrs_specific=True, mapping_note="IFRS の PL 独自表示。J-GAAP では営業外収益/費用に計上"),
    IFRSConceptMapping("ProfitLossBeforeTaxIFRS", CK.INCOME_BEFORE_TAX, _PL, jgaap_concept="IncomeBeforeIncomeTaxes", mapping_note="J-GAAP の経常利益に最も近い概念"),
    IFRSConceptMapping("IncomeTaxExpenseIFRS", CK.INCOME_TAXES, _PL, jgaap_concept="IncomeTaxes"),
    IFRSConceptMapping("ProfitLossIFRS", CK.NET_INCOME, _PL, jgaap_concept="ProfitLoss"),
    IFRSConceptMapping("ProfitLossAttributableToOwnersOfParentIFRS", CK.NET_INCOME_PARENT, _PL, jgaap_concept="ProfitLossAttributableToOwnersOfParent"),
    IFRSConceptMapping("ProfitLossAttributableToNonControllingInterestsIFRS", CK.NET_INCOME_MINORITY, _PL, jgaap_concept="ProfitLossAttributableToNonControllingInterests"),
)

# --- BS マッピング（19 concepts） ---
# XSD 検証済み: jpigp_cor_2025-11-01.xsd
# NOTE: NonCurrentAssetsIFRS（NonCurrent、Noncurrent ではない）
# NOTE: NonCurrentLabilitiesIFRS（EDINET XSD のタイポ: Labilities）
# NOTE: TotalCurrentLiabilitiesIFRS（CurrentLiabilitiesIFRS は存在しない）
# NOTE: ShareCapitalIFRS（IssuedCapitalIFRS は存在しない）
_BS = StatementType.BALANCE_SHEET
_BS_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    IFRSConceptMapping("TradeAndOtherReceivablesCAIFRS", CK.TRADE_RECEIVABLES, _BS, jgaap_concept="NotesAndAccountsReceivableTrade", mapping_note="IFRS は「営業債権及びその他の債権」。J-GAAP「受取手形及び売掛金」に近似対応"),
    IFRSConceptMapping("InventoriesCAIFRS", CK.INVENTORIES, _BS, jgaap_concept="Inventories"),
    IFRSConceptMapping("CashAndCashEquivalentsIFRS", CK.CASH_AND_EQUIVALENTS, _BS, jgaap_concept="CashAndDeposits", mapping_note="J-GAAP「現金及び預金」に近似対応。CF 期首/期末は BS で表現"),
    IFRSConceptMapping("CurrentAssetsIFRS", CK.CURRENT_ASSETS, _BS, jgaap_concept="CurrentAssets"),
    IFRSConceptMapping("NonCurrentAssetsIFRS", CK.NONCURRENT_ASSETS, _BS, jgaap_concept="NoncurrentAssets", mapping_note="J-GAAP「固定資産」に対応。用語が異なる"),
    IFRSConceptMapping("PropertyPlantAndEquipmentIFRS", CK.PPE, _BS, jgaap_concept="PropertyPlantAndEquipment"),
    IFRSConceptMapping("IntangibleAssetsIFRS", CK.INTANGIBLE_ASSETS, _BS, jgaap_concept="IntangibleAssets", mapping_note="IFRS では「無形資産」、J-GAAP では「無形固定資産」"),
    IFRSConceptMapping("AssetsIFRS", CK.TOTAL_ASSETS, _BS, jgaap_concept="Assets"),
    IFRSConceptMapping("TradeAndOtherPayablesCLIFRS", CK.TRADE_PAYABLES, _BS, jgaap_concept="NotesAndAccountsPayableTrade", mapping_note="IFRS は「営業債務及びその他の債務」。J-GAAP「支払手形及び買掛金」に近似対応"),
    IFRSConceptMapping("TotalCurrentLiabilitiesIFRS", CK.CURRENT_LIABILITIES, _BS, jgaap_concept="CurrentLiabilities"),
    IFRSConceptMapping("NonCurrentLabilitiesIFRS", CK.NONCURRENT_LIABILITIES, _BS, jgaap_concept="NoncurrentLiabilities", mapping_note="J-GAAP「固定負債」に対応。用語が異なる。NOTE: EDINET XSD のタイポ（Labilities）をそのまま使用"),
    IFRSConceptMapping("LiabilitiesIFRS", CK.TOTAL_LIABILITIES, _BS, jgaap_concept="Liabilities"),
    IFRSConceptMapping("ShareCapitalIFRS", CK.CAPITAL_STOCK, _BS, jgaap_concept="CapitalStock", mapping_note="XSD では ShareCapitalIFRS（IssuedCapitalIFRS は存在しない）"),
    IFRSConceptMapping("CapitalSurplusIFRS", CK.CAPITAL_SURPLUS, _BS, jgaap_concept="CapitalSurplus"),
    IFRSConceptMapping("RetainedEarningsIFRS", CK.RETAINED_EARNINGS, _BS, jgaap_concept="RetainedEarnings"),
    IFRSConceptMapping("TreasurySharesIFRS", CK.TREASURY_STOCK, _BS, jgaap_concept="TreasuryStock"),
    IFRSConceptMapping("EquityAttributableToOwnersOfParentIFRS", CK.EQUITY_PARENT, _BS, jgaap_concept="ShareholdersEquity", mapping_note="J-GAAP「株主資本」に近いが等価ではない。IFRS には「株主資本」概念がない。近似対応は normalize の責務"),
    IFRSConceptMapping("NonControllingInterestsIFRS", CK.MINORITY_INTERESTS, _BS, jgaap_concept="NonControllingInterests"),
    IFRSConceptMapping("EquityIFRS", CK.NET_ASSETS, _BS, jgaap_concept="NetAssets", mapping_note="IFRS は「資本」、J-GAAP は「純資産」"),
)

# --- CF マッピング（16 concepts） ---
# XSD 検証済み: jpigp_cor_2025-11-01.xsd
# NOTE: XSD は NetCashProvidedByUsedIn... 形式（CashFlowsFromUsedIn... ではない）
# NOTE: CashAndCashEquivalentsAtBeginningOfPeriodIFRS / ...AtEndOfPeriodIFRS は
#       XSD に存在しない（IFRS では BS の CashAndCashEquivalentsIFRS を使用）
# NOTE: 連結範囲変動に伴うキャッシュ増減の独立 concept は XSD に存在しない
_CF = StatementType.CASH_FLOW_STATEMENT
_CF_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    # --- 営業 CF 内訳 ---
    IFRSConceptMapping("DepreciationAndAmortizationOpeCFIFRS", CK.DEPRECIATION_CF, _CF, jgaap_concept="DepreciationAndAmortizationOpeCF"),
    IFRSConceptMapping("ImpairmentLossesReversalOfImpairmentLossesOpeCFIFRS", CK.IMPAIRMENT_LOSS_CF, _CF, is_ifrs_specific=True, jgaap_concept="ImpairmentLossOpeCF", mapping_note="IFRS は戻入れを含む"),
    IFRSConceptMapping("ShareOfLossProfitOfInvestmentsAccountedForUsingEquityMethodOpeCFIFRS", CK.EQUITY_METHOD_CF, _CF, jgaap_concept="EquityInEarningsLossesOfAffiliatesOpeCF"),
    IFRSConceptMapping("DecreaseIncreaseInTradeAndOtherReceivablesOpeCFIFRS", CK.TRADE_RECEIVABLES_CHANGE_CF, _CF, jgaap_concept="DecreaseIncreaseInNotesAndAccountsReceivableTradeOpeCF"),
    IFRSConceptMapping("DecreaseIncreaseInInventoriesOpeCFIFRS", CK.INVENTORIES_CHANGE_CF, _CF, jgaap_concept="DecreaseIncreaseInInventoriesOpeCF"),
    IFRSConceptMapping("IncreaseDecreaseInTradeAndOtherPayablesOpeCFIFRS", CK.TRADE_PAYABLES_CHANGE_CF, _CF, jgaap_concept="IncreaseDecreaseInNotesAndAccountsPayableTradeOpeCF"),
    IFRSConceptMapping("SubtotalOpeCFIFRS", CK.SUBTOTAL_OPERATING_CF, _CF, jgaap_concept="SubtotalOpeCF"),
    IFRSConceptMapping("IncomeTaxesPaidOpeCFIFRS", CK.INCOME_TAXES_PAID_CF, _CF, jgaap_concept="IncomeTaxesPaidOpeCF"),
    # --- 営業 CF 合計 ---
    IFRSConceptMapping("NetCashProvidedByUsedInOperatingActivitiesIFRS", CK.OPERATING_CF, _CF, jgaap_concept="NetCashProvidedByUsedInOperatingActivities"),
    # --- 投資 CF 内訳 ---
    IFRSConceptMapping("PurchaseOfPropertyPlantAndEquipmentInvCFIFRS", CK.PURCHASE_PPE_CF, _CF, jgaap_concept="PurchaseOfPropertyPlantAndEquipmentInvCF"),
    # --- 投資 CF 合計 ---
    IFRSConceptMapping("NetCashProvidedByUsedInInvestingActivitiesIFRS", CK.INVESTING_CF, _CF, jgaap_concept="NetCashProvidedByUsedInInvestmentActivities", mapping_note="J-GAAP は Investment、IFRS は Investing"),
    # --- 財務 CF 内訳 ---
    IFRSConceptMapping("RepaymentsOfLongTermBorrowingsFinCFIFRS", CK.REPAYMENT_LONG_TERM_LOANS_CF, _CF, jgaap_concept="RepaymentOfLongTermLoansPayableFinCF"),
    IFRSConceptMapping("DividendsPaidFinCFIFRS", CK.DIVIDENDS_PAID_CF, _CF, jgaap_concept="CashDividendsPaidFinCF"),
    # --- 財務 CF 合計 ---
    IFRSConceptMapping("NetCashProvidedByUsedInFinancingActivitiesIFRS", CK.FINANCING_CF, _CF, jgaap_concept="NetCashProvidedByUsedInFinancingActivities"),
    # --- 換算差額等 ---
    IFRSConceptMapping("EffectOfExchangeRateChangesOnCashAndCashEquivalentsIFRS", CK.FX_EFFECT_ON_CASH, _CF, jgaap_concept="EffectOfExchangeRateChangeOnCashAndCashEquivalents", mapping_note="J-GAAP は Change（単数）、IFRS は Changes（複数）"),
    IFRSConceptMapping("NetIncreaseDecreaseInCashAndCashEquivalentsIFRS", CK.NET_CHANGE_IN_CASH, _CF, jgaap_concept="NetIncreaseDecreaseInCashAndCashEquivalents"),
)

# --- KPI マッピング（statement_type=None: 特定の財務諸表に属さない） ---
_KPI_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    IFRSConceptMapping("BasicEarningsLossPerShareIFRS", CK.EPS, None, jgaap_concept="BasicEarningsLossPerShareSummaryOfBusinessResults"),
    IFRSConceptMapping("DilutedEarningsLossPerShareIFRS", CK.EPS_DILUTED, None, jgaap_concept="DilutedEarningsPerShareSummaryOfBusinessResults"),
)

# --- CI マッピング（包括利益。statement_type=None: 独立した CI 計算書は未対応） ---
_CI_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    IFRSConceptMapping("ComprehensiveIncomeIFRS", CK.COMPREHENSIVE_INCOME, None, is_ifrs_specific=True),
    IFRSConceptMapping("ComprehensiveIncomeAttributableToOwnersOfParentIFRS", CK.COMPREHENSIVE_INCOME_PARENT, None, mapping_note="J-GAAP の包括利益は jgaap.py 未登録のため jgaap_concept=None"),
    IFRSConceptMapping("ComprehensiveIncomeAttributableToNonControllingInterestsIFRS", CK.COMPREHENSIVE_INCOME_MINORITY, None, is_ifrs_specific=True),
)

# --- 全マッピング ---
_ALL_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    *_PL_MAPPINGS,
    *_BS_MAPPINGS,
    *_CF_MAPPINGS,
    *_KPI_MAPPINGS,
    *_CI_MAPPINGS,
)

# M-5: モジュールレベルで事前構築
_ALL_CANONICAL_KEYS: frozenset[str] = frozenset(
    m.canonical_key for m in _ALL_MAPPINGS
)

# ---------------------------------------------------------------------------
# インデックス辞書
# ---------------------------------------------------------------------------

_CONCEPT_INDEX: dict[str, IFRSConceptMapping] = {
    m.concept: m for m in _ALL_MAPPINGS
}

_CANONICAL_INDEX: dict[str, IFRSConceptMapping] = {
    m.canonical_key: m for m in _ALL_MAPPINGS
}

_STATEMENT_INDEX: dict[StatementType, tuple[IFRSConceptMapping, ...]] = {
    StatementType.INCOME_STATEMENT: _PL_MAPPINGS,
    StatementType.BALANCE_SHEET: _BS_MAPPINGS,
    StatementType.CASH_FLOW_STATEMENT: _CF_MAPPINGS,
}

# ---------------------------------------------------------------------------
# J-GAAP 固有科目リスト
# ---------------------------------------------------------------------------

# jgaap.jgaap_specific_concepts() から is_jgaap_specific=True の概念を動的取得し、
# IFRS に独立 concept がない J-GAAP 固有科目（手動管理）と合成する。


def _build_jgaap_only_concepts() -> frozenset[str]:
    """J-GAAP 固有科目リストを構築する（遅延 import でE402回避）。"""
    from edinet.financial.standards import jgaap as _jgaap_mod  # noqa: E402

    return frozenset(
        {m.concept for m in _jgaap_mod.jgaap_specific_concepts()}
        | _JGAAP_ONLY_MANUAL
    )


_JGAAP_ONLY_MANUAL: frozenset[str] = frozenset(
    {
        # IFRS 非対応（is_jgaap_specific=False だが IFRS に独立 concept なし）
        "IncomeTaxesDeferred",  # IFRS では IncomeTaxExpenseIFRS に内包
        # J-GAAP 固有の BS 構造
        "DeferredAssets",
        # NOTE: ShareholdersEquity は EquityAttributableToOwnersOfParentIFRS の
        # 近似対応として jgaap_concept に設定されているため、ここには含めない。
        # 厳密な等価ではないが、双方向マッピングの整合性を優先する。
        "ValuationAndTranslationAdjustments",
        "SubscriptionRightsToShares",
        "LiabilitiesAndNetAssets",
        "InvestmentsAndOtherAssets",  # J-GAAP 固有の小計
    }
)

_JGAAP_ONLY_CONCEPTS: frozenset[str] = _build_jgaap_only_concepts()


# ---------------------------------------------------------------------------
# 整合性検証（モジュールロード時実行）
# ---------------------------------------------------------------------------


def _validate_registry() -> None:
    """マッピングレジストリの整合性を検証する。

    モジュールロード時に自動実行される。
    ``assert`` ではなく ``ValueError`` を使用し、
    ``python -O``（最適化モード）でもスキップされない。
    """
    if len(_CONCEPT_INDEX) != len(_ALL_MAPPINGS):
        raise ValueError("concept ローカル名に重複があります")
    if len(_CANONICAL_INDEX) != len(_ALL_MAPPINGS):
        raise ValueError("canonical_key に重複があります")
    # _JGAAP_ONLY_CONCEPTS と jgaap_concept の重複検知
    # 重複があると jgaap_to_ifrs_map() で有効なマッピングが None で上書きされる
    jgaap_concepts_in_mappings = {
        m.jgaap_concept for m in _ALL_MAPPINGS if m.jgaap_concept is not None
    }
    overlap = jgaap_concepts_in_mappings & _JGAAP_ONLY_CONCEPTS
    if overlap:
        raise ValueError(
            f"_JGAAP_ONLY_CONCEPTS と jgaap_concept に重複があります: {overlap}"
        )
    # jgaap_concept が jgaap レジストリに実在するかクロスバリデーション
    from edinet.financial.standards import jgaap as _jgaap

    jgaap_all_concepts = {m.concept for m in _jgaap.all_mappings()}
    phantom = jgaap_concepts_in_mappings - jgaap_all_concepts
    if phantom:
        raise ValueError(
            f"jgaap_concept に設定されているが jgaap レジストリに存在しない "
            f"concept があります: {phantom}"
        )


_validate_registry()


# ---------------------------------------------------------------------------
# 公開 API — ルックアップ
# ---------------------------------------------------------------------------


def lookup(concept: str) -> IFRSConceptMapping | None:
    """IFRS concept ローカル名からマッピング情報を取得する。

    Args:
        concept: ``jpigp_cor`` のローカル名（例: ``"RevenueIFRS"``）。

    Returns:
        ``IFRSConceptMapping``。登録されていない concept の場合は ``None``。
    """
    return _CONCEPT_INDEX.get(concept)


def canonical_key(concept: str) -> str | None:
    """IFRS concept ローカル名を正規化キーにマッピングする。

    ``lookup()`` の簡易版。正規化キーのみを返す。

    Args:
        concept: ``jpigp_cor`` のローカル名。

    Returns:
        正規化キー文字列。登録されていない concept の場合は ``None``。
    """
    m = _CONCEPT_INDEX.get(concept)
    return m.canonical_key if m is not None else None


def reverse_lookup(key: str) -> IFRSConceptMapping | None:
    """正規化キーから IFRS の ``IFRSConceptMapping`` を取得する（逆引き）。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        ``IFRSConceptMapping``。該当する IFRS concept がない場合は ``None``。
    """
    return _CANONICAL_INDEX.get(key)


# ---------------------------------------------------------------------------
# 公開 API — 一覧取得
# ---------------------------------------------------------------------------


def mappings_for_statement(
    statement_type: StatementType,
) -> tuple[IFRSConceptMapping, ...]:
    """指定した財務諸表タイプの IFRS マッピングを返す。

    定義順（タクソノミの標準表示順序に準拠）。

    Args:
        statement_type: ``INCOME_STATEMENT`` / ``BALANCE_SHEET`` /
            ``CASH_FLOW_STATEMENT``。

    Returns:
        ``IFRSConceptMapping`` のタプル（定義順）。
    """
    return _STATEMENT_INDEX.get(statement_type, ())


def all_mappings() -> tuple[IFRSConceptMapping, ...]:
    """全 ``IFRSConceptMapping`` を返す（PL → BS → CF 順）。

    Returns:
        全 ``IFRSConceptMapping`` のタプル。
    """
    return _ALL_MAPPINGS


def all_canonical_keys() -> frozenset[str]:
    """定義されている全 ``canonical_key`` の集合を返す。

    「この key は IFRS で定義されているか」の高速判定に使用。
    モジュールレベルで事前構築済みの ``frozenset`` を返す。

    Returns:
        正規化キーのフローズンセット。
    """
    return _ALL_CANONICAL_KEYS


_IFRS_SPECIFIC: tuple[IFRSConceptMapping, ...] = tuple(
    m for m in _ALL_MAPPINGS if m.is_ifrs_specific
)


def ifrs_specific_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 固有の概念（J-GAAP に対応概念がないもの）を返す。

    対象科目: 金融収益（``FinanceIncomeIFRS``）、
    金融費用（``FinanceCostsIFRS``）等。
    モジュールレベルで事前構築済みのタプルを返す。

    Returns:
        ``is_ifrs_specific=True`` の ``IFRSConceptMapping`` のタプル。
    """
    return _IFRS_SPECIFIC


def load_ifrs_pl_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 損益計算書の科目定義を返す。"""
    return mappings_for_statement(StatementType.INCOME_STATEMENT)


def load_ifrs_bs_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 貸借対照表の科目定義を返す。"""
    return mappings_for_statement(StatementType.BALANCE_SHEET)


def load_ifrs_cf_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS キャッシュフロー計算書の科目定義を返す。"""
    return mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)


# ---------------------------------------------------------------------------
# 公開 API — 科目セット
# ---------------------------------------------------------------------------


_CONCEPT_SETS: dict[StatementType, frozenset[str]] = {
    st: frozenset(m.concept for m in mappings)
    for st, mappings in _STATEMENT_INDEX.items()
}


def get_ifrs_concept_set(statement_type: StatementType) -> frozenset[str]:
    """指定された財務諸表タイプの IFRS concept 名の集合を返す。

    ``LineItem`` の concept 名がこの集合に含まれるかを
    高速に判定するために使用する。
    モジュールレベルで事前構築済みの ``frozenset`` を返す。

    Args:
        statement_type: 財務諸表タイプ。

    Returns:
        concept ローカル名の ``frozenset``。
    """
    return _CONCEPT_SETS.get(statement_type, frozenset())


# ---------------------------------------------------------------------------
# 公開 API — IFRS ↔ J-GAAP マッピング
# ---------------------------------------------------------------------------


@functools.cache
def ifrs_to_jgaap_map() -> dict[str, str | None]:
    """IFRS concept 名 → J-GAAP concept 名の辞書を返す（補助）。

    ``_ALL_MAPPINGS`` の ``jgaap_concept`` フィールドから自動生成。
    IFRS 固有の科目（J-GAAP に対応なし）は ``None`` にマッピングされる。
    結果はキャッシュされる。

    Returns:
        IFRS concept 名をキー、J-GAAP concept 名（または ``None``）を値とする辞書。

    Example:
        >>> m = ifrs_to_jgaap_map()
        >>> m["RevenueIFRS"]
        'NetSales'
        >>> m["FinanceIncomeIFRS"] is None
        True
    """
    return {m.concept: m.jgaap_concept for m in _ALL_MAPPINGS}


@functools.cache
def jgaap_to_ifrs_map() -> dict[str, str | None]:
    """J-GAAP concept 名 → IFRS concept 名の辞書を返す（補助）。

    キーには以下が含まれる:

    - ``_ALL_MAPPINGS`` で ``jgaap_concept`` が定義されている J-GAAP concept
      （値は IFRS concept 名）
    - ``_JGAAP_ONLY_CONCEPTS`` に含まれる J-GAAP 固有科目
      （値は ``None``）

    Lane 3 の KPI 概念（EPS / BPS 等）は含まない。
    結果はキャッシュされる。

    Returns:
        J-GAAP concept 名をキー、IFRS concept 名（または ``None``）を値とする辞書。

    Example:
        >>> m = jgaap_to_ifrs_map()
        >>> m["NetSales"]
        'RevenueIFRS'
        >>> m["OrdinaryIncome"] is None
        True
    """
    result: dict[str, str | None] = {}
    for m in _ALL_MAPPINGS:
        if m.jgaap_concept is not None:
            result[m.jgaap_concept] = m.concept
    for jgaap_concept in _JGAAP_ONLY_CONCEPTS:
        result[jgaap_concept] = None
    return result


# ---------------------------------------------------------------------------
# 公開 API — 名前空間判定
# ---------------------------------------------------------------------------


def is_ifrs_module(module_group: str) -> bool:
    """``module_group`` が IFRS 固有のモジュールに属するかを判定する。

    注意: IFRS 企業でも ``jppfs_cor`` はディメンション要素等で
    併用されるため（D-1）、この関数の結果だけで会計基準を
    断定してはならない。会計基準の判別は ``standards/detect`` を使用すること。

    NOTE: ``jpdei`` / ``jpcrp`` は J-GAAP / IFRS 両方で使用される共通モジュール。
    Lane 3 の ``is_jgaap_module()`` は ``jpdei``/``jpcrp`` を ``True`` と判定するが、
    本関数は ``jpigp`` のみを ``True`` と判定する。この非対称性は Wave 3 の
    normalize で会計基準判別ロジックが吸収する。

    Args:
        module_group: ``_namespaces.classify_namespace()`` で取得した
            ``NamespaceInfo.module_group`` の値。

    Returns:
        IFRS 固有のモジュールグループであれば ``True``。
    """
    return module_group in _IFRS_MODULE_GROUPS


# ---------------------------------------------------------------------------
# 公開 API — プロファイル
# ---------------------------------------------------------------------------

_PROFILE = IFRSProfile(
    standard_id="ifrs",
    display_name_ja="国際財務報告基準",
    display_name_en="IFRS",
    module_groups=_IFRS_MODULE_GROUPS,
    canonical_key_count=len(_ALL_MAPPINGS),
    has_ordinary_income=False,
    has_extraordinary_items=False,
)


def get_profile() -> IFRSProfile:
    """IFRS 会計基準のプロファイルを返す。

    ``standards/normalize`` (Wave 3) が全会計基準のプロファイルを
    並列に取得する際のエントリーポイント。Lane 3 の ``get_profile()`` と対称。

    Returns:
        ``IFRSProfile``。
    """
    return _PROFILE

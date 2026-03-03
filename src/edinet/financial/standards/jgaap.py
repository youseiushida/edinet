"""J-GAAP 科目の正規化マッピング。

J-GAAP（日本基準）の主要 concept について、会計基準横断の正規化キー
（canonical key）とメタデータを提供する。Wave 3 の ``standards/normalize``
が「売上高を指定すれば会計基準に依存せず値を取得できる」統一レイヤーを
実現するための入力データモジュール。

対象モジュールグループ: ``jppfs``（財務諸表本表）、``jpcrp``（有報等記載事項）、
``jpdei``（DEI 情報）。

典型的な使用例::

    from edinet.financial.standards.jgaap import lookup, canonical_key, reverse_lookup

    # concept ローカル名 → 正規化キー
    mapping = lookup("NetSales")
    assert mapping is not None
    assert mapping.canonical_key == "revenue"

    # 正規化キー → ConceptMapping（逆引き）
    rev = reverse_lookup("revenue")
    assert rev is not None
    assert rev.concept == "NetSales"

    # 簡易版
    assert canonical_key("NetSales") == "revenue"
"""

from __future__ import annotations

from dataclasses import dataclass

from edinet.models.financial import StatementType
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "ConceptMapping",
    "JGAAPProfile",
    "all_canonical_keys",
    "all_mappings",
    "canonical_key",
    "get_profile",
    "is_jgaap_module",
    "jgaap_specific_concepts",
    "lookup",
    "mappings_for_statement",
    "reverse_lookup",
]

# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConceptMapping:
    """J-GAAP concept の正規化マッピング。

    1 つの jppfs_cor / jpcrp_cor concept について、正規化キーと
    メタデータを保持する。standards/normalize (Wave 3) が
    会計基準横断の統一アクセスを提供する際の入力データ。

    Attributes:
        concept: jppfs_cor / jpcrp_cor のローカル名
            （例: ``"NetSales"``）。
            バージョン非依存。
        canonical_key: 正規化キー（例: ``"revenue"``）。
            会計基準間で共通の文字列識別子。
            IFRS の Revenue も同じ ``"revenue"`` キーにマッピングされる。
            小文字 snake_case。
        statement_type: 所属する財務諸表。PL / BS / CF。
            複数に属する場合は主たる所属先。
            主要経営指標（EPS 等）は None。
        is_jgaap_specific: J-GAAP 固有の概念か。
            True の場合、IFRS / US-GAAP に直接対応する概念がない。
            例: 経常利益（OrdinaryIncome）、特別利益（ExtraordinaryIncome）。
    """

    concept: str
    canonical_key: str
    statement_type: StatementType | None
    is_jgaap_specific: bool = False


@dataclass(frozen=True, slots=True)
class JGAAPProfile:
    """J-GAAP 会計基準のプロファイル（概要情報）。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に保持し、ディスパッチに使用する。

    Attributes:
        standard_id: 会計基準の識別子。``"japan_gaap"`` 固定。
        display_name_ja: 日本語表示名。
        display_name_en: 英語表示名。
        module_groups: この会計基準に関連する EDINET
            タクソノミモジュールグループの集合。
        canonical_key_count: 定義されている正規化キーの総数。
        has_ordinary_income: 経常利益の概念を持つか（J-GAAP 固有）。
        has_extraordinary_items: 特別利益/特別損失の概念を持つか。
    """

    standard_id: str
    display_name_ja: str
    display_name_en: str
    module_groups: frozenset[str]
    canonical_key_count: int
    has_ordinary_income: bool
    has_extraordinary_items: bool


# ---------------------------------------------------------------------------
# 名前空間判定
# ---------------------------------------------------------------------------

_JGAAP_MODULE_GROUPS: frozenset[str] = frozenset({"jppfs", "jpcrp", "jpdei"})

# ---------------------------------------------------------------------------
# マッピングレジストリ
# ---------------------------------------------------------------------------

_PL = StatementType.INCOME_STATEMENT
_BS = StatementType.BALANCE_SHEET
_CF = StatementType.CASH_FLOW_STATEMENT

_PL_MAPPINGS: tuple[ConceptMapping, ...] = (
    ConceptMapping("NetSales", CK.REVENUE, _PL),
    ConceptMapping("CostOfSales", CK.COST_OF_SALES, _PL),
    ConceptMapping("GrossProfit", CK.GROSS_PROFIT, _PL),
    ConceptMapping("SellingGeneralAndAdministrativeExpenses", CK.SGA_EXPENSES, _PL),
    ConceptMapping("OperatingIncome", CK.OPERATING_INCOME, _PL),
    ConceptMapping("NonOperatingIncome", CK.NON_OPERATING_INCOME, _PL, is_jgaap_specific=True),
    ConceptMapping("NonOperatingExpenses", CK.NON_OPERATING_EXPENSES, _PL, is_jgaap_specific=True),
    ConceptMapping("OrdinaryIncome", CK.ORDINARY_INCOME, _PL, is_jgaap_specific=True),
    ConceptMapping("ExtraordinaryIncome", CK.EXTRAORDINARY_INCOME, _PL, is_jgaap_specific=True),
    ConceptMapping("ExtraordinaryLoss", CK.EXTRAORDINARY_LOSS, _PL, is_jgaap_specific=True),
    ConceptMapping("IncomeBeforeIncomeTaxes", CK.INCOME_BEFORE_TAX, _PL),
    ConceptMapping("IncomeTaxes", CK.INCOME_TAXES, _PL),
    ConceptMapping("IncomeTaxesDeferred", CK.INCOME_TAXES_DEFERRED, _PL),
    ConceptMapping("ProfitLoss", CK.NET_INCOME, _PL),
    ConceptMapping("ProfitLossAttributableToOwnersOfParent", CK.NET_INCOME_PARENT, _PL),
    ConceptMapping("ProfitLossAttributableToNonControllingInterests", CK.NET_INCOME_MINORITY, _PL),
)

_BS_MAPPINGS: tuple[ConceptMapping, ...] = (
    ConceptMapping("CashAndDeposits", CK.CASH_AND_DEPOSITS, _BS),
    ConceptMapping("NotesAndAccountsReceivableTrade", CK.TRADE_RECEIVABLES, _BS),
    ConceptMapping("Inventories", CK.INVENTORIES, _BS),
    ConceptMapping("CurrentAssets", CK.CURRENT_ASSETS, _BS),
    ConceptMapping("NoncurrentAssets", CK.NONCURRENT_ASSETS, _BS),
    ConceptMapping("PropertyPlantAndEquipment", CK.PPE, _BS),
    ConceptMapping("IntangibleAssets", CK.INTANGIBLE_ASSETS, _BS),
    ConceptMapping("InvestmentsAndOtherAssets", CK.INVESTMENTS_AND_OTHER, _BS),
    ConceptMapping("DeferredAssets", CK.DEFERRED_ASSETS, _BS),
    ConceptMapping("Assets", CK.TOTAL_ASSETS, _BS),
    ConceptMapping("NotesAndAccountsPayableTrade", CK.TRADE_PAYABLES, _BS),
    ConceptMapping("CurrentLiabilities", CK.CURRENT_LIABILITIES, _BS),
    ConceptMapping("NoncurrentLiabilities", CK.NONCURRENT_LIABILITIES, _BS),
    ConceptMapping("Liabilities", CK.TOTAL_LIABILITIES, _BS),
    ConceptMapping("CapitalStock", CK.CAPITAL_STOCK, _BS),
    ConceptMapping("CapitalSurplus", CK.CAPITAL_SURPLUS, _BS),
    ConceptMapping("RetainedEarnings", CK.RETAINED_EARNINGS, _BS),
    ConceptMapping("TreasuryStock", CK.TREASURY_STOCK, _BS),
    ConceptMapping("ShareholdersEquity", CK.SHAREHOLDERS_EQUITY, _BS),
    ConceptMapping("ValuationAndTranslationAdjustments", CK.OCI_ACCUMULATED, _BS),
    ConceptMapping("SubscriptionRightsToShares", CK.STOCK_OPTIONS, _BS),
    ConceptMapping("NonControllingInterests", CK.MINORITY_INTERESTS, _BS),
    ConceptMapping("NetAssets", CK.NET_ASSETS, _BS),
    ConceptMapping("LiabilitiesAndNetAssets", CK.LIABILITIES_AND_NET_ASSETS, _BS),
)

_CF_MAPPINGS: tuple[ConceptMapping, ...] = (
    # --- 営業 CF 内訳 ---
    ConceptMapping("DepreciationAndAmortizationOpeCF", CK.DEPRECIATION_CF, _CF),
    ConceptMapping("ImpairmentLossOpeCF", CK.IMPAIRMENT_LOSS_CF, _CF),
    ConceptMapping("AmortizationOfGoodwillOpeCF", CK.GOODWILL_AMORTIZATION_CF, _CF),
    ConceptMapping("IncreaseDecreaseInAllowanceForDoubtfulAccountsOpeCF", CK.ALLOWANCE_DOUBTFUL_CHANGE_CF, _CF),
    ConceptMapping("InterestAndDividendsIncomeOpeCF", CK.INTEREST_DIVIDEND_INCOME_CF, _CF),
    ConceptMapping("InterestExpensesOpeCF", CK.INTEREST_EXPENSE_CF, _CF),
    ConceptMapping("ForeignExchangeLossesGainsOpeCF", CK.FX_LOSS_GAIN_CF, _CF),
    ConceptMapping("EquityInEarningsLossesOfAffiliatesOpeCF", CK.EQUITY_METHOD_CF, _CF),
    ConceptMapping("LossGainOnSalesOfPropertyPlantAndEquipmentOpeCF", CK.PPE_SALE_LOSS_GAIN_CF, _CF),
    ConceptMapping("DecreaseIncreaseInNotesAndAccountsReceivableTradeOpeCF", CK.TRADE_RECEIVABLES_CHANGE_CF, _CF),
    ConceptMapping("DecreaseIncreaseInInventoriesOpeCF", CK.INVENTORIES_CHANGE_CF, _CF),
    ConceptMapping("IncreaseDecreaseInNotesAndAccountsPayableTradeOpeCF", CK.TRADE_PAYABLES_CHANGE_CF, _CF),
    ConceptMapping("OtherNetOpeCF", CK.OTHER_OPERATING_CF, _CF),
    ConceptMapping("SubtotalOpeCF", CK.SUBTOTAL_OPERATING_CF, _CF),
    ConceptMapping("IncomeTaxesPaidOpeCF", CK.INCOME_TAXES_PAID_CF, _CF),
    # --- 営業 CF 合計 ---
    ConceptMapping("NetCashProvidedByUsedInOperatingActivities", CK.OPERATING_CF, _CF),
    # --- 投資 CF 内訳 ---
    ConceptMapping("PurchaseOfPropertyPlantAndEquipmentInvCF", CK.PURCHASE_PPE_CF, _CF),
    ConceptMapping("ProceedsFromSalesOfPropertyPlantAndEquipmentInvCF", CK.PROCEEDS_PPE_SALE_CF, _CF),
    ConceptMapping("PurchaseOfInvestmentSecuritiesInvCF", CK.PURCHASE_INVESTMENT_SECURITIES_CF, _CF),
    ConceptMapping("ProceedsFromSalesOfInvestmentSecuritiesInvCF", CK.PROCEEDS_INVESTMENT_SECURITIES_CF, _CF),
    ConceptMapping("PaymentsOfLoansReceivableInvCF", CK.LOANS_PAID_CF, _CF),
    ConceptMapping("CollectionOfLoansReceivableInvCF", CK.LOANS_COLLECTED_CF, _CF),
    ConceptMapping("OtherNetInvCF", CK.OTHER_INVESTING_CF, _CF),
    # --- 投資 CF 合計 ---
    ConceptMapping("NetCashProvidedByUsedInInvestmentActivities", CK.INVESTING_CF, _CF),
    # --- 財務 CF 内訳 ---
    ConceptMapping("ProceedsFromLongTermLoansPayableFinCF", CK.PROCEEDS_LONG_TERM_LOANS_CF, _CF),
    ConceptMapping("RepaymentOfLongTermLoansPayableFinCF", CK.REPAYMENT_LONG_TERM_LOANS_CF, _CF),
    ConceptMapping("ProceedsFromIssuanceOfBondsFinCF", CK.PROCEEDS_BONDS_CF, _CF),
    ConceptMapping("RedemptionOfBondsFinCF", CK.REDEMPTION_BONDS_CF, _CF),
    ConceptMapping("PurchaseOfTreasuryStockFinCF", CK.PURCHASE_TREASURY_STOCK_CF, _CF),
    ConceptMapping("CashDividendsPaidFinCF", CK.DIVIDENDS_PAID_CF, _CF),
    ConceptMapping("OtherNetFinCF", CK.OTHER_FINANCING_CF, _CF),
    # --- 財務 CF 合計 ---
    ConceptMapping("NetCashProvidedByUsedInFinancingActivities", CK.FINANCING_CF, _CF),
    # --- 換算差額等 ---
    ConceptMapping("EffectOfExchangeRateChangeOnCashAndCashEquivalents", CK.FX_EFFECT_ON_CASH, _CF),
    ConceptMapping("NetIncreaseDecreaseInCashAndCashEquivalents", CK.NET_CHANGE_IN_CASH, _CF),
    ConceptMapping("IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeOfScopeOfConsolidationCCE", CK.CONSOLIDATION_SCOPE_CHANGE_CASH, _CF),
    # --- 期首・期末残高 ---
    # CashAndCashEquivalents (periodType="instant") は ConceptMapping に
    # 登録しない。1 concept : 1 key 制約のため期首/期末の 2 キーを
    # 表現できない。statements._absorb_cf_instant_balances() が
    # ConceptSet の preferred_label (periodStartLabel/periodEndLabel) から
    # 動的検出し、ポストプロセスで CF に吸収する。
)

_KPI_MAPPINGS: tuple[ConceptMapping, ...] = (
    ConceptMapping("BasicEarningsLossPerShareSummaryOfBusinessResults", CK.EPS, None),
    ConceptMapping("DilutedEarningsPerShareSummaryOfBusinessResults", CK.EPS_DILUTED, None),
    ConceptMapping("NetAssetsPerShareSummaryOfBusinessResults", CK.BPS, None),
    ConceptMapping("DividendPerShareDividendsOfSurplus", CK.DPS, None),
    ConceptMapping("EquityToAssetRatioSummaryOfBusinessResults", CK.EQUITY_RATIO, None),
    ConceptMapping("RateOfReturnOnEquitySummaryOfBusinessResults", CK.ROE, None),
    ConceptMapping("PriceEarningsRatioSummaryOfBusinessResults", CK.PER, None),
    ConceptMapping("NumberOfEmployees", CK.EMPLOYEES, None),
)

# --- SummaryOfBusinessResults マッピング（jpcrp_cor 由来の経営指標サマリー） ---
# extract_values() で canonical key による全業種横断取得を可能にする。
# PL 本体の concept と同じ CK にマッピングするため、canonical_key に重複が生じる。
# _ALL_MAPPINGS で _SUMMARY_MAPPINGS を先頭に配置し、
# 詳細科目（PL 本体）が reverse_lookup で優先されるようにする。
_SUMMARY_MAPPINGS: tuple[ConceptMapping, ...] = (
    # Revenue（業種別フォールバック）
    ConceptMapping("NetSalesSummaryOfBusinessResults", CK.REVENUE, None),
    ConceptMapping("OrdinaryIncomeSummaryOfBusinessResults", CK.REVENUE, None),  # 銀行業（経常収益）
    ConceptMapping("OperatingRevenue1SummaryOfBusinessResults", CK.REVENUE, None),  # 鉄道業（営業収益）
    ConceptMapping("OperatingRevenue2SummaryOfBusinessResults", CK.REVENUE, None),
    ConceptMapping("GrossOperatingRevenueSummaryOfBusinessResults", CK.REVENUE, None),
    ConceptMapping("RevenueKeyFinancialData", CK.REVENUE, None),
    # Operating Income（提出者独自タクソノミ。標準 XSD に存在しないが実データに出現）
    ConceptMapping("OperatingIncomeSummaryOfBusinessResults", CK.OPERATING_INCOME, None),
    # Ordinary Income
    ConceptMapping("OrdinaryIncomeLossSummaryOfBusinessResults", CK.ORDINARY_INCOME, None),
    # Net Income
    ConceptMapping("NetIncomeLossSummaryOfBusinessResults", CK.NET_INCOME, None),
    ConceptMapping("ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults", CK.NET_INCOME_PARENT, None),
    # Comprehensive Income
    ConceptMapping("ComprehensiveIncomeSummaryOfBusinessResults", CK.COMPREHENSIVE_INCOME, None),
    # Total Assets
    ConceptMapping("TotalAssetsSummaryOfBusinessResults", CK.TOTAL_ASSETS, None),
    # Net Assets
    ConceptMapping("NetAssetsSummaryOfBusinessResults", CK.NET_ASSETS, None),
    # Capital Stock
    ConceptMapping("CapitalStockSummaryOfBusinessResults", CK.CAPITAL_STOCK, None),
    # Cash Flow
    ConceptMapping("NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults", CK.OPERATING_CF, None),
    ConceptMapping("NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults", CK.INVESTING_CF, None),
    ConceptMapping("NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults", CK.FINANCING_CF, None),
    ConceptMapping("CashAndCashEquivalentsSummaryOfBusinessResults", CK.CASH_END, None),
    # Shares / Dividend
    ConceptMapping("DividendPaidPerShareSummaryOfBusinessResults", CK.DPS, None),
)

# ---------------------------------------------------------------------------
# 統合レジストリとインデックス
# ---------------------------------------------------------------------------

_ALL_MAPPINGS: tuple[ConceptMapping, ...] = (
    *_SUMMARY_MAPPINGS,  # サマリーを先に → 詳細科目が後勝ちで reverse_lookup 優先
    *_PL_MAPPINGS,
    *_BS_MAPPINGS,
    *_CF_MAPPINGS,
    *_KPI_MAPPINGS,
)

# concept ローカル名 → ConceptMapping
_CONCEPT_INDEX: dict[str, ConceptMapping] = {
    m.concept: m for m in _ALL_MAPPINGS
}

# canonical_key → ConceptMapping
_CANONICAL_INDEX: dict[str, ConceptMapping] = {
    m.canonical_key: m for m in _ALL_MAPPINGS
}

# StatementType → tuple[ConceptMapping, ...]
_STATEMENT_INDEX: dict[StatementType, tuple[ConceptMapping, ...]] = {
    st: tuple(m for m in _ALL_MAPPINGS if m.statement_type == st)
    for st in StatementType
}

# J-GAAP 固有科目（is_jgaap_specific=True）
_JGAAP_SPECIFIC: tuple[ConceptMapping, ...] = tuple(
    m for m in _ALL_MAPPINGS if m.is_jgaap_specific
)

# 全正規化キーの集合
_ALL_CANONICAL_KEYS: frozenset[str] = frozenset(_CANONICAL_INDEX)

# ---------------------------------------------------------------------------
# レジストリ検証（モジュールロード時に実行）
# ---------------------------------------------------------------------------


def _validate_registry() -> None:
    """マッピングレジストリの整合性を検証する。

    モジュールロード時に呼び出され、データ定義のミスを早期に検出する。
    ``assert`` ではなく ``ValueError`` を使用し、``python -O`` でも動作する。

    Raises:
        ValueError: レジストリに不整合がある場合。
    """
    concepts = [m.concept for m in _ALL_MAPPINGS]
    if len(concepts) != len(set(concepts)):
        duplicates = [c for c in concepts if concepts.count(c) > 1]
        raise ValueError(f"concept が重複しています: {set(duplicates)}")

    # canonical_key の重複は許容する（同一 CK に詳細科目とサマリー科目の
    # 両方がマッピングされるケース: NetSales + NetSalesSummaryOfBusinessResults）。
    # concept ローカル名の一意性のみ検証する。

    for m in _ALL_MAPPINGS:
        if not m.concept:
            raise ValueError("空の concept が登録されています")
        if not m.canonical_key:
            raise ValueError(
                f"{m.concept} の canonical_key が空です"
            )


_validate_registry()

# ---------------------------------------------------------------------------
# プロファイル
# ---------------------------------------------------------------------------

_PROFILE = JGAAPProfile(
    standard_id="japan_gaap",
    display_name_ja="日本基準（J-GAAP）",
    display_name_en="Japanese GAAP",
    module_groups=_JGAAP_MODULE_GROUPS,
    canonical_key_count=len(_ALL_MAPPINGS),
    has_ordinary_income=True,
    has_extraordinary_items=True,
)

# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def lookup(concept: str) -> ConceptMapping | None:
    """J-GAAP concept ローカル名からマッピング情報を取得する。

    Args:
        concept: jppfs_cor / jpcrp_cor のローカル名
            （例: ``"NetSales"``）。

    Returns:
        ConceptMapping。登録されていない concept の場合は None。
    """
    return _CONCEPT_INDEX.get(concept)


def canonical_key(concept: str) -> str | None:
    """J-GAAP concept ローカル名を正規化キーにマッピングする。

    ``lookup()`` の簡易版。正規化キーのみを返す。

    Args:
        concept: jppfs_cor / jpcrp_cor のローカル名。

    Returns:
        正規化キー文字列。登録されていない concept の場合は None。
    """
    m = _CONCEPT_INDEX.get(concept)
    return m.canonical_key if m is not None else None


def reverse_lookup(key: str) -> ConceptMapping | None:
    """正規化キーから J-GAAP の ConceptMapping を取得する（逆引き）。

    一般事業会社の主要科目に限定した 1:1 マッピング。
    銀行業・保険業等の業種固有科目は Phase 4 で sector/ モジュールとして
    別途マッピングされるため、本関数の対象外。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        ConceptMapping。該当する J-GAAP concept がない場合は None。
    """
    return _CANONICAL_INDEX.get(key)


def mappings_for_statement(
    statement_type: StatementType,
) -> tuple[ConceptMapping, ...]:
    """指定した財務諸表タイプの J-GAAP マッピングを返す。

    定義順（タクソノミの標準表示順序に準拠）。
    ``statement_type=None`` の ConceptMapping（主要経営指標）は
    本関数では取得できない。``all_mappings()`` を使用すること。

    Args:
        statement_type: PL / BS / CF。

    Returns:
        ConceptMapping のタプル（定義順）。
        未登録の StatementType の場合は空タプル。
    """
    return _STATEMENT_INDEX.get(statement_type, ())


def all_mappings() -> tuple[ConceptMapping, ...]:
    """全ての J-GAAP マッピングを返す。

    PL → BS → CF → その他（statement_type=None）の順、
    各グループ内は定義順。

    Returns:
        全 ConceptMapping のタプル。
    """
    return _ALL_MAPPINGS


def all_canonical_keys() -> frozenset[str]:
    """J-GAAP で定義されている全正規化キーの集合を返す。

    Returns:
        正規化キーのフローズンセット。
    """
    return _ALL_CANONICAL_KEYS


def jgaap_specific_concepts() -> tuple[ConceptMapping, ...]:
    """J-GAAP 固有の概念（他会計基準に対応概念がないもの）を返す。

    対象科目: 営業外収益（NonOperatingIncome）、営業外費用（NonOperatingExpenses）、
    経常利益（OrdinaryIncome）、特別利益（ExtraordinaryIncome）、
    特別損失（ExtraordinaryLoss）。

    Returns:
        ``is_jgaap_specific=True`` の ConceptMapping のタプル。
    """
    return _JGAAP_SPECIFIC


def is_jgaap_module(module_group: str) -> bool:
    """module_group が J-GAAP に属するかどうかを判定する。

    J-GAAP に関連するモジュールグループ: ``"jppfs"``, ``"jpcrp"``, ``"jpdei"``。

    注意: IFRS 企業でも jppfs はディメンション要素等で併用される
    ため、この関数の結果だけで会計基準を断定してはならない。
    会計基準の判別は standards/detect を使用すること。

    Args:
        module_group: _namespaces.classify_namespace() で取得した
            NamespaceInfo.module_group の値。

    Returns:
        J-GAAP に関連するモジュールグループであれば True。
    """
    return module_group in _JGAAP_MODULE_GROUPS


def get_profile() -> JGAAPProfile:
    """J-GAAP 会計基準のプロファイルを返す。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に取得する際のエントリーポイント。

    Returns:
        JGAAPProfile。
    """
    return _PROFILE

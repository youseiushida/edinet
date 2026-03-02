"""銀行業（bk1/bk2）の業種固有 sector_key マッピング。

銀行業は PL・BS・CF の勘定科目体系が一般事業会社と根本的に異なるため、
``standards/jgaap.py`` とは独立した専用マッピングを定義する。
API 設計は ``jgaap.py`` と対称的であり、Wave 3 の ``standards/normalize``
が業種横断の統一アクセスを実現するための入力データモジュール。

対象業種コード: ``bk1``（銀行・信託業）、``bk2``（銀行・信託業（特定取引勘定設置銀行））。

典型的な使用例::

    from edinet.financial.sector.banking import lookup, sector_key, reverse_lookup

    # 銀行業固有の concept → 正規化キー
    mapping = lookup("OrdinaryIncomeBNK")
    assert mapping is not None
    assert mapping.sector_key == "ordinary_revenue_bnk"

    # 正規化キー → SectorConceptMapping（逆引き）
    rev = reverse_lookup("ordinary_revenue_bnk")
    assert rev is not None
    assert rev.concept == "OrdinaryIncomeBNK"

    # 一般事業会社との対応関係
    assert mapping.general_equivalent == "revenue"

    # 銀行業の判定
    from edinet.financial.sector.banking import is_banking_industry
    assert is_banking_industry("bk1") is True
"""

from __future__ import annotations

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "BANKING_INDUSTRY_CODES",
    "BankingConceptMapping",
    "all_mappings",
    "all_sector_keys",
    "banking_specific_concepts",
    "banking_to_general_map",
    "from_general_key",
    "general_equivalent",
    "get_profile",
    "is_banking_concept",
    "is_banking_industry",
    "lookup",
    "registry",
    "reverse_lookup",
    "sector_key",
    "to_general_key",
]

# ---------------------------------------------------------------------------
# 後方互換エイリアス
# ---------------------------------------------------------------------------

BankingConceptMapping = SectorConceptMapping
"""後方互換エイリアス。新規コードでは ``SectorConceptMapping`` を使用すること。"""

# ---------------------------------------------------------------------------
# 名前空間判定
# ---------------------------------------------------------------------------

BANKING_INDUSTRY_CODES: frozenset[str] = frozenset({"bk1", "bk2"})
"""銀行業の業種コード集合。"""

# ---------------------------------------------------------------------------
# プロファイル
# ---------------------------------------------------------------------------

_PROFILE = SectorProfile(
    sector_id="banking",
    display_name_ja="銀行・信託業",
    display_name_en="Banking and trust",
    industry_codes=BANKING_INDUSTRY_CODES,
    concept_suffix="BNK",
    pl_structure_note="経常収益・経常費用の二段階構造。",
    has_consolidated_template=True,
    cf_method="both",
)

# ---------------------------------------------------------------------------
# マッピングレジストリ
# ---------------------------------------------------------------------------

_CODES = BANKING_INDUSTRY_CODES

# --- PL: 銀行業固有科目 (13件) ---

_PL_BANKING_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OrdinaryIncomeBNK",
        sector_key="ordinary_revenue_bnk",
        industry_codes=_CODES,
        general_equivalent=CK.REVENUE,
    ),
    SectorConceptMapping(
        concept="InterestIncomeOIBNK",
        sector_key="interest_income_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="FeesAndCommissionsOIBNK",
        sector_key="fees_and_commissions_income_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="TradingIncomeOIBNK",
        sector_key="trading_income_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherOrdinaryIncomeOIBNK",
        sector_key="other_ordinary_income_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherIncomeOIBNK",
        sector_key="other_income_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OrdinaryExpensesBNK",
        sector_key="ordinary_expenses_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="InterestExpensesOEBNK",
        sector_key="interest_expenses_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="FeesAndCommissionsPaymentsOEBNK",
        sector_key="fees_and_commissions_expenses_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="TradingExpensesOEBNK",
        sector_key="trading_expenses_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherOrdinaryExpensesOEBNK",
        sector_key="other_ordinary_expenses_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="GeneralAndAdministrativeExpensesOEBNK",
        sector_key="general_admin_expenses_bnk",
        industry_codes=_CODES,
        general_equivalent=CK.SGA_EXPENSES,
    ),
    SectorConceptMapping(
        concept="OtherExpensesOEBNK",
        sector_key="other_expenses_bnk",
        industry_codes=_CODES,
    ),
)

# --- PL: 一般事業会社と共通の科目 (7件) ---
# sector_key は jgaap.py と完全一致。

_COMMON_PL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OrdinaryIncome",
        sector_key="ordinary_income",
        industry_codes=_CODES,
        general_equivalent=CK.ORDINARY_INCOME,
    ),
    SectorConceptMapping(
        concept="ExtraordinaryIncome",
        sector_key="extraordinary_income",
        industry_codes=_CODES,
        general_equivalent=CK.EXTRAORDINARY_INCOME,
    ),
    SectorConceptMapping(
        concept="ExtraordinaryLoss",
        sector_key="extraordinary_loss",
        industry_codes=_CODES,
        general_equivalent=CK.EXTRAORDINARY_LOSS,
    ),
    SectorConceptMapping(
        concept="IncomeBeforeIncomeTaxes",
        sector_key="income_before_tax",
        industry_codes=_CODES,
        general_equivalent=CK.INCOME_BEFORE_TAX,
    ),
    SectorConceptMapping(
        concept="ProfitLoss",
        sector_key="net_income",
        industry_codes=_CODES,
        general_equivalent=CK.NET_INCOME,
    ),
    SectorConceptMapping(
        concept="ProfitLossAttributableToOwnersOfParent",
        sector_key="net_income_parent",
        industry_codes=_CODES,
        general_equivalent=CK.NET_INCOME_PARENT,
    ),
    SectorConceptMapping(
        concept="ProfitLossAttributableToNonControllingInterests",
        sector_key="net_income_minority",
        industry_codes=_CODES,
        general_equivalent=CK.NET_INCOME_MINORITY,
    ),
)

# --- BS: 銀行業固有科目 (12件) ---

_BS_BANKING_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="CashAndDueFromBanksAssetsBNK",
        sector_key="cash_due_from_banks_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CallLoansAndBillsBoughtAssetsBNK",
        sector_key="call_loans_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="ReceivablesUnderResaleAgreementsAssetsBNK",
        sector_key="receivables_resale_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="SecuritiesAssetsBNK",
        sector_key="securities_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="LoansAndBillsDiscountedAssetsBNK",
        sector_key="loans_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="ForeignExchangesAssetsBNK",
        sector_key="foreign_exchange_assets_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherAssetsAssetsBNK",
        sector_key="other_assets_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="DepositsLiabilitiesBNK",
        sector_key="deposits_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CallMoneyAndBillsSoldLiabilitiesBNK",
        sector_key="call_money_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="BorrowedMoneyLiabilitiesBNK",
        sector_key="borrowed_money_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="ForeignExchangesLiabilitiesBNK",
        sector_key="foreign_exchange_liabilities_bnk",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherLiabilitiesLiabilitiesBNK",
        sector_key="other_liabilities_bnk",
        industry_codes=_CODES,
    ),
)

# --- BS: 一般事業会社と共通の科目 (3件) ---

_COMMON_BS_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="Assets",
        sector_key="total_assets",
        industry_codes=_CODES,
        general_equivalent=CK.TOTAL_ASSETS,
    ),
    SectorConceptMapping(
        concept="Liabilities",
        sector_key="total_liabilities",
        industry_codes=_CODES,
        general_equivalent=CK.TOTAL_LIABILITIES,
    ),
    SectorConceptMapping(
        concept="NetAssets",
        sector_key="net_assets",
        industry_codes=_CODES,
        general_equivalent=CK.NET_ASSETS,
    ),
)

# --- CF: 直接法固有科目 (4件) ---

_CF_DIRECT_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="CollectionOfLoansReceivableOpeCFBNK",
        sector_key="cf_direct_collection_loans_bnk",
        industry_codes=_CODES,
        mapping_note="直接法 CF のみ",
    ),
    SectorConceptMapping(
        concept="PaymentsForWithdrawalOfDepositsOpeCFBNK",
        sector_key="cf_direct_deposit_withdrawals_bnk",
        industry_codes=_CODES,
        mapping_note="直接法 CF のみ",
    ),
    SectorConceptMapping(
        concept="ProceedsFromInterestOnLoansOpeCFBNK",
        sector_key="cf_direct_interest_received_bnk",
        industry_codes=_CODES,
        mapping_note="直接法 CF のみ",
    ),
    SectorConceptMapping(
        concept="PaymentsForInterestExpensesForDepositOpeCFBNK",
        sector_key="cf_direct_interest_paid_bnk",
        industry_codes=_CODES,
        mapping_note="直接法 CF のみ",
    ),
)

# --- CF: 間接法固有科目 (3件) ---

_CF_INDIRECT_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    # IncomeBeforeIncomeTaxes は _COMMON_PL_MAPPINGS で登録済みのため
    # CF 間接法でも同一 concept を使用するがここでは重複登録しない。
    SectorConceptMapping(
        concept="DepreciationAndAmortizationOpeCF",
        sector_key="cf_indirect_depreciation_bnk",
        industry_codes=_CODES,
        mapping_note="間接法 CF のみ。タクソノミ上は一般事業会社と共通の concept。",
    ),
    SectorConceptMapping(
        concept="NetDecreaseIncreaseInLoansAndBillsDiscountedOpeCFBNK",
        sector_key="cf_indirect_loans_change_bnk",
        industry_codes=_CODES,
        mapping_note="間接法 CF のみ",
    ),
    SectorConceptMapping(
        concept="NetIncreaseDecreaseInDepositOpeCFBNK",
        sector_key="cf_indirect_deposits_change_bnk",
        industry_codes=_CODES,
        mapping_note="間接法 CF のみ",
    ),
)

# --- CF: 一般事業会社と共通の科目 (3件) ---

_COMMON_CF_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="NetCashProvidedByUsedInOperatingActivities",
        sector_key="operating_cf",
        industry_codes=_CODES,
        general_equivalent=CK.OPERATING_CF,
    ),
    SectorConceptMapping(
        concept="NetCashProvidedByUsedInInvestmentActivities",
        sector_key="investing_cf",
        industry_codes=_CODES,
        general_equivalent=CK.INVESTING_CF,
    ),
    SectorConceptMapping(
        concept="NetCashProvidedByUsedInFinancingActivities",
        sector_key="financing_cf",
        industry_codes=_CODES,
        general_equivalent=CK.FINANCING_CF,
    ),
)

# ---------------------------------------------------------------------------
# レジストリ構築
# ---------------------------------------------------------------------------

_ALL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    *_PL_BANKING_MAPPINGS,
    *_COMMON_PL_MAPPINGS,
    *_BS_BANKING_MAPPINGS,
    *_COMMON_BS_MAPPINGS,
    *_CF_DIRECT_MAPPINGS,
    *_CF_INDIRECT_MAPPINGS,
    *_COMMON_CF_MAPPINGS,
)

registry = SectorRegistry(profile=_PROFILE, mappings=_ALL_MAPPINGS)
"""銀行業の SectorRegistry インスタンス。"""

# 銀行業固有の concept 集合（一般事業会社に対応がないもの）
_BANKING_SPECIFIC_CONCEPTS: tuple[SectorConceptMapping, ...] = tuple(
    m for m in _ALL_MAPPINGS if m.general_equivalent is None
)

# ---------------------------------------------------------------------------
# 公開 API（レジストリへのデリゲート）
# ---------------------------------------------------------------------------

lookup = registry.lookup
sector_key = registry.sector_key
reverse_lookup = registry.reverse_lookup
all_mappings = registry.all_mappings
all_sector_keys = registry.all_sector_keys
to_general_key = registry.to_general_key
from_general_key = registry.from_general_key

# ---------------------------------------------------------------------------
# 銀行業固有 API
# ---------------------------------------------------------------------------


def is_banking_concept(concept: str) -> bool:
    """指定した concept が銀行業固有のものかを判定する。

    ``general_equivalent`` が None のマッピング（一般事業会社に対応がないもの）
    を銀行業固有科目とみなす。

    Args:
        concept: タクソノミのローカル名。

    Returns:
        銀行業固有の concept であれば True。
    """
    m = registry.lookup(concept)
    return m is not None and m.general_equivalent is None


def banking_specific_concepts() -> tuple[SectorConceptMapping, ...]:
    """銀行業固有の概念（一般事業会社に対応がないもの）を返す。

    ``general_equivalent`` が None のマッピングのみを返す。
    定義順（PL → BS → CF）を維持。

    Returns:
        銀行業固有の SectorConceptMapping のタプル。
    """
    return _BANKING_SPECIFIC_CONCEPTS


def general_equivalent(concept: str) -> str | None:
    """銀行業 concept の一般事業会社における canonical_key を返す。

    Args:
        concept: タクソノミのローカル名。

    Returns:
        一般事業会社の canonical_key。対応がない場合は None。
        未登録の concept の場合も None。
    """
    return registry.to_general_key(concept)


def banking_to_general_map() -> dict[str, str]:
    """銀行業 sector_key → 一般事業会社 canonical_key のマッピング辞書を返す。

    ``general_equivalent`` が設定されているマッピングのみを含む。

    Returns:
        ``{banking_sector_key: general_canonical_key}`` の辞書。
    """
    return registry.to_general_map()


def get_profile() -> SectorProfile:
    """銀行業のプロファイルを返す。

    Returns:
        SectorProfile インスタンス。
    """
    return registry.get_profile()


def is_banking_industry(industry_code: str) -> bool:
    """業種コードが銀行業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        銀行業であれば True。
    """
    return industry_code in BANKING_INDUSTRY_CODES

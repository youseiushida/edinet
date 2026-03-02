"""保険業（in1/in2）の業種固有 sector_key マッピング。

保険業は PL・BS の勘定科目体系が一般事業会社と根本的に異なるため、
``standards/jgaap.py`` とは独立した専用マッピングを定義する。
API 設計は ``jgaap.py`` および ``sector/banking.py`` と対称的であり、
Wave 3 の ``standards/normalize`` が業種横断の統一アクセスを実現するための
入力データモジュール。

対象業種コード: ``in1``（生命保険業）、``in2``（損害保険業）。

INS ポリシー:
    本モジュールは保険業固有の INS サフィックス付き concept を中心に管理する。
    ただし利益行（OrdinaryIncome, ExtraordinaryIncome 等）はタクソノミ上
    一般事業会社と共通の concept（INS サフィックスなし）のため、
    それらも含めて管理する。
    TotalAssets, NetAssets 等の BS 共通科目は jgaap.py への
    フォールバックで解決する。normalize レイヤーが
    ``insurance.lookup() → None → jgaap.lookup()`` の
    フォールバックチェーンを実装する。

典型的な使用例::

    from edinet.financial.sector.insurance import lookup, sector_key, reverse_lookup

    # 保険業固有の concept → 正規化キー
    mapping = lookup("OperatingIncomeINS")
    assert mapping is not None
    assert mapping.sector_key == "ordinary_revenue_ins"

    # 正規化キー → SectorConceptMapping（逆引き）
    rev = reverse_lookup("ordinary_revenue_ins")
    assert rev is not None
    assert rev.concept == "OperatingIncomeINS"

    # 一般事業会社との対応関係
    assert mapping.general_equivalent == "revenue"

    # 保険業の判定
    from edinet.financial.sector.insurance import is_insurance_industry
    assert is_insurance_industry("in1") is True

Note:
    保険業タクソノミでは ``Operating`` が「経常」（ordinary）の意味で
    使用される。一般事業の ``OperatingIncome``（営業利益）とは異なる概念で
    あるにもかかわらず、同一の英語接頭辞が使われている。
    本モジュールの ``sector_key`` はタクソノミの concept 名ではなく
    **経済的意味** に基づいて命名している（``ordinary_revenue_ins``）ため、
    concept 名との乖離が生じる。保守時に concept 名だけを見て
    sector_key を推測しないこと。
"""

from __future__ import annotations

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "INSURANCE_INDUSTRY_CODES",
    "InsuranceConceptMapping",
    "all_mappings",
    "all_sector_keys",
    "from_general_key",
    "get_profile",
    "insurance_specific_concepts",
    "insurance_to_general_map",
    "is_insurance_industry",
    "lookup",
    "registry",
    "reverse_lookup",
    "sector_key",
    "to_general_key",
]

# ---------------------------------------------------------------------------
# 後方互換エイリアス
# ---------------------------------------------------------------------------

InsuranceConceptMapping = SectorConceptMapping
"""後方互換エイリアス。新規コードでは ``SectorConceptMapping`` を使用すること。"""

# ---------------------------------------------------------------------------
# 業種コード定数
# ---------------------------------------------------------------------------

INSURANCE_INDUSTRY_CODES: frozenset[str] = frozenset({"in1", "in2"})
"""保険業の業種コード集合。in1=生命保険業、in2=損害保険業。"""

# ---------------------------------------------------------------------------
# プロファイル
# ---------------------------------------------------------------------------

_CODES = INSURANCE_INDUSTRY_CODES

_PROFILE = SectorProfile(
    sector_id="insurance",
    display_name_ja="保険業",
    display_name_en="Insurance",
    industry_codes=_CODES,
    concept_suffix="INS",
    pl_structure_note="経常収益・経常費用の二段階構造。保険引受収益+資産運用収益。",
)

# ---------------------------------------------------------------------------
# マッピングレジストリ
# ---------------------------------------------------------------------------

# --- PL: 経常収益 (in1+in2 共通) ---

_PL_REVENUE_COMMON: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OperatingIncomeINS",
        # タクソノミ名は "Operating" だが意味は「経常収益」
        # ≠ 一般事業の OperatingIncome（営業利益）
        sector_key="ordinary_revenue_ins",
        industry_codes=_CODES,
        general_equivalent=CK.REVENUE,
        mapping_note="経常収益は売上高に相当するが、保険引受収益+資産運用収益+その他で構成される保険業固有の構造。",
    ),
    SectorConceptMapping(
        concept="InvestmentIncomeOIINS",
        sector_key="investment_income_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="InterestDividendsAndOtherIncomeOIINS",
        sector_key="interest_dividends_income_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="GainOnSalesOfSecuritiesOIINS",
        sector_key="gain_on_sales_of_securities_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherOperatingIncomeOIINS",
        sector_key="other_ordinary_income_ins",
        industry_codes=_CODES,
    ),
)

# --- PL: 経常収益 (in1 生命保険固有) ---

_PL_REVENUE_IN1: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="InsurancePremiumsAndOtherOIINS",
        sector_key="insurance_premiums_total_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="InsurancePremiumsOIINS",
        sector_key="insurance_premiums_ins",
        industry_codes=frozenset({"in1"}),
    ),
)

# --- PL: 経常収益 (in2 損害保険固有) ---

_PL_REVENUE_IN2: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="UnderwritingIncomeOIINS",
        sector_key="underwriting_income_ins",
        industry_codes=frozenset({"in2"}),
    ),
    SectorConceptMapping(
        concept="NetPremiumsWrittenOIINS",
        sector_key="net_premiums_written_ins",
        industry_codes=frozenset({"in2"}),
    ),
)

# --- PL: 経常費用 (in1+in2 共通) ---

_PL_EXPENSE_COMMON: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OperatingExpensesINS",
        sector_key="ordinary_expenses_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="ProvisionOfPolicyReserveAndOtherOEINS",
        sector_key="provision_policy_reserve_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="ProvisionOfOutstandingClaimsOEINS",
        sector_key="provision_outstanding_claims_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="InvestmentExpensesOEINS",
        sector_key="investment_expenses_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="InterestExpensesOEINS",
        sector_key="interest_expenses_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="LossOnSalesOfSecuritiesOEINS",
        sector_key="loss_on_sales_of_securities_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="LossOnValuationOfSecuritiesOEINS",
        sector_key="loss_on_valuation_of_securities_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherOperatingExpensesOEINS",
        sector_key="other_ordinary_expenses_ins",
        industry_codes=_CODES,
    ),
)

# --- PL: 経常費用 (in1 生命保険固有) ---

_PL_EXPENSE_IN1: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="InsuranceClaimsAndOtherOEINS",
        sector_key="insurance_claims_total_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="InsuranceClaimsOEINS",
        sector_key="insurance_claims_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="BenefitsOEINS",
        sector_key="benefits_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="SurrenderBenefitsOEINS",
        sector_key="surrender_benefits_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="ProvisionOfPolicyReserveOEINS",
        sector_key="provision_policy_reserve_detail_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="CommissionsAndCollectionFeesOEINS",
        sector_key="business_expenses_ins",
        industry_codes=frozenset({"in1"}),
        general_equivalent=CK.SGA_EXPENSES,
        mapping_note="保険業の「事業費」は一般事業の販管費に機能的に相当するが、構成要素が異なる（代理店手数料・集金費等を含む）。",
    ),
)

# --- PL: 経常費用 (in2 損害保険固有) ---

_PL_EXPENSE_IN2: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="UnderwritingExpensesOEINS",
        sector_key="underwriting_expenses_ins",
        industry_codes=frozenset({"in2"}),
    ),
    SectorConceptMapping(
        concept="NetLossPaidOEINS",
        sector_key="net_loss_paid_ins",
        industry_codes=frozenset({"in2"}),
    ),
    SectorConceptMapping(
        concept="LossAdjustmentExpensesOEINS",
        sector_key="loss_adjustment_expenses_ins",
        industry_codes=frozenset({"in2"}),
    ),
    SectorConceptMapping(
        concept="SalesAndAdministrativeExpensesOEINS",
        sector_key="sales_admin_expenses_ins",
        industry_codes=frozenset({"in2"}),
        general_equivalent=CK.SGA_EXPENSES,
        mapping_note="損害保険業の販管費。生保の「事業費」に機能的に対応。",
    ),
)

# --- PL: 利益 (共通) ---

_PL_PROFIT_COMMON: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OrdinaryIncome",
        sector_key="ordinary_income",
        industry_codes=_CODES,
        general_equivalent=CK.ORDINARY_INCOME,
        mapping_note="保険業では営業利益が存在せず、経常収益-経常費用=経常利益の直接計算。タクソノミ上は一般事業会社と共通の concept。",
    ),
    SectorConceptMapping(
        concept="ExtraordinaryIncome",
        sector_key="extraordinary_income",
        industry_codes=_CODES,
        general_equivalent=CK.EXTRAORDINARY_INCOME,
        mapping_note="タクソノミ上は一般事業会社と共通の concept（INS サフィックスなし）。",
    ),
    SectorConceptMapping(
        concept="ExtraordinaryLoss",
        sector_key="extraordinary_loss",
        industry_codes=_CODES,
        general_equivalent=CK.EXTRAORDINARY_LOSS,
        mapping_note="タクソノミ上は一般事業会社と共通の concept（INS サフィックスなし）。",
    ),
    SectorConceptMapping(
        concept="IncomeBeforeIncomeTaxes",
        sector_key="income_before_tax",
        industry_codes=_CODES,
        general_equivalent=CK.INCOME_BEFORE_TAX,
        mapping_note="タクソノミ上は一般事業会社と共通の concept（INS サフィックスなし）。",
    ),
    SectorConceptMapping(
        concept="ProfitLoss",
        sector_key="net_income",
        industry_codes=_CODES,
        general_equivalent=CK.NET_INCOME,
        mapping_note="タクソノミ上は一般事業会社と共通の concept（INS サフィックスなし）。",
    ),
)

# --- BS: 資産 (共通) ---

_BS_ASSET_COMMON: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="CashAndDepositsAssetsINS",
        sector_key="cash_and_deposits_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="SecuritiesAssetsINS",
        sector_key="securities_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="LoansReceivablesAssetsINS",
        sector_key="loans_receivables_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="MoneyHeldInTrustAssetsINS",
        sector_key="money_held_in_trust_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CallLoansAssetsINS",
        sector_key="call_loans_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherAssetsAssetsINS",
        sector_key="other_assets_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="AllowanceForDoubtfulAccountsAssetsINS",
        sector_key="allowance_doubtful_accounts_ins",
        industry_codes=_CODES,
    ),
)

# --- BS: 資産 (in1 生命保険固有) ---

_BS_ASSET_IN1: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="PolicyLoansAssetsINS",
        sector_key="policy_loans_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="AgencyAccountsReceivableAssetsINS",
        sector_key="agency_accounts_receivable_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="ReinsuranceAccountsReceivableAssetsINS",
        sector_key="reinsurance_receivable_ins",
        industry_codes=frozenset({"in1"}),
    ),
)

# --- BS: 負債 (共通) ---

_BS_LIABILITY_COMMON: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="ReserveForInsurancePolicyLiabilitiesLiabilitiesINS",
        sector_key="policy_reserve_total_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OutstandingClaimsLiabilitiesINS",
        sector_key="outstanding_claims_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="ReserveForPriceFluctuationLiabilitiesINS",
        sector_key="reserve_price_fluctuation_ins",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OtherLiabilitiesLiabilitiesINS",
        sector_key="other_liabilities_ins",
        industry_codes=_CODES,
    ),
)

# --- BS: 負債 (in1 生命保険固有) ---

_BS_LIABILITY_IN1: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="PolicyReserveLiabilitiesINS",
        sector_key="policy_reserve_ins",
        industry_codes=frozenset({"in1"}),
    ),
    SectorConceptMapping(
        concept="ReserveForDividendsToPolicyholdersLiabilitiesINS",
        sector_key="reserve_dividends_policyholders_ins",
        industry_codes=frozenset({"in1"}),
    ),
)

# --- BS: 負債 (in2 損害保険固有) ---

_BS_LIABILITY_IN2: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="PolicyReserveAndOtherLiabilitiesINS",
        sector_key="policy_reserve_and_other_ins",
        industry_codes=frozenset({"in2"}),
    ),
)

# ---------------------------------------------------------------------------
# レジストリ構築
# ---------------------------------------------------------------------------

_ALL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    *_PL_REVENUE_COMMON,
    *_PL_REVENUE_IN1,
    *_PL_REVENUE_IN2,
    *_PL_EXPENSE_COMMON,
    *_PL_EXPENSE_IN1,
    *_PL_EXPENSE_IN2,
    *_PL_PROFIT_COMMON,
    *_BS_ASSET_COMMON,
    *_BS_ASSET_IN1,
    *_BS_LIABILITY_COMMON,
    *_BS_LIABILITY_IN1,
    *_BS_LIABILITY_IN2,
)

registry = SectorRegistry(profile=_PROFILE, mappings=_ALL_MAPPINGS)
"""保険業の SectorRegistry インスタンス。"""

# INS サフィックス検証（保険業固有科目の大多数が INS を含むことを確認）
# 利益行（OrdinaryIncome, ProfitLoss 等）はタクソノミ上 INS サフィックスを持たない
_ins_count = sum(1 for _m in registry.all_mappings() if "INS" in _m.concept)
if _ins_count < len(registry) // 2:
    raise ValueError(
        f"INS サフィックスを含む concept が過半数未満: "
        f"{_ins_count}/{len(registry)}"
    )
del _ins_count

# 保険業固有の concept（一般事業会社と共通でないもの）
_INSURANCE_SPECIFIC_CONCEPTS: tuple[SectorConceptMapping, ...] = tuple(
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
# 保険業固有 API
# ---------------------------------------------------------------------------


def insurance_specific_concepts() -> tuple[SectorConceptMapping, ...]:
    """保険業固有の概念（一般事業会社に対応がないもの）を返す。

    ``general_equivalent`` が None のマッピングのみを返す。
    定義順（PL → BS → CF）を維持。

    Returns:
        保険業固有の SectorConceptMapping のタプル。
    """
    return _INSURANCE_SPECIFIC_CONCEPTS


def is_insurance_industry(industry_code: str) -> bool:
    """業種コードが保険業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        保険業であれば True。
    """
    return industry_code in INSURANCE_INDUSTRY_CODES


def insurance_to_general_map() -> dict[str, str]:
    """保険業 sector_key → 一般事業会社 canonical_key のマッピング辞書を返す。

    ``general_equivalent`` が設定されているマッピングのみを含む。

    Returns:
        ``{insurance_sector_key: general_canonical_key}`` の辞書。
    """
    return registry.to_general_map()


def get_profile() -> SectorProfile:
    """保険業のプロファイルを取得する。

    Returns:
        SectorProfile インスタンス。
    """
    return registry.get_profile()

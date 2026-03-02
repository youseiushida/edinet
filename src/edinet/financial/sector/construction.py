"""建設業（cns）の業種固有 sector_key マッピング。

建設業は PL が完成工事・不動産事業・開発事業・兼業事業の 4 区分に分かれ、
それぞれ売上高・売上原価・売上総利益の 3 段階を持つ。BS も未成工事支出金や
工事未払金などの固有科目がある。

対象業種コード: ``cns``（建設業）。

典型的な使用例::

    from edinet.financial.sector.construction import registry, lookup, sector_key

    # 建設業固有の concept → 正規化キー
    m = lookup("NetSalesOfCompletedConstructionContractsCNS")
    assert m is not None
    assert m.sector_key == "completed_construction_revenue_cns"

    # 一般事業会社との対応関係
    assert m.general_equivalent == "revenue"

    # 逆引き: 一般事業会社の "revenue" → 建設業の概念（完成工事高）
    rev = registry.from_general_key("revenue")
    assert rev[0].concept == "NetSalesOfCompletedConstructionContractsCNS"
"""

from __future__ import annotations

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "CONSTRUCTION_INDUSTRY_CODES",
    "all_mappings",
    "all_sector_keys",
    "from_general_key",
    "get_profile",
    "is_construction_industry",
    "lookup",
    "registry",
    "reverse_lookup",
    "sector_key",
    "to_general_key",
]

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

CONSTRUCTION_INDUSTRY_CODES: frozenset[str] = frozenset({"cns"})
"""建設業の業種コード集合。"""

_CODES = CONSTRUCTION_INDUSTRY_CODES

# ---------------------------------------------------------------------------
# プロファイル
# ---------------------------------------------------------------------------

_PROFILE = SectorProfile(
    sector_id="construction",
    display_name_ja="建設業",
    display_name_en="Construction",
    industry_codes=_CODES,
    concept_suffix="CNS",
    pl_structure_note="完成工事・不動産事業・開発事業・兼業事業の4区分構造。"
    "それぞれ売上高・売上原価・売上総利益の3段階を持つ。",
)

# ---------------------------------------------------------------------------
# PL マッピング（12 概念: 4事業区分 × 3段階）
# ---------------------------------------------------------------------------

_PL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    # --- 完成工事（主たる事業） ---
    SectorConceptMapping(
        concept="NetSalesOfCompletedConstructionContractsCNS",
        sector_key="completed_construction_revenue_cns",
        industry_codes=_CODES,
        general_equivalent=CK.REVENUE,
    ),
    SectorConceptMapping(
        concept="CostOfSalesOfCompletedConstructionContractsCNS",
        sector_key="completed_construction_cost_cns",
        industry_codes=_CODES,
        general_equivalent=CK.COST_OF_SALES,
    ),
    SectorConceptMapping(
        concept="GrossProfitOnCompletedConstructionContractsCNS",
        sector_key="completed_construction_gross_profit_cns",
        industry_codes=_CODES,
        general_equivalent=CK.GROSS_PROFIT,
    ),
    # --- 不動産事業 ---
    SectorConceptMapping(
        concept="NetSalesOfRealEstateBusinessAndOtherCNS",
        sector_key="real_estate_revenue_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CostOfSalesOnRealEstateBusinessAndOtherCNS",
        sector_key="real_estate_cost_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="GrossProfitOnRealEstateBusinessAndOtherCNS",
        sector_key="real_estate_gross_profit_cns",
        industry_codes=_CODES,
    ),
    # --- 開発事業 ---
    SectorConceptMapping(
        concept="NetSalesOfDevelopmentBusinessAndOtherCNS",
        sector_key="development_revenue_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CostOfSalesOnDevelopmentBusinessAndOtherCNS",
        sector_key="development_cost_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="GrossProfitOnDevelopmentBusinessAndOtherCNS",
        sector_key="development_gross_profit_cns",
        industry_codes=_CODES,
    ),
    # --- 兼業事業 ---
    SectorConceptMapping(
        concept="NetSalesOfSideLineBusinessCNS",
        sector_key="sideline_revenue_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CostOfSalesOnSideLineBusinessCNS",
        sector_key="sideline_cost_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="GrossProfitOnSideLineBusinessCNS",
        sector_key="sideline_gross_profit_cns",
        industry_codes=_CODES,
    ),
)

# ---------------------------------------------------------------------------
# BS マッピング（8 概念: 建設業固有の債権債務・仕掛品）
# ---------------------------------------------------------------------------

_BS_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="CostsOnUncompletedConstructionContractsCNS",
        sector_key="uncompleted_construction_costs_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="RawMaterialsAndSuppliesCNS",
        sector_key="raw_materials_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="AccountsReceivableFromCompletedConstructionContractsCNS",
        sector_key="accounts_receivable_construction_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept=(
            "NotesReceivableAccountsReceivable"
            "FromCompletedConstructionContractsCNS"
        ),
        sector_key="notes_accounts_receivable_construction_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CostsOnUncompletedConstructionContractsAndOtherCNS",
        sector_key="uncompleted_construction_costs_other_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="AdvancesReceivedOnUncompletedConstructionContractsCNS",
        sector_key="advances_received_construction_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="AccountsPayableForConstructionContractsCNS",
        sector_key="accounts_payable_construction_cns",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept=(
            "NotesPayableAccountsPayable"
            "ForConstructionContractsAndOtherCNS"
        ),
        sector_key="notes_payable_construction_cns",
        industry_codes=_CODES,
    ),
)

# ---------------------------------------------------------------------------
# レジストリ構築
# ---------------------------------------------------------------------------

_ALL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    *_PL_MAPPINGS,
    *_BS_MAPPINGS,
)

registry = SectorRegistry(profile=_PROFILE, mappings=_ALL_MAPPINGS)
"""建設業の SectorRegistry インスタンス。"""

# ---------------------------------------------------------------------------
# 公開 API（レジストリへのデリゲート）
# ---------------------------------------------------------------------------

lookup = registry.lookup
sector_key = registry.sector_key
reverse_lookup = registry.reverse_lookup
all_mappings = registry.all_mappings
all_sector_keys = registry.all_sector_keys
get_profile = registry.get_profile
to_general_key = registry.to_general_key
from_general_key = registry.from_general_key


def is_construction_industry(industry_code: str) -> bool:
    """業種コードが建設業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        建設業であれば True。
    """
    return industry_code in CONSTRUCTION_INDUSTRY_CODES

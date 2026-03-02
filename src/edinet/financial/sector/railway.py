"""鉄道業（rwy）の業種固有 sector_key マッピング。

鉄道業は PL が運輸業収益の内訳（旅客運輸収入・貨物運輸収入・線路使用料収入等）
を持ち、連結・個別で構造が異なる。RWY サフィックス付き概念をマッピングする。

対象業種コード: ``rwy``（鉄道業）。

典型的な使用例::

    from edinet.financial.sector.railway import registry, lookup, sector_key

    # 鉄道業固有の concept → 正規化キー
    m = lookup("OperatingRevenueRWY")
    assert m is not None
    assert m.sector_key == "operating_revenue_rwy"

    # 一般事業会社との対応関係
    assert m.general_equivalent == "revenue"
"""

from __future__ import annotations

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "RAILWAY_INDUSTRY_CODES",
    "all_mappings",
    "all_sector_keys",
    "from_general_key",
    "get_profile",
    "is_railway_industry",
    "lookup",
    "registry",
    "reverse_lookup",
    "sector_key",
    "to_general_key",
]

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

RAILWAY_INDUSTRY_CODES: frozenset[str] = frozenset({"rwy"})
"""鉄道業の業種コード集合。"""

_CODES = RAILWAY_INDUSTRY_CODES

# ---------------------------------------------------------------------------
# プロファイル
# ---------------------------------------------------------------------------

_PROFILE = SectorProfile(
    sector_id="railway",
    display_name_ja="鉄道業",
    display_name_en="Railway",
    industry_codes=_CODES,
    concept_suffix="RWY",
    pl_structure_note="営業収益の中に鉄道事業営業収益（旅客・貨物・線路使用料等）を"
    "内訳として持つ。連結と個別で構造が異なる。",
)

# ---------------------------------------------------------------------------
# PL マッピング（11 概念）
# ---------------------------------------------------------------------------

_PL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OperatingRevenueRWY",
        sector_key="operating_revenue_rwy",
        industry_codes=_CODES,
        general_equivalent=CK.REVENUE,
    ),
    SectorConceptMapping(
        concept="OperatingRevenueRailwayRWY",
        sector_key="railway_revenue_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="PassengerTransportationORRWY",
        sector_key="passenger_transportation_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="FreightTransportationORRWY",
        sector_key="freight_transportation_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="TrackageRevenueORRWY",
        sector_key="trackage_revenue_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="MiscellaneousIncomeOfTransportationORRWY",
        sector_key="misc_transportation_income_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OperatingExpensesAndCostOfSalesOfTransportationRWY",
        sector_key="transportation_expenses_cost_rwy",
        industry_codes=_CODES,
        general_equivalent=CK.COST_OF_SALES,
    ),
    SectorConceptMapping(
        concept="TransportationExpensesOERWY",
        sector_key="transportation_expenses_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OperatingExpensesRailwayRWY",
        sector_key="railway_expenses_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OperatingExpensesRWY",
        sector_key="operating_expenses_rwy",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="OperatingIncomeRailwayRWY",
        sector_key="railway_operating_income_rwy",
        industry_codes=_CODES,
    ),
)

# ---------------------------------------------------------------------------
# レジストリ構築
# ---------------------------------------------------------------------------

_ALL_MAPPINGS: tuple[SectorConceptMapping, ...] = _PL_MAPPINGS

registry = SectorRegistry(profile=_PROFILE, mappings=_ALL_MAPPINGS)
"""鉄道業の SectorRegistry インスタンス。"""

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


def is_railway_industry(industry_code: str) -> bool:
    """業種コードが鉄道業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        鉄道業であれば True。
    """
    return industry_code in RAILWAY_INDUSTRY_CODES

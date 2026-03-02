"""鉄道業（rwy）の業種固有マッピングのテスト。

sector/railway モジュールの全公開 API とデータ整合性を検証する。
"""

from __future__ import annotations

import pytest

from edinet.financial.sector._base import SectorConceptMapping, SectorProfile
from edinet.financial.sector.railway import (
    RAILWAY_INDUSTRY_CODES,
    all_mappings,
    all_sector_keys,
    from_general_key,
    get_profile,
    is_railway_industry,
    lookup,
    registry,
    reverse_lookup,
    sector_key,
    to_general_key,
)

# ===========================================================================
# P0: Core API テスト（T50〜T53）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestRailwayCoreAPI:
    """鉄道業コア API テスト群。"""

    def test_t50_lookup_operating_revenue(self) -> None:
        """lookup() が営業収益のマッピングを返す。"""
        m = lookup("OperatingRevenueRWY")
        assert m is not None
        assert isinstance(m, SectorConceptMapping)
        assert m.sector_key == "operating_revenue_rwy"

    def test_t51_lookup_returns_none_for_unknown(self) -> None:
        """lookup() が未登録 concept で None を返す。"""
        assert lookup("UnknownConceptRWY") is None

    def test_t52_sector_key(self) -> None:
        """sector_key() が正規化キーを返す。"""
        assert sector_key("OperatingRevenueRWY") == "operating_revenue_rwy"
        assert sector_key("Unknown") is None

    def test_t53_reverse_lookup(self) -> None:
        """reverse_lookup() が逆引きできる。"""
        m = reverse_lookup("operating_revenue_rwy")
        assert m is not None
        assert m.concept == "OperatingRevenueRWY"
        assert reverse_lookup("unknown_key") is None

    def test_t53b_roundtrip(self) -> None:
        """lookup → reverse_lookup のラウンドトリップ。"""
        m = lookup("OperatingRevenueRWY")
        assert m is not None
        rev = reverse_lookup(m.sector_key)
        assert rev is m


# ===========================================================================
# P0: マッピング件数・整合性テスト（T54〜T57）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestRailwayMappingIntegrity:
    """鉄道業マッピング整合性テスト群。"""

    def test_t55_all_mappings_count(self) -> None:
        """全マッピングが 11 件。"""
        total = all_mappings()
        assert len(total) == 11
        assert len(all_sector_keys()) == len(total)

    def test_t56_concepts_unique(self) -> None:
        """全 concept がユニーク。"""
        concepts = [m.concept for m in all_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_t57_sector_keys_unique(self) -> None:
        """全 sector_key がユニーク。"""
        keys = [m.sector_key for m in all_mappings()]
        assert len(keys) == len(set(keys))


# ===========================================================================
# P0: general_equivalent テスト（T58〜T59）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestRailwayGeneralEquivalent:
    """鉄道業の general_equivalent テスト群。"""

    def test_t58_operating_revenue_maps_to_revenue(self) -> None:
        """営業収益が一般事業会社の revenue に対応する。"""
        assert to_general_key("OperatingRevenueRWY") == "revenue"

    def test_t58b_transportation_expenses_maps_to_cost(self) -> None:
        """営業費及び運輸営業費が cost_of_sales に対応する。"""
        assert (
            to_general_key(
                "OperatingExpensesAndCostOfSalesOfTransportationRWY"
            )
            == "cost_of_sales"
        )

    def test_t59_passenger_has_no_general_equivalent(self) -> None:
        """旅客運輸収入は一般事業会社に対応がない。"""
        assert to_general_key("PassengerTransportationORRWY") is None

    def test_t59b_from_general_key_revenue(self) -> None:
        """from_general_key("revenue") が営業収益を返す。"""
        result = from_general_key("revenue")
        assert len(result) == 1
        assert result[0].concept == "OperatingRevenueRWY"

    def test_t59c_from_general_key_cost_of_sales(self) -> None:
        """from_general_key("cost_of_sales") が営業費を返す。"""
        result = from_general_key("cost_of_sales")
        assert len(result) == 1
        assert result[0].concept == (
            "OperatingExpensesAndCostOfSalesOfTransportationRWY"
        )


# ===========================================================================
# P1: プロファイル・業種判定テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestRailwayProfile:
    """鉄道業プロファイルテスト群。"""

    def test_profile(self) -> None:
        """プロファイルが正しい。"""
        profile = get_profile()
        assert isinstance(profile, SectorProfile)
        assert profile.sector_id == "railway"
        assert profile.display_name_ja == "鉄道業"
        assert profile.concept_suffix == "RWY"
        assert profile.industry_codes == frozenset({"rwy"})

    def test_is_railway_industry(self) -> None:
        """rwy で is_railway_industry() が True。"""
        assert is_railway_industry("rwy") is True
        assert is_railway_industry("sec") is False
        assert is_railway_industry("") is False

    def test_industry_codes_constant(self) -> None:
        """RAILWAY_INDUSTRY_CODES 定数が正しい。"""
        assert RAILWAY_INDUSTRY_CODES == frozenset({"rwy"})

    def test_registry_len_and_repr(self) -> None:
        """registry の __len__ と __repr__ が正しい。"""
        assert len(registry) == 11
        assert "railway" in repr(registry)


# ===========================================================================
# P1: 鉄道業 PL 構造テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestRailwayPLStructure:
    """鉄道業 PL の構造テスト。"""

    def test_expense_concepts_exist(self) -> None:
        """費用系 concept が全て存在する。"""
        expense_concepts = [
            "OperatingExpensesAndCostOfSalesOfTransportationRWY",
            "TransportationExpensesOERWY",
            "OperatingExpensesRailwayRWY",
            "OperatingExpensesRWY",
        ]
        for concept_name in expense_concepts:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"

    def test_railway_operating_income(self) -> None:
        """鉄道事業営業利益の sector_key が正しい。"""
        m = lookup("OperatingIncomeRailwayRWY")
        assert m is not None
        assert m.sector_key == "railway_operating_income_rwy"

    @pytest.mark.parametrize(
        "concept",
        [
            "OperatingRevenueRWY",
            "OperatingRevenueRailwayRWY",
            "PassengerTransportationORRWY",
            "FreightTransportationORRWY",
            "TrackageRevenueORRWY",
            "MiscellaneousIncomeOfTransportationORRWY",
            "OperatingExpensesAndCostOfSalesOfTransportationRWY",
            "TransportationExpensesOERWY",
            "OperatingExpensesRailwayRWY",
            "OperatingExpensesRWY",
            "OperatingIncomeRailwayRWY",
        ],
    )
    def test_all_concepts_registered(self, concept: str) -> None:
        """全 concept が lookup 可能。"""
        m = lookup(concept)
        assert m is not None, f"{concept} が登録されていない"
        assert m.concept == concept

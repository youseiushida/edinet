"""建設業（cns）の業種固有マッピングのテスト。

sector/construction モジュールの全公開 API とデータ整合性を検証する。
"""

from __future__ import annotations

import pytest

from edinet.financial.sector._base import SectorConceptMapping, SectorProfile
from edinet.financial.sector.construction import (
    CONSTRUCTION_INDUSTRY_CODES,
    all_mappings,
    all_sector_keys,
    from_general_key,
    get_profile,
    is_construction_industry,
    lookup,
    registry,
    reverse_lookup,
    sector_key,
    to_general_key,
)

# ===========================================================================
# P0: Core API テスト（T30〜T33）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestConstructionCoreAPI:
    """建設業コア API テスト群。"""

    def test_t30_lookup_completed_construction_revenue(self) -> None:
        """lookup() が完成工事高のマッピングを返す。"""
        m = lookup("NetSalesOfCompletedConstructionContractsCNS")
        assert m is not None
        assert isinstance(m, SectorConceptMapping)
        assert m.sector_key == "completed_construction_revenue_cns"

    def test_t31_lookup_returns_none_for_unknown(self) -> None:
        """lookup() が未登録 concept で None を返す。"""
        assert lookup("UnknownConceptCNS") is None

    def test_t32_sector_key(self) -> None:
        """sector_key() が正規化キーを返す。"""
        assert (
            sector_key("NetSalesOfCompletedConstructionContractsCNS")
            == "completed_construction_revenue_cns"
        )
        assert sector_key("Unknown") is None

    def test_t33_reverse_lookup(self) -> None:
        """reverse_lookup() が逆引きできる。"""
        m = reverse_lookup("completed_construction_revenue_cns")
        assert m is not None
        assert m.concept == "NetSalesOfCompletedConstructionContractsCNS"
        assert reverse_lookup("unknown_key") is None


# ===========================================================================
# P0: マッピング件数・整合性テスト（T34〜T39）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestConstructionMappingIntegrity:
    """建設業マッピング整合性テスト群。"""

    def test_t34_from_general_key_revenue_returns_completed_construction(
        self,
    ) -> None:
        """from_general_key("revenue") が完成工事高（最包括概念）を返す。"""
        result = from_general_key("revenue")
        assert len(result) == 1
        assert result[0].concept == (
            "NetSalesOfCompletedConstructionContractsCNS"
        )

    def test_t34b_from_general_key_cost_of_sales(self) -> None:
        """from_general_key("cost_of_sales") が完成工事原価を返す。"""
        result = from_general_key("cost_of_sales")
        assert len(result) == 1
        assert result[0].concept == (
            "CostOfSalesOfCompletedConstructionContractsCNS"
        )

    def test_t34c_from_general_key_gross_profit(self) -> None:
        """from_general_key("gross_profit") が完成工事総利益を返す。"""
        result = from_general_key("gross_profit")
        assert len(result) == 1
        assert result[0].concept == (
            "GrossProfitOnCompletedConstructionContractsCNS"
        )

    def test_t37_all_mappings_count(self) -> None:
        """全マッピングが 20 件。"""
        total = all_mappings()
        assert len(total) == 20
        assert len(all_sector_keys()) == len(total)

    def test_t38_concepts_unique(self) -> None:
        """全 concept がユニーク。"""
        concepts = [m.concept for m in all_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_t39_sector_keys_unique(self) -> None:
        """全 sector_key がユニーク。"""
        keys = [m.sector_key for m in all_mappings()]
        assert len(keys) == len(set(keys))


# ===========================================================================
# P0: general_equivalent テスト（T40〜T41）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestConstructionGeneralEquivalent:
    """建設業の general_equivalent テスト群。"""

    def test_t40_completed_construction_maps_to_revenue(self) -> None:
        """完成工事高が一般事業会社の revenue に対応する。"""
        assert (
            to_general_key("NetSalesOfCompletedConstructionContractsCNS")
            == "revenue"
        )

    def test_t40b_completed_cost_maps_to_cost_of_sales(self) -> None:
        """完成工事原価が一般事業会社の cost_of_sales に対応する。"""
        assert (
            to_general_key("CostOfSalesOfCompletedConstructionContractsCNS")
            == "cost_of_sales"
        )

    def test_t41_real_estate_has_no_general_equivalent(self) -> None:
        """不動産事業売上高は一般事業会社に対応がない。"""
        assert (
            to_general_key("NetSalesOfRealEstateBusinessAndOtherCNS") is None
        )

    def test_t41b_sideline_has_no_general_equivalent(self) -> None:
        """兼業事業売上高は一般事業会社に対応がない。"""
        assert to_general_key("NetSalesOfSideLineBusinessCNS") is None


# ===========================================================================
# P1: プロファイル・業種判定テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestConstructionProfile:
    """建設業プロファイルテスト群。"""

    def test_profile(self) -> None:
        """プロファイルが正しい。"""
        profile = get_profile()
        assert isinstance(profile, SectorProfile)
        assert profile.sector_id == "construction"
        assert profile.display_name_ja == "建設業"
        assert profile.concept_suffix == "CNS"
        assert profile.industry_codes == frozenset({"cns"})

    def test_is_construction_industry(self) -> None:
        """cns で is_construction_industry() が True。"""
        assert is_construction_industry("cns") is True
        assert is_construction_industry("sec") is False
        assert is_construction_industry("") is False

    def test_industry_codes_constant(self) -> None:
        """CONSTRUCTION_INDUSTRY_CODES 定数が正しい。"""
        assert CONSTRUCTION_INDUSTRY_CODES == frozenset({"cns"})

    def test_registry_len_and_repr(self) -> None:
        """registry の __len__ と __repr__ が正しい。"""
        assert len(registry) == 20
        assert "construction" in repr(registry)


# ===========================================================================
# P1: 4 事業区分構造テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestConstructionBusinessSegments:
    """建設業の 4 事業区分構造テスト。"""

    def test_four_segments_revenue_concepts(self) -> None:
        """4 事業区分の売上高 concept が全て存在する。"""
        revenue_concepts = [
            "NetSalesOfCompletedConstructionContractsCNS",
            "NetSalesOfRealEstateBusinessAndOtherCNS",
            "NetSalesOfDevelopmentBusinessAndOtherCNS",
            "NetSalesOfSideLineBusinessCNS",
        ]
        for concept_name in revenue_concepts:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"

    def test_four_segments_cost_concepts(self) -> None:
        """4 事業区分の売上原価 concept が全て存在する。"""
        cost_concepts = [
            "CostOfSalesOfCompletedConstructionContractsCNS",
            "CostOfSalesOnRealEstateBusinessAndOtherCNS",
            "CostOfSalesOnDevelopmentBusinessAndOtherCNS",
            "CostOfSalesOnSideLineBusinessCNS",
        ]
        for concept_name in cost_concepts:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"

    def test_four_segments_gross_profit_concepts(self) -> None:
        """4 事業区分の総利益 concept が全て存在する。"""
        gp_concepts = [
            "GrossProfitOnCompletedConstructionContractsCNS",
            "GrossProfitOnRealEstateBusinessAndOtherCNS",
            "GrossProfitOnDevelopmentBusinessAndOtherCNS",
            "GrossProfitOnSideLineBusinessCNS",
        ]
        for concept_name in gp_concepts:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"


# ===========================================================================
# P1: BS 科目テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestConstructionBSConcepts:
    """建設業 BS 科目テスト。"""

    @pytest.mark.parametrize(
        "concept",
        [
            "CostsOnUncompletedConstructionContractsCNS",
            "RawMaterialsAndSuppliesCNS",
            "AccountsReceivableFromCompletedConstructionContractsCNS",
            (
                "NotesReceivableAccountsReceivable"
                "FromCompletedConstructionContractsCNS"
            ),
            "CostsOnUncompletedConstructionContractsAndOtherCNS",
            "AdvancesReceivedOnUncompletedConstructionContractsCNS",
            "AccountsPayableForConstructionContractsCNS",
            (
                "NotesPayableAccountsPayable"
                "ForConstructionContractsAndOtherCNS"
            ),
        ],
    )
    def test_bs_concepts_registered(self, concept: str) -> None:
        """全 BS concept が lookup 可能。"""
        m = lookup(concept)
        assert m is not None, f"{concept} が登録されていない"

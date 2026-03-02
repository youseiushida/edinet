"""証券業（sec）の業種固有マッピングのテスト。

sector/securities モジュールの全公開 API とデータ整合性を検証する。
"""

from __future__ import annotations

import pytest

from edinet.financial.sector._base import SectorConceptMapping, SectorProfile
from edinet.financial.sector.securities import (
    SECURITIES_INDUSTRY_CODES,
    all_mappings,
    all_sector_keys,
    from_general_key,
    get_profile,
    is_securities_industry,
    lookup,
    registry,
    reverse_lookup,
    sector_key,
    to_general_key,
)

# ===========================================================================
# P0: Core API テスト（T5〜T12）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSecuritiesCoreAPI:
    """証券業コア API テスト群。"""

    def test_t5_lookup_operating_revenue(self) -> None:
        """lookup() が営業収益のマッピングを返す。"""
        m = lookup("OperatingRevenueSEC")
        assert m is not None
        assert isinstance(m, SectorConceptMapping)
        assert m.sector_key == "operating_revenue_sec"

    def test_t6_lookup_returns_none_for_unknown(self) -> None:
        """lookup() が未登録 concept で None を返す。"""
        assert lookup("UnknownConceptSEC") is None

    def test_t7_sector_key(self) -> None:
        """sector_key() が正規化キーを返す。"""
        assert sector_key("OperatingRevenueSEC") == "operating_revenue_sec"
        assert sector_key("Unknown") is None

    def test_t8_reverse_lookup(self) -> None:
        """reverse_lookup() が逆引きできる。"""
        m = reverse_lookup("operating_revenue_sec")
        assert m is not None
        assert m.concept == "OperatingRevenueSEC"
        assert reverse_lookup("unknown_key") is None

    def test_t9_roundtrip(self) -> None:
        """lookup → reverse_lookup のラウンドトリップ。"""
        m = lookup("OperatingRevenueSEC")
        assert m is not None
        rev = reverse_lookup(m.sector_key)
        assert rev is m

    def test_t12_all_mappings_count(self) -> None:
        """全マッピングが 13 件。"""
        total = all_mappings()
        assert len(total) == 13
        assert len(all_sector_keys()) == len(total)


# ===========================================================================
# P0: マッピング整合性テスト（T13〜T18）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSecuritiesMappingIntegrity:
    """証券業マッピング整合性テスト群。"""

    def test_t13_concepts_unique(self) -> None:
        """全 concept がユニーク。"""
        concepts = [m.concept for m in all_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_t14_sector_keys_unique(self) -> None:
        """全 sector_key がユニーク。"""
        keys = [m.sector_key for m in all_mappings()]
        assert len(keys) == len(set(keys))


# ===========================================================================
# P0: general_equivalent テスト（T19〜T22）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSecuritiesGeneralEquivalent:
    """証券業の general_equivalent テスト群。"""

    def test_t19_operating_revenue_maps_to_revenue(self) -> None:
        """営業収益が一般事業会社の revenue に対応する。"""
        assert to_general_key("OperatingRevenueSEC") == "revenue"

    def test_t20_net_operating_revenue_maps_to_gross_profit(self) -> None:
        """純営業収益が一般事業会社の gross_profit に対応する。"""
        assert to_general_key("NetOperatingRevenueSEC") == "gross_profit"

    def test_t21_commission_has_no_general_equivalent(self) -> None:
        """受入手数料は一般事業会社に対応がない。"""
        assert to_general_key("CommissionReceivedORSEC") is None

    def test_t22_from_general_key_revenue(self) -> None:
        """from_general_key("revenue") が営業収益を返す。"""
        result = from_general_key("revenue")
        assert len(result) == 1
        assert result[0].concept == "OperatingRevenueSEC"

    def test_t22b_from_general_key_gross_profit(self) -> None:
        """from_general_key("gross_profit") が純営業収益を返す。"""
        result = from_general_key("gross_profit")
        assert len(result) == 1
        assert result[0].concept == "NetOperatingRevenueSEC"

    def test_t22c_sga_maps_to_general(self) -> None:
        """販売費及び一般管理費が sga_expenses に対応する。"""
        assert (
            to_general_key("SellingGeneralAndAdministrativeExpenses")
            == "sga_expenses"
        )

    def test_t22d_operating_profit_maps_to_general(self) -> None:
        """営業利益が operating_income に対応する。"""
        assert to_general_key("OperatingIncome") == "operating_income"


# ===========================================================================
# P1: プロファイル・業種判定テスト（T23〜T25）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSecuritiesProfile:
    """証券業プロファイルテスト群。"""

    def test_t23_profile(self) -> None:
        """プロファイルが正しい。"""
        profile = get_profile()
        assert isinstance(profile, SectorProfile)
        assert profile.sector_id == "securities"
        assert profile.display_name_ja == "証券業"
        assert profile.concept_suffix == "SEC"
        assert profile.industry_codes == frozenset({"sec"})

    def test_t24_is_securities_industry(self) -> None:
        """sec で is_securities_industry() が True。"""
        assert is_securities_industry("sec") is True
        assert is_securities_industry("bk1") is False
        assert is_securities_industry("") is False

    def test_t24b_industry_codes_constant(self) -> None:
        """SECURITIES_INDUSTRY_CODES 定数が正しい。"""
        assert SECURITIES_INDUSTRY_CODES == frozenset({"sec"})

    def test_t25b_registry_len_and_repr(self) -> None:
        """registry の __len__ と __repr__ が正しい。"""
        assert len(registry) == 13
        assert "securities" in repr(registry)


# ===========================================================================
# P1: 個別 concept 存在テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSecuritiesConceptExistence:
    """全登録 concept の存在確認テスト。"""

    @pytest.mark.parametrize(
        "concept",
        [
            "OperatingRevenueSEC",
            "CommissionReceivedORSEC",
            "NetTradingIncomeORSEC",
            "FinancialRevenueORSEC",
            "FinancialExpensesSEC",
            "NetOperatingRevenueSEC",
            "SellingGeneralAndAdministrativeExpenses",
            "OperatingIncome",
            "TradingProductsCASEC",
            "TradingProductsCLSEC",
            "MarginTransactionAssetsCASEC",
            "MarginTransactionLiabilitiesCLSEC",
            "CashSegregatedAsDepositsCASEC",
        ],
    )
    def test_all_concepts_registered(self, concept: str) -> None:
        """全 concept が lookup 可能。"""
        m = lookup(concept)
        assert m is not None, f"{concept} が登録されていない"
        assert m.concept == concept

"""銀行業（bk1/bk2）の業種固有マッピングのテスト。

sector/banking モジュールの全公開 API と内部データ整合性を検証する。
"""

from __future__ import annotations

import pytest

from edinet.financial.sector._base import SectorConceptMapping, SectorProfile
from edinet.financial.sector.banking import (
    BANKING_INDUSTRY_CODES,
    BankingConceptMapping,
    all_mappings,
    all_sector_keys,
    banking_specific_concepts,
    banking_to_general_map,
    general_equivalent,
    get_profile,
    is_banking_concept,
    is_banking_industry,
    lookup,
    reverse_lookup,
    sector_key,
)

# ===========================================================================
# P0: Core API テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP0CoreAPI:
    """P0 コア API テスト群（T1-T12）。"""

    # --- T1-T4: lookup / sector_key ---

    def test_t01_lookup_returns_mapping(self) -> None:
        """lookup() が銀行業固有 concept で SectorConceptMapping を返す。"""
        result = lookup("OrdinaryIncomeBNK")
        assert result is not None
        assert isinstance(result, SectorConceptMapping)
        # 後方互換エイリアスも動作する
        assert isinstance(result, BankingConceptMapping)
        assert result.sector_key == "ordinary_revenue_bnk"

    def test_t02_lookup_returns_none_for_unknown(self) -> None:
        """lookup() が未登録 concept で None を返す。"""
        assert lookup("UnknownConcept") is None

    def test_t03_sector_key_returns_key(self) -> None:
        """sector_key() が正規化キーを返す。"""
        assert sector_key("OrdinaryIncomeBNK") == "ordinary_revenue_bnk"

    def test_t04_sector_key_returns_none_for_unknown(self) -> None:
        """sector_key() が未登録 concept で None を返す。"""
        assert sector_key("FooBar") is None

    # --- T5-T7: reverse_lookup ---

    def test_t05_reverse_lookup_returns_mapping(self) -> None:
        """reverse_lookup() が正規化キーから BankingConceptMapping を返す。"""
        result = reverse_lookup("ordinary_revenue_bnk")
        assert result is not None
        assert result.concept == "OrdinaryIncomeBNK"

    def test_t06_reverse_lookup_returns_none_for_unknown(self) -> None:
        """reverse_lookup() が未登録キーで None を返す。"""
        assert reverse_lookup("nonexistent_key") is None

    def test_t07_lookup_and_reverse_roundtrip(self) -> None:
        """lookup → reverse_lookup のラウンドトリップが一致する。"""
        m = lookup("OrdinaryIncomeBNK")
        assert m is not None
        rev = reverse_lookup(m.sector_key)
        assert rev is m

    # --- T11-T12: all_mappings / all_sector_keys ---

    def test_t11_all_mappings_count(self) -> None:
        """全マッピングが 45 件。"""
        assert len(all_mappings()) == 45

    def test_t12_all_sector_keys_count(self) -> None:
        """全 sector_key 数がマッピング数と一致（ユニーク）。"""
        keys = all_sector_keys()
        assert len(keys) == len(all_mappings())


# ===========================================================================
# P0: マッピング整合性テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP0MappingIntegrity:
    """P0 マッピング整合性テスト群（T13-T14）。"""

    def test_t13_concepts_unique(self) -> None:
        """全 concept がユニーク。"""
        concepts = [m.concept for m in all_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_t14_sector_keys_unique(self) -> None:
        """全 sector_key がユニーク。"""
        keys = [m.sector_key for m in all_mappings()]
        assert len(keys) == len(set(keys))


# ===========================================================================
# P0: 共通科目一致テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP0CommonConceptMatch:
    """P0 共通科目テスト群（T21-T25）。

    銀行業と一般事業会社で共通の科目について、
    sector_key が jgaap.py と完全一致することを検証する。
    テスト時のみ jgaap をインポートする。
    """

    def test_t21_net_income_sector_key_matches_jgaap(self) -> None:
        """ProfitLoss の sector_key が jgaap.py と一致する。"""
        from edinet.financial.standards.jgaap import (
            canonical_key as jgaap_canonical_key,
        )

        banking_key = sector_key("ProfitLoss")
        jgaap_key = jgaap_canonical_key("ProfitLoss")
        assert banking_key == jgaap_key == "net_income"

    def test_t22_total_assets_sector_key_matches_jgaap(self) -> None:
        """Assets の sector_key が jgaap.py と一致する。"""
        from edinet.financial.standards.jgaap import (
            canonical_key as jgaap_canonical_key,
        )

        banking_key = sector_key("Assets")
        jgaap_key = jgaap_canonical_key("Assets")
        assert banking_key == jgaap_key == "total_assets"

    def test_t23_operating_cf_sector_key_matches_jgaap(self) -> None:
        """NetCashProvidedByUsedInOperatingActivities の sector_key が一致する。"""
        from edinet.financial.standards.jgaap import (
            canonical_key as jgaap_canonical_key,
        )

        banking_key = sector_key("NetCashProvidedByUsedInOperatingActivities")
        jgaap_key = jgaap_canonical_key(
            "NetCashProvidedByUsedInOperatingActivities"
        )
        assert banking_key == jgaap_key == "operating_cf"

    def test_t24_ordinary_income_sector_key_matches_jgaap(self) -> None:
        """OrdinaryIncome の sector_key が jgaap.py と一致する。"""
        from edinet.financial.standards.jgaap import (
            canonical_key as jgaap_canonical_key,
        )

        banking_key = sector_key("OrdinaryIncome")
        jgaap_key = jgaap_canonical_key("OrdinaryIncome")
        assert banking_key == jgaap_key == "ordinary_income"

    def test_t25_all_common_concepts_match_jgaap(self) -> None:
        """general_equivalent を持つ全共通科目の sector_key が jgaap と一致する。"""
        from edinet.financial.standards.jgaap import (
            canonical_key as jgaap_canonical_key,
        )

        common_mappings = [m for m in all_mappings() if m.general_equivalent is not None]
        assert len(common_mappings) > 0, "共通科目が1件もない"

        for m in common_mappings:
            jgaap_key = jgaap_canonical_key(m.concept)
            if jgaap_key is not None:
                # jgaap にも同一 concept が存在する場合、sector_key が一致
                assert m.sector_key == jgaap_key, (
                    f"{m.concept}: banking={m.sector_key}, jgaap={jgaap_key}"
                )


# ===========================================================================
# P1: プロファイルテスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1Profile:
    """P1 プロファイルテスト群（T26-T29）。"""

    def test_t26_profile(self) -> None:
        """銀行業プロファイルが正しい。"""
        profile = get_profile()
        assert isinstance(profile, SectorProfile)
        assert profile.sector_id == "banking"
        assert profile.display_name_ja == "銀行・信託業"
        assert profile.has_consolidated_template is True
        assert profile.cf_method == "both"
        assert profile.industry_codes == frozenset({"bk1", "bk2"})

    def test_t27_profile_unified(self) -> None:
        """bk1/bk2 共通の統合プロファイル。"""
        profile = get_profile()
        assert profile.sector_id == "banking"
        assert profile.has_consolidated_template is True
        assert "bk1" in profile.industry_codes
        assert "bk2" in profile.industry_codes

    def test_t28_profile_via_registry(self) -> None:
        """registry.get_profile() と一致する。"""
        from edinet.financial.sector.banking import registry
        assert get_profile() is registry.get_profile()

    def test_t29_profile_is_frozen(self) -> None:
        """SectorProfile が frozen dataclass。"""
        profile = get_profile()
        with pytest.raises(AttributeError):
            profile.sector_id = "changed"  # type: ignore[misc]


# ===========================================================================
# P1: エッジケーステスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1EdgeCases:
    """P1 エッジケーステスト群（T30-T34）。"""

    def test_t30_lookup_empty_string(self) -> None:
        """空文字列で lookup() が None を返す。"""
        assert lookup("") is None

    def test_t31_sector_key_empty_string(self) -> None:
        """空文字列で sector_key() が None を返す。"""
        assert sector_key("") is None

    def test_t32_reverse_lookup_empty_string(self) -> None:
        """空文字列で reverse_lookup() が None を返す。"""
        assert reverse_lookup("") is None

    def test_t33_frozen_dataclass_immutable(self) -> None:
        """BankingConceptMapping が frozen dataclass で変更不可。"""
        m = lookup("OrdinaryIncomeBNK")
        assert m is not None
        with pytest.raises(AttributeError):
            m.sector_key = "changed"  # type: ignore[misc]

    def test_t34_industry_codes_is_frozenset(self) -> None:
        """industry_codes が frozenset。"""
        m = lookup("OrdinaryIncomeBNK")
        assert m is not None
        assert isinstance(m.industry_codes, frozenset)
        assert m.industry_codes == frozenset({"bk1", "bk2"})


# ===========================================================================
# P1: CF メソッドテスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1CFMethods:
    """P1 CF メソッド分離テスト群（T35-T37）。"""

    def test_t35_direct_method_concepts_exist(self) -> None:
        """直接法 CF 固有科目が存在する。"""
        direct_concepts = [
            "CollectionOfLoansReceivableOpeCFBNK",
            "PaymentsForWithdrawalOfDepositsOpeCFBNK",
            "ProceedsFromInterestOnLoansOpeCFBNK",
            "PaymentsForInterestExpensesForDepositOpeCFBNK",
        ]
        for concept_name in direct_concepts:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"
            assert "直接法" in m.mapping_note

    def test_t36_indirect_method_concepts_exist(self) -> None:
        """間接法 CF 固有科目が存在する。"""
        indirect_concepts = [
            "DepreciationAndAmortizationOpeCF",
            "NetDecreaseIncreaseInLoansAndBillsDiscountedOpeCFBNK",
            "NetIncreaseDecreaseInDepositOpeCFBNK",
        ]
        for concept_name in indirect_concepts:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"
            assert "間接法" in m.mapping_note

    def test_t37_common_cf_has_general_equivalent(self) -> None:
        """共通 CF 科目が general_equivalent を持つ。"""
        common_cf = [
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInInvestmentActivities",
            "NetCashProvidedByUsedInFinancingActivities",
        ]
        for concept_name in common_cf:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"
            assert m.general_equivalent is not None, (
                f"{concept_name} の general_equivalent が None"
            )


# ===========================================================================
# P1: 銀行業固有 API テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1BankingSpecificAPI:
    """P1 銀行業固有 API テスト群（T38-T43）。"""

    def test_t38_is_banking_concept_true(self) -> None:
        """銀行業固有 concept で is_banking_concept() が True。"""
        assert is_banking_concept("InterestIncomeOIBNK") is True

    def test_t38b_is_banking_concept_false_with_general_equivalent(self) -> None:
        """general_equivalent を持つ concept は銀行業固有ではない。"""
        # OrdinaryIncomeBNK は general_equivalent="revenue" → 一般事業対応あり
        assert is_banking_concept("OrdinaryIncomeBNK") is False

    def test_t39_is_banking_concept_false_for_common(self) -> None:
        """一般事業会社と共通の concept で is_banking_concept() が False。"""
        assert is_banking_concept("ProfitLoss") is False

    def test_t40_is_banking_concept_false_for_unknown(self) -> None:
        """未登録 concept で is_banking_concept() が False。"""
        assert is_banking_concept("UnknownConcept") is False

    def test_t41_general_equivalent_returns_key(self) -> None:
        """general_equivalent() が一般事業会社の canonical_key を返す。"""
        assert general_equivalent("OrdinaryIncomeBNK") == "revenue"

    def test_t42_general_equivalent_returns_none_for_banking_only(self) -> None:
        """銀行業固有科目で general_equivalent() が None を返す。"""
        assert general_equivalent("InterestIncomeOIBNK") is None

    def test_t43_banking_to_general_map_nonempty(self) -> None:
        """banking_to_general_map() が空でない辞書を返す。"""
        mapping = banking_to_general_map()
        assert len(mapping) > 0
        # ordinary_revenue_bnk → revenue が含まれる
        assert mapping["ordinary_revenue_bnk"] == "revenue"

    def test_t44_is_banking_industry_true(self) -> None:
        """bk1/bk2 で is_banking_industry() が True。"""
        assert is_banking_industry("bk1") is True
        assert is_banking_industry("bk2") is True

    def test_t45_is_banking_industry_false(self) -> None:
        """非銀行業コードで is_banking_industry() が False。"""
        assert is_banking_industry("general") is False
        assert is_banking_industry("") is False

    def test_t46_banking_industry_codes_constant(self) -> None:
        """BANKING_INDUSTRY_CODES 定数が正しい。"""
        assert BANKING_INDUSTRY_CODES == frozenset({"bk1", "bk2"})

    def test_t47_banking_specific_concepts_self_consistent(self) -> None:
        """銀行業固有科目が自己整合的である。"""
        specifics = banking_specific_concepts()
        all_total = all_mappings()
        # 全マッピングの部分集合
        specific_concepts = {m.concept for m in specifics}
        all_concepts = {m.concept for m in all_total}
        assert specific_concepts.issubset(all_concepts)
        # 固有科目は全て general_equivalent=None
        assert all(m.general_equivalent is None for m in specifics)
        # 全て is_banking_concept() == True
        assert all(is_banking_concept(m.concept) for m in specifics)
        # 非固有科目は general_equivalent が設定されている
        non_specific = [m for m in all_total if m.concept not in specific_concepts]
        assert all(m.general_equivalent is not None for m in non_specific)

    def test_t48_general_equivalent_exists_in_jgaap(self) -> None:
        """general_equivalent が設定されている場合、jgaap に存在する。"""
        from edinet.financial.standards.jgaap import (
            all_canonical_keys as jgaap_keys,
        )

        jgaap = jgaap_keys()
        for m in all_mappings():
            if m.general_equivalent is not None:
                assert m.general_equivalent in jgaap, (
                    f"{m.concept} の general_equivalent="
                    f"{m.general_equivalent!r} が jgaap に存在しない"
                )

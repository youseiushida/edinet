"""保険業（in1/in2）の業種固有マッピングのテスト。

sector/insurance モジュールの全公開 API と内部データ整合性を検証する。
"""

from __future__ import annotations

import pytest

from edinet.financial.sector._base import SectorConceptMapping, SectorProfile
from edinet.financial.sector.insurance import (
    INSURANCE_INDUSTRY_CODES,
    InsuranceConceptMapping,
    all_mappings,
    all_sector_keys,
    get_profile,
    insurance_specific_concepts,
    insurance_to_general_map,
    is_insurance_industry,
    lookup,
    registry,
    reverse_lookup,
    sector_key,
)

# ===========================================================================
# P0: Core API テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP0CoreAPI:
    """P0 コア API テスト群。"""

    # --- lookup / sector_key ---

    def test_t01_lookup_returns_mapping(self) -> None:
        """lookup() が保険業固有 concept で SectorConceptMapping を返す。"""
        result = lookup("OperatingIncomeINS")
        assert result is not None
        assert isinstance(result, SectorConceptMapping)
        # 後方互換エイリアスも動作する
        assert isinstance(result, InsuranceConceptMapping)
        assert result.sector_key == "ordinary_revenue_ins"

    def test_t02_lookup_returns_none_for_unknown(self) -> None:
        """lookup() が未登録 concept で None を返す。"""
        assert lookup("UnknownConcept") is None

    def test_t03_sector_key_returns_key(self) -> None:
        """sector_key() が正規化キーを返す。"""
        assert sector_key("OperatingIncomeINS") == "ordinary_revenue_ins"

    def test_t04_sector_key_returns_none_for_unknown(self) -> None:
        """sector_key() が未登録 concept で None を返す。"""
        assert sector_key("FooBar") is None

    # --- reverse_lookup ---

    def test_t05_reverse_lookup_returns_mapping(self) -> None:
        """reverse_lookup() が正規化キーから InsuranceConceptMapping を返す。"""
        result = reverse_lookup("ordinary_revenue_ins")
        assert result is not None
        assert result.concept == "OperatingIncomeINS"

    def test_t06_reverse_lookup_returns_none_for_unknown(self) -> None:
        """reverse_lookup() が未登録キーで None を返す。"""
        assert reverse_lookup("nonexistent_key") is None

    def test_t07_lookup_and_reverse_roundtrip(self) -> None:
        """lookup → reverse_lookup のラウンドトリップが一致する。"""
        m = lookup("OperatingIncomeINS")
        assert m is not None
        rev = reverse_lookup(m.sector_key)
        assert rev is m

    # --- all_mappings / all_sector_keys ---

    def test_t11_all_mappings_count(self) -> None:
        """全マッピングが 49 件。"""
        assert len(all_mappings()) == 49

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
    """P0 マッピング整合性テスト群。"""

    def test_t13_concepts_unique(self) -> None:
        """全 concept がユニーク。"""
        concepts = [m.concept for m in all_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_t14_sector_keys_unique(self) -> None:
        """全 sector_key がユニーク。"""
        keys = [m.sector_key for m in all_mappings()]
        assert len(keys) == len(set(keys))


# ===========================================================================
# P0: INS サフィックステスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP0INSSuffix:
    """全 concept が INS サフィックスを含むことを検証する。"""

    def test_t22_majority_concepts_contain_ins(self) -> None:
        """大多数の concept に 'INS' が含まれる。

        利益行（OrdinaryIncome, ProfitLoss 等）はタクソノミ上
        一般事業会社と共通の concept のため INS サフィックスを持たない。
        """
        mappings = all_mappings()
        ins_count = sum(1 for m in mappings if "INS" in m.concept)
        assert ins_count > len(mappings) // 2, (
            f"INS を含む concept が過半数未満: {ins_count}/{len(mappings)}"
        )


# ===========================================================================
# P0: 共通科目一致テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP0CommonConceptMatch:
    """共通科目テスト群。

    保険業と一般事業会社で共通の概念について、
    general_equivalent が jgaap.py の canonical_key と一致することを検証する。
    """

    def test_t23_ordinary_income_matches_jgaap(self) -> None:
        """OrdinaryIncome の general_equivalent が jgaap の canonical_key と一致。"""
        from edinet.financial.standards.jgaap import (
            canonical_key as jgaap_canonical_key,
        )

        m = lookup("OrdinaryIncome")
        assert m is not None
        assert m.general_equivalent == "ordinary_income"
        jgaap_key = jgaap_canonical_key("OrdinaryIncome")
        assert jgaap_key == "ordinary_income"
        assert m.general_equivalent == jgaap_key

    def test_t24_net_income_matches_jgaap(self) -> None:
        """ProfitLoss の sector_key が jgaap の ProfitLoss と同じ。"""
        from edinet.financial.standards.jgaap import (
            canonical_key as jgaap_canonical_key,
        )

        insurance_key = sector_key("ProfitLoss")
        jgaap_key = jgaap_canonical_key("ProfitLoss")
        assert insurance_key == jgaap_key == "net_income"

    def test_t25_all_general_equivalents_exist_in_jgaap(self) -> None:
        """general_equivalent を持つ全マッピングの値が jgaap の canonical_key 集合に存在する。"""
        from edinet.financial.standards.jgaap import (
            all_canonical_keys as jgaap_all_canonical_keys,
        )

        jgaap_keys = jgaap_all_canonical_keys()
        common_mappings = [
            m for m in all_mappings() if m.general_equivalent is not None
        ]
        assert len(common_mappings) > 0, "共通科目が1件もない"

        for m in common_mappings:
            assert m.general_equivalent in jgaap_keys, (
                f"{m.concept} の general_equivalent={m.general_equivalent!r} "
                f"が jgaap に存在しない"
            )

    def test_t26_insurance_specific_keys_not_in_jgaap(self) -> None:
        """``_ins`` サフィックスの sector_key は jgaap に存在しない。"""
        from edinet.financial.standards.jgaap import (
            all_canonical_keys as jgaap_all_canonical_keys,
        )

        jgaap_keys = jgaap_all_canonical_keys()
        ins_keys = [
            m.sector_key
            for m in all_mappings()
            if m.sector_key.endswith("_ins")
        ]
        assert len(ins_keys) > 0, "_ins サフィックスのキーが1件もない"

        for key in ins_keys:
            assert key not in jgaap_keys, (
                f"_ins キー {key!r} が jgaap にも存在する"
            )


# ===========================================================================
# P1: プロファイルテスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1Profile:
    """P1 プロファイルテスト群。"""

    def test_t27_profile_fields(self) -> None:
        """プロファイルの基本フィールドが正しい。"""
        profile = get_profile()
        assert isinstance(profile, SectorProfile)
        assert profile.sector_id == "insurance"
        assert profile.display_name_ja == "保険業"
        assert profile.display_name_en == "Insurance"
        assert profile.industry_codes == frozenset({"in1", "in2"})

    def test_t28_profile_sector_key_count(self) -> None:
        """registry の sector_key_count がマッピング数と一致。"""
        assert registry.sector_key_count == len(all_mappings())
        assert registry.sector_key_count == len(all_sector_keys())

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
    """P1 エッジケーステスト群。"""

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
        """InsuranceConceptMapping が frozen dataclass で変更不可。"""
        m = lookup("OperatingIncomeINS")
        assert m is not None
        with pytest.raises(AttributeError):
            m.sector_key = "changed"  # type: ignore[misc]

    def test_t34_industry_codes_is_frozenset(self) -> None:
        """共通 concept の industry_codes が frozenset({"in1", "in2"})。"""
        m = lookup("OperatingIncomeINS")
        assert m is not None
        assert isinstance(m.industry_codes, frozenset)
        assert m.industry_codes == frozenset({"in1", "in2"})


# ===========================================================================
# P1: 業種コードフィルタリングテスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1IndustryCodeFiltering:
    """in1/in2 固有科目の industry_codes が正しいことを検証する。"""

    def test_t35_in1_only_concepts_exist(self) -> None:
        """in1（生命保険）固有の concept が存在する。"""
        in1_only = [
            m for m in all_mappings()
            if m.industry_codes == frozenset({"in1"})
        ]
        assert len(in1_only) > 0, "in1 固有の concept が 0 件"

    def test_t36_in2_only_concepts_exist(self) -> None:
        """in2（損害保険）固有の concept が存在する。"""
        in2_only = [
            m for m in all_mappings()
            if m.industry_codes == frozenset({"in2"})
        ]
        assert len(in2_only) > 0, "in2 固有の concept が 0 件"

    def test_t37_common_concepts_exist(self) -> None:
        """in1+in2 共通の concept が存在する。"""
        common = [
            m for m in all_mappings()
            if m.industry_codes == frozenset({"in1", "in2"})
        ]
        assert len(common) > 0, "共通 concept が 0 件"

    def test_t38_in1_life_insurance_has_premiums(self) -> None:
        """生命保険固有の「保険料等収入」が in1 限定で登録されている。"""
        m = lookup("InsurancePremiumsAndOtherOIINS")
        assert m is not None
        assert m.industry_codes == frozenset({"in1"})

    def test_t39_in2_nonlife_has_underwriting(self) -> None:
        """損害保険固有の「保険引受収益」が in2 限定で登録されている。"""
        m = lookup("UnderwritingIncomeOIINS")
        assert m is not None
        assert m.industry_codes == frozenset({"in2"})

    def test_t40_industry_codes_subset_of_insurance(self) -> None:
        """全 mapping の industry_codes が INSURANCE_INDUSTRY_CODES のサブセット。"""
        for m in all_mappings():
            assert m.industry_codes <= INSURANCE_INDUSTRY_CODES, (
                f"{m.concept} の industry_codes={m.industry_codes} "
                f"が INSURANCE_INDUSTRY_CODES のサブセットでない"
            )


# ===========================================================================
# P1: 保険業固有 API テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1InsuranceSpecificAPI:
    """P1 保険業固有 API テスト群。"""

    def test_t41_is_insurance_industry_true(self) -> None:
        """in1/in2 で is_insurance_industry() が True。"""
        assert is_insurance_industry("in1") is True
        assert is_insurance_industry("in2") is True

    def test_t42_is_insurance_industry_false(self) -> None:
        """非保険業コードで is_insurance_industry() が False。"""
        assert is_insurance_industry("cai") is False
        assert is_insurance_industry("bk1") is False
        assert is_insurance_industry("") is False

    def test_t43_insurance_industry_codes_constant(self) -> None:
        """INSURANCE_INDUSTRY_CODES 定数が正しい。"""
        assert INSURANCE_INDUSTRY_CODES == frozenset({"in1", "in2"})

    def test_t44_insurance_to_general_map_nonempty(self) -> None:
        """insurance_to_general_map() が空でない辞書を返す。"""
        mapping = insurance_to_general_map()
        assert len(mapping) > 0
        # ordinary_revenue_ins → revenue が含まれる
        assert mapping["ordinary_revenue_ins"] == "revenue"

    def test_t45_insurance_specific_concepts_count(self) -> None:
        """保険業固有科目数が正しい（general_equivalent=None のもの）。"""
        specifics = insurance_specific_concepts()
        expected_specifics = [
            m for m in all_mappings() if m.general_equivalent is None
        ]
        assert len(specifics) == len(expected_specifics)
        assert all(m.general_equivalent is None for m in specifics)

    def test_t47_insurance_to_general_map_values_in_jgaap(self) -> None:
        """insurance_to_general_map() の値が全て jgaap の canonical_key に存在する。"""
        from edinet.financial.standards.jgaap import (
            all_canonical_keys as jgaap_all_canonical_keys,
        )

        jgaap_keys = jgaap_all_canonical_keys()
        for ins_key, gen_key in insurance_to_general_map().items():
            assert gen_key in jgaap_keys, (
                f"insurance_to_general_map()[{ins_key!r}]={gen_key!r} "
                f"が jgaap に存在しない"
            )


# ===========================================================================
# P1: レジストリ整合性テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1RegistryValidation:
    """レジストリが正しく構築されていることを検証する。"""

    def test_t48_module_loads_without_error(self) -> None:
        """モジュールのインポートがエラーなく完了する（_validate_registry 通過）。"""
        # このテストの存在自体が _validate_registry() の通過を証明する
        import edinet.financial.sector.insurance as ins_module

        assert hasattr(ins_module, "lookup")
        assert hasattr(ins_module, "all_mappings")

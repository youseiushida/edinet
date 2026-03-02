"""SectorRegistry バリデーションテスト。

_base.py の SectorConceptMapping / SectorProfile / SectorRegistry の
バリデーションロジックとエッジケースを検証する。
"""

from __future__ import annotations

import pytest

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)


# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------

def _make_profile(sector_id: str = "test") -> SectorProfile:
    """テスト用プロファイルを生成する。"""
    return SectorProfile(
        sector_id=sector_id,
        display_name_ja="テスト業",
        display_name_en="Test Industry",
        industry_codes=frozenset({"tst"}),
        concept_suffix="TST",
    )


def _make_mapping(
    concept: str = "TestConcept",
    sector_key: str = "test_key",
    *,
    general_equivalent: str | None = None,
    industry_codes: frozenset[str] | None = None,
) -> SectorConceptMapping:
    """テスト用マッピングを生成する。"""
    return SectorConceptMapping(
        concept=concept,
        sector_key=sector_key,
        industry_codes=industry_codes if industry_codes is not None else frozenset({"tst"}),
        general_equivalent=general_equivalent,
    )


# ===========================================================================
# T1〜T4: SectorRegistry バリデーション
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSectorRegistryValidation:
    """SectorRegistry のバリデーションテスト群。"""

    def test_t1_valid_registry_creation(self) -> None:
        """正常なマッピングで SectorRegistry が作成できる。"""
        profile = _make_profile()
        mappings = (
            _make_mapping("A", "key_a"),
            _make_mapping("B", "key_b"),
        )
        reg = SectorRegistry(profile=profile, mappings=mappings)
        assert len(reg) == 2

    def test_t2_duplicate_concept_raises_value_error(self) -> None:
        """concept が重複するとバリデーションで ValueError。"""
        profile = _make_profile("dup_test")
        mappings = (
            _make_mapping("SameConcept", "key_a"),
            _make_mapping("SameConcept", "key_b"),
        )
        with pytest.raises(ValueError, match="dup_test.*concept.*重複"):
            SectorRegistry(profile=profile, mappings=mappings)

    def test_t3_duplicate_sector_key_raises_value_error(self) -> None:
        """sector_key が重複するとバリデーションで ValueError。"""
        profile = _make_profile("key_dup")
        mappings = (
            _make_mapping("ConceptA", "same_key"),
            _make_mapping("ConceptB", "same_key"),
        )
        with pytest.raises(ValueError, match="key_dup.*sector_key.*重複"):
            SectorRegistry(profile=profile, mappings=mappings)

    def test_t4_empty_industry_codes_raises_value_error(self) -> None:
        """空の industry_codes でバリデーションエラー。"""
        profile = _make_profile("empty_ic")
        mappings = (
            _make_mapping(
                "EmptyIC", "empty_key",
                industry_codes=frozenset(),
            ),
        )
        with pytest.raises(ValueError, match="empty_ic.*industry_codes.*空"):
            SectorRegistry(profile=profile, mappings=mappings)


@pytest.mark.small
@pytest.mark.unit
class TestSectorRegistryValidationExtended:
    """SectorRegistry バリデーションの追加テスト。"""

    def test_t4c_empty_concept_raises_value_error(self) -> None:
        """空の concept でバリデーションエラー。"""
        profile = _make_profile("empty_c")
        mappings = (_make_mapping("", "some_key"),)
        with pytest.raises(ValueError, match="empty_c.*空の concept"):
            SectorRegistry(profile=profile, mappings=mappings)

    def test_t4d_empty_sector_key_raises_value_error(self) -> None:
        """空の sector_key でバリデーションエラー。"""
        profile = _make_profile("empty_k")
        mappings = (_make_mapping("SomeConcept", ""),)
        with pytest.raises(ValueError, match="empty_k.*sector_key.*空"):
            SectorRegistry(profile=profile, mappings=mappings)

    def test_t4g_error_message_contains_sector_id(self) -> None:
        """バリデーションエラーのメッセージに sector_id が含まれる。"""
        profile = _make_profile("my_sector_123")
        mappings = (
            _make_mapping("A", "key_a"),
            _make_mapping("A", "key_b"),
        )
        with pytest.raises(ValueError, match="my_sector_123"):
            SectorRegistry(profile=profile, mappings=mappings)

    def test_t4h_industry_codes_not_subset_raises_value_error(self) -> None:
        """マッピングの industry_codes がプロファイルに含まれない場合 ValueError。"""
        profile = _make_profile("ic_sub")
        mappings = (
            _make_mapping(
                "X", "key_x",
                industry_codes=frozenset({"tst", "unknown"}),
            ),
        )
        with pytest.raises(ValueError, match="ic_sub.*industry_codes.*プロファイル"):
            SectorRegistry(profile=profile, mappings=mappings)


# ===========================================================================
# T5〜T9: SectorRegistry 公開 API
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSectorRegistryAPI:
    """SectorRegistry 公開 API のテスト群。"""

    @pytest.fixture()
    def reg(self) -> SectorRegistry:
        """テスト用の SectorRegistry を作成する。"""
        profile = _make_profile()
        mappings = (
            _make_mapping(
                "RevenueTST", "revenue_tst",
                general_equivalent="revenue",
            ),
            _make_mapping(
                "CostTST", "cost_tst",
            ),
            _make_mapping(
                "AssetTST", "asset_tst",
            ),
        )
        return SectorRegistry(profile=profile, mappings=mappings)

    def test_t5_lookup_returns_mapping(self, reg: SectorRegistry) -> None:
        """lookup() が登録済み concept でマッピングを返す。"""
        m = reg.lookup("RevenueTST")
        assert m is not None
        assert m.sector_key == "revenue_tst"

    def test_t5b_lookup_returns_none(self, reg: SectorRegistry) -> None:
        """lookup() が未登録 concept で None を返す。"""
        assert reg.lookup("Unknown") is None

    def test_t6_sector_key(self, reg: SectorRegistry) -> None:
        """sector_key() が正規化キーを返す。"""
        assert reg.sector_key("RevenueTST") == "revenue_tst"
        assert reg.sector_key("Unknown") is None

    def test_t7_reverse_lookup(self, reg: SectorRegistry) -> None:
        """reverse_lookup() が逆引きできる。"""
        m = reg.reverse_lookup("revenue_tst")
        assert m is not None
        assert m.concept == "RevenueTST"
        assert reg.reverse_lookup("unknown_key") is None

    def test_t7b_lookup_reverse_roundtrip(
        self, reg: SectorRegistry,
    ) -> None:
        """lookup → reverse_lookup のラウンドトリップ。"""
        m = reg.lookup("RevenueTST")
        assert m is not None
        rev = reg.reverse_lookup(m.sector_key)
        assert rev is m

    def test_t9_all_mappings(self, reg: SectorRegistry) -> None:
        """all_mappings() が全件返す。"""
        assert len(reg.all_mappings()) == 3

    def test_t9b_all_sector_keys(self, reg: SectorRegistry) -> None:
        """all_sector_keys() が frozenset を返す。"""
        keys = reg.all_sector_keys()
        assert isinstance(keys, frozenset)
        assert len(keys) == 3

    def test_t9c_get_profile(self, reg: SectorRegistry) -> None:
        """get_profile() がプロファイルを返す。"""
        profile = reg.get_profile()
        assert profile.sector_id == "test"

    def test_t9d_to_general_key(self, reg: SectorRegistry) -> None:
        """to_general_key() が一般事業会社のキーを返す。"""
        assert reg.to_general_key("RevenueTST") == "revenue"
        assert reg.to_general_key("CostTST") is None
        assert reg.to_general_key("Unknown") is None

    def test_t9e_from_general_key(self, reg: SectorRegistry) -> None:
        """from_general_key() が逆引きタプルを返す。"""
        result = reg.from_general_key("revenue")
        assert len(result) == 1
        assert result[0].concept == "RevenueTST"

    def test_t9f_from_general_key_empty(self, reg: SectorRegistry) -> None:
        """from_general_key() が対応なしで空タプルを返す。"""
        assert reg.from_general_key("nonexistent") == ()

    def test_t9h_sector_key_count(self, reg: SectorRegistry) -> None:
        """sector_key_count プロパティが正しい値を返す。"""
        assert reg.sector_key_count == 3

    def test_t9i_repr(self, reg: SectorRegistry) -> None:
        """__repr__() がデバッグ用文字列を返す。"""
        r = repr(reg)
        assert "test" in r
        assert "3" in r

    def test_t9j_len(self, reg: SectorRegistry) -> None:
        """__len__() がマッピング数を返す。"""
        assert len(reg) == 3


# ===========================================================================
# データモデルの不変性テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestDataModelImmutability:
    """frozen dataclass の不変性テスト。"""

    def test_sector_concept_mapping_is_frozen(self) -> None:
        """SectorConceptMapping が frozen で変更不可。"""
        m = _make_mapping()
        with pytest.raises(AttributeError):
            m.concept = "changed"  # type: ignore[misc]

    def test_sector_profile_is_frozen(self) -> None:
        """SectorProfile が frozen で変更不可。"""
        p = _make_profile()
        with pytest.raises(AttributeError):
            p.sector_id = "changed"  # type: ignore[misc]

    def test_empty_registry(self) -> None:
        """空のマッピングで Registry を作成できる。"""
        profile = _make_profile()
        reg = SectorRegistry(profile=profile, mappings=())
        assert len(reg) == 0
        assert reg.all_sector_keys() == frozenset()


# ===========================================================================
# to_general_map / SectorProfile オプション
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestToGeneralMap:
    """to_general_map() のテスト。"""

    def test_to_general_map_returns_dict(self) -> None:
        """to_general_map() が正しい辞書を返す。"""
        profile = _make_profile()
        mappings = (
            _make_mapping(
                "RevTST", "rev_tst",
                general_equivalent="revenue",
            ),
            _make_mapping("CostTST", "cost_tst"),
        )
        reg = SectorRegistry(profile=profile, mappings=mappings)
        gmap = reg.to_general_map()
        assert gmap == {"rev_tst": "revenue"}

    def test_to_general_map_empty(self) -> None:
        """general_equivalent が全て None なら空辞書。"""
        profile = _make_profile()
        mappings = (
            _make_mapping("A", "key_a"),
        )
        reg = SectorRegistry(profile=profile, mappings=mappings)
        assert reg.to_general_map() == {}


@pytest.mark.small
@pytest.mark.unit
class TestSectorProfileOptionalFields:
    """SectorProfile オプショナルフィールドのテスト。"""

    def test_default_optional_fields_are_none(self) -> None:
        """デフォルトでオプショナルフィールドが None。"""
        profile = _make_profile()
        assert profile.has_consolidated_template is None
        assert profile.cf_method is None

    def test_optional_fields_can_be_set(self) -> None:
        """オプショナルフィールドに値を設定できる。"""
        profile = SectorProfile(
            sector_id="banking",
            display_name_ja="銀行業",
            display_name_en="Banking",
            industry_codes=frozenset({"bk1"}),
            concept_suffix="BNK",
            has_consolidated_template=True,
            cf_method="both",
        )
        assert profile.has_consolidated_template is True
        assert profile.cf_method == "both"

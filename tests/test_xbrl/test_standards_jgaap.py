"""J-GAAP 科目の正規化マッピングのテスト。

standards/jgaap モジュールの全公開 API と内部データ整合性を検証する。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from edinet.models.financial import StatementType
from edinet.financial.standards.jgaap import (
    ConceptMapping,
    JGAAPProfile,
    all_canonical_keys,
    all_mappings,
    canonical_key,
    get_profile,
    is_jgaap_module,
    jgaap_specific_concepts,
    lookup,
    mappings_for_statement,
    reverse_lookup,
)


# ===========================================================================
# P0: 必須テスト（マッピング基本・一覧取得・J-GAAP 固有・レガシー互換・名前空間・プロファイル）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP0Essential:
    """P0 必須テスト群（T1-T29）。"""

    # --- T1-T7: マッピング基本 ---

    def test_t01_lookup_returns_mapping(self) -> None:
        """lookup() が登録済み concept で ConceptMapping を返す。"""
        result = lookup("NetSales")
        assert result is not None
        assert isinstance(result, ConceptMapping)
        assert result.canonical_key == "revenue"

    def test_t02_lookup_returns_none_for_unknown(self) -> None:
        """lookup() が未登録 concept で None を返す。"""
        assert lookup("UnknownConcept") is None

    def test_t03_canonical_key_returns_key(self) -> None:
        """canonical_key() が正規化キーを返す。"""
        assert canonical_key("OperatingIncome") == "operating_income"

    def test_t04_canonical_key_returns_none_for_unknown(self) -> None:
        """canonical_key() が未登録 concept で None を返す。"""
        assert canonical_key("FooBar") is None

    def test_t05_reverse_lookup_returns_mapping(self) -> None:
        """reverse_lookup() が正規化キーから ConceptMapping を返す。"""
        result = reverse_lookup("revenue")
        assert result is not None
        assert result.concept == "NetSales"

    def test_t06_reverse_lookup_returns_none_for_unknown(self) -> None:
        """reverse_lookup() が未登録キーで None を返す。"""
        assert reverse_lookup("nonexistent_key") is None

    def test_t07_lookup_and_reverse_roundtrip(self) -> None:
        """lookup → reverse_lookup のラウンドトリップが一致する。"""
        m = lookup("OrdinaryIncome")
        assert m is not None
        rev = reverse_lookup(m.canonical_key)
        assert rev is m

    # --- T8-T13: 一覧取得 ---

    def test_t08_pl_mappings_count(self) -> None:
        """PL マッピングが 16 件。"""
        result = mappings_for_statement(StatementType.INCOME_STATEMENT)
        assert len(result) == 16

    def test_t09_bs_mappings_count(self) -> None:
        """BS マッピングが 24 件。"""
        result = mappings_for_statement(StatementType.BALANCE_SHEET)
        assert len(result) == 24

    def test_t10_cf_mappings_count(self) -> None:
        """CF マッピングが 35 件（合計行 8 + 営業内訳 15 + 投資内訳 7 + 財務内訳 7 - 期首期末除外2）。"""
        result = mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)
        assert len(result) == 35

    def test_t11_all_mappings_count(self) -> None:
        """全マッピングが 83 件（PL16 + BS24 + CF35 + KPI8）。"""
        assert len(all_mappings()) == 83

    def test_t12_all_canonical_keys_unique(self) -> None:
        """全 canonical_key が 83 個でユニーク。"""
        keys = all_canonical_keys()
        assert len(keys) == 83

    def test_t13_mappings_for_statement_subset_of_all(self) -> None:
        """各 statement の mappings_for_statement() が all_mappings() のサブセット。"""
        all_set = set(all_mappings())
        for st in StatementType:
            mappings = mappings_for_statement(st)
            assert set(mappings).issubset(all_set), (
                f"{st.value} の mappings_for_statement() が all_mappings() のサブセットでない"
            )

    # --- T14-T17: J-GAAP 固有 ---

    def test_t14_ordinary_income_is_jgaap_specific(self) -> None:
        """OrdinaryIncome.is_jgaap_specific が True。"""
        m = lookup("OrdinaryIncome")
        assert m is not None
        assert m.is_jgaap_specific is True

    def test_t15_net_sales_not_jgaap_specific(self) -> None:
        """NetSales.is_jgaap_specific が False。"""
        m = lookup("NetSales")
        assert m is not None
        assert m.is_jgaap_specific is False

    def test_t16_jgaap_specific_contains_ordinary_income(self) -> None:
        """jgaap_specific_concepts() に OrdinaryIncome が含まれる。"""
        specifics = jgaap_specific_concepts()
        concepts = {m.concept for m in specifics}
        assert "OrdinaryIncome" in concepts

    def test_t17_jgaap_specific_count(self) -> None:
        """J-GAAP 固有の概念が 5 件。"""
        specifics = jgaap_specific_concepts()
        assert len(specifics) == 5
        expected = {
            "NonOperatingIncome",
            "NonOperatingExpenses",
            "OrdinaryIncome",
            "ExtraordinaryIncome",
            "ExtraordinaryLoss",
        }
        assert {m.concept for m in specifics} == expected

    # --- T23-T26: 名前空間判定 ---

    def test_t23_jppfs_is_jgaap(self) -> None:
        """jppfs は J-GAAP モジュール。"""
        assert is_jgaap_module("jppfs") is True

    def test_t24_jpcrp_is_jgaap(self) -> None:
        """jpcrp は J-GAAP モジュール。"""
        assert is_jgaap_module("jpcrp") is True

    def test_t25_jpigp_not_jgaap(self) -> None:
        """jpigp は J-GAAP モジュールではない。"""
        assert is_jgaap_module("jpigp") is False

    def test_t26_unknown_not_jgaap(self) -> None:
        """未知のモジュールグループは J-GAAP ではない。"""
        assert is_jgaap_module("unknown") is False

    # --- T27-T29: プロファイル ---

    def test_t27_profile_standard_id(self) -> None:
        """プロファイルの standard_id が 'japan_gaap'。"""
        profile = get_profile()
        assert profile.standard_id == "japan_gaap"

    def test_t28_profile_has_ordinary_income(self) -> None:
        """プロファイルの has_ordinary_income が True。"""
        profile = get_profile()
        assert profile.has_ordinary_income is True

    def test_t29_profile_canonical_key_count(self) -> None:
        """プロファイルの canonical_key_count が 83。"""
        profile = get_profile()
        assert profile.canonical_key_count == 83


# ===========================================================================
# P1: データ整合性テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestP1DataIntegrity:
    """P1 データ整合性テスト群（T30-T40）。"""

    def test_t30_concepts_unique(self) -> None:
        """全 concept がユニーク。"""
        concepts = [m.concept for m in all_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_t31_canonical_keys_nonempty(self) -> None:
        """全 canonical_key が非空。"""
        for m in all_mappings():
            assert m.canonical_key, f"{m.concept} の canonical_key が空"

    def test_t35_frozen_dataclass(self) -> None:
        """ConceptMapping が frozen dataclass。"""
        m = lookup("NetSales")
        assert m is not None
        with pytest.raises(AttributeError):
            m.canonical_key = "changed"  # type: ignore[misc]

    def test_t38_kpi_statement_type_none(self) -> None:
        """KPI 科目の statement_type が全て None。"""
        kpi_concepts = {
            "BasicEarningsLossPerShareSummaryOfBusinessResults",
            "DilutedEarningsPerShareSummaryOfBusinessResults",
            "NetAssetsPerShareSummaryOfBusinessResults",
            "DividendPerShareDividendsOfSurplus",
            "EquityToAssetRatioSummaryOfBusinessResults",
            "RateOfReturnOnEquitySummaryOfBusinessResults",
            "PriceEarningsRatioSummaryOfBusinessResults",
            "NumberOfEmployees",
        }
        for concept_name in kpi_concepts:
            m = lookup(concept_name)
            assert m is not None, f"{concept_name} が見つからない"
            assert m.statement_type is None, (
                f"{concept_name} の statement_type が None でない"
            )

    def test_t39_profile_is_frozen(self) -> None:
        """JGAAPProfile が frozen dataclass。"""
        profile = get_profile()
        assert isinstance(profile, JGAAPProfile)
        with pytest.raises(AttributeError):
            profile.standard_id = "changed"  # type: ignore[misc]

    def test_t40_all_mappings_order_pl_bs_cf_kpi(self) -> None:
        """all_mappings() が PL → BS → CF → KPI の順で返される。"""
        mappings = all_mappings()
        statement_types = [m.statement_type for m in mappings]

        first_pl = next(
            i for i, st in enumerate(statement_types)
            if st == StatementType.INCOME_STATEMENT
        )
        first_bs = next(
            i for i, st in enumerate(statement_types)
            if st == StatementType.BALANCE_SHEET
        )
        first_cf = next(
            i for i, st in enumerate(statement_types)
            if st == StatementType.CASH_FLOW_STATEMENT
        )
        first_kpi = next(
            i for i, st in enumerate(statement_types)
            if st is None
        )
        assert first_pl < first_bs < first_cf < first_kpi


# ===========================================================================
# P1b: CK インスタンステスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestCKInstances:
    """全 canonical_key が CK StrEnum のインスタンスであることを検証する。"""

    def test_all_canonical_keys_are_ck_instances(self) -> None:
        """全マッピングの canonical_key が CK インスタンス。"""
        from edinet.financial.standards.canonical_keys import CK

        for m in all_mappings():
            assert isinstance(m.canonical_key, CK), (
                f"{m.concept} の canonical_key '{m.canonical_key}' が "
                f"CK インスタンスでない"
            )


# ===========================================================================
# タクソノミ実在検証（EDINET_TAXONOMY_ROOT 必須）
# ===========================================================================

_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_SKIP_REASON = "EDINET_TAXONOMY_ROOT が未設定"


def _collect_xsd_concepts_jgaap(taxonomy_root: str) -> frozenset[str]:
    """jppfs_cor / jpcrp_cor の XSD から全 concept 名を抽出する。"""
    concepts: set[str] = set()
    pattern = re.compile(r'name="([^"]+)"')
    root = Path(taxonomy_root) / "taxonomy"
    for module_dir in ("jppfs", "jpcrp"):
        target = root / module_dir
        if not target.exists():
            continue
        for xsd_file in target.rglob("*.xsd"):
            for line in xsd_file.read_text(encoding="utf-8").splitlines():
                m = pattern.search(line)
                if m:
                    concepts.add(m.group(1))
    return frozenset(concepts)


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
@pytest.mark.medium
@pytest.mark.integration
class TestTaxonomyExistence:
    """J-GAAP マッピングの全 concept がタクソノミ XSD に実在するか検証する。

    ハルシネーション防止のための品質ゲート。
    EDINET_TAXONOMY_ROOT 環境変数が設定されている場合のみ実行される。
    """

    @pytest.fixture(scope="class")
    def xsd_concepts(self) -> frozenset[str]:
        """タクソノミ XSD の全 concept 名。"""
        assert _TAXONOMY_ROOT is not None
        return _collect_xsd_concepts_jgaap(_TAXONOMY_ROOT)

    def test_all_jgaap_concepts_exist_in_taxonomy(
        self,
        xsd_concepts: frozenset[str],
    ) -> None:
        """全 J-GAAP concept がタクソノミ XSD に実在する。"""
        missing = [
            m.concept
            for m in all_mappings()
            if m.concept not in xsd_concepts
        ]
        assert not missing, (
            f"タクソノミ XSD に存在しない J-GAAP concept: {missing}"
        )

    def test_pl_concepts_exist(self, xsd_concepts: frozenset[str]) -> None:
        """PL concept が全てタクソノミに実在する。"""
        missing = [
            m.concept
            for m in mappings_for_statement(StatementType.INCOME_STATEMENT)
            if m.concept not in xsd_concepts
        ]
        assert not missing, f"PL で不在: {missing}"

    def test_bs_concepts_exist(self, xsd_concepts: frozenset[str]) -> None:
        """BS concept が全てタクソノミに実在する。"""
        missing = [
            m.concept
            for m in mappings_for_statement(StatementType.BALANCE_SHEET)
            if m.concept not in xsd_concepts
        ]
        assert not missing, f"BS で不在: {missing}"

    def test_cf_concepts_exist(self, xsd_concepts: frozenset[str]) -> None:
        """CF concept が全てタクソノミに実在する。"""
        missing = [
            m.concept
            for m in mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)
            if m.concept not in xsd_concepts
        ]
        assert not missing, f"CF で不在: {missing}"

"""summary_mappings モジュールのテスト。

SummaryOfBusinessResults の CK マッピングの全公開 API と
データ整合性を検証する。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from edinet.financial.standards.canonical_keys import CK
from edinet.financial.standards.summary_mappings import (
    SummaryMapping,
    all_summary_mappings,
    lookup_summary,
    summary_concepts_for_standard,
)


# ===========================================================================
# 基本 API テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestLookupSummary:
    """lookup_summary() のテスト。"""

    def test_jgaap_net_sales(self) -> None:
        """J-GAAP の NetSalesSummaryOfBusinessResults → "revenue"。"""
        assert lookup_summary("NetSalesSummaryOfBusinessResults") == "revenue"

    def test_ifrs_revenue(self) -> None:
        """IFRS の RevenueIFRSSummaryOfBusinessResults → "revenue"。"""
        assert lookup_summary("RevenueIFRSSummaryOfBusinessResults") == "revenue"

    def test_usgaap_revenue(self) -> None:
        """US-GAAP の RevenuesUSGAAPSummaryOfBusinessResults → "revenue"。"""
        assert lookup_summary("RevenuesUSGAAPSummaryOfBusinessResults") == "revenue"

    def test_jmis_revenue(self) -> None:
        """JMIS の RevenueJMISSummaryOfBusinessResults → "revenue"。"""
        assert lookup_summary("RevenueJMISSummaryOfBusinessResults") == "revenue"

    def test_unknown_concept_returns_none(self) -> None:
        """未登録 concept で None を返す。"""
        assert lookup_summary("UnknownConcept") is None

    def test_pl_concept_returns_none(self) -> None:
        """PL 本体の概念名ではマッチしない。"""
        assert lookup_summary("NetSales") is None
        assert lookup_summary("RevenueIFRS") is None

    def test_operating_income_jgaap_mapping(self) -> None:
        """J-GAAP の経常利益サマリーが ordinary_income にマッピングされる。"""
        assert lookup_summary("OrdinaryIncomeLossSummaryOfBusinessResults") == "ordinary_income"

    def test_total_assets(self) -> None:
        """4 基準共通の TotalAssets が total_assets にマッピングされる。"""
        assert lookup_summary("TotalAssetsSummaryOfBusinessResults") == "total_assets"
        assert lookup_summary("TotalAssetsIFRSSummaryOfBusinessResults") == "total_assets"
        assert lookup_summary("TotalAssetsUSGAAPSummaryOfBusinessResults") == "total_assets"
        assert lookup_summary("TotalAssetsJMISSummaryOfBusinessResults") == "total_assets"


# ===========================================================================
# 一覧 API テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestAllSummaryMappings:
    """all_summary_mappings() のテスト。"""

    def test_returns_tuple(self) -> None:
        """戻り値が tuple。"""
        result = all_summary_mappings()
        assert isinstance(result, tuple)

    def test_nonempty(self) -> None:
        """空でない。"""
        assert len(all_summary_mappings()) > 0

    def test_all_are_summary_mappings(self) -> None:
        """全要素が SummaryMapping。"""
        for m in all_summary_mappings():
            assert isinstance(m, SummaryMapping)


@pytest.mark.small
@pytest.mark.unit
class TestSummaryConceptsForStandard:
    """summary_concepts_for_standard() のテスト。"""

    def test_jgaap(self) -> None:
        """J-GAAP マッピングが非空。"""
        result = summary_concepts_for_standard("jgaap")
        assert len(result) > 0
        assert all(m.standard == "jgaap" for m in result)

    def test_ifrs(self) -> None:
        """IFRS マッピングが非空。"""
        result = summary_concepts_for_standard("ifrs")
        assert len(result) > 0
        assert all(m.standard == "ifrs" for m in result)

    def test_usgaap(self) -> None:
        """US-GAAP マッピングが非空。"""
        result = summary_concepts_for_standard("usgaap")
        assert len(result) > 0
        assert all(m.standard == "usgaap" for m in result)

    def test_jmis(self) -> None:
        """JMIS マッピングが非空。"""
        result = summary_concepts_for_standard("jmis")
        assert len(result) > 0
        assert all(m.standard == "jmis" for m in result)

    def test_unknown_returns_empty(self) -> None:
        """未知の基準は空タプル。"""
        assert summary_concepts_for_standard("unknown") == ()


# ===========================================================================
# データ整合性テスト
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestDataIntegrity:
    """データ整合性テスト。"""

    def test_concepts_unique(self) -> None:
        """全 concept がユニーク。"""
        concepts = [m.concept for m in all_summary_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_all_canonical_keys_are_ck(self) -> None:
        """全 canonical_key が CK インスタンス。"""
        for m in all_summary_mappings():
            assert isinstance(m.canonical_key, CK), (
                f"{m.concept} の canonical_key '{m.canonical_key}' が "
                f"CK インスタンスでない"
            )

    def test_frozen_dataclass(self) -> None:
        """SummaryMapping が frozen。"""
        m = all_summary_mappings()[0]
        with pytest.raises(AttributeError):
            m.concept = "changed"  # type: ignore[misc]

    def test_all_concepts_end_with_summary(self) -> None:
        """全 concept が 'SummaryOfBusinessResults' で終わる。"""
        for m in all_summary_mappings():
            assert "SummaryOfBusinessResults" in m.concept, (
                f"{m.concept} に 'SummaryOfBusinessResults' が含まれない"
            )

    def test_four_standards_covered(self) -> None:
        """4 基準全てがカバーされている。"""
        standards = {m.standard for m in all_summary_mappings()}
        assert standards == {"jgaap", "ifrs", "usgaap", "jmis"}


# ===========================================================================
# タクソノミ XSD 実在検証（EDINET_TAXONOMY_ROOT 必須）
# ===========================================================================

_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_SKIP_REASON = "EDINET_TAXONOMY_ROOT が未設定"


def _collect_jpcrp_concepts(taxonomy_root: str) -> frozenset[str]:
    """jpcrp_cor の XSD から全 concept 名を抽出する。"""
    concepts: set[str] = set()
    pattern = re.compile(r'name="([^"]+)"')
    root = Path(taxonomy_root) / "taxonomy" / "jpcrp"
    if not root.exists():
        return frozenset()
    for xsd_file in root.rglob("*.xsd"):
        for line in xsd_file.read_text(encoding="utf-8").splitlines():
            m = pattern.search(line)
            if m:
                concepts.add(m.group(1))
    return frozenset(concepts)


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
@pytest.mark.medium
@pytest.mark.integration
class TestTaxonomyExistence:
    """全 SummaryMapping の concept が jpcrp_cor XSD に実在するか検証する。

    ハルシネーション防止の品質ゲート。
    _FILER_SPECIFIC_CONCEPTS 除外リスト不要（全て標準タクソノミ）。
    """

    @pytest.fixture(scope="class")
    def xsd_concepts(self) -> frozenset[str]:
        """jpcrp_cor XSD の全 concept 名。"""
        assert _TAXONOMY_ROOT is not None
        return _collect_jpcrp_concepts(_TAXONOMY_ROOT)

    def test_all_concepts_exist_in_taxonomy(
        self,
        xsd_concepts: frozenset[str],
    ) -> None:
        """全 SummaryMapping の concept が XSD に実在する（除外リストなし）。"""
        missing = [
            m.concept
            for m in all_summary_mappings()
            if m.concept not in xsd_concepts
        ]
        assert not missing, (
            f"jpcrp_cor XSD に存在しない concept: {missing}"
        )

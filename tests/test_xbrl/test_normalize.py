"""normalize モジュールのテスト。

v0.2.0 で以下の関数は削除された:
    - get_canonical_key()
    - get_concept_for_key()
    - cross_standard_lookup()
    - get_canonical_key_for_sector()

残存する公開 API のテスト: get_known_concepts, get_concept_order, get_concept_set。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from edinet.models.financial import StatementType
from edinet.xbrl.dei import AccountingStandard
from edinet.financial.standards.normalize import (
    get_concept_order,
    get_known_concepts,
)


# ===================================================================
# get_known_concepts（taxonomy_root なし → 空の frozenset）
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestGetKnownConceptsNoTaxonomy:
    """taxonomy_root なしの get_known_concepts テスト（レガシーフォールバック）。"""

    def test_jgaap_pl_legacy(self) -> None:
        """J-GAAP PL のレガシーフォールバックが非空。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP, StatementType.INCOME_STATEMENT
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0
        assert "NetSales" in result

    def test_ifrs_pl_legacy(self) -> None:
        """IFRS PL のレガシーフォールバックが非空。"""
        result = get_known_concepts(
            AccountingStandard.IFRS, StatementType.INCOME_STATEMENT
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0

    def test_usgaap_returns_empty(self) -> None:
        """US-GAAP は空 frozenset。"""
        result = get_known_concepts(
            AccountingStandard.US_GAAP, StatementType.INCOME_STATEMENT
        )
        assert result == frozenset()

    def test_none_falls_back_to_jgaap(self) -> None:
        """standard=None は J-GAAP にフォールバック。"""
        result = get_known_concepts(None, StatementType.INCOME_STATEMENT)
        jgaap_result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP, StatementType.INCOME_STATEMENT
        )
        assert result == jgaap_result


# ===================================================================
# get_concept_order（taxonomy_root なし → レガシーフォールバック）
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestGetConceptOrderNoTaxonomy:
    """taxonomy_root なしの get_concept_order テスト。"""

    def test_jgaap_pl_order_legacy(self) -> None:
        """J-GAAP PL のレガシー順序が非空。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP, StatementType.INCOME_STATEMENT
        )
        assert isinstance(result, dict)
        assert "NetSales" in result
        assert "OperatingIncome" in result
        assert result["NetSales"] < result["OperatingIncome"]


# ===================================================================
# concept_sets 接続の統合テスト（EDINET_TAXONOMY_ROOT 必須）
# ===================================================================


_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_skip_no_taxonomy = pytest.mark.skipif(
    _TAXONOMY_ROOT is None,
    reason="EDINET_TAXONOMY_ROOT が未設定",
)


@_skip_no_taxonomy
class TestConceptSetsIntegration:
    """concept_sets 接続の統合テスト。"""

    def test_known_concepts_taxonomy_root_returns_concept_sets(
        self,
    ) -> None:
        """taxonomy_root ありで concept_sets 経由の known_concepts。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0
        assert "NetSales" in result

    def test_concept_order_taxonomy_root_returns_concept_sets(
        self,
    ) -> None:
        """taxonomy_root ありで concept_sets 経由の表示順序。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
        )
        assert isinstance(result, dict)
        assert len(result) > 0
        assert "NetSales" in result

    def test_known_concepts_ifrs_taxonomy_root(self) -> None:
        """IFRS + taxonomy_root で jpigp の concept_sets を使う。"""
        result = get_known_concepts(
            AccountingStandard.IFRS,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0

    def test_known_concepts_industry_code_banking(self) -> None:
        """industry_code='bk1' で業種別 concept_sets。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
            industry_code="bk1",
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0
        # 一般事業会社 (cai) とは異なるセットを返す
        general = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
        )
        assert result != general

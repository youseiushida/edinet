"""normalize モジュールのテスト。

会計基準横断の統一アクセスレイヤーの全公開 API を検証する。
Detroit 派: 公開 API のみをテストし、内部実装に依存しない。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from edinet.models.financial import StatementType
from edinet.xbrl.dei import AccountingStandard
from edinet.financial.standards.normalize import (
    cross_standard_lookup,
    get_canonical_key,
    get_canonical_key_for_sector,
    get_concept_for_key,
    get_concept_order,
    get_known_concepts,
)
from edinet.financial.standards import jgaap, ifrs


# ===================================================================
# T01-T04: get_canonical_key
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestGetCanonicalKey:
    """get_canonical_key のテスト。"""

    def test_t01_jgaap_net_sales(self) -> None:
        """T01: J-GAAP の NetSales → "revenue"。"""
        result = get_canonical_key("NetSales", AccountingStandard.JAPAN_GAAP)
        assert result == "revenue"

    def test_t02_ifrs_revenue(self) -> None:
        """T02: IFRS の RevenueIFRS → "revenue"。"""
        result = get_canonical_key("RevenueIFRS", AccountingStandard.IFRS)
        assert result == "revenue"

    def test_t03_unknown_concept(self) -> None:
        """T03: 未知の concept → None。"""
        result = get_canonical_key("UnknownConcept", AccountingStandard.JAPAN_GAAP)
        assert result is None

    def test_t04_auto_detect_none(self) -> None:
        """T04: standard=None で J-GAAP → IFRS 順の自動検索。"""
        # J-GAAP 概念
        assert get_canonical_key("NetSales") == "revenue"
        # IFRS 概念
        assert get_canonical_key("RevenueIFRS") == "revenue"
        # 未知
        assert get_canonical_key("NonExistent") is None


# ===================================================================
# T05-T07: get_concept_for_key
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestGetConceptForKey:
    """get_concept_for_key のテスト。"""

    def test_t05_jgaap_revenue(self) -> None:
        """T05: J-GAAP 基準で "revenue" → "NetSales"。"""
        result = get_concept_for_key("revenue", AccountingStandard.JAPAN_GAAP)
        assert result == "NetSales"

    def test_t06_ifrs_revenue(self) -> None:
        """T06: IFRS 基準で "revenue" → "RevenueIFRS"。"""
        result = get_concept_for_key("revenue", AccountingStandard.IFRS)
        assert result == "RevenueIFRS"

    def test_t07_missing_key(self) -> None:
        """T07: 未知の canonical_key → None。"""
        result = get_concept_for_key("nonexistent_key", AccountingStandard.JAPAN_GAAP)
        assert result is None


# ===================================================================
# T08-T11: get_known_concepts
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestGetKnownConcepts:
    """get_known_concepts のテスト。"""

    def test_t08_jgaap_pl(self) -> None:
        """T08: J-GAAP PL の概念集合が frozenset で非空。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP, StatementType.INCOME_STATEMENT
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0
        assert "NetSales" in result

    def test_t09_ifrs_bs(self) -> None:
        """T09: IFRS BS の概念集合に IFRS 概念が含まれる。"""
        result = get_known_concepts(
            AccountingStandard.IFRS, StatementType.BALANCE_SHEET
        )
        assert isinstance(result, frozenset)
        assert "AssetsIFRS" in result
        assert "CashAndCashEquivalentsIFRS" in result

    def test_t10_usgaap_empty(self) -> None:
        """T10: US-GAAP の概念集合は空。"""
        result = get_known_concepts(
            AccountingStandard.US_GAAP, StatementType.INCOME_STATEMENT
        )
        assert result == frozenset()

    def test_t11_none_falls_back_to_jgaap(self) -> None:
        """T11: standard=None は J-GAAP にフォールバック。"""
        result = get_known_concepts(None, StatementType.INCOME_STATEMENT)
        jgaap_result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP, StatementType.INCOME_STATEMENT
        )
        assert result == jgaap_result


# ===================================================================
# T12-T13: get_concept_order
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestGetConceptOrder:
    """get_concept_order のテスト。"""

    def test_t12_jgaap_pl_order(self) -> None:
        """T12: J-GAAP PL の順序辞書が正しい。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP, StatementType.INCOME_STATEMENT
        )
        assert isinstance(result, dict)
        assert "NetSales" in result
        assert "OperatingIncome" in result
        # NetSales は OperatingIncome より前
        assert result["NetSales"] < result["OperatingIncome"]

    def test_t13_ifrs_pl_contains_revenue(self) -> None:
        """T13: IFRS PL の順序辞書に RevenueIFRS が含まれる。"""
        result = get_concept_order(
            AccountingStandard.IFRS, StatementType.INCOME_STATEMENT
        )
        assert "RevenueIFRS" in result


# ===================================================================
# T14-T17: cross_standard_lookup
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestCrossStandardLookup:
    """cross_standard_lookup のテスト。"""

    def test_t14_jgaap_to_ifrs(self) -> None:
        """T14: J-GAAP NetSales → IFRS RevenueIFRS。"""
        result = cross_standard_lookup(
            "NetSales", AccountingStandard.JAPAN_GAAP, AccountingStandard.IFRS
        )
        assert result == "RevenueIFRS"

    def test_t15_ifrs_to_jgaap(self) -> None:
        """T15: IFRS RevenueIFRS → J-GAAP NetSales。"""
        result = cross_standard_lookup(
            "RevenueIFRS", AccountingStandard.IFRS, AccountingStandard.JAPAN_GAAP
        )
        assert result == "NetSales"

    def test_t16_jgaap_specific_to_ifrs(self) -> None:
        """T16: J-GAAP 固有概念 (OrdinaryIncome) → IFRS は None。"""
        result = cross_standard_lookup(
            "OrdinaryIncome", AccountingStandard.JAPAN_GAAP, AccountingStandard.IFRS
        )
        assert result is None

    def test_t17_same_standard(self) -> None:
        """T17: 同一基準内の変換は自分自身を返す。"""
        result = cross_standard_lookup(
            "NetSales", AccountingStandard.JAPAN_GAAP, AccountingStandard.JAPAN_GAAP
        )
        assert result == "NetSales"


# ===================================================================
# T18: JMIS フォールバック
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestJMISFallback:
    """JMIS の IFRS フォールバックテスト。"""

    def test_t18_jmis_uses_ifrs_concepts(self) -> None:
        """T18: JMIS は IFRS 概念セットにフォールバック。"""
        jmis_concepts = get_known_concepts(
            AccountingStandard.JMIS, StatementType.INCOME_STATEMENT
        )
        ifrs_concepts = get_known_concepts(
            AccountingStandard.IFRS, StatementType.INCOME_STATEMENT
        )
        assert jmis_concepts == ifrs_concepts


# ===================================================================
# T19-T20: 安全ネット
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSafetyNet:
    """全概念の canonical_key 存在検証。"""

    def test_t19_all_jgaap_have_canonical_key(self) -> None:
        """T19: J-GAAP の全概念に canonical_key がある。"""
        for m in jgaap.all_mappings():
            key = get_canonical_key(m.concept, AccountingStandard.JAPAN_GAAP)
            assert key is not None, f"J-GAAP {m.concept} の canonical_key が None"

    def test_t20_all_ifrs_have_canonical_key(self) -> None:
        """T20: IFRS の全概念に canonical_key がある。"""
        for m in ifrs.all_mappings():
            key = get_canonical_key(m.concept, AccountingStandard.IFRS)
            assert key is not None, f"IFRS {m.concept} の canonical_key が None"


# ===================================================================
# T21: PL/BS/CF 概念重複なし
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestConceptDisjoint:
    """PL/BS/CF の概念が重複しないことの検証。"""

    def test_t21_pl_bs_cf_disjoint(self) -> None:
        """T21: 同一基準内で PL/BS/CF の concept が重複しない。"""
        for std in (AccountingStandard.JAPAN_GAAP, AccountingStandard.IFRS):
            pl = get_known_concepts(std, StatementType.INCOME_STATEMENT)
            bs = get_known_concepts(std, StatementType.BALANCE_SHEET)
            cf = get_known_concepts(std, StatementType.CASH_FLOW_STATEMENT)
            assert not (pl & bs), f"{std}: PL と BS の重複: {pl & bs}"
            assert not (pl & cf), f"{std}: PL と CF の重複: {pl & cf}"
            assert not (bs & cf), f"{std}: BS と CF の重複: {bs & cf}"


# ===================================================================
# T25-T30: sector 対応関数
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestSectorAware:
    """sector 対応の normalize 関数テスト。"""

    def test_t25_none_industry_falls_back_to_general(self) -> None:
        """T25: industry_code=None は一般事業会社にフォールバック。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            industry_code=None,
        )
        general = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
        )
        assert result == general

    def test_t26_ifrs_ignores_industry_code(self) -> None:
        """T26: IFRS は industry_code を無視して IFRS 概念を返す。"""
        result = get_known_concepts(
            AccountingStandard.IFRS,
            StatementType.INCOME_STATEMENT,
            industry_code="bk1",
        )
        ifrs_result = get_known_concepts(
            AccountingStandard.IFRS,
            StatementType.INCOME_STATEMENT,
        )
        assert result == ifrs_result

    def test_t27_canonical_key_sector_first(self) -> None:
        """T27: sector 固有概念の canonical_key が取得できる。"""
        result = get_canonical_key_for_sector(
            "OrdinaryIncomeBNK",
            AccountingStandard.JAPAN_GAAP,
            "bk1",
        )
        assert result == "ordinary_revenue_bnk"

    def test_t28_canonical_key_falls_back_to_jgaap(self) -> None:
        """T28: sector にない概念は jgaap にフォールバック。"""
        result = get_canonical_key_for_sector(
            "NetSales",
            AccountingStandard.JAPAN_GAAP,
            "bk1",
        )
        assert result == "revenue"

    def test_t30_concept_order_none_industry_same_as_general(self) -> None:
        """T30: industry_code=None は get_concept_order と同一結果。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            industry_code=None,
        )
        general = get_concept_order(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
        )
        assert result == general

    def test_legacy_fallback_no_sector_merge(self) -> None:
        """銀行業 industry_code 指定でも一般事業会社と同一結果を返す（sector 合算削除確認）。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            industry_code="bk1",
        )
        general = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
        )
        assert result == general


# ===================================================================
# T31-T34: レガシーフォールバックと taxonomy_root パラメータ
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestLegacyFallback:
    """taxonomy_root なしのレガシーフォールバックテスト。"""

    def test_t33_known_concepts_no_taxonomy_root_legacy(self) -> None:
        """T33: taxonomy_root なしで従来動作。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
        )
        assert isinstance(result, frozenset)
        assert "NetSales" in result

    def test_t34_concept_order_no_taxonomy_root_legacy(self) -> None:
        """T34: taxonomy_root なしで従来の順序動作。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
        )
        assert isinstance(result, dict)
        assert "NetSales" in result
        assert "OperatingIncome" in result

    def test_t37_ifrs_legacy_fallback(self) -> None:
        """T37: IFRS の taxonomy_root なしレガシーフォールバック。"""
        result = get_known_concepts(
            AccountingStandard.IFRS,
            StatementType.INCOME_STATEMENT,
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0

    def test_legacy_order_is_zero_based_consecutive(self) -> None:
        """レガシー order が 0-based 連番であること。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP, StatementType.INCOME_STATEMENT
        )
        values = sorted(result.values())
        assert values == list(range(len(values)))


# ===================================================================
# T31-T32, T35-T36: concept_sets 接続の統合テスト
# ===================================================================


_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_skip_no_taxonomy = pytest.mark.skipif(
    _TAXONOMY_ROOT is None,
    reason="EDINET_TAXONOMY_ROOT が未設定",
)


@_skip_no_taxonomy
class TestConceptSetsIntegration:
    """concept_sets 接続の統合テスト。"""

    def test_t31_known_concepts_taxonomy_root_returns_concept_sets(
        self,
    ) -> None:
        """T31: taxonomy_root ありで concept_sets 経由の known_concepts。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0
        assert "NetSales" in result

    def test_t32_concept_order_taxonomy_root_returns_concept_sets(
        self,
    ) -> None:
        """T32: taxonomy_root ありで concept_sets 経由の表示順序。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
        )
        assert isinstance(result, dict)
        assert len(result) > 0
        assert "NetSales" in result

    def test_t35_known_concepts_ifrs_taxonomy_root(self) -> None:
        """T35: IFRS + taxonomy_root で jpigp の concept_sets を使う。"""
        result = get_known_concepts(
            AccountingStandard.IFRS,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),  # type: ignore[arg-type]
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0

    def test_t36_known_concepts_industry_code_banking(self) -> None:
        """T36: industry_code='bk1' で業種別 concept_sets。"""
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

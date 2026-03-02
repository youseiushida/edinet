"""test_standards_detect.py — 会計基準自動判別モジュールのテスト。"""

from __future__ import annotations

import dataclasses

import pytest

from edinet.exceptions import EdinetWarning
from edinet.xbrl.dei import (
    DEI,
    AccountingStandard,
    PeriodType,
    extract_dei,
)
from edinet.xbrl.parser import RawFact
from edinet.financial.standards.detect import (
    DetectedStandard,
    DetectionMethod,
    DetailLevel,
    _DETAIL_LEVEL_MAP,
    detect_accounting_standard,
    detect_from_dei,
    detect_from_namespaces,
)

# ---------------------------------------------------------------------------
# テスト用名前空間
# ---------------------------------------------------------------------------

_NS_JPDEI = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor"
_NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
_NS_JPIGP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor"
_NS_JPCRP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
_NS_FILER = "http://disclosure.edinet-fsa.go.jp/taxonomy/E02144/AccountingStandardsOfThisCompany"


# ---------------------------------------------------------------------------
# テストヘルパー
# ---------------------------------------------------------------------------


def _make_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    namespace_uri: str = _NS_JPPFS,
    is_nil: bool = False,
) -> RawFact:
    """テスト用の RawFact を簡便に構築する。"""
    return RawFact(
        concept_qname=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref="CurrentYearDuration",
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )


def _make_dei_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    is_nil: bool = False,
) -> RawFact:
    """DEI 用の RawFact を簡便に構築する。"""
    return RawFact(
        concept_qname=f"{{{_NS_JPDEI}}}{local_name}",
        namespace_uri=_NS_JPDEI,
        local_name=local_name,
        context_ref="FilingDateInstant",
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )


def _build_dei_facts(
    accounting_standard: str | None = None,
    *,
    has_consolidated: str | None = "true",
    period_type: str | None = "FY",
    nil_standard: bool = False,
) -> tuple[RawFact, ...]:
    """典型的な DEI facts セットを構築する。"""
    facts: list[RawFact] = []

    if accounting_standard is not None:
        facts.append(
            _make_dei_fact("AccountingStandardsDEI", accounting_standard)
        )
    elif nil_standard:
        facts.append(
            _make_dei_fact("AccountingStandardsDEI", is_nil=True)
        )

    if has_consolidated is not None:
        facts.append(
            _make_dei_fact(
                "WhetherConsolidatedFinancialStatementsArePreparedDEI",
                has_consolidated,
            )
        )

    if period_type is not None:
        facts.append(
            _make_dei_fact("TypeOfCurrentPeriodDEI", period_type)
        )

    return tuple(facts)


# ---------------------------------------------------------------------------
# P0 (T1-T4): 4 会計基準の DEI 判別（メインフロー）
# ---------------------------------------------------------------------------


class TestDetectMainFlow:
    """detect_accounting_standard のメインフローテスト。"""

    def test_detect_japan_gaap_from_dei(self) -> None:
        """T1: DEI に 'Japan GAAP' → J-GAAP と判別。"""
        facts = _build_dei_facts("Japan GAAP")
        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.JAPAN_GAAP
        assert result.method == DetectionMethod.DEI
        assert result.detail_level == DetailLevel.DETAILED

    def test_detect_ifrs_from_dei(self) -> None:
        """T2: DEI に 'IFRS' → IFRS と判別。"""
        facts = _build_dei_facts("IFRS")
        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.IFRS
        assert result.method == DetectionMethod.DEI
        assert result.detail_level == DetailLevel.DETAILED

    def test_detect_us_gaap_from_dei(self) -> None:
        """T3: DEI に 'US GAAP' → US-GAAP と判別。"""
        facts = _build_dei_facts("US GAAP")
        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.US_GAAP
        assert result.method == DetectionMethod.DEI
        assert result.detail_level == DetailLevel.BLOCK_ONLY

    def test_detect_jmis_from_dei(self) -> None:
        """T4: DEI に 'JMIS' → JMIS と判別。"""
        facts = _build_dei_facts("JMIS")
        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.JMIS
        assert result.method == DetectionMethod.DEI
        assert result.detail_level == DetailLevel.BLOCK_ONLY

    def test_detect_dei_nil_falls_back_to_namespace(self) -> None:
        """T5: DEI の AccountingStandardsDEI が nil → 名前空間フォールバック。"""
        dei_facts = _build_dei_facts(nil_standard=True)
        jppfs_fact = _make_fact("NetSales", "1000000")
        facts = dei_facts + (jppfs_fact,)

        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.JAPAN_GAAP
        assert result.method == DetectionMethod.NAMESPACE
        assert result.detail_level == DetailLevel.DETAILED

    def test_detect_no_dei_falls_back_to_namespace(self) -> None:
        """T6: DEI 要素が存在しない → 名前空間フォールバック。

        大量保有報告書等で jpdei_cor の Fact が 1 つもない場合。
        extract_dei は全フィールド None の DEI を返す。
        """
        jppfs_fact = _make_fact("NetSales", "1000000")
        facts = (jppfs_fact,)

        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.JAPAN_GAAP
        assert result.method == DetectionMethod.NAMESPACE
        assert result.has_consolidated is None
        assert result.period_type is None


# ---------------------------------------------------------------------------
# P0 (T7-T11): detect_from_dei
# ---------------------------------------------------------------------------


class TestDetectFromDei:
    """detect_from_dei のテスト。"""

    def test_from_dei_with_standard(self) -> None:
        """T7: AccountingStandard Enum が設定された DEI → 正しい DetectedStandard。"""
        dei = DEI(accounting_standards=AccountingStandard.JAPAN_GAAP)
        result = detect_from_dei(dei)

        assert result.standard == AccountingStandard.JAPAN_GAAP
        assert result.method == DetectionMethod.DEI
        assert result.detail_level == DetailLevel.DETAILED

    def test_from_dei_without_standard(self) -> None:
        """T8: accounting_standards=None → standard=None, method=UNKNOWN。"""
        dei = DEI(accounting_standards=None)
        result = detect_from_dei(dei)

        assert result.standard is None
        assert result.method == DetectionMethod.UNKNOWN

    def test_from_dei_unknown_string(self) -> None:
        """T9: 未知の文字列 → standard="NewStandard", detail=None, 警告。"""
        dei = DEI(accounting_standards="NewStandard")

        with pytest.warns(EdinetWarning, match="未知の会計基準"):
            result = detect_from_dei(dei)

        assert result.standard == "NewStandard"
        assert result.method == DetectionMethod.DEI
        assert result.detail_level is None

    def test_from_dei_preserves_consolidated(self) -> None:
        """T10: DEI の has_consolidated が結果に反映される。"""
        dei = DEI(
            accounting_standards=AccountingStandard.JAPAN_GAAP,
            has_consolidated=True,
        )
        result = detect_from_dei(dei)

        assert result.has_consolidated is True

    def test_from_dei_preserves_period_type(self) -> None:
        """T11: DEI の type_of_current_period が結果に反映される。"""
        dei = DEI(
            accounting_standards=AccountingStandard.JAPAN_GAAP,
            type_of_current_period=PeriodType.HY,
        )
        result = detect_from_dei(dei)

        assert result.period_type == PeriodType.HY


# ---------------------------------------------------------------------------
# P0 (T12-T16): detect_from_namespaces
# ---------------------------------------------------------------------------


class TestDetectFromNamespaces:
    """detect_from_namespaces のテスト。"""

    def test_namespace_jppfs_only_is_jgaap(self) -> None:
        """T12: jppfs_cor のみ → J-GAAP。"""
        facts = (_make_fact("NetSales", namespace_uri=_NS_JPPFS),)
        result = detect_from_namespaces(facts)

        assert result.standard == AccountingStandard.JAPAN_GAAP
        assert result.method == DetectionMethod.NAMESPACE
        assert result.detail_level == DetailLevel.DETAILED

    def test_namespace_jpigp_present_is_ifrs(self) -> None:
        """T13: jpigp_cor が存在 → IFRS（jppfs_cor も同時に存在しても IFRS）。"""
        facts = (
            _make_fact("NetSales", namespace_uri=_NS_JPPFS),
            _make_fact("Revenue", namespace_uri=_NS_JPIGP),
        )
        result = detect_from_namespaces(facts)

        assert result.standard == AccountingStandard.IFRS
        assert result.method == DetectionMethod.NAMESPACE
        assert result.detail_level == DetailLevel.DETAILED

    def test_namespace_no_standard_taxonomy(self) -> None:
        """T14: 標準タクソノミなし → standard=None。"""
        facts = (_make_fact("SomeElement", namespace_uri=_NS_FILER),)
        result = detect_from_namespaces(facts)

        assert result.standard is None
        assert result.method == DetectionMethod.UNKNOWN

    def test_namespace_jpcrp_only_is_unknown(self) -> None:
        """T15: jpcrp_cor のみ（jppfs も jpigp もなし）→ standard=None。"""
        facts = (_make_fact("DocumentTitle", namespace_uri=_NS_JPCRP),)
        result = detect_from_namespaces(facts)

        assert result.standard is None
        assert result.method == DetectionMethod.UNKNOWN

    def test_namespace_modules_populated(self) -> None:
        """T16: namespace_modules に検出されたモジュールグループが含まれる。"""
        facts = (
            _make_fact("NetSales", namespace_uri=_NS_JPPFS),
            _make_fact("DocumentTitle", namespace_uri=_NS_JPCRP),
        )
        result = detect_from_namespaces(facts)

        assert "jppfs" in result.namespace_modules
        assert "jpcrp" in result.namespace_modules


# ---------------------------------------------------------------------------
# P1 (T17-T26): エッジケースと統合
# ---------------------------------------------------------------------------


class TestDetectEdgeCases:
    """エッジケースと統合テスト。"""

    def test_detect_dei_takes_priority_over_namespace(self) -> None:
        """T17: DEI=IFRS + 名前空間=jppfs のみ → DEI の IFRS が優先。"""
        dei_facts = _build_dei_facts("IFRS")
        jppfs_fact = _make_fact("NetSales", "1000000", namespace_uri=_NS_JPPFS)
        facts = dei_facts + (jppfs_fact,)

        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.IFRS
        assert result.method == DetectionMethod.DEI

    def test_detect_empty_facts(self) -> None:
        """T18: 空の facts タプル → standard=None, method=UNKNOWN。"""
        result = detect_accounting_standard(())

        assert result.standard is None
        assert result.method == DetectionMethod.UNKNOWN

    def test_detect_consolidation_info_in_fallback(self) -> None:
        """T19: DEI に has_consolidated はあるが accounting_standards がない
        → 名前空間フォールバック結果に has_consolidated が統合される。
        """
        dei_facts = _build_dei_facts(
            accounting_standard=None, has_consolidated="true"
        )
        jppfs_fact = _make_fact("NetSales", "1000000")
        facts = dei_facts + (jppfs_fact,)

        result = detect_accounting_standard(facts)

        assert result.standard == AccountingStandard.JAPAN_GAAP
        assert result.method == DetectionMethod.NAMESPACE
        assert result.has_consolidated is True

    def test_detected_standard_frozen(self) -> None:
        """T20: DetectedStandard が frozen であり変更不可。"""
        result = DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.DEI,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.standard = AccountingStandard.IFRS  # type: ignore[misc]

    def test_detail_level_map_completeness(self) -> None:
        """T21: 全 AccountingStandard 値に対して DetailLevel がマッピングされている。"""
        for standard in AccountingStandard:
            assert standard in _DETAIL_LEVEL_MAP, (
                f"{standard} が _DETAIL_LEVEL_MAP に含まれていません"
            )

    def test_namespace_different_taxonomy_versions(self) -> None:
        """T22: 異なるバージョンの jppfs_cor URI でも正しく判別される。"""
        old_ns = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor"
        facts = (_make_fact("NetSales", namespace_uri=old_ns),)
        result = detect_from_namespaces(facts)

        assert result.standard == AccountingStandard.JAPAN_GAAP

    def test_namespace_filer_taxonomy_ignored(self) -> None:
        """T23: 提出者別タクソノミ名前空間は module_groups に含まれない。"""
        facts = (
            _make_fact("NetSales", namespace_uri=_NS_JPPFS),
            _make_fact("CustomItem", namespace_uri=_NS_FILER),
        )
        result = detect_from_namespaces(facts)

        # module_groups には標準タクソノミのみ含まれる
        assert "filer" not in result.namespace_modules

    @pytest.mark.parametrize(
        ("standard_value", "expected_standard", "expected_detail"),
        [
            ("Japan GAAP", AccountingStandard.JAPAN_GAAP, DetailLevel.DETAILED),
            ("IFRS", AccountingStandard.IFRS, DetailLevel.DETAILED),
            ("US GAAP", AccountingStandard.US_GAAP, DetailLevel.BLOCK_ONLY),
            ("JMIS", AccountingStandard.JMIS, DetailLevel.BLOCK_ONLY),
        ],
    )
    def test_detect_parametrize_all_standards(
        self,
        standard_value: str,
        expected_standard: AccountingStandard,
        expected_detail: DetailLevel,
    ) -> None:
        """T24: 4 会計基準すべてを parametrize でテスト（DEI 経由）。"""
        facts = _build_dei_facts(standard_value)
        result = detect_accounting_standard(facts)

        assert result.standard == expected_standard
        assert result.method == DetectionMethod.DEI
        assert result.detail_level == expected_detail

    def test_detect_unknown_standard_no_namespace_fallback(self) -> None:
        """T25: DEI に未知の文字列 → メインフロー経由で standard が返る
        （is not None により名前空間フォールバックに入らない）。
        """
        dei_facts = (
            _make_dei_fact("AccountingStandardsDEI", "NewStandard"),
        )
        jppfs_fact = _make_fact("NetSales", "1000000")
        facts = dei_facts + (jppfs_fact,)

        with pytest.warns(EdinetWarning, match="未知の会計基準"):
            result = detect_accounting_standard(facts)

        assert result.standard == "NewStandard"
        assert result.method == DetectionMethod.DEI
        assert result.detail_level is None

    def test_detect_with_preextracted_dei(self) -> None:
        """T26: 事前抽出済み DEI を渡した場合、正しく判別される。"""
        facts = _build_dei_facts("Japan GAAP")
        dei = extract_dei(facts)

        result = detect_accounting_standard(facts, dei=dei)

        assert result.standard == AccountingStandard.JAPAN_GAAP
        assert result.method == DetectionMethod.DEI
        assert result.detail_level == DetailLevel.DETAILED

"""structure_contexts のテスト。"""

from __future__ import annotations

import datetime

import pytest

from edinet.exceptions import EdinetParseError
from edinet.xbrl.contexts import (
    ContextCollection,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
    structure_contexts,
)
from edinet.xbrl.parser import RawContext, parse_xbrl_facts

from .conftest import load_xbrl_bytes

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

_JPPFS_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor"


def _make_raw_context(
    context_id: str | None,
    xml: str,
    source_line: int | None = None,
) -> RawContext:
    """インライン RawContext を生成する。

    Args:
        context_id: Context ID。
        xml: Context の XML 文字列。
        source_line: 行番号。

    Returns:
        RawContext インスタンス。
    """
    return RawContext(context_id=context_id, xml=xml, source_line=source_line)


# ---------------------------------------------------------------------------
# XML 定数
# ---------------------------------------------------------------------------

DURATION_XML = (
    '<xbrli:context id="ctx_dur"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
    "<xbrli:entity>"
    '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
    "X99001-000"
    "</xbrli:identifier>"
    "</xbrli:entity>"
    "<xbrli:period>"
    "<xbrli:startDate>2024-04-01</xbrli:startDate>"
    "<xbrli:endDate>2025-03-31</xbrli:endDate>"
    "</xbrli:period>"
    "</xbrli:context>"
)

INSTANT_XML = (
    '<xbrli:context id="ctx_inst"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
    "<xbrli:entity>"
    '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
    "X99001-000"
    "</xbrli:identifier>"
    "</xbrli:entity>"
    "<xbrli:period>"
    "<xbrli:instant>2025-03-31</xbrli:instant>"
    "</xbrli:period>"
    "</xbrli:context>"
)

DIMENSION_XML = (
    '<xbrli:context id="ctx_dim"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:xbrldi="http://xbrl.org/2006/xbrldi"'
    '  xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor">'
    "<xbrli:entity>"
    '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
    "X99001-000"
    "</xbrli:identifier>"
    "</xbrli:entity>"
    "<xbrli:period>"
    "<xbrli:startDate>2024-04-01</xbrli:startDate>"
    "<xbrli:endDate>2025-03-31</xbrli:endDate>"
    "</xbrli:period>"
    "<xbrli:scenario>"
    '<xbrldi:explicitMember dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">'
    "jppfs_cor:NonConsolidatedMember"
    "</xbrldi:explicitMember>"
    "</xbrli:scenario>"
    "</xbrli:context>"
)

_SUBMITTER_PREFIX = "jpcrp030000-asr_X99001-000"
_SUBMITTER_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp030000-asr/X99001-000/2024-03-31/01/2024-06-25"

SUBMITTER_DIMENSION_XML = (
    '<xbrli:context id="ctx_sub"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:xbrldi="http://xbrl.org/2006/xbrldi"'
    f'  xmlns:{_SUBMITTER_PREFIX}="{_SUBMITTER_NS}">'
    "<xbrli:entity>"
    '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
    "X99001-000"
    "</xbrli:identifier>"
    "</xbrli:entity>"
    "<xbrli:period>"
    "<xbrli:startDate>2024-04-01</xbrli:startDate>"
    "<xbrli:endDate>2025-03-31</xbrli:endDate>"
    "</xbrli:period>"
    "<xbrli:scenario>"
    f'<xbrldi:explicitMember dimension="{_SUBMITTER_PREFIX}:CommunicationsEquipmentReportableSegmentAxis">'
    f"{_SUBMITTER_PREFIX}:CommunicationsEquipmentReportableSegmentMember"
    "</xbrldi:explicitMember>"
    "</xbrli:scenario>"
    "</xbrli:context>"
)

MULTI_DIMENSION_XML = (
    '<xbrli:context id="ctx_multi"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:xbrldi="http://xbrl.org/2006/xbrldi"'
    '  xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor">'
    "<xbrli:entity>"
    '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
    "X99001-000"
    "</xbrli:identifier>"
    "</xbrli:entity>"
    "<xbrli:period>"
    "<xbrli:startDate>2024-04-01</xbrli:startDate>"
    "<xbrli:endDate>2025-03-31</xbrli:endDate>"
    "</xbrli:period>"
    "<xbrli:scenario>"
    '<xbrldi:explicitMember dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">'
    "jppfs_cor:NonConsolidatedMember"
    "</xbrldi:explicitMember>"
    '<xbrldi:explicitMember dimension="jppfs_cor:BusinessSegmentsAxis">'
    "jppfs_cor:ReportableSegmentsMember"
    "</xbrldi:explicitMember>"
    "</xbrli:scenario>"
    "</xbrli:context>"
)


# ===========================================================================
# P0 テスト（14 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestStructureContextsP0:
    """P0: 必須テスト群。"""

    def test_parses_duration_period(self) -> None:
        """startDate/endDate が DurationPeriod に変換される。"""
        result = structure_contexts([_make_raw_context("ctx_dur", DURATION_XML)])
        ctx = result["ctx_dur"]
        assert isinstance(ctx.period, DurationPeriod)
        assert ctx.period.start_date == datetime.date(2024, 4, 1)
        assert ctx.period.end_date == datetime.date(2025, 3, 31)

    def test_parses_instant_period(self) -> None:
        """instant が InstantPeriod に変換される。"""
        result = structure_contexts([_make_raw_context("ctx_inst", INSTANT_XML)])
        ctx = result["ctx_inst"]
        assert isinstance(ctx.period, InstantPeriod)
        assert ctx.period.instant == datetime.date(2025, 3, 31)

    def test_extracts_entity_id(self) -> None:
        """entity/identifier のテキスト値が取得される。"""
        result = structure_contexts([_make_raw_context("ctx_dur", DURATION_XML)])
        assert result["ctx_dur"].entity_id == "X99001-000"

    def test_extracts_dimensions(self) -> None:
        """explicitMember が DimensionMember (Clark notation) に変換される。"""
        result = structure_contexts([_make_raw_context("ctx_dim", DIMENSION_XML)])
        ctx = result["ctx_dim"]
        assert len(ctx.dimensions) == 1
        dim = ctx.dimensions[0]
        assert dim.axis == f"{{{_JPPFS_NS}}}ConsolidatedOrNonConsolidatedAxis"
        assert dim.member == f"{{{_JPPFS_NS}}}NonConsolidatedMember"

    def test_returns_empty_dimensions_when_no_scenario(self) -> None:
        """scenario なしの Context では dimensions は空タプル。"""
        result = structure_contexts([_make_raw_context("ctx_dur", DURATION_XML)])
        assert result["ctx_dur"].dimensions == ()

    def test_returns_dict_keyed_by_context_id(self) -> None:
        """返り値が context_id をキーとする dict。"""
        result = structure_contexts([_make_raw_context("ctx_dur", DURATION_XML)])
        assert isinstance(result, dict)
        assert "ctx_dur" in result
        assert isinstance(result["ctx_dur"], StructuredContext)

    def test_handles_multiple_contexts(self) -> None:
        """instant + duration + dimension 混在を正しく処理する。"""
        raws = [
            _make_raw_context("ctx_dur", DURATION_XML),
            _make_raw_context("ctx_inst", INSTANT_XML),
            _make_raw_context("ctx_dim", DIMENSION_XML),
        ]
        result = structure_contexts(raws)
        assert len(result) == 3
        assert isinstance(result["ctx_dur"].period, DurationPeriod)
        assert isinstance(result["ctx_inst"].period, InstantPeriod)
        assert len(result["ctx_dim"].dimensions) == 1

    def test_raises_on_missing_period(self) -> None:
        """period 欠落で EdinetParseError が送出される。"""
        xml = (
            '<xbrli:context id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "</xbrli:context>"
        )
        with pytest.raises(EdinetParseError, match="period 要素が見つかりません"):
            structure_contexts([_make_raw_context("bad", xml)])

    def test_raises_on_invalid_date(self) -> None:
        """不正日付で EdinetParseError が送出される。"""
        xml = (
            '<xbrli:context id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:instant>not-a-date</xbrli:instant>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        with pytest.raises(EdinetParseError, match="日付形式が不正です"):
            structure_contexts([_make_raw_context("bad", xml)])

    def test_raises_on_missing_entity(self) -> None:
        """entity 欠落で EdinetParseError が送出される。"""
        xml = (
            '<xbrli:context id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:period>"
            "<xbrli:instant>2025-03-31</xbrli:instant>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        with pytest.raises(EdinetParseError, match="entity 要素が見つかりません"):
            structure_contexts([_make_raw_context("bad", xml)])

    def test_strips_whitespace_in_date(self) -> None:
        """日付前後の空白が strip される。"""
        xml = (
            '<xbrli:context id="ctx_ws"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:instant>  2025-03-31  </xbrli:instant>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        result = structure_contexts([_make_raw_context("ctx_ws", xml)])
        assert isinstance(result["ctx_ws"].period, InstantPeriod)
        assert result["ctx_ws"].period.instant == datetime.date(2025, 3, 31)

    def test_strips_whitespace_in_dimension_qname(self) -> None:
        """QName 前後の空白が strip される。"""
        xml = (
            '<xbrli:context id="ctx_ws"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:xbrldi="http://xbrl.org/2006/xbrldi"'
            '  xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:startDate>2024-04-01</xbrli:startDate>"
            "<xbrli:endDate>2025-03-31</xbrli:endDate>"
            "</xbrli:period>"
            "<xbrli:scenario>"
            '<xbrldi:explicitMember dimension="  jppfs_cor:ConsolidatedOrNonConsolidatedAxis  ">'
            "  jppfs_cor:NonConsolidatedMember  "
            "</xbrldi:explicitMember>"
            "</xbrli:scenario>"
            "</xbrli:context>"
        )
        result = structure_contexts([_make_raw_context("ctx_ws", xml)])
        dim = result["ctx_ws"].dimensions[0]
        assert dim.axis == f"{{{_JPPFS_NS}}}ConsolidatedOrNonConsolidatedAxis"
        assert dim.member == f"{{{_JPPFS_NS}}}NonConsolidatedMember"

    def test_empty_input(self) -> None:
        """空リストを渡すと空辞書が返る。"""
        result = structure_contexts([])
        assert result == {}

    def test_last_wins_on_duplicate_context_id(self) -> None:
        """重複 context_id は後勝ちで上書きされる。"""
        xml_first = (
            '<xbrli:context id="dup"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:instant>2025-03-31</xbrli:instant>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        xml_second = (
            '<xbrli:context id="dup"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:instant>2024-12-31</xbrli:instant>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        result = structure_contexts([
            _make_raw_context("dup", xml_first),
            _make_raw_context("dup", xml_second),
        ])
        assert len(result) == 1
        assert isinstance(result["dup"].period, InstantPeriod)
        assert result["dup"].period.instant == datetime.date(2024, 12, 31)


# ===========================================================================
# P1 テスト（8 件）
# ===========================================================================


@pytest.mark.unit
class TestStructureContextsP1:
    """P1: 推奨テスト群。"""

    @pytest.mark.small
    def test_resolves_qname_to_clark_notation(self) -> None:
        """QName が正しく Clark notation に変換される。"""
        result = structure_contexts([_make_raw_context("ctx_dim", DIMENSION_XML)])
        dim = result["ctx_dim"].dimensions[0]
        expected_axis = "{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor}ConsolidatedOrNonConsolidatedAxis"
        expected_member = "{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor}NonConsolidatedMember"
        assert dim.axis == expected_axis
        assert dim.member == expected_member

    @pytest.mark.small
    def test_handles_multiple_dimensions(self) -> None:
        """2 つの Dimension を同時に抽出する。"""
        result = structure_contexts(
            [_make_raw_context("ctx_multi", MULTI_DIMENSION_XML)],
        )
        ctx = result["ctx_multi"]
        assert len(ctx.dimensions) == 2
        axes = {d.axis for d in ctx.dimensions}
        assert f"{{{_JPPFS_NS}}}ConsolidatedOrNonConsolidatedAxis" in axes
        assert f"{{{_JPPFS_NS}}}BusinessSegmentsAxis" in axes

    @pytest.mark.small
    def test_skips_context_without_id(self, caplog: pytest.LogCaptureFixture) -> None:
        """context_id が None の RawContext はスキップされる。"""
        xml = (
            '<xbrli:context'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:instant>2025-03-31</xbrli:instant>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        with caplog.at_level("DEBUG", logger="edinet.xbrl.contexts"):
            result = structure_contexts([_make_raw_context(None, xml)])
        assert result == {}
        assert "None" in caplog.text

    @pytest.mark.small
    def test_preserves_all_periods(self) -> None:
        """当期と前期の両方がフィルタされずに保持される。"""
        xml_current = (
            '<xbrli:context id="current"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:startDate>2024-04-01</xbrli:startDate>"
            "<xbrli:endDate>2025-03-31</xbrli:endDate>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        xml_prior = (
            '<xbrli:context id="prior"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:startDate>2023-04-01</xbrli:startDate>"
            "<xbrli:endDate>2024-03-31</xbrli:endDate>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        result = structure_contexts([
            _make_raw_context("current", xml_current),
            _make_raw_context("prior", xml_prior),
        ])
        assert len(result) == 2
        assert "current" in result
        assert "prior" in result

    @pytest.mark.medium
    @pytest.mark.integration
    def test_with_simple_pl_fixture(self) -> None:
        """parse_xbrl_facts → structure_contexts の結合テスト。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(data)
        result = structure_contexts(parsed.contexts)

        assert len(result) == 4

        # CurrentYearDuration
        ctx_dur = result["CurrentYearDuration"]
        assert isinstance(ctx_dur.period, DurationPeriod)
        assert ctx_dur.period.start_date == datetime.date(2024, 4, 1)
        assert ctx_dur.period.end_date == datetime.date(2025, 3, 31)
        assert ctx_dur.entity_id == "E00001"
        assert ctx_dur.dimensions == ()

        # CurrentYearInstant
        ctx_inst = result["CurrentYearInstant"]
        assert isinstance(ctx_inst.period, InstantPeriod)
        assert ctx_inst.period.instant == datetime.date(2025, 3, 31)
        assert ctx_inst.entity_id == "E00001"

        # CurrentYearDuration_NonConsolidatedMember
        ctx_dim = result["CurrentYearDuration_NonConsolidatedMember"]
        assert isinstance(ctx_dim.period, DurationPeriod)
        assert len(ctx_dim.dimensions) == 1
        assert ctx_dim.dimensions[0].axis == f"{{{_JPPFS_NS}}}ConsolidatedOrNonConsolidatedAxis"
        assert ctx_dim.dimensions[0].member == f"{{{_JPPFS_NS}}}NonConsolidatedMember"

        # Prior1YearDuration
        ctx_prior = result["Prior1YearDuration"]
        assert isinstance(ctx_prior.period, DurationPeriod)
        assert ctx_prior.period.start_date == datetime.date(2023, 4, 1)
        assert ctx_prior.period.end_date == datetime.date(2024, 3, 31)

    @pytest.mark.small
    def test_raises_on_undefined_prefix(self) -> None:
        """未定義 prefix で EdinetParseError が送出される。"""
        xml = (
            '<xbrli:context id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:xbrldi="http://xbrl.org/2006/xbrldi">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:startDate>2024-04-01</xbrli:startDate>"
            "<xbrli:endDate>2025-03-31</xbrli:endDate>"
            "</xbrli:period>"
            "<xbrli:scenario>"
            '<xbrldi:explicitMember dimension="unknown_ns:SomeAxis">'
            "unknown_ns:SomeMember"
            "</xbrldi:explicitMember>"
            "</xbrli:scenario>"
            "</xbrli:context>"
        )
        with pytest.raises(EdinetParseError, match="prefix が未定義です"):
            structure_contexts([_make_raw_context("bad", xml)])

    @pytest.mark.small
    def test_resolves_submitter_namespace_qname(self) -> None:
        """提出者別タクソノミのハイフン・アンダースコア混在 prefix が Clark notation に正しく解決される。"""
        result = structure_contexts(
            [_make_raw_context("ctx_sub", SUBMITTER_DIMENSION_XML)],
        )
        dim = result["ctx_sub"].dimensions[0]
        assert dim.axis == f"{{{_SUBMITTER_NS}}}CommunicationsEquipmentReportableSegmentAxis"
        assert dim.member == f"{{{_SUBMITTER_NS}}}CommunicationsEquipmentReportableSegmentMember"

    @pytest.mark.small
    def test_raises_on_unprefixed_qname(self) -> None:
        """prefix なしの QName で EdinetParseError が送出される。"""
        xml = (
            '<xbrli:context id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:xbrldi="http://xbrl.org/2006/xbrldi">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:startDate>2024-04-01</xbrli:startDate>"
            "<xbrli:endDate>2025-03-31</xbrli:endDate>"
            "</xbrli:period>"
            "<xbrli:scenario>"
            '<xbrldi:explicitMember dimension="NoPrefixAxis">'
            "NoPrefixMember"
            "</xbrldi:explicitMember>"
            "</xbrli:scenario>"
            "</xbrli:context>"
        )
        with pytest.raises(EdinetParseError, match="prefix がありません"):
            structure_contexts([_make_raw_context("bad", xml)])

    @pytest.mark.small
    def test_malformed_period_no_instant_no_duration_raises(self) -> None:
        """period 内に instant も startDate/endDate もない場合 EdinetParseError が送出される。"""
        xml = (
            '<xbrli:context id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "X99001-000"
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<!-- 子要素なし -->"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        with pytest.raises(EdinetParseError, match="period の子要素が不正です"):
            structure_contexts([_make_raw_context("bad", xml)])

    @pytest.mark.small
    def test_empty_entity_identifier_text_raises(self) -> None:
        """identifier のテキストが空白のみの場合 EdinetParseError が送出される。"""
        xml = (
            '<xbrli:context id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">'
            "   "
            "</xbrli:identifier>"
            "</xbrli:entity>"
            "<xbrli:period>"
            "<xbrli:instant>2025-03-31</xbrli:instant>"
            "</xbrli:period>"
            "</xbrli:context>"
        )
        with pytest.raises(EdinetParseError, match="identifier のテキストが空です"):
            structure_contexts([_make_raw_context("bad", xml)])


# ---------------------------------------------------------------------------
# XML 生成ヘルパー（Phase 2〜）
# ---------------------------------------------------------------------------


def _make_context_xml(
    context_id: str,
    *,
    instant: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    dimensions: list[tuple[str, str, str]] | None = None,
    entity_id: str = "X99001-000",
    scheme: str = "http://disclosure.edinet-fsa.go.jp",
) -> str:
    """テスト用 Context XML を動的に組み立てる。

    Args:
        context_id: Context ID。
        instant: instant 日付。指定時は InstantPeriod。
        start_date: 開始日。end_date とセットで DurationPeriod。
        end_date: 終了日。
        dimensions: ``(namespace_uri, axis_local, member_local)`` のリスト。
        entity_id: Entity ID。
        scheme: identifier の scheme 属性。

    Returns:
        Context XML 文字列。
    """
    ns_decls = [
        'xmlns:xbrli="http://www.xbrl.org/2003/instance"',
    ]
    dim_xmls: list[str] = []
    if dimensions:
        ns_decls.append('xmlns:xbrldi="http://xbrl.org/2006/xbrldi"')
        for i, (ns_uri, axis_local, member_local) in enumerate(dimensions):
            prefix = f"ns{i}"
            ns_decls.append(f'xmlns:{prefix}="{ns_uri}"')
            dim_xmls.append(
                f'<xbrldi:explicitMember dimension="{prefix}:{axis_local}">'
                f"{prefix}:{member_local}"
                f"</xbrldi:explicitMember>"
            )

    # period
    if instant is not None:
        period_xml = f"<xbrli:instant>{instant}</xbrli:instant>"
    else:
        period_xml = (
            f"<xbrli:startDate>{start_date}</xbrli:startDate>"
            f"<xbrli:endDate>{end_date}</xbrli:endDate>"
        )

    # scenario
    scenario_xml = ""
    if dim_xmls:
        scenario_xml = "<xbrli:scenario>" + "".join(dim_xmls) + "</xbrli:scenario>"

    return (
        f'<xbrli:context id="{context_id}" {" ".join(ns_decls)}>'
        f"<xbrli:entity>"
        f'<xbrli:identifier scheme="{scheme}">{entity_id}</xbrli:identifier>'
        f"</xbrli:entity>"
        f"<xbrli:period>{period_xml}</xbrli:period>"
        f"{scenario_xml}"
        f"</xbrli:context>"
    )


def _parse_one(xml: str, context_id: str) -> StructuredContext:
    """XML 文字列を解析して StructuredContext を1つ返す。"""
    result = structure_contexts([_make_raw_context(context_id, xml)])
    return result[context_id]


_CONSOLIDATED_AXIS_CLARK = f"{{{_JPPFS_NS}}}ConsolidatedOrNonConsolidatedAxis"
_CONSOLIDATED_MEMBER_CLARK = f"{{{_JPPFS_NS}}}ConsolidatedMember"
_NON_CONSOLIDATED_MEMBER_CLARK = f"{{{_JPPFS_NS}}}NonConsolidatedMember"


# ===========================================================================
# Phase 1: entity_scheme テスト（2 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestEntityScheme:
    """entity_scheme フィールドのテスト。"""

    def test_entity_scheme_extracted(self) -> None:
        """scheme 属性が entity_scheme に格納される。"""
        xml = _make_context_xml("s1", instant="2025-03-31")
        ctx = _parse_one(xml, "s1")
        assert ctx.entity_scheme == "http://disclosure.edinet-fsa.go.jp"

    def test_entity_scheme_default_none(self) -> None:
        """entity_scheme なしで StructuredContext を構築するとデフォルト None。"""
        ctx = StructuredContext(
            context_id="test",
            period=InstantPeriod(instant=datetime.date(2025, 3, 31)),
            entity_id="E00001",
            dimensions=(),
            source_line=None,
        )
        assert ctx.entity_scheme is None


# ===========================================================================
# Phase 2: StructuredContext プロパティテスト（17 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestStructuredContextPropertiesP0:
    """P0: StructuredContext プロパティの必須テスト群。"""

    def test_is_consolidated_no_dimensions(self) -> None:
        """Dimension なしは連結として扱う。"""
        xml = _make_context_xml("c1", instant="2025-03-31")
        ctx = _parse_one(xml, "c1")
        assert ctx.is_consolidated is True

    def test_is_consolidated_with_consolidated_member(self) -> None:
        """ConsolidatedMember 明示は連結。"""
        xml = _make_context_xml(
            "c2",
            instant="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "ConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "c2")
        assert ctx.is_consolidated is True

    def test_is_consolidated_false_with_non_consolidated(self) -> None:
        """NonConsolidatedMember は非連結なので is_consolidated=False。"""
        xml = _make_context_xml(
            "c3",
            start_date="2024-04-01",
            end_date="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "NonConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "c3")
        assert ctx.is_consolidated is False

    def test_is_non_consolidated(self) -> None:
        """NonConsolidatedMember 明示時のみ is_non_consolidated=True。"""
        xml = _make_context_xml(
            "nc1",
            instant="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "NonConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "nc1")
        assert ctx.is_non_consolidated is True

    def test_is_non_consolidated_false_no_dimensions(self) -> None:
        """Dimension なしは is_non_consolidated=False。"""
        xml = _make_context_xml("nc2", instant="2025-03-31")
        ctx = _parse_one(xml, "nc2")
        assert ctx.is_non_consolidated is False

    def test_is_instant(self) -> None:
        """InstantPeriod の場合 is_instant=True。"""
        xml = _make_context_xml("i1", instant="2025-03-31")
        ctx = _parse_one(xml, "i1")
        assert ctx.is_instant is True
        assert ctx.is_duration is False

    def test_is_duration(self) -> None:
        """DurationPeriod の場合 is_duration=True。"""
        xml = _make_context_xml("d1", start_date="2024-04-01", end_date="2025-03-31")
        ctx = _parse_one(xml, "d1")
        assert ctx.is_duration is True
        assert ctx.is_instant is False

    def test_has_dimensions(self) -> None:
        """Dimension ありの場合 has_dimensions=True。"""
        xml = _make_context_xml(
            "hd1",
            instant="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "ConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "hd1")
        assert ctx.has_dimensions is True

    def test_has_dimensions_false(self) -> None:
        """Dimension なしの場合 has_dimensions=False。"""
        xml = _make_context_xml("hd2", instant="2025-03-31")
        ctx = _parse_one(xml, "hd2")
        assert ctx.has_dimensions is False

    def test_dimension_dict(self) -> None:
        """dimension_dict が軸→メンバーの辞書を返す。"""
        xml = _make_context_xml(
            "dd1",
            instant="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "NonConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "dd1")
        d = ctx.dimension_dict
        assert d[_CONSOLIDATED_AXIS_CLARK] == _NON_CONSOLIDATED_MEMBER_CLARK

    def test_has_extra_dimensions_false_consolidated_only(self) -> None:
        """連結軸のみの場合 has_extra_dimensions=False。"""
        xml = _make_context_xml(
            "ed1",
            instant="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "ConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "ed1")
        assert ctx.has_extra_dimensions is False

    def test_is_consolidated_with_segment_dimension_only(self) -> None:
        """セグメント軸のみ（連結軸なし）の場合 is_consolidated=True。

        Note:
            ``statements.py`` の ``_is_consolidated()`` では False になるケース。
            XBRL Dimensions 仕様では連結軸未指定 = デフォルト（連結）。
        """
        xml = _make_context_xml(
            "seg_only",
            start_date="2024-04-01",
            end_date="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "BusinessSegmentsAxis", "ReportableSegmentsMember"),
            ],
        )
        ctx = _parse_one(xml, "seg_only")
        assert ctx.is_consolidated is True
        assert ctx.is_non_consolidated is False
        assert ctx.has_extra_dimensions is True

    def test_is_consolidated_with_consolidated_and_segment(self) -> None:
        """ConsolidatedMember + セグメント軸の場合 is_consolidated=True かつ has_extra_dimensions=True。

        Note:
            ``statements.py`` の ``_is_consolidated()`` では False になるケース。
        """
        xml = _make_context_xml(
            "con_seg",
            start_date="2024-04-01",
            end_date="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "ConsolidatedMember"),
                (_JPPFS_NS, "BusinessSegmentsAxis", "ReportableSegmentsMember"),
            ],
        )
        ctx = _parse_one(xml, "con_seg")
        assert ctx.is_consolidated is True
        assert ctx.is_non_consolidated is False
        assert ctx.has_extra_dimensions is True

    def test_has_extra_dimensions_true(self) -> None:
        """連結軸以外の Dimension がある場合 has_extra_dimensions=True。"""
        result = structure_contexts(
            [_make_raw_context("ctx_multi", MULTI_DIMENSION_XML)],
        )
        ctx = result["ctx_multi"]
        assert ctx.has_extra_dimensions is True


@pytest.mark.small
@pytest.mark.unit
class TestStructuredContextPropertiesP1:
    """P1: StructuredContext プロパティの推奨テスト群。"""

    def test_has_dimension(self) -> None:
        """has_dimension で軸の存在判定ができる。"""
        xml = _make_context_xml(
            "hdim1",
            instant="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "ConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "hdim1")
        assert ctx.has_dimension(_CONSOLIDATED_AXIS_CLARK) is True
        assert ctx.has_dimension(f"{{{_JPPFS_NS}}}BusinessSegmentsAxis") is False

    def test_get_dimension_member(self) -> None:
        """get_dimension_member で軸に対応するメンバーを取得できる。"""
        xml = _make_context_xml(
            "gm1",
            instant="2025-03-31",
            dimensions=[
                (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "NonConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "gm1")
        assert ctx.get_dimension_member(_CONSOLIDATED_AXIS_CLARK) == _NON_CONSOLIDATED_MEMBER_CLARK
        assert ctx.get_dimension_member(f"{{{_JPPFS_NS}}}Unknown") is None

    def test_has_extra_dimensions_false_no_dimensions(self) -> None:
        """Dimension なしの場合 has_extra_dimensions=False。"""
        xml = _make_context_xml("ed0", instant="2025-03-31")
        ctx = _parse_one(xml, "ed0")
        assert ctx.has_extra_dimensions is False

    def test_dimension_dict_empty(self) -> None:
        """Dimension なしの場合 dimension_dict は空辞書。"""
        xml = _make_context_xml("dd0", instant="2025-03-31")
        ctx = _parse_one(xml, "dd0")
        assert ctx.dimension_dict == {}

    def test_is_consolidated_with_non_jppfs_consolidated_axis(self) -> None:
        """提出者別タクソノミの ConsolidatedOrNonConsolidatedAxis でも連結判定できる。"""
        other_ns = "http://example.com/taxonomy"
        xml = _make_context_xml(
            "oc1",
            instant="2025-03-31",
            dimensions=[
                (other_ns, "ConsolidatedOrNonConsolidatedAxis", "ConsolidatedMember"),
            ],
        )
        ctx = _parse_one(xml, "oc1")
        assert ctx.is_consolidated is True
        assert ctx.is_non_consolidated is False


# ===========================================================================
# Phase 3: ContextCollection 基本アクセステスト（5 件）
# ===========================================================================


def _build_collection() -> ContextCollection:
    """テスト用の ContextCollection を構築する。"""
    contexts: dict[str, StructuredContext] = {}
    # 連結・duration（当期）
    xml = _make_context_xml("dur_con", start_date="2024-04-01", end_date="2025-03-31")
    contexts.update(structure_contexts([_make_raw_context("dur_con", xml)]))
    # 連結・instant（当期末）
    xml = _make_context_xml("inst_con", instant="2025-03-31")
    contexts.update(structure_contexts([_make_raw_context("inst_con", xml)]))
    # 非連結・duration（当期）
    xml = _make_context_xml(
        "dur_nc",
        start_date="2024-04-01",
        end_date="2025-03-31",
        dimensions=[
            (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "NonConsolidatedMember"),
        ],
    )
    contexts.update(structure_contexts([_make_raw_context("dur_nc", xml)]))
    # 連結・duration（前期）
    xml = _make_context_xml("dur_prior", start_date="2023-04-01", end_date="2024-03-31")
    contexts.update(structure_contexts([_make_raw_context("dur_prior", xml)]))
    # 連結・instant（前期末）
    xml = _make_context_xml("inst_prior", instant="2024-03-31")
    contexts.update(structure_contexts([_make_raw_context("inst_prior", xml)]))
    return ContextCollection(contexts)


@pytest.mark.small
@pytest.mark.unit
class TestContextCollectionBasic:
    """ContextCollection の基本アクセステスト。"""

    def test_len(self) -> None:
        """len が格納 Context 数を返す。"""
        col = _build_collection()
        assert len(col) == 5

    def test_iter(self) -> None:
        """イテレーションで StructuredContext を返す。"""
        col = _build_collection()
        items = list(col)
        assert len(items) == 5
        assert all(isinstance(item, StructuredContext) for item in items)

    def test_getitem_and_contains(self) -> None:
        """[] アクセスと in 演算が動作する。"""
        col = _build_collection()
        assert "dur_con" in col
        assert col["dur_con"].context_id == "dur_con"
        assert "nonexistent" not in col

    def test_getitem_raises_keyerror(self) -> None:
        """存在しない context_id で KeyError が送出される。"""
        col = _build_collection()
        with pytest.raises(KeyError):
            col["nonexistent"]

    def test_get_and_as_dict(self) -> None:
        """get メソッドと as_dict が動作する。"""
        col = _build_collection()
        assert col.get("dur_con") is not None
        assert col.get("nonexistent") is None
        d = col.as_dict
        assert isinstance(d, dict)
        assert len(d) == 5

    def test_repr(self) -> None:
        """__repr__ が正しいフォーマット。"""
        col = _build_collection()
        r = repr(col)
        assert "ContextCollection(" in r
        assert "total=5" in r
        assert "instant=2" in r
        assert "duration=3" in r


# ===========================================================================
# Phase 4: ContextCollection フィルタメソッドテスト（10 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestContextCollectionFilterP0:
    """P0: フィルタメソッドの必須テスト群。"""

    def test_filter_consolidated(self) -> None:
        """filter_consolidated が連結 Context のみを返す。"""
        col = _build_collection()
        result = col.filter_consolidated()
        assert len(result) == 4
        assert all(ctx.is_consolidated for ctx in result)

    def test_filter_non_consolidated(self) -> None:
        """filter_non_consolidated が非連結 Context のみを返す。"""
        col = _build_collection()
        result = col.filter_non_consolidated()
        assert len(result) == 1
        assert "dur_nc" in result

    def test_filter_instant(self) -> None:
        """filter_instant が InstantPeriod のみを返す。"""
        col = _build_collection()
        result = col.filter_instant()
        assert len(result) == 2
        assert all(ctx.is_instant for ctx in result)

    def test_filter_duration(self) -> None:
        """filter_duration が DurationPeriod のみを返す。"""
        col = _build_collection()
        result = col.filter_duration()
        assert len(result) == 3
        assert all(ctx.is_duration for ctx in result)

    def test_filter_no_extra_dimensions(self) -> None:
        """filter_no_extra_dimensions が連結軸以外の Dimension を持たない Context を返す。"""
        col = _build_collection()
        result = col.filter_no_extra_dimensions()
        assert len(result) == 5  # 全て連結軸のみ or Dimension なし

    def test_filter_no_dimensions(self) -> None:
        """filter_no_dimensions が Dimension なしの Context を返す。"""
        col = _build_collection()
        result = col.filter_no_dimensions()
        assert len(result) == 4  # dur_nc のみ除外

    def test_filter_by_period(self) -> None:
        """filter_by_period が指定期間の Context を返す。"""
        col = _build_collection()
        period = DurationPeriod(
            start_date=datetime.date(2024, 4, 1),
            end_date=datetime.date(2025, 3, 31),
        )
        result = col.filter_by_period(period)
        assert len(result) == 2  # dur_con + dur_nc


@pytest.mark.small
@pytest.mark.unit
class TestContextCollectionFilterP1:
    """P1: フィルタメソッドの推奨テスト群。"""

    def test_filter_by_dimension_axis_only(self) -> None:
        """filter_by_dimension で軸のみ指定のフィルタ。"""
        col = _build_collection()
        result = col.filter_by_dimension(_CONSOLIDATED_AXIS_CLARK)
        assert len(result) == 1  # dur_nc のみ連結軸を明示
        assert "dur_nc" in result

    def test_filter_by_dimension_axis_and_member(self) -> None:
        """filter_by_dimension で軸+メンバー指定のフィルタ。"""
        col = _build_collection()
        result = col.filter_by_dimension(
            _CONSOLIDATED_AXIS_CLARK,
            _NON_CONSOLIDATED_MEMBER_CLARK,
        )
        assert len(result) == 1
        assert "dur_nc" in result

    def test_filter_chaining(self) -> None:
        """フィルタのチェーンが正しく動作する。"""
        col = _build_collection()
        result = col.filter_consolidated().filter_duration()
        assert len(result) == 2  # dur_con + dur_prior

    def test_empty_collection(self) -> None:
        """空の ContextCollection のフィルタが空を返す。"""
        col = ContextCollection({})
        assert len(col) == 0
        assert len(col.filter_consolidated()) == 0
        assert len(col.filter_instant()) == 0

    def test_immutability(self) -> None:
        """フィルタが元コレクションを変更しない。"""
        col = _build_collection()
        original_len = len(col)
        _ = col.filter_consolidated()
        _ = col.filter_instant()
        assert len(col) == original_len


# ===========================================================================
# Phase 5: 期間クエリテスト（7 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestContextCollectionPeriodQueryP0:
    """P0: 期間クエリの必須テスト群。"""

    def test_latest_instant_period(self) -> None:
        """latest_instant_period が最新の InstantPeriod を返す。"""
        col = _build_collection()
        period = col.latest_instant_period
        assert period is not None
        assert period.instant == datetime.date(2025, 3, 31)

    def test_latest_duration_period(self) -> None:
        """latest_duration_period が end_date 最新の DurationPeriod を返す。"""
        col = _build_collection()
        period = col.latest_duration_period
        assert period is not None
        assert period.end_date == datetime.date(2025, 3, 31)
        assert period.start_date == datetime.date(2024, 4, 1)

    def test_latest_duration_period_tiebreak(self) -> None:
        """同一 end_date の場合、最長期間（start_date が早い方）が選ばれる。"""
        contexts: dict[str, StructuredContext] = {}
        # 半期: 2024-10-01 〜 2025-03-31
        xml = _make_context_xml("half", start_date="2024-10-01", end_date="2025-03-31")
        contexts.update(structure_contexts([_make_raw_context("half", xml)]))
        # 通期: 2024-04-01 〜 2025-03-31
        xml = _make_context_xml("full", start_date="2024-04-01", end_date="2025-03-31")
        contexts.update(structure_contexts([_make_raw_context("full", xml)]))
        col = ContextCollection(contexts)
        period = col.latest_duration_period
        assert period is not None
        assert period.start_date == datetime.date(2024, 4, 1)  # 最長期間


@pytest.mark.small
@pytest.mark.unit
class TestContextCollectionPeriodQueryP1:
    """P1: 期間クエリの推奨テスト群。"""

    def test_unique_instant_periods(self) -> None:
        """unique_instant_periods が instant 降順のタプルを返す。"""
        col = _build_collection()
        periods = col.unique_instant_periods
        assert len(periods) == 2
        assert periods[0].instant == datetime.date(2025, 3, 31)
        assert periods[1].instant == datetime.date(2024, 3, 31)

    def test_unique_duration_periods(self) -> None:
        """unique_duration_periods が end_date 降順のタプルを返す。"""
        col = _build_collection()
        periods = col.unique_duration_periods
        assert len(periods) == 2
        assert periods[0].end_date == datetime.date(2025, 3, 31)
        assert periods[1].end_date == datetime.date(2024, 3, 31)

    def test_latest_instant_contexts(self) -> None:
        """latest_instant_contexts が最新期間の Context を返す。"""
        col = _build_collection()
        result = col.latest_instant_contexts()
        assert len(result) == 1
        assert "inst_con" in result

    def test_latest_duration_contexts(self) -> None:
        """latest_duration_contexts が最新期間の Context を返す。"""
        col = _build_collection()
        result = col.latest_duration_contexts()
        assert len(result) == 2  # dur_con + dur_nc（同期間）

    def test_empty_latest_period(self) -> None:
        """instant なしの場合 latest_instant_period は None。"""
        xml = _make_context_xml("d_only", start_date="2024-04-01", end_date="2025-03-31")
        contexts = structure_contexts([_make_raw_context("d_only", xml)])
        col = ContextCollection(contexts)
        assert col.latest_instant_period is None
        assert len(col.latest_instant_contexts()) == 0
        assert col.latest_duration_period is not None


# ===========================================================================
# Phase 6: 結合テスト（3 件）
# ===========================================================================


@pytest.mark.medium
@pytest.mark.integration
class TestContextCollectionIntegration:
    """ContextCollection の結合テスト。"""

    def test_collection_from_simple_pl_fixture(self) -> None:
        """parse_xbrl_facts → structure_contexts → ContextCollection パイプライン。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(data)
        contexts = structure_contexts(parsed.contexts)
        col = ContextCollection(contexts)

        assert len(col) == 4
        assert len(col.filter_consolidated()) == 3
        assert len(col.filter_non_consolidated()) == 1
        assert col.latest_duration_period is not None
        assert col.latest_duration_period.end_date == datetime.date(2025, 3, 31)
        assert col.latest_instant_period is not None
        assert col.latest_instant_period.instant == datetime.date(2025, 3, 31)

    def test_latest_period_with_multiple_periods(self) -> None:
        """当期+前期混在時に最新期間が正しく選択される。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(data)
        contexts = structure_contexts(parsed.contexts)
        col = ContextCollection(contexts)

        # 当期 (2024-04-01 ~ 2025-03-31) が最新
        latest = col.latest_duration_period
        assert latest is not None
        assert latest.start_date == datetime.date(2024, 4, 1)
        assert latest.end_date == datetime.date(2025, 3, 31)

        # 前期 (2023-04-01 ~ 2024-03-31) は2番目
        periods = col.unique_duration_periods
        assert len(periods) == 2
        assert periods[1].end_date == datetime.date(2024, 3, 31)

    def test_filter_consolidated_then_no_dimensions(self) -> None:
        """filter_consolidated().filter_no_dimensions() のチェーン検証。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(data)
        contexts = structure_contexts(parsed.contexts)
        col = ContextCollection(contexts)

        # 連結 → Dimension なし
        result = col.filter_consolidated().filter_no_dimensions()
        # simple_pl.xbrl: CurrentYearDuration, CurrentYearInstant, Prior1YearDuration
        # は全て連結 & Dimension なし
        assert len(result) == 3
        for ctx in result:
            assert ctx.is_consolidated
            assert not ctx.has_dimensions

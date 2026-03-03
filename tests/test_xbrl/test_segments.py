"""Wave 7 Lane 6: セグメント抽出モジュールのテスト。

``extract_segments()`` / ``list_dimension_axes()`` と
関連 dataclass・ヘルパーのテスト。

テストデータはヘルパー関数で構築する（XML フィクスチャ不使用）。
TaxonomyResolver は境界依存のため軽量スタブを使用する（デトロイト派）。
"""

from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from edinet.models.financial import LineItem
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
)
from edinet.xbrl.linkbase.definition import (
    AxisInfo,
    DefinitionTree,
    HypercubeInfo,
    MemberNode,
)
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

from edinet.financial.dimensions.segments import (
    SegmentData,
    _build_member_index,
    _extract_local_name_from_clark,
    _extract_namespace_from_clark,
    _find_axis_info,
    _resolve_member_label,
    extract_segments,
    list_dimension_axes,
)

# ---------------------------------------------------------------------------
# 名前空間定数
# ---------------------------------------------------------------------------

_JPCRP_NS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)
_JPPFS_NS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)
_FILER_NS = (
    "http://disclosure.edinet-fsa.go.jp/"
    "jpcrp030000/asr/001/E05452-000/2025-03-31/01/2025-06-18"
)
_OPERATING_SEGMENTS_AXIS = f"{{{_JPCRP_NS}}}OperatingSegmentsAxis"
_CUSTOM_AXIS = f"{{{_JPCRP_NS}}}DirectorsAndOtherOfficersAxis"
_CONSOLIDATED_AXIS = (
    f"{{{_JPPFS_NS}}}ConsolidatedOrNonConsolidatedAxis"
)
_CONSOLIDATED_MEMBER = f"{{{_JPPFS_NS}}}ConsolidatedMember"
_NON_CONSOLIDATED_MEMBER = f"{{{_JPPFS_NS}}}NonConsolidatedMember"

_DEFAULT_PERIOD = DurationPeriod(
    start_date=datetime.date(2024, 4, 1),
    end_date=datetime.date(2025, 3, 31),
)
_PRIOR_PERIOD = DurationPeriod(
    start_date=datetime.date(2023, 4, 1),
    end_date=datetime.date(2024, 3, 31),
)
# 標準メンバー
_REPORTABLE_MEMBER = f"{{{_JPCRP_NS}}}ReportableSegmentsMember"
_RECONCILIATION_MEMBER = f"{{{_JPCRP_NS}}}ReconciliationMember"

# 提出者メンバー
_SEG_A_MEMBER = f"{{{_FILER_NS}}}SegmentAReportableSegmentMember"
_SEG_B_MEMBER = f"{{{_FILER_NS}}}SegmentBReportableSegmentMember"


# ---------------------------------------------------------------------------
# テスト用スタブ / ヘルパー
# ---------------------------------------------------------------------------


class _StubResolver:
    """テスト用の TaxonomyResolver スタブ。

    ``resolve_clark()`` のみ実装する軽量テストダブル。
    """

    def __init__(
        self, labels: dict[str, dict[str, str]] | None = None
    ) -> None:
        self._labels = labels or {}

    def resolve_clark(
        self,
        concept_qname: str,
        *,
        role: str = "",
        lang: str = "ja",
    ) -> LabelInfo:
        """スタブのラベル解決。"""
        if (
            concept_qname in self._labels
            and lang in self._labels[concept_qname]
        ):
            return LabelInfo(
                text=self._labels[concept_qname][lang],
                role=role,
                lang=lang,
                source=LabelSource.STANDARD,
            )
        local = (
            concept_qname.rsplit("}", 1)[-1]
            if "}" in concept_qname
            else concept_qname
        )
        return LabelInfo(
            text=local, role=role, lang=lang, source=LabelSource.FALLBACK
        )


def _make_context(
    context_id: str,
    *,
    consolidated: bool = True,
    segment_member_clark: str | None = None,
    axis_clark: str = _OPERATING_SEGMENTS_AXIS,
    period: DurationPeriod | InstantPeriod | None = None,
) -> StructuredContext:
    """テスト用 StructuredContext を生成する。"""
    dims: list[DimensionMember] = []
    consol_member = (
        _CONSOLIDATED_MEMBER if consolidated else _NON_CONSOLIDATED_MEMBER
    )
    dims.append(
        DimensionMember(axis=_CONSOLIDATED_AXIS, member=consol_member)
    )
    if segment_member_clark is not None:
        dims.append(
            DimensionMember(axis=axis_clark, member=segment_member_clark)
        )

    if period is None:
        period = _DEFAULT_PERIOD

    return StructuredContext(
        context_id=context_id,
        period=period,
        entity_id="E05452",
        dimensions=tuple(dims),
        source_line=None,
    )


def _make_line_item(
    concept: str,
    context_id: str,
    value: Decimal | str | None = Decimal("1000"),
    *,
    namespace_uri: str = _JPPFS_NS,
    dimensions: tuple[DimensionMember, ...] = (),
    period: DurationPeriod | InstantPeriod | None = None,
    order: int = 0,
    label_ja_text: str | None = None,
    label_en_text: str | None = None,
) -> LineItem:
    """テスト用 LineItem を生成する。"""
    if period is None:
        period = _DEFAULT_PERIOD
    ja_text = label_ja_text if label_ja_text is not None else concept
    en_text = label_en_text if label_en_text is not None else concept
    return LineItem(
        concept=f"{{{namespace_uri}}}{concept}",
        namespace_uri=namespace_uri,
        local_name=concept,
        label_ja=LabelInfo(
            text=ja_text, role="", lang="ja", source=LabelSource.FALLBACK
        ),
        label_en=LabelInfo(
            text=en_text, role="", lang="en", source=LabelSource.FALLBACK
        ),
        value=value,
        unit_ref="JPY" if isinstance(value, Decimal) else None,
        decimals=-6 if isinstance(value, Decimal) else None,
        context_id=context_id,
        period=period,
        entity_id="E05452",
        dimensions=dimensions,
        is_nil=value is None,
        source_line=None,
        order=order,
    )


def _make_items_and_ctx_map(
    *,
    seg_a_member: str = _SEG_A_MEMBER,
    seg_b_member: str = _SEG_B_MEMBER,
    consolidated: bool = True,
    period: DurationPeriod | InstantPeriod | None = None,
    axis_clark: str = _OPERATING_SEGMENTS_AXIS,
) -> tuple[list[LineItem], dict[str, StructuredContext]]:
    """2 セグメント（A, B）の標準テストデータを構築する。"""
    ctx_a = _make_context(
        "ctx_seg_a",
        consolidated=consolidated,
        segment_member_clark=seg_a_member,
        axis_clark=axis_clark,
        period=period,
    )
    ctx_b = _make_context(
        "ctx_seg_b",
        consolidated=consolidated,
        segment_member_clark=seg_b_member,
        axis_clark=axis_clark,
        period=period,
    )
    ctx_map = {ctx_a.context_id: ctx_a, ctx_b.context_id: ctx_b}

    items = [
        _make_line_item(
            "NetSales",
            "ctx_seg_a",
            Decimal("5000"),
            dimensions=ctx_a.dimensions,
            period=period,
            order=1,
        ),
        _make_line_item(
            "OperatingIncome",
            "ctx_seg_a",
            Decimal("800"),
            dimensions=ctx_a.dimensions,
            period=period,
            order=2,
        ),
        _make_line_item(
            "NetSales",
            "ctx_seg_b",
            Decimal("3000"),
            dimensions=ctx_b.dimensions,
            period=period,
            order=3,
        ),
    ]
    return items, ctx_map


def _make_definition_trees(
    axis_name: str = "OperatingSegmentsAxis",
    *,
    members: list[tuple[str, list[tuple[str, list]]]] | None = None,
    default_member: str | None = "EntityTotalMember",
) -> dict[str, DefinitionTree]:
    """テスト用 DefinitionTree を構築する。

    Args:
        axis_name: 軸のローカル名。
        members: メンバー階層。
            ``[("DomainMember", [("ChildA", []), ("ChildB", [])])]``
        default_member: デフォルトメンバーのローカル名。
    """
    if members is None:
        members = [
            (
                "EntityTotalMember",
                [
                    ("ReportableSegmentsMember", [
                        ("SegmentAReportableSegmentMember", []),
                        ("SegmentBReportableSegmentMember", []),
                    ]),
                    ("ReconciliationMember", []),
                ],
            )
        ]

    def _build_tree(
        specs: list[tuple[str, list]],
    ) -> tuple[MemberNode, ...]:
        nodes = []
        for concept, children_specs in specs:
            children = _build_tree(children_specs)
            nodes.append(
                MemberNode(
                    concept=concept,
                    href=f"dummy.xsd#{concept}",
                    usable=True,
                    children=children,
                )
            )
        return tuple(nodes)

    # ドメインルート
    root_spec = members[0] if members else ("EntityTotalMember", [])
    root_children = _build_tree(root_spec[1])
    domain_root = MemberNode(
        concept=root_spec[0],
        href=f"dummy.xsd#{root_spec[0]}",
        usable=True,
        children=root_children,
    )

    axis = AxisInfo(
        axis_concept=axis_name,
        order=0.0,
        domain=domain_root,
        default_member=default_member,
    )
    hc = HypercubeInfo(
        table_concept="SegmentInfoTable",
        heading_concept="SegmentInfoHeading",
        axes=(axis,),
        closed=True,
        context_element="scenario",
        line_items_concept=None,
    )
    tree = DefinitionTree(
        role_uri="http://example.com/role/SegmentInfo",
        arcs=(),
        hypercubes=(hc,),
    )
    return {tree.role_uri: tree}


# ---------------------------------------------------------------------------
# TestListDimensionAxes
# ---------------------------------------------------------------------------


class TestListDimensionAxes:
    """list_dimension_axes() のテスト。"""

    def test_single_axis(self) -> None:
        """1 軸のみの LineItem 群で DimensionAxisSummary が 1 件返る。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver({
            _OPERATING_SEGMENTS_AXIS: {
                "ja": "事業セグメント",
                "en": "Operating segments",
            },
        })
        result = list_dimension_axes(items, ctx_map, resolver)
        # 連結軸 + セグメント軸の 2 軸
        axis_names = {ax.local_name for ax in result}
        assert "OperatingSegmentsAxis" in axis_names

    def test_multiple_axes(self) -> None:
        """複数軸が存在する場合、全軸が返る。"""
        ctx = _make_context(
            "ctx1",
            segment_member_clark=_SEG_A_MEMBER,
        )
        # 追加の軸を持つ LineItem
        extra_dim = DimensionMember(
            axis=_CUSTOM_AXIS, member=f"{{{_JPCRP_NS}}}SomeMember"
        )
        dims = ctx.dimensions + (extra_dim,)
        item = _make_line_item(
            "NetSales", "ctx1", dimensions=dims, order=1
        )
        ctx_map = {"ctx1": ctx}
        resolver = _StubResolver()
        result = list_dimension_axes([item], ctx_map, resolver)
        local_names = {ax.local_name for ax in result}
        assert "OperatingSegmentsAxis" in local_names
        assert "DirectorsAndOtherOfficersAxis" in local_names
        assert "ConsolidatedOrNonConsolidatedAxis" in local_names

    def test_label_resolved(self) -> None:
        """TaxonomyResolver で軸の日本語/英語ラベルが解決される。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver({
            _OPERATING_SEGMENTS_AXIS: {
                "ja": "事業セグメント",
                "en": "Operating segments",
            },
        })
        result = list_dimension_axes(items, ctx_map, resolver)
        seg_axis = next(
            ax for ax in result
            if ax.local_name == "OperatingSegmentsAxis"
        )
        assert seg_axis.label_ja == "事業セグメント"
        assert seg_axis.label_en == "Operating segments"

    def test_label_fallback_to_local_name(self) -> None:
        """ラベル未解決時はローカル名がフォールバック。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver()  # ラベルなし
        result = list_dimension_axes(items, ctx_map, resolver)
        seg_axis = next(
            ax for ax in result
            if ax.local_name == "OperatingSegmentsAxis"
        )
        assert seg_axis.label_ja == "OperatingSegmentsAxis"

    def test_is_standard_true(self) -> None:
        """標準タクソノミの軸で is_standard=True。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver()
        result = list_dimension_axes(items, ctx_map, resolver)
        seg_axis = next(
            ax for ax in result
            if ax.local_name == "OperatingSegmentsAxis"
        )
        assert seg_axis.is_standard is True

    def test_is_standard_false(self) -> None:
        """提出者タクソノミの軸で is_standard=False。"""
        filer_axis = f"{{{_FILER_NS}}}CustomAxis"
        ctx = _make_context(
            "ctx1",
            segment_member_clark=f"{{{_FILER_NS}}}CustomMember",
            axis_clark=filer_axis,
        )
        item = _make_line_item(
            "NetSales", "ctx1", dimensions=ctx.dimensions, order=1
        )
        resolver = _StubResolver()
        result = list_dimension_axes(
            [item], {"ctx1": ctx}, resolver
        )
        filer = next(
            ax for ax in result if ax.local_name == "CustomAxis"
        )
        assert filer.is_standard is False

    def test_member_count(self) -> None:
        """member_count がユニークメンバー数を正しく反映する。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver()
        result = list_dimension_axes(items, ctx_map, resolver)
        seg_axis = next(
            ax for ax in result
            if ax.local_name == "OperatingSegmentsAxis"
        )
        # _SEG_A_MEMBER と _SEG_B_MEMBER の 2 メンバー
        assert seg_axis.member_count == 2

    def test_item_count(self) -> None:
        """item_count がその軸を持つ LineItem 数を正しく反映する。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver()
        result = list_dimension_axes(items, ctx_map, resolver)
        seg_axis = next(
            ax for ax in result
            if ax.local_name == "OperatingSegmentsAxis"
        )
        # 3 アイテム（SegA: NetSales + OperatingIncome, SegB: NetSales）
        assert seg_axis.item_count == 3

    def test_ordered_by_item_count_desc(self) -> None:
        """結果が item_count 降順でソートされる。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver()
        result = list_dimension_axes(items, ctx_map, resolver)
        counts = [ax.item_count for ax in result]
        assert counts == sorted(counts, reverse=True)

    def test_no_dimensions(self) -> None:
        """ディメンションなしの LineItem のみで空タプルが返る。"""
        ctx = StructuredContext(
            context_id="ctx_plain",
            period=_DEFAULT_PERIOD,
            entity_id="E05452",
            dimensions=(),
            source_line=None,
        )
        item = _make_line_item("NetSales", "ctx_plain", order=1)
        resolver = _StubResolver()
        result = list_dimension_axes(
            [item], {"ctx_plain": ctx}, resolver
        )
        assert result == ()

    def test_consolidated_filter(self) -> None:
        """consolidated=True で連結コンテキストの軸のみ返る。"""
        ctx_consol = _make_context(
            "ctx_c",
            consolidated=True,
            segment_member_clark=_SEG_A_MEMBER,
        )
        ctx_noncon = _make_context(
            "ctx_n",
            consolidated=False,
            segment_member_clark=_SEG_B_MEMBER,
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_c",
                dimensions=ctx_consol.dimensions,
                order=1,
            ),
            _make_line_item(
                "NetSales",
                "ctx_n",
                dimensions=ctx_noncon.dimensions,
                order=2,
            ),
        ]
        ctx_map = {"ctx_c": ctx_consol, "ctx_n": ctx_noncon}
        resolver = _StubResolver()

        # consolidated=True → 連結のみ
        result_c = list_dimension_axes(
            items, ctx_map, resolver, consolidated=True
        )
        seg_axis_c = next(
            (ax for ax in result_c
             if ax.local_name == "OperatingSegmentsAxis"),
            None,
        )
        assert seg_axis_c is not None
        assert seg_axis_c.member_count == 1  # _SEG_A_MEMBER のみ

        # consolidated=False → 個別のみ
        result_n = list_dimension_axes(
            items, ctx_map, resolver, consolidated=False
        )
        seg_axis_n = next(
            (ax for ax in result_n
             if ax.local_name == "OperatingSegmentsAxis"),
            None,
        )
        assert seg_axis_n is not None
        assert seg_axis_n.member_count == 1  # _SEG_B_MEMBER のみ


# ---------------------------------------------------------------------------
# TestExtractSegments
# ---------------------------------------------------------------------------


class TestExtractSegments:
    """extract_segments() のテスト。"""

    def test_single_segment(self) -> None:
        """1 セグメントの LineItem が正しく抽出される。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                Decimal("5000"),
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver({
            _SEG_A_MEMBER: {"ja": "セグメントA"},
        })
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert len(result) == 1
        assert result[0].name == "セグメントA"
        assert len(result[0].items) == 1

    def test_multiple_segments(self) -> None:
        """複数セグメントが正しくグルーピングされる。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver({
            _SEG_A_MEMBER: {"ja": "セグメントA"},
            _SEG_B_MEMBER: {"ja": "セグメントB"},
        })
        result = extract_segments(items, ctx_map, resolver)
        assert len(result) == 2
        names = {seg.name for seg in result}
        assert names == {"セグメントA", "セグメントB"}

    def test_segment_name_from_resolver(self) -> None:
        """TaxonomyResolver でメンバーの日本語ラベルが解決される。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver({
            _SEG_A_MEMBER: {"ja": "省エネルギー関連事業"},
        })
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert result[0].name == "省エネルギー関連事業"

    def test_segment_name_fallback_to_local(self) -> None:
        """ラベルが見つからない場合はローカル名がセグメント名になる。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()  # ラベルなし
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        # "SegmentAReportableSegmentMember" → "SegmentAReportableSegment"
        assert result[0].name == "SegmentAReportableSegment"

    def test_is_standard_member_true(self) -> None:
        """標準メンバー（jpcrp_cor）で is_standard_member=True。"""
        ctx = _make_context(
            "ctx_r", segment_member_clark=_REPORTABLE_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_r",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver({
            _REPORTABLE_MEMBER: {"ja": "報告セグメント"},
        })
        result = extract_segments(
            items, {"ctx_r": ctx}, resolver
        )
        assert result[0].is_standard_member is True

    def test_is_standard_member_false(self) -> None:
        """提出者メンバーで is_standard_member=False。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert result[0].is_standard_member is False

    def test_consolidated_filter(self) -> None:
        """consolidated=True で連結コンテキストのみ抽出される。"""
        ctx_c = _make_context(
            "ctx_c",
            consolidated=True,
            segment_member_clark=_SEG_A_MEMBER,
        )
        ctx_n = _make_context(
            "ctx_n",
            consolidated=False,
            segment_member_clark=_SEG_B_MEMBER,
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_c",
                Decimal("5000"),
                dimensions=ctx_c.dimensions,
            ),
            _make_line_item(
                "NetSales",
                "ctx_n",
                Decimal("3000"),
                dimensions=ctx_n.dimensions,
            ),
        ]
        ctx_map = {"ctx_c": ctx_c, "ctx_n": ctx_n}
        resolver = _StubResolver()
        result = extract_segments(
            items, ctx_map, resolver, consolidated=True
        )
        assert len(result) == 1
        assert result[0].member_concept == "SegmentAReportableSegmentMember"

    def test_non_consolidated_filter(self) -> None:
        """consolidated=False で個別コンテキストのみ抽出される。"""
        ctx_c = _make_context(
            "ctx_c",
            consolidated=True,
            segment_member_clark=_SEG_A_MEMBER,
        )
        ctx_n = _make_context(
            "ctx_n",
            consolidated=False,
            segment_member_clark=_SEG_B_MEMBER,
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_c",
                dimensions=ctx_c.dimensions,
            ),
            _make_line_item(
                "NetSales",
                "ctx_n",
                dimensions=ctx_n.dimensions,
            ),
        ]
        ctx_map = {"ctx_c": ctx_c, "ctx_n": ctx_n}
        resolver = _StubResolver()
        result = extract_segments(
            items, ctx_map, resolver, consolidated=False
        )
        assert len(result) == 1
        assert result[0].member_concept == "SegmentBReportableSegmentMember"

    def test_period_filter(self) -> None:
        """period 指定で該当期間のみ抽出される。"""
        ctx_cur = _make_context(
            "ctx_cur",
            segment_member_clark=_SEG_A_MEMBER,
            period=_DEFAULT_PERIOD,
        )
        ctx_pri = _make_context(
            "ctx_pri",
            segment_member_clark=_SEG_A_MEMBER,
            period=_PRIOR_PERIOD,
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_cur",
                Decimal("5000"),
                dimensions=ctx_cur.dimensions,
                period=_DEFAULT_PERIOD,
            ),
            _make_line_item(
                "NetSales",
                "ctx_pri",
                Decimal("4000"),
                dimensions=ctx_pri.dimensions,
                period=_PRIOR_PERIOD,
            ),
        ]
        ctx_map = {"ctx_cur": ctx_cur, "ctx_pri": ctx_pri}
        resolver = _StubResolver()
        result = extract_segments(
            items, ctx_map, resolver, period=_DEFAULT_PERIOD
        )
        assert len(result) == 1
        assert result[0].items[0].value == Decimal("5000")

    def test_no_segments(self) -> None:
        """セグメント情報がない Filing で空タプルが返る。"""
        ctx = StructuredContext(
            context_id="ctx_plain",
            period=_DEFAULT_PERIOD,
            entity_id="E05452",
            dimensions=(),
            source_line=None,
        )
        item = _make_line_item("NetSales", "ctx_plain")
        resolver = _StubResolver()
        result = extract_segments(
            [item], {"ctx_plain": ctx}, resolver
        )
        assert result == ()

    def test_items_contain_values(self) -> None:
        """SegmentItem に正しい value が設定される。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                Decimal("12345"),
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert result[0].items[0].value == Decimal("12345")

    def test_items_contain_labels(self) -> None:
        """SegmentItem に label_ja, label_en が設定される。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
                label_ja_text="売上高",
                label_en_text="Net sales",
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        seg_item = result[0].items[0]
        assert seg_item.label_ja.text == "売上高"
        assert seg_item.label_en.text == "Net sales"

    def test_items_preserve_period(self) -> None:
        """SegmentItem に period が正しく設定される。"""
        ctx = _make_context(
            "ctx_a",
            segment_member_clark=_SEG_A_MEMBER,
            period=_DEFAULT_PERIOD,
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
                period=_DEFAULT_PERIOD,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert result[0].items[0].period == _DEFAULT_PERIOD

    def test_custom_axis(self) -> None:
        """axis_local_name を変更して別の軸でセグメント抽出できる。"""
        custom_member = f"{{{_JPCRP_NS}}}SomeDirectorMember"
        ctx = _make_context(
            "ctx_d",
            segment_member_clark=custom_member,
            axis_clark=_CUSTOM_AXIS,
        )
        items = [
            _make_line_item(
                "Compensation",
                "ctx_d",
                Decimal("500"),
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver({custom_member: {"ja": "取締役A"}})
        result = extract_segments(
            items,
            {"ctx_d": ctx},
            resolver,
            axis_local_name="DirectorsAndOtherOfficersAxis",
        )
        assert len(result) == 1
        assert result[0].name == "取締役A"
        assert result[0].axis_concept == "DirectorsAndOtherOfficersAxis"

    def test_reconciliation_member_included(self) -> None:
        """ReconciliationMember が SegmentData に含まれる。"""
        ctx = _make_context(
            "ctx_r", segment_member_clark=_RECONCILIATION_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_r",
                Decimal("-100"),
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver({
            _RECONCILIATION_MEMBER: {"ja": "調整額"},
        })
        result = extract_segments(
            items, {"ctx_r": ctx}, resolver
        )
        assert len(result) == 1
        assert result[0].name == "調整額"
        assert result[0].is_standard_member is True

    def test_multiple_items_per_segment(self) -> None:
        """1 セグメントに複数の科目が含まれる。"""
        items, ctx_map = _make_items_and_ctx_map()
        resolver = _StubResolver()
        result = extract_segments(items, ctx_map, resolver)
        # SegA には NetSales + OperatingIncome の 2 アイテム
        seg_a = next(
            s for s in result
            if s.member_concept == "SegmentAReportableSegmentMember"
        )
        assert len(seg_a.items) == 2

    def test_context_id_not_in_map_skipped(self) -> None:
        """context_map に存在しない context_id の LineItem はスキップ。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
            ),
            _make_line_item(
                "NetSales",
                "ctx_unknown",  # context_map にない
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert len(result) == 1
        assert len(result[0].items) == 1

    def test_result_ordered_by_document_appearance(self) -> None:
        """definition_trees なしでは元文書の出現順でソートされる。"""
        ctx_a = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        ctx_b = _make_context(
            "ctx_b", segment_member_clark=_SEG_B_MEMBER
        )
        # B が先に出現（order=1）、A が後に出現（order=10）
        items = [
            _make_line_item(
                "NetSales",
                "ctx_b",
                dimensions=ctx_b.dimensions,
                order=1,
            ),
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx_a.dimensions,
                order=10,
            ),
        ]
        ctx_map = {"ctx_a": ctx_a, "ctx_b": ctx_b}
        resolver = _StubResolver()
        result = extract_segments(items, ctx_map, resolver)
        # B（order=1）が先、A（order=10）が後
        assert result[0].member_concept == "SegmentBReportableSegmentMember"
        assert result[1].member_concept == "SegmentAReportableSegmentMember"

    def test_nil_value_in_segment_item(self) -> None:
        """is_nil=True / value=None の LineItem がセグメントに含まれる。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "Assets",
                "ctx_a",
                None,  # nil
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert len(result) == 1
        assert result[0].items[0].value is None

    def test_text_fact_in_segment(self) -> None:
        """value: str の LineItem がセグメントに含まれる。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "SegmentDescription",
                "ctx_a",
                "テキスト値",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert result[0].items[0].value == "テキスト値"


# ---------------------------------------------------------------------------
# TestDefinitionLinkbaseIntegration
# ---------------------------------------------------------------------------


class TestDefinitionLinkbaseIntegration:
    """DefinitionLinkbase 連携テスト（definition_trees 引数）。"""

    def test_depth_from_member_hierarchy(self) -> None:
        """definition_trees 提供時に depth がメンバー階層深度を反映する。"""
        def_trees = _make_definition_trees()
        ctx_a = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx_a.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items,
            {"ctx_a": ctx_a},
            resolver,
            definition_trees=def_trees,
        )
        # EntityTotalMember(0) → ReportableSegmentsMember(1)
        #   → SegmentAReportableSegmentMember(2)
        assert result[0].depth == 2

    def test_is_default_member_true(self) -> None:
        """AxisInfo.default_member と一致するメンバーで is_default_member=True。"""
        def_trees = _make_definition_trees()
        default_clark = f"{{{_JPCRP_NS}}}EntityTotalMember"
        ctx = _make_context(
            "ctx_d", segment_member_clark=default_clark
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_d",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items,
            {"ctx_d": ctx},
            resolver,
            definition_trees=def_trees,
        )
        assert result[0].is_default_member is True

    def test_is_default_member_false_without_definition(self) -> None:
        """definition_trees=None の場合は is_default_member=False。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver
        )
        assert result[0].is_default_member is False

    def test_ordering_by_taxonomy_definition(self) -> None:
        """definition_trees 提供時にタクソノミ定義順でソートされる。"""
        def_trees = _make_definition_trees()
        # SegA は SegB より先にタクソノミ定義で出現する
        ctx_a = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        ctx_b = _make_context(
            "ctx_b", segment_member_clark=_SEG_B_MEMBER
        )
        # 文書上は B が先（order=1）、A が後（order=10）
        items = [
            _make_line_item(
                "NetSales",
                "ctx_b",
                dimensions=ctx_b.dimensions,
                order=1,
            ),
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx_a.dimensions,
                order=10,
            ),
        ]
        ctx_map = {"ctx_a": ctx_a, "ctx_b": ctx_b}
        resolver = _StubResolver()
        result = extract_segments(
            items,
            ctx_map,
            resolver,
            definition_trees=def_trees,
        )
        # タクソノミ定義順: A が先（depth=2, 3番目の走査）、B が後（4番目）
        assert result[0].member_concept == "SegmentAReportableSegmentMember"
        assert result[1].member_concept == "SegmentBReportableSegmentMember"

    def test_unknown_member_appended_at_end(self) -> None:
        """インデックスに存在しないメンバーはタクソノミ定義順の末尾に追加。"""
        def_trees = _make_definition_trees()
        unknown_clark = f"{{{_FILER_NS}}}UnknownSegmentMember"
        ctx_known = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        ctx_unknown = _make_context(
            "ctx_u", segment_member_clark=unknown_clark
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_u",
                dimensions=ctx_unknown.dimensions,
                order=1,
            ),
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx_known.dimensions,
                order=2,
            ),
        ]
        ctx_map = {"ctx_a": ctx_known, "ctx_u": ctx_unknown}
        resolver = _StubResolver()
        result = extract_segments(
            items,
            ctx_map,
            resolver,
            definition_trees=def_trees,
        )
        # known（タクソノミ定義順）が先、unknown が末尾
        assert result[0].member_concept == "SegmentAReportableSegmentMember"
        assert result[1].member_concept == "UnknownSegmentMember"

    def test_definition_trees_none_fallback(self) -> None:
        """definition_trees=None なら depth=0, is_default_member=False。"""
        ctx = _make_context(
            "ctx_a", segment_member_clark=_SEG_A_MEMBER
        )
        items = [
            _make_line_item(
                "NetSales",
                "ctx_a",
                dimensions=ctx.dimensions,
            ),
        ]
        resolver = _StubResolver()
        result = extract_segments(
            items, {"ctx_a": ctx}, resolver, definition_trees=None
        )
        assert result[0].depth == 0
        assert result[0].is_default_member is False


# ---------------------------------------------------------------------------
# TestSegmentData
# ---------------------------------------------------------------------------


class TestSegmentData:
    """SegmentData dataclass のテスト。"""

    def test_dataclass_frozen(self) -> None:
        """SegmentData が frozen dataclass。"""
        seg = SegmentData(
            name="テスト",
            member_concept="TestMember",
            member_qname="{ns}TestMember",
            is_standard_member=True,
            items=(),
        )
        with pytest.raises(FrozenInstanceError):
            seg.name = "変更"  # type: ignore[misc]

    def test_member_qname(self) -> None:
        """member_qname に Clark notation が設定される。"""
        seg = SegmentData(
            name="テスト",
            member_concept="TestMember",
            member_qname="{ns}TestMember",
            is_standard_member=True,
            items=(),
        )
        assert seg.member_qname == "{ns}TestMember"

    def test_axis_concept_default(self) -> None:
        """axis_concept のデフォルト値が OperatingSegmentsAxis。"""
        seg = SegmentData(
            name="テスト",
            member_concept="TestMember",
            member_qname="{ns}TestMember",
            is_standard_member=True,
            items=(),
        )
        assert seg.axis_concept == "OperatingSegmentsAxis"

    def test_depth_default_zero(self) -> None:
        """depth のデフォルト値が 0。"""
        seg = SegmentData(
            name="テスト",
            member_concept="TestMember",
            member_qname="{ns}TestMember",
            is_standard_member=True,
            items=(),
        )
        assert seg.depth == 0

    def test_is_default_member_default_false(self) -> None:
        """is_default_member のデフォルト値が False。"""
        seg = SegmentData(
            name="テスト",
            member_concept="TestMember",
            member_qname="{ns}TestMember",
            is_standard_member=True,
            items=(),
        )
        assert seg.is_default_member is False


# ---------------------------------------------------------------------------
# TestHelpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """内部ヘルパー関数のテスト。"""

    def test_extract_local_name_from_clark(self) -> None:
        """Clark notation からローカル名が正しく抽出される。"""
        assert _extract_local_name_from_clark(
            "{http://example.com}NetSales"
        ) == "NetSales"

    def test_extract_local_name_from_plain(self) -> None:
        """Clark notation でない場合はそのまま返る。"""
        assert _extract_local_name_from_clark("NetSales") == "NetSales"

    def test_extract_namespace_from_clark(self) -> None:
        """Clark notation から名前空間 URI が正しく抽出される。"""
        assert _extract_namespace_from_clark(
            "{http://example.com}NetSales"
        ) == "http://example.com"

    def test_extract_namespace_from_plain(self) -> None:
        """Clark notation でない場合は空文字列。"""
        assert _extract_namespace_from_clark("NetSales") == ""

    def test_resolve_member_label_standard(self) -> None:
        """標準メンバーのラベルが解決される。"""
        resolver = _StubResolver({
            _REPORTABLE_MEMBER: {"ja": "報告セグメント"},
        })
        result = _resolve_member_label(_REPORTABLE_MEMBER, resolver)
        assert result == "報告セグメント"

    def test_resolve_member_label_fallback(self) -> None:
        """ラベル未解決時はローカル名から Member を除去。"""
        resolver = _StubResolver()
        result = _resolve_member_label(_SEG_A_MEMBER, resolver)
        assert result == "SegmentAReportableSegment"

    def test_find_axis_info_found(self) -> None:
        """_find_axis_info() が最初にヒットした AxisInfo を返す。"""
        def_trees = _make_definition_trees()
        axis = _find_axis_info(def_trees, "OperatingSegmentsAxis")
        assert axis is not None
        assert axis.axis_concept == "OperatingSegmentsAxis"

    def test_find_axis_info_not_found(self) -> None:
        """_find_axis_info() で対象軸が存在しない場合は None。"""
        def_trees = _make_definition_trees()
        axis = _find_axis_info(def_trees, "NonExistentAxis")
        assert axis is None

    def test_build_member_index_with_definition(self) -> None:
        """DefinitionTree から member → (depth, order) インデックスが構築。"""
        def_trees = _make_definition_trees()
        index, default = _build_member_index(
            def_trees, "OperatingSegmentsAxis"
        )
        assert "EntityTotalMember" in index
        assert "SegmentAReportableSegmentMember" in index
        assert index["EntityTotalMember"].depth == 0
        assert index["ReportableSegmentsMember"].depth == 1
        assert index["SegmentAReportableSegmentMember"].depth == 2
        assert default == "EntityTotalMember"

    def test_build_member_index_none(self) -> None:
        """definition_trees=None で空辞書と None が返る。"""
        index, default = _build_member_index(None, "OperatingSegmentsAxis")
        assert index == {}
        assert default is None

    def test_build_member_index_axis_not_found(self) -> None:
        """対象軸が DefinitionTree に存在しない場合は空辞書と None。"""
        def_trees = _make_definition_trees()
        index, default = _build_member_index(
            def_trees, "NonExistentAxis"
        )
        assert index == {}
        assert default is None

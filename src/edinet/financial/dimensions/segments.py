"""XBRL ディメンションからセグメント別データを抽出するモジュール。

XBRL コンテキストの ``xbrldi:explicitMember`` から事業セグメント・
地域セグメント等を抽出し、セグメント別の売上高・利益・資産等を
構造化する。

主要 API:
    - ``list_dimension_axes()``: Filing 内の全ディメンション軸を列挙
    - ``extract_segments()``: 指定軸のセグメント別データを抽出

Example:
    >>> from edinet.financial.dimensions.segments import (
    ...     extract_segments, list_dimension_axes,
    ... )
    >>> axes = list_dimension_axes(items, ctx_map, resolver)
    >>> for ax in axes:
    ...     print(f"{ax.label_ja}: {ax.member_count} メンバー")
    >>> segments = extract_segments(items, ctx_map, resolver)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from edinet.models.financial import LineItem
from edinet.xbrl._namespaces import is_standard_taxonomy
from edinet.xbrl.taxonomy import LabelSource

if TYPE_CHECKING:
    from edinet.financial.statements import Statements
    from edinet.xbrl.contexts import Period, StructuredContext
    from edinet.xbrl.linkbase.definition import (
        AxisInfo,
        DefinitionTree,
        MemberNode,
    )
    from edinet.xbrl.taxonomy import LabelInfo, TaxonomyResolver

logger = logging.getLogger(__name__)

_OPERATING_SEGMENTS_AXIS_LOCAL = "OperatingSegmentsAxis"
"""デフォルトの事業セグメント軸ローカル名。

EDINET 制度上の構造定数。``contexts.py`` の
``_CONSOLIDATED_AXIS_LOCAL`` と同レベルの不変定数。
"""

__all__ = [
    "DimensionAxisSummary",
    "SegmentItem",
    "SegmentData",
    "list_dimension_axes",
    "extract_segments",
]


# ---------------------------------------------------------------------------
# Clark notation ヘルパー
# ---------------------------------------------------------------------------


def _extract_local_name_from_clark(clark: str) -> str:
    """Clark notation からローカル名を抽出する。

    Args:
        clark: ``"{namespace}localName"`` 形式の文字列。

    Returns:
        ローカル名。``"}"`` を含まない場合はそのまま返す。

    Note:
        ``dataframe/facts.py`` L80-81 と同一パターン。
        将来的にコードベース全体で共通ユーティリティに統合する候補。
    """
    return clark.rsplit("}", 1)[-1]


def _extract_namespace_from_clark(clark: str) -> str:
    """Clark notation から名前空間 URI を抽出する。

    Args:
        clark: ``"{namespace}localName"`` 形式の文字列。

    Returns:
        名前空間 URI。Clark notation でない場合は空文字列。
    """
    if clark.startswith("{"):
        return clark[1 : clark.index("}")]
    return ""


# ---------------------------------------------------------------------------
# DefinitionLinkbase 連携ヘルパー
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _MemberMeta:
    """DefinitionLinkbase から取得したメンバーのメタ情報。"""

    depth: int
    order: float


def _find_axis_info(
    definition_trees: dict[str, DefinitionTree],
    axis_local_name: str,
) -> AxisInfo | None:
    """全 DefinitionTree から指定軸の AxisInfo を検索する。

    最初にヒットした AxisInfo を返す。C-8 QA によると
    OperatingSegmentsAxis は複数 role に出現するが、メンバー階層は
    同一であるため最初のヒットで十分。

    Args:
        definition_trees: ``parse_definition_linkbase()`` の戻り値。
        axis_local_name: 対象のディメンション軸ローカル名。

    Returns:
        AxisInfo。見つからなければ None。
    """
    for tree in definition_trees.values():
        for hc in tree.hypercubes:
            for axis in hc.axes:
                if axis.axis_concept == axis_local_name:
                    return axis
    return None


def _build_member_index(
    definition_trees: dict[str, DefinitionTree] | None,
    axis_local_name: str,
) -> tuple[dict[str, _MemberMeta], str | None]:
    """DefinitionLinkbase からメンバーのメタ情報インデックスを構築する。

    全 DefinitionTree を走査し、指定軸の AxisInfo を検索。
    MemberNode ツリーを深さ優先で走査して
    member_concept → _MemberMeta のインデックスを構築する。

    Args:
        definition_trees: ``parse_definition_linkbase()`` の戻り値。
            None の場合は空辞書を返す。
        axis_local_name: 対象のディメンション軸ローカル名。

    Returns:
        (メンバーインデックス, デフォルトメンバーのローカル名 or None)
        のタプル。
    """
    if definition_trees is None:
        return {}, None

    target_axis = _find_axis_info(definition_trees, axis_local_name)

    if target_axis is None or target_axis.domain is None:
        return {}, None

    index: dict[str, _MemberMeta] = {}
    counter = 0.0

    def _walk(node: MemberNode, depth: int) -> None:
        nonlocal counter
        index[node.concept] = _MemberMeta(depth=depth, order=counter)
        counter += 1.0
        for child in node.children:
            _walk(child, depth + 1)

    _walk(target_axis.domain, depth=0)

    return index, target_axis.default_member


# ---------------------------------------------------------------------------
# ラベル解決ヘルパー
# ---------------------------------------------------------------------------


def _resolve_member_label(
    member_qname: str,
    resolver: TaxonomyResolver,
) -> str:
    """メンバーの Clark notation から日本語ラベルを解決する。

    Args:
        member_qname: メンバーの Clark notation。
        resolver: TaxonomyResolver。

    Returns:
        日本語ラベル文字列。ラベルが見つからない場合は
        ローカル名から ``"Member"`` サフィックスを除去して返す。
    """
    result = resolver.resolve_clark(member_qname, lang="ja")
    if result.source != LabelSource.FALLBACK:
        return result.text
    local = _extract_local_name_from_clark(member_qname)
    return local.removesuffix("Member")


# ---------------------------------------------------------------------------
# 公開 dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DimensionAxisSummary:
    """Filing 内で検出されたディメンション軸の概要。

    ``list_dimension_axes()`` が返す。ユーザーが XBRL の内部名を
    知らなくても、日本語/英語ラベルで軸を選択できる。

    Attributes:
        local_name: 軸のローカル名（例: ``"OperatingSegmentsAxis"``）。
            ``extract_segments(axis_local_name=...)`` にそのまま渡せる。
        clark: 軸の Clark notation。
        label_ja: 日本語ラベル（例: ``"事業セグメント"``）。
        label_en: 英語ラベル（例: ``"Operating segments"``）。
        is_standard: 標準タクソノミの軸なら True。
        member_count: ユニークメンバー数。
        item_count: この軸を持つ LineItem の総数。
    """

    local_name: str
    clark: str
    label_ja: str
    label_en: str
    is_standard: bool
    member_count: int
    item_count: int


@dataclass(frozen=True, slots=True)
class SegmentItem:
    """セグメント内の 1 科目。

    Attributes:
        concept: concept のローカル名（例: ``"NetSales"``）。
        label_ja: 日本語ラベル情報。LineItem から転写。
        label_en: 英語ラベル情報。LineItem から転写。
        value: 値。数値 Fact は Decimal、テキストは str、nil は None。
        period: 期間情報。
        context_id: contextRef 属性値（トレーサビリティ用）。
    """

    concept: str
    label_ja: LabelInfo
    label_en: LabelInfo
    value: Decimal | str | None
    period: Period
    context_id: str


@dataclass(frozen=True, slots=True)
class SegmentData:
    """1 つのセグメントのデータ。

    Attributes:
        name: セグメント名（日本語ラベル。例: ``"自動車"``）。
        member_concept: メンバーのローカル名
            （例: ``"AutomotiveReportableSegmentMember"``）。
        member_qname: メンバーの Clark notation。
        is_standard_member: 標準メンバー（jpcrp_cor）なら True。
            提出者独自メンバーなら False。
        items: セグメント内の科目タプル。
        axis_concept: ディメンション軸のローカル名。
        depth: DefinitionLinkbase から取得したメンバー階層の深さ。
            0 = ドメインルート。DefinitionLinkbase 未提供時は 0。
        is_default_member: AxisInfo.default_member と一致する場合 True。
            DefinitionLinkbase 未提供時は False。
    """

    name: str
    member_concept: str
    member_qname: str
    is_standard_member: bool
    items: tuple[SegmentItem, ...]
    axis_concept: str = _OPERATING_SEGMENTS_AXIS_LOCAL
    depth: int = 0
    is_default_member: bool = False


# ---------------------------------------------------------------------------
# 内部ヘルパー: Statements 展開
# ---------------------------------------------------------------------------


def _resolve_source(
    source: Statements | Sequence[LineItem],
    context_map: dict[str, StructuredContext] | None,
    resolver: TaxonomyResolver | None,
) -> tuple[Sequence[LineItem], dict[str, StructuredContext], TaxonomyResolver]:
    """Statements または低レベル引数から (items, context_map, resolver) を取得する。

    Args:
        source: ``Statements`` または ``Sequence[LineItem]``。
        context_map: コンテキストマッピング。Statements 時は None 可。
        resolver: TaxonomyResolver。Statements 時は None 可。

    Returns:
        ``(items, context_map, resolver)`` のタプル。

    Raises:
        TypeError: 低レベル呼び出し時に必須引数が欠落した場合。
        EdinetConfigError: Statements に resolver が設定されていない場合。
    """
    from edinet.financial.statements import Statements as _Statements

    if isinstance(source, _Statements):
        items = list(source)
        ctx = source.context_map or {}
        res = resolver or source.resolver
        if res is None:
            from edinet.exceptions import EdinetConfigError

            raise EdinetConfigError(
                "Statements に resolver が設定されていません。"
                "taxonomy_path を指定して xbrl() を実行してください。"
            )
        return items, ctx, res

    if context_map is None or resolver is None:
        raise TypeError(
            "Sequence[LineItem] を渡す場合は context_map と resolver が必須です"
        )
    return source, context_map, resolver


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


def list_dimension_axes(
    source: Statements | Sequence[LineItem],
    context_map: dict[str, StructuredContext] | None = None,
    resolver: TaxonomyResolver | None = None,
    *,
    consolidated: bool = True,
) -> tuple[DimensionAxisSummary, ...]:
    """Filing 内の全ディメンション軸を日本語/英語ラベル付きで列挙する。

    ``Statements`` を渡す場合は ``context_map`` / ``resolver`` は不要
    （内部で自動取得される）。低レベル呼び出しでは3引数全て必須。

    Args:
        source: ``Statements`` または ``build_line_items()`` が返した全 LineItem。
        context_map: ``structure_contexts()`` が返した Context 辞書。
            ``Statements`` を渡す場合は省略可。
        resolver: ラベル解決用の TaxonomyResolver。
            ``Statements`` を渡す場合は省略可。
        consolidated: True なら連結、False なら個別の LineItem のみ対象。

    Returns:
        DimensionAxisSummary のタプル。item_count 降順。
        ディメンション軸が存在しなければ空タプル。
    """
    items, resolved_ctx_map, resolved_resolver = _resolve_source(
        source, context_map, resolver,
    )
    # axis_clark → {members: set, item_count: int}
    axis_stats: dict[str, tuple[set[str], int]] = {}

    for item in items:
        ctx = resolved_ctx_map.get(item.context_id)
        if ctx is None:
            continue
        if consolidated and not ctx.is_consolidated:
            continue
        if not consolidated and not ctx.is_non_consolidated:
            continue

        for dim in item.dimensions:
            members, count = axis_stats.get(dim.axis, (set(), 0))
            members.add(dim.member)
            axis_stats[dim.axis] = (members, count + 1)

    if not axis_stats:
        return ()

    results: list[DimensionAxisSummary] = []
    for axis_clark, (members, count) in axis_stats.items():
        local_name = _extract_local_name_from_clark(axis_clark)
        ns_uri = _extract_namespace_from_clark(axis_clark)

        label_ja_info = resolved_resolver.resolve_clark(axis_clark, lang="ja")
        label_en_info = resolved_resolver.resolve_clark(axis_clark, lang="en")

        label_ja = (
            label_ja_info.text
            if label_ja_info.source != LabelSource.FALLBACK
            else local_name
        )
        label_en = (
            label_en_info.text
            if label_en_info.source != LabelSource.FALLBACK
            else local_name
        )

        results.append(
            DimensionAxisSummary(
                local_name=local_name,
                clark=axis_clark,
                label_ja=label_ja,
                label_en=label_en,
                is_standard=is_standard_taxonomy(ns_uri),
                member_count=len(members),
                item_count=count,
            )
        )

    results.sort(key=lambda s: s.item_count, reverse=True)
    return tuple(results)


def extract_segments(
    source: Statements | Sequence[LineItem],
    context_map: dict[str, StructuredContext] | None = None,
    resolver: TaxonomyResolver | None = None,
    *,
    consolidated: bool = True,
    period: Period | None = None,
    axis_local_name: str = _OPERATING_SEGMENTS_AXIS_LOCAL,
    definition_trees: dict[str, DefinitionTree] | None = None,
) -> tuple[SegmentData, ...]:
    """LineItem 群からセグメント別データを抽出する。

    ``Statements`` を渡す場合は ``context_map`` / ``resolver`` は不要
    （内部で自動取得される）。低レベル呼び出しでは3引数全て必須。

    Args:
        source: ``Statements`` または ``build_line_items()`` が返した全 LineItem。
        context_map: ``structure_contexts()`` が返した Context 辞書。
            ``Statements`` を渡す場合は省略可。
        resolver: ラベル解決用の TaxonomyResolver。
            ``Statements`` を渡す場合は省略可。
        consolidated: True なら連結、False なら個別。
        period: 対象期間。None なら全期間のセグメントを抽出。
        axis_local_name: ディメンション軸のローカル名。
            デフォルトは ``"OperatingSegmentsAxis"``。
        definition_trees: ``parse_definition_linkbase()`` の戻り値（任意）。
            指定した場合、メンバーの depth / is_default_member /
            タクソノミ定義順を付与する。

    Returns:
        SegmentData のタプル。セグメントが見つからなければ空タプル。
    """
    items, resolved_ctx_map, resolved_resolver = _resolve_source(
        source, context_map, resolver,
    )
    # Step 0: DefinitionLinkbase からメタ情報を構築
    member_index, default_member = _build_member_index(
        definition_trees, axis_local_name
    )

    # Step 1-2: LineItem を走査し、対象軸のメンバーでグルーピング
    # member_clark → list[(LineItem, DimensionMember)]
    groups: dict[str, list[LineItem]] = defaultdict(list)

    for item in items:
        ctx = resolved_ctx_map.get(item.context_id)
        if ctx is None:
            continue

        # 連結/個別フィルタ
        if consolidated and not ctx.is_consolidated:
            continue
        if not consolidated and not ctx.is_non_consolidated:
            continue

        # 期間フィルタ
        if period is not None and item.period != period:
            continue

        # ディメンション軸のマッチング
        for dim in item.dimensions:
            axis_local = _extract_local_name_from_clark(dim.axis)
            if axis_local == axis_local_name:
                groups[dim.member].append(item)
                break  # 1 アイテムにつき同一軸は 1 回のみ

    if not groups:
        return ()

    # Step 3-4: 各グループから SegmentData を構築
    segments: list[tuple[float, SegmentData]] = []

    for member_clark, group_items in groups.items():
        member_local = _extract_local_name_from_clark(member_clark)
        member_ns = _extract_namespace_from_clark(member_clark)
        segment_name = _resolve_member_label(member_clark, resolved_resolver)
        is_standard = is_standard_taxonomy(member_ns)

        # SegmentItem に変換
        seg_items = tuple(
            SegmentItem(
                concept=item.local_name,
                label_ja=item.label_ja,
                label_en=item.label_en,
                value=item.value,
                period=item.period,
                context_id=item.context_id,
            )
            for item in group_items
        )

        # DefinitionLinkbase メタ情報
        meta = member_index.get(member_local)
        depth = meta.depth if meta is not None else 0
        is_default = (
            default_member is not None and member_local == default_member
        )

        # ソート用キー
        if meta is not None:
            sort_key = meta.order
        else:
            # definition_trees なし or 未知メンバー → 文書出現順
            min_order = min(item.order for item in group_items)
            # 未知メンバーはタクソノミ定義順の末尾（大きな値）に配置
            sort_key = 1_000_000.0 + min_order

        segments.append((
            sort_key,
            SegmentData(
                name=segment_name,
                member_concept=member_local,
                member_qname=member_clark,
                is_standard_member=is_standard,
                items=seg_items,
                axis_concept=axis_local_name,
                depth=depth,
                is_default_member=is_default,
            ),
        ))

    segments.sort(key=lambda pair: pair[0])
    return tuple(seg for _, seg in segments)

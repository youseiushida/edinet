"""XBRL Presentation Linkbase パーサー。

Presentation Linkbase (_pre.xml) を解析し、科目の表示順序ツリーを構築する。
後続の concept_sets モジュールが本モジュールに依存し、手動 JSON による
科目セット定義を置き換える基盤となる。

典型的な使い方::

    from edinet.xbrl.linkbase.presentation import parse_presentation_linkbase

    trees = parse_presentation_linkbase(xml_bytes)
    for role_uri, tree in trees.items():
        for node in tree.flatten():
            print(f"{'  ' * node.depth}{node.concept}")
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING
from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl._linkbase_utils import (
    ROLE_LABEL,  # noqa: F401 — 後方互換の re-export
    ROLE_NEGATED_LABEL,  # noqa: F401
    ROLE_PERIOD_END_LABEL,  # noqa: F401
    ROLE_PERIOD_START_LABEL,  # noqa: F401
    ROLE_TERSE_LABEL,  # noqa: F401
    ROLE_TOTAL_LABEL,
    ROLE_VERBOSE_LABEL,  # noqa: F401
    extract_concept_from_href as _extract_concept_from_href,
)
from edinet.xbrl._namespaces import NS_LINK, NS_XLINK

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Sequence

# ============================================================
# ディメンション関連定数
# ============================================================

_DIMENSION_SUFFIXES = (
    "Axis",
    "Member",
    "Domain",
    "Table",
    "LineItems",
)
"""ディメンション関連ノードを識別するサフィックス群。"""

# ============================================================
# 内部データモデル
# ============================================================


@dataclass(frozen=True, slots=True)
class _LocInfo:
    """loc 要素から抽出した情報。

    Attributes:
        href: xlink:href 属性値（元の値）。
        concept: 正規化済み concept 名。
    """

    href: str
    concept: str


@dataclass(frozen=True, slots=True)
class _RawArc:
    """presentationArc 要素から抽出した情報。

    Attributes:
        from_label: xlink:from 属性値。
        to_label: xlink:to 属性値。
        order: order 属性値。
        preferred_label: preferredLabel 属性値。
    """

    from_label: str
    to_label: str
    order: float
    preferred_label: str | None


# ============================================================
# 公開データモデル
# ============================================================


@dataclass(frozen=True, slots=True)
class PresentationNode:
    """Presentation Linkbase のツリーノード。

    Attributes:
        concept: 正規化済み concept 名（例: "CashAndDeposits"）。
        href: 元の xlink:href 値。
        order: 表示順序。
        preferred_label: preferredLabel ロール URI。None の場合は標準ラベル。
        depth: ツリーにおける深さ（ルート = 0）。
        children: 子ノードのタプル（order 順）。
        is_abstract: Abstract ノードかどうか。concept 名が "Abstract" で
            終わるかどうかで判定する。
        is_dimension_node: ディメンション関連ノードかどうか。
    """

    concept: str
    href: str
    order: float
    preferred_label: str | None = None
    depth: int = 0
    children: tuple[PresentationNode, ...] = ()
    is_abstract: bool = False
    is_dimension_node: bool = False

    @property
    def is_total(self) -> bool:
        """合計行かどうかを返す。

        Returns:
            preferred_label が totalLabel ロールの場合 True。
        """
        return self.preferred_label == ROLE_TOTAL_LABEL

    def __repr__(self) -> str:
        child_count = len(self.children)
        return (
            f"PresentationNode(concept={self.concept!r}, "
            f"depth={self.depth}, order={self.order}, "
            f"children={child_count})"
        )


@dataclass(frozen=True, slots=True)
class PresentationTree:
    """1 つの role URI に対応する Presentation ツリー。

    Attributes:
        role_uri: ツリーが属する role URI。
        roots: ルートノード群（order 順）。
        node_count: ツリー内の全ノード数。
    """

    role_uri: str
    roots: tuple[PresentationNode, ...] = ()
    node_count: int = 0

    def line_items_roots(self) -> tuple[PresentationNode, ...]:
        """LineItems ノード以下のルートを返す。

        Presentation ツリーでは Heading → Table → LineItems の構造が
        一般的であり、実際の科目は LineItems の子として並ぶ。
        本メソッドは LineItems ノードを探索し、その子をルートとして返す。

        LineItems が見つからない場合は roots をそのまま返す。

        Returns:
            LineItems ノードの子、または roots。
        """
        for root in self.roots:
            result = _find_line_items(root)
            if result is not None:
                return result
        return self.roots

    def flatten(
        self,
        *,
        skip_abstract: bool = False,
        skip_dimension: bool = False,
    ) -> tuple[PresentationNode, ...]:
        """ツリーを深さ優先で平坦化する。

        Args:
            skip_abstract: True の場合、Abstract ノードをスキップする。
            skip_dimension: True の場合、ディメンション関連ノードをスキップする。

        Returns:
            深さ優先順のノードタプル。

        Note:
            同一 concept が複数の位置に出現する場合（例: dimension ノードと
            科目ツリーの両方に同じ concept が参照される場合）、返り値には
            同一 concept 名の異なるノードが含まれる。concept のユニーク
            集合が必要な場合は ``{n.concept for n in tree.flatten()}`` を使用する。
        """
        result: list[PresentationNode] = []
        for root in self.roots:
            _flatten_node(root, result, skip_abstract, skip_dimension)
        return tuple(result)

    def __repr__(self) -> str:
        return (
            f"PresentationTree(role_uri={self.role_uri!r}, "
            f"roots={len(self.roots)}, node_count={self.node_count})"
        )


# ============================================================
# 公開 API
# ============================================================


def parse_presentation_linkbase(
    xml_bytes: bytes,
    *,
    source_path: str | None = None,
) -> dict[str, PresentationTree]:
    """Presentation Linkbase XML をパースし、role URI ごとのツリーを返す。

    Args:
        xml_bytes: linkbase XML のバイト列。
        source_path: エラーメッセージ用のソースファイルパス。

    Returns:
        role URI をキー、PresentationTree を値とする辞書。

    Raises:
        EdinetParseError: XML が不正な場合。
    """
    source_label = source_path or "<bytes>"

    try:
        root = etree.fromstring(xml_bytes)  # noqa: S320
    except etree.XMLSyntaxError as exc:
        msg = f"Presentation Linkbase の XML 解析に失敗しました: {source_label}: {exc}"
        raise EdinetParseError(msg) from exc

    return _parse_links(root, source_label)


def merge_presentation_trees(
    *tree_dicts: dict[str, PresentationTree],
) -> dict[str, PresentationTree]:
    """複数の PresentationTree 辞書をマージする。

    同一 role URI のツリーは再帰的に子をマージし、異なる role URI の
    ツリーはそのまま結合する。

    Args:
        *tree_dicts: マージ対象の辞書群。

    Returns:
        マージ済み辞書。
    """
    if not tree_dicts:
        return {}

    non_empty = [d for d in tree_dicts if d]
    if not non_empty:
        return {}
    if len(non_empty) == 1:
        return dict(non_empty[0])

    # role URI ごとにツリーを収集
    by_role: dict[str, list[PresentationTree]] = {}
    for d in non_empty:
        for role_uri, tree in d.items():
            by_role.setdefault(role_uri, []).append(tree)

    result: dict[str, PresentationTree] = {}
    for role_uri, trees in by_role.items():
        if len(trees) == 1:
            result[role_uri] = trees[0]
        else:
            merged_roots = _merge_root_lists([t.roots for t in trees])
            rebuilt = tuple(_rebuild_with_depth(r, 0) for r in merged_roots)
            result[role_uri] = PresentationTree(
                role_uri=role_uri,
                roots=rebuilt,
                node_count=_count_nodes(rebuilt),
            )

    return result


# ============================================================
# 内部実装
# ============================================================


def _parse_links(
    root: etree._Element,
    source_label: str,
) -> dict[str, PresentationTree]:
    """XML ルートから presentationLink を解析する。

    Args:
        root: XML のルート要素。
        source_label: エラーメッセージ用のソース表示名。

    Returns:
        role URI → PresentationTree の辞書。
    """
    result: dict[str, PresentationTree] = {}

    for plink in root.iter(f"{{{NS_LINK}}}presentationLink"):
        role_uri = plink.get(f"{{{NS_XLINK}}}role")
        if not role_uri:
            warnings.warn(
                f"presentationLink に xlink:role がありません: {source_label}",
                EdinetWarning,
                stacklevel=4,
            )
            continue

        # loc マップ構築
        loc_map: dict[str, _LocInfo] = {}
        for loc_elem in plink.iter(f"{{{NS_LINK}}}loc"):
            label = loc_elem.get(f"{{{NS_XLINK}}}label")
            href = loc_elem.get(f"{{{NS_XLINK}}}href")
            if not label:
                continue
            if not href:
                warnings.warn(
                    f"loc 要素に xlink:href がありません (label={label!r}): "
                    f"{source_label}",
                    EdinetWarning,
                    stacklevel=4,
                )
                continue
            concept = _extract_concept_from_href(href)
            if concept is None:
                warnings.warn(
                    f"loc の href からコンセプト名を抽出できません "
                    f"(href={href!r}): {source_label}",
                    EdinetWarning,
                    stacklevel=4,
                )
                continue
            loc_map[label] = _LocInfo(href=href, concept=concept)

        # arc リスト構築
        arcs: list[_RawArc] = []
        for arc_elem in plink.iter(f"{{{NS_LINK}}}presentationArc"):
            from_label = arc_elem.get(f"{{{NS_XLINK}}}from")
            to_label = arc_elem.get(f"{{{NS_XLINK}}}to")
            if not from_label or not to_label:
                continue

            order = _parse_order(arc_elem.get("order"), source_label)
            preferred_label = arc_elem.get("preferredLabel")

            arcs.append(
                _RawArc(
                    from_label=from_label,
                    to_label=to_label,
                    order=order,
                    preferred_label=preferred_label,
                )
            )

        # ツリー構築
        tree = _build_tree(arcs, loc_map, role_uri)
        result[role_uri] = tree

    return result


def _parse_order(raw: str | None, source_label: str) -> float:
    """order 属性値をパースする。

    Args:
        raw: order 属性の文字列値。
        source_label: 警告メッセージ用のソース表示名。

    Returns:
        パース済みの float 値。パース不能の場合は 0.0。
    """
    if raw is None:
        warnings.warn(
            f"presentationArc に order 属性がありません: {source_label}",
            EdinetWarning,
            stacklevel=4,
        )
        return 0.0
    try:
        return float(raw)
    except (ValueError, TypeError):
        warnings.warn(
            f"order 属性を数値に変換できません (order={raw!r}): {source_label}",
            EdinetWarning,
            stacklevel=4,
        )
        return 0.0


def _build_tree(
    arcs: list[_RawArc],
    loc_map: dict[str, _LocInfo],
    role_uri: str,
) -> PresentationTree:
    """arc と loc 情報からツリーを構築する。

    Args:
        arcs: presentationArc の情報リスト。
        loc_map: xlink:label → _LocInfo のマップ。
        role_uri: このツリーの role URI。

    Returns:
        構築済み PresentationTree。
    """
    if not arcs:
        return PresentationTree(role_uri=role_uri, roots=(), node_count=0)

    # 隣接リスト構築: from_label → [(to_label, order, preferred_label)]
    children_map: dict[str, list[tuple[str, float, str | None]]] = {}
    child_labels: set[str] = set()

    for arc in arcs:
        if arc.from_label not in loc_map or arc.to_label not in loc_map:
            continue
        children_map.setdefault(arc.from_label, []).append(
            (arc.to_label, arc.order, arc.preferred_label)
        )
        child_labels.add(arc.to_label)

    # ルートは、arc で参照されているが子としては現れないノード
    all_from = {arc.from_label for arc in arcs if arc.from_label in loc_map}
    all_to = {arc.to_label for arc in arcs if arc.to_label in loc_map}
    root_labels = all_from - all_to

    if not root_labels:
        # 全てが子 → 循環の可能性。from 側の最初をルートとする。
        root_labels = all_from

    # order でソート
    for _label, child_list in children_map.items():
        child_list.sort(key=lambda x: x[1])

    # DFS でツリー構築（循環検出付き）
    def build_node(
        label: str,
        order: float,
        preferred_label: str | None,
        depth: int,
        visited: set[str],
    ) -> PresentationNode | None:
        if label in visited:
            loc_info_cycle = loc_map.get(label)
            cycle_name = loc_info_cycle.concept if loc_info_cycle else label
            warnings.warn(
                f"Presentation ツリーに循環参照があります: "
                f"concept={cycle_name!r}, role_uri={role_uri!r}",
                EdinetWarning,
                stacklevel=4,
            )
            return None
        visited.add(label)

        loc_info = loc_map.get(label)
        if loc_info is None:
            return None

        concept = loc_info.concept
        node_children: list[PresentationNode] = []

        for child_label, child_order, child_pref in children_map.get(label, []):
            child_node = build_node(
                child_label, child_order, child_pref, depth + 1, visited
            )
            if child_node is not None:
                node_children.append(child_node)

        visited.discard(label)

        is_abstract = concept.endswith("Abstract") or concept.endswith("Heading")
        is_dim = any(concept.endswith(s) for s in _DIMENSION_SUFFIXES)

        return PresentationNode(
            concept=concept,
            href=loc_info.href,
            order=order,
            preferred_label=preferred_label,
            depth=depth,
            children=tuple(node_children),
            is_abstract=is_abstract,
            is_dimension_node=is_dim,
        )

    # ルートノード構築
    roots: list[PresentationNode] = []
    # ルートの order は arc での出現順に基づくため 0 始まり
    root_label_list = sorted(root_labels)
    for root_label in root_label_list:
        node = build_node(root_label, 0.0, None, 0, set())
        if node is not None:
            roots.append(node)

    roots_tuple = tuple(roots)
    return PresentationTree(
        role_uri=role_uri,
        roots=roots_tuple,
        node_count=_count_nodes(roots_tuple),
    )


def _count_nodes(roots: tuple[PresentationNode, ...] | Sequence[PresentationNode]) -> int:
    """ノード数を再帰的にカウントする。

    Args:
        roots: ルートノード群。

    Returns:
        全ノード数。
    """
    count = 0
    for node in roots:
        count += 1 + _count_nodes(node.children)
    return count


def _find_line_items(node: PresentationNode) -> tuple[PresentationNode, ...] | None:
    """LineItems ノードを探索し、その子を返す。

    Args:
        node: 探索起点のノード。

    Returns:
        LineItems ノードの children、見つからなければ None。
    """
    if node.concept.endswith("LineItems"):
        return node.children
    for child in node.children:
        result = _find_line_items(child)
        if result is not None:
            return result
    return None


def _flatten_node(
    node: PresentationNode,
    result: list[PresentationNode],
    skip_abstract: bool,
    skip_dimension: bool,
) -> None:
    """ノードを深さ優先で平坦化する。

    Args:
        node: 平坦化対象のノード。
        result: 結果を格納するリスト（破壊的更新）。
        skip_abstract: Abstract ノードをスキップするか。
        skip_dimension: ディメンションノードをスキップするか。
    """
    skip = False
    if skip_abstract and node.is_abstract:
        skip = True
    if skip_dimension and node.is_dimension_node:
        skip = True

    if not skip:
        result.append(node)

    for child in node.children:
        _flatten_node(child, result, skip_abstract, skip_dimension)


# ============================================================
# マージ関連
# ============================================================


def _merge_root_lists(
    root_lists: list[tuple[PresentationNode, ...]],
) -> list[PresentationNode]:
    """複数のルートリストをマージする。

    Args:
        root_lists: マージ対象のルートリスト群。

    Returns:
        マージ済みルートリスト。
    """
    by_concept: dict[str, list[PresentationNode]] = {}
    concept_order: list[str] = []

    for roots in root_lists:
        for root in roots:
            if root.concept not in by_concept:
                concept_order.append(root.concept)
            by_concept.setdefault(root.concept, []).append(root)

    result: list[PresentationNode] = []
    for concept in concept_order:
        nodes = by_concept[concept]
        if len(nodes) == 1:
            result.append(nodes[0])
        else:
            merged = _merge_nodes(nodes)
            result.append(merged)

    return result


def _merge_nodes(nodes: list[PresentationNode]) -> PresentationNode:
    """同一 concept の複数ノードをマージする。

    先着のノードの属性を優先し、子を再帰的にマージする。

    Args:
        nodes: マージ対象のノード群（全て同一 concept）。

    Returns:
        マージ済みノード。
    """
    first = nodes[0]

    # 子をマージ
    all_children_lists = [list(n.children) for n in nodes]
    merged_children = _merge_children(all_children_lists)

    return PresentationNode(
        concept=first.concept,
        href=first.href,
        order=first.order,
        preferred_label=first.preferred_label,
        depth=first.depth,
        children=tuple(merged_children),
        is_abstract=first.is_abstract,
        is_dimension_node=first.is_dimension_node,
    )


def _merge_children(
    children_lists: list[list[PresentationNode]],
) -> list[PresentationNode]:
    """複数の children リストをマージする。

    同一 concept の子は再帰的にマージし、order 順にソートする。

    Args:
        children_lists: マージ対象の children リスト群。

    Returns:
        マージ済み children リスト。
    """
    by_concept: dict[str, list[PresentationNode]] = {}
    concept_order: list[str] = []

    for children in children_lists:
        for child in children:
            if child.concept not in by_concept:
                concept_order.append(child.concept)
            by_concept.setdefault(child.concept, []).append(child)

    result: list[PresentationNode] = []
    for concept in concept_order:
        nodes = by_concept[concept]
        if len(nodes) == 1:
            result.append(nodes[0])
        else:
            result.append(_merge_nodes(nodes))

    # order 順でソート（安定ソート）
    result.sort(key=lambda n: n.order)
    return result


def _rebuild_with_depth(node: PresentationNode, depth: int) -> PresentationNode:
    """ノードの depth を再帰的に再計算する。

    Args:
        node: 再計算対象のノード。
        depth: このノードに設定する depth。

    Returns:
        depth が再計算されたノード。
    """
    new_children = tuple(
        _rebuild_with_depth(child, depth + 1) for child in node.children
    )
    return PresentationNode(
        concept=node.concept,
        href=node.href,
        order=node.order,
        preferred_label=node.preferred_label,
        depth=depth,
        children=new_children,
        is_abstract=node.is_abstract,
        is_dimension_node=node.is_dimension_node,
    )

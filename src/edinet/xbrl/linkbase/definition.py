"""Definition Linkbase パーサー。

XBRL Definition Linkbase (`_def.xml`) をパースし、
ハイパーキューブ構造（Table → Axis → Domain → Member）を
木構造として提供する。
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl._linkbase_utils import extract_concept_from_href as _extract_concept_from_href
from edinet.xbrl._namespaces import NS_LINK, NS_XBRLDT, NS_XLINK

logger = logging.getLogger(__name__)

# ---------- arcrole 定数（プライベート） ----------
_ARCROLE_ALL = "http://xbrl.org/int/dim/arcrole/all"
_ARCROLE_HYPERCUBE_DIMENSION = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
_ARCROLE_DIMENSION_DOMAIN = "http://xbrl.org/int/dim/arcrole/dimension-domain"
_ARCROLE_DIMENSION_DEFAULT = "http://xbrl.org/int/dim/arcrole/dimension-default"
_ARCROLE_DOMAIN_MEMBER = "http://xbrl.org/int/dim/arcrole/domain-member"
_ARCROLE_GENERAL_SPECIAL = "http://www.xbrl.org/2003/arcrole/general-special"

# ========== データモデル ==========


@dataclass(frozen=True, slots=True)
class DefinitionArc:
    """Definition Linkbase の 1 本の arc。

    Attributes:
        from_concept: 親 concept のローカル名（例: ``"ConsolidatedBalanceSheetHeading"``）。
        to_concept: 子 concept のローカル名（例: ``"BalanceSheetTable"``）。
        from_href: 親 concept の xlink:href（XSD 相対パス + フラグメント）。
        to_href: 子 concept の xlink:href。
        arcrole: arcrole URI。
        order: 表示順。
        closed: xbrldt:closed 属性値。``all`` arcrole のアークでのみ設定される。
            それ以外のアークでは**常に** ``None``（XML に属性が存在しても無視される）。
        context_element: xbrldt:contextElement 属性値。``all`` arcrole のアークでのみ設定される。
            それ以外のアークでは**常に** ``None``。
        usable: usable 属性値。全 arc 型の XML 属性から読み取るが、
            意味的に有効なのは ``domain-member`` arcrole のみ。
    """

    from_concept: str
    to_concept: str
    from_href: str
    to_href: str
    arcrole: str
    order: float
    closed: bool | None = None
    context_element: str | None = None
    usable: bool = True


@dataclass(frozen=True, slots=True)
class MemberNode:
    """ドメイン配下のメンバーノード（ツリー構造）。

    ドメインをルートとし、domain-member arc による階層を再帰的に保持する。
    SS の列ヘッダー構築等で階層情報と usable フラグが必要。

    Attributes:
        concept: メンバーのローカル名（例: ``"ShareholdersEquityAbstract"``）。
        href: xlink:href（XSD 相対パス + フラグメント）。
        usable: Fact を持ちうるか。``False`` の場合は表示専用（Abstract 等）。
        children: 子メンバーノードのタプル（order 順ソート済み）。
    """

    concept: str
    href: str
    usable: bool = True
    children: tuple[MemberNode, ...] = ()

    def __repr__(self) -> str:
        return (
            f"MemberNode(concept={self.concept!r}, "
            f"usable={self.usable}, children={len(self.children)})"
        )


@dataclass(frozen=True, slots=True)
class AxisInfo:
    """1 つの Axis（次元軸）の構造化情報。

    Attributes:
        axis_concept: Axis のローカル名（例: ``"ComponentsOfEquityAxis"``）。
        order: hypercube-dimension arc の order 値（複数 Axis の表示順序）。
        domain: ドメインのルートノード。子にメンバー階層を再帰的に持つ。
            ドメインが未定義の場合は None。
        default_member: デフォルトメンバーのローカル名。
            デフォルトがない場合は None。
    """

    axis_concept: str
    order: float = 0.0
    domain: MemberNode | None = None
    default_member: str | None = None


@dataclass(frozen=True, slots=True)
class HypercubeInfo:
    """ハイパーキューブの構造化情報。

    Attributes:
        table_concept: Table のローカル名。
        heading_concept: Heading（ルート要素）のローカル名。
        axes: ハイパーキューブに属する Axis の情報
            （``hypercube-dimension`` arc の order 昇順でソート済み）。
        closed: ハイパーキューブが closed かどうか。
        context_element: ``"segment"`` or ``"scenario"``。
        line_items_concept: LineItems のローカル名。
            LineItems がない場合は None。
    """

    table_concept: str
    heading_concept: str
    axes: tuple[AxisInfo, ...]
    closed: bool
    context_element: str
    line_items_concept: str | None = None

    def __repr__(self) -> str:
        axes = ", ".join(a.axis_concept for a in self.axes)
        return (
            f"HypercubeInfo(table={self.table_concept!r}, "
            f"axes=[{axes}])"
        )


@dataclass(frozen=True, slots=True)
class DefinitionTree:
    """1 つの role URI に対応する定義ツリー。

    Attributes:
        role_uri: ロール URI。
        arcs: 全 arc のタプル。認識されない arcrole の arc も含む。
        hypercubes: 構造化されたハイパーキューブ情報のタプル。
            ``arcs`` の部分集合（``all``, ``hypercube-dimension``,
            ``dimension-domain``, ``dimension-default``, ``domain-member``
            arcrole）を構造化したもの。``general-special`` のみの role では
            空タプル（``has_hypercube`` == False）。
    """

    role_uri: str
    arcs: tuple[DefinitionArc, ...]
    hypercubes: tuple[HypercubeInfo, ...]

    @property
    def has_hypercube(self) -> bool:
        """ハイパーキューブ構造を含むかどうか。"""
        return len(self.hypercubes) > 0

    def __repr__(self) -> str:
        return (
            f"DefinitionTree(role_uri={self.role_uri!r}, "
            f"arcs={len(self.arcs)}, hypercubes={len(self.hypercubes)})"
        )


# ========== プライベートヘルパー ==========


def _build_member_tree(
    concept: str,
    href: str,
    usable: bool,
    arcs: list[DefinitionArc],
    visited: set[str],
) -> MemberNode:
    """domain-member arc を再帰的に辿り MemberNode ツリーを構築する。

    Args:
        concept: 現在のノードの concept ローカル名。
        href: 現在のノードの xlink:href。
        usable: 現在のノードの usable フラグ。
        arcs: 現在の role 内の全 DefinitionArc。
        visited: 祖先パス上の concept 名（循環検出用、コピー方式）。
    """
    visited = visited | {concept}  # 兄弟間独立のイミュータブルコピー

    # この concept を起点とする domain-member arc を収集（order 昇順）
    child_arcs = sorted(
        [
            a
            for a in arcs
            if a.arcrole == _ARCROLE_DOMAIN_MEMBER and a.from_concept == concept
        ],
        key=lambda a: a.order,
    )

    children: list[MemberNode] = []
    for arc in child_arcs:
        if arc.to_concept in visited:
            logger.warning(
                "定義リンク: domain-member 循環参照を検出: %s → %s",
                concept,
                arc.to_concept,
            )
            continue
        child_node = _build_member_tree(
            concept=arc.to_concept,
            href=arc.to_href,
            usable=arc.usable,
            arcs=arcs,
            visited=visited,
        )
        children.append(child_node)

    return MemberNode(
        concept=concept,
        href=href,
        usable=usable,
        children=tuple(children),
    )


def _build_hypercubes(arcs: list[DefinitionArc]) -> list[HypercubeInfo]:
    """DefinitionArc 群からハイパーキューブ構造を構築する。

    Args:
        arcs: 1 つの role 内の全 DefinitionArc。

    Returns:
        構造化された HypercubeInfo のリスト。
    """
    hypercubes: list[HypercubeInfo] = []

    for arc in arcs:
        if arc.arcrole != _ARCROLE_ALL:
            continue

        heading = arc.from_concept
        table = arc.to_concept
        closed = arc.closed if arc.closed is not None else False
        context_element = arc.context_element if arc.context_element is not None else "scenario"

        # 1. この table に属する axes を収集
        axis_arcs = [
            a
            for a in arcs
            if a.arcrole == _ARCROLE_HYPERCUBE_DIMENSION
            and a.from_concept == table
        ]

        # 2. 各 axis の domain, default, members を収集
        axis_infos: list[AxisInfo] = []
        for axis_arc in axis_arcs:
            axis_concept = axis_arc.to_concept

            # dimension-domain → ドメインを特定し MemberNode ツリーのルートとする
            domain_arcs = [
                a
                for a in arcs
                if a.arcrole == _ARCROLE_DIMENSION_DOMAIN
                and a.from_concept == axis_concept
            ]
            domain_node: MemberNode | None = None
            if domain_arcs:
                da = domain_arcs[0]
                domain_node = _build_member_tree(
                    concept=da.to_concept,
                    href=da.to_href,
                    usable=da.usable,
                    arcs=arcs,
                    visited=set(),
                )

            # dimension-default arc → デフォルトメンバーを特定
            default_member: str | None = None
            for a in arcs:
                if (
                    a.arcrole == _ARCROLE_DIMENSION_DEFAULT
                    and a.from_concept == axis_concept
                ):
                    default_member = a.to_concept
                    break

            axis_infos.append(
                AxisInfo(
                    axis_concept=axis_concept,
                    order=axis_arc.order,
                    domain=domain_node,
                    default_member=default_member,
                )
            )

        # Axes を hypercube-dimension arc の order 昇順ソート
        axis_infos.sort(key=lambda a: a.order)

        # 3. heading から domain-member で接続される *LineItems を特定
        line_items_arcs = [
            a
            for a in arcs
            if a.arcrole == _ARCROLE_DOMAIN_MEMBER
            and a.from_concept == heading
            and a.to_concept.endswith("LineItems")
        ]
        line_items_concept: str | None = None
        if line_items_arcs:
            line_items_concept = min(
                line_items_arcs, key=lambda a: a.order
            ).to_concept

        hypercubes.append(
            HypercubeInfo(
                table_concept=table,
                heading_concept=heading,
                axes=tuple(axis_infos),
                closed=closed,
                context_element=context_element,
                line_items_concept=line_items_concept,
            )
        )

    return hypercubes


# ========== 公開 API ==========


def parse_definition_linkbase(
    xml_bytes: bytes,
    *,
    source_path: str | None = None,
) -> dict[str, DefinitionTree]:
    """Definition Linkbase の XML bytes をパースする。

    Args:
        xml_bytes: ``_def.xml`` の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。

    Returns:
        role_uri をキー、DefinitionTree を値とする辞書。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
    # 1. XML パース
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        path_info = f": {source_path}" if source_path else ""
        raise EdinetParseError(
            f"定義リンクベースの XML パースに失敗しました{path_info}"
        ) from e

    # 2. definitionLink 要素を走査
    def_links = root.findall(f"{{{NS_LINK}}}definitionLink")
    logger.debug("定義リンクベースをパース中: %d definitionLink 要素", len(def_links))

    trees: dict[str, DefinitionTree] = {}

    for def_link in def_links:
        role_uri = def_link.get(f"{{{NS_XLINK}}}role")
        if not role_uri:
            warnings.warn(
                "定義リンク: xlink:role が未設定のためスキップします",
                EdinetWarning,
                stacklevel=2,
            )
            continue

        # 3. loc マップ構築: {xlink:label: (concept_local_name, href)}
        loc_map: dict[str, tuple[str, str]] = {}
        for loc_elem in def_link.findall(f"{{{NS_LINK}}}loc"):
            label = loc_elem.get(f"{{{NS_XLINK}}}label")
            href = loc_elem.get(f"{{{NS_XLINK}}}href")
            if not label or not href:
                continue
            concept = _extract_concept_from_href(href)
            if concept is None:
                warnings.warn(
                    f"定義リンク: loc の href にフラグメントがありません: '{href}'",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue
            loc_map[label] = (concept, href)

        # 4. definitionArc → DefinitionArc に変換
        arc_list: list[DefinitionArc] = []
        for arc_elem in def_link.findall(f"{{{NS_LINK}}}definitionArc"):
            from_label = arc_elem.get(f"{{{NS_XLINK}}}from")
            to_label = arc_elem.get(f"{{{NS_XLINK}}}to")
            arcrole = arc_elem.get(f"{{{NS_XLINK}}}arcrole", "")

            if not from_label or not to_label:
                continue

            # loc_map から concept を解決
            if from_label not in loc_map:
                warnings.warn(
                    f"定義リンク: 不明なロケーター参照 '{from_label}' をスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue
            if to_label not in loc_map:
                warnings.warn(
                    f"定義リンク: 不明なロケーター参照 '{to_label}' をスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            from_concept, from_href = loc_map[from_label]
            to_concept, to_href = loc_map[to_label]

            # order の解析
            order_str = arc_elem.get("order")
            order: float = 0.0
            if order_str is not None:
                try:
                    order = float(order_str)
                except ValueError:
                    warnings.warn(
                        f"定義リンク: order 値 '{order_str}' が不正です。0.0 を使用します",
                        EdinetWarning,
                        stacklevel=2,
                    )

            # usable の解析（全 arc 型から XML 属性を読み取り）
            # xs:boolean: "true"/"1" → True, "false"/"0" → False
            usable_str = arc_elem.get("usable")
            usable = usable_str not in ("false", "0") if usable_str is not None else True

            # closed / contextElement は all arcrole のみ
            closed: bool | None = None
            context_element: str | None = None
            if arcrole == _ARCROLE_ALL:
                closed_str = arc_elem.get(f"{{{NS_XBRLDT}}}closed")
                if closed_str is not None:
                    # xs:boolean: "true"/"1" → True, "false"/"0" → False
                    closed = closed_str in ("true", "1")
                context_element = arc_elem.get(
                    f"{{{NS_XBRLDT}}}contextElement"
                )

            arc_list.append(
                DefinitionArc(
                    from_concept=from_concept,
                    to_concept=to_concept,
                    from_href=from_href,
                    to_href=to_href,
                    arcrole=arcrole,
                    order=order,
                    closed=closed,
                    context_element=context_element,
                    usable=usable,
                )
            )

        logger.debug(
            "ロール %s: %d loc, %d arc",
            role_uri,
            len(loc_map),
            len(arc_list),
        )

        # 5. ハイパーキューブ構造化
        hypercubes = _build_hypercubes(arc_list)

        trees[role_uri] = DefinitionTree(
            role_uri=role_uri,
            arcs=tuple(arc_list),
            hypercubes=tuple(hypercubes),
        )

    total_hc = sum(len(t.hypercubes) for t in trees.values())
    logger.info(
        "定義リンクベースのパース完了: %d ロール, %d ハイパーキューブ",
        len(trees),
        total_hc,
    )

    return trees

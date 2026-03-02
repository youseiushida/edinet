"""Calculation Linkbase パーサー。

XBRL Calculation Linkbase (``_cal.xml``) をパースし、
科目間の加減算関係（親子・weight）を木構造として提供する。

下流の ``validation/calc_check``（Phase 9）や
``taxonomy/standard_mapping``（Phase 5）で利用される。

典型的な使い方::

    from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase

    lb = parse_calculation_linkbase(xml_bytes)
    for role_uri in lb.role_uris:
        tree = lb.get_tree(role_uri)
        for arc in tree.arcs:
            sign = "+" if arc.weight == 1 else "-"
            print(f"  {arc.parent} {sign}→ {arc.child}")
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Literal

from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl._linkbase_utils import extract_concept_from_href as _extract_concept_from_href
from edinet.xbrl._namespaces import NS_LINK, NS_XLINK

logger = logging.getLogger(__name__)

# ---------- 定数 ----------

ARCROLE_SUMMATION = "http://www.xbrl.org/2003/arcrole/summation-item"
"""summation-item arcrole URI。"""

# ========== データモデル ==========


@dataclass(frozen=True, slots=True)
class CalculationArc:
    """計算リンクベースの 1 本のアーク。

    親 concept から子 concept への加減算関係を表す。

    Attributes:
        parent: 親 concept のローカル名（例: ``"GrossProfit"``）。
        child: 子 concept のローカル名（例: ``"NetSales"``）。
        parent_href: 親 concept の xlink:href（元の値）。
        child_href: 子 concept の xlink:href（元の値）。
        weight: 加減算方向。``1`` が加算、``-1`` が減算。
        order: 同一親の下での表示順序。
        role_uri: 所属ロール URI。
    """

    parent: str
    child: str
    parent_href: str
    child_href: str
    weight: Literal[1, -1]
    order: float
    role_uri: str

    def __repr__(self) -> str:
        sign = "+" if self.weight == 1 else "-"
        return f"CalculationArc({self.parent} {sign}→ {self.child})"


@dataclass(frozen=True, slots=True)
class CalculationTree:
    """1 つの role URI 内の計算木。

    Attributes:
        role_uri: ロール URI。
        arcs: 全アークのタプル（パース順保持）。
        roots: 親のみで子でない concept のタプル（XML 初出順）。
    """

    role_uri: str
    arcs: tuple[CalculationArc, ...]
    roots: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            f"CalculationTree(role_uri={self.role_uri!r}, "
            f"arcs={len(self.arcs)}, roots={self.roots})"
        )


@dataclass(frozen=True, slots=True)
class CalculationLinkbase:
    """計算リンクベースのパース結果全体。

    Attributes:
        source_path: ソースファイルパス（エラーメッセージ用）。
        trees: role_uri → CalculationTree の辞書。
    """

    source_path: str | None
    trees: dict[str, CalculationTree]
    _children_index: dict[tuple[str, str], tuple[CalculationArc, ...]] = field(
        init=False, repr=False, compare=False,
    )
    _parent_index: dict[tuple[str, str], tuple[CalculationArc, ...]] = field(
        init=False, repr=False, compare=False,
    )

    def __repr__(self) -> str:
        return (
            f"CalculationLinkbase(roles={len(self.trees)}, "
            f"arcs={sum(len(t.arcs) for t in self.trees.values())})"
        )

    def __post_init__(self) -> None:
        """内部インデックスを構築する。"""
        object.__setattr__(self, "_children_index", self._build_children_index())
        object.__setattr__(self, "_parent_index", self._build_parent_index())

    def _build_children_index(
        self,
    ) -> dict[tuple[str, str], tuple[CalculationArc, ...]]:
        """子インデックスを構築する。

        Returns:
            ``(role_uri, parent)`` → アークのタプル（order 昇順ソート済み）。
        """
        index: dict[tuple[str, str], list[CalculationArc]] = {}
        for tree in self.trees.values():
            for arc in tree.arcs:
                key = (arc.role_uri, arc.parent)
                index.setdefault(key, []).append(arc)
        return {
            k: tuple(sorted(v, key=lambda a: a.order)) for k, v in index.items()
        }

    def _build_parent_index(
        self,
    ) -> dict[tuple[str, str], tuple[CalculationArc, ...]]:
        """親インデックスを構築する。

        Returns:
            ``(role_uri, child)`` → アークのタプル（パース順保持）。
        """
        index: dict[tuple[str, str], list[CalculationArc]] = {}
        for tree in self.trees.values():
            for arc in tree.arcs:
                key = (arc.role_uri, arc.child)
                index.setdefault(key, []).append(arc)
        return {k: tuple(v) for k, v in index.items()}

    @property
    def role_uris(self) -> tuple[str, ...]:
        """全ロール URI のタプルを返す。

        Returns:
            ロール URI のタプル。
        """
        return tuple(self.trees.keys())

    def get_tree(self, role_uri: str) -> CalculationTree | None:
        """指定ロールの計算木を返す。

        Args:
            role_uri: ロール URI。

        Returns:
            CalculationTree。存在しない場合は ``None``。
        """
        return self.trees.get(role_uri)

    def children_of(
        self,
        parent: str,
        *,
        role_uri: str | None = None,
    ) -> tuple[CalculationArc, ...]:
        """指定 concept の子アークを返す。

        Args:
            parent: 親 concept のローカル名。
            role_uri: ロール URI。``None`` の場合は全ロールを横断する。

        Returns:
            子アークのタプル。role_uri 指定時は order 昇順、
            ``None`` 時は ``(role_uri, order)`` 昇順。
        """
        if role_uri is not None:
            return self._children_index.get((role_uri, parent), ())

        # 全ロール横断: O(R) 走査（R は典型的に 8 程度）
        result: list[CalculationArc] = []
        for tree in self.trees.values():
            result.extend(
                self._children_index.get((tree.role_uri, parent), ())
            )
        result.sort(key=lambda a: (a.role_uri, a.order))
        return tuple(result)

    def parent_of(
        self,
        child: str,
        *,
        role_uri: str | None = None,
    ) -> tuple[CalculationArc, ...]:
        """指定 concept の親アークを返す。

        Args:
            child: 子 concept のローカル名。
            role_uri: ロール URI。``None`` の場合は全ロールを横断する。

        Returns:
            親アークのタプル。
        """
        if role_uri is not None:
            return self._parent_index.get((role_uri, child), ())

        # 全ロール横断: O(R) 走査（R は典型的に 8 程度）
        result: list[CalculationArc] = []
        for tree in self.trees.values():
            result.extend(
                self._parent_index.get((tree.role_uri, child), ())
            )
        result.sort(key=lambda a: (a.role_uri, a.order))
        return tuple(result)

    def ancestors_of(
        self,
        concept: str,
        *,
        role_uri: str,
    ) -> tuple[str, ...]:
        """指定 concept の祖先を根まで辿って返す。

        ``_parent_index`` を辿り、複数親がある場合は先頭を辿る。
        循環は ``visited`` で防御する。

        Args:
            concept: 起点 concept のローカル名。
            role_uri: ロール URI。

        Returns:
            祖先 concept のタプル（近い順）。ルート concept が末尾。
        """
        ancestors: list[str] = []
        visited: set[str] = {concept}
        current = concept

        while True:
            parent_arcs = self._parent_index.get((role_uri, current))
            if not parent_arcs:
                break
            parent = parent_arcs[0].parent
            if parent in visited:
                break
            visited.add(parent)
            ancestors.append(parent)
            current = parent

        return tuple(ancestors)


# ========== 公開 API ==========


def parse_calculation_linkbase(
    xml_bytes: bytes,
    *,
    source_path: str | None = None,
) -> CalculationLinkbase:
    """Calculation Linkbase の XML bytes をパースする。

    Args:
        xml_bytes: ``_cal.xml`` の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。

    Returns:
        パース結果の CalculationLinkbase。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
    # 1. XML パース
    try:
        root = etree.fromstring(xml_bytes)  # noqa: S320
    except etree.XMLSyntaxError as e:
        path_info = f": {source_path}" if source_path else ""
        raise EdinetParseError(
            f"計算リンクベースの XML パースに失敗しました{path_info}"
        ) from e

    # 2. calculationLink 要素を走査
    calc_links = root.findall(f"{{{NS_LINK}}}calculationLink")
    logger.debug(
        "計算リンクベースをパース中: %d calculationLink 要素", len(calc_links)
    )

    trees: dict[str, CalculationTree] = {}

    for calc_link in calc_links:
        role_uri = calc_link.get(f"{{{NS_XLINK}}}role")
        if not role_uri:
            warnings.warn(
                "計算リンク: xlink:role が未設定のためスキップします",
                EdinetWarning,
                stacklevel=2,
            )
            continue

        # 3. loc マップ構築: {xlink:label: (concept_local_name, href)}
        loc_map: dict[str, tuple[str, str]] = {}
        for loc_elem in calc_link.findall(f"{{{NS_LINK}}}loc"):
            label = loc_elem.get(f"{{{NS_XLINK}}}label")
            href = loc_elem.get(f"{{{NS_XLINK}}}href")
            if not label or not href:
                continue

            if "#" not in href:
                warnings.warn(
                    f"計算リンク: loc の href にフラグメントがありません: '{href}'",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            concept = _extract_concept_from_href(href)
            if concept is None:
                warnings.warn(
                    f"計算リンク: loc の href からコンセプト名を抽出できません: '{href}'",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            loc_map[label] = (concept, href)

        logger.debug("ロール %s: %d loc", role_uri, len(loc_map))

        # 4. calculationArc → CalculationArc に変換
        arc_list: list[CalculationArc] = []
        parent_set: list[str] = []  # 初出順保持用
        child_set: set[str] = set()
        parent_seen: set[str] = set()

        for arc_elem in calc_link.findall(f"{{{NS_LINK}}}calculationArc"):
            # arcrole 検証
            arcrole = arc_elem.get(f"{{{NS_XLINK}}}arcrole", "")
            if arcrole != ARCROLE_SUMMATION:
                warnings.warn(
                    f"計算リンク: 未知の arcrole '{arcrole}' をスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            from_label = arc_elem.get(f"{{{NS_XLINK}}}from")
            to_label = arc_elem.get(f"{{{NS_XLINK}}}to")
            if not from_label or not to_label:
                continue

            # loc_map から concept を解決
            if from_label not in loc_map:
                warnings.warn(
                    f"計算リンク: 不明なロケーター参照 '{from_label}' をスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue
            if to_label not in loc_map:
                warnings.warn(
                    f"計算リンク: 不明なロケーター参照 '{to_label}' をスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            parent_concept, parent_href = loc_map[from_label]
            child_concept, child_href = loc_map[to_label]

            # weight の解析（直接属性、xlink 名前空間ではない）
            weight_str = arc_elem.get("weight")
            if weight_str is None:
                warnings.warn(
                    "計算リンク: weight 属性が未設定のためスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            try:
                weight_float = float(weight_str)
            except ValueError:
                warnings.warn(
                    f"計算リンク: weight 値 '{weight_str}' が不正なためスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            if weight_float not in (1.0, -1.0):
                warnings.warn(
                    f"計算リンク: weight 値 '{weight_str}' は 1 または -1 "
                    f"でないためスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )
                continue

            weight: Literal[1, -1] = 1 if weight_float == 1.0 else -1

            # order の解析（直接属性）
            order_str = arc_elem.get("order")
            order: float = 0.0
            if order_str is not None:
                try:
                    order = float(order_str)
                except ValueError:
                    warnings.warn(
                        f"計算リンク: order 値 '{order_str}' が不正です。"
                        f"0.0 を使用します",
                        EdinetWarning,
                        stacklevel=2,
                    )
            else:
                logger.debug("計算リンク: order 属性が未設定です。0.0 を使用します")

            arc_list.append(
                CalculationArc(
                    parent=parent_concept,
                    child=child_concept,
                    parent_href=parent_href,
                    child_href=child_href,
                    weight=weight,
                    order=order,
                    role_uri=role_uri,
                )
            )

            # roots 算出用にトラッキング
            if parent_concept not in parent_seen:
                parent_seen.add(parent_concept)
                parent_set.append(parent_concept)
            child_set.add(child_concept)

        # 5. roots 算出: 親集合 - 子集合（初出順保持）
        roots = tuple(p for p in parent_set if p not in child_set)

        trees[role_uri] = CalculationTree(
            role_uri=role_uri,
            arcs=tuple(arc_list),
            roots=roots,
        )

        logger.debug(
            "ロール %s: %d arc, %d root",
            role_uri,
            len(arc_list),
            len(roots),
        )

    logger.info(
        "計算リンクベースのパース完了: %d ロール, %d アーク",
        len(trees),
        sum(len(t.arcs) for t in trees.values()),
    )

    return CalculationLinkbase(
        source_path=source_path,
        trees=trees,
    )

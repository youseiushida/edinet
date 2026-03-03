"""標準/非標準科目の分類と親標準科目の推定。

各 LineItem が EDINET 標準タクソノミに属するか、提出者別タクソノミ
（企業固有の拡張科目）に属するかを判別する。非標準科目については
Definition Linkbase の general-special arcrole を用いて「どの標準科目の
特殊化か」を推定する。

D3（LineItem 拡張ポリシー）により LineItem にフィールドは追加せず、
分類結果は ``CustomDetectionResult`` dataclass で返す。

Example:
    基本的な使い方::

        from edinet.xbrl.taxonomy.custom import detect_custom_items

        result = detect_custom_items(statements)
        print(f"拡張科目率: {result.custom_ratio:.1%}")

    DefinitionLinkbase との連携（親標準科目推定）::

        from edinet.xbrl.linkbase.definition import parse_definition_linkbase
        from edinet.xbrl.taxonomy.custom import detect_custom_items

        def_trees = parse_definition_linkbase(def_xml_bytes)
        result = detect_custom_items(statements, definition_linkbase=def_trees)
        for ci in result.custom_items:
            if ci.parent_standard_concept:
                print(f"  {ci.item.local_name} → 親: {ci.parent_standard_concept}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from edinet.models.financial import LineItem
from edinet.xbrl._namespaces import (
    NamespaceInfo,
    classify_namespace,
    is_standard_taxonomy,
)
from edinet.xbrl.linkbase.calculation import (
    CalculationLinkbase,
)
from edinet.xbrl.linkbase.definition import DefinitionTree
from edinet.financial.statements import Statements

# ============================================================
# 定数
# ============================================================

_ARCROLE_GENERAL_SPECIAL = "http://www.xbrl.org/2003/arcrole/general-special"
"""general-special arcrole URI。

E-6.a.md の調査結果より、wider-narrower arcrole は EDINET で使用されていない
（0 インスタンス）。general-special のみを対象とする。
"""

_FILER_XSD_RE = re.compile(r"jpcrp\d+")
"""提出者別タクソノミの XSD ファイル名パターン。

例:
    - ``"jpcrp030000-asr-001_E02144-000.xsd"`` → 一致（提出者）
    - ``"jppfs_cor_2025-11-01.xsd"`` → 不一致（標準）
    - ``"jpcrp_cor_2025-11-01.xsd"`` → 不一致（標準: ``jpcrp_cor`` は
      ``jpcrp\\d+`` に一致しない）
"""


# ============================================================
# データクラス
# ============================================================


@dataclass(frozen=True, slots=True)
class _CalcMappingResult:
    """CalculationLinkbase ベースのマッピング結果（内部用）。

    Attributes:
        ancestor: summation-item 由来の最近接標準科目のローカル名。
            標準科目が見つからない場合は None。
        path: 非標準科目からの経路（ローカル名のタプル）。
        role_uri: マッピングが特定された role URI。
    """

    ancestor: str | None
    path: tuple[str, ...]
    role_uri: str


@dataclass(frozen=True, slots=True)
class CustomItemInfo:
    """非標準（拡張）科目の分析結果。

    Attributes:
        item: 元の LineItem への参照。
        namespace_info: 名前空間の分類結果（カテゴリ、EDINET コード等）。
        parent_standard_concept: general-special arcrole で推定した
            親標準科目のローカル名。DefinitionLinkbase が未指定、
            または該当する関係がない場合は None。
        calculation_ancestor: Calculation Linkbase (summation-item) 由来の
            最近接標準科目のローカル名。CalculationLinkbase が未指定、
            または該当する計算関係がない場合は None。
        calculation_path: 非標準科目から calculation_ancestor までの経路
            （ローカル名のタプル）。先頭が非標準科目、末尾が
            calculation_ancestor。calculation_ancestor が None の場合は
            ルートまでの経路。CalculationLinkbase が未指定の場合は None。
        calculation_role_uri: マッピングが特定された Calculation Linkbase の
            role URI。CalculationLinkbase が未指定の場合は None。
    """

    item: LineItem
    namespace_info: NamespaceInfo
    parent_standard_concept: str | None

    calculation_ancestor: str | None = None
    calculation_path: tuple[str, ...] | None = None
    calculation_role_uri: str | None = None


@dataclass(frozen=True, slots=True)
class CustomDetectionResult:
    """標準/非標準科目の分類結果。

    Attributes:
        custom_items: 非標準科目の分析結果タプル。
        standard_items: 標準科目の LineItem タプル。
        custom_ratio: 非標準科目の割合（0.0〜1.0）。
            全科目数が 0 の場合は 0.0。Fact 単位の割合であり、
            ユニーク concept 数ベースの割合ではない。
        total_count: 全科目数（custom + standard）。
    """

    custom_items: tuple[CustomItemInfo, ...]
    standard_items: tuple[LineItem, ...]
    custom_ratio: float
    total_count: int


# ============================================================
# 公開関数
# ============================================================


def detect_custom_items(
    statements: Statements,
    *,
    definition_linkbase: dict[str, DefinitionTree] | None = None,
    calculation_linkbase: CalculationLinkbase | None = None,
) -> CustomDetectionResult:
    """各 LineItem を標準/非標準に分類する。

    Statements 内の全 LineItem について、名前空間 URI を基に
    標準タクソノミか提出者別タクソノミかを判定する。
    非標準科目については NamespaceInfo と、Definition Linkbase が
    利用可能な場合は親標準科目の推定結果を付与する。

    Calculation Linkbase が指定された場合は、summation-item arcrole を
    辿って「どの標準科目の計算内訳か」も推定する。

    Note:
        本関数は XBRL インスタンス内の Fact（LineItem）のみを対象とする。
        タクソノミ定義上の abstract 要素（domainItemType のセグメント Member 等）は
        XBRL インスタンスに Fact として出現しないため検出対象外である。

        同一 concept が複数の期間・次元に出現する場合、各 Fact は独立にカウント
        される。custom_ratio は Fact 単位の割合であり、ユニーク concept 数ベース
        の割合ではない。concept レベルの割合が必要な場合は
        ``{ci.item.local_name for ci in result.custom_items}`` で重複除去すること。

    Args:
        statements: build_statements() で構築した Statements。
        definition_linkbase: parse_definition_linkbase() の戻り値。
            指定した場合、general-special arcrole を用いて
            拡張科目の親標準科目を推定する。None の場合は推定しない。
        calculation_linkbase: parse_calculation_linkbase() の戻り値。
            指定した場合、summation-item arcrole を用いて
            拡張科目の計算上の最近接標準科目を推定する。
            None の場合は推定しない。

    Returns:
        CustomDetectionResult。
    """
    custom: list[CustomItemInfo] = []
    standard: list[LineItem] = []

    # DefinitionLinkbase から逆引きインデックスを構築（optional）
    parent_index = _build_parent_index(definition_linkbase)

    # CalculationLinkbase から逆引きインデックスを構築（optional）
    calc_index = _build_calculation_index(calculation_linkbase)

    # Statements の公開イテレーションプロトコル（__iter__）でアクセスする。
    # _items への直接アクセスはリファクタリング耐性を損なうため避ける。
    for item in statements:
        if is_standard_taxonomy(item.namespace_uri):
            standard.append(item)
        else:
            ns_info = classify_namespace(item.namespace_uri)
            parent = parent_index.get(item.local_name)
            calc = calc_index.get(item.local_name)
            custom.append(
                CustomItemInfo(
                    item=item,
                    namespace_info=ns_info,
                    parent_standard_concept=parent,
                    calculation_ancestor=calc.ancestor if calc else None,
                    calculation_path=calc.path if calc else None,
                    calculation_role_uri=calc.role_uri if calc else None,
                )
            )

    total = len(custom) + len(standard)
    ratio = len(custom) / total if total > 0 else 0.0

    return CustomDetectionResult(
        custom_items=tuple(custom),
        standard_items=tuple(standard),
        custom_ratio=ratio,
        total_count=total,
    )


def find_custom_concepts(
    calc_linkbase: CalculationLinkbase,
) -> tuple[str, ...]:
    """Calculation Linkbase 内の全非標準科目を自動検出する。

    全 CalculationArc の parent/child の href を走査し、
    提出者タクソノミに属する concept を抽出する。

    Args:
        calc_linkbase: パース済みの CalculationLinkbase。

    Returns:
        非標準科目ローカル名のタプル（重複除去・ソート済み）。
    """
    return tuple(sorted(_find_custom_in_calc(calc_linkbase)))


# ============================================================
# 内部関数
# ============================================================


def _find_custom_in_calc(calc_linkbase: CalculationLinkbase) -> set[str]:
    """CalculationLinkbase 内の全非標準科目を検出する（内部用）。

    全ロールの全 CalculationArc を走査し、child_href / parent_href が
    提出者タクソノミの XSD を参照している concept を収集する。

    Args:
        calc_linkbase: パース済みの CalculationLinkbase。

    Returns:
        非標準科目ローカル名の集合。
    """
    custom: set[str] = set()
    for tree in calc_linkbase.trees.values():
        for arc in tree.arcs:
            if not _is_standard_href(arc.child_href):
                custom.add(arc.child)
            if not _is_standard_href(arc.parent_href):
                custom.add(arc.parent)
    return custom


def _build_calculation_index(
    calculation_linkbase: CalculationLinkbase | None,
) -> dict[str, _CalcMappingResult]:
    """CalculationLinkbase の summation-item を辿り、全非標準科目のマッピングを構築する。

    各非標準科目について parent_of() で 1 段ずつ祖先を辿り、
    CalculationArc.parent_href から _is_standard_href() で
    標準/非標準を判定する。最初に標準科目が見つかった時点で停止する。

    Args:
        calculation_linkbase: パース済みの CalculationLinkbase。
            None の場合は空辞書を返す。

    Returns:
        非標準科目ローカル名 → _CalcMappingResult の辞書。
    """
    if calculation_linkbase is None:
        return {}

    custom_concepts = _find_custom_in_calc(calculation_linkbase)
    result: dict[str, _CalcMappingResult] = {}

    for concept in custom_concepts:
        for role_uri in calculation_linkbase.role_uris:
            path: list[str] = [concept]
            standard_ancestor: str | None = None
            current = concept
            visited: set[str] = {concept}

            while True:
                parent_arcs = calculation_linkbase.parent_of(
                    current, role_uri=role_uri,
                )
                if not parent_arcs:
                    break  # ルートに到達
                arc = parent_arcs[0]
                parent = arc.parent
                if parent in visited:
                    break  # 循環検出
                visited.add(parent)
                path.append(parent)

                if _is_standard_href(arc.parent_href):
                    standard_ancestor = parent
                    break  # 最も近い標準科目で停止

                current = parent

            if standard_ancestor is not None or len(path) > 1:
                result[concept] = _CalcMappingResult(
                    ancestor=standard_ancestor,
                    path=tuple(path),
                    role_uri=role_uri,
                )
                if standard_ancestor is not None:
                    break  # 最初に標準科目が見つかった role を採用

    return result


def _is_standard_href(href: str) -> bool:
    """DefinitionArc の href が標準タクソノミの XSD を参照しているか判定する。

    提出者別タクソノミの XSD ファイル名は ``jpcrp`` + 数字で始まるパターンを持つ
    （例: ``jpcrp030000-asr-001_E02144-000.xsd``）。このパターンに一致しなければ
    標準タクソノミと判定する。

    Args:
        href: ``DefinitionArc.from_href`` または ``to_href``。
            形式: ``"../jppfs_cor_2025-11-01.xsd#NetSales"`` 等。

    Returns:
        標準タクソノミの XSD を参照している場合 True。
    """
    # href からファイル名部分を抽出（"#" より前、最後の "/" より後）
    path_part = href.split("#")[0] if "#" in href else href
    filename = path_part.rsplit("/", 1)[-1] if "/" in path_part else path_part
    # 空文字列やフラグメントのみの href は標準として扱う（保守的判定）。
    return not bool(_FILER_XSD_RE.match(filename))


def _build_parent_index(
    definition_linkbase: dict[str, DefinitionTree] | None,
) -> dict[str, str]:
    """DefinitionLinkbase の general-special arcrole から逆引きインデックスを構築する。

    general-special arc は from_concept（general/親）→ to_concept（special/子）の
    方向で定義される。これを逆引きし、to_concept → 最も近い標準タクソノミ親概念の
    マッピングを返す。

    親が標準タクソノミに属さない場合（提出者別同士の general-special）はさらに
    親を辿り、標準タクソノミに到達した最初の概念を返す。

    Args:
        definition_linkbase: parse_definition_linkbase() の戻り値。
            None の場合は空辞書を返す。

    Returns:
        to_concept → 最も近い標準タクソノミ親概念のローカル名。
    """
    if definition_linkbase is None:
        return {}

    # Step 1: general-special arc の情報を収集
    # child → [(parent_concept, parent_href), ...] の逆引きマップ
    child_to_parents: dict[str, list[tuple[str, str]]] = {}
    for tree in definition_linkbase.values():
        for arc in tree.arcs:
            if arc.arcrole == _ARCROLE_GENERAL_SPECIAL:
                child_to_parents.setdefault(arc.to_concept, []).append(
                    (arc.from_concept, arc.from_href),
                )

    # Step 2: 各 child について、標準タクソノミに属する最も近い祖先を探す
    result: dict[str, str] = {}
    for child in child_to_parents:
        ancestor = _find_standard_ancestor(child, child_to_parents)
        if ancestor is not None:
            result[child] = ancestor

    return result


def _find_standard_ancestor(
    concept: str,
    child_to_parents: dict[str, list[tuple[str, str]]],
    *,
    _visited: set[str] | None = None,
) -> str | None:
    """general-special 関係を辿り、標準タクソノミに属する最も近い祖先を返す。

    ``DefinitionArc.from_href`` の XSD ファイル名パターンで標準/非標準を判定し、
    最初に標準タクソノミと判定された親概念を返す。直接の親が全て非標準の場合は
    さらに祖先を再帰的に辿る。

    Args:
        concept: 起点の concept ローカル名。
        child_to_parents: 全体の逆引きマップ。
            各エントリは ``(parent_concept, parent_href)`` のタプルリスト。
        _visited: 循環検出用の内部引数。

    Returns:
        標準タクソノミに属する最も近い祖先のローカル名。見つからない場合は None。
    """
    if _visited is None:
        _visited = set()
    _visited.add(concept)

    parents = child_to_parents.get(concept, [])
    for parent_concept, parent_href in parents:
        if parent_concept in _visited:
            continue  # 循環防止

        # from_href の XSD パターンで標準/非標準を判定
        if _is_standard_href(parent_href):
            return parent_concept

        # 親も非標準の場合、さらに祖先を辿る
        result = _find_standard_ancestor(
            parent_concept,
            child_to_parents,
            _visited=_visited,
        )
        if result is not None:
            return result

    return None

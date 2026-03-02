"""J-4. 連結子会社・関連会社の concept 検索スクリプト。

実行方法: EDINET_TAXONOMY_ROOT=... uv run docs/QAs/scripts/J-4.subsidiary_concepts.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: jpcrp_cor から Subsidiary, Consolidat, EquityMethod, Associate 関連 element を抽出。
      dimension axis の有無を確認。
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "xbrli": "http://www.xbrl.org/2003/instance",
}

JPCRP_COR = (
    TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01" / "jpcrp_cor_2025-11-01.xsd"
)

# 検索パターン（大文字小文字区別なし）
SEARCH_PATTERNS = [
    "Subsidiary",
    "Consolidat",
    "EquityMethod",
    "Associate",
    "Affiliate",
]


@dataclass
class Concept:
    """XSD element 要素の情報。"""

    name: str
    element_id: str
    xbrl_type: str
    abstract: bool
    period_type: str
    substitution_group: str


def parse_concepts(xsd_path: Path) -> list[Concept]:
    """XSD ファイルから全 xsd:element を抽出する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        Concept のリスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    concepts: list[Concept] = []
    for elem in root.findall(f"{{{NS['xsd']}}}element"):
        name = elem.get("name", "")
        element_id = elem.get("id", "")
        xbrl_type = elem.get("type", "")
        abstract = elem.get("abstract", "false") == "true"
        period_type = elem.get(f"{{{NS['xbrli']}}}periodType", "")
        substitution_group = elem.get("substitutionGroup", "")

        concepts.append(
            Concept(
                name=name,
                element_id=element_id,
                xbrl_type=xbrl_type,
                abstract=abstract,
                period_type=period_type,
                substitution_group=substitution_group,
            )
        )

    return concepts


def simplify_type(xbrl_type: str) -> str:
    """型名を簡略化する（プレフィックス除去）。

    Args:
        xbrl_type: 完全修飾型名。

    Returns:
        簡略化された型名。
    """
    if ":" in xbrl_type:
        return xbrl_type.split(":")[-1]
    return xbrl_type


def matches_pattern(name: str) -> list[str]:
    """concept 名が検索パターンのいずれかにマッチするかを返す。

    Args:
        name: concept 名。

    Returns:
        マッチしたパターンのリスト。
    """
    matched = []
    for pattern in SEARCH_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            matched.append(pattern)
    return matched


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("J-4. 連結子会社・関連会社の concept 検索")
    print("=" * 80)

    print(f"\nファイル: {JPCRP_COR}")
    all_concepts = parse_concepts(JPCRP_COR)
    print(f"全 concept 数: {len(all_concepts)}")

    # パターンマッチで子会社・関連会社関連を抽出
    matched_concepts: list[tuple[Concept, list[str]]] = []
    for c in all_concepts:
        patterns = matches_pattern(c.name)
        if patterns:
            matched_concepts.append((c, patterns))

    print(f"\n子会社・関連会社関連 concept 数: {len(matched_concepts)}")
    abstract_count = sum(1 for c, _ in matched_concepts if c.abstract)
    concrete_count = len(matched_concepts) - abstract_count
    print(f"  abstract: {abstract_count}")
    print(f"  concrete: {concrete_count}")

    # --- Section 1: Axis 要素の確認 ---
    print("\n" + "=" * 80)
    print("【1. Axis 要素の確認】")
    print("=" * 80)

    axis_concepts = [
        (c, p) for c, p in matched_concepts if "Axis" in c.name
    ]
    if axis_concepts:
        print(f"\nAxis 要素: {len(axis_concepts)} 件")
        for c, p in axis_concepts:
            simple_type = simplify_type(c.xbrl_type)
            print(
                f"  {c.name:<70s} type={simple_type:<25s} "
                f"abstract={c.abstract} period={c.period_type}"
            )
    else:
        print("\nAxis 要素: なし")

    # 全 concept から Axis を検索（子会社関連以外も含めて確認）
    all_axis = [c for c in all_concepts if "Axis" in c.name]
    print(f"\n全 Axis 要素（jpcrp_cor 全体）: {len(all_axis)} 件")
    for c in all_axis:
        simple_type = simplify_type(c.xbrl_type)
        # 子会社関連かどうかマーク
        marker = " ★子会社関連" if matches_pattern(c.name) else ""
        print(f"  {c.name:<70s} type={simple_type}{marker}")

    # --- Section 2: パターン別集計 ---
    print("\n" + "=" * 80)
    print("【2. 検索パターン別集計】")
    print("=" * 80)

    pattern_counter: dict[str, list[Concept]] = defaultdict(list)
    for c, patterns in matched_concepts:
        for p in patterns:
            pattern_counter[p].append(c)

    for pattern in SEARCH_PATTERNS:
        concepts_for_pattern = pattern_counter.get(pattern, [])
        print(f"\n  {pattern}: {len(concepts_for_pattern)} 件")
        for c in concepts_for_pattern[:5]:
            simple_type = simplify_type(c.xbrl_type)
            print(f"    - {c.name} (type={simple_type}, abstract={c.abstract})")
        if len(concepts_for_pattern) > 5:
            print(f"    ... 残り {len(concepts_for_pattern) - 5} 件")

    # --- Section 3: 型別グルーピング ---
    print("\n" + "=" * 80)
    print("【3. 型別グルーピング（concrete のみ）】")
    print("=" * 80)

    concrete_matched = [(c, p) for c, p in matched_concepts if not c.abstract]
    type_groups: dict[str, list[Concept]] = defaultdict(list)
    for c, _ in concrete_matched:
        simple_type = simplify_type(c.xbrl_type)
        type_groups[simple_type].append(c)

    for t in sorted(type_groups.keys(), key=lambda x: len(type_groups[x]), reverse=True):
        concepts_in_group = type_groups[t]
        pct = len(concepts_in_group) / len(concrete_matched) * 100 if concrete_matched else 0
        print(f"\n  {t}: {len(concepts_in_group)} 件 ({pct:.1f}%)")
        for c in concepts_in_group[:10]:
            print(f"    - {c.name} (period={c.period_type})")
        if len(concepts_in_group) > 10:
            print(f"    ... 残り {len(concepts_in_group) - 10} 件")

    # --- Section 4: 構造化データ（数値型）の詳細 ---
    print("\n" + "=" * 80)
    print("【4. 構造化データ（非 textBlock 型、concrete のみ）の詳細】")
    print("=" * 80)

    structured_types = {
        "monetaryItemType",
        "nonNegativeIntegerItemType",
        "percentItemType",
        "sharesItemType",
        "perShareItemType",
        "decimalItemType",
        "integerItemType",
        "booleanItemType",
        "dateItemType",
    }

    structured_concepts = [
        c
        for c, _ in concrete_matched
        if simplify_type(c.xbrl_type) in structured_types
    ]

    if structured_concepts:
        print(f"\n構造化数値型 concept: {len(structured_concepts)} 件")
        for c in structured_concepts:
            simple_type = simplify_type(c.xbrl_type)
            print(
                f"  {c.name:<70s} type={simple_type:<30s} period={c.period_type}"
            )
    else:
        print("\n構造化数値型 concept: なし")

    # --- Section 5: 全 concrete 要素の一覧 ---
    print("\n" + "=" * 80)
    print("【5. 全 concrete 要素一覧（子会社・関連会社関連）】")
    print("=" * 80)

    for c, patterns in matched_concepts:
        if not c.abstract:
            simple_type = simplify_type(c.xbrl_type)
            print(
                f"  {c.name:<75s} type={simple_type:<30s} "
                f"period={c.period_type:<10s} patterns={','.join(patterns)}"
            )

    # --- Section 6: SubstitutionGroup 別集計 ---
    print("\n" + "=" * 80)
    print("【6. substitutionGroup 別集計】")
    print("=" * 80)

    sg_counter = Counter(c.substitution_group for c, _ in matched_concepts)
    for sg, count in sg_counter.most_common():
        print(f"  {sg:<50s}: {count:>5d}")

    # --- Section 7: サマリ ---
    print("\n" + "=" * 80)
    print("【サマリ】")
    print("=" * 80)
    print(f"  全 concept 数: {len(all_concepts)}")
    print(f"  子会社・関連会社関連: {len(matched_concepts)} 件")
    print(f"    abstract: {abstract_count}")
    print(f"    concrete: {concrete_count}")

    type_summary = Counter(
        simplify_type(c.xbrl_type) for c, _ in matched_concepts if not c.abstract
    )
    print(f"\n  concrete の型別内訳:")
    for t, count in type_summary.most_common():
        print(f"    {t:<35s}: {count:>5d}")

    axis_related = [c for c in all_axis if matches_pattern(c.name)]
    print(f"\n  子会社関連 Axis 要素: {len(axis_related)} 件")
    print(f"  全 Axis 要素（jpcrp_cor）: {len(all_axis)} 件")

    # Dimension Member の確認
    member_concepts = [
        (c, p)
        for c, p in matched_concepts
        if "Member" in c.name or simplify_type(c.xbrl_type) == "domainItemType"
    ]
    print(f"\n  子会社関連 Member/Domain 要素: {len(member_concepts)} 件")
    for c, p in member_concepts[:10]:
        simple_type = simplify_type(c.xbrl_type)
        print(f"    - {c.name} (type={simple_type})")
    if len(member_concepts) > 10:
        print(f"    ... 残り {len(member_concepts) - 10} 件")


if __name__ == "__main__":
    main()

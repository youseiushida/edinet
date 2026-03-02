"""E-1b. jpcrp_cor concept のタイプ別分類スクリプト

実行方法: uv run docs/QAs/scripts/E-1b.jpcrp_concepts.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: jpcrp_cor_2025-11-01.xsd の全 concept を type 別に分類し、非財務データの種類を推定
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

JPCRP_COR = TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01" / "jpcrp_cor_2025-11-01.xsd"


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

        concepts.append(Concept(
            name=name,
            element_id=element_id,
            xbrl_type=xbrl_type,
            abstract=abstract,
            period_type=period_type,
            substitution_group=substitution_group,
        ))

    return concepts


def simplify_type(xbrl_type: str) -> str:
    """型名を簡略化する。

    Args:
        xbrl_type: 完全修飾型名。

    Returns:
        簡略化された型名。
    """
    # プレフィックスを除去
    if ":" in xbrl_type:
        return xbrl_type.split(":")[-1]
    return xbrl_type


def infer_content_category(name: str) -> str:
    """concept 名から内容カテゴリを推定する。

    Args:
        name: concept 名。

    Returns:
        推定カテゴリ名。
    """
    categories = [
        ("Employee|NumberOfEmployees|AverageAnnualSalary|worker|labor", "従業員情報"),
        ("Dividend|DividendPer", "配当情報"),
        ("Director|Officer|Auditor|BoardMember|ExecutiveOfficer", "役員情報"),
        ("Governance|CorporateGovernance", "ガバナンス"),
        ("MajorShareholder|LargestShareholder", "大株主情報"),
        ("Compensation|Remuneration|BoardCompensation", "報酬情報"),
        ("BusinessDescription|BusinessOutline|Overview", "事業概要"),
        ("Risk|BusinessRisk", "リスク情報"),
        ("Research|Development|RAndD", "研究開発"),
        ("Capital|CapitalExpenditure|Facility|Equipment", "設備投資"),
        ("Stock|Share|Treasury", "株式情報"),
        ("Segment|OperatingSegment", "セグメント情報"),
        ("Consolidated|Subsidiary|Affiliate", "連結・関連会社"),
        ("Accounting|AccountingPolicy|SignificantAccounting", "会計方針"),
        ("CoverPage|Filing|Document|Submission", "表紙・書類情報"),
        ("Order|Ordinance|Form|Heading", "府令様式"),
    ]

    for pattern, category in categories:
        if re.search(pattern, name, re.IGNORECASE):
            return category

    return "その他"


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("E-1b. jpcrp_cor concept タイプ別分類")
    print("=" * 80)

    print(f"\nファイル: {JPCRP_COR}")
    concepts = parse_concepts(JPCRP_COR)
    print(f"合計 concept 数: {len(concepts)}")

    # abstract vs concrete
    abstract_count = sum(1 for c in concepts if c.abstract)
    concrete_count = len(concepts) - abstract_count
    print(f"  abstract: {abstract_count}")
    print(f"  concrete: {concrete_count}")

    # type 別集計
    print("\n" + "=" * 80)
    print("【type 別集計】")
    print("=" * 80)
    type_counter = Counter(simplify_type(c.xbrl_type) for c in concepts)
    for t, count in type_counter.most_common():
        pct = count / len(concepts) * 100
        print(f"  {t:<40s}: {count:>5d} ({pct:>5.1f}%)")

    # textBlockItemType の concept を列挙（HTML ブロック = 非財務のテキスト記述）
    print("\n" + "=" * 80)
    print("【textBlockItemType の concept（HTML ブロック）— 上位30件】")
    print("=" * 80)
    text_blocks = [c for c in concepts if "textblock" in c.xbrl_type.lower()]
    print(f"合計: {len(text_blocks)} 件")
    for c in text_blocks[:30]:
        print(f"  {c.name}")
    if len(text_blocks) > 30:
        print(f"  ... 残り {len(text_blocks) - 30} 件")

    # monetaryItemType の concept
    print("\n" + "=" * 80)
    print("【monetaryItemType の concept — 上位30件】")
    print("=" * 80)
    monetary = [c for c in concepts if "monetary" in c.xbrl_type.lower()]
    print(f"合計: {len(monetary)} 件")
    for c in monetary[:30]:
        print(f"  {c.name}")
    if len(monetary) > 30:
        print(f"  ... 残り {len(monetary) - 30} 件")

    # stringItemType の concept
    print("\n" + "=" * 80)
    print("【stringItemType の concept（abstract 除く）— 上位20件】")
    print("=" * 80)
    strings = [c for c in concepts if "string" in c.xbrl_type.lower() and not c.abstract]
    print(f"合計: {len(strings)} 件")
    for c in strings[:20]:
        print(f"  {c.name}")

    # 内容カテゴリ別分類
    print("\n" + "=" * 80)
    print("【内容カテゴリ別分類（命名パターンから推定）】")
    print("=" * 80)
    category_counter: dict[str, list[str]] = defaultdict(list)
    for c in concepts:
        if not c.abstract:
            cat = infer_content_category(c.name)
            category_counter[cat].append(c.name)

    for cat in sorted(category_counter.keys(), key=lambda x: len(category_counter[x]), reverse=True):
        names = category_counter[cat]
        print(f"\n  {cat}: {len(names)} 件")
        for name in names[:5]:
            print(f"    - {name}")
        if len(names) > 5:
            print(f"    ... 残り {len(names) - 5} 件")

    # substitutionGroup 別集計
    print("\n" + "=" * 80)
    print("【substitutionGroup 別集計】")
    print("=" * 80)
    sg_counter = Counter(c.substitution_group for c in concepts)
    for sg, count in sg_counter.most_common():
        print(f"  {sg:<50s}: {count:>5d}")

    # periodType 別集計
    print("\n" + "=" * 80)
    print("【periodType 別集計】")
    print("=" * 80)
    pt_counter = Counter(c.period_type for c in concepts)
    for pt, count in pt_counter.most_common():
        print(f"  {pt:<15s}: {count:>5d}")

    # Heading/Abstract 要素のパターン（非財務セクション構造）
    print("\n" + "=" * 80)
    print("【Heading 要素一覧（非財務セクションの目次構造）— 上位30件】")
    print("=" * 80)
    headings = [c for c in concepts if c.name.endswith("Heading") and c.abstract]
    print(f"合計: {len(headings)} 件")
    for c in headings[:30]:
        print(f"  {c.name}")
    if len(headings) > 30:
        print(f"  ... 残り {len(headings) - 30} 件")


if __name__ == "__main__":
    main()

"""G-4. jpctl タクソノミ XSD 要素型分類の検証スクリプト

実行方法: EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 uv run docs/QAs/scripts/G-4.verify_jpctl.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: jpctl_cor XSD 内の全要素を型別に分類し、G-4.a.md の記述と照合した結果
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
))

NS = {"xs": "http://www.w3.org/2001/XMLSchema"}


def main() -> None:
    """メイン処理。"""
    xsd_path = sorted(TAXONOMY_ROOT.glob("taxonomy/jpctl/*/jpctl_cor_*.xsd"))[-1]
    print(f"対象XSD: {xsd_path}")
    print(f"行数: {len(xsd_path.read_text(encoding='utf-8').splitlines())}")

    tree = ET.parse(xsd_path)
    root = tree.getroot()
    elements = root.findall("xs:element", NS)
    print(f"要素総数: {len(elements)}")

    # 型別分類
    type_map: dict[str, list[str]] = defaultdict(list)
    abstract_elements: list[str] = []

    for el in elements:
        name = el.get("name", "")
        el_type = el.get("type", "")
        abstract = el.get("abstract", "false") == "true"
        type_short = el_type.split(":")[-1] if ":" in el_type else el_type

        type_map[type_short].append(name)
        if abstract:
            abstract_elements.append(name)

    print(f"\n=== 型別分類 ===")
    for type_name, names in sorted(type_map.items(), key=lambda x: -len(x[1])):
        print(f"\n[{type_name}] ({len(names)} 要素)")
        for n in names:
            is_abstract = "(abstract)" if n in abstract_elements else ""
            print(f"  - {n} {is_abstract}")

    # G-4.a.md の主張との照合
    print(f"\n\n=== G-4.a.md との照合 ===")
    print(f"回答: 総要素数=25  → 実際: {len(elements)}")
    print(f"回答: abstract(Heading)=7  → 実際: {len(abstract_elements)}")

    # Heading 要素の列挙
    headings = [n for n in abstract_elements if "Heading" in n]
    print(f"\nHeading 要素 ({len(headings)} 個):")
    for h in headings:
        print(f"  - {h}")

    # textBlockItemType の分類
    tb = type_map.get("textBlockItemType", [])
    tb_coverpage = [n for n in tb if "CoverPage" in n]
    tb_body = [n for n in tb if "CoverPage" not in n]
    print(f"\ntextBlockItemType 全体: {len(tb)}")
    print(f"  表紙: {len(tb_coverpage)} → {tb_coverpage}")
    print(f"  本文: {len(tb_body)} → {tb_body}")
    print(f"  回答: 本文TB=8 → 実際: {len(tb_body)}")

    # 数値型
    numeric_types = ["monetaryItemType", "sharesItemType", "percentItemType",
                     "decimalItemType", "nonNegativeIntegerItemType"]
    print(f"\n数値型:")
    for nt in numeric_types:
        count = len(type_map.get(nt, []))
        print(f"  {nt}: {count}")


if __name__ == "__main__":
    main()

"""G-5. jplvh タクソノミ XSD 要素型分類の検証スクリプト

実行方法: EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 uv run docs/QAs/scripts/G-5.verify_jplvh.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: jplvh_cor XSD 内の全要素を型別に分類し、G-5.a.md の記述と照合した結果
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
    xsd_path = sorted(TAXONOMY_ROOT.glob("taxonomy/jplvh/*/jplvh_cor_*.xsd"))[-1]
    print(f"対象XSD: {xsd_path}")
    print(f"行数: {len(xsd_path.read_text(encoding='utf-8').splitlines())}")

    tree = ET.parse(xsd_path)
    root = tree.getroot()
    elements = root.findall("xs:element", NS)
    print(f"要素総数: {len(elements)}")

    # 型別分類
    type_map: dict[str, list[str]] = defaultdict(list)
    abstract_map: dict[str, list[str]] = defaultdict(list)
    non_abstract_map: dict[str, list[str]] = defaultdict(list)

    for el in elements:
        name = el.get("name", "")
        el_type = el.get("type", "")
        abstract = el.get("abstract", "false") == "true"
        type_short = el_type.split(":")[-1] if ":" in el_type else el_type

        type_map[type_short].append(name)
        if abstract:
            abstract_map[type_short].append(name)
        else:
            non_abstract_map[type_short].append(name)

    print(f"\n=== 型別分類 ===")
    for type_name, names in sorted(type_map.items(), key=lambda x: -len(x[1])):
        abstract_count = len(abstract_map.get(type_name, []))
        non_abstract_count = len(non_abstract_map.get(type_name, []))
        print(f"\n[{type_name}] (全{len(names)}: abstract={abstract_count}, concrete={non_abstract_count})")
        for n in names:
            is_abs = "(abstract)" if n in abstract_map.get(type_name, []) else ""
            print(f"  - {n} {is_abs}")

    # G-5.a.md の主張との照合
    print(f"\n\n=== G-5.a.md との照合 ===")

    # sharesItemType
    shares_all = type_map.get("sharesItemType", [])
    shares_concrete = non_abstract_map.get("sharesItemType", [])
    print(f"sharesItemType: 回答=~40  → 実際(全)={len(shares_all)}, 実際(concrete)={len(shares_concrete)}")

    # Hypercube
    hypercube = type_map.get("hypercubeItem", [])
    print(f"\nHypercube (hypercubeItem): 回答=4  → 実際={len(hypercube)}")
    for h in hypercube:
        print(f"  - {h}")

    # Dimension
    dimension = type_map.get("dimensionItem", [])
    print(f"\nAxis (dimensionItem): {len(dimension)}")
    for d in dimension:
        print(f"  - {d}")

    # Domain
    domain = type_map.get("domainItemType", [])
    print(f"\nDomain (domainItemType): {len(domain)}")
    for d in domain:
        print(f"  - {d}")

    # percentItemType
    pct = type_map.get("percentItemType", [])
    print(f"\npercentItemType: {len(pct)}")
    for p in pct:
        print(f"  - {p}")

    # monetaryItemType
    mon = type_map.get("monetaryItemType", [])
    print(f"\nmonetaryItemType: {len(mon)}")
    for m in mon:
        print(f"  - {m}")

    # nonNegativeIntegerItemType
    nni = type_map.get("nonNegativeIntegerItemType", [])
    print(f"\nnonNegativeIntegerItemType: {len(nni)}")
    for n in nni:
        print(f"  - {n}")

    # dateItemType
    date = type_map.get("dateItemType", [])
    print(f"\ndateItemType: {len(date)}")
    for d in date:
        print(f"  - {d}")


if __name__ == "__main__":
    main()

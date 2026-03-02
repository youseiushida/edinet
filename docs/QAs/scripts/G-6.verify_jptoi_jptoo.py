"""G-6. jptoi / jptoo-ton タクソノミ XSD 要素型分類の検証スクリプト

実行方法: EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 uv run docs/QAs/scripts/G-6.verify_jptoi_jptoo.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: jptoi_cor と jptoo-ton_cor の要素型分類。G-6.a.md F5 の「jptoi_cor に数値型あり」の主張を検証
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

NUMERIC_TYPES = {
    "monetaryItemType", "sharesItemType", "percentItemType",
    "perShareItemType", "decimalItemType", "integerItemType",
    "nonNegativeIntegerItemType",
}


def analyze_xsd(xsd_path: Path, label: str) -> None:
    """XSD の全要素を型別に分類して表示する。

    Args:
        xsd_path: XSD ファイルパス。
        label: 表示用ラベル。
    """
    print(f"\n{'=' * 70}")
    print(f"{label}: {xsd_path.name}")
    print(f"{'=' * 70}")
    print(f"行数: {len(xsd_path.read_text(encoding='utf-8').splitlines())}")

    tree = ET.parse(xsd_path)
    root = tree.getroot()
    elements = root.findall("xs:element", NS)
    print(f"要素総数: {len(elements)}")

    type_map: dict[str, list[str]] = defaultdict(list)
    for el in elements:
        name = el.get("name", "")
        el_type = el.get("type", "")
        type_short = el_type.split(":")[-1] if ":" in el_type else el_type
        type_map[type_short].append(name)

    print(f"\n--- 型別分類 ---")
    for type_name, names in sorted(type_map.items(), key=lambda x: -len(x[1])):
        print(f"  [{type_name}] ({len(names)} 要素)")
        for n in names[:10]:
            print(f"    - {n}")
        if len(names) > 10:
            print(f"    ... (他 {len(names) - 10} 要素)")

    # 数値型チェック
    print(f"\n--- 数値型チェック ---")
    found = False
    for nt in sorted(NUMERIC_TYPES):
        if nt in type_map:
            print(f"  {nt}: {len(type_map[nt])} 要素 ← ★数値型あり")
            for n in type_map[nt]:
                print(f"    - {n}")
            found = True
        else:
            print(f"  {nt}: 0 要素")
    if not found:
        print(f"  → 数値型要素なし")

    # Dimension チェック
    print(f"\n--- Dimension チェック ---")
    for dt in ["hypercubeItem", "dimensionItem", "domainItemType"]:
        if dt in type_map:
            print(f"  {dt}: {len(type_map[dt])} 要素")
            for n in type_map[dt]:
                print(f"    - {n}")
        else:
            print(f"  {dt}: 0 要素")


def main() -> None:
    """メイン処理。"""
    print("G-6 検証: jptoi_cor vs jptoo-ton_cor の要素型比較")

    # jptoi_cor
    jptoi_xsds = sorted(TAXONOMY_ROOT.glob("taxonomy/jptoi/*/jptoi_cor_*.xsd"))
    if jptoi_xsds:
        analyze_xsd(jptoi_xsds[-1], "自社株買付 (jptoi)")
    else:
        print("jptoi_cor XSD が見つかりません")

    # jptoo-ton_cor
    jptoo_ton_xsds = sorted(TAXONOMY_ROOT.glob("taxonomy/jptoo-ton/*/jptoo-ton_cor_*.xsd"))
    if jptoo_ton_xsds:
        analyze_xsd(jptoo_ton_xsds[-1], "他社株買付-届出書 (jptoo-ton)")
    else:
        print("jptoo-ton_cor XSD が見つかりません")

    # 照合サマリー
    print(f"\n\n{'=' * 70}")
    print("G-6.a.md F5 の主張: jptoi_cor に sharesItemType/monetaryItemType/percentItemType が存在する")
    print("↑ 上記の実行結果と照合してください")


if __name__ == "__main__":
    main()

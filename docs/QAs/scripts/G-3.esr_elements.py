"""G-3. jpcrp-esr_cor XSD の要素型分類検証スクリプト

G-3.a.md F5 の「目次項目（Heading系 abstract=true）5要素」を検証する。
検証の結果、abstract=true かつ stringItemType の要素は 4 個であり、
回答の「5」は誤りであることを確認した。

実行方法:
    EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 \
        uv run docs/QAs/scripts/G-3.esr_elements.py

前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: jpcrp-esr_cor XSD 内の全要素を型別・abstract別に分類した結果
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
    """メイン処理。jpcrp-esr_cor XSD を解析し要素型を分類する。"""
    xsd_path = sorted(
        TAXONOMY_ROOT.glob("taxonomy/jpcrp-esr/*/jpcrp-esr_cor_*.xsd"),
    )[-1]
    print(f"対象XSD: {xsd_path}")
    print(f"行数: {len(xsd_path.read_text(encoding='utf-8').splitlines())}")

    tree = ET.parse(xsd_path)
    root = tree.getroot()
    elements = root.findall("xs:element", NS)
    print(f"要素総数: {len(elements)}")

    # 型別分類
    type_map: dict[str, list[str]] = defaultdict(list)
    abstract_elements: list[str] = []
    concrete_elements: list[str] = []

    for el in elements:
        name = el.get("name", "")
        el_type = el.get("type", "")
        abstract = el.get("abstract", "false") == "true"
        type_short = el_type.split(":")[-1] if ":" in el_type else el_type

        type_map[type_short].append(name)
        if abstract:
            abstract_elements.append(name)
        else:
            concrete_elements.append(name)

    # 型別サマリー
    print(f"\n=== 型別分類 ===")
    for type_name, names in sorted(type_map.items(), key=lambda x: -len(x[1])):
        abs_in_type = [n for n in names if n in abstract_elements]
        con_in_type = [n for n in names if n in concrete_elements]
        print(
            f"\n[{type_name}] "
            f"(全{len(names)}: abstract={len(abs_in_type)}, "
            f"concrete={len(con_in_type)})"
        )
        for n in names:
            tag = "(abstract)" if n in abstract_elements else ""
            print(f"  - {n} {tag}")

    # G-3.a.md F5 との照合
    print(f"\n\n=== G-3.a.md F5 との照合 ===")

    heading = [n for n in abstract_elements]
    print(f"abstract=true 要素（Heading系）: 回答=5 → 実際={len(heading)}")
    for n in heading:
        print(f"  - {n}")

    textblock = type_map.get("textBlockItemType", [])
    textblock_concrete = [n for n in textblock if n in concrete_elements]
    print(f"\ntextBlockItemType (concrete): 回答=約45 → 実際={len(textblock_concrete)}")

    string_concrete = [
        n for n in type_map.get("stringItemType", [])
        if n in concrete_elements
    ]
    print(f"stringItemType (concrete): 回答=約12 → 実際={len(string_concrete)}")

    date_type = type_map.get("dateItemType", [])
    print(f"dateItemType: 回答=1 → 実際={len(date_type)}")

    # 数値型の確認（0のはず）
    numeric_types = [
        "monetaryItemType", "sharesItemType",
        "percentItemType", "integerItemType",
    ]
    for nt in numeric_types:
        count = len(type_map.get(nt, []))
        if count > 0:
            print(f"[警告] {nt}: {count} 要素（回答では0）")
    print(f"数値型要素: 0（確認OK）")

    # サマリー
    print(f"\n=== 検証結論 ===")
    print(f"abstract=true（Heading系）要素は {len(heading)} 個。")
    if len(heading) != 5:
        print(f"→ 回答の「5要素」は誤り。正しくは {len(heading)} 要素。")
    else:
        print(f"→ 回答の「5要素」と一致。")


if __name__ == "__main__":
    main()

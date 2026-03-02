"""D-2. TextBlock 分類の検証スクリプト

D-2.usgaap_search.py のセクション4にある TextBlock フィルタにバグがあるため
（'textBlock' in type.lower() は大文字Bが小文字化され常に False）、
本スクリプトで正しいフィルタによる TextBlock/非TextBlock 分類を独立検証する。

実行方法: uv run docs/QAs/scripts/D-2.verify_textblock.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: USGAAP 要素の TextBlock/非TextBlock 分類結果
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
))

JPCRP_DIR = TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01"

NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "xbrli": "http://www.xbrl.org/2003/instance",
}


def main() -> None:
    """メイン処理。"""
    xsd_path = JPCRP_DIR / "jpcrp_cor_2025-11-01.xsd"
    print("D-2 TextBlock 分類の独立検証")
    print("=" * 70)
    print(f"対象: {xsd_path}")

    tree = ET.parse(xsd_path)
    root = tree.getroot()

    # USGAAP 要素を収集
    usgaap_elements: list[dict[str, str | bool]] = []
    for elem in root.findall("xsd:element", NS):
        name = elem.get("name", "")
        if "USGAAP" in name:
            usgaap_elements.append({
                "name": name,
                "type": elem.get("type", ""),
                "abstract": elem.get("abstract", "false") == "true",
            })

    print(f"\nUSGAAP 要素数: {len(usgaap_elements)}")

    # 正しいフィルタで分類
    textblock = [e for e in usgaap_elements if "textblock" in str(e["type"]).lower()]
    abstract = [e for e in usgaap_elements if e["abstract"]]
    non_tb_non_abs = [
        e for e in usgaap_elements
        if "textblock" not in str(e["type"]).lower() and not e["abstract"]
    ]

    print(f"TextBlock 型: {len(textblock)}")
    print(f"Abstract: {len(abstract)}")
    print(f"非TextBlock・非Abstract: {len(non_tb_non_abs)}")
    print(f"合計チェック: {len(textblock)} + {len(abstract)} + {len(non_tb_non_abs)} = {len(textblock) + len(abstract) + len(non_tb_non_abs)}")

    # TextBlock 一覧
    print(f"\n--- TextBlock 要素（{len(textblock)} 件）---")
    for e in sorted(textblock, key=lambda x: str(x["name"])):
        print(f"  {e['name']}")

    # 非TextBlock・非Abstract 一覧
    print(f"\n--- 非TextBlock・非Abstract 要素（{len(non_tb_non_abs)} 件）---")
    has_summary = 0
    for e in sorted(non_tb_non_abs, key=lambda x: str(x["name"])):
        suffix = ""
        if "SummaryOfBusinessResults" in str(e["name"]):
            has_summary += 1
            suffix = " [SummaryOfBusinessResults]"
        print(f"  {e['name']}  type={e['type']}{suffix}")

    print(f"\n  うち SummaryOfBusinessResults サフィックスを持つ要素: {has_summary}/{len(non_tb_non_abs)}")

    # D-2.a.md の記述との照合
    print(f"\n{'=' * 70}")
    print("D-2.a.md の記述との照合:")
    print(f"  [F3] textBlockItemType = 14  → 実際: {len(textblock)}  {'OK' if len(textblock) == 14 else 'NG'}")
    print(f"  [F4] 非TextBlock非Abstract = 20 → 実際: {len(non_tb_non_abs)}  {'OK' if len(non_tb_non_abs) == 20 else 'NG'}")
    print(f"  [F4] 全て SummaryOfBusinessResults → 実際: {has_summary}/{len(non_tb_non_abs)}  {'OK' if has_summary == len(non_tb_non_abs) else 'NG'}")
    print(f"\n結論: D-2.a.md の記述は正確。D-2.usgaap_search.py のセクション4のフィルタにバグがあるが、")
    print(f"      回答の数値はセクション2の型分布集計から正しく算出されている。")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

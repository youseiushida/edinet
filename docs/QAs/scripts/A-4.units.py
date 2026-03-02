"""A-4 調査スクリプト: サンプル .xbrl から全 Unit 定義を抽出する。

サンプルインスタンスの .xbrl ファイルから xbrli:unit 要素を抽出し、
ユニット ID・measure・divide 構造を一覧表示する。
"""

from __future__ import annotations

from pathlib import Path
from lxml import etree

SAMPLE_BASE = Path(__file__).resolve().parents[2] / "仕様書" / "2026" / "サンプルインスタンス" / "サンプルインスタンス" / "ダウンロードデータ"

XBRL_FILES = [
    ("J-GAAP", SAMPLE_BASE / "02_開示府令-有価証券報告書" / "S002XXXX" / "XBRL" / "PublicDoc" / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12.xbrl"),
    ("IFRS", SAMPLE_BASE / "03_開示府令-IFRS有価証券報告書" / "S003XXXX" / "XBRL" / "PublicDoc" / "jpcrp030000-asr-001_X99002-000_2026-03-31_01_2026-06-12.xbrl"),
]

NS = {
    "xbrli": "http://www.xbrl.org/2003/instance",
}


def extract_units(path: Path) -> list[dict]:
    """XBRLファイルから全Unit定義を抽出する。

    Args:
        path: XBRLファイルのパス。

    Returns:
        Unit情報の辞書リスト。
    """
    tree = etree.parse(str(path))
    root = tree.getroot()
    units = []

    for unit_elem in root.findall(".//xbrli:unit", NS):
        unit_id = unit_elem.get("id", "")
        measures = unit_elem.findall("xbrli:measure", NS)
        divide = unit_elem.find("xbrli:divide", NS)

        if divide is not None:
            numerator = divide.find("xbrli:unitNumerator/xbrli:measure", NS)
            denominator = divide.find("xbrli:unitDenominator/xbrli:measure", NS)
            units.append({
                "id": unit_id,
                "type": "divide",
                "numerator": numerator.text if numerator is not None else "",
                "denominator": denominator.text if denominator is not None else "",
            })
        elif measures:
            units.append({
                "id": unit_id,
                "type": "simple",
                "measure": measures[0].text if measures else "",
            })

    return units


def main() -> None:
    """メイン処理。"""
    for label, path in XBRL_FILES:
        print(f"\n{'=' * 70}")
        print(f"{label}: {path.name}")
        print(f"{'=' * 70}")

        if not path.exists():
            print(f"  [SKIP] ファイルが存在しません: {path}")
            continue

        units = extract_units(path)
        print(f"  Unit 定義数: {len(units)}")

        for u in units:
            if u["type"] == "simple":
                print(f"  - id={u['id']:20s}  measure={u['measure']}")
            else:
                print(f"  - id={u['id']:20s}  divide: {u['numerator']} / {u['denominator']}")

        # 原文 XML も表示
        tree = etree.parse(str(path))
        root = tree.getroot()
        print("\n  --- 原文 XML ---")
        for unit_elem in root.findall(".//xbrli:unit", NS):
            xml_str = etree.tostring(unit_elem, pretty_print=True, encoding="unicode")
            for line in xml_str.strip().split("\n"):
                print(f"  {line}")
            print()


if __name__ == "__main__":
    main()

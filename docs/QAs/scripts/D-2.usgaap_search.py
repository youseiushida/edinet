"""D-2. US-GAAP 関連要素の検索スクリプト

実行方法: uv run docs/QAs/scripts/D-2.usgaap_search.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: jpcrp_cor XSD 内の USGAAP を含む要素一覧、ラベル、
      タクソノミ内の US-GAAP 関連ファイルの有無
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

# タクソノミルート
TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
))

JPCRP_DIR = TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01"
TAXONOMY_DIR = TAXONOMY_ROOT / "taxonomy"

# XML名前空間
NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "xbrli": "http://www.xbrl.org/2003/instance",
    "xlink": "http://www.w3.org/1999/xlink",
}


def search_usgaap_elements(xsd_path: Path) -> list[dict]:
    """XSD ファイルから USGAAP を含む要素を検索する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        要素情報の辞書リスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    results = []
    for elem in root.findall("xsd:element", NS):
        name = elem.get("name", "")
        if "USGAAP" in name or "USGaap" in name or "usgaap" in name.lower():
            results.append({
                "name": name,
                "type": elem.get("type", ""),
                "abstract": elem.get("abstract", "false") == "true",
                "periodType": elem.get(f"{{{NS['xbrli']}}}periodType", ""),
                "substitutionGroup": elem.get("substitutionGroup", ""),
            })

    return results


def search_jmis_elements(xsd_path: Path) -> list[dict]:
    """XSD ファイルから JMIS（修正国際基準）を含む要素を検索する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        要素情報の辞書リスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    results = []
    for elem in root.findall("xsd:element", NS):
        name = elem.get("name", "")
        if "JMIS" in name:
            results.append({
                "name": name,
                "type": elem.get("type", ""),
                "abstract": elem.get("abstract", "false") == "true",
                "periodType": elem.get(f"{{{NS['xbrli']}}}periodType", ""),
            })

    return results


def check_usgaap_taxonomy_dirs() -> None:
    """タクソノミディレクトリに US-GAAP 関連のディレクトリがあるか確認する。"""
    print(f"\n{'=' * 70}")
    print("  US-GAAP 関連タクソノミディレクトリの確認")
    print(f"{'=' * 70}")

    if not TAXONOMY_DIR.exists():
        print(f"  ERROR: {TAXONOMY_DIR} が存在しません")
        return

    for item in sorted(TAXONOMY_DIR.iterdir()):
        if item.is_dir():
            name_lower = item.name.lower()
            marker = ""
            if any(kw in name_lower for kw in ["usgaap", "us-gaap", "fasb"]):
                marker = " ★ US-GAAP 関連"
            elif any(kw in name_lower for kw in ["jpigp", "ifrs"]):
                marker = " ★ IFRS 関連"
            elif "jmis" in name_lower:
                marker = " ★ JMIS 関連"
            print(f"  {item.name}/{marker}")


def extract_labels_for_elements(
    lab_path: Path,
    target_names: set[str],
) -> dict[str, str]:
    """ラベルファイルから特定要素のラベルを抽出する。

    Args:
        lab_path: ラベル XML ファイルのパス。
        target_names: 対象要素名のセット。

    Returns:
        要素名 → ラベルテキストの辞書。
    """
    if not lab_path.exists():
        return {}

    tree = ET.parse(lab_path)
    root = tree.getroot()

    loc_map: dict[str, str] = {}
    label_map: dict[str, str] = {}
    arc_map: dict[str, list[str]] = {}

    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag == "loc":
            label_key = elem.get(f"{{{NS['xlink']}}}label", "")
            href = elem.get(f"{{{NS['xlink']}}}href", "")
            if "#" in href:
                fragment = href.split("#")[-1]
                # jpcrp_cor_ElementName → ElementName
                parts = fragment.split("_", 2)
                name = parts[2] if len(parts) >= 3 else fragment
                loc_map[label_key] = name

        elif tag == "label":
            label_key = elem.get(f"{{{NS['xlink']}}}label", "")
            role = elem.get(f"{{{NS['xlink']}}}role", "")
            if "label" in role and "verbose" not in role and "documentation" not in role:
                text = elem.text or ""
                label_map[label_key] = text

        elif tag == "labelArc":
            from_key = elem.get(f"{{{NS['xlink']}}}from", "")
            to_key = elem.get(f"{{{NS['xlink']}}}to", "")
            arc_map.setdefault(from_key, []).append(to_key)

    result: dict[str, str] = {}
    for loc_key, name in loc_map.items():
        if name in target_names and loc_key in arc_map:
            for lbl_key in arc_map[loc_key]:
                if lbl_key in label_map:
                    result[name] = label_map[lbl_key]
                    break

    return result


def main() -> None:
    """メイン処理。"""
    print("D-2: US-GAAP 関連要素の検索")
    print("=" * 70)

    # 1. タクソノミディレクトリの確認
    check_usgaap_taxonomy_dirs()

    # 2. jpcrp_cor XSD から USGAAP 要素を検索
    xsd_path = JPCRP_DIR / "jpcrp_cor_2025-11-01.xsd"
    print(f"\n{'=' * 70}")
    print(f"  jpcrp_cor XSD から USGAAP 要素を検索")
    print(f"  ファイル: {xsd_path}")
    print(f"{'=' * 70}")

    usgaap_elements = search_usgaap_elements(xsd_path)
    print(f"\n  USGAAP 要素数: {len(usgaap_elements)}")

    # 型別集計
    type_counts: dict[str, int] = {}
    for e in usgaap_elements:
        t = e["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print("\n  --- データ型分布 ---")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<50s}: {c}")

    # 全要素一覧
    abstract_elems = [e for e in usgaap_elements if e["abstract"]]
    concrete_elems = [e for e in usgaap_elements if not e["abstract"]]

    print(f"\n  Abstract: {len(abstract_elems)}")
    print(f"  Concrete: {len(concrete_elems)}")

    # ラベル取得
    target_names = {e["name"] for e in usgaap_elements}
    lab_path = JPCRP_DIR / "label" / "jpcrp_2025-11-01_lab.xml"
    labels = extract_labels_for_elements(lab_path, target_names)

    print(f"\n  --- USGAAP 要素一覧 ---")
    for e in sorted(usgaap_elements, key=lambda x: x["name"]):
        label = labels.get(e["name"], "")
        abstract_str = " [Abstract]" if e["abstract"] else ""
        label_str = f" → {label}" if label else ""
        print(f"  {e['name']:<70s} type={e['type']:<45s}{abstract_str}{label_str}")

    # 3. JMIS（修正国際基準）要素も検索
    print(f"\n{'=' * 70}")
    print(f"  jpcrp_cor XSD から JMIS 要素を検索")
    print(f"{'=' * 70}")

    jmis_elements = search_jmis_elements(xsd_path)
    print(f"\n  JMIS 要素数: {len(jmis_elements)}")

    if jmis_elements:
        jmis_names = {e["name"] for e in jmis_elements}
        jmis_labels = extract_labels_for_elements(lab_path, jmis_names)

        print(f"\n  --- JMIS 要素一覧 ---")
        for e in sorted(jmis_elements, key=lambda x: x["name"]):
            label = jmis_labels.get(e["name"], "")
            abstract_str = " [Abstract]" if e["abstract"] else ""
            label_str = f" → {label}" if label else ""
            print(f"  {e['name']:<70s} type={e['type']:<45s}{abstract_str}{label_str}")

    # 4. 包括タグ付けの確認: TextBlock 型の要素を抽出
    print(f"\n{'=' * 70}")
    print(f"  USGAAP TextBlock 要素の分析")
    print(f"{'=' * 70}")

    textblock_elems = [e for e in usgaap_elements if "textBlock" in e["type"].lower()]
    non_textblock_elems = [e for e in usgaap_elements if "textBlock" not in e["type"].lower() and not e["abstract"]]

    print(f"\n  TextBlock 型: {len(textblock_elems)}")
    print(f"  非TextBlock・非Abstract型: {len(non_textblock_elems)}")

    if non_textblock_elems:
        print("\n  ★ 非TextBlock の concrete USGAAP 要素（詳細タグ付け可能性）:")
        for e in non_textblock_elems:
            label = labels.get(e["name"], "")
            print(f"    {e['name']:<60s} type={e['type']} → {label}")
    else:
        print("\n  → 全ての concrete USGAAP 要素が TextBlock 型")
        print("  → 仕様書の記述通り、US-GAAP は包括タグ付けのみ")

    print(f"\n{'=' * 70}")
    print("D-2 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

"""D-1. IFRS タクソノミの概念抽出・J-GAAP 対応表生成スクリプト

実行方法: uv run docs/QAs/scripts/D-1.ifrs_concepts.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: IFRS タクソノミ(jpigp_cor)の全要素一覧、日英ラベル、
      calculation linkbase の主要科目階層、J-GAAP 対応表
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

JPIGP_DIR = TAXONOMY_ROOT / "taxonomy" / "jpigp" / "2025-11-01"
JPPFS_DIR = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01"

# XML名前空間
NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "xbrli": "http://www.xbrl.org/2003/instance",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
    "label": "http://www.xbrl.org/2003/linkbase",
}


def extract_elements(xsd_path: Path) -> list[dict]:
    """XSD ファイルから要素定義を抽出する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        要素情報の辞書リスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    elements = []
    for elem in root.findall("xsd:element", NS):
        name = elem.get("name", "")
        elem_type = elem.get("type", "")
        abstract = elem.get("abstract", "false")
        nillable = elem.get("nillable", "false")
        period_type = elem.get(f"{{{NS['xbrli']}}}periodType", "")
        subst_group = elem.get("substitutionGroup", "")
        elem_id = elem.get("id", "")

        elements.append({
            "name": name,
            "type": elem_type,
            "abstract": abstract == "true",
            "nillable": nillable == "true",
            "periodType": period_type,
            "substitutionGroup": subst_group,
            "id": elem_id,
        })

    return elements


def extract_labels(lab_path: Path) -> dict[str, dict[str, str]]:
    """ラベルリンクベースからラベルを抽出する。

    Args:
        lab_path: ラベル XML ファイルのパス。

    Returns:
        要素名 -> {ロール -> ラベルテキスト} の辞書。
    """
    tree = ET.parse(lab_path)
    root = tree.getroot()

    # loc → href のマッピング
    loc_map: dict[str, str] = {}
    # label → テキストのマッピング
    label_map: dict[str, tuple[str, str]] = {}  # label_key -> (role, text)
    # loc → label の紐付け
    arc_map: dict[str, list[str]] = {}

    for linkbase_elem in root.iter():
        tag = linkbase_elem.tag.split("}")[-1] if "}" in linkbase_elem.tag else linkbase_elem.tag

        if tag == "loc":
            label_key = linkbase_elem.get(f"{{{NS['xlink']}}}label", "")
            href = linkbase_elem.get(f"{{{NS['xlink']}}}href", "")
            loc_map[label_key] = href

        elif tag == "label":
            label_key = linkbase_elem.get(f"{{{NS['xlink']}}}label", "")
            role = linkbase_elem.get(f"{{{NS['xlink']}}}role", "")
            text = linkbase_elem.text or ""
            label_map[label_key] = (role, text)

        elif tag == "labelArc":
            from_key = linkbase_elem.get(f"{{{NS['xlink']}}}from", "")
            to_key = linkbase_elem.get(f"{{{NS['xlink']}}}to", "")
            arc_map.setdefault(from_key, []).append(to_key)

    # 組み立て: 要素名 → ラベルマップ
    result: dict[str, dict[str, str]] = {}
    for loc_key, href in loc_map.items():
        # href から要素名を抽出 (例: jpigp_cor_2025-11-01.xsd#jpigp_cor_RevenueIFRS)
        if "#" in href:
            fragment = href.split("#")[-1]
            # jpigp_cor_RevenueIFRS → RevenueIFRS
            # プレフィックスを除去
            parts = fragment.split("_", 2)
            if len(parts) >= 3:
                elem_name = parts[2]
            else:
                elem_name = fragment
        else:
            elem_name = href

        if loc_key in arc_map:
            for label_key in arc_map[loc_key]:
                if label_key in label_map:
                    role, text = label_map[label_key]
                    role_short = role.split("/")[-1] if "/" in role else role
                    result.setdefault(elem_name, {})[role_short] = text

    return result


def extract_cal_hierarchy(cal_path: Path) -> list[tuple[str, str, float, int]]:
    """calculation linkbase から親子関係を抽出する。

    Args:
        cal_path: calculation linkbase XML ファイルのパス。

    Returns:
        (親要素名, 子要素名, weight, order) のリスト。
    """
    tree = ET.parse(cal_path)
    root = tree.getroot()

    # loc → 要素名
    loc_map: dict[str, str] = {}
    arcs: list[tuple[str, str, float, int]] = []

    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag == "loc":
            label = elem.get(f"{{{NS['xlink']}}}label", "")
            href = elem.get(f"{{{NS['xlink']}}}href", "")
            if "#" in href:
                fragment = href.split("#")[-1]
                parts = fragment.split("_", 2)
                name = parts[2] if len(parts) >= 3 else fragment
            else:
                name = href
            loc_map[label] = name

        elif tag == "calculationArc":
            from_key = elem.get(f"{{{NS['xlink']}}}from", "")
            to_key = elem.get(f"{{{NS['xlink']}}}to", "")
            weight = float(elem.get("weight", "1"))
            order = int(float(elem.get("order", "0")))
            arcs.append((from_key, to_key, weight, order))

    # label を要素名に解決
    result = []
    for from_key, to_key, weight, order in arcs:
        parent = loc_map.get(from_key, from_key)
        child = loc_map.get(to_key, to_key)
        result.append((parent, child, weight, order))

    return result


def print_cal_tree(arcs: list[tuple[str, str, float, int]], labels_ja: dict[str, dict[str, str]], *, title: str) -> None:
    """calculation linkbase の階層をツリー表示する。

    Args:
        arcs: (親, 子, weight, order) のリスト。
        labels_ja: 日本語ラベルの辞書。
        title: セクションタイトル。
    """
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

    # 親→子のマッピング
    children: dict[str, list[tuple[str, float, int]]] = {}
    all_children: set[str] = set()
    for parent, child, weight, order in arcs:
        children.setdefault(parent, []).append((child, weight, order))
        all_children.add(child)

    # ソート
    for parent in children:
        children[parent].sort(key=lambda x: x[2])

    # ルート要素を特定（他の要素の子でない要素）
    all_parents = set(children.keys())
    roots = all_parents - all_children

    def get_label(name: str) -> str:
        """要素名の日本語ラベルを取得する。"""
        if name in labels_ja:
            return labels_ja[name].get("label", "")
        return ""

    def print_node(name: str, depth: int = 0, weight: float = 1.0) -> None:
        """ノードを再帰的に表示する。"""
        indent = "  " * depth
        sign = "+" if weight >= 0 else "-"
        label = get_label(name)
        label_str = f" ({label})" if label else ""
        print(f"  {indent}{sign} {name}{label_str}")
        if name in children:
            for child_name, child_weight, _ in children[name]:
                print_node(child_name, depth + 1, child_weight)

    for root in sorted(roots):
        print_node(root)
        print()


def main() -> None:
    """メイン処理。"""
    print("D-1: IFRS タクソノミ概念抽出・J-GAAP 対応表")
    print("=" * 70)

    # 1. jpigp_cor XSD から全要素を抽出
    xsd_path = JPIGP_DIR / "jpigp_cor_2025-11-01.xsd"
    print(f"\n[1] XSD 要素抽出: {xsd_path}")

    elements = extract_elements(xsd_path)
    abstract_elems = [e for e in elements if e["abstract"]]
    concrete_elems = [e for e in elements if not e["abstract"]]

    print(f"  全要素数: {len(elements)}")
    print(f"  Abstract: {len(abstract_elems)}")
    print(f"  Concrete: {len(concrete_elems)}")

    # jpigp_rt (role type schema) も確認
    rt_path = JPIGP_DIR / "jpigp_rt_2025-11-01.xsd"
    if rt_path.exists():
        rt_elements = extract_elements(rt_path)
        print(f"\n  jpigp_rt 要素数: {len(rt_elements)}")

    # 要素一覧を型別に分類
    type_counts: dict[str, int] = {}
    for e in elements:
        t = e["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print("\n  --- データ型分布 ---")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<50s}: {c}")

    # Concrete 要素の一覧
    print(f"\n  --- Concrete 要素一覧（{len(concrete_elems)} 件）---")
    for e in concrete_elems:
        print(f"  {e['name']:<60s} type={e['type']:<40s} period={e['periodType']}")

    # 2. 日本語ラベルを抽出
    lab_ja_path = JPIGP_DIR / "label" / "jpigp_2025-11-01_lab.xml"
    print(f"\n[2] 日本語ラベル抽出: {lab_ja_path}")

    labels_ja = extract_labels(lab_ja_path)
    print(f"  ラベル付き要素数: {len(labels_ja)}")

    # 日本語ラベルの一覧
    print("\n  --- 日本語ラベル一覧（標準ラベル）---")
    for name in sorted(labels_ja):
        std_label = labels_ja[name].get("label", "")
        verbose_label = labels_ja[name].get("verboseLabel", "")
        if std_label:
            extra = f" [verbose: {verbose_label}]" if verbose_label else ""
            print(f"  {name:<60s}: {std_label}{extra}")

    # 3. 英語ラベルを抽出
    lab_en_path = JPIGP_DIR / "label" / "jpigp_2025-11-01_lab-en.xml"
    print(f"\n[3] 英語ラベル抽出: {lab_en_path}")

    labels_en = extract_labels(lab_en_path)
    print(f"  ラベル付き要素数: {len(labels_en)}")

    # 4. calculation linkbase の解析
    cal_files = {
        "B/S (貸借対照表)": JPIGP_DIR / "r" / "jpigp_ac_2025-11-01_cal_bs.xml",
        "P/L (損益計算書)": JPIGP_DIR / "r" / "jpigp_ac_2025-11-01_cal_pl.xml",
        "C/F (キャッシュ・フロー)": JPIGP_DIR / "r" / "jpigp_ac_2025-11-01_cal_cf.xml",
        "C/I (包括利益)": JPIGP_DIR / "r" / "jpigp_ac_2025-11-01_cal_ci.xml",
        "S/S (株主資本等変動)": JPIGP_DIR / "r" / "jpigp_ac_2025-11-01_cal_ss.xml",
    }

    print(f"\n[4] Calculation Linkbase 解析")
    for title, cal_path in cal_files.items():
        if cal_path.exists():
            arcs = extract_cal_hierarchy(cal_path)
            print(f"\n  {title}: {len(arcs)} 件のアーク")
            print_cal_tree(arcs, labels_ja, title=title)
        else:
            print(f"\n  {title}: ファイルなし ({cal_path})")

    # 5. J-GAAP 対応表（主要科目のみ）
    print(f"\n{'=' * 70}")
    print("  [5] J-GAAP ↔ IFRS 主要科目対応表")
    print(f"{'=' * 70}")

    # jppfs_cor のラベルも取得
    jppfs_lab_path = JPPFS_DIR / "label" / "jppfs_2025-11-01_lab.xml"
    jppfs_labels: dict[str, dict[str, str]] = {}
    if jppfs_lab_path.exists():
        jppfs_labels = extract_labels(jppfs_lab_path)

    # 手動対応表（calculation linkbase の構造から判定）
    mapping = [
        ("--- P/L 科目 ---", "", ""),
        ("NetSales", "RevenueIFRS", "売上高 → 収益"),
        ("CostOfSales", "CostOfSalesIFRS", "売上原価"),
        ("GrossProfit", "GrossProfitIFRS", "売上総利益"),
        ("OperatingIncome", "OperatingProfitLossIFRS", "営業利益"),
        ("OrdinaryIncome", "(該当なし)", "経常利益 → IFRS になし"),
        ("ProfitLoss", "ProfitLossIFRS", "当期純利益"),
        ("--- B/S 科目 ---", "", ""),
        ("TotalAssets", "TotalAssetsIFRS (要確認)", "総資産"),
        ("NetAssets", "EquityIFRS (要確認)", "純資産 → 資本"),
    ]

    print(f"\n  {'J-GAAP (jppfs_cor)':<35s} {'IFRS (jpigp_cor)':<40s} {'備考'}")
    print(f"  {'-'*35} {'-'*40} {'-'*30}")
    for jgaap, ifrs, note in mapping:
        if jgaap.startswith("---"):
            print(f"\n  {jgaap}")
            continue
        # ラベル取得
        jgaap_label = jppfs_labels.get(jgaap, {}).get("label", "")
        ifrs_label = labels_ja.get(ifrs.split(" ")[0], {}).get("label", "")
        print(f"  {jgaap:<35s} {ifrs:<40s} {note} [ja: {jgaap_label} → {ifrs_label}]")

    # 6. OrdinaryIncome の不存在を確認
    print(f"\n{'=' * 70}")
    print("  [6] OrdinaryIncome の不存在確認")
    print(f"{'=' * 70}")
    ordinary_found = [e for e in elements if "Ordinary" in e["name"]]
    if ordinary_found:
        print("  ★ Ordinary を含む要素が存在:")
        for e in ordinary_found:
            print(f"    {e['name']} (abstract={e['abstract']}, type={e['type']})")
    else:
        print("  Ordinary を含む要素: なし → IFRS に経常利益は存在しない")

    print(f"\n{'=' * 70}")
    print("D-1 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

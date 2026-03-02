"""C-7. Calculation Linkbase 構造解析スクリプト

サンプルインスタンスの _cal.xml をパースし、weight値・ロールURI・計算ツリーを解析する。

実行方法: uv run docs/QAs/scripts/C-7.cal_analysis.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: weight値一覧、ロールURI比較（pre vs cal）、PL計算ツリー例
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

SAMPLE_BASE = Path(__file__).resolve().parents[2] / "仕様書" / "2026" / "サンプルインスタンス" / "サンプルインスタンス" / "提出データ"
SAMPLE_02 = SAMPLE_BASE / "02_開示府令-有価証券報告書" / "XBRL" / "PublicDoc"

SAMPLE_CAL = SAMPLE_02 / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12_cal.xml"
SAMPLE_PRE = SAMPLE_02 / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12_pre.xml"

# タクソノミの計算リンク（一般商工業、連結PL）
TAXONOMY_CAL_PL = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "r" / "cai" / "jppfs_cai_ac_2025-11-01_cal_pl.xml"
TAXONOMY_CAL_BS = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "r" / "cai" / "jppfs_cai_ac_2025-11-01_cal_bs.xml"

NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

SUMMATION_ITEM = "http://www.xbrl.org/2003/arcrole/summation-item"


@dataclass
class CalcArc:
    """calculationArc の情報。"""

    from_label: str
    to_label: str
    order: float
    weight: float


@dataclass
class CalcNode:
    """計算ツリーノード。"""

    name: str
    weight: float = 1.0
    order: float = 0.0
    children: list[CalcNode] = field(default_factory=list)


def extract_local_name(href: str) -> str:
    """href から要素のローカル名を抽出する。

    Args:
        href: xlink:href の値。

    Returns:
        ローカル名。
    """
    if "#" in href:
        fragment = href.split("#", 1)[1]
        parts = fragment.split("_")
        if len(parts) >= 3 and parts[0] in ("jppfs", "jpcrp", "jpdei"):
            return "_".join(parts[2:])
        if "-" in parts[0]:
            return "_".join(parts[2:]) if len(parts) >= 3 else fragment
        return fragment
    return href


def parse_cal_file(xml_path: Path) -> dict[str, dict]:
    """_cal.xml をパースしてロール別のデータを抽出する。

    Args:
        xml_path: _cal.xml のパス。

    Returns:
        ロール URI → {"loc_map": ..., "arcs": ...} の辞書。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    results: dict[str, dict] = {}

    for clink in root.findall(f"{{{NS['link']}}}calculationLink"):
        role = clink.get(f"{{{NS['xlink']}}}role", "")

        loc_map: dict[str, str] = {}
        for loc in clink.findall(f"{{{NS['link']}}}loc"):
            label = loc.get(f"{{{NS['xlink']}}}label", "")
            href = loc.get(f"{{{NS['xlink']}}}href", "")
            loc_map[label] = href

        arcs: list[CalcArc] = []
        for arc in clink.findall(f"{{{NS['link']}}}calculationArc"):
            arcrole = arc.get(f"{{{NS['xlink']}}}arcrole", "")
            if arcrole != SUMMATION_ITEM:
                continue
            from_label = arc.get(f"{{{NS['xlink']}}}from", "")
            to_label = arc.get(f"{{{NS['xlink']}}}to", "")
            order = float(arc.get("order", "0"))
            weight = float(arc.get("weight", "1"))
            arcs.append(CalcArc(from_label, to_label, order, weight))

        results[role] = {"loc_map": loc_map, "arcs": arcs}

    return results


def build_calc_tree(loc_map: dict[str, str], arcs: list[CalcArc]) -> list[CalcNode]:
    """計算ツリーを構築する。

    Args:
        loc_map: ロケータラベル → href。
        arcs: CalcArc のリスト。

    Returns:
        ルートノードのリスト。
    """
    label_to_name = {label: extract_local_name(href) for label, href in loc_map.items()}
    children_map: dict[str, list[CalcArc]] = defaultdict(list)
    child_labels: set[str] = set()
    for arc in arcs:
        children_map[arc.from_label].append(arc)
        child_labels.add(arc.to_label)

    root_labels = set(children_map.keys()) - child_labels

    def build_node(label: str, weight: float = 1.0, order: float = 0.0) -> CalcNode:
        """再帰的にノードを構築。"""
        name = label_to_name.get(label, label)
        node = CalcNode(name=name, weight=weight, order=order)
        if label in children_map:
            for arc in sorted(children_map[label], key=lambda a: a.order):
                node.children.append(build_node(arc.to_label, arc.weight, arc.order))
        return node

    return [build_node(label) for label in sorted(root_labels)]


def print_calc_tree(nodes: list[CalcNode], indent: int = 0) -> None:
    """計算ツリーを表示する。

    Args:
        nodes: ノードリスト。
        indent: インデント深さ。
    """
    for node in nodes:
        prefix = "  " * indent
        w_str = f"+{node.weight:g}" if node.weight >= 0 else f"{node.weight:g}"
        print(f"{prefix}[w={w_str}] {node.name}")
        if node.children:
            print_calc_tree(node.children, indent + 1)


def extract_role_refs(xml_path: Path) -> list[str]:
    """リンクベースから roleRef URI を抽出する。

    Args:
        xml_path: リンクベースのパス。

    Returns:
        roleURI のリスト。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    return [rr.get("roleURI", "") for rr in root.findall(f"{{{NS['link']}}}roleRef") if rr.get("roleURI")]


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("C-7. Calculation Linkbase 構造解析")
    print("=" * 80)

    # 1. サンプルインスタンスの _cal.xml 解析
    print(f"\n{'=' * 80}")
    print(f"【サンプルインスタンスの _cal.xml】")
    print(f"ファイル: {SAMPLE_CAL.name}")
    print(f"{'=' * 80}")

    cal_data = parse_cal_file(SAMPLE_CAL)
    print(f"  ロール数: {len(cal_data)}")

    # 全 weight 値を列挙
    all_weights: set[float] = set()
    total_arcs = 0
    for role_uri, data in cal_data.items():
        for arc in data["arcs"]:
            all_weights.add(arc.weight)
            total_arcs += 1

    print(f"  総アーク数: {total_arcs}")
    print(f"  weight 値の種類: {sorted(all_weights)}")
    weight_counts: dict[float, int] = defaultdict(int)
    for data in cal_data.values():
        for arc in data["arcs"]:
            weight_counts[arc.weight] += 1
    for w in sorted(weight_counts.keys()):
        print(f"    weight={w:+g}: {weight_counts[w]} 件")

    # ロール一覧
    print(f"\n  ロール一覧:")
    for role_uri in sorted(cal_data.keys()):
        role_short = role_uri.split("/")[-1]
        arc_count = len(cal_data[role_uri]["arcs"])
        print(f"    {role_short}: {arc_count} arcs")

    # 2. Presentation との ロール URI 比較
    print(f"\n{'=' * 80}")
    print("【_cal.xml vs _pre.xml のロール URI 比較】")
    print(f"{'=' * 80}")

    cal_roles = set(extract_role_refs(SAMPLE_CAL))
    pre_roles = set(extract_role_refs(SAMPLE_PRE))

    # jppfs ロールのみフィルタ
    cal_jppfs = {r for r in cal_roles if "/jppfs/" in r}
    pre_jppfs = {r for r in pre_roles if "/jppfs/" in r}

    print(f"  _cal.xml jppfs ロール: {len(cal_jppfs)}")
    for r in sorted(cal_jppfs):
        print(f"    {r.split('/')[-1]}")
    print(f"  _pre.xml jppfs ロール: {len(pre_jppfs)}")
    for r in sorted(pre_jppfs):
        print(f"    {r.split('/')[-1]}")

    common = cal_jppfs & pre_jppfs
    cal_only = cal_jppfs - pre_jppfs
    pre_only = pre_jppfs - cal_jppfs
    print(f"\n  共通: {len(common)}")
    print(f"  _cal のみ: {len(cal_only)} {[r.split('/')[-1] for r in cal_only] if cal_only else ''}")
    print(f"  _pre のみ: {len(pre_only)} {[r.split('/')[-1] for r in pre_only] if pre_only else ''}")

    # 3. 連結 PL の計算ツリー
    pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
    if pl_role in cal_data:
        print(f"\n{'=' * 80}")
        print("【連結損益計算書 — 計算ツリー】")
        print(f"{'=' * 80}")
        data = cal_data[pl_role]
        roots = build_calc_tree(data["loc_map"], data["arcs"])
        print_calc_tree(roots)

    # 4. 連結 BS の計算ツリー（あれば）
    bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
    if bs_role in cal_data:
        print(f"\n{'=' * 80}")
        print("【連結貸借対照表 — 計算ツリー】")
        print(f"{'=' * 80}")
        data = cal_data[bs_role]
        roots = build_calc_tree(data["loc_map"], data["arcs"])
        print_calc_tree(roots)

    # 5. タクソノミの _cal.xml との比較
    if TAXONOMY_CAL_PL.exists():
        print(f"\n{'=' * 80}")
        print("【EDINET タクソノミ (cai) — PL 計算リンク】")
        print(f"ファイル: {TAXONOMY_CAL_PL.name}")
        print(f"{'=' * 80}")
        tax_data = parse_cal_file(TAXONOMY_CAL_PL)
        tax_weights: set[float] = set()
        tax_total = 0
        for data in tax_data.values():
            for arc in data["arcs"]:
                tax_weights.add(arc.weight)
                tax_total += 1
        print(f"  ロール数: {len(tax_data)}")
        print(f"  総アーク数: {tax_total}")
        print(f"  weight 値: {sorted(tax_weights)}")

    if TAXONOMY_CAL_BS.exists():
        print(f"\n{'=' * 80}")
        print("【EDINET タクソノミ (cai) — BS 計算リンク】")
        print(f"ファイル: {TAXONOMY_CAL_BS.name}")
        print(f"{'=' * 80}")
        tax_data = parse_cal_file(TAXONOMY_CAL_BS)
        tax_weights_bs: set[float] = set()
        tax_total_bs = 0
        for data in tax_data.values():
            for arc in data["arcs"]:
                tax_weights_bs.add(arc.weight)
                tax_total_bs += 1
        print(f"  ロール数: {len(tax_data)}")
        print(f"  総アーク数: {tax_total_bs}")
        print(f"  weight 値: {sorted(tax_weights_bs)}")


if __name__ == "__main__":
    main()

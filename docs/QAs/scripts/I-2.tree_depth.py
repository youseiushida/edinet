"""I-2. Presentation ツリー構造の解析スクリプト

サンプルインスタンスの _pre.xml をパースし、特定ロール（連結BS）のプレゼンテーション
ツリーを構築して、深さ・order・preferredLabel を表示する。

実行方法: uv run docs/QAs/scripts/I-2.tree_depth.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: ツリー構造（インデント表示）、深さ統計、preferredLabel 使用状況
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

# サンプルインスタンスのパス
SAMPLE_BASE = Path(__file__).resolve().parents[2] / "仕様書" / "2026" / "サンプルインスタンス" / "サンプルインスタンス" / "提出データ"
SAMPLE_02 = SAMPLE_BASE / "02_開示府令-有価証券報告書" / "XBRL" / "PublicDoc"
SAMPLE_PRE = SAMPLE_02 / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12_pre.xml"

# タクソノミの表示リンク（参考: EDINET タクソノミの連結BS）
TAXONOMY_PRE_BS = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "r" / "cai" / "jppfs_cai_ac_2025-11-01_pre_bs.xml"

NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

PARENT_CHILD = "http://www.xbrl.org/2003/arcrole/parent-child"


@dataclass
class PresentationArc:
    """presentationArc の情報を保持する。"""

    from_label: str
    to_label: str
    order: float
    preferred_label: str


@dataclass
class TreeNode:
    """ツリーノード。"""

    name: str
    order: float = 0.0
    preferred_label: str = ""
    children: list[TreeNode] = field(default_factory=list)


def extract_local_name(href: str) -> str:
    """href から要素のローカル名を抽出する。

    Args:
        href: xlink:href の値（例: ...xsd#jppfs_cor_Assets）

    Returns:
        ローカル名（#以降のプレフィックス除去後）。
    """
    if "#" in href:
        fragment = href.split("#", 1)[1]
        # プレフィックスを除去（jppfs_cor_Assets → Assets）
        parts = fragment.split("_")
        # 一般的なプレフィックス: jppfs_cor_, jpcrp_cor_, jpcrp030000-asr_X99001-000_
        # 安全策として、先頭の namespace-like 部分を除去
        if len(parts) >= 3 and parts[0] in ("jppfs", "jpcrp", "jpdei"):
            return "_".join(parts[2:])
        if "-" in parts[0]:
            # jpcrp030000-asr_X99001-000_ElementName パターン
            return "_".join(parts[2:]) if len(parts) >= 3 else fragment
        return fragment
    return href


def parse_presentation_link(xml_path: Path, target_role: str | None = None) -> dict[str, list[tuple[str, PresentationArc]]]:
    """_pre.xml をパースしてロール別のアーク一覧を抽出する。

    Args:
        xml_path: _pre.xml のパス。
        target_role: 特定ロールのみ抽出する場合に指定。None なら全ロール。

    Returns:
        ロール URI → (ロケータラベル→要素名マッピング用, アーク一覧) の辞書。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    results: dict[str, dict] = {}

    for plink in root.findall(f"{{{NS['link']}}}presentationLink"):
        role = plink.get(f"{{{NS['xlink']}}}role", "")
        if target_role and role != target_role:
            continue

        # ロケータ: label → href マッピング
        loc_map: dict[str, str] = {}
        for loc in plink.findall(f"{{{NS['link']}}}loc"):
            label = loc.get(f"{{{NS['xlink']}}}label", "")
            href = loc.get(f"{{{NS['xlink']}}}href", "")
            loc_map[label] = href

        # アーク
        arcs: list[PresentationArc] = []
        for arc in plink.findall(f"{{{NS['link']}}}presentationArc"):
            arcrole = arc.get(f"{{{NS['xlink']}}}arcrole", "")
            if arcrole != PARENT_CHILD:
                continue
            from_label = arc.get(f"{{{NS['xlink']}}}from", "")
            to_label = arc.get(f"{{{NS['xlink']}}}to", "")
            order = float(arc.get("order", "0"))
            preferred = arc.get("preferredLabel", "")
            arcs.append(PresentationArc(from_label, to_label, order, preferred))

        results[role] = {"loc_map": loc_map, "arcs": arcs}

    return results


def build_tree(loc_map: dict[str, str], arcs: list[PresentationArc]) -> list[TreeNode]:
    """アークからツリーを構築する。

    Args:
        loc_map: ロケータラベル → href のマッピング。
        arcs: PresentationArc のリスト。

    Returns:
        ルートノードのリスト。
    """
    # ラベル → 要素名
    label_to_name = {label: extract_local_name(href) for label, href in loc_map.items()}

    # 親 → 子リスト
    children_map: dict[str, list[PresentationArc]] = defaultdict(list)
    child_labels: set[str] = set()
    for arc in arcs:
        children_map[arc.from_label].append(arc)
        child_labels.add(arc.to_label)

    # ルートはどの子にもなっていないラベル
    all_parents = set(children_map.keys())
    root_labels = all_parents - child_labels

    def build_node(label: str, order: float = 0.0, preferred: str = "") -> TreeNode:
        """再帰的にノードを構築する。"""
        name = label_to_name.get(label, label)
        node = TreeNode(name=name, order=order, preferred_label=preferred)
        if label in children_map:
            sorted_arcs = sorted(children_map[label], key=lambda a: a.order)
            for arc in sorted_arcs:
                child = build_node(arc.to_label, arc.order, arc.preferred_label)
                node.children.append(child)
        return node

    roots = []
    for label in sorted(root_labels):
        roots.append(build_node(label))

    return roots


def print_tree(nodes: list[TreeNode], indent: int = 0, max_depth: int = 6) -> tuple[int, int, dict[int, int], dict[str, int]]:
    """ツリーをインデント表示し、統計を返す。

    Args:
        nodes: ノードリスト。
        indent: 現在のインデント深さ。
        max_depth: 表示する最大深さ。

    Returns:
        (総ノード数, 最大深さ, 深さ別ノード数, preferredLabel 使用頻度)。
    """
    total = 0
    max_d = indent
    depth_counts: dict[int, int] = defaultdict(int)
    pref_counts: dict[str, int] = defaultdict(int)

    for node in nodes:
        total += 1
        depth_counts[indent] += 1
        if indent > max_d:
            max_d = indent

        # preferredLabel の短縮表示
        pref_short = ""
        if node.preferred_label:
            pref_short = node.preferred_label.split("/")[-1]
            pref_counts[node.preferred_label] += 1

        if indent <= max_depth:
            prefix = "  " * indent
            order_str = f"[{node.order:.1f}]"
            pref_str = f" {{pref={pref_short}}}" if pref_short else ""
            print(f"{prefix}{order_str} {node.name}{pref_str}")

        if node.children:
            ct, md, dc, pc = print_tree(node.children, indent + 1, max_depth)
            total += ct
            if md > max_d:
                max_d = md
            for k, v in dc.items():
                depth_counts[k] += v
            for k, v in pc.items():
                pref_counts[k] += v

    return total, max_d, depth_counts, pref_counts


def analyze_file(xml_path: Path, label: str, target_role: str | None = None) -> None:
    """ファイルを解析して結果を表示する。

    Args:
        xml_path: _pre.xml のパス。
        label: 表示用ラベル。
        target_role: 特定ロール URI。None なら全ロール。
    """
    print(f"\n{'=' * 80}")
    print(f"【{label}】")
    print(f"ファイル: {xml_path.name}")
    print(f"{'=' * 80}")

    data = parse_presentation_link(xml_path, target_role)

    if not data:
        print("  (該当ロールなし)")
        return

    for role_uri, role_data in sorted(data.items()):
        role_short = role_uri.split("/")[-1] if "/" in role_uri else role_uri
        loc_map = role_data["loc_map"]
        arcs = role_data["arcs"]

        print(f"\n--- Role: {role_short} ---")
        print(f"  ロケータ数: {len(loc_map)}, アーク数: {len(arcs)}")

        roots = build_tree(loc_map, arcs)

        if roots:
            print(f"  ルートノード: {[r.name for r in roots]}")
            print()
            total, max_d, depth_counts, pref_counts = print_tree(roots)
            print(f"\n  --- 統計 ---")
            print(f"  総ノード数: {total}")
            print(f"  最大深さ: {max_d}")
            print(f"  深さ別ノード数:")
            for d in sorted(depth_counts.keys()):
                print(f"    深さ {d}: {depth_counts[d]} ノード")
            if pref_counts:
                print(f"  preferredLabel 使用状況:")
                for pl, count in sorted(pref_counts.items(), key=lambda x: -x[1]):
                    pl_short = pl.split("/")[-1] if "/" in pl else pl
                    print(f"    {pl_short}: {count} 回")
            else:
                print(f"  preferredLabel: 使用なし")


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("I-2. Presentation ツリー構造の解析")
    print("=" * 80)

    # 1. サンプルインスタンスの連結BS
    bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
    analyze_file(SAMPLE_PRE, "サンプルインスタンス — 連結貸借対照表", bs_role)

    # 2. サンプルインスタンスの連結PL
    pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
    analyze_file(SAMPLE_PRE, "サンプルインスタンス — 連結損益計算書", pl_role)

    # 3. タクソノミの連結BS（EDINET タクソノミ用 _std_ ロール）
    std_bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedBalanceSheet"
    if TAXONOMY_PRE_BS.exists():
        analyze_file(TAXONOMY_PRE_BS, "EDINET タクソノミ — 連結貸借対照表 (cai)", std_bs_role)
    else:
        print(f"\n(タクソノミファイル未検出: {TAXONOMY_PRE_BS})")

    # 4. サンプルインスタンスの全ロール一覧
    print(f"\n{'=' * 80}")
    print("【サンプルインスタンス — 全ロール一覧】")
    print(f"{'=' * 80}")
    all_data = parse_presentation_link(SAMPLE_PRE)
    for role_uri in sorted(all_data.keys()):
        role_short = role_uri.split("/")[-1] if "/" in role_uri else role_uri
        arcs = all_data[role_uri]["arcs"]
        locs = all_data[role_uri]["loc_map"]
        print(f"  {role_short}: ロケータ {len(locs)}, アーク {len(arcs)}")


if __name__ == "__main__":
    main()

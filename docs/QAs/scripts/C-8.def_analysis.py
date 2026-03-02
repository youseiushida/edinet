"""C-8. Definition Linkbase 構造解析スクリプト

サンプルインスタンスの _def.xml をパースし、arcrole一覧・ディメンション構造・
ハイパーキューブ構造を解析する。

実行方法: uv run docs/QAs/scripts/C-8.def_analysis.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: arcrole一覧、Axis/Domain/Member構造、ハイパーキューブ構造の実例
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
SAMPLE_DEF = SAMPLE_02 / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12_def.xml"

# タクソノミの定義リンク
TAXONOMY_DEF_BS = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "r" / "cai" / "jppfs_cai_ac_2025-11-01_def_bs.xml"

NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
    "xbrldt": "http://xbrl.org/2005/xbrldt",
}

# XBRL Dimensions arcrole URIs
ARCROLE_ALL = "http://xbrl.org/int/dim/arcrole/all"
ARCROLE_NOT_ALL = "http://xbrl.org/int/dim/arcrole/notAll"
ARCROLE_HYPERCUBE_DIM = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
ARCROLE_DIM_DOMAIN = "http://xbrl.org/int/dim/arcrole/dimension-domain"
ARCROLE_DIM_DEFAULT = "http://xbrl.org/int/dim/arcrole/dimension-default"
ARCROLE_DOMAIN_MEMBER = "http://xbrl.org/int/dim/arcrole/domain-member"
ARCROLE_GENERAL_SPECIAL = "http://www.xbrl.org/2003/arcrole/general-special"


@dataclass
class DefArc:
    """definitionArc の情報。"""

    from_label: str
    to_label: str
    arcrole: str
    order: float
    closed: str = ""
    context_element: str = ""
    usable: str = ""


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


def parse_def_file(xml_path: Path) -> dict[str, dict]:
    """_def.xml をパースしてロール別のデータを抽出する。

    Args:
        xml_path: _def.xml のパス。

    Returns:
        ロール URI → {"loc_map": ..., "arcs": ...} の辞書。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    results: dict[str, dict] = {}

    for dlink in root.findall(f"{{{NS['link']}}}definitionLink"):
        role = dlink.get(f"{{{NS['xlink']}}}role", "")

        loc_map: dict[str, str] = {}
        for loc in dlink.findall(f"{{{NS['link']}}}loc"):
            label = loc.get(f"{{{NS['xlink']}}}label", "")
            href = loc.get(f"{{{NS['xlink']}}}href", "")
            loc_map[label] = href

        arcs: list[DefArc] = []
        for arc in dlink.findall(f"{{{NS['link']}}}definitionArc"):
            from_label = arc.get(f"{{{NS['xlink']}}}from", "")
            to_label = arc.get(f"{{{NS['xlink']}}}to", "")
            arcrole = arc.get(f"{{{NS['xlink']}}}arcrole", "")
            order = float(arc.get("order", "0"))
            closed = arc.get(f"{{{NS['xbrldt']}}}closed", "")
            ctx_elem = arc.get(f"{{{NS['xbrldt']}}}contextElement", "")
            usable = arc.get(f"{{{NS['xbrldt']}}}usable", "")
            arcs.append(DefArc(from_label, to_label, arcrole, order, closed, ctx_elem, usable))

        results[role] = {"loc_map": loc_map, "arcs": arcs}

    return results


def arcrole_short(arcrole: str) -> str:
    """arcrole URI を短縮名にする。

    Args:
        arcrole: arcrole URI。

    Returns:
        短縮名。
    """
    if "/" in arcrole:
        return arcrole.split("/")[-1]
    return arcrole


def analyze_arcroles(data: dict[str, dict]) -> dict[str, int]:
    """全ロールの arcrole を集計する。

    Args:
        data: parse_def_file の結果。

    Returns:
        arcrole → 使用回数 の辞書。
    """
    counts: dict[str, int] = defaultdict(int)
    for role_data in data.values():
        for arc in role_data["arcs"]:
            counts[arc.arcrole] += 1
    return dict(counts)


def extract_dimensions(data: dict[str, dict]) -> dict[str, dict]:
    """全ロールから Axis（ディメンション）情報を抽出する。

    Args:
        data: parse_def_file の結果。

    Returns:
        Axis 名 → {"domains": [...], "default": ..., "roles": [...]} の辞書。
    """
    axes: dict[str, dict] = {}

    for role_uri, role_data in data.items():
        loc_map = role_data["loc_map"]
        label_to_name = {label: extract_local_name(href) for label, href in loc_map.items()}

        for arc in role_data["arcs"]:
            if arc.arcrole == ARCROLE_HYPERCUBE_DIM:
                axis_name = label_to_name.get(arc.to_label, arc.to_label)
                if axis_name not in axes:
                    axes[axis_name] = {"domains": [], "default": "", "roles": set(), "members": []}
                axes[axis_name]["roles"].add(role_uri)

            elif arc.arcrole == ARCROLE_DIM_DOMAIN:
                axis_name = label_to_name.get(arc.from_label, arc.from_label)
                domain_name = label_to_name.get(arc.to_label, arc.to_label)
                if axis_name in axes:
                    if domain_name not in axes[axis_name]["domains"]:
                        axes[axis_name]["domains"].append(domain_name)

            elif arc.arcrole == ARCROLE_DIM_DEFAULT:
                axis_name = label_to_name.get(arc.from_label, arc.from_label)
                default_name = label_to_name.get(arc.to_label, arc.to_label)
                if axis_name in axes:
                    axes[axis_name]["default"] = default_name

            elif arc.arcrole == ARCROLE_DOMAIN_MEMBER:
                parent_name = label_to_name.get(arc.from_label, arc.from_label)
                member_name = label_to_name.get(arc.to_label, arc.to_label)
                # メンバーは axis のドメインの子として記録
                for axis_info in axes.values():
                    if parent_name in axis_info["domains"]:
                        if member_name not in axis_info["members"]:
                            axes_for_member = [a for a, info in axes.items() if parent_name in info["domains"]]
                            for a in axes_for_member:
                                if member_name not in axes[a]["members"]:
                                    axes[a]["members"].append(member_name)

    return axes


def print_hypercube_example(data: dict[str, dict], target_role: str) -> None:
    """特定ロールのハイパーキューブ構造を表示する。

    Args:
        data: parse_def_file の結果。
        target_role: 対象ロール URI。
    """
    if target_role not in data:
        print(f"  (ロール {target_role.split('/')[-1]} なし)")
        return

    role_data = data[target_role]
    loc_map = role_data["loc_map"]
    label_to_name = {label: extract_local_name(href) for label, href in loc_map.items()}

    print(f"\n  ロール: {target_role.split('/')[-1]}")
    print(f"  ロケータ数: {len(loc_map)}, アーク数: {len(role_data['arcs'])}")

    # arcrole 別にアークを表示
    arcs_by_type: dict[str, list[DefArc]] = defaultdict(list)
    for arc in role_data["arcs"]:
        arcs_by_type[arc.arcrole].append(arc)

    for ar_uri in sorted(arcs_by_type.keys()):
        ar_short = arcrole_short(ar_uri)
        arcs_list = arcs_by_type[ar_uri]
        print(f"\n  [{ar_short}] ({len(arcs_list)} arcs)")
        for arc in sorted(arcs_list, key=lambda a: a.order):
            from_name = label_to_name.get(arc.from_label, arc.from_label)
            to_name = label_to_name.get(arc.to_label, arc.to_label)
            attrs = []
            if arc.closed:
                attrs.append(f"closed={arc.closed}")
            if arc.context_element:
                attrs.append(f"contextElement={arc.context_element}")
            if arc.usable:
                attrs.append(f"usable={arc.usable}")
            attr_str = f" ({', '.join(attrs)})" if attrs else ""
            print(f"    {from_name} → {to_name}{attr_str}")


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("C-8. Definition Linkbase 構造解析")
    print("=" * 80)

    # 1. サンプルインスタンスの _def.xml 解析
    print(f"\n{'=' * 80}")
    print(f"【サンプルインスタンスの _def.xml】")
    print(f"ファイル: {SAMPLE_DEF.name}")
    print(f"{'=' * 80}")

    def_data = parse_def_file(SAMPLE_DEF)
    print(f"  ロール数: {len(def_data)}")

    # 2. arcrole 一覧
    print(f"\n{'=' * 80}")
    print("【arcrole 一覧】")
    print(f"{'=' * 80}")
    arcrole_counts = analyze_arcroles(def_data)
    for ar_uri in sorted(arcrole_counts.keys()):
        print(f"  {arcrole_short(ar_uri):>25s}: {arcrole_counts[ar_uri]:>4d} 件  ({ar_uri})")

    # 3. ロール一覧
    print(f"\n{'=' * 80}")
    print("【ロール一覧（定義リンクロール数順）】")
    print(f"{'=' * 80}")
    for role_uri in sorted(def_data.keys()):
        role_short = role_uri.split("/")[-1]
        arcs_count = len(def_data[role_uri]["arcs"])
        locs_count = len(def_data[role_uri]["loc_map"])
        # arcrole 内訳
        ar_breakdown: dict[str, int] = defaultdict(int)
        for arc in def_data[role_uri]["arcs"]:
            ar_breakdown[arcrole_short(arc.arcrole)] += 1
        breakdown_str = ", ".join(f"{k}:{v}" for k, v in sorted(ar_breakdown.items()))
        print(f"  {role_short}: locs={locs_count}, arcs={arcs_count} ({breakdown_str})")

    # 4. ディメンション（Axis）一覧
    print(f"\n{'=' * 80}")
    print("【ディメンション（Axis）一覧】")
    print(f"{'=' * 80}")
    axes = extract_dimensions(def_data)
    for axis_name in sorted(axes.keys()):
        info = axes[axis_name]
        print(f"\n  Axis: {axis_name}")
        print(f"    Domain: {info['domains']}")
        print(f"    Default: {info['default']}")
        if info['members']:
            print(f"    Members: {info['members']}")
        print(f"    使用ロール数: {len(info['roles'])}")

    # 5. 連結 BS のハイパーキューブ構造例
    bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
    print(f"\n{'=' * 80}")
    print("【連結貸借対照表 — ハイパーキューブ構造】")
    print(f"{'=' * 80}")
    print_hypercube_example(def_data, bs_role)

    # 6. 科目一覧ツリー（general-special）の確認
    print(f"\n{'=' * 80}")
    print("【科目一覧ツリー (general-special) の確認】")
    print(f"{'=' * 80}")
    gs_count = 0
    gs_roles = []
    for role_uri, role_data in def_data.items():
        for arc in role_data["arcs"]:
            if arc.arcrole == ARCROLE_GENERAL_SPECIAL:
                gs_count += 1
                if role_uri not in gs_roles:
                    gs_roles.append(role_uri)
    print(f"  general-special アーク総数: {gs_count}")
    print(f"  使用ロール:")
    for r in gs_roles:
        print(f"    {r.split('/')[-1]}")

    # 7. タクソノミの _def.xml（あれば）
    if TAXONOMY_DEF_BS.exists():
        print(f"\n{'=' * 80}")
        print(f"【EDINET タクソノミ (cai) — BS 定義リンク】")
        print(f"ファイル: {TAXONOMY_DEF_BS.name}")
        print(f"{'=' * 80}")
        tax_data = parse_def_file(TAXONOMY_DEF_BS)
        tax_arcroles = analyze_arcroles(tax_data)
        print(f"  ロール数: {len(tax_data)}")
        for ar_uri in sorted(tax_arcroles.keys()):
            print(f"  {arcrole_short(ar_uri):>25s}: {tax_arcroles[ar_uri]:>4d} 件")


if __name__ == "__main__":
    main()

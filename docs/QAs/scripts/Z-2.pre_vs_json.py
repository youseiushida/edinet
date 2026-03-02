"""Z-2. Presentation Linkbase と手動 JSON の比較検証スクリプト

実行方法: uv run docs/QAs/scripts/Z-2.pre_vs_json.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要（例: /mnt/c/Users/nezow/Downloads/ALL_20251101）
出力: 1) _pre_*.xml から抽出した concept リストと pl/bs/cf_jgaap.json の差分比較
      2) 業種ディレクトリ一覧と各ディレクトリ内の _pre ファイル数
      3) deprecated concept の統計
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

# ── 設定 ──────────────────────────────────────────────────────────────
TAXONOMY_ROOT = Path(
    os.environ.get(
        "EDINET_TAXONOMY_ROOT",
        "/mnt/c/Users/nezow/Downloads/ALL_20251101",
    )
)
JPPFS_BASE = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01"
CNS_DIR = JPPFS_BASE / "r" / "cns"  # 一般事業会社・連結

# プロジェクトルートから JSON を参照
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "src" / "edinet" / "xbrl" / "data"

# XML 名前空間
NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

# ── ヘルパー ──────────────────────────────────────────────────────────

def parse_presentation_linkbase(xml_path: Path) -> list[dict]:
    """Presentation Linkbase XML をパースし、concept リストを返す。

    Args:
        xml_path: _pre_*.xml のパス。

    Returns:
        [{"concept": str, "order": float, "parent": str}, ...] のリスト。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # loc: label -> concept 名のマッピング
    loc_map: dict[str, str] = {}
    # arc: (from_label, to_label, order) のリスト
    arcs: list[tuple[str, str, float]] = []

    for pres_link in root.findall(".//link:presentationLink", NS):
        for loc in pres_link.findall("link:loc", NS):
            label = loc.get(f"{{{NS['xlink']}}}label", "")
            href = loc.get(f"{{{NS['xlink']}}}href", "")
            # href 例: ../../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales
            if "#" in href:
                fragment = href.split("#", 1)[1]
                # jppfs_cor_NetSales -> NetSales
                parts = fragment.split("_", 2)
                if len(parts) >= 3:
                    concept = parts[2]
                else:
                    concept = fragment
                loc_map[label] = concept

        for arc in pres_link.findall("link:presentationArc", NS):
            from_label = arc.get(f"{{{NS['xlink']}}}from", "")
            to_label = arc.get(f"{{{NS['xlink']}}}to", "")
            order = float(arc.get("order", "0"))
            arcs.append((from_label, to_label, order))

    # arc を使って (concept, order, parent) リストを構築
    results = []
    for from_label, to_label, order in arcs:
        concept = loc_map.get(to_label, to_label)
        parent = loc_map.get(from_label, from_label)
        results.append({
            "concept": concept,
            "order": order,
            "parent": parent,
        })

    return results


def load_json_concepts(json_path: Path) -> list[dict]:
    """JSON ファイルからコンセプトリストを読み込む。

    Args:
        json_path: JSON ファイルのパス。

    Returns:
        JSON の中身（リスト）。
    """
    with open(json_path) as f:
        return json.load(f)


def compare_concepts(
    pre_concepts: list[dict],
    json_concepts: list[dict],
    statement_type: str,
) -> None:
    """Presentation Linkbase の concept と JSON の concept を比較表示する。

    Args:
        pre_concepts: _pre_*.xml から抽出した concept リスト。
        json_concepts: JSON ファイルの concept リスト。
        statement_type: 財務諸表の種類（PL/BS/CF）。
    """
    # Abstract 以外で集計（Abstract は表示用ヘッダー）
    pre_set = {
        c["concept"] for c in pre_concepts
        if not c["concept"].endswith("Abstract")
        and not c["concept"].endswith("Table")
        and not c["concept"].endswith("LineItems")
        and not c["concept"].endswith("Axis")
        and not c["concept"].endswith("Member")
    }
    json_set = {c["concept"] for c in json_concepts}

    in_both = pre_set & json_set
    only_in_pre = pre_set - json_set
    only_in_json = json_set - pre_set

    print(f"\n{'=' * 70}")
    print(f"  {statement_type}: Presentation Linkbase vs JSON 比較")
    print(f"{'=' * 70}")
    print(f"  Presentation Linkbase: {len(pre_set)} concepts（Abstract/Table/Axis/Member 除外）")
    print(f"  JSON:                  {len(json_set)} concepts")
    print(f"  一致:                  {len(in_both)} concepts")
    print(f"  Presentation のみ:     {len(only_in_pre)} concepts")
    print(f"  JSON のみ:             {len(only_in_json)} concepts")

    if in_both:
        print(f"\n  --- 一致した concept ---")
        for c in sorted(in_both):
            print(f"    {c}")

    if only_in_pre:
        print(f"\n  --- Presentation にのみ存在（JSON に追加可能な候補） ---")
        for c in sorted(only_in_pre):
            print(f"    {c}")

    if only_in_json:
        print(f"\n  --- JSON にのみ存在（Presentation に不在） ---")
        for c in sorted(only_in_json):
            print(f"    {c}")


def show_pre_tree(concepts: list[dict], *, max_depth: int = 2) -> None:
    """Presentation の親子関係をツリー表示する。

    Args:
        concepts: parse_presentation_linkbase の出力。
        max_depth: 表示する最大深さ。
    """
    # parent -> [(order, concept)] のマッピング
    children: dict[str, list[tuple[float, str]]] = defaultdict(list)
    all_children = set()
    for c in concepts:
        children[c["parent"]].append((c["order"], c["concept"]))
        all_children.add(c["concept"])

    # ルート = parent にいるが children にいない
    roots = set(children.keys()) - all_children

    def _print_tree(node: str, depth: int, prefix: str = "") -> None:
        if depth > max_depth:
            return
        kids = sorted(children.get(node, []))
        for i, (order, child) in enumerate(kids):
            is_last = i == len(kids) - 1
            connector = "└── " if is_last else "├── "
            print(f"    {prefix}{connector}{child} (order={order})")
            next_prefix = prefix + ("    " if is_last else "│   ")
            _print_tree(child, depth + 1, next_prefix)

    for root in sorted(roots):
        print(f"    {root}")
        _print_tree(root, 0)


def count_industry_dirs() -> None:
    """業種ディレクトリ一覧と _pre ファイル数を表示する。"""
    r_dir = JPPFS_BASE / "r"
    if not r_dir.exists():
        print(f"  ディレクトリが見つかりません: {r_dir}")
        return

    print(f"\n{'=' * 70}")
    print(f"  業種ディレクトリ一覧（{r_dir}）")
    print(f"{'=' * 70}")

    # 業種コード -> 名前のマッピング（既知のもの）
    industry_names = {
        "bk1": "銀行業(第一種)",
        "bk2": "銀行業(第二種)",
        "cai": "生命保険業",
        "cmd": "商品取引所業",
        "cna": "損害保険業",
        "cns": "一般事業会社(連結)",
        "edu": "学校法人",
        "elc": "電気通信事業",
        "ele": "電気事業",
        "fnd": "ファンド",
        "gas": "ガス事業",
        "hwy": "高速道路事業",
        "in1": "保険業(第一種)",
        "in2": "保険業(第二種)",
        "inv": "投資運用業",
        "ivt": "投資信託",
        "lea": "リース業",
        "liq": "特定目的会社",
        "med": "医療法人",
        "rwy": "鉄道事業",
        "sec": "証券業",
        "spf": "特定目的信託",
        "wat": "水道事業",
    }

    total_pre = 0
    for subdir in sorted(r_dir.iterdir()):
        if not subdir.is_dir():
            continue
        code = subdir.name
        pre_files = list(subdir.glob("*_pre_*.xml"))
        cal_files = list(subdir.glob("*_cal_*.xml"))
        name = industry_names.get(code, "???")
        print(f"  {code} ({name:16s}): _pre={len(pre_files):2d}, _cal={len(cal_files):2d}")
        total_pre += len(pre_files)

    print(f"\n  合計 _pre ファイル数: {total_pre}")


def check_deprecated() -> None:
    """deprecated concept の統計を表示する。"""
    dep_dir = JPPFS_BASE / "deprecated"
    if not dep_dir.exists():
        print(f"  deprecated ディレクトリが見つかりません: {dep_dir}")
        return

    print(f"\n{'=' * 70}")
    print(f"  Deprecated Concepts（{dep_dir}）")
    print(f"{'=' * 70}")

    xsd_path = dep_dir / "jppfs_dep_2025-11-01.xsd"
    if not xsd_path.exists():
        print(f"  XSD が見つかりません: {xsd_path}")
        return

    tree = ET.parse(xsd_path)
    root = tree.getroot()
    xs_ns = "http://www.w3.org/2001/XMLSchema"

    elements = root.findall(f".//{{{xs_ns}}}element")
    print(f"  deprecated element 数: {len(elements)}")

    # 最初の 10 件を表示
    print(f"\n  --- 先頭 10 件 ---")
    for elem in elements[:10]:
        name = elem.get("name", "")
        sub_group = elem.get("substitutionGroup", "")
        print(f"    {name}  (substitutionGroup={sub_group})")

    # ラベルファイルの行数
    lab_path = dep_dir / "jppfs_dep_2025-11-01_lab.xml"
    if lab_path.exists():
        tree_lab = ET.parse(lab_path)
        labels = tree_lab.findall(".//{http://www.xbrl.org/2003/linkbase}label")
        print(f"\n  deprecated ラベル数（日本語）: {len(labels)}")


def check_order_consistency(
    pre_concepts: list[dict],
    json_concepts: list[dict],
    statement_type: str,
) -> None:
    """JSON の order と Presentation Linkbase の order の対応を比較する。

    Args:
        pre_concepts: _pre_*.xml から抽出した concept リスト。
        json_concepts: JSON ファイルの concept リスト。
        statement_type: 財務諸表の種類（PL/BS/CF）。
    """
    # Presentation: StatementOfIncomeLineItems 直下の concept と order
    line_items_parent = None
    for c in pre_concepts:
        if c["concept"].endswith("LineItems"):
            line_items_parent = c["concept"]
            break

    if not line_items_parent:
        # Table 直下を試す
        for c in pre_concepts:
            if c["concept"].endswith("Table"):
                line_items_parent = c["concept"]
                break

    pre_order_map: dict[str, float] = {}
    for c in pre_concepts:
        pre_order_map[c["concept"]] = c["order"]

    json_order_map: dict[str, int] = {
        c["concept"]: c["order"] for c in json_concepts
    }

    # 共通 concept について order を比較
    common = set(pre_order_map.keys()) & set(json_order_map.keys())
    if common:
        print(f"\n  --- {statement_type}: order 比較（共通 concept） ---")
        print(f"  {'concept':<50s} {'JSON':>6s} {'PRE':>6s}")
        for c in sorted(common, key=lambda x: json_order_map.get(x, 999)):
            j_order = json_order_map[c]
            p_order = pre_order_map[c]
            match = "✓" if j_order == int(p_order) else "≠"
            print(f"  {c:<50s} {j_order:>6d} {p_order:>6.1f}  {match}")


# ── メイン ────────────────────────────────────────────────────────────

def main() -> None:
    """メイン処理。"""
    print(f"EDINET_TAXONOMY_ROOT: {TAXONOMY_ROOT}")
    print(f"PROJECT_ROOT:         {PROJECT_ROOT}")
    print(f"DATA_DIR:             {DATA_DIR}")

    if not JPPFS_BASE.exists():
        print(f"ERROR: タクソノミが見つかりません: {JPPFS_BASE}")
        sys.exit(1)

    # ── 1. PL の比較 ────────────────────────────────────────────────
    pre_pl_path = CNS_DIR / "jppfs_cns_ac_2025-11-01_pre_pl.xml"
    json_pl_path = DATA_DIR / "pl_jgaap.json"

    if pre_pl_path.exists() and json_pl_path.exists():
        pre_pl = parse_presentation_linkbase(pre_pl_path)
        json_pl = load_json_concepts(json_pl_path)
        compare_concepts(pre_pl, json_pl, "PL（損益計算書）")
        show_pre_tree(pre_pl, max_depth=1)
        check_order_consistency(pre_pl, json_pl, "PL")
    else:
        print(f"  PL ファイルが見つかりません: pre={pre_pl_path.exists()}, json={json_pl_path.exists()}")

    # ── 2. BS の比較 ────────────────────────────────────────────────
    pre_bs_path = CNS_DIR / "jppfs_cns_ac_2025-11-01_pre_bs.xml"
    json_bs_path = DATA_DIR / "bs_jgaap.json"

    if pre_bs_path.exists() and json_bs_path.exists():
        pre_bs = parse_presentation_linkbase(pre_bs_path)
        json_bs = load_json_concepts(json_bs_path)
        compare_concepts(pre_bs, json_bs, "BS（貸借対照表）")
    else:
        print(f"  BS ファイルが見つかりません: pre={pre_bs_path.exists()}, json={json_bs_path.exists()}")

    # ── 3. CF の比較 ────────────────────────────────────────────────
    # CF は間接法を使用
    pre_cf_path = CNS_DIR / "jppfs_cns_ac_2025-11-01_pre_cf-in-3-CF-03-Method-Indirect.xml"
    json_cf_path = DATA_DIR / "cf_jgaap.json"

    if pre_cf_path.exists() and json_cf_path.exists():
        pre_cf = parse_presentation_linkbase(pre_cf_path)
        json_cf = load_json_concepts(json_cf_path)
        compare_concepts(pre_cf, json_cf, "CF（キャッシュフロー計算書・間接法）")
    else:
        print(f"  CF ファイルが見つかりません: pre={pre_cf_path.exists()}, json={json_cf_path.exists()}")

    # ── 4. 業種ディレクトリ一覧 ─────────────────────────────────────
    count_industry_dirs()

    # ── 5. deprecated 統計 ──────────────────────────────────────────
    check_deprecated()

    # ── 6. 自動生成可能性のサマリ ───────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  自動生成可能性サマリ")
    print(f"{'=' * 70}")
    print(f"  1. PL/BS/CF の concept リスト:     _pre_*.xml から完全自動生成可能")
    print(f"  2. 表示順序 (order):                presentationArc の order 属性で取得可能")
    print(f"  3. 親子関係（階層構造）:            parent-child arcrole で取得可能")
    print(f"  4. 業種別 concept セット:           r/{{業種コード}}/ の _pre_*.xml で取得可能")
    print(f"  5. ラベル（日本語/英語）:           _lab.xml / _lab-en.xml で取得可能（既に実装済み）")
    print(f"  6. 計算関係（weight, 加減算）:      _cal_*.xml で取得可能")
    print(f"  7. deprecated concept:              deprecated/ ディレクトリで取得可能")
    print(f"  8. 会計基準間マッピング:            *** 自動生成不可 ***（公式データなし）")


if __name__ == "__main__":
    main()

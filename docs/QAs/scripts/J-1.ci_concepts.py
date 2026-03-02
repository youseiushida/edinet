"""J-1. 包括利益計算書の concept 検索スクリプト。

実行方法: EDINET_TAXONOMY_ROOT=... EDINET_API_KEY=... uv run docs/QAs/scripts/J-1.ci_concepts.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要、EDINET_API_KEY が必要
出力: jppfs_cor から包括利益関連の element を抽出し、CI role の構造を表示
"""

from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ===========================================================================
# 共通ヘルパー
# ===========================================================================
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import extract_member, find_public_doc_members, get_zip  # noqa: E402

# ===========================================================================
# 定数
# ===========================================================================
TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])
JPPFS_COR_XSD = (
    TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "jppfs_cor_2025-11-01.xsd"
)
JPPFS_RT_XSD = (
    TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "jppfs_rt_2025-11-01.xsd"
)
JPPFS_R_DIR = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "r"

NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

# 検索対象キーワード
CI_KEYWORDS = [
    "ComprehensiveIncome",
    "OtherComprehensiveIncome",
    "Reclassification",
]

TOYOTA_DOC_ID = "S100VWVY"


# ===========================================================================
# Step 1: jppfs_cor XSD から包括利益関連 element を抽出
# ===========================================================================
def find_ci_elements(xsd_path: Path) -> list[dict[str, str]]:
    """jppfs_cor XSD から包括利益関連の element を抽出する。

    Args:
        xsd_path: jppfs_cor XSD ファイルのパス。

    Returns:
        各 element の属性情報を含む辞書のリスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    results: list[dict[str, str]] = []
    for elem in root.findall(f"{{{NS['xsd']}}}element"):
        name = elem.get("name", "")
        # キーワードにマッチするか判定
        if not any(kw.lower() in name.lower() for kw in CI_KEYWORDS):
            continue

        elem_type = elem.get("type", "")
        abstract = elem.get("abstract", "false")
        # substitutionGroup で item/tuple 判定
        subst = elem.get("substitutionGroup", "")
        # xbrli 属性
        period_type = elem.get(
            "{http://www.xbrl.org/2003/instance}periodType", ""
        )
        balance = elem.get(
            "{http://www.xbrl.org/2003/instance}balance", ""
        )

        results.append({
            "name": name,
            "type": elem_type,
            "abstract": abstract,
            "substitutionGroup": subst,
            "periodType": period_type,
            "balance": balance,
        })

    return results


# ===========================================================================
# Step 2: CI role の定義情報を取得
# ===========================================================================
def find_ci_role_types(xsd_path: Path) -> list[dict[str, str]]:
    """jppfs_rt XSD から CI 関連の roleType を抽出する。

    Args:
        xsd_path: jppfs_rt XSD ファイルのパス。

    Returns:
        CI 関連の roleType 情報を含む辞書のリスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    results: list[dict[str, str]] = []
    for rt in root.iter(f"{{{NS['link']}}}roleType"):
        role_uri = rt.get("roleURI", "")
        role_id = rt.get("id", "")
        definition_elem = rt.find(f"{{{NS['link']}}}definition")
        definition = (
            definition_elem.text.strip()
            if definition_elem is not None and definition_elem.text
            else ""
        )

        # CI 関連: ComprehensiveIncome を含む、または 包括利益 を含む
        if "comprehensiveincome" in role_id.lower() or "包括利益" in definition:
            results.append({
                "role_uri": role_uri,
                "role_id": role_id,
                "definition": definition,
            })

    return results


# ===========================================================================
# Step 3: CI プレゼンテーションリンクベースのツリー構造を解析
# ===========================================================================
def parse_presentation_tree(xml_path: Path) -> list[dict[str, str]]:
    """プレゼンテーションリンクベースからツリー構造を解析する。

    Args:
        xml_path: プレゼンテーションリンクベース XML ファイルのパス。

    Returns:
        プレゼンテーションアークの一覧（from, to, order）。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # loc 要素: label -> href (concept name)
    locs: dict[str, str] = {}
    for loc in root.iter(f"{{{NS['link']}}}loc"):
        label = loc.get(f"{{{NS['xlink']}}}label", "")
        href = loc.get(f"{{{NS['xlink']}}}href", "")
        # href から concept 名を抽出
        if "#" in href:
            concept = href.split("#")[-1]
        else:
            concept = href
        locs[label] = concept

    # presentationArc: from -> to
    arcs: list[dict[str, str]] = []
    for arc in root.iter(f"{{{NS['link']}}}presentationArc"):
        from_label = arc.get(f"{{{NS['xlink']}}}from", "")
        to_label = arc.get(f"{{{NS['xlink']}}}to", "")
        order = arc.get("order", "")

        from_concept = locs.get(from_label, from_label)
        to_concept = locs.get(to_label, to_label)

        arcs.append({
            "from": from_concept,
            "to": to_concept,
            "order": order,
        })

    return arcs


def build_tree_string(arcs: list[dict[str, str]], *, indent: int = 2) -> str:
    """アーク一覧からインデント付きツリー文字列を構築する。

    Args:
        arcs: プレゼンテーションアークの一覧。
        indent: インデント幅。

    Returns:
        ツリー表示文字列。
    """
    # 親子関係を構築
    children: dict[str, list[tuple[float, str]]] = {}
    all_children: set[str] = set()
    for arc in arcs:
        parent = arc["from"]
        child = arc["to"]
        order = float(arc["order"]) if arc["order"] else 0.0
        if parent not in children:
            children[parent] = []
        children[parent].append((order, child))
        all_children.add(child)

    # ルートを特定（親にはなるが、子にはならない要素）
    all_parents = set(children.keys())
    roots = all_parents - all_children

    # ツリーを再帰的に構築
    lines: list[str] = []

    def _walk(node: str, depth: int) -> None:
        """ツリーを再帰的に展開する。

        Args:
            node: 現在のノード名。
            depth: 現在の深さ。
        """
        prefix = " " * (indent * depth)
        # jppfs_cor_ プレフィクスを除去して見やすく
        short = node.replace("jppfs_cor_", "")
        lines.append(f"{prefix}{short}")
        if node in children:
            for _, child in sorted(children[node]):
                _walk(child, depth + 1)

    for root in sorted(roots):
        _walk(root, 0)

    return "\n".join(lines)


# ===========================================================================
# Step 4: Toyota filing で 1計算書方式 / 2計算書方式を検証
# ===========================================================================
def check_toyota_ci_approach(doc_id: str) -> None:
    """Toyota の filing をダウンロードし、CI の方式を判定する。

    提出者 XSD 内の roleRef / linkbaseRef、および XBRL インスタンス内の
    schemaRef / roleRef を検索し、CI role URI の使用有無を確認する。

    Args:
        doc_id: トヨタの書類管理番号。
    """
    print(f"\n{'=' * 70}")
    print(f"[Step 4] Toyota filing ({doc_id}) の CI 方式検証")
    print("=" * 70)

    zip_bytes = get_zip(doc_id)

    # XSD ファイル（提出者タクソノミ）を検索
    xsd_members = find_public_doc_members(zip_bytes, ".xsd")
    print(f"\n  提出者 XSD ファイル: {xsd_members}")

    # XBRL ファイルを検索
    xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")
    print(f"  XBRL ファイル: {xbrl_members}")

    # HTM ファイル (iXBRL) を検索
    htm_members = find_public_doc_members(zip_bytes, ".htm")
    ixbrl_members = [m for m in htm_members if "_ixbrl" in m.lower()]
    print(f"  iXBRL ファイル: {len(ixbrl_members)} 件")

    # 提出者 XSD を解析して roleType を確認
    ci_role_found = False
    pl_ci_role_found = False

    for xsd_member in xsd_members:
        content = extract_member(zip_bytes, xsd_member)
        text = content.decode("utf-8", errors="replace")

        # CI 関連 role URI を検索
        ci_2stmt_pattern = re.compile(
            r"ComprehensiveIncome", re.IGNORECASE
        )
        ci_matches = ci_2stmt_pattern.findall(text)
        if ci_matches:
            print(f"\n  --- {xsd_member} ---")
            # roleType 定義を詳細に検索
            for line in text.split("\n"):
                if "ComprehensiveIncome" in line or "包括利益" in line:
                    print(f"    {line.strip()}")

        # StatementOfComprehensiveIncome (2計算書方式の CI ロール)
        if "StatementOfComprehensiveIncome" in text:
            ci_role_found = True
        # StatementOfIncome + CI パターン (1計算書方式)
        if "StatementOfIncome" in text and "ComprehensiveIncome" in text:
            pl_ci_role_found = True

    # XBRL インスタンスからも確認
    for xbrl_member in xbrl_members:
        content = extract_member(zip_bytes, xbrl_member)
        text = content.decode("utf-8", errors="replace")

        # schemaRef / roleRef を検索
        role_refs = re.findall(
            r'roleURI="([^"]*ComprehensiveIncome[^"]*)"', text
        )
        if role_refs:
            print(f"\n  --- {xbrl_member} の roleRef ---")
            for rr in role_refs:
                print(f"    {rr}")

    # iXBRL からも確認
    for ixbrl_member in ixbrl_members[:3]:
        content = extract_member(zip_bytes, ixbrl_member)
        text = content.decode("utf-8", errors="replace")

        # CI 関連の role URI を検索
        ci_roles = re.findall(
            r'role="([^"]*(?:ComprehensiveIncome|包括利益)[^"]*)"',
            text,
            re.IGNORECASE,
        )
        if ci_roles:
            print(f"\n  --- {ixbrl_member} の CI role ---")
            for cr in sorted(set(ci_roles)):
                print(f"    {cr}")

        # 当期純利益から包括利益への遷移を検索
        oci_facts = re.findall(
            r'name="[^"]*(?:OtherComprehensiveIncome|ComprehensiveIncome)[^"]*"',
            text,
        )
        if oci_facts:
            print(f"\n  --- {ixbrl_member} の OCI/CI fact ---")
            for f in sorted(set(oci_facts))[:15]:
                print(f"    {f}")

    # 判定
    print(f"\n  --- 判定 ---")
    print(f"  StatementOfComprehensiveIncome (2計算書方式 CI ロール): "
          f"{'検出' if ci_role_found else '未検出'}")
    print(f"  StatementOfIncome + CI (1計算書方式 可能性): "
          f"{'検出' if pl_ci_role_found else '未検出'}")

    if ci_role_found and not pl_ci_role_found:
        print(f"  → 2計算書方式（PL と CI が別ロール）の可能性が高い")
    elif pl_ci_role_found and not ci_role_found:
        print(f"  → 1計算書方式（PL ロール内に CI を包含）の可能性が高い")
    elif ci_role_found and pl_ci_role_found:
        print(f"  → 両方のロールが検出。XSD には両方定義されるが、"
              f"実際に使用されるのはいずれか一方")


# ===========================================================================
# Step 5: CI リンクベースファイルのパターン一覧
# ===========================================================================
def list_ci_linkbase_patterns() -> None:
    """CI 関連リンクベースファイルのパターンを業種横断で一覧表示する。"""
    print(f"\n{'=' * 70}")
    print("[Step 5] CI 関連リンクベースファイルのパターン一覧")
    print("=" * 70)

    ci_patterns: dict[str, list[str]] = {}

    for industry_dir in sorted(JPPFS_R_DIR.iterdir()):
        if not industry_dir.is_dir():
            continue
        industry = industry_dir.name
        for f in sorted(industry_dir.iterdir()):
            fname = f.name
            # CI 関連ファイルを検索（CI- を含む、または _ci を含む）
            if "_ci" in fname.lower() or "-ci-" in fname.lower():
                # パターンを抽出（業種部分を除去）
                pattern = re.sub(
                    r"jppfs_[a-z0-9]+_", "jppfs_{ind}_", fname
                )
                if pattern not in ci_patterns:
                    ci_patterns[pattern] = []
                ci_patterns[pattern].append(industry)

    for pattern in sorted(ci_patterns.keys()):
        industries = ci_patterns[pattern]
        print(f"  {pattern}")
        print(f"    業種数: {len(industries)}, 例: {industries[:5]}")


# ===========================================================================
# メイン処理
# ===========================================================================
def main() -> None:
    """メイン処理。"""
    print("=" * 70)
    print("J-1. 包括利益計算書の concept 検索")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: jppfs_cor XSD から CI 関連 element を抽出
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"[Step 1] jppfs_cor XSD から CI 関連 element を抽出")
    print(f"  XSD: {JPPFS_COR_XSD}")
    print("=" * 70)

    elements = find_ci_elements(JPPFS_COR_XSD)
    print(f"\n  CI 関連 element 数: {len(elements)}")

    # abstract / non-abstract で分類
    abstract_elems = [e for e in elements if e["abstract"] == "true"]
    concrete_elems = [e for e in elements if e["abstract"] != "true"]

    print(f"  abstract: {len(abstract_elems)}, concrete: {len(concrete_elems)}")

    print(f"\n  --- abstract element ---")
    for e in sorted(abstract_elems, key=lambda x: x["name"]):
        print(f"    {e['name']}")

    print(f"\n  --- concrete element ---")
    print(f"  {'name':<75s} {'type':<30s} {'period':>8s} {'balance':>8s}")
    print(f"  {'-' * 75} {'-' * 30} {'-' * 8} {'-' * 8}")
    for e in sorted(concrete_elems, key=lambda x: x["name"]):
        print(
            f"  {e['name']:<75s} {e['type']:<30s} "
            f"{e['periodType']:>8s} {e['balance']:>8s}"
        )

    # キーワード別集計
    print(f"\n  --- キーワード別集計 ---")
    for kw in CI_KEYWORDS:
        matching = [e for e in elements if kw.lower() in e["name"].lower()]
        print(f"  '{kw}': {len(matching)} 件")

    # NetOfTax vs BeforeTax 分類
    net_of_tax = [e for e in elements if "NetOfTax" in e["name"]]
    before_tax = [e for e in elements if "BeforeTax" in e["name"]]
    neither = [
        e for e in elements
        if "NetOfTax" not in e["name"] and "BeforeTax" not in e["name"]
    ]
    print(f"\n  --- 税効果分類 ---")
    print(f"  NetOfTax サフィックス: {len(net_of_tax)} 件")
    print(f"  BeforeTax サフィックス: {len(before_tax)} 件")
    print(f"  どちらでもない: {len(neither)} 件")

    # ------------------------------------------------------------------
    # Step 2: CI role の定義情報
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"[Step 2] CI 関連 roleType の定義情報")
    print(f"  RT XSD: {JPPFS_RT_XSD}")
    print("=" * 70)

    ci_roles = find_ci_role_types(JPPFS_RT_XSD)
    print(f"\n  CI 関連 roleType 数: {len(ci_roles)}")

    for r in ci_roles:
        print(f"\n  role_id: {r['role_id']}")
        print(f"    URI: {r['role_uri']}")
        print(f"    Def: {r['definition']}")

    # PL ロールの中で「包括利益」を含むものも検索
    print(f"\n  --- PL ロールの中で「包括利益」を含むもの ---")
    tree = ET.parse(JPPFS_RT_XSD)
    root = tree.getroot()
    for rt in root.iter(f"{{{NS['link']}}}roleType"):
        role_id = rt.get("id", "")
        definition_elem = rt.find(f"{{{NS['link']}}}definition")
        definition = (
            definition_elem.text.strip()
            if definition_elem is not None and definition_elem.text
            else ""
        )
        if "StatementOfIncome" in role_id and "包括利益" in definition:
            print(f"  role_id: {role_id}")
            print(f"    Def: {definition}")

    # ------------------------------------------------------------------
    # Step 3: CI プレゼンテーションリンクベースのツリー構造
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("[Step 3] CI プレゼンテーションリンクベースのツリー構造 (cai 業種)")
    print("=" * 70)

    cai_dir = JPPFS_R_DIR / "cai"

    # 2計算書方式: CI-01 (TwoStatementsNetOfTax)
    ci_01_pre = (
        cai_dir
        / "jppfs_cai_ac_2025-11-01_pre_ci-4-CI-01-TwoStatementsNetOfTax.xml"
    )
    if ci_01_pre.exists():
        print(f"\n  --- 2計算書方式 / 税効果控除後 (CI-01) ---")
        print(f"  ファイル: {ci_01_pre.name}")
        arcs = parse_presentation_tree(ci_01_pre)
        tree_str = build_tree_string(arcs)
        for line in tree_str.split("\n"):
            print(f"    {line}")

    # 2計算書方式: CI-02 (TwoStatementsBeforeTax)
    ci_02_pre = (
        cai_dir
        / "jppfs_cai_ac_2025-11-01_pre_ci-4-CI-02-TwoStatementsBeforeTax.xml"
    )
    if ci_02_pre.exists():
        print(f"\n  --- 2計算書方式 / 税効果控除前 (CI-02) ---")
        print(f"  ファイル: {ci_02_pre.name}")
        arcs = parse_presentation_tree(ci_02_pre)
        tree_str = build_tree_string(arcs)
        for line in tree_str.split("\n"):
            print(f"    {line}")

    # 1計算書方式: PL-09-CI-1 (SingleStatementNetOfTax)
    pl_ci_1_pre = (
        cai_dir
        / "jppfs_cai_ac_2025-11-01_pre_pl-2-PL-09-CI-1-SingleStatementNetOfTax.xml"
    )
    if pl_ci_1_pre.exists():
        print(f"\n  --- 1計算書方式 / 税効果控除後 (PL-09-CI-1) ---")
        print(f"  ファイル: {pl_ci_1_pre.name}")
        print(f"  ※ PL ロール (ConsolidatedStatementOfIncome) 内に CI が追加される")
        arcs = parse_presentation_tree(pl_ci_1_pre)
        tree_str = build_tree_string(arcs)
        for line in tree_str.split("\n"):
            print(f"    {line}")

    # 1計算書方式: PL-09-CI-2 (SingleStatementBeforeTax)
    pl_ci_2_pre = (
        cai_dir
        / "jppfs_cai_ac_2025-11-01_pre_pl-2-PL-09-CI-2-SingleStatementBeforeTax.xml"
    )
    if pl_ci_2_pre.exists():
        print(f"\n  --- 1計算書方式 / 税効果控除前 (PL-09-CI-2) ---")
        print(f"  ファイル: {pl_ci_2_pre.name}")
        arcs = parse_presentation_tree(pl_ci_2_pre)
        tree_str = build_tree_string(arcs)
        for line in tree_str.split("\n"):
            print(f"    {line}")

    # 基本 CI プレゼンテーション（ci.xml: テーブル構造のみ）
    ci_base_pre = cai_dir / "jppfs_cai_ac_2025-11-01_pre_ci.xml"
    if ci_base_pre.exists():
        print(f"\n  --- CI 基本プレゼンテーション (ci.xml) ---")
        print(f"  ファイル: {ci_base_pre.name}")
        arcs = parse_presentation_tree(ci_base_pre)
        tree_str = build_tree_string(arcs)
        for line in tree_str.split("\n"):
            print(f"    {line}")

    # ------------------------------------------------------------------
    # Step 4: Toyota filing 検証
    # ------------------------------------------------------------------
    check_toyota_ci_approach(TOYOTA_DOC_ID)

    # ------------------------------------------------------------------
    # Step 5: CI リンクベースパターン一覧
    # ------------------------------------------------------------------
    list_ci_linkbase_patterns()

    # ------------------------------------------------------------------
    # サマリー
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("サマリー")
    print("=" * 70)
    print(f"  CI 関連 element 数 (jppfs_cor): {len(elements)}")
    print(f"    abstract: {len(abstract_elems)}, concrete: {len(concrete_elems)}")
    print(f"    NetOfTax: {len(net_of_tax)}, BeforeTax: {len(before_tax)}, "
          f"その他: {len(neither)}")
    print(f"  CI 関連 roleType 数 (jppfs_rt): {len(ci_roles)}")
    print(f"  全 element は jppfs_cor 名前空間に含まれる（別モジュールなし）")
    print(f"\n  1計算書方式 vs 2計算書方式:")
    print(f"    1計算書方式: PL ロール (StatementOfIncome) 内に OCI/CI を追加")
    print(f"      パターン名: PL-09-CI-1-SingleStatementNetOfTax (税効果控除後)")
    print(f"      パターン名: PL-09-CI-2-SingleStatementBeforeTax (税効果控除前)")
    print(f"    2計算書方式: 独立した CI ロール (StatementOfComprehensiveIncome)")
    print(f"      パターン名: CI-01-TwoStatementsNetOfTax (税効果控除後)")
    print(f"      パターン名: CI-02-TwoStatementsBeforeTax (税効果控除前)")
    print(f"\n  CI = Comprehensive Income（包括利益）")


if __name__ == "__main__":
    main()

"""E-1d. 直接法 vs 間接法のプレゼンテーションリンクベース比較スクリプト

実行方法: uv run docs/QAs/scripts/E-1d.cf_compare.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: 直接法/間接法の concept セット差異、role URI の違い、識別方法
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

BASE_DIR = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01"


def find_cf_pre_files(industry: str) -> dict[str, list[Path]]:
    """指定業種の CF プレゼンテーションファイルを検索し、直接法/間接法に分類する。

    Args:
        industry: 業種略号。

    Returns:
        {"direct": [...], "indirect": [...]} の辞書。
    """
    r_dir = BASE_DIR / "r" / industry
    result: dict[str, list[Path]] = {"direct": [], "indirect": []}

    if not r_dir.exists():
        return result

    for f in sorted(r_dir.glob("*_pre_cf*")):
        name = f.name.lower()
        if "direct" in name and "indirect" not in name:
            result["direct"].append(f)
        elif "indirect" in name:
            result["indirect"].append(f)

    return result


def extract_concepts_from_pre(file_path: Path) -> tuple[set[str], str]:
    """プレゼンテーションリンクベースから使用 concept セットと role URI を抽出する。

    Args:
        file_path: プレゼンテーションリンクベースファイルのパス。

    Returns:
        (concept セット, role URI) のタプル。
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    concepts: set[str] = set()
    role_uri = ""

    for pre_link in root.findall(f".//{{{NS['link']}}}presentationLink"):
        role = pre_link.get(f"{{{NS['xlink']}}}role", "")
        if role:
            role_uri = role

        for loc in pre_link.findall(f"{{{NS['link']}}}loc"):
            href = loc.get(f"{{{NS['xlink']}}}href", "")
            if "#" in href:
                concept = href.split("#")[-1]
                # プレフィックスを除去
                if "_" in concept:
                    parts = concept.split("_", 1)
                    if len(parts) > 1:
                        concept = parts[1]
                concepts.add(concept)

    return concepts, role_uri


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("E-1d. CF 直接法 vs 間接法 比較分析")
    print("=" * 80)

    # 複数の業種で比較
    industries = ["cai", "cns", "bk1"]

    for industry in industries:
        print(f"\n{'=' * 70}")
        print(f"【{industry} 業種 — CF プレゼンテーションファイル】")
        print(f"{'=' * 70}")

        cf_files = find_cf_pre_files(industry)

        if not cf_files["direct"] and not cf_files["indirect"]:
            print(f"  CF プレゼンテーションファイルが見つかりません")
            continue

        print(f"\n  直接法ファイル: {len(cf_files['direct'])} 件")
        for f in cf_files["direct"]:
            print(f"    {f.name}")

        print(f"  間接法ファイル: {len(cf_files['indirect'])} 件")
        for f in cf_files["indirect"]:
            print(f"    {f.name}")

        # 連結通期の直接法/間接法を比較
        direct_concepts: set[str] = set()
        direct_role = ""
        indirect_concepts: set[str] = set()
        indirect_role = ""

        # 通期連結の CF ファイルを選択（ac = 通期連結）
        for f in cf_files["direct"]:
            if "_ac_" in f.name or (not direct_concepts):
                concepts, role = extract_concepts_from_pre(f)
                if concepts:
                    direct_concepts = concepts
                    direct_role = role
                    print(f"\n  直接法分析対象: {f.name}")
                    break

        for f in cf_files["indirect"]:
            if "_ac_" in f.name or (not indirect_concepts):
                concepts, role = extract_concepts_from_pre(f)
                if concepts:
                    indirect_concepts = concepts
                    indirect_role = role
                    print(f"  間接法分析対象: {f.name}")
                    break

        if not direct_concepts or not indirect_concepts:
            print("  比較に必要なファイルが不足しています")
            continue

        # Role URI の比較
        print(f"\n--- Role URI ---")
        print(f"  直接法: {direct_role}")
        print(f"  間接法: {indirect_role}")

        # Concept セットの比較
        common = direct_concepts & indirect_concepts
        direct_only = direct_concepts - indirect_concepts
        indirect_only = indirect_concepts - direct_concepts

        print(f"\n--- Concept セット比較 ---")
        print(f"  直接法のみの concept: {len(direct_only)} 件")
        print(f"  間接法のみの concept: {len(indirect_only)} 件")
        print(f"  共通の concept: {len(common)} 件")

        print(f"\n  直接法のみ:")
        for c in sorted(direct_only):
            print(f"    + {c}")

        print(f"\n  間接法のみ:")
        for c in sorted(indirect_only):
            print(f"    + {c}")

        print(f"\n  共通:")
        for c in sorted(common):
            print(f"    = {c}")

    # role URI パターンの全体分析
    print("\n" + "=" * 80)
    print("【全業種の CF role URI パターン】")
    print("=" * 80)

    # jppfs_rt XSD から CF 関連の role URI を抽出
    rt_file = BASE_DIR / "jppfs_rt_2025-11-01.xsd"
    tree = ET.parse(rt_file)
    root = tree.getroot()

    cf_roles: list[tuple[str, str, str]] = []
    for rt in root.iter("{http://www.xbrl.org/2003/linkbase}roleType"):
        role_id = rt.get("id", "")
        role_uri = rt.get("roleURI", "")
        def_elem = rt.find("{http://www.xbrl.org/2003/linkbase}definition")
        definition = def_elem.text.strip() if def_elem is not None and def_elem.text else ""

        if "cashflow" in role_id.lower() or "cf" in role_id.lower():
            cf_roles.append((role_id, role_uri, definition))

    print(f"\n  CF 関連 roleType 数: {len(cf_roles)}")
    for role_id, role_uri, definition in sorted(cf_roles, key=lambda x: x[2]):
        method = "直接" if "direct" in role_id.lower() and "indirect" not in role_id.lower() else "間接" if "indirect" in role_id.lower() else "?"
        print(f"  [{method}] {definition}")
        print(f"         ID: {role_id}")

    # 識別方法のまとめ
    print("\n" + "=" * 80)
    print("【CF 直接法/間接法の識別方法まとめ】")
    print("=" * 80)
    print("""
  1. Role URI による識別（最も確実）:
     - 直接法: role URI に "-direct" を含む
       例: rol_std_ConsolidatedStatementOfCashFlows-direct
     - 間接法: role URI に "-indirect" を含む
       例: rol_std_ConsolidatedStatementOfCashFlows-indirect

  2. Concept セットの違い:
     - 直接法: 営業収入・営業支出などの直接的なキャッシュフロー科目を使用
     - 間接法: 税引前当期純利益からスタートし、減価償却費・運転資本変動等の調整項目を使用
     - 営業活動 CF セクションの concept が完全に異なる

  3. DEI 要素による識別:
     - DEI に直接法/間接法を示す要素は見当たらない
     - role URI が最も確実な識別方法

  4. ファイル命名パターン:
     - 直接法: *_cf-di-3-CF-01-Method-Direct*
     - 間接法: *_cf-in-3-CF-03-Method-Indirect*
""")


if __name__ == "__main__":
    main()

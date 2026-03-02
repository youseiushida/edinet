"""J-5. 修正再表示関連の要素検索スクリプト。

実行方法: EDINET_TAXONOMY_ROOT=... uv run docs/QAs/scripts/J-5.restatement_search.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: jppfs_cor および jpcrp_cor の XSD から Restatement, Retrospective,
      CumulativeEffect 関連要素を検索。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from xml.etree import ElementTree as ET

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

# 検索対象 XSD ファイル
XSDS = {
    "jppfs_cor": TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "jppfs_cor_2025-11-01.xsd",
    "jpcrp_cor": TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01" / "jpcrp_cor_2025-11-01.xsd",
}

# 検索キーワード（大文字小文字区別なし）
KEYWORDS = [
    "Restatement",
    "Retrospective",
    "CumulativeEffect",
    "AccountingChange",
    "PolicyChange",
]

# XSD 名前空間
XSD_NS = {"xsd": "http://www.w3.org/2001/XMLSchema"}


def search_elements(
    xsd_path: Path,
    keywords: list[str],
) -> list[dict]:
    """XSD ファイル内の要素を検索する。

    Args:
        xsd_path: XSD ファイルのパス。
        keywords: 検索キーワードのリスト。

    Returns:
        マッチした要素情報の辞書リスト。
    """
    if not xsd_path.exists():
        print(f"  WARNING: {xsd_path} が見つかりません")
        return []

    tree = ET.parse(xsd_path)
    root = tree.getroot()

    results = []
    pattern = re.compile("|".join(keywords), re.IGNORECASE)

    for elem in root.findall("xsd:element", XSD_NS):
        name = elem.get("name", "")
        if pattern.search(name):
            results.append({
                "name": name,
                "id": elem.get("id", ""),
                "type": elem.get("type", ""),
                "abstract": elem.get("abstract", "false"),
                "substitutionGroup": elem.get("substitutionGroup", ""),
                "periodType": elem.get(
                    "{http://www.xbrl.org/2003/instance}periodType", "",
                ),
                "balance": elem.get(
                    "{http://www.xbrl.org/2003/instance}balance", "",
                ),
            })

    return results


def categorize_element(elem_info: dict) -> str:
    """要素の種類を分類する。

    Args:
        elem_info: 要素情報の辞書。

    Returns:
        分類名。
    """
    sub_group = elem_info["substitutionGroup"]
    elem_type = elem_info["type"]
    abstract = elem_info["abstract"]

    if "dimensionItem" in sub_group:
        return "Dimension (軸)"
    if "domainItemType" in elem_type:
        return "Member (メンバー)"
    if abstract == "true" and "identifierItem" in sub_group:
        return "Heading (見出し)"
    if abstract == "true":
        return "Abstract"
    if "textBlockItemType" in elem_type:
        return "TextBlock (注記)"
    if "monetaryItemType" in elem_type:
        return "Monetary (金額)"
    if "stringItemType" in elem_type:
        return "String"
    return "Other"


def main() -> None:
    """メイン処理。"""
    print("J-5: 修正再表示関連の要素検索")
    print("=" * 70)
    print(f"TAXONOMY_ROOT: {TAXONOMY_ROOT}")
    print(f"検索キーワード: {KEYWORDS}")

    all_results: dict[str, list[dict]] = {}

    for schema_name, xsd_path in XSDS.items():
        print(f"\n\n{'=' * 70}")
        print(f"[{schema_name}] {xsd_path.name}")
        print(f"{'=' * 70}")

        results = search_elements(xsd_path, KEYWORDS)
        all_results[schema_name] = results

        if not results:
            print("  マッチなし")
            continue

        print(f"  マッチ数: {len(results)}")
        print()

        # カテゴリ別にグルーピング
        by_category: dict[str, list[dict]] = {}
        for r in results:
            cat = categorize_element(r)
            by_category.setdefault(cat, []).append(r)

        for cat, items in sorted(by_category.items()):
            print(f"  --- {cat} ({len(items)} 件) ---")
            for item in items:
                print(f"    {item['name']}")
                print(f"      type={item['type']}, periodType={item['periodType']}, "
                      f"balance={item['balance'] or 'N/A'}")
            print()

    # Step 2: Axis のメンバーを探す
    print(f"\n\n{'=' * 70}")
    print("[特記] Dimension 軸とそのメンバーの探索")
    print(f"{'=' * 70}")

    # RetrospectiveApplicationAndRetrospectiveRestatementAxis のメンバーを探す
    axis_name = "RetrospectiveApplicationAndRetrospectiveRestatementAxis"
    print(f"\n  軸: {axis_name}")

    # 定義リンクベースを検索
    def_files = list(
        (TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01").rglob("*_def*.xml")
    )
    print(f"  定義リンクベース数: {len(def_files)}")

    found_in_def = False
    for def_file in def_files:
        content = def_file.read_text(encoding="utf-8")
        if axis_name in content:
            found_in_def = True
            print(f"\n  検出: {def_file.relative_to(TAXONOMY_ROOT)}")

            # 軸の直後のメンバーを探す
            tree = ET.parse(def_file)
            root = tree.getroot()

            # 全リンクを走査して axis への参照を探す
            for link_elem in root.iter():
                label_attr = link_elem.get(
                    "{http://www.w3.org/1999/xlink}label", "",
                )
                href_attr = link_elem.get(
                    "{http://www.w3.org/1999/xlink}href", "",
                )
                if axis_name in (label_attr + href_attr):
                    print(f"    タグ: {link_elem.tag}")
                    print(f"    label: {label_attr}")
                    print(f"    href: {href_attr}")

    if not found_in_def:
        print(f"  定義リンクベースに {axis_name} が見つかりませんでした")
        print("  → この軸はXSDで定義されているが、定義リンクベースでメンバーが")
        print("    割り当てられていない可能性があります")

    # Step 3: ラベルを確認
    print(f"\n\n{'=' * 70}")
    print("[特記] 関連要素の日本語ラベル")
    print(f"{'=' * 70}")

    label_files = [
        TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "label" / "jppfs_2025-11-01_lab.xml",
        TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01" / "label" / "jpcrp_2025-11-01_lab.xml",
    ]

    label_keywords = [
        "Retrospective",
        "CumulativeEffect",
        "Restatement",
    ]
    label_pattern = re.compile("|".join(label_keywords))

    for label_file in label_files:
        if not label_file.exists():
            continue

        print(f"\n  ファイル: {label_file.name}")
        tree = ET.parse(label_file)
        root = tree.getroot()

        LINK_NS = "http://www.xbrl.org/2003/linkbase"
        XLINK_NS = "http://www.w3.org/1999/xlink"

        # ラベル要素を走査
        for label_elem in root.iter(f"{{{LINK_NS}}}label"):
            label_id = label_elem.get("id", "")
            if label_pattern.search(label_id):
                role = label_elem.get(f"{{{XLINK_NS}}}role", "")
                # 標準ラベルのみ表示
                if role == "http://www.xbrl.org/2003/role/label":
                    text = label_elem.text or ""
                    print(f"    {label_id}: {text}")

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    for schema_name, results in all_results.items():
        print(f"\n  [{schema_name}]")
        dims = [r for r in results if "dimensionItem" in r["substitutionGroup"]]
        moneys = [r for r in results if "monetaryItemType" in r["type"]]
        texts = [r for r in results if "textBlockItemType" in r["type"]]
        print(f"    Dimension 軸: {len(dims)} 件")
        for d in dims:
            print(f"      - {d['name']}")
        print(f"    金額要素: {len(moneys)} 件")
        for m in moneys:
            print(f"      - {m['name']}")
        print(f"    TextBlock: {len(texts)} 件")
        for t in texts:
            print(f"      - {t['name']}")


if __name__ == "__main__":
    main()

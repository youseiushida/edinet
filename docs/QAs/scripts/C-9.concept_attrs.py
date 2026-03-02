"""C-9. Concept 定義属性の全モジュール横断集計

実行方法: uv run docs/QAs/scripts/C-9.concept_attrs.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: 全モジュールの concept 属性（type, substitutionGroup, abstract, periodType, balance）分布
"""

import os
import re
from pathlib import Path
from collections import Counter

TAXONOMY_ROOT = Path(os.environ.get("EDINET_TAXONOMY_ROOT", r"C:\Users\nezow\Downloads\ALL_20251101"))


def parse_elements(filepath):
    """XSD ファイルから xsd:element 定義を抽出する。

    Args:
        filepath: XSD ファイルのパス

    Returns:
        属性辞書のリスト。各辞書は xsd:element タグの属性を格納する。
    """
    elements = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # xsd:element タグを正規表現で抽出（複数行にまたがる場合も対応）
    pattern = r"<xsd:element\s+([^>]+?)/?>"
    for match in re.finditer(pattern, content, re.DOTALL):
        attrs_str = match.group(1)
        attrs = {}
        for attr_match in re.finditer(r'(\S+?)="([^"]*)"', attrs_str):
            attrs[attr_match.group(1)] = attr_match.group(2)
        if "name" in attrs:
            elements.append(attrs)
    return elements


def main():
    """全モジュール横断で concept 属性の統計を収集・出力する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    # _cor_*.xsd ファイルを検索
    cor_files = []
    for root, dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if "_cor_" in f and f.endswith(".xsd"):
                cor_files.append(os.path.join(root, f))

    # _dep_*.xsd（廃止要素）ファイルも検索
    dep_files = []
    for root, dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if "_dep_" in f and f.endswith(".xsd"):
                dep_files.append(os.path.join(root, f))

    print("=" * 70)
    print("1. 対象ファイル一覧（_cor_*.xsd）")
    print("=" * 70)
    all_elements = []
    for filepath in sorted(cor_files):
        rel = os.path.relpath(filepath, taxonomy_dir)
        elements = parse_elements(filepath)
        print(f"  {rel}: {len(elements)} elements")
        for e in elements:
            e["_source"] = rel
        all_elements.extend(elements)

    print(f"\n  合計: {len(all_elements)} elements from {len(cor_files)} files")

    # _dep_*.xsd の要素数も参考表示
    print(f"\n  参考: _dep_*.xsd ファイル数: {len(dep_files)}")
    dep_total = 0
    for filepath in sorted(dep_files):
        rel = os.path.relpath(filepath, taxonomy_dir)
        elements = parse_elements(filepath)
        print(f"    {rel}: {len(elements)} elements")
        dep_total += len(elements)
    print(f"    廃止要素合計: {dep_total}")

    # 2. substitutionGroup 分布
    print("\n" + "=" * 70)
    print("2. substitutionGroup 分布")
    print("=" * 70)
    sg_counter = Counter(e.get("substitutionGroup", "NONE") for e in all_elements)
    for sg, count in sg_counter.most_common():
        print(f"  {sg}: {count}")

    # tuple の有無を確認
    tuples = [e for e in all_elements if e.get("substitutionGroup") == "xbrli:tuple"]
    if tuples:
        print(f"\n  xbrli:tuple が存在: {len(tuples)} 件")
        for t in tuples[:10]:
            print(f"    {t['_source']}: {t['name']}")
    else:
        print("\n  xbrli:tuple は存在しない")

    # 3. type 分布
    print("\n" + "=" * 70)
    print("3. type 分布")
    print("=" * 70)
    type_counter = Counter(e.get("type", "NONE") for e in all_elements)
    for t, count in type_counter.most_common():
        print(f"  {t}: {count}")

    # 4. abstract 分布
    print("\n" + "=" * 70)
    print("4. abstract 分布")
    print("=" * 70)
    abs_counter = Counter(e.get("abstract", "NONE") for e in all_elements)
    for a, count in abs_counter.most_common():
        print(f"  {a}: {count}")

    # 5. periodType 分布
    print("\n" + "=" * 70)
    print("5. periodType 分布")
    print("=" * 70)
    pt_counter = Counter(
        e.get("xbrli:periodType", "NONE") for e in all_elements
    )
    for pt, count in pt_counter.most_common():
        print(f"  {pt}: {count}")

    # 6. balance 分布
    print("\n" + "=" * 70)
    print("6. balance 分布")
    print("=" * 70)
    bal_counter = Counter(
        e.get("xbrli:balance", "NONE") for e in all_elements
    )
    for b, count in bal_counter.most_common():
        print(f"  {b}: {count}")

    # 7. nillable 分布
    print("\n" + "=" * 70)
    print("7. nillable 分布")
    print("=" * 70)
    nil_counter = Counter(e.get("nillable", "NONE") for e in all_elements)
    for n, count in nil_counter.most_common():
        print(f"  {n}: {count}")

    # 8. 非ASCII concept名チェック
    print("\n" + "=" * 70)
    print("8. 非ASCII concept名 チェック")
    print("=" * 70)
    non_ascii = []
    for e in all_elements:
        name = e.get("name", "")
        if not all(ord(c) < 128 for c in name):
            non_ascii.append((e["_source"], name))
    if non_ascii:
        print(f"  非ASCII名: {len(non_ascii)} 件")
        for src, name in non_ascii[:20]:
            print(f"    {src}: {name}")
    else:
        print("  全 concept 名が ASCII のみ")

    # 9. periodType x balance クロス集計（abstract=false のみ）
    print("\n" + "=" * 70)
    print("9. periodType x balance クロス集計（abstract=false のみ）")
    print("=" * 70)
    concrete = [e for e in all_elements if e.get("abstract") == "false"]
    cross = Counter(
        (
            e.get("xbrli:periodType", "NONE"),
            e.get("xbrli:balance", "NONE"),
        )
        for e in concrete
    )
    print(f"  {'periodType':<12} {'balance':<10} {'count':<8}")
    print(f"  {'-'*12} {'-'*10} {'-'*8}")
    for (pt, bal), count in sorted(cross.items()):
        print(f"  {pt:<12} {bal:<10} {count:<8}")

    # 10. type x abstract クロス集計
    print("\n" + "=" * 70)
    print("10. type x abstract クロス集計")
    print("=" * 70)
    cross2 = Counter(
        (e.get("type", "NONE"), e.get("abstract", "NONE"))
        for e in all_elements
    )
    print(f"  {'type':<40} {'abstract':<10} {'count':<8}")
    print(f"  {'-'*40} {'-'*10} {'-'*8}")
    for (t, a), count in sorted(cross2.items(), key=lambda x: -x[1]):
        print(f"  {t:<40} {a:<10} {count:<8}")

    # 11. モジュール別サマリー
    print("\n" + "=" * 70)
    print("11. モジュール別サマリー")
    print("=" * 70)
    modules = {}
    for e in all_elements:
        # パスからモジュール名を抽出
        parts = e["_source"].replace("\\", "/").split("/")
        mod = parts[0]
        if mod not in modules:
            modules[mod] = {
                "total": 0,
                "abstract": 0,
                "concrete": 0,
                "monetary": 0,
                "has_balance": 0,
            }
        modules[mod]["total"] += 1
        if e.get("abstract") == "true":
            modules[mod]["abstract"] += 1
        else:
            modules[mod]["concrete"] += 1
        if e.get("type") == "xbrli:monetaryItemType":
            modules[mod]["monetary"] += 1
        if e.get("xbrli:balance") in ("debit", "credit"):
            modules[mod]["has_balance"] += 1

    print(
        f"  {'module':<20} {'total':<8} {'abstract':<10} {'concrete':<10} "
        f"{'monetary':<10} {'has_balance':<12}"
    )
    print(
        f"  {'-'*20} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*12}"
    )
    for mod in sorted(modules.keys()):
        m = modules[mod]
        print(
            f"  {mod:<20} {m['total']:<8} {m['abstract']:<10} "
            f"{m['concrete']:<10} {m['monetary']:<10} {m['has_balance']:<12}"
        )

    # 12. 全属性名の完全リスト
    print("\n" + "=" * 70)
    print("12. xsd:element に出現する全属性名（_source を除く）")
    print("=" * 70)
    all_attr_names = set()
    for e in all_elements:
        all_attr_names.update(k for k in e.keys() if k != "_source")
    for attr in sorted(all_attr_names):
        print(f"  {attr}")

    # 13. periodType x type クロス集計（abstract=false, type=monetaryItemType のみ）
    print("\n" + "=" * 70)
    print("13. monetaryItemType の periodType 分布（abstract=false）")
    print("=" * 70)
    monetary = [
        e
        for e in all_elements
        if e.get("type") == "xbrli:monetaryItemType"
        and e.get("abstract") == "false"
    ]
    pt_bal_monetary = Counter(
        (
            e.get("xbrli:periodType", "NONE"),
            e.get("xbrli:balance", "NONE"),
        )
        for e in monetary
    )
    print(f"  {'periodType':<12} {'balance':<10} {'count':<8}")
    print(f"  {'-'*12} {'-'*10} {'-'*8}")
    for (pt, bal), count in sorted(pt_bal_monetary.items()):
        print(f"  {pt:<12} {bal:<10} {count:<8}")

    # 14. concept名のキャラクタセット詳細分析
    print("\n" + "=" * 70)
    print("14. concept名のキャラクタセット分析")
    print("=" * 70)
    char_set = set()
    name_lengths = []
    for e in all_elements:
        name = e.get("name", "")
        char_set.update(name)
        name_lengths.append(len(name))
    # 使用文字種のカテゴリ分け
    digits = sorted(c for c in char_set if c.isdigit())
    uppers = sorted(c for c in char_set if c.isupper())
    lowers = sorted(c for c in char_set if c.islower())
    others = sorted(c for c in char_set if not c.isalnum())
    print(f"  大文字: {''.join(uppers)}")
    print(f"  小文字: {''.join(lowers)}")
    print(f"  数字:   {''.join(digits)}")
    print(f"  その他: {others}")
    print(f"  名前の長さ: min={min(name_lengths)}, max={max(name_lengths)}, "
          f"avg={sum(name_lengths)/len(name_lengths):.1f}")
    # 最長の名前を表示
    longest = max(all_elements, key=lambda e: len(e.get("name", "")))
    print(f"  最長名: {longest['name']} ({len(longest['name'])}文字)")


if __name__ == "__main__":
    main()

"""C-10. リンクベース XML 構造の完全な例を抽出

実行方法: uv run docs/QAs/scripts/C-10.xml_examples.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: 4種類のリンクベースの XML 構造サマリーと属性分析
"""

import os
import re
from collections import Counter
from pathlib import Path

TAXONOMY_ROOT = Path(
    os.environ.get(
        "EDINET_TAXONOMY_ROOT",
        "/mnt/c/Users/nezow/Downloads/ALL_20251101"
        if os.path.exists("/mnt/c/Users/nezow/Downloads/ALL_20251101")
        else r"C:\Users\nezow\Downloads\ALL_20251101",
    )
)


def count_elements(filepath: Path) -> dict[str, int]:
    """XML ファイル内の主要要素をカウントする。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        要素名をキー、出現回数を値とする辞書
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    counts = {}
    for tag in [
        "link:loc",
        "link:presentationArc",
        "link:calculationArc",
        "link:definitionArc",
        "link:labelArc",
        "link:label ",
        "link:roleRef",
        "link:arcroleRef",
        "link:presentationLink",
        "link:calculationLink",
        "link:definitionLink",
        "link:labelLink",
    ]:
        counts[tag.strip()] = len(re.findall(rf"<{tag}", content))
    return counts


def analyze_xlink_labels(filepath: Path) -> list[str]:
    """xlink:label 属性値を抽出する。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        xlink:label 属性値のリスト（最初の30件）
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    labels = re.findall(r'xlink:label="([^"]+)"', content)
    return labels[:30]


def analyze_href_patterns(filepath: Path) -> Counter:
    """xlink:href のパスパターンを分析する。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        href パスパターンの出現回数カウンター
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    hrefs = re.findall(r'xlink:href="([^"]+)"', content)
    patterns = Counter()
    for href in hrefs:
        if "#" in href:
            path_part = href.split("#")[0]
            patterns[path_part] += 1
        else:
            patterns[href] += 1
    return patterns


def analyze_arcrole_values(filepath: Path) -> Counter:
    """xlink:arcrole 属性値を分析する。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        arcrole 値の出現回数カウンター
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    arcroles = re.findall(r'xlink:arcrole="([^"]+)"', content)
    return Counter(arcroles)


def analyze_preferredlabel(filepath: Path) -> Counter:
    """preferredLabel 属性値を分析する。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        preferredLabel 値の出現回数カウンター
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    labels = re.findall(r'preferredLabel="([^"]+)"', content)
    return Counter(labels)


def analyze_weight_values(filepath: Path) -> Counter:
    """weight 属性値を分析する。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        weight 値の出現回数カウンター
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    weights = re.findall(r'weight="([^"]+)"', content)
    return Counter(weights)


def analyze_def_special_attrs(filepath: Path) -> dict[str, Counter]:
    """定義リンクの特殊属性（closed, contextElement, usable）を分析する。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        属性名をキー、値の出現回数カウンターを値とする辞書
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    result = {}
    for attr in ["xbrldt:closed", "xbrldt:contextElement", "usable"]:
        values = re.findall(rf'{attr}="([^"]+)"', content)
        if values:
            result[attr] = Counter(values)
    return result


def analyze_label_roles(filepath: Path) -> Counter:
    """ラベルリソースの xlink:role 属性値を分析する。

    Args:
        filepath: 解析対象の XML ファイルパス

    Returns:
        ラベルロール URI の出現回数カウンター
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    # link:label 要素の xlink:role のみ抽出
    roles = re.findall(r"<link:label\s[^>]*xlink:role=\"([^\"]+)\"", content)
    return Counter(roles)


def main():
    """リンクベース XML 構造の分析を実行する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"
    jppfs_dir = taxonomy_dir / "jppfs" / "2025-11-01"
    r_dir = jppfs_dir / "r" / "cna"

    if not r_dir.exists():
        print(f"エラー: {r_dir} が存在しません")
        return

    print("=" * 80)
    print("1. Presentation リンクベース分析")
    print("=" * 80)

    pre_file = r_dir / "jppfs_cna_ac_2025-11-01_pre_bs.xml"
    if pre_file.exists():
        counts = count_elements(pre_file)
        print(f"  ファイル: {pre_file.name}")
        for tag, count in counts.items():
            if count > 0:
                print(f"    <{tag}>: {count}")

        print("\n  xlink:label サンプル:")
        labels = analyze_xlink_labels(pre_file)
        for lab in labels[:15]:
            print(f"    {lab}")

        print("\n  xlink:href パターン:")
        href_patterns = analyze_href_patterns(pre_file)
        for pat, count in href_patterns.most_common(5):
            print(f"    {pat}: {count}")

        print("\n  preferredLabel 値:")
        pref = analyze_preferredlabel(pre_file)
        for val, count in pref.most_common():
            print(f"    {val}: {count}")

    print("\n" + "=" * 80)
    print("2. Calculation リンクベース分析")
    print("=" * 80)

    cal_file = r_dir / "jppfs_cna_ac_2025-11-01_cal_bs.xml"
    if cal_file.exists():
        counts = count_elements(cal_file)
        print(f"  ファイル: {cal_file.name}")
        for tag, count in counts.items():
            if count > 0:
                print(f"    <{tag}>: {count}")

        print("\n  arcrole 値:")
        arcroles = analyze_arcrole_values(cal_file)
        for val, count in arcroles.most_common():
            print(f"    {val}: {count}")

        print("\n  weight 値:")
        weights = analyze_weight_values(cal_file)
        for val, count in weights.most_common():
            print(f"    {val}: {count}")

    print("\n" + "=" * 80)
    print("3. Definition リンクベース分析")
    print("=" * 80)

    def_file = r_dir / "jppfs_cna_ac_2025-11-01_def_bs.xml"
    if def_file.exists():
        counts = count_elements(def_file)
        print(f"  ファイル: {def_file.name}")
        for tag, count in counts.items():
            if count > 0:
                print(f"    <{tag}>: {count}")

        print("\n  arcrole 値:")
        arcroles = analyze_arcrole_values(def_file)
        for val, count in arcroles.most_common():
            print(f"    {val}: {count}")

        print("\n  特殊属性:")
        special = analyze_def_special_attrs(def_file)
        for attr, counter in special.items():
            for val, count in counter.most_common():
                print(f"    {attr}={val}: {count}")

    print("\n" + "=" * 80)
    print("4. Label リンクベース分析")
    print("=" * 80)

    lab_file = jppfs_dir / "label" / "jppfs_2025-11-01_lab.xml"
    if lab_file.exists():
        counts = count_elements(lab_file)
        print(f"  ファイル: {lab_file.name}")
        for tag, count in counts.items():
            if count > 0:
                print(f"    <{tag}>: {count}")

        print("\n  ラベルロール (xlink:role) 分布:")
        label_roles = analyze_label_roles(lab_file)
        for val, count in label_roles.most_common():
            print(f"    {val}: {count}")

    # 5. 全業種の pre ファイルの集計
    print("\n" + "=" * 80)
    print("5. 全業種 pre_bs.xml の loc/arc 件数比較（上位5業種）")
    print("=" * 80)

    results = []
    for industry_dir in sorted((jppfs_dir / "r").iterdir()):
        if not industry_dir.is_dir():
            continue
        pre = industry_dir / f"jppfs_{industry_dir.name}_ac_2025-11-01_pre_bs.xml"
        if pre.exists():
            c = count_elements(pre)
            results.append(
                (
                    industry_dir.name,
                    c.get("link:loc", 0),
                    c.get("link:presentationArc", 0),
                )
            )

    results.sort(key=lambda x: x[2], reverse=True)
    print(f"  {'業種':<6} {'loc件数':>8} {'arc件数':>8}")
    for name, loc, arc in results[:5]:
        print(f"  {name:<6} {loc:>8} {arc:>8}")
    print(f"  ... ({len(results)}業種)")
    if results:
        total_loc = sum(r[1] for r in results)
        total_arc = sum(r[2] for r in results)
        print(f"  合計    {total_loc:>8} {total_arc:>8}")

    # 6. xlink:label の loc 参照とフラグメントの対応
    print("\n" + "=" * 80)
    print("6. loc 要素の xlink:label と xlink:href フラグメントの対応")
    print("=" * 80)

    if pre_file.exists():
        with open(pre_file, "r", encoding="utf-8") as f:
            content = f.read()

        locs = re.findall(
            r'<link:loc\s[^>]*xlink:href="([^"]+)"\s*xlink:label="([^"]+)"', content
        )
        if not locs:
            locs = re.findall(
                r'<link:loc\s[^>]*xlink:label="([^"]+)"[^>]*xlink:href="([^"]+)"',
                content,
            )
            locs = [(href, label) for label, href in locs]

        print(f"  サンプル（最初の10件）:")
        for href, label in locs[:10]:
            fragment = href.split("#")[-1] if "#" in href else "(no fragment)"
            print(f"    label={label:40s} fragment={fragment}")

        # パターン確認: label == fragment の最後の部分か？
        match_count = 0
        for href, label in locs:
            fragment = href.split("#")[-1] if "#" in href else ""
            # fragment は jppfs_cor_XXX, label は XXX
            if fragment.endswith(label) or fragment == f"jppfs_cor_{label}":
                match_count += 1
        print(
            f"\n  xlink:label が fragment の concept 名部分と一致: {match_count}/{len(locs)} "
            f"({match_count * 100 // len(locs) if locs else 0}%)"
        )


if __name__ == "__main__":
    main()

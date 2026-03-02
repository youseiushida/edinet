"""C-11. リンクベースマージの実態調査

実行方法: uv run docs/QAs/scripts/C-11.merge_example.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
      + docs/仕様書/2026/サンプルインスタンス/ にサンプルインスタンスが存在すること
出力: 名称リンクにおける priority/prohibited の使用実態、
      及び標準タクソノミ・サンプル提出者別タクソノミの labelArc 属性分布
"""

import os
import re
from pathlib import Path
from collections import Counter

TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    "/mnt/c/Users/nezow/Downloads/ALL_20251101",
))
SAMPLE_ROOT = Path(
    r"/mnt/c/Users/nezow/OneDrive - Kyoto University"
    r"/ドキュメント/edinet/docs/仕様書/2026/サンプルインスタンス"
)


def analyze_label_arcs(filepath):
    """ラベルリンクベース内の labelArc の属性を分析する。

    Args:
        filepath: 分析対象のラベルリンクベースファイルのパス。

    Returns:
        分析結果の辞書。total_arcs, priorities, uses, prohibited_count を含む。
    """
    results = {
        "total_arcs": 0,
        "priorities": Counter(),
        "uses": Counter(),
        "prohibited_count": 0,
    }
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        arcs = re.findall(
            r"<link:labelArc[^>]*/?>|<link:labelArc[^>]*>[^<]*</link:labelArc>",
            content,
            re.DOTALL,
        )
        results["total_arcs"] = len(arcs)

        for arc in arcs:
            # priority 属性の抽出
            pri_match = re.search(r'priority="([^"]*)"', arc)
            if pri_match:
                results["priorities"][pri_match.group(1)] += 1
            else:
                results["priorities"]["(default/none)"] += 1

            # use 属性の抽出
            use_match = re.search(r'use="([^"]*)"', arc)
            if use_match:
                results["uses"][use_match.group(1)] += 1
                if use_match.group(1) == "prohibited":
                    results["prohibited_count"] += 1
            else:
                results["uses"]["(default/optional)"] += 1
    except Exception as e:
        results["error"] = str(e)

    return results


def scan_all_arcs_for_priority(dirpath, file_pattern):
    """指定ディレクトリ配下の全アークから priority/use="prohibited" を検索する。

    Args:
        dirpath: 検索対象のルートディレクトリ。
        file_pattern: 対象ファイルの正規表現パターン（拡張子等）。

    Returns:
        (priority > 0 のファイル数, prohibited を含むファイル数) のタプル。
    """
    high_pri_files = []
    prohibited_files = []

    for root, dirs, files in os.walk(dirpath):
        for f in files:
            if re.search(file_pattern, f):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    # labelArc 内の priority チェック
                    for m in re.finditer(
                        r"<link:labelArc[^>]*>", content
                    ):
                        arc_str = m.group(0)
                        pri = re.search(r'priority="(\d+)"', arc_str)
                        if pri and int(pri.group(1)) > 0:
                            rel = os.path.relpath(filepath, dirpath)
                            high_pri_files.append((rel, pri.group(1)))
                        use = re.search(r'use="prohibited"', arc_str)
                        if use:
                            rel = os.path.relpath(filepath, dirpath)
                            prohibited_files.append(rel)
                except Exception:
                    pass

    return high_pri_files, prohibited_files


def main():
    """メイン処理: 標準タクソノミとサンプル提出者別タクソノミの名称リンクを分析する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    # ========================================
    # 1. 標準タクソノミのラベルファイル分析
    # ========================================
    print("=" * 80)
    print("1. EDINET 標準タクソノミの labelArc 属性分布")
    print("=" * 80)

    total_files = 0
    total_arcs = 0
    all_priorities = Counter()
    all_uses = Counter()

    for root, dirs, files in os.walk(taxonomy_dir):
        for f in sorted(files):
            if f.endswith("_lab.xml") or f.endswith("_lab-en.xml"):
                filepath = os.path.join(root, f)
                results = analyze_label_arcs(filepath)
                if results["total_arcs"] > 0:
                    total_files += 1
                    total_arcs += results["total_arcs"]
                    all_priorities.update(results["priorities"])
                    all_uses.update(results["uses"])

    print(f"  分析ファイル数: {total_files}")
    print(f"  総 labelArc 数: {total_arcs}")
    print(f"  priority 分布: {dict(all_priorities)}")
    print(f"  use 分布:      {dict(all_uses)}")

    # ========================================
    # 2. 標準タクソノミで priority > 0 の検索
    # ========================================
    print("\n" + "=" * 80)
    print("2. 標準タクソノミの labelArc で priority > 0 を検索")
    print("=" * 80)

    high_pri, prohibited = scan_all_arcs_for_priority(
        taxonomy_dir, r"_lab(-en)?\.xml$"
    )
    if high_pri:
        for rel, pri in high_pri[:10]:
            print(f"  {rel}: priority={pri}")
    else:
        print("  priority > 0 の labelArc: なし")
        print("  → 標準タクソノミの labelArc は全て priority=0（デフォルト）")

    if prohibited:
        for rel in prohibited[:10]:
            print(f"  use='prohibited': {rel}")
    else:
        print("  use='prohibited' の labelArc: なし")

    # ========================================
    # 3. サンプル提出者別タクソノミのラベルファイル分析
    # ========================================
    print("\n" + "=" * 80)
    print("3. サンプル提出者別タクソノミの labelArc 属性分布")
    print("=" * 80)

    if SAMPLE_ROOT.exists():
        sub_total_files = 0
        sub_total_arcs = 0
        sub_priorities = Counter()
        sub_uses = Counter()

        for root, dirs, files in os.walk(SAMPLE_ROOT):
            for f in sorted(files):
                if (f.endswith("_lab.xml") or f.endswith("_lab-en.xml")
                        or f.endswith(".lab.xml") or f.endswith(".lab-en.xml")):
                    filepath = os.path.join(root, f)
                    results = analyze_label_arcs(filepath)
                    if results["total_arcs"] > 0:
                        sub_total_files += 1
                        sub_total_arcs += results["total_arcs"]
                        sub_priorities.update(results["priorities"])
                        sub_uses.update(results["uses"])

        print(f"  分析ファイル数: {sub_total_files}")
        print(f"  総 labelArc 数: {sub_total_arcs}")
        print(f"  priority 分布: {dict(sub_priorities)}")
        print(f"  use 分布:      {dict(sub_uses)}")

        # サンプル内で priority > 0 / prohibited を検索
        high_pri_sub, prohibited_sub = scan_all_arcs_for_priority(
            SAMPLE_ROOT, r"_lab(-en)?\.xml$|\.lab(-en)?\.xml$"
        )
        if high_pri_sub:
            print("\n  priority > 0 の例:")
            for rel, pri in high_pri_sub[:10]:
                print(f"    {rel}: priority={pri}")
        else:
            print("  priority > 0 の labelArc: なし")

        if prohibited_sub:
            print("  use='prohibited' の例:")
            for rel in prohibited_sub[:10]:
                print(f"    {rel}")
        else:
            print("  use='prohibited' の labelArc: なし")
    else:
        print(f"  サンプルディレクトリが存在しません: {SAMPLE_ROOT}")

    # ========================================
    # 4. サンプルの他リンク種別での priority 使用状況（参考）
    # ========================================
    print("\n" + "=" * 80)
    print("4. 参考: サンプル提出者別タクソノミの presentationArc/definitionArc/calculationArc")
    print("   における priority の使用状況")
    print("=" * 80)

    if SAMPLE_ROOT.exists():
        for arc_type in ["presentationArc", "definitionArc", "calculationArc"]:
            pri_found = []
            proh_found = []
            for root, dirs, files in os.walk(SAMPLE_ROOT):
                for f in files:
                    if f.endswith(".xml"):
                        filepath = os.path.join(root, f)
                        try:
                            with open(filepath, "r", encoding="utf-8") as fh:
                                content = fh.read()
                            for m in re.finditer(
                                rf"<link:{arc_type}[^>]*>", content
                            ):
                                arc_str = m.group(0)
                                pri = re.search(
                                    r'priority="(\d+)"', arc_str
                                )
                                if pri and int(pri.group(1)) > 0:
                                    rel = os.path.relpath(filepath, SAMPLE_ROOT)
                                    pri_found.append(
                                        (rel, pri.group(1), arc_str[:120])
                                    )
                                use = re.search(
                                    r'use="prohibited"', arc_str
                                )
                                if use:
                                    rel = os.path.relpath(filepath, SAMPLE_ROOT)
                                    proh_found.append(
                                        (rel, arc_str[:120])
                                    )
                        except Exception:
                            pass

            print(f"\n  {arc_type}:")
            if pri_found:
                print(f"    priority > 0: {len(pri_found)} 件")
                for rel, pri, snippet in pri_found[:3]:
                    print(f"      {rel}: priority={pri}")
                    print(f"        {snippet}...")
            else:
                print("    priority > 0: なし")

            if proh_found:
                print(f"    use='prohibited': {len(proh_found)} 件")
                for rel, snippet in proh_found[:3]:
                    print(f"      {rel}")
                    print(f"        {snippet}...")
            else:
                print("    use='prohibited': なし")

    # ========================================
    # 5. labelLink の拡張リンクロール確認
    # ========================================
    print("\n" + "=" * 80)
    print("5. 標準タクソノミとサンプル提出者の labelLink の拡張リンクロール比較")
    print("=" * 80)

    # 標準タクソノミの labelLink role
    std_roles = set()
    for root, dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if f.endswith("_lab.xml") or f.endswith("_lab-en.xml"):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    for m in re.finditer(
                        r'<link:labelLink[^>]*xlink:role="([^"]*)"', content
                    ):
                        std_roles.add(m.group(1))
                except Exception:
                    pass

    print(f"  標準タクソノミの labelLink ロール: {std_roles}")

    # サンプル提出者の labelLink role
    if SAMPLE_ROOT.exists():
        sub_roles = set()
        for root, dirs, files in os.walk(SAMPLE_ROOT):
            for f in files:
                if (f.endswith("_lab.xml") or f.endswith("_lab-en.xml")
                        or f.endswith(".lab.xml") or f.endswith(".lab-en.xml")):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", encoding="utf-8") as fh:
                            content = fh.read()
                        for m in re.finditer(
                            r'<link:labelLink[^>]*xlink:role="([^"]*)"',
                            content,
                        ):
                            sub_roles.add(m.group(1))
                    except Exception:
                        pass

        print(f"  提出者の labelLink ロール:       {sub_roles}")
        print(f"  共通ロール:                      {std_roles & sub_roles}")
        print(f"  → 同一 role URI の extendedLink が両方に存在する = "
              f"{'あり' if std_roles & sub_roles else 'なし'}")
        if std_roles & sub_roles:
            print("  → XBRL 2.1 マージルールの適用対象となる")


if __name__ == "__main__":
    main()

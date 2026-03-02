"""C-5. ラベルロール URI 頻度分析

実行方法: uv run docs/QAs/scripts/C-5.label_roles.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: ラベルリンクベース内の全ラベルロール URI と頻度
"""

import os
import re
from pathlib import Path
from collections import Counter


_default = r"C:\Users\nezow\Downloads\ALL_20251101"
_wsl = "/mnt/c/Users/nezow/Downloads/ALL_20251101"
_env = os.environ.get("EDINET_TAXONOMY_ROOT", "")
if _env:
    TAXONOMY_ROOT = Path(_env)
elif Path(_wsl).exists():
    TAXONOMY_ROOT = Path(_wsl)
else:
    TAXONOMY_ROOT = Path(_default)


def main():
    """メイン処理。ラベルリンクベースのロール分析を実行する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    # 1. jppfs 日本語ラベル分析
    lab_file = (
        taxonomy_dir / "jppfs" / "2025-11-01" / "label" / "jppfs_2025-11-01_lab.xml"
    )

    print("=" * 80)
    print("1. jppfs 日本語ラベル (jppfs_2025-11-01_lab.xml)")
    print("=" * 80)

    if lab_file.exists():
        with open(lab_file, "r", encoding="utf-8") as f:
            content = f.read()

        # ラベルロールをカウント
        roles = re.findall(r'xlink:role="([^"]+)"', content)
        # link ロールを除外（labelLink の xlink:role）
        label_roles = [
            r
            for r in roles
            if r != "http://www.xbrl.org/2003/role/link" and "xlink" not in r
        ]
        role_counter = Counter(label_roles)

        print(f"  ラベル要素数: {content.count('<link:label ')}")
        print(f"  loc 要素数: {content.count('<link:loc ')}")
        print(f"  labelArc 要素数: {content.count('<link:labelArc ')}")
        print(f"\n  ラベルロール URI 分布:")
        for role, count in role_counter.most_common():
            print(f"    {role}: {count}")
    else:
        print(f"  ファイルが見つかりません: {lab_file}")

    # 2. jppfs 英語ラベル分析
    lab_en_file = (
        taxonomy_dir
        / "jppfs"
        / "2025-11-01"
        / "label"
        / "jppfs_2025-11-01_lab-en.xml"
    )

    print("\n" + "=" * 80)
    print("2. jppfs 英語ラベル (jppfs_2025-11-01_lab-en.xml)")
    print("=" * 80)

    if lab_en_file.exists():
        with open(lab_en_file, "r", encoding="utf-8") as f:
            content = f.read()

        label_count = content.count("<link:label ")
        roles = re.findall(r'xlink:role="([^"]+)"', content)
        label_roles = [r for r in roles if r != "http://www.xbrl.org/2003/role/link"]
        role_counter = Counter(label_roles)

        print(f"  ラベル要素数: {label_count}")
        print(f"\n  ラベルロール URI 分布:")
        for role, count in role_counter.most_common():
            print(f"    {role}: {count}")
    else:
        print(f"  ファイルが見つかりません: {lab_en_file}")

    # 3. 全モジュールの _lab.xml ファイル
    print("\n" + "=" * 80)
    print("3. 全モジュールの _lab.xml ファイル")
    print("=" * 80)

    for root, dirs, files in os.walk(taxonomy_dir):
        for f in sorted(files):
            if (
                f.endswith("_lab.xml")
                and "deprecated" not in root.lower()
                and "dep" not in f
            ):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    label_count = content.count("<link:label ")
                    loc_count = content.count("<link:loc ")
                    rel = os.path.relpath(filepath, taxonomy_dir)
                    print(f"  {rel}: {label_count} labels, {loc_count} locs")
                except Exception:
                    pass

    # 4. extended link role チェック
    print("\n" + "=" * 80)
    print("4. ラベルリンクベースの extended link role")
    print("=" * 80)

    if lab_file.exists():
        with open(lab_file, "r", encoding="utf-8") as f:
            content = f.read()
        link_roles = re.findall(
            r"<link:labelLink[^>]*xlink:role=\"([^\"]+)\"", content
        )
        role_counter = Counter(link_roles)
        print("  labelLink の xlink:role 値:")
        for role, count in role_counter.most_common():
            print(f"    {role}: {count} 件")

    # 5. roleRef 一覧
    print("\n" + "=" * 80)
    print("5. roleRef 一覧（_lab.xml）")
    print("=" * 80)

    if lab_file.exists():
        with open(lab_file, "r", encoding="utf-8") as f:
            content = f.read()
        role_refs = re.findall(r'roleURI="([^"]+)"', content)
        for rr in sorted(set(role_refs)):
            print(f"  {rr}")

    # 6. 全モジュール横断の roleRef 一覧
    print("\n" + "=" * 80)
    print("6. 全モジュール横断: _lab.xml の roleRef 一覧")
    print("=" * 80)

    all_role_refs = set()
    for root, dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if f.endswith("_lab.xml"):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    role_refs = re.findall(r'roleURI="([^"]+)"', content)
                    all_role_refs.update(role_refs)
                except Exception:
                    pass

    for rr in sorted(all_role_refs):
        print(f"  {rr}")


if __name__ == "__main__":
    main()

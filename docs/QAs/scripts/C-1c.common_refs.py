"""C-1c. common モジュール参照調査

実行方法: uv run docs/QAs/scripts/C-1c.common_refs.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: iod namespace を import する全モジュールの一覧
"""

import os
import re
from pathlib import Path

_default = r"C:\Users\nezow\Downloads\ALL_20251101"
_linux_fallback = "/mnt/c/Users/nezow/Downloads/ALL_20251101"
_env = os.environ.get("EDINET_TAXONOMY_ROOT", _default)
TAXONOMY_ROOT = Path(_env) if Path(_env).exists() else Path(_linux_fallback)

IOD_NAMESPACE = "http://disclosure.edinet-fsa.go.jp/taxonomy/common/2013-08-31/iod"
IOD_SCHEMA = "identificationAndOrdering_2013-08-31.xsd"


def main():
    """メイン処理。iod namespace の内容と参照元を調査する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    # 1. common XSD の内容表示
    common_xsd = (
        taxonomy_dir
        / "common"
        / "2013-08-31"
        / "identificationAndOrdering_2013-08-31.xsd"
    )
    print("=" * 60)
    print("1. common/identificationAndOrdering_2013-08-31.xsd の内容")
    print("=" * 60)
    if common_xsd.exists():
        with open(common_xsd, "r", encoding="utf-8") as f:
            content = f.read()
        print(content)
        print(
            f"\n  ファイルサイズ: {len(content)} bytes, "
            f"行数: {len(content.splitlines())}"
        )
    else:
        print(f"  ファイルが見つかりません: {common_xsd}")

    # 2. iod namespace を import している XSD ファイルの検索
    print("\n" + "=" * 60)
    print("2. iod namespace を import する XSD ファイル一覧")
    print("=" * 60)

    importers = []
    xsd_count = 0
    for root, _dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if not f.endswith(".xsd"):
                continue
            xsd_count += 1
            filepath = os.path.join(root, f)
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    file_content = fh.read()
                    if IOD_NAMESPACE in file_content or IOD_SCHEMA in file_content:
                        rel = os.path.relpath(filepath, taxonomy_dir)
                        importers.append(rel)
            except Exception:
                pass

    print(f"  検索対象 XSD 数: {xsd_count}")
    print(f"  iod を import/参照する XSD 数: {len(importers)}")
    for imp in sorted(importers):
        print(f"    {imp}")

    # 3. _cor_ XSD のみに絞った参照一覧
    print("\n" + "=" * 60)
    print("3. _cor_ XSD のうち iod を import するもの")
    print("=" * 60)
    cor_importers = [i for i in importers if "_cor_" in i]
    print(f"  _cor_ XSD で iod を参照する数: {len(cor_importers)}")
    for imp in sorted(cor_importers):
        print(f"    {imp}")

    # 4. iod 要素の特徴分析
    print("\n" + "=" * 60)
    print("4. iod 要素の特徴分析")
    print("=" * 60)
    if common_xsd.exists():
        with open(common_xsd, "r", encoding="utf-8") as f:
            content = f.read()
        elements = re.findall(r'name="(\w+)"', content)
        abstracts = re.findall(r'abstract="(\w+)"', content)
        sub_groups = re.findall(r'substitutionGroup="([^"]+)"', content)
        types = re.findall(r'type="([^"]+)"', content)
        print(f"  定義された要素名: {elements}")
        print(f"  abstract 属性: {abstracts}")
        print(f"  substitutionGroup: {sub_groups}")
        print(f"  type: {types}")
        if all(a == "true" for a in abstracts):
            print("  → 全要素が abstract=true — Fact には出現しない")
        print(
            "\n  → identifierItem は xbrli:item の substitutionGroup に属する"
            " abstract 要素"
        )
        print(
            "  → 各モジュールの目次項目(Heading)要素が "
            "substitutionGroup='iod:identifierItem' として派生"
        )

    # 5. identifierItem を substitutionGroup に持つ要素の例を検索
    print("\n" + "=" * 60)
    print("5. substitutionGroup='iod:identifierItem' を持つ要素の例（先頭10件）")
    print("=" * 60)
    heading_examples = []
    for root, _dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if not f.endswith(".xsd"):
                continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    for line in fh:
                        if 'substitutionGroup="iod:identifierItem"' in line:
                            name_match = re.search(r'name="([^"]+)"', line)
                            if name_match:
                                rel = os.path.relpath(filepath, taxonomy_dir)
                                heading_examples.append(
                                    (rel, name_match.group(1))
                                )
                                if len(heading_examples) >= 10:
                                    break
            except Exception:
                pass
            if len(heading_examples) >= 10:
                break
        if len(heading_examples) >= 10:
            break

    for path, name in heading_examples:
        print(f"    {path}: {name}")


if __name__ == "__main__":
    main()

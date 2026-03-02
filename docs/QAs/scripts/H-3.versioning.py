"""H-3: タクソノミバージョニング調査。

deprecated XSD の要素一覧を取得し、
異なる年の提出書類の schemaRef バージョン部分を抽出し、
タクソノミ差分情報を解析する。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, "docs/QAs/scripts")
from _common import (
    extract_member,
    find_filings,
    find_public_doc_members,
    get_zip,
    print_filing_info,
)

TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
))

XSD_NS = "http://www.w3.org/2001/XMLSchema"

# ============================================================
# H-3.2: deprecated ディレクトリの内容
# ============================================================
print("=" * 70)
print("H-3.2: deprecated ディレクトリの要素解析")
print("=" * 70)

dep_modules = ["jppfs", "jpcrp", "jpigp"]
dep_stats: dict[str, int] = {}

for mod in dep_modules:
    # バージョンディレクトリを検索
    mod_dir = TAXONOMY_ROOT / "taxonomy" / mod
    if not mod_dir.exists():
        print(f"\n  {mod}: ディレクトリなし")
        continue

    for ver_dir in sorted(mod_dir.iterdir()):
        dep_dir = ver_dir / "deprecated"
        if not dep_dir.exists():
            continue

        dep_xsd_files = list(dep_dir.glob("*_dep_*.xsd"))
        if not dep_xsd_files:
            continue

        for dep_xsd in dep_xsd_files:
            print(f"\n--- {dep_xsd.relative_to(TAXONOMY_ROOT)} ---")
            tree = ET.parse(dep_xsd)
            root = tree.getroot()

            # targetNamespace
            tns = root.get("targetNamespace", "N/A")
            print(f"  targetNamespace: {tns}")

            # 要素数
            elements = root.findall(f"{{{XSD_NS}}}element")
            print(f"  要素数: {len(elements)}")
            dep_stats[f"{mod}/{ver_dir.name}"] = len(elements)

            # 最初の5要素
            for elem in elements[:5]:
                name = elem.get("name", "?")
                elem_type = elem.get("type", "?")
                print(f"    - {name} ({elem_type})")
            if len(elements) > 5:
                print(f"    ... 他 {len(elements) - 5} 要素")

            # ラベルファイルの存在確認
            lab_files = list(dep_dir.glob("*_lab*.xml"))
            print(f"  ラベルファイル: {[f.name for f in lab_files]}")

print("\n--- deprecated 要素数サマリ ---")
for key, count in sorted(dep_stats.items()):
    print(f"  {key}: {count} 要素")

# ============================================================
# H-3.4: 異なる年の提出書類のバージョン確認
# ============================================================
print(f"\n{'=' * 70}")
print("H-3.4: 各年の提出書類が参照するタクソノミバージョン")
print("=" * 70)

# 各年度の代表的な有価証券報告書を1件ずつ取得
# 有報は通常6月に提出される
sample_periods = [
    ("2025-06-01", "2025-06-30", "2025年6月"),
    ("2024-06-01", "2024-06-30", "2024年6月"),
    ("2023-06-01", "2023-06-30", "2023年6月"),
    ("2022-06-01", "2022-06-30", "2022年6月"),
    ("2021-06-01", "2021-06-30", "2021年6月"),
    ("2020-06-01", "2020-06-30", "2020年6月"),
]

version_results: list[tuple[str, str, str, list[str]]] = []

for start, end, label in sample_periods:
    print(f"\n--- {label} ---")
    try:
        filings = find_filings(
            doc_type="120",  # 有価証券報告書
            start=start, end=end,
            has_xbrl=True, max_results=3,
        )
        if not filings:
            print("  Filing なし")
            continue

        f = filings[0]
        print_filing_info(f, label=label)

        # XSD を取得してバージョンを抽出
        zip_bytes = get_zip(f.doc_id)
        xsd_members = find_public_doc_members(zip_bytes, ".xsd")
        if not xsd_members:
            print("  XSD なし")
            continue

        # 提出者 XSD を解析
        xsd_content = extract_member(zip_bytes, xsd_members[0])
        xsd_text = xsd_content.decode("utf-8")

        # schemaLocation からバージョン部分を抽出
        versions = re.findall(
            r'schemaLocation="[^"]*?/(\d{4}-\d{2}-\d{2})/[^"]*?"',
            xsd_text,
        )
        unique_versions = sorted(set(versions))
        print(f"  参照バージョン: {unique_versions}")
        version_results.append((label, f.filing_date, f.filer_name, unique_versions))

    except Exception as e:
        print(f"  エラー: {e}")

print("\n--- バージョン分布サマリ ---")
for label, fdate, fname, vers in version_results:
    print(f"  {label} ({fdate}, {fname}): {vers}")

# ============================================================
# H-3.6: 名前空間 URI のバージョン依存性
# ============================================================
print(f"\n{'=' * 70}")
print("H-3.6: 名前空間 URI にバージョン日付が含まれるか")
print("=" * 70)

# ローカルタクソノミの targetNamespace を確認
check_xsds = [
    "taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd",
    "taxonomy/jpcrp/2025-11-01/jpcrp_cor_2025-11-01.xsd",
    "taxonomy/jpigp/2025-11-01/jpigp_cor_2025-11-01.xsd",
    "taxonomy/jpdei/2013-08-31/jpdei_cor_2013-08-31.xsd",
    "taxonomy/common/2013-08-31/identificationAndOrdering_2013-08-31.xsd",
]

for xsd_rel in check_xsds:
    xsd_path = TAXONOMY_ROOT / xsd_rel
    if not xsd_path.exists():
        # Windowsパスの場合を試す
        xsd_path = Path(str(TAXONOMY_ROOT).replace("/", "\\")) / xsd_rel
        if not xsd_path.exists():
            print(f"  {xsd_rel}: ファイルなし")
            continue

    tree = ET.parse(xsd_path)
    root = tree.getroot()
    tns = root.get("targetNamespace", "N/A")
    print(f"  {xsd_rel}")
    print(f"    targetNamespace: {tns}")

    # バージョン日付が含まれるか
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", tns)
    if date_match:
        print(f"    バージョン日付: {date_match.group()} (含まれる)")
    else:
        print("    バージョン日付: なし")

# ============================================================
# H-3.8: タクソノミ差分情報の解析
# ============================================================
print(f"\n{'=' * 70}")
print("H-3.8: タクソノミ差分情報")
print("=" * 70)

diff_dir = Path(
    "docs/仕様書/2026/タクソノミ差分情報"
)
if diff_dir.exists():
    diff_files = sorted(diff_dir.glob("*.html")) + sorted(diff_dir.glob("*.htm"))
    print(f"  差分ファイル数: {len(diff_files)}")
    for f in diff_files[:10]:
        print(f"    - {f.name} ({f.stat().st_size:,} bytes)")
else:
    print(f"  差分ディレクトリなし: {diff_dir}")
    # 代替: deprecated 要素数で差分規模を推定
    print("  代替: deprecated 要素数から差分規模を推定")
    for key, count in sorted(dep_stats.items()):
        print(f"    {key}: {count} deprecated 要素（＝過去に削除/改名された概念数）")

# ============================================================
# H-3.9: deprecated 要素の名前パターン分析
# ============================================================
print(f"\n{'=' * 70}")
print("H-3.9: deprecated 要素の名前パターン分析")
print("=" * 70)

jppfs_dep = TAXONOMY_ROOT / "taxonomy/jppfs/2025-11-01/deprecated/jppfs_dep_2025-11-01.xsd"
if jppfs_dep.exists():
    tree = ET.parse(jppfs_dep)
    root = tree.getroot()
    elements = root.findall(f"{{{XSD_NS}}}element")

    # 特徴的なキーワード分析
    keywords: dict[str, int] = {}
    for elem in elements:
        name = elem.get("name", "")
        # MinorityInterests → NonControllingInterests への変更を示唆
        for kw in ["MinorityInterest", "NetIncome", "DeferredTax", "Deprecated",
                    "Provision", "Prior", "Amortization", "Capital"]:
            if kw in name:
                keywords[kw] = keywords.get(kw, 0) + 1

    print(f"  jppfs deprecated 要素数: {len(elements)}")
    print("  キーワード分布:")
    for kw, count in sorted(keywords.items(), key=lambda x: -x[1]):
        print(f"    {kw}: {count} 要素")

    # MinorityInterests 関連（代表的な改名例）
    mi_elements = [e.get("name") for e in elements if "MinorityInterest" in e.get("name", "")]
    print(f"\n  MinorityInterests 関連（改名例）: {len(mi_elements)} 要素")
    for name in mi_elements:
        print(f"    - {name}")

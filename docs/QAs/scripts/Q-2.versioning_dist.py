"""Q-2.5: 過去書類のタクソノミバージョン分布調査。

各年1件ずつ有価証券報告書をサンプリングし、
import の taxonomy バージョンを抽出してバージョン分布を確認する。
一般事業会社（sec_code あり）を優先的に取得する。
"""

from __future__ import annotations

import re
import sys

sys.path.insert(0, "docs/QAs/scripts")
from _common import (
    extract_member,
    find_filings,
    find_public_doc_members,
    get_zip,
    print_filing_info,
)

print("=" * 70)
print("Q-2.5: 各年の有報が参照するタクソノミバージョン分布")
print("=" * 70)

# 有価証券報告書は6月提出が多い（3月決算企業）
# 一般事業会社を取得するため sec_code ありでフィルタ
sample_periods = [
    ("2025-06-15", "2025-06-30", "2025年"),
    ("2024-06-15", "2024-06-30", "2024年"),
    ("2023-06-15", "2023-06-30", "2023年"),
    ("2022-06-15", "2022-06-30", "2022年"),
    ("2021-06-15", "2021-06-30", "2021年"),
    ("2020-06-15", "2020-06-30", "2020年"),
    ("2019-06-15", "2019-06-30", "2019年"),
    ("2018-06-15", "2018-06-30", "2018年"),
    ("2017-06-15", "2017-06-30", "2017年"),
]

results: list[dict] = []

for start, end, label in sample_periods:
    print(f"\n{'=' * 70}")
    print(f"{label}")
    print("=" * 70)

    try:
        filings = find_filings(
            doc_type="120",  # 有価証券報告書
            start=start, end=end,
            has_xbrl=True, max_results=20,
        )

        # sec_code がある（＝上場企業の）Filing を優先
        corp_filings = [f for f in filings if f.sec_code]
        if corp_filings:
            f = corp_filings[0]
        elif filings:
            f = filings[0]
        else:
            print("  Filing なし")
            continue

        print_filing_info(f, label=label)

        # XSD を取得
        zip_bytes = get_zip(f.doc_id)
        xsd_members = find_public_doc_members(zip_bytes, ".xsd")
        if not xsd_members:
            print("  XSD なし")
            continue

        xsd_content = extract_member(zip_bytes, xsd_members[0])
        xsd_text = xsd_content.decode("utf-8", errors="replace")

        # schemaLocation からバージョンと名前空間を抽出
        import_matches = re.findall(
            r'(?:namespace|schemaLocation)="([^"]*)"',
            xsd_text,
        )

        # より正確に: import 要素ごとに namespace と schemaLocation を取得
        import_pattern = re.compile(
            r'<(?:xsd:|xs:)?import\s+'
            r'(?:[^>]*?namespace="([^"]*)")?'
            r'[^>]*?schemaLocation="([^"]*)"'
            r'[^>]*/?>',
            re.DOTALL,
        )

        imports = import_pattern.findall(xsd_text)
        versions = set()
        edinet_imports = []

        for ns, sl in imports:
            ver_match = re.search(r'/(\d{4}-\d{2}-\d{2})/', sl)
            if ver_match:
                ver = ver_match.group(1)
                versions.add(ver)
                # EDINET URL かどうか
                is_edinet = "disclosure.edinet-fsa.go.jp" in sl
                is_xbrl = "xbrl.org" in sl
                edinet_imports.append({
                    "namespace": ns,
                    "schemaLocation": sl,
                    "version": ver,
                    "type": "EDINET" if is_edinet else ("XBRL" if is_xbrl else "OTHER"),
                })

        # EDINET のみのバージョン
        edinet_versions = {
            i["version"] for i in edinet_imports if i["type"] == "EDINET"
        }

        print(f"\n  EDINET タクソノミバージョン: {sorted(edinet_versions)}")
        print(f"  全バージョン（XBRL含む）: {sorted(versions)}")

        for imp in edinet_imports:
            sl_short = imp["schemaLocation"].split("/")[-1]
            print(f"    [{imp['type']}] {sl_short} (v{imp['version']})")

        results.append({
            "label": label,
            "filing_date": str(f.filing_date),
            "filer_name": f.filer_name,
            "edinet_versions": sorted(edinet_versions),
            "all_versions": sorted(versions),
        })

    except Exception as e:
        print(f"  エラー: {e}")
        import traceback
        traceback.print_exc()

# ============================================================
# サマリ
# ============================================================
print(f"\n{'=' * 70}")
print("バージョン分布サマリ")
print("=" * 70)

print(f"\n{'提出年':<8} {'提出日':<12} {'企業名':<20} {'EDINET バージョン'}")
print("-" * 80)
for r in results:
    name = r["filer_name"][:18] if r["filer_name"] else "N/A"
    vers = ", ".join(r["edinet_versions"])
    print(f"{r['label']:<8} {r['filing_date']:<12} {name:<20} {vers}")

# バージョンの一意リスト
all_edinet_vers = set()
for r in results:
    all_edinet_vers.update(r["edinet_versions"])

print(f"\n全期間で使用された EDINET バージョン: {sorted(all_edinet_vers)}")
print(f"バージョン数: {len(all_edinet_vers)}")

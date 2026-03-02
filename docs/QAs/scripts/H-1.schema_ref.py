"""H-1: schemaRef と linkbaseRef の調査。

P-1 の5件のテスト対象で .xbrl ファイルを解析し、
schemaRef の数、xsi:schemaLocation の有無、roleRef/arcroleRef の有無を確認する。
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

# ============================================================
# テスト対象 Filing の取得
# ============================================================
print("=" * 70)
print("H-1: schemaRef / linkbaseRef / roleRef / arcroleRef 調査")
print("=" * 70)

# P-1 の5件に近い Filing を取得
test_cases = [
    # (edinet_code, doc_type, start, end, label)
    ("E02144", "120", "2025-06-01", "2025-06-30", "トヨタ（有報）"),
    (None, "120", "2025-07-01", "2025-07-31", "一般企業（有報）"),
    (None, "120", "2024-06-01", "2024-06-30", "2024年企業（有報）"),
]

for edinet_code, doc_type, start, end, label in test_cases:
    print(f"\n{'=' * 70}")
    print(f"対象: {label}")
    print("=" * 70)

    try:
        filings = find_filings(
            edinet_code=edinet_code,
            doc_type=doc_type,
            start=start, end=end,
            has_xbrl=True, max_results=3,
        )
        if not filings:
            print("  Filing なし")
            continue

        f = filings[0]
        print_filing_info(f, label=label)

        # XBRL ファイルを取得
        zip_bytes = get_zip(f.doc_id)
        xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")

        if not xbrl_members:
            print("  .xbrl ファイルなし")
            continue

        for xbrl_name in xbrl_members[:1]:  # 最初の1件のみ
            print(f"\n--- {xbrl_name} ---")
            xbrl_bytes = extract_member(zip_bytes, xbrl_name)
            xbrl_text = xbrl_bytes.decode("utf-8", errors="replace")

            # H-1.1: schemaRef
            schema_refs = re.findall(
                r'<[^>]*schemaRef[^>]*xlink:href="([^"]*)"[^>]*/?>',
                xbrl_text,
            )
            print("\n  [H-1.1] schemaRef:")
            print(f"    数: {len(schema_refs)}")
            for href in schema_refs:
                is_relative = not href.startswith("http")
                print(f"    href: {href} ({'相対' if is_relative else '絶対'})")

            # H-1.2: linkbaseRef
            linkbase_refs = re.findall(
                r'<[^>]*linkbaseRef[^>]*xlink:href="([^"]*)"[^>]*/?>',
                xbrl_text,
            )
            print("\n  [H-1.2] linkbaseRef (インスタンス内):")
            print(f"    数: {len(linkbase_refs)}")
            for href in linkbase_refs[:5]:
                print(f"    href: {href}")
            if len(linkbase_refs) > 5:
                print(f"    ... 他 {len(linkbase_refs) - 5} 件")

            # H-1.4: xsi:schemaLocation
            schema_loc_match = re.search(
                r'xsi:schemaLocation="([^"]*)"',
                xbrl_text,
            )
            print("\n  [H-1.4] xsi:schemaLocation:")
            if schema_loc_match:
                sl_value = schema_loc_match.group(1)
                # スペース区切りで namespace-URL ペアを表示
                pairs = sl_value.split()
                print("    存在: YES")
                print(f"    値の長さ: {len(sl_value)} 文字")
                # ペア表示
                for i in range(0, len(pairs), 2):
                    if i + 1 < len(pairs):
                        print(f"    NS:  {pairs[i]}")
                        print(f"    URL: {pairs[i+1]}")
                    else:
                        print(f"    残り: {pairs[i]}")
            else:
                print("    存在: NO")

            # H-1.6: schemaRef の数（複数か）
            print(f"\n  [H-1.6] schemaRef 数: {len(schema_refs)}")
            if len(schema_refs) > 1:
                print("    *** 複数 schemaRef 検出 ***")
            else:
                print("    単一 schemaRef（標準的）")

            # H-1.7: roleRef / arcroleRef
            role_refs = re.findall(
                r'<[^>]*:?roleRef[^>]*roleURI="([^"]*)"[^>]*/?>',
                xbrl_text,
            )
            arcrole_refs = re.findall(
                r'<[^>]*:?arcroleRef[^>]*arcroleURI="([^"]*)"[^>]*/?>',
                xbrl_text,
            )
            print("\n  [H-1.7] roleRef:")
            print(f"    数: {len(role_refs)}")
            for uri in role_refs[:5]:
                print(f"    roleURI: {uri}")
            if len(role_refs) > 5:
                print(f"    ... 他 {len(role_refs) - 5} 件")

            print("\n  [H-1.7] arcroleRef:")
            print(f"    数: {len(arcrole_refs)}")
            for uri in arcrole_refs[:5]:
                print(f"    arcroleURI: {uri}")

            # ルート要素の最初の100文字を表示（名前空間宣言確認用）
            root_match = re.search(r'<xbrli?:xbrl\b[^>]*>', xbrl_text[:5000])
            if root_match:
                root_tag = root_match.group(0)
                print("\n  [追加] ルート要素の名前空間宣言:")
                # xmlns 属性を抽出
                ns_decls = re.findall(r'xmlns:?(\w*)="([^"]*)"', root_tag)
                for prefix, uri in ns_decls[:15]:
                    print(f"    xmlns:{prefix} = {uri}" if prefix else f"    xmlns = {uri}")

    except Exception as e:
        print(f"  エラー: {e}")
        import traceback
        traceback.print_exc()

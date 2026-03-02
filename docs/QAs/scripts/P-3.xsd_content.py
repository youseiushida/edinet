"""P-3. 提出者別タクソノミ XSD の内容確認スクリプト

実行方法: uv run docs/QAs/scripts/P-3.xsd_content.py
前提: EDINET_API_KEY 環境変数が必要
出力: .xsd ファイルの全内容（短い場合）または冒頭100行、
      xs:import URL、拡張要素定義、target namespace を強調
"""

from __future__ import annotations

import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    extract_member,
    find_filings,
    find_public_doc_members,
    get_zip,
    print_filing_info,
)

# トヨタの有報を対象とする
TARGET = {
    "edinet_code": "E02144",
    "doc_type": "120",
    "start": "2025-06-01",
    "end": "2025-07-31",
}

HEAD_LINES = 100


def decode_xml(raw: bytes) -> str:
    """XML/HTML バイト列をテキストにデコードする。

    Args:
        raw: デコード対象のバイト列。

    Returns:
        デコードされたテキスト。
    """
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw.decode("utf-8", errors="replace")


def analyze_xsd_file(zip_bytes: bytes, member: str) -> None:
    """XSD ファイルの内容を分析する。

    Args:
        zip_bytes: ZIP バイト列。
        member: メンバー名。
    """
    print(f"\n{'=' * 70}")
    print(f"ファイル: {member}")
    print(f"{'=' * 70}")

    raw = extract_member(zip_bytes, member)
    text = decode_xml(raw)
    lines = text.splitlines()
    total = len(lines)

    print(f"  サイズ: {len(raw):,} bytes")
    print(f"  総行数: {total}")

    # 全内容（100行以内の場合）または冒頭100行
    if total <= HEAD_LINES:
        print(f"\n  --- 全内容 ({total} 行) ---")
        for i, line in enumerate(lines, 1):
            display = line if len(line) <= 200 else line[:200] + "..."
            print(f"  {i:5d}: {display}")
    else:
        print(f"\n  --- 冒頭 {HEAD_LINES} 行 ---")
        for i, line in enumerate(lines[:HEAD_LINES], 1):
            display = line if len(line) <= 200 else line[:200] + "..."
            print(f"  {i:5d}: {display}")
        print(f"\n  ... (残り {total - HEAD_LINES} 行省略)")

    # targetNamespace の抽出
    print(f"\n  --- targetNamespace ---")
    tns_found = False
    for i, line in enumerate(lines, 1):
        match = re.search(r'targetNamespace="([^"]*)"', line)
        if match:
            print(f"  L.{i}: targetNamespace=\"{match.group(1)}\"")
            tns_found = True
    if not tns_found:
        print("  targetNamespace: 見つかりません")

    # xs:import の URL 一覧
    print(f"\n  --- xs:import ---")
    imports = []
    for i, line in enumerate(lines, 1):
        for match in re.finditer(
            r'<(?:xs|xsd):import\b[^>]*'
            r'(?:namespace="([^"]*)"[^>]*schemaLocation="([^"]*)"'
            r'|schemaLocation="([^"]*)"[^>]*namespace="([^"]*)")',
            line, re.IGNORECASE,
        ):
            ns = match.group(1) or match.group(4) or ""
            loc = match.group(2) or match.group(3) or ""
            imports.append((i, ns, loc))
        # xs:import が属性1つだけの場合のフォールバック
        if re.search(r'<(?:xs|xsd):import\b', line, re.IGNORECASE) and not any(
            i == imp[0] for imp in imports
        ):
            ns_match = re.search(r'namespace="([^"]*)"', line)
            loc_match = re.search(r'schemaLocation="([^"]*)"', line)
            ns_val = ns_match.group(1) if ns_match else ""
            loc_val = loc_match.group(1) if loc_match else ""
            if ns_val or loc_val:
                imports.append((i, ns_val, loc_val))

    if imports:
        for ln, ns, loc in imports:
            print(f"  L.{ln}:")
            print(f"    namespace    : {ns}")
            print(f"    schemaLocation: {loc}")
    else:
        print("  xs:import: 見つかりません")

    # 拡張要素定義 (xs:element) の一覧
    print(f"\n  --- 拡張要素定義 (xs:element) ---")
    elements = []
    for i, line in enumerate(lines, 1):
        for match in re.finditer(
            r'<(?:xs|xsd):element\b[^>]*name="([^"]*)"', line, re.IGNORECASE,
        ):
            elements.append((i, match.group(1)))

    if elements:
        print(f"  合計 {len(elements)} 要素")
        for ln, name in elements[:20]:  # 最大20要素
            print(f"  L.{ln}: {name}")
        if len(elements) > 20:
            print(f"  ... (残り {len(elements) - 20} 要素)")
    else:
        print("  xs:element: 見つかりません")

    # linkbaseRef の一覧
    print(f"\n  --- linkbaseRef ---")
    linkbases = []
    for i, line in enumerate(lines, 1):
        for match in re.finditer(
            r'<link:linkbaseRef\b[^>]*xlink:href="([^"]*)"', line, re.IGNORECASE,
        ):
            linkbases.append((i, match.group(1)))

    if linkbases:
        for ln, href in linkbases:
            print(f"  L.{ln}: {href}")
    else:
        print("  linkbaseRef: 見つかりません")

    # schemaRef の確認
    print(f"\n  --- schemaRef ---")
    schema_refs = []
    for i, line in enumerate(lines, 1):
        for match in re.finditer(
            r'<link:schemaRef\b[^>]*xlink:href="([^"]*)"', line, re.IGNORECASE,
        ):
            schema_refs.append((i, match.group(1)))

    if schema_refs:
        for ln, href in schema_refs:
            print(f"  L.{ln}: {href}")
    else:
        print("  schemaRef: (XSD 内では通常なし)")


def main() -> None:
    """メイン処理。"""
    print("P-3: 提出者別タクソノミ XSD の内容確認")
    print("=" * 70)

    # Filing 検索
    filings = find_filings(
        edinet_code=TARGET["edinet_code"],
        doc_type=TARGET["doc_type"],
        start=TARGET["start"],
        end=TARGET["end"],
        has_xbrl=True,
        max_results=1,
    )

    if not filings:
        print("ERROR: Filing が見つかりません")
        return

    filing = filings[0]
    print_filing_info(filing, label="P-3 対象 Filing")

    zip_bytes = get_zip(filing.doc_id)

    # PublicDoc 配下の .xsd ファイル
    xsd_members = find_public_doc_members(zip_bytes, ".xsd")
    print(f"\n[PublicDoc .xsd ファイル: {len(xsd_members)} 件]")

    if not xsd_members:
        print("  .xsd ファイルが見つかりません")
        return

    for member in xsd_members:
        try:
            analyze_xsd_file(zip_bytes, member)
        except Exception as exc:
            print(f"  ERROR: {member}: {type(exc).__name__}: {exc}")

    print(f"\n{'=' * 70}")
    print("P-3 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

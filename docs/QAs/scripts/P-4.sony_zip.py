"""P-4. IFRS 企業（ソニー E01777）の ZIP 構造調査スクリプト

実行方法: uv run docs/QAs/scripts/P-4.sony_zip.py
前提: EDINET_API_KEY 環境変数が必要
出力: ZIP ファイル一覧、主要 XBRL ファイルの冒頭100行、XSD の import 文、
      DEI セクション（AccountingStandardsDEI）
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
    print_zip_tree,
)


# ソニー E01777 の有報を対象
# FY2025（3月決算）→ 提出は 2025年6月頃
TARGETS = [
    {
        "label": "ソニー (E01777) — IFRS 適用企業",
        "edinet_code": "E01777",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-08-31",
    },
    # フォールバック: トヨタ (E02144) — IFRS 確認済み (P-3.a.md)
    {
        "label": "トヨタ (E02144) — IFRS 適用企業（フォールバック）",
        "edinet_code": "E02144",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-07-31",
    },
]

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


def print_head(text: str, *, head: int = HEAD_LINES) -> None:
    """テキストの冒頭を表示する。

    Args:
        text: 表示対象テキスト。
        head: 冒頭行数。
    """
    lines = text.splitlines()
    total = len(lines)
    print(f"  総行数: {total}")

    print(f"\n  --- 冒頭 {min(head, total)} 行 ---")
    for i, line in enumerate(lines[:head], 1):
        display = line if len(line) <= 200 else line[:200] + "..."
        print(f"  {i:5d}: {display}")

    if total > head:
        print(f"\n  ... (残り {total - head} 行省略) ...")


def print_xsd_imports(text: str) -> None:
    """XSD ファイルの import/include 文を抽出して表示する。

    Args:
        text: XSD ファイルのテキスト。
    """
    lines = text.splitlines()
    print("\n  --- import/include 文 ---")
    count = 0
    for i, line in enumerate(lines, 1):
        if re.search(r"<(xsd:|xs:)?import\b", line, re.IGNORECASE) or \
           re.search(r"<(xsd:|xs:)?include\b", line, re.IGNORECASE):
            display = line.strip()
            if len(display) > 200:
                display = display[:200] + "..."
            print(f"  {i:5d}: {display}")
            count += 1
    if count == 0:
        print("  (なし)")
    else:
        print(f"  計 {count} 件")


def print_dei_section(text: str) -> None:
    """AccountingStandardsDEI 周辺を表示する。

    Args:
        text: XBRL ファイルのテキスト。
    """
    lines = text.splitlines()
    print("\n  --- DEI 要素（AccountingStandards 周辺）---")
    for i, line in enumerate(lines, 1):
        if "AccountingStandards" in line:
            display = line.strip()
            if len(display) > 300:
                display = display[:300] + "..."
            print(f"  {i:5d}: {display}")

    # WhetherConsolidated も確認
    print("\n  --- DEI 要素（WhetherConsolidated 周辺）---")
    for i, line in enumerate(lines, 1):
        if "WhetherConsolidated" in line:
            display = line.strip()
            if len(display) > 300:
                display = display[:300] + "..."
            print(f"  {i:5d}: {display}")

    # TypeOfCurrentPeriod も確認
    print("\n  --- DEI 要素（TypeOfCurrentPeriod 周辺）---")
    for i, line in enumerate(lines, 1):
        if "TypeOfCurrentPeriod" in line:
            display = line.strip()
            if len(display) > 300:
                display = display[:300] + "..."
            print(f"  {i:5d}: {display}")


def print_namespace_summary(text: str) -> None:
    """名前空間宣言の要約を表示する。

    Args:
        text: XBRL ファイルのテキスト。
    """
    print("\n  --- 名前空間宣言の要約 ---")
    ns_pattern = re.compile(r'xmlns:(\w+)\s*=\s*"([^"]*)"')
    namespaces: dict[str, str] = {}
    for match in ns_pattern.finditer(text):
        prefix = match.group(1)
        uri = match.group(2)
        namespaces[prefix] = uri

    for prefix in sorted(namespaces):
        uri = namespaces[prefix]
        print(f"  {prefix:<20s} = {uri}")

    # IFRS 関連の名前空間を強調
    print("\n  --- IFRS/会計基準関連の名前空間 ---")
    for prefix, uri in sorted(namespaces.items()):
        if any(kw in uri.lower() for kw in ["jpigp", "jppfs", "ifrs", "usgaap", "jmis"]):
            print(f"  ★ {prefix:<20s} = {uri}")


def main() -> None:
    """メイン処理。"""
    print("P-4: IFRS 企業（ソニー）の ZIP 構造調査")
    print("=" * 70)

    filing = None
    for target in TARGETS:
        print(f"\n[検索] {target['label']}...")
        filings = find_filings(
            edinet_code=target["edinet_code"],
            doc_type=target["doc_type"],
            start=target["start"],
            end=target["end"],
            has_xbrl=True,
            max_results=1,
        )
        if filings:
            filing = filings[0]
            print_filing_info(filing, label="P-4 対象 Filing")
            break
        print(f"  → 見つかりませんでした")

    if filing is None:
        print("ERROR: IFRS 企業の Filing が見つかりません")
        return

    # 1. ZIP ファイル一覧
    zip_bytes = get_zip(filing.doc_id)
    print_zip_tree(zip_bytes, title="P-4.1: ZIP ファイル一覧")

    # 2. 主要 XBRL ファイルの冒頭100行
    xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")
    print(f"\n{'=' * 70}")
    print(f"P-4.2: 主要 XBRL ファイルの冒頭 {HEAD_LINES} 行")
    print(f"{'=' * 70}")

    if xbrl_members:
        # 最大のXBRLファイルを選択（メインのインスタンス）
        sizes = []
        for m in xbrl_members:
            raw = extract_member(zip_bytes, m)
            sizes.append((m, len(raw), raw))
        sizes.sort(key=lambda x: x[1], reverse=True)

        main_xbrl = sizes[0]
        print(f"\n  対象ファイル: {main_xbrl[0]} ({main_xbrl[1]:,} bytes)")
        text = decode_xml(main_xbrl[2])
        print_head(text)
        print_namespace_summary(text)
        print_dei_section(text)
    else:
        print("  ERROR: .xbrl ファイルが見つかりません")

    # 3. XSD ファイルの import 文
    xsd_members = find_public_doc_members(zip_bytes, ".xsd")
    print(f"\n{'=' * 70}")
    print("P-4.3: XSD ファイルの import 文")
    print(f"{'=' * 70}")

    for xsd_member in xsd_members:
        raw = extract_member(zip_bytes, xsd_member)
        text = decode_xml(raw)
        print(f"\n  ファイル: {xsd_member} ({len(raw):,} bytes)")
        print_xsd_imports(text)

    print(f"\n{'=' * 70}")
    print("P-4 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

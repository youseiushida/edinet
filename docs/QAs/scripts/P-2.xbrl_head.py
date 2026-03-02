"""P-2. XBRL/iXBRL ファイルの冒頭・構造確認スクリプト

実行方法: uv run docs/QAs/scripts/P-2.xbrl_head.py
前提: EDINET_API_KEY 環境変数が必要
出力: 主要 XBRL/iXBRL ファイルの冒頭200行・末尾50行、
      xbrli:context 周辺±30行、xbrli:unit 周辺±10行
"""

from __future__ import annotations

import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    extract_member,
    find_filings,
    find_members_by_ext,
    find_public_doc_members,
    get_zip,
    print_filing_info,
)

# トヨタの有報を対象とする（P-1a と同じ）
TARGET = {
    "edinet_code": "E02144",
    "doc_type": "120",
    "start": "2025-06-01",
    "end": "2025-07-31",
}

HEAD_LINES = 200
TAIL_LINES = 50
CONTEXT_WINDOW = 30
UNIT_WINDOW = 10


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


def print_head_tail(text: str, *, head: int = HEAD_LINES, tail: int = TAIL_LINES) -> None:
    """テキストの冒頭と末尾を表示する。

    Args:
        text: 表示対象テキスト。
        head: 冒頭行数。
        tail: 末尾行数。
    """
    lines = text.splitlines()
    total = len(lines)
    print(f"  総行数: {total}")

    print(f"\n  --- 冒頭 {head} 行 ---")
    for i, line in enumerate(lines[:head], 1):
        display = line if len(line) <= 200 else line[:200] + "..."
        print(f"  {i:5d}: {display}")

    if total > head + tail:
        print(f"\n  ... (省略: {total - head - tail} 行) ...")

    if total > head:
        start_idx = max(head, total - tail)
        print(f"\n  --- 末尾 {min(tail, total - head)} 行 ---")
        for i, line in enumerate(lines[start_idx:], start_idx + 1):
            display = line if len(line) <= 200 else line[:200] + "..."
            print(f"  {i:5d}: {display}")


def print_context_around(text: str, pattern: str, *, window: int, label: str) -> None:
    """パターンにマッチする行の周辺を表示する。

    Args:
        text: 検索対象テキスト。
        pattern: 検索パターン（大文字小文字区別なし）。
        window: 表示する前後行数。
        label: セクションラベル。
    """
    lines = text.splitlines()
    matches = [
        i for i, line in enumerate(lines)
        if re.search(pattern, line, re.IGNORECASE)
    ]

    if not matches:
        print(f"\n  --- {label}: マッチなし ---")
        return

    # 最初のマッチ周辺のみ表示
    first = matches[0]
    start = max(0, first - window)
    end = min(len(lines), first + window + 1)

    print(f"\n  --- {label} (初出: L.{first + 1}, 全{len(matches)}箇所) ---")
    for i in range(start, end):
        marker = " >>>" if i == first else "    "
        display = lines[i] if len(lines[i]) <= 200 else lines[i][:200] + "..."
        print(f"  {marker} {i + 1:5d}: {display}")


def analyze_xbrl_file(zip_bytes: bytes, member: str) -> None:
    """XBRL/iXBRL ファイルの内容を分析する。

    Args:
        zip_bytes: ZIP バイト列。
        member: メンバー名。
    """
    print(f"\n{'=' * 70}")
    print(f"ファイル: {member}")
    print(f"{'=' * 70}")

    raw = extract_member(zip_bytes, member)
    print(f"  サイズ: {len(raw):,} bytes")

    text = decode_xml(raw)
    print_head_tail(text)
    print_context_around(text, r"<xbrli:context", window=CONTEXT_WINDOW, label="xbrli:context 周辺")
    print_context_around(text, r"<xbrli:unit", window=UNIT_WINDOW, label="xbrli:unit 周辺")


def main() -> None:
    """メイン処理。"""
    print("P-2: XBRL/iXBRL ファイルの冒頭・構造確認")
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
    print_filing_info(filing, label="P-2 対象 Filing")

    zip_bytes = get_zip(filing.doc_id)

    # .xbrl ファイル（自動生成 XBRL インスタンス）
    xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")
    print(f"\n[PublicDoc .xbrl ファイル: {len(xbrl_members)} 件]")
    for member in xbrl_members[:3]:  # 最大3ファイル
        analyze_xbrl_file(zip_bytes, member)

    # .htm ファイル（iXBRL ファイル）
    htm_members = find_public_doc_members(zip_bytes, ".htm")
    print(f"\n[PublicDoc .htm ファイル: {len(htm_members)} 件]")
    for member in htm_members[:3]:  # 最大3ファイル
        analyze_xbrl_file(zip_bytes, member)

    print(f"\n{'=' * 70}")
    print("P-2 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

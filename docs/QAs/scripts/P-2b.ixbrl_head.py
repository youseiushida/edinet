"""P-2b. iXBRL (.htm) ファイルの冒頭・構造確認スクリプト

実行方法: uv run docs/QAs/scripts/P-2b.ixbrl_head.py
前提: EDINET_API_KEY 環境変数が必要
出力: .htm ファイルの冒頭100行、ix: 名前空間宣言、ix:header、ix:hidden の存在確認
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


def analyze_ixbrl_file(zip_bytes: bytes, member: str) -> None:
    """iXBRL .htm ファイルの内容を分析する。

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

    # 冒頭100行
    print(f"\n  --- 冒頭 {HEAD_LINES} 行 ---")
    for i, line in enumerate(lines[:HEAD_LINES], 1):
        display = line if len(line) <= 200 else line[:200] + "..."
        print(f"  {i:5d}: {display}")

    # ix: 名前空間宣言の検索
    print(f"\n  --- ix: 名前空間宣言 ---")
    ix_ns_found = False
    for i, line in enumerate(lines, 1):
        if re.search(r'xmlns:ix\b', line, re.IGNORECASE):
            print(f"  L.{i}: {line.strip()[:200]}")
            ix_ns_found = True
        if re.search(r'xmlns:ixt\b', line, re.IGNORECASE):
            print(f"  L.{i}: {line.strip()[:200]}")
    if not ix_ns_found:
        print("  ix: 名前空間宣言: 見つかりません")

    # ixt 関連の名前空間宣言
    print(f"\n  --- ixt 関連名前空間宣言 ---")
    ixt_found = False
    for i, line in enumerate(lines, 1):
        if re.search(r'xmlns:ixt', line, re.IGNORECASE):
            print(f"  L.{i}: {line.strip()[:200]}")
            ixt_found = True
    if not ixt_found:
        print("  ixt 名前空間: 見つかりません")

    # ix:header の存在確認
    print(f"\n  --- ix:header 存在確認 ---")
    header_lines = [
        (i, line) for i, line in enumerate(lines, 1)
        if re.search(r'<ix:header\b', line, re.IGNORECASE)
    ]
    if header_lines:
        for ln, line in header_lines:
            print(f"  L.{ln}: {line.strip()[:200]}")
            # ix:header 周辺を表示
            start = max(0, ln - 1 - 5)
            end = min(total, ln + 20)
            print(f"  (周辺 L.{start + 1}-{end}):")
            for j in range(start, end):
                marker = " >>>" if j == ln - 1 else "    "
                display = lines[j] if len(lines[j]) <= 200 else lines[j][:200] + "..."
                print(f"  {marker} {j + 1:5d}: {display}")
    else:
        print("  ix:header: 見つかりません")

    # ix:hidden の存在確認
    print(f"\n  --- ix:hidden 存在確認 ---")
    hidden_lines = [
        (i, line) for i, line in enumerate(lines, 1)
        if re.search(r'<ix:hidden\b', line, re.IGNORECASE)
    ]
    if hidden_lines:
        for ln, line in hidden_lines:
            print(f"  L.{ln}: {line.strip()[:200]}")
            # ix:hidden 周辺を表示
            start = max(0, ln - 1 - 3)
            end = min(total, ln + 15)
            print(f"  (周辺 L.{start + 1}-{end}):")
            for j in range(start, end):
                marker = " >>>" if j == ln - 1 else "    "
                display = lines[j] if len(lines[j]) <= 200 else lines[j][:200] + "..."
                print(f"  {marker} {j + 1:5d}: {display}")
    else:
        print("  ix:hidden: 見つかりません")

    # ix:nonFraction / ix:nonNumeric の使用例（最初の5箇所）
    print(f"\n  --- ix:nonFraction / ix:nonNumeric 使用例 ---")
    ix_elements = []
    for i, line in enumerate(lines, 1):
        if re.search(r'<ix:(nonFraction|nonNumeric)\b', line, re.IGNORECASE):
            ix_elements.append((i, line.strip()))
    if ix_elements:
        print(f"  合計 {len(ix_elements)} 箇所")
        for ln, line in ix_elements[:5]:
            display = line if len(line) <= 200 else line[:200] + "..."
            print(f"  L.{ln}: {display}")
        if len(ix_elements) > 5:
            print(f"  ... (残り {len(ix_elements) - 5} 箇所)")
    else:
        print("  ix:nonFraction / ix:nonNumeric: 見つかりません")

    # format 属性の一覧
    print(f"\n  --- format 属性の種類 ---")
    formats: set[str] = set()
    for line in lines:
        for m in re.finditer(r'format="([^"]*)"', line):
            formats.add(m.group(1))
    if formats:
        for fmt in sorted(formats):
            print(f"  {fmt}")
    else:
        print("  format 属性: 見つかりません")

    # scale 属性の一覧
    print(f"\n  --- scale 属性の種類 ---")
    scales: set[str] = set()
    for line in lines:
        for m in re.finditer(r'scale="([^"]*)"', line):
            scales.add(m.group(1))
    if scales:
        for s in sorted(scales, key=lambda x: int(x) if x.lstrip("-").isdigit() else 0):
            print(f"  scale=\"{s}\"")
    else:
        print("  scale 属性: 見つかりません")


def main() -> None:
    """メイン処理。"""
    print("P-2b: iXBRL (.htm) ファイルの冒頭・構造確認")
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
    print_filing_info(filing, label="P-2b 対象 Filing")

    zip_bytes = get_zip(filing.doc_id)

    # PublicDoc 配下の .htm ファイル
    htm_members = find_public_doc_members(zip_bytes, ".htm")
    print(f"\n[PublicDoc .htm ファイル: {len(htm_members)} 件]")

    if not htm_members:
        print("  .htm ファイルが見つかりません。iXBRL は不採用の可能性。")
        return

    # 全 .htm ファイルを分析（iXBRL の確認のため）
    for member in htm_members:
        try:
            analyze_ixbrl_file(zip_bytes, member)
        except Exception as exc:
            print(f"  ERROR: {member}: {type(exc).__name__}: {exc}")

    print(f"\n{'=' * 70}")
    print("P-2b 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

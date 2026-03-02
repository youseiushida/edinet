"""K-3 / P-5. CSV 内容調査スクリプト

実行方法: uv run docs/QAs/scripts/K-3.csv_sample.py
前提: EDINET_API_KEY 環境変数が必要
出力: CSV ZIP の構造、CSV ファイルの冒頭50行、列構成分析
"""

from __future__ import annotations

import io
import os
import zipfile
from datetime import date, timedelta

import edinet
edinet.configure(api_key=os.environ["EDINET_API_KEY"])

import edinet.public_api as public_api
from edinet.api.download import (
    download_document,
    list_zip_members,
)
from edinet.models.filing import Filing


def find_csv_xbrl_filing(lookback_days: int = 30) -> Filing | None:
    """has_csv=True かつ has_xbrl=True の書類を直近日から探す。

    Args:
        lookback_days: 遡る最大日数。

    Returns:
        条件に合致する Filing、見つからなければ None。
    """
    today = date.today()
    for i in range(lookback_days):
        d = today - timedelta(days=i)
        filings = public_api.documents(date=d)
        for f in filings:
            if f.has_csv and f.has_xbrl:
                return f
    return None


def analyze_csv_zip(zip_bytes: bytes) -> None:
    """CSV ZIP の内容を分析・表示する。

    Args:
        zip_bytes: ダウンロードした CSV ZIP のバイト列。
    """
    # ZIP 構造を表示
    members = list_zip_members(zip_bytes)
    print("=" * 70)
    print("ZIP 内ファイル一覧:")
    print("=" * 70)
    for m in members:
        print(f"  {m}")
    print(f"\n合計: {len(members)} ファイル")

    # CSV ファイルを展開して冒頭を表示
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_files = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        print(f"\nCSV ファイル数: {len(csv_files)}")

        for csv_name in csv_files:
            print("\n" + "=" * 70)
            print(f"ファイル: {csv_name}")
            print("=" * 70)

            raw = zf.read(csv_name)
            # エンコーディング判定: BOM で判定、なければ順に試す
            print(f"先頭4バイト: {raw[:4].hex(' ')}")
            if raw[:2] == b"\xff\xfe":
                enc = "utf-16-le"
                text = raw[2:].decode(enc)
                print(f"エンコーディング: UTF-16 LE (BOM検出)")
            elif raw[:2] == b"\xfe\xff":
                enc = "utf-16-be"
                text = raw[2:].decode(enc)
                print(f"エンコーディング: UTF-16 BE (BOM検出)")
            else:
                for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
                    try:
                        text = raw.decode(enc)
                        print(f"エンコーディング: {enc}")
                        break
                    except (UnicodeDecodeError, ValueError):
                        continue
                else:
                    print("エンコーディング判定失敗、バイナリとしてスキップ")
                    continue

            lines = text.splitlines()
            print(f"総行数: {len(lines)}")
            print(f"\n--- 冒頭 50 行 ---")
            for i, line in enumerate(lines[:50], 1):
                # 長い行は切り詰め
                display = line if len(line) <= 200 else line[:200] + "..."
                print(f"  {i:3d}: {display}")

            # 列構成分析
            if lines:
                print(f"\n--- 列構成分析 ---")
                # ヘッダー行（1行目）
                header = lines[0]
                cols = header.split(",")
                print(f"列数: {len(cols)}")
                print("列名:")
                for j, col in enumerate(cols, 1):
                    print(f"  [{j}] {col.strip()}")

                # XBRL 関連キーワードの検出
                keywords = [
                    "concept", "element", "context", "unit",
                    "fact", "value", "namespace", "prefix",
                    "period", "instant", "duration", "dimension",
                    "member", "scenario", "segment",
                ]
                header_lower = header.lower()
                found = [kw for kw in keywords if kw in header_lower]
                if found:
                    print(f"\nXBRL 関連キーワード検出: {found}")
                else:
                    print("\nXBRL 関連キーワード: 検出されず")

            print()


def main() -> None:
    """メイン処理。"""
    print("K-3 / P-5: CSV 内容調査")
    print("=" * 70)

    # Step 1: has_csv=True かつ has_xbrl=True の書類を探す
    print("\n[Step 1] has_csv=True かつ has_xbrl=True の書類を検索中...")
    filing = find_csv_xbrl_filing()

    if filing is None:
        print("ERROR: 条件に合致する書類が見つかりませんでした")
        return

    print(f"  書類ID: {filing.doc_id}")
    print(f"  提出者: {filing.filer_name}")
    print(f"  書類種別: {filing.doc_type_label_ja}")
    print(f"  提出日: {filing.filing_date}")
    print(f"  has_xbrl={filing.has_xbrl}, has_csv={filing.has_csv}")

    # Step 2: CSV ZIP をダウンロード
    print(f"\n[Step 2] CSV ZIP (file_type=5) をダウンロード中...")
    csv_zip = download_document(filing.doc_id, file_type="5")
    print(f"  ZIP サイズ: {len(csv_zip):,} bytes")

    # Step 3: CSV ZIP の内容を分析
    print(f"\n[Step 3] CSV ZIP の内容分析")
    analyze_csv_zip(csv_zip)

    # Step 4: 比較用に XBRL ZIP の構造も確認
    print("\n[Step 4] 比較用: XBRL ZIP (file_type=1) の構造")
    print("=" * 70)
    xbrl_zip = download_document(filing.doc_id, file_type="1")
    xbrl_members = list_zip_members(xbrl_zip)
    print(f"  ZIP サイズ: {len(xbrl_zip):,} bytes")
    print(f"  ファイル数: {len(xbrl_members)}")
    for m in xbrl_members:
        print(f"    {m}")


if __name__ == "__main__":
    main()

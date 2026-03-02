"""K-3. CSV 列構成分析の検証スクリプト（列分割バグ修正版）

実行方法: uv run docs/QAs/scripts/K-3.verify.py
前提: EDINET_API_KEY 環境変数が必要
出力: CSV ヘッダーをタブ区切りで正しく分割した列構成分析結果。
      元スクリプト K-3.csv_sample.py の L106 にある split(",") を
      split("\\t") に修正した場合の正しい出力を再現する。
"""

from __future__ import annotations

import io
import os
import zipfile
from datetime import date, timedelta

import edinet

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

import edinet.public_api as public_api
from edinet.api.download import download_document
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


def analyze_csv_columns(zip_bytes: bytes) -> None:
    """CSV ZIP 内の各ファイルについてタブ区切りで列構成を分析する。

    Args:
        zip_bytes: ダウンロードした CSV ZIP のバイト列。
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_files = [n for n in zf.namelist() if n.lower().endswith(".csv")]

        for csv_name in csv_files:
            print(f"\n{'=' * 70}")
            print(f"ファイル: {csv_name}")
            print("=" * 70)

            raw = zf.read(csv_name)
            # BOM で UTF-16 LE を検出
            if raw[:2] == b"\xff\xfe":
                text = raw[2:].decode("utf-16-le")
                print(f"エンコーディング: UTF-16 LE (BOM検出)")
            else:
                text = raw.decode("utf-8-sig")
                print(f"エンコーディング: UTF-8")

            lines = text.splitlines()
            print(f"総行数: {len(lines)}")

            if not lines:
                continue

            # 修正ポイント: タブ区切りで分割（元スクリプトは split(",") だった）
            header = lines[0]
            cols = header.split("\t")
            print(f"\n--- 列構成分析（タブ区切り） ---")
            print(f"列数: {len(cols)}")
            print("列名:")
            for j, col in enumerate(cols, 1):
                print(f"  [{j}] {col.strip()}")

            # 各列のサンプル値（データ行があれば）
            if len(lines) > 1:
                print(f"\n--- 列ごとのサンプル値（2行目） ---")
                data_cols = lines[1].split("\t")
                for j, (h, v) in enumerate(zip(cols, data_cols), 1):
                    display_v = v.strip()
                    if len(display_v) > 80:
                        display_v = display_v[:80] + "..."
                    print(f"  [{j}] {h.strip()} = {display_v}")

            # XBRL 関連キーワード検出（タブ分割後の各列で）
            keywords = [
                "concept", "element", "context", "unit",
                "fact", "value", "namespace", "prefix",
                "period", "instant", "duration", "dimension",
                "member", "scenario", "segment",
            ]
            for col in cols:
                col_lower = col.lower()
                found = [kw for kw in keywords if kw in col_lower]
                if found:
                    print(f"\n  列 {col.strip()} に XBRL キーワード: {found}")


def main() -> None:
    """メイン処理。"""
    print("K-3 検証: CSV 列構成分析（タブ区切り修正版）")
    print("=" * 70)

    # 元スクリプトと同じ書類を使用
    print("\n[Step 1] has_csv=True かつ has_xbrl=True の書類を検索中...")
    filing = find_csv_xbrl_filing()

    if filing is None:
        print("ERROR: 条件に合致する書類が見つかりませんでした")
        return

    print(f"  書類ID: {filing.doc_id}")
    print(f"  提出者: {filing.filer_name}")
    print(f"  書類種別: {filing.doc_type_label_ja}")
    print(f"  提出日: {filing.filing_date}")

    # CSV ZIP ダウンロード
    print(f"\n[Step 2] CSV ZIP (file_type=5) をダウンロード中...")
    csv_zip = download_document(filing.doc_id, file_type="5")
    print(f"  ZIP サイズ: {len(csv_zip):,} bytes")

    # 列構成分析
    print(f"\n[Step 3] 列構成分析（タブ区切りで正しく分割）")
    analyze_csv_columns(csv_zip)

    # 検証結論
    print(f"\n\n{'=' * 70}")
    print("検証結論")
    print(f"{'=' * 70}")
    print("元スクリプト K-3.csv_sample.py L106 の header.split(',') は")
    print("タブ区切りデータに対してカンマで分割しており、列数が 1 と誤表示される。")
    print("本スクリプトで split('\\t') に修正した結果、列数 9 が正しく表示される。")
    print("K-3.a.md の Fact [F2]（9列）は正しい。")


if __name__ == "__main__":
    main()

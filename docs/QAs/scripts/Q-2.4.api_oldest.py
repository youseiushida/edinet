"""Q-2.4: EDINET API 提供期間の調査。

API で取得可能な最古日を確定し、対応すべきタクソノミバージョン数を決める。
2016年1月〜3月を中心に documents() API を呼び、最古の応答日を特定する。
最古の書類で file_type="1" ダウンロードを試行する。
"""

from __future__ import annotations

import sys
from datetime import date

sys.path.insert(0, "docs/QAs/scripts")
from _common import find_filings, get_zip, print_filing_info

# ============================================================
# 1. 最古取得可能日の探索
#    仕様書: 閲覧期間10年 → 2016年頃が最古と推定
#    2016-01-01 から月単位で探索
# ============================================================
print("=" * 70)
print("Q-2.4: EDINET API 最古取得可能日の探索")
print("=" * 70)

# 10年前 = 2016-02-23 付近が最古と想定
# ただし仕様書 v1.1 で5年→10年に延長されたのは2023年5月
# 実際の最古日を探索する

search_ranges = [
    ("2016-01-04", "2016-01-31"),
    ("2016-02-01", "2016-02-29"),
    ("2016-03-01", "2016-03-31"),
    ("2016-04-01", "2016-04-30"),
    ("2016-05-01", "2016-05-31"),
    ("2016-06-01", "2016-06-30"),
]

oldest_filing = None
oldest_date = None

for start, end in search_ranges:
    print(f"\n--- 検索期間: {start} ~ {end} ---")
    try:
        filings = find_filings(
            start=start, end=end, has_xbrl=False, max_results=0,
        )
        print(f"  結果: {len(filings)} 件")
        if filings:
            # 最古の filing_date を特定
            for f in filings:
                fd = f.filing_date
                if fd and (oldest_date is None or fd < oldest_date):
                    oldest_date = fd
                    oldest_filing = f
            print(f"  最古 filing_date: {oldest_date}")
            # 最初に見つかった範囲で十分（これ以前は空のはず）
            if oldest_filing:
                break
    except Exception as e:
        print(f"  エラー: {e}")

if oldest_filing:
    print(f"\n{'=' * 70}")
    print("最古の Filing:")
    print_filing_info(oldest_filing, label="最古 Filing")
else:
    print("\n2016年前半に Filing が見つかりませんでした。")
    # 後半を試す
    for start, end in [
        ("2016-07-01", "2016-07-31"),
        ("2016-08-01", "2016-08-31"),
        ("2016-09-01", "2016-09-30"),
    ]:
        print(f"\n--- 検索期間: {start} ~ {end} ---")
        try:
            filings = find_filings(
                start=start, end=end, has_xbrl=False, max_results=0,
            )
            print(f"  結果: {len(filings)} 件")
            if filings:
                for f in filings:
                    fd = f.filing_date
                    if fd and (oldest_date is None or fd < oldest_date):
                        oldest_date = fd
                        oldest_filing = f
                if oldest_filing:
                    print_filing_info(oldest_filing, label="最古 Filing")
                    break
        except Exception as e:
            print(f"  エラー: {e}")

# ============================================================
# 2. 最古 Filing の XBRL ダウンロード試行
# ============================================================
if oldest_filing:
    print(f"\n{'=' * 70}")
    print("最古 Filing の XBRL ダウンロード試行")
    print("=" * 70)

    # XBRL付き Filing を探す
    print("\n--- XBRL付き最古 Filing の検索 ---")
    xbrl_oldest = None
    for start, end in search_ranges:
        try:
            filings = find_filings(
                start=start, end=end, has_xbrl=True, max_results=5,
            )
            if filings:
                for f in filings:
                    fd = f.filing_date
                    if fd and (xbrl_oldest is None or fd < fd):
                        xbrl_oldest = f
                if xbrl_oldest:
                    break
        except Exception:
            pass

    if xbrl_oldest:
        print_filing_info(xbrl_oldest, label="XBRL付き最古 Filing")
        try:
            zip_bytes = get_zip(xbrl_oldest.doc_id, file_type="1")
            print(f"  ダウンロード成功: {len(zip_bytes):,} bytes")
        except Exception as e:
            print(f"  ダウンロード失敗: {e}")
    else:
        print("  XBRL付き Filing が見つかりませんでした。")

# ============================================================
# 3. 現在日付から最古日までの年数計算
# ============================================================
if oldest_date:
    today = date.today()
    years = (today - oldest_date).days / 365.25
    print(f"\n{'=' * 70}")
    print("サマリ")
    print("=" * 70)
    print(f"  今日の日付      : {today}")
    print(f"  最古 Filing 日付: {oldest_date}")
    print(f"  経過年数        : {years:.1f} 年")
    print(f"  対応バージョン数: 約 {int(years) + 1} バージョン（年次更新想定）")

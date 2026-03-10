"""1年間の EDINET 書類数を日次で集計する（メタデータのみ、ZIP不要）。

使い方:
    uv run python tools/_count_annual_docs.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet

# 2024/7/1 ~ 2025/6/30 の1年間（2025年3月期決算の有報シーズンを含む）
START = date(2024, 7, 1)
END = date(2025, 6, 30)
CONCURRENCY = 10  # adocuments 同時リクエスト数


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY", "your_api_key_here")
    edinet.configure(api_key=api_key)

    total_days = (END - START).days + 1
    print(f"期間: {START} ~ {END} ({total_days}日間)")
    print(f"同時リクエスト数: {CONCURRENCY}")

    sem = asyncio.Semaphore(CONCURRENCY)
    daily_counts: dict[date, dict[str, int]] = {}
    done = 0
    errors = 0
    t0 = time.perf_counter()

    async def fetch_day(d: date) -> None:
        nonlocal done, errors
        async with sem:
            try:
                filings = await edinet.adocuments(date=d)
                total = len(filings)
                xbrl = sum(1 for f in filings if f.has_xbrl)
                daily_counts[d] = {"total": total, "xbrl": xbrl}
            except Exception as e:
                errors += 1
                daily_counts[d] = {"total": 0, "xbrl": 0}
                print(f"  [ERR] {d}: {e!r}")
            finally:
                done += 1
                if done % 30 == 0 or done == total_days:
                    elapsed = time.perf_counter() - t0
                    print(f"  進捗: {done}/{total_days} ({elapsed:.0f}s)")

    # 全日を並列取得
    dates = [START + timedelta(days=i) for i in range(total_days)]
    await asyncio.gather(*(fetch_day(d) for d in dates))

    elapsed = time.perf_counter() - t0
    await edinet.aclose()

    # --- 集計 ---
    print(f"\n取得完了: {elapsed:.0f}s (エラー: {errors})")

    total_all = sum(v["total"] for v in daily_counts.values())
    total_xbrl = sum(v["xbrl"] for v in daily_counts.values())

    # 月別集計
    monthly: dict[str, dict[str, int]] = {}
    for d, v in sorted(daily_counts.items()):
        key = d.strftime("%Y-%m")
        if key not in monthly:
            monthly[key] = {"total": 0, "xbrl": 0, "days": 0}
        monthly[key]["total"] += v["total"]
        monthly[key]["xbrl"] += v["xbrl"]
        monthly[key]["days"] += 1

    print(f"\n{'='*60}")
    print(f"年間集計: {START} ~ {END}")
    print(f"{'='*60}")
    print(f"\n{'月':>8}  {'全書類':>8}  {'XBRL有':>8}  {'日数':>4}  {'平均/日':>8}")
    print(f"{'-'*8}  {'-'*8}  {'-'*8}  {'-'*4}  {'-'*8}")
    for month, v in sorted(monthly.items()):
        avg = v["total"] / v["days"] if v["days"] > 0 else 0
        print(f"{month:>8}  {v['total']:>8,}  {v['xbrl']:>8,}  {v['days']:>4}  {avg:>8.0f}")

    print(f"{'-'*8}  {'-'*8}  {'-'*8}  {'-'*4}  {'-'*8}")
    avg_daily = total_all / total_days
    print(f"{'合計':>8}  {total_all:>8,}  {total_xbrl:>8,}  {total_days:>4}  {avg_daily:>8.0f}")

    # ピーク日
    peak_day = max(daily_counts, key=lambda d: daily_counts[d]["total"])
    peak_val = daily_counts[peak_day]
    print(f"\nピーク日: {peak_day} ({peak_val['total']:,}件, XBRL有: {peak_val['xbrl']:,})")

    # Parquet サイズ推定
    KB_PER_FILING = 108  # ストレステスト結果
    KB_PER_XBRL = 146
    est_all = total_all * KB_PER_FILING / 1024 / 1024
    est_xbrl = total_xbrl * KB_PER_XBRL / 1024 / 1024
    print(f"\nParquet サイズ推定 (ストレステスト実測ベース):")
    print(f"  全書類: {total_all:,} × {KB_PER_FILING}KB = {est_all:.1f} GB")
    print(f"  XBRL有: {total_xbrl:,} × {KB_PER_XBRL}KB = {est_xbrl:.1f} GB")

    # レポート保存
    report_dir = Path(__file__).resolve().parent.parent / "parquet"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "annual_doc_count.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"EDINET 年間書類数レポート ({START} ~ {END})\n\n")
        f.write(f"全書類: {total_all:,}\n")
        f.write(f"XBRL有: {total_xbrl:,}\n")
        f.write(f"平均/日: {avg_daily:.0f}\n")
        f.write(f"ピーク日: {peak_day} ({peak_val['total']:,}件)\n\n")
        f.write(f"月別:\n")
        for month, v in sorted(monthly.items()):
            f.write(f"  {month}: {v['total']:>6,} (XBRL: {v['xbrl']:>6,})\n")
        f.write(f"\nParquet推定: 全{est_all:.1f}GB / XBRL{est_xbrl:.1f}GB\n")
    print(f"\nレポート保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())

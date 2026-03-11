"""EDINET API サーバーのレイテンシ計測。

書類一覧取得 (metadata) と ZIP ダウンロード (download) の
レスポンスタイムを計測する。

使い方:
    uv run python tools/_bench_edinet_latency.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet
from edinet._config import get_config
from edinet.api.download import DownloadFileType, adownload_document
from edinet.public_api import adocuments

API_KEY = "your_api_key_here" 

# 計測対象の日付（有報集中日で書類が多い）
TARGET_DATES = ["2025-06-25", "2025-03-31", "2025-01-15"]

# ZIPダウンロード計測用の件数
DL_SAMPLE_COUNT = 10


async def measure_metadata_latency() -> None:
    """書類一覧 API のレイテンシを計測する。"""
    print("=" * 60)
    print("[Phase 1] 書類一覧 API (metadata) レイテンシ")
    print("=" * 60)

    for date in TARGET_DATES:
        t0 = time.perf_counter()
        filings = await adocuments(date)
        elapsed = time.perf_counter() - t0
        print(f"  {date}: {elapsed:.2f}s ({len(filings)} 件)")


async def measure_download_latency() -> None:
    """ZIP ダウンロード API のレイテンシを計測する。"""
    print(f"\n{'=' * 60}")
    print(f"[Phase 2] ZIP ダウンロード (type=1) レイテンシ — 逐次")
    print(f"{'=' * 60}")

    # まずサンプル doc_id を取得（has_xbrl=True のもの）
    filings = await adocuments("2025-06-25")
    xbrl_filings = [f for f in filings if f.has_xbrl][:DL_SAMPLE_COUNT]
    print(f"  サンプル: {len(xbrl_filings)} 件 (has_xbrl=True)")

    latencies: list[float] = []
    sizes: list[int] = []

    for f in xbrl_filings:
        t0 = time.perf_counter()
        data = await adownload_document(f.doc_id)
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)
        sizes.append(len(data))
        size_kb = len(data) / 1024
        print(f"    {f.doc_id} ({f.filer_name}): "
              f"{elapsed:.2f}s, {size_kb:.0f} KB")

    avg_lat = sum(latencies) / len(latencies)
    avg_size = sum(sizes) / len(sizes) / 1024
    min_lat = min(latencies)
    max_lat = max(latencies)

    print(f"\n  レイテンシ: avg={avg_lat:.2f}s, "
          f"min={min_lat:.2f}s, max={max_lat:.2f}s")
    print(f"  ZIPサイズ: avg={avg_size:.0f} KB")
    print(f"  実効スループット: "
          f"{sum(sizes) / sum(latencies) / 1024:.0f} KB/s")


async def measure_concurrent_download_scaling() -> None:
    """並行数を変えて ZIP ダウンロードのスケーラビリティを計測する。"""
    print(f"\n{'=' * 60}")
    print(f"[Phase 3] ZIP ダウンロード — 並行数スケーリング")
    print(f"{'=' * 60}")

    filings = await adocuments("2025-06-25")
    xbrl_filings = [f for f in filings if f.has_xbrl]

    # 50件で計測（少なすぎると並行の効果が見えない）
    sample = xbrl_filings[:50]
    print(f"  サンプル: {len(sample)} 件")

    concurrency_levels = [1, 4, 8, 16, 32, 64]
    summary: list[dict] = []

    for conc in concurrency_levels:
        sem = asyncio.Semaphore(conc)
        results: list[tuple[str, float, int]] = []
        error_count = 0

        async def _dl(f, _sem=sem):
            nonlocal error_count
            async with _sem:
                t0 = time.perf_counter()
                try:
                    data = await adownload_document(f.doc_id)
                    elapsed = time.perf_counter() - t0
                    results.append((f.doc_id, elapsed, len(data)))
                except Exception as e:
                    elapsed = time.perf_counter() - t0
                    error_count += 1
                    results.append((f.doc_id, elapsed, 0))
                    print(f"    エラー: {f.doc_id} ({type(e).__name__}: {e})")

        t_total_start = time.perf_counter()
        await asyncio.gather(*[_dl(f) for f in sample])
        t_total = time.perf_counter() - t_total_start

        ok_results = [(d, l, s) for d, l, s in results if s > 0]
        total_bytes = sum(r[2] for r in ok_results)
        avg_lat = sum(r[1] for r in ok_results) / len(ok_results) if ok_results else 0
        throughput = total_bytes / t_total / 1024 if t_total > 0 else 0
        wall_per_doc = t_total / len(sample)

        row = {
            "concurrency": conc,
            "total_time": t_total,
            "wall_per_doc": wall_per_doc,
            "avg_latency": avg_lat,
            "throughput_kbs": throughput,
            "total_kb": total_bytes / 1024,
            "errors": error_count,
            "docs": len(sample),
        }
        summary.append(row)

        print(f"\n  concurrency={conc}:")
        print(f"    全体: {t_total:.1f}s, wall/件: {wall_per_doc:.2f}s")
        print(f"    個別レイテンシ avg: {avg_lat:.2f}s")
        print(f"    スループット: {throughput:.0f} KB/s")
        if error_count:
            print(f"    エラー: {error_count} 件")

    # サマリテーブル
    print(f"\n{'=' * 60}")
    print("スケーリング サマリ")
    print(f"{'=' * 60}")

    base = summary[0]  # concurrency=1
    print(f"\n  {'並列数':>6s}  {'全体時間':>8s}  {'wall/件':>8s}  "
          f"{'個別lat':>8s}  {'KB/s':>8s}  {'速度比':>6s}  {'エラー':>4s}")
    print("  " + "-" * 62)
    for row in summary:
        speedup = base["total_time"] / row["total_time"] if row["total_time"] > 0 else 0
        print(
            f"  {row['concurrency']:>6d}  "
            f"{row['total_time']:>7.1f}s  "
            f"{row['wall_per_doc']:>7.2f}s  "
            f"{row['avg_latency']:>7.2f}s  "
            f"{row['throughput_kbs']:>7.0f}  "
            f"{speedup:>5.1f}x  "
            f"{row['errors']:>4d}"
        )


async def main() -> None:
    edinet.configure(api_key=API_KEY)
    await measure_metadata_latency()
    await measure_download_latency()
    await measure_concurrent_download_scaling()
    await edinet.aclose()


if __name__ == "__main__":
    asyncio.run(main())

"""EDINET API スループット計測 — 高速回線環境用。

ACK 渋滞仮説の検証: 高速対称回線 (Colab) で DL 並列数を
1〜64 まで変化させ、サーバー律速の天井を特定する。

使い方 (Colab セル):
    # --- セル 1 ---
    !pip install aiohttp

    # --- セル 2 ---
    API_KEY = "YOUR_KEY_HERE"  # ← ここに API キーを貼る
    %run bench_colab_latency.py

CLI:
    python bench_colab_latency.py --api-key YOUR_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# aiohttp のみ依存（Colab にプリインストール or pip install aiohttp）
# ---------------------------------------------------------------------------

try:
    import aiohttp
except ImportError:
    print("aiohttp が必要です: pip install aiohttp", file=sys.stderr)
    sys.exit(1)

# Colab / Jupyter は既にイベントループが動いているため asyncio.run() が使えない。
# nest_asyncio でパッチする。
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # CLI 実行時は不要

BASE = "https://api.edinet-fsa.go.jp/api/v2"


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------

@dataclass
class DLResult:
    """1 件のダウンロード結果。"""
    doc_id: str
    size_bytes: int
    elapsed: float
    error: str | None = None


@dataclass
class ConcurrencyResult:
    """1 つの並列数設定の結果。"""
    concurrency: int
    samples: int
    total_time: float
    results: list[DLResult] = field(default_factory=list)

    @property
    def ok_results(self) -> list[DLResult]:
        return [r for r in self.results if r.error is None]

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.error is not None)

    @property
    def wall_per_doc(self) -> float:
        n = len(self.ok_results)
        return self.total_time / n if n else 0

    @property
    def avg_latency(self) -> float:
        ok = self.ok_results
        return statistics.mean(r.elapsed for r in ok) if ok else 0

    @property
    def median_latency(self) -> float:
        ok = self.ok_results
        return statistics.median(r.elapsed for r in ok) if ok else 0

    @property
    def p95_latency(self) -> float:
        ok = self.ok_results
        if not ok:
            return 0
        sorted_lat = sorted(r.elapsed for r in ok)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def total_bytes(self) -> int:
        return sum(r.size_bytes for r in self.ok_results)

    @property
    def throughput_kbps(self) -> float:
        return (self.total_bytes / 1024) / self.total_time if self.total_time else 0

    @property
    def docs_per_sec(self) -> float:
        n = len(self.ok_results)
        return n / self.total_time if self.total_time else 0


# ---------------------------------------------------------------------------
# API ヘルパー
# ---------------------------------------------------------------------------

async def fetch_document_list(
    session: aiohttp.ClientSession,
    api_key: str,
    target_date: str,
) -> list[dict]:
    """書類一覧 API を呼び出し、XBRL ありの書類リストを返す。"""
    url = f"{BASE}/documents.json"
    params = {"date": target_date, "type": "2", "Subscription-Key": api_key}

    t0 = time.perf_counter()
    async with session.get(url, params=params) as resp:
        data = await resp.json(content_type=None)
        elapsed = time.perf_counter() - t0

    if resp.status != 200:
        print(f"書類一覧 API エラー: status={resp.status}", file=sys.stderr)
        sys.exit(1)

    results = data.get("results", [])
    xbrl_docs = [r for r in results if r.get("xbrlFlag") == "1"]

    print(f"書類一覧: {len(results)} 件 (XBRL: {len(xbrl_docs)} 件), "
          f"レイテンシ: {elapsed:.2f}s")

    return xbrl_docs


async def download_one(
    session: aiohttp.ClientSession,
    api_key: str,
    doc_id: str,
) -> DLResult:
    """1 件の ZIP をダウンロードし結果を返す。"""
    url = f"{BASE}/documents/{doc_id}"
    params = {"type": "5", "Subscription-Key": api_key}

    t0 = time.perf_counter()
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            body = await resp.read()
            elapsed = time.perf_counter() - t0

            if resp.status != 200:
                return DLResult(doc_id, 0, elapsed, error=f"HTTP {resp.status}")

            return DLResult(doc_id, len(body), elapsed)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return DLResult(doc_id, 0, elapsed, error=str(exc)[:100])


# ---------------------------------------------------------------------------
# ベンチマーク本体
# ---------------------------------------------------------------------------

async def bench_concurrency(
    session: aiohttp.ClientSession,
    api_key: str,
    doc_ids: list[str],
    concurrency: int,
) -> ConcurrencyResult:
    """指定並列数でダウンロードし計測する。"""
    sem = asyncio.Semaphore(concurrency)

    async def _dl(doc_id: str) -> DLResult:
        async with sem:
            return await download_one(session, api_key, doc_id)

    t0 = time.perf_counter()
    results = await asyncio.gather(*[_dl(d) for d in doc_ids])
    total_time = time.perf_counter() - t0

    return ConcurrencyResult(
        concurrency=concurrency,
        samples=len(doc_ids),
        total_time=total_time,
        results=list(results),
    )


async def run_benchmark(
    api_key: str,
    target_date: str,
    samples: int,
    concurrencies: list[int],
    warmup: int,
) -> list[ConcurrencyResult]:
    """全並列数でベンチマークを実行する。"""

    connector = aiohttp.TCPConnector(limit=0, limit_per_host=0)
    async with aiohttp.ClientSession(connector=connector) as session:

        # 1. 書類一覧取得
        docs = await fetch_document_list(session, api_key, target_date)
        if len(docs) < samples + warmup:
            print(f"警告: XBRL 書類が {len(docs)} 件しかありません "
                  f"(必要: {samples + warmup})")
            samples = max(1, len(docs) - warmup)

        # 2. ウォームアップ（TCP 接続プール + サーバーキャッシュ）
        if warmup > 0:
            warmup_ids = [d["docID"] for d in docs[:warmup]]
            print(f"\nウォームアップ: {warmup} 件ダウンロード中...", flush=True)
            await bench_concurrency(session, api_key, warmup_ids, concurrency=8)
            print("ウォームアップ完了")

        # 3. 計測対象の doc_id
        target_ids = [d["docID"] for d in docs[warmup:warmup + samples]]
        print(f"計測対象: {len(target_ids)} 件\n")

        # 4. 各並列数で計測
        all_results: list[ConcurrencyResult] = []

        for conc in concurrencies:
            label = f"並列={conc:>3d}"
            print(f"  {label} ... ", end="", flush=True)

            result = await bench_concurrency(
                session, api_key, target_ids, conc,
            )
            all_results.append(result)

            print(
                f"{result.total_time:>6.1f}s  "
                f"{result.wall_per_doc:.3f}s/件  "
                f"latency avg={result.avg_latency:.2f}s med={result.median_latency:.2f}s p95={result.p95_latency:.2f}s  "
                f"{result.throughput_kbps:>8.0f} KB/s  "
                f"{result.docs_per_sec:.1f} 件/s  "
                f"err={result.errors}"
            )

        return all_results


# ---------------------------------------------------------------------------
# レポート
# ---------------------------------------------------------------------------

def print_report(results: list[ConcurrencyResult], target_date: str) -> None:
    """結果テーブルを表示する。"""
    baseline = results[0].total_time if results else 1

    print(f"\n{'=' * 100}")
    print(f"EDINET API DL スループット計測結果  (対象日: {target_date})")
    print(f"{'=' * 100}")

    header = (
        f"{'並列':>4s}  {'全体時間':>8s}  {'wall/件':>8s}  "
        f"{'avg lat':>8s}  {'med lat':>8s}  {'p95 lat':>8s}  "
        f"{'KB/s':>8s}  {'件/s':>6s}  {'速度比':>6s}  {'err':>4s}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        speedup = baseline / r.total_time if r.total_time else 0
        print(
            f"{r.concurrency:>4d}  "
            f"{r.total_time:>7.1f}s  "
            f"{r.wall_per_doc:>7.3f}s  "
            f"{r.avg_latency:>7.2f}s  "
            f"{r.median_latency:>7.2f}s  "
            f"{r.p95_latency:>7.2f}s  "
            f"{r.throughput_kbps:>8.0f}  "
            f"{r.docs_per_sec:>5.1f}  "
            f"{speedup:>5.1f}x  "
            f"{r.errors:>4d}"
        )

    # サイズ統計
    all_ok = []
    for r in results:
        all_ok.extend(r.ok_results)
    if all_ok:
        sizes = [x.size_bytes for x in all_ok]
        print(f"\nZIP サイズ: "
              f"avg={statistics.mean(sizes)/1024:.0f}KB  "
              f"med={statistics.median(sizes)/1024:.0f}KB  "
              f"min={min(sizes)/1024:.0f}KB  "
              f"max={max(sizes)/1024:.0f}KB")

    # 結論
    print(f"\n{'─' * 60}")
    print("分析:")

    if len(results) >= 2:
        best = min(results, key=lambda r: r.total_time)
        print(f"  最速: 並列={best.concurrency} ({best.docs_per_sec:.1f} 件/s)")

        # 8 並列 vs 最速を比較
        c8 = next((r for r in results if r.concurrency == 8), None)
        if c8 and best.concurrency > 8:
            gain = (c8.total_time - best.total_time) / c8.total_time * 100
            print(f"  8並列 vs 最速({best.concurrency}並列): {gain:+.1f}% 改善")
        elif c8:
            print(f"  8並列が最速または同等 → サーバー律速の可能性")

        # レイテンシ膨張率
        c1 = next((r for r in results if r.concurrency == 1), None)
        if c1 and best:
            inflation = best.avg_latency / c1.avg_latency
            print(f"  レイテンシ膨張: 1並列 {c1.avg_latency:.2f}s → "
                  f"{best.concurrency}並列 {best.avg_latency:.2f}s "
                  f"({inflation:.1f}x)")

    # JSON 出力
    print(f"\n{'─' * 60}")
    json_data = []
    for r in results:
        json_data.append({
            "concurrency": r.concurrency,
            "samples": r.samples,
            "total_time": round(r.total_time, 2),
            "wall_per_doc": round(r.wall_per_doc, 3),
            "avg_latency": round(r.avg_latency, 3),
            "median_latency": round(r.median_latency, 3),
            "p95_latency": round(r.p95_latency, 3),
            "throughput_kbps": round(r.throughput_kbps, 0),
            "docs_per_sec": round(r.docs_per_sec, 2),
            "errors": r.errors,
            "total_bytes": r.total_bytes,
        })
    print("JSON:")
    print(json.dumps(json_data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(
    api_key: str | None = None,
    target_date: str = "2025-06-25",
    samples: int = 50,
    concurrencies: list[int] | None = None,
    warmup: int = 5,
) -> None:
    """ベンチマーク実行。

    Colab からは直接呼べる::

        main(api_key="YOUR_KEY")

    CLI からは argparse 経由。
    """
    if concurrencies is None:
        concurrencies = [1, 2, 4, 8, 16, 32, 64]

    # --- Colab / スクリプト両対応: API キーの解決 ---
    if api_key is None:
        # グローバル変数 API_KEY があれば使う（Colab セルで定義）
        api_key = globals().get("API_KEY") or locals().get("API_KEY")  # type: ignore[assignment]

    if api_key is None and not _is_notebook():
        parser = argparse.ArgumentParser(
            description="EDINET API DL スループット計測",
        )
        parser.add_argument("--api-key", required=True)
        parser.add_argument("--date", default=target_date)
        parser.add_argument("--samples", type=int, default=samples)
        parser.add_argument(
            "--concurrencies", nargs="*", type=int, default=concurrencies,
        )
        parser.add_argument("--warmup", type=int, default=warmup)
        args = parser.parse_args()
        api_key = args.api_key
        target_date = args.date
        samples = args.samples
        concurrencies = sorted(args.concurrencies)
        warmup = args.warmup

    if not api_key:
        print("エラー: API キーが指定されていません。\n"
              "  Colab: セル冒頭で API_KEY = 'YOUR_KEY' を定義してください\n"
              "  CLI:   --api-key YOUR_KEY を指定してください",
              file=sys.stderr)
        return

    print("=" * 60)
    print("EDINET API DL スループット計測")
    print("=" * 60)
    print(f"対象日: {target_date}")
    print(f"サンプル数: {samples}")
    print(f"並列数: {concurrencies}")
    print(f"ウォームアップ: {warmup}")
    print()

    results = asyncio.run(run_benchmark(
        api_key=api_key,
        target_date=target_date,
        samples=samples,
        concurrencies=sorted(concurrencies),
        warmup=warmup,
    ))

    print_report(results, target_date)


def _is_notebook() -> bool:
    """Jupyter / Colab 環境かどうかを判定する。"""
    try:
        from IPython import get_ipython
        shell = get_ipython()
        return shell is not None and "IPKernelApp" in shell.config
    except Exception:
        return False


if __name__ == "__main__":
    main()

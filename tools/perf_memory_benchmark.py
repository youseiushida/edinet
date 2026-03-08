#!/usr/bin/env python3
"""メモリベンチマーク: Filing 処理時のメモリ使用量を計測する。

EDINET API から実際の Filing を取得し xbrl() を呼び出して、
RSS / _zip_cache 保持量 / classify_namespace キャッシュサイズ等を計測する。

2パターン計測:
  - pattern_a: 全 Filing 保持（_zip_cache そのまま）
  - pattern_b: xbrl() 後に clear_fetch_cache() 呼び出し

使用方法:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/perf_memory_benchmark.py
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/perf_memory_benchmark.py --output results.json
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
import tracemalloc

# EDINET ライブラリ
import edinet
from edinet.xbrl._namespaces import classify_namespace


def _get_rss_mb() -> float:
    """現在の RSS（Resident Set Size）を MB で返す。"""
    # resource.getrusage は KB 単位（Linux）
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss / 1024.0


def _get_tracemalloc_mb() -> float:
    """tracemalloc で計測中の現在の Python ヒープ使用量を MB で返す。"""
    current, _peak = tracemalloc.get_traced_memory()
    return current / (1024 * 1024)


def _get_tracemalloc_peak_mb() -> float:
    """tracemalloc で計測中のピーク Python ヒープ使用量を MB で返す。"""
    _current, peak = tracemalloc.get_traced_memory()
    return peak / (1024 * 1024)


def _zip_cache_total_bytes(filings: list) -> int:
    """全 Filing の _zip_cache の合計バイト数を返す。"""
    total = 0
    for f in filings:
        zc = f._zip_cache
        if zc is not None:
            total += len(zc)
    return total


def _stmts_cache_count(filings: list) -> int:
    """_stmts_cache が非 None の Filing 数を返す。"""
    return sum(1 for f in filings if f._stmts_cache is not None)


def run_benchmark(
    filings: list,
    taxonomy_path: str,
    *,
    clear_after: bool = False,
    label: str = "",
) -> dict:
    """Filing リストに対して xbrl() を呼び、メモリ計測結果を返す。

    Args:
        filings: Filing リスト。
        taxonomy_path: タクソノミパス。
        clear_after: True の場合、各 xbrl() 後に clear_fetch_cache() を呼ぶ。
        label: 計測パターンのラベル。

    Returns:
        計測結果の dict。
    """
    tracemalloc.start()
    rss_before = _get_rss_mb()
    heap_before = _get_tracemalloc_mb()

    rss_history: list[dict] = []
    processed = 0
    errors = 0

    for i, filing in enumerate(filings):
        try:
            filing.xbrl(taxonomy_path=taxonomy_path)
            if clear_after:
                filing.clear_fetch_cache()
            processed += 1
        except Exception as exc:
            errors += 1
            print(f"  [{i+1}] {filing.doc_id} エラー: {exc}", file=sys.stderr)

        rss_history.append({
            "index": i + 1,
            "doc_id": filing.doc_id,
            "rss_mb": _get_rss_mb(),
            "heap_mb": _get_tracemalloc_mb(),
        })

    rss_after = _get_rss_mb()
    heap_after = _get_tracemalloc_mb()
    heap_peak = _get_tracemalloc_peak_mb()

    cache_info = classify_namespace.cache_info()
    zip_total = _zip_cache_total_bytes(filings)
    stmts_cached = _stmts_cache_count(filings)

    tracemalloc.stop()

    return {
        "label": label,
        "clear_after": clear_after,
        "total_filings": len(filings),
        "processed": processed,
        "errors": errors,
        "rss_before_mb": round(rss_before, 2),
        "rss_after_mb": round(rss_after, 2),
        "rss_delta_mb": round(rss_after - rss_before, 2),
        "heap_before_mb": round(heap_before, 2),
        "heap_after_mb": round(heap_after, 2),
        "heap_peak_mb": round(heap_peak, 2),
        "zip_cache_total_bytes": zip_total,
        "zip_cache_total_mb": round(zip_total / (1024 * 1024), 2),
        "stmts_cached_count": stmts_cached,
        "classify_ns_cache_size": cache_info.currsize,
        "classify_ns_cache_hits": cache_info.hits,
        "classify_ns_cache_misses": cache_info.misses,
        "rss_history": rss_history,
    }


def main() -> None:
    """メインエントリポイント。"""
    parser = argparse.ArgumentParser(description="EDINET メモリベンチマーク")
    parser.add_argument("--output", "-o", help="結果を JSON ファイルに出力")
    parser.add_argument("--count", "-n", type=int, default=20, help="取得する Filing 数")
    parser.add_argument("--date", "-d", default="2025-06-18", help="書類一覧の取得日 (YYYY-MM-DD)")
    args = parser.parse_args()

    api_key = os.environ.get("EDINET_API_KEY")
    taxonomy_root = os.environ.get("EDINET_TAXONOMY_ROOT")

    if not api_key:
        print("エラー: EDINET_API_KEY 環境変数を設定してください", file=sys.stderr)
        sys.exit(1)
    if not taxonomy_root:
        print("エラー: EDINET_TAXONOMY_ROOT 環境変数を設定してください", file=sys.stderr)
        sys.exit(1)

    edinet.configure(api_key=api_key, taxonomy_path=taxonomy_root)

    print("=== EDINET メモリベンチマーク ===")
    print(f"日付: {args.date}")
    print(f"取得数上限: {args.count}")
    print(f"タクソノミ: {taxonomy_root}")
    print()

    # XBRL 付き Filing を取得
    print("書類一覧を取得中...")
    all_filings = edinet.documents(args.date)

    xbrl_filings = [f for f in all_filings if f.has_xbrl]
    selected = xbrl_filings[:args.count]
    print(f"XBRL 付き Filing: {len(xbrl_filings)} 件中 {len(selected)} 件を使用")
    print()

    # パターン A: 全保持
    print("--- Pattern A: 全 Filing 保持 ---")
    t0 = time.monotonic()
    result_a = run_benchmark(
        selected, taxonomy_root, clear_after=False, label="pattern_a_hold_all"
    )
    elapsed_a = time.monotonic() - t0
    print(f"  処理: {result_a['processed']}/{result_a['total_filings']} 件")
    print(f"  RSS: {result_a['rss_before_mb']} → {result_a['rss_after_mb']} MB (Δ{result_a['rss_delta_mb']})")
    print(f"  _zip_cache 合計: {result_a['zip_cache_total_mb']} MB")
    print(f"  _stmts_cache 保持: {result_a['stmts_cached_count']} 件")
    print(f"  classify_ns cache: {result_a['classify_ns_cache_size']} エントリ")
    print(f"  所要時間: {elapsed_a:.1f}s")
    print()

    # キャッシュクリアしてリロード
    for f in selected:
        f.clear_fetch_cache()
    classify_namespace.cache_clear()

    # パターン B: 処理後クリア
    # 新しい Filing を取得（キャッシュが残らないように）
    all_filings2 = edinet.documents(args.date)
    xbrl_filings2 = [f for f in all_filings2 if f.has_xbrl]
    selected2 = xbrl_filings2[:args.count]

    print("--- Pattern B: 処理後 clear_fetch_cache() ---")
    t1 = time.monotonic()
    result_b = run_benchmark(
        selected2, taxonomy_root, clear_after=True, label="pattern_b_clear_after"
    )
    elapsed_b = time.monotonic() - t1
    print(f"  処理: {result_b['processed']}/{result_b['total_filings']} 件")
    print(f"  RSS: {result_b['rss_before_mb']} → {result_b['rss_after_mb']} MB (Δ{result_b['rss_delta_mb']})")
    print(f"  _zip_cache 合計: {result_b['zip_cache_total_mb']} MB")
    print(f"  _stmts_cache 保持: {result_b['stmts_cached_count']} 件")
    print(f"  classify_ns cache: {result_b['classify_ns_cache_size']} エントリ")
    print(f"  所要時間: {elapsed_b:.1f}s")
    print()

    # 結果出力
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "date": args.date,
        "count": args.count,
        "taxonomy_root": taxonomy_root,
        "pattern_a": result_a,
        "pattern_b": result_b,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(output, fp, ensure_ascii=False, indent=2)
        print(f"結果を {args.output} に保存しました")
    else:
        print("=== JSON 結果 ===")
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

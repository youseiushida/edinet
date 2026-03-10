"""doc_type_codes フィルタのベンチマーク。

iter_parquet で有報+半期報告書 (120, 130) のみ処理する場合の
速度・メモリ改善効果を計測する。

比較対象:
  A: フィルタなし → for 文内で doc_type_code を判定してスキップ
  B: doc_type_codes=["120", "130"] で事前フィルタ

使い方:
    uv run python tools/bench_doc_type_filter.py

前提: parquet/ ディレクトリに dump_stress_*.parquet が存在すること。
"""

from __future__ import annotations

import gc
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

# プロジェクトルートを path に追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# --- 設定 ---
ROOT = Path(__file__).resolve().parent.parent
PARQUET_DIR = ROOT / "parquet"
PREFIX = "dump_stress_"
TARGET_DOC_TYPES = {"120", "130"}

# extract_values で検証する主要キー
_EXTRACT_KEYS = [
    "revenue",
    "operating_income",
    "net_income",
    "total_assets",
    "net_assets",
]


def _fmt_mb(b: float) -> str:
    """バイト数を MB 文字列にフォーマットする。"""
    return f"{b / (1024 * 1024):.1f} MB"


def _measure(label: str, func: Any) -> dict[str, Any]:
    """関数を実行し、時間とメモリを計測する。"""
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()

    result = func()

    elapsed = time.perf_counter() - t0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()

    return {
        "label": label,
        "elapsed": elapsed,
        "mem_peak": peak,
        "result": result,
    }


def main() -> None:
    """ベンチマーク本体。"""
    import pyarrow.parquet as pq

    from edinet.extension import iter_parquet
    from edinet.financial.extract import extract_values

    # 前提チェック
    filings_path = PARQUET_DIR / f"{PREFIX}filings.parquet"
    if not filings_path.exists():
        print(f"エラー: {filings_path} が見つかりません。")
        print("先に tools/parquet_dump_stress_test.py を実行してください。")
        sys.exit(1)

    # データ概要
    fi_table = pq.read_table(filings_path)
    total_count = fi_table.num_rows
    dtc_col = fi_table.column("doc_type_code").to_pylist()
    target_count = sum(1 for c in dtc_col if c in TARGET_DOC_TYPES)

    print("=" * 70)
    print("doc_type_codes フィルタ ベンチマーク")
    print("=" * 70)
    print(f"全書類数: {total_count}")
    print(f"対象 (120, 130): {target_count} "
          f"({target_count / total_count * 100:.1f}%)")
    print(f"対象外: {total_count - target_count}")
    print()

    results: list[dict[str, Any]] = []

    # =================================================================
    # Phase A: フィルタなし + for 文内で分岐
    # =================================================================
    print("[Phase A] フィルタなし → for 文内で doc_type_code 判定")

    def _phase_a() -> dict[str, int]:
        processed = 0
        skipped = 0
        revenue_hits = 0
        for filing, stmts in iter_parquet(
            PARQUET_DIR, prefix=PREFIX, batch_size=100,
        ):
            if filing.doc_type_code not in TARGET_DOC_TYPES:
                skipped += 1
                continue
            processed += 1
            if stmts is None:
                continue
            vals = extract_values(stmts, _EXTRACT_KEYS)
            if vals.get("revenue") is not None:
                revenue_hits += 1
        return {
            "processed": processed,
            "skipped": skipped,
            "revenue_hits": revenue_hits,
        }

    r = _measure("フィルタなし + for分岐", _phase_a)
    info = r["result"]
    print(f"  時間: {r['elapsed']:.2f}s")
    print(f"  メモリ peak: {_fmt_mb(r['mem_peak'])}")
    print(f"  処理: {info['processed']} 件, "
          f"スキップ: {info['skipped']} 件, "
          f"revenue: {info['revenue_hits']}")
    results.append(r)

    # =================================================================
    # Phase B: doc_type_codes フィルタ
    # =================================================================
    print(f"\n[Phase B] doc_type_codes={list(TARGET_DOC_TYPES)} で事前フィルタ")

    def _phase_b() -> dict[str, int]:
        processed = 0
        revenue_hits = 0
        for filing, stmts in iter_parquet(
            PARQUET_DIR, prefix=PREFIX, batch_size=100,
            doc_type_codes=list(TARGET_DOC_TYPES),
        ):
            processed += 1
            if stmts is None:
                continue
            vals = extract_values(stmts, _EXTRACT_KEYS)
            if vals.get("revenue") is not None:
                revenue_hits += 1
        return {
            "processed": processed,
            "revenue_hits": revenue_hits,
        }

    r = _measure("doc_type_codes フィルタ", _phase_b)
    info = r["result"]
    print(f"  時間: {r['elapsed']:.2f}s")
    print(f"  メモリ peak: {_fmt_mb(r['mem_peak'])}")
    print(f"  処理: {info['processed']} 件, "
          f"revenue: {info['revenue_hits']}")
    results.append(r)

    # =================================================================
    # Phase C: doc_type_codes + concepts フィルタ（最大絞り込み）
    # =================================================================
    print(f"\n[Phase C] doc_type_codes + concepts 併用")

    _CONCEPTS = ["NetSales", "OperatingIncome", "OrdinaryIncome",
                 "ProfitLoss", "TotalAssets", "NetAssets"]

    def _phase_c() -> dict[str, int]:
        processed = 0
        revenue_hits = 0
        for filing, stmts in iter_parquet(
            PARQUET_DIR, prefix=PREFIX, batch_size=100,
            doc_type_codes=list(TARGET_DOC_TYPES),
            concepts=_CONCEPTS,
        ):
            processed += 1
            if stmts is None:
                continue
            vals = extract_values(stmts, _EXTRACT_KEYS)
            if vals.get("revenue") is not None:
                revenue_hits += 1
        return {
            "processed": processed,
            "revenue_hits": revenue_hits,
        }

    r = _measure("doc_type_codes + concepts", _phase_c)
    info = r["result"]
    print(f"  時間: {r['elapsed']:.2f}s")
    print(f"  メモリ peak: {_fmt_mb(r['mem_peak'])}")
    print(f"  処理: {info['processed']} 件, "
          f"revenue: {info['revenue_hits']}")
    results.append(r)

    # =================================================================
    # 比較サマリ
    # =================================================================
    print("\n" + "=" * 70)
    print("比較サマリ")
    print("=" * 70)

    base = results[0]
    print(f"\n{'方式':<40s} {'時間':>8s} {'メモリ':>10s} {'速度比':>8s} {'メモリ比':>8s}")
    print("-" * 80)
    for r in results:
        t = r["elapsed"]
        m = r["mem_peak"]
        speedup = f"{base['elapsed'] / t:.2f}x" if t > 0 else "N/A"
        mem_ratio = f"{m / base['mem_peak']:.0%}" if base["mem_peak"] > 0 else "N/A"
        print(f"  {r['label']:<38s} {t:>7.2f}s {_fmt_mb(m):>10s} {speedup:>8s} {mem_ratio:>8s}")

    # 処理件数の内訳
    a_info = results[0]["result"]
    print(f"\n処理件数:")
    print(f"  Phase A: {a_info['processed']} 処理 + "
          f"{a_info['skipped']} スキップ = {a_info['processed'] + a_info['skipped']} 復元")
    print(f"  Phase B: {results[1]['result']['processed']} 処理 "
          f"(対象外は復元自体をスキップ)")
    if len(results) > 2:
        print(f"  Phase C: {results[2]['result']['processed']} 処理 "
              f"(doc_type + concepts 併用)")

    # revenue 一致確認
    a_rev = results[0]["result"]["revenue_hits"]
    b_rev = results[1]["result"]["revenue_hits"]
    match = "✓ 一致" if a_rev == b_rev else "✗ 不一致!"
    print(f"\nrevenue ヒット数: A={a_rev}, B={b_rev} → {match}")

    # =================================================================
    # レポート保存
    # =================================================================
    report_path = ROOT / "tools" / "bench_doc_type_filter_result.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("doc_type_codes フィルタ ベンチマーク結果\n")
        f.write(f"全書類数: {total_count}\n")
        f.write(f"対象 (120, 130): {target_count} "
                f"({target_count / total_count * 100:.1f}%)\n\n")

        f.write(f"{'方式':<40s} {'時間':>8s} {'メモリ':>10s} {'速度比':>8s}\n")
        f.write("-" * 70 + "\n")
        for r in results:
            t = r["elapsed"]
            m = r["mem_peak"]
            speedup = f"{base['elapsed'] / t:.2f}x" if t > 0 else "N/A"
            f.write(f"  {r['label']:<38s} {t:>7.2f}s "
                    f"{_fmt_mb(m):>10s} {speedup:>8s}\n")

    print(f"\nレポート保存: {report_path}")


if __name__ == "__main__":
    main()

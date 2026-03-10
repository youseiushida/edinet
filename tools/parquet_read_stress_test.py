"""Parquet 読み込みストレステスト: import_parquet / iter_parquet の性能を計測する。

既存の Parquet ファイル（parquet_dump_stress_test.py で生成済み）を使い、
各読み込み方式の速度・メモリを比較する。

計測項目:
  Phase 1: import_parquet() — 全件読み込み（ベースライン）
  Phase 2: import_parquet(include_text_blocks=False) — TextBlock 除外
  Phase 3: import_parquet(doc_ids=...) — doc_id フィルタ
  Phase 4: import_parquet(concepts=...) — concepts フィルタ
  Phase 5: iter_parquet(batch_size=50) — バッチイテレーション
  Phase 6: iter_parquet(batch_size=200) — 大きめバッチ
  Phase 7: iter_parquet(concepts=...) — concepts フィルタ付きバッチ
  Phase 8: extract_values 付きイテレーション — 実用パイプライン

使い方:
    uv run python tools/parquet_read_stress_test.py

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
    return f"{b / (1024 * 1024):.2f} MB"


def _measure(
    label: str, func: Any,
) -> dict[str, Any]:
    """関数を実行し、時間とメモリを計測して結果を返す。"""
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()

    result = func()

    elapsed = time.perf_counter() - t0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"  {label}")
    print(f"    時間: {elapsed:.2f}s")
    print(f"    メモリ: current={_fmt_mb(current)}, peak={_fmt_mb(peak)}")

    return {
        "label": label,
        "elapsed": elapsed,
        "mem_current": current,
        "mem_peak": peak,
        "result": result,
    }


def main() -> None:
    """全フェーズを実行する。"""
    import pyarrow.parquet as pq

    from edinet.extension import import_parquet, iter_parquet
    from edinet.financial.extract import extract_values

    # 前提チェック
    filings_path = PARQUET_DIR / f"{PREFIX}filings.parquet"
    if not filings_path.exists():
        print(f"エラー: {filings_path} が見つかりません。")
        print("先に tools/parquet_dump_stress_test.py を実行してください。")
        sys.exit(1)

    # ファイルサイズ一覧
    print("=" * 70)
    print("Parquet 読み込みストレステスト")
    print("=" * 70)

    total_mb = 0.0
    for p in sorted(PARQUET_DIR.glob(f"{PREFIX}*.parquet")):
        sz = p.stat().st_size / (1024 * 1024)
        total_mb += sz
    print(f"\nParquet 合計: {total_mb:.2f} MB")

    # doc_id 一覧を取得（フィルタ用）
    fi_table = pq.read_table(filings_path, columns=["doc_id"])
    all_doc_ids = fi_table.column("doc_id").to_pylist()
    total_count = len(all_doc_ids)
    print(f"書類数: {total_count}")

    # フィルタ用の doc_id サンプル
    sample_10 = all_doc_ids[:10]
    sample_100 = all_doc_ids[:100]

    results: list[dict[str, Any]] = []

    # =================================================================
    # Phase 1: import_parquet() — 全件読み込み
    # =================================================================
    # print("\n[Phase 1] import_parquet() — 全件読み込み")

    # def _phase1() -> dict[str, int]:
    #     data = import_parquet(PARQUET_DIR, prefix=PREFIX)
    #     xbrl = sum(1 for _, s in data if s is not None)
    #     total_items = sum(len(s) for _, s in data if s is not None)
    #     del data
    #     return {"count": len(all_doc_ids), "xbrl": xbrl, "items": total_items}

    # r = _measure("全件 (include_text_blocks=True)", _phase1)
    # info = r["result"]
    # print(f"    復元: {info['count']} 件, XBRL: {info['xbrl']}, "
    #       f"Items: {info['items']:,}")
    # results.append(r)
    # gc.collect()

    # =================================================================
    # Phase 2: import_parquet(include_text_blocks=False)
    # =================================================================
    # print("\n[Phase 2] import_parquet() — TextBlock 除外")

    # def _phase2() -> dict[str, int]:
    #     data = import_parquet(
    #         PARQUET_DIR, prefix=PREFIX, include_text_blocks=False,
    #     )
    #     xbrl = sum(1 for _, s in data if s is not None)
    #     total_items = sum(len(s) for _, s in data if s is not None)
    #     del data
    #     return {"count": total_count, "xbrl": xbrl, "items": total_items}

    # r = _measure("全件 (include_text_blocks=False)", _phase2)
    # info = r["result"]
    # print(f"    復元: {info['count']} 件, Items: {info['items']:,}")
    # results.append(r)
    # gc.collect()

    # =================================================================
    # Phase 3: import_parquet(doc_ids=...) — doc_id フィルタ
    # =================================================================
    # print("\n[Phase 3] import_parquet() — doc_id フィルタ")

    # def _phase3a() -> int:
    #     data = import_parquet(PARQUET_DIR, prefix=PREFIX, doc_ids=sample_10)
    #     n = len(data)
    #     del data
    #     return n

    # r = _measure(f"doc_ids={len(sample_10)}件", _phase3a)
    # print(f"    復元: {r['result']} 件")
    # results.append(r)
    # gc.collect()

    # def _phase3b() -> int:
    #     data = import_parquet(PARQUET_DIR, prefix=PREFIX, doc_ids=sample_100)
    #     n = len(data)
    #     del data
    #     return n

    # r = _measure(f"doc_ids={len(sample_100)}件", _phase3b)
    # print(f"    復元: {r['result']} 件")
    # results.append(r)
    # gc.collect()

    # =================================================================
    # Phase 4: import_parquet(concepts=...) — concepts フィルタ
    # =================================================================
    # print("\n[Phase 4] import_parquet() — concepts フィルタ")

    # def _phase4a() -> dict[str, int]:
    #     data = import_parquet(
    #         PARQUET_DIR, prefix=PREFIX, concepts=["NetSales"],
    #     )
    #     count = len(data)
    #     hits = sum(1 for _, s in data if s is not None and len(s) > 0)
    #     del data
    #     return {"count": count, "hits": hits}

    # r = _measure("concepts=['NetSales']", _phase4a)
    # print(f"    ヒット: {r['result']['hits']} 件")
    # results.append(r)
    # gc.collect()

    # def _phase4b() -> dict[str, int]:
    #     concepts = ["NetSales", "OperatingIncome", "TotalAssets",
    #                  "TotalLiabilities", "NetAssets"]
    #     data = import_parquet(
    #         PARQUET_DIR, prefix=PREFIX, concepts=concepts,
    #     )
    #     hits = sum(1 for _, s in data if s is not None and len(s) > 0)
    #     items = sum(len(s) for _, s in data if s is not None)
    #     del data
    #     return {"hits": hits, "items": items}

    # r = _measure("concepts=5科目", _phase4b)
    # print(f"    ヒット: {r['result']['hits']} 件, Items: {r['result']['items']:,}")
    # results.append(r)
    # gc.collect()

    # =================================================================
    # Phase 5: iter_parquet(batch_size=50)
    # =================================================================
    print("\n[Phase 5] iter_parquet() — batch_size=50")

    def _phase5() -> dict[str, int]:
        total = 0
        xbrl = 0
        for _, stmts in iter_parquet(
            PARQUET_DIR, prefix=PREFIX, batch_size=50,
        ):
            total += 1
            if stmts is not None:
                xbrl += 1
        return {"total": total, "xbrl": xbrl}

    r = _measure("batch_size=50", _phase5)
    print(f"    イテレーション: {r['result']['total']} 件, "
          f"XBRL: {r['result']['xbrl']}")
    results.append(r)
    gc.collect()

    # =================================================================
    # Phase 6: iter_parquet(batch_size=200)
    # =================================================================
    print("\n[Phase 6] iter_parquet() — batch_size=200")

    def _phase6() -> dict[str, int]:
        total = 0
        xbrl = 0
        for _, stmts in iter_parquet(
            PARQUET_DIR, prefix=PREFIX, batch_size=200,
        ):
            total += 1
            if stmts is not None:
                xbrl += 1
        return {"total": total, "xbrl": xbrl}

    r = _measure("batch_size=200", _phase6)
    print(f"    イテレーション: {r['result']['total']} 件, "
          f"XBRL: {r['result']['xbrl']}")
    results.append(r)
    gc.collect()

    # =================================================================
    # Phase 7: iter_parquet(concepts=...)
    # =================================================================
    print("\n[Phase 7] iter_parquet() — concepts フィルタ付き")

    def _phase7() -> dict[str, int]:
        total = 0
        hits = 0
        for _, stmts in iter_parquet(
            PARQUET_DIR, prefix=PREFIX,
            concepts=["NetSales", "OperatingIncome"],
            batch_size=100,
        ):
            total += 1
            if stmts is not None and len(stmts) > 0:
                hits += 1
        return {"total": total, "hits": hits}

    r = _measure("concepts=['NetSales','OperatingIncome'], batch=100", _phase7)
    print(f"    イテレーション: {r['result']['total']} 件, "
          f"ヒット: {r['result']['hits']}")
    results.append(r)
    gc.collect()

    # =================================================================
    # Phase 8: iter_parquet + extract_values — 実用パイプライン
    # =================================================================
    print("\n[Phase 8] iter_parquet() + extract_values() — 実用パイプライン")

    def _phase8() -> dict[str, int]:
        total = 0
        xbrl = 0
        revenue_hits = 0
        for _, stmts in iter_parquet(
            PARQUET_DIR, prefix=PREFIX, batch_size=100,
        ):
            total += 1
            if stmts is None:
                continue
            xbrl += 1
            result = extract_values(stmts, _EXTRACT_KEYS)
            if result.get("revenue") is not None:
                revenue_hits += 1
        return {"total": total, "xbrl": xbrl, "revenue": revenue_hits}

    r = _measure("iter + extract_values(5 keys), batch=100", _phase8)
    print(f"    処理: {r['result']['total']} 件, XBRL: {r['result']['xbrl']}, "
          f"revenue: {r['result']['revenue']}")
    results.append(r)
    gc.collect()

    # =================================================================
    # 比較サマリ
    # =================================================================
    print("\n" + "=" * 70)
    print("比較サマリ")
    print("=" * 70)

    print(f"\n{'Phase':<55s} {'時間':>8s}  {'メモリPeak':>12s}")
    print("-" * 80)
    for r in results:
        label = r["label"]
        t = r["elapsed"]
        peak = r["mem_peak"]
        print(f"  {label:<53s} {t:>7.2f}s  {_fmt_mb(peak):>12s}")

    # dump ベンチとの比較情報
    # baseline_import = results[0]  # Phase 1 が import_parquet 全件
    # baseline_iter = results[6]    # Phase 5 が iter_parquet batch=50

    print("\n比較:")
    print(f"  import_parquet (全件)       : "
          f"{baseline_import['elapsed']:.1f}s, "
          f"peak {_fmt_mb(baseline_import['mem_peak'])}")
    print(f"  iter_parquet (batch=50)     : "
          f"{baseline_iter['elapsed']:.1f}s, "
          f"peak {_fmt_mb(baseline_iter['mem_peak'])}")

    if baseline_import["mem_peak"] > 0:
        ratio = baseline_iter["mem_peak"] / baseline_import["mem_peak"]
        print(f"  メモリ比 (iter/import)     : {ratio:.1%}")

    speed_ratio = baseline_iter["elapsed"] / baseline_import["elapsed"]
    print(f"  速度比 (iter/import)       : {speed_ratio:.2f}x")

    # per-1k 処理時間
    print("\n1k件あたり処理時間:")
    for r in results:
        per_1k = r["elapsed"] / total_count * 1000
        print(f"  {r['label']:<53s} {per_1k:>7.1f}s/1k")

    # =================================================================
    # レポート保存
    # =================================================================
    report_path = PARQUET_DIR / "read_stress_test_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Parquet 読み込みストレステスト結果\n")
        f.write(f"書類数: {total_count}\n")
        f.write(f"Parquet 合計: {total_mb:.2f} MB\n\n")

        f.write(f"{'Phase':<55s} {'時間':>8s}  {'メモリPeak':>12s}\n")
        f.write("-" * 80 + "\n")
        for r in results:
            label = r["label"]
            t = r["elapsed"]
            peak = r["mem_peak"]
            f.write(f"  {label:<53s} {t:>7.2f}s  {_fmt_mb(peak):>12s}\n")

        f.write("\n比較:\n")
        f.write("  import (全件) vs iter (batch=50):\n")
        f.write(f"    import: {baseline_import['elapsed']:.1f}s, "
                f"peak {_fmt_mb(baseline_import['mem_peak'])}\n")
        f.write(f"    iter  : {baseline_iter['elapsed']:.1f}s, "
                f"peak {_fmt_mb(baseline_iter['mem_peak'])}\n")
        if baseline_import["mem_peak"] > 0:
            f.write(f"    メモリ比: "
                    f"{baseline_iter['mem_peak'] / baseline_import['mem_peak']:.1%}\n")

    print(f"\nレポート保存: {report_path}")


if __name__ == "__main__":
    main()

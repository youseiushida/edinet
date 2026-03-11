"""有報系統の書類を書類種別ごとにダンプするパイプライン。

書類種別ごとに別 prefix で adump_to_parquet() を呼び出し、
読み込み時に複数 prefix をまとめて iter_parquet() で処理できる。

対象書類種別:
  120: 有価証券報告書
  130: 訂正有価証券報告書
  140: 四半期報告書
  150: 訂正四半期報告書
  160: 半期報告書
  170: 訂正半期報告書

使い方:
    EDINET_API_KEY=... uv run python tools/dump_securities_reports.py \
        --start 2025-06-01 --end 2025-06-30

    # 出力先や並行数の変更
    EDINET_API_KEY=... uv run python tools/dump_securities_reports.py \
        --start 2025-06-01 --end 2025-06-30 \
        --output-dir ./parquet/securities \
        --concurrency 4

    # 読み込み時のイメージ（別スクリプトで）
    for prefix in ["120_2025-06-01_2025-06-30_", "130_2025-06-01_2025-06-30_", ...]:
        for filing, stmts in iter_parquet("./parquet/securities", prefix=prefix):
            ...
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import os
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

# プロジェクトルートを path に追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ROOT = Path(__file__).resolve().parent.parent

# 有報系統の書類種別
_SECURITIES_DOC_TYPES: dict[str, str] = {
    "120": "有価証券報告書",
    "130": "訂正有価証券報告書",
    "140": "四半期報告書",
    "150": "訂正四半期報告書",
    "160": "半期報告書",
    "170": "訂正半期報告書",
}


def _fmt_mb(b: float) -> str:
    """バイト数を MB 文字列にフォーマットする。"""
    return f"{b / (1024 * 1024):.1f} MB"


def _fmt_time(s: float) -> str:
    """秒数を見やすい文字列にフォーマットする。"""
    if s < 60:
        return f"{s:.1f}s"
    m, sec = divmod(s, 60)
    return f"{int(m)}m{sec:.0f}s"


def _measure_files(directory: Path, prefix: str) -> dict[str, float]:
    """Parquet ファイルのサイズ (MB) を計測する。"""
    sizes: dict[str, float] = {}
    total = 0.0
    for p in sorted(directory.glob(f"{prefix}*.parquet")):
        size_mb = p.stat().st_size / (1024 * 1024)
        sizes[p.name] = size_mb
        total += size_mb
    sizes["__total__"] = total
    return sizes


async def _dump_one(
    doc_type_code: str,
    label: str,
    *,
    start: str,
    end: str,
    output_dir: Path,
    concurrency: int,
    taxonomy_path: str | None,
    use_thread_pool: bool = False,
    max_workers: int = 4,
) -> dict[str, Any]:
    """1 書類種別をダンプし、計測結果を返す。"""
    prefix = f"{doc_type_code}_{start}_{end}_"
    mode_label = f"thread-pool(workers={max_workers})" if use_thread_pool else "async"
    print(f"\n{'─' * 60}")
    print(f"[{doc_type_code}] {label}  ({mode_label})")
    print(f"  prefix={prefix}, 期間={start}〜{end}")
    print(f"{'─' * 60}")

    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()

    if use_thread_pool:
        from edinet.extension import adump_to_parquet_thread_pool

        result = await adump_to_parquet_thread_pool(
            start=start,
            end=end,
            doc_type=doc_type_code,
            output_dir=output_dir,
            prefix=prefix,
            concurrency=concurrency,
            max_workers=max_workers,
            taxonomy_path=taxonomy_path,
            strict=False,
        )
    else:
        from edinet.extension import adump_to_parquet

        result = await adump_to_parquet(
            start=start,
            end=end,
            doc_type=doc_type_code,
            output_dir=output_dir,
            prefix=prefix,
            concurrency=concurrency,
            taxonomy_path=taxonomy_path,
            strict=False,
        )

    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()

    # ファイルサイズ
    file_sizes = _measure_files(output_dir, prefix)

    print(f"  書類数: {result.total_filings}")
    print(f"  XBRL: {result.xbrl_ok}/{result.xbrl_count} 成功")
    print(f"  エラー: {result.errors}")
    print(f"  時間: {_fmt_time(elapsed)}")
    print(f"  メモリ peak: {_fmt_mb(peak)}")
    print(f"  ファイルサイズ: {file_sizes['__total__']:.1f} MB")

    return {
        "doc_type_code": doc_type_code,
        "label": label,
        "prefix": prefix,
        "total_filings": result.total_filings,
        "xbrl_count": result.xbrl_count,
        "xbrl_ok": result.xbrl_ok,
        "errors": result.errors,
        "elapsed": elapsed,
        "mem_peak": peak,
        "file_size_mb": file_sizes["__total__"],
        "file_sizes": file_sizes,
    }


async def main() -> None:
    """メイン処理。"""
    parser = argparse.ArgumentParser(
        description="有報系統の書類を書類種別ごとにダンプする",
    )
    parser.add_argument("--start", required=True, help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="終了日 (YYYY-MM-DD)")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "parquet" / "securities"),
        help="出力ディレクトリ (default: parquet/securities/)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=8,
        help="同時ダウンロード数 (default: 8)",
    )
    parser.add_argument(
        "--doc-types", nargs="*", default=None,
        help="対象の書類種別コード (default: 120 130 140 150 160 170)",
    )
    parser.add_argument(
        "--thread-pool", action="store_true", default=False,
        help="ThreadPoolExecutor でパースをオフロードする",
    )
    parser.add_argument(
        "--max-workers", type=int, default=4,
        help="ThreadPool のワーカー数 (default: 4, --thread-pool 時のみ有効)",
    )
    parser.add_argument(
        "--api-key", required=True,
        help="EDINET API キー",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 対象 doc_type の決定
    if args.doc_types:
        doc_types = {
            code: _SECURITIES_DOC_TYPES.get(code, f"不明({code})")
            for code in args.doc_types
        }
    else:
        doc_types = dict(_SECURITIES_DOC_TYPES)

    # --- configure ---
    import edinet
    edinet.configure(api_key=args.api_key)

    # タクソノミ: 環境変数 → --start の年度で install_taxonomy() 自動解決
    taxonomy_path = os.environ.get("EDINET_TAXONOMY_ROOT")
    if taxonomy_path:
        edinet.configure(taxonomy_path=taxonomy_path)
    else:
        start_year = int(args.start[:4])
        available = edinet.list_taxonomy_versions()
        taxonomy_year = min(max(start_year, min(available)), max(available))
        if taxonomy_year != start_year:
            print(f"タクソノミ年度 {start_year} は範囲外のため {taxonomy_year} にフォールバック")
        info = edinet.install_taxonomy(year=taxonomy_year)
        taxonomy_path = str(info.path)
        print(f"タクソノミ自動解決: {info.year}年版 @ {info.path}")

    # ヘッダー
    print("=" * 60)
    print("有報系統ダンプパイプライン")
    print("=" * 60)
    print(f"期間: {args.start} 〜 {args.end}")
    print(f"出力先: {output_dir}")
    print(f"並行数: {args.concurrency}")
    print(f"対象: {', '.join(f'{k}({v})' for k, v in doc_types.items())}")
    if args.thread_pool:
        print(f"モード: thread-pool (max_workers={args.max_workers})")
    else:
        print("モード: async (デフォルト)")
    if taxonomy_path:
        print(f"タクソノミ: {taxonomy_path}")

    # --- 全体計測開始 ---
    gc.collect()
    tracemalloc.start()
    t_total_start = time.perf_counter()

    results: list[dict[str, Any]] = []

    for code, label in doc_types.items():
        r = await _dump_one(
            code, label,
            start=args.start,
            end=args.end,
            output_dir=output_dir,
            concurrency=args.concurrency,
            taxonomy_path=taxonomy_path,
            use_thread_pool=args.thread_pool,
            max_workers=args.max_workers,
        )
        results.append(r)

    t_total = time.perf_counter() - t_total_start
    _, total_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # =================================================================
    # サマリ
    # =================================================================
    print(f"\n{'=' * 60}")
    print("サマリ")
    print(f"{'=' * 60}")

    total_filings = sum(r["total_filings"] for r in results)
    total_xbrl_ok = sum(r["xbrl_ok"] for r in results)
    total_xbrl_count = sum(r["xbrl_count"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    total_size_mb = sum(r["file_size_mb"] for r in results)

    print(f"\n全体:")
    print(f"  合計書類数: {total_filings}")
    print(f"  XBRL 成功: {total_xbrl_ok}/{total_xbrl_count}")
    print(f"  エラー: {total_errors}")
    print(f"  合計時間: {_fmt_time(t_total)}")
    print(f"  メモリ peak (全体): {_fmt_mb(total_peak)}")
    print(f"  合計ファイルサイズ: {total_size_mb:.1f} MB")

    # 書類種別ごとの表
    print(f"\n{'コード':<6s} {'種別':<20s} {'書類数':>6s} {'XBRL':>10s} "
          f"{'時間':>8s} {'メモリ':>10s} {'サイズ':>8s}")
    print("-" * 72)
    for r in results:
        xbrl_str = f"{r['xbrl_ok']}/{r['xbrl_count']}"
        print(
            f"  {r['doc_type_code']:<4s} {r['label']:<20s} "
            f"{r['total_filings']:>6d} "
            f"{xbrl_str:>10s} "
            f"{_fmt_time(r['elapsed']):>8s} "
            f"{_fmt_mb(r['mem_peak']):>10s} "
            f"{r['file_size_mb']:>7.1f} MB"
        )

    # 0件の書類種別
    empty = [r for r in results if r["total_filings"] == 0]
    if empty:
        print(f"\n※ 0件: {', '.join(r['doc_type_code'] + '(' + r['label'] + ')' for r in empty)}")

    # =================================================================
    # テーブル別サイズ
    # =================================================================
    print(f"\n{'─' * 60}")
    print("テーブル別ファイルサイズ (MB)")
    print(f"{'─' * 60}")
    table_names = [
        "filings", "line_items", "text_blocks", "contexts",
        "dei", "calc_edges", "def_parents",
    ]
    for tname in table_names:
        row_sizes = []
        for r in results:
            fname = f"{r['prefix']}{tname}.parquet"
            size = r["file_sizes"].get(fname, 0.0)
            row_sizes.append(size)
        total_t = sum(row_sizes)
        if total_t > 0:
            detail = ", ".join(
                f"{r['doc_type_code']}={sz:.1f}"
                for r, sz in zip(results, row_sizes) if sz > 0
            )
            print(f"  {tname:<15s} {total_t:>7.1f} MB  ({detail})")

    # =================================================================
    # 読み込みサンプル
    # =================================================================
    print(f"\n{'─' * 60}")
    print("読み込み例:")
    print(f"{'─' * 60}")
    prefixes = [r["prefix"] for r in results if r["total_filings"] > 0]
    print(f"""
from edinet.extension import iter_parquet
from edinet.financial.extract import extract_values
from edinet.financial.standards.canonical_keys import CK

KEYS = [CK.REVENUE, CK.OPERATING_INCOME, CK.NET_INCOME]
PREFIXES = {prefixes}

for prefix in PREFIXES:
    for filing, stmts in iter_parquet(
        "{output_dir}", prefix=prefix, batch_size=100,
    ):
        if stmts is None:
            continue
        result = extract_values(stmts, KEYS)
        ...
""")

    # =================================================================
    # レポート保存
    # =================================================================
    report_path = output_dir / "dump_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("有報系統ダンプパイプライン 結果レポート\n")
        f.write(f"期間: {args.start} 〜 {args.end}\n")
        f.write(f"出力先: {output_dir}\n\n")

        f.write(f"合計書類数: {total_filings}\n")
        f.write(f"XBRL 成功: {total_xbrl_ok}/{total_xbrl_count}\n")
        f.write(f"エラー: {total_errors}\n")
        f.write(f"合計時間: {_fmt_time(t_total)}\n")
        f.write(f"メモリ peak: {_fmt_mb(total_peak)}\n")
        f.write(f"合計ファイルサイズ: {total_size_mb:.1f} MB\n\n")

        f.write(f"{'コード':<6s} {'種別':<20s} {'書類数':>6s} {'XBRL':>10s} "
                f"{'時間':>8s} {'メモリ':>10s} {'サイズ':>8s}\n")
        f.write("-" * 72 + "\n")
        for r in results:
            xbrl_str = f"{r['xbrl_ok']}/{r['xbrl_count']}"
            f.write(
                f"  {r['doc_type_code']:<4s} {r['label']:<20s} "
                f"{r['total_filings']:>6d} "
                f"{xbrl_str:>10s} "
                f"{_fmt_time(r['elapsed']):>8s} "
                f"{_fmt_mb(r['mem_peak']):>10s} "
                f"{r['file_size_mb']:>7.1f} MB\n"
            )

    print(f"レポート保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())

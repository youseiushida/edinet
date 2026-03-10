"""ストリーミング vs バッチ書き出しのメモリ比較。

既存の stress_line_items.parquet を読んで、
バッチ一括 vs ParquetWriter チャンクの書き出しメモリを計測する。

使い方:
    uv run python tools/_streaming_benchmark.py
"""

from __future__ import annotations

import gc
import shutil
import time
import tracemalloc
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

PARQUET_DIR = Path(__file__).resolve().parent.parent / "parquet"
BENCH_DIR = PARQUET_DIR / "bench_stream"
SOURCE = PARQUET_DIR / "stress_line_items.parquet"

# 1日分相当に制限（全3日のうち約1/3）
MAX_ROWS = 300_000


def main() -> None:
    if not SOURCE.exists():
        print(f"ソースファイルが見つかりません: {SOURCE}")
        return

    # ソース読み込み
    print("ソース読み込み中...")
    table = pq.read_table(SOURCE)
    if len(table) > MAX_ROWS:
        table = table.slice(0, MAX_ROWS)
    print(f"  行数: {len(table):,}")

    # dict リストに変換（RowAccumulator 相当）
    print("dict リストに変換中...")
    rows = table.to_pylist()
    print(f"  変換完了: {len(rows):,} rows")

    # nullable スキーマ
    nullable_fields = [pa.field(f.name, f.type, nullable=True) for f in table.schema]
    schema = pa.schema(nullable_fields)
    del table
    gc.collect()

    results: list[str] = []
    results.append(f"ストリーミング vs バッチ書き出しベンチマーク")
    results.append(f"行数: {len(rows):,}")
    results.append("")
    results.append(f"{'モード':>20} {'サイズMB':>9} {'書出s':>7} {'読込s':>7} {'ピークMB':>9}")
    results.append("-" * 60)

    configs = [
        ("batch", None),
        ("stream_5000", 5000),
        ("stream_1000", 1000),
        ("stream_200", 200),
    ]

    for mode, chunk_size in configs:
        out_dir = BENCH_DIR / mode
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "line_items.parquet"

        gc.collect()
        tracemalloc.start()

        t0 = time.perf_counter()

        if chunk_size is None:
            # バッチ: 全行を一括で Table → write
            t = pa.Table.from_pylist(rows, schema=schema)
            pq.write_table(t, out_path, compression="zstd")
            del t
        else:
            # ストリーミング: チャンクごとに write
            writer = pq.ParquetWriter(out_path, schema, compression="zstd")
            try:
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i : i + chunk_size]
                    t = pa.Table.from_pylist(chunk, schema=schema)
                    writer.write_table(t)
                    del t
            finally:
                writer.close()

        t_write = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        size_mb = out_path.stat().st_size / (1024 * 1024)

        # 読み込み速度
        t0 = time.perf_counter()
        pq.read_table(out_path)
        t_read = time.perf_counter() - t0

        peak_mb = peak / (1024 * 1024)
        line = f"{mode:>20} {size_mb:>9.2f} {t_write:>7.2f} {t_read:>7.2f} {peak_mb:>9.1f}"
        print(f"  {line}")
        results.append(line)

        # クリーンアップ
        shutil.rmtree(out_dir)

    # ベンチディレクトリ削除
    if BENCH_DIR.exists():
        shutil.rmtree(BENCH_DIR)

    # レポートに追記
    report_path = Path(__file__).resolve().parent.parent / "docs" / "compression_benchmark.txt"
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + "\n".join(results) + "\n")
    print(f"\nレポート追記: {report_path}")


if __name__ == "__main__":
    main()

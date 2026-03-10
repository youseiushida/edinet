"""圧縮アルゴリズム & ストリーミング書き出しの比較ベンチマーク。

1日分（2025-06-25）のデータで以下を計測:
- snappy / zstd / gzip / none の圧縮率・書き出し時間・読み込み時間
- バッチ書き出し vs ParquetWriter ストリーミングのメモリ使用量

使い方:
    EDINET_API_KEY=your_api_key_here uv run python tools/_compression_benchmark.py
"""

from __future__ import annotations

import asyncio
import gc
import os
import shutil
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet
from edinet.extension._serialize import (
    serialize_calc_edges,
    serialize_context,
    serialize_dei,
    serialize_def_parents,
    serialize_filing,
    serialize_line_item,
)
from edinet.models.filing import Filing

TARGET_DATE = "2025-06-25"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "parquet" / "bench"
CONCURRENCY = 8
REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "compression_benchmark.txt"

COMPRESSIONS = ["snappy", "zstd", "gzip", "none"]


class RowAccumulator:
    """dict 行を蓄積する。"""

    def __init__(self) -> None:
        self.filing_rows: list[dict[str, Any]] = []
        self.line_item_rows: list[dict[str, Any]] = []
        self.context_rows: list[dict[str, Any]] = []
        self.dei_rows: list[dict[str, Any]] = []
        self.calc_rows: list[dict[str, Any]] = []
        self.def_rows: list[dict[str, Any]] = []

    def add_filing(self, filing: Filing) -> None:
        self.filing_rows.append(serialize_filing(filing))

    def add_statements(self, filing: Filing, stmts: Any) -> None:
        doc_id = filing.doc_id
        for item in stmts:
            self.line_item_rows.append(serialize_line_item(item, doc_id))
        ctx_map = stmts.context_map
        if ctx_map:
            for ctx in ctx_map.values():
                self.context_rows.append(serialize_context(ctx, doc_id))
        dei = stmts.dei
        if dei is not None:
            self.dei_rows.append(
                serialize_dei(dei, doc_id, detected_standard=stmts.detected_standard)
            )
        calc = stmts.calculation_linkbase
        if calc is not None:
            self.calc_rows.extend(serialize_calc_edges(calc, doc_id))
        defn = stmts.definition_linkbase
        if defn is not None:
            self.def_rows.extend(serialize_def_parents(defn, doc_id))

    @property
    def all_tables(self) -> list[tuple[str, list[dict[str, Any]]]]:
        return [
            ("filings", self.filing_rows),
            ("line_items", self.line_item_rows),
            ("contexts", self.context_rows),
            ("dei", self.dei_rows),
            ("calc_edges", self.calc_rows),
            ("def_parents", self.def_rows),
        ]


def write_batch(acc: RowAccumulator, out_dir: Path, compression: str | None) -> dict[str, float]:
    """一括書き出し。ファイルサイズ (MB) を返す。"""
    import pyarrow as pa
    import pyarrow.parquet as pq

    out_dir.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, float] = {}
    comp = None if compression == "none" else compression

    for name, rows in acc.all_tables:
        if not rows:
            continue
        path = out_dir / f"{name}.parquet"
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, path, compression=comp)
        sizes[name] = path.stat().st_size / (1024 * 1024)

    sizes["__total__"] = sum(v for v in sizes.values())
    return sizes


def write_streaming(
    acc: RowAccumulator, out_dir: Path, compression: str | None, chunk_size: int = 1000,
) -> dict[str, float]:
    """ParquetWriter でチャンク書き出し。"""
    import pyarrow as pa
    import pyarrow.parquet as pq

    out_dir.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, float] = {}
    comp = None if compression == "none" else compression

    for name, rows in acc.all_tables:
        if not rows:
            continue
        path = out_dir / f"{name}.parquet"

        # 最初のチャンクからスキーマ推論し、全フィールドを nullable にする
        first_table = pa.Table.from_pylist(rows[:chunk_size])
        nullable_fields = [pa.field(f.name, f.type, nullable=True) for f in first_table.schema]
        schema = pa.schema(nullable_fields)
        del first_table

        writer = pq.ParquetWriter(path, schema, compression=comp)
        try:
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i : i + chunk_size]
                batch_table = pa.Table.from_pylist(chunk, schema=schema)
                writer.write_table(batch_table)
        finally:
            writer.close()

        sizes[name] = path.stat().st_size / (1024 * 1024)

    sizes["__total__"] = sum(v for v in sizes.values())
    return sizes


def read_all(out_dir: Path) -> float:
    """全 Parquet ファイルを読み込み、合計時間 (s) を返す。"""
    import pyarrow.parquet as pq

    t0 = time.perf_counter()
    for p in sorted(out_dir.glob("*.parquet")):
        pq.read_table(p)
    return time.perf_counter() - t0


async def collect_data() -> RowAccumulator:
    """1日分のデータをパース・シリアライズして RowAccumulator に蓄積する。"""
    acc = RowAccumulator()
    sem = asyncio.Semaphore(CONCURRENCY)

    filings = await edinet.adocuments(date=TARGET_DATE)
    print(f"  書類数: {len(filings)} (XBRL有: {sum(1 for f in filings if f.has_xbrl)})")

    xbrl_filings = [f for f in filings if f.has_xbrl]
    for f in filings:
        if not f.has_xbrl:
            acc.add_filing(f)

    total = len(xbrl_filings)
    done = 0
    ok = 0
    errors = 0
    t0 = time.perf_counter()

    async def process(filing: Filing) -> None:
        nonlocal done, ok, errors
        async with sem:
            acc.add_filing(filing)
            try:
                stmts = await filing.axbrl(strict=False)
                acc.add_statements(filing, stmts)
                ok += 1
                del stmts
            except Exception:
                errors += 1
            finally:
                filing.clear_fetch_cache()

    batch_size = 20
    for i in range(0, total, batch_size):
        batch = xbrl_filings[i : i + batch_size]
        await asyncio.gather(*(process(f) for f in batch))
        done += len(batch)
        elapsed = time.perf_counter() - t0
        rate = done / elapsed if elapsed > 0 else 0
        print(f"  パース: {done}/{total} ({elapsed:.0f}s, {rate:.1f}/s, ok={ok}, err={errors})")
        gc.collect()

    print(f"  完了: ok={ok}, err={errors}")
    return acc


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY", "your_api_key_here")
    edinet.configure(api_key=api_key)

    tax_info = edinet.install_taxonomy(year=2025)
    print(f"タクソノミ: {tax_info.path}")

    print(f"\n[Phase 1] {TARGET_DATE} のデータ収集...")
    acc = collect_data_result = await collect_data()

    lines: list[str] = []
    lines.append(f"圧縮ベンチマーク: {TARGET_DATE}")
    lines.append(f"行数: line_items={len(acc.line_item_rows):,}, "
                 f"contexts={len(acc.context_rows):,}, "
                 f"filings={len(acc.filing_rows):,}")
    lines.append("")

    print(f"\n  行数: line_items={len(acc.line_item_rows):,}, "
          f"contexts={len(acc.context_rows):,}")

    # --- 圧縮アルゴリズム比較 ---
    print(f"\n[Phase 2] 圧縮アルゴリズム比較...")
    lines.append("=" * 60)
    lines.append("圧縮アルゴリズム比較 (バッチ書き出し)")
    lines.append("=" * 60)

    results: dict[str, dict[str, Any]] = {}

    for comp in COMPRESSIONS:
        out_dir = OUTPUT_DIR / f"batch_{comp}"
        if out_dir.exists():
            shutil.rmtree(out_dir)

        print(f"\n  --- {comp} ---")

        # 書き出し
        gc.collect()
        tracemalloc.start()
        t_write = time.perf_counter()
        sizes = write_batch(acc, out_dir, comp)
        t_write = time.perf_counter() - t_write
        _, peak_write = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 読み込み
        t_read = read_all(out_dir)

        total_mb = sizes["__total__"]
        li_mb = sizes.get("line_items", 0)

        results[comp] = {
            "total_mb": total_mb,
            "line_items_mb": li_mb,
            "write_s": t_write,
            "read_s": t_read,
            "peak_mem_mb": peak_write / (1024 * 1024),
        }

        print(f"    合計: {total_mb:.2f} MB (line_items: {li_mb:.2f} MB)")
        print(f"    書き出し: {t_write:.2f}s / 読み込み: {t_read:.2f}s")
        print(f"    ピークメモリ(書き出し): {peak_write / (1024*1024):.1f} MB")

    # 比較表
    snappy_total = results["snappy"]["total_mb"]
    lines.append("")
    lines.append(f"{'アルゴリズム':>12} {'合計MB':>8} {'圧縮率':>8} {'LI MB':>10} "
                 f"{'書出s':>7} {'読込s':>7} {'ピークMB':>9}")
    lines.append("-" * 75)
    for comp in COMPRESSIONS:
        r = results[comp]
        ratio = r["total_mb"] / snappy_total if snappy_total > 0 else 0
        line = (f"{comp:>12} {r['total_mb']:>8.2f} {ratio:>7.1%} {r['line_items_mb']:>10.2f} "
                f"{r['write_s']:>7.2f} {r['read_s']:>7.2f} {r['peak_mem_mb']:>9.1f}")
        lines.append(line)
        print(f"  {line}")

    # --- ストリーミング vs バッチ（zstd で比較）---
    print(f"\n[Phase 3] バッチ vs ストリーミング (zstd)...")
    lines.append("")
    lines.append("=" * 60)
    lines.append("バッチ vs ストリーミング (zstd, chunk_size=1000)")
    lines.append("=" * 60)

    for mode, chunk in [("batch", None), ("streaming_1000", 1000), ("streaming_200", 200)]:
        out_dir = OUTPUT_DIR / f"stream_{mode}"
        if out_dir.exists():
            shutil.rmtree(out_dir)

        gc.collect()
        tracemalloc.start()
        t0 = time.perf_counter()
        if chunk is None:
            sizes = write_batch(acc, out_dir, "zstd")
        else:
            sizes = write_streaming(acc, out_dir, "zstd", chunk_size=chunk)
        t_w = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        t_r = read_all(out_dir)
        total_mb = sizes["__total__"]

        line = (f"  {mode:>20}: {total_mb:.2f} MB, "
                f"書出 {t_w:.2f}s, 読込 {t_r:.2f}s, "
                f"ピーク {peak / (1024*1024):.1f} MB")
        print(line)
        lines.append(line)

    await edinet.aclose()

    # クリーンアップ
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    # レポート保存
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nレポート保存: {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())

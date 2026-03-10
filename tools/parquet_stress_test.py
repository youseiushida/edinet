"""Parquet ストレステスト: 有報集中日 (2025/6/25) 1日分を永続化して性能を計測する。

公開 API (export_parquet / import_parquet) を直接使い、
ライブラリが実際に通るコードパスをテストする。
1日単位は実運用でも推奨される粒度。

計測項目:
  - 速度: パース / export / import の各フェーズ
  - メモリ: パース蓄積 / export / import のピーク (tracemalloc)
  - ファイルサイズ: Parquet 合計

使い方:
    EDINET_API_KEY=... uv run python tools/parquet_stress_test.py
"""

from __future__ import annotations

import asyncio
import gc
import os
import sys
import time
import tracemalloc
from pathlib import Path

# プロジェクトルートを path に追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet
from edinet.extension import export_parquet, import_parquet
from edinet.financial.statements import Statements
from edinet.models.filing import Filing

# --- 設定 ---
TARGET_DATE = "2025-06-25"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "parquet"
CONCURRENCY = 8  # 同時 axbrl() 数
LOG_EVERY = 20   # N 件ごとに進捗表示


async def parse_all_xbrl(
    filings: list[Filing],
) -> tuple[list[tuple[Filing, Statements | None]], int, int]:
    """全書類を非同期パースし (Filing, Statements | None) ペアを返す。

    Returns:
        (data, パース成功数, エラー数)
    """
    sem = asyncio.Semaphore(CONCURRENCY)
    data: list[tuple[Filing, Statements | None]] = []

    # non-XBRL は Statements=None で追加
    for f in filings:
        if not f.has_xbrl:
            data.append((f, None))

    xbrl_filings = [f for f in filings if f.has_xbrl]
    total = len(xbrl_filings)
    done = 0
    errors = 0
    ok = 0
    t0 = time.perf_counter()

    async def process_one(filing: Filing) -> None:
        nonlocal done, errors, ok
        async with sem:
            try:
                stmts = await filing.axbrl()
                data.append((filing, stmts))
                ok += 1
            except Exception as e:
                data.append((filing, None))
                errors += 1
                print(f"  [WARN] {filing.doc_id} ({filing.filer_name}): {e!r}")
            finally:
                filing.clear_fetch_cache()

    # バッチ処理 + 進捗表示
    batch_size = LOG_EVERY
    for i in range(0, total, batch_size):
        batch = xbrl_filings[i : i + batch_size]
        await asyncio.gather(*(process_one(f) for f in batch))
        done += len(batch)
        elapsed = time.perf_counter() - t0
        rate = done / elapsed if elapsed > 0 else 0
        print(
            f"  XBRL パース: {done}/{total} "
            f"({elapsed:.1f}s, {rate:.1f} filings/s, ok={ok}, err={errors})"
        )
        gc.collect()

    return data, ok, errors


def measure_files(directory: Path, prefix: str) -> dict[str, float]:
    """Parquet ファイルのサイズ (MB) を計測する。"""
    sizes: dict[str, float] = {}
    total = 0.0
    for p in sorted(directory.glob(f"{prefix}*.parquet")):
        size_mb = p.stat().st_size / (1024 * 1024)
        sizes[p.name] = size_mb
        total += size_mb
    sizes["__total__"] = total
    return sizes


def _fmt_mb(b: float) -> str:
    """バイト数を MB 文字列にフォーマットする。"""
    return f"{b / (1024 * 1024):.2f} MB"


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY", "your_api_key_here")
    edinet.configure(api_key=api_key)

    # 2025年版タクソノミ（2025/6 の書類に対応）を自動インストール
    print("タクソノミ確認中...")
    info = edinet.install_taxonomy(year=2025)
    print(f"  {info.year}年版タクソノミ: {info.path}")

    print("=" * 70)
    print(f"Parquet ストレステスト: {TARGET_DATE} (1日分)")
    print("=" * 70)

    # --- Phase 1: 書類一覧取得 ---
    print("\n[Phase 1] 書類一覧取得...")
    t_start = time.perf_counter()
    filings = await edinet.adocuments(date=TARGET_DATE)
    t_list = time.perf_counter() - t_start

    total_filings = len(filings)
    xbrl_count = sum(1 for f in filings if f.has_xbrl)
    print(f"  取得: {total_filings} 件 (XBRL有: {xbrl_count}) in {t_list:.1f}s")

    # --- Phase 2: パース + メモリ計測 ---
    print(f"\n[Phase 2] XBRL パース (concurrency={CONCURRENCY})...")
    gc.collect()
    tracemalloc.start()
    t_parse_start = time.perf_counter()
    data, xbrl_ok, xbrl_err = await parse_all_xbrl(filings)
    t_parse = time.perf_counter() - t_parse_start
    parse_current, parse_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"  完了: {xbrl_ok}/{xbrl_count} パース成功 in {t_parse:.1f}s")
    print(f"  メモリ: current={_fmt_mb(parse_current)}, peak={_fmt_mb(parse_peak)}")

    # --- Phase 3: export_parquet() + メモリ計測 ---
    print("\n[Phase 3] export_parquet() (zstd, row_group_size=5000)...")
    prefix = "stress_"
    gc.collect()
    tracemalloc.start()
    t_export_start = time.perf_counter()
    result = export_parquet(data, OUTPUT_DIR, prefix=prefix)
    t_export = time.perf_counter() - t_export_start
    export_current, export_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"  書き出し完了 in {t_export:.1f}s ({len(result)} テーブル)")
    print(f"  メモリ: current={_fmt_mb(export_current)}, peak={_fmt_mb(export_peak)}")

    # Statements を解放
    del data
    gc.collect()

    # --- Phase 4: サイズ計測 ---
    print("\n[Phase 4] ファイルサイズ計測...")
    sizes = measure_files(OUTPUT_DIR, prefix)
    for name, size_mb in sorted(sizes.items()):
        if name == "__total__":
            continue
        print(f"  {name}: {size_mb:.2f} MB")
    total_mb = sizes["__total__"]
    print(f"  ─────────────────")
    print(f"  合計: {total_mb:.2f} MB")

    # --- Phase 5: import_parquet() + メモリ計測 ---
    print("\n[Phase 5] import_parquet()...")
    gc.collect()
    tracemalloc.start()
    t_import_start = time.perf_counter()
    restored = import_parquet(OUTPUT_DIR, prefix=prefix)
    t_import = time.perf_counter() - t_import_start
    import_current, import_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    restored_xbrl = sum(1 for _, s in restored if s is not None)
    print(f"  復元: {len(restored)} 件 (Statements有: {restored_xbrl}) in {t_import:.1f}s")
    print(f"  メモリ: current={_fmt_mb(import_current)}, peak={_fmt_mb(import_peak)}")
    del restored
    gc.collect()

    # --- 統計サマリ ---
    t_total = time.perf_counter() - t_start

    print("\n" + "=" * 70)
    print("統計サマリ")
    print("=" * 70)

    print(f"\n書類数:")
    print(f"  全書類:        {total_filings}")
    print(f"  XBRL有:        {xbrl_count}")
    print(f"  パース成功:    {xbrl_ok}")
    if xbrl_err:
        print(f"  パースエラー:  {xbrl_err}")

    print(f"\n処理時間:")
    print(f"  一覧取得:        {t_list:.1f}s")
    print(f"  パース:          {t_parse:.1f}s")
    print(f"  export_parquet:  {t_export:.1f}s")
    print(f"  import_parquet:  {t_import:.1f}s")
    print(f"  合計:            {t_total:.1f}s")

    per_1k_parse = 0.0
    per_1k_export = 0.0
    per_1k_import = 0.0
    if xbrl_ok > 0:
        per_1k_parse = t_parse / xbrl_ok * 1000
        per_1k_export = t_export / total_filings * 1000
        per_1k_import = t_import / total_filings * 1000
        print(f"\n1k件あたり処理時間:")
        print(f"  パース:          {per_1k_parse:.1f}s / 1k filings")
        print(f"  export_parquet:  {per_1k_export:.1f}s / 1k filings")
        print(f"  import_parquet:  {per_1k_import:.1f}s / 1k filings")

    print(f"\nメモリ (tracemalloc ピーク):")
    print(f"  パース+蓄積:     {_fmt_mb(parse_peak)}")
    print(f"  export_parquet:  {_fmt_mb(export_peak)}")
    print(f"  import_parquet:  {_fmt_mb(import_peak)}")

    print(f"\nファイルサイズ:")
    print(f"  Parquet 合計:      {total_mb:.2f} MB")
    per_filing_kb = total_mb * 1024 / total_filings if total_filings > 0 else 0
    per_xbrl_kb = total_mb * 1024 / xbrl_ok if xbrl_ok > 0 else 0
    print(f"  1件あたり:         {per_filing_kb:.1f} KB (全書類)")
    print(f"  1件あたり:         {per_xbrl_kb:.1f} KB (XBRL有のみ)")

    await edinet.aclose()

    # レポート保存
    report_path = OUTPUT_DIR / "stress_test_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Parquet ストレステスト結果\n")
        f.write(f"日付: {TARGET_DATE}\n\n")
        f.write(f"書類数: 全{total_filings}, XBRL有{xbrl_count}, "
                f"パース成功{xbrl_ok}, エラー{xbrl_err}\n\n")
        f.write(f"処理時間:\n")
        f.write(f"  一覧取得:        {t_list:.1f}s\n")
        f.write(f"  パース:          {t_parse:.1f}s\n")
        f.write(f"  export_parquet:  {t_export:.1f}s\n")
        f.write(f"  import_parquet:  {t_import:.1f}s\n")
        f.write(f"  合計:            {t_total:.1f}s\n")
        if xbrl_ok > 0:
            f.write(f"  1kあたり: パース{per_1k_parse:.1f}s "
                    f"export{per_1k_export:.1f}s import{per_1k_import:.1f}s\n")
        f.write(f"\nメモリ (tracemalloc ピーク):\n")
        f.write(f"  パース+蓄積:     {_fmt_mb(parse_peak)}\n")
        f.write(f"  export_parquet:  {_fmt_mb(export_peak)}\n")
        f.write(f"  import_parquet:  {_fmt_mb(import_peak)}\n")
        f.write(f"\nファイルサイズ:\n")
        f.write(f"  Parquet 合計:      {total_mb:.2f} MB\n")
        for name, size_mb in sorted(sizes.items()):
            if name != "__total__":
                f.write(f"    {name}: {size_mb:.2f} MB\n")
        f.write(f"  1件あたり: {per_filing_kb:.1f} KB (全), {per_xbrl_kb:.1f} KB (XBRL)\n")
    print(f"\nレポート保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())

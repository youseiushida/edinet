"""adump_to_parquet ストレステスト: 有報集中日 (2025/6/25) 1日分を永続化して性能を計測する。

adump_to_parquet() を使い、メモリ効率パイプラインの性能を計測する。

計測項目:
  Phase 1: adump_to_parquet — 速度・メモリ
  Phase 2: ファイルサイズ（テーブル別 + TextBlock 占有率）
  Phase 3: import_parquet — 速度・メモリ
  Phase 4: 復元後マッパー実行 — extract_values() / build_summary() の動作検証
  Phase 5: def_parents 復元状況の検証
  Phase 6: source_path 復元状況の検証

使い方:
    EDINET_API_KEY=... uv run python tools/parquet_dump_stress_test.py
"""

from __future__ import annotations

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

import edinet
from edinet.extension import adump_to_parquet, import_parquet

# --- 設定 ---
TARGET_DATE = "2025-06-25"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "parquet"
PREFIX = "dump_stress_"
CONCURRENCY = 8

# extract_values で検証する主要キー
_EXTRACT_KEYS = [
    "revenue",
    "operating_income",
    "net_income",
    "total_assets",
    "net_assets",
]


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


def measure_textblock_ratio(directory: Path, prefix: str) -> dict[str, int]:
    """line_items テーブル内の TextBlock 行数と非 TextBlock 行数を計測する。"""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return {"text_block": 0, "non_text_block": 0, "total": 0}

    li_path = directory / f"{prefix}line_items.parquet"
    if not li_path.exists():
        return {"text_block": 0, "non_text_block": 0, "total": 0}

    table = pq.read_table(li_path, columns=["local_name", "value_type"])
    total = len(table)

    # TextBlock 判定: local_name が "TextBlock" で終わる
    local_names = table.column("local_name").to_pylist()
    tb_count = sum(1 for n in local_names if n and n.endswith("TextBlock"))

    # value_type == "str" の件数（TextBlock 含むテキスト系全般）
    value_types = table.column("value_type").to_pylist()
    str_count = sum(1 for v in value_types if v == "str")

    del table
    return {
        "text_block": tb_count,
        "value_type_str": str_count,
        "non_text_block": total - tb_count,
        "total": total,
    }


def measure_textblock_bytes(directory: Path, prefix: str) -> dict[str, int]:
    """line_items テーブルの TextBlock 行 vs 非 TextBlock 行のバイト数を推計する。"""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return {"text_block_bytes": 0, "other_bytes": 0}

    li_path = directory / f"{prefix}line_items.parquet"
    if not li_path.exists():
        return {"text_block_bytes": 0, "other_bytes": 0}

    table = pq.read_table(li_path, columns=["local_name", "value_text"])
    tb_bytes = 0
    other_bytes = 0
    local_names = table.column("local_name").to_pylist()
    value_texts = table.column("value_text").to_pylist()

    for name, text in zip(local_names, value_texts):
        size = len(text.encode("utf-8")) if text else 0
        if name and name.endswith("TextBlock"):
            tb_bytes += size
        else:
            other_bytes += size

    del table
    return {"text_block_bytes": tb_bytes, "other_bytes": other_bytes}


def verify_def_parents(directory: Path, prefix: str) -> dict[str, int]:
    """def_parents テーブルの復元状況を検証する。"""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return {"exists": False, "rows": 0, "docs": 0}

    dp_path = directory / f"{prefix}def_parents.parquet"
    if not dp_path.exists():
        return {"exists": False, "rows": 0, "docs": 0}

    table = pq.read_table(dp_path)
    rows = len(table)
    docs = len(set(table.column("doc_id").to_pylist()))
    del table
    return {"exists": True, "rows": rows, "docs": docs}


def run_mapper_benchmark(
    restored: list[tuple[Any, Any]],
) -> dict[str, object]:
    """復元後の Statements に対して extract_values / build_summary を実行する。"""
    from edinet.financial.extract import extract_values
    from edinet.financial.summary import build_summary

    extract_ok = 0
    extract_fail = 0
    extract_errors: list[str] = []
    extract_hit_counts: dict[str, int] = {k: 0 for k in _EXTRACT_KEYS}

    summary_ok = 0
    summary_fail = 0

    t_extract_total = 0.0
    t_summary_total = 0.0

    for filing, stmts in restored:
        if stmts is None:
            continue

        # extract_values
        t0 = time.perf_counter()
        try:
            result = extract_values(stmts, _EXTRACT_KEYS)
            t_extract_total += time.perf_counter() - t0
            extract_ok += 1
            for k, v in result.items():
                if v is not None:
                    extract_hit_counts[k] += 1
        except Exception as e:
            t_extract_total += time.perf_counter() - t0
            extract_fail += 1
            doc_id = getattr(filing, "doc_id", "?")
            if len(extract_errors) < 5:
                extract_errors.append(f"{doc_id}: {type(e).__name__}: {e}")

        # build_summary
        t0 = time.perf_counter()
        try:
            build_summary(stmts)
            t_summary_total += time.perf_counter() - t0
            summary_ok += 1
        except Exception:
            t_summary_total += time.perf_counter() - t0
            summary_fail += 1

    return {
        "extract_ok": extract_ok,
        "extract_fail": extract_fail,
        "extract_errors": extract_errors,
        "extract_hit_counts": extract_hit_counts,
        "extract_time": t_extract_total,
        "summary_ok": summary_ok,
        "summary_fail": summary_fail,
        "summary_time": t_summary_total,
    }


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY", "your_api_key_here")
    edinet.configure(api_key=api_key)

    # 2025年版タクソノミ（2025/6 の書類に対応）を自動インストール
    print("タクソノミ確認中...")
    info = edinet.install_taxonomy(year=2025)
    print(f"  {info.year}年版タクソノミ: {info.path}")

    print("=" * 70)
    print(f"adump_to_parquet ストレステスト: {TARGET_DATE} (1日分)")
    print(f"  concurrency={CONCURRENCY}, compression=zstd")
    print("=" * 70)

    # =====================================================================
    # Phase 1: adump_to_parquet() + メモリ計測
    # =====================================================================
    print("\n[Phase 1] adump_to_parquet() (取得→パース→書き出し)...")
    gc.collect()
    tracemalloc.start()
    t_start = time.perf_counter()

    result = await adump_to_parquet(
        date=TARGET_DATE,
        output_dir=OUTPUT_DIR,
        prefix=PREFIX,
        concurrency=CONCURRENCY,
        strict=False,
    )

    t_dump = time.perf_counter() - t_start
    dump_current, dump_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"  完了 in {t_dump:.1f}s")
    print(f"  書類数: 全{result.total_filings}, "
          f"XBRL有{result.xbrl_count}, "
          f"パース成功{result.xbrl_ok}, "
          f"エラー{result.errors}")
    print(f"  出力テーブル: {len(result.paths)}")
    print(f"  メモリ: current={_fmt_mb(dump_current)}, peak={_fmt_mb(dump_peak)}")

    gc.collect()

    # =====================================================================
    # Phase 2: ファイルサイズ + TextBlock 占有率
    # =====================================================================
    print("\n[Phase 2] ファイルサイズ + TextBlock 分析...")
    sizes = measure_files(OUTPUT_DIR, PREFIX)
    for name, size_mb in sorted(sizes.items()):
        if name == "__total__":
            continue
        print(f"  {name}: {size_mb:.2f} MB")
    total_mb = sizes["__total__"]
    print("  ─────────────────")
    print(f"  合計: {total_mb:.2f} MB")

    # TextBlock 行数分析
    tb_ratio = measure_textblock_ratio(OUTPUT_DIR, PREFIX)
    if tb_ratio["total"] > 0:
        pct = tb_ratio["text_block"] / tb_ratio["total"] * 100
        str_pct = tb_ratio["value_type_str"] / tb_ratio["total"] * 100
        print(f"\n  line_items 行数: {tb_ratio['total']:,}")
        print(f"    TextBlock:     {tb_ratio['text_block']:,} ({pct:.1f}%)")
        print(f"    value_type=str: {tb_ratio['value_type_str']:,} ({str_pct:.1f}%)")
        print(f"    非TextBlock:   {tb_ratio['non_text_block']:,}")

    # TextBlock バイト数分析
    tb_bytes = measure_textblock_bytes(OUTPUT_DIR, PREFIX)
    tb_b = tb_bytes["text_block_bytes"]
    other_b = tb_bytes["other_bytes"]
    total_text_b = tb_b + other_b
    if total_text_b > 0:
        tb_pct = tb_b / total_text_b * 100
        print(f"\n  value_text バイト数 (非圧縮):")
        print(f"    TextBlock:     {tb_b / 1024 / 1024:.2f} MB ({tb_pct:.1f}%)")
        print(f"    その他テキスト: {other_b / 1024 / 1024:.2f} MB")

    # =====================================================================
    # Phase 3: import_parquet() + メモリ計測
    # =====================================================================
    print("\n[Phase 3] import_parquet()...")
    gc.collect()
    tracemalloc.start()
    t_import_start = time.perf_counter()
    restored = import_parquet(OUTPUT_DIR, prefix=PREFIX)
    t_import = time.perf_counter() - t_import_start
    import_current, import_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    restored_xbrl = sum(1 for _, s in restored if s is not None)
    print(f"  復元: {len(restored)} 件 (Statements有: {restored_xbrl}) in {t_import:.1f}s")
    print(f"  メモリ: current={_fmt_mb(import_current)}, peak={_fmt_mb(import_peak)}")

    # =====================================================================
    # Phase 4: 復元後マッパー実行テスト
    # =====================================================================
    print("\n[Phase 4] 復元後マッパー実行テスト...")
    gc.collect()
    t_mapper_start = time.perf_counter()
    mapper_result = run_mapper_benchmark(restored)
    t_mapper = time.perf_counter() - t_mapper_start

    print(f"  extract_values():")
    print(f"    成功: {mapper_result['extract_ok']}, "
          f"失敗: {mapper_result['extract_fail']}, "
          f"所要: {mapper_result['extract_time']:.2f}s")
    hit_counts = mapper_result["extract_hit_counts"]
    for k, cnt in hit_counts.items():
        print(f"      {k}: {cnt} 件ヒット")
    if mapper_result["extract_errors"]:
        print(f"    エラー例:")
        for err in mapper_result["extract_errors"]:
            print(f"      {err}")

    print(f"  build_summary():")
    print(f"    成功: {mapper_result['summary_ok']}, "
          f"失敗: {mapper_result['summary_fail']}, "
          f"所要: {mapper_result['summary_time']:.2f}s")

    # =====================================================================
    # Phase 5: def_parents 復元検証
    # =====================================================================
    print("\n[Phase 5] def_parents 復元検証...")
    dp_info = verify_def_parents(OUTPUT_DIR, PREFIX)
    print(f"  ファイル存在: {dp_info['exists']}")
    if dp_info["exists"]:
        print(f"  行数: {dp_info['rows']:,}")
        print(f"  書類数: {dp_info['docs']}")

    # def_parents が Statements に結線されているか確認
    dp_connected = 0
    dp_disconnected = 0
    for _, stmts in restored:
        if stmts is None:
            continue
        dpi = stmts.definition_parent_index
        if dpi is not None and len(dpi) > 0:
            dp_connected += 1
        else:
            dp_disconnected += 1
    print(f"  definition_parent_index 結線: "
          f"{dp_connected} 件 / 未結線: {dp_disconnected} 件")

    # =====================================================================
    # Phase 6: source_path 復元検証
    # =====================================================================
    print("\n[Phase 6] source_path 復元検証...")
    sp_has = 0
    sp_none = 0
    sp_examples: list[str] = []
    for _, stmts in restored:
        if stmts is None:
            continue
        sp = stmts.source_path
        if sp is not None:
            sp_has += 1
            if len(sp_examples) < 3:
                sp_examples.append(sp)
        else:
            sp_none += 1
    print(f"  source_path あり: {sp_has} 件 / なし: {sp_none} 件")
    if sp_examples:
        print(f"  例: {sp_examples}")

    del restored
    gc.collect()

    # =====================================================================
    # 統計サマリ
    # =====================================================================
    t_total = time.perf_counter() - t_start

    print("\n" + "=" * 70)
    print("統計サマリ")
    print("=" * 70)

    print(f"\n書類数:")
    print(f"  全書類:        {result.total_filings}")
    print(f"  XBRL有:        {result.xbrl_count}")
    print(f"  パース成功:    {result.xbrl_ok}")
    if result.errors:
        print(f"  パースエラー:  {result.errors}")

    print(f"\n処理時間:")
    print(f"  adump_to_parquet:  {t_dump:.1f}s (取得+パース+書き出し)")
    print(f"  import_parquet:    {t_import:.1f}s")
    print(f"  マッパー実行:     {t_mapper:.1f}s (extract+summary)")
    print(f"  合計:              {t_total:.1f}s")

    if result.xbrl_ok > 0:
        per_1k_dump = t_dump / result.xbrl_ok * 1000
        per_1k_import = t_import / result.total_filings * 1000
        print(f"\n1k件あたり処理時間:")
        print(f"  adump_to_parquet:  {per_1k_dump:.1f}s / 1k filings")
        print(f"  import_parquet:    {per_1k_import:.1f}s / 1k filings")

    print(f"\nメモリ (tracemalloc ピーク):")
    print(f"  adump_to_parquet:  {_fmt_mb(dump_peak)}")
    print(f"  import_parquet:    {_fmt_mb(import_peak)}")

    print(f"\nファイルサイズ:")
    print(f"  Parquet 合計:      {total_mb:.2f} MB")
    per_filing_kb = total_mb * 1024 / result.total_filings if result.total_filings > 0 else 0
    per_xbrl_kb = total_mb * 1024 / result.xbrl_ok if result.xbrl_ok > 0 else 0
    print(f"  1件あたり:         {per_filing_kb:.1f} KB (全書類)")
    print(f"  1件あたり:         {per_xbrl_kb:.1f} KB (XBRL有のみ)")

    if tb_ratio["total"] > 0:
        print(f"\nTextBlock 分離効果 (見込み):")
        print(f"  分離対象行数:      {tb_ratio['text_block']:,} / {tb_ratio['total']:,}")
        if total_text_b > 0:
            print(f"  分離対象テキスト:  {tb_b / 1024 / 1024:.2f} MB "
                  f"({tb_b / total_text_b * 100:.1f}% of value_text)")

    print(f"\nマッパー復元:")
    print(f"  extract_values:    "
          f"成功{mapper_result['extract_ok']} / 失敗{mapper_result['extract_fail']}")
    print(f"  build_summary:     "
          f"成功{mapper_result['summary_ok']} / 失敗{mapper_result['summary_fail']}")
    print(f"  def_parents 結線:  {dp_connected} / {dp_connected + dp_disconnected}")
    print(f"  source_path:       {sp_has} / {sp_has + sp_none}")

    await edinet.aclose()

    # =====================================================================
    # レポート保存
    # =====================================================================
    report_path = OUTPUT_DIR / "dump_stress_test_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("adump_to_parquet ストレステスト結果\n")
        f.write(f"日付: {TARGET_DATE}\n")
        f.write(f"concurrency: {CONCURRENCY}\n\n")
        f.write(f"書類数: 全{result.total_filings}, XBRL有{result.xbrl_count}, "
                f"パース成功{result.xbrl_ok}, エラー{result.errors}\n\n")
        f.write("処理時間:\n")
        f.write(f"  adump_to_parquet:  {t_dump:.1f}s\n")
        f.write(f"  import_parquet:    {t_import:.1f}s\n")
        f.write(f"  マッパー実行:     {t_mapper:.1f}s\n")
        f.write(f"  合計:              {t_total:.1f}s\n")
        if result.xbrl_ok > 0:
            f.write(f"  1kあたり: dump{per_1k_dump:.1f}s "
                    f"import{per_1k_import:.1f}s\n")
        f.write(f"\nメモリ (tracemalloc ピーク):\n")
        f.write(f"  adump_to_parquet:  {_fmt_mb(dump_peak)}\n")
        f.write(f"  import_parquet:    {_fmt_mb(import_peak)}\n")
        f.write(f"\nファイルサイズ:\n")
        f.write(f"  Parquet 合計:      {total_mb:.2f} MB\n")
        for name, size_mb in sorted(sizes.items()):
            if name != "__total__":
                f.write(f"    {name}: {size_mb:.2f} MB\n")
        f.write(f"  1件あたり: {per_filing_kb:.1f} KB (全), {per_xbrl_kb:.1f} KB (XBRL)\n")
        f.write(f"\nTextBlock 分析:\n")
        f.write(f"  行数: {tb_ratio['text_block']:,} / {tb_ratio['total']:,}\n")
        f.write(f"  テキストバイト: TB={tb_b / 1024 / 1024:.2f} MB, "
                f"その他={other_b / 1024 / 1024:.2f} MB\n")
        f.write(f"\nマッパー復元:\n")
        f.write(f"  extract_values: 成功{mapper_result['extract_ok']} "
                f"失敗{mapper_result['extract_fail']}\n")
        for k, cnt in hit_counts.items():
            f.write(f"    {k}: {cnt} 件ヒット\n")
        f.write(f"  build_summary: 成功{mapper_result['summary_ok']} "
                f"失敗{mapper_result['summary_fail']}\n")
        f.write(f"  def_parents: ファイル{'有' if dp_info['exists'] else '無'}, "
                f"行数{dp_info['rows']}, "
                f"結線{dp_connected}/{dp_connected + dp_disconnected}\n")
        f.write(f"  source_path: {sp_has}/{sp_has + sp_none}\n")
        if mapper_result["extract_errors"]:
            f.write(f"\nextract_values エラー例:\n")
            for err in mapper_result["extract_errors"]:
                f.write(f"  {err}\n")
    print(f"\nレポート保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())

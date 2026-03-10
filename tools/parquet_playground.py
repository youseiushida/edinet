#!/usr/bin/env python3
"""Parquet プレイグラウンド — 出力済み Parquet を読み込んで色々試すコード例。

使い方:
    uv run python tools/parquet_playground.py

前提: parquet/ ディレクトリに dump_stress_*.parquet が存在すること。
      (tools/parquet_dump_stress_test.py で生成)

依存: pyarrow (必須), pandas (任意), duckdb (任意), polars (任意)
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── パス設定 ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PARQUET_DIR = ROOT / "parquet"
PREFIX = "dump_stress_"


def parquet_path(name: str) -> Path:
    """テーブル名からファイルパスを返す。"""
    return PARQUET_DIR / f"{PREFIX}{name}.parquet"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. PyArrow だけで読む（最軽量・常に使える）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def demo_pyarrow() -> None:
    """PyArrow でメタデータ確認・カラム選択読み込み。"""
    import pyarrow.parquet as pq

    print("=" * 70)
    print("1. PyArrow — メタデータ & カラム選択")
    print("=" * 70)

    # スキーマ確認
    meta = pq.read_metadata(parquet_path("line_items"))
    print(f"\nline_items: {meta.num_rows:,} 行, {meta.num_columns} 列")
    print(f"  row_groups: {meta.num_row_groups}")
    print(f"  ファイルサイズ: {parquet_path('line_items').stat().st_size / 1e6:.1f} MB")

    schema = pq.read_schema(parquet_path("line_items"))
    print("\nスキーマ:")
    for field in schema:
        print(f"  {field.name}: {field.type}")

    # カラム選択読み込み（メモリ節約）
    table = pq.read_table(
        parquet_path("line_items"),
        columns=["doc_id", "local_name", "value_numeric", "label_ja_text"],
    )
    print(f"\n選択カラム読み込み: {table.num_rows:,} 行 × {table.num_columns} 列")

    # フィルタ付き読み込み（行の絞り込み）
    table_filtered = pq.read_table(
        parquet_path("line_items"),
        columns=["doc_id", "local_name", "value_numeric", "label_ja_text"],
        filters=[("local_name", "=", "NetSales")],
    )
    print(f"NetSales のみ: {table_filtered.num_rows:,} 行")
    for row in table_filtered.to_pylist()[:3]:
        print(f"  {row['doc_id']}: {row['label_ja_text']} = {row['value_numeric']}")

    # 全テーブルのサイズ一覧
    print("\n全テーブル:")
    for name in [
        "filings",
        "line_items",
        "text_blocks",
        "contexts",
        "dei",
        "calc_edges",
        "def_parents",
    ]:
        p = parquet_path(name)
        if p.exists():
            m = pq.read_metadata(p)
            sz = p.stat().st_size / 1e6
            print(f"  {name:20s}: {m.num_rows:>10,} 行  {sz:>8.2f} MB")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. pandas で読む
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def demo_pandas() -> None:
    """pandas DataFrame として操作する例。"""
    try:
        import pandas as pd
    except ImportError:
        print("\n[SKIP] pandas がインストールされていません (uv pip install pandas)")
        return

    print("\n" + "=" * 70)
    print("2. pandas — DataFrame 操作")
    print("=" * 70)

    # line_items を読む（数値カラムだけ）
    df = pd.read_parquet(
        parquet_path("line_items"),
        columns=[
            "doc_id", "local_name", "label_ja_text",
            "value_numeric", "value_type", "context_id",
            "period_start", "period_end", "period_instant",
        ],
    )
    print(f"\nline_items: {len(df):,} 行")

    # 数値 Fact だけ抽出
    numeric = df[df["value_type"] == "decimal"].copy()
    numeric["value"] = pd.to_numeric(numeric["value_numeric"], errors="coerce")
    print(f"数値 Fact: {len(numeric):,} 行")

    # 売上高ランキング（当期）
    sales = numeric[numeric["local_name"] == "NetSales"].copy()
    if not sales.empty:
        sales = sales.sort_values("value", ascending=False)
        print("\n売上高 Top 10:")
        for _, row in sales.head(10).iterrows():
            v = row["value"]
            label = f"{v / 1e6:>12,.0f} 百万円" if pd.notna(v) else "N/A"
            print(f"  {row['doc_id']}: {label}  ({row['label_ja_text']})")

    # DEI: 会計基準の分布
    dei = pd.read_parquet(parquet_path("dei"))
    if "accounting_standards" in dei.columns:
        print("\n会計基準の分布:")
        print(dei["accounting_standards"].value_counts().to_string())

    # filings と DEI を JOIN して企業名＋売上を表示
    filings = pd.read_parquet(
        parquet_path("filings"),
        columns=["doc_id", "filer_name", "edinet_code", "sec_code"],
    )
    if not sales.empty:
        merged = sales.merge(filings, on="doc_id", how="left")
        print("\n企業名付き売上高 Top 10:")
        for _, row in merged.sort_values("value", ascending=False).head(10).iterrows():
            v = row["value"]
            label = f"{v / 1e6:>12,.0f} 百万円" if pd.notna(v) else "N/A"
            print(f"  {row.get('filer_name', 'N/A'):30s} {label}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. DuckDB で SQL クエリ（超高速・最もおすすめ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def demo_duckdb() -> None:
    """DuckDB で Parquet を直接 SQL クエリする例。"""
    try:
        import duckdb
    except ImportError:
        print("\n[SKIP] duckdb がインストールされていません (uv pip install duckdb)")
        return

    print("\n" + "=" * 70)
    print("3. DuckDB — SQL クエリ（ファイルを直接読む）")
    print("=" * 70)

    con = duckdb.connect()

    # Parquet ファイルパスを変数にバインド
    li = str(parquet_path("line_items"))
    fi = str(parquet_path("filings"))
    dei = str(parquet_path("dei"))

    # テーブル概要
    result = con.execute(
        f"SELECT count(*) as rows FROM read_parquet('{li}')"
    ).fetchone()
    print(f"\nline_items: {result[0]:,} 行")

    # 売上高ランキング（JOIN で企業名付き）
    print("\n売上高 Top 10 (SQL JOIN):")
    rows = con.execute(f"""
        SELECT
            f.filer_name,
            f.edinet_code,
            CAST(l.value_numeric AS DOUBLE) / 1e6 AS sales_million,
            l.context_id
        FROM read_parquet('{li}') l
        JOIN read_parquet('{fi}') f ON l.doc_id = f.doc_id
        WHERE l.local_name = 'NetSales'
          AND l.value_type = 'decimal'
          AND l.value_numeric IS NOT NULL
        ORDER BY CAST(l.value_numeric AS DOUBLE) DESC
        LIMIT 10
    """).fetchall()
    for row in rows:
        print(f"  {row[0]:30s}  {row[2]:>12,.0f} 百万円  ({row[3]})")

    # 会計基準別の書類数
    print("\n会計基準別の書類数:")
    rows = con.execute(f"""
        SELECT
            accounting_standards,
            COUNT(*) as cnt
        FROM read_parquet('{dei}')
        GROUP BY accounting_standards
        ORDER BY cnt DESC
    """).fetchall()
    for row in rows:
        print(f"  {str(row[0]):20s}: {row[1]:>5} 件")

    # 科目の出現頻度 Top 20
    print("\n科目出現頻度 Top 20:")
    rows = con.execute(f"""
        SELECT
            local_name,
            label_ja_text,
            COUNT(*) as cnt
        FROM read_parquet('{li}')
        WHERE value_type = 'decimal'
        GROUP BY local_name, label_ja_text
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()
    for row in rows:
        print(f"  {row[1]:40s}  {row[2]:>6} 件  ({row[0]})")

    # 計算リンクベースの親子関係を探索
    ce = str(parquet_path("calc_edges"))
    if parquet_path("calc_edges").exists():
        print("\n計算リンクベース — NetSales の構成要素:")
        rows = con.execute(f"""
            SELECT DISTINCT child, weight
            FROM read_parquet('{ce}')
            WHERE parent = 'NetSales'
            ORDER BY child
        """).fetchall()
        for row in rows:
            sign = "+" if row[1] > 0 else "-"
            print(f"  {sign} {row[0]}")

    con.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Polars で読む（pandas 代替、高速）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def demo_polars() -> None:
    """Polars LazyFrame で操作する例。"""
    try:
        import polars as pl
    except ImportError:
        print("\n[SKIP] polars がインストールされていません (uv pip install polars)")
        return

    print("\n" + "=" * 70)
    print("4. Polars — LazyFrame（遅延評価・高速）")
    print("=" * 70)

    # LazyFrame として読む（実際の読み込みは collect() 時）
    lf = pl.scan_parquet(parquet_path("line_items"))

    # 数値 Fact の売上高ランキング
    sales = (
        lf.filter(
            (pl.col("local_name") == "NetSales")
            & (pl.col("value_type") == "decimal")
        )
        .with_columns(pl.col("value_numeric").cast(pl.Float64).alias("value"))
        .sort("value", descending=True)
        .head(10)
        .select("doc_id", "label_ja_text", "value", "context_id")
        .collect()
    )
    print("\n売上高 Top 10:")
    print(sales)

    # 書類ごとの Fact 数
    fact_counts = (
        lf.group_by("doc_id")
        .agg(pl.len().alias("fact_count"))
        .sort("fact_count", descending=True)
        .head(10)
        .collect()
    )
    print("\nFact 数 Top 10:")
    print(fact_counts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. edinet ライブラリで復元して操作
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def demo_edinet_restore() -> None:
    """edinet.extension.import_parquet() でドメインオブジェクトに復元。"""
    print("\n" + "=" * 70)
    print("5. edinet ライブラリ — Statements 復元 & extract_values()")
    print("=" * 70)

    from edinet.extension import import_parquet
    from edinet.financial.extract import extract_values

    data = import_parquet(PARQUET_DIR, prefix=PREFIX)

    # 最初の5件の概要
    count = 0
    for filing, stmts in data:
        if stmts is None:
            continue
        if count >= 5:
            break

        vals = extract_values(stmts)

        # 基本情報
        std = stmts.detected_standard
        std_label = std.standard.value if std and std.standard else "?"
        src = stmts.source_path or "N/A"

        print(f"\n{filing.doc_id} ({filing.filer_name})")
        print(f"  基準: {std_label}, source: {src}")
        print(f"  科目数: {len(stmts)}, def_parents: "
              f"{'あり' if stmts.definition_parent_index else 'なし'}")

        # extract_values の結果
        for key in ["revenue", "operating_income", "net_income",
                     "total_assets", "net_assets"]:
            v = getattr(vals, key, None)
            if v is not None:
                print(f"  {key:25s}: {v / 1e6:>12,.0f} 百万円")
            else:
                print(f"  {key:25s}: N/A")

        count += 1

    print("\n... (残り省略)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. doc_ids / concepts フィルタで選択読み込み
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def demo_filtered_import() -> None:
    """doc_ids / concepts フィルタの使用例。"""
    print("\n" + "=" * 70)
    print("6. edinet ライブラリ — フィルタ付きインポート")
    print("=" * 70)

    import pyarrow.parquet as pq

    from edinet.extension import import_parquet

    # filings から先頭3件の doc_id を取得
    fi_table = pq.read_table(parquet_path("filings"), columns=["doc_id"])
    all_doc_ids = fi_table.column("doc_id").to_pylist()
    target_ids = all_doc_ids[:3]
    print(f"\n全 {len(all_doc_ids)} 件から {len(target_ids)} 件を選択読み込み")

    # doc_ids フィルタ: 指定した書類だけ復元
    data = import_parquet(PARQUET_DIR, prefix=PREFIX, doc_ids=target_ids)
    print(f"  doc_ids フィルタ: {len(data)} 件復元")
    for filing, stmts in data:
        n = len(stmts) if stmts else 0
        print(f"    {filing.doc_id}: {filing.filer_name} ({n} items)")

    # concepts フィルタ: 売上高 + 営業利益だけ復元
    concepts = ["NetSales", "OperatingIncome"]
    data2 = import_parquet(
        PARQUET_DIR, prefix=PREFIX,
        doc_ids=target_ids, concepts=concepts,
    )
    print(f"\n  concepts フィルタ ({concepts}):")
    for filing, stmts in data2:
        if stmts is None:
            continue
        for item in stmts:
            print(f"    {filing.doc_id}: {item.label_ja.text} = {item.value}")

    # concepts フィルタ（全件）: 特定科目を全書類から抽出
    data3 = import_parquet(PARQUET_DIR, prefix=PREFIX, concepts=["NetSales"])
    hit = sum(1 for _, s in data3 if s is not None and len(s) > 0)
    print(f"\n  NetSales 全件抽出: {hit} 件ヒット / {len(data3)} 件")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. iter_parquet() でバッチ処理（大規模データ向け）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def demo_iter_parquet() -> None:
    """iter_parquet() でメモリ効率的にバッチ処理する例。"""
    print("\n" + "=" * 70)
    print("7. iter_parquet() — バッチ処理（大規模データ向け）")
    print("=" * 70)

    from edinet.extension import iter_parquet
    from edinet.financial.extract import extract_values

    # 全件イテレーション（batch_size=50 で処理）
    total = 0
    xbrl_count = 0
    revenue_hits = 0

    for _, stmts in iter_parquet(
        PARQUET_DIR, prefix=PREFIX, batch_size=50,
    ):
        total += 1
        if stmts is None:
            continue
        xbrl_count += 1

        result = extract_values(stmts, ["revenue"])
        if result.get("revenue") is not None:
            revenue_hits += 1

    print(f"\n  全件イテレーション: {total} 件 (XBRL: {xbrl_count})")
    print(f"  revenue ヒット: {revenue_hits} 件")

    # concepts フィルタ付きイテレーション（軽量）
    concepts = ["NetSales", "OperatingIncome", "TotalAssets"]
    total2 = 0
    for _, stmts in iter_parquet(
        PARQUET_DIR, prefix=PREFIX,
        concepts=concepts, batch_size=200,
    ):
        if stmts is not None:
            total2 += 1

    print(f"\n  concepts フィルタ ({len(concepts)} 科目): {total2} 件に Fact あり")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main() -> None:
    """全デモを実行する。"""
    if not PARQUET_DIR.exists():
        print(f"エラー: {PARQUET_DIR} が見つかりません。")
        print("先に tools/parquet_dump_stress_test.py を実行してください。")
        sys.exit(1)

    if not parquet_path("line_items").exists():
        print(f"エラー: {parquet_path('line_items')} が見つかりません。")
        sys.exit(1)

    demo_pyarrow()
    demo_pandas()
    demo_duckdb()
    demo_polars()
    demo_edinet_restore()
    demo_filtered_import()
    demo_iter_parquet()

    print("\n" + "=" * 70)
    print("完了！")
    print("=" * 70)


if __name__ == "__main__":
    main()

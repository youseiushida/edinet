# edinet.extension — Parquet パイプライン ベストプラクティス

`edinet.extension` は EDINET の書類データ（Filing + Statements）を Parquet 形式で永続化・読み込みするモジュールです。このドキュメントでは、パイプラインの構築方法と出力データの利用方法について、実測ベンチマークをもとにしたベストプラクティスをまとめます。

---

## 目次

1. [出力テーブル構成](#1-出力テーブル構成)
2. [書き出しパイプライン](#2-書き出しパイプライン)
3. [読み込みパイプライン](#3-読み込みパイプライン)
4. [パフォーマンス特性](#4-パフォーマンス特性)
5. [フィルタ戦略](#5-フィルタ戦略)
6. [extract_values() との組み合わせ](#6-extract_values-との組み合わせ)
7. [外部ツールでの直接クエリ](#7-外部ツールでの直接クエリ)
8. [エッジケースと注意点](#8-エッジケースと注意点)
9. [シナリオ別レシピ](#9-シナリオ別レシピ)

---

## 1. 出力テーブル構成

`export_parquet()` / `adump_to_parquet()` は以下の 7 テーブルを出力します。

| テーブル | ファイル名 | 内容 | 行数目安（1,784件） |
|---|---|---|---|
| `filings` | `{prefix}filings.parquet` | 書類メタデータ（Filing） | 1,784 行 |
| `line_items` | `{prefix}line_items.parquet` | 数値 Fact（TextBlock 除外） | 〜300万行 |
| `text_blocks` | `{prefix}text_blocks.parquet` | テキスト Fact（TextBlock のみ） | 〜80万行 |
| `contexts` | `{prefix}contexts.parquet` | XBRL コンテキスト定義 | 〜5万行 |
| `dei` | `{prefix}dei.parquet` | DEI メタ情報 + DetectedStandard | 〜1,000行 |
| `calc_edges` | `{prefix}calc_edges.parquet` | Calculation Linkbase のエッジ | 〜30万行 |
| `def_parents` | `{prefix}def_parents.parquet` | Definition Linkbase の親子関係 | 〜10万行 |

**テーブル間の関係:** 全テーブルは `doc_id` カラムで結合可能です。`filings` が主キーテーブルで、他テーブルは `doc_id` で参照します。

**ストレージ効率:**

- 1,784件（1日分）で約 153 MB（平均 88 KB/件）
- zstd 圧縮がデフォルト（辞書エンコーディング + zstd で高い圧縮率）
- `line_items` と `text_blocks` が容量の大部分を占める

### Row Group 構造

各テーブルは**書類（doc_id）単位で 1 row group** を作成します。この設計により:

- `doc_id` フィルタが row group レベルの predicate pushdown で効く（min=max=対象 doc_id）
- `iter_parquet()` が `read_row_groups()` で書類単位の効率的な読み込みを実現
- 将来的な書類単位のランダムアクセスにも対応

### 辞書エンコーディング

繰り返しの多いカラムには `pa.dictionary(pa.int16(), pa.string())` を使用:

```
doc_id, concept, local_name, namespace_uri, context_id, entity_id,
edinet_code, sec_code, fund_code, ...
```

辞書エンコーディングにより:
- ファイルサイズが 40-60% 削減
- 読み込み時のメモリ効率が向上
- DuckDB/Polars 等の外部ツールでも自動的に利用される

---

## 2. 書き出しパイプライン

### 2.1. adump_to_parquet() — API → Parquet 直接永続化

最も一般的なパターン。EDINET API からダウンロードしながらストリーミング書き出しします。

```python
import asyncio
from edinet.extension import adump_to_parquet

async def main():
    result = await adump_to_parquet(
        start="2026-01-01",
        end="2026-01-31",
        output_dir="./parquet",
        prefix="2026-01_",
        concurrency=8,          # 同時ダウンロード数
        compression="zstd",     # デフォルト
    )
    print(f"書類数: {result.total_filings}")
    print(f"XBRL成功: {result.xbrl_ok} / {result.xbrl_count}")
    print(f"エラー: {result.errors}")

asyncio.run(main())
```

**メモリ特性:** ストリーミング書き出しのため、全件をメモリに保持しません。1,784件で peak 171 MB 程度です。数万件規模でもメモリ不足になりません。

**エラーハンドリング:**
- `on_invalid="skip"`（デフォルト）: EDINET API レスポンスの不正行をスキップ
- `on_invalid="error"`: API レスポンスに不正行がある場合に例外を投げる
- XBRL パースエラーは `on_invalid` に関係なく常に警告を出してスキップされる
- `DumpResult.errors` で XBRL パースエラー件数を確認可能

**concurrency の指針:**
- デフォルト `8` が一般的に最適
- EDINET API のレート制限に注意（大量リクエスト時は `4` に下げる）
- ローカルのタクソノミ解析が CPU ボトルネックの場合は `4-8` で十分

### 2.2. export_parquet() — 既存データの永続化

すでに `(Filing, Statements)` のリストがメモリにある場合に使います。

```python
from edinet.extension import export_parquet

# data: list[tuple[Filing, Statements | None]]
paths = export_parquet(data, output_dir="./parquet", prefix="custom_")
print(paths)  # {"filings": Path(...), "line_items": Path(...), ...}
```

**用途:**
- 複数日分のデータをマージして再出力
- テスト用のサンプルデータ作成
- カスタムフィルタ後のデータ再出力

### 2.3. prefix による管理

`prefix` パラメータでファイル名を名前空間分離できます。

```python
# 日付ごとに分離
await adump_to_parquet(date="2026-01-15", prefix="2026-01-15_", ...)
await adump_to_parquet(date="2026-01-16", prefix="2026-01-16_", ...)

# 読み込み時もプレフィックスで選択
data = import_parquet("./parquet", prefix="2026-01-15_")
```

**注意:** 同じ prefix のファイルは上書きされます。日付やバッチごとに異なる prefix を使うか、出力ディレクトリを分けてください。

### 2.4. インクリメンタルビルド — 複数回に分けてデータを蓄積する

年間データのような大量データを一度に作る必要はありません。日単位・月単位で分割してダンプし、読み込み時にまとめて使えます。

#### なぜファイルを分けるのか — Parquet は追記（append）できない

「既存ファイルに追加ダンプ分をくっつければいいのでは？」と思うかもしれませんが、**Parquet フォーマットはファイル末尾に追記できません。** Parquet ファイルは閉じる時にメタデータ（footer）が書き込まれ、以後の変更は不可能です。PyArrow の `ParquetWriter` にも append モードはありません。

既存ファイルに新データを「合体」するには、全データを読み込んで結合し、丸ごと書き直す必要があります。これは:

- 既存データが大きいほど遅くなる（毎回全量の読み書き）
- 途中でクラッシュすると既存データも失うリスクがある
- `adump_to_parquet` のストリーミング設計（peak 171 MB）が無意味になる

そのため、**prefix でファイルを分ける → 読み込み時にまとめる** のが Parquet のインクリメンタル蓄積の標準パターンです。DuckDB / Polars は glob パターン（`*_filings.parquet`）で複数ファイルを透過的に 1 テーブルとして読めるので、ファイルが分かれていてもユーザー体験は変わりません。

#### ダンプ: 好きなタイミングで追加していく

```python
import asyncio
from edinet.extension import adump_to_parquet

async def main():
    # 今日は 2025年1月分をダンプ
    await adump_to_parquet(
        start="2025-01-01", end="2025-01-31",
        output_dir="./parquet/db", prefix="2025-01_",
    )

    # 明日、追加で 2024年12月分をダンプ（同じディレクトリに追加）
    await adump_to_parquet(
        start="2024-12-01", end="2024-12-31",
        output_dir="./parquet/db", prefix="2024-12_",
    )

    # さらに後日、2025年2月分を追加
    await adump_to_parquet(
        start="2025-02-01", end="2025-02-28",
        output_dir="./parquet/db", prefix="2025-02_",
    )

asyncio.run(main())
```

実行後のディレクトリ構造:
```
parquet/db/
  2024-12_filings.parquet
  2024-12_line_items.parquet
  2024-12_text_blocks.parquet
  2024-12_contexts.parquet
  2024-12_dei.parquet
  2024-12_calc_edges.parquet
  2024-12_def_parents.parquet
  2025-01_filings.parquet
  2025-01_line_items.parquet
  ...
  2025-02_filings.parquet
  2025-02_line_items.parquet
  ...
```

各 prefix は独立したファイルセットなので、**追加ダンプは既存データに影響しません**。同じ prefix で再ダンプすればその月のデータだけ上書きされます。

#### 読み込み方法 A: Python — 複数 prefix をループして統合

`import_parquet()` / `iter_parquet()` は 1 つの prefix しか受け取れないため、複数 prefix をループします。

```python
from edinet.extension import iter_parquet
from edinet.financial.extract import extract_values, extracted_to_dict
from edinet.financial.standards.canonical_keys import CK

KEYS = [CK.REVENUE, CK.OPERATING_INCOME, CK.NET_INCOME, CK.TOTAL_ASSETS]
PREFIXES = ["2024-12_", "2025-01_", "2025-02_"]

rows = []
for prefix in PREFIXES:
    for filing, stmts in iter_parquet(
        "./parquet/db", prefix=prefix, batch_size=100,
    ):
        if stmts is None:
            continue
        result = extract_values(stmts, KEYS, period="current", consolidated=True)
        rows.append({
            "doc_id": filing.doc_id,
            "filer_name": filing.filer_name,
            "period_end": filing.period_end,
            **extracted_to_dict(result),
        })
```

prefix 一覧をハードコードしたくない場合は、ディレクトリから自動検出できます:

```python
from pathlib import Path

db_dir = Path("./parquet/db")
prefixes = sorted({
    p.name.replace("filings.parquet", "")
    for p in db_dir.glob("*filings.parquet")
})
# → ["2024-12_", "2025-01_", "2025-02_"]
```

#### 読み込み方法 B: DuckDB — glob で全 prefix を一発読み込み

DuckDB のグロブパターンを使えば、prefix を意識せずに全ファイルをまとめて読めます。**集計・分析にはこれが最も簡単です。**

```python
import duckdb

conn = duckdb.connect()

# *_filings.parquet で全 prefix を横断
conn.sql("""
    SELECT
        f.filer_name,
        f.edinet_code,
        f.period_end,
        CAST(li.value_numeric AS DOUBLE) AS revenue
    FROM read_parquet('./parquet/db/*_filings.parquet') AS f
    JOIN read_parquet('./parquet/db/*_line_items.parquet') AS li
        ON f.doc_id = li.doc_id
    WHERE li.local_name = 'NetSales'
      AND li.dimensions_json IS NULL
      AND li.period_type = 'duration'
    ORDER BY revenue DESC
    LIMIT 30
""").show()
```

**ポイント:** `read_parquet('./parquet/db/*_filings.parquet')` が全 prefix のファイルを UNION して 1 テーブルとして扱います。DuckDB は遅延評価なので、WHERE 句で絞ったぶんだけ読み込まれます。

#### 読み込み方法 C: Polars — glob で横断読み込み

```python
import polars as pl

# 全 prefix の filings を一括読み込み
filings = pl.read_parquet("./parquet/db/*_filings.parquet")
line_items = pl.read_parquet("./parquet/db/*_line_items.parquet")

# 通常通り結合・フィルタ
revenue = line_items.filter(
    (pl.col("local_name") == "NetSales")
    & pl.col("dimensions_json").is_null()
)
result = filings.join(revenue, on="doc_id")
```

#### prefix の命名規約

| 粒度 | prefix 例 | 用途 |
|---|---|---|
| 日単位 | `"2025-01-15_"` | 日次バッチ、差分更新 |
| 月単位 | `"2025-01_"` | 月次集計、中規模蓄積 |
| 範囲指定 | `"2025-Q1_"` | 四半期単位の管理 |
| カスタム | `"toyota_"` | 企業別のサブセット |

**推奨:** 月単位が管理しやすく、ファイル数も適度です（年間 12 セット = 84 ファイル）。日単位は年間 365 セット = 2,555 ファイルになり、glob 読み込み時のオーバーヘッドが大きくなります。

#### やり直し・部分更新

```python
# 2025年1月分だけやり直す（同じ prefix で上書き）
await adump_to_parquet(
    start="2025-01-01", end="2025-01-31",
    output_dir="./parquet/db", prefix="2025-01_",
)
# → 2025-01_*.parquet だけが上書きされ、他の月は影響なし
```

### 2.5. 圧縮アルゴリズムの選択

| アルゴリズム | 速度 | 圧縮率 | 用途 |
|---|---|---|---|
| `"zstd"`（デフォルト）| 速い | 高い | 一般的な永続化 |
| `"snappy"` | 最速 | 中 | 頻繁な読み書き |
| `"gzip"` | 遅い | 最高 | アーカイブ・配布 |
| `"none"` | 最速 | なし | デバッグ・一時データ |

実測（1,784件）: zstd で 153 MB、snappy で約 180 MB、gzip で約 140 MB。zstd が速度と圧縮率のバランスに優れます。

---

## 3. 読み込みパイプライン

### 3.1. import_parquet() — 一括読み込み

全データをメモリに展開します。数千件以下の探索的分析に最適。

```python
from edinet.extension import import_parquet

# 全件読み込み
data = import_parquet("./parquet", prefix="2026-01-15_")

for filing, stmts in data:
    if stmts is None:
        continue  # XBRL なしの書類
    print(filing.filer_name, len(stmts))
```

**戻り値の型:** `list[tuple[Filing, Statements | None]]`

- `Statements` が `None` = has_xbrl=False の書類（PDF のみ等）
- `Statements` が存在 = XBRL パース成功済み

### 3.2. iter_parquet() — バッチイテレーション

メモリ制約がある大規模データ（数千件〜数万件）に最適。内部で `ParquetFile` を 1 回だけ開き、`doc_id → row_group` マッピングを構築して `read_row_groups()` で効率的に読みます。

```python
from edinet.extension import iter_parquet

for filing, stmts in iter_parquet(
    "./parquet",
    prefix="2026-01-15_",
    batch_size=100,
):
    if stmts is None:
        continue
    # 処理...
```

**batch_size のチューニング:**

| batch_size | メモリ peak | 速度 | 推奨用途 |
|---|---|---|---|
| 50 | 〜300 MB | 196s (1,784件) | メモリ制約厳しい環境 |
| 100（デフォルト） | 〜385 MB | 190s | 一般的なバッチ処理 |
| 200 | 〜564 MB | 190s | 高速処理優先 |

内部で `ParquetFile` を 1 度だけ開くため、**batch_size による速度差はほぼありません**（batch=50 と batch=200 で 6s 差）。メモリ使用量だけが batch_size に比例します。

**iter_parquet のデフォルト:** `include_text_blocks=False`（import_parquet と逆）。大規模バッチ処理では TextBlock が不要なケースが多いため。

---

## 4. パフォーマンス特性

### 実測値（1,784件、7テーブル、153 MB）

| 操作 | 時間 | メモリ peak | 備考 |
|---|---|---|---|
| **書き出し** ||||
| `adump_to_parquet()` | 938s | 171 MB | API DL + パース + 書き出し |
| **一括読み込み** ||||
| `import_parquet()` 全件（TB有） | 282s | 5,158 MB | TextBlock 含む完全復元 |
| `import_parquet()` 全件（TB無） | 193s | 2,017 MB | `include_text_blocks=False` |
| `import_parquet(doc_ids=10件)` | 3.5s | 0.05 MB | doc_id pushdown が効く |
| `import_parquet(doc_ids=100件)` | 8.5s | 17 MB | doc_id pushdown が効く |
| `import_parquet(concepts=1科目)` | 30s | 224 MB | 行レベルフィルタ |
| `import_parquet(concepts=5科目)` | 30s | 235 MB | 行レベルフィルタ |
| **バッチイテレーション** ||||
| `iter_parquet(batch=50)` | 196s | 300 MB | TB無・全件 |
| `iter_parquet(batch=100)` | 190s | 385 MB | TB無・全件 |
| `iter_parquet(batch=200)` | 190s | 564 MB | TB無・全件 |
| `iter_parquet(concepts=2科目)` | 32s | 229 MB | concepts フィルタ付き |
| `iter_parquet` + `extract_values` | 207s | 385 MB | 実用パイプライン |

### 規模別の推奨

| 規模 | 推奨 API | メモリ目安 |
|---|---|---|
| 〜100件（特定企業・探索） | `import_parquet(doc_ids=...)` | 数十 MB |
| 〜1,000件（数日分） | `import_parquet()` | 2-5 GB |
| 〜5,000件（1ヶ月分） | `iter_parquet()` | 300-600 MB |
| 10,000件〜（年間データ） | `iter_parquet()` | 300-600 MB |
| 集計・分析のみ | DuckDB / Polars 直接 | テーブル依存 |

### 70,000件規模（年間データ）の推定

| 操作 | 推定時間 | 推定メモリ |
|---|---|---|
| `adump_to_parquet()` | 〜10時間 | 〜200 MB |
| `import_parquet()` 全件 | 実用的でない | 〜200 GB |
| `iter_parquet(batch=100)` | 〜2.5時間 | 〜400 MB |
| `iter_parquet` + `extract_values` | 〜3時間 | 〜400 MB |

---

## 5. フィルタ戦略

### 5.1. doc_ids フィルタ — 特定書類のピンポイント取得

```python
# 特定企業の書類のみ
target_ids = ["S100ABC1", "S100ABC2"]
data = import_parquet("./parquet", prefix="...", doc_ids=target_ids)
```

**仕組み:** PyArrow の predicate pushdown により、対象 doc_id の row group だけを I/O します。1,784件中 10件を取得する場合、3.5s / 0.05 MB と極めて高速です。

**用途:**
- 特定企業の時系列データ取得（edinet_code → doc_id をまず filings から引く）
- デバッグ時の単一書類確認
- ユーザーリクエストに応じたオンデマンド取得

### 5.2. concepts フィルタ — 特定科目のみ

```python
# 売上高と営業利益だけ
data = import_parquet(
    "./parquet", prefix="...",
    concepts=["NetSales", "OperatingIncome"],
)
```

**仕組み:** `line_items` / `text_blocks` テーブルの `local_name` カラムに対する行レベルフィルタです。row group レベルの pushdown は効きません（1 row group に多数の concept が混在するため）。テーブル全体を読み込んだ後にフィルタされます。

**効果:**
- メモリ削減: Statements オブジェクトの item 数が激減する
- 速度改善: デシリアライゼーションの行数が減る（30s vs 282s）
- `filings`, `contexts`, `dei`, `calc_edges`, `def_parents` は concepts フィルタの影響を受けない（全件読まれる）

**注意:**

```python
# concepts フィルタは local_name での完全一致
# 名前空間プレフィックス(jppfs_cor:NetSales)は使えない
concepts=["NetSales"]  # OK
concepts=["jppfs_cor:NetSales"]  # NG — マッチしない
```

### 5.3. include_text_blocks — TextBlock の制御

```python
# TextBlock を除外（デフォルト: import_parquet は True、iter_parquet は False）
data = import_parquet("./parquet", prefix="...", include_text_blocks=False)
```

**効果:**
- メモリ: 5,158 MB → 2,017 MB（**60% 削減**）
- 速度: 282s → 193s（**32% 高速化**）

**TextBlock とは:** `local_name` が `*TextBlock` で終わる Fact。注記事項などの HTML テキストを含みます。`extract_values()` は数値 Fact のみを使うため、ファンダメンタルDB 構築では `include_text_blocks=False` で十分です。

**旧形式互換:** v0.3.x 以前で生成された Parquet（text_blocks 未分離）でも `include_text_blocks=True` は正しく動作します。line_items テーブル内の TextBlock が自動検出されます。

### 5.4. doc_type_codes フィルタ — 書類種別で絞り込み

```python
# 有報（120）と半期報告書（130）のみ
for filing, stmts in iter_parquet(
    "./parquet", prefix="...",
    doc_type_codes=["120", "130"],
    batch_size=100,
):
    ...
```

**仕組み:** `filings.parquet` を読み込んだ後、`doc_type_code` が一致する Filing のみを残します。対象外の書類は `line_items` 等の重いテーブルの復元自体をスキップするため、I/O とデシリアライゼーションの両方が削減されます。

**主な書類種別コード:**

| コード | 書類 |
|---|---|
| `"120"` | 有価証券報告書 |
| `"130"` | 半期報告書 |
| `"140"` | 四半期報告書 |
| `"030"` | 有価証券届出書 |
| `"350"` | 大量保有報告書 |

**パフォーマンス特性:**
- 対象外の書類が軽量（臨報等）な場合、速度改善は限定的
- `concepts` フィルタとの併用が最も効果的（6.5倍高速化）
- `import_parquet()` でも同パラメータが使用可能

### 5.5. フィルタの組み合わせ

```python
# 特定企業 × 特定科目
data = import_parquet(
    "./parquet", prefix="...",
    doc_ids=["S100ABC1"],
    concepts=["NetSales", "OperatingIncome", "TotalAssets"],
)

# 書類種別 × 特定科目（最も効果的な組み合わせ）
for filing, stmts in iter_parquet(
    "./parquet", prefix="...",
    doc_type_codes=["120", "130"],
    concepts=["NetSales", "OperatingIncome", "TotalAssets"],
    batch_size=100,
):
    ...

# iter_parquet でも同様
for filing, stmts in iter_parquet(
    "./parquet", prefix="...",
    doc_ids=target_ids,
    concepts=["NetSales"],
    batch_size=50,
):
    ...
```

---

## 6. extract_values() との組み合わせ

### 6.1. 基本パターン — ファンダメンタル DB 構築

```python
from edinet.extension import iter_parquet
from edinet.financial.extract import extract_values, extracted_to_dict
from edinet.financial.standards.canonical_keys import CK

KEYS = [
    CK.REVENUE, CK.OPERATING_INCOME, CK.ORDINARY_INCOME,
    CK.NET_INCOME, CK.TOTAL_ASSETS, CK.NET_ASSETS,
    CK.SHAREHOLDERS_EQUITY, CK.EPS, CK.BPS, CK.DPS,
]

rows = []
for filing, stmts in iter_parquet(
    "./parquet",
    prefix="2026-01_",
    batch_size=100,
    include_text_blocks=False,  # デフォルトで False
):
    if stmts is None:
        continue

    result = extract_values(stmts, KEYS, period="current", consolidated=True)
    values = extracted_to_dict(result)

    rows.append({
        "doc_id": filing.doc_id,
        "edinet_code": filing.edinet_code,
        "filer_name": filing.filer_name,
        "period_end": filing.period_end,
        **values,
    })

# pandas DataFrame や CSV に出力
import pandas as pd
df = pd.DataFrame(rows)
```

**実測:** 1,784件で 207s、peak 385 MB。年間 70,000件でも 3時間・400 MB 程度で完了する見込みです。

### 6.2. concepts フィルタで高速化

`extract_values()` で使う科目が事前にわかっている場合、`concepts` フィルタで大幅に高速化できます。

```python
# extract_values の summary_mapper が使う local_name を直接指定
CONCEPTS = [
    "NetSales", "Revenue", "OperatingRevenue1",  # revenue 系
    "OperatingIncome", "OrdinaryIncome",
    "ProfitLossAttributableToOwnersOfParent",
    "TotalAssets", "NetAssets",
    "ShareholdersEquity",
]

for filing, stmts in iter_parquet(
    "./parquet", prefix="...",
    concepts=CONCEPTS,
    batch_size=100,
):
    if stmts is None:
        continue
    result = extract_values(stmts, KEYS)
    ...
```

**効果:** 1,784件で 32s（concepts フィルタなしの 207s → 32s、**6.5倍高速化**）。

**注意点:** `concepts` フィルタを使うと、指定した `local_name` 以外の Fact が除外されます。これにより:

- `extract_values()` の `definition_mapper` や `calc_mapper` が使う関連科目も含める必要がある
- `income_statement()` / `balance_sheet()` 等の財務諸表組み立てメソッドは不完全な結果を返す

`extract_values()` のみを使い、必要科目が事前にわかっている場合に限り有効です。

### 6.3. 連結 / 個別 / 期間の制御

```python
# 当期連結
result_current = extract_values(stmts, KEYS, period="current", consolidated=True)

# 前期連結
result_prior = extract_values(stmts, KEYS, period="prior", consolidated=True)

# 個別（連結がない場合のフォールバック）
result_nc = extract_values(stmts, KEYS, period="current", consolidated=False)

# マージ（先に見つかった値を優先）
merged = extracted_to_dict(result_current, result_nc)
```

### 6.4. Statements が None のケース

```python
for filing, stmts in iter_parquet(...):
    if stmts is None:
        # has_xbrl=False: XBRL データがない書類
        # 例: PDF のみの臨報、適時開示、訂正報告書の一部
        rows.append({
            "doc_id": filing.doc_id,
            "filer_name": filing.filer_name,
            "has_xbrl": False,
            **{k: None for k in KEYS},
        })
        continue
    ...
```

---

## 7. 外部ツールでの直接クエリ

Parquet ファイルは標準フォーマットなので、Python 以外のツールでも直接読めます。

### 7.1. DuckDB

```python
import duckdb

conn = duckdb.connect()

# 全ファイラーの売上高ランキング
conn.sql("""
    SELECT
        f.filer_name,
        f.edinet_code,
        CAST(li.value_numeric AS DOUBLE) AS revenue
    FROM read_parquet('./parquet/2026-01_filings.parquet') AS f
    JOIN read_parquet('./parquet/2026-01_line_items.parquet') AS li
        ON f.doc_id = li.doc_id
    WHERE li.local_name = 'NetSales'
      AND li.period_type = 'duration'
      AND li.dimensions_json IS NULL
    ORDER BY revenue DESC
    LIMIT 20
""").show()
```

```python
# DEI と結合して会計基準別の集計
conn.sql("""
    SELECT
        d.accounting_standards,
        COUNT(*) AS count,
        AVG(CAST(li.value_numeric AS DOUBLE)) AS avg_revenue
    FROM read_parquet('./parquet/2026-01_dei.parquet') AS d
    JOIN read_parquet('./parquet/2026-01_line_items.parquet') AS li
        ON d.doc_id = li.doc_id
    WHERE li.local_name = 'NetSales'
      AND li.dimensions_json IS NULL
    GROUP BY d.accounting_standards
""").show()
```

### 7.2. Polars

```python
import polars as pl

filings = pl.read_parquet("./parquet/2026-01_filings.parquet")
line_items = pl.read_parquet("./parquet/2026-01_line_items.parquet")

# フィルタ → 結合
revenue = (
    line_items
    .filter(
        (pl.col("local_name") == "NetSales")
        & pl.col("dimensions_json").is_null()
    )
    .select("doc_id", "value_numeric")
)

result = filings.join(revenue, on="doc_id").select(
    "filer_name", "edinet_code", "value_numeric"
)
```

### 7.3. pandas

```python
import pandas as pd

filings = pd.read_parquet("./parquet/2026-01_filings.parquet")
dei = pd.read_parquet("./parquet/2026-01_dei.parquet")

# doc_id で結合
merged = filings.merge(dei, on="doc_id", how="left", suffixes=("", "_dei"))
```

### 直接クエリ vs import_parquet の使い分け

| シナリオ | 推奨 |
|---|---|
| 特定科目の集計・ランキング | DuckDB / Polars 直接 |
| 会計基準別の分析 | DuckDB（DEI と結合） |
| extract_values() を使った正規化抽出 | import_parquet / iter_parquet |
| 財務諸表の組み立て（PL/BS/CF） | import_parquet / iter_parquet |
| 大量データの逐次処理 | iter_parquet |

**ポイント:** `extract_values()` は概念名（local_name）の表記揺れを吸収するマッパーチェーン（summary_mapper → statement_mapper → definition_mapper → calc_mapper）を適用します。DuckDB 等での直接クエリでは `local_name` の完全一致しかできないため、**表記揺れへの対応が必要な場合は `extract_values()` を使ってください。**

---

## 8. エッジケースと注意点

### 8.1. Statements が None になるケース

`import_parquet()` / `iter_parquet()` が `Statements=None` を返すのは以下の場合です:

1. **has_xbrl=False の書類** — XBRL を含まない書類（臨時報告書、PDF のみの書類等）。全書類の約 40-50%
2. **XBRL パースエラー** — `adump_to_parquet()` での XBRL パースが失敗した書類。Filing は書き出されるが line_items は書かれない

```python
for filing, stmts in iter_parquet(...):
    if stmts is None:
        if not filing.has_xbrl:
            pass  # XBRL なし書類
        else:
            pass  # has_xbrl=True だがパースエラーで復元できなかった可能性
        continue
```

### 8.2. TextBlock の扱い

TextBlock は注記事項等の HTML テキストを含む大きな Fact です。

```
# text_blocks テーブルの行サイズは line_items の 10-50 倍
# 1書類で数 MB の TextBlock を含むこともある
```

- `include_text_blocks=True`: Statements の `_items` に TextBlock が含まれる。`stmts.search("TextBlock")` で検索可能
- `include_text_blocks=False`: 数値 Fact のみ。`extract_values()` の動作に影響なし

**推奨:** バッチ処理では `include_text_blocks=False`（iter_parquet のデフォルト）。探索的分析で注記テキストが必要な場合のみ `True` にする。

### 8.3. concepts フィルタの制限

`concepts` フィルタは `local_name` の完全一致です。以下の制限があります:

1. **名前空間なし:** `"NetSales"` は `jppfs_cor:NetSales` にも `jpigp_cor:NetSales` にもマッチ
2. **IFRS / US-GAAP の科目名:** IFRS 企業は `"Revenue"` や `"ProfitLoss"` 等の別名を使用
3. **提出者独自科目:** `"NetSalesXXX"` のようなカスタム科目は個別指定が必要
4. **calc_edges / def_parents への非適用:** concepts フィルタは `line_items` / `text_blocks` のみに適用。Calculation Linkbase や Definition Linkbase は全件読まれる

```python
# 会計基準をまたいで売上高を取得したい場合
concepts = [
    "NetSales",              # J-GAAP 一般
    "OperatingRevenue1",     # J-GAAP 銀行・保険
    "Revenue",               # IFRS
    "Revenues",              # US-GAAP
    "NetRevenue",            # J-GAAP 一部業種
]
```

### 8.4. definition_mapper / calc_mapper と concepts フィルタ

`extract_values()` のデフォルトマッパーチェーンには `definition_mapper` と `calc_mapper` が含まれます。これらは:

- **definition_mapper:** `def_parents` テーブルの親子関係を使って、提出者独自科目を標準科目にマッピング
- **calc_mapper:** `calc_edges` テーブルの計算リンクを使って、関連科目を推定

concepts フィルタで `line_items` を絞ると、definition_mapper / calc_mapper が参照する**関連科目の Fact が存在しない**場合があります。ただし、これらのマッパーは Statements の `_items` をスキャンするため、concepts フィルタで除外された科目にはアクセスできません。

**結論:** concepts フィルタと extract_values() を組み合わせる場合、summary_mapper / statement_mapper で十分な科目は問題ありません。definition_mapper / calc_mapper に依存する提出者独自科目は、concepts フィルタ**なし**で取得してください。

### 8.5. 訂正報告書（amendment）

同一企業が訂正報告書を提出した場合、同じ期間の書類が複数存在します。

```python
# DEI の amendment_flag で判別
for filing, stmts in iter_parquet(...):
    if stmts is None:
        continue
    dei = stmts.dei
    if dei and dei.amendment_flag:
        # 訂正報告書 — 通常は最新のものだけを使う
        pass
```

**推奨:** ファンダメンタル DB 構築時は `doc_id` の `seq_number`（数値が大きいほど新しい）で最新版を選択するか、DEI の `amendment_flag` / `xbrl_amendment_flag` を確認してください。

### 8.6. 連結/個別の混在

```python
# has_consolidated で確認
for filing, stmts in iter_parquet(...):
    if stmts is None:
        continue
    if stmts.has_consolidated_data:
        result = extract_values(stmts, KEYS, consolidated=True)
    elif stmts.has_non_consolidated_data:
        result = extract_values(stmts, KEYS, consolidated=False)
    else:
        continue  # データなし
```

### 8.7. 会計基準の判別

Parquet に永続化された `DEI` と `DetectedStandard` から会計基準を判別できます。

```python
for filing, stmts in iter_parquet(...):
    if stmts is None or stmts.detected_standard is None:
        continue
    std = stmts.detected_standard.standard
    # std: AccountingStandard.JGAAP / IFRS / USGAAP
```

**注意:** `detected_standard` は DEI 内の `accounting_standards` フィールドに加え、名前空間解析によるフォールバック判別の結果も含みます。Parquet に同梱されるため、再計算は不要です。

### 8.8. ファンド書類

投信関連の書類（有価証券届出書（投信）等）は:

- `filing.fund_code` が設定されている
- XBRL 構造が一般事業会社と異なる
- 1 ZIP 内に数百の XBRL ファイル（ファンドごと）を含むことがある
- パースエラーが発生しやすい

```python
# ファンド書類を除外
for filing, stmts in iter_parquet(...):
    if filing.fund_code:
        continue  # ファンド書類をスキップ
    ...
```

### 8.9. 業種別の財務諸表

`equity_statement()` や `comprehensive_income()` はタクソノミの Presentation Linkbase を使います。Parquet 復元時は `taxonomy_root` が設定されないため、これらのメソッドは空を返します。

```python
# Parquet から復元した Statements
stmts.equity_statement()  # → 空の FinancialStatement

# 代わりに extract_values() を使う
result = extract_values(stmts, [CK.SHAREHOLDERS_EQUITY, CK.RETAINED_EARNINGS])
```

`income_statement()`, `balance_sheet()`, `cash_flow_statement()` は JSON 概念セットベースのため、Parquet 復元後も正常に動作します。

### 8.10. dimensions（セグメント情報）

`dimensions_json` カラムに JSON 配列で格納されています。

```python
# dimensions なし = 全社合計
# dimensions あり = セグメント別
import json

for item in stmts:
    if item.dimensions:
        for dim in item.dimensions:
            print(f"  {dim.axis}: {dim.member}")
```

`extract_values()` はデフォルトで dimensions なし（全社合計）の Fact のみを対象とします。セグメント別の値が必要な場合は Statements を直接イテレーションしてください。

### 8.11. value_numeric の型

`value_numeric` は Parquet 上では文字列（`pa.string()`）です。これは `Decimal` の精度を保持するためです。

```python
# DuckDB での数値変換
# CAST(li.value_numeric AS DOUBLE) -- 近似値で OK な場合
# CAST(li.value_numeric AS DECIMAL(38,0)) -- 精度が必要な場合

# Python の import_parquet では自動的に Decimal に復元される
for item in stmts:
    if isinstance(item.value, Decimal):
        print(f"{item.local_name}: {item.value}")
```

---

## 9. シナリオ別レシピ

### シナリオ 1: 毎日のバッチ — 日次ダンプ + 差分更新

```python
import asyncio
from datetime import date
from edinet.extension import adump_to_parquet

async def daily_dump(target_date: date):
    prefix = f"{target_date.isoformat()}_"
    result = await adump_to_parquet(
        date=target_date,
        output_dir="./parquet/daily",
        prefix=prefix,
        concurrency=8,
    )
    print(f"{target_date}: {result.total_filings}件, "
          f"XBRL: {result.xbrl_ok}/{result.xbrl_count}")
    return result
```

### シナリオ 2: 特定企業の時系列分析（複数 prefix 横断）

```python
import duckdb
from pathlib import Path
from edinet.extension import import_parquet
from edinet.financial.extract import extract_values
from edinet.financial.standards.canonical_keys import CK

DB_DIR = "./parquet/db"

# Step 1: DuckDB で全 prefix を横断して edinet_code から doc_id + prefix を特定
conn = duckdb.connect()
hits = conn.sql(f"""
    SELECT doc_id, filename
    FROM read_parquet('{DB_DIR}/*_filings.parquet', filename=true)
    WHERE edinet_code = 'E00001'
    ORDER BY period_end DESC
""").fetchall()

# filename から prefix を逆引き
def extract_prefix(filepath: str) -> str:
    name = Path(filepath).name  # "2025-01_filings.parquet"
    return name.replace("filings.parquet", "")  # "2025-01_"

# prefix ごとに doc_id をグループ化
from collections import defaultdict
by_prefix: dict[str, list[str]] = defaultdict(list)
for doc_id, filepath in hits:
    by_prefix[extract_prefix(filepath)].append(doc_id)

# Step 2: prefix ごとに import_parquet（doc_ids フィルタで高速）
for prefix, doc_ids in by_prefix.items():
    data = import_parquet(DB_DIR, prefix=prefix, doc_ids=doc_ids)
    for filing, stmts in data:
        if stmts is None:
            continue
        result = extract_values(stmts, [CK.REVENUE, CK.NET_INCOME])
        print(f"{filing.period_end}: revenue={result['revenue']}")
```

**ポイント:** `import_parquet()` は 1 つの prefix しか受け取れないため、DuckDB の glob で先に doc_id を特定し、prefix ごとに分けて読みます。doc_ids フィルタにより各 `import_parquet()` は数件の高速読み込みになります。

### シナリオ 3: 全上場企業のファンダメンタル DB（インクリメンタル構築）

月単位でダンプを蓄積し、まとめて処理する例です。

```python
import asyncio
import csv
from pathlib import Path
from edinet.extension import adump_to_parquet, iter_parquet
from edinet.financial.extract import extract_values, extracted_to_dict
from edinet.financial.standards.canonical_keys import CK

KEYS = [
    CK.REVENUE, CK.OPERATING_INCOME, CK.ORDINARY_INCOME,
    CK.NET_INCOME, CK.NET_INCOME_PARENT,
    CK.TOTAL_ASSETS, CK.NET_ASSETS, CK.SHAREHOLDERS_EQUITY,
    CK.EPS, CK.BPS, CK.DPS, CK.EQUITY_RATIO,
    CK.OPERATING_CF, CK.INVESTING_CF, CK.FINANCING_CF,
]

DB_DIR = Path("./parquet/2025")

# -------------------------------------------------------
# Step 1: 月単位でダンプ（必要な月だけ、好きなタイミングで実行）
# -------------------------------------------------------
async def dump_month(year: int, month: int):
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    prefix = f"{year}-{month:02d}_"

    # 既にダンプ済みならスキップ
    if (DB_DIR / f"{prefix}filings.parquet").exists():
        print(f"{prefix} はダンプ済み、スキップ")
        return

    result = await adump_to_parquet(
        start=f"{year}-{month:02d}-01",
        end=f"{year}-{month:02d}-{last_day}",
        output_dir=DB_DIR,
        prefix=prefix,
        concurrency=8,
    )
    print(f"{prefix}: {result.total_filings}件, XBRL: {result.xbrl_ok}")

# 例: 1月〜3月をダンプ（既存はスキップ）
async def main():
    for m in range(1, 4):
        await dump_month(2025, m)

asyncio.run(main())

# -------------------------------------------------------
# Step 2: 蓄積された全 prefix を走査して extract_values
# -------------------------------------------------------
def build_csv(output_csv: str):
    # ディレクトリ内の prefix を自動検出
    prefixes = sorted({
        p.name.replace("filings.parquet", "")
        for p in DB_DIR.glob("*filings.parquet")
    })
    print(f"対象 prefix: {prefixes}")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "doc_id", "edinet_code", "sec_code", "filer_name",
            "period_start", "period_end", "accounting_standard",
        ] + [k for k in KEYS])
        writer.writeheader()

        for prefix in prefixes:
            print(f"処理中: {prefix}")
            for filing, stmts in iter_parquet(
                DB_DIR, prefix=prefix, batch_size=100,
            ):
                if stmts is None or filing.fund_code:
                    continue

                result = extract_values(
                    stmts, KEYS,
                    period="current", consolidated=True,
                )
                values = extracted_to_dict(result)

                std = (stmts.detected_standard.standard.value
                       if stmts.detected_standard else None)

                writer.writerow({
                    "doc_id": filing.doc_id,
                    "edinet_code": filing.edinet_code,
                    "sec_code": filing.sec_code,
                    "filer_name": filing.filer_name,
                    "period_start": filing.period_start,
                    "period_end": filing.period_end,
                    "accounting_standard": std,
                    **values,
                })

build_csv("funda_2025.csv")
```

**ポイント:**
- **ダンプは好きなタイミングで追加可能。** 今日 1月分、明日 2月分、来週 3月分と追加していく
- **同じ prefix で再実行すればその月だけ上書き。** 他の月に影響なし
- **読み込み時は prefix を自動検出して全月を走査。** prefix を増やすだけでデータが増える
- 月単位なら年間 12 prefix（84 ファイル）で管理しやすい

### シナリオ 4: 特定科目の高速スクリーニング

```python
from edinet.extension import iter_parquet
from edinet.financial.extract import extract_values
from edinet.financial.standards.canonical_keys import CK

# 売上高 > 1兆円の企業を抽出
BIG_REVENUE_CONCEPTS = [
    "NetSales", "Revenue", "OperatingRevenue1",
    "NetRevenue", "Revenues",
]

for filing, stmts in iter_parquet(
    "./parquet",
    prefix="2026-01_",
    concepts=BIG_REVENUE_CONCEPTS,
    batch_size=200,
):
    if stmts is None:
        continue
    result = extract_values(stmts, [CK.REVENUE], period="current")
    ev = result.get("revenue")
    if ev and ev.value and ev.value > 1_000_000_000_000:
        print(f"{filing.filer_name}: {ev.value:,.0f}")
```

**ポイント:** `concepts` フィルタにより、全件走査でも 32s 程度で完了します。

### シナリオ 5: Calculation Linkbase の検証

```python
import duckdb

conn = duckdb.connect()
conn.sql("""
    -- 営業利益の計算構造を確認
    SELECT
        f.filer_name,
        ce.parent,
        ce.child,
        ce.weight
    FROM read_parquet('./parquet/2026-01_calc_edges.parquet') AS ce
    JOIN read_parquet('./parquet/2026-01_filings.parquet') AS f
        ON ce.doc_id = f.doc_id
    WHERE ce.parent = 'OperatingIncome'
    LIMIT 20
""").show()
```

### シナリオ 6: DuckDB で全テーブル横断分析

```python
import duckdb

conn = duckdb.connect()

# 会計基準 × 業種別の平均営業利益率
conn.sql("""
    WITH revenue AS (
        SELECT doc_id, CAST(value_numeric AS DOUBLE) AS rev
        FROM read_parquet('./parquet/2026-01_line_items.parquet')
        WHERE local_name = 'NetSales'
          AND dimensions_json IS NULL
          AND period_type = 'duration'
    ),
    oi AS (
        SELECT doc_id, CAST(value_numeric AS DOUBLE) AS oi
        FROM read_parquet('./parquet/2026-01_line_items.parquet')
        WHERE local_name = 'OperatingIncome'
          AND dimensions_json IS NULL
          AND period_type = 'duration'
    )
    SELECT
        d.accounting_standards,
        d.industry_code_consolidated,
        COUNT(*) AS n,
        AVG(oi.oi / NULLIF(revenue.rev, 0)) AS avg_opm
    FROM read_parquet('./parquet/2026-01_dei.parquet') AS d
    JOIN revenue ON d.doc_id = revenue.doc_id
    JOIN oi ON d.doc_id = oi.doc_id
    WHERE revenue.rev > 0
    GROUP BY d.accounting_standards, d.industry_code_consolidated
    ORDER BY avg_opm DESC
""").show()
```

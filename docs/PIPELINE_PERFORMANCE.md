# Parquet パイプライン性能調査

`adump_to_parquet()` → Parquet 書き出し → `iter_parquet()` 読み込みパイプラインの
性能特性と並列化の実現性についての調査結果。

調査日: 2026-03-11

---

## 目次

1. [パイプラインのボトルネック構造](#1-パイプラインのボトルネック構造)
2. [EDINET API サーバーレイテンシ実測](#2-edinet-api-サーバーレイテンシ実測)
3. [並列数スケーリング実測](#3-並列数スケーリング実測)
4. [ネットワーク vs CPU 律速の分岐点](#4-ネットワーク-vs-cpu-律速の分岐点)
5. [ProcessPool 並列化の実現性](#5-processpool-並列化の実現性)
6. [ThreadPool vs ProcessPool 比較](#6-threadpool-vs-processpool-比較)
7. [書き出しパイプラインの設計](#7-書き出しパイプラインの設計)
8. [読み込み側の性能特性](#8-読み込み側の性能特性)
9. [結論と推奨](#9-結論と推奨)

---

## 1. パイプラインのボトルネック構造

### `adump_to_parquet()` の 1 書類あたりのコスト内訳

| フェーズ | 処理内容 | 推定コスト | 並列化状況 |
|---|---|---|---|
| **ネットワーク** | EDINET API → ZIP DL（avg ~500KB） | 1.8s/件 | asyncio concurrency=8 で並列 |
| **CPU** | lxml パース + タクソノミ解決 + LineItem 生成 | 0.5-1s/件 | **直列**（sync、event loop ブロック） |
| **ローカル I/O** | serialize + Parquet 書き出し | 50-100ms/件 | 直列 |

### event loop ブロックの問題

`axbrl()` は「DL は await で非同期、パース処理は同期的に実行」する設計
（`filing.py` axbrl docstring: "ネットワーク I/O（ZIP ダウンロード）のみ非同期で、パース処理は同期的に実行する"）。

パース中は event loop がブロックされ、他のダウンロードも進行しない。

```
DL1 → Parse1(block 0.7s) → DL2完了済 → Parse2(block 0.7s) → ...
```

TCP バッファに溜まったデータは即読み出せるが、バッファサイズ（~256KB）を超える分は待ちが発生する。

---

## 2. EDINET API サーバーレイテンシ実測

計測スクリプト: `tools/_bench_edinet_latency.py`

### 書類一覧 API（metadata）

| 日付 | 書類数 | レイテンシ |
|---|---|---|
| 2025-06-25（有報集中日） | 1,784 件 | 4.1-4.9s |
| 2025-03-31 | 767 件 | 0.16-0.19s |
| 2025-01-15 | 311 件 | 0.11s |

件数が多い日はレスポンスが遅い。

### ZIP ダウンロード（逐次、10 件サンプル）

| 指標 | 値 |
|---|---|
| 平均レイテンシ | **1.81-1.89s** |
| 最小 | 0.35s（11 KB の小規模 ZIP） |
| 最大 | 3.70s（938 KB の有報 ZIP） |
| 平均 ZIP サイズ | 454 KB |
| 実効スループット | 240-250 KB/s |

**14KB の ZIP でも 0.35s かかっている** → 帯域ではなくサーバー処理時間が支配的。

### 環境別ボトルネック

| ネットワーク環境 | ボトルネック |
|---|---|
| < 10 Mbps | ユーザー側のネットワーク帯域 |
| 10-100 Mbps | EDINET API サーバーのレイテンシ |
| 100 Mbps+ | CPU（XBRL パースの同期ブロック） |

---

## 3. 並列数スケーリング実測

50 件の XBRL 書類（2025-06-25）を対象に、並列数を 1〜64 で変化させて計測。

### 結果

| 並列数 | 全体時間 | wall/件 | 個別レイテンシ | スループット | 速度比 | エラー |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 134.5s | 2.69s | 2.69s | 347 KB/s | 1.0x | 0 |
| 4 | 34.2s | 0.68s | 2.47s | 1,365 KB/s | 3.9x | 0 |
| **8** | **21.7s** | **0.43s** | **3.08s** | **2,158 KB/s** | **6.2x** | **0** |
| 16 | 30.2s | 0.60s | 5.26s | 1,549 KB/s | 4.5x | 0 |
| 32 | 21.0s | 0.42s | 7.53s | 2,225 KB/s | 6.4x | 0 |
| 64 | 22.6s | 0.45s | 9.69s | 2,067 KB/s | 5.9x | 0 |

### 分析

- **8 並列で頭打ち**（6.2x）。16〜64 に増やしてもほぼ改善なし（21-23s で横ばい）
- **エラーは 0 件** — レート制限による接続拒否は発生しなかった
- **個別レイテンシは並列数に比例して悪化** — 64 並列で 9.69s。サーバー側で同時接続数に応じてスロットリングしている
- 16 並列が 30.2s と 8 並列より遅いのは、サーバー側の負荷変動（タイミング依存）
- 全体スループットは ~2 MB/s で天井

### 結論

**DL 並列数は 8 が実質上限。** これ以上増やしてもサーバー側が個別レスポンスを遅くするだけで、全体スループットは変わらない。

---

## 4. ネットワーク vs CPU 律速の分岐点

### 理論計算

CPU 律速の条件: `DL 時間 / 実効並列数 < パース時間`

```
ZIP_size / (bandwidth × concurrency) < parse_time
1MB / (bandwidth × 8) < 0.7s
bandwidth > 180 KB/s ≈ 1.4 Mbps
```

ただし EDINET API サーバー自体のレイテンシが 1.8s/件あるため、ユーザー側の帯域が速くてもサーバー律速になる。

### 実測ベースの結論

現状の EDINET API 相手では:

- **DL スループット**: ~2 MB/s（8 並列、サーバー律速）= ~4.4 件/s
- **パーススループット**: 1 プロセスで ~1.4 件/s
- **DL > パース** なので、**CPU（パース）が律速**

パースを並列化すれば DL 供給速度に追いつける:

| パースプロセス数 | パーススループット | DL に追いつくか |
|---:|---:|---|
| 1 | 1.4 件/s | ✗（DL の 4.4 件/s に負ける） |
| 4 | 5.6 件/s | ✓ |
| 8 | 11.2 件/s | ✓（余裕あり） |

**4 プロセスで DL 供給に追いつく。** 8 プロセスなら余裕がある。

---

## 5. ProcessPool 並列化の実現性

### パースフロー（全て CPU-bound・同期）

`axbrl()` 内の `_build_statements()` が実行する処理:

```
Step 3: 提出者タクソノミ抽出（ZIP から _lab.xml, .xsd 等）
Step 4: lxml で XBRL パース → RawFact リスト ← 最重量
Step 5: Context 構造化
Step 6: ラベル解決（TaxonomyResolver）
Step 7: LineItem 生成
Step 7b: リンクベースパース（Calculation, Definition）
Step 8: Statement 組み立て
```

Step 3〜7b が全て同期処理で、asyncio の恩恵を受けていない。

### pickle 可能性

| 型 | pickle | 備考 |
|---|---|---|
| Filing (Pydantic BaseModel) | ✓ | frozen=True |
| LineItem (frozen dataclass) | ✓ | |
| StructuredContext (frozen dataclass) | ✓ | |
| RawFact (frozen dataclass) | ✓ | |
| TaxonomyResolver | ⚠️ | pickle 可能だが辞書が 100MB+ → 転送コスト大 |
| CalculationLinkbase | ✓ | |
| DefinitionTree | ✓ | |

### TaxonomyResolver の問題

- プロセスメモリが隔離されるため `_resolver_cache` は共有不可
- 各ワーカーで独立に `get_taxonomy_resolver()` を初期化する必要がある
- 初回起動時に全プロセス分のタクソノミパースが走る（各 ~2 分）
- ただしプロセス内キャッシュにより 2 回目以降は即座

### 設計アプローチ

#### アプローチ A: ワーカーが DL + パース両方（extension/ 内で完結）

```
Main (asyncio): Filing リスト配布 → 結果受け取り → Parquet 書き出し
Worker (×8):    filing.xbrl() → DL + パース + serialize → dict を返す
```

- **変更範囲**: `extension/__init__.py` のみ（~200 行）
- **メリット**: 既存 API に変更なし
- **デメリット**: DL が sync になる（実質的には同等、サーバー律速のため）

#### アプローチ B: Main が async DL → ワーカーがパースのみ

```
Main (asyncio): Semaphore(8) で DL → zip_bytes をキューに投入
Worker (×N):    zip_bytes → パース → serialize → dict を返す
Main:           dict → ParquetWriter 書き出し
```

- **変更範囲**: `extension/__init__.py` + `models/filing.py`（`_build_statements` の公開）
- **メリット**: DL 並列数とパース並列数を独立に制御可能
- **デメリット**: Filing の公開 API が増える

#### アプローチ選定

DL は 8 並列が上限（サーバー律速）で、パースも 4-8 プロセスで追いつくため、
**DL とパースの並列数を独立制御する需要がない**。

→ **アプローチ A（extension/ 内で完結）で十分。**

---

## 6. ThreadPool vs ProcessPool 比較

### パース 0.7s/件の内訳推定と GIL の影響

| 処理 | 比率 | GIL | ThreadPool | ProcessPool |
|---|---|---|---|---|
| lxml XML パース | ~50% | **リリース**（C 拡張） | 並列 | 並列 |
| dict 操作（ラベル解決等） | ~30% | **保持** | 直列 | 並列 |
| dataclass 生成 | ~20% | **保持** | 直列 | 並列 |

### 比較表

| 観点 | ThreadPool | ProcessPool |
|---|---|---|
| TaxonomyResolver | **1 個共有**（初期化コスト 0） | プロセスごと独立初期化（各 ~2 分） |
| メモリ使用量 | +ほぼ 0 | +800MB〜（resolver 100MB × 8） |
| lxml パース並列化 | ✓（GIL リリース） | ✓ |
| Python dict 操作並列化 | ✗（GIL 保持） | ✓ |
| データ転送コスト | ゼロコピー | pickle シリアライズ |
| スレッドセーフ | `_resolver_cache` に注意 | 隔離されてるので問題なし |
| 障害分離 | 1 スレッド死亡 → プロセス全体死亡 | 1 プロセス死亡 → 他は無事 |
| 変更量 | 20-30 行 | ~200 行 |
| **並列化率** | **~50%**（lxml 部分のみ） | **~100%** |
| **理論上限（8 並列）** | **~1.8 倍** | **~6-7 倍** |

### ユースケース別推奨

| ユースケース | 推奨 | 理由 |
|---|---|---|
| 短時間ジョブ（1 日分） | ThreadPool | 初期化なし、1.8 倍でも十分 |
| 長時間ジョブ（月〜年間） | ProcessPool | 初期化コスト償却、6-7 倍 |
| メモリ制約あり | ThreadPool | +0 MB |

---

## 7. 書き出しパイプラインの設計

### `adump_to_parquet()` の内部構造

```python
# 1. 書類一覧取得（軽量メタデータ、全件メモリ保持）
filings = await adocuments(date, start, end, doc_type, ...)

# 2. non-XBRL → Filing だけ即書き出し
writers.write_rows("filings", [...])

# 3. XBRL → Semaphore(8) で並行 DL + パース → 即書き出し → 即解放
async def _process_xbrl(filing):
    async with sem:                          # 最大 8 件同時
        stmts = await filing.axbrl(...)      # DL(async) + パース(sync)
    writers.write_rows("filings", [...])     # serialize + 書き出し
    writers.write_rows("line_items", [...])
    # ... 7 テーブル全て書き出し
    del stmts                                # メモリ解放
    filing.clear_fetch_cache()

await asyncio.gather(*[_process_xbrl(f) for f in xbrl_filings])
```

- **Statements は蓄積しない** — 1 件パース→即書き出し→即解放
- **メモリ**: 最大 concurrency 件分の Statements しか保持しない（peak ~170MB）
- **年間 7 万件でもメモリ不足にならない**

### 書類種別ごとのダンプ

`doc_type` パラメータは単一値のみ受け付けるため、複数種別は別 prefix でダンプする。

```bash
# tools/dump_securities_reports.py で実装済み
uv run python tools/dump_securities_reports.py \
    --api-key YOUR_KEY \
    --start 2025-06-01 --end 2025-06-30
```

出力例:

```
120_2025-06-01_2025-06-30_filings.parquet
120_2025-06-01_2025-06-30_line_items.parquet
130_2025-06-01_2025-06-30_filings.parquet
...
```

---

## 8. 読み込み側の性能特性

### 年単位 vs 月単位 prefix

| | 年単位 prefix | 月単位 prefix |
|---|---|---|
| RG マッピング構築 | 7 万 RG → 数十秒 | 6 千 RG × 12 = 7 万 RG（**同じ**） |
| iter_parquet メモリ | batch_size に依存（同じ） | 同じ |
| 途中失敗の影響 | 全部やり直し | 月単位で再実行可能 |
| DuckDB 直接クエリ | 問題なし | 問題なし |

**読み込み時の走査 RG 総数は同じ。** 月単位のメリットは書き出し側の再実行粒度。

### `doc_type_codes` フィルタ

`iter_parquet()` / `import_parquet()` に `doc_type_codes` パラメータを追加済み。

```python
for filing, stmts in iter_parquet(
    "./parquet", prefix="...",
    doc_type_codes=["120", "130"],  # 有報 + 訂正有報のみ
    concepts=["NetSales", "OperatingIncome"],
    batch_size=100,
):
    ...
```

- `doc_type_codes` 単体: 対象外書類が軽量な場合、速度改善は限定的
- **`doc_type_codes` + `concepts` 併用**: 6.5 倍高速化（最も効果的）

---

## 9. 結論と推奨

### 現状の性能プロファイル

```
EDINET API DL:  ~2 MB/s（8 並列、サーバー律速）= ~4.4 件/s
XBRL パース:    ~1.4 件/s（シングルプロセス、CPU 律速）
Parquet 書き出し: ~10 件/s（軽量、律速にならない）
```

**パースが律速。** DL は 8 並列で頭打ち。

### 推奨施策（効果順）

| 施策 | 効果 | 実装コスト | 変更範囲 |
|---|---|---|---|
| ProcessPool（パース並列化） | 6-7 倍 | ~200 行 | extension/ のみ |
| ThreadPool（パース並列化） | ~1.8 倍 | 20-30 行 | extension/ のみ |
| concurrency 増加（DL 並列） | 効果なし | - | - |
| 高クロック CPU | パース時間に比例 | ハードウェア | - |

### 現状で十分なケース

- 1 日分（~1,800 件）: 現状 ~15 分、ProcessPool で ~3 分
- 1 ヶ月分（~5,000 件）: 現状 ~45 分、ProcessPool で ~10 分
- 年間（~70,000 件）: 現状 ~10 時間、ProcessPool で ~2 時間

バッチ処理として夜間実行するなら、現状の asyncio 版でも年間データを 1 晩で処理可能。
ProcessPool 化は「待ち時間を減らしたい」場合に有効。

### 関連ファイル

- `tools/_bench_edinet_latency.py` — EDINET API レイテンシ計測スクリプト
- `tools/dump_securities_reports.py` — 有報系統ダンプパイプライン
- `tools/bench_doc_type_filter.py` — doc_type_codes フィルタベンチマーク
- `tools/parquet_read_stress_test.py` — 読み込み性能計測
- `src/edinet/extension/README.md` — Parquet パイプラインのベストプラクティス

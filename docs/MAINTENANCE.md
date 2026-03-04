# 運用保守ガイド（V030 完了版）

> **作成日**: 2026-03-04
> **前版**: Wave 4 完了版（2026-03-02）
> **本版の変更点**: V030（パイプラインマッパーリファクタ）完了後の実態を反映。存在しないファイル・dataclass の記述を全面修正。数値を実コードと突合

---

## 目次

- [Part 1: ハードコード全量マップ](#part-1-ハードコード全量マップ)
- [Part 2: 保守カテゴリ別ガイド](#part-2-保守カテゴリ別ガイド)
- [Part 3: 自動化の現状](#part-3-自動化の現状)
- [Part 4: 検証方法](#part-4-検証方法)
- [Appendix: Q&A 記録](#appendix-qa-記録)

---

# Part 1: ハードコード全量マップ

2026-03-04 時点のコードベース全量調査に基づく。

## サマリ

| 保守頻度 | カテゴリ | エントリ総数 | ファイル数 | 生成方法 |
|---|---|---|---|---|
| **月次〜四半期** | 自動生成マスタ | 18,013 | 3 | スクリプト |
| **年次** | タクソノミ concept マッピング | 352 | 3 | 手動 + CK 定数 |
| **数年に一度** | 法令・API 仕様 | ~100 | 5 | 手動 |
| **不変** | XBRL/EDINET 構造定数 | ~60 | 8 | — |
| | **合計** | **~18,525** | **19** | |

## 全ファイル一覧

### 自動生成マスタ（スクリプトで再生成）

| ファイル | 行数 | エントリ数 | ソースデータ | 生成スクリプト |
|---|---|---|---|---|
| `models/edinet_code.py` | 168,580 | 11,223 | `EdinetcodeDlInfo.csv` | `tools/generate_edinet_codes.py` |
| `models/fund_code.py` | 70,209 | 6,377 | `FundcodeDlInfo.csv` | `tools/generate_fund_codes.py` |
| `models/form_code.py` | 3,778 | 413 | `ESE140327.xlsx` | `tools/generate_form_codes.py` |

### タクソノミ concept マッピング（手動保守）

| ファイル | concept 数 | 参照タクソノミ | 内容 |
|---|---|---|---|
| `financial/standards/canonical_keys.py` | **120 CK 定数** | — | 全 canonical_key の StrEnum 定数 |
| `financial/standards/summary_mappings.py` | 97 | `jpcrp_cor` | SummaryOfBusinessResults → CK（4基準統合） |
| `financial/standards/statement_mappings.py` | 135 | `jppfs_cor`, `jpigp_cor` | PL/BS/CF 本体 → CK（J-GAAP + IFRS）+ 正規化レイヤー |
| **合計** | **232 + 120 CK** | | |

#### statement_mappings.py のマッチング戦略

`lookup_statement()` は防御的 2 段マッチングを使用:

1. **辞書完全一致** (`lookup_statement_exact`): `_CONCEPT_INDEX` から O(1) で取得
2. **正規化フォールバック** (`lookup_statement_normalized`): EDINET サフィックス（`IFRS`, `JGAAP` 等）+ ポジションタグ（`CA`, `CL` 等）を剥離後に辞書引き

#### パイプラインマッパー（`mapper.py`）

`extract_values()` はパイプラインマッパーで `_items` を 1 パス走査する。デフォルトパイプラインは `[summary_mapper, statement_mapper]`。パイプライン位置（先頭が高優先）で同一 CK の競合を解決する。

| マッパー | 役割 |
|---|---|
| `summary_mapper` | `lookup_summary()` を呼ぶ。SummaryOfBusinessResults 概念のマッチ |
| `statement_mapper` | `lookup_statement_exact()` → `lookup_statement_normalized()` の 2 段フォールバック |
| `dict_mapper()` | ユーザー辞書からの O(1) ルックアップ（ファクトリ関数） |

### 法令・API 仕様（手動保守、低頻度）

| ファイル | エントリ数 | 内容 | ソース |
|---|---|---|---|
| `models/doc_types.py` | 42 enum + 16 訂正マップ | 書類種別コード | EDINET API 仕様書 |
| `models/ordinance_code.py` | 7 enum | 府令コード | EDINET API 仕様書 |
| `xbrl/dei.py` | 27 + 6 enum + 20 業種マップ | DEI フィールドマップ | `jpdei_cor` |
| `api/documents.py` | ~10 | API パス、パラメータ名、JSONフィールド名 | EDINET API v2 |
| `_http.py` | ~13 | 認証ヘッダ名、リトライ設定、接続制限 | EDINET API v2 |

### 不変のハードコード（保守不要）

| ファイル | エントリ数 | 内容 | 依存先 |
|---|---|---|---|
| `xbrl/_namespaces.py` | 13 URI + 2 regex | XBRL 標準 NS + EDINET URL パターン | W3C XBRL 仕様 |
| `xbrl/taxonomy/concept_sets.py` | 11 キーワード + 1 regex | role URI 分類 | EDINET 設定規約書 |
| `financial/statements.py` | 3 定数 | 連結軸名 | EDINET 次元命名規則 |
| `xbrl/contexts.py` | 2 定数 | 連結軸名（statements.py と重複） | 同上 |
| `xbrl/units.py` | 3 プレフィクス | iso4217, xbrli, utr | XBRL 仕様 |
| `xbrl/dei.py` | 2 NS パターン | DEI NS | EDINET 制度 |
| `models/financial.py` | 5 enum + 5 ラベル | StatementType（PL/BS/CF/SS/CI） | 会計の基本構造 |
| `api/download.py` | 5 サイズ上限 | ZIP 展開制限 | セキュリティ設計 |

---

# Part 2: 保守カテゴリ別ガイド

## A. 自動生成マスタデータ（月次〜四半期）

### 対象ファイル

| ファイル | ソース | エンコーディング | 更新トリガー |
|---|---|---|---|
| `edinet_code.py` (168K行) | `EdinetcodeDlInfo.csv` | Shift-JIS (cp932) | 企業の上場/廃止/住所変更等 |
| `fund_code.py` (70K行) | `FundcodeDlInfo.csv` | Shift-JIS (cp932) | 投資信託の設定/償還 |
| `form_code.py` (3.8K行) | `ESE140327.xlsx` | Excel | 様式の新設（数年に一度） |

### 更新手順

```bash
# 1. EDINET から最新データをダウンロード
# 2. data/source/ にソースファイルを配置
# 3. 生成スクリプト実行
uv run python tools/generate_edinet_codes.py --source data/source/EdinetcodeDlInfo.csv
uv run python tools/generate_fund_codes.py   --source data/source/FundcodeDlInfo.csv
uv run python tools/generate_form_codes.py   --source data/source/ESE140327.xlsx
# 4. テスト
uv run pytest tests/test_models/
# 5. スタブ再生成
uv run stubgen src/edinet --include-docstrings -o stubs
```

### 注意事項

- **エンコーディング**: CSV は必ず Shift-JIS のまま使用。UTF-8 に変換すると文字化けする
- **ヘッダ検証**: スクリプトはヘッダ行を厳密に検証し、不一致時はエラーで停止する
- **git 管理**: 24万行が毎回変更される。差分レビューは `git diff --stat` 推奨

---

## B. タクソノミ年次更新（年1回）

EDINET タクソノミは **年1回（11月1日付）** で改定される。

### 保守フロー

```
1. 金融庁から新タクソノミ ZIP をダウンロード → EDINET_TAXONOMY_ROOT 設定変更
2. uv run pytest で既存テストを実行（概念名の不一致があれば失敗する）
3. 下記チェックリストに従い Python ファイル内のマッピングを突合・修正
4. uv run pytest で回帰テストを再実行
5. uv run stubgen src/edinet --include-docstrings -o stubs でスタブ再生成
```

### マッピングデータの構成

concept → CK のマッピングは 2 ファイルに集約されている:

**summary_mappings.py `SummaryMapping`**:

| フィールド | 内容 | 保守方法 |
|---|---|---|
| `concept` | jpcrp_cor のローカル名（例: `"NetSalesSummaryOfBusinessResults"`） | タクソノミ突合 |
| `canonical_key` | CK StrEnum 定数（例: `CK.REVENUE`） | 人間の知識（typo は StrEnum が防止） |
| `standard` | 会計基準識別子（`"jgaap"` / `"ifrs"` / `"usgaap"` / `"jmis"`） | タクソノミ突合 |

エントリは `_JGAAP`（40件）、`_IFRS`（19件）、`_USGAAP`（19件）、`_JMIS`（19件）の 4 タプルに分かれている。

**statement_mappings.py（plain dict）**:

| 構造 | 内容 | 保守方法 |
|---|---|---|
| `_JGAAP_PL`, `_JGAAP_BS`, `_JGAAP_CF` | J-GAAP の concept → CK 辞書 | タクソノミ突合 |
| `_IFRS_PL`, `_IFRS_BS`, `_IFRS_CF` | IFRS の concept → CK 辞書 | タクソノミ突合 |
| `_CONCEPT_INDEX` | 上記 6 辞書のマージ | 自動（dict の `**` 展開） |

各辞書は `{concept_local_name: CK.XXX}` の plain dict であり、dataclass は使用していない。

### 修正パターン

**concept 名が変更された場合:**

```python
# statement_mappings.py の _JGAAP_PL 内:
# Before:
"NetSales": CK.REVENUE,
# After:
"Revenue": CK.REVENUE,
# ^^^^^^^^ concept だけ変更。CK 定数は不変
```

**新 concept が追加された場合:**

```python
# 1. canonical_keys.py に CK 定数を追加
class CK(StrEnum):
    # --- PL ---
    NEW_CONCEPT = "new_concept"  # 追加

# 2. statement_mappings.py の対応辞書に追加
_JGAAP_PL: dict[str, str] = {
    ...,
    "NewConcept": CK.NEW_CONCEPT,  # 追加
}

# 3. summary 版がある場合は summary_mappings.py にも追加
SummaryMapping("NewConceptSummaryOfBusinessResults", CK.NEW_CONCEPT, "jgaap"),
```

### 自動追従するファイル（タクソノミ更新の影響を受けない）

| ファイル | 理由 |
|----------|------|
| `taxonomy/concept_sets.py` | Presentation Linkbase を毎回スキャンして動的導出。**自動追従** |
| `taxonomy/__init__.py` (TaxonomyResolver) | ラベルリンクベースを動的読み込み。**自動追従** |
| `standards/normalize.py` | statement_mappings へのファサード。自身に concept 名なし |
| `financial/extract.py` | パイプラインマッパーで 1 パス抽出。マッピングデータなし |
| `financial/mapper.py` | `summary_mapper` / `statement_mapper` / `dict_mapper` の定義。マッピングデータは summary_mappings / statement_mappings に委譲 |
| `financial/statements.py` | normalize 経由で概念セットを取得。直接の concept 依存なし |
| `xbrl/parser.py` | XML 構造のパースのみ |
| `xbrl/_namespaces.py` | namespace URI をバージョン非依存の正規表現で処理 |
| `standards/detect.py` | DEI 値とモジュールグループ名で判定。バージョン非依存 |
| `xbrl/contexts.py`, `xbrl/units.py` | XML 構造解析のみ |
| `linkbase/*.py` | XML 構造のパースのみ |

---

## C. 法令・API 仕様変更（数年に一度）

| トリガー | 頻度 | 影響箇所 | 緊急度 |
|----------|------|----------|--------|
| EDINET API 仕様変更（v2→v3） | 数年に1回 | `api/` 以下の URL・パラメータ・JSONフィールド名、`_http.py` の認証ヘッダ | **高**（動かなくなる） |
| 法改正（書類種別の新設・廃止） | 不定期 | `doc_types.py` の enum 42件 + `_DOC_TYPE_NAMES_JA` + `_CORRECTION_MAP` | 中 |
| 府令の新設 | 極めてまれ | `ordinance_code.py` の enum 7件 | 低 |
| DEI 制度改正（新項目追加） | 極めてまれ | `dei.py` の `_DEI_FIELD_MAP` 27件 + 業種マップ 20件 | 中 |
| 会計基準の新設 | 極めてまれ | `dei.py` の `AccountingStandard` enum 4件 + `PeriodType` enum 2件 | 中 |

### graceful degradation

- `DocType.from_code()`: 未知のコード → `None` + warning（例外なし）
- `OrdinanceCode.from_code()`: 同上
- `EdinetCodeEntry` / `FundCodeEntry` ルックアップ: 未登録 → `None`（例外なし）

---

## D. 不変のハードコード（保守不要）

EDINET/XBRL の仕様レベルに依存しており、仕様の根本改訂がない限り変更不要。

### concept_sets.py の堅牢性

concept_sets.py は **concept 名を一切ハードコードしていない**。ハードコードは全て EDINET 設定規約書に明記された仕様レベル:

| ハードコード | 壊れるケース |
|---|---|
| `_STATEMENT_KEYWORDS` (11個) | XBRL 仕様 + EDINET role URI 命名規則の変更 |
| `_STMT_RE` | EDINET 設定規約書のファイル名命名規則変更 |
| `taxonomy/{module_group}/*/r` glob | EDINET ディレクトリ構造変更 |
| `"cai"` / `"ifrs"` デフォルト | EDINET 業種コード体系変更 |

タクソノミが 2025-11-01 → 2026-11-01 に更新された場合、concept_sets.py は **コード変更不要で自動追従** する。

---

# Part 3: 自動化の現状

## 現在のアーキテクチャ

concept → CK のマッピングは以下の 3 ファイルに集約されている。dataclass やメタデータフィールドは最小限で、plain dict + `SummaryMapping`（3 フィールド）のみ:

| ファイル | データ構造 | concept 数 |
|---|---|---|
| `canonical_keys.py` | `CK` StrEnum | 120 定数 |
| `summary_mappings.py` | `SummaryMapping(concept, canonical_key, standard)` | 97 |
| `statement_mappings.py` | `dict[str, str]` (concept → CK) | 135 |

ラベル（`label_ja` / `label_en`）、表示順（`display_order`）、合計フラグ（`is_total`）等のメタデータはマッピングに含まれず、以下のパイプラインで動的に取得される:

| メタデータ | 取得元 |
|---|---|
| ラベル（日本語/英語） | TaxonomyResolver (`taxonomy/__init__.py`) が Linkbase から動的読み込み |
| 表示順 | concept_sets の `ConceptEntry.order`（Presentation Linkbase から動的導出） |
| 合計フラグ | concept_sets の `preferredLabel`（Presentation Linkbase から動的導出） |
| 財務諸表分類（PL/BS/CF） | concept_sets が role URI から動的分類 |

## 現在の保守コスト

```
タクソノミ年次更新（タクソノミ追従が必要なファイル）:
  summary_mappings.py      → Summary concept 名の変更追従（97件）
  statement_mappings.py    → PL/BS/CF concept 名の変更追従（135件）
  canonical_keys.py        → 新 CK の追加のみ（年に 0〜数件）

タクソノミ追従不要（安定コード）:
  concept_sets             → 変更不要（Presentation Linkbase 動的導出）
  taxonomy/labels          → 変更不要（動的読み込み）
  normalize.py             → statement_mappings へのファサード
  extract.py               → パイプラインマッパー（ロジックのみ）
  mapper.py                → マッパー定義（ロジックのみ）

マスタデータ更新:
  edinet_code              → スクリプト実行
  fund_code                → スクリプト実行
  form_code                → 数年に一度
```

---

# Part 4: 検証方法

## 1. 単体テスト

```bash
uv run pytest
```

concept 名の不一致はテストで検出できる（全マッピングの整合性テストが `test_statement_mappings.py`, `test_summary_mappings.py`, `test_canonical_keys.py` に存在）。

## 2. タクソノミ実在検証（`EDINET_TAXONOMY_ROOT` 必須）

```bash
EDINET_TAXONOMY_ROOT=/path/to/ALL_YYYYMMDD uv run pytest -m integration
```

| 対象 | テストファイル | テストクラス | 状態 |
|------|---------------|-------------|------|
| PL/BS/CF 本体 (J-GAAP + IFRS) | `test_statement_mappings.py` | `TestTaxonomyExistence` | 実装済み |
| SummaryOfBusinessResults | `test_summary_mappings.py` | `TestTaxonomyExistence` | 実装済み |

Presentation Linkbase + XSD の2段階フォールバックで全 concept 名の実在を検証する。`EDINET_TAXONOMY_ROOT` 未設定時はスキップ。

## 3. クロスバリデーション

| 検証内容 | テスト |
|---|---|
| summary_mappings の全 CK が CK enum に存在 | `test_canonical_keys.py` T08-T09 |

## 4. lint + スタブ

```bash
uv run ruff check src tests
uv run stubgen src/edinet --include-docstrings -o stubs
```

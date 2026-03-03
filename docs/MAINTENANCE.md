# 運用保守ガイド（Wave 4 完了版）

> **作成日**: 2026-03-02
> **前版**: `MAINTENANCE.md`（タクソノミ年次更新のみ）、`MAINTENANCE.new.md`（Wave 3 完了時点の全量調査）
> **本版の変更点**: Wave 4（自動化統合 & スリム化）完了後の実態を反映。フィールド構造・concept 数・コード例を全て更新

---

## 目次

- [Part 1: ハードコード全量マップ](#part-1-ハードコード全量マップ)
- [Part 2: 保守カテゴリ別ガイド](#part-2-保守カテゴリ別ガイド)
- [Part 3: 自動化の現状](#part-3-自動化の現状)
- [Part 4: 検証方法](#part-4-検証方法)
- [Appendix: Q&A 記録](#appendix-qa-記録)

---

# Part 1: ハードコード全量マップ

2026-03-02 時点（Wave 4 完了後）のコードベース全量調査に基づく。

## サマリ

| 保守頻度 | カテゴリ | エントリ総数 | ファイル数 | 生成方法 |
|---|---|---|---|---|
| **月次〜四半期** | 自動生成マスタ | 18,013 | 3 | スクリプト |
| **年次** | タクソノミ concept マッピング | 301 | 9 | 手動 + CK 定数 |
| **数年に一度** | 法令・API 仕様 | ~100 | 5 | 手動 |
| **不変** | XBRL/EDINET 構造定数 | ~55 | 8 | — |
| | **合計** | **~18,439** | **25** | |

## 全ファイル一覧

### 自動生成マスタ（スクリプトで再生成）

| ファイル | 行数 | エントリ数 | ソースデータ | 生成スクリプト |
|---|---|---|---|---|
| `models/edinet_code.py` | 168,411 | 11,223 | `EdinetcodeDlInfo.csv` | `tools/generate_edinet_codes.py` |
| `models/fund_code.py` | 70,209 | 6,377 | `FundcodeDlInfo.csv` | `tools/generate_fund_codes.py` |
| `models/form_code.py` | 3,778 | 413 | `ESE140327.xlsx` | `tools/generate_form_codes.py` |

### タクソノミ concept マッピング（手動保守）

| ファイル | concept 数 | 参照タクソノミ | 内容 |
|---|---|---|---|
| `financial/standards/canonical_keys.py` | **100 CK 定数** | — | 全 canonical_key の StrEnum 定数 |
| `financial/standards/summary_mappings.py` | 77 | `jpcrp_cor` | SummaryOfBusinessResults → CK（4基準統合） |
| `financial/standards/statement_mappings.py` | ~130 | `jppfs_cor`, `jpigp_cor` | PL/BS/CF 本体 → CK（J-GAAP + IFRS）+ 正規化レイヤー |
| **合計** | **~207 + 100 CK** | | |

#### statement_mappings.py の 3 層マッチング

`lookup_statement()` は防御的 2 段マッチングを使用:

1. **辞書完全一致** (`lookup_statement_exact`): `_CONCEPT_INDEX` から O(1) で取得
2. **正規化フォールバック** (`lookup_statement_normalized`): EDINET サフィックス（`IFRS`, `JGAAP` 等）+ ポジションタグ（`CA`, `CL` 等）を剥離後に辞書引き

`extract_values()` は `_items` を 2 パスで走査し、exact の結果を normalized が上書きしない。

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
| `xbrl/_namespaces.py` | 11 URI + 2 regex | XBRL 標準 NS + EDINET URL パターン | W3C XBRL 仕様 |
| `xbrl/taxonomy/concept_sets.py` | 11 キーワード + 1 regex | role URI 分類 | EDINET 設定規約書 |
| `xbrl/statements.py` | 3 定数 | 連結軸名 | EDINET 次元命名規則 |
| `xbrl/contexts.py` | 2 定数 | 連結軸名（statements.py と重複） | 同上 |
| `xbrl/units.py` | 3 プレフィクス | iso4217, xbrli, utr | XBRL 仕様 |
| `xbrl/dei.py` | 2 NS パターン | DEI NS | EDINET 制度 |
| `models/financial.py` | 3 enum + 3 ラベル | StatementType | 会計の基本構造 |
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

### 各マッピングのフィールド構成（Wave 4 後）

Wave 4 で `label_ja`, `label_en`, `display_order`, `period_type`, `is_total` は全て削除済み。各 ConceptMapping は以下のフィールドのみ:

**jgaap.py `ConceptMapping`**:

| フィールド | 内容 | 保守方法 |
|---|---|---|
| `concept` | タクソノミの concept ローカル名 | タクソノミ突合 |
| `canonical_key` | CK StrEnum 定数 | 人間の知識（typo は StrEnum が防止） |
| `statement_type` | PL/BS/CF（KPI は None） | レガシーフォールバック用 |
| `is_jgaap_specific` | J-GAAP 固有フラグ | 人間の知識 |

**ifrs.py `IFRSConceptMapping`**:

| フィールド | 内容 |
|---|---|
| `concept` | タクソノミの concept ローカル名 |
| `canonical_key` | CK StrEnum 定数 |
| `statement_type` | PL/BS/CF（KPI/CI は None） |
| `is_ifrs_specific` | IFRS 固有フラグ |
| `jgaap_concept` | J-GAAP 対応（jgaap レジストリに実在するか _validate_registry で検証） |
| `mapping_note` | 補足説明 |

**usgaap.py `_SummaryConceptDef`**:

| フィールド | 内容 | 保守方法 |
|---|---|---|
| `key` | 正規化キー（CK と同一値） | canonical_keys.py と統一 |
| `concept_local_name` | jpcrp_cor の concept ローカル名 | タクソノミ突合 |
| `jgaap_concept` | 対応する J-GAAP concept（None 可） | jgaap.py と突合 |
| `label_ja` | 日本語ラベル | jpcrp_cor ラベルファイル突合 |
| `label_en` | 英語ラベル | jpcrp_cor ラベルファイル突合 |

**sector/*.py `SectorConceptMapping`**:

| フィールド | 内容 |
|---|---|
| `concept` | タクソノミの concept ローカル名 |
| `sector_key` | 業種内ローカルの正規化キー |
| `industry_codes` | 適用業種コード |
| `general_equivalent` | CK StrEnum 定数（一般事業会社の canonical_key への翻訳） |
| `mapping_note` | 補足説明 |

### 修正パターン

**concept 名が変更された場合:**

```python
# jgaap.py の _PL_MAPPINGS 内:
# Before:
ConceptMapping("NetSales", CK.REVENUE, _PL),
# After:
ConceptMapping("Revenue", CK.REVENUE, _PL),
#               ^^^^^^^^ concept だけ変更。CK 定数は不変
```

**新 concept が追加された場合:**

```python
# 1. canonical_keys.py に CK 定数を追加
class CK(StrEnum):
    # --- PL ---
    NEW_CONCEPT = "new_concept"  # 追加

# 2. jgaap.py or ifrs.py のマッピングに追加
IFRSConceptMapping(
    "NewConceptIFRS",
    CK.NEW_CONCEPT,
    StatementType.BALANCE_SHEET,
    jgaap_concept="NewConcept",
)
```

**業種モジュールでの追加:**

```python
# sector/banking.py の _PL_BANKING_MAPPINGS に追加:
SectorConceptMapping(
    concept="NewBankingConceptBNK",
    sector_key="new_banking_concept_bnk",
    industry_codes=_CODES,
    general_equivalent=CK.REVENUE,
),
```

### 自動追従するファイル（タクソノミ更新の影響を受けない）

| ファイル | 理由 |
|----------|------|
| `taxonomy/concept_sets.py` | Presentation Linkbase を毎回スキャンして動的導出。**自動追従** |
| `taxonomy/__init__.py` (TaxonomyResolver) | ラベルリンクベースを動的読み込み。**自動追従** |
| `standards/normalize.py` | statement_mappings へのファサード。自身に concept 名なし |
| `financial/extract.py` | 3 層信頼度モデル（summary → exact → normalized）で抽出。マッピングデータなし |
| `xbrl/statements.py` | normalize 経由で概念セットを取得。直接の concept 依存なし |
| `xbrl/parser.py` | XML 構造のパースのみ |
| `xbrl/_namespaces.py` | namespace URI をバージョン非依存の正規表現で処理 |
| `standards/detect.py` | DEI 値とモジュールグループ名で判定。バージョン非依存 |
| `xbrl/contexts.py`, `xbrl/units.py` | XML 構造解析のみ |
| `linkbase/*.py` | XML 構造のパースのみ |

### 二重管理の注意点

banking.py の `_COMMON_*` タプル（13件）は `jppfs_cor` の concept 名を使い、`jgaap.py` と同一の名称が重複定義されている。`jppfs_cor` の concept 名が変更された場合は **両方** を修正する必要がある。

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

## Wave 4 で達成された自動化

Wave 3 完了時点では、jgaap.py / ifrs.py / sector/*.py の各 ConceptMapping に 8〜10 フィールドがハードコードされていた。Wave 4 で以下のフィールドを削除し、自動パイプラインに接続した:

| フィールド | Wave 3 | Wave 4 後 | 代替パイプライン |
|---|---|---|---|
| `label_ja` | ハードコード | **削除済み** | TaxonomyResolver (`taxonomy/__init__.py`) |
| `label_en` | ハードコード | **削除済み** | TaxonomyResolver |
| `display_order` | ハードコード | **削除済み** | concept_sets の `ConceptEntry.order` |
| `period_type` | ハードコード | **削除済み** | どこからも参照されていなかった |
| `is_total` | ハードコード | **削除済み** | concept_sets の `preferredLabel` |
| `statement_type` (sector) | ハードコード | **削除済み** | concept_sets で分類 |
| `canonical_key` (sector) | 名前が misleading | `sector_key` にリネーム | — |

## 現在の保守コスト

```
タクソノミ年次更新（タクソノミ追従が必要なファイル）:
  summary_mappings.py      → Summary concept 名の変更追従（77件）
  statement_mappings.py    → PL/BS/CF concept 名の変更追従（~130件）
  canonical_keys.py        → 新 CK の追加のみ（年に 0〜数件）

タクソノミ追従不要（安定コード）:
  concept_sets             → 変更不要（Presentation Linkbase 動的導出）
  taxonomy/labels          → 変更不要（動的読み込み）
  normalize.py             → statement_mappings へのファサード
  extract.py               → 3 層信頼度モデル（ロジックのみ）

マスタデータ更新:
  edinet_code              → スクリプト実行
  fund_code                → スクリプト実行
  form_code                → 数年に一度
```

## usgaap.py の label_ja について

`usgaap.py` の `_SummaryConceptDef` には `label_ja` が残存している。これは US-GAAP が BLOCK_ONLY（包括タグ付け）であり、`extract_usgaap_summary()` → `USGAAPSummaryItem` の専用パスを持つため。TaxonomyResolver パイプラインを経由しない設計上の制約により、Wave 4 の自動化対象外とした。

---

# Part 4: 検証方法

## 1. 単体テスト

```bash
uv run pytest
```

concept 名の不一致はテストで検出できる（全マッピングの整合性テスト、クロスバリデーションテスト `test_sector_cross_validation.py` が存在）。

## 2. タクソノミ実在検証（`EDINET_TAXONOMY_ROOT` 必須）

```bash
EDINET_TAXONOMY_ROOT=/path/to/ALL_YYYYMMDD uv run pytest -m integration
```

| 対象 | テストファイル | テストクラス | 状態 |
|------|---------------|-------------|------|
| 業種別 (sector) | `test_sector_cross_validation.py` | `TestSectorConceptExistence` (T16) | 実装済み |
| 一般事業 (jgaap) | `test_standards_jgaap.py` | `TestTaxonomyExistence` | 実装済み |
| IFRS | `test_standards_ifrs.py` | `TestTaxonomyExistence` | 実装済み |

Presentation Linkbase + XSD の2段階フォールバックで全 concept 名の実在を検証する。`EDINET_TAXONOMY_ROOT` 未設定時はスキップ。

## 3. クロスバリデーション

| 検証内容 | テスト |
|---|---|
| sector の `general_equivalent` が jgaap の canonical_key に存在 | `test_sector_cross_validation.py` T06-T10 |
| ifrs の `jgaap_concept` が jgaap レジストリに実在 | `ifrs.py` `_validate_registry()` （モジュールロード時） |
| `_JGAAP_ONLY_CONCEPTS` が jgaap に実在 | `test_standards_ifrs.py` `TestJGAAPOnlyConcepts` |
| CK が jgaap ∪ ifrs の canonical_key と過不足なし | `test_canonical_keys.py` test_t12 |
| US-GAAP の `key` が CK に存在し label_en が大文字始まり | `test_standards_usgaap.py` `TestCanonicalKeyAndReverseLookup` |

## 4. lint + スタブ

```bash
uv run ruff check src tests
uv run stubgen src/edinet --include-docstrings -o stubs
```


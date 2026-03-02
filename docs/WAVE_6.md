# Wave 6: Tier A 実装計画

> **作成日**: 2026-03-02
> **前提**: Wave 1–5 完了、Tier S 実装済み
> **目的**: Company API + キャッシュ + バリデーション。edgartools 的 UX

---

## 0. 工数見積もり（Wave 5 / Tier S との比較）

### 基準値: Wave 5（完了済み）と Tier S（完了済み）

| | Wave 5 | Tier S (6件) |
|---|---|---|
| **性質** | リファクタリング（既存コード大幅削減） | 新規機能（既存基盤の薄いラッパー） |
| **ソース変更** | ~3,500行削減 + ~230行追加 | ~550行新規 |
| **テスト** | 44ケース | ~40ケース |
| **難易度** | 高（回帰リスク大、12ファイル横断） | 低〜中（新規追加が主） |
| **セッション数目安** | 2〜3セッション | 1〜2セッション |

### Tier A (8件) 個別見積もり

| # | 機能 | 既存基盤 | 新規ソース | 新規テスト | 難易度 |
|---|------|---------|-----------|-----------|--------|
| 7 | **company/lookup** | `company.py`(172行) + `edinet_code.py`(168K行 静的レジストリ) 既存 | ~200-350行 | ~300-400行 | 中（名寄せ・ファジー検索） |
| 8 | **company/filings** | `Company.get_filings()` **既に存在** | ~100-150行（拡張） | ~200-300行 | 低 |
| 9 | **company/latest** | `Company.latest()` **既に存在** | ~50-80行（拡張） | ~100-150行 | 低 |
| 10 | **cache** | なし（完全新規） | ~350-500行 | ~400-600行 | 中（キャッシュ無効化、パス管理） |
| 11 | **revision_chain** | `Filing.parent_doc_id` 既存 | ~200-350行 | ~300-500行 | 中（チェーン走査のエッジケース） |
| 12 | **custom_detection** | `_namespaces.py` 既存 | ~150-250行 | ~200-400行 | 低〜中 |
| 13 | **validation/calc_check** | `CalculationLinkbase` **完全実装済み**（473行、tree走査API完備） | ~300-500行 | ~500-800行 | 中〜高（丸め誤差の仕様理解） |
| 14 | **fiscal_year** | `contexts.py` の Period 既存 | ~100-150行 | ~200-300行 | 低 |

### Tier A 合計

| | Tier A (8件) | 対 Tier S 比 | 対 Wave 4 比 |
|---|---|---|---|
| **新規ソース** | ~1,450-2,330行 | **2.6〜4.2倍** | 新規行数では10倍だが性質が異なる |
| **新規テスト** | ~2,200-3,450行 | **4〜6倍** | テスト数では1.5〜2倍 |
| **合計行数** | ~3,650-5,780行 | **3.5〜5.5倍** | ほぼ同等 |
| **セッション数目安** | **3〜5セッション** | 2〜3倍 | 1.5〜2倍 |

### 重要な発見: Company API は部分実装済み

`company.py` (172行) に既に以下が存在する:
- `Company.from_filing()`
- `Company.get_filings(date, doc_type)`
- `Company.latest(doc_type)`

つまり **#8 company/filings と #9 company/latest は拡張レベル**であり、#7 company/lookup が本丸（EDINET コードレジストリからの検索インターフェース構築）。

### 難易度の山

| 山 | 件名 | 理由 |
|---|---|---|
| **最大** | #13 validation/calc_check | `CalculationLinkbase` は完成しているが、Fact との突合ロジック（decimals/precision の丸め処理、weight=±1 の加算検証）は仕様理解が必要 |
| **中** | #10 cache | 完全新規モジュール。キャッシュ無効化・容量管理・並行アクセスなど設計判断が多い |
| **中** | #7 company/lookup | 名前の名寄せ（「トヨタ」→「トヨタ自動車」）の精度と、168K行のレジストリからの効率的検索 |
| **軽** | #8, #9, #14 | 既存基盤の薄いラッパー |

### まとめ

```
Tier S (6件) ≈ 1-2 セッション  ← 基準
Wave 4 (4Part) ≈ 2-3 セッション  ← リファクタ難易度で重い
Tier A (8件) ≈ 3-5 セッション  ← 件数は多いが既存基盤が充実
```

Tier A は **Tier S の約 3〜4 倍、Wave 4 の約 1.5〜2 倍** の工数感。ただし Tier A はほぼ全て「新規追加」なので回帰リスクが低く、**並列実装しやすい**（company 系 3件、cache+revision 2件、taxonomy/validation 2件、fiscal_year 1件 の 4 レーンに分割可能）という利点がある。

---

## 1. Tier A 調査必要度ランキング（ハルシネーション防止順）

| 順位 | 機能 | 調査必要度 | 理由 |
|:---:|------|:---:|------|
| **1** | **validation/calc_check** | ★★★★★ | XBRL計算バリデーション仕様（`decimals` の丸めルール、`weight=±1` の加算検証、`"INF"` 精度の扱い）が**仕様書ベースで確認必須**。間違えると静かに不正な検証結果を出す。docs/QAs/C-7.q.md 要精読 |
| **2** | **taxonomy/custom_detection** | ★★★★☆ | `is_standard` フラグ自体は `namespace_uri` で判定可能（**基盤済み**）。しかし `shadowing_target`（非標準科目が上書きする標準科目の推定）は **definition linkbase の wider-narrower arcrole 走査**が必要で仕様理解が不十分だと壊れる |
| **3** | **revision_chain** | ★★★☆☆ | `parent_doc_id` の意味論（原本を指すのか直前の訂正を指すのか）、複数回訂正・取下げのエッジケース、API の返却順序を **実データで確認**する必要あり |
| **4** | **cache** | ★★★☆☆ | 完全新規モジュール。キャッシュキー戦略（`doc_id + file_type`）、無効化ポリシー、並行アクセス、容量管理など**設計判断が多い**。EDINET API のレスポンスヘッダ（ETag等）の実調査が必要 |
| **5** | **company/lookup** | ★★☆☆☆ | データは `edinet_code.py`（168K行）に**全て存在**。`get_edinet_code()` と `all_edinet_codes()` も実装済み。名前検索のマッチング方式（部分一致 vs 読み仮名 vs ファジー）の**設計判断**のみ |
| **6** | **dimensions/fiscal_year** | ★☆☆☆☆ | DEI に全フィールド揃っている（`current_fiscal_year_start_date`, `current_period_end_date`, `type_of_current_period`）。期間長の計算だけ。**調査不要、即実装可能** |
| — | ~~company/filings~~ | — | **実装済み**（`Company.get_filings()` が本番稼働中） |
| — | ~~company/latest~~ | — | **実装済み**（`Company.latest()` が本番稼働中） |

---

## 2. Tier A 全体前提条件の充足状況

| 前提条件 | 状態 | 詳細 |
|---------|:---:|------|
| **CalculationLinkbase** | ✅ 完了 | `calculation.py` 473行。`CalculationArc`(weight=±1), `CalculationTree`(roots), O(1)インデックス、`ancestors_of()` 循環検出付き |
| **NamespaceInfo / classify_namespace()** | ✅ 完了 | `_namespaces.py`。LRU キャッシュ付き。`is_standard`, `module_name`, `module_group`, `edinet_code` 全て抽出可能 |
| **LineItem.namespace_uri** | ✅ 完了 | `RawFact` → `LineItem` で `namespace_uri` が保持される。`is_standard_taxonomy(item.namespace_uri)` で即判定可能 |
| **DEI 全フィールド** | ✅ 完了 | 27フィールド。fiscal_year_start, period_end, type_of_current_period, amendment_flag 等全て抽出済み |
| **Filing.parent_doc_id** | ✅ 完了 | API レスポンスから `parentDocID` が `Filing` モデルに格納済み |
| **DocType.is_correction / _CORRECTION_MAP** | ✅ 完了 | 訂正報告書の意味論的判定が可能 |
| **Company モデル** | ✅ 完了 | `get_filings()`, `latest()`, `from_filing()` 全て稼働中 |
| **EdinetCodeEntry レジストリ** | ✅ 完了 | `get_edinet_code(code)` O(1) + `all_edinet_codes()` 全件取得。13フィールド（名前、読み、業種、証券コード等） |
| **PeriodClassification** | ✅ 完了 | `period_variants.py` 82行。DEI → 当期/前期 の Duration/Instant 分類 |
| **DefinitionLinkbase** | ✅ 完了 | `definition.py` で wider-narrower / dimension-domain 等パース済み |
| **Filing._zip_cache / _xbrl_cache** | ✅ 完了 | インスタンスレベルのインメモリキャッシュは既存（永続キャッシュは未実装） |
| **Taxonomy pickle キャッシュ** | ✅ 完了 | `platformdirs.user_cache_dir("edinet")` に永続化。パターンとして参考可能 |

**結論: Tier A の全体前提条件は 100% 充足している。新規で基盤を作る必要はない。**

---

## 3. Tier A 間の依存関係 & 並列実装の衝突分析

### 依存グラフ

```
company/lookup ──────────────────────── 独立（company.py のみ）
cache ───────────────────────────────── 独立（_config.py + 新規 cache.py）
revision_chain ──────────────────────── 独立（filing.py + 新規モジュール）
taxonomy/custom_detection ──┐
                            ├── facts.py を共有修正する可能性
validation/calc_check ──────┘
dimensions/fiscal_year ──────────────── 独立（dimensions/ 内で完結）
```

### ファイル衝突マトリクス

| 変更対象ファイル | company | cache | revision | custom_det | calc_check | fiscal_year | **衝突** |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `models/company.py` | **M** | | | | | | — |
| `models/edinet_code.py` | **M** | | | | | | — |
| `_config.py` | | **M** | | | | | — |
| `api/download.py` | | **M** | | | | | — |
| `models/filing.py` | | | **M** | | | | — |
| `xbrl/_namespaces.py` | | | | **M** | | | — |
| `xbrl/facts.py` | | | | **M?** | **M?** | | **衝突リスク** |
| `xbrl/linkbase/calculation.py` | | | | | R | | — |
| `xbrl/linkbase/definition.py` | | | | R | | R | — |
| `dimensions/period_variants.py` | | | | | | **M** | — |
| 新規: `api/cache.py` | | **C** | | | | | — |
| 新規: `models/revision.py` | | | **C** | | | | — |
| 新規: `xbrl/taxonomy/custom.py` | | | | **C** | | | — |
| 新規: `xbrl/validation/` | | | | | **C** | | — |
| 新規: `dimensions/fiscal_year.py` | | | | | | **C** | — |

**M**=変更 **C**=新規作成 **R**=読み取りのみ

### 唯一の衝突ポイント: `facts.py` (LineItem)

| 機能 | facts.py への変更内容 |
|------|---------------------|
| custom_detection | LineItem に `is_standard: bool` フィールド追加の可能性 |
| calc_check | LineItem を読むだけ（フィールド追加なし）→ **実は衝突しない** |

**精査結果**: `calc_check` は LineItem の `value`, `decimals`, `local_name`, `context_id` を**読むだけ**で、フィールド追加は不要。`custom_detection` も `is_standard` は LineItem に追加せず**外部関数** `is_standard_taxonomy(item.namespace_uri)` で判定可能（既に実装済み）。

`shadowing_target` だけが LineItem 拡張の候補だが、これも別の `CustomDetectionResult` データクラスとして返せば LineItem を触らない。

### 結論: 全 6 機能が並列実装可能

```
Lane A: company/lookup         → models/company.py, models/edinet_code.py
Lane B: cache                  → _config.py, api/download.py, 新規 api/cache.py
Lane C: revision_chain         → models/filing.py, 新規 models/revision.py
Lane D: taxonomy/custom_detect → 新規 xbrl/taxonomy/custom.py（既存は読み取りのみ）
Lane E: validation/calc_check  → 新規 xbrl/validation/calc_check.py（既存は読み取りのみ）
Lane F: dimensions/fiscal_year → 新規 dimensions/fiscal_year.py, period_variants.py 拡張
```

**`__init__.py` は全レーン共通だが、Wave 4 と同じく統合タスクで一括更新すればゼロ衝突。**

---

## 4. 既存実装の詳細調査結果

### 4.1 Company モジュール（company/lookup の基盤）

#### Company モデル (`src/edinet/models/company.py`, 172行)

**既に実装済み:**
- `Company(BaseModel)` — Pydantic frozen config
- フィールド: `edinet_code: str`, `name_ja: str | None`, `sec_code: str | None`
- `ticker: str | None` — `sec_code` の先頭4桁を抽出する computed property
- `from_filing(filing: Filing) -> Company | None` — Filing から Company 構築
- `get_filings()` — **本番稼働中**。`edinet.documents()` API を edinet_code フィルタで呼び出し
- `latest()` — **本番稼働中**。`get_filings()` + doc_type フィルタ + submit_date_time の max

#### EdinetCode レジストリ (`src/edinet/models/edinet_code.py`)

**既に実装済み:**
- `EdinetCodeEntry(BaseModel)` — 13フィールド:
  - `edinet_code`, `submitter_type`, `listing_status`, `consolidated`
  - `capital_million_yen`, `fiscal_year_end`, `submitter_name`, `submitter_name_en`, `submitter_name_yomi`
  - `address`, `industry`, `sec_code`, `corporate_number`
- `_EDINET_CODE_TABLE: dict[str, EdinetCodeEntry]` — 自動生成済み O(1) ルックアップ
- `get_edinet_code(code: str) -> EdinetCodeEntry | None` — 実装済み
- `all_edinet_codes() -> list[EdinetCodeEntry]` — 実装済み

**company/lookup で未実装:**
- 名前検索（部分一致/読み仮名）
- 証券コード検索
- 業種別検索
- ファジーマッチング

#### Filing モデル (`src/edinet/models/filing.py`)

**revision_chain 関連フィールド（既に存在）:**
- `parent_doc_id: str | None` (L225) — API の `parentDocID` から取得
- `company: Company | None` プロパティ (L288-292) — `Company.from_filing()` 経由

### 4.2 キャッシュ基盤

**現状:**
- `Filing._zip_cache: bytes | None` — インスタンスレベルのインメモリキャッシュ
- `Filing._xbrl_cache: tuple[str, bytes] | None` — 同上
- `Filing.fetch(refresh=False)` — `_xbrl_cache` があれば再ダウンロードしない
- `Filing.clear_fetch_cache()` — キャッシュクリア

**永続キャッシュの参考パターン:**
- `TaxonomyResolver` が `platformdirs.user_cache_dir("edinet")` に pickle で永続化
- `concept_sets.py` も同様の pickle キャッシュ

**未実装:**
- `_config.py` に `cache_dir` 設定なし
- ダウンロード ZIP の永続キャッシュなし
- HTTP レベルキャッシュ（ETag/If-Modified-Since）なし

### 4.3 バリデーション基盤

#### CalculationLinkbase (`src/edinet/xbrl/linkbase/calculation.py`, 473行)

```python
@dataclass(frozen=True, slots=True)
class CalculationArc:
    parent: str                      # 親概念ローカル名
    child: str                       # 子概念ローカル名
    parent_href: str                 # xlink:href（デバッグ用）
    child_href: str                  # xlink:href（デバッグ用）
    weight: Literal[1, -1]           # 加算方向: 1=加算, -1=減算
    order: float                     # 兄弟間の表示順序
    role_uri: str                    # 所属 role URI

@dataclass(frozen=True, slots=True)
class CalculationTree:
    role_uri: str
    arcs: tuple[CalculationArc, ...]
    roots: tuple[str, ...]           # 親を持たない概念（合計項目）

@dataclass(frozen=True, slots=True)
class CalculationLinkbase:
    source_path: str | None
    trees: dict[str, CalculationTree]
    # 内部インデックス: O(1) lookup
    _children_index: dict[tuple[str, str], tuple[CalculationArc, ...]]
    _parent_index: dict[tuple[str, str], tuple[CalculationArc, ...]]
```

**利用可能 API:**
- `children_of(parent, role_uri=None)` → 子の CalculationArc タプル（order ソート済み）
- `parent_of(child, role_uri=None)` → 親の CalculationArc タプル
- `ancestors_of(concept, role_uri)` → ルートまでの祖先（循環検出付き）
- `role_uris` プロパティ → 全 role URI
- `get_tree(role_uri)` → CalculationTree

### 4.4 名前空間分類基盤

#### NamespaceInfo (`src/edinet/xbrl/_namespaces.py`)

```python
@dataclass(frozen=True, slots=True)
class NamespaceInfo:
    uri: str
    category: NamespaceCategory      # STANDARD_TAXONOMY | FILER_TAXONOMY | XBRL_INFRASTRUCTURE | OTHER
    is_standard: bool                # True only if STANDARD_TAXONOMY
    module_name: str | None          # e.g., "jppfs_cor"
    module_group: str | None         # e.g., "jppfs"
    taxonomy_version: str | None     # e.g., "2025-11-01"
    edinet_code: str | None          # e.g., "E02144" (FILER only)
```

**利用可能 API:**
- `classify_namespace(uri) -> NamespaceInfo` — LRU キャッシュ付き
- `is_standard_taxonomy(uri) -> bool`
- `is_filer_namespace(uri) -> bool`
- `extract_taxonomy_module(uri) -> str | None`

### 4.5 DEI / Period 基盤

**DEI (`src/edinet/xbrl/dei.py`):** 27フィールド完全抽出
- fiscal_year 判定に必要: `current_fiscal_year_start_date`, `current_period_end_date`, `type_of_current_period` ("FY"/"HY"), `current_fiscal_year_end_date`
- revision 判定に必要: `amendment_flag`, `number_of_submission`, `identification_of_document_subject_to_amendment`

**Period 型 (`src/edinet/xbrl/contexts.py`):**
- `InstantPeriod(instant: date)`
- `DurationPeriod(start_date: date, end_date: date)`
- `Period = InstantPeriod | DurationPeriod`

**PeriodClassification (`src/edinet/xbrl/dimensions/period_variants.py`, 82行):**
- `current_duration`, `prior_duration`, `current_instant`, `prior_instant`
- `classify_periods(dei: DEI) -> PeriodClassification`

---

## 5. 総合まとめ

| 観点 | 結果 |
|------|------|
| **Tier A 実質件数** | 8件中 **2件が実装済み** → **実質 6件** |
| **前提条件** | **100% 充足**（新規基盤構築の必要なし） |
| **調査が最も必要** | #13 calc_check（XBRL仕様の丸めルール）、#12 custom_detection（shadowing_target） |
| **即実装可能** | #14 fiscal_year、#7 company/lookup |
| **並列可能性** | **6レーン完全並列可能**（ファイル衝突ゼロ、`__init__.py` は統合タスクに委任） |

---

## 6. 事前準備作業・統合作業・API 非対称性リスク

### 6.1 並列実装開始前の事前準備作業

J-GAAP/IFRS/US-GAAP 並列実装時に発生した非対称性問題を防ぐため、**事前に API 設計規約を策定する必要がある**。

#### 現存する非対称性

現状のコードベースに既に非対称性が存在しており、6レーンがこれを参照して自由にやると悪化する:

| 現存する非対称性 | 例 |
|---|---|
| **return 型がバラバラ** | `Company.latest()` → `Filing | None`（Noneで返す）vs `Filing.fetch()` → `tuple[str, bytes]`（例外で落ちる） |
| **factory 命名がバラバラ** | `build_line_items()` vs `extract_dei()` vs `structure_units()` vs `classify_periods()` |
| **エラー戦略がバラバラ** | `build_line_items()` → raise / `build_statements()` → 空を返す / `documents()` → warning + skip |
| **Pydantic vs dataclass** | `Filing`, `Company` = Pydantic frozen / `LineItem`, `Period` = dataclass frozen |

#### 事前に決めるべき 5 項目

| # | 決定事項 | 影響するレーン | 理由 |
|---|---------|-------------|------|
| **D1** | **ValidationResult 型の定義** | calc_check, (将来の validation/* 全て) | calc_check が `list[ValidationError]` / `CalcCheckResult` / `bool` のどれを返すかで後続の全バリデーション機能の API が決まる |
| **D2** | **キャッシュの透過性** | cache, revision_chain | 透過的（`fetch()` が自動キャッシュ）vs 明示的（`fetch(use_cache=True)`）で revision_chain のキャッシュキー設計が変わる。**キャッシュキー = `doc_id` だけだと訂正前/後で衝突** |
| **D3** | **LineItem 拡張ポリシー** | custom_detection, (calc_check, fiscal_year) | `is_standard` を LineItem に足すか外部関数にするかの判断。足すと前例ができて他レーンも足したがる → God Object 化 |
| **D4** | **メソッド配置規約** | 全レーン | instance method（`filing.revisions()`）vs standalone function（`edinet.validate(statements)`）vs クラス（`Validator(statements).run()`）の使い分けルール |
| **D5** | **命名規約の統一** | 全レーン | `get_*` = lookup (Optional返却) / `build_*` = 構築 (raise) / `classify_*` = 分類 / `validate_*` = 検証 の辞書を決める |

### 6.2 統合作業

Wave 4 と同じパターンで以下が必要。

| # | 統合作業 | タイミング |
|---|---------|---------|
| I1 | `__init__.py` 一括更新（全レーンの新規 export を集約） | 全レーン完了後 |
| I2 | `uv run stubgen` でスタブ再生成 | I1 の後 |
| I3 | API 一貫性テスト（命名規約・return 型・error 戦略が規約通りか） | I2 の後 |
| I4 | cross-feature 統合テスト（cache × revision_chain、custom_detection × calc_check） | I3 の後 |
| I5 | `uv run ruff check src tests` | 最後 |

### 6.3 API 非対称性リスク（具体的な衝突シナリオ）

#### Risk 1: `latest()` の衝突（company × revision_chain）

```python
# company/latest（既に実装済み）
company.latest("有報")  # → Filing | None（見つからなければ None）

# revision_chain が追加する latest()
filing.latest()  # → Filing（最終訂正版）
# ↑ こっちは「必ず存在する」（自分自身が最終版の場合は自分を返す）
# → None を返す必要がない
# → 同じ名前 latest() なのに return 型が Filing | None vs Filing で非対称
```

#### Risk 2: キャッシュキーと訂正チェーン

```python
# cache が doc_id をキーにする場合:
filing_original.fetch()   # cache["S100ABC0"] = original.zip
filing_corrected.fetch()  # cache["S100ABC1"] = corrected.zip  ← OK、別ID

# しかし revision_chain で原本を辿る時:
chain = filing_corrected.revisions()
# chain[0].doc_id == "S100ABC0"（原本）
# chain[0].fetch() → キャッシュヒット ← これは正しい

# 問題: EDINET API は同一 doc_id で内容が更新される場合がある？
# → 要実データ確認（D2 の決定事項）
```

#### Risk 3: LineItem の God Object 化

```python
# 各レーンが独立に LineItem にフィールドを足したがる:
@dataclass(frozen=True, slots=True)
class LineItem:
    # 既存 17 フィールド
    concept: str
    namespace_uri: str
    local_name: str
    ...

    # custom_detection が足したい
    is_standard: bool              # ← Lane D
    shadowing_target: str | None   # ← Lane D

    # fiscal_year が足したい
    fiscal_year_type: str | None   # ← Lane F

    # calc_check が足したい
    calc_status: str | None        # ← Lane E

# → 17 → 21 フィールド、frozen dataclass なので再構築コスト増
# → 解決策: LineItem は触らず、外部 detector/validator パターンに統一
```

#### Risk 4: validate 系の return 型分裂

```python
# calc_check が先に実装:
statements.validate_calculations()  # → list[CalcError]

# 将来の required_items 検証:
statements.validate_required()      # → bool（ある/なしの判定だけ）

# 将来の footnote 検証:
validate_footnotes(statements)      # → dict[str, list[str]]（standalone function）

# → 3つの validate 系が全部違う return 型 & 配置
```

#### Risk 5: fiscal_year と period_variants の責任境界

```python
# period_variants.py（既存）:
classify_periods(dei)  # → PeriodClassification（当期/前期の分類）

# fiscal_year（新規）:
detect_fiscal_year(dei)  # → FiscalYearInfo（変則決算の判定）

# ↑ 両方とも DEI を入力にして期間メタデータを返す
# → ユーザーから見ると「なぜ 2 つの関数が必要？」
# → PeriodClassification に fiscal_year 情報を統合すべきか、別モジュールか？
```

### 6.4 DEFACTO.md の決定事項（Step 0 に組み込む）

docs/DEFACTO.md での議論により以下が確定済み。D1〜D5 の設計規約に反映すること。

#### DEFACTO-1: `doctypes/` は作らない（DEFACTO.md §5-2, §6）

書類タイプ固有の型付きオブジェクト（`LargeHolding` 等）は保守コストに見合わないため作らない。
全 27 書類タイプは汎用パイプライン（`stmts["ラベル名"]` / `stmts.search("キーワード")`）でアクセスする。

**D3 への影響**: LineItem にフィールドを追加しない方針が確定。`is_standard` / `shadowing_target` / `fiscal_year_type` は全て外部関数パターンで実装する。

#### DEFACTO-2: `Statements` に dict-like プロトコル追加（DEFACTO.md §6-2）

`Statements` に `__getitem__` / `get()` / `__contains__` / `__iter__` / `__len__` / `search()` を追加する。
`FinancialStatement` に既にある dict-like プロトコル（L160-214）と同じインターフェース。
3 つのキーで完全一致: `label_ja.text` / `label_en.text` / `local_name`。
`search()` は部分一致（探索用）。

**D4 への影響**: `Statements` は全書類タイプの汎用アクセスの核になる。
Wave 6 の全レーンと衝突しないため、並列実装と独立して追加可能（数十行）。

#### DEFACTO-3: フォルダ restructure は Wave 6 後（DEFACTO.md §5-4）

```
xbrl/statements.py      → financial/statements.py
xbrl/standards/          → financial/standards/
xbrl/sector/             → financial/sector/
xbrl/dimensions/         → financial/dimensions/
```

Wave 6 では現構造のまま実装する。restructure で移動するファイルに新規コードを追加する場合は
将来の `financial/` 配置を意識し、`xbrl/` 固有の機能（パース、名前空間解決等）への依存を
最小限に留める。

#### DEFACTO-4: 保守コスト増加なし（DEFACTO.md §8-4b）

Wave 6 の全機能は MAINTENANCE.md の既存保守カテゴリに収まる。
新しい保守カテゴリの追加はない。

### 6.5 推奨アクション

```
Step 0: 事前準備
         - D1〜D5 の設計規約を策定
         - DEFACTO-1〜4 を規約に組み込む
         - DEFACTO-2 の Statements dict-like プロトコルを先行実装（全レーンと独立）
         ↓
Step 1: 6 レーン並列実装（各レーンは規約 + DEFACTO 決定事項を参照）
         ↓
Step 2: 統合作業（I1〜I5）
```

**Step 0 をスキップすると J-GAAP/IFRS/US-GAAP の時と同じ問題が起きる。** D1〜D5 + DEFACTO-1〜4 を先に決めてから並列開始すべき。

# step 0の決定事項

> **決定日**: 2026-03-03
> **前提**: DEFACTO-1〜4 を組み込み済み

---

## D1: ValidationResult 型の定義

**決定**: 構造化された結果 dataclass を返す。`bool` や `list[str]` は使わない。

### 共通パターン

```python
@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """個別の検証不一致。"""
    role_uri: str                           # 所属 role URI
    parent_concept: str                     # 親概念（ローカル名）
    expected: Decimal                       # 計算上の期待値
    actual: Decimal                         # 実際の Fact 値
    difference: Decimal                     # |expected - actual|
    tolerance: Decimal                      # decimals ベースの許容誤差
    severity: Literal["error", "warning"]   # tolerance 超過=error, tolerance 内=warning
    message: str                            # 人間向けメッセージ（日本語）

@dataclass(frozen=True, slots=True)
class CalcValidationResult:
    """計算リンクベース検証の結果。"""
    issues: tuple[ValidationIssue, ...]
    checked_count: int        # 検証した親科目の数
    passed_count: int         # 一致した親科目の数
    skipped_count: int        # Fact 不足でスキップした数

    @property
    def is_valid(self) -> bool:
        """error がゼロなら True。"""
        return all(i.severity != "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")
```

### 根拠

- `bool` は情報不足（どこが不一致か分からない）
- `list[str]` は型安全でない
- 構造化された結果により、利用者が severity でフィルタリング可能
- `checked_count` / `skipped_count` で検証の網羅度が分かる
- 将来の `validate_required()` 等も同様のパターンで `RequiredValidationResult` を定義

### Risk 4 の解決

全 `validate_*` 関数は `*ValidationResult` dataclass を返す。配置は standalone 関数に統一。

```python
# 統一された validate API
validate_calculations(fs, calc_linkbase) -> CalcValidationResult
# 将来:
# validate_required(fs, concept_set)  -> RequiredValidationResult
# validate_footnotes(fs)              -> FootnoteValidationResult
```

---

## D2: キャッシュの透過性

**決定**: **透過的キャッシュ**（`fetch()` が自動的にディスクキャッシュを使用）。

### API 設計

```python
# 有効化（デフォルト: 無効 = cache_dir=None）
edinet.configure(cache_dir="~/.cache/edinet")

# 透過的に動作
filing.fetch()              # 1回目: ダウンロード → ディスク保存 → 返却
filing.fetch()              # 2回目: ディスクから読み込み → 返却
filing.fetch(refresh=True)  # 強制再ダウンロード → ディスク上書き → 返却

# キャッシュ全削除
edinet.clear_cache()
```

### キャッシュキー

`doc_id`（安全。G-7.a.md で確認済み: 訂正報告書は常に新しい doc_id が付与される。同一 doc_id の内容更新はない）

### キャッシュ構造

```
{cache_dir}/
  downloads/
    {doc_id}.zip          # ZIP 全体
```

### 設計判断

| 項目 | 決定 | 理由 |
|------|------|------|
| TTL | なし | EDINET の開示書類は不変。取下げは `withdrawal_status` で判定 |
| デフォルト | 無効 (`cache_dir=None`) | 明示的に opt-in |
| 並行アクセス | ファイルロック不要 | 同一 doc_id は冪等、tempfile + rename で原子性保証 |
| 容量管理 | v0.1.0 ではユーザー責任 | 将来的に LRU eviction を検討 |

### Risk 2 の解決

キャッシュキー = `doc_id` は安全。訂正報告書は別の `doc_id` を持つ（G-7.a.md）。`revision_chain` がキャッシュに影響することはない。

---

## D3: LineItem 拡張ポリシー

**決定**: **LineItem にフィールドを追加しない**。外部関数パターンで統一。

### パターン

```python
# NG: LineItem にフィールド追加（God Object 化リスク）
item.is_standard
item.shadowing_target
item.fiscal_year_type
item.calc_status

# OK: 既存の外部関数（実装済み）
from edinet.xbrl._namespaces import is_standard_taxonomy
is_standard_taxonomy(item.namespace_uri)

# OK: 分析結果は別の dataclass で返す
from edinet.xbrl.taxonomy.custom import detect_custom_items
result: CustomDetectionResult = detect_custom_items(statements)
```

### 根拠

- DEFACTO-1（`doctypes/` は作らない）と整合
- LineItem は XBRL Fact の忠実な表現に徹する（17フィールド固定）
- 分析・分類・検証の結果は全て外部 dataclass で返す
- frozen dataclass の再構築コスト増加を防止

### Risk 3 の解決

全レーンが LineItem を触らず、外部 detector/validator パターンに統一。

---

## D4: メソッド配置規約

| パターン | 配置 | 例 | 判定基準 |
|---------|------|-----|---------|
| **エンティティ操作** | インスタンスメソッド | `company.get_filings()`, `company.latest()` | 主語が明確なエンティティ |
| **型のコンストラクタ** | クラスメソッド | `Company.from_filing()`, `Company.search("トヨタ")` | 型のファクトリ |
| **データ分析** | standalone 関数 | `validate_calculations(fs, calc_linkbase)` | 複数の入力を組み合わせる |
| **データ変換** | standalone 関数 | `detect_custom_items(statements)` | 変換・検出の入出力が別型 |
| **メタデータ取得** | プロパティ | `statements.period_classification` | 単一属性の派生値 |
| **訂正チェーン構築** | standalone 関数 | `build_revision_chain(filing)` | API 呼び出しを伴う処理は standalone が適切 |

### Risk 1 の解決

```python
# company/latest（既存 — Filing | None を返す。見つからない場合がある）
company.latest("有報")  # → Filing | None

# revision_chain（standalone 関数 — RevisionChain を返す。自分自身が原本でも動作）
build_revision_chain(filing)  # → RevisionChain（.latest は Filing を返す、常に存在）
```

`latest` という名前が衝突しない。`Company.latest()` はクエリ結果、`RevisionChain.latest` はチェーン末端。

### Risk 5 の解決

```python
# period_variants（既存）: 当期/前期の分類 → PeriodClassification
classify_periods(dei)

# fiscal_year（新規）: 決算期の構造化 → FiscalYearInfo
detect_fiscal_year(dei)

# 両者は責任が異なる:
# - classify_periods: コンテキスト選択に使用（BS/PL の当期/前期を決定）
# - detect_fiscal_year: メタデータ（変則決算か、決算月は何月か）
# → 別モジュールで正しい。統合は不要。
```

---

## D5: 命名規約の統一

| prefix | 意味 | return 型 | 既存例 | Wave 6 での使用 |
|--------|------|-----------|--------|----------------|
| `get_*` | O(1) lookup | `T \| None` | `get_edinet_code(code)` | `get_cache_path(doc_id)` |
| `search_*` | 部分一致探索 | `list[T]` | （新規） | `Company.search("トヨタ")` |
| `build_*` | 構築（raise 可） | `T` | `build_line_items(...)` | `build_revision_chain(filing)` |
| `extract_*` | 生データから抽出 | `T` | `extract_dei(facts)` | — |
| `classify_*` | 分類 | enum/dataclass | `classify_namespace(uri)` | — |
| `detect_*` | 発見・判定 | result dataclass | `detect_accounting_standard(facts)` | `detect_custom_items(stmts)`, `detect_fiscal_year(dei)` |
| `validate_*` | 検証 | `*ValidationResult` | （新規） | `validate_calculations(fs, calc)` |
| `resolve_*` | 曖昧→確定 | `T \| None` | `resolve_industry_code(dei)` | — |
| `clear_*` | 削除・リセット | `None` | `clear_fetch_cache()` | `clear_cache()` |

### 特記事項

- `from_*()` はクラスメソッドファクトリ専用（`Company.from_filing()`）
- `to_*()` はエクスポート専用（`to_dataframe()`, `to_csv()`）
- `is_*` / `has_*` は bool プロパティ/関数（`is_standard_taxonomy()`, `has_consolidated_data`）

---

## DEFACTO 決定事項の反映

| DEFACTO | D への影響 |
|---------|-----------|
| **DEFACTO-1** (doctypes/ なし) | → D3: LineItem にフィールド追加しない |
| **DEFACTO-2** (Statements dict-like) | → Step 0 で先行実装（全レーンと独立） |
| **DEFACTO-3** (restructure は Wave 6 後) | → 全レーンは現構造 (`xbrl/`) のまま実装 |
| **DEFACTO-4** (保守カテゴリ増加なし) | → 確認済み、特別な対応不要 |

---

## Wave 6 レーン別ファイル割り当て

| Lane | 機能 | 変更・作成するファイル |
|------|------|---------------------|
| L1 | company_lookup | `src/edinet/models/company.py` (変更), `src/edinet/models/edinet_code.py` (変更), `tests/test_models/test_company_lookup.py` (新規) |
| L2 | cache | `src/edinet/api/cache.py` (新規), `src/edinet/_config.py` (変更), `src/edinet/api/download.py` (変更), `src/edinet/models/filing.py` (変更), `tests/test_api/test_cache.py` (新規) |
| L3 | revision_chain | `src/edinet/models/revision.py` (新規), `tests/test_models/test_revision.py` (新規) |
| L4 | custom_detection | `src/edinet/xbrl/taxonomy/custom.py` (新規), `tests/test_xbrl/test_custom_detection.py` (新規), `tests/fixtures/custom_detection/` (新規) |
| L5 | calc_check | `src/edinet/xbrl/validation/calc_check.py` (新規), `tests/test_xbrl/test_calc_check.py` (新規), `tests/fixtures/calc_check/` (新規) |
| L6 | fiscal_year | `src/edinet/xbrl/dimensions/fiscal_year.py` (新規), `src/edinet/xbrl/dimensions/period_variants.py` (変更), `tests/test_xbrl/test_fiscal_year.py` (新規) |

### 衝突管理

- L2 と L3: 元計画では両方 `filing.py` を変更するが、**L3 は `revision.py` に standalone 関数 `build_revision_chain()` として実装**し `filing.py` を触らない。統合タスクで `Filing.revisions()` メソッドを追加。
- `__init__.py`: 全レーン共通で触らない。統合タスクで一括更新。
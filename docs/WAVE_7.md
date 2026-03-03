# Wave 7: Tier B + Tier C 実装計画

> **作成日**: 2026-03-03
> **前提**: Wave 1–6 完了（Tier S + Tier A + フォルダ restructure 済み）
> **目的**: v0.1.0 の完成。テキストブロック、セグメント、PDF、脚注、サマリー、diff 等

---

## 0. 概要

### 対 Wave 6（Tier A）との比較

| | Wave 6 (Tier A) | Wave 7 (Tier B+C) |
|---|---|---|
| **件数** | 6件（実質、2件は実装済み） | 12件 |
| **性質** | 既存基盤の拡張が主 | **ほぼ全て新規モジュール** |
| **新規ソース** | ~1,450-2,330行 | ~1,910-2,740行 |
| **ファイル衝突** | facts.py に軽微なリスク | **ゼロ**（全レーン独立） |
| **セッション数目安** | 3-5 | 3-5 |
| **難易度の山** | calc_check（XBRL仕様理解） | segments（提出者ごとの定義差異） |

### ベースライン

```
テスト: 1582 passed, 0 skipped (TAXONOMY_ROOT あり), 8 warnings
ruff: All checks passed
```

### 8 レーン構成

```
Lane 1: Text (B1+B2+B3)         → xbrl/text/ (新規パッケージ)
Lane 2: fetch_pdf (B8)          → models/filing.py + api/download.py
Lane 3: Footnotes (B9)          → xbrl/linkbase/footnotes.py (新規)
Lane 4: Analysis (B6+B7)        → financial/summary.py + financial/notes/ (新規)
Lane 5: Taxonomy (B5)           → xbrl/taxonomy/standard_mapping.py (新規)
Lane 6: Segments (B4)           → financial/dimensions/segments.py (新規)
Lane 7: Display (B10)           → display/html.py (新規)
Lane 8: Diff (C1+C2)            → financial/diff.py (新規)
```

### ファイル衝突マトリクス

| 変更対象 | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | 衝突 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `xbrl/text/` (新規) | **C** | | | | | | | | — |
| `models/filing.py` | | **M** | | | | | | | — |
| `api/download.py` | | **M** | | | | | | | — |
| `xbrl/linkbase/footnotes.py` (新規) | | | **C** | | | | | | — |
| `financial/summary.py` (新規) | | | | **C** | | | | | — |
| `financial/notes/` (新規) | | | | **C** | | | | | — |
| `xbrl/taxonomy/standard_mapping.py` (新規) | | | | | **C** | | | | — |
| `financial/dimensions/segments.py` (新規) | | | | | | **C** | | | — |
| `display/html.py` (新規) | | | | | | | **C** | | — |
| `financial/diff.py` (新規) | | | | | | | | **C** | — |
| `financial/statements.py` | | | | R | | R | R | R | 読み取りのみ |
| `xbrl/parser.py` | R | | R | | | | | | 読み取りのみ |

**C**=新規作成 **M**=変更 **R**=読み取りのみ

**結論: 全 8 レーンが完全並列可能。ファイル衝突ゼロ。**

### 依存関係グラフ

```
即開始可能（他レーンへの依存なし）:
  Lane 2: fetch_pdf          ← 最も簡単
  Lane 3: Footnotes          ← parser.py の既存基盤で独立
  Lane 4: Analysis           ← DEI + facts の集計のみ
  Lane 5: Taxonomy mapping   ← CalculationLinkbase 読み取りのみ
  Lane 8: Diff               ← Statements 読み取りのみ

レーン内チェーン（ステップ順序あり）:
  Lane 1: text_blocks → sections → clean

弱い依存（独立可能だが統合テスト推奨）:
  Lane 6: Segments           ← StructuredContext.dimensions 読み取り
  Lane 7: Display/HTML       ← Statements + DisplayRow 読み取り
```

### 難易度ランキング

| 難度 | レーン | 理由 |
|---|---|---|
| **最大** | Lane 6 (Segments) | 提出者ごとにセグメント定義が異なる。definition linkbase の dimension-domain 走査 + 提出者独自メンバーのラベル解決が必要 |
| **中** | Lane 1 (Text) | role URI のバリエーション。提出者固有の roleType 対応。HTML クリーニングの堅牢性 |
| **中** | Lane 8 (Diff) | 前期修正再表示のエッジケース。概念名照合の精度 |
| **軽** | Lane 2,3,4,5,7 | 既存基盤の薄いラッパーまたは集計 |

### 統合作業（全レーン完了後）

| # | 統合作業 | タイミング |
|---|---------|---------|
| I1 | `__init__.py` 一括更新（全レーンの新規 export を集約）+ `financial.py` L41 の TextBlock コメント更新 | 全レーン完了後 |
| I2 | `uv run stubgen` でスタブ再生成 | I1 の後 |
| I3 | cross-feature 統合テスト | I2 の後 |
| I4 | `uv run ruff check src tests` | 最後 |

---

## Lane 1 — Text: テキストブロック抽出 (B1 + B2 + B3)

### 位置づけ

DEFACTO.md §5-2 で定義された `xbrl/text/` パッケージ。XBRL の `textBlockItemType` Fact からセクション構造化テキストを抽出し、LLM 前処理用のクリーンテキスト変換を提供する。

### FEATURES.md 対応

- `text_blocks`: textBlockItemType タグの構造的抽出
- `text_blocks/sections`: `stmts.sections["事業等のリスク"]` によるセクション名アクセス
- `text_blocks/clean`: HTML → プレーンテキスト変換

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/text/__init__.py` | 新規 | パッケージ初期化 + re-export |
| `src/edinet/xbrl/text/blocks.py` | 新規 | `extract_text_blocks()`: textBlockItemType Fact の抽出 |
| `src/edinet/xbrl/text/sections.py` | 新規 | `TextSection`, role URI → セクション名マッピング |
| `src/edinet/xbrl/text/clean.py` | 新規 | `clean_html()`: HTML → プレーンテキスト変換 |
| `tests/test_xbrl/test_text_blocks.py` | 新規 | テスト |
| `tests/fixtures/text_blocks/` | 新規 | テストフィクスチャ |

### 既存基盤

- `RawFact.value_inner_xml`: HTML タグを含む原文が既に保持されている
- `financial.py` L41 コメント: 「TextBlock 等、v0.2.0 の text_blocks モジュールで対応予定」
- 689 個の `jpcrp_cor` テキストブロック概念（352 instant + 337 duration）
- parser.py が自動的に XML エスケープを解除済み

### 技術詳細

**TextBlock dataclass**:
```python
@dataclass(frozen=True, slots=True)
class TextBlock:
    concept: str              # ローカル名
    role_uri: str             # 所属 role URI
    section_name: str | None  # role URI から推定したセクション名
    html: str                 # 原文 HTML
    clean_text: str           # クリーンテキスト（lazy or eager）
    context_ref: str
    period: Period
```

**セクション名マッピング**: role URI の末尾から日本語セクション名を推定。提出者固有の roleType は filer_lab.xml のラベルを使用。

**対象セクション例**:
- 企業の概況（事業の内容）
- 事業等のリスク
- 経営者による財政状態…の分析（MD&A）
- コーポレートガバナンスの状況
- 経理の状況（注記事項）

**clean_html() の方針**: lxml の `tostring(method="text")` をベースに、テーブル構造をタブ/改行で保持。BeautifulSoup 非依存（lxml のみ）。

### QA 参照

| QA | 関連度 | 内容 |
|----|--------|------|
| A-9 | 直接 | TextBlock HTML コンテンツの取り扱い |
| I-1 | 直接 | Role URI とステートメントのマッピング |
| I-1b | 関連 | 提出者固有の roleType |
| J-3 | 関連 | 注記情報の構造 |

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~400-570行 |
| 新規テスト | ~300-500行 |
| 難易度 | 中 |
| セッション | 1-2 |

---

## Lane 2 — fetch_pdf: PDF ダウンロード (B8)

### 位置づけ

XBRL を含まない書類（有価証券通知書、届出取下げ等 8 種）向けの PDF ダウンロード。EDINET API の `type=2` エンドポイントを使用。

### FEATURES.md 対応

- `fetch_pdf`: `Filing.fetch_pdf()` メソッド

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/models/filing.py` | 変更 | `fetch_pdf()` / `afetch_pdf()` メソッド追加 |
| `src/edinet/api/download.py` | 変更 | PDF レスポンスの Content-Type 検証追加（軽微） |
| `tests/test_models/test_filing_pdf.py` | 新規 | テスト |

### 既存基盤

- `DownloadFileType.PDF = "2"`: download.py に既に定義済み
- `Filing.has_pdf: bool`: フィールド既に存在（L235-238）
- `download_document()` / `adownload_document()`: sync/async 両方既存
- `CacheStore`: cache.py に永続キャッシュ基盤あり（L103 に PDF 拡張コメントあり）

### 技術詳細

```python
def fetch_pdf(self, *, refresh: bool = False) -> bytes:
    """PDF バイト列を返す。has_pdf=False なら EdinetAPIError。"""
    if not self.has_pdf:
        raise EdinetAPIError(f"この書類には PDF がありません: {self.doc_id}")
    # 3層キャッシュ: _pdf_cache → disk → network
    ...
    return download_document(self.doc_id, file_type=DownloadFileType.PDF)
```

- **PDF は ZIP ではなく raw bytes** で返却される（`application/pdf`）
- PDF テキスト抽出はスコープ外（ユーザー責任）
- キャッシュキー: `{doc_id}_pdf` でディスクキャッシュ

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~80-100行 |
| 新規テスト | ~100-150行 |
| 難易度 | **最低** |
| セッション | 0.5 以下 |

---

## Lane 3 — Footnotes: 脚注リンク解析 (B9)

### 位置づけ

XBRL の `footnoteLink` 要素をパースし、Fact と脚注テキスト（※1, ※2 等）の紐付けを提供する。

### FEATURES.md 対応

- `footnotes`: Fact ↔ 脚注テキスト紐付け

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/linkbase/footnotes.py` | 新規 | `parse_footnote_links()`, `FootnoteLink`, `Footnote` |
| `tests/test_xbrl/test_footnotes.py` | 新規 | テスト |
| `tests/fixtures/footnotes/` | 新規 | テストフィクスチャ |

### 既存基盤

- `parser.py` L33: `_LINK_FOOTNOTELINK_TAG` 定数が既に定義
- Calculation/Presentation/Definition Linkbase のパースパターンが確立済み
- `_linkbase_utils.py`: `_XLINK_*` 定数群、共通ユーティリティ

### 技術詳細

**XML 構造** (A-5.a.md より):
```xml
<link:footnoteLink>
  <link:footnote xlink:label="fn1" xml:lang="ja">※1</link:footnote>
  <link:loc xlink:href="#IdFact1234" xlink:label="fact1"/>
  <link:footnoteArc xlink:from="fact1" xlink:to="fn1"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"/>
</link:footnoteLink>
```

**出力型**:
```python
@dataclass(frozen=True, slots=True)
class Footnote:
    label: str          # "fn1"
    text: str           # "※1"
    lang: str           # "ja"
    role: str           # NotesNumber / NotesNumberPeriodStart 等

@dataclass(frozen=True, slots=True)
class FootnoteMap:
    """Fact ID → 脚注テキストのマッピング。"""
    _index: dict[str, tuple[Footnote, ...]]

    def get(self, fact_id: str) -> tuple[Footnote, ...]: ...
```

**スコープ**: J-GAAP の BS/PL 脚注のみ。IFRS 連結は脚注なし（個別部分のみ）。

### QA 参照

| QA | 関連度 | 内容 |
|----|--------|------|
| A-5 | 直接 | footnoteLink の構造と存在確認 |

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~150-200行 |
| 新規テスト | ~200-300行 |
| 難易度 | 中 |
| セッション | 0.5-1 |

---

## Lane 4 — Analysis: サマリー + 従業員情報 (B6 + B7)

### 位置づけ

Filing の概観情報（Fact 数、会計基準、非標準科目率等）と、jpcrp_cor の構造化 Fact から従業員統計を抽出する。Jupyter での EDA エントリーポイント。

### FEATURES.md 対応

- `eda/summary`: `stmts.summary()` — Filing 概観
- `notes/employees`: 従業員数・平均年齢・平均給与

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/financial/summary.py` | 新規 | `build_summary()`, `FilingSummary` |
| `src/edinet/financial/notes/__init__.py` | 新規 | パッケージ初期化 |
| `src/edinet/financial/notes/employees.py` | 新規 | `extract_employee_info()`, `EmployeeInfo` |
| `tests/test_xbrl/test_summary.py` | 新規 | テスト |
| `tests/test_xbrl/test_notes_employees.py` | 新規 | テスト |

### 既存基盤

- `DEI`: 27 フィールド完全抽出済み（会計基準、業種コード、報告期間等）
- `Statements.__iter__()`: 全 LineItem のイテレーション
- `is_standard_taxonomy()`: 標準/非標準科目判定
- `jpcrp_cor` namespace: 従業員関連 Fact は構造化済み（テーブルパース不要）

### 技術詳細

**FilingSummary**:
```python
@dataclass(frozen=True, slots=True)
class FilingSummary:
    total_items: int
    accounting_standard: str      # "J-GAAP" / "IFRS" / "US-GAAP"
    period: str                   # "2024-04-01 ~ 2025-03-31"
    has_consolidated: bool
    has_non_consolidated: bool
    standard_item_ratio: float    # 0.89 = 89%
    top_items: tuple[str, ...]    # 金額上位 N 件のラベル
    segment_count: int            # セグメント数
```

**EmployeeInfo**:
```python
@dataclass(frozen=True, slots=True)
class EmployeeInfo:
    count: int | None                  # 従業員数
    average_age: float | None          # 平均年齢
    average_annual_salary: int | None  # 平均年間給与（千円）
    consolidated: bool                 # 連結/単体
```

### QA 参照

| QA | 関連度 | 内容 |
|----|--------|------|
| E-1b | 関連 | 非財務構造化データの取り扱い |

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~180-270行 |
| 新規テスト | ~200-350行 |
| 難易度 | 低 |
| セッション | 0.5-1 |

---

## Lane 5 — Taxonomy: 非標準科目 → 標準科目マッピング (B5)

### 位置づけ

Calculation Linkbase の祖先走査により、提出者独自の拡張科目が「どの標準科目の配下にあるか」を逆引きする。クロス企業比較の基盤。

### FEATURES.md 対応

- `taxonomy/standard_mapping`: 非標準科目 → 標準科目の祖先マッピング

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/taxonomy/standard_mapping.py` | 新規 | `map_to_standard()`, `StandardMapping` |
| `tests/test_xbrl/test_standard_mapping.py` | 新規 | テスト |
| `tests/fixtures/standard_mapping/` | 新規 | テストフィクスチャ |

### 既存基盤

- `CalculationLinkbase.ancestors_of(concept, role_uri)`: ルートまでの祖先（循環検出付き）— **完全実装済み**
- `CalculationLinkbase.parent_of(child)`: 直接の親
- `is_standard_taxonomy(uri)`: 標準/非標準判定
- `CustomDetectionResult`（Wave 6 Lane 4）: 非標準科目のリスト

### 技術詳細

```python
@dataclass(frozen=True, slots=True)
class StandardMapping:
    custom_concept: str           # 非標準科目ローカル名
    standard_ancestor: str | None # 最も近い標準科目の祖先
    path: tuple[str, ...]         # custom → ... → standard の経路
    role_uri: str

def map_to_standard(
    calc_linkbase: CalculationLinkbase,
    custom_concepts: Sequence[str],
) -> dict[str, StandardMapping]:
    """非標準科目 → 標準科目の祖先マッピングを返す。"""
```

**例**: `受注損失引当金` → `販管費` → `営業利益` の場合、`standard_ancestor = "OperatingIncome"`

### QA 参照

| QA | 関連度 | 内容 |
|----|--------|------|
| E-6 | 直接 | 拡張科目の実態（1社あたり 4〜91 個） |
| C-7 | 関連 | Calculation Linkbase の木構造 |

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~200-300行 |
| 新規テスト | ~300-400行 |
| 難易度 | 中 |
| セッション | 0.5-1 |

---

## Lane 6 — Segments: 事業セグメント + 地域セグメント (B4 + dimensions/geographic)

### 位置づけ

XBRL コンテキストの `xbrldi:explicitMember` ディメンションから事業セグメント・地域セグメントを抽出し、セグメント別の売上高・利益・資産等を構造化する。

### FEATURES.md 対応

- `dimensions/segments`: 事業セグメント解析
- `dimensions/geographic`: 地域セグメント解析

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/financial/dimensions/segments.py` | 新規 | `extract_segments()`, `SegmentData`, `SegmentItem` |
| `tests/test_xbrl/test_segments.py` | 新規 | テスト |
| `tests/fixtures/segments/` | 新規 | テストフィクスチャ |

### 既存基盤

- `StructuredContext.dimensions`: `dict[str, str]` でディメンション軸→メンバーのマッピングが既にパース済み
- `DefinitionLinkbase`: dimension-domain 関係のパース完了
- `TaxonomyResolver`: 提出者固有メンバーのラベル解決

### 技術詳細

**セグメント軸** (J-2.a.md):
- 事業セグメント: `jpcrp_cor:OperatingSegmentsAxis`
- 地域セグメント: `jpcrp_cor:GeographicAreasAxis`（推定、要実データ確認）

**メンバー構造（2層）**:
1. **標準メンバー**（`jpcrp_cor` 名前空間）: `ReportableSegmentsMember`, `ReconciliationMember` 等
2. **提出者メンバー**（提出者名前空間）: `AutomotiveReportableSegmentMember` 等

```python
@dataclass(frozen=True, slots=True)
class SegmentItem:
    concept: str          # "NetSales"
    label_ja: str         # "売上高"
    value: Decimal
    period: Period

@dataclass(frozen=True, slots=True)
class SegmentData:
    name: str                       # セグメント名（日本語ラベル）
    member_qname: str               # メンバー QName
    is_standard_member: bool        # 標準メンバーか提出者メンバーか
    items: tuple[SegmentItem, ...]  # セグメント内の科目
```

**実装上の課題**:
- 提出者ごとにセグメント定義が異なる → definition linkbase の走査が必須
- メンバーの日本語ラベルは提出者 `_lab.xml` から取得
- v0.1.0 では `OperatingSegmentsAxis` のみ対応で十分

### QA 参照

| QA | 関連度 | 内容 |
|----|--------|------|
| J-2 | 直接 | セグメント情報の構造（ディメンション軸、メンバー定義） |
| C-8 | 関連 | Definition Linkbase のディメンション構造 |

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~300-400行 |
| 新規テスト | ~400-600行 |
| 難易度 | **高** |
| セッション | 1-2 |

---

## Lane 7 — Display: Jupyter HTML 表示 (B10)

### 位置づけ

`_repr_html_` プロトコルを実装し、Jupyter Notebook での財務諸表のインライン表示を提供する。既存の Rich 表示（`__rich_console__`）と並立。

### FEATURES.md 対応

- `display/html`: Jupyter `_repr_html_` 実装

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/display/html.py` | 新規 | `to_html()`, `_repr_html_` 生成ロジック |
| `tests/test_display/test_html.py` | 新規 | テスト |

### 既存基盤

- `DisplayRow` dataclass: 階層表示用の行データが既に構造化済み
- `build_display_rows(statement)`: FinancialStatement → DisplayRow リスト変換
- `render_hierarchical_statement()`: Rich Table への変換（HTML 版のモデル）
- `RawFact.source_line`: ソース行番号（source_linking 基盤、WIP）

### 技術詳細

```python
def to_html(statement: FinancialStatement) -> str:
    """FinancialStatement → HTML テーブル文字列。"""
    rows = build_display_rows(statement)
    # DisplayRow の depth でインデント
    # value, label_ja, label_en をカラムに
    ...
```

**FinancialStatement._repr_html_()** と **Statements._repr_html_()** の両方を実装。

**スタイル**: edgartools の Jupyter 表示を参考に、inline CSS でクリーンなテーブル表示。行間のボーダー、金額の右寄せ、セクション見出しの太字。

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~200-300行 |
| 新規テスト | ~150-250行 |
| 難易度 | 中 |
| セッション | 1 |

---

## Lane 8 — Diff: 訂正差分 + 期間差分 (C1 + C2)

### 位置づけ

訂正前 vs 訂正後の Fact レベル差分（revision diff）と、前期 vs 当期の科目増減（period diff）を構造化する。

### FEATURES.md 対応

- `diff/revision`: 訂正前 vs 訂正後の Fact レベル差分
- `diff/period`: 前期 vs 当期の科目増減

### ファイル割り当て

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/financial/diff.py` | 新規 | `diff_revisions()`, `diff_periods()`, `DiffResult`, `DiffItem` |
| `tests/test_xbrl/test_diff.py` | 新規 | テスト |

### 既存基盤

- `RevisionChain`（Wave 6 Lane 3）: `build_revision_chain()` で訂正チェーンを構築済み
- `Statements.__iter__()`: 全 LineItem のイテレーション
- `LineItem.local_name` + `LineItem.context_id`: Fact の一意識別
- G-7.a.md: 訂正報告書は**完全差し替え**（差分ではない）。別 `doc_id` が付与

### 技術詳細

```python
@dataclass(frozen=True, slots=True)
class DiffItem:
    concept: str
    label_ja: str
    old_value: Decimal | str | None
    new_value: Decimal | str | None
    difference: Decimal | None      # new - old（数値の場合）

@dataclass(frozen=True, slots=True)
class DiffResult:
    added: tuple[LineItem, ...]     # 新しい方にのみ存在
    removed: tuple[LineItem, ...]   # 古い方にのみ存在
    modified: tuple[DiffItem, ...]  # 値が変更された科目
    unchanged_count: int

def diff_revisions(
    original: Statements,
    corrected: Statements,
) -> DiffResult:
    """訂正前 vs 訂正後の Fact レベル差分。"""

def diff_periods(
    prior: FinancialStatement,
    current: FinancialStatement,
) -> DiffResult:
    """前期 vs 当期の科目増減。"""
```

**マッチング戦略**: `local_name` をキーとして Fact を照合。同一 `local_name` で値が異なれば `modified`、片方にのみ存在すれば `added` / `removed`。

**period diff の注意点** (J-5, J-6):
- 当期の有報に含まれる前期データと、前期の有報のデータは**修正再表示により異なる場合がある**
- `diff_periods()` は同一 Filing 内の current/prior を比較するのがデフォルト

### QA 参照

| QA | 関連度 | 内容 |
|----|--------|------|
| G-7 | 直接 | 訂正報告書の XBRL 構造（完全差し替え、別 doc_id） |
| J-5 | 関連 | 前期データの修正再表示 |
| J-6 | 関連 | 修正再表示のエッジケース |

### 工数見積もり

| 項目 | 見積もり |
|------|---------|
| 新規ソース | ~400-600行 |
| 新規テスト | ~400-600行 |
| 難易度 | 中〜高 |
| セッション | 1-2 |

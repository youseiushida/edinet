# Wave 3 / Lane 1 — standards/normalize + statements.py 統合

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 3 / Lane 1 を担当するエージェントです。
担当機能: normalize_integration

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/standards/normalize.py` (新規)
   - `src/edinet/xbrl/statements.py` (変更)
   - `src/edinet/xbrl/standards/jgaap.py` (変更: `to_legacy_concept_list()` 削除)
   - `src/edinet/xbrl/standards/ifrs.py` (変更: `to_legacy_concept_list()`, `_load_json()` 削除)
   - `src/edinet/xbrl/taxonomy/concept_sets.py` (変更: `to_legacy_format()` 削除)
   - `src/edinet/xbrl/data/pl_jgaap.json` (削除)
   - `src/edinet/xbrl/data/bs_jgaap.json` (削除)
   - `src/edinet/xbrl/data/cf_jgaap.json` (削除)
   - `src/edinet/xbrl/data/pl_ifrs.json` (削除)
   - `src/edinet/xbrl/data/bs_ifrs.json` (削除)
   - `src/edinet/xbrl/data/cf_ifrs.json` (削除)
   - `tests/test_xbrl/test_statements.py` (変更)
   - `tests/test_xbrl/test_normalize.py` (新規)
   - `tests/test_xbrl/test_standards_jgaap.py` (変更: legacy テスト削除)
   - `tests/test_xbrl/test_standards_ifrs.py` (変更: legacy テスト削除)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - `Statements` クラスと `build_statements()` の**公開シグネチャ**は変更してはならない
   - `FinancialStatement` / `LineItem` / `StatementType` の定義は変更してはならない
   - `income_statement()` / `balance_sheet()` / `cash_flow_statement()` のシグネチャは変更してはならない
   - **内部実装の切り替え**（JSON → standards モジュール）は公開 API を維持したまま行う

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/taxonomy_mini/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/xbrl_fragments/` 配下の既存ファイルを変更してはならない

### 推奨事項

6. **テストファイルの命名規則**
   - normalize の新規テストは `tests/test_xbrl/test_normalize.py` に作成
   - statements の既存テストは `tests/test_xbrl/test_statements.py` を更新

7. **他モジュールの利用は import のみ**
   - Wave 1 / Wave 2 で完成したモジュールは全て import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.dei` (DEI, AccountingStandard, PeriodType, extract_dei)
     - `edinet.xbrl._namespaces` (NS_* 定数, classify_namespace, NamespaceInfo 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl.taxonomy.concept_sets` (ConceptSet, ConceptSetRegistry, derive_concept_sets 等)
     - `edinet.financial.standards.detect` (detect_accounting_standard, DetectedStandard, AccountingStandard, DetailLevel)
     - `edinet.financial.standards.jgaap` (lookup, canonical_key, reverse_lookup, mappings_for_statement 等)
     - `edinet.financial.standards.ifrs` (lookup, canonical_key, ifrs_to_jgaap_map 等)
     - `edinet.financial.standards.usgaap` (extract_usgaap_summary, USGAAPSummary 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning 等)

8. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 1 — standards/normalize + statements.py 統合

## 0. 位置づけ

Wave 3 Lane 1 は、FEATURES.md の **Accounting Standard Normalization > standards/normalize** と **Financial Statements > statements/*（PL/BS/CF）** の統合に対応する。Wave 2 で独立して作られた部品群（detect, jgaap, ifrs, usgaap, concept_sets）を `statements.py` に統合し、**全会計基準で財務諸表が出る**状態を達成する Wave 3 の最重要レーン。

FEATURES.md の定義:

> - standards/normalize: 会計基準横断の統一アクセス [TODO]
>   - depends: standards/detect, standards/jgaap, standards/ifrs, standards/usgaap
>   - detail: 「売上高」を指定すれば会計基準に依存せず値を取得できる抽象レイヤー

FUTUREPLAN.tmp.md での位置:

> Wave 3 L1 が唯一の statements.py 変更者。
> 1. standards/normalize.py を新規作成
> 2. statements.py の _load_concept_definitions() を concept_sets 呼び出しに置換
> 3. statements.py に normalize ディスパッチを追加

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `standards/detect` (Wave 2 L2) | `detect_accounting_standard()` で会計基準を判別 | read-only |
| `standards/jgaap` (Wave 2 L3) | J-GAAP 科目マッピング（lookup, canonical_key, mappings_for_statement） | read-only |
| `standards/ifrs` (Wave 2 L4) | IFRS 科目マッピング（lookup, canonical_key, ifrs_to_jgaap_map） | read-only |
| `standards/usgaap` (Wave 2 L5) | US-GAAP サマリー抽出（extract_usgaap_summary） | read-only |
| `taxonomy/concept_sets` (Wave 2 L1) | ConceptSet でどの概念が BS/PL/CF に属するかを取得 | read-only |
| `dei` (Wave 1 L6) | DEI 抽出（extract_dei） | read-only |
| `models/financial` | LineItem, FinancialStatement, StatementType | read-only |

### QA 参照

| QA | 関連するトピック |
|------|------|
| D-1 | IFRS 適用企業の XBRL 構造 |
| D-2 | US-GAAP 適用企業の XBRL 構造（BLOCK_ONLY） |
| D-3 | 会計基準の判別方法 |
| E-1 | 財務諸表の種類と識別 |
| E-1d | CF の直接法/間接法識別 |
| E-5 | 業種別の財務諸表の差異 |
| E-7 | 主要勘定科目の concept 名辞書 |
| Z-2 | 科目定義の自動導出可能性 |

---

## 1. 現状分析

### 1.1 現在の statements.py のアーキテクチャ

```
statements.py (現在):
  _load_concept_definitions(StatementType)
    → importlib.resources で JSON 読み込み（pl_jgaap.json 等）
    → {"concept": str, "order": int, "label_hint": str} のリスト

  _build_single_statement(items, statement_type, concept_defs, ...)
    → known_concepts = {d["concept"] for d in concept_defs}   ← J-GAAP 固定
    → candidates = [item for item if item.local_name in known_concepts]
    → period フィルタ → consolidated フィルタ → dimension フィルタ → 重複解決
    → JSON order でソート

  Statements._items: tuple[LineItem, ...]
    → income_statement() / balance_sheet() / cash_flow_statement()
    → 各メソッドが _load_concept_definitions() + _build_single_statement() を呼ぶ
```

### 1.2 問題点

| ID | 問題 | 影響 |
|----|------|------|
| BUG-2~5 | **IFRS / US-GAAP 企業で財務諸表が空になる**。`known_concepts` が J-GAAP 固定のため、`jpigp_cor` や `jppfs_cor` 以外の概念が全て除外される | IFRS 企業約 80 社、US-GAAP 企業 6 社が対象外 |
| BUG-6 | **PL に SS/CF 科目が混入する**。JSON の concept リストが PL に SS 科目（DividendsFromSurplus）や CF 科目を含んでいるケースがある | PL の内容が不正確 |
| BUG-1 | **NetIncome 等が local_name fallback になる**。`canonical_key` 経由でなく JSON の concept 文字列マッチのため、タクソノミ上の正規名と一致しないことがある | 表示名が不安定 |
| BUG-7 | **Duplicate Fact 警告が過剰**。当期/前期の Context が period で正しく disambiguate されていない | ログが汚い |
| 構造 | **JSON とPython の二重管理**。`data/*.json` と `standards/*.py` の `_MAPPINGS` タプルが重複してマッピングを持つ | メンテコスト増大 |

### 1.3 Wave 2 で完成した部品群

```
detect_accounting_standard(facts)
  → DetectedStandard(standard=AccountingStandard.JAPAN_GAAP, detail_level=DETAILED, ...)

jgaap.lookup("NetSales")
  → ConceptMapping(concept="NetSales", canonical_key="revenue", label_ja="売上高", ...)

jgaap.mappings_for_statement(StatementType.INCOME_STATEMENT)
  → (ConceptMapping(...), ConceptMapping(...), ...)  # display_order 順

ifrs.lookup("RevenueIFRS")
  → IFRSConceptMapping(concept="RevenueIFRS", canonical_key="revenue", ...)

usgaap.extract_usgaap_summary(facts)
  → USGAAPSummary(summary_items=[...], text_blocks=[...])

concept_sets.derive_concept_sets(taxonomy_root)
  → ConceptSetRegistry  # 23 業種 × PL/BS/CF/SS/CI の concept セット
```

---

## 2. 設計

### 2.1 アーキテクチャ概要（After）

```
statements.py (Wave 3 L1 後):
  build_statements(items, *, facts=None, contexts=None, taxonomy_root=None)
    → Statements(_items=..., _detected_standard=..., _facts=..., _contexts=..., _taxonomy_root=...)

  Statements:
    income_statement(*, consolidated=True, period=None)
    balance_sheet(*, consolidated=True, period=None)
    cash_flow_statement(*, consolidated=True, period=None)
      ↓ 全て _build_for_type() に委譲（DRY）
    _build_for_type(statement_type, *, consolidated, period)
      ↓
    detect_accounting_standard(facts)
      → DetectedStandard(standard=..., detail_level=...)
      ↓
    ★ 分岐は detail_level ベース:
      BLOCK_ONLY:
        US_GAAP → _build_usgaap_statement()
          → extract_usgaap_summary() でサマリー返却
          → 期間フィルタリング（available_periods / get_items_by_period）
          → FinancialStatement として返却（items は要約のみ）
        JMIS 等 → 空の FinancialStatement + 警告メッセージ

      DETAILED:
        J-GAAP / IFRS / UNKNOWN → 共通パス
          → get_known_concepts(standard, statement_type) で概念セット取得
          → get_concept_order(standard, statement_type) で表示順取得
          → _build_single_statement() で組み立て

normalize.py:
  get_canonical_key(local_name, standard)
    → canonical_key ベースで会計基準横断のアクセス

  get_known_concepts(standard, statement_type)
    → 財務諸表の concept セット（Single Source of Truth）

  cross_standard_lookup(local_name, source, target)
    → 他基準での等価概念を返す
```

### 2.2 公開 API の設計

#### 2.2.1 `build_statements()` の拡張

```python
def build_statements(
    items: Sequence[LineItem],
    *,
    facts: tuple[RawFact, ...] | None = None,
    contexts: dict[str, StructuredContext] | None = None,
    taxonomy_root: Path | None = None,
) -> Statements:
    """LineItem から Statements コンテナを構築する。

    Args:
        items: build_line_items() の出力。
        facts: RawFact タプル。会計基準判別に使用。
            IFRS / US-GAAP の正しい判別には facts 引数が必要。
            facts=None の場合は J-GAAP として扱う（後方互換）。
        contexts: StructuredContext 辞書。US-GAAP サマリー抽出に使用。
        taxonomy_root: タクソノミルートパス（将来の拡張用）。

    Returns:
        Statements コンテナ。

    Note:
        facts を渡さずに IFRS の LineItem（RevenueIFRS 等）を投入した場合、
        J-GAAP の概念セットでフィルタされるため items が空になります。
        全会計基準で正しい財務諸表を得るには facts 引数を指定してください。
    """
    detected = detect_accounting_standard(facts) if facts else None
    return Statements(
        _items=tuple(items),
        _detected_standard=detected,
        _facts=facts,
        _contexts=contexts,
        _taxonomy_root=taxonomy_root,
    )
```

**後方互換性の保証:**
- `facts` / `contexts` / `taxonomy_root` はすべてオプション引数（デフォルト `None`）
- `facts=None` の場合: 会計基準判別をスキップし、J-GAAP フォールバック（既存動作と同一）
- `facts` が渡された場合: `detect_accounting_standard(facts)` で会計基準を判別し、適切なディスパッチを行う
- `contexts` は US-GAAP サマリー抽出（`extract_usgaap_summary(facts, contexts)` の第2引数）に必要
- 既存コード（`build_statements(line_items)` だけの呼び出し）は一切壊れない

**設計判断: なぜ `build_statements()` に `facts` を渡すか:**
- `LineItem` は既にパース済みのため `namespace_uri` / `local_name` はあるが、DEI 情報（`AccountingStandardsDEI`）は `RawFact` 段階でしか取得できない
- `detect_accounting_standard()` は `RawFact` タプルを入力とする
- alternatives として `Statements` の各メソッドに `standard` 引数を追加する案もあるが、呼び出し元が毎回基準を指定するのは冗長

**上位層との接続点（L1 スコープ外、将来の統合で対応）:**
- 現在 `facts` を持っているのは `ParsedXBRL` のみ。上位層（`Filing` クラス等）のパイプラインでは `ParsedXBRL` → `build_line_items()` → `build_statements()` の順で呼ばれる
- `ParsedXBRL` が `facts` と `contexts` を持っているので、呼び出し元が `build_statements(items, facts=parsed.facts, contexts=parsed.contexts)` とすればよい
- この統合は L1 のスコープ外だが、将来の統合に支障のない設計にしておく

#### 2.2.2 `Statements` クラスの拡張

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Statements:
    _items: tuple[LineItem, ...]
    _detected_standard: DetectedStandard | None = None
    _facts: tuple[RawFact, ...] | None = None
    _contexts: dict[str, StructuredContext] | None = None
    _taxonomy_root: Path | None = None

    @property
    def detected_standard(self) -> DetectedStandard | None:
        """検出された会計基準情報を返す。

        Returns:
            DetectedStandard。facts 未指定の場合は None。
        """
        return self._detected_standard
```

- `_detected_standard`: 内部フィールドだが、`detected_standard` プロパティで読み取り可能
  - ユーザーが「この Filing は何基準？」と知りたいケースは一般的であるため公開する
  - 例: `stmts.detected_standard.standard == AccountingStandard.US_GAAP`
- `_facts`: US-GAAP サマリー抽出（`extract_usgaap_summary(facts, contexts)`）に必要
- `_contexts`: 同上。`extract_usgaap_summary()` の第2引数
- `_taxonomy_root`: 将来の拡張用（セクション 5.4 参照）
- 全フィールドのデフォルトは `None`。`Statements(_items=items)` のみでの構築が可能（後方互換）
- 各 `income_statement()` / `balance_sheet()` / `cash_flow_statement()` メソッド内で `_detected_standard` を参照

#### 2.2.3 `normalize.py` の公開 API

```python
# --- 単一概念の正規化 ---

def get_canonical_key(
    local_name: str,
    standard: AccountingStandard | None,
) -> str | None:
    """local_name を canonical_key に変換する。

    Args:
        local_name: XBRL の概念名（例: "NetSales", "RevenueIFRS"）。
        standard: 会計基準。None の場合は全基準を検索。

    Returns:
        canonical_key（例: "revenue"）。未定義の場合は None。

    Note:
        standard=None の場合の検索順序: J-GAAP → IFRS → US-GAAP。
        最初にヒットしたものを返す。
        現時点で J-GAAP と IFRS の local_name は衝突しない
        （IFRS は ``*IFRS`` サフィックス付き）が、将来の安全のため
        検索順序を固定する。
    """

def get_concept_for_key(
    canonical_key: str,
    target_standard: AccountingStandard,
) -> str | None:
    """canonical_key から指定基準の概念名を返す。

    Args:
        canonical_key: 正規化キー（例: "revenue"）。
        target_standard: 取得したい会計基準。

    Returns:
        概念名（例: J-GAAP なら "NetSales", IFRS なら "RevenueIFRS"）。
        未定義の場合は None。
    """

# --- 財務諸表レベルの正規化 ---

def get_known_concepts(
    standard: AccountingStandard | None,
    statement_type: StatementType,
) -> frozenset[str]:
    """指定会計基準・財務諸表の known concept セットを返す。

    statements.py が _build_single_statement() に渡す concept 集合の
    Single Source of Truth。JSON 読み込みを完全に置換する。

    Args:
        standard: 会計基準。None の場合は J-GAAP（フォールバック）。
        statement_type: PL / BS / CF。

    Returns:
        concept 名の frozenset。
    """

def get_concept_order(
    standard: AccountingStandard | None,
    statement_type: StatementType,
) -> dict[str, int]:
    """指定会計基準・財務諸表の concept 表示順を返す。

    JSON の "order" フィールドを完全に置換する。
    Python の _MAPPINGS タプルの display_order を使用。

    Args:
        standard: 会計基準。
        statement_type: PL / BS / CF。

    Returns:
        {concept_name: display_order} の辞書。
    """

# --- クロススタンダード ---

def cross_standard_lookup(
    local_name: str,
    source_standard: AccountingStandard,
    target_standard: AccountingStandard,
) -> str | None:
    """概念名を別の会計基準に変換する。

    内部で get_canonical_key() → get_concept_for_key() を経由する。
    ユーザーが canonical_key を事前に知っている必要がない。

    例: cross_standard_lookup("NetSales", JAPAN_GAAP, IFRS) → "RevenueIFRS"

    Args:
        local_name: 元の概念名（例: "NetSales"）。
        source_standard: 元の会計基準。
        target_standard: 変換先の会計基準。

    Returns:
        変換先の概念名。マッピング不在の場合は None。
    """
    key = get_canonical_key(local_name, source_standard)
    if key is None:
        return None
    return get_concept_for_key(key, target_standard)
```

### 2.3 `_build_single_statement()` の変更

現在の `_build_single_statement()` の変更は最小限に抑え、**concept_defs 引数を known_concepts + concept_order に分離**する:

```python
# Before:
def _build_single_statement(items, statement_type, concept_defs, *, consolidated, period):
    known_concepts = {str(d["concept"]) for d in concept_defs}
    ...
    concept_order = {str(d["concept"]): int(d["order"]) for d in concept_defs}

# After:
def _build_single_statement(
    items: tuple[LineItem, ...],
    statement_type: StatementType,
    known_concepts: frozenset[str],
    concept_order: dict[str, int],
    *,
    consolidated: bool = True,
    period: Period | None = None,
) -> FinancialStatement:
```

**ポイント:**
- `concept_defs: list[dict]` → `known_concepts: frozenset[str]` + `concept_order: dict[str, int]`
- 選択ルール（期間・連結・dimension・重複解決）のロジックは**一切変更しない**
- JSON 固有の処理（`d["concept"]`, `d["order"]`）が消え、純粋なデータ構造が入力になる

### 2.4 会計基準ディスパッチの設計

**設計方針: `detail_level` ベースのディスパッチ + `_build_for_type()` への集約**

`standard` ではなく `detail_level` で一次分岐する。これにより:
- JMIS（BLOCK_ONLY）が US-GAAP と同じ BLOCK_ONLY パスに入り、空の結果を明示的に返す
- 将来新たな BLOCK_ONLY 基準が追加されても自然に対応
- DRY 違反が解消（`income_statement` / `balance_sheet` / `cash_flow_statement` の 3 重複が消える）

```python
# Statements クラス内

def income_statement(self, *, consolidated=True, period=None):
    """損益計算書を返す。"""
    return self._build_for_type(
        StatementType.INCOME_STATEMENT, consolidated=consolidated, period=period
    )

def balance_sheet(self, *, consolidated=True, period=None):
    """貸借対照表を返す。"""
    return self._build_for_type(
        StatementType.BALANCE_SHEET, consolidated=consolidated, period=period
    )

def cash_flow_statement(self, *, consolidated=True, period=None):
    """キャッシュフロー計算書を返す。"""
    return self._build_for_type(
        StatementType.CASH_FLOW_STATEMENT, consolidated=consolidated, period=period
    )

def _build_for_type(self, statement_type, *, consolidated, period):
    """会計基準に応じた財務諸表を組み立てる（内部メソッド）。"""
    std = self._detected_standard

    # --- BLOCK_ONLY パス ---
    if std is not None and std.detail_level == DetailLevel.BLOCK_ONLY:
        if std.standard == AccountingStandard.US_GAAP:
            return self._build_usgaap_statement(
                statement_type, consolidated=consolidated, period=period
            )
        # JMIS 等の BLOCK_ONLY は明示的に警告付きで返す
        return FinancialStatement(
            statement_type=statement_type,
            period=period,
            items=(),
            consolidated=consolidated,
            entity_id="",
            warnings_issued=(
                f"{std.standard.value}: BLOCK_ONLY形式のため"
                "構造化財務諸表を生成できません。",
            ),
        )

    # --- DETAILED パス（J-GAAP / IFRS / UNKNOWN） ---
    # 型安全: DetectedStandard.standard が AccountingStandard enum でない場合は None にフォールバック
    standard_enum: AccountingStandard | None = (
        std.standard if std and isinstance(std.standard, AccountingStandard) else None
    )
    known = get_known_concepts(standard_enum, statement_type)
    order = get_concept_order(standard_enum, statement_type)
    return _build_single_statement(
        self._items,
        statement_type,
        known,
        order,
        consolidated=consolidated,
        period=period,
    )
```

### 2.5 US-GAAP の特殊処理

US-GAAP は BLOCK_ONLY（個別数値タグなし）のため、PL/BS/CF を構造化できない。

**設計方針:**
- `detail_level == DetailLevel.BLOCK_ONLY` を検出
- `extract_usgaap_summary(self._facts, self._contexts)` を呼び出し、summary_items を LineItem 相当に変換
- `FinancialStatement` として返却するが、`warnings_issued` に「US-GAAP は構造化財務諸表非対応、サマリー形式で返却」を含める
- PL/BS/CF の区分は `USGAAPSummaryItem.key` → `jgaap.reverse_lookup(key)` → `ConceptMapping.statement_type` で判定

**`extract_usgaap_summary()` のシグネチャ（実コード確認済み）:**
```python
def extract_usgaap_summary(
    facts: tuple[RawFact, ...],
    contexts: dict[str, StructuredContext],
) -> USGAAPSummary:
```
→ `contexts` が第2引数として必要。`Statements._contexts` で保持する。

```python
def _build_usgaap_statement(
    self,
    statement_type: StatementType,
    *,
    consolidated: bool,
    period: Period | None,
) -> FinancialStatement:
    """US-GAAP のサマリーベース財務諸表を返す。"""
    if self._facts is None or self._contexts is None:
        return FinancialStatement(
            statement_type=statement_type,
            period=period,
            items=(),
            consolidated=consolidated,
            entity_id="",
            warnings_issued=("US-GAAP: facts/contexts が提供されていないため財務諸表を生成できません",),
        )

    summary = extract_usgaap_summary(self._facts, self._contexts)

    # --- 期間フィルタリング ---
    # H-2 修正: 両分岐で target_period を束縛し、未束縛パスを排除
    target_period: Period | None
    if period is not None:
        target_period = period
        target_items = summary.get_items_by_period(period)
    else:
        # period=None → 最新期間を自動選択
        target_period = _select_latest_usgaap_period(
            summary.available_periods, statement_type
        )
        target_items = (
            summary.get_items_by_period(target_period)
            if target_period is not None
            else summary.summary_items
        )

    # summary_items から statement_type に該当する items を抽出
    # key → jgaap.reverse_lookup(key) → ConceptMapping.statement_type で分類
    items: list[LineItem] = []
    for si in target_items:
        jgaap_mapping = jgaap.reverse_lookup(si.key)
        if jgaap_mapping is None:
            continue
        if jgaap_mapping.statement_type != statement_type:
            continue
        items.append(_usgaap_summary_item_to_lineitem(si, jgaap_mapping, self._contexts))

    # --- 成功パスの FinancialStatement 構築 ---
    return FinancialStatement(
        statement_type=statement_type,
        period=target_period,  # 常に束縛済み
        items=tuple(items),
        consolidated=consolidated,
        entity_id=items[0].entity_id if items else "",
        warnings_issued=(
            "US-GAAP: BLOCK_ONLY形式のためサマリー形式で返却しています。"
            "個別科目の構造化データは利用できません。",
        ),
    )
```

#### 2.5.2 `_usgaap_summary_item_to_lineitem()` の変換仕様

`USGAAPSummaryItem` → `LineItem` は構造が異なるため、変換ルールを明示する。

**USGAAPSummaryItem のフィールド（ソースコード確認済み）:**

| フィールド | 型 | 値 |
|-----------|----|----|
| `key` | `str` | canonical_key（例: `"revenue"`） |
| `concept` | `str` | XBRL 概念名（例: `"RevenueUSGAAP"`） |
| `label_ja` | `str` | 日本語ラベル |
| `value` | `Decimal \| str \| None` | 値 |
| `unit_ref` | `str \| None` | 単位参照（`"JPY"` 等） |
| `period` | `Period` | `InstantPeriod \| DurationPeriod` |
| `context_id` | `str` | コンテキスト参照 |

**変換ルール:**

```python
def _usgaap_summary_item_to_lineitem(
    si: USGAAPSummaryItem,
    jgaap_mapping: ConceptMapping,
    contexts: dict[str, StructuredContext],
) -> LineItem:
    """USGAAPSummaryItem を LineItem に変換する。"""
    # entity_id: USGAAPSummaryItem にはないため、contexts から取得
    ctx = contexts.get(si.context_id)
    entity_id = ctx.entity if ctx is not None else ""

    return LineItem(
        concept=f"{{{NS_JPCRP_COR}}}{si.concept}",  # Clark notation
        namespace_uri=NS_JPCRP_COR,
        local_name=si.concept,
        label_ja=LabelInfo(
            label=si.label_ja or jgaap_mapping.label_ja,
            source="usgaap_summary",
            role="label",
        ),
        label_en=LabelInfo(
            label=jgaap_mapping.label_en,
            source="jgaap_mapping",
            role="label",
        ),
        value=si.value,
        unit_ref=si.unit_ref,
        decimals=None,           # US-GAAP summary には decimals がない
        context_id=si.context_id,
        period=si.period,        # Period 型がそのまま使える
        entity_id=entity_id,
        dimensions=(),           # summary items は次元なし
        is_nil=(si.value is None),
        source_line=None,
        order=jgaap_mapping.display_order,
    )
```

#### 2.5.3 `_select_latest_usgaap_period()` の仕様

US-GAAP 企業は 10 期間分の summary items を持つ（5年 × 当期/前期等）。
`period=None` の場合、最新期間を自動選択する。

```python
def _select_latest_usgaap_period(
    available_periods: tuple[Period, ...],
    statement_type: StatementType,
) -> Period | None:
    """US-GAAP の available_periods から最新期間を選択する。

    Args:
        available_periods: USGAAPSummary.available_periods の出力。
        statement_type: BS は InstantPeriod、PL/CF は DurationPeriod を優先。

    Returns:
        最新の Period。available_periods が空の場合は None。
    """
    if not available_periods:
        return None

    if statement_type == StatementType.BALANCE_SHEET:
        # BS: InstantPeriod を優先、最新日付を選択
        instants = [p for p in available_periods if isinstance(p, InstantPeriod)]
        if instants:
            return max(instants, key=lambda p: p.instant)
    else:
        # PL/CF: DurationPeriod を優先、最新終了日を選択
        durations = [p for p in available_periods if isinstance(p, DurationPeriod)]
        if durations:
            return max(durations, key=lambda p: p.end_date)

    # フォールバック: 型に関わらず最新を返す
    return available_periods[0]  # available_periods は日付降順と仮定
```

### 2.6 JSON 廃止とレガシーコードの削除

#### 削除対象ファイル

| ファイル | 理由 |
|----------|------|
| `src/edinet/xbrl/data/pl_jgaap.json` | `jgaap.mappings_for_statement()` に置換 |
| `src/edinet/xbrl/data/bs_jgaap.json` | 同上 |
| `src/edinet/xbrl/data/cf_jgaap.json` | 同上 |
| `src/edinet/xbrl/data/pl_ifrs.json` | `ifrs.mappings_for_statement()` に置換 |
| `src/edinet/xbrl/data/bs_ifrs.json` | 同上 |
| `src/edinet/xbrl/data/cf_ifrs.json` | 同上 |

#### 削除対象コード

| ファイル | 関数/メソッド | 理由 |
|----------|-------------|------|
| `statements.py` | `_load_concept_definitions()` | JSON 読み込みが不要になるため |
| `jgaap.py` | `to_legacy_concept_list()` | JSON ブリッジが不要になるため |
| `ifrs.py` | `to_legacy_concept_list()` | 同上 |
| `ifrs.py` | `_load_json()` | 同上 |
| `concept_sets.py` | `to_legacy_format()` | 同上 |

#### 削除対象テスト

| テストファイル | テスト | 理由 |
|-------------|------|------|
| `test_statements.py` | `TestJSONDataIntegrity` | JSON が存在しなくなるため |
| `test_statements.py` | `TestJsonOnlyFiltering` のうち JSON 前提テスト | リファクタリング（standards ベースに書き換え） |
| `test_standards_jgaap.py` | `to_legacy_concept_list` 関連テスト | 関数自体を削除するため |
| `test_standards_ifrs.py` | `to_legacy_concept_list` / `_load_json` 関連テスト | 同上 |
| `test_standards_ifrs.py` | `_clear_ifrs_cache` autouse fixture から `_load_json.cache_clear()` 行を削除 | `_load_json` 自体が Step 3 で削除されるため。残さないと `AttributeError` で全テスト失敗 |

---

## 3. 実装ステップ

### Step 1: `normalize.py` の新規作成

**目的:** 会計基準間の橋渡しロジックを独立モジュールとして作成する。

**実装内容:**
1. `get_canonical_key(local_name, standard)` — local_name → canonical_key
2. `get_concept_for_key(canonical_key, target_standard)` — canonical_key → local_name
3. `get_known_concepts(standard, statement_type)` — 財務諸表の concept セット
4. `get_concept_order(standard, statement_type)` — concept の表示順序
5. `cross_standard_lookup(local_name, source, target)` — 基準間変換

**設計詳細:**

```python
# normalize.py の内部構造
# get_known_concepts / get_concept_order に @functools.lru_cache を付与し、
# 同一引数での再呼び出しコストを排除する。

@functools.lru_cache(maxsize=32)
def get_known_concepts(standard, statement_type):
    if standard == AccountingStandard.JAPAN_GAAP or standard is None:
        return frozenset(
            m.concept for m in jgaap.mappings_for_statement(statement_type)
        )
    elif standard == AccountingStandard.IFRS:
        return frozenset(
            m.concept for m in ifrs.mappings_for_statement(statement_type)
        )
    elif standard == AccountingStandard.US_GAAP:
        # US-GAAP は BLOCK_ONLY のため空セットを返す
        # （実際の処理は extract_usgaap_summary 経由）
        return frozenset()
    elif standard == AccountingStandard.JMIS:
        # JMIS は現在 BLOCK_ONLY のため _build_for_type() からは呼ばれない。
        # JMIS が将来 DETAILED に変更された場合に備えた分岐。
        # JMIS は IFRS ベースのため IFRS にフォールバック
        return frozenset(
            m.concept for m in ifrs.mappings_for_statement(statement_type)
        )
    # UNKNOWN → J-GAAP フォールバック
    return frozenset(
        m.concept for m in jgaap.mappings_for_statement(statement_type)
    )

@functools.lru_cache(maxsize=32)
def get_concept_order(standard, statement_type):
    if standard == AccountingStandard.JAPAN_GAAP or standard is None:
        return {
            m.concept: m.display_order
            for m in jgaap.mappings_for_statement(statement_type)
        }
    elif standard == AccountingStandard.IFRS:
        return {
            m.concept: m.display_order
            for m in ifrs.mappings_for_statement(statement_type)
        }
    # ... 同パターン
```

**テスト（`test_normalize.py`）:**

| # | テスト | 検証内容 |
|---|--------|---------|
| T01 | `test_get_canonical_key_jgaap` | `get_canonical_key("NetSales", JAPAN_GAAP)` → `"revenue"` |
| T02 | `test_get_canonical_key_ifrs` | `get_canonical_key("RevenueIFRS", IFRS)` → `"revenue"` |
| T03 | `test_get_canonical_key_unknown` | `get_canonical_key("UnknownConcept", JAPAN_GAAP)` → `None` |
| T04 | `test_get_canonical_key_auto_detect` | `get_canonical_key("NetSales", None)` → `"revenue"`（全基準検索） |
| T05 | `test_get_concept_for_key_jgaap` | `get_concept_for_key("revenue", JAPAN_GAAP)` → `"NetSales"` |
| T06 | `test_get_concept_for_key_ifrs` | `get_concept_for_key("revenue", IFRS)` → `"RevenueIFRS"` |
| T07 | `test_get_concept_for_key_missing` | `get_concept_for_key("nonexistent", JAPAN_GAAP)` → `None` |
| T08 | `test_get_known_concepts_jgaap_pl` | `get_known_concepts(JAPAN_GAAP, PL)` → `"NetSales"` 等を含む frozenset |
| T09 | `test_get_known_concepts_ifrs_bs` | `get_known_concepts(IFRS, BS)` → `"AssetsIFRS"` 等を含む frozenset |
| T10 | `test_get_known_concepts_usgaap_returns_empty` | `get_known_concepts(US_GAAP, PL)` → `frozenset()` |
| T11 | `test_get_known_concepts_none_defaults_to_jgaap` | `get_known_concepts(None, PL)` と `get_known_concepts(JAPAN_GAAP, PL)` が等価 |
| T12 | `test_get_concept_order_jgaap_pl` | `get_concept_order(JAPAN_GAAP, PL)` で NetSales < OperatingIncome |
| T13 | `test_get_concept_order_ifrs_pl` | `get_concept_order(IFRS, PL)` で RevenueIFRS が含まれる |
| T14 | `test_cross_standard_lookup_jgaap_to_ifrs` | `cross_standard_lookup("NetSales", JAPAN_GAAP, IFRS)` → `"RevenueIFRS"` |
| T15 | `test_cross_standard_lookup_ifrs_to_jgaap` | `cross_standard_lookup("RevenueIFRS", IFRS, JAPAN_GAAP)` → `"NetSales"` |
| T16 | `test_cross_standard_lookup_jgaap_specific` | `cross_standard_lookup("OrdinaryIncome", JAPAN_GAAP, IFRS)` → `None`（IFRS に経常利益は存在しない） |
| T17 | `test_cross_standard_lookup_same_standard` | `cross_standard_lookup("NetSales", JAPAN_GAAP, JAPAN_GAAP)` → `"NetSales"` |
| T18 | `test_get_known_concepts_jmis_falls_back_to_ifrs` | JMIS は IFRS と同じセットを返す |
| T19 | `test_all_jgaap_pl_have_canonical_key` | J-GAAP PL の全概念に canonical_key がある。docstring で「将来の _MAPPINGS 追加時に canonical_key 忘れを防ぐ安全ネット」の意図を明記する |
| T20 | `test_all_ifrs_pl_have_canonical_key` | IFRS PL の全概念に canonical_key がある。同上 |
| T21 | `test_known_concepts_pl_bs_cf_no_overlap` | 同一基準内で PL/BS/CF の concept が重複しない。**注意**: IFRS 拡張（Step 1.5）で `CashAndCashEquivalentsIFRS` を BS に追加する場合、CF にも同名概念がないかを事前に確認すること。現 `_MAPPINGS` では J-GAAP CF の `CashAndCashEquivalentsAtEndOfPeriod` (cash_end) と IFRS BS の `CashAndCashEquivalentsIFRS` は local_name が異なるため重複しない |

---

### Step 1.5: IFRS マッピング拡張

**目的:** TEMP.md 課題2 で指摘された「IFRS canonical_key を 35 → 50-60 に拡張」を実施する。E2E で日立の有報（189 unique 概念）を分析した結果、明らかに canonical_key を振るべき主要概念が未マッピング。

**変更ファイル:** `src/edinet/xbrl/standards/ifrs.py`

**追加概念:**

| カテゴリ | 概念名 | canonical_key | 追加先 | `statement_type` |
|----------|--------|--------------|--------|-----------------|
| KPI | `BasicEarningsLossPerShareIFRS` | `eps` | `_KPI_MAPPINGS`（新規タプル） | **`None`** |
| KPI | `DilutedEarningsLossPerShareIFRS` | `eps_diluted` | `_KPI_MAPPINGS` | **`None`** |
| CI | `ComprehensiveIncomeIFRS` | `comprehensive_income` | `_CI_MAPPINGS`（新規タプル） | **`None`** |
| CI | `ComprehensiveIncomeAttributableToOwnersOfParentIFRS` | `comprehensive_income_parent` | `_CI_MAPPINGS` | **`None`** |
| CI | `ComprehensiveIncomeAttributableToNonControllingInterestsIFRS` | `comprehensive_income_minority` | `_CI_MAPPINGS` | **`None`** |
| BS | `CashAndCashEquivalentsIFRS` | `cash_and_equivalents` | `_BS_MAPPINGS` に追加 | `StatementType.BALANCE_SHEET` |

**`statement_type` の設計判断（重要）:**
- KPI 概念（EPS 等）は特定の財務諸表に属さないため `statement_type=None`
- CI 概念（包括利益等）は `StatementType.COMPREHENSIVE_INCOME` が未定義のため `statement_type=None`（TEMP.md 課題3 参照。将来の CI 実装時に `StatementType` に `COMPREHENSIVE_INCOME` を追加し、マッピングを更新する）
- `statement_type=None` の概念は `mappings_for_statement(PL)` の結果に**含まれない**（PL に包括利益や EPS が混入することを防ぐ）
- `get_known_concepts()` は `mappings_for_statement()` を通して概念セットを取得するため、KPI/CI は PL/BS/CF のいずれにも混入しない

**設計判断:**
- 未マッピングの残り 150 概念の大半は BS 詳細項目・SS 変動項目・TextBlock・CF 詳細項目であり、canonical_key を振る必要はない（計算リンク遡及や sector モジュールに委ねる）
- 追加は「主要 KPI（EPS）」「包括利益」「BS 現金」に限定し、35 → 41 程度の控えめな拡張とする
- 残りの拡張（50-60 目標）は E2E で企業ごとの不足概念を洗い出しながら段階的に追加

**テスト:**
- 既存の `test_standards_ifrs.py` で `all_mappings()` の件数が増えることの確認
- `_validate_registry()` がモジュールロード時に自動実行され、追加概念の整合性を検証

**既存テストの件数更新（Step 1.5 で必須）:**

| テスト | 現在値 | Step 1.5 後 | 変動理由 |
|--------|--------|-------------|---------|
| `test_all_mappings_count` | 35 | 41 (+6) | KPI 2 + CI 3 + BS 1 |
| `test_all_canonical_keys_count` | 35 | 41 (+6) | 同上 |
| `test_profile_canonical_key_count` | 35 | 41 (+6) | 同上 |
| `test_mappings_for_bs` | BS = 15 | 16 (+1) | `CashAndCashEquivalentsIFRS` 追加 |
| `test_mappings_for_pl` | PL = 15 | 15 (不変) | KPI/CI は `statement_type=None` |
| `test_mappings_for_cf` | CF = 5 | 5 (不変) | 同上 |

**`_ALL_MAPPINGS` の更新（Step 1.5 で必須）:**

```python
# Before:
_ALL_MAPPINGS = (*_PL_MAPPINGS, *_BS_MAPPINGS, *_CF_MAPPINGS)

# After:
_ALL_MAPPINGS = (*_PL_MAPPINGS, *_BS_MAPPINGS, *_CF_MAPPINGS, *_KPI_MAPPINGS, *_CI_MAPPINGS)
```

この統合を忘れると `all_mappings()` / `lookup()` / `canonical_key()` が KPI/CI 概念を返さない。

**行数見積:** ~60 行追加

---

### Step 2: `statements.py` の書き換え

**目的:** JSON 依存を除去し、normalize.py 経由で会計基準別ディスパッチを行う。

**変更の範囲:**

| 関数 | 変更内容 |
|------|---------|
| `_load_concept_definitions()` | **削除** |
| `_build_single_statement()` | 引数を `concept_defs: list[dict]` → `known_concepts: frozenset[str]` + `concept_order: dict[str, int]` に変更 |
| `Statements.__init__` | `_detected_standard: DetectedStandard \| None = None` フィールド追加 |
| `Statements.income_statement()` | normalize 経由で known_concepts / concept_order を取得する形に変更 |
| `Statements.balance_sheet()` | 同上 |
| `Statements.cash_flow_statement()` | 同上 |
| `Statements._build_usgaap_statement()` | **新規追加**（US-GAAP サマリーベース + 期間フィルタリング） |
| `Statements._build_for_type()` | **新規追加**（ディスパッチの集約。DRY 解消） |
| `_usgaap_summary_item_to_lineitem()` | **新規追加**（USGAAPSummaryItem → LineItem 変換） |
| `_select_latest_usgaap_period()` | **新規追加**（US-GAAP 最新期間選択） |
| `build_statements()` | `facts` / `contexts` / `taxonomy_root` オプション引数を追加。`detect_accounting_standard()` を呼ぶ |

**変更しないもの（選択ルール）:**
- `_is_consolidated()` / `_is_non_consolidated()` / `_is_total()` — 連結判定
- `_select_latest_period()` — 最新期間の自動選択
- `_filter_by_period()` — 期間フィルタ
- `_filter_consolidated_with_fallback()` — 連結/個別フォールバック
- 重複解決ロジック（concept_to_items → 先頭採用）

**テスト (`test_statements.py`) の更新:**

| 変更 | 詳細 |
|------|------|
| `TestJSONDataIntegrity` | **削除**（JSON が存在しなくなるため） |
| `TestJsonOnlyFiltering` | **リファクタ**: JSON 前提のテスト名を更新、ロジックは同等のテストを standards ベースで再記述 |
| `TestP1Additional.test_json_loading` | **削除**（`_load_concept_definitions` が消えるため） |
| 既存の全テスト | `build_statements(items)` 呼び出しは**変更不要**（後方互換）。全テストがそのまま Pass する |
| 新規: `TestMultiStandard` | IFRS / US-GAAP の LineItem を投入し、正しく財務諸表が組み立てられることを検証 |
| 新規: `TestUSGAAPBlockOnly` | US-GAAP でサマリーが返されることを検証 |
| 新規: `TestUnknownStandard` | 不明な会計基準で J-GAAP フォールバックが発生することを検証 |

#### 新規テスト詳細

| # | テスト | 検証内容 |
|---|--------|---------|
| T-S01 | `test_ifrs_items_produce_pl` | IFRS の概念名（`RevenueIFRS` 等）を持つ LineItem で PL が組み立てられること |
| T-S02 | `test_ifrs_items_produce_bs` | IFRS BS 概念で BS が組み立てられること |
| T-S03 | `test_jgaap_backward_compat` | `build_statements(items)` （facts なし）で既存動作が維持されること |
| T-S04 | `test_detected_standard_jgaap` | `_detected_standard` が J-GAAP の場合に J-GAAP 概念セットが使われること |
| T-S05 | `test_detected_standard_ifrs` | `_detected_standard` が IFRS の場合に IFRS 概念セットが使われること |
| T-S06 | `test_usgaap_returns_summary_with_warning` | US-GAAP でサマリー形式 + 警告メッセージ（テストデータ仕様: 下記参照） |
| T-S07 | `test_unknown_standard_falls_back_to_jgaap` | 不明基準で J-GAAP フォールバック |
| T-S08 | `test_concept_order_matches_mappings` | 表示順が standards モジュールの display_order と一致 |
| T-S09 | `test_jmis_falls_back_to_ifrs` | JMIS は IFRS 概念セットを使用 |
| T-S10 | `test_jmis_block_only_returns_empty_with_warning` | JMIS（BLOCK_ONLY）で空の FinancialStatement + 警告が返されること |
| T-S11 | `test_usgaap_period_filtering` | US-GAAP で `period` 指定時に該当期間のみの items が返されること |
| T-S12 | `test_usgaap_latest_period_auto_select` | US-GAAP で `period=None` 時に最新期間が自動選択されること（BS: 最新 instant、PL: 最新 duration） |
| T-S13 | `test_same_statements_different_types` | 同一の Statements オブジェクトから `income_statement()` と `balance_sheet()` が異なる StatementType のデータを返すこと（ビヘイビアテスト。内部の `_build_for_type()` 委譲は検証しない） |

**T-S06 のテストデータ仕様:**

```
テストデータ構成:
  - RawFact 3-5 個:
    - revenue 相当（local_name が _SUMMARY_CONCEPTS のいずれかに該当）
    - total_assets 相当
    - net_income_parent 相当
    - 各 RawFact の context_id が StructuredContext 辞書にマッピングされること
    - namespace_uri は NS_JPCRP_COR
  - StructuredContext 辞書（最低 1 context）:
    - context_id → StructuredContext のマッピング
    - entity フィールドに企業識別子を含む
  - DetectedStandard:
    - standard=AccountingStandard.US_GAAP
    - detail_level=DetailLevel.BLOCK_ONLY
  - 期待される検証項目:
    1. FinancialStatement.items に summary 由来の LineItem が含まれること
    2. warnings_issued に BLOCK_ONLY 関連の警告が含まれること
    3. PL/BS で items が正しく分類されること（revenue → PL, total_assets → BS）
    4. 期間フィルタリングが正しく動作すること（最新期間のみ返却）
```

---

### Step 3: レガシーコードの削除

**目的:** JSON 二重管理を解消し、Single Source of Truth を Python に統一する。

**実行順序:**
1. Step 2 の全テストが通ることを確認
2. JSON ファイル 6 個を削除
3. `statements.py` から `_load_concept_definitions()` を削除（Step 2 で既に未使用にしてある）
4. `jgaap.py` から `to_legacy_concept_list()` を削除
5. `ifrs.py` から `to_legacy_concept_list()`, `_load_json()` を削除
6. `concept_sets.py` から `to_legacy_format()` を削除
7. テストの legacy 関連テストを削除
8. `test_standards_ifrs.py` の `_clear_ifrs_cache` autouse fixture から `_load_json.cache_clear()` 行を削除（`_load_json` 削除に伴い `AttributeError` になるため）
9. 全テスト実行で Pass を確認

**削除後の影響確認:**

```bash
# JSON import の残存確認
grep -r "importlib.resources" src/edinet/xbrl/statements.py  # → 0 件
grep -r "_load_concept_definitions" src/ tests/               # → 0 件
grep -r "to_legacy_concept_list" src/ tests/                 # → 0 件
grep -r "to_legacy_format" src/ tests/                       # → 0 件
grep -r "_load_json" src/edinet/xbrl/standards/ifrs.py       # → 0 件
```

---

### Step 4: E2E テスト + 回帰テスト

**目的:** Wave 2 の E2E テストが引き続き Pass することを確認する。

```bash
# ユニットテスト
uv run pytest

# Wave 2 E2E 回帰テスト（API キー・タクソノミパスは環境変数で渡す）
EDINET_API_KEY=$EDINET_API_KEY EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 \
  uv run python tools/wave2_e2e_detect.py

EDINET_API_KEY=$EDINET_API_KEY EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 \
  uv run python tools/wave2_e2e_concept_sets.py
```

---

## 4. バグ解決マッピング

| BUG | 原因 | 解決される Step | 解決方法 |
|-----|------|----------------|---------|
| BUG-2~5 | IFRS/US-GAAP で known_concepts が空 | Step 2 | `detect_accounting_standard()` → IFRS/US-GAAP ディスパッチで正しい概念セットを使用 |
| BUG-6 | PL に SS/CF 科目が混入 | Step 1 + 2 | `get_known_concepts()` が `mappings_for_statement(PL)` のみを返すため、SS/CF 科目は含まれない。JSON の曖昧な分類が Python の厳密な StatementType 分類に置き換わる |
| BUG-1 | NetIncome 等の local_name fallback | Step 1 | `get_canonical_key()` で canonical_key を経由させ、jgaap.lookup() の正確なマッピングを使用 |
| BUG-7 | 重複 Fact 警告が過剰 | Step 2 | 既存の `_select_latest_period()` は既に正しく動作。JSON の concept セットが広すぎたため不要な科目が候補に含まれ、重複が増えていた。概念セットの厳密化で候補数が適正になり、重複も減少 |

---

## 5. エッジケースと注意事項

### 5.1 JMIS（修正国際基準）の扱い

- `AccountingStandard.JMIS` は E2E テストでは未検証（JMIS 適用企業は極めて少数、2社程度）
- **JMIS は `detect.py` で `DetailLevel.BLOCK_ONLY` に分類される**（detect.py:126 で確認済み）
- **ディスパッチ**: `_build_for_type()` の BLOCK_ONLY パスで処理され、空の `FinancialStatement` + 警告メッセージを返す
  - 将来 JMIS が DETAILED タグ付けに変わった場合は、`detect.py` の `DetailLevel` マッピングを更新すれば IFRS フォールバックパスに自動的に流れる
- `normalize.py` の `get_known_concepts(JMIS, PL)` は IFRS 概念セットにフォールバックする。これは JMIS が DETAILED になった場合に備えた設計
- **未検証事項**: JMIS 適用企業の XBRL で使用される概念名が IFRS と同一か否かは未確認。Wave 3 完了後に E2E で確認する
- 将来的に JMIS 固有の概念が必要になった場合は `standards/jmis.py` を追加する余地を残す

### 5.2 `equity_parent` と `shareholders_equity` の分離

WAVE_2_LANE_4_FEEDBACK.md の L-1 で指摘済み:
- IFRS `EquityAttributableToOwnersOfParentIFRS` → `canonical_key="equity_parent"`
- J-GAAP `ShareholdersEquity` → `canonical_key="shareholders_equity"`

`cross_standard_lookup()` ではこの 2 つを「近似マッピング」として扱わない。
概念的に近いが等価ではないため、`ifrs_to_jgaap_map()` の既存マッピングに従う。

### 5.3 銀行業・保険業の扱い

Wave 3 の L2-L4 が sector/* を担当する。L1 は一般事業会社を対象とし、
銀行業の PL 構造差異（経常収益 vs 売上高）は sector モジュールに委ねる。

`get_known_concepts()` が返す概念セットは一般事業会社用。
sector モジュールが完成した後、`get_known_concepts()` に industry_code パラメータを
追加する拡張が想定されるが、Wave 3 L1 では実装しない。

### 5.4 taxonomy_root パラメータの使途

`build_statements(items, facts=facts, taxonomy_root=path)` で taxonomy_root を渡した場合、
`concept_sets.derive_concept_sets(taxonomy_root)` を呼んで role URI ベースの概念分類を
補完できる。ただし Wave 3 L1 ではこの統合は**行わない**（standards モジュールの
`mappings_for_statement()` で十分なため）。将来の sector 対応や非標準科目の分類で使用する。

`taxonomy_root` パラメータは `Statements._taxonomy_root` として保持するが、
L1 では未使用。将来の拡張ポイントとして引数だけ受け付けておく。

### 5.5 ソート順のタイブレーク方針

`concept_order` の `display_order` が同一の概念が存在する場合のソート安定性について:

- **意図的な設計判断**: Python の `sorted()` は安定ソート（Timsort）であるため、同一 `display_order` の概念は XML 文書順（`LineItem.order`）が保持される
- `_build_single_statement()` のソートキーは `(concept_order.get(item.local_name, 9999), item.order)` のタプルとし、`display_order` → `document_order` の二段階ソートとする
- これにより `display_order` が同一でも決定論的な順序が保証される

### 5.6 概念カバレッジの方針

`get_known_concepts()` が返す概念セットは `_MAPPINGS` の「主要科目」に限定される。
これは **意図的な設計判断** であり、以下の理由による:

1. `_MAPPINGS` の科目は財務分析で最も頻繁に参照される「ヘッドライン指標」（売上高、営業利益、総資産 等）
2. `concept_sets` の全概念（PL 65件等）を含めると非標準科目（各社独自の勘定科目）が混入し、企業間比較のノイズになる
3. 詳細科目は将来の `calc_tree` / `pres_tree` 統合で階層構造付きで提供する（Phase 6）

**ユーザーが全 Fact を見たい場合:**
- `Statements` ではなく `LineItem` 一覧（`build_line_items()` の出力）を直接参照する
- `concept_sets` を使って role URI ベースで全概念をフィルタすることも可能

**カバレッジ目安:**
| 基準 | _MAPPINGS 概念数 | concept_sets 概念数（一般事業会社） | カバレッジ |
|------|-----------------|-----------------------------------|----------|
| J-GAAP | 52 | PL:65, BS:68, CF:29 | ~32% |
| IFRS | 41（Step 1.5 拡張後） | - | - |
| US-GAAP | 19（サマリー） | - | BLOCK_ONLY |

### 5.7 Statements のメモリフットプリント（設計トレードオフ認識済み）

`Statements` が `_facts` / `_contexts` を保持する設計は、`Statements` オブジェクトのメモリフットプリントを増加させる（`_facts` は数千要素の RawFact タプル）。代替案として `build_statements()` 内で US-GAAP 判定を済ませ、結果の LineItem だけを Statements に渡す方法もあるが、以下の理由で現設計を採用する:
- 1 Filing あたりのメモリ影響は数 MB 以下で実用上無視できるレベル
- lazy evaluation により初回アクセスまで US-GAAP 処理コストが発生しない
- `taxonomy_root` を使った将来の拡張（sector 対応等）に対応しやすい
- 将来の profiling で問題が出た場合に対処すれば十分

---

## 6. ファイル変更サマリー

| ファイル | 操作 | 行数見積 |
|----------|------|---------|
| `src/edinet/xbrl/standards/normalize.py` | **新規** | ~200 行 |
| `src/edinet/xbrl/statements.py` | **変更** | ~180 行変更（全体 ~550 行。`_build_for_type()` 集約、US-GAAP 期間フィルタ、`_usgaap_summary_item_to_lineitem()` 追加） |
| `src/edinet/xbrl/standards/jgaap.py` | **変更** | ~30 行削除（`to_legacy_concept_list`） |
| `src/edinet/xbrl/standards/ifrs.py` | **変更** | ~60 行追加（Step 1.5 KPI/CI/BS 拡張）+ ~50 行削除（`to_legacy_concept_list`, `_load_json`） |
| `src/edinet/xbrl/taxonomy/concept_sets.py` | **変更** | ~20 行削除（`to_legacy_format`） |
| `src/edinet/xbrl/data/*.json` (6 files) | **削除** | 6 ファイル全削除 |
| `tests/test_xbrl/test_normalize.py` | **新規** | ~300 行 |
| `tests/test_xbrl/test_statements.py` | **変更** | ~100 行変更 + ~200 行追加（T-S10〜T-S13 追加） |
| `tests/test_xbrl/test_standards_jgaap.py` | **変更** | legacy テスト削除 |
| `tests/test_xbrl/test_standards_ifrs.py` | **変更** | legacy テスト削除 + IFRS 拡張テスト追加 |

---

## 7. 完了条件

1. **全会計基準で財務諸表が出る**
   - J-GAAP: PL/BS/CF が正しい概念セットで組み立てられる
   - IFRS: PL/BS/CF が IFRS 概念セットで組み立てられる
   - US-GAAP: サマリー形式で返却される（BLOCK_ONLY 制約）。**期間フィルタリングが正しく動作する**
   - JMIS: BLOCK_ONLY として空の FinancialStatement + 警告メッセージが返される
   - UNKNOWN: J-GAAP フォールバックで動作する

2. **後方互換性が維持される**
   - `build_statements(items)` （facts なし）は既存動作と同一
   - `Statements.income_statement()` / `balance_sheet()` / `cash_flow_statement()` のシグネチャ不変
   - `FinancialStatement` のフィールド・メソッドは不変

3. **JSON 二重管理が解消される**
   - `data/*.json` 6 ファイルが削除済み
   - `_load_concept_definitions()` が削除済み
   - `to_legacy_concept_list()` / `to_legacy_format()` / `_load_json()` が削除済み

4. **テスト**
   - `uv run pytest` — 全 Pass
   - `uv run ruff check src tests` — All checks passed
   - Wave 2 E2E テスト — 回帰なし

5. **normalize API が使える**
   - `get_canonical_key("NetSales", JAPAN_GAAP)` → `"revenue"`
   - `cross_standard_lookup("NetSales", JAPAN_GAAP, IFRS)` → `"RevenueIFRS"`

6. **IFRS マッピングが拡張されている**（Step 1.5）
   - IFRS 概念数が 35 → 41 以上に拡張済み
   - EPS (`BasicEarningsLossPerShareIFRS`) と包括利益がマッピング済み

7. **`Statements.detected_standard` プロパティが利用可能**
   - `stmts = build_statements(items, facts=facts, contexts=contexts)`
   - `stmts.detected_standard` で会計基準情報にアクセス可能

---

## 8. 第5回フィードバック反映状況

| ID | 内容 | 判定 | 対応 |
|-----|------|------|------|
| H-1 | `FinancialStatement.warnings_issued` フィールド未定義 | **誤指摘** — 実コード確認で `warnings_issued: tuple[str, ...]` が既に存在（`models/financial.py:154`）。変更許可リストへの追加不要 | 対応不要 |
| H-2 | `target_period` 未束縛パス | **妥当** | **反映済み** — セクション 2.5 のコードで両分岐で `target_period` を束縛するよう修正。`period=target_period` に統一 |
| M-1 | `facts=None` 時の IFRS LineItem ケース | **妥当** | **反映済み** — `build_statements()` の Docstring に「IFRS/US-GAAP の正しい判別には facts 引数が必要」と Note を追記 |
| M-2 | JMIS 到達不能分岐のコメント | **妥当** | **反映済み** — `get_known_concepts()` の JMIS 分岐に到達不能コメントを追加 |
| M-3 | `cross_standard_lookup()` 引数名の誤記 | **妥当** | **反映済み** — Step 1 実装内容 5. を `cross_standard_lookup(local_name, source, target)` に修正 |
| L-1 | 期間選択ロジック重複 | **妥当** | Wave 3 L1 スコープ外。将来対応 |
| L-2 | T-S13 のテスト方針 | **妥当** | **反映済み** — T-S13 をビヘイビアテスト（同一 Statements から異なる StatementType）に変更 |
| L-3 | Statements のメモリフットプリント | **妥当** | **反映済み** — セクション 5.7 に設計トレードオフ認識を追記 |

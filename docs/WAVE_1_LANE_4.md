# 並列実装の安全ルール（必ず遵守）

あなたは Wave 1 / Lane L4 を担当するエージェントです。
担当機能: contexts

## 絶対禁止事項

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
   - `src/edinet/xbrl/contexts.py` (変更)
   - `tests/test_xbrl/test_contexts.py` (変更)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - 既存の dataclass / class にフィールドを追加する場合は必ずデフォルト値を付与すること
   - 既存のフィールド名・型・関数シグネチャを変更してはならない
   - 既存の定数名を変更・削除してはならない（追加のみ可）

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/taxonomy_mini/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/xbrl_fragments/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリを作成すること
     例: `tests/fixtures/contexts/` 等

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.contexts import ContextCollection` （OK）
   - 例: `from edinet.xbrl import ContextCollection` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_contexts.py` に追記
   - 既存のテストファイル（test_facts.py, test_statements.py 等）は変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 0 で事前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl._namespaces` (NS_* 定数)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 4 — Context 解析の強化

## 0. 位置づけ

Lane 4 は、既存の `contexts.py` を強化し、**Context の構造化情報に対する便利な問い合わせ機構と、下流モジュール（statements, dimensions, standards）が必要とするフィルタリング・分類ユーティリティを提供する** レーン。

FEATURES.md の `XBRL Core > contexts` に対応する。Wave 2 以降の `dimensions/consolidated`、`dimensions/period_variants`、`dimensions/segments` の基盤となる。

### 現在の実装状態

| 機能 | 状態 | 備考 |
|------|------|------|
| period パース（instant/duration） | 実装済み | `InstantPeriod`, `DurationPeriod` |
| entity identifier 抽出 | 実装済み | テキスト値のみ。scheme 属性は未抽出 |
| explicit dimension 抽出（scenario 内） | 実装済み | `DimensionMember(axis, member)` |
| typed dimension 対応 | 未実装 | EDINET は explicit のみ使用（A-2）→ 対応不要 |
| segment 内 dimension | 未対応 | EDINET は scenario のみ使用（A-2）→ 対応不要 |
| entity scheme 属性 | 未抽出 | scheme URI を保持していない |
| 連結/個別判定 | 未実装 | `ConsolidatedOrNonConsolidatedAxis` の判定 |
| 期間ユーティリティ | 未実装 | 最新期間選択、期間フィルタ等 |
| dimension クエリ | 未実装 | 軸→メンバー辞書、特定軸の検索等 |
| Context コレクション | 未実装 | 複数 Context に対するバルクフィルタ |

### L4 完了時のマイルストーン

```python
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import (
    structure_contexts,
    StructuredContext,
    ContextCollection,
    InstantPeriod,
    DurationPeriod,
)

parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)

# --- 新機能: ContextCollection ---
collection = ContextCollection(ctx_map)

# 連結のみ
consolidated = collection.filter_consolidated()
print(len(consolidated))  # 連結 Context 数

# 個別のみ
non_consolidated = collection.filter_non_consolidated()

# 最新期間の duration Context
latest_dur = collection.latest_duration_contexts()

# 最新期間の instant Context
latest_inst = collection.latest_instant_contexts()

# 連結 + 最新期間 + dimension なし（= 全社合計）
main_ctx = collection.filter_consolidated().filter_no_extra_dimensions()
print(main_ctx.filter_duration())   # 当期 PL/CF 用の Context 群
print(main_ctx.filter_instant())    # 当期末 BS 用の Context 群

# 最新期間の取得（property）
print(collection.latest_instant_period)    # InstantPeriod | None
print(collection.latest_duration_period)   # DurationPeriod | None

# REPL / Jupyter での表示
print(repr(collection))
# → ContextCollection(total=278, instant=139, duration=139)

# --- 新機能: StructuredContext の便利プロパティ ---
ctx = ctx_map["CurrentYearDuration"]
print(ctx.is_consolidated)     # True（dimension なし = 連結がデフォルト）
print(ctx.is_instant)          # False
print(ctx.is_duration)         # True
print(ctx.entity_scheme)       # "http://disclosure.edinet-fsa.go.jp"
print(ctx.dimension_dict)      # {} （dimension なし）

ctx_nc = ctx_map["CurrentYearDuration_NonConsolidatedMember"]
print(ctx_nc.is_consolidated)  # False
print(ctx_nc.dimension_dict)   # {"{ns}ConsolidatedOrNonConsolidatedAxis": "{ns}NonConsolidatedMember"}

# --- レシピ: 財務諸表取得の典型パターン ---

# レシピ1: 連結 PL/CF 用の Context（当期）
pl_cf_ctx = collection.filter_consolidated().filter_no_extra_dimensions().filter_duration()
latest_pl_cf = pl_cf_ctx.latest_duration_contexts()

# レシピ2: 連結 BS 用の Context（当期末）
bs_ctx = collection.filter_consolidated().filter_no_extra_dimensions().filter_instant()
latest_bs = bs_ctx.latest_instant_contexts()

# レシピ3: 個別 PL（当期）
noncon_pl = collection.filter_non_consolidated().filter_no_extra_dimensions().filter_duration()
latest_noncon_pl = noncon_pl.latest_duration_contexts()
```

上記レシピは `statements.py` の `_filter_items_for_statement()` が内部的に行っている処理と等価。`ContextCollection` は `statements.py` の内部ロジックを「ユーザー向けに開放する」存在として機能する。

---

## 1. QA 反映方針（L4 に直結するもの）

| QA | 内容 | L4 への反映 |
|---|---|---|
| A-2.1 | Context ID 命名規則: EDINET では `{相対期間}{期間種別}(_{メンバー})*` の規則あり。ただし仕様で厳密に規定されたものではない | Context ID パースには**依存しない**。期間・dimension は XML 構造から取得し、Context ID はトレーサビリティ用途のみ |
| A-2.2 | entity scheme: `http://disclosure.edinet-fsa.go.jp` 固定 | `entity_scheme` フィールドを追加して保持。下流で entity 検証に利用可能 |
| A-2.3 | segment vs scenario: EDINET は **scenario のみ**使用。segment は使用しない | 既存の scenario パースをそのまま維持。segment パースは実装しない |
| A-2.5 | typed dimension: EDINET は **explicit のみ**。typed dimension は使用しない | typed dimension パースは実装しない |
| A-2.6 | デフォルト dimension: dimension 未指定 = 連結（`ConsolidatedMember` がデフォルト） | `is_consolidated` で dimension なしを連結と判定 |
| A-2.8 | Context 総数: 約 278 個（トヨタ有報）。dict で十分 | `ContextCollection` は `dict[str, StructuredContext]` を内部保持 |
| A-2.9 | period 形式: 常に `YYYY-MM-DD`。タイムゾーンなし。`forever` は不使用 | 既存の `datetime.date.fromisoformat()` で十分。`forever` は非対応（エラー時に明示メッセージ） |
| E-2 | 連結/個別の区別: `ConsolidatedOrNonConsolidatedAxis` で判別 | `is_consolidated` / `is_non_consolidated` プロパティ + `filter_consolidated()` ユーティリティ |
| E-3 | 複数期間データ: 当期・前期（・前々期）は別 Context。四半期は累計期間 | `latest_duration_contexts()` / `latest_instant_contexts()` で最新期間を自動選択 |
| J-6.2 | Context ID の年度間安定性: 同じ `CurrentYearDuration` が異なる年度で異なる期間を指す。年度横断は period の日付で照合すべき | Context ID パースには依存しない設計で対応済み |

---

## 2. スコープ

### 2.1 L4 のスコープ

| # | 内容 | 詳細 |
|---|---|---|
| CTX-1 | `StructuredContext` への便利プロパティ追加 | `is_consolidated`, `is_non_consolidated`, `is_instant`, `is_duration`, `has_dimensions`, `dimension_dict`, `entity_scheme` |
| CTX-2 | `entity_scheme` フィールドの追加 | `entity/identifier/@scheme` 属性を抽出して保持。デフォルト値 `None` で後方互換 |
| CTX-3 | `ContextCollection` クラスの新規作成 | 複数 Context に対するバルクフィルタ・クエリの窓口 |
| CTX-4 | 連結/個別フィルタ | `filter_consolidated()`, `filter_non_consolidated()` |
| CTX-5 | 期間フィルタ | `filter_instant()`, `filter_duration()`, `filter_by_period()`, `latest_duration_contexts()`, `latest_instant_contexts()` |
| CTX-6 | Dimension フィルタ | `filter_no_extra_dimensions()`, `filter_no_dimensions()`, `filter_by_dimension()` |
| CTX-7 | 期間ユーティリティ | `unique_instant_periods`, `unique_duration_periods`, `latest_instant_period`, `latest_duration_period` (全て property) |
| CTX-8 | `__repr__` | `ContextCollection` の REPL/Jupyter 表示 |
| CTX-9 | テストの拡充 | 新プロパティ・新クラスに対する P0/P1 テスト |

### 2.2 L4 でやらないこと

| # | 内容 | やらない理由 |
|---|---|---|
| CTX-N1 | typed dimension パース | EDINET は explicit dimension のみ使用（A-2.5） |
| CTX-N2 | segment 内 dimension パース | EDINET は scenario のみ使用（A-2.3） |
| CTX-N3 | Context ID の意味解析（命名規則パース） | Context ID 命名は仕様保証されていない。期間・dimension は XML 構造から取得（J-6.2） |
| CTX-N4 | `forever` period 対応 | EDINET で使用されない（A-2.9） |
| CTX-N5 | statements.py の書き換え | L4 は contexts.py のみ変更。statements.py が新 API を使うのは Wave 3 統合時 |
| CTX-N6 | dimensions/* モジュールの作成 | Wave 2 の Free Rider で対応 |
| CTX-N7 | Definition Linkbase に基づく dimension 検証 | Wave 1 L3 (def_links) の責務 |

---

## 3. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/xbrl/contexts.py` | 変更 | `StructuredContext` プロパティ追加 + `ContextCollection` 新規追加 |
| `tests/test_xbrl/test_contexts.py` | 変更 | 新プロパティ・新クラスのテスト追加 |

---

## 4. データモデル変更

### 4.1 `StructuredContext` — フィールド追加

```python
@dataclass(frozen=True, slots=True)
class StructuredContext:
    """構造化された Context。"""

    # --- 既存フィールド（変更なし） ---
    context_id: str
    period: Period
    entity_id: str
    dimensions: tuple[DimensionMember, ...]
    source_line: int | None

    # --- 新規フィールド（デフォルト値で後方互換） ---
    entity_scheme: str | None = None
    """Entity identifier の scheme 属性値。
    EDINET では ``"http://disclosure.edinet-fsa.go.jp"`` 固定。"""
```

**後方互換性**: `entity_scheme` にデフォルト値 `None` を付与。既存の `StructuredContext(context_id=..., period=..., entity_id=..., dimensions=..., source_line=...)` は引き続き動作する。

### 4.2 `StructuredContext` — プロパティ追加

```python
    # --- 連結/個別判定 ---

    @property
    def is_consolidated(self) -> bool:
        """連結 Context かどうか。

        ``ConsolidatedOrNonConsolidatedAxis`` が未指定（デフォルト = 連結）
        または ``ConsolidatedMember`` が明示的に指定されている場合 True。
        """

    @property
    def is_non_consolidated(self) -> bool:
        """個別（非連結）Context かどうか。

        ``ConsolidatedOrNonConsolidatedAxis`` に
        ``NonConsolidatedMember`` が指定されている場合 True。
        """

    # --- 期間判定 ---

    @property
    def is_instant(self) -> bool:
        """期間が InstantPeriod（時点）かどうか。"""

    @property
    def is_duration(self) -> bool:
        """期間が DurationPeriod（期間）かどうか。"""

    # --- Dimension ユーティリティ ---

    @property
    def has_dimensions(self) -> bool:
        """Dimension が 1 つ以上あるかどうか。"""

    @property
    def dimension_dict(self) -> dict[str, str]:
        """Dimension を ``{axis: member}`` の辞書で返す。

        Returns:
            axis (Clark notation) をキー、member (Clark notation) を値とする辞書。
            Dimension がなければ空辞書。
        """

    def has_dimension(self, axis: str) -> bool:
        """指定した軸の Dimension が存在するかどうか。

        Args:
            axis: 軸の Clark notation。

        Returns:
            指定した軸が dimensions に存在すれば True。
        """

    def get_dimension_member(self, axis: str) -> str | None:
        """指定した軸のメンバーを返す。

        Args:
            axis: 軸の Clark notation。

        Returns:
            メンバーの Clark notation。軸が存在しなければ None。
        """

    @property
    def has_extra_dimensions(self) -> bool:
        """連結/個別軸以外の Dimension があるかどうか。

        「連結/個別軸」とは ``ConsolidatedOrNonConsolidatedAxis``
        （local_name で判定）のみを指す。それ以外の全ての dimension
        （セグメント軸、提出者独自軸等）を extra として扱う。

        全社合計の Fact を取得する際に、``is_consolidated`` と
        ``has_extra_dimensions == False`` を組み合わせて使用する。
        """
```

**連結/個別判定のロジック**:

```
ConsolidatedOrNonConsolidatedAxis の local_name で判定。
namespace は jppfs_cor の任意バージョンを許容するため、local_name 部分のみ比較する。

is_consolidated:
  dimension なし（= デフォルト = 連結）  →  True
  ConsolidatedMember が明示            →  True
  NonConsolidatedMember が明示         →  False
  上記軸が存在しない                    →  True（デフォルト = 連結）

is_non_consolidated:
  NonConsolidatedMember が明示  →  True
  それ以外                      →  False
```

**⚠ `statements.py` の `_is_consolidated()` との差異**:

既存の `statements.py:_is_consolidated()` は「全 dimension の axis が `ConsolidatedOrNonConsolidatedAxis` で終わる場合のみ True」という**より厳格な**定義を採用している。具体的な差異:

| Context の dimension 構成 | L4 `is_consolidated` | `statements.py` `_is_consolidated` |
|---|---|---|
| dimension なし | `True` | `True` |
| ConsolidatedMember 明示のみ | `True` | `True` |
| NonConsolidatedMember 明示 | `False` | `False` |
| セグメント軸のみ（連結軸なし） | **`True`** | **`False`** |
| ConsolidatedMember + セグメント軸 | **`True`** | **`False`** |

L4 の `is_consolidated` は **XBRL Dimensions 仕様に準拠**（`ConsolidatedOrNonConsolidatedAxis` が未指定 = デフォルトメンバー `ConsolidatedMember` が適用される）。`statements.py` の `_is_consolidated` は「全社合計かつ連結」を実質的に判定する関数として実装されている。

**網羅性**: `is_consolidated` のロジック上、`NonConsolidatedMember` が明示されていない限り全 Context は `is_consolidated=True` となる。したがって `filter_consolidated()` と `filter_non_consolidated()` の和集合は **必ず全 Context を網羅する**（どちらにも属さない Context は存在しない）。

**全社合計の抽出には `is_consolidated` と `has_extra_dimensions == False` の組み合わせを使う**:

```python
# statements.py の _is_consolidated() + _is_total() 相当
main = coll.filter_consolidated().filter_no_extra_dimensions()

# statements.py の _is_consolidated() のみ相当（≠ L4 の is_consolidated 単体）
# → filter_consolidated() は「XBRL 仕様上の連結」を返す
# → filter_no_extra_dimensions() で「セグメント分解なし」に絞り込む
```

Wave 3 統合時に `statements.py` を書き換える際は、`ContextCollection` のメソッドチェーンで同等のロジックを再現する。

### 4.3 定数の追加

```python
# _CONSOLIDATED_AXIS / _MEMBER はモジュール内部定数。
# namespace URI にはバージョン年度が含まれるため local_name で判定する。
_CONSOLIDATED_AXIS_LOCAL = "ConsolidatedOrNonConsolidatedAxis"
_CONSOLIDATED_MEMBER_LOCAL = "ConsolidatedMember"
_NON_CONSOLIDATED_MEMBER_LOCAL = "NonConsolidatedMember"
```

namespace URI にバージョン年度が埋め込まれる（例: `jppfs/2023-11-01/jppfs_cor` と `jppfs/2025-11-01/jppfs_cor`）ため、完全な Clark notation ではなく **local_name 部分で判定** する。これにより複数年度のタクソノミに対応可能。

**判定方式**: `str.endswith()` を使用する（例: `dim.axis.endswith("ConsolidatedOrNonConsolidatedAxis")`）。`rsplit("}", 1)` で local_name を抽出するヘルパー関数方式も検討したが、以下の理由で `endswith` を採用する:

1. `statements.py` の既存判定と同じ方式であり、Wave 3 統合時の差異が最小
2. ヘルパー関数の追加が不要（YAGNI）
3. Clark notation `{ns}localName` において `endswith` が false positive になるケースは EDINET では存在しない

---

## 5. `ContextCollection` クラス

### 5.1 設計方針

- **Immutable**: 内部の辞書は変更しない。`__init__` で浅いコピー（`dict(contexts)`）を取り、外部からの変更を遮断する。フィルタ結果は新しい `ContextCollection` を返す
- **Chainable**: `collection.filter_consolidated().filter_no_extra_dimensions()` のようにメソッドチェーン可能
- **Read-only 参照**: 内部は `dict[str, StructuredContext]` を保持し、既存の `structure_contexts()` の戻り値をそのまま受け取る

### 5.2 インターフェース

```python
class ContextCollection:
    """複数の StructuredContext に対するフィルタ・クエリ操作を提供する。

    ``structure_contexts()`` の戻り値を受け取り、連結/個別・期間・
    Dimension によるフィルタリングを行う。フィルタ結果は新しい
    ``ContextCollection`` として返されるため、メソッドチェーンが可能。

    Note:
        ``__iter__`` は values（``StructuredContext``）を返す。
        ``collections.abc.Mapping`` プロトコルには準拠しない。
        キー付きアクセスには ``as_dict`` を使用すること。

    Examples:
        >>> ctx_map = structure_contexts(parsed.contexts)
        >>> coll = ContextCollection(ctx_map)
        >>> main = coll.filter_consolidated().filter_no_extra_dimensions()
        >>> for ctx in main:
        ...     print(ctx.context_id, ctx.period)
    """

    def __init__(self, contexts: dict[str, StructuredContext]) -> None:
        """コレクションを初期化する。

        内部では ``dict(contexts)`` で浅いコピーを作成し、
        外部からの変更を遮断する。

        Args:
            contexts: ``structure_contexts()`` の戻り値。
                ``dict[str, StructuredContext]`` のみ受け付ける。
                ``ContextCollection`` を渡す場合は ``.as_dict`` で変換すること。
        """

    # --- 基本アクセス ---

    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[StructuredContext]: ...
    def __contains__(self, context_id: str) -> bool: ...
    def __getitem__(self, context_id: str) -> StructuredContext: ...
    def get(self, context_id: str) -> StructuredContext | None: ...
    # __bool__ は __len__ からの暗黙的導出で OK（明示的定義は不要）

    def __repr__(self) -> str:
        """REPL / Jupyter 向けの表示。

        パフォーマンス考慮: ``filter_instant()`` / ``filter_duration()`` は
        新しい ``ContextCollection`` を生成するため、``__repr__`` 内では
        使用しない。代わりに ``ctx.is_instant`` / ``ctx.is_duration`` で
        直接カウントする。

        Examples:
            >>> repr(coll)
            'ContextCollection(total=278, instant=139, duration=139)'
        """

    @property
    def as_dict(self) -> dict[str, StructuredContext]:
        """内部辞書の浅いコピーを返す。

        ``StructuredContext`` は frozen dataclass のため、
        deep copy は不要。
        """

    # --- 連結/個別フィルタ ---

    def filter_consolidated(self) -> ContextCollection:
        """連結 Context のみを含む新しいコレクションを返す。

        dimension なし（デフォルト = 連結）または
        ConsolidatedMember が明示された Context を抽出する。

        Note:
            ConsolidatedMember が明示されている Context は、dimension として
            そのまま保持される。dimension なし（デフォルト連結）の Context のみ
            抽出する場合は ``filter_no_dimensions()`` と組み合わせること。
        """

    def filter_non_consolidated(self) -> ContextCollection:
        """個別（非連結）Context のみを含む新しいコレクションを返す。

        NonConsolidatedMember が明示された Context を抽出する。
        """

    # --- 期間フィルタ ---

    def filter_instant(self) -> ContextCollection:
        """InstantPeriod の Context のみを含む新しいコレクションを返す。"""

    def filter_duration(self) -> ContextCollection:
        """DurationPeriod の Context のみを含む新しいコレクションを返す。"""

    def filter_by_period(self, period: Period) -> ContextCollection:
        """指定した期間に完全一致する Context を返す。

        Args:
            period: フィルタ条件の期間。InstantPeriod と DurationPeriod は
                異なる型のため、同じ日付でも別物として扱われる。
        """

    # --- Dimension フィルタ ---

    def filter_no_extra_dimensions(self) -> ContextCollection:
        """連結/個別軸以外の Dimension がない Context を返す。

        「連結/個別軸」は ``ConsolidatedOrNonConsolidatedAxis``
        （local_name 判定）のみ。セグメント軸や提出者独自軸を除外する。
        全社合計の Fact を取得したい場合に使用する。

        Examples:
            全社合計（連結）の典型パターン::

                main = coll.filter_consolidated().filter_no_extra_dimensions()
        """

    def filter_no_dimensions(self) -> ContextCollection:
        """Dimension が一切ない Context を返す。

        Note:
            ``ConsolidatedMember`` が明示的に設定された Context も除外される。
            全社合計の抽出には :meth:`filter_no_extra_dimensions` を
            使用すること。
        """

    def filter_by_dimension(
        self,
        axis: str,
        member: str | None = None,
    ) -> ContextCollection:
        """指定した Dimension 軸（とメンバー）を持つ Context を返す。

        Args:
            axis: 軸の Clark notation（例:
                ``"{http://...jppfs_cor}ConsolidatedOrNonConsolidatedAxis"``）。
            member: メンバーの Clark notation。None の場合は軸の存在のみ判定。

        Note:
            Clark notation にはタクソノミバージョン年度が含まれるため、
            バージョン非依存の検索には local_name での検索が必要になる。
            local_name 版は将来検討。
        """

    # --- 期間クエリ ---

    @property
    def unique_instant_periods(self) -> tuple[InstantPeriod, ...]:
        """ユニークな InstantPeriod を instant 降順で返す。"""

    @property
    def unique_duration_periods(self) -> tuple[DurationPeriod, ...]:
        """ユニークな DurationPeriod を (end_date DESC, start_date ASC) で返す。"""

    @property
    def latest_instant_period(self) -> InstantPeriod | None:
        """最新の InstantPeriod を返す。なければ None。"""

    @property
    def latest_duration_period(self) -> DurationPeriod | None:
        """最新の DurationPeriod を返す。

        end_date が最新のものを選択。同一 end_date なら最長期間
        （start_date が最も古い）を優先する。
        """

    def latest_instant_contexts(self) -> ContextCollection:
        """最新の InstantPeriod を持つ Context のみを返す。"""

    def latest_duration_contexts(self) -> ContextCollection:
        """最新の DurationPeriod を持つ Context のみを返す。"""
```

### 5.3 最新期間選択ロジック

```
latest_instant_period:
  全 InstantPeriod の instant 日付のうち最大値を持つ期間を返す。

latest_duration_period:
  全 DurationPeriod について (end_date DESC, start_date ASC) でソートし先頭を返す。
  → end_date が同一の場合は最長期間（start_date が最も古い）を選択。
  → 四半期報告書では累計期間 (2024-04-01, 2025-03-31) と
    四半期単独 (2025-01-01, 2025-03-31) が同一 end_date で共存するため、
    このタイブレークが必要（Day 15 §6.2 と同じロジック）。
```

このロジックは現在 `statements.py` の `_select_latest_period()` に存在するが、`ContextCollection` に集約することで、下流モジュール（Wave 2 以降の `dimensions/*`、`standards/*`）が同じロジックを再実装しなくて済む。

**注意**: `statements.py` 自体は L4 では変更しない。Wave 3 統合時に `statements.py` が `ContextCollection` を利用するように書き換える。

---

## 6. `entity_scheme` の抽出

### 6.1 変更箇所

`_parse_entity_id()` 関数を拡張し、scheme 属性も返すようにする。

現在:
```python
def _parse_entity_id(elem, cid) -> str:
    # identifier のテキスト値のみ返す
```

変更後:
```python
def _parse_entity_id(elem, cid) -> tuple[str, str | None]:
    # (identifier テキスト値, scheme 属性値) のタプルを返す
```

`_parse_single_context()` 内で戻り値を展開し、`StructuredContext` の `entity_id` と `entity_scheme` にそれぞれ格納する。

**scheme 属性の取得方法**:

```python
scheme = identifier_elem.get("scheme")  # str | None
```

lxml の `Element.get(attr)` は属性が存在しない場合に `None` を返す。EDINET では scheme は必ず存在するが、壊れた XML に対する防御として scheme が `None` のケースは **エラーにせず** `entity_scheme=None` としてそのまま渡す。

### 6.2 EDINET での scheme 値

EDINET では scheme は `http://disclosure.edinet-fsa.go.jp` 固定（A-2.2）。将来的に entity 検証や外部システム連携で利用可能。

---

## 7. 実装の順序

### Step 1: `StructuredContext` のフィールド追加・プロパティ追加

1. `entity_scheme: str | None = None` フィールドを追加
2. `_parse_entity_id()` を拡張して scheme を返す
3. `_parse_single_context()` で `entity_scheme` を設定
4. 連結/個別判定の内部定数を追加
5. `is_consolidated`, `is_non_consolidated` プロパティ追加
6. `is_instant`, `is_duration` プロパティ追加
7. `has_dimensions`, `dimension_dict`, `has_dimension()`, `get_dimension_member()` 追加
8. `has_extra_dimensions` プロパティ追加
9. 対応するテストを追加

### Step 2: `ContextCollection` クラスの実装

1. 基本アクセス（`__len__`, `__iter__`, `__contains__`, `__getitem__`, `get`, `as_dict`）
2. `__repr__` の実装
3. 連結/個別フィルタ（`filter_consolidated()`, `filter_non_consolidated()`）
4. 期間フィルタ（`filter_instant()`, `filter_duration()`, `filter_by_period()`）
5. Dimension フィルタ（`filter_no_extra_dimensions()`, `filter_no_dimensions()`, `filter_by_dimension()`）
6. 期間クエリ（`unique_instant_periods`, `unique_duration_periods`, `latest_instant_period`, `latest_duration_period` — 全て property）
7. 最新 Context 取得（`latest_instant_contexts()`, `latest_duration_contexts()`）
8. 対応するテストを追加

### Step 3: テスト仕上げと品質確認

1. 既存テスト（22 件）が全パスすることを確認
2. 新プロパティのテスト（P0: 必須、P1: 推奨）
3. `ContextCollection` のテスト（P0: 必須、P1: 推奨）
4. `uv run ruff check src tests` でリントクリーン
5. `uv run pytest` で全パス確認

---

## 8. テスト計画

### 8.1 `StructuredContext` プロパティテスト（P0: 12 件）

| # | テスト | 検証内容 |
|---|---|---|
| 1 | `test_is_consolidated_when_no_dimensions` | dimension なし → `is_consolidated=True` |
| 2 | `test_is_consolidated_when_consolidated_member` | `ConsolidatedMember` 明示 → `is_consolidated=True` |
| 3 | `test_is_non_consolidated` | `NonConsolidatedMember` 明示 → `is_non_consolidated=True`, `is_consolidated=False` |
| 4 | `test_is_consolidated_with_segment_dimension_only` | セグメント軸のみ（連結軸なし）→ `is_consolidated=True`。**`statements.py` との差異確認** |
| 5 | `test_is_consolidated_with_consolidated_and_segment` | 連結軸+セグメント軸 → `is_consolidated=True`, `has_extra_dimensions=True` |
| 6 | `test_is_instant_property` | `InstantPeriod` → `is_instant=True`, `is_duration=False` |
| 7 | `test_is_duration_property` | `DurationPeriod` → `is_duration=True`, `is_instant=False` |
| 8 | `test_has_dimensions_true` | dimension あり → `has_dimensions=True` |
| 9 | `test_has_dimensions_false` | dimension なし → `has_dimensions=False` |
| 10 | `test_dimension_dict` | `dimensions` タプル → `{axis: member}` 辞書変換 |
| 11 | `test_entity_scheme_extracted` | `entity/identifier/@scheme` が `entity_scheme` に格納される |
| 12 | `test_entity_scheme_default_none` | 既存コードとの後方互換: デフォルト値 `None` |

### 8.2 `StructuredContext` プロパティテスト（P1: 5 件）

| # | テスト | 検証内容 |
|---|---|---|
| 13 | `test_has_extra_dimensions_true` | セグメント軸あり → `has_extra_dimensions=True` |
| 14 | `test_has_extra_dimensions_false_only_consolidated_axis` | 連結軸のみ → `has_extra_dimensions=False` |
| 15 | `test_get_dimension_member_found` | 存在する軸 → メンバー返却 |
| 16 | `test_get_dimension_member_not_found` | 存在しない軸 → `None` |
| 17 | `test_has_dimension` | 軸の存在確認 |

### 8.3 `ContextCollection` テスト（P0: 16 件）

| # | テスト | 検証内容 |
|---|---|---|
| 18 | `test_collection_len` | 件数が正しい |
| 19 | `test_collection_iter` | イテレーションで全 Context が返る |
| 20 | `test_collection_getitem` | context_id でアクセス可能 |
| 21 | `test_collection_repr` | `__repr__` が `ContextCollection(total=N, instant=M, duration=K)` 形式 |
| 22 | `test_filter_consolidated` | 連結 Context のみ抽出 |
| 23 | `test_filter_non_consolidated` | 個別 Context のみ抽出 |
| 24 | `test_filter_instant` | InstantPeriod のみ抽出 |
| 25 | `test_filter_duration` | DurationPeriod のみ抽出 |
| 26 | `test_filter_no_extra_dimensions` | 連結軸以外の dimension がない Context のみ |
| 27 | `test_filter_no_dimensions_excludes_explicit_consolidated` | `filter_no_dimensions()` が ConsolidatedMember 明示 Context を除外 |
| 28 | `test_filter_by_period` | 指定期間に一致する Context のみ |
| 29 | `test_latest_instant_period_property` | 最新の InstantPeriod が property で返る |
| 30a | `test_latest_duration_period_selects_newest_end_date` | end_date が異なる場合、最新の end_date が選択される |
| 30b | `test_latest_duration_period_tiebreak_selects_longest` | end_date 同一の場合、start_date が最も古い（最長期間）が選択される |
| 31 | `test_method_chaining` | `filter_consolidated().filter_no_extra_dimensions()` がチェーン可能 |
| 32 | `test_collection_getitem_missing_raises_keyerror` | 存在しない context_id で `KeyError` が送出される。`get()` が `None` を返すこととの対比 |

### 8.4 `ContextCollection` テスト（P1: 9 件）

| # | テスト | 検証内容 |
|---|---|---|
| 33 | `test_unique_instant_periods` | ユニーク InstantPeriod のソート順（降順） |
| 34 | `test_unique_duration_periods` | ユニーク DurationPeriod のソート順 (end_date DESC, start_date ASC) |
| 35 | `test_latest_instant_contexts` | 最新 instant の Context 群 |
| 36 | `test_latest_duration_contexts` | 最新 duration の Context 群 |
| 37 | `test_filter_by_dimension_axis_only` | 軸のみ指定でフィルタ |
| 38 | `test_filter_by_dimension_axis_and_member` | 軸+メンバー指定でフィルタ |
| 39 | `test_empty_collection` | 空コレクションの各操作が安全に動作 |
| 40 | `test_latest_duration_period_empty` | 空 or InstantPeriod のみで `latest_duration_period` が `None` |
| 41 | `test_collection_immutability` | 外部の dict を変更しても ContextCollection の内容に影響しないことの確認 |

### 8.5 テスト用 XML ヘルパー

テスト冒頭の XML 定数の増殖を抑えるため、以下のヘルパー関数を導入する:

```python
def _make_context_xml(
    context_id: str,
    *,
    instant: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    dimensions: list[tuple[str, str, str]] | None = None,  # [(ns, axis, member), ...]
    entity_id: str = "X99001-000",
    scheme: str = "http://disclosure.edinet-fsa.go.jp",
) -> str:
    """テスト用 Context XML を生成するヘルパー。"""
```

L4 の新テスト（約 20 件）ではセグメント軸のみ、ConsolidatedMember 明示 + セグメント軸、空 Context 等の XML 定数が必要になる。ヘルパー関数を使用することで、XML 文字列の手書きを減らしテストの可読性を向上させる。既存の XML 定数（`DURATION_XML`, `INSTANT_XML`, `DIMENSION_XML`, `SUBMITTER_DIMENSION_XML`, `MULTI_DIMENSION_XML`）は変更しない。

### 8.6 結合テスト（P1: 3 件）

| # | テスト | 検証内容 |
|---|---|---|
| 42 | `test_collection_from_simple_pl_fixture` | `parse_xbrl_facts → structure_contexts → ContextCollection` の結合 |
| 43 | `test_latest_period_with_multiple_periods` | 当期+前期混在時に最新期間が正しく選択される |
| 44 | `test_filter_consolidated_then_no_dimensions` | `filter_consolidated().filter_no_dimensions()` で ConsolidatedMember 明示 Context が除外されることの確認 |

---

## 9. 後方互換性の保証

### 9.1 影響範囲

`StructuredContext` は以下のモジュールから参照されている:

| ファイル | 使い方 | 影響 |
|---|---|---|
| `xbrl/facts.py` | `build_line_items()` の引数型 | **影響なし**: フィールド追加のみ、既存フィールドは不変 |
| `xbrl/statements.py` | 期間フィルタリングに使用 | **影響なし**: 既存フィールドは不変 |
| `models/financial.py` | `LineItem.period` の型 | **影響なし**: `Period` 型は変更しない |
| `test_contexts.py` | 直接テスト | **影響なし**: 既存テストは全て動作 |
| `test_facts.py` | テストで使用 | **影響なし**: 既存フィールドは不変 |
| `test_statements.py` | テストで使用 | **影響なし**: 既存フィールドは不変 |
| `test_financial_display.py` | テストで使用 | **影響なし**: 既存フィールドは不変 |

### 9.2 保証の方法

1. 既存の `StructuredContext` フィールドは一切変更しない
2. 新フィールド `entity_scheme` にはデフォルト値 `None` を付与
3. `structure_contexts()` のシグネチャと戻り値型は変更しない
4. `ContextCollection` は新クラスであり既存コードに影響しない
5. 全既存テスト（22 件）がパスすることを step 3 で確認

---

## 10. 設計上の判断

### 10.1 `ContextCollection` を別クラスにする理由

`structure_contexts()` の戻り値を `dict` から `ContextCollection` に変更する案も検討したが、以下の理由で **別クラスとして追加** し、`structure_contexts()` は `dict` のまま維持する:

- 既存の全下流モジュール（`facts.py`, `statements.py`）が `dict[str, StructuredContext]` を前提としている
- `ContextCollection(ctx_map)` でラップするだけなので変換コストは無視できる
- 将来的に `structure_contexts()` の戻り値を `ContextCollection` に変更する場合も、`ContextCollection` が `dict` と同じインターフェース（`__getitem__`, `__contains__`）を提供するため移行が容易

### 10.2 連結/個別判定で local_name を使う理由

Clark notation の完全一致（`{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}ConsolidatedOrNonConsolidatedAxis`）ではなく、local_name 部分（`ConsolidatedOrNonConsolidatedAxis`）で判定する。

理由:
- namespace URI にタクソノミバージョン年度が含まれる（`jppfs/2023-11-01` vs `jppfs/2025-11-01`）（H-3）
- バージョン年度は年次更新で変わるため、完全一致では古い filing に対応できない
- local_name は EDINET 開設以来安定している
- `_namespaces.py` が L5 の管轄であり、L4 からは namespace 定数を追加できない

### 10.3 `_parse_entity_id()` の戻り値変更

内部関数 `_parse_entity_id()` の戻り値を `str` から `tuple[str, str | None]` に変更する。これは公開 API ではなく `_` プレフィックス付きの内部関数であるため、後方互換の問題はない。

### 10.4 `unique_periods` を廃止し型別プロパティのみ提供する理由

`unique_periods` は `InstantPeriod` と `DurationPeriod` が混在するため、ソート順の定義が曖昧になる。型が混在したコレクションの利用シーンも不明瞭。`unique_instant_periods` と `unique_duration_periods` のみ提供することで、型安全性と API の明確さを確保する。

### 10.5 プロパティエイリアス (`instant_contexts` / `duration_contexts`) を廃止する理由

同じ操作に2つのアクセス手段（メソッド `filter_instant()` とプロパティ `instant_contexts`）があると「どちらを使うべきか」の認知負荷が発生する。ディファクトスタンダードなライブラリは **One Way to Do It** 原則に従い、フィルタ操作は `filter_*()` メソッドに統一する。

### 10.6 `unique_instant_periods` / `unique_duration_periods` のキャッシュは不要

これらの property は呼ばれるたびに全 Context を走査してソートする。EDINET の 1 Filing あたり最大 Context 数は約 278 個（A-2.8）で、ソート対象のユニーク期間数は通常 2〜6 個程度。走査 + ソートのコストは無視できるレベルであり、キャッシュ機構を導入する必要はない。将来メンテナがこれらの property にキャッシュを追加したくなった場合は、まずプロファイリングで実際のボトルネックを確認すること。

### 10.7 `ContextCollection.from_raw()` ファクトリメソッドについて

`ContextCollection.from_raw(raw_contexts)` のようなファクトリメソッドは利便性があるが、L4 のスコープ内では `ContextCollection(structure_contexts(raw_contexts))` で十分であり、API surface の不要な拡大を避ける。Wave 3 統合時に `structure_contexts()` の戻り値を `ContextCollection` に変更する判断と合わせて検討する。

---

## 11. `__all__` の更新

`contexts.py` の `__all__` に新しいクラスを追加する:

```python
__all__ = [
    "InstantPeriod",
    "DurationPeriod",
    "Period",
    "DimensionMember",
    "StructuredContext",
    "ContextCollection",   # 追加
    "structure_contexts",
]
```

これは `__init__.py` の変更ではなく、`contexts.py` 自身の `__all__` 更新であるため、安全ルールに抵触しない。

---

## 12. 変更ログ（フィードバック反映）

WAVE_1_LANE_4_FEEDBACK.md のフィードバックを反映した変更記録。

### Rev 1 (2026-02-28): フィードバック反映

| FB# | 区分 | 対応 | 変更箇所 | 変更内容 |
|---|---|---|---|---|
| M-1 | MUST | **採用** | §4.2 | `statements.py` の `_is_consolidated()` との差異を表形式で明記。全社合計の抽出には `is_consolidated + has_extra_dimensions == False` の組み合わせを推奨する旨を追加 |
| M-2 | MUST | **採用（選択肢3）** | §5.2, §7, §8, §10.4 | `unique_periods` プロパティを削除。`unique_instant_periods` / `unique_duration_periods` のみ提供。理由を §10.4 に追記 |
| M-3 | MUST | **採用** | §5.2, §8.3 | `latest_instant_period()` / `latest_duration_period()` をメソッドから `@property` に変更。テスト名も `_property` に更新 |
| S-1 | SHOULD | **採用** | §2.1, §5.2, §7, §8.3 | `ContextCollection.__repr__` を追加。スコープ表に CTX-8 として記載。テスト #21 `test_collection_repr` を P0 に追加 |
| S-2 | SHOULD | **採用** | §0, §5.2, §7, §10.5 | `instant_contexts` / `duration_contexts` プロパティエイリアスを廃止。マイルストーンコード例を `filter_instant()` / `filter_duration()` に修正。理由を §10.5 に追記 |
| S-3 | SHOULD | **採用** | §4.2 | `has_extra_dimensions` の docstring に「連結/個別軸 = `ConsolidatedOrNonConsolidatedAxis` のみ」と明記 |
| S-4 | SHOULD→P0 | **採用** | §8.1 | テスト #4 `test_is_consolidated_with_segment_dimension_only`、#5 `test_is_consolidated_with_consolidated_and_segment` を P0 に追加（既存テストの番号を繰り下げ） |
| S-5 | SHOULD | **先送り** | §10.6 | `from_raw()` ファクトリは Wave 3 統合時に検討。理由を §10.6 に追記 |
| Y-1 | MAY | **不採用** | — | `__iter__` が values を返す設計と整合。`as_dict` で dict アクセス可能 |
| Y-2 | MAY | **不採用** | — | 時期尚早の最適化 |
| Y-3 | MAY | **採用** | §5.2 | `filter_consolidated()` の docstring に Note として ConsolidatedMember 明示の dimension 残存を明記 |
| 確認1 | — | **採用** | §5.2 | `__init__` の docstring に `dict[str, StructuredContext]` のみ受付、`ContextCollection` を渡す場合は `.as_dict` で変換する旨を追記 |
| 確認2 | — | **確認済** | — | `filter_by_period` の等価判定は frozen dataclass の値比較で意図通り。異なる Period 型は別物として扱われる。docstring に明記 |
| 確認3 | — | **先送り** | — | `filter_by_dimension` の local_name 対応は将来検討 |
| NEW-1 | テスト | **採用** | §8.1 #4 | セグメント軸のみ Context の `is_consolidated` テスト（P0） |
| NEW-2 | テスト | **採用** | §8.1 #5 | 連結+セグメント混在 Context のテスト（P0） |
| NEW-3 | テスト | **採用** | §8.3 #21 | `__repr__` のテスト（P0） |
| NEW-4 | テスト | **採用** | §8.4 #40 | 空/InstantPeriodのみで `latest_duration_period` が `None` のテスト（P1） |
| NEW-5 | テスト | **採用** | §8.6 #44 | `filter_consolidated().filter_no_dimensions()` の直感テスト（P1） |

### テスト件数サマリー（Rev 1）

| カテゴリ | P0 | P1 | 合計 |
|---|---|---|---|
| StructuredContext プロパティ | 12 (+2) | 5 | 17 |
| ContextCollection | 13 (+1) | 8 (+2) | 21 |
| 結合テスト | — | 3 (+1) | 3 |
| **合計** | **25** | **16** | **41** |

※ 括弧内はフィードバック反映による追加分。既存テスト 22 件と合わせて最大 63 件。

### Rev 2 (2026-02-28): フィードバック反映

| FB# | 区分 | 対応 | 変更箇所 | 変更内容 |
|---|---|---|---|---|
| M-1 | MUST | **採用** | §5.2 `__repr__` | `__repr__` の docstring にパフォーマンス考慮を追記。`filter_instant()` / `filter_duration()` を呼ばず `ctx.is_instant` / `ctx.is_duration` で直接カウントする旨を明記 |
| M-2 | MUST | **採用** | §5.2 `as_dict` | docstring を「内部辞書の浅いコピーを返す」に修正。frozen dataclass のため deep copy 不要の理由も追記 |
| M-3 | MUST | **採用** | §6.1 | `identifier_elem.get("scheme")` が `None` を返すケースはエラーにせず `entity_scheme=None` として渡す旨を明記 |
| S-1 | SHOULD | **採用** | §5.2 | `filter_no_dimensions()` の docstring に「ConsolidatedMember 明示も除外される」旨と See Also を追記。`filter_no_extra_dimensions()` に全社合計の典型パターン Examples を追記 |
| S-2 | SHOULD | **採用** | §8.3 | テスト #29 を #30a `test_latest_duration_period_selects_newest_end_date` と #30b `test_latest_duration_period_tiebreak_selects_longest` に分割。P0 件数を 15 に更新 |
| S-3 | SHOULD | **採用** | §5.1, §5.2 | `__init__` で `dict(contexts)` による浅いコピーを取る旨を設計方針と docstring の両方に明記 |
| S-4 | SHOULD | **採用** | §10.6 | `unique_*_periods` property のキャッシュ不要の根拠を追記（278 Context, ユニーク期間 2〜6 個） |
| S-5 | SHOULD | **採用** | §8.5 | テスト用 XML ヘルパー `_make_context_xml()` の仕様を新セクション §8.5 として追記。既存 XML 定数は変更しない |
| Y-1 | MAY | **採用** | §5.2 | `__bool__` は `__len__` から暗黙導出される旨のコメントを追記 |
| Y-2 | MAY | **採用** | §5.2 | `filter_by_dimension` の docstring に local_name 版将来検討の Note を追記 |
| Y-3 | MAY | **実装時注意** | — | `entity_scheme` フィールドの dataclass 順序制約は計画通り末尾追加で問題なし。実装時に `source_line` のデフォルト値変更がありうることを認識するのみ |
| NEW-6 | テスト | **採用（S-2 に含む）** | §8.3 #30b | `test_latest_duration_period_tiebreak_selects_longest` として P0 に追加 |
| NEW-7 | テスト | **採用** | §8.3 #27 | `test_filter_no_dimensions_excludes_explicit_consolidated` を P0 に追加 |
| NEW-8 | テスト | **採用** | §8.4 #41 | `test_collection_immutability` を P1 に追加 |
| 注意1 | 実装注意 | **認識済** | — | `_parse_entity_id()` の戻り値展開と `StructuredContext` コンストラクタ更新を忘れないこと |
| 注意2 | 実装注意 | **認識済→Rev 3 で解消** | §4.3 | `endswith` 方式を採用（Rev 3 S-2）。`_local_name()` ヘルパーは不要 |
| 注意3 | 実装注意 | **認識済** | — | Step 3 で既存テスト 22 件の完全パスを確認。特に `test_extracts_entity_id` と `test_with_simple_pl_fixture` に注意 |

### テスト件数サマリー（Rev 2）

| カテゴリ | P0 | P1 | 合計 |
|---|---|---|---|
| StructuredContext プロパティ | 12 | 5 | 17 |
| ContextCollection | 15 (+2) | 9 (+1) | 24 |
| 結合テスト | — | 3 | 3 |
| **合計** | **27** | **17** | **44** |

※ Rev 1 から +3 件: P0 に #27 (no_dimensions 除外確認), #30a/#30b (tiebreak 分割で +1)。P1 に #40 (immutability 確認)。既存テスト 22 件と合わせて最大 66 件。

### Rev 3 (2026-02-28): フィードバック反映

| FB# | 区分 | 対応 | 変更箇所 | 変更内容 |
|---|---|---|---|---|
| S-1 | SHOULD | **採用** | §8.3 #32 | `test_collection_getitem_missing_raises_keyerror` を P0 に追加。`__getitem__` の error contract テスト |
| S-2 | SHOULD | **採用（方式 B）** | §4.3 | local_name 判定に `endswith` を使用する旨を明記。`statements.py` と同方式で Wave 3 統合時の差異を最小化。ヘルパー関数は不要（YAGNI） |
| S-3 | SHOULD | **採用** | §0 | マイルストーンのコード例末尾に財務諸表取得の典型パターン（レシピ 3 パターン）を追記。`statements.py` 内部ロジックの「ユーザー向け開放」としての位置づけを明記 |
| S-4 | SHOULD | **採用** | §4.2 | `filter_consolidated()` と `filter_non_consolidated()` の和集合が全 Context を網羅する旨（網羅性）を1行追記 |
| Y-1 | MAY | **採用** | §5.2 | `ContextCollection` の class docstring に `collections.abc.Mapping` 非準拠の Note を追記。`__iter__` が values を返す設計と `as_dict` の使い分けを明記 |
| Y-2 | MAY | **不採用** | — | `__or__` 演算子は YAGNI。将来メモとしても計画の肥大化を避ける |
| Y-3 | MAY | **不採用** | — | `filter_by_period` の型区別テストは #28 で暗黙的にカバー済み。独立テストは冗長 |
| NEW-9 | テスト | **採用** | §8.3 #32 | `test_collection_getitem_missing_raises_keyerror` を P0 に追加（S-1 に含む） |

### テスト件数サマリー（Rev 3）

| カテゴリ | P0 | P1 | 合計 |
|---|---|---|---|
| StructuredContext プロパティ | 12 | 5 | 17 |
| ContextCollection | 16 (+1) | 9 | 25 |
| 結合テスト | — | 3 | 3 |
| **合計** | **28** | **17** | **45** |

※ Rev 2 から +1 件: P0 に #32 (KeyError テスト)。P1 テスト番号を #33〜 に繰り下げ、結合テスト番号を #42〜44 に繰り下げ。既存テスト 22 件と合わせて最大 67 件。

# Wave 4 / Part 2 — jgaap.py / ifrs.py スリム化

# エージェントが守るべきルール

あなたは Wave 4 / Part 2 を担当するエージェントです。
担当機能: jgaap.py / ifrs.py から不要フィールドを削除しスリム化

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/sector/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他 Part が担当するファイルを変更しないこと**
   あなたが変更してよいファイルは以下に限定される:
   - `src/edinet/xbrl/standards/jgaap.py` (既存・変更)
   - `src/edinet/xbrl/standards/ifrs.py` (既存・変更)
   - `src/edinet/xbrl/standards/normalize.py` (既存・変更 — `_get_concept_order_legacy()` のみ)
   - `src/edinet/xbrl/statements.py` (既存・変更 — `_build_usgaap_statement()` のみ)
   - `tests/test_xbrl/test_standards_jgaap.py` (既存・変更)
   - `tests/test_xbrl/test_standards_ifrs.py` (既存・変更)
   - `tests/test_xbrl/test_normalize.py` (既存・変更)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存の公開 API のシグネチャを変更しないこと**
   - `lookup()`, `canonical_key()`, `reverse_lookup()` の引数と戻り値型は維持
   - `mappings_for_statement()`, `all_mappings()`, `all_canonical_keys()` は維持
   - `jgaap_specific_concepts()`, `ifrs_specific_concepts()` は維持
   - `is_jgaap_module()`, `is_ifrs_module()`, `get_profile()` は維持
   - `ifrs_to_jgaap_map()`, `jgaap_to_ifrs_map()` は維持
   - **戻り値の ConceptMapping / IFRSConceptMapping の型は変わるがフィールド削減のみ**

4. **`stubgen` を実行しないこと**
   統合タスクで一括実行する。

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/` 配下の既存ファイルを変更してはならない

## 推奨事項

6. **sector/ モジュールは一切触らないこと**
   - sector/ のフィールド削減は Part 3 の責務
   - sector/ のテストも変更しないこと

7. **テストファイルの命名規則**
   - 既存の `tests/test_xbrl/test_standards_jgaap.py`, `tests/test_xbrl/test_standards_ifrs.py` を変更
   - 新規テストファイルは作成しない

8. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# PART 2 — jgaap.py / ifrs.py スリム化

## 0. 位置づけ

### WAVE_4.md との対応

WAVE_4.md §Part 2:

> Part 1b で concept_sets がパイプラインに接続された後、jgaap.py / ifrs.py から以下のフィールドが不要になる:
> - `label_ja`, `label_en` → TaxonomyResolver が提供
> - `display_order` → concept_sets が提供
> - `period_type` → concept_sets + XSD で導出可能
> - `is_total` → concept_sets の `preferredLabel`

### 依存先

| 依存先 | 用途 | 種類 |
|--------|------|------|
| Part 1b (完了済み) | normalize.py が concept_sets ベースに接続済み | 前提 |
| `taxonomy/concept_sets.py` (Part 1a) | concept_sets で display_order/is_total を代替 | 読取専用 |
| `sector/` (Wave 3) | sector が jgaap の ConceptMapping を参照 | 読取専用（Part 3 で対応） |

### 他 Part とのファイル衝突

- Part 3 が `sector/_base.py` 等を変更するが、本 Part は `jgaap.py` / `ifrs.py` のみ変更するため衝突なし
- Part 1b が `normalize.py` / `statements.py` を変更済みだが、本 Part の変更箇所（`_get_concept_order_legacy()` / `_build_usgaap_statement()`）は Part 1b の変更箇所と重複しない

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| NOW.md §1.7 | 高 | あるべき姿（jgaap → canonical_key のみ） |
| WAVE_4.md §2.1 | 高 | Part 2 の設計方針 |

---

## 1. 背景知識

### 1.1 現在の jgaap.py (1,202 行)

`ConceptMapping` は 9 フィールドを持つ:

| フィールド | 型 | 用途 | 代替元 | **Part 2 判定** |
|-----------|-----|------|--------|:--------:|
| `concept` | `str` | ローカル名 | — | **維持** |
| `canonical_key` | `str` | 正規化キー | — | **維持** |
| `label_ja` | `str` | 日本語ラベル | TaxonomyResolver | **削除** |
| `label_en` | `str` | 英語ラベル | TaxonomyResolver | **削除** |
| `statement_type` | `StatementType \| None` | PL/BS/CF | — | **維持** |
| `period_type` | `PeriodType` | instant/duration | concept_sets + XSD | **削除** |
| `is_jgaap_specific` | `bool` | J-GAAP 固有 | — | **維持** |
| `is_total` | `bool` | 合計行 | concept_sets preferredLabel | **削除** |
| `display_order` | `int` | 表示順序 | concept_sets | **削除** |

83 個の ConceptMapping（PL 16 + BS 24 + CF 35 + KPI 8）。

**display_order の値域**: PL は 1-16（連続）だが、BS は 101-1500（非連続: 101, 102, 103, 200, 300, ...）、CF は 101-720（非連続: 101-115, 200, 301-307, ...）。`enumerate` 変更後は全て 0-based 連番になるが、相対順序は維持される。

### 1.2 現在の ifrs.py (1,155 行)

`IFRSConceptMapping` は 11 フィールドを持つ:

| フィールド | 型 | **Part 2 判定** |
|-----------|-----|:--------:|
| `concept` | `str` | **維持** |
| `canonical_key` | `str` | **維持** |
| `label_ja` | `str` | **削除** |
| `label_en` | `str` | **削除** |
| `statement_type` | `StatementType \| None` | **維持** |
| `period_type` | `str` | **削除** |
| `is_ifrs_specific` | `bool` | **維持** |
| `is_total` | `bool` | **削除** |
| `display_order` | `int` | **削除** |
| `jgaap_concept` | `str \| None` | **維持** |
| `mapping_note` | `str` | **維持** |

55 個の IFRSConceptMapping（PL 15 + BS 19 + CF 16 + CI/KPI 5）。

**CI/KPI の扱い**: CI 3 個 + KPI 2 個は `statement_type=None` であり、`mappings_for_statement()` では取得されない。`_get_concept_order_legacy()` に含まれず、別経路で処理される想定。

### 1.3 `statement_type` を残す理由

WAVE_4.md §2.1 から引用:

> **`statement_type` を残す理由**: normalize.py のレガシーフォールバック（`taxonomy_root=None` の場合）が `mappings_for_statement(statement_type)` を呼び、各 ConceptMapping を `statement_type` でフィルタして既知概念集合を構築する。`statement_type` がないとフォールバック自体が動かない。また US-GAAP パスの `_build_usgaap_statement()` も `reverse_lookup(si.key) → jm.statement_type` で PL/BS/CF を判別している。

### 1.4 `display_order` 削除に伴う波及

#### normalize.py の `_get_concept_order_legacy()`

Part 1b で追加した `_get_concept_order_legacy()` は `m.display_order` を直接参照している:

```python
# normalize.py L234-236 (現在)
base = {
    m.concept: m.display_order  # ← display_order が必要
    for m in jgaap.mappings_for_statement(statement_type)
}
```

`display_order` 削除後は、`mappings_for_statement()` が返すタプルの **定義順（enumerate）** をそのまま order として使う。タプルの定義順は現在の `display_order` 昇順と同一（`_PL_MAPPINGS` / `_BS_MAPPINGS` / `_CF_MAPPINGS` がその順で定義されている）。

#### statements.py の `_build_usgaap_statement()`

`statements.py` L536 で `jm.display_order` を使用している:

```python
# statements.py L479-536
jm = _jgaap.reverse_lookup(si.key)
...
order=jm.display_order,  # ← display_order が必要
```

US-GAAP パスでは `jgaap.reverse_lookup(si.key)` で得た `ConceptMapping` の `display_order` を `LineItem.order` に設定し、ソートに使用している。

**解決策**: `display_order` 削除後は `_ALL_MAPPINGS` 内の定義順インデックスを返すプロパティまたは関数を用意するか、`mappings_for_statement()` の `enumerate` を使う。ただし US-GAAP パスでは `reverse_lookup()` → 単一マッピング取得の流れのため、タプルインデックスは直接使えない。

**設計判断**: `jgaap.py` に `display_index(concept)` ヘルパーを追加する。これは `_ALL_MAPPINGS` 内のインデックスを返し、`display_order` の代替として使う。しかし、これはオーバーエンジニアリングの懸念がある。

**より簡潔な代替案**: `_build_usgaap_statement()` で `si.key` → `reverse_lookup()` → `jm` を取得した後、`jm.statement_type` でフィルタ済みの `mappings_for_statement()` のタプル位置を使う（`list(m.concept for m in ...).index(jm.concept)`）。ただしこれも冗長。

**最もシンプルな解決策**: `_build_usgaap_statement()` 内で独自に `enumerate` ベースの order 辞書を構築する:

```python
from edinet.financial.standards import jgaap as _jgaap

_usgaap_order = {
    m.concept: i
    for st in StatementType
    for i, m in enumerate(_jgaap.mappings_for_statement(st))
}
...
order=_usgaap_order.get(jm.concept, 0),
```

**しかし、US-GAAP サマリーの `si.key` は canonical_key であり、`si.concept` は jgaap のローカル名ではない**。`_build_usgaap_statement()` の `jm = _jgaap.reverse_lookup(si.key)` は canonical_key → ConceptMapping の逆引きであり、`jm.concept` が jgaap のローカル名を返す。US-GAAP サマリーの概念数は少ない（8 個程度）ため、全 mappings を走査しても問題ない。

**最終設計**: statements.py の `_build_usgaap_statement()` を以下のように変更:

```python
# display_order → enumerate ベースの定義順 order
_order_map = {
    m.concept: i
    for i, m in enumerate(_jgaap.mappings_for_statement(statement_type))
}
...
order=_order_map.get(jm.concept, 0),
```

ただし `_order_map` は `_build_usgaap_statement()` のローカル変数として毎回構築する（関数呼び出し頻度が低いため問題ない）。

### 1.5 `PeriodType` 型の削除

`jgaap.py` L55:
```python
PeriodType = Literal["instant", "duration"]
```

`PeriodType` は `__all__` にエクスポートされている。`period_type` フィールド削除に伴い、`PeriodType` も不要になる。**ただし sector/_base.py が `PeriodType` を import している可能性がある**。

調査結果: `sector/_base.py` は `from edinet.financial.standards.jgaap import PeriodType` をしている。sector/ は Part 3 のスコープだが、Part 2 で `PeriodType` を削除すると Part 3 より先に sector/ が壊れる。

**設計判断**: `PeriodType` は jgaap.py に **残す**（型エイリアスのみ、フィールドとしては使わない）。Part 3 で sector/ の `period_type` を削除する際に `PeriodType` も同時に削除する。`__all__` からも維持する。**`# TODO(Part 3): Part 3 で sector/ の period_type 削除時に PeriodType も削除`** コメントを付記。

### 1.6 検証関数の変更

`_validate_registry()` は以下のチェックを行っている:

| チェック | 削除後の状態 |
|---------|------------|
| concept 重複チェック | **維持** |
| canonical_key 重複チェック | **維持** |
| period_type 検証 | **削除** |
| label_ja/label_en 非空チェック | **削除** |
| display_order 一意性（statement_type 内） | **削除** |
| display_order 一意性（KPI） | **削除** |

### 1.7 既存テストの影響

**test_standards_jgaap.py** (378 行):

| テスト | 参照フィールド | 対応 |
|--------|-------------|------|
| T01 `test_lookup_returns_mapping` | `label_ja` | `label_ja` アサーション削除 |
| T13 `test_display_order_ascending` | `display_order` | **削除 → 定義順昇順テストに置換** |
| T32 `test_bs_period_type_instant` | `period_type` | **削除** |
| T33 `test_pl_period_type_duration` | `period_type` | **削除** |
| T34 `test_cf_period_type` | `period_type` | **削除** |
| T36 `test_labels_nonempty` | `label_ja`, `label_en` | **削除** |
| T37 `test_display_order_unique_per_statement` | `display_order` | **削除** |

**test_standards_ifrs.py** (604 行):

| テスト | 参照フィールド | 対応 |
|--------|-------------|------|
| T `test_lookup_revenue_ifrs` | `label_ja` | アサーション削除 |
| T `test_concepts_ordered_by_display_order` | `display_order` | **定義順テストに置換** |
| T `test_all_labels_not_empty` | `label_ja`, `label_en` | **削除** |
| T `test_period_type_bs_is_instant` | `period_type` | **削除** |
| T `test_period_type_pl_is_duration` | `period_type` | **削除** |
| T `test_display_order_unique_per_statement` | `display_order` | **削除** |
| T `test_period_type_cf_is_duration` | `period_type` | **削除** |

### 1.8 sector/ からの参照（Part 2 のスコープ外だが把握必要）

`sector/_base.py` の `SectorConceptMapping` は以下のフィールドを持つ:
- `display_order`, `label_ja`, `label_en`, `period_type`, `is_total` — 全て Part 3 で削除予定
- `from edinet.financial.standards.jgaap import PeriodType` — Part 2 では `PeriodType` を維持して回避

**Part 2 で jgaap.py / ifrs.py から削除するフィールドは sector/ には影響しない**（sector は独自の `SectorConceptMapping` を持ち、jgaap の `ConceptMapping` を継承していないため）。

---

## 2. ゴール

1. `ConceptMapping` から `label_ja`, `label_en`, `period_type`, `is_total`, `display_order` を削除する
2. `IFRSConceptMapping` から同様の 5 フィールドを削除する
3. 全 83 (jgaap) + 55 (ifrs) = 138 個のマッピングエントリを新フォーマットに書き換える
4. `_validate_registry()` から削除フィールドの検証を除去する
5. `normalize.py` の `_get_concept_order_legacy()` を `enumerate` ベースに変更する
6. `statements.py` の `_build_usgaap_statement()` を `enumerate` ベースに変更する
7. テストから削除フィールド参照を除去する

### 非ゴール（スコープ外）

- `PeriodType` 型エイリアスの削除 → Part 3 で sector/ と同時に削除
- sector/ のフィールド削減 → Part 3 の責務
- `canonical_key` の定数化 → Part 4 の責務
- `mappings_for_statement()` のソート順保証変更 → 定義順で維持（後述）

### 非機能要件

- 既存テスト（1,332 件 + Part 1a/1b の新規テスト）が壊れないこと
- `taxonomy_root=None` のレガシーフォールバックが引き続き正常動作すること

---

## 3. 設計

### 3.1 ConceptMapping の変更後

```python
@dataclass(frozen=True, slots=True)
class ConceptMapping:
    """J-GAAP concept の正規化マッピング。

    Attributes:
        concept: jppfs_cor / jpcrp_cor のローカル名
            （例: ``"NetSales"``）。
        canonical_key: 正規化キー（例: ``"revenue"``）。
        statement_type: 所属する財務諸表。PL / BS / CF。
            主要経営指標（EPS 等）は None。
        is_jgaap_specific: J-GAAP 固有の概念か。
    """

    concept: str
    canonical_key: str
    statement_type: StatementType | None
    is_jgaap_specific: bool = False
```

**削除フィールド**: `label_ja`, `label_en`, `period_type`, `is_total`, `display_order`

### 3.2 IFRSConceptMapping の変更後

```python
@dataclass(frozen=True, slots=True)
class IFRSConceptMapping:
    """IFRS concept の正規化マッピング。

    Attributes:
        concept: jpigp_cor のローカル名（例: ``"RevenueIFRS"``）。
        canonical_key: 正規化キー（例: ``"revenue"``）。
        statement_type: 所属する財務諸表。
        is_ifrs_specific: IFRS 固有の概念か。
        jgaap_concept: 対応する J-GAAP のローカル名。
        mapping_note: マッピングに関する補足説明。
    """

    concept: str
    canonical_key: str
    statement_type: StatementType | None
    is_ifrs_specific: bool = False
    jgaap_concept: str | None = None
    mapping_note: str = ""
```

**削除フィールド**: `label_ja`, `label_en`, `period_type`, `is_total`, `display_order`

### 3.3 マッピングエントリの書き換え例

```python
# Before (jgaap.py)
ConceptMapping(
    concept="NetSales",
    canonical_key="revenue",
    label_ja="売上高",
    label_en="Net sales",
    statement_type=_PL,
    period_type="duration",
    display_order=1,
)

# After
ConceptMapping(
    concept="NetSales",
    canonical_key="revenue",
    statement_type=_PL,
)
```

```python
# Before (ifrs.py)
IFRSConceptMapping(
    concept="RevenueIFRS",
    canonical_key="revenue",
    label_ja="売上収益",
    label_en="Revenue",
    statement_type=_PL,
    period_type="duration",
    display_order=1,
    jgaap_concept="NetSales",
)

# After
IFRSConceptMapping(
    concept="RevenueIFRS",
    canonical_key="revenue",
    statement_type=_PL,
    jgaap_concept="NetSales",
)
```

### 3.4 mappings_for_statement() のソート順保証

現在の `_STATEMENT_INDEX` は `_ALL_MAPPINGS` をフィルタして構築:

```python
_STATEMENT_INDEX: dict[StatementType, tuple[ConceptMapping, ...]] = {
    st: tuple(m for m in _ALL_MAPPINGS if m.statement_type == st)
    for st in StatementType
}
```

`_ALL_MAPPINGS` は `(*_PL_MAPPINGS, *_BS_MAPPINGS, *_CF_MAPPINGS, *_KPI_MAPPINGS)` で構築される。`_PL_MAPPINGS` 等のタプル定義順は現在 `display_order` 昇順と同一。

**`display_order` 削除後もタプル定義順を維持する**ことで、`mappings_for_statement()` の返り値は既存と同じ順序になる。docstring の「display_order 順でソート済み」を「定義順でソート済み（タクソノミの標準表示順序に準拠）」に変更する。

### 3.5 normalize.py の `_get_concept_order_legacy()` 変更

```python
# Before
if standard in (AccountingStandard.JAPAN_GAAP, None):
    base = {
        m.concept: m.display_order
        for m in jgaap.mappings_for_statement(statement_type)
    }

# After
if standard in (AccountingStandard.JAPAN_GAAP, None):
    base = {
        m.concept: i
        for i, m in enumerate(jgaap.mappings_for_statement(statement_type))
    }
```

同様に ifrs と最後の else ブランチも変更。

**ポイント**: `enumerate` は 0-based なので `display_order` の 1-based と異なるが、表示順序は相対的な大小関係のみが重要であり、絶対値に意味はないため問題ない。

### 3.6 statements.py の `_build_usgaap_statement()` 変更

```python
# Before (L536)
order=jm.display_order,

# After
# 引数の statement_type に対する定義順 order 辞書を構築（関数内ローカル）
_order_map = {
    m.concept: i
    for i, m in enumerate(_jgaap.mappings_for_statement(statement_type))
}
...
order=_order_map.get(jm.concept, 0),
```

`_order_map` は `_build_usgaap_statement()` の引数 `statement_type` のみで構築する。全 `StatementType` をループする必要はない（US-GAAP パスは statement ごとに呼ばれるため）。関数内ローカルで毎回構築するが、マッピング数は最大 35 個のため性能問題はない。

### 3.7 `_validate_registry()` の変更

```python
# jgaap.py の _validate_registry() — After
def _validate_registry() -> None:
    """マッピングレジストリの整合性を検証する。"""
    concepts = [m.concept for m in _ALL_MAPPINGS]
    if len(concepts) != len(set(concepts)):
        duplicates = [c for c in concepts if concepts.count(c) > 1]
        raise ValueError(f"concept が重複しています: {set(duplicates)}")

    keys = [m.canonical_key for m in _ALL_MAPPINGS]
    if len(keys) != len(set(keys)):
        duplicates = [k for k in keys if keys.count(k) > 1]
        raise ValueError(f"canonical_key が重複しています: {set(duplicates)}")

    for m in _ALL_MAPPINGS:
        if not m.concept:
            raise ValueError("空の concept が登録されています")
        if not m.canonical_key:
            raise ValueError(f"{m.concept} の canonical_key が空です")
```

**削除**: period_type 検証、label_ja/label_en 非空チェック、display_order 一意性チェック。

ifrs.py の `_validate_registry()` も同様に変更。ただし ifrs.py は追加で J-GAAP overlap チェック（`_JGAAP_ONLY_CONCEPTS`）を持ち、これは維持する。

### 3.8 PeriodType の取り扱い

```python
# jgaap.py — PeriodType は残す（sector/ が参照しているため）
# TODO(Part 3): Part 3 で sector/ の period_type 削除時に PeriodType も削除
PeriodType = Literal["instant", "duration"]
```

`__all__` からも削除しない。

---

## 4. 変更内容の詳細

### 4.1 jgaap.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| `ConceptMapping` dataclass | `label_ja`, `label_en`, `period_type`, `is_total`, `display_order` の 5 フィールドと docstring 削除 |
| `PeriodType` | **維持**（`# TODO(Part 3)` コメント追加） |
| `_PL_MAPPINGS` (16 entries) | 各エントリから 5 フィールドを削除 |
| `_BS_MAPPINGS` (24 entries) | 同上 |
| `_CF_MAPPINGS` (35 entries) | 同上 |
| `_KPI_MAPPINGS` (8 entries) | 同上 |
| `_validate_registry()` | period_type / label / display_order チェック削除 |
| `mappings_for_statement()` docstring | 「display_order 順」→「定義順」 |
| `all_mappings()` docstring | 「display_order 昇順」→「定義順」 |
| `import functools` | `functools` の使用箇所を確認し不要なら削除 |

**概算行数変化**: 1,202 行 → ~350 行 (**-850 行**)

### 4.2 ifrs.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| `IFRSConceptMapping` dataclass | `label_ja`, `label_en`, `period_type`, `is_total`, `display_order` の 5 フィールドと docstring 削除 |
| `_PL_MAPPINGS` (15 entries) | 各エントリから 5 フィールドを削除 |
| `_BS_MAPPINGS` (19 entries) | 同上 |
| `_CF_MAPPINGS` (16 entries) | 同上 |
| `_KPI_MAPPINGS` (2 entries) | 同上 |
| `_CI_MAPPINGS` (5 entries) | 同上 |
| `_validate_registry()` | period_type / label / display_order チェック削除（J-GAAP overlap は維持） |
| `mappings_for_statement()` docstring | 「display_order 順」→「定義順」 |

**概算行数変化**: 1,155 行 → ~350 行 (**-805 行**)

### 4.3 normalize.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| `_get_concept_order_legacy()` の 3 箇所 | `m.display_order` → `enumerate` ベースの `i` |
| `_get_concept_order_legacy()` の docstring | 「display_order が優先される」→「表示順序が優先される」、戻り値の説明を更新 |

### 4.4 statements.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| `_build_usgaap_statement()` 内 | `jm.display_order` → `_order_map.get(jm.concept, 0)` |

### 4.5 test_standards_jgaap.py の変更箇所

| テスト | 変更内容 |
|--------|---------|
| T01 | `assert result.label_ja == "売上高"` 削除 |
| T13 | `display_order` 昇順チェック → **定義順序一貫性チェックに置換** |
| T32, T33, T34 | `period_type` テスト → **削除** |
| T36 | `label_ja` / `label_en` 非空テスト → **削除** |
| T37 | `display_order` 一意性テスト → **削除** |

### 4.6 test_standards_ifrs.py の変更箇所

| テスト | 変更内容 |
|--------|---------|
| `test_lookup_revenue_ifrs` | `label_ja` アサーション削除 |
| `test_concepts_ordered_by_display_order` | **定義順テストに置換**（テスト名もリネーム） |
| `test_all_labels_not_empty` | **削除** |
| `test_period_type_bs_is_instant` | **削除** |
| `test_period_type_pl_is_duration` | **削除** |
| `test_display_order_unique_per_statement` | **削除** |
| `test_period_type_cf_is_duration` | **削除** |

---

## 5. テスト計画

### 5.1 テスト原則

- Detroit 派（古典派）: モック不使用
- 既存テストの削除は最小限（削除フィールド参照のみ）
- 新規テストで定義順の一貫性を検証

### 5.2 jgaap テスト一覧

**削除するテスト:**

| ID | テスト名 | 理由 |
|----|---------|------|
| T32 | `test_bs_period_type_instant` | `period_type` フィールド削除 |
| T33 | `test_pl_period_type_duration` | 同上 |
| T34 | `test_cf_period_type` | 同上 |
| T36 | `test_labels_nonempty` | `label_ja` / `label_en` フィールド削除 |
| T37 | `test_display_order_unique_per_statement` | `display_order` フィールド削除 |

**変更するテスト:**

| ID | テスト名 | 変更内容 |
|----|---------|---------|
| T01 | `test_lookup_returns_mapping` | `label_ja` アサーション削除 |
| T13 | `test_display_order_ascending` | 定義順が statement_type ごとに一貫していることを検証に変更 |

**新規テスト（T13 置換）:**

```python
def test_t13_mappings_are_subset_of_all(self) -> None:
    """mappings_for_statement() が all_mappings() のサブセット。"""
    all_concepts = {m.concept for m in all_mappings()}
    for st in StatementType:
        st_concepts = {m.concept for m in mappings_for_statement(st)}
        assert st_concepts.issubset(all_concepts), (
            f"{st.value} に all_mappings() にない concept がある"
        )
```

### 5.3 ifrs テスト一覧

**削除するテスト:**

| テスト名 | 理由 |
|---------|------|
| `test_all_labels_not_empty` | `label_ja` / `label_en` フィールド削除 |
| `test_period_type_bs_is_instant` | `period_type` フィールド削除 |
| `test_period_type_pl_is_duration` | 同上 |
| `test_display_order_unique_per_statement` | `display_order` フィールド削除 |
| `test_period_type_cf_is_duration` | 同上 |

**変更するテスト:**

| テスト名 | 変更内容 |
|---------|---------|
| `test_lookup_revenue_ifrs` | `label_ja` アサーション削除 |
| `test_concepts_ordered_by_display_order` | テスト名変更 + 定義順一貫性チェックに |

### 5.4 normalize レガシーフォールバックテスト

**変更するテスト (test_normalize.py):**

| ID | テスト名 | 変更内容 |
|----|---------|---------|
| T12 | `test_jgaap_pl_order` | `display_order` の具体的値ではなく相対順序のみ検証に変更 |
| T13 | `test_ifrs_pl_contains_revenue` | 変更なし（`display_order` を参照していない） |

**新規テスト:**

| ID | テスト名 | 内容 |
|----|---------|------|
| NEW | `test_legacy_order_is_zero_based_consecutive` | レガシー order が 0-based 連番であることを検証 |

### 5.5 全テスト回帰確認

```bash
uv run pytest
uv run ruff check src/edinet/xbrl/standards/jgaap.py src/edinet/xbrl/standards/ifrs.py src/edinet/xbrl/standards/normalize.py src/edinet/xbrl/statements.py
```

---

## 6. 実装手順

### Step 1: jgaap.py の ConceptMapping 変更

1. `ConceptMapping` から `label_ja`, `label_en`, `period_type`, `is_total`, `display_order` の 5 フィールドを削除
2. `PeriodType` は維持（`# TODO(Part 3)` コメント追加）
3. docstring 更新

### Step 2: jgaap.py のマッピングデータ書き換え

1. `_PL_MAPPINGS` (16 entries): 各エントリから 5 フィールドを削除
2. `_BS_MAPPINGS` (24 entries): 同上
3. `_CF_MAPPINGS` (35 entries): 同上
4. `_KPI_MAPPINGS` (8 entries): 同上
5. **定義順を現在の display_order 順のまま維持する**（タプル内の要素順序を変えない）

### Step 3: jgaap.py の検証・API 関数更新

1. `_validate_registry()`: period_type / label / display_order チェック削除
2. `mappings_for_statement()` docstring: 「display_order 順」→「定義順」
3. `all_mappings()` docstring: 同上
4. 不要な import (`functools` 等) があれば削除

### Step 4: ifrs.py の IFRSConceptMapping 変更

1. Step 1-3 と同様の変更を ifrs.py に適用
2. J-GAAP overlap チェック（`_validate_registry()` 内）は維持

### Step 5: normalize.py の `_get_concept_order_legacy()` 変更

1. `m.display_order` → `enumerate` ベースの `i` に 3 箇所変更
2. docstring の「display_order」言及箇所を更新

### Step 6: statements.py の `_build_usgaap_statement()` 変更

1. `jm.display_order` → `_order_map.get(jm.concept, 0)` に変更
2. `_order_map` を関数内ローカルで構築

### Step 7: test_standards_jgaap.py の更新

1. T01: `label_ja` アサーション削除
2. T13: 定義順一貫性テストに置換
3. T32, T33, T34, T36, T37: 削除

### Step 8: test_standards_ifrs.py の更新

1. Step 7 と同様の変更を ifrs テストに適用

### Step 9: test_normalize.py の更新

1. T12 の `display_order` 具体値チェックがあれば相対順序チェックに変更
2. 新規テスト追加（legacy order の 0-based 連番検証）

### Step 10: 回帰テスト

```bash
uv run pytest
uv run ruff check src/edinet/xbrl/standards/jgaap.py src/edinet/xbrl/standards/ifrs.py src/edinet/xbrl/standards/normalize.py src/edinet/xbrl/statements.py
```

---

## 7. 作成・変更ファイル一覧

| ファイル | 操作 | 行数概算（差分） |
|---------|------|:------:|
| `src/edinet/xbrl/standards/jgaap.py` | 変更 | -850 |
| `src/edinet/xbrl/standards/ifrs.py` | 変更 | -805 |
| `src/edinet/xbrl/standards/normalize.py` | 変更 | -3, +3 |
| `src/edinet/xbrl/statements.py` | 変更 | -1, +8 |
| `tests/test_xbrl/test_standards_jgaap.py` | 変更 | -50, +5 |
| `tests/test_xbrl/test_standards_ifrs.py` | 変更 | -50, +5 |
| `tests/test_xbrl/test_normalize.py` | 変更 | +10 |

---

## 8. 設計判断の記録

### Q1: `display_order` を削除するのに `mappings_for_statement()` は定義順で返すのか？

**A**: タプル定義順は現在の `display_order` 昇順と同一（`_PL_MAPPINGS` は売上高→売上原価→売上総利益→... の順に定義されている）。`display_order` フィールドを削除しても、タプル定義順を維持することで **外部から見た振る舞いは変わらない**。docstring の表現のみ変更する。

### Q2: US-GAAP パスの `jm.display_order` をどう代替するか？

**A**: `_build_usgaap_statement()` 内で `_order_map = {m.concept: i for i, m in enumerate(mappings_for_statement(st))}` を構築し、`jm.concept` でルックアップする。US-GAAP サマリーは最大 8 科目程度のため、毎回構築しても性能問題はない。

### Q3: `PeriodType` を残す必要があるか？

**A**: `sector/_base.py` が `from edinet.financial.standards.jgaap import PeriodType` している。Part 2 で削除すると sector/ のテストが壊れるため、Part 3 と同時に削除する。`# TODO(Part 3)` コメントで明記。

### Q4: テストの削除は適切か？

**A**: 削除するテスト（T32-T34, T36-T37 等）は **削除されたフィールドの存在を前提としたデータ整合性テスト**。フィールド自体が存在しないため、テストの存在意義がなくなる。concept / canonical_key の一意性チェック（T30, T31, T12）等は維持する。

### Q5: `_get_concept_order_legacy()` の sector 合算部分はどうなるか？

**A**: sector 合算部分（`m.display_order for m in reg.mappings_for_statement()`）は **Part 3 のスコープ**。Part 2 では jgaap / ifrs の `m.display_order` のみ `enumerate` に置換する。sector 側の `SectorConceptMapping.display_order` は Part 3 まで維持されるため、sector 合算のロジック自体は変更不要。

ただし、sector 合算のオフセット計算（`max_sector + 1 + order`）で、jgaap 側の `order` が 0-based 連番になる点に注意。元の jgaap 側 `display_order` は statement ごとに異なる開始値と値域（PL: 1-16 連続、BS: 101-1500 非連続、CF: 101-720 非連続）だったが、`enumerate` 後は全て 0, 1, 2, ... の連番になる。`max_sector + 1 + 0` = `max_sector + 1`、`max_sector + 1 + 1` = `max_sector + 2`、... となるため、一般概念が sector 概念の後に配置される動作は維持される。**相対順序のみが重要であり、問題なし**。

### Q6: `test_normalize.py` T12 の変更は必要か？

**A**: T12 は `result["NetSales"] < result["OperatingIncome"]` をチェックしている。これは `display_order` の具体的な値ではなく **相対順序** のチェックであり、`enumerate` ベースでも `NetSales` (index 0) < `OperatingIncome` (index 4) が成立するため **変更不要**。

---

## 9. 実行チェックリスト

- [ ] jgaap.py: ConceptMapping から 5 フィールド削除
- [ ] jgaap.py: PeriodType に `# TODO(Part 3)` コメント追加
- [ ] jgaap.py: 83 個のマッピングエントリを新フォーマットに書き換え
- [ ] jgaap.py: `_validate_registry()` の不要チェック削除
- [ ] jgaap.py: docstring 更新（display_order → 定義順）
- [ ] ifrs.py: IFRSConceptMapping から 5 フィールド削除
- [ ] ifrs.py: 55 個のマッピングエントリを新フォーマットに書き換え
- [ ] ifrs.py: `_validate_registry()` の不要チェック削除
- [ ] ifrs.py: docstring 更新
- [ ] normalize.py: `_get_concept_order_legacy()` の 3 箇所を `enumerate` に変更
- [ ] normalize.py: `_get_concept_order_legacy()` の docstring 更新
- [ ] statements.py: `_build_usgaap_statement()` の `jm.display_order` を置換
- [ ] test_standards_jgaap.py: T01 の `label_ja` アサーション削除
- [ ] test_standards_jgaap.py: T13 を定義順一貫性テストに置換
- [ ] test_standards_jgaap.py: T32, T33, T34, T36, T37 を削除
- [ ] test_standards_ifrs.py: 同様の変更
- [ ] test_normalize.py: 新規テスト追加（legacy order の 0-based 連番検証）
- [ ] 既存テスト全件がパス
- [ ] `uv run ruff check` クリーン

---

## フィードバック反映サマリー（第 1 回）

| # | 指摘 | 重要度 | 判定 | 対応 |
|---|------|:------:|------|------|
| 1 | display_order の値域が非連続（BS: 101-1500、CF: 101-720） | 重要 | **妥当** | §1.1 に display_order の実データ値域を追記。§Q5 の「元は 1-based」を「statement ごとに異なる開始値と値域」に修正 |
| 2 | `_STATEMENT_INDEX` がソートではなくフィルタのみ | 情報 | **確認済み** | jgaap.py L977-980 で確認。ソートなし、フィルタのみ。タプル定義順が維持される |
| 3 | `_order_map` を `statement_type` 引数のみで構築 | 中 | **妥当・採用** | §3.6 を修正。全 StatementType ループを削除し、引数の `statement_type` のみで構築する簡潔な実装に変更 |
| 4 | jgaap マッピング数が 79 ではなく 83（CF が 35） | 中 | **妥当** | 実データで確認。jgaap: 83 個（PL 16 + BS 24 + CF 35 + KPI 8）、ifrs: 55 個（PL 15 + BS 19 + CF 16 + CI/KPI 5）。全箇所の数値を修正 |
| 5 | CI マッピングの statement_type=None が legacy order に含まれない | 低 | **妥当** | §1.2 に CI/KPI の扱いを明記 |
| 6 | T13 置換テストが concept 一意性テスト（T30 と重複） | 中 | **妥当** | `mappings_for_statement()` が `all_mappings()` のサブセットであることを検証するテストに変更 |
| 7 | `__all__` の更新漏れリスク | 低 | **対応済み** | §3.8 で既に明記 |
| 8 | sector 合算テストが display_order 具体値に依存していないか | 中 | **確認済み: 問題なし** | test_normalize.py の T22-T30 に display_order / .order への参照なし（Grep 確認済み） |
| 9 | normalize.py の docstring にも display_order 言及あり | 低 | **妥当** | §4.3 と Step 5 に docstring 更新を追加 |

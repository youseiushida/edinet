# Wave 4 / Part 3 — sector/ スリム化 + sector_key リネーム

# エージェントが守るべきルール

あなたは Wave 4 / Part 3 を担当するエージェントです。
担当機能: sector/ から不要フィールドを削除し、`canonical_key` → `sector_key` リネームを行う

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
   - `src/edinet/xbrl/sector/_base.py` (既存・変更)
   - `src/edinet/xbrl/sector/banking.py` (既存・変更)
   - `src/edinet/xbrl/sector/insurance.py` (既存・変更)
   - `src/edinet/xbrl/sector/construction.py` (既存・変更)
   - `src/edinet/xbrl/sector/railway.py` (既存・変更)
   - `src/edinet/xbrl/sector/securities.py` (既存・変更)
   - `src/edinet/xbrl/standards/normalize.py` (既存・変更 — sector 関連ブロックのみ)
   - `tests/test_xbrl/test_sector_base.py` (既存・変更)
   - `tests/test_xbrl/test_sector_banking.py` (既存・変更)
   - `tests/test_xbrl/test_sector_insurance.py` (既存・変更)
   - `tests/test_xbrl/test_sector_construction.py` (既存・変更)
   - `tests/test_xbrl/test_sector_railway.py` (既存・変更)
   - `tests/test_xbrl/test_sector_securities.py` (既存・変更)
   - `tests/test_xbrl/test_sector_cross_validation.py` (既存・変更)
   - `tests/test_xbrl/test_normalize.py` (既存・変更 — sector 関連テストのみ)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **jgaap.py / ifrs.py / statements.py を変更しないこと**
   - Part 2 が完了済みのため、jgaap.py / ifrs.py は変更不要
   - jgaap.py の `PeriodType` は Part 2 のフィードバック対応で **既に削除済み**（`__all__` からも除去済み）
   - statements.py は sector/ と直接結合していないため変更不要
   - `sector/__init__.py` も変更不可（ルール 1）

4. **`stubgen` を実行しないこと**
   統合タスクで一括実行する。

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/` 配下の既存ファイルを変更してはならない

## 推奨事項

6. **sector/__init__.py の `_REGISTRY_MAP` は触らない**
   - `__init__.py` 変更禁止のため、registry 初期化ロジックは現状維持
   - `SectorRegistry` の API リネームは `__init__.py` 経由の呼び出しに影響しないことを確認すること
   - `get_sector_registry()` の戻り値型は `SectorRegistry` のため、メソッド名変更は透過的に反映される

7. **テストファイルの命名規則**
   - 既存のテストファイルを変更する（新規テストファイルは作成しない）

8. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# PART 3 — sector/ スリム化 + sector_key リネーム

## 0. 位置づけ

### WAVE_4.md との対応

WAVE_4.md §Part 3:

> NOW.md §Q11 の設計判断:
> - `SectorConceptMapping.canonical_key` → `sector_key` にリネーム（スコープの混同を防ぐ）
> - `label_ja`, `label_en`, `display_order`, `statement_type`, `period_type`, `is_total` を削除（concept_sets + TaxonomyResolver で自動化）

### 依存先

| 依存先 | 用途 | 種類 |
|--------|------|------|
| Part 1b (完了済み) | normalize.py が concept_sets ベースに接続済み。taxonomy_root ありの場合は sector レガシーフォールバックを使わない | 前提 |
| Part 2 (完了済み) | jgaap.py / ifrs.py がスリム化済み。`PeriodType` は jgaap.py から **既に削除済み** | 前提 |
| `taxonomy/concept_sets.py` (Part 1a) | concept_sets で display_order / is_total / statement_type を代替 | 読取専用 |
| `standards/jgaap.py` (Part 2 完了) | `all_canonical_keys()` で general_equivalent の検証に使用 | 読取専用 |

### 他 Part とのファイル衝突

- Part 2 は jgaap.py / ifrs.py のみ変更済みで、sector/ は一切未変更 → **衝突なし**
- Part 4 は `canonical_keys.py` 新規作成 + jgaap/ifrs の文字列リテラル → StrEnum 置換 → **衝突なし**
- normalize.py は Part 2 が `_get_concept_order_legacy()` を変更済み。本 Part は sector レガシーフォールバックブロック（`# TODO(Part 3)` 付き）と `get_canonical_key_for_sector()` を変更 → **変更箇所が異なるため衝突なし**

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| WAVE_4.md §3.1-3.7 | 高 | Part 3 の設計方針 |
| NOW.md §Q11 | 高 | sector_key リネームの意思決定 |
| docs/QAs/INDEX.md | 中 | 業種固有タクソノミの調査結果 |

---

## 1. 背景知識

### 1.1 現在の `_base.py` の `SectorConceptMapping` (11 フィールド)

| フィールド | 型 | 用途 | 代替元 | **Part 3 判定** |
|-----------|-----|------|--------|:--------:|
| `concept` | `str` | ローカル名 | — | **維持** |
| `canonical_key` | `str` | 業種内ローカルキー | — | **リネーム → `sector_key`** |
| `label_ja` | `str` | 日本語ラベル | TaxonomyResolver | **削除** |
| `label_en` | `str` | 英語ラベル | TaxonomyResolver | **削除** |
| `statement_type` | `StatementType \| None` | PL/BS/CF | concept_sets | **削除** |
| `period_type` | `PeriodType` | instant/duration | concept_sets + XSD | **削除** |
| `industry_codes` | `frozenset[str]` | 適用業種コード | — | **維持** |
| `display_order` | `int` | 表示順序 | concept_sets | **削除** |
| `general_equivalent` | `str \| None` | jgaap canonical_key | — | **維持** |
| `is_total` | `bool` | 合計行 | concept_sets preferredLabel | **削除** |
| `mapping_note` | `str` | 備考 | — | **維持** |

### 1.2 現在の業種モジュール概要

| モジュール | 概念数 | 業種コード | suffix | PL | BS | CF |
|-----------|:------:|-----------|--------|:--:|:--:|:--:|
| banking.py (733行) | 45 | bk1, bk2 | BNK | 20 | 15 | 10 |
| insurance.py (807行) | 49 | in1, in2 | INS | 32 | 17 | 0 |
| construction.py (351行) | 20 | cns | CNS | 12 | 8 | 0 |
| railway.py (229行) | 11 | rwy | RWY | 11 | 0 | 0 |
| securities.py (265行) | 13 | sec | SEC | 8 | 5 | 0 |

banking.py 内訳: `_PL_BANKING_MAPPINGS`(13) + `_COMMON_PL_MAPPINGS`(7) + `_BS_BANKING_MAPPINGS`(12) + `_COMMON_BS_MAPPINGS`(3) + `_CF_DIRECT_MAPPINGS`(4) + `_CF_INDIRECT_MAPPINGS`(3) + `_COMMON_CF_MAPPINGS`(3) = **45**

### 1.3 `SectorRegistry` の現在の API

| メソッド/プロパティ | **Part 3 判定** | 理由 |
|-------------------|:--------:|------|
| `lookup(concept)` | **維持** | concept → mapping の正引き |
| `canonical_key(concept)` | **リネーム → `sector_key(concept)`** | 名前が misleading |
| `reverse_lookup(key)` | **維持** (引数は sector_key) | key → mapping の逆引き |
| `mappings_for_statement(st)` | **削除** | concept_sets で代替。normalize.py の TODO(Part 3) ブロックも同時に削除 |
| `all_mappings()` | **維持** | 全マッピング一覧 |
| `all_canonical_keys()` | **リネーム → `all_sector_keys()`** | |
| `get_profile()` | **維持** | プロファイル取得 |
| `to_general_key(concept)` | **維持** | sector concept → jgaap canonical_key |
| `from_general_key(key)` | **維持** | jgaap canonical_key → sector concepts |
| `to_general_map()` | **維持** | 一括変換辞書 |
| `known_concepts()` | **削除** | concept_sets で代替 |
| `canonical_key_count` (property) | **リネーム → `sector_key_count`** | |
| `__len__`, `__repr__` | **維持** | |

### 1.4 `_base.py` の内部インデックス

| インデックス | **Part 3 判定** |
|------------|:--------:|
| `_concept_index: dict[str, SectorConceptMapping]` | **維持** |
| `_key_index: dict[str, SectorConceptMapping]` | **維持** (キーが `sector_key` に) |
| `_statement_index: dict[StatementType \| None, tuple]` | **削除** |
| `_general_index: dict[str, list[SectorConceptMapping]]` | **維持** |
| `_all_canonical_keys: frozenset[str]` | **リネーム → `_all_sector_keys`** |
| `_known_concepts: frozenset[str]` | **削除** |

### 1.5 `_base.py` の `PeriodType`

`_base.py` L47 に独自定義:
```python
PeriodType = Literal["instant", "duration"]
```

jgaap.py からは import しておらず、完全に独立。`SectorConceptMapping.period_type` フィールド削除に伴い `PeriodType` も `_base.py` から削除する。`__all__` からも外す。

### 1.6 normalize.py の sector 関連箇所

#### `_get_known_concepts_legacy()` (L192-207)

```python
# TODO(Part 3): Part 3 で SectorRegistry.mappings_for_statement() が
# 削除される際、このブロックも削除すること。
if industry_code is not None and standard in (...):
    from edinet.financial.sector import get_sector_registry
    reg = get_sector_registry(industry_code)
    if reg is not None:
        sector_concepts = frozenset(
            m.concept for m in reg.mappings_for_statement(statement_type)
        )
        return sector_concepts | base
```

**判定**: `mappings_for_statement()` を削除するため、このブロックも **削除**。
taxonomy_root ありの場合は concept_sets 経由で業種別セットが取得されるため、レガシーフォールバックでの sector 合算は不要。

#### `_get_concept_order_legacy()` (L252-270)

```python
# TODO(Part 3): Part 3 で SectorRegistry.mappings_for_statement() が
# 削除される際、このブロックも削除すること。
if industry_code is not None and standard in (...):
    ...
    sector_order = {
        m.concept: m.display_order
        for m in reg.mappings_for_statement(statement_type)
    }
    ...
```

**判定**: 同様に **削除**。

#### `get_canonical_key_for_sector()` (L408-438)

```python
def get_canonical_key_for_sector(local_name, standard=None, industry_code=None):
    ...
    reg = get_sector_registry(industry_code)
    if reg is not None:
        key = reg.canonical_key(local_name)  # ← リネーム対象
        ...
```

**判定**: `reg.canonical_key()` → `reg.sector_key()` に **リネーム**。関数自体は維持。

### 1.7 各業種モジュールのモジュールレベル関数エイリアス

全 5 モジュールで以下のパターンが使われている:

```python
lookup = registry.lookup
canonical_key = registry.canonical_key          # → sector_key = registry.sector_key
reverse_lookup = registry.reverse_lookup
mappings_for_statement = registry.mappings_for_statement  # → 削除
all_mappings = registry.all_mappings
all_canonical_keys = registry.all_canonical_keys  # → all_sector_keys = registry.all_sector_keys
to_general_key = registry.to_general_key
from_general_key = registry.from_general_key
known_concepts = registry.known_concepts        # → 削除
```

banking.py と insurance.py は追加で固有ヘルパー関数を持つ:
- banking: `is_banking_concept()`, `general_equivalent()`, `banking_to_general_map()`, `banking_specific_concepts()`
- insurance: `insurance_specific_concepts()`, `insurance_to_general_map()`

### 1.8 バリデーション (`_validate()`) の現在のチェック

| チェック | **Part 3 判定** |
|---------|:--------:|
| concept 重複 | **維持** |
| canonical_key 重複 | **維持** (sector_key に) |
| period_type 検証 | **削除** |
| concept / canonical_key 非空 | **維持** (sector_key に) |
| label_ja / label_en 非空 | **削除** |
| industry_codes 非空 + サブセット検証 | **維持** |
| display_order >= 1 | **削除** |
| display_order 一意性 (statement_type 内) | **削除** |

---

## 2. ゴール

1. `SectorConceptMapping` から 6 フィールド（`label_ja`, `label_en`, `statement_type`, `period_type`, `is_total`, `display_order`）を削除し、`canonical_key` → `sector_key` にリネームする
2. `_base.py` から `PeriodType` 型を削除する
3. `SectorRegistry` から `mappings_for_statement()` / `known_concepts()` を削除し、`canonical_key()` → `sector_key()` 等のリネームを行う
4. 全 5 業種モジュール（banking / insurance / construction / railway / securities）のマッピングエントリを新フォーマットに書き換える
5. normalize.py の sector レガシーフォールバックブロック（TODO(Part 3) 付き 2 箇所）を削除し、`get_canonical_key_for_sector()` 内の `reg.canonical_key()` → `reg.sector_key()` にリネームする
6. 全テストを更新する

### 非ゴール（スコープ外）

- `sector/__init__.py` の変更 → 統合タスクの責務
- `general_equivalent` の文字列リテラル → `CK.*` StrEnum 定数化 → Part 4 の責務
- jgaap.py / ifrs.py の変更 → Part 2 で完了済み
- concept_sets の機能追加 → Part 1a で完了済み

### 非機能要件

- 全テスト（1,324+ 件）がパス
- `uv run ruff check` クリーン
- 破壊的変更（API リネーム）は一気に実施、deprecated wrapper は置かない

---

## 3. 設計

### 3.1 `SectorConceptMapping` の変更後

```python
# Before (11 フィールド)
@dataclass(frozen=True, slots=True)
class SectorConceptMapping:
    concept: str
    canonical_key: str
    label_ja: str
    label_en: str
    statement_type: StatementType | None
    period_type: PeriodType
    industry_codes: frozenset[str]
    display_order: int
    general_equivalent: str | None = None
    is_total: bool = False
    mapping_note: str = ""

# After (5 フィールド)
@dataclass(frozen=True, slots=True)
class SectorConceptMapping:
    concept: str
    sector_key: str                          # ← リネーム
    industry_codes: frozenset[str]
    general_equivalent: str | None = None    # jgaap canonical_key への翻訳
    mapping_note: str = ""
```

### 3.2 `SectorRegistry` の変更後

```python
class SectorRegistry:
    def __init__(self, *, profile, mappings):
        # 内部インデックス:
        # _concept_index: dict[str, SectorConceptMapping]  — 維持
        # _key_index: dict[str, SectorConceptMapping]      — キーが sector_key に
        # _general_index: dict[str, list]                  — 維持
        # _all_sector_keys: frozenset[str]                 — リネーム
        # 削除: _statement_index, _known_concepts

    # 維持（リネームなし）
    def lookup(self, concept: str) -> SectorConceptMapping | None: ...
    def reverse_lookup(self, key: str) -> SectorConceptMapping | None: ...
    def all_mappings(self) -> tuple[SectorConceptMapping, ...]: ...
    def get_profile(self) -> SectorProfile: ...
    def to_general_key(self, concept: str) -> str | None: ...
    def from_general_key(self, general_key: str) -> tuple[SectorConceptMapping, ...]: ...
    def to_general_map(self) -> dict[str, str]: ...

    # リネーム
    def sector_key(self, concept: str) -> str | None: ...    # 旧 canonical_key()
    def all_sector_keys(self) -> frozenset[str]: ...         # 旧 all_canonical_keys()
    @property
    def sector_key_count(self) -> int: ...                   # 旧 canonical_key_count

    # 削除
    # mappings_for_statement() — concept_sets で代替
    # known_concepts() — concept_sets で代替
```

### 3.3 `to_general_map()` の変更

```python
# Before
def to_general_map(self) -> dict[str, str]:
    return {
        m.canonical_key: m.general_equivalent
        for m in self._all_mappings
        if m.general_equivalent is not None
    }

# After
def to_general_map(self) -> dict[str, str]:
    return {
        m.sector_key: m.general_equivalent
        for m in self._all_mappings
        if m.general_equivalent is not None
    }
```

### 3.4 `from_general_key()` のソート変更

`from_general_key()` は現在 `display_order` でソートしている。削除後はタプル定義順（`_general_index` の挿入順）をそのまま返す:

```python
# Before
def from_general_key(self, general_key: str) -> tuple[SectorConceptMapping, ...]:
    items = self._general_index.get(general_key, [])
    return tuple(sorted(items, key=lambda m: m.display_order))

# After
def from_general_key(self, general_key: str) -> tuple[SectorConceptMapping, ...]:
    return tuple(self._general_index.get(general_key, []))
```

### 3.5 各業種モジュールのマッピング変更例

```python
# Before (banking.py)
SectorConceptMapping(
    concept="OrdinaryIncomeBNK",
    canonical_key="ordinary_revenue_bnk",
    label_ja="経常収益",
    label_en="Ordinary income",
    statement_type=StatementType.INCOME_STATEMENT,
    period_type="duration",
    industry_codes=frozenset({"bk1", "bk2"}),
    display_order=1,
    general_equivalent="revenue",
    is_total=True,
    mapping_note="...",
)

# After
SectorConceptMapping(
    concept="OrdinaryIncomeBNK",
    sector_key="ordinary_revenue_bnk",
    industry_codes=frozenset({"bk1", "bk2"}),
    general_equivalent="revenue",
    mapping_note="...",
)
```

### 3.6 normalize.py の変更

```python
# _get_known_concepts_legacy() — TODO(Part 3) ブロック全体を削除
# _get_concept_order_legacy() — TODO(Part 3) ブロック全体を削除

# get_canonical_key_for_sector() — 内部呼び出しをリネーム
def get_canonical_key_for_sector(local_name, standard=None, industry_code=None):
    ...
    if reg is not None:
        key = reg.sector_key(local_name)  # 旧: reg.canonical_key(local_name)
        if key is not None:
            return key
    ...
```

---

## 4. 変更内容の詳細

### 4.1 `_base.py` の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| L37-41 `__all__` | `"PeriodType"` を削除 |
| L47 `PeriodType` | 削除（型定義 + docstring） |
| L32 `from typing import Literal` | 削除（PeriodType がなくなるため不要） |
| L34 `from edinet.models.financial import StatementType` | 削除（`statement_type` フィールド + `_statement_index` + `mappings_for_statement()` + `_validate()` の `for st in StatementType` が全て削除されるため不要） |
| L55-88 `SectorConceptMapping` | 6 フィールド削除、`canonical_key` → `sector_key` リネーム、docstring 更新 |
| L127-200 `SectorRegistry.__init__()` | `_statement_index` / `_known_concepts` 構築を削除、`_all_canonical_keys` → `_all_sector_keys`、`_key_index` のキーを `sector_key` に |
| L230-300 `_validate()` | `period_type` / `label_ja` / `label_en` / `display_order` チェック削除、`canonical_key` → `sector_key` |
| L310-340 `canonical_key()` | メソッド名を `sector_key()` にリネーム、docstring 更新 |
| L337-370 `mappings_for_statement()` | **メソッド全体を削除** |
| L375-380 `all_canonical_keys()` | `all_sector_keys()` にリネーム |
| L420-425 `canonical_key_count` | `sector_key_count` にリネーム |
| L427-430 `known_concepts()` | **メソッド全体を削除** |
| L418 `to_general_map()` | `m.canonical_key` → `m.sector_key` |
| L395-405 `from_general_key()` | `display_order` ソートを削除（定義順をそのまま返す）。docstring の「先頭が最包括的な概念（display_order 最小）」→「定義順」に更新 |
| `__repr__` | 確認済み: `canonical_key_count` は使用しておらず `mappings={len}` のみ → **変更不要** |

### 4.2 banking.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| 全 45 個のマッピングエントリ | 6 フィールド削除、`canonical_key=` → `sector_key=` |
| `BankingConceptMapping = SectorConceptMapping` | 維持（エイリアス） |
| `canonical_key = registry.canonical_key` | → `sector_key = registry.sector_key` |
| `mappings_for_statement = registry.mappings_for_statement` | **削除** |
| `all_canonical_keys = registry.all_canonical_keys` | → `all_sector_keys = registry.all_sector_keys` |
| `known_concepts = registry.known_concepts` | **削除** |
| `__all__` | `"canonical_key"` → `"sector_key"`、`"mappings_for_statement"` 削除、`"all_canonical_keys"` → `"all_sector_keys"`、`"known_concepts"` 削除 |
| `is_banking_concept()` | `m.general_equivalent` 参照は変更なし |
| `general_equivalent()` | `registry.to_general_key()` 委譲は変更なし |
| `banking_to_general_map()` | `registry.to_general_map()` 委譲は変更なし（内部で `sector_key` 使用に） |

### 4.3 insurance.py の変更箇所

banking.py と同様のパターン（`__all__` 更新を含む）。追加で:

| 箇所 | 変更内容 |
|------|---------|
| モジュールロード時検証 `_ins_count` | `"INS" in _m.concept` チェックは維持（concept フィールドは不変） |
| `InsuranceConceptMapping = SectorConceptMapping` | 維持 |

### 4.4 construction.py / railway.py / securities.py の変更箇所

banking.py と同様のパターン（固有ヘルパー関数なし）。全モジュールで `__all__` の `"canonical_key"` → `"sector_key"`、`"mappings_for_statement"` / `"known_concepts"` 削除、`"all_canonical_keys"` → `"all_sector_keys"` を実施。

### 4.5 normalize.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| `_get_known_concepts_legacy()` L192-207 | TODO(Part 3) ブロック全体を削除（`if industry_code is not None` の分岐） |
| `_get_concept_order_legacy()` L252-270 | TODO(Part 3) ブロック全体を削除（`if industry_code is not None` の分岐） |
| `get_canonical_key_for_sector()` L434 | `reg.canonical_key(local_name)` → `reg.sector_key(local_name)` |
| `_get_known_concepts_legacy()` シグネチャ | `industry_code` パラメータを **削除**（TODO ブロック削除後は参照されなくなるため） |
| `_get_concept_order_legacy()` シグネチャ | `industry_code` パラメータを **削除** |
| `get_known_concepts()` / `get_concept_order()` 内の呼び出し | レガシー関数への `industry_code` 引数渡しを削除 |

---

## 5. テスト計画

### 5.1 テスト原則

- Detroit 派（古典派）: モック不使用、公開 API のみテスト
- 削除されたフィールドを参照するテストは削除
- リネームされた API のテストは名前を更新

### 5.2 既存テストの変更一覧

#### test_sector_base.py

| テスト | 変更内容 |
|--------|---------|
| `TestSectorRegistryValidation` のフィクスチャ | マッピング構築を新フォーマットに。`label_ja` / `label_en` / `period_type` / `statement_type` / `display_order` / `is_total` を削除、`canonical_key` → `sector_key` |
| `test_duplicate_canonical_key` | → `test_duplicate_sector_key` にリネーム |
| `test_empty_label_ja` / `test_empty_label_en` | **削除** |
| `test_duplicate_display_order` | **削除** |
| `test_display_order_zero_or_negative` | **削除** |
| `test_invalid_period_type` | **削除** |
| `TestSectorRegistryAPI` のフィクスチャ | 新フォーマットに更新 |
| `test_canonical_key` | → `test_sector_key`（メソッド名変更） |
| `test_mappings_for_statement` | **削除** |
| `test_all_canonical_keys` | → `test_all_sector_keys` |
| `test_known_concepts` | **削除** |
| `test_canonical_key_count` | → `test_sector_key_count` |
| `TestStatementTypeNone` | **クラスごと削除**（statement_type フィールド自体が削除されるため） |
| `TestToGeneralMap` のアサーション | `m.canonical_key` → `m.sector_key` |

#### test_sector_banking.py

| テスト（実際の名前） | 変更内容 |
|--------|---------|
| `test_t01_lookup_returns_mapping` | `m.canonical_key` → `m.sector_key`、`m.label_ja` アサーション **削除** |
| `test_t03_canonical_key_returns_key` | → `test_t03_sector_key_returns_key`（`canonical_key()` → `sector_key()` 呼び出し） |
| `test_t04_canonical_key_returns_none_for_unknown` | → `test_t04_sector_key_returns_none_for_unknown` |
| `test_t07_lookup_and_reverse_roundtrip` | `m.canonical_key` → `m.sector_key` |
| `test_t08_pl_mappings_not_empty` | **削除**（`mappings_for_statement()` 削除のため） |
| `test_t09_bs_mappings_not_empty` | **削除** |
| `test_t10_cf_mappings_not_empty` | **削除** |
| `test_t11_all_mappings_count` | `mappings_for_statement()` を使用しているため **書き換え** → `assert len(all_mappings()) == 45` |
| `test_t12_all_canonical_keys_count` | → `test_t12_all_sector_keys_count`（`all_canonical_keys()` → `all_sector_keys()`） |
| `test_t13_concepts_unique` | 維持 |
| `test_t14_canonical_keys_unique` | → `test_t14_sector_keys_unique`（`m.canonical_key` → `m.sector_key`） |
| `test_t15_bs_period_type_instant` | **削除** |
| `test_t16_pl_period_type_duration` | **削除** |
| `test_t17_cf_period_type_duration` | **削除** |
| `test_t18_display_order_ascending_per_statement` | **削除** |
| `test_t19_display_order_unique_per_statement` | **削除** |
| `test_t20_labels_nonempty` | **削除** |
| `test_t21_net_income_canonical_key_matches_jgaap` 〜 `test_t25_all_common_concepts_match_jgaap` | `m.canonical_key` → `m.sector_key` |
| `test_t31_canonical_key_empty_string` | → `test_t31_sector_key_empty_string` |
| `test_t33_frozen_dataclass_immutable` | `m.canonical_key =` → `m.sector_key =` |
| `test_t35_direct_method_concepts_exist` | `m.statement_type` アサーション **削除**（statement_type フィールド削除のため） |
| `test_t36_indirect_method_concepts_exist` | 同上 |
| `test_t47_banking_specific_concepts_self_consistent` | `m.canonical_key` → `m.sector_key` があれば更新 |
| `test_t49_all_mappings_order_pl_bs_cf` | `m.statement_type` 参照を使用しているため **削除** |

#### test_sector_insurance.py

banking と同様のパターン。追加の注意点:
- `test_t11_all_mappings_count` は `mappings_for_statement()` 使用 → `assert len(all_mappings()) == 49` に書き換え
- `test_t21_display_order_positive` → **削除**
- `test_t28_profile_canonical_key_count` → `test_t28_profile_sector_key_count`
- `test_t46_all_mappings_order_pl_bs_cf` → `m.statement_type` 参照のため **削除**

#### test_sector_construction.py / test_sector_railway.py / test_sector_securities.py

banking と同様のパターン。各モジュール固有の `mappings_for_statement()` / `display_order` / `period_type` / `label_ja` / `label_en` / `statement_type` 参照テストを削除、`canonical_key` → `sector_key` リネーム。

#### test_sector_cross_validation.py

| テスト | 変更内容 |
|--------|---------|
| T06-T10 `TestGeneralEquivalent` | `to_general_map()` の戻り値キーが `sector_key` に変わるが、検証ロジック（`general_equivalent` 値が jgaap に存在するか）は変更なし |
| T13 `TestProfileConsistency::test_majority_concepts_have_suffix` | 維持（concept フィールドは不変） |
| T14 `TestDisplayOrderUniqueness` | **削除** |
| T16 `TestSectorConceptExistence` | 維持（concept フィールドは不変） |

#### test_normalize.py

| テスト | 変更内容 |
|--------|---------|
| T22 `test_banking_pl_contains_sector_concepts` | **削除**（sector レガシーフォールバック自体が削除されるため） |
| T23 `test_banking_pl_also_contains_jgaap_general` | **削除** |
| T24 `test_insurance_bs_contains_sector_concepts` | **削除** |
| T27 `test_canonical_key_sector_first` | `sector_key` 経由の動作テスト。テスト内容は維持（`get_canonical_key_for_sector()` の公開 API は変更なし） |
| T29 `test_concept_order_sector_has_banking_concepts` | **削除**（sector order レガシーフォールバックが削除されるため） |
| T30 `test_concept_order_none_industry_same_as_general` | 維持（industry_code=None のケース） |

### 5.3 新規テスト

| ID | テスト名 | 内容 | ファイル |
|----|---------|------|---------|
| N01 | `test_sector_key_via_registry` | `registry.sector_key("OrdinaryIncomeBNK")` が `"ordinary_revenue_bnk"` を返すこと（公開 API 経由でリネーム確認） | test_sector_base.py |
| N02 | `test_all_sector_keys_returns_frozenset` | `registry.all_sector_keys()` が frozenset を返し全キーを含むこと | test_sector_base.py |
| N03 | `test_legacy_fallback_no_sector_merge` | `get_known_concepts(JAPAN_GAAP, PL, industry_code="bk1")` が一般事業会社と同一結果（sector 合算されない）を返すこと | test_normalize.py |

---

## 6. 実装手順

### Step 1: `_base.py` — SectorConceptMapping + SectorRegistry 変更

1. `PeriodType` 定義を削除、`from typing import Literal` を削除
2. `__all__` から `"PeriodType"` を削除
3. `SectorConceptMapping` の 6 フィールド削除、`canonical_key` → `sector_key` リネーム
4. `SectorProfile` — 変更なし
5. `SectorRegistry.__init__()`:
   - `_statement_index` 構築を削除
   - `_known_concepts` 構築を削除
   - `_all_canonical_keys` → `_all_sector_keys`
   - `_key_index` のキーを `m.sector_key` に
6. `_validate()`:
   - `period_type` / `label_ja` / `label_en` / `display_order` チェック削除
   - `canonical_key` → `sector_key` 参照更新
7. `canonical_key()` → `sector_key()` リネーム
8. `mappings_for_statement()` 削除
9. `all_canonical_keys()` → `all_sector_keys()` リネーム
10. `known_concepts()` 削除
11. `canonical_key_count` → `sector_key_count` リネーム
12. `to_general_map()` 内の `m.canonical_key` → `m.sector_key`
13. `from_general_key()` の `display_order` ソート削除
14. `__repr__` の `canonical_key_count` → `sector_key_count`

```bash
uv run pytest tests/test_xbrl/test_sector_base.py -x
```

### Step 2: banking.py の変更

1. 全 45 マッピングエントリを新フォーマットに書き換え
2. モジュールレベル関数エイリアス: `canonical_key` → `sector_key`、`mappings_for_statement` / `known_concepts` 削除、`all_canonical_keys` → `all_sector_keys`
3. `BankingConceptMapping = SectorConceptMapping` — 維持
4. 固有ヘルパー関数: `canonical_key` 参照があれば `sector_key` に更新

```bash
uv run pytest tests/test_xbrl/test_sector_banking.py -x
```

### Step 3: insurance.py の変更

banking.py と同様のパターン。in1/in2 の `industry_codes` 分岐は維持。

```bash
uv run pytest tests/test_xbrl/test_sector_insurance.py -x
```

### Step 4: construction.py / railway.py / securities.py の変更

banking.py と同様のパターン。

```bash
uv run pytest tests/test_xbrl/test_sector_construction.py tests/test_xbrl/test_sector_railway.py tests/test_xbrl/test_sector_securities.py -x
```

### Step 5: normalize.py の変更

1. `_get_known_concepts_legacy()` の TODO(Part 3) ブロック（`if industry_code is not None` 分岐）を **削除**
2. `_get_concept_order_legacy()` の TODO(Part 3) ブロックを **削除**
3. `get_canonical_key_for_sector()` 内の `reg.canonical_key(local_name)` → `reg.sector_key(local_name)`

```bash
uv run pytest tests/test_xbrl/test_normalize.py -x
```

### Step 6: テスト更新

1. `test_sector_base.py` — フィクスチャ更新、削除テスト除去、リネーム
2. `test_sector_banking.py` — フィールド参照更新、不要テスト削除
3. `test_sector_insurance.py` — 同上
4. `test_sector_construction.py` — 同上
5. `test_sector_railway.py` — 同上
6. `test_sector_securities.py` — 同上
7. `test_sector_cross_validation.py` — display_order テスト削除、リネーム反映
8. `test_normalize.py` — sector レガシーフォールバックテスト削除、新規テスト追加

### Step 7: 回帰テスト

```bash
uv run pytest
uv run ruff check src/edinet/xbrl/sector/ src/edinet/xbrl/standards/normalize.py
```

---

## 7. 作成・変更ファイル一覧

| ファイル | 操作 | 行数概算（差分） |
|---------|------|:--------:|
| `src/edinet/xbrl/sector/_base.py` | 変更 | **-196** (446 → ~250) |
| `src/edinet/xbrl/sector/banking.py` | 変更 | **-533** (733 → ~200) |
| `src/edinet/xbrl/sector/insurance.py` | 変更 | **-607** (807 → ~200) |
| `src/edinet/xbrl/sector/construction.py` | 変更 | **-251** (351 → ~100) |
| `src/edinet/xbrl/sector/railway.py` | 変更 | **-149** (229 → ~80) |
| `src/edinet/xbrl/sector/securities.py` | 変更 | **-185** (265 → ~80) |
| `src/edinet/xbrl/standards/normalize.py` | 変更 | **-30** (TODO ブロック削除 + リネーム) |
| `tests/test_xbrl/test_sector_base.py` | 変更 | **-80** (フィクスチャ簡素化 + テスト削除) |
| `tests/test_xbrl/test_sector_banking.py` | 変更 | **-100** |
| `tests/test_xbrl/test_sector_insurance.py` | 変更 | **-80** |
| `tests/test_xbrl/test_sector_construction.py` | 変更 | **-40** |
| `tests/test_xbrl/test_sector_railway.py` | 変更 | **-30** |
| `tests/test_xbrl/test_sector_securities.py` | 変更 | **-30** |
| `tests/test_xbrl/test_sector_cross_validation.py` | 変更 | **-20** |
| `tests/test_xbrl/test_normalize.py` | 変更 | **-20** (sector テスト削除 + 新規テスト追加) |
| **合計** | | **-2,350** |

---

## 8. 設計判断の記録

### Q1: `mappings_for_statement()` を削除して大丈夫か？

**A**: normalize.py の `_get_known_concepts_legacy()` / `_get_concept_order_legacy()` で呼ばれているが、これらの TODO(Part 3) ブロック自体を Part 3 で同時に削除する。taxonomy_root ありの場合は Part 1b で concept_sets 経由に切り替え済み。taxonomy_root なしの場合でも、一般事業会社概念（jgaap/ifrs）のみでレガシーフォールバックが機能する。sector レガシーフォールバックの削除は sector 合算がなくなることを意味するが、taxonomy_root なしの利用ケース自体がフォールバック用途のため許容範囲。

### Q2: `known_concepts()` を削除して大丈夫か？

**A**: normalize.py の `_get_known_concepts_legacy()` 内で sector 合算に使われている（間接的に `mappings_for_statement()` 経由）。Q1 と同じく TODO(Part 3) ブロック削除で安全に除去可能。外部からの直接呼び出しは `test_sector_*.py` のテストのみ。

### Q3: sector レガシーフォールバック削除の影響は？

**A**: `get_known_concepts(JAPAN_GAAP, PL, industry_code="bk1")` を `taxonomy_root=None` で呼ぶと、削除前は「一般事業会社 PL 概念 + 銀行業 PL 概念」が返されていたが、削除後は「一般事業会社 PL 概念のみ」が返される。`taxonomy_root` が指定されている場合は concept_sets 経由で業種別セットが返されるため問題ない。この変更は API の振る舞い変更だが、レガシーフォールバック自体が暫定措置であり、taxonomy_root を指定する正規パスを推奨する設計のため許容する。

### Q4: `from_general_key()` の `display_order` ソート削除の影響は？

**A**: `from_general_key()` は「jgaap の canonical_key に対応する sector 概念の一覧」を返す。多くの場合 1:1 対応のため影響は軽微。複数対応の場合もタプル定義順がそのまま返されるが、利用側は順序に依存していない（テストも順序非依存のアサーション）。

### Q5: `sector/__init__.py` を変更しなくて大丈夫か？

**A**: `__init__.py` は `get_sector_registry()` → `SectorRegistry` を返す。`SectorRegistry` のメソッド名が変わる（`canonical_key()` → `sector_key()` 等）が、`__init__.py` 自体は `SectorRegistry` の **インスタンスを返す** だけなので、メソッドリネームは透過的に反映される。`__init__.py` 内で `canonical_key` を文字列として参照している箇所はない。唯一の影響は `_register_all()` 内の `reg.get_profile().industry_codes` だが `get_profile()` は変更なしのため問題ない。

### Q6: `SectorProfile` は変更するか？

**A**: 変更しない。`SectorProfile` のフィールド（`sector_id`, `display_name_ja`, `display_name_en`, `industry_codes`, `concept_suffix`, `pl_structure_note`, `has_consolidated_template`, `cf_method`）は全て会計基準プロファイル情報であり、concept_sets では代替できない。

---

## 9. 実行チェックリスト

- [ ] `_base.py` — `PeriodType` 削除、`SectorConceptMapping` 6 フィールド削除 + リネーム
- [ ] `_base.py` — `SectorRegistry` メソッド削除 + リネーム
- [ ] `banking.py` — 45 マッピング新フォーマット + エイリアス + `__all__` 更新
- [ ] `insurance.py` — マッピング新フォーマット + エイリアス + `__all__` 更新
- [ ] `construction.py` — マッピング新フォーマット + エイリアス + `__all__` 更新
- [ ] `railway.py` — マッピング新フォーマット + エイリアス + `__all__` 更新
- [ ] `securities.py` — マッピング新フォーマット + エイリアス + `__all__` 更新
- [ ] `normalize.py` — TODO(Part 3) ブロック 2 箇所削除 + `sector_key()` リネーム + レガシー関数の `industry_code` パラメータ削除
- [ ] テスト更新（7 テストファイル）
- [ ] `uv run pytest` — 全テストパス
- [ ] `uv run ruff check src/edinet/xbrl/sector/ src/edinet/xbrl/standards/normalize.py` — クリーン

---

## フィードバック反映サマリー（第 1 回）

| # | 指摘 | 重要度 | 判定 | 対応 |
|---|------|--------|------|------|
| 1 | banking 概念数 43→45 | 高 | **妥当** | §1.2 / §4.2 / Step 2 / チェックリストを 45 に修正 |
| 2 | jgaap.py PeriodType 削除が宙に浮いている | 高 | **事実と異なる**: Part 2 フィードバック対応で既に削除済み（grep 確認済み） | ルール 3 に「PeriodType は既に削除済み」を明記して矛盾を解消 |
| 3 | テスト番号と実名の不一致 | 高 | **妥当** | §5.2 banking を実際のテスト名（`test_t01_lookup_returns_mapping` 等）で全面書き換え |
| 4 | T11 が mappings_for_statement() 使用 | 高 | **妥当** | `test_t11_all_mappings_count` を `assert len(all_mappings()) == 45` に書き換える旨を明記 |
| 5 | T01 の canonical_key / label_ja 未対応 | 高 | **妥当** | §5.2 banking テーブルに T01 の `m.canonical_key` → `m.sector_key`、`m.label_ja` 削除を追記 |
| 6 | T35/T36/T49 の statement_type 参照 | 中 | **妥当** | §5.2 banking テーブルに T35/T36/T49 の statement_type 関連変更を追記 |
| 7 | sector モジュールの `__all__` 更新漏れ | 中 | **妥当** | §4.2 に `__all__` 更新行を追加。§4.3 / §4.4 / チェックリストにも反映 |
| 8 | `StatementType` import 不要化 | 中 | **妥当** | §4.1 に `from edinet.models.financial import StatementType` 削除を追記 |
| 9 | レガシー関数の industry_code 死コード化 | 中 | **妥当** | §4.5 に `industry_code` パラメータ削除 + 呼び出し元修正を追記。チェックリスト更新 |
| 10 | from_general_key() docstring 更新 | 中 | **妥当** | §4.1 の from_general_key 行に docstring 更新を明記 |
| 11 | insurance 概念数 | 低 | **確認済み**: 49 で正しい | 変更なし |
| 12 | `__repr__` の文字列リテラル確認 | 低 | **確認済み**: `canonical_key_count` は不使用（`mappings={len}` のみ） | §4.1 を「変更不要」に修正 |
| 13 | N01-N03 がフィールド存在チェック（Detroit 派） | 低 | **妥当** | N01-N03 を公開 API テスト（`registry.sector_key()` / `registry.all_sector_keys()`）に置換 |

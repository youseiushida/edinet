# Wave 4 / Part 1b — `normalize` + `statements` パイプライン接続

# エージェントが守るべきルール

あなたは Wave 4 / Part 1b を担当するエージェントです。
担当機能: normalize.py / statements.py を concept_sets ベースに接続

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/sector/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他 Part が担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/standards/normalize.py` (既存・変更)
   - `src/edinet/xbrl/statements.py` (既存・変更)
   - `tests/test_xbrl/test_normalize.py` (既存・変更)
   - `tests/test_xbrl/test_statements.py` (既存・変更)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存の公開 API の戻り値型を変更しないこと**
   - `get_known_concepts()` → `frozenset[str]`
   - `get_concept_order()` → `dict[str, int]`
   - `build_statements()` のシグネチャは維持
   - 新規キーワード引数の追加はデフォルト値付きで可

4. **`stubgen` を実行しないこと**
   統合タスクで一括実行する。

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/` 配下の既存ファイルを変更してはならない

## 推奨事項

6. **他モジュールの利用は import のみ**
   - Part 1a で変更済みの `edinet.xbrl.taxonomy.concept_sets` (derive_concept_sets 等) を import 可能
   - `edinet.financial.standards.jgaap`, `edinet.financial.standards.ifrs` は読み取り専用
   - `edinet.financial.sector` は読み取り専用

7. **テストファイルの命名規則**
   - 既存の `tests/test_xbrl/test_normalize.py`, `tests/test_xbrl/test_statements.py` に追加

8. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# PART 1b — `normalize` + `statements` パイプライン接続

## 0. 位置づけ

### WAVE_4.md との対応

WAVE_4.md §Part 1b:

> Part 1a で concept_sets が J-GAAP（全 23 業種）と IFRS の両方をカバーするようになった後、Part 1b で normalize.py / statements.py に接続する。

### 依存先

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `taxonomy/concept_sets.py` (Part 1a) | `derive_concept_sets()`, `ConceptSetRegistry` | import |
| `standards/jgaap.py` (Wave 2 L3) | レガシーフォールバック | import (読取専用) |
| `standards/ifrs.py` (Wave 2 L4) | レガシーフォールバック | import (読取専用) |
| `sector/` (Wave 3 L2-L4) | `get_sector_registry()` | import (読取専用) |
| `standards/detect.py` (Wave 2 L2) | `detect_accounting_standard()` | import (読取専用) |

### 他 Part とのファイル衝突

- Part 2 が `jgaap.py` / `ifrs.py` を変更するが、本 Part は `normalize.py` / `statements.py` のみ変更するため衝突なし
- Part 3 が `sector/_base.py` を変更するが、本 Part は `sector/` を読み取り専用として扱うため衝突なし

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| NOW.md §1.7 | 高 | あるべき姿（concept_sets → 分類、jgaap → canonical_key のみ） |
| NOW.md §Q7 | 高 | 年次タクソノミ更新時の変更不要を実現する設計 |
| C-1b | 中 | IFRS concept が jpigp_cor 名前空間を使う（module_group 分岐の根拠） |

---

## 1. 背景知識

### 1.1 現在の normalize.py (320 行)

`normalize.py` は `statements.py` と `jgaap.py` / `ifrs.py` の間のファサード。8 つの公開関数を持つ:

| 関数 | 行 | 用途 | lru_cache |
|------|:--:|------|:---------:|
| `get_canonical_key()` | 38 | concept → canonical_key | なし |
| `get_concept_for_key()` | 72 | canonical_key → concept | なし |
| `get_known_concepts()` | 100 | PL/BS/CF の既知概念集合 | **maxsize=32** |
| `get_concept_order()` | 136 | 表示順序の辞書 | **maxsize=32** |
| `cross_standard_lookup()` | 172 | 基準間概念変換 | なし |
| `get_known_concepts_for_sector()` | 201 | 業種考慮版 | なし |
| `get_concept_order_for_sector()` | 245 | 業種考慮版 | なし |
| `get_canonical_key_for_sector()` | 289 | 業種考慮版 | なし |

**問題点**: `get_known_concepts()` / `get_concept_order()` は `jgaap.py` / `ifrs.py` のハードコードから概念セットと表示順序を取得している。concept_sets が既にタクソノミから動的導出可能なのに、接続されていない。

### 1.2 現在の statements.py の _build_for_type() (L606-687)

`_build_for_type()` は `normalize` ファサードを経由して概念セットと順序を取得:

```python
# L669-679: DETAILED の処理（J-GAAP / IFRS / 未検出）
if self._industry_code is not None:
    known = get_known_concepts_for_sector(
        standard_enum, statement_type, self._industry_code,
    )
    order = get_concept_order_for_sector(
        standard_enum, statement_type, self._industry_code,
    )
else:
    known = get_known_concepts(standard_enum, statement_type)
    order = get_concept_order(standard_enum, statement_type)
```

sector の有無で分岐しており、`taxonomy_root` は **渡されていない**（`Statements._taxonomy_root` は保持されているが未使用）。

### 1.3 lru_cache の問題

`get_known_concepts()` / `get_concept_order()` に `@functools.lru_cache(maxsize=32)` がある。`taxonomy_root: Path` と `industry_code: str` を追加すると:

- 23 業種 × 3 諸表 × 2 基準 = 138 パターン → `maxsize=32` が不足
- `Path` の同一性が OS 依存（WSL パス正規化等）

**解決策**: `lru_cache` を外す。`derive_concept_sets()` 側に pickle キャッシュがあり、`ConceptSetRegistry.get()` は O(n) で n ≤ 数十のため実質無料。

### 1.4 既存テストの状況

**test_normalize.py** (378 行、30 テスト):
- T01-T21: `get_canonical_key`, `get_known_concepts`, `get_concept_order`, `cross_standard_lookup` 等
- T22-T30 (`TestSectorAware`): `get_known_concepts_for_sector`, `get_concept_order_for_sector`, `get_canonical_key_for_sector`

T22-T30 は sector 専用関数を直接テストしている。Part 1b で sector 関数を削除するため、これらのテストは **書き換え** が必要。

**test_statements.py**: `_build_for_type` を間接的にテスト（`income_statement()` / `balance_sheet()` 等を呼ぶ）。normalize の import を直接参照していないため、normalize のシグネチャ変更による影響は間接的。

---

## 2. ゴール

1. `get_known_concepts()` / `get_concept_order()` に `taxonomy_root` / `industry_code` パラメータを追加し、concept_sets ベースの概念セット・順序取得を実現する
2. `get_known_concepts_for_sector()` / `get_concept_order_for_sector()` を削除し、統合版 `get_known_concepts()` / `get_concept_order()` に一本化する
3. `statements.py` の `_build_for_type()` を簡素化し、`taxonomy_root` / `industry_code` を normalize に伝搬する
4. `taxonomy_root` が渡されない場合はレガシーフォールバック（jgaap/ifrs ハードコード）を維持する
5. `lru_cache` を除去する

### 非ゴール（スコープ外）

- jgaap.py / ifrs.py のスリム化 → Part 2 の責務
- sector/ のスリム化 → Part 3 の責務
- `get_canonical_key()` / `get_concept_for_key()` / `cross_standard_lookup()` の変更 → 本 Part では不変
- `get_canonical_key_for_sector()` の変更 → 本 Part では不変（sector/ に依存するため Part 3 で対応）

### 非機能要件

- 既存テスト（1,342 件 + Part 1a の 15 件）が壊れないこと
- `taxonomy_root=None` で既存動作が完全に維持されること（レガシーフォールバック）

---

## 3. 設計

### 3.1 normalize.py: `get_known_concepts()` の変更

```python
# 変更前 (L99-127)
@functools.lru_cache(maxsize=32)
def get_known_concepts(
    standard: AccountingStandard | None,
    statement_type: StatementType,
) -> frozenset[str]:

# 変更後
def get_known_concepts(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    *,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,
) -> frozenset[str]:
    """指定基準・諸表種別の既知概念集合を返す。

    ``taxonomy_root`` が指定されている場合、concept_sets（Presentation
    Linkbase 動的導出）を優先的に使用する。指定がない場合は jgaap/ifrs の
    ハードコードにフォールバック。

    Args:
        standard: 会計基準。``None`` / ``UNKNOWN`` は J-GAAP にフォールバック。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。指定時は concept_sets を優先。
        industry_code: 業種コード。``None`` は一般事業会社。

    Returns:
        concept ローカル名の frozenset。
    """
    if taxonomy_root is not None:
        cs = _get_concept_set(standard, statement_type, taxonomy_root, industry_code)
        if cs is not None:
            return cs.non_abstract_concepts()
    return _get_known_concepts_legacy(standard, statement_type, industry_code)
```

### 3.2 normalize.py: `get_concept_order()` の変更

```python
# 変更後
def get_concept_order(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    *,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,
) -> dict[str, int]:
    """指定基準・諸表種別の表示順序マッピングを返す。

    Args:
        standard: 会計基準。``None`` / 未知は J-GAAP フォールバック。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード。

    Returns:
        ``{concept_local_name: display_order}`` の辞書。
    """
    if taxonomy_root is not None:
        cs = _get_concept_set(standard, statement_type, taxonomy_root, industry_code)
        if cs is not None:
            return {
                e.concept: int(e.order)
                for e in cs.concepts
                if not e.is_abstract
            }
    return _get_concept_order_legacy(standard, statement_type, industry_code)
```

### 3.3 normalize.py: 新規ヘルパー関数

```python
from pathlib import Path

from edinet.xbrl.taxonomy.concept_sets import (
    ConceptSet,
    derive_concept_sets,
)


def _standard_to_module_group(standard: AccountingStandard | None) -> str:
    """会計基準 → module_group を返す。"""
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return "jpigp"
    return "jppfs"


def _get_concept_set(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    taxonomy_root: Path,
    industry_code: str | None,
) -> ConceptSet | None:
    """concept_sets から ConceptSet を取得する共通ヘルパー。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード。

    Returns:
        ConceptSet。取得できなかった場合は ``None``。
    """
    module_group = _standard_to_module_group(standard)
    registry = derive_concept_sets(taxonomy_root, module_group=module_group)
    ind = industry_code or ("ifrs" if module_group == "jpigp" else "cai")
    # NOTE: consolidated=True で連結テンプレートのみ使用。
    # 現在の _build_single_statement() は known_concepts を「この statement type に
    # 属する concept の集合」として使い、連結/個別フィルタは後段の
    # _filter_consolidated_with_fallback() で処理する。概念名自体は連結/個別で
    # 同一のため問題ないが、将来個別テンプレート固有の概念が必要になった場合は
    # consolidated パラメータの伝搬が必要。
    return registry.get(statement_type, consolidated=True, industry_code=ind)
```

### 3.4 normalize.py: レガシーフォールバック関数

旧 `get_known_concepts()` / `get_concept_order()` のロジックと、旧 `get_known_concepts_for_sector()` / `get_concept_order_for_sector()` の sector 合算ロジックを統合した内部関数。公開 API を一本化しつつ、`taxonomy_root=None` の後方互換を維持する。

`_get_known_concepts_legacy()` / `_get_concept_order_legacy()` の具体的な実装は §5.4 を参照。

### 3.5 normalize.py: sector 関数の削除

`get_known_concepts_for_sector()` と `get_concept_order_for_sector()` を **公開関数として削除** する。ただしロジック自体はレガシーフォールバック内部（`_get_known_concepts_legacy()` / `_get_concept_order_legacy()`）に移動して維持する。

理由:
- concept_sets が全 23 業種をカバーするため、`taxonomy_root` ありの場合は sector モジュールの手動リストを経由する必要がない
- `get_known_concepts(..., taxonomy_root=..., industry_code="bk1")` で concept_sets が業種別セットを直接返す
- `taxonomy_root=None` のレガシーフォールバックでは、内部関数が `get_sector_registry()` 経由で sector 概念を合算する従来動作を維持する

**Part 3 との連携**: レガシーフォールバック内の sector 合算は `reg.mappings_for_statement()` を呼ぶ。Part 3 で `SectorRegistry.mappings_for_statement()` を削除する際、`_get_known_concepts_legacy()` / `_get_concept_order_legacy()` 内の sector 合算ブロックも同時に削除すること。コード内に `# TODO(Part 3)` で明記する。

**`get_canonical_key_for_sector()` は維持する**。この関数は sector レジストリの `canonical_key()` を使い、Part 3 で `sector_key()` にリネームされる予定。Part 1b のスコープ外。

`__all__` から `get_known_concepts_for_sector`, `get_concept_order_for_sector` を削除。

### 3.6 statements.py: `_build_for_type()` の変更

```python
# 変更前 (L669-687)
# DETAILED の処理（J-GAAP / IFRS / 未検出）
if self._industry_code is not None:
    known = get_known_concepts_for_sector(
        standard_enum, statement_type, self._industry_code,
    )
    order = get_concept_order_for_sector(
        standard_enum, statement_type, self._industry_code,
    )
else:
    known = get_known_concepts(standard_enum, statement_type)
    order = get_concept_order(standard_enum, statement_type)

# 変更後
known = get_known_concepts(
    standard_enum, statement_type,
    taxonomy_root=self._taxonomy_root,
    industry_code=self._industry_code,
)
order = get_concept_order(
    standard_enum, statement_type,
    taxonomy_root=self._taxonomy_root,
    industry_code=self._industry_code,
)
```

import 文から `get_known_concepts_for_sector`, `get_concept_order_for_sector` を削除。

---

## 4. 変更内容の詳細

### 4.1 normalize.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| import 文 | `Path`, `ConceptSet`, `derive_concept_sets` の import 追加 |
| `__all__` | `get_known_concepts_for_sector`, `get_concept_order_for_sector` を削除 |
| `get_known_concepts()` | lru_cache 除去、`taxonomy_root` / `industry_code` パラメータ追加、concept_sets 優先ロジック |
| `get_concept_order()` | 同上 |
| `_standard_to_module_group()` | 新規: 会計基準 → module_group 変換 |
| `_get_concept_set()` | 新規: concept_sets から ConceptSet を取得する共通ヘルパー |
| `_get_known_concepts_legacy()` | 新規: 旧 `get_known_concepts` + 旧 `get_known_concepts_for_sector` のロジックを統合・内部関数化 |
| `_get_concept_order_legacy()` | 新規: 旧 `get_concept_order` + 旧 `get_concept_order_for_sector` のロジックを統合・内部関数化 |
| `get_known_concepts_for_sector()` | **削除**（ロジックは `_get_known_concepts_legacy()` に移動済み） |
| `get_concept_order_for_sector()` | **削除**（ロジックは `_get_concept_order_legacy()` に移動済み） |

### 4.2 statements.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| import 文 | `get_known_concepts_for_sector`, `get_concept_order_for_sector` を削除 |
| `_build_for_type()` の DETAILED 分岐 | sector 有無の if/else を統一呼び出しに置換 |

### 4.3 test_normalize.py の変更箇所

| 箇所 | 変更内容 |
|------|---------|
| import | `get_known_concepts_for_sector`, `get_concept_order_for_sector` を削除 |
| `TestSectorAware` (L274-378) | T22-T30 を書き換え: `get_known_concepts(..., industry_code=...)` 形式に |
| 新規テストクラス | concept_sets 経由テスト（タクソノミ実物） |

---

## 5. テスト計画

### 5.1 テスト原則

- Detroit 派（古典派）: モック不使用
- 既存テストの書き換えは最小限（sector 関数呼び出しの置換のみ）
- タクソノミ実物テストは `@pytest.mark.skipif` で条件付き

### 5.2 テスト一覧

**test_normalize.py に追加/変更:**

| ID | テスト名 | 内容 | 種別 |
|----|---------|------|------|
| T31 | `test_known_concepts_taxonomy_root_returns_concept_sets` | taxonomy_root ありで concept_sets 経由の known_concepts | タクソノミ実物 |
| T32 | `test_concept_order_taxonomy_root_returns_concept_sets` | taxonomy_root ありで concept_sets 経由の concept_order | タクソノミ実物 |
| T33 | `test_known_concepts_no_taxonomy_root_legacy` | taxonomy_root なしで従来のレガシーフォールバック | 単体 |
| T34 | `test_concept_order_no_taxonomy_root_legacy` | taxonomy_root なしで従来の順序フォールバック | 単体 |
| T35 | `test_known_concepts_ifrs_taxonomy_root` | IFRS + taxonomy_root で jpigp の concept_sets を使う | タクソノミ実物 |
| T36 | `test_known_concepts_industry_code_banking` | industry_code="bk1" で業種別 concept_sets | タクソノミ実物 |
| T37 | `test_known_concepts_ifrs_no_jpigp_dir_fallback` | taxonomy_root あるが jpigp なし → レガシーフォールバック | 単体 |
| T22' | `test_banking_pl_via_unified_api` | 旧 T22 を統合版 API で書き換え | 単体 |
| T23' | `test_banking_pl_also_has_general` | 旧 T23 を書き換え | 単体 |
| T25' | `test_none_industry_falls_back` | 旧 T25 を書き換え | 単体 |
| T26' | `test_ifrs_ignores_industry_code` | 旧 T26 を書き換え | 単体 |
| T29' | `test_concept_order_with_industry_code` | 旧 T29 を書き換え | 単体 |
| T30' | `test_concept_order_none_industry_same_as_general` | 旧 T30 を書き換え | 単体 |

**test_statements.py に追加:**

| ID | テスト名 | 内容 | 種別 |
|----|---------|------|------|
| T38 | `test_build_for_type_passes_taxonomy_root` | _build_for_type が taxonomy_root を normalize に伝搬 | 単体 |
| T39 | `test_build_for_type_passes_industry_code` | _build_for_type が industry_code を normalize に伝搬 | 単体 |

### 5.3 既存テストの書き換え方針

`TestSectorAware` クラスの T22-T30 は sector 専用関数を直接テストしている。書き換え方針:

- **T22-T26**: `get_known_concepts_for_sector(std, st, code)` → `get_known_concepts(std, st, industry_code=code)` に置換。ただし `taxonomy_root=None` のままなのでレガシーフォールバック経由。sector 固有概念は concept_sets でないとカバーされないため、一部テストの期待値を調整する必要あり
- **T27-T28**: `get_canonical_key_for_sector()` は変更なし → テスト変更不要
- **T29-T30**: `get_concept_order_for_sector(std, st, code)` → `get_concept_order(std, st, industry_code=code)` に置換

**重要**: `taxonomy_root=None` のレガシーフォールバックでは、`get_known_concepts()` は jgaap/ifrs のハードコードを使う。業種固有概念（`OrdinaryIncomeBNK` 等）はハードコードに含まれていないため、**T22（銀行業固有概念を含む）等は taxonomy_root ありのテストに変更する**か、sector レガシーフォールバックを維持するかの選択が必要。

**設計判断**: sector レガシーフォールバックを維持する。理由: Part 2/3 でスリム化が完了するまで、既存の sector テストが壊れないことが重要。具体的には:
- `taxonomy_root=None` かつ `industry_code` 指定の場合、レガシーフォールバック内で `get_sector_registry()` を使って sector 概念を合算する従来動作を維持する
- `taxonomy_root` あり の場合のみ concept_sets にディスパッチする

### 5.4 レガシーフォールバック内の sector 対応

`_get_known_concepts_legacy()` を拡張し、`industry_code` を受け取れるようにする:

```python
def _get_known_concepts_legacy(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    industry_code: str | None = None,
) -> frozenset[str]:
    """taxonomy_root なしの場合の従来動作。"""
    # 基本セット（jgaap/ifrs）
    if standard in (AccountingStandard.JAPAN_GAAP, None):
        base = frozenset(
            m.concept for m in jgaap.mappings_for_statement(statement_type)
        )
    elif standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        base = frozenset(
            m.concept for m in ifrs.mappings_for_statement(statement_type)
        )
    elif standard == AccountingStandard.US_GAAP:
        return frozenset()
    else:
        base = frozenset(
            m.concept for m in jgaap.mappings_for_statement(statement_type)
        )

    # sector 合算（industry_code ありかつ J-GAAP の場合）
    # TODO(Part 3): Part 3 で SectorRegistry.mappings_for_statement() が削除される際、
    # このブロックも削除すること。taxonomy_root ありの場合は concept_sets が
    # 業種別セットを直接返すため、sector レガシーフォールバックは不要になる。
    if industry_code is not None and standard in (
        AccountingStandard.JAPAN_GAAP, None,
    ):
        from edinet.financial.sector import get_sector_registry
        reg = get_sector_registry(industry_code)
        if reg is not None:
            sector_concepts = frozenset(
                m.concept for m in reg.mappings_for_statement(statement_type)
            )
            return sector_concepts | base

    return base
```

`_get_concept_order_legacy()` も同様に `industry_code` を受け取れるよう拡張。sector 順序の合算は既存の `get_concept_order_for_sector()` のロジック（sector 概念を前方配置、一般概念をオフセット）を移植する:

```python
def _get_concept_order_legacy(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    industry_code: str | None = None,
) -> dict[str, int]:
    """taxonomy_root なしの場合の従来表示順序。"""
    if standard in (AccountingStandard.JAPAN_GAAP, None):
        base = {
            m.concept: m.display_order
            for m in jgaap.mappings_for_statement(statement_type)
        }
    elif standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        base = {
            m.concept: m.display_order
            for m in ifrs.mappings_for_statement(statement_type)
        }
    elif standard == AccountingStandard.US_GAAP:
        return {}
    else:
        base = {
            m.concept: m.display_order
            for m in jgaap.mappings_for_statement(statement_type)
        }

    # sector 合算（既存 get_concept_order_for_sector() のロジックを移植）
    # TODO(Part 3): Part 3 で SectorRegistry.mappings_for_statement() が削除される際、
    # このブロックも削除すること。
    if industry_code is not None and standard in (
        AccountingStandard.JAPAN_GAAP, None,
    ):
        from edinet.financial.sector import get_sector_registry
        reg = get_sector_registry(industry_code)
        if reg is not None:
            sector_order = {
                m.concept: m.display_order
                for m in reg.mappings_for_statement(statement_type)
            }
            # sector 概念を前方配置、一般概念をオフセット
            max_sector = max(sector_order.values()) if sector_order else 0
            result = dict(sector_order)
            for concept, order in base.items():
                if concept not in result:
                    result[concept] = max_sector + 1 + order
            return result

    return base
```

---

## 6. テストの実装パターン

### T31-T32: concept_sets 経由テスト（タクソノミ実物）

```python
_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_skip_no_taxonomy = pytest.mark.skipif(
    _TAXONOMY_ROOT is None,
    reason="EDINET_TAXONOMY_ROOT が未設定",
)

@_skip_no_taxonomy
class TestConceptSetsIntegration:
    """concept_sets 接続の統合テスト。"""

    def test_known_concepts_taxonomy_root_returns_concept_sets(self) -> None:
        """T31: taxonomy_root ありで concept_sets 経由。"""
        result = get_known_concepts(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),
        )
        assert isinstance(result, frozenset)
        assert len(result) > 0
        assert "NetSales" in result

    def test_concept_order_taxonomy_root_returns_concept_sets(self) -> None:
        """T32: taxonomy_root ありで concept_sets 経由の表示順序。"""
        result = get_concept_order(
            AccountingStandard.JAPAN_GAAP,
            StatementType.INCOME_STATEMENT,
            taxonomy_root=Path(_TAXONOMY_ROOT),
        )
        assert isinstance(result, dict)
        assert len(result) > 0
        assert "NetSales" in result
```

### T33-T34: レガシーフォールバック

```python
def test_known_concepts_no_taxonomy_root_legacy(self) -> None:
    """T33: taxonomy_root なしで従来動作。"""
    result = get_known_concepts(
        AccountingStandard.JAPAN_GAAP,
        StatementType.INCOME_STATEMENT,
    )
    assert isinstance(result, frozenset)
    assert "NetSales" in result
```

### T22' 等: sector テストの書き換え

```python
def test_banking_pl_via_unified_api(self) -> None:
    """T22': 銀行業 PL に銀行業固有概念が含まれる（レガシーフォールバック）。"""
    result = get_known_concepts(
        AccountingStandard.JAPAN_GAAP,
        StatementType.INCOME_STATEMENT,
        industry_code="bk1",
    )
    assert isinstance(result, frozenset)
    assert "OrdinaryIncomeBNK" in result
```

### T38-T39: statements.py 伝搬テスト（Detroit 派）

`_build_for_type()` が `taxonomy_root` / `industry_code` を normalize に伝搬するかは、外部の公開 API（`income_statement()` 等）の結果を検証する。taxonomy_root を渡した Statements が concept_sets 由来の概念を使って正しい結果を返すことを間接的に確認する。

```python
class TestStatementsConceptSetsIntegration:
    """Statements と concept_sets の接続テスト。"""

    def test_build_for_type_passes_taxonomy_root(self) -> None:
        """T38: taxonomy_root を渡した Statements が concept_sets 由来の概念で構築される。

        taxonomy_root ありの場合、concept_sets から導出された概念セットが
        使われることを、結果の FinancialStatement が空でないことで確認する。
        taxonomy_root なしでも jgaap レガシーで動くため、差異の検証には
        concept_sets のみに存在する概念（jgaap にはない概念）が含まれるか
        で判断する。ただし実装上は known_concepts が concept_sets 由来になった
        時点で網羅性が上がるため、items 数が増えることを確認する。
        """
        # LineItem のヘルパーで PL items を作成し、build_statements に渡す
        # taxonomy_root=None と taxonomy_root=Path(...) の結果を比較
        # taxonomy_root ありの方が items 数 >= taxonomy_root なしを確認
        # （concept_sets は jgaap ハードコードより多くの概念をカバーするため）
        pass  # 実装時に具体化

    def test_build_for_type_passes_industry_code(self) -> None:
        """T39: industry_code を渡した Statements が業種別概念で構築される。"""
        # industry_code="bk1" で build_statements を呼び、
        # taxonomy_root ありの場合に銀行業固有概念が結果に含まれることを確認
        pass  # 実装時に具体化
```

**注**: T38/T39 は完全な E2E テストに近い。Detroit 派の原則に従い、LineItem ヘルパーで Fact を構築し `build_statements()` → `income_statement()` の結果を検証する。タクソノミ実物（`EDINET_TAXONOMY_ROOT`）が必要なため `@_skip_no_taxonomy` で条件付き実行。

---

## 7. 実装手順

### Step 1: normalize.py にヘルパー関数追加

1. import 追加: `Path`, `ConceptSet`, `derive_concept_sets`
2. `_standard_to_module_group()` 新規追加
3. `_get_concept_set()` 新規追加
4. `_get_known_concepts_legacy()` 新規追加（旧 `get_known_concepts` のロジック + sector 合算）
5. `_get_concept_order_legacy()` 新規追加（旧 `get_concept_order` のロジック + sector 合算）

### Step 2: normalize.py の公開関数を書き換え

1. `get_known_concepts()`: lru_cache 除去、シグネチャ変更、concept_sets 優先 + レガシーフォールバック
2. `get_concept_order()`: 同上
3. `get_known_concepts_for_sector()`: 削除
4. `get_concept_order_for_sector()`: 削除
5. `__all__` 更新

### Step 3: statements.py の変更

1. import から `get_known_concepts_for_sector`, `get_concept_order_for_sector` を削除
2. `_build_for_type()` の sector 分岐を統一呼び出しに置換

### Step 4: test_normalize.py の変更

1. import から `get_known_concepts_for_sector`, `get_concept_order_for_sector` を削除
2. `TestSectorAware` を書き換え（統合版 API に置換）
3. 新規テストクラス `TestConceptSetsIntegration` を追加

### Step 5: test_statements.py にテスト追加

1. T38, T39 を追加

### Step 6: 全テスト回帰確認

```bash
uv run pytest
uv run ruff check src/edinet/xbrl/standards/normalize.py src/edinet/xbrl/statements.py
```

---

## 8. 作成・変更ファイル一覧

| ファイル | 操作 | 行数概算（差分） |
|---------|------|:------:|
| `src/edinet/xbrl/standards/normalize.py` | 変更 | +60, -80 (実質 -20) |
| `src/edinet/xbrl/statements.py` | 変更 | -10 |
| `tests/test_xbrl/test_normalize.py` | 変更 | +60, -30 (実質 +30) |
| `tests/test_xbrl/test_statements.py` | 変更 | +30 |

---

## 9. 設計判断の記録

### Q1: sector 関数を削除するのに sector レガシーフォールバックを維持するのは矛盾しないか？

**A**: 矛盾しない。`get_known_concepts_for_sector()` / `get_concept_order_for_sector()` という **公開関数を削除** するが、レガシーフォールバック（`_get_known_concepts_legacy()`）の内部では `get_sector_registry()` を使って sector 概念を合算する。公開インターフェースを一本化しつつ、taxonomy_root なしの後方互換を維持する設計。

### Q2: lru_cache を外して性能問題はないか？

**A**: ない。`derive_concept_sets()` は pickle キャッシュを持ち、2 回目以降はデシリアライズのみ（~0.03 秒）。`ConceptSetRegistry.get()` は内部辞書の線形走査（n ≤ 数十）で実質 O(1)。レガシーフォールバックでは `jgaap.mappings_for_statement()` がモジュールレベルのタプルを返すため O(n) で十分高速。

### Q3: `_get_concept_set()` で `consolidated=True` を固定しているが問題ないか？

**A**: 現在の `_build_for_type()` のフローでは、consolidated フィルタは `_build_single_statement()` 内の `_filter_consolidated_with_fallback()` で処理される。`get_known_concepts()` は「どの concept がこの statement type に属するか」を返す役割で、連結/個別は問わない。

実害は小さいが、保証されているわけではない。タクソノミの Presentation Linkbase には `rol_NonConsolidatedBalanceSheet` のような個別用ロールが存在し、注記科目等で連結テンプレートと概念集合が異なるケースがありうる。`_get_concept_set()` の docstring に「現在は連結テンプレートのみ使用。将来個別テンプレート固有の概念が必要になった場合は consolidated パラメータの伝搬が必要」と明記する。

### Q4: IFRS で industry_code=None の場合のデフォルト "ifrs" は正しいか？

**A**: 正しい。`_get_concept_set()` 内で `ind = industry_code or ("ifrs" if module_group == "jpigp" else "cai")` としている。IFRS タクソノミは業種別サブディレクトリを持たず、全企業が同一テンプレートを使うため `"ifrs"` 固定で正しい。

### Q5: `test_normalize.py` の T22-T26 で taxonomy_root なしの sector テストは動くのか？

**A**: 動く。レガシーフォールバック（`_get_known_concepts_legacy()`）が `industry_code` を受け取り、`get_sector_registry()` で sector 概念を合算する従来動作を維持するため。Part 2/3 でスリム化が完了するまで、この後方互換パスは必要。

---

## 10. 実行チェックリスト

- [ ] normalize.py: `_standard_to_module_group()` 新規追加
- [ ] normalize.py: `_get_concept_set()` 新規追加
- [ ] normalize.py: `_get_known_concepts_legacy()` 新規追加（sector 合算対応）
- [ ] normalize.py: `_get_concept_order_legacy()` 新規追加（sector 合算対応）
- [ ] normalize.py: `get_known_concepts()` の lru_cache 除去 + シグネチャ変更
- [ ] normalize.py: `get_concept_order()` の lru_cache 除去 + シグネチャ変更
- [ ] normalize.py: `get_known_concepts_for_sector()` 削除
- [ ] normalize.py: `get_concept_order_for_sector()` 削除
- [ ] normalize.py: `__all__` 更新
- [ ] statements.py: import から sector 関数を削除
- [ ] statements.py: `_build_for_type()` を統一呼び出しに変更
- [ ] test_normalize.py: import から sector 関数を削除
- [ ] test_normalize.py: `TestSectorAware` T22-T26, T29-T30 を書き換え
- [ ] test_normalize.py: `TestConceptSetsIntegration` 新規追加 (T31-T37)
- [ ] test_statements.py: T38-T39 追加
- [ ] 既存テスト全件がパス
- [ ] `uv run ruff check` クリーン

---

## フィードバック反映サマリー（第 1 回）

| # | 指摘 | 重要度 | 判定 | 対応 |
|---|------|:------:|------|------|
| A-1 | `_get_concept_set()` で `consolidated=True` 固定の注記 | 中 | **妥当** | `_get_concept_set()` の docstring と §9 Q3 に「現在は連結テンプレートのみ使用。将来個別テンプレート固有の概念が必要になった場合は consolidated パラメータの伝搬が必要」と明記 |
| A-2 | sector レガシーフォールバックの `mappings_for_statement()` が Part 3 で削除される | 高 | **妥当** | §3.5 に Part 3 との連携を明記。`_get_known_concepts_legacy()` / `_get_concept_order_legacy()` 内の sector 合算ブロックに `# TODO(Part 3)` を追加。WAVE_4.md Part 3 実装ステップに「normalize.py の legacy 内 sector 合算を削除」を含める |
| A-3 | `_get_concept_order_legacy()` の sector 合算ロジックが未設計 | 高 | **妥当** | §5.4 に具体的なコード例を追加。既存の `get_concept_order_for_sector()` のオフセットロジック（`max_sector + 1 + order` で sector 前方配置）を移植 |
| B-3 | `__all__` の re-export 確認 | 軽微 | **確認済み: 問題なし** | `statements.py` の `__all__` は `["build_statements", "Statements"]` のみで normalize 関数の re-export なし |
| B-4 | T38/T39 のテスト実装パターン不足 | 中 | **妥当** | §6 に T38/T39 のコード例を追加。Detroit 派で `build_statements()` → `income_statement()` の結果を検証する方針を明記 |
| C-1 | 「公開 API 削除、ロジックは内部移動」の明確化 | 軽微 | **妥当** | §3.5 に一文追加:「公開関数として削除するが、ロジック自体はレガシーフォールバック内部に移動して維持」 |
| C-2 | 行番号が Part 1a で既にずれている可能性 | 軽微 | **妥当** | §4.1 / §4.2 の表から行番号列を削除し、関数名での特定に統一 |

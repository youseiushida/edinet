# Wave 3 統合タスク — 並列実装完了後の統合計画

## 0. 概要

Wave 3 の 4 レーン（L1: normalize + statements, L2: banking, L3: insurance, L4: construction/railway/securities）が並列完了した後に実施する統合タスク。並列安全ルールにより各レーンが独立して作成した成果物を一つのコヒーレントなパッケージに統合する。

**前提条件**: 4 レーン全てが完了し、`uv run pytest` が全パスしていること。

**統合タスクの実施者**: 人間またはエージェント 1 名が順序通りに実施する（並列不可）。

---

## 1. 統合が必要な理由

並列安全ルールにより以下の制約があった:

| 制約 | 理由 | 統合で解決 |
|------|------|-----------|
| `__init__.py` 変更禁止 | 複数レーンの同時編集によるマージコンフリクト防止 | 全 `__init__.py` を一括更新 |
| 他レーンのファイル変更禁止 | ファイル排他制御 | レーン間の接続コードを追加 |
| `stubgen` 実行禁止 | stubs/ の同時更新によるコンフリクト防止 | 統合後に一括生成 |
| レーン間の実行時依存禁止 | 未完成モジュールへの依存防止 | 全モジュール完成後に相互接続 |

---

## 2. 統合ステップ一覧

| Step | 内容 | 影響ファイル | リスク |
|------|------|------------|--------|
| 1 | sector データクラスの統一 | `sector/*.py` | 中 |
| 2 | `sector/__init__.py` の更新 | `sector/__init__.py` | 低 |
| 3 | `standards/__init__.py` の更新 | `standards/__init__.py` | 低 |
| 4 | `xbrl/__init__.py` の更新 | `xbrl/__init__.py` | 低 |
| 5 | `PeriodType` の集約 | `_types.py`(新規), 各モジュール | 中 |
| 6 | normalize と sector の接続 | `standards/normalize.py` | 高 |
| 7 | stubgen 一括実行 | `stubs/` 配下全体 | 低 |
| 8 | 全テスト + リント | — | — |
| 9 | E2E 回帰テスト | `tools/` | 低 |

---

## 3. Step 1: sector データクラスの統一

### 3.1 現状

Wave 3 完了時点で 3 種類のデータクラスが存在する:

| Lane | データクラス | 定義場所 | フィールド |
|------|------------|---------|-----------|
| L2 | `BankingConceptMapping` | `sector/banking.py` | `concept`, `canonical_key`, `label_ja`, `label_en`, `statement_type: StatementType \| None`, `period_type`, `is_total`, `display_order`, `general_equivalent`, `industry_codes`, `mapping_note` |
| L3 | `InsuranceConceptMapping` | `sector/insurance.py` | `concept`, `canonical_key`, `label_ja`, `label_en`, `statement_type: StatementType \| None`, `period_type`, `is_total`, `display_order`, `general_equivalent`, `industry_codes`, `mapping_note` |
| L4 | `SectorConceptMapping` | `sector/_base.py` | `concept`, `canonical_key`, `label_ja`, `label_en`, `statement_type: StatementType` (**None 不可**), `period_type`, `industry_codes`, `display_order`, `general_equivalent`, `is_total`, `mapping_note` |

### 3.2 統一方針

L4 の `SectorConceptMapping` + `SectorRegistry` を**全 sector モジュールの共通基底型**として採用する。

**変更内容:**

1. **`SectorConceptMapping.statement_type` を `StatementType | None` に拡張する**
   - L2/L3 は KPI 概念（`statement_type=None`）を持つ可能性がある
   - L4 の 3 業種は現時点で KPI を持たないため影響なし

2. **`BankingConceptMapping` → `SectorConceptMapping` に置換**
   - `banking.py` 内の `BankingConceptMapping` dataclass 定義を削除
   - `from edinet.financial.sector._base import SectorConceptMapping` を import
   - 全マッピングタプルの型を `SectorConceptMapping` に変更
   - 手書きの API 関数群（`lookup`, `canonical_key`, `reverse_lookup` 等）を削除
   - `_registry = SectorRegistry(mappings=..., profile=_PROFILE)` を作成
   - モジュールレベル関数として公開（`lookup = _registry.lookup` 等）

3. **`InsuranceConceptMapping` → `SectorConceptMapping` に置換**
   - 同上のパターンで置換
   - `insurance_sub_type` 等の保険固有フィールドがある場合は `mapping_note` に情報を含める

4. **`BankingProfile` / `InsuranceProfile` → `SectorProfile` に置換**
   - L2/L3 固有のフィールド（`cf_method`, `has_consolidated_template` 等）は `SectorProfile` に追加するか、`mapping_note` / 別途のメタデータ辞書として分離
   - **方針**: `SectorProfile` にオプショナルフィールドとして追加（デフォルト `None`）

```python
# _base.py に追加するフィールド（全てオプショナル）
@dataclass(frozen=True, slots=True)
class SectorProfile:
    sector_id: str
    display_name_ja: str
    display_name_en: str
    industry_codes: frozenset[str]
    concept_suffix: str
    pl_structure_note: str
    # --- Wave 3 統合で追加 ---
    has_consolidated_template: bool | None = None  # banking 用
    cf_method: str | None = None                   # banking 用（"direct"/"indirect"/"both"）
```

5. **L2 の `general_equivalent(concept)` 関数を `SectorRegistry` の API で代替**
   - `banking.general_equivalent("OrdinaryIncomeBNK")` は `banking.to_general_key(banking.canonical_key("OrdinaryIncomeBNK"))` に分解される
   - 互換性のため、`general_equivalent()` をラッパーとして残すことも可

6. **L2/L3 の `is_banking_concept()` / `insurance_specific_concepts()` の扱い**
   - `SectorRegistry` には `known_concepts()` メソッドがある
   - L2 の `is_banking_concept()` は「銀行**固有**科目のみ True、共通科目は False」というセマンティクス
   - `SectorRegistry` にこのセマンティクスを追加するか、各モジュールに薄いラッパーを残す
   - **方針**: 各モジュールに薄いラッパーを残す（セマンティクスが業種ごとに微妙に異なるため）

```python
# banking.py に残すラッパー例
def is_banking_concept(concept: str) -> bool:
    """銀行業固有科目かどうか。共通科目は False。"""
    return concept in _BANKING_SPECIFIC_CONCEPTS
```

### 3.3 変更対象ファイル

| ファイル | 変更内容 |
|----------|---------|
| `sector/_base.py` | `SectorConceptMapping.statement_type` を `StatementType \| None` に変更。`SectorProfile` にオプショナルフィールド追加 |
| `sector/banking.py` | `BankingConceptMapping` → `SectorConceptMapping`、`BankingProfile` → `SectorProfile`、手書き API → `SectorRegistry` 委譲 |
| `sector/insurance.py` | `InsuranceConceptMapping` → `SectorConceptMapping`、`InsuranceProfile` → `SectorProfile`、手書き API → `SectorRegistry` 委譲 |
| `tests/test_xbrl/test_sector_banking.py` | import パスの更新、型名の更新 |
| `tests/test_xbrl/test_sector_insurance.py` | 同上 |
| `tests/test_xbrl/test_sector_base.py` | `statement_type: StatementType \| None` のテスト追加 |

### 3.4 テスト確認

```bash
uv run pytest tests/test_xbrl/test_sector_*.py -v
```

全テストが Pass することを確認。型名の変更に伴うテストの修正が必要。

---

## 4. Step 2: `sector/__init__.py` の更新

### 4.1 現状

```python
"""業種固有タクソノミサブパッケージ。"""
```

空。

### 4.2 更新後

```python
"""業種固有タクソノミサブパッケージ。

各業種モジュールは直接インポートして使用する::

    from edinet.financial.sector import banking, insurance
    from edinet.financial.sector.construction import lookup as cns_lookup

全業種で共通の基底型::

    from edinet.financial.sector._base import SectorConceptMapping, SectorProfile, SectorRegistry

業種コードから対応するレジストリを取得::

    from edinet.financial.sector import get_sector_registry
    registry = get_sector_registry("bk1")  # → banking の SectorRegistry
"""

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)

# 業種モジュールは名前衝突（lookup, canonical_key 等）があるため
# __init__ からの関数再エクスポートは行わない。
# サブモジュールとしてのインポートのみ提供する。
from edinet.financial.sector import (
    banking,
    construction,
    insurance,
    railway,
    securities,
)

# --- 業種コード → SectorRegistry のルーティング ---

_SECTOR_REGISTRIES: dict[str, SectorRegistry] = {}


def _register_all() -> None:
    """全業種モジュールの SectorRegistry を登録する。"""
    # banking
    for code in banking.BANKING_INDUSTRY_CODES:
        _SECTOR_REGISTRIES[code] = banking._registry
    # insurance
    for code in insurance.INSURANCE_INDUSTRY_CODES:
        _SECTOR_REGISTRIES[code] = insurance._registry
    # construction
    _SECTOR_REGISTRIES["cns"] = construction._registry
    # railway
    _SECTOR_REGISTRIES["rwy"] = railway._registry
    # securities
    _SECTOR_REGISTRIES["sec"] = securities._registry


_register_all()


def get_sector_registry(industry_code: str) -> SectorRegistry | None:
    """業種コードから対応する SectorRegistry を取得する。

    Args:
        industry_code: EDINET タクソノミの業種コード（例: "bk1", "in1", "sec"）。

    Returns:
        対応する SectorRegistry。未対応の業種コードの場合は None。
    """
    return _SECTOR_REGISTRIES.get(industry_code)


def supported_industry_codes() -> frozenset[str]:
    """対応済みの業種コードの集合を返す。"""
    return frozenset(_SECTOR_REGISTRIES)


__all__ = [
    # 基底型
    "SectorConceptMapping",
    "SectorProfile",
    "SectorRegistry",
    # サブモジュール
    "banking",
    "construction",
    "insurance",
    "railway",
    "securities",
    # ルーティング
    "get_sector_registry",
    "supported_industry_codes",
]
```

### 4.3 設計判断

**`get_sector_registry()` を導入する理由:**
- normalize レイヤーが「業種コード → 適切な sector モジュール」の分岐を行う際、if/elif の連鎖ではなく辞書ルックアップで O(1) で解決できる
- 将来の業種追加時も `_register_all()` に 1 行追加するだけ
- ユーザーが「この企業の業種モジュールを取得したい」ケースにも対応

**`_registry` を各モジュールの公開属性とする:**
- Step 1 で banking/insurance を `SectorRegistry` パターンに移行した時点で `_registry` が存在する
- `_registry` はアンダースコア付きだが、`sector/__init__.py` からのアクセスは「パッケージ内部のモジュール間参照」であり問題ない
- 外部ユーザーには `get_sector_registry()` を提供する

---

## 5. Step 3: `standards/__init__.py` の更新

### 5.1 現状

`detect` 関連の 6 シンボルのみをエクスポート。`jgaap` / `ifrs` / `usgaap` / `normalize` は同名関数があるため再エクスポートしない設計。

### 5.2 更新後

```python
"""会計基準の判別・正規化サブパッケージ。

会計基準の自動判別には :func:`detect_accounting_standard` を使用する。
判別後の基準固有モジュールは直接インポートする::

    from edinet.financial.standards import detect_accounting_standard, DetailLevel
    from edinet.financial.standards import jgaap, ifrs
    from edinet.financial.standards.usgaap import extract_usgaap_summary
    from edinet.financial.standards.normalize import get_canonical_key, cross_standard_lookup

    detected = detect_accounting_standard(facts, dei=dei)
    if detected.standard == "jgaap":
        mapping = jgaap.lookup("NetSales")
    elif detected.standard == "ifrs":
        mapping = ifrs.lookup("RevenueIFRS")
    elif detected.detail_level == DetailLevel.BLOCK_ONLY:
        summary = extract_usgaap_summary(facts, contexts)

    # 会計基準横断アクセス
    key = get_canonical_key("NetSales", AccountingStandard.JAPAN_GAAP)
    ifrs_concept = cross_standard_lookup("NetSales", JAPAN_GAAP, IFRS)

Note:
    ``jgaap`` と ``ifrs`` は ``lookup``, ``canonical_key``,
    ``reverse_lookup`` 等の同名関数を持つため、
    ``__init__.py`` からの再エクスポートは行わない。
    利用者はサブモジュールから直接インポートすること。

    ``normalize`` は ``get_canonical_key``, ``get_known_concepts`` 等の
    独自名称を持つため、主要関数を再エクスポートする。
"""

from edinet.financial.standards.detect import (
    DetectedStandard,
    DetectionMethod,
    DetailLevel,
    detect_accounting_standard,
    detect_from_dei,
    detect_from_namespaces,
)

# normalize は関数名が jgaap/ifrs と衝突しないため再エクスポート可能
from edinet.financial.standards.normalize import (
    cross_standard_lookup,
    get_canonical_key,
    get_concept_for_key,
    get_concept_order,
    get_known_concepts,
)

__all__ = [
    # detect (Wave 2 Lane 2)
    "DetectedStandard",
    "DetectionMethod",
    "DetailLevel",
    "detect_accounting_standard",
    "detect_from_dei",
    "detect_from_namespaces",
    # normalize (Wave 3 Lane 1)
    "get_canonical_key",
    "get_concept_for_key",
    "get_known_concepts",
    "get_concept_order",
    "cross_standard_lookup",
]
```

---

## 6. Step 4: `xbrl/__init__.py` の更新

### 6.1 変更内容

L1 で `build_statements()` のシグネチャが拡張される（`facts`, `contexts`, `taxonomy_root` オプション引数追加）。これは後方互換なので `__init__.py` の import 文は変更不要。

追加のエクスポート:
- `DetectedStandard` を `xbrl` レベルでもアクセス可能にする（利便性）

```python
"""XBRL 関連機能を提供するサブパッケージ。"""

from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType, extract_dei
from edinet.xbrl.facts import build_line_items
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.financial.standards import DetectedStandard, detect_accounting_standard
from edinet.financial.statements import Statements, build_statements
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.units import (
    DivideMeasure,
    Measure,
    SimpleMeasure,
    StructuredUnit,
    structure_units,
)

__all__ = [
    "parse_xbrl_facts",
    "structure_contexts",
    "ContextCollection",
    "TaxonomyResolver",
    "build_line_items",
    "build_statements",
    "Statements",
    "DEI",
    "AccountingStandard",
    "PeriodType",
    "extract_dei",
    "SimpleMeasure",
    "DivideMeasure",
    "Measure",
    "StructuredUnit",
    "structure_units",
    # Wave 3 追加
    "DetectedStandard",
    "detect_accounting_standard",
]
```

---

## 7. Step 5: `PeriodType` の集約

### 7.1 現状

`PeriodType` が 3 箇所で独立定義されている:

| 定義場所 | 型 | 用途 |
|----------|------|------|
| `dei.py` | `enum.Enum("FY", "HY", "Q1", ...)` | DEI の会計期間種別 |
| `jgaap.py` | `Literal["instant", "duration"]` | XBRL 期間型 |
| `sector/_base.py` | `Literal["instant", "duration"]` | XBRL 期間型（jgaap と同一定義） |

### 7.2 問題

- `dei.py` の `PeriodType` と `jgaap.py` / `_base.py` の `PeriodType` は**全く別の概念**
  - `dei.py`: 会計期間の種類（通期、半期、四半期）
  - `jgaap.py` / `_base.py`: XBRL の期間型（時点 or 期間）
- 名前の衝突はあるが、使用コンテキストが異なるため実害は少ない
- `jgaap.py` と `_base.py` の `PeriodType` は完全に同一定義

### 7.3 統合方針

**最小限の変更（推奨）:**

1. `jgaap.py` と `_base.py` の XBRL 期間型 `PeriodType` を共有モジュールに集約
2. `dei.py` の `PeriodType` は名前を変更しない（後方互換）

```python
# src/edinet/xbrl/_types.py（新規）
"""XBRL サブパッケージ内で共有される型定義。"""

from typing import Literal

# XBRL fact の期間型。instant（時点）または duration（期間）。
# dei.py の PeriodType（FY/HY/Q1 等の会計期間種別 Enum）とは別概念。
XBRLPeriodType = Literal["instant", "duration"]
```

```python
# jgaap.py での使用
from edinet.xbrl._types import XBRLPeriodType as PeriodType  # 後方互換エイリアス

# _base.py での使用
from edinet.xbrl._types import XBRLPeriodType as PeriodType  # 後方互換エイリアス
```

### 7.4 代替案: 変更しない

3 箇所の `Literal["instant", "duration"]` は各 2 行程度の定義であり、実害が小さい。
Wave 3 統合のスコープを最小化するため、**この Step はオプションとする**。
将来の型整理フェーズで対応しても遅くない。

---

## 8. Step 6: normalize と sector の接続

### 8.1 現状（L1 完了時点）

L1 の `normalize.py` は `jgaap.py` と `ifrs.py` のみを参照する:

```python
# normalize.py（L1 完了時点）
def get_known_concepts(standard, statement_type):
    if standard == AccountingStandard.JAPAN_GAAP or standard is None:
        return frozenset(m.concept for m in jgaap.mappings_for_statement(statement_type))
    elif standard == AccountingStandard.IFRS:
        return frozenset(m.concept for m in ifrs.mappings_for_statement(statement_type))
    ...
```

業種判定は行わない。銀行業の `OrdinaryIncomeBNK` は `jgaap.lookup()` にヒットしないため、sector モジュールへのフォールバックが必要。

### 8.2 統合後の設計

`normalize.py` に業種対応を追加する。

```python
# normalize.py に追加する関数

from edinet.financial.sector import get_sector_registry

def get_known_concepts_for_sector(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    industry_code: str | None = None,
) -> frozenset[str]:
    """業種を考慮した concept セットを返す。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表タイプ。
        industry_code: 業種コード（例: "bk1", "in1", "sec"）。
            None の場合は一般事業会社として扱う。

    Returns:
        concept 名の frozenset。
    """
    # IFRS / US-GAAP は業種区分なし（IFRS は業種非依存の分類体系）
    if standard in (AccountingStandard.IFRS, AccountingStandard.US_GAAP):
        return get_known_concepts(standard, statement_type)

    # J-GAAP + 業種コード指定あり → sector モジュールを参照
    if industry_code is not None:
        registry = get_sector_registry(industry_code)
        if registry is not None:
            sector_mappings = registry.mappings_for_statement(statement_type)
            return frozenset(m.concept for m in sector_mappings)

    # フォールバック: 一般事業会社（cai）
    return get_known_concepts(standard, statement_type)


def get_canonical_key_for_sector(
    local_name: str,
    standard: AccountingStandard | None,
    industry_code: str | None = None,
) -> str | None:
    """業種を考慮した canonical_key 変換。

    Args:
        local_name: XBRL の概念名。
        standard: 会計基準。
        industry_code: 業種コード。None の場合は一般事業会社。

    Returns:
        canonical_key。未定義の場合は None。
    """
    # まず sector モジュールで検索
    if industry_code is not None:
        registry = get_sector_registry(industry_code)
        if registry is not None:
            key = registry.canonical_key(local_name)
            if key is not None:
                return key

    # sector で見つからない → 一般事業（jgaap / ifrs）にフォールバック
    return get_canonical_key(local_name, standard)
```

### 8.3 statements.py との接続

L1 完了時点の `statements.py` は `industry_code` を受け取らない。統合で以下を追加:

```python
# build_statements() に industry_code パラメータを追加
def build_statements(
    items: Sequence[LineItem],
    *,
    facts: tuple[RawFact, ...] | None = None,
    contexts: dict[str, StructuredContext] | None = None,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,  # ← 統合で追加
) -> Statements:
    ...

# Statements に _industry_code フィールドを追加
@dataclass(frozen=True, slots=True, kw_only=True)
class Statements:
    _items: tuple[LineItem, ...]
    _detected_standard: DetectedStandard | None = None
    _facts: tuple[RawFact, ...] | None = None
    _contexts: dict[str, StructuredContext] | None = None
    _taxonomy_root: Path | None = None
    _industry_code: str | None = None  # ← 統合で追加
```

`_build_for_type()` 内で `get_known_concepts_for_sector()` を呼ぶように変更:

```python
def _build_for_type(self, statement_type, *, consolidated, period):
    std = self._detected_standard
    # ... BLOCK_ONLY パス（既存）...

    # DETAILED パス
    standard_enum = std.standard if std else None
    # ↓ 統合で変更: industry_code を渡す
    known = get_known_concepts_for_sector(
        standard_enum, statement_type, self._industry_code
    )
    order = get_concept_order_for_sector(
        standard_enum, statement_type, self._industry_code
    )
    return _build_single_statement(
        self._items, statement_type, known, order,
        consolidated=consolidated, period=period,
    )
```

### 8.4 後方互換性

- `industry_code=None`（デフォルト）の場合、L1 完了時点と同一の動作（一般事業会社）
- 既存コード（`build_statements(items)` や `build_statements(items, facts=facts)`）は一切壊れない

### 8.5 テスト

| テスト | 内容 |
|--------|------|
| `test_banking_statements` | 銀行業の LineItem から PL を組み立て、経常収益が含まれることを検証 |
| `test_insurance_statements` | 保険業の LineItem から PL を組み立て、保険引受収益が含まれることを検証 |
| `test_construction_statements` | 建設業の LineItem から PL を組み立て、完成工事高が含まれることを検証 |
| `test_sector_fallback_to_general` | sector で見つからない共通科目が jgaap にフォールバックすることを検証 |
| `test_industry_code_none_backward_compat` | `industry_code=None` で L1 完了時と同一動作を検証 |

---

## 9. Step 7: stubgen 一括実行

```bash
uv run stubgen src/edinet --include-docstrings -o stubs
```

全モジュールの `.pyi` ファイルを一括再生成する。

**確認事項:**
- `stubs/edinet/xbrl/sector/_base.pyi` が生成されていること
- `stubs/edinet/xbrl/sector/banking.pyi` が生成されていること
- `stubs/edinet/xbrl/sector/insurance.pyi` が生成されていること
- `stubs/edinet/xbrl/sector/construction.pyi` が生成されていること
- `stubs/edinet/xbrl/sector/railway.pyi` が生成されていること
- `stubs/edinet/xbrl/sector/securities.pyi` が生成されていること
- `stubs/edinet/xbrl/standards/normalize.pyi` が生成されていること
- `stubs/edinet/xbrl/statements.pyi` が更新されていること（新フィールド反映）

---

## 10. Step 8: 全テスト + リント

```bash
# 全ユニットテスト
uv run pytest

# リント
uv run ruff check src tests
```

**合格条件:**
- 全テスト Pass
- リントエラー 0 件

---

## 11. Step 9: E2E 回帰テスト

### 11.1 Wave 2 E2E 回帰

```bash
EDINET_API_KEY=$EDINET_API_KEY \
EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 \
  uv run python tools/wave2_e2e_detect.py

EDINET_API_KEY=$EDINET_API_KEY \
EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 \
  uv run python tools/wave2_e2e_concept_sets.py
```

### 11.2 Wave 3 E2E テスト（新規作成）

`tools/wave3_e2e_integration.py` を作成し、以下を検証:

```python
# 1. normalize API の動作確認
from edinet.financial.standards.normalize import (
    get_canonical_key,
    cross_standard_lookup,
    get_known_concepts,
)

# J-GAAP
assert get_canonical_key("NetSales", AccountingStandard.JAPAN_GAAP) == "revenue"
# IFRS
assert get_canonical_key("RevenueIFRS", AccountingStandard.IFRS) == "revenue"
# クロススタンダード
assert cross_standard_lookup("NetSales", JAPAN_GAAP, IFRS) == "RevenueIFRS"

# 2. sector モジュールの動作確認
from edinet.financial.sector import get_sector_registry

banking_reg = get_sector_registry("bk1")
assert banking_reg is not None
assert banking_reg.canonical_key("OrdinaryIncomeBNK") == "ordinary_revenue_bnk"

insurance_reg = get_sector_registry("in1")
assert insurance_reg is not None

# 3. 実データ E2E（API キー必要）
# 銀行業: みずほフィナンシャルグループ等
# 保険業: 東京海上日動等
# 建設業: 大林組等
# 証券業: 大和証券グループ等
# 鉄道業: JR東日本等
```

---

## 12. レガシーコード残存確認

統合完了後に以下を確認し、不要なコードが残っていないことを検証する:

```bash
# JSON import の残存確認
grep -r "importlib.resources" src/edinet/xbrl/statements.py    # → 0 件
grep -r "_load_concept_definitions" src/ tests/                 # → 0 件
grep -r "to_legacy_concept_list" src/ tests/                   # → 0 件
grep -r "to_legacy_format" src/ tests/                         # → 0 件
grep -r "_load_json" src/edinet/xbrl/standards/ifrs.py         # → 0 件

# BankingConceptMapping / InsuranceConceptMapping の残存確認
grep -r "BankingConceptMapping" src/                            # → 0 件（SectorConceptMapping に統一済み）
grep -r "InsuranceConceptMapping" src/                          # → 0 件（SectorConceptMapping に統一済み）
grep -r "BankingProfile" src/                                   # → 0 件（SectorProfile に統一済み）
grep -r "InsuranceProfile" src/                                 # → 0 件（SectorProfile に統一済み）

# JSON データファイルの残存確認
ls src/edinet/xbrl/data/                                       # → 空ディレクトリ or 削除済み
```

---

## 13. 変更ファイル一覧（統合タスク全体）

| ファイル | 操作 | Step |
|----------|------|------|
| `src/edinet/xbrl/sector/_base.py` | 変更（`statement_type` 拡張、`SectorProfile` フィールド追加） | 1 |
| `src/edinet/xbrl/sector/banking.py` | 変更（`SectorConceptMapping` / `SectorRegistry` に移行） | 1 |
| `src/edinet/xbrl/sector/insurance.py` | 変更（`SectorConceptMapping` / `SectorRegistry` に移行） | 1 |
| `src/edinet/xbrl/sector/__init__.py` | 変更（サブモジュール登録、`get_sector_registry` 追加） | 2 |
| `src/edinet/xbrl/standards/__init__.py` | 変更（normalize シンボル追加） | 3 |
| `src/edinet/xbrl/__init__.py` | 変更（`DetectedStandard` 追加） | 4 |
| `src/edinet/xbrl/_types.py` | 新規（`XBRLPeriodType` 定義）**オプション** | 5 |
| `src/edinet/xbrl/standards/normalize.py` | 変更（sector 対応関数追加） | 6 |
| `src/edinet/xbrl/statements.py` | 変更（`industry_code` パラメータ追加） | 6 |
| `tests/test_xbrl/test_sector_banking.py` | 変更（型名更新） | 1 |
| `tests/test_xbrl/test_sector_insurance.py` | 変更（型名更新） | 1 |
| `tests/test_xbrl/test_sector_base.py` | 変更（`statement_type \| None` テスト追加） | 1 |
| `tests/test_xbrl/test_statements.py` | 変更（sector 統合テスト追加） | 6 |
| `tests/test_xbrl/test_normalize.py` | 変更（sector 対応テスト追加） | 6 |
| `tools/wave3_e2e_integration.py` | 新規 | 9 |
| `stubs/` 配下全体 | 再生成 | 7 |

---

## 14. 完了条件

| # | 条件 | 検証方法 |
|---|------|---------|
| 1 | 全 sector モジュールが `SectorConceptMapping` を使用している | `grep -r "BankingConceptMapping\|InsuranceConceptMapping" src/` → 0 件 |
| 2 | `sector/__init__.py` から `get_sector_registry()` が利用可能 | `from edinet.financial.sector import get_sector_registry` が成功 |
| 3 | `standards/__init__.py` から normalize API が利用可能 | `from edinet.financial.standards import get_canonical_key` が成功 |
| 4 | `build_statements()` が `industry_code` を受け付ける | テスト Pass |
| 5 | 銀行業の LineItem から PL が組み立てられる | テスト Pass |
| 6 | 保険業の LineItem から PL が組み立てられる | テスト Pass |
| 7 | `uv run pytest` 全 Pass | CI |
| 8 | `uv run ruff check src tests` クリーン | CI |
| 9 | `stubs/` が最新状態 | stubgen 実行済み |
| 10 | Wave 2 E2E 回帰テスト Pass | E2E スクリプト |
| 11 | JSON データファイルが削除済み | `ls src/edinet/xbrl/data/` → 空 |
| 12 | レガシー関数が削除済み | grep 確認 |

---

## 15. 所要時間の見積もり

| Step | 作業量 | 目安 |
|------|--------|------|
| Step 1: データクラス統一 | 中（3 ファイル変更 + テスト修正） | — |
| Step 2: sector/__init__.py | 小 | — |
| Step 3: standards/__init__.py | 小 | — |
| Step 4: xbrl/__init__.py | 小 | — |
| Step 5: PeriodType 集約 | 小（オプション） | — |
| Step 6: normalize-sector 接続 | 大（設計判断 + テスト作成） | — |
| Step 7: stubgen | 小（コマンド 1 発） | — |
| Step 8-9: テスト + E2E | 中 | — |

**最もリスクが高い Step**: Step 6（normalize と sector の接続）。設計判断が多く、テストも新規作成が必要。

---

## 16. 注意事項

### 16.1 `jgaap.py` の `display_order` デフォルト値

現在 `jgaap.py` の `ConceptMapping.display_order` はデフォルト値 `0` を持つ（省略可能）。
一方 `SectorConceptMapping.display_order` は必須フィールド（`SectorRegistry._validate()` が `> 0` を検証）。

**統合での対応**: `jgaap.py` の `display_order` を必須フィールドに変更するかは、既存コードへの影響を考慮して判断する。現時点では `jgaap.py` の全マッピングに `display_order` が設定されているため、デフォルト値を削除しても実害はないが、外部ユーザーが `ConceptMapping()` を直接構築しているケースがあれば破壊的変更になる。

**推奨**: 統合タスクではデフォルト値を維持し、将来のメジャーバージョンアップで統一する。

### 16.2 `general_equivalent` の命名統一

全レーンで `general_equivalent` フィールド名に統一済み。格納する値も canonical_key 文字列で統一済み。追加の変更は不要。

### 16.3 Step の実行順序

Step 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 の順序で実行すること。
特に Step 1（データクラス統一）が Step 2（`__init__.py`）と Step 6（normalize 接続）の前提条件。
Step 5（PeriodType 集約）はオプションであり、スキップ可能。

---

## 17. Wave 3 Lane 4 レビューで発見された追加課題

Wave 3 Lane 4（construction / railway / securities + _base.py）のレビューで発見された、上記統合ステップに含まれていない追加課題。

### 17.1 API 非対称性の詳細（Step 1 で解消予定の補足情報）

L2（banking）/ L3（insurance）と L4（construction / railway / securities）で以下の API 差異がある。Step 1 でデータクラスを統一する際に、これらの API も統一すること。

| API | L2 banking | L3 insurance | L4 (construction/railway/securities) |
|-----|-----------|-------------|--------------------------------------|
| concept → general_key | `general_equivalent(concept: str) -> str \| None` | `insurance_to_general_map() -> dict[str, str]` | `to_general_key(concept: str) -> str \| None` |
| general_key → sector_concepts | なし | なし | `from_general_key(general_key: str) -> tuple[SectorConceptMapping, ...]` |
| 全 general マッピング辞書 | `banking_to_general_map() -> dict[str, str]` | `insurance_to_general_map() -> dict[str, str]` | なし |
| 業種判定 | `is_banking_industry(code) -> bool` | `is_insurance_industry(code) -> bool` | `is_XXX_industry(code) -> bool` (**統一済み**) |
| 固有概念判定 | `is_banking_concept(concept) -> bool` | `insurance_specific_concepts() -> frozenset[str]` | なし（`known_concepts()` で代替可能） |

**統合方針（推奨）:**
- `to_general_key(concept)` を全 sector モジュールの標準 API として採用（`SectorRegistry` のメソッド）
- `from_general_key(general_key)` を全 sector モジュールの標準 API として採用
- L2/L3 の `*_to_general_map()` は互換ラッパーとして残すか、段階的に廃止
- `is_banking_concept()` / `insurance_specific_concepts()` は各モジュールに薄いラッパーを残す（§3.2 #6 の方針どおり）

### 17.2 L4 に `*_to_general_map()` 相当が未実装

L2/L3 には `banking_to_general_map()` / `insurance_to_general_map()` という「全 general_equivalent マッピングを dict で返す」API がある。L4 の `SectorRegistry` にはこの API がない。

**対応案:**
Step 1 で `SectorRegistry` に以下のメソッドを追加する:

```python
def to_general_map(self) -> dict[str, str]:
    """全 general_equivalent マッピングを辞書で返す。

    Returns:
        {concept: general_equivalent} の辞書。
        general_equivalent が None のマッピングは含まない。
    """
    return {
        m.concept: m.general_equivalent
        for m in self._mappings
        if m.general_equivalent is not None
    }
```

### 17.3 banking の `display_order` デフォルト値問題

L2 の `BankingConceptMapping.display_order` はデフォルト値 `0` を持つ。一方 L4 の `SectorRegistry._validate()` は `display_order >= 1` を要求する（今回のレビューで追加済み）。

**Step 1 で banking を SectorRegistry に移行する際**:
- 全 banking マッピングの `display_order` が 1 以上であることを確認する
- `display_order=0` のマッピングがあれば 1 始まりに修正する
- banking の現在のマッピング定義を確認し、未設定（デフォルト 0）の科目がないかチェック

### 17.4 未実装のクロスバリデーションテスト

計画書（WAVE_3_LANE_4.md）では以下のテストが設計されていたが、現時点では未実装。理由: 統合前の並列安全ルールにより、他レーンのモジュール（jgaap）を直接テストで参照できない。

| テスト ID | 内容 | 対象 |
|-----------|------|------|
| T25 | 証券業の `general_equivalent` 値が jgaap の canonical_key に存在するか検証 | securities × jgaap |
| T41 | 建設業の `general_equivalent` 値が jgaap の canonical_key に存在するか検証 | construction × jgaap |
| T59 | 鉄道業の `general_equivalent` 値が jgaap の canonical_key に存在するか検証 | railway × jgaap |

**Step 8 で追加するテスト案:**

```python
# tests/test_xbrl/test_sector_cross_validation.py（統合後に新規作成）
from edinet.financial.standards import jgaap
from edinet.financial.sector import construction, railway, securities

@pytest.mark.parametrize("sector_module", [construction, railway, securities])
def test_general_equivalents_exist_in_jgaap(sector_module):
    """全 sector の general_equivalent が jgaap の canonical_key に存在する。"""
    jgaap_keys = jgaap.all_canonical_keys()
    for m in sector_module.all_mappings():
        if m.general_equivalent is not None:
            assert m.general_equivalent in jgaap_keys, (
                f"{m.concept} の general_equivalent={m.general_equivalent!r} "
                f"が jgaap に存在しない"
            )
```

### 17.5 今回のレビューで修正済みの項目（参考）

以下は L4 レビューで発見され、**統合前に修正済み**の項目。統合タスクでは追加対応不要。

| 修正内容 | 対象ファイル |
|----------|------------|
| 証券業 PL に `SellingGeneralAndAdministrativeExpensesSEC` と `OperatingProfitSEC` を追加（6→8 概念） | `sector/securities.py`, `test_sector_securities.py` |
| `SectorRegistry._validate()` に `industry_codes ⊆ profile.industry_codes` チェックを追加 | `sector/_base.py`, `test_sector_base.py` |
| `SectorRegistry._validate()` に `display_order >= 1` チェックを追加 | `sector/_base.py`, `test_sector_base.py` |

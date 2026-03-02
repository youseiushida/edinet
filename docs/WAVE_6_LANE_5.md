# 並列実装の安全ルール（必ず遵守）

あなたは Wave 6 / Lane 5 を担当するエージェントです。
担当機能: calc_check

## 絶対禁止事項

1. **既存の `__init__.py` を変更しないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 既存の `__init__.py` への re-export 追加は Wave 完了後の統合タスクが一括で行う
   - **例外**: `src/edinet/xbrl/validation/__init__.py` は事前作業で作成済み（空ファイル）。変更しないこと

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/validation/calc_check.py` (新規)
   - `tests/test_xbrl/test_calc_check.py` (新規)
   - `tests/fixtures/calc_check/` (新規ディレクトリ)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - 既存の dataclass / class にフィールドを追加する場合は必ずデフォルト値を付与すること
   - 既存のフィールド名・型・関数シグネチャを変更してはならない
   - 既存の定数名を変更・削除してはならない（追加のみ可）

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリを作成すること
     例: `tests/fixtures/calc_check/`

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.validation.calc_check import validate_calculations` （OK）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_calc_check.py` に作成

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 5 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.dei` (DEI, AccountingStandard, PeriodType, extract_dei)
     - `edinet.xbrl._namespaces` (NS_* 定数, classify_namespace 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl.linkbase.calculation` (CalculationArc, CalculationTree, CalculationLinkbase, parse_calculation_linkbase)
     - `edinet.xbrl.linkbase.definition` (DefinitionArc, DefinitionTree 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果を報告すること

---

# LANE 5 — validation/calc_check: 計算リンクベースによる合計値バリデーション

## 0. 位置づけ

### FEATURES.md との対応

Wave 6 Lane 5 は、FEATURES.md の **validation/calc_check** に対応する。計算リンクベース（CalculationLinkbase）と実際の財務諸表の Fact 値を突合し、親科目の値が子科目の加重和と一致するかを検証する。

FEATURES.md の定義:

> - validation/calc_check: 計算リンクベースのバリデーション [TODO]
>   - depends: calc_tree, facts
>   - detail: 計算リンクベースの加算・減算関係に基づき、合計値の整合性を検証

### WAVE_6.md での位置

> Lane E: validation/calc_check → 新規 xbrl/validation/calc_check.py（既存は読み取りのみ）

### 設計方針: D1 / D4 / D5 の遵守

- **D1**: 構造化された `CalcValidationResult` dataclass を返す（`bool` や `list[str]` は使わない）
- **D4**: standalone 関数 `validate_calculations()` として実装（複数の入力を組み合わせる分析のため）
- **D5**: `validate_*` プレフィックスで `*ValidationResult` を返す

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.linkbase.calculation` | `CalculationLinkbase`, `CalculationArc`, `CalculationTree` | read-only |
| `edinet.models.financial` | `FinancialStatement`, `LineItem` | read-only |

他レーンとのファイル衝突なし（全て新規ファイル作成）。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| C-7 | 直接 | 計算リンクベースの仕様。weight は ±1 のみ、role URI は presentation と同じ、validation only（assembly ではない）、丸め許容あり |
| D-1 | 直接 | ValidationResult 型の設計決定 |
| E-1 | 関連 | 財務諸表の種類と識別 |

### XBRL 仕様参照

- XBRL 2.1 §5.2.5.2: Calculation Validation
  - **全ての** summation-item 親子関係を検証対象とする（roots だけでなく中間ノードも含む）
  - 親の値 = Σ(子の値 × weight) ± tolerance
  - tolerance の計算: 本実装では `0.5 × 10^(-min(decimals))` を採用（§1.2 参照）
  - summation-item arcrole のみ

---

## 1. 背景知識

### 1.1 XBRL 計算バリデーションの仕様（C-7.a.md より）

計算リンクベースは「合計値の整合性検証」に使用される。重要な仕様ポイント:

| 仕様 | 詳細 |
|------|------|
| **weight** | ±1 のみ（分数は使われない）。`weight=1` が加算、`weight=-1` が減算 |
| **role URI** | Presentation linkbase と同じ role URI を共有する |
| **用途** | Validation only（assembly ではない）。計算リンクベースから財務諸表を組み立てることは仕様上想定されていない |
| **不一致** | decimals/precision の丸めの範囲内なら許容。丸め範囲を超えた場合が検証エラー |
| **欠損 Fact** | 子科目の Fact が存在しない場合、その合計検証はスキップされる |

### 1.2 decimals と丸め許容差

#### XBRL 2.1 §5.2.5.2 の正式な検証方法

XBRL 2.1 の厳密な定義は rounding-then-compare:

```
round(parent, parent_decimals) == round(Σ(round(child_i, child_i_decimals) × weight_i), parent_decimals)
```

あるいは、実装でよく使われる合算方式:

```
tolerance = Σ(0.5 × 10^(-decimals_i))   # 全 item（親+子）について
```

#### 本実装の採用方式: min-decimals 方式

```
tolerance = 0.5 × 10^(-min(parent_decimals, child1_decimals, child2_decimals, ...))
```

min-decimals 方式は「関係する全 Fact のうち最も粗い精度」に基づき tolerance を算出する方式であり、Arelle 等の一般的な XBRL バリデータで広く使用される。XBRL 2.1 §5.2.5.2 の合算方式（`Σ(0.5 × 10^(-d_i))`）と比較した特性:

| ケース | min-decimals | 合算方式 | 影響 |
|--------|-------------|---------|------|
| 全員 decimals=-6 (3 items) | 500,000 | 1,500,000 | min-decimals の方が厳しい → false positive のリスク |
| parent=0, child=-6 (2 items) | 500,000 | 500,000.5 | ほぼ同等 |

**EDINET の実データでは同一 FinancialStatement 内の decimals はほぼ均一（全て `-6` か全て `-3`）**であるため、両方式の差は実運用上ほぼゼロ。v0.1.0 では min-decimals 方式を採用し、将来的に合算方式への移行を検討する。

#### decimals 値と tolerance の対応

| decimals | 意味 | tolerance |
|----------|------|-----------|
| `-6` | 百万円単位 | `0.5 × 10^6 = 500,000` |
| `-3` | 千円単位 | `0.5 × 10^3 = 500` |
| `0` | 円単位 | `0.5 × 10^0 = 0.5` |
| `"INF"` | 完全精度 | `0`（完全一致） |
| `None` | 未指定 | `0`（安全側: 完全一致） |

**例**: parent_decimals=-6, child_decimals=[-6, -6] → min = -6 → tolerance = 0.5 × 10^6 = 500,000

実際の EDINET データでは `decimals="-6"`（百万円単位）が最も一般的。この場合、50万円以内の差は丸めの範囲として許容される。

### 1.3 CalculationLinkbase の API（calculation.py より）

```python
# 全 role URI
calc_linkbase.role_uris  # → tuple[str, ...]

# 特定 role の計算木
tree = calc_linkbase.get_tree(role_uri)  # → CalculationTree | None
tree.roots   # → tuple[str, ...]    # 親のみで子でない概念
tree.arcs    # → tuple[CalculationArc, ...]

# 子の取得
arcs = calc_linkbase.children_of(parent="GrossProfit", role_uri=role_uri)
# → tuple[CalculationArc, ...]
# arc.child = "NetSales", arc.weight = 1
# arc.child = "CostOfSales", arc.weight = -1
```

### 1.4 LineItem からの Fact 値取得

```python
item: LineItem
item.local_name  # → "NetSales"
item.value       # → Decimal("100000000") or str or None
item.decimals    # → -6 or "INF" or None
item.is_nil      # → False
```

**注意**: `item.value` は `Decimal | str | None`。テキスト Fact（`str`）や nil Fact（`None`）は計算バリデーションの対象外。

---

## 2. ゴール

### 2.1 機能要件

1. **`validate_calculations()` 関数の実装**
   - 入力: `FinancialStatement` + `CalculationLinkbase`
   - 出力: `CalcValidationResult`
   - 計算リンクベースの**全ての親科目**（roots だけでなく中間ノードも含む）について、子科目の加重和と親科目の値を比較
   - 丸め許容差（tolerance）を XBRL 2.1 仕様に準拠して計算

2. **`CalcValidationResult` dataclass の定義**（D1 準拠）
   - `issues`: 不一致科目のタプル
   - `checked_count`: 検証した親科目の数
   - `passed_count`: 一致した親科目の数
   - `skipped_count`: Fact 不足でスキップした数
   - `is_valid`: error がゼロなら True
   - `error_count` / `warning_count`

3. **`ValidationIssue` dataclass の定義**
   - `role_uri`: 所属 role URI
   - `parent_concept`: 親概念のローカル名
   - `expected`: 計算上の期待値（子の加重和）
   - `actual`: 実際の Fact 値
   - `difference`: |expected - actual|
   - `tolerance`: decimals ベースの許容誤差
   - `severity`: `"error"` (tolerance 超過) / `"warning"` (将来用の予約)
   - `message`: 人間向けメッセージ（日本語）

4. **丸め許容差の計算**（min-decimals 方式、§1.2 参照）
   - `0.5 × 10^(-min(parent_decimals, *child_decimals))`
   - `"INF"` → tolerance=0（完全一致）
   - `None` → tolerance=0（安全側）
   - EDINET の実データでは decimals が均一のため、合算方式との実質的な差はない

5. **欠損 Fact のスキップ**
   - 親科目の Fact がない → skip
   - 子科目の Fact が 1 つでもない → skip
   - スキップ数を `skipped_count` に記録

### 2.2 非ゴール

- **XBRL Calculations 1.1 への対応**: EDINET は XBRL 2.1 の summation-item のみ使用（C-7.a.md）
- **FinancialStatement の自動組み立て**: 計算リンクベースは validation only（assembly ではない）
- **重複 Fact の解決**: FinancialStatement 構築時に既に解決済み（statements.py の責務）
- **テキスト Fact / nil Fact の検証**: 数値 Fact のみが対象

---

## 3. データモデル設計

### 3.1 ValidationIssue (frozen dataclass)

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """計算バリデーションの個別不一致。

    Attributes:
        role_uri: 計算リンクベースのロール URI。
        parent_concept: 親概念のローカル名（例: "GrossProfit"）。
        expected: 子科目の加重和（計算上の期待値）。
        actual: 実際の Fact 値。
        difference: |expected - actual|。
        tolerance: decimals ベースの許容誤差。
        severity: 深刻度。tolerance 超過は "error"。
        message: 人間向けメッセージ（日本語）。
    """
    role_uri: str
    parent_concept: str
    expected: Decimal
    actual: Decimal
    difference: Decimal
    tolerance: Decimal
    severity: Literal["error", "warning"]
    message: str
```

### 3.2 CalcValidationResult (frozen dataclass)

```python
@dataclass(frozen=True, slots=True)
class CalcValidationResult:
    """計算リンクベース検証の結果。

    Attributes:
        issues: 不一致の詳細タプル。
        checked_count: 検証した親科目の数（passed + error）。
        passed_count: 一致した（tolerance 内の）親科目の数。
        skipped_count: Fact 不足でスキップした親科目の数。
    """
    issues: tuple[ValidationIssue, ...]
    checked_count: int
    passed_count: int
    skipped_count: int

    @property
    def is_valid(self) -> bool:
        """error が 1 つもなければ True。"""
        return all(i.severity != "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        """error の件数。"""
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        """warning の件数。"""
        return sum(1 for i in self.issues if i.severity == "warning")

    def __str__(self) -> str:
        """人間向けサマリを返す。"""
        status = "合格" if self.is_valid else "不合格"
        return (
            f"計算バリデーション: {status} "
            f"(検証={self.checked_count}, 合格={self.passed_count}, "
            f"エラー={self.error_count}, スキップ={self.skipped_count})"
        )
```

**設計根拠**:

- `is_valid`, `error_count`, `warning_count` を property にする理由: `issues` から計算可能な派生値であり、フィールドにすると `issues` との不整合リスクがある。frozen dataclass なので property のコストは許容範囲
- `checked_count` が `passed_count + error_count` になる関係: `checked_count = passed_count + len([i for i in issues if i.severity == "error"])`
- `skipped_count` は `checked_count` に含まれない（検証対象外のため）
- `severity` が現時点で `"error"` のみ使用される理由: 将来的に tolerance の閾値を段階的に設定して warning を出す拡張を見据えている

---

## 4. 実装詳細

### 4.1 Fact インデックスの構築

```python
def _build_fact_index(
    statement: FinancialStatement,
) -> dict[str, LineItem]:
    """FinancialStatement から local_name → LineItem のインデックスを構築する。

    同一 local_name の LineItem が複数存在する場合は最初のものを使用する
    （FinancialStatement 構築時に重複解決済みのため、通常は 1 対 1）。

    数値以外（str 型の value や None）、nil の Fact は除外する。

    Args:
        statement: 対象の FinancialStatement。

    Returns:
        local_name → LineItem の辞書。
    """
    index: dict[str, LineItem] = {}
    for item in statement.items:
        if item.local_name not in index:
            if isinstance(item.value, Decimal) and not item.is_nil:
                index[item.local_name] = item
    return index
```

### 4.2 丸め許容差の計算

```python
def _compute_tolerance(
    parent_decimals: int | Literal["INF"] | None,
    child_decimals_list: list[int | Literal["INF"] | None],
) -> Decimal:
    """XBRL 2.1 §5.2.5.2 に基づく丸め許容誤差を計算する。

    min-decimals 方式を採用（§1.2 参照）:
    tolerance = 0.5 × 10^(-min(parent_decimals, child1_decimals, ...))

    0.5 係数は XBRL 2.1 の丸め定義に由来する。各 Fact は
    ±0.5 × 10^(-decimals) の丸め誤差を持つため、最も粗い精度の
    Fact に合わせた tolerance を採用する。Arelle 等の一般的な
    XBRL バリデータと同等の方式。

    XBRL 2.1 の合算方式（Σ(0.5 × 10^(-d_i))）との差は、
    EDINET の実データでは decimals がほぼ均一のため実質ゼロ。
    将来的に合算方式への移行を検討する。

    "INF" は無限精度を意味し、min 計算からは除外される（他に有限の
    decimals があればその最小値を使用）。全て "INF" の場合は tolerance=0。
    None は未指定であり、安全側として tolerance=0（完全一致）とする。

    Args:
        parent_decimals: 親科目の decimals 属性値。
        child_decimals_list: 子科目の decimals 属性値のリスト。

    Returns:
        許容誤差（Decimal）。
    """
    all_decimals = [parent_decimals] + child_decimals_list

    # None を除外（未指定は安全側: 完全一致）
    specified = [d for d in all_decimals if d is not None]

    if not specified:
        # 全て None → tolerance=0（完全一致）
        return Decimal(0)

    # INF を除外して数値のみ抽出
    numeric = [d for d in specified if isinstance(d, int)]

    if not numeric:
        # 全て INF → tolerance=0（完全一致）
        return Decimal(0)

    # min(numeric) が最小の decimals
    min_dec = min(numeric)
    return Decimal(5) * Decimal(10) ** Decimal(-min_dec - 1)
```

**丸め許容差の計算例**:

```
parent_decimals=-6, child_decimals=[-6, -6]
→ min(-6, -6, -6) = -6
→ tolerance = 0.5 × 10^6 = 500,000

parent_decimals=-3, child_decimals=[-6]
→ min(-3, -6) = -6
→ tolerance = 0.5 × 10^6 = 500,000

parent_decimals="INF", child_decimals=["INF"]
→ numeric = [] → tolerance = 0

parent_decimals=-6, child_decimals=["INF"]
→ numeric = [-6] → min = -6
→ tolerance = 0.5 × 10^6 = 500,000
```

### 4.3 メイン関数: `validate_calculations()`

```python
from edinet.models.financial import FinancialStatement, LineItem
from edinet.xbrl.linkbase.calculation import CalculationLinkbase, CalculationArc


def validate_calculations(
    statement: FinancialStatement,
    calc_linkbase: CalculationLinkbase,
    *,
    role_uri: str | None = None,
) -> CalcValidationResult:
    """計算リンクベースに基づき財務諸表の合計値を検証する。

    XBRL 2.1 §5.2.5.2 に準拠し、計算リンクベース内の**全ての**
    summation-item 親子関係を検証対象とする（roots だけでなく
    中間ノードも含む）。各親科目について子科目の加重和と比較し、
    decimals ベースの丸め許容差を超える不一致を検出する。

    Args:
        statement: 検証対象の FinancialStatement。
        calc_linkbase: parse_calculation_linkbase() で取得した
            CalculationLinkbase。
        role_uri: 検証対象のロール URI。None の場合は全ロールを検証する。

    Returns:
        CalcValidationResult。
    """
    fact_index = _build_fact_index(statement)
    issues: list[ValidationIssue] = []
    checked = 0
    passed = 0
    skipped = 0

    # 対象 role URI の決定
    if role_uri is not None:
        target_roles = [role_uri] if calc_linkbase.get_tree(role_uri) is not None else []
    else:
        target_roles = list(calc_linkbase.role_uris)

    for r_uri in target_roles:
        tree = calc_linkbase.get_tree(r_uri)
        if tree is None:
            continue

        # 全てのユニーク親科目を収集（roots + 中間ノード）
        # XBRL 2.1 §5.2.5.2: 全 summation-item 関係を検証対象とする
        all_parents: list[str] = []
        seen: set[str] = set()
        for arc in tree.arcs:
            if arc.parent not in seen:
                all_parents.append(arc.parent)
                seen.add(arc.parent)

        for parent_concept in all_parents:
            # 親科目の Fact を取得
            parent_item = fact_index.get(parent_concept)
            if parent_item is None:
                skipped += 1
                continue

            # 子科目の Fact を取得
            children = calc_linkbase.children_of(parent_concept, role_uri=r_uri)
            if not children:
                skipped += 1
                continue

            child_values: list[tuple[Decimal, int | Literal["INF"] | None]] = []
            all_found = True
            for arc in children:
                child_item = fact_index.get(arc.child)
                if child_item is None:
                    all_found = False
                    break
                assert isinstance(child_item.value, Decimal)  # _build_fact_index で保証済み
                child_values.append((child_item.value * arc.weight, child_item.decimals))

            if not all_found:
                skipped += 1
                continue

            # 期待値の計算
            expected = sum((v for v, _ in child_values), Decimal(0))
            actual = parent_item.value
            assert isinstance(actual, Decimal)  # _build_fact_index で保証済み

            # 許容誤差の計算
            tolerance = _compute_tolerance(
                parent_item.decimals,
                [d for _, d in child_values],
            )

            # 比較
            difference = abs(expected - actual)
            checked += 1

            if difference <= tolerance:
                passed += 1
            else:
                msg = (
                    f"計算不一致: {parent_concept} の期待値={expected:,.0f}, "
                    f"実際値={actual:,.0f}, 差={difference:,.0f}, "
                    f"許容誤差={tolerance:,.0f}"
                )
                issues.append(
                    ValidationIssue(
                        role_uri=r_uri,
                        parent_concept=parent_concept,
                        expected=expected,
                        actual=actual,
                        difference=difference,
                        tolerance=tolerance,
                        severity="error",
                        message=msg,
                    )
                )

    return CalcValidationResult(
        issues=tuple(issues),
        checked_count=checked,
        passed_count=passed,
        skipped_count=skipped,
    )
```

---

## 5. 使用例

### 5.1 基本的なバリデーション

```python
from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase
from edinet.xbrl.validation.calc_check import validate_calculations

# CalculationLinkbase をパース
with open("path/to/_cal.xml", "rb") as f:
    calc_linkbase = parse_calculation_linkbase(f.read())

# PL を検証
pl = statements.income_statement()
result = validate_calculations(pl, calc_linkbase)

print(f"検証科目数: {result.checked_count}")
print(f"合格: {result.passed_count}")
print(f"スキップ: {result.skipped_count}")
print(f"エラー: {result.error_count}")
print(f"検証合格: {result.is_valid}")

# エラー詳細
for issue in result.issues:
    print(f"  [{issue.severity}] {issue.message}")
```

### 5.2 特定ロールでの検証

```python
# 特定の role URI のみ検証
result = validate_calculations(
    pl,
    calc_linkbase,
    role_uri="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome",
)
```

### 5.3 BS / CF の検証

```python
# BS の検証
bs = statements.balance_sheet()
bs_result = validate_calculations(bs, calc_linkbase)

# CF の検証
cf = statements.cash_flow_statement()
cf_result = validate_calculations(cf, calc_linkbase)
```

---

## 6. テスト設計

`tests/test_xbrl/test_calc_check.py` に以下のテストを作成する。

### 6.1 テスト用ヘルパー

```python
from decimal import Decimal
from datetime import date
from typing import Literal
from edinet.models.financial import LineItem, FinancialStatement, StatementType
from edinet.xbrl.contexts import DurationPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource
from edinet.xbrl.linkbase.calculation import (
    CalculationArc, CalculationTree, CalculationLinkbase,
    parse_calculation_linkbase,
)


ROLE = "http://example.com/role/test"


def _item(
    local_name: str,
    value: Decimal,
    decimals: int | Literal["INF"] | None = -6,
) -> LineItem:
    """テスト用 LineItem を生成する。"""
    return LineItem(
        concept=f"{{http://example.com/ns}}{local_name}",
        namespace_uri="http://example.com/ns",
        local_name=local_name,
        label_ja=LabelInfo(text=local_name, role="label", lang="ja", source=LabelSource.STANDARD),
        label_en=LabelInfo(text=local_name, role="label", lang="en", source=LabelSource.STANDARD),
        value=value,
        unit_ref="JPY",
        decimals=decimals,
        context_id="ctx",
        period=DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)),
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=0,
    )


def _fs(*items: LineItem) -> FinancialStatement:
    """テスト用 FinancialStatement を生成する。"""
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)),
        items=items,
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


def _calc_linkbase(
    arcs: list[tuple[str, str, int]],  # (parent, child, weight)
    role_uri: str = ROLE,
) -> CalculationLinkbase:
    """テスト用 CalculationLinkbase を生成する。"""
    calc_arcs = tuple(
        CalculationArc(
            parent=parent,
            child=child,
            parent_href=f"dummy.xsd#{parent}",
            child_href=f"dummy.xsd#{child}",
            weight=weight,
            order=float(i),
            role_uri=role_uri,
        )
        for i, (parent, child, weight) in enumerate(arcs)
    )
    # roots の算出: 親のみで子でない concept
    parents = {a[0] for a in arcs}
    children = {a[1] for a in arcs}
    roots = tuple(p for p in parents if p not in children)

    tree = CalculationTree(role_uri=role_uri, arcs=calc_arcs, roots=roots)
    return CalculationLinkbase(source_path=None, trees={role_uri: tree})
```

### 6.2 テストケース一覧（約35テスト）

```python
class TestValidateCalculations:
    """validate_calculations() の単体テスト群。"""

    # --- 基本的な一致/不一致 ---

    def test_perfect_match(self):
        """親=子1+子2 が完全一致する場合。is_valid=True, error_count=0。
        GrossProfit(300) = NetSales(500) + CostOfSales(-200, weight=-1)。"""

    def test_within_tolerance(self):
        """差が tolerance 内（decimals=-6 で差=300,000 < tolerance=500,000）。
        is_valid=True。"""

    def test_exceeds_tolerance(self):
        """差が tolerance を超過（decimals=-6 で差=600,000 > tolerance=500,000）。
        is_valid=False, error_count=1。"""

    def test_at_tolerance_boundary(self):
        """差が tolerance と完全一致する場合（difference == tolerance）。
        difference <= tolerance なので is_valid=True。境界条件の検証。"""

    # --- decimals の扱い ---

    def test_decimals_inf_exact_match(self):
        """decimals="INF" で完全一致。tolerance=0, is_valid=True。"""

    def test_decimals_inf_mismatch(self):
        """decimals="INF" で 1 の差。tolerance=0, is_valid=False。"""

    def test_mixed_decimals(self):
        """parent_decimals=-3, child_decimals=-6 の混在。
        tolerance=0.5×10^6=500,000 (min=-6 を採用)。"""

    def test_decimals_none(self):
        """decimals=None の場合。tolerance=0（安全側: 完全一致）。"""

    # --- weight の扱い ---

    def test_weight_minus_one(self):
        """weight=-1 の減算。
        GrossProfit(300) = NetSales(500) + CostOfSales(200, weight=-1)。
        → expected = 500 + 200*(-1) = 300。"""

    def test_weight_mixed(self):
        """weight=1 と weight=-1 の混在。
        OperatingProfit(100) = GrossProfit(300, w=1) + SGA(200, w=-1)。"""

    # --- Fact 欠損のスキップ ---

    def test_missing_parent_fact_skipped(self):
        """親科目の Fact がない場合。skipped_count=1, checked_count=0。"""

    def test_missing_child_fact_skipped(self):
        """子科目の Fact が 1 つでもない場合。skipped_count=1, checked_count=0。"""

    def test_partial_children_missing(self):
        """子科目の一部のみ Fact がある場合。全体がスキップされること。"""

    # --- 中間ノードの検証（roots だけでなく全親を走査） ---

    def test_intermediate_parent_validated(self):
        """中間ノード（roots ではない親）が検証されること。
        OperatingProfit (root)
          ├── GrossProfit (w=1)      ← 中間ノード（子でもあり親でもある）
          │     ├── NetSales (w=1)
          │     └── CostOfSales (w=-1)
          └── SGA (w=-1)
        GrossProfit の検証（NetSales - CostOfSales）も行われること。
        checked_count=2（OperatingProfit + GrossProfit）。"""

    def test_hierarchical_chain(self):
        """多段チェーンで全段階が検証されること。
        ProfitLoss → OrdinaryIncome → OperatingIncome → GrossProfit
        の各段階が全て checked_count に含まれること。"""

    # --- 複数科目・複数ロール ---

    def test_multiple_children(self):
        """3 つ以上の子科目。
        Total(600) = A(100) + B(200) + C(300)。"""

    def test_multiple_roles(self):
        """複数の role URI を検証。各ロールの結果が統合されること。"""

    def test_specific_role_uri_filter(self):
        """role_uri を指定して特定ロールのみ検証。
        他のロールの科目はスキップされること。"""

    def test_same_concept_in_multiple_roles(self):
        """同一 concept が複数の role に出現し、各 role で異なる children を持つ場合。
        例: GrossProfit が連結PL role では NetSales+COGS、個別PL role では別の children。
        各 role で独立に検証され、checked_count が role 数分だけ加算されること。"""

    def test_nonexistent_role_uri(self):
        """存在しない role_uri を指定した場合。
        checked_count=0, skipped_count=0, is_valid=True。"""

    # --- 空のケース ---

    def test_empty_statement(self):
        """空の FinancialStatement。checked_count=0, skipped_count=全親科目数。"""

    def test_empty_linkbase(self):
        """空の CalculationLinkbase（trees={}）。
        checked_count=0, skipped_count=0。"""

    # --- 結果プロパティ ---

    def test_is_valid_true(self):
        """全科目一致時に is_valid=True。"""

    def test_is_valid_false(self):
        """不一致あり時に is_valid=False。"""

    def test_error_count(self):
        """error_count が正しいこと。"""

    def test_warning_count(self):
        """warning_count（現時点では常に 0）。"""

    def test_checked_count(self):
        """checked_count = passed_count + error_count であること。"""

    def test_skipped_count(self):
        """skipped_count が正しいこと。"""

    # --- 数値のエッジケース ---

    def test_negative_values(self):
        """マイナスの Fact 値（赤字企業の OperatingIncome = -100 等）。
        OperatingIncome(-100) = GrossProfit(50, w=1) + SGA(150, w=-1)。
        expected = 50 - 150 = -100。is_valid=True。"""

    def test_zero_value_parent(self):
        """親科目が 0 の場合。
        GrossProfit(0) = NetSales(200) + CostOfSales(200, w=-1)。
        expected = 200 - 200 = 0。is_valid=True。"""

    # --- 実データに近いテスト ---

    def test_real_world_rounding(self):
        """EDINET の典型的データ: decimals=-6（百万円単位）。
        GrossProfit(300000000) = NetSales(500000000) + COGS(200000000, w=-1)。
        tolerance=500,000 で 499,999 の差を許容。"""

    def test_real_world_boundary_pass(self):
        """EDINET の実データ境界: decimals=-6 で差=499,999（tolerance=500,000 以内）。
        is_valid=True。"""

    def test_real_world_boundary_fail(self):
        """EDINET の実データ境界: decimals=-6 で差=500,001（tolerance=500,000 超過）。
        is_valid=False。"""

    def test_nil_fact_excluded(self):
        """nil Fact は検証対象から除外されること。"""

    def test_text_fact_excluded(self):
        """テキスト Fact（value が str）は検証対象から除外されること。"""

    def test_same_local_name_different_namespace(self):
        """異なる namespace で同一 local_name を持つ LineItem が存在する場合。
        _build_fact_index は最初に出現した数値 Fact を採用すること。
        計算リンクベースは local_name で科目を識別するため正しい挙動。"""
```

### 6.3 ValidationIssue の検証

```python
class TestValidationIssue:
    """ValidationIssue dataclass のフィールド検証。"""

    def test_issue_fields(self):
        """ValidationIssue の各フィールドが正しく設定されること。"""

    def test_message_japanese(self):
        """message が日本語であること。"""
```

---

## 7. ファイル変更サマリ

| ファイル | 操作 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/validation/__init__.py` | **事前作成済み** | 空ファイル（パッケージ認識用。事前作業で作成済み、変更不要） |
| `src/edinet/xbrl/validation/calc_check.py` | **新規** | `validate_calculations()`, `CalcValidationResult`, `ValidationIssue`, `_build_fact_index()`, `_compute_tolerance()` — 約200〜300行 |
| `tests/test_xbrl/test_calc_check.py` | **新規** | 上記テスト群（約35テスト関数） |
| `tests/fixtures/calc_check/` | **新規** | テスト用フィクスチャ（必要に応じて） |

### 既存モジュールへの影響

- **影響なし**: `calculation.py`, `financial.py`, `statements.py` は全て read-only で利用
- 既存テスト: 一切変更なし
- `__init__.py`: 一切変更なし

### ディレクトリ構造

```
src/edinet/xbrl/validation/
├── __init__.py            # 事前作業で作成済み（空ファイル、変更不要）
└── calc_check.py          # 本 Lane で新規作成
```

`src/edinet/xbrl/validation/__init__.py` は事前作業（案 A）で空ファイルとして作成済み。Hatchling + src layout では `__init__.py` がないとサブパッケージとして import できないため。利用者は `from edinet.xbrl.validation.calc_check import validate_calculations` で直接インポートする。

---

## 8. 設計判断の記録

### Q: なぜ `FinancialStatement` を入力にするのか？`Statements` 全体ではないのか？

**A**: 計算バリデーションは特定の財務諸表（PL / BS / CF）に対して行われるため、`FinancialStatement` 単位が自然。`Statements` 全体を受け取ると、連結/個別、当期/前期の組み合わせで複数回検証する必要があり、利用者が結果を紐づけにくくなる。利用者が `statements.income_statement()` → `validate_calculations(pl, calc_linkbase)` の流れで使うことを想定。

### Q: `_build_fact_index` で同一 `local_name` の重複をどう扱うか？

**A**: `FinancialStatement` 構築時（`statements.py`）で重複解決済みのため、通常は 1 対 1。万が一残った場合は最初に出現したものを使用する（`if not in index` ガード）。計算リンクベースは `local_name` で科目を識別するため、名前空間の考慮は不要（同一 role 内では local_name がユニーク）。

### Q: `severity` が現時点で `"error"` のみなのに、なぜ `Literal["error", "warning"]` にするのか？

**A**: D1 の設計で将来の拡張を見据えている。例えば、tolerance の 50% を超えたが tolerance 内に収まった場合を `"warning"` として通知する拡張が考えられる。現時点では tolerance を超えたもののみを `"error"` として報告する。`warning_count` プロパティは将来のために存在する。

### Q: 丸め許容差で `decimals=None` を `0`（完全一致）とする理由は？

**A**: XBRL 2.1 仕様では `decimals` 属性が省略された場合の precision は不定である。安全側の設計として tolerance=0（完全一致）とし、false negative（見逃し）を防ぐ。実際の EDINET データではほぼ全ての数値 Fact に `decimals` が設定されているため、実運用上の影響は軽微。

### Q: `root` 以外の中間ノードの加算検証は行うか？

**A**: **行う。** XBRL 2.1 §5.2.5.2 は全ての summation-item 親子関係を検証対象と定義しており、`tree.roots` のみでは中間ノードの検証を見逃す。典型的な PL 計算ツリーでは:

```
ProfitLoss (root)
  ├── OrdinaryIncome (中間ノード)
  │     ├── OperatingIncome (中間ノード)
  │     │     ├── GrossProfit (中間ノード)
  │     │     └── SGA (w=-1)
  │     └── NonOperatingIncome (w=1)
  └── IncomeTaxes (w=-1)
```

roots = `(ProfitLoss,)` のみだが、GrossProfit / OperatingIncome / OrdinaryIncome の各段階も検証すべきである。実装では `tree.arcs` から全ユニーク親を収集して走査する。

### Q: 丸め許容差に min-decimals 方式を採用した理由は？

**A**: XBRL 2.1 §5.2.5.2 の厳密な定義は合算方式（`Σ(0.5 × 10^(-d_i))`）だが、min-decimals 方式（`0.5 × 10^(-min(d_i))`）を採用した。0.5 係数は XBRL 2.1 の丸め定義に由来する（各 Fact は ±0.5 × 10^(-decimals) の丸め誤差を持つ）。理由:

1. **EDINET の実データでは decimals がほぼ均一**（全て `-6` か全て `-3`）であるため、両方式の差は実運用上ほぼゼロ
2. 実装がシンプルで理解しやすい
3. Arelle 等の一般的な XBRL バリデータで広く使われている方式

混合精度のケース（例: parent=0, child=-6）では min-decimals の方が厳しい（子の数に依存しない固定 tolerance のため）が、EDINET では decimals がほぼ均一のため実質的に差は出ない。将来的に合算方式への移行を検討する余地を `_compute_tolerance()` の docstring に記載した。

### Q: `message` を日本語にする理由は？

**A**: CLAUDE.md の「コメントはやエラーメッセージは利用者の大半が日本人なので日本語」に従う。

---

## 9. 後続機能との接続点

| 利用先 | 利用方法 |
|--------|----------|
| **将来: validation/required** | D1 パターンの `RequiredValidationResult` を同様の設計で実装 |
| **将来: display/validation_report** | `CalcValidationResult` の可視化（Rich テーブル等） |
| **利用者のデータ品質チェック** | `is_valid` で合否判定、`issues` で不一致の詳細分析 |
| **将来: diff/revision** | 訂正前後の計算整合性比較 |

Lane 5 が提供する `validate_calculations()` は、D5 命名規約の `validate_*` パターンに従い、検証結果を `*ValidationResult` dataclass で返す standalone 関数として設計されている。XBRL 2.1 §5.2.5.2 の仕様に準拠した丸め許容差計算（`0.5 × 10^(-min(decimals))`、Arelle 等と同等の min-decimals 方式）により、実データでの false positive を最小化する。

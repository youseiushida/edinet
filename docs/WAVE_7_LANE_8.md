# Wave 7 / Lane 8 — Diff: 訂正差分 + 期間差分 (C1 + C2)

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 7 / Lane 8 を担当するエージェントです。
担当機能: diff（訂正前 vs 訂正後の Fact レベル差分、前期 vs 当期の科目増減）

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/financial/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/financial/diff.py` (新規)
   - `tests/test_xbrl/test_diff.py` (新規)
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
   - テスト用フィクスチャが必要な場合は直接テストコード内で構築すること

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - 例: `from edinet.financial.diff import diff_revisions, diff_periods` （OK）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_diff.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 6 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (LabelInfo)
     - `edinet.exceptions` (EdinetError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 8 — Diff: 訂正差分 + 期間差分 (C1 + C2)

## 0. 位置づけ

### FEATURES.md との対応

| Feature Key | 内容 |
|-------------|------|
| `diff/revision` | 訂正前 vs 訂正後の Fact レベル差分 |
| `diff/period` | 前期 vs 当期の科目増減 |

訂正前 vs 訂正後の Fact レベル差分（revision diff）と、前期 vs 当期の科目増減（period diff）を構造化する。

### SCOPE.md との関係

SCOPE.md が定める「複数のパース済みオブジェクトを受け取る比較ユーティリティ（diff, compare）」に該当。1件の Filing 内の前期比較データ取得もスコープ内。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.models.financial` | `LineItem`, `FinancialStatement` の比較 | read-only |
| `edinet.financial.statements` | `Statements` コンテナ | read-only |
| `edinet.xbrl.contexts` | `Period` 型 | read-only |
| `edinet.xbrl.taxonomy` | `LabelInfo` 型 | read-only |

他レーンとのファイル衝突なし。`financial/statements.py` は読み取りのみ。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| G-7 | **直接** | 訂正報告書の XBRL 構造。**完全差し替え**（差分ではない）。別 doc_id が付与。DEI フラグで訂正を検知 |
| J-5 | **直接** | 前期データの修正再表示。Prior{n}Year コンテキスト。前期 Fact 値は常に修正後。遡及適用軸 |
| J-6 | **直接** | 年度間データの一貫性。概念の 96.4% が安定。Context ID は相対参照。期間照合は startDate/endDate で行う |

---

## 1. 背景知識

### 1.1 訂正報告書の仕組み (G-7 より)

EDINET の訂正報告書（訂正有価証券報告書等）は以下の特性を持つ:

- **完全差し替え**: XBRL 全体が再提出される。差分 XML ではない
- **別 doc_id**: 訂正報告書には元の報告書とは別の `doc_id` が付与される
- **DEI フラグ**: 訂正を検知するための 4 つの DEI フィールド:

| DEI フィールド | 型 | 内容 |
|---------------|-----|------|
| `AmendmentFlagDEI` | bool | True = 訂正報告書 |
| `IdentificationOfDocumentSubjectToAmendmentDEI` | str | 訂正元の doc_id |
| `ReportAmendmentFlagDEI` | bool | True = 記述（テキスト）部分の訂正あり |
| `XBRLAmendmentFlagDEI` | bool | True = XBRL 数値部分の訂正あり |

- **複数回訂正**: 訂正チェーンは常に**元の doc_id** を参照（直前の訂正ではない）
- **API `parentDocID`**: EDINET API のレスポンスにも `parentDocID` フィールドがあり、DEI の `IdentificationOfDocumentSubjectToAmendmentDEI` と同値

### 1.2 diff_revisions の設計思想

訂正報告書は完全差し替えなので、**2 つの Statements オブジェクトを比較**する:

1. ユーザーが元報告書と訂正報告書をそれぞれ `Filing.xbrl()` でパース
2. `diff_revisions(original_stmts, corrected_stmts)` で差分を取得

本 Lane は比較ロジックのみを提供。Filing の取得・訂正チェーン解決は既存の `RevisionChain`（Wave 6 Lane 3）が担当。

### 1.3 前期データの仕組み (J-5 より)

有価証券報告書には**当期 + 前期**の財務データが含まれる:

| Context ID パターン | 意味 |
|--------------------|------|
| `CurrentYearDuration` | 当期（PL/CF） |
| `CurrentYearInstant` | 当期末（BS） |
| `Prior1YearDuration` | 前期（PL/CF） |
| `Prior1YearInstant` | 前期末（BS） |
| `Prior{n}Year...` | n 期前（経営指標等で最大 4 期前まで） |

**重要**: Context ID は **相対参照** である。`CurrentYearDuration` は常に「その Filing の当期」を指す。年度横断比較では Context ID ではなく `period.start_date` / `period.end_date` / `period.instant` で照合する (J-6)。

### 1.4 前期データの修正再表示 (J-5, J-6 より)

- 当期の有報に含まれる前期データは、**修正再表示後の値**が格納される
- 前期の有報の `CurrentYear` 値 vs 当期の有報の `Prior1Year` 値は **修正再表示がなければ 100% 一致**
- 修正再表示がある場合:
  - 遡及適用軸 `RetrospectiveApplicationAndRetrospectiveRestatementAxis` が使用される場合がある
  - ただしメンバー定義は提出者拡張に依存し、v0.1.0 では完全対応しない

### 1.5 概念の年度間安定性 (J-6 より)

- 標準タクソノミの概念名は **96.4%** が年度間で安定
- 年度あたり 20-30 概念が追加・削除される（主にマイナーな変更）
- **非推奨化**: `MinorityInterests` → `NonControllingInterests` 等の改名がある
  - v0.1.0 では手動マッピングは提供しない。`local_name` ベースの照合で対応

---

## 2. ゴール

完了条件:

```python
from edinet.financial.diff import diff_revisions, diff_periods, DiffResult, DiffItem

# --- 訂正差分 ---
# original_stmts, corrected_stmts は Filing.xbrl() の戻り値
result = diff_revisions(original_stmts, corrected_stmts)
assert isinstance(result, DiffResult)

# 変更された科目
for item in result.modified:
    assert isinstance(item, DiffItem)
    print(f"{item.label_ja}: {item.old_value} → {item.new_value} (差額: {item.difference})")

# 追加・削除された科目
print(f"追加: {len(result.added)} 件")
print(f"削除: {len(result.removed)} 件")
print(f"変更なし: {result.unchanged_count} 件")

# --- 期間差分 ---
pl_current = stmts.income_statement(period="current")
pl_prior = stmts.income_statement(period="prior")
period_diff = diff_periods(pl_prior, pl_current)
assert isinstance(period_diff, DiffResult)
```

---

## 3. スコープ / 非スコープ

### 3.1 スコープ

| # | 内容 | 対応 |
|---|------|------|
| S1 | 2 つの Statements の Fact レベル差分（訂正差分） | `diff_revisions()` |
| S2 | 2 つの FinancialStatement の科目増減（期間差分） | `diff_periods()` |
| S3 | 追加 / 削除 / 変更 / 変更なしの 4 分類 | `DiffResult` |
| S4 | 数値科目の差額計算 | `DiffItem.difference` |
| S5 | テキスト科目の変更検出 | `DiffItem.old_value` / `new_value` が str |

### 3.2 非スコープ

| # | 内容 | 理由 |
|---|------|------|
| N1 | 訂正チェーンの解決（Filing 取得） | Wave 6 Lane 3 の `RevisionChain` が担当 |
| N2 | 年度横断の時系列比較（3 期以上） | SCOPE.md: 年度横断集約はスコープ外。2 期比較は提供 |
| N3 | 非推奨概念のマッピングテーブル | v0.2.0 で検討。v0.1.0 は local_name 完全一致 |
| N4 | テキストブロックの内容差分（文字列 diff） | SCOPE.md: NLP はパイプライン外側。値の変更有無のみ検出 |
| N5 | 差分の Rich 表示 / HTML 表示 | Lane 7 が担当。本 Lane はデータ構造のみ |
| N6 | DEI フラグの自動解析（訂正種類の判定） | 既存 DEI 構造体で十分。diff は比較ロジックに集中 |

---

## 4. 実装計画

### 4.1 DiffItem dataclass

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from edinet.xbrl.taxonomy import LabelInfo


@dataclass(frozen=True, slots=True)
class DiffItem:
    """値が変更された科目。

    Attributes:
        concept: concept のローカル名。
        label_ja: 日本語ラベル（old 側のラベルを使用）。
        label_en: 英語ラベル（old 側のラベルを使用）。
        old_value: 変更前の値。
        new_value: 変更後の値。
        difference: new - old（数値の場合）。
            テキスト科目や片方が None の場合は None。
    """
    concept: str
    label_ja: LabelInfo
    label_en: LabelInfo
    old_value: Decimal | str | None
    new_value: Decimal | str | None
    difference: Decimal | None
```

### 4.2 DiffResult dataclass

```python
from edinet.models.financial import LineItem


@dataclass(frozen=True, slots=True)
class DiffResult:
    """差分比較の結果。

    Attributes:
        added: new にのみ存在する科目。
        removed: old にのみ存在する科目。
        modified: 値が変更された科目。
        unchanged_count: 値が変更されていない科目の件数。
    """
    added: tuple[LineItem, ...]
    removed: tuple[LineItem, ...]
    modified: tuple[DiffItem, ...]
    unchanged_count: int

    @property
    def has_changes(self) -> bool:
        """変更があるかどうかを返す。"""
        return bool(self.added or self.removed or self.modified)

    @property
    def total_compared(self) -> int:
        """比較対象の総科目数を返す。"""
        return len(self.added) + len(self.removed) + len(self.modified) + self.unchanged_count

    def summary(self) -> str:
        """差分のサマリー文字列を返す。

        Returns:
            ``"追加: 2, 削除: 1, 変更: 3, 変更なし: 50"`` のような文字列。
        """
        return (
            f"追加: {len(self.added)}, "
            f"削除: {len(self.removed)}, "
            f"変更: {len(self.modified)}, "
            f"変更なし: {self.unchanged_count}"
        )
```

### 4.3 diff_revisions()

```python
from edinet.financial.statements import Statements


def diff_revisions(
    original: Statements,
    corrected: Statements,
) -> DiffResult:
    """訂正前 vs 訂正後の Fact レベル差分を返す。

    2 つの Statements を LineItem の local_name をキーに照合し、
    追加・削除・変更・変更なしに分類する。

    比較対象は全 LineItem（PL + BS + CF + その他、全期間・全 dimension）。
    連結/個別の絞り込みが必要な場合は、事前に
    ``Statements.income_statement(consolidated=True)`` 等で
    FinancialStatement を取得し、``diff_periods()`` を使用すること。

    Args:
        original: 訂正前の Statements。
        corrected: 訂正後の Statements。

    Returns:
        DiffResult。
    """
```

**マッチング戦略**:

```
1. original の全 LineItem を走査
   - キー: (local_name, context_id) のタプル
     → 同一 concept + 同一 context（= 同一期間・同一 dimension）で照合
   - 連結/個別のフィルタは行わない（全 LineItem を比較対象にする）
2. corrected の全 LineItem も同様にキー付き辞書を構築
3. キーの集合演算:
   - original にのみ存在 → removed
   - corrected にのみ存在 → added
   - 両方に存在:
     - 値が同一 → unchanged (カウントのみ)
     - 値が異なる → modified (DiffItem 生成)
```

**設計判断: consolidated フィルタを持たない理由**:
- 連結/個別の判定ロジックは `Statements.income_statement()` 等に既に実装されている
- diff_revisions で同じロジックを再実装すると DRY 違反になる
- ユーザーが連結 PL のみの訂正差分を取りたい場合は以下で対応可能:
  ```python
  orig_pl = original_stmts.income_statement(consolidated=True)
  corr_pl = corrected_stmts.income_statement(consolidated=True)
  result = diff_periods(orig_pl, corr_pl)
  ```

**context_id ベースのマッチング理由**:
- 同一 Filing の訂正では context_id 体系が同一
- `CurrentYearDuration` は両方の Filing で同じ期間を指す
- dimension も含めた正確なマッチングが可能

### 4.4 diff_periods()

```python
from edinet.models.financial import FinancialStatement


def diff_periods(
    prior: FinancialStatement,
    current: FinancialStatement,
) -> DiffResult:
    """前期 vs 当期の科目増減を返す。

    2 つの FinancialStatement を LineItem の local_name をキーに照合し、
    追加・削除・変更・変更なしに分類する。

    **注意**: 同一 Filing 内の current vs prior を比較するのがデフォルトの
    ユースケース。異なる年度の Filing を比較する場合、概念名の改廃により
    不正確な結果になる可能性がある（v0.1.0 では非推奨概念のマッピングなし）。

    Args:
        prior: 前期の FinancialStatement。
        current: 当期の FinancialStatement。

    Returns:
        DiffResult。
    """
```

**マッチング戦略**:

period diff では context_id が異なる（`Prior1YearDuration` vs `CurrentYearDuration`）ため、**local_name のみ** をキーにする:

```
1. prior の全 LineItem を local_name → LineItem の辞書に変換
   - 同一 local_name が複数ある場合は先頭を使用（警告あり）
2. current も同様
3. local_name の集合演算:
   - prior にのみ存在 → removed（前期にはあったが当期にはない科目）
   - current にのみ存在 → added（当期に新規追加された科目）
   - 両方に存在 → 値を比較して modified or unchanged
```

### 4.5 _compute_difference() ヘルパー

```python
def _compute_difference(
    old_value: Decimal | str | None,
    new_value: Decimal | str | None,
) -> Decimal | None:
    """2 つの値の差額を計算する。

    両方が Decimal の場合のみ差額を返す。
    それ以外（str, None, 型混在）の場合は None を返す。

    Args:
        old_value: 変更前の値。
        new_value: 変更後の値。

    Returns:
        new_value - old_value。計算不可の場合は None。
    """
    if isinstance(old_value, Decimal) and isinstance(new_value, Decimal):
        return new_value - old_value
    return None
```

### 4.6 _values_equal() ヘルパー

```python
def _values_equal(
    a: Decimal | str | None,
    b: Decimal | str | None,
) -> bool:
    """2 つの値が等しいかを判定する。

    Decimal 同士は数値比較、str 同士は文字列比較、
    None 同士は等しいと判定する。型が異なる場合は不等。

    Args:
        a: 値 A。
        b: 値 B。

    Returns:
        等しければ True。
    """
```

---

## 5. 実装の注意点

### 5.1 マッチングキーの選択

**diff_revisions**: `(local_name, context_id)` ペアをキーにする。訂正前後で context_id 体系は同一のため、正確なマッチングが可能。

**diff_periods**: `local_name` のみをキーにする。context_id は期間によって異なる（`Prior1Year...` vs `CurrentYear...`）ため、concept 名でのみ照合する。

### 5.2 同一 local_name の重複

同一 Filing 内で同じ `local_name` が複数回出現するケース（異なる dimension 等）がある。

- **diff_revisions**: `(local_name, context_id)` で一意化されるため問題なし
- **diff_periods**: `local_name` のみでは重複しうる。先頭の LineItem を使用し、重複があれば `warnings.warn()` で警告を出す（既存コードと同じ方式）

### 5.3 テキスト Fact の比較

テキスト Fact（`value` が `str` 型）の変更は「異なる文字列」として検出する。文字列の内容差分（どこが変わったか）は提供しない。

### 5.4 Decimal の比較精度

`Decimal` の比較は Python の `==` で行う。`decimals` 属性の違いによる見かけ上の差異（`1000` vs `1000.000`）は `Decimal` の仕様上等しいと判定される。

### 5.5 nil Fact の扱い

`value=None`（nil Fact）同士は等しいと判定する。片方が None で片方が値を持つ場合は modified として扱う。

### 5.6 空の FinancialStatement

`FinancialStatement.items` が空タプルの場合:
- prior が空、current が非空 → 全 current が added
- prior が非空、current が空 → 全 prior が removed
- 両方空 → unchanged_count = 0 の DiffResult

---

## 6. テスト計画

### 6.1 テストファイル

`tests/test_xbrl/test_diff.py` に全テストを作成する。

### 6.2 テスト方式

テストは LineItem / FinancialStatement / Statements のフィクスチャデータをヘルパー関数で直接構築する方式。XML フィクスチャは使用しない（デトロイト派）。

```python
def _make_line_item(
    local_name: str,
    value: Decimal | str | None = None,
    context_id: str = "CurrentYearDuration",
    **kwargs,
) -> LineItem:
    """テスト用 LineItem を生成するヘルパー。"""
```

### 6.3 テストケース一覧（~27 件）

```python
class TestDiffRevisions:
    def test_identical_statements(self):
        """同一の Statements 同士で変更なし。"""

    def test_single_modified_value(self):
        """1 科目の値が変更された場合 modified に分類される。"""

    def test_added_item(self):
        """訂正後にのみ存在する科目が added に分類される。"""

    def test_removed_item(self):
        """訂正前にのみ存在する科目が removed に分類される。"""

    def test_mixed_changes(self):
        """added + removed + modified + unchanged の混合ケース。"""

    def test_difference_calculated(self):
        """数値科目の DiffItem.difference が正しく計算される。"""

    def test_text_value_change(self):
        """テキスト科目の変更が検出される。"""

    def test_nil_to_value(self):
        """None → Decimal の変更が modified に分類される。"""

    def test_value_to_nil(self):
        """Decimal → None の変更が modified に分類される。"""

    def test_nil_to_nil_unchanged(self):
        """None → None は unchanged に分類される。"""

    def test_context_id_matching(self):
        """context_id が異なる同名科目は別科目として扱われる。"""

    def test_empty_statements(self):
        """空の Statements 同士で空の DiffResult が返る。"""


class TestDiffPeriods:
    def test_identical_periods(self):
        """同一の FinancialStatement 同士で変更なし。"""

    def test_value_increase(self):
        """売上高増加が modified + 正の difference で検出される。"""

    def test_value_decrease(self):
        """利益減少が modified + 負の difference で検出される。"""

    def test_new_concept_in_current(self):
        """当期にのみ存在する科目が added に分類される。"""

    def test_removed_concept_in_current(self):
        """前期にのみ存在する科目が removed に分類される。"""

    def test_local_name_matching(self):
        """local_name ベースで前期/当期が照合される。"""

    def test_empty_prior(self):
        """空の prior で全 current が added。"""

    def test_empty_current(self):
        """空の current で全 prior が removed。"""

    def test_both_empty(self):
        """両方空で空の DiffResult。"""


class TestDiffResult:
    def test_has_changes_true(self):
        """変更がある場合 has_changes が True。"""

    def test_has_changes_false(self):
        """変更がない場合 has_changes が False。"""

    def test_total_compared(self):
        """total_compared が全科目数を返す。"""

    def test_summary(self):
        """summary() が正しいフォーマットの文字列を返す。"""


class TestHelpers:
    def test_compute_difference_decimals(self):
        """Decimal 同士の差額が正しく計算される。"""

    def test_compute_difference_mixed_types(self):
        """型が異なる場合 None が返る。"""

    def test_values_equal_decimals(self):
        """Decimal 同士の等価判定。"""

    def test_values_equal_none(self):
        """None 同士が等しいと判定される。"""
```

---

## 7. 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `src/edinet/financial/diff.py` | 新規 | `DiffItem`, `DiffResult`, `diff_revisions()`, `diff_periods()` + ヘルパー群 |
| `tests/test_xbrl/test_diff.py` | 新規 | ~27 テストケース |

### 変更行数見積もり

| ファイル | 行数 |
|---------|------|
| `diff.py` | ~350 行 |
| テスト | ~600 行 |
| **合計** | **~950 行** |

---

## 8. 検証手順

1. `uv run pytest tests/test_xbrl/test_diff.py -v` で新規テスト全 PASS
2. `uv run pytest` で全テスト PASS（既存テスト破壊なし）
3. `uv run ruff check src/edinet/financial/diff.py tests/test_xbrl/test_diff.py` でリント PASS

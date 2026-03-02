# 並列実装の安全ルール（必ず遵守）

あなたは Wave 6 / Lane 6 を担当するエージェントです。
担当機能: fiscal_year

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/dimensions/fiscal_year.py` (新規)
   - `src/edinet/xbrl/dimensions/period_variants.py` (変更)
   - `tests/test_xbrl/test_fiscal_year.py` (新規)
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

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.financial.dimensions.fiscal_year import detect_fiscal_year` （OK）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_fiscal_year.py` に作成

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
     - `edinet.financial.dimensions.period_variants` (PeriodClassification, classify_periods)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果を報告すること

---

# LANE 6 — dimensions/fiscal_year: 決算期判定と変則決算検出

## 0. 位置づけ

### FEATURES.md との対応

Wave 6 Lane 6 は、FEATURES.md の **dimensions/fiscal_year** に対応する。DEI の日付情報から決算期の構造的メタデータ（決算月、期間月数、通期/半期、変則決算の有無等）を抽出し、利用者が企業の会計期間特性を分析できるようにする。

FEATURES.md の定義:

> - dimensions/fiscal_year: 変則決算の判定 [TODO]
>   - depends: dei
>   - detail: DEI の日付情報から変則決算かどうかを判定

### WAVE_6.md での位置

> Lane F: dimensions/fiscal_year → 新規 dimensions/fiscal_year.py, period_variants.py 拡張

### 設計方針: D4 / D5 の遵守

- **D4**: standalone 関数 `detect_fiscal_year(dei)` として実装（データ変換/検出の入出力が別型のため）
- **D5**: `detect_*` プレフィックスで発見・判定結果を返す

### Risk 5 の解決（classify_periods vs detect_fiscal_year の責任分離）

| 関数 | 責任 | 出力 | 利用場面 |
|------|------|------|---------|
| `classify_periods(dei)` | コンテキスト選択 | `PeriodClassification`（当期/前期の Duration/Instant） | BS/PL 構築時に当期/前期を判別 |
| `detect_fiscal_year(dei)` | メタデータ抽出 | `FiscalYearInfo`（決算月、変則決算か等） | 企業分析、スクリーニング、データ品質チェック |

両者は入力が同じ（DEI）だが責任が明確に異なるため、別モジュールで正しい。統合は不要。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.dei` | `DEI`, `PeriodType` | read-only |
| `edinet.financial.dimensions.period_variants` | `PeriodClassification`, `classify_periods` | read-only (変更は追加のみ) |

他レーンとのファイル衝突なし。`period_variants.py` は Lane 6 のみが変更する。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| E-3 | 直接 | 期間の扱い。DEI の日付フィールドの意味と使い方 |
| F-1 | 関連 | DEI フィールドの一覧。`type_of_current_period` の取りうる値 |
| D-4 | 関連 | メソッド配置規約（standalone 関数として実装） |
| D-5 | 関連 | 命名規約（detect_* プレフィックス） |

---

## 1. 背景知識

### 1.1 DEI の日付フィールド

`DEI` dataclass（`dei.py`）には以下の日付関連フィールドが存在する:

| フィールド | 型 | 意味 | 例 |
|-----------|------|------|-----|
| `current_fiscal_year_start_date` | `date \| None` | 当事業年度開始日 | `2024-04-01` |
| `current_period_end_date` | `date \| None` | 当会計期間終了日 | `2025-03-31` |
| `current_fiscal_year_end_date` | `date \| None` | 当事業年度終了日（決算日） | `2025-03-31` |
| `type_of_current_period` | `PeriodType \| str \| None` | 当会計期間の種類 | `PeriodType.FY` / `PeriodType.HY` |
| `previous_fiscal_year_start_date` | `date \| None` | 前事業年度開始日 | `2023-04-01` |
| `previous_fiscal_year_end_date` | `date \| None` | 前事業年度終了日 | `2024-03-31` |
| `comparative_period_end_date` | `date \| None` | 比較対象会計期間終了日 | `2024-03-31` |

### 1.2 日本企業の決算パターン

| パターン | 決算月 | 期間 | 頻度 |
|---------|--------|------|------|
| **3月決算** | 3月 | 4月〜3月（12ヶ月） | 全体の約 65% |
| **12月決算** | 12月 | 1月〜12月（12ヶ月） | 約 10%（主にグローバル企業） |
| **9月決算** | 9月 | 10月〜9月 | 少数 |
| **6月決算** | 6月 | 7月〜6月 | 少数 |
| **変則決算** | 任意 | 12ヶ月以外（設立初年度、決算期変更等） | 非常に少数 |
| **半期報告** | - | 6ヶ月 | 半期報告書の提出時 |

### 1.3 変則決算とは

変則決算は `type_of_current_period == PeriodType.FY`（通期）であるにもかかわらず、実際の期間が12ヶ月でないケースを指す:

- **設立初年度**: 設立日から最初の決算日まで（例: 6ヶ月、9ヶ月）
- **決算期変更**: 3月決算から12月決算に変更する場合の移行期間（例: 9ヶ月）
- **合併・会社分割**: 事業年度が短縮される場合

変則決算の検出は、財務分析で前年比較を行う際に重要（12ヶ月ではない期間の数値を単純比較すると誤解を招く）。

### 1.4 期間月数の概算方法

DEI には「期間月数」を直接報告するフィールドがないため、開始日と終了日から計算する必要がある:

```python
delta_days = (end_date - start_date).days + 1  # 両端含む
period_months = round(delta_days / 30.44)  # 概算（四捨五入）
```

**30.44** は 365.25 / 12 で、平均月日数。閏年を考慮した概算値。

例:
- `2024-04-01` 〜 `2025-03-31`: 366日 → 12.02 → 12ヶ月
- `2024-10-01` 〜 `2025-03-31`: 183日 → 6.01 → 6ヶ月
- `2024-07-01` 〜 `2025-03-31`: 274日 → 9.00 → 9ヶ月

---

## 2. ゴール

### 2.1 機能要件

1. **`detect_fiscal_year()` 関数の実装**
   - 入力: `DEI`
   - 出力: `FiscalYearInfo`
   - DEI の日付フィールドから決算期のメタデータを構造化して返す

2. **`FiscalYearInfo` dataclass の定義**
   - `start_date`: 当事業年度開始日
   - `end_date`: 当会計期間終了日
   - `fiscal_year_end_date`: 決算期末日（当事業年度終了日）
   - `period_months`: 期間月数（概算、四捨五入）
   - `period_type`: 期間種類（`PeriodType.FY` / `PeriodType.HY` / その他の文字列 / `None`）
   - `is_full_year`: 12ヶ月通期か（`PeriodType.FY` かつ期間月数12ヶ月）
   - `is_irregular`: 変則決算か（`PeriodType.FY` なのに12ヶ月でない）
   - `fiscal_year_end_month`: 決算月（1〜12）

3. **`period_variants.py` への最小限の変更**（もし必要であれば）
   - `detect_fiscal_year` と `classify_periods` の接続点を提供する
   - 既存の `PeriodClassification` / `classify_periods` のインターフェースは変更しない

### 2.2 非ゴール

- **`PeriodClassification` への統合**: Risk 5 の解決により、責任分離を維持。統合しない
- **前事業年度の `FiscalYearInfo`**: 当期のみを対象。前期の情報が必要な場合は利用者が前期の DEI で呼び出す
- **月次の正確な計算**: 概算で十分。会計上の正確な月数は DEI に含まれないため
- **`LineItem` へのフィールド追加**: D3 により禁止

---

## 3. データモデル設計

### 3.1 FiscalYearInfo (frozen dataclass)

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from edinet.xbrl.dei import PeriodType


@dataclass(frozen=True, slots=True)
class FiscalYearInfo:
    """DEI から抽出した決算期メタデータ。

    DEI の日付情報を構造化し、決算期の特性（通期/半期、
    変則決算の有無、決算月等）を提供する。

    Attributes:
        start_date: 当事業年度開始日。DEI に未設定の場合は None。
        end_date: 当会計期間終了日。DEI に未設定の場合は None。
        fiscal_year_end_date: 決算期末日（当事業年度終了日）。
            DEI に未設定の場合は None。
        period_months: 期間月数（概算、四捨五入）。
            開始日または終了日が None の場合は None。
        period_type: 期間種類。DEI の type_of_current_period の値。
            PeriodType.FY（通期）、PeriodType.HY（半期）、
            未知の文字列、または None。
        is_full_year: 12ヶ月通期かどうか。
            PeriodType.FY かつ period_months が 12 の場合のみ True。
            日付情報が不足している場合は False。
        is_irregular: 変則決算かどうか。
            PeriodType.FY なのに period_months が 12 でない場合に True。
            日付情報が不足している場合は False。
        fiscal_year_end_month: 決算月（1〜12）。
            fiscal_year_end_date の月。未設定の場合は None。
    """
    start_date: date | None
    end_date: date | None
    fiscal_year_end_date: date | None
    period_months: int | None
    period_type: PeriodType | str | None
    is_full_year: bool
    is_irregular: bool
    fiscal_year_end_month: int | None
```

**設計根拠**:

- `is_full_year` と `is_irregular` を算出済みフィールドにする理由: 利用者が最も頻繁にチェックする条件であり、property にするとロジックが dataclass 内に入り込む。frozen dataclass の構築時に確定するため、フィールドとして持つ方が自然
- `period_type` が `PeriodType | str | None` である理由: DEI の `type_of_current_period` フィールドの型をそのまま反映。未知の値が文字列のまま格納される可能性がある
- `fiscal_year_end_month` を独立フィールドにする理由: `fiscal_year_end_date.month` で取得可能だが、`fiscal_year_end_date` が `None` の場合の null チェックを利用者に強いない設計

---

## 4. 実装詳細

### 4.1 期間月数の概算: `_calc_months()`

```python
def _calc_months(start: date, end: date) -> int:
    """期間の月数を概算する。

    開始日・終了日の両端を含む日数を 30.44（= 365.25 / 12）で
    割り、四捨五入して整数月数を返す。
    会計期間は開始日と終了日を共に含むため +1 日とする。

    Args:
        start: 期間開始日。
        end: 期間終了日。

    Returns:
        概算月数（整数）。

    Examples:
        >>> _calc_months(date(2024, 4, 1), date(2025, 3, 31))
        12
        >>> _calc_months(date(2024, 10, 1), date(2025, 3, 31))
        6
        >>> _calc_months(date(2024, 7, 1), date(2025, 3, 31))
        9
    """
    delta_days = (end - start).days + 1  # 両端含む（会計期間の慣行）
    return round(delta_days / 30.44)
```

### 4.2 メイン関数: `detect_fiscal_year()`

```python
from edinet.xbrl.dei import DEI, PeriodType


def detect_fiscal_year(dei: DEI) -> FiscalYearInfo:
    """DEI の日付情報から決算期メタデータを抽出する。

    DEI の各日付フィールド（current_fiscal_year_start_date,
    current_period_end_date, current_fiscal_year_end_date,
    type_of_current_period）を構造化し、決算期の特性を判定する。

    日付フィールドが未設定（None）の場合は、該当する判定結果も
    None または False となる（graceful degradation）。

    Args:
        dei: extract_dei() で取得した DEI。

    Returns:
        FiscalYearInfo。

    Examples:
        >>> # 典型的な3月決算（通期）
        >>> info = detect_fiscal_year(dei)
        >>> info.fiscal_year_end_month
        3
        >>> info.is_full_year
        True
        >>> info.is_irregular
        False

        >>> # 変則決算（設立初年度、9ヶ月）
        >>> info = detect_fiscal_year(dei_irregular)
        >>> info.period_months
        9
        >>> info.is_full_year
        False
        >>> info.is_irregular
        True
    """
    start = dei.current_fiscal_year_start_date
    end = dei.current_period_end_date
    fy_end = dei.current_fiscal_year_end_date
    period_type = dei.type_of_current_period

    # 期間月数の計算（両方の日付が必要）
    period_months: int | None = None
    if start is not None and end is not None:
        period_months = _calc_months(start, end)

    # 通期（FY）かどうかの判定
    is_fy = isinstance(period_type, PeriodType) and period_type == PeriodType.FY

    # 12ヶ月通期の判定
    is_full_year = is_fy and period_months == 12

    # 変則決算の判定（FY なのに 12ヶ月でない）
    is_irregular = is_fy and period_months is not None and period_months != 12

    # 決算月の抽出
    fiscal_year_end_month: int | None = None
    if fy_end is not None:
        fiscal_year_end_month = fy_end.month

    return FiscalYearInfo(
        start_date=start,
        end_date=end,
        fiscal_year_end_date=fy_end,
        period_months=period_months,
        period_type=period_type,
        is_full_year=is_full_year,
        is_irregular=is_irregular,
        fiscal_year_end_month=fiscal_year_end_month,
    )
```

### 4.3 period_variants.py への変更

`period_variants.py` への変更は**最小限**に留める。既存の `classify_periods()` / `PeriodClassification` は一切変更しない。

変更内容: なし（当初計画時点）。

`detect_fiscal_year` と `classify_periods` は入力が同じ（DEI）だが出力が完全に異なるため、統合の必要はない。利用者は必要に応じて両方を呼び出す:

```python
periods = classify_periods(dei)       # コンテキスト選択用
fy_info = detect_fiscal_year(dei)     # メタデータ用
```

`period_variants.py` への変更が必要になるケースは、将来的に `PeriodClassification` に `fiscal_year_info` プロパティを追加する場合のみ。これは Wave 6 のスコープ外。

---

## 5. 使用例

### 5.1 基本的な使い方

```python
from edinet.xbrl.dei import extract_dei
from edinet.financial.dimensions.fiscal_year import detect_fiscal_year

# DEI を抽出
dei = extract_dei(parsed_xbrl.facts)

# 決算期メタデータを取得
fy = detect_fiscal_year(dei)

print(f"決算月: {fy.fiscal_year_end_month}月")
print(f"期間: {fy.period_months}ヶ月")
print(f"通期: {fy.is_full_year}")
print(f"変則決算: {fy.is_irregular}")
```

### 5.2 変則決算のスクリーニング

```python
# 複数企業の変則決算を検出
for filing in filings:
    dei = extract_dei(filing.xbrl.facts)
    fy = detect_fiscal_year(dei)
    if fy.is_irregular:
        print(f"{dei.filer_name_ja}: {fy.period_months}ヶ月決算（変則）")
```

### 5.3 決算月別の分類

```python
# 決算月別に企業を分類
march_filers = []
december_filers = []

for filing in filings:
    dei = extract_dei(filing.xbrl.facts)
    fy = detect_fiscal_year(dei)
    if fy.fiscal_year_end_month == 3:
        march_filers.append(dei.filer_name_ja)
    elif fy.fiscal_year_end_month == 12:
        december_filers.append(dei.filer_name_ja)
```

### 5.4 classify_periods との組み合わせ

```python
from edinet.financial.dimensions.period_variants import classify_periods
from edinet.financial.dimensions.fiscal_year import detect_fiscal_year

dei = extract_dei(parsed_xbrl.facts)

# コンテキスト選択用（BS/PL 構築に使用）
periods = classify_periods(dei)
print(f"当期: {periods.current_duration}")
print(f"前期: {periods.prior_duration}")

# メタデータ用（分析に使用）
fy = detect_fiscal_year(dei)
print(f"決算月: {fy.fiscal_year_end_month}月")
print(f"変則: {fy.is_irregular}")
```

---

## 6. テスト設計

`tests/test_xbrl/test_fiscal_year.py` に以下のテストを作成する。

### 6.1 テスト用ヘルパー

```python
import pytest
from datetime import date
from edinet.xbrl.dei import DEI, PeriodType
from edinet.financial.dimensions.fiscal_year import detect_fiscal_year, FiscalYearInfo


def _make_dei(
    *,
    start: date | None = date(2024, 4, 1),
    end: date | None = date(2025, 3, 31),
    fy_end: date | None = date(2025, 3, 31),
    period_type: PeriodType | str | None = PeriodType.FY,
) -> DEI:
    """テスト用の最小限 DEI を生成する。

    指定した 4 フィールド以外の DEI の 23 フィールド（edinet_code,
    filer_name_ja 等）は全て DEI のデフォルト値（None）が使われる。
    """
    return DEI(
        current_fiscal_year_start_date=start,
        current_period_end_date=end,
        current_fiscal_year_end_date=fy_end,
        type_of_current_period=period_type,
    )
```

### 6.2 テストケース一覧（約16テスト）

```python
@pytest.mark.small
@pytest.mark.unit
class TestDetectFiscalYear:
    """detect_fiscal_year() の単体テスト群。"""

    # --- 典型的な決算パターン ---

    def test_march_fiscal_year(self):
        """3月決算、FY、12ヶ月。
        start=2024-04-01, end=2025-03-31, fy_end=2025-03-31。
        is_full_year=True, is_irregular=False, fiscal_year_end_month=3。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.start_date == date(2024, 4, 1)
        assert info.end_date == date(2025, 3, 31)
        assert info.fiscal_year_end_date == date(2025, 3, 31)
        assert info.period_months == 12
        assert info.period_type == PeriodType.FY
        assert info.is_full_year is True
        assert info.is_irregular is False
        assert info.fiscal_year_end_month == 3

    def test_december_fiscal_year(self):
        """12月決算。fiscal_year_end_month=12。"""
        dei = _make_dei(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            fy_end=date(2024, 12, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 12
        assert info.is_full_year is True
        assert info.fiscal_year_end_month == 12

    def test_half_year(self):
        """半期報告（HY）、6ヶ月。is_full_year=False, is_irregular=False。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2024, 9, 30),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.HY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 6
        assert info.period_type == PeriodType.HY
        assert info.is_full_year is False
        assert info.is_irregular is False  # HY なので変則ではない

    # --- 変則決算 ---

    def test_irregular_fiscal_year_9months(self):
        """変則決算（FY だが 9ヶ月）。is_irregular=True。
        決算期変更による移行期間など。"""
        dei = _make_dei(
            start=date(2024, 7, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 9
        assert info.is_full_year is False
        assert info.is_irregular is True

    def test_irregular_fiscal_year_short(self):
        """変則決算（FY だが 6ヶ月）。設立初年度など。"""
        dei = _make_dei(
            start=date(2024, 10, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 6
        assert info.is_full_year is False
        assert info.is_irregular is True

    def test_irregular_fiscal_year_15months(self):
        """変則決算（FY だが 15ヶ月）。3月→6月への決算期変更。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2025, 6, 30),
            fy_end=date(2025, 6, 30),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 15
        assert info.is_full_year is False
        assert info.is_irregular is True

    def test_irregular_fiscal_year_1month(self):
        """極端な変則決算（FY だが 1ヶ月）。
        設立直後の決算期変更など。_calc_months の境界ケース。"""
        dei = _make_dei(
            start=date(2025, 3, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 1
        assert info.is_full_year is False
        assert info.is_irregular is True

    # --- フィールド単体の検証 ---

    def test_fiscal_year_end_month(self):
        """fiscal_year_end_month が正しく抽出されること。"""
        for month in [3, 6, 9, 12]:
            dei = _make_dei(fy_end=date(2025, month, 28 if month != 6 else 30))
            info = detect_fiscal_year(dei)
            assert info.fiscal_year_end_month == month

    def test_period_months_calculation(self):
        """期間月数の概算が正しいこと。"""
        # 12ヶ月
        dei = _make_dei(start=date(2024, 4, 1), end=date(2025, 3, 31))
        assert detect_fiscal_year(dei).period_months == 12

        # 6ヶ月
        dei = _make_dei(start=date(2024, 4, 1), end=date(2024, 9, 30))
        assert detect_fiscal_year(dei).period_months == 6

        # 3ヶ月
        dei = _make_dei(start=date(2024, 1, 1), end=date(2024, 3, 31))
        assert detect_fiscal_year(dei).period_months == 3

    def test_period_type_fy(self):
        """period_type が PeriodType.FY であること。"""
        dei = _make_dei(period_type=PeriodType.FY)
        assert detect_fiscal_year(dei).period_type == PeriodType.FY

    def test_period_type_hy(self):
        """period_type が PeriodType.HY であること。"""
        dei = _make_dei(period_type=PeriodType.HY)
        assert detect_fiscal_year(dei).period_type == PeriodType.HY

    # --- 欠損データのハンドリング ---

    def test_dei_missing_all_dates(self):
        """全日付フィールドが None の場合。graceful degradation。
        period_months=None, is_full_year=False, is_irregular=False,
        fiscal_year_end_month=None。"""
        dei = _make_dei(start=None, end=None, fy_end=None, period_type=None)
        info = detect_fiscal_year(dei)
        assert info.start_date is None
        assert info.end_date is None
        assert info.fiscal_year_end_date is None
        assert info.period_months is None
        assert info.period_type is None
        assert info.is_full_year is False
        assert info.is_irregular is False
        assert info.fiscal_year_end_month is None

    def test_dei_partial_dates(self):
        """開始日のみ設定されている場合。
        period_months=None（計算不可）、is_full_year=False。"""
        dei = _make_dei(start=date(2024, 4, 1), end=None, fy_end=None)
        info = detect_fiscal_year(dei)
        assert info.start_date == date(2024, 4, 1)
        assert info.end_date is None
        assert info.period_months is None
        assert info.is_full_year is False
        assert info.is_irregular is False

    def test_is_full_year_false_for_hy(self):
        """HY の場合、たとえ 12ヶ月であっても is_full_year=False。
        （通常 HY で 12ヶ月はありえないが、防御的にテスト）"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2025, 3, 31),
            period_type=PeriodType.HY,
        )
        info = detect_fiscal_year(dei)
        assert info.is_full_year is False  # HY なので通期ではない

    # --- 未知の period_type ---

    def test_unknown_period_type_string(self):
        """未知の period_type 文字列の場合。
        PeriodType.FY でないため is_full_year=False, is_irregular=False。
        isinstance(period_type, PeriodType) ガードの回帰テスト。"""
        dei = _make_dei(period_type="Q1")
        info = detect_fiscal_year(dei)
        assert info.period_type == "Q1"
        assert info.is_full_year is False
        assert info.is_irregular is False
```

---

## 7. ファイル変更サマリ

| ファイル | 操作 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/dimensions/fiscal_year.py` | **新規** | `detect_fiscal_year()`, `FiscalYearInfo`, `_calc_months()` — 約80〜120行 |
| `src/edinet/xbrl/dimensions/period_variants.py` | **変更なし** | WAVE_6.md では拡張の可能性を想定していたが、調査の結果 `classify_periods`（コンテキスト選択用）と `detect_fiscal_year`（メタデータ用）の責任が明確に異なるため変更不要と判断 |
| `tests/test_xbrl/test_fiscal_year.py` | **新規** | 上記テスト群（約16テスト関数） |

### 既存モジュールへの影響

- **影響なし**: `dei.py`, `period_variants.py`, `contexts.py` は全て read-only で利用
- 既存テスト: 一切変更なし
- `__init__.py`: 一切変更なし

---

## 8. 設計判断の記録

### Q: なぜ `period_variants.py` を変更しないのか？

**A**: Risk 5 の解決策として、`classify_periods` と `detect_fiscal_year` は異なる責任を持つ別モジュールとして設計する。`classify_periods` はコンテキスト選択（BS/PL 構築時の当期/前期判別）に使用され、`detect_fiscal_year` はメタデータ抽出（決算月、変則決算の有無等）に使用される。入力が同じ（DEI）だが出力の目的が異なるため、統合は不要。利用者にとっても「何のために呼ぶか」が明確に分離される。

### Q: `_calc_months` の概算精度は十分か？

**A**: DEI には「期間月数」を直接報告するフィールドがないため、日数からの概算は不可避。30.44 日/月の概算で、典型的な 3ヶ月/6ヶ月/9ヶ月/12ヶ月は正確に判定できる。閏年（366日）でも 12.02 → 12ヶ月と四捨五入されるため誤差は発生しない。13ヶ月以上の変則決算（理論上は可能だが極めて稀）でも概算精度は ±0.5ヶ月以内。

### Q: `is_irregular` が False になるのはどういう場合か？

**A**: 以下のいずれかの場合に `is_irregular = False`:
1. `period_type` が `PeriodType.FY` でない（HY、None、未知の文字列）
2. `period_type` が `PeriodType.FY` で `period_months` が 12
3. `period_months` が `None`（日付情報不足で計算不可）

つまり「通期（FY）と宣言しているのに12ヶ月でない」場合のみ `True` になる。半期報告で6ヶ月なのは正常なので `is_irregular = False`。

### Q: `period_type` が文字列の場合はどう扱うか？

**A**: DEI の `type_of_current_period` は `PeriodType | str | None` 型。未知の値（`PeriodType.FY` でも `PeriodType.HY` でもない文字列）の場合、`is_fy` の判定で `isinstance(period_type, PeriodType)` が `False` を返すため、`is_full_year = False`, `is_irregular = False` となる。未知の値をエラーにはしない（graceful degradation）。

### Q: `fiscal_year_end_date` と `end_date` は同じ値にならないのか？

**A**: 通期（FY）の場合は通常同じ値になる。しかし半期報告（HY）の場合は異なる:
- `end_date` = 半期末日（例: `2024-09-30`）
- `fiscal_year_end_date` = 事業年度末日（例: `2025-03-31`）

この区別があるため、両方を `FiscalYearInfo` に含める。

### Q: この機能の工数は？

**A**: WAVE_6.md の見積もりでは「低」難易度、新規ソース約100〜150行、新規テスト約200〜300行。DEI のフィールドが全て揃っており、純粋な計算ロジックのため調査は不要。実装は即座に着手可能。

---

## 9. 後続機能との接続点

| 利用先 | 利用方法 |
|--------|----------|
| **将来: diff/period** | 期間比較時に `is_irregular` で変則決算を警告 |
| **将来: eda/summary** | 企業サマリーに決算月・期間月数を含める |
| **将来: dataframe/** | DataFrame のメタデータ列に `fiscal_year_end_month` を追加 |
| **利用者のスクリーニング** | `is_irregular` で変則決算企業を除外、`fiscal_year_end_month` で決算月別に集計 |

Lane 6 が提供する `detect_fiscal_year()` は、D5 命名規約の `detect_*` パターンに従い、発見・判定の結果を result dataclass で返す standalone 関数として設計されている。最も軽量な Lane であり、DEI の日付フィールドを構造化するだけの純粋関数。

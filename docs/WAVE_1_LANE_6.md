# Wave 1 / Lane 6 — DEI (Document and Entity Information) 抽出

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 1 / Lane 6 を担当するエージェントです。
担当機能: dei

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
   - `src/edinet/xbrl/dei.py` (新規)
   - `tests/test_xbrl/test_dei.py` (新規)
   - `tests/fixtures/dei/` (新規ディレクトリ)
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
     例: `tests/fixtures/dei/`

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.dei import extract_dei` （OK）
   - 例: `from edinet.xbrl import extract_dei` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_dei.py` に作成
   - 既存のテストファイル（test_contexts.py, test_facts.py, test_statements.py 等）は変更しないこと

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

# LANE 6 — DEI (Document and Entity Information) 抽出

## 0. 位置づけ

Lane 6 は、XBRL インスタンスの `ParsedXBRL.facts` から **DEI（Document and Entity Information）要素を抽出し、型安全な `DEI` dataclass に変換する** レーン。

FEATURES.md の `dei` 機能に対応し、Wave 2 以降の `standards/detect`（会計基準自動判別）や `dimensions/consolidated`（連結/個別判定の前処理）の直接的な入力データとなる重要な基盤レイヤー。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.parser.RawFact` | 入力データ型 | read-only |
| `edinet.exceptions.EdinetParseError` | パースエラー | read-only |
| `edinet.exceptions.EdinetWarning` | 警告カテゴリ | read-only |

他レーンとのファイル衝突なし（新規ファイルのみ作成）。

### QA 参照

| QA | タイトル | 関連度 |
|----|---------|--------|
| F-1 | DEI 要素の一覧 | 直接（全 34 要素の定義） |
| F-1b | DEI 要素の Context | 直接（FilingDateInstant パターン） |
| F-2 | DEI の利用シーン | 直接（会計基準判別等の利用方法） |
| D-3 | 会計基準の判別方法 | 関連（AccountingStandardsDEI の値） |

---

## 1. ゴール

1. `ParsedXBRL.facts` から `jpdei_cor` 名前空間に属する DEI 要素を抽出する関数 `extract_dei()` を実装する
2. 全 27 個の非 Abstract DEI 要素を型安全なフィールドとして持つ `DEI` frozen dataclass を定義する
3. 値の型変換を正確に行う（`str` / `datetime.date` / `bool` / `int`、nil → `None`）
4. `AccountingStandard` / `PeriodType` の列挙型を定義し、事実上の列挙値を型で表現する
5. Wave 2 の `standards/detect` が `dei.accounting_standards` を直接参照できるインターフェースを提供する

### 非ゴール（スコープ外）

- 大量保有報告書の保有者別 DEI（`jplvh_cor` 名前空間）の抽出 → v0.2.0+
- DEI 値のバリデーション（例: `AccountingStandardsDEI` が 4 値 + nil 以外の場合のエラー） → 警告のみ出し、値はそのまま保持
- Context の構造化（`FilingDateInstant` の解析） → Lane 4 (contexts) の責務
- Filing モデルとの統合（`Filing.dei` プロパティ等） → Wave 完了後の統合タスク

---

## 2. データモデル設計

### 2.1 列挙型

```python
import enum

class AccountingStandard(str, enum.Enum):
    """会計基準（DEI で報告される値）。

    F-1.a.md より、AccountingStandardsDEI の取りうる値は以下の 4 種。
    xsi:nil="true" の場合は None として扱い、この Enum には含めない。
    """
    JAPAN_GAAP = "Japan GAAP"
    IFRS = "IFRS"
    US_GAAP = "US GAAP"
    JMIS = "JMIS"


class PeriodType(str, enum.Enum):
    """報告期間の種類（DEI で報告される値）。

    F-1.a.md より、TypeOfCurrentPeriodDEI の取りうる値は以下の 2 種。
    四半期報告書制度の廃止に伴い、四半期に対応する値は存在しない。
    """
    FY = "FY"  # 年度（通期）
    HY = "HY"  # 中間期
```

**設計判断**: `str` を継承する `str, enum.Enum` パターンを採用。これにより `dei.accounting_standards == "Japan GAAP"` のような文字列比較と `dei.accounting_standards == AccountingStandard.JAPAN_GAAP` の列挙型比較の両方が可能。未知の値が来た場合は Enum 化せず `str` のまま保持し、警告を出す。

### 2.2 DEI dataclass

```python
import datetime
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class DEI:
    """XBRL インスタンスから抽出した DEI (Document and Entity Information)。

    全 27 個の非 Abstract DEI 要素を型安全なフィールドとして保持する。
    DEI タクソノミ（jpdei_cor）には提出者が独自の要素を追加することはないため
    （F-1.a.md [F17]）、このクラスの定義は安定している。

    Attributes:
        # --- (A) 提出者情報 ---
        edinet_code: EDINETコード（例: "E00001"）。
        fund_code: ファンドコード。ファンド以外は None。
        security_code: 証券コード（5桁、例: "11110"）。該当なしは None。
        filer_name_ja: 提出者名（日本語表記）。
        filer_name_en: 提出者名（英語表記）。
        fund_name_ja: ファンド名称（日本語表記）。ファンド以外は None。
        fund_name_en: ファンド名称（英語表記）。ファンド以外は None。
        # --- (B) 提出書類情報 ---
        cabinet_office_ordinance: 府令名。
        document_type: 様式名（例: "第三号様式"）。
        accounting_standards: 会計基準（AccountingStandard 列挙型）。
            対象外書類は None。未知の値は文字列のまま格納（型は AccountingStandard | str | None）。
        has_consolidated: 連結決算の有無。対象外書類は None。
        industry_code_consolidated: 別記事業（連結）の業種コード。該当なしは None。
        industry_code_non_consolidated: 別記事業（個別）の業種コード。該当なしは None。
        # --- (C) 当会計期間 ---
        current_fiscal_year_start_date: 当事業年度開始日。
        current_period_end_date: 当会計期間終了日。
        type_of_current_period: 当会計期間の種類（PeriodType 列挙型）。
            未知の値は文字列のまま格納。
        current_fiscal_year_end_date: 当事業年度終了日（決算日）。
        # --- (D) 比較対象会計期間 ---
        previous_fiscal_year_start_date: 前事業年度開始日。
        comparative_period_end_date: 比較対象会計期間終了日。
        previous_fiscal_year_end_date: 前事業年度終了日。
        # --- (E) 次の中間期 ---
        next_fiscal_year_start_date: 次の事業年度開始日。
        end_date_of_next_semi_annual_period: 次の中間期の会計期間終了日。
        # --- (F) 訂正関連 ---
        number_of_submission: 提出回数（当初提出=1、1回目訂正=2、...）。
        amendment_flag: 訂正の有無。
        identification_of_document_subject_to_amendment: 訂正対象書類の書類管理番号。
        report_amendment_flag: 記載事項訂正のフラグ。
        xbrl_amendment_flag: XBRL訂正のフラグ。
    """
    # (A) 提出者情報
    edinet_code: str | None = None
    fund_code: str | None = None
    security_code: str | None = None
    filer_name_ja: str | None = None
    filer_name_en: str | None = None
    fund_name_ja: str | None = None
    fund_name_en: str | None = None
    # (B) 提出書類情報
    cabinet_office_ordinance: str | None = None
    document_type: str | None = None
    accounting_standards: AccountingStandard | str | None = None
    has_consolidated: bool | None = None
    industry_code_consolidated: str | None = None
    industry_code_non_consolidated: str | None = None
    # (C) 当会計期間
    current_fiscal_year_start_date: datetime.date | None = None
    current_period_end_date: datetime.date | None = None
    type_of_current_period: PeriodType | str | None = None
    current_fiscal_year_end_date: datetime.date | None = None
    # (D) 比較対象会計期間
    previous_fiscal_year_start_date: datetime.date | None = None
    comparative_period_end_date: datetime.date | None = None
    previous_fiscal_year_end_date: datetime.date | None = None
    # (E) 次の中間期
    next_fiscal_year_start_date: datetime.date | None = None
    end_date_of_next_semi_annual_period: datetime.date | None = None
    # (F) 訂正関連
    number_of_submission: int | None = None
    amendment_flag: bool | None = None
    identification_of_document_subject_to_amendment: str | None = None
    report_amendment_flag: bool | None = None
    xbrl_amendment_flag: bool | None = None
```

**設計判断**:
- 全フィールドにデフォルト値 `None` を付与。DEI は書類タイプにより設定される要素が異なるため（有報では全要素、大量保有報告書では一部のみ等）、欠落を `None` で自然に表現する
- `accounting_standards` の型を `AccountingStandard | str | None` にする。既知の 4 値は Enum に変換、未知の値は `str` のまま保持して警告を出す（堅牢性優先）
- `type_of_current_period` も同様に `PeriodType | str | None`
- フィールド名は concept 名のキャメルケースをスネークケースに変換し、`DEI` サフィックスを除去（`EDINETCodeDEI` → `edinet_code`）。ただし過度に長い名前は短縮（`IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI` → `industry_code_consolidated`）
- `__repr__` をオーバーライドし、`None` フィールドを省略した簡潔な表示を提供する。REPL/Jupyter での探索的分析の DX 向上のため:

```python
import dataclasses

def __repr__(self) -> str:
    parts = []
    for f in dataclasses.fields(self):
        v = getattr(self, f.name)
        if v is not None:
            parts.append(f"{f.name}={v!r}")
    return f"DEI({', '.join(parts)})"
```

### 2.3 concept 名 ↔ フィールド名のマッピング

DEI タクソノミの concept `local_name` と `DEI` dataclass のフィールド名のマッピングテーブル:

| # | concept local_name | DEI フィールド名 | データ型 | 変換 |
|---|-------------------|-----------------|---------|------|
| 1 | `EDINETCodeDEI` | `edinet_code` | str | そのまま |
| 2 | `FundCodeDEI` | `fund_code` | str | そのまま |
| 3 | `SecurityCodeDEI` | `security_code` | str | そのまま |
| 4 | `FilerNameInJapaneseDEI` | `filer_name_ja` | str | そのまま |
| 5 | `FilerNameInEnglishDEI` | `filer_name_en` | str | そのまま |
| 6 | `FundNameInJapaneseDEI` | `fund_name_ja` | str | そのまま |
| 7 | `FundNameInEnglishDEI` | `fund_name_en` | str | そのまま |
| 8 | `CabinetOfficeOrdinanceDEI` | `cabinet_office_ordinance` | str | そのまま |
| 9 | `DocumentTypeDEI` | `document_type` | str | そのまま |
| 10 | `AccountingStandardsDEI` | `accounting_standards` | AccountingStandard/str | Enum 変換、未知値は str |
| 11 | `WhetherConsolidatedFinancialStatementsArePreparedDEI` | `has_consolidated` | bool | `"true"` → True, `"false"` → False |
| 12 | `IndustryCodeWhen...ConsolidatedDEI` | `industry_code_consolidated` | str | そのまま |
| 13 | `IndustryCodeWhen...NonConsolidatedDEI` | `industry_code_non_consolidated` | str | そのまま |
| 14 | `CurrentFiscalYearStartDateDEI` | `current_fiscal_year_start_date` | date | `YYYY-MM-DD` → `datetime.date` |
| 15 | `CurrentPeriodEndDateDEI` | `current_period_end_date` | date | 同上 |
| 16 | `TypeOfCurrentPeriodDEI` | `type_of_current_period` | PeriodType/str | Enum 変換、未知値は str |
| 17 | `CurrentFiscalYearEndDateDEI` | `current_fiscal_year_end_date` | date | 同上 |
| 18 | `PreviousFiscalYearStartDateDEI` | `previous_fiscal_year_start_date` | date | 同上 |
| 19 | `ComparativePeriodEndDateDEI` | `comparative_period_end_date` | date | 同上 |
| 20 | `PreviousFiscalYearEndDateDEI` | `previous_fiscal_year_end_date` | date | 同上 |
| 21 | `NextFiscalYearStartDateDEI` | `next_fiscal_year_start_date` | date | 同上 |
| 22 | `EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI` | `end_date_of_next_semi_annual_period` | date | 同上 |
| 23 | `NumberOfSubmissionDEI` | `number_of_submission` | int | `str` → `int` |
| 24 | `AmendmentFlagDEI` | `amendment_flag` | bool | `"true"` → True |
| 25 | `IdentificationOfDocumentSubjectToAmendmentDEI` | `identification_of_document_subject_to_amendment` | str | そのまま |
| 26 | `ReportAmendmentFlagDEI` | `report_amendment_flag` | bool | `"true"` → True |
| 27 | `XBRLAmendmentFlagDEI` | `xbrl_amendment_flag` | bool | `"true"` → True |

Abstract 要素（7 個）はデータを持たないためマッピング対象外。合計 27 個の非 Abstract 要素が抽出対象。

---

## 3. 公開 API

### 3.1 `extract_dei()`

```python
def extract_dei(facts: tuple[RawFact, ...]) -> DEI:
    """ParsedXBRL の facts から DEI 要素を抽出する。

    Args:
        facts: ParsedXBRL.facts から得られる RawFact のタプル。

    Returns:
        DEI dataclass。XBRL インスタンスに DEI 要素が存在しない場合は
        全フィールドが None の DEI を返す（エラーにはしない）。

    Note:
        jpdei_cor 名前空間（URI パターン:
        ``http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/*/jpdei_cor``）
        に属する Fact のみを対象とする。

        DEI 要素は全て FilingDateInstant コンテキストに紐づくが（F-1b.a.md）、
        この関数は contextRef によるフィルタリングは行わない。
        複数の同名 DEI Fact が存在する場合は最初に出現したものを使用する。
    """
```

**設計判断**:
- **入力を `facts` (タプル) にする理由**: `ParsedXBRL` 全体を受け取ると依存が広がる。`facts` のみを受け取ることで疎結合を保つ。呼び出し側は `extract_dei(parsed.facts)` とする
- **DEI 要素が皆無でもエラーにしない理由**: 大量保有報告書等、書類タイプによっては `jpdei_cor` の DEI が最小限しかない場合がある。呼び出し側で必要なフィールドの有無を判定する方が柔軟
- **contextRef フィルタリングをしない理由**: F-1b.a.md より全 DEI は `FilingDateInstant` に紐づくことが確認されているが、concept の `local_name` によるフィルタで十分に一意性が得られる。contextRef の検証は上位レイヤー（Wave 2 以降）の責務とし、この関数は単純に保つ

---

## 4. 内部アルゴリズム

### 4.1 名前空間の判定

DEI 要素は `jpdei_cor` 名前空間に属する。名前空間 URI のパターン:

```
http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/{version}/jpdei_cor
```

例: `http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor`

判定は `RawFact.namespace_uri` が上記パターンに合致するかを文字列一致で行う:

```python
_JPDEI_NS_PREFIX = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/"
_JPDEI_NS_SUFFIX = "/jpdei_cor"

def _is_dei_namespace(namespace_uri: str) -> bool:
    """jpdei_cor 名前空間に属するか判定する。"""
    return (
        namespace_uri.startswith(_JPDEI_NS_PREFIX)
        and namespace_uri.endswith(_JPDEI_NS_SUFFIX)
    )
```

### 4.2 値の型変換

concept のデータ型に基づく変換関数群:

```python
from edinet.exceptions import EdinetWarning

def _convert_date(value_raw: str) -> datetime.date:
    """YYYY-MM-DD 形式の文字列を datetime.date に変換する。"""
    return datetime.date.fromisoformat(value_raw)

def _convert_bool(value_raw: str) -> bool:
    """XBRL の boolean 値を Python bool に変換する。

    xs:boolean で許容される値は "true"/"false"/"1"/"0" の 4 つのみ。
    不正な値の場合は EdinetWarning を出し False にフォールバックする。
    """
    v = value_raw.strip().lower()
    if v in ("true", "1"):
        return True
    if v in ("false", "0"):
        return False
    warnings.warn(
        f"不正な boolean 値: {value_raw!r}。'true'/'false'/'1'/'0' を期待。",
        EdinetWarning,
        stacklevel=2,
    )
    return False  # フォールバック

def _convert_int(value_raw: str) -> int:
    """文字列を非負整数に変換する。

    NumberOfSubmissionDEI の XSD 型は nonNegativeIntegerItemType。
    負の値は仕様上存在しないため警告を出す。
    """
    result = int(value_raw.strip())
    if result < 0:
        warnings.warn(
            f"NumberOfSubmissionDEI に負の値: {result}",
            EdinetWarning,
            stacklevel=2,
        )
    return result

def _convert_accounting_standard(value_raw: str) -> AccountingStandard | str:
    """AccountingStandard Enum に変換を試み、未知の値は str のまま返す。"""
    try:
        return AccountingStandard(value_raw.strip())
    except ValueError:
        warnings.warn(
            f"未知の会計基準: {value_raw!r}。"
            f"既知の値: {[e.value for e in AccountingStandard]}",
            EdinetWarning,
            stacklevel=2,
        )
        return value_raw.strip()

def _convert_period_type(value_raw: str) -> PeriodType | str:
    """PeriodType Enum に変換を試み、未知の値は str のまま返す。"""
    try:
        return PeriodType(value_raw.strip())
    except ValueError:
        warnings.warn(
            f"未知の報告期間種別: {value_raw!r}。"
            f"既知の値: {[e.value for e in PeriodType]}",
            EdinetWarning,
            stacklevel=2,
        )
        return value_raw.strip()
```

### 4.3 マッピングテーブル（内部定数）

concept `local_name` → (DEI フィールド名, 変換関数) のマッピングを辞書で定義:

```python
from typing import Callable, Any

# 変換関数の型エイリアス
_Converter = Callable[[str], Any]

_DEI_FIELD_MAP: dict[str, tuple[str, _Converter]] = {
    "EDINETCodeDEI": ("edinet_code", str.strip),
    "FundCodeDEI": ("fund_code", str.strip),
    "SecurityCodeDEI": ("security_code", str.strip),
    "FilerNameInJapaneseDEI": ("filer_name_ja", str.strip),
    "FilerNameInEnglishDEI": ("filer_name_en", str.strip),
    "FundNameInJapaneseDEI": ("fund_name_ja", str.strip),
    "FundNameInEnglishDEI": ("fund_name_en", str.strip),
    "CabinetOfficeOrdinanceDEI": ("cabinet_office_ordinance", str.strip),
    "DocumentTypeDEI": ("document_type", str.strip),
    "AccountingStandardsDEI": ("accounting_standards", _convert_accounting_standard),
    "WhetherConsolidatedFinancialStatementsArePreparedDEI": ("has_consolidated", _convert_bool),
    "IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI": ("industry_code_consolidated", str.strip),
    "IndustryCodeWhenFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI": ("industry_code_non_consolidated", str.strip),
    "CurrentFiscalYearStartDateDEI": ("current_fiscal_year_start_date", _convert_date),
    "CurrentPeriodEndDateDEI": ("current_period_end_date", _convert_date),
    "TypeOfCurrentPeriodDEI": ("type_of_current_period", _convert_period_type),
    "CurrentFiscalYearEndDateDEI": ("current_fiscal_year_end_date", _convert_date),
    "PreviousFiscalYearStartDateDEI": ("previous_fiscal_year_start_date", _convert_date),
    "ComparativePeriodEndDateDEI": ("comparative_period_end_date", _convert_date),
    "PreviousFiscalYearEndDateDEI": ("previous_fiscal_year_end_date", _convert_date),
    "NextFiscalYearStartDateDEI": ("next_fiscal_year_start_date", _convert_date),
    "EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI": ("end_date_of_next_semi_annual_period", _convert_date),
    "NumberOfSubmissionDEI": ("number_of_submission", _convert_int),
    "AmendmentFlagDEI": ("amendment_flag", _convert_bool),
    "IdentificationOfDocumentSubjectToAmendmentDEI": ("identification_of_document_subject_to_amendment", str.strip),
    "ReportAmendmentFlagDEI": ("report_amendment_flag", _convert_bool),
    "XBRLAmendmentFlagDEI": ("xbrl_amendment_flag", _convert_bool),
}
```

### 4.4 抽出アルゴリズム（疑似コード）

```python
def extract_dei(facts: tuple[RawFact, ...]) -> DEI:
    dei_values: dict[str, Any] = {}

    for fact in facts:
        # 1. jpdei_cor 名前空間のみ対象
        if not _is_dei_namespace(fact.namespace_uri):
            continue

        # 2. マッピングテーブルに存在する concept のみ対象
        mapping = _DEI_FIELD_MAP.get(fact.local_name)
        if mapping is None:
            continue

        field_name, converter = mapping

        # 3. 同名 concept が複数ある場合は最初のものを使用
        if field_name in dei_values:
            continue

        # 4. nil の場合は None
        if fact.is_nil or fact.value_raw is None:
            dei_values[field_name] = None
        else:
            # 5. 型変換
            try:
                dei_values[field_name] = converter(fact.value_raw)
            except (ValueError, TypeError) as e:
                warnings.warn(
                    f"DEI 要素 {fact.local_name} の値変換に失敗: "
                    f"{fact.value_raw!r} ({e})",
                    EdinetWarning,
                    stacklevel=2,
                )
                dei_values[field_name] = fact.value_raw  # フォールバック: 生値を保持

        # 6. 全 DEI フィールドが揃ったら早期終了
        if len(dei_values) == len(_DEI_FIELD_MAP):
            break

    return DEI(**dei_values)
```

**ポイント**:
- `facts` を 1 回の線形走査で完了。DEI 要素は 27 個しかないため、全 Fact を走査しても計算量は O(N)（N = 全 Fact 数、典型的に数百〜数千）
- 全 27 フィールドが揃った時点で早期終了（DEI は通常ファイル冒頭近くに出現するため、平均ケースで大幅に高速化）
- nil Fact は `None` に変換（`is_nil=True` または `value_raw=None`）
- 型変換に失敗した場合は `EdinetWarning` で警告を出し、生の `value_raw` をフォールバック値として保持（堅牢性優先）
- 同名 concept の重複は最初の出現を採用（DEI は通常重複しないが安全策）
- 全ての `warnings.warn()` に `EdinetWarning` カテゴリを指定（ライブラリ全体の一貫性）

---

## 5. ファイル構成

### 作成ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/dei.py` | 新規 | `DEI` dataclass, `AccountingStandard` / `PeriodType` Enum, `extract_dei()` |
| `tests/test_xbrl/test_dei.py` | 新規 | 単体テスト |
| `tests/fixtures/dei/` | 新規ディレクトリ | テスト用フィクスチャ |

### `src/edinet/xbrl/dei.py` の構成

```
dei.py
├── AccountingStandard(str, Enum)    # 会計基準の列挙型
├── PeriodType(str, Enum)            # 報告期間種別の列挙型
├── DEI (frozen dataclass)           # DEI データ保持クラス（27 フィールド、__repr__ カスタム）
├── _JPDEI_NS_PREFIX / _JPDEI_NS_SUFFIX  # 名前空間判定用定数
├── _is_dei_namespace()              # 名前空間判定ヘルパー
├── _convert_date()                  # 日付変換ヘルパー
├── _convert_bool()                  # 真偽値変換ヘルパー
├── _convert_int()                   # 整数変換ヘルパー
├── _convert_accounting_standard()   # 会計基準 Enum 変換
├── _convert_period_type()           # 報告期間 Enum 変換
├── _DEI_FIELD_MAP                   # concept → (field, converter) マッピング
└── extract_dei()                    # 公開 API
```

---

## 6. テスト計画

テストは Detroit 派（古典派）のスタイルで、内部実装に依存せず公開 API のみをテストする。

### 6.1 テストフィクスチャ

`tests/fixtures/dei/` に最小限の XBRL フラグメントを配置する。

テストでは実際の XBRL パーサー (`parse_xbrl_facts`) は使わず、`RawFact` を直接構築してテストする。これにより:
- パーサーの変更に影響されない
- テストが高速（XML パース不要）
- DEI 抽出ロジックのみを正確にテストできる

```python
# テストヘルパー: DEI 用の RawFact を簡便に構築する
def _make_dei_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    is_nil: bool = False,
    namespace_uri: str = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor",
) -> RawFact:
    # value_inner_xml はデフォルト値 None を持つため省略可能。
    # DEI 要素はテキストノードのみで子要素を持たないため、常に None で正しい。
    return RawFact(
        concept_qname=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref="FilingDateInstant",
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )
```

### 6.2 テストケース

#### P0（必須）

| # | テスト名 | 概要 |
|---|---------|------|
| T1 | `test_extract_dei_full` | 全 27 フィールドが正しく抽出・型変換されることを検証 |
| T2 | `test_extract_dei_empty_facts` | Fact が空の場合、全フィールド None の DEI が返ることを検証 |
| T3 | `test_extract_dei_no_dei_facts` | jpdei_cor 以外の Fact のみの場合、全フィールド None の DEI が返ることを検証 |
| T4 | `test_accounting_standards_enum` | "Japan GAAP", "IFRS", "US GAAP", "JMIS" の 4 値が正しく Enum に変換されることを検証（parametrize） |
| T5 | `test_accounting_standards_nil` | `xsi:nil=true` の場合に None が返ることを検証 |
| T6 | `test_period_type_enum` | "FY", "HY" が正しく PeriodType に変換されることを検証 |
| T7 | `test_date_conversion` | 日付フィールド（`current_fiscal_year_end_date` 等）が `datetime.date` に変換されることを検証 |
| T8 | `test_bool_conversion` | boolean フィールド（`has_consolidated`, `amendment_flag` 等）が `bool` に変換されることを検証 |
| T9 | `test_int_conversion` | `number_of_submission` が `int` に変換されることを検証 |
| T10 | `test_nil_handling` | `is_nil=True` の Fact が `None` として処理されることを検証 |
| T11 | `test_duplicate_concept_first_wins` | 同名 concept が複数ある場合、最初の出現が使われることを検証 |

#### P1（推奨）

| # | テスト名 | 概要 |
|---|---------|------|
| T12 | `test_unknown_accounting_standard_warns` | 未知の会計基準値（例: "Unknown"）で警告が出ることを検証 |
| T13 | `test_unknown_period_type_warns` | 未知の報告期間種別で警告が出ることを検証 |
| T14 | `test_invalid_date_fallback` | 不正な日付文字列で警告が出て生値が保持されることを検証 |
| T15 | `test_different_jpdei_versions` | 異なるタクソノミバージョン（2013-08-31 以外）の名前空間 URI でも正しく抽出されることを検証 |
| T16 | `test_non_dei_namespace_ignored` | `jppfs_cor` 等の非 DEI 名前空間の Fact が無視されることを検証 |
| T17 | `test_accounting_standard_str_comparison` | `dei.accounting_standards == "Japan GAAP"` が True になることを検証（str Enum の利便性） |
| T18 | `test_dei_frozen` | DEI dataclass が frozen であり、フィールドの変更が `FrozenInstanceError` を raise することを検証 |
| T19 | `test_invalid_bool_warns` | 不正な boolean 値（例: "yes"）で `EdinetWarning` が出て `False` にフォールバックされることを検証 |
| T20 | `test_dei_repr_omits_none` | `DEI.__repr__` が None フィールドを省略した簡潔な表示を返すことを検証 |
| T21 | `test_early_termination` | 全 27 DEI 要素が先頭にある場合、後続の Fact が処理されないことを検証（重複 concept を末尾に配置し、最初の値が使われることで間接的に確認） |

---

## 7. Wave 2 への接続点

Lane 6 (DEI) の出力は Wave 2 の以下のレーンで消費される:

| Wave 2 Lane | 消費するフィールド | 用途 |
|-------------|-------------------|------|
| L2 (standards/detect) | `dei.accounting_standards` | 会計基準の判別（第一手段） |
| L2 (standards/detect) | `dei.has_consolidated` | 連結/個別の判定補助 |
| L2 (standards/detect) | `dei.type_of_current_period` | 通期/半期の判定 |
| Free Rider (dimensions/consolidated) | `dei.has_consolidated` | 連結財務諸表の存在確認 |

Wave 2 では以下のように使用される想定:

```python
from edinet.xbrl.dei import extract_dei, AccountingStandard

dei = extract_dei(parsed.facts)

# standards/detect での使用例
if dei.accounting_standards == AccountingStandard.IFRS:
    # IFRS 用の処理パス
    ...
elif dei.accounting_standards == AccountingStandard.JAPAN_GAAP:
    # J-GAAP 用の処理パス
    ...
```

---

## 8. 実行チェックリスト

### Phase 1: 実装（推定 40 分）

1. `src/edinet/xbrl/dei.py` を新規作成
   - `AccountingStandard` / `PeriodType` Enum 定義
   - `DEI` frozen dataclass 定義（27 フィールド + `__repr__` オーバーライド）
   - `_is_dei_namespace()` ヘルパー
   - 型変換ヘルパー群（`_convert_date`, `_convert_bool`, `_convert_int`, `_convert_accounting_standard`, `_convert_period_type`）
   - `_DEI_FIELD_MAP` マッピング定数
   - `extract_dei()` 公開関数

### Phase 2: テスト（推定 30 分）

2. `tests/fixtures/dei/` ディレクトリ作成（フィクスチャが必要な場合）
3. `tests/test_xbrl/test_dei.py` を新規作成
   - P0 テスト（T1〜T11）を全て実装
   - P1 テスト（T12〜T21）を全て実装

### Phase 3: 検証（推定 10 分）

4. `uv run ruff check src/edinet/xbrl/dei.py tests/test_xbrl/test_dei.py` — Lint チェック
5. `uv run pytest tests/test_xbrl/test_dei.py -v` — DEI テストのみ実行
6. `uv run pytest` — 全テスト実行（既存テストを壊していないことを確認）

### 完了条件

- [ ] `extract_dei()` が全 27 DEI 要素を正しく抽出・型変換する
- [ ] `AccountingStandard` / `PeriodType` Enum が定義されている
- [ ] DEI 要素が存在しない場合でもエラーにならず全フィールド None の DEI が返る
- [ ] nil Fact が None として処理される
- [ ] 未知の列挙値に対して `EdinetWarning` で警告が出つつ文字列として保持される
- [ ] 不正な boolean 値に対して `EdinetWarning` で警告が出て `False` にフォールバックされる
- [ ] `DEI.__repr__` が None フィールドを省略した簡潔な表示を返す
- [ ] 全 27 フィールドが揃った時点で走査が早期終了する
- [ ] P0 テスト全件 PASS
- [ ] P1 テスト全件 PASS
- [ ] 既存テスト全件 PASS
- [ ] ruff Clean

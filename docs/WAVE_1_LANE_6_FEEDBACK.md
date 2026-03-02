# WAVE 1 LANE 6 フィードバック（第1ラウンド）: DEI 抽出

## 総評

計画は全体として**非常に高い品質**で書かれている。以下の点が優れている:

- **QA トレーサビリティ**: F-1.a.md / F-1b.a.md / F-2.a.md / D-3.a.md との対応が明確で、全設計判断の根拠が追跡可能
- **堅牢性設計**: nil → None、未知 Enum 値 → str + 警告、型変換失敗 → 生値フォールバック、と防御的パターンが一貫している
- **スコープの明確な線引き**: 大量保有報告書の保有者別 DEI（`jplvh_cor`）を明示的に除外。Context 検証を上位レイヤーに委譲。適切
- **疎結合な API**: `extract_dei(facts)` が `ParsedXBRL` 全体ではなく `facts` タプルのみを受け取る設計は正しい
- **並列安全性**: 新規ファイルのみ作成で他レーンとの衝突リスクゼロ

以下は「ディファクトスタンダード」品質を目指す上での残存課題を記載する。

---

## HIGH（実装時にバグ・不整合を生むリスクがある）

### H-1. 非 Abstract 要素数の誤記: 「26」ではなく「27」

**現状**: 計画全体で「全 26 個の非 Abstract DEI 要素」「Abstract 要素（8 個）」と記載。

**問題**: F-1.a.md の全 34 要素を数え直すと、Abstract 要素は **7 個**、非 Abstract 要素は **27 個** である。

Abstract 要素（7 個）:
1. `DocumentAndEntityInformationDEIAbstract`
2. `EntityInformationDEIAbstract`
3. `DocumentInformationDEIAbstract`
4. `CurrentPeriodDEIAbstract`
5. `ComparativePeriodDEIAbstract`
6. `QuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEIAbstract`
7. `TypeOfAmendmentDEIAbstract`

7 + 27 = 34（全要素数と整合）。

実際に、計画自身のマッピングテーブル（§2.3）は #1〜#27 の **27 エントリ** を列挙しており、`DEI` dataclass のフィールド数も **27 個** である。つまりマッピングテーブルと dataclass は正しいが、本文中の「26」「8」という数字が誤り。

**対策**: 計画中の「26」を「27」に、「8」を「7」に修正。具体的には §1 ゴール、§2.2 docstring、§2.3 末尾の説明文、§4.3 直前の説明、§4.4 コメント、§8 完了条件。

**影響**: 実装エージェントがマッピングテーブルではなく本文の「26」を信じた場合、1 要素が実装漏れする。

---

### H-2. `warnings.warn` に `EdinetWarning` カテゴリが未指定

**現状**: `_convert_accounting_standard()`, `_convert_period_type()`, 抽出アルゴリズムの型変換エラーで `warnings.warn()` を使用しているが、warning カテゴリ（第2引数）が指定されていない。

**問題**: Python の `warnings.warn(message)` はデフォルトで `UserWarning` カテゴリを使用する。既存コードベースは `EdinetWarning`（`edinet.exceptions` で定義、`UserWarning` のサブクラス）を一貫して使用している。`UserWarning` で出すと、利用者が以下のように DEI 警告を選択的に制御できない:

```python
# ユーザーが期待する使い方
import warnings
from edinet.exceptions import EdinetWarning
warnings.filterwarnings("ignore", category=EdinetWarning)
```

**対策**: 全ての `warnings.warn()` 呼び出しに `EdinetWarning` を追加:

```python
warnings.warn(
    f"未知の会計基準: {value_raw!r}。...",
    EdinetWarning,  # ← 追加
    stacklevel=2,
)
```

あわせて §0 の依存テーブルに `edinet.exceptions.EdinetWarning` を追加（現在は `EdinetParseError` のみ記載）。

Lane 1 フィードバック H-4 でも同一の指摘があり、ライブラリ全体で統一すべきパターン。

---

### H-3. `_convert_bool` が不正な値を黙って `False` にする

**現状（§4.2）**:

```python
def _convert_bool(value_raw: str) -> bool:
    return value_raw.strip().lower() in ("true", "1")
```

**問題**: XBRL の `booleanItemType` で許容される値は `"true"` / `"false"` / `"1"` / `"0"` の 4 つのみ（XML Schema の `xs:boolean` 定義に準拠）。現在の実装では `"maybe"` や `"yes"` のような不正な値が**警告なしに `False`** として扱われる。これは `_convert_accounting_standard` や `_convert_period_type` の「未知の値は警告を出す」という設計方針と矛盾する。

**対策**: 明示的に truthy / falsy の両方をチェックし、どちらでもない場合は警告を出す:

```python
def _convert_bool(value_raw: str) -> bool:
    """XBRL の boolean 値を Python bool に変換する。"""
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
```

**テストへの影響**: P1 テストに `test_invalid_bool_warns`（不正な boolean 値で警告が出ること）を追加すべき。

---

## MEDIUM（API品質・開発者体験の改善）

### M-1. `DEI.__repr__` の可読性

**現状**: `frozen=True, slots=True` の dataclass はデフォルトの `__repr__` を生成する。27 フィールドの DEI を REPL で表示すると非常に長くなる。

```python
>>> dei
DEI(edinet_code='E00001', fund_code=None, security_code='11110', filer_name_ja='A株式会社', filer_name_en='A Corp.', fund_name_ja=None, fund_name_en=None, cabinet_office_ordinance='企業内容等の開示に関する内閣府令', document_type='第三号様式', accounting_standards=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, has_consolidated=True, industry_code_consolidated=None, industry_code_non_consolidated=None, current_fiscal_year_start_date=datetime.date(2025, 4, 1), current_period_end_date=datetime.date(2026, 3, 31), type_of_current_period=<PeriodType.FY: 'FY'>, current_fiscal_year_end_date=datetime.date(2026, 3, 31), previous_fiscal_year_start_date=datetime.date(2024, 4, 1), comparative_period_end_date=datetime.date(2025, 3, 31), previous_fiscal_year_end_date=datetime.date(2025, 3, 31), next_fiscal_year_start_date=None, end_date_of_next_semi_annual_period=None, number_of_submission=1, amendment_flag=False, identification_of_document_subject_to_amendment=None, report_amendment_flag=False, xbrl_amendment_flag=False)
```

**提案**: `__repr__` をオーバーライドし、None フィールドを省略する簡潔な表示を提供:

```python
def __repr__(self) -> str:
    fields = ", ".join(
        f"{k}={v!r}"
        for k, v in self.__dict__.items()  # slots=True でも __dict__ はない
        if v is not None
    )
    return f"DEI({fields})"
```

ただし `slots=True` の場合 `__dict__` がないため、`dataclasses.fields()` を使う:

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

REPL / Jupyter での探索的分析が主要ユースケースであるため、DX への影響は大きい。計画変更としては「実装時に `__repr__` のオーバーライドを検討する」の 1 行追記で十分。

---

### M-2. `NumberOfSubmissionDEI` の非負チェック

**現状**: `_convert_int` は `int(value_raw.strip())` のみ。

**問題**: F-1.a.md より、`NumberOfSubmissionDEI` の XSD 型は `xbrli:nonNegativeIntegerItemType`。負の値は仕様上存在しないはずだが、万が一 `"-1"` のような値が来た場合、黙って `-1` に変換される。

**提案**: 型変換失敗時と同じく、仕様外の値には警告を出す:

```python
def _convert_int(value_raw: str) -> int:
    """文字列を非負整数に変換する。"""
    result = int(value_raw.strip())
    if result < 0:
        warnings.warn(
            f"NumberOfSubmissionDEI に負の値: {result}",
            EdinetWarning,
            stacklevel=2,
        )
    return result
```

あるいは、この関数名を `_convert_non_negative_int` に変更して型の意図を明示するのも良い。

**影響度**: 低（実際に負の値が来ることはまずない）。ただし防御的プログラミングの一貫性として。

---

### M-3. テスト用ヘルパー `_make_dei_fact` と `RawFact.value_inner_xml` の互換性

**現状（§6.1）**: テストヘルパー `_make_dei_fact` は `RawFact` を直接構築するが、`value_inner_xml` 引数を渡していない。

**問題**: `RawFact` の `value_inner_xml` フィールドはデフォルト値（`None`）を持つため、省略しても動作する。しかし将来的に `RawFact` にデフォルトなしの新フィールドが追加された場合、全テストが壊れる。

**提案**: 計画変更は不要だが、テストヘルパーに以下のコメントを追記すると実装エージェントの混乱を防げる:

```python
# value_inner_xml はデフォルト値 None を持つため省略可能。
# DEI 要素はテキストノードのみで子要素を持たないため、常に None で正しい。
```

---

### M-4. 早期終了の最適化余地

**現状（§4.4）**: 全 `facts` を線形走査して DEI 要素を収集する。

**問題**: DEI 要素は最大 27 個しかないため、全 27 個が揃った時点で走査を打ち切れる。典型的な有報の Fact 数は数千であり、DEI は通常ファイル冒頭近くに出現するため、早期終了の効果が見込める。

**提案**: 疑似コードに以下を追加:

```python
# 全 DEI フィールドが揃ったら早期終了
if len(dei_values) == len(_DEI_FIELD_MAP):
    break
```

計算量は最悪でも O(N) のままだが、平均ケースで大幅に高速化される。パフォーマンスが問題でなければ計画変更不要（実装時の判断に委ねる）。

---

## LOW（実装ヒント、計画変更不要）

### L-1. `DEI` に便利プロパティの将来的追加を考慮

計画変更不要だが、Wave 2 の `standards/detect` での利用パターンを考えると、以下のようなプロパティがあると便利:

```python
@property
def is_amendment(self) -> bool:
    """訂正報告書かどうか。"""
    return self.amendment_flag is True

@property
def fiscal_year_months(self) -> int | None:
    """事業年度の月数（変則決算判定用）。"""
    if self.current_fiscal_year_start_date and self.current_fiscal_year_end_date:
        # 月数計算
        ...
    return None
```

ただし YAGNI 原則に基づき、v0.1.0 では不要。Wave 2 以降で必要になった時点で追加すればよい。frozen dataclass にプロパティを追加しても後方互換性は保たれる。

---

### L-2. `_DEI_FIELD_MAP` を `dict` ではなく `Mapping` 型アノテーションに

計画変更不要だが、内部定数を `dict` ではなく `Mapping` として型アノテーションすると、意図しない変更を防げる:

```python
from collections.abc import Mapping

_DEI_FIELD_MAP: Mapping[str, tuple[str, _Converter]] = { ... }
```

あるいは定数であることを示すために `Final` を使う:

```python
from typing import Final

_DEI_FIELD_MAP: Final[dict[str, tuple[str, _Converter]]] = { ... }
```

---

## 今回のフィードバック優先度まとめ

| ID | 優先度 | 概要 | 影響 |
|----|--------|------|------|
| H-1 | **HIGH** | 要素数「26」→「27」の修正 | 実装漏れリスク。マッピングテーブル自体は正しいが本文が矛盾 |
| H-2 | **HIGH** | `EdinetWarning` カテゴリの明示 | 利用者の `filterwarnings` 制御を保証。ライブラリ全体の一貫性 |
| H-3 | **HIGH** | `_convert_bool` の不正値検出 | 他の変換関数との防御的プログラミングの一貫性 |
| M-1 | MEDIUM | `DEI.__repr__` の簡潔化 | REPL/Jupyter での DX 向上 |
| M-2 | MEDIUM | `_convert_int` の非負チェック | XSD 型との整合。防御的プログラミング |
| M-3 | MEDIUM | テストヘルパーの `value_inner_xml` コメント | 実装エージェントの混乱防止 |
| M-4 | MEDIUM | 早期終了の最適化 | パフォーマンス向上（実装時判断可） |
| L-1 | LOW | 便利プロパティの将来的追加考慮 | 計画変更不要 |
| L-2 | LOW | `_DEI_FIELD_MAP` の型アノテーション強化 | 計画変更不要 |

---

## 総合判定

**計画は HIGH 項目（H-1, H-2, H-3）を反映すれば実装可能な品質に達している。**

H-1 はテキスト修正のみ、H-2 は `EdinetWarning` の追記、H-3 は `_convert_bool` の小修正。いずれも計画の構造を変更せず、数行の追記で対応可能。

MEDIUM 項目のうち M-1（`__repr__`）は DEI がライブラリの主要な公開データ型のひとつであることを考えると、実装時に対応する価値がある。M-4（早期終了）は実装エージェントの判断に委ねてよい。

計画の最大の強みは、マッピングテーブルと変換関数が QA ドキュメント（F-1.a.md）に1対1で対応しており、実装エージェントが迷いなくコードに落とせる点にある。DEI タクソノミは提出者による拡張がない（F-17）ため、この 27 要素のマッピングは長期的に安定する。

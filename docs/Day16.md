# Day 16 — `.to_dataframe()` + Rich 表示 + `__str__`

## 0. 位置づけ

Day 16 は、Day 15 で完成した `FinancialStatement` に **表示レイヤー** を実装する日。
PLAN.LIVING.md の Day 16:

> **Day 16 (1.5h) — .to_dataframe() + Rich 表示**
> - `FinancialStatement.to_dataframe()`: pandas 変換
> - `display/rich.py`: コンソール表示
> - [注意] pandas, rich は遅延 import（import edinet 時点では読み込まない）
> - [注意] pandas なしでも `import edinet` が成功することをテスト

Day 15 完了時点の状態:
- `parse_xbrl_facts()` → `ParsedXBRL`（RawFact + RawContext + RawUnit）
- `structure_contexts()` → `dict[str, StructuredContext]`
- `TaxonomyResolver` → concept → `LabelInfo` のラベル解決
- `build_line_items()` → `tuple[LineItem, ...]`
- `build_statements()` → `Statements`（`income_statement()`, `balance_sheet()`, `cash_flow_statement()`）
- `FinancialStatement` frozen dataclass: `__getitem__`, `get`, `__contains__`, `__len__`, `__iter__`, `__repr__` 実装済み
- `display/rich.py` は docstring 1行のみ（空スタブ）
- pyproject.toml: `analysis = ["pandas>=2.0"]`, `display = ["rich>=13.0"]` 宣言済み
- pytest 434/434 PASS、ruff Clean

Day 16 完了時のマイルストーン:

```python
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.facts import build_line_items
from edinet.financial.statements import build_statements

parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)
resolver = TaxonomyResolver("/path/to/ALL_20251101")
resolver.load_filer_labels(filer_lab_bytes, filer_lab_en_bytes, xsd_bytes=filer_xsd_bytes)

items = build_line_items(parsed.facts, ctx_map, resolver)
stmts = build_statements(items)
pl = stmts.income_statement()

# 1. プレーンテキスト表示（Rich なし）
print(pl)
# 損益計算書 (Income Statement)  [連結] 2024-04-01〜2025-03-31
#
#   売上高                              45,095,325,000,000
#   売上原価                            38,000,000,000,000
#   ...
#   (16 科目)

# 2. Rich テーブル表示
from rich.console import Console
Console().print(pl)  # 色付き・整列されたテーブル

# 3. Rich Table オブジェクトの取得（カスタマイズ用）
from edinet.display.rich import render_statement
table = render_statement(pl)

# 4. pandas DataFrame 変換
df = pl.to_dataframe()
print(df)
#        label_ja        label_en               value unit      concept
# 0        売上高       Net sales  45095325000000  JPY      NetSales
# 1      売上原価  Cost of sales  38000000000000  JPY   CostOfSales
# ...
```

---

## 1. 現在実装の確認結果

| ファイル | 現状 | Day 16 で必要な変更 |
|---|---|---|
| `src/edinet/models/financial.py` | `FinancialStatement` 168行。`__repr__` あり、`__str__` なし、`to_dataframe()` なし | `__str__()`, `to_dataframe()`, `__rich_console__()` を追加 |
| `src/edinet/display/rich.py` | docstring 1行のみ（`"""Rich 表示向けの描画ヘルパー。"""`） | `render_statement()` を新規実装 |
| `src/edinet/display/__init__.py` | docstring 1行のみ | `render_statement` をエクスポート追加 |
| `tests/test_display/` | ディレクトリ未作成 | 新規作成 |
| `stubs/edinet/models/financial.pyi` | 124行。`__str__` なし、`to_dataframe()` なし | stubgen で再生成 |
| `stubs/edinet/display/rich.pyi` | docstring 1行のみ | stubgen で再生成 |
| `pyproject.toml` | `analysis = ["pandas>=2.0"]`, `display = ["rich>=13.0"]` 宣言済み | 変更なし |

補足:
- `FinancialStatement` は frozen dataclass（`kw_only=True`, `slots=True`）。メソッド追加は frozen 制約と矛盾しない（フィールドを変更しないため）
- `FinancialStatement.items` は `tuple[LineItem, ...]`。各 `LineItem` は `label_ja: LabelInfo`, `label_en: LabelInfo`, `value: Decimal | str | None`, `unit_ref: str | None`, `local_name: str` 等を持つ
- 既存の `__repr__` は `FinancialStatement(type=income_statement, period=..., items=16, consolidated=True)` 形式
- Rich 関連のコードはプロジェクト全体でゼロ（`__rich_console__` も `Console` も未使用）
- テスト用ヘルパー `_make_pl_item()`, `_make_bs_item()`, `_make_label()` は `tests/test_xbrl/test_statements.py` にある

---

## 2. ゴール

1. `FinancialStatement.__str__()` — Rich なしでも `print(pl)` で読みやすいテーブルを出力する
2. `FinancialStatement.to_dataframe()` — pandas DataFrame に変換する（遅延 import）
3. `display/rich.py` に `render_statement()` — Rich Table を返す公開 API
4. `FinancialStatement.__rich_console__()` — `Console().print(pl)` で Rich テーブルが表示される
5. Rich / pandas なしでも `import edinet` が成功することをテストで保証する

**オプション依存の遅延 import が重要な理由**: 日本の企業環境では pip install が制限されているケースが多い。コアモジュール（`import edinet`）は純 Python + lxml のみで動作し、pandas / Rich は利用者が必要な時にのみインストールする設計とする。これは edgartools にはない EDINET 固有の設計判断であり、日本市場への最適化として重要。

---

## 3. スコープ / 非スコープ

### 3.1 Day 16 のスコープ

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| D16-1 | プレーンテキスト表示 | `__str__()` で科目名・金額のテーブルを出力 | PLAN.LIVING.md Day 16 |
| D16-2 | DataFrame 変換 | `to_dataframe()` で pandas DataFrame に変換 | PLAN.LIVING.md Day 16 |
| D16-3 | Rich テーブル描画 | `render_statement()` + `__rich_console__()` | PLAN.LIVING.md Day 16 |
| D16-4 | 遅延 import 保証 | pandas / rich がなくても `import edinet` が動く | PLAN.LIVING.md 注意事項 |

### 3.2 Day 16 でやらないこと

| # | カテゴリ | 内容 | やらない理由 |
|---|---------|------|-------------|
| D16N-1 | `_repr_html_()` | Jupyter でのインラインテーブル表示 | FEATURES.md `display/html` → v0.2.0 |
| D16N-2 | 複数期間並列表示 | 当期 vs 前期の並列テーブル | CODESCOPE.md SN-6 → v0.2.0 |
| D16N-3 | `decimals` スケーリング | 百万円・千円表示 | 値は XBRL 原値のまま表示。スケーリングは利用者の責務 |
| D16N-4 | `Statements` レベルの表示 | PL + BS + CF を一括表示 | 個別 statement 単位で十分。`for s in [pl, bs, cf]: print(s)` で対応可能 |
| D16N-5 | Filing.xbrl() の E2E 統合 | ZIP → パース → Statement → 表示 | → Day 17 |
| D16N-6 | 階層インデント表示 | 小計・内訳の階層構造 | Presentation Linkbase の木構造がない（SN-3）。v0.2.0 で `pres_tree` 実装後に対応 |
| D16N-7 | 負値の日本語表記 | △ / () 表記によるマイナス値の表示 | v0.2.0 のフォーマットオプションとして検討。v0.1.0 では Python 標準の `-` 表記 |
| D16N-8 | Rich concept カラム幅制限 | 長い concept 名の `max_width` / `overflow="ellipsis"` | v0.1.0 は J-GAAP のみで concept 名は短い。IFRS 対応時（v0.2.0）に検討 |
| D16N-9 | Rich テーブルの unit カラム | 金額と株数が混在する場合に必要 | v0.1.0 は PL/BS/CF とも金額のみ。EPS 対応時に検討 |
| D16N-10 | `to_dict()` / `to_records()` | pandas 不要で辞書リストを返す。LLM パイプライン向け | 5 行・依存ゼロで実装可能だが Day 16 の計画は十分詳細。Day 17 以降で検討 |
| D16N-11 | `__str__` の値幅の動的計算 | 固定 20 カラム幅を科目値の最大幅に基づいて動的計算 | 百兆円超で溢れる理論上のリスクがあるが、実務上の J-GAAP 企業では問題にならない。動的化は 3 行で済むため v0.2.0 で対応可能 |
| D16N-12 | `Statements.__str__()` | PL + BS + CF を一括 `print(stmts)` | `Statements` は NamedTuple で `__str__` 未定義。5 行で追加可能だが Day 16 スコープ外。Day 17 以降で検討 |
| D16N-13 | `_display_width()` の wcwidth 移行 | Ambiguous カテゴリ（△ 等）の端末依存幅を正確に計算 | wcwidth ライブラリは依存を増やす。v0.2.0 で検討 |

### 3.3 v0.2.0 拡張性の評価

実装後レビューで v0.2.0 機能の拡張容易性が評価された。記録として以下に残す:

| v0.2.0 機能 | 拡張の容易さ | コメント |
|---|---|---|
| `_repr_html_()` (DN-1) | 容易 | `display/html.py` を追加、`FinancialStatement` に 2 行のメソッド追加 |
| 複数期間並列表示 (DN-2) | 中程度 | 新関数 `render_comparison()` として独立実装可能。既存 API に変更なし |
| 階層インデント (DN-4) | 中程度 | `LineItem` に `depth: int` を追加 + `__str__` のインデント計算。`pres_tree` 依存 |
| IFRS concept の namespace 区別 | 容易 | `_DATAFRAME_COLUMNS` に `"namespace"` 追加。破壊的変更なし |
| Rich の unit カラム (D16N-9) | 容易 | `table.add_column` 1 行追加 |

`display → models` の一方向依存と additive な設計により、全機能が既存 API を壊さずに追加可能。

---

## 4. QA 反映方針（Day 16 に直結するもの）

Day 16 は表示レイヤーであり、QA の直接的な影響は少ない。以下のみ関連:

| QA | Day 16 への反映 |
|---|---|
| E-7 | 主要勘定科目の concept 名辞書。`__str__()` で表示される科目は Day 15 の JSON 定義 + 非標準科目であり、Day 16 はその並びをそのまま出力する |
| H-9b | TaxonomyResolver のラベルフォールバック。`__str__()` が表示する `item.label_ja.text` は常に非 None（T-7 保証）。表示層は「ラベルがない」ケースを考慮しなくてよい |

---

## 5. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/models/financial.py` | 追記 | `__str__()`, `to_dataframe()`, `__rich_console__()`, `format_period()`, `STATEMENT_TYPE_LABELS` |
| `src/edinet/display/rich.py` | 新規実装 | `render_statement()` |
| `src/edinet/display/__init__.py` | 追記 | `render_statement` エクスポート（遅延 import） |
| `tests/test_display/__init__.py` | 新規作成 | 空ファイル（パッケージ化） |
| `tests/test_display/test_rich.py` | 新規作成 | Rich 描画テスト |
| `tests/test_models/test_financial_display.py` | 新規作成 | `to_dataframe()`, `__str__()` テスト |
| `stubs/edinet/models/financial.pyi` | 再生成 | stubgen で自動生成 |
| `stubs/edinet/display/rich.pyi` | 再生成 | stubgen で自動生成 |

---

## 6. `FinancialStatement.__str__()` の設計

### 6.1 出力フォーマット

```
損益計算書 (Income Statement)  [連結] 2024-04-01〜2025-03-31

  売上高                              45,095,325,000,000
  売上原価                            38,000,000,000,000
  売上総利益                           7,095,325,000,000
  販売費及び一般管理費                    2,800,000,000,000
  営業利益又は営業損失（△）              4,295,325,000,000
  ...

  (16 科目)
```

空の statement の場合:

```
損益計算書 (Income Statement)  [連結] (期間なし)

  (科目なし)
```

### 6.2 実装

```python
# models/financial.py に追加

import unicodedata
from typing import Final

STATEMENT_TYPE_LABELS: Final[dict[StatementType, str]] = {
    StatementType.INCOME_STATEMENT: "損益計算書 (Income Statement)",
    StatementType.BALANCE_SHEET: "貸借対照表 (Balance Sheet)",
    StatementType.CASH_FLOW_STATEMENT: "キャッシュ・フロー計算書 (Cash Flow Statement)",
}


def _display_width(s: str) -> int:
    """文字列の端末表示幅を返す。CJK 全角文字は 2 カラム、それ以外は 1 カラム。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def __str__(self) -> str:
    """プレーンテキスト表示。

    Rich なしでも ``print(pl)`` で読みやすいテーブルを出力する。
    科目名（日本語ラベル）と金額をカンマ区切り・右寄せで表示する。
    CJK 全角文字の表示幅を考慮して列を揃える。

    Note:
        value は ``build_statements()`` 経由で数値 Fact のみ含まれる前提。
        ``Decimal('Infinity')`` / ``Decimal('NaN')`` は来ない想定。
    """
    header = STATEMENT_TYPE_LABELS.get(
        self.statement_type, self.statement_type.value
    )
    scope = "連結" if self.consolidated else "個別"
    period_str = format_period(self.period) if self.period else "(期間なし)"

    lines: list[str] = [f"{header}  [{scope}] {period_str}", ""]

    if not self.items:
        lines.append("  (科目なし)")
        return "\n".join(lines)

    # ラベル幅を動的計算（最大 40 カラム幅でクリップ）
    # default=0: 早期リターンで到達しないが defensive coding として付与
    max_width = min(
        max((_display_width(item.label_ja.text) for item in self.items), default=0), 40
    )

    for item in self.items:
        label = item.label_ja.text
        label_width = _display_width(label)
        padding = max_width - label_width
        if isinstance(item.value, Decimal):
            # Note: 値幅は固定 20 カラム。混合精度の科目が入る場合は動的幅計算を検討
            value_str = f"{item.value:>20,}"
        elif item.value is None:
            value_str = f"{'—':>20}"
        else:
            value_str = f"{str(item.value):>20}"
        lines.append(f"  {label}{' ' * padding}  {value_str}")

    lines.append(f"\n  ({len(self.items)} 科目)")
    return "\n".join(lines)
```

### 6.3 `format_period()` ヘルパー

```python
def format_period(period: Period) -> str:
    """Period を表示用文字列に変換する。

    InstantPeriod → "2025-03-31"
    DurationPeriod → "2024-04-01〜2025-03-31"
    """
    from edinet.xbrl.contexts import DurationPeriod, InstantPeriod

    if isinstance(period, InstantPeriod):
        return str(period.instant)
    if isinstance(period, DurationPeriod):
        return f"{period.start_date}〜{period.end_date}"
    return str(period)
```

`format_period()` は `models/financial.py` のモジュールレベル関数として定義する。`__str__` と `display/rich.py` の `_build_title()` の両方から使う。`display/rich.py` は `from edinet.models.financial import format_period` で import する。依存方向は `display → models` であり、既に `FinancialStatement` を引数に取る時点で確立済みのため、新たな依存は発生しない。

### 6.4 設計判断

1. **日本語ラベルをメインにする理由**: EDINET は日本の開示システムであり、利用者の大半が日本語でアクセスする。英語ラベルは `to_dataframe()` の `label_en` カラムで取得可能
2. **CJK 幅計算**: `unicodedata.east_asian_width` を用いた `_display_width()` ヘルパーで全角文字の表示幅（2カラム）を考慮する。EDINET の科目名はほぼ全角であり、`len()` ベースでは金額列が大きくズレるため。3 行のヘルパーで十分実用的なアラインメントが得られる
3. **`decimals` によるスケーリングをしない理由**: 同一 FinancialStatement 内で `decimals` が異なる科目が混在しうる（例: 売上高は `-6` で百万円単位、EPS は `2` で小数2桁）。一律の「百万円表示」は誤解を招くため、XBRL 原値をそのまま表示する。スケーリングは v0.2.0 で検討する
4. **空 statement の表示**: `items=()` の場合は `"(科目なし)"` を表示。空 FinancialStatement は正常な状態（該当する Fact がない場合に返る。CODESCOPE.md §5 SN-1）
5. **`STATEMENT_TYPE_LABELS` / `format_period()` のアンダースコアなし命名**: `display/rich.py` からクロスモジュールで import するため、`_` prefix（モジュール内部専用の慣習）を付けない。`__all__` には含めず、公開 API ではないが internal cross-module use を許容する命名とする。`_display_width()` は `financial.py` 内のみで使うため `_` を維持する
6. **`_display_width()` の Ambiguous カテゴリ**: `east_asian_width(c) in "WF"` は W (Wide) と F (Fullwidth) のみチェックする。"A" (Ambiguous) カテゴリの文字（例: ○, ×, △）は端末によって 1 幅か 2 幅か異なる。EDINET の科目名で「△」が使われるケース（「営業利益又は営業損失（△は営業損失）」）があるが、v0.1.0 ではアラインメントの軽微なズレとして許容する。EDINET で頻出するため v0.2.0 で wcwidth ライブラリへの移行を検討する（D16N-13）
7. **ヘッダーの `[連結]` 前後のダブルスペース**: `"{header}  [{scope}] {period_str}"` のスペース 2 つは意図的なフォーマット。型ラベル・連結/個別・期間の 3 要素を視覚的に区切るため。Rich 側 `_build_title()` と同一フォーマット文字列で一貫性を保つ

---

## 7. `FinancialStatement.to_dataframe()` の設計

### 7.1 実装

```python
# models/financial.py に追加
# TYPE_CHECKING ガード（既存の TYPE_CHECKING ブロックに追記）:
#   if TYPE_CHECKING:
#       import pandas as pd

_DATAFRAME_COLUMNS: Final[list[str]] = ["label_ja", "label_en", "value", "unit", "concept"]


def to_dataframe(self) -> "pd.DataFrame":
    """pandas DataFrame に変換する。

    各科目を1行とし、以下のカラムを持つ DataFrame を返す:
    - ``label_ja``: 日本語ラベル（``str``）
    - ``label_en``: 英語ラベル（``str``）
    - ``value``: 値（``Decimal | str | None``）
    - ``unit``: 単位（``str | None``）
    - ``concept``: concept のローカル名（``str``）

    ``value`` 列は ``Decimal`` のまま保持される（``object`` 型）。
    集計が必要な場合は ``df["value"].astype(float)`` で変換すること。
    日本企業の金額は通常 ``int`` で表現可能なため、
    ``df["value"].astype(int)`` も安全に使える。

    返却される DataFrame の ``attrs`` に statement レベルのメタデータ
    （``statement_type``, ``consolidated``, ``period``, ``entity_id``）を付与する。
    ``attrs`` は ``pd.concat()`` や ``to_csv()`` / ``to_parquet()`` では保持されない。

    Returns:
        科目名・金額等を含む DataFrame。

    Raises:
        ImportError: pandas がインストールされていない場合。
            ``pip install edinet[analysis]`` でインストールできる。

    Examples:
        >>> df = pl.to_dataframe()
        >>> df[df["value"] > 0]  # 正の値のみ抽出
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for to_dataframe(). "
            "Install it with: pip install edinet[analysis]"
        ) from None

    rows: list[dict] = []
    for item in self.items:
        rows.append({
            "label_ja": item.label_ja.text,
            "label_en": item.label_en.text,
            "value": item.value,
            "unit": item.unit_ref,
            "concept": item.local_name,
        })

    if not rows:
        df = pd.DataFrame(columns=_DATAFRAME_COLUMNS)
    else:
        df = pd.DataFrame(rows)

    df.attrs["statement_type"] = self.statement_type.value
    df.attrs["consolidated"] = self.consolidated
    df.attrs["period"] = format_period(self.period) if self.period else None
    df.attrs["entity_id"] = self.entity_id
    return df
```

### 7.2 設計判断

1. **カラム選定（5列）**: `label_ja`, `label_en`, `value`, `unit`, `concept`。利用者が最も頻繁に必要とする情報に絞る。`decimals`, `context_id`, `dimensions` 等のメタデータは含めない。メタデータが必要な利用者は `[{"decimals": item.decimals, ...} for item in pl]` で独自に構築できる
2. **PLAN.LIVING.md のサンプルとの差異**: PLAN.LIVING.md は `{"科目": item.label_ja, "金額": item.value, "単位": item.unit}` としているが、Day 16 ではスネークケース英語カラム名を使う。理由: (a) pandas の慣習はスネークケース英語、(b) `df.label_ja` のようなドットアクセスが可能、(c) 日本語カラム名は `df["科目"]` と毎回括弧が必要で不便
3. **`value` 列の型**: `Decimal | str | None` のまま DataFrame に入れる。pandas は `Decimal` を `object` 型として保持する。`float` への変換は精度損失を伴うため、利用者が明示的に `.astype(float)` で変換する方が安全。v0.1.0 の FinancialStatement には数値 Fact のみ含まれる（`_build_single_statement()` で `isinstance(item.value, Decimal)` フィルタ済み）が、インターフェース上は `Decimal | str | None` を型として保持する
4. **遅延 import**: `import pandas` は `to_dataframe()` 呼び出し時にのみ実行。`import edinet` 時点では pandas を読み込まない。`from None` で元の ImportError traceback を隠す（利用者にとってノイズ）
5. **空 statement**: `items=()` の場合は空の DataFrame（0行、5カラム）を返す。`_DATAFRAME_COLUMNS` 定数でカラム名を一元管理し、空リスト時も非空時も同じカラム名が保証される
6. **frozen dataclass との整合**: `to_dataframe()` はフィールドを変更しない純粋な変換メソッドであり frozen 制約と矛盾しない
7. **戻り値型アノテーション**: `-> "pd.DataFrame"` を文字列リテラルで付与する。`TYPE_CHECKING` ガード下で `import pandas as pd` し、runtime では pandas を import しない。既存の `models/financial.py` の TYPE_CHECKING パターンと一貫する
8. **`concept` カラムが `local_name` のみの理由**: 提出者別拡張科目と標準科目で `local_name` が衝突する可能性は理論上あるが、v0.1.0 では J-GAAP 一般事業会社のみのため実質リスクゼロ。IFRS 対応時（v0.2.0）に `namespace` カラムの追加を検討する。末尾へのカラム追加であれば `df[["label_ja", "value"]]` 等の既存コードは壊れない
9. **`df.attrs` によるメタデータ付与**: `statement_type`, `consolidated`, `period`, `entity_id` を `DataFrame.attrs` に格納する。複数 Filing の DataFrame を `pd.concat()` した後に「この DataFrame はどの statement から来たか」を確認する手段。`attrs` は `concat` / `to_csv` / `to_parquet` で消えるが、これは pandas の仕様として許容する。additive change であり破壊的変更にならない
10. **docstring Example の `df["value"] > 0`**: `value` 列は `Decimal` 型のため Python の `>` 演算子は `Decimal` との比較になる。pandas 2.0+ では `Decimal` の比較演算が正しく動作するため、`astype(float)` を経由しなくても安全。`astype(float)` を Example に使う代替案は正確だが冗長であり、pandas 2.0+ を `pyproject.toml` で要求しているため現状の Example を維持する

---

## 8. `display/rich.py` の設計

### 8.1 モジュール構造

```python
"""Rich 表示向けの描画ヘルパー。

``render_statement()`` で ``FinancialStatement`` を Rich Table に変換する。
``FinancialStatement.__rich_console__()`` から内部的に呼ばれる。

利用者が Rich Table をカスタマイズしたい場合は
``render_statement()`` で Table オブジェクトを取得し、
Rich の API で加工してから ``console.print(table)`` する。

Examples:
    >>> from rich.console import Console
    >>> from edinet.display.rich import render_statement
    >>> table = render_statement(pl)
    >>> Console().print(table)  # そのまま表示
    >>>
    >>> table.add_column("備考")  # カラム追加等のカスタマイズ
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.table import Table

    from edinet.models.financial import FinancialStatement

__all__ = ["render_statement"]
```

### 8.2 `render_statement()`

```python
def render_statement(statement: FinancialStatement) -> Table:
    """FinancialStatement を Rich Table に変換する。

    Args:
        statement: 表示対象の財務諸表。

    Returns:
        Rich Table オブジェクト。``console.print(table)`` で表示する。

    Raises:
        ImportError: rich がインストールされていない場合。
            ``pip install edinet[display]`` でインストールできる。
    """
    try:
        from rich.table import Table
    except ImportError:
        raise ImportError(
            "rich is required for render_statement(). "
            "Install it with: pip install edinet[display]"
        ) from None

    title = _build_title(statement)
    table = Table(title=title, title_style="bold", show_lines=False)

    table.add_column("科目", style="cyan", min_width=20)
    table.add_column("金額", justify="right", style="green", min_width=20)
    table.add_column("concept", style="dim", no_wrap=True)

    for item in statement.items:
        label = item.label_ja.text
        if isinstance(item.value, Decimal):
            value_str = f"{item.value:,}"
        elif item.value is None:
            value_str = "—"
        else:
            value_str = str(item.value)
        table.add_row(label, value_str, item.local_name)

    return table
```

### 8.3 `_build_title()`

```python
def _build_title(statement: FinancialStatement) -> str:
    """テーブルタイトルを組み立てる。

    Note:
        Rich の Table title はマークアップを解釈するため、
        ``[連結]`` が ``[style]text[/style]`` 構文と衝突する。
        ``rich.markup.escape()`` でエスケープする。
    """
    from rich.markup import escape

    from edinet.models.financial import STATEMENT_TYPE_LABELS, format_period

    type_label = STATEMENT_TYPE_LABELS.get(
        statement.statement_type,
        statement.statement_type.value,
    )
    scope = "連結" if statement.consolidated else "個別"
    period_str = format_period(statement.period) if statement.period else ""

    return escape(f"{type_label}  [{scope}] {period_str}")
```

### 8.4 `display/__init__.py` の更新

```python
"""表示・整形ユーティリティを提供するサブパッケージ。"""


def __getattr__(name: str):
    """遅延 import。Rich がインストールされていなくても import edinet.display は成功する。"""
    if name == "render_statement":
        from edinet.display.rich import render_statement
        return render_statement
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """IDE 補完のために公開名を列挙する。"""
    return __all__


__all__ = ["render_statement"]
```

### 8.5 設計判断

1. **`render_statement()` を公開 API にする理由**: `console.print(pl)` だけでなく、`table = render_statement(pl)` で Table オブジェクトを取得しカスタマイズしたい利用者向け。edgartools も statement オブジェクトから直接 Rich Table を取得できる
2. **`display/rich.py` に描画ロジックを集約する理由**: `models/financial.py` に Rich の import を持ち込まない。`__rich_console__` は 2 行のブリッジのみ。Rich がインストールされていない環境でも `models/financial.py` の import は成功する
3. **concept カラムを `dim` スタイルで表示する理由**: 利用者が「この科目は何の concept か」を確認したいケース（デバッグ・API 連携・CSV 出力時のキー確認）が多い。`dim` スタイルで視覚的ノイズを最小限にしつつ情報を提供する
4. **`show_lines=False` の理由**: 財務諸表は罫線なしの方が見慣れた形式に近い。Excel や有報の表示形式を踏襲
5. **Rich の遅延 import**: `from rich.table import Table` は `render_statement()` 呼び出し時に実行。Rich がない環境では `ImportError` を投げる（`to_dataframe()` と同様のユーザーフレンドリーメッセージ付き）
6. **`_repr_html_` を実装しない理由**: FEATURES.md の `display/html` は `[TODO]` であり v0.2.0 のスコープ。Day 16 はターミナル表示 + DataFrame に集中する
7. **間接層 `render_for_console()` を設けない理由**: `__rich_console__` から直接 `render_statement()` を呼んで `yield` する方がシンプル。`console` / `options` 引数を使わない間接関数は不要な認知負荷とテスト対象を増やすだけ
8. **`display/__init__.py` に `__dir__()` を定義する理由**: `__getattr__` による遅延 import だけでは IDE の補完が効かない。`__dir__` を定義することで Python 3.12+ の ModuleSpec が公開名を正しく認識する
9. **`STATEMENT_TYPE_LABELS` / `format_period()` を `financial.py` から import する理由**: `__str__()` と Rich 表示でタイトル形式を統一する。`display/rich.py` は既に `FinancialStatement` を引数に取る時点で `models → display` の依存方向が確立済みのため、追加の共有関数を import しても新たな依存は発生しない
10. **Rich title で `period` が `None` のとき空文字にする理由**: `__str__()` は `"(期間なし)"` を表示するが、Rich Table の title では `"損益計算書 (Income Statement)  [連結]"` だけの方が視覚的にスマート。Rich Table は title が短い方がバランスが良く、欠損情報を明示するのは `__str__()` の責務とする
11. **`_build_title()` で `rich.markup.escape()` を使う理由**: Rich の Table title はマークアップ構文を解釈するため、`[連結]` が `[style]text[/style]` と衝突して `MarkupError` が発生する。`escape()` で角括弧をエスケープすることで回避する。`__str__()` 側は Rich を使わないためエスケープ不要
12. **`render_statement()` の公開 API 判断のレビュー評価**: edgartools も statement オブジェクトから Rich Table を取得できる公開 API を持つ。Table オブジェクトを返すことで、利用者が `table.add_column("備考")` 等のカスタマイズを行える。レビューでこの設計が「カスタマイズが容易」と評価された

---

## 9. `FinancialStatement.__rich_console__()` の設計

### 9.1 実装

```python
# models/financial.py に追加

def __rich_console__(self, console, options):
    """Rich Console Protocol。

    ``from rich.console import Console; Console().print(pl)`` で
    フォーマットされたテーブルが表示される。

    rich がインストールされていない場合、この Protocol は呼ばれない
    （Rich Console 自体が存在しないため）。
    display/rich.py の import に失敗した場合は __str__ にフォールバックする。
    """
    try:
        from edinet.display.rich import render_statement

        yield render_statement(self)
    except ImportError:
        yield str(self)
```

### 9.2 `print(pl)` の挙動整理

| 状況 | `print(pl)` の結果 |
|---|---|
| Rich なし | `__str__()` が呼ばれる → プレーンテキストテーブル |
| Rich あり、通常の `print()` | `__str__()` が呼ばれる → プレーンテキストテーブル |
| Rich あり、`Console().print(pl)` | `__rich_console__()` が呼ばれる → Rich テーブル |

Python 標準の `print()` は常に `__str__()` を呼ぶ。Rich テーブルは `Console().print()` を使う必要がある。これは Rich の標準的な使い方であり、利用者にとって自然。

### 9.3 型アノテーション

`__rich_console__` のシグネチャに `Console`, `ConsoleOptions`, `RenderResult` の型を付けると `import edinet` 時に Rich の import が必要になる。`TYPE_CHECKING` ガードで回避:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from rich.console import Console, ConsoleOptions, RenderResult

# 実行時のシグネチャは型なし
def __rich_console__(self, console, options):
    ...
```

既存の `models/financial.py` は `TYPE_CHECKING` ガードを使っている（`contexts.py` や `taxonomy.py` の型を runtime で import しない）ため、この パターンは既存の設計と一貫する。

### 9.4 設計判断

1. **`ImportError` のみキャッチする理由**: Rich がインストールされているが `display/rich.py` のコードにバグがある場合（`TypeError`, `AttributeError` 等）、それを飲み込むとデバッグが困難になる。`ImportError` のみを対象にすることで、依存不足のセーフティネットと、バグの早期発見を両立する
2. **間接関数を経由しない理由**: §8.5-7 参照。`yield render_statement(self)` の 1 行で十分

---

## 10. テスト計画

### 10.1 テスト用フィクスチャの方針

**既存の `tests/test_xbrl/test_statements.py` のヘルパー（`_make_pl_item()`, `_make_bs_item()`, `_make_label()`）を `conftest.py` に移動せず、Day 16 のテストファイル内でも同等のヘルパーを定義する**。理由:
- `_make_pl_item()` は `test_statements.py` の内部ヘルパーであり、公開フィクスチャではない
- Day 16 のテストは `FinancialStatement` を直接構築するため、`_make_pl_item()` より薄いヘルパーで十分
- テストファイル間の結合を避ける（Day 15 のヘルパーが変わっても Day 16 のテストが壊れない）

**重複の許容判断**: `_label()` と `_item()` が `test_rich.py`、`test_financial_display.py`、`test_statements.py` の 3 箇所に存在する。`LineItem` のフィールド数（15 個）を考えると `conftest.py` での共有も選択肢だが、v0.1.0 では `LineItem` のフィールドが安定しているため現状維持とする。

**`conftest.py` 共通化のトリガー条件**: 以下のいずれかが発生した時点で共通化を実行する:
- `LineItem` にフィールド追加（`indent_level`, `depth` 等）が発生し、3 箇所以上のヘルパーを修正する必要が生じた場合
- 新たなテストファイルが `_item()` 相当のヘルパーを 4 箇所目として定義しようとした場合
- いずれも v0.2.0 の Presentation Linkbase 対応時に該当する見込み

### 10.2 テスト用ヘルパー

```python
"""tests/test_models/test_financial_display.py — __str__, to_dataframe のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
_PERIOD = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))


def _label(text: str, lang: str = "ja") -> LabelInfo:
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _item(
    local_name: str = "NetSales",
    label_ja: str = "売上高",
    label_en: str = "Net sales",
    value: Decimal | str | None = Decimal("1000000000"),
    order: int = 0,
    period: DurationPeriod | InstantPeriod = _PERIOD,
) -> LineItem:
    return LineItem(
        concept=f"{{{_NS}}}{local_name}",
        namespace_uri=_NS,
        local_name=local_name,
        label_ja=_label(label_ja, "ja"),
        label_en=_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearDuration",
        period=period,
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


@pytest.fixture()
def sample_pl() -> FinancialStatement:
    """テスト用の PL。3 科目。"""
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(
            _item("NetSales", "売上高", "Net sales", Decimal("45095325000000"), 1),
            _item("OperatingIncome", "営業利益", "Operating income", Decimal("4295325000000"), 5),
            _item("OrdinaryIncome", "経常利益", "Ordinary income", Decimal("4800000000000"), 8),
        ),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


@pytest.fixture()
def empty_pl() -> FinancialStatement:
    """空の PL。"""
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=None,
        items=(),
        consolidated=True,
        entity_id="",
        warnings_issued=(),
    )
```

### 10.3 テストケース — `__str__()`

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| S-1 | `test_str_contains_type_label` | 出力に `"損益計算書"` が含まれる | small, unit |
| S-2 | `test_str_contains_consolidated_label` | 出力に `"連結"` が含まれる | small, unit |
| S-3 | `test_str_contains_period` | 出力に `"2024-04-01"` と `"2025-03-31"` が含まれる | small, unit |
| S-4 | `test_str_contains_item_labels` | 出力に各科目の `label_ja.text` が含まれる | small, unit |
| S-5 | `test_str_contains_formatted_values` | 出力に `"45,095,325,000,000"` が含まれる（カンマ区切り） | small, unit |
| S-6 | `test_str_contains_count` | 出力に `"3 科目"` が含まれる | small, unit |
| S-7 | `test_str_empty_statement` | 空 statement で `"科目なし"` が含まれ、例外が出ない | small, unit |
| S-8 | `test_str_non_consolidated` | `consolidated=False` で `"個別"` が含まれる | small, unit |
| S-9 | `test_str_balance_sheet_instant_period` | BS（`InstantPeriod`）で `"2025-03-31"` が含まれる（`〜` なし） | small, unit |
| S-10 | `test_str_negative_value` | 負値（`Decimal("-500000000")`）で `"-500,000,000"` が出力に含まれること | small, unit |
| S-11 | `test_str_text_value` | `value="テキスト値"` の LineItem で `__str__` が例外なく動き、`"テキスト値"` が出力に含まれること | small, unit |
| S-12 | `test_str_none_value` | `value=None` の LineItem で `__str__` が例外なく動き、`"—"` が出力に含まれること | small, unit |
| S-13 | `test_str_cash_flow_statement` | CF タイプで `"キャッシュ・フロー計算書"` が含まれること。3 種の `StatementType` 全てのラベルを検証 | small, unit |

### 10.4 テストケース — `to_dataframe()`

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| D-1 | `test_to_dataframe_columns` | カラムが `["label_ja", "label_en", "value", "unit", "concept"]` であること | small, unit |
| D-2 | `test_to_dataframe_row_count` | 行数が `len(pl.items)` と一致すること | small, unit |
| D-3 | `test_to_dataframe_value_type` | `value` 列の値が `Decimal` であること（`float` に変換されていない） | small, unit |
| D-4 | `test_to_dataframe_labels` | `label_ja` 列の値が科目名と一致すること | small, unit |
| D-5 | `test_to_dataframe_empty` | 空 statement で空 DataFrame（0行）が返り、**カラム名が `["label_ja", "label_en", "value", "unit", "concept"]` と一致する**こと | small, unit |
| D-6 | `test_to_dataframe_import_error` | `patch.dict(sys.modules, {"pandas": None})` で `ImportError` が `"pip install edinet[analysis]"` メッセージ付きで発生すること | small, unit |
| D-7 | `test_to_dataframe_attrs` | `df.attrs` に `statement_type`, `consolidated`, `period`, `entity_id` が含まれ、値が正しいこと | small, unit |
| D-8 | `test_to_dataframe_roundtrip_value` | `df["value"].iloc[0] == Decimal("45095325000000")` であること。D-3 は型のみだが D-8 は値レベルで `Decimal` が `float` に劣化していないことを検証 | small, unit |

### 10.5 テストケース — Rich 描画

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| R-1 | `test_render_statement_returns_table` | `render_statement()` が `rich.table.Table` を返すこと | small, unit |
| R-2 | `test_render_statement_column_count` | Table のカラム数が 3 であること | small, unit |
| R-3 | `test_render_statement_row_count` | `table.row_count` が `len(pl.items)` と一致すること | small, unit |
| R-4 | `test_render_statement_title_contains_type` | Table の title に `"損益計算書"` が含まれること | small, unit |
| R-5 | `test_rich_console_print` | `Console(file=StringIO()).print(pl)` が例外なく動き、出力に `"損益計算書"` が含まれること | small, unit |
| R-6 | `test_render_statement_empty` | 空 statement で空の Table（0行）が返ること | small, unit |
| R-7 | `test_render_statement_escaped_brackets` | `[連結]` が Rich マークアップと衝突せず `MarkupError` が発生しないこと。`Console(file=StringIO()).print(table)` で出力に `"連結"` が含まれることを検証（Rev3-C3 の `escape()` 実装の検証） | small, unit |

### 10.6 テストケース — 遅延 import 保証

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| I-1 | `test_import_edinet_without_pandas` | `import edinet` が pandas なしでも成功すること | slow |
| I-2 | `test_import_edinet_without_rich` | `import edinet` が rich なしでも成功すること | slow |

I-1 と I-2 は `subprocess` で別プロセスを起動し、mock ではなく実際に `import` を試みる。`monkeypatch` による `sys.modules` 操作は副作用が大きいため `subprocess` を使う。

```python
@pytest.mark.slow
def test_import_edinet_without_pandas():
    """pandas なしでも import edinet が成功すること。"""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable, "-c",
            "import sys; sys.modules['pandas'] = None; import edinet; print('ok')",
        ],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout
```

注意: `sys.modules['pandas'] = None` は CPython 固有の挙動に依存しており、Python 3.12+ で不安定になる可能性がある。CI で不安定になった場合は pandas なしの仮想環境を用意する方式に切り替えを検討する。

### 10.7 marker 方針

- `small` + `unit`: in-memory FinancialStatement を使うテスト（S-1〜S-13, D-1〜D-8, R-1〜R-7）
- `slow`: subprocess による import テスト（I-1, I-2）

### 10.8 `pytest.mark.parametrize` の活用

- S-8 + S-9 → `test_str_scope_and_period` にまとめ、`(consolidated, period, expected_scope, expected_period_substr)` で parametrize:

```python
@pytest.mark.parametrize("consolidated,expected", [
    (True, "連結"),
    (False, "個別"),
])
def test_str_scope_label(consolidated, expected):
    pl = FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(_item(),),
        consolidated=consolidated,
        entity_id="E00001",
        warnings_issued=(),
    )
    assert expected in str(pl)
```

---

## 11. 依存関係の確認

```
Day 16 の依存構造:

models/financial.py   →   display/rich.py   →   rich (optional)
  (__rich_console__)       (render_statement)     (Table)
                                ↓
                           models/financial.py から import:
                             STATEMENT_TYPE_LABELS
                             format_period
        ↓
  to_dataframe()      →   pandas (optional)

models/financial.py   →   xbrl/contexts.py
  (__str__, format_period)  (InstantPeriod, DurationPeriod)
```

- `models/financial.py` → `display/rich.py`: `__rich_console__()` 内での **runtime import**。`from edinet.display.rich import render_statement` はメソッド呼び出し時にのみ実行される
- `display/rich.py` → `models/financial.py`: runtime import（`STATEMENT_TYPE_LABELS`, `format_period`）。依存方向は `display → models` で一方通行
- `display/rich.py` → `rich`: runtime import（`from rich.table import Table`）。Rich がない環境では `ImportError`（ユーザーフレンドリーメッセージ付き）
- `models/financial.py` → `pandas`: `to_dataframe()` 内での runtime import のみ
- `display/__init__.py` → `display/rich.py`: `__getattr__` による遅延 import。`import edinet.display` 時点では Rich を import しない
- 循環依存は発生しない（`financial.py` → `rich.py` は `__rich_console__` 内の遅延 import、`rich.py` → `financial.py` は通常 import）

---

## 12. CODESCOPE.md への追記

Day 16 の内容を §7 として追記する:

```markdown
## 7. display — 表示レイヤー（Day 16）

### 責務

FinancialStatement を人間が読みやすい形式で表示する。**表示のためのフォーマット変換のみ** を行い、
ビジネスロジック（Fact 選択・並び順の決定等）は §5 statements の責務。

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| D-1 | プレーンテキスト | `FinancialStatement.__str__()` で Rich なしでもまともな表示 | PLAN.LIVING.md Day 16 |
| D-2 | Rich テーブル | `render_statement()` + `__rich_console__()` | PLAN.LIVING.md Day 16 |
| D-3 | DataFrame 変換 | `to_dataframe()` で pandas DataFrame に変換 | PLAN.LIVING.md Day 16 |

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| DN-1 | HTML / Jupyter | `_repr_html_()` による Jupyter インライン表示 | FEATURES.md display/html → v0.2.0 |
| DN-2 | 複数期間並列表示 | 当期 vs 前期の並列テーブル | CODESCOPE.md SN-6 → v0.2.0 |
| DN-3 | decimals スケーリング | 百万円・千円表示 | 値は XBRL 原値のまま。スケーリングは利用者の責務 |
| DN-4 | 階層インデント | 小計・内訳の階層構造 | Presentation Linkbase の木構造がない（SN-3）。v0.2.0 |

### 設計判断の記録

- **描画ロジックを `display/rich.py` に集約する理由**: `models/financial.py` に Rich の import を持ち込まない。
  `__rich_console__` は 2 行のブリッジのみ。Rich がない環境でも `models/financial.py` の import は成功する
- **`render_statement()` を公開 API にする理由**: Rich Table オブジェクトを取得しカスタマイズしたい利用者向け
- **`to_dataframe()` のカラムを 5 列に絞る理由**: 利用者が最も頻繁に必要とする情報に限定。メタデータは `LineItem` から直接取得可能
```

---

## 13. 当日の作業手順（チェックリスト）

### Phase 1: `__str__()` の実装（~15 分）

1. `src/edinet/models/financial.py` に `STATEMENT_TYPE_LABELS` 辞書、`_display_width()` ヘルパー、`format_period()` ヘルパーを追加
2. `FinancialStatement.__str__()` を実装（§6.2）
3. `uv run ruff check src/edinet/models/financial.py` で lint pass を確認
4. 手動スモーク: `print(pl)` でプレーンテキストが出力されることを確認

### Phase 2: `to_dataframe()` の実装（~15 分）

1. `FinancialStatement.to_dataframe()` を実装（§7.1）
2. `uv run ruff check src/edinet/models/financial.py` で lint pass を確認
3. 手動スモーク: `pl.to_dataframe()` で DataFrame が返ることを確認

### Phase 3: `display/rich.py` の実装（~15 分）

1. `src/edinet/display/rich.py` に `render_statement()`, `_build_title()` を実装（§8）
2. `src/edinet/display/__init__.py` に `__getattr__` 遅延 import + `__dir__` を追加（§8.4）
3. `src/edinet/models/financial.py` に `__rich_console__()` を追加（§9.1）
4. `uv run ruff check src/edinet/display/ src/edinet/models/financial.py` で lint pass を確認
5. 手動スモーク: `from rich.console import Console; Console().print(pl)` でテーブルが出力されることを確認

### Phase 4: テスト（~30 分）

1. `tests/test_display/__init__.py` を空ファイルで作成
2. `tests/test_display/test_rich.py` を作成（§10.5: R-1〜R-7）
3. `tests/test_models/test_financial_display.py` を作成（§10.3: S-1〜S-13, §10.4: D-1〜D-8）
4. `uv run pytest tests/test_display/ tests/test_models/test_financial_display.py -v` で全件 pass を確認
5. 遅延 import テスト（§10.6: I-1, I-2）を適切な場所に追加
6. `uv run pytest tests/test_display/ tests/test_models/test_financial_display.py -v -m slow` で slow テストが pass することを確認（`slow` マーカーは pyproject.toml に定義済み。デフォルト実行でも除外されない）

### Phase 5: 検証（~15 分）

1. `uv run pytest` — 全テスト回帰なし（434 + 新規テスト）
2. `uv run ruff check src tests` — 警告なし
3. `uv run stubgen src/edinet --include-docstrings -o stubs` — `.pyi` 再生成
4. 生成された `stubs/edinet/models/financial.pyi` と `stubs/edinet/display/rich.pyi` の diff を確認
4b. 生成された `stubs/edinet/display/__init__.pyi` に `render_statement` が明示的にエクスポートされていることを確認する。`__getattr__` による遅延 import は型チェッカーが認識しない場合があるため、`.pyi` での明示が必須。もし stubgen が `__getattr__` を解決できない場合は、手動で `def render_statement(statement: FinancialStatement) -> Table: ...` を `.pyi` に記述する
5. CODESCOPE.md に §7 を追記（§12）
5b. FEATURES.md の `display/rich` ステータスを確認する。現在 `[DONE]` だが Day 16 以前は空スタブのため不正確だった。Day 16 完了で実質 DONE になるため、ステータスは維持で良いが、実装内容（`render_statement()` が提供する機能）との整合を確認する
6. 手動スモーク: 実 filing 1 件で全パイプラインを実行し、以下を順に確認

```python
from edinet import documents
from edinet.xbrl import (
    parse_xbrl_facts, structure_contexts, TaxonomyResolver,
    build_line_items, build_statements,
)

filing = documents("2025-06-25", doc_type="120")[0]
path, xbrl_bytes = filing.fetch()
parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)
resolver = TaxonomyResolver(r"C:\Users\nezow\Downloads\ALL_20251101")

items = build_line_items(parsed.facts, ctx_map, resolver)
stmts = build_statements(items)
pl = stmts.income_statement()

# 1. __str__
print(pl)

# 2. __repr__（既存、回帰なし確認）
print(repr(pl))

# 3. Rich テーブル
from rich.console import Console
Console().print(pl)

# 4. render_statement（公開 API）
from edinet.display.rich import render_statement
table = render_statement(pl)
Console().print(table)

# 5. DataFrame
df = pl.to_dataframe()
print(df)
print(df.dtypes)  # value が object（Decimal）であること

# 6. BS / CF も同様に確認
bs = stmts.balance_sheet()
print(bs)
Console().print(bs)

cf = stmts.cash_flow_statement()
print(cf)
Console().print(cf)
```

---

## 14. Day 17 への引き継ぎ事項

Day 16 完了後、Day 17（E2E 統合）で以下が動くための前提が揃う:

```python
from edinet import Company
toyota = Company("7203")
filing = toyota.latest("有価証券報告書")
pl = filing.xbrl().statements.income_statement()
print(pl)              # __str__ で表示（Day 16）
df = pl.to_dataframe() # DataFrame 変換（Day 16）
```

Day 17 で実装すべきもの:
- `Filing.xbrl()` メソッド: ZIP 展開 → パース → ラベル解決 → Statement 組み立てを繋ぐ
- `Company.latest()` メソッド
- E2E 統合テスト

Day 16 レビューからの引き継ぎ（P1 推奨）:
- **`to_dict()` / `to_records()` の実装** (P1-1): LLM（RAG）パイプラインとの親和性が PLAN.LIVING.md の設計思想に明記されている。pandas 不要で dict リストを返すメソッドは、LLM 連携の第一歩として Day 17 までに実装すべき。5 行・依存ゼロ
- **`Statements.__str__()` の追加** (P2-1): `print(stmts)` で PL + BS + CF が一括表示される。REPL での第一印象に直結。5 行で実装可能

Day 16 の成果物（`__str__`, `to_dataframe()`, Rich 表示）は Day 17 の E2E デモで直接使われるため、Day 16 の品質が Day 17 のデモの印象を決定する。

---

## 15. 改訂ログ

本セクションは計画の変更履歴を記録する。§6〜§9 本文は常に最終版を反映する。

> **可読性に関する注記**: 改訂ログが計画書全体の約 1/3 を占めている。v0.2.0 以降、改訂ログが計画本文より長くなる場合は別ファイル（例: `Day16_revisions.md`）への分離を検討する。現時点では単一ファイルに全情報を保持する利便性を優先する。

### Rev.1（レビュー 1 回目）

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev1-A1 | `render_statement()` に `try/except ImportError` + ユーザーフレンドリーメッセージを追加 | `to_dataframe()` との一貫性 |
| Rev1-A2 | `_STATEMENT_TYPE_TITLES` を廃止し `STATEMENT_TYPE_LABELS` を `financial.py` に一本化。`rich.py` から import | タイトル形式の統一 |
| Rev1-A3 | `format_period()` を `financial.py` で定義し `rich.py` の `_build_title()` から import | 重複ロジックの排除。依存方向は display → models で既に確立 |
| Rev1-B1 | `_display_width()` ヘルパー追加。`__str__()` のラベル幅計算を CJK 対応に | `print(pl)` の第一印象向上 |
| Rev1-B2 | `__rich_console__()` に `ImportError` キャッチ + `__str__` フォールバック | 防御的プログラミング |
| Rev1-B3 | テスト D-5 にカラム名の一致検証を追加 | テスト補強 |
| Rev1-C1 | `rich_console_hook` → `render_for_console` にリネーム | 命名の明確化（※ Rev.2 で関数自体を削除） |
| Rev1-C2 | D16N-7「負値の △ / () 表記」を §3.2 に追加 | v0.2.0 フォーマットオプションとして記録 |
| Rev1-C3 | Phase 5 に `.pyi` の `render_statement` エクスポート確認を追加 | 型チェッカー対応 |

### Rev.2（レビュー 2 回目）

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev2-A1 | `render_for_console()` を削除。`__rich_console__` から直接 `render_statement` を yield | 不要な間接層の排除（console/options を使わない） |
| Rev2-A2 | `_format_period` → `format_period`、`_STATEMENT_TYPE_LABELS` → `STATEMENT_TYPE_LABELS` にリネーム | クロスモジュール利用に `_` prefix は慣習に反する。`__all__` には含めず内部 API の位置づけ |
| Rev2-A3 | `to_dataframe()` の空 DataFrame 処理を §7.1 に統合。`_DATAFRAME_COLUMNS` 定数を導入 | 実装の分散（§7.1 + §7.3）を解消 |
| Rev2-B1 | `__str__()` の docstring に Decimal INF/NaN が来ない前提を注記 | `build_statements()` 経由の保証を文書化 |
| Rev2-B2 | テスト I-1/I-2 の `sys.modules` パターンの制限を注記 | Python 3.12+ での不安定性の可能性を記録 |
| Rev2-B3 | `display/__init__.py` に `__dir__()` を追加 | IDE 補完対応 |
| Rev2-B4 | D16N-8「Rich concept カラム幅制限」を §3.2 に追加 | v0.2.0 IFRS 対応時に検討として記録 |
| Rev2-D1 | §15 の改訂コードブロックを §6〜§9 本文にマージ。§15 は変更ログに縮小 | 最終版を一箇所にまとめ、実装時の混乱を防止 |

### Rev.3（レビュー 3 回目）

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev3-A1 | `slow` マーカーは pyproject.toml に定義済みであることを確認。Phase 4 の `--run-slow`（存在しないオプション）を `-m slow` に修正 | A-1: マーカー定義の確認 |
| Rev3-A2 | `tests/test_models/` は存在済みを確認。`tests/test_display/` は新規作成が必要（計画通り） | A-2: ディレクトリ存在確認 |
| Rev3-A3 | Phase 5 に FEATURES.md の `display/rich` ステータス整合確認を追加 | A-3: FEATURES.md の `[DONE]` が空スタブ時点で付いていた不正確さ |
| Rev3-B1 | テスト S-10「負値の表示」を追加。`Decimal("-500000000")` → `"-500,000,000"` が含まれることを検証 | B-1: 負値テストケースの欠落 |
| Rev3-B2 | テスト D-6 の実装方法を明記。`patch.dict(sys.modules, {"pandas": None})` を使用 | B-2: テスト実装の詳細化 |
| Rev3-B3 | テスト R-3 に `table.row_count` プロパティの使用を明記 | B-3: Rich API の明確化 |
| Rev3-B4 | `to_dataframe()` に `-> "pd.DataFrame"` 戻り値型アノテーションを追加。`TYPE_CHECKING` ガードで `import pandas as pd` | B-4: 型安全性 |
| Rev3-C1 | §6.4 に `_display_width()` の Ambiguous カテゴリの制限を記録 | C-1: △ 等の文字幅の不定性を認識 |
| Rev3-C3 | `_build_title()` に `rich.markup.escape()` を追加。`[連結]` が Rich マークアップと衝突する問題を修正 | C-3: **実装時バグの未然防止** |
| Rev3-C4 | `__str__` の末尾改行の仕様は現状維持（`print()` が `\n` を付加するため問題なし） | C-4: 認識のみ |

### Rev.4（レビュー 4 回目）

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev4-P0-1 | `to_dataframe()` に `df.attrs` でメタデータ（`statement_type`, `consolidated`, `period`, `entity_id`）を付与。テスト D-7 を追加 | 複数 Filing の DataFrame を concat した後の識別手段を提供 |
| Rev4-P0-2 | テスト S-11「`value: str` ケース」を追加。型定義上 `str` を許容するため防御テスト | ユーザーが手動構築した場合の堅牢性保証 |
| Rev4-P0-3 | `max(..., default=0)` を §6.2 に追加。早期リターンで到達しないが defensive coding | `ValueError` の未然防止 |
| Rev4-P1-4 | `to_dataframe()` docstring に `astype(int)` ヒントと `attrs` がシリアライズされない旨を追記 | EDINET 固有の知識提供。利用者の第一印象向上 |
| Rev4-P1-5 | D16N-9「Rich テーブルの unit カラム」を §3.2 に追加 | v0.2.0 EPS 対応時に検討として記録 |
| Rev4-P1-7 | `format_period()` を `financial.py` に置く現設計を維持。`contexts.py` に `__str__` を追加する代替案は「表示の責務が contexts に漏れる」ため不採用 | 責務の分離が明確 |

### Rev.5（レビュー 5 回目 — 最終）

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev5-B1 | テスト S-12「`value: None` ケース」を追加。`"—"` が出力に含まれることを検証 | 型定義上の全分岐をテスト |
| Rev5-B2 | §7.2 に `concept` カラムが `local_name` のみの理由と v0.2.0 での `namespace` カラム追加検討を追記 | IFRS 対応時の手戻り防止 |
| Rev5-D2 | §8.5 に Rich title で `period=None` のとき空文字にする理由を追記 | `__str__` の `"(期間なし)"` との差異を意図的なものとして明文化 |
| Rev5-D3 | テストヘルパー `_item()` に `period` 引数と `value` 型を `Decimal | str | None` に拡張 | テストの柔軟性向上（S-9 の BS テスト等で活用） |

### Rev.6（外部フィードバック反映）

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev6-1 | テスト R-7「Rich エスケープテスト」を追加。`[連結]` が `MarkupError` を起こさないことを検証 | Rev3-C3 の `escape()` 実装に対応するテストが欠落していた。唯一の実質的な穴 |
| Rev6-2 | テスト S-13「CF ラベルテスト」を追加。`"キャッシュ・フロー計算書"` が含まれることを検証 | 3 種の `StatementType` 全てのラベルをテストでカバー |
| Rev6-3 | テスト D-8「Decimal 値レベル検証」を追加。`df["value"].iloc[0] == Decimal(...)` を検証 | D-3 は型のみ。値レベルで `float` 劣化がないことを保証 |
| Rev6-4 | `STATEMENT_TYPE_LABELS` に `Final` アノテーション、`_DATAFRAME_COLUMNS` に `Final` アノテーションを追加 | frozen dataclass のコンセプトと一貫。定数の意図を明確化 |
| Rev6-5 | `__str__()` の `f"{item.value:>20,}"` に「値幅は固定 20 カラム」の Note コメントを追加 | ラベル幅は動的計算なのに値幅が固定である不統一を将来の開発者に伝達 |
| Rev6-6 | D16N-10「`to_dict()` / `to_records()`」を §3.2 に追加 | LLM パイプライン向け。Day 17 以降で検討 |

### Rev.7（実装後レビュー反映）

実装完了後のレビューフィードバックを反映。全指摘が「nice to have」レベルであり、コード変更は不要。
v0.2.0 以降の検討事項として §3.2 に記録し、設計判断の補足を追記。

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev7-1 | D16N-11「`__str__` の値幅の動的計算」を §3.2 に追加 | 固定 20 カラム幅は百兆円超で溢れる理論上のリスク。動的化は 3 行で対応可能なため v0.2.0 で検討 |
| Rev7-2 | D16N-12「`Statements.__str__()`」を §3.2 に追加 | D16N-4 と関連するが、REPL 体験の改善として Day 17 以降で 5 行の追加を検討 |
| Rev7-3 | D16N-13「`_display_width()` の wcwidth 移行」を §3.2 に追加 | §6.4-6 で認識済みの Ambiguous カテゴリ問題。`△` が EDINET 科目名で頻出するため v0.2.0 で検討 |
| Rev7-4 | §6.4 に「ヘッダーの `[連結]` 前後のダブルスペースは意図的なフォーマット」を補足 | レビューでの質問に対する明文化 |
| Rev7-5 | §10.1 にテストヘルパー重複の許容判断を補足。`LineItem` が安定している v0.1.0 では現状維持、v0.2.0 で `conftest.py` 共有化を再検討 | レビュー指摘への応答 |
| Rev7-6 | §7.2 に `to_dataframe()` docstring の Example（`df["value"] > 0`）が pandas 2.0+ の `Decimal` 比較で正しく動作する旨を補足 | レビューで指摘された `astype(float)` 代替案は cosmetic であり現状維持 |
| Rev7-7 | 拡張性評価を §3.2 末尾に追記。v0.2.0 機能（`_repr_html_`, 複数期間, 階層インデント, IFRS namespace, unit カラム）の拡張容易性を記録 | レビューの拡張シナリオ評価を計画に反映 |

### Rev.8（実装後レビュー 2 回目反映）

2 回目の実装後レビューフィードバックを反映。P0（修正必須）なし。P1 を Day 17 以降のアクションとして記録。
レビューで特に高く評価された設計判断（遅延 import、Decimal 保持、CJK 幅、Rich エスケープ）を §2 の設計判断根拠に反映。

| # | 変更内容 | 根拠 |
|---|---------|------|
| Rev8-1 | P1-1「`to_dict()` / `to_records()` の Day 17 実装」を §14 Day 17 引き継ぎに追記 | LLM パイプラインとの親和性が PLAN.LIVING.md の設計思想に明記されている。pandas 不要で dict リストを返すメソッドは Day 17 までの実装を推奨 |
| Rev8-2 | P1-2「テストヘルパーの `conftest.py` 共通化」のトリガー条件を §10.1 に明記 | v0.2.0 で `LineItem` にフィールド追加時に実行。トリガー条件が曖昧だったため閾値を明文化 |
| Rev8-3 | P2-1「`Statements.__str__()`」を §14 Day 17 引き継ぎに追記 | REPL 体験改善。5 行で実装可能 |
| Rev8-4 | §2.1 に「オプション依存の遅延 import が日本の企業環境で重要な理由」を補足 | レビューで「pip install が制限されている環境が多い」との指摘。設計判断の根拠強化 |
| Rev8-5 | §8.5 に「`render_statement()` の公開 API 判断」のレビュー評価を追記 | edgartools との対比評価がレビューで示された |
| Rev8-6 | 計画書の可読性改善提案（改訂ログの分離）を §15 冒頭に注記 | レビュー指摘: 改訂ログが全体の 1/3 を占め過長。別ファイル化を v0.2.0 で検討 |

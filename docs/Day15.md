# Day 15 — FinancialStatement 組み立て

## 0. 位置づけ

Day 15 は、Day 13 で生成した `LineItem` 群を **PL / BS / CF に分類し、選択ルールを適用して `FinancialStatement` オブジェクトを組み立てる** 日。
Week 3（統合 + 公開）の最初のマイルストーンであり、v0.1.0 の核心機能。

Day 14 完了時点の状態:
- `parse_xbrl_facts()` → `ParsedXBRL`（RawFact + RawContext + RawUnit）
- `structure_contexts()` → `dict[str, StructuredContext]`（期間・Entity・Dimension を型付きで引ける）
- `TaxonomyResolver` → concept → `LabelInfo` のラベル解決（標準 + 提出者、namespace バージョンフォールバック対応済み）
- `build_line_items()` → `tuple[LineItem, ...]`（全 Fact を型付き・ラベル付きに変換）
- 全書類タイプ 24 種でパイプライン PASS、FALLBACK 率 0%（v0.1.0 対象書類）
- pytest 397/397 PASS、ruff Clean

Day 15 完了時のマイルストーン:

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
print(pl.statement_type)  # StatementType.INCOME_STATEMENT
print(len(pl.items))      # 科目数

for item in pl.items:
    print(f"{item.label_ja.text}: {item.value:>20,} {item.unit_ref}")
    # "売上高:   45,095,325,000,000 JPY"

# 辞書的アクセス
revenue = pl["売上高"]
revenue = pl["Net sales"]
revenue = pl["NetSales"]
print(revenue.value)  # Decimal("45095325000000")
```

CODESCOPE.md §5 で定義された責務（ST-1〜ST-5）を実装し、スコープ外（SN-1〜SN-7）は実装しない。

---

## 1. 現在実装の確認結果

| ファイル | 現状 | Day 15 で必要な変更 |
|---|---|---|
| `src/edinet/xbrl/statements.py` | 1 行 docstring のみ（`"""XBRL 財務諸表構造ユーティリティ。"""`） | 新規実装。`build_statements()` + `Statements` クラス + Fact 選択ロジック **[FB2-C1]** |
| `src/edinet/models/financial.py` | `LineItem` frozen dataclass のみ | `FinancialStatement`, `StatementType` を追加（`Statements` は `xbrl/statements.py` に配置 **[FB2-C1]**） |
| `src/edinet/xbrl/data/` | ディレクトリ未作成 | PL/BS/CF の concept 定義 JSON を新規作成 |
| `src/edinet/xbrl/__init__.py` | `parse_xbrl_facts`, `structure_contexts`, `TaxonomyResolver`, `build_line_items` をエクスポート | `build_statements` を追加エクスポート |
| `tests/test_xbrl/test_statements.py` | 未作成 | 新規作成 |
| `stubs/edinet/xbrl/statements.pyi` | 空（docstring のみ） | stubgen で生成 |
| `stubs/edinet/models/financial.pyi` | `LineItem` のみ | stubgen で再生成 |

補足:
- `LineItem` のフィールド一覧（financial.py L46-60）: `concept`, `namespace_uri`, `local_name`, `label_ja`, `label_en`, `value`, `unit_ref`, `decimals`, `context_id`, `period`, `entity_id`, `dimensions`, `is_nil`, `source_line`, `order`
- `LineItem.value` は `Decimal | str | None`。数値 Fact（`unit_ref` あり）は `Decimal`、テキスト Fact（`unit_ref` なし）は `str`、nil Fact は `None`
- `LineItem.dimensions` は `tuple[DimensionMember, ...]`。空 = dimension なし = 連結（デフォルト）
- `LineItem.period` は `InstantPeriod | DurationPeriod`。BS は instant、PL/CF は duration
- `isinstance(item.period, Period)` は Python 3.12 で正常に動作する（`Period = InstantPeriod | DurationPeriod` は `types.UnionType`）。個別の型判定は `isinstance(item.period, DurationPeriod)` を使うこと

---

## 2. ゴール

1. `LineItem` 群を PL / BS / CF に分類する関数を実装する
2. Fact 選択ルール（期間・連結・dimension フィルタ）を明示的にコード化する
3. JSON データファイルで concept 集合と並び順を管理する
4. `FinancialStatement` / `StatementType` / `Statements` を `models/financial.py` に定義する
5. `FinancialStatement.__getitem__` で `pl["売上高"]` / `pl["NetSales"]` アクセスを提供する
6. 重複 Fact 発生時に候補数と除外理由を含む `warnings.warn()` を出す

---

## 3. スコープ / 非スコープ

### 3.1 Day 15 のスコープ

CODESCOPE.md §5 の処理する項目（ST-1〜ST-5）に対応:

| CODESCOPE | 内容 | Day 15 での実装 |
|---|---|---|
| ST-1 | Fact 選択 | 期間・連結・dimension の 3 段フィルタ。ルールは §6 で詳述 |
| ST-2 | 科目分類 | JSON データファイルの concept 集合で PL/BS/CF に分類 |
| ST-3 | 並び順 | JSON の `order` に従う。JSON にない科目は末尾に出現順で追加 |
| ST-4 | ラベル解決 | Day 13 で LineItem に付与済み。Day 15 では追加処理なし |
| ST-5 | 重複候補の警告 | 候補数と除外理由を含む `warnings.warn()` |

### 3.2 Day 15 でやらないこと

CODESCOPE.md §5 のスコープ外（SN-1〜SN-7）:

| CODESCOPE | 内容 | やらない理由 |
|---|---|---|
| SN-1 | 欠損科目の補填（None 出力） | 1社の PL を見るのが主用途。企業間比較は DataFrame merge 時に NaN が自然に出る |
| SN-2 | 非標準科目の除外オプション | v0.1.0 では末尾追加で固定。データ欠落を防ぐ方が優先 |
| SN-3 | Presentation Linkbase 並び順 | v0.1.0 では JSON の order で代替 |
| SN-4 | IFRS / US-GAAP 対応 | v0.1.0 は J-GAAP 一般事業会社のみ（PLAN.LIVING.md §1） |
| SN-5 | 特定業種対応（銀行・保険等） | v0.1.0 は一般事業会社のみ |
| SN-6 | 複数期間比較 | v0.1.0 では単一期間。全 Fact は保持しているので v0.2.0 で拡張可能 |
| SN-7 | Calculation Linkbase 検算 | validation/ モジュール（FEATURES.md）の責務 |

Day 15 でやらないその他:
- `to_dataframe()` の実装（→ Day 16）
- Rich 表示の実装（→ Day 16）
- `Filing.xbrl()` の E2E 統合（→ Day 17）
- `Company.latest()` の実装（→ Day 17）
- SS（株主資本等変動計算書）の組み立て（→ v0.2.0。2 次元テーブル構造のため definition linkbase が必要）

---

## 4. QA 反映方針（Day 15 に直結するもの）

| QA | Day 15 への反映 |
|---|---|
| E-1 | 財務諸表の分類は Role URI / roleID キーワードで識別可能だが、v0.1.0 では JSON の concept 集合で直接分類する（Presentation Linkbase 不使用）。concept が PL/BS/CF いずれの JSON にも含まれなければ「未分類」として扱う |
| E-2 | 連結/個別は `ConsolidatedOrNonConsolidatedAxis` の dimension で判別。dimension なし = 連結（デフォルト）。`NonConsolidatedMember` がある = 個別。個別のみの企業（`WhetherConsolidatedFinancialStatementsArePreparedDEI` = false）は連結が存在しないため個別にフォールバック |
| E-3 | 全期間の Fact を保持し、`income_statement()` 呼び出し時に期間フィルタをかける。BS は `InstantPeriod`（period.instant が最新の日付）、PL/CF は `DurationPeriod`（period.end_date が最新の日付）で最新期間を判定 |
| E-7 | 主要勘定科目の concept 名辞書。PL/BS/CF の JSON データファイルの根拠として使用 |
| E-4 | EPS / BPS 等の 1 株当たり情報は `jpcrp_cor` 名前空間にあり、`jppfs_cor` の財務諸表とは別。v0.1.0 の PL/BS/CF には含めない |
| E-6 | 提出者独自の拡張科目は JSON に含まれないため、concept 集合マッチで「未分類」になる。`namespace_uri` に基づき `jppfs_cor` 系なら所属する Statement に末尾追加する |
| I-1 | Role URI と財務諸表の対応。v0.1.0 では使用しないが、v0.2.0 で Presentation Linkbase を実装する際の基盤情報 |

---

## 5. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/models/financial.py` | 追記 | `FinancialStatement`, `StatementType` を追加（純粋なデータ型のみ）**[FB2-C1]** |
| `src/edinet/xbrl/statements.py` | 新規実装 | `build_statements()` + `Statements` クラス + Fact 選択ロジック **[FB2-C1]** |
| `src/edinet/xbrl/data/__init__.py` | 新規作成 | 空ファイル（パッケージ化） |
| `src/edinet/xbrl/data/pl_jgaap.json` | 新規作成 | PL の concept 集合と並び順 |
| `src/edinet/xbrl/data/bs_jgaap.json` | 新規作成 | BS の concept 集合と並び順 |
| `src/edinet/xbrl/data/cf_jgaap.json` | 新規作成 | CF の concept 集合と並び順 |
| `src/edinet/xbrl/__init__.py` | 追記 | `build_statements` を追加エクスポート |
| `tests/test_xbrl/test_statements.py` | 新規作成 | Small/Unit + Medium/Integration テスト |
| `stubs/edinet/xbrl/statements.pyi` | 生成 | stubgen で自動生成 |
| `stubs/edinet/models/financial.pyi` | 再生成 | stubgen で自動生成 |

---

## 6. Fact 選択ルール（v0.1.0）

### 6.1 選択ルールの全体像

```
入力: tuple[LineItem, ...] （全 Fact、全期間、全 dimension）
出力: FinancialStatement （単一期間・単一連結区分の科目リスト）

ルール適用順:
  1. 科目分類:     JSON の concept 集合で PL/BS/CF に分類
  2. 数値フィルタ:  数値 Fact のみ（isinstance(item.value, Decimal)）
  3. nil 除外:     is_nil=True の Fact を除外（value=None）
  4. 期間フィルタ:  引数 period が None なら最新期間を自動選択
  5. 連結フィルタ:  引数 consolidated=True なら dimension なし（連結）を優先
  6. dimension:    上記連結軸以外の dimension がない Fact のみ（全社合計）
  7. 重複解決:     同一 concept で複数 Fact が残る場合は先頭を採用 + warnings.warn()
  8. 並び順:       JSON の order → JSON にない科目は末尾に出現順で追加
```

### 6.2 期間フィルタの詳細

```python
def _select_latest_period(
    items: Sequence[LineItem],
    statement_type: StatementType,
) -> InstantPeriod | DurationPeriod:
    """最新期間を自動選択する。

    BS は InstantPeriod（instant が最新の日付）を選択する。
    PL / CF は DurationPeriod（end_date が最新の日付）を選択する。

    同一日付の instant と duration が混在する場合、statement_type に
    合致する期間タイプのみを候補とする。
    """
```

- **BS**: `InstantPeriod` の `instant` 日付が最も新しいもの
- **PL / CF**: `DurationPeriod` の `end_date` が最も新しいもの。**end_date が同値の場合は最長期間（start_date が最も古い）を選択する** **[FB2-C2]**。四半期報告書では `DurationPeriod(2024-04-01, 2025-03-31)`（累計）と `DurationPeriod(2025-01-01, 2025-03-31)`（Q4 単独）が同一 end_date で共存するため、タイブレークが必要。ソートキーは `(end_date DESC, start_date ASC)` で先頭を採用する
- `period` 引数が明示的に渡された場合はそれを使用（フィルタの上書き）
- 前期（`Prior1Year*`）や前々期（`Prior2Year*`）の Fact は Context ID ではなく `period` の日付値で判別する（Context ID 命名規則に依存しない。CODESCOPE.md §2 CN-4）

**`_filter_by_period()` の仕様** **[FB-E1]**:

```python
def _filter_by_period(
    items: Sequence[LineItem],
    period: InstantPeriod | DurationPeriod,
    statement_type: StatementType,
) -> list[LineItem]:
    """指定期間の Fact のみを返す。

    期間の一致判定は == 比較（完全一致）で行う。
    _select_latest_period() で選ばれた period オブジェクトと
    == 比較することで、変則決算（15ヶ月決算等）でも
    start_date / end_date の両方が一致する Fact のみを選択する。

    BS: InstantPeriod 同士の == 比較。
    PL / CF: DurationPeriod 同士の == 比較（start_date と end_date の両方が一致）。

    注意: candidates に異なる periodType の Fact が混在していても、
    period 引数の型（InstantPeriod / DurationPeriod）と
    item.period の型が異なれば == は常に False を返すため、
    自然に除外される。例えば CF の candidates に BS 用の
    CashAndCashEquivalents（InstantPeriod）が含まれていても、
    CF の period は DurationPeriod なので型不一致で弾かれる。 **[FB3-C1]**
    """
```

注意: `stacklevel` の値は実装時に呼び出し深度に応じて調整する。計画書の値は目安。**[FB-E2]**

### 6.3 連結フィルタの詳細

```python
def _filter_consolidated_with_fallback(
    items: Sequence[LineItem],
    consolidated: bool,
) -> tuple[list[LineItem], bool]:
    """連結/個別フィルタ（フォールバック付き）。 [FB2-I2]

    consolidated=True の場合:
      1. dimensions が空（= 連結デフォルト）の Fact を優先
      2. 連結 Fact が 1 件も存在しない場合、個別にフォールバック

    consolidated=False の場合:
      NonConsolidatedMember を持つ Fact のみ

    Returns:
        (フィルタ済み LineItem リスト, 実際に適用された連結/個別)。
        フォールバックが発生した場合、2番目の値は引数と異なる。
    """
```

連結判定ロジック:
- `dimensions` が空 → 連結（XBRL のデフォルト Member）
- `dimensions` に `NonConsolidatedMember` を含む → 個別
- `dimensions` に連結軸以外（セグメント軸等）を含む → 全社合計ではない → 除外

```python
# 連結判定のヘルパー
_NONCONSOLIDATED_MEMBER_SUFFIX = "NonConsolidatedMember"

def _is_consolidated(item: LineItem) -> bool:
    """dimension なし = 連結（デフォルト）。"""
    return len(item.dimensions) == 0

def _is_non_consolidated(item: LineItem) -> bool:
    """NonConsolidatedMember を持つ = 個別。"""
    return any(
        dim.member.endswith(_NONCONSOLIDATED_MEMBER_SUFFIX)
        for dim in item.dimensions
    )

def _is_total(item: LineItem) -> bool:
    """連結軸のみ（セグメント軸なし）の全社合計。

    dimension なし（連結）か、連結軸の NonConsolidatedMember のみの場合に True。
    セグメント軸等が含まれる場合は False。
    """
    if len(item.dimensions) == 0:
        return True
    return (
        len(item.dimensions) == 1
        and _is_non_consolidated(item)
    )
```

注意: DimensionMember の `member` は Clark notation（`"{ns}NonConsolidatedMember"`）のため、`endswith()` でサフィックスマッチする。namespace URI の日付部分が変わっても動作する。

### 6.4 重複解決と警告

```python
def _resolve_duplicates(
    items: list[LineItem],
    concept: str,
) -> LineItem:
    """同一 concept で複数 Fact が残った場合の解決。

    先頭（元文書の出現順が早い方）を採用し、
    候補数と除外理由を含む warnings.warn() を出す。
    """
    if len(items) == 1:
        return items[0]

    adopted = items[0]
    warnings.warn(
        f"{concept}: {len(items)}候補中1件を採用"
        f"（context_id={adopted.context_id!r}）",
        EdinetWarning,
        stacklevel=4,
    )
    return adopted
```

### 6.5 非標準科目（拡張科目）の扱い

JSON の concept 集合に含まれない科目の扱い:

1. `namespace_uri` が `jppfs_cor` を含む → その Statement に属する可能性が高い。`periodType` で分類:
   - `DurationPeriod` → PL 候補（BS は instant のため除外される）
   - `InstantPeriod` → BS 候補
2. **提出者別タクソノミ** の科目のみ追加対象とする → `periodType` で PL/BS に振り分け **[FB2-I1]**
3. **標準 non-PFS 名前空間** (`jpcrp_cor`, `jpdei_cor`, `jpigp_cor` 等) の科目は除外する **[FB2-I1]**。例えば `jpcrp_cor:NumberOfEmployees`（従業員数）は duration 型の数値 Fact だが PL に混入すべきではない
4. 分類された非標準科目は JSON 定義の科目の末尾に、元文書の出現順（`item.order`）で追加する

```python
# 標準 non-PFS 名前空間のフラグメント [FB2-I1]
# これらの名前空間に属する科目は財務諸表の非標準科目として追加しない
# [FB5-P1] _cor サフィックス付きで照合することで、同一モジュール配下の
# 提出者拡張名前空間（例: jpcrp030000-asr_E12345-000）を誤除外しない。
# _cor なしだと "jpcrp" in "jpcrp030000-asr_..." → True で提出者拡張まで除外される。
#   jpcrp_cor   → 注記・開示府令
#   jpdei_cor   → DEI 書類情報
#   jpigp_cor   → IFRS/業種拡張（v0.2.0 で要見直し: §14-15）
#   jplvh_cor   → 大量保有報告書
#   jppfs_e_cor → EDINET 拡張 PFS（jppfs_cor とは別名前空間）
#   jpcti_cor   → 特定情報  [FB3-I7]
#   jpctl_cor   → 内部統制  [FB3-I7]
_STANDARD_NON_PFS_FRAGMENTS = ("jpcrp_cor", "jpdei_cor", "jpigp_cor", "jplvh_cor", "jppfs_e_cor", "jpcti_cor", "jpctl_cor")

def _is_extra_item_candidate(item: LineItem, known_concepts: set[str]) -> bool:
    """非標準科目として末尾追加する候補か判定。

    JSON の known_concepts に含まれず、かつ以下のいずれかの場合に True:
    - jppfs_cor 名前空間（標準 PFS の JSON 漏れ分）
    - 提出者別タクソノミ名前空間（標準 non-PFS でない）
    """
    if item.local_name in known_concepts:
        return False
    if "jppfs_cor" in item.namespace_uri:
        return True
    # 標準 non-PFS は除外
    return not any(frag in item.namespace_uri for frag in _STANDARD_NON_PFS_FRAGMENTS)
```

CF の非標準科目はより複雑（duration だが PL とは異なる）。v0.1.0 では JSON に含まれる CF concept のみを CF として扱い、JSON にない duration 科目は PL 末尾に追加する方針を基本とする。ただし、提出者別拡張科目には `*OpeCF` / `*InvCF` / `*FinCF` 等の CF を示すサフィックスが慣例的に使われるため（E-6.a.md で確認済み）、`_collect_extra_items()` でサフィックスヒューリスティックを適用し、明らかに CF に属する科目は CF に振り分ける。**[FB-A3]**

```python
# CF 拡張科目のサフィックスヒューリスティック [FB-A3]
_CF_SUFFIXES = ("OpeCF", "InvCF", "FinCF", "CFOperating", "CFInvesting", "CFFinancing")

def _looks_like_cf(local_name: str) -> bool:
    """local_name が CF 拡張科目のサフィックスパターンにマッチするか。"""
    return any(local_name.endswith(suffix) for suffix in _CF_SUFFIXES)
```

これにより CF 内訳科目（`DepreciationAndAmortizationOpeCF` 等）の PL 混入を大幅に削減する。完璧な分類は v0.2.0 の Role URI ベース分類で実現する。

**`_collect_extra_items()` の periodType 振り分け仕様** **[FB3-C2]**:

```python
def _collect_extra_items(
    numeric_items: list[LineItem],
    known_concepts: set[str],
    statement_type: StatementType,
) -> list[LineItem]:
    """JSON に含まれない非標準科目を収集する。

    numeric_items は期間フィルタ前の全 numeric Fact を受け取る。
    前期の Fact も候補に含まれるが、後段の _filter_by_period() で
    除外されるため最終結果には影響しない。 [FB5-1]

    statement_type に応じて periodType と CF サフィックスで振り分ける:
    - PL: DurationPeriod かつ _looks_like_cf() が False の候補
    - BS: InstantPeriod の候補
    - CF: _looks_like_cf() が True の候補（DurationPeriod 前提）

    PL と CF の排他性は _looks_like_cf() が担保する。
    CF suffix がある duration Fact → CF のみに追加。
    CF suffix がない duration Fact → PL のみに追加。
    これにより PL と CF の _build_single_statement() を独立に
    呼んでも同一 Fact が両方に現れることはない。 [FB3-C3]
    """
    result = []
    for item in numeric_items:
        if not _is_extra_item_candidate(item, known_concepts):
            continue
        if statement_type == StatementType.BALANCE_SHEET:
            if isinstance(item.period, InstantPeriod):
                result.append(item)
        elif statement_type == StatementType.CASH_FLOW_STATEMENT:
            if isinstance(item.period, DurationPeriod) and _looks_like_cf(item.local_name):
                result.append(item)
        else:  # INCOME_STATEMENT
            if isinstance(item.period, DurationPeriod) and not _looks_like_cf(item.local_name):
                result.append(item)
    return result
```

注意: CF suffix に該当しない提出者拡張の CF 科目（例: 独自の営業 CF 内訳で suffix なし）は PL 末尾に漏れる。これは v0.1.0 の既知の限界であり、v0.2.0 の Role URI ベース分類で解消される。

---

## 7. データモデル設計

### 7.1 StatementType

```python
import enum


class StatementType(enum.Enum):
    """財務諸表の種類。"""
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW_STATEMENT = "cash_flow_statement"
```

SS（株主資本等変動計算書）は v0.2.0 で追加する。2 次元テーブル構造のため definition linkbase が必要であり、v0.1.0 のスコープ外。

### 7.2 FinancialStatement

```python
@dataclass(frozen=True, slots=True, kw_only=True)  # [FB3-A3] kw_only=True で将来のフィールド追加が後方互換
class FinancialStatement:
    """組み立て済みの財務諸表。

    LineItem 群を選択ルール（期間・連結・dimension フィルタ）で
    絞り込み、JSON データファイルの order に従って並べたもの。

    ``items`` 内の各 ``LineItem.label_ja`` / ``LineItem.label_en`` は
    常に非 None（``LabelInfo`` 型）。TaxonomyResolver のフォールバック
    チェーン（T-7: 指定 role → 標準ラベル → 冗長ラベル → local_name）
    により保証される。 **[FB3-I4]**

    Attributes:
        statement_type: 財務諸表の種類（PL / BS / CF）。
        period: この財務諸表が対象とする期間。BS の場合は
            ``InstantPeriod``、PL / CF の場合は ``DurationPeriod``。
            該当する Fact が 0 件の場合は ``None``。 **[FB-C2, FB-B1]**
        items: 並び順が確定した LineItem のタプル。
        consolidated: 連結（True）か個別（False）か。
        entity_id: Entity ID（トレーサビリティ用）。1 filing 内で
            entity_id は統一されるため単一値。空の statement
            （``items=()``）では空文字列 ``""``。 **[FB4-5]**
        warnings_issued: 組み立て中に発行された警告メッセージ一覧。
    """
    statement_type: StatementType
    period: Period | None  # [FB-C2] 空の場合は None
    items: tuple[LineItem, ...]
    consolidated: bool
    entity_id: str
    warnings_issued: tuple[str, ...]

    def __getitem__(self, key: str) -> LineItem:
        """科目を日本語ラベル・英語ラベル・local_name で検索する。

        Args:
            key: 検索キー。以下の順で照合する:
                1. ``label_ja.text``（例: ``"売上高"``）
                2. ``label_en.text``（例: ``"Net sales"``）
                3. ``local_name``（例: ``"NetSales"``）

        Returns:
            最初にマッチした LineItem。同一ラベルの科目が
            複数存在する場合は、items 内で最初に見つかったものを返す。 **[FB-A2]**

        Raises:
            KeyError: マッチする科目が見つからない場合。
        """
        for item in self.items:
            if key in (item.label_ja.text, item.label_en.text, item.local_name):
                return item
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """科目の存在確認。``"売上高" in pl`` のように使う。"""
        try:
            self[key]
            return True
        except KeyError:
            return False

    def __len__(self) -> int:
        """科目数を返す。"""
        return len(self.items)

    def __iter__(self):
        """科目を順に返す。"""
        return iter(self.items)
```

### 7.3 Statements

**配置: `xbrl/statements.py`** **[FB2-C1]**

`Statements` はビジネスロジック（選択ルール適用）を持つビルダーであり、純粋なデータモデルではない。`models/financial.py` に置くと `income_statement()` メソッドが `xbrl/statements.py` の `_build_single_statement()` を呼ぶ際に **runtime 循環 import** が発生する。`TaxonomyResolver` が `xbrl/taxonomy.py` にある前例に倣い、ロジックを持つクラスは `xbrl/` に配置する。

依存方向（一方通行）:
```
xbrl/statements.py (Statements, build_statements)
    → models/financial.py (FinancialStatement, StatementType, LineItem)
    → xbrl/contexts.py (Period, DimensionMember)
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)  # [FB3-A3] kw_only=True で将来のフィールド追加が後方互換
class Statements:
    """財務諸表コンテナ。

    ``build_statements()`` 経由で構築すること。直接コンストラクトは非推奨。

    ``build_statements()`` の返り値。PL / BS / CF への
    アクセスメソッドを提供する。内部には全 LineItem を保持し、
    メソッド呼び出し時に選択ルールを適用する。

    JSON データファイルの読み込みはメソッド呼び出し時に行う
    （遅延読み込み）。これにより Statements のフィールドは
    ``_items`` のみとなり、frozen dataclass として自然な設計になる。 **[FB-A1]**

    Attributes:
        _items: 全 LineItem（全期間・全 dimension）。
    """
    _items: tuple[LineItem, ...]
    # [FB-A1] _concept_sets フィールドを削除。
    # JSON はメソッド内で _load_concept_definitions() を呼んで取得する。
    # JSON ファイルは合計 50 エントリ程度で読み込みコストは無視できる。
    # income_statement() しか呼ばないケースでは BS/CF の JSON を読まない利点もある。

    def income_statement(
        self,
        *,
        consolidated: bool = True,
        period: Period | None = None,
    ) -> FinancialStatement:
        """損益計算書を組み立てる。

        選択ルール（v0.1.0）:
          1. period: None なら最新期間を選択
          2. consolidated: True なら連結を優先、連結がなければ個別にフォールバック
          3. dimensions: dimension なし（全社合計）の Fact のみを採用
          4. 重複: 同一 concept で上記ルール適用後も複数 Fact が残る場合は
             warnings.warn() で警告
          5. 並び順: JSON データファイルの order に従う。JSON にない科目は末尾

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。None なら最新期間を自動選択。

        Returns:
            組み立て済みの損益計算書。
        """
        ...

    def balance_sheet(
        self,
        *,
        consolidated: bool = True,
        period: InstantPeriod | None = None,
    ) -> FinancialStatement:
        """貸借対照表を組み立てる。

        BS は InstantPeriod（時点）を使用する。
        選択ルールは income_statement() と同一。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象時点。None なら最新時点を自動選択。

        Returns:
            組み立て済みの貸借対照表。
        """
        ...

    def cash_flow_statement(
        self,
        *,
        consolidated: bool = True,
        period: DurationPeriod | None = None,
    ) -> FinancialStatement:
        """キャッシュフロー計算書を組み立てる。

        選択ルールは income_statement() と同一。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。None なら最新期間を自動選択。

        Returns:
            組み立て済みのキャッシュフロー計算書。
        """
        ...
```

### 7.4 設計判断

1. **`Statements` を返す理由**: `build_statements()` が `Statements` オブジェクトを返し、利用者が `stmts.income_statement()` を呼ぶ設計にする。理由: (a) 全 LineItem を保持したまま、呼び出し時に選択ルールを適用する「データは広く持ち、フィルタは遅く」の原則を実現できる。(b) v0.2.0 で `income_statement_compare()` 等のメソッドを追加する際、`Statements` に追加するだけで済む（`build_statements()` の返り値の変更不要）

2. **`FinancialStatement.items` を `tuple` にする理由**: frozen dataclass の一貫性。`list` にすると `FinancialStatement` 自体が hashable でなくなる。並び順が確定した後に変更する理由がない

3. **`__getitem__` の照合順序**: `label_ja.text` → `label_en.text` → `local_name` の順。日本語ラベルを最優先にする理由は、日本の EDINET ライブラリであり利用者の大半が日本語でアクセスするため。`concept`（Clark notation）ではなく `local_name` で照合する理由は、Clark notation は `"{http://...long...}NetSales"` のように長くなり実用的でないため。**[FB2-M1]** FALLBACK ラベル（T-7: 指定 role → 標準ラベル → local name）の場合、`label_ja.text` が `local_name` と同一値になるため、`pl["NetSales"]` は label_ja.text でも local_name でもマッチする（実害なし）

4. **`consolidated` フィールドを `FinancialStatement` に保持する理由**: 「この PL は連結か個別か」を明示する。`items[0].dimensions` を見ればわかるが、利用者がいちいち推論するのは負担。選択ルールの結果を明示的にメタデータとして残す

5. **`warnings_issued` を保持する理由**: `warnings.warn()` はグローバルな副作用であり、キャプチャが難しい。組み立て中に発生した警告を `FinancialStatement` に記録しておけば、後から「この PL の構築で何が起きたか」を確認できる。v0.2.0 の diagnostics モードの前段階

6. ~~**`Statements._concept_sets` を `dict` にする理由**~~: **[FB-A1] で廃止**。`_concept_sets` フィールドを削除し、メソッド内で `_load_concept_definitions()` を毎回呼ぶ方式に変更。JSON は小さいためコストは無視できる

7. **SS を v0.2.0 に先送りする理由**: SS は本質的に 2 次元テーブル（行=資本項目、列=期首残高/変動額/期末残高）であり、列方向の区別は dimension の Member で定義される（E-1c）。definition linkbase の dimension 情報が必要であり、v0.1.0 の JSON ベース分類では対応できない

8. **`Statements` を frozen dataclass にする理由**: `_items` は構築時に確定し変更されない。frozen にすることで不変性を保証する。メソッド（`income_statement()` 等）はフィールドを変更しない純粋な変換。**[FB-A1]** により `_concept_sets` が消えたことで、`_items` のみのシンプルな frozen dataclass になった

9. **`__contains__` を提供する理由**: `"売上高" in pl` のような Pythonic な存在確認を可能にする。edgartools の DX に合わせる

---

## 8. JSON データファイル設計

### 8.1 ファイル配置

```
src/edinet/xbrl/data/
  __init__.py          # 空ファイル（パッケージ化）
  pl_jgaap.json        # PL の concept 集合と並び順
  bs_jgaap.json        # BS の concept 集合と並び順
  cf_jgaap.json        # CF の concept 集合と並び順
```

### 8.2 JSON フォーマット

```json
[
  {
    "concept": "NetSales",
    "order": 1,
    "label_hint": "売上高"
  },
  {
    "concept": "CostOfSales",
    "order": 2,
    "label_hint": "売上原価"
  }
]
```

フィールド定義:
- `concept`: `local_name`（namespace prefix なし）。`jppfs_cor:` は全 concept で共通のため省略する。照合時は `LineItem.local_name` と比較する
- `order`: 表示順。1-indexed、連番。JSON 配列の順序とも一致させる（冗長だが可読性のため）
- `label_hint`: 日本語ラベルのヒント。コード内では使用しない（JSON の可読性と根拠記録のため）

### 8.3 PL の concept 集合（pl_jgaap.json）

E-7.a.md の主要勘定科目辞書に基づく。J-GAAP 一般事業会社の標準的な PL 構造:

```json
[
  {"concept": "NetSales", "order": 1, "label_hint": "売上高"},
  {"concept": "CostOfSales", "order": 2, "label_hint": "売上原価"},
  {"concept": "GrossProfit", "order": 3, "label_hint": "売上総利益"},
  {"concept": "SellingGeneralAndAdministrativeExpenses", "order": 4, "label_hint": "販売費及び一般管理費"},
  {"concept": "OperatingIncome", "order": 5, "label_hint": "営業利益又は営業損失（△）"},
  {"concept": "NonOperatingIncome", "order": 6, "label_hint": "営業外収益"},
  {"concept": "NonOperatingExpenses", "order": 7, "label_hint": "営業外費用"},
  {"concept": "OrdinaryIncome", "order": 8, "label_hint": "経常利益又は経常損失（△）"},
  {"concept": "ExtraordinaryIncome", "order": 9, "label_hint": "特別利益"},
  {"concept": "ExtraordinaryLoss", "order": 10, "label_hint": "特別損失"},
  {"concept": "IncomeBeforeIncomeTaxes", "order": 11, "label_hint": "税引前当期純利益又は税引前当期純損失（△）"},
  {"concept": "IncomeTaxes", "order": 12, "label_hint": "法人税、住民税及び事業税"},
  {"concept": "IncomeTaxesDeferred", "order": 13, "label_hint": "法人税等調整額"},
  {"concept": "ProfitLoss", "order": 14, "label_hint": "当期純利益又は当期純損失（△）"},
  {"concept": "ProfitLossAttributableToOwnersOfParent", "order": 15, "label_hint": "親会社株主に帰属する当期純利益又は親会社株主に帰属する当期純損失（△）"},
  {"concept": "ProfitLossAttributableToNonControllingInterests", "order": 16, "label_hint": "非支配株主に帰属する当期純利益又は非支配株主に帰属する当期純損失（△）"}
]
```

注意:
- `ProfitLoss`（個別用）と `ProfitLossAttributableToOwnersOfParent`（連結用）は排他的に出現する。連結 PL では後者のみ出現し、個別 PL では前者のみ出現する。両方を JSON に含めておき、存在しない方は自然にスキップされる
- 営業外収益・費用の内訳（受取利息、支払利息等）は企業によって大きく異なるため、小計レベルのみ JSON に含める。内訳項目は非標準科目として末尾に追加される

### 8.4 BS の concept 集合（bs_jgaap.json）

```json
[
  {"concept": "CurrentAssets", "order": 1, "label_hint": "流動資産"},
  {"concept": "NoncurrentAssets", "order": 2, "label_hint": "固定資産"},
  {"concept": "PropertyPlantAndEquipment", "order": 3, "label_hint": "有形固定資産"},
  {"concept": "IntangibleAssets", "order": 4, "label_hint": "無形固定資産"},
  {"concept": "InvestmentsAndOtherAssets", "order": 5, "label_hint": "投資その他の資産"},
  {"concept": "DeferredAssets", "order": 6, "label_hint": "繰延資産"},
  {"concept": "Assets", "order": 7, "label_hint": "資産合計"},
  {"concept": "CurrentLiabilities", "order": 8, "label_hint": "流動負債"},
  {"concept": "NoncurrentLiabilities", "order": 9, "label_hint": "固定負債"},
  {"concept": "Liabilities", "order": 10, "label_hint": "負債合計"},
  {"concept": "CapitalStock", "order": 11, "label_hint": "資本金"},
  {"concept": "CapitalSurplus", "order": 12, "label_hint": "資本剰余金"},
  {"concept": "RetainedEarnings", "order": 13, "label_hint": "利益剰余金"},
  {"concept": "TreasuryStock", "order": 14, "label_hint": "自己株式"},
  {"concept": "ShareholdersEquity", "order": 15, "label_hint": "株主資本合計"},
  {"concept": "ValuationAndTranslationAdjustments", "order": 16, "label_hint": "その他の包括利益累計額"},
  {"concept": "SubscriptionRightsToShares", "order": 17, "label_hint": "新株予約権"},
  {"concept": "NonControllingInterests", "order": 18, "label_hint": "非支配株主持分"},
  {"concept": "NetAssets", "order": 19, "label_hint": "純資産合計"},
  {"concept": "LiabilitiesAndNetAssets", "order": 20, "label_hint": "負債純資産合計"}
]
```

**[FB-D1]** 固定資産の内訳（有形/無形/投資その他）を追加。NoncurrentAssets（合計）だけでは BS としての実用性が低い。jppfs_cor に `PropertyPlantAndEquipment` / `IntangibleAssets` / `InvestmentsAndOtherAssets` が存在することを確認済み。order を 3-5 に挿入し、以降を繰り下げ。

注意: **[FB4-2]** PL の §8.3 注記と同様、BS も**小計レベルのみ** JSON に含める方針とする。`CashAndDeposits`（現金及び預金）、`NotesAndAccountsReceivableTrade`（受取手形及び売掛金）、`Goodwill`（のれん）等の内訳科目は企業によって大きく異なるため JSON には含めず、非標準科目として末尾に出現順で追加される。

### 8.5 CF の concept 集合（cf_jgaap.json）

```json
[
  {"concept": "NetCashProvidedByUsedInOperatingActivities", "order": 1, "label_hint": "営業活動によるキャッシュ・フロー"},
  {"concept": "NetCashProvidedByUsedInInvestmentActivities", "order": 2, "label_hint": "投資活動によるキャッシュ・フロー"},
  {"concept": "NetCashProvidedByUsedInFinancingActivities", "order": 3, "label_hint": "財務活動によるキャッシュ・フロー"},
  {"concept": "EffectOfExchangeRateChangeOnCashAndCashEquivalents", "order": 4, "label_hint": "現金及び現金同等物に係る換算差額"},
  {"concept": "NetIncreaseDecreaseInCashAndCashEquivalents", "order": 5, "label_hint": "現金及び現金同等物の増減額（△は減少）"},
  {"concept": "IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeInScopeOfConsolidation", "order": 6, "label_hint": "連結範囲の変動に伴う現金及び現金同等物の増減額"},
  {"concept": "CashAndCashEquivalentsAtBeginningOfPeriod", "order": 7, "label_hint": "現金及び現金同等物の期首残高"},
  {"concept": "CashAndCashEquivalentsAtEndOfPeriod", "order": 8, "label_hint": "現金及び現金同等物の期末残高"}
]
```

**[FB-D3]** 連結 CF で頻出する「連結範囲の変動に伴う現金及び現金同等物の増減額」を追加。多くの連結企業で出現する科目。

注意: CF の期首・期末残高は同一 concept `CashAndCashEquivalents` で period（instant の日付）で区別されるケースがある（E-7）。一方、タクソノミには `CashAndCashEquivalentsAtBeginningOfPeriod` / `CashAndCashEquivalentsAtEndOfPeriod` という別 concept もある。JSON には後者を入れ、前者は非標準科目として末尾に追加されることを許容する。

### 8.6 JSON 読み込み

```python
import functools
import importlib.resources
import json

@functools.cache  # [FB2-M3] 同一 StatementType の再読込を防止。コスト 1 行、デメリットなし
def _load_concept_definitions(statement_type: StatementType) -> list[dict]:
    """JSON データファイルから concept 定義を読み込む。

    Args:
        statement_type: 財務諸表の種類。

    Returns:
        concept 定義のリスト。各要素は
        ``{"concept": str, "order": int, "label_hint": str}``。
    """
    filename = {
        StatementType.INCOME_STATEMENT: "pl_jgaap.json",
        StatementType.BALANCE_SHEET: "bs_jgaap.json",
        StatementType.CASH_FLOW_STATEMENT: "cf_jgaap.json",
    }[statement_type]

    ref = importlib.resources.files("edinet.xbrl.data").joinpath(filename)
    with importlib.resources.as_file(ref) as path:
        return json.loads(path.read_text(encoding="utf-8"))
```

`importlib.resources` を使う理由: `__file__` ベースの相対パス解決は pip install 後のパッケージ構造で壊れるリスクがある。`importlib.resources` は Python 3.9+ の標準ライブラリであり、パッケージ内のデータファイル読み込みの推奨パターン。

---

## 9. `build_statements()` 関数設計

### 9.1 公開 I/F

```python
from __future__ import annotations

import json
import logging
import warnings
from collections.abc import Sequence
from decimal import Decimal

from edinet.exceptions import EdinetWarning
from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
# [FB2-C1] Statements は本モジュール内で定義する（循環 import 回避）
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod, Period

logger = logging.getLogger(__name__)

__all__ = ["build_statements", "Statements"]  # [FB2-C1] Statements も本モジュールからエクスポート


def build_statements(
    items: Sequence[LineItem],
) -> Statements:
    """LineItem 群から Statements コンテナを構築する。

    全 LineItem をそのまま保持し、``income_statement()`` 等の
    メソッド呼び出し時に選択ルールを適用する。

    Args:
        items: ``build_line_items()`` が返した LineItem のシーケンス。

    Returns:
        Statements コンテナ。
    """
    # [FB-A1] JSON の読み込みは Statements のメソッド内で行う（遅延読み込み）
    return Statements(_items=tuple(items))
```

### 9.2 内部実装方針

```python
def _build_single_statement(
    items: tuple[LineItem, ...],
    statement_type: StatementType,
    concept_defs: list[dict],
    *,
    consolidated: bool = True,
    period: Period | None = None,
) -> FinancialStatement:
    """単一の財務諸表を組み立てる（内部関数）。

    §6 の選択ルールを順に適用する。
    """
    issued_warnings: list[str] = []

    # 1. concept 集合のセットを構築
    known_concepts = {d["concept"] for d in concept_defs}

    # 2. 数値 Fact のみ（テキスト、nil 除外）
    numeric_items = [
        item for item in items
        if isinstance(item.value, Decimal) and not item.is_nil
    ]

    # 3. 科目分類 — JSON の concept 集合に含まれる LineItem を抽出
    #    + 非標準科目（JSON にないが jppfs_cor 系の同 periodType）を候補に含める
    classified = [
        item for item in numeric_items
        if item.local_name in known_concepts
    ]
    # 非標準科目: known_concepts にないが periodType が合致する jppfs_cor 系
    extra_items = _collect_extra_items(
        numeric_items, known_concepts, statement_type
    )

    # 4. 期間フィルタ
    candidates = classified + extra_items
    # [FB-C2] 空の場合は period=None。date.min は意味的に不適切
    if not candidates:
        return FinancialStatement(
            statement_type=statement_type,
            period=period,  # 引数が None ならそのまま None
            items=(),
            consolidated=consolidated,
            entity_id="",
            warnings_issued=(),
        )

    if period is None:
        period = _select_latest_period(candidates, statement_type)
    period_filtered = _filter_by_period(candidates, period, statement_type)

    # 5. 連結フィルタ（フォールバック付き）
    consolidated_filtered, actual_consolidated = _filter_consolidated_with_fallback(
        period_filtered, consolidated
    )
    if actual_consolidated != consolidated:
        msg = (
            f"{statement_type.value}: 連結データなし、個別にフォールバック"
        )
        issued_warnings.append(msg)
        warnings.warn(msg, EdinetWarning, stacklevel=3)

    # 6. dimension フィルタ（全社合計のみ）
    total_items = [
        item for item in consolidated_filtered
        if _is_total(item)
    ]

    # 7. 重複解決
    # [FB2-M4] キーは local_name。理論上 namespace_uri が異なる同名 local_name が
    # 存在しうるが、v0.1.0 は jppfs_cor 中心のため実害は極めて低い。
    # v0.2.0 で concept（Clark notation）をキーにすることを検討する。
    concept_to_items: dict[str, list[LineItem]] = {}
    for item in total_items:
        concept_to_items.setdefault(item.local_name, []).append(item)

    selected: list[LineItem] = []
    for concept_name, concept_items in concept_to_items.items():
        if len(concept_items) > 1:
            msg = (
                f"{concept_name}: {len(concept_items)}候補中1件を採用"
                f"（context_id={concept_items[0].context_id!r}）"
            )
            issued_warnings.append(msg)
            warnings.warn(msg, EdinetWarning, stacklevel=3)
        selected.append(concept_items[0])

    # 8. 並び順: JSON order → 非標準科目は末尾
    concept_order = {d["concept"]: d["order"] for d in concept_defs}
    max_order = max(concept_order.values()) if concept_order else 0

    def sort_key(item: LineItem) -> tuple[int, int]:
        json_order = concept_order.get(item.local_name)
        if json_order is not None:
            return (json_order, 0)
        return (max_order + 1, item.order)

    selected.sort(key=sort_key)

    entity_id = selected[0].entity_id if selected else ""

    logger.info(
        "%s を組み立て: %d 科目（候補 %d 件から選択）",
        statement_type.value, len(selected), len(items),
    )

    return FinancialStatement(
        statement_type=statement_type,
        period=period,
        items=tuple(selected),
        consolidated=actual_consolidated,
        entity_id=entity_id,
        warnings_issued=tuple(issued_warnings),
    )
```

### 9.3 エラー処理方針

statements.py は parser.py / contexts.py / facts.py と異なり、**best-effort 方針** を採る。理由:
- 上流（parser → contexts → facts）は「XBRL 文書の解釈」であり、1 箇所の失敗は全体の信頼性を毀損する（fail-fast が正しい）
- statements.py は「解釈済みデータの選択と組み立て」であり、一部の科目で問題があっても他の科目は正しく組み立てられる
- 利用者にとって「PL が 0 科目で返る」より「10 科目中 8 科目が取れて 2 科目で警告が出る」方が有用

| 状況 | 処理 |
|---|---|
| JSON データファイルが見つからない | `EdinetParseError`（設定ミスのため fail-fast） |
| JSON のフォーマットが不正 | `EdinetParseError`（同上） |
| 該当する concept が 0 件 | 空の `FinancialStatement`（`items=()`）を返す。エラーにしない |
| 連結データがない | 個別にフォールバック + `warnings.warn()` |
| 同一 concept で重複 | 先頭を採用 + `warnings.warn()` |
| 期間データがない | 空の `FinancialStatement` を返す |

ロガー規約:
- `logger.info()` で組み立て結果のサマリー（「PL を組み立て: N 科目」）を出力する
- `warnings.warn()` はユーザー向けの診断情報（重複、フォールバック等）

---

## 10. テスト計画

### 10.1 テスト用フィクスチャの方針

**テスト内で in-memory LineItem を生成する方式** を主とする。理由:
- `build_statements()` / `Statements.income_statement()` の入力は `LineItem` のシーケンスであり、XML ファイルではない
- LineItem を直接構築することでテストの意図が明確になる
- 既存フィクスチャへの影響がない

### 10.2 テスト用ヘルパー

```python
"""test_statements.py — build_statements() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.exceptions import EdinetWarning
from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
)
from edinet.financial.statements import build_statements, Statements  # [FB2-C1]
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

# テスト用名前空間
_NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    """テスト用 LabelInfo を構築するヘルパー。"""
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _make_pl_item(
    *,
    local_name: str = "NetSales",
    value: Decimal = Decimal("1000000000"),
    period: DurationPeriod | None = None,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    context_id: str = "CurrentYearDuration",
    label_ja: str = "売上高",
    label_en: str = "Net sales",
) -> LineItem:
    """テスト用 PL LineItem を構築するヘルパー。"""
    if period is None:
        period = DurationPeriod(
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
    return LineItem(
        concept=f"{{{_NS_JPPFS}}}{local_name}",
        namespace_uri=_NS_JPPFS,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=False,
        source_line=1,
        order=order,
    )


def _make_bs_item(
    *,
    local_name: str = "Assets",
    value: Decimal = Decimal("5000000000"),
    period: InstantPeriod | None = None,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    context_id: str = "CurrentYearInstant",
    label_ja: str = "資産合計",   # [FB2-I3] local_name に連動するよう引数化
    label_en: str = "Total assets",  # [FB2-I3]
) -> LineItem:
    """テスト用 BS LineItem を構築するヘルパー。"""
    if period is None:
        period = InstantPeriod(instant=date(2025, 3, 31))
    return LineItem(
        concept=f"{{{_NS_JPPFS}}}{local_name}",
        namespace_uri=_NS_JPPFS,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),   # [FB2-I3]
        label_en=_make_label(label_en, "en"),    # [FB2-I3]
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=False,
        source_line=1,
        order=order,
    )
```

### 10.3 テストケース（P0: 必須）

**Statements 構築**

1. `test_build_statements_returns_statements` — `build_statements()` が `Statements` を返すこと
2. `test_income_statement_returns_financial_statement` — `stmts.income_statement()` が `FinancialStatement` を返すこと。`statement_type` が `StatementType.INCOME_STATEMENT` であること

**Fact 選択ルール**

3. `test_pl_selects_numeric_facts_only` — テキスト Fact（`value: str`）と nil Fact（`value: None`）が除外されること
4. `test_pl_selects_latest_period` — 当期（`end_date=2025-03-31`）と前期（`end_date=2024-03-31`）の Fact を渡し、当期のみが選択されること
5. `test_pl_selects_consolidated_by_default` — dimension なし（連結）と `NonConsolidatedMember`（個別）の Fact を渡し、連結のみが選択されること
6. `test_pl_fallback_to_non_consolidated` — 連結 Fact が 0 件で個別のみの場合、個別にフォールバックし `EdinetWarning` が出ること
7. `test_pl_excludes_dimension_facts` — セグメント軸（`OperatingSegmentsAxis`）を持つ Fact が除外されること
8. `test_pl_duplicate_warns` — 同一 concept で 2 件の Fact が残った場合、`EdinetWarning` が出て先頭が採用されること

**科目分類と並び順**

9. `test_pl_items_ordered_by_json` — `NetSales`（order=1）→ `OperatingIncome`（order=5）→ `OrdinaryIncome`（order=8）の順で並ぶこと
10. `test_pl_extra_items_appended_at_end` — JSON にない `jppfs_cor` 系 concept が末尾に追加されること。順序は `item.order`（元文書出現順）による

**FinancialStatement API**

11. `test_getitem_by_label_ja` — `pl["売上高"]` で `NetSales` の LineItem が返ること
12. `test_getitem_by_label_en` — `pl["Net sales"]` で同上
13. `test_getitem_by_local_name` — `pl["NetSales"]` で同上
14. `test_getitem_not_found_raises_key_error` — `pl["存在しない科目"]` で `KeyError` が raise されること
15. `test_contains` — `"売上高" in pl` が `True`、`"存在しない" in pl` が `False` であること

**BS / CF**

16. `test_balance_sheet_uses_instant_period` — BS が `InstantPeriod` を使用すること
17. `test_cash_flow_uses_duration_period` — CF が `DurationPeriod` を使用すること

**JSON データファイルの健全性** **[FB-C1]** P1-6 から P0 に昇格

18. `test_json_concepts_are_valid` — 以下を検証するバリデーションテスト:
    - 各 JSON の concept が重複なし
    - order が 1-indexed 連番
    - PL/BS/CF 間で concept の重複なし（同一 concept が複数の statement に属していないこと）

**CF サフィックスヒューリスティック** **[FB2-I4]**

19. `test_cf_suffix_heuristic` — `local_name` が `"DepreciationAndAmortizationOpeCF"` の duration Fact が CF に分類され、PL に混入しないこと。FB-A3 の設計判断を直接検証

**期間タイブレーク** **[FB4-3]**

20. `test_pl_selects_cumulative_over_quarterly` — `DurationPeriod(2024-04-01, 2025-03-31)`（累計）と `DurationPeriod(2025-01-01, 2025-03-31)`（Q4 単独）が同一 `end_date` で共存する場合、累計（最長）が選択されること。§6.2 の `(end_date DESC, start_date ASC)` タイブレークを直接検証。FB2-C2 で Critical として追加した仕様のため P0

### 10.4 テストケース（P1: 推奨）

1. `test_pl_explicit_period_argument` — `period` 引数を明示的に渡した場合、自動選択ではなく指定期間の Fact が使われること
2. `test_pl_non_consolidated_explicit` — `consolidated=False` を渡した場合、個別 Fact のみが選択されること
3. `test_empty_items_returns_empty_statement` — 空の `items` を渡した場合、空の `FinancialStatement`（`items=()`, `period=None`）が返ること **[FB-C2]**
4. `test_warnings_issued_recorded` — `FinancialStatement.warnings_issued` に警告メッセージが記録されていること
5. `test_json_loading` — `_load_concept_definitions()` が PL/BS/CF の JSON を正しく読み込めること
6. ~~`test_json_concepts_are_valid`~~ — **[FB-C1] P0-18 に昇格**
7. `test_len_and_iter` — `len(pl)` が `pl.items` の長さと一致し、`list(pl)` が `list(pl.items)` と一致すること
8. `test_integration_with_full_pipeline` — `simple_pl.xbrl` → `parse_xbrl_facts` → `structure_contexts` → `build_line_items` → `build_statements` のフルパイプライン。`stmts.income_statement()` が空でない `FinancialStatement` を返すこと。`@pytest.mark.medium` + `@pytest.mark.integration`。**[FB-C3]** Day 15 の成否を決める最重要テスト。少なくとも `NetSales` / `OperatingIncome` / `OrdinaryIncome` が含まれることを検証。**[FB3-I6]** スコープは PL のみ。`simple_pl.xbrl` には CF 用 Fact が含まれないため、BS/CF のフルパイプライン統合テストは Day 17 の実 filing E2E テストでカバーする

### 10.5 `pytest.mark.parametrize` の活用

以下のテストは `@pytest.mark.parametrize` で統合してテスト関数の増殖を防ぐ:

- P0-11 + P0-12 + P0-13 → `test_getitem_by_key` にまとめ、`(key, expected_local_name)` で parametrize:
  ```python
  @pytest.mark.parametrize("key,expected", [
      ("売上高", "NetSales"),
      ("Net sales", "NetSales"),
      ("NetSales", "NetSales"),
  ])
  def test_getitem_by_key(key, expected, pl_fixture):
      assert pl_fixture[key].local_name == expected
  ```
- P0-16 + P0-17 → **個別に残す**。Context の構築（`InstantPeriod` vs `DurationPeriod`）が異なるため

### 10.6 marker 方針

- `small` + `unit`: in-memory LineItem を使うテスト（P0 の大半、P1 の大半）
- `medium` + `integration`: `simple_pl.xbrl` fixture を使ったフルパイプライン結合テスト（P1-8）

---

## 11. 依存関係の確認

```
[FB2-C1] 修正後の依存構造:

xbrl/statements.py          →  models/financial.py  →  xbrl/contexts.py
  (Statements,                    (LineItem,               (Period,
   build_statements,               FinancialStatement,      DimensionMember)
   _build_single_statement)        StatementType)
        ↓
  xbrl/data/*.json
        ↓
  xbrl/__init__.py (エクスポート)

新規依存: statements.py → {models.financial, contexts, data/*.json}
既存モジュールへの変更: models/financial.py へのクラス追加 + __init__.py へのエクスポート追加
```

- `statements.py` は `models/financial.py`（LineItem, FinancialStatement, StatementType）と `contexts.py`（Period, DimensionMember, DurationPeriod, InstantPeriod）に依存する **[FB2-C1]**
- `Statements` は `xbrl/statements.py` に配置。`_build_single_statement()` と同一モジュール内のため循環 import が発生しない **[FB2-C1]**
- `models/financial.py` は `contexts.py`（Period, DimensionMember）と `taxonomy.py`（LabelInfo）に依存する（既存の LineItem の依存 + 新規の FinancialStatement の依存）。`xbrl/statements.py` への依存は一切持たない
- 循環依存は発生しない（依存方向は一方通行: parser → contexts → facts → statements → models）
- `statements.py` は `parser.py` / `taxonomy.py` / `facts.py` に直接依存しない。入力は `LineItem` のシーケンスのみ

---

## 12. 当日の作業手順（チェックリスト）

### Phase 1: JSON データファイル（~20 分）

1. `src/edinet/xbrl/data/` ディレクトリを作成
2. `src/edinet/xbrl/data/__init__.py` を空ファイルで作成
3. `src/edinet/xbrl/data/pl_jgaap.json` を作成（§8.3）
4. `src/edinet/xbrl/data/bs_jgaap.json` を作成（§8.4）
5. `src/edinet/xbrl/data/cf_jgaap.json` を作成（§8.5）
6. JSON の整合性を手動確認: concept の重複なし、order が連番、配列の順序と order が一致

### Phase 2: データモデル（~20 分）— Phase 3 の前提 **[FB3-M8]**

1. `src/edinet/models/financial.py` に `StatementType` enum を追加
2. `FinancialStatement` frozen dataclass を追加（`kw_only=True`、`__getitem__`, `__contains__`, `__len__`, `__iter__` 含む）**[FB3-A3]**
3. `__all__` に `FinancialStatement`, `StatementType` を追加（`Statements` は `xbrl/statements.py` に配置 **[FB2-C1]**）
4. `uv run ruff check src/edinet/models/financial.py` で lint pass を確認

### Phase 3: statements.py 実装（~40 分）— Phase 2 完了が前提 **[FB3-M8]**

1. `_load_concept_definitions()` を実装（§8.6）
2. 連結判定ヘルパー群を実装（`_is_consolidated`, `_is_non_consolidated`, `_is_total`）（§6.3）
3. `_select_latest_period()` を実装（§6.2）
4. `_filter_by_period()` を実装
5. `_filter_consolidated_with_fallback()` を実装
6. `_collect_extra_items()` を実装（§6.5）。CF サフィックスヒューリスティック（`_looks_like_cf()`）を含む **[FB-A3]**
7. `_build_single_statement()` を実装（§9.2）
8. `Statements` frozen dataclass を **`xbrl/statements.py` 内に** 定義（`income_statement()`, `balance_sheet()`, `cash_flow_statement()` メソッド含む）**[FB2-C1]**
9. `Statements.income_statement()` 等から `_build_single_statement()` を呼ぶ（同一モジュール内なので循環 import なし）
10. `build_statements()` を実装（§9.1）
11. `__all__ = ["build_statements", "Statements"]` を定義
12. `src/edinet/xbrl/__init__.py` に `from edinet.financial.statements import build_statements, Statements` を追加 **[FB2-C1]**
13. `uv run ruff check src/edinet/xbrl/statements.py` で lint pass を確認

### Phase 4: テスト（~30 分）

1. `tests/test_xbrl/test_statements.py` を作成
2. テスト用ヘルパー（`_make_label`, `_make_pl_item`, `_make_bs_item`）を定義（§10.2）
3. P0 テスト（§10.3、17 件）を実装
4. `uv run pytest tests/test_xbrl/test_statements.py -v` で全件 pass を確認
5. P1 テスト（§10.4、8 件）を実装
6. `uv run pytest tests/test_xbrl/test_statements.py -v` で全件 pass を確認

### Phase 5: 検証（~20 分）

1. `uv run pytest tests/test_xbrl/test_parser.py` — 既存テスト回帰なし
2. `uv run pytest tests/test_xbrl/test_contexts.py` — 既存テスト回帰なし
3. `uv run pytest tests/test_xbrl/test_taxonomy.py` — 既存テスト回帰なし
4. `uv run pytest tests/test_xbrl/test_facts.py` — 既存テスト回帰なし
5. `uv run pytest` — 全テスト回帰なし
6. `uv run ruff check src tests` — 警告なし
7. `uv run stubgen src/edinet --include-docstrings -o stubs` — `.pyi` 生成
8. 生成された `stubs/edinet/xbrl/statements.pyi` と `stubs/edinet/models/financial.pyi` の diff を確認
9. 手動スモーク: 実 filing 1 件で全パイプラインを実行し、PL の科目一覧が正しく出力されることを確認

```python
# 手動スモークのイメージ
from decimal import Decimal

from edinet import documents
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.facts import build_line_items
from edinet.financial.statements import build_statements

filing = documents("2025-06-25", doc_type="120")[0]
path, xbrl_bytes = filing.fetch()
parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)
resolver = TaxonomyResolver(r"C:\Users\nezow\Downloads\ALL_20251101")

items = build_line_items(parsed.facts, ctx_map, resolver)
stmts = build_statements(items)

# PL
pl = stmts.income_statement()
print(f"=== PL ({pl.statement_type.value}) ===")
print(f"期間: {pl.period}")
print(f"連結: {pl.consolidated}")
print(f"科目数: {len(pl)}")
for item in pl:
    val = f"{item.value:>20,}" if isinstance(item.value, Decimal) else repr(item.value)
    print(f"  {item.label_ja.text}: {val}")
if pl.warnings_issued:
    print(f"警告: {pl.warnings_issued}")

# BS
bs = stmts.balance_sheet()
print(f"\n=== BS ({bs.statement_type.value}) ===")
print(f"科目数: {len(bs)}")
for item in bs:
    val = f"{item.value:>20,}" if isinstance(item.value, Decimal) else repr(item.value)
    print(f"  {item.label_ja.text}: {val}")

# CF
cf = stmts.cash_flow_statement()
print(f"\n=== CF ({cf.statement_type.value}) ===")
print(f"科目数: {len(cf)}")
for item in cf:
    val = f"{item.value:>20,}" if isinstance(item.value, Decimal) else repr(item.value)
    print(f"  {item.label_ja.text}: {val}")

# __getitem__ 確認
print(f"\n売上高: {pl['売上高'].value:,}")
```

---

## 13. 受け入れ基準（Done の定義）

- `build_statements()` が `LineItem` 群を受け取り `Statements` を返す
- `stmts.income_statement()` / `balance_sheet()` / `cash_flow_statement()` が `FinancialStatement` を返す
- PL の科目が JSON の `order` に従って並んでいる
- JSON にない科目が末尾に出現順で追加されている
- 数値 Fact のみが選択されている（テキスト・nil は除外）
- 最新期間の Fact が自動選択されている
- 連結 Fact が優先され、連結なしの場合に個別へフォールバックする
- dimension 付き（セグメント等）の Fact が除外されている
- 重複 Fact 発生時に候補数を含む `EdinetWarning` が出る
- `pl["売上高"]` / `pl["Net sales"]` / `pl["NetSales"]` で LineItem にアクセスできる
- `"売上高" in pl` が `True` を返す
- P0 テスト（§10.3、20 件）が全て pass **[FB-C1]** JSON バリデーション P0 昇格 +1、**[FB2-I4]** CF ヒューリスティック +1、**[FB4-3]** 期間タイブレーク +1
- P1 テスト（§10.4、7 件）は同日完了が望ましい。特に P1-8（統合テスト）は堅牢性に重要 **[FB-C3]**
- 既存テストスイートが回帰なし
- ruff で警告なし
- `.pyi` が生成され FinancialStatement / Statements / StatementType の型情報が反映されている
- 手動スモークで実 filing 1 件の PL/BS/CF が出力されること

---

## 14. 設計判断の記録（§7.4 からの再掲 + 追加）

1. **`build_statements()` を関数として提供する理由**: parser.py の `parse_xbrl_facts()`、contexts.py の `structure_contexts()`、facts.py の `build_line_items()` に倣い、ステートレスな関数として提供する。`Statements` クラスの構築は `build_statements()` に委ね、利用者がクラスを直接コンストラクトする必要をなくす

2. **JSON の `concept` を `local_name`（prefix なし）にする理由**: v0.1.0 は J-GAAP 一般事業会社のみが対象であり、PL/BS/CF の concept は全て `jppfs_cor` 名前空間に属する。prefix を含めると JSON の可読性が落ち、namespace バージョン（日付部分）の変化にも対応が必要になる。`local_name` で照合することで、namespace バージョンに依存しない設計になる

3. **`_is_total()` を dimension なし OR 連結軸のみに限定する理由**: 「全社合計」の Fact を取得するのが v0.1.0 の目的。セグメント軸や地域軸を持つ Fact は部分値であり、PL の合計値としては不適切。連結軸は「連結/個別」の区分であり、全社合計には影響しない

4. **best-effort 方針の理由**: §9.3 に記載。上流（parser → facts）の fail-fast とは異なり、statements は「選択と組み立て」であり、一部の科目で問題があっても他は正しく返せる。空の PL を返すより部分的な PL を返す方がユーザーにとって有用

5. **`Statements` のメソッド内で選択ルールを適用する理由**: PLAN.LIVING.md の「データは広く持ち、フィルタは遅く」の原則に従う。`build_statements()` 時点では全 LineItem を保持し、`income_statement()` 呼び出し時にフィルタする。これにより v0.2.0 で `income_statement(consolidated=False)` や `income_statement(period=prior_year)` を呼ぶだけで異なるビューが取得できる

6. **CF の非標準科目の振り分け**: ~~§6.5 に記載。PL 末尾に追加する~~ **[FB-A3]** `*OpeCF` / `*InvCF` / `*FinCF` 等のサフィックスを持つ科目は CF に振り分けるヒューリスティックを追加。E-6.a.md で提出者別拡張科目にこのパターンが実在することを確認済み。サフィックスに該当しない duration 科目は従来通り PL 末尾に追加。v0.2.0 で Role URI ベースの分類を導入すれば完全な分類が可能になる

7. **[FB-A1] `Statements` の `_concept_sets` フィールド廃止の理由**: frozen dataclass のフィールドに `_ prefix` の内部用 dict を持つのは設計として不自然。JSON は合計 50 エントリ程度で毎回読み込んでもコストは無視できる。メソッド内で `_load_concept_definitions()` を呼ぶ方式にすることで、Statements のフィールドは `_items` のみになり、frozen dataclass として自然な設計になる。副次的に、`income_statement()` しか呼ばないケースでは BS/CF の JSON を読まない利点もある

8. **[FB-C2] 空 FinancialStatement の period を None にする理由**: `date.min` (0001-01-01) は意味的に不適切なセンチネル値であり、利用者が見ると混乱する。`period: Period | None` にすることで、空の FinancialStatement は `period=None, items=()` で「何もなかった」ことが自明になる。LineItem.period は非 None なので既存の型安全性に影響しない

9. **[FB2-C1] `Statements` を `xbrl/statements.py` に配置する理由**: `Statements` はビジネスロジック（選択ルール適用）を持つビルダーであり、純粋なデータモデルではない。`models/financial.py` に置くと `income_statement()` → `_build_single_statement()` の呼び出しで runtime 循環 import が発生する。`TaxonomyResolver` が `xbrl/taxonomy.py` にある前例に倣い、ロジックを持つクラスは `xbrl/` に配置する

10. **[FB2-C2] end_date 同値タイブレークの理由**: 四半期報告書では累計期間（2024-04-01〜2025-03-31）と当四半期（2025-01-01〜2025-03-31）が同一 end_date で共存する。PL で欲しいのは累計なので、同値時は最長期間（start_date が最も古い）を選択する。v0.1.0 のスコープに半期報告書（160）も含まれるため、現実的に踏みうるケース

11. **[FB2-I1] extra items の対象を限定する理由**: `jpcrp_cor` 名前空間の数値 Fact（例: NumberOfEmployees）が PL に混入するのを防ぐ。extra items の対象は (a) `jppfs_cor` 系（標準 PFS の JSON 漏れ分）と (b) 提出者別タクソノミ（`/{edinetCode}/` パターン等）に限定する

12. **[FB3-A3] `kw_only=True` を採用する理由**: frozen dataclass へのフィールド追加は positional args の位置が変わるため後方互換を壊す。`kw_only=True` ならフィールド追加が additive change になる。`FinancialStatement`（6 フィールド）と `Statements`（1 フィールド）に適用。既存の `LineItem`（15 フィールド）は v0.1.0 リリース前のタイミングで揃える（テストヘルパーは既に全て keyword 引数で構築しており影響なし）

13. **[FB3-B1] `_collect_extra_items()` は v0.1.0 限定のワークアラウンド**: v0.2.0 で Presentation Linkbase（pres_tree）を導入すれば、各 Role URI に属する concept を直接取得できるため、`_collect_extra_items()` は不要になる。v0.2.0 での差し替え点は `_load_concept_definitions()` の1箇所のみ（`concept_defs` の取得元を JSON → pres_tree に変更するだけ）。`concept_defs` の型 `list[dict]` は v0.2.0 で必要に応じて変更する

14. **[FB3-A1] `_load_concept_definitions()` は v0.2.0 の会計基準切り替えポイント**: IFRS 対応時、`_load_concept_definitions()` のディスパッチロジック（`StatementType → ファイル名`）に会計基準軸を追加する必要がある（例: `pl_jgaap.json` → `pl_ifrs.json`）。`build_statements()` のシグネチャに `accounting_standard` パラメータを追加するのは additive change のため後方互換

15. **[FB3-B2] `_STANDARD_NON_PFS_FRAGMENTS` は v0.2.0 で見直しが必要**: IFRS 対応時、`ifrs-full` 名前空間の Fact は `jppfs_cor` ではないため extra items ロジック全体が動作しない。また `jpigp` には業種固有の PFS 科目が含まれる可能性がある（`sector/banking` 等）。v0.2.0 で「ホワイトリスト方式（PFS として認める名前空間を列挙）」への切り替えを検討する

16. **[FB3-C2f] `_is_consolidated()` / `_is_non_consolidated()` は将来 dimensions モジュールに移動**: v0.2.0 で `dimensions/consolidated` モジュール（FEATURES.md）を実装する際、statements.py 内のプライベート関数を共通モジュールに移動する。v0.1.0 では statements.py 内で十分

17. **[FB3-M9] JSON の `order` フィールドを明示する理由**: 配列インデックスで代替可能だが、明示的な `order` フィールドにより (a) JSON の可読性が向上し (b) 将来の挿入・並べ替え時にインデックスずれを気にせず済む。P0-18 で order の連番性を検証するため冗長だが有用

18. **[FB3-F1] JSON フォーマットの将来拡張性**: IFRS 対応時、concept フィールドの `local_name` 照合だけでは不足する可能性がある（`ifrs-full:Revenue` は namespace が異なる）。将来 `namespace_hint` フィールドを追加して照合ロジックを拡張できるよう、JSON の構造は additive に設計している

---

## 15. Day 16 への引き継ぎ

Day 15 完了後、Day 16 以降は以下を前提に着手する:

1. `build_statements()` → `Statements` が全 LineItem を保持する
2. `stmts.income_statement()` / `balance_sheet()` / `cash_flow_statement()` が選択ルール適用済みの `FinancialStatement` を返す
3. Day 16 は `FinancialStatement.to_dataframe()` と Rich 表示を実装する:
   - `pandas` / `rich` は遅延 import（`import edinet` 時点では読み込まない）
   - `pandas` なしでも `import edinet` が成功することをテスト
4. Day 17 で `Filing.xbrl()` メソッドを実装し、E2E 統合を完了する:
   - ZIP 展開 → パース → ラベル解決 → Statement 組み立てを繋ぐ
   - `Company("7203").latest("有価証券報告書").xbrl().statements.income_statement()` が動く
5. Day 15 で確認すべき事項:
   - PL の科目数が妥当か（トヨタの有報で 10-30 程度が期待値。JSON の標準科目 + 非標準科目の末尾追加）
   - BS / CF も同様に妥当な科目数か
   - 連結フォールバックが正しく動作するか（個別のみの企業で確認）
   - 重複警告の内容が診断に役立つか
6. **[FB3-D1]** v0.2.0 で `standards/normalize` を実装する際、現在の `__getitem__` は変更しない。IFRS の「収益」≠ J-GAAP の「売上高」問題は `pl.get_normalized("revenue")` 的な新メソッド追加で解決する（`__getitem__` 変更は後方互換を壊す）
7. **[FB3-E1]** `_make_pl_item()` / `_make_bs_item()` は `test_statements.py` 内のローカルヘルパー。Day 16 以降で `test_compare.py` / `test_dimensions.py` 等から再利用が必要になった時点で `tests/conftest.py` または `tests/factories.py` に移動する
8. **[FB3-E2]** テスト fixture の追加方針: `tests/fixtures/xbrl_fragments/` の下に `jgaap/` / `ifrs/` / `sector/` を切ることを将来検討。v0.1.0 では現状の flat 構造で十分

---

## 16. 実行コマンド（Day 15）

```bash
# Phase 2: データモデル
uv run ruff check src/edinet/models/financial.py

# Phase 3: statements.py
uv run ruff check src/edinet/xbrl/statements.py

# Phase 4: テスト
uv run pytest tests/test_xbrl/test_statements.py -v

# Phase 5: 検証
uv run pytest tests/test_xbrl/test_parser.py
uv run pytest tests/test_xbrl/test_contexts.py
uv run pytest tests/test_xbrl/test_taxonomy.py
uv run pytest tests/test_xbrl/test_facts.py
uv run pytest
uv run ruff check src tests
uv run stubgen src/edinet --include-docstrings -o stubs
```

---

## 17. フィードバック変更履歴

2026-02-25 のレビューで反映したフィードバック一覧。各変更箇所に `[FB-XX]` タグを付与し追跡可能にしている。

| タグ | カテゴリ | 変更内容 | 影響箇所 |
|------|---------|---------|---------|
| **FB-A1** | 設計 | `Statements._concept_sets` フィールドを削除。メソッド内で `_load_concept_definitions()` を毎回呼ぶ方式に変更。frozen dataclass として自然な設計に | §7.3, §7.4-6, §7.4-8, §9.1, §14 |
| **FB-A2** | 設計 | `__getitem__` の docstring に「同一ラベルの科目が複数ある場合は最初にマッチしたものを返す」を明記 | §7.2 |
| **FB-A3** | 設計 | CF 拡張科目のサフィックスヒューリスティック追加。`*OpeCF` / `*InvCF` / `*FinCF` 等のパターンで CF に振り分け | §6.5, §14 |
| **FB-B1** | モデル | `FinancialStatement.period` の docstring に「BS は InstantPeriod、PL/CF は DurationPeriod」を明記 | §7.2 |
| **FB-C1** | テスト | JSON バリデーションテストを P1-6 → P0-18 に昇格。PL/BS/CF 間の concept 重複なし検証も追加 | §10.3, §10.4, §13 |
| **FB-C2** | テスト/モデル | 空 FinancialStatement の period を `date.min` → `None` に変更。`period: Period \| None` 型に | §7.2, §9.2, §10.4-3, §14 |
| **FB-C3** | テスト | Integration テスト（P1-8）に NetSales / OperatingIncome / OrdinaryIncome の存在検証を追加 | §10.4-8, §13 |
| **FB-D1** | データ | BS JSON に固定資産内訳 3 concept 追加（PropertyPlantAndEquipment, IntangibleAssets, InvestmentsAndOtherAssets）。order を繰り下げ | §8.4 |
| **FB-D3** | データ | CF JSON に連結範囲変動 concept 追加（IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeInScopeOfConsolidation） | §8.5 |
| **FB-E1** | 仕様 | `_filter_by_period()` の仕様を明記。`==` 比較（完全一致）で期間フィルタ | §6.2 |
| **FB-E2** | 実装 | `stacklevel` の値は実装時に調整する旨を明記 | §6.2 |

### Round 2 フィードバック（FB2-XX）

| タグ | カテゴリ | 変更内容 | 影響箇所 |
|------|---------|---------|---------|
| **FB2-C1** | Critical/設計 | `Statements` を `models/financial.py` → `xbrl/statements.py` に移動。runtime 循環 import を回避。`models/financial.py` には純粋なデータ型（`StatementType`, `FinancialStatement`）のみ残す | §1, §5, §7.3, §9.1, §11, §12 Phase2/3, §14 |
| **FB2-C2** | Critical/仕様 | `_select_latest_period` に end_date 同値タイブレーク仕様を追加。`(end_date DESC, start_date ASC)` で最長期間を優先。四半期報告書の累計 vs Q4 単独問題を回避 | §6.2 |
| **FB2-I1** | Important/設計 | `_collect_extra_items` の対象を `jppfs_cor` + 提出者別タクソノミに限定。`jpcrp_cor` 等の標準 non-PFS を除外（NumberOfEmployees 等の PL 混入防止） | §6.5 |
| **FB2-I2** | Important/仕様 | `_filter_consolidated` → `_filter_consolidated_with_fallback` に統一。返り値型 `tuple[list[LineItem], bool]` を明記 | §6.3 |
| **FB2-I3** | Important/テスト | `_make_bs_item` のラベル (`label_ja`, `label_en`) を引数化。`local_name` に連動させる | §10.2 |
| **FB2-I4** | Important/テスト | CF サフィックスヒューリスティックの P0 テスト（P0-19）を追加。FB-A3 の設計判断を直接検証 | §10.3, §13 |
| **FB2-M1** | Minor/文書 | `__getitem__` の FALLBACK ラベル時の挙動を docstring に明記 | §7.4-3 |
| **FB2-M3** | Minor/実装 | `_load_concept_definitions` に `@functools.cache` を追加。コスト 1 行、デメリットなし | §8.6 |
| **FB2-M4** | Minor/文書 | 重複解決キーに `local_name` を使う理由と v0.2.0 での改善方針を注記 | §9.2 |

### Round 3 フィードバック（FB3-XX）

| タグ | カテゴリ | 変更内容 | 影響箇所 |
|------|---------|---------|---------|
| **FB3-C1** | Critical/文書 | `_filter_by_period()` docstring に「異なる periodType の Fact は型不一致で自然に除外される」旨を明記。BS instant Fact が CF に混入しない理由の説明 | §6.2 |
| **FB3-C2** | Critical/仕様 | `_collect_extra_items()` の完全な擬似コードを追加。`statement_type` に応じた periodType + CF suffix 振り分けロジックを明示 | §6.5 |
| **FB3-C3** | Critical/文書 | PL と CF の extra items 排他性が `_looks_like_cf()` で担保されることを docstring に明記 | §6.5 (`_collect_extra_items` docstring 内) |
| **FB3-I4** | Important/文書 | `FinancialStatement` docstring に `label_ja` / `label_en` が常に非 None（TaxonomyResolver フォールバック保証）である旨を明記 | §7.2 |
| **FB3-I6** | Important/テスト | P1-8 統合テストのスコープを PL のみに限定。BS/CF の統合テストは Day 17 の実 filing E2E でカバーする旨を明記 | §10.4-8 |
| **FB3-I7** | Important/データ | `_STANDARD_NON_PFS_FRAGMENTS` に `jpcti`（特定情報）/ `jpctl`（内部統制）を防御的に追加 | §6.5 |
| **FB3-M8** | Minor/文書 | §12 Phase 2/3 に Phase 間依存を明記（「Phase 3 の前提」「Phase 2 完了が前提」） | §12 |
| **FB3-A3** | 将来/設計 | `FinancialStatement` / `Statements` に `kw_only=True` を追加。将来のフィールド追加を後方互換にする | §7.2, §7.3, §12, §14-12 |
| **FB3-A1** | 将来/記録 | `_load_concept_definitions()` が v0.2.0 の会計基準切り替えポイントであることを §14 に記録 | §14-14 |
| **FB3-B1** | 将来/記録 | `_collect_extra_items()` が v0.1.0 限定ワークアラウンドであることを §14 に記録。v0.2.0 で pres_tree に差し替え | §14-13 |
| **FB3-B2** | 将来/記録 | `_STANDARD_NON_PFS_FRAGMENTS` の IFRS 対応時の見直し必要性を §14 に記録 | §14-15 |
| **FB3-C2f** | 将来/記録 | 連結判定ヘルパーの将来の dimensions モジュール移動を §14 に記録 | §14-16 |
| **FB3-D1** | 将来/記録 | `__getitem__` と standards/normalize の衝突回避方針を §15 に記録 | §15-6 |
| **FB3-E1** | 将来/記録 | テストヘルパーの共有化方針を §15 に記録 | §15-7 |
| **FB3-E2** | 将来/記録 | テスト fixture ディレクトリ構造の将来方針を §15 に記録 | §15-8 |
| **FB3-F1** | 将来/記録 | JSON フォーマットの IFRS 拡張性（`namespace_hint` フィールド追加可能性）を §14 に記録 | §14-18 |
| **FB3-M9** | Minor/記録 | JSON `order` フィールドの冗長性に関する設計判断を §14 に記録 | §14-17 |

### Round 4 フィードバック（FB4-XX）

| タグ | カテゴリ | 変更内容 | 影響箇所 |
|------|---------|---------|---------|
| **FB4-2** | Important/文書 | BS JSON に「小計レベルのみ含め、内訳は非標準として末尾追加」の方針を PL と同様に明記 | §8.4 |
| **FB4-3** | Important/テスト | 四半期累計 vs Q4 単独の期間タイブレークテスト（P0-20）を追加。FB2-C2 の仕様を直接検証 | §10.3, §13 |
| **FB4-4** | Minor/文書 | `_STANDARD_NON_PFS_FRAGMENTS` の各フラグメントが対応する名前空間をコメントで明記。`jppfs_e` が `jppfs_cor` を誤除外しないことも注記 | §6.5 |
| **FB4-5** | Minor/文書 | `FinancialStatement.entity_id` の docstring に空 statement で空文字列になることを明記 | §7.2 |

### 不採用のフィードバック

| 元の指摘 | 不採用理由 |
|---------|----------|
| B-2. `_concept_sets` の型を厳密化 | FB-A1 でフィールド自体が消えたため不要 |
| D-2. PL に InterestIncome / InterestExpense 追加 | v0.1.0 では小計レベルで十分。拡張科目として末尾に追加される |
| E-3. JSON 遅延読み込み | FB-A1 でメソッド内読み込みにしたため自動的に実現 |
| M-2. simple_pl.xbrl の存在確認 | `tests/fixtures/xbrl_fragments/simple_pl.xbrl` に存在確認済み |
| R3-5. entity_id の複数混在チェック | EDINET 仕様上 1 filing 内で entity_id は統一（A-2.2）。YAGNI |
| R3-10. `_items` の `_` prefix 変更 | 現状維持で十分。docstring に `build_statements()` 経由構築を明記済み |
| R3-A2. StatementType に COMPREHENSIVE_INCOME 追加 | Enum に未使用の値を定義するとユーザー混乱。additive change なので v0.2.0 で追加すれば十分 |
| R3-G1. `_build_single_statement()` の重複走査最適化 | v0.1.0 では問題にならない（数百〜数千件、O(n)×3）。v0.2.0 で必要なら最適化 |
| R4-1. `__getitem__` の O(n) 最適化 | v0.1.0 で ~20 科目、v0.2.0 でも数百科目。`@cached_property` は `slots=True` と共存不可。必要になった時点で対応すれば十分 |
| R4-6. `_items` アンダースコアの強制制限 | R3-10 と同一指摘。docstring 注記で十分。`__post_init__` バリデーション等は過剰 |

### Round 5 フィードバック（FB5-XX）

| タグ | カテゴリ | 変更内容 | 影響箇所 |
|------|---------|---------|---------|
| **FB5-1** | Critical/文書 | `_collect_extra_items()` docstring に「期間フィルタ前の全 items を受け取る。前期 Fact は後段 `_filter_by_period()` で除外」を明記 | §6.5 |

| 元の指摘 | 不採用理由 |
|---------|----------|
| R5-2. JSON concept 数が少なすぎる | 指摘者自身が「まず出荷し手動スモーク後に拡充が現実的」と結論。JSON 追加は additive change で blocker ではない |
| R5-3. deny-list 方式のリスク | FB3-B2（§14-15）、FB3-I7、FB4-4 で既に対応済み |
| R5-4. 冗長ラベル問題 | T-7 のフォールバック順が標準ラベル優先。冗長ラベルが入る場合でも `pl["NetSales"]`（local_name）で常にアクセス可能 |
| R5-5. `_items` アンダースコア（3回目） | R3-10, R4-6 と同一。結論変更なし |

### Round 6 フィードバック（FB6-XX）

| タグ | カテゴリ | 変更内容 | 影響箇所 |
|------|---------|---------|---------|
| **FB6-1** | Minor/文書 | `_collect_extra_items()` docstring に「`known_concepts` は当該 StatementType の JSON のみから構築される。PL/BS/CF 間の concept 非重複は P0-18 で保証」を明記 | §6.5, statements.py |
| **FB6-2** | Minor/文書 | `FinancialStatement.__repr__()` / `.get()` を実装時に追加した旨を §17 に記録。Day15.md §7.2 の擬似コードにはなかったが DX 向上のため追加 | §17 |

| 元の指摘 | 不採用理由 |
|---------|----------|
| R6-C1. `_is_consolidated()` のリネーム/docstring 修正 | docstring に「（他の軸を含まない場合のみ）」と既記載。プライベート関数であり将来移動時（FB3-C2f）に再検討すれば十分 |
| R6-C2. `known_concepts` を全 StatementType の union にする | FB6-1 の docstring 注記で対応。P0-18 が cross-statement 重複を検証済み |
| R6-I1. `_filter_by_period()` の未使用引数削除 | Day15.md §6.2 に将来拡張用と記録済み。削除のリターンが低い |
| R6-I5. `_is_consolidated()` に ConsolidatedMember 明示チェック追加 | EDINET タクソノミ上、連結軸の Member は ConsolidatedMember / NonConsolidatedMember の 2 種のみ。起こりえないケースへの防御は YAGNI |
| R6-P2. InstantPeriod の現金残高を CF に含める | Day15.md §8.5 で明示的に許容済みの既知の限界。v0.2.0 の Role URI ベース分類で解消 |
| R6-P3. Statements stub に `_items` フィールドがない | stubgen が `_` prefix を省略する仕様。stub は自動生成を継続するため手動修正は無意味 |

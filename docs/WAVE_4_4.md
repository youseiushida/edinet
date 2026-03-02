# Wave 4 / Part 4 — CanonicalKey 定数化

# エージェントが守るべきルール

あなたは Wave 4 / Part 4 を担当するエージェントです。
担当機能: canonical_key の文字列リテラルを StrEnum 定数に置換し、typo を防止する

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/sector/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他 Part が担当するファイルの構造を変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/standards/canonical_keys.py` (**新規作成**)
   - `src/edinet/xbrl/standards/jgaap.py` (既存・変更 — `canonical_key=` 文字列の置換のみ)
   - `src/edinet/xbrl/standards/ifrs.py` (既存・変更 — `canonical_key=` 文字列の置換のみ)
   - `src/edinet/xbrl/sector/banking.py` (既存・変更 — `general_equivalent=` 文字列の置換のみ)
   - `src/edinet/xbrl/sector/insurance.py` (既存・変更 — 同上)
   - `src/edinet/xbrl/sector/construction.py` (既存・変更 — 同上)
   - `src/edinet/xbrl/sector/railway.py` (既存・変更 — 同上)
   - `src/edinet/xbrl/sector/securities.py` (既存・変更 — 同上)
   - `tests/test_xbrl/test_canonical_keys.py` (**新規作成**)
   - `tests/test_xbrl/test_standards_jgaap.py` (既存・変更 — CK 参照テスト)
   - `tests/test_xbrl/test_standards_ifrs.py` (既存・変更 — CK 参照テスト)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **フィールド追加・削除を行わないこと**
   - `ConceptMapping` / `IFRSConceptMapping` / `SectorConceptMapping` のフィールド構成は変更しない
   - 文字列リテラルを `CK.*` 定数に **置換するのみ**

4. **`stubgen` を実行しないこと**
   統合タスクで一括実行する。

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/` 配下の既存ファイルを変更してはならない

## 推奨事項

6. **置換は機械的に行うこと**
   - `canonical_key="revenue"` → `canonical_key=CK.REVENUE` のように、値の意味は一切変えない
   - `general_equivalent="revenue"` → `general_equivalent=CK.REVENUE` も同様

7. **テストファイルの命名規則**
   - `tests/test_xbrl/test_canonical_keys.py` を新規作成（CK StrEnum 自体のテスト）

8. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# PART 4 — CanonicalKey 定数化

## 0. 位置づけ

### WAVE_4.md との対応

WAVE_4.md §Part 4:

> canonical_key の文字列リテラルを StrEnum 定数化し、typo を防止する。
> `CK.REVENUE == "revenue"` が True（`.value` 不要）。

### 依存先

| 依存先 | 用途 | 種類 |
|--------|------|------|
| Part 2 (完了済み) | jgaap.py / ifrs.py がスリム化済み。`canonical_key` フィールドが残存 | 前提 |
| Part 3 (完了済み) | sector/ がスリム化済み。`general_equivalent` フィールドが `canonical_key` 値を参照 | 前提 |
| Part 1a/1b (完了済み) | concept_sets + normalize パイプライン接続済み | 読取専用 |

### 他 Part とのファイル衝突

- Part 2 は jgaap.py / ifrs.py のフィールド構成を変更済み。本 Part は **文字列リテラルの定数置換のみ** → **構造的衝突なし**
- Part 3 は sector/ のフィールド構成を変更済み。本 Part は `general_equivalent=` の文字列置換のみ → **構造的衝突なし**
- normalize.py は変更対象外 → **衝突なし**

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| WAVE_4.md §4.1-4.5 | 高 | Part 4 の設計方針 |
| NOW.md §Q11 | 高 | canonical_key の typo 防止の意思決定 |

---

## 1. 背景知識

### 1.1 問題

現状、`canonical_key` は全て文字列リテラルで管理されている:

```python
# jgaap.py
ConceptMapping(concept="NetSales", canonical_key="revenue", ...)
# ifrs.py
IFRSConceptMapping(concept="RevenueIFRS", canonical_key="revenue", ...)
# sector/banking.py
SectorConceptMapping(..., general_equivalent="revenue")
```

同一の `"revenue"` が 3 箇所に散在しており、typo しても静かに壊れる。IDE のオートコンプリートも効かない。

### 1.2 解決策

`StrEnum` 定数に集約し、typo を `AttributeError` で即座に検出する:

```python
# canonical_keys.py
class CK(StrEnum):
    REVENUE = "revenue"

# jgaap.py
ConceptMapping(concept="NetSales", canonical_key=CK.REVENUE, ...)
# ifrs.py
IFRSConceptMapping(concept="RevenueIFRS", canonical_key=CK.REVENUE, ...)
# sector/banking.py
SectorConceptMapping(..., general_equivalent=CK.REVENUE)
```

### 1.3 StrEnum の特性

Python 3.11+ の `StrEnum` を使用（本プロジェクトは Python >= 3.12）:

- `CK.REVENUE == "revenue"` → `True`（`.value` 不要）
- `isinstance(CK.REVENUE, str)` → `True`（dict キーにそのまま使える）
- `CK("revenue")` → `CK.REVENUE`（逆引き可能）
- `list(CK)` → 全定数列挙可能
- IDE のオートコンプリートが効く
- JSON シリアライズ時に自動的に文字列化される

### 1.4 現在の canonical_key データ（2026-03-02 実測値）

| カテゴリ | 件数 | 内訳 |
|---------|:----:|------|
| J-GAAP canonical_key | 83 | PL:16, BS:24, CF:35, KPI:8 |
| IFRS canonical_key | 55 | PL:15, BS:19, CF:16, KPI/CI:5 |
| J-GAAP ∩ IFRS (共有) | 45 | 両基準共通のキー |
| J-GAAP のみ | 38 | J-GAAP 固有のキー |
| IFRS のみ | 10 | IFRS 固有のキー |
| **合計ユニーク数** | **93** | CK 定数の数 |
| Sector general_equivalent | 18 | 全て J-GAAP canonical_key のサブセット |

### 1.5 J-GAAP のみのキー (38 個)

`allowance_doubtful_change_cf`, `bps`, `cash_and_deposits`, `consolidation_scope_change_cash`, `deferred_assets`, `dps`, `employees`, `equity_ratio`, `extraordinary_income`, `extraordinary_loss`, `fx_loss_gain_cf`, `goodwill_amortization_cf`, `income_taxes_deferred`, `interest_dividend_income_cf`, `interest_expense_cf`, `investments_and_other`, `liabilities_and_net_assets`, `loans_collected_cf`, `loans_paid_cf`, `non_operating_expenses`, `non_operating_income`, `oci_accumulated`, `ordinary_income`, `other_financing_cf`, `other_investing_cf`, `other_operating_cf`, `per`, `ppe_sale_loss_gain_cf`, `proceeds_bonds_cf`, `proceeds_investment_securities_cf`, `proceeds_long_term_loans_cf`, `proceeds_ppe_sale_cf`, `purchase_investment_securities_cf`, `purchase_treasury_stock_cf`, `redemption_bonds_cf`, `roe`, `shareholders_equity`, `stock_options`

### 1.6 IFRS のみのキー (10 個)

`cash_and_equivalents`, `comprehensive_income`, `comprehensive_income_minority`, `comprehensive_income_parent`, `equity_method_income_ifrs`, `equity_parent`, `finance_costs`, `finance_income`, `other_expenses_ifrs`, `other_income_ifrs`

### 1.7 Sector general_equivalent の全値 (18 個)

`cost_of_sales`, `extraordinary_income`, `extraordinary_loss`, `financing_cf`, `gross_profit`, `income_before_tax`, `investing_cf`, `net_assets`, `net_income`, `net_income_minority`, `net_income_parent`, `operating_cf`, `operating_income`, `ordinary_income`, `revenue`, `sga_expenses`, `total_assets`, `total_liabilities`

→ 全て J-GAAP canonical_key のサブセット（確認済み）。CK に全て含まれる。

---

## 2. ゴール

1. `src/edinet/xbrl/standards/canonical_keys.py` を新規作成し、`CK` StrEnum に 93 個の定数を PL / BS / CF / KPI セクション分けで定義する
2. `jgaap.py` の全 83 個の `canonical_key=` 文字列を `CK.*` に置換する
3. `ifrs.py` の全 55 個の `canonical_key=` 文字列を `CK.*` に置換する
4. 5 業種モジュールの `general_equivalent=` 文字列（18 種、延べ 32 箇所）を `CK.*` に置換する
5. テストで `CK.*` と文字列値の一致・整合性を検証する

### 非ゴール（スコープ外）

- sector の `sector_key=` 文字列の定数化 → 業種ローカルキーであり基準横断ではないため対象外
- normalize.py の変更 → `get_canonical_key()` 等は文字列を受け取り文字列を返す。`CK` を import する必要なし
- `CK` 定数の docstring/コメントに日本語ラベルを付加 → TaxonomyResolver の責務

### 非機能要件

- 全テスト（1,261+ 件）がパス
- `uv run ruff check` クリーン
- 既存の公開 API の振る舞いに影響なし（`CK.REVENUE == "revenue"` のため透過的）

---

## 3. 設計

### 3.1 `canonical_keys.py` の構成

```python
"""会計基準横断の正規化キー定数。

jgaap.py, ifrs.py, sector/*.py が共有する canonical_key の
文字列リテラルを定数化し、typo を防止する。

``CK`` は ``StrEnum`` であり、``CK.REVENUE == "revenue"`` が True。
``isinstance(CK.REVENUE, str)`` も True のため、文字列を期待する
dict キーやフィールド値にそのまま使用できる。

典型的な使用例::

    from edinet.financial.standards.canonical_keys import CK

    # マッピング定義
    ConceptMapping(concept="NetSales", canonical_key=CK.REVENUE, ...)

    # 比較（StrEnum なので .value 不要）
    assert CK.REVENUE == "revenue"

    # 逆引き
    assert CK("revenue") is CK.REVENUE
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["CK"]


class CK(StrEnum):
    """CanonicalKey 定数群。

    StrEnum を使用。``CK.REVENUE == "revenue"`` が True（.value 不要）。
    ``isinstance(CK.REVENUE, str)`` も True のため dict[str, ...] にそのまま使える。

    命名規則: 大文字スネークケース。値は小文字スネークケースの文字列。

    セクション:
        PL — 損益計算書の科目
        BS — 貸借対照表の科目
        CF — キャッシュフロー計算書の科目
        KPI — 主要経営指標
        CI — 包括利益計算書（IFRS）
    """

    # --- PL (損益計算書) ---
    REVENUE = "revenue"
    COST_OF_SALES = "cost_of_sales"
    GROSS_PROFIT = "gross_profit"
    SGA_EXPENSES = "sga_expenses"
    OPERATING_INCOME = "operating_income"
    NON_OPERATING_INCOME = "non_operating_income"          # J-GAAP
    NON_OPERATING_EXPENSES = "non_operating_expenses"      # J-GAAP
    ORDINARY_INCOME = "ordinary_income"                    # J-GAAP
    EXTRAORDINARY_INCOME = "extraordinary_income"          # J-GAAP
    EXTRAORDINARY_LOSS = "extraordinary_loss"              # J-GAAP
    OTHER_INCOME_IFRS = "other_income_ifrs"                # IFRS
    OTHER_EXPENSES_IFRS = "other_expenses_ifrs"            # IFRS
    FINANCE_INCOME = "finance_income"                      # IFRS
    FINANCE_COSTS = "finance_costs"                        # IFRS
    EQUITY_METHOD_INCOME_IFRS = "equity_method_income_ifrs"  # IFRS
    INCOME_BEFORE_TAX = "income_before_tax"
    INCOME_TAXES = "income_taxes"
    INCOME_TAXES_DEFERRED = "income_taxes_deferred"        # J-GAAP
    NET_INCOME = "net_income"
    NET_INCOME_PARENT = "net_income_parent"
    NET_INCOME_MINORITY = "net_income_minority"

    # --- BS (貸借対照表) ---
    CASH_AND_DEPOSITS = "cash_and_deposits"                # J-GAAP
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"          # IFRS
    TRADE_RECEIVABLES = "trade_receivables"
    INVENTORIES = "inventories"
    CURRENT_ASSETS = "current_assets"
    NONCURRENT_ASSETS = "noncurrent_assets"
    PPE = "ppe"
    INTANGIBLE_ASSETS = "intangible_assets"
    INVESTMENTS_AND_OTHER = "investments_and_other"        # J-GAAP
    DEFERRED_ASSETS = "deferred_assets"                    # J-GAAP
    TOTAL_ASSETS = "total_assets"
    TRADE_PAYABLES = "trade_payables"
    CURRENT_LIABILITIES = "current_liabilities"
    NONCURRENT_LIABILITIES = "noncurrent_liabilities"
    TOTAL_LIABILITIES = "total_liabilities"
    CAPITAL_STOCK = "capital_stock"
    CAPITAL_SURPLUS = "capital_surplus"
    RETAINED_EARNINGS = "retained_earnings"
    TREASURY_STOCK = "treasury_stock"
    SHAREHOLDERS_EQUITY = "shareholders_equity"            # J-GAAP
    OCI_ACCUMULATED = "oci_accumulated"                    # J-GAAP
    STOCK_OPTIONS = "stock_options"                        # J-GAAP
    EQUITY_PARENT = "equity_parent"                        # IFRS
    MINORITY_INTERESTS = "minority_interests"
    NET_ASSETS = "net_assets"
    LIABILITIES_AND_NET_ASSETS = "liabilities_and_net_assets"  # J-GAAP

    # --- CF (キャッシュフロー計算書) ---
    DEPRECIATION_CF = "depreciation_cf"
    IMPAIRMENT_LOSS_CF = "impairment_loss_cf"
    GOODWILL_AMORTIZATION_CF = "goodwill_amortization_cf"  # J-GAAP
    ALLOWANCE_DOUBTFUL_CHANGE_CF = "allowance_doubtful_change_cf"  # J-GAAP
    INTEREST_DIVIDEND_INCOME_CF = "interest_dividend_income_cf"    # J-GAAP
    INTEREST_EXPENSE_CF = "interest_expense_cf"            # J-GAAP
    FX_LOSS_GAIN_CF = "fx_loss_gain_cf"                    # J-GAAP
    EQUITY_METHOD_CF = "equity_method_cf"
    PPE_SALE_LOSS_GAIN_CF = "ppe_sale_loss_gain_cf"        # J-GAAP
    TRADE_RECEIVABLES_CHANGE_CF = "trade_receivables_change_cf"
    INVENTORIES_CHANGE_CF = "inventories_change_cf"
    TRADE_PAYABLES_CHANGE_CF = "trade_payables_change_cf"
    OTHER_OPERATING_CF = "other_operating_cf"              # J-GAAP
    SUBTOTAL_OPERATING_CF = "subtotal_operating_cf"
    INCOME_TAXES_PAID_CF = "income_taxes_paid_cf"
    OPERATING_CF = "operating_cf"
    PURCHASE_PPE_CF = "purchase_ppe_cf"
    PROCEEDS_PPE_SALE_CF = "proceeds_ppe_sale_cf"          # J-GAAP
    PURCHASE_INVESTMENT_SECURITIES_CF = "purchase_investment_securities_cf"  # J-GAAP
    PROCEEDS_INVESTMENT_SECURITIES_CF = "proceeds_investment_securities_cf"  # J-GAAP
    LOANS_PAID_CF = "loans_paid_cf"                        # J-GAAP
    LOANS_COLLECTED_CF = "loans_collected_cf"              # J-GAAP
    OTHER_INVESTING_CF = "other_investing_cf"              # J-GAAP
    INVESTING_CF = "investing_cf"
    PROCEEDS_LONG_TERM_LOANS_CF = "proceeds_long_term_loans_cf"  # J-GAAP
    REPAYMENT_LONG_TERM_LOANS_CF = "repayment_long_term_loans_cf"
    PROCEEDS_BONDS_CF = "proceeds_bonds_cf"                # J-GAAP
    REDEMPTION_BONDS_CF = "redemption_bonds_cf"            # J-GAAP
    PURCHASE_TREASURY_STOCK_CF = "purchase_treasury_stock_cf"  # J-GAAP
    DIVIDENDS_PAID_CF = "dividends_paid_cf"
    OTHER_FINANCING_CF = "other_financing_cf"              # J-GAAP
    FINANCING_CF = "financing_cf"
    FX_EFFECT_ON_CASH = "fx_effect_on_cash"
    NET_CHANGE_IN_CASH = "net_change_in_cash"
    CONSOLIDATION_SCOPE_CHANGE_CASH = "consolidation_scope_change_cash"  # J-GAAP

    # --- KPI (主要経営指標) ---
    EPS = "eps"
    EPS_DILUTED = "eps_diluted"
    BPS = "bps"                                            # J-GAAP
    DPS = "dps"                                            # J-GAAP
    EQUITY_RATIO = "equity_ratio"                          # J-GAAP
    ROE = "roe"                                            # J-GAAP
    PER = "per"                                            # J-GAAP
    EMPLOYEES = "employees"                                # J-GAAP

    # --- CI (包括利益 — IFRS) ---
    COMPREHENSIVE_INCOME = "comprehensive_income"          # IFRS (is_ifrs_specific=True)
    COMPREHENSIVE_INCOME_PARENT = "comprehensive_income_parent"  # IFRS (is_ifrs_specific=False — J-GAAP にも概念が存在しうる)
    COMPREHENSIVE_INCOME_MINORITY = "comprehensive_income_minority"  # IFRS (is_ifrs_specific=True)
```

### 3.2 置換パターン

#### jgaap.py

```python
# Before
from edinet.financial.standards.canonical_keys import CK  # ← 追加

ConceptMapping(concept="NetSales", canonical_key="revenue", ...)
# After
ConceptMapping(concept="NetSales", canonical_key=CK.REVENUE, ...)
```

83 マッピング × 1 箇所（`canonical_key=`） = **83 箇所** の置換。

#### ifrs.py

```python
# Before
from edinet.financial.standards.canonical_keys import CK  # ← 追加

IFRSConceptMapping(concept="RevenueIFRS", canonical_key="revenue", ...)
# After
IFRSConceptMapping(concept="RevenueIFRS", canonical_key=CK.REVENUE, ...)
```

55 マッピング × 1 箇所（`canonical_key=`） = **55 箇所** の置換。

加えて、`jgaap_concept=` フィールドの文字列は **置換しない**（これは concept 名であり canonical_key ではない）。

#### sector/*.py

`general_equivalent=` のみ置換。`sector_key=` は **置換しない**（業種ローカルキーは `CK` の範囲外）。

```python
# Before
from edinet.financial.standards.canonical_keys import CK  # ← 追加

SectorConceptMapping(
    concept="OrdinaryIncomeBNK",
    sector_key="ordinary_revenue_bnk",      # ← 置換しない
    industry_codes=_CODES,
    general_equivalent="revenue",           # ← CK.REVENUE に置換
)

# After
SectorConceptMapping(
    concept="OrdinaryIncomeBNK",
    sector_key="ordinary_revenue_bnk",
    industry_codes=_CODES,
    general_equivalent=CK.REVENUE,
)
```

置換箇所数（延べ）:

| モジュール | general_equivalent 非 None 件数 | ユニーク値数 |
|-----------|:---:|:---:|
| banking.py | 15 | 15 |
| insurance.py | 8 | 7 |
| construction.py | 3 | 3 |
| railway.py | 2 | 2 |
| securities.py | 4 | 4 |
| **合計** | **32** | **18** |

Note: insurance の `sga_expenses` は 2 件（生保 `CommissionsAndCollectionFeesOEINS` + 損保 `SalesAndAdministrativeExpensesOEINS`）が同一値を使用するため、延べ件数（8）とユニーク値数（7）が異なる。

---

## 4. 変更内容の詳細

### 4.1 `canonical_keys.py` 新規作成

- 93 個の `CK` StrEnum 定数を PL / BS / CF / KPI / CI セクション分けで定義
- 各定数に `# J-GAAP` / `# IFRS` / コメントなし（共有）のインラインコメント
- `__all__ = ["CK"]`
- docstring は Google Style、日本語

### 4.2 `jgaap.py` の変更

| 箇所 | 変更内容 |
|------|---------|
| import | `from edinet.financial.standards.canonical_keys import CK` 追加 |
| 全 83 マッピングの `canonical_key=` | 文字列 → `CK.*` |

**変更しないもの**:
- `ConceptMapping` dataclass 定義（`canonical_key: str` のまま — `CK.*` は `str` のサブクラスなので互換）
- `concept=` フィールド
- `statement_type=` フィールド
- `is_jgaap_specific=` フィールド
- 公開 API（`lookup`, `canonical_key`, `reverse_lookup` 等）
- バリデーション関数
- `__all__`

### 4.3 `ifrs.py` の変更

| 箇所 | 変更内容 |
|------|---------|
| import | `from edinet.financial.standards.canonical_keys import CK` 追加 |
| 全 55 マッピングの `canonical_key=` | 文字列 → `CK.*` |

**変更しないもの**:
- `IFRSConceptMapping` dataclass 定義
- `jgaap_concept=` フィールド（concept 名であり canonical_key ではない）
- `mapping_note=` フィールド
- 公開 API
- `__all__`

### 4.4 sector/*.py の変更（5 ファイル）

各ファイル共通:

| 箇所 | 変更内容 |
|------|---------|
| import | `from edinet.financial.standards.canonical_keys import CK` 追加 |
| `general_equivalent=` の文字列 | → `CK.*` |

**変更しないもの**:
- `sector_key=` フィールド（業種ローカルキー、`CK` の範囲外）
- `concept=` フィールド
- `mapping_note=` フィールド
- 公開 API
- `__all__`

### 4.5 置換マッピング表（general_equivalent 文字列 → CK 定数）

| 文字列 | CK 定数 | 使用箇所 | 延べ件数 |
|--------|---------|---------|:---:|
| `"revenue"` | `CK.REVENUE` | banking, insurance, construction, railway, securities | 5 |
| `"cost_of_sales"` | `CK.COST_OF_SALES` | construction, railway | 2 |
| `"gross_profit"` | `CK.GROSS_PROFIT` | construction, securities | 2 |
| `"sga_expenses"` | `CK.SGA_EXPENSES` | banking, insurance(×2), securities | 4 |
| `"operating_income"` | `CK.OPERATING_INCOME` | securities | 1 |
| `"ordinary_income"` | `CK.ORDINARY_INCOME` | banking, insurance | 2 |
| `"extraordinary_income"` | `CK.EXTRAORDINARY_INCOME` | banking, insurance | 2 |
| `"extraordinary_loss"` | `CK.EXTRAORDINARY_LOSS` | banking, insurance | 2 |
| `"income_before_tax"` | `CK.INCOME_BEFORE_TAX` | banking, insurance | 2 |
| `"net_income"` | `CK.NET_INCOME` | banking, insurance | 2 |
| `"net_income_parent"` | `CK.NET_INCOME_PARENT` | banking | 1 |
| `"net_income_minority"` | `CK.NET_INCOME_MINORITY` | banking | 1 |
| `"total_assets"` | `CK.TOTAL_ASSETS` | banking | 1 |
| `"total_liabilities"` | `CK.TOTAL_LIABILITIES` | banking | 1 |
| `"net_assets"` | `CK.NET_ASSETS` | banking | 1 |
| `"operating_cf"` | `CK.OPERATING_CF` | banking | 1 |
| `"investing_cf"` | `CK.INVESTING_CF` | banking | 1 |
| `"financing_cf"` | `CK.FINANCING_CF` | banking | 1 |
| | | **合計** | **32** |

---

## 5. テスト計画

### 5.1 テスト原則

- Detroit 派（古典派）: モック不使用、公開 API のみテスト
- `CK` 自体のプロパティテスト（StrEnum 特性、重複なし、命名規則）
- jgaap / ifrs の全 canonical_key が `CK` に存在するかの整合性テスト
- sector の全 general_equivalent が `CK` に存在するかの整合性テスト

### 5.2 新規テスト: `test_canonical_keys.py`

| ID | テスト名 | 内容 |
|----|---------|------|
| T01 | `test_all_values_are_snake_case` | 全 `CK` 定数の値が小文字 snake_case 文字列 |
| T02 | `test_no_duplicate_values` | `CK` 定数の値に重複なし |
| T03 | `test_all_names_are_upper_snake_case` | 全 `CK` 定数の名前が大文字 SNAKE_CASE |
| T04 | `test_str_equality` | `CK.REVENUE == "revenue"` が True（StrEnum 特性） |
| T05 | `test_isinstance_str` | `isinstance(CK.REVENUE, str)` が True |
| T06 | `test_reverse_lookup` | `CK("revenue")` が `CK.REVENUE` を返す |
| T07 | `test_list_enumeration` | `list(CK)` で全定数列挙可能 |
| T08 | `test_jgaap_all_canonical_keys_in_ck` | jgaap の全 canonical_key が `CK` に存在 |
| T09 | `test_ifrs_all_canonical_keys_in_ck` | ifrs の全 canonical_key が `CK` に存在 |
| T10 | `test_sector_all_general_equivalents_in_ck` | sector の全 general_equivalent が `CK` に存在 |
| T11 | `test_jgaap_ifrs_shared_keys_use_same_ck` | jgaap と ifrs で共有するキーが同一 `CK` 定数（一致確認） |
| T12 | `test_ck_covers_exactly_union` | `set(CK) == jgaap_keys \| ifrs_keys`（CK が jgaap ∪ ifrs の和集合と完全一致。過不足なし） |

### 5.3 既存テストの変更

#### test_standards_jgaap.py

| テスト | 変更内容 |
|--------|---------|
| 新規追加: `test_all_canonical_keys_are_ck_instances` | `all_mappings()` の全 `m.canonical_key` が `CK` のインスタンスであること |

#### test_standards_ifrs.py

| テスト | 変更内容 |
|--------|---------|
| 新規追加: `test_all_canonical_keys_are_ck_instances` | `all_mappings()` の全 `m.canonical_key` が `CK` のインスタンスであること |

既存テストは **変更不要**:
- `CK.REVENUE == "revenue"` のため、`assert m.canonical_key == "revenue"` は引き続きパスする
- `assert "revenue" in all_canonical_keys()` も引き続きパスする（StrEnum は str のサブクラス）

---

## 6. 実装手順

### Step 1: `canonical_keys.py` 新規作成

1. `src/edinet/xbrl/standards/canonical_keys.py` を新規作成
2. `CK` StrEnum に 93 個の定数を定義（§3.1 の構成に従う）
3. docstring / `__all__` を設定

```bash
uv run python -c "from edinet.financial.standards.canonical_keys import CK; print(len(CK))"
# → 93
```

### Step 2: `jgaap.py` の `canonical_key=` 置換

1. `from edinet.financial.standards.canonical_keys import CK` を追加
2. 全 83 マッピングの `canonical_key="..."` → `canonical_key=CK.*` に置換
3. 文字列以外は一切変更しない

```bash
uv run pytest tests/test_xbrl/test_standards_jgaap.py -x -q
```

### Step 3: `ifrs.py` の `canonical_key=` 置換

1. `from edinet.financial.standards.canonical_keys import CK` を追加
2. 全 55 マッピングの `canonical_key="..."` → `canonical_key=CK.*` に置換

```bash
uv run pytest tests/test_xbrl/test_standards_ifrs.py -x -q
```

### Step 4: sector/*.py の `general_equivalent=` 置換

5 ファイルそれぞれ:
1. `from edinet.financial.standards.canonical_keys import CK` を追加
2. `general_equivalent="..."` → `general_equivalent=CK.*` に置換（非 None のもののみ）

```bash
uv run pytest tests/test_xbrl/test_sector_banking.py tests/test_xbrl/test_sector_insurance.py tests/test_xbrl/test_sector_construction.py tests/test_xbrl/test_sector_railway.py tests/test_xbrl/test_sector_securities.py -x -q
```

### Step 5: テスト作成

1. `tests/test_xbrl/test_canonical_keys.py` を新規作成（T01–T12）
2. `tests/test_xbrl/test_standards_jgaap.py` に `test_all_canonical_keys_are_ck_instances` 追加
3. `tests/test_xbrl/test_standards_ifrs.py` に `test_all_canonical_keys_are_ck_instances` 追加

```bash
uv run pytest tests/test_xbrl/test_canonical_keys.py -x -q
```

### Step 6: 回帰テスト

```bash
uv run pytest
uv run ruff check src/edinet/xbrl/standards/ src/edinet/xbrl/sector/
```

---

## 7. 作成・変更ファイル一覧

| ファイル | 操作 | 主な変更 |
|---------|------|---------|
| `src/edinet/xbrl/standards/canonical_keys.py` | **新規** | CK StrEnum 93 定数 (~150 行) |
| `src/edinet/xbrl/standards/jgaap.py` | 変更 | import 追加 + 83 箇所の文字列→CK 置換 |
| `src/edinet/xbrl/standards/ifrs.py` | 変更 | import 追加 + 55 箇所の文字列→CK 置換 |
| `src/edinet/xbrl/sector/banking.py` | 変更 | import 追加 + 15 箇所の文字列→CK 置換 |
| `src/edinet/xbrl/sector/insurance.py` | 変更 | import 追加 + 8 箇所の文字列→CK 置換 |
| `src/edinet/xbrl/sector/construction.py` | 変更 | import 追加 + 3 箇所の文字列→CK 置換 |
| `src/edinet/xbrl/sector/railway.py` | 変更 | import 追加 + 2 箇所の文字列→CK 置換 |
| `src/edinet/xbrl/sector/securities.py` | 変更 | import 追加 + 4 箇所の文字列→CK 置換 |
| `tests/test_xbrl/test_canonical_keys.py` | **新規** | T01–T12 (CK StrEnum テスト) |
| `tests/test_xbrl/test_standards_jgaap.py` | 変更 | CK インスタンステスト 1 件追加 |
| `tests/test_xbrl/test_standards_ifrs.py` | 変更 | CK インスタンステスト 1 件追加 |
| **合計** | 新規 2 + 変更 9 | |

---

## 8. 設計判断の記録

### Q1: なぜ `sector_key` は定数化しないのか？

**A**: `sector_key` は業種内ローカルキー（例: `"ordinary_revenue_bnk"`, `"cash_due_from_banks_bnk"`）であり、基準横断の `canonical_key` とはスコープが異なる。sector_key は各業種モジュール内でのみ使用され、基準横断の一致チェックは不要。定数化のメリット（typo 防止）に対してコスト（45+49+20+11+13 = 138 個の追加定数）が過大であり、ROI が低い。

### Q2: `CK` の値は小文字 snake_case で統一するのか？

**A**: 統一する。現在の jgaap.py / ifrs.py の `canonical_key` 値が全て小文字 snake_case であり、そのまま `CK` の値にする。`CK` の **名前** は Python 慣例に従い大文字 SNAKE_CASE とする。

### Q3: StrEnum ではなく Final[str] 定数群ではダメか？

**A**: StrEnum が優れている理由:
1. `list(CK)` で全定数列挙 → テストで「jgaap の全 canonical_key が CK に存在するか」を O(1) で検証可能
2. `CK("revenue")` の逆引き → デバッグ時に文字列からの逆引きが可能
3. IDE のオートコンプリートが StrEnum メンバーを列挙
4. 値の重複チェックが StrEnum 側で自動（重複定義は `ValueError`）

### Q4: normalize.py は変更しなくてよいのか？

**A**: 変更不要。`get_canonical_key()` は `str | None` を返す。`CK.REVENUE` は `str` のサブクラスなので、`get_canonical_key("NetSales") == "revenue"` は引き続き True。normalize.py が `CK` を import する必要はない。

### Q5: 既存テストは全てそのままパスするのか？

**A**: パスする。`CK.REVENUE == "revenue"` が `True` であるため、文字列比較・dict キー参照・frozenset メンバーシップ検査の全てで既存テストが透過的にパスする。新規テスト `test_all_canonical_keys_are_ck_instances` を追加して、置換漏れを防止する。

### Q6: IFRS 固有キーの命名規則は？

**A**: `_ifrs` サフィックスを持つキー（`other_income_ifrs`, `finance_income` 等）はそのまま CK 定数名に反映する。例: `CK.OTHER_INCOME_IFRS = "other_income_ifrs"`, `CK.FINANCE_INCOME = "finance_income"`。サフィックスがないものは名前だけでは J-GAAP/IFRS の区別がつかないが、`# IFRS` / `# J-GAAP` インラインコメントで識別性を維持する。

---

## 9. 実行チェックリスト

- [ ] `canonical_keys.py` — CK StrEnum 93 定数を PL/BS/CF/KPI/CI セクション分けで定義
- [ ] `jgaap.py` — import 追加 + 83 マッピングの `canonical_key=` 置換
- [ ] `ifrs.py` — import 追加 + 55 マッピングの `canonical_key=` 置換
- [ ] `banking.py` — import 追加 + 15 箇所の `general_equivalent=` 置換
- [ ] `insurance.py` — import 追加 + 8 箇所の `general_equivalent=` 置換
- [ ] `construction.py` — import 追加 + 3 箇所の `general_equivalent=` 置換
- [ ] `railway.py` — import 追加 + 2 箇所の `general_equivalent=` 置換
- [ ] `securities.py` — import 追加 + 4 箇所の `general_equivalent=` 置換
- [ ] `test_canonical_keys.py` — T01–T12 新規テスト
- [ ] `test_standards_jgaap.py` — CK インスタンステスト追加
- [ ] `test_standards_ifrs.py` — CK インスタンステスト追加
- [ ] `uv run pytest` — 全テストパス
- [ ] `uv run ruff check src/edinet/xbrl/standards/ src/edinet/xbrl/sector/` — クリーン

---

## フィードバック反映サマリー（第 1 回）

| # | 指摘 | 判定 | 対応 |
|---|------|------|------|
| 1 | 数値の不一致（J-GAAP 83→48, IFRS 55→40） | **事実と異なる**: 実コードで `all_canonical_keys()` が J-GAAP=83, IFRS=55 を返すことを再確認済み。mappings 数と unique canonical_key 数は一致（重複なし）。フィードバック側の「実測値 48/40」は Part 2 後の ConceptMapping フィールド数（4 フィールド）等との混同の可能性 | 数値変更なし |
| 2 | §1.5 リスト不整合 | **事実と異なる**: 38 個のリストが実コードの `jgaap_keys - ifrs_keys` と完全一致することを確認済み | 変更なし |
| 3 | CI セクションの `comprehensive_income_parent` コメント | **妥当**: `is_ifrs_specific=False` であり J-GAAP にも概念が存在しうる | §3.1 の該当行に `is_ifrs_specific=False` を注記追加 |
| 4 | CF 期首・期末キャッシュのキー不在 | **確認済み**: jgaap.py / ifrs.py に cash_beginning/cash_ending は存在しない。`net_change_in_cash` のみ | 変更なし（問題なし） |
| 5 | §4.5 insurance の不足 | **妥当**: insurance は延べ 8 件（7 ユニーク値）。`sga_expenses` が 2 件ある。`net_income_parent`/`net_income_minority` は banking のみ | §3.2 置換箇所数テーブルを insurance=8 に修正、合計=32 に修正。§4.5 に延べ件数列と insurance(×2) の注記追加 |
| 6 | T12 のハードコード値 | **妥当**: 導出ベースのテスト（`set(CK) == jgaap_keys \| ifrs_keys`）に変更 | T07 の件数記述削除、T12 を導出ベース（`test_ck_covers_exactly_union`）に変更 |
| 7 | 良い点 | — | 変更なし |

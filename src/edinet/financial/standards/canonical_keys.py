"""会計基準横断の正規化キー定数。

``summary_mappings.py`` と ``statement_mappings.py`` が共有する
canonical_key の文字列リテラルを定数化し、typo を防止する。

``CK`` は ``StrEnum`` であり、``CK.REVENUE == "revenue"`` が True。
``isinstance(CK.REVENUE, str)`` も True のため、文字列を期待する
dict キーやフィールド値にそのまま使用できる。

典型的な使用例::

    from edinet.financial.standards.canonical_keys import CK

    # extract_values で使用
    result = extract_values(stmts, [CK.REVENUE, CK.OPERATING_INCOME])

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
    INTEREST_INCOME_PL = "interest_income_pl"              # J-GAAP (営業外収益)
    INTEREST_EXPENSE_PL = "interest_expense_pl"            # J-GAAP (営業外費用)
    RD_EXPENSES = "rd_expenses"                            # 研究開発費
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
    GOODWILL = "goodwill"
    INVESTMENTS_AND_OTHER = "investments_and_other"        # J-GAAP
    DEFERRED_ASSETS = "deferred_assets"                    # J-GAAP
    TOTAL_ASSETS = "total_assets"
    TRADE_PAYABLES = "trade_payables"
    SHORT_TERM_LOANS = "short_term_loans"
    CURRENT_LIABILITIES = "current_liabilities"
    LONG_TERM_LOANS = "long_term_loans"
    BONDS_PAYABLE = "bonds_payable"
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
    CASH_BEGINNING = "cash_beginning"                                    # J-GAAP (instant)
    CASH_END = "cash_end"                                                # J-GAAP (instant)

    # --- KPI (主要経営指標) ---
    EPS = "eps"
    EPS_DILUTED = "eps_diluted"
    BPS = "bps"                                            # J-GAAP
    DPS = "dps"                                            # J-GAAP
    EQUITY_RATIO = "equity_ratio"                          # J-GAAP
    ROE = "roe"                                            # J-GAAP
    PER = "per"                                            # J-GAAP
    EMPLOYEES = "employees"                                # J-GAAP
    INTERIM_DPS = "interim_dps"                            # J-GAAP
    PAYOUT_RATIO = "payout_ratio"                          # J-GAAP
    TOTAL_SHARES_ISSUED = "total_shares_issued"            # J-GAAP
    EQUITY_METHOD_INCOME = "equity_method_income"          # J-GAAP
    CONTINUING_OPERATIONS_INCOME = "continuing_operations_income"  # IFRS/JMIS

    # --- CI (包括利益 — IFRS) ---
    COMPREHENSIVE_INCOME = "comprehensive_income"          # IFRS (is_ifrs_specific=True)
    COMPREHENSIVE_INCOME_PARENT = "comprehensive_income_parent"  # IFRS (is_ifrs_specific=False)
    COMPREHENSIVE_INCOME_MINORITY = "comprehensive_income_minority"  # IFRS (is_ifrs_specific=True)

    # --- BANKING (銀行業固有) ---
    CAPITAL_ADEQUACY_RATIO_BIS = "capital_adequacy_ratio_bis"
    CAPITAL_ADEQUACY_RATIO_DOMESTIC = "capital_adequacy_ratio_domestic"
    CAPITAL_ADEQUACY_RATIO_DOMESTIC_2 = "capital_adequacy_ratio_domestic_2"
    CAPITAL_ADEQUACY_RATIO_INTERNATIONAL = "capital_adequacy_ratio_international"
    DEPOSITS = "deposits"
    LOANS_AND_BILLS_DISCOUNTED = "loans_and_bills_discounted"
    SECURITIES_BANKING = "securities_banking"

    # --- INSURANCE (保険業固有) ---
    NET_PREMIUMS_WRITTEN = "net_premiums_written"
    INTEREST_DIVIDEND_INCOME_INS = "interest_dividend_income_ins"
    INVESTMENT_YIELD_INCOME = "investment_yield_income"
    INVESTMENT_YIELD_REALIZED = "investment_yield_realized"
    NET_LOSS_RATIO = "net_loss_ratio"
    NET_OPERATING_EXPENSE_RATIO = "net_operating_expense_ratio"

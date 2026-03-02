"""Week 2 E2E テスト: J-GAAP 一般事業会社に特化。

week2_e2e_test.py では最初に取得された有報が投資信託だったため、
J-GAAP 一般事業会社の PL/BS/CF を明示的にテストする。

対象企業例:
  - ジョイフル本田 (E04726) : J-GAAP、半期報告書あり
  - 適当な一般事業会社を 2026-02-20 の有報から選択
"""

from __future__ import annotations

import sys
import time
import traceback
from datetime import date
from decimal import Decimal

import edinet
from edinet import (
    Company,
    DocType,
    Filing,
    FinancialStatement,
    LineItem,
    Statements,
    configure,
    documents,
)
from edinet.xbrl import (
    TaxonomyResolver,
    build_line_items,
    build_statements,
    parse_xbrl_facts,
    structure_contexts,
)
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

API_KEY = "your_api_key_here"
TAXONOMY_PATH = "/mnt/c/Users/nezow/Downloads/ALL_20251101"
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)

passed = 0
failed = 0
errors: list[str] = []


def test_case(name: str):
    def decorator(func):
        def wrapper():
            global passed, failed
            print(f"\n{'='*70}")
            print(f"TEST: {name}")
            print(f"{'='*70}")
            try:
                func()
                passed += 1
                print(f"  ✓ PASSED")
            except Exception as e:
                failed += 1
                print(f"  ✗ FAILED: {e}")
                traceback.print_exc()
                errors.append(f"{name}: {e}")
        return wrapper
    return decorator


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")


def assert_gt(a, b, msg=""):
    if not (a > b):
        raise AssertionError(f"Expected {a} > {b}: {msg}")


def assert_isinstance(obj, cls, msg=""):
    if not isinstance(obj, cls):
        raise AssertionError(f"Expected {type(obj).__name__} to be {cls.__name__}: {msg}")


# ─── J-GAAP 一般事業会社を見つける ────────────────────────────

def find_jgaap_filing(target_date: str = "2026-02-20") -> Filing:
    """J-GAAP 一般事業会社の has_xbrl=True な有報を探す。

    投信・IFRS企業を除外するため ordinanceCode="010" (開示府令) かつ
    formCode が有報の一般事業会社を狙う。
    """
    filings = documents(target_date, doc_type="120")
    candidates = [
        f for f in filings
        if f.has_xbrl
        and f.ordinance_code == "010"  # 開示府令（一般事業会社）
    ]
    if not candidates:
        # 別日で再試行
        filings = documents("2026-02-21", doc_type="120")
        candidates = [
            f for f in filings
            if f.has_xbrl and f.ordinance_code == "010"
        ]
    if not candidates:
        raise RuntimeError("J-GAAP 一般事業会社の有報が見つからない")

    print(f"  J-GAAP 候補: {len(candidates)}件")
    # 一般事業会社を選択（最初の候補を使用）
    f = candidates[0]
    print(f"  選択: {f.filer_name} ({f.doc_id})")
    print(f"    ordinance: {f.ordinance}")
    print(f"    form: {f.form}")
    print(f"    period: {f.period_start} ~ {f.period_end}")
    return f


# ─── テスト ───────────────────────────────────────────────────

@test_case("J1: J-GAAP 企業の PL - 主要科目が存在する")
def test_jgaap_pl_main_items():
    f = find_jgaap_filing()
    stmts = f.xbrl()
    pl = stmts.income_statement()

    print(f"  PL 科目数: {len(pl)}")
    print(f"  期間: {pl.period}")
    print(f"  連結: {pl.consolidated}")
    print(f"  entity_id: {pl.entity_id}")
    assert_gt(len(pl), 0, "PL に科目が存在するはず")

    # 全科目を表示
    print(f"\n  === PL 全科目 ===")
    for i, item in enumerate(pl):
        val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
        src = item.label_ja.source.value
        print(f"  [{i+1:2d}] {item.label_ja.text}: {val} {item.unit_ref or ''} "
              f"(concept={item.local_name}, source={src})")

    # 主要科目の存在確認（一般事業会社なら少なくとも一部は存在するはず）
    key_items = {
        "売上高": "NetSales",
        "売上原価": "CostOfSales",
        "売上総利益": "GrossProfit",
        "販売費及び一般管理費": "SellingGeneralAndAdministrativeExpenses",
        "営業利益": "OperatingIncome",
        "経常利益": "OrdinaryIncome",
    }
    found = 0
    for label, concept in key_items.items():
        # 日本語ラベル or local_name で検索
        item = pl.get(label) or pl.get(concept)
        if item:
            val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            print(f"  ✓ {label}: {val}")
            found += 1
        else:
            print(f"  ⚠ {label}: 見つからない")

    print(f"\n  主要科目ヒット率: {found}/{len(key_items)}")
    # 少なくとも営業利益・経常利益のどちらかは存在するはず
    has_op = pl.get("営業利益") is not None or pl.get("OperatingIncome") is not None
    has_ord = pl.get("経常利益") is not None or pl.get("OrdinaryIncome") is not None
    assert_true(has_op or has_ord, "営業利益 or 経常利益が見つかるはず")


@test_case("J2: J-GAAP 企業の BS - 資産・負債・純資産が存在する")
def test_jgaap_bs_main_items():
    f = find_jgaap_filing()
    stmts = f.xbrl()
    bs = stmts.balance_sheet()

    print(f"  BS 科目数: {len(bs)}")
    print(f"  期間: {bs.period}")

    # BS は InstantPeriod
    if bs.period:
        assert_isinstance(bs.period, InstantPeriod,
                          f"BS は InstantPeriod のはず: {type(bs.period)}")

    # 全科目を表示
    print(f"\n  === BS 全科目 ===")
    for i, item in enumerate(bs):
        val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
        print(f"  [{i+1:2d}] {item.label_ja.text}: {val} {item.unit_ref or ''} "
              f"(concept={item.local_name})")

    # 主要科目
    key_items = {
        "流動資産": "CurrentAssets",
        "固定資産": "NoncurrentAssets",
        "資産合計": "Assets",
        "流動負債": "CurrentLiabilities",
        "固定負債": "NoncurrentLiabilities",
        "負債合計": "Liabilities",
        "純資産合計": "NetAssets",
        "負債純資産合計": "LiabilitiesAndNetAssets",
    }
    found = 0
    for label, concept in key_items.items():
        item = bs.get(label) or bs.get(concept)
        if item:
            val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            print(f"  ✓ {label}: {val}")
            found += 1
        else:
            print(f"  ⚠ {label}: 見つからない")

    print(f"\n  主要科目ヒット率: {found}/{len(key_items)}")
    assert_gt(found, 0, "BS の主要科目が少なくとも1つは存在するはず")


@test_case("J3: J-GAAP 企業の CF")
def test_jgaap_cf():
    f = find_jgaap_filing()
    stmts = f.xbrl()
    cf = stmts.cash_flow_statement()

    print(f"  CF 科目数: {len(cf)}")
    print(f"  期間: {cf.period}")

    # 全科目を表示
    print(f"\n  === CF 全科目 ===")
    for i, item in enumerate(cf):
        val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
        print(f"  [{i+1:2d}] {item.label_ja.text}: {val} {item.unit_ref or ''} "
              f"(concept={item.local_name})")

    # 主要科目
    key_items = {
        "営業活動によるキャッシュ・フロー": "NetCashProvidedByUsedInOperatingActivities",
        "投資活動によるキャッシュ・フロー": "NetCashProvidedByUsedInInvestmentActivities",
        "財務活動によるキャッシュ・フロー": "NetCashProvidedByUsedInFinancingActivities",
    }
    found = 0
    for label, concept in key_items.items():
        item = cf.get(label) or cf.get(concept)
        if item:
            val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            print(f"  ✓ {label}: {val}")
            found += 1
        else:
            print(f"  ⚠ {label}: 見つからない")
    print(f"\n  主要科目ヒット率: {found}/{len(key_items)}")


@test_case("J4: __getitem__ で日本語ラベル・英語ラベル・local_name 検索")
def test_getitem_variants():
    f = find_jgaap_filing()
    stmts = f.xbrl()
    pl = stmts.income_statement()

    # 日本語ラベルで検索
    for key in ["営業利益又は営業損失（△）", "経常利益又は経常損失（△）"]:
        item = pl.get(key)
        if item:
            print(f"  日本語 '{key}': {item.value:,}")
            break

    # 英語ラベルで検索
    for key in ["Operating profit (loss)", "Ordinary profit (loss)"]:
        item = pl.get(key)
        if item:
            print(f"  英語 '{key}': {item.value:,}")
            break

    # local_name で検索
    for key in ["OperatingIncome", "OrdinaryIncome"]:
        item = pl.get(key)
        if item:
            print(f"  local_name '{key}': {item.value:,}")
            break


@test_case("J5: to_dataframe() のカラムと型")
def test_to_dataframe_columns():
    f = find_jgaap_filing()
    stmts = f.xbrl()
    pl = stmts.income_statement()

    try:
        import pandas as pd

        df = pl.to_dataframe()
        print(f"  shape: {df.shape}")
        print(f"  columns: {list(df.columns)}")
        print(f"  dtypes:\n{df.dtypes}")
        print(f"\n  attrs: {df.attrs}")

        # カラム確認
        expected_cols = ["label_ja", "label_en", "value", "unit", "concept"]
        for col in expected_cols:
            assert_true(col in df.columns, f"カラム '{col}' が存在")

        # attrs 確認
        assert_true("statement_type" in df.attrs, "attrs に statement_type")
        assert_true("consolidated" in df.attrs, "attrs に consolidated")
        assert_true("period" in df.attrs, "attrs に period")

        # 全行表示
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 120)
        print(f"\n{df}")

    except ImportError:
        print("  ⚠ pandas 未インストール")


@test_case("J6: to_dict() の内容")
def test_to_dict_content():
    f = find_jgaap_filing()
    stmts = f.xbrl()
    pl = stmts.income_statement()

    dicts = pl.to_dict()
    print(f"  to_dict 件数: {len(dicts)}")
    for d in dicts[:5]:
        print(f"  {d}")


@test_case("J7: Rich 表示 - PL/BS/CF")
def test_rich_display_all():
    f = find_jgaap_filing()
    stmts = f.xbrl()

    try:
        from rich.console import Console
        console = Console(width=120)

        print(f"\n  === PL ===")
        pl = stmts.income_statement()
        console.print(pl)

        print(f"\n  === BS ===")
        bs = stmts.balance_sheet()
        console.print(bs)

        print(f"\n  === CF ===")
        cf = stmts.cash_flow_statement()
        console.print(cf)
    except ImportError:
        print("  ⚠ rich 未インストール")


@test_case("J8: 連結 vs 個別の比較")
def test_consolidated_vs_non_consolidated():
    f = find_jgaap_filing()
    stmts = f.xbrl()

    pl_cons = stmts.income_statement(consolidated=True)
    pl_solo = stmts.income_statement(consolidated=False)

    print(f"  連結 PL: {len(pl_cons)}科目, consolidated={pl_cons.consolidated}")
    print(f"  個別 PL: {len(pl_solo)}科目, consolidated={pl_solo.consolidated}")

    # 同じ科目で値を比較
    for key in ["OperatingIncome", "OrdinaryIncome"]:
        cons = pl_cons.get(key)
        solo = pl_solo.get(key)
        if cons and solo:
            print(f"  {key}:")
            print(f"    連結: {cons.value:,}")
            print(f"    個別: {solo.value:,}")

    bs_cons = stmts.balance_sheet(consolidated=True)
    bs_solo = stmts.balance_sheet(consolidated=False)
    print(f"\n  連結 BS: {len(bs_cons)}科目")
    print(f"  個別 BS: {len(bs_solo)}科目")


@test_case("J9: 半期報告書の J-GAAP 企業")
def test_jgaap_semi_annual():
    filings = documents(start="2026-02-01", end="2026-02-28", doc_type="160")
    candidates = [
        f for f in filings
        if f.has_xbrl and f.ordinance_code == "010"
    ]
    if not candidates:
        print("  ⚠ J-GAAP 半期報告書が見つからない")
        return

    f = candidates[0]
    print(f"  半期報告書: {f.filer_name} ({f.doc_id})")
    print(f"  period: {f.period_start} ~ {f.period_end}")

    stmts = f.xbrl()
    pl = stmts.income_statement()
    bs = stmts.balance_sheet()

    print(f"  PL: {len(pl)}科目")
    print(f"  BS: {len(bs)}科目")

    # 主要科目
    for key in ["OperatingIncome", "OrdinaryIncome", "ProfitLoss"]:
        item = pl.get(key)
        if item:
            print(f"  PL {key}: {item.value:,}")


@test_case("J10: 複数 J-GAAP 企業の PL 比較")
def test_multiple_jgaap_companies():
    filings = documents("2026-02-20", doc_type="120")
    candidates = [
        f for f in filings
        if f.has_xbrl and f.ordinance_code == "010"
    ]
    print(f"  J-GAAP 有報(開示府令): {len(candidates)}件")

    # 最大5社を比較
    for f in candidates[:5]:
        print(f"\n  --- {f.filer_name} ({f.doc_id}) ---")
        try:
            stmts = f.xbrl()
            pl = stmts.income_statement()
            bs = stmts.balance_sheet()
            cf = stmts.cash_flow_statement()

            print(f"    PL: {len(pl)}科目, BS: {len(bs)}科目, CF: {len(cf)}科目")
            print(f"    連結: {pl.consolidated}, 期間: {pl.period}")

            sales = pl.get("NetSales") or pl.get("売上高")
            op = pl.get("OperatingIncome")
            if sales:
                print(f"    売上高: {sales.value:,}")
            if op:
                print(f"    営業利益: {op.value:,}")

            if pl.warnings_issued:
                print(f"    PL警告: {pl.warnings_issued}")
        except Exception as e:
            print(f"    ⚠ エラー: {e}")


@test_case("J11: パフォーマンス計測 - J-GAAP 企業")
def test_jgaap_performance():
    f = find_jgaap_filing()
    f.clear_fetch_cache()

    t0 = time.perf_counter()
    stmts = f.xbrl()
    t1 = time.perf_counter()
    print(f"  xbrl() 合計: {(t1-t0)*1000:.0f}ms")

    t2 = time.perf_counter()
    pl = stmts.income_statement()
    t3 = time.perf_counter()
    print(f"  income_statement(): {(t3-t2)*1000:.1f}ms ({len(pl)} items)")

    t4 = time.perf_counter()
    bs = stmts.balance_sheet()
    t5 = time.perf_counter()
    print(f"  balance_sheet(): {(t5-t4)*1000:.1f}ms ({len(bs)} items)")

    t6 = time.perf_counter()
    cf = stmts.cash_flow_statement()
    t7 = time.perf_counter()
    print(f"  cash_flow_statement(): {(t7-t6)*1000:.1f}ms ({len(cf)} items)")


@test_case("J12: 提出者ラベルが正しく解決される")
def test_filer_labels_resolved():
    """提出者タクソノミの独自科目がラベル解決されているか確認。"""
    f = find_jgaap_filing()
    stmts = f.xbrl()
    pl = stmts.income_statement()

    filer_items = [item for item in pl if item.label_ja.source == LabelSource.FILER]
    standard_items = [item for item in pl if item.label_ja.source == LabelSource.STANDARD]
    fallback_items = [item for item in pl if item.label_ja.source == LabelSource.FALLBACK]

    print(f"  ラベルソース分布:")
    print(f"    STANDARD: {len(standard_items)}")
    print(f"    FILER: {len(filer_items)}")
    print(f"    FALLBACK: {len(fallback_items)}")

    if filer_items:
        print(f"  提出者ラベル例:")
        for item in filer_items[:5]:
            print(f"    {item.label_ja.text} ({item.local_name})")

    if fallback_items:
        print(f"  フォールバック例:")
        for item in fallback_items[:5]:
            print(f"    {item.label_ja.text} ({item.local_name})")

    # BS / CF も確認
    bs = stmts.balance_sheet()
    cf = stmts.cash_flow_statement()

    for name, stmt in [("BS", bs), ("CF", cf)]:
        filer = [i for i in stmt if i.label_ja.source == LabelSource.FILER]
        fb = [i for i in stmt if i.label_ja.source == LabelSource.FALLBACK]
        print(f"  {name}: FILER={len(filer)}, FALLBACK={len(fb)}")


# ─── 実行 ─────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Week 2 E2E テスト: J-GAAP 一般事業会社特化")
    print(f"日時: {date.today()}")
    print("=" * 70)

    tests = [
        test_jgaap_pl_main_items,
        test_jgaap_bs_main_items,
        test_jgaap_cf,
        test_getitem_variants,
        test_to_dataframe_columns,
        test_to_dict_content,
        test_rich_display_all,
        test_consolidated_vs_non_consolidated,
        test_jgaap_semi_annual,
        test_multiple_jgaap_companies,
        test_jgaap_performance,
        test_filer_labels_resolved,
    ]

    for test_fn in tests:
        test_fn()

    print("\n" + "=" * 70)
    print(f"結果: {passed} passed, {failed} failed")
    if errors:
        print("\n失敗したテスト:")
        for e in errors:
            print(f"  ✗ {e}")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

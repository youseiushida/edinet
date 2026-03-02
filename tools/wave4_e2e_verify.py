"""Wave 4 E2E 検証スクリプト。

Wave 4 のデータモデル変更後、EDINET API から実データを取得し、
statements パイプラインが正しく動作するか検証する。

対象:
  - J-GAAP 一般事業会社: ナカバヤシ (S100W4JX)
  - IFRS 企業: 日立製作所 (S100W56G)
  - 銀行業: 三菱UFJ等を documents API で検索

確認事項:
  - Filing.xbrl() でエラーなく Statements が取得できるか
  - income_statement / balance_sheet / cash_flow_statement が科目を返すか
  - canonical_key での名寄せが機能しているか
  - FinancialStatement の items 数・値の妥当性
"""

from __future__ import annotations

import os
import sys
import time
import traceback
import warnings
from decimal import Decimal
from io import StringIO

from edinet import configure, documents
from edinet.financial.standards.canonical_keys import CK
from edinet.financial.standards import jgaap, ifrs, normalize

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "wave4_e2e_results.txt")

# --- テストユーティリティ ---

passed = 0
failed = 0
errors: list[str] = []
output_lines: list[str] = []


def log(msg: str = ""):
    """画面とファイル出力両方に書き出す。"""
    print(msg)
    output_lines.append(msg)


def test_case(name: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            global passed, failed
            log(f"\n{'='*70}")
            log(f"TEST: {name}")
            log(f"{'='*70}")
            try:
                func(*args, **kwargs)
                passed += 1
                log(f"  -> PASSED")
            except Exception as e:
                failed += 1
                tb = traceback.format_exc()
                log(f"  -> FAILED: {e}")
                log(tb)
                errors.append(f"{name}: {e}")
        return wrapper
    return decorator


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")


def assert_gt(a, b, msg=""):
    if not (a > b):
        raise AssertionError(f"Expected {a} > {b}: {msg}")


def assert_is_not_none(obj, msg=""):
    if obj is None:
        raise AssertionError(f"Expected not None: {msg}")


# --- 既知の doc_id ---

JGAAP_DOC_ID = "S100W4JX"    # ナカバヤシ (J-GAAP 一般事業会社)
IFRS_DOC_ID = "S100W56G"      # 日立製作所 (IFRS)
TOYOTA_DOC_ID = "S100VWVY"    # トヨタ (IFRS)


# ================================================================
# TEST 1: CK StrEnum 定数の基本動作
# ================================================================
@test_case("CK-1: CK StrEnum は文字列として比較可能")
def test_ck_basics():
    """CK が StrEnum として機能するか。"""
    assert_true(CK.REVENUE == "revenue", f"CK.REVENUE={CK.REVENUE!r}")
    assert_true(isinstance(CK.REVENUE, str), "CK.REVENUE は str")
    assert_true(CK("revenue") is CK.REVENUE, "CK('revenue') is CK.REVENUE")
    log(f"  CK.REVENUE = {CK.REVENUE!r}")
    log(f"  CK.TOTAL_ASSETS = {CK.TOTAL_ASSETS!r}")
    log(f"  CK.OPERATING_CF = {CK.OPERATING_CF!r}")
    log(f"  CK メンバー数: {len(CK)}")


# ================================================================
# TEST 2: jgaap.py の canonical_key マッピングが CK と整合
# ================================================================
@test_case("CK-2: jgaap.lookup() の canonical_key が CK 値を使用")
def test_jgaap_ck_integration():
    """jgaap.py のマッピングが CK StrEnum 定数を使っているか確認。"""
    test_cases = [
        ("NetSales", CK.REVENUE),
        ("CostOfSales", CK.COST_OF_SALES),
        ("GrossProfit", CK.GROSS_PROFIT),
        ("OperatingIncome", CK.OPERATING_INCOME),
        ("OrdinaryIncome", CK.ORDINARY_INCOME),
        ("NetIncome", CK.NET_INCOME),
        ("TotalAssets", CK.TOTAL_ASSETS),
        ("TotalLiabilities", CK.TOTAL_LIABILITIES),
    ]
    for concept, expected_ck in test_cases:
        m = jgaap.lookup(concept)
        if m is not None:
            assert_true(
                m.canonical_key == expected_ck,
                f"{concept}: {m.canonical_key!r} != {expected_ck!r}"
            )
            log(f"  {concept} -> {m.canonical_key!r} (OK)")
        else:
            log(f"  {concept} -> None (NOT FOUND)")

    # 全マッピング数
    all_m = jgaap.all_mappings()
    log(f"  jgaap 全マッピング数: {len(all_m)}")
    all_keys = jgaap.all_canonical_keys()
    log(f"  jgaap 全正規化キー数: {len(all_keys)}")


# ================================================================
# TEST 3: ifrs.py の canonical_key マッピングが CK と整合
# ================================================================
@test_case("CK-3: ifrs.lookup() の canonical_key が CK 値を使用")
def test_ifrs_ck_integration():
    """ifrs.py のマッピングが CK StrEnum 定数を使っているか確認。"""
    test_cases = [
        ("RevenueIFRS", CK.REVENUE),
        ("CostOfSalesIFRS", CK.COST_OF_SALES),
        ("OperatingIncomeIFRS", CK.OPERATING_INCOME),
        ("NetIncomeIFRS", CK.NET_INCOME),
        ("TotalAssetsIFRS", CK.TOTAL_ASSETS),
    ]
    for concept, expected_ck in test_cases:
        m = ifrs.lookup(concept)
        if m is not None:
            assert_true(
                m.canonical_key == expected_ck,
                f"{concept}: {m.canonical_key!r} != {expected_ck!r}"
            )
            log(f"  {concept} -> {m.canonical_key!r} (OK)")
        else:
            log(f"  {concept} -> None (NOT FOUND)")

    all_m = ifrs.all_mappings()
    log(f"  ifrs 全マッピング数: {len(all_m)}")
    all_keys = ifrs.all_canonical_keys()
    log(f"  ifrs 全正規化キー数: {len(all_keys)}")


# ================================================================
# TEST 4: normalize レイヤーが Wave 4 後も動作するか
# ================================================================
@test_case("NRM-1: normalize.get_canonical_key() が動作")
def test_normalize_get_canonical_key():
    """normalize の統一 API で名寄せが機能するか。"""
    from edinet.xbrl.dei import AccountingStandard

    # J-GAAP
    key = normalize.get_canonical_key("NetSales", AccountingStandard.JAPAN_GAAP)
    assert_true(key == "revenue", f"NetSales -> {key}")
    log(f"  J-GAAP: NetSales -> {key}")

    # IFRS
    key = normalize.get_canonical_key("RevenueIFRS", AccountingStandard.IFRS)
    assert_true(key == "revenue", f"RevenueIFRS -> {key}")
    log(f"  IFRS: RevenueIFRS -> {key}")

    # 基準なし（自動検索）
    key = normalize.get_canonical_key("NetSales")
    assert_true(key == "revenue", f"auto NetSales -> {key}")
    log(f"  auto: NetSales -> {key}")

    # cross-standard lookup
    concept = normalize.cross_standard_lookup(
        "NetSales", AccountingStandard.JAPAN_GAAP, AccountingStandard.IFRS
    )
    log(f"  cross: NetSales (J-GAAP -> IFRS) = {concept}")


# ================================================================
# TEST 5: J-GAAP 一般事業会社 (ナカバヤシ) の statements
# ================================================================
@test_case("E2E-JGAAP: ナカバヤシ (S100W4JX) のフルパイプライン")
def test_jgaap_full_pipeline():
    """J-GAAP 企業のステートメント取得。"""
    log(f"  doc_id: {JGAAP_DOC_ID}")

    # Filing を検索
    filings = documents("2025-06-26", doc_type="120")
    target = None
    for f in filings:
        if f.doc_id == JGAAP_DOC_ID:
            target = f
            break

    if target is None:
        # 直接 doc_id アクセスでフォールバック
        log("  2025-06-26 のリストに見つからず。2025-06-27 を試行。")
        filings = documents("2025-06-27", doc_type="120")
        for f in filings:
            if f.doc_id == JGAAP_DOC_ID:
                target = f
                break

    assert_is_not_none(target, f"ナカバヤシ {JGAAP_DOC_ID} が見つかりません")
    log(f"  Filing: {target.filer_name} (ticker={target.ticker})")

    t0 = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        stmts = target.xbrl()
    elapsed = time.perf_counter() - t0
    log(f"  xbrl() 完了: {elapsed:.2f}s")

    if caught_warnings:
        log(f"  発行された警告: {len(caught_warnings)}")
        for w in caught_warnings[:10]:
            log(f"    - {w.category.__name__}: {w.message}")

    # 会計基準の検出
    log(f"  detected_standard: {stmts.detected_standard}")

    # --- PL ---
    pl = stmts.income_statement()
    log(f"\n  [PL] 科目数: {len(pl)}")
    log(f"  [PL] period: {pl.period}")
    log(f"  [PL] consolidated: {pl.consolidated}")
    assert_gt(len(pl), 0, "PL に科目が存在")

    # 主要科目の確認
    pl_checks = [
        ("売上高", CK.REVENUE),
        ("売上原価", CK.COST_OF_SALES),
        ("売上総利益", CK.GROSS_PROFIT),
        ("営業利益", CK.OPERATING_INCOME),
        ("経常利益", CK.ORDINARY_INCOME),
        ("当期純利益", CK.NET_INCOME),
    ]
    for label_ja, ck in pl_checks:
        item = pl.get(label_ja)
        if item is not None:
            log(f"    {label_ja}: {item.value:>15,} ({item.local_name})")
        else:
            # local_name で再試行
            for it in pl:
                m = jgaap.lookup(it.local_name)
                if m and m.canonical_key == ck:
                    log(f"    {label_ja}: {it.value:>15,} (via canonical_key={ck}, local={it.local_name})")
                    break
            else:
                log(f"    {label_ja}: NOT FOUND (ck={ck})")

    # --- BS ---
    bs = stmts.balance_sheet()
    log(f"\n  [BS] 科目数: {len(bs)}")
    log(f"  [BS] period: {bs.period}")
    assert_gt(len(bs), 0, "BS に科目が存在")

    bs_checks = [
        ("総資産", CK.TOTAL_ASSETS),
        ("負債合計", CK.TOTAL_LIABILITIES),
        ("純資産合計", CK.NET_ASSETS),
    ]
    for label_ja, ck in bs_checks:
        item = bs.get(label_ja)
        if item is not None:
            log(f"    {label_ja}: {item.value:>15,} ({item.local_name})")
        else:
            for it in bs:
                m = jgaap.lookup(it.local_name)
                if m and m.canonical_key == ck:
                    log(f"    {label_ja}: {it.value:>15,} (via ck={ck}, local={it.local_name})")
                    break
            else:
                log(f"    {label_ja}: NOT FOUND (ck={ck})")

    # --- CF ---
    cf = stmts.cash_flow_statement()
    log(f"\n  [CF] 科目数: {len(cf)}")
    log(f"  [CF] period: {cf.period}")
    assert_gt(len(cf), 0, "CF に科目が存在")

    cf_checks = [
        ("営業活動によるキャッシュ・フロー", CK.OPERATING_CF),
        ("投資活動によるキャッシュ・フロー", CK.INVESTING_CF),
        ("財務活動によるキャッシュ・フロー", CK.FINANCING_CF),
    ]
    for label_ja, ck in cf_checks:
        item = cf.get(label_ja)
        if item is not None:
            log(f"    {label_ja}: {item.value:>15,} ({item.local_name})")
        else:
            for it in cf:
                m = jgaap.lookup(it.local_name)
                if m and m.canonical_key == ck:
                    log(f"    {label_ja}: {it.value:>15,} (via ck={ck}, local={it.local_name})")
                    break
            else:
                log(f"    {label_ja}: NOT FOUND (ck={ck})")

    # to_dict / to_dataframe
    pl_dict = pl.to_dict()
    log(f"\n  [PL] to_dict() 件数: {len(pl_dict)}")
    assert_gt(len(pl_dict), 0, "to_dict() が空でない")

    try:
        pl_df = pl.to_dataframe()
        log(f"  [PL] to_dataframe() shape: {pl_df.shape}")
        log(f"  [PL] columns: {list(pl_df.columns)}")
    except ImportError:
        log("  [PL] pandas 未インストール、to_dataframe() スキップ")


# ================================================================
# TEST 6: IFRS 企業 (日立) の statements
# ================================================================
@test_case("E2E-IFRS: 日立 (S100W56G) のフルパイプライン")
def test_ifrs_full_pipeline():
    """IFRS 企業のステートメント取得。"""
    log(f"  doc_id: {IFRS_DOC_ID}")

    # Filing 取得 (日立は 2025-06-25 提出)
    target = None
    for date in ["2025-06-25", "2025-06-26", "2025-06-27"]:
        filings = documents(date, doc_type="120")
        for f in filings:
            if f.doc_id == IFRS_DOC_ID:
                target = f
                break
        if target:
            break

    assert_is_not_none(target, f"日立 {IFRS_DOC_ID} が見つかりません")
    log(f"  Filing: {target.filer_name} (ticker={target.ticker})")

    t0 = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        stmts = target.xbrl()
    elapsed = time.perf_counter() - t0
    log(f"  xbrl() 完了: {elapsed:.2f}s")

    if caught_warnings:
        log(f"  発行された警告: {len(caught_warnings)}")
        for w in caught_warnings[:10]:
            log(f"    - {w.category.__name__}: {w.message}")

    log(f"  detected_standard: {stmts.detected_standard}")

    # --- PL ---
    pl = stmts.income_statement()
    log(f"\n  [PL] 科目数: {len(pl)}")
    log(f"  [PL] period: {pl.period}")
    log(f"  [PL] consolidated: {pl.consolidated}")

    if len(pl) > 0:
        # IFRS 特有の science 目を表示
        log("  [PL] 全科目:")
        for item in pl:
            val_str = f"{item.value:>15,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            ck = ifrs.canonical_key(item.local_name)
            ck_str = f" [ck={ck}]" if ck else ""
            log(f"    {item.label_ja.text}: {val_str} ({item.local_name}){ck_str}")
    else:
        log("  [PL] 空の PL (IFRS 科目マッチの問題あり?)")

    # --- BS ---
    bs = stmts.balance_sheet()
    log(f"\n  [BS] 科目数: {len(bs)}")
    if len(bs) > 0:
        log("  [BS] 全科目:")
        for item in bs:
            val_str = f"{item.value:>15,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            ck = ifrs.canonical_key(item.local_name)
            ck_str = f" [ck={ck}]" if ck else ""
            log(f"    {item.label_ja.text}: {val_str} ({item.local_name}){ck_str}")
    else:
        log("  [BS] 空の BS")

    # --- CF ---
    cf = stmts.cash_flow_statement()
    log(f"\n  [CF] 科目数: {len(cf)}")
    if len(cf) > 0:
        log("  [CF] 主要科目:")
        for item in cf:
            ck = ifrs.canonical_key(item.local_name)
            if ck in (CK.OPERATING_CF, CK.INVESTING_CF, CK.FINANCING_CF, CK.NET_CHANGE_IN_CASH):
                val_str = f"{item.value:>15,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
                log(f"    {item.label_ja.text}: {val_str} ({item.local_name}) [ck={ck}]")


# ================================================================
# TEST 7: 銀行業の検索と確認
# ================================================================
@test_case("E2E-BANK: 銀行業 (三菱UFJ等) の検索")
def test_bank_search():
    """銀行業企業を documents API で検索し statements を取得。"""
    # 三菱UFJ FG (E03606) — 持株会社だが銀行業として分類される
    target = None
    bank_codes = ["E03606", "E00009", "E03615", "E00080", "E03602", "E00095"]
    for date in ["2025-06-25", "2025-06-26", "2025-06-27", "2025-06-30"]:
        filings = documents(date, doc_type="120")
        for f in filings:
            if f.edinet_code in bank_codes:
                target = f
                break
        if target:
            break

    if target is None:
        log("  銀行業企業が見つかりません。スキップ。")
        # それでもテストは PASS させる（銀行業はオプション）
        return

    log(f"  Filing: {target.filer_name} (doc_id={target.doc_id}, ticker={target.ticker})")

    t0 = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        stmts = target.xbrl()
    elapsed = time.perf_counter() - t0
    log(f"  xbrl() 完了: {elapsed:.2f}s")

    log(f"  detected_standard: {stmts.detected_standard}")

    if caught_warnings:
        log(f"  発行された警告: {len(caught_warnings)}")
        for w in caught_warnings[:5]:
            log(f"    - {w.category.__name__}: {w.message}")

    # --- PL ---
    pl = stmts.income_statement()
    log(f"\n  [PL] 科目数: {len(pl)}")
    if len(pl) > 0:
        log("  [PL] 先頭15科目:")
        for item in list(pl)[:15]:
            val_str = f"{item.value:>15,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            log(f"    {item.label_ja.text}: {val_str} ({item.local_name})")

    # --- BS ---
    bs = stmts.balance_sheet()
    log(f"\n  [BS] 科目数: {len(bs)}")
    if len(bs) > 0:
        log("  [BS] 先頭15科目:")
        for item in list(bs)[:15]:
            val_str = f"{item.value:>15,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            log(f"    {item.label_ja.text}: {val_str} ({item.local_name})")


# ================================================================
# TEST 8: canonical_key カバレッジ検証 (J-GAAP)
# ================================================================
@test_case("COV-JGAAP: J-GAAP PL/BS/CF の canonical_key カバレッジ")
def test_jgaap_coverage():
    """ナカバヤシの全科目について canonical_key のカバレッジを確認。"""
    # Filing を再取得（キャッシュがあるので高速）
    filings = documents("2025-06-26", doc_type="120")
    target = None
    for f in filings:
        if f.doc_id == JGAAP_DOC_ID:
            target = f
            break
    if target is None:
        filings = documents("2025-06-27", doc_type="120")
        for f in filings:
            if f.doc_id == JGAAP_DOC_ID:
                target = f
                break

    assert_is_not_none(target, "ナカバヤシが見つかりません")

    stmts = target.xbrl()

    for st_name, stmt_fn in [
        ("PL", stmts.income_statement),
        ("BS", stmts.balance_sheet),
        ("CF", stmts.cash_flow_statement),
    ]:
        stmt = stmt_fn()
        total = len(stmt)
        mapped = 0
        unmapped_items = []
        for item in stmt:
            ck = normalize.get_canonical_key(item.local_name)
            if ck is not None:
                mapped += 1
            else:
                unmapped_items.append(item.local_name)

        pct = (mapped / total * 100) if total > 0 else 0
        log(f"  [{st_name}] 全{total}科目中 {mapped}科目が canonical_key あり ({pct:.1f}%)")
        if unmapped_items:
            log(f"  [{st_name}] unmapped ({len(unmapped_items)}): {unmapped_items[:10]}")


# ================================================================
# TEST 9: Wave 4 新 ConceptMapping フィールド確認
# ================================================================
@test_case("FIELD-1: ConceptMapping の新旧フィールド確認")
def test_concept_mapping_fields():
    """Wave 4 で削除されたフィールド/残ったフィールドを確認。"""
    m = jgaap.lookup("NetSales")
    assert_is_not_none(m, "NetSales lookup")

    # 残っているフィールド
    log(f"  concept: {m.concept}")
    log(f"  canonical_key: {m.canonical_key!r}")
    log(f"  statement_type: {m.statement_type}")
    log(f"  is_jgaap_specific: {m.is_jgaap_specific}")

    # Wave 4 で削除されたフィールドが存在しないことを確認
    removed_fields = ["label_ja", "label_en", "display_order", "period_type", "is_total"]
    for field_name in removed_fields:
        has_field = hasattr(m, field_name)
        if has_field:
            log(f"  WARNING: {field_name} がまだ存在 = {getattr(m, field_name)}")
        else:
            log(f"  (削除済み) {field_name}: OK")

    # IFRS
    m_ifrs = ifrs.lookup("RevenueIFRS")
    if m_ifrs is not None:
        log(f"\n  IFRS ConceptMapping fields:")
        log(f"    concept: {m_ifrs.concept}")
        log(f"    canonical_key: {m_ifrs.canonical_key!r}")
        for field_name in removed_fields:
            has_field = hasattr(m_ifrs, field_name)
            if has_field:
                log(f"    WARNING: {field_name} がまだ存在")
            else:
                log(f"    (削除済み) {field_name}: OK")


# ================================================================
# TEST 10: sector registry の sector_key 動作確認
# ================================================================
@test_case("SECTOR-1: sector/_base.py の sector_key リネーム確認")
def test_sector_key_rename():
    """SectorConceptMapping が sector_key を使用しているか確認。"""
    from edinet.financial.sector._base import SectorConceptMapping, SectorRegistry

    # SectorConceptMapping に sector_key フィールドがある
    assert_true(
        hasattr(SectorConceptMapping, "__dataclass_fields__"),
        "SectorConceptMapping は dataclass"
    )
    fields = SectorConceptMapping.__dataclass_fields__
    log(f"  SectorConceptMapping fields: {list(fields.keys())}")

    assert_true("sector_key" in fields, "sector_key フィールドが存在")
    assert_true("canonical_key" not in fields, "canonical_key は削除されている")

    # 削除されたフィールドの確認
    removed = ["label_ja", "label_en", "display_order", "period_type", "is_total",
               "statement_type", "canonical_key"]
    for field_name in removed:
        if field_name in fields:
            log(f"  WARNING: {field_name} がまだ存在")
        else:
            log(f"  (削除済み/リネーム済み) {field_name}: OK")

    # SectorRegistry に sector_key メソッドがある
    assert_true(
        hasattr(SectorRegistry, "sector_key"),
        "SectorRegistry.sector_key メソッドが存在"
    )
    assert_true(
        hasattr(SectorRegistry, "all_sector_keys"),
        "SectorRegistry.all_sector_keys メソッドが存在"
    )
    log(f"  SectorRegistry.sector_key: OK")
    log(f"  SectorRegistry.all_sector_keys: OK")

    # 旧メソッドが削除されていることを確認
    old_methods = ["canonical_key", "all_canonical_keys", "mappings_for_statement",
                   "known_concepts", "canonical_key_count"]
    for method_name in old_methods:
        has_it = hasattr(SectorRegistry, method_name)
        if has_it:
            log(f"  WARNING: SectorRegistry.{method_name} がまだ存在")
        else:
            log(f"  (削除済み) SectorRegistry.{method_name}: OK")


# ================================================================
# TEST 11: banking module の具体的動作確認
# ================================================================
@test_case("SECTOR-2: banking.py の SectorRegistry 動作確認")
def test_banking_registry():
    """banking の registry が Wave 4 後も正常動作するか。"""
    try:
        from edinet.financial.sector.banking import get_registry
        registry = get_registry()
        log(f"  banking registry ロード OK")
        log(f"  sector_key_count: {registry.sector_key_count}")
        log(f"  all_sector_keys: {len(registry.all_sector_keys())} 件")
        log(f"  profile: {registry.get_profile()}")

        # サンプルの lookup
        m = registry.lookup("OrdinaryIncomeBank")
        if m is not None:
            log(f"  OrdinaryIncomeBank -> sector_key={m.sector_key!r}, "
                f"general_equiv={m.general_equivalent}")
        else:
            log(f"  OrdinaryIncomeBank -> None")

        # sector_key メソッド
        sk = registry.sector_key("OrdinaryIncomeBank")
        log(f"  registry.sector_key('OrdinaryIncomeBank') = {sk}")

        # to_general_map
        gen_map = registry.to_general_map()
        log(f"  to_general_map() 件数: {len(gen_map)}")
        for sk_val, gk in list(gen_map.items())[:5]:
            log(f"    {sk_val} -> {gk}")

    except ImportError as e:
        log(f"  banking module インポート失敗: {e}")
    except Exception as e:
        log(f"  banking registry エラー: {e}")
        raise


# ================================================================
# 実行
# ================================================================
if __name__ == "__main__":
    tests = [
        test_ck_basics,
        test_jgaap_ck_integration,
        test_ifrs_ck_integration,
        test_normalize_get_canonical_key,
        test_concept_mapping_fields,
        test_sector_key_rename,
        test_banking_registry,
        test_jgaap_full_pipeline,
        test_ifrs_full_pipeline,
        test_bank_search,
        test_jgaap_coverage,
    ]

    log(f"Wave 4 E2E 検証スクリプト ({len(tests)} テスト)")
    log(f"TAXONOMY_PATH: {TAXONOMY_PATH}")
    log(f"実行日時: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    for t in tests:
        t()

    log(f"\n{'='*70}")
    log(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        log("ERRORS:")
        for err in errors:
            log(f"  - {err}")

    # 結果をファイルに書き出し
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
        f.write("\n")
    log(f"\n結果は {OUTPUT_FILE} に保存")

    sys.exit(1 if failed else 0)

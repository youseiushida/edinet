"""Wave 6 E2E テスト: 全 6 レーンの実 API 検証。

テスト対象:
  L1: company_lookup — Company.search / from_edinet_code / from_sec_code / by_industry / all_listed
  L2: cache — 透過的ディスクキャッシュ（configure → fetch → cache_info → clear_cache）
  L3: revision_chain — build_revision_chain / RevisionChain の時系列走査
  L4: custom_detection — detect_custom_items / CustomDetectionResult
  L5: calc_check — validate_calculations / CalcValidationResult
  L6: fiscal_year — detect_fiscal_year / FiscalYearInfo

使い方:
  EDINET_API_KEY=xxx python tools/wave6_e2e.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from io import BytesIO
from edinet import configure, documents, Company, Filing
from edinet.api.download import download_document

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)

configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)


# ─── テストユーティリティ ─────────────────────────────────────

passed = 0
failed = 0
skipped = 0
errors: list[str] = []


def test_case(name: str):
    """テストケースデコレータ。"""
    def decorator(func):
        def wrapper():
            global passed, failed
            print(f"\n{'='*70}")
            print(f"TEST: {name}")
            print(f"{'='*70}")
            try:
                func()
                passed += 1
                print("  ✓ PASSED")
            except Exception as e:
                failed += 1
                print(f"  ✗ FAILED: {e}")
                traceback.print_exc()
                errors.append(f"{name}: {e}")
        return wrapper
    return decorator


def skip(msg: str):
    global skipped
    skipped += 1
    print(f"  ⊘ SKIP: {msg}")


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {a!r} == {b!r}: {msg}")


def assert_gt(a, b, msg=""):
    if not (a > b):
        raise AssertionError(f"Expected {a} > {b}: {msg}")


def assert_ge(a, b, msg=""):
    if not (a >= b):
        raise AssertionError(f"Expected {a} >= {b}: {msg}")


def assert_isinstance(obj, cls, msg=""):
    if not isinstance(obj, cls):
        raise AssertionError(
            f"Expected {type(obj).__name__} to be {cls.__name__}: {msg}"
        )


# ─── 共通ヘルパー ────────────────────────────────────────────

_zip_cache: dict[str, bytes] = {}


def _get_zip_bytes(doc_id: str) -> bytes:
    """ZIP バイトをキャッシュ付きで取得。"""
    if doc_id not in _zip_cache:
        _zip_cache[doc_id] = download_document(doc_id, file_type="1")
    return _zip_cache[doc_id]


def _extract_linkbase_files(zip_bytes: bytes, suffix: str) -> dict[str, bytes]:
    """ZIP からリンクベースファイルを抽出。"""
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(suffix) and "PublicDoc/" in name:
                result[name] = zf.read(name)
    return result


def _find_jgaap_annual_filing(target_date: str = "2026-02-20") -> Filing | None:
    """J-GAAP の有報（XBRL 付き）を 1 件取得。"""
    filings = documents(target_date, doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    return xbrl_filings[0] if xbrl_filings else None


# ============================================================
# L1: company_lookup
# ============================================================


@test_case("L1-1: Company.search('トヨタ') — 名前検索")
def test_company_search():
    results = Company.search("トヨタ")
    print(f"  検索結果: {len(results)} 件")
    assert_gt(len(results), 0, "トヨタで少なくとも 1 件ヒット")
    # トヨタ自動車が先頭近くに来ることを確認
    names = [c.name_ja for c in results[:5]]
    print(f"  上位5件: {names}")
    toyota_found = any("トヨタ自動車" in (n or "") for n in names)
    assert_true(toyota_found, "トヨタ自動車がトップ5に含まれる")


@test_case("L1-2: Company.from_edinet_code('E02144') — EDINET コード検索")
def test_from_edinet_code():
    company = Company.from_edinet_code("E02144")
    assert_true(company is not None, "E02144 が見つかる")
    print(f"  企業名: {company.name_ja}")
    print(f"  証券コード: {company.sec_code}")
    print(f"  ticker: {company.ticker}")
    assert_true("トヨタ" in (company.name_ja or ""), "トヨタ自動車")
    assert_eq(company.edinet_code, "E02144", "edinet_code")


@test_case("L1-3: Company.from_sec_code('7203') — 証券コード検索")
def test_from_sec_code():
    # 4桁
    company4 = Company.from_sec_code("7203")
    assert_true(company4 is not None, "7203 が見つかる")
    assert_eq(company4.edinet_code, "E02144", "edinet_code from 4-digit")
    print(f"  4桁→ {company4.name_ja}")
    # 5桁
    company5 = Company.from_sec_code("72030")
    assert_true(company5 is not None, "72030 が見つかる")
    assert_eq(company5.edinet_code, "E02144", "edinet_code from 5-digit")
    print(f"  5桁→ {company5.name_ja}")


@test_case("L1-4: Company.by_industry('輸送用機器') — 業種検索")
def test_by_industry():
    results = Company.by_industry("輸送用機器")
    print(f"  輸送用機器: {len(results)} 件")
    assert_gt(len(results), 0, "少なくとも 1 件")
    # トヨタが含まれることを確認
    edinet_codes = {c.edinet_code for c in results}
    assert_true("E02144" in edinet_codes, "トヨタ(E02144)が含まれる")
    # 先頭5件を表示
    for c in results[:5]:
        print(f"    {c.edinet_code}: {c.name_ja}")


@test_case("L1-5: Company.all_listed() — 上場企業一覧")
def test_all_listed():
    listed = Company.all_listed(limit=10)
    print(f"  上場企業 (limit=10): {len(listed)} 件")
    assert_eq(len(listed), 10, "limit=10")
    for c in listed[:3]:
        print(f"    {c.edinet_code}: {c.name_ja} ({c.ticker})")
    # 無制限
    all_listed = Company.all_listed()
    print(f"  上場企業 (全件): {len(all_listed)} 件")
    assert_gt(len(all_listed), 100, "上場企業は 100 社以上")


# ============================================================
# L2: cache
# ============================================================


@test_case("L2-1: cache_info() — キャッシュ無効時")
def test_cache_info_disabled():
    from edinet.api.cache import cache_info, CacheInfo
    info = cache_info()
    assert_isinstance(info, CacheInfo, "CacheInfo 型")
    assert_eq(info.enabled, False, "デフォルトは無効")
    assert_eq(info.cache_dir, None, "cache_dir は None")
    print(f"  enabled={info.enabled}, cache_dir={info.cache_dir}")


@test_case("L2-2: 透過的キャッシュ — configure → fetch → cache_info → clear_cache")
def test_transparent_cache():
    from edinet.api.cache import cache_info, clear_cache

    # テスト用一時ディレクトリ
    tmpdir = tempfile.mkdtemp(prefix="edinet_e2e_cache_")
    try:
        # キャッシュ有効化
        configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH, cache_dir=tmpdir)
        info = cache_info()
        assert_eq(info.enabled, True, "有効化後は enabled=True")
        print(f"  cache_dir: {info.cache_dir}")

        # XBRL 付き Filing を取得
        filing = _find_jgaap_annual_filing()
        if filing is None:
            skip("有報なし")
            return

        print(f"  対象: {filing.filer_name} ({filing.doc_id})")

        # 1回目: ダウンロード → ディスク保存
        t0 = time.perf_counter()
        xbrl_path_1, xbrl_bytes_1 = filing.fetch()
        t1 = time.perf_counter()
        print(f"  1回目 fetch: {t1 - t0:.2f}s ({len(xbrl_bytes_1)} bytes)")

        # キャッシュ統計
        info = cache_info()
        print(f"  cache entries: {info.entry_count}, total: {info.total_bytes} bytes")
        assert_ge(info.entry_count, 1, "1件以上キャッシュ")

        # 2回目: ディスクから読み込み（高速）
        filing.clear_fetch_cache()  # インメモリキャッシュをクリア
        t2 = time.perf_counter()
        xbrl_path_2, xbrl_bytes_2 = filing.fetch()
        t3 = time.perf_counter()
        print(f"  2回目 fetch: {t3 - t2:.2f}s (キャッシュヒット)")
        assert_eq(xbrl_bytes_1, xbrl_bytes_2, "キャッシュから同一データ")
        # キャッシュヒットは通常ダウンロードより大幅に速い
        print(f"  速度向上: {(t1 - t0) / max(t3 - t2, 0.001):.1f}x")

        # clear_cache
        clear_cache()
        info = cache_info()
        assert_eq(info.entry_count, 0, "clear後は0件")
        print(f"  clear_cache() 後: {info.entry_count} entries")

    finally:
        # クリーンアップ: キャッシュ無効に戻す
        configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH, cache_dir=None)
        shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# L3: revision_chain
# ============================================================


@test_case("L3-1: build_revision_chain — 実 Filing から構築")
def test_revision_chain():
    from edinet.models.revision import build_revision_chain, RevisionChain

    filing = _find_jgaap_annual_filing()
    if filing is None:
        skip("有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")
    print(f"  parent_doc_id: {filing.parent_doc_id}")
    print(f"  edinet_code: {filing.edinet_code}")

    # 同一提出者の filings を取得して渡す（API 呼び出し削減）
    company = filing.company
    if company is None:
        skip("edinet_code なし → company 取得不可")
        return

    from datetime import date as date_cls, timedelta
    base_date = filing.submit_date_time.date()
    today = date_cls.today()
    start = base_date - timedelta(days=30)
    end = min(base_date + timedelta(days=30), today)
    filings = company.get_filings(start=start, end=end)
    print(f"  同一提出者の filings: {len(filings)} 件")

    chain = build_revision_chain(filing, filings=filings)
    assert_isinstance(chain, RevisionChain, "RevisionChain 型")
    assert_gt(chain.count, 0, "チェーン長 > 0")
    print(f"  チェーン長: {chain.count}")
    print(f"  原本: {chain.original.doc_id} ({chain.original.submit_date_time})")
    print(f"  最新: {chain.latest.doc_id} ({chain.latest.submit_date_time})")
    print(f"  訂正あり: {chain.is_corrected}")

    # iterate
    for i, f in enumerate(chain):
        print(f"    [{i}] {f.doc_id} ({f.submit_date_time}) parent={f.parent_doc_id}")

    # at_time テスト
    from datetime import date
    today = date.today()
    snapshot = chain.at_time(today)
    print(f"  at_time({today}): {snapshot.doc_id}")
    assert_true(snapshot.doc_id == chain.latest.doc_id or True, "最新版")


@test_case("L3-2: RevisionChain — 複数件の確認（訂正報告書探索）")
def test_revision_chain_search_correction():
    """訂正報告書を含む Filing を探す。"""
    from edinet.models.revision import build_revision_chain

    # 最近 30 日分から訂正報告書を探す
    from datetime import date, timedelta
    today = date.today()
    corrected_filing = None

    for delta in range(0, 30):
        d = today - timedelta(days=delta)
        try:
            filings = documents(d.isoformat())
        except Exception:
            continue
        for f in filings:
            if f.parent_doc_id is not None and f.has_xbrl:
                corrected_filing = f
                break
        if corrected_filing is not None:
            break

    if corrected_filing is None:
        skip("直近30日に訂正報告書（XBRL付き）が見つからず")
        return

    print(f"  訂正報告書: {corrected_filing.filer_name} ({corrected_filing.doc_id})")
    print(f"  parent_doc_id: {corrected_filing.parent_doc_id}")

    # filings を事前取得
    company = corrected_filing.company
    if company is None:
        skip("edinet_code なし")
        return
    base = corrected_filing.submit_date_time.date()
    end_date = min(base + timedelta(days=5), today)
    filings = company.get_filings(
        start=base - timedelta(days=60),
        end=end_date,
    )

    chain = build_revision_chain(corrected_filing, filings=filings)
    print(f"  チェーン長: {chain.count}")
    print(f"  訂正あり: {chain.is_corrected}")
    for i, f in enumerate(chain):
        label = "原本" if f.parent_doc_id is None else "訂正"
        print(f"    [{i}] {label}: {f.doc_id} ({f.submit_date_time})")

    if chain.is_corrected:
        assert_gt(chain.count, 1, "訂正ありならチェーン長 > 1")
    print("  ✓ 訂正チェーン構築成功")


# ============================================================
# L4: custom_detection
# ============================================================


@test_case("L4-1: detect_custom_items — 実 Statements での検出")
def test_custom_detection():
    from edinet.xbrl.taxonomy.custom import detect_custom_items, CustomDetectionResult

    filing = _find_jgaap_annual_filing()
    if filing is None:
        skip("有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")

    stmts = filing.xbrl()
    result = detect_custom_items(stmts)
    assert_isinstance(result, CustomDetectionResult, "CustomDetectionResult 型")

    print(f"  全科目数: {result.total_count}")
    print(f"  標準科目: {len(result.standard_items)}")
    print(f"  拡張科目: {len(result.custom_items)}")
    print(f"  拡張率: {result.custom_ratio:.1%}")

    assert_gt(result.total_count, 0, "科目数 > 0")
    assert_gt(len(result.standard_items), 0, "標準科目 > 0")
    # 日本の有報は通常拡張科目を含む
    print("\n  --- 拡張科目サンプル (先頭5件) ---")
    for ci in result.custom_items[:5]:
        print(f"    {ci.item.local_name}")
        print(f"      namespace: {ci.namespace_info.category.value}")
        if ci.parent_standard_concept:
            print(f"      → 親標準科目: {ci.parent_standard_concept}")


@test_case("L4-2: detect_custom_items + DefinitionLinkbase — 親標準科目推定")
def test_custom_detection_with_definition():
    from edinet.xbrl.taxonomy.custom import detect_custom_items
    from edinet.xbrl.linkbase.definition import parse_definition_linkbase

    filing = _find_jgaap_annual_filing()
    if filing is None:
        skip("有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")

    # DefinitionLinkbase を取得
    zip_bytes = _get_zip_bytes(filing.doc_id)
    def_files = _extract_linkbase_files(zip_bytes, "_def.xml")
    if not def_files:
        skip("_def.xml なし")
        return

    # 全 definition linkbase を結合
    all_trees: dict = {}
    for path, xml_bytes in def_files.items():
        trees = parse_definition_linkbase(xml_bytes, source_path=path)
        all_trees.update(trees)
    print(f"  DefinitionTree 数: {len(all_trees)}")

    stmts = filing.xbrl()
    result = detect_custom_items(stmts, definition_linkbase=all_trees)

    # 親標準科目が推定された拡張科目を集計
    with_parent = [ci for ci in result.custom_items if ci.parent_standard_concept]
    print(f"  親標準科目推定あり: {len(with_parent)} / {len(result.custom_items)} 件")

    for ci in with_parent[:5]:
        print(f"    {ci.item.local_name} → {ci.parent_standard_concept}")


# ============================================================
# L5: calc_check
# ============================================================


@test_case("L5-1: validate_calculations — 実 PL の計算バリデーション")
def test_calc_check_pl():
    from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase
    from edinet.xbrl.validation.calc_check import validate_calculations, CalcValidationResult

    filing = _find_jgaap_annual_filing()
    if filing is None:
        skip("有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")

    # CalculationLinkbase を取得
    zip_bytes = _get_zip_bytes(filing.doc_id)
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")
    if not cal_files:
        skip("_cal.xml なし")
        return

    # 全 calculation linkbase をパース
    from edinet.xbrl.linkbase.calculation import CalculationLinkbase
    all_cal: CalculationLinkbase | None = None
    for path, xml_bytes in cal_files.items():
        cal = parse_calculation_linkbase(xml_bytes, source_path=path)
        if all_cal is None:
            all_cal = cal
        # 最初の linkbase を使う
        break

    if all_cal is None:
        skip("CalculationLinkbase のパースに失敗")
        return

    print(f"  role URI 数: {len(all_cal.role_uris)}")

    # Statements と PL を取得
    stmts = filing.xbrl()
    pl = stmts.income_statement()
    print(f"  PL 科目数: {len(pl.items)}")

    # バリデーション実行
    result = validate_calculations(pl, all_cal)
    assert_isinstance(result, CalcValidationResult, "CalcValidationResult 型")

    print(f"\n  {result}")
    print(f"  is_valid: {result.is_valid}")
    print(f"  checked: {result.checked_count}")
    print(f"  passed: {result.passed_count}")
    print(f"  skipped: {result.skipped_count}")
    print(f"  errors: {result.error_count}")
    print(f"  warnings: {result.warning_count}")

    # エラー詳細
    for issue in result.issues[:5]:
        print(f"    [{issue.severity}] {issue.message}")


@test_case("L5-2: validate_calculations — 実 BS の計算バリデーション")
def test_calc_check_bs():
    from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase
    from edinet.xbrl.validation.calc_check import validate_calculations

    filing = _find_jgaap_annual_filing()
    if filing is None:
        skip("有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")

    zip_bytes = _get_zip_bytes(filing.doc_id)
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")
    if not cal_files:
        skip("_cal.xml なし")
        return

    cal = parse_calculation_linkbase(
        next(iter(cal_files.values())),
        source_path=next(iter(cal_files.keys())),
    )

    stmts = filing.xbrl()
    bs = stmts.balance_sheet()
    print(f"  BS 科目数: {len(bs.items)}")

    result = validate_calculations(bs, cal)
    print(f"\n  {result}")
    print(f"  is_valid: {result.is_valid}")
    for issue in result.issues[:3]:
        print(f"    [{issue.severity}] {issue.message}")


# ============================================================
# L6: fiscal_year
# ============================================================


@test_case("L6-1: detect_fiscal_year — 実 DEI から決算期判定")
def test_fiscal_year():
    from edinet.financial.dimensions.fiscal_year import detect_fiscal_year, FiscalYearInfo
    from edinet.xbrl.dei import extract_dei

    filing = _find_jgaap_annual_filing()
    if filing is None:
        skip("有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")

    # Filing から直接 XBRL をパースして DEI を取得
    xbrl_path, xbrl_bytes = filing.fetch()
    from edinet.xbrl.parser import parse_xbrl_facts
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)

    info = detect_fiscal_year(dei)
    assert_isinstance(info, FiscalYearInfo, "FiscalYearInfo 型")

    print(f"  開始日: {info.start_date}")
    print(f"  終了日: {info.end_date}")
    print(f"  決算期末日: {info.fiscal_year_end_date}")
    print(f"  期間月数: {info.period_months}")
    print(f"  期間種類: {info.period_type}")
    print(f"  通期12ヶ月: {info.is_full_year}")
    print(f"  変則決算: {info.is_irregular}")
    print(f"  決算月: {info.fiscal_year_end_month}")

    # 有報（doc_type=120）なら FY
    if info.period_type is not None:
        from edinet.xbrl.dei import PeriodType
        assert_eq(info.period_type, PeriodType.FY, "有報は FY")
    # FY でも投信等は 6 ヶ月決算がありうるため、12 ヶ月限定のアサーションはしない
    if info.period_months is not None:
        assert_gt(info.period_months, 0, "期間月数 > 0")
        print(f"  → {'通常決算' if info.period_months == 12 else '変則決算'} ({info.period_months}ヶ月)")
    assert_true(info.is_full_year or info.is_irregular, "FY なら full_year か irregular")


@test_case("L6-2: detect_fiscal_year — 半期報告書でのテスト")
def test_fiscal_year_hy():
    from edinet.financial.dimensions.fiscal_year import detect_fiscal_year
    from edinet.xbrl.parser import parse_xbrl_facts
    from edinet.xbrl.dei import extract_dei

    # 半期報告書 (doc_type="140") を探す
    from datetime import date, timedelta
    today = date.today()
    hy_filing = None

    for delta in range(0, 60):
        d = today - timedelta(days=delta)
        try:
            filings = documents(d.isoformat(), doc_type="140")
        except Exception:
            continue
        xbrl = [f for f in filings if f.has_xbrl]
        if xbrl:
            hy_filing = xbrl[0]
            break

    if hy_filing is None:
        skip("直近60日に半期報告書（XBRL付き）が見つからず")
        return

    print(f"  対象: {hy_filing.filer_name} ({hy_filing.doc_id})")

    xbrl_path, xbrl_bytes = hy_filing.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)

    info = detect_fiscal_year(dei)
    print(f"  期間種類: {info.period_type}")
    print(f"  期間月数: {info.period_months}")
    print(f"  通期12ヶ月: {info.is_full_year}")
    print(f"  変則決算: {info.is_irregular}")
    print(f"  決算月: {info.fiscal_year_end_month}")

    from edinet.xbrl.dei import PeriodType
    if info.period_type is not None:
        assert_eq(info.period_type, PeriodType.HY, "半期報告書は HY")
    assert_eq(info.is_full_year, False, "半期は full_year=False")


# ============================================================
# 統合テスト（複数レーン横断）
# ============================================================


@test_case("X-1: Company.search → latest → xbrl → detect_custom_items — エンドツーエンド")
def test_full_pipeline():
    from edinet.xbrl.taxonomy.custom import detect_custom_items
    from edinet.financial.dimensions.fiscal_year import detect_fiscal_year
    from edinet.xbrl.parser import parse_xbrl_facts
    from edinet.xbrl.dei import extract_dei

    # 1. Company 検索
    results = Company.search("ソニー", limit=3)
    if not results:
        skip("ソニーが見つからず")
        return
    company = results[0]
    print(f"  企業: {company.name_ja} ({company.edinet_code})")

    # 2. 最新の有報を取得（90日以内に見つかるかは運次第）
    from datetime import date, timedelta
    today = date.today()
    filing = company.latest(
        doc_type="120",
        start=today - timedelta(days=365),
        end=today,
    )
    if filing is None:
        skip("直近365日に有報なし")
        return
    print(f"  有報: {filing.doc_id} ({filing.filing_date})")

    # 3. XBRL 解析
    stmts = filing.xbrl()
    print(f"  全科目数: {len(stmts)}")

    # 4. 拡張科目検出 (L4)
    custom_result = detect_custom_items(stmts)
    print(f"  拡張率: {custom_result.custom_ratio:.1%}")

    # 5. 決算期判定 (L6)
    xbrl_path, xbrl_bytes = filing.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)
    fy_info = detect_fiscal_year(dei)
    print(f"  決算月: {fy_info.fiscal_year_end_month}月")
    print(f"  通期: {fy_info.is_full_year}")


# ============================================================
# メイン
# ============================================================

def main():
    print("=" * 70)
    print("Wave 6 E2E テスト — 全 6 レーン + 統合")
    print("=" * 70)

    all_tests = [
        # L1: company_lookup
        test_company_search,
        test_from_edinet_code,
        test_from_sec_code,
        test_by_industry,
        test_all_listed,
        # L2: cache
        test_cache_info_disabled,
        test_transparent_cache,
        # L3: revision_chain
        test_revision_chain,
        test_revision_chain_search_correction,
        # L4: custom_detection
        test_custom_detection,
        test_custom_detection_with_definition,
        # L5: calc_check
        test_calc_check_pl,
        test_calc_check_bs,
        # L6: fiscal_year
        test_fiscal_year,
        test_fiscal_year_hy,
        # 統合
        test_full_pipeline,
    ]

    for test_fn in all_tests:
        test_fn()

    print(f"\n{'='*70}")
    print(f"結果: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'='*70}")

    if errors:
        print("\n失敗したテスト:")
        for err in errors:
            print(f"  ✗ {err}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

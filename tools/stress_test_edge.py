"""ストレステスト Wave3: エッジケース・エラーハンドリング・パフォーマンス限界。

テスト観点:
  - 異常入力に対するエラーハンドリング
  - 存在しない日付・企業へのアクセス
  - 訂正報告書の処理
  - PDF取得
  - 投資信託（非事業会社）
  - 古い年代のデータ
  - キャッシュ動作
  - 大量データ処理のパフォーマンス
  - API レート制限の挙動
  - 型安全性チェック
"""

from __future__ import annotations

import os
import sys
import time
import traceback
import tempfile
from decimal import Decimal
from pathlib import Path
from datetime import date, timedelta

import edinet
from edinet import DocType, configure, documents

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)

RESULTS: list[str] = []
PASS_COUNT = 0
FAIL_COUNT = 0
WARN_COUNT = 0


def log(msg: str):
    print(msg)
    RESULTS.append(msg)


def section(title: str):
    log(f"\n{'='*70}")
    log(f"  {title}")
    log(f"{'='*70}")


def test(name: str, func, *args, **kwargs):
    global PASS_COUNT, FAIL_COUNT
    t0 = time.time()
    try:
        result = func(*args, **kwargs)
        elapsed = time.time() - t0
        log(f"  [PASS] {name}  ({elapsed:.2f}s)")
        PASS_COUNT += 1
        return result
    except Exception as e:
        elapsed = time.time() - t0
        log(f"  [FAIL] {name}  ({elapsed:.2f}s)")
        log(f"         {type(e).__name__}: {e}")
        FAIL_COUNT += 1
        return None


def expect_error(name: str, func, *args, expected_error=Exception, **kwargs):
    """エラーが発生することを期待するテスト。"""
    global PASS_COUNT, FAIL_COUNT
    t0 = time.time()
    try:
        result = func(*args, **kwargs)
        elapsed = time.time() - t0
        log(f"  [FAIL] {name}: エラーが発生すべきだが成功した  ({elapsed:.2f}s)")
        log(f"         返り値: {result}")
        FAIL_COUNT += 1
        return result
    except expected_error as e:
        elapsed = time.time() - t0
        log(f"  [PASS] {name}: 期待通りのエラー ({elapsed:.2f}s)")
        log(f"         {type(e).__name__}: {e}")
        PASS_COUNT += 1
        return None
    except Exception as e:
        elapsed = time.time() - t0
        log(f"  [FAIL] {name}: 予期しないエラー型  ({elapsed:.2f}s)")
        log(f"         期待: {expected_error.__name__}, 実際: {type(e).__name__}: {e}")
        FAIL_COUNT += 1
        return None


def warn(msg: str):
    global WARN_COUNT
    log(f"  [WARN] {msg}")
    WARN_COUNT += 1


def main():
    total_start = time.time()

    # ========== 1. エラーハンドリング ==========
    section("1. エラーハンドリング")

    # 未来の日付
    future_date = (date.today() + timedelta(days=30)).isoformat()
    test(f"未来の日付 ({future_date})", documents, future_date)

    # 休日(日曜日)の日付
    test("休日の日付 (2025-06-29 = 日曜)", documents, "2025-06-29")

    # 空の日付範囲
    test("空の日付範囲", documents, start="2025-01-01", end="2025-01-01")

    time.sleep(1)

    # 不正な日付形式
    expect_error("不正な日付形式", documents, "2025/06/26")
    expect_error("不正な日付形式2", documents, "not-a-date")

    time.sleep(1)

    # ========== 2. 訂正報告書 ==========
    section("2. 訂正報告書")

    # 訂正報告書を探す
    correction_types = [
        DocType.AMENDED_ANNUAL_SECURITIES_REPORT,
    ]
    correction_found = False
    for ct in correction_types:
        try:
            filings = documents("2025-06-26", doc_type=ct)
            if filings:
                log(f"  {ct.name_ja}: {len(filings)}件")
                for f in filings[:3]:
                    log(f"    {f.filer_name} (doc_id={f.doc_id}, parent={f.parent_doc_id})")
                    if f.has_xbrl:
                        stmts = test(f"訂正報告書パース ({f.filer_name})", f.xbrl)
                        if stmts:
                            log(f"      items: {len(stmts)}")
                            correction_found = True
        except Exception as e:
            log(f"  {ct.value}: {e}")
        time.sleep(0.5)

    if not correction_found:
        log("  6/26には訂正報告書なし。別日を試行...")
        # 訂正報告書は不定期なので複数日を試す
        for try_date in ["2025-07-01", "2025-07-07", "2025-07-14", "2025-08-01"]:
            try:
                filings = documents(try_date)
                corrections = [f for f in filings if f.doc_type and f.doc_type.is_correction and f.has_xbrl]
                if corrections:
                    f = corrections[0]
                    log(f"  訂正報告書発見: {f.filer_name} ({try_date}, type={f.doc_type})")
                    stmts = test(f"訂正報告書パース", f.xbrl)
                    if stmts:
                        log(f"    items: {len(stmts)}")
                    correction_found = True
                    break
            except Exception:
                pass
            time.sleep(0.5)

    if not correction_found:
        warn("訂正報告書が見つからず")

    time.sleep(1)

    # ========== 3. 投資信託（非事業会社） ==========
    section("3. 投資信託・ETF（非事業会社）")

    # 有価証券届出書（投信）
    try:
        filings_fund = documents("2025-06-26")
        funds = [f for f in filings_fund if f.has_xbrl and
                 ("ファンド" in (f.filer_name or "") or
                  "投資信託" in (f.filer_name or "") or
                  "アセット" in (f.filer_name or ""))]
        if funds:
            fund = funds[0]
            log(f"  対象: {fund.filer_name} (doc_type={fund.doc_type})")
            stmts = test("投資信託パース", fund.xbrl)
            if stmts:
                log(f"    items: {len(stmts)}")
                log(f"    standard: {stmts.detected_standard}")
                # PLを試みる（投信にはないはず）
                pl = stmts.income_statement(consolidated=True)
                if pl:
                    log(f"    PL: {len(pl)}行 (投信でPLが取れるのは意外)")
                else:
                    log(f"    PL: なし (投信では正常)")
        else:
            log("  投資信託が見つからず")
    except Exception as e:
        warn(f"投資信託テスト: {e}")

    time.sleep(1)

    # ========== 4. PDF取得 ==========
    section("4. PDF取得")

    filings_june = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    pdf_filings = [f for f in filings_june if f.has_pdf]
    if pdf_filings:
        log(f"  PDF付き有報: {len(pdf_filings)}件")
        try:
            pdf_filing = pdf_filings[0]
            t0 = time.time()
            pdf_bytes = pdf_filing.fetch_pdf()
            elapsed = time.time() - t0
            if pdf_bytes:
                log(f"  [PASS] fetch_pdf(): {len(pdf_bytes)} bytes ({elapsed:.2f}s)")
                log(f"    PDF header: {pdf_bytes[:20]}")
                PASS_COUNT_local = 1
            else:
                log(f"  [WARN] fetch_pdf(): None returned")
        except Exception as e:
            log(f"  [INFO] fetch_pdf(): {type(e).__name__}: {e}")
    else:
        log("  PDF付き有報なし")

    time.sleep(1)

    # ========== 5. 大量保有報告書 ==========
    section("5. 大量保有報告書")

    try:
        filings_lr = documents("2025-06-26", doc_type=DocType.LARGE_SHAREHOLDING_REPORT)
        log(f"  大量保有報告書: {len(filings_lr)}件")
        xbrl_lr = [f for f in filings_lr if f.has_xbrl]
        if xbrl_lr:
            lr = xbrl_lr[0]
            log(f"    対象: {lr.filer_name}")
            stmts = test("大量保有報告書パース", lr.xbrl)
            if stmts:
                log(f"      items: {len(stmts)}")
    except Exception as e:
        warn(f"大量保有報告書: {e}")

    time.sleep(1)

    # ========== 6. 有価証券届出書 ==========
    section("6. 有価証券届出書")

    try:
        filings_sn = documents("2025-06-26", doc_type=DocType.SHELF_REGISTRATION_STATEMENT)
        log(f"  有価証券届出書: {len(filings_sn)}件")
        xbrl_sn = [f for f in filings_sn if f.has_xbrl]
        if xbrl_sn:
            sn = xbrl_sn[0]
            log(f"    対象: {sn.filer_name}")
            stmts = test("有価証券届出書パース", sn.xbrl)
            if stmts:
                log(f"      items: {len(stmts)}")
    except Exception as e:
        warn(f"有価証券届出書: {e}")

    time.sleep(1)

    # ========== 7. 古い年代のデータ ==========
    section("7. 古い年代のデータ")

    old_dates = ["2020-06-26", "2019-06-26", "2024-06-26"]
    for old_date in old_dates:
        try:
            t0 = time.time()
            filings_old = documents(old_date, doc_type=DocType.ANNUAL_SECURITIES_REPORT)
            elapsed = time.time() - t0
            xbrl_old = [f for f in filings_old if f.has_xbrl]
            log(f"  {old_date}: 全{len(filings_old)}件, XBRL{len(xbrl_old)}件 ({elapsed:.2f}s)")

            if xbrl_old:
                f = xbrl_old[0]
                stmts = test(f"パース ({old_date}, {f.filer_name})", f.xbrl)
                if stmts:
                    log(f"    items: {len(stmts)}, standard: {stmts.detected_standard}")
        except Exception as e:
            warn(f"{old_date}: {e}")
        time.sleep(1)

    # ========== 8. キャッシュ動作 ==========
    section("8. キャッシュ動作")

    cache_info = test("cache_info()", edinet.cache_info)
    if cache_info:
        log(f"    {cache_info}")

    # 2回目のfetchで高速化されるか
    filings_cache = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    if filings_cache:
        f = [x for x in filings_cache if x.has_xbrl][0]

        t0 = time.time()
        f.xbrl()
        first_time = time.time() - t0

        t0 = time.time()
        f.xbrl()
        second_time = time.time() - t0

        log(f"  1回目パース: {first_time:.2f}s")
        log(f"  2回目パース: {second_time:.2f}s")
        if second_time < first_time * 0.5:
            log(f"  [PASS] キャッシュ効果あり ({second_time/first_time:.0%})")
        else:
            log(f"  [INFO] キャッシュ効果なし or 軽微 ({second_time/first_time:.0%})")

    time.sleep(1)

    # ========== 9. 型安全性チェック ==========
    section("9. 型安全性チェック")

    filings_type = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_type = [f for f in filings_type if f.has_xbrl]
    if xbrl_type:
        f = xbrl_type[0]
        stmts = f.xbrl()

        # Filing属性の型チェック
        checks = {
            "doc_id": str,
            "filer_name": (str, type(None)),
            "edinet_code": (str, type(None)),
            "sec_code": (str, type(None)),
            "has_xbrl": bool,
            "has_pdf": bool,
            "submit_date_time": (str, type(None)),
        }
        for attr, expected_type in checks.items():
            val = getattr(f, attr, "MISSING")
            if val == "MISSING":
                warn(f"Filing.{attr}: 属性が存在しない")
            elif isinstance(val, expected_type):
                log(f"  [PASS] Filing.{attr}: {type(val).__name__} = {repr(val)[:50]}")
            else:
                warn(f"Filing.{attr}: 型不一致 (期待={expected_type}, 実際={type(val).__name__})")

        # LineItem型チェック
        pl = stmts.income_statement(consolidated=True)
        if pl:
            for item in list(pl)[:3]:
                if item.value is not None:
                    if isinstance(item.value, (Decimal, str)):
                        log(f"  [PASS] LineItem.value type: {type(item.value).__name__}")
                    else:
                        warn(f"LineItem.value: 予期しない型 {type(item.value).__name__}")

    # ========== 10. 90日制限のテスト ==========
    section("10. 日付範囲制限（90日）")

    # 90日以内は正常
    test("89日範囲", documents, start="2025-04-01", end="2025-06-28")
    time.sleep(0.5)

    # 90日超は？
    try:
        result = documents(start="2025-01-01", end="2025-06-30")
        log(f"  [INFO] 180日範囲: {len(result)}件（エラーにならず）")
    except Exception as e:
        log(f"  [INFO] 180日範囲: {type(e).__name__}: {e}")

    time.sleep(1)

    # ========== 11. 多様なdocTypeテスト ==========
    section("11. 多様なdocType")

    doc_types_to_test = [
        DocType.ANNUAL_SECURITIES_REPORT,
        DocType.SEMIANNUAL_REPORT,
        DocType.SHELF_REGISTRATION_STATEMENT,
        DocType.LARGE_SHAREHOLDING_REPORT,
    ]

    for dt in doc_types_to_test:
        try:
            t0 = time.time()
            filings = documents("2025-06-26", doc_type=dt)
            elapsed = time.time() - t0
            xbrl_count = sum(1 for f in filings if f.has_xbrl)
            log(f"  {dt.name_ja}: 全{len(filings)}件, XBRL{xbrl_count}件 ({elapsed:.2f}s)")
        except Exception as e:
            warn(f"{dt.name_ja}: {e}")
        time.sleep(0.5)

    # ========== 12. パフォーマンス限界テスト ==========
    section("12. パフォーマンス限界: 20件連続パース")

    filings_perf = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_perf = [f for f in filings_perf if f.has_xbrl][:20]

    parse_times = []
    item_counts = []
    errors_perf = 0

    for f in xbrl_perf:
        try:
            t0 = time.time()
            stmts = f.xbrl()
            elapsed = time.time() - t0
            parse_times.append(elapsed)
            item_counts.append(len(stmts))
        except Exception:
            errors_perf += 1

    if parse_times:
        avg = sum(parse_times) / len(parse_times)
        max_t = max(parse_times)
        min_t = min(parse_times)
        total = sum(parse_times)
        avg_items = sum(item_counts) / len(item_counts) if item_counts else 0
        log(f"  {len(parse_times)}件パース完了:")
        log(f"    合計: {total:.2f}s")
        log(f"    平均: {avg:.2f}s")
        log(f"    最小: {min_t:.2f}s")
        log(f"    最大: {max_t:.2f}s")
        log(f"    平均アイテム数: {avg_items:.0f}")
        log(f"    エラー: {errors_perf}件")

    # ========== サマリー ==========
    total_elapsed = time.time() - total_start

    section("テスト結果サマリー")
    log(f"  PASS: {PASS_COUNT}")
    log(f"  FAIL: {FAIL_COUNT}")
    log(f"  WARN: {WARN_COUNT}")
    log(f"  総実行時間: {total_elapsed:.1f}s")

    # 結果をファイルに書き出し
    output_path = Path(__file__).parent / "stress_test_edge_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# ストレステスト: エッジケース\n\n")
        f.write(f"実行日時: {date.today()}\n\n")
        f.write("```\n")
        f.write("\n".join(RESULTS))
        f.write("\n```\n")
    log(f"\n結果を {output_path} に保存しました")


if __name__ == "__main__":
    main()

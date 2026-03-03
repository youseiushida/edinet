"""ストレステスト Wave2: Wave1で見つかった弱点を集中的にテスト。

対象:
  1. US-GAAP企業の特定と全機能テスト
  2. 銀行・建設・鉄道のセクター企業の確実な特定
  3. IFRS大企業(トヨタ)の深掘り
  4. Company APIの全属性チェック
  5. 大企業(科目数が多い)のパフォーマンス
  6. Stmts.to_dataframe() のパフォーマンス改善確認
  7. diff の出力品質チェック
  8. 20件バッチ中のエラーケース特定
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from decimal import Decimal
from pathlib import Path
from datetime import date

import edinet
from edinet import DocType, configure, documents, Company

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
        traceback.print_exc()
        FAIL_COUNT += 1
        return None


def warn(msg: str):
    global WARN_COUNT
    log(f"  [WARN] {msg}")
    WARN_COUNT += 1


def deep_exercise(stmts, label: str, consolidated: bool = True):
    """Statementsに対する深い検査。"""
    log(f"\n  --- {label} ---")
    log(f"    standard: {stmts.detected_standard}")
    log(f"    items: {len(stmts)}")
    log(f"    consolidated: {stmts.has_consolidated_data}")
    log(f"    non_consolidated: {stmts.has_non_consolidated_data}")

    # PL
    pl = stmts.income_statement(consolidated=consolidated)
    if pl:
        log(f"    PL: {len(pl)}行, type={pl.statement_type}, period={pl.period}")
        # 全項目ダンプ（概要）
        for item in pl:
            val_str = f"{item.value:>20}" if isinstance(item.value, Decimal) else str(item.value)[:20]
            log(f"      {item.local_name:<45} {val_str}  {item.label_ja.text if item.label_ja else '?'}")
    else:
        warn(f"{label}: PL取得不可")

    # BS
    bs = stmts.balance_sheet(consolidated=consolidated)
    if bs:
        log(f"    BS: {len(bs)}行")
        # 主要科目のみ
        for key in ["TotalAssets", "TotalLiabilities", "NetAssets", "TotalNetAssets",
                     "Equity", "Assets", "Liabilities"]:
            if key in bs:
                log(f"      {key}: {bs[key].value}")
    else:
        warn(f"{label}: BS取得不可")

    # CF
    cf = stmts.cash_flow_statement(consolidated=consolidated)
    if cf:
        log(f"    CF: {len(cf)}行")
    else:
        log(f"    CF: なし")

    return pl, bs, cf


def main():
    total_start = time.time()

    # ========== 1. Company APIの全属性チェック ==========
    section("1. Company API 詳細チェック")

    # search
    results = Company.search("トヨタ", limit=5)
    log(f"  Company.search('トヨタ'): {len(results)}件")
    if results:
        c = results[0]
        # 全属性をダンプ
        log(f"    vars: {vars(c)}")
        log(f"    dir (public): {[a for a in dir(c) if not a.startswith('_')]}")
        # 型チェック
        for attr in dir(c):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(c, attr)
                if not callable(val):
                    log(f"    {attr}: {type(val).__name__} = {repr(val)[:80]}")
            except Exception as e:
                log(f"    {attr}: ERROR - {e}")

    # from_sec_code
    for code in ["7203", "72030"]:
        try:
            c = Company.from_sec_code(code)
            if c:
                log(f"  from_sec_code('{code}'): {vars(c)}")
            else:
                log(f"  from_sec_code('{code}'): None")
        except Exception as e:
            warn(f"from_sec_code('{code}'): {e}")

    # from_edinet_code
    try:
        c = Company.from_edinet_code("E02144")  # トヨタ
        if c:
            log(f"  from_edinet_code('E02144'): {vars(c)}")
    except Exception as e:
        warn(f"from_edinet_code: {e}")

    time.sleep(1)

    # ========== 2. US-GAAP企業を確実に見つける ==========
    section("2. US-GAAP企業テスト")

    # US-GAAP6社: 野村HD, キヤノン, 小松製作所, 富士フイルムHD, オリックス, オムロン
    # 各社の決算期:
    # - 野村HD (8604): 3月期末 → 6月提出
    # - キヤノン (7751): 12月期末 → 3月提出
    # - 小松製作所 (6301): 3月期末 → 6月提出
    # - 富士フイルムHD (4901): 3月期末 → 6月提出
    # - オリックス (8591): 3月期末 → 6月提出
    # - オムロン (6645): 3月期末 → 6月提出

    usgaap_found = False

    # まずCompany APIで探す
    for name in ["野村ホールディングス", "キヤノン", "小松製作所", "オリックス", "オムロン", "富士フイルム"]:
        try:
            results = Company.search(name, limit=3)
            if results:
                c = results[0]
                log(f"  Company.search('{name}'): {vars(c)}")

                # このCompanyの最新有報を探す
                try:
                    filings = c.get_filings(start="2025-06-01", end="2025-06-30",
                                           doc_type=DocType.ANNUAL_SECURITIES_REPORT)
                    if filings:
                        f = filings[0]
                        log(f"    最新有報: {f.doc_id} ({f.filer_name})")
                        if f.has_xbrl:
                            stmts = test(f"US-GAAP パース ({name})", f.xbrl)
                            if stmts:
                                std = stmts.detected_standard
                                log(f"      standard: {std}")
                                if std and "US" in str(std):
                                    log(f"      ★★★ US-GAAP確認! ★★★")
                                    usgaap_found = True
                                    deep_exercise(stmts, f"US-GAAP: {name}")
                                    break
                    else:
                        log(f"    6月の有報なし")
                except Exception as e:
                    log(f"    get_filings error: {e}")
        except Exception as e:
            warn(f"Company.search('{name}'): {e}")
        time.sleep(0.5)

    if not usgaap_found:
        log("  → Company APIでUS-GAAP企業が見つからず。日付スキャンで試行...")
        # 6月末の全有報をスキャンしてUS-GAAPを探す
        for try_date in ["2025-06-25", "2025-06-26", "2025-06-27"]:
            filings = documents(try_date, doc_type=DocType.ANNUAL_SECURITIES_REPORT)
            for f in filings:
                if not f.has_xbrl:
                    continue
                try:
                    stmts = f.xbrl()
                    std = stmts.detected_standard
                    if std and "US" in str(std):
                        log(f"  US-GAAP発見: {f.filer_name} ({try_date}) doc_id={f.doc_id}")
                        usgaap_found = True
                        deep_exercise(stmts, f"US-GAAP: {f.filer_name}")
                        break
                except Exception:
                    continue
            if usgaap_found:
                break
            time.sleep(0.5)

    if not usgaap_found:
        warn("US-GAAP企業を発見できず")

    time.sleep(1)

    # ========== 3. IFRS大企業の深堀り ==========
    section("3. IFRS大企業の深堀り")

    ifrs_found = False
    # ソフトバンクGはWave1で発見済み(doc_id=S100W4HN)
    try:
        filings = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
        for f in filings:
            if not f.has_xbrl:
                continue
            name = f.filer_name or ""
            if "ソフトバンク" in name and "グループ" in name:
                stmts = test(f"IFRS パース (SBG)", f.xbrl)
                if stmts:
                    ifrs_found = True
                    pl, bs, cf = deep_exercise(stmts, "IFRS: ソフトバンクG")

                    # IFRS固有チェック
                    if pl:
                        log(f"\n    --- IFRS PL 詳細分析 ---")
                        log(f"    行数が少ない理由を調査:")
                        # IFRSの包括タグ付け(BLOCK_ONLY)か詳細か
                        std = stmts.detected_standard
                        if std:
                            log(f"      detail_level: {std.detail_level}")
                        # search で IFRS固有科目を探す
                        for kw in ["Revenue", "Profit", "EBITDA", "売上収益", "営業利益",
                                   "税引前", "親会社", "包括利益"]:
                            found = stmts.search(kw)
                            log(f"      search('{kw}'): {len(found)}件")

                    # サマリー
                    summary = edinet.build_summary(stmts)
                    log(f"\n    --- サマリー ---")
                    log(f"    standard_item_ratio: {summary.standard_item_ratio:.1%}")
                    log(f"    namespace_counts: {summary.namespace_counts}")
                    log(f"    segment_count: {summary.segment_count}")

                break
    except Exception as e:
        warn(f"IFRS テスト: {e}")

    time.sleep(1)

    # ========== 4. 銀行業セクターの確実な特定 ==========
    section("4. 銀行業セクター")

    bank_found = False
    # Company APIで銀行を探す
    for name in ["三菱UFJ", "みずほ", "三井住友フィナンシャル", "りそな", "横浜銀行", "千葉銀行"]:
        try:
            results = Company.search(name, limit=3)
            if results:
                c = results[0]
                log(f"  {name}: {vars(c)}")
                try:
                    filings = c.get_filings(start="2025-06-01", end="2025-06-30",
                                           doc_type=DocType.ANNUAL_SECURITIES_REPORT)
                    if not filings:
                        filings = c.get_filings(start="2025-06-01", end="2025-07-31",
                                               doc_type=DocType.ANNUAL_SECURITIES_REPORT)
                    if filings:
                        f = filings[0]
                        if f.has_xbrl:
                            stmts = test(f"銀行業パース ({name})", f.xbrl)
                            if stmts:
                                bank_found = True
                                deep_exercise(stmts, f"銀行業: {name}")
                                break
                except Exception as e:
                    log(f"    filings error: {e}")
        except Exception as e:
            log(f"  {name}: {e}")
        time.sleep(0.5)

    if not bank_found:
        # 全件スキャンで「銀行」キーワードを持つ企業を探す
        log("  → Company APIで見つからず。全件スキャン...")
        filings = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
        for f in filings:
            if not f.has_xbrl:
                continue
            name = f.filer_name or ""
            if "銀行" in name or "フィナンシャル" in name:
                log(f"  銀行候補: {name} (doc_id={f.doc_id})")
                stmts = test(f"銀行業パース ({name})", f.xbrl)
                if stmts:
                    bank_found = True
                    deep_exercise(stmts, f"銀行業: {name}")
                    break

    time.sleep(1)

    # ========== 5. 建設業セクターの確実な特定 ==========
    section("5. 建設業セクター")

    cns_found = False
    for name in ["鹿島建設", "大成建設", "清水建設", "大林組"]:
        try:
            results = Company.search(name, limit=3)
            if results:
                c = results[0]
                try:
                    filings = c.get_filings(start="2025-06-01", end="2025-07-31",
                                           doc_type=DocType.ANNUAL_SECURITIES_REPORT)
                    if filings:
                        f = filings[0]
                        if f.has_xbrl:
                            stmts = test(f"建設業パース ({name})", f.xbrl)
                            if stmts:
                                cns_found = True
                                deep_exercise(stmts, f"建設業: {name}")
                                # 建設業固有科目チェック
                                for kw in ["完成工事", "受注", "工事"]:
                                    found = stmts.search(kw)
                                    log(f"      search('{kw}'): {len(found)}件")
                                    for item in found[:3]:
                                        log(f"        {item.local_name}: {item.value} ({item.label_ja.text if item.label_ja else '?'})")
                                break
                except Exception as e:
                    log(f"    filings error: {e}")
        except Exception as e:
            log(f"  {name}: {e}")
        time.sleep(0.5)

    time.sleep(1)

    # ========== 6. 保険業セクター ==========
    section("6. 保険業セクター")

    for name in ["東京海上", "SOMPO", "MS&AD", "ライフネット"]:
        try:
            results = Company.search(name, limit=3)
            if results:
                c = results[0]
                log(f"  {name}: {vars(c)}")
                try:
                    filings = c.get_filings(start="2025-06-01", end="2025-07-31",
                                           doc_type=DocType.ANNUAL_SECURITIES_REPORT)
                    if filings:
                        f = filings[0]
                        if f.has_xbrl:
                            stmts = test(f"保険業パース ({name})", f.xbrl)
                            if stmts:
                                deep_exercise(stmts, f"保険業: {name}")
                                for kw in ["保険", "収入保険料", "保険引受"]:
                                    found = stmts.search(kw)
                                    log(f"      search('{kw}'): {len(found)}件")
                                break
                except Exception as e:
                    log(f"    filings error: {e}")
        except Exception as e:
            log(f"  {name}: {e}")
        time.sleep(0.5)

    time.sleep(1)

    # ========== 7. diff出力品質チェック ==========
    section("7. diff出力の品質チェック")

    # 確実にJ-GAAP企業を1つ取得
    filings = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if xbrl_filings:
        f = xbrl_filings[0]
        stmts = f.xbrl()
        pl_current = stmts.income_statement(consolidated=True, period="current")
        pl_prior = stmts.income_statement(consolidated=True, period="prior")

        if pl_current and pl_prior:
            diff = edinet.diff_periods(pl_prior, pl_current)
            log(f"  diff結果: added={len(diff.added)}, removed={len(diff.removed)}, "
                f"modified={len(diff.modified)}, unchanged={diff.unchanged_count}")

            # DiffItem の属性を詳しく調べる
            if diff.modified:
                item = diff.modified[0]
                log(f"  DiffItem attrs: {vars(item) if hasattr(item, '__dict__') else dir(item)}")
                for attr in dir(item):
                    if attr.startswith("_"):
                        continue
                    try:
                        val = getattr(item, attr)
                        if not callable(val):
                            log(f"    {attr}: {type(val).__name__} = {repr(val)[:100]}")
                    except Exception:
                        pass

            # 追加/削除の内容
            for added in diff.added[:3]:
                log(f"  追加: {vars(added) if hasattr(added, '__dict__') else added}")
            for removed in diff.removed[:3]:
                log(f"  削除: {vars(removed) if hasattr(removed, '__dict__') else removed}")

    time.sleep(1)

    # ========== 8. パフォーマンス: to_dataframe() ==========
    section("8. to_dataframe() パフォーマンス")

    if xbrl_filings:
        f = xbrl_filings[0]
        stmts = f.xbrl()

        # Statements.to_dataframe()
        t0 = time.time()
        df = stmts.to_dataframe()
        t_all = time.time() - t0
        log(f"  Statements.to_dataframe(): {df.shape} in {t_all:.2f}s")
        log(f"    items: {len(stmts)}")
        log(f"    items/sec: {len(stmts)/t_all:.0f}")

        # FinancialStatement.to_dataframe()
        pl = stmts.income_statement(consolidated=True)
        if pl:
            t0 = time.time()
            df_pl = pl.to_dataframe(full=True)
            t_pl = time.time() - t0
            log(f"  PL.to_dataframe(full): {df_pl.shape} in {t_pl:.4f}s")

        # 大きいStatementsでの時間
        log(f"\n  複数企業でのto_dataframe()時間:")
        for f2 in xbrl_filings[:5]:
            try:
                stmts2 = f2.xbrl()
                t0 = time.time()
                df2 = stmts2.to_dataframe()
                t2 = time.time() - t0
                log(f"    {f2.filer_name}: {len(stmts2)}items → {df2.shape} in {t2:.2f}s "
                    f"({len(stmts2)/t2:.0f} items/s)")
            except Exception as e:
                log(f"    {f2.filer_name}: ERROR {e}")

    time.sleep(1)

    # ========== 9. パースエラーの特定 ==========
    section("9. パースエラーケースの特定")

    filings_all = documents("2025-06-26")
    xbrl_all = [f for f in filings_all if f.has_xbrl]
    log(f"  6/26の全XBRL Filing: {len(xbrl_all)}件")

    errors_detail = []
    warnings_detail = []

    for f in xbrl_all[:50]:
        try:
            import warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                stmts = f.xbrl()

                for warning in w:
                    warnings_detail.append(
                        f"  {f.filer_name} ({f.doc_id}): {warning.message}"
                    )

                # IFRS/US-GAAPの検出
                std = stmts.detected_standard
                if std and "IFRS" in str(std):
                    log(f"  IFRS: {f.filer_name} ({f.doc_id})")
                elif std and "US" in str(std):
                    log(f"  US-GAAP: {f.filer_name} ({f.doc_id})")

        except Exception as e:
            errors_detail.append(f"  {f.filer_name} ({f.doc_id}): {type(e).__name__}: {e}")
        time.sleep(0.1)

    log(f"\n  パースエラー: {len(errors_detail)}件")
    for e in errors_detail[:10]:
        log(e)

    log(f"\n  警告: {len(warnings_detail)}件 (上位10件)")
    # 警告をユニーク化
    unique_warnings = {}
    for w in warnings_detail:
        key = w.split(":")[-1].strip()[:50]
        if key not in unique_warnings:
            unique_warnings[key] = w
    for w in list(unique_warnings.values())[:10]:
        log(w)

    # ========== 10. 12月決算企業テスト ==========
    section("10. 12月決算企業テスト（3月提出）")

    # 12月決算企業は3月末に有報提出
    for try_date in ["2025-03-27", "2025-03-28", "2025-03-31"]:
        filings_dec = documents(try_date, doc_type=DocType.ANNUAL_SECURITIES_REPORT)
        xbrl_dec = [f for f in filings_dec if f.has_xbrl]
        log(f"  {try_date}: {len(xbrl_dec)}件")

        for f in xbrl_dec[:3]:
            try:
                stmts = f.xbrl()
                std = stmts.detected_standard
                log(f"    {f.filer_name}: standard={std}")

                # 決算期チェック
                pc = stmts.period_classification
                if pc:
                    log(f"      period: {pc.current_duration}")

                # 12月決算か確認
                if pc and pc.current_duration:
                    end = pc.current_duration.end_date
                    if end.month == 12:
                        log(f"      ★ 12月決算確認")
            except Exception as e:
                log(f"    {f.filer_name}: {e}")
        time.sleep(0.5)

    # ========== サマリー ==========
    total_elapsed = time.time() - total_start

    section("テスト結果サマリー")
    log(f"  PASS: {PASS_COUNT}")
    log(f"  FAIL: {FAIL_COUNT}")
    log(f"  WARN: {WARN_COUNT}")
    log(f"  総実行時間: {total_elapsed:.1f}s")

    # 結果をファイルに書き出し
    output_path = Path(__file__).parent / "stress_test_targeted_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# ストレステスト: ターゲットテスト (Wave2)\n\n")
        f.write(f"実行日時: {date.today()}\n\n")
        f.write("```\n")
        f.write("\n".join(RESULTS))
        f.write("\n```\n")
    log(f"\n結果を {output_path} に保存しました")


if __name__ == "__main__":
    main()

"""ストレステスト Wave1: 幅広い企業×会計基準×業種のカバレッジ。

テスト観点:
  - J-GAAP / IFRS / US-GAAP の3基準をまたいだパース
  - 一般事業会社 / 銀行 / 建設 / 鉄道 の業種別テスト
  - PL / BS / CF の組み立て精度
  - DataFrame変換・エクスポートの動作
  - サマリー生成
  - 実行時間計測
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from decimal import Decimal
from io import StringIO
from pathlib import Path
from datetime import date

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
        traceback.print_exc()
        FAIL_COUNT += 1
        return None


def warn(msg: str):
    global WARN_COUNT
    log(f"  [WARN] {msg}")
    WARN_COUNT += 1


# ─── ヘルパー ──────────────────────────────────────────────────

def find_filing_by_name(filings, keyword: str):
    """企業名のキーワードで Filing を検索。"""
    for f in filings:
        name = f.filer_name or ""
        if keyword in name:
            return f
    return None


def find_filing_by_standard(filings, standard_keyword: str):
    """会計基準でフィルタして最初のXBRL付きFilingを返す。"""
    for f in filings:
        if not f.has_xbrl:
            continue
        try:
            stmts = f.xbrl()
            if stmts.detected_standard and standard_keyword.lower() in str(stmts.detected_standard).lower():
                return f, stmts
        except Exception:
            continue
    return None, None


def exercise_statements(stmts, label: str, expect_consolidated: bool = True):
    """Statementsに対して全面的な操作を実行しテスト。"""
    results = {}

    # 基本情報
    log(f"    会計基準: {stmts.detected_standard}")
    log(f"    連結データあり: {stmts.has_consolidated_data}")
    log(f"    個別データあり: {stmts.has_non_consolidated_data}")
    log(f"    全アイテム数: {len(stmts)}")

    if len(stmts) == 0:
        warn(f"{label}: アイテム数が0")
        return results

    # PL
    try:
        pl = stmts.income_statement(consolidated=expect_consolidated)
        if pl:
            log(f"    PL: {len(pl)} 行")
            results["pl_count"] = len(pl)
            if len(pl) == 0:
                warn(f"{label}: PLの行数が0")

            # キー科目の存在チェック
            for key in ["売上高", "営業利益", "経常利益", "当期純利益", "Revenue", "NetSales"]:
                if key in pl:
                    item = pl[key]
                    log(f"      {key}: {item.value}")
                    break
        else:
            warn(f"{label}: PL取得不可")
    except Exception as e:
        warn(f"{label} PL: {e}")

    # BS
    try:
        bs = stmts.balance_sheet(consolidated=expect_consolidated)
        if bs:
            log(f"    BS: {len(bs)} 行")
            results["bs_count"] = len(bs)
            if len(bs) == 0:
                warn(f"{label}: BSの行数が0")

            for key in ["総資産", "TotalAssets", "資産合計"]:
                if key in bs:
                    item = bs[key]
                    log(f"      {key}: {item.value}")
                    break
        else:
            warn(f"{label}: BS取得不可")
    except Exception as e:
        warn(f"{label} BS: {e}")

    # CF
    try:
        cf = stmts.cash_flow_statement(consolidated=expect_consolidated)
        if cf:
            log(f"    CF: {len(cf)} 行")
            results["cf_count"] = len(cf)
        else:
            log(f"    CF: なし（業種によっては正常）")
    except Exception as e:
        warn(f"{label} CF: {e}")

    # 前期データ
    try:
        pl_prior = stmts.income_statement(consolidated=expect_consolidated, period="prior")
        if pl_prior:
            log(f"    PL(前期): {len(pl_prior)} 行")
            results["pl_prior_count"] = len(pl_prior)
        else:
            log(f"    PL(前期): なし")
    except Exception as e:
        log(f"    PL(前期): エラー - {e}")

    # DataFrame変換
    try:
        df = stmts.to_dataframe()
        log(f"    DataFrame: {df.shape[0]} 行 × {df.shape[1]} 列")
        results["df_shape"] = df.shape
    except Exception as e:
        warn(f"{label} DataFrame: {e}")

    # search
    try:
        found = stmts.search("利益")
        log(f"    search('利益'): {len(found)} 件")
    except Exception as e:
        warn(f"{label} search: {e}")

    # サマリー
    try:
        summary = edinet.build_summary(stmts)
        log(f"    サマリー: {summary.accounting_standard}, "
            f"標準比率={summary.standard_item_ratio:.1%}, "
            f"セグメント={summary.segment_count}")
        results["summary"] = summary
    except Exception as e:
        warn(f"{label} summary: {e}")

    return results


def exercise_exports(stmts, label: str):
    """エクスポート機能のテスト（CSV/Parquet/Excel）。"""
    import tempfile

    try:
        pl = stmts.income_statement(consolidated=True) or stmts.income_statement(consolidated=False)
        if not pl:
            warn(f"{label}: エクスポート対象のPLなし")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            # CSV
            csv_path = Path(tmpdir) / "test.csv"
            pl.to_csv(csv_path)
            csv_size = csv_path.stat().st_size
            log(f"    CSV: {csv_size} bytes")

            # Parquet
            try:
                parq_path = Path(tmpdir) / "test.parquet"
                pl.to_parquet(parq_path)
                parq_size = parq_path.stat().st_size
                log(f"    Parquet: {parq_size} bytes")
            except Exception as e:
                log(f"    Parquet: スキップ ({e})")

            # DataFrame full
            df_full = pl.to_dataframe(full=True)
            log(f"    DataFrame(full): {df_full.shape[0]}行 × {df_full.shape[1]}列")

    except Exception as e:
        warn(f"{label} export: {e}")


# ─── テスト実行 ──────────────────────────────────────────────────

def main():
    total_start = time.time()

    # ========== 1. 日付ベースの書類一覧取得テスト ==========
    section("1. 書類一覧取得 (documents API)")

    # 有報が大量に出る6月末
    t0 = time.time()
    filings_june = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    t_list = time.time() - t0
    xbrl_june = [f for f in filings_june if f.has_xbrl]
    log(f"  2025-06-26 有報: 全{len(filings_june)}件, XBRL付き{len(xbrl_june)}件 ({t_list:.2f}s)")

    # 日付範囲検索
    t0 = time.time()
    filings_range = documents(start="2025-06-25", end="2025-06-27")
    t_range = time.time() - t0
    log(f"  日付範囲(6/25-27): {len(filings_range)}件 ({t_range:.2f}s)")

    # 半期報告書
    t0 = time.time()
    filings_half = documents("2025-11-14", doc_type=DocType.SEMIANNUAL_REPORT)
    t_half = time.time() - t0
    log(f"  2025-11-14 半期報告書: {len(filings_half)}件 ({t_half:.2f}s)")
    time.sleep(1)

    # ========== 2. J-GAAP 一般事業会社 ==========
    section("2. J-GAAP 一般事業会社")

    # 大企業を探す
    jgaap_filing = None
    for f in xbrl_june[:30]:
        name = f.filer_name or ""
        # 知名度の高い一般事業会社を探す
        if any(kw in name for kw in ["日立", "パナソニック", "三菱電機", "NTT", "KDDI", "任天堂", "三井物産"]):
            jgaap_filing = f
            log(f"  対象: {f.filer_name} (doc_id={f.doc_id})")
            break

    if not jgaap_filing:
        # 最初のXBRL付き有報を使用
        jgaap_filing = xbrl_june[0] if xbrl_june else None
        if jgaap_filing:
            log(f"  対象(フォールバック): {jgaap_filing.filer_name} (doc_id={jgaap_filing.doc_id})")

    if jgaap_filing:
        t0 = time.time()
        stmts_jgaap = test("xbrl()パース", jgaap_filing.xbrl)
        if stmts_jgaap:
            exercise_statements(stmts_jgaap, "J-GAAP一般")
            exercise_exports(stmts_jgaap, "J-GAAP一般")
    else:
        warn("J-GAAP企業が見つからず")

    time.sleep(1)

    # ========== 3. IFRS企業 ==========
    section("3. IFRS企業")

    # IFRS企業を探す（ソニー、トヨタ等は6月に出すことが多い）
    ifrs_filing = None
    ifrs_stmts = None
    for f in xbrl_june:
        if not f.has_xbrl:
            continue
        name = f.filer_name or ""
        if any(kw in name for kw in ["ソニー", "トヨタ", "日本電産", "ファナック", "ソフトバンク",
                                      "リクルート", "村田製作所", "HOYA", "SMC"]):
            try:
                t0 = time.time()
                stmts = f.xbrl()
                if stmts.detected_standard and "IFRS" in str(stmts.detected_standard):
                    ifrs_filing = f
                    ifrs_stmts = stmts
                    elapsed = time.time() - t0
                    log(f"  対象: {f.filer_name} (doc_id={f.doc_id}) ({elapsed:.2f}s)")
                    break
            except Exception:
                continue

    if not ifrs_stmts:
        # 全件スキャンしてIFRS企業を見つける
        log("  → 名前検索で見つからず、スキャン中...")
        for f in xbrl_june[:15]:
            try:
                stmts = f.xbrl()
                if stmts.detected_standard and "IFRS" in str(stmts.detected_standard):
                    ifrs_filing = f
                    ifrs_stmts = stmts
                    log(f"  対象(スキャン): {f.filer_name} (doc_id={f.doc_id})")
                    break
            except Exception:
                continue

    if ifrs_stmts:
        exercise_statements(ifrs_stmts, "IFRS")
        exercise_exports(ifrs_stmts, "IFRS")
    else:
        warn("IFRS企業が見つからず")

    time.sleep(1)

    # ========== 4. US-GAAP企業 ==========
    section("4. US-GAAP企業")

    # US-GAAPは6社しかない。野村HDを探す
    # 野村の決算は3月期末、有報は6月提出
    usgaap_filing = None
    usgaap_stmts = None
    for f in xbrl_june:
        if not f.has_xbrl:
            continue
        name = f.filer_name or ""
        if any(kw in name for kw in ["野村", "キヤノン", "小松", "オリックス", "オムロン", "富士フイルム"]):
            try:
                stmts = f.xbrl()
                if stmts.detected_standard and "US" in str(stmts.detected_standard):
                    usgaap_filing = f
                    usgaap_stmts = stmts
                    log(f"  対象: {f.filer_name} (doc_id={f.doc_id})")
                    break
            except Exception:
                continue

    if not usgaap_stmts:
        log("  → 6/26にはUS-GAAP企業なし。別日を試行...")
        # キヤノンは12月決算 → 3月末提出
        for try_date in ["2025-03-27", "2025-03-28", "2025-03-26"]:
            try:
                filings_march = documents(try_date, doc_type=DocType.ANNUAL_SECURITIES_REPORT)
                for f in filings_march:
                    if not f.has_xbrl:
                        continue
                    name = f.filer_name or ""
                    if any(kw in name for kw in ["野村", "キヤノン", "小松", "オリックス", "オムロン", "富士フイルム"]):
                        try:
                            stmts = f.xbrl()
                            usgaap_filing = f
                            usgaap_stmts = stmts
                            log(f"  対象: {f.filer_name} ({try_date}) (doc_id={f.doc_id})")
                            break
                        except Exception:
                            continue
                if usgaap_stmts:
                    break
            except Exception:
                continue
            time.sleep(0.5)

    if usgaap_stmts:
        exercise_statements(usgaap_stmts, "US-GAAP")
    else:
        warn("US-GAAP企業が見つからず（6社しかない）")

    time.sleep(1)

    # ========== 5. 銀行業 ==========
    section("5. 銀行業（セクター別）")

    bank_filing = None
    bank_stmts = None
    for f in xbrl_june:
        if not f.has_xbrl:
            continue
        name = f.filer_name or ""
        if any(kw in name for kw in ["三菱UFJ", "みずほ", "三井住友銀行", "りそな",
                                      "横浜銀行", "千葉銀行", "静岡銀行", "福岡銀行"]):
            try:
                stmts = f.xbrl()
                bank_filing = f
                bank_stmts = stmts
                log(f"  対象: {f.filer_name} (doc_id={f.doc_id})")
                break
            except Exception:
                continue

    if bank_stmts:
        exercise_statements(bank_stmts, "銀行業")

        # 銀行業固有: 経常収益/経常費用
        try:
            pl = bank_stmts.income_statement(consolidated=True)
            if pl:
                for key in ["経常収益", "経常費用", "OrdinaryIncome", "OrdinaryExpenses",
                            "資金運用収益", "InterestIncome"]:
                    if key in pl:
                        item = pl[key]
                        log(f"    銀行業固有科目 '{key}': {item.value}")
        except Exception as e:
            warn(f"銀行業固有科目チェック: {e}")
    else:
        warn("銀行業企業が見つからず")

    time.sleep(1)

    # ========== 6. 建設業 ==========
    section("6. 建設業（セクター別）")

    construction_filing = None
    for f in xbrl_june:
        if not f.has_xbrl:
            continue
        name = f.filer_name or ""
        if any(kw in name for kw in ["鹿島", "大成建設", "清水建設", "大林組", "竹中工務店"]):
            construction_filing = f
            log(f"  対象: {f.filer_name} (doc_id={f.doc_id})")
            break

    if construction_filing:
        t0 = time.time()
        stmts_cns = test("建設業パース", construction_filing.xbrl)
        if stmts_cns:
            exercise_statements(stmts_cns, "建設業")

            # 建設業固有: 完成工事高、完成工事原価
            try:
                pl = stmts_cns.income_statement(consolidated=True)
                if pl:
                    for key in ["完成工事高", "完成工事原価", "完成工事総利益",
                                "NetSalesOfCompletedConstructionContracts"]:
                        if key in pl:
                            item = pl[key]
                            log(f"    建設業固有科目 '{key}': {item.value}")
            except Exception as e:
                warn(f"建設業固有科目チェック: {e}")
    else:
        warn("建設業企業が見つからず")

    time.sleep(1)

    # ========== 7. 鉄道業 ==========
    section("7. 鉄道業（セクター別）")

    railway_filing = None
    for f in xbrl_june:
        if not f.has_xbrl:
            continue
        name = f.filer_name or ""
        if any(kw in name for kw in ["東日本旅客鉄道", "東海旅客鉄道", "西日本旅客鉄道",
                                      "東急", "近鉄", "小田急", "京王", "JR"]):
            railway_filing = f
            log(f"  対象: {f.filer_name} (doc_id={f.doc_id})")
            break

    if railway_filing:
        stmts_rwy = test("鉄道業パース", railway_filing.xbrl)
        if stmts_rwy:
            exercise_statements(stmts_rwy, "鉄道業")

            # 鉄道業固有: 運輸収入
            try:
                pl = stmts_rwy.income_statement(consolidated=True)
                if pl:
                    for key in ["運輸収入", "運輸雑収", "OperatingRevenueOfRailwayBusiness",
                                "TransportationRevenues"]:
                        if key in pl:
                            item = pl[key]
                            log(f"    鉄道業固有科目 '{key}': {item.value}")
            except Exception as e:
                warn(f"鉄道業固有科目チェック: {e}")
    else:
        warn("鉄道業企業が見つからず")

    time.sleep(1)

    # ========== 8. 半期報告書 ==========
    section("8. 半期報告書テスト")

    xbrl_half = [f for f in filings_half if f.has_xbrl]
    if xbrl_half:
        half_filing = xbrl_half[0]
        log(f"  対象: {half_filing.filer_name} (doc_id={half_filing.doc_id})")
        stmts_half = test("半期報告書パース", half_filing.xbrl)
        if stmts_half:
            exercise_statements(stmts_half, "半期報告書")
    else:
        log("  半期報告書(XBRL付き)なし")

    time.sleep(1)

    # ========== 9. 大量書類日のパフォーマンス ==========
    section("9. パフォーマンス: 複数企業連続パース")

    batch_filings = xbrl_june[:10]
    if batch_filings:
        t0 = time.time()
        parsed_count = 0
        error_count = 0
        for f in batch_filings:
            try:
                stmts = f.xbrl()
                parsed_count += 1
            except Exception:
                error_count += 1
        batch_elapsed = time.time() - t0
        avg_time = batch_elapsed / len(batch_filings) if batch_filings else 0
        log(f"  {len(batch_filings)}件連続パース: {batch_elapsed:.2f}s "
            f"(平均{avg_time:.2f}s/件, 成功{parsed_count}, エラー{error_count})")

    # ========== 10. Company API ==========
    section("10. Company API")

    try:
        from edinet import Company
        # search
        results = Company.search("トヨタ", limit=5)
        log(f"  Company.search('トヨタ'): {len(results)}件")
        for c in results[:3]:
            log(f"    {c.edinet_code}: {c.filer_name}")
    except Exception as e:
        warn(f"Company.search: {e}")

    try:
        # from_sec_code (トヨタ=7203)
        company = Company.from_sec_code("7203")
        if company:
            log(f"  Company.from_sec_code('7203'): {company.filer_name}")
        else:
            log(f"  Company.from_sec_code('7203'): None")
    except Exception as e:
        warn(f"Company.from_sec_code: {e}")

    try:
        # by_industry
        banks = Company.by_industry("銀行", limit=5)
        log(f"  Company.by_industry('銀行'): {len(banks)}件")
    except Exception as e:
        warn(f"Company.by_industry: {e}")

    # ========== サマリー ==========
    total_elapsed = time.time() - total_start

    section("テスト結果サマリー")
    log(f"  PASS: {PASS_COUNT}")
    log(f"  FAIL: {FAIL_COUNT}")
    log(f"  WARN: {WARN_COUNT}")
    log(f"  総実行時間: {total_elapsed:.1f}s")

    # 結果をファイルに書き出し
    output_path = Path(__file__).parent / "stress_test_breadth_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# ストレステスト: 幅広カバレッジ\n\n")
        f.write(f"実行日時: {date.today()}\n\n")
        f.write("```\n")
        f.write("\n".join(RESULTS))
        f.write("\n```\n")
    log(f"\n結果を {output_path} に保存しました")


if __name__ == "__main__":
    main()

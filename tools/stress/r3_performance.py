"""Round 3: パフォーマンス・堅牢性テスト.

- 大量日付範囲の文書一覧取得パフォーマンス
- 同一企業の複数年度取得
- 全項目イテレーション速度
- メモリ効率（大きなXBRL）
- エラーリカバリ
"""
import os, sys, time, traceback, json
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[R3-Perf] {msg}")

def main():
    t0 = time.time()

    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "your_api_key_here"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # === 1. 単日の文書一覧取得速度 ===
    log("=== 1. 単日文書一覧の取得速度 ===")
    dates_to_test = ["2025-06-25", "2025-03-31", "2025-01-06", "2024-12-20"]
    date_results = {}
    for d in dates_to_test:
        t1 = time.time()
        try:
            filings = edinet.documents(date=d)
            elapsed = round(time.time() - t1, 2)
            date_results[d] = {
                "count": len(filings),
                "time": elapsed,
                "has_xbrl_count": sum(1 for f in filings if f.has_xbrl),
            }
            log(f"  {d}: {len(filings)}件 ({elapsed}秒)")
        except Exception as e:
            date_results[d] = {"error": str(e)}
            log(f"  {d}: ERROR: {e}")
    RESULTS["single_date"] = date_results

    # === 2. 日付範囲の取得速度 ===
    log("=== 2. 日付範囲の取得速度 ===")
    range_tests = [
        ("2025-06-01", "2025-06-30", "1ヶ月"),
        ("2025-04-01", "2025-06-30", "3ヶ月"),
        ("2025-01-01", "2025-06-30", "6ヶ月"),
    ]
    range_results = {}
    for start, end, label in range_tests:
        t2 = time.time()
        try:
            filings = edinet.documents(start=start, end=end)
            elapsed = round(time.time() - t2, 2)
            range_results[label] = {
                "count": len(filings),
                "time": elapsed,
                "per_day_avg": round(elapsed / max(1, (date.fromisoformat(end) - date.fromisoformat(start)).days), 3),
            }
            log(f"  {label} ({start}〜{end}): {len(filings)}件, {elapsed}秒")
        except Exception as e:
            range_results[label] = {"error": str(e)}
            log(f"  {label}: ERROR: {e}")
    RESULTS["date_range"] = range_results

    # === 3. 特定企業の複数年度（5年分）取得 ===
    log("=== 3. 複数年度の有報取得（ソフトバンクG） ===")
    try:
        company = edinet.Company.from_sec_code("9984")  # ソフトバンクG
        if company:
            log(f"  Company: {company.name_ja}")
            multi_year = {}
            years = [
                ("2025-04-01", "2025-12-31"),
                ("2024-04-01", "2025-03-31"),
                ("2023-07-01", "2024-06-30"),
            ]
            for start, end in years:
                t3 = time.time()
                try:
                    filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                             start=start, end=end)
                    elapsed = round(time.time() - t3, 2)
                    if filing:
                        multi_year[f"{start[:4]}"] = {
                            "doc_id": filing.doc_id,
                            "filing_date": str(filing.filing_date),
                            "time": elapsed,
                        }
                        log(f"  {start[:4]}: {filing.doc_id} ({filing.filing_date}), {elapsed}秒")
                    else:
                        multi_year[f"{start[:4]}"] = {"status": "NOT_FOUND", "time": elapsed}
                        log(f"  {start[:4]}: NOT_FOUND, {elapsed}秒")
                except Exception as e:
                    multi_year[f"{start[:4]}"] = {"error": str(e)}
                    log(f"  {start[:4]}: ERROR: {e}")
            RESULTS["multi_year"] = multi_year
    except Exception as e:
        RESULTS["multi_year"] = {"error": str(e)}
        log(f"  ERROR: {e}")

    # === 4. XBRL解析の速度（2回目はキャッシュ効果） ===
    log("=== 4. XBRL解析速度（キャッシュ効果） ===")
    try:
        company = edinet.Company.from_sec_code("6758")  # ソニー
        if company:
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2025-01-01", end="2025-12-31")
            if filing:
                # 1回目
                t4a = time.time()
                stmts1 = filing.xbrl()
                time1 = round(time.time() - t4a, 2)
                log(f"  1回目: {time1}秒")

                # 2回目（キャッシュ）
                t4b = time.time()
                stmts2 = filing.xbrl()
                time2 = round(time.time() - t4b, 2)
                log(f"  2回目: {time2}秒 (キャッシュ)")

                RESULTS["cache_effect"] = {
                    "first": time1,
                    "second": time2,
                    "speedup": round(time1 / max(0.001, time2), 1),
                }
                log(f"  高速化倍率: {RESULTS['cache_effect']['speedup']}x")
    except Exception as e:
        RESULTS["cache_effect"] = {"error": str(e)}
        log(f"  ERROR: {e}")

    # === 5. 全項目イテレーション速度 ===
    log("=== 5. 全項目イテレーション ===")
    try:
        company = edinet.Company.from_sec_code("1812")  # 鹿島建設
        if company:
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2024-06-01", end="2025-06-30")
            if filing:
                stmts = filing.xbrl()

                # 全財務諸表の全項目を列挙
                t5 = time.time()
                total_items = 0
                for stmt_name, getter in [
                    ("PL", lambda: stmts.income_statement(consolidated=True)),
                    ("BS", lambda: stmts.balance_sheet(consolidated=True)),
                    ("CF", lambda: stmts.cash_flow_statement(consolidated=True)),
                ]:
                    try:
                        stmt = getter()
                        count = 0
                        for item in stmt:
                            # 各項目の全属性にアクセス
                            _ = item.label_ja
                            _ = item.label_en
                            _ = item.local_name
                            _ = item.value
                            _ = item.unit_ref
                            _ = item.context_id
                            _ = item.period
                            _ = item.dimensions
                            count += 1
                        total_items += count
                    except Exception as e:
                        log(f"    {stmt_name}: ERROR: {e}")

                elapsed = round(time.time() - t5, 4)
                RESULTS["iteration"] = {
                    "total_items": total_items,
                    "time": elapsed,
                    "per_item_ms": round(elapsed / max(1, total_items) * 1000, 3),
                }
                log(f"  {total_items}項目, {elapsed}秒 ({RESULTS['iteration']['per_item_ms']}ms/item)")
    except Exception as e:
        RESULTS["iteration"] = {"error": str(e)}
        log(f"  ERROR: {e}")

    # === 6. doc_typeフィルタの網羅テスト ===
    log("=== 6. doc_type フィルタ ===")
    doc_type_results = {}
    test_doc_types = [
        DocType.ANNUAL_SECURITIES_REPORT,
        DocType.QUARTERLY_REPORT,
        DocType.SEMIANNUAL_REPORT,
        DocType.EXTRAORDINARY_REPORT,
    ]
    for dt in test_doc_types:
        t6 = time.time()
        try:
            filings = edinet.documents(date="2025-06-25", doc_type=dt)
            elapsed = round(time.time() - t6, 2)
            doc_type_results[dt.value] = {
                "name": dt.name,
                "count": len(filings),
                "time": elapsed,
            }
            log(f"  {dt.name} ({dt.value}): {len(filings)}件, {elapsed}秒")
        except Exception as e:
            doc_type_results[dt.value] = {"error": str(e)}
            log(f"  {dt.name}: ERROR: {e}")
    RESULTS["doc_type_filter"] = doc_type_results

    # === 7. all_listedの規模確認 ===
    log("=== 7. all_listed() ===")
    t7 = time.time()
    try:
        all_companies = edinet.Company.all_listed()
        elapsed = round(time.time() - t7, 2)
        RESULTS["all_listed"] = {
            "count": len(all_companies),
            "time": elapsed,
        }
        log(f"  上場企業数: {len(all_companies)}, {elapsed}秒")
    except Exception as e:
        RESULTS["all_listed"] = {"error": str(e)}
        log(f"  ERROR: {e}")

    total = round(time.time() - t0, 2)
    RESULTS["total_time"] = total
    log(f"\n=== 全体完了 ({total}秒) ===")

    outpath = os.path.join(os.path.dirname(__file__), "r3_performance_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

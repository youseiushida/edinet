"""Round 2: エッジケーステスト.

- 前期/当期の期間指定
- 個別財務諸表
- 四半期報告書
- 訂正報告書の検索
- 古い年度の書類
- 検索のエッジケース
- エラーハンドリング
"""
import os, sys, time, traceback, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[R2-Edge] {msg}")

def main():
    t0 = time.time()

    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    filing = None  # 初期化

    # === 1. 前期/当期の取り分け ===
    log("=== 1. 前期/当期の取り分け ===")
    try:
        company = edinet.Company.from_sec_code("1802")  # 大成建設
        if not company:
            company = edinet.Company.search("大成建設")[0]
        filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                 start="2025-01-01", end="2025-12-31")
        if not filing:
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2024-06-01", end="2025-05-31")
        if filing:
            statements = filing.xbrl()
            pl_current = statements.income_statement(consolidated=True, period="current")
            pl_prior = statements.income_statement(consolidated=True, period="prior")
            RESULTS["period_split"] = {
                "status": "OK",
                "current_items": len(list(pl_current)),
                "prior_items": len(list(pl_prior)),
            }
            current_sales = pl_current.get("売上高")
            prior_sales = pl_prior.get("売上高")
            if current_sales:
                RESULTS["period_split"]["current_sales"] = str(current_sales.value)
                log(f"  当期売上高: {current_sales.value}")
            if prior_sales:
                RESULTS["period_split"]["prior_sales"] = str(prior_sales.value)
                log(f"  前期売上高: {prior_sales.value}")
            log(f"  当期項目数: {RESULTS['period_split']['current_items']}")
            log(f"  前期項目数: {RESULTS['period_split']['prior_items']}")
        else:
            RESULTS["period_split"] = {"status": "NOT_FOUND"}
            log("  有報が見つかりません")
    except Exception as e:
        RESULTS["period_split"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 2. 個別財務諸表 ===
    log("=== 2. 個別財務諸表 ===")
    try:
        if filing:
            statements = filing.xbrl()
            pl_noncon = statements.income_statement(consolidated=False)
            bs_noncon = statements.balance_sheet(consolidated=False)
            RESULTS["non_consolidated"] = {
                "status": "OK",
                "pl_items": len(list(pl_noncon)),
                "bs_items": len(list(bs_noncon)),
            }
            log(f"  個別PL項目数: {RESULTS['non_consolidated']['pl_items']}")
            log(f"  個別BS項目数: {RESULTS['non_consolidated']['bs_items']}")
            sales = pl_noncon.get("売上高")
            if sales:
                RESULTS["non_consolidated"]["sales"] = str(sales.value)
                log(f"  個別売上高: {sales.value}")
        else:
            RESULTS["non_consolidated"] = {"status": "SKIP"}
            log("  SKIP: filing無し")
    except Exception as e:
        RESULTS["non_consolidated"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 3. 四半期報告書（ソニー） ===
    log("=== 3. 四半期報告書 ===")
    try:
        company_q = edinet.Company.from_sec_code("6758")  # ソニー
        if company_q:
            quarterly = company_q.latest(doc_type=DocType.QUARTERLY_REPORT,
                                          start="2025-01-01", end="2025-12-31")
            if not quarterly:
                quarterly = company_q.latest(doc_type=DocType.QUARTERLY_REPORT,
                                              start="2024-06-01", end="2025-05-31")
            if quarterly:
                log(f"  四半期報告書: {quarterly.doc_id}, {quarterly.filer_name}, {quarterly.filing_date}")
                RESULTS["quarterly"] = {
                    "status": "OK",
                    "doc_id": quarterly.doc_id,
                    "filing_date": str(quarterly.filing_date),
                }
                if quarterly.has_xbrl:
                    stmts = quarterly.xbrl()
                    pl = stmts.income_statement(consolidated=True)
                    RESULTS["quarterly"]["pl_items"] = len(list(pl))
                    RESULTS["quarterly"]["standard"] = str(stmts.detected_standard)
                    log(f"  基準: {stmts.detected_standard}, PL項目数: {RESULTS['quarterly']['pl_items']}")
            else:
                RESULTS["quarterly"] = {"status": "NOT_FOUND"}
                log("  四半期報告書が見つかりません")
    except Exception as e:
        RESULTS["quarterly"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 4. 訂正報告書検索 ===
    log("=== 4. 訂正報告書検索 ===")
    try:
        from datetime import date, timedelta
        found_amendments = []
        for i in range(30):
            d = date(2025, 6, 1) - timedelta(days=i)
            filings_a = edinet.documents(date=str(d), doc_type=DocType.AMENDED_ANNUAL_SECURITIES_REPORT)
            if filings_a:
                for f in filings_a[:3]:
                    found_amendments.append({
                        "doc_id": f.doc_id,
                        "filer_name": f.filer_name,
                        "date": str(f.filing_date),
                        "parent_doc_id": f.parent_doc_id,
                    })
                break
        RESULTS["amendments"] = {
            "status": "OK" if found_amendments else "NOT_FOUND",
            "count": len(found_amendments),
            "items": found_amendments,
        }
        log(f"  訂正報告書: {len(found_amendments)}件")
        for a in found_amendments[:3]:
            log(f"    {a['filer_name']} ({a['doc_id']}) parent={a['parent_doc_id']}")
    except Exception as e:
        RESULTS["amendments"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 5. エラーハンドリング ===
    log("=== 5. エラーハンドリング ===")

    # 5a. 存在しないEDINETコード
    try:
        company_none = edinet.Company.from_edinet_code("E99999")
        RESULTS["error_invalid_edinet_code"] = {
            "status": "OK_NONE" if company_none is None else "UNEXPECTED",
            "returned": str(company_none),
        }
        log(f"  E99999 → {company_none}")
    except Exception as e:
        RESULTS["error_invalid_edinet_code"] = {"status": "EXCEPTION", "error": str(e)}
        log(f"  E99999 → Exception: {e}")

    # 5b. 存在しない証券コード
    try:
        company_none2 = edinet.Company.from_sec_code("0000")
        RESULTS["error_invalid_sec_code"] = {
            "status": "OK_NONE" if company_none2 is None else "UNEXPECTED",
            "returned": str(company_none2),
        }
        log(f"  sec=0000 → {company_none2}")
    except Exception as e:
        RESULTS["error_invalid_sec_code"] = {"status": "EXCEPTION", "error": str(e)}
        log(f"  sec=0000 → Exception: {e}")

    # 5c. 空の検索
    try:
        empty_search = edinet.Company.search("")
        RESULTS["error_empty_search"] = {"status": "OK", "count": len(empty_search)}
        log(f"  空検索 → {len(empty_search)}件")
    except Exception as e:
        RESULTS["error_empty_search"] = {"status": "EXCEPTION", "error": str(e)}
        log(f"  空検索 → Exception: {e}")

    # 5d. 非常に長い検索文字列
    try:
        long_search = edinet.Company.search("あ" * 1000)
        RESULTS["error_long_search"] = {"status": "OK", "count": len(long_search)}
        log(f"  長い検索 → {len(long_search)}件")
    except Exception as e:
        RESULTS["error_long_search"] = {"status": "EXCEPTION", "error": str(e)}
        log(f"  長い検索 → Exception: {e}")

    # 5e. 不正な日付形式
    try:
        bad_date = edinet.documents(date="not-a-date")
        RESULTS["error_bad_date"] = {"status": "UNEXPECTED_OK", "count": len(bad_date)}
    except Exception as e:
        RESULTS["error_bad_date"] = {"status": "EXCEPTION", "error": str(e), "type": type(e).__name__}
        log(f"  不正日付 → {type(e).__name__}: {e}")

    # 5f. 日付範囲上限テスト
    try:
        edge_366 = edinet.documents(start="2025-01-01", end="2026-01-01")  # ちょうど366日
        RESULTS["error_edge_366"] = {"status": "OK", "count": len(edge_366)}
        log(f"  366日丁度 → {len(edge_366)}件")
    except Exception as e:
        RESULTS["error_edge_366"] = {"status": "EXCEPTION", "error": str(e)}
        log(f"  366日丁度 → Exception: {e}")

    try:
        edge_367 = edinet.documents(start="2025-01-01", end="2026-01-02")  # 367日
        RESULTS["error_edge_367"] = {"status": "UNEXPECTED_OK", "count": len(edge_367)}
    except ValueError as e:
        RESULTS["error_edge_367"] = {"status": "OK_REJECTED", "error": str(e)}
        log(f"  367日 → 正しく拒否: {e}")
    except Exception as e:
        RESULTS["error_edge_367"] = {"status": "EXCEPTION", "error": str(e)}

    # === 6. 未来の日付 ===
    log("=== 6. 未来の日付 ===")
    try:
        future_filings = edinet.documents(date="2099-01-01")
        RESULTS["future_date"] = {"status": "OK", "count": len(future_filings)}
        log(f"  2099-01-01 → {len(future_filings)}件")
    except Exception as e:
        RESULTS["future_date"] = {"status": "EXCEPTION", "error": str(e), "type": type(e).__name__}
        log(f"  2099-01-01 → {type(e).__name__}: {e}")

    # === 7. strict=True ===
    log("=== 7. strict=True ===")
    if filing:
        try:
            statements = filing.xbrl()
            pl = statements.income_statement(consolidated=True, strict=True)
            RESULTS["strict_mode"] = {"status": "OK", "items": len(list(pl))}
            log(f"  strict=True → {RESULTS['strict_mode']['items']}項目")
        except Exception as e:
            RESULTS["strict_mode"] = {"status": "EXCEPTION", "error": str(e), "type": type(e).__name__}
            log(f"  strict=True → {type(e).__name__}: {e}")
    else:
        RESULTS["strict_mode"] = {"status": "SKIP"}

    # === 8. KeyError ===
    log("=== 8. 存在しない項目へのアクセス ===")
    if filing:
        try:
            statements = filing.xbrl()
            pl = statements.income_statement(consolidated=True)
            try:
                _ = pl["存在しない項目名XYZ"]
                RESULTS["missing_key"] = {"status": "UNEXPECTED_OK"}
            except KeyError as e:
                RESULTS["missing_key"] = {"status": "OK_KEYERROR", "message": str(e)}
                log(f"  KeyError（期待通り）: {e}")
        except Exception as e:
            RESULTS["missing_key"] = {"status": "ERROR", "error": str(e)}
    else:
        RESULTS["missing_key"] = {"status": "SKIP"}

    # === 9. DocType文字列指定 ===
    log("=== 9. DocType文字列指定 ===")
    try:
        # 日本語名で指定
        f1 = edinet.documents(date="2025-06-25", doc_type="有価証券報告書")
        # コード文字列で指定
        f2 = edinet.documents(date="2025-06-25", doc_type="120")
        # enum で指定
        f3 = edinet.documents(date="2025-06-25", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
        RESULTS["doc_type_strings"] = {
            "japanese_name": len(f1),
            "code_string": len(f2),
            "enum": len(f3),
            "all_equal": len(f1) == len(f2) == len(f3),
        }
        log(f"  日本語名: {len(f1)}, コード: {len(f2)}, enum: {len(f3)}")
        log(f"  全て同数: {len(f1) == len(f2) == len(f3)}")
    except Exception as e:
        RESULTS["doc_type_strings"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 10. ticker vs sec_code ===
    log("=== 10. ticker vs sec_code ===")
    try:
        # 4桁
        c4 = edinet.Company.from_sec_code("7203")
        # 5桁
        c5 = edinet.Company.from_sec_code("72030")
        RESULTS["ticker_vs_sec"] = {
            "4digit": c4.name_ja if c4 else None,
            "5digit": c5.name_ja if c5 else None,
            "same": (c4 and c5 and c4.edinet_code == c5.edinet_code) if (c4 and c5) else False,
        }
        log(f"  4桁(7203): {c4.name_ja if c4 else None}")
        log(f"  5桁(72030): {c5.name_ja if c5 else None}")
    except Exception as e:
        RESULTS["ticker_vs_sec"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")

    total_time = round(time.time() - t0, 2)
    RESULTS["total_time"] = total_time
    log(f"=== 完了 (合計: {total_time}秒) ===")

    outpath = os.path.join(os.path.dirname(__file__), "r2_edge_cases_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

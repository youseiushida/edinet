"""Round 1 v2: 全業種×会計基準 統合テスト（日付範囲修正版）.

テスト対象:
1. J-GAAP 建設業（鹿島建設 1812）
2. J-GAAP 銀行業（MUFG E03606）
3. IFRS 製造業（トヨタ 7203）
4. US-GAAP 証券業（野村HD 8604）
5. J-GAAP 鉄道業（JR東日本 9020）
6. IFRS 保険業（SOMPO 8630）
"""
import os, sys, time, traceback, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

ALL_RESULTS = {}

def log(msg):
    print(f"[R1v2] {msg}")

def test_company(label, *, sec_code=None, edinet_code=None, search_name=None,
                  expected_standard=None, pl_keys=None, bs_keys=None):
    """一社分のフルテストを実行."""
    results = {}
    t0 = time.time()
    log(f"\n{'='*60}")
    log(f"=== {label} ===")
    log(f"{'='*60}")

    # 1. 企業検索
    company = None
    if sec_code:
        try:
            company = edinet.Company.from_sec_code(sec_code)
            results["lookup"] = {
                "method": "sec_code",
                "status": "OK" if company else "NOT_FOUND",
                "name": company.name_ja if company else None,
            }
            log(f"  sec_code={sec_code} → {company.name_ja if company else 'NOT_FOUND'}")
        except Exception as e:
            results["lookup"] = {"status": "ERROR", "error": str(e)}
            log(f"  sec_code={sec_code} → ERROR: {e}")

    if not company and edinet_code:
        try:
            company = edinet.Company.from_edinet_code(edinet_code)
            results["lookup"] = {
                "method": "edinet_code",
                "status": "OK" if company else "NOT_FOUND",
                "name": company.name_ja if company else None,
            }
            log(f"  edinet_code={edinet_code} → {company.name_ja if company else 'NOT_FOUND'}")
        except Exception as e:
            results["lookup"] = {"status": "ERROR", "error": str(e)}

    if not company and search_name:
        try:
            found = edinet.Company.search(search_name)
            if found:
                company = found[0]
            results["lookup"] = {
                "method": "search",
                "status": "OK" if company else "NOT_FOUND",
                "name": company.name_ja if company else None,
                "total_found": len(found),
            }
            log(f"  search={search_name} → {company.name_ja if company else 'NOT_FOUND'}")
        except Exception as e:
            results["lookup"] = {"status": "ERROR", "error": str(e)}

    if not company:
        results["overall"] = "COMPANY_NOT_FOUND"
        return results

    # 2. 有報取得 (直近1年)
    filing = None
    t2 = time.time()
    try:
        filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                 start="2025-01-01", end="2025-12-31")
        if not filing:
            # 2024年度を試す
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2024-06-01", end="2025-06-30")
        results["filing"] = {
            "status": "OK" if filing else "NOT_FOUND",
            "time": round(time.time() - t2, 2),
        }
        if filing:
            results["filing"]["doc_id"] = filing.doc_id
            results["filing"]["filer_name"] = filing.filer_name
            results["filing"]["filing_date"] = str(filing.filing_date)
            results["filing"]["has_xbrl"] = filing.has_xbrl
            results["filing"]["period_start"] = str(filing.period_start) if filing.period_start else None
            results["filing"]["period_end"] = str(filing.period_end) if filing.period_end else None
            log(f"  有報: {filing.doc_id} ({filing.filing_date})")
        else:
            log("  有報: NOT_FOUND")
    except Exception as e:
        results["filing"] = {"status": "ERROR", "error": str(e)}
        log(f"  有報: ERROR: {e}")

    if not filing or not filing.has_xbrl:
        results["overall"] = "NO_XBRL"
        return results

    # 3. XBRL解析
    statements = None
    t3 = time.time()
    try:
        statements = filing.xbrl()
        results["xbrl"] = {
            "status": "OK",
            "time": round(time.time() - t3, 2),
            "detected_standard": str(statements.detected_standard),
            "has_consolidated": statements.has_consolidated_data,
            "has_non_consolidated": statements.has_non_consolidated_data,
        }
        log(f"  XBRL: 基準={statements.detected_standard}, "
            f"連結={statements.has_consolidated_data}, "
            f"time={results['xbrl']['time']}s")

        # 期待する会計基準と一致するか
        if expected_standard:
            actual = str(statements.detected_standard)
            results["xbrl"]["standard_match"] = expected_standard in actual
            if expected_standard not in actual:
                log(f"  ⚠ 期待: {expected_standard}, 実際: {actual}")
    except Exception as e:
        results["xbrl"] = {"status": "ERROR", "error": str(e)}
        log(f"  XBRL: ERROR: {e}")
        traceback.print_exc()
        results["overall"] = "XBRL_PARSE_ERROR"
        return results

    # 4. PL
    try:
        pl = statements.income_statement(consolidated=True)
        items = list(pl)
        results["pl"] = {
            "status": "OK",
            "item_count": len(items),
            "warnings": list(pl.warnings_issued) if hasattr(pl, 'warnings_issued') else [],
        }
        log(f"  PL: {len(items)}項目")
        if pl_keys:
            for key in pl_keys:
                item = pl.get(key)
                if item:
                    results["pl"][key] = str(item.value)
                    log(f"    {key}: {item.value}")
                else:
                    results["pl"][key] = "NOT_FOUND"
                    log(f"    {key}: NOT_FOUND")
    except Exception as e:
        results["pl"] = {"status": "ERROR", "error": str(e)}
        log(f"  PL: ERROR: {e}")

    # 5. BS
    try:
        bs = statements.balance_sheet(consolidated=True)
        items = list(bs)
        results["bs"] = {
            "status": "OK",
            "item_count": len(items),
        }
        log(f"  BS: {len(items)}項目")
        if bs_keys:
            for key in bs_keys:
                item = bs.get(key)
                if item:
                    results["bs"][key] = str(item.value)
                    log(f"    {key}: {item.value}")
                else:
                    results["bs"][key] = "NOT_FOUND"
                    log(f"    {key}: NOT_FOUND")
    except Exception as e:
        results["bs"] = {"status": "ERROR", "error": str(e)}
        log(f"  BS: ERROR: {e}")

    # 6. CF
    try:
        cf = statements.cash_flow_statement(consolidated=True)
        items = list(cf)
        results["cf"] = {
            "status": "OK",
            "item_count": len(items),
        }
        log(f"  CF: {len(items)}項目")
    except Exception as e:
        results["cf"] = {"status": "ERROR", "error": str(e)}
        log(f"  CF: ERROR: {e}")

    # 7. DataFrame
    try:
        pl = statements.income_statement(consolidated=True)
        df = pl.to_dataframe()
        results["dataframe"] = {
            "status": "OK",
            "shape": list(df.shape),
            "columns": list(df.columns),
        }
        log(f"  DataFrame: {df.shape}")
    except Exception as e:
        results["dataframe"] = {"status": "ERROR", "error": str(e)}
        log(f"  DataFrame: ERROR: {e}")

    results["total_time"] = round(time.time() - t0, 2)
    results["overall"] = "OK"
    log(f"  合計: {results['total_time']}秒")
    return results

def main():
    t0 = time.time()

    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # === テスト対象企業 ===
    test_cases = [
        {
            "label": "1. J-GAAP 建設業（鹿島建設）",
            "sec_code": "1812",
            "expected_standard": "J-GAAP",
            "pl_keys": ["売上高", "営業利益", "経常利益", "当期純利益"],
            "bs_keys": ["資産合計", "純資産合計", "負債合計"],
        },
        {
            "label": "2. J-GAAP 銀行業（MUFG）",
            "edinet_code": "E03606",
            "expected_standard": "J-GAAP",
            "pl_keys": ["経常収益", "経常利益", "当期純利益"],
            "bs_keys": ["資産合計", "純資産合計"],
        },
        {
            "label": "3. IFRS 製造業（トヨタ）",
            "sec_code": "7203",
            "expected_standard": "IFRS",
            "pl_keys": ["売上収益", "営業利益", "当期利益"],
            "bs_keys": ["資産合計", "負債合計", "資本合計"],
        },
        {
            "label": "4. US-GAAP 証券業（野村HD）",
            "sec_code": "8604",
            "expected_standard": "US-GAAP",
            "pl_keys": ["収益", "当期純利益"],
            "bs_keys": ["資産合計", "純資産合計"],
        },
        {
            "label": "5. J-GAAP 鉄道業（JR東日本）",
            "sec_code": "9020",
            "expected_standard": "J-GAAP",
            "pl_keys": ["営業収益", "営業利益", "経常利益", "当期純利益"],
            "bs_keys": ["資産合計", "純資産合計"],
        },
        {
            "label": "6. IFRS 保険業（SOMPO HD）",
            "sec_code": "8630",
            "expected_standard": "IFRS",
            "pl_keys": ["保険収益", "営業利益", "当期利益"],
            "bs_keys": ["資産合計", "負債合計"],
        },
    ]

    for tc in test_cases:
        label = tc.pop("label")
        ALL_RESULTS[label] = test_company(label, **tc)

    # === 追加テスト: 企業検索の全角/半角問題 ===
    log("\n" + "="*60)
    log("=== 追加: 検索の全角/半角問題 ===")
    log("="*60)

    search_tests = {
        "三菱UFJ": "半角UFJ",
        "三菱ＵＦＪ": "全角ＵＦＪ",
        "トヨタ": "カタカナ",
        "toyota": "英語小文字",
        "TOYOTA": "英語大文字",
        "ソニー": "カタカナ",
        "Sony": "英語",
    }
    search_results = {}
    for query, desc in search_tests.items():
        try:
            found = edinet.Company.search(query)
            search_results[f"{query}({desc})"] = {
                "count": len(found),
                "names": [c.name_ja for c in found[:3]],
            }
            log(f"  '{query}' ({desc}) → {len(found)}件: {[c.name_ja for c in found[:3]]}")
        except Exception as e:
            search_results[f"{query}({desc})"] = {"error": str(e)}
            log(f"  '{query}' ({desc}) → ERROR: {e}")
    ALL_RESULTS["search_tests"] = search_results

    # === 追加テスト: by_industry ===
    log("\n=== 追加: by_industry ===")
    industry_tests = ["銀行", "銀行業", "建設", "建設業", "証券", "保険", "鉄道"]
    industry_results = {}
    for ind in industry_tests:
        try:
            found = edinet.Company.by_industry(ind, limit=5)
            industry_results[ind] = {
                "count": len(found),
                "names": [c.name_ja for c in found[:3]],
            }
            log(f"  '{ind}' → {len(found)}件")
        except Exception as e:
            industry_results[ind] = {"error": str(e)}
            log(f"  '{ind}' → ERROR: {e}")
    ALL_RESULTS["industry_tests"] = industry_results

    total = round(time.time() - t0, 2)
    ALL_RESULTS["total_time"] = total
    log(f"\n=== 全体完了 ({total}秒) ===")

    outpath = os.path.join(os.path.dirname(__file__), "r1_v2_all_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(ALL_RESULTS, f, ensure_ascii=False, indent=2)
    log(f"結果: {outpath}")

if __name__ == "__main__":
    main()

"""Round 1-2: J-GAAP 銀行業（三菱UFJ FG）ストレステスト."""
import os, sys, time, traceback, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[R1-JGAAP-銀行] {msg}")

def main():
    t0 = time.time()

    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # === 1. 企業検索 ===
    log("=== 1. 企業検索: 三菱UFJ ===")
    t1 = time.time()
    try:
        companies = edinet.Company.search("三菱UFJ")
        RESULTS["company_search"] = {
            "status": "OK" if companies else "EMPTY",
            "count": len(companies),
            "time": round(time.time() - t1, 2),
            "names": [c.name_ja for c in companies[:5]],
        }
        log(f"  結果: {len(companies)}件")
        for c in companies[:5]:
            log(f"    {c.name_ja} ({c.edinet_code}, sec={c.sec_code})")
    except Exception as e:
        RESULTS["company_search"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 2. 銀行業の企業一覧 ===
    log("=== 2. 銀行業の企業一覧 ===")
    t2 = time.time()
    try:
        bank_companies = edinet.Company.by_industry("銀行", limit=10)
        RESULTS["industry_search"] = {
            "status": "OK" if bank_companies else "EMPTY",
            "count": len(bank_companies),
            "time": round(time.time() - t2, 2),
            "names": [c.name_ja for c in bank_companies[:5]],
        }
        log(f"  銀行業: {len(bank_companies)}件")
        for c in bank_companies[:5]:
            log(f"    {c.name_ja} ({c.edinet_code})")
    except Exception as e:
        RESULTS["industry_search"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 3. 有報取得（MUFG） ===
    log("=== 3. MUFG有報取得 ===")
    t3 = time.time()
    filing = None
    try:
        # MUFGのEDINETコード: E03606
        company = edinet.Company.from_edinet_code("E03606")
        if company:
            log(f"  Company: {company.name_ja}")
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2024-01-01", end="2025-12-31")
        else:
            # フォールバック: 検索
            companies = edinet.Company.search("三菱UFJフィナンシャル")
            if companies:
                company = companies[0]
                filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                         start="2024-01-01", end="2025-12-31")
        RESULTS["latest_filing"] = {
            "status": "OK" if filing else "NOT_FOUND",
            "time": round(time.time() - t3, 2),
        }
        if filing:
            RESULTS["latest_filing"]["doc_id"] = filing.doc_id
            RESULTS["latest_filing"]["filer_name"] = filing.filer_name
            RESULTS["latest_filing"]["filing_date"] = str(filing.filing_date)
            log(f"  doc_id={filing.doc_id}, {filing.filer_name}")
    except Exception as e:
        RESULTS["latest_filing"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 4. XBRL解析 ===
    log("=== 4. XBRL解析（銀行業様式） ===")
    statements = None
    if filing and filing.has_xbrl:
        t4 = time.time()
        try:
            statements = filing.xbrl()
            RESULTS["xbrl_parse"] = {
                "status": "OK",
                "time": round(time.time() - t4, 2),
                "detected_standard": str(statements.detected_standard),
                "has_consolidated": statements.has_consolidated_data,
                "has_non_consolidated": statements.has_non_consolidated_data,
            }
            log(f"  会計基準: {statements.detected_standard}")
            log(f"  連結: {statements.has_consolidated_data}")
        except Exception as e:
            RESULTS["xbrl_parse"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 5. 銀行業PL ===
    log("=== 5. 銀行業PL ===")
    if statements:
        try:
            pl = statements.income_statement(consolidated=True)
            items = list(pl)
            RESULTS["pl"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")
            # 銀行業特有の勘定科目
            bank_keys = ["経常収益", "経常費用", "経常利益", "当期純利益",
                         "資金運用収益", "役務取引等収益", "特定取引収益"]
            for key in bank_keys:
                item = pl.get(key)
                if item:
                    log(f"  {key}: {item.value}")
                    RESULTS["pl"][key] = str(item.value)
                else:
                    log(f"  {key}: NOT FOUND")
                    RESULTS["pl"][key] = "NOT_FOUND"
            # search で項目を探す
            log("  --- search('収益') ---")
            revenue_items = pl.search("収益")
            RESULTS["pl"]["search_revenue_count"] = len(revenue_items)
            for item in revenue_items[:5]:
                log(f"    {item.label_ja.text}: {item.value}")
        except Exception as e:
            RESULTS["pl"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 6. 銀行業BS ===
    log("=== 6. 銀行業BS ===")
    if statements:
        try:
            bs = statements.balance_sheet(consolidated=True)
            items = list(bs)
            RESULTS["bs"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")
            bank_bs_keys = ["現金預け金", "有価証券", "貸出金", "預金", "資産合計"]
            for key in bank_bs_keys:
                item = bs.get(key)
                if item:
                    log(f"  {key}: {item.value}")
                    RESULTS["bs"][key] = str(item.value)
                else:
                    log(f"  {key}: NOT FOUND")
                    RESULTS["bs"][key] = "NOT_FOUND"
        except Exception as e:
            RESULTS["bs"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 7. CF ===
    log("=== 7. CF ===")
    if statements:
        try:
            cf = statements.cash_flow_statement(consolidated=True)
            items = list(cf)
            RESULTS["cf"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")
        except Exception as e:
            RESULTS["cf"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    total_time = round(time.time() - t0, 2)
    RESULTS["total_time"] = total_time
    log(f"=== 完了 (合計: {total_time}秒) ===")

    outpath = os.path.join(os.path.dirname(__file__), "r1_jgaap_bank_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

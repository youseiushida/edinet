"""Round 1-4: US-GAAP 証券業（野村HD）ストレステスト."""
import os, sys, time, traceback, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[R1-USGAAP-証券] {msg}")

def main():
    t0 = time.time()

    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # === 1. 野村HD検索 ===
    log("=== 1. 野村HD検索 ===")
    t1 = time.time()
    try:
        companies = edinet.Company.search("野村ホールディングス")
        RESULTS["company_search"] = {
            "status": "OK" if companies else "EMPTY",
            "count": len(companies),
            "time": round(time.time() - t1, 2),
            "names": [c.name_ja for c in companies[:5]],
        }
        log(f"  結果: {len(companies)}件")
        for c in companies[:3]:
            log(f"    {c.name_ja} ({c.edinet_code})")
    except Exception as e:
        RESULTS["company_search"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")

    # === 2. 証券コードからも検索 ===
    log("=== 2. 証券コード8604検索 ===")
    try:
        company_by_sec = edinet.Company.from_sec_code("8604")
        RESULTS["sec_code_lookup"] = {
            "status": "OK" if company_by_sec else "NOT_FOUND",
        }
        if company_by_sec:
            RESULTS["sec_code_lookup"]["name"] = company_by_sec.name_ja
            log(f"  {company_by_sec.name_ja}")
    except Exception as e:
        RESULTS["sec_code_lookup"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")

    # === 3. 有報取得 ===
    log("=== 3. 有報取得 ===")
    filing = None
    company = company_by_sec if company_by_sec else (companies[0] if companies else None)
    if company:
        t3 = time.time()
        try:
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2024-01-01", end="2025-12-31")
            RESULTS["latest_filing"] = {
                "status": "OK" if filing else "NOT_FOUND",
                "time": round(time.time() - t3, 2),
            }
            if filing:
                RESULTS["latest_filing"]["doc_id"] = filing.doc_id
                RESULTS["latest_filing"]["filer_name"] = filing.filer_name
                log(f"  {filing.doc_id}: {filing.filer_name}")
        except Exception as e:
            RESULTS["latest_filing"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 4. XBRL解析 ===
    log("=== 4. XBRL解析（US-GAAP） ===")
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
            }
            log(f"  会計基準: {statements.detected_standard}")
        except Exception as e:
            RESULTS["xbrl_parse"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 5. US-GAAP PL ===
    log("=== 5. US-GAAP PL ===")
    if statements:
        try:
            pl = statements.income_statement(consolidated=True)
            items = list(pl)
            RESULTS["pl"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")

            usgaap_keys = ["Revenue", "収益", "営業利益", "NetRevenue",
                           "当期純利益", "NetIncome", "税引前当期純利益"]
            for key in usgaap_keys:
                item = pl.get(key)
                if item:
                    log(f"  {key}: {item.value}")
                    RESULTS["pl"][key] = str(item.value)
                else:
                    log(f"  {key}: NOT FOUND")
                    RESULTS["pl"][key] = "NOT_FOUND"

            # 全項目ダンプ
            log("  --- 全項目 ---")
            all_items = []
            for item in pl:
                label = item.label_ja.text if item.label_ja else item.local_name
                log(f"    {label}: {item.value}")
                all_items.append({
                    "label_ja": item.label_ja.text if item.label_ja else None,
                    "local_name": item.local_name,
                    "value": str(item.value),
                })
            RESULTS["all_pl_items"] = all_items
        except Exception as e:
            RESULTS["pl"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 6. BS ===
    log("=== 6. US-GAAP BS ===")
    if statements:
        try:
            bs = statements.balance_sheet(consolidated=True)
            items = list(bs)
            RESULTS["bs"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")
            for key in ["資産合計", "TotalAssets", "純資産合計"]:
                item = bs.get(key)
                if item:
                    log(f"  {key}: {item.value}")
                    RESULTS["bs"][key] = str(item.value)
                else:
                    RESULTS["bs"][key] = "NOT_FOUND"
        except Exception as e:
            RESULTS["bs"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 7. CF ===
    log("=== 7. US-GAAP CF ===")
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

    outpath = os.path.join(os.path.dirname(__file__), "r1_usgaap_securities_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

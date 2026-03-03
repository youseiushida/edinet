"""Round 1-3: IFRS 製造業（トヨタ自動車）ストレステスト."""
import os, sys, time, traceback, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[R1-IFRS-製造] {msg}")

def main():
    t0 = time.time()

    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "your_api_key_here"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # === 1. トヨタ（証券コード7203）===
    log("=== 1. トヨタ検索 ===")
    t1 = time.time()
    try:
        company = edinet.Company.from_sec_code("7203")
        RESULTS["company_lookup"] = {
            "status": "OK" if company else "NOT_FOUND",
            "time": round(time.time() - t1, 2),
        }
        if company:
            RESULTS["company_lookup"]["name"] = company.name_ja
            RESULTS["company_lookup"]["edinet_code"] = company.edinet_code
            log(f"  {company.name_ja} ({company.edinet_code})")
        else:
            log("  NOT FOUND")
    except Exception as e:
        RESULTS["company_lookup"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")

    # === 2. 有報取得 ===
    log("=== 2. 有報取得 ===")
    filing = None
    if company:
        t2 = time.time()
        try:
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2024-01-01", end="2025-12-31")
            RESULTS["latest_filing"] = {
                "status": "OK" if filing else "NOT_FOUND",
                "time": round(time.time() - t2, 2),
            }
            if filing:
                RESULTS["latest_filing"]["doc_id"] = filing.doc_id
                RESULTS["latest_filing"]["filer_name"] = filing.filer_name
                RESULTS["latest_filing"]["filing_date"] = str(filing.filing_date)
                log(f"  {filing.doc_id}: {filing.filer_name} ({filing.filing_date})")
        except Exception as e:
            RESULTS["latest_filing"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 3. XBRL解析 ===
    log("=== 3. XBRL解析（IFRS） ===")
    statements = None
    if filing and filing.has_xbrl:
        t3 = time.time()
        try:
            statements = filing.xbrl()
            RESULTS["xbrl_parse"] = {
                "status": "OK",
                "time": round(time.time() - t3, 2),
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

    # === 4. IFRS PL ===
    log("=== 4. IFRS PL ===")
    if statements:
        try:
            pl = statements.income_statement(consolidated=True)
            items = list(pl)
            RESULTS["pl"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")

            # IFRS特有の勘定科目
            ifrs_pl_keys = ["売上収益", "Revenue", "営業利益", "OperatingProfit",
                            "税引前利益", "当期利益", "親会社の所有者に帰属する当期利益"]
            for key in ifrs_pl_keys:
                item = pl.get(key)
                if item:
                    log(f"  {key}: {item.value}")
                    RESULTS["pl"][key] = str(item.value)
                else:
                    log(f"  {key}: NOT FOUND")
                    RESULTS["pl"][key] = "NOT_FOUND"

            # search でIFRS項目を探索
            log("  --- search('利益') ---")
            profit_items = pl.search("利益")
            RESULTS["pl"]["search_profit_count"] = len(profit_items)
            for item in profit_items[:10]:
                log(f"    {item.label_ja.text if item.label_ja else item.local_name}: {item.value}")
        except Exception as e:
            RESULTS["pl"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 5. IFRS BS ===
    log("=== 5. IFRS BS ===")
    if statements:
        try:
            bs = statements.balance_sheet(consolidated=True)
            items = list(bs)
            RESULTS["bs"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")

            ifrs_bs_keys = ["資産合計", "TotalAssets", "負債合計", "資本合計",
                            "親会社の所有者に帰属する持分"]
            for key in ifrs_bs_keys:
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

    # === 6. IFRS CF ===
    log("=== 6. IFRS CF ===")
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

    # === 7. 全項目ダンプ ===
    log("=== 7. 全項目ダンプ（PL） ===")
    if statements:
        try:
            pl = statements.income_statement(consolidated=True)
            all_items = []
            for item in pl:
                all_items.append({
                    "label_ja": item.label_ja.text if item.label_ja else None,
                    "label_en": item.label_en.text if item.label_en else None,
                    "local_name": item.local_name,
                    "value": str(item.value),
                    "context_id": item.context_id,
                })
            RESULTS["all_pl_items"] = all_items
            log(f"  全{len(all_items)}項目をダンプ")
        except Exception as e:
            log(f"  ERROR: {e}")

    total_time = round(time.time() - t0, 2)
    RESULTS["total_time"] = total_time
    log(f"=== 完了 (合計: {total_time}秒) ===")

    outpath = os.path.join(os.path.dirname(__file__), "r1_ifrs_manufacturer_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

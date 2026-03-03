"""Round 1-1: J-GAAP 建設業（鹿島建設）ストレステスト."""
import os, sys, time, traceback, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[R1-JGAAP-建設] {msg}")

def main():
    t0 = time.time()

    # Configure
    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "your_api_key_here"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # === 1. 企業検索 ===
    log("=== 1. 企業検索: 鹿島建設 ===")
    t1 = time.time()
    try:
        companies = edinet.Company.search("鹿島建設")
        RESULTS["company_search"] = {
            "status": "OK" if companies else "EMPTY",
            "count": len(companies),
            "time": round(time.time() - t1, 2),
            "names": [c.name_ja for c in companies[:5]],
        }
        log(f"  結果: {len(companies)}件, {RESULTS['company_search']['time']}秒")
        for c in companies[:3]:
            log(f"    {c.name_ja} ({c.edinet_code})")
    except Exception as e:
        RESULTS["company_search"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")

    # === 2. 有報取得 ===
    log("=== 2. 最新有報取得 ===")
    t2 = time.time()
    filing = None
    try:
        if companies:
            company = companies[0]
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
                RESULTS["latest_filing"]["has_xbrl"] = filing.has_xbrl
                log(f"  doc_id={filing.doc_id}, {filing.filer_name}, {filing.filing_date}")
            else:
                log("  有報が見つかりません")
    except Exception as e:
        RESULTS["latest_filing"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === 3. XBRL解析 ===
    log("=== 3. XBRL解析 ===")
    statements = None
    if filing and filing.has_xbrl:
        t3 = time.time()
        try:
            statements = filing.xbrl()
            RESULTS["xbrl_parse"] = {
                "status": "OK",
                "time": round(time.time() - t3, 2),
                "detected_standard": str(statements.detected_standard) if statements else None,
            }
            log(f"  会計基準: {statements.detected_standard}")
            log(f"  連結: {statements.has_consolidated_data}, 個別: {statements.has_non_consolidated_data}")
        except Exception as e:
            RESULTS["xbrl_parse"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()
    else:
        RESULTS["xbrl_parse"] = {"status": "SKIP", "reason": "no filing or no XBRL"}

    # === 4. PL取得 ===
    log("=== 4. 損益計算書 ===")
    if statements:
        try:
            pl = statements.income_statement(consolidated=True)
            items = list(pl)
            RESULTS["pl"] = {
                "status": "OK",
                "item_count": len(items),
                "warnings": list(pl.warnings_issued) if hasattr(pl, 'warnings_issued') else [],
            }
            log(f"  項目数: {len(items)}")
            # 主要項目チェック
            for key in ["売上高", "営業利益", "経常利益", "当期純利益"]:
                item = pl.get(key)
                if item:
                    log(f"  {key}: {item.value}")
                    RESULTS["pl"][key] = str(item.value)
                else:
                    log(f"  {key}: NOT FOUND")
                    RESULTS["pl"][key] = "NOT_FOUND"
        except Exception as e:
            RESULTS["pl"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 5. BS取得 ===
    log("=== 5. 貸借対照表 ===")
    if statements:
        try:
            bs = statements.balance_sheet(consolidated=True)
            items = list(bs)
            RESULTS["bs"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")
            for key in ["総資産", "資産合計", "純資産合計", "負債合計"]:
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

    # === 6. CF取得 ===
    log("=== 6. キャッシュ・フロー計算書 ===")
    if statements:
        try:
            cf = statements.cash_flow_statement(consolidated=True)
            items = list(cf)
            RESULTS["cf"] = {
                "status": "OK",
                "item_count": len(items),
            }
            log(f"  項目数: {len(items)}")
            for key in ["営業活動によるキャッシュ・フロー", "投資活動によるキャッシュ・フロー", "財務活動によるキャッシュ・フロー"]:
                item = cf.get(key)
                if item:
                    log(f"  {key}: {item.value}")
                    RESULTS["cf"][key] = str(item.value)
                else:
                    log(f"  {key}: NOT FOUND")
                    RESULTS["cf"][key] = "NOT_FOUND"
        except Exception as e:
            RESULTS["cf"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")
            traceback.print_exc()

    # === 7. DataFrame変換 ===
    log("=== 7. DataFrame変換 ===")
    if statements:
        try:
            t7 = time.time()
            pl = statements.income_statement(consolidated=True)
            df = pl.to_dataframe()
            RESULTS["dataframe"] = {
                "status": "OK",
                "shape": list(df.shape),
                "columns": list(df.columns),
                "time": round(time.time() - t7, 2),
            }
            log(f"  shape: {df.shape}, columns: {list(df.columns)}")
        except Exception as e:
            RESULTS["dataframe"] = {"status": "ERROR", "error": str(e)}
            log(f"  ERROR: {e}")

    # === 総合 ===
    total_time = round(time.time() - t0, 2)
    RESULTS["total_time"] = total_time
    log(f"=== 完了 (合計: {total_time}秒) ===")

    # 結果をJSONに保存
    outpath = os.path.join(os.path.dirname(__file__), "r1_jgaap_construction_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    log(f"結果を {outpath} に保存")

if __name__ == "__main__":
    main()

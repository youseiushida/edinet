"""Round 1 v3: 全項目ダンプ - 実際のラベル名を確認する."""
import os, sys, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[DUMP] {msg}")

def dump_statement(label, stmt_getter, results_key):
    """財務諸表の全項目をダンプ."""
    try:
        stmt = stmt_getter()
        items = []
        for item in stmt:
            items.append({
                "label_ja": item.label_ja.text if item.label_ja else None,
                "label_en": item.label_en.text if item.label_en else None,
                "local_name": item.local_name,
                "value": str(item.value) if item.value is not None else None,
                "context_id": item.context_id,
            })
            log(f"  {item.label_ja.text if item.label_ja else item.local_name}: {item.value}")
        RESULTS[results_key] = {"count": len(items), "items": items}
    except Exception as e:
        RESULTS[results_key] = {"error": str(e)}
        log(f"  ERROR: {e}")

def main():
    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # 鹿島建設の有報（直近キャッシュされているはず）
    log("=== 鹿島建設（J-GAAP） ===")
    company = edinet.Company.from_sec_code("1812")
    filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                             start="2025-01-01", end="2025-12-31")
    if filing:
        stmts = filing.xbrl()
        log(f"--- PL ---")
        dump_statement("PL", lambda: stmts.income_statement(consolidated=True), "kajima_pl")
        log(f"\n--- BS ---")
        dump_statement("BS", lambda: stmts.balance_sheet(consolidated=True), "kajima_bs")

    # トヨタ（IFRS）
    log("\n=== トヨタ（IFRS） ===")
    company2 = edinet.Company.from_sec_code("7203")
    filing2 = company2.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                               start="2025-01-01", end="2025-12-31")
    if filing2:
        stmts2 = filing2.xbrl()
        log(f"--- PL ---")
        dump_statement("PL", lambda: stmts2.income_statement(consolidated=True), "toyota_pl")
        log(f"\n--- BS ---")
        dump_statement("BS", lambda: stmts2.balance_sheet(consolidated=True), "toyota_bs")

    # 野村HD（US-GAAP）
    log("\n=== 野村HD（US-GAAP） ===")
    company3 = edinet.Company.from_sec_code("8604")
    filing3 = company3.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                               start="2025-01-01", end="2025-12-31")
    if filing3:
        stmts3 = filing3.xbrl()
        log(f"--- PL ---")
        dump_statement("PL", lambda: stmts3.income_statement(consolidated=True), "nomura_pl")
        log(f"\n--- BS ---")
        dump_statement("BS", lambda: stmts3.balance_sheet(consolidated=True), "nomura_bs")

    outpath = os.path.join(os.path.dirname(__file__), "r1_v3_itemdump_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    log(f"\n結果: {outpath}")

if __name__ == "__main__":
    main()

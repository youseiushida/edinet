"""Round 4: 実用シナリオテスト.

実際のデータ分析ワークフローを想定:
1. 同一セクター企業比較（自動車3社の売上高比較）
2. 時系列分析（1社の過去数年分のデータ取得）
3. 特定科目の横断検索
4. DataFrame操作の実用性
5. CSV/Excelエクスポート
"""
import os, sys, time, traceback, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import edinet
from edinet.models.doc_types import DocType

RESULTS = {}

def log(msg):
    print(f"[R4-Practical] {msg}")

def main():
    t0 = time.time()

    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363"),
        taxonomy_path=os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"),
    )

    # === シナリオ1: 自動車セクター比較 ===
    log("=== シナリオ1: 自動車セクター比較 ===")
    auto_companies = {
        "トヨタ": "7203",
        "ホンダ": "7267",
        "日産": "7201",
    }
    sector_results = {}
    for name, sec_code in auto_companies.items():
        t1 = time.time()
        try:
            company = edinet.Company.from_sec_code(sec_code)
            if not company:
                log(f"  {name}: Company NOT FOUND")
                sector_results[name] = {"status": "NOT_FOUND"}
                continue

            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2025-01-01", end="2025-12-31")
            if not filing:
                filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                         start="2024-06-01", end="2025-05-31")
            if not filing:
                log(f"  {name}: Filing NOT FOUND")
                sector_results[name] = {"status": "FILING_NOT_FOUND"}
                continue

            stmts = filing.xbrl()
            standard = str(stmts.detected_standard)
            pl = stmts.income_statement(consolidated=True)

            # 売上高を探す（会計基準によって名称が違う）
            revenue = None
            for key in ["売上高", "売上収益", "Revenue", "営業収益", "NetSales"]:
                revenue = pl.get(key)
                if revenue:
                    break

            # 当期純利益を探す
            net_income = None
            for key in ["当期純利益", "当期利益", "親会社の所有者に帰属する当期利益",
                         "NetIncome", "親会社株主に帰属する当期純利益"]:
                net_income = pl.get(key)
                if net_income:
                    break

            elapsed = round(time.time() - t1, 2)
            sector_results[name] = {
                "status": "OK",
                "standard": standard,
                "revenue": str(revenue.value) if revenue else "NOT_FOUND",
                "revenue_label": revenue.label_ja.text if revenue and revenue.label_ja else None,
                "net_income": str(net_income.value) if net_income else "NOT_FOUND",
                "net_income_label": net_income.label_ja.text if net_income and net_income.label_ja else None,
                "time": elapsed,
            }
            log(f"  {name} ({standard}): 売上={revenue.value if revenue else 'N/A'}, "
                f"純利益={net_income.value if net_income else 'N/A'}, {elapsed}秒")
        except Exception as e:
            sector_results[name] = {"status": "ERROR", "error": str(e)}
            log(f"  {name}: ERROR: {e}")
            traceback.print_exc()
    RESULTS["sector_comparison"] = sector_results

    # === シナリオ2: DataFrameの実用性チェック ===
    log("\n=== シナリオ2: DataFrame実用性 ===")
    try:
        company = edinet.Company.from_sec_code("7203")  # トヨタ
        if company:
            filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                     start="2025-01-01", end="2025-12-31")
            if not filing:
                filing = company.latest(doc_type=DocType.ANNUAL_SECURITIES_REPORT,
                                         start="2024-06-01", end="2025-05-31")
            if filing:
                stmts = filing.xbrl()
                pl = stmts.income_statement(consolidated=True)

                # デフォルトDataFrame
                df_default = pl.to_dataframe()
                log(f"  デフォルトDF: shape={df_default.shape}, columns={list(df_default.columns)}")

                # fullオプション
                df_full = pl.to_dataframe(full=True)
                log(f"  フルDF: shape={df_full.shape}, columns={list(df_full.columns)}")

                # 値のフィルタリング
                import pandas as pd
                numeric_mask = pd.to_numeric(df_default.get("value", pd.Series()), errors="coerce").notna()
                numeric_df = df_default[numeric_mask] if "value" in df_default.columns else df_default
                log(f"  数値行数: {len(numeric_df)} / {len(df_default)}")

                RESULTS["dataframe_usability"] = {
                    "status": "OK",
                    "default_shape": list(df_default.shape),
                    "default_columns": list(df_default.columns),
                    "full_shape": list(df_full.shape),
                    "full_columns": list(df_full.columns),
                    "numeric_rows": int(len(numeric_df)),
                }
    except Exception as e:
        RESULTS["dataframe_usability"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === シナリオ3: CSVエクスポート ===
    log("\n=== シナリオ3: CSVエクスポート ===")
    try:
        if filing:
            stmts = filing.xbrl()
            pl = stmts.income_statement(consolidated=True)
            outdir = os.path.join(os.path.dirname(__file__), "output")
            os.makedirs(outdir, exist_ok=True)

            csv_path = os.path.join(outdir, "test_pl.csv")
            t3 = time.time()
            pl.to_csv(csv_path)
            csv_time = round(time.time() - t3, 2)
            csv_size = os.path.getsize(csv_path)
            log(f"  CSV: {csv_path}, {csv_size} bytes, {csv_time}秒")

            RESULTS["csv_export"] = {
                "status": "OK",
                "size_bytes": csv_size,
                "time": csv_time,
            }
    except Exception as e:
        RESULTS["csv_export"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")
        traceback.print_exc()

    # === シナリオ4: 特定科目の横断検索 ===
    log("\n=== シナリオ4: 特定科目の横断検索 ===")
    try:
        # 同じ日に提出された複数企業の有報を取得し、売上高を比較
        filings_day = edinet.documents(date="2025-06-25",
                                        doc_type=DocType.ANNUAL_SECURITIES_REPORT)
        cross_results = []
        tested = 0
        for f in filings_day[:10]:  # 最大10社
            if not f.has_xbrl:
                continue
            try:
                stmts = f.xbrl()
                pl = stmts.income_statement(consolidated=True)
                revenue = None
                for key in ["売上高", "売上収益", "営業収益"]:
                    revenue = pl.get(key)
                    if revenue:
                        break
                cross_results.append({
                    "filer": f.filer_name,
                    "standard": str(stmts.detected_standard),
                    "revenue": str(revenue.value) if revenue else "NOT_FOUND",
                })
                tested += 1
                log(f"  {f.filer_name}: {revenue.value if revenue else 'N/A'}")
            except Exception as e:
                cross_results.append({
                    "filer": f.filer_name,
                    "error": str(e),
                })
                log(f"  {f.filer_name}: ERROR: {e}")
            if tested >= 5:
                break
        RESULTS["cross_search"] = {
            "date": "2025-06-25",
            "total_filings": len(filings_day),
            "tested": tested,
            "results": cross_results,
        }
    except Exception as e:
        RESULTS["cross_search"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")

    # === シナリオ5: PLの全項目名の一覧取得（DX検証） ===
    log("\n=== シナリオ5: 項目名一覧のDX ===")
    try:
        if filing:
            stmts = filing.xbrl()
            pl = stmts.income_statement(consolidated=True)
            bs = stmts.balance_sheet(consolidated=True)
            cf = stmts.cash_flow_statement(consolidated=True)

            pl_labels = [item.label_ja.text if item.label_ja else item.local_name for item in pl]
            bs_labels = [item.label_ja.text if item.label_ja else item.local_name for item in bs]
            cf_labels = [item.label_ja.text if item.label_ja else item.local_name for item in cf]

            RESULTS["label_overview"] = {
                "pl_labels": pl_labels[:20],
                "pl_total": len(pl_labels),
                "bs_labels": bs_labels[:20],
                "bs_total": len(bs_labels),
                "cf_labels": cf_labels[:20],
                "cf_total": len(cf_labels),
            }
            log(f"  PL: {len(pl_labels)}項目, BS: {len(bs_labels)}項目, CF: {len(cf_labels)}項目")
            log(f"  PL先頭5: {pl_labels[:5]}")
            log(f"  BS先頭5: {bs_labels[:5]}")
            log(f"  CF先頭5: {cf_labels[:5]}")
    except Exception as e:
        RESULTS["label_overview"] = {"status": "ERROR", "error": str(e)}
        log(f"  ERROR: {e}")

    # === シナリオ6: DX検証 - contains / get / search の使い勝手 ===
    log("\n=== シナリオ6: API DX検証 ===")
    try:
        if filing:
            stmts = filing.xbrl()
            pl = stmts.income_statement(consolidated=True)

            # containsテスト
            dx_results = {}
            test_keys = ["売上高", "売上収益", "Revenue", "営業利益", "存在しないXYZ"]
            for key in test_keys:
                dx_results[f"contains_{key}"] = key in pl
                log(f"  '{key}' in pl → {key in pl}")

            # getテスト
            for key in test_keys:
                item = pl.get(key)
                dx_results[f"get_{key}"] = item is not None
                if item:
                    log(f"  get('{key}') → {item.value}")

            # len
            dx_results["len"] = len(pl)
            log(f"  len(pl) → {len(pl)}")

            RESULTS["dx_test"] = dx_results
    except Exception as e:
        RESULTS["dx_test"] = {"status": "ERROR", "error": str(e)}

    total = round(time.time() - t0, 2)
    RESULTS["total_time"] = total
    log(f"\n=== 全体完了 ({total}秒) ===")

    outpath = os.path.join(os.path.dirname(__file__), "r4_practical_result.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

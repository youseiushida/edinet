"""ストレステスト Wave2: 単一企業の全機能エクササイズ。

1社の有報に対して、ライブラリの全機能を行使する。
  - パース → 文型組立 → DataFrame変換 → エクスポート
  - diff (前期 vs 当期)
  - カスタム科目検出
  - 計算リンク検証
  - セグメント抽出
  - テキストブロック抽出
  - 脚注抽出
  - サマリー
  - 従業員情報抽出
  - 決算期判定
  - Company API チェーン
  - Rich表示
"""

from __future__ import annotations

import os
import sys
import time
import traceback
import tempfile
from decimal import Decimal
from pathlib import Path
from datetime import date

import edinet
from edinet import DocType, configure, documents

API_KEY = os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363")
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


def subsection(title: str):
    log(f"\n  --- {title} ---")


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


def main():
    total_start = time.time()

    # ========== 対象企業の選定 ==========
    section("0. 対象企業の選定")

    # 2025年6月末の有報から大企業を探す
    filings = documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filings = [f for f in filings if f.has_xbrl]
    log(f"  候補: {len(xbrl_filings)}件")

    # 最初のXBRL付き有報を使う（大企業の可能性が高い）
    target = None
    for f in xbrl_filings:
        name = f.filer_name or ""
        # 十分に大きい企業を優先
        if len(name) > 0:
            target = f
            log(f"  対象: {target.filer_name} (doc_id={target.doc_id})")
            log(f"        submit: {target.submit_date_time}")
            log(f"        edinet_code: {target.edinet_code}")
            log(f"        sec_code: {target.sec_code}")
            log(f"        doc_type: {target.doc_type}")
            log(f"        has_xbrl: {target.has_xbrl}")
            break

    if not target:
        log("  [FATAL] 対象企業なし。終了。")
        return

    # ========== 1. fetch + parse ==========
    section("1. fetch + parse")

    t0 = time.time()
    stmts = test("Filing.xbrl()", target.xbrl)
    if not stmts:
        log("  [FATAL] パース失敗。終了。")
        return

    log(f"    detected_standard: {stmts.detected_standard}")
    log(f"    has_consolidated: {stmts.has_consolidated_data}")
    log(f"    has_non_consolidated: {stmts.has_non_consolidated_data}")
    log(f"    total items: {len(stmts)}")
    log(f"    period_classification: {stmts.period_classification}")

    # ========== 2. 財務諸表組み立て ==========
    section("2. 財務諸表組み立て")

    # 連結PL
    pl = test("income_statement(consolidated=True)", stmts.income_statement, consolidated=True)
    if pl:
        log(f"    PL行数: {len(pl)}")
        log(f"    statement_type: {pl.statement_type}")
        log(f"    period: {pl.period}")
        log(f"    consolidated: {pl.consolidated}")
        log(f"    warnings: {pl.warnings_issued}")

        # イテレーション
        items = list(pl)
        log(f"    イテレーション: {len(items)}件")

        # __getitem__ アクセス
        for key in ["売上高", "営業利益", "経常利益", "当期純利益",
                     "売上原価", "販売費及び一般管理費"]:
            if key in pl:
                item = pl[key]
                log(f"    pl['{key}']: {item.value} (concept={item.local_name})")

        # to_dict (LLM/RAG用)
        dict_data = pl.to_dict()
        log(f"    to_dict(): {len(dict_data)}件")
        if dict_data:
            log(f"      先頭: {dict_data[0]}")

    # 個別PL
    pl_solo = test("income_statement(consolidated=False)",
                   stmts.income_statement, consolidated=False)
    if pl_solo:
        log(f"    個別PL行数: {len(pl_solo)}")

    # 連結BS
    bs = test("balance_sheet(consolidated=True)", stmts.balance_sheet, consolidated=True)
    if bs:
        log(f"    BS行数: {len(bs)}")
        for key in ["総資産", "TotalAssets", "資産合計", "流動資産", "固定資産"]:
            if key in bs:
                log(f"    bs['{key}']: {bs[key].value}")

    # 連結CF
    cf = test("cash_flow_statement(consolidated=True)",
              stmts.cash_flow_statement, consolidated=True)
    if cf:
        log(f"    CF行数: {len(cf)}")

    # 前期PL
    pl_prior = test("income_statement(period='prior')",
                    stmts.income_statement, consolidated=True, period="prior")
    if pl_prior:
        log(f"    前期PL行数: {len(pl_prior)}")

    # strict mode
    try:
        pl_strict = stmts.income_statement(consolidated=True, strict=True)
        if pl_strict:
            log(f"  [PASS] strict=True: {len(pl_strict)}行")
            PASS_COUNT_local = 1
        else:
            log(f"  [INFO] strict=True: None (フォールバック禁止で取得不可)")
    except Exception as e:
        log(f"  [INFO] strict=True: {e}")

    # ========== 3. search ==========
    section("3. search API")

    searches = ["利益", "資産", "売上", "負債", "純資産", "キャッシュ", "配当"]
    for keyword in searches:
        results = stmts.search(keyword)
        log(f"    search('{keyword}'): {len(results)}件")

    # ========== 4. DataFrame変換 ==========
    section("4. DataFrame変換")

    df_all = test("Statements.to_dataframe()", stmts.to_dataframe)
    if df_all is not None:
        log(f"    shape: {df_all.shape}")
        log(f"    columns: {list(df_all.columns)}")
        log(f"    dtypes:\n{df_all.dtypes.to_string()}")

    if pl:
        df_pl = test("PL.to_dataframe()", pl.to_dataframe)
        if df_pl is not None:
            log(f"    PL DataFrame shape: {df_pl.shape}")

        df_pl_full = test("PL.to_dataframe(full=True)", pl.to_dataframe, full=True)
        if df_pl_full is not None:
            log(f"    PL DataFrame(full) shape: {df_pl_full.shape}")
            log(f"    columns: {list(df_pl_full.columns)}")

    # ========== 5. エクスポート ==========
    section("5. エクスポート")

    with tempfile.TemporaryDirectory() as tmpdir:
        if pl:
            csv_path = Path(tmpdir) / "pl.csv"
            test("PL.to_csv()", pl.to_csv, csv_path)
            if csv_path.exists():
                log(f"    CSV size: {csv_path.stat().st_size} bytes")
                # CSVの中身をチェック
                content = csv_path.read_text(encoding="utf-8-sig")
                lines = content.strip().split("\n")
                log(f"    CSV行数: {len(lines)} (ヘッダ含む)")

            try:
                parq_path = Path(tmpdir) / "pl.parquet"
                test("PL.to_parquet()", pl.to_parquet, parq_path)
                if parq_path.exists():
                    log(f"    Parquet size: {parq_path.stat().st_size} bytes")
            except Exception as e:
                log(f"    Parquet: スキップ ({e})")

            try:
                xlsx_path = Path(tmpdir) / "pl.xlsx"
                test("PL.to_excel()", pl.to_excel, xlsx_path)
                if xlsx_path.exists():
                    log(f"    Excel size: {xlsx_path.stat().st_size} bytes")
            except Exception as e:
                log(f"    Excel: スキップ ({e})")

        # Statementsレベルのエクスポート
        csv_all_path = Path(tmpdir) / "all.csv"
        test("Statements.to_csv()", stmts.to_csv, csv_all_path)
        if csv_all_path.exists():
            log(f"    全体CSV size: {csv_all_path.stat().st_size} bytes")

    # ========== 6. diff (前期 vs 当期) ==========
    section("6. diff (前期 vs 当期)")

    if pl and pl_prior:
        diff_result = test("diff_periods(prior, current)", edinet.diff_periods, pl_prior, pl)
        if diff_result:
            log(f"    has_changes: {diff_result.has_changes}")
            log(f"    added: {len(diff_result.added)}")
            log(f"    removed: {len(diff_result.removed)}")
            log(f"    modified: {len(diff_result.modified)}")
            log(f"    unchanged_count: {diff_result.unchanged_count}")
            log(f"    total_compared: {diff_result.total_compared}")
            log(f"    summary: {diff_result.summary()}")

            # modified の中身チェック
            for item in diff_result.modified[:5]:
                log(f"      変更: {getattr(item, 'key', '?')}: "
                    f"{getattr(item, 'old_value', '?')} → {getattr(item, 'new_value', '?')} "
                    f"(差額: {getattr(item, 'difference', '?')})")
    else:
        warn("diffテスト: PL or 前期PLなし")

    # ========== 7. サマリー ==========
    section("7. サマリー (build_summary)")

    summary = test("build_summary()", edinet.build_summary, stmts)
    if summary:
        log(f"    total_items: {summary.total_items}")
        log(f"    accounting_standard: {summary.accounting_standard}")
        log(f"    period_start: {summary.period_start}")
        log(f"    period_end: {summary.period_end}")
        log(f"    period_type: {summary.period_type}")
        log(f"    has_consolidated: {summary.has_consolidated}")
        log(f"    has_non_consolidated: {summary.has_non_consolidated}")
        log(f"    standard_item_count: {summary.standard_item_count}")
        log(f"    custom_item_count: {summary.custom_item_count}")
        log(f"    standard_item_ratio: {summary.standard_item_ratio:.1%}")
        log(f"    namespace_counts: {summary.namespace_counts}")
        log(f"    segment_count: {summary.segment_count}")

    # ========== 8. カスタム科目検出 ==========
    section("8. カスタム科目検出 (detect_custom_items)")

    custom_result = test("detect_custom_items()", edinet.detect_custom_items, stmts)
    if custom_result:
        log(f"    custom_items: {len(custom_result.custom_items)}")
        log(f"    standard_items: {len(custom_result.standard_items)}")
        log(f"    custom_ratio: {custom_result.custom_ratio:.1%}")
        log(f"    total_count: {custom_result.total_count}")

        # カスタム科目のサンプル
        for ci in custom_result.custom_items[:5]:
            log(f"      カスタム: {ci.item.local_name} "
                f"(label={ci.item.label_ja.text if ci.item.label_ja else '?'})")

    # ========== 9. 計算リンク検証 ==========
    section("9. 計算リンク検証 (validate_calculations)")

    if pl:
        calc_result = test("validate_calculations(PL)", edinet.validate_calculations, pl)
        if calc_result:
            log(f"    is_valid: {calc_result.is_valid}")
            log(f"    checked_count: {calc_result.checked_count}")
            log(f"    passed_count: {calc_result.passed_count}")
            log(f"    skipped_count: {calc_result.skipped_count}")
            log(f"    error_count: {calc_result.error_count}")
            log(f"    warning_count: {calc_result.warning_count}")

            for issue in calc_result.issues[:5]:
                log(f"      問題: {issue.message}")

    if bs:
        calc_bs = test("validate_calculations(BS)", edinet.validate_calculations, bs)
        if calc_bs:
            log(f"    BS: valid={calc_bs.is_valid}, checked={calc_bs.checked_count}, "
                f"errors={calc_bs.error_count}")

    # ========== 10. 決算期判定 ==========
    section("10. 決算期判定 (detect_fiscal_year)")

    fy_info = test("detect_fiscal_year()", edinet.detect_fiscal_year, stmts)
    if fy_info:
        log(f"    start_date: {fy_info.start_date}")
        log(f"    end_date: {fy_info.end_date}")
        log(f"    fiscal_year_end_date: {fy_info.fiscal_year_end_date}")
        log(f"    period_months: {fy_info.period_months}")
        log(f"    is_full_year: {fy_info.is_full_year}")
        log(f"    is_irregular: {fy_info.is_irregular}")
        log(f"    fiscal_year_end_month: {fy_info.fiscal_year_end_month}")

    # ========== 11. セグメント抽出 ==========
    section("11. セグメント (extract_segments / list_dimension_axes)")

    try:
        # low-level objects needed for dimension API
        from edinet.xbrl import parse_xbrl_facts
        from edinet.xbrl.contexts import structure_contexts as _sc
        from edinet.xbrl.taxonomy import TaxonomyResolver

        _xbrl_path, _xbrl_bytes = target.fetch()
        _parsed = parse_xbrl_facts(_xbrl_bytes, source_path=_xbrl_path)
        _ctx_map = _sc(_parsed.contexts)
        _resolver = TaxonomyResolver(TAXONOMY_PATH)
        from edinet.xbrl.facts import build_line_items
        _items = build_line_items(_parsed.facts, _ctx_map, _resolver)

        axes = test("list_dimension_axes()", edinet.list_dimension_axes,
                     _items, _ctx_map, _resolver)
        if axes:
            log(f"    次元数: {len(axes)}")
            for ax in axes[:5]:
                log(f"      {ax.local_name}: {ax.label_ja or '?'} "
                    f"(standard={ax.is_standard}, members={ax.member_count}, items={ax.item_count})")
    except Exception as e:
        warn(f"list_dimension_axes: {e}")

    try:
        segments = test("extract_segments()", edinet.extract_segments,
                        _items, _ctx_map, _resolver)
        if segments:
            log(f"    セグメント数: {len(segments)}")
            for seg in segments[:5]:
                log(f"      {seg.name}: items={len(seg.items)}, depth={seg.depth}")
    except Exception as e:
        warn(f"extract_segments: {e}")

    # ========== 12. 従業員情報 ==========
    section("12. 従業員情報")

    try:
        from edinet.financial.notes.employees import extract_employee_info
        emp = test("extract_employee_info()", extract_employee_info, stmts)
        if emp:
            log(f"    従業員数: {emp.count}")
            log(f"    平均年齢: {emp.average_age}")
            log(f"    平均勤続年数: {emp.average_service_years}")
            log(f"    平均年間給与: {emp.average_annual_salary}")
    except ImportError:
        log("  [INFO] employees モジュール未実装")
    except Exception as e:
        warn(f"employee_info: {e}")

    # ========== 13. テキストブロック ==========
    section("13. テキストブロック")

    try:
        from edinet.xbrl.text import extract_text_blocks, build_section_map
        # low-level access needed
        from edinet.xbrl import parse_xbrl_facts
        from edinet.xbrl.contexts import structure_contexts as sc

        xbrl_path, xbrl_bytes = target.fetch()
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        ctx_map = sc(parsed.contexts)

        tbs = test("extract_text_blocks()", extract_text_blocks, parsed.facts, ctx_map)
        if tbs:
            log(f"    テキストブロック数: {len(tbs)}")
            for tb in tbs[:5]:
                text_preview = tb.html[:100] if tb.html else ""
                log(f"      {tb.concept}: {len(tb.html or '')} chars")

            section_map = test("build_section_map()", build_section_map, tbs)
            if section_map:
                log(f"    セクションマップ: {len(section_map)}件")
    except ImportError:
        log("  [INFO] text_blocks モジュール未実装")
    except Exception as e:
        warn(f"text_blocks: {e}")

    # ========== 14. 脚注 ==========
    section("14. 脚注 (footnotes)")

    try:
        from edinet.xbrl.linkbase.footnotes import parse_footnote_links
        from edinet.xbrl import parse_xbrl_facts

        xbrl_path, xbrl_bytes = target.fetch()
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)

        if parsed.footnote_links:
            fn_map = test("parse_footnote_links()", parse_footnote_links, parsed.footnote_links)
            if fn_map:
                log(f"    脚注数: {len(fn_map)}")
                all_fns = fn_map.all_footnotes()
                log(f"    全脚注: {len(all_fns)}件")
                for fn in all_fns[:3]:
                    preview = fn.text[:80] if fn.text else ""
                    log(f"      {fn.label}: {preview}...")
        else:
            log("  脚注リンクなし")
    except ImportError:
        log("  [INFO] footnotes モジュール未実装")
    except Exception as e:
        warn(f"footnotes: {e}")

    # ========== 15. HTML表示 ==========
    section("15. HTML表示")

    try:
        from edinet.display.html import to_html
        if pl:
            html = test("to_html(PL)", to_html, pl)
            if html:
                log(f"    HTML length: {len(html)} chars")
                log(f"    <table>: {'<table' in html}")
                log(f"    <tr>: {html.count('<tr')}")
    except ImportError:
        log("  [INFO] html モジュール未実装")
    except Exception as e:
        warn(f"html: {e}")

    # ========== 16. DocType全種テスト ==========
    section("16. DocType 全種")

    for dt in DocType:
        log(f"    {dt.value}: {dt.name_ja} (original={dt.original}, correction={dt.is_correction})")

    # ========== 17. LineItem 詳細チェック ==========
    section("17. LineItem 詳細チェック")

    if pl:
        items = list(pl)
        if items:
            item = items[0]
            log(f"    concept: {item.concept}")
            log(f"    namespace_uri: {item.namespace_uri}")
            log(f"    local_name: {item.local_name}")
            log(f"    label_ja: {item.label_ja}")
            log(f"    label_en: {item.label_en}")
            log(f"    value: {item.value} (type={type(item.value).__name__})")
            log(f"    unit_ref: {item.unit_ref}")
            log(f"    decimals: {item.decimals}")
            log(f"    context_id: {item.context_id}")
            log(f"    period: {item.period}")
            log(f"    entity_id: {item.entity_id}")
            log(f"    dimensions: {item.dimensions}")
            log(f"    is_nil: {item.is_nil}")
            log(f"    source_line: {item.source_line}")
            log(f"    order: {item.order}")

            # Decimal精度チェック
            numeric_items = [i for i in items if isinstance(i.value, Decimal)]
            log(f"    数値アイテム: {len(numeric_items)} / {len(items)}")
            str_items = [i for i in items if isinstance(i.value, str)]
            log(f"    文字列アイテム: {len(str_items)}")
            nil_items = [i for i in items if i.is_nil]
            log(f"    nilアイテム: {len(nil_items)}")
            no_value = [i for i in items if i.value is None and not i.is_nil]
            log(f"    value=None(non-nil): {len(no_value)}")

    # ========== サマリー ==========
    total_elapsed = time.time() - total_start

    section("テスト結果サマリー")
    log(f"  対象企業: {target.filer_name}")
    log(f"  PASS: {PASS_COUNT}")
    log(f"  FAIL: {FAIL_COUNT}")
    log(f"  WARN: {WARN_COUNT}")
    log(f"  総実行時間: {total_elapsed:.1f}s")

    # 結果をファイルに書き出し
    output_path = Path(__file__).parent / "stress_test_depth_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# ストレステスト: 深堀りテスト\n\n")
        f.write(f"実行日時: {date.today()}\n\n")
        f.write("```\n")
        f.write("\n".join(RESULTS))
        f.write("\n```\n")
    log(f"\n結果を {output_path} に保存しました")


if __name__ == "__main__":
    main()

"""Parquet 復元データに対して README 記載の使用例がどこまで動くか検証する。

使い方:
    uv run python tools/parquet_capability_check.py

前提: tools/parquet_dump_stress_test.py または tools/parquet_stress_test.py で
Parquet ファイルが parquet/ ディレクトリに生成済みであること。
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edinet.extension import import_parquet

# --- Parquet ファイルの探索 ---
PARQUET_DIR = Path(__file__).resolve().parent.parent / "parquet"

# dump_stress_ → stress_ の順で探す
PREFIXES = ["dump_stress_", "stress_", ""]


def find_parquet() -> tuple[Path, str]:
    """利用可能な Parquet ファイルを探す。"""
    for prefix in PREFIXES:
        p = PARQUET_DIR / f"{prefix}filings.parquet"
        if p.exists():
            return PARQUET_DIR, prefix
    print(f"ERROR: {PARQUET_DIR} に Parquet ファイルが見つかりません。")
    print("先に tools/parquet_dump_stress_test.py を実行してください。")
    sys.exit(1)


def run_check(name: str, func, *, expect_fail: bool = False) -> str:
    """テストを実行し結果を返す。"""
    try:
        result = func()
        if expect_fail:
            return f"  UNEXPECTED OK : {name} (失敗想定だが成功した)"
        detail = f" → {result}" if result is not None else ""
        return f"  OK            : {name}{detail}"
    except Exception as e:
        if expect_fail:
            return f"  EXPECTED NG   : {name} ({type(e).__name__}: {e!s:.80s})"
        tb = traceback.format_exc().strip().split("\n")[-1]
        return f"  NG            : {name} ({tb:.100s})"


def main() -> None:
    parquet_dir, prefix = find_parquet()
    print(f"Parquet ディレクトリ: {parquet_dir}")
    print(f"プレフィックス: {prefix!r}")

    # --- 復元 ---
    print("\n[Phase 0] import_parquet()...")
    restored = import_parquet(parquet_dir, prefix=prefix)
    print(f"  復元: {len(restored)} 件")

    # XBRL 付きの一般事業会社（連結あり・科目数多い）を選ぶ
    filing, stmts = None, None
    best_score = 0
    for f, s in restored:
        if s is None:
            continue
        n_items = len(list(s))
        has_consol = s.has_consolidated_data
        dei = s.dei
        # 連結あり + 科目数が多い + 有報(120) を優先
        score = n_items
        if has_consol:
            score += 5000
        if f.doc_type_code == "120":
            score += 3000
        # ファンド（投信）は避ける
        if dei and dei.fund_code:
            score -= 10000
        if score > best_score:
            best_score = score
            filing, stmts = f, s

    if stmts is None:
        print("ERROR: Statements 付きの Filing が見つかりません。")
        sys.exit(1)

    print(f"  対象: {filing.doc_id} ({filing.filer_name})")
    print(f"  LineItem 数: {len(list(stmts))}")

    results: list[str] = []

    # =====================================================================
    # 1. Filing メタデータ
    # =====================================================================
    print("\n" + "=" * 70)
    print("[1] Filing メタデータ")
    print("=" * 70)

    results.append(run_check(
        "filing.doc_id",
        lambda: filing.doc_id,
    ))
    results.append(run_check(
        "filing.filer_name",
        lambda: filing.filer_name,
    ))
    results.append(run_check(
        "filing.ticker",
        lambda: filing.ticker,
    ))
    results.append(run_check(
        "filing.doc_type (computed_field)",
        lambda: repr(filing.doc_type),
    ))
    results.append(run_check(
        "filing.filing_date (computed_field)",
        lambda: str(filing.filing_date),
    ))

    for r in results[-5:]:
        print(r)

    # =====================================================================
    # 2. 財務三表
    # =====================================================================
    print("\n" + "=" * 70)
    print("[2] 財務三表")
    print("=" * 70)

    pl = None
    results.append(run_check(
        "stmts.income_statement()",
        lambda: f"{len(list(stmts.income_statement()))} items",
    ))
    try:
        pl = stmts.income_statement()
    except Exception:
        pass

    results.append(run_check(
        "stmts.balance_sheet()",
        lambda: f"{len(list(stmts.balance_sheet()))} items",
    ))
    results.append(run_check(
        "stmts.cash_flow_statement()",
        lambda: f"{len(list(stmts.cash_flow_statement()))} items",
    ))
    results.append(run_check(
        'stmts.income_statement(period="prior")',
        lambda: f"{len(list(stmts.income_statement(period='prior')))} items",
    ))
    results.append(run_check(
        'stmts.income_statement(period="current")',
        lambda: f"{len(list(stmts.income_statement(period='current')))} items",
    ))
    results.append(run_check(
        "stmts.income_statement(consolidated=False)",
        lambda: f"{len(list(stmts.income_statement(consolidated=False)))} items",
    ))
    def _check_ss():
        ss = stmts.equity_statement()
        n = len(list(ss))
        return f"{n} items (taxonomy_root なしのため空)" if n == 0 else f"{n} items"

    def _check_ci():
        ci = stmts.comprehensive_income()
        n = len(list(ci))
        return f"{n} items (taxonomy_root なしのため空)" if n == 0 else f"{n} items"

    results.append(run_check(
        "stmts.equity_statement() [taxonomy_root なし → 空]",
        _check_ss,
    ))
    results.append(run_check(
        "stmts.comprehensive_income() [taxonomy_root なし → 空]",
        _check_ci,
    ))

    for r in results[-8:]:
        print(r)

    # =====================================================================
    # 3. 科目アクセス
    # =====================================================================
    print("\n" + "=" * 70)
    print("[3] 科目アクセス（Statements 直接）")
    print("=" * 70)

    results.append(run_check(
        'stmts.search("売上")',
        lambda: f"{len(stmts.search('売上'))} hits",
    ))
    results.append(run_check(
        '"売上高" in stmts (__contains__)',
        lambda: f"{'売上高' in stmts}",
    ))
    results.append(run_check(
        "len(stmts)",
        lambda: f"{len(stmts)} items",
    ))
    results.append(run_check(
        "iter(stmts) → first item",
        lambda: next(iter(stmts)).local_name,
    ))

    if pl and len(list(pl)) > 0:
        first_label = list(pl)[0].label_ja.text
        results.append(run_check(
            f'pl["{first_label}"] (ラベルアクセス)',
            lambda: str(pl[first_label].value),
        ))
        results.append(run_check(
            f'pl.get("{first_label}")',
            lambda: str(pl.get(first_label).value) if pl.get(first_label) else "None",
        ))

    for r in results[-6:]:
        print(r)

    # =====================================================================
    # 4. 会計基準・DEI
    # =====================================================================
    print("\n" + "=" * 70)
    print("[4] 会計基準・DEI")
    print("=" * 70)

    results.append(run_check(
        "stmts.detected_standard",
        lambda: repr(stmts.detected_standard),
    ))
    results.append(run_check(
        "stmts.dei.filer_name_ja",
        lambda: stmts.dei.filer_name_ja if stmts.dei else "None",
    ))
    results.append(run_check(
        "stmts.dei.accounting_standards",
        lambda: repr(stmts.dei.accounting_standards) if stmts.dei else "None",
    ))
    results.append(run_check(
        "stmts.industry_code",
        lambda: stmts.industry_code,
    ))

    for r in results[-4:]:
        print(r)

    # =====================================================================
    # 5. extract_values (CK)
    # =====================================================================
    print("\n" + "=" * 70)
    print("[5] extract_values (CK)")
    print("=" * 70)

    from edinet import extract_values, CK

    results.append(run_check(
        "extract_values(stmts, [CK.REVENUE])",
        lambda: str(extract_values(stmts, [CK.REVENUE]).get(CK.REVENUE)),
    ))
    results.append(run_check(
        "extract_values(stmts, [CK.OPERATING_INCOME, CK.TOTAL_ASSETS])",
        lambda: str({
            k: v.value if v else None
            for k, v in extract_values(stmts, [CK.OPERATING_INCOME, CK.TOTAL_ASSETS]).items()
        }),
    ))
    results.append(run_check(
        'extract_values(stmts, [CK.REVENUE], period="current")',
        lambda: str(extract_values(stmts, [CK.REVENUE], period="current").get(CK.REVENUE)),
    ))
    results.append(run_check(
        'extract_values(stmts, [CK.REVENUE], period="prior")',
        lambda: str(extract_values(stmts, [CK.REVENUE], period="prior").get(CK.REVENUE)),
    ))
    results.append(run_check(
        "extract_values(stmts, [CK.REVENUE], consolidated=False)",
        lambda: str(extract_values(stmts, [CK.REVENUE], consolidated=False).get(CK.REVENUE)),
    ))

    for r in results[-5:]:
        print(r)

    # =====================================================================
    # 6. マッパーパイプライン
    # =====================================================================
    print("\n" + "=" * 70)
    print("[6] マッパーパイプライン")
    print("=" * 70)

    from edinet import (
        summary_mapper,
        statement_mapper,
        definition_mapper,
        calc_mapper,
        standard_concept_mapper,
        dict_mapper,
    )

    results.append(run_check(
        "summary_mapper のみ",
        lambda: str(extract_values(stmts, [CK.REVENUE], mapper=[summary_mapper]).get(CK.REVENUE)),
    ))
    results.append(run_check(
        "statement_mapper のみ",
        lambda: str(extract_values(stmts, [CK.REVENUE], mapper=[statement_mapper]).get(CK.REVENUE)),
    ))
    results.append(run_check(
        "definition_mapper() [要 definition_linkbase]",
        lambda: str(extract_values(stmts, [CK.REVENUE], mapper=[definition_mapper()]).get(CK.REVENUE)),
    ))
    results.append(run_check(
        "calc_mapper() [要 calculation_linkbase]",
        lambda: str(extract_values(stmts, [CK.REVENUE], mapper=[calc_mapper()]).get(CK.REVENUE)),
    ))
    results.append(run_check(
        "standard_concept_mapper",
        lambda: str(extract_values(stmts, ["NetSales"], mapper=[standard_concept_mapper]).get("NetSales")),
    ))
    results.append(run_check(
        "dict_mapper (カスタム)",
        lambda: str(extract_values(
            stmts, ["my_rev"],
            mapper=[dict_mapper({"NetSales": "my_rev"})],
        ).get("my_rev")),
    ))

    for r in results[-6:]:
        print(r)

    # =====================================================================
    # 7. DataFrame 変換
    # =====================================================================
    print("\n" + "=" * 70)
    print("[7] DataFrame 変換")
    print("=" * 70)

    try:
        import pandas as pd  # noqa: F401
        has_pandas = True
    except ImportError:
        has_pandas = False

    if has_pandas and pl:
        results.append(run_check(
            "pl.to_dataframe()",
            lambda: f"{len(pl.to_dataframe())} rows",
        ))
        results.append(run_check(
            "pl.to_dataframe(full=True)",
            lambda: f"{len(pl.to_dataframe(full=True).columns)} cols",
        ))
        results.append(run_check(
            "stmts.to_dataframe()",
            lambda: f"{len(stmts.to_dataframe())} rows",
        ))
    else:
        msg = "pandas 未インストール" if not has_pandas else "PL 取得失敗"
        results.append(f"  SKIP          : DataFrame 変換 ({msg})")

    for r in results[-3:]:
        print(r)

    # =====================================================================
    # 8. 計算検証
    # =====================================================================
    print("\n" + "=" * 70)
    print("[8] 計算検証")
    print("=" * 70)

    from edinet import validate_calculations

    calc_lb = stmts.calculation_linkbase
    if calc_lb and pl:
        results.append(run_check(
            "validate_calculations(pl, calc_linkbase)",
            lambda: f"valid={validate_calculations(pl, calc_lb).is_valid}, "
                    f"checked={validate_calculations(pl, calc_lb).checked_count}",
        ))
    else:
        results.append(run_check(
            "validate_calculations [calc_linkbase 存在確認]",
            lambda: f"calc_linkbase={'あり' if calc_lb else 'なし'}",
        ))

    for r in results[-1:]:
        print(r)

    # =====================================================================
    # 9. 訂正差分・期間差分
    # =====================================================================
    print("\n" + "=" * 70)
    print("[9] 訂正差分・期間差分")
    print("=" * 70)

    from edinet import diff_periods

    if pl:
        results.append(run_check(
            "diff_periods(pl_prior, pl_current)",
            lambda: (
                diff_periods(
                    stmts.income_statement(period="prior"),
                    stmts.income_statement(period="current"),
                ).summary()
            ),
        ))
    else:
        results.append(f"  SKIP          : diff_periods (PL 取得失敗)")

    for r in results[-1:]:
        print(r)

    # =====================================================================
    # 10. セグメント分析
    # =====================================================================
    print("\n" + "=" * 70)
    print("[10] セグメント分析 [要 resolver]")
    print("=" * 70)

    from edinet import list_dimension_axes, extract_segments

    results.append(run_check(
        "list_dimension_axes(stmts) [要 resolver]",
        lambda: f"{len(list_dimension_axes(stmts))} axes",
        expect_fail=True,
    ))
    results.append(run_check(
        'extract_segments(stmts, axis_local_name="OperatingSegmentsAxis") [要 resolver]',
        lambda: f"{len(extract_segments(stmts, axis_local_name='OperatingSegmentsAxis'))} segments",
        expect_fail=True,
    ))

    for r in results[-2:]:
        print(r)

    # =====================================================================
    # 11. 非標準科目判定
    # =====================================================================
    print("\n" + "=" * 70)
    print("[11] 非標準科目判定 [要 resolver]")
    print("=" * 70)

    from edinet import detect_custom_items

    def _check_custom():
        r = detect_custom_items(stmts)
        has_resolver = stmts.resolver is not None
        return (f"{len(r.custom_items)} custom, "
                f"resolver={'あり' if has_resolver else 'なし (parent推定不可)'}")

    results.append(run_check(
        "detect_custom_items(stmts) [resolver なしでも部分動作]",
        _check_custom,
    ))

    for r in results[-1:]:
        print(r)

    # =====================================================================
    # 12. 変則決算・期間分類
    # =====================================================================
    print("\n" + "=" * 70)
    print("[12] 変則決算・期間分類")
    print("=" * 70)

    from edinet import detect_fiscal_year
    from edinet.financial import classify_periods

    dei = stmts.dei
    if dei:
        results.append(run_check(
            "detect_fiscal_year(dei)",
            lambda: f"months={detect_fiscal_year(dei).period_months}, "
                    f"irregular={detect_fiscal_year(dei).is_irregular}",
        ))
        results.append(run_check(
            "classify_periods(dei)",
            lambda: f"current={classify_periods(dei).current_duration}",
        ))
    else:
        results.append(f"  SKIP          : DEI なし")

    for r in results[-2:]:
        print(r)

    # =====================================================================
    # 13. 従業員情報
    # =====================================================================
    print("\n" + "=" * 70)
    print("[13] 従業員情報")
    print("=" * 70)

    from edinet.financial.notes.employees import extract_employee_info

    results.append(run_check(
        "extract_employee_info(stmts)",
        lambda: (
            f"count={extract_employee_info(stmts).count}"
            if extract_employee_info(stmts) else "None (この書類には従業員データなし)"
        ),
    ))

    for r in results[-1:]:
        print(r)

    # =====================================================================
    # 14. Filing サマリー
    # =====================================================================
    print("\n" + "=" * 70)
    print("[14] Filing サマリー")
    print("=" * 70)

    from edinet import build_summary

    results.append(run_check(
        "build_summary(stmts)",
        lambda: f"total_items={build_summary(stmts).total_items}, "
                f"standard_ratio={build_summary(stmts).standard_item_ratio:.1%}",
    ))

    for r in results[-1:]:
        print(r)

    # =====================================================================
    # 15. テキストブロック
    # =====================================================================
    print("\n" + "=" * 70)
    print("[15] テキストブロック [要 raw_facts]")
    print("=" * 70)

    results.append(run_check(
        "stmts.raw_facts [復元後は None]",
        lambda: f"raw_facts={'あり' if stmts.raw_facts else 'None'}",
    ))

    # extract_text_blocks は raw_facts が必要
    from edinet.xbrl.text import extract_text_blocks
    results.append(run_check(
        "extract_text_blocks(stmts.raw_facts, ...) [要 raw_facts]",
        lambda: (
            extract_text_blocks(stmts.raw_facts, stmts.context_map or {})
            if stmts.raw_facts else (_ for _ in ()).throw(
                ValueError("raw_facts is None — Parquet 復元後は利用不可")
            )
        ),
        expect_fail=True,
    ))

    for r in results[-2:]:
        print(r)

    # =====================================================================
    # 16. Linkbase プロパティ
    # =====================================================================
    print("\n" + "=" * 70)
    print("[16] Linkbase プロパティ")
    print("=" * 70)

    results.append(run_check(
        "stmts.calculation_linkbase",
        lambda: f"{'あり' if stmts.calculation_linkbase else 'None'}"
                + (f" ({len(stmts.calculation_linkbase.trees)} trees)"
                   if stmts.calculation_linkbase else ""),
    ))
    results.append(run_check(
        "stmts.definition_linkbase [復元後は None]",
        lambda: f"{'あり' if stmts.definition_linkbase else 'None'}",
    ))
    results.append(run_check(
        "stmts.resolver [復元後は None]",
        lambda: f"{'あり' if stmts.resolver else 'None'}",
    ))
    results.append(run_check(
        "stmts.taxonomy_root [復元後は None]",
        lambda: f"{'あり' if stmts.taxonomy_root else 'None'}",
    ))

    for r in results[-4:]:
        print(r)

    # =====================================================================
    # サマリー
    # =====================================================================
    print("\n" + "=" * 70)
    print("サマリー")
    print("=" * 70)

    ok_count = sum(1 for r in results if r.strip().startswith("OK"))
    ng_count = sum(1 for r in results if r.strip().startswith("NG"))
    expected_ng = sum(1 for r in results if r.strip().startswith("EXPECTED NG"))
    unexpected_ok = sum(1 for r in results if r.strip().startswith("UNEXPECTED OK"))
    skip_count = sum(1 for r in results if r.strip().startswith("SKIP"))

    print(f"\n  OK            : {ok_count}")
    print(f"  EXPECTED NG   : {expected_ng} (復元後は使えない想定)")
    print(f"  NG            : {ng_count} (想定外の失敗)")
    if unexpected_ok:
        print(f"  UNEXPECTED OK : {unexpected_ok} (失敗想定だが成功)")
    if skip_count:
        print(f"  SKIP          : {skip_count}")
    print(f"  合計          : {len(results)}")

    print("\n--- 復元後に使えない機能（EXPECTED NG）---")
    for r in results:
        if "EXPECTED NG" in r:
            print(r)

    if ng_count > 0:
        print("\n--- 想定外の失敗（要調査）---")
        for r in results:
            if r.strip().startswith("NG"):
                print(r)


if __name__ == "__main__":
    main()

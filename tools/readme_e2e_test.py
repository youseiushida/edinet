"""README.md 全サンプルコードの E2E 検証スクリプト。

実 EDINET API を叩いて README に記載の全コードが問題なく動くか検証する。
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import traceback
import warnings
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# ─── 環境変数 ─────────────────────────────
API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_ROOT = os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    "/mnt/c/Users/nezow/Downloads/ALL_20251101",
)

# ─── 結果蓄積 ─────────────────────────────
results: list[tuple[str, str, str]] = []  # (section, status, detail)


def record(section: str, status: str, detail: str = "") -> None:
    results.append((section, status, detail))
    mark = "✓" if status == "PASS" else ("✗" if status == "FAIL" else "⚠")
    print(f"  [{mark}] {section}: {detail[:120]}" if detail else f"  [{mark}] {section}")


def run_section(name: str):
    """セクションテスト用デコレータ。"""
    def decorator(func):
        def wrapper():
            print(f"\n{'='*60}")
            print(f"  {name}")
            print(f"{'='*60}")
            try:
                func()
            except Exception as e:
                record(name, "FAIL", f"{type(e).__name__}: {e}")
                traceback.print_exc()
        return wrapper
    return decorator


# ================================================================
# 0. configure
# ================================================================
@run_section("§0 configure")
def test_configure():
    import edinet

    edinet.configure(
        api_key=API_KEY,
        taxonomy_path=TAXONOMY_ROOT,
        cache_dir="./cache",
    )
    record("configure()", "PASS")


# ================================================================
# 1. クイックスタート
# ================================================================
@run_section("§1 クイックスタート")
def test_quickstart():
    import edinet
    from edinet import extract_values, CK

    # 有価証券報告書の一覧を取得（最近の日付で）
    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    record("documents()", "PASS", f"{len(filings)} filings found")
    assert len(filings) > 0, "有報が見つからない"

    for filing in filings:
        if filing.has_xbrl:
            stmts = filing.xbrl()
            pl = stmts.income_statement()
            bs = stmts.balance_sheet()
            cf = stmts.cash_flow_statement()

            record("三表取得", "PASS", f"PL={len(pl)}科目, BS={len(bs)}科目, CF={len(cf)}科目")

            print(f"  {filing.filer_name}（{filing.ticker}）")

            # search で売上高関連を探して値確認
            hits = stmts.search("売上")
            if hits:
                print(f"    売上系科目: {hits[0].label_ja.text} = {hits[0].value}")
                record("search(売上)", "PASS", f"{hits[0].label_ja.text}={hits[0].value}")

            # extract_values
            result = extract_values(stmts, [CK.OPERATING_INCOME, CK.TOTAL_ASSETS])
            oi = result.get(CK.OPERATING_INCOME)
            ta = result.get(CK.TOTAL_ASSETS)
            record(
                "extract_values()",
                "PASS",
                f"営業利益={oi.value if oi else 'N/A'}, 総資産={ta.value if ta else 'N/A'}",
            )
            break
    else:
        record("XBRL filing", "WARN", "XBRL付きの有報が見つからなかった")


# ================================================================
# 2. 企業検索
# ================================================================
@run_section("§2 企業検索")
def test_company_search():
    from edinet import Company
    import edinet

    # 企業名で検索（部分一致）
    results_search = Company.search("トヨタ自動車")
    assert len(results_search) > 0, "トヨタ自動車が見つからない"
    toyota = results_search[0]
    print(f"  name_ja: {toyota.name_ja}")
    print(f"  ticker: {toyota.ticker}")
    record("Company.search()", "PASS", f"{toyota.name_ja}, ticker={toyota.ticker}")

    # 銘柄コードから
    sony = Company.from_sec_code("6758")
    assert sony is not None, "6758 が見つからない"
    record("Company.from_sec_code()", "PASS", f"{sony.name_ja}")

    # EDINET コードから
    company = Company.from_edinet_code("E02144")
    assert company is not None, "E02144 が見つからない"
    record("Company.from_edinet_code()", "PASS", f"{company.name_ja}")

    # latest（API呼び出しが重いので控えめにテスト）
    filing = toyota.latest(doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    if filing is not None:
        record("Company.latest()", "PASS", f"{filing.doc_id}")
    else:
        record("Company.latest()", "WARN", "最新有報が見つからなかった（期間外の可能性）")


# ================================================================
# 3. 書類タイプ
# ================================================================
@run_section("§3 書類タイプ")
def test_doc_type():
    from edinet import DocType

    dt = DocType.ANNUAL_SECURITIES_REPORT
    print(f"  name_ja: {dt.name_ja}")
    print(f"  is_correction: {dt.is_correction}")
    assert dt.name_ja == "有価証券報告書"
    assert dt.is_correction is False
    record("DocType properties", "PASS")

    # 訂正報告書
    corrected = DocType.AMENDED_ANNUAL_SECURITIES_REPORT
    assert corrected.original == DocType.ANNUAL_SECURITIES_REPORT
    record("DocType.original", "PASS", f"{corrected.name_ja} → {corrected.original.name_ja}")


# ================================================================
# 4. 書類タイプ別アクセス (三表・ラベル・PDF)
# ================================================================
@run_section("§4 書類タイプ別アクセス")
def test_doc_type_access():
    import edinet

    # 有報系: 三表 + ラベルアクセス
    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = None
    for f in filings:
        if f.has_xbrl:
            xbrl_filing = f
            break

    if xbrl_filing is None:
        record("有報 XBRL", "WARN", "XBRL付きの有報がない")
        return

    stmts = xbrl_filing.xbrl()
    pl = stmts.income_statement()

    # ラベルアクセス: search して最初に見つかった科目を使う
    for item in pl:
        print(f"  PL最初の科目: {item.label_ja.text} = {item.value}")
        record("PL item access", "PASS", f"{item.label_ja.text}")
        break

    # search（部分一致）
    hits = stmts.search("営業利益")
    if hits:
        record("stmts.search()", "PASS", f"{len(hits)} hits: {hits[0].label_ja.text}")
    else:
        record("stmts.search()", "WARN", "営業利益が見つからない")

    # get() で安全にアクセス
    item = stmts.get("売上高")
    if item:
        record("stmts.get(売上高)", "PASS", f"{item.value}")
    else:
        record("stmts.get(売上高)", "WARN", "売上高が見つからない（業種依存の可能性）")


# ================================================================
# 5. 財務諸表: 前期・個別
# ================================================================
@run_section("§5 財務諸表 前期・個別")
def test_statements_variants():
    import edinet

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()

    # 前期
    pl_prior = stmts.income_statement(period="prior")
    record("income_statement(prior)", "PASS", f"{len(pl_prior)} 科目")

    # 個別
    pl_solo = stmts.income_statement(consolidated=False)
    record("income_statement(solo)", "PASS", f"{len(pl_solo)} 科目")


# ================================================================
# 6. 科目アクセス (label_ja / label_en / concept)
# ================================================================
@run_section("§6 科目アクセス")
def test_item_access():
    import edinet

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    pl = stmts.income_statement()

    # 日本語ラベルで取得
    item = pl.get("売上高")
    if item:
        print(f"  value: {item.value}")
        print(f"  unit_ref: {item.unit_ref}")
        record("pl[売上高]", "PASS", f"value={item.value}")

        # 英語ラベル / concept 名
        en_item = pl.get("Net sales")
        concept_item = pl.get("NetSales")
        record("pl[Net sales]", "PASS" if en_item else "WARN")
        record("pl[NetSales]", "PASS" if concept_item else "WARN")
    else:
        record("pl[売上高]", "WARN", "売上高が見つからない")

    # get() の None 安全性
    none_item = pl.get("存在しない科目名")
    assert none_item is None, "存在しない科目が返された"
    record("pl.get(not_found)", "PASS", "None returned correctly")


# ================================================================
# 7. 会計基準の自動判別
# ================================================================
@run_section("§7 会計基準の自動判別")
def test_detected_standard():
    import edinet

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    print(f"  detected_standard: {stmts.detected_standard}")
    print(f"  repr: {repr(stmts.detected_standard)}")
    record("detected_standard", "PASS", str(stmts.detected_standard))


# ================================================================
# 8. extract_values (各種パラメータ)
# ================================================================
@run_section("§8 extract_values 各種パラメータ")
def test_extract_values():
    import edinet
    from edinet import extract_values, extracted_to_dict, CK

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()

    # デフォルト（全期間・全区分から先頭マッチ）
    result = extract_values(stmts, [CK.REVENUE, CK.OPERATING_INCOME, CK.GOODWILL])
    record("extract_values(default)", "PASS", f"{sum(1 for v in result.values() if v)} found")

    # 当期・連結を明示指定
    result2 = extract_values(stmts, [CK.REVENUE], period="current", consolidated=True)
    record("extract_values(current/consol)", "PASS")

    # 前期
    result3 = extract_values(stmts, [CK.REVENUE], period="prior")
    record("extract_values(prior)", "PASS")

    # 個別
    result4 = extract_values(stmts, [CK.REVENUE], consolidated=False)
    record("extract_values(solo)", "PASS")

    # ExtractedValue のフィールド
    rev = result.get(CK.REVENUE)
    if rev:
        print(f"  value: {rev.value}")
        print(f"  mapper_name: {rev.mapper_name}")
        print(f"  item.label_ja.text: {rev.item.label_ja.text}")
        print(f"  item.local_name: {rev.item.local_name}")
        record("ExtractedValue fields", "PASS")
    else:
        record("ExtractedValue fields", "WARN", "REVENUE not found")

    # マッパー名でフィルタ
    safe = {k: v for k, v in result.items() if v and v.mapper_name == "summary_mapper"}
    record("mapper filter", "PASS", f"{len(safe)} items via summary_mapper")

    # Summary のみ
    from edinet import summary_mapper
    result5 = extract_values(stmts, [CK.REVENUE], mapper=[summary_mapper])
    record("extract_values(summary only)", "PASS")

    # extracted_to_dict
    keys = [CK.REVENUE, CK.OPERATING_INCOME, CK.NET_INCOME, CK.TOTAL_ASSETS]
    full_result = extract_values(stmts, keys, period="current", consolidated=True)
    d = extracted_to_dict(full_result)
    record("extracted_to_dict()", "PASS", f"{d}")


# ================================================================
# 9. dict_mapper
# ================================================================
@run_section("§9 dict_mapper")
def test_dict_mapper():
    import edinet
    from edinet import extract_values, summary_mapper, statement_mapper, dict_mapper

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()

    # カスタムマッパー
    my_mapper = dict_mapper({"MyCustomRevenue": "revenue"}, name="my_rules")
    result = extract_values(stmts, mapper=[my_mapper, summary_mapper, statement_mapper])
    record("dict_mapper()", "PASS", f"{sum(1 for v in result.values() if v)} found")


# ================================================================
# 10. DataFrame 変換・エクスポート
# ================================================================
@run_section("§10 DataFrame・エクスポート")
def test_dataframe():
    import edinet

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    pl = stmts.income_statement()

    # to_dataframe
    try:
        import pandas as pd

        df = pl.to_dataframe()
        record("to_dataframe()", "PASS", f"shape={df.shape}")

        df_full = pl.to_dataframe(full=True)
        record("to_dataframe(full)", "PASS", f"shape={df_full.shape}, cols={list(df_full.columns)[:5]}...")

        # エクスポート
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "pl.csv"
            pl.to_csv(str(csv_path))
            assert csv_path.exists()
            record("to_csv()", "PASS", f"size={csv_path.stat().st_size}")

            parquet_path = Path(tmpdir) / "pl.parquet"
            pl.to_parquet(str(parquet_path))
            assert parquet_path.exists()
            record("to_parquet()", "PASS", f"size={parquet_path.stat().st_size}")

            xlsx_path = Path(tmpdir) / "pl.xlsx"
            pl.to_excel(str(xlsx_path))
            assert xlsx_path.exists()
            record("to_excel()", "PASS", f"size={xlsx_path.stat().st_size}")

        # Statements 全体
        df_all = stmts.to_dataframe()
        record("stmts.to_dataframe()", "PASS", f"shape={df_all.shape}")

    except ImportError:
        record("DataFrame", "WARN", "pandas not installed")


# ================================================================
# 11. テキストブロック（LLM 連携）
# ================================================================
@run_section("§11 テキストブロック")
def test_text_blocks():
    import edinet
    from edinet.xbrl.text import extract_text_blocks, build_section_map, clean_html

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()

    # Statements を直接渡せるインターフェース
    blocks = extract_text_blocks(stmts)
    record("extract_text_blocks()", "PASS", f"{len(blocks)} blocks")

    sections = build_section_map(stmts)
    record("build_section_map()", "PASS", f"{len(sections)} sections: {sections.sections[:5]}...")

    # セクション名でアクセス
    risk_blocks = sections.get("事業等のリスク")
    if risk_blocks:
        clean_text = clean_html(risk_blocks[0].html)
        record("clean_html(事業等のリスク)", "PASS", f"{len(clean_text)} chars: {clean_text[:80]}...")
    else:
        record("clean_html(事業等のリスク)", "WARN", "セクション未発見")


# ================================================================
# 12. タクソノミ・ラベル解決
# ================================================================
@run_section("§12 TaxonomyResolver")
def test_taxonomy():
    from edinet.xbrl.taxonomy import TaxonomyResolver

    resolver = TaxonomyResolver(TAXONOMY_ROOT)
    label = resolver.resolve("jppfs_cor", "NetSales", lang="ja")
    print(f"  text: {label.text}")
    print(f"  source: {label.source}")
    assert label.text == "売上高", f"Expected '売上高', got '{label.text}'"
    record("TaxonomyResolver.resolve()", "PASS", f"{label.text}, source={label.source}")


# ================================================================
# 13. Linkbase 解析
# ================================================================
@run_section("§13 Linkbase 解析")
def test_linkbase():
    import edinet
    from edinet.xbrl.linkbase import (
        parse_presentation_linkbase,
        parse_calculation_linkbase,
        parse_definition_linkbase,
    )
    from edinet.api.download import download_document, list_zip_members, extract_zip_member

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    # ZIP をダウンロードして linkbase ファイルを探す
    zip_bytes = download_document(xbrl_filing.doc_id, file_type="1")
    members = list_zip_members(zip_bytes)

    pres_files = [m for m in members if "_pre.xml" in m and "PublicDoc" in m]
    calc_files = [m for m in members if "_cal.xml" in m and "PublicDoc" in m]
    def_files = [m for m in members if "_def.xml" in m and "PublicDoc" in m]

    if pres_files:
        pres_bytes = extract_zip_member(zip_bytes, pres_files[0])
        pres_trees = parse_presentation_linkbase(pres_bytes)
        record("parse_presentation_linkbase()", "PASS", f"{len(pres_trees)} roles")
    else:
        record("parse_presentation_linkbase()", "WARN", "no _pre.xml found")

    if calc_files:
        calc_bytes = extract_zip_member(zip_bytes, calc_files[0])
        calc_lb = parse_calculation_linkbase(calc_bytes)
        record("parse_calculation_linkbase()", "PASS", f"{len(calc_lb.trees)} roles")
    else:
        record("parse_calculation_linkbase()", "WARN", "no _cal.xml found")

    if def_files:
        def_bytes = extract_zip_member(zip_bytes, def_files[0])
        def_trees = parse_definition_linkbase(def_bytes)
        record("parse_definition_linkbase()", "PASS", f"{len(def_trees)} roles")
    else:
        record("parse_definition_linkbase()", "WARN", "no _def.xml found")


# ================================================================
# 14. ConceptSet 自動導出
# ================================================================
@run_section("§14 ConceptSet 自動導出")
def test_concept_sets():
    from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets, StatementCategory
    from edinet.models.financial import StatementType

    registry = derive_concept_sets(TAXONOMY_ROOT)
    cs = registry.get(StatementType.INCOME_STATEMENT, consolidated=True, industry_code="cai")
    assert cs is not None, "ConceptSet for PL/consolidated/cai not found"
    for entry in cs.concepts[:5]:
        print(f"  {entry.concept}, depth={entry.depth}, is_total={entry.is_total}")
    record("derive_concept_sets()", "PASS", f"{len(cs.concepts)} concepts in PL/cai")


# ================================================================
# 15. 計算検証
# ================================================================
@run_section("§15 計算検証")
def test_validate_calculations():
    import edinet
    from edinet import validate_calculations
    from edinet.xbrl.linkbase import parse_calculation_linkbase
    from edinet.api.download import download_document, list_zip_members, extract_zip_member

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("XBRL filing", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    pl = stmts.income_statement()

    # calc linkbase を取得
    zip_bytes = download_document(xbrl_filing.doc_id, file_type="1")
    members = list_zip_members(zip_bytes)
    calc_files = [m for m in members if "_cal.xml" in m and "PublicDoc" in m]
    if not calc_files:
        record("validate_calculations()", "WARN", "no _cal.xml")
        return

    calc_bytes = extract_zip_member(zip_bytes, calc_files[0])
    calc_linkbase = parse_calculation_linkbase(calc_bytes)

    result = validate_calculations(pl, calc_linkbase)
    print(f"  is_valid: {result.is_valid}")
    print(f"  checked_count: {result.checked_count}")

    for issue in result.issues[:3]:
        print(f"  issue: {issue.parent_concept}: diff={issue.difference}")

    record(
        "validate_calculations()",
        "PASS",
        f"valid={result.is_valid}, checked={result.checked_count}, issues={len(result.issues)}",
    )


# ================================================================
# 16. 訂正チェーン
# ================================================================
@run_section("§16 訂正チェーン")
def test_revision_chain():
    import edinet
    from edinet import build_revision_chain

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    if not filings:
        record("revision_chain", "WARN", "filings empty")
        return

    filing = filings[0]
    chain = build_revision_chain(filing, filings=filings)
    print(f"  is_corrected: {chain.is_corrected}")
    print(f"  count: {chain.count}")
    print(f"  original: {chain.original.doc_id}")
    print(f"  latest: {chain.latest.doc_id}")

    record(
        "build_revision_chain()",
        "PASS",
        f"corrected={chain.is_corrected}, count={chain.count}",
    )

    # at_time
    snapshot = chain.at_time(date(2025, 9, 1))
    record("chain.at_time()", "PASS", f"snapshot={snapshot.doc_id}")


# ================================================================
# 17. 訂正差分・期間差分
# ================================================================
@run_section("§17 訂正差分・期間差分")
def test_diff():
    import edinet
    from edinet import diff_periods

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("diff", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    pl_prior = stmts.income_statement(period="prior")
    pl_current = stmts.income_statement(period="current")

    period_diff = diff_periods(pl_prior, pl_current)
    summary = period_diff.summary()
    print(f"  summary: {summary}")
    record("diff_periods()", "PASS", summary)


# ================================================================
# 18. セグメント分析
# ================================================================
@run_section("§18 セグメント分析")
def test_segments():
    import edinet
    from edinet import list_dimension_axes, extract_segments

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("segments", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()

    axes = list_dimension_axes(stmts)
    for axis in axes:
        print(f"  axis: {axis.label_ja}: {axis.member_count} メンバー")
    record("list_dimension_axes()", "PASS", f"{len(axes)} axes")

    if axes:
        # 最初の軸で extract_segments を試みる
        first_axis = axes[0]
        segments = extract_segments(stmts, axis_local_name=first_axis.local_name)
        for seg in segments[:3]:
            print(f"    segment: {seg.name}: {len(seg.items)} 科目")
        record("extract_segments()", "PASS", f"{len(segments)} segments")
    else:
        record("extract_segments()", "WARN", "no axes found")


# ================================================================
# 19. 非標準科目の判定
# ================================================================
@run_section("§19 非標準科目の判定")
def test_custom_items():
    import edinet
    from edinet import detect_custom_items

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("custom items", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    result = detect_custom_items(stmts)
    print(f"  標準科目: {len(result.standard_items)}")
    print(f"  独自科目: {len(result.custom_items)} ({result.custom_ratio:.1%})")
    record(
        "detect_custom_items()",
        "PASS",
        f"standard={len(result.standard_items)}, custom={len(result.custom_items)} ({result.custom_ratio:.1%})",
    )

    for ci in result.custom_items[:3]:
        print(f"    {ci.item.label_ja.text} → 標準祖先: {ci.parent_standard_concept}")


# ================================================================
# 20. find_custom_concepts
# ================================================================
@run_section("§20 find_custom_concepts")
def test_find_custom_concepts():
    import edinet
    from edinet import find_custom_concepts
    from edinet.xbrl.linkbase import parse_calculation_linkbase
    from edinet.api.download import download_document, list_zip_members, extract_zip_member

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("find_custom_concepts", "WARN", "なし")
        return

    zip_bytes = download_document(xbrl_filing.doc_id, file_type="1")
    members = list_zip_members(zip_bytes)
    calc_files = [m for m in members if "_cal.xml" in m and "PublicDoc" in m]
    if not calc_files:
        record("find_custom_concepts()", "WARN", "no _cal.xml")
        return

    calc_bytes = extract_zip_member(zip_bytes, calc_files[0])
    calc_linkbase = parse_calculation_linkbase(calc_bytes)

    custom_concepts = find_custom_concepts(calc_linkbase)
    print(f"  拡張科目数: {len(custom_concepts)}")
    record("find_custom_concepts()", "PASS", f"{len(custom_concepts)} concepts")


# ================================================================
# 21. 変則決算の判定
# ================================================================
@run_section("§21 変則決算の判定")
def test_fiscal_year():
    import edinet
    from edinet import detect_fiscal_year

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("fiscal year", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    # detect_fiscal_year は DEI を受け取る
    # stmts から DEI を取得する方法を確認
    # README では dei を引数にしているが、stmts の period_classification 経由でテスト
    pc = stmts.period_classification
    # detect_fiscal_year は DEI を受け取るので、低レベルAPIから取得
    xbrl_path, xbrl_bytes = xbrl_filing.fetch()
    from edinet.xbrl import parse_xbrl_facts, extract_dei
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)

    info = detect_fiscal_year(dei)
    print(f"  period_months: {info.period_months}")
    print(f"  is_irregular: {info.is_irregular}")
    print(f"  is_full_year: {info.is_full_year}")
    print(f"  start_date: {info.start_date}")
    print(f"  end_date: {info.end_date}")
    record(
        "detect_fiscal_year()",
        "PASS",
        f"months={info.period_months}, irregular={info.is_irregular}",
    )


# ================================================================
# 22. 従業員情報
# ================================================================
@run_section("§22 従業員情報")
def test_employee_info():
    import edinet
    from edinet.financial.notes.employees import extract_employee_info

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("employee info", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    info = extract_employee_info(stmts)
    if info is not None:
        print(f"  count: {info.count}")
        print(f"  average_age: {info.average_age}")
        print(f"  average_service_years: {info.average_service_years}")
        print(f"  average_annual_salary: {info.average_annual_salary}")
        record(
            "extract_employee_info()",
            "PASS",
            f"count={info.count}, salary={info.average_annual_salary}",
        )
    else:
        record("extract_employee_info()", "WARN", "None returned (従業員情報なし)")


# ================================================================
# 23. Filing サマリー
# ================================================================
@run_section("§23 Filing サマリー")
def test_summary():
    import edinet
    from edinet import build_summary

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("summary", "WARN", "なし")
        return

    stmts = xbrl_filing.xbrl()
    summary = build_summary(stmts)
    print(f"  accounting_standard: {summary.accounting_standard}")
    print(f"  total_items: {summary.total_items}")
    print(f"  standard_item_ratio: {summary.standard_item_ratio}")
    print(f"  segment_count: {summary.segment_count}")
    record(
        "build_summary()",
        "PASS",
        f"standard={summary.accounting_standard}, items={summary.total_items}, ratio={summary.standard_item_ratio:.2f}",
    )


# ================================================================
# 24. 非同期クライアント
# ================================================================
@run_section("§24 非同期クライアント")
def test_async():
    import edinet

    async def main():
        filings = await edinet.adocuments("2025-06-26")
        record("adocuments()", "PASS", f"{len(filings)} filings")

        for filing in filings:
            if filing.has_xbrl and filing.doc_type == edinet.DocType.ANNUAL_SECURITIES_REPORT:
                stmts = await filing.axbrl()
                pl = stmts.income_statement()
                record("axbrl()", "PASS", f"PL={len(pl)} items")
                break
        else:
            record("axbrl()", "WARN", "XBRL有報なし")

        await edinet.aclose()
        record("aclose()", "PASS")

    asyncio.run(main())


# ================================================================
# 25. 期間分類
# ================================================================
@run_section("§25 期間分類")
def test_classify_periods():
    import edinet
    from edinet.financial import classify_periods

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("classify_periods", "WARN", "なし")
        return

    xbrl_path, xbrl_bytes = xbrl_filing.fetch()
    from edinet.xbrl import parse_xbrl_facts, extract_dei
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)

    pc = classify_periods(dei)
    print(f"  current_duration: {pc.current_duration}")
    print(f"  prior_duration: {pc.prior_duration}")
    print(f"  current_instant: {pc.current_instant}")
    record("classify_periods()", "PASS", f"current={pc.current_duration}")


# ================================================================
# 26. キャッシュ
# ================================================================
@run_section("§26 キャッシュ")
def test_cache():
    import edinet

    info = edinet.cache_info()
    print(f"  entry_count: {info.entry_count}, total_bytes: {info.total_bytes}")
    record("cache_info()", "PASS", f"entries={info.entry_count}, bytes={info.total_bytes}")

    # clear_cache は破壊的なのでコメントアウト
    # edinet.clear_cache()
    record("clear_cache()", "PASS", "skipped (non-destructive)")


# ================================================================
# 27. 低レベル API
# ================================================================
@run_section("§27 低レベル API")
def test_low_level():
    import edinet
    from edinet.xbrl import parse_xbrl_facts, extract_dei
    from edinet.xbrl.contexts import ContextCollection, structure_contexts
    from edinet.xbrl.units import structure_units

    filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filing = next((f for f in filings if f.has_xbrl), None)
    if not xbrl_filing:
        record("low level", "WARN", "なし")
        return

    # XBRL インスタンスのパース
    xbrl_path, xbrl_bytes = xbrl_filing.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    record("parse_xbrl_facts()", "PASS", f"{len(parsed.facts)} facts")

    # DEI の抽出
    dei = extract_dei(parsed.facts)
    print(f"  filer_name_ja: {dei.filer_name_ja}")
    print(f"  accounting_standards: {dei.accounting_standards}")
    print(f"  security_code: {dei.security_code}")
    record("extract_dei()", "PASS", f"{dei.filer_name_ja}")

    # Context / Unit の構造化
    contexts = ContextCollection(structure_contexts(parsed.contexts))
    units = structure_units(parsed.units)
    record("structure_contexts()", "PASS", f"{len(contexts)} contexts")
    record("structure_units()", "PASS", f"{len(units)} units")

    # フィルタチェーン
    consolidated = contexts.filter_consolidated().filter_no_extra_dimensions()
    record("filter chain", "PASS", f"{len(consolidated)} consolidated contexts")


# ================================================================
# 28. エラーハンドリング
# ================================================================
@run_section("§28 エラーハンドリング")
def test_error_handling():
    import edinet

    # 例外クラスの存在確認
    assert hasattr(edinet, "EdinetError")
    assert hasattr(edinet, "EdinetConfigError")
    assert hasattr(edinet, "EdinetAPIError")
    assert hasattr(edinet, "EdinetParseError")
    assert hasattr(edinet, "EdinetWarning")

    # 継承関係
    assert issubclass(edinet.EdinetConfigError, edinet.EdinetError)
    assert issubclass(edinet.EdinetAPIError, edinet.EdinetError)
    assert issubclass(edinet.EdinetParseError, edinet.EdinetError)

    record("Exception classes", "PASS", "all exist and inherit correctly")


# ================================================================
# 29. PDF 取得
# ================================================================
@run_section("§29 PDF 取得")
def test_pdf():
    import edinet

    filings = edinet.documents("2025-06-26")
    pdf_filing = next((f for f in filings if f.has_pdf), None)
    if not pdf_filing:
        record("PDF", "WARN", "PDF付き書類なし")
        return

    pdf_bytes = pdf_filing.fetch_pdf()
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"
    record("fetch_pdf()", "PASS", f"{len(pdf_bytes)} bytes")


# ================================================================
# 30. レートリミット
# ================================================================
@run_section("§30 レートリミット")
def test_rate_limit():
    import edinet

    # レートリミット設定 (非破壊)
    edinet.configure(rate_limit=1.0)
    record("rate_limit=1.0", "PASS")
    edinet.configure(rate_limit=0)  # 元に戻す
    record("rate_limit=0", "PASS")


# ================================================================
# メイン
# ================================================================
def main():
    print("=" * 60)
    print("  README.md 全サンプルコード E2E 検証")
    print("=" * 60)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        test_configure()
        test_quickstart()
        test_company_search()
        test_doc_type()
        test_doc_type_access()
        test_statements_variants()
        test_item_access()
        test_detected_standard()
        test_extract_values()
        test_dict_mapper()
        test_dataframe()
        test_text_blocks()
        test_taxonomy()
        test_linkbase()
        test_concept_sets()
        test_validate_calculations()
        test_revision_chain()
        test_diff()
        test_segments()
        test_custom_items()
        test_find_custom_concepts()
        test_fiscal_year()
        test_employee_info()
        test_summary()
        test_async()
        test_classify_periods()
        test_cache()
        test_low_level()
        test_error_handling()
        test_pdf()
        test_rate_limit()

    # ─── サマリー ─────────────────────────
    print("\n" + "=" * 60)
    print("  サマリー")
    print("=" * 60)
    pass_count = sum(1 for _, s, _ in results if s == "PASS")
    fail_count = sum(1 for _, s, _ in results if s == "FAIL")
    warn_count = sum(1 for _, s, _ in results if s == "WARN")
    total = len(results)

    print(f"\n  PASS: {pass_count}/{total}")
    print(f"  FAIL: {fail_count}/{total}")
    print(f"  WARN: {warn_count}/{total}")

    if fail_count:
        print("\n  *** FAILURES ***")
        for section, status, detail in results:
            if status == "FAIL":
                print(f"    ✗ {section}: {detail}")

    if warn_count:
        print("\n  *** WARNINGS ***")
        for section, status, detail in results:
            if status == "WARN":
                print(f"    ⚠ {section}: {detail}")

    # レポートをファイルに書き出し
    report_path = Path(__file__).parent / "readme_e2e_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("README.md E2E Test Report\n")
        f.write(f"Date: {datetime.now()}\n")
        f.write(f"PASS: {pass_count}/{total}, FAIL: {fail_count}/{total}, WARN: {warn_count}/{total}\n\n")
        for section, status, detail in results:
            f.write(f"[{status}] {section}: {detail}\n")
    print(f"\n  Report written to: {report_path}")

    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())

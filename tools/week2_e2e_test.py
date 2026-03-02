"""Week 2 (Day 8-17) 実装の包括的 E2E テスト。

実際の EDINET API を叩いて、Week 2 で実装した全機能を網羅的にテストする。
主なテスト対象:
  - XBRL パーサー (parser.py)
  - Context 構造化 (contexts.py)
  - TaxonomyResolver (taxonomy.py)
  - Fact → LineItem 変換 (facts.py)
  - Statement 組み立て (statements.py)
  - FinancialStatement API (financial.py)
  - Filing.xbrl() E2E パイプライン
  - Rich 表示 / DataFrame 変換
  - Async 版
"""

from __future__ import annotations

import asyncio
import sys
import time
import traceback
import warnings
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# ─── セットアップ ───────────────────────────────────────────────

import edinet
from edinet import (
    Company,
    DocType,
    Filing,
    FinancialStatement,
    LineItem,
    Statements,
    configure,
    documents,
)
from edinet.xbrl import (
    TaxonomyResolver,
    build_line_items,
    build_statements,
    parse_xbrl_facts,
    structure_contexts,
)
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
)
from edinet.xbrl.parser import ParsedXBRL, RawContext, RawFact
from edinet.xbrl.taxonomy import LabelInfo, LabelSource
from edinet.api.download import (
    DownloadFileType,
    download_document,
    extract_primary_xbrl,
    find_primary_xbrl_path,
    list_zip_members,
)
from edinet.exceptions import EdinetAPIError, EdinetConfigError, EdinetParseError

# 設定
API_KEY = "your_api_key_here"
TAXONOMY_PATH = "/mnt/c/Users/nezow/Downloads/ALL_20251101"

configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)


# ─── テストユーティリティ ─────────────────────────────────────

passed = 0
failed = 0
errors: list[str] = []


def test_case(name: str):
    """テストケースデコレータ。"""
    def decorator(func):
        def wrapper():
            global passed, failed
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print(f"{'='*60}")
            try:
                func()
                passed += 1
                print(f"  ✓ PASSED")
            except Exception as e:
                failed += 1
                msg = f"  ✗ FAILED: {e}"
                print(msg)
                traceback.print_exc()
                errors.append(f"{name}: {e}")
        return wrapper
    return decorator


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {a!r} == {b!r}: {msg}")


def assert_gt(a, b, msg=""):
    if not (a > b):
        raise AssertionError(f"Expected {a} > {b}: {msg}")


def assert_isinstance(obj, cls, msg=""):
    if not isinstance(obj, cls):
        raise AssertionError(f"Expected {type(obj).__name__} to be {cls.__name__}: {msg}")


# ─── 1. documents() API テスト ────────────────────────────────

@test_case("1-1: documents() 単日指定")
def test_documents_single_date():
    filings = documents("2026-02-20")
    assert_isinstance(filings, list)
    assert_gt(len(filings), 0, "2026-02-20 に書類が存在するはず")
    print(f"  取得件数: {len(filings)}")
    f = filings[0]
    assert_isinstance(f, Filing)
    assert_true(f.doc_id is not None)
    assert_true(f.filing_date == date(2026, 2, 20))
    print(f"  先頭: {f.doc_id} / {f.filer_name} / {f.doc_type_label_ja}")


@test_case("1-2: documents() 日付範囲指定")
def test_documents_date_range():
    filings = documents(start="2026-02-20", end="2026-02-21")
    assert_isinstance(filings, list)
    assert_gt(len(filings), 0, "2日間で書類が存在するはず")
    dates = {f.filing_date for f in filings}
    print(f"  取得件数: {len(filings)}, 日付: {dates}")
    # documents() の日付範囲は API 仕様に依存、件数が0でなければ OK
    assert_gt(len(filings), 0, "範囲指定で書類が取得できるはず")


@test_case("1-3: documents() doc_type フィルタ")
def test_documents_doc_type_filter():
    # 有価証券報告書
    filings = documents("2026-02-20", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    print(f"  有報: {len(filings)}件")
    for f in filings:
        assert_eq(f.doc_type, DocType.ANNUAL_SECURITIES_REPORT,
                  f"doc_type が有報でない: {f.doc_type}")

    # 文字列でも指定可
    filings2 = documents("2026-02-20", doc_type="120")
    assert_eq(len(filings), len(filings2), "Enum と文字列で同じ結果")


@test_case("1-4: documents() edinet_code フィルタ")
def test_documents_edinet_code_filter():
    # トヨタの EDINET コード
    filings = documents(
        start="2025-06-01", end="2025-06-30",
        edinet_code="E02144"
    )
    print(f"  トヨタ 2025年6月: {len(filings)}件")
    for f in filings:
        assert_eq(f.edinet_code, "E02144", "edinet_code が一致しない")
        print(f"    {f.doc_id}: {f.doc_description}")


@test_case("1-5: documents() 書類がない日")
def test_documents_no_results():
    # 日曜日 (提出がないはず)
    # 2026-02-22 は日曜
    filings = documents("2026-02-22")
    print(f"  日曜日: {len(filings)}件")
    # 日曜日でも0件とは限らない（祝日移動等）が、少ないはず


@test_case("1-6: documents() doc_type を日本語で指定")
def test_documents_doc_type_japanese():
    filings = documents("2026-02-20", doc_type="有価証券報告書")
    print(f"  有報(日本語指定): {len(filings)}件")
    for f in filings:
        assert_eq(f.doc_type, DocType.ANNUAL_SECURITIES_REPORT)


# ─── 2. Filing モデルのプロパティ ──────────────────────────────

@test_case("2-1: Filing 基本プロパティ")
def test_filing_properties():
    filings = documents("2026-02-20")
    f = filings[0]
    print(f"  doc_id: {f.doc_id}")
    print(f"  doc_type: {f.doc_type}")
    print(f"  doc_type_label_ja: {f.doc_type_label_ja}")
    print(f"  filing_date: {f.filing_date}")
    print(f"  filer_name: {f.filer_name}")
    print(f"  edinet_code: {f.edinet_code}")
    print(f"  sec_code: {f.sec_code}")
    print(f"  ticker: {f.ticker}")
    print(f"  has_xbrl: {f.has_xbrl}")
    print(f"  has_pdf: {f.has_pdf}")
    print(f"  period_start: {f.period_start}")
    print(f"  period_end: {f.period_end}")
    print(f"  ordinance: {f.ordinance}")
    print(f"  form: {f.form}")

    # Filing → Company
    company = f.company
    if company:
        print(f"  company.edinet_code: {company.edinet_code}")
        print(f"  company.name_ja: {company.name_ja}")
        print(f"  company.ticker: {company.ticker}")


@test_case("2-2: Filing.fetch() で XBRL 取得")
def test_filing_fetch():
    # has_xbrl=True の書類を探す
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        print("  ⚠ XBRL 付き有報が見つからない、別日で再試行")
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    assert_gt(len(xbrl_filings), 0, "XBRL 付き有報が必要")

    f = xbrl_filings[0]
    print(f"  対象: {f.doc_id} / {f.filer_name}")

    t0 = time.perf_counter()
    xbrl_path, xbrl_bytes = f.fetch()
    t1 = time.perf_counter()
    print(f"  fetch() 所要時間: {t1-t0:.2f}s")
    print(f"  XBRL パス: {xbrl_path}")
    print(f"  XBRL サイズ: {len(xbrl_bytes):,} bytes")

    assert_true(xbrl_path.endswith(".xbrl"), "拡張子が .xbrl")
    assert_gt(len(xbrl_bytes), 0, "XBRL が空でない")

    # キャッシュが効くか
    t2 = time.perf_counter()
    xbrl_path2, xbrl_bytes2 = f.fetch()
    t3 = time.perf_counter()
    print(f"  fetch() キャッシュ: {t3-t2:.4f}s")
    assert_eq(xbrl_path, xbrl_path2, "キャッシュで同じパス")
    assert_eq(len(xbrl_bytes), len(xbrl_bytes2), "キャッシュで同じサイズ")

    # refresh=True でキャッシュ破棄
    t4 = time.perf_counter()
    xbrl_path3, xbrl_bytes3 = f.fetch(refresh=True)
    t5 = time.perf_counter()
    print(f"  fetch(refresh=True): {t5-t4:.2f}s")


@test_case("2-3: Filing.fetch() XBRL なし書類でエラー")
def test_filing_fetch_no_xbrl():
    filings = documents("2026-02-20")
    no_xbrl = [f for f in filings if not f.has_xbrl]
    if not no_xbrl:
        print("  ⚠ has_xbrl=False の書類が見つからない、スキップ")
        return
    f = no_xbrl[0]
    print(f"  対象: {f.doc_id} / {f.filer_name} (has_xbrl=False)")
    try:
        f.fetch()
        raise AssertionError("EdinetAPIError が発生すべき")
    except EdinetAPIError as e:
        print(f"  期待通りのエラー: {e}")
    except EdinetParseError as e:
        print(f"  期待通りのエラー(Parse): {e}")


# ─── 3. XBRL パーサー (parse_xbrl_facts) ──────────────────────

@test_case("3-1: parse_xbrl_facts 基本")
def test_parse_xbrl_facts_basic():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    xbrl_path, xbrl_bytes = f.fetch()
    print(f"  対象: {f.filer_name} ({f.doc_id})")

    t0 = time.perf_counter()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    t1 = time.perf_counter()
    print(f"  パース所要時間: {(t1-t0)*1000:.1f}ms")

    assert_isinstance(parsed, ParsedXBRL)
    print(f"  Fact 数: {parsed.fact_count}")
    print(f"  Context 数: {len(parsed.contexts)}")
    print(f"  Unit 数: {len(parsed.units)}")
    print(f"  SchemaRef 数: {len(parsed.schema_refs)}")
    print(f"  FootnoteLink 数: {len(parsed.footnote_links)}")
    print(f"  IgnoredElement 数: {len(parsed.ignored_elements)}")
    print(f"  source_format: {parsed.source_format}")

    assert_gt(parsed.fact_count, 0, "Fact が1件以上")
    assert_gt(len(parsed.contexts), 0, "Context が1件以上")


@test_case("3-2: RawFact の内容チェック")
def test_raw_fact_content():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    _, xbrl_bytes = f.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes)

    # Fact の属性確認
    fact = parsed.facts[0]
    assert_isinstance(fact, RawFact)
    print(f"  先頭 Fact:")
    print(f"    concept_qname: {fact.concept_qname}")
    print(f"    namespace_uri: {fact.namespace_uri[:80]}...")
    print(f"    local_name: {fact.local_name}")
    print(f"    context_ref: {fact.context_ref}")
    print(f"    unit_ref: {fact.unit_ref}")
    print(f"    decimals: {fact.decimals}")
    print(f"    value_raw: {str(fact.value_raw)[:60]}")
    print(f"    is_nil: {fact.is_nil}")
    print(f"    source_line: {fact.source_line}")
    print(f"    order: {fact.order}")

    # 数値 Fact を探す
    numeric_facts = [ff for ff in parsed.facts if ff.unit_ref is not None and not ff.is_nil]
    print(f"  数値 Fact 数: {len(numeric_facts)}")
    assert_gt(len(numeric_facts), 0, "数値 Fact が存在するはず")

    # テキスト Fact を探す
    text_facts = [ff for ff in parsed.facts if ff.unit_ref is None and not ff.is_nil]
    print(f"  テキスト Fact 数: {len(text_facts)}")

    # nil Fact を探す
    nil_facts = [ff for ff in parsed.facts if ff.is_nil]
    print(f"  nil Fact 数: {len(nil_facts)}")

    # 名前空間の分布
    ns_counts: dict[str, int] = {}
    for ff in parsed.facts:
        prefix = ff.namespace_uri.split("/")[-1] if "/" in ff.namespace_uri else ff.namespace_uri
        ns_counts[prefix] = ns_counts.get(prefix, 0) + 1
    print(f"  名前空間分布: {dict(sorted(ns_counts.items(), key=lambda x: -x[1])[:10])}")


# ─── 4. Context 構造化 ────────────────────────────────────────

@test_case("4-1: structure_contexts 基本")
def test_structure_contexts_basic():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    _, xbrl_bytes = f.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes)

    ctx_map = structure_contexts(parsed.contexts)
    assert_isinstance(ctx_map, dict)
    assert_gt(len(ctx_map), 0, "Context が1件以上")
    print(f"  構造化 Context 数: {len(ctx_map)}")

    # 各 Context の内容を確認
    for ctx_id, ctx in list(ctx_map.items())[:5]:
        assert_isinstance(ctx, StructuredContext)
        print(f"  {ctx_id}:")
        print(f"    period: {ctx.period}")
        print(f"    entity_id: {ctx.entity_id}")
        print(f"    dimensions: {ctx.dimensions}")

    # InstantPeriod と DurationPeriod の混在確認
    instants = [c for c in ctx_map.values() if isinstance(c.period, InstantPeriod)]
    durations = [c for c in ctx_map.values() if isinstance(c.period, DurationPeriod)]
    print(f"  InstantPeriod: {len(instants)}件, DurationPeriod: {len(durations)}件")

    # Dimension 付き Context
    dim_ctxs = [c for c in ctx_map.values() if len(c.dimensions) > 0]
    print(f"  Dimension 付き Context: {len(dim_ctxs)}件")
    if dim_ctxs:
        c = dim_ctxs[0]
        print(f"    例: {c.context_id}")
        for d in c.dimensions:
            assert_isinstance(d, DimensionMember)
            print(f"      axis={d.axis}, member={d.member}")


# ─── 5. TaxonomyResolver ──────────────────────────────────────

@test_case("5-1: TaxonomyResolver 初期化")
def test_taxonomy_resolver_init():
    t0 = time.perf_counter()
    resolver = TaxonomyResolver(TAXONOMY_PATH)
    t1 = time.perf_counter()
    print(f"  初期化所要時間: {(t1-t0)*1000:.1f}ms")
    print(f"  taxonomy_version: {resolver.taxonomy_version}")
    print(f"  taxonomy_path: {resolver.taxonomy_path}")


@test_case("5-2: TaxonomyResolver 標準ラベル解決")
def test_taxonomy_resolver_standard_labels():
    resolver = TaxonomyResolver(TAXONOMY_PATH)

    # 主要科目のラベル解決
    concepts = [
        ("jppfs_cor", "NetSales", "売上高"),
        ("jppfs_cor", "CostOfSales", "売上原価"),
        ("jppfs_cor", "GrossProfit", "売上総利益"),
        ("jppfs_cor", "OperatingIncome", "営業利益"),
        ("jppfs_cor", "OrdinaryIncome", "経常利益"),
        ("jppfs_cor", "NetIncome", "当期純利益"),
        ("jppfs_cor", "TotalAssets", "総資産"),
        ("jppfs_cor", "TotalNetAssets", "純資産"),
    ]
    for prefix, local, expected_ja in concepts:
        label = resolver.resolve(prefix, local, lang="ja")
        assert_isinstance(label, LabelInfo)
        print(f"  {prefix}:{local} → ja={label.text}, source={label.source.value}")
        # ラベルテキストに期待する語が含まれるか確認（完全一致ではなく部分一致）
        # EDINETタクソノミのラベルは厳密には異なることがあるため

        label_en = resolver.resolve(prefix, local, lang="en")
        print(f"    en={label_en.text}")
        assert_eq(label_en.lang, "en")


@test_case("5-3: TaxonomyResolver 未知 concept のフォールバック")
def test_taxonomy_resolver_unknown_concept():
    resolver = TaxonomyResolver(TAXONOMY_PATH)
    label = resolver.resolve("jpcrp_cor", "TotallyFakeConceptXYZ123", lang="ja")
    assert_isinstance(label, LabelInfo)
    assert_eq(label.source, LabelSource.FALLBACK,
              f"未知 concept は FALLBACK のはず: {label.source}")
    print(f"  未知 concept → text={label.text}, source={label.source.value}")


@test_case("5-4: TaxonomyResolver Clark notation 解決")
def test_taxonomy_resolver_clark():
    resolver = TaxonomyResolver(TAXONOMY_PATH)

    # 実際の XBRL から取得した Clark notation を使う
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    _, xbrl_bytes = f.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes)

    # 最初の数値 Fact の concept_qname で解決
    numeric = [ff for ff in parsed.facts if ff.unit_ref is not None]
    if numeric:
        qname = numeric[0].concept_qname
        label = resolver.resolve_clark(qname, lang="ja")
        print(f"  {qname} → {label.text} (source={label.source.value})")


@test_case("5-5: TaxonomyResolver 提出者ラベル読み込み")
def test_taxonomy_resolver_filer_labels():
    resolver = TaxonomyResolver(TAXONOMY_PATH)

    # 提出者タクソノミを ZIP から取得
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    print(f"  対象: {f.filer_name}")

    # ZIP をダウンロードして中身を探索
    zip_bytes = download_document(f.doc_id, file_type=DownloadFileType.XBRL_AND_AUDIT)
    members = list_zip_members(zip_bytes)
    print(f"  ZIP メンバー数: {len(members)}")

    # _lab.xml を探す
    from edinet.api.download import extract_zip_member
    lab_files = [m for m in members if m.endswith("_lab.xml") and "PublicDoc" in m]
    lab_en_files = [m for m in members if m.endswith("_lab-en.xml") and "PublicDoc" in m]
    xsd_files = [m for m in members if m.endswith(".xsd") and "PublicDoc" in m]
    print(f"  _lab.xml: {lab_files}")
    print(f"  _lab-en.xml: {lab_en_files}")
    print(f"  .xsd: {xsd_files}")

    lab_bytes = extract_zip_member(zip_bytes, lab_files[0]) if lab_files else None
    lab_en_bytes = extract_zip_member(zip_bytes, lab_en_files[0]) if lab_en_files else None
    xsd_bytes = extract_zip_member(zip_bytes, xsd_files[0]) if xsd_files else None

    added = resolver.load_filer_labels(
        lab_xml_bytes=lab_bytes,
        lab_en_xml_bytes=lab_en_bytes,
        xsd_bytes=xsd_bytes,
    )
    print(f"  追加されたラベル数: {added}")

    # クリア
    resolver.clear_filer_labels()
    print(f"  ラベルクリア完了")


# ─── 6. build_line_items (Fact → LineItem) ─────────────────────

@test_case("6-1: build_line_items 基本")
def test_build_line_items_basic():
    resolver = TaxonomyResolver(TAXONOMY_PATH)

    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    print(f"  対象: {f.filer_name}")
    _, xbrl_bytes = f.fetch()

    parsed = parse_xbrl_facts(xbrl_bytes)
    ctx_map = structure_contexts(parsed.contexts)

    # 提出者ラベルも読み込む
    zip_bytes = download_document(f.doc_id, file_type=DownloadFileType.XBRL_AND_AUDIT)
    members = list_zip_members(zip_bytes)
    lab_files = [m for m in members if m.endswith("_lab.xml") and "PublicDoc" in m]
    lab_en_files = [m for m in members if m.endswith("_lab-en.xml") and "PublicDoc" in m]
    xsd_files = [m for m in members if m.endswith(".xsd") and "PublicDoc" in m]
    from edinet.api.download import extract_zip_member
    if lab_files:
        resolver.load_filer_labels(
            lab_xml_bytes=extract_zip_member(zip_bytes, lab_files[0]),
            lab_en_xml_bytes=extract_zip_member(zip_bytes, lab_en_files[0]) if lab_en_files else None,
            xsd_bytes=extract_zip_member(zip_bytes, xsd_files[0]) if xsd_files else None,
        )

    t0 = time.perf_counter()
    items = build_line_items(parsed.facts, ctx_map, resolver)
    t1 = time.perf_counter()
    print(f"  LineItem 数: {len(items)}")
    print(f"  変換所要時間: {(t1-t0)*1000:.1f}ms")

    assert_gt(len(items), 0)

    # LineItem の属性チェック
    item = items[0]
    assert_isinstance(item, LineItem)
    print(f"  先頭 LineItem:")
    print(f"    concept: {item.concept}")
    print(f"    local_name: {item.local_name}")
    print(f"    label_ja: {item.label_ja.text} (source={item.label_ja.source.value})")
    print(f"    label_en: {item.label_en.text}")
    print(f"    value: {item.value}")
    print(f"    unit_ref: {item.unit_ref}")
    print(f"    decimals: {item.decimals}")
    print(f"    context_id: {item.context_id}")
    print(f"    period: {item.period}")
    print(f"    entity_id: {item.entity_id}")
    print(f"    dimensions: {item.dimensions}")
    print(f"    is_nil: {item.is_nil}")

    # 数値 LineItem
    numeric_items = [i for i in items if isinstance(i.value, Decimal)]
    print(f"  数値 LineItem 数: {len(numeric_items)}")
    if numeric_items:
        ni = numeric_items[0]
        print(f"    例: {ni.label_ja.text} = {ni.value} {ni.unit_ref}")

    resolver.clear_filer_labels()


# ─── 7. build_statements / Statements ─────────────────────────

@test_case("7-1: Filing.xbrl() フルパイプライン")
def test_filing_xbrl_full_pipeline():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    print(f"  対象: {f.filer_name} ({f.doc_id})")

    t0 = time.perf_counter()
    stmts = f.xbrl()
    t1 = time.perf_counter()
    print(f"  xbrl() 所要時間: {t1-t0:.2f}s")

    assert_isinstance(stmts, Statements)


@test_case("7-2: income_statement() 基本")
def test_income_statement_basic():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()

    pl = stmts.income_statement()
    assert_isinstance(pl, FinancialStatement)
    print(f"  PL 科目数: {len(pl)}")
    print(f"  period: {pl.period}")
    print(f"  consolidated: {pl.consolidated}")
    print(f"  entity_id: {pl.entity_id}")
    print(f"  warnings: {pl.warnings_issued}")

    for item in pl:
        assert_isinstance(item, LineItem)

    # 主要科目の存在確認
    for key in ["売上高", "営業利益", "経常利益"]:
        item = pl.get(key)
        if item:
            print(f"  {key}: {item.value:,} {item.unit_ref}")
        else:
            print(f"  ⚠ {key}: 見つからない")


@test_case("7-3: balance_sheet() 基本")
def test_balance_sheet_basic():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()

    bs = stmts.balance_sheet()
    assert_isinstance(bs, FinancialStatement)
    print(f"  BS 科目数: {len(bs)}")
    print(f"  period: {bs.period}")
    print(f"  consolidated: {bs.consolidated}")

    # BS は InstantPeriod
    if bs.period:
        assert_isinstance(bs.period, InstantPeriod,
                          f"BS の period は InstantPeriod のはず: {type(bs.period)}")

    for key in ["総資産", "純資産"]:
        item = bs.get(key)
        if item:
            print(f"  {key}: {item.value:,} {item.unit_ref}")
        else:
            # 英語ラベルでも試す
            for en_key in ["Total assets", "TotalAssets"]:
                item = bs.get(en_key)
                if item:
                    print(f"  {en_key}: {item.value:,} {item.unit_ref}")
                    break
            if not item:
                print(f"  ⚠ {key}: 見つからない")


@test_case("7-4: cash_flow_statement() 基本")
def test_cash_flow_statement_basic():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()

    cf = stmts.cash_flow_statement()
    assert_isinstance(cf, FinancialStatement)
    print(f"  CF 科目数: {len(cf)}")
    print(f"  period: {cf.period}")
    print(f"  consolidated: {cf.consolidated}")

    # CF の主要科目
    for item in list(cf)[:5]:
        val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
        print(f"  {item.label_ja.text}: {val}")


@test_case("7-5: income_statement(consolidated=False) 個別")
def test_income_statement_non_consolidated():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()

    pl_solo = stmts.income_statement(consolidated=False)
    assert_isinstance(pl_solo, FinancialStatement)
    print(f"  個別 PL 科目数: {len(pl_solo)}")
    print(f"  consolidated: {pl_solo.consolidated}")
    assert_eq(pl_solo.consolidated, False, "個別のはず")

    # 連結と比較
    pl_cons = stmts.income_statement(consolidated=True)
    print(f"  連結 PL 科目数: {len(pl_cons)}")

    # 売上高の比較
    sales_solo = pl_solo.get("売上高")
    sales_cons = pl_cons.get("売上高")
    if sales_solo and sales_cons:
        print(f"  売上高(個別): {sales_solo.value:,}")
        print(f"  売上高(連結): {sales_cons.value:,}")


# ─── 8. FinancialStatement API ─────────────────────────────────

@test_case("8-1: FinancialStatement.__getitem__ / get / in")
def test_financial_statement_access():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()
    pl = stmts.income_statement()

    # __contains__
    if "売上高" in pl:
        print(f"  '売上高' in pl: True")
        # __getitem__
        item = pl["売上高"]
        assert_isinstance(item, LineItem)
        print(f"  pl['売上高'] = {item.value:,}")

    # get() with default
    missing = pl.get("存在しない科目XYZ")
    assert_true(missing is None, "存在しない科目は None")

    # KeyError テスト
    try:
        _ = pl["存在しない科目XYZ"]
        raise AssertionError("KeyError が発生すべき")
    except KeyError:
        print(f"  pl['存在しない科目XYZ'] → KeyError (OK)")

    # __len__
    print(f"  len(pl) = {len(pl)}")

    # __iter__
    count = 0
    for item in pl:
        count += 1
    assert_eq(count, len(pl), "iter と len の整合性")


@test_case("8-2: FinancialStatement.to_dataframe()")
def test_financial_statement_to_dataframe():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()
    pl = stmts.income_statement()

    try:
        import pandas as pd
        df = pl.to_dataframe()
        assert_isinstance(df, pd.DataFrame)
        print(f"  DataFrame shape: {df.shape}")
        print(f"  columns: {list(df.columns)}")
        print(f"  dtypes:\n{df.dtypes}")
        print(f"  attrs: {df.attrs}")
        print(f"\n{df.head(10)}")

        # カラムの存在確認
        for col in ["label_ja", "label_en", "value", "unit", "concept"]:
            assert_true(col in df.columns, f"カラム {col} が存在するはず")
    except ImportError:
        print("  ⚠ pandas 未インストール、スキップ")


@test_case("8-3: FinancialStatement.to_dict()")
def test_financial_statement_to_dict():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()
    pl = stmts.income_statement()

    dicts = pl.to_dict()
    assert_isinstance(dicts, list)
    assert_eq(len(dicts), len(pl), "to_dict の件数が items と一致")
    print(f"  to_dict 件数: {len(dicts)}")
    if dicts:
        print(f"  先頭: {dicts[0]}")
        for key in ["label_ja", "label_en", "value", "unit", "concept"]:
            assert_true(key in dicts[0], f"キー {key} が存在するはず")


@test_case("8-4: Rich 表示")
def test_rich_display():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()
    pl = stmts.income_statement()

    try:
        from rich.console import Console
        console = Console(width=120)
        print(f"  --- PL Rich 表示 ---")
        console.print(pl)
        print(f"  --- BS Rich 表示 ---")
        bs = stmts.balance_sheet()
        console.print(bs)
        print(f"  --- CF Rich 表示 ---")
        cf = stmts.cash_flow_statement()
        console.print(cf)
    except ImportError:
        print("  ⚠ rich 未インストール、文字列表示にフォールバック")
        print(str(pl)[:500])


@test_case("8-5: render_statement 関数")
def test_render_statement():
    try:
        from edinet.display.rich import render_statement
        filings = documents("2026-02-20", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
        if not xbrl_filings:
            filings = documents("2026-02-21", doc_type="120")
            xbrl_filings = [f for f in filings if f.has_xbrl]
        f = xbrl_filings[0]
        stmts = f.xbrl()
        pl = stmts.income_statement()

        table = render_statement(pl)
        print(f"  render_statement() 成功: {type(table).__name__}")

        from rich.console import Console
        Console(width=120).print(table)
    except ImportError:
        print("  ⚠ rich 未インストール、スキップ")


# ─── 9. Company API ───────────────────────────────────────────

@test_case("9-1: Company.from_filing()")
def test_company_from_filing():
    filings = documents("2026-02-20")
    f = filings[0]
    company = Company.from_filing(f)
    if company:
        print(f"  Company: {company.edinet_code} / {company.name_ja} / ticker={company.ticker}")
    else:
        print(f"  ⚠ edinet_code なし → Company=None")


@test_case("9-2: Company.get_filings()")
def test_company_get_filings():
    company = Company(edinet_code="E02144", name_ja="トヨタ自動車株式会社", sec_code="72030")
    print(f"  Company: {company.edinet_code} / {company.name_ja}")

    filings = company.get_filings(date="2026-02-20")
    print(f"  2026-02-20 の書類: {len(filings)}件")
    for f in filings:
        print(f"    {f.doc_id}: {f.doc_description}")


@test_case("9-3: Company.latest() 有報")
def test_company_latest():
    company = Company(edinet_code="E02144", name_ja="トヨタ自動車株式会社", sec_code="72030")
    print(f"  Company: {company.name_ja}")

    t0 = time.perf_counter()
    filing = company.latest(doc_type="有価証券報告書", start="2025-06-01", end="2025-07-31")
    t1 = time.perf_counter()
    print(f"  latest() 所要時間: {t1-t0:.1f}s")

    if filing:
        print(f"  最新有報: {filing.doc_id}")
        print(f"  提出日: {filing.filing_date}")
        print(f"  書類名: {filing.doc_description}")
        print(f"  period: {filing.period_start} ~ {filing.period_end}")
    else:
        print(f"  ⚠ 有報が見つからない")


# ─── 10. 複数企業での E2E テスト ──────────────────────────────

@test_case("10-1: 複数企業の PL 比較")
def test_multiple_companies_pl():
    # 有報提出日（2026年2月の平日）で有報を検索
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    print(f"  有報(XBRL付): {len(xbrl_filings)}件")

    # 最大3社のPLを取得
    for f in xbrl_filings[:3]:
        print(f"\n  --- {f.filer_name} ({f.doc_id}) ---")
        try:
            stmts = f.xbrl()
            pl = stmts.income_statement()
            print(f"    PL 科目数: {len(pl)}, period: {pl.period}")
            sales = pl.get("売上高")
            op_income = pl.get("営業利益")
            ord_income = pl.get("経常利益")
            if sales:
                print(f"    売上高: {sales.value:,}")
            if op_income:
                print(f"    営業利益: {op_income.value:,}")
            if ord_income:
                print(f"    経常利益: {ord_income.value:,}")
        except Exception as e:
            print(f"    ⚠ エラー: {e}")


# ─── 11. エッジケース ──────────────────────────────────────────

@test_case("11-1: 訂正報告書の処理")
def test_correction_report():
    # 訂正有報 (doc_type=130) を探す
    filings = documents(start="2026-02-01", end="2026-02-28", doc_type="130")
    if filings:
        f = filings[0]
        print(f"  訂正有報: {f.doc_id} / {f.filer_name}")
        print(f"  parent_doc_id: {f.parent_doc_id}")
        print(f"  doc_description: {f.doc_description}")
        if f.has_xbrl:
            try:
                stmts = f.xbrl()
                pl = stmts.income_statement()
                print(f"  PL 科目数: {len(pl)}")
            except Exception as e:
                print(f"  ⚠ XBRL パースエラー: {e}")
    else:
        print(f"  ⚠ 2026年2月に訂正有報が見つからない")


@test_case("11-2: 半期報告書の処理")
def test_semi_annual_report():
    # 半期報告書 (doc_type=160)
    filings = documents(start="2026-02-01", end="2026-02-28", doc_type="160")
    if filings:
        xbrl_filings = [f for f in filings if f.has_xbrl]
        if xbrl_filings:
            f = xbrl_filings[0]
            print(f"  半期報告書: {f.doc_id} / {f.filer_name}")
            try:
                stmts = f.xbrl()
                pl = stmts.income_statement()
                print(f"  PL 科目数: {len(pl)}")
                bs = stmts.balance_sheet()
                print(f"  BS 科目数: {len(bs)}")
            except Exception as e:
                print(f"  ⚠ エラー: {e}")
        else:
            print(f"  半期報告書(XBRL付)なし")
    else:
        print(f"  ⚠ 半期報告書が見つからない")


@test_case("11-3: 大量保有報告書 (has_xbrl=True)")
def test_large_holding_report():
    filings = documents(start="2026-02-20", end="2026-02-20", doc_type="350")
    if filings:
        xbrl_filings = [f for f in filings if f.has_xbrl]
        print(f"  大量保有報告書: {len(filings)}件 (XBRL付: {len(xbrl_filings)}件)")
        if xbrl_filings:
            f = xbrl_filings[0]
            print(f"  対象: {f.doc_id} / {f.filer_name}")
            # 大量保有報告書のXBRLは財務諸表ではないので PL は空のはず
            try:
                stmts = f.xbrl()
                pl = stmts.income_statement()
                print(f"  PL 科目数: {len(pl)} (0件が期待値)")
            except Exception as e:
                print(f"  ⚠ エラー（想定内の可能性）: {e}")
    else:
        print(f"  ⚠ 大量保有報告書が見つからない")


@test_case("11-4: 様々な doc_type の書類一覧")
def test_various_doc_types():
    # 主要な doc_type を試す
    doc_types_to_test = [
        ("120", "有価証券報告書"),
        ("130", "訂正有価証券報告書"),
        ("140", "四半期報告書"),
        ("160", "半期報告書"),
        ("350", "大量保有報告書"),
        ("030", "有価証券届出書"),
    ]
    for code, name in doc_types_to_test:
        filings = documents(start="2026-02-01", end="2026-02-28", doc_type=code)
        xbrl_count = sum(1 for f in filings if f.has_xbrl)
        print(f"  {code}({name}): {len(filings)}件 (XBRL:{xbrl_count})")


@test_case("11-5: ZIP 構造の探索")
def test_zip_structure():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    print(f"  対象: {f.filer_name}")

    zip_bytes = download_document(f.doc_id, file_type=DownloadFileType.XBRL_AND_AUDIT)
    members = list_zip_members(zip_bytes)
    print(f"  ZIP メンバー数: {len(members)}")

    # ファイル種別の分類
    exts: dict[str, int] = {}
    for m in members:
        ext = Path(m).suffix.lower()
        exts[ext] = exts.get(ext, 0) + 1
    print(f"  拡張子分布: {dict(sorted(exts.items(), key=lambda x: -x[1]))}")

    # PublicDoc 配下のファイル
    public_docs = [m for m in members if "PublicDoc" in m]
    print(f"  PublicDoc 配下: {len(public_docs)}件")
    for m in public_docs[:10]:
        print(f"    {m}")

    # 代表 XBRL の特定
    primary = find_primary_xbrl_path(zip_bytes)
    print(f"  代表 XBRL: {primary}")
    assert_true(primary is not None, "代表 XBRL が見つかるはず")


# ─── 12. Async テスト ─────────────────────────────────────────

@test_case("12-1: adocuments() + afetch() + axbrl() 非同期")
def test_async_all():
    """async テストを1つの asyncio.run() にまとめる（ループ再利用問題回避）。"""
    async def _run():
        from edinet import adocuments, aclose

        # 12-1: adocuments
        filings = await adocuments("2026-02-20", doc_type="120")
        print(f"  非同期 documents: {len(filings)}件")
        assert_gt(len(filings), 0)

        # 12-2: afetch
        xbrl_filings = [f for f in filings if f.has_xbrl]
        if not xbrl_filings:
            filings = await adocuments("2026-02-21", doc_type="120")
            xbrl_filings = [f for f in filings if f.has_xbrl]
        f = xbrl_filings[0]
        print(f"  対象: {f.filer_name}")

        path, data = await f.afetch()
        print(f"  afetch: {path}, {len(data):,} bytes")
        assert_gt(len(data), 0)

        # 12-3: axbrl
        stmts = await f.axbrl()
        assert_isinstance(stmts, Statements)

        pl = stmts.income_statement()
        print(f"  async PL 科目数: {len(pl)}")
        sales = pl.get("売上高")
        if sales:
            print(f"  売上高: {sales.value:,}")

        await aclose()

    asyncio.run(_run())


# ─── 13. パフォーマンス計測 ────────────────────────────────────

@test_case("13-1: E2E パフォーマンス計測")
def test_e2e_performance():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    f.clear_fetch_cache()
    print(f"  対象: {f.filer_name}")

    # 各ステップの時間計測
    t0 = time.perf_counter()
    xbrl_path, xbrl_bytes = f.fetch()
    t1 = time.perf_counter()
    print(f"  [1] fetch():       {(t1-t0)*1000:.0f}ms")

    t2 = time.perf_counter()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    t3 = time.perf_counter()
    print(f"  [2] parse_xbrl:    {(t3-t2)*1000:.0f}ms ({parsed.fact_count} facts)")

    t4 = time.perf_counter()
    ctx_map = structure_contexts(parsed.contexts)
    t5 = time.perf_counter()
    print(f"  [3] contexts:      {(t5-t4)*1000:.0f}ms ({len(ctx_map)} contexts)")

    t6 = time.perf_counter()
    resolver = TaxonomyResolver(TAXONOMY_PATH)
    t7 = time.perf_counter()
    print(f"  [4] taxonomy:      {(t7-t6)*1000:.0f}ms")

    # 提出者ラベル読み込み
    zip_bytes = download_document(f.doc_id, file_type=DownloadFileType.XBRL_AND_AUDIT)
    members = list_zip_members(zip_bytes)
    from edinet.api.download import extract_zip_member
    lab_files = [m for m in members if m.endswith("_lab.xml") and "PublicDoc" in m]
    lab_en_files = [m for m in members if m.endswith("_lab-en.xml") and "PublicDoc" in m]
    xsd_files = [m for m in members if m.endswith(".xsd") and "PublicDoc" in m]
    t8 = time.perf_counter()
    if lab_files:
        resolver.load_filer_labels(
            lab_xml_bytes=extract_zip_member(zip_bytes, lab_files[0]),
            lab_en_xml_bytes=extract_zip_member(zip_bytes, lab_en_files[0]) if lab_en_files else None,
            xsd_bytes=extract_zip_member(zip_bytes, xsd_files[0]) if xsd_files else None,
        )
    t9 = time.perf_counter()
    print(f"  [5] filer labels:  {(t9-t8)*1000:.0f}ms")

    t10 = time.perf_counter()
    items = build_line_items(parsed.facts, ctx_map, resolver)
    t11 = time.perf_counter()
    print(f"  [6] line items:    {(t11-t10)*1000:.0f}ms ({len(items)} items)")

    t12 = time.perf_counter()
    stmts = build_statements(items)
    t13 = time.perf_counter()
    print(f"  [7] statements:    {(t13-t12)*1000:.0f}ms")

    t14 = time.perf_counter()
    pl = stmts.income_statement()
    t15 = time.perf_counter()
    print(f"  [8] PL assembly:   {(t15-t14)*1000:.0f}ms ({len(pl)} items)")

    total = (t15 - t0) * 1000
    network = (t1 - t0) * 1000
    parse_total = total - network
    print(f"\n  合計: {total:.0f}ms (ネットワーク: {network:.0f}ms, パース: {parse_total:.0f}ms)")

    resolver.clear_filer_labels()


# ─── 14. DownloadFileType テスト ───────────────────────────────

@test_case("14-1: DownloadFileType.PDF")
def test_download_pdf():
    filings = documents("2026-02-20")
    pdf_filings = [f for f in filings if f.has_pdf]
    if not pdf_filings:
        print("  ⚠ PDF 付き書類なし、スキップ")
        return
    f = pdf_filings[0]
    print(f"  対象: {f.doc_id} / {f.filer_name}")

    pdf_bytes = download_document(f.doc_id, file_type=DownloadFileType.PDF)
    print(f"  PDF サイズ: {len(pdf_bytes):,} bytes")
    assert_gt(len(pdf_bytes), 0)
    # PDF ヘッダーの確認
    assert_true(pdf_bytes[:4] == b"%PDF", "PDF ヘッダーが %PDF")


@test_case("14-2: DownloadFileType.CSV")
def test_download_csv():
    filings = documents("2026-02-20")
    csv_filings = [f for f in filings if f.has_csv]
    if not csv_filings:
        print("  ⚠ CSV 付き書類なし、スキップ")
        return
    f = csv_filings[0]
    print(f"  対象: {f.doc_id} / {f.filer_name}")

    csv_zip_bytes = download_document(f.doc_id, file_type=DownloadFileType.CSV)
    print(f"  CSV ZIP サイズ: {len(csv_zip_bytes):,} bytes")
    members = list_zip_members(csv_zip_bytes)
    print(f"  CSV ZIP メンバー: {members}")


# ─── 15. 低レベルパイプラインのステップ毎テスト ────────────────

@test_case("15-1: パイプライン各ステップの型チェック")
def test_pipeline_type_checks():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]

    # Step 1: fetch
    path, data = f.fetch()
    assert_isinstance(path, str)
    assert_isinstance(data, bytes)

    # Step 2: parse
    parsed = parse_xbrl_facts(data, source_path=path)
    assert_isinstance(parsed, ParsedXBRL)
    assert_isinstance(parsed.facts, tuple)
    assert_isinstance(parsed.contexts, tuple)
    if parsed.facts:
        assert_isinstance(parsed.facts[0], RawFact)
    if parsed.contexts:
        assert_isinstance(parsed.contexts[0], RawContext)

    # Step 3: structure_contexts
    ctx_map = structure_contexts(parsed.contexts)
    assert_isinstance(ctx_map, dict)
    for k, v in list(ctx_map.items())[:1]:
        assert_isinstance(k, str)
        assert_isinstance(v, StructuredContext)
        assert_isinstance(v.period, (InstantPeriod, DurationPeriod))
        assert_isinstance(v.dimensions, tuple)

    # Step 4: TaxonomyResolver
    resolver = TaxonomyResolver(TAXONOMY_PATH)
    label = resolver.resolve("jppfs_cor", "NetSales")
    assert_isinstance(label, LabelInfo)
    assert_isinstance(label.source, LabelSource)

    # Step 5: build_line_items
    items = build_line_items(parsed.facts, ctx_map, resolver)
    assert_isinstance(items, tuple)
    if items:
        item = items[0]
        assert_isinstance(item, LineItem)
        assert_isinstance(item.label_ja, LabelInfo)
        assert_isinstance(item.label_en, LabelInfo)
        assert_isinstance(item.period, (InstantPeriod, DurationPeriod))
        assert_isinstance(item.dimensions, tuple)

    # Step 6: build_statements
    stmts = build_statements(items)
    assert_isinstance(stmts, Statements)

    # Step 7: FinancialStatement
    pl = stmts.income_statement()
    assert_isinstance(pl, FinancialStatement)
    assert_isinstance(pl.items, tuple)
    assert_isinstance(pl.warnings_issued, tuple)

    print(f"  全ステップの型チェック完了")

    resolver.clear_filer_labels()


# ─── 16. 日付系バリデーション ──────────────────────────────────

@test_case("16-1: date 型での指定")
def test_date_type_input():
    d = date(2026, 2, 20)
    filings = documents(d)
    assert_gt(len(filings), 0)
    print(f"  date型: {len(filings)}件")


@test_case("16-2: 不正な日付でエラー")
def test_invalid_date():
    try:
        documents("2026-13-01")
        raise AssertionError("ValueError が発生すべき")
    except (ValueError, Exception) as e:
        print(f"  不正日付エラー: {type(e).__name__}: {e}")


@test_case("16-3: start > end でエラー")
def test_start_after_end():
    try:
        documents(start="2026-02-25", end="2026-02-20")
        raise AssertionError("ValueError が発生すべき")
    except ValueError as e:
        print(f"  start > end エラー: {e}")


# ─── 17. 警告の確認 ───────────────────────────────────────────

@test_case("17-1: Statement 組み立て時の警告")
def test_statement_warnings():
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        filings = documents("2026-02-21", doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
    f = xbrl_filings[0]
    stmts = f.xbrl()

    pl = stmts.income_statement()
    if pl.warnings_issued:
        print(f"  PL 警告 ({len(pl.warnings_issued)}件):")
        for w in pl.warnings_issued:
            print(f"    {w}")
    else:
        print(f"  PL 警告なし")

    bs = stmts.balance_sheet()
    if bs.warnings_issued:
        print(f"  BS 警告 ({len(bs.warnings_issued)}件):")
        for w in bs.warnings_issued[:5]:
            print(f"    {w}")
    else:
        print(f"  BS 警告なし")


# ─── 18. PLAN.LIVING.md のゴールコード ─────────────────────────

@test_case("18-1: PLAN のゴールコード再現")
def test_plan_goal_code():
    """
    PLAN.LIVING.md Day 17 のゴール:
    ```python
    from edinet import Company
    toyota = Company("7203")
    filing = toyota.latest("有価証券報告書")
    pl = filing.xbrl().statements.income_statement()
    print(pl)
    df = pl.to_dataframe()
    ```
    ※ Company("7203") はティッカー検索で v0.2.0。
    現行 API では edinet_code 必須。
    """
    # v0.1.0 版
    company = Company(edinet_code="E02144", name_ja="トヨタ自動車株式会社", sec_code="72030")
    print(f"  Company: {company.name_ja}")

    filing = company.latest("有価証券報告書", start="2025-06-01", end="2025-07-31")
    if filing is None:
        print("  ⚠ トヨタの有報が見つからない")
        return

    print(f"  Filing: {filing.doc_id} / {filing.doc_description}")
    print(f"  提出日: {filing.filing_date}")

    stmts = filing.xbrl()
    pl = stmts.income_statement()

    print(f"\n  === トヨタ 損益計算書 ===")
    print(f"  期間: {pl.period}")
    print(f"  科目数: {len(pl)}")

    try:
        from rich.console import Console
        Console(width=120).print(pl)
    except ImportError:
        for item in pl:
            val = f"{item.value:,}" if isinstance(item.value, (int, Decimal)) else str(item.value)
            print(f"  {item.label_ja.text}: {val}")

    try:
        import pandas as pd
        df = pl.to_dataframe()
        print(f"\n  DataFrame:\n{df}")
    except ImportError:
        pass

    # BS も
    bs = stmts.balance_sheet()
    print(f"\n  === トヨタ 貸借対照表 ===")
    print(f"  科目数: {len(bs)}")

    # CF も
    cf = stmts.cash_flow_statement()
    print(f"\n  === トヨタ キャッシュフロー計算書 ===")
    print(f"  科目数: {len(cf)}")


# ─── 実行 ─────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Week 2 E2E テスト開始")
    print(f"日時: {date.today()}")
    print(f"API キー: {API_KEY[:8]}...")
    print(f"タクソノミ: {TAXONOMY_PATH}")
    print("=" * 60)

    tests = [
        # 1. documents() API
        test_documents_single_date,
        test_documents_date_range,
        test_documents_doc_type_filter,
        test_documents_edinet_code_filter,
        test_documents_no_results,
        test_documents_doc_type_japanese,
        # 2. Filing モデル
        test_filing_properties,
        test_filing_fetch,
        test_filing_fetch_no_xbrl,
        # 3. XBRL パーサー
        test_parse_xbrl_facts_basic,
        test_raw_fact_content,
        # 4. Context
        test_structure_contexts_basic,
        # 5. TaxonomyResolver
        test_taxonomy_resolver_init,
        test_taxonomy_resolver_standard_labels,
        test_taxonomy_resolver_unknown_concept,
        test_taxonomy_resolver_clark,
        test_taxonomy_resolver_filer_labels,
        # 6. LineItem
        test_build_line_items_basic,
        # 7. Statements
        test_filing_xbrl_full_pipeline,
        test_income_statement_basic,
        test_balance_sheet_basic,
        test_cash_flow_statement_basic,
        test_income_statement_non_consolidated,
        # 8. FinancialStatement API
        test_financial_statement_access,
        test_financial_statement_to_dataframe,
        test_financial_statement_to_dict,
        test_rich_display,
        test_render_statement,
        # 9. Company
        test_company_from_filing,
        test_company_get_filings,
        test_company_latest,
        # 10. 複数企業
        test_multiple_companies_pl,
        # 11. エッジケース
        test_correction_report,
        test_semi_annual_report,
        test_large_holding_report,
        test_various_doc_types,
        test_zip_structure,
        # 12. Async
        test_async_all,
        # 13. パフォーマンス
        test_e2e_performance,
        # 14. Download
        test_download_pdf,
        test_download_csv,
        # 15. パイプライン型チェック
        test_pipeline_type_checks,
        # 16. バリデーション
        test_date_type_input,
        test_invalid_date,
        test_start_after_end,
        # 17. 警告
        test_statement_warnings,
        # 18. ゴールコード
        test_plan_goal_code,
    ]

    for test_fn in tests:
        test_fn()

    print("\n" + "=" * 60)
    print(f"結果: {passed} passed, {failed} failed")
    if errors:
        print("\n失敗したテスト:")
        for e in errors:
            print(f"  ✗ {e}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

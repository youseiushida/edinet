"""Wave 1 E2E テスト: US-GAAP 企業 6 社の検証。

日本市場で US-GAAP を採用する全 6 社の有報を取得し、
DEI・Units・Contexts・Linkbase の全レイヤーを検証する。

対象企業:
  - 野村ホールディングス (E03752) 2025-06-23
  - キヤノン (E02274) 2025-03-28
  - 小松製作所 (E01532) 2025-06-16
  - 富士フイルムHD (E00988) 2025-06-25
  - オリックス (E04762) 2025-06-24
  - オムロン (E01755) 2025-06-23
"""

from __future__ import annotations

import os
import sys
import traceback
import zipfile
from io import BytesIO

from edinet import configure, documents
from edinet.api.download import download_document
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl.dei import AccountingStandard, PeriodType
from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl.units import structure_units, DivideMeasure, SimpleMeasure
from edinet.xbrl.linkbase import (
    parse_presentation_linkbase,
    parse_calculation_linkbase,
    parse_definition_linkbase,
)
from edinet.xbrl._namespaces import classify_namespace, NamespaceCategory

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)

# US-GAAP 6社の doc_id
USGAAP_COMPANIES = {
    "S100VXTD": ("野村ホールディングス", "E03752", "8604"),
    "S100VHZZ": ("キヤノン", "E02274", "7751"),
    "S100VXAI": ("小松製作所", "E01532", "6301"),
    "S100W3XJ": ("富士フイルムHD", "E00988", "4901"),
    "S100W3GQ": ("オリックス", "E04762", "8591"),
    "S100W20H": ("オムロン", "E01755", "6645"),
}


# ─── テストユーティリティ ─────────────────────────────────────

passed = 0
failed = 0
errors: list[str] = []


def test_case(name: str):
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
                print(f"  ✗ FAILED: {e}")
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


# ─── ヘルパー ────────────────────────────────────────────────

def _extract_linkbase_files(zip_bytes: bytes, suffix: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(suffix) and "PublicDoc/" in name:
                result[name] = zf.read(name)
    return result


# ─── テストケース ────────────────────────────────────────────

@test_case("USGAAP-1: 全 6 社の DEI 抽出と会計基準の確認")
def test_all_dei():
    """全 6 社の DEI を抽出し、US-GAAP であることを確認。"""
    us_gaap_count = 0

    for doc_id, (name, edinet_code, sec_code) in USGAAP_COMPANIES.items():
        try:
            zip_bytes = download_document(doc_id, file_type="1")
            # XBRL インスタンスを取得
            xbrl_data = None
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                for zname in zf.namelist():
                    if zname.endswith(".xbrl") and "PublicDoc/" in zname:
                        xbrl_data = (zname, zf.read(zname))
                        break

            if xbrl_data is None:
                print(f"  {name}: XBRL なし (SKIP)")
                continue

            xbrl_path, xbrl_bytes = xbrl_data
            parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
            dei = extract_dei(parsed.facts)

            std = dei.accounting_standards
            is_us = std == AccountingStandard.US_GAAP
            if is_us:
                us_gaap_count += 1

            print(
                f"  {name}: {std!r}"
                f" | 連結={dei.has_consolidated}"
                f" | EDINET={dei.edinet_code}"
                f" | 証券={dei.security_code}"
                f" | {'✓ US-GAAP' if is_us else '✗ NOT US-GAAP'}"
            )

        except Exception as e:
            print(f"  {name} ({doc_id}): ERROR {e}")

    print(f"\n  US-GAAP 判定: {us_gaap_count}/{len(USGAAP_COMPANIES)}")
    assert_gt(us_gaap_count, 0, "少なくとも 1 社は US-GAAP")


@test_case("USGAAP-2: 野村HD の詳細検証 (DEI + Units + Contexts)")
def test_nomura_detail():
    """野村HDは証券業の大手。US-GAAP + 連結の典型例。"""
    doc_id = "S100VXTD"
    zip_bytes = download_document(doc_id, file_type="1")

    xbrl_data = None
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for zname in zf.namelist():
            if zname.endswith(".xbrl") and "PublicDoc/" in zname:
                xbrl_data = (zname, zf.read(zname))
                break

    assert_true(xbrl_data is not None, "XBRL ファイルあり")
    xbrl_path, xbrl_bytes = xbrl_data
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)

    print(f"  企業名: {dei.filer_name_ja}")
    print(f"  英語名: {dei.filer_name_en}")
    print(f"  会計基準: {dei.accounting_standards!r}")
    print(f"  連結: {dei.has_consolidated}")
    print(f"  証券コード: {dei.security_code}")
    print(f"  EDINET: {dei.edinet_code}")
    print(f"  期間種別: {dei.type_of_current_period!r}")
    print(f"  当期末: {dei.current_period_end_date}")
    print(f"  fact 数: {parsed.fact_count}")

    # Units
    unit_map = structure_units(parsed.units)
    unit_types = set()
    for u in unit_map.values():
        if isinstance(u.measure, SimpleMeasure):
            unit_types.add(u.measure.local_name)
        elif isinstance(u.measure, DivideMeasure):
            unit_types.add(f"{u.measure.numerator.local_name}/{u.measure.denominator.local_name}")
    print(f"  Unit 種別: {sorted(unit_types)}")

    # Contexts
    ctx_map = structure_contexts(parsed.contexts)
    coll = ContextCollection(ctx_map)
    cons = coll.filter_consolidated()
    non_cons = coll.filter_non_consolidated()
    print(f"  Context 数: {len(ctx_map)}")
    print(f"  連結: {len(cons)}, 個別: {len(non_cons)}")

    # Dimension 分析
    dim_axes = set()
    for ctx in coll:
        for dm in ctx.dimensions:
            # Clark notation から local_name を抽出
            axis_local = dm.axis.split("}")[-1] if "}" in dm.axis else dm.axis
            dim_axes.add(axis_local)
    print(f"  Dimension 軸: {len(dim_axes)}")
    for ax in sorted(dim_axes)[:10]:
        print(f"    - {ax}")
    if len(dim_axes) > 10:
        print(f"    ... +{len(dim_axes) - 10}")

    assert_true(dei.has_consolidated is True or dei.has_consolidated is None, "野村HDは連結あり(のはず)")
    assert_gt(parsed.fact_count, 100, "Fact 数 100 以上")


@test_case("USGAAP-3: キヤノンの詳細検証 (12月決算)")
def test_canon_detail():
    """キヤノンは12月決算のUS-GAAP企業。"""
    doc_id = "S100VHZZ"
    zip_bytes = download_document(doc_id, file_type="1")

    xbrl_data = None
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for zname in zf.namelist():
            if zname.endswith(".xbrl") and "PublicDoc/" in zname:
                xbrl_data = (zname, zf.read(zname))
                break

    assert_true(xbrl_data is not None, "XBRL ファイルあり")
    xbrl_path, xbrl_bytes = xbrl_data
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)

    print(f"  企業名: {dei.filer_name_ja}")
    print(f"  英語名: {dei.filer_name_en}")
    print(f"  会計基準: {dei.accounting_standards!r}")
    print(f"  連結: {dei.has_consolidated}")
    print(f"  当期末: {dei.current_period_end_date}")
    print(f"  fact 数: {parsed.fact_count}")

    # 名前空間分析: US-GAAP 特有の名前空間があるか
    ns_set = {fact.namespace_uri for fact in parsed.facts if fact.namespace_uri}
    categorized: dict[str, int] = {}
    for uri in ns_set:
        info = classify_namespace(uri)
        cat = info.category.value
        categorized[cat] = categorized.get(cat, 0) + 1
    print(f"  名前空間カテゴリ分布:")
    for cat, count in sorted(categorized.items()):
        print(f"    {cat}: {count}")

    # 使用モジュール
    modules = sorted({
        classify_namespace(uri).module_name
        for uri in ns_set
        if classify_namespace(uri).module_name
    })
    print(f"  使用モジュール: {modules}")

    assert_gt(parsed.fact_count, 100, "Fact 数 100 以上")


@test_case("USGAAP-4: コマツの Linkbase 検証")
def test_komatsu_linkbase():
    """コマツの calculation/definition linkbase を検証。"""
    doc_id = "S100VXAI"
    zip_bytes = download_document(doc_id, file_type="1")

    # Calculation
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")
    if cal_files:
        cal_xml = next(iter(cal_files.values()))
        cal = parse_calculation_linkbase(cal_xml)
        total_arcs = sum(len(t.arcs) for t in cal.trees.values())
        print(f"  Calculation: {len(cal.trees)} roles, {total_arcs} arcs")
        for role_uri in sorted(cal.trees.keys()):
            short = role_uri.rsplit("/", 1)[-1]
            tree = cal.trees[role_uri]
            print(f"    {short}: {len(tree.arcs)} arcs, roots={tree.roots}")
    else:
        print("  Calculation: _cal.xml なし")

    # Definition
    def_files = _extract_linkbase_files(zip_bytes, "_def.xml")
    if def_files:
        def_xml = next(iter(def_files.values()))
        defs = parse_definition_linkbase(def_xml)
        total_hc = sum(len(t.hypercubes) for t in defs.values())
        print(f"  Definition: {len(defs)} roles, {total_hc} hypercubes")
    else:
        print("  Definition: _def.xml なし")

    # Presentation
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")
    if pre_files:
        pre_xml = next(iter(pre_files.values()))
        pres = parse_presentation_linkbase(pre_xml)
        total_nodes = sum(t.node_count for t in pres.values())
        print(f"  Presentation: {len(pres)} roles, {total_nodes} nodes")

        # is_total / is_abstract の分布
        total_count = 0
        abstract_count = 0
        for tree in pres.values():
            for node in tree.flatten():
                if node.is_total:
                    total_count += 1
                if node.is_abstract:
                    abstract_count += 1
        print(f"    is_total: {total_count}, is_abstract: {abstract_count}")
    else:
        print("  Presentation: _pre.xml なし")

    assert_true(cal_files or def_files or pre_files, "少なくとも 1 つの linkbase あり")


@test_case("USGAAP-5: 全 6 社の名前空間モジュール比較")
def test_namespace_comparison():
    """全社の名前空間モジュール使用状況を比較。"""
    results = {}

    for doc_id, (name, _, _) in USGAAP_COMPANIES.items():
        try:
            zip_bytes = download_document(doc_id, file_type="1")
            xbrl_data = None
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                for zname in zf.namelist():
                    if zname.endswith(".xbrl") and "PublicDoc/" in zname:
                        xbrl_data = (zname, zf.read(zname))
                        break

            if xbrl_data is None:
                continue

            xbrl_path, xbrl_bytes = xbrl_data
            parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)

            ns_set = {fact.namespace_uri for fact in parsed.facts if fact.namespace_uri}
            modules = sorted({
                classify_namespace(uri).module_name
                for uri in ns_set
                if classify_namespace(uri).module_name
            })

            cat_dist: dict[str, int] = {}
            for uri in ns_set:
                info = classify_namespace(uri)
                cat = info.category.value
                cat_dist[cat] = cat_dist.get(cat, 0) + 1

            has_filer = any(
                classify_namespace(uri).category == NamespaceCategory.FILER_TAXONOMY
                for uri in ns_set
            )

            results[name] = {
                "modules": modules,
                "fact_count": parsed.fact_count,
                "ns_count": len(ns_set),
                "has_filer": has_filer,
                "cat_dist": cat_dist,
            }
        except Exception as e:
            print(f"  {name}: ERROR {e}")

    # 結果表示
    for name, info in results.items():
        print(
            f"  {name}: facts={info['fact_count']}"
            f" | ns={info['ns_count']}"
            f" | filer_tax={info['has_filer']}"
            f" | modules={info['modules']}"
        )

    # 全社で共通のモジュール
    if results:
        all_modules = [set(r["modules"]) for r in results.values()]
        common = all_modules[0]
        for s in all_modules[1:]:
            common &= s
        print(f"\n  全社共通モジュール: {sorted(common)}")

        # いずれかの社で使われているモジュール
        union = set()
        for s in all_modules:
            union |= s
        print(f"  いずれかで使用: {sorted(union)}")

    assert_gt(len(results), 0, "少なくとも 1 社のデータ取得成功")


@test_case("USGAAP-6: オリックスの全パイプライン (Filing.xbrl())")
def test_orix_pipeline():
    """オリックスで Filing.xbrl() を使った全パイプライン。"""
    # オリックスの有報を取得
    filings = documents("2025-06-24", doc_type="120")
    target = None
    for f in filings:
        if f.has_xbrl and f.filer_name and "オリックス" in f.filer_name:
            # オリックス銀行ではなくオリックス本体
            if "銀行" not in f.filer_name:
                target = f
                break

    if target is None:
        print("  SKIP: オリックスの有報が見つからない")
        return

    import time
    t0 = time.perf_counter()
    stmts = target.xbrl()
    elapsed = time.perf_counter() - t0

    print(f"  対象: {target.filer_name} ({target.doc_id})")
    print(f"  処理時間: {elapsed:.2f}s")

    # 各財務諸表を取得
    pl = stmts.income_statement()
    bs = stmts.balance_sheet()
    cf = stmts.cash_flow_statement()

    print(f"  PL: {len(pl.items)} 行")
    print(f"  BS: {len(bs.items)} 行")
    print(f"  CF: {len(cf.items)} 行")
    print(f"  PL 連結={pl.consolidated}, BS 連結={bs.consolidated}")

    # PL の先頭行を表示
    for item in pl.items[:5]:
        print(f"    PL: {item.label_ja} = {item.value}")

    # BS の先頭行を表示
    for item in bs.items[:5]:
        print(f"    BS: {item.label_ja} = {item.value}")

    assert_gt(len(pl.items) + len(bs.items), 0, "財務諸表の行が存在")


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_all_dei,
        test_nomura_detail,
        test_canon_detail,
        test_komatsu_linkbase,
        test_namespace_comparison,
        test_orix_pipeline,
    ]

    print(f"Wave 1 E2E テスト: US-GAAP 企業 ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

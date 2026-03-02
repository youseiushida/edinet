"""Wave 1 E2E テスト: 一般事業会社（連結・jpcrp・shares・DivideMeasure）。

6月提出の有報を使い、投資信託では検証できなかった以下を確認する:
  - shares / JPYPerShares (DivideMeasure) unit
  - 連結/個別の両方が存在する Context
  - 提出者タクソノミ (filer_taxonomy) の名前空間
  - jpcrp モジュールの存在
  - 大量の Context (100+) でのフィルタ性能
  - 複数の _pre.xml による merge_presentation_trees
  - DEI の has_consolidated=True

対象企業: 2025-06-26/27 提出の一般事業会社
"""

from __future__ import annotations

import os
import sys
import time
import traceback
import zipfile
from io import BytesIO

from edinet import configure, documents
from edinet.api.download import download_document
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl.contexts import ContextCollection, DurationPeriod, InstantPeriod, structure_contexts
from edinet.xbrl.dei import AccountingStandard, DEI, PeriodType
from edinet.xbrl.units import DivideMeasure, SimpleMeasure, StructuredUnit, structure_units
from edinet.xbrl._namespaces import NamespaceCategory, classify_namespace
from edinet.xbrl.linkbase import (
    PresentationTree,
    CalculationLinkbase,
    DefinitionTree,
    HypercubeInfo,
    merge_presentation_trees,
    parse_calculation_linkbase,
    parse_definition_linkbase,
    parse_presentation_linkbase,
)

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)


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


def assert_isinstance(obj, cls, msg=""):
    if not isinstance(obj, cls):
        raise AssertionError(f"Expected {type(obj).__name__} to be {cls.__name__}: {msg}")


# ─── データキャッシュ ────────────────────────────────────────

# 一般事業会社の doc_id（probe2 で発見済み）
# ナカバヤシ: 5種unit, 290ctx, 連結あり
TARGET_DOC_ID = "S100W4JX"
TARGET_NAME = "ナカバヤシ株式会社"

_zip_cache: dict[str, bytes] = {}
_parsed_cache: dict = {}


def _get_zip(doc_id: str) -> bytes:
    if doc_id not in _zip_cache:
        _zip_cache[doc_id] = download_document(doc_id, file_type="1")
    return _zip_cache[doc_id]


def _get_parsed(doc_id: str):
    if doc_id not in _parsed_cache:
        zip_bytes = _get_zip(doc_id)
        # primary XBRL を探す
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            xbrl_files = [
                n for n in zf.namelist()
                if "PublicDoc/" in n and n.endswith(".xbrl")
            ]
            if not xbrl_files:
                raise RuntimeError(f"XBRL ファイルが見つかりません: {doc_id}")
            xbrl_path = xbrl_files[0]
            xbrl_bytes = zf.read(xbrl_path)
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        _parsed_cache[doc_id] = (xbrl_path, parsed)
    return _parsed_cache[doc_id]


def _extract_linkbase_files(zip_bytes: bytes, suffix: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(suffix) and "PublicDoc/" in name:
                result[name] = zf.read(name)
    return result


# ─── テストケース ────────────────────────────────────────────

@test_case("GC-1: 一般事業会社の DEI 検証")
def test_general_corp_dei():
    """連結あり一般事業会社の DEI を検証。"""
    _, parsed = _get_parsed(TARGET_DOC_ID)
    dei = extract_dei(parsed.facts)

    print(f"  対象: {dei.filer_name_ja} (edinet={dei.edinet_code})")
    assert_isinstance(dei, DEI)
    assert_true(dei.has_consolidated is True, "連結あり")
    assert_true(
        dei.accounting_standards == AccountingStandard.JAPAN_GAAP,
        f"J-GAAP: {dei.accounting_standards}",
    )
    assert_true(dei.security_code is not None, f"証券コードあり: {dei.security_code}")
    assert_true(dei.type_of_current_period == PeriodType.FY, "有報=FY")
    assert_true(dei.edinet_code is not None, "EDINET コードあり")
    assert_true(dei.filer_name_en is not None, f"英語名あり: {dei.filer_name_en}")
    assert_true(dei.current_period_end_date is not None, "当期末あり")
    assert_true(dei.current_fiscal_year_start_date is not None, "当期開始あり")
    assert_true(dei.number_of_submission is not None, f"提出回数: {dei.number_of_submission}")

    print(f"  証券コード: {dei.security_code}")
    print(f"  英語名: {dei.filer_name_en}")
    print(f"  会計基準: {dei.accounting_standards}")
    print(f"  当期: {dei.current_fiscal_year_start_date} ～ {dei.current_period_end_date}")


@test_case("GC-2: shares / JPYPerShares / tCO2e Unit の検証")
def test_general_corp_units():
    """一般事業会社特有の Unit バリエーションを検証。"""
    _, parsed = _get_parsed(TARGET_DOC_ID)
    unit_map = structure_units(parsed.units)

    print(f"  Unit 数: {len(unit_map)}")
    for uid, u in unit_map.items():
        if isinstance(u.measure, SimpleMeasure):
            print(f"    {uid}: SimpleMeasure({u.measure.local_name}) | monetary={u.is_monetary} pure={u.is_pure} shares={u.is_shares}")
        elif isinstance(u.measure, DivideMeasure):
            print(f"    {uid}: DivideMeasure({u.measure.numerator.local_name}/{u.measure.denominator.local_name}) | per_share={u.is_per_share} currency={u.currency_code}")

    # JPY
    jpy_units = [u for u in unit_map.values() if isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "JPY"]
    assert_gt(len(jpy_units), 0, "JPY unit が存在")
    assert_true(jpy_units[0].is_monetary, "JPY is_monetary=True")
    assert_eq(jpy_units[0].currency_code, "JPY")

    # shares
    shares_units = [u for u in unit_map.values() if isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "shares"]
    assert_gt(len(shares_units), 0, "shares unit が存在")
    assert_true(shares_units[0].is_shares, "shares is_shares=True")
    assert_true(not shares_units[0].is_monetary, "shares is_monetary=False")

    # JPYPerShares (DivideMeasure)
    divide_units = [u for u in unit_map.values() if isinstance(u.measure, DivideMeasure)]
    assert_gt(len(divide_units), 0, "DivideMeasure が存在")
    per_share = [u for u in divide_units if u.is_per_share]
    assert_gt(len(per_share), 0, "per_share unit が存在")
    assert_eq(per_share[0].currency_code, "JPY", "per_share の currency_code は JPY")
    assert_true(not per_share[0].is_monetary, "per_share は is_monetary=False")

    # pure
    pure_units = [u for u in unit_map.values() if isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "pure"]
    assert_gt(len(pure_units), 0, "pure unit が存在")

    # tCO2e（特殊単位、ナカバヤシ固有）
    other_units = [u for u in unit_map.values() if not u.is_monetary and not u.is_pure and not u.is_shares and not u.is_per_share]
    if other_units:
        for ou in other_units:
            if isinstance(ou.measure, SimpleMeasure):
                print(f"  特殊 Unit 発見: {ou.unit_id} = {ou.measure.local_name} (ns={ou.measure.namespace_uri})")


@test_case("GC-3: 大量 Context での ContextCollection フィルタ")
def test_general_corp_contexts():
    """290+ Context での ContextCollection 操作を検証。"""
    _, parsed = _get_parsed(TARGET_DOC_ID)
    ctx_map = structure_contexts(parsed.contexts)
    coll = ContextCollection(ctx_map)

    print(f"  全 Context 数: {len(coll)}")
    assert_gt(len(coll), 100, "100+ Context が存在")

    # 連結と個別の両方
    cons = coll.filter_consolidated()
    non_cons = coll.filter_non_consolidated()
    print(f"  連結: {len(cons)}, 個別: {len(non_cons)}")
    assert_gt(len(cons), 0, "連結 Context が存在")
    assert_gt(len(non_cons), 0, "個別 Context が存在")

    # Instant/Duration
    instant = coll.filter_instant()
    duration = coll.filter_duration()
    print(f"  Instant: {len(instant)}, Duration: {len(duration)}")
    assert_gt(len(instant), 0, "Instant Context が存在")
    assert_gt(len(duration), 0, "Duration Context が存在")

    # メインの連結コンテキスト
    main = coll.filter_consolidated().filter_no_extra_dimensions()
    print(f"  連結+extra_dimsなし: {len(main)}")
    assert_gt(len(main), 0, "メイン連結 Context が存在")

    # ユニーク期間
    uip = coll.unique_instant_periods
    udp = coll.unique_duration_periods
    print(f"  ユニーク Instant: {len(uip)}, Duration: {len(udp)}")
    for p in uip[:5]:
        print(f"    Instant: {p.instant}")
    for p in udp[:5]:
        print(f"    Duration: {p.start_date} ～ {p.end_date}")

    # extra dimensions を持つ Context
    with_extra = [c for c in coll if c.has_extra_dimensions]
    print(f"  Extra dimensions 付き: {len(with_extra)}")
    if with_extra:
        axes = set()
        for c in with_extra:
            for d in c.dimensions:
                local = d.axis.split("}")[-1] if "}" in d.axis else d.axis
                axes.add(local)
        print(f"    軸: {sorted(axes)}")


@test_case("GC-4: 提出者タクソノミの名前空間分類")
def test_general_corp_namespaces():
    """一般事業会社の XBRL から filer_taxonomy が検出されることを確認。"""
    _, parsed = _get_parsed(TARGET_DOC_ID)

    ns_set = {fact.namespace_uri for fact in parsed.facts if fact.namespace_uri}
    print(f"  名前空間数: {len(ns_set)}")

    category_map: dict[str, list[str]] = {}
    for uri in sorted(ns_set):
        info = classify_namespace(uri)
        cat = info.category.value
        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(uri)

    for cat, uris in sorted(category_map.items()):
        print(f"  {cat}: {len(uris)}")
        for uri in uris[:3]:
            info = classify_namespace(uri)
            extras = []
            if info.module_name:
                extras.append(f"module={info.module_name}")
            if info.edinet_code:
                extras.append(f"edinet={info.edinet_code}")
            print(f"    {uri}" + (f" ({', '.join(extras)})" if extras else ""))

    # jpcrp モジュールが存在
    has_jpcrp = any(
        classify_namespace(uri).module_name and "jpcrp" in (classify_namespace(uri).module_name or "")
        for uri in ns_set
    )
    assert_true(has_jpcrp, "jpcrp モジュールが存在するはず")

    # filer taxonomy が存在
    filer_uris = [uri for uri in ns_set if classify_namespace(uri).category == NamespaceCategory.FILER_TAXONOMY]
    print(f"  filer_taxonomy: {len(filer_uris)} 件")
    if filer_uris:
        for uri in filer_uris:
            info = classify_namespace(uri)
            print(f"    edinet_code={info.edinet_code}: {uri[:80]}")


@test_case("GC-5: 複数 _pre.xml の merge_presentation_trees")
def test_general_corp_merge_pre():
    """一般事業会社の複数 _pre.xml をマージ。"""
    zip_bytes = _get_zip(TARGET_DOC_ID)
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")

    print(f"  _pre.xml ファイル数: {len(pre_files)}")
    assert_gt(len(pre_files), 0, "_pre.xml が存在")

    tree_dicts = []
    for path, xml_bytes in pre_files.items():
        trees = parse_presentation_linkbase(xml_bytes, source_path=path)
        tree_dicts.append(trees)
        total_nodes = sum(t.node_count for t in trees.values())
        print(f"    {os.path.basename(path)}: {len(trees)} roles, {total_nodes} nodes")

    if len(tree_dicts) >= 2:
        merged = merge_presentation_trees(*tree_dicts)
        merged_nodes = sum(t.node_count for t in merged.values())
        print(f"  マージ後: {len(merged)} roles, {merged_nodes} nodes")

        # マージ後のロール数 >= 各個のロール数
        all_roles = set()
        for td in tree_dicts:
            all_roles.update(td.keys())
        assert_eq(len(merged), len(all_roles), "マージ後ロール数 == ユニークロール数")

        # BS/PL/CF 関連ロールを確認
        for role_uri, tree in merged.items():
            short = role_uri.rsplit("/", 1)[-1]
            if any(k in short for k in ["BalanceSheet", "Income", "CashFlow", "ChangesInEquity"]):
                flat = tree.flatten(skip_abstract=True)
                print(f"    {short}: {tree.node_count} nodes ({len(flat)} non-abstract)")
    else:
        print("  SKIP: _pre.xml が 1 つのみ")


@test_case("GC-6: Calculation Linkbase の構造検証")
def test_general_corp_calculation():
    """一般事業会社の計算リンクベース。"""
    zip_bytes = _get_zip(TARGET_DOC_ID)
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")

    print(f"  _cal.xml ファイル数: {len(cal_files)}")
    assert_gt(len(cal_files), 0, "_cal.xml が存在")

    for path, xml_bytes in cal_files.items():
        lb = parse_calculation_linkbase(xml_bytes, source_path=path)
        print(f"    {os.path.basename(path)}:")
        print(f"      ロール数: {len(lb.trees)}")

        for role_uri in lb.role_uris:
            tree = lb.get_tree(role_uri)
            if tree is None:
                continue
            short = role_uri.rsplit("/", 1)[-1]
            add_count = sum(1 for a in tree.arcs if a.weight == 1)
            sub_count = sum(1 for a in tree.arcs if a.weight == -1)
            print(f"      {short}: arcs={len(tree.arcs)} (+{add_count}/-{sub_count}), roots={tree.roots}")

            # GrossProfit 等の典型的な計算構造を確認
            for root in tree.roots:
                children = lb.children_of(root, role_uri=role_uri)
                if children:
                    child_summary = ", ".join(
                        f"{'+' if a.weight == 1 else '-'}{a.child}" for a in children[:5]
                    )
                    print(f"        {root} = {child_summary}")


@test_case("GC-7: Definition Linkbase のハイパーキューブ構造")
def test_general_corp_definition():
    """一般事業会社の定義リンクベース。"""
    zip_bytes = _get_zip(TARGET_DOC_ID)
    def_files = _extract_linkbase_files(zip_bytes, "_def.xml")

    print(f"  _def.xml ファイル数: {len(def_files)}")
    assert_gt(len(def_files), 0, "_def.xml が存在")

    total_hc = 0
    for path, xml_bytes in def_files.items():
        trees = parse_definition_linkbase(xml_bytes, source_path=path)
        hc_trees = [(r, t) for r, t in trees.items() if t.has_hypercube]

        for role_uri, tree in hc_trees:
            for hc in tree.hypercubes:
                total_hc += 1
                short = role_uri.rsplit("/", 1)[-1]
                axes_names = [a.axis_concept for a in hc.axes]
                print(
                    f"    {short}: table={hc.table_concept}"
                    f" | closed={hc.closed}"
                    f" | ctx_elem={hc.context_element}"
                    f" | axes={axes_names}"
                    f" | line_items={hc.line_items_concept}"
                )

                # Axis の中身を確認
                for axis in hc.axes:
                    if axis.domain is not None:
                        # メンバー数を数える
                        def count_members(node):
                            return 1 + sum(count_members(c) for c in node.children)
                        member_count = count_members(axis.domain)
                        print(f"      axis={axis.axis_concept}: domain={axis.domain.concept}, members={member_count}, default={axis.default_member}")

    print(f"  合計ハイパーキューブ数: {total_hc}")
    assert_gt(total_hc, 0, "ハイパーキューブが存在")


@test_case("GC-8: Filing.xbrl() パイプライン全体")
def test_general_corp_full_pipeline():
    """Filing.xbrl() の E2E パイプライン。"""
    filings = documents("2025-06-26", doc_type="120")
    # ナカバヤシを探す
    target = None
    for f in filings:
        if f.doc_id == TARGET_DOC_ID:
            target = f
            break

    if target is None:
        print("  SKIP: ナカバヤシの Filing が見つからない")
        return

    print(f"  対象: {target.filer_name} ({target.doc_id})")
    t0 = time.perf_counter()
    stmts = target.xbrl()
    elapsed = time.perf_counter() - t0
    print(f"  xbrl() 完了: {elapsed:.2f}s")

    # BS
    bs = stmts.balance_sheet()
    if bs is not None:
        print(f"  BS: {len(bs)} items")
        total_assets = bs.get("総資産")
        if total_assets is None:
            total_assets = bs.get("TotalAssets")
        if total_assets is not None:
            print(f"    総資産: {total_assets.value:,}")
    else:
        print("  BS: None")

    # PL
    pl = stmts.income_statement()
    if pl is not None:
        print(f"  PL: {len(pl)} items")
        net_sales = pl.get("売上高")
        if net_sales is None:
            net_sales = pl.get("NetSales")
        if net_sales is not None:
            print(f"    売上高: {net_sales.value:,}")
    else:
        print("  PL: None")

    # CF
    cf = stmts.cash_flow_statement()
    if cf is not None:
        print(f"  CF: {len(cf)} items")
    else:
        print("  CF: None")


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_general_corp_dei,
        test_general_corp_units,
        test_general_corp_contexts,
        test_general_corp_namespaces,
        test_general_corp_merge_pre,
        test_general_corp_calculation,
        test_general_corp_definition,
        test_general_corp_full_pipeline,
    ]

    print(f"Wave 1 E2E テスト: 一般事業会社 ({len(tests)} テスト)")
    print(f"対象: {TARGET_NAME} ({TARGET_DOC_ID})")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

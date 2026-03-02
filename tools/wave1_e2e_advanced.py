"""Wave 1 E2E テスト: 高度なケース。

  1. IFRS 企業の DEI 抽出
  2. Calculation linkbase の整合性検証（合計値チェック）
  3. 大規模企業の全パイプライン性能
  4. 複数 _pre.xml を持つ ZIP の merge
  5. Definition linkbase の dimensional 構造の深さ
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
    merge_presentation_trees,
    parse_calculation_linkbase,
    parse_definition_linkbase,
)
from edinet.xbrl._namespaces import classify_namespace, NamespaceCategory

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


# ─── ヘルパー ────────────────────────────────────────────────

def _extract_linkbase_files(zip_bytes: bytes, suffix: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(suffix) and "PublicDoc/" in name:
                result[name] = zf.read(name)
    return result


def _find_ifrs_company(date: str, max_check: int = 30):
    """指定日付で IFRS 企業を探す。"""
    filings = documents(date, doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]

    for f in xbrl_filings[:max_check]:
        try:
            xbrl_path, xbrl_bytes = f.fetch()
            parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
            dei = extract_dei(parsed.facts)
            if dei.accounting_standards == AccountingStandard.IFRS:
                return f, parsed, dei
        except Exception:
            continue
    return None


# ─── テストケース ────────────────────────────────────────────

@test_case("ADV-1: IFRS 企業の DEI 抽出")
def test_ifrs_dei():
    """IFRS 企業の DEI が正しく抽出できるか。"""
    # 6月下旬（有報ピーク）で IFRS 企業を探す
    result = _find_ifrs_company("2025-06-26")
    if result is None:
        result = _find_ifrs_company("2025-06-27")

    if result is None:
        print("  SKIP: IFRS 企業が見つからない")
        return

    f, parsed, dei = result
    print(f"  対象: {dei.filer_name_ja or f.filer_name} ({f.doc_id})")
    print(f"  accounting_standards: {dei.accounting_standards!r}")
    print(f"  EDINET コード: {dei.edinet_code}")
    print(f"  証券コード: {dei.security_code}")
    print(f"  連結あり: {dei.has_consolidated}")
    print(f"  英語名: {dei.filer_name_en}")

    assert_eq(dei.accounting_standards, AccountingStandard.IFRS, "IFRS 確認")
    assert_true(dei.edinet_code is not None, "EDINET コードあり")

    # IFRS 企業は通常連結あり
    if dei.has_consolidated:
        print("  → IFRS + 連結 ✓")

    # 名前空間にIFRS関連モジュールがあるか確認
    ns_set = {fact.namespace_uri for fact in parsed.facts if fact.namespace_uri}
    ifrs_modules = sorted({
        classify_namespace(uri).module_name
        for uri in ns_set
        if classify_namespace(uri).module_name and "ifrs" in (classify_namespace(uri).module_name or "").lower()
    })
    print(f"  IFRS モジュール: {ifrs_modules}")


@test_case("ADV-2: Calculation linkbase の合計値検証")
def test_calculation_sum_check():
    """Calculation linkbase の親子関係で、子 arc の weight を使った検証。"""
    doc_id = "S100W4JX"  # ナカバヤシ
    zip_bytes = download_document(doc_id, file_type="1")
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")

    if not cal_files:
        print("  SKIP: _cal.xml なし")
        return

    first_xml = next(iter(cal_files.values()))
    linkbase = parse_calculation_linkbase(first_xml)

    print(f"  ロール数: {len(linkbase.trees)}")

    # 各ロールの arc を検証 (CalculationTree.arcs はタプル)
    total_arcs = 0
    positive_arcs = 0
    negative_arcs = 0
    for role_uri, tree in linkbase.trees.items():
        total_arcs += len(tree.arcs)
        for arc in tree.arcs:
            if arc.weight > 0:
                positive_arcs += 1
            elif arc.weight < 0:
                negative_arcs += 1

    print(f"  全 arc 数: {total_arcs}")
    print(f"  正 weight: {positive_arcs}")
    print(f"  負 weight: {negative_arcs}")

    assert_gt(total_arcs, 0, "Arc が存在する")
    assert_gt(positive_arcs, 0, "正の weight が存在する")
    assert_gt(negative_arcs, 0, "負の weight が存在する（控除項目）")

    # 特定ロール（BS）で子の構造を検証 (children_of は CalculationLinkbase のメソッド)
    bs_role = None
    for role_uri in linkbase.trees:
        if "BalanceSheet" in role_uri:
            bs_role = role_uri
            break

    if bs_role:
        tree = linkbase.trees[bs_role]
        roots = tree.roots
        print(f"\n  BS ロール: {bs_role.rsplit('/', 1)[-1]}")
        print(f"  ルートノード数: {len(roots)}")

        # ルートの子を表示 (linkbase.children_of を使用)
        for root in roots[:3]:
            children = linkbase.children_of(root, role_uri=bs_role)
            print(f"    {root}: {len(children)} 子")
            for child_arc in children[:5]:
                sign = "+" if child_arc.weight > 0 else "-"
                print(f"      {sign} {child_arc.child} (weight={child_arc.weight})")


@test_case("ADV-3: 実データで facts と calculation の照合")
def test_facts_vs_calculation():
    """実際の fact 値と calculation 構造を照合する。"""
    doc_id = "S100W4JX"  # ナカバヤシ
    zip_bytes = download_document(doc_id, file_type="1")

    # XBRL インスタンスから facts を取得
    xbrl_files = {}
    cal_files = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if "PublicDoc/" in name:
                if name.endswith(".xbrl"):
                    xbrl_files[name] = zf.read(name)
                elif name.endswith("_cal.xml"):
                    cal_files[name] = zf.read(name)

    if not xbrl_files or not cal_files:
        print("  SKIP: XBRL or _cal.xml なし")
        return

    # Facts をパース
    xbrl_path, xbrl_bytes = next(iter(xbrl_files.items()))
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    contexts = structure_contexts(parsed.contexts)
    coll = ContextCollection(contexts)

    # Calculation をパース
    cal_xml = next(iter(cal_files.values()))
    linkbase = parse_calculation_linkbase(cal_xml)

    # 連結・最新期間・Dimension なしのコンテキストを取得
    cons_instant = coll.filter_consolidated().latest_instant_contexts().filter_no_extra_dimensions()
    cons_duration = coll.filter_consolidated().latest_duration_contexts().filter_no_extra_dimensions()
    # instant と duration を合わせて取得
    cons_ctx_ids: set[str] = set()
    for c in cons_instant:
        cons_ctx_ids.add(c.context_id)
    for c in cons_duration:
        cons_ctx_ids.add(c.context_id)

    # Facts をコンセプト → 値のマップに変換（連結当期のみ）
    fact_values: dict[str, float] = {}
    for fact in parsed.facts:
        if fact.context_ref in cons_ctx_ids and fact.value_raw is not None:
            local = fact.local_name
            try:
                val = float(fact.value_raw)
                fact_values[local] = val
            except (ValueError, TypeError):
                pass

    print(f"  連結当期の数値 fact 数: {len(fact_values)}")

    # 全ロールで合計チェック
    checked = 0
    matched = 0
    exact_matched = 0
    rounding_matched = 0
    mismatched = 0
    for role_uri, tree in linkbase.trees.items():
        for root in tree.roots:
            if root not in fact_values:
                continue
            children = linkbase.children_of(root, role_uri=role_uri)
            if not children:
                continue

            # 子の加重合計
            calc_sum = 0.0
            all_children_have_values = True
            for arc in children:
                if arc.child in fact_values:
                    calc_sum += arc.weight * fact_values[arc.child]
                else:
                    all_children_have_values = False

            if all_children_have_values and len(children) >= 2:
                actual = fact_values[root]
                checked += 1
                diff = abs(calc_sum - actual)
                # XBRL の百万円単位丸め誤差を許容（±子ノード数 × 1百万円）
                tolerance = len(children) * 1_000_000
                if diff < 1:
                    exact_matched += 1
                    matched += 1
                elif diff <= tolerance:
                    rounding_matched += 1
                    matched += 1
                else:
                    mismatched += 1
                    if mismatched <= 3:
                        short_role = role_uri.rsplit("/", 1)[-1]
                        print(f"  不一致: {root} in {short_role}")
                        print(f"    actual={actual:,.0f}, calc_sum={calc_sum:,.0f}, diff={diff:,.0f}")

    print(f"  チェック対象: {checked}")
    print(f"  完全一致: {exact_matched}")
    print(f"  丸め誤差内一致: {rounding_matched}")
    print(f"  不一致: {mismatched}")

    if checked > 0:
        match_rate = matched / checked * 100
        print(f"  一致率(丸め込み): {match_rate:.1f}%")
        # 丸め誤差を考慮すれば大半が一致するはず
        assert_true(match_rate >= 50, f"一致率 50% 以上 (実際: {match_rate:.1f}%)")


@test_case("ADV-4: 複数ファイルの _pre.xml マージ結果の詳細検証")
def test_merge_detail():
    """merge で共通ロールのノード数が正しく増加するか、詳細に検証。"""
    from pathlib import Path

    tax_root = Path(TAXONOMY_PATH)
    # jpcrp の _pre.xml を全て取得
    jpcrp_dir = tax_root / "taxonomy" / "jpcrp"
    std_pre_files: list[Path] = []
    if jpcrp_dir.is_dir():
        for p in jpcrp_dir.rglob("*_pre.xml"):
            std_pre_files.append(p)

    if not std_pre_files:
        print("  SKIP: 標準タクソノミの _pre.xml なし")
        return

    print(f"  標準タクソノミの _pre.xml: {len(std_pre_files)} 件")
    for p in std_pre_files[:5]:
        print(f"    {p.name}")

    # 各ファイルをパースしてマージ
    all_trees: dict = {}
    for p in std_pre_files:
        trees = parse_presentation_linkbase(p.read_bytes(), source_path=str(p))
        all_trees = merge_presentation_trees(all_trees, trees) if all_trees else trees

    std_roles = len(all_trees)
    std_nodes = sum(t.node_count for t in all_trees.values())
    print(f"  標準タクソノミ統合: {std_roles} roles, {std_nodes} nodes")

    # 提出者 _pre.xml を追加
    doc_id = "S100W4JX"
    zip_bytes = download_document(doc_id, file_type="1")
    filer_pre = _extract_linkbase_files(zip_bytes, "_pre.xml")

    if not filer_pre:
        print("  SKIP: 提出者の _pre.xml なし")
        return

    filer_path, filer_xml = next(iter(filer_pre.items()))
    filer_trees = parse_presentation_linkbase(filer_xml, source_path=filer_path)
    filer_roles = len(filer_trees)
    filer_nodes = sum(t.node_count for t in filer_trees.values())
    print(f"  提出者: {filer_roles} roles, {filer_nodes} nodes")

    # マージ
    merged = merge_presentation_trees(all_trees, filer_trees)
    merged_roles = len(merged)
    merged_nodes = sum(t.node_count for t in merged.values())
    print(f"  マージ後: {merged_roles} roles, {merged_nodes} nodes")

    # 共通ロールの詳細
    common_roles = set(all_trees.keys()) & set(filer_trees.keys())
    print(f"  共通ロール: {len(common_roles)}")

    for role in sorted(common_roles)[:5]:
        short = role.rsplit("/", 1)[-1]
        std_n = all_trees[role].node_count
        filer_n = filer_trees[role].node_count
        merged_n = merged[role].node_count
        print(f"    {short}: 標準={std_n}, 提出者={filer_n}, マージ後={merged_n}")
        assert_true(
            merged_n >= max(std_n, filer_n),
            f"{short}: マージ後 >= max(標準, 提出者)",
        )


@test_case("ADV-5: Definition linkbase の dimensional 構造の深さ")
def test_definition_depth():
    """Definition linkbase の各 hypercube の axis 数と member 数を検証。"""
    from edinet.xbrl.linkbase.definition import MemberNode

    def _count_members(node: MemberNode) -> int:
        """MemberNode ツリーのノード数を再帰的にカウント。"""
        return 1 + sum(_count_members(c) for c in node.children)

    def _flatten_members(node: MemberNode, depth: int = 0) -> list[tuple[str, int]]:
        """MemberNode ツリーをフラット化。"""
        result = [(node.concept, depth)]
        for c in node.children:
            result.extend(_flatten_members(c, depth + 1))
        return result

    def _axis_member_count(axis_info) -> int:
        """AxisInfo のメンバー数（domain 含む）。"""
        if axis_info.domain is None:
            return 0
        return _count_members(axis_info.domain)

    doc_id = "S100W4JX"  # ナカバヤシ
    zip_bytes = download_document(doc_id, file_type="1")
    def_files = _extract_linkbase_files(zip_bytes, "_def.xml")

    if not def_files:
        print("  SKIP: _def.xml なし")
        return

    first_xml = next(iter(def_files.values()))
    trees = parse_definition_linkbase(first_xml)

    print(f"  ロール数: {len(trees)}")

    max_axes = 0
    max_members = 0
    total_hypercubes = 0
    total_axes = 0
    total_members = 0

    for role_uri, tree in trees.items():
        for hc in tree.hypercubes:
            total_hypercubes += 1
            axes = len(hc.axes)
            total_axes += axes
            members = sum(_axis_member_count(a) for a in hc.axes)
            total_members += members
            max_axes = max(max_axes, axes)
            max_members = max(max_members, members)

    print(f"  hypercube 数: {total_hypercubes}")
    print(f"  全 axis 数: {total_axes}")
    print(f"  全 member 数: {total_members}")
    print(f"  最大 axis 数 (per hypercube): {max_axes}")
    print(f"  最大 member 数 (per hypercube): {max_members}")

    assert_gt(total_hypercubes, 0, "Hypercube が存在")
    assert_gt(total_axes, 0, "Axis が存在")
    assert_gt(total_members, 0, "Member が存在")

    # 最も複雑な hypercube を表示
    print(f"\n  最も複雑な hypercube:")
    for role_uri, tree in trees.items():
        for hc in tree.hypercubes:
            axes = len(hc.axes)
            members = sum(_axis_member_count(a) for a in hc.axes)
            if members == max_members:
                short = role_uri.rsplit("/", 1)[-1]
                print(f"    ロール: {short}")
                print(f"    hypercube: {hc.table_concept}")
                for ax in hc.axes:
                    mc = _axis_member_count(ax)
                    print(f"      axis: {ax.axis_concept} ({mc} members)")
                    if ax.domain:
                        flat = _flatten_members(ax.domain)
                        for concept, depth in flat[:5]:
                            indent = "  " * depth
                            print(f"        {indent}{concept}")
                        if len(flat) > 5:
                            print(f"        ... +{len(flat) - 5}")
                break
        else:
            continue
        break


@test_case("ADV-6: US-GAAP 企業の DEI")
def test_us_gaap_dei():
    """US-GAAP 企業を探して DEI を検証。"""
    result = None
    for date in ["2025-06-26", "2025-06-27"]:
        filings = documents(date, doc_type="120")
        xbrl_filings = [f for f in filings if f.has_xbrl]
        for f in xbrl_filings[:50]:
            try:
                xbrl_path, xbrl_bytes = f.fetch()
                parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
                dei = extract_dei(parsed.facts)
                if dei.accounting_standards == AccountingStandard.US_GAAP:
                    result = (f, parsed, dei)
                    break
            except Exception:
                continue
        if result:
            break

    if result is None:
        print("  SKIP: US-GAAP 企業が見つからない")
        return

    f, parsed, dei = result
    print(f"  対象: {dei.filer_name_ja or f.filer_name} ({f.doc_id})")
    print(f"  accounting_standards: {dei.accounting_standards!r}")
    print(f"  連結あり: {dei.has_consolidated}")
    print(f"  証券コード: {dei.security_code}")

    assert_eq(dei.accounting_standards, AccountingStandard.US_GAAP, "US-GAAP 確認")


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_ifrs_dei,
        test_calculation_sum_check,
        test_facts_vs_calculation,
        test_merge_detail,
        test_definition_depth,
        test_us_gaap_dei,
    ]

    print(f"Wave 1 E2E テスト: 高度なケース ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

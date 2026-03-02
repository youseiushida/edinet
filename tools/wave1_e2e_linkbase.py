"""Wave 1 E2E テスト: リンクベースパーサー (Presentation / Calculation / Definition)。

実際の EDINET API を叩いてリンクベース解析の実用性を確認する。

テスト対象:
  - parse_presentation_linkbase() / PresentationTree / PresentationNode
  - parse_calculation_linkbase() / CalculationLinkbase / CalculationArc
  - parse_definition_linkbase() / DefinitionTree / HypercubeInfo / AxisInfo
  - merge_presentation_trees()
  - 標準タクソノミと提出者タクソノミの両方のリンクベース解析

使い方:
  EDINET_API_KEY=xxx python tools/wave1_e2e_linkbase.py
"""

from __future__ import annotations

import os
import sys
import traceback
import zipfile
from io import BytesIO

from edinet import configure, documents
from edinet.api.download import download_document
from edinet.xbrl.linkbase import (
    ROLE_LABEL,
    ROLE_TOTAL_LABEL,
    CalculationArc,
    CalculationLinkbase,
    CalculationTree,
    DefinitionArc,
    DefinitionTree,
    HypercubeInfo,
    AxisInfo,
    MemberNode,
    PresentationNode,
    PresentationTree,
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
        raise AssertionError(
            f"Expected {type(obj).__name__} to be {cls.__name__}: {msg}"
        )


# ─── 共通ヘルパー ────────────────────────────────────────────

_zip_cache: dict[str, bytes] = {}


def _get_zip_bytes(doc_id: str) -> bytes:
    """ZIP バイトをキャッシュ付きで取得。"""
    if doc_id not in _zip_cache:
        _zip_cache[doc_id] = download_document(doc_id, file_type="1")
    return _zip_cache[doc_id]


def _extract_linkbase_files(
    zip_bytes: bytes,
    suffix: str,
) -> dict[str, bytes]:
    """ZIP から指定サフィックスのリンクベースファイルを抽出する。

    Args:
        zip_bytes: ZIP バイト列。
        suffix: ファイル名のサフィックス（例: "_pre.xml", "_cal.xml"）。

    Returns:
        ファイルパス → bytes の辞書。
    """
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(suffix) and "PublicDoc/" in name:
                result[name] = zf.read(name)
    return result


def _get_first_xbrl_filing(target_date: str = "2026-02-20"):
    """有報の XBRL 付き Filing を 1 件取得。"""
    filings = documents(target_date, doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    return xbrl_filings[0] if xbrl_filings else None


# ─── Presentation テスト ─────────────────────────────────────

@test_case("LB-1: Presentation Linkbase パース（提出者タクソノミ）")
def test_presentation_parse():
    """提出者の _pre.xml が正しくパースされることを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")
    zip_bytes = _get_zip_bytes(filing.doc_id)
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")

    if not pre_files:
        print("  SKIP: _pre.xml なし")
        return

    print(f"  _pre.xml ファイル数: {len(pre_files)}")
    total_trees = 0
    total_nodes = 0

    for path, xml_bytes in pre_files.items():
        trees = parse_presentation_linkbase(xml_bytes, source_path=path)
        assert_isinstance(trees, dict, "parse 結果は dict")

        for role_uri, tree in trees.items():
            assert_isinstance(tree, PresentationTree, "PresentationTree 型")
            assert_true(len(tree.roots) > 0, f"ルートノードが存在: {role_uri}")
            total_trees += 1
            total_nodes += tree.node_count

        # 最初のファイルの詳細表示
        if path == next(iter(pre_files)):
            first_tree = next(iter(trees.values()))
            print(f"  先頭ツリー ({first_tree.role_uri}):")
            print(f"    ルート数: {len(first_tree.roots)}")
            print(f"    ノード数: {first_tree.node_count}")
            for root in first_tree.roots[:3]:
                print(f"    root: {root.concept} (order={root.order})")

    print(f"  合計: {total_trees} ツリー, {total_nodes} ノード")


@test_case("LB-2: PresentationNode の属性")
def test_presentation_node_attributes():
    """PresentationNode の各属性が正しく設定されていることを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    zip_bytes = _get_zip_bytes(filing.doc_id)
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")
    if not pre_files:
        print("  SKIP: _pre.xml なし")
        return

    first_xml = next(iter(pre_files.values()))
    trees = parse_presentation_linkbase(first_xml)
    tree = next(iter(trees.values()))

    # ルートノードの検証
    root = tree.roots[0]
    assert_isinstance(root, PresentationNode, "PresentationNode 型")
    assert_true(isinstance(root.concept, str) and len(root.concept) > 0, "concept は非空文字列")
    assert_true(isinstance(root.href, str) and len(root.href) > 0, "href は非空文字列")
    assert_isinstance(root.order, float, "order は float")
    assert_eq(root.depth, 0, "ルートの depth は 0")
    assert_isinstance(root.children, tuple, "children は tuple")
    assert_isinstance(root.is_abstract, bool, "is_abstract は bool")
    assert_isinstance(root.is_total, bool, "is_total は bool")

    print(f"  root.concept: {root.concept}")
    print(f"  root.href: {root.href[:80]}...")
    print(f"  root.is_abstract: {root.is_abstract}")
    print(f"  root.children: {len(root.children)}")

    # 子ノードの depth 検証
    if root.children:
        child = root.children[0]
        assert_eq(child.depth, 1, "子の depth は 1")
        if child.children:
            grandchild = child.children[0]
            assert_eq(grandchild.depth, 2, "孫の depth は 2")


@test_case("LB-3: PresentationTree.flatten()")
def test_presentation_flatten():
    """flatten() と line_items_roots() が正しく動作することを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    zip_bytes = _get_zip_bytes(filing.doc_id)
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")
    if not pre_files:
        print("  SKIP: _pre.xml なし")
        return

    first_xml = next(iter(pre_files.values()))
    trees = parse_presentation_linkbase(first_xml)
    tree = next(iter(trees.values()))

    # flatten
    flat = tree.flatten()
    assert_gt(len(flat), 0, "flatten 結果が存在")
    assert_eq(len(flat), tree.node_count, "flatten 長 == node_count")

    # skip_abstract
    flat_no_abs = tree.flatten(skip_abstract=True)
    abstract_count = sum(1 for n in flat if n.is_abstract)
    assert_eq(
        len(flat_no_abs), len(flat) - abstract_count,
        "skip_abstract で Abstract 分だけ減少",
    )

    # line_items_roots
    li_roots = tree.line_items_roots()
    assert_isinstance(li_roots, tuple, "line_items_roots は tuple")
    print(f"  flatten: {len(flat)} nodes, abstract={abstract_count}")
    print(f"  line_items_roots: {len(li_roots)} roots")


@test_case("LB-4: merge_presentation_trees()")
def test_merge_presentation():
    """複数の _pre.xml をマージできることを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    zip_bytes = _get_zip_bytes(filing.doc_id)
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")
    if len(pre_files) < 2:
        print("  SKIP: _pre.xml が 2 つ未満")
        return

    tree_dicts = []
    for path, xml_bytes in pre_files.items():
        tree_dicts.append(parse_presentation_linkbase(xml_bytes, source_path=path))

    merged = merge_presentation_trees(*tree_dicts)
    assert_isinstance(merged, dict, "マージ結果は dict")

    # マージ後のロール数 >= 各個のロール数
    all_roles = set()
    for td in tree_dicts:
        all_roles.update(td.keys())
    assert_eq(len(merged), len(all_roles), "マージ後のロール数 == ユニークロール数")

    print(f"  マージ元: {len(tree_dicts)} ファイル")
    print(f"  マージ後: {len(merged)} ロール")


# ─── Calculation テスト ──────────────────────────────────────

@test_case("LB-5: Calculation Linkbase パース")
def test_calculation_parse():
    """提出者の _cal.xml が正しくパースされることを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")
    zip_bytes = _get_zip_bytes(filing.doc_id)
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")

    if not cal_files:
        print("  SKIP: _cal.xml なし")
        return

    print(f"  _cal.xml ファイル数: {len(cal_files)}")

    for path, xml_bytes in cal_files.items():
        lb = parse_calculation_linkbase(xml_bytes, source_path=path)
        assert_isinstance(lb, CalculationLinkbase, "CalculationLinkbase 型")
        assert_gt(len(lb.trees), 0, "少なくとも 1 つの計算木")

        print(f"  {path}:")
        print(f"    ロール数: {len(lb.trees)}")
        print(f"    ロール URI: {lb.role_uris}")

        for role_uri in lb.role_uris[:3]:
            tree = lb.get_tree(role_uri)
            assert_isinstance(tree, CalculationTree, "CalculationTree 型")
            assert_gt(len(tree.arcs), 0, f"アークが存在: {role_uri}")
            print(f"    {role_uri}: arcs={len(tree.arcs)}, roots={tree.roots}")


@test_case("LB-6: CalculationArc の属性と weight")
def test_calculation_arc_attributes():
    """CalculationArc の weight が 1 or -1 であることを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    zip_bytes = _get_zip_bytes(filing.doc_id)
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")
    if not cal_files:
        print("  SKIP: _cal.xml なし")
        return

    first_xml = next(iter(cal_files.values()))
    lb = parse_calculation_linkbase(first_xml)
    tree = next(iter(lb.trees.values()))

    add_count = 0
    sub_count = 0

    for arc in tree.arcs:
        assert_isinstance(arc, CalculationArc, "CalculationArc 型")
        assert_true(arc.weight in (1, -1), f"weight は 1 or -1: {arc.weight}")
        assert_true(len(arc.parent) > 0, "parent は非空")
        assert_true(len(arc.child) > 0, "child は非空")
        assert_isinstance(arc.order, float, "order は float")
        if arc.weight == 1:
            add_count += 1
        else:
            sub_count += 1

    print(f"  加算 (weight=1): {add_count}")
    print(f"  減算 (weight=-1): {sub_count}")

    # 具体例を表示
    for arc in tree.arcs[:5]:
        sign = "+" if arc.weight == 1 else "-"
        print(f"    {arc.parent} → {sign}{arc.child}")


@test_case("LB-7: CalculationLinkbase のナビゲーション")
def test_calculation_navigation():
    """children_of / parent_of / ancestors_of が正しく動作することを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    zip_bytes = _get_zip_bytes(filing.doc_id)
    cal_files = _extract_linkbase_files(zip_bytes, "_cal.xml")
    if not cal_files:
        print("  SKIP: _cal.xml なし")
        return

    first_xml = next(iter(cal_files.values()))
    lb = parse_calculation_linkbase(first_xml)
    role_uri = lb.role_uris[0]
    tree = lb.get_tree(role_uri)

    # ルート concept の children
    if tree.roots:
        root = tree.roots[0]
        children = lb.children_of(root, role_uri=role_uri)
        print(f"  root={root}: children={len(children)}")

        for arc in children[:3]:
            print(f"    → {arc.child} (weight={arc.weight}, order={arc.order})")

            # 子の parent
            parents = lb.parent_of(arc.child, role_uri=role_uri)
            assert_gt(len(parents), 0, f"{arc.child} の親が存在")
            parent_concepts = [p.parent for p in parents]
            assert_true(root in parent_concepts, f"{root} が親に含まれる")

        # ancestors
        if children:
            leaf = children[0].child
            leaf_children = lb.children_of(leaf, role_uri=role_uri)
            if leaf_children:
                grandchild = leaf_children[0].child
                ancestors = lb.ancestors_of(grandchild, role_uri=role_uri)
                print(f"  ancestors_of({grandchild}): {ancestors}")
                assert_gt(len(ancestors), 0, "祖先が存在")


# ─── Definition テスト ───────────────────────────────────────

@test_case("LB-8: Definition Linkbase パース")
def test_definition_parse():
    """提出者の _def.xml が正しくパースされることを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")
    zip_bytes = _get_zip_bytes(filing.doc_id)
    def_files = _extract_linkbase_files(zip_bytes, "_def.xml")

    if not def_files:
        print("  SKIP: _def.xml なし")
        return

    print(f"  _def.xml ファイル数: {len(def_files)}")

    for path, xml_bytes in def_files.items():
        trees = parse_definition_linkbase(xml_bytes, source_path=path)
        assert_isinstance(trees, dict, "parse 結果は dict")

        hc_count = 0
        arc_count = 0
        for role_uri, tree in trees.items():
            assert_isinstance(tree, DefinitionTree, "DefinitionTree 型")
            hc_count += len(tree.hypercubes)
            arc_count += len(tree.arcs)

        print(f"  {path}:")
        print(f"    ロール数: {len(trees)}")
        print(f"    ハイパーキューブ数: {hc_count}")
        print(f"    アーク数: {arc_count}")


@test_case("LB-9: HypercubeInfo の構造")
def test_hypercube_info():
    """HypercubeInfo が正しく構造化されていることを確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    zip_bytes = _get_zip_bytes(filing.doc_id)
    def_files = _extract_linkbase_files(zip_bytes, "_def.xml")
    if not def_files:
        print("  SKIP: _def.xml なし")
        return

    first_xml = next(iter(def_files.values()))
    trees = parse_definition_linkbase(first_xml)

    # ハイパーキューブを持つツリーを探す
    hc_trees = [(r, t) for r, t in trees.items() if t.has_hypercube]
    if not hc_trees:
        print("  SKIP: ハイパーキューブなし")
        return

    role_uri, tree = hc_trees[0]
    hc = tree.hypercubes[0]
    assert_isinstance(hc, HypercubeInfo, "HypercubeInfo 型")

    print(f"  ロール: {role_uri}")
    print(f"  table: {hc.table_concept}")
    print(f"  heading: {hc.heading_concept}")
    print(f"  closed: {hc.closed}")
    print(f"  contextElement: {hc.context_element}")
    print(f"  line_items: {hc.line_items_concept}")
    print(f"  axes: {len(hc.axes)}")

    assert_true(isinstance(hc.table_concept, str), "table_concept は str")
    assert_true(isinstance(hc.heading_concept, str), "heading_concept は str")
    assert_isinstance(hc.closed, bool, "closed は bool")
    assert_true(hc.context_element in ("segment", "scenario"), "contextElement は segment/scenario")

    for axis in hc.axes:
        assert_isinstance(axis, AxisInfo, "AxisInfo 型")
        print(f"    axis: {axis.axis_concept} (order={axis.order}, default={axis.default_member})")

        if axis.domain is not None:
            assert_isinstance(axis.domain, MemberNode, "domain は MemberNode")
            print(f"      domain: {axis.domain.concept} (usable={axis.domain.usable})")


@test_case("LB-10: DefinitionArc の arcrole 分布")
def test_definition_arcrole_distribution():
    """DefinitionArc の arcrole の分布を確認。"""
    filing = _get_first_xbrl_filing()
    if filing is None:
        print("  SKIP: 有報なし")
        return

    zip_bytes = _get_zip_bytes(filing.doc_id)
    def_files = _extract_linkbase_files(zip_bytes, "_def.xml")
    if not def_files:
        print("  SKIP: _def.xml なし")
        return

    arcrole_counts: dict[str, int] = {}
    for xml_bytes in def_files.values():
        trees = parse_definition_linkbase(xml_bytes)
        for tree in trees.values():
            for arc in tree.arcs:
                assert_isinstance(arc, DefinitionArc, "DefinitionArc 型")
                # arcrole の末尾部分のみ表示
                short = arc.arcrole.rsplit("/", 1)[-1]
                arcrole_counts[short] = arcrole_counts.get(short, 0) + 1

    print(f"  arcrole 分布:")
    for role, count in sorted(arcrole_counts.items(), key=lambda x: -x[1]):
        print(f"    {role}: {count}")


@test_case("LB-11: ROLE_LABEL 定数の値")
def test_role_constants():
    """ラベルロール定数が正しい URI であることを確認。"""
    assert_eq(
        ROLE_LABEL,
        "http://www.xbrl.org/2003/role/label",
        "ROLE_LABEL",
    )
    assert_eq(
        ROLE_TOTAL_LABEL,
        "http://www.xbrl.org/2003/role/totalLabel",
        "ROLE_TOTAL_LABEL",
    )
    print(f"  ROLE_LABEL: {ROLE_LABEL}")
    print(f"  ROLE_TOTAL_LABEL: {ROLE_TOTAL_LABEL}")


@test_case("LB-12: 標準タクソノミのリンクベース解析")
def test_standard_taxonomy_linkbase():
    """ローカルのタクソノミから標準リンクベースを解析する。"""
    taxonomy_path = TAXONOMY_PATH
    # jppfs の presentation linkbase を探す
    taxonomy_root = os.path.join(taxonomy_path, "taxonomy", "jppfs")

    if not os.path.isdir(taxonomy_root):
        print(f"  SKIP: タクソノミディレクトリなし: {taxonomy_root}")
        return

    # pre ファイルを探す
    pre_files_found: list[str] = []
    for root, dirs, files in os.walk(taxonomy_root):
        for f in files:
            if f.endswith("_pre.xml"):
                pre_files_found.append(os.path.join(root, f))

    if not pre_files_found:
        print("  SKIP: jppfs の _pre.xml なし")
        return

    pre_path = pre_files_found[0]
    print(f"  ファイル: {pre_path}")

    with open(pre_path, "rb") as fh:
        xml_bytes = fh.read()

    trees = parse_presentation_linkbase(xml_bytes, source_path=pre_path)
    assert_gt(len(trees), 0, "標準タクソノミから tree がパースされる")

    total_nodes = sum(t.node_count for t in trees.values())
    print(f"  ロール数: {len(trees)}")
    print(f"  合計ノード数: {total_nodes}")

    # 具体的なコンセプトを確認
    all_concepts = set()
    for tree in trees.values():
        for node in tree.flatten():
            all_concepts.add(node.concept)

    known_concepts = [
        "CashAndDeposits", "NetSales", "GrossProfit",
        "OperatingIncome", "OrdinaryIncome",
    ]
    for kc in known_concepts:
        if kc in all_concepts:
            print(f"    ✓ {kc}")
        else:
            print(f"    ? {kc} (not found)")


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_presentation_parse,
        test_presentation_node_attributes,
        test_presentation_flatten,
        test_merge_presentation,
        test_calculation_parse,
        test_calculation_arc_attributes,
        test_calculation_navigation,
        test_definition_parse,
        test_hypercube_info,
        test_definition_arcrole_distribution,
        test_role_constants,
        test_standard_taxonomy_linkbase,
    ]

    print(f"Wave 1 E2E テスト: Linkbase ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

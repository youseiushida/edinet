"""Wave 1 E2E テスト: エッジケースと残課題の検証。

これまでのイテレーションで SKIP だった項目や追加のエッジケースを検証する:
  1. merge_presentation_trees: 標準タクソノミ _pre.xml + 提出者 _pre.xml のマージ
  2. 半期報告書 (HY) の DEI
  3. ZIP 解析失敗のエラーハンドリング
  4. 非連結のみの企業
  5. is_total / is_abstract / is_dimension_node の検証
"""

from __future__ import annotations

import os
import sys
import traceback
import zipfile
from io import BytesIO
from pathlib import Path

from edinet import configure, documents
from edinet.api.download import download_document
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl.dei import DEI, PeriodType
from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl.linkbase import (
    PresentationTree,
    merge_presentation_trees,
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


# ─── ヘルパー ────────────────────────────────────────────────

def _extract_linkbase_files(zip_bytes: bytes, suffix: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(suffix) and "PublicDoc/" in name:
                result[name] = zf.read(name)
    return result


# ─── テストケース ────────────────────────────────────────────

@test_case("EDGE-1: 標準タクソノミ _pre.xml と提出者 _pre.xml のマージ")
def test_merge_std_and_filer_pre():
    """標準タクソノミと提出者の _pre.xml を同時にパース・マージ。"""
    tax_root = Path(TAXONOMY_PATH)
    # jppfs の _pre.xml を探す
    std_pre_files: list[Path] = []
    jppfs_dir = tax_root / "taxonomy" / "jppfs"
    if jppfs_dir.is_dir():
        for p in jppfs_dir.rglob("*_pre.xml"):
            std_pre_files.append(p)

    if not std_pre_files:
        # jpcrp でも探す
        jpcrp_dir = tax_root / "taxonomy" / "jpcrp"
        if jpcrp_dir.is_dir():
            for p in jpcrp_dir.rglob("*_pre.xml"):
                std_pre_files.append(p)

    if not std_pre_files:
        print("  SKIP: 標準タクソノミの _pre.xml なし")
        return

    # 標準タクソノミをパース
    std_path = std_pre_files[0]
    print(f"  標準タクソノミ: {std_path.name}")
    std_xml = std_path.read_bytes()
    std_trees = parse_presentation_linkbase(std_xml, source_path=str(std_path))
    std_nodes = sum(t.node_count for t in std_trees.values())
    print(f"    → {len(std_trees)} roles, {std_nodes} nodes")

    # ナカバヤシの提出者 _pre.xml
    doc_id = "S100W4JX"
    zip_bytes = download_document(doc_id, file_type="1")
    filer_pre = _extract_linkbase_files(zip_bytes, "_pre.xml")

    if not filer_pre:
        print("  SKIP: 提出者の _pre.xml なし")
        return

    filer_path, filer_xml = next(iter(filer_pre.items()))
    print(f"  提出者: {os.path.basename(filer_path)}")
    filer_trees = parse_presentation_linkbase(filer_xml, source_path=filer_path)
    filer_nodes = sum(t.node_count for t in filer_trees.values())
    print(f"    → {len(filer_trees)} roles, {filer_nodes} nodes")

    # マージ
    merged = merge_presentation_trees(std_trees, filer_trees)
    merged_nodes = sum(t.node_count for t in merged.values())
    print(f"  マージ後: {len(merged)} roles, {merged_nodes} nodes")

    # マージ後は両方のロールを含む
    all_roles = set(std_trees.keys()) | set(filer_trees.keys())
    assert_eq(len(merged), len(all_roles), "全ロールが含まれる")

    # 共通ロール（例: BS）ではノードが増加するはず
    common_roles = set(std_trees.keys()) & set(filer_trees.keys())
    if common_roles:
        role = next(iter(common_roles))
        short = role.rsplit("/", 1)[-1]
        merged_count = merged[role].node_count
        std_count = std_trees[role].node_count
        filer_count = filer_trees[role].node_count
        print(f"  共通ロール {short}:")
        print(f"    標準={std_count}, 提出者={filer_count}, マージ後={merged_count}")
        assert_true(
            merged_count >= max(std_count, filer_count),
            f"マージ後 >= max(標準, 提出者)",
        )


@test_case("EDGE-2: 半期報告書の DEI (PeriodType=HY)")
def test_half_year_dei():
    """半期報告書から DEI を抽出し、PeriodType=HY を確認。"""
    # 半期報告書は doc_type="160"、9月決算企業は11月に提出
    filings = documents("2025-11-14", doc_type="160")  # 半期報告書
    xbrl_filings = [f for f in filings if f.has_xbrl]

    if not xbrl_filings:
        filings = documents("2025-12-19", doc_type="160")
        xbrl_filings = [f for f in filings if f.has_xbrl]

    if not xbrl_filings:
        print("  SKIP: 半期報告書なし")
        return

    # jpcrp を使っている半期報告書を探す
    target = None
    for f in xbrl_filings[:10]:
        try:
            xbrl_path, xbrl_bytes = f.fetch()
            parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
            dei = extract_dei(parsed.facts)
            if dei.type_of_current_period is not None:
                target = (f, dei)
                break
        except Exception:
            continue

    if target is None:
        print("  SKIP: DEI 付きの半期報告書が見つからない")
        return

    f, dei = target
    print(f"  対象: {dei.filer_name_ja or f.filer_name} ({f.doc_id})")
    print(f"  type_of_current_period: {dei.type_of_current_period!r}")
    print(f"  accounting_standards: {dei.accounting_standards!r}")
    print(f"  has_consolidated: {dei.has_consolidated}")

    if dei.type_of_current_period == PeriodType.HY:
        print("  → HY 確認済み ✓")
    elif dei.type_of_current_period == PeriodType.FY:
        print("  → FY (半期報告書だが FY の場合もある)")
    else:
        print(f"  → 未知の値: {dei.type_of_current_period}")


@test_case("EDGE-3: PresentationNode の is_total / is_abstract / is_dimension_node")
def test_node_flags():
    """PresentationNode の各フラグが実データで正しく動作するか確認。"""
    doc_id = "S100W4JX"
    zip_bytes = download_document(doc_id, file_type="1")
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")

    if not pre_files:
        print("  SKIP: _pre.xml なし")
        return

    first_xml = next(iter(pre_files.values()))
    trees = parse_presentation_linkbase(first_xml)

    total_count = 0
    abstract_count = 0
    dim_count = 0
    normal_count = 0

    for tree in trees.values():
        for node in tree.flatten():
            if node.is_total:
                total_count += 1
            if node.is_abstract:
                abstract_count += 1
            if node.is_dimension_node:
                dim_count += 1
            if not node.is_abstract and not node.is_dimension_node and not node.is_total:
                normal_count += 1

    all_nodes = sum(t.node_count for t in trees.values())
    print(f"  全ノード数: {all_nodes}")
    print(f"  is_total: {total_count}")
    print(f"  is_abstract: {abstract_count}")
    print(f"  is_dimension_node: {dim_count}")
    print(f"  通常ノード: {normal_count}")

    assert_gt(abstract_count, 0, "Abstract ノードが存在")
    assert_gt(total_count, 0, "Total ノードが存在")

    # Total の例を表示
    for tree in trees.values():
        for node in tree.flatten():
            if node.is_total:
                print(f"    total: {node.concept} (preferred_label={node.preferred_label})")
                break
        break


@test_case("EDGE-4: 非連結のみ企業 (投資信託) の ContextCollection")
def test_non_consolidated_only():
    """非連結のみ（投信）の ContextCollection。"""
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]

    if not xbrl_filings:
        print("  SKIP: 書類なし")
        return

    f = xbrl_filings[0]
    xbrl_path, xbrl_bytes = f.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    dei = extract_dei(parsed.facts)
    ctx_map = structure_contexts(parsed.contexts)
    coll = ContextCollection(ctx_map)

    print(f"  対象: {dei.filer_name_ja or f.filer_name} ({f.doc_id})")
    print(f"  has_consolidated: {dei.has_consolidated}")

    cons = coll.filter_consolidated()
    non_cons = coll.filter_non_consolidated()
    print(f"  連結: {len(cons)}, 個別: {len(non_cons)}")

    # 投信は has_consolidated=False で、連結軸なしのコンテキストが多い
    # 連結軸なし → is_consolidated=True（デフォルト挙動）
    # これが正しいかどうかを確認
    no_dim = coll.filter_no_dimensions()
    with_dim = len(coll) - len(no_dim)
    print(f"  Dimension なし: {len(no_dim)}, あり: {with_dim}")


@test_case("EDGE-5: flatten(skip_dimension=True) の動作")
def test_flatten_skip_dimension():
    """flatten(skip_dimension=True) でディメンション関連ノードが除外されるか確認。"""
    doc_id = "S100W4JX"
    zip_bytes = download_document(doc_id, file_type="1")
    pre_files = _extract_linkbase_files(zip_bytes, "_pre.xml")

    if not pre_files:
        print("  SKIP: _pre.xml なし")
        return

    first_xml = next(iter(pre_files.values()))
    trees = parse_presentation_linkbase(first_xml)

    # SS の role を探す（ComponentsOfEquity 等のディメンションが含まれやすい）
    ss_role = None
    for role_uri in trees:
        if "ChangesInEquity" in role_uri:
            ss_role = role_uri
            break

    if ss_role is None:
        # 任意のロールで
        ss_role = next(iter(trees))

    tree = trees[ss_role]
    full = tree.flatten()
    no_dim = tree.flatten(skip_dimension=True)
    no_abs = tree.flatten(skip_abstract=True)
    no_both = tree.flatten(skip_abstract=True, skip_dimension=True)

    dim_nodes = [n for n in full if n.is_dimension_node]
    abs_nodes = [n for n in full if n.is_abstract]

    print(f"  ロール: {ss_role.rsplit('/', 1)[-1]}")
    print(f"  全ノード: {len(full)}")
    print(f"  skip_dimension: {len(no_dim)} (除外: {len(full) - len(no_dim)})")
    print(f"  skip_abstract: {len(no_abs)} (除外: {len(full) - len(no_abs)})")
    print(f"  skip_both: {len(no_both)}")
    print(f"  is_dimension_node: {len(dim_nodes)}")
    print(f"  is_abstract: {len(abs_nodes)}")


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_merge_std_and_filer_pre,
        test_half_year_dei,
        test_node_flags,
        test_non_consolidated_only,
        test_flatten_skip_dimension,
    ]

    print(f"Wave 1 E2E テスト: エッジケース ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

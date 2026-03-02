"""Wave 2 E2E テスト #3: ConceptSet (Presentation Linkbase 自動導出)。

ローカルタクソノミ (ALL_20251101) から ConceptSetRegistry を構築し、
実際の企業のFact と照合して分類精度を検証する。

検証項目:
  1. derive_concept_sets がエラーなく動く
  2. classify_role_uri で主要 role URI が正しく分類される
  3. 一般事業会社 (cns) の BS/PL/CF/SS ConceptSet が存在
  4. 実企業の jppfs_cor fact がどの ConceptSet に分類されるか
  5. ConceptSet の legacy format 変換
"""

from __future__ import annotations

import os
import sys
import time
import traceback
import zipfile
from io import BytesIO

from edinet import configure
from edinet.api.download import download_document
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.models.financial import StatementType
from edinet.xbrl.taxonomy.concept_sets import (
    ConceptSet,
    ConceptSetRegistry,
    StatementCategory,
    classify_role_uri,
    derive_concept_sets,
    get_concept_set,
)

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)

# ─── ユーティリティ ──────────────────────────────────────────
passed = 0
failed = 0
errors: list[str] = []


def test_case(name: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            global passed, failed
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print(f"{'='*60}")
            try:
                func(*args, **kwargs)
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


# ─── テストケース ────────────────────────────────────────────

@test_case("CS-1: classify_role_uri 基本テスト")
def test_classify_role_uri():
    """主要 role URI の分類が正しいかを確認。"""
    cases = [
        # (role_uri, expected_category, expected_consolidated)
        # 注: "Consolidated" を含まない role URI は個別(False)
        (
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet",
            StatementCategory.BALANCE_SHEET,
            False,
        ),
        (
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet",
            StatementCategory.BALANCE_SHEET,
            True,
        ),
        (
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome",
            StatementCategory.INCOME_STATEMENT,
            False,
        ),
        (
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome",
            StatementCategory.INCOME_STATEMENT,
            True,
        ),
        (
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfCashFlows",
            StatementCategory.CASH_FLOW_STATEMENT,
            False,
        ),
        (
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfCashFlows",
            StatementCategory.CASH_FLOW_STATEMENT,
            True,
        ),
    ]
    for uri, expected_cat, expected_cons in cases:
        result = classify_role_uri(uri)
        if result is None:
            print(f"  {uri} -> None (unexpected)")
            assert_true(False, f"classify_role_uri returned None for {uri}")
        else:
            cat, cons = result
            print(f"  {uri.split('/')[-1]} -> {cat.name}, consolidated={cons}")
            assert_eq(cat, expected_cat, f"category mismatch for {uri}")
            assert_eq(cons, expected_cons, f"consolidated mismatch for {uri}")


@test_case("CS-2: derive_concept_sets 基本動作")
def test_derive_concept_sets():
    """ローカルタクソノミから ConceptSetRegistry を構築。"""
    t0 = time.time()
    registry = derive_concept_sets(TAXONOMY_PATH, use_cache=False)
    t1 = time.time()
    print(f"  elapsed: {t1-t0:.1f}s (no cache)")

    industries = registry.industries()
    print(f"  industries: {len(industries)}")
    print(f"  industry codes: {sorted(industries)[:10]}...")

    # キャッシュ付きで再度
    t2 = time.time()
    registry2 = derive_concept_sets(TAXONOMY_PATH, use_cache=True)
    t3 = time.time()
    print(f"  elapsed (cached): {t3-t2:.3f}s")

    assert_true(len(industries) > 0, "should have at least 1 industry")


@test_case("CS-3: 一般事業会社 (cns) の主要 ConceptSet 存在確認")
def test_cns_concept_sets():
    """一般事業会社の BS/PL/CF/SS が存在し、概念を含むことを確認。"""
    from edinet.xbrl.dei import AccountingStandard as AS
    registry = derive_concept_sets(TAXONOMY_PATH)

    categories_to_check = [
        StatementCategory.BALANCE_SHEET,
        StatementCategory.INCOME_STATEMENT,
        StatementCategory.CASH_FLOW_STATEMENT,
        StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY,
    ]

    for cat in categories_to_check:
        st = cat.to_statement_type()
        if st is None:
            print(f"  {cat.name}: to_statement_type() returned None (skip)")
            continue
        cs = registry.get(st, consolidated=True, industry_code="cns")
        if cs is None:
            print(f"  {cat.name}: NOT FOUND for cns consolidated")
            # SS と CF は別の業種コードかもしれないので WARNING のみ
            if cat in (StatementCategory.BALANCE_SHEET, StatementCategory.INCOME_STATEMENT):
                assert_true(False, f"{cat.name} should exist for cns")
            continue
        print(f"  {cat.name}: {len(cs.concepts)} concepts, role={cs.role_uri.split('/')[-1]}")
        names = cs.concept_names()
        non_abs = cs.non_abstract_concepts()
        print(f"    total concepts: {len(names)}, non-abstract: {len(non_abs)}")
        assert_true(len(non_abs) > 0, f"{cat.name} should have non-abstract concepts")


@test_case("CS-4: get_concept_set ショートカット")
def test_get_concept_set():
    """get_concept_set で直接取得。"""
    cs = get_concept_set(
        TAXONOMY_PATH,
        StatementType.BALANCE_SHEET,
        consolidated=True,
        industry_code="cns",
    )
    if cs is None:
        print("  get_concept_set returned None")
        # BS は存在するはず
        assert_true(False, "BS ConceptSet should exist")
    else:
        print(f"  BS: {len(cs.concepts)} concepts, role={cs.role_uri}")
        # legacy format 変換
        legacy = cs.to_legacy_format()
        print(f"  legacy format entries: {len(legacy)}")
        if legacy:
            print(f"    sample: {legacy[0]}")
        assert_true(len(legacy) > 0, "legacy format should have entries")


@test_case("CS-5: 実企業 Fact の ConceptSet 分類照合")
def test_fact_classification():
    """ソフトバンクG の jppfs_cor fact が ConceptSet 内に含まれるか検証。"""
    zip_bytes = download_document("S100W3C3", file_type="1")
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(".xbrl") and "PublicDoc/" in name:
                parsed = parse_xbrl_facts(zf.read(name), source_path=name)
                break
        else:
            raise RuntimeError("XBRL not found")

    jppfs_concepts_in_facts = set()
    for f in parsed.facts:
        if "jppfs_cor" in (f.namespace_uri or ""):
            jppfs_concepts_in_facts.add(f.local_name)

    print(f"  unique jppfs_cor concepts in facts: {len(jppfs_concepts_in_facts)}")

    registry = derive_concept_sets(TAXONOMY_PATH)

    # BS, PL の ConceptSet と照合
    for cat_name, st in [
        ("BS", StatementType.BALANCE_SHEET),
        ("PL", StatementType.INCOME_STATEMENT),
        ("CF", StatementType.CASH_FLOW_STATEMENT),
    ]:
        cs = registry.get(st, consolidated=True, industry_code="cns")
        if cs is None:
            print(f"  {cat_name}: ConceptSet not found (skip)")
            continue
        cs_names = cs.non_abstract_concepts()
        overlap = jppfs_concepts_in_facts & cs_names
        only_in_fact = jppfs_concepts_in_facts - cs_names
        print(f"  {cat_name}: {len(cs_names)} in set, {len(overlap)} overlap, {len(only_in_fact)} unclassified")
        if overlap:
            print(f"    sample overlap: {sorted(overlap)[:8]}")
        assert_true(len(overlap) > 0, f"{cat_name} should have overlap with actual facts")


# ─── 実行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_classify_role_uri,
        test_derive_concept_sets,
        test_cns_concept_sets,
        test_get_concept_set,
        test_fact_classification,
    ]
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)

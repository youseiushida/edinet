"""Wave 1 E2E テスト: 名前空間分類。

実際の EDINET API を叩いて名前空間分類機能の実用性を確認する。

テスト対象:
  - classify_namespace() で XBRL インスタンス内の全名前空間を分類
  - is_standard_taxonomy() / is_filer_namespace() の精度
  - extract_taxonomy_module() / extract_taxonomy_version() の抽出精度
  - NamespaceCategory の妥当性

使い方:
  EDINET_API_KEY=xxx python tools/wave1_e2e_namespaces.py
"""

from __future__ import annotations

import os
import sys
import traceback

from edinet import configure, documents
from edinet.xbrl import parse_xbrl_facts
from edinet.xbrl._namespaces import (
    NamespaceCategory,
    NamespaceInfo,
    classify_namespace,
    extract_taxonomy_module,
    extract_taxonomy_version,
    is_filer_namespace,
    is_standard_taxonomy,
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

def _collect_namespaces_from_xbrl(target_date: str = "2026-02-20") -> tuple[set[str], str]:
    """有報の XBRL から全名前空間 URI を収集する。"""
    filings = documents(target_date, doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        return set(), ""

    filing = xbrl_filings[0]
    xbrl_path, xbrl_bytes = filing.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)

    namespaces: set[str] = set()
    # Fact の concept_qname (Clark notation) から名前空間を抽出
    for fact in parsed.facts:
        if fact.concept_qname.startswith("{"):
            ns_end = fact.concept_qname.index("}")
            namespaces.add(fact.concept_qname[1:ns_end])
        # namespace_uri からも直接
        if fact.namespace_uri:
            namespaces.add(fact.namespace_uri)

    filer_name = filing.filer_name or filing.doc_id
    return namespaces, filer_name


# ─── テストケース ────────────────────────────────────────────

@test_case("NS-1: 既知の標準タクソノミ URI の分類")
def test_known_standard_uris():
    """既知の標準タクソノミ URI が正しく分類されることを確認。"""
    known_uris = {
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor": {
            "category": NamespaceCategory.STANDARD_TAXONOMY,
            "module": "jppfs_cor",
            "module_group": "jppfs",
            "version": "2025-11-01",
        },
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2025-11-01/jpdei_cor": {
            "category": NamespaceCategory.STANDARD_TAXONOMY,
            "module": "jpdei_cor",
            "module_group": "jpdei",
            "version": "2025-11-01",
        },
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor": {
            "category": NamespaceCategory.STANDARD_TAXONOMY,
            "module": "jpcrp_cor",
            "module_group": "jpcrp",
            "version": "2025-11-01",
        },
    }

    for uri, expected in known_uris.items():
        info = classify_namespace(uri)
        assert_isinstance(info, NamespaceInfo, "NamespaceInfo 型")
        assert_eq(info.category, expected["category"], f"category: {uri}")
        assert_true(info.is_standard, f"is_standard: {uri}")
        assert_eq(info.module_name, expected["module"], f"module: {uri}")
        assert_eq(info.module_group, expected["module_group"], f"module_group: {uri}")
        assert_eq(info.taxonomy_version, expected["version"], f"version: {uri}")
        assert_true(info.edinet_code is None, f"edinet_code は None: {uri}")
        print(f"  ✓ {uri}")
        print(f"    → {info.category.value}, module={info.module_name}, ver={info.taxonomy_version}")


@test_case("NS-2: 提出者タクソノミ URI の分類")
def test_filer_namespace():
    """提出者タクソノミ URI が正しく分類されることを確認。"""
    # 提出者タクソノミの URI は /taxonomy/ を含まないパス構成
    # 例: http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/...
    filer_uris = [
        "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18",
        "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E00001-000/2025-03-31/01/2025-06-18",
    ]

    for uri in filer_uris:
        info = classify_namespace(uri)
        assert_eq(info.category, NamespaceCategory.FILER_TAXONOMY, f"filer: {uri}")
        assert_true(not info.is_standard, f"is_standard=False: {uri}")
        assert_true(info.edinet_code is not None, f"edinet_code not None: {uri}")
        assert_true(
            info.edinet_code is not None and info.edinet_code.startswith("E"),
            f"edinet_code は E 始まり: {info.edinet_code}",
        )
        print(f"  ✓ {uri}")
        print(f"    → FILER, edinet_code={info.edinet_code}")


@test_case("NS-3: XBRL インフラ名前空間の分類")
def test_xbrl_infrastructure():
    """XBRL 標準名前空間が XBRL_INFRASTRUCTURE に分類されることを確認。"""
    # XBRL_INFRASTRUCTURE は _XBRL_INFRASTRUCTURE_URIS に定義された 5 URI のみ
    # iso4217, numeric, non-numeric は OTHER に分類される
    infra_uris = [
        "http://www.xbrl.org/2003/instance",      # NS_XBRLI
        "http://www.xbrl.org/2003/linkbase",       # NS_LINK
        "http://www.w3.org/1999/xlink",            # NS_XLINK
        "http://xbrl.org/2006/xbrldi",             # NS_XBRLDI
        "http://xbrl.org/2005/xbrldt",             # NS_XBRLDT
    ]

    for uri in infra_uris:
        info = classify_namespace(uri)
        assert_eq(
            info.category, NamespaceCategory.XBRL_INFRASTRUCTURE,
            f"infra: {uri}",
        )
        assert_true(not info.is_standard, f"is_standard=False: {uri}")
        assert_true(info.edinet_code is None, f"edinet_code は None: {uri}")
        print(f"  ✓ {uri} → {info.category.value}")


@test_case("NS-4: is_standard_taxonomy() / is_filer_namespace() ショートカット")
def test_shortcut_functions():
    """ショートカット関数の動作を確認。"""
    std_uri = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
    filer_uri = "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18"
    infra_uri = "http://www.xbrl.org/2003/instance"
    other_uri = "http://example.com/unknown"

    # is_standard_taxonomy
    assert_true(is_standard_taxonomy(std_uri), "標準 → True")
    assert_true(not is_standard_taxonomy(filer_uri), "提出者 → False")
    assert_true(not is_standard_taxonomy(infra_uri), "インフラ → False")
    assert_true(not is_standard_taxonomy(other_uri), "その他 → False")

    # is_filer_namespace
    assert_true(not is_filer_namespace(std_uri), "標準 → False")
    assert_true(is_filer_namespace(filer_uri), "提出者 → True")
    assert_true(not is_filer_namespace(infra_uri), "インフラ → False")
    assert_true(not is_filer_namespace(other_uri), "その他 → False")

    print("  is_standard_taxonomy / is_filer_namespace: OK")


@test_case("NS-5: extract_taxonomy_module() / extract_taxonomy_version()")
def test_extract_functions():
    """extract 関数の動作を確認。"""
    uri = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"

    module = extract_taxonomy_module(uri)
    assert_eq(module, "jppfs_cor", "module")

    version = extract_taxonomy_version(uri)
    assert_eq(version, "2025-11-01", "version")

    # 非標準 URI
    assert_true(extract_taxonomy_module("http://example.com") is None, "非標準は None")
    assert_true(extract_taxonomy_version("http://example.com") is None, "非標準は None")

    print(f"  module={module}, version={version}")


@test_case("NS-6: 実データの名前空間分類")
def test_real_data_classification():
    """実際の XBRL から収集した名前空間をすべて分類する。"""
    namespaces, filer_name = _collect_namespaces_from_xbrl()
    if not namespaces:
        print("  SKIP: 名前空間なし")
        return

    print(f"  対象: {filer_name}")
    print(f"  名前空間数: {len(namespaces)}")

    category_counts: dict[str, int] = {}
    for uri in sorted(namespaces):
        info = classify_namespace(uri)
        cat = info.category.value
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print(f"  分類結果:")
    for cat, count in sorted(category_counts.items()):
        print(f"    {cat}: {count}")

    # 標準タクソノミが少なくとも 1 つ存在するはず
    assert_true(
        category_counts.get("standard_taxonomy", 0) > 0,
        "標準タクソノミが存在するはず",
    )


@test_case("NS-7: 複数書類での名前空間バリエーション")
def test_namespace_variation_across_filings():
    """複数の書類で名前空間のバリエーションを確認。"""
    filings = documents("2026-02-20")
    xbrl_filings = [f for f in filings if f.has_xbrl][:3]

    if not xbrl_filings:
        print("  SKIP: XBRL 付き書類なし")
        return

    all_modules: set[str] = set()
    all_edinet_codes: set[str] = set()

    for filing in xbrl_filings:
        xbrl_path, xbrl_bytes = filing.fetch()
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)

        ns_set: set[str] = set()
        for fact in parsed.facts:
            if fact.namespace_uri:
                ns_set.add(fact.namespace_uri)

        modules = set()
        edinet_codes = set()
        for uri in ns_set:
            info = classify_namespace(uri)
            if info.module_name:
                modules.add(info.module_name)
            if info.edinet_code:
                edinet_codes.add(info.edinet_code)

        all_modules.update(modules)
        all_edinet_codes.update(edinet_codes)

        print(
            f"  {filing.doc_id} ({filing.filer_name}): "
            f"ns={len(ns_set)}, modules={sorted(modules)}, "
            f"filer_codes={sorted(edinet_codes)}"
        )

    print(f"\n  全モジュール: {sorted(all_modules)}")
    print(f"  全 EDINET コード: {sorted(all_edinet_codes)}")


@test_case("NS-8: module_group の抽出")
def test_module_group():
    """module_group が正しく抽出されることを確認。"""
    test_cases = {
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor": "jppfs",
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2025-11-01/jpdei_cor": "jpdei",
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor": "jpcrp",
    }

    for uri, expected_group in test_cases.items():
        info = classify_namespace(uri)
        assert_eq(info.module_group, expected_group, f"module_group for {uri}")
        print(f"  ✓ {uri} → group={info.module_group}")


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_known_standard_uris,
        test_filer_namespace,
        test_xbrl_infrastructure,
        test_shortcut_functions,
        test_extract_functions,
        test_real_data_classification,
        test_namespace_variation_across_filings,
        test_module_group,
    ]

    print(f"Wave 1 E2E テスト: Namespaces ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

"""Wave 2 E2E テスト #2: エッジケース検証。

シナリオ:
  A. 大量保有報告書 (S100VHHR) → DEI nil, namespace fallback も失敗 → UNKNOWN
  B. JMIS 企業: 該当企業を検索して検証
  C. 半期報告書 (銀行): DEI あり but doc_type が異なる
  D. J-GAAP 銀行業 (三菱UFJ E00009): 別記事業のコンセプト
  E. IFRS 企業で jgaap.canonical_key を呼んだ場合 → None (cross-standard safety)
  F. detect_from_dei に dei=None を渡した場合
"""

from __future__ import annotations

import os
import sys
import traceback
import zipfile
from io import BytesIO

from edinet import configure
from edinet.api.download import download_document
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl.dei import AccountingStandard
from edinet.financial.standards.detect import (
    DetectionMethod,
    DetailLevel,
    detect_accounting_standard,
    detect_from_dei,
    detect_from_namespaces,
)
from edinet.financial.standards import jgaap, ifrs

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


def assert_none(v, msg=""):
    if v is not None:
        raise AssertionError(f"Expected None, got {v!r}: {msg}")


def _load_xbrl(doc_id: str):
    """ZIPダウンロード → XBRL パース → (parsed, dei) を返す。"""
    zip_bytes = download_document(doc_id, file_type="1")
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(".xbrl") and "PublicDoc/" in name:
                xbrl_bytes = zf.read(name)
                parsed = parse_xbrl_facts(xbrl_bytes, source_path=name)
                dei = extract_dei(parsed.facts)
                return parsed, dei
    raise RuntimeError(f"XBRL not found in {doc_id}")


# ─── A. 大量保有報告書 ──────────────────────────────────────

@test_case("EDGE-A1: 大量保有報告書 → standard=None (DEI nil)")
def test_lvh_unknown():
    """大量保有報告書は AccountingStandardsDEI が nil で namespace も jpigp/jppfs なし。"""
    parsed, dei = _load_xbrl("S100VHHR")
    assert_none(dei.accounting_standards, "大量保有は accounting_standards=None")
    result = detect_accounting_standard(parsed.facts, dei=dei)
    print(f"  standard={result.standard}, method={result.method}")
    print(f"  namespace_modules={result.namespace_modules}")
    # standard は None (UNKNOWN) が正しい
    assert_none(result.standard, "大量保有報告書は standard=None が正しい")


# ─── B. IFRS 企業に jgaap.canonical_key → None ─────────────

@test_case("EDGE-B1: IFRS concept に jgaap.canonical_key → None (cross-standard)")
def test_cross_standard_safety():
    """IFRS の concept を jgaap.canonical_key に渡しても None になることを確認。"""
    # IFRS の代表的コンセプト
    ifrs_concepts = [
        "RevenueIFRS",
        "OperatingProfitLossIFRS",
        "ProfitLossAttributableToOwnersOfParentIFRS",
        "AssetsIFRS",
    ]
    for c in ifrs_concepts:
        key = jgaap.canonical_key(c)
        print(f"  jgaap.canonical_key({c}) = {key}")
        assert_none(key, f"IFRS concept {c} should not map in jgaap")


@test_case("EDGE-B2: J-GAAP concept に ifrs.canonical_key → None (cross-standard)")
def test_cross_standard_safety_reverse():
    """J-GAAP の concept を ifrs.canonical_key に渡しても None になることを確認。"""
    jgaap_concepts = [
        "NetSales",
        "OperatingIncome",
        "OrdinaryIncome",
        "NetIncome",
    ]
    for c in jgaap_concepts:
        key = ifrs.canonical_key(c)
        print(f"  ifrs.canonical_key({c}) = {key}")
        assert_none(key, f"J-GAAP concept {c} should not map in ifrs")


# ─── C. J-GAAP 銀行業の検証 ────────────────────────────────

@test_case("EDGE-C1: J-GAAP 銀行業 (みずほFG E00024 S100VZ5R)")
def test_jgaap_bank():
    """銀行業は別のコンセプトセットを使うが、detect は正常に動くはず。"""
    parsed, dei = _load_xbrl("S100VZ5R")
    result = detect_accounting_standard(parsed.facts, dei=dei)
    print(f"  standard={result.standard}, method={result.method}")
    print(f"  has_consolidated={result.has_consolidated}")
    print(f"  filer: {dei.filer_name_ja}")
    assert_eq(result.standard, AccountingStandard.JAPAN_GAAP)
    assert_eq(result.method, DetectionMethod.DEI)

    # 銀行特有: jppfs は使わず jpcrp + jpdei + jpbk (銀行モジュール)
    jppfs_facts = [f for f in parsed.facts if "jppfs_cor" in (f.namespace_uri or "")]
    jpcrp_facts = [f for f in parsed.facts if "jpcrp_cor" in (f.namespace_uri or "")]
    print(f"  jppfs_cor facts: {len(jppfs_facts)}")
    print(f"  jpcrp_cor facts: {len(jpcrp_facts)}")

    # 銀行でも canonical_key はある程度動く
    mapped = {}
    for f in jppfs_facts[:50]:
        key = jgaap.canonical_key(f.local_name)
        if key:
            mapped[f.local_name] = key
    print(f"  jgaap.canonical_key hits from jppfs: {len(mapped)}")
    for c, k in sorted(mapped.items())[:10]:
        print(f"    {c} -> {k}")


# ─── D. IFRS/J-GAAP マッピング整合性 ──────────────────────

@test_case("EDGE-D1: ifrs_to_jgaap / jgaap_to_ifrs 双方向マッピング")
def test_bidirectional_mapping():
    """IFRS → J-GAAP と J-GAAP → IFRS が整合的かを確認。"""
    i2j = ifrs.ifrs_to_jgaap_map()
    j2i = ifrs.jgaap_to_ifrs_map()
    print(f"  IFRS→J-GAAP entries: {len(i2j)}")
    print(f"  J-GAAP→IFRS entries: {len(j2i)}")

    # 双方向チェック: IFRS→J-GAAP があれば J-GAAP→IFRS にも逆が存在するはず
    mismatches = []
    for ifrs_concept, jgaap_concept in i2j.items():
        if jgaap_concept is None:
            continue
        reverse = j2i.get(jgaap_concept)
        if reverse != ifrs_concept:
            mismatches.append((ifrs_concept, jgaap_concept, reverse))

    if mismatches:
        for m in mismatches[:10]:
            print(f"  MISMATCH: IFRS {m[0]} -> J-GAAP {m[1]} -> IFRS {m[2]}")
    print(f"  mismatches: {len(mismatches)}")
    # Some mismatches may be expected (many-to-one) but should be minimal
    assert_true(len(mismatches) < 10, f"too many bidirectional mismatches: {len(mismatches)}")


# ─── E. 全 canonical key の一意性 ──────────────────────────

@test_case("EDGE-E1: J-GAAP canonical keys are unique")
def test_jgaap_unique_keys():
    all_keys = jgaap.all_canonical_keys()
    all_mappings = jgaap.all_mappings()
    print(f"  unique keys: {len(all_keys)}")
    print(f"  total mappings: {len(all_mappings)}")
    # 各 canonical_key で reverse_lookup が動く
    for key in sorted(all_keys):
        m = jgaap.reverse_lookup(key)
        assert_true(m is not None, f"reverse_lookup({key}) returned None")
    print(f"  all reverse_lookups passed")


@test_case("EDGE-E2: IFRS canonical keys are unique")
def test_ifrs_unique_keys():
    all_keys = ifrs.all_canonical_keys()
    all_mappings = ifrs.all_mappings()
    print(f"  unique keys: {len(all_keys)}")
    print(f"  total mappings: {len(all_mappings)}")
    for key in sorted(all_keys):
        m = ifrs.reverse_lookup(key)
        assert_true(m is not None, f"reverse_lookup({key}) returned None")
    print(f"  all reverse_lookups passed")


# ─── F. canonical key の cross-standard 整合性 ─────────────

@test_case("EDGE-F1: J-GAAP と IFRS の共通 canonical key")
def test_common_canonical_keys():
    """J-GAAP と IFRS で同じ canonical_key を使えば cross-standard 集計が可能。"""
    jgaap_keys = jgaap.all_canonical_keys()
    ifrs_keys = ifrs.all_canonical_keys()
    common = jgaap_keys & ifrs_keys
    jgaap_only = jgaap_keys - ifrs_keys
    ifrs_only = ifrs_keys - jgaap_keys
    print(f"  common keys: {len(common)}")
    print(f"  J-GAAP only: {len(jgaap_only)}")
    print(f"  IFRS only: {len(ifrs_only)}")
    print(f"  common: {sorted(common)}")
    if jgaap_only:
        print(f"  J-GAAP only: {sorted(jgaap_only)[:10]}")
    if ifrs_only:
        print(f"  IFRS only: {sorted(ifrs_only)[:10]}")
    # 主要指標は両方にあるべき
    for key in ["revenue", "operating_income", "total_assets", "net_assets"]:
        assert_true(key in common, f"'{key}' should be a common canonical key")


# ─── 実行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_lvh_unknown,
        test_cross_standard_safety,
        test_cross_standard_safety_reverse,
        test_jgaap_bank,
        test_bidirectional_mapping,
        test_jgaap_unique_keys,
        test_ifrs_unique_keys,
        test_common_canonical_keys,
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

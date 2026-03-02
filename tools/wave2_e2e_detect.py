"""Wave 2 E2E テスト #1: 会計基準検出 + 各標準モジュール lookup。

3社で detect_accounting_standard を検証:
  - J-GAAP: ソフトバンクグループ (E02778) S100W3C3  有報
  - IFRS:   日立製作所 (E01737) S100W56G  有報
  - US-GAAP: 野村HD (E03752) S100VXTD  有報

検証項目:
  1. detect_accounting_standard の standard / method / detail_level
  2. detect_from_dei / detect_from_namespaces それぞれ単独
  3. J-GAAP 企業で jgaap.canonical_key が動作
  4. IFRS 企業で ifrs.canonical_key が動作
  5. US-GAAP 企業で usgaap.extract_usgaap_summary が動作
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
from edinet.xbrl.contexts import structure_contexts
from edinet.financial.standards.detect import (
    DetectionMethod,
    DetailLevel,
    detect_accounting_standard,
    detect_from_dei,
    detect_from_namespaces,
)
from edinet.financial.standards import jgaap, ifrs, usgaap

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


# ─── J-GAAP: ソフトバンクG S100W3C3 ─────────────────────────

@test_case("DETECT-1: J-GAAP DEI検出 (ソフトバンクG)")
def test_jgaap_detect():
    parsed, dei = _load_xbrl("S100W3C3")
    result = detect_accounting_standard(parsed.facts, dei=dei)
    print(f"  standard={result.standard}, method={result.method}, detail={result.detail_level}")
    print(f"  has_consolidated={result.has_consolidated}")
    assert_eq(result.standard, AccountingStandard.JAPAN_GAAP)
    assert_eq(result.method, DetectionMethod.DEI)
    assert_eq(result.detail_level, DetailLevel.DETAILED)


@test_case("DETECT-2: J-GAAP namespace fallback (ソフトバンクG)")
def test_jgaap_ns():
    parsed, _ = _load_xbrl("S100W3C3")
    result = detect_from_namespaces(parsed.facts)
    print(f"  standard={result.standard}, modules={result.namespace_modules}")
    assert_eq(result.standard, AccountingStandard.JAPAN_GAAP)
    assert_true("jppfs" in result.namespace_modules, "should detect jppfs module")


@test_case("DETECT-3: J-GAAP canonical_key (ソフトバンクG)")
def test_jgaap_canonical():
    parsed, _ = _load_xbrl("S100W3C3")
    jppfs_facts = [f for f in parsed.facts if "jppfs_cor" in (f.namespace_uri or "")]
    print(f"  jppfs_cor facts: {len(jppfs_facts)}")
    assert_true(len(jppfs_facts) > 0, "should have jppfs_cor facts")

    mapped = {}
    for f in jppfs_facts:
        key = jgaap.canonical_key(f.local_name)
        if key:
            mapped[f.local_name] = key
    print(f"  mapped concepts: {len(mapped)}")
    for c, k in sorted(mapped.items())[:15]:
        print(f"    {c} -> {k}")
    assert_true(len(mapped) > 0, "should map jppfs concepts to canonical keys")


# ─── IFRS: 日立 S100W56G ────────────────────────────────────

@test_case("DETECT-4: IFRS DEI検出 (日立)")
def test_ifrs_detect():
    parsed, dei = _load_xbrl("S100W56G")
    result = detect_accounting_standard(parsed.facts, dei=dei)
    print(f"  standard={result.standard}, method={result.method}, detail={result.detail_level}")
    print(f"  has_consolidated={result.has_consolidated}")
    assert_eq(result.standard, AccountingStandard.IFRS, "standard should be IFRS")
    assert_eq(result.method, DetectionMethod.DEI)
    assert_eq(result.detail_level, DetailLevel.DETAILED)


@test_case("DETECT-5: IFRS namespace fallback (日立)")
def test_ifrs_ns():
    parsed, _ = _load_xbrl("S100W56G")
    result = detect_from_namespaces(parsed.facts)
    print(f"  standard={result.standard}, modules={result.namespace_modules}")
    assert_eq(result.standard, AccountingStandard.IFRS,
              "namespace fallback should detect IFRS via jpigp")
    assert_true("jpigp" in result.namespace_modules, "should detect jpigp module")


@test_case("DETECT-6: IFRS canonical_key (日立)")
def test_ifrs_canonical():
    parsed, _ = _load_xbrl("S100W56G")
    ifrs_facts = [f for f in parsed.facts if "jpigp_cor" in (f.namespace_uri or "")]
    print(f"  jpigp_cor facts: {len(ifrs_facts)}")
    assert_true(len(ifrs_facts) > 0, "should have jpigp_cor facts")

    mapped = {}
    for f in ifrs_facts:
        key = ifrs.canonical_key(f.local_name)
        if key:
            mapped[f.local_name] = key
    print(f"  mapped concepts: {len(mapped)}")
    for c, k in sorted(mapped.items())[:15]:
        print(f"    {c} -> {k}")
    assert_true(len(mapped) > 0, "should map jpigp concepts to canonical keys")


# ─── US-GAAP: 野村HD S100VXTD ──────────────────────────────

@test_case("DETECT-7: US-GAAP DEI検出 (野村HD)")
def test_usgaap_detect():
    parsed, dei = _load_xbrl("S100VXTD")
    result = detect_accounting_standard(parsed.facts, dei=dei)
    print(f"  standard={result.standard}, method={result.method}, detail={result.detail_level}")
    assert_eq(result.standard, AccountingStandard.US_GAAP)
    assert_eq(result.method, DetectionMethod.DEI)
    assert_eq(result.detail_level, DetailLevel.BLOCK_ONLY)


@test_case("DETECT-8: US-GAAP extract_summary (野村HD)")
def test_usgaap_summary():
    parsed, _ = _load_xbrl("S100VXTD")
    ctx_dict = structure_contexts(parsed.contexts)
    summary = usgaap.extract_usgaap_summary(parsed.facts, ctx_dict)
    print(f"  summary_items: {len(summary.summary_items)}")
    print(f"  text_blocks: {len(summary.text_blocks)}")
    print(f"  total_usgaap_elements: {summary.total_usgaap_elements}")
    for item in summary.summary_items[:8]:
        print(f"    {item.key}: {item.value}")
    assert_true(
        len(summary.summary_items) > 0 or len(summary.text_blocks) > 0,
        "should have summary items or text blocks",
    )


# ─── 実行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_jgaap_detect,
        test_jgaap_ns,
        test_jgaap_canonical,
        test_ifrs_detect,
        test_ifrs_ns,
        test_ifrs_canonical,
        test_usgaap_detect,
        test_usgaap_summary,
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

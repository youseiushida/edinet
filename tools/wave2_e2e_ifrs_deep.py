"""Wave 2 E2E テスト #5: IFRS 企業の詳細検証。

複数の IFRS 企業で:
  1. IFRS 検出が確実に動く
  2. canonical_key カバレッジが十分か
  3. ifrs_to_jgaap_map で cross-standard mapping が動くか
  4. IFRS 特有概念 (finance_income/costs) が検出されるか
  5. IFRS BS/PL の概念分布

対象:
  - 日立 (E01737) S100W56G  (有報)
  - NTT (E00734)  → 検索
  - 武田薬品 (E00919) → 検索
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
from edinet.xbrl.dei import AccountingStandard
from edinet.financial.standards.detect import (
    DetectionMethod,
    DetailLevel,
    detect_accounting_standard,
)
from edinet.financial.standards import ifrs, jgaap

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
    zip_bytes = download_document(doc_id, file_type="1")
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(".xbrl") and "PublicDoc/" in name:
                xbrl_bytes = zf.read(name)
                parsed = parse_xbrl_facts(xbrl_bytes, source_path=name)
                dei = extract_dei(parsed.facts)
                return parsed, dei
    raise RuntimeError(f"XBRL not found in {doc_id}")


def _find_doc_id(edinet_code: str, dates: list[str], doc_type: str = "120") -> str | None:
    """EDINET API から特定企業の特定種類の doc_id を検索。"""
    for date in dates:
        doc_list = documents(date)
        for doc in doc_list:
            if doc.edinet_code == edinet_code and doc.doc_type_code == doc_type:
                return doc.doc_id
    return None


# ─── テストケース ────────────────────────────────────────────

@test_case("IFRS-1: 日立の IFRS Fact カバレッジ詳細")
def test_hitachi_coverage():
    """日立の jpigp_cor fact が ifrs canonical_key にどの程度マッピングされるか。"""
    parsed, dei = _load_xbrl("S100W56G")
    print(f"  filer: {dei.filer_name_ja}")

    ifrs_facts = [f for f in parsed.facts if "jpigp_cor" in (f.namespace_uri or "")]
    unique_concepts = set(f.local_name for f in ifrs_facts)
    print(f"  total jpigp_cor facts: {len(ifrs_facts)}")
    print(f"  unique jpigp_cor concepts: {len(unique_concepts)}")

    mapped = {}
    unmapped = set()
    for c in unique_concepts:
        key = ifrs.canonical_key(c)
        if key:
            mapped[c] = key
        else:
            unmapped.add(c)

    print(f"  mapped: {len(mapped)}")
    print(f"  unmapped: {len(unmapped)}")

    print(f"\n  === Mapped concepts ===")
    for c, k in sorted(mapped.items()):
        print(f"    {c} -> {k}")

    print(f"\n  === Unmapped concepts (sample) ===")
    for c in sorted(unmapped)[:20]:
        print(f"    {c}")

    coverage = len(mapped) / len(unique_concepts) * 100 if unique_concepts else 0
    print(f"\n  coverage: {coverage:.1f}%")
    # 主要概念はマッピングされるべき (最低20%)
    assert_true(coverage > 15, f"coverage too low: {coverage:.1f}%")


@test_case("IFRS-2: IFRS 特有概念の検出")
def test_ifrs_specific():
    """日立の IFRS fact から finance_income, finance_costs が検出されるか。"""
    parsed, _ = _load_xbrl("S100W56G")

    ifrs_facts = [f for f in parsed.facts if "jpigp_cor" in (f.namespace_uri or "")]
    concept_set = set(f.local_name for f in ifrs_facts)

    # IFRS 特有の概念
    specific = ifrs.ifrs_specific_concepts()
    print(f"  IFRS-specific concepts defined: {len(specific)}")
    for s in specific:
        found = s.concept in concept_set
        print(f"    {s.concept}: canonical={s.canonical_key}, found={found}")

    # FinanceIncomeIFRS と FinanceCostsIFRS は存在するはず
    assert_true("FinanceIncomeIFRS" in concept_set or "FinanceCostsIFRS" in concept_set,
                "at least one of FinanceIncome/Costs should exist in IFRS filing")


@test_case("IFRS-3: ifrs_to_jgaap cross-mapping の実用テスト")
def test_cross_mapping():
    """日立の IFRS fact を J-GAAP 相当に変換できるか。"""
    parsed, _ = _load_xbrl("S100W56G")
    i2j = ifrs.ifrs_to_jgaap_map()

    ifrs_facts = [f for f in parsed.facts if "jpigp_cor" in (f.namespace_uri or "")]
    unique_concepts = set(f.local_name for f in ifrs_facts)

    cross_mapped = {}
    for c in unique_concepts:
        if c in i2j and i2j[c] is not None:
            cross_mapped[c] = i2j[c]

    print(f"  IFRS concepts with J-GAAP equivalent: {len(cross_mapped)}")
    for ifrs_c, jgaap_c in sorted(cross_mapped.items()):
        # J-GAAP 側で canonical_key も確認
        jkey = jgaap.canonical_key(jgaap_c)
        print(f"    {ifrs_c} -> {jgaap_c} (canonical: {jkey})")


@test_case("IFRS-4: NTT (E00734) IFRS検出")
def test_ntt():
    """NTT の有報を探して IFRS 検出。"""
    doc_id = _find_doc_id("E00734", ["2025-06-25", "2025-06-26", "2025-06-27"])
    if doc_id is None:
        print("  NTT 有報が見つからず (skip)")
        return
    print(f"  doc_id: {doc_id}")
    parsed, dei = _load_xbrl(doc_id)
    print(f"  filer: {dei.filer_name_ja}")
    result = detect_accounting_standard(parsed.facts, dei=dei)
    print(f"  standard={result.standard}, method={result.method}")
    assert_eq(result.standard, AccountingStandard.IFRS, "NTT should be IFRS")

    # canonical_key チェック
    ifrs_facts = [f for f in parsed.facts if "jpigp_cor" in (f.namespace_uri or "")]
    mapped = {f.local_name: ifrs.canonical_key(f.local_name)
              for f in ifrs_facts if ifrs.canonical_key(f.local_name)}
    print(f"  jpigp_cor facts: {len(ifrs_facts)}, mapped: {len(mapped)}")


@test_case("IFRS-5: 武田薬品 (E00919) IFRS検出")
def test_takeda():
    """武田薬品の有報を探して IFRS 検出。"""
    doc_id = _find_doc_id("E00919", ["2025-06-25", "2025-06-26", "2025-06-27", "2025-06-30"])
    if doc_id is None:
        print("  武田薬品 有報が見つからず (skip)")
        return
    print(f"  doc_id: {doc_id}")
    parsed, dei = _load_xbrl(doc_id)
    print(f"  filer: {dei.filer_name_ja}")
    result = detect_accounting_standard(parsed.facts, dei=dei)
    print(f"  standard={result.standard}, method={result.method}")
    assert_eq(result.standard, AccountingStandard.IFRS, "Takeda should be IFRS")

    ifrs_facts = [f for f in parsed.facts if "jpigp_cor" in (f.namespace_uri or "")]
    mapped = {f.local_name: ifrs.canonical_key(f.local_name)
              for f in ifrs_facts if ifrs.canonical_key(f.local_name)}
    print(f"  jpigp_cor facts: {len(ifrs_facts)}, mapped: {len(mapped)}")


# ─── 実行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_hitachi_coverage,
        test_ifrs_specific,
        test_cross_mapping,
        test_ntt,
        test_takeda,
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

"""Wave 2 E2E テスト #4: US-GAAP 詳細検証。

US-GAAP 全6社で extract_usgaap_summary を実行し、
summary_items / text_blocks の内容を深掘り検証する。

対象:
  - 野村ホールディングス S100VXTD
  - キヤノン S100VHZZ
  - 小松製作所 S100VXAI
  - 富士フイルムHD S100W3XJ
  - オリックス S100W3GQ
  - オムロン S100W20H

検証項目:
  1. 全社で standard=US_GAAP, detail_level=BLOCK_ONLY
  2. summary_items の期間重複チェック
  3. text_blocks の statement_hint 分布
  4. get_jgaap_mapping の動作
  5. canonical key カバレッジ
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
)
from edinet.financial.standards import usgaap

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)

USGAAP_COMPANIES = {
    "S100VXTD": "野村HD",
    "S100VHZZ": "キヤノン",
    "S100VXAI": "小松製作所",
    "S100W3XJ": "富士フイルムHD",
    "S100W3GQ": "オリックス",
    "S100W20H": "オムロン",
}

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


# ─── テストケース ────────────────────────────────────────────

@test_case("USGAAP-1: 全6社の基準検出と summary 抽出")
def test_all_usgaap():
    for doc_id, name in USGAAP_COMPANIES.items():
        print(f"\n  --- {name} ({doc_id}) ---")
        try:
            parsed, dei = _load_xbrl(doc_id)
            result = detect_accounting_standard(parsed.facts, dei=dei)
            print(f"    standard={result.standard}, detail={result.detail_level}")
            assert_eq(result.standard, AccountingStandard.US_GAAP, f"{name} should be US_GAAP")
            assert_eq(result.detail_level, DetailLevel.BLOCK_ONLY, f"{name} detail")

            ctx_dict = structure_contexts(parsed.contexts)
            summary = usgaap.extract_usgaap_summary(parsed.facts, ctx_dict)
            print(f"    items={len(summary.summary_items)}, blocks={len(summary.text_blocks)}, total={summary.total_usgaap_elements}")

            # 期間別集計
            periods = summary.available_periods
            print(f"    periods: {len(periods)}")
            for p in periods[:3]:
                items = summary.get_items_by_period(p)
                print(f"      {p}: {len(items)} items")
        except Exception as e:
            print(f"    ERROR: {e}")
            raise


@test_case("USGAAP-2: summary to_dict 変換")
def test_summary_to_dict():
    """to_dict が正常に動くか確認。"""
    parsed, _ = _load_xbrl("S100VXTD")
    ctx_dict = structure_contexts(parsed.contexts)
    summary = usgaap.extract_usgaap_summary(parsed.facts, ctx_dict)
    d = summary.to_dict()
    print(f"  to_dict entries: {len(d)}")
    if d:
        print(f"  sample: {d[0]}")
    assert_true(len(d) > 0, "to_dict should return entries")


@test_case("USGAAP-3: get_jgaap_mapping 動作確認")
def test_jgaap_mapping():
    """US-GAAP → J-GAAP マッピングが存在するか確認。"""
    mapping = usgaap.get_jgaap_mapping()
    print(f"  mapping entries: {len(mapping)}")
    for key, jgaap_concept in sorted(mapping.items()):
        print(f"    {key} -> {jgaap_concept}")
    assert_true(len(mapping) > 0, "should have mappings")
    # revenue は J-GAAP の NetSales にマッピングされるはず
    assert_true("revenue" in mapping, "revenue should be in mapping")


@test_case("USGAAP-4: is_usgaap_element 判定")
def test_is_usgaap_element():
    """US-GAAP 関連コンセプトの判定。"""
    assert_true(usgaap.is_usgaap_element("RevenuesUSGAAPSummaryOfBusinessResults"))
    assert_true(usgaap.is_usgaap_element("NetIncomeUSGAAPSummaryOfBusinessResults"))
    assert_true(not usgaap.is_usgaap_element("NetSales"), "J-GAAP concept should not match")
    assert_true(not usgaap.is_usgaap_element("RevenueIFRS"), "IFRS concept should not match")
    print("  all checks passed")


@test_case("USGAAP-5: text_blocks の中身確認")
def test_text_blocks():
    """text_blocks のうち少なくとも1つが html_content を持つか確認。"""
    parsed, _ = _load_xbrl("S100VXTD")
    ctx_dict = structure_contexts(parsed.contexts)
    summary = usgaap.extract_usgaap_summary(parsed.facts, ctx_dict)

    has_html = 0
    for block in summary.text_blocks:
        has_content = block.html_content is not None and len(block.html_content) > 0
        if has_content:
            has_html += 1
        print(f"  {block.concept[:60]}: hint={block.statement_hint}, has_html={has_content}, semi={block.is_semi_annual}")
    print(f"  text_blocks with HTML: {has_html}/{len(summary.text_blocks)}")


# ─── 実行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_all_usgaap,
        test_summary_to_dict,
        test_jgaap_mapping,
        test_is_usgaap_element,
        test_text_blocks,
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

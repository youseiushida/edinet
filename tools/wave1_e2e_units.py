"""Wave 1 E2E テスト: Unit 構造化。

実際の EDINET API を叩いて Unit 構造化の実用性を確認する。

テスト対象:
  - structure_units() で SimpleMeasure / DivideMeasure が正しく生成されるか
  - is_monetary / is_pure / is_shares / is_per_share の判定精度
  - currency_code の抽出
  - 実データに含まれる Unit のバリエーション

使い方:
  EDINET_API_KEY=xxx python tools/wave1_e2e_units.py
"""

from __future__ import annotations

import os
import sys
import traceback

from edinet import DocType, Filing, configure, documents
from edinet.xbrl import parse_xbrl_facts
from edinet.xbrl.units import (
    DivideMeasure,
    SimpleMeasure,
    StructuredUnit,
    structure_units,
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

def _fetch_and_parse(
    target_date: str = "2026-02-20",
    doc_type: DocType | str | None = "120",
):
    """XBRL 付き Filing を取得してパースする。"""
    kwargs: dict = {"date": target_date}
    if doc_type:
        kwargs["doc_type"] = doc_type
    filings = documents(**kwargs)
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        return None, None, None
    filing = xbrl_filings[0]
    xbrl_path, xbrl_bytes = filing.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    return filing, parsed, structure_units(parsed.units)


# ─── テストケース ────────────────────────────────────────────

@test_case("UNIT-1: 基本的な structure_units")
def test_basic_structure():
    """structure_units が辞書を返すことを確認。"""
    filing, parsed, unit_map = _fetch_and_parse()
    if unit_map is None:
        print("  SKIP: XBRL データなし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")
    assert_isinstance(unit_map, dict, "unit_map は dict")
    assert_gt(len(unit_map), 0, "少なくとも 1 つの Unit が存在")
    print(f"  Unit 数: {len(unit_map)}")

    for uid, unit in unit_map.items():
        assert_isinstance(unit, StructuredUnit, f"unit_map[{uid!r}] は StructuredUnit")
        assert_eq(unit.unit_id, uid, "unit_id とキーが一致")


@test_case("UNIT-2: JPY (通貨) の SimpleMeasure")
def test_jpy_simple_measure():
    """JPY の StructuredUnit が SimpleMeasure で通貨判定されることを確認。"""
    _, _, unit_map = _fetch_and_parse()
    if unit_map is None:
        print("  SKIP: XBRL データなし")
        return

    # JPY unit を探す
    jpy_units = [
        u for u in unit_map.values()
        if isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "JPY"
    ]

    if not jpy_units:
        print("  SKIP: JPY unit なし（外国企業の可能性）")
        return

    jpy = jpy_units[0]
    print(f"  unit_id: {jpy.unit_id}")
    print(f"  measure.raw_text: {jpy.measure.raw_text}")
    print(f"  measure.namespace_uri: {jpy.measure.namespace_uri}")

    assert_true(jpy.is_monetary, "JPY は is_monetary=True")
    assert_true(not jpy.is_pure, "JPY は is_pure=False")
    assert_true(not jpy.is_shares, "JPY は is_shares=False")
    assert_eq(jpy.currency_code, "JPY", "currency_code は JPY")


@test_case("UNIT-3: pure (比率) の検出")
def test_pure_unit():
    """xbrli:pure の StructuredUnit が正しく検出されることを確認。"""
    _, _, unit_map = _fetch_and_parse()
    if unit_map is None:
        print("  SKIP: XBRL データなし")
        return

    pure_units = [
        u for u in unit_map.values()
        if isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "pure"
    ]

    if not pure_units:
        print("  INFO: pure unit なし（比率データを持たない書類）")
        return

    pure = pure_units[0]
    print(f"  unit_id: {pure.unit_id}")
    assert_true(pure.is_pure, "pure は is_pure=True")
    assert_true(not pure.is_monetary, "pure は is_monetary=False")
    assert_true(not pure.is_shares, "pure は is_shares=False")
    assert_true(pure.currency_code is None, "pure は currency_code=None")


@test_case("UNIT-4: shares (株式数) の検出")
def test_shares_unit():
    """xbrli:shares の StructuredUnit が正しく検出されることを確認。"""
    _, _, unit_map = _fetch_and_parse()
    if unit_map is None:
        print("  SKIP: XBRL データなし")
        return

    shares_units = [
        u for u in unit_map.values()
        if isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "shares"
    ]

    if not shares_units:
        print("  INFO: shares unit なし")
        return

    shares = shares_units[0]
    print(f"  unit_id: {shares.unit_id}")
    assert_true(shares.is_shares, "shares は is_shares=True")
    assert_true(not shares.is_monetary, "shares は is_monetary=False")
    assert_true(not shares.is_pure, "shares は is_pure=False")


@test_case("UNIT-5: DivideMeasure (1株あたり等) の検出")
def test_divide_measure():
    """DivideMeasure が正しく構造化されることを確認。"""
    _, _, unit_map = _fetch_and_parse()
    if unit_map is None:
        print("  SKIP: XBRL データなし")
        return

    divide_units = [
        u for u in unit_map.values()
        if isinstance(u.measure, DivideMeasure)
    ]

    if not divide_units:
        print("  INFO: DivideMeasure なし（1株あたりデータなし）")
        return

    for du in divide_units:
        m = du.measure
        assert_isinstance(m, DivideMeasure, "DivideMeasure 型")
        assert_isinstance(m.numerator, SimpleMeasure, "分子は SimpleMeasure")
        assert_isinstance(m.denominator, SimpleMeasure, "分母は SimpleMeasure")
        print(
            f"  {du.unit_id}: {m.numerator.local_name} / {m.denominator.local_name}"
            f" | is_per_share={du.is_per_share}"
            f" | currency_code={du.currency_code}"
        )

    # JPY/shares のパターンを確認
    per_share = [u for u in divide_units if u.is_per_share]
    if per_share:
        ps = per_share[0]
        print(f"  1株あたり unit: {ps.unit_id}")
        assert_true(ps.is_per_share, "is_per_share=True")
        assert_true(not ps.is_monetary, "is_monetary=False")
        if ps.currency_code:
            print(f"  currency_code: {ps.currency_code}")


@test_case("UNIT-6: 全 Unit のバリエーション一覧")
def test_unit_variation():
    """実データに含まれる Unit の種類を一覧する。"""
    _, _, unit_map = _fetch_and_parse()
    if unit_map is None:
        print("  SKIP: XBRL データなし")
        return

    categories = {
        "monetary": [],
        "pure": [],
        "shares": [],
        "per_share": [],
        "other": [],
    }

    for u in unit_map.values():
        if u.is_monetary:
            categories["monetary"].append(u.unit_id)
        elif u.is_pure:
            categories["pure"].append(u.unit_id)
        elif u.is_shares:
            categories["shares"].append(u.unit_id)
        elif u.is_per_share:
            categories["per_share"].append(u.unit_id)
        else:
            categories["other"].append(u.unit_id)

    for cat, ids in categories.items():
        if ids:
            print(f"  {cat}: {', '.join(ids[:5])}" + (f" ... (+{len(ids)-5})" if len(ids) > 5 else ""))

    total = sum(len(v) for v in categories.values())
    assert_eq(total, len(unit_map), "カテゴリ合計 == Unit 総数")


@test_case("UNIT-7: 複数書類での Unit 比較")
def test_unit_across_filings():
    """異なる書類で Unit 構造が正しく取得できることを確認。"""
    filings = documents("2026-02-20")
    xbrl_filings = [f for f in filings if f.has_xbrl][:3]

    if not xbrl_filings:
        print("  SKIP: XBRL データなし")
        return

    for f in xbrl_filings:
        xbrl_path, xbrl_bytes = f.fetch()
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        unit_map = structure_units(parsed.units)

        monetary_count = sum(1 for u in unit_map.values() if u.is_monetary)
        divide_count = sum(1 for u in unit_map.values() if isinstance(u.measure, DivideMeasure))

        print(
            f"  {f.doc_id} ({f.filer_name}): "
            f"total={len(unit_map)}, "
            f"monetary={monetary_count}, "
            f"divide={divide_count}"
        )


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_basic_structure,
        test_jpy_simple_measure,
        test_pure_unit,
        test_shares_unit,
        test_divide_measure,
        test_unit_variation,
        test_unit_across_filings,
    ]

    print(f"Wave 1 E2E テスト: Units ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

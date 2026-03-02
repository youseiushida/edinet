"""Wave 1 E2E テスト: Context 構造化と ContextCollection。

実際の EDINET API を叩いて Context 関連機能の実用性を確認する。

テスト対象:
  - structure_contexts() で StructuredContext が正しく生成されるか
  - InstantPeriod / DurationPeriod の判定精度
  - DimensionMember の抽出
  - ContextCollection のフィルタチェーン
  - 最新期間の取得

使い方:
  EDINET_API_KEY=xxx python tools/wave1_e2e_contexts.py
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import date

from edinet import DocType, configure, documents
from edinet.xbrl import parse_xbrl_facts
from edinet.xbrl.contexts import (
    ContextCollection,
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
    structure_contexts,
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


def assert_lte(a, b, msg=""):
    if not (a <= b):
        raise AssertionError(f"Expected {a} <= {b}: {msg}")


# ─── 共通ヘルパー ────────────────────────────────────────────

def _fetch_ctx_map(
    target_date: str = "2026-02-20",
    doc_type: str = "120",
):
    """有報の Context をパースして返す。"""
    filings = documents(target_date, doc_type=doc_type)
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        return None, None
    filing = xbrl_filings[0]
    xbrl_path, xbrl_bytes = filing.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    ctx_map = structure_contexts(parsed.contexts)
    return filing, ctx_map


# ─── テストケース ────────────────────────────────────────────

@test_case("CTX-1: 基本的な structure_contexts")
def test_basic_structure():
    """structure_contexts が辞書を返すことを確認。"""
    filing, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    print(f"  対象: {filing.filer_name} ({filing.doc_id})")
    assert_isinstance(ctx_map, dict, "ctx_map は dict")
    assert_gt(len(ctx_map), 0, "少なくとも 1 つの Context が存在")
    print(f"  Context 数: {len(ctx_map)}")

    for cid, ctx in list(ctx_map.items())[:3]:
        assert_isinstance(ctx, StructuredContext, f"ctx は StructuredContext")
        assert_eq(ctx.context_id, cid, "context_id とキーが一致")
        print(f"  {cid}: period={ctx.period}, dims={len(ctx.dimensions)}")


@test_case("CTX-2: InstantPeriod / DurationPeriod の混在")
def test_period_types():
    """有報には Instant と Duration の両方が含まれることを確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    instant_count = sum(1 for c in ctx_map.values() if c.is_instant)
    duration_count = sum(1 for c in ctx_map.values() if c.is_duration)

    print(f"  InstantPeriod: {instant_count}")
    print(f"  DurationPeriod: {duration_count}")

    assert_gt(instant_count, 0, "Instant コンテキストが存在するはず")
    assert_gt(duration_count, 0, "Duration コンテキストが存在するはず")

    # 型チェック
    for ctx in ctx_map.values():
        if ctx.is_instant:
            assert_isinstance(ctx.period, InstantPeriod, "is_instant なら InstantPeriod")
            assert_isinstance(ctx.period.instant, date, "instant は date")
        else:
            assert_isinstance(ctx.period, DurationPeriod, "is_duration なら DurationPeriod")
            assert_isinstance(ctx.period.start_date, date, "start_date は date")
            assert_isinstance(ctx.period.end_date, date, "end_date は date")
            assert_true(
                ctx.period.start_date <= ctx.period.end_date,
                "start_date <= end_date",
            )


@test_case("CTX-3: 連結・個別の判定")
def test_consolidated_flag():
    """is_consolidated / is_non_consolidated の判定を確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    cons_count = sum(1 for c in ctx_map.values() if c.is_consolidated)
    non_cons_count = sum(1 for c in ctx_map.values() if c.is_non_consolidated)

    print(f"  連結: {cons_count}")
    print(f"  個別: {non_cons_count}")

    # 相互排他
    for ctx in ctx_map.values():
        assert_true(
            not (ctx.is_consolidated and ctx.is_non_consolidated),
            f"{ctx.context_id}: 連結と個別が同時に True",
        )


@test_case("CTX-4: DimensionMember の抽出")
def test_dimension_members():
    """Dimension を持つ Context の DimensionMember を確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    dim_contexts = [c for c in ctx_map.values() if c.has_dimensions]
    print(f"  Dimension 付き Context: {len(dim_contexts)} / {len(ctx_map)}")

    if not dim_contexts:
        print("  INFO: Dimension 付き Context なし")
        return

    # いくつかの Dimension を確認
    axes_seen: set[str] = set()
    for ctx in dim_contexts[:10]:
        for dm in ctx.dimensions:
            assert_isinstance(dm, DimensionMember, "DimensionMember 型")
            assert_true(dm.axis.startswith("{"), f"axis は Clark notation: {dm.axis}")
            assert_true(dm.member.startswith("{"), f"member は Clark notation: {dm.member}")
            axes_seen.add(dm.axis.split("}")[-1])

    print(f"  検出された軸 (ローカル名): {', '.join(sorted(axes_seen)[:10])}")


@test_case("CTX-5: ContextCollection 基本操作")
def test_context_collection_basic():
    """ContextCollection の初期化と基本操作を確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    coll = ContextCollection(ctx_map)

    assert_eq(len(coll), len(ctx_map), "len() が一致")

    # __iter__
    iter_count = sum(1 for _ in coll)
    assert_eq(iter_count, len(ctx_map), "__iter__ が全件返す")

    # __contains__
    first_id = next(iter(ctx_map))
    assert_true(first_id in coll, "__contains__ が動作する")

    # __getitem__
    ctx = coll[first_id]
    assert_isinstance(ctx, StructuredContext, "__getitem__ が StructuredContext を返す")

    # get
    ctx2 = coll.get(first_id)
    assert_eq(ctx, ctx2, "get() と [] が同じ結果")
    assert_true(coll.get("nonexistent_id") is None, "存在しないキーは None")

    # as_dict
    d = coll.as_dict
    assert_isinstance(d, dict, "as_dict は dict")
    assert_eq(len(d), len(ctx_map), "as_dict の長さが一致")

    print(f"  基本操作: OK (len={len(coll)})")


@test_case("CTX-6: ContextCollection フィルタチェーン")
def test_context_collection_filters():
    """ContextCollection のフィルタが正しく動作することを確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    coll = ContextCollection(ctx_map)
    total = len(coll)

    # 連結フィルタ
    cons = coll.filter_consolidated()
    assert_lte(len(cons), total, "連結 <= 全体")
    for ctx in cons:
        assert_true(ctx.is_consolidated, f"{ctx.context_id} は連結であるべき")

    # 個別フィルタ
    non_cons = coll.filter_non_consolidated()
    for ctx in non_cons:
        assert_true(ctx.is_non_consolidated, f"{ctx.context_id} は個別であるべき")

    # Instant フィルタ
    instant = coll.filter_instant()
    for ctx in instant:
        assert_true(ctx.is_instant, f"{ctx.context_id} は Instant であるべき")

    # Duration フィルタ
    duration = coll.filter_duration()
    for ctx in duration:
        assert_true(ctx.is_duration, f"{ctx.context_id} は Duration であるべき")

    # Extra dimensions なし
    no_extra = coll.filter_no_extra_dimensions()
    for ctx in no_extra:
        assert_true(
            not ctx.has_extra_dimensions,
            f"{ctx.context_id} は extra dimensions なしであるべき",
        )

    print(f"  全体={total}, 連結={len(cons)}, 個別={len(non_cons)}")
    print(f"  Instant={len(instant)}, Duration={len(duration)}")
    print(f"  extra_dims なし={len(no_extra)}")

    # チェーン
    main_instant = coll.filter_consolidated().filter_no_extra_dimensions().filter_instant()
    main_duration = coll.filter_consolidated().filter_no_extra_dimensions().filter_duration()
    print(f"  連結+主要+Instant={len(main_instant)}, 連結+主要+Duration={len(main_duration)}")


@test_case("CTX-7: 最新期間の取得")
def test_latest_period():
    """latest_instant_period / latest_duration_period が正しく動作することを確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    coll = ContextCollection(ctx_map)

    # 最新 Instant
    lip = coll.latest_instant_period
    if lip is not None:
        assert_isinstance(lip, InstantPeriod, "latest_instant_period は InstantPeriod")
        print(f"  最新 InstantPeriod: {lip.instant}")

        # latest_instant_contexts で同じ期間のコンテキストが返ること
        latest_inst = coll.latest_instant_contexts()
        assert_gt(len(latest_inst), 0, "最新 Instant コンテキストが存在")
        for ctx in latest_inst:
            assert_eq(ctx.period, lip, "最新 Instant と一致")

    # 最新 Duration
    ldp = coll.latest_duration_period
    if ldp is not None:
        assert_isinstance(ldp, DurationPeriod, "latest_duration_period は DurationPeriod")
        print(f"  最新 DurationPeriod: {ldp.start_date} ～ {ldp.end_date}")

        latest_dur = coll.latest_duration_contexts()
        assert_gt(len(latest_dur), 0, "最新 Duration コンテキストが存在")
        for ctx in latest_dur:
            assert_eq(ctx.period, ldp, "最新 Duration と一致")


@test_case("CTX-8: unique_*_periods の一覧")
def test_unique_periods():
    """unique_instant_periods / unique_duration_periods が正しく動作することを確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    coll = ContextCollection(ctx_map)

    # ユニーク Instant 期間
    uip = coll.unique_instant_periods
    print(f"  ユニーク InstantPeriod: {len(uip)}")
    for p in uip:
        assert_isinstance(p, InstantPeriod, "InstantPeriod 型")
    # 降順確認
    for i in range(len(uip) - 1):
        assert_true(
            uip[i].instant >= uip[i + 1].instant,
            f"降順: {uip[i].instant} >= {uip[i+1].instant}",
        )
    for p in uip[:5]:
        print(f"    {p.instant}")

    # ユニーク Duration 期間
    udp = coll.unique_duration_periods
    print(f"  ユニーク DurationPeriod: {len(udp)}")
    for p in udp:
        assert_isinstance(p, DurationPeriod, "DurationPeriod 型")
    # 降順確認 (end_date)
    for i in range(len(udp) - 1):
        assert_true(
            udp[i].end_date >= udp[i + 1].end_date,
            f"降順: {udp[i].end_date} >= {udp[i+1].end_date}",
        )
    for p in udp[:5]:
        print(f"    {p.start_date} ～ {p.end_date}")


@test_case("CTX-9: filter_by_period")
def test_filter_by_period():
    """filter_by_period が指定期間に一致するコンテキストを返すことを確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    coll = ContextCollection(ctx_map)

    # 最新 Instant で絞り込み
    lip = coll.latest_instant_period
    if lip is not None:
        filtered = coll.filter_by_period(lip)
        assert_gt(len(filtered), 0, "filter_by_period で結果がある")
        for ctx in filtered:
            assert_eq(ctx.period, lip, "期間が一致")
        print(f"  InstantPeriod({lip.instant}) で絞り込み: {len(filtered)} 件")


@test_case("CTX-10: dimension_dict / get_dimension_member")
def test_dimension_access():
    """dimension_dict / has_dimension / get_dimension_member の動作を確認。"""
    _, ctx_map = _fetch_ctx_map()
    if ctx_map is None:
        print("  SKIP: データなし")
        return

    dim_contexts = [c for c in ctx_map.values() if c.has_dimensions]
    if not dim_contexts:
        print("  SKIP: Dimension 付き Context なし")
        return

    ctx = dim_contexts[0]
    dd = ctx.dimension_dict
    assert_isinstance(dd, dict, "dimension_dict は dict")
    assert_eq(len(dd), len(ctx.dimensions), "dimension_dict の長さ == dimensions の長さ")

    for dm in ctx.dimensions:
        assert_true(ctx.has_dimension(dm.axis), f"has_dimension({dm.axis}) == True")
        member = ctx.get_dimension_member(dm.axis)
        assert_eq(member, dm.member, "get_dimension_member の一致")

    # 存在しない軸
    assert_true(not ctx.has_dimension("{fake}FakeAxis"), "存在しない軸は False")
    assert_true(ctx.get_dimension_member("{fake}FakeAxis") is None, "存在しない軸は None")

    print(f"  {ctx.context_id}: {len(ctx.dimensions)} dimensions")


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_basic_structure,
        test_period_types,
        test_consolidated_flag,
        test_dimension_members,
        test_context_collection_basic,
        test_context_collection_filters,
        test_latest_period,
        test_unique_periods,
        test_filter_by_period,
        test_dimension_access,
    ]

    print(f"Wave 1 E2E テスト: Contexts ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

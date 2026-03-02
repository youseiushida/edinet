"""test_facts.py — build_line_items() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.exceptions import EdinetParseError
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
    structure_contexts,
)
from edinet.xbrl.facts import build_line_items
from edinet.xbrl.parser import RawFact, parse_xbrl_facts
from edinet.xbrl.taxonomy import LabelSource, TaxonomyResolver, ROLE_LABEL

from .conftest import TAXONOMY_MINI_DIR, load_xbrl_bytes

# テスト用名前空間（taxonomy_mini の XSD targetNamespace と一致させること）
_NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
_NS_JPDEI = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2025-11-01/jpdei_cor"


def _make_fact(
    *,
    local_name: str = "NetSales",
    namespace_uri: str = _NS_JPPFS,
    context_ref: str = "CurrentYearDuration",
    unit_ref: str | None = "JPY",
    decimals: int | str | None = -6,
    value_raw: str | None = "1000000000",
    is_nil: bool = False,
    fact_id: str | None = None,
    xml_lang: str | None = None,
    source_line: int | None = 1,
    order: int = 0,
    value_inner_xml: str | None = None,
) -> RawFact:
    """テスト用 RawFact を構築するヘルパー。"""
    return RawFact(
        concept_qname=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=unit_ref,
        decimals=decimals,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=fact_id,
        xml_lang=xml_lang,
        source_line=source_line,
        order=order,
        value_inner_xml=value_inner_xml,
    )


def _make_ctx(
    *,
    context_id: str = "CurrentYearDuration",
    period: DurationPeriod | InstantPeriod | None = None,
    entity_id: str = "E00001",
    dimensions: tuple[DimensionMember, ...] = (),
    source_line: int | None = 1,
) -> StructuredContext:
    """テスト用 StructuredContext を構築するヘルパー。"""
    if period is None:
        period = DurationPeriod(
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
    return StructuredContext(
        context_id=context_id,
        period=period,
        entity_id=entity_id,
        dimensions=dimensions,
        source_line=source_line,
    )


def _make_ctx_map(
    *contexts: StructuredContext,
) -> dict[str, StructuredContext]:
    """テスト用 Context 辞書を構築するヘルパー。"""
    return {ctx.context_id: ctx for ctx in contexts}


@pytest.fixture()
def resolver() -> TaxonomyResolver:
    """taxonomy_mini フィクスチャを使った TaxonomyResolver。"""
    return TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)


# ---------------------------------------------------------------------------
# P0 テスト（14 件・必須）
# ---------------------------------------------------------------------------


class TestP0:
    """P0: 必須テストケース。"""

    def test_numeric_fact_to_line_item(self, resolver: TaxonomyResolver) -> None:
        """数値 Fact が Decimal に変換され、ラベルが正しく解決されること。"""
        fact = _make_fact()
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        items = build_line_items([fact], ctx_map, resolver)

        assert len(items) == 1
        item = items[0]
        assert isinstance(item, LineItem)
        assert item.value == Decimal("1000000000")
        assert isinstance(item.value, Decimal)

        # ラベル検証
        assert item.label_ja.text == "売上高"
        assert item.label_en.text == "Net sales"
        assert item.label_ja.source == LabelSource.STANDARD
        assert item.label_ja.role == ROLE_LABEL
        assert item.label_ja.lang == "ja"
        assert item.label_en.lang == "en"

    def test_negative_numeric_value(self, resolver: TaxonomyResolver) -> None:
        """負の数値が正しく Decimal に変換されること。"""
        fact = _make_fact(
            local_name="OperatingIncome",
            value_raw="-500000000",
        )
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].value == Decimal("-500000000")

    def test_text_fact_to_line_item(self, resolver: TaxonomyResolver) -> None:
        """テキスト Fact の value が str のまま保持されること。"""
        fact = _make_fact(
            local_name="FilerNameInJapaneseDEI",
            namespace_uri=_NS_JPDEI,
            unit_ref=None,
            decimals=None,
            value_raw="テスト株式会社",
        )
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        item = items[0]
        assert item.value == "テスト株式会社"
        assert isinstance(item.value, str)
        assert item.unit_ref is None
        assert item.decimals is None

    @pytest.mark.parametrize(
        ("unit_ref", "decimals"),
        [
            ("JPY", -6),
            (None, None),
        ],
        ids=["nil_numeric", "nil_text"],
    )
    def test_nil_fact_value_is_none(
        self,
        resolver: TaxonomyResolver,
        unit_ref: str | None,
        decimals: int | None,
    ) -> None:
        """nil Fact（数値・テキスト両方）の value が None であること。"""
        fact = _make_fact(
            is_nil=True,
            value_raw=None,
            unit_ref=unit_ref,
            decimals=decimals,
        )
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].value is None
        assert items[0].is_nil is True

    def test_context_id_preserved(self, resolver: TaxonomyResolver) -> None:
        """LineItem.context_id が RawFact.context_ref と一致すること。"""
        fact = _make_fact(context_ref="MyCtx")
        ctx = _make_ctx(context_id="MyCtx")
        ctx_map = _make_ctx_map(ctx)

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].context_id == "MyCtx"

    def test_period_duration_from_context(self, resolver: TaxonomyResolver) -> None:
        """DurationPeriod の Context から period が正しく転写されること。"""
        period = DurationPeriod(
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
        fact = _make_fact()
        ctx = _make_ctx(period=period)
        ctx_map = _make_ctx_map(ctx)

        items = build_line_items([fact], ctx_map, resolver)

        assert isinstance(items[0].period, DurationPeriod)
        assert items[0].period.start_date == date(2024, 4, 1)
        assert items[0].period.end_date == date(2025, 3, 31)

    def test_period_instant_from_context(self, resolver: TaxonomyResolver) -> None:
        """InstantPeriod の Context から period が正しく転写されること。"""
        period = InstantPeriod(instant=date(2025, 3, 31))
        fact = _make_fact(context_ref="Instant")
        ctx = _make_ctx(context_id="Instant", period=period)
        ctx_map = _make_ctx_map(ctx)

        items = build_line_items([fact], ctx_map, resolver)

        assert isinstance(items[0].period, InstantPeriod)
        assert items[0].period.instant == date(2025, 3, 31)

    def test_dimensions_from_context(self, resolver: TaxonomyResolver) -> None:
        """Dimension 付き Context の dimensions が正しく転写されること。"""
        dim = DimensionMember(
            axis="{http://example.com}ConsolidatedOrNonConsolidatedAxis",
            member="{http://example.com}NonConsolidatedMember",
        )
        fact = _make_fact(context_ref="DimCtx")
        ctx = _make_ctx(context_id="DimCtx", dimensions=(dim,))
        ctx_map = _make_ctx_map(ctx)

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].dimensions == (dim,)
        assert items[0].dimensions[0].axis == dim.axis
        assert items[0].dimensions[0].member == dim.member

    def test_dimensions_empty_when_no_scenario(self, resolver: TaxonomyResolver) -> None:
        """Dimension なし Context の dimensions が空タプルであること。"""
        fact = _make_fact()
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].dimensions == ()

    def test_order_preserved(self, resolver: TaxonomyResolver) -> None:
        """出力タプルの順序が入力の facts と同じであること。"""
        facts = [
            _make_fact(local_name="NetSales", order=0),
            _make_fact(local_name="OperatingIncome", order=1),
            _make_fact(local_name="Assets", order=2),
        ]
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items(facts, ctx_map, resolver)

        assert [item.order for item in items] == [0, 1, 2]
        for i, item in enumerate(items):
            assert item.order == i

    def test_all_facts_converted_no_filter(self, resolver: TaxonomyResolver) -> None:
        """入力 Fact 数 = 出力 LineItem 数であること（フィルタなし）。"""
        facts = [
            _make_fact(local_name="NetSales", order=0),
            _make_fact(
                local_name="FilerName",
                namespace_uri=_NS_JPDEI,
                unit_ref=None,
                decimals=None,
                value_raw="テスト株式会社",
                order=1,
            ),
            _make_fact(
                local_name="ExtraordinaryLoss",
                is_nil=True,
                value_raw=None,
                order=2,
            ),
        ]
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items(facts, ctx_map, resolver)

        assert len(items) == len(facts) == 3

    def test_entity_id_from_context(self, resolver: TaxonomyResolver) -> None:
        """LineItem.entity_id が StructuredContext.entity_id と一致すること。"""
        fact = _make_fact()
        ctx = _make_ctx(entity_id="E12345")
        ctx_map = _make_ctx_map(ctx)

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].entity_id == "E12345"

    def test_missing_context_raises(self, resolver: TaxonomyResolver) -> None:
        """context_map に存在しない context_ref で EdinetParseError が発生すること。"""
        fact = _make_fact(context_ref="UnknownCtx")
        ctx_map: dict[str, StructuredContext] = {}

        with pytest.raises(EdinetParseError, match=r"UnknownCtx"):
            build_line_items([fact], ctx_map, resolver)


# ---------------------------------------------------------------------------
# P1 テスト（9 件・推奨）
# ---------------------------------------------------------------------------


class TestP1:
    """P1: 推奨テストケース。"""

    def test_decimals_inf(self, resolver: TaxonomyResolver) -> None:
        """decimals="INF" が文字列 "INF" として保持されること。"""
        fact = _make_fact(decimals="INF")
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].decimals == "INF"
        assert isinstance(items[0].decimals, str)

    def test_decimals_zero(self, resolver: TaxonomyResolver) -> None:
        """decimals=0 が int 0 として保持されること。"""
        fact = _make_fact(decimals=0)
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].decimals == 0
        assert isinstance(items[0].decimals, int)

    def test_fallback_label(self, resolver: TaxonomyResolver) -> None:
        """taxonomy_mini に含まれない namespace で FALLBACK になること。"""
        unknown_ns = "http://example.com/unknown/2025-11-01/unknown_cor"
        fact = _make_fact(
            local_name="CustomConcept",
            namespace_uri=unknown_ns,
        )
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].label_ja.source == LabelSource.FALLBACK
        assert items[0].label_ja.text == "CustomConcept"

    def test_empty_facts_returns_empty_tuple(self, resolver: TaxonomyResolver) -> None:
        """空の facts で空の tuple が返ること。"""
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([], ctx_map, resolver)

        assert items == ()
        assert isinstance(items, tuple)

    def test_concept_and_namespace_preserved(self, resolver: TaxonomyResolver) -> None:
        """concept / namespace_uri / local_name が正しく保持されること。"""
        fact = _make_fact(local_name="NetSales", namespace_uri=_NS_JPPFS)
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        item = items[0]
        assert item.concept == f"{{{_NS_JPPFS}}}NetSales"
        assert item.namespace_uri == _NS_JPPFS
        assert item.local_name == "NetSales"

    def test_source_line_preserved(self, resolver: TaxonomyResolver) -> None:
        """LineItem.source_line が RawFact.source_line と一致すること。"""
        fact = _make_fact(source_line=42)
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].source_line == 42

    @pytest.mark.medium
    @pytest.mark.integration
    def test_integration_with_simple_pl_fixture(self, resolver: TaxonomyResolver) -> None:
        """simple_pl.xbrl のフルパイプラインで全 Fact が LineItem に変換されること。"""
        xbrl_bytes = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(xbrl_bytes, source_path="simple_pl.xbrl")
        ctx_map = structure_contexts(parsed.contexts)

        # 前提検証
        assert len(ctx_map) == 4

        items = build_line_items(parsed.facts, ctx_map, resolver)

        assert len(items) == 20

        # 数値 Fact の型検証
        numeric_items = [item for item in items if item.unit_ref is not None and not item.is_nil]
        for item in numeric_items:
            assert isinstance(item.value, Decimal)

        # テキスト Fact の型検証
        text_items = [item for item in items if item.unit_ref is None and not item.is_nil]
        for item in text_items:
            assert isinstance(item.value, str)

        # nil Fact の型検証
        nil_items = [item for item in items if item.is_nil]
        for item in nil_items:
            assert item.value is None

        # バージョン違いフォールバックにより jppfs_cor の Fact は STANDARD で解決される
        # （taxonomy_mini にラベルが含まれている concept のみ）。
        # jpdei_cor / jpigp_cor は taxonomy_mini に含まれないため FALLBACK のまま。
        # taxonomy_mini に含まれない jppfs_cor の concept も FALLBACK になる。
        net_sales = next(i for i in items if i.local_name == "NetSales" and i.order == 0)
        assert net_sales.label_ja.source == LabelSource.STANDARD
        assert net_sales.label_ja.text == "売上高"

    def test_decimal_conversion_failure_raises(self, resolver: TaxonomyResolver) -> None:
        """数値 Fact で Decimal 変換できない値の場合 EdinetParseError が発生すること。"""
        fact = _make_fact(value_raw="not_a_number")
        ctx_map = _make_ctx_map(_make_ctx())

        with pytest.raises(EdinetParseError, match=r"not_a_number"):
            build_line_items([fact], ctx_map, resolver)

    def test_text_fact_value_raw_none_raises(self, resolver: TaxonomyResolver) -> None:
        """非 nil テキスト Fact で value_raw も value_inner_xml も None の場合 EdinetParseError。"""
        fact = _make_fact(
            unit_ref=None,
            decimals=None,
            value_raw=None,
            is_nil=False,
            value_inner_xml=None,
        )
        ctx_map = _make_ctx_map(_make_ctx())

        with pytest.raises(EdinetParseError, match=r"non-nil text fact"):
            build_line_items([fact], ctx_map, resolver)

    def test_markup_only_text_fact_returns_empty_string(
        self, resolver: TaxonomyResolver
    ) -> None:
        """マークアップのみの TextBlock（value_raw=None, value_inner_xml あり）が空文字列になること。"""
        fact = _make_fact(
            local_name="NotesTextBlock",
            unit_ref=None,
            decimals=None,
            value_raw=None,
            is_nil=False,
            value_inner_xml="<p/>",
        )
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].value == ""
        assert isinstance(items[0].value, str)

    def test_text_fact_prefers_value_raw_over_inner_xml(
        self, resolver: TaxonomyResolver
    ) -> None:
        """value_raw と value_inner_xml が両方ある場合、value_raw が優先されること。"""
        fact = _make_fact(
            local_name="NotesTextBlock",
            unit_ref=None,
            decimals=None,
            value_raw="プレーンテキスト",
            is_nil=False,
            value_inner_xml="<p>マークアップ付き</p>",
        )
        ctx_map = _make_ctx_map(_make_ctx())

        items = build_line_items([fact], ctx_map, resolver)

        assert items[0].value == "プレーンテキスト"

    def test_numeric_fact_value_raw_none_raises(
        self, resolver: TaxonomyResolver
    ) -> None:
        """非 nil 数値 Fact で value_raw=None の場合 EdinetParseError が発生すること。"""
        fact = _make_fact(
            unit_ref="JPY",
            decimals=-6,
            value_raw=None,
            is_nil=False,
        )
        ctx_map = _make_ctx_map(_make_ctx())

        with pytest.raises(EdinetParseError, match=r"non-nil numeric fact"):
            build_line_items([fact], ctx_map, resolver)

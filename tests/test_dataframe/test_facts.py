"""test_facts.py — line_items_to_dataframe() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.dataframe.facts import _FULL_COLUMNS, line_items_to_dataframe
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
)
from edinet.financial.statements import build_statements
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _make_item(
    *,
    local_name: str = "NetSales",
    value: Decimal = Decimal("1000000"),
    period: DurationPeriod | InstantPeriod | None = None,
    dimensions: tuple[DimensionMember, ...] = (),
    label_ja: str = "売上高",
    label_en: str = "Net sales",
) -> LineItem:
    if period is None:
        period = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
    return LineItem(
        concept=f"{{{_NS}}}{local_name}",
        namespace_uri=_NS,
        local_name=local_name,
        label_ja=_make_label(label_ja),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="ctx",
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=False,
        source_line=1,
        order=0,
    )


@pytest.mark.small
@pytest.mark.unit
class TestLineItemsToDataframe:
    """line_items_to_dataframe() のテスト。"""

    def test_basic_conversion(self) -> None:
        """3 items → DataFrame 3 行、全カラム存在。"""
        items = [
            _make_item(local_name="NetSales", value=Decimal("1000")),
            _make_item(
                local_name="CostOfSales", value=Decimal("700"),
                label_ja="売上原価", label_en="Cost of sales",
            ),
            _make_item(
                local_name="GrossProfit", value=Decimal("300"),
                label_ja="売上総利益", label_en="Gross profit",
            ),
        ]
        df = line_items_to_dataframe(items)
        assert len(df) == 3
        for col in _FULL_COLUMNS:
            assert col in df.columns, f"カラム {col!r} が存在しない"

    def test_empty_items(self) -> None:
        """空 items → 空 DataFrame、カラム名は正しい。"""
        df = line_items_to_dataframe([])
        assert len(df) == 0
        for col in _FULL_COLUMNS:
            assert col in df.columns

    def test_period_type_duration(self) -> None:
        """DurationPeriod → period_type='duration'。"""
        item = _make_item(
            period=DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)),
        )
        df = line_items_to_dataframe([item])
        assert df.iloc[0]["period_type"] == "duration"
        assert df.iloc[0]["period_start"] == date(2024, 4, 1)
        assert df.iloc[0]["period_end"] == date(2025, 3, 31)

    def test_period_type_instant(self) -> None:
        """InstantPeriod → period_type='instant'。"""
        item = _make_item(
            local_name="Assets",
            period=InstantPeriod(instant=date(2025, 3, 31)),
            label_ja="資産合計",
            label_en="Total assets",
        )
        df = line_items_to_dataframe([item])
        assert df.iloc[0]["period_type"] == "instant"
        assert df.iloc[0]["period_start"] is None
        assert df.iloc[0]["period_end"] == date(2025, 3, 31)

    def test_consolidated_no_dimensions(self) -> None:
        """dimensions なし → consolidated=True。"""
        item = _make_item(dimensions=())
        df = line_items_to_dataframe([item])
        assert df.iloc[0]["consolidated"] == True  # noqa: E712

    def test_consolidated_non_consolidated(self) -> None:
        """NonConsolidatedMember → consolidated=False。"""
        dim = (
            DimensionMember(
                axis=f"{{{_NS}}}ConsolidatedOrNonConsolidatedAxis",
                member=f"{{{_NS}}}NonConsolidatedMember",
            ),
        )
        item = _make_item(dimensions=dim)
        df = line_items_to_dataframe([item])
        assert df.iloc[0]["consolidated"] == False  # noqa: E712

    def test_consolidated_mixed_dimensions(self) -> None:
        """非標準 dimension のみ → consolidated=None。"""
        dim = (
            DimensionMember(
                axis=f"{{{_NS}}}OperatingSegmentsAxis",
                member=f"{{{_NS}}}SegmentAMember",
            ),
        )
        item = _make_item(dimensions=dim)
        df = line_items_to_dataframe([item])
        assert df.iloc[0]["consolidated"] is None

    def test_metadata_in_attrs(self) -> None:
        """metadata が attrs に設定されること。"""
        df = line_items_to_dataframe(
            [_make_item()],
            metadata={"test_key": "test_value"},
        )
        assert df.attrs["test_key"] == "test_value"


@pytest.mark.small
@pytest.mark.unit
class TestStatementsToDataframe:
    """Statements.to_dataframe() のテスト。"""

    def test_statements_to_dataframe(self) -> None:
        """Statements.to_dataframe() が全 LineItem を含むこと。"""
        items = (
            _make_item(local_name="NetSales"),
            _make_item(
                local_name="CostOfSales",
                label_ja="売上原価", label_en="Cost of sales",
            ),
        )
        stmts = build_statements(items)
        df = stmts.to_dataframe()
        # 全アイテムが含まれる（フィルタされない）
        assert len(df) == 2
        for col in _FULL_COLUMNS:
            assert col in df.columns


@pytest.mark.small
@pytest.mark.unit
class TestFinancialStatementToDataframe:
    """FinancialStatement.to_dataframe() のテスト。"""

    def test_default_5_columns(self) -> None:
        """デフォルト（full=False）→ 5 カラム。"""
        items = (_make_item(),)
        stmts = build_statements(items)
        pl = stmts.income_statement()
        df = pl.to_dataframe()
        assert list(df.columns) == ["label_ja", "label_en", "value", "unit", "concept"]

    def test_full_all_columns(self) -> None:
        """full=True → 全カラム。"""
        items = (_make_item(),)
        stmts = build_statements(items)
        pl = stmts.income_statement()
        df = pl.to_dataframe(full=True)
        for col in _FULL_COLUMNS:
            assert col in df.columns

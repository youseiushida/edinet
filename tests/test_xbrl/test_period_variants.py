"""test_period_variants.py — 期間分類のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.exceptions import EdinetWarning
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod
from edinet.xbrl.dei import DEI
from edinet.financial.dimensions.period_variants import classify_periods
from edinet.financial.statements import Statements
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
    value: Decimal = Decimal("1000"),
    period: DurationPeriod | InstantPeriod | None = None,
    order: int = 0,
) -> LineItem:
    if period is None:
        period = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
    return LineItem(
        concept=f"{{{_NS}}}{local_name}",
        namespace_uri=_NS,
        local_name=local_name,
        label_ja=_make_label("売上高"),
        label_en=_make_label("Net sales", "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="ctx",
        period=period,
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


# ---------------------------------------------------------------------------
# classify_periods のテスト
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestClassifyPeriods:
    """classify_periods() のテスト。"""

    def test_all_dates_present(self) -> None:
        """全日付あり → 正しい current/prior。"""
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
            previous_fiscal_year_start_date=date(2023, 4, 1),
            previous_fiscal_year_end_date=date(2024, 3, 31),
        )
        pc = classify_periods(dei)
        assert pc.current_duration == DurationPeriod(
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
        )
        assert pc.current_instant == InstantPeriod(instant=date(2025, 3, 31))
        assert pc.prior_duration == DurationPeriod(
            start_date=date(2023, 4, 1), end_date=date(2024, 3, 31),
        )
        assert pc.prior_instant == InstantPeriod(instant=date(2024, 3, 31))

    def test_comparative_period_preferred(self) -> None:
        """comparative_period_end_date が優先されること。"""
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
            previous_fiscal_year_start_date=date(2023, 4, 1),
            comparative_period_end_date=date(2024, 9, 30),
            previous_fiscal_year_end_date=date(2024, 3, 31),
        )
        pc = classify_periods(dei)
        # comparative が優先される
        assert pc.prior_duration is not None
        assert pc.prior_duration.end_date == date(2024, 9, 30)
        assert pc.prior_instant is not None
        assert pc.prior_instant.instant == date(2024, 9, 30)

    def test_no_prior_dates(self) -> None:
        """前期日付なし → prior が None。"""
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
        )
        pc = classify_periods(dei)
        assert pc.current_duration is not None
        assert pc.current_instant is not None
        assert pc.prior_duration is None
        assert pc.prior_instant is None

    def test_all_none(self) -> None:
        """全 None → 全フィールド None。"""
        dei = DEI()
        pc = classify_periods(dei)
        assert pc.current_duration is None
        assert pc.prior_duration is None
        assert pc.current_instant is None
        assert pc.prior_instant is None


# ---------------------------------------------------------------------------
# Statements の period variant 統合テスト
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestPeriodVariantIntegration:
    """Statements.income_statement(period="prior") 等の統合テスト。"""

    def test_period_current_selects_current(self) -> None:
        """period='current' → 当期の PL。"""
        cur = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        prev = DurationPeriod(start_date=date(2023, 4, 1), end_date=date(2024, 3, 31))

        items = (
            _make_item(local_name="NetSales", value=Decimal("1000"), period=cur),
            _make_item(local_name="NetSales", value=Decimal("800"), period=prev),
        )
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
            previous_fiscal_year_start_date=date(2023, 4, 1),
            previous_fiscal_year_end_date=date(2024, 3, 31),
        )
        stmts = Statements(
            _items=items,
            _dei=dei,
        )
        pl = stmts.income_statement(period="current")
        assert pl.period == cur

    def test_period_prior_selects_prior(self) -> None:
        """period='prior' → 前期の PL。"""
        cur = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        prev = DurationPeriod(start_date=date(2023, 4, 1), end_date=date(2024, 3, 31))

        items = (
            _make_item(local_name="NetSales", value=Decimal("1000"), period=cur),
            _make_item(local_name="NetSales", value=Decimal("800"), period=prev),
        )
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
            previous_fiscal_year_start_date=date(2023, 4, 1),
            previous_fiscal_year_end_date=date(2024, 3, 31),
        )
        stmts = Statements(
            _items=items,
            _dei=dei,
        )
        pl = stmts.income_statement(period="prior")
        assert pl.period == prev

    def test_period_prior_bs(self) -> None:
        """period='prior' → 前期末の BS。"""
        cur_i = InstantPeriod(instant=date(2025, 3, 31))
        prev_i = InstantPeriod(instant=date(2024, 3, 31))

        items = (
            _make_item(local_name="Assets", value=Decimal("5000"), period=cur_i),
            _make_item(local_name="Assets", value=Decimal("4000"), period=prev_i),
        )
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
            previous_fiscal_year_start_date=date(2023, 4, 1),
            previous_fiscal_year_end_date=date(2024, 3, 31),
        )
        stmts = Statements(
            _items=items,
            _dei=dei,
        )
        bs = stmts.balance_sheet(period="prior")
        assert bs.period == prev_i

    def test_no_dei_period_prior_warns(self) -> None:
        """DEI なしで period='prior' → warning + auto-latest。"""
        items = (_make_item(),)
        stmts = Statements(_items=items)
        with pytest.warns(EdinetWarning, match="解決できません"):
            pl = stmts.income_statement(period="prior")
        # DEI なし → period=None に解決 → auto-latest
        assert pl.period is not None  # auto-latest で選択される

    def test_period_current_bs(self) -> None:
        """period='current' → 当期末の BS。"""
        cur_i = InstantPeriod(instant=date(2025, 3, 31))
        prev_i = InstantPeriod(instant=date(2024, 3, 31))

        items = (
            _make_item(local_name="Assets", value=Decimal("5000"), period=cur_i),
            _make_item(local_name="Assets", value=Decimal("4000"), period=prev_i),
        )
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
            previous_fiscal_year_start_date=date(2023, 4, 1),
            previous_fiscal_year_end_date=date(2024, 3, 31),
        )
        stmts = Statements(_items=items, _dei=dei)
        bs = stmts.balance_sheet(period="current")
        assert bs.period == cur_i

    def test_invalid_period_literal_warns(self) -> None:
        """不正な period 文字列 → warning + auto-latest。"""
        items = (_make_item(),)
        dei = DEI(
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
        )
        stmts = Statements(_items=items, _dei=dei)
        with pytest.warns(EdinetWarning, match="不明な period 指定"):
            pl = stmts.income_statement(period="invalid")  # type: ignore[arg-type]
        assert pl.period is not None  # auto-latest にフォールバック

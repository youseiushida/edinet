"""test_rich.py — Rich 描画のテスト (R-1〜R-7)。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest

from edinet.display.rich import render_statement
from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
from edinet.xbrl.contexts import DurationPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
_PERIOD = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))


def _label(text: str, lang: str = "ja") -> LabelInfo:
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _item(
    local_name: str = "NetSales",
    label_ja: str = "売上高",
    label_en: str = "Net sales",
    value: Decimal | str | None = Decimal("1000000000"),
    order: int = 0,
) -> LineItem:
    return LineItem(
        concept=f"{{{_NS}}}{local_name}",
        namespace_uri=_NS,
        local_name=local_name,
        label_ja=_label(label_ja, "ja"),
        label_en=_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearDuration",
        period=_PERIOD,
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


@pytest.fixture()
def sample_pl() -> FinancialStatement:
    """テスト用の PL。3 科目。"""
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(
            _item("NetSales", "売上高", "Net sales", Decimal("45095325000000"), 1),
            _item(
                "OperatingIncome",
                "営業利益",
                "Operating income",
                Decimal("4295325000000"),
                5,
            ),
            _item(
                "OrdinaryIncome",
                "経常利益",
                "Ordinary income",
                Decimal("4800000000000"),
                8,
            ),
        ),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


@pytest.fixture()
def empty_pl() -> FinancialStatement:
    """空の PL。"""
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=None,
        items=(),
        consolidated=True,
        entity_id="",
        warnings_issued=(),
    )


# ---- R-1: render_statement が Table を返す ----


def test_render_statement_returns_table(sample_pl: FinancialStatement) -> None:
    """R-1: render_statement() が rich.table.Table を返すこと。"""
    from rich.table import Table

    table = render_statement(sample_pl)
    assert isinstance(table, Table)


# ---- R-2: カラム数 ----


def test_render_statement_column_count(sample_pl: FinancialStatement) -> None:
    """R-2: Table のカラム数が 3 であること。"""
    table = render_statement(sample_pl)
    assert len(table.columns) == 3


# ---- R-3: 行数 ----


def test_render_statement_row_count(sample_pl: FinancialStatement) -> None:
    """R-3: table.row_count が items 数と一致すること。"""
    table = render_statement(sample_pl)
    assert table.row_count == len(sample_pl.items)


# ---- R-4: タイトルに型ラベルが含まれる ----


def test_render_statement_title_contains_type(
    sample_pl: FinancialStatement,
) -> None:
    """R-4: Table の title に '損益計算書' が含まれること。"""
    table = render_statement(sample_pl)
    assert table.title is not None
    assert "損益計算書" in table.title


# ---- R-5: Console.print() の E2E ----


def test_rich_console_print(sample_pl: FinancialStatement) -> None:
    """R-5: Console(file=StringIO()).print(pl) が例外なく動き出力に '損益計算書' が含まれること。"""
    from rich.console import Console

    buf = StringIO()
    console = Console(file=buf, force_terminal=True)
    console.print(sample_pl)
    output = buf.getvalue()
    assert "損益計算書" in output


# ---- R-6: 空 statement ----


def test_render_statement_empty(empty_pl: FinancialStatement) -> None:
    """R-6: 空 statement で空の Table（0行）が返ること。"""
    table = render_statement(empty_pl)
    assert table.row_count == 0


# ---- R-7: [連結] の Rich マークアップエスケープ ----


def test_render_statement_escaped_brackets(
    sample_pl: FinancialStatement,
) -> None:
    """R-7: [連結] が Rich マークアップと衝突せず MarkupError が発生しないこと。"""
    from rich.console import Console

    table = render_statement(sample_pl)
    buf = StringIO()
    console = Console(file=buf, force_terminal=True)
    console.print(table)
    output = buf.getvalue()
    assert "連結" in output

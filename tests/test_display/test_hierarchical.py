"""test_hierarchical.py — 階層表示のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.display.statements import build_display_rows
from edinet.models.financial import FinancialStatement, LineItem, StatementType
from edinet.xbrl.contexts import DurationPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource
from edinet.xbrl.taxonomy.concept_sets import ConceptEntry, ConceptSet, StatementCategory

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
    label_ja: str = "売上高",
) -> LineItem:
    return LineItem(
        concept=f"{{{_NS}}}{local_name}",
        namespace_uri=_NS,
        local_name=local_name,
        label_ja=_make_label(label_ja),
        label_en=_make_label("Net sales", "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="ctx",
        period=DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)),
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=0,
    )


def _make_fs(*items: LineItem) -> FinancialStatement:
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)),
        items=items,
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


def _make_concept_set(entries: list[ConceptEntry]) -> ConceptSet:
    return ConceptSet(
        role_uri="http://example.com/role/PL",
        category=StatementCategory.INCOME_STATEMENT,
        is_consolidated=True,
        concepts=tuple(entries),
        source_info="test",
    )


# ---------------------------------------------------------------------------
# build_display_rows のテスト
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestBuildDisplayRows:
    """build_display_rows() のテスト。"""

    def test_flat_without_concept_set(self) -> None:
        """ConceptSet なし → フラット表示。"""
        items = (
            _make_item(local_name="NetSales", label_ja="売上高"),
            _make_item(local_name="CostOfSales", label_ja="売上原価", value=Decimal("700")),
        )
        fs = _make_fs(*items)
        rows = build_display_rows(fs)
        assert len(rows) == 2
        assert all(r.depth == 0 for r in rows)
        assert all(not r.is_abstract for r in rows)

    def test_hierarchical_with_concept_set(self) -> None:
        """ConceptSet あり → abstract 行が挿入、depth 正しい。"""
        entries = [
            ConceptEntry(concept="IncomeStatementAbstract", order=0, is_total=False, is_abstract=True, depth=0, href=""),
            ConceptEntry(concept="NetSales", order=1, is_total=False, is_abstract=False, depth=1, href=""),
            ConceptEntry(concept="CostOfSales", order=2, is_total=False, is_abstract=False, depth=1, href=""),
            ConceptEntry(concept="GrossProfit", order=3, is_total=True, is_abstract=False, depth=1, href=""),
        ]
        cs = _make_concept_set(entries)

        items = (
            _make_item(local_name="NetSales", label_ja="売上高", value=Decimal("1000")),
            _make_item(local_name="CostOfSales", label_ja="売上原価", value=Decimal("700")),
            _make_item(local_name="GrossProfit", label_ja="売上総利益", value=Decimal("300")),
        )
        fs = _make_fs(*items)

        rows = build_display_rows(
            fs, cs,
            abstract_labels={"IncomeStatementAbstract": "損益計算書"},
        )
        # abstract + 3 non-abstract = 4 rows
        assert len(rows) == 4

        # abstract 行
        assert rows[0].is_abstract is True
        assert rows[0].value is None
        assert rows[0].depth == 0
        assert rows[0].label == "損益計算書"

        # 非 abstract 行
        assert rows[1].concept == "NetSales"
        assert rows[1].depth == 1
        assert rows[1].is_abstract is False

        # total 行
        assert rows[3].is_total is True
        assert rows[3].concept == "GrossProfit"

    def test_concept_not_in_fs_skipped(self) -> None:
        """ConceptSet に存在するが FS にない科目 → スキップ。"""
        entries = [
            ConceptEntry(concept="NetSales", order=0, is_total=False, is_abstract=False, depth=0, href=""),
            ConceptEntry(concept="CostOfSales", order=1, is_total=False, is_abstract=False, depth=0, href=""),
        ]
        cs = _make_concept_set(entries)
        items = (_make_item(local_name="NetSales"),)
        fs = _make_fs(*items)

        rows = build_display_rows(fs, cs)
        # CostOfSales は FS にないのでスキップ
        assert len(rows) == 1
        assert rows[0].concept == "NetSales"

    def test_fs_extra_concepts_appended(self) -> None:
        """FS にあるが ConceptSet にない科目 → 末尾に追加。"""
        entries = [
            ConceptEntry(concept="NetSales", order=0, is_total=False, is_abstract=False, depth=0, href=""),
        ]
        cs = _make_concept_set(entries)
        items = (
            _make_item(local_name="NetSales"),
            _make_item(local_name="ExtraItem", label_ja="追加科目"),
        )
        fs = _make_fs(*items)

        rows = build_display_rows(fs, cs)
        assert len(rows) == 2
        assert rows[0].concept == "NetSales"
        assert rows[1].concept == "ExtraItem"
        assert rows[1].depth == 0

    def test_empty_financial_statement(self) -> None:
        """空の FinancialStatement → 空のリスト。"""
        fs = _make_fs()  # no items
        rows = build_display_rows(fs)
        assert rows == []

    def test_empty_fs_with_concept_set(self) -> None:
        """空 FS + ConceptSet → abstract 行のみ。"""
        entries = [
            ConceptEntry(concept="Heading", order=0, is_total=False, is_abstract=True, depth=0, href=""),
            ConceptEntry(concept="NetSales", order=1, is_total=False, is_abstract=False, depth=1, href=""),
        ]
        cs = _make_concept_set(entries)
        fs = _make_fs()

        rows = build_display_rows(
            fs, cs,
            abstract_labels={"Heading": "見出し"},
        )
        # abstract 行のみ（非 abstract は FS にないのでスキップ）
        assert len(rows) == 1
        assert rows[0].is_abstract is True


@pytest.mark.small
@pytest.mark.unit
class TestRenderHierarchicalStatement:
    """render_hierarchical_statement() のテスト。"""

    def test_render_returns_rich_table(self) -> None:
        """Rich Table が返されること。"""
        from rich.table import Table

        from edinet.display.statements import render_hierarchical_statement

        items = (_make_item(),)
        fs = _make_fs(*items)
        table = render_hierarchical_statement(fs)
        assert isinstance(table, Table)

    def test_render_with_concept_set(self) -> None:
        """ConceptSet ありで Rich Table の行数が正しいこと。"""
        from rich.table import Table

        from edinet.display.statements import render_hierarchical_statement

        entries = [
            ConceptEntry(concept="Heading", order=0, is_total=False, is_abstract=True, depth=0, href=""),
            ConceptEntry(concept="NetSales", order=1, is_total=False, is_abstract=False, depth=1, href=""),
        ]
        cs = _make_concept_set(entries)
        items = (_make_item(),)
        fs = _make_fs(*items)

        table = render_hierarchical_statement(
            fs, cs,
            abstract_labels={"Heading": "見出し"},
        )
        assert isinstance(table, Table)
        assert table.row_count == 2  # abstract + 1 data row

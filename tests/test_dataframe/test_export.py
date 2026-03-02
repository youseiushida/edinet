"""test_export.py — CSV / Parquet / Excel エクスポートのテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from edinet.dataframe.export import to_csv, to_parquet
from edinet.dataframe.facts import line_items_to_dataframe
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import DurationPeriod
from edinet.financial.statements import build_statements
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"


def _has_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


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


@pytest.mark.small
@pytest.mark.unit
class TestExportCsv:
    """to_csv() のテスト。"""

    def test_csv_roundtrip(self, tmp_path) -> None:
        """CSV 出力→読み戻しで内容が保持されること。"""
        items = [_make_item(), _make_item(local_name="CostOfSales", label_ja="売上原価")]
        df = line_items_to_dataframe(items)
        path = tmp_path / "test.csv"
        to_csv(df, path)

        loaded = pd.read_csv(path)
        assert len(loaded) == 2
        assert "label_ja" in loaded.columns

    def test_csv_utf8_sig(self, tmp_path) -> None:
        """UTF-8-sig エンコーディングであること。"""
        df = line_items_to_dataframe([_make_item()])
        path = tmp_path / "test.csv"
        to_csv(df, path)

        with open(path, "rb") as f:
            bom = f.read(3)
        assert bom == b"\xef\xbb\xbf"  # UTF-8 BOM


@pytest.mark.small
@pytest.mark.unit
class TestExportParquet:
    """to_parquet() のテスト。"""

    @pytest.mark.skipif(
        not _has_pyarrow(),
        reason="pyarrow がインストールされていない",
    )
    def test_parquet_roundtrip(self, tmp_path) -> None:
        """Parquet 出力→読み戻しで行数が保持されること。"""
        items = [_make_item()]
        df = line_items_to_dataframe(items)
        path = tmp_path / "test.parquet"
        to_parquet(df, path)

        loaded = pd.read_parquet(path)
        assert len(loaded) == 1
        assert "label_ja" in loaded.columns


@pytest.mark.small
@pytest.mark.unit
class TestFinancialStatementExport:
    """FinancialStatement の便利メソッドテスト。"""

    def test_financial_statement_to_csv(self, tmp_path) -> None:
        """FinancialStatement.to_csv() が動作すること。"""
        items = (_make_item(),)
        stmts = build_statements(items)
        pl = stmts.income_statement()
        path = tmp_path / "pl.csv"
        pl.to_csv(path)

        loaded = pd.read_csv(path)
        assert len(loaded) >= 1

    def test_statements_to_csv(self, tmp_path) -> None:
        """Statements.to_csv() が動作すること。"""
        items = (_make_item(),)
        stmts = build_statements(items)
        path = tmp_path / "stmts.csv"
        stmts.to_csv(path)

        loaded = pd.read_csv(path)
        assert len(loaded) >= 1


@pytest.mark.small
@pytest.mark.unit
class TestExportExcel:
    """to_excel() のテスト。"""

    def test_excel_roundtrip(self, tmp_path) -> None:
        """Excel 出力→読み戻しで内容が保持されること。"""
        items = [_make_item(), _make_item(local_name="CostOfSales", label_ja="売上原価")]
        df = line_items_to_dataframe(items)
        path = tmp_path / "test.xlsx"

        from edinet.dataframe.export import to_excel

        to_excel(df, path)

        loaded = pd.read_excel(path)
        assert len(loaded) == 2
        assert "label_ja" in loaded.columns

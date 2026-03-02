"""test_financial_display.py — __str__, to_dataframe, 遅延 import のテスト。"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
    _DATAFRAME_COLUMNS,
)
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod
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
    period: DurationPeriod | InstantPeriod = _PERIOD,
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
        period=period,
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


# ==========================================================================
# __str__() テスト (S-1 〜 S-13)
# ==========================================================================


def test_str_contains_type_label(sample_pl: FinancialStatement) -> None:
    """S-1: 出力に '損益計算書' が含まれる。"""
    assert "損益計算書" in str(sample_pl)


def test_str_contains_consolidated_label(sample_pl: FinancialStatement) -> None:
    """S-2: 出力に '連結' が含まれる。"""
    assert "連結" in str(sample_pl)


def test_str_contains_period(sample_pl: FinancialStatement) -> None:
    """S-3: 出力に '2024-04-01' と '2025-03-31' が含まれる。"""
    output = str(sample_pl)
    assert "2024-04-01" in output
    assert "2025-03-31" in output


def test_str_contains_item_labels(sample_pl: FinancialStatement) -> None:
    """S-4: 出力に各科目の label_ja.text が含まれる。"""
    output = str(sample_pl)
    for item in sample_pl.items:
        assert item.label_ja.text in output


def test_str_contains_formatted_values(sample_pl: FinancialStatement) -> None:
    """S-5: 出力に '45,095,325,000,000' が含まれる（カンマ区切り）。"""
    assert "45,095,325,000,000" in str(sample_pl)


def test_str_contains_count(sample_pl: FinancialStatement) -> None:
    """S-6: 出力に '3 科目' が含まれる。"""
    assert "3 科目" in str(sample_pl)


def test_str_empty_statement(empty_pl: FinancialStatement) -> None:
    """S-7: 空 statement で '科目なし' が含まれ、例外が出ない。"""
    output = str(empty_pl)
    assert "科目なし" in output


@pytest.mark.parametrize(
    ("consolidated", "expected"),
    [
        (True, "連結"),
        (False, "個別"),
    ],
)
def test_str_scope_label(consolidated: bool, expected: str) -> None:
    """S-8: 連結/個別ラベルの切り替え。"""
    pl = FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(_item(),),
        consolidated=consolidated,
        entity_id="E00001",
        warnings_issued=(),
    )
    assert expected in str(pl)


def test_str_balance_sheet_instant_period() -> None:
    """S-9: BS（InstantPeriod）で '2025-03-31' が含まれ '〜' がない。"""
    instant = InstantPeriod(instant=date(2025, 3, 31))
    bs = FinancialStatement(
        statement_type=StatementType.BALANCE_SHEET,
        period=instant,
        items=(_item(period=instant),),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )
    output = str(bs)
    assert "2025-03-31" in output
    assert "貸借対照表" in output
    # InstantPeriod は '〜' を含まない
    header_line = output.split("\n")[0]
    assert "〜" not in header_line


def test_str_negative_value() -> None:
    """S-10: 負値で '-500,000,000' が出力に含まれること。"""
    pl = FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(_item(value=Decimal("-500000000")),),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )
    assert "-500,000,000" in str(pl)


def test_str_text_value() -> None:
    """S-11: value が str の LineItem で例外なく動き、値が出力に含まれること。"""
    pl = FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(_item(value="テキスト値"),),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )
    assert "テキスト値" in str(pl)


def test_str_none_value() -> None:
    """S-12: value が None の LineItem で '—' が出力に含まれること。"""
    pl = FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(_item(value=None),),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )
    assert "—" in str(pl)


def test_str_cash_flow_statement() -> None:
    """S-13: CF タイプで 'キャッシュ・フロー計算書' が含まれること。"""
    cf = FinancialStatement(
        statement_type=StatementType.CASH_FLOW_STATEMENT,
        period=_PERIOD,
        items=(_item(),),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )
    assert "キャッシュ・フロー計算書" in str(cf)


# ==========================================================================
# to_dataframe() テスト (D-1 〜 D-8)
# ==========================================================================


def test_to_dataframe_columns(sample_pl: FinancialStatement) -> None:
    """D-1: カラムが期待通りであること。"""
    df = sample_pl.to_dataframe()
    assert list(df.columns) == _DATAFRAME_COLUMNS


def test_to_dataframe_row_count(sample_pl: FinancialStatement) -> None:
    """D-2: 行数が items 数と一致すること。"""
    df = sample_pl.to_dataframe()
    assert len(df) == len(sample_pl.items)


def test_to_dataframe_value_type(sample_pl: FinancialStatement) -> None:
    """D-3: value 列の値が Decimal であること。"""
    df = sample_pl.to_dataframe()
    assert isinstance(df["value"].iloc[0], Decimal)


def test_to_dataframe_labels(sample_pl: FinancialStatement) -> None:
    """D-4: label_ja 列の値が科目名と一致すること。"""
    df = sample_pl.to_dataframe()
    assert df["label_ja"].iloc[0] == "売上高"
    assert df["label_ja"].iloc[1] == "営業利益"
    assert df["label_ja"].iloc[2] == "経常利益"


def test_to_dataframe_empty(empty_pl: FinancialStatement) -> None:
    """D-5: 空 statement で空 DataFrame（0行）が返りカラム名が一致すること。"""
    df = empty_pl.to_dataframe()
    assert len(df) == 0
    assert list(df.columns) == _DATAFRAME_COLUMNS


def test_to_dataframe_import_error() -> None:
    """D-6: pandas がない場合に ImportError が発生すること。"""
    pl = FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_PERIOD,
        items=(_item(),),
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )
    with patch.dict(sys.modules, {"pandas": None}):
        with pytest.raises(ImportError, match="pip install edinet"):
            pl.to_dataframe()


def test_to_dataframe_attrs(sample_pl: FinancialStatement) -> None:
    """D-7: df.attrs にメタデータが含まれること。"""
    df = sample_pl.to_dataframe()
    assert df.attrs["statement_type"] == "income_statement"
    assert df.attrs["consolidated"] is True
    assert "2024-04-01" in df.attrs["period"]
    assert df.attrs["entity_id"] == "E00001"


def test_to_dataframe_roundtrip_value(sample_pl: FinancialStatement) -> None:
    """D-8: Decimal 値が float に劣化していないこと。"""
    df = sample_pl.to_dataframe()
    assert df["value"].iloc[0] == Decimal("45095325000000")


# ==========================================================================
# to_dict() テスト (TD-1 〜 TD-4)
# ==========================================================================


def test_to_dict_returns_list(sample_pl: FinancialStatement) -> None:
    """TD-1: to_dict() がリストを返すこと。"""
    result = sample_pl.to_dict()
    assert isinstance(result, list)
    assert len(result) == len(sample_pl.items)


def test_to_dict_keys(sample_pl: FinancialStatement) -> None:
    """TD-2: 各辞書のキーが to_dataframe のカラムと一致すること。"""
    result = sample_pl.to_dict()
    expected_keys = {"label_ja", "label_en", "value", "unit", "concept"}
    for row in result:
        assert set(row.keys()) == expected_keys


def test_to_dict_values(sample_pl: FinancialStatement) -> None:
    """TD-3: 値が正しく変換されていること。"""
    result = sample_pl.to_dict()
    assert result[0]["label_ja"] == "売上高"
    assert result[0]["value"] == Decimal("45095325000000")
    assert result[0]["concept"] == "NetSales"


def test_to_dict_empty(empty_pl: FinancialStatement) -> None:
    """TD-4: 空 statement で空リストが返ること。"""
    assert empty_pl.to_dict() == []


# ==========================================================================
# 遅延 import テスト (I-1, I-2)
# ==========================================================================


@pytest.mark.slow
def test_import_edinet_without_pandas() -> None:
    """I-1: pandas なしでも import edinet が成功すること。"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['pandas'] = None; import edinet; print('ok')",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


@pytest.mark.slow
def test_import_edinet_without_rich() -> None:
    """I-2: rich なしでも import edinet が成功すること。"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['rich'] = None; import edinet; print('ok')",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout

"""HTML 表示のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.display.html import to_html
from edinet.models.financial import FinancialStatement, LineItem, StatementType
from edinet.xbrl.contexts import DurationPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource
from edinet.xbrl.taxonomy.concept_sets import ConceptEntry, ConceptSet, StatementCategory

_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    """テスト用ラベルを生成する。"""
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _make_item(
    *,
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000"),
    label_ja: str = "売上高",
    order: int = 0,
) -> LineItem:
    """テスト用 LineItem を生成する。"""
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
        order=order,
    )


def _make_fs(*items: LineItem) -> FinancialStatement:
    """テスト用 FinancialStatement を生成する。"""
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)),
        items=items,
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


def _make_concept_set(entries: list[ConceptEntry]) -> ConceptSet:
    """テスト用 ConceptSet を生成する。"""
    return ConceptSet(
        role_uri="http://example.com/role/PL",
        category=StatementCategory.INCOME_STATEMENT,
        is_consolidated=True,
        concepts=tuple(entries),
        source_info="test",
    )


# ---------------------------------------------------------------------------
# to_html() のテスト
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestToHtml:
    """to_html() のテスト。"""

    def test_to_html_contains_table_tags(self) -> None:
        """基本的な HTML テーブル構造を含むこと。"""
        fs = _make_fs(_make_item())
        html = to_html(fs)

        assert "<table" in html
        assert "</table>" in html
        assert "<thead>" in html
        assert "</thead>" in html
        assert "<tbody>" in html
        assert "</tbody>" in html
        assert "<caption>" in html
        assert "科目" in html
        assert "金額" in html

    def test_to_html_abstract_row_has_class(self) -> None:
        """abstract 行が abstract CSS クラスを持つこと。"""
        entries = [
            ConceptEntry(
                concept="IncomeStatementAbstract",
                order=0, is_total=False, is_abstract=True, depth=0, href="",
            ),
            ConceptEntry(
                concept="NetSales",
                order=1, is_total=False, is_abstract=False, depth=1, href="",
            ),
        ]
        cs = _make_concept_set(entries)
        fs = _make_fs(_make_item())

        html = to_html(
            fs,
            concept_set=cs,
            abstract_labels={"IncomeStatementAbstract": "損益計算書"},
        )

        assert 'class="abstract"' in html

    def test_to_html_total_row_has_class(self) -> None:
        """total 行が total CSS クラスを持つこと。"""
        entries = [
            ConceptEntry(
                concept="NetSales",
                order=0, is_total=False, is_abstract=False, depth=0, href="",
            ),
            ConceptEntry(
                concept="GrossProfit",
                order=1, is_total=True, is_abstract=False, depth=0, href="",
            ),
        ]
        cs = _make_concept_set(entries)
        fs = _make_fs(
            _make_item(local_name="NetSales", label_ja="売上高"),
            _make_item(
                local_name="GrossProfit", label_ja="売上総利益",
                value=Decimal("300"), order=1,
            ),
        )

        html = to_html(fs, concept_set=cs)

        assert 'class="total"' in html

    def test_to_html_depth_indentation(self) -> None:
        """depth > 0 の行に padding-left スタイルが付くこと。"""
        entries = [
            ConceptEntry(
                concept="Heading",
                order=0, is_total=False, is_abstract=True, depth=0, href="",
            ),
            ConceptEntry(
                concept="NetSales",
                order=1, is_total=False, is_abstract=False, depth=2, href="",
            ),
        ]
        cs = _make_concept_set(entries)
        fs = _make_fs(_make_item())

        html = to_html(
            fs,
            concept_set=cs,
            abstract_labels={"Heading": "見出し"},
        )

        # depth=2 → padding-left:3.0em
        assert "padding-left:3.0em" in html

    def test_to_html_formats_decimal_with_commas(self) -> None:
        """Decimal 値が 3 桁カンマ区切りで表示されること。"""
        fs = _make_fs(
            _make_item(value=Decimal("1234567890")),
        )
        html = to_html(fs)

        assert "1,234,567,890" in html

    def test_to_html_escapes_html_in_labels(self) -> None:
        """ラベルに含まれる HTML 特殊文字がエスケープされること。"""
        fs = _make_fs(
            _make_item(label_ja="<script>alert('xss')</script>"),
        )
        html = to_html(fs)

        # 生の <script> タグが含まれないこと
        assert "<script>" not in html
        # エスケープされた形で含まれること
        assert "&lt;script&gt;" in html

    def test_to_html_empty_statement(self) -> None:
        """空の FinancialStatement でもエラーにならないこと。"""
        fs = _make_fs()
        html = to_html(fs)

        assert "<table" in html
        assert "</table>" in html

    def test_to_html_title_contains_statement_info(self) -> None:
        """タイトルに諸表種類と連結区分が含まれること。"""
        fs = _make_fs(_make_item())
        html = to_html(fs)

        assert "損益計算書" in html
        assert "連結" in html

    def test_to_html_none_value_renders_empty(self) -> None:
        """value=None の場合、金額セルが空文字列であること。"""
        fs = _make_fs(
            _make_item(value=None),
        )
        html = to_html(fs)

        # value=None は空文字列として表示（abstract でない通常行）
        assert '<td class="amount"></td>' in html


# ---------------------------------------------------------------------------
# FinancialStatement._repr_html_() のテスト
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestReprHtml:
    """FinancialStatement._repr_html_() のテスト。"""

    def test_repr_html_returns_string(self) -> None:
        """_repr_html_() が文字列を返すこと。"""
        fs = _make_fs(_make_item())
        result = fs._repr_html_()

        assert isinstance(result, str)
        assert "<table" in result

    def test_repr_html_with_concept_set(self) -> None:
        """_concept_set を持つ FinancialStatement で階層表示されること。"""
        entries = [
            ConceptEntry(
                concept="Heading",
                order=0, is_total=False, is_abstract=True, depth=0, href="",
            ),
            ConceptEntry(
                concept="NetSales",
                order=1, is_total=False, is_abstract=False, depth=1, href="",
            ),
        ]
        cs = _make_concept_set(entries)

        fs = FinancialStatement(
            statement_type=StatementType.INCOME_STATEMENT,
            period=DurationPeriod(
                start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            ),
            items=(_make_item(),),
            consolidated=True,
            entity_id="E00001",
            warnings_issued=(),
            _concept_set=cs,
        )

        result = fs._repr_html_()
        assert isinstance(result, str)
        assert "<table" in result
        # 階層表示 → abstract 行が存在する
        assert 'class="abstract"' in result

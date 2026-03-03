"""test_extract.py — extract_values() / extracted_to_dict() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from edinet.financial.extract import (
    ExtractedValue,
    extract_values,
    extracted_to_dict,
)
from edinet.financial.standards.canonical_keys import CK
from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

# ---------------------------------------------------------------------------
# テスト用定数
# ---------------------------------------------------------------------------

_NS_JPPFS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)
_NS_JPIGP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor"
)
_NS_JPCRP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)

_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
)
_CUR_INSTANT = InstantPeriod(instant=date(2025, 3, 31))


# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    """テスト用 LabelInfo を構築するヘルパー。"""
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _make_line_item(
    *,
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000000"),
    context_id: str = "CurrentYearDuration",
    period: DurationPeriod | InstantPeriod | None = None,
    label_ja: str = "売上高",
    label_en: str = "Net sales",
    order: int = 0,
    namespace_uri: str = _NS_JPPFS,
    is_nil: bool = False,
    unit_ref: str | None = "JPY",
) -> LineItem:
    """テスト用 LineItem を構築するヘルパー。"""
    if period is None:
        period = _CUR_DURATION
    return LineItem(
        concept=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref=unit_ref,
        decimals=-6 if isinstance(value, Decimal) else None,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=(),
        is_nil=is_nil,
        source_line=1,
        order=order,
    )


def _make_fs(
    *items: LineItem,
    statement_type: StatementType = StatementType.INCOME_STATEMENT,
    period: DurationPeriod | InstantPeriod | None = None,
) -> FinancialStatement:
    """テスト用 FinancialStatement を構築するヘルパー。"""
    if period is None:
        period = items[0].period if items else None
    return FinancialStatement(
        statement_type=statement_type,
        period=period,
        items=items,
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


# ---------------------------------------------------------------------------
# TestExtractValues
# ---------------------------------------------------------------------------


class TestExtractValues:
    """extract_values() のテスト。"""

    def test_extract_specific_keys(self) -> None:
        """指定した canonical key の値が正しく返る。"""
        fs = _make_fs(
            _make_line_item(
                local_name="NetSales",
                value=Decimal("1000000"),
                label_ja="売上高",
            ),
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("200000"),
                label_ja="営業利益",
                label_en="Operating income",
                order=1,
            ),
        )
        result = extract_values(fs, [CK.REVENUE, CK.OPERATING_INCOME])

        assert CK.REVENUE in result
        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("1000000")
        assert result[CK.OPERATING_INCOME] is not None
        assert result[CK.OPERATING_INCOME].value == Decimal("200000")

    def test_extract_missing_key_returns_none(self) -> None:
        """存在しない canonical key は None で返る。"""
        fs = _make_fs(
            _make_line_item(local_name="NetSales"),
        )
        result = extract_values(fs, [CK.REVENUE, CK.TOTAL_ASSETS])

        assert result[CK.REVENUE] is not None
        assert result[CK.TOTAL_ASSETS] is None

    def test_extract_all_keys(self) -> None:
        """keys=None で全マッピング可能科目を発見する。"""
        fs = _make_fs(
            _make_line_item(local_name="NetSales", value=Decimal("1000000")),
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("200000"),
                label_ja="営業利益",
                label_en="Operating income",
                order=1,
            ),
            # マッピングされない独自科目
            _make_line_item(
                local_name="CustomFilerItem",
                value=Decimal("50000"),
                label_ja="独自科目",
                label_en="Custom item",
                order=2,
            ),
        )
        result = extract_values(fs)

        # NetSales → revenue, OperatingIncome → operating_income
        assert "revenue" in result
        assert "operating_income" in result
        # CustomFilerItem はマッピングされない
        assert len(result) == 2

    def test_extract_preserves_item(self) -> None:
        """.item が元の LineItem と同一オブジェクトを参照する。"""
        item = _make_line_item(local_name="NetSales")
        fs = _make_fs(item)

        result = extract_values(fs, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].item is item

    def test_extract_empty_statement(self) -> None:
        """空の FinancialStatement で空辞書が返る。"""
        fs = _make_fs()

        result = extract_values(fs, [CK.REVENUE])

        assert result == {CK.REVENUE: None}

    def test_extract_empty_statement_all_keys(self) -> None:
        """空の FinancialStatement + keys=None で空辞書が返る。"""
        fs = _make_fs()

        result = extract_values(fs)

        assert result == {}

    def test_extract_ifrs_concepts(self) -> None:
        """IFRS の概念名でもマッチする。"""
        fs = _make_fs(
            _make_line_item(
                local_name="RevenueIFRS",
                value=Decimal("5000000"),
                label_ja="売上収益",
                label_en="Revenue",
                namespace_uri=_NS_JPIGP,
            ),
        )
        result = extract_values(fs, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("5000000")
        assert result[CK.REVENUE].item.local_name == "RevenueIFRS"

    def test_extract_usgaap_concepts(self) -> None:
        """US-GAAP の概念名でもマッチする。"""
        fs = _make_fs(
            _make_line_item(
                local_name="RevenuesUSGAAPSummaryOfBusinessResults",
                value=Decimal("8000000"),
                label_ja="売上高",
                label_en="Revenue",
                namespace_uri=_NS_JPCRP,
            ),
        )
        result = extract_values(fs, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("8000000")

    def test_extract_canonical_key_field(self) -> None:
        """ExtractedValue.canonical_key が正しく設定される。"""
        fs = _make_fs(
            _make_line_item(local_name="NetSales"),
        )
        result = extract_values(fs, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].canonical_key == "revenue"

    def test_extract_nil_value(self) -> None:
        """nil 値の科目も抽出される。"""
        fs = _make_fs(
            _make_line_item(
                local_name="NetSales", value=None, is_nil=True,
            ),
        )
        result = extract_values(fs, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value is None


# ---------------------------------------------------------------------------
# TestExtractedToDict
# ---------------------------------------------------------------------------


class TestExtractedToDict:
    """extracted_to_dict() のテスト。"""

    def test_basic_conversion(self) -> None:
        """ExtractedValue → {key: value} の変換が正しい。"""
        extracted = {
            "revenue": ExtractedValue(
                canonical_key="revenue",
                value=Decimal("1000000"),
                item=_make_line_item(),
            ),
            "operating_income": ExtractedValue(
                canonical_key="operating_income",
                value=Decimal("200000"),
                item=_make_line_item(
                    local_name="OperatingIncome",
                    label_ja="営業利益",
                ),
            ),
        }
        result = extracted_to_dict(extracted)

        assert result == {
            "revenue": Decimal("1000000"),
            "operating_income": Decimal("200000"),
        }

    def test_none_values(self) -> None:
        """None の ExtractedValue は None 値になる。"""
        extracted: dict[str, ExtractedValue | None] = {
            "revenue": ExtractedValue(
                canonical_key="revenue",
                value=Decimal("1000000"),
                item=_make_line_item(),
            ),
            "total_assets": None,
        }
        result = extracted_to_dict(extracted)

        assert result == {
            "revenue": Decimal("1000000"),
            "total_assets": None,
        }

    def test_empty_dict(self) -> None:
        """空辞書の変換。"""
        assert extracted_to_dict({}) == {}

"""test_summary.py — build_summary() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.financial.statements import Statements, build_statements
from edinet.financial.summary import build_summary
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import DimensionMember, DurationPeriod, InstantPeriod
from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType
from edinet.financial.standards.detect import (
    DetectedStandard,
    DetectionMethod,
    DetailLevel,
)
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

# テスト用名前空間
_NS_JPPFS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)
_NS_JPCRP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)
_NS_FILER = (
    "http://disclosure.edinet-fsa.go.jp/E00001/jpcrp/2025-11-01/"
    "E00001_jpcrp_cor"
)

# 共通期間
_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
)
_CUR_INSTANT = InstantPeriod(instant=date(2025, 3, 31))

# dimension
_SEGMENT_DIM_A = (
    DimensionMember(
        axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor}OperatingSegmentsAxis",
        member="{http://disclosure.edinet-fsa.go.jp/taxonomy/E00001/2025-11-01}SegmentAMember",
    ),
)
_SEGMENT_DIM_B = (
    DimensionMember(
        axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor}OperatingSegmentsAxis",
        member="{http://disclosure.edinet-fsa.go.jp/taxonomy/E00001/2025-11-01}SegmentBMember",
    ),
)


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


def _make_item(
    *,
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000000"),
    namespace_uri: str = _NS_JPPFS,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    label_ja: str = "売上高",
    label_en: str = "Net sales",
) -> LineItem:
    """テスト用 LineItem を構築するヘルパー。"""
    return LineItem(
        concept=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearDuration",
        period=_CUR_DURATION,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=False,
        source_line=1,
        order=order,
    )


def _make_dei(
    *,
    start: date | None = date(2024, 4, 1),
    end: date | None = date(2025, 3, 31),
    period_type: PeriodType | str | None = PeriodType.FY,
    accounting_standards: AccountingStandard | str | None = AccountingStandard.JAPAN_GAAP,
) -> DEI:
    """テスト用の DEI を構築するヘルパー。"""
    return DEI(
        edinet_code="E00001",
        fund_code=None,
        security_code="11110",
        filer_name_ja="テスト株式会社",
        filer_name_en="Test Corp.",
        fund_name_ja=None,
        fund_name_en=None,
        cabinet_office_ordinance="企業内容等の開示に関する内閣府令",
        document_type="第三号様式",
        accounting_standards=accounting_standards,
        has_consolidated=True,
        industry_code_consolidated=None,
        industry_code_non_consolidated=None,
        current_fiscal_year_start_date=start,
        current_period_end_date=end,
        type_of_current_period=period_type,
        current_fiscal_year_end_date=end,
        previous_fiscal_year_start_date=None,
        comparative_period_end_date=None,
        previous_fiscal_year_end_date=None,
        next_fiscal_year_start_date=None,
        end_date_of_next_semi_annual_period=None,
        number_of_submission=1,
        amendment_flag=False,
        identification_of_document_subject_to_amendment=None,
        report_amendment_flag=None,
        xbrl_amendment_flag=None,
    )


def _make_statements_with_dei(
    items: tuple[LineItem, ...],
    dei: DEI | None = None,
    detected: DetectedStandard | None = None,
) -> Statements:
    """DEI 付きの Statements を直接構築するヘルパー。"""
    return Statements(
        _items=items,
        _detected_standard=detected,
        _facts=None,
        _contexts=None,
        _taxonomy_root=None,
        _industry_code=None,
        _dei=dei,
    )


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestSummaryTotalItems:
    """total_items のテスト。"""

    def test_summary_total_items(self) -> None:
        """total_items が LineItem 数と一致すること。"""
        items = (
            _make_item(local_name="NetSales", order=0),
            _make_item(local_name="CostOfSales", order=1, label_ja="売上原価"),
            _make_item(local_name="GrossProfit", order=2, label_ja="売上総利益"),
        )
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.total_items == 3


@pytest.mark.small
@pytest.mark.unit
class TestSummaryStandardRatio:
    """standard_item_count / custom_item_count / standard_item_ratio のテスト。"""

    def test_summary_standard_ratio_all_standard(self) -> None:
        """全て標準タクソノミの場合、比率が 1.0 になること。"""
        items = (
            _make_item(namespace_uri=_NS_JPPFS, order=0),
            _make_item(namespace_uri=_NS_JPCRP, order=1, local_name="X", label_ja="X"),
        )
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.standard_item_count == 2
        assert summary.custom_item_count == 0
        assert summary.standard_item_ratio == 1.0

    def test_summary_standard_ratio_mixed(self) -> None:
        """標準/提出者別が混在する場合の比率。"""
        items = (
            _make_item(namespace_uri=_NS_JPPFS, order=0),
            _make_item(namespace_uri=_NS_FILER, order=1, local_name="Custom1", label_ja="独自科目"),
        )
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.standard_item_count == 1
        assert summary.custom_item_count == 1
        assert summary.standard_item_ratio == pytest.approx(0.5)


@pytest.mark.small
@pytest.mark.unit
class TestSummaryNamespaceCounts:
    """namespace_counts のテスト。"""

    def test_summary_namespace_counts(self) -> None:
        """モジュールグループ別にカウントされること。"""
        items = (
            _make_item(namespace_uri=_NS_JPPFS, order=0),
            _make_item(namespace_uri=_NS_JPPFS, order=1, local_name="A", label_ja="A"),
            _make_item(namespace_uri=_NS_JPCRP, order=2, local_name="B", label_ja="B"),
            _make_item(namespace_uri=_NS_FILER, order=3, local_name="C", label_ja="C"),
        )
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.namespace_counts.get("jppfs") == 2
        assert summary.namespace_counts.get("jpcrp") == 1
        # 提出者別タクソノミは module_group が None → "その他"
        assert summary.namespace_counts.get("その他") == 1


@pytest.mark.small
@pytest.mark.unit
class TestSummaryEmpty:
    """空の Statements に対するテスト。"""

    def test_summary_empty_statements(self) -> None:
        """空の Statements でゼロ除算せずに正しく返ること。"""
        stmts = build_statements(())
        summary = build_summary(stmts)
        assert summary.total_items == 0
        assert summary.standard_item_count == 0
        assert summary.custom_item_count == 0
        assert summary.standard_item_ratio == 0.0
        assert summary.namespace_counts == {}
        assert summary.segment_count == 0
        assert summary.accounting_standard == "不明"
        assert summary.period_start is None
        assert summary.period_end is None
        assert summary.period_type is None


@pytest.mark.small
@pytest.mark.unit
class TestSummaryPeriodInfo:
    """DEI からの期間情報取得テスト。"""

    def test_summary_period_info(self) -> None:
        """DEI の期間情報が正しく取得されること。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        detected = DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        items = (_make_item(),)
        stmts = _make_statements_with_dei(items, dei=dei, detected=detected)
        summary = build_summary(stmts)

        assert summary.period_start == date(2024, 4, 1)
        assert summary.period_end == date(2025, 3, 31)
        assert summary.period_type == "FY"
        assert summary.accounting_standard == "Japan GAAP"

    def test_summary_no_dei(self) -> None:
        """DEI が None の場合、期間情報が None になること。"""
        items = (_make_item(),)
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.period_start is None
        assert summary.period_end is None
        assert summary.period_type is None

    def test_summary_hy_period_type(self) -> None:
        """半期の period_type が正しく取得されること。"""
        dei = _make_dei(period_type=PeriodType.HY)
        items = (_make_item(),)
        stmts = _make_statements_with_dei(items, dei=dei)
        summary = build_summary(stmts)
        assert summary.period_type == "HY"


@pytest.mark.small
@pytest.mark.unit
class TestSummarySegmentCount:
    """segment_count のテスト。"""

    def test_summary_segment_count(self) -> None:
        """ディメンション付きコンテキストの種類数が正しくカウントされること。"""
        items = (
            _make_item(order=0),  # dimension なし
            _make_item(order=1, local_name="A", label_ja="A", dimensions=_SEGMENT_DIM_A),
            _make_item(order=2, local_name="B", label_ja="B", dimensions=_SEGMENT_DIM_A),  # 同じ dim
            _make_item(order=3, local_name="C", label_ja="C", dimensions=_SEGMENT_DIM_B),  # 別の dim
        )
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.segment_count == 2  # DIM_A と DIM_B の 2 種

    def test_summary_no_segments(self) -> None:
        """ディメンションなしの場合は segment_count が 0 になること。"""
        items = (_make_item(),)
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.segment_count == 0


@pytest.mark.small
@pytest.mark.unit
class TestSummaryConsolidated:
    """連結/個別判定のテスト。"""

    def test_summary_has_consolidated(self) -> None:
        """連結データの有無が正しく判定されること。"""
        items = (_make_item(),)  # dimension なし = 連結
        stmts = build_statements(items)
        summary = build_summary(stmts)
        assert summary.has_consolidated is True

"""XBRL ディメンション解析サブパッケージ。"""

from edinet.financial.dimensions.fiscal_year import (
    FiscalYearInfo as FiscalYearInfo,
    detect_fiscal_year as detect_fiscal_year,
)
from edinet.financial.dimensions.period_variants import (
    PeriodClassification as PeriodClassification,
    classify_periods as classify_periods,
)
from edinet.financial.dimensions.segments import (
    DimensionAxisSummary as DimensionAxisSummary,
    SegmentData as SegmentData,
    SegmentItem as SegmentItem,
    extract_segments as extract_segments,
    list_dimension_axes as list_dimension_axes,
)

__all__ = [
    "PeriodClassification",
    "classify_periods",
    # Wave 6: 決算期判定 (L6)
    "FiscalYearInfo",
    "detect_fiscal_year",
    # Wave 7: セグメント (L6)
    "DimensionAxisSummary",
    "SegmentItem",
    "SegmentData",
    "list_dimension_axes",
    "extract_segments",
]

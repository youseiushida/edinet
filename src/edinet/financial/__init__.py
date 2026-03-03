"""財務諸表組み立てサブパッケージ。

有報系 docType 専用の財務諸表ロジック（会計基準の名寄せ、業種別科目、三表分類）を提供する。
汎用 XBRL パースは ``edinet.xbrl`` パッケージを使用する。
"""

from edinet.financial.dimensions.fiscal_year import (
    FiscalYearInfo as FiscalYearInfo,
    detect_fiscal_year as detect_fiscal_year,
)
from edinet.financial.dimensions.period_variants import (
    PeriodClassification as PeriodClassification,
    classify_periods as classify_periods,
)
from edinet.financial.standards import (
    DetectedStandard as DetectedStandard,
    detect_accounting_standard as detect_accounting_standard,
)
from edinet.financial.statements import (
    Statements as Statements,
    build_statements as build_statements,
)
from edinet.financial.diff import (
    DiffItem as DiffItem,
    DiffResult as DiffResult,
    diff_periods as diff_periods,
    diff_revisions as diff_revisions,
)
from edinet.financial.dimensions.segments import (
    DimensionAxisSummary as DimensionAxisSummary,
    SegmentData as SegmentData,
    SegmentItem as SegmentItem,
    extract_segments as extract_segments,
    list_dimension_axes as list_dimension_axes,
)
from edinet.financial.notes.employees import (
    EmployeeInfo as EmployeeInfo,
    extract_employee_info as extract_employee_info,
)
from edinet.financial.extract import (
    ExtractedValue as ExtractedValue,
    extract_values as extract_values,
    extracted_to_dict as extracted_to_dict,
)
from edinet.financial.summary import (
    FilingSummary as FilingSummary,
    build_summary as build_summary,
)

__all__ = [
    "Statements",
    "build_statements",
    "DetectedStandard",
    "detect_accounting_standard",
    "PeriodClassification",
    "classify_periods",
    "FiscalYearInfo",
    "detect_fiscal_year",
    # Wave 7: 差分比較 (L8)
    "DiffItem",
    "DiffResult",
    "diff_revisions",
    "diff_periods",
    # Wave 7: セグメント (L6)
    "DimensionAxisSummary",
    "SegmentItem",
    "SegmentData",
    "list_dimension_axes",
    "extract_segments",
    # 正規化キー抽出
    "ExtractedValue",
    "extract_values",
    "extracted_to_dict",
    # Wave 7: サマリー (L4)
    "FilingSummary",
    "build_summary",
    # Wave 7: 従業員情報 (L4)
    "EmployeeInfo",
    "extract_employee_info",
]

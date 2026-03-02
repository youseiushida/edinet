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

__all__ = [
    "Statements",
    "build_statements",
    "DetectedStandard",
    "detect_accounting_standard",
    "PeriodClassification",
    "classify_periods",
    "FiscalYearInfo",
    "detect_fiscal_year",
]

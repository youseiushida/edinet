"""XBRL 関連機能を提供するサブパッケージ。"""

from __future__ import annotations

from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType, extract_dei
from edinet.xbrl.facts import build_line_items
from edinet.xbrl.ixbrl_parser import merge_ixbrl_results, parse_ixbrl_facts
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.taxonomy.custom import (
    CustomDetectionResult,
    detect_custom_items,
    find_custom_concepts,
)
from edinet.xbrl.text import (
    SectionMap,
    TextBlock,
    build_section_map,
    clean_html,
    extract_text_blocks,
)
from edinet.xbrl.units import DivideMeasure, Measure, SimpleMeasure, StructuredUnit, structure_units
from edinet.xbrl.validation.calc_check import CalcValidationResult, validate_calculations

# financial.* からの再エクスポート（後方互換）。
# 循環インポート防止のため遅延読み込みにする。
# (financial → xbrl.dei → xbrl.__init__ → financial の循環を回避)
_LAZY_FINANCIAL_EXPORTS: dict[str, tuple[str, str]] = {
    "Statements": ("edinet.financial.statements", "Statements"),
    "build_statements": ("edinet.financial.statements", "build_statements"),
    "DetectedStandard": ("edinet.financial.standards", "DetectedStandard"),
    "detect_accounting_standard": ("edinet.financial.standards", "detect_accounting_standard"),
    "FiscalYearInfo": ("edinet.financial.dimensions.fiscal_year", "FiscalYearInfo"),
    "detect_fiscal_year": ("edinet.financial.dimensions.fiscal_year", "detect_fiscal_year"),
}


def __getattr__(name: str) -> object:
    if name in _LAZY_FINANCIAL_EXPORTS:
        module_path, attr = _LAZY_FINANCIAL_EXPORTS[name]
        import importlib

        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value  # 次回以降はキャッシュ
        return value
    raise AttributeError(f"module 'edinet.xbrl' has no attribute {name!r}")

__all__ = [
    "parse_xbrl_facts",
    "parse_ixbrl_facts",
    "merge_ixbrl_results",
    "structure_contexts",
    "ContextCollection",
    "TaxonomyResolver",
    "build_line_items",
    "build_statements",
    "Statements",
    "DEI",
    "AccountingStandard",
    "PeriodType",
    "extract_dei",
    "DetectedStandard",
    "detect_accounting_standard",
    "SimpleMeasure",
    "DivideMeasure",
    "Measure",
    "StructuredUnit",
    "structure_units",
    # Wave 6: 拡張科目検出 (L4) + Wave 7: L5 拡張
    "CustomDetectionResult",
    "detect_custom_items",
    "find_custom_concepts",
    # Wave 6: 計算バリデーション (L5)
    "CalcValidationResult",
    "validate_calculations",
    # Wave 6: 決算期判定 (L6)
    "FiscalYearInfo",
    "detect_fiscal_year",
    # Wave 7: テキストブロック (L1)
    "TextBlock",
    "extract_text_blocks",
    "SectionMap",
    "build_section_map",
    "clean_html",
]

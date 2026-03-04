"""edinet パッケージの公開 API。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet._config import configure as configure
    from edinet._http import aclose as aclose
    from edinet.api.cache import CacheInfo as CacheInfo
    from edinet.api.cache import cache_info as cache_info
    from edinet.api.cache import clear_cache as clear_cache
    from edinet.models.company import Company as Company
    from edinet.models.doc_types import DocType as DocType
    from edinet.models.filing import Filing as Filing
    from edinet.models.financial import FinancialStatement as FinancialStatement
    from edinet.models.financial import LineItem as LineItem
    from edinet.models.revision import RevisionChain as RevisionChain
    from edinet.models.revision import build_revision_chain as build_revision_chain
    from edinet.public_api import adocuments as adocuments
    from edinet.public_api import documents as documents
    from edinet.financial.dimensions.fiscal_year import FiscalYearInfo as FiscalYearInfo
    from edinet.financial.dimensions.fiscal_year import (
        detect_fiscal_year as detect_fiscal_year,
    )
    from edinet.financial.statements import Statements as Statements
    from edinet.xbrl.taxonomy.custom import (
        CustomDetectionResult as CustomDetectionResult,
    )
    from edinet.xbrl.taxonomy.custom import (
        detect_custom_items as detect_custom_items,
    )
    from edinet.xbrl.taxonomy.custom import (
        find_custom_concepts as find_custom_concepts,
    )
    from edinet.xbrl.validation.calc_check import (
        CalcValidationResult as CalcValidationResult,
    )
    from edinet.xbrl.validation.calc_check import (
        validate_calculations as validate_calculations,
    )
    from edinet.financial.diff import DiffResult as DiffResult
    from edinet.financial.diff import diff_periods as diff_periods
    from edinet.financial.diff import diff_revisions as diff_revisions
    from edinet.financial.dimensions.segments import (
        extract_segments as extract_segments,
    )
    from edinet.financial.dimensions.segments import (
        list_dimension_axes as list_dimension_axes,
    )
    from edinet.financial.summary import FilingSummary as FilingSummary
    from edinet.financial.summary import build_summary as build_summary
    from edinet.exceptions import (
        EdinetError as EdinetError,
        EdinetConfigError as EdinetConfigError,
        EdinetAPIError as EdinetAPIError,
        EdinetParseError as EdinetParseError,
        EdinetWarning as EdinetWarning,
    )
    from edinet.financial.extract import (
        ExtractedValue as ExtractedValue,
        extract_values as extract_values,
        extracted_to_dict as extracted_to_dict,
    )
    from edinet.financial.standards.canonical_keys import CK as CK
    from edinet.financial.mapper import (
        summary_mapper as summary_mapper,
        statement_mapper as statement_mapper,
        definition_mapper as definition_mapper,
        calc_mapper as calc_mapper,
        dict_mapper as dict_mapper,
    )

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # --- 設定・ユーティリティ ---
    "configure": ("edinet._config", "configure"),
    "documents": ("edinet.public_api", "documents"),
    "adocuments": ("edinet.public_api", "adocuments"),
    "aclose": ("edinet._http", "aclose"),
    # --- コアモデル ---
    "Company": ("edinet.models.company", "Company"),
    "Filing": ("edinet.models.filing", "Filing"),
    "DocType": ("edinet.models.doc_types", "DocType"),
    "Statements": ("edinet.financial.statements", "Statements"),
    "FinancialStatement": ("edinet.models.financial", "FinancialStatement"),
    "LineItem": ("edinet.models.financial", "LineItem"),
    # --- Wave 6: キャッシュ (L2) ---
    "clear_cache": ("edinet.api.cache", "clear_cache"),
    "cache_info": ("edinet.api.cache", "cache_info"),
    "CacheInfo": ("edinet.api.cache", "CacheInfo"),
    # --- Wave 6: 訂正チェーン (L3) ---
    "build_revision_chain": ("edinet.models.revision", "build_revision_chain"),
    "RevisionChain": ("edinet.models.revision", "RevisionChain"),
    # --- Wave 6: 拡張科目検出 (L4) ---
    "detect_custom_items": ("edinet.xbrl.taxonomy.custom", "detect_custom_items"),
    "CustomDetectionResult": (
        "edinet.xbrl.taxonomy.custom",
        "CustomDetectionResult",
    ),
    # --- Wave 6: 計算バリデーション (L5) ---
    "validate_calculations": (
        "edinet.xbrl.validation.calc_check",
        "validate_calculations",
    ),
    "CalcValidationResult": (
        "edinet.xbrl.validation.calc_check",
        "CalcValidationResult",
    ),
    # --- Wave 6: 決算期判定 (L6) ---
    "detect_fiscal_year": (
        "edinet.financial.dimensions.fiscal_year",
        "detect_fiscal_year",
    ),
    "FiscalYearInfo": ("edinet.financial.dimensions.fiscal_year", "FiscalYearInfo"),
    # --- Wave 7: 拡張科目検出の拡張 (L5) ---
    "find_custom_concepts": (
        "edinet.xbrl.taxonomy.custom",
        "find_custom_concepts",
    ),
    # --- Wave 7: 差分比較 (L8) ---
    "diff_revisions": ("edinet.financial.diff", "diff_revisions"),
    "diff_periods": ("edinet.financial.diff", "diff_periods"),
    "DiffResult": ("edinet.financial.diff", "DiffResult"),
    # --- Wave 7: セグメント (L6) ---
    "extract_segments": (
        "edinet.financial.dimensions.segments",
        "extract_segments",
    ),
    "list_dimension_axes": (
        "edinet.financial.dimensions.segments",
        "list_dimension_axes",
    ),
    # --- Wave 7: サマリー (L4) ---
    "build_summary": ("edinet.financial.summary", "build_summary"),
    "FilingSummary": ("edinet.financial.summary", "FilingSummary"),
    # --- 例外 ---
    "EdinetError": ("edinet.exceptions", "EdinetError"),
    "EdinetConfigError": ("edinet.exceptions", "EdinetConfigError"),
    "EdinetAPIError": ("edinet.exceptions", "EdinetAPIError"),
    "EdinetParseError": ("edinet.exceptions", "EdinetParseError"),
    "EdinetWarning": ("edinet.exceptions", "EdinetWarning"),
    # --- 正規化キー抽出 ---
    "CK": ("edinet.financial.standards.canonical_keys", "CK"),
    "extract_values": ("edinet.financial.extract", "extract_values"),
    "extracted_to_dict": ("edinet.financial.extract", "extracted_to_dict"),
    "ExtractedValue": ("edinet.financial.extract", "ExtractedValue"),
    # --- マッパー ---
    "summary_mapper": ("edinet.financial.mapper", "summary_mapper"),
    "statement_mapper": ("edinet.financial.mapper", "statement_mapper"),
    "definition_mapper": ("edinet.financial.mapper", "definition_mapper"),
    "calc_mapper": ("edinet.financial.mapper", "calc_mapper"),
    "dict_mapper": ("edinet.financial.mapper", "dict_mapper"),
}


def __getattr__(name: str):
    """公開シンボルを遅延ロードする。

    Args:
        name: 取得対象の属性名。

    Returns:
        遅延ロードされた属性。

    Raises:
        AttributeError: 公開対象外の属性名が指定された場合。
    """
    module_and_attr = _LAZY_EXPORTS.get(name)
    if module_and_attr is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = module_and_attr
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = [
    # 設定・ユーティリティ
    "configure",
    "documents",
    "adocuments",
    "aclose",
    # コアモデル
    "Company",
    "Filing",
    "DocType",
    "Statements",
    "FinancialStatement",
    "LineItem",
    # Wave 6: キャッシュ (L2)
    "clear_cache",
    "cache_info",
    "CacheInfo",
    # Wave 6: 訂正チェーン (L3)
    "build_revision_chain",
    "RevisionChain",
    # Wave 6: 拡張科目検出 (L4)
    "detect_custom_items",
    "CustomDetectionResult",
    # Wave 6: 計算バリデーション (L5)
    "validate_calculations",
    "CalcValidationResult",
    # Wave 6: 決算期判定 (L6)
    "detect_fiscal_year",
    "FiscalYearInfo",
    # Wave 7: 拡張科目検出の拡張 (L5)
    "find_custom_concepts",
    # Wave 7: 差分比較 (L8)
    "diff_revisions",
    "diff_periods",
    "DiffResult",
    # Wave 7: セグメント (L6)
    "extract_segments",
    "list_dimension_axes",
    # Wave 7: サマリー (L4)
    "build_summary",
    "FilingSummary",
    # 例外
    "EdinetError",
    "EdinetConfigError",
    "EdinetAPIError",
    "EdinetParseError",
    "EdinetWarning",
    # 正規化キー抽出
    "CK",
    "extract_values",
    "extracted_to_dict",
    "ExtractedValue",
    # マッパー
    "summary_mapper",
    "statement_mapper",
    "definition_mapper",
    "calc_mapper",
    "dict_mapper",
]

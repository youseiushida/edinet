"""ドメインオブジェクト → dict 行（Parquet 行）への変換。"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal
from typing import Any

from edinet.models.filing import Filing
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import (
    InstantPeriod,
    StructuredContext,
)
from edinet.financial.standards.detect import DetectedStandard
from edinet.xbrl.dei import DEI
from edinet.xbrl.linkbase.calculation import CalculationLinkbase
from edinet.xbrl.linkbase.definition import DefinitionTree  # noqa: F401

_TEXTBLOCK_SUFFIX = "TextBlock"


def is_text_block(local_name: str) -> bool:
    """TextBlock 系の Fact かどうかを判定する。

    Args:
        local_name: 概念のローカル名。

    Returns:
        ``True`` なら TextBlock。
    """
    return local_name.endswith(_TEXTBLOCK_SUFFIX)


# Filing の computed_field 名（model_dump から除外する）
_COMPUTED_FIELDS = frozenset(
    {"doc_type", "filing_date", "ticker", "doc_type_label_ja"}
)


def serialize_filing(filing: Filing) -> dict[str, Any]:
    """Filing を dict 行に変換する。

    Args:
        filing: Filing オブジェクト。

    Returns:
        Parquet 行用の辞書。computed_field は除外される。
    """
    row = filing.model_dump()
    for key in _COMPUTED_FIELDS:
        row.pop(key, None)
    return row


def serialize_line_item(item: LineItem, doc_id: str) -> dict[str, Any]:
    """LineItem を dict 行に変換する。

    Args:
        item: LineItem オブジェクト。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書。
    """
    # value 型判別
    if isinstance(item.value, Decimal):
        value_numeric = str(item.value)
        value_text = None
        value_type = "decimal"
    elif isinstance(item.value, str):
        value_numeric = None
        value_text = item.value
        value_type = "str"
    else:
        value_numeric = None
        value_text = None
        value_type = "none"

    # decimals
    if item.decimals == "INF":
        decimals_int = None
        decimals_inf = True
    elif item.decimals is not None:
        decimals_int = item.decimals
        decimals_inf = False
    else:
        decimals_int = None
        decimals_inf = False

    # period
    period = item.period
    if isinstance(period, InstantPeriod):
        period_type = "instant"
        period_instant = period.instant
        period_start = None
        period_end = None
    else:
        period_type = "duration"
        period_instant = None
        period_start = period.start_date
        period_end = period.end_date

    # dimensions
    if item.dimensions:
        dims = [{"axis": d.axis, "member": d.member} for d in item.dimensions]
        dimensions_json = json.dumps(dims, ensure_ascii=False)
    else:
        dimensions_json = None

    return {
        "doc_id": doc_id,
        "concept": item.concept,
        "namespace_uri": item.namespace_uri,
        "local_name": item.local_name,
        "label_ja_text": item.label_ja.text,
        "label_ja_role": item.label_ja.role,
        "label_ja_lang": item.label_ja.lang,
        "label_ja_source": item.label_ja.source.value,
        "label_en_text": item.label_en.text,
        "label_en_role": item.label_en.role,
        "label_en_lang": item.label_en.lang,
        "label_en_source": item.label_en.source.value,
        "value_numeric": value_numeric,
        "value_text": value_text,
        "value_type": value_type,
        "unit_ref": item.unit_ref,
        "decimals_int": decimals_int,
        "decimals_inf": decimals_inf,
        "context_id": item.context_id,
        "period_type": period_type,
        "period_instant": period_instant,
        "period_start": period_start,
        "period_end": period_end,
        "entity_id": item.entity_id,
        "dimensions_json": dimensions_json,
        "is_nil": item.is_nil,
        "source_line": item.source_line,
        "order": item.order,
    }


def serialize_context(ctx: StructuredContext, doc_id: str) -> dict[str, Any]:
    """StructuredContext を dict 行に変換する。

    Args:
        ctx: StructuredContext オブジェクト。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書。
    """
    period = ctx.period
    if isinstance(period, InstantPeriod):
        period_type = "instant"
        period_instant = period.instant
        period_start = None
        period_end = None
    else:
        period_type = "duration"
        period_instant = None
        period_start = period.start_date
        period_end = period.end_date

    if ctx.dimensions:
        dims = [{"axis": d.axis, "member": d.member} for d in ctx.dimensions]
        dimensions_json = json.dumps(dims, ensure_ascii=False)
    else:
        dimensions_json = None

    return {
        "doc_id": doc_id,
        "context_id": ctx.context_id,
        "period_type": period_type,
        "period_instant": period_instant,
        "period_start": period_start,
        "period_end": period_end,
        "entity_id": ctx.entity_id,
        "entity_scheme": ctx.entity_scheme,
        "dimensions_json": dimensions_json,
        "source_line": ctx.source_line,
    }


def _serialize_enum_or_str(val: Any) -> str | None:
    """Enum は .value、str はそのまま、None は None を返す。"""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    # AccountingStandard, PeriodType は str enum
    return val.value if hasattr(val, "value") else str(val)


def _serialize_date(val: datetime.date | None) -> datetime.date | None:
    """date をそのまま返す（型ヒント明示用）。"""
    return val


def serialize_dei(
    dei: DEI,
    doc_id: str,
    *,
    detected_standard: DetectedStandard | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    """DEI を dict 行に変換する。

    Args:
        dei: DEI オブジェクト。
        doc_id: 対応する Filing の doc_id。
        detected_standard: 永続化する DetectedStandard（DEI のみでは
            復元できない名前空間フォールバック判別結果を保持するため）。

    Returns:
        Parquet 行用の辞書。Enum は .value 文字列で保存。
    """
    row: dict[str, Any] = {
        "doc_id": doc_id,
        "edinet_code": dei.edinet_code,
        "fund_code": dei.fund_code,
        "security_code": dei.security_code,
        "filer_name_ja": dei.filer_name_ja,
        "filer_name_en": dei.filer_name_en,
        "fund_name_ja": dei.fund_name_ja,
        "fund_name_en": dei.fund_name_en,
        "cabinet_office_ordinance": dei.cabinet_office_ordinance,
        "document_type": dei.document_type,
        "accounting_standards": _serialize_enum_or_str(dei.accounting_standards),
        "has_consolidated": dei.has_consolidated,
        "industry_code_consolidated": dei.industry_code_consolidated,
        "industry_code_non_consolidated": dei.industry_code_non_consolidated,
        "current_fiscal_year_start_date": _serialize_date(
            dei.current_fiscal_year_start_date
        ),
        "current_period_end_date": _serialize_date(dei.current_period_end_date),
        "type_of_current_period": _serialize_enum_or_str(
            dei.type_of_current_period
        ),
        "current_fiscal_year_end_date": _serialize_date(
            dei.current_fiscal_year_end_date
        ),
        "previous_fiscal_year_start_date": _serialize_date(
            dei.previous_fiscal_year_start_date
        ),
        "comparative_period_end_date": _serialize_date(
            dei.comparative_period_end_date
        ),
        "previous_fiscal_year_end_date": _serialize_date(
            dei.previous_fiscal_year_end_date
        ),
        "next_fiscal_year_start_date": _serialize_date(
            dei.next_fiscal_year_start_date
        ),
        "end_date_of_next_semi_annual_period": _serialize_date(
            dei.end_date_of_next_semi_annual_period
        ),
        "number_of_submission": dei.number_of_submission,
        "amendment_flag": dei.amendment_flag,
        "identification_of_document_subject_to_amendment": (
            dei.identification_of_document_subject_to_amendment
        ),
        "report_amendment_flag": dei.report_amendment_flag,
        "xbrl_amendment_flag": dei.xbrl_amendment_flag,
    }
    # source_path を同梱（Statements レベルのトレーサビリティ）
    row["source_path"] = source_path
    # DetectedStandard を同梱（DEI のみでは復元できないケース対策）
    if detected_standard is not None:
        row["detected_standard"] = _serialize_enum_or_str(
            detected_standard.standard
        )
        row["detected_method"] = detected_standard.method.value
        row["detected_detail_level"] = (
            detected_standard.detail_level.value
            if detected_standard.detail_level is not None
            else None
        )
        row["detected_has_consolidated"] = detected_standard.has_consolidated
        row["detected_period_type"] = _serialize_enum_or_str(
            detected_standard.period_type
        )
    return row


def serialize_calc_edges(
    calc_linkbase: CalculationLinkbase, doc_id: str
) -> list[dict[str, Any]]:
    """CalculationLinkbase を dict 行リストに変換する。

    Args:
        calc_linkbase: CalculationLinkbase オブジェクト。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書リスト。
    """
    rows: list[dict[str, Any]] = []
    for tree in calc_linkbase.trees.values():
        for arc in tree.arcs:
            rows.append(
                {
                    "doc_id": doc_id,
                    "role_uri": arc.role_uri,
                    "parent": arc.parent,
                    "child": arc.child,
                    "parent_href": arc.parent_href,
                    "child_href": arc.child_href,
                    "weight": arc.weight,
                    "order": arc.order,
                }
            )
    return rows


def serialize_def_parents(
    definition_linkbase: dict[str, DefinitionTree] | None,
    doc_id: str,
) -> list[dict[str, Any]]:
    """DefinitionLinkbase → parent_index → dict 行リストに変換する。

    Args:
        definition_linkbase: parse_definition_linkbase() の戻り値。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書リスト。
    """
    from edinet.xbrl.taxonomy.custom import _build_parent_index

    parent_index = _build_parent_index(definition_linkbase)
    rows: list[dict[str, Any]] = []
    for child_concept, parent_concept in parent_index.items():
        rows.append(
            {
                "doc_id": doc_id,
                "child_concept": child_concept,
                "parent_standard_concept": parent_concept,
            }
        )
    return rows

"""dict 行（Parquet 行）→ ドメインオブジェクトへの復元。"""

from __future__ import annotations

import datetime
import json
import math
from collections import defaultdict
from decimal import Decimal
from typing import Any

from edinet.financial.standards.detect import (
    DetectedStandard,
    DetectionMethod,
    DetailLevel,
    detect_from_dei,
)
from edinet.financial.statements import Statements
from edinet.models.filing import Filing
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
)
from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType
from edinet.xbrl.linkbase.calculation import (
    CalculationArc,
    CalculationLinkbase,
    CalculationTree,
)
from edinet.xbrl.taxonomy import LabelInfo, LabelSource


def deserialize_filing(row: dict[str, Any]) -> Filing:
    """dict 行から Filing を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        Filing オブジェクト。computed_field は自動再計算される。
    """
    return Filing.model_validate(row)


def _parse_date(val: Any) -> datetime.date | None:
    """date 型またはその文字列表現を datetime.date に変換する。"""
    if val is None:
        return None
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        return datetime.date.fromisoformat(val)
    return None


def _parse_dimensions(dims_json: str | None) -> tuple[DimensionMember, ...]:
    """JSON 文字列から DimensionMember タプルを復元する。"""
    if not dims_json:
        return ()
    dims = json.loads(dims_json)
    return tuple(DimensionMember(axis=d["axis"], member=d["member"]) for d in dims)


def _parse_period(
    row: dict[str, Any],
) -> InstantPeriod | DurationPeriod:
    """行データから Period を復元する。"""
    if row["period_type"] == "instant":
        return InstantPeriod(instant=_parse_date(row["period_instant"]))
    return DurationPeriod(
        start_date=_parse_date(row["period_start"]),
        end_date=_parse_date(row["period_end"]),
    )


def deserialize_line_item(row: dict[str, Any]) -> LineItem:
    """dict 行から LineItem を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        LineItem オブジェクト。
    """
    # value
    vtype = row["value_type"]
    if vtype == "decimal":
        value: Decimal | str | None = Decimal(row["value_numeric"])
    elif vtype == "str":
        value = row["value_text"]
    else:
        value = None

    # decimals
    if row.get("decimals_inf"):
        decimals: int | str | None = "INF"
    elif row.get("decimals_int") is not None:
        decimals = int(row["decimals_int"])
    else:
        decimals = None

    return LineItem(
        concept=row["concept"],
        namespace_uri=row["namespace_uri"],
        local_name=row["local_name"],
        label_ja=LabelInfo(
            text=row["label_ja_text"],
            role=row["label_ja_role"],
            lang=row["label_ja_lang"],
            source=LabelSource(row["label_ja_source"]),
        ),
        label_en=LabelInfo(
            text=row["label_en_text"],
            role=row["label_en_role"],
            lang=row["label_en_lang"],
            source=LabelSource(row["label_en_source"]),
        ),
        value=value,
        unit_ref=row.get("unit_ref"),
        decimals=decimals,
        context_id=row["context_id"],
        period=_parse_period(row),
        entity_id=row["entity_id"],
        dimensions=_parse_dimensions(row.get("dimensions_json")),
        is_nil=bool(row.get("is_nil", False)),
        source_line=_safe_int(row.get("source_line")),
        order=int(row["order"]),
    )


def deserialize_context(row: dict[str, Any]) -> StructuredContext:
    """dict 行から StructuredContext を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        StructuredContext オブジェクト。
    """
    return StructuredContext(
        context_id=row["context_id"],
        period=_parse_period(row),
        entity_id=row["entity_id"],
        dimensions=_parse_dimensions(row.get("dimensions_json")),
        source_line=_safe_int(row.get("source_line")),
        entity_scheme=row.get("entity_scheme"),
    )


def _safe_int(val: Any) -> int | None:
    """None/NaN を考慮して int に変換する。"""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    return int(val)


def _parse_accounting_standard(
    val: str | None,
) -> AccountingStandard | str | None:
    """文字列を AccountingStandard Enum に変換する。未知の値はそのまま str。"""
    if val is None:
        return None
    try:
        return AccountingStandard(val)
    except ValueError:
        return val


def _parse_period_type(val: str | None) -> PeriodType | str | None:
    """文字列を PeriodType Enum に変換する。未知の値はそのまま str。"""
    if val is None:
        return None
    try:
        return PeriodType(val)
    except ValueError:
        return val


def _parse_bool(val: Any) -> bool | None:
    """None を考慮して bool に変換する。"""
    if val is None:
        return None
    return bool(val)


def deserialize_dei(row: dict[str, Any]) -> DEI:
    """dict 行から DEI を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        DEI オブジェクト。Enum 値は自動復元される。
    """
    return DEI(
        edinet_code=row.get("edinet_code"),
        fund_code=row.get("fund_code"),
        security_code=row.get("security_code"),
        filer_name_ja=row.get("filer_name_ja"),
        filer_name_en=row.get("filer_name_en"),
        fund_name_ja=row.get("fund_name_ja"),
        fund_name_en=row.get("fund_name_en"),
        cabinet_office_ordinance=row.get("cabinet_office_ordinance"),
        document_type=row.get("document_type"),
        accounting_standards=_parse_accounting_standard(
            row.get("accounting_standards")
        ),
        has_consolidated=_parse_bool(row.get("has_consolidated")),
        industry_code_consolidated=row.get("industry_code_consolidated"),
        industry_code_non_consolidated=row.get(
            "industry_code_non_consolidated"
        ),
        current_fiscal_year_start_date=_parse_date(
            row.get("current_fiscal_year_start_date")
        ),
        current_period_end_date=_parse_date(
            row.get("current_period_end_date")
        ),
        type_of_current_period=_parse_period_type(
            row.get("type_of_current_period")
        ),
        current_fiscal_year_end_date=_parse_date(
            row.get("current_fiscal_year_end_date")
        ),
        previous_fiscal_year_start_date=_parse_date(
            row.get("previous_fiscal_year_start_date")
        ),
        comparative_period_end_date=_parse_date(
            row.get("comparative_period_end_date")
        ),
        previous_fiscal_year_end_date=_parse_date(
            row.get("previous_fiscal_year_end_date")
        ),
        next_fiscal_year_start_date=_parse_date(
            row.get("next_fiscal_year_start_date")
        ),
        end_date_of_next_semi_annual_period=_parse_date(
            row.get("end_date_of_next_semi_annual_period")
        ),
        number_of_submission=_safe_int(row.get("number_of_submission")),
        amendment_flag=_parse_bool(row.get("amendment_flag")),
        identification_of_document_subject_to_amendment=row.get(
            "identification_of_document_subject_to_amendment"
        ),
        report_amendment_flag=_parse_bool(row.get("report_amendment_flag")),
        xbrl_amendment_flag=_parse_bool(row.get("xbrl_amendment_flag")),
    )


def deserialize_calc_linkbase(
    rows: list[dict[str, Any]],
) -> CalculationLinkbase:
    """dict 行リストから CalculationLinkbase を復元する。

    Args:
        rows: Parquet 行の辞書リスト（1 つの doc_id 分）。

    Returns:
        CalculationLinkbase オブジェクト。
    """
    # role_uri でグループ化
    by_role: dict[str, list[CalculationArc]] = defaultdict(list)
    for row in rows:
        arc = CalculationArc(
            parent=row["parent"],
            child=row["child"],
            parent_href=row["parent_href"],
            child_href=row["child_href"],
            weight=int(row["weight"]),
            order=float(row["order"]),
            role_uri=row["role_uri"],
        )
        by_role[arc.role_uri].append(arc)

    trees: dict[str, CalculationTree] = {}
    for role_uri, arcs in by_role.items():
        # roots = parent のみで child でない concept
        children = {a.child for a in arcs}
        parents = {a.parent for a in arcs}
        roots = tuple(p for p in parents if p not in children)
        trees[role_uri] = CalculationTree(
            role_uri=role_uri,
            arcs=tuple(arcs),
            roots=roots,
        )

    return CalculationLinkbase(source_path=None, trees=trees)


def deserialize_detected_standard(
    row: dict[str, Any],
) -> DetectedStandard | None:
    """DEI 行に同梱された DetectedStandard を復元する。

    Args:
        row: DEI Parquet 行の辞書。

    Returns:
        DetectedStandard。同梱データがない場合は None。
    """
    method_val = row.get("detected_method")
    if method_val is None:
        return None

    standard = _parse_accounting_standard(row.get("detected_standard"))
    method = DetectionMethod(method_val)
    detail_val = row.get("detected_detail_level")
    detail_level = DetailLevel(detail_val) if detail_val is not None else None
    has_consolidated = _parse_bool(row.get("detected_has_consolidated"))
    period_type = _parse_period_type(row.get("detected_period_type"))

    return DetectedStandard(
        standard=standard,
        method=method,
        detail_level=detail_level,
        has_consolidated=has_consolidated,
        period_type=period_type,
    )


def deserialize_statements(
    items: tuple[LineItem, ...],
    *,
    dei: DEI | None = None,
    detected_standard: DetectedStandard | None = None,
    contexts: dict[str, StructuredContext] | None = None,
    calculation_linkbase: CalculationLinkbase | None = None,
) -> Statements:
    """復元済みパーツから Statements を直接構築する。

    Args:
        items: 復元済み LineItem タプル。
        dei: 復元済み DEI。
        detected_standard: 永続化された DetectedStandard。
        contexts: 復元済み context マッピング。
        calculation_linkbase: 復元済み CalculationLinkbase。

    Returns:
        Statements オブジェクト。
    """
    from edinet.xbrl.dei import resolve_industry_code

    industry_code = None
    if dei is not None:
        # 永続化された DetectedStandard がなければ DEI から再導出
        if detected_standard is None:
            detected_standard = detect_from_dei(dei)
        industry_code = resolve_industry_code(dei)

    return Statements(
        _items=items,
        _detected_standard=detected_standard,
        _dei=dei,
        _contexts=contexts,
        _industry_code=industry_code,
        _calculation_linkbase=calculation_linkbase,
        _facts=None,
        _taxonomy_root=None,
        _resolver=None,
        _definition_linkbase=None,
    )

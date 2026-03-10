"""Parquet テーブルの明示的 PyArrow スキーマ定義。

繰り返しの多い文字列カラムに ``pa.dictionary()`` を適用し、
型推論を省略することで書き出し速度とファイルサイズを改善する。
"""

from __future__ import annotations

from typing import Any


def _require_pa() -> Any:
    """pyarrow を遅延 import する。"""
    import pyarrow as pa

    return pa


def filings_schema() -> Any:
    """filings テーブルのスキーマを返す。

    Returns:
        pa.Schema: filings テーブル用の PyArrow スキーマ。
    """
    pa = _require_pa()
    return pa.schema(
        [
            pa.field("seq_number", pa.int64()),
            pa.field("doc_id", pa.string()),
            pa.field("doc_type_code", pa.dictionary(pa.int8(), pa.string())),
            pa.field("ordinance_code", pa.dictionary(pa.int8(), pa.string())),
            pa.field("form_code", pa.dictionary(pa.int8(), pa.string())),
            pa.field("edinet_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("sec_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("jcn", pa.string()),
            pa.field("filer_name", pa.string()),
            pa.field("fund_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("submit_date_time", pa.timestamp("us")),
            pa.field("period_start", pa.date32()),
            pa.field("period_end", pa.date32()),
            pa.field("doc_description", pa.string()),
            pa.field("issuer_edinet_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("subject_edinet_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("subsidiary_edinet_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("current_report_reason", pa.string()),
            pa.field("parent_doc_id", pa.string()),
            pa.field("ope_date_time", pa.timestamp("us")),
            pa.field("withdrawal_status", pa.dictionary(pa.int8(), pa.string())),
            pa.field("doc_info_edit_status", pa.dictionary(pa.int8(), pa.string())),
            pa.field("disclosure_status", pa.dictionary(pa.int8(), pa.string())),
            pa.field("has_xbrl", pa.bool_()),
            pa.field("has_pdf", pa.bool_()),
            pa.field("has_attachment", pa.bool_()),
            pa.field("has_english", pa.bool_()),
            pa.field("has_csv", pa.bool_()),
            pa.field("legal_status", pa.dictionary(pa.int8(), pa.string())),
        ]
    )


def line_items_schema() -> Any:
    """line_items テーブルのスキーマを返す。

    Returns:
        pa.Schema: line_items テーブル用の PyArrow スキーマ。
    """
    pa = _require_pa()
    return pa.schema(
        [
            pa.field("doc_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("concept", pa.dictionary(pa.int16(), pa.string())),
            pa.field("namespace_uri", pa.dictionary(pa.int8(), pa.string())),
            pa.field("local_name", pa.dictionary(pa.int16(), pa.string())),
            pa.field("label_ja_text", pa.string()),
            pa.field("label_ja_role", pa.dictionary(pa.int8(), pa.string())),
            pa.field("label_ja_lang", pa.dictionary(pa.int8(), pa.string())),
            pa.field("label_ja_source", pa.dictionary(pa.int8(), pa.string())),
            pa.field("label_en_text", pa.string()),
            pa.field("label_en_role", pa.dictionary(pa.int8(), pa.string())),
            pa.field("label_en_lang", pa.dictionary(pa.int8(), pa.string())),
            pa.field("label_en_source", pa.dictionary(pa.int8(), pa.string())),
            pa.field("value_numeric", pa.string()),
            pa.field("value_text", pa.string()),
            pa.field("value_type", pa.dictionary(pa.int8(), pa.string())),
            pa.field("unit_ref", pa.dictionary(pa.int8(), pa.string())),
            pa.field("decimals_int", pa.int32()),
            pa.field("decimals_inf", pa.bool_()),
            pa.field("context_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("period_type", pa.dictionary(pa.int8(), pa.string())),
            pa.field("period_instant", pa.date32()),
            pa.field("period_start", pa.date32()),
            pa.field("period_end", pa.date32()),
            pa.field("entity_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("dimensions_json", pa.string()),
            pa.field("is_nil", pa.bool_()),
            pa.field("source_line", pa.int32()),
            pa.field("order", pa.int32()),
        ]
    )


def contexts_schema() -> Any:
    """contexts テーブルのスキーマを返す。

    Returns:
        pa.Schema: contexts テーブル用の PyArrow スキーマ。
    """
    pa = _require_pa()
    return pa.schema(
        [
            pa.field("doc_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("context_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("period_type", pa.dictionary(pa.int8(), pa.string())),
            pa.field("period_instant", pa.date32()),
            pa.field("period_start", pa.date32()),
            pa.field("period_end", pa.date32()),
            pa.field("entity_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("entity_scheme", pa.dictionary(pa.int8(), pa.string())),
            pa.field("dimensions_json", pa.string()),
            pa.field("source_line", pa.int32()),
        ]
    )


def dei_schema() -> Any:
    """dei テーブルのスキーマを返す。

    Returns:
        pa.Schema: dei テーブル用の PyArrow スキーマ。
    """
    pa = _require_pa()
    return pa.schema(
        [
            pa.field("doc_id", pa.string()),
            pa.field("edinet_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("fund_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("security_code", pa.dictionary(pa.int16(), pa.string())),
            pa.field("filer_name_ja", pa.string()),
            pa.field("filer_name_en", pa.string()),
            pa.field("fund_name_ja", pa.string()),
            pa.field("fund_name_en", pa.string()),
            pa.field("cabinet_office_ordinance", pa.dictionary(pa.int8(), pa.string())),
            pa.field("document_type", pa.dictionary(pa.int8(), pa.string())),
            pa.field("accounting_standards", pa.dictionary(pa.int8(), pa.string())),
            pa.field("has_consolidated", pa.bool_()),
            pa.field("industry_code_consolidated", pa.dictionary(pa.int8(), pa.string())),
            pa.field("industry_code_non_consolidated", pa.dictionary(pa.int8(), pa.string())),
            pa.field("current_fiscal_year_start_date", pa.date32()),
            pa.field("current_period_end_date", pa.date32()),
            pa.field("type_of_current_period", pa.dictionary(pa.int8(), pa.string())),
            pa.field("current_fiscal_year_end_date", pa.date32()),
            pa.field("previous_fiscal_year_start_date", pa.date32()),
            pa.field("comparative_period_end_date", pa.date32()),
            pa.field("previous_fiscal_year_end_date", pa.date32()),
            pa.field("next_fiscal_year_start_date", pa.date32()),
            pa.field("end_date_of_next_semi_annual_period", pa.date32()),
            pa.field("number_of_submission", pa.int64()),
            pa.field("amendment_flag", pa.bool_()),
            pa.field("identification_of_document_subject_to_amendment", pa.string()),
            pa.field("report_amendment_flag", pa.bool_()),
            pa.field("xbrl_amendment_flag", pa.bool_()),
            pa.field("source_path", pa.string()),
            pa.field("detected_standard", pa.dictionary(pa.int8(), pa.string())),
            pa.field("detected_method", pa.dictionary(pa.int8(), pa.string())),
            pa.field("detected_detail_level", pa.dictionary(pa.int8(), pa.string())),
            pa.field("detected_has_consolidated", pa.bool_()),
            pa.field("detected_period_type", pa.dictionary(pa.int8(), pa.string())),
        ]
    )


def calc_edges_schema() -> Any:
    """calc_edges テーブルのスキーマを返す。

    Returns:
        pa.Schema: calc_edges テーブル用の PyArrow スキーマ。
    """
    pa = _require_pa()
    return pa.schema(
        [
            pa.field("doc_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("role_uri", pa.dictionary(pa.int8(), pa.string())),
            pa.field("parent", pa.dictionary(pa.int16(), pa.string())),
            pa.field("child", pa.dictionary(pa.int16(), pa.string())),
            pa.field("parent_href", pa.string()),
            pa.field("child_href", pa.string()),
            pa.field("weight", pa.float64()),
            pa.field("order", pa.float64()),
        ]
    )


def def_parents_schema() -> Any:
    """def_parents テーブルのスキーマを返す。

    Returns:
        pa.Schema: def_parents テーブル用の PyArrow スキーマ。
    """
    pa = _require_pa()
    return pa.schema(
        [
            pa.field("doc_id", pa.dictionary(pa.int16(), pa.string())),
            pa.field("child_concept", pa.dictionary(pa.int16(), pa.string())),
            pa.field("parent_standard_concept", pa.dictionary(pa.int16(), pa.string())),
        ]
    )


SCHEMAS: dict[str, Any] = {
    "filings": filings_schema,
    "line_items": line_items_schema,
    "text_blocks": line_items_schema,
    "contexts": contexts_schema,
    "dei": dei_schema,
    "calc_edges": calc_edges_schema,
    "def_parents": def_parents_schema,
}

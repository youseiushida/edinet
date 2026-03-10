from typing import Any

def filings_schema() -> Any:
    """filings テーブルのスキーマを返す。

    Returns:
        pa.Schema: filings テーブル用の PyArrow スキーマ。
    """
def line_items_schema() -> Any:
    """line_items テーブルのスキーマを返す。

    Returns:
        pa.Schema: line_items テーブル用の PyArrow スキーマ。
    """
def contexts_schema() -> Any:
    """contexts テーブルのスキーマを返す。

    Returns:
        pa.Schema: contexts テーブル用の PyArrow スキーマ。
    """
def dei_schema() -> Any:
    """dei テーブルのスキーマを返す。

    Returns:
        pa.Schema: dei テーブル用の PyArrow スキーマ。
    """
def calc_edges_schema() -> Any:
    """calc_edges テーブルのスキーマを返す。

    Returns:
        pa.Schema: calc_edges テーブル用の PyArrow スキーマ。
    """
def def_parents_schema() -> Any:
    """def_parents テーブルのスキーマを返す。

    Returns:
        pa.Schema: def_parents テーブル用の PyArrow スキーマ。
    """

SCHEMAS: dict[str, Any]

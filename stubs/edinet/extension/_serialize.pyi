from edinet.financial.standards.detect import DetectedStandard as DetectedStandard
from edinet.models.filing import Filing as Filing
from edinet.models.financial import LineItem as LineItem
from edinet.xbrl.contexts import InstantPeriod as InstantPeriod, StructuredContext as StructuredContext
from edinet.xbrl.dei import DEI as DEI
from edinet.xbrl.linkbase.calculation import CalculationLinkbase as CalculationLinkbase
from edinet.xbrl.linkbase.definition import DefinitionTree as DefinitionTree
from typing import Any

def is_text_block(local_name: str) -> bool:
    """TextBlock 系の Fact かどうかを判定する。

    Args:
        local_name: 概念のローカル名。

    Returns:
        ``True`` なら TextBlock。
    """
def serialize_filing(filing: Filing) -> dict[str, Any]:
    """Filing を dict 行に変換する。

    Args:
        filing: Filing オブジェクト。

    Returns:
        Parquet 行用の辞書。computed_field は除外される。
    """
def serialize_line_item(item: LineItem, doc_id: str) -> dict[str, Any]:
    """LineItem を dict 行に変換する。

    Args:
        item: LineItem オブジェクト。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書。
    """
def serialize_context(ctx: StructuredContext, doc_id: str) -> dict[str, Any]:
    """StructuredContext を dict 行に変換する。

    Args:
        ctx: StructuredContext オブジェクト。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書。
    """
def serialize_dei(dei: DEI, doc_id: str, *, detected_standard: DetectedStandard | None = None, source_path: str | None = None) -> dict[str, Any]:
    """DEI を dict 行に変換する。

    Args:
        dei: DEI オブジェクト。
        doc_id: 対応する Filing の doc_id。
        detected_standard: 永続化する DetectedStandard（DEI のみでは
            復元できない名前空間フォールバック判別結果を保持するため）。

    Returns:
        Parquet 行用の辞書。Enum は .value 文字列で保存。
    """
def serialize_calc_edges(calc_linkbase: CalculationLinkbase, doc_id: str) -> list[dict[str, Any]]:
    """CalculationLinkbase を dict 行リストに変換する。

    Args:
        calc_linkbase: CalculationLinkbase オブジェクト。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書リスト。
    """
def serialize_def_parents(definition_linkbase: dict[str, DefinitionTree] | None, doc_id: str) -> list[dict[str, Any]]:
    """DefinitionLinkbase → parent_index → dict 行リストに変換する。

    Args:
        definition_linkbase: parse_definition_linkbase() の戻り値。
        doc_id: 対応する Filing の doc_id。

    Returns:
        Parquet 行用の辞書リスト。
    """

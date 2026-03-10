from edinet.financial.standards.detect import DetailLevel as DetailLevel, DetectedStandard as DetectedStandard, DetectionMethod as DetectionMethod, detect_from_dei as detect_from_dei
from edinet.financial.statements import Statements as Statements
from edinet.models.filing import Filing as Filing
from edinet.models.financial import LineItem as LineItem
from edinet.xbrl.contexts import DimensionMember as DimensionMember, DurationPeriod as DurationPeriod, InstantPeriod as InstantPeriod, StructuredContext as StructuredContext
from edinet.xbrl.dei import AccountingStandard as AccountingStandard, DEI as DEI, PeriodType as PeriodType
from edinet.xbrl.linkbase.calculation import CalculationArc as CalculationArc, CalculationLinkbase as CalculationLinkbase, CalculationTree as CalculationTree
from edinet.xbrl.taxonomy import LabelInfo as LabelInfo, LabelSource as LabelSource
from typing import Any

def deserialize_filing(row: dict[str, Any]) -> Filing:
    """dict 行から Filing を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        Filing オブジェクト。computed_field は自動再計算される。
    """
def deserialize_line_item(row: dict[str, Any]) -> LineItem:
    """dict 行から LineItem を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        LineItem オブジェクト。
    """
def deserialize_context(row: dict[str, Any]) -> StructuredContext:
    """dict 行から StructuredContext を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        StructuredContext オブジェクト。
    """
def deserialize_dei(row: dict[str, Any]) -> DEI:
    """dict 行から DEI を復元する。

    Args:
        row: Parquet 行の辞書。

    Returns:
        DEI オブジェクト。Enum 値は自動復元される。
    """
def deserialize_calc_linkbase(rows: list[dict[str, Any]]) -> CalculationLinkbase:
    """dict 行リストから CalculationLinkbase を復元する。

    Args:
        rows: Parquet 行の辞書リスト（1 つの doc_id 分）。

    Returns:
        CalculationLinkbase オブジェクト。
    """
def deserialize_detected_standard(row: dict[str, Any]) -> DetectedStandard | None:
    """DEI 行に同梱された DetectedStandard を復元する。

    Args:
        row: DEI Parquet 行の辞書。

    Returns:
        DetectedStandard。同梱データがない場合は None。
    """
def deserialize_statements(items: tuple[LineItem, ...], *, dei: DEI | None = None, detected_standard: DetectedStandard | None = None, contexts: dict[str, StructuredContext] | None = None, calculation_linkbase: CalculationLinkbase | None = None, definition_parent_index: dict[str, str] | None = None, source_path: str | None = None) -> Statements:
    """復元済みパーツから Statements を直接構築する。

    Args:
        items: 復元済み LineItem タプル。
        dei: 復元済み DEI。
        detected_standard: 永続化された DetectedStandard。
        contexts: 復元済み context マッピング。
        calculation_linkbase: 復元済み CalculationLinkbase。
        definition_parent_index: 復元済みの definition parent index。
            ``extract_values()`` の ``definition_mapper`` が使用する。
        source_path: 元の XBRL ファイルパス（ZIP 内パス）。

    Returns:
        Statements オブジェクト。
    """

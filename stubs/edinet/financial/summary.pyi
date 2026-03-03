from dataclasses import dataclass
from datetime import date
from edinet.financial.statements import Statements

__all__ = ['FilingSummary', 'build_summary']

@dataclass(frozen=True, slots=True)
class FilingSummary:
    '''書類の概観情報。

    Attributes:
        total_items: 全 LineItem 数。
        accounting_standard: 会計基準名（"Japan GAAP" / "IFRS" / "US GAAP"）。
        period_start: 当期開始日。
        period_end: 当期終了日。
        period_type: 期間種別（"FY" / "HY"）。
        has_consolidated: 連結データの有無。
        has_non_consolidated: 個別データの有無。
        standard_item_count: 標準タクソノミの科目数。
        custom_item_count: 提出者別タクソノミの科目数。
        standard_item_ratio: 標準科目比率（0.0-1.0）。
        namespace_counts: モジュールグループ別の科目数。
        segment_count: セグメント数（ディメンション付きコンテキストの種類数）。
    '''
    total_items: int
    accounting_standard: str
    period_start: date | None
    period_end: date | None
    period_type: str | None
    has_consolidated: bool
    has_non_consolidated: bool
    standard_item_count: int
    custom_item_count: int
    standard_item_ratio: float
    namespace_counts: dict[str, int]
    segment_count: int

def build_summary(stmts: Statements) -> FilingSummary:
    """Statements から概観情報を構築する。

    Args:
        stmts: 構築済みの Statements オブジェクト。

    Returns:
        FilingSummary dataclass。
    """

"""書類の概観情報を提供するモジュール。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from edinet.xbrl._namespaces import classify_namespace, is_standard_taxonomy

if TYPE_CHECKING:
    from edinet.financial.statements import Statements

__all__ = ["FilingSummary", "build_summary"]


@dataclass(frozen=True, slots=True)
class FilingSummary:
    """書類の概観情報。

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
    """

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
    total_items = len(stmts)

    # 会計基準
    detected = stmts.detected_standard
    if detected is not None and detected.standard is not None:
        accounting_standard = str(detected.standard.value)
    else:
        accounting_standard = "不明"

    # DEI から期間情報を取得
    dei = stmts.dei
    period_start: date | None = None
    period_end: date | None = None
    period_type: str | None = None
    if dei is not None:
        period_start = dei.current_fiscal_year_start_date
        period_end = dei.current_period_end_date
        top = dei.type_of_current_period
        if top is not None:
            period_type = str(top.value) if hasattr(top, "value") else str(top)

    # 連結/個別
    has_consolidated = stmts.has_consolidated_data
    has_non_consolidated = stmts.has_non_consolidated_data

    # 標準/提出者別の分類
    standard_item_count = 0
    custom_item_count = 0
    namespace_counts: dict[str, int] = {}
    segments: set[frozenset[tuple[str, str]]] = set()

    for item in stmts:
        # 標準/提出者別カウント
        if is_standard_taxonomy(item.namespace_uri):
            standard_item_count += 1
        else:
            custom_item_count += 1

        # モジュールグループ別カウント
        ns_info = classify_namespace(item.namespace_uri)
        group = ns_info.module_group if ns_info.module_group is not None else "その他"
        namespace_counts[group] = namespace_counts.get(group, 0) + 1

        # セグメントカウント（ディメンション付きのコンテキストのみ）
        if item.dimensions:
            dim_key = frozenset(
                (dm.axis, dm.member) for dm in item.dimensions
            )
            segments.add(dim_key)

    segment_count = len(segments)

    # 標準科目比率
    if total_items > 0:
        standard_item_ratio = standard_item_count / total_items
    else:
        standard_item_ratio = 0.0

    return FilingSummary(
        total_items=total_items,
        accounting_standard=accounting_standard,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        has_consolidated=has_consolidated,
        has_non_consolidated=has_non_consolidated,
        standard_item_count=standard_item_count,
        custom_item_count=custom_item_count,
        standard_item_ratio=standard_item_ratio,
        namespace_counts=namespace_counts,
        segment_count=segment_count,
    )

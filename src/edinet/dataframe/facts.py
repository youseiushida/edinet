"""全 LineItem を全カラム DataFrame に変換するモジュール。

``line_items_to_dataframe()`` で LineItem シーケンスを
全フィールドの DataFrame に変換する。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from edinet.models.financial import LineItem
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["line_items_to_dataframe"]

_FULL_COLUMNS: Final[list[str]] = [
    "concept",
    "namespace_uri",
    "local_name",
    "label_ja",
    "label_en",
    "value",
    "unit_ref",
    "decimals",
    "context_id",
    "period_type",
    "period_start",
    "period_end",
    "entity_id",
    "consolidated",
    "dimensions_str",
    "is_nil",
    "source_line",
    "order",
]

_CONSOLIDATED_AXIS_SUFFIX = "ConsolidatedOrNonConsolidatedAxis"
_NONCONSOLIDATED_MEMBER_SUFFIX = "NonConsolidatedMember"


def _derive_consolidated(item: LineItem) -> bool | None:
    """dimensions から連結/個別を導出する。

    Args:
        item: 対象の LineItem。

    Returns:
        True=連結、False=個別、None=判定不能。
    """
    if len(item.dimensions) == 0:
        return True
    for dim in item.dimensions:
        if dim.member.endswith(_NONCONSOLIDATED_MEMBER_SUFFIX):
            return False
    if all(
        dim.axis.endswith(_CONSOLIDATED_AXIS_SUFFIX)
        for dim in item.dimensions
    ):
        return True
    return None


def _format_dimensions(item: LineItem) -> str:
    """dimensions を文字列表現に変換する。

    Args:
        item: 対象の LineItem。

    Returns:
        ``"axis1=member1;axis2=member2"`` 形式。空なら ``""``。
    """
    if not item.dimensions:
        return ""
    parts = []
    for dim in item.dimensions:
        axis_short = dim.axis.rsplit("}", 1)[-1] if "}" in dim.axis else dim.axis
        member_short = dim.member.rsplit("}", 1)[-1] if "}" in dim.member else dim.member
        parts.append(f"{axis_short}={member_short}")
    return ";".join(parts)


def line_items_to_dataframe(
    items: Sequence[LineItem],
    *,
    metadata: dict[str, object] | None = None,
) -> pd.DataFrame:
    """全 LineItem を全カラム DataFrame に変換する。

    Args:
        items: LineItem のシーケンス。
        metadata: DataFrame の attrs に付与するメタデータ。

    Returns:
        全カラムの pandas DataFrame。

    Raises:
        ImportError: pandas がインストールされていない場合。
    """
    try:
        import pandas as pd_
    except ImportError:
        raise ImportError(
            "pandas が必要です。pip install edinet[analysis] でインストールしてください"
        ) from None

    rows: list[dict[str, object]] = []
    for item in items:
        period = item.period
        if isinstance(period, InstantPeriod):
            period_type = "instant"
            period_start = None
            period_end = period.instant
        elif isinstance(period, DurationPeriod):
            period_type = "duration"
            period_start = period.start_date
            period_end = period.end_date
        else:
            period_type = None
            period_start = None
            period_end = None

        rows.append({
            "concept": item.concept,
            "namespace_uri": item.namespace_uri,
            "local_name": item.local_name,
            "label_ja": item.label_ja.text,
            "label_en": item.label_en.text,
            "value": item.value,
            "unit_ref": item.unit_ref,
            "decimals": item.decimals,
            "context_id": item.context_id,
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "entity_id": item.entity_id,
            "consolidated": _derive_consolidated(item),
            "dimensions_str": _format_dimensions(item),
            "is_nil": item.is_nil,
            "source_line": item.source_line,
            "order": item.order,
        })

    if not rows:
        df = pd_.DataFrame(columns=_FULL_COLUMNS)
    else:
        df = pd_.DataFrame(rows, columns=_FULL_COLUMNS)

    if metadata:
        df.attrs.update(metadata)
    return df

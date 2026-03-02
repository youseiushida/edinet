import pandas as pd
from collections.abc import Sequence
from edinet.models.financial import LineItem

__all__ = ['line_items_to_dataframe']

def line_items_to_dataframe(items: Sequence[LineItem], *, metadata: dict[str, object] | None = None) -> pd.DataFrame:
    """全 LineItem を全カラム DataFrame に変換する。

    Args:
        items: LineItem のシーケンス。
        metadata: DataFrame の attrs に付与するメタデータ。

    Returns:
        全カラムの pandas DataFrame。

    Raises:
        ImportError: pandas がインストールされていない場合。
    """

from edinet.models.financial import FinancialStatement
from rich.table import Table

__all__ = ['render_statement']

def render_statement(statement: FinancialStatement) -> Table:
    """FinancialStatement を Rich Table に変換する。

    Args:
        statement: 表示対象の財務諸表。

    Returns:
        Rich Table オブジェクト。``console.print(table)`` で表示する。

    Raises:
        ImportError: rich がインストールされていない場合。
            ``pip install edinet[display]`` でインストールできる。
    """

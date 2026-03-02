"""Rich 表示向けの描画ヘルパー。

``render_statement()`` で ``FinancialStatement`` を Rich Table に変換する。
``FinancialStatement.__rich_console__()`` から内部的に呼ばれる。

利用者が Rich Table をカスタマイズしたい場合は
``render_statement()`` で Table オブジェクトを取得し、
Rich の API で加工してから ``console.print(table)`` する。

Examples:
    >>> from rich.console import Console
    >>> from edinet.display.rich import render_statement
    >>> table = render_statement(pl)
    >>> Console().print(table)  # そのまま表示
    >>>
    >>> table.add_column("備考")  # カラム追加等のカスタマイズ
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.table import Table

    from edinet.models.financial import FinancialStatement

__all__ = ["render_statement"]


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
    try:
        from rich.table import Table as RichTable
    except ImportError:
        raise ImportError(
            "rich is required for render_statement(). "
            "Install it with: pip install edinet[display]"
        ) from None

    title = _build_title(statement)
    table = RichTable(title=title, title_style="bold", show_lines=False)

    table.add_column("科目", style="cyan", min_width=20)
    table.add_column("金額", justify="right", style="green", min_width=20)
    table.add_column("concept", style="dim", no_wrap=True)

    for item in statement.items:
        label = item.label_ja.text
        if isinstance(item.value, Decimal):
            value_str = f"{item.value:,}"
        elif item.value is None:
            value_str = "—"
        else:
            value_str = str(item.value)
        table.add_row(label, value_str, item.local_name)

    return table


def _build_title(statement: FinancialStatement) -> str:
    """テーブルタイトルを組み立てる。

    Note:
        Rich の Table title はマークアップを解釈するため、
        ``[連結]`` が ``[style]text[/style]`` 構文と衝突する。
        ``rich.markup.escape()`` でエスケープする。
    """
    from rich.markup import escape

    from edinet.models.financial import STATEMENT_TYPE_LABELS, format_period

    type_label = STATEMENT_TYPE_LABELS.get(
        statement.statement_type,
        statement.statement_type.value,
    )
    scope = "連結" if statement.consolidated else "個別"
    period_str = format_period(statement.period) if statement.period else ""

    return escape(f"{type_label}  [{scope}] {period_str}")

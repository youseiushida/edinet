"""財務諸表の HTML 表示モジュール。

Jupyter Notebook での ``_repr_html_()`` プロトコル用の HTML テーブル生成を提供する。
``display/statements.py`` の ``build_display_rows()`` を再利用し、
``DisplayRow`` → HTML ``<tr>`` への変換を行う。
"""

from __future__ import annotations

from decimal import Decimal
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.models.financial import FinancialStatement
    from edinet.xbrl.taxonomy.concept_sets import ConceptSet

__all__ = ["to_html"]

# インライン CSS（外部依存なし）
_CSS = """\
<style scoped>
.edinet-stmt { border-collapse: collapse; width: 100%; font-family: system-ui, sans-serif; font-size: 13px; }
.edinet-stmt th { background: #f5f5f5; text-align: left; padding: 6px 8px; border-bottom: 2px solid #ddd; }
.edinet-stmt td { padding: 4px 8px; border-bottom: 1px solid #eee; }
.edinet-stmt .amount { text-align: right; font-variant-numeric: tabular-nums; }
.edinet-stmt .abstract td { font-weight: bold; background: #fafafa; }
.edinet-stmt .total td { font-weight: bold; border-top: 1px solid #333; }
.edinet-stmt .label { white-space: nowrap; }
</style>
"""


def _format_value(value: Decimal | str | None) -> str:
    """値を表示用文字列に変換する。

    Args:
        value: 変換対象の値。Decimal は 3 桁カンマ区切り、
            str はエスケープ済み文字列、None は空文字列。

    Returns:
        表示用文字列。
    """
    if value is None:
        return ""
    if isinstance(value, Decimal):
        # 3桁カンマ区切り
        return f"{value:,.0f}"
    return escape(str(value))


def to_html(
    statement: FinancialStatement,
    *,
    concept_set: ConceptSet | None = None,
    abstract_labels: dict[str, str] | None = None,
) -> str:
    """FinancialStatement を HTML テーブル文字列に変換する。

    ``display/statements.py`` の ``build_display_rows()`` を使用して
    ``DisplayRow`` リストを生成し、HTML テーブルに変換する。

    Args:
        statement: 表示対象の財務諸表。
        concept_set: 階層表示用の ConceptSet。None の場合はフラット表示。
        abstract_labels: 抽象概念のラベル辞書。

    Returns:
        HTML テーブル文字列。
    """
    from edinet.display.statements import build_display_rows
    from edinet.models.financial import STATEMENT_TYPE_LABELS, format_period

    rows = build_display_rows(statement, concept_set, abstract_labels=abstract_labels)

    # タイトル構築
    type_label = STATEMENT_TYPE_LABELS.get(
        statement.statement_type,
        statement.statement_type.value,
    )
    scope = "連結" if statement.consolidated else "個別"
    period_str = format_period(statement.period) if statement.period else ""
    title = f"{type_label}  [{scope}] {period_str}"

    lines = [_CSS]
    lines.append('<table class="edinet-stmt">')
    lines.append(f"<caption><strong>{escape(title)}</strong></caption>")
    lines.append(
        "<thead><tr><th>科目</th><th class='amount'>金額</th></tr></thead>"
    )
    lines.append("<tbody>")

    for row in rows:
        css_classes: list[str] = []
        if row.is_abstract:
            css_classes.append("abstract")
        if row.is_total:
            css_classes.append("total")
        class_attr = f' class="{" ".join(css_classes)}"' if css_classes else ""

        indent = f"padding-left:{row.depth * 1.5}em" if row.depth > 0 else ""
        style_attr = f' style="{indent}"' if indent else ""

        value_str = _format_value(row.value)

        lines.append(f"<tr{class_attr}>")
        lines.append(f'  <td class="label"{style_attr}>{escape(row.label)}</td>')
        lines.append(f'  <td class="amount">{value_str}</td>')
        lines.append("</tr>")

    lines.append("</tbody></table>")
    return "\n".join(lines)

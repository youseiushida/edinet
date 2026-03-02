"""財務諸表の階層表示モジュール。

ConceptSet の depth / is_abstract / is_total を使い、
財務諸表を「人間が見慣れた形式」で階層表示する。

LineItem は変更せず、表示時に ConceptSet の構造情報と
FinancialStatement の値データをマージする。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.table import Table

    from edinet.models.financial import FinancialStatement, LineItem
    from edinet.xbrl.taxonomy.concept_sets import ConceptSet

logger = logging.getLogger(__name__)

# href 例: "jppfs_cor_2025-11-01.xsd#jppfs_cor_CashAndDeposits"
# → prefix = "jppfs_cor"
_HREF_PREFIX_RE = re.compile(r"^(.+?)_\d{4}-\d{2}-\d{2}\.")

__all__ = [
    "DisplayRow",
    "build_display_rows",
    "render_hierarchical_statement",
]


@dataclass(frozen=True, slots=True)
class DisplayRow:
    """表示用の1行。

    Attributes:
        label: 表示ラベル。
        value: 値。None はセクションヘッダー。
        concept: concept ローカル名。
        depth: インデント深度。
        is_abstract: セクションヘッダーかどうか。
        is_total: 合計行かどうか。
    """

    label: str
    value: Decimal | str | None
    concept: str
    depth: int
    is_abstract: bool
    is_total: bool


def _resolve_abstract_labels(
    concept_set: ConceptSet,
    taxonomy_root: Path | None = None,
) -> dict[str, str]:
    """abstract 科目のラベル辞書を構築する。

    Args:
        concept_set: ConceptSet。
        taxonomy_root: タクソノミルートパス。

    Returns:
        ``{concept_local_name: label}`` の辞書。
    """
    labels: dict[str, str] = {}

    if taxonomy_root is not None:
        try:
            from edinet.xbrl.taxonomy import LabelSource, TaxonomyResolver

            resolver = TaxonomyResolver(taxonomy_root)
            for entry in concept_set.concepts:
                if entry.is_abstract and entry.href:
                    href_file = entry.href.split("#")[0] if "#" in entry.href else ""
                    m = _HREF_PREFIX_RE.match(href_file)
                    prefix = m.group(1) if m else ""
                    if prefix:
                        info = resolver.resolve(prefix, entry.concept, lang="ja")
                        if info.source != LabelSource.FALLBACK:
                            labels[entry.concept] = info.text
        except Exception:
            logger.debug("abstract ラベル解決に失敗", exc_info=True)

    # taxonomy で解決できなかった abstract 科目はフォールバック
    for entry in concept_set.concepts:
        if entry.is_abstract and entry.concept not in labels:
            name = entry.concept
            for suffix in ("Abstract", "Heading", "LineItems"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            labels[entry.concept] = name

    return labels


def build_display_rows(
    statement: FinancialStatement,
    concept_set: ConceptSet | None = None,
    *,
    abstract_labels: dict[str, str] | None = None,
) -> list[DisplayRow]:
    """ConceptSet をマージして表示行を生成する。

    Args:
        statement: 財務諸表。
        concept_set: ConceptSet。None の場合はフラット表示。
        abstract_labels: abstract 科目のラベル辞書。

    Returns:
        DisplayRow のリスト。
    """
    if concept_set is None:
        # フラット表示
        return [
            DisplayRow(
                label=item.label_ja.text,
                value=item.value,
                concept=item.local_name,
                depth=0,
                is_abstract=False,
                is_total=False,
            )
            for item in statement.items
        ]

    if abstract_labels is None:
        abstract_labels = {}

    # LineItem を local_name でインデックス
    item_map: dict[str, LineItem] = {}
    for item in statement.items:
        if item.local_name not in item_map:
            item_map[item.local_name] = item

    rows: list[DisplayRow] = []
    seen_concepts: set[str] = set()

    for entry in concept_set.concepts:
        if entry.is_abstract:
            label = abstract_labels.get(entry.concept, entry.concept)
            rows.append(DisplayRow(
                label=label,
                value=None,
                concept=entry.concept,
                depth=entry.depth,
                is_abstract=True,
                is_total=False,
            ))
        else:
            li = item_map.get(entry.concept)
            if li is None:
                # ConceptSet に存在するが FS にない科目 → スキップ
                continue
            seen_concepts.add(entry.concept)
            rows.append(DisplayRow(
                label=li.label_ja.text,
                value=li.value,
                concept=entry.concept,
                depth=entry.depth,
                is_abstract=False,
                is_total=entry.is_total,
            ))

    # FS にあるが ConceptSet にない科目 → 末尾に追加
    for item in statement.items:
        if item.local_name not in seen_concepts:
            rows.append(DisplayRow(
                label=item.label_ja.text,
                value=item.value,
                concept=item.local_name,
                depth=0,
                is_abstract=False,
                is_total=False,
            ))

    return rows


def render_hierarchical_statement(
    statement: FinancialStatement,
    concept_set: ConceptSet | None = None,
    *,
    abstract_labels: dict[str, str] | None = None,
) -> Table:
    """階層表示の Rich Table を返す。

    Args:
        statement: 財務諸表。
        concept_set: ConceptSet。
        abstract_labels: abstract 科目のラベル辞書。

    Returns:
        Rich Table オブジェクト。
    """
    from rich.table import Table as RichTable

    from edinet.display.rich import _build_title

    rows = build_display_rows(statement, concept_set, abstract_labels=abstract_labels)

    title = _build_title(statement)
    table = RichTable(title=title, title_style="bold", show_lines=False)
    table.add_column("科目", style="cyan", min_width=20)
    table.add_column("金額", justify="right", style="green", min_width=20)
    table.add_column("concept", style="dim", no_wrap=True)

    for row in rows:
        indent = "  " * row.depth
        label = f"{indent}{row.label}"

        if row.is_abstract:
            table.add_row(
                f"[bold cyan]{label}[/bold cyan]",
                "",
                f"[dim]{row.concept}[/dim]",
            )
        elif row.is_total:
            if isinstance(row.value, Decimal):
                value_str = f"[bold green]{row.value:,}[/bold green]"
            else:
                value_str = ""
            table.add_row(
                f"[bold]{label}[/bold]",
                value_str,
                row.concept,
            )
        else:
            if isinstance(row.value, Decimal):
                value_str = f"{row.value:,}"
            elif row.value is None:
                value_str = "—"
            else:
                value_str = str(row.value)
            table.add_row(label, value_str, row.concept)

    return table

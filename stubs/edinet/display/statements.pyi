from dataclasses import dataclass
from decimal import Decimal
from edinet.models.financial import FinancialStatement
from edinet.xbrl.taxonomy.concept_sets import ConceptSet
from rich.table import Table

__all__ = ['DisplayRow', 'build_display_rows', 'render_hierarchical_statement']

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

def build_display_rows(statement: FinancialStatement, concept_set: ConceptSet | None = None, *, abstract_labels: dict[str, str] | None = None) -> list[DisplayRow]:
    """ConceptSet をマージして表示行を生成する。

    Args:
        statement: 財務諸表。
        concept_set: ConceptSet。None の場合はフラット表示。
        abstract_labels: abstract 科目のラベル辞書。

    Returns:
        DisplayRow のリスト。
    """
def render_hierarchical_statement(statement: FinancialStatement, concept_set: ConceptSet | None = None, *, abstract_labels: dict[str, str] | None = None) -> Table:
    """階層表示の Rich Table を返す。

    Args:
        statement: 財務諸表。
        concept_set: ConceptSet。
        abstract_labels: abstract 科目のラベル辞書。

    Returns:
        Rich Table オブジェクト。
    """

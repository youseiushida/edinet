from edinet.models.financial import FinancialStatement
from edinet.xbrl.taxonomy.concept_sets import ConceptSet

__all__ = ['to_html']

def to_html(statement: FinancialStatement, *, concept_set: ConceptSet | None = None, abstract_labels: dict[str, str] | None = None) -> str:
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

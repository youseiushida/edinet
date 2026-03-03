from edinet.models.financial import StatementType
from edinet.xbrl.dei import AccountingStandard
from edinet.xbrl.taxonomy.concept_sets import ConceptSet
from pathlib import Path

__all__ = ['get_concept_set', 'get_known_concepts', 'get_concept_order']

def get_known_concepts(standard: AccountingStandard | None, statement_type: StatementType, *, taxonomy_root: Path | None = None, industry_code: str | None = None) -> frozenset[str]:
    """指定基準・諸表種別の既知概念集合を返す。

    ``taxonomy_root`` が指定されている場合、concept_sets（Presentation
    Linkbase 動的導出）を優先的に使用する。指定がない場合は
    インラインのレガシー概念リストにフォールバック。

    Args:
        standard: 会計基準。``None`` / ``UNKNOWN`` は J-GAAP にフォールバック。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。指定時は concept_sets を優先。
            存在しないパスを指定した場合は ``EdinetConfigError``。
        industry_code: 業種コード。``None`` は一般事業会社。

    Returns:
        concept ローカル名の frozenset。

    Raises:
        EdinetConfigError: ``taxonomy_root`` が存在しないパスの場合。
    """
def get_concept_order(standard: AccountingStandard | None, statement_type: StatementType, *, taxonomy_root: Path | None = None, industry_code: str | None = None) -> dict[str, int]:
    """指定基準・諸表種別の表示順序マッピングを返す。

    ``taxonomy_root`` が指定されている場合、concept_sets（Presentation
    Linkbase 動的導出）を優先的に使用する。

    Args:
        standard: 会計基準。``None`` / 未知は J-GAAP フォールバック。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。指定時は concept_sets を優先。
            存在しないパスを指定した場合は ``EdinetConfigError``。
        industry_code: 業種コード。``None`` は一般事業会社。

    Returns:
        ``{concept_local_name: display_order}`` の辞書。

    Raises:
        EdinetConfigError: ``taxonomy_root`` が存在しないパスの場合。
    """
def get_concept_set(standard: AccountingStandard | None, statement_type: StatementType, taxonomy_root: Path, industry_code: str | None = None) -> ConceptSet | None:
    """指定基準・諸表種別の ConceptSet を返す。

    ``_get_concept_set()`` の公開ラッパー。
    階層表示（display/statements）等で ConceptSet を直接取得する場合に使用する。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード。``None`` は一般事業会社。

    Returns:
        ConceptSet。取得できなかった場合は ``None``。
    """

from edinet.models.financial import StatementType
from edinet.xbrl.dei import AccountingStandard
from edinet.xbrl.taxonomy.concept_sets import ConceptSet
from pathlib import Path

__all__ = ['get_canonical_key', 'get_concept_for_key', 'get_concept_set', 'get_known_concepts', 'get_concept_order', 'cross_standard_lookup', 'get_canonical_key_for_sector']

def get_canonical_key(local_name: str, standard: AccountingStandard | None = None) -> str | None:
    '''concept ローカル名から正規化キーを返す。

    Args:
        local_name: タクソノミの concept ローカル名
            （例: ``"NetSales"``, ``"RevenueIFRS"``）。
        standard: 検索対象の会計基準。``None`` の場合は
            J-GAAP → IFRS の順で全基準を検索する。

    Returns:
        正規化キー（例: ``"revenue"``）。見つからなければ ``None``。
    '''
def get_concept_for_key(canonical_key: str, target_standard: AccountingStandard) -> str | None:
    '''正規化キーから対象基準の concept ローカル名を返す。

    Args:
        canonical_key: 正規化キー（例: ``"revenue"``）。
        target_standard: 対象の会計基準。

    Returns:
        concept ローカル名。見つからなければ ``None``。
    '''
def get_known_concepts(standard: AccountingStandard | None, statement_type: StatementType, *, taxonomy_root: Path | None = None, industry_code: str | None = None) -> frozenset[str]:
    """指定基準・諸表種別の既知概念集合を返す。

    ``taxonomy_root`` が指定されている場合、concept_sets（Presentation
    Linkbase 動的導出）を優先的に使用する。指定がない場合は jgaap/ifrs の
    ハードコードにフォールバック。

    ``taxonomy_root`` が指定されたがパスが存在しない場合は
    ``EdinetConfigError`` が発生する（サイレントフォールバックはしない）。

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

    ``taxonomy_root`` が指定されたがパスが存在しない場合は
    ``EdinetConfigError`` が発生する。

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
def cross_standard_lookup(local_name: str, source_standard: AccountingStandard, target_standard: AccountingStandard) -> str | None:
    """会計基準間で概念を変換する。

    ``source_standard`` の ``local_name`` に対応する
    ``target_standard`` の concept ローカル名を返す。

    Args:
        local_name: 変換元の concept ローカル名。
        source_standard: 変換元の会計基準。
        target_standard: 変換先の会計基準。

    Returns:
        変換先の concept ローカル名。変換できなければ ``None``。
    """
def get_canonical_key_for_sector(local_name: str, standard: AccountingStandard | None = None, industry_code: str | None = None) -> str | None:
    """業種考慮の canonical_key 解決。

    sector レジストリを先に検索し、見つからなければ jgaap にフォールバック。

    Args:
        local_name: concept ローカル名。
        standard: 会計基準。
        industry_code: 業種コード。None は一般事業会社。

    Returns:
        正規化キー。見つからなければ None。
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

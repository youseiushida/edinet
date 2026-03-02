from _typeshed import Incomplete
from edinet.financial.sector._base import SectorConceptMapping, SectorProfile

__all__ = ['BANKING_INDUSTRY_CODES', 'BankingConceptMapping', 'all_mappings', 'all_sector_keys', 'banking_specific_concepts', 'banking_to_general_map', 'from_general_key', 'general_equivalent', 'get_profile', 'is_banking_concept', 'is_banking_industry', 'lookup', 'registry', 'reverse_lookup', 'sector_key', 'to_general_key']

BankingConceptMapping = SectorConceptMapping
BANKING_INDUSTRY_CODES: frozenset[str]
registry: Incomplete
lookup: Incomplete
sector_key: Incomplete
reverse_lookup: Incomplete
all_mappings: Incomplete
all_sector_keys: Incomplete
to_general_key: Incomplete
from_general_key: Incomplete

def is_banking_concept(concept: str) -> bool:
    """指定した concept が銀行業固有のものかを判定する。

    ``general_equivalent`` が None のマッピング（一般事業会社に対応がないもの）
    を銀行業固有科目とみなす。

    Args:
        concept: タクソノミのローカル名。

    Returns:
        銀行業固有の concept であれば True。
    """
def banking_specific_concepts() -> tuple[SectorConceptMapping, ...]:
    """銀行業固有の概念（一般事業会社に対応がないもの）を返す。

    ``general_equivalent`` が None のマッピングのみを返す。
    定義順（PL → BS → CF）を維持。

    Returns:
        銀行業固有の SectorConceptMapping のタプル。
    """
def general_equivalent(concept: str) -> str | None:
    """銀行業 concept の一般事業会社における canonical_key を返す。

    Args:
        concept: タクソノミのローカル名。

    Returns:
        一般事業会社の canonical_key。対応がない場合は None。
        未登録の concept の場合も None。
    """
def banking_to_general_map() -> dict[str, str]:
    """銀行業 sector_key → 一般事業会社 canonical_key のマッピング辞書を返す。

    ``general_equivalent`` が設定されているマッピングのみを含む。

    Returns:
        ``{banking_sector_key: general_canonical_key}`` の辞書。
    """
def get_profile() -> SectorProfile:
    """銀行業のプロファイルを返す。

    Returns:
        SectorProfile インスタンス。
    """
def is_banking_industry(industry_code: str) -> bool:
    """業種コードが銀行業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        銀行業であれば True。
    """

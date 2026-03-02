from _typeshed import Incomplete
from edinet.financial.sector._base import SectorConceptMapping, SectorProfile

__all__ = ['INSURANCE_INDUSTRY_CODES', 'InsuranceConceptMapping', 'all_mappings', 'all_sector_keys', 'from_general_key', 'get_profile', 'insurance_specific_concepts', 'insurance_to_general_map', 'is_insurance_industry', 'lookup', 'registry', 'reverse_lookup', 'sector_key', 'to_general_key']

InsuranceConceptMapping = SectorConceptMapping
INSURANCE_INDUSTRY_CODES: frozenset[str]
registry: Incomplete
lookup: Incomplete
sector_key: Incomplete
reverse_lookup: Incomplete
all_mappings: Incomplete
all_sector_keys: Incomplete
to_general_key: Incomplete
from_general_key: Incomplete

def insurance_specific_concepts() -> tuple[SectorConceptMapping, ...]:
    """保険業固有の概念（一般事業会社に対応がないもの）を返す。

    ``general_equivalent`` が None のマッピングのみを返す。
    定義順（PL → BS → CF）を維持。

    Returns:
        保険業固有の SectorConceptMapping のタプル。
    """
def is_insurance_industry(industry_code: str) -> bool:
    """業種コードが保険業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        保険業であれば True。
    """
def insurance_to_general_map() -> dict[str, str]:
    """保険業 sector_key → 一般事業会社 canonical_key のマッピング辞書を返す。

    ``general_equivalent`` が設定されているマッピングのみを含む。

    Returns:
        ``{insurance_sector_key: general_canonical_key}`` の辞書。
    """
def get_profile() -> SectorProfile:
    """保険業のプロファイルを取得する。

    Returns:
        SectorProfile インスタンス。
    """

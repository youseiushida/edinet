from _typeshed import Incomplete

__all__ = ['CONSTRUCTION_INDUSTRY_CODES', 'all_mappings', 'all_sector_keys', 'from_general_key', 'get_profile', 'is_construction_industry', 'lookup', 'registry', 'reverse_lookup', 'sector_key', 'to_general_key']

CONSTRUCTION_INDUSTRY_CODES: frozenset[str]
registry: Incomplete
lookup: Incomplete
sector_key: Incomplete
reverse_lookup: Incomplete
all_mappings: Incomplete
all_sector_keys: Incomplete
get_profile: Incomplete
to_general_key: Incomplete
from_general_key: Incomplete

def is_construction_industry(industry_code: str) -> bool:
    """業種コードが建設業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        建設業であれば True。
    """

from edinet.financial.sector._base import SectorConceptMapping as SectorConceptMapping, SectorProfile as SectorProfile, SectorRegistry as SectorRegistry

__all__ = ['SectorConceptMapping', 'SectorProfile', 'SectorRegistry', 'get_sector_registry', 'supported_industry_codes']

def get_sector_registry(industry_code: str) -> SectorRegistry | None:
    '''業種コードから対応する SectorRegistry を返す。

    Args:
        industry_code: 業種コード（例: ``"bk1"``, ``"cns"``, ``"in1"``）。

    Returns:
        SectorRegistry。未登録の業種コードの場合は None。
    '''
def supported_industry_codes() -> frozenset[str]:
    """サポートされている全業種コードの集合を返す。

    Returns:
        業種コードのフローズンセット。
    """

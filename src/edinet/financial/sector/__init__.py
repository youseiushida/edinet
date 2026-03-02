"""業種固有タクソノミサブパッケージ。

5 つの業種モジュール（banking / insurance / construction / railway / securities）を
統一的にルーティングする。

典型的な使用例::

    from edinet.financial.sector import get_sector_registry, supported_industry_codes

    reg = get_sector_registry("bk1")
    if reg is not None:
        m = reg.lookup("OrdinaryIncomeBNK")
"""

from __future__ import annotations

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)

__all__ = [
    "SectorConceptMapping",
    "SectorProfile",
    "SectorRegistry",
    "get_sector_registry",
    "supported_industry_codes",
]

# ---------------------------------------------------------------------------
# 全業種 Registry のルーティング
# ---------------------------------------------------------------------------

_REGISTRY_MAP: dict[str, SectorRegistry] = {}


def _register_all() -> None:
    """全業種の registry を辞書登録する。"""
    from edinet.financial.sector import banking, construction, insurance, railway, securities

    for module in (banking, construction, insurance, railway, securities):
        reg: SectorRegistry = module.registry
        for code in reg.get_profile().industry_codes:
            _REGISTRY_MAP[code] = reg


_register_all()


def get_sector_registry(industry_code: str) -> SectorRegistry | None:
    """業種コードから対応する SectorRegistry を返す。

    Args:
        industry_code: 業種コード（例: ``"bk1"``, ``"cns"``, ``"in1"``）。

    Returns:
        SectorRegistry。未登録の業種コードの場合は None。
    """
    return _REGISTRY_MAP.get(industry_code)


def supported_industry_codes() -> frozenset[str]:
    """サポートされている全業種コードの集合を返す。

    Returns:
        業種コードのフローズンセット。
    """
    return frozenset(_REGISTRY_MAP)

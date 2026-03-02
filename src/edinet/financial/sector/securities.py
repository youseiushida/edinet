"""証券業（sec）の業種固有 sector_key マッピング。

証券業は PL 構造が一般事業会社と大きく異なり、営業収益・純営業収益の
二段階構造を取る。BS も信用取引関連の固有科目を持つ。

対象業種コード: ``sec``（証券業、金融商品取引業）。

典型的な使用例::

    from edinet.financial.sector.securities import registry, lookup, sector_key

    # 証券業固有の concept → 正規化キー
    m = lookup("OperatingRevenueSEC")
    assert m is not None
    assert m.sector_key == "operating_revenue_sec"

    # 一般事業会社との対応関係
    assert m.general_equivalent == "revenue"

    # 逆引き: 一般事業会社の "revenue" → 証券業の概念
    rev = registry.from_general_key("revenue")
    assert len(rev) == 1
    assert rev[0].concept == "OperatingRevenueSEC"
"""

from __future__ import annotations

from edinet.financial.sector._base import (
    SectorConceptMapping,
    SectorProfile,
    SectorRegistry,
)
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    "SECURITIES_INDUSTRY_CODES",
    "all_mappings",
    "all_sector_keys",
    "from_general_key",
    "get_profile",
    "is_securities_industry",
    "lookup",
    "registry",
    "reverse_lookup",
    "sector_key",
    "to_general_key",
]

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

SECURITIES_INDUSTRY_CODES: frozenset[str] = frozenset({"sec"})
"""証券業の業種コード集合。"""

_CODES = SECURITIES_INDUSTRY_CODES

# ---------------------------------------------------------------------------
# プロファイル
# ---------------------------------------------------------------------------

_PROFILE = SectorProfile(
    sector_id="securities",
    display_name_ja="証券業",
    display_name_en="Securities",
    industry_codes=_CODES,
    concept_suffix="SEC",
    pl_structure_note="営業収益→純営業収益の二段階構造。"
    "金融収益・金融費用を差し引いて純営業収益を算出する。",
)

# ---------------------------------------------------------------------------
# PL マッピング（8 概念）
# ---------------------------------------------------------------------------

_PL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OperatingRevenueSEC",
        sector_key="operating_revenue_sec",
        industry_codes=_CODES,
        general_equivalent=CK.REVENUE,
    ),
    SectorConceptMapping(
        concept="CommissionReceivedORSEC",
        sector_key="commission_received_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="NetTradingIncomeORSEC",
        sector_key="net_trading_income_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="FinancialRevenueORSEC",
        sector_key="financial_revenue_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="FinancialExpensesSEC",
        sector_key="financial_expenses_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="NetOperatingRevenueSEC",
        sector_key="net_operating_revenue_sec",
        industry_codes=_CODES,
        general_equivalent=CK.GROSS_PROFIT,
    ),
    SectorConceptMapping(
        concept="SellingGeneralAndAdministrativeExpenses",
        sector_key="sga_expenses_sec",
        industry_codes=_CODES,
        general_equivalent=CK.SGA_EXPENSES,
    ),
    SectorConceptMapping(
        concept="OperatingIncome",
        sector_key="operating_income_sec",
        industry_codes=_CODES,
        general_equivalent=CK.OPERATING_INCOME,
    ),
)

# ---------------------------------------------------------------------------
# BS マッピング（5 概念）
# ---------------------------------------------------------------------------

_BS_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="TradingProductsCASEC",
        sector_key="trading_products_assets_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="TradingProductsCLSEC",
        sector_key="trading_products_liab_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="MarginTransactionAssetsCASEC",
        sector_key="margin_transaction_assets_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="MarginTransactionLiabilitiesCLSEC",
        sector_key="margin_transaction_liab_sec",
        industry_codes=_CODES,
    ),
    SectorConceptMapping(
        concept="CashSegregatedAsDepositsCASEC",
        sector_key="cash_segregated_sec",
        industry_codes=_CODES,
    ),
)

# ---------------------------------------------------------------------------
# レジストリ構築
# ---------------------------------------------------------------------------

_ALL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    *_PL_MAPPINGS,
    *_BS_MAPPINGS,
)

registry = SectorRegistry(profile=_PROFILE, mappings=_ALL_MAPPINGS)
"""証券業の SectorRegistry インスタンス。"""

# ---------------------------------------------------------------------------
# 公開 API（レジストリへのデリゲート）
# ---------------------------------------------------------------------------

lookup = registry.lookup
sector_key = registry.sector_key
reverse_lookup = registry.reverse_lookup
all_mappings = registry.all_mappings
all_sector_keys = registry.all_sector_keys
get_profile = registry.get_profile
to_general_key = registry.to_general_key
from_general_key = registry.from_general_key


def is_securities_industry(industry_code: str) -> bool:
    """業種コードが証券業かどうかを判定する。

    Args:
        industry_code: 業種コード。

    Returns:
        証券業であれば True。
    """
    return industry_code in SECURITIES_INDUSTRY_CODES

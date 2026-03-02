"""府令コード (ordinanceCode) の Enum 定義。"""
from __future__ import annotations

import warnings
from enum import Enum

from edinet.exceptions import EdinetWarning


class OrdinanceCode(str, Enum):
    """EDINET 府令コード。"""

    DISCLOSURE = "010"
    INTERNAL_CONTROL = "015"
    FOREIGN_ISSUERS = "020"
    SPECIFIED_SECURITIES = "030"
    TENDER_OFFER = "040"
    ISSUER_TENDER_OFFER = "050"
    LARGE_SHAREHOLDING = "060"

    @property
    def name_ja(self) -> str:
        """日本語名称。"""
        return _ORDINANCE_CODE_NAMES_JA[self.value]

    @classmethod
    def from_code(cls, code: str) -> OrdinanceCode | None:
        """コード文字列から OrdinanceCode を返す。未知コードは None + warning。"""
        try:
            return cls(code)
        except ValueError:
            if code not in _warned_unknown_ordinance_codes:
                _warned_unknown_ordinance_codes.add(code)
                warnings.warn(
                    f"Unknown ordinanceCode: '{code}'.",
                    category=EdinetWarning,
                    stacklevel=2,
                )
            return None


_warned_unknown_ordinance_codes: set[str] = set()


def _reset_warning_state() -> None:
    """テスト用: warning 抑制状態をリセットする。"""
    _warned_unknown_ordinance_codes.clear()


_ORDINANCE_CODE_NAMES_JA: dict[str, str] = {
    "010": "企業内容等の開示に関する内閣府令",
    "015": "財務計算に関する書類その他の情報の適正性を確保するための体制に関する内閣府令",
    "020": "外国債等の発行者の開示に関する内閣府令",
    "030": "特定有価証券の内容等の開示に関する内閣府令",
    "040": "発行者以外の者による株券等の公開買付けの開示に関する内閣府令",
    "050": "発行者による上場株券等の公開買付けの開示に関する内閣府令",
    "060": "株券等の大量保有の状況の開示に関する内閣府令",
}


OFFICIAL_CODES: tuple[str, ...] = tuple(sorted(_ORDINANCE_CODE_NAMES_JA.keys()))

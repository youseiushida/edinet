from edinet.exceptions import EdinetWarning as EdinetWarning
from enum import Enum

class OrdinanceCode(str, Enum):
    """EDINET 府令コード。"""
    DISCLOSURE = '010'
    INTERNAL_CONTROL = '015'
    FOREIGN_ISSUERS = '020'
    SPECIFIED_SECURITIES = '030'
    TENDER_OFFER = '040'
    ISSUER_TENDER_OFFER = '050'
    LARGE_SHAREHOLDING = '060'
    @property
    def name_ja(self) -> str:
        """日本語名称。"""
    @classmethod
    def from_code(cls, code: str) -> OrdinanceCode | None:
        """コード文字列から OrdinanceCode を返す。未知コードは None + warning。"""

OFFICIAL_CODES: tuple[str, ...]

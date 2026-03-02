from edinet.exceptions import EdinetWarning as EdinetWarning
from enum import Enum

class DocType(str, Enum):
    '''EDINET 書類種別コード。

    str を継承しているため、文字列として比較可能:
        DocType.ANNUAL_SECURITIES_REPORT == "120"  # True

    Attributes:
        name_ja: 日本語名称（API 仕様書準拠）
        original: 訂正版の場合、原本の DocType。原本自身は None
        is_correction: 訂正報告書かどうか
    '''
    SECURITIES_NOTIFICATION = '010'
    SECURITIES_CHANGE_NOTIFICATION = '020'
    SECURITIES_REGISTRATION = '030'
    AMENDED_SECURITIES_REGISTRATION = '040'
    WITHDRAWAL_OF_REGISTRATION = '050'
    SHELF_REGISTRATION_NOTICE = '060'
    SHELF_REGISTRATION_CHANGE_NOTIFICATION = '070'
    SHELF_REGISTRATION_STATEMENT = '080'
    AMENDED_SHELF_REGISTRATION_STATEMENT = '090'
    SHELF_REGISTRATION_SUPPLEMENTS = '100'
    WITHDRAWAL_OF_SHELF_REGISTRATION = '110'
    ANNUAL_SECURITIES_REPORT = '120'
    AMENDED_ANNUAL_SECURITIES_REPORT = '130'
    CONFIRMATION_LETTER = '135'
    AMENDED_CONFIRMATION_LETTER = '136'
    QUARTERLY_REPORT = '140'
    AMENDED_QUARTERLY_REPORT = '150'
    SEMIANNUAL_REPORT = '160'
    AMENDED_SEMIANNUAL_REPORT = '170'
    EXTRAORDINARY_REPORT = '180'
    AMENDED_EXTRAORDINARY_REPORT = '190'
    PARENT_COMPANY_STATUS_REPORT = '200'
    AMENDED_PARENT_COMPANY_STATUS_REPORT = '210'
    SHARE_BUYBACK_STATUS_REPORT = '220'
    AMENDED_SHARE_BUYBACK_STATUS_REPORT = '230'
    INTERNAL_CONTROL_REPORT = '235'
    AMENDED_INTERNAL_CONTROL_REPORT = '236'
    TENDER_OFFER_REGISTRATION = '240'
    AMENDED_TENDER_OFFER_REGISTRATION = '250'
    TENDER_OFFER_WITHDRAWAL = '260'
    TENDER_OFFER_REPORT = '270'
    AMENDED_TENDER_OFFER_REPORT = '280'
    OPINION_REPORT = '290'
    AMENDED_OPINION_REPORT = '300'
    TENDER_OFFER_ANSWER_REPORT = '310'
    AMENDED_TENDER_OFFER_ANSWER_REPORT = '320'
    SEPARATE_PURCHASE_PROHIBITION_EXCEPTION = '330'
    AMENDED_SEPARATE_PURCHASE_PROHIBITION_EXCEPTION = '340'
    LARGE_SHAREHOLDING_REPORT = '350'
    AMENDED_LARGE_SHAREHOLDING_REPORT = '360'
    STATUS_REPORT_AS_OF_RECORD_DATE = '370'
    CHANGE_REPORT = '380'
    @property
    def name_ja(self) -> str:
        """日本語名称（API 仕様書準拠）。"""
    @property
    def original(self) -> DocType | None:
        """訂正版の場合、原本の DocType を返す。原本自身は None。"""
    @property
    def is_correction(self) -> bool:
        """訂正報告書かどうか。"""
    @classmethod
    def from_code(cls, code: str) -> DocType | None:
        """コード文字列から DocType を返す。未知のコードは None + warning。

        edinet-tools は未知のコードをサイレントに除外していた。
        このメソッドは未知のコードを warning で通知し、
        呼び出し元が判断できるようにする。

        同一コードに対する warning は同一 Python プロセス内で1回だけ出す（スパム防止）。
        API レスポンスに未知コードが大量に含まれるケース
        （将来のコード追加・API 側の一時的不整合）でログが溢れない。

        Args:
            code: 書類種別コード。「010」「120」のような3桁ゼロ埋め文字列。
                  EDINET API は常に3桁文字列で返すため、int や非ゼロ埋め（「10」等）は
                  未知コード扱いになる。

        Returns:
            対応する DocType。未知のコードは None。
        """

OFFICIAL_CODES: tuple[str, ...]

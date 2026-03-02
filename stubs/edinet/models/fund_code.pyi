from _typeshed import Incomplete
from edinet.exceptions import EdinetWarning as EdinetWarning
from pydantic import BaseModel

class FundCodeEntry(BaseModel):
    """ファンドコードリストの1行。"""
    model_config: Incomplete
    fund_code: str
    sec_code: str | None
    fund_name: str
    fund_name_yomi: str
    security_type: str
    period_1: str | None
    period_2: str | None
    edinet_code: str
    issuer_name: str

FUND_CODE_RECORD_COUNT: Incomplete

def get_fund_code(code: str) -> FundCodeEntry | None:
    """ファンドコードから FundCodeEntry を返す。"""
def all_fund_codes() -> list[FundCodeEntry]:
    """全ファンドコードの一覧を返す。"""

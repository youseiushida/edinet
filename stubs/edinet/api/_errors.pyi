from edinet.exceptions import EdinetAPIError as EdinetAPIError
from typing import Any

def parse_api_error_response(response: Any, *, default_status_code: int = 0) -> tuple[int, str]:
    """EDINET API の JSON エラーボディを解釈して (status_code, message) を返す。

    この関数は例外を送出せず、常に安全なフォールバック値を返す。
    """
def raise_for_api_error_response(response: Any, *, default_status_code: int = 0) -> None:
    """parse_api_error_response() の結果に基づいて EdinetAPIError を送出する。"""

from edinet.api._errors import raise_for_api_error_response as raise_for_api_error_response
from typing import Any

def get_documents(date: str, *, include_details: bool = True) -> dict[str, Any]:
    '''指定日の提出書類一覧を取得する。

    Args:
        date:
            ファイル日付（YYYY-MM-DD 形式）。
            当日以前で、10年を経過していない日付。
            土日祝日も指定可能。
        include_details:
            True  → type=2「提出書類一覧及びメタデータ」を取得（デフォルト）
            False → type=1「メタデータのみ」を取得

    Returns:
        EDINET API のレスポンス JSON（dict）。

    Raises:
        EdinetConfigError: API キーが未設定。
        EdinetAPIError: EDINET API がエラーを返した（HTTP エラーまたは
                        レスポンス JSON の metadata.status が "200" 以外）。

    Examples:
        >>> result = get_documents("2026-02-07")
        >>> result["metadata"]["resultset"]["count"]
        42
        >>> result["results"][0]["docID"]
        \'S100XXXX\'
    '''
async def aget_documents(date: str, *, include_details: bool = True) -> dict[str, Any]:
    '''指定日の提出書類一覧を非同期で取得する。

    Args:
        date:
            ファイル日付（YYYY-MM-DD 形式）。
            当日以前で、10年を経過していない日付。
            土日祝日も指定可能。
        include_details:
            True  → type=2「提出書類一覧及びメタデータ」を取得（デフォルト）
            False → type=1「メタデータのみ」を取得

    Returns:
        EDINET API のレスポンス JSON（dict）。

    Raises:
        EdinetConfigError: API キーが未設定。
        EdinetAPIError: EDINET API がエラーを返した（HTTP エラーまたは
                        レスポンス JSON の metadata.status が "200" 以外）。
    '''

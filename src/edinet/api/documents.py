"""EDINET 書類一覧 API (documents API) のラッパー。"""
from __future__ import annotations

from typing import Any

from edinet import _http
from edinet.api._errors import raise_for_api_error_response


def _validate_documents_response(response: Any) -> dict[str, Any]:
    """get_documents / aget_documents 共通のレスポンス検証。

    Args:
        response: HTTP レスポンス。

    Returns:
        検証済みの API レスポンス dict。

    Raises:
        EdinetAPIError: レスポンスが不正な場合。
    """
    try:
        data = response.json()
    except Exception:  # noqa: BLE001
        raise_for_api_error_response(response, default_status_code=response.status_code)

    if not isinstance(data, dict):
        raise_for_api_error_response(response, default_status_code=response.status_code)

    # 401 形式の検査（API 仕様書 §3-3 参照）。
    # 401 だけ JSON 構造が異なる: {"StatusCode": 401, "message": "..."} 。
    # metadata 構造ではないため、先に検査する。
    if "StatusCode" in data or "statusCode" in data:
        raise_for_api_error_response(response, default_status_code=response.status_code)

    # EDINET API は HTTP 200 を返しつつ JSON の metadata.status が
    # "200" 以外のケースがありうる。HTTP ステータスだけでは不十分なので
    # JSON レベルでもステータスを検査する。
    metadata = data.get("metadata")
    status = str(metadata.get("status", "")) if isinstance(metadata, dict) else ""
    if status != "200":
        raise_for_api_error_response(response, default_status_code=response.status_code)

    return data


def get_documents(date: str, *, include_details: bool = True) -> dict[str, Any]:
    """指定日の提出書類一覧を取得する。

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
        'S100XXXX'
    """
    response = _http.get(
        "/documents.json",
        params={
            "date": date,
            "type": "2" if include_details else "1",
        },
    )
    return _validate_documents_response(response)


async def aget_documents(date: str, *, include_details: bool = True) -> dict[str, Any]:
    """指定日の提出書類一覧を非同期で取得する。

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
    """
    response = await _http.aget(
        "/documents.json",
        params={
            "date": date,
            "type": "2" if include_details else "1",
        },
    )
    return _validate_documents_response(response)

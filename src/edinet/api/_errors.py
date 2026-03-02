"""EDINET API の JSON エラー解釈ヘルパー。"""
from __future__ import annotations

from typing import Any

from edinet.exceptions import EdinetAPIError


def parse_api_error_response(
    response: Any,
    *,
    default_status_code: int = 0,
) -> tuple[int, str]:
    """EDINET API の JSON エラーボディを解釈して (status_code, message) を返す。

    この関数は例外を送出せず、常に安全なフォールバック値を返す。
    """
    fallback_status_code = _coerce_status_code(default_status_code, fallback=0)

    try:
        data = response.json()
    except Exception:  # noqa: BLE001
        return (
            fallback_status_code,
            f"Response is not valid JSON (HTTP {_response_status_code(response)})",
        )

    if not isinstance(data, dict):
        return (
            fallback_status_code,
            f"Response JSON must be an object, got {type(data).__name__}",
        )

    if "StatusCode" in data or "statusCode" in data:
        raw_status = data.get("StatusCode", data.get("statusCode"))
        return (
            _coerce_status_code(raw_status, fallback=fallback_status_code),
            _coerce_message(data.get("message"), fallback="Unknown error"),
        )

    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        return (
            _coerce_status_code(metadata.get("status"), fallback=fallback_status_code),
            _coerce_message(metadata.get("message"), fallback="Unknown error"),
        )

    return (
        fallback_status_code,
        _coerce_message(data.get("message"), fallback="Unknown error"),
    )


def raise_for_api_error_response(
    response: Any,
    *,
    default_status_code: int = 0,
) -> None:
    """parse_api_error_response() の結果に基づいて EdinetAPIError を送出する。"""
    status_code, message = parse_api_error_response(
        response,
        default_status_code=default_status_code,
    )
    raise EdinetAPIError(status_code, message)


def _coerce_status_code(value: Any, *, fallback: int) -> int:
    """ステータスコード候補を整数に正規化する。

    Args:
        value: 正規化対象の値。
        fallback: 変換できない場合に返す代替値。

    Returns:
        int: 正規化後のステータスコード。
    """
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return fallback
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            try:
                return int(stripped)
            except ValueError:
                return fallback
    return fallback


def _coerce_message(value: Any, *, fallback: str) -> str:
    """エラーメッセージ候補を文字列に正規化する。

    Args:
        value: 正規化対象の値。
        fallback: 空値や未設定時に返す代替メッセージ。

    Returns:
        str: 正規化後のメッセージ。
    """
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _response_status_code(response: Any) -> int:
    """レスポンスオブジェクトから status_code を安全に取得する。

    Args:
        response: `status_code` 属性を持つ可能性があるオブジェクト。

    Returns:
        int: 取得または正規化したステータスコード。
    """
    return _coerce_status_code(getattr(response, "status_code", 0), fallback=0)

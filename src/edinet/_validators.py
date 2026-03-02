"""内部入力バリデーションヘルパー。"""
from __future__ import annotations

import re

_EDINET_CODE_PATTERN = re.compile(r"^E\d{5}$")


def normalize_edinet_code(
    value: str | None,
    *,
    allow_none: bool = True,
) -> str | None:
    """edinet_code を正規化して検証する。

    Args:
        value: 入力値。
        allow_none: `None` を許可する場合は `True`。

    Returns:
        正規化済みの EDINET コード。`allow_none=True` かつ `value=None` の場合は `None`。

    Raises:
        ValueError: 型不正、空文字、または `E` + 5桁形式に一致しない場合。
    """
    if value is None:
        if allow_none:
            return None
        raise ValueError("edinet_code must not be None")

    if not isinstance(value, str):
        raise ValueError("edinet_code must be str or None")

    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("edinet_code must not be empty")
    if not _EDINET_CODE_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"Invalid edinet_code: {value!r}. Expected format like 'E02144'.",
        )
    return normalized

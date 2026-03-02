def normalize_edinet_code(value: str | None, *, allow_none: bool = True) -> str | None:
    """edinet_code を正規化して検証する。

    Args:
        value: 入力値。
        allow_none: `None` を許可する場合は `True`。

    Returns:
        正規化済みの EDINET コード。`allow_none=True` かつ `value=None` の場合は `None`。

    Raises:
        ValueError: 型不正、空文字、または `E` + 5桁形式に一致しない場合。
    """

"""共通バリデータのテスト。"""
from __future__ import annotations

import pytest

from edinet._validators import normalize_edinet_code


def test_normalize_edinet_code_accepts_valid_value() -> None:
    """有効な EDINET コードが正規化されること。"""
    assert normalize_edinet_code(" e02144 ") == "E02144"


def test_normalize_edinet_code_allows_none_when_configured() -> None:
    """allow_none=True では None を許可すること。"""
    assert normalize_edinet_code(None) is None


def test_normalize_edinet_code_rejects_none_when_not_allowed() -> None:
    """allow_none=False では None を拒否すること。"""
    with pytest.raises(ValueError, match="must not be None"):
        normalize_edinet_code(None, allow_none=False)


def test_normalize_edinet_code_rejects_invalid_type() -> None:
    """文字列以外を拒否すること。"""
    with pytest.raises(ValueError, match="must be str or None"):
        normalize_edinet_code(7203)  # type: ignore[arg-type]

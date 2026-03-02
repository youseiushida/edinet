"""form_code.py のテスト。"""
from __future__ import annotations

import warnings

import pytest
from pydantic import ValidationError

from edinet.models.ordinance_code import OFFICIAL_CODES
from edinet.models.form_code import (
    FORM_CODE_RECORD_COUNT,
    _FORM_CODE_TABLE,
    _reset_warning_state,
    all_form_codes,
    get_form_code,
)


def setup_function() -> None:
    _reset_warning_state()


def test_form_code_count() -> None:
    assert FORM_CODE_RECORD_COUNT == 413
    assert len(all_form_codes()) == 413


def test_get_form_code_known() -> None:
    entry = get_form_code("010", "010000")
    assert entry is not None
    assert entry.form_name == "有価証券通知書"


def test_get_form_code_unknown() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert get_form_code("010", "999999") is None
        assert len(caught) == 1
        assert "Unknown formCode" in str(caught[0].message)


def test_form_code_entry_frozen() -> None:
    entry = get_form_code("010", "010000")
    assert entry is not None
    with pytest.raises(ValidationError):
        entry.form_name = "x"  # type: ignore[misc]


def test_form_code_ordinance_code_consistency() -> None:
    for entry in all_form_codes():
        assert entry.ordinance_code in OFFICIAL_CODES


def test_disclosure_type_values() -> None:
    allowed = {"開示", "非開示"}
    for entry in all_form_codes():
        assert entry.disclosure_type in allowed


def test_form_code_unique_keys() -> None:
    keys = list(_FORM_CODE_TABLE.keys())
    assert len(keys) == len(set(keys))

"""fund_code.py のテスト。"""
from __future__ import annotations

import warnings

from edinet.models.fund_code import (
    FUND_CODE_RECORD_COUNT,
    _FUND_CODE_TABLE,
    _reset_warning_state,
    all_fund_codes,
    get_fund_code,
)


def setup_function() -> None:
    _reset_warning_state()


def test_fund_code_count() -> None:
    assert FUND_CODE_RECORD_COUNT == 6377
    assert len(all_fund_codes()) == 6377


def test_get_fund_code_known() -> None:
    entry = get_fund_code("G01003")
    assert entry is not None
    assert entry.fund_code == "G01003"
    assert entry.edinet_code.startswith("E")


def test_get_fund_code_unknown() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert get_fund_code("G99999") is None
        assert len(caught) == 1
        assert "Unknown fundCode" in str(caught[0].message)


def test_fund_code_entry_has_edinet_code() -> None:
    for entry in all_fund_codes():
        assert len(entry.edinet_code) == 6
        assert entry.edinet_code.startswith("E")


def test_fund_code_no_duplicate() -> None:
    keys = list(_FUND_CODE_TABLE.keys())
    assert len(keys) == len(set(keys))

"""edinet_code.py の機能テスト。"""
from __future__ import annotations

import warnings

from edinet.models.edinet_code import (
    EDINET_CODE_RECORD_COUNT,
    _EDINET_CODE_TABLE,
    _reset_warning_state,
    all_edinet_codes,
    get_edinet_code,
)


def setup_function() -> None:
    _reset_warning_state()


def test_edinet_code_count() -> None:
    assert EDINET_CODE_RECORD_COUNT == 11223
    assert len(all_edinet_codes()) == 11223


def test_get_edinet_code_known() -> None:
    entry = get_edinet_code("E00004")
    assert entry is not None
    assert entry.submitter_name == "カネコ種苗株式会社"


def test_get_edinet_code_unknown() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert get_edinet_code("E99999") is None
        assert len(caught) == 1
        assert "Unknown edinetCode" in str(caught[0].message)


def test_edinet_code_no_duplicate() -> None:
    keys = list(_EDINET_CODE_TABLE.keys())
    assert len(keys) == len(set(keys))

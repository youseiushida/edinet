"""ordinance_code.py のテスト。"""
from __future__ import annotations

import warnings

from edinet.models.ordinance_code import OFFICIAL_CODES, OrdinanceCode
from edinet.models.ordinance_code import _reset_warning_state


def setup_function() -> None:
    _reset_warning_state()


def test_all_7_ordinance_codes_defined() -> None:
    assert len(OFFICIAL_CODES) == 7
    for code in OFFICIAL_CODES:
        assert OrdinanceCode.from_code(code) is not None


def test_from_code_known() -> None:
    assert OrdinanceCode.from_code("010") == OrdinanceCode.DISCLOSURE


def test_from_code_unknown_returns_none() -> None:
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert OrdinanceCode.from_code("999") is None


def test_from_code_unknown_warns() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert OrdinanceCode.from_code("999") is None
        assert len(caught) == 1
        assert "Unknown ordinanceCode" in str(caught[0].message)


def test_from_code_unknown_warns_once() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        OrdinanceCode.from_code("998")
        OrdinanceCode.from_code("998")
        assert len(caught) == 1


def test_name_ja() -> None:
    for code in OFFICIAL_CODES:
        ordinance = OrdinanceCode(code)
        assert isinstance(ordinance.name_ja, str)
        assert ordinance.name_ja


def test_string_comparison() -> None:
    assert OrdinanceCode.DISCLOSURE == "010"

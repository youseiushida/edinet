"""CK (CanonicalKey) StrEnum のテスト。

StrEnum 特性・命名規則・jgaap/ifrs/sector との整合性を検証する。
"""

from __future__ import annotations

import re

import pytest

from edinet.financial.standards.canonical_keys import CK


_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$")


@pytest.mark.small
@pytest.mark.unit
class TestCKProperties:
    """CK StrEnum の基本プロパティテスト。"""

    def test_t01_all_values_are_snake_case(self) -> None:
        """全 CK 定数の値が小文字 snake_case 文字列。"""
        for member in CK:
            assert _SNAKE_CASE_RE.match(member.value), (
                f"CK.{member.name} の値 '{member.value}' が snake_case でない"
            )

    def test_t02_no_duplicate_values(self) -> None:
        """CK 定数の値に重複がない。"""
        values = [m.value for m in CK]
        assert len(values) == len(set(values))

    def test_t03_all_names_are_upper_snake_case(self) -> None:
        """全 CK 定数の名前が大文字 UPPER_SNAKE_CASE。"""
        for member in CK:
            assert _UPPER_SNAKE_RE.match(member.name), (
                f"CK.{member.name} が UPPER_SNAKE_CASE でない"
            )

    def test_t04_str_equality(self) -> None:
        """CK.REVENUE == "revenue" が True（StrEnum 特性）。"""
        assert CK.REVENUE == "revenue"
        assert CK.NET_INCOME == "net_income"
        assert CK.TOTAL_ASSETS == "total_assets"

    def test_t05_isinstance_str(self) -> None:
        """isinstance(CK.REVENUE, str) が True。"""
        assert isinstance(CK.REVENUE, str)

    def test_t06_reverse_lookup(self) -> None:
        """CK("revenue") が CK.REVENUE を返す。"""
        assert CK("revenue") is CK.REVENUE
        assert CK("net_income") is CK.NET_INCOME

    def test_t07_list_enumeration(self) -> None:
        """list(CK) で全定数を列挙できる。"""
        members = list(CK)
        assert len(members) > 0
        assert all(isinstance(m, CK) for m in members)


@pytest.mark.small
@pytest.mark.unit
class TestCKIntegrity:
    """CK と summary_mappings の整合性テスト。"""

    def test_t08_summary_mappings_all_canonical_keys_in_ck(self) -> None:
        """summary_mappings の全 canonical_key が CK に存在する。"""
        from edinet.financial.standards.summary_mappings import all_summary_mappings

        ck_values = set(CK)
        for m in all_summary_mappings():
            assert m.canonical_key in ck_values, (
                f"summary_mappings の canonical_key '{m.canonical_key}' "
                f"が CK に存在しない（concept: {m.concept}）"
            )

    def test_t09_summary_keys_subset_of_ck(self) -> None:
        """summary_mappings で使用される CK が全て有効。"""
        from edinet.financial.standards.summary_mappings import all_summary_mappings

        summary_keys = {m.canonical_key for m in all_summary_mappings()}
        ck_values = set(CK)
        orphan = summary_keys - ck_values
        assert not orphan, f"CK に存在しないキー: {orphan}"

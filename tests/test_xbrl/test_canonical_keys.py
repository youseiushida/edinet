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
    """CK と jgaap/ifrs/sector の整合性テスト。"""

    def test_t08_jgaap_all_canonical_keys_in_ck(self) -> None:
        """jgaap の全 canonical_key が CK に存在する。"""
        from edinet.financial.standards import jgaap

        ck_values = set(CK)
        for m in jgaap.all_mappings():
            assert m.canonical_key in ck_values, (
                f"jgaap の canonical_key '{m.canonical_key}' が CK に存在しない"
            )

    def test_t09_ifrs_all_canonical_keys_in_ck(self) -> None:
        """ifrs の全 canonical_key が CK に存在する。"""
        from edinet.financial.standards import ifrs

        ck_values = set(CK)
        for m in ifrs.all_mappings():
            assert m.canonical_key in ck_values, (
                f"ifrs の canonical_key '{m.canonical_key}' が CK に存在しない"
            )

    def test_t10_sector_all_general_equivalents_in_ck(self) -> None:
        """sector の全 general_equivalent が CK に存在する。"""
        from edinet.financial.sector import (
            banking,
            construction,
            insurance,
            railway,
            securities,
        )

        ck_values = set(CK)
        for module in (banking, construction, insurance, railway, securities):
            for m in module.all_mappings():
                if m.general_equivalent is not None:
                    assert m.general_equivalent in ck_values, (
                        f"{module.__name__} の general_equivalent "
                        f"'{m.general_equivalent}' が CK に存在しない"
                    )

    def test_t11_jgaap_ifrs_shared_keys_use_same_ck(self) -> None:
        """jgaap と ifrs で共有するキーが同一の CK メンバーとして有効。"""
        from edinet.financial.standards import ifrs, jgaap

        jgaap_keys = jgaap.all_canonical_keys()
        ifrs_keys = ifrs.all_canonical_keys()
        shared = jgaap_keys & ifrs_keys
        assert len(shared) > 0, "共有キーが 0 件"
        for key in shared:
            assert key in set(CK), f"共有キー '{key}' が CK に存在しない"

    def test_t12_ck_covers_exactly_union(self) -> None:
        """set(CK) == jgaap_keys | ifrs_keys | _UNMAPPED_CKS（過不足なし）。

        CK は jgaap と ifrs の canonical_key の和集合に加え、
        ConceptMapping で表現できない CK（1 concept : N key のケース）
        を含む。CASH_BEGINNING / CASH_END は CashAndCashEquivalents を
        期首/期末で共有するため ConceptMapping に登録できず、
        statements._absorb_cf_instant_balances() が直接使用する。
        """
        from edinet.financial.standards import ifrs, jgaap

        # ConceptMapping に登録できない CK 定数
        _UNMAPPED_CKS = {CK.CASH_BEGINNING, CK.CASH_END}

        jgaap_keys = jgaap.all_canonical_keys()
        ifrs_keys = ifrs.all_canonical_keys()
        expected = jgaap_keys | ifrs_keys | _UNMAPPED_CKS
        actual = set(CK)
        assert actual == expected, (
            f"差分: CK にのみ存在={actual - expected}, "
            f"jgaap|ifrs にのみ存在={expected - actual}"
        )

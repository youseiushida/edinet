"""test_notes_employees.py — extract_employee_info() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.financial.notes.employees import extract_employee_info
from edinet.financial.statements import build_statements
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import DurationPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

# テスト用名前空間
_NS_JPCRP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)
_NS_JPPFS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)

# 共通期間
_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
)


# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    """テスト用 LabelInfo を構築するヘルパー。"""
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _make_item(
    *,
    local_name: str,
    value: Decimal | str | None,
    namespace_uri: str = _NS_JPCRP,
    label_ja: str = "",
    label_en: str = "",
    order: int = 0,
) -> LineItem:
    """テスト用 LineItem を構築するヘルパー。"""
    return LineItem(
        concept=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        label_ja=_make_label(label_ja or local_name, "ja"),
        label_en=_make_label(label_en or local_name, "en"),
        value=value,
        unit_ref="JPY" if isinstance(value, Decimal) else None,
        decimals=-6 if isinstance(value, Decimal) else None,
        context_id="CurrentYearDuration",
        period=_CUR_DURATION,
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestExtractEmployeeInfoFound:
    """従業員関連概念が全て揃っている場合のテスト。"""

    def test_extract_employee_info_found(self) -> None:
        """全ての従業員関連概念が存在する場合、正しく抽出されること。"""
        items = (
            _make_item(
                local_name="NumberOfEmployees",
                value=Decimal("1500"),
                label_ja="従業員数",
                order=0,
            ),
            _make_item(
                local_name="AverageAgeYearsInformationAboutReportingCompanyInformationAboutEmployees",
                value=Decimal("40.5"),
                label_ja="平均年齢",
                order=1,
            ),
            _make_item(
                local_name="AverageServiceYearsYearsInformationAboutReportingCompanyInformationAboutEmployees",
                value=Decimal("15.3"),
                label_ja="平均勤続年数",
                order=2,
            ),
            _make_item(
                local_name="AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees",
                value=Decimal("6500000"),
                label_ja="平均年間給与",
                order=3,
            ),
            # 無関係な項目（従業員情報以外）
            _make_item(
                local_name="NetSales",
                value=Decimal("1000000000"),
                namespace_uri=_NS_JPPFS,
                label_ja="売上高",
                order=4,
            ),
        )
        stmts = build_statements(items)
        info = extract_employee_info(stmts)

        assert info.count == 1500
        assert info.average_age == Decimal("40.5")
        assert info.average_service_years == Decimal("15.3")
        assert info.average_annual_salary == Decimal("6500000")


@pytest.mark.small
@pytest.mark.unit
class TestExtractEmployeeInfoNotFound:
    """従業員関連概念が存在しない場合のテスト。"""

    def test_extract_employee_info_not_found(self) -> None:
        """従業員関連概念がない場合、全フィールドが None になること。"""
        items = (
            _make_item(
                local_name="NetSales",
                value=Decimal("1000000000"),
                namespace_uri=_NS_JPPFS,
                label_ja="売上高",
            ),
        )
        stmts = build_statements(items)
        info = extract_employee_info(stmts)

        assert info.count is None
        assert info.average_age is None
        assert info.average_service_years is None
        assert info.average_annual_salary is None

    def test_extract_employee_info_empty_statements(self) -> None:
        """空の Statements でも正しく全 None を返すこと。"""
        stmts = build_statements(())
        info = extract_employee_info(stmts)

        assert info.count is None
        assert info.average_age is None
        assert info.average_service_years is None
        assert info.average_annual_salary is None


@pytest.mark.small
@pytest.mark.unit
class TestExtractEmployeeInfoPartial:
    """一部の従業員関連概念のみ存在する場合のテスト。"""

    def test_extract_employee_info_partial(self) -> None:
        """従業員数と平均年齢のみの場合、他は None になること。"""
        items = (
            _make_item(
                local_name="NumberOfEmployees",
                value=Decimal("800"),
                label_ja="従業員数",
                order=0,
            ),
            _make_item(
                local_name="AverageAgeYearsInformationAboutReportingCompanyInformationAboutEmployees",
                value=Decimal("38.2"),
                label_ja="平均年齢",
                order=1,
            ),
        )
        stmts = build_statements(items)
        info = extract_employee_info(stmts)

        assert info.count == 800
        assert info.average_age == Decimal("38.2")
        assert info.average_service_years is None
        assert info.average_annual_salary is None

    def test_extract_employee_info_salary_only(self) -> None:
        """平均年間給与のみの場合のテスト。"""
        items = (
            _make_item(
                local_name="AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees",
                value=Decimal("7000000"),
                label_ja="平均年間給与",
            ),
        )
        stmts = build_statements(items)
        info = extract_employee_info(stmts)

        assert info.count is None
        assert info.average_age is None
        assert info.average_service_years is None
        assert info.average_annual_salary == Decimal("7000000")

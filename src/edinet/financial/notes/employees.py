"""従業員情報の抽出モジュール。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.financial.statements import Statements

__all__ = ["EmployeeInfo", "extract_employee_info"]

# jpcrp_cor の従業員関連概念名
_CONCEPT_NUMBER_OF_EMPLOYEES = "NumberOfEmployees"
_CONCEPT_AVERAGE_AGE = (
    "AverageAgeYearsInformationAboutReportingCompanyInformationAboutEmployees"
)
_CONCEPT_AVERAGE_SERVICE_YEARS = (
    "AverageServiceYearsYearsInformationAboutReportingCompanyInformationAboutEmployees"
)
_CONCEPT_AVERAGE_ANNUAL_SALARY = (
    "AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees"
)


@dataclass(frozen=True, slots=True)
class EmployeeInfo:
    """従業員情報。

    Attributes:
        count: 従業員数。
        average_age: 平均年齢。
        average_service_years: 平均勤続年数。
        average_annual_salary: 平均年間給与。
    """

    count: int | None
    average_age: Decimal | None
    average_service_years: Decimal | None
    average_annual_salary: Decimal | None


def extract_employee_info(stmts: Statements) -> EmployeeInfo:
    """Statements から従業員情報を抽出する。

    提出会社の従業員情報（従業員数、平均年齢、平均勤続年数、平均年間給与）を返す。
    該当する Fact が存在しない場合は各フィールドが None になる。

    Args:
        stmts: 構築済みの Statements オブジェクト。

    Returns:
        EmployeeInfo dataclass。全フィールドが None の場合もある。
    """
    count: int | None = None
    average_age: Decimal | None = None
    average_service_years: Decimal | None = None
    average_annual_salary: Decimal | None = None

    for item in stmts:
        if item.local_name == _CONCEPT_NUMBER_OF_EMPLOYEES:
            if count is None and isinstance(item.value, (Decimal, int)):
                count = int(item.value)
        elif item.local_name == _CONCEPT_AVERAGE_AGE:
            if average_age is None and isinstance(item.value, Decimal):
                average_age = item.value
            elif average_age is None and isinstance(item.value, str):
                try:
                    average_age = Decimal(item.value)
                except InvalidOperation:
                    pass
        elif item.local_name == _CONCEPT_AVERAGE_SERVICE_YEARS:
            if average_service_years is None and isinstance(item.value, Decimal):
                average_service_years = item.value
            elif average_service_years is None and isinstance(item.value, str):
                try:
                    average_service_years = Decimal(item.value)
                except InvalidOperation:
                    pass
        elif item.local_name == _CONCEPT_AVERAGE_ANNUAL_SALARY:
            if average_annual_salary is None and isinstance(item.value, Decimal):
                average_annual_salary = item.value
            elif average_annual_salary is None and isinstance(item.value, str):
                try:
                    average_annual_salary = Decimal(item.value)
                except InvalidOperation:
                    pass

    return EmployeeInfo(
        count=count,
        average_age=average_age,
        average_service_years=average_service_years,
        average_annual_salary=average_annual_salary,
    )

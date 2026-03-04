"""従業員情報の抽出モジュール。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.models.financial import LineItem
    from edinet.financial.statements import Statements

__all__ = ["EmployeeInfo", "extract_employee_info"]

# jpcrp_cor の従業員関連概念名
_CONCEPT_NUMBER_OF_EMPLOYEES = "NumberOfEmployees"
_CONCEPT_AVERAGE_AGE = (
    "AverageAgeYearsInformationAboutReportingCompanyInformationAboutEmployees"
)
_CONCEPT_AVERAGE_SERVICE_YEARS = (
    "AverageLengthOfServiceYearsInformationAboutReportingCompanyInformationAboutEmployees"
)
_CONCEPT_AVERAGE_ANNUAL_SALARY = (
    "AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees"
)

# 提出会社コンテキストの判定用サフィックス
_NON_CONSOLIDATED_SUFFIX = "NonConsolidatedMember"


@dataclass(frozen=True, slots=True)
class EmployeeInfo:
    """従業員情報。

    有価証券報告書「提出会社の状況 ― 従業員の状況」に対応する。
    全フィールドが **提出会社** の **当期** 値に統一される。

    Attributes:
        count: 従業員数。
        average_age: 平均年齢。
        average_service_years: 平均勤続年数。
        average_annual_salary: 平均年間給与（円）。
    """

    count: int | None
    average_age: Decimal | None
    average_service_years: Decimal | None
    average_annual_salary: Decimal | None


def _is_reporting_company(item: LineItem) -> bool:
    """提出会社（NonConsolidatedMember のみ）コンテキストか判定する。"""
    return (
        len(item.dimensions) == 1
        and item.dimensions[0].member.endswith(_NON_CONSOLIDATED_SUFFIX)
    )


def _pick_best(candidates: list[LineItem]) -> LineItem | None:
    """提出会社・当期の値を優先して選択する。

    選択ルール:
      1. NonConsolidatedMember のみの Fact（提出会社）を優先
      2. なければ dimension なし（連結 or 単体のみ企業）にフォールバック
      3. 候補内で InstantPeriod が最新のものを選択
    """
    from edinet.xbrl.contexts import InstantPeriod

    # 提出会社コンテキスト（NonConsolidatedMember のみ）でフィルタ
    reporting = [c for c in candidates if _is_reporting_company(c)]
    # フォールバック: dimension なし（単体のみ企業のケース）
    pool = reporting if reporting else [c for c in candidates if not c.dimensions]
    if not pool:
        return None

    # InstantPeriod の最新を選択
    instant_items = [c for c in pool if isinstance(c.period, InstantPeriod)]
    if instant_items:
        return max(instant_items, key=lambda c: c.period.instant)
    return pool[-1]


def _to_decimal(item: LineItem | None) -> Decimal | None:
    """LineItem の値を Decimal に変換する。"""
    if item is None:
        return None
    if isinstance(item.value, Decimal):
        return item.value
    if isinstance(item.value, str):
        try:
            return Decimal(item.value)
        except InvalidOperation:
            return None
    return None


def extract_employee_info(stmts: Statements) -> EmployeeInfo:
    """Statements から従業員情報を抽出する。

    有価証券報告書の「提出会社の状況 ― 従業員の状況」に対応し、
    提出会社・当期の値を返す。全4概念で提出会社コンテキスト
    （NonConsolidatedMember）を優先し、当期（最新 InstantPeriod）を
    選択する。

    該当する Fact が存在しない場合は各フィールドが None になる。

    Args:
        stmts: 構築済みの Statements オブジェクト。

    Returns:
        EmployeeInfo dataclass。全フィールドが None の場合もある。
    """
    count_candidates: list[LineItem] = []
    age_candidates: list[LineItem] = []
    service_candidates: list[LineItem] = []
    salary_candidates: list[LineItem] = []

    for item in stmts:
        ln = item.local_name
        if ln == _CONCEPT_NUMBER_OF_EMPLOYEES:
            count_candidates.append(item)
        elif ln == _CONCEPT_AVERAGE_AGE:
            age_candidates.append(item)
        elif ln == _CONCEPT_AVERAGE_SERVICE_YEARS:
            service_candidates.append(item)
        elif ln == _CONCEPT_AVERAGE_ANNUAL_SALARY:
            salary_candidates.append(item)

    count_item = _pick_best(count_candidates)
    age_item = _pick_best(age_candidates)
    service_item = _pick_best(service_candidates)
    salary_item = _pick_best(salary_candidates)

    count: int | None = None
    if count_item is not None and isinstance(count_item.value, (Decimal, int)):
        count = int(count_item.value)

    return EmployeeInfo(
        count=count,
        average_age=_to_decimal(age_item),
        average_service_years=_to_decimal(service_item),
        average_annual_salary=_to_decimal(salary_item),
    )

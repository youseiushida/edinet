from dataclasses import dataclass
from decimal import Decimal
from edinet.financial.statements import Statements

__all__ = ['EmployeeInfo', 'extract_employee_info']

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

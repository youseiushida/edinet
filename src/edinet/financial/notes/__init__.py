"""注記・補足情報の抽出モジュール。"""

from edinet.financial.notes.employees import (
    EmployeeInfo as EmployeeInfo,
    extract_employee_info as extract_employee_info,
)

__all__ = [
    "EmployeeInfo",
    "extract_employee_info",
]

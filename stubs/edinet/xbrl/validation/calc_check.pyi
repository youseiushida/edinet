from dataclasses import dataclass
from decimal import Decimal
from edinet.models.financial import FinancialStatement
from edinet.xbrl.linkbase.calculation import CalculationLinkbase
from typing import Literal

__all__ = ['CalcValidationResult', 'ValidationIssue', 'validate_calculations']

@dataclass(frozen=True, slots=True)
class ValidationIssue:
    '''計算バリデーションの個別不一致。

    Attributes:
        role_uri: 計算リンクベースのロール URI。
        parent_concept: 親概念のローカル名（例: ``"GrossProfit"``）。
        expected: 子科目の加重和（計算上の期待値）。
        actual: 実際の Fact 値。
        difference: ``|expected - actual|``。
        tolerance: decimals ベースの許容誤差。
        severity: 深刻度。tolerance 超過は ``"error"``。
        message: 人間向けメッセージ（日本語）。
    '''
    role_uri: str
    parent_concept: str
    expected: Decimal
    actual: Decimal
    difference: Decimal
    tolerance: Decimal
    severity: Literal['error', 'warning']
    message: str

@dataclass(frozen=True, slots=True)
class CalcValidationResult:
    """計算リンクベース検証の結果。

    Attributes:
        issues: 不一致の詳細タプル。
        checked_count: 検証した親科目の数（passed + error）。
        passed_count: 一致した（tolerance 内の）親科目の数。
        skipped_count: Fact 不足でスキップした親科目の数。
    """
    issues: tuple[ValidationIssue, ...]
    checked_count: int
    passed_count: int
    skipped_count: int
    @property
    def is_valid(self) -> bool:
        """error が 1 つもなければ True。"""
    @property
    def error_count(self) -> int:
        """error の件数。"""
    @property
    def warning_count(self) -> int:
        """warning の件数。"""

def validate_calculations(statement: FinancialStatement, calc_linkbase: CalculationLinkbase, *, role_uri: str | None = None) -> CalcValidationResult:
    """計算リンクベースに基づき財務諸表の合計値を検証する。

    XBRL 2.1 §5.2.5.2 に準拠し、計算リンクベース内の **全ての**
    summation-item 親子関係を検証対象とする（roots だけでなく
    中間ノードも含む）。各親科目について子科目の加重和と比較し、
    decimals ベースの丸め許容差を超える不一致を検出する。

    Args:
        statement: 検証対象の FinancialStatement。
        calc_linkbase: ``parse_calculation_linkbase()`` で取得した
            CalculationLinkbase。
        role_uri: 検証対象のロール URI。``None`` の場合は全ロールを検証する。

    Returns:
        CalcValidationResult。
    """

"""DEI ベースの期間分類モジュール。

DEI の日付情報から「当期」「前期」を分類し、
``Statements.income_statement(period="current")`` /
``period="prior"`` を可能にする。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from edinet.xbrl.contexts import DurationPeriod, InstantPeriod

if TYPE_CHECKING:
    from edinet.xbrl.dei import DEI

__all__ = ["PeriodClassification", "classify_periods"]


@dataclass(frozen=True, slots=True)
class PeriodClassification:
    """DEI ベースの期間分類結果。

    Attributes:
        current_duration: 当期の duration 期間。
        prior_duration: 前期の duration 期間。
        current_instant: 当期末の instant 時点。
        prior_instant: 前期末の instant 時点。
    """

    current_duration: DurationPeriod | None
    prior_duration: DurationPeriod | None
    current_instant: InstantPeriod | None
    prior_instant: InstantPeriod | None


def classify_periods(dei: DEI) -> PeriodClassification:
    """DEI の日付情報から当期/前期を分類する。

    Args:
        dei: ``extract_dei()`` で取得した DEI。

    Returns:
        PeriodClassification。日付情報が不足している場合は
        該当フィールドが None になる。
    """
    # 当期 duration: start=current_fiscal_year_start_date, end=current_period_end_date
    current_duration = None
    if dei.current_fiscal_year_start_date and dei.current_period_end_date:
        current_duration = DurationPeriod(
            start_date=dei.current_fiscal_year_start_date,
            end_date=dei.current_period_end_date,
        )

    # 当期末 instant: instant=current_period_end_date
    current_instant = None
    if dei.current_period_end_date:
        current_instant = InstantPeriod(instant=dei.current_period_end_date)

    # 前期の終了日: comparative_period_end_date を優先、なければ previous_fiscal_year_end_date
    prior_end = dei.comparative_period_end_date or dei.previous_fiscal_year_end_date

    # 前期 duration: start=previous_fiscal_year_start_date, end=prior_end
    prior_duration = None
    if dei.previous_fiscal_year_start_date and prior_end:
        prior_duration = DurationPeriod(
            start_date=dei.previous_fiscal_year_start_date,
            end_date=prior_end,
        )

    # 前期末 instant: instant=prior_end
    prior_instant = None
    if prior_end:
        prior_instant = InstantPeriod(instant=prior_end)

    return PeriodClassification(
        current_duration=current_duration,
        prior_duration=prior_duration,
        current_instant=current_instant,
        prior_instant=prior_instant,
    )

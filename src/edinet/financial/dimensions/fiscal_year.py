"""決算期メタデータの抽出モジュール。

DEI の日付情報から決算月・期間月数・変則決算の有無を判定し、
``FiscalYearInfo`` として返す。

``classify_periods()`` がコンテキスト選択（BS/PL 構築時の当期/前期判別）
を担うのに対し、``detect_fiscal_year()`` は企業の決算期特性を表す
メタデータの抽出を担う。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from edinet.xbrl.dei import PeriodType

if TYPE_CHECKING:
    from edinet.xbrl.dei import DEI

__all__ = ["FiscalYearInfo", "detect_fiscal_year"]

# 平均月日数（365.25 / 12）。閏年を考慮した概算値。
_DAYS_PER_MONTH = 30.44


@dataclass(frozen=True, slots=True)
class FiscalYearInfo:
    """DEI から抽出した決算期メタデータ。

    DEI の日付情報を構造化し、決算期の特性（通期/半期、
    変則決算の有無、決算月等）を提供する。

    Attributes:
        start_date: 当事業年度開始日。DEI に未設定の場合は None。
        end_date: 当会計期間終了日。DEI に未設定の場合は None。
        fiscal_year_end_date: 決算期末日（当事業年度終了日）。
            DEI に未設定の場合は None。
        period_months: 期間月数（概算、四捨五入）。
            開始日または終了日が None の場合は None。
        period_type: 期間種類。DEI の type_of_current_period の値。
            PeriodType.FY（通期）、PeriodType.HY（半期）、
            未知の文字列、または None。
        is_full_year: 12ヶ月通期かどうか。
            PeriodType.FY かつ period_months が 12 の場合のみ True。
            日付情報が不足している場合は False。
        is_irregular: 変則決算かどうか。
            PeriodType.FY なのに period_months が 12 でない場合に True。
            日付情報が不足している場合は False。
        fiscal_year_end_month: 決算月（1〜12）。
            fiscal_year_end_date の月。未設定の場合は None。
    """

    start_date: date | None
    end_date: date | None
    fiscal_year_end_date: date | None
    period_months: int | None
    period_type: PeriodType | str | None
    is_full_year: bool
    is_irregular: bool
    fiscal_year_end_month: int | None


def _calc_months(start: date, end: date) -> int:
    """期間の月数を概算する。

    開始日・終了日の両端を含む日数を平均月日数（30.44）で
    割り、四捨五入して整数月数を返す。

    Args:
        start: 期間開始日。
        end: 期間終了日。

    Returns:
        概算月数（整数）。
    """
    delta_days = (end - start).days + 1  # 両端含む（会計期間の慣行）
    return round(delta_days / _DAYS_PER_MONTH)


def detect_fiscal_year(dei_or_stmts: DEI | Any) -> FiscalYearInfo:
    """DEI の日付情報から決算期メタデータを抽出する。

    ``Statements`` を渡すと内部の DEI を自動取得する。

    DEI の各日付フィールド（current_fiscal_year_start_date,
    current_period_end_date, current_fiscal_year_end_date,
    type_of_current_period）を構造化し、決算期の特性を判定する。

    日付フィールドが未設定（None）の場合は、該当する判定結果も
    None または False となる（graceful degradation）。

    Args:
        dei_or_stmts: ``extract_dei()`` で取得した DEI、
            または ``Statements`` オブジェクト。

    Returns:
        FiscalYearInfo。
    """
    # Statements を受け付ける
    from edinet.financial.statements import Statements as _Statements

    if isinstance(dei_or_stmts, _Statements):
        dei = dei_or_stmts._dei  # noqa: SLF001
        if dei is None:
            # DEI なしの Statements → 全フィールド None の FiscalYearInfo を返す
            return FiscalYearInfo(
                start_date=None, end_date=None,
                fiscal_year_end_date=None, period_months=None,
                period_type=None, is_full_year=False, is_irregular=False,
                fiscal_year_end_month=None,
            )
    else:
        dei = dei_or_stmts
    start = dei.current_fiscal_year_start_date
    end = dei.current_period_end_date
    fy_end = dei.current_fiscal_year_end_date
    period_type = dei.type_of_current_period

    # 期間月数の計算（両方の日付が必要）
    period_months: int | None = None
    if start is not None and end is not None:
        period_months = _calc_months(start, end)

    # 通期（FY）かどうかの判定
    is_fy = isinstance(period_type, PeriodType) and period_type == PeriodType.FY

    # 12ヶ月通期の判定
    is_full_year = is_fy and period_months == 12

    # 変則決算の判定（FY なのに 12ヶ月でない）
    is_irregular = is_fy and period_months is not None and period_months != 12

    # 決算月の抽出
    fiscal_year_end_month: int | None = None
    if fy_end is not None:
        fiscal_year_end_month = fy_end.month

    return FiscalYearInfo(
        start_date=start,
        end_date=end,
        fiscal_year_end_date=fy_end,
        period_months=period_months,
        period_type=period_type,
        is_full_year=is_full_year,
        is_irregular=is_irregular,
        fiscal_year_end_month=fiscal_year_end_month,
    )

from dataclasses import dataclass
from datetime import date
from edinet.xbrl.dei import DEI, PeriodType

__all__ = ['FiscalYearInfo', 'detect_fiscal_year']

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

def detect_fiscal_year(dei: DEI) -> FiscalYearInfo:
    """DEI の日付情報から決算期メタデータを抽出する。

    DEI の各日付フィールド（current_fiscal_year_start_date,
    current_period_end_date, current_fiscal_year_end_date,
    type_of_current_period）を構造化し、決算期の特性を判定する。

    日付フィールドが未設定（None）の場合は、該当する判定結果も
    None または False となる（graceful degradation）。

    Args:
        dei: ``extract_dei()`` で取得した DEI。

    Returns:
        FiscalYearInfo。
    """

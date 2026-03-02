"""test_fiscal_year.py — 決算期判定のテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from edinet.xbrl.dei import DEI, PeriodType
from edinet.financial.dimensions.fiscal_year import detect_fiscal_year


def _make_dei(
    *,
    start: date | None = date(2024, 4, 1),
    end: date | None = date(2025, 3, 31),
    fy_end: date | None = date(2025, 3, 31),
    period_type: PeriodType | str | None = PeriodType.FY,
) -> DEI:
    """テスト用の最小限 DEI を生成する。

    指定した 4 フィールド以外は DEI のデフォルト値（None）が使われる。
    """
    return DEI(
        current_fiscal_year_start_date=start,
        current_period_end_date=end,
        current_fiscal_year_end_date=fy_end,
        type_of_current_period=period_type,
    )


@pytest.mark.small
@pytest.mark.unit
class TestDetectFiscalYear:
    """detect_fiscal_year() の単体テスト群。"""

    # --- 典型的な決算パターン ---

    def test_march_fiscal_year(self) -> None:
        """3月決算、FY、12ヶ月。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.start_date == date(2024, 4, 1)
        assert info.end_date == date(2025, 3, 31)
        assert info.fiscal_year_end_date == date(2025, 3, 31)
        assert info.period_months == 12
        assert info.period_type == PeriodType.FY
        assert info.is_full_year is True
        assert info.is_irregular is False
        assert info.fiscal_year_end_month == 3

    def test_december_fiscal_year(self) -> None:
        """12月決算。fiscal_year_end_month=12。"""
        dei = _make_dei(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            fy_end=date(2024, 12, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 12
        assert info.is_full_year is True
        assert info.is_irregular is False
        assert info.fiscal_year_end_month == 12

    def test_half_year(self) -> None:
        """半期報告（HY）、6ヶ月。is_full_year=False, is_irregular=False。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2024, 9, 30),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.HY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 6
        assert info.period_type == PeriodType.HY
        assert info.is_full_year is False
        assert info.is_irregular is False
        assert info.fiscal_year_end_month == 3

    # --- 変則決算 ---

    def test_irregular_fiscal_year_9months(self) -> None:
        """変則決算（FY だが 9ヶ月）。決算期変更による移行期間。"""
        dei = _make_dei(
            start=date(2024, 7, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 9
        assert info.is_full_year is False
        assert info.is_irregular is True

    def test_irregular_fiscal_year_short(self) -> None:
        """変則決算（FY だが 6ヶ月）。設立初年度など。"""
        dei = _make_dei(
            start=date(2024, 10, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 6
        assert info.is_full_year is False
        assert info.is_irregular is True

    def test_irregular_fiscal_year_15months(self) -> None:
        """変則決算（FY だが 15ヶ月）。3月→6月への決算期変更。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2025, 6, 30),
            fy_end=date(2025, 6, 30),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 15
        assert info.is_full_year is False
        assert info.is_irregular is True

    def test_irregular_fiscal_year_1month(self) -> None:
        """極端な変則決算（FY だが 1ヶ月）。設立直後の決算期変更。"""
        dei = _make_dei(
            start=date(2025, 3, 1),
            end=date(2025, 3, 31),
            fy_end=date(2025, 3, 31),
            period_type=PeriodType.FY,
        )
        info = detect_fiscal_year(dei)
        assert info.period_months == 1
        assert info.is_full_year is False
        assert info.is_irregular is True

    # --- フィールド単体の検証 ---

    def test_fiscal_year_end_month_various(self) -> None:
        """fiscal_year_end_month が各月で正しく抽出されること。"""
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            dei = _make_dei(fy_end=date(2025, month, day))
            info = detect_fiscal_year(dei)
            assert info.fiscal_year_end_month == month

    def test_period_months_calculation(self) -> None:
        """期間月数の概算が代表的なケースで正しいこと。"""
        # 12ヶ月
        dei = _make_dei(start=date(2024, 4, 1), end=date(2025, 3, 31))
        assert detect_fiscal_year(dei).period_months == 12

        # 6ヶ月
        dei = _make_dei(start=date(2024, 4, 1), end=date(2024, 9, 30))
        assert detect_fiscal_year(dei).period_months == 6

        # 3ヶ月
        dei = _make_dei(start=date(2024, 1, 1), end=date(2024, 3, 31))
        assert detect_fiscal_year(dei).period_months == 3

    def test_period_type_fy(self) -> None:
        """period_type が PeriodType.FY であること。"""
        dei = _make_dei(period_type=PeriodType.FY)
        assert detect_fiscal_year(dei).period_type == PeriodType.FY

    def test_period_type_hy(self) -> None:
        """period_type が PeriodType.HY であること。"""
        dei = _make_dei(period_type=PeriodType.HY)
        assert detect_fiscal_year(dei).period_type == PeriodType.HY

    # --- 欠損データのハンドリング ---

    def test_dei_missing_all_dates(self) -> None:
        """全日付フィールドが None の場合。graceful degradation。"""
        dei = _make_dei(start=None, end=None, fy_end=None, period_type=None)
        info = detect_fiscal_year(dei)
        assert info.start_date is None
        assert info.end_date is None
        assert info.fiscal_year_end_date is None
        assert info.period_months is None
        assert info.period_type is None
        assert info.is_full_year is False
        assert info.is_irregular is False
        assert info.fiscal_year_end_month is None

    def test_dei_partial_dates_start_only(self) -> None:
        """開始日のみ設定されている場合。period_months は計算不可。"""
        dei = _make_dei(start=date(2024, 4, 1), end=None, fy_end=None)
        info = detect_fiscal_year(dei)
        assert info.start_date == date(2024, 4, 1)
        assert info.end_date is None
        assert info.period_months is None
        assert info.is_full_year is False
        assert info.is_irregular is False

    def test_is_full_year_false_for_hy_even_12months(self) -> None:
        """HY の場合、たとえ 12ヶ月であっても is_full_year=False。"""
        dei = _make_dei(
            start=date(2024, 4, 1),
            end=date(2025, 3, 31),
            period_type=PeriodType.HY,
        )
        info = detect_fiscal_year(dei)
        assert info.is_full_year is False

    # --- 未知の period_type ---

    def test_unknown_period_type_string(self) -> None:
        """未知の period_type 文字列の場合。is_full_year/is_irregular は False。"""
        dei = _make_dei(period_type="Q1")
        info = detect_fiscal_year(dei)
        assert info.period_type == "Q1"
        assert info.is_full_year is False
        assert info.is_irregular is False


@pytest.mark.small
@pytest.mark.unit
class TestFiscalYearInfoFrozen:
    """FiscalYearInfo の frozen 特性のテスト。"""

    def test_immutable(self) -> None:
        """FiscalYearInfo は frozen であり、フィールド変更で例外が発生すること。"""
        info = detect_fiscal_year(_make_dei())
        with pytest.raises(AttributeError):
            info.start_date = date(2000, 1, 1)  # type: ignore[misc]

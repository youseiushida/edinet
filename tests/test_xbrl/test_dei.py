"""test_dei.py — DEI 抽出モジュールのテスト。"""

from __future__ import annotations

import dataclasses
import datetime

import pytest

from edinet.exceptions import EdinetWarning
from edinet.xbrl.dei import (
    DEI,
    AccountingStandard,
    PeriodType,
    _VOCAB_TO_INDUSTRY,
    extract_dei,
    resolve_industry_code,
)
from edinet.xbrl.parser import RawFact

# テスト用デフォルト名前空間
_NS_JPDEI = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor"
_NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"


def _make_dei_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    is_nil: bool = False,
    namespace_uri: str = _NS_JPDEI,
    order: int = 0,
) -> RawFact:
    """テスト用 DEI RawFact を構築するヘルパー。

    DEI 要素はテキストノードのみで子要素を持たないため、
    value_inner_xml はデフォルト値 None のまま省略する。
    """
    return RawFact(
        concept_qname=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref="FilingDateInstant",
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=order,
    )


def _make_full_dei_facts() -> tuple[RawFact, ...]:
    """全 27 DEI 要素を含む RawFact タプルを構築するヘルパー。"""
    return (
        _make_dei_fact("EDINETCodeDEI", "E00001", order=0),
        _make_dei_fact("FundCodeDEI", "FUND001", order=1),
        _make_dei_fact("SecurityCodeDEI", "11110", order=2),
        _make_dei_fact("FilerNameInJapaneseDEI", "テスト株式会社", order=3),
        _make_dei_fact("FilerNameInEnglishDEI", "Test Corp.", order=4),
        _make_dei_fact("FundNameInJapaneseDEI", "テストファンド", order=5),
        _make_dei_fact("FundNameInEnglishDEI", "Test Fund", order=6),
        _make_dei_fact("CabinetOfficeOrdinanceDEI", "企業内容等の開示に関する内閣府令", order=7),
        _make_dei_fact("DocumentTypeDEI", "第三号様式", order=8),
        _make_dei_fact("AccountingStandardsDEI", "Japan GAAP", order=9),
        _make_dei_fact(
            "WhetherConsolidatedFinancialStatementsArePreparedDEI",
            "true",
            order=10,
        ),
        _make_dei_fact(
            "IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI",
            "CNA",
            order=11,
        ),
        _make_dei_fact(
            "IndustryCodeWhenFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI",
            "CNB",
            order=12,
        ),
        _make_dei_fact("CurrentFiscalYearStartDateDEI", "2025-04-01", order=13),
        _make_dei_fact("CurrentPeriodEndDateDEI", "2026-03-31", order=14),
        _make_dei_fact("TypeOfCurrentPeriodDEI", "FY", order=15),
        _make_dei_fact("CurrentFiscalYearEndDateDEI", "2026-03-31", order=16),
        _make_dei_fact("PreviousFiscalYearStartDateDEI", "2024-04-01", order=17),
        _make_dei_fact("ComparativePeriodEndDateDEI", "2025-03-31", order=18),
        _make_dei_fact("PreviousFiscalYearEndDateDEI", "2025-03-31", order=19),
        _make_dei_fact("NextFiscalYearStartDateDEI", "2026-04-01", order=20),
        _make_dei_fact(
            "EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI",
            "2026-09-30",
            order=21,
        ),
        _make_dei_fact("NumberOfSubmissionDEI", "1", order=22),
        _make_dei_fact("AmendmentFlagDEI", "false", order=23),
        _make_dei_fact(
            "IdentificationOfDocumentSubjectToAmendmentDEI",
            "",
            order=24,
        ),
        _make_dei_fact("ReportAmendmentFlagDEI", "false", order=25),
        _make_dei_fact("XBRLAmendmentFlagDEI", "false", order=26),
    )


# ---------------------------------------------------------------------------
# P0 テスト（T1〜T11・必須）
# ---------------------------------------------------------------------------


class TestP0:
    """P0: 必須テストケース。"""

    def test_extract_dei_full(self) -> None:
        """T1: 全 27 フィールドが正しく抽出・型変換されること。"""
        facts = _make_full_dei_facts()
        dei = extract_dei(facts)

        # (A) 提出者情報
        assert dei.edinet_code == "E00001"
        assert dei.fund_code == "FUND001"
        assert dei.security_code == "11110"
        assert dei.filer_name_ja == "テスト株式会社"
        assert dei.filer_name_en == "Test Corp."
        assert dei.fund_name_ja == "テストファンド"
        assert dei.fund_name_en == "Test Fund"

        # (B) 提出書類情報
        assert dei.cabinet_office_ordinance == "企業内容等の開示に関する内閣府令"
        assert dei.document_type == "第三号様式"
        assert dei.accounting_standards == AccountingStandard.JAPAN_GAAP
        assert dei.has_consolidated is True
        assert dei.industry_code_consolidated == "CNA"
        assert dei.industry_code_non_consolidated == "CNB"

        # (C) 当会計期間
        assert dei.current_fiscal_year_start_date == datetime.date(2025, 4, 1)
        assert dei.current_period_end_date == datetime.date(2026, 3, 31)
        assert dei.type_of_current_period == PeriodType.FY
        assert dei.current_fiscal_year_end_date == datetime.date(2026, 3, 31)

        # (D) 比較対象会計期間
        assert dei.previous_fiscal_year_start_date == datetime.date(2024, 4, 1)
        assert dei.comparative_period_end_date == datetime.date(2025, 3, 31)
        assert dei.previous_fiscal_year_end_date == datetime.date(2025, 3, 31)

        # (E) 次の中間期
        assert dei.next_fiscal_year_start_date == datetime.date(2026, 4, 1)
        assert dei.end_date_of_next_semi_annual_period == datetime.date(2026, 9, 30)

        # (F) 訂正関連
        assert dei.number_of_submission == 1
        assert dei.amendment_flag is False
        assert dei.identification_of_document_subject_to_amendment == ""
        assert dei.report_amendment_flag is False
        assert dei.xbrl_amendment_flag is False

    def test_extract_dei_empty_facts(self) -> None:
        """T2: Fact が空の場合、全フィールド None の DEI が返ること。"""
        dei = extract_dei(())

        for f in dataclasses.fields(dei):
            assert getattr(dei, f.name) is None, f"{f.name} should be None"

    def test_extract_dei_no_dei_facts(self) -> None:
        """T3: jpdei_cor 以外の Fact のみの場合、全フィールド None の DEI が返ること。"""
        facts = (
            _make_dei_fact(
                "NetSales",
                "1000000",
                namespace_uri=_NS_JPPFS,
            ),
        )
        dei = extract_dei(facts)

        for f in dataclasses.fields(dei):
            assert getattr(dei, f.name) is None, f"{f.name} should be None"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Japan GAAP", AccountingStandard.JAPAN_GAAP),
            ("IFRS", AccountingStandard.IFRS),
            ("US GAAP", AccountingStandard.US_GAAP),
            ("JMIS", AccountingStandard.JMIS),
        ],
        ids=["japan_gaap", "ifrs", "us_gaap", "jmis"],
    )
    def test_accounting_standards_enum(
        self, value: str, expected: AccountingStandard
    ) -> None:
        """T4: 4 つの会計基準値が正しく Enum に変換されること。"""
        facts = (_make_dei_fact("AccountingStandardsDEI", value),)
        dei = extract_dei(facts)
        assert dei.accounting_standards == expected
        assert isinstance(dei.accounting_standards, AccountingStandard)

    def test_accounting_standards_nil(self) -> None:
        """T5: xsi:nil=true の場合に None が返ること。"""
        facts = (_make_dei_fact("AccountingStandardsDEI", is_nil=True),)
        dei = extract_dei(facts)
        assert dei.accounting_standards is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("FY", PeriodType.FY),
            ("HY", PeriodType.HY),
        ],
        ids=["fy", "hy"],
    )
    def test_period_type_enum(self, value: str, expected: PeriodType) -> None:
        """T6: FY/HY が正しく PeriodType に変換されること。"""
        facts = (_make_dei_fact("TypeOfCurrentPeriodDEI", value),)
        dei = extract_dei(facts)
        assert dei.type_of_current_period == expected
        assert isinstance(dei.type_of_current_period, PeriodType)

    def test_date_conversion(self) -> None:
        """T7: 日付フィールドが datetime.date に変換されること。"""
        facts = (
            _make_dei_fact("CurrentFiscalYearEndDateDEI", "2026-03-31"),
            _make_dei_fact("PreviousFiscalYearEndDateDEI", "2025-03-31"),
        )
        dei = extract_dei(facts)
        assert dei.current_fiscal_year_end_date == datetime.date(2026, 3, 31)
        assert dei.previous_fiscal_year_end_date == datetime.date(2025, 3, 31)
        assert isinstance(dei.current_fiscal_year_end_date, datetime.date)

    def test_bool_conversion(self) -> None:
        """T8: boolean フィールドが bool に変換されること。"""
        facts = (
            _make_dei_fact(
                "WhetherConsolidatedFinancialStatementsArePreparedDEI",
                "true",
            ),
            _make_dei_fact("AmendmentFlagDEI", "false"),
        )
        dei = extract_dei(facts)
        assert dei.has_consolidated is True
        assert dei.amendment_flag is False

    def test_int_conversion(self) -> None:
        """T9: number_of_submission が int に変換されること。"""
        facts = (_make_dei_fact("NumberOfSubmissionDEI", "3"),)
        dei = extract_dei(facts)
        assert dei.number_of_submission == 3
        assert isinstance(dei.number_of_submission, int)

    def test_nil_handling(self) -> None:
        """T10: is_nil=True の Fact が None として処理されること。"""
        facts = (
            _make_dei_fact("EDINETCodeDEI", is_nil=True),
            _make_dei_fact("SecurityCodeDEI", is_nil=True),
            _make_dei_fact("CurrentFiscalYearEndDateDEI", is_nil=True),
            _make_dei_fact(
                "WhetherConsolidatedFinancialStatementsArePreparedDEI",
                is_nil=True,
            ),
            _make_dei_fact("NumberOfSubmissionDEI", is_nil=True),
        )
        dei = extract_dei(facts)
        assert dei.edinet_code is None
        assert dei.security_code is None
        assert dei.current_fiscal_year_end_date is None
        assert dei.has_consolidated is None
        assert dei.number_of_submission is None

    def test_duplicate_concept_first_wins(self) -> None:
        """T11: 同名 concept が複数ある場合、最初の出現が使われること。"""
        facts = (
            _make_dei_fact("EDINETCodeDEI", "E00001", order=0),
            _make_dei_fact("EDINETCodeDEI", "E99999", order=1),
        )
        dei = extract_dei(facts)
        assert dei.edinet_code == "E00001"

    def test_value_raw_none_without_nil(self) -> None:
        """T11b: value_raw=None (is_nil=False) の場合も None として処理されること。"""
        facts = (_make_dei_fact("EDINETCodeDEI", value_raw=None, is_nil=False),)
        dei = extract_dei(facts)
        assert dei.edinet_code is None


# ---------------------------------------------------------------------------
# P1 テスト（T12〜T21・推奨）
# ---------------------------------------------------------------------------

class TestP1:
    """P1: 推奨テストケース。"""

    def test_unknown_accounting_standard_warns(self) -> None:
        """T12: 未知の会計基準値で EdinetWarning が出ること。"""
        facts = (_make_dei_fact("AccountingStandardsDEI", "Unknown Standard"),)
        with pytest.warns(EdinetWarning, match="未知の会計基準"):
            dei = extract_dei(facts)
        assert dei.accounting_standards == "Unknown Standard"
        assert isinstance(dei.accounting_standards, str)

    def test_unknown_period_type_warns(self) -> None:
        """T13: 未知の報告期間種別で EdinetWarning が出ること。"""
        facts = (_make_dei_fact("TypeOfCurrentPeriodDEI", "QY"),)
        with pytest.warns(EdinetWarning, match="未知の報告期間種別"):
            dei = extract_dei(facts)
        assert dei.type_of_current_period == "QY"
        assert isinstance(dei.type_of_current_period, str)

    def test_invalid_date_fallback(self) -> None:
        """T14: 不正な日付文字列で警告が出て None になること。"""
        facts = (_make_dei_fact("CurrentFiscalYearEndDateDEI", "not-a-date"),)
        with pytest.warns(EdinetWarning, match="値変換に失敗"):
            dei = extract_dei(facts)
        assert dei.current_fiscal_year_end_date is None

    def test_different_jpdei_versions(self) -> None:
        """T15: 異なるタクソノミバージョンの名前空間 URI でも正しく抽出されること。"""
        ns_2025 = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2025-11-01/jpdei_cor"
        facts = (
            _make_dei_fact("EDINETCodeDEI", "E12345", namespace_uri=ns_2025),
        )
        dei = extract_dei(facts)
        assert dei.edinet_code == "E12345"

    def test_non_dei_namespace_ignored(self) -> None:
        """T16: jppfs_cor 等の非 DEI 名前空間の Fact が無視されること。"""
        facts = (
            _make_dei_fact(
                "EDINETCodeDEI",
                "E00001",
                namespace_uri=_NS_JPPFS,
            ),
        )
        dei = extract_dei(facts)
        assert dei.edinet_code is None

    def test_accounting_standard_str_comparison(self) -> None:
        """T17: dei.accounting_standards == "Japan GAAP" が True になること。"""
        facts = (_make_dei_fact("AccountingStandardsDEI", "Japan GAAP"),)
        dei = extract_dei(facts)
        assert dei.accounting_standards == "Japan GAAP"
        assert dei.accounting_standards == AccountingStandard.JAPAN_GAAP

    def test_dei_frozen(self) -> None:
        """T18: DEI dataclass が frozen であり、変更が例外を raise すること。"""
        dei = DEI(edinet_code="E00001")
        with pytest.raises(dataclasses.FrozenInstanceError):
            dei.edinet_code = "E99999"  # type: ignore[misc]

    def test_invalid_bool_warns(self) -> None:
        """T19: 不正な boolean 値で EdinetWarning が出て False にフォールバックされること。"""
        facts = (_make_dei_fact("AmendmentFlagDEI", "yes"),)
        with pytest.warns(EdinetWarning, match="不正な boolean 値"):
            dei = extract_dei(facts)
        assert dei.amendment_flag is False

    def test_dei_repr_omits_none(self) -> None:
        """T20: DEI.__repr__ が None フィールドを省略した簡潔な表示を返すこと。"""
        dei = DEI(edinet_code="E00001", filer_name_ja="テスト株式会社")
        r = repr(dei)
        assert "edinet_code='E00001'" in r
        assert "filer_name_ja='テスト株式会社'" in r
        assert "fund_code" not in r
        assert "None" not in r
        assert r.startswith("DEI(")
        assert r.endswith(")")

    def test_early_termination(self) -> None:
        """T21: 全 27 DEI 要素が先頭にある場合、後続の重複が無視されること。

        全 27 要素が揃った後に配置された重複 concept の値が
        使われないことで、早期終了を間接的に確認する。
        """
        full_facts = list(_make_full_dei_facts())
        # 末尾に重複を追加（もし走査が続いていたら上書きされるはずだが、
        # first-wins ルールにより無視される）
        full_facts.append(
            _make_dei_fact("EDINETCodeDEI", "OVERWRITTEN", order=99)
        )
        dei = extract_dei(tuple(full_facts))
        assert dei.edinet_code == "E00001"


# ---------------------------------------------------------------------------
# resolve_industry_code テスト
# ---------------------------------------------------------------------------


class TestResolveIndustryCode:
    """resolve_industry_code() のテスト。"""

    def test_bnk_to_bk1(self) -> None:
        """銀行の語彙層コード BNK が関係層 bk1 に変換されること。"""
        dei = DEI(industry_code_consolidated="BNK", has_consolidated=True)
        assert resolve_industry_code(dei) == "bk1"

    def test_ins_to_in1(self) -> None:
        """保険の語彙層コード INS が関係層 in1 に変換されること。"""
        dei = DEI(industry_code_consolidated="INS", has_consolidated=True)
        assert resolve_industry_code(dei) == "in1"

    def test_cns_to_cns(self) -> None:
        """建設業の語彙層コード CNS が関係層 cns に変換されること。"""
        dei = DEI(industry_code_consolidated="CNS", has_consolidated=True)
        assert resolve_industry_code(dei) == "cns"

    def test_cte_returns_none(self) -> None:
        """一般事業会社 CTE は None を返すこと。"""
        dei = DEI(industry_code_consolidated="CTE", has_consolidated=True)
        assert resolve_industry_code(dei) is None

    def test_none_returns_none(self) -> None:
        """業種コードが未設定（None）の場合は None を返すこと。"""
        dei = DEI()
        assert resolve_industry_code(dei) is None

    def test_prefer_consolidated_true(self) -> None:
        """prefer_consolidated=True で連結の業種コードが使用されること。"""
        dei = DEI(
            industry_code_consolidated="BNK",
            industry_code_non_consolidated="SEC",
        )
        assert resolve_industry_code(dei, prefer_consolidated=True) == "bk1"

    def test_prefer_consolidated_false(self) -> None:
        """prefer_consolidated=False で個別の業種コードが使用されること。"""
        dei = DEI(
            industry_code_consolidated="BNK",
            industry_code_non_consolidated="SEC",
        )
        assert resolve_industry_code(dei, prefer_consolidated=False) == "sec"

    def test_consolidated_fallback_to_non_consolidated(self) -> None:
        """連結が None の場合、個別にフォールバックすること。"""
        dei = DEI(industry_code_non_consolidated="RWY")
        assert resolve_industry_code(dei) == "rwy"

    def test_non_consolidated_fallback_to_consolidated(self) -> None:
        """個別が None の場合、連結にフォールバックすること。"""
        dei = DEI(industry_code_consolidated="GAS")
        assert resolve_industry_code(dei, prefer_consolidated=False) == "gas"

    def test_all_vocab_codes_covered(self) -> None:
        """_VOCAB_TO_INDUSTRY の全 20 コードが正しく変換されること。"""
        for vocab, expected in _VOCAB_TO_INDUSTRY.items():
            dei = DEI(industry_code_consolidated=vocab)
            result = resolve_industry_code(dei)
            assert result == expected, f"{vocab} → {result}（期待: {expected}）"

    def test_unknown_code_returns_none(self) -> None:
        """辞書にない未知のコードは None を返すこと。"""
        dei = DEI(industry_code_consolidated="UNKNOWN")
        assert resolve_industry_code(dei) is None

"""Company 検索 API のテスト（Wave 6 Lane 1）。"""
from __future__ import annotations

from edinet.models.company import Company


# ============================================================
# Company.search() テスト
# ============================================================


class TestCompanySearch:
    """Company.search() のテスト。"""

    def test_search_by_japanese_name(self) -> None:
        """日本語名「トヨタ」で検索して結果が返る。"""
        results = Company.search("トヨタ")
        assert len(results) >= 1
        assert any(c.name_ja and "トヨタ" in c.name_ja for c in results)

    def test_search_by_english_name(self) -> None:
        """英語名「TOYOTA」で検索して結果が返る。"""
        results = Company.search("TOYOTA")
        assert len(results) >= 1

    def test_search_case_insensitive(self) -> None:
        """小文字「toyota」でも検索できる（case-insensitive）。"""
        results = Company.search("toyota")
        assert len(results) >= 1
        results_upper = Company.search("TOYOTA")
        assert {c.edinet_code for c in results} == {
            c.edinet_code for c in results_upper
        }

    def test_search_by_yomi(self) -> None:
        """読み仮名「トヨタジドウシャ」で検索して結果が返る。"""
        results = Company.search("トヨタジドウシャ")
        assert len(results) >= 1

    def test_search_prefix_match_first(self) -> None:
        """名前がqueryで始まるエントリが、含むだけのエントリより先に返る。"""
        results = Company.search("トヨタ")
        assert len(results) >= 2
        assert results[0].name_ja is not None
        assert results[0].name_ja.startswith("トヨタ")

    def test_search_limit(self) -> None:
        """limitを指定すると件数が制限される。"""
        results = Company.search("株式会社", limit=5)
        assert len(results) <= 5

    def test_search_limit_zero_unlimited(self) -> None:
        """limit=0で制限なし。"""
        results_limited = Company.search("株式会社", limit=5)
        results_unlimited = Company.search("株式会社", limit=0)
        assert len(results_unlimited) >= len(results_limited)

    def test_search_empty_query(self) -> None:
        """空文字列で検索すると空リストが返る。"""
        results = Company.search("")
        assert results == []

    def test_search_no_results(self) -> None:
        """マッチしない検索語では空リストが返る。"""
        results = Company.search("zzz_存在しない企業名_zzz")
        assert results == []


# ============================================================
# Company.from_edinet_code() テスト
# ============================================================


class TestCompanyFromEdinetCode:
    """Company.from_edinet_code() のテスト。"""

    def test_from_edinet_code_found(self) -> None:
        """存在するEDINETコードからCompanyが構築される。"""
        company = Company.from_edinet_code("E02144")
        assert company is not None
        assert company.edinet_code == "E02144"
        assert company.name_ja == "トヨタ自動車株式会社"

    def test_from_edinet_code_sec_code(self) -> None:
        """from_edinet_codeで構築したCompanyのsec_codeが正しい。"""
        company = Company.from_edinet_code("E02144")
        assert company is not None
        assert company.sec_code == "72030"
        assert company.ticker == "7203"

    def test_from_edinet_code_non_listed(self) -> None:
        """非上場企業のCompanyではsec_codeがNoneになりうる。"""
        from edinet.models.edinet_code import all_edinet_codes

        non_listed = next(
            (e for e in all_edinet_codes() if e.sec_code is None),
            None,
        )
        if non_listed is not None:
            company = Company.from_edinet_code(non_listed.edinet_code)
            assert company is not None
            assert company.sec_code is None
            assert company.ticker is None

    def test_from_edinet_code_not_found(self) -> None:
        """存在しないEDINETコードではNoneが返る。"""
        company = Company.from_edinet_code("E99999")
        assert company is None


# ============================================================
# Company.from_sec_code() テスト
# ============================================================


class TestCompanyFromSecCode:
    """Company.from_sec_code() のテスト。"""

    def test_from_sec_code_4digit(self) -> None:
        """4桁の証券コードからCompanyが構築される。"""
        company = Company.from_sec_code("7203")
        assert company is not None
        assert company.edinet_code is not None

    def test_from_sec_code_5digit(self) -> None:
        """5桁の証券コードからCompanyが構築される。"""
        company = Company.from_sec_code("72030")
        assert company is not None

    def test_from_sec_code_4digit_5digit_same_result(self) -> None:
        """4桁と5桁で同じCompanyが返る。"""
        c4 = Company.from_sec_code("7203")
        c5 = Company.from_sec_code("72030")
        assert c4 is not None
        assert c5 is not None
        assert c4.edinet_code == c5.edinet_code

    def test_from_sec_code_whitespace(self) -> None:
        """前後の空白が除去されて正しく検索できる。"""
        company = Company.from_sec_code(" 7203 ")
        assert company is not None
        assert company.edinet_code is not None

    def test_from_sec_code_not_found(self) -> None:
        """存在しない証券コードではNoneが返る。"""
        company = Company.from_sec_code("0000")
        assert company is None


# ============================================================
# Company.by_industry() テスト
# ============================================================


class TestCompanyByIndustry:
    """Company.by_industry() のテスト。"""

    def test_by_industry(self) -> None:
        """業種名で検索して結果が返る。"""
        results = Company.by_industry("輸送用機器")
        assert len(results) >= 1

    def test_by_industry_limit(self) -> None:
        """limitを指定すると件数が制限される。"""
        results = Company.by_industry("輸送用機器", limit=3)
        assert len(results) <= 3

    def test_by_industry_empty(self) -> None:
        """存在しない業種名では空リストが返る。"""
        results = Company.by_industry("存在しない業種名")
        assert results == []


# ============================================================
# Company.all_listed() テスト
# ============================================================


class TestCompanyAllListed:
    """Company.all_listed() のテスト。"""

    def test_all_listed(self) -> None:
        """上場企業の一覧が返る。"""
        listed = Company.all_listed()
        assert len(listed) > 100

    def test_all_listed_limit(self) -> None:
        """limitを指定すると件数が制限される。"""
        listed = Company.all_listed(limit=10)
        assert len(listed) <= 10

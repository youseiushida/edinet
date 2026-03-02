"""Wave 1 E2E テスト: DEI (Document and Entity Information) 抽出。

実際の EDINET API を叩いて DEI 抽出の実用性を確認する。

テスト対象:
  - extract_dei() で全 27 フィールドが適切に抽出されるか
  - AccountingStandard / PeriodType 列挙型の正常変換
  - 日付フィールドのパース精度
  - 有報・半報・届出書など異なる書類種別での動作

使い方:
  EDINET_API_KEY=xxx python tools/wave1_e2e_dei.py
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import date

# ─── セットアップ ───────────────────────────────────────────────

from edinet import DocType, Filing, configure, documents
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)

configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)


# ─── テストユーティリティ ─────────────────────────────────────

passed = 0
failed = 0
errors: list[str] = []


def test_case(name: str):
    """テストケースデコレータ。"""

    def decorator(func):
        def wrapper():
            global passed, failed
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print(f"{'='*60}")
            try:
                func()
                passed += 1
                print(f"  ✓ PASSED")
            except Exception as e:
                failed += 1
                msg = f"  ✗ FAILED: {e}"
                print(msg)
                traceback.print_exc()
                errors.append(f"{name}: {e}")

        return wrapper

    return decorator


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {a!r} == {b!r}: {msg}")


def assert_isinstance(obj, cls, msg=""):
    if not isinstance(obj, cls):
        raise AssertionError(
            f"Expected {type(obj).__name__} to be {cls.__name__}: {msg}"
        )


def assert_not_none(obj, msg=""):
    if obj is None:
        raise AssertionError(f"Expected not None: {msg}")


# ─── 共通ヘルパー ────────────────────────────────────────────

def _fetch_filing_with_xbrl(
    target_date: str,
    doc_type: DocType | str | None = None,
    edinet_code: str | None = None,
) -> Filing | None:
    """XBRL 付きの Filing を 1 件取得する。"""
    kwargs: dict = {"date": target_date}
    if doc_type:
        kwargs["doc_type"] = doc_type
    if edinet_code:
        kwargs["edinet_code"] = edinet_code
    filings = documents(**kwargs)
    xbrl_filings = [f for f in filings if f.has_xbrl]
    return xbrl_filings[0] if xbrl_filings else None


def _extract_dei_from_filing(filing: Filing) -> DEI:
    """Filing から DEI を抽出する。"""
    xbrl_path, xbrl_bytes = filing.fetch()
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
    return extract_dei(parsed.facts)


# ─── テストケース ────────────────────────────────────────────

@test_case("DEI-1: 有報 (J-GAAP) の DEI 抽出")
def test_dei_annual_jgaap():
    """有価証券報告書(J-GAAP)の DEI が正しく抽出されることを確認。"""
    filing = _fetch_filing_with_xbrl(
        "2026-02-20", doc_type=DocType.ANNUAL_SECURITIES_REPORT
    )
    if filing is None:
        print("  SKIP: 2026-02-20 に有報なし")
        return
    print(f"  対象: {filing.filer_name} ({filing.doc_id})")

    dei = _extract_dei_from_filing(filing)
    assert_isinstance(dei, DEI, "DEI 型")

    # 基本フィールド
    assert_not_none(dei.edinet_code, "edinet_code")
    assert_not_none(dei.filer_name_ja, "filer_name_ja")
    print(f"  EDINET コード: {dei.edinet_code}")
    print(f"  提出者名: {dei.filer_name_ja}")
    print(f"  英語名: {dei.filer_name_en}")
    print(f"  証券コード: {dei.security_code}")

    # 会計基準
    if dei.accounting_standards is not None:
        print(f"  会計基準: {dei.accounting_standards!r}")
        # J-GAAP の有報が多いはず（ただし保証なし）
        if isinstance(dei.accounting_standards, AccountingStandard):
            print(f"  → Enum 変換成功: {dei.accounting_standards.name}")

    # 期間情報
    if dei.current_period_end_date is not None:
        assert_isinstance(dei.current_period_end_date, date, "current_period_end_date は date 型")
        print(f"  当会計期間終了日: {dei.current_period_end_date}")

    if dei.type_of_current_period is not None:
        print(f"  当会計期間種類: {dei.type_of_current_period!r}")
        if isinstance(dei.type_of_current_period, PeriodType):
            assert_true(
                dei.type_of_current_period in (PeriodType.FY, PeriodType.HY),
                "FY or HY",
            )

    # 連結の有無
    if dei.has_consolidated is not None:
        assert_isinstance(dei.has_consolidated, bool, "has_consolidated は bool")
        print(f"  連結あり: {dei.has_consolidated}")

    # 提出回数
    if dei.number_of_submission is not None:
        assert_isinstance(dei.number_of_submission, int, "number_of_submission は int")
        print(f"  提出回数: {dei.number_of_submission}")

    # 訂正フラグ
    if dei.amendment_flag is not None:
        assert_isinstance(dei.amendment_flag, bool, "amendment_flag は bool")
        print(f"  訂正フラグ: {dei.amendment_flag}")


@test_case("DEI-2: 全27フィールドの型チェック")
def test_dei_all_fields_type():
    """DEI の全 27 フィールドが正しい型であることを確認。"""
    filing = _fetch_filing_with_xbrl("2026-02-20", doc_type="120")
    if filing is None:
        print("  SKIP: 2026-02-20 に有報なし")
        return

    dei = _extract_dei_from_filing(filing)

    # 文字列 or None フィールド
    str_fields = [
        "edinet_code", "fund_code", "security_code",
        "filer_name_ja", "filer_name_en",
        "fund_name_ja", "fund_name_en",
        "cabinet_office_ordinance", "document_type",
        "industry_code_consolidated", "industry_code_non_consolidated",
        "identification_of_document_subject_to_amendment",
    ]
    for name in str_fields:
        val = getattr(dei, name)
        assert_true(
            val is None or isinstance(val, str),
            f"{name} は str | None であるべき (実際: {type(val).__name__})",
        )

    # date or None フィールド
    date_fields = [
        "current_fiscal_year_start_date", "current_period_end_date",
        "current_fiscal_year_end_date",
        "previous_fiscal_year_start_date", "comparative_period_end_date",
        "previous_fiscal_year_end_date",
        "next_fiscal_year_start_date", "end_date_of_next_semi_annual_period",
    ]
    for name in date_fields:
        val = getattr(dei, name)
        assert_true(
            val is None or isinstance(val, date),
            f"{name} は date | None であるべき (実際: {type(val).__name__}: {val!r})",
        )
        if val is not None:
            print(f"  {name}: {val}")

    # bool or None フィールド
    bool_fields = [
        "has_consolidated", "amendment_flag",
        "report_amendment_flag", "xbrl_amendment_flag",
    ]
    for name in bool_fields:
        val = getattr(dei, name)
        assert_true(
            val is None or isinstance(val, bool),
            f"{name} は bool | None であるべき (実際: {type(val).__name__})",
        )

    # int or None フィールド
    if dei.number_of_submission is not None:
        assert_isinstance(dei.number_of_submission, int, "number_of_submission は int")

    # Enum or str or None フィールド
    if dei.accounting_standards is not None:
        assert_true(
            isinstance(dei.accounting_standards, (AccountingStandard, str)),
            f"accounting_standards は AccountingStandard | str | None (実際: {type(dei.accounting_standards).__name__})",
        )
    if dei.type_of_current_period is not None:
        assert_true(
            isinstance(dei.type_of_current_period, (PeriodType, str)),
            f"type_of_current_period は PeriodType | str | None (実際: {type(dei.type_of_current_period).__name__})",
        )

    print(f"  全 27 フィールドの型チェック完了")


@test_case("DEI-3: 複数書類で DEI 比較")
def test_dei_multiple_filings():
    """同日の複数書類で DEI が一貫して抽出できることを確認。"""
    filings = documents("2026-02-20")
    xbrl_filings = [f for f in filings if f.has_xbrl][:5]  # 最大 5 件

    if not xbrl_filings:
        print("  SKIP: XBRL 付き書類なし")
        return

    print(f"  検証対象: {len(xbrl_filings)} 件")

    for f in xbrl_filings:
        dei = _extract_dei_from_filing(f)
        # EDINET コードは必ず存在するはず
        if dei.edinet_code is not None:
            assert_true(
                dei.edinet_code.startswith("E"),
                f"EDINET コードは E 始まり: {dei.edinet_code}",
            )
            assert_true(
                len(dei.edinet_code) == 6,
                f"EDINET コードは 6 文字: {dei.edinet_code}",
            )
        doc_type_str = f.doc_type_label_ja or f.doc_type_code or "?"
        print(
            f"  {f.doc_id}: {dei.filer_name_ja} | "
            f"基準={dei.accounting_standards!r} | "
            f"連結={dei.has_consolidated} | "
            f"書類={doc_type_str}"
        )


@test_case("DEI-4: 有報で FY、半報で HY")
def test_dei_period_type():
    """有報の type_of_current_period が FY であることを確認。"""
    filing = _fetch_filing_with_xbrl("2026-02-20", doc_type="120")
    if filing is None:
        print("  SKIP: 有報なし")
        return

    dei = _extract_dei_from_filing(filing)
    if dei.type_of_current_period is not None:
        print(f"  有報: type_of_current_period = {dei.type_of_current_period!r}")
        assert_eq(
            dei.type_of_current_period,
            PeriodType.FY,
            "有報は FY であるべき",
        )
    else:
        print("  type_of_current_period が None（ファンド等の可能性）")


@test_case("DEI-5: 会計基準の列挙型変換")
def test_dei_accounting_standard_enum():
    """AccountingStandard が正しく列挙型に変換されることを確認。"""
    # 複数の有報を取得して会計基準を確認
    filings = documents("2026-02-20", doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl][:10]

    if not xbrl_filings:
        print("  SKIP: 有報なし")
        return

    seen_standards: dict[str, int] = {}
    for f in xbrl_filings:
        dei = _extract_dei_from_filing(f)
        std = dei.accounting_standards
        if std is not None:
            key = str(std)
            seen_standards[key] = seen_standards.get(key, 0) + 1

    print(f"  検出された会計基準:")
    for std, count in sorted(seen_standards.items()):
        print(f"    {std}: {count} 件")

    assert_true(len(seen_standards) > 0, "少なくとも 1 つの会計基準が検出されるべき")


@test_case("DEI-6: 日付フィールドの整合性")
def test_dei_date_consistency():
    """DEI の日付フィールドが論理的に整合していることを確認。"""
    filing = _fetch_filing_with_xbrl("2026-02-20", doc_type="120")
    if filing is None:
        print("  SKIP: 有報なし")
        return

    dei = _extract_dei_from_filing(filing)

    # 当期開始日 < 当期終了日
    if dei.current_fiscal_year_start_date and dei.current_period_end_date:
        assert_true(
            dei.current_fiscal_year_start_date < dei.current_period_end_date,
            f"開始日 {dei.current_fiscal_year_start_date} < 終了日 {dei.current_period_end_date}",
        )
        print(
            f"  当期: {dei.current_fiscal_year_start_date} ～ {dei.current_period_end_date}"
        )

    # 前期開始日 < 前期終了日
    if dei.previous_fiscal_year_start_date and dei.previous_fiscal_year_end_date:
        assert_true(
            dei.previous_fiscal_year_start_date < dei.previous_fiscal_year_end_date,
            f"前期開始日 {dei.previous_fiscal_year_start_date} < 前期終了日 {dei.previous_fiscal_year_end_date}",
        )
        print(
            f"  前期: {dei.previous_fiscal_year_start_date} ～ {dei.previous_fiscal_year_end_date}"
        )

    # 前期終了日 < 当期終了日
    if dei.previous_fiscal_year_end_date and dei.current_period_end_date:
        assert_true(
            dei.previous_fiscal_year_end_date < dei.current_period_end_date,
            "前期終了日 < 当期終了日",
        )


# ─── 実行 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_dei_annual_jgaap,
        test_dei_all_fields_type,
        test_dei_multiple_filings,
        test_dei_period_type,
        test_dei_accounting_standard_enum,
        test_dei_date_consistency,
    ]

    print(f"Wave 1 E2E テスト: DEI ({len(tests)} テスト)")
    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed (total {passed + failed})")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
    sys.exit(1 if failed else 0)

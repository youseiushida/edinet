"""DEI (Document and Entity Information) 抽出モジュール。

XBRL インスタンスの facts から jpdei_cor 名前空間の DEI 要素を抽出し、
型安全な :class:`DEI` frozen dataclass に変換する。
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
import logging
import warnings
from dataclasses import dataclass
from typing import Any, Callable

from edinet.exceptions import EdinetWarning
from edinet.xbrl.parser import RawFact

__all__ = ["DEI", "AccountingStandard", "PeriodType", "extract_dei", "resolve_industry_code"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 列挙型
# ---------------------------------------------------------------------------


class AccountingStandard(str, enum.Enum):
    """会計基準（DEI で報告される値）。

    F-1.a.md より、AccountingStandardsDEI の取りうる値は以下の 4 種。
    xsi:nil="true" の場合は None として扱い、この Enum には含めない。
    """

    JAPAN_GAAP = "Japan GAAP"
    IFRS = "IFRS"
    US_GAAP = "US GAAP"
    JMIS = "JMIS"


class PeriodType(str, enum.Enum):
    """報告期間の種類（DEI で報告される値）。

    F-1.a.md より、TypeOfCurrentPeriodDEI の取りうる値は以下の 2 種。
    四半期報告書制度の廃止に伴い、四半期に対応する値は存在しない。
    """

    FY = "FY"  # 年度（通期）
    HY = "HY"  # 中間期


# ---------------------------------------------------------------------------
# DEI dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DEI:
    """XBRL インスタンスから抽出した DEI (Document and Entity Information)。

    全 27 個の非 Abstract DEI 要素を型安全なフィールドとして保持する。
    DEI タクソノミ（jpdei_cor）には提出者が独自の要素を追加することはないため
    （F-1.a.md [F17]）、このクラスの定義は安定している。

    Attributes:
        edinet_code: EDINETコード（例: "E00001"）。
        fund_code: ファンドコード。ファンド以外は None。
        security_code: 証券コード（5桁、例: "11110"）。該当なしは None。
        filer_name_ja: 提出者名（日本語表記）。
        filer_name_en: 提出者名（英語表記）。
        fund_name_ja: ファンド名称（日本語表記）。ファンド以外は None。
        fund_name_en: ファンド名称（英語表記）。ファンド以外は None。
        cabinet_office_ordinance: 府令名。
        document_type: 様式名（例: "第三号様式"）。
        accounting_standards: 会計基準（AccountingStandard 列挙型）。
            対象外書類は None。未知の値は文字列のまま格納。
        has_consolidated: 連結決算の有無。対象外書類は None。
        industry_code_consolidated: 別記事業（連結）の業種コード。該当なしは None。
        industry_code_non_consolidated: 別記事業（個別）の業種コード。該当なしは None。
        current_fiscal_year_start_date: 当事業年度開始日。
        current_period_end_date: 当会計期間終了日。
        type_of_current_period: 当会計期間の種類（PeriodType 列挙型）。
            未知の値は文字列のまま格納。
        current_fiscal_year_end_date: 当事業年度終了日（決算日）。
        previous_fiscal_year_start_date: 前事業年度開始日。
        comparative_period_end_date: 比較対象会計期間終了日。
        previous_fiscal_year_end_date: 前事業年度終了日。
        next_fiscal_year_start_date: 次の事業年度開始日。
        end_date_of_next_semi_annual_period: 次の中間期の会計期間終了日。
        number_of_submission: 提出回数（当初提出=1、1回目訂正=2、...）。
        amendment_flag: 訂正の有無。
        identification_of_document_subject_to_amendment: 訂正対象書類の書類管理番号。
        report_amendment_flag: 記載事項訂正のフラグ。
        xbrl_amendment_flag: XBRL訂正のフラグ。
    """

    # (A) 提出者情報
    edinet_code: str | None = None
    fund_code: str | None = None
    security_code: str | None = None
    filer_name_ja: str | None = None
    filer_name_en: str | None = None
    fund_name_ja: str | None = None
    fund_name_en: str | None = None
    # (B) 提出書類情報
    cabinet_office_ordinance: str | None = None
    document_type: str | None = None
    accounting_standards: AccountingStandard | str | None = None
    has_consolidated: bool | None = None
    industry_code_consolidated: str | None = None
    industry_code_non_consolidated: str | None = None
    # (C) 当会計期間
    current_fiscal_year_start_date: datetime.date | None = None
    current_period_end_date: datetime.date | None = None
    type_of_current_period: PeriodType | str | None = None
    current_fiscal_year_end_date: datetime.date | None = None
    # (D) 比較対象会計期間
    previous_fiscal_year_start_date: datetime.date | None = None
    comparative_period_end_date: datetime.date | None = None
    previous_fiscal_year_end_date: datetime.date | None = None
    # (E) 次の中間期
    next_fiscal_year_start_date: datetime.date | None = None
    end_date_of_next_semi_annual_period: datetime.date | None = None
    # (F) 訂正関連
    number_of_submission: int | None = None
    amendment_flag: bool | None = None
    identification_of_document_subject_to_amendment: str | None = None
    report_amendment_flag: bool | None = None
    xbrl_amendment_flag: bool | None = None

    def __repr__(self) -> str:
        """None フィールドを省略した簡潔な表示を返す。"""
        parts: list[str] = []
        for f in dataclasses.fields(self):
            v = getattr(self, f.name)
            if v is not None:
                parts.append(f"{f.name}={v!r}")
        return f"DEI({', '.join(parts)})"


# ---------------------------------------------------------------------------
# 名前空間判定
# ---------------------------------------------------------------------------

_JPDEI_NS_PREFIX = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/"
_JPDEI_NS_SUFFIX = "/jpdei_cor"


def _is_dei_namespace(namespace_uri: str) -> bool:
    """jpdei_cor 名前空間に属するか判定する。

    Args:
        namespace_uri: RawFact の名前空間 URI。

    Returns:
        jpdei_cor パターンに合致する場合 True。
    """
    return namespace_uri.startswith(_JPDEI_NS_PREFIX) and namespace_uri.endswith(
        _JPDEI_NS_SUFFIX
    )


# ---------------------------------------------------------------------------
# 型変換ヘルパー
# ---------------------------------------------------------------------------

_Converter = Callable[[str], Any]


def _convert_date(value_raw: str) -> datetime.date:
    """YYYY-MM-DD 形式の文字列を datetime.date に変換する。

    Args:
        value_raw: 日付文字列。

    Returns:
        変換された date オブジェクト。

    Raises:
        ValueError: 不正な日付形式の場合。
    """
    return datetime.date.fromisoformat(value_raw.strip())


def _convert_bool(value_raw: str) -> bool:
    """XBRL の boolean 値を Python bool に変換する。

    xs:boolean で許容される値は "true"/"false"/"1"/"0" の 4 つのみ。
    不正な値の場合は EdinetWarning を出し False にフォールバックする。

    Args:
        value_raw: boolean 文字列。

    Returns:
        変換された bool 値。
    """
    v = value_raw.strip().lower()
    if v in ("true", "1"):
        return True
    if v in ("false", "0"):
        return False
    warnings.warn(
        f"不正な boolean 値: {value_raw!r}。'true'/'false'/'1'/'0' を期待。",
        EdinetWarning,
        stacklevel=3,
    )
    return False


def _convert_int(value_raw: str) -> int:
    """文字列を非負整数に変換する。

    NumberOfSubmissionDEI の XSD 型は nonNegativeIntegerItemType。
    負の値は仕様上存在しないため警告を出す。

    Args:
        value_raw: 整数文字列。

    Returns:
        変換された int 値。

    Raises:
        ValueError: 整数として解釈できない場合。
    """
    result = int(value_raw.strip())
    if result < 0:
        warnings.warn(
            f"NumberOfSubmissionDEI に負の値: {result}",
            EdinetWarning,
            stacklevel=3,
        )
    return result


def _convert_accounting_standard(value_raw: str) -> AccountingStandard | str:
    """AccountingStandard Enum に変換を試み、未知の値は str のまま返す。

    Args:
        value_raw: 会計基準の文字列値。

    Returns:
        既知の値は AccountingStandard、未知の値は str。
    """
    stripped = value_raw.strip()
    try:
        return AccountingStandard(stripped)
    except ValueError:
        warnings.warn(
            f"未知の会計基準: {value_raw!r}。"
            f"既知の値: {[e.value for e in AccountingStandard]}",
            EdinetWarning,
            stacklevel=3,
        )
        return stripped


def _convert_period_type(value_raw: str) -> PeriodType | str:
    """PeriodType Enum に変換を試み、未知の値は str のまま返す。

    Args:
        value_raw: 報告期間種別の文字列値。

    Returns:
        既知の値は PeriodType、未知の値は str。
    """
    stripped = value_raw.strip()
    try:
        return PeriodType(stripped)
    except ValueError:
        warnings.warn(
            f"未知の報告期間種別: {value_raw!r}。"
            f"既知の値: {[e.value for e in PeriodType]}",
            EdinetWarning,
            stacklevel=3,
        )
        return stripped


# ---------------------------------------------------------------------------
# マッピング定数
# ---------------------------------------------------------------------------

_DEI_FIELD_MAP: dict[str, tuple[str, _Converter]] = {
    "EDINETCodeDEI": ("edinet_code", str.strip),
    "FundCodeDEI": ("fund_code", str.strip),
    "SecurityCodeDEI": ("security_code", str.strip),
    "FilerNameInJapaneseDEI": ("filer_name_ja", str.strip),
    "FilerNameInEnglishDEI": ("filer_name_en", str.strip),
    "FundNameInJapaneseDEI": ("fund_name_ja", str.strip),
    "FundNameInEnglishDEI": ("fund_name_en", str.strip),
    "CabinetOfficeOrdinanceDEI": ("cabinet_office_ordinance", str.strip),
    "DocumentTypeDEI": ("document_type", str.strip),
    "AccountingStandardsDEI": ("accounting_standards", _convert_accounting_standard),
    "WhetherConsolidatedFinancialStatementsArePreparedDEI": (
        "has_consolidated",
        _convert_bool,
    ),
    "IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI": (
        "industry_code_consolidated",
        str.strip,
    ),
    "IndustryCodeWhenFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI": (
        "industry_code_non_consolidated",
        str.strip,
    ),
    "CurrentFiscalYearStartDateDEI": (
        "current_fiscal_year_start_date",
        _convert_date,
    ),
    "CurrentPeriodEndDateDEI": ("current_period_end_date", _convert_date),
    "TypeOfCurrentPeriodDEI": ("type_of_current_period", _convert_period_type),
    "CurrentFiscalYearEndDateDEI": (
        "current_fiscal_year_end_date",
        _convert_date,
    ),
    "PreviousFiscalYearStartDateDEI": (
        "previous_fiscal_year_start_date",
        _convert_date,
    ),
    "ComparativePeriodEndDateDEI": ("comparative_period_end_date", _convert_date),
    "PreviousFiscalYearEndDateDEI": (
        "previous_fiscal_year_end_date",
        _convert_date,
    ),
    "NextFiscalYearStartDateDEI": ("next_fiscal_year_start_date", _convert_date),
    "EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI": (
        "end_date_of_next_semi_annual_period",
        _convert_date,
    ),
    "NumberOfSubmissionDEI": ("number_of_submission", _convert_int),
    "AmendmentFlagDEI": ("amendment_flag", _convert_bool),
    "IdentificationOfDocumentSubjectToAmendmentDEI": (
        "identification_of_document_subject_to_amendment",
        str.strip,
    ),
    "ReportAmendmentFlagDEI": ("report_amendment_flag", _convert_bool),
    "XBRLAmendmentFlagDEI": ("xbrl_amendment_flag", _convert_bool),
}


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def extract_dei(facts: tuple[RawFact, ...]) -> DEI:
    """ParsedXBRL の facts から DEI 要素を抽出する。

    Args:
        facts: ParsedXBRL.facts から得られる RawFact のタプル。

    Returns:
        DEI dataclass。XBRL インスタンスに DEI 要素が存在しない場合は
        全フィールドが None の DEI を返す（エラーにはしない）。

    Note:
        jpdei_cor 名前空間（URI パターン:
        ``http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/*/jpdei_cor``）
        に属する Fact のみを対象とする。

        DEI 要素は全て FilingDateInstant コンテキストに紐づくが（F-1b.a.md）、
        この関数は contextRef によるフィルタリングは行わない。
        複数の同名 DEI Fact が存在する場合は最初に出現したものを使用する。
    """
    dei_values: dict[str, Any] = {}

    for fact in facts:
        # 1. jpdei_cor 名前空間のみ対象
        if not _is_dei_namespace(fact.namespace_uri):
            continue

        # 2. マッピングテーブルに存在する concept のみ対象
        mapping = _DEI_FIELD_MAP.get(fact.local_name)
        if mapping is None:
            continue

        field_name, converter = mapping

        # 3. 同名 concept が複数ある場合は最初のものを使用
        if field_name in dei_values:
            continue

        # 4. nil の場合は None
        if fact.is_nil or fact.value_raw is None:
            dei_values[field_name] = None
        else:
            # 5. 型変換
            try:
                dei_values[field_name] = converter(fact.value_raw)
            except (ValueError, TypeError) as e:
                warnings.warn(
                    f"DEI 要素 {fact.local_name} の値変換に失敗: "
                    f"{fact.value_raw!r} ({e})",
                    EdinetWarning,
                    stacklevel=2,
                )
                dei_values[field_name] = None

        # 6. 全 DEI フィールドが揃ったら早期終了
        if len(dei_values) == len(_DEI_FIELD_MAP):
            break

    return DEI(**dei_values)


# ---------------------------------------------------------------------------
# 業種コード変換
# ---------------------------------------------------------------------------

_VOCAB_TO_INDUSTRY: dict[str, str] = {
    "CNS": "cns",  # 建設業
    "BNK": "bk1",  # 銀行（代表。bk2 との区別は DTS 解決が必要）
    "CNA": "cna",  # 建設保証業
    "SEC": "sec",  # 第一種金融商品取引業
    "INS": "in1",  # 保険（代表。in2 との区別は DTS 解決が必要）
    "RWY": "rwy",  # 鉄道事業
    "WAT": "wat",  # 海運事業
    "HWY": "hwy",  # 高速道路事業
    "ELC": "elc",  # 電気通信事業
    "ELE": "ele",  # 電気事業
    "GAS": "gas",  # ガス事業
    "LIQ": "liq",  # 資産流動化業
    "IVT": "ivt",  # 投資運用業
    "INV": "inv",  # 投資業
    "SPF": "spf",  # 特定金融業
    "MED": "med",  # 社会医療法人
    "EDU": "edu",  # 学校法人
    "CMD": "cmd",  # 商品先物取引業
    "LEA": "lea",  # リース事業
    "FND": "fnd",  # 投資信託受益証券
    # CTE / None → 一般事業会社 → None 返却（辞書に含めない）
}


def resolve_industry_code(
    dei: DEI, *, prefer_consolidated: bool = True
) -> str | None:
    """DEI の業種コード（語彙層）を関係層の業種コードに変換する。

    語彙層コード (例: ``"BNK"``) をタクソノミの関係層で使用される
    業種コード (例: ``"bk1"``) に変換する。一般事業会社 (``"CTE"``)
    および未設定 (``None``) は ``None`` を返す。

    Args:
        dei: ``extract_dei()`` で取得した DEI。
        prefer_consolidated: ``True`` なら連結の業種コードを優先、
            ``False`` なら個別の業種コードを優先する。
            優先側が ``None`` の場合は非優先側にフォールバックする。

    Returns:
        関係層の業種コード文字列。一般事業会社・未設定・未知のコードは ``None``。
    """
    if prefer_consolidated:
        vocab = dei.industry_code_consolidated or dei.industry_code_non_consolidated
    else:
        vocab = dei.industry_code_non_consolidated or dei.industry_code_consolidated
    if vocab is None:
        return None
    return _VOCAB_TO_INDUSTRY.get(vocab)

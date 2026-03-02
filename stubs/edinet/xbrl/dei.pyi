import datetime
import enum
from dataclasses import dataclass
from edinet.xbrl.parser import RawFact

__all__ = ['DEI', 'AccountingStandard', 'PeriodType', 'extract_dei', 'resolve_industry_code']

class AccountingStandard(str, enum.Enum):
    '''会計基準（DEI で報告される値）。

    F-1.a.md より、AccountingStandardsDEI の取りうる値は以下の 4 種。
    xsi:nil="true" の場合は None として扱い、この Enum には含めない。
    '''
    JAPAN_GAAP = 'Japan GAAP'
    IFRS = 'IFRS'
    US_GAAP = 'US GAAP'
    JMIS = 'JMIS'

class PeriodType(str, enum.Enum):
    """報告期間の種類（DEI で報告される値）。

    F-1.a.md より、TypeOfCurrentPeriodDEI の取りうる値は以下の 2 種。
    四半期報告書制度の廃止に伴い、四半期に対応する値は存在しない。
    """
    FY = 'FY'
    HY = 'HY'

@dataclass(frozen=True, slots=True)
class DEI:
    '''XBRL インスタンスから抽出した DEI (Document and Entity Information)。

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
    '''
    edinet_code: str | None = ...
    fund_code: str | None = ...
    security_code: str | None = ...
    filer_name_ja: str | None = ...
    filer_name_en: str | None = ...
    fund_name_ja: str | None = ...
    fund_name_en: str | None = ...
    cabinet_office_ordinance: str | None = ...
    document_type: str | None = ...
    accounting_standards: AccountingStandard | str | None = ...
    has_consolidated: bool | None = ...
    industry_code_consolidated: str | None = ...
    industry_code_non_consolidated: str | None = ...
    current_fiscal_year_start_date: datetime.date | None = ...
    current_period_end_date: datetime.date | None = ...
    type_of_current_period: PeriodType | str | None = ...
    current_fiscal_year_end_date: datetime.date | None = ...
    previous_fiscal_year_start_date: datetime.date | None = ...
    comparative_period_end_date: datetime.date | None = ...
    previous_fiscal_year_end_date: datetime.date | None = ...
    next_fiscal_year_start_date: datetime.date | None = ...
    end_date_of_next_semi_annual_period: datetime.date | None = ...
    number_of_submission: int | None = ...
    amendment_flag: bool | None = ...
    identification_of_document_subject_to_amendment: str | None = ...
    report_amendment_flag: bool | None = ...
    xbrl_amendment_flag: bool | None = ...

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
def resolve_industry_code(dei: DEI, *, prefer_consolidated: bool = True) -> str | None:
    '''DEI の業種コード（語彙層）を関係層の業種コードに変換する。

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
    '''

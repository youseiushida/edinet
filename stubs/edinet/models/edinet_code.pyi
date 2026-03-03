from _typeshed import Incomplete
from edinet.exceptions import EdinetWarning as EdinetWarning
from pydantic import BaseModel

class EdinetCodeEntry(BaseModel):
    """EDINETコードリストの1行。"""
    model_config: Incomplete
    edinet_code: str
    submitter_type: str
    listing_status: str | None
    consolidated: str | None
    capital_million_yen: int | None
    fiscal_year_end: str | None
    submitter_name: str
    submitter_name_en: str | None
    submitter_name_yomi: str | None
    address: str | None
    industry: str | None
    sec_code: str | None
    corporate_number: str | None

EDINET_CODE_RECORD_COUNT: Incomplete

def get_edinet_code(code: str) -> EdinetCodeEntry | None:
    """EDINETコードから EdinetCodeEntry を返す。"""
def all_edinet_codes() -> list[EdinetCodeEntry]:
    """全EDINETコードの一覧を返す。"""
def search_edinet_codes(query: str, *, limit: int = 20) -> list[EdinetCodeEntry]:
    '''企業名でEdinetCodeEntryを部分一致検索する。

    ``submitter_name`` / ``submitter_name_en`` / ``submitter_name_yomi`` の
    いずれかに ``query`` が含まれるエントリを返す。
    全角半角を正規化（NFKC）し、大文字・小文字を区別しない。

    結果は関連度順にソートされる:
    - 名前が query で始まるもの（prefix match）が先頭
    - 名前に query を含むもの（contains match）が後続

    Args:
        query: 検索キーワード。空文字の場合は空リストを返す。
            全角・半角どちらでも検索可能（例: ``"三菱UFJ"`` と
            ``"三菱ＵＦＪ"`` は同一視される）。
        limit: 最大返却件数。0で無制限。

    Returns:
        マッチしたEdinetCodeEntryのリスト（関連度順）。
    '''
def get_edinet_code_by_sec_code(sec_code: str) -> EdinetCodeEntry | None:
    '''証券コードからEdinetCodeEntryを返す。

    4桁の場合は末尾に ``"0"`` を付与して5桁にしてから検索する。

    Args:
        sec_code: 証券コード（4桁または5桁）。

    Returns:
        マッチしたEdinetCodeEntry。見つからない場合はNone。
    '''
def get_edinet_codes_by_industry(industry: str, *, limit: int = 100) -> list[EdinetCodeEntry]:
    '''業種名でEdinetCodeEntryを検索する。

    完全一致を優先し、見つからなければ部分一致にフォールバックする。
    例: ``"銀行"`` → ``"銀行業"`` にマッチ。

    Args:
        industry: 業種名（例: ``"銀行業"``、``"銀行"``）。
        limit: 最大返却件数。0で無制限。

    Returns:
        マッチしたEdinetCodeEntryのリスト。
    '''
def get_listed_edinet_codes(*, limit: int = 0) -> list[EdinetCodeEntry]:
    '''上場企業のEdinetCodeEntry一覧を返す。

    ``listing_status == "上場"`` のエントリを返す。

    Args:
        limit: 最大返却件数。0で無制限。

    Returns:
        上場企業のEdinetCodeEntryのリスト。
    '''

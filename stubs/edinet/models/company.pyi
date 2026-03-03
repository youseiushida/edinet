from _typeshed import Incomplete
from datetime import date as DateType
from edinet._validators import normalize_edinet_code as normalize_edinet_code
from edinet.models.doc_types import DocType as DocType
from edinet.models.edinet_code import EdinetCodeEntry as EdinetCodeEntry
from edinet.models.filing import Filing as Filing
from pydantic import BaseModel, computed_field

class Company(BaseModel):
    """提出者（企業）を表すモデル。"""
    model_config: Incomplete
    edinet_code: str
    name_ja: str | None
    sec_code: str | None
    @computed_field
    @property
    def ticker(self) -> str | None:
        """証券コード 4 桁を返す。"""
    @classmethod
    def from_filing(cls, filing: Filing) -> Company | None:
        """Filing から Company を構築する。

        Args:
            filing: 変換元の提出書類。

        Returns:
            `filing.edinet_code` がある場合は `Company`。無い場合は `None`。
        """
    def get_filings(self, date: str | DateType | None = None, *, start: str | DateType | None = None, end: str | DateType | None = None, doc_type: DocType | str | None = None) -> list[Filing]:
        """この企業の提出書類一覧を返す。

        Args:
            date: 単日指定。
            start: 範囲指定の開始日。
            end: 範囲指定の終了日。
            doc_type: 書類種別フィルタ。

        Returns:
            企業コードで絞り込まれた提出書類一覧。

        Note:
            `date` / `start` / `end` がすべて省略された場合は JST 当日を使う。
        """
    def latest(self, doc_type: DocType | str | None = None, *, start: str | DateType | None = None, end: str | DateType | None = None) -> Filing | None:
        '''この企業の最新の Filing を返す。

        ``get_filings()`` で書類一覧を取得し、``submit_date_time`` の降順で
        最初の Filing を返す。該当なしの場合は ``None``。

        ``start`` / ``end`` を省略した場合、過去 90 日間を検索する。

        Args:
            doc_type: 書類種別フィルタ。日本語文字列（``"有価証券報告書"``）
                または ``DocType`` Enum、コード文字列（``"120"``）を指定可能。
            start: 検索範囲の開始日。省略時は今日から 90 日前。
                ``end`` のみ指定した場合は ``end - 90日`` が自動設定される。
            end: 検索範囲の終了日。省略時は今日。
                ``start`` のみ指定した場合は今日が自動設定される。

        Returns:
            最新の Filing。見つからない場合は ``None``。

        Note:
            末尾（最新日）から1日ずつ探索し、該当書類が見つかった時点で返す。
            有報は決算期末の3ヶ月後（6月末）に集中するため、直近から探すと
            高速に見つかる。最悪ケースでも検索期間分の API コールが発生する。
        '''
    @classmethod
    def search(cls, query: str, *, limit: int = 20) -> list[Company]:
        '''企業名でCompanyを部分一致検索する。

        ``submitter_name`` / ``submitter_name_en`` / ``submitter_name_yomi`` の
        いずれかに ``query`` が含まれるエントリをCompanyに変換して返す。
        大文字・小文字を区別しない。

        結果は関連度順にソートされる:
        - 名前が query で始まるもの（prefix match）が先頭
        - 名前に query を含むもの（contains match）が後続

        Args:
            query: 検索キーワード。空文字の場合は空リストを返す。
            limit: 最大返却件数。0で無制限。デフォルト20。

        Returns:
            マッチしたCompanyのリスト（関連度順）。

        利用例:
            >>> results = Company.search("トヨタ")
            >>> results[0].name_ja
            \'トヨタ自動車株式会社\'
        '''
    @classmethod
    def from_edinet_code(cls, code: str) -> Company | None:
        '''EDINETコードからCompanyを構築する。

        Args:
            code: EDINETコード（例: ``"E02144"``）。

        Returns:
            Company。見つからない場合はNone。

        利用例:
            >>> company = Company.from_edinet_code("E02144")
            >>> company.name_ja
            \'トヨタ自動車株式会社\'
        '''
    @classmethod
    def from_sec_code(cls, sec_code: str) -> Company | None:
        '''証券コードからCompanyを構築する。

        4桁の場合は末尾に ``"0"`` を付与して5桁にしてから検索する。
        前後の空白は自動的に除去される。

        Args:
            sec_code: 証券コード（4桁または5桁）。

        Returns:
            Company。見つからない場合はNone。

        利用例:
            >>> company = Company.from_sec_code("7203")
            >>> company.edinet_code
            \'E02144\'
            >>> company = Company.from_sec_code("72030")  # 5桁でもOK
            >>> company.edinet_code
            \'E02144\'
        '''
    @classmethod
    def by_industry(cls, industry: str, *, limit: int = 100) -> list[Company]:
        '''業種名でCompanyを検索する。

        ``industry`` フィールドの完全一致で検索する。

        Args:
            industry: 業種名（例: ``"輸送用機器"``）。
            limit: 最大返却件数。0で無制限。デフォルト100。

        Returns:
            マッチしたCompanyのリスト。

        利用例:
            >>> results = Company.by_industry("輸送用機器")
            >>> len(results) > 0
            True
        '''
    @classmethod
    def all_listed(cls, *, limit: int = 0) -> list[Company]:
        """上場企業のCompany一覧を返す。

        Args:
            limit: 最大返却件数。0で無制限（デフォルト）。

        Returns:
            上場企業のCompanyのリスト。

        利用例:
            >>> listed = Company.all_listed()
            >>> len(listed) > 100
            True
        """

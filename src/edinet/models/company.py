"""提出者（企業）モデル。"""
from __future__ import annotations

from datetime import date as DateType, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from edinet._validators import normalize_edinet_code

if TYPE_CHECKING:
    from edinet.models.doc_types import DocType
    from edinet.models.edinet_code import EdinetCodeEntry
    from edinet.models.filing import Filing


def _today_jst() -> DateType:
    """EDINET 基準（JST）の日付を返す。

    Returns:
        JST の当日。

    Note:
        tzdb 未導入環境では UTC+9 固定でフォールバックする。
    """
    try:
        return datetime.now(ZoneInfo("Asia/Tokyo")).date()
    except ZoneInfoNotFoundError:
        return (datetime.now(timezone.utc) + timedelta(hours=9)).date()


def _entry_to_company(entry: EdinetCodeEntry) -> Company:
    """EdinetCodeEntryからCompanyを構築する。

    Args:
        entry: 変換元のEdinetCodeEntry。

    Returns:
        Companyオブジェクト。

    Note:
        ``name_ja`` は ``EdinetCodeEntry.submitter_name``（EDINETコード一覧CSV由来）
        を使用する。``Company.from_filing()`` は ``Filing.filer_name``（APIレスポンス由来）
        を使用するため、同一企業でも情報源の違いにより値が異なる場合がある。
    """
    return Company(
        edinet_code=entry.edinet_code,
        name_ja=entry.submitter_name,
        sec_code=entry.sec_code,
    )


class Company(BaseModel):
    """提出者（企業）を表すモデル。"""

    model_config = ConfigDict(frozen=True)

    edinet_code: str
    name_ja: str | None = None
    sec_code: str | None = None

    @field_validator("edinet_code")
    @classmethod
    def _validate_edinet_code(cls, value: str) -> str:
        """EDINET コードを正規化して検証する。"""
        normalized = normalize_edinet_code(value, allow_none=False)
        assert isinstance(normalized, str)
        return normalized

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ticker(self) -> str | None:
        """証券コード 4 桁を返す。"""
        if self.sec_code and len(self.sec_code) >= 4:
            return self.sec_code[:4]
        return None

    @classmethod
    def from_filing(cls, filing: Filing) -> Company | None:
        """Filing から Company を構築する。

        Args:
            filing: 変換元の提出書類。

        Returns:
            `filing.edinet_code` がある場合は `Company`。無い場合は `None`。
        """
        if filing.edinet_code is None:
            return None
        return cls(
            edinet_code=filing.edinet_code,
            name_ja=filing.filer_name,
            sec_code=filing.sec_code,
        )

    def get_filings(
        self,
        date: str | DateType | None = None,
        *,
        start: str | DateType | None = None,
        end: str | DateType | None = None,
        doc_type: DocType | str | None = None,
    ) -> list[Filing]:
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
        from edinet import documents

        resolved_date = date
        if resolved_date is None and start is None and end is None:
            resolved_date = _today_jst()

        return documents(
            resolved_date,
            start=start,
            end=end,
            doc_type=doc_type,
            edinet_code=self.edinet_code,
        )

    def latest(
        self,
        doc_type: DocType | str | None = None,
        *,
        start: str | DateType | None = None,
        end: str | DateType | None = None,
    ) -> Filing | None:
        """この企業の最新の Filing を返す。

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
        """
        import logging

        from edinet import documents as _documents

        logger = logging.getLogger(__name__)

        # start/end の自動補完
        if start is None and end is None:
            end_date = _today_jst()
            start_date = end_date - timedelta(days=89)
            logger.debug(
                "latest(): start/end 未指定のため過去 90 日間 (%s 〜 %s) を検索します",
                start_date, end_date,
            )
        else:
            if isinstance(start, str):
                from datetime import date as _date
                start = _date.fromisoformat(start)
            if isinstance(end, str):
                from datetime import date as _date
                end = _date.fromisoformat(end)
            end_date = end if end is not None else _today_jst()
            start_date = start if start is not None else end_date - timedelta(days=89)

        # 末尾から1日ずつ探索（最新の Filing を高速に見つける）
        current = end_date
        best: Filing | None = None
        while current >= start_date:
            try:
                day_filings = _documents(
                    current,
                    doc_type=doc_type,
                    edinet_code=self.edinet_code,
                )
            except Exception:
                day_filings = []
            if day_filings:
                # この日の最新を候補にして即 return
                best = max(day_filings, key=lambda f: f.submit_date_time)
                return best
            current -= timedelta(days=1)

        return None

    # ------------------------------------------------------------------
    # 検索 API（Wave 6 Lane 1）
    # ------------------------------------------------------------------

    @classmethod
    def search(cls, query: str, *, limit: int = 20) -> list[Company]:
        """企業名でCompanyを部分一致検索する。

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
            'トヨタ自動車株式会社'
        """
        from edinet.models.edinet_code import search_edinet_codes

        entries = search_edinet_codes(query, limit=limit)
        return [_entry_to_company(e) for e in entries]

    @classmethod
    def from_edinet_code(cls, code: str) -> Company | None:
        """EDINETコードからCompanyを構築する。

        Args:
            code: EDINETコード（例: ``"E02144"``）。

        Returns:
            Company。見つからない場合はNone。

        利用例:
            >>> company = Company.from_edinet_code("E02144")
            >>> company.name_ja
            'トヨタ自動車株式会社'
        """
        from edinet.models.edinet_code import get_edinet_code

        entry = get_edinet_code(code)
        if entry is None:
            return None
        return _entry_to_company(entry)

    @classmethod
    def from_sec_code(cls, sec_code: str) -> Company | None:
        """証券コードからCompanyを構築する。

        4桁の場合は末尾に ``"0"`` を付与して5桁にしてから検索する。
        前後の空白は自動的に除去される。

        Args:
            sec_code: 証券コード（4桁または5桁）。

        Returns:
            Company。見つからない場合はNone。

        利用例:
            >>> company = Company.from_sec_code("7203")
            >>> company.edinet_code
            'E02144'
            >>> company = Company.from_sec_code("72030")  # 5桁でもOK
            >>> company.edinet_code
            'E02144'
        """
        from edinet.models.edinet_code import get_edinet_code_by_sec_code

        entry = get_edinet_code_by_sec_code(sec_code)
        if entry is None:
            return None
        return _entry_to_company(entry)

    @classmethod
    def by_industry(cls, industry: str, *, limit: int = 100) -> list[Company]:
        """業種名でCompanyを検索する。

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
        """
        from edinet.models.edinet_code import get_edinet_codes_by_industry

        entries = get_edinet_codes_by_industry(industry, limit=limit)
        return [_entry_to_company(e) for e in entries]

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
        from edinet.models.edinet_code import get_listed_edinet_codes

        entries = get_listed_edinet_codes(limit=limit)
        return [_entry_to_company(e) for e in entries]

    def __str__(self) -> str:
        """簡潔な文字列表現を返す。"""
        name = self.name_ja or "(不明)"
        return f"Company({self.edinet_code} | {name} | {self.ticker})"

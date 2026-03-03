from _typeshed import Incomplete
from datetime import date, datetime
from edinet.financial.statements import Statements as Statements
from edinet.models.company import Company as Company
from edinet.models.doc_types import DocType as DocType
from edinet.models.form_code import FormCodeEntry as FormCodeEntry
from edinet.models.ordinance_code import OrdinanceCode as OrdinanceCode
from pydantic import BaseModel, computed_field
from typing import Any

class Filing(BaseModel):
    '''EDINET に提出された書類1件を表すモデル。

    EDINET API の書類一覧レスポンス (results 配列の1要素) から生成する。
    API 由来の全29フィールドを保持し、データを一切落とさない。
    加えて派生フィールド（doc_type, filing_date, ticker, doc_type_label_ja）を
    computed_field として提供する。
    また、`ordinance` / `form` は model_dump に含めない `@property` として提供する。

    **Note: コード値の型について**
    - `docTypeCode`: `DocType` Enum に変換して保持する（Day 4 のスコープ）。
    - `ordinanceCode`, `formCode`, `fundCode`: Day 4 時点では `str` としてそのまま保持する。これらは定義数が多く更新頻度も高いため、将来的にメタプログラミングで生成された専用 Enum/Model に移行する予定（Day 4.5 以降）。


    Note:
        日時フィールド（submit_date_time, ope_date_time）は EDINET API が返す
        JST（日本時間, UTC+9）を naive datetime として保持する。
        タイムゾーン情報は付与されない。

    利用例:
        >>> result = get_documents("2026-02-07")
        >>> filings = Filing.from_api_list(result)
        >>> f = filings[0]
        >>> f.doc_id
        \'S100XXXX\'
        >>> f.doc_type
        DocType.ANNUAL_SECURITIES_REPORT
        >>> f.filing_date
        datetime.date(2026, 2, 7)
    '''
    model_config: Incomplete
    seq_number: int
    doc_id: str
    doc_type_code: str | None
    ordinance_code: str | None
    form_code: str | None
    edinet_code: str | None
    sec_code: str | None
    jcn: str | None
    filer_name: str | None
    fund_code: str | None
    submit_date_time: datetime
    period_start: date | None
    period_end: date | None
    doc_description: str | None
    issuer_edinet_code: str | None
    subject_edinet_code: str | None
    subsidiary_edinet_code: str | None
    current_report_reason: str | None
    parent_doc_id: str | None
    ope_date_time: datetime | None
    withdrawal_status: str
    doc_info_edit_status: str
    disclosure_status: str
    has_xbrl: bool
    has_pdf: bool
    has_attachment: bool
    has_english: bool
    has_csv: bool
    legal_status: str
    @computed_field
    @property
    def doc_type(self) -> DocType | None:
        """doc_type_code に対応する DocType Enum。

        未知のコードの場合は None（DocType.from_code() が warning を出す）。
        コード自体が None の場合も None。
        dict lookup（O(1)）なのでキャッシュ不要。
        """
    @computed_field
    @property
    def filing_date(self) -> date:
        """提出日（submit_date_time の日付部分）。

        PLAN.md §4 の Filing モデル定義で filing_date: date と定義。
        submit_date_time から導出することで二重管理を避ける。
        """
    @property
    def ordinance(self) -> OrdinanceCode | None:
        """府令コード Enum。"""
    @property
    def form(self) -> FormCodeEntry | None:
        """様式コード情報。"""
    @property
    def company(self) -> Company | None:
        """提出者 Company を返す。"""
    def clear_fetch_cache(self) -> None:
        """`fetch()` / `fetch_pdf()` のキャッシュを破棄する。"""
    def fetch_pdf(self, *, refresh: bool = False) -> bytes:
        """提出書類の PDF をダウンロードして返す。

        3層キャッシュ（メモリ → ディスク → ネットワーク）を使用する。

        Args:
            refresh: ``True`` の場合は PDF キャッシュを破棄して再取得する。

        Returns:
            PDF のバイト列。

        Raises:
            EdinetAPIError: 当該書類に PDF が含まれていない場合。
            EdinetParseError: ダウンロードの入力不正の正規化。
            EdinetError: 通信層失敗。
        """
    async def afetch_pdf(self, *, refresh: bool = False) -> bytes:
        """提出書類の PDF を非同期でダウンロードして返す。

        ``fetch_pdf()`` の非同期版。

        Args:
            refresh: ``True`` の場合は PDF キャッシュを破棄して再取得する。

        Returns:
            PDF のバイト列。

        Raises:
            EdinetAPIError: 当該書類に PDF が含まれていない場合。
            EdinetParseError: ダウンロードの入力不正の正規化。
            EdinetError: 通信層失敗。
        """
    def fetch(self, *, refresh: bool = False) -> tuple[str, bytes]:
        """提出本文書 ZIP から代表 XBRL を取得する。

        Args:
            refresh: `True` の場合はキャッシュを破棄して再取得する。

        Returns:
            `(xbrl_path, xbrl_bytes)` のタプル。

        Raises:
            EdinetAPIError: 当該書類に XBRL が無い場合。
            EdinetError: 通信層失敗。
            EdinetAPIError: API レイヤー失敗。
            EdinetParseError: ZIP 解析失敗、primary 不在、または入力不正の正規化。
        """
    async def afetch(self, *, refresh: bool = False) -> tuple[str, bytes]:
        """提出本文書 ZIP から代表 XBRL を非同期で取得する。

        Args:
            refresh: `True` の場合はキャッシュを破棄して再取得する。

        Returns:
            `(xbrl_path, xbrl_bytes)` のタプル。

        Raises:
            EdinetAPIError: 当該書類に XBRL が無い場合。
            EdinetError: 通信層失敗。
            EdinetAPIError: API レイヤー失敗。
            EdinetParseError: ZIP 解析失敗、primary 不在、または入力不正の正規化。
        """
    @computed_field
    @property
    def ticker(self) -> str | None:
        """証券コード4桁。

        sec_code は5桁（末尾チェックディジット付き）で返る。
        先頭4桁を切り出して一般的な「証券コード」として返す。
        sec_code が None または短すぎる場合は None。
        """
    @computed_field
    @property
    def doc_type_label_ja(self) -> str:
        """書類種別の日本語表示ラベル（常に str を返す）。

        doc_type が None（未知コードまたはコードなし）の場合は
        doc_type_code にフォールバックするが、それも None なら空文字を返す。
        UI やログで doc_type の Optional チェックを毎回書かずに済む。
        """
    def xbrl(self, *, taxonomy_path: str | None = None) -> Statements:
        '''XBRL を解析し財務諸表コンテナを返す。

        ZIP ダウンロード → XBRL パース → Context 構造化 → ラベル解決 →
        LineItem 生成 → Statement 組み立てのフルパイプラインを実行する。

        Args:
            taxonomy_path: EDINET タクソノミのルートパス
                （例: ``"/path/to/ALL_20251101"``）。
                省略時は ``configure(taxonomy_path=...)`` で設定された値を使用する。

        Returns:
            Statements コンテナ。``income_statement()`` / ``balance_sheet()`` /
            ``cash_flow_statement()`` でアクセスする。

        Raises:
            EdinetAPIError: 当該書類に XBRL が無い場合。
            EdinetConfigError: taxonomy_path が未設定の場合。
            EdinetParseError: XBRL パースに失敗した場合。
            EdinetError: 通信層の失敗。

        Note:
            v0.1.0 は **J-GAAP の一般事業会社** のみ対応。IFRS / US-GAAP 企業の
            XBRL を渡した場合、科目がマッチせず空または不完全な Statement が返り、
            ``UserWarning`` を発行する。スレッドセーフではない。
        '''
    async def axbrl(self, *, taxonomy_path: str | None = None) -> Statements:
        """XBRL を非同期で解析し財務諸表コンテナを返す。

        ``xbrl()`` の非同期版。ネットワーク I/O（ZIP ダウンロード）のみ
        非同期で、パース処理は同期的に実行する。

        Args:
            taxonomy_path: EDINET タクソノミのルートパス。
                省略時は ``configure(taxonomy_path=...)`` で設定された値を使用する。

        Returns:
            Statements コンテナ。

        Raises:
            EdinetAPIError: 当該書類に XBRL が無い場合。
            EdinetConfigError: taxonomy_path が未設定の場合。
            EdinetParseError: XBRL パースに失敗した場合。
            EdinetError: 通信層の失敗。

        Note:
            v0.1.0 は **J-GAAP の一般事業会社** のみ対応。IFRS / US-GAAP 企業の
            XBRL を渡した場合、科目がマッチせず空または不完全な Statement が返り、
            ``UserWarning`` を発行する。スレッドセーフではない。
        """
    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Filing:
        """EDINET API の書類一覧レスポンス（1件分の dict）から Filing を生成する。

        Args:
            data: get_documents() の results 配列の1要素。

        Returns:
            Filing オブジェクト。

        Raises:
            KeyError: 必須フィールド（docID, seqNumber, submitDateTime）が欠落。
            ValueError: 日時文字列のフォーマットが不正。
        """
    @classmethod
    def from_api_list(cls, api_response: dict[str, Any]) -> list[Filing]:
        """get_documents() の戻り値全体から Filing リストを生成する。

        各要素の変換中に例外が発生した場合、何件目のどの書類で
        壊れたかを含む ValueError にラップして raise する。

        Args:
            api_response: get_documents() の戻り値（metadata + results を含む dict）。
                          引数名で「これは API のレスポンスそのもの」であることを明示。

        Returns:
            Filing オブジェクトのリスト。

        Raises:
            ValueError: 個別の Filing 変換に失敗した場合（元の例外を chain）。
        """

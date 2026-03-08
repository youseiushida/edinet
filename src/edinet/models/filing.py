"""EDINET 提出書類 (Filing) の Pydantic モデル。

EDINET API 仕様書 §3-1-2-2 の全29フィールドを保持する。
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, PrivateAttr, computed_field

from edinet.models.doc_types import DocType
from edinet.models.ordinance_code import OrdinanceCode

if TYPE_CHECKING:
    from edinet.models.company import Company
    from edinet.models.form_code import FormCodeEntry
    from edinet.financial.statements import Statements

# EDINET コードパターン（_select_filer_xsd 用）
_EDINET_CODE_RE = re.compile(r"_E\d{5}", re.IGNORECASE)

# --- ヘルパー関数（モジュールプライベート） ---

def _parse_date(value: str | None) -> date | None:
    """EDINET API の日付文字列 'YYYY-MM-DD' を date に変換。

    None、空文字、空白のみの場合は None を返す。
    """
    if not value or not value.strip():
        return None
    return date.fromisoformat(value)

def _parse_datetime(value: str, *, field_name: str = "") -> datetime:
    """EDINET API の日時文字列 'YYYY-MM-DD HH:MM' を datetime に変換。

    Note:
        EDINET API は日本時間（JST, UTC+9）で日時を返すが、タイムゾーン情報は
        付与されない。本ライブラリでは naive datetime として保持する。
        期間比較や並び替えを行う場合は、全ての datetime が JST である
        前提で扱うこと。aware datetime への移行は v0.2.0 以降で検討。

    Raises:
        ValueError: フォーマット不正。field_name が指定されていれば
                    エラーメッセージにフィールド名と生文字列を含める。
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as e:
        label = f" (field={field_name})" if field_name else ""
        msg = f"Invalid datetime format{label}: '{value}' (expected 'YYYY-MM-DD HH:MM')"
        raise ValueError(msg) from e
    
def _parse_datetime_optional(value: str | None, *, field_name: str = "") -> datetime | None:
    """EDINET API の日時文字列を datetime に変換。None/空なら None。"""
    if not value or not value.strip():
        return None
    return _parse_datetime(value, field_name=field_name)

def _parse_flag(value: str | None) -> bool:
    """EDINET API のフラグ '0'/'1' を bool に変換。"""
    return value == "1"

def _select_filer_xsd(candidates: list[str]) -> str | None:
    """複数の XSD 候補から提出者 XSD を決定的に選択する。

    EDINET コード（``_E\\d{5}``）を含むファイルを優先する。
    該当がなければアルファベット順で最初のファイルを返す。

    Args:
        candidates: PublicDoc 配下の非 audit XSD パスのリスト。

    Returns:
        選択されたパス。候補がない場合は None。
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    filer_matches = [c for c in candidates if _EDINET_CODE_RE.search(c)]
    if filer_matches:
        return sorted(filer_matches)[0]
    return sorted(candidates)[0]


def _extract_filer_taxonomy_files(zip_bytes: bytes | None) -> dict[str, bytes]:
    """ZIP 内から提出者別タクソノミファイルを抽出する。

    PublicDoc 配下の ``_lab.xml``（日本語ラベル）、``_lab-en.xml``（英語ラベル）、
    ``_cal.xml``（計算リンク）、``_def.xml``（定義リンク）、
    ``.xsd``（スキーマ、監査報告書を除く）を探索して返す。

    XSD が複数存在する場合は EDINET コードを含むファイルを優先し、
    それでも複数ある場合はアルファベット順で先頭のファイルを選択する。
    ラベルファイルは選択された XSD のベース名から導出し、XSD と同じ
    タクソノミに属するラベルを確実に取得する。

    ZIP は一度だけオープンし、必要なメンバーを一括で読み出す。

    Args:
        zip_bytes: ZIP のバイト列。None の場合は空辞書を返す。

    Returns:
        キーが ``"lab"`` / ``"lab_en"`` / ``"xsd"`` / ``"cal"`` / ``"def"``、値が bytes の辞書。
        対応するファイルが存在しない場合はキーが含まれない。
    """
    if zip_bytes is None:
        return {}

    import logging
    from io import BytesIO
    from zipfile import ZipFile

    logger = logging.getLogger(__name__)

    with ZipFile(BytesIO(zip_bytes)) as zf:
        members = [info.filename for info in zf.infolist() if not info.is_dir()]
        member_set = set(members)
        xsd_candidates: list[str] = []
        lab_fallbacks: list[str] = []
        lab_en_fallbacks: list[str] = []

        for name in members:
            lower = name.lower()
            if "publicdoc/" not in lower.replace("\\", "/"):
                continue
            if lower.endswith("_lab.xml") and "_lab-en" not in lower:
                lab_fallbacks.append(name)
            elif lower.endswith("_lab-en.xml"):
                lab_en_fallbacks.append(name)
            elif lower.endswith(".xsd") and "audit" not in lower:
                xsd_candidates.append(name)

        result: dict[str, bytes] = {}

        # 1. XSD を決定的に選択
        selected_xsd = _select_filer_xsd(xsd_candidates)
        if selected_xsd is not None:
            result["xsd"] = zf.read(selected_xsd)

        if len(xsd_candidates) > 1:
            logger.debug(
                "複数の XSD を検出: %s → %s を選択", xsd_candidates, selected_xsd,
            )

        # 2. ラベル・リンクベースファイルを XSD のベース名から導出
        if selected_xsd is not None:
            xsd_stem = selected_xsd[:selected_xsd.lower().rfind(".xsd")]
            derived_lab = xsd_stem + "_lab.xml"
            derived_lab_en = xsd_stem + "_lab-en.xml"
            derived_cal = xsd_stem + "_cal.xml"
            derived_def = xsd_stem + "_def.xml"

            if derived_lab in member_set:
                result["lab"] = zf.read(derived_lab)
            if derived_lab_en in member_set:
                result["lab_en"] = zf.read(derived_lab_en)
            if derived_cal in member_set:
                result["cal"] = zf.read(derived_cal)
            if derived_def in member_set:
                result["def"] = zf.read(derived_def)

        # 3. XSD から導出できなかった場合はフォールバック
        if "lab" not in result and lab_fallbacks:
            result["lab"] = zf.read(sorted(lab_fallbacks)[0])
        if "lab_en" not in result and lab_en_fallbacks:
            result["lab_en"] = zf.read(sorted(lab_en_fallbacks)[0])

    logger.debug("filer taxonomy files found: %s", list(result.keys()))
    return result


class Filing(BaseModel):
    """EDINET に提出された書類1件を表すモデル。

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
        'S100XXXX'
        >>> f.doc_type
        DocType.ANNUAL_SECURITIES_REPORT
        >>> f.filing_date
        datetime.date(2026, 2, 7)
    """

    model_config = ConfigDict(frozen=True)

    # --- 識別子 ---
    seq_number: int
    doc_id: str

    # --- 書類種別 ---
    doc_type_code: str | None
    ordinance_code: str | None
    form_code: str | None

    # --- 提出者情報（Day 6 で Company にネストする候補） ---
    edinet_code: str | None
    sec_code: str | None
    jcn: str | None
    filer_name: str | None
    fund_code: str | None

    # --- 日付・期間 ---
    submit_date_time: datetime
    period_start: date | None
    period_end: date | None

    # --- 書類概要 ---
    doc_description: str | None

    # --- 関連書類・関連コード ---
    issuer_edinet_code: str | None
    subject_edinet_code: str | None
    subsidiary_edinet_code: str | None
    current_report_reason: str | None
    parent_doc_id: str | None
    ope_date_time: datetime | None

    # --- ステータス（Day 4 では文字列のまま） ---
    withdrawal_status: str
    doc_info_edit_status: str
    disclosure_status: str

    # --- コンテンツフラグ ---
    has_xbrl: bool
    has_pdf: bool
    has_attachment: bool
    has_english: bool
    has_csv: bool

    # --- 法定・任意 ---
    legal_status: str

    # --- Day 6: fetch キャッシュ ---
    _zip_cache: bytes | None = PrivateAttr(default=None)
    _xbrl_cache: tuple[str, bytes] | None = PrivateAttr(default=None)
    _pdf_cache: bytes | None = PrivateAttr(default=None)

    # --- 計算フィールド ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def doc_type(self) -> DocType | None:
        """doc_type_code に対応する DocType Enum。

        未知のコードの場合は None（DocType.from_code() が warning を出す）。
        コード自体が None の場合も None。
        dict lookup（O(1)）なのでキャッシュ不要。
        """
        if self.doc_type_code is None:
            return None
        return DocType.from_code(self.doc_type_code)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def filing_date(self) -> date:
        """提出日（submit_date_time の日付部分）。

        PLAN.md §4 の Filing モデル定義で filing_date: date と定義。
        submit_date_time から導出することで二重管理を避ける。
        """
        return self.submit_date_time.date()

    @property
    def ordinance(self) -> OrdinanceCode | None:
        """府令コード Enum。"""
        if self.ordinance_code is None:
            return None
        return OrdinanceCode.from_code(self.ordinance_code)

    @property
    def form(self) -> FormCodeEntry | None:
        """様式コード情報。"""
        if self.ordinance_code is None or self.form_code is None:
            return None
        from edinet.models.form_code import get_form_code

        return get_form_code(self.ordinance_code, self.form_code)

    @property
    def company(self) -> Company | None:
        """提出者 Company を返す。"""
        from edinet.models.company import Company
        return Company.from_filing(self)

    def clear_fetch_cache(self) -> None:
        """`fetch()` / `fetch_pdf()` のキャッシュを破棄する。"""
        object.__setattr__(self, "_zip_cache", None)
        object.__setattr__(self, "_xbrl_cache", None)
        object.__setattr__(self, "_pdf_cache", None)

    def _get_from_disk_cache(self) -> bytes | None:
        """ディスクキャッシュから ZIP を読み込む。

        Returns:
            キャッシュヒット時は bytes。キャッシュ無効またはミス時は ``None``。
        """
        from edinet.api.cache import _get_cache_store

        store = _get_cache_store()
        if store is None:
            return None
        return store.get(self.doc_id)

    def _save_to_disk_cache(self, data: bytes) -> None:
        """ZIP をディスクキャッシュに保存する。

        Args:
            data: 保存する ZIP バイナリ。
        """
        from edinet.api.cache import _get_cache_store

        store = _get_cache_store()
        if store is None:
            return
        store.put(self.doc_id, data)

    def _delete_disk_cache(self) -> None:
        """ディスクキャッシュの当該エントリを削除する。

        破損したキャッシュファイルによる無限ループを防止するために使用。
        ディスクキャッシュ由来の ZIP が解析に失敗した場合に呼ばれ、
        次回の ``fetch()`` でネットワークから再取得できるようにする。
        """
        from edinet.api.cache import _get_cache_store

        store = _get_cache_store()
        if store is None:
            return
        store.delete(self.doc_id)

    def _get_pdf_from_disk_cache(self) -> bytes | None:
        """ディスクキャッシュから PDF を読み込む。

        Returns:
            キャッシュヒット時は bytes。キャッシュ無効またはミス時は ``None``。
        """
        from edinet.api.cache import _get_cache_store

        store = _get_cache_store()
        if store is None:
            return None
        return store.get(self.doc_id, suffix=".pdf")

    def _save_pdf_to_disk_cache(self, data: bytes) -> None:
        """PDF をディスクキャッシュに保存する。

        Args:
            data: 保存する PDF バイナリ。
        """
        from edinet.api.cache import _get_cache_store

        store = _get_cache_store()
        if store is None:
            return
        store.put(self.doc_id, data, suffix=".pdf")

    def _delete_pdf_disk_cache(self) -> None:
        """ディスクキャッシュの PDF エントリを削除する。"""
        from edinet.api.cache import _get_cache_store

        store = _get_cache_store()
        if store is None:
            return
        store.delete(self.doc_id, suffix=".pdf")

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
        from edinet.api.download import DownloadFileType, download_document
        from edinet.exceptions import EdinetAPIError, EdinetParseError

        if not self.has_pdf:
            raise EdinetAPIError(
                0,
                f"書類に PDF が含まれていません (doc_id={self.doc_id}, pdfFlag=0)。",
            )

        if refresh:
            object.__setattr__(self, "_pdf_cache", None)
            self._delete_pdf_disk_cache()

        # Layer 1: メモリキャッシュ
        if self._pdf_cache is not None:
            return self._pdf_cache

        # Layer 2: ディスクキャッシュ
        if not refresh:
            disk_data = self._get_pdf_from_disk_cache()
            if disk_data is not None:
                object.__setattr__(self, "_pdf_cache", disk_data)
                return disk_data

        # Layer 3: ネットワーク
        try:
            pdf_bytes = download_document(
                self.doc_id,
                file_type=DownloadFileType.PDF,
            )
        except ValueError as exc:
            raise EdinetParseError(
                f"PDF のダウンロードに失敗しました "
                f"(doc_id={self.doc_id!r}): {exc}",
            ) from exc

        object.__setattr__(self, "_pdf_cache", pdf_bytes)
        self._save_pdf_to_disk_cache(pdf_bytes)
        return pdf_bytes

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
        from edinet.api.download import DownloadFileType, adownload_document
        from edinet.exceptions import EdinetAPIError, EdinetParseError

        if not self.has_pdf:
            raise EdinetAPIError(
                0,
                f"書類に PDF が含まれていません (doc_id={self.doc_id}, pdfFlag=0)。",
            )

        if refresh:
            object.__setattr__(self, "_pdf_cache", None)
            self._delete_pdf_disk_cache()

        # Layer 1: メモリキャッシュ
        if self._pdf_cache is not None:
            return self._pdf_cache

        # Layer 2: ディスクキャッシュ
        if not refresh:
            disk_data = self._get_pdf_from_disk_cache()
            if disk_data is not None:
                object.__setattr__(self, "_pdf_cache", disk_data)
                return disk_data

        # Layer 3: ネットワーク
        try:
            pdf_bytes = await adownload_document(
                self.doc_id,
                file_type=DownloadFileType.PDF,
            )
        except ValueError as exc:
            raise EdinetParseError(
                f"PDF のダウンロードに失敗しました "
                f"(doc_id={self.doc_id!r}): {exc}",
            ) from exc

        object.__setattr__(self, "_pdf_cache", pdf_bytes)
        self._save_pdf_to_disk_cache(pdf_bytes)
        return pdf_bytes

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
        from edinet.api.download import (
            DownloadFileType,
            download_document,
            extract_primary_xbrl,
        )
        from edinet.exceptions import EdinetAPIError, EdinetParseError

        if not self.has_xbrl:
            raise EdinetAPIError(
                0,
                f"書類に XBRL が含まれていません (doc_id={self.doc_id}, xbrlFlag=0)。",
            )

        if refresh:
            self.clear_fetch_cache()

        if self._xbrl_cache is not None:
            return self._xbrl_cache

        from_disk = False

        if self._zip_cache is None:
            # Layer 2: ディスクキャッシュ確認
            if not refresh:
                disk_data = self._get_from_disk_cache()
                if disk_data is not None:
                    object.__setattr__(self, "_zip_cache", disk_data)
                    from_disk = True

        if self._zip_cache is None:
            try:
                zip_bytes = download_document(
                    self.doc_id,
                    file_type=DownloadFileType.XBRL_AND_AUDIT,
                )
            except ValueError as exc:
                raise EdinetParseError(
                    f"XBRL ZIP のダウンロードに失敗しました "
                    f"(doc_id={self.doc_id!r}): {exc}",
                ) from exc
            object.__setattr__(self, "_zip_cache", zip_bytes)
            # Layer 2: ディスクに保存
            self._save_to_disk_cache(zip_bytes)

        assert self._zip_cache is not None
        try:
            result = extract_primary_xbrl(self._zip_cache)
        except ValueError as exc:
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"EDINET ZIP の解析に失敗しました (doc_id={self.doc_id})。",
            ) from exc

        if result is None:
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"ZIP 内に主要な XBRL が見つかりません (doc_id={self.doc_id})。",
            )

        object.__setattr__(self, "_xbrl_cache", result)
        return result

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
        from edinet.api.download import (
            DownloadFileType,
            adownload_document,
            extract_primary_xbrl,
        )
        from edinet.exceptions import EdinetAPIError, EdinetParseError

        if not self.has_xbrl:
            raise EdinetAPIError(
                0,
                f"書類に XBRL が含まれていません (doc_id={self.doc_id}, xbrlFlag=0)。",
            )

        if refresh:
            self.clear_fetch_cache()

        if self._xbrl_cache is not None:
            return self._xbrl_cache

        from_disk = False

        if self._zip_cache is None:
            # Layer 2: ディスクキャッシュ確認（同期 I/O で十分）
            if not refresh:
                disk_data = self._get_from_disk_cache()
                if disk_data is not None:
                    object.__setattr__(self, "_zip_cache", disk_data)
                    from_disk = True

        if self._zip_cache is None:
            try:
                zip_bytes = await adownload_document(
                    self.doc_id,
                    file_type=DownloadFileType.XBRL_AND_AUDIT,
                )
            except ValueError as exc:
                raise EdinetParseError(
                    f"XBRL ZIP のダウンロードに失敗しました "
                    f"(doc_id={self.doc_id!r}): {exc}",
                ) from exc
            object.__setattr__(self, "_zip_cache", zip_bytes)
            # Layer 2: ディスクに保存（同期 I/O で十分）
            self._save_to_disk_cache(zip_bytes)

        assert self._zip_cache is not None
        try:
            result = extract_primary_xbrl(self._zip_cache)
        except ValueError as exc:
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"EDINET ZIP の解析に失敗しました (doc_id={self.doc_id})。",
            ) from exc

        if result is None:
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"ZIP 内に主要な XBRL が見つかりません (doc_id={self.doc_id})。",
            )

        object.__setattr__(self, "_xbrl_cache", result)
        return result

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ticker(self) -> str | None:
        """証券コード4桁。

        sec_code は5桁（末尾チェックディジット付き）で返る。
        先頭4桁を切り出して一般的な「証券コード」として返す。
        sec_code が None または短すぎる場合は None。
        """
        if self.sec_code and len(self.sec_code) >= 4:
            return self.sec_code[:4]
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def doc_type_label_ja(self) -> str:
        """書類種別の日本語表示ラベル（常に str を返す）。

        doc_type が None（未知コードまたはコードなし）の場合は
        doc_type_code にフォールバックするが、それも None なら空文字を返す。
        UI やログで doc_type の Optional チェックを毎回書かずに済む。
        """
        dt = self.doc_type
        if dt:
            return dt.name_ja
        return self.doc_type_code or ""
    
    # --- XBRL パイプライン ---

    def _resolve_taxonomy_path(self, taxonomy_path: str | None) -> str:
        """taxonomy_path を解決する。引数 > configure() の優先順位。

        Args:
            taxonomy_path: 明示指定されたパス。None の場合は configure() から取得。

        Returns:
            解決されたタクソノミパス。

        Raises:
            EdinetConfigError: どちらも未設定の場合。
        """
        from edinet._config import get_config
        from edinet.exceptions import EdinetConfigError

        resolved = taxonomy_path or get_config().taxonomy_path
        if resolved is None:
            raise EdinetConfigError(
                "taxonomy_path が未設定です。"
                "xbrl(taxonomy_path=...) で直接指定するか、"
                "configure(taxonomy_path=...) でグローバルに設定してください。"
            )
        return resolved

    def _build_statements(
        self,
        taxonomy_path: str,
        xbrl_path: str,
        xbrl_bytes: bytes,
    ) -> Statements:
        """ZIP キャッシュからパイプラインを実行する（同期）。

        xbrl() / axbrl() の共通パイプライン。I/O 完了後の
        ステップ 3〜8 を担当する。

        Args:
            taxonomy_path: 解決済みタクソノミパス。
            xbrl_path: XBRL ファイルのパス（トレース用）。
            xbrl_bytes: XBRL ファイルのバイト列。

        Returns:
            Statements コンテナ。

        Raises:
            EdinetParseError: パイプラインの各ステップで失敗した場合。
        """
        import logging

        from edinet.exceptions import EdinetError, EdinetParseError
        from edinet.xbrl import (
            build_line_items,
            build_statements,
            parse_xbrl_facts,
            structure_contexts,
        )
        from edinet.xbrl.taxonomy import get_taxonomy_resolver

        logger = logging.getLogger(__name__)

        try:
            # 3. 提出者タクソノミファイルの抽出
            filer_files = _extract_filer_taxonomy_files(self._zip_cache)

            # 4. XBRL パース
            parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
            logger.debug(
                "step 4: parsed %d facts, %d contexts",
                len(parsed.facts), len(parsed.contexts),
            )

            # 4b. J-GAAP 名前空間チェック（IFRS/US-GAAP 検知）
            namespaces = {
                f.concept_qname.split("}")[0]
                for f in parsed.facts
                if "}" in f.concept_qname
            }
            if not any("jppfs" in ns for ns in namespaces):
                import warnings

                from edinet.exceptions import EdinetWarning

                warnings.warn(
                    f"Filing {self.doc_id}: jppfs_cor 名前空間の Fact がありません。"
                    "IFRS / US-GAAP の Filing は v0.1.0 では未対応です。",
                    EdinetWarning,
                    stacklevel=3,
                )

            # 5. Context 構造化
            ctx_map = structure_contexts(parsed.contexts)
            logger.debug("step 5: structured %d contexts", len(ctx_map))

            # 6. ラベル解決
            resolver = get_taxonomy_resolver(taxonomy_path)
            resolver.load_filer_labels(
                lab_xml_bytes=filer_files.get("lab"),
                lab_en_xml_bytes=filer_files.get("lab_en"),
                xsd_bytes=filer_files.get("xsd"),
            )

            # 7. LineItem 生成
            items = build_line_items(parsed.facts, ctx_map, resolver)
            logger.debug("step 7: built %d line items", len(items))

            # 7b. リンクベースパース（definition_mapper / calc_mapper 用）
            from edinet.xbrl.linkbase import (
                parse_calculation_linkbase,
                parse_definition_linkbase,
            )

            cal_lb = None
            cal_bytes = filer_files.get("cal")
            if cal_bytes is not None:
                cal_lb = parse_calculation_linkbase(cal_bytes)

            def_trees = None
            def_bytes = filer_files.get("def")
            if def_bytes is not None:
                def_trees = parse_definition_linkbase(def_bytes)

            logger.debug(
                "step 7b: linkbases cal=%s def=%s",
                cal_lb is not None,
                def_trees is not None,
            )

            # 8. Statement 組み立て
            from pathlib import Path as _Path

            from edinet.xbrl.dei import extract_dei, resolve_industry_code

            dei = extract_dei(parsed.facts)
            industry_code = resolve_industry_code(dei)

            stmts = build_statements(
                items,
                facts=parsed.facts,
                contexts=ctx_map,
                taxonomy_root=_Path(taxonomy_path),
                industry_code=industry_code,
                resolver=resolver,
                calculation_linkbase=cal_lb,
                definition_linkbase=def_trees,
            )
        except EdinetError:
            raise
        except Exception as exc:
            raise EdinetParseError(
                f"Filing {self.doc_id}: XBRL パイプラインで予期しないエラーが発生しました"
            ) from exc

        return stmts

    def xbrl(self, *, taxonomy_path: str | None = None) -> Statements:
        """XBRL を解析し財務諸表コンテナを返す。

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
            J-GAAP / IFRS / US-GAAP の 3 会計基準に対応。
            23 業種の ConceptSet を自動導出し、銀行・保険・証券・建設・鉄道の
            5 業種は専用科目マッピングを提供する。
            有報・四半期報告書・半期報告書など XBRL を含む全書類タイプで動作する。
            スレッドセーフではない。
        """
        from edinet.exceptions import EdinetAPIError

        if not self.has_xbrl:
            raise EdinetAPIError(
                0,
                f"書類に XBRL が含まれていません (doc_id={self.doc_id}, xbrlFlag=0)。",
            )
        resolved_taxonomy_path = self._resolve_taxonomy_path(taxonomy_path)
        xbrl_path, xbrl_bytes = self.fetch()
        return self._build_statements(resolved_taxonomy_path, xbrl_path, xbrl_bytes)

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
            J-GAAP / IFRS / US-GAAP の 3 会計基準に対応。
            23 業種の ConceptSet を自動導出し、銀行・保険・証券・建設・鉄道の
            5 業種は専用科目マッピングを提供する。
            有報・四半期報告書・半期報告書など XBRL を含む全書類タイプで動作する。
            スレッドセーフではない。
        """
        from edinet.exceptions import EdinetAPIError

        if not self.has_xbrl:
            raise EdinetAPIError(
                0,
                f"書類に XBRL が含まれていません (doc_id={self.doc_id}, xbrlFlag=0)。",
            )
        resolved_taxonomy_path = self._resolve_taxonomy_path(taxonomy_path)
        xbrl_path, xbrl_bytes = await self.afetch()
        return self._build_statements(resolved_taxonomy_path, xbrl_path, xbrl_bytes)

    # --- ファクトリメソッド ---

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
        return cls(
            # === 必須フィールド（data["key"] — 欠落は KeyError で即座に検知） ===
            seq_number=data["seqNumber"],
            doc_id=data["docID"],
            doc_type_code=data.get("docTypeCode"),
            ordinance_code=data.get("ordinanceCode"),
            form_code=data.get("formCode"),
            filer_name=data.get("filerName"),
            submit_date_time=_parse_datetime(
                data["submitDateTime"], field_name="submitDateTime",
            ),
            doc_description=data.get("docDescription"),
            # === 任意フィールド（data.get() — None で保持、デフォルト空文字は使わない） ===
            edinet_code=data.get("edinetCode"),
            sec_code=data.get("secCode"),
            jcn=data.get("JCN"),
            fund_code=data.get("fundCode"),
            # 日付・期間
            period_start=_parse_date(data.get("periodStart")),
            period_end=_parse_date(data.get("periodEnd")),
            # 関連書類
            issuer_edinet_code=data.get("issuerEdinetCode"),
            subject_edinet_code=data.get("subjectEdinetCode"),
            subsidiary_edinet_code=data.get("subsidiaryEdinetCode"),
            current_report_reason=data.get("currentReportReason"),
            parent_doc_id=data.get("parentDocID"),
            ope_date_time=_parse_datetime_optional(
                data.get("opeDateTime"), field_name="opeDateTime",
            ),
            # ステータス
            # API 仕様上は常に存在する想定だが、防御的にデフォルト "0" を採用する。
            # Note: これにより API 仕様変更（フィールド削除）時の検知が遅れる可能性がある。
            # 必須化を検討する場合は KeyAccess に変更すること。
            withdrawal_status=data.get("withdrawalStatus", "0"),
            doc_info_edit_status=data.get("docInfoEditStatus", "0"),
            disclosure_status=data.get("disclosureStatus", "0"),
            # コンテンツフラグ
            has_xbrl=_parse_flag(data.get("xbrlFlag")),
            has_pdf=_parse_flag(data.get("pdfFlag")),
            has_attachment=_parse_flag(data.get("attachDocFlag")),
            has_english=_parse_flag(data.get("englishDocFlag")),
            has_csv=_parse_flag(data.get("csvFlag")),
            # 法定・任意
            legal_status=data.get("legalStatus", "0"),
        )

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
        results = api_response.get("results", [])
        filings: list[Filing] = []
        for i, doc in enumerate(results):
            try:
                filings.append(cls.from_api_response(doc))
            except (KeyError, TypeError, ValueError) as e:
                doc_id = doc.get("docID", "?") if isinstance(doc, dict) else "?"
                doc_type = doc.get("docTypeCode", "?") if isinstance(doc, dict) else "?"
                raise ValueError(
                    f"書類の変換に失敗しました (index={i}, "
                    f"docID={doc_id}, docTypeCode={doc_type}): "
                    f"keys={sorted(doc.keys()) if isinstance(doc, dict) else type(doc).__name__}"
                ) from e
        return filings

    # --- 表示 ---

    def __str__(self) -> str:
        """コンソールでの簡潔な表示。"""
        filer_name = self.filer_name or "(不明)"
        return f"Filing({self.doc_id} | {filer_name} | {self.doc_type_label_ja})"

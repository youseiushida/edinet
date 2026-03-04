"""EDINET 書類取得 API (download API) のラッパー。"""
from __future__ import annotations

from enum import Enum
from io import BytesIO
import logging
import re
from zlib import error as ZlibError
from zipfile import BadZipFile, ZipFile, ZipInfo

import httpx

from edinet import _http
from edinet.api._errors import raise_for_api_error_response
from edinet.exceptions import EdinetAPIError

logger = logging.getLogger(__name__)

ZIP_CONTENT_TYPES: tuple[str, ...] = (
    "application/octet-stream",
    "application/zip",
    "application/x-zip-compressed",
)

MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_MEMBER_COUNT = 2000
MAX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_XBRL_SCAN_BYTES_TOTAL = 4 * 1024 * 1024


class DownloadFileType(str, Enum):
    """書類取得 API の必要書類 type パラメータ。"""

    XBRL_AND_AUDIT = "1"
    PDF = "2"
    ATTACHMENT = "3"
    ENGLISH = "4"
    CSV = "5"

    @property
    def expected_content_types(self) -> tuple[str, ...]:
        """この書類種別で受け入れる Content-Type 一覧を返す。

        Returns:
            tuple[str, ...]: 期待される Content-Type。
        """
        if self is DownloadFileType.PDF:
            return ("application/pdf",)
        return ZIP_CONTENT_TYPES

    @property
    def is_zip(self) -> bool:
        """ZIP 形式で取得する種別かどうかを返す。

        Returns:
            bool: PDF 以外なら `True`。
        """
        return self is not DownloadFileType.PDF


_DOC_ID_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


def _validate_and_normalize_download_params(
    doc_id: str,
    file_type: DownloadFileType | str,
) -> tuple[str, DownloadFileType]:
    """入力バリデーション（sync/async 共通）。

    Args:
        doc_id: 書類 ID。
        file_type: ファイル種別。

    Returns:
        正規化済みの (doc_id, file_type) タプル。

    Raises:
        ValueError: 入力が不正な場合。
    """
    if not isinstance(doc_id, str):
        raise ValueError("doc_id must be str")

    normalized_doc_id = doc_id.strip()
    if not normalized_doc_id:
        raise ValueError("doc_id must not be empty")
    if not _DOC_ID_PATTERN.fullmatch(normalized_doc_id):
        raise ValueError("doc_id must be alphanumeric only")

    try:
        normalized_file_type = DownloadFileType(file_type)
    except ValueError as exc:
        raise ValueError(f"Invalid file_type: {file_type!r}") from exc

    return normalized_doc_id, normalized_file_type


def _validate_download_response(
    response: httpx.Response,
    normalized_file_type: DownloadFileType,
) -> bytes:
    """レスポンス検証（sync/async 共通）。

    Args:
        response: HTTP レスポンス。
        normalized_file_type: 正規化済みのファイル種別。

    Returns:
        レスポンスボディの bytes。

    Raises:
        EdinetAPIError: レスポンスが不正な場合。
    """
    content_type = _normalize_content_type(response.headers.get("Content-Type"))

    # _http は transport/retry と HTTP 非200 を処理し、
    # ここは HTTP 200 内の EDINET JSON エラーを処理する。
    if content_type == "application/json":
        raise_for_api_error_response(response, default_status_code=response.status_code)

    if normalized_file_type.is_zip and content_type == "application/pdf":
        raise EdinetAPIError(
            response.status_code,
            "Received PDF for ZIP-type request. The document may be non-disclosed "
            "or XBRL/CSV download may be unavailable.",
        )

    if normalized_file_type.is_zip and content_type in {
        "application/zip",
        "application/x-zip-compressed",
    }:
        logger.debug(
            "Accepted non-spec ZIP Content-Type '%s' for type=%s",
            content_type,
            normalized_file_type.value,
        )

    if content_type not in normalized_file_type.expected_content_types:
        raise EdinetAPIError(
            response.status_code,
            f"Unexpected Content-Type '{content_type}' for type={normalized_file_type.value}. "
            f"Expected one of {normalized_file_type.expected_content_types}.",
        )

    body = response.content
    if normalized_file_type.is_zip and len(body) > MAX_ZIP_BYTES:
        raise EdinetAPIError(
            response.status_code,
            f"ZIP payload too large: {len(body)} bytes",
        )
    return body


def download_document(
    doc_id: str,
    *,
    file_type: DownloadFileType | str = DownloadFileType.XBRL_AND_AUDIT,
) -> bytes:
    """書類取得 API でバイナリを取得する。

    Args:
        doc_id: 書類管理番号（英数字のみ）。
        file_type: ファイル種別。``DownloadFileType`` または文字列 ``"1"``〜``"5"``。

    Returns:
        レスポンスボディの bytes。

    Raises:
        ValueError: ``doc_id`` や ``file_type`` が不正。
        EdinetAPIError: API エラーまたは Content-Type 不正。
    """
    normalized_doc_id, normalized_file_type = _validate_and_normalize_download_params(
        doc_id, file_type,
    )
    response = _http.get(
        f"/documents/{normalized_doc_id}",
        params={"type": normalized_file_type.value},
    )
    return _validate_download_response(response, normalized_file_type)


async def adownload_document(
    doc_id: str,
    *,
    file_type: DownloadFileType | str = DownloadFileType.XBRL_AND_AUDIT,
) -> bytes:
    """書類取得 API で非同期にバイナリを取得する。

    Args:
        doc_id: 書類管理番号。
        file_type: ファイル種別。

    Returns:
        バイナリデータ。

    Raises:
        ValueError: doc_id や file_type が不正。
        EdinetAPIError: API エラー。
    """
    normalized_doc_id, normalized_file_type = _validate_and_normalize_download_params(
        doc_id, file_type,
    )
    response = await _http.aget(
        f"/documents/{normalized_doc_id}",
        params={"type": normalized_file_type.value},
    )
    return _validate_download_response(response, normalized_file_type)


def list_zip_members(zip_bytes: bytes) -> tuple[str, ...]:
    """ZIP 内の通常ファイル名一覧を昇順で返す。"""
    with _open_zip(zip_bytes) as zf:
        infos = _iter_file_infos(zf)
        names = [info.filename for info in infos]
    return tuple(sorted(names))


def find_primary_xbrl_path(zip_bytes: bytes) -> str | None:
    """`PublicDoc/` を含む代表 XBRL ファイルのパスを返す。"""
    with _open_zip(zip_bytes) as zf:
        infos = _iter_file_infos(zf)
        candidates = [
            info
            for info in infos
            if "/publicdoc/" in f"/{info.filename.lower()}"
            and info.filename.lower().endswith(".xbrl")
        ]

        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0].filename

        ranked: list[tuple[tuple[int, int, int, int, str], str]] = []
        scanned_total = 0
        for info in candidates:
            remaining = MAX_XBRL_SCAN_BYTES_TOTAL - scanned_total
            if remaining <= 0:
                raise ValueError("XBRL head scan budget exceeded")
            head = _read_head_bytes(zf, info.filename, limit=min(65536, remaining)).lower()
            scanned_total += len(head)

            key = (
                0 if b"jppfs_cor" in head else 1,
                0 if b"jpcrp_cor" in head else 1,
                -info.file_size,
                info.filename.count("/"),
                info.filename,
            )
            ranked.append((key, info.filename))

        ranked.sort(key=lambda item: item[0])
        return ranked[0][1]


def extract_zip_member(zip_bytes: bytes, member_name: str) -> bytes:
    """ZIP 内の指定メンバーを bytes で返す。"""
    if not isinstance(member_name, str):
        raise ValueError("member_name must be str")

    normalized_member_name = member_name.strip()
    if not normalized_member_name:
        raise ValueError("member_name must not be empty")

    with _open_zip(zip_bytes) as zf:
        _validate_zip_limits(zf)
        try:
            info = zf.getinfo(normalized_member_name)
        except KeyError as exc:
            raise ValueError(f"ZIP member not found: {normalized_member_name}") from exc

        if info.is_dir():
            raise ValueError(f"ZIP member is a directory: {normalized_member_name}")
        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError(
                f"ZIP member too large: {normalized_member_name} ({info.file_size} bytes)"
            )

        try:
            with zf.open(info, "r") as fp:
                return fp.read()
        except (BadZipFile, ZlibError, OSError, EOFError, RuntimeError) as exc:
            raise ValueError(f"Invalid ZIP member data: {normalized_member_name}") from exc


def find_ixbrl_paths(zip_bytes: bytes) -> tuple[str, ...]:
    """ZIP 内の iXBRL（Inline XBRL）ファイルパスを返す。

    ``PublicDoc/`` 配下の ``_ixbrl.htm`` で終わるファイルを検出する。
    IXDS（Inline XBRL Document Set）では1つの提出書類に複数の
    iXBRL ファイルが含まれる。

    Args:
        zip_bytes: EDINET / TDnet からダウンロードした ZIP の bytes。

    Returns:
        iXBRL ファイルのパスをソート済みタプルで返す。
        該当ファイルがない場合は空タプル。

    Raises:
        ValueError: ZIP として不正な場合。
    """
    members = list_zip_members(zip_bytes)
    paths = [
        m
        for m in members
        if m.lower().endswith("_ixbrl.htm")
        and "/publicdoc/" in f"/{m.lower()}"
    ]
    return tuple(sorted(paths))


def extract_primary_xbrl(zip_bytes: bytes) -> tuple[str, bytes] | None:
    """代表 XBRL を (path, bytes) で返す。見つからなければ None。"""
    path = find_primary_xbrl_path(zip_bytes)
    if path is None:
        return None
    return path, extract_zip_member(zip_bytes, path)


def _normalize_content_type(raw: str | None) -> str:
    """Content-Type ヘッダ値を比較しやすい形に正規化する。

    Args:
        raw: 生の Content-Type ヘッダ値。

    Returns:
        str: 小文字化し、`;` 以降のパラメータを除去した値。未設定時は空文字。
    """
    if not raw:
        return ""
    return raw.split(";", 1)[0].strip().lower()


def _open_zip(zip_bytes: bytes) -> ZipFile:
    """bytes から `ZipFile` を安全に生成する。

    Args:
        zip_bytes: ZIP バイナリ。

    Returns:
        ZipFile: 読み取り可能な ZIP オブジェクト。

    Raises:
        ValueError: 入力型が不正、サイズ超過、または ZIP が破損している場合。
    """
    if not isinstance(zip_bytes, (bytes, bytearray, memoryview)):
        raise ValueError("zip_bytes must be bytes-like")

    raw = bytes(zip_bytes)
    if len(raw) > MAX_ZIP_BYTES:
        raise ValueError(f"ZIP payload too large for helper input: {len(raw)} bytes")

    try:
        return ZipFile(BytesIO(raw))
    except (BadZipFile, ValueError) as exc:
        raise ValueError("Invalid ZIP data") from exc


def _iter_file_infos(zf: ZipFile) -> list[ZipInfo]:
    """ZIP 内の通常ファイル情報を制限チェック付きで返す。

    Args:
        zf: 検査対象の ZIP オブジェクト。

    Returns:
        list[ZipInfo]: ディレクトリを除外したファイル情報一覧。
    """
    return _validate_zip_limits(zf)


def _validate_zip_limits(zf: ZipFile) -> list[ZipInfo]:
    """ZIP 内の件数・サイズ制約を検証する。

    Args:
        zf: 検査対象の ZIP オブジェクト。

    Returns:
        list[ZipInfo]: 制約を満たす通常ファイル情報一覧。

    Raises:
        ValueError: 件数、個別サイズ、合計展開サイズのいずれかが上限を超える場合。
    """
    infos = [info for info in zf.infolist() if not info.is_dir()]

    if len(infos) > MAX_MEMBER_COUNT:
        raise ValueError(f"ZIP has too many members: {len(infos)}")

    for info in infos:
        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError(f"ZIP member too large: {info.filename} ({info.file_size} bytes)")

    total_uncompressed = sum(info.file_size for info in infos)
    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise ValueError(f"ZIP total uncompressed bytes too large: {total_uncompressed}")

    return infos


def _read_head_bytes(zf: ZipFile, member_name: str, *, limit: int) -> bytes:
    """ZIP メンバーの先頭バイト列を読み取る。

    Args:
        zf: 読み取り元の ZIP オブジェクト。
        member_name: 読み取るメンバー名。
        limit: 最大読み取りバイト数。

    Returns:
        bytes: 読み取った先頭データ。

    Raises:
        ValueError: メンバーが大きすぎる、または読み取り時に破損が検出された場合。
    """
    info = zf.getinfo(member_name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"ZIP member too large for scan: {member_name} ({info.file_size} bytes)")
    try:
        with zf.open(member_name, "r") as fp:
            return fp.read(limit)
    except (BadZipFile, ZlibError, OSError, EOFError, RuntimeError) as exc:
        raise ValueError(f"Invalid ZIP member data: {member_name}") from exc

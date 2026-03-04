from _typeshed import Incomplete
from edinet.api._errors import raise_for_api_error_response as raise_for_api_error_response
from edinet.exceptions import EdinetAPIError as EdinetAPIError
from enum import Enum

logger: Incomplete
ZIP_CONTENT_TYPES: tuple[str, ...]
MAX_ZIP_BYTES: Incomplete
MAX_MEMBER_COUNT: int
MAX_MEMBER_BYTES: Incomplete
MAX_TOTAL_UNCOMPRESSED_BYTES: Incomplete
MAX_XBRL_SCAN_BYTES_TOTAL: Incomplete

class DownloadFileType(str, Enum):
    """書類取得 API の必要書類 type パラメータ。"""
    XBRL_AND_AUDIT = '1'
    PDF = '2'
    ATTACHMENT = '3'
    ENGLISH = '4'
    CSV = '5'
    @property
    def expected_content_types(self) -> tuple[str, ...]:
        """この書類種別で受け入れる Content-Type 一覧を返す。

        Returns:
            tuple[str, ...]: 期待される Content-Type。
        """
    @property
    def is_zip(self) -> bool:
        """ZIP 形式で取得する種別かどうかを返す。

        Returns:
            bool: PDF 以外なら `True`。
        """

def download_document(doc_id: str, *, file_type: DownloadFileType | str = ...) -> bytes:
    '''書類取得 API でバイナリを取得する。

    Args:
        doc_id: 書類管理番号（英数字のみ）。
        file_type: ファイル種別。``DownloadFileType`` または文字列 ``"1"``〜``"5"``。

    Returns:
        レスポンスボディの bytes。

    Raises:
        ValueError: ``doc_id`` や ``file_type`` が不正。
        EdinetAPIError: API エラーまたは Content-Type 不正。
    '''
async def adownload_document(doc_id: str, *, file_type: DownloadFileType | str = ...) -> bytes:
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
def list_zip_members(zip_bytes: bytes) -> tuple[str, ...]:
    """ZIP 内の通常ファイル名一覧を昇順で返す。"""
def find_primary_xbrl_path(zip_bytes: bytes) -> str | None:
    """`PublicDoc/` を含む代表 XBRL ファイルのパスを返す。"""
def extract_zip_member(zip_bytes: bytes, member_name: str) -> bytes:
    """ZIP 内の指定メンバーを bytes で返す。"""
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
def extract_primary_xbrl(zip_bytes: bytes) -> tuple[str, bytes] | None:
    """代表 XBRL を (path, bytes) で返す。見つからなければ None。"""

from datetime import date as DateType
from edinet._validators import normalize_edinet_code as normalize_edinet_code
from edinet.exceptions import EdinetParseError as EdinetParseError, EdinetWarning as EdinetWarning
from edinet.models.doc_types import DocType as DocType
from edinet.models.filing import Filing as Filing
from typing import Literal

MAX_DOCUMENT_RANGE_DAYS: int

def documents(date: str | DateType | None = None, *, start: str | DateType | None = None, end: str | DateType | None = None, doc_type: DocType | str | None = None, edinet_code: str | None = None, on_invalid: Literal['skip', 'error'] = 'skip') -> list[Filing]:
    '''提出書類を `Filing` のリストで返す。

    Args:
        date: 単日指定（`YYYY-MM-DD` 文字列または `date`）。
        start: 範囲指定の開始日。
        end: 範囲指定の終了日。
        doc_type: `DocType` または `docTypeCode` 文字列。
        edinet_code: `E` + 5桁の提出者コード。
        on_invalid: 不正行（非 dict や Filing 変換失敗）の扱い。
            ``"skip"``（デフォルト）: 不正行をスキップし `EdinetWarning` を発行。
            ``"error"``: 最初の不正行で `EdinetParseError` を送出。

    Returns:
        提出書類一覧。

    Raises:
        ValueError: 入力引数が不正な場合。
        EdinetError: 通信層失敗（`get_documents()` から透過）。
        EdinetAPIError: API 業務エラー（`get_documents()` から透過）。
        EdinetParseError: API レスポンス形状異常または `Filing` 変換失敗
            （``on_invalid="error"`` 時は不正行でも送出）。

    Warns:
        EdinetWarning: ``on_invalid="skip"`` で不正行をスキップした場合。
    '''
async def adocuments(date: str | DateType | None = None, *, start: str | DateType | None = None, end: str | DateType | None = None, doc_type: DocType | str | None = None, edinet_code: str | None = None, on_invalid: Literal['skip', 'error'] = 'skip') -> list[Filing]:
    '''提出書類を `Filing` のリストで非同期に返す。

    Args:
        date: 単日指定（`YYYY-MM-DD` 文字列または `date`）。
        start: 範囲指定の開始日。
        end: 範囲指定の終了日。
        doc_type: `DocType` または `docTypeCode` 文字列。
        edinet_code: `E` + 5桁の提出者コード。
        on_invalid: 不正行（非 dict や Filing 変換失敗）の扱い。
            ``"skip"``（デフォルト）: 不正行をスキップし `EdinetWarning` を発行。
            ``"error"``: 最初の不正行で `EdinetParseError` を送出。

    Returns:
        提出書類一覧。

    Raises:
        ValueError: 入力引数が不正な場合。
        EdinetError: 通信層失敗（`aget_documents()` から透過）。
        EdinetAPIError: API 業務エラー（`aget_documents()` から透過）。
        EdinetParseError: API レスポンス形状異常または `Filing` 変換失敗
            （``on_invalid="error"`` 時は不正行でも送出）。

    Warns:
        EdinetWarning: ``on_invalid="skip"`` で不正行をスキップした場合。
    '''

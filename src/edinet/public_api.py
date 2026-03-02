"""公開 API の業務ロジック実装。"""
from __future__ import annotations

import warnings
from datetime import date as DateType, datetime as DateTimeType, timedelta
from typing import TYPE_CHECKING, Any, Literal

from edinet._validators import normalize_edinet_code
from edinet.exceptions import EdinetParseError, EdinetWarning

if TYPE_CHECKING:
    from edinet.models.doc_types import DocType
    from edinet.models.filing import Filing

MAX_DOCUMENT_RANGE_DAYS = 366


def documents(
    date: str | DateType | None = None,
    *,
    start: str | DateType | None = None,
    end: str | DateType | None = None,
    doc_type: DocType | str | None = None,
    edinet_code: str | None = None,
    on_invalid: Literal["skip", "error"] = "skip",
) -> list[Filing]:
    """提出書類を `Filing` のリストで返す。

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
    """
    if date is not None and (start is not None or end is not None):
        raise ValueError("date and start/end are mutually exclusive")
    if date is None and (start is None or end is None):
        raise ValueError("Specify either date or both start/end")

    if date is not None:
        start_date = _coerce_date(date, field_name="date")
        end_date = start_date
    else:
        assert start is not None and end is not None
        start_date = _coerce_date(start, field_name="start")
        end_date = _coerce_date(end, field_name="end")
        if start_date > end_date:
            raise ValueError("start must be <= end")

    _validate_date_span(start_date, end_date)
    doc_type_code = _normalize_doc_type(doc_type)
    normalized_edinet_code = normalize_edinet_code(edinet_code)

    from edinet.api.documents import get_documents
    from edinet.models.filing import Filing

    filings: list[Filing] = []
    for current in _iter_dates_inclusive(start_date, end_date):
        api_response = get_documents(
            current.isoformat(),
            include_details=True,
        )
        filtered_results = _prepare_response_for_filing_parse(
            api_response,
            doc_type_code=doc_type_code,
            edinet_code=normalized_edinet_code,
            on_invalid=on_invalid,
        )

        skipped: list[str] = []
        for i, row in enumerate(filtered_results):
            try:
                filings.append(Filing.from_api_response(row))
            except (KeyError, TypeError, ValueError) as exc:
                doc_id = row.get("docID", "?") if isinstance(row, dict) else "?"
                if on_invalid == "error":
                    raise EdinetParseError(
                        f"documents({current.isoformat()}): Filing変換に失敗 "
                        f"(index={i}, docID={doc_id}). "
                        f"on_invalid='skip' を指定すると不正行をスキップできます。",
                    ) from exc
                skipped.append(doc_id)

        if skipped:
            warnings.warn(
                f"documents({current.isoformat()}): "
                f"{len(skipped)}件の不正行をスキップ "
                f"(代表docID={skipped[0]})",
                EdinetWarning,
                stacklevel=2,
            )

    return filings


def _coerce_date(value: str | DateType, *, field_name: str) -> DateType:
    """日付入力を `date` へ変換する。

    Args:
        value: 入力値。
        field_name: エラーメッセージ用の項目名。

    Returns:
        変換済みの日付。

    Raises:
        ValueError: 型不正またはフォーマット不正の場合。
    """
    if isinstance(value, DateTimeType):
        raise ValueError(
            f"{field_name} must be YYYY-MM-DD date without time component",
        )
    if isinstance(value, DateType):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be YYYY-MM-DD string or date")
    try:
        return DateType.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD, got {value!r}") from exc


def _iter_dates_inclusive(start: DateType, end: DateType):
    """開始日と終了日を含む日付列を返す。

    Args:
        start: 開始日。
        end: 終了日。

    Yields:
        `start` から `end` までの日付。
    """
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _validate_date_span(start: DateType, end: DateType) -> None:
    """日付範囲の上限を検証する。

    Args:
        start: 開始日。
        end: 終了日。

    Raises:
        ValueError: 範囲が上限日数を超える場合。
    """
    days = (end - start).days + 1
    if days > MAX_DOCUMENT_RANGE_DAYS:
        raise ValueError(
            f"Date range too large: {days} days. Maximum is {MAX_DOCUMENT_RANGE_DAYS} days.",
        )


def _validate_resultset_count(api_response: dict[str, Any]) -> list[Any]:
    """`metadata.resultset.count` と `results` 件数の一致を検証する。

    Args:
        api_response: `get_documents()` が返した API レスポンス。

    Returns:
        `results` の配列。

    Raises:
        EdinetParseError: メタデータ構造が不正、または件数不一致の場合。
    """
    metadata = api_response.get("metadata")
    if not isinstance(metadata, dict):
        raise EdinetParseError("EDINET API response 'metadata' must be dict")

    resultset = metadata.get("resultset")
    if not isinstance(resultset, dict):
        raise EdinetParseError("EDINET API response 'metadata.resultset' must be dict")

    count_raw = resultset.get("count")
    try:
        declared_count = int(str(count_raw))
    except (TypeError, ValueError) as exc:
        raise EdinetParseError(
            "EDINET API response 'metadata.resultset.count' must be int-compatible",
        ) from exc

    raw_results = api_response.get("results")
    if not isinstance(raw_results, list):
        raise EdinetParseError("EDINET API response 'results' must be list")

    if declared_count != len(raw_results):
        raise EdinetParseError(
            f"EDINET API result count mismatch: metadata={declared_count}, results={len(raw_results)}",
        )
    return raw_results


def _prepare_response_for_filing_parse(
    api_response: dict[str, Any],
    *,
    doc_type_code: str | None,
    edinet_code: str | None,
    on_invalid: Literal["skip", "error"],
) -> list[dict[str, Any]]:
    """`Filing` 変換前に raw レスポンスを検証・事前フィルタする。

    非 dict 行の処理は ``on_invalid`` に従い、フィルタ有無に関係なく
    同じ契約を適用する。

    Args:
        api_response: 生の API レスポンス。
        doc_type_code: 書類種別コードのフィルタ。
        edinet_code: 提出者コードのフィルタ。
        on_invalid: 不正行の扱い（``"skip"`` または ``"error"``）。

    Returns:
        Filing 変換対象の dict 行リスト。

    Raises:
        EdinetParseError: 生レスポンスが不正な場合、または
            ``on_invalid="error"`` で非 dict 行が存在する場合。

    Warns:
        EdinetWarning: ``on_invalid="skip"`` で非 dict 行をスキップした場合。
    """
    raw_results = _validate_resultset_count(api_response)

    # 非 dict 行を分離
    dict_rows: list[dict[str, Any]] = []
    non_dict_count = 0
    for row in raw_results:
        if isinstance(row, dict):
            dict_rows.append(row)
        else:
            non_dict_count += 1

    if non_dict_count > 0:
        if on_invalid == "error":
            raise EdinetParseError(
                f"EDINET API response 'results' に非 dict 行が "
                f"{non_dict_count}件あります。"
                f"on_invalid='skip' を指定すると不正行をスキップできます。",
            )
        # stacklevel=3: _prepare_response... → documents() → caller
        warnings.warn(
            f"EDINET API response 'results' に非 dict 行が "
            f"{non_dict_count}件あります（スキップ済み）",
            EdinetWarning,
            stacklevel=3,
        )

    # doc_type / edinet_code フィルタ適用
    if doc_type_code is not None or edinet_code is not None:
        dict_rows = [
            row
            for row in dict_rows
            if (doc_type_code is None or row.get("docTypeCode") == doc_type_code)
            and (edinet_code is None or row.get("edinetCode") == edinet_code)
        ]

    return dict_rows


async def adocuments(
    date: str | DateType | None = None,
    *,
    start: str | DateType | None = None,
    end: str | DateType | None = None,
    doc_type: DocType | str | None = None,
    edinet_code: str | None = None,
    on_invalid: Literal["skip", "error"] = "skip",
) -> list[Filing]:
    """提出書類を `Filing` のリストで非同期に返す。

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
    """
    if date is not None and (start is not None or end is not None):
        raise ValueError("date and start/end are mutually exclusive")
    if date is None and (start is None or end is None):
        raise ValueError("Specify either date or both start/end")

    if date is not None:
        start_date = _coerce_date(date, field_name="date")
        end_date = start_date
    else:
        assert start is not None and end is not None
        start_date = _coerce_date(start, field_name="start")
        end_date = _coerce_date(end, field_name="end")
        if start_date > end_date:
            raise ValueError("start must be <= end")

    _validate_date_span(start_date, end_date)
    doc_type_code = _normalize_doc_type(doc_type)
    normalized_edinet_code = normalize_edinet_code(edinet_code)

    from edinet.api.documents import aget_documents
    from edinet.models.filing import Filing

    filings: list[Filing] = []
    for current in _iter_dates_inclusive(start_date, end_date):
        api_response = await aget_documents(
            current.isoformat(),
            include_details=True,
        )
        filtered_results = _prepare_response_for_filing_parse(
            api_response,
            doc_type_code=doc_type_code,
            edinet_code=normalized_edinet_code,
            on_invalid=on_invalid,
        )

        skipped: list[str] = []
        for i, row in enumerate(filtered_results):
            try:
                filings.append(Filing.from_api_response(row))
            except (KeyError, TypeError, ValueError) as exc:
                doc_id = row.get("docID", "?") if isinstance(row, dict) else "?"
                if on_invalid == "error":
                    raise EdinetParseError(
                        f"documents({current.isoformat()}): Filing変換に失敗 "
                        f"(index={i}, docID={doc_id}). "
                        f"on_invalid='skip' を指定すると不正行をスキップできます。",
                    ) from exc
                skipped.append(doc_id)

        if skipped:
            warnings.warn(
                f"documents({current.isoformat()}): "
                f"{len(skipped)}件の不正行をスキップ "
                f"(代表docID={skipped[0]})",
                EdinetWarning,
                stacklevel=2,
            )

    return filings


def _build_ja_to_doc_type() -> dict[str, DocType]:
    """日本語名称 → DocType の逆引き辞書を構築する。

    Returns:
        日本語名称をキー、DocType を値とする辞書。
    """
    from edinet.models.doc_types import DocType, _DOC_TYPE_NAMES_JA

    return {name_ja: DocType(code) for code, name_ja in _DOC_TYPE_NAMES_JA.items()}


def _normalize_doc_type(doc_type: DocType | str | None) -> str | None:
    """`doc_type` 引数を API コードへ正規化する。

    コード文字列（``"120"`` 等）、``DocType`` Enum、日本語名称
    （``"有価証券報告書"`` 等）のいずれも受け付ける。

    Args:
        doc_type: `DocType`、`docTypeCode` 文字列、日本語名称、または `None`。

    Returns:
        正規化済みの `docTypeCode`。未指定時は `None`。

    Raises:
        ValueError: 形式不正または未知コードの場合。
    """
    from edinet.models.doc_types import DocType

    if doc_type is None:
        return None
    if isinstance(doc_type, DocType):
        return doc_type.value
    if isinstance(doc_type, str):
        normalized = doc_type.strip()
        if not normalized:
            raise ValueError("doc_type must not be empty")
        # 既存: コード文字列 ("120" 等) → DocType
        try:
            return DocType(normalized).value
        except ValueError:
            pass
        # 新規: 日本語文字列 ("有価証券報告書" 等) → DocType
        ja_map = _build_ja_to_doc_type()
        matched = ja_map.get(normalized)
        if matched is not None:
            return matched.value
        raise ValueError(
            f"Unknown doc_type: {doc_type!r}. "
            "Use valid docTypeCode such as '120', DocType enum, "
            "or Japanese name such as '有価証券報告書'.",
        )
    raise ValueError("doc_type must be DocType, str, or None")

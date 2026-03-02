"""Day5 手動確認用: 書類取得 API と ZIP 展開の E2E チェック。"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import os
from typing import Any

from edinet._config import configure
from edinet.api.documents import get_documents
from edinet.api.download import (
    DownloadFileType,
    download_document,
    extract_primary_xbrl,
    list_zip_members,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "EDINET API から書類を取得し、ZIP 内メンバーと primary XBRL を確認します。"
        ),
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="EDINET API key。未指定時は環境変数 EDINET_API_KEY を使います。",
    )
    parser.add_argument(
        "--download-doc-id",
        default=None,
        help=(
            "ダウンロード対象の doc_id。未指定時は直近 --lookback-days 日の "
            "提出一覧から候補を自動選定します。"
        ),
    )
    parser.add_argument(
        "--download-type",
        default="1",
        choices=[ft.value for ft in DownloadFileType],
        help="書類取得 API の type（1..5）。既定値: 1",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=7,
        help="doc_id 自動選定時に遡る日数（既定値: 7）",
    )
    return parser.parse_args()


def _date_strings(lookback_days: int) -> list[str]:
    if lookback_days < 1:
        raise ValueError("lookback-days must be >= 1")
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(lookback_days)]


def _find_candidate_doc_id(lookback_days: int) -> tuple[str, str, int]:
    """直近日付から候補 doc_id を返す。

    Returns:
        tuple[filing_date, doc_id, candidate_count_for_day]
    """
    for filing_date in _date_strings(lookback_days):
        payload = get_documents(filing_date)
        results = payload.get("results", [])
        candidates: list[dict[str, Any]] = []
        for row in results:
            if not isinstance(row, dict):
                continue
            if row.get("xbrlFlag") != "1":
                continue
            if row.get("withdrawalStatus") != "0":
                continue
            if not row.get("docID"):
                continue
            if row.get("docTypeCode") is None:
                continue
            if row.get("ordinanceCode") is None:
                continue
            if row.get("formCode") is None:
                continue
            candidates.append(row)
        if candidates:
            return filing_date, str(candidates[0]["docID"]), len(candidates)

    raise ValueError(f"No candidate found in the last {lookback_days} days")


def _print_zip_summary(zip_bytes: bytes) -> None:
    members = list_zip_members(zip_bytes)
    print(f"zip_member_count={len(members)}")
    preview = ", ".join(members[:5]) if members else "(none)"
    print(f"zip_members_preview={preview}")

    primary = extract_primary_xbrl(zip_bytes)
    if primary is None:
        print("primary_xbrl_path=(not found)")
        return
    path, xbrl_bytes = primary
    print(f"primary_xbrl_path={path}")
    print(f"primary_xbrl_size_bytes={len(xbrl_bytes)}")


def main() -> int:
    args = _parse_args()

    api_key = args.api_key or os.environ.get("EDINET_API_KEY")
    if not api_key:
        print("ERROR: API key is missing. Set --api-key or EDINET_API_KEY.")
        return 1

    configure(api_key=api_key)
    file_type = DownloadFileType(args.download_type)

    try:
        if args.download_doc_id:
            doc_id = args.download_doc_id
            print(f"selected_doc_id={doc_id}")
        else:
            filing_date, doc_id, candidate_count = _find_candidate_doc_id(args.lookback_days)
            print(f"selected_doc_id={doc_id}")
            print(f"selected_doc_date={filing_date}")
            print(f"candidate_count_on_date={candidate_count}")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to select doc_id: {type(exc).__name__}: {exc}")
        return 1

    try:
        payload = download_document(doc_id, file_type=file_type)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: download failed: {type(exc).__name__}: {exc}")
        return 1

    print(f"download_type={file_type.value}")
    print(f"download_size_bytes={len(payload)}")

    if file_type.is_zip:
        try:
            _print_zip_summary(payload)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: zip analysis failed: {type(exc).__name__}: {exc}")
            return 1
    else:
        print("zip_member_count=(not zip type)")
        print(f"payload_head={payload[:16]!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

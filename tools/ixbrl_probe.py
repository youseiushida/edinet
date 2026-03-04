"""EDINET ZIP 内の .htm ファイルを探索するプローブスクリプト。

EDINET ZIP に iXBRL (.htm) ファイルが含まれているか確認する。
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import edinet
from edinet.api.download import adownload_document, list_zip_members


async def probe_zip(doc_id: str) -> None:
    """ZIP の中身を表示する。"""
    print(f"\n{'='*60}")
    print(f"doc_id: {doc_id}")
    print(f"{'='*60}")
    zip_bytes = await adownload_document(doc_id, file_type="1")
    members = list_zip_members(zip_bytes)
    htm_files = [m for m in members if m.lower().endswith((".htm", ".html", ".xhtml"))]
    xbrl_files = [m for m in members if m.lower().endswith(".xbrl")]

    print(f"Total members: {len(members)}")
    print(f"\n.xbrl files ({len(xbrl_files)}):")
    for f in xbrl_files:
        print(f"  {f}")
    print(f"\n.htm/.html/.xhtml files ({len(htm_files)}):")
    for f in htm_files:
        print(f"  {f}")


async def main() -> None:
    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", ""),
    )
    # 代表的な企業のdoc_idをいくつか試す（最近の有報）
    # まずは書類一覧から取得して確認
    from edinet.api.documents import aget_documents

    # 最近の日付で有報を探す
    result = await aget_documents("2025-06-26")
    filings = result.get("results", [])

    # has_xbrl=True で有報をいくつか取得
    xbrl_filings = [
        f for f in filings
        if f.get("xbrlFlag") == "1" and f.get("docTypeCode") in ("120", "130", "140")
    ]

    print(f"Found {len(xbrl_filings)} XBRL filings on 2025-06-26")
    for f in xbrl_filings[:3]:
        await probe_zip(f["docID"])


if __name__ == "__main__":
    asyncio.run(main())

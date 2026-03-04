"""未発見企業の doc_id を検索する。"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import edinet
from edinet.api.documents import aget_documents

MISSING = {
    "E04167": "JR東海",       # 3月決算
    "E03742": "大和証券グループ",  # 3月決算
    "E03714": "野村HD",       # 3月決算
    "E02274": "キヤノン",       # 12月決算
    "E05765": "SBI HD",       # 3月決算
    "E31394": "第一生命HD",    # 3月決算
}

async def main() -> None:
    edinet.configure(api_key=os.environ.get("EDINET_API_KEY", ""))

    found: dict[str, str] = {}

    # 3月決算企業は6月末に有報提出、12月決算は3月頃
    search_ranges = [
        # 2025年6月（3月期決算）
        [f"2025-06-{d:02d}" for d in range(1, 31)],
        # 2025年7月初旬
        [f"2025-07-{d:02d}" for d in range(1, 10)],
        # 2025年3月（12月期決算）
        [f"2025-03-{d:02d}" for d in range(15, 32)],
        # 2025年4月
        [f"2025-04-{d:02d}" for d in range(1, 10)],
        # 2024年のデータも試す
        [f"2024-06-{d:02d}" for d in range(20, 31)],
    ]

    for date_range in search_ranges:
        if len(found) == len(MISSING):
            break

        sem = asyncio.Semaphore(5)

        async def search_date(date_str: str) -> None:
            async with sem:
                try:
                    result = await aget_documents(date_str)
                except Exception:
                    return
                for item in result.get("results", []):
                    ec = item.get("edinetCode")
                    doc_type = item.get("docTypeCode")
                    if ec in MISSING and ec not in found and doc_type in ("120", "130"):
                        found[ec] = item["docID"]
                        print(f"  Found: {MISSING[ec]} → {item['docID']} ({date_str}, type={doc_type})")

        await asyncio.gather(*[search_date(d) for d in date_range])

    print(f"\n結果: {len(found)}/{len(MISSING)} 件")
    for ec, doc_id in found.items():
        print(f"  {MISSING[ec]} ({ec}): {doc_id}")
    for ec in MISSING:
        if ec not in found:
            print(f"  未発見: {MISSING[ec]} ({ec})")


if __name__ == "__main__":
    asyncio.run(main())

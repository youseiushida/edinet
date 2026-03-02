"""Wave 2 診断: IFRS企業の正しい doc_id を検索。

トヨタ自動車 (E02144) の有報を EDINET API document list から探す。
2025-06-20 前後で検索。
"""

from __future__ import annotations

import os

from edinet import configure, documents

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
configure(api_key=API_KEY)

# トヨタは3月決算 → 有報は6月提出
# 2025-06-19〜2025-06-25 あたりを検索
dates = ["2025-06-19", "2025-06-20", "2025-06-23", "2025-06-24", "2025-06-25"]

for date in dates:
    print(f"\n=== {date} ===")
    doc_list = documents(date)
    for doc in doc_list:
        # E02144 = トヨタ
        if doc.edinet_code == "E02144":
            print(f"  doc_id={doc.doc_id}, type={doc.doc_type_code}, desc={doc.doc_description}")

# IFRS企業として他にも探す: ソニー(E01777), 任天堂(E01onal)
# ソニー
print("\n\n=== IFRS企業検索: ソニー E01777 ===")
for date in ["2025-06-25", "2025-06-26", "2025-06-27"]:
    doc_list = documents(date)
    for doc in doc_list:
        if doc.edinet_code == "E01777":
            print(f"  {date}: doc_id={doc.doc_id}, type={doc.doc_type_code}, desc={doc.doc_description}")

# 日立 E01737
print("\n=== IFRS企業検索: 日立 E01737 ===")
for date in ["2025-06-25", "2025-06-26", "2025-06-27"]:
    doc_list = documents(date)
    for doc in doc_list:
        if doc.edinet_code == "E01737":
            print(f"  {date}: doc_id={doc.doc_id}, type={doc.doc_type_code}, desc={doc.doc_description}")

print("\n=== Done ===")

"""三菱UFJ (E00009) の有報 doc_id を検索。"""
from __future__ import annotations
import os
from edinet import configure, documents

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
configure(api_key=API_KEY)

# 三菱UFJ: 3月決算 → 6月提出
for date in ["2025-06-25", "2025-06-26", "2025-06-27"]:
    doc_list = documents(date)
    for doc in doc_list:
        if doc.edinet_code == "E00009":
            print(f"  {date}: doc_id={doc.doc_id}, type={doc.doc_type_code}, desc={doc.doc_description}")

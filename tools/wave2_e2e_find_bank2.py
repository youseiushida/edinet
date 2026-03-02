"""銀行業の有報 (doc_type 120) を検索。"""
from __future__ import annotations
import os
from edinet import configure, documents

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
configure(api_key=API_KEY)

# doc_type 120 = 有価証券報告書
# 三菱UFJ (E00009), みずほ (E00024), 三井住友 (E00040) をチェック
targets = {"E00009", "E00024", "E00040"}

for date in ["2025-06-25", "2025-06-26", "2025-06-27", "2025-06-30", "2025-07-01"]:
    doc_list = documents(date)
    for doc in doc_list:
        if doc.edinet_code in targets:
            print(f"  {date}: {doc.edinet_code} doc_id={doc.doc_id}, type={doc.doc_type_code}, desc={doc.doc_description}")

# ない場合は2025年夏に提出されたJ-GAAP銀行を探す
# 地銀など → 例えば横浜銀行(E04807) の親会社コンコルディア(E31881)
more_targets = {"E31881", "E04807", "E03527", "E03539"}
print("\n=== 地銀等 ===")
for date in ["2025-06-25", "2025-06-26", "2025-06-27"]:
    doc_list = documents(date)
    for doc in doc_list:
        if doc.edinet_code in more_targets:
            print(f"  {date}: {doc.edinet_code} doc_id={doc.doc_id}, type={doc.doc_type_code}, desc={doc.doc_description}")

# 銀行業有報を探す: description に「銀行」を含む doc_type 120
print("\n=== 銀行業 doc_type 120 ===")
for date in ["2025-06-25", "2025-06-26", "2025-06-27"]:
    doc_list = documents(date)
    for doc in doc_list:
        if doc.doc_type_code == "120" and "銀行" in (doc.doc_description or ""):
            print(f"  {date}: {doc.edinet_code} doc_id={doc.doc_id}, desc={doc.doc_description}")

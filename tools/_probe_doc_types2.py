"""追加調査: 2016-2022 の確実な営業日で対象書類種別の有無を調べる。

前回のサンプリングでは祝日に当たってtotal=0の日が多かった。
今回は各年の確実な営業日（火曜日〜木曜日を狙う）でサンプリング。
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

TARGET_DOC_TYPES = {
    "180": "臨時報告書",
    "190": "訂正臨時報告書",
    "350": "大量保有報告書",
    "360": "訂正大量保有報告書",
    "030": "有価証券届出書",
    "220": "自己株券買付状況報告書",
    "240": "公開買付届出書",
}

# 確実な営業日を狙う (火〜木で祝日でない日)
# 各半年の代表日を手動選定
sample_dates = [
    # 2016
    date(2016, 4, 5),   # 火
    date(2016, 6, 14),  # 火
    date(2016, 9, 13),  # 火
    date(2016, 11, 15), # 火
    # 2017
    date(2017, 3, 14),  # 火
    date(2017, 6, 13),  # 火
    date(2017, 9, 12),  # 火
    date(2017, 12, 12), # 火
    # 2018
    date(2018, 3, 13),  # 火
    date(2018, 6, 12),  # 火
    date(2018, 9, 11),  # 火
    date(2018, 12, 11), # 火
    # 2019
    date(2019, 3, 12),  # 火
    date(2019, 6, 11),  # 火
    date(2019, 9, 10),  # 火
    date(2019, 12, 10), # 火
    # 2020
    date(2020, 3, 10),  # 火
    date(2020, 6, 9),   # 火
    date(2020, 9, 8),   # 火
    date(2020, 12, 8),  # 火
    # 2021
    date(2021, 3, 9),   # 火
    date(2021, 6, 8),   # 火
    date(2021, 9, 7),   # 火
    date(2021, 12, 7),  # 火
    # 2022
    date(2022, 3, 8),   # 火
    date(2022, 6, 7),   # 火
    date(2022, 9, 6),   # 火
    date(2022, 12, 6),  # 火
    # 2023
    date(2023, 3, 7),   # 火
    date(2023, 6, 6),   # 火
    date(2023, 9, 5),   # 火
    date(2023, 12, 5),  # 火
    # 2024
    date(2024, 3, 5),   # 火
    date(2024, 6, 4),   # 火
    date(2024, 9, 3),   # 火
    date(2024, 12, 3),  # 火
    # 2025
    date(2025, 3, 4),   # 火
    date(2025, 6, 3),   # 火
    date(2025, 9, 2),   # 火
    date(2025, 12, 2),  # 火
    # 2026
    date(2026, 3, 3),   # 火
]

lines: list[str] = []
results: dict[str, dict[str, int]] = {code: {} for code in TARGET_DOC_TYPES}

for i, d in enumerate(sample_dates):
    ds = d.isoformat()
    try:
        filings = edinet.documents(ds)
        counts: dict[str, int] = {}
        for f in filings:
            dt = f.doc_type_code
            if dt in TARGET_DOC_TYPES:
                counts[dt] = counts.get(dt, 0) + 1

        parts = [f"{ds} ({d.strftime('%a')}): total={len(filings):4d}"]
        for code in TARGET_DOC_TYPES:
            c = counts.get(code, 0)
            results[code][ds] = c
            if c > 0:
                parts.append(f"{code}={c}")
        line = "  ".join(parts)
    except Exception as e:
        line = f"{ds}: ERROR ({type(e).__name__}: {e})"

    print(f"[{i+1}/{len(sample_dates)}] {line}")
    lines.append(line)
    time.sleep(0.5)

# サマリー
print("\n" + "=" * 60)
print("サマリー: 各書類種別の最古検出日")
print("=" * 60)
summary_lines: list[str] = []
for code, label in TARGET_DOC_TYPES.items():
    found = {d: c for d, c in results[code].items() if c > 0}
    if found:
        earliest = min(found.keys())
        latest = max(found.keys())
        total = sum(found.values())
        hit_days = len(found)
        s = f"  [{code}] {label}: 最古={earliest}, 最新={latest}, 検出日数={hit_days}/{len(sample_dates)}, 合計={total}件"
    else:
        s = f"  [{code}] {label}: データなし"
    print(s)
    summary_lines.append(s)

out = Path(__file__).resolve().parent / "_probe_doc_types2_result.txt"
out.write_text(
    "\n".join(lines) + "\n\n=== サマリー ===\n" + "\n".join(summary_lines) + "\n",
    encoding="utf-8",
)
print(f"\n結果を {out} に書き出しました")

"""各書類種別の EDINET API データ存在期間を調査する。

対象:
  180: 臨時報告書
  190: 訂正臨時報告書
  350: 大量保有報告書
  360: 訂正大量保有報告書
  030: 有価証券届出書
  220: 自己株券買付状況報告書
  240: 公開買付届出書
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

# 10年制限の境界 = 今日 - 10年
today = date.today()
boundary = date(today.year - 10, today.month, today.day)

# サンプリング日: 境界付近 + 各年の代表的な営業日
sample_dates: list[date] = []
# 境界付近 (最古の取得可能日)
sample_dates.append(boundary)
sample_dates.append(boundary + timedelta(days=7))
# 各年の4月第1週・10月第1週 (営業日が多い時期)
for year in range(boundary.year, today.year + 1):
    for month in [1, 4, 7, 10]:
        d = date(year, month, 3)  # 3日 = 大体営業日
        if d >= boundary and d <= today:
            sample_dates.append(d)

sample_dates = sorted(set(sample_dates))

print(f"調査期間: {boundary} 〜 {today}")
print(f"サンプル日数: {len(sample_dates)}")
print(f"対象書類種別: {list(TARGET_DOC_TYPES.keys())}")
print()

# 日付ごとに全書類を取得し、対象書類種別でフィルタ
results: dict[str, dict[str, int]] = {code: {} for code in TARGET_DOC_TYPES}
lines: list[str] = []

for i, d in enumerate(sample_dates):
    ds = d.isoformat()
    try:
        filings = edinet.documents(ds)
        counts: dict[str, int] = {}
        for f in filings:
            dt = f.doc_type_code
            if dt in TARGET_DOC_TYPES:
                counts[dt] = counts.get(dt, 0) + 1

        parts = [f"{ds}: total={len(filings):4d}"]
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
print("サマリー: 各書類種別の最古・最新の検出日と合計件数")
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
        s = f"  [{code}] {label}: データなし (サンプル期間内)"
    print(s)
    summary_lines.append(s)

# ファイル出力
out = Path(__file__).resolve().parent / "_probe_doc_types_result.txt"
out.write_text(
    f"調査日: {today}\n"
    f"境界日(10年制限): {boundary}\n"
    f"サンプル日数: {len(sample_dates)}\n\n"
    + "=== 日別詳細 ===\n"
    + "\n".join(lines)
    + "\n\n=== サマリー ===\n"
    + "\n".join(summary_lines)
    + "\n",
    encoding="utf-8",
)
print(f"\n結果を {out} に書き出しました")

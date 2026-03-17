"""EDINET API の 10年制限の境界日を探す実験スクリプト。"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

results: list[str] = []

# 生HTTPレスポンスも確認する
# 古い日付・境界付近を試す
# 2016-03-14 〜 2016-03-20 で正確な境界を探る
test_dates = [date(2016, 3, d) for d in range(14, 21)]

import edinet._http as _http

for d in test_dates:
    ds = d.isoformat()
    # 生HTTPレスポンスを確認
    try:
        resp = _http.get("/documents.json", params={"date": ds, "type": "2"})
        line = f"{ds}: HTTP {resp.status_code}, body_snippet={resp.text[:200]}"
    except Exception as e:
        line = f"{ds}: HTTP_FAIL ({type(e).__name__}: {e})"
    print(line)
    results.append(line)
    time.sleep(1)

# 結果をファイルに書き出し
out = Path(__file__).resolve().parent / "_probe_api_boundary_result.txt"
out.write_text("\n".join(results) + "\n")
print(f"\n結果を {out} に書き出しました")

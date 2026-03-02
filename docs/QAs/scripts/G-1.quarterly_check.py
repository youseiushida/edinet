"""G-1. 四半期報告書の廃止状況確認スクリプト

実行方法: uv run docs/QAs/scripts/G-1.quarterly_check.py
前提: EDINET_API_KEY 環境変数が必要
出力: 2024年4月以降の doc_type=140（四半期報告書）の検索結果
"""

from __future__ import annotations

import sys

sys.path.insert(0, "docs/QAs/scripts")
from _common import find_filings, print_filing_info


# 各期間を1週間に絞ったサンプリング（API は1日ずつ呼ぶため高速化）
# 四半期報告書は各四半期末の翌月に集中提出されるため、
# 提出ピーク期の1週間をサンプリングすれば十分
SAMPLE_PERIODS_POST = [
    # 2024-04以降（廃止後）
    ("2024-05-13", "2024-05-17"),  # Q1決算後
    ("2024-08-12", "2024-08-16"),  # Q1決算後
    ("2024-11-11", "2024-11-15"),  # Q2決算後
    ("2025-02-10", "2025-02-14"),  # Q3決算後
    ("2025-05-12", "2025-05-16"),  # Q1決算後
    ("2025-08-11", "2025-08-15"),  # Q1決算後
]

SAMPLE_PERIODS_PRE = [
    # 2024-04以前（制度存続中）: 提出ピーク1週間
    ("2024-02-12", "2024-02-16"),
]

SAMPLE_PERIODS_SEMI = [
    # 半期報告書（2025年、提出ピーク期）
    ("2025-03-10", "2025-03-14"),
]


def main() -> None:
    """四半期報告書（doc_type=140）の存否を 2024年4月以降で確認する。"""
    print("G-1: 四半期報告書の廃止状況確認")
    print("=" * 70)

    # ── Step 1: 2024年4月以降（廃止後）の四半期報告書を検索 ──
    print("\n[Step 1] 2024-04-01 以降の doc_type=140 を検索（各期間1週間サンプル）")
    print("-" * 70)

    total_found = 0
    for start, end in SAMPLE_PERIODS_POST:
        filings = find_filings(
            doc_type="140",
            start=start,
            end=end,
            has_xbrl=False,  # XBRL有無問わず検索
            max_results=0,
        )
        total_found += len(filings)
        xbrl_count = sum(1 for f in filings if f.has_xbrl)
        print(f"  {start} ~ {end}: {len(filings)} 件 (うち has_xbrl=True: {xbrl_count})")

        for f in filings[:2]:
            print_filing_info(f, label=f"  サンプル: {f.filer_name}")

    # ── Step 2: 2024年4月以前（制度存続中）の確認 ──
    print(f"\n\n[Step 2] 2024年2月 (廃止前) の doc_type=140 を検索")
    print("-" * 70)

    pre_total = 0
    pre_xbrl = 0
    for start, end in SAMPLE_PERIODS_PRE:
        filings = find_filings(
            doc_type="140",
            start=start,
            end=end,
            has_xbrl=False,
            max_results=0,
        )
        pre_total += len(filings)
        pre_xbrl += sum(1 for f in filings if f.has_xbrl)
        print(f"  {start} ~ {end}: {len(filings)} 件 (うち has_xbrl=True: {pre_xbrl})")
        for f in filings[:3]:
            print_filing_info(f, label=f"  サンプル: {f.filer_name}")

    # ── Step 3: 半期報告書（doc_type=160）の確認 ──
    print(f"\n\n[Step 3] 半期報告書 (doc_type=160) の最近の存在確認")
    print("-" * 70)

    semi_total = 0
    semi_xbrl = 0
    for start, end in SAMPLE_PERIODS_SEMI:
        filings = find_filings(
            doc_type="160",
            start=start,
            end=end,
            has_xbrl=False,
            max_results=0,
        )
        semi_total += len(filings)
        semi_xbrl += sum(1 for f in filings if f.has_xbrl)
        print(f"  {start} ~ {end}: {len(filings)} 件 (うち has_xbrl=True: {semi_xbrl})")
        for f in filings[:3]:
            print_filing_info(f, label=f"  サンプル: {f.filer_name}")

    # ── サマリー ──
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"  2024-04以降の四半期報告書(140)サンプル: {total_found} 件")
    print(f"  2024-02の四半期報告書(140)サンプル: {pre_total} 件")
    print(f"  2025-03の半期報告書(160)サンプル: {semi_total} 件")

    if total_found == 0:
        print("\n  → 四半期報告制度は 2024年4月の法改正で廃止されたことを確認。")
        print("  → TypeOfCurrentPeriodDEI に 'Q1'/'Q2'/'Q3' は今後使用されない。")
    else:
        print(f"\n  → 2024-04以降に {total_found} 件の doc_type=140 が存在。")
        print("  → 経過措置による提出の可能性あり。要確認。")


if __name__ == "__main__":
    main()

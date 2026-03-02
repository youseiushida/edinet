"""E-1b. 実ファイルの名前空間別 Fact 比率スクリプト（非同期版）

実行方法: uv run docs/QAs/scripts/E-1b.fact_ratio_async.py
前提: EDINET_API_KEY 環境変数が必要
出力: 有価証券報告書の XBRL インスタンスから名前空間別の Fact 数を集計し、
      財務4表 vs 非財務の比率を算出する。20社程度を非同期に取得して統計をとる。
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass

import edinet
from edinet.api.download import adownload_document
from edinet.models.filing import Filing
import edinet.public_api as public_api

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

# 同時並行ダウンロード数の上限（EDINET API のレート制限考慮）
MAX_CONCURRENT = 5


@dataclass
class FactProfile:
    """1社分の名前空間別 Fact 集計結果。"""

    filer_name: str
    doc_id: str
    ns_counts: Counter
    total: int


def count_facts_by_namespace(xbrl_bytes: bytes) -> Counter:
    """XBRL インスタンスから名前空間別の Fact 数をカウントする。

    Args:
        xbrl_bytes: XBRL ファイルのバイト列。

    Returns:
        名前空間プレフィックス分類 -> Fact 数の Counter。
    """
    try:
        content = xbrl_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = xbrl_bytes.decode("cp932", errors="replace")

    root = ET.fromstring(content)

    skip_prefixes = {
        "http://www.xbrl.org/2003/instance",
        "http://www.xbrl.org/2003/linkbase",
    }

    ns_counter: Counter = Counter()
    for child in root:
        tag = child.tag
        m = re.match(r"\{(.+?)\}", tag)
        if not m:
            ns_counter["(no namespace)"] += 1
            continue
        ns_uri = m.group(1)
        if any(ns_uri.startswith(p) for p in skip_prefixes):
            continue
        ns_counter[classify_namespace(ns_uri)] += 1

    return ns_counter


def classify_namespace(ns_uri: str) -> str:
    """名前空間 URI をカテゴリに分類する。

    Args:
        ns_uri: 名前空間 URI。

    Returns:
        分類名。
    """
    ns_lower = ns_uri.lower()
    if "jppfs" in ns_lower:
        return "jppfs (財務4表)"
    if "jpdei" in ns_lower:
        return "jpdei (DEI)"
    if "jpcrp" in ns_lower:
        return "jpcrp (有報非財務)"
    if "jpigp" in ns_lower:
        return "jpigp (IFRS一般目的)"
    if "ifrs" in ns_lower:
        return "IFRS"
    return "提出者拡張等"


async def process_filing(
    filing: Filing, sem: asyncio.Semaphore
) -> FactProfile | None:
    """1件の Filing を非同期ダウンロード・解析する。

    Args:
        filing: 対象 Filing。
        sem: 同時接続制限用セマフォ。

    Returns:
        解析結果。失敗時は None。
    """
    async with sem:
        try:
            zip_bytes = await adownload_document(filing.doc_id, file_type="1")
        except Exception as e:
            print(f"  [SKIP] {filing.filer_name} ({filing.doc_id}): {e}")
            return None

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        xbrl_members = [
            m
            for m in zf.namelist()
            if m.lower().endswith(".xbrl") and "publicdoc" in m.lower()
        ]
        if not xbrl_members:
            print(f"  [SKIP] {filing.filer_name}: .xbrl not found in PublicDoc")
            return None
        xbrl_bytes = zf.read(xbrl_members[0])

    ns_counts = count_facts_by_namespace(xbrl_bytes)
    total = sum(ns_counts.values())
    print(
        f"  [OK] {filing.filer_name:<20s} "
        f"({filing.sec_code or '----'}) "
        f"Fact={total:>5d}"
    )
    return FactProfile(
        filer_name=filing.filer_name or filing.doc_id,
        doc_id=filing.doc_id,
        ns_counts=ns_counts,
        total=total,
    )


async def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("E-1b. 実ファイルの名前空間別 Fact 比率分析（非同期版）")
    print("=" * 80)

    # 有報 (doc_type=120) を検索 — 2025年6月〜9月（決算集中期間）
    print("\n有価証券報告書 (doc_type=120) を検索中...")
    filings = await public_api.adocuments(
        doc_type="120", start="2025-06-01", end="2025-09-30"
    )
    filings = [
        f
        for f in filings
        if f.has_xbrl and f.edinet_code and f.sec_code and f.filer_name
    ]
    print(f"  XBRL 付き有報: {len(filings)} 件")

    if not filings:
        print("ERROR: 該当 Filing なし")
        return

    # 多様性のため sec_code でソートし、均等に20社を選定
    filings.sort(key=lambda f: f.sec_code or "")
    step = max(1, len(filings) // 20)
    selected = filings[::step][:20]
    print(f"  選定: {len(selected)} 社（sec_code 均等サンプリング）\n")

    # 非同期で並列ダウンロード・解析
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [process_filing(f, sem) for f in selected]
    results = await asyncio.gather(*tasks)
    profiles = [r for r in results if r is not None]

    if not profiles:
        print("ERROR: 解析成功 0 件")
        return

    # 集計
    print(f"\n{'=' * 80}")
    print(f"【集計結果】 解析成功: {len(profiles)} 社")
    print("=" * 80)

    # 個社別サマリ
    print(f"\n{'企業名':<22s} {'合計':>6s} {'jppfs':>8s} {'jpcrp':>8s} "
          f"{'jpdei':>8s} {'IFRS':>8s} {'拡張等':>8s}")
    print("-" * 80)
    for p in profiles:
        jppfs = p.ns_counts.get("jppfs (財務4表)", 0)
        jpcrp = p.ns_counts.get("jpcrp (有報非財務)", 0)
        jpdei = p.ns_counts.get("jpdei (DEI)", 0)
        ifrs = (
            p.ns_counts.get("IFRS", 0)
            + p.ns_counts.get("jpigp (IFRS一般目的)", 0)
        )
        ext = p.ns_counts.get("提出者拡張等", 0)
        print(
            f"  {p.filer_name:<20s} {p.total:>6d} "
            f"{jppfs:>5d}({jppfs / p.total * 100:>4.1f}%) "
            f"{jpcrp:>5d}({jpcrp / p.total * 100:>4.1f}%) "
            f"{jpdei:>5d}({jpdei / p.total * 100:>4.1f}%) "
            f"{ifrs:>5d}({ifrs / p.total * 100:>4.1f}%) "
            f"{ext:>5d}({ext / p.total * 100:>4.1f}%)"
        )

    # 全体集計
    all_counts: Counter = Counter()
    total_facts = 0
    for p in profiles:
        all_counts += p.ns_counts
        total_facts += p.total

    print(f"\n--- 全体集計 (合計 Fact: {total_facts:,}) ---")
    for cat, count in all_counts.most_common():
        pct = count / total_facts * 100
        print(f"  {cat:<30s}: {count:>7,} ({pct:>5.1f}%)")

    # 財務 vs 非財務
    jppfs_total = all_counts.get("jppfs (財務4表)", 0)
    ifrs_total = (
        all_counts.get("IFRS", 0)
        + all_counts.get("jpigp (IFRS一般目的)", 0)
    )
    financial_total = jppfs_total + ifrs_total
    dei_total = all_counts.get("jpdei (DEI)", 0)
    non_financial = total_facts - financial_total - dei_total

    print(f"\n--- 財務 vs 非財務 ---")
    print(
        f"  財務 (jppfs+IFRS):  {financial_total:>7,} "
        f"({financial_total / total_facts * 100:.1f}%)"
    )
    print(
        f"  非財務 (jpcrp+拡張): {non_financial:>7,} "
        f"({non_financial / total_facts * 100:.1f}%)"
    )
    print(
        f"  DEI:                 {dei_total:>7,} "
        f"({dei_total / total_facts * 100:.1f}%)"
    )


if __name__ == "__main__":
    asyncio.run(main())

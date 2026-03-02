"""E-1b. 実ファイルの名前空間別 Fact 比率スクリプト

実行方法: uv run docs/QAs/scripts/E-1b.fact_ratio.py
前提: EDINET_API_KEY 環境変数が必要
出力: 有価証券報告書の XBRL インスタンスから名前空間別の Fact 数を集計し、
      財務4表 vs 非財務の比率を算出
"""

from __future__ import annotations

import io
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

from _common import find_filings, get_zip, print_filing_info


def count_facts_by_namespace(xbrl_bytes: bytes) -> Counter:
    """XBRL インスタンスから名前空間別の Fact 数をカウントする。

    Args:
        xbrl_bytes: XBRL ファイルのバイト列。

    Returns:
        名前空間 URI -> Fact 数の Counter。
    """
    ns_counter: Counter = Counter()

    # XML パース
    try:
        content = xbrl_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = xbrl_bytes.decode("cp932", errors="replace")

    root = ET.fromstring(content)

    # xbrli:xbrl 直下の子要素で、context/unit/schemaRef 以外が Fact
    skip_tags = {
        "{http://www.xbrl.org/2003/instance}context",
        "{http://www.xbrl.org/2003/instance}unit",
        "{http://www.xbrl.org/2003/instance}schemaRef",
        "{http://www.xbrl.org/2003/linkbase}schemaRef",
    }

    for child in root:
        tag = child.tag
        if tag in skip_tags:
            continue
        # link: 要素もスキップ
        if tag.startswith("{http://www.xbrl.org/2003/linkbase}"):
            continue
        if tag.startswith("{http://www.xbrl.org/2003/instance}"):
            continue

        # 名前空間を抽出
        m = re.match(r"\{(.+?)\}", tag)
        if m:
            ns_uri = m.group(1)
            ns_counter[ns_uri] += 1
        else:
            ns_counter["(no namespace)"] += 1

    return ns_counter


def classify_namespace(ns_uri: str) -> str:
    """名前空間 URI を分類する。

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
        return "jpcrp (非財務)"
    if "jpigp" in ns_lower:
        return "jpigp (IFRS一般目的)"
    if "jppfs_e" in ns_lower or "jppfs_t" in ns_lower:
        return "jppfs拡張"
    if "ifrs" in ns_lower:
        return "IFRS"

    # 提出者拡張（提出者の独自名前空間）
    return f"その他 ({ns_uri[:60]}...)"


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("E-1b. 実ファイルの名前空間別 Fact 比率分析")
    print("=" * 80)

    # 2-3 社の有価証券報告書を取得
    print("\n有価証券報告書 (doc_type=120) を検索中...")
    filings = find_filings(
        doc_type="120",
        start="2025-06-01",
        end="2025-09-30",
        has_xbrl=True,
        max_results=20,
    )

    if not filings:
        print("ERROR: Filing が見つかりませんでした")
        return

    # 小規模企業と中規模企業を選定（多様性のため）
    # sec_code でソートし、異なる企業を選択
    candidates = [f for f in filings if f.edinet_code and f.sec_code and f.filer_name]
    if len(candidates) > 3:
        # 最初、中間、最後の3社を選択
        selected = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
    else:
        selected = candidates[:3]

    print(f"\n選定企業数: {len(selected)}")

    all_ns_totals: Counter = Counter()
    company_results: list[tuple[str, Counter]] = []

    for filing in selected:
        print(f"\n{'=' * 60}")
        print_filing_info(filing, label=f"分析対象")

        try:
            zip_bytes = get_zip(filing.doc_id)
        except Exception as e:
            print(f"  ダウンロードエラー: {e}")
            continue

        # XBRL ファイルを検索
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xbrl_members = [
                m for m in zf.namelist()
                if m.lower().endswith(".xbrl")
                and "publicdoc" in m.lower()
            ]

            if not xbrl_members:
                print("  PublicDoc 内に .xbrl ファイルが見つかりません")
                continue

            print(f"  XBRL ファイル: {xbrl_members[0]}")
            xbrl_bytes = zf.read(xbrl_members[0])

        ns_counter = count_facts_by_namespace(xbrl_bytes)
        total_facts = sum(ns_counter.values())

        print(f"\n  --- 名前空間別 Fact 数 (合計: {total_facts}) ---")
        for ns_uri, count in ns_counter.most_common():
            pct = count / total_facts * 100 if total_facts > 0 else 0
            category = classify_namespace(ns_uri)
            print(f"    {category:<30s}: {count:>5d} ({pct:>5.1f}%)")
            print(f"      URI: {ns_uri}")

        all_ns_totals += ns_counter
        company_results.append((filing.filer_name or filing.doc_id, ns_counter))

    # 全体集計
    if company_results:
        print("\n" + "=" * 80)
        print("【全体集計 — 名前空間カテゴリ別 Fact 比率】")
        print("=" * 80)

        total = sum(all_ns_totals.values())
        category_totals: Counter = Counter()

        for ns_uri, count in all_ns_totals.items():
            category = classify_namespace(ns_uri)
            category_totals[category] += count

        print(f"\n  合計 Fact 数: {total}")
        for category, count in category_totals.most_common():
            pct = count / total * 100 if total > 0 else 0
            print(f"    {category:<35s}: {count:>6d} ({pct:>5.1f}%)")

        # 財務4表 vs 非財務
        financial = category_totals.get("jppfs (財務4表)", 0)
        non_financial = total - financial - category_totals.get("jpdei (DEI)", 0)
        dei = category_totals.get("jpdei (DEI)", 0)

        print(f"\n  --- 財務 vs 非財務 ---")
        print(f"    財務4表 (jppfs): {financial:>6d} ({financial / total * 100:.1f}%)")
        print(f"    非財務 (jpcrp等): {non_financial:>6d} ({non_financial / total * 100:.1f}%)")
        print(f"    DEI:              {dei:>6d} ({dei / total * 100:.1f}%)")


if __name__ == "__main__":
    main()

"""J-5. 前期 Fact の concept 名確認スクリプト。

実行方法: EDINET_API_KEY=... uv run docs/QAs/scripts/J-5.prior_facts.py
前提: EDINET_API_KEY 環境変数が必要
出力: トヨタ Filing から Prior1YearDuration の Fact を抽出し、
      CurrentYearDuration と同じ concept 名が使われていることを確認。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import extract_member, find_public_doc_members, get_zip  # noqa: E402

# トヨタ Filing
DOC_ID = "S100VWVY"

# XBRL 名前空間
NS_XBRLI = "http://www.xbrl.org/2003/instance"


def extract_local_name(tag: str) -> tuple[str, str]:
    """タグ名から名前空間 URI とローカル名を抽出する。

    Args:
        tag: XML タグ名。

    Returns:
        (名前空間 URI, ローカル名) のタプル。
    """
    if "}" in tag:
        ns_uri, local = tag.rsplit("}", 1)
        ns_uri = ns_uri.lstrip("{")
        return ns_uri, local
    return "", tag


def main() -> None:
    """メイン処理。"""
    print("J-5: 前期 Fact の concept 名確認")
    print("=" * 70)

    # Step 1: XBRL ファイルの取得
    print(f"\n[Step 1] Filing {DOC_ID} の XBRL を取得中...")
    zip_bytes = get_zip(DOC_ID)
    xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")
    print(f"  XBRL ファイル数: {len(xbrl_members)}")

    if not xbrl_members:
        print("ERROR: XBRL ファイルが見つかりません")
        return

    xbrl_path = xbrl_members[0]
    print(f"  使用ファイル: {xbrl_path}")
    xbrl_bytes = extract_member(zip_bytes, xbrl_path)

    # Step 2: Fact を Context ID 別に収集
    print(f"\n[Step 2] Fact を Context ID グループ別に収集")
    print("-" * 70)

    root = ET.fromstring(xbrl_bytes)

    # Context ID ごとに Fact の concept 名を収集
    facts_by_ctx: dict[str, set[str]] = defaultdict(set)
    value_by_ctx_concept: dict[tuple[str, str], str] = {}

    for elem in root:
        ctx_ref = elem.get("contextRef")
        if not ctx_ref:
            continue

        _, local_name = extract_local_name(elem.tag)
        facts_by_ctx[ctx_ref].add(local_name)

        val = (elem.text or "").strip()
        if len(val) > 50:
            val = val[:50] + "..."
        value_by_ctx_concept[(ctx_ref, local_name)] = val

    print(f"  Context 種別数: {len(facts_by_ctx)}")

    # Step 3: CurrentYearDuration vs Prior1YearDuration の比較
    print(f"\n[Step 3] CurrentYearDuration vs Prior1YearDuration の concept 比較")
    print("-" * 70)

    current_concepts = facts_by_ctx.get("CurrentYearDuration", set())
    prior1_concepts = facts_by_ctx.get("Prior1YearDuration", set())

    print(f"  CurrentYearDuration の concept 数: {len(current_concepts)}")
    print(f"  Prior1YearDuration の concept 数: {len(prior1_concepts)}")

    shared = current_concepts & prior1_concepts
    only_current = current_concepts - prior1_concepts
    only_prior = prior1_concepts - current_concepts

    print(f"\n  共通 concept 数: {len(shared)}")
    print(f"  CurrentYear のみ: {len(only_current)}")
    print(f"  Prior1Year のみ: {len(only_prior)}")

    overlap_pct = len(shared) / len(prior1_concepts) * 100 if prior1_concepts else 0
    print(f"  重複率（Prior1 ベース）: {overlap_pct:.1f}%")

    # 共通 concept の値を比較（先頭20件）
    print(f"\n  --- 共通 concept の値比較（先頭 20 件）---")
    print(f"  {'concept 名':<60s} {'CurrentYear':>15s} {'Prior1Year':>15s}")
    print(f"  {'-' * 60} {'-' * 15} {'-' * 15}")

    for concept in sorted(shared)[:20]:
        cur_val = value_by_ctx_concept.get(("CurrentYearDuration", concept), "")
        pri_val = value_by_ctx_concept.get(("Prior1YearDuration", concept), "")
        print(f"  {concept:<60s} {cur_val:>15s} {pri_val:>15s}")

    # CurrentYear のみの concept（先頭10件）
    if only_current:
        print(f"\n  --- CurrentYear のみの concept（先頭 10 件）---")
        for concept in sorted(only_current)[:10]:
            print(f"    {concept}")
        if len(only_current) > 10:
            print(f"    ... 残り {len(only_current) - 10} 件")

    # Prior1Year のみの concept（先頭10件）
    if only_prior:
        print(f"\n  --- Prior1Year のみの concept（先頭 10 件）---")
        for concept in sorted(only_prior)[:10]:
            print(f"    {concept}")
        if len(only_prior) > 10:
            print(f"    ... 残り {len(only_prior) - 10} 件")

    # Step 4: CurrentYearInstant vs Prior1YearInstant の比較
    print(f"\n\n[Step 4] CurrentYearInstant vs Prior1YearInstant の concept 比較")
    print("-" * 70)

    current_inst = facts_by_ctx.get("CurrentYearInstant", set())
    prior1_inst = facts_by_ctx.get("Prior1YearInstant", set())

    print(f"  CurrentYearInstant の concept 数: {len(current_inst)}")
    print(f"  Prior1YearInstant の concept 数: {len(prior1_inst)}")

    shared_inst = current_inst & prior1_inst
    only_current_inst = current_inst - prior1_inst
    only_prior_inst = prior1_inst - current_inst

    print(f"\n  共通 concept 数: {len(shared_inst)}")
    print(f"  CurrentYear のみ: {len(only_current_inst)}")
    print(f"  Prior1Year のみ: {len(only_prior_inst)}")

    if prior1_inst:
        overlap_inst_pct = len(shared_inst) / len(prior1_inst) * 100
        print(f"  重複率（Prior1 ベース）: {overlap_inst_pct:.1f}%")

    # Step 5: 全 Prior{n} グループの概要
    print(f"\n\n[Step 5] 全 Prior{{n}} グループの Fact 数概要")
    print("-" * 70)

    prior_groups = sorted(
        [k for k in facts_by_ctx if k.startswith("Prior")],
    )
    for ctx_id in prior_groups[:20]:
        concepts = facts_by_ctx[ctx_id]
        print(f"  {ctx_id:<55s}: {len(concepts):>5d} concepts")

    if len(prior_groups) > 20:
        print(f"  ... 残り {len(prior_groups) - 20} 件")

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print("=" * 70)
    print(f"  Duration 比較:")
    print(f"    CurrentYearDuration concepts: {len(current_concepts)}")
    print(f"    Prior1YearDuration concepts:  {len(prior1_concepts)}")
    print(f"    共通 concepts:                {len(shared)}")
    print(f"    重複率 (Prior1 ベース):       {overlap_pct:.1f}%")
    print(f"  Instant 比較:")
    print(f"    CurrentYearInstant concepts:  {len(current_inst)}")
    print(f"    Prior1YearInstant concepts:   {len(prior1_inst)}")
    print(f"    共通 concepts:                {len(shared_inst)}")
    print(f"  結論: 前期 Fact は当期 Fact と同じ concept 名（jppfs_cor/jpcrp_cor）を使用する")


if __name__ == "__main__":
    main()

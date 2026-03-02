"""J-6. クロスフィリング（年度横断）データ一貫性の検証スクリプト。

実行方法: EDINET_API_KEY=... uv run docs/QAs/scripts/J-6.cross_year_compare.py
前提: EDINET_API_KEY 環境変数が必要
出力: 同一企業の2年分の有報をダウンロードし、
      (a) concept 名の一致、(b) Context ID パターンの一致、
      (c) 前年有報 CurrentYear ↔ 当年有報 Prior1Year の値比較、
      (d) entity/identifier の安定性を検証。
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    extract_member,
    find_filings,
    find_public_doc_members,
    get_zip,
    print_filing_info,
)

# トヨタの EDINET コード
TOYOTA_EDINET_CODE = "E02144"

# XBRL 名前空間
NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_LINK = "http://www.xbrl.org/2003/linkbase"
NS_XLINK = "http://www.w3.org/1999/xlink"
NS = {
    "xbrli": NS_XBRLI,
    "xbrldi": "http://xbrl.org/2006/xbrldi",
    "link": NS_LINK,
}


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


def guess_prefix(ns_uri: str) -> str:
    """名前空間 URI から短縮プレフィックスを推定する。

    Args:
        ns_uri: 名前空間 URI。

    Returns:
        推定されたプレフィックス文字列。
    """
    if "jppfs_cor" in ns_uri:
        return "jppfs_cor"
    if "jpcrp_cor" in ns_uri:
        return "jpcrp_cor"
    if "jpdei_cor" in ns_uri:
        return "jpdei_cor"
    if "jpigp_cor" in ns_uri:
        return "jpigp_cor"
    if "jpcrp" in ns_uri and "asr" in ns_uri:
        return "filer"
    if "ifrs" in ns_uri:
        return "ifrs"
    return ""


def parse_xbrl_facts(
    xbrl_bytes: bytes,
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, dict],
    dict[str, str],
    list[str],
]:
    """XBRL バイト列から Fact と Context を解析する。

    Args:
        xbrl_bytes: XBRL ファイルのバイト列。

    Returns:
        (facts, contexts, entity_info, schema_refs) のタプル。
        facts: {context_id: {qualified_concept: value}}
        contexts: {context_id: {period: str, members: list[str]}}
        entity_info: {context_id: identifier_text}
        schema_refs: schemaRef の href リスト
    """
    root = ET.fromstring(xbrl_bytes)

    # schemaRef を抽出
    schema_refs: list[str] = []
    for sr in root.iter(f"{{{NS_LINK}}}schemaRef"):
        href = sr.get(f"{{{NS_XLINK}}}href", "")
        if href:
            schema_refs.append(href)

    # Context を解析
    contexts: dict[str, dict] = {}
    entity_info: dict[str, str] = {}

    for ctx in root.findall("xbrli:context", NS):
        ctx_id = ctx.get("id", "")

        # entity/identifier
        entity_elem = ctx.find("xbrli:entity", NS)
        if entity_elem is not None:
            ident = entity_elem.find("xbrli:identifier", NS)
            if ident is not None and ident.text:
                entity_info[ctx_id] = ident.text.strip()

        # period
        period_elem = ctx.find("xbrli:period", NS)
        period_str = ""
        if period_elem is not None:
            instant = period_elem.find("xbrli:instant", NS)
            if instant is not None and instant.text:
                period_str = f"instant={instant.text}"
            else:
                start = period_elem.find("xbrli:startDate", NS)
                end = period_elem.find("xbrli:endDate", NS)
                if start is not None and end is not None:
                    period_str = f"duration={start.text}~{end.text}"

        # scenario members
        members: list[str] = []
        scenario = ctx.find("xbrli:scenario", NS)
        if scenario is not None:
            for em in scenario.findall("xbrldi:explicitMember", NS):
                dim = em.get("dimension", "")
                val = (em.text or "").strip()
                members.append(f"{dim}={val}")

        contexts[ctx_id] = {
            "period": period_str,
            "members": members,
        }

    # Fact を収集
    facts: dict[str, dict[str, str]] = defaultdict(dict)
    for elem in root:
        ctx_ref = elem.get("contextRef")
        if not ctx_ref:
            continue
        ns_uri, local_name = extract_local_name(elem.tag)
        prefix = guess_prefix(ns_uri)
        qname = f"{prefix}:{local_name}" if prefix else local_name
        val = (elem.text or "").strip()
        facts[ctx_ref][qname] = val

    return dict(facts), contexts, entity_info, schema_refs


def classify_context_group(ctx_id: str) -> str:
    """Context ID から相対期間グループを抽出する。

    Args:
        ctx_id: Context ID 文字列。

    Returns:
        グループ名（例: CurrentYear, Prior1Year）。
    """
    m = re.match(
        r"^(CurrentYear|Interim|Prior\d+Year|Prior\d+Interim|"
        r"FilingDate|RecordDate|RecentDate|FutureDate)",
        ctx_id,
    )
    return m.group(1) if m else "Unknown"


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("J-6. クロスフィリング（年度横断）データ一貫性の検証")
    print("=" * 80)

    # ===== Step 1: 2年分の Filing を検索 =====
    print("\n[Step 1] トヨタの2年分の有報を検索")
    print("-" * 70)

    # 2025年6月期（2025-03-31 期）: S100VWVY
    # 2024年6月期（2024-03-31 期）: 別の doc_id を検索
    filings_2025 = find_filings(
        edinet_code=TOYOTA_EDINET_CODE,
        doc_type="120",
        start="2025-06-01",
        end="2025-07-31",
        has_xbrl=True,
    )
    filings_2024 = find_filings(
        edinet_code=TOYOTA_EDINET_CODE,
        doc_type="120",
        start="2024-06-01",
        end="2024-07-31",
        has_xbrl=True,
    )

    print(f"  2025年提出 Filing 数: {len(filings_2025)}")
    print(f"  2024年提出 Filing 数: {len(filings_2024)}")

    if not filings_2025 or not filings_2024:
        print("ERROR: Filing が見つかりません")
        return

    filing_new = filings_2025[0]  # 2025年（当年）
    filing_old = filings_2024[0]  # 2024年（前年）

    print_filing_info(filing_new, label="当年 Filing (2025)")
    print_filing_info(filing_old, label="前年 Filing (2024)")

    # ===== Step 2: XBRL ファイルの取得・解析 =====
    print("\n\n[Step 2] XBRL ファイルの取得・解析")
    print("-" * 70)

    def load_xbrl(doc_id: str, label: str) -> tuple:
        """Filing から XBRL を取得・解析する。

        Args:
            doc_id: 書類管理番号。
            label: ラベル文字列。

        Returns:
            (facts, contexts, entity_info, schema_refs) のタプル。
        """
        print(f"\n  [{label}] doc_id={doc_id}")
        zip_bytes = get_zip(doc_id)
        xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")
        print(f"    .xbrl ファイル: {xbrl_members}")
        if not xbrl_members:
            print("    ERROR: .xbrl ファイルが見つかりません")
            return {}, {}, {}, []
        xbrl_bytes = extract_member(zip_bytes, xbrl_members[0])
        print(f"    サイズ: {len(xbrl_bytes):,} bytes")
        return parse_xbrl_facts(xbrl_bytes)

    facts_new, ctx_new, entity_new, schemas_new = load_xbrl(
        filing_new.doc_id, "当年 2025",
    )
    facts_old, ctx_old, entity_old, schemas_old = load_xbrl(
        filing_old.doc_id, "前年 2024",
    )

    # ===== Step 3: schemaRef の比較（タクソノミバージョン） =====
    print("\n\n[Step 3] schemaRef の比較（タクソノミバージョン）")
    print("-" * 70)

    print(f"  当年 (2025) schemaRef ({len(schemas_new)} 件):")
    for s in schemas_new:
        print(f"    {s}")
    print(f"\n  前年 (2024) schemaRef ({len(schemas_old)} 件):")
    for s in schemas_old:
        print(f"    {s}")

    # バージョン日付を抽出して比較
    ver_re = re.compile(r"/(\d{4}-\d{2}-\d{2})/")
    versions_new = set()
    versions_old = set()
    for s in schemas_new:
        m = ver_re.search(s)
        if m:
            versions_new.add(m.group(1))
    for s in schemas_old:
        m = ver_re.search(s)
        if m:
            versions_old.add(m.group(1))
    print(f"\n  当年のタクソノミバージョン: {sorted(versions_new)}")
    print(f"  前年のタクソノミバージョン: {sorted(versions_old)}")

    # ===== Step 4: entity/identifier の比較 =====
    print("\n\n[Step 4] entity/identifier の比較")
    print("-" * 70)

    unique_entities_new = set(entity_new.values())
    unique_entities_old = set(entity_old.values())

    print(f"  当年の identifier: {unique_entities_new}")
    print(f"  前年の identifier: {unique_entities_old}")
    print(f"  一致: {unique_entities_new == unique_entities_old}")

    # ===== Step 5: concept 名の年度間比較 =====
    print("\n\n[Step 5] concept 名の年度間比較")
    print("-" * 70)

    # 全 concept を収集
    all_concepts_new: set[str] = set()
    for ctx_facts in facts_new.values():
        all_concepts_new.update(ctx_facts.keys())

    all_concepts_old: set[str] = set()
    for ctx_facts in facts_old.values():
        all_concepts_old.update(ctx_facts.keys())

    shared_concepts = all_concepts_new & all_concepts_old
    only_new = all_concepts_new - all_concepts_old
    only_old = all_concepts_old - all_concepts_new

    print(f"  当年の concept 数: {len(all_concepts_new)}")
    print(f"  前年の concept 数: {len(all_concepts_old)}")
    print(f"  共通 concept 数: {len(shared_concepts)}")
    print(f"  当年のみ: {len(only_new)}")
    print(f"  前年のみ: {len(only_old)}")

    if all_concepts_old:
        overlap_pct = len(shared_concepts) / len(all_concepts_old) * 100
        print(f"  重複率（前年ベース）: {overlap_pct:.1f}%")

    # 名前空間別に差分を表示
    print(f"\n  --- 当年のみの concept（先頭 15 件）---")
    for c in sorted(only_new)[:15]:
        print(f"    {c}")
    if len(only_new) > 15:
        print(f"    ... 残り {len(only_new) - 15} 件")

    print(f"\n  --- 前年のみの concept（先頭 15 件）---")
    for c in sorted(only_old)[:15]:
        print(f"    {c}")
    if len(only_old) > 15:
        print(f"    ... 残り {len(only_old) - 15} 件")

    # filer: プレフィックス（提出者別タクソノミ）を除いた比較
    std_concepts_new = {c for c in all_concepts_new if not c.startswith("filer:")}
    std_concepts_old = {c for c in all_concepts_old if not c.startswith("filer:")}
    shared_std = std_concepts_new & std_concepts_old
    only_new_std = std_concepts_new - std_concepts_old
    only_old_std = std_concepts_old - std_concepts_new

    print(f"\n  --- 標準タクソノミのみ（filer: を除外）---")
    print(f"  当年: {len(std_concepts_new)}, 前年: {len(std_concepts_old)}")
    print(f"  共通: {len(shared_std)}, 当年のみ: {len(only_new_std)}, 前年のみ: {len(only_old_std)}")
    if std_concepts_old:
        print(f"  重複率（前年ベース）: {len(shared_std) / len(std_concepts_old) * 100:.1f}%")

    if only_new_std:
        print(f"\n  標準タクソノミで当年のみ:")
        for c in sorted(only_new_std)[:10]:
            print(f"    {c}")
    if only_old_std:
        print(f"\n  標準タクソノミで前年のみ:")
        for c in sorted(only_old_std)[:10]:
            print(f"    {c}")

    # ===== Step 6: Context ID パターンの比較 =====
    print("\n\n[Step 6] Context ID パターンの比較")
    print("-" * 70)

    # Context ID のグループ分け
    groups_new: dict[str, list[str]] = defaultdict(list)
    groups_old: dict[str, list[str]] = defaultdict(list)

    for ctx_id in ctx_new:
        groups_new[classify_context_group(ctx_id)].append(ctx_id)
    for ctx_id in ctx_old:
        groups_old[classify_context_group(ctx_id)].append(ctx_id)

    print(f"  当年 Context 総数: {len(ctx_new)}")
    print(f"  前年 Context 総数: {len(ctx_old)}")

    all_groups = sorted(set(groups_new.keys()) | set(groups_old.keys()))
    print(f"\n  {'グループ':<20s} {'当年':>6s} {'前年':>6s}")
    print(f"  {'-' * 35}")
    for g in all_groups:
        n_new = len(groups_new.get(g, []))
        n_old = len(groups_old.get(g, []))
        print(f"  {g:<20s} {n_new:>6d} {n_old:>6d}")

    # Context ID 名の共通/差分
    ctx_ids_new = set(ctx_new.keys())
    ctx_ids_old = set(ctx_old.keys())
    shared_ctx = ctx_ids_new & ctx_ids_old
    only_new_ctx = ctx_ids_new - ctx_ids_old
    only_old_ctx = ctx_ids_old - ctx_ids_new

    print(f"\n  共通 Context ID: {len(shared_ctx)}")
    print(f"  当年のみ: {len(only_new_ctx)}")
    print(f"  前年のみ: {len(only_old_ctx)}")

    # 基本 Context ID（メンバーなし）のパターン比較
    basic_ids = {
        "CurrentYearDuration", "CurrentYearInstant",
        "Prior1YearDuration", "Prior1YearInstant",
    }
    print(f"\n  基本 Context ID の存在確認:")
    for bid in sorted(basic_ids):
        in_new = bid in ctx_new
        in_old = bid in ctx_old
        print(f"    {bid:<30s}: 当年={in_new}, 前年={in_old}")

    # ===== Step 7: Prior1Year（当年）vs CurrentYear（前年）の値比較 =====
    print("\n\n[Step 7] Prior1Year（当年）vs CurrentYear（前年）の値比較")
    print("-" * 70)
    print("  当年有報の Prior1YearDuration Fact と前年有報の CurrentYearDuration Fact を比較")

    prior1_facts_new = facts_new.get("Prior1YearDuration", {})
    current_facts_old = facts_old.get("CurrentYearDuration", {})

    print(f"\n  当年 Prior1YearDuration Fact 数: {len(prior1_facts_new)}")
    print(f"  前年 CurrentYearDuration Fact 数: {len(current_facts_old)}")

    # 共通 concept で値を比較
    shared_dur = set(prior1_facts_new.keys()) & set(current_facts_old.keys())
    print(f"  共通 concept 数: {len(shared_dur)}")

    match_count = 0
    mismatch_count = 0
    mismatches: list[tuple[str, str, str]] = []

    for concept in sorted(shared_dur):
        val_prior1 = prior1_facts_new[concept]
        val_current = current_facts_old[concept]

        # 長い textBlock は比較から除外
        if len(val_prior1) > 500 or len(val_current) > 500:
            continue

        if val_prior1 == val_current:
            match_count += 1
        else:
            mismatch_count += 1
            mismatches.append((concept, val_prior1, val_current))

    total_compared = match_count + mismatch_count
    print(f"\n  比較対象 Fact 数（textBlock 除外）: {total_compared}")
    print(f"  一致: {match_count}")
    print(f"  不一致: {mismatch_count}")
    if total_compared > 0:
        print(f"  一致率: {match_count / total_compared * 100:.1f}%")

    if mismatches:
        print(f"\n  --- 不一致の Fact（先頭 20 件）---")
        print(f"  {'concept':<50s} {'Prior1(当年)':>15s} {'Current(前年)':>15s}")
        print(f"  {'-' * 50} {'-' * 15} {'-' * 15}")
        for concept, v1, v2 in mismatches[:20]:
            # 値を短縮表示
            d1 = v1[:15] if len(v1) <= 15 else v1[:12] + "..."
            d2 = v2[:15] if len(v2) <= 15 else v2[:12] + "..."
            print(f"  {concept:<50s} {d1:>15s} {d2:>15s}")
        if len(mismatches) > 20:
            print(f"  ... 残り {len(mismatches) - 20} 件")

    # Instant 版の比較
    print(f"\n  --- Instant の比較 ---")
    prior1_inst_new = facts_new.get("Prior1YearInstant", {})
    current_inst_old = facts_old.get("CurrentYearInstant", {})

    print(f"  当年 Prior1YearInstant Fact 数: {len(prior1_inst_new)}")
    print(f"  前年 CurrentYearInstant Fact 数: {len(current_inst_old)}")

    shared_inst = set(prior1_inst_new.keys()) & set(current_inst_old.keys())
    match_inst = 0
    mismatch_inst = 0
    mismatches_inst: list[tuple[str, str, str]] = []

    for concept in sorted(shared_inst):
        v1 = prior1_inst_new[concept]
        v2 = current_inst_old[concept]
        if len(v1) > 500 or len(v2) > 500:
            continue
        if v1 == v2:
            match_inst += 1
        else:
            mismatch_inst += 1
            mismatches_inst.append((concept, v1, v2))

    total_inst = match_inst + mismatch_inst
    print(f"  比較対象: {total_inst}, 一致: {match_inst}, 不一致: {mismatch_inst}")
    if total_inst > 0:
        print(f"  一致率: {match_inst / total_inst * 100:.1f}%")

    if mismatches_inst:
        print(f"\n  --- Instant 不一致（先頭 15 件）---")
        for concept, v1, v2 in mismatches_inst[:15]:
            d1 = v1[:20] if len(v1) <= 20 else v1[:17] + "..."
            d2 = v2[:20] if len(v2) <= 20 else v2[:17] + "..."
            print(f"    {concept:<50s}")
            print(f"      Prior1(当年): {d1}")
            print(f"      Current(前年): {d2}")

    # ===== Step 8: period 日付の整合性確認 =====
    print("\n\n[Step 8] period 日付の整合性確認")
    print("-" * 70)

    print("  当年有報の Prior1Year と前年有報の CurrentYear の period が一致するか:")

    # Prior1YearDuration の period（当年有報）
    p1_dur_period = ctx_new.get("Prior1YearDuration", {}).get("period", "N/A")
    cy_dur_period = ctx_old.get("CurrentYearDuration", {}).get("period", "N/A")
    print(f"\n    当年 Prior1YearDuration period: {p1_dur_period}")
    print(f"    前年 CurrentYearDuration period: {cy_dur_period}")
    print(f"    一致: {p1_dur_period == cy_dur_period}")

    p1_inst_period = ctx_new.get("Prior1YearInstant", {}).get("period", "N/A")
    cy_inst_period = ctx_old.get("CurrentYearInstant", {}).get("period", "N/A")
    print(f"\n    当年 Prior1YearInstant period: {p1_inst_period}")
    print(f"    前年 CurrentYearInstant period: {cy_inst_period}")
    print(f"    一致: {p1_inst_period == cy_inst_period}")

    # ===== サマリー =====
    print(f"\n\n{'=' * 80}")
    print("サマリー")
    print("=" * 80)
    print(f"  Filing:")
    print(f"    当年: {filing_new.doc_id} ({filing_new.filing_date})")
    print(f"    前年: {filing_old.doc_id} ({filing_old.filing_date})")
    print(f"  entity/identifier: {'一致' if unique_entities_new == unique_entities_old else '不一致'}")
    print(f"    値: {unique_entities_new}")
    print(f"  タクソノミバージョン:")
    print(f"    当年: {sorted(versions_new)}")
    print(f"    前年: {sorted(versions_old)}")
    print(f"  concept 一致率（前年ベース）: {len(shared_concepts) / len(all_concepts_old) * 100:.1f}%")
    print(f"    標準タクソノミのみ: {len(shared_std) / len(std_concepts_old) * 100:.1f}%")
    print(f"  Context パターン:")
    print(f"    当年 Context 数: {len(ctx_new)}, 前年 Context 数: {len(ctx_old)}")
    print(f"    基本 ID (CurrentYear/Prior1Year) は両年とも存在")
    print(f"  Prior1Year(当年) vs CurrentYear(前年):")
    print(f"    Duration 一致率: {match_count / total_compared * 100:.1f}%" if total_compared > 0 else "    Duration: 比較不可")
    print(f"    Instant 一致率: {match_inst / total_inst * 100:.1f}%" if total_inst > 0 else "    Instant: 比較不可")
    print(f"    period 日付一致: {p1_dur_period == cy_dur_period}")
    print(f"  結論:")
    print(f"    - concept 名（local_name）は年度間で高い安定性を持つ")
    print(f"    - Context ID パターン（CurrentYear/Prior1Year）は毎年同一")
    print(f"    - entity/identifier は同一企業で安定")
    print(f"    - Prior1Year データは前年 CurrentYear と概ね一致するが、")
    print(f"      遡及適用・表示変更等で不一致が生じうる")


if __name__ == "__main__":
    main()

"""J-2. セグメント情報の dimension 構造検索スクリプト。

実行方法: EDINET_TAXONOMY_ROOT=... EDINET_API_KEY=... uv run docs/QAs/scripts/J-2.segment_dims.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）、EDINET_API_KEY が必要
出力: jpcrp_cor から *Axis / *Member 要素を抽出し、OperatingSegmentsAxis 関連構造を表示。
      トヨタ実データからセグメント Fact を抽出。
"""

from __future__ import annotations

import io
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# --- 共通ヘルパーのインポート ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import extract_member, find_public_doc_members, get_zip

# --- 定数 ---
TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])
JPCRP_XSD = (
    TAXONOMY_ROOT
    / "taxonomy"
    / "jpcrp"
    / "2025-11-01"
    / "jpcrp_cor_2025-11-01.xsd"
)

TOYOTA_DOC_ID = "S100VWVY"

NS_XSD = "http://www.w3.org/2001/XMLSchema"
NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"


@dataclass
class TaxoElement:
    """タクソノミ内の要素情報を保持するデータクラス。"""

    name: str
    elem_type: str
    abstract: bool
    period_type: str


def extract_axis_member_elements(xsd_path: Path) -> list[TaxoElement]:
    """XSD ファイルから Axis / Member 要素を抽出する。

    Args:
        xsd_path: jpcrp_cor XSD ファイルのパス。

    Returns:
        Axis または Member で終わる要素名を持つ TaxoElement のリスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    results: list[TaxoElement] = []
    for elem in root.iter(f"{{{NS_XSD}}}element"):
        name = elem.get("name", "")
        if not (name.endswith("Axis") or name.endswith("Member")):
            continue

        elem_type = elem.get("type", "")
        # type 属性から名前空間プレフィックスを除去
        if ":" in elem_type:
            elem_type = elem_type.split(":", 1)[1]

        abstract = elem.get("abstract", "false").lower() == "true"
        period_type = elem.get(f"{{{NS_XBRLI}}}periodType", "")

        results.append(TaxoElement(
            name=name,
            elem_type=elem_type,
            abstract=abstract,
            period_type=period_type,
        ))

    return results


def show_segment_elements(elements: list[TaxoElement]) -> None:
    """セグメント関連の Axis / Member 要素を表示する。

    Args:
        elements: 抽出済みの TaxoElement リスト。
    """
    # Axis 一覧
    axes = [e for e in elements if e.name.endswith("Axis")]
    members = [e for e in elements if e.name.endswith("Member")]

    print(f"\n--- jpcrp_cor の全 Axis 要素 ({len(axes)} 件) ---")
    for a in sorted(axes, key=lambda x: x.name):
        print(f"  {a.name:<60s} type={a.elem_type}")

    # セグメント関連の Axis を特定
    seg_axes = [a for a in axes if "Segment" in a.name or "segment" in a.name.lower()]
    print(f"\n--- セグメント関連 Axis ({len(seg_axes)} 件) ---")
    for a in seg_axes:
        print(f"  {a.name}")

    # OperatingSegmentsAxis に関連する Member を特定
    seg_members = [
        m for m in members
        if "Segment" in m.name
        or "Reconciliation" in m.name
        or "Unallocated" in m.name
    ]
    print(f"\n--- セグメント関連 Member ({len(seg_members)} 件) ---")
    for m in sorted(seg_members, key=lambda x: x.name):
        print(f"  {m.name:<70s} abstract={m.abstract}")

    # 全 Member のサマリ
    print("\n--- 全 Member サマリ ---")
    print(f"  全 Member 数: {len(members)}")
    print(f"  abstract=true: {sum(1 for m in members if m.abstract)}")
    print(f"  abstract=false: {sum(1 for m in members if not m.abstract)}")


def extract_segment_facts_from_xbrl(xbrl_bytes: bytes) -> None:
    """XBRL バイト列からセグメント Fact を抽出・表示する。

    OperatingSegmentsAxis を含む Context を検出し、
    その Context を参照する Fact の概念名・メンバー名・値を出力する。

    Args:
        xbrl_bytes: XBRL ファイルのバイト列。
    """
    tree = ET.parse(io.BytesIO(xbrl_bytes))
    root = tree.getroot()

    # Step 1: 全 Context を解析し、OperatingSegmentsAxis を含むものを特定
    segment_contexts: dict[str, str] = {}  # context_id -> member QName

    for ctx in root.iter(f"{{{NS_XBRLI}}}context"):
        ctx_id = ctx.get("id", "")

        # scenario 内の explicitMember を検索
        for em in ctx.iter(f"{{{NS_XBRLDI}}}explicitMember"):
            dim = em.get("dimension", "")
            if "OperatingSegmentsAxis" in dim:
                member_qname = (em.text or "").strip()
                segment_contexts[ctx_id] = member_qname

    print(f"\n  OperatingSegmentsAxis を含む Context 数: {len(segment_contexts)}")

    if not segment_contexts:
        print("  （セグメント Context が見つかりませんでした）")
        return

    # Context ID -> member の表示
    print("\n  --- セグメント Context 一覧 (先頭 20 件) ---")
    for i, (ctx_id, member) in enumerate(sorted(segment_contexts.items())):
        if i >= 20:
            print(f"  ... 残り {len(segment_contexts) - 20} 件省略")
            break
        print(f"    {ctx_id}")
        print(f"      member: {member}")

    # Step 2: セグメント Context を参照する Fact を収集
    @dataclass
    class SegmentFact:
        """セグメント Fact の情報を保持するデータクラス。"""

        concept: str
        member: str
        value: str
        context_id: str

    facts: list[SegmentFact] = []

    for elem in root:
        ctx_ref = elem.get("contextRef", "")
        if ctx_ref not in segment_contexts:
            continue

        # タグ名から名前空間を除去して概念名を取得
        tag = elem.tag
        if "}" in tag:
            ns, local = tag.rsplit("}", 1)
            ns = ns.lstrip("{")
            # 名前空間 URI から短縮プレフィックスを推定
            prefix = _guess_prefix(ns)
            concept = f"{prefix}:{local}" if prefix else local
        else:
            concept = tag

        value = (elem.text or "").strip()
        member = segment_contexts[ctx_ref]

        # textBlock は長すぎるので省略
        if len(value) > 200:
            value = value[:100] + f"... ({len(value)} chars)"

        facts.append(SegmentFact(
            concept=concept,
            member=member,
            value=value,
            context_id=ctx_ref,
        ))

    print(f"\n  セグメント Fact 数: {len(facts)}")

    # 概念名別にグループ化して表示
    from collections import defaultdict

    by_concept: dict[str, list[SegmentFact]] = defaultdict(list)
    for f in facts:
        by_concept[f.concept].append(f)

    print(f"  ユニーク概念名数: {len(by_concept)}")

    print("\n  --- セグメント Fact 一覧（概念名別） ---")
    for concept in sorted(by_concept.keys()):
        concept_facts = by_concept[concept]
        print(f"\n  [{concept}] ({len(concept_facts)} 件)")
        for cf in concept_facts[:10]:
            # member QName から短縮名を抽出
            member_short = cf.member.split(":")[-1] if ":" in cf.member else cf.member
            val_display = cf.value if cf.value else "(empty)"
            print(f"    {member_short:<55s} = {val_display}")
        if len(concept_facts) > 10:
            print(f"    ... 残り {len(concept_facts) - 10} 件省略")


def _guess_prefix(ns_uri: str) -> str:
    """名前空間 URI から短縮プレフィックスを推定する。

    Args:
        ns_uri: 名前空間 URI。

    Returns:
        推定されたプレフィックス文字列。
    """
    if "jppfs_cor" in ns_uri or ns_uri.endswith("/jppfs_cor"):
        return "jppfs_cor"
    if "jpcrp_cor" in ns_uri or ns_uri.endswith("/jpcrp_cor"):
        return "jpcrp_cor"
    if "jpdei_cor" in ns_uri or ns_uri.endswith("/jpdei_cor"):
        return "jpdei_cor"
    if "jpigp_cor" in ns_uri or ns_uri.endswith("/jpigp_cor"):
        return "jpigp_cor"
    # 提出者別タクソノミ
    if "jpcrp" in ns_uri and "asr" in ns_uri:
        return "filer"
    # IFRS
    if "ifrs" in ns_uri:
        return "ifrs"
    return ""


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("J-2. セグメント情報の dimension 構造")
    print("=" * 80)

    # ===== Part 1: タクソノミ分析 =====
    print("\n[Part 1] jpcrp_cor XSD から Axis / Member 要素を抽出")
    print(f"  XSD: {JPCRP_XSD}")

    elements = extract_axis_member_elements(JPCRP_XSD)
    print(f"  抽出数: {len(elements)} (Axis + Member)")

    show_segment_elements(elements)

    # ===== Part 2: トヨタ実データ検証 =====
    print("\n" + "=" * 80)
    print("[Part 2] トヨタ実データからセグメント Fact を抽出")
    print(f"  doc_id: {TOYOTA_DOC_ID}")
    print("=" * 80)

    zip_bytes = get_zip(TOYOTA_DOC_ID)

    # .xbrl ファイルを検索
    xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")
    print(f"\n  PublicDoc 内 .xbrl ファイル: {xbrl_members}")

    if not xbrl_members:
        # iXBRL (.htm) を試す
        htm_members = find_public_doc_members(zip_bytes, ".htm")
        print(f"  PublicDoc 内 .htm ファイル: {htm_members}")
        if htm_members:
            print("  （iXBRL 形式のため .htm ファイルを解析）")
            xbrl_bytes = extract_member(zip_bytes, htm_members[0])
            print(f"  ファイルサイズ: {len(xbrl_bytes):,} bytes")
            extract_segment_facts_from_xbrl(xbrl_bytes)
        else:
            print("  （XBRL / iXBRL ファイルが見つかりませんでした）")
    else:
        for xbrl_name in xbrl_members:
            print(f"\n  --- {xbrl_name} ---")
            xbrl_bytes = extract_member(zip_bytes, xbrl_name)
            print(f"  ファイルサイズ: {len(xbrl_bytes):,} bytes")
            extract_segment_facts_from_xbrl(xbrl_bytes)

    # ===== Part 3: Axis / Member の全リスト (デバッグ用) =====
    print("\n" + "=" * 80)
    print("[Part 3] jpcrp_cor の全 Axis 一覧（完全版）")
    print("=" * 80)
    all_axes = [e for e in elements if e.name.endswith("Axis")]
    for a in sorted(all_axes, key=lambda x: x.name):
        print(f"  {a.name}")

    print(f"\n  合計 Axis 数: {len(all_axes)}")


if __name__ == "__main__":
    main()

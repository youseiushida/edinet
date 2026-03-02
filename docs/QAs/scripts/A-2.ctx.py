"""A-2 調査スクリプト: サンプル .xbrl から Context 構造を抽出する。

Context ID 命名パターン、Dimension 軸、Period パターンを分析する。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from lxml import etree

SAMPLE_BASE = Path(__file__).resolve().parents[2] / "仕様書" / "2026" / "サンプルインスタンス" / "サンプルインスタンス" / "ダウンロードデータ"

JGAAP_XBRL = SAMPLE_BASE / "02_開示府令-有価証券報告書" / "S002XXXX" / "XBRL" / "PublicDoc" / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12.xbrl"

NS = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "xbrldi": "http://xbrl.org/2006/xbrldi",
}


def analyze_contexts(path: Path) -> None:
    """XBRLファイルのContext構造を分析・表示する。

    Args:
        path: XBRLファイルのパス。
    """
    tree = etree.parse(str(path))
    root = tree.getroot()

    contexts = root.findall(".//xbrli:context", NS)
    print(f"Context 総数: {len(contexts)}")

    # scheme と identifier の分析
    schemes: Counter = Counter()
    identifiers: Counter = Counter()
    period_types: Counter = Counter()
    dimension_axes: Counter = Counter()
    has_segment = 0
    has_scenario = 0

    for ctx in contexts:
        ctx_id = ctx.get("id", "")

        # entity
        identifier = ctx.find("xbrli:entity/xbrli:identifier", NS)
        if identifier is not None:
            schemes[identifier.get("scheme", "")] += 1
            identifiers[identifier.text or ""] += 1

        # segment
        segment = ctx.find("xbrli:entity/xbrli:segment", NS)
        if segment is not None:
            has_segment += 1

        # period
        instant = ctx.find("xbrli:period/xbrli:instant", NS)
        start = ctx.find("xbrli:period/xbrli:startDate", NS)
        forever = ctx.find("xbrli:period/xbrli:forever", NS)
        if instant is not None:
            period_types["instant"] += 1
        elif start is not None:
            period_types["duration"] += 1
        elif forever is not None:
            period_types["forever"] += 1
        else:
            period_types["unknown"] += 1

        # scenario
        scenario = ctx.find("xbrli:scenario", NS)
        if scenario is not None:
            has_scenario += 1
            for member in scenario.findall("xbrldi:explicitMember", NS):
                dim = member.get("dimension", "")
                dimension_axes[dim] += 1

    # 結果表示
    print("\n--- entity ---")
    print("  scheme パターン:")
    for s, c in schemes.most_common():
        print(f"    {s}: {c} 件")
    print("  identifier パターン:")
    for i, c in identifiers.most_common():
        print(f"    {i}: {c} 件")

    print("\n--- segment vs scenario ---")
    print(f"  segment あり: {has_segment} 件")
    print(f"  scenario あり: {has_scenario} 件")

    print("\n--- period タイプ ---")
    for p, c in period_types.most_common():
        print(f"  {p}: {c} 件")

    print("\n--- Dimension 軸 ---")
    for d, c in dimension_axes.most_common():
        print(f"  {d}: {c} 件")

    # Context ID パターンの分析
    print("\n--- Context ID 一覧 (先頭 20 件) ---")
    for ctx in contexts[:20]:
        ctx_id = ctx.get("id", "")
        period_type = "instant" if ctx.find("xbrli:period/xbrli:instant", NS) is not None else "duration"
        scenario = ctx.find("xbrli:scenario", NS)
        dims = []
        if scenario is not None:
            for member in scenario.findall("xbrldi:explicitMember", NS):
                dims.append(f"{member.get('dimension', '')}={member.text or ''}")
        dim_str = ", ".join(dims) if dims else "(なし)"
        print(f"  {ctx_id:60s}  {period_type:8s}  dims={dim_str}")


def main() -> None:
    """メイン処理。"""
    print(f"ファイル: {JGAAP_XBRL.name}")
    if not JGAAP_XBRL.exists():
        print(f"[ERROR] ファイルが存在しません: {JGAAP_XBRL}")
        return
    analyze_contexts(JGAAP_XBRL)


if __name__ == "__main__":
    main()

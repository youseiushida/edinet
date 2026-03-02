"""G-5. jplvh タクソノミの substitutionGroup による Dimension 要素判定検証

既存の G-5.verify_jplvh.py は type 属性で Hypercube/Axis を判定しているが、
XBRL 仕様上は substitutionGroup 属性で判定するのが正しい。
本スクリプトは substitutionGroup を使って正しく判定し、回答 F7 の記述を検証する。

また、サンプルインスタンスにおいて xbrldi:explicitMember が
entity/segment と xbrli:scenario のどちらに配置されているかも検証する。

実行方法:
    EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 \
        uv run docs/QAs/scripts/G-5.verify_subgroup.py

前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: substitutionGroup による分類結果 + サンプルの Dimension 配置場所
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
))

SAMPLE_DIR = Path(
    "docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス"
    "/ダウンロードデータ/18_大量保有府令-大量保有報告書"
)

NS_XSD = {"xs": "http://www.w3.org/2001/XMLSchema"}
NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"


def verify_xsd() -> None:
    """XSD の substitutionGroup 属性で Hypercube/Axis を判定する。"""
    xsd_path = sorted(
        TAXONOMY_ROOT.glob("taxonomy/jplvh/*/jplvh_cor_*.xsd"),
    )[-1]
    print(f"対象XSD: {xsd_path}")

    tree = ET.parse(xsd_path)
    root = tree.getroot()
    elements = root.findall("xs:element", NS_XSD)
    print(f"要素総数: {len(elements)}")

    # substitutionGroup 別に分類
    subgroup_map: dict[str, list[str]] = defaultdict(list)
    type_map: dict[str, list[str]] = defaultdict(list)

    for el in elements:
        name = el.get("name", "")
        sub_group = el.get("substitutionGroup", "")
        el_type = el.get("type", "")
        type_short = el_type.split(":")[-1] if ":" in el_type else el_type

        if sub_group:
            subgroup_map[sub_group].append(name)
        type_map[type_short].append(name)

    # Hypercube (substitutionGroup="xbrldt:hypercubeItem")
    print(f"\n=== substitutionGroup による Dimension 要素分類 ===")

    hypercube = subgroup_map.get("xbrldt:hypercubeItem", [])
    print(f"\nHypercube (substitutionGroup=xbrldt:hypercubeItem): {len(hypercube)} 個")
    for h in hypercube:
        print(f"  - {h}")

    # Axis (substitutionGroup="xbrldt:dimensionItem")
    axis = subgroup_map.get("xbrldt:dimensionItem", [])
    print(f"\nAxis (substitutionGroup=xbrldt:dimensionItem): {len(axis)} 個")
    for a in axis:
        print(f"  - {a}")

    # Domain/Member (type による分類: domainItemType)
    domain = type_map.get("domainItemType", [])
    print(f"\nDomain/Member (type=domainItemType): {len(domain)} 個")
    for d in domain:
        print(f"  - {d}")

    # 比較: type 属性での分類（既存スクリプト G-5.verify_jplvh.py の方式）
    print(f"\n=== 参考: type 属性での分類（既存スクリプトの方式） ===")
    hypercube_by_type = type_map.get("hypercubeItem", [])
    dimension_by_type = type_map.get("dimensionItem", [])
    print(f"type=hypercubeItem: {len(hypercube_by_type)} 個")
    print(f"type=dimensionItem: {len(dimension_by_type)} 個")

    # 差分
    print(f"\n=== 判定方法の差分 ===")
    if set(hypercube) == set(hypercube_by_type):
        print(f"Hypercube: 両方式で結果一致 ({len(hypercube)} 個)")
    else:
        print(f"Hypercube: 差分あり!")
        print(f"  substitutionGroup のみ: {set(hypercube) - set(hypercube_by_type)}")
        print(f"  type のみ: {set(hypercube_by_type) - set(hypercube)}")

    if set(axis) == set(dimension_by_type):
        print(f"Axis: 両方式で結果一致 ({len(axis)} 個)")
    else:
        print(f"Axis: 差分あり!")
        print(f"  substitutionGroup のみ: {set(axis) - set(dimension_by_type)}")
        print(f"  type のみ: {set(dimension_by_type) - set(axis)}")

    # G-5.a.md F7 との照合
    print(f"\n=== G-5.a.md F7 との照合 ===")
    print(f"回答 F7: Hypercube=5 → 実際={len(hypercube)}")
    print(f"回答 F7: Axis=1 → 実際={len(axis)}")
    print(f"回答 F7: Domain/Member=3 → 実際={len(domain)}")


def verify_sample_dimension_placement() -> None:
    """サンプルインスタンスで Dimension が segment/scenario のどちらにあるか確認。"""
    print(f"\n\n{'=' * 70}")
    print(f"=== サンプルインスタンスの Dimension 配置場所検証 ===")
    print(f"{'=' * 70}")

    if not SAMPLE_DIR.exists():
        print(f"サンプルディレクトリなし: {SAMPLE_DIR}")
        return

    xbrl_files = sorted(SAMPLE_DIR.rglob("*.xbrl"))
    print(f"検出 .xbrl ファイル: {len(xbrl_files)} 個")

    for xbrl_path in xbrl_files:
        print(f"\n--- {xbrl_path.name} ---")

        tree = ET.parse(xbrl_path)
        root = tree.getroot()

        segment_dims: list[str] = []
        scenario_dims: list[str] = []

        for ctx in root.iter(f"{{{NS_XBRLI}}}context"):
            ctx_id = ctx.get("id", "")

            # entity/segment 内を検索
            entity = ctx.find(f"{{{NS_XBRLI}}}entity")
            if entity is not None:
                segment = entity.find(f"{{{NS_XBRLI}}}segment")
                if segment is not None:
                    for member in segment.iter(f"{{{NS_XBRLDI}}}explicitMember"):
                        dim = member.get("dimension", "")
                        val = member.text or ""
                        segment_dims.append(
                            f"  ctx={ctx_id}: {dim}={val}"
                        )

            # scenario 内を検索
            scenario = ctx.find(f"{{{NS_XBRLI}}}scenario")
            if scenario is not None:
                for member in scenario.iter(f"{{{NS_XBRLDI}}}explicitMember"):
                    dim = member.get("dimension", "")
                    val = member.text or ""
                    scenario_dims.append(
                        f"  ctx={ctx_id}: {dim}={val}"
                    )

        print(f"  entity/segment 内の explicitMember: {len(segment_dims)} 個")
        for s in segment_dims[:5]:
            print(f"    {s}")
        if len(segment_dims) > 5:
            print(f"    ... (他 {len(segment_dims) - 5} 個)")

        print(f"  xbrli:scenario 内の explicitMember: {len(scenario_dims)} 個")
        for s in scenario_dims[:5]:
            print(f"    {s}")
        if len(scenario_dims) > 5:
            print(f"    ... (他 {len(scenario_dims) - 5} 個)")

        # 判定
        if scenario_dims and not segment_dims:
            print(f"  → Dimension は scenario に配置（回答 F8 と一致）")
        elif segment_dims and not scenario_dims:
            print(f"  → Dimension は segment に配置（回答 F8 と不一致!）")
        elif segment_dims and scenario_dims:
            print(f"  → Dimension は segment と scenario の両方に存在")
        else:
            print(f"  → Dimension なし")

    print(f"\n=== 検証結論 ===")
    print(
        "既存 G-5.jplvh_sample.py は entity/segment のみ検索しており、"
        "scenario 内の Dimension を見逃す可能性がある。"
    )
    print(
        "本スクリプトで segment/scenario の両方を検索し、"
        "実際の配置場所を確認した。"
    )


def main() -> None:
    """メイン処理。"""
    print("G-5: jplvh substitutionGroup 検証 + Dimension 配置検証")
    print("=" * 70)

    verify_xsd()
    verify_sample_dimension_placement()


if __name__ == "__main__":
    main()

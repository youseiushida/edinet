"""H-9. タクソノミの規模感 — concept数/label数/arc数/Fact数のカウントスクリプト

実行方法: uv run docs/QAs/scripts/H-9.taxonomy_scale.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: タクソノミの各種統計（concept数、ラベル数、arc数等）
"""

import os
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

TAXONOMY_ROOT = Path(
    os.environ.get("EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101")
)

# 名前空間定義
NS = {
    "xs": "http://www.w3.org/2001/XMLSchema",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
    "label": "http://www.xbrl.org/2003/linkbase",
}


def count_concepts(taxonomy_dir: Path) -> dict[str, int]:
    """各モジュールの XSD から concept 数をカウントする。

    Args:
        taxonomy_dir: タクソノミルートの taxonomy/ ディレクトリ

    Returns:
        モジュール名 → concept数 の辞書
    """
    counts: dict[str, int] = {}
    # _cor_*.xsd パターンに一致するファイルを検索
    for xsd in sorted(taxonomy_dir.rglob("*_cor*.xsd")):
        module_name = xsd.parent.parent.name  # e.g., jppfs, jpcrp
        try:
            tree = ET.parse(xsd)
            root = tree.getroot()
            # xs:element がconcept定義
            elements = root.findall(".//{http://www.w3.org/2001/XMLSchema}element")
            concept_count = len(elements)
            if concept_count > 0:
                key = f"{module_name}/{xsd.name}"
                counts[key] = concept_count
        except ET.ParseError as e:
            print(f"  WARN: パースエラー {xsd}: {e}", file=sys.stderr)
    return counts


def count_labels(taxonomy_dir: Path) -> dict[str, dict[str, int]]:
    """ラベルリンクベースからラベル数をカウントする。

    Args:
        taxonomy_dir: タクソノミルートの taxonomy/ ディレクトリ

    Returns:
        言語 → {ファイル名 → ラベル数} の辞書
    """
    result: dict[str, dict[str, int]] = {"ja": {}, "en": {}}
    for lab_file in sorted(taxonomy_dir.rglob("*_lab.xml")):
        try:
            tree = ET.parse(lab_file)
            root = tree.getroot()
            labels = root.findall(".//{http://www.xbrl.org/2003/linkbase}label")
            if labels:
                module = lab_file.parent.parent.parent.name
                result["ja"][f"{module}/{lab_file.name}"] = len(labels)
        except ET.ParseError:
            pass

    for lab_file in sorted(taxonomy_dir.rglob("*_lab-en.xml")):
        try:
            tree = ET.parse(lab_file)
            root = tree.getroot()
            labels = root.findall(".//{http://www.xbrl.org/2003/linkbase}label")
            if labels:
                module = lab_file.parent.parent.parent.name
                result["en"][f"{module}/{lab_file.name}"] = len(labels)
        except ET.ParseError:
            pass

    return result


def count_arcs(taxonomy_dir: Path) -> dict[str, dict[str, int]]:
    """リンクベースの arc 数をカウントする。

    Args:
        taxonomy_dir: タクソノミルートの taxonomy/ ディレクトリ

    Returns:
        リンクベース種別 → {ファイル名 → arc数} の辞書
    """
    result: dict[str, dict[str, int]] = {
        "pre": {},  # presentationArc
        "cal": {},  # calculationArc
        "def": {},  # definitionArc
    }

    arc_tags = {
        "pre": "{http://www.xbrl.org/2003/linkbase}presentationArc",
        "cal": "{http://www.xbrl.org/2003/linkbase}calculationArc",
        "def": "{http://www.xbrl.org/2003/linkbase}definitionArc",
    }

    patterns = {
        "pre": "*_pre*.xml",
        "cal": "*_cal*.xml",
        "def": "*_def*.xml",
    }

    for link_type, pattern in patterns.items():
        for xml_file in sorted(taxonomy_dir.rglob(pattern)):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                arcs = root.findall(f".//{arc_tags[link_type]}")
                if arcs:
                    module = xml_file.parent.parent.parent.name
                    result[link_type][f"{module}/{xml_file.name}"] = len(arcs)
            except ET.ParseError:
                pass

    return result


def count_facts_in_sample() -> dict[str, int]:
    """サンプルインスタンスの Fact 数をカウントする。

    Returns:
        ファイル名 → Fact数 の辞書
    """
    sample_dir = Path(
        "docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ"
    )
    if not sample_dir.exists():
        return {}

    result: dict[str, int] = {}
    # XBRL 非メタ要素 = Fact
    meta_ns = {
        "http://www.xbrl.org/2003/instance",  # xbrli:context, xbrli:unit
        "http://www.xbrl.org/2003/linkbase",  # link:schemaRef, link:roleRef
    }

    for xbrl_file in sorted(sample_dir.rglob("PublicDoc/*.xbrl")):
        try:
            tree = ET.parse(xbrl_file)
            root = tree.getroot()
            fact_count = 0
            for child in root:
                # 名前空間がメタ要素でないものは Fact
                ns = child.tag.split("}")[0].lstrip("{") if "}" in child.tag else ""
                if ns not in meta_ns:
                    fact_count += 1
            if fact_count > 0:
                # ディレクトリ名から書類種別を取得
                doc_type = xbrl_file.parts[-5]  # e.g., "02_開示府令-有価証券報告書"
                result[f"{doc_type}/{xbrl_file.name}"] = fact_count
        except ET.ParseError:
            pass

    return result


def main() -> None:
    """タクソノミの規模感を調査する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"
    if not taxonomy_dir.exists():
        print(f"ERROR: {taxonomy_dir} が見つかりません")
        return

    # 1. Concept 数
    print("=== Concept 数（_cor*.xsd の xs:element 数）===")
    concepts = count_concepts(taxonomy_dir)
    total_concepts = 0
    by_module: dict[str, int] = defaultdict(int)
    for key, count in sorted(concepts.items(), key=lambda x: -x[1]):
        module = key.split("/")[0]
        by_module[module] += count
        total_concepts += count
        if count >= 100:
            print(f"  {key}: {count:,}")
    print(f"\nモジュール別合計:")
    for module, count in sorted(by_module.items(), key=lambda x: -x[1]):
        print(f"  {module}: {count:,}")
    print(f"  --- 全合計: {total_concepts:,}")

    # 2. ラベル数
    print("\n=== ラベル数 ===")
    labels = count_labels(taxonomy_dir)
    total_ja = sum(labels["ja"].values())
    total_en = sum(labels["en"].values())
    print(f"日本語ラベル合計: {total_ja:,}")
    for key, count in sorted(labels["ja"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {key}: {count:,}")
    print(f"英語ラベル合計: {total_en:,}")
    for key, count in sorted(labels["en"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {key}: {count:,}")
    print(f"ラベル総数（日英合計）: {total_ja + total_en:,}")

    # 3. Arc 数
    print("\n=== Arc 数 ===")
    arcs = count_arcs(taxonomy_dir)
    for link_type in ["pre", "cal", "def"]:
        total = sum(arcs[link_type].values())
        print(f"\n{link_type}（{['Presentation', 'Calculation', 'Definition'][['pre', 'cal', 'def'].index(link_type)]}）合計: {total:,}")
        for key, count in sorted(arcs[link_type].items(), key=lambda x: -x[1])[:5]:
            print(f"  {key}: {count:,}")

    # 4. サンプルの Fact 数
    print("\n=== サンプルインスタンスの Fact 数 ===")
    facts = count_facts_in_sample()
    if facts:
        for key, count in sorted(facts.items()):
            print(f"  {key}: {count:,}")
    else:
        print("  （サンプルデータなし）")

    # 5. メモリ見積もり
    print("\n=== メモリ見積もり（概算）===")
    print(f"  Concept 数: {total_concepts:,} → 辞書エントリ約 {total_concepts * 200 / 1024 / 1024:.1f} MB")
    print(f"  ラベル数: {total_ja + total_en:,} → 文字列辞書約 {(total_ja + total_en) * 300 / 1024 / 1024:.1f} MB")
    total_arcs = sum(sum(d.values()) for d in arcs.values())
    print(f"  Arc 数: {total_arcs:,} → ツリー構造約 {total_arcs * 100 / 1024 / 1024:.1f} MB")
    total_mem = (total_concepts * 200 + (total_ja + total_en) * 300 + total_arcs * 100) / 1024 / 1024
    print(f"  合計見積もり: 約 {total_mem:.0f} MB（全タクソノミをオンメモリ）")


if __name__ == "__main__":
    main()

"""G-8. jpsps タクソノミ XSD 要素型分類スクリプト

実行方法: uv run docs/QAs/scripts/G-8.jpsps_analysis.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要
出力: jpsps_cor XSD 内の全要素を型別に分類した結果
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

# タクソノミルート
TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
))


def find_xsd(prefix: str) -> Path | None:
    """タクソノミプレフィックスから _cor XSD ファイルを検索する。

    Args:
        prefix: タクソノミプレフィックス（例: "jpsps"）。

    Returns:
        見つかった XSD ファイルのパス。見つからなければ None。
    """
    pattern = f"taxonomy/{prefix}/*/{prefix}_cor_*.xsd"
    matches = sorted(TAXONOMY_ROOT.glob(pattern))
    return matches[-1] if matches else None


def analyze_xsd(xsd_path: Path, label: str) -> dict[str, list[str]]:
    """XSD ファイル内の全要素を型別に分類する。

    Args:
        xsd_path: 解析対象の XSD ファイルパス。
        label: 表示用ラベル。

    Returns:
        型名 -> 要素名リストの辞書。
    """
    print(f"\n{'=' * 70}")
    print(f"{label}: {xsd_path.name}")
    print(f"{'=' * 70}")

    tree = ET.parse(xsd_path)
    root = tree.getroot()

    ns = {"xs": "http://www.w3.org/2001/XMLSchema"}

    # 全 element 定義を取得
    elements = root.findall("xs:element", ns)
    print(f"要素総数: {len(elements)}")

    type_map: dict[str, list[str]] = defaultdict(list)
    abstract_count = 0
    substitution_groups: Counter[str] = Counter()

    for el in elements:
        name = el.get("name", "")
        el_type = el.get("type", "")
        abstract = el.get("abstract", "false") == "true"
        subst = el.get("substitutionGroup", "")

        if abstract:
            abstract_count += 1

        # 型名の簡略化（名前空間プレフィックスを除去）
        type_short = el_type.split(":")[-1] if ":" in el_type else el_type

        type_map[type_short].append(name)
        if subst:
            substitution_groups[subst.split(":")[-1]] += 1

    # 型別サマリー
    print(f"\n--- 型別分類 ---")
    for type_name, names in sorted(type_map.items(), key=lambda x: -len(x[1])):
        print(f"\n  [{type_name}] ({len(names)} 要素)")
        # 最初の5つと最後の2つを表示
        if len(names) <= 8:
            for n in names:
                print(f"    - {n}")
        else:
            for n in names[:5]:
                print(f"    - {n}")
            print(f"    ... ({len(names) - 7} 要素省略)")
            for n in names[-2:]:
                print(f"    - {n}")

    # 数値型の有無チェック
    numeric_types = {
        "monetaryItemType", "sharesItemType", "percentItemType",
        "perShareItemType", "decimalItemType", "integerItemType",
        "nonNegativeIntegerItemType",
    }
    print(f"\n--- 数値型チェック ---")
    found_numeric = False
    for nt in sorted(numeric_types):
        if nt in type_map:
            print(f"  {nt}: {len(type_map[nt])} 要素 ← ★数値型あり")
            found_numeric = True
        else:
            print(f"  {nt}: 0 要素")

    if not found_numeric:
        print(f"\n  → 数値型要素なし。テキストブロック/文字列中心のタクソノミ。")

    # Dimension 関連チェック
    dim_types = {"hypercubeItem", "dimensionItem", "domainItemType"}
    print(f"\n--- Dimension 関連チェック ---")
    found_dim = False
    for dt in sorted(dim_types):
        if dt in type_map:
            print(f"  {dt}: {len(type_map[dt])} 要素 ← ★Dimension あり")
            for n in type_map[dt]:
                print(f"    - {n}")
            found_dim = True
        else:
            print(f"  {dt}: 0 要素")

    if not found_dim:
        print(f"\n  → Dimension 構造なし。")

    # substitutionGroup 統計
    print(f"\n--- substitutionGroup 統計 ---")
    for sg, count in substitution_groups.most_common():
        print(f"  {sg}: {count}")

    # abstract 統計
    print(f"\n--- abstract 統計 ---")
    print(f"  abstract=true: {abstract_count}")
    print(f"  abstract=false (concrete): {len(elements) - abstract_count}")

    return dict(type_map)


def main() -> None:
    """メイン処理。"""
    print("G-8: タクソノミ XSD 要素型分類")
    print("=" * 70)

    # 分析対象
    targets = [
        ("jpsps", "特定有価証券開示府令 (jpsps)"),
        ("jpsps-esr", "特定有価証券 臨時報告書 (jpsps-esr)"),
        ("jpsps-sbr", "特定有価証券 自己株券買付状況報告書 (jpsps-sbr)"),
    ]

    results: dict[str, dict[str, list[str]]] = {}
    for prefix, label in targets:
        xsd_path = find_xsd(prefix)
        if xsd_path:
            results[prefix] = analyze_xsd(xsd_path, label)
        else:
            print(f"\n[SKIP] {label}: XSD が見つかりません")

    # 横断比較
    print(f"\n\n{'=' * 70}")
    print("横断比較サマリー")
    print(f"{'=' * 70}")

    print(f"\n{'タクソノミ':<20s} {'要素数':>6s} {'textBlock':>10s} "
          f"{'monetary':>10s} {'shares':>8s} {'percent':>9s} {'Dim':>5s}")
    print("-" * 70)

    for prefix, label in targets:
        if prefix not in results:
            continue
        tm = results[prefix]
        total = sum(len(v) for v in tm.values())
        tb = len(tm.get("textBlockItemType", []))
        mn = len(tm.get("monetaryItemType", []))
        sh = len(tm.get("sharesItemType", []))
        pc = len(tm.get("percentItemType", []))
        dim = (
            len(tm.get("hypercubeItem", []))
            + len(tm.get("dimensionItem", []))
            + len(tm.get("domainItemType", []))
        )
        print(f"  {prefix:<18s} {total:>6d} {tb:>10d} {mn:>10d} {sh:>8d} {pc:>9d} {dim:>5d}")


if __name__ == "__main__":
    main()

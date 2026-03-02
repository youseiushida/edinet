"""E-7. 主要勘定科目 concept 名辞書 — jppfs_cor から抽出するスクリプト

実行方法: uv run docs/QAs/scripts/E-7.concept_dict.py
前提: EDINET_TAXONOMY_ROOT 環境変数が必要
      （例: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: 主要勘定科目の concept 名、periodType、データ型の辞書
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# タクソノミルートの取得
_raw_root = os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
)
# WSL 環境ではバックスラッシュのパスを変換
if _raw_root.startswith("C:"):
    _raw_root = "/mnt/c" + _raw_root[2:].replace("\\", "/")
TAXONOMY_ROOT = Path(_raw_root)

# 対象ファイルパス
JPPFS_XSD = TAXONOMY_ROOT / "taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd"
JPPFS_LAB = TAXONOMY_ROOT / "taxonomy/jppfs/2025-11-01/label/jppfs_2025-11-01_lab.xml"
JPPFS_LAB_EN = TAXONOMY_ROOT / "taxonomy/jppfs/2025-11-01/label/jppfs_2025-11-01_lab-en.xml"

# 主要勘定科目の検索対象ラベル（日本語）
TARGET_LABELS_BS = [
    "流動資産合計",
    "流動資産",
    "固定資産合計",
    "固定資産",
    "資産合計",
    "資産",
    "流動負債合計",
    "流動負債",
    "固定負債合計",
    "固定負債",
    "負債合計",
    "負債",
    "純資産合計",
    "純資産",
    "資本金",
    "利益剰余金",
]

TARGET_LABELS_PL = [
    "売上高",
    "売上原価",
    "売上総利益",
    "売上総利益又は売上総損失",
    "販売費及び一般管理費",
    "販売費及び一般管理費合計",
    "営業利益",
    "営業利益又は営業損失",
    "経常利益",
    "経常利益又は経常損失",
    "税引前当期純利益",
    "税金等調整前当期純利益",
    "税金等調整前当期純利益又は税金等調整前当期純損失",
    "当期純利益",
    "当期純利益又は当期純損失",
    "親会社株主に帰属する当期純利益",
    "親会社株主に帰属する当期純利益又は親会社株主に帰属する当期純損失",
]

TARGET_LABELS_CF = [
    "営業活動によるキャッシュ・フロー",
    "投資活動によるキャッシュ・フロー",
    "財務活動によるキャッシュ・フロー",
    "現金及び現金同等物の期末残高",
    "現金及び現金同等物に係る換算差額",
    "現金及び現金同等物の増減額",
    "現金及び現金同等物の増減額（△は減少）",
    "現金及び現金同等物の期首残高",
]

TARGET_LABELS_SS = [
    "資本金",
    "資本剰余金",
    "資本剰余金合計",
    "利益剰余金",
    "利益剰余金合計",
    "自己株式",
    "株主資本合計",
    "株主資本",
    "その他の包括利益累計額合計",
    "新株予約権",
    "非支配株主持分",
    "純資産合計",
]

ALL_TARGETS = (
    TARGET_LABELS_BS + TARGET_LABELS_PL +
    TARGET_LABELS_CF + TARGET_LABELS_SS
)


def parse_xsd_elements(xsd_path: Path) -> dict[str, dict]:
    """XSD から全 element 定義を抽出する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        要素名 -> 属性辞書のマッピング。
    """
    print(f"\n[XSD 解析] {xsd_path}")
    text = xsd_path.read_text(encoding="utf-8-sig")
    elements: dict[str, dict] = {}

    for m in re.finditer(
        r'<(?:xs:|xsd:)?element\b([^>]*?)(?:/>|>)',
        text,
        re.IGNORECASE,
    ):
        attrs_str = m.group(1)
        attrs = {}
        for attr_m in re.finditer(
            r'([\w:]+)\s*=\s*"([^"]*)"',
            attrs_str,
        ):
            attrs[attr_m.group(1)] = attr_m.group(2)

        name = attrs.get("name")
        if name:
            elements[name] = {
                "name": name,
                "type": attrs.get("type", ""),
                "periodType": attrs.get("xbrli:periodType", ""),
                "balance": attrs.get("xbrli:balance", ""),
                "abstract": attrs.get("abstract", "false"),
                "nillable": attrs.get("nillable", ""),
                "substitutionGroup": attrs.get("substitutionGroup", ""),
            }

    print(f"  要素数: {len(elements)}")
    abstract_count = sum(
        1 for e in elements.values() if e["abstract"] == "true"
    )
    print(f"  うち abstract: {abstract_count}")

    # periodType の分布
    period_dist: dict[str, int] = {}
    for e in elements.values():
        p = e["periodType"] or "(なし)"
        period_dist[p] = period_dist.get(p, 0) + 1
    print(f"  periodType 分布: {period_dist}")

    # type の分布
    type_dist: dict[str, int] = {}
    for e in elements.values():
        t = e["type"] or "(なし)"
        type_dist[t] = type_dist.get(t, 0) + 1
    print(f"  type 分布 (上位10):")
    for t, c in sorted(type_dist.items(), key=lambda x: -x[1])[:10]:
        print(f"    {t}: {c}")

    return elements


def parse_labels(lab_path: Path) -> dict[str, dict[str, str]]:
    """ラベルファイルを解析する。

    ラベルファイルの構造:
    - link:loc: xlink:label="Assets" xlink:href="...#jppfs_cor_Assets"
    - link:labelArc: xlink:from="Assets" xlink:to="label_Assets"
    - link:label: xlink:label="label_Assets" xlink:role="...role/label" >資産</link:label>

    loc の xlink:label が labelArc の from と一致し、loc の href の
    フラグメント部分が XSD の要素名（プレフィックス付き）に対応する。
    戻り値のキーは XSD の name 属性に合わせるため、プレフィックスを除去する。

    Args:
        lab_path: ラベルファイルのパス。

    Returns:
        要素名 -> {role_short: label_text} の辞書。
    """
    print(f"\n[ラベル解析] {lab_path}")
    text = lab_path.read_text(encoding="utf-8-sig")

    # loc 要素: xlink:label → href フラグメント（プレフィックス付き concept 名）
    loc_map: dict[str, str] = {}
    for m in re.finditer(
        r'<link:loc\b[^>]*?xlink:href="[^"]*#([^"]*)"[^>]*?'
        r'xlink:label="([^"]*)"',
        text,
    ):
        loc_map[m.group(2)] = m.group(1)
    for m in re.finditer(
        r'<link:loc\b[^>]*?xlink:label="([^"]*)"[^>]*?'
        r'xlink:href="[^"]*#([^"]*)"',
        text,
    ):
        loc_map[m.group(1)] = m.group(2)

    # labelArc: from → to のリスト
    arcs: list[tuple[str, str]] = []
    for m in re.finditer(
        r'<link:labelArc\b[^>]*?xlink:from="([^"]*)"[^>]*?'
        r'xlink:to="([^"]*)"',
        text,
    ):
        arcs.append((m.group(1), m.group(2)))
    for m in re.finditer(
        r'<link:labelArc\b[^>]*?xlink:to="([^"]*)"[^>]*?'
        r'xlink:from="([^"]*)"',
        text,
    ):
        arcs.append((m.group(2), m.group(1)))

    # label 要素: xlink:label → (role, text)
    label_data: dict[str, tuple[str, str]] = {}
    for m in re.finditer(
        r'<link:label\b[^>]*?xlink:label="([^"]*)"[^>]*?'
        r'xlink:role="([^"]*)"[^>]*?>([^<]*)</link:label>',
        text,
    ):
        label_data[m.group(1)] = (m.group(2), m.group(3).strip())

    # 統合: concept名（プレフィックスを除去）→ {role_short: label_text}
    labels: dict[str, dict[str, str]] = {}
    for from_id, to_id in arcs:
        href_concept = loc_map.get(from_id, "")
        if not href_concept:
            continue
        # プレフィックス (jppfs_cor_ 等) を除去して XSD の name に合わせる
        concept = re.sub(r"^[a-z]+_[a-z]+_", "", href_concept)

        if to_id in label_data:
            role_uri, text_val = label_data[to_id]
            # role URI を短縮
            role_tail = role_uri.rsplit("/", 1)[-1] if "/" in role_uri else role_uri
            if role_tail == "label":
                role_short = "standard"
            elif role_tail == "verboseLabel":
                role_short = "verbose"
            elif role_tail == "totalLabel":
                role_short = "total"
            elif role_tail == "negativeLabel":
                role_short = "negative"
            elif role_tail == "positiveLabel":
                role_short = "positive"
            elif role_tail == "documentationLabel":
                role_short = "documentation"
            elif role_tail == "periodStartLabel":
                role_short = "periodStart"
            elif role_tail == "periodEndLabel":
                role_short = "periodEnd"
            else:
                role_short = role_tail

            if concept not in labels:
                labels[concept] = {}
            # standard ラベルは上書きしない（最初のマッチを採用）
            if role_short not in labels[concept]:
                labels[concept][role_short] = text_val

    print(f"  ラベル付き要素数: {len(labels)}")
    return labels


def build_reverse_lookup(
    labels: dict[str, dict[str, str]],
) -> dict[str, str]:
    """日本語ラベル → concept 名の逆引き辞書を構築する。

    standard, verbose, total の全ラベルを逆引き対象とする。
    同一ラベルが複数の concept に使われる場合は先勝ち。

    Args:
        labels: 要素名 -> ラベル辞書。

    Returns:
        日本語ラベル -> 要素名の辞書。
    """
    reverse: dict[str, str] = {}
    for concept, role_labels in labels.items():
        for role, text in role_labels.items():
            if role in ("standard", "verbose", "total"):
                if text not in reverse:
                    reverse[text] = concept
    return reverse


def main() -> None:
    """メイン処理。"""
    print("E-7: 主要勘定科目 concept 名辞書")
    print("=" * 70)

    if not JPPFS_XSD.exists():
        print(f"ERROR: XSD ファイルが見つかりません: {JPPFS_XSD}")
        print("EDINET_TAXONOMY_ROOT 環境変数を確認してください")
        return

    # XSD パース
    elements = parse_xsd_elements(JPPFS_XSD)

    # 日本語ラベルパース
    labels_ja = parse_labels(JPPFS_LAB)

    # 英語ラベルパース
    labels_en = {}
    if JPPFS_LAB_EN.exists():
        labels_en = parse_labels(JPPFS_LAB_EN)

    # 逆引き辞書
    reverse = build_reverse_lookup(labels_ja)

    # 主要勘定科目の検索
    print(f"\n{'#' * 70}")
    print("=== 主要勘定科目辞書 ===")
    print(f"{'#' * 70}")

    # BS
    print(f"\n--- BS（貸借対照表）---")
    print(f"{'ラベル':<40s} {'concept名':<50s} {'periodType':<10s} "
          f"{'balance':<8s} {'type'}")
    print("-" * 140)
    for label in TARGET_LABELS_BS:
        concept = reverse.get(label, "")
        if concept and concept in elements:
            e = elements[concept]
            en_label = labels_en.get(concept, {}).get("standard", "")
            print(f"{label:<40s} {concept:<50s} {e['periodType']:<10s} "
                  f"{e['balance']:<8s} {e['type']}")
            if en_label:
                print(f"  EN: {en_label}")
        else:
            # 部分一致で検索
            candidates = [
                (l, c) for l, c in reverse.items()
                if label in l
            ]
            if candidates:
                print(f"{label:<40s} (完全一致なし、候補:)")
                for cl, cc in candidates[:3]:
                    if cc in elements:
                        e = elements[cc]
                        print(f"  → {cl}: {cc} "
                              f"period={e['periodType']} "
                              f"balance={e['balance']}")
            else:
                print(f"{label:<40s} (見つからない)")

    # PL
    print(f"\n--- PL（損益計算書）---")
    print(f"{'ラベル':<40s} {'concept名':<50s} {'periodType':<10s} "
          f"{'balance':<8s} {'type'}")
    print("-" * 140)
    for label in TARGET_LABELS_PL:
        concept = reverse.get(label, "")
        if concept and concept in elements:
            e = elements[concept]
            en_label = labels_en.get(concept, {}).get("standard", "")
            print(f"{label:<40s} {concept:<50s} {e['periodType']:<10s} "
                  f"{e['balance']:<8s} {e['type']}")
            if en_label:
                print(f"  EN: {en_label}")
        else:
            candidates = [
                (l, c) for l, c in reverse.items()
                if label in l
            ]
            if candidates:
                print(f"{label:<40s} (完全一致なし、候補:)")
                for cl, cc in candidates[:3]:
                    if cc in elements:
                        e = elements[cc]
                        print(f"  → {cl}: {cc} "
                              f"period={e['periodType']} "
                              f"balance={e['balance']}")
            else:
                print(f"{label:<40s} (見つからない)")

    # CF
    print(f"\n--- CF（キャッシュフロー計算書）---")
    print(f"{'ラベル':<40s} {'concept名':<50s} {'periodType':<10s} "
          f"{'balance':<8s} {'type'}")
    print("-" * 140)
    for label in TARGET_LABELS_CF:
        concept = reverse.get(label, "")
        if concept and concept in elements:
            e = elements[concept]
            en_label = labels_en.get(concept, {}).get("standard", "")
            print(f"{label:<40s} {concept:<50s} {e['periodType']:<10s} "
                  f"{e['balance']:<8s} {e['type']}")
            if en_label:
                print(f"  EN: {en_label}")
        else:
            candidates = [
                (l, c) for l, c in reverse.items()
                if label in l
            ]
            if candidates:
                print(f"{label:<40s} (完全一致なし、候補:)")
                for cl, cc in candidates[:3]:
                    if cc in elements:
                        e = elements[cc]
                        print(f"  → {cl}: {cc} "
                              f"period={e['periodType']} "
                              f"balance={e['balance']}")
            else:
                print(f"{label:<40s} (見つからない)")

    # SS
    print(f"\n--- SS（株主資本等変動計算書）---")
    print(f"{'ラベル':<40s} {'concept名':<50s} {'periodType':<10s} "
          f"{'balance':<8s} {'type'}")
    print("-" * 140)
    for label in TARGET_LABELS_SS:
        concept = reverse.get(label, "")
        if concept and concept in elements:
            e = elements[concept]
            en_label = labels_en.get(concept, {}).get("standard", "")
            print(f"{label:<40s} {concept:<50s} {e['periodType']:<10s} "
                  f"{e['balance']:<8s} {e['type']}")
            if en_label:
                print(f"  EN: {en_label}")
        else:
            candidates = [
                (l, c) for l, c in reverse.items()
                if label in l
            ]
            if candidates:
                print(f"{label:<40s} (完全一致なし、候補:)")
                for cl, cc in candidates[:3]:
                    if cc in elements:
                        e = elements[cc]
                        print(f"  → {cl}: {cc} "
                              f"period={e['periodType']} "
                              f"balance={e['balance']}")
            else:
                print(f"{label:<40s} (見つからない)")

    # 全要素の periodType 別集計
    print(f"\n{'#' * 70}")
    print("=== 統計情報 ===")
    print(f"{'#' * 70}")

    # balance 別集計
    balance_dist: dict[str, int] = {}
    for e in elements.values():
        b = e["balance"] or "(なし)"
        balance_dist[b] = balance_dist.get(b, 0) + 1
    print(f"\nbalance 分布: {balance_dist}")

    # substitutionGroup 別集計
    sg_dist: dict[str, int] = {}
    for e in elements.values():
        sg = e["substitutionGroup"] or "(なし)"
        sg_dist[sg] = sg_dist.get(sg, 0) + 1
    print(f"substitutionGroup 分布: {sg_dist}")

    print(f"\n{'=' * 70}")
    print("E-7 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

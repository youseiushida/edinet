"""J-3. 注記テキストの concept 検索スクリプト。

実行方法: EDINET_TAXONOMY_ROOT=... EDINET_API_KEY=... uv run docs/QAs/scripts/J-3.note_concepts.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）、EDINET_API_KEY が必要
出力: jppfs_cor と jpcrp_cor から textBlockItemType の element を抽出・分類。
      実ファイルから textBlock Fact のサンプルを表示。
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "xbrli": "http://www.xbrl.org/2003/instance",
}

JPPFS_COR = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "jppfs_cor_2025-11-01.xsd"
JPCRP_COR = TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01" / "jpcrp_cor_2025-11-01.xsd"


@dataclass
class TextBlockConcept:
    """textBlockItemType の element 情報を保持するデータクラス。"""

    name: str
    element_id: str
    xbrl_type: str
    abstract: bool
    period_type: str
    source_ns: str


def parse_textblock_concepts(xsd_path: Path, source_ns: str) -> list[TextBlockConcept]:
    """XSD ファイルから textBlockItemType の element を抽出する。

    Args:
        xsd_path: XSD ファイルのパス。
        source_ns: ソース名前空間の識別名（例: "jppfs_cor", "jpcrp_cor"）。

    Returns:
        TextBlockConcept のリスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    concepts: list[TextBlockConcept] = []
    for elem in root.findall(f"{{{NS['xsd']}}}element"):
        xbrl_type = elem.get("type", "")
        if "textblock" not in xbrl_type.lower():
            continue

        name = elem.get("name", "")
        element_id = elem.get("id", "")
        abstract = elem.get("abstract", "false") == "true"
        period_type = elem.get(f"{{{NS['xbrli']}}}periodType", "")

        concepts.append(TextBlockConcept(
            name=name,
            element_id=element_id,
            xbrl_type=xbrl_type,
            abstract=abstract,
            period_type=period_type,
            source_ns=source_ns,
        ))

    return concepts


def classify_note_category(name: str) -> str:
    """concept 名から注記カテゴリを推定する。

    Args:
        name: concept 名。

    Returns:
        推定カテゴリ名。
    """
    import re

    categories = [
        (r"AccountingPolicy|SignificantAccounting", "重要な会計方針"),
        (r"RelatedParty", "関連当事者"),
        (r"Segment", "セグメント情報"),
        (r"TaxEffect|DeferredTax", "税効果会計"),
        (r"FinancialInstrument", "金融商品"),
        (r"RetirementBenefit|PensionPlan", "退職給付"),
        (r"PerShare|EarningsPerShare", "1株当たり情報"),
        (r"Impairment", "減損損失"),
        (r"ConsolidatedBalanceSheet|ConsolidatedStatementOf", "連結財務諸表注記"),
        (r"BalanceSheet|StatementOf", "個別財務諸表注記"),
        (r"Lease", "リース"),
        (r"Contingent|Commitment", "偶発債務・コミットメント"),
        (r"SubsequentEvent", "後発事象"),
        (r"Inventory|Inventories", "棚卸資産"),
        (r"Investment", "投資"),
        (r"BusinessCombination|Merger", "企業結合"),
        (r"Revenue", "収益認識"),
        (r"Risk|BusinessRisk", "リスク情報"),
        (r"CoverPage|Filing|Document", "表紙・書類情報"),
        (r"Governance", "ガバナンス"),
        (r"Compensation|Remuneration", "報酬"),
        (r"AnnexedDetailedSchedule", "附属明細表"),
        (r"Dividend", "配当"),
        (r"Employee", "従業員"),
    ]

    for pattern, category in categories:
        if re.search(pattern, name, re.IGNORECASE):
            return category

    return "その他"


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("J-3. 注記テキストの concept 検索")
    print("=" * 80)

    # ============================
    # セクション1: タクソノミから textBlockItemType を抽出
    # ============================
    print(f"\n--- jppfs_cor: {JPPFS_COR} ---")
    jppfs_concepts = parse_textblock_concepts(JPPFS_COR, "jppfs_cor")
    print(f"  textBlockItemType 数: {len(jppfs_concepts)}")

    print(f"\n--- jpcrp_cor: {JPCRP_COR} ---")
    jpcrp_concepts = parse_textblock_concepts(JPCRP_COR, "jpcrp_cor")
    print(f"  textBlockItemType 数: {len(jpcrp_concepts)}")

    all_concepts = jppfs_concepts + jpcrp_concepts
    print(f"\n合計 textBlockItemType 数: {len(all_concepts)}")

    # ============================
    # セクション2: 名前空間別集計
    # ============================
    print("\n" + "=" * 80)
    print("【名前空間別 textBlockItemType 集計】")
    print("=" * 80)
    ns_counter = Counter(c.source_ns for c in all_concepts)
    for ns, count in ns_counter.most_common():
        pct = count / len(all_concepts) * 100
        print(f"  {ns:<15s}: {count:>5d} ({pct:>5.1f}%)")

    # ============================
    # セクション3: jppfs_cor の textBlock 一覧（全件）
    # ============================
    print("\n" + "=" * 80)
    print(f"【jppfs_cor の textBlockItemType（全 {len(jppfs_concepts)} 件）】")
    print("=" * 80)
    for i, c in enumerate(jppfs_concepts[:20], 1):
        print(f"  {i:>3d}. {c.name}")
    if len(jppfs_concepts) > 20:
        print(f"  ... 残り {len(jppfs_concepts) - 20} 件")

    # ============================
    # セクション4: jpcrp_cor の textBlock 一覧（先頭20件）
    # ============================
    print("\n" + "=" * 80)
    print(f"【jpcrp_cor の textBlockItemType（先頭 20 件 / 全 {len(jpcrp_concepts)} 件）】")
    print("=" * 80)
    for i, c in enumerate(jpcrp_concepts[:20], 1):
        print(f"  {i:>3d}. {c.name}")
    if len(jpcrp_concepts) > 20:
        print(f"  ... 残り {len(jpcrp_concepts) - 20} 件")

    # ============================
    # セクション5: 注記カテゴリ分類
    # ============================
    print("\n" + "=" * 80)
    print("【注記カテゴリ別分類（命名パターンから推定）】")
    print("=" * 80)

    from collections import defaultdict
    category_map: dict[str, list[TextBlockConcept]] = defaultdict(list)
    for c in all_concepts:
        cat = classify_note_category(c.name)
        category_map[cat].append(c)

    for cat in sorted(category_map.keys(), key=lambda x: len(category_map[x]), reverse=True):
        items = category_map[cat]
        jppfs_n = sum(1 for i in items if i.source_ns == "jppfs_cor")
        jpcrp_n = sum(1 for i in items if i.source_ns == "jpcrp_cor")
        print(f"\n  {cat}: {len(items)} 件 (jppfs={jppfs_n}, jpcrp={jpcrp_n})")
        for item in items[:3]:
            print(f"    [{item.source_ns}] {item.name}")
        if len(items) > 3:
            print(f"    ... 残り {len(items) - 3} 件")

    # ============================
    # セクション6: 注記キーワードを含む textBlock（代表的なもの）
    # ============================
    print("\n" + "=" * 80)
    print("【注記に関連する代表的な textBlock concept】")
    print("=" * 80)

    keywords = [
        ("AccountingPolicy", "会計方針"),
        ("RelatedParty", "関連当事者"),
        ("Segment", "セグメント"),
        ("TaxEffect", "税効果"),
        ("FinancialInstrument", "金融商品"),
        ("RetirementBenefit", "退職給付"),
        ("PerShare", "1株当たり"),
        ("Revenue", "収益認識"),
    ]

    for keyword, label in keywords:
        matching = [c for c in all_concepts if keyword.lower() in c.name.lower()]
        print(f"\n  {label} ({keyword}): {len(matching)} 件")
        for c in matching[:3]:
            print(f"    [{c.source_ns}] {c.name}")
        if len(matching) > 3:
            print(f"    ... 残り {len(matching) - 3} 件")

    # ============================
    # セクション7: periodType 別集計
    # ============================
    print("\n" + "=" * 80)
    print("【periodType 別集計】")
    print("=" * 80)
    pt_counter = Counter(c.period_type for c in all_concepts)
    for pt, count in pt_counter.most_common():
        print(f"  {pt:<15s}: {count:>5d}")

    # ============================
    # セクション8: 実ファイルから textBlock Fact のサンプルを抽出
    # ============================
    print("\n" + "=" * 80)
    print("【実ファイルからの textBlock Fact サンプル（トヨタ S100VWVY）】")
    print("=" * 80)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _common import extract_member, find_public_doc_members, get_zip

    # textBlock concept 名セット（高速ルックアップ用）
    textblock_names = {c.name for c in all_concepts}

    try:
        doc_id = "S100VWVY"
        print(f"\n  書類管理番号: {doc_id}")
        zip_bytes = get_zip(doc_id, file_type="1")

        # .xbrl ファイルを探す
        xbrl_members = find_public_doc_members(zip_bytes, ".xbrl")
        print(f"  .xbrl ファイル数: {len(xbrl_members)}")

        if not xbrl_members:
            print("  [WARN] .xbrl ファイルが見つかりません")
        else:
            xbrl_path = xbrl_members[0]
            print(f"  対象ファイル: {xbrl_path}")
            xbrl_bytes = extract_member(zip_bytes, xbrl_path)
            root = ET.fromstring(xbrl_bytes)

            # contextRef を持つ要素で textBlock に該当するものを検索
            textblock_facts: list[tuple[str, str, str]] = []
            for elem in root:
                tag = elem.tag
                if not isinstance(tag, str) or "}" not in tag:
                    continue

                ns_uri, local_name = tag.rsplit("}", 1)
                ns_uri = ns_uri.lstrip("{")

                # contextRef があれば Fact
                context_ref = elem.get("contextRef")
                if context_ref is None:
                    continue

                # textBlock concept かどうかを判定
                # 方法1: 名前が既知の textBlock concept に一致
                is_textblock = local_name in textblock_names

                # 方法2: テキスト内容に HTML タグを含む（長いテキスト）
                text_content = elem.text or ""
                if not is_textblock and len(text_content) > 200:
                    if "<table" in text_content.lower() or "<p" in text_content.lower():
                        is_textblock = True

                if is_textblock and text_content:
                    textblock_facts.append((local_name, context_ref, text_content))

            print(f"\n  textBlock Fact 検出数: {len(textblock_facts)}")

            # 名前空間別に分類
            jpcrp_facts = [f for f in textblock_facts if any(
                f[0] == c.name for c in jpcrp_concepts
            )]
            jppfs_facts = [f for f in textblock_facts if any(
                f[0] == c.name for c in jppfs_concepts
            )]
            other_facts = [f for f in textblock_facts
                           if f not in jpcrp_facts and f not in jppfs_facts]

            print(f"    jpcrp_cor 由来: {len(jpcrp_facts)}")
            print(f"    jppfs_cor 由来: {len(jppfs_facts)}")
            print(f"    その他（拡張等）: {len(other_facts)}")

            # サンプル表示（先頭5件）
            print(f"\n  --- textBlock Fact サンプル（先頭 10 件）---")
            for i, (name, ctx, text) in enumerate(textblock_facts[:10], 1):
                # テキストの先頭200文字を表示（HTMLタグを含む）
                preview = text[:200].replace("\n", " ").replace("\r", "")
                if len(text) > 200:
                    preview += "..."
                print(f"\n  [{i}] concept: {name}")
                print(f"      context: {ctx}")
                print(f"      長さ: {len(text):,} 文字")
                print(f"      先頭: {preview}")

    except Exception as e:
        print(f"  [ERROR] 実ファイル取得に失敗: {e}")
        import traceback
        traceback.print_exc()

    # ============================
    # サマリ
    # ============================
    print("\n" + "=" * 80)
    print("【サマリ】")
    print("=" * 80)
    print(f"  jppfs_cor textBlockItemType: {len(jppfs_concepts)} 件")
    print(f"  jpcrp_cor textBlockItemType: {len(jpcrp_concepts)} 件")
    print(f"  合計: {len(all_concepts)} 件")
    print(f"  periodType=duration: {pt_counter.get('duration', 0)} 件")
    print(f"  注記は textBlockItemType として HTML 形式で XBRL に含まれる")
    print(f"  大部分は jpcrp_cor 名前空間に属する")


if __name__ == "__main__":
    main()

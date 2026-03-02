"""E-1c. SS 定義リンクベースの次元構造可視化スクリプト

実行方法: uv run docs/QAs/scripts/E-1c.ss_structure.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: StatementOfChangesInEquityTable のハイパーキューブ構造、
      ComponentsOfEquityAxis の Member 一覧（列ヘッダー）、
      行方向の concept 構造
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

# 建設業 (cns) と一般商工業 (cai) の SS 定義ファイル
BASE_DIR = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01"
SS_DEF_FILES = {
    "cns": BASE_DIR / "r" / "cns" / "jppfs_cns_cm_2025-11-01_def_ss.xml",
    "cai": BASE_DIR / "r" / "cai" / "jppfs_cai_cm_2025-11-01_def_ss.xml",
}

# プレゼンテーションリンクベースも参照
SS_PRE_FILES_PATTERN = "_pre_ss"


def parse_def_linkbase(
    file_path: Path,
) -> tuple[dict[str, str], dict[str, list[tuple[str, str, float]]]]:
    """定義リンクベースをパースし、locator と arc 情報を抽出する。

    Args:
        file_path: 定義リンクベースファイルのパス。

    Returns:
        (locators, arcs) のタプル。
        locators: label -> concept名。
        arcs: from_label -> [(to_label, arcrole, order), ...] の辞書。
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    # locator: label -> href (concept名を含む)
    locators: dict[str, str] = {}
    # arcs: from_label -> [(to_label, arcrole, order)]
    arcs: dict[str, list[tuple[str, str, float]]] = defaultdict(list)

    for def_link in root.findall(f".//{{{NS['link']}}}definitionLink"):
        # locator を収集
        for loc in def_link.findall(f"{{{NS['link']}}}loc"):
            label = loc.get(f"{{{NS['xlink']}}}label", "")
            href = loc.get(f"{{{NS['xlink']}}}href", "")
            # href から concept 名を抽出 (fragment identifier)
            if "#" in href:
                concept = href.split("#")[-1]
                # プレフィックスを除去
                if "_" in concept:
                    concept = concept.split("_", 1)[-1]
            else:
                concept = href
            locators[label] = concept

        # arc を収集
        for arc in def_link.findall(f"{{{NS['link']}}}definitionArc"):
            from_label = arc.get(f"{{{NS['xlink']}}}from", "")
            to_label = arc.get(f"{{{NS['xlink']}}}to", "")
            arcrole = arc.get(f"{{{NS['xlink']}}}arcrole", "")
            order = float(arc.get("order", "0"))
            arcs[from_label].append((to_label, arcrole, order))

    return locators, arcs


def print_tree(
    label: str,
    locators: dict[str, str],
    arcs: dict[str, list[tuple[str, str, float]]],
    indent: int = 0,
    visited: set[str] | None = None,
) -> None:
    """ツリー構造を再帰的に表示する。

    Args:
        label: 現在のラベル。
        locators: locator マップ。
        arcs: arc マップ。
        indent: インデント深さ。
        visited: 訪問済みラベル（循環防止）。
    """
    if visited is None:
        visited = set()

    if label in visited:
        return
    visited.add(label)

    concept = locators.get(label, label)
    prefix = "  " * indent

    # ノードの種類を推定
    node_type = ""
    if "Table" in concept:
        node_type = " [TABLE]"
    elif "Axis" in concept:
        node_type = " [AXIS]"
    elif "Member" in concept:
        node_type = " [MEMBER]"
    elif "LineItems" in concept:
        node_type = " [LINE-ITEMS]"
    elif "Abstract" in concept:
        node_type = " [ABSTRACT]"

    print(f"{prefix}{concept}{node_type}")

    children = arcs.get(label, [])
    children.sort(key=lambda x: x[2])  # order でソート

    for to_label, _arcrole, _order in children:
        print_tree(to_label, locators, arcs, indent + 1, visited.copy())


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("E-1c. SS（株主資本等変動計算書）の2次元構造分析")
    print("=" * 80)

    for industry, file_path in SS_DEF_FILES.items():
        print(f"\n{'=' * 70}")
        print(f"【{industry} 業種 — SS 定義リンクベース】")
        print(f"ファイル: {file_path.name}")
        print(f"{'=' * 70}")

        if not file_path.exists():
            print(f"  ファイルが存在しません: {file_path}")
            continue

        locators, arcs = parse_def_linkbase(file_path)

        print(f"\n  locator 数: {len(locators)}")
        print(f"  arc 数: {sum(len(v) for v in arcs.values())}")

        # ルート要素を特定（他のノードの子でないノード）
        all_from = set(arcs.keys())
        all_to = set()
        for children in arcs.values():
            for to_label, _, _ in children:
                all_to.add(to_label)

        roots = all_from - all_to
        print(f"  ルート要素: {roots}")

        print(f"\n--- ツリー構造 ---")
        for root_label in sorted(roots):
            print_tree(root_label, locators, arcs)

        # Member 一覧（列ヘッダー候補）を抽出
        print(f"\n--- ComponentsOfEquityAxis の Member 一覧（列ヘッダー）---")
        axis_label = None
        for label, concept in locators.items():
            if "ComponentsOfEquityAxis" in concept:
                axis_label = label
                break

        if axis_label:
            members: list[tuple[str, float]] = []
            _collect_members(axis_label, locators, arcs, members)
            for member_name, order in members:
                print(f"  [{order:>4.1f}] {member_name}")
        else:
            print("  ComponentsOfEquityAxis が見つかりませんでした")

        # LineItems 構造（行方向）
        print(f"\n--- StatementOfChangesInEquityLineItems 構造（行方向）---")
        li_label = None
        for label, concept in locators.items():
            if "StatementOfChangesInEquityLineItems" in concept:
                li_label = label
                break

        if li_label:
            print_tree(li_label, locators, arcs)
        else:
            print("  LineItems が見つかりませんでした")

    # SS プレゼンテーションリンクベースも確認
    print("\n" + "=" * 80)
    print("【SS プレゼンテーションリンクベースの存在確認】")
    print("=" * 80)

    for industry in ["cns", "cai"]:
        r_dir = BASE_DIR / "r" / industry
        if r_dir.exists():
            ss_pre_files = list(r_dir.glob("*_pre_ss*"))
            ss_pre_files += list(r_dir.glob("*_pre*ss*"))
            if ss_pre_files:
                for f in ss_pre_files:
                    print(f"  {industry}: {f.name}")
            else:
                print(f"  {industry}: SS プレゼンテーションファイルなし")

    # 2次元構造のまとめ
    print("\n" + "=" * 80)
    print("【SS 2次元構造のまとめ】")
    print("=" * 80)
    print("""
  SS の2次元構造は以下のように XBRL 上で表現される:

  1. ハイパーキューブ構造:
     StatementOfChangesInEquityAbstract
       ├── StatementOfChangesInEquityTable [TABLE] (ハイパーキューブ)
       │     └── ComponentsOfEquityAxis [AXIS] (列方向の次元軸)
       │           ├── NetAssetsMember (純資産合計)
       │           │     ├── ShareholdersEquityMember (株主資本)
       │           │     │     ├── CapitalStockMember (資本金)
       │           │     │     ├── CapitalSurplusMember (資本剰余金)
       │           │     │     ├── RetainedEarningsMember (利益剰余金)
       │           │     │     └── TreasuryStockMember (自己株式)
       │           │     ├── ValuationAndTranslationAdjustmentsMember (評価・換算差額等)
       │           │     ├── ShareAwardRightsMember
       │           │     ├── SubscriptionRightsToSharesMember (新株予約権)
       │           │     └── NonControllingInterestsMember (非支配株主持分)
       │           └── ...
       └── StatementOfChangesInEquityLineItems [LINE-ITEMS] (行方向)
             ├── NetAssets (純資産)
             ├── ChangesOfItemsDuringThePeriodAbstract (当期変動額)
             │     ├── IssuanceOfNewShares (新株の発行)
             │     ├── DividendsFromSurplus (剰余金の配当)
             │     ├── ProfitLossAttributableToOwnersOfParent (親会社株主に帰属する当期純損益)
             │     ├── ProfitLoss (当期純損益)
             │     ├── DisposalOfTreasuryStock (自己株式の処分)
             │     ├── NetChangesOfItemsOtherThanShareholdersEquity (株主資本以外の項目の当期変動額)
             │     └── TotalChangesOfItemsDuringThePeriod (当期変動額合計)
             └── (期末残高は LineItems の一部)

  2. 列方向: ComponentsOfEquityAxis の Member で区別（dimension）
  3. 行方向: LineItems 配下の concept で表現
  4. 期首/期末残高: Context の period (instant) で区別
  5. 当期変動額: Context の period (duration) で表現
""")


def _collect_members(
    label: str,
    locators: dict[str, str],
    arcs: dict[str, list[tuple[str, str, float]]],
    result: list[tuple[str, float]],
    depth: int = 0,
) -> None:
    """Member を再帰的に収集する。

    Args:
        label: 現在のラベル。
        locators: locator マップ。
        arcs: arc マップ。
        result: 結果リスト。
        depth: 深さ。
    """
    children = arcs.get(label, [])
    children.sort(key=lambda x: x[2])

    for to_label, _, order in children:
        concept = locators.get(to_label, to_label)
        indent_prefix = "  " * depth
        result.append((f"{indent_prefix}{concept}", order))
        _collect_members(to_label, locators, arcs, result, depth + 1)


if __name__ == "__main__":
    main()

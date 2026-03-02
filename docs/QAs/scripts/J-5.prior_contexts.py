"""J-5. 前期 Context の構造分析スクリプト。

実行方法: EDINET_API_KEY=... uv run docs/QAs/scripts/J-5.prior_contexts.py
前提: EDINET_API_KEY 環境変数が必要
出力: トヨタ Filing (S100VWVY) から全 Context を抽出し、Prior{n} パターンでグルーピング。
      各前期 Context の日付範囲を表示。
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import extract_member, find_public_doc_members, get_zip

# トヨタ Filing
DOC_ID = "S100VWVY"

# XBRL 名前空間
NS = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "xbrldi": "http://xbrl.org/2006/xbrldi",
}

# Prior{n} パターンの正規表現
PERIOD_RE = re.compile(
    r"^(CurrentYear|Interim|Prior\d+Year|Prior\d+Interim|"
    r"FilingDate|RecordDate|RecentDate|FutureDate)"
)


def classify_context_id(ctx_id: str) -> str:
    """Context ID から相対期間部分を抽出する。

    Args:
        ctx_id: Context ID 文字列。

    Returns:
        相対期間部分（例: CurrentYear, Prior1Year）。不明の場合は "Unknown"。
    """
    m = PERIOD_RE.match(ctx_id)
    return m.group(1) if m else "Unknown"


def extract_period_info(period_elem: ET.Element) -> str:
    """period 要素から日付情報を文字列として抽出する。

    Args:
        period_elem: xbrli:period 要素。

    Returns:
        日付情報文字列。
    """
    instant = period_elem.find("xbrli:instant", NS)
    if instant is not None and instant.text:
        return f"instant={instant.text}"

    start = period_elem.find("xbrli:startDate", NS)
    end = period_elem.find("xbrli:endDate", NS)
    if start is not None and end is not None:
        return f"duration={start.text}~{end.text}"

    return "unknown"


def extract_scenario_members(scenario_elem: ET.Element | None) -> list[str]:
    """scenario 要素から dimension メンバーを抽出する。

    Args:
        scenario_elem: xbrli:scenario 要素（None 可）。

    Returns:
        メンバー名のリスト。
    """
    if scenario_elem is None:
        return []

    members = []
    for em in scenario_elem.findall("xbrldi:explicitMember", NS):
        dim = em.get("dimension", "")
        val = em.text or ""
        members.append(f"{dim}={val}")
    return members


def main() -> None:
    """メイン処理。"""
    print("J-5: 前期 Context の構造分析")
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

    # Step 2: 全 Context を解析
    print(f"\n[Step 2] Context 要素の解析")
    print("-" * 70)
    root = ET.fromstring(xbrl_bytes)

    contexts = root.findall("xbrli:context", NS)
    print(f"  Context 総数: {len(contexts)}")

    # Context 情報を収集
    ctx_info: list[dict] = []
    for ctx in contexts:
        ctx_id = ctx.get("id", "")
        period_elem = ctx.find("xbrli:period", NS)
        scenario_elem = ctx.find("xbrli:scenario", NS)

        period_str = extract_period_info(period_elem) if period_elem is not None else "none"
        members = extract_scenario_members(scenario_elem)
        group = classify_context_id(ctx_id)

        ctx_info.append({
            "id": ctx_id,
            "group": group,
            "period": period_str,
            "members": members,
        })

    # Step 3: グループ別に集計
    print(f"\n[Step 3] 相対期間グループ別の Context 集計")
    print("-" * 70)

    by_group: dict[str, list[dict]] = defaultdict(list)
    for info in ctx_info:
        by_group[info["group"]].append(info)

    # ソートキー: CurrentYear -> Interim -> Prior1Year -> Prior1Interim -> ...
    def sort_key(group_name: str) -> tuple[int, int]:
        """グループ名をソート可能なキーに変換する。

        Args:
            group_name: グループ名。

        Returns:
            ソート用のタプル。
        """
        if group_name == "CurrentYear":
            return (0, 0)
        if group_name == "Interim":
            return (0, 1)
        m = re.match(r"Prior(\d+)(Year|Interim)", group_name)
        if m:
            n = int(m.group(1))
            suffix = 0 if m.group(2) == "Year" else 1
            return (n, suffix)
        # FilingDate 等はあとにまとめる
        order_map = {"FilingDate": 100, "RecordDate": 101, "RecentDate": 102, "FutureDate": 103, "Unknown": 999}
        return (order_map.get(group_name, 500), 0)

    for group_name in sorted(by_group.keys(), key=sort_key):
        items = by_group[group_name]
        # 日付パターンを集約
        periods = set()
        for item in items:
            periods.add(item["period"])

        print(f"\n  [{group_name}] Context 数: {len(items)}")
        print(f"    日付パターン: {sorted(periods)}")

        # 代表例を3つまで表示
        for item in items[:3]:
            member_str = ", ".join(item["members"]) if item["members"] else "(なし)"
            print(f"      id={item['id']}")
            print(f"        period: {item['period']}")
            print(f"        members: {member_str}")
        if len(items) > 3:
            print(f"      ... 他 {len(items) - 3} 件")

    # Step 4: 各グループの Fact 数をカウント
    print(f"\n\n[Step 4] グループ別 Fact 数の集計")
    print("-" * 70)

    # Context ID -> グループ名のマッピング
    ctx_to_group = {info["id"]: info["group"] for info in ctx_info}

    # 全 Fact 要素を走査
    group_fact_count: dict[str, int] = defaultdict(int)
    total_facts = 0

    for elem in root.iter():
        ctx_ref = elem.get("contextRef")
        if ctx_ref:
            total_facts += 1
            group = ctx_to_group.get(ctx_ref, "Unknown")
            group_fact_count[group] += 1

    print(f"  Fact 総数: {total_facts}")
    print()
    print(f"  {'グループ':<25s} {'Fact 数':>10s} {'割合':>8s}")
    print(f"  {'-' * 45}")

    for group_name in sorted(group_fact_count.keys(), key=sort_key):
        count = group_fact_count[group_name]
        pct = count / total_facts * 100 if total_facts > 0 else 0
        print(f"  {group_name:<25s} {count:>10,d} {pct:>7.1f}%")

    # Step 5: Prior{n} の最大 n を確認
    print(f"\n\n[Step 5] Prior{{n}} の最大値確認")
    print("-" * 70)
    prior_groups = [g for g in by_group.keys() if g.startswith("Prior")]
    prior_groups.sort(key=sort_key)
    if prior_groups:
        print(f"  検出された Prior グループ: {prior_groups}")
        max_n = 0
        for g in prior_groups:
            m = re.match(r"Prior(\d+)", g)
            if m:
                max_n = max(max_n, int(m.group(1)))
        print(f"  最大 n: {max_n} (= Prior{max_n}Year)")
    else:
        print("  Prior グループなし")

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"  Context 総数: {len(contexts)}")
    print(f"  グループ数: {len(by_group)}")
    print(f"  Fact 総数: {total_facts}")
    print(f"  Prior グループ: {prior_groups}")


if __name__ == "__main__":
    main()

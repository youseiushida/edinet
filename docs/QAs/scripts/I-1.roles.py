"""I-1. jppfs_rt + jpcrp_rt XSD から全 roleType を抽出するスクリプト

実行方法: uv run docs/QAs/scripts/I-1.roles.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: 全 roleType の一覧（roleURI, id, definition, usedOn）を財務諸表種別にグルーピングして表示
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "link": "http://www.xbrl.org/2003/linkbase",
}

JPPFS_RT = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "jppfs_rt_2025-11-01.xsd"
JPCRP_RT = TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01" / "jpcrp_rt_2025-11-01.xsd"


@dataclass
class RoleType:
    """roleType 要素の情報を保持するデータクラス。"""

    role_uri: str
    role_id: str
    definition: str
    used_on: list[str] = field(default_factory=list)
    source_file: str = ""


def parse_role_types(xsd_path: Path) -> list[RoleType]:
    """XSD ファイルから全 roleType 要素を抽出する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        RoleType のリスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()

    roles: list[RoleType] = []
    for rt in root.iter(f"{{{NS['link']}}}roleType"):
        role_uri = rt.get("roleURI", "")
        role_id = rt.get("id", "")

        definition_elem = rt.find(f"{{{NS['link']}}}definition")
        definition = definition_elem.text.strip() if definition_elem is not None and definition_elem.text else ""

        used_on_elems = rt.findall(f"{{{NS['link']}}}usedOn")
        used_on = [elem.text.strip() for elem in used_on_elems if elem.text]

        roles.append(RoleType(
            role_uri=role_uri,
            role_id=role_id,
            definition=definition,
            used_on=used_on,
            source_file=xsd_path.name,
        ))

    return roles


def classify_financial_statement(role_id: str, definition: str) -> str:
    """roleType を財務諸表種別に分類する。

    Args:
        role_id: roleType の ID。
        definition: roleType の definition テキスト。

    Returns:
        分類名（BS/PL/CI/SS/CF/Notes/ListOfAccounts/Other）。
    """
    rid = role_id.lower()
    defn = definition.lower()

    if "balancesheet" in rid:
        if "listofaccounts" in rid:
            return "BS-科目一覧"
        return "BS"
    if "statementofincome" in rid or "incomestatement" in rid:
        if "listofaccounts" in rid:
            return "PL-科目一覧"
        return "PL"
    if "comprehensiveincome" in rid:
        if "listofaccounts" in rid:
            return "CI-科目一覧"
        return "CI"
    if "statementofchangesinequity" in rid or "changesinnetassets" in rid:
        if "listofaccounts" in rid:
            return "SS-科目一覧"
        return "SS"
    if "statementofcashflows" in rid or "cashflow" in rid:
        if "listofaccounts" in rid:
            return "CF-科目一覧"
        return "CF"
    if "notesnumber" in rid or "注記" in defn:
        return "Notes"
    if "pe" == rid.replace("rol_", ""):
        return "業種参照"
    if "listofaccounts" in rid:
        return "科目一覧(その他)"

    return "Other"


def classify_jpcrp_role(role_id: str, definition: str) -> str:
    """jpcrp roleType をセクションに分類する。

    Args:
        role_id: roleType の ID。
        definition: roleType の definition テキスト。

    Returns:
        分類名。
    """
    if "有価証券届出書" in definition:
        return "有価証券届出書"
    if "有価証券報告書" in definition:
        return "有価証券報告書"
    if "半期報告書" in definition or "semiannual" in role_id.lower():
        return "半期報告書"
    if "棚卸資産" in definition or "shelfreg" in role_id.lower():
        return "棚卸登録"
    if "臨時報告書" in definition:
        return "臨時報告書"
    if "自己株券" in definition:
        return "自己株券"

    return "その他"


def extract_industry_code(role_id: str) -> str:
    """roleType ID から業種略号を抽出する。

    Args:
        role_id: roleType の ID。

    Returns:
        業種略号。見つからなければ "std"。
    """
    m = re.match(r"rol_(?:std_)?([a-z]{2,3}\d?)_", role_id)
    if m:
        return m.group(1)
    if role_id.startswith("rol_std_"):
        return "std"
    return ""


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("I-1. Role URI と財務諸表の対応 — 全 roleType 抽出")
    print("=" * 80)

    # jppfs roleType 抽出
    print(f"\n--- jppfs_rt: {JPPFS_RT} ---")
    jppfs_roles = parse_role_types(JPPFS_RT)
    print(f"  合計 roleType 数: {len(jppfs_roles)}")

    # jpcrp roleType 抽出
    print(f"\n--- jpcrp_rt: {JPCRP_RT} ---")
    jpcrp_roles = parse_role_types(JPCRP_RT)
    print(f"  合計 roleType 数: {len(jpcrp_roles)}")

    # ===== jppfs 分析 =====
    print("\n" + "=" * 80)
    print("【jppfs roleType — 財務諸表種別グルーピング】")
    print("=" * 80)

    jppfs_by_category: dict[str, list[RoleType]] = defaultdict(list)
    for r in jppfs_roles:
        cat = classify_financial_statement(r.role_id, r.definition)
        jppfs_by_category[cat].append(r)

    for cat in sorted(jppfs_by_category.keys()):
        roles = jppfs_by_category[cat]
        print(f"\n--- {cat} ({len(roles)} 件) ---")
        for r in roles:
            industry = extract_industry_code(r.role_id)
            used_on_str = ", ".join(r.used_on)
            print(f"  [{industry:>3s}] {r.role_id}")
            print(f"        URI: {r.role_uri}")
            print(f"        Def: {r.definition}")
            print(f"        UsedOn: {used_on_str}")

    # usedOn 値の一覧
    print("\n" + "=" * 80)
    print("【jppfs usedOn 値の一覧】")
    print("=" * 80)
    all_used_on: set[str] = set()
    for r in jppfs_roles:
        all_used_on.update(r.used_on)
    for uo in sorted(all_used_on):
        print(f"  - {uo}")

    # definition パターン分析
    print("\n" + "=" * 80)
    print("【definition テキストパターン分析】")
    print("=" * 80)
    print("\n財務諸表名の日本語キーワードマッピング:")
    keyword_map = {
        "貸借対照表": "BS",
        "損益計算書": "PL",
        "包括利益計算書": "CI",
        "株主資本等変動計算書": "SS",
        "キャッシュ・フロー計算書": "CF",
    }
    for keyword, stmt_type in keyword_map.items():
        matching = [r for r in jppfs_roles if keyword in r.definition]
        print(f"  '{keyword}' → {stmt_type}: {len(matching)} 件マッチ")
        for r in matching[:3]:
            print(f"    例: {r.definition}")

    # std ロールのみ抽出（提出者用テンプレート）
    print("\n" + "=" * 80)
    print("【提出者用 roleType（std なし）vs EDINET タクソノミ用（std 付き）】")
    print("=" * 80)
    std_roles = [r for r in jppfs_roles if r.role_id.startswith("rol_std_")]
    non_std_roles = [r for r in jppfs_roles if not r.role_id.startswith("rol_std_") and r.role_id.startswith("rol_")]
    print(f"  EDINET タクソノミ用 (rol_std_*): {len(std_roles)} 件")
    print(f"  提出者用 (rol_*、std なし): {len(non_std_roles)} 件")

    # 主要な財務諸表 role URI 一覧（std のみ、業種共通パターン）
    print("\n" + "=" * 80)
    print("【主要財務諸表の role URI 完全リスト（EDINET タクソノミ用 rol_std_*）】")
    print("=" * 80)
    for r in sorted(std_roles, key=lambda x: x.definition):
        cat = classify_financial_statement(r.role_id, r.definition)
        if cat in ("BS", "PL", "CI", "SS", "CF"):
            print(f"  {cat:>2s} | {r.definition:<60s} | {r.role_id}")

    # ===== jpcrp 分析 =====
    print("\n" + "=" * 80)
    print("【jpcrp roleType — 非財務セクション role URI 完全リスト】")
    print("=" * 80)

    jpcrp_by_section: dict[str, list[RoleType]] = defaultdict(list)
    for r in jpcrp_roles:
        section = classify_jpcrp_role(r.role_id, r.definition)
        jpcrp_by_section[section].append(r)

    for section in sorted(jpcrp_by_section.keys()):
        roles = jpcrp_by_section[section]
        print(f"\n--- {section} ({len(roles)} 件) ---")
        for r in roles:
            print(f"  {r.role_id}")
            print(f"    Def: {r.definition}")

    # 業種コード集計
    print("\n" + "=" * 80)
    print("【jppfs 業種コード別 roleType 数】")
    print("=" * 80)
    industry_counts: dict[str, int] = defaultdict(int)
    for r in jppfs_roles:
        industry = extract_industry_code(r.role_id)
        if industry:
            industry_counts[industry] += 1
    for industry in sorted(industry_counts.keys()):
        print(f"  {industry:>4s}: {industry_counts[industry]:>4d} 件")

    print(f"\n合計: jppfs={len(jppfs_roles)}, jpcrp={len(jpcrp_roles)}")


if __name__ == "__main__":
    main()

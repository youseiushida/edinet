"""I-1b. 提出者独自 roleType の調査スクリプト

サンプルインスタンスの XSD を走査して link:roleType の有無を確認し、
_pre.xml の roleRef URI を EDINET 標準タクソノミの roleType と照合する。

実行方法: uv run docs/QAs/scripts/I-1b.custom_roles.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: 提出者 XSD 内の roleType 有無、roleRef 一覧と標準タクソノミとの照合結果
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

SAMPLE_BASE = Path(__file__).resolve().parents[2] / "仕様書" / "2026" / "サンプルインスタンス" / "サンプルインスタンス" / "提出データ"

NS = {
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

JPPFS_RT = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01" / "jppfs_rt_2025-11-01.xsd"
JPCRP_RT = TAXONOMY_ROOT / "taxonomy" / "jpcrp" / "2025-11-01" / "jpcrp_rt_2025-11-01.xsd"


def extract_role_types_from_xsd(xsd_path: Path) -> list[dict[str, str]]:
    """XSD から link:roleType 要素を抽出する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        roleType 情報のリスト。
    """
    tree = ET.parse(xsd_path)
    root = tree.getroot()
    roles = []
    for rt in root.iter(f"{{{NS['link']}}}roleType"):
        role_uri = rt.get("roleURI", "")
        role_id = rt.get("id", "")
        def_elem = rt.find(f"{{{NS['link']}}}definition")
        definition = def_elem.text.strip() if def_elem is not None and def_elem.text else ""
        roles.append({"roleURI": role_uri, "id": role_id, "definition": definition})
    return roles


def extract_role_uris_from_rt(xsd_path: Path) -> set[str]:
    """ロールタイプスキーマから全 roleURI を抽出する。

    Args:
        xsd_path: ロールタイプスキーマのパス。

    Returns:
        roleURI の集合。
    """
    roles = extract_role_types_from_xsd(xsd_path)
    return {r["roleURI"] for r in roles}


def extract_role_refs_from_linkbase(xml_path: Path) -> list[str]:
    """リンクベースファイルから roleRef の roleURI を抽出する。

    Args:
        xml_path: リンクベースファイルのパス。

    Returns:
        roleURI のリスト。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    uris = []
    for rr in root.findall(f"{{{NS['link']}}}roleRef"):
        uri = rr.get("roleURI", "")
        if uri:
            uris.append(uri)
    return uris


def scan_sample_directory(sample_dir: Path) -> None:
    """サンプルディレクトリ内の全 XSD を走査して roleType を探す。

    Args:
        sample_dir: サンプルデータのルートディレクトリ。
    """
    print(f"\n{'=' * 80}")
    print("【全サンプルインスタンスの XSD 走査 — roleType 探索】")
    print(f"{'=' * 80}")

    total_xsd = 0
    total_role_types = 0

    for xsd_path in sorted(sample_dir.rglob("*.xsd")):
        total_xsd += 1
        roles = extract_role_types_from_xsd(xsd_path)
        if roles:
            total_role_types += len(roles)
            rel_path = xsd_path.relative_to(sample_dir)
            print(f"\n  {rel_path}: {len(roles)} 件の roleType")
            for r in roles:
                print(f"    URI: {r['roleURI']}")
                print(f"    ID:  {r['id']}")
                print(f"    Def: {r['definition']}")

    print(f"\n  走査した XSD: {total_xsd} ファイル")
    print(f"  発見した roleType: {total_role_types} 件")
    if total_role_types == 0:
        print("  → 提出者の XSD に独自 roleType は定義されていない")


def analyze_sample(sample_name: str, xsd_path: Path, pre_path: Path) -> None:
    """個別サンプルの roleRef 照合分析を行う。

    Args:
        sample_name: サンプル名。
        xsd_path: 提出者 XSD のパス。
        pre_path: _pre.xml のパス。
    """
    print(f"\n{'=' * 80}")
    print(f"【{sample_name} — roleRef 照合分析】")
    print(f"{'=' * 80}")

    # EDINET 標準タクソノミの全 roleURI
    std_uris = set()
    if JPPFS_RT.exists():
        std_uris |= extract_role_uris_from_rt(JPPFS_RT)
    if JPCRP_RT.exists():
        std_uris |= extract_role_uris_from_rt(JPCRP_RT)
    print(f"  EDINET 標準タクソノミの roleURI 総数: {len(std_uris)}")

    # _pre.xml の roleRef URI
    if pre_path.exists():
        pre_uris = extract_role_refs_from_linkbase(pre_path)
        print(f"  _pre.xml の roleRef 数: {len(pre_uris)}")

        # 分類
        jppfs_uris = [u for u in pre_uris if "/jppfs/" in u]
        jpcrp_uris = [u for u in pre_uris if "/jpcrp/" in u]
        other_uris = [u for u in pre_uris if "/jppfs/" not in u and "/jpcrp/" not in u]

        print(f"    jppfs ロール: {len(jppfs_uris)}")
        for u in jppfs_uris:
            role_short = u.split("/")[-1]
            in_std = "✓" if u in std_uris else "✗ NOT IN STANDARD"
            print(f"      {role_short} {in_std}")

        print(f"    jpcrp ロール: {len(jpcrp_uris)}")
        for u in jpcrp_uris:
            role_short = u.split("/")[-1]
            in_std = "✓" if u in std_uris else "✗ NOT IN STANDARD"
            print(f"      {role_short} {in_std}")

        if other_uris:
            print(f"    その他ロール: {len(other_uris)}")
            for u in other_uris:
                in_std = "✓" if u in std_uris else "✗ NOT IN STANDARD"
                print(f"      {u} {in_std}")

        # 標準にないロール
        non_std = [u for u in pre_uris if u not in std_uris]
        if non_std:
            print(f"\n  ⚠ 標準タクソノミにない roleRef ({len(non_std)} 件):")
            for u in non_std:
                print(f"    {u}")
        else:
            print(f"\n  ✓ 全 roleRef が EDINET 標準タクソノミに定義済み")

        # 提出者用ロール（_std なし）の確認
        submitter_roles = [u for u in jppfs_uris if "rol_std_" not in u.split("/")[-1]]
        std_roles = [u for u in jppfs_uris if "rol_std_" in u.split("/")[-1]]
        print(f"\n  jppfs ロールの内訳:")
        print(f"    提出者用 (rol_*, std なし): {len(submitter_roles)}")
        for u in submitter_roles:
            print(f"      {u.split('/')[-1]}")
        print(f"    EDINET タクソノミ用 (rol_std_*): {len(std_roles)}")

    # XSD の roleType 確認
    if xsd_path.exists():
        roles = extract_role_types_from_xsd(xsd_path)
        print(f"\n  提出者 XSD の roleType: {len(roles)} 件")
        if roles:
            for r in roles:
                print(f"    {r['id']}: {r['definition']}")
        else:
            print("    → 独自 roleType の定義なし")


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("I-1b. 提出者独自 roleType の調査")
    print("=" * 80)

    # 1. 全サンプル走査
    scan_sample_directory(SAMPLE_BASE)

    # 2. サンプル 02（有価証券報告書）の詳細分析
    sample_02 = SAMPLE_BASE / "02_開示府令-有価証券報告書" / "XBRL" / "PublicDoc"
    xsd_02 = sample_02 / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12.xsd"
    pre_02 = sample_02 / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12_pre.xml"
    analyze_sample("サンプル 02: 有価証券報告書 (一般商工業)", xsd_02, pre_02)

    # 3. def.xml の roleRef も確認
    def_02 = sample_02 / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12_def.xml"
    if def_02.exists():
        print(f"\n{'=' * 80}")
        print("【_def.xml の roleRef】")
        print(f"{'=' * 80}")
        def_uris = extract_role_refs_from_linkbase(def_02)
        std_uris = set()
        if JPPFS_RT.exists():
            std_uris |= extract_role_uris_from_rt(JPPFS_RT)
        if JPCRP_RT.exists():
            std_uris |= extract_role_uris_from_rt(JPCRP_RT)

        # 科目一覧ツリー用ロール
        list_of_accounts = [u for u in def_uris if "ListOfAccounts" in u]
        print(f"  科目一覧ツリー用ロール: {len(list_of_accounts)}")
        for u in list_of_accounts:
            print(f"    {u.split('/')[-1]}")

        non_std = [u for u in def_uris if u not in std_uris]
        if non_std:
            print(f"  ⚠ 標準にないロール: {len(non_std)}")
            for u in non_std:
                print(f"    {u}")
        else:
            print(f"  ✓ 全 roleRef が標準タクソノミ内")

    # 4. 結論
    print(f"\n{'=' * 80}")
    print("【結論】")
    print(f"{'=' * 80}")
    print("  サンプルインスタンスにおいて:")
    print("  1. 提出者の XSD に独自 roleType を定義しているケースは存在しない")
    print("  2. 全ての roleRef は EDINET 標準タクソノミ（jppfs_rt, jpcrp_rt）に")
    print("     あらかじめ定義された提出者用ロール (rol_*, std なし) を使用")
    print("  3. 提出者が使用する jppfs ロールは _std_ を含まない提出者用ロール")
    print("     （例: rol_ConsolidatedBalanceSheet, rol_BalanceSheet）")


if __name__ == "__main__":
    main()

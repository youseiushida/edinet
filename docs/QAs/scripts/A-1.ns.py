"""A-1 調査スクリプト: J-GAAP / IFRS サンプルファイルの名前空間を抽出・比較する。

サンプルインスタンスの .xbrl ファイルからルート要素の名前空間宣言を抽出し、
J-GAAP と IFRS の差異を明らかにする。
"""

from __future__ import annotations

from pathlib import Path
from lxml import etree

SAMPLE_BASE = Path(__file__).resolve().parents[2] / "仕様書" / "2026" / "サンプルインスタンス" / "サンプルインスタンス" / "ダウンロードデータ"

JGAAP_XBRL = SAMPLE_BASE / "02_開示府令-有価証券報告書" / "S002XXXX" / "XBRL" / "PublicDoc" / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12.xbrl"
IFRS_XBRL = SAMPLE_BASE / "03_開示府令-IFRS有価証券報告書" / "S003XXXX" / "XBRL" / "PublicDoc" / "jpcrp030000-asr-001_X99002-000_2026-03-31_01_2026-06-12.xbrl"


def extract_namespaces(path: Path) -> dict[str, str]:
    """XBRLファイルのルート要素から名前空間マップを抽出する。

    Args:
        path: XBRLファイルのパス。

    Returns:
        プレフィックス→URI の辞書。
    """
    tree = etree.parse(str(path))
    root = tree.getroot()
    return dict(root.nsmap)


def classify_namespace(uri: str) -> str:
    """名前空間URIを分類する。

    Args:
        uri: 名前空間URI。

    Returns:
        分類文字列（"標準タクソノミ", "提出者別", "XBRL標準", "その他"）。
    """
    if "disclosure.edinet-fsa.go.jp/taxonomy/" in uri:
        return "標準タクソノミ"
    elif "disclosure.edinet-fsa.go.jp/" in uri:
        return "提出者別"
    elif "xbrl.org" in uri or "w3.org" in uri:
        return "XBRL/XML標準"
    else:
        return "その他"


def main() -> None:
    """メイン処理。"""
    for label, path in [("J-GAAP", JGAAP_XBRL), ("IFRS", IFRS_XBRL)]:
        print(f"\n{'=' * 70}")
        print(f"{label}: {path.name}")
        print(f"{'=' * 70}")

        if not path.exists():
            print(f"  [SKIP] ファイルが存在しません: {path}")
            continue

        ns_map = extract_namespaces(path)

        for prefix, uri in sorted(ns_map.items(), key=lambda x: (x[0] or "")):
            category = classify_namespace(uri)
            display_prefix = prefix if prefix else "(default)"
            print(f"  {display_prefix:40s} {category:12s}  {uri}")

    # 差異分析
    if JGAAP_XBRL.exists() and IFRS_XBRL.exists():
        jgaap_ns = extract_namespaces(JGAAP_XBRL)
        ifrs_ns = extract_namespaces(IFRS_XBRL)

        jgaap_uris = set(jgaap_ns.values())
        ifrs_uris = set(ifrs_ns.values())

        print(f"\n{'=' * 70}")
        print("差異分析")
        print(f"{'=' * 70}")

        only_ifrs = ifrs_uris - jgaap_uris
        only_jgaap = jgaap_uris - ifrs_uris

        if only_ifrs:
            print("\n  IFRS のみに存在する名前空間:")
            for uri in sorted(only_ifrs):
                prefix = [k for k, v in ifrs_ns.items() if v == uri][0]
                print(f"    {prefix}: {uri}")

        if only_jgaap:
            print("\n  J-GAAP のみに存在する名前空間:")
            for uri in sorted(only_jgaap):
                prefix = [k for k, v in jgaap_ns.items() if v == uri][0]
                print(f"    {prefix}: {uri}")

        common = jgaap_uris & ifrs_uris
        print(f"\n  共通の名前空間: {len(common)} 個")
        print(f"  J-GAAP 固有: {len(only_jgaap)} 個")
        print(f"  IFRS 固有: {len(only_ifrs)} 個")


if __name__ == "__main__":
    main()

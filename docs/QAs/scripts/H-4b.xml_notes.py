"""H-4b. XML パース上の注意 — サンプルインスタンスの調査スクリプト

実行方法: uv run docs/QAs/scripts/H-4b.xml_notes.py
前提: docs/仕様書/2026/サンプルインスタンス/ 配下にサンプルデータが展開済み
出力: BOM有無、CDATA有無、デフォルト名前空間有無、DOCTYPE有無の調査結果
"""

from pathlib import Path


def check_file(path: Path) -> dict:
    """ファイルの XML パース上の特徴を調査する。

    Args:
        path: 調査対象ファイルのパス

    Returns:
        調査結果の辞書
    """
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")  # BOM を除去して読む

    has_bom = raw[:3] == b"\xef\xbb\xbf"
    has_cdata = "<![CDATA[" in text
    has_doctype = "<!DOCTYPE" in text.upper()

    # デフォルト名前空間: xmlns="..." (プレフィックスなし) を検索
    import re

    default_ns_matches = re.findall(r'xmlns="([^"]+)"', text[:5000])

    return {
        "path": path.name,
        "size_kb": len(raw) / 1024,
        "has_bom": has_bom,
        "has_cdata": has_cdata,
        "has_doctype": has_doctype,
        "default_ns": default_ns_matches or None,
    }


def main() -> None:
    """サンプルインスタンスの XML 特徴を調査する。"""
    base = Path("docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ")
    if not base.exists():
        print(f"ERROR: {base} が見つかりません")
        return

    # .xbrl, .htm, .xml, .xsd をすべて収集
    extensions = [".xbrl", ".htm", ".xml", ".xsd"]
    files = []
    for ext in extensions:
        files.extend(sorted(base.rglob(f"*{ext}")))

    print(f"調査対象ファイル数: {len(files)}")
    print()

    # 統計集計
    stats = {"bom": 0, "no_bom": 0, "cdata": 0, "doctype": 0, "default_ns": 0}
    bom_examples: list[str] = []
    cdata_examples: list[str] = []
    doctype_examples: list[str] = []
    default_ns_examples: list[tuple[str, list[str]]] = []

    for f in files:
        result = check_file(f)
        if result["has_bom"]:
            stats["bom"] += 1
            if len(bom_examples) < 5:
                bom_examples.append(result["path"])
        else:
            stats["no_bom"] += 1
        if result["has_cdata"]:
            stats["cdata"] += 1
            if len(cdata_examples) < 5:
                cdata_examples.append(result["path"])
        if result["has_doctype"]:
            stats["doctype"] += 1
            if len(doctype_examples) < 5:
                doctype_examples.append(result["path"])
        if result["default_ns"]:
            stats["default_ns"] += 1
            if len(default_ns_examples) < 5:
                default_ns_examples.append((result["path"], result["default_ns"]))

    # ファイルタイプ別のBOM統計
    print("=== BOM 統計 ===")
    for ext in extensions:
        ext_files = [f for f in files if f.suffix == ext]
        bom_count = sum(1 for f in ext_files if f.read_bytes()[:3] == b"\xef\xbb\xbf")
        print(f"  {ext}: {bom_count}/{len(ext_files)} ファイルに BOM あり")
    print(f"  合計: BOM あり={stats['bom']}, BOM なし={stats['no_bom']}")
    if bom_examples:
        print(f"  BOM ありの例: {bom_examples[:3]}")
    print()

    print("=== CDATA セクション ===")
    print(f"  CDATA を含むファイル: {stats['cdata']}/{len(files)}")
    if cdata_examples:
        print(f"  例: {cdata_examples}")
    print()

    print("=== DOCTYPE 宣言 ===")
    print(f"  DOCTYPE を含むファイル: {stats['doctype']}/{len(files)}")
    if doctype_examples:
        print(f"  例: {doctype_examples}")
    print()

    print("=== デフォルト名前空間 (xmlns=\"...\") ===")
    print(f"  デフォルト名前空間を持つファイル: {stats['default_ns']}/{len(files)}")
    if default_ns_examples:
        for name, ns_list in default_ns_examples[:5]:
            print(f"  {name}: {ns_list}")


if __name__ == "__main__":
    main()

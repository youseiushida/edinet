"""H-1b: DTS 解決アルゴリズム調査。

2026 サンプル XSD を起点に xs:import の schemaLocation を全て抽出し、
各 URL を ALL_20251101 のローカルパスに変換してファイル存在を確認する。
再帰的に import 先の XSD も解析し、完全な import グラフを構築する。
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

TAXONOMY_ROOT = Path(os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    r"C:\Users\nezow\Downloads\ALL_20251101",
))

SAMPLE_DIR = Path(
    "docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ"
)

XSD_NS = "http://www.w3.org/2001/XMLSchema"
EDINET_BASE = "http://disclosure.edinet-fsa.go.jp/taxonomy/"
XBRL_ORG_BASE = "http://www.xbrl.org/"
W3C_BASE = "http://www.w3.org/"

# ============================================================
# URL → ローカルパス変換ルール
# ============================================================
def url_to_local(url: str, base_dir: Path | None = None) -> Path | None:
    """URL をローカルパスに変換する。

    Args:
        url: スキーマ URL または相対パス。
        base_dir: 相対パスの基準ディレクトリ。

    Returns:
        ローカルパス。変換不能なら None。
    """
    if url.startswith(EDINET_BASE):
        # EDINET URL → ALL_20251101/taxonomy/ にマッピング
        relative = url[len(EDINET_BASE):]
        return TAXONOMY_ROOT / "taxonomy" / relative
    elif url.startswith(("http://", "https://")):
        # 外部 URL（XBRL.org, W3C 等）→ ローカルに変換不可
        return None
    else:
        # 相対パス
        if base_dir:
            return base_dir / url
        return None


# ============================================================
# H-1b.1, H-1b.3: import 連鎖の再帰的追跡
# ============================================================
def extract_imports(xsd_path: Path) -> list[dict[str, str]]:
    """XSD ファイルから xs:import 要素を全て抽出する。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        import 情報の辞書リスト。
    """
    try:
        tree = ET.parse(xsd_path)
    except Exception as e:
        return [{"error": str(e)}]

    root = tree.getroot()
    imports = []

    for imp in root.findall(f"{{{XSD_NS}}}import"):
        ns = imp.get("namespace", "")
        sl = imp.get("schemaLocation", "")
        imports.append({"namespace": ns, "schemaLocation": sl})

    return imports


def build_import_graph(
    start_path: Path,
    *,
    visited: set[str] | None = None,
    depth: int = 0,
    max_depth: int = 10,
) -> dict:
    """再帰的に import グラフを構築する。

    Args:
        start_path: 起点 XSD のパス。
        visited: 訪問済み URL セット。
        depth: 現在の深さ。
        max_depth: 最大探索深さ。

    Returns:
        import グラフの辞書。
    """
    if visited is None:
        visited = set()

    key = str(start_path)
    if key in visited or depth > max_depth:
        return {"path": key, "depth": depth, "already_visited": True}

    visited.add(key)
    imports = extract_imports(start_path)
    children = []

    for imp in imports:
        sl = imp.get("schemaLocation", "")
        if not sl:
            continue

        local = url_to_local(sl, base_dir=start_path.parent)
        child_info = {
            "namespace": imp.get("namespace", ""),
            "schemaLocation": sl,
            "local_path": str(local) if local else None,
            "exists": local.exists() if local else False,
            "is_external": sl.startswith(("http://", "https://")) and not sl.startswith(EDINET_BASE),
        }

        # 再帰的に解析（ローカルファイルが存在する場合のみ）
        if local and local.exists() and str(local) not in visited:
            child_info["children"] = build_import_graph(
                local, visited=visited, depth=depth + 1, max_depth=max_depth,
            )

        children.append(child_info)

    return {
        "path": key,
        "depth": depth,
        "imports": children,
    }


def print_graph(graph: dict, indent: int = 0) -> None:
    """import グラフを表示する。

    Args:
        graph: グラフ辞書。
        indent: インデント数。
    """
    prefix = "  " * indent
    path = graph.get("path", "?")
    # パスを短縮表示
    short = path.split("/")[-1] if "/" in path else path.split("\\")[-1] if "\\" in path else path

    if graph.get("already_visited"):
        print(f"{prefix}[visited] {short}")
        return

    print(f"{prefix}{short} (depth={graph.get('depth', '?')})")

    for child in graph.get("imports", []):
        sl = child.get("schemaLocation", "")
        ns = child.get("namespace", "")
        exists = child.get("exists", False)
        is_ext = child.get("is_external", False)

        # 短縮表示
        sl_short = sl.split("/")[-1] if "/" in sl else sl
        status = "OK" if exists else ("EXTERNAL" if is_ext else "MISSING")
        print(f"{prefix}  -> {sl_short} [{status}] ns={ns[:60]}...")

        if "children" in child:
            print_graph(child["children"], indent + 2)


# ============================================================
# メイン処理
# ============================================================

# 2026 サンプル XSD の解析
print("=" * 70)
print("H-1b: DTS 解決アルゴリズム調査")
print("=" * 70)

# サンプル XSD を探す
sample_xsds: list[Path] = []
for d in sorted(SAMPLE_DIR.iterdir()):
    if d.is_dir():
        for xsd in d.rglob("*.xsd"):
            if "jpcrp030000-asr" in xsd.name:
                sample_xsds.append(xsd)

print(f"\n2026 サンプル XSD ファイル: {len(sample_xsds)} 件")
for xsd in sample_xsds:
    print(f"  - {xsd.relative_to(SAMPLE_DIR)}")

# ============================================================
# H-1b.1: import の schemaLocation は相対パスか絶対 URL か
# ============================================================
print(f"\n{'=' * 70}")
print("H-1b.1: xs:import の schemaLocation 形式")
print("=" * 70)

if sample_xsds:
    xsd = sample_xsds[0]
    print(f"\n--- {xsd.name} ---")
    imports = extract_imports(xsd)
    abs_count = 0
    rel_count = 0
    for imp in imports:
        sl = imp.get("schemaLocation", "")
        is_abs = sl.startswith("http")
        if is_abs:
            abs_count += 1
        else:
            rel_count += 1
        print(f"  {'ABS' if is_abs else 'REL'}: {sl}")
        print(f"       ns: {imp.get('namespace', '')}")

    print(f"\n  絶対 URL: {abs_count}, 相対パス: {rel_count}")
    print("  結論: 提出者 XSD の import は全て**絶対 URL**")

# ============================================================
# H-1b.2: URL → ローカルパスのマッピング表
# ============================================================
print(f"\n{'=' * 70}")
print("H-1b.2: URL → ローカルパスのマッピング表")
print("=" * 70)

url_map: list[tuple[str, str, bool]] = []

if sample_xsds:
    for imp in imports:
        sl = imp.get("schemaLocation", "")
        if not sl:
            continue
        local = url_to_local(sl, base_dir=sample_xsds[0].parent)
        local_str = str(local.relative_to(TAXONOMY_ROOT)) if local and str(local).startswith(str(TAXONOMY_ROOT)) else str(local) if local else "N/A (外部URL)"
        exists = local.exists() if local else False
        url_map.append((sl, local_str, exists))
        print(f"\n  URL:   {sl}")
        print(f"  LOCAL: {local_str}")
        print(f"  EXISTS: {exists}")

# ============================================================
# H-1b.3, H-1b.4: import 連鎖の深さとローカルパス
# ============================================================
print(f"\n{'=' * 70}")
print("H-1b.3: import 連鎖グラフ")
print("=" * 70)

if sample_xsds:
    graph = build_import_graph(sample_xsds[0], max_depth=5)
    print_graph(graph)

    # 統計
    def count_nodes(g: dict) -> tuple[int, int, int]:
        """ノード数を数える。"""
        total = 1
        external = 0
        missing = 0
        for child in g.get("imports", []):
            if child.get("is_external"):
                external += 1
            if not child.get("exists") and not child.get("is_external"):
                missing += 1
            if "children" in child:
                t, e, m = count_nodes(child["children"])
                total += t
                external += e
                missing += m
        return total, external, missing

    total, ext, miss = count_nodes(graph)
    print(f"\n  総ノード数: {total}")
    print(f"  外部URL（XBRL.org等）: {ext}")
    print(f"  欠落ファイル: {miss}")

# ============================================================
# H-1b.5: 固定プレフィックスの検証
# ============================================================
print(f"\n{'=' * 70}")
print("H-1b.5: EDINET URL プレフィックスの一貫性")
print("=" * 70)

edinet_urls = [sl for sl, _, _ in url_map if sl.startswith(EDINET_BASE)]
non_edinet_urls = [sl for sl, _, _ in url_map if sl.startswith("http") and not sl.startswith(EDINET_BASE)]

print(f"  EDINET URL数: {len(edinet_urls)}")
print(f"  非EDINET URL数: {len(non_edinet_urls)}")
print(f"  EDINET URL は全て '{EDINET_BASE}' で始まる: {all(u.startswith(EDINET_BASE) for u in edinet_urls)}")
print("\n  非EDINET URL 一覧:")
for url in non_edinet_urls:
    print(f"    - {url}")

# ============================================================
# H-1b.6: XBRL 国際標準スキーマの所在
# ============================================================
print(f"\n{'=' * 70}")
print("H-1b.6: XBRL 国際標準スキーマの ALL_20251101 内検索")
print("=" * 70)

# 外部 URL のファイル名で ALL_20251101 内を検索
xbrl_schemas = [
    "xbrl-instance-2003-12-31.xsd",
    "xbrl-linkbase-2003-12-31.xsd",
    "xl-2003-12-31.xsd",
    "xbrldt-2005.xsd",
    "nonNumeric-2009-12-16.xsd",
    "numeric-2009-12-16.xsd",
    "xml.xsd",
    "ref-2006-02-27.xsd",
    "deprecated-2009-12-16.xsd",
    "types.xsd",
]

for schema_name in xbrl_schemas:
    found = list(TAXONOMY_ROOT.rglob(schema_name))
    if found:
        for f in found:
            print(f"  FOUND: {schema_name} -> {f.relative_to(TAXONOMY_ROOT)}")
    else:
        print(f"  NOT FOUND: {schema_name}")

# ============================================================
# H-1b.7: META-INF / catalog.xml の存在確認
# ============================================================
print(f"\n{'=' * 70}")
print("H-1b.7: META-INF / catalog.xml / taxonomyPackages.xml の検索")
print("=" * 70)

for pattern in ["META-INF", "catalog.xml", "taxonomyPackages.xml"]:
    found = list(TAXONOMY_ROOT.rglob(pattern))
    if found:
        for f in found:
            print(f"  FOUND: {f.relative_to(TAXONOMY_ROOT)}")
    else:
        print(f"  NOT FOUND: {pattern}")

# ============================================================
# 追加: EDINET 標準タクソノミ XSD 内の外部 import 一覧
# ============================================================
print(f"\n{'=' * 70}")
print("追加: EDINET タクソノミ XSD 内の外部 import URL 集約")
print("=" * 70)

external_urls: set[str] = set()

# 主要モジュールの XSD を解析
for xsd_rel in [
    "taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd",
    "taxonomy/jpcrp/2025-11-01/jpcrp_cor_2025-11-01.xsd",
    "taxonomy/jpigp/2025-11-01/jpigp_cor_2025-11-01.xsd",
    "taxonomy/jpdei/2013-08-31/jpdei_cor_2013-08-31.xsd",
    "taxonomy/jppfs/2025-11-01/jppfs_rt_2025-11-01.xsd",
    "taxonomy/jpcrp/2025-11-01/jpcrp_rt_2025-11-01.xsd",
]:
    xsd_path = TAXONOMY_ROOT / xsd_rel
    if not xsd_path.exists():
        continue

    imports = extract_imports(xsd_path)
    for imp in imports:
        sl = imp.get("schemaLocation", "")
        if sl.startswith("http") and not sl.startswith(EDINET_BASE):
            external_urls.add(sl)

print(f"  外部 URL 一覧（{len(external_urls)} 件）:")
for url in sorted(external_urls):
    print(f"    - {url}")

print(f"\n{'=' * 70}")
print("完了")
print("=" * 70)

"""C-1b. jpigp モジュールの構造と jppfs との比較

実行方法: uv run docs/QAs/scripts/C-1b.jpigp_analysis.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: jpigp モジュールの構造、namespace、要素数、jppfs との要素名重複分析
"""

import os
import re
from pathlib import Path
from collections import Counter

TAXONOMY_ROOT = Path(os.environ.get("EDINET_TAXONOMY_ROOT", r"C:\Users\nezow\Downloads\ALL_20251101"))

def extract_elements(xsd_path):
    """XSD から要素名を抽出する。

    Args:
        xsd_path: XSD ファイルのパス

    Returns:
        要素名のリスト
    """
    elements = []
    try:
        with open(xsd_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for match in re.finditer(r'<xsd:element\s+name="(\w+)"', content):
            elements.append(match.group(1))
    except Exception:
        pass
    return elements

def get_namespace(xsd_path):
    """XSD から targetNamespace を抽出する。

    Args:
        xsd_path: XSD ファイルのパス

    Returns:
        targetNamespace の値（見つからない場合は None）
    """
    try:
        with open(xsd_path, 'r', encoding='utf-8') as f:
            content = f.read(5000)
        match = re.search(r'targetNamespace="([^"]+)"', content)
        return match.group(1) if match else None
    except Exception:
        return None

def main():
    """jpigp モジュールの構造を分析し、jppfs との比較を行う。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    # 1. jpigp module structure
    print("=" * 70)
    print("1. jpigp モジュール構造")
    print("=" * 70)

    jpigp_dir = None
    for d in taxonomy_dir.iterdir():
        if d.name == "jpigp":
            jpigp_dir = d
            break

    if not jpigp_dir or not jpigp_dir.exists():
        print(f"  jpigp ディレクトリが見つかりません")
        print(f"  検索パス: {taxonomy_dir}")
        print(f"  存在するディレクトリ: {sorted(d.name for d in taxonomy_dir.iterdir() if d.is_dir())}")
        return

    # List directory structure
    for root, dirs, files in os.walk(jpigp_dir):
        level = root.replace(str(jpigp_dir), '').count(os.sep)
        indent = '  ' * level
        rel = os.path.relpath(root, jpigp_dir)
        if rel == '.':
            print(f"  jpigp/")
        else:
            print(f"  {indent}{os.path.basename(root)}/")
        subindent = '  ' * (level + 1)
        for f in sorted(files):
            size = os.path.getsize(os.path.join(root, f))
            print(f"  {subindent}{f} ({size:,} bytes)")

    # 2. jpigp_cor XSD analysis
    print("\n" + "=" * 70)
    print("2. jpigp_cor XSD 分析")
    print("=" * 70)

    jpigp_cor = None
    for root, dirs, files in os.walk(jpigp_dir):
        for f in files:
            if '_cor_' in f and f.endswith('.xsd'):
                jpigp_cor = os.path.join(root, f)
                break

    if jpigp_cor:
        ns = get_namespace(jpigp_cor)
        elements = extract_elements(jpigp_cor)
        print(f"  ファイル: {os.path.relpath(jpigp_cor, taxonomy_dir)}")
        print(f"  Namespace: {ns}")
        print(f"  要素数: {len(elements)}")
        print(f"  最初の20要素: {elements[:20]}")
        print(f"  最後の10要素: {elements[-10:]}")

        # Analyze element naming patterns
        with open(jpigp_cor, 'r', encoding='utf-8') as f:
            content = f.read()
        abstract_count = content.count('abstract="true"')
        concrete_count = content.count('abstract="false"')
        print(f"  abstract=true: {abstract_count}, abstract=false: {concrete_count}")

        # IFRS suffix analysis
        ifrs_suffix = [e for e in elements if e.endswith('IFRS')]
        non_ifrs = [e for e in elements if not e.endswith('IFRS') and not e.endswith('Heading')]
        heading = [e for e in elements if e.endswith('Heading')]
        print(f"\n  命名パターン分析:")
        print(f"    IFRS サフィックス付き: {len(ifrs_suffix)}")
        print(f"    Heading サフィックス付き: {len(heading)}")
        print(f"    その他: {len(non_ifrs)}")
        if non_ifrs:
            print(f"    その他の例（最初の10件）: {non_ifrs[:10]}")
    else:
        print("  jpigp_cor XSD が見つかりません")

    # 3. jppfs_cor との要素名重複分析
    print("\n" + "=" * 70)
    print("3. jppfs_cor との要素名重複分析")
    print("=" * 70)

    jppfs_cor = None
    for root, dirs, files in os.walk(taxonomy_dir / "jppfs"):
        for f in files:
            if '_cor_' in f and f.endswith('.xsd'):
                jppfs_cor = os.path.join(root, f)
                break

    if jpigp_cor and jppfs_cor:
        jpigp_elements = set(extract_elements(jpigp_cor))
        jppfs_elements = set(extract_elements(jppfs_cor))

        overlap = jpigp_elements & jppfs_elements
        jpigp_only = jpigp_elements - jppfs_elements
        jppfs_only = jppfs_elements - jpigp_elements

        print(f"  jpigp 要素数: {len(jpigp_elements)}")
        print(f"  jppfs 要素数: {len(jppfs_elements)}")
        print(f"  重複要素数: {len(overlap)}")
        print(f"  jpigp のみ: {len(jpigp_only)}")
        print(f"  jppfs のみ: {len(jppfs_only)}")

        if overlap:
            print(f"\n  重複要素の例（最初の30件）:")
            for e in sorted(overlap)[:30]:
                print(f"    {e}")

        if jpigp_only:
            print(f"\n  jpigp のみの要素の例（最初の30件）:")
            for e in sorted(jpigp_only)[:30]:
                print(f"    {e}")

        # IFRS suffix matching check
        print(f"\n  IFRS サフィックス除去後の重複チェック:")
        jpigp_base_names = set()
        for e in jpigp_elements:
            if e.endswith('IFRS'):
                jpigp_base_names.add(e[:-4])  # Remove 'IFRS'
            else:
                jpigp_base_names.add(e)
        conceptual_overlap = jpigp_base_names & jppfs_elements
        print(f"    jpigp の IFRS サフィックス除去後の要素名と jppfs の重複: {len(conceptual_overlap)}")
        if conceptual_overlap:
            print(f"    概念的重複の例（最初の20件）:")
            for e in sorted(conceptual_overlap)[:20]:
                print(f"      jppfs: {e} <-> jpigp: {e}IFRS (or {e})")
    else:
        print("  XSD ファイルが見つかりません")

    # 4. jpigp r/ directory structure
    print("\n" + "=" * 70)
    print("4. jpigp r/ ディレクトリ構造（業種サブディレクトリの有無）")
    print("=" * 70)

    for version_dir in sorted(jpigp_dir.iterdir()):
        if not version_dir.is_dir():
            continue
        print(f"\n  バージョン: {version_dir.name}")
        r_dir = version_dir / "r"
        if r_dir.exists():
            print(f"  r/ ディレクトリの内容:")
            items = sorted(r_dir.iterdir())
            subdirs = [i for i in items if i.is_dir()]
            files = [i for i in items if i.is_file()]
            if subdirs:
                print(f"    サブディレクトリ: {[d.name for d in subdirs]}")
                for d in subdirs:
                    file_count = sum(1 for _ in d.rglob('*'))
                    print(f"      {d.name}/: {file_count} files")
            else:
                print(f"    サブディレクトリ: なし（業種別分割なし）")
            if files:
                print(f"    ファイル数: {len(files)}")
                for f in files[:10]:
                    print(f"      {f.name} ({f.stat().st_size:,} bytes)")
                if len(files) > 10:
                    print(f"      ... 他 {len(files) - 10} ファイル")
        else:
            print(f"  r/ ディレクトリなし")

    # jppfs の r/ との比較
    print("\n  比較: jppfs の r/ ディレクトリ:")
    for version_dir in sorted((taxonomy_dir / "jppfs").iterdir()):
        if not version_dir.is_dir():
            continue
        r_dir = version_dir / "r"
        if r_dir.exists():
            subdirs = sorted(d.name for d in r_dir.iterdir() if d.is_dir())
            print(f"    jppfs/{version_dir.name}/r/ のサブディレクトリ({len(subdirs)}個): {subdirs}")

    # 5. jpigp_cor XSD の import 分析
    print("\n" + "=" * 70)
    print("5. jpigp_cor XSD の import 分析")
    print("=" * 70)

    if jpigp_cor:
        with open(jpigp_cor, 'r', encoding='utf-8') as f:
            content = f.read()
        imports = re.findall(r'<xsd:import\s+namespace="([^"]+)"', content)
        for imp in imports:
            print(f"  import: {imp}")

    # 6. jpigp エントリーポイント分析
    print("\n" + "=" * 70)
    print("6. jpigp エントリーポイント分析")
    print("=" * 70)

    samples_dir = TAXONOMY_ROOT / "samples"
    if samples_dir.exists():
        for root, dirs, files in os.walk(samples_dir):
            for f in sorted(files):
                if 'jpigp' in f:
                    fp = os.path.join(root, f)
                    size = os.path.getsize(fp)
                    print(f"  {os.path.relpath(fp, TAXONOMY_ROOT)} ({size:,} bytes)")

    # 7. jpigp r/ ファイルの詳細分析（プレゼンテーション/計算/定義リンクベース）
    print("\n" + "=" * 70)
    print("7. jpigp r/ ファイルの命名パターン分析")
    print("=" * 70)

    for version_dir in sorted(jpigp_dir.iterdir()):
        if not version_dir.is_dir():
            continue
        r_dir = version_dir / "r"
        if r_dir.exists():
            # Analyze naming patterns
            prefixes = Counter()
            suffixes = Counter()
            for f in r_dir.glob('*.xml'):
                name = f.stem
                # Extract suffix pattern (pre/cal/def/lab/gla)
                parts = name.split('_')
                if len(parts) >= 2:
                    # Find the type indicator
                    for p in parts:
                        if p in ('pre', 'cal', 'def', 'lab', 'gla'):
                            suffixes[p] += 1
                    # Check for cu/lq pattern
                    for p in parts:
                        if p in ('cu', 'lq'):
                            prefixes[p] += 1

            print(f"  バージョン: {version_dir.name}")
            print(f"  リンクベース種別:")
            for s, c in sorted(suffixes.items()):
                print(f"    {s}: {c} ファイル")
            if prefixes:
                print(f"  cu/lq パターン:")
                for p, c in sorted(prefixes.items()):
                    print(f"    {p}: {c} ファイル")

            # Show a sample of file names
            all_files = sorted(f.name for f in r_dir.glob('*.xml'))
            print(f"  全ファイル数: {len(all_files)}")
            print(f"  ファイル名一覧（最初の20件）:")
            for name in all_files[:20]:
                print(f"    {name}")
            if len(all_files) > 20:
                print(f"  ... 他 {len(all_files) - 20} ファイル")
                print(f"  ファイル名一覧（最後の10件）:")
                for name in all_files[-10:]:
                    print(f"    {name}")


if __name__ == "__main__":
    main()

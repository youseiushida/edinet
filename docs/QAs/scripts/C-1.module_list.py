"""C-1. タクソノミモジュール体系調査

実行方法: uv run docs/QAs/scripts/C-1.module_list.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: 全モジュールの名前、namespace、要素数、ファイル構成
"""

import os
import re
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ.get("EDINET_TAXONOMY_ROOT", r"C:\Users\nezow\Downloads\ALL_20251101"))

def get_target_namespace(xsd_path):
    """XSD からtargetNamespace を抽出する。

    Args:
        xsd_path: XSD ファイルのパス

    Returns:
        targetNamespace 文字列、または取得不可時は None
    """
    try:
        with open(xsd_path, 'r', encoding='utf-8') as f:
            content = f.read(5000)  # First 5000 chars should have namespace
        match = re.search(r'targetNamespace="([^"]+)"', content)
        return match.group(1) if match else None
    except Exception:
        return None

def count_elements(xsd_path):
    """XSD 内の xsd:element 数をカウントする。

    Args:
        xsd_path: XSD ファイルのパス

    Returns:
        要素数（int）
    """
    try:
        with open(xsd_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return len(re.findall(r'<xsd:element\s', content))
    except Exception:
        return 0

def main():
    """タクソノミディレクトリを走査し、全モジュールの情報を出力する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    print("=" * 80)
    print("EDINET タクソノミモジュール一覧")
    print("=" * 80)

    # List all top-level directories under taxonomy/
    if not taxonomy_dir.exists():
        print(f"エラー: {taxonomy_dir} が存在しません")
        return

    modules = []
    for item in sorted(taxonomy_dir.iterdir()):
        if not item.is_dir():
            continue
        module_name = item.name

        # Find version directories
        for version_dir in sorted(item.iterdir()):
            if not version_dir.is_dir():
                continue
            version = version_dir.name

            # Find _cor_*.xsd files
            cor_files = list(version_dir.glob('*_cor_*.xsd'))
            if not cor_files:
                cor_files = list(version_dir.glob('*.xsd'))

            namespace = None
            element_count = 0
            xsd_files = []

            for xsd in sorted(version_dir.glob('*.xsd')):
                xsd_files.append(xsd.name)
                if '_cor_' in xsd.name:
                    namespace = get_target_namespace(xsd)
                    element_count = count_elements(xsd)

            # Count files in subdirectories
            subdir_info = {}
            for subdir in sorted(version_dir.iterdir()):
                if subdir.is_dir():
                    file_count = sum(1 for _ in subdir.rglob('*') if _.is_file())
                    subdir_info[subdir.name] = file_count

            modules.append({
                'name': module_name,
                'version': version,
                'namespace': namespace,
                'elements': element_count,
                'xsd_files': xsd_files,
                'subdirs': subdir_info,
            })

    # Print results
    for mod in modules:
        print(f"\n--- {mod['name']} ({mod['version']}) ---")
        print(f"  Namespace: {mod['namespace'] or '(なし)'}")
        print(f"  要素数: {mod['elements']}")
        print(f"  XSD files: {', '.join(mod['xsd_files'])}")
        if mod['subdirs']:
            for sd, cnt in mod['subdirs'].items():
                print(f"  {sd}/: {cnt} files")

    # Print summary table
    print("\n" + "=" * 80)
    print("サマリーテーブル")
    print("=" * 80)
    print(f"{'Module':<20} {'Version':<15} {'Elements':<10} {'Namespace (末尾)':<50}")
    print(f"{'-'*20} {'-'*15} {'-'*10} {'-'*50}")
    for mod in modules:
        ns_short = mod['namespace'].split('/')[-1] if mod['namespace'] else '—'
        print(f"{mod['name']:<20} {mod['version']:<15} {mod['elements']:<10} {ns_short:<50}")

    # Also list r/ directories if they exist
    print("\n" + "=" * 80)
    print("r/ ディレクトリの内容（存在する場合）")
    print("=" * 80)
    for mod in modules:
        mod_dir = taxonomy_dir / mod['name'] / mod['version']
        r_dir = mod_dir / "r"
        if r_dir.exists():
            subdirs = sorted(d.name for d in r_dir.iterdir() if d.is_dir())
            print(f"  {mod['name']}: {subdirs}")

if __name__ == "__main__":
    main()

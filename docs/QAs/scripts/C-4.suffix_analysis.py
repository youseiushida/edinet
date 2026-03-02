"""C-4. リンクベースファイルサフィックス体系調査

実行方法: uv run docs/QAs/scripts/C-4.suffix_analysis.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: 連結区分/財務諸表サフィックスのマトリックス、BSバリエーション完全一覧
"""

import os
import re
from pathlib import Path
from collections import Counter, defaultdict

_default = r"C:\Users\nezow\Downloads\ALL_20251101"
_env = os.environ.get("EDINET_TAXONOMY_ROOT", _default)
# WSL環境でWindowsパスを/mnt/c/...形式に変換
if _env.startswith("C:"):
    _env = "/mnt/c" + _env[2:].replace("\\", "/")
TAXONOMY_ROOT = Path(_env)

def main():
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    # Collect all files from r/ directories across ALL modules (not just jppfs)
    all_files = []
    for root, dirs, files in os.walk(taxonomy_dir):
        # Check if we're in an r/ directory (use string check for cross-platform compatibility)
        root_str = root.replace('\\', '/')
        if '/r/' in root_str or root_str.endswith('/r'):
            for f in files:
                if f.endswith('.xml'):
                    rel = os.path.relpath(os.path.join(root, f), taxonomy_dir)
                    all_files.append((rel, f))

    print(f"総ファイル数（r/配下）: {len(all_files)}")

    # Parse file names for jppfs module specifically
    # Pattern: jppfs_{業種}_{連結区分}_{日付}_{リンク種別}_{財務諸表}.xml
    print("\n" + "=" * 80)
    print("1. jppfs モジュールの r/ ファイルパターン分析")
    print("=" * 80)

    consolidation_types = Counter()
    link_types = Counter()
    fs_types = Counter()
    bs_variants = set()
    pl_variants = set()
    cf_variants = set()
    ss_variants = set()

    jppfs_files = [f for _, f in all_files if f.startswith('jppfs_')]
    print(f"  jppfs ファイル数: {len(jppfs_files)}")

    for f in jppfs_files:
        # Remove .xml extension
        name = f.replace('.xml', '')
        # Parse: jppfs_{industry}_{consol}_{date}_{linktype}_{fstype}
        # e.g., jppfs_bk1_ac_2025-11-01_pre_bs
        parts = name.split('_')
        if len(parts) >= 6:
            industry = parts[1]

            # Find consolidation type - it's after industry and before the date
            # Date pattern: YYYY-MM-DD
            date_idx = None
            for i, p in enumerate(parts):
                if re.match(r'\d{4}-\d{2}-\d{2}', p):
                    date_idx = i
                    break

            if date_idx is not None:
                consol = '_'.join(parts[2:date_idx])
                link_type = parts[date_idx + 1] if date_idx + 1 < len(parts) else ''
                fs_type = '_'.join(parts[date_idx + 2:]) if date_idx + 2 < len(parts) else ''

                consolidation_types[consol] += 1
                link_types[link_type] += 1
                fs_types[fs_type] += 1

                if fs_type.startswith('bs'):
                    bs_variants.add(fs_type)
                elif fs_type.startswith('pl'):
                    pl_variants.add(fs_type)
                elif fs_type.startswith('cf'):
                    cf_variants.add(fs_type)
                elif fs_type.startswith('ss'):
                    ss_variants.add(fs_type)

    print("\n連結区分:")
    for ct, count in consolidation_types.most_common():
        print(f"  {ct}: {count}")

    print("\nリンク種別:")
    for lt, count in link_types.most_common():
        print(f"  {lt}: {count}")

    # Print financial statement variants
    print("\n" + "=" * 80)
    print("2. 財務諸表サフィックス一覧")
    print("=" * 80)

    print("\nBS バリエーション:")
    for v in sorted(bs_variants):
        print(f"  {v}")

    print("\nPL バリエーション:")
    for v in sorted(pl_variants):
        print(f"  {v}")

    print("\nCF バリエーション:")
    for v in sorted(cf_variants):
        print(f"  {v}")

    print("\nSS バリエーション:")
    for v in sorted(ss_variants):
        print(f"  {v}")

    # 3. Consolidation type × Link type matrix
    print("\n" + "=" * 80)
    print("3. 連結区分 × リンク種別 マトリックス")
    print("=" * 80)

    matrix = defaultdict(lambda: defaultdict(int))
    for f in jppfs_files:
        name = f.replace('.xml', '')
        parts = name.split('_')
        date_idx = None
        for i, p in enumerate(parts):
            if re.match(r'\d{4}-\d{2}-\d{2}', p):
                date_idx = i
                break
        if date_idx:
            consol = '_'.join(parts[2:date_idx])
            link_type = parts[date_idx + 1] if date_idx + 1 < len(parts) else ''
            matrix[consol][link_type] += 1

    consols = sorted(matrix.keys())
    lts = sorted(set(lt for c in matrix.values() for lt in c.keys()))

    header = f"{'連結区分':<12}" + "".join(f"{lt:<8}" for lt in lts)
    print(header)
    print("-" * len(header))
    for c in consols:
        row = f"{c:<12}" + "".join(f"{matrix[c].get(lt, 0):<8}" for lt in lts)
        print(row)

    # 4. Consolidation type × Financial statement type matrix
    print("\n" + "=" * 80)
    print("4. 連結区分 × 財務諸表種別 マトリックス")
    print("=" * 80)

    matrix2 = defaultdict(lambda: defaultdict(set))
    for f in jppfs_files:
        name = f.replace('.xml', '')
        parts = name.split('_')
        date_idx = None
        for i, p in enumerate(parts):
            if re.match(r'\d{4}-\d{2}-\d{2}', p):
                date_idx = i
                break
        if date_idx:
            consol = '_'.join(parts[2:date_idx])
            link_type = parts[date_idx + 1] if date_idx + 1 < len(parts) else ''
            fs_type = '_'.join(parts[date_idx + 2:]) if date_idx + 2 < len(parts) else ''
            # Simplify fs_type to category
            if fs_type.startswith('bs'):
                cat = 'BS'
            elif fs_type.startswith('pl'):
                cat = 'PL'
            elif fs_type.startswith('cf'):
                cat = 'CF'
            elif fs_type.startswith('ss'):
                cat = 'SS'
            else:
                cat = fs_type
            matrix2[consol][cat].add(fs_type)

    for c in sorted(matrix2.keys()):
        print(f"\n  {c}:")
        for cat in sorted(matrix2[c].keys()):
            variants = sorted(matrix2[c][cat])
            print(f"    {cat}: {variants}")

    # 5. Non-jppfs modules with r/ directories
    print("\n" + "=" * 80)
    print("5. jppfs 以外のモジュールの r/ ファイル")
    print("=" * 80)

    non_jppfs = [f for rel, f in all_files if not f.startswith('jppfs_')]
    module_counter = Counter()
    for f in non_jppfs:
        mod = f.split('_')[0]
        module_counter[mod] += 1

    for mod, count in module_counter.most_common():
        print(f"  {mod}: {count} files")
        examples = [f for f in non_jppfs if f.startswith(mod + '_')][:3]
        for ex in examples:
            print(f"    例: {ex}")

    # 6. Full unique financial statement type list
    print("\n" + "=" * 80)
    print("6. 財務諸表種別 完全一覧（重複排除）")
    print("=" * 80)
    for fs, count in fs_types.most_common():
        print(f"  {fs}: {count}")

    # 7. Decode BS variant names
    print("\n" + "=" * 80)
    print("7. BS バリエーション名のデコード")
    print("=" * 80)

    bs_decode = {
        'bs': '貸借対照表（基本）',
        'bs-01-CA-Doubtful-1-ByAccount': 'BS-01: 流動資産・貸倒引当金・個別法',
        'bs-01-CA-Doubtful-2-ByGroup': 'BS-01: 流動資産・貸倒引当金・一括法',
        'bs-01-CA-Doubtful-3-Direct': 'BS-01: 流動資産・貸倒引当金・直接控除',
        'bs-03-IA-Doubtful-1-ByAccount': 'BS-03: 投資その他・貸倒引当金・個別法',
        'bs-03-IA-Doubtful-2-ByGroup': 'BS-03: 投資その他・貸倒引当金・一括法',
        'bs-03-IA-Doubtful-3-Direct': 'BS-03: 投資その他・貸倒引当金・直接控除',
    }

    for v in sorted(bs_variants):
        decoded = bs_decode.get(v, '（要調査）')
        print(f"  {v}")
        print(f"    → {decoded}")

if __name__ == "__main__":
    main()

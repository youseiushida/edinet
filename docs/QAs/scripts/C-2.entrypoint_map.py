"""C-2. エントリーポイント命名規則調査

実行方法: uv run docs/QAs/scripts/C-2.entrypoint_map.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: サフィックス→報告書種別マッピング、ファイル名パターン分析
"""

import os
import re
from pathlib import Path
from collections import Counter, defaultdict

TAXONOMY_ROOT = Path(os.environ.get("EDINET_TAXONOMY_ROOT", r"C:\Users\nezow\Downloads\ALL_20251101"))

def main():
    samples_dir = TAXONOMY_ROOT / "samples" / "2025-11-01"

    if not samples_dir.exists():
        # Try alternative paths
        for alt in [TAXONOMY_ROOT / "samples", TAXONOMY_ROOT]:
            if alt.exists():
                print(f"Looking in: {alt}")
                for item in sorted(alt.iterdir()):
                    print(f"  {item.name}")
        print(f"エラー: {samples_dir} が存在しません")
        return

    print("=" * 80)
    print("1. samples/2025-11-01/ ファイル一覧")
    print("=" * 80)

    files = sorted(f.name for f in samples_dir.iterdir() if f.is_file())
    print(f"  ファイル数: {len(files)}")
    for f in files:
        print(f"  {f}")

    # Parse file names
    print("\n" + "=" * 80)
    print("2. ファイル名パターン分析")
    print("=" * 80)

    suffixes = Counter()
    prefixes = Counter()
    form_codes = Counter()
    parsed = []

    for f in files:
        if not f.endswith('.xsd'):
            continue
        # Pattern: {module}{formcode}-{suffix}-{date}.xsd
        # e.g., jpcrp030000-asr-001_E00000-000_2025-11-01.xsd
        # or: jppfs-esr-E00000-000_2025-11-01.xsd

        # Extract suffix (3-letter code like asr, esr, sbr, etc.)
        match = re.match(r'(\w+?)(\d+)?-(\w+)-', f)
        if match:
            module = match.group(1)
            form_code = match.group(2) or ''
            suffix = match.group(3)
            suffixes[suffix] += 1
            prefixes[module] += 1
            if form_code:
                form_codes[form_code] += 1
            parsed.append({
                'file': f,
                'module': module,
                'form_code': form_code,
                'suffix': suffix,
            })

    print("\nサフィックス分布:")
    for s, c in suffixes.most_common():
        print(f"  {s}: {c} files")

    print("\nモジュール分布:")
    for p, c in prefixes.most_common():
        print(f"  {p}: {c} files")

    print("\n様式コード分布:")
    for fc, c in form_codes.most_common():
        print(f"  {fc}: {c} files")

    # Group by suffix
    print("\n" + "=" * 80)
    print("3. サフィックス別ファイル一覧")
    print("=" * 80)

    by_suffix = defaultdict(list)
    for p in parsed:
        by_suffix[p['suffix']].append(p)

    for suffix in sorted(by_suffix.keys()):
        items = by_suffix[suffix]
        print(f"\n  [{suffix}] ({len(items)} files)")
        for item in items:
            print(f"    {item['file']}")

    # Group by form_code
    print("\n" + "=" * 80)
    print("4. 様式コード別一覧")
    print("=" * 80)

    by_fc = defaultdict(list)
    for p in parsed:
        if p['form_code']:
            by_fc[p['form_code']].append(p)

    for fc in sorted(by_fc.keys()):
        items = by_fc[fc]
        print(f"\n  [form_code={fc}]")
        for item in items:
            print(f"    {item['file']} (suffix={item['suffix']})")

    # Also look at subdirectories
    print("\n" + "=" * 80)
    print("5. samples/2025-11-01/ サブディレクトリ")
    print("=" * 80)

    dirs = sorted(d.name for d in samples_dir.iterdir() if d.is_dir())
    if dirs:
        for d in dirs:
            print(f"  {d}/")
            subdir = samples_dir / d
            subfiles = sorted(f.name for f in subdir.iterdir())
            for sf in subfiles[:10]:
                print(f"    {sf}")
            if len(list(subdir.iterdir())) > 10:
                print(f"    ... (合計 {len(list(subdir.iterdir()))} items)")
    else:
        print("  サブディレクトリなし")

if __name__ == "__main__":
    main()

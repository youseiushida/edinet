"""H-3.8: タクソノミ差分情報の集計スクリプト。

実行方法: uv run docs/QAs/scripts/H-3.diff_stats.py
前提: docs/仕様書/2026/タクソノミ差分情報/ が存在すること
出力: 各モジュール・業種ごとの差分統計（追加/削除/変更）を集計し、
      2024-11-01 → 2025-11-01 の単年差分規模を報告する
"""

from __future__ import annotations

import re
from pathlib import Path

DIFF_ROOT = Path("docs/仕様書/2026/タクソノミ差分情報")

# page5.html から統計テーブルを解析する
ROW_PATTERN = re.compile(
    r"<td[^>]*>(.*?)</td>"
    r"<td[^>]*>(\d+)</td>"
    r"<td[^>]*>(\d+)</td>"
    r"<td[^>]*>(\d+)</td>"
    r"<td[^>]*>(\d+)</td>",
)


def parse_page5(path: Path) -> dict[str, dict[str, int]]:
    """page5.html の統計テーブルを解析する。

    Args:
        path: page5.html のパス。

    Returns:
        分類名 → {追加, 削除, 変更, 合計} の辞書。
    """
    text = path.read_text(encoding="utf-8")
    result: dict[str, dict[str, int]] = {}
    for m in ROW_PATTERN.finditer(text):
        category = m.group(1).strip()
        if not category:
            continue
        result[category] = {
            "追加": int(m.group(2)),
            "削除": int(m.group(3)),
            "変更": int(m.group(4)),
            "合計": int(m.group(5)),
        }
    return result


# ============================================================
# 全モジュール・業種の page5.html を収集
# ============================================================
print("=" * 70)
print("H-3.8: タクソノミ差分情報統計（2024-11-01 → 2025-11-01）")
print("=" * 70)

if not DIFF_ROOT.exists():
    print(f"エラー: {DIFF_ROOT} が見つかりません")
    raise SystemExit(1)

modules = sorted(d.name for d in DIFF_ROOT.iterdir() if d.is_dir())
print(f"\nモジュール: {modules}")

# モジュール別集計
module_totals: dict[str, dict[str, int]] = {}
# スキーマ要素のみ集計（concept の追加/削除に対応）
schema_totals: dict[str, dict[str, int]] = {}

all_results: list[tuple[str, str, dict[str, dict[str, int]]]] = []

for mod in modules:
    mod_dir = DIFF_ROOT / mod
    # サブディレクトリ内の page5.html を探す
    page5_files = sorted(mod_dir.rglob("page5.html"))

    if not page5_files:
        print(f"\n  {mod}: page5.html なし")
        continue

    mod_add = mod_del = mod_chg = 0
    schema_add = schema_del = schema_chg = 0

    for p5 in page5_files:
        # 親ディレクトリ名 = 業種/報告書タイプ
        variant = p5.parent.name
        stats = parse_page5(p5)
        all_results.append((mod, variant, stats))

        if "合計" in stats:
            mod_add += stats["合計"].get("追加", 0)
            mod_del += stats["合計"].get("削除", 0)
            mod_chg += stats["合計"].get("変更", 0)

        if "スキーマの要素" in stats:
            schema_add += stats["スキーマの要素"]["追加"]
            schema_del += stats["スキーマの要素"]["削除"]
            schema_chg += stats["スキーマの要素"]["変更"]

    module_totals[mod] = {"追加": mod_add, "削除": mod_del, "変更": mod_chg}
    schema_totals[mod] = {"追加": schema_add, "削除": schema_del, "変更": schema_chg}

# ============================================================
# モジュール別サマリ
# ============================================================
print(f"\n{'=' * 70}")
print("モジュール別差分サマリ（全要素）")
print("=" * 70)
print(f"{'モジュール':<12} {'業種数':>6} {'追加':>8} {'削除':>8} {'変更':>8}")
print("-" * 50)

grand_add = grand_del = grand_chg = 0
for mod in modules:
    if mod not in module_totals:
        continue
    t = module_totals[mod]
    variants = len([r for r in all_results if r[0] == mod])
    print(f"{mod:<12} {variants:>6} {t['追加']:>8} {t['削除']:>8} {t['変更']:>8}")
    grand_add += t["追加"]
    grand_del += t["削除"]
    grand_chg += t["変更"]

print("-" * 50)
print(f"{'合計':<12} {'':>6} {grand_add:>8} {grand_del:>8} {grand_chg:>8}")

# ============================================================
# スキーマ要素のみ（concept の追加/削除に直結）
# ============================================================
print(f"\n{'=' * 70}")
print("モジュール別差分サマリ（スキーマ要素のみ = concept の追加/削除/変更）")
print("=" * 70)
print(f"{'モジュール':<12} {'追加':>8} {'削除':>8} {'変更':>8}")
print("-" * 40)

s_add = s_del = s_chg = 0
for mod in modules:
    if mod not in schema_totals:
        continue
    t = schema_totals[mod]
    print(f"{mod:<12} {t['追加']:>8} {t['削除']:>8} {t['変更']:>8}")
    s_add += t["追加"]
    s_del += t["削除"]
    s_chg += t["変更"]

print("-" * 40)
print(f"{'合計':<12} {s_add:>8} {s_del:>8} {s_chg:>8}")

# ============================================================
# 代表的なモジュールの詳細
# ============================================================
print(f"\n{'=' * 70}")
print("代表モジュールの業種別詳細（スキーマ要素のみ）")
print("=" * 70)

for mod in ["jppfs", "jpcrp", "jpigp"]:
    print(f"\n--- {mod} ---")
    for m, variant, stats in all_results:
        if m != mod:
            continue
        if "スキーマの要素" in stats:
            s = stats["スキーマの要素"]
            if s["追加"] > 0 or s["削除"] > 0:
                print(f"  {variant:<30} 追加={s['追加']:>3}  削除={s['削除']:>3}  変更={s['変更']:>3}")

# ============================================================
# ラベル差分（ラベル変更はパーサーに影響する）
# ============================================================
print(f"\n{'=' * 70}")
print("ラベルリンクベースの差分サマリ")
print("=" * 70)
print(f"{'モジュール':<12} {'追加':>8} {'削除':>8} {'変更':>8}")
print("-" * 40)

for mod in modules:
    label_stats = {"追加": 0, "削除": 0, "変更": 0}
    for m, variant, stats in all_results:
        if m != mod:
            continue
        if "ラベルリンクベースの要素" in stats:
            s = stats["ラベルリンクベースの要素"]
            label_stats["追加"] += s["追加"]
            label_stats["削除"] += s["削除"]
            label_stats["変更"] += s["変更"]
    if any(v > 0 for v in label_stats.values()):
        print(f"{mod:<12} {label_stats['追加']:>8} {label_stats['削除']:>8} {label_stats['変更']:>8}")

print(f"\n{'=' * 70}")
print("完了")
print("=" * 70)

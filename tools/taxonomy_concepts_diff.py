"""各年度タクソノミの概念 ID 一覧出力 & 差分統計。

年度ごとに ``prefix:local_name`` 形式の概念 ID を改行区切りで
テキストファイルに出力し、以下 2 種類の差分統計を表示する。

1. **ベースライン比較**: 最新版（デフォルト 2026）との差分
2. **前年度比**: 各年度 vs 直前の年度（隔年差分）

TextBlock / 非TextBlock の内訳も出力する。

使い方:
    uv run python tools/taxonomy_concepts_diff.py
    uv run python tools/taxonomy_concepts_diff.py --output-dir ./taxonomy_concepts
    uv run python tools/taxonomy_concepts_diff.py --years 2024 2025 2026
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ROOT = Path(__file__).resolve().parent.parent

_TEXTBLOCK_SUFFIX = "TextBlock"


def _is_text_block(concept_id: str) -> bool:
    """概念 ID が TextBlock 型かどうかを判定する。"""
    local_name = concept_id.split(":", 1)[1] if ":" in concept_id else concept_id
    return local_name.endswith(_TEXTBLOCK_SUFFIX)


@dataclass(frozen=True, slots=True)
class ConceptSets:
    """年度ごとの概念集合を TextBlock / 非TextBlock に分けて保持する。"""

    all: set[str]
    text_block: set[str]
    non_text_block: set[str]


def _extract_concepts(taxonomy_path: str | Path) -> ConceptSets:
    """タクソノミから概念 ID を抽出し TextBlock / 非TextBlock に分類する。

    Args:
        taxonomy_path: タクソノミのルートパス。

    Returns:
        全体・TextBlock・非TextBlock の概念集合。
    """
    from edinet.xbrl.taxonomy import TaxonomyResolver

    resolver = TaxonomyResolver(taxonomy_path, use_cache=True)
    all_concepts: set[str] = set()
    for prefix, local_name, _role, _lang in resolver._standard_labels:
        all_concepts.add(f"{prefix}:{local_name}")

    tb = {c for c in all_concepts if _is_text_block(c)}
    non_tb = all_concepts - tb
    return ConceptSets(all=all_concepts, text_block=tb, non_text_block=non_tb)


def _diff_stats(
    target: set[str],
    base: set[str],
) -> tuple[int, int, int, int, float, float]:
    """2 つの概念集合の差分統計を計算する。

    Returns:
        (n_target, n_common, n_added, n_removed, add_rate%, del_rate%)
        追加 = base にあって target にない（base 視点の新規）
        削除 = target にあって base にない（base 視点の廃止）
    """
    common = target & base
    added = base - target
    removed = target - base
    n_target = len(target)
    n_common = len(common)
    n_added = len(added)
    n_removed = len(removed)
    add_rate = n_added / len(base) * 100 if base else 0
    del_rate = n_removed / n_target * 100 if n_target else 0
    return n_target, n_common, n_added, n_removed, add_rate, del_rate


_DIFF_HEADER = (
    f"{'from':>6s}  {'to':>6s}  {'from数':>8s}  "
    f"{'共通':>8s}  {'追加':>8s}  {'削除':>8s}  "
    f"{'追加率':>7s}  {'削除率':>7s}"
)
_DIFF_SEP = "-" * len(_DIFF_HEADER) + "---"


def _format_diff_row(
    from_year: int | str,
    to_year: int | str,
    target: set[str],
    base: set[str],
) -> str:
    """差分統計を 1 行にフォーマットする。"""
    n_target, n_common, n_added, n_removed, add_rate, del_rate = _diff_stats(
        target, base,
    )
    return (
        f"{from_year!s:>6s}  {to_year!s:>6s}  {n_target:>8,}  "
        f"{n_common:>8,}  {n_added:>8,}  {n_removed:>8,}  "
        f"{add_rate:>6.1f}%  {del_rate:>6.1f}%"
    )


def _print_comparison_section(
    title: str,
    pairs: list[tuple[int, int]],
    getter: Callable[[ConceptSets], set[str]],
    concepts_by_year: dict[int, ConceptSets],
) -> list[str]:
    """比較ペアのリストに対して差分テーブルを表示する。

    Args:
        title: セクションタイトル（例: "全体", "TextBlock"）。
        pairs: (from_year, to_year) のリスト。
        getter: ConceptSets からカテゴリの set を取り出す関数。
        concepts_by_year: 年度→ConceptSets のマッピング。

    Returns:
        サマリファイル用の行リスト。
    """
    print(f"\n--- {title} ---")
    print(_DIFF_HEADER)
    print(_DIFF_SEP)

    lines = [f"\n--- {title} ---", _DIFF_HEADER, _DIFF_SEP]

    for from_year, to_year in pairs:
        target = getter(concepts_by_year[from_year])
        base = getter(concepts_by_year[to_year])
        line = _format_diff_row(from_year, to_year, target, base)
        print(line)
        lines.append(line)

    return lines


def _write_detail_file(
    path: Path,
    from_year: int,
    to_year: int,
    from_cs: ConceptSets,
    to_cs: ConceptSets,
) -> None:
    """差分詳細ファイルを書き出す。"""
    with open(path, "w", encoding="utf-8") as f:
        for label, target, base in [
            ("全体", from_cs.all, to_cs.all),
            ("TextBlock", from_cs.text_block, to_cs.text_block),
            ("非TextBlock", from_cs.non_text_block, to_cs.non_text_block),
        ]:
            added = base - target
            removed = target - base
            f.write(f"{'=' * 50}\n")
            f.write(f"[{label}] {from_year}年版 → {to_year}年版\n")
            f.write(
                f"共通: {len(target & base):,}, "
                f"追加(→{to_year}): {len(added):,}, "
                f"削除(→{to_year}): {len(removed):,}\n"
            )
            f.write(f"{'=' * 50}\n\n")

            if added:
                f.write(f"## {to_year}年版で追加 ({len(added):,}件)\n")
                for c in sorted(added):
                    f.write(f"+ {c}\n")
                f.write("\n")

            if removed:
                f.write(f"## {to_year}年版で削除 ({len(removed):,}件)\n")
                for c in sorted(removed):
                    f.write(f"- {c}\n")
                f.write("\n")


def main() -> None:
    """メイン処理。"""
    parser = argparse.ArgumentParser(
        description="各年度タクソノミの概念 ID 一覧 & 差分統計",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "taxonomy_concepts"),
        help="出力ディレクトリ (default: taxonomy_concepts/)",
    )
    parser.add_argument(
        "--years", nargs="*", type=int, default=None,
        help="対象年度 (default: 利用可能な全年度)",
    )
    parser.add_argument(
        "--base-year", type=int, default=None,
        help="比較基準年度 (default: 利用可能な最新年度)",
    )
    args = parser.parse_args()

    import edinet

    available = edinet.list_taxonomy_versions()

    if args.years:
        years = sorted(args.years)
    else:
        years = sorted(available)

    base_year = args.base_year if args.base_year else max(years)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("タクソノミ概念 ID 一覧 & 差分統計")
    print("=" * 60)
    print(f"対象年度: {years}")
    print(f"比較基準: {base_year}年版")
    print(f"出力先: {output_dir}")
    print()

    # ────────────────────────────────────────────────────────
    # 1. 各年度のタクソノミをインストール & 概念抽出
    # ────────────────────────────────────────────────────────
    concepts_by_year: dict[int, ConceptSets] = {}

    for year in years:
        print(f"[{year}] インストール中...", end=" ", flush=True)
        t0 = time.perf_counter()
        info = edinet.install_taxonomy(year=year)
        cs = _extract_concepts(info.path)
        elapsed = time.perf_counter() - t0

        concepts_by_year[year] = cs

        # テキストファイル出力（全体・TextBlock・非TextBlock）
        for suffix, concepts in [
            ("", cs.all),
            ("_textblock", cs.text_block),
            ("_non_textblock", cs.non_text_block),
        ]:
            out_path = output_dir / f"concepts_{year}{suffix}.txt"
            with open(out_path, "w", encoding="utf-8") as f:
                for c in sorted(concepts):
                    f.write(c + "\n")

        print(
            f"{len(cs.all):,} 概念 "
            f"(TB={len(cs.text_block):,}, 非TB={len(cs.non_text_block):,}), "
            f"{elapsed:.1f}s"
        )

    # ────────────────────────────────────────────────────────
    # 2. ベースライン比較（各年度 vs 基準年度）
    # ────────────────────────────────────────────────────────
    if base_year not in concepts_by_year:
        print(f"\n基準年度 {base_year} が対象に含まれていません。差分統計をスキップします。")
        return

    other_years = [y for y in years if y != base_year]
    if not other_years:
        print("\n比較対象の年度がありません。")
        return

    summary_lines: list[str] = []

    # --- ベースライン比較 ---
    baseline_pairs = [(y, base_year) for y in other_years]

    print(f"\n{'=' * 60}")
    print(f"ベースライン比較 (各年度 vs {base_year}年版)")
    print(f"{'=' * 60}")
    summary_lines.append(f"ベースライン比較 (各年度 vs {base_year}年版)")

    for label, getter in [
        ("全体", lambda cs: cs.all),
        ("TextBlock", lambda cs: cs.text_block),
        ("非TextBlock", lambda cs: cs.non_text_block),
    ]:
        lines = _print_comparison_section(
            label, baseline_pairs, getter, concepts_by_year,
        )
        summary_lines.extend(lines)

    # ベースライン詳細ファイル
    for year in other_years:
        _write_detail_file(
            output_dir / f"diff_{year}_vs_{base_year}.txt",
            year, base_year,
            concepts_by_year[year], concepts_by_year[base_year],
        )

    # ────────────────────────────────────────────────────────
    # 3. 前年度比（隔年差分）
    # ────────────────────────────────────────────────────────
    if len(years) >= 2:
        yoy_pairs = [(years[i], years[i + 1]) for i in range(len(years) - 1)]

        print(f"\n{'=' * 60}")
        print("前年度比 (Year-over-Year)")
        print(f"{'=' * 60}")
        summary_lines.append("\n前年度比 (Year-over-Year)")

        for label, getter in [
            ("全体", lambda cs: cs.all),
            ("TextBlock", lambda cs: cs.text_block),
            ("非TextBlock", lambda cs: cs.non_text_block),
        ]:
            lines = _print_comparison_section(
                label, yoy_pairs, getter, concepts_by_year,
            )
            summary_lines.extend(lines)

        # 前年度比の詳細ファイル
        for from_year, to_year in yoy_pairs:
            _write_detail_file(
                output_dir / f"diff_{from_year}_vs_{to_year}.txt",
                from_year, to_year,
                concepts_by_year[from_year], concepts_by_year[to_year],
            )

    # ────────────────────────────────────────────────────────
    # 4. prefix 別の統計
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("prefix 別概念数 (各年度)")
    print(f"{'=' * 60}")

    all_prefixes: set[str] = set()
    for cs in concepts_by_year.values():
        for c in cs.all:
            all_prefixes.add(c.split(":")[0])

    prefix_counts: dict[str, dict[int, tuple[int, int, int]]] = {}
    for prefix in sorted(all_prefixes):
        prefix_counts[prefix] = {}
        for year in years:
            cs = concepts_by_year[year]
            total = sum(1 for c in cs.all if c.startswith(prefix + ":"))
            tb = sum(1 for c in cs.text_block if c.startswith(prefix + ":"))
            non_tb = total - tb
            prefix_counts[prefix][year] = (total, tb, non_tb)

    year_cols = "  ".join(f"{y:>14d}" for y in years)
    sub_header = "  ".join(f"{'全体':>4s}/{'TB':>3s}/{'非TB':>4s}" for _ in years)
    print(f"{'prefix':<20s}  {year_cols}")
    print(f"{'':20s}  {sub_header}")
    print("-" * (22 + 16 * len(years)))

    for prefix in sorted(
        prefix_counts,
        key=lambda p: -prefix_counts[p].get(base_year, (0, 0, 0))[0],
    ):
        counts = prefix_counts[prefix]
        if all(v[0] == 0 for v in counts.values()):
            continue
        cols = "  ".join(
            f"{counts.get(y, (0, 0, 0))[0]:>4},{counts.get(y, (0, 0, 0))[1]:>3},"
            f"{counts.get(y, (0, 0, 0))[2]:>4}"
            for y in years
        )
        print(f"{prefix:<20s}  {cols}")

    # ────────────────────────────────────────────────────────
    # 5. サマリファイル保存
    # ────────────────────────────────────────────────────────
    summary_path = output_dir / "summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("タクソノミ概念 ID 差分統計サマリ\n\n")
        for line in summary_lines:
            f.write(line + "\n")
        f.write(f"\n基準年度: {base_year}\n")
        for year in years:
            cs = concepts_by_year[year]
            f.write(
                f"  {year}年: {len(cs.all):,} 概念 "
                f"(TB={len(cs.text_block):,}, 非TB={len(cs.non_text_block):,})\n"
            )

    print(f"\nサマリ保存: {summary_path}")
    print("完了")


if __name__ == "__main__":
    main()

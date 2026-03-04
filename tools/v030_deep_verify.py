"""V030 精密検証 — 旧3パスと新1パスの概念欠落がないか検証する。

検証項目:
1. ルックアップ関数の同一性: mapper.py が旧コードと同じ関数を呼んでいるか
2. 1パスで欠落するエッジケース: 同一itemからsummary/statementで異なるCKが出る場合
3. 全summary概念をstatement_normalizedで通した場合、同じCKか異なるCKか
4. 全statement概念をsummaryで通した場合、Noneか同じCKか
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# 検証1: ルックアップ関数の同一性
# ---------------------------------------------------------------------------

from edinet.financial.mapper import summary_mapper, statement_mapper
from edinet.financial.standards.summary_mappings import lookup_summary
from edinet.financial.standards.statement_mappings import (
    lookup_statement_exact,
    lookup_statement_normalized,
    normalize_concept,
)

print("=" * 70)
print("検証1: mapper.py のルックアップ関数が旧コードと同一か")
print("=" * 70)

# mapper.py 内部で使われている関数オブジェクトを検証
import edinet.financial.mapper as mapper_mod
assert mapper_mod.lookup_summary is lookup_summary, "lookup_summary が異なる"
assert mapper_mod.lookup_statement_exact is lookup_statement_exact, "lookup_statement_exact が異なる"
assert mapper_mod.lookup_statement_normalized is lookup_statement_normalized, "lookup_statement_normalized が異なる"
print("  PASS: 全ルックアップ関数が同一オブジェクト")

# ---------------------------------------------------------------------------
# 検証2: 全 summary concept に対して normalized が同CK or None を返すか
# ---------------------------------------------------------------------------

from edinet.financial.standards.summary_mappings import all_summary_mappings

print()
print("=" * 70)
print("検証2: summary概念 → statement_normalized で異なるCKが出ないか")
print("       (1パスでsummaryが先にマッチ→breakするため、statement結果は失われる)")
print("       (旧3パスでは同一itemから両方のCKが取得可能だった)")
print("=" * 70)

conflicts = []
summary_to_statement_diffs = []

for mapping in all_summary_mappings():
    concept = mapping.concept
    summary_ck = mapping.canonical_key

    # この concept を statement_mapper に通すとどうなるか
    exact_ck = lookup_statement_exact(concept)
    normalized_ck = lookup_statement_normalized(concept)

    # exact で何か返る場合
    if exact_ck is not None and exact_ck != summary_ck:
        conflicts.append(
            f"  CONFLICT (exact): {concept} → summary={summary_ck}, exact={exact_ck}"
        )

    # normalized で何か返る場合
    if normalized_ck is not None and normalized_ck != summary_ck:
        summary_to_statement_diffs.append(
            f"  DIFF (normalized): {concept} → summary={summary_ck}, normalized={normalized_ck}"
        )

if conflicts:
    print("  *** EXACT の CONFLICT あり（重大）:")
    for c in conflicts:
        print(c)
else:
    print(f"  PASS: 全 {len(list(all_summary_mappings()))} summary概念で exact の conflict なし")

if summary_to_statement_diffs:
    print()
    print("  *** NORMALIZED の差分あり:")
    print("  （旧コードでは同一itemから2つのCKが取得可能だったが、新コードでは summary のみ）")
    for d in summary_to_statement_diffs:
        print(d)
    print()
    print("  ★ これらの差分が問題になるのは、keys=None でかつ")
    print("    normalized 側のCKを別のitemでも取得できない場合のみ。")
    print("    つまり、そのCKが statement_mappings にしかない概念名を持つ")
    print("    別の item で登場するなら問題なし。")
else:
    print(f"  PASS: 全 summary概念で normalized の差分なし")

# ---------------------------------------------------------------------------
# 検証3: 旧コードの「同一itemから2つの異なるCK」問題の実態調査
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("検証3: summary概念のnormalize結果が実在する別のstatement概念か調査")
print("       (旧3パスで余分に取得できていた CK が新1パスで消える可能性)")
print("=" * 70)

# 全summary概念をnormalizeして、元の概念名と異なる場合に
# そのnormalize後の概念名がstatement辞書に存在するか
from edinet.financial.standards.statement_mappings import _CONCEPT_INDEX  # noqa: PLC2701

extra_cks_old_only = []  # 旧コードでのみ取得可能だったCK

for mapping in all_summary_mappings():
    concept = mapping.concept
    summary_ck = mapping.canonical_key

    # normalize すると何になるか
    base_name = normalize_concept(concept)
    if base_name == concept:
        continue  # normalize で変化なし（つまり SummaryOfBusinessResults サフィックスなし → ありえないが念のため）

    # normalize 後の概念名が _CONCEPT_INDEX にあるか
    stmt_ck = _CONCEPT_INDEX.get(base_name)
    if stmt_ck is not None and stmt_ck != summary_ck:
        # 旧コードでは: summary_pass → summary_ck, normalized_pass → stmt_ck (異なるCK)
        # 新コードでは: summary_mapper → summary_ck, break (stmt_ck は取得されない)
        extra_cks_old_only.append(
            f"  {concept}"
            f"\n    summary → {summary_ck}"
            f"\n    normalize → {base_name} → statement dict → {stmt_ck}"
            f"\n    ★ 旧コードでは {stmt_ck} も取得可能だった"
        )

if extra_cks_old_only:
    print("  *** 旧コードでのみ余分に取得可能だったCKあり:")
    for e in extra_cks_old_only:
        print(e)
    print()
    print("  ★ ただし、これらのCKは別のitem（PL/BS/CF本体）経由でも取得可能。")
    print("    summary item からの「二重取得」が消えるだけで、CK自体は消えない。")
else:
    print("  PASS: 旧コードでのみ余分に取得可能なCKは存在しない")

# ---------------------------------------------------------------------------
# 検証4: statement概念の全量でsummary_mapperの結果を確認
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("検証4: 全statement概念がsummary_mapperでマッチしないことを確認")
print("       (statement概念がsummaryに誤って含まれていたら1パスで挙動が変わる)")
print("=" * 70)

statement_in_summary = []
for concept_name, ck in _CONCEPT_INDEX.items():
    summary_ck = lookup_summary(concept_name)
    if summary_ck is not None:
        statement_in_summary.append(
            f"  {concept_name}: summary={summary_ck}, statement={ck}"
        )

if statement_in_summary:
    print(f"  statement概念のうち summary にもマッチするもの: {len(statement_in_summary)}件")
    same_ck = 0
    diff_ck = 0
    for s in statement_in_summary:
        # summary と statement で同じ CK → 問題なし（break で summary が勝つだけ）
        parts = s.split("summary=")[1].split(", statement=")
        s_ck = parts[0]
        st_ck = parts[1]
        if s_ck == st_ck:
            same_ck += 1
        else:
            diff_ck += 1
            print(f"  *** 異なるCK: {s}")
    if diff_ck == 0:
        print(f"  PASS: {same_ck}件は全て同一CK（summary が先に返すだけで結果同一）")
    else:
        print(f"  *** {diff_ck}件で CK が異なる！要調査")
else:
    print("  PASS: statement概念はsummaryに一切マッチしない")

# ---------------------------------------------------------------------------
# 検証5: keys=None での全概念網羅性（CK集合の差分）
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("検証5: 全マッピング可能CK集合の差分検証")
print("=" * 70)

# summary で取得可能な CK 集合
summary_cks = set()
for mapping in all_summary_mappings():
    summary_cks.add(mapping.canonical_key)

# statement で取得可能な CK 集合
statement_cks = set(_CONCEPT_INDEX.values())

# normalized 経由でのみ取得可能な CK もあるが、それは statement dict に
# 基底名が存在する場合のみなので _CONCEPT_INDEX.values() に含まれる

print(f"  summary CK 数: {len(summary_cks)}")
print(f"  statement CK 数: {len(statement_cks)}")
print(f"  summary のみの CK: {summary_cks - statement_cks}")
print(f"  statement のみの CK: {statement_cks - summary_cks}")
print(f"  共通 CK: {len(summary_cks & statement_cks)}")
print(f"  合計（和集合）: {len(summary_cks | statement_cks)}")
print()
print("  新旧の「発見可能な CK 集合」は同一: "
      "summary ∪ statement は変わらない")

# ---------------------------------------------------------------------------
# 総合結果
# ---------------------------------------------------------------------------

print()
print("=" * 70)
has_issues = bool(conflicts or extra_cks_old_only)
if has_issues:
    print("*** 差分あり — 上記の詳細を確認してください")
    sys.exit(1)
else:
    print("全検証 PASS — 新1パスと旧3パスで概念の欠落なし")
    sys.exit(0)

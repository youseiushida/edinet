"""Wave 1 E2E 探索: 一般事業会社の有報を探す。

投資信託ではなく、一般事業会社（連結あり・shares/per_share あり・提出者タクソノミあり）
の有報が取得できる日付と doc_id を特定する。
"""

from __future__ import annotations

import os
import sys

from edinet import DocType, configure, documents
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl.dei import AccountingStandard
from edinet.xbrl.units import DivideMeasure, SimpleMeasure, structure_units
from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl._namespaces import classify_namespace, NamespaceCategory

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)


def probe_date(target_date: str):
    """指定日付の有報を分析し、一般事業会社を探す。"""
    print(f"\n{'='*70}")
    print(f"日付: {target_date}")
    print(f"{'='*70}")

    filings = documents(target_date, doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    xbrl_filings = [f for f in filings if f.has_xbrl]
    print(f"  有報(XBRL付き): {len(xbrl_filings)} 件")

    if not xbrl_filings:
        print("  → 該当なし")
        return []

    good_candidates = []

    for f in xbrl_filings[:20]:  # 最大20件
        try:
            xbrl_path, xbrl_bytes = f.fetch()
            parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
            dei = extract_dei(parsed.facts)
            unit_map = structure_units(parsed.units)
            ctx_map = structure_contexts(parsed.contexts)
            coll = ContextCollection(ctx_map)

            # 分析
            has_shares = any(
                isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "shares"
                for u in unit_map.values()
            )
            has_divide = any(isinstance(u.measure, DivideMeasure) for u in unit_map.values())
            has_consolidated = dei.has_consolidated or False
            cons_count = len(coll.filter_consolidated())
            non_cons_count = len(coll.filter_non_consolidated())

            # 名前空間分析
            ns_set = {fact.namespace_uri for fact in parsed.facts if fact.namespace_uri}
            filer_ns = [uri for uri in ns_set if classify_namespace(uri).category == NamespaceCategory.FILER_TAXONOMY]
            std_modules = sorted({
                classify_namespace(uri).module_name
                for uri in ns_set
                if classify_namespace(uri).module_name
            })

            is_general = (
                has_consolidated
                and len(ctx_map) > 20
                and has_shares
            )

            marker = "★" if is_general else " "
            print(
                f"  {marker} {f.doc_id} | {dei.filer_name_ja or f.filer_name or '?'}"
                f" | 基準={dei.accounting_standards!r}"
                f" | 連結={has_consolidated}"
                f" | ctx={len(ctx_map)}"
                f" | units={len(unit_map)}"
                f" | shares={has_shares}"
                f" | divide={has_divide}"
                f" | filer_ns={len(filer_ns)}"
                f" | modules={std_modules}"
            )

            if is_general:
                good_candidates.append({
                    "doc_id": f.doc_id,
                    "filer_name": dei.filer_name_ja or f.filer_name,
                    "edinet_code": dei.edinet_code,
                    "accounting_standards": str(dei.accounting_standards),
                    "ctx_count": len(ctx_map),
                    "unit_count": len(unit_map),
                    "has_divide": has_divide,
                    "filer_ns_count": len(filer_ns),
                    "cons_count": cons_count,
                    "non_cons_count": non_cons_count,
                    "fact_count": parsed.fact_count,
                })
        except Exception as e:
            print(f"  ! {f.doc_id}: ERROR {e}")

    return good_candidates


if __name__ == "__main__":
    # 一般事業会社の有報が多い日付候補を探す
    # 3月決算企業の有報は6月下旬に集中するが、直近で確認
    dates_to_probe = [
        "2026-02-27",  # 昨日
        "2026-02-26",
        "2026-02-25",
        "2026-02-20",
        "2026-02-13",
        "2026-01-30",
    ]

    all_candidates = []
    for d in dates_to_probe:
        candidates = probe_date(d)
        all_candidates.extend(candidates)
        if len(all_candidates) >= 3:
            break  # 十分な候補が見つかった

    print(f"\n{'='*70}")
    print(f"一般事業会社の有報候補: {len(all_candidates)} 件")
    print(f"{'='*70}")
    for c in all_candidates:
        print(
            f"  {c['doc_id']} | {c['filer_name']}"
            f" | facts={c['fact_count']}, ctx={c['ctx_count']}, units={c['unit_count']}"
            f" | divide={c['has_divide']}, filer_ns={c['filer_ns_count']}"
        )

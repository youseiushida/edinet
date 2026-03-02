"""Wave 1 E2E 探索2: 一般事業会社を書類種別を広げて探す。

有報(120)以外にも半期報告書(140)や訂正有報(130)を含めて、
一般事業会社（連結あり・jpcrp タクソノミ使用）を探す。
また、6月の有報提出ピークも探す。
"""

from __future__ import annotations

import os
import sys

from edinet import DocType, configure, documents
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl.units import DivideMeasure, SimpleMeasure, structure_units
from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl._namespaces import classify_namespace, NamespaceCategory

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)


def probe_all_types(target_date: str, max_check: int = 30):
    """全書類種別で一般事業会社を探す。"""
    print(f"\n{'='*70}")
    print(f"日付: {target_date} (全書類種別)")
    print(f"{'='*70}")

    filings = documents(target_date)
    xbrl_filings = [f for f in filings if f.has_xbrl]
    print(f"  XBRL付き書類: {len(xbrl_filings)} 件")

    # 書類種別の分布
    type_dist: dict[str, int] = {}
    for f in xbrl_filings:
        key = f.doc_type_label_ja or f.doc_type_code or "?"
        type_dist[key] = type_dist.get(key, 0) + 1
    print(f"  書類種別分布:")
    for k, v in sorted(type_dist.items(), key=lambda x: -x[1]):
        print(f"    {k}: {v}")

    # jpcrp を使っている書類を探す
    checked = 0
    for f in xbrl_filings:
        if checked >= max_check:
            break
        try:
            xbrl_path, xbrl_bytes = f.fetch()
            parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
            dei = extract_dei(parsed.facts)
            unit_map = structure_units(parsed.units)

            ns_set = {fact.namespace_uri for fact in parsed.facts if fact.namespace_uri}
            std_modules = sorted({
                classify_namespace(uri).module_name
                for uri in ns_set
                if classify_namespace(uri).module_name
            })

            has_jpcrp = any("jpcrp" in m for m in std_modules)
            has_shares = any(
                isinstance(u.measure, SimpleMeasure) and u.measure.local_name == "shares"
                for u in unit_map.values()
            )
            has_divide = any(isinstance(u.measure, DivideMeasure) for u in unit_map.values())

            if has_jpcrp or has_shares or has_divide or len(unit_map) > 3:
                marker = "★"
            else:
                marker = " "

            doc_label = f.doc_type_label_ja or f.doc_type_code or "?"
            print(
                f"  {marker} {f.doc_id} [{doc_label}]"
                f" | {dei.filer_name_ja or f.filer_name or '?'}"
                f" | 連結={dei.has_consolidated}"
                f" | ctx={len(structure_contexts(parsed.contexts))}"
                f" | units={len(unit_map)}({','.join(u.unit_id for u in unit_map.values())})"
                f" | modules={std_modules}"
            )
            checked += 1
        except Exception as e:
            print(f"  ! {f.doc_id}: {e}")
            checked += 1


if __name__ == "__main__":
    # 6月下旬（3月決算の有報ピーク）は過去データ
    # 直近で一般事業会社が提出する書類を探す
    dates = [
        "2025-06-27",  # 3月決算有報の提出ピーク（去年）
        "2025-06-26",
    ]

    for d in dates:
        probe_all_types(d)

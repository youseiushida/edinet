"""Day 14 全書類タイプ スイープテスト。

has_xbrl=True の全書類タイプ（最大38種）に対して
パイプラインを1件ずつ通し、クラッシュや異常を検出する。

Usage:
    EDINET_API_KEY=... uv run python tools/day14_sweep.py
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

import edinet

api_key = os.environ.get("EDINET_API_KEY")
if not api_key:
    print("ERROR: EDINET_API_KEY 環境変数を設定してください。")
    sys.exit(1)
edinet.configure(api_key=api_key)

from edinet import documents  # noqa: E402
from edinet.api.download import (  # noqa: E402
    download_document,
    extract_primary_xbrl,
    list_zip_members,
    extract_zip_member,
)
from edinet.xbrl.parser import parse_xbrl_facts  # noqa: E402
from edinet.xbrl.contexts import structure_contexts  # noqa: E402
from edinet.xbrl.taxonomy import TaxonomyResolver, LabelSource  # noqa: E402
from edinet.xbrl.facts import build_line_items  # noqa: E402
from edinet.models.doc_types import OFFICIAL_CODES  # noqa: E402

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
TAXONOMY_ROOT = os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    "/mnt/c/Users/nezow/Downloads/ALL_20251101",
)
# 直近何日間のデータを探索するか
LOOKBACK_DAYS = 30


def find_filer_taxonomy_files(zip_bytes: bytes) -> dict[str, bytes]:
    """ZIP 内から提出者別タクソノミファイルを探して返す。"""
    members = list_zip_members(zip_bytes)
    result: dict[str, bytes] = {}

    for name in members:
        lower = name.lower()
        if "publicdoc/" not in lower.replace("\\", "/"):
            continue
        if lower.endswith("_lab.xml") and "_lab-en" not in lower:
            result["lab"] = extract_zip_member(zip_bytes, name)
        elif lower.endswith("_lab-en.xml"):
            result["lab_en"] = extract_zip_member(zip_bytes, name)
        elif lower.endswith(".xsd") and "audit" not in lower:
            if "xsd" not in result:
                result["xsd"] = extract_zip_member(zip_bytes, name)

    return result


def find_one_xbrl_filing(doc_type: str, lookback: int) -> object | None:
    """指定 doc_type で has_xbrl=True の filing を1件探す。"""
    today = date(2026, 2, 25)
    for offset in range(lookback):
        d = today - timedelta(days=offset)
        date_str = d.strftime("%Y-%m-%d")
        try:
            filings = documents(date_str, doc_type=doc_type)
        except Exception:
            continue
        for f in filings:
            if f.has_xbrl:
                return f
        time.sleep(0.3)
    return None


def run_pipeline_for_filing(filing: object, resolver: TaxonomyResolver) -> dict:
    """1件の filing に対してフルパイプラインを実行する。"""
    result: dict = {
        "doc_id": filing.doc_id,
        "filer_name": filing.filer_name,
        "doc_type_code": filing.doc_type_code,
        "status": "UNKNOWN",
        "error": None,
        "stats": {},
    }

    try:
        # ZIP ダウンロード
        zip_bytes = download_document(filing.doc_id, file_type="1")

        # 代表 XBRL 取得
        primary = extract_primary_xbrl(zip_bytes)
        if primary is None:
            result["status"] = "FAIL"
            result["error"] = "No primary XBRL found in ZIP"
            return result
        xbrl_path, xbrl_bytes = primary
        result["stats"]["xbrl_path"] = xbrl_path
        result["stats"]["xbrl_size"] = len(xbrl_bytes)

        # 提出者タクソノミ
        filer_files = find_filer_taxonomy_files(zip_bytes)
        resolver.clear_filer_labels()
        if filer_files:
            resolver.load_filer_labels(
                lab_xml_bytes=filer_files.get("lab"),
                lab_en_xml_bytes=filer_files.get("lab_en"),
                xsd_bytes=filer_files.get("xsd"),
            )

        # parse_xbrl_facts
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        result["stats"]["raw_facts"] = len(parsed.facts)
        result["stats"]["raw_contexts"] = len(parsed.contexts)
        result["stats"]["raw_units"] = len(parsed.units)

        # structure_contexts
        ctx_map = structure_contexts(parsed.contexts)
        result["stats"]["structured_contexts"] = len(ctx_map)

        # build_line_items
        items = build_line_items(parsed.facts, ctx_map, resolver)
        result["stats"]["line_items"] = len(items)

        # 統計
        label_sources = Counter(item.label_ja.source for item in items)
        ns_counts = Counter(item.namespace_uri for item in items)
        total = len(items)
        fallback_count = label_sources.get(LabelSource.FALLBACK, 0)

        result["stats"]["numeric"] = sum(
            1 for item in items if isinstance(item.value, Decimal)
        )
        result["stats"]["text"] = sum(
            1 for item in items if isinstance(item.value, str)
        )
        result["stats"]["nil"] = sum(
            1 for item in items if item.value is None
        )
        result["stats"]["dimension_items"] = sum(
            1 for item in items if item.dimensions
        )
        result["stats"]["label_sources"] = {
            src.value: cnt for src, cnt in label_sources.items()
        }
        result["stats"]["fallback_pct"] = (
            f"{fallback_count / total * 100:.1f}%"
            if total > 0
            else "N/A"
        )
        result["stats"]["namespaces"] = [
            ns.split("/")[-1] if "/" in ns else ns
            for ns, _ in ns_counts.most_common(5)
        ]

        # 異常検知フラグ
        warnings_list: list[str] = []
        if total == 0:
            warnings_list.append("WARN: LineItem が 0 件")
        if total > 0 and fallback_count / total > 0.5:
            warnings_list.append(
                f"WARN: FALLBACK 率 {fallback_count / total * 100:.1f}% (> 50%)"
            )
        if result["stats"]["raw_facts"] != result["stats"]["line_items"]:
            warnings_list.append(
                f"WARN: Fact数 {result['stats']['raw_facts']} != LineItem数 {result['stats']['line_items']}"
            )
        result["warnings"] = warnings_list

        result["status"] = "PASS"

    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()

    return result


def main() -> int:
    """メイン関数。"""
    print("=" * 80)
    print("Day 14 全書類タイプ スイープテスト")
    print(f"対象: OFFICIAL_CODES {len(OFFICIAL_CODES)} 種, lookback={LOOKBACK_DAYS}日")
    print("=" * 80)

    resolver = TaxonomyResolver(TAXONOMY_ROOT)
    print(f"TaxonomyResolver version: {resolver.taxonomy_version}\n")

    results: list[dict] = []
    found_types: list[str] = []
    no_xbrl_types: list[str] = []
    not_found_types: list[str] = []

    for i, code in enumerate(OFFICIAL_CODES, 1):
        from edinet.models.doc_types import DocType
        dt = DocType.from_code(code)
        name_ja = dt.name_ja if dt else code
        print(f"[{i:2d}/{len(OFFICIAL_CODES)}] {code} ({name_ja}) ... ", end="", flush=True)

        filing = find_one_xbrl_filing(code, LOOKBACK_DAYS)
        if filing is None:
            print("SKIP (has_xbrl=True の filing なし)")
            not_found_types.append(f"{code} ({name_ja})")
            continue

        print(f"found: {filing.filer_name} ({filing.doc_id}) ... ", end="", flush=True)
        found_types.append(code)

        result = run_pipeline_for_filing(filing, resolver)
        result["name_ja"] = name_ja
        results.append(result)

        if result["status"] == "PASS":
            stats = result["stats"]
            warn_str = f" [{', '.join(result['warnings'])}]" if result["warnings"] else ""
            print(
                f"PASS  "
                f"Facts={stats['raw_facts']}, Items={stats['line_items']}, "
                f"FB={stats['fallback_pct']}, NS={stats['namespaces'][:3]}"
                f"{warn_str}"
            )
        elif result["status"] == "FAIL":
            print(f"FAIL  {result['error']}")
            if result.get("traceback"):
                for line in result["traceback"].splitlines()[-3:]:
                    print(f"         {line}")
        else:
            print(f"{result['status']}  {result.get('error', '')}")

    # サマリー
    print(f"\n{'=' * 80}")
    print("サマリー")
    print(f"{'=' * 80}")
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    print(f"  書類タイプ全体: {len(OFFICIAL_CODES)} 種")
    print(f"  XBRL あり (テスト実行): {len(found_types)} 種")
    print(f"  XBRL なし (スキップ):   {len(not_found_types)} 種")
    print(f"  PASS: {pass_count}, FAIL: {fail_count}")

    if fail_count > 0:
        print("\n  --- FAIL ---")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    {r['doc_type_code']} ({r.get('name_ja','')}): {r['error']}")

    # 警告があるもの
    warned = [r for r in results if r.get("warnings")]
    if warned:
        print("\n  --- 警告 ---")
        for r in warned:
            print(f"    {r['doc_type_code']} ({r.get('name_ja','')}): {', '.join(r['warnings'])}")

    # XBRL なしリスト
    if not_found_types:
        print(f"\n  --- has_xbrl=True の filing が見つからなかった書類タイプ ({len(not_found_types)} 種) ---")
        for t in not_found_types:
            print(f"    {t}")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

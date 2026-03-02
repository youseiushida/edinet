"""Day 14 拡張スイープ — 直近30日で未検出だった書類タイプの存在確認。

期間を拡大して has_xbrl=True の filing を探す。
見つかった場合はパイプラインも通す。

Usage:
    EDINET_API_KEY=... uv run python tools/day14_sweep_extended.py
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
from edinet.models.doc_types import DocType  # noqa: E402

TAXONOMY_ROOT = os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    "/mnt/c/Users/nezow/Downloads/ALL_20251101",
)

# 直近30日で見つからなかった書類タイプ
MISSING_CODES = [
    "010",  # 有価証券通知書
    "020",  # 変更通知書（有価証券通知書）
    "050",  # 届出の取下げ願い
    "060",  # 発行登録通知書
    "070",  # 変更通知書（発行登録通知書）
    "090",  # 訂正発行登録書
    "110",  # 発行登録取下届出書
    "135",  # 確認書
    "136",  # 訂正確認書
    "140",  # 四半期報告書
    "150",  # 訂正四半期報告書
    "200",  # 親会社等状況報告書
    "210",  # 訂正親会社等状況報告書
    "260",  # 公開買付撤回届出書
    "280",  # 訂正公開買付報告書
    "310",  # 対質問回答報告書
    "320",  # 訂正対質問回答報告書
    "330",  # 別途買付け禁止の特例を受けるための申出書
    "340",  # 訂正別途買付け禁止の特例を受けるための申出書
    "370",  # 基準日の届出書
    "380",  # 変更の届出書
]


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


def search_filing(doc_type: str, max_days: int = 365) -> tuple[object | None, str | None]:
    """指定書類タイプで has_xbrl=True の filing を探す。

    まず粗いサンプリング（7日おき）で探し、
    見つからなければ has_xbrl=False も含めて存在自体を確認する。

    Returns:
        (filing, search_info) のタプル。
    """
    today = date(2026, 2, 25)

    # Phase 1: 7日おきにサンプリング（has_xbrl=True を探す）
    for offset in range(0, max_days, 7):
        d = today - timedelta(days=offset)
        date_str = d.strftime("%Y-%m-%d")
        try:
            filings = documents(date_str, doc_type=doc_type)
        except Exception:
            time.sleep(0.5)
            continue

        xbrl_filings = [f for f in filings if f.has_xbrl]
        if xbrl_filings:
            return xbrl_filings[0], f"found at {date_str} (offset={offset}d)"

        # has_xbrl=False でも存在していれば記録
        if filings:
            # xbrl なしの filing はあった。もう少し探す。
            pass

        time.sleep(0.3)

    # Phase 2: 見つからなかった。存在自体の確認（30日おき）
    any_filing_found = False
    for offset in range(0, max_days, 30):
        d = today - timedelta(days=offset)
        date_str = d.strftime("%Y-%m-%d")
        try:
            filings = documents(date_str, doc_type=doc_type)
        except Exception:
            continue
        if filings:
            any_filing_found = True
            has_xbrl_count = sum(1 for f in filings if f.has_xbrl)
            if has_xbrl_count > 0:
                xbrl_f = next(f for f in filings if f.has_xbrl)
                return xbrl_f, f"found at {date_str} (phase2, offset={offset}d)"
            # has_xbrl=False のみ
            sample = filings[0]
            return None, (
                f"has_xbrl=False only at {date_str} "
                f"(例: {sample.filer_name}, {sample.doc_id})"
            )
        time.sleep(0.3)

    if any_filing_found:
        return None, "filings exist but none with has_xbrl=True"
    return None, f"no filings found in {max_days} days"


def run_pipeline(filing: object, resolver: TaxonomyResolver) -> dict:
    """パイプライン実行。"""
    result: dict = {
        "doc_id": filing.doc_id,
        "filer_name": filing.filer_name,
        "status": "UNKNOWN",
        "error": None,
        "stats": {},
    }
    try:
        zip_bytes = download_document(filing.doc_id, file_type="1")
        primary = extract_primary_xbrl(zip_bytes)
        if primary is None:
            result["status"] = "FAIL"
            result["error"] = "No primary XBRL in ZIP"
            return result
        xbrl_path, xbrl_bytes = primary

        filer_files = find_filer_taxonomy_files(zip_bytes)
        resolver.clear_filer_labels()
        if filer_files:
            resolver.load_filer_labels(
                lab_xml_bytes=filer_files.get("lab"),
                lab_en_xml_bytes=filer_files.get("lab_en"),
                xsd_bytes=filer_files.get("xsd"),
            )

        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        ctx_map = structure_contexts(parsed.contexts)
        items = build_line_items(parsed.facts, ctx_map, resolver)

        total = len(items)
        label_sources = Counter(item.label_ja.source for item in items)
        fallback_count = label_sources.get(LabelSource.FALLBACK, 0)
        ns_counts = Counter(item.namespace_uri for item in items)

        result["stats"] = {
            "facts": len(parsed.facts),
            "items": total,
            "numeric": sum(1 for i in items if isinstance(i.value, Decimal)),
            "text": sum(1 for i in items if isinstance(i.value, str)),
            "nil": sum(1 for i in items if i.value is None),
            "fallback_pct": f"{fallback_count / total * 100:.1f}%" if total > 0 else "N/A",
            "label_sources": {s.value: c for s, c in label_sources.items()},
            "namespaces": [
                ns.split("/")[-1] if "/" in ns else ns
                for ns, _ in ns_counts.most_common(5)
            ],
        }
        result["status"] = "PASS"

    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()

    return result


def main() -> int:
    """メイン関数。"""
    print("=" * 80)
    print("Day 14 拡張スイープ — 未検出書類タイプの探索")
    print(f"対象: {len(MISSING_CODES)} 種, 最大 1 年分 (365 日)")
    print("=" * 80)

    resolver = TaxonomyResolver(TAXONOMY_ROOT)

    results: list[dict] = []

    for i, code in enumerate(MISSING_CODES, 1):
        dt = DocType.from_code(code)
        name_ja = dt.name_ja if dt else code
        print(f"\n[{i:2d}/{len(MISSING_CODES)}] {code} ({name_ja})")
        print(f"  検索中...", end="", flush=True)

        filing, info = search_filing(code, max_days=365)
        print(f" {info}")

        entry = {
            "code": code,
            "name_ja": name_ja,
            "search_info": info,
            "filing": None,
            "pipeline": None,
        }

        if filing is not None:
            print(f"  → {filing.filer_name} ({filing.doc_id})")
            print(f"  パイプライン実行中...", end="", flush=True)
            pipe_result = run_pipeline(filing, resolver)
            entry["filing"] = {
                "doc_id": filing.doc_id,
                "filer_name": filing.filer_name,
            }
            entry["pipeline"] = pipe_result

            if pipe_result["status"] == "PASS":
                s = pipe_result["stats"]
                print(
                    f" PASS  Facts={s['facts']}, Items={s['items']}, "
                    f"FB={s['fallback_pct']}, NS={s['namespaces'][:3]}"
                )
            else:
                print(f" {pipe_result['status']}  {pipe_result.get('error', '')}")
                if pipe_result.get("traceback"):
                    for line in pipe_result["traceback"].splitlines()[-3:]:
                        print(f"    {line}")
        else:
            print(f"  → XBRL filing なし")

        results.append(entry)

    # サマリー
    print(f"\n{'=' * 80}")
    print("拡張スイープ サマリー")
    print(f"{'=' * 80}")

    found_xbrl = [r for r in results if r["filing"] is not None]
    not_found = [r for r in results if r["filing"] is None]
    passed = [r for r in found_xbrl if r["pipeline"] and r["pipeline"]["status"] == "PASS"]
    failed = [r for r in found_xbrl if r["pipeline"] and r["pipeline"]["status"] == "FAIL"]

    print(f"  XBRL filing 発見: {len(found_xbrl)} 種")
    print(f"    PASS: {len(passed)}")
    print(f"    FAIL: {len(failed)}")
    print(f"  XBRL filing なし: {len(not_found)} 種")

    if found_xbrl:
        print(f"\n  --- XBRL あり ---")
        for r in found_xbrl:
            status = r["pipeline"]["status"] if r["pipeline"] else "?"
            fb = r["pipeline"]["stats"].get("fallback_pct", "?") if r["pipeline"] and r["pipeline"].get("stats") else "?"
            print(f"    {r['code']} ({r['name_ja']}): {status}, FB={fb}")
            print(f"      {r['search_info']}")

    if not_found:
        print(f"\n  --- XBRL なし (5年間) ---")
        for r in not_found:
            print(f"    {r['code']} ({r['name_ja']})")
            print(f"      {r['search_info']}")

    if failed:
        print(f"\n  --- FAIL 詳細 ---")
        for r in failed:
            print(f"    {r['code']} ({r['name_ja']}): {r['pipeline']['error']}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""日経225 CKカバレッジ再調査（v5 — CK/map更新後）。

v4 の results から doc_id を再利用して検索フェーズをスキップし、
最新コードでの XBRL 再パースのみ行う。

Usage:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/nikkei225_coverage_v5.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import edinet
from edinet.financial.standards.canonical_keys import CK

V4_RESULTS = Path("reports/nikkei225_coverage_v4.json")
V5_RESULTS = Path("reports/nikkei225_coverage_v5.json")
MAX_CONCURRENT = 16

ALL_CK_VALUES = sorted(str(ck) for ck in CK)


def _make_filing(doc_id: str) -> edinet.Filing:
    """doc_id から最小限の Filing を構築する。"""
    from datetime import datetime

    return edinet.Filing.model_construct(
        seq_number=0,
        doc_id=doc_id,
        doc_type_code="120",
        ordinance_code=None,
        form_code=None,
        edinet_code=None,
        sec_code=None,
        jcn=None,
        filer_name=None,
        fund_code=None,
        submit_date_time=datetime(2024, 6, 1),
        period_start=None,
        period_end=None,
        doc_description=None,
        issuer_edinet_code=None,
        subject_edinet_code=None,
        subsidiary_edinet_code=None,
        current_report_reason=None,
        parent_doc_id=None,
        ope_date_time=None,
        withdrawal_status="0",
        doc_info_edit_status="0",
        disclosure_status="0",
        has_xbrl=True,
        has_pdf=False,
        has_attachment=False,
        has_english=False,
        has_csv=False,
        legal_status="0",
    )


def process_one(ticker: str, doc_id: str, company: str) -> dict:
    """1つの doc_id を再処理。"""
    try:
        filing = _make_filing(doc_id)
        stmts = filing.xbrl()
        extracted = edinet.extract_values(stmts)
        covered = sorted(k for k, v in extracted.items() if v is not None)
        missing = sorted(set(ALL_CK_VALUES) - set(covered))

        mapper_counts: dict[str, int] = {}
        for v in extracted.values():
            if v is not None:
                name = v.mapper_name or "unknown"
                mapper_counts[name] = mapper_counts.get(name, 0) + 1

        return {
            "ticker": ticker,
            "company": company,
            "doc_id": doc_id,
            "covered_count": len(covered),
            "missing_count": len(missing),
            "total_ck": len(ALL_CK_VALUES),
            "coverage_pct": round(len(covered) / len(ALL_CK_VALUES) * 100, 1),
            "covered": covered,
            "missing": missing,
            "mapper_counts": mapper_counts,
            "status": "ok",
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "company": company,
            "doc_id": doc_id,
            "status": "error",
            "error": str(e),
        }


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY")
    tax_root = os.environ.get("EDINET_TAXONOMY_ROOT")
    if not api_key or not tax_root:
        print("EDINET_API_KEY / EDINET_TAXONOMY_ROOT が未設定", file=sys.stderr)
        sys.exit(1)

    edinet.configure(api_key=api_key, taxonomy_path=Path(tax_root))

    if not V4_RESULTS.exists():
        print(f"{V4_RESULTS} が見つかりません", file=sys.stderr)
        sys.exit(1)

    old_data: dict[str, dict] = json.loads(V4_RESULTS.read_text())
    print(f"入力: {V4_RESULTS} ({len(old_data)} 銘柄)")

    to_process = {
        t: r
        for t, r in old_data.items()
        if r.get("status") in ("ok", "error") and r.get("doc_id")
    }
    print(f"再処理対象: {len(to_process)} 銘柄")

    results: dict[str, dict] = {}
    if V5_RESULTS.exists():
        try:
            results = json.loads(V5_RESULTS.read_text())
            print(f"既存v5結果: {len(results)} 銘柄（スキップ）")
        except Exception:
            pass

    for t, r in old_data.items():
        if r.get("status") == "not_found":
            results[t] = r

    remaining = {t: r for t, r in to_process.items() if t not in results}
    if not remaining:
        print("全銘柄処理済み")
    else:
        print(f"処理中: {len(remaining)} 銘柄 (並列数={MAX_CONCURRENT})")
        sem = asyncio.Semaphore(MAX_CONCURRENT)
        processed = [0]
        total = len(remaining)
        lock = asyncio.Lock()

        async def run_one(ticker: str, info: dict) -> None:
            async with sem:
                result = await asyncio.to_thread(
                    process_one,
                    ticker,
                    info["doc_id"],
                    info.get("company", "?"),
                )
                async with lock:
                    results[ticker] = result
                    processed[0] += 1
                    status = "ok" if result.get("status") == "ok" else "ERROR"
                    pct = result.get("coverage_pct", "?")
                    mc = result.get("mapper_counts", {})
                    print(
                        f"  [{processed[0]:3d}/{total}] {ticker} "
                        f"{result.get('company', '?')[:20]:20s} "
                        f"{pct:>5}% [{status}] {mc}",
                        flush=True,
                    )
                    if processed[0] % 10 == 0 or processed[0] == total:
                        V5_RESULTS.parent.mkdir(parents=True, exist_ok=True)
                        V5_RESULTS.write_text(
                            json.dumps(results, ensure_ascii=False, indent=2)
                        )

        t0 = time.perf_counter()
        tasks = [run_one(t, r) for t, r in remaining.items()]
        await asyncio.gather(*tasks)
        t1 = time.perf_counter()
        print(f"\n完了 ({t1 - t0:.1f}秒)")

    V5_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    V5_RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    _print_comparison(old_data, results)
    print(f"\n結果ファイル: {V5_RESULTS}")


def _print_comparison(old_data: dict, new_data: dict) -> None:
    """v4 と v5 の比較サマリーを表示する。"""
    print("\n" + "=" * 70)
    print("v4 vs v5 比較")
    print("=" * 70)

    v4_ok = {t: r for t, r in old_data.items() if r.get("status") == "ok"}
    v5_ok = {t: r for t, r in new_data.items() if r.get("status") == "ok"}

    both = sorted(set(v4_ok.keys()) & set(v5_ok.keys()))
    n = len(both)
    print(f"比較可能銘柄数: {n}")

    if not both:
        return

    total_ck = len(ALL_CK_VALUES)
    v4_avg = sum(v4_ok[t]["covered_count"] for t in both) / n
    v5_avg = sum(v5_ok[t]["covered_count"] for t in both) / n
    v4_pct = v4_avg / total_ck * 100
    v5_pct = v5_avg / total_ck * 100
    print(f"全CK数: {total_ck}")
    print(f"v4 平均カバー: {v4_avg:.1f} CK ({v4_pct:.1f}%)")
    print(f"v5 平均カバー: {v5_avg:.1f} CK ({v5_pct:.1f}%)")
    print(f"改善: {v5_avg - v4_avg:+.1f} CK ({v5_pct - v4_pct:+.1f}pp)")

    # --- 変化銘柄 ---
    changes = []
    for t in both:
        v4c = v4_ok[t]["covered_count"]
        v5c = v5_ok[t]["covered_count"]
        if v5c != v4c:
            changes.append((t, v5_ok[t].get("company", "?"), v4c, v5c, v5c - v4c))
    changes.sort(key=lambda x: -x[4])
    if changes:
        print(f"\n--- 変化銘柄 top 30 ({len(changes)} 社中) ---")
        for t, co, v4c, v5c, diff in changes[:30]:
            print(f"  {t} {co[:25]:25s} {v4c}->{v5c} ({diff:+d})")

    # --- マッパー別 ---
    v4_mapper: dict[str, int] = {}
    v5_mapper: dict[str, int] = {}
    for t in both:
        for m, c in v4_ok[t].get("mapper_counts", {}).items():
            v4_mapper[m] = v4_mapper.get(m, 0) + c
        for m, c in v5_ok[t].get("mapper_counts", {}).items():
            v5_mapper[m] = v5_mapper.get(m, 0) + c

    all_mappers = sorted(set(v4_mapper) | set(v5_mapper))
    if all_mappers:
        print(f"\n--- マッパー別 CK 総数 ({n} 社合計) ---")
        print(f"  {'mapper':35s} {'v4':>6s} {'v5':>6s} {'diff':>6s}")
        for m in sorted(all_mappers, key=lambda x: -v5_mapper.get(x, 0)):
            v4c = v4_mapper.get(m, 0)
            v5c = v5_mapper.get(m, 0)
            d = v5c - v4c
            print(f"  {m:35s} {v4c:6d} {v5c:6d} {d:+6d}")

    # --- CK別変化 ---
    v4_ck: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
    v5_ck: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
    for t in both:
        for ck in v4_ok[t].get("covered", []):
            if ck in v4_ck:
                v4_ck[ck] += 1
        for ck in v5_ok[t].get("covered", []):
            if ck in v5_ck:
                v5_ck[ck] += 1

    improved_cks = [
        (ck, v4_ck.get(ck, 0), v5_ck[ck])
        for ck in ALL_CK_VALUES
        if v5_ck[ck] > v4_ck.get(ck, 0)
    ]
    if improved_cks:
        improved_cks.sort(key=lambda x: -(x[2] - x[1]))
        print(f"\n--- 改善 CK ({len(improved_cks)} 個) ---")
        for ck, v4c, v5c in improved_cks:
            print(f"  {ck:45s} {v4c:3d}->{v5c:3d} (+{v5c - v4c:2d}, {v5c / n * 100:.1f}%)")

    # ============================================================
    # README用: カバレッジ帯域別CK一覧
    # ============================================================
    print(f"\n{'=' * 70}")
    print(f"README用 カバレッジ帯域別CK一覧（{n} 社中、v5）")
    print(f"{'=' * 70}")

    bands = [
        ("100%", 100.0, 100.01),
        ("[99%, 100%)", 99.0, 100.0),
        ("[96%, 99%)", 96.0, 99.0),
        ("[90%, 96%)", 90.0, 96.0),
        ("[80%, 90%)", 80.0, 90.0),
        ("[50%, 80%)", 50.0, 80.0),
        ("[30%, 50%)", 30.0, 50.0),
        ("[0%, 30%)", 0.0, 30.0),
    ]

    for band_label, lo, hi in bands:
        cks_in_band = []
        for ck in sorted(ALL_CK_VALUES):
            cnt = v5_ck.get(ck, 0)
            pct = cnt / n * 100
            if lo <= pct < hi or (hi > 100 and pct == 100.0):
                cks_in_band.append((ck, cnt, pct))
        cks_in_band.sort(key=lambda x: (-x[2], x[0]))

        print(f"\n### {band_label} カバレッジ ({len(cks_in_band)} CK)")
        if cks_in_band:
            print(f"  {'CK':45s} {'社数':>5s} {'率':>7s}")
            for ck, cnt, pct in cks_in_band:
                print(f"  {ck:45s} {cnt:3d}/{n} ({pct:5.1f}%)")
        else:
            print("  (なし)")

    # --- 新CK（v4に存在しなかったCK） ---
    new_cks = [ck for ck in ALL_CK_VALUES if ck not in v4_ck]
    if new_cks:
        print(f"\n--- 新規CK（v5で追加、{len(new_cks)} 個） ---")
        for ck in new_cks:
            cnt = v5_ck.get(ck, 0)
            pct = cnt / n * 100
            print(f"  {ck:45s} {cnt:3d}/{n} ({pct:5.1f}%)")

    # --- 退化チェック ---
    degraded = [
        (ck, v4_ck.get(ck, 0), v5_ck[ck])
        for ck in ALL_CK_VALUES
        if ck in v4_ck and v5_ck[ck] < v4_ck[ck]
    ]
    if degraded:
        print(f"\n--- ⚠ 退化 CK ({len(degraded)} 個) ---")
        for ck, v4c, v5c in degraded:
            print(f"  {ck:45s} {v4c:3d}->{v5c:3d} ({v5c - v4c:+d})")
    else:
        print("\n退化 CK なし")

    # --- エラー銘柄 ---
    v5_errors = {t: r for t, r in new_data.items() if r.get("status") == "error"}
    if v5_errors:
        print(f"\n--- エラー銘柄 ({len(v5_errors)} 社) ---")
        for t, r in sorted(v5_errors.items()):
            print(f"  {t} {r.get('company', '?')[:25]:25s} {r.get('error', '')[:60]}")


if __name__ == "__main__":
    asyncio.run(main())

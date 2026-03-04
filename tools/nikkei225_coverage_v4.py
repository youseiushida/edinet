"""日経225 CKカバレッジ再調査（v4 — V030後の最新コード）。

v3 の results から doc_id を再利用して検索フェーズをスキップし、
最新コードでの XBRL 再パースのみ行う。

Usage:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/nikkei225_coverage_v4.py
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

# v3 の結果を入力として使う（doc_id 再利用）
V3_RESULTS = Path("reports/nikkei225_coverage_v3.json")
V4_RESULTS = Path("reports/nikkei225_coverage_v4.json")
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

        # マッパー内訳
        mapper_counts: dict[str, int] = {}
        for k, v in extracted.items():
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

    # v3 の結果を読み込む
    if not V3_RESULTS.exists():
        print(f"{V3_RESULTS} が見つかりません", file=sys.stderr)
        sys.exit(1)

    old_data: dict[str, dict] = json.loads(V3_RESULTS.read_text())
    print(f"入力: {V3_RESULTS} ({len(old_data)} 銘柄)")

    # doc_id が存在する銘柄のみ再処理
    to_process = {
        t: r
        for t, r in old_data.items()
        if r.get("status") in ("ok", "error") and r.get("doc_id")
    }
    print(f"再処理対象: {len(to_process)} 銘柄")

    # 既に処理済みの結果（resume対応）
    results: dict[str, dict] = {}
    if V4_RESULTS.exists():
        try:
            results = json.loads(V4_RESULTS.read_text())
            print(f"既存v4結果: {len(results)} 銘柄（スキップ）")
        except Exception:
            pass

    # not_found は前回をそのまま引き継ぐ
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
                    # 10件ごとに保存
                    if processed[0] % 10 == 0 or processed[0] == total:
                        V4_RESULTS.parent.mkdir(parents=True, exist_ok=True)
                        V4_RESULTS.write_text(
                            json.dumps(results, ensure_ascii=False, indent=2)
                        )

        t0 = time.perf_counter()
        tasks = [run_one(t, r) for t, r in remaining.items()]
        await asyncio.gather(*tasks)
        t1 = time.perf_counter()
        print(f"\n完了 ({t1 - t0:.1f}秒)")

    # 最終保存
    V4_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    V4_RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # === v3 vs v4 比較サマリー ===
    _print_comparison(old_data, results)

    print(f"\n結果ファイル: {V4_RESULTS}")


def _print_comparison(old_data: dict, new_data: dict) -> None:
    """v3 と v4 の比較サマリーを表示する。"""
    print("\n" + "=" * 70)
    print("v3 vs v4 比較")
    print("=" * 70)

    v3_ok = {t: r for t, r in old_data.items() if r.get("status") == "ok"}
    v4_ok = {t: r for t, r in new_data.items() if r.get("status") == "ok"}

    both = sorted(set(v3_ok.keys()) & set(v4_ok.keys()))
    print(f"比較可能銘柄数: {len(both)}")

    if not both:
        return

    total_ck = len(ALL_CK_VALUES)
    v3_avg = sum(v3_ok[t]["covered_count"] for t in both) / len(both)
    v4_avg = sum(v4_ok[t]["covered_count"] for t in both) / len(both)
    v3_pct = v3_avg / total_ck * 100
    v4_pct = v4_avg / total_ck * 100
    print(f"全CK数: {total_ck}")
    print(f"v3 平均カバー: {v3_avg:.1f} CK ({v3_pct:.1f}%)")
    print(f"v4 平均カバー: {v4_avg:.1f} CK ({v4_pct:.1f}%)")
    print(f"改善: +{v4_avg - v3_avg:.1f} CK ({v4_pct - v3_pct:+.1f}pp)")

    # --- 改善が大きい銘柄 top 20 ---
    improvements = []
    for t in both:
        v3c = v3_ok[t]["covered_count"]
        v4c = v4_ok[t]["covered_count"]
        if v4c != v3c:
            improvements.append(
                (t, v4_ok[t].get("company", "?"), v3c, v4c, v4c - v3c)
            )
    improvements.sort(key=lambda x: -x[4])
    if improvements:
        print(f"\n--- 変化銘柄 top 30 ({len(improvements)} 社中) ---")
        for t, co, v3c, v4c, diff in improvements[:30]:
            sign = "+" if diff > 0 else ""
            print(f"  {t} {co[:25]:25s} {v3c}->{v4c} ({sign}{diff})")

    # --- マッパー別の寄与 ---
    v3_mapper: dict[str, int] = {}
    v4_mapper: dict[str, int] = {}
    for t in both:
        for m, c in v3_ok[t].get("mapper_counts", {}).items():
            v3_mapper[m] = v3_mapper.get(m, 0) + c
        for m, c in v4_ok[t].get("mapper_counts", {}).items():
            v4_mapper[m] = v4_mapper.get(m, 0) + c

    all_mappers = sorted(set(v3_mapper) | set(v4_mapper))
    if all_mappers:
        print(f"\n--- マッパー別 CK 総数 ({len(both)} 社合計) ---")
        print(f"  {'mapper':35s} {'v3':>6s} {'v4':>6s} {'diff':>6s}")
        for m in sorted(all_mappers, key=lambda x: -v4_mapper.get(x, 0)):
            v3c = v3_mapper.get(m, 0)
            v4c = v4_mapper.get(m, 0)
            d = v4c - v3c
            ds = f"+{d}" if d > 0 else str(d)
            print(f"  {m:35s} {v3c:6d} {v4c:6d} {ds:>6s}")

    # --- CK別のv3→v4変化 ---
    v3_ck_count: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
    v4_ck_count: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
    for t in both:
        for ck in v3_ok[t].get("covered", []):
            if ck in v3_ck_count:
                v3_ck_count[ck] += 1
        for ck in v4_ok[t].get("covered", []):
            if ck in v4_ck_count:
                v4_ck_count[ck] += 1

    improved_cks = [
        (ck, v3_ck_count[ck], v4_ck_count[ck])
        for ck in ALL_CK_VALUES
        if v4_ck_count[ck] > v3_ck_count[ck]
    ]
    if improved_cks:
        improved_cks.sort(key=lambda x: -(x[2] - x[1]))
        print(f"\n--- 改善 CK ({len(improved_cks)} 個) ---")
        for ck, v3c, v4c in improved_cks:
            print(
                f"  {ck:45s} {v3c:3d}->{v4c:3d} "
                f"(+{v4c - v3c:2d}, {v4c / len(both) * 100:.1f}%)"
            )

    # --- 全 CK のカバレッジ一覧（ASCII棒グラフ） ---
    print(f"\n--- 全 CK カバー率（{len(both)} 社中、v4） ---")
    for ck in sorted(ALL_CK_VALUES, key=lambda x: -v4_ck_count[x]):
        cnt = v4_ck_count[ck]
        pct = cnt / len(both) * 100
        bar = "#" * int(pct / 2)
        print(f"  {ck:45s} {cnt:3d}/{len(both)} ({pct:5.1f}%) |{bar}")

    # --- 退化チェック ---
    degraded_cks = [
        (ck, v3_ck_count[ck], v4_ck_count[ck])
        for ck in ALL_CK_VALUES
        if v4_ck_count[ck] < v3_ck_count[ck]
    ]
    if degraded_cks:
        print(f"\n--- ⚠ 退化 CK ({len(degraded_cks)} 個) ---")
        for ck, v3c, v4c in degraded_cks:
            print(f"  {ck:45s} {v3c:3d}->{v4c:3d} ({v4c - v3c:+d})")
    else:
        print("\n退化 CK なし（全 CK で v3 以上のカバレッジ）")

    # --- v4 エラー銘柄 ---
    v4_errors = {t: r for t, r in new_data.items() if r.get("status") == "error"}
    if v4_errors:
        print(f"\n--- エラー銘柄 ({len(v4_errors)} 社) ---")
        for t, r in sorted(v4_errors.items()):
            print(f"  {t} {r.get('company', '?')[:25]:25s} {r.get('error', '')[:60]}")


if __name__ == "__main__":
    asyncio.run(main())

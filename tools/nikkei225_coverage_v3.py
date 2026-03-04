"""日経225 CKカバレッジ再調査（v3 — statement_mappings 拡充版）。

v2 の results から doc_id を再利用して検索フェーズをスキップし、
拡充後の statement_mappings での XBRL 再パースのみ行う。

Usage:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/nikkei225_coverage_v3.py
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

# v2 の結果を入力として使う（doc_id 再利用）
V1_RESULTS = Path("reports/nikkei225_coverage.json")
V2_RESULTS = Path("reports/nikkei225_coverage_v2.json")
V3_RESULTS = Path("reports/nikkei225_coverage_v3.json")
MAX_CONCURRENT = 12

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

    # v2 の結果を読み込む（v2がなければv1を使う）
    src_file = V2_RESULTS if V2_RESULTS.exists() else V1_RESULTS
    if not src_file.exists():
        print(f"{src_file} が見つかりません", file=sys.stderr)
        sys.exit(1)

    old_data: dict[str, dict] = json.loads(src_file.read_text())
    print(f"入力: {src_file} ({len(old_data)} 銘柄)")

    # doc_id が存在する銘柄のみ再処理
    to_process = {
        t: r
        for t, r in old_data.items()
        if r.get("status") in ("ok", "error") and r.get("doc_id")
    }
    print(f"再処理対象: {len(to_process)} 銘柄")

    # 既に処理済みの結果（resume対応）
    results: dict[str, dict] = {}
    if V3_RESULTS.exists():
        try:
            results = json.loads(V3_RESULTS.read_text())
            print(f"既存v3結果: {len(results)} 銘柄（スキップ）")
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

        async def run_one(ticker: str, info: dict) -> None:
            async with sem:
                result = await asyncio.to_thread(
                    process_one,
                    ticker,
                    info["doc_id"],
                    info.get("company", "?"),
                )
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
                # 逐次保存
                V3_RESULTS.parent.mkdir(parents=True, exist_ok=True)
                V3_RESULTS.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2)
                )

        t0 = time.perf_counter()
        tasks = [run_one(t, r) for t, r in remaining.items()]
        await asyncio.gather(*tasks)
        t1 = time.perf_counter()
        print(f"\n完了 ({t1 - t0:.1f}秒)")

    # 最終保存
    V3_RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # === v2 vs v3 比較サマリー ===
    _print_comparison(old_data, results)

    print(f"\n結果ファイル: {V3_RESULTS}")


def _print_comparison(old_data: dict, new_data: dict) -> None:
    """v2 と v3 の比較サマリーを表示する。"""
    print("\n" + "=" * 70)
    print("v2 (before mappings expansion) vs v3 (after)")
    print("=" * 70)

    v2_ok = {t: r for t, r in old_data.items() if r.get("status") == "ok"}
    v3_ok = {t: r for t, r in new_data.items() if r.get("status") == "ok"}

    both = sorted(set(v2_ok.keys()) & set(v3_ok.keys()))
    print(f"比較可能銘柄数: {len(both)}")

    if not both:
        return

    total_ck = v3_ok[both[0]]["total_ck"]
    v2_avg = sum(v2_ok[t]["covered_count"] for t in both) / len(both)
    v3_avg = sum(v3_ok[t]["covered_count"] for t in both) / len(both)
    v2_pct = v2_avg / total_ck * 100
    v3_pct = v3_avg / total_ck * 100
    print(f"v2 平均カバー: {v2_avg:.1f} CK ({v2_pct:.1f}%)")
    print(f"v3 平均カバー: {v3_avg:.1f} CK ({v3_pct:.1f}%)")
    print(f"改善: +{v3_avg - v2_avg:.1f} CK (+{v3_pct - v2_pct:.1f}pp)")

    # --- 改善が大きい銘柄 top 20 ---
    improvements = []
    for t in both:
        v2c = v2_ok[t]["covered_count"]
        v3c = v3_ok[t]["covered_count"]
        if v3c > v2c:
            improvements.append(
                (t, v3_ok[t].get("company", "?"), v2c, v3c, v3c - v2c)
            )
    improvements.sort(key=lambda x: -x[4])
    if improvements:
        print(f"\n--- 改善銘柄 top 20 ({len(improvements)} 社中) ---")
        for t, co, v2c, v3c, diff in improvements[:20]:
            print(f"  {t} {co[:25]:25s} {v2c}->{v3c} (+{diff})")

    # --- マッパー別の寄与 ---
    v2_mapper: dict[str, int] = {}
    v3_mapper: dict[str, int] = {}
    for t in both:
        for m, c in v2_ok[t].get("mapper_counts", {}).items():
            v2_mapper[m] = v2_mapper.get(m, 0) + c
        for m, c in v3_ok[t].get("mapper_counts", {}).items():
            v3_mapper[m] = v3_mapper.get(m, 0) + c

    all_mappers = sorted(set(v2_mapper) | set(v3_mapper))
    if all_mappers:
        print(f"\n--- マッパー別 CK 総数 ({len(both)} 社合計) ---")
        print(f"  {'mapper':35s} {'v2':>6s} {'v3':>6s} {'diff':>6s}")
        for m in sorted(all_mappers, key=lambda x: -v3_mapper.get(x, 0)):
            v2c = v2_mapper.get(m, 0)
            v3c = v3_mapper.get(m, 0)
            d = v3c - v2c
            ds = f"+{d}" if d > 0 else str(d)
            print(f"  {m:35s} {v2c:6d} {v3c:6d} {ds:>6s}")

    # --- CK別のv2→v3変化 ---
    v2_ck_count: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
    v3_ck_count: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
    for t in both:
        for ck in v2_ok[t].get("covered", []):
            v2_ck_count[ck] += 1
        for ck in v3_ok[t].get("covered", []):
            v3_ck_count[ck] += 1

    improved_cks = [
        (ck, v2_ck_count[ck], v3_ck_count[ck])
        for ck in ALL_CK_VALUES
        if v3_ck_count[ck] > v2_ck_count[ck]
    ]
    if improved_cks:
        improved_cks.sort(key=lambda x: -(x[2] - x[1]))
        print(f"\n--- 改善 CK ({len(improved_cks)} 個) ---")
        for ck, v2c, v3c in improved_cks:
            print(
                f"  {ck:45s} {v2c:3d}->{v3c:3d} "
                f"(+{v3c - v2c:2d}, {v3c / len(both) * 100:.1f}%)"
            )

    # --- 全 CK のカバレッジ一覧（ASCII棒グラフ） ---
    print(f"\n--- 全 CK カバー率（{len(both)} 社中、v3） ---")
    for ck in sorted(ALL_CK_VALUES, key=lambda x: -v3_ck_count[x]):
        cnt = v3_ck_count[ck]
        pct = cnt / len(both) * 100
        bar = "#" * int(pct / 2)
        print(f"  {ck:45s} {cnt:3d}/{len(both)} ({pct:5.1f}%) |{bar}")

    # --- 退化チェック ---
    degraded_cks = [
        (ck, v2_ck_count[ck], v3_ck_count[ck])
        for ck in ALL_CK_VALUES
        if v3_ck_count[ck] < v2_ck_count[ck]
    ]
    if degraded_cks:
        print(f"\n--- ⚠ 退化 CK ({len(degraded_cks)} 個) ---")
        for ck, v2c, v3c in degraded_cks:
            print(f"  {ck:45s} {v2c:3d}->{v3c:3d} ({v3c - v2c:+d})")
    else:
        print("\n退化 CK なし（全 CK で v2 以上のカバレッジ）")


if __name__ == "__main__":
    asyncio.run(main())

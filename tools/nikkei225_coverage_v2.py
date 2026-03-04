"""日経225 CKカバレッジ再調査（v2 — linkbase mapper 有効版）。

前回の reports/nikkei225_coverage.json から doc_id を再利用して
検索フェーズをスキップし、XBRL 再パースのみ行う。

Usage:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/nikkei225_coverage_v2.py
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

OLD_RESULTS = Path("reports/nikkei225_coverage.json")
NEW_RESULTS = Path("reports/nikkei225_coverage_v2.json")
MAX_CONCURRENT = 8

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

    if not OLD_RESULTS.exists():
        print(f"{OLD_RESULTS} が見つかりません", file=sys.stderr)
        sys.exit(1)

    old_data: dict[str, dict] = json.loads(OLD_RESULTS.read_text())
    print(f"前回結果: {len(old_data)} 銘柄")

    # doc_id が存在する銘柄のみ再処理
    to_process = {
        t: r for t, r in old_data.items()
        if r.get("status") in ("ok", "error") and r.get("doc_id")
    }
    print(f"再処理対象: {len(to_process)} 銘柄")

    # 既に処理済みの結果（resume対応）
    results: dict[str, dict] = {}
    if NEW_RESULTS.exists():
        try:
            results = json.loads(NEW_RESULTS.read_text())
            print(f"既存v2結果: {len(results)} 銘柄（スキップ）")
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
                    process_one, ticker, info["doc_id"], info.get("company", "?"),
                )
                results[ticker] = result
                processed[0] += 1
                status = "ok" if result.get("status") == "ok" else "ERROR"
                cov = result.get("covered_count", "?")
                tot = result.get("total_ck", "?")
                pct = result.get("coverage_pct", "?")
                mc = result.get("mapper_counts", {})
                print(
                    f"  [{processed[0]}/{total}] {ticker} "
                    f"{result.get('company', '?')[:20]} -> "
                    f"{cov}/{tot} ({pct}%) [{status}] {mc}",
                    flush=True,
                )
                # 逐次保存
                NEW_RESULTS.parent.mkdir(parents=True, exist_ok=True)
                NEW_RESULTS.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2)
                )

        t0 = time.perf_counter()
        tasks = [run_one(t, r) for t, r in remaining.items()]
        await asyncio.gather(*tasks)
        t1 = time.perf_counter()
        print(f"完了 ({t1 - t0:.1f}秒)")

    # 最終保存
    NEW_RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # === 比較サマリー ===
    print("\n" + "=" * 70)
    print("v1 (before linkbase mappers) vs v2 (after)")
    print("=" * 70)

    v1_ok = {t: r for t, r in old_data.items() if r.get("status") == "ok"}
    v2_ok = {t: r for t, r in results.items() if r.get("status") == "ok"}

    both = set(v1_ok.keys()) & set(v2_ok.keys())
    print(f"比較可能銘柄数: {len(both)}")

    if both:
        v1_avg = sum(v1_ok[t]["covered_count"] for t in both) / len(both)
        v2_avg = sum(v2_ok[t]["covered_count"] for t in both) / len(both)
        v1_pct = v1_avg / v1_ok[next(iter(both))]["total_ck"] * 100
        v2_pct = v2_avg / v2_ok[next(iter(both))]["total_ck"] * 100
        print(f"v1 平均カバー: {v1_avg:.1f} CK ({v1_pct:.1f}%)")
        print(f"v2 平均カバー: {v2_avg:.1f} CK ({v2_pct:.1f}%)")
        print(f"改善: +{v2_avg - v1_avg:.1f} CK (+{v2_pct - v1_pct:.1f}pp)")

        # 改善が大きい銘柄 top 20
        improvements = []
        for t in both:
            v1c = v1_ok[t]["covered_count"]
            v2c = v2_ok[t]["covered_count"]
            if v2c > v1c:
                improvements.append((t, v1_ok[t].get("company", "?"), v1c, v2c, v2c - v1c))
        improvements.sort(key=lambda x: -x[4])
        if improvements:
            print(f"\n--- 改善銘柄 top 20 ({len(improvements)} 社中) ---")
            for t, co, v1c, v2c, diff in improvements[:20]:
                print(f"  {t} {co[:25]:25s} {v1c}->{v2c} (+{diff})")

        # マッパー別の寄与
        total_mapper_counts: dict[str, int] = {}
        for t in both:
            mc = v2_ok[t].get("mapper_counts", {})
            for m, c in mc.items():
                total_mapper_counts[m] = total_mapper_counts.get(m, 0) + c
        if total_mapper_counts:
            print(f"\n--- マッパー別 CK 総数 ({len(both)} 社合計) ---")
            for m, c in sorted(total_mapper_counts.items(), key=lambda x: -x[1]):
                print(f"  {m:30s} {c:5d}")

        # CK別のv1→v2変化
        v1_ck_count: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
        v2_ck_count: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
        for t in both:
            for ck in v1_ok[t].get("covered", []):
                v1_ck_count[ck] += 1
            for ck in v2_ok[t].get("covered", []):
                v2_ck_count[ck] += 1

        improved_cks = [
            (ck, v1_ck_count[ck], v2_ck_count[ck])
            for ck in ALL_CK_VALUES
            if v2_ck_count[ck] > v1_ck_count[ck]
        ]
        if improved_cks:
            improved_cks.sort(key=lambda x: -(x[2] - x[1]))
            print(f"\n--- 改善 CK ({len(improved_cks)} 個) ---")
            for ck, v1c, v2c in improved_cks:
                print(
                    f"  {ck:45s} {v1c:3d}->{v2c:3d} "
                    f"(+{v2c - v1c:2d}, {v2c / len(both) * 100:.1f}%)"
                )

        # まだ取得できない企業＆CK
        still_missing: list[tuple[str, str, list[str]]] = []
        for t in sorted(both):
            miss = v2_ok[t].get("missing", [])
            if miss:
                still_missing.append((t, v2_ok[t].get("company", "?"), miss))

        if still_missing:
            print(f"\n--- まだ欠損がある銘柄 ({len(still_missing)} 社) ---")
            for t, co, miss in still_missing[:30]:
                print(f"  {t} {co[:25]:25s} 欠損{len(miss)}個: {', '.join(miss[:5])}...")

    print(f"\n結果ファイル: {NEW_RESULTS}")


if __name__ == "__main__":
    asyncio.run(main())

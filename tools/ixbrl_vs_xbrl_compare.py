"""iXBRL パーサー vs XBRL パーサーの比較検証スクリプト。

EDINET の同一 ZIP から .xbrl と _ixbrl.htm の両方をパースし、
抽出された Fact が一致するかを検証する。

各業種・会計基準の企業を対象にする。
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import edinet
from edinet.api.download import (
    adownload_document,
    extract_primary_xbrl,
    extract_zip_member,
    list_zip_members,
)
from edinet.exceptions import EdinetWarning
from edinet.xbrl.ixbrl_parser import parse_ixbrl_facts
from edinet.xbrl.parser import ParsedXBRL, parse_xbrl_facts

warnings.filterwarnings("ignore", category=EdinetWarning)

# =====================================================================
# 対象企業（EDINET コード → 企業名, 業種, 会計基準）
# =====================================================================

@dataclass
class Target:
    edinet_code: str
    name: str
    industry: str
    standard: str
    doc_id: str | None = None  # 後で API で取得


# doc_id を直接指定（2025年6月提出の有報を事前に特定）
TARGETS: list[Target] = [
    # --- JPGAAP ---
    # 建設業
    Target("E00069", "大林組", "建設", "JPGAAP"),
    Target("E00048", "鹿島建設", "建設", "JPGAAP"),
    # 銀行業
    Target("E03606", "三菱UFJ FG", "銀行", "JPGAAP"),
    Target("E03615", "三井住友 FG", "銀行", "JPGAAP"),
    # 鉄道業
    Target("E04142", "JR東日本", "鉄道", "JPGAAP"),
    Target("E04167", "JR東海", "鉄道", "JPGAAP"),
    # 証券業
    Target("E03742", "大和証券グループ", "証券", "JPGAAP"),
    # 保険業
    Target("E03793", "東京海上HD", "保険", "JPGAAP"),
    # 一般
    Target("E02144", "トヨタ自動車", "一般", "JPGAAP"),
    Target("E04427", "NTT", "一般", "JPGAAP"),

    # --- USGAAP ---
    Target("E03714", "野村HD", "証券", "USGAAP"),
    Target("E02274", "キヤノン", "一般", "USGAAP"),

    # --- IFRS ---
    Target("E05765", "SBI HD", "証券", "IFRS"),
    Target("E01737", "日立製作所", "一般", "IFRS"),
    Target("E02778", "ソフトバンクG", "一般", "IFRS"),
    Target("E31394", "第一生命HD", "保険", "IFRS"),
]


# =====================================================================
# doc_id 取得（EDINET API から有報を検索）
# =====================================================================

async def find_doc_ids(targets: list[Target]) -> None:
    """EDINET API で各企業の最新有報 doc_id を取得する。"""
    from edinet.api.documents import aget_documents

    edinet_code_map = {t.edinet_code: t for t in targets}
    found = set()

    # 2025年6月の各日を並列で取得（有報の提出ピーク）
    dates = [f"2025-06-{d:02d}" for d in range(20, 30)]

    async def search_date(date_str: str) -> None:
        try:
            result = await aget_documents(date_str)
        except Exception as e:
            print(f"  skip {date_str}: {e}")
            return
        for item in result.get("results", []):
            ec = item.get("edinetCode")
            doc_type = item.get("docTypeCode")
            if ec in edinet_code_map and ec not in found:
                # 有報=120, 四半期=140, 半期=160
                if doc_type in ("120", "130"):
                    target = edinet_code_map[ec]
                    target.doc_id = item["docID"]
                    found.add(ec)
                    print(f"  Found: {target.name} → {target.doc_id} (type={doc_type})")

    print("Searching for doc_ids...")
    # 並列で日付を検索
    await asyncio.gather(*[search_date(d) for d in dates])

    # 見つからなかったものは別の日付レンジも検索
    missing = [t for t in targets if t.doc_id is None]
    if missing:
        print(f"\n{len(missing)} 件が未発見。追加日付を検索中...")
        extra_dates = [f"2025-06-{d:02d}" for d in range(10, 20)]
        extra_dates += [f"2025-07-{d:02d}" for d in range(1, 10)]
        await asyncio.gather(*[search_date(d) for d in extra_dates])


# =====================================================================
# 比較ロジック
# =====================================================================

@dataclass
class CompareResult:
    """1 Filing の XBRL vs iXBRL 比較結果。"""
    target: Target
    xbrl_fact_count: int = 0
    ixbrl_fact_count: int = 0
    xbrl_context_count: int = 0
    ixbrl_context_count: int = 0
    xbrl_unit_count: int = 0
    ixbrl_unit_count: int = 0
    common_concepts: int = 0
    xbrl_only_concepts: int = 0
    ixbrl_only_concepts: int = 0
    value_matches: int = 0
    value_mismatches: int = 0
    mismatch_details: list[str] = field(default_factory=list)
    error: str | None = None
    ixbrl_file_count: int = 0
    elapsed_sec: float = 0.0


def _find_ixbrl_files(members: tuple[str, ...]) -> list[str]:
    """ZIP 内の PublicDoc 配下の iXBRL ファイルを返す。"""
    return [
        m for m in members
        if m.lower().endswith("_ixbrl.htm")
        and "publicdoc/" in m.lower().replace("\\", "/")
    ]


def _merge_ixbrl_results(results: list[ParsedXBRL]) -> ParsedXBRL:
    """複数 iXBRL パース結果を1つにマージする（IXDS 対応）。"""
    all_facts = []
    all_contexts = []
    all_units = []
    all_schema_refs = []
    seen_context_ids: set[str] = set()
    seen_unit_ids: set[str] = set()
    order = 0

    for parsed in results:
        for ctx in parsed.contexts:
            if ctx.context_id and ctx.context_id not in seen_context_ids:
                all_contexts.append(ctx)
                seen_context_ids.add(ctx.context_id)
        for unit in parsed.units:
            if unit.unit_id and unit.unit_id not in seen_unit_ids:
                all_units.append(unit)
                seen_unit_ids.add(unit.unit_id)
        for sr in parsed.schema_refs:
            all_schema_refs.append(sr)
        for fact in parsed.facts:
            # order を振り直す
            from dataclasses import replace
            all_facts.append(replace(fact, order=order))
            order += 1

    return ParsedXBRL(
        source_path="(merged iXBRL)",
        source_format="inline",
        facts=tuple(all_facts),
        contexts=tuple(all_contexts),
        units=tuple(all_units),
        schema_refs=tuple(all_schema_refs),
    )


def _build_fact_key(concept_qname: str, context_ref: str, unit_ref: str | None) -> str:
    return f"{concept_qname}|{context_ref}|{unit_ref or ''}"


def compare_parsed(
    xbrl: ParsedXBRL,
    ixbrl: ParsedXBRL,
    target: Target,
    ixbrl_file_count: int,
    elapsed: float,
) -> CompareResult:
    """2つのパース結果を比較する。"""
    result = CompareResult(
        target=target,
        xbrl_fact_count=len(xbrl.facts),
        ixbrl_fact_count=len(ixbrl.facts),
        xbrl_context_count=len(xbrl.contexts),
        ixbrl_context_count=len(ixbrl.contexts),
        xbrl_unit_count=len(xbrl.units),
        ixbrl_unit_count=len(ixbrl.units),
        ixbrl_file_count=ixbrl_file_count,
        elapsed_sec=elapsed,
    )

    # Fact を (concept_qname, context_ref, unit_ref) でグルーピング
    xbrl_facts: dict[str, list[str | None]] = defaultdict(list)
    for f in xbrl.facts:
        key = _build_fact_key(f.concept_qname, f.context_ref, f.unit_ref)
        xbrl_facts[key].append(f.value_raw)

    ixbrl_facts: dict[str, list[str | None]] = defaultdict(list)
    for f in ixbrl.facts:
        key = _build_fact_key(f.concept_qname, f.context_ref, f.unit_ref)
        ixbrl_facts[key].append(f.value_raw)

    xbrl_keys = set(xbrl_facts.keys())
    ixbrl_keys = set(ixbrl_facts.keys())

    result.common_concepts = len(xbrl_keys & ixbrl_keys)
    result.xbrl_only_concepts = len(xbrl_keys - ixbrl_keys)
    result.ixbrl_only_concepts = len(ixbrl_keys - xbrl_keys)

    # 共通 Fact の値比較
    for key in xbrl_keys & ixbrl_keys:
        xbrl_vals = sorted(xbrl_facts[key], key=lambda x: x or "")
        ixbrl_vals = sorted(ixbrl_facts[key], key=lambda x: x or "")
        if xbrl_vals == ixbrl_vals:
            result.value_matches += 1
        else:
            result.value_mismatches += 1
            if len(result.mismatch_details) < 5:
                parts = key.split("|")
                concept = parts[0].split("}")[-1] if "}" in parts[0] else parts[0]
                result.mismatch_details.append(
                    f"  {concept}: xbrl={xbrl_vals[:2]} vs ixbrl={ixbrl_vals[:2]}"
                )

    return result


async def process_target(target: Target, zip_cache: dict[str, bytes]) -> CompareResult:
    """1企業の比較処理。"""
    t0 = time.monotonic()
    try:
        doc_id = target.doc_id
        if doc_id is None:
            return CompareResult(target=target, error="doc_id 未取得")

        # ZIP ダウンロード（キャッシュ利用）
        if doc_id not in zip_cache:
            zip_bytes = await adownload_document(doc_id, file_type="1")
            zip_cache[doc_id] = zip_bytes
        zip_bytes = zip_cache[doc_id]

        members = list_zip_members(zip_bytes)

        # 1. XBRL パース
        xbrl_result = extract_primary_xbrl(zip_bytes)
        if xbrl_result is None:
            return CompareResult(target=target, error="primary XBRL が見つかりません")
        xbrl_path, xbrl_bytes = xbrl_result
        xbrl_parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path, strict=False)

        # 2. iXBRL パース（全 PublicDoc/*.htm をマージ）
        ixbrl_files = _find_ixbrl_files(members)
        if not ixbrl_files:
            return CompareResult(target=target, error="iXBRL ファイルが見つかりません")

        ixbrl_results = []
        for htm_path in ixbrl_files:
            htm_bytes = extract_zip_member(zip_bytes, htm_path)
            try:
                parsed = parse_ixbrl_facts(htm_bytes, source_path=htm_path, strict=False)
                ixbrl_results.append(parsed)
            except Exception as e:
                print(f"    WARN: {htm_path} parse failed: {e}")

        if not ixbrl_results:
            return CompareResult(target=target, error="iXBRL パース結果 0 件")

        ixbrl_merged = _merge_ixbrl_results(ixbrl_results)
        elapsed = time.monotonic() - t0

        return compare_parsed(xbrl_parsed, ixbrl_merged, target, len(ixbrl_files), elapsed)

    except Exception as e:
        return CompareResult(
            target=target,
            error=f"{type(e).__name__}: {e}",
            elapsed_sec=time.monotonic() - t0,
        )


# =====================================================================
# レポート出力
# =====================================================================

def print_report(results: list[CompareResult]) -> None:
    """比較結果を整形して出力する。"""
    print("\n" + "=" * 100)
    print("iXBRL vs XBRL 比較結果")
    print("=" * 100)

    # テーブルヘッダー
    header = (
        f"{'企業名':<16} {'業種':<6} {'基準':<8} "
        f"{'XBRL':>6} {'iXBRL':>6} {'共通':>6} {'Xのみ':>6} {'iのみ':>6} "
        f"{'一致':>6} {'不一致':>6} {'htm数':>5} {'秒':>5} {'状態':<10}"
    )
    print(header)
    print("-" * 100)

    for r in results:
        if r.error:
            print(
                f"{r.target.name:<16} {r.target.industry:<6} {r.target.standard:<8} "
                f"{'—':>6} {'—':>6} {'—':>6} {'—':>6} {'—':>6} "
                f"{'—':>6} {'—':>6} {'—':>5} {'—':>5} ERROR: {r.error}"
            )
        else:
            match_rate = (
                f"{r.value_matches / (r.value_matches + r.value_mismatches) * 100:.0f}%"
                if (r.value_matches + r.value_mismatches) > 0
                else "—"
            )
            status = "OK" if r.value_mismatches == 0 and r.ixbrl_only_concepts == 0 else match_rate
            print(
                f"{r.target.name:<16} {r.target.industry:<6} {r.target.standard:<8} "
                f"{r.xbrl_fact_count:>6} {r.ixbrl_fact_count:>6} {r.common_concepts:>6} "
                f"{r.xbrl_only_concepts:>6} {r.ixbrl_only_concepts:>6} "
                f"{r.value_matches:>6} {r.value_mismatches:>6} "
                f"{r.ixbrl_file_count:>5} {r.elapsed_sec:>5.1f} {status:<10}"
            )
            if r.mismatch_details:
                for detail in r.mismatch_details[:3]:
                    print(f"  {detail}")

    # サマリー
    print("\n" + "=" * 100)
    ok = [r for r in results if not r.error]
    err = [r for r in results if r.error]
    print(f"合計: {len(results)} 企業, 成功: {len(ok)}, エラー: {len(err)}")
    if ok:
        total_match = sum(r.value_matches for r in ok)
        total_mismatch = sum(r.value_mismatches for r in ok)
        total = total_match + total_mismatch
        if total > 0:
            print(f"値一致率: {total_match}/{total} ({total_match/total*100:.1f}%)")
        total_xbrl_only = sum(r.xbrl_only_concepts for r in ok)
        total_ixbrl_only = sum(r.ixbrl_only_concepts for r in ok)
        print(f"XBRL のみ概念合計: {total_xbrl_only}, iXBRL のみ概念合計: {total_ixbrl_only}")


# =====================================================================
# メイン
# =====================================================================

async def main() -> None:
    edinet.configure(
        api_key=os.environ.get("EDINET_API_KEY", ""),
        taxonomy_path=os.environ.get(
            "EDINET_TAXONOMY_ROOT",
            "/mnt/c/Users/nezow/Downloads/ALL_20251101",
        ),
    )

    # 1. doc_id 取得
    await find_doc_ids(TARGETS)

    # 未取得の企業を報告
    available = [t for t in TARGETS if t.doc_id is not None]
    missing = [t for t in TARGETS if t.doc_id is None]
    print(f"\ndoc_id 取得完了: {len(available)} 件, 未取得: {len(missing)} 件")
    for t in missing:
        print(f"  未取得: {t.name} ({t.edinet_code})")

    # 2. 並列でダウンロード＆比較
    # ネットワーク帯域を考慮して同時実行数を制限
    sem = asyncio.Semaphore(4)
    zip_cache: dict[str, bytes] = {}

    async def process_with_sem(target: Target) -> CompareResult:
        async with sem:
            return await process_target(target, zip_cache)

    print(f"\n比較処理開始 ({len(available)} 件)...")
    t0 = time.monotonic()
    results = await asyncio.gather(*[process_with_sem(t) for t in available])
    elapsed = time.monotonic() - t0
    print(f"全体所要時間: {elapsed:.1f} 秒")

    # 3. レポート
    print_report(list(results))

    # 4. 結果をファイルに保存
    output_path = os.path.join(os.path.dirname(__file__), "ixbrl_compare_results.txt")
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_report(list(results))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"\n結果を {output_path} に保存しました。")


if __name__ == "__main__":
    asyncio.run(main())

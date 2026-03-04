"""iXBRL vs XBRL 最終比較スクリプト。

doc_id を直接指定して高速に比較する。
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass, field, replace

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


@dataclass
class Target:
    doc_id: str
    name: str
    industry: str
    standard: str


TARGETS = [
    # JPGAAP - 建設
    Target("S100W3SK", "大林組", "建設", "JPGAAP"),
    Target("S100VZ3Z", "鹿島建設", "建設", "JPGAAP"),
    # JPGAAP - 銀行
    Target("S100W4FB", "三菱UFJ FG", "銀行", "JPGAAP"),
    Target("S100VYQX", "三井住友 FG", "銀行", "JPGAAP"),
    # JPGAAP - 鉄道
    Target("S100W5LD", "JR東日本", "鉄道", "JPGAAP"),
    # JPGAAP - 保険
    Target("S100W40P", "東京海上HD", "保険", "JPGAAP"),
    # JPGAAP - 一般
    Target("S100VWVY", "トヨタ自動車", "一般", "JPGAAP"),
    Target("S100W0YP", "NTT", "一般", "JPGAAP"),
    # USGAAP - 一般
    Target("S100VHZZ", "キヤノン", "一般", "USGAAP"),
    # IFRS - 一般
    Target("S100W56G", "日立製作所", "一般", "IFRS"),
    Target("S100W4HN", "ソフトバンクG", "一般", "IFRS"),
]


@dataclass
class CompareResult:
    target: Target
    xbrl_fact_count: int = 0
    ixbrl_fact_count: int = 0
    xbrl_context_count: int = 0
    ixbrl_context_count: int = 0
    common_keys: int = 0
    xbrl_only_keys: int = 0
    ixbrl_only_keys: int = 0
    value_exact_match: int = 0
    value_numeric_match: int = 0
    value_text_diff: int = 0
    value_real_mismatch: int = 0
    real_mismatch_details: list[str] = field(default_factory=list)
    ixbrl_file_count: int = 0
    elapsed_sec: float = 0.0
    error: str | None = None


def _find_ixbrl_files(members: tuple[str, ...]) -> list[str]:
    return [
        m for m in members
        if m.lower().endswith("_ixbrl.htm")
        and "publicdoc/" in m.lower().replace("\\", "/")
    ]


def _merge_ixbrl_results(results: list[ParsedXBRL]) -> ParsedXBRL:
    all_facts = []
    all_contexts = []
    all_units = []
    all_schema_refs = []
    seen_ctx: set[str] = set()
    seen_unit: set[str] = set()
    order = 0
    for parsed in results:
        for ctx in parsed.contexts:
            if ctx.context_id and ctx.context_id not in seen_ctx:
                all_contexts.append(ctx)
                seen_ctx.add(ctx.context_id)
        for unit in parsed.units:
            if unit.unit_id and unit.unit_id not in seen_unit:
                all_units.append(unit)
                seen_unit.add(unit.unit_id)
        for sr in parsed.schema_refs:
            all_schema_refs.append(sr)
        for fact in parsed.facts:
            all_facts.append(replace(fact, order=order))
            order += 1
    return ParsedXBRL(
        source_path="(merged)",
        source_format="inline",
        facts=tuple(all_facts),
        contexts=tuple(all_contexts),
        units=tuple(all_units),
        schema_refs=tuple(all_schema_refs),
    )


def _numeric_equal(a: str | None, b: str | None) -> bool:
    """数値として等しいか（"50.00" == "50"）。"""
    if a == b:
        return True
    if a is None or b is None:
        return False
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(a.strip()) == Decimal(b.strip())
    except InvalidOperation:
        return False


def _is_text_block_diff(a: str | None, b: str | None) -> bool:
    """HTML タグの有無のみの差異かどうか。"""
    if a is None or b is None:
        return False
    import re
    a_plain = re.sub(r"<[^>]+>", "", a).strip()
    b_plain = re.sub(r"<[^>]+>", "", b).strip()
    # 空白の正規化
    a_norm = re.sub(r"\s+", " ", a_plain)
    b_norm = re.sub(r"\s+", " ", b_plain)
    return a_norm == b_norm


def _fact_key(concept: str, ctx: str, unit: str | None) -> str:
    return f"{concept}|{ctx}|{unit or ''}"


def compare_parsed(xbrl: ParsedXBRL, ixbrl: ParsedXBRL, target: Target,
                   ixbrl_file_count: int, elapsed: float) -> CompareResult:
    r = CompareResult(
        target=target,
        xbrl_fact_count=len(xbrl.facts),
        ixbrl_fact_count=len(ixbrl.facts),
        xbrl_context_count=len(xbrl.contexts),
        ixbrl_context_count=len(ixbrl.contexts),
        ixbrl_file_count=ixbrl_file_count,
        elapsed_sec=elapsed,
    )

    xbrl_facts: dict[str, list[str | None]] = defaultdict(list)
    for f in xbrl.facts:
        xbrl_facts[_fact_key(f.concept_qname, f.context_ref, f.unit_ref)].append(f.value_raw)

    ixbrl_facts: dict[str, list[str | None]] = defaultdict(list)
    for f in ixbrl.facts:
        ixbrl_facts[_fact_key(f.concept_qname, f.context_ref, f.unit_ref)].append(f.value_raw)

    xkeys = set(xbrl_facts)
    ikeys = set(ixbrl_facts)
    r.common_keys = len(xkeys & ikeys)
    r.xbrl_only_keys = len(xkeys - ikeys)
    r.ixbrl_only_keys = len(ikeys - xkeys)

    for key in xkeys & ikeys:
        xv = sorted(xbrl_facts[key], key=lambda x: x or "")
        iv = sorted(ixbrl_facts[key], key=lambda x: x or "")
        if xv == iv:
            r.value_exact_match += 1
        elif len(xv) == len(iv) and all(_numeric_equal(a, b) for a, b in zip(xv, iv)):
            r.value_numeric_match += 1
        elif len(xv) == len(iv) and all(
            _numeric_equal(a, b) or _is_text_block_diff(a, b) for a, b in zip(xv, iv)
        ):
            r.value_text_diff += 1
        else:
            r.value_real_mismatch += 1
            if len(r.real_mismatch_details) < 3:
                c = key.split("|")[0].split("}")[-1] if "}" in key else key
                xsnip = str(xv[:1])[:60]
                isnip = str(iv[:1])[:60]
                r.real_mismatch_details.append(f"  {c}: X={xsnip} I={isnip}")

    return r


async def process(target: Target, sem: asyncio.Semaphore) -> CompareResult:
    async with sem:
        t0 = time.monotonic()
        try:
            zip_bytes = await adownload_document(target.doc_id, file_type="1")
            members = list_zip_members(zip_bytes)

            xr = extract_primary_xbrl(zip_bytes)
            if xr is None:
                return CompareResult(target=target, error="no primary xbrl")
            xbrl_parsed = parse_xbrl_facts(xr[1], source_path=xr[0], strict=False)

            htm_files = _find_ixbrl_files(members)
            if not htm_files:
                return CompareResult(target=target, error="no ixbrl files")

            ixbrl_results = []
            for hp in htm_files:
                hb = extract_zip_member(zip_bytes, hp)
                try:
                    ixbrl_results.append(parse_ixbrl_facts(hb, source_path=hp, strict=False))
                except Exception as e:
                    print(f"  WARN: {hp}: {e}")

            ixbrl_merged = _merge_ixbrl_results(ixbrl_results)
            return compare_parsed(xbrl_parsed, ixbrl_merged, target, len(htm_files),
                                  time.monotonic() - t0)
        except Exception as e:
            return CompareResult(target=target, error=str(e), elapsed_sec=time.monotonic() - t0)


def report(results: list[CompareResult]) -> str:
    lines = []
    lines.append("")
    lines.append("=" * 120)
    lines.append("iXBRL vs XBRL 比較結果（改良版: 数値同値・HTML差異を分離）")
    lines.append("=" * 120)
    h = (
        f"{'企業名':<14} {'業種':<5} {'基準':<7} "
        f"{'X件':>5} {'i件':>5} {'共通K':>5} {'Xのみ':>5} {'iのみ':>5} "
        f"{'完全一致':>7} {'数値同':>5} {'HTML差':>5} {'真不一致':>6} "
        f"{'htm':>4} {'秒':>5}"
    )
    lines.append(h)
    lines.append("-" * 120)

    for r in results:
        if r.error:
            lines.append(f"{r.target.name:<14} {r.target.industry:<5} {r.target.standard:<7} ERROR: {r.error}")
            continue
        total = r.value_exact_match + r.value_numeric_match + r.value_text_diff + r.value_real_mismatch
        real_pct = f"({r.value_real_mismatch / total * 100:.1f}%)" if total else ""
        lines.append(
            f"{r.target.name:<14} {r.target.industry:<5} {r.target.standard:<7} "
            f"{r.xbrl_fact_count:>5} {r.ixbrl_fact_count:>5} {r.common_keys:>5} "
            f"{r.xbrl_only_keys:>5} {r.ixbrl_only_keys:>5} "
            f"{r.value_exact_match:>7} {r.value_numeric_match:>5} {r.value_text_diff:>5} "
            f"{r.value_real_mismatch:>6}{real_pct:>7} "
            f"{r.ixbrl_file_count:>4} {r.elapsed_sec:>5.1f}"
        )
        for d in r.real_mismatch_details:
            lines.append(d)

    lines.append("")
    lines.append("=" * 120)
    ok = [r for r in results if not r.error]
    lines.append(f"企業数: {len(results)}, 成功: {len(ok)}")
    if ok:
        t_exact = sum(r.value_exact_match for r in ok)
        t_num = sum(r.value_numeric_match for r in ok)
        t_html = sum(r.value_text_diff for r in ok)
        t_real = sum(r.value_real_mismatch for r in ok)
        t_all = t_exact + t_num + t_html + t_real
        lines.append(f"完全一致: {t_exact}/{t_all} ({t_exact/t_all*100:.1f}%)")
        lines.append(f"数値同値: {t_num}/{t_all} ({t_num/t_all*100:.1f}%)  ← 小数末尾ゼロの差")
        lines.append(f"HTML差異: {t_html}/{t_all} ({t_html/t_all*100:.1f}%)  ← TextBlock の HTML タグ有無")
        lines.append(f"真の不一致: {t_real}/{t_all} ({t_real/t_all*100:.1f}%)  ← 要調査")
        lines.append(f"実質一致率: {(t_exact+t_num+t_html)/t_all*100:.1f}%")

    return "\n".join(lines)


async def main() -> None:
    edinet.configure(api_key=os.environ.get("EDINET_API_KEY", ""))

    print(f"対象: {len(TARGETS)} 企業")
    sem = asyncio.Semaphore(4)
    t0 = time.monotonic()
    results = await asyncio.gather(*[process(t, sem) for t in TARGETS])
    elapsed = time.monotonic() - t0
    print(f"全体: {elapsed:.1f} 秒")

    text = report(list(results))
    print(text)

    out = os.path.join(os.path.dirname(__file__), "ixbrl_compare_results.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n保存: {out}")


if __name__ == "__main__":
    asyncio.run(main())

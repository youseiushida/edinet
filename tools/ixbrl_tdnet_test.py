"""TDnet iXBRL サンプルのパーステスト。

samples/ 配下の TDnet 決算短信 iXBRL ファイルをパースし、
抽出結果を検証する。TDnet は iXBRL のみ（従来 XBRL なし）。
"""
from __future__ import annotations

import os
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import warnings

from edinet.exceptions import EdinetWarning
from edinet.xbrl.ixbrl_parser import parse_ixbrl_facts
from edinet.xbrl.parser import ParsedXBRL

warnings.filterwarnings("always", category=EdinetWarning)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


@dataclass
class FileResult:
    path: str
    fact_count: int = 0
    context_count: int = 0
    unit_count: int = 0
    schema_ref_count: int = 0
    numeric_facts: int = 0
    text_facts: int = 0
    nil_facts: int = 0
    namespaces: set[str] = field(default_factory=set)
    sample_facts: list[str] = field(default_factory=list)
    error: str | None = None
    warnings_: list[str] = field(default_factory=list)


@dataclass
class DirResult:
    name: str
    files: list[FileResult] = field(default_factory=list)
    merged_fact_count: int = 0
    merged_context_count: int = 0
    merged_unit_count: int = 0


def parse_file(path: Path) -> FileResult:
    """1つの iXBRL ファイルをパースする。"""
    result = FileResult(path=path.name)
    try:
        data = path.read_bytes()

        # 警告をキャプチャ
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", EdinetWarning)
            parsed = parse_ixbrl_facts(data, source_path=str(path), strict=False)
            result.warnings_ = [str(x.message) for x in w]

        result.fact_count = len(parsed.facts)
        result.context_count = len(parsed.contexts)
        result.unit_count = len(parsed.units)
        result.schema_ref_count = len(parsed.schema_refs)

        for f in parsed.facts:
            if f.is_nil:
                result.nil_facts += 1
            elif f.unit_ref is not None:
                result.numeric_facts += 1
            else:
                result.text_facts += 1
            result.namespaces.add(f.namespace_uri)

        # サンプル Fact（最初の5つ）
        for f in parsed.facts[:8]:
            val = f.value_raw
            if val and len(val) > 40:
                val = val[:40] + "..."
            result.sample_facts.append(
                f"  {f.local_name}: {val} "
                f"(ctx={f.context_ref}, unit={f.unit_ref})"
            )
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    return result


def merge_dir_results(files: list[FileResult], parsed_list: list[ParsedXBRL]) -> tuple[int, int, int]:
    """ディレクトリ内の全パース結果をマージした統計を返す。"""
    from dataclasses import replace
    all_facts = []
    seen_ctx: set[str] = set()
    seen_unit: set[str] = set()
    ctx_count = 0
    unit_count = 0
    order = 0
    for parsed in parsed_list:
        for ctx in parsed.contexts:
            if ctx.context_id and ctx.context_id not in seen_ctx:
                seen_ctx.add(ctx.context_id)
                ctx_count += 1
        for unit in parsed.units:
            if unit.unit_id and unit.unit_id not in seen_unit:
                seen_unit.add(unit.unit_id)
                unit_count += 1
        for f in parsed.facts:
            all_facts.append(replace(f, order=order))
            order += 1
    return len(all_facts), ctx_count, unit_count


def main() -> None:
    if not SAMPLES_DIR.exists():
        print(f"samples/ が見つかりません: {SAMPLES_DIR}")
        return

    dirs = sorted([d for d in SAMPLES_DIR.iterdir() if d.is_dir()])
    print(f"TDnet サンプルディレクトリ: {len(dirs)} 件")
    print("=" * 100)

    all_dir_results: list[DirResult] = []

    for d in dirs:
        htm_files = sorted(d.glob("*-ixbrl.htm"))
        if not htm_files:
            continue

        dr = DirResult(name=d.name)
        print(f"\n{'='*80}")
        print(f"■ {d.name} ({len(htm_files)} iXBRL files)")
        print(f"{'='*80}")

        parsed_list: list[ParsedXBRL] = []
        for htm in htm_files:
            fr = parse_file(htm)
            dr.files.append(fr)

            status = "OK" if fr.error is None else f"ERROR: {fr.error}"
            print(f"\n  {fr.path}")
            print(f"    Status: {status}")
            if fr.error:
                continue

            print(f"    Facts: {fr.fact_count} (numeric={fr.numeric_facts}, "
                  f"text={fr.text_facts}, nil={fr.nil_facts})")
            print(f"    Contexts: {fr.context_count}, Units: {fr.unit_count}, "
                  f"SchemaRefs: {fr.schema_ref_count}")

            ns_short = [ns.split("/")[-1] if "/" in ns else ns for ns in sorted(fr.namespaces)]
            print(f"    Namespaces: {', '.join(ns_short[:5])}")

            if fr.sample_facts:
                print(f"    Sample Facts:")
                for sf in fr.sample_facts[:5]:
                    print(f"      {sf}")

            if fr.warnings_:
                print(f"    Warnings ({len(fr.warnings_)}):")
                for w in fr.warnings_[:3]:
                    print(f"      {w[:120]}")

            # パース結果を保存（マージ用）
            data = htm.read_bytes()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    parsed = parse_ixbrl_facts(data, source_path=str(htm), strict=False)
                    parsed_list.append(parsed)
                except Exception:
                    pass

        # マージ統計
        if parsed_list:
            mf, mc, mu = merge_dir_results(dr.files, parsed_list)
            dr.merged_fact_count = mf
            dr.merged_context_count = mc
            dr.merged_unit_count = mu
            print(f"\n  [マージ結果] Facts={mf}, Contexts={mc}, Units={mu}")

        all_dir_results.append(dr)

    # サマリー
    print("\n\n" + "=" * 100)
    print("サマリー")
    print("=" * 100)
    total_files = 0
    total_ok = 0
    total_err = 0
    total_facts = 0
    for dr in all_dir_results:
        for fr in dr.files:
            total_files += 1
            if fr.error:
                total_err += 1
            else:
                total_ok += 1
                total_facts += fr.fact_count
        print(f"  {dr.name}: {len(dr.files)} files, "
              f"merged facts={dr.merged_fact_count}, "
              f"contexts={dr.merged_context_count}, "
              f"units={dr.merged_unit_count}")

    print(f"\n合計: {total_files} files, 成功={total_ok}, エラー={total_err}, "
          f"Fact合計={total_facts}")


if __name__ == "__main__":
    main()

"""トヨタの連結フォールバック問題の診断スクリプト。

トヨタの有報XBRLを取得し、以下を調査する:
1. コンテキストのDimension構造（連結/個別の区分）
2. PL概念セットに該当するFactがどのコンテキストに紐づいているか
3. 連結判定が失敗する原因の特定
"""
import json
import os
import sys
import importlib.resources

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from edinet._config import configure
configure(
    api_key="your_api_key_here",
    taxonomy_path="/mnt/c/Users/nezow/Downloads/ALL_20251101",
)

from edinet.api.download import (
    DownloadFileType,
    download_document,
    find_primary_xbrl_path,
    list_zip_members,
    extract_zip_member,
)
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts, DurationPeriod
from edinet.financial.statements import (
    _CONSOLIDATED_AXIS_SUFFIX,
    _CONSOLIDATED_MEMBER_SUFFIX,
    _NONCONSOLIDATED_MEMBER_SUFFIX,
)

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "debug_toyota_output.txt")
DOC_ID = "S100VWVY"  # トヨタ 有価証券報告書 第121期

def write(f, msg=""):
    print(msg)
    f.write(msg + "\n")

def main():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        write(f, "=" * 70)
        write(f, "トヨタ 連結フォールバック問題 診断")
        write(f, f"doc_id: {DOC_ID}")
        write(f, "=" * 70)

        # 1. ZIP をダウンロード
        write(f, "\n--- ZIPダウンロード ---")
        zip_bytes = download_document(DOC_ID, file_type=DownloadFileType.XBRL_AND_AUDIT)
        write(f, f"  ZIPサイズ: {len(zip_bytes):,} bytes")

        # 2. ZIP構造を確認
        write(f, "\n--- ZIP構造 ---")
        members = list_zip_members(zip_bytes)

        xbrl_files = [m for m in members if m.lower().endswith(".xbrl")]
        htm_files = [m for m in members if "_ixbrl" in m.lower()]

        write(f, f"  .xbrl ファイル数: {len(xbrl_files)}")
        for x in xbrl_files:
            write(f, f"    {x}")

        write(f, f"\n  iXBRL (.htm) ファイル数: {len(htm_files)}")
        for h in htm_files[:10]:
            write(f, f"    {h}")
        if len(htm_files) > 10:
            write(f, f"    ... 他 {len(htm_files) - 10} 件")

        # 3. 代表XBRLを特定
        primary_path = find_primary_xbrl_path(zip_bytes)
        write(f, f"\n  代表XBRL: {primary_path}")

        # 4. 代表XBRLをパース
        write(f, "\n--- 代表XBRL パース ---")
        xbrl_bytes = extract_zip_member(zip_bytes, primary_path)
        write(f, f"  XBRLサイズ: {len(xbrl_bytes):,} bytes")

        parsed = parse_xbrl_facts(xbrl_bytes, source_path=primary_path)
        write(f, f"  Fact数: {len(parsed.facts)}")
        write(f, f"  Context数: {len(parsed.contexts)}")

        # 5. コンテキストを構造化して分析
        write(f, "\n--- コンテキスト分析 ---")
        structured = structure_contexts(parsed.contexts)

        consolidated_contexts = []
        nonconsolidated_contexts = []
        other_contexts = []
        no_dim_contexts = []

        for cid, ctx in structured.items():
            has_noncons_member = any(
                dim.member.endswith(_NONCONSOLIDATED_MEMBER_SUFFIX)
                for dim in ctx.dimensions
            )
            has_cons_member = any(
                dim.member.endswith(_CONSOLIDATED_MEMBER_SUFFIX)
                and not dim.member.endswith(_NONCONSOLIDATED_MEMBER_SUFFIX)
                for dim in ctx.dimensions
            )

            if len(ctx.dimensions) == 0:
                no_dim_contexts.append((cid, ctx))
            elif has_noncons_member:
                nonconsolidated_contexts.append((cid, ctx))
            elif has_cons_member:
                consolidated_contexts.append((cid, ctx))
            else:
                other_contexts.append((cid, ctx))

        write(f, f"  Dimension なし: {len(no_dim_contexts)}件")
        for cid, ctx in no_dim_contexts:
            write(f, f"    {cid}: period={ctx.period}")

        write(f, f"\n  明示的ConsolidatedMember: {len(consolidated_contexts)}件")
        for cid, ctx in consolidated_contexts:
            dims_str = ", ".join(f"{d.axis.split('}')[1]}={d.member.split('}')[1]}" for d in ctx.dimensions)
            write(f, f"    {cid}: period={ctx.period}, dims=[{dims_str}]")

        write(f, f"\n  NonConsolidatedMember: {len(nonconsolidated_contexts)}件")
        for cid, ctx in nonconsolidated_contexts:
            dims_str = ", ".join(f"{d.axis.split('}')[1]}={d.member.split('}')[1]}" for d in ctx.dimensions)
            write(f, f"    {cid}: period={ctx.period}, dims=[{dims_str}]")

        write(f, f"\n  その他 Dimension: {len(other_contexts)}件")
        for cid, ctx in other_contexts[:20]:
            dims_str = ", ".join(f"{d.axis.split('}')[1]}={d.member.split('}')[1]}" for d in ctx.dimensions)
            write(f, f"    {cid}: period={ctx.period}, dims=[{dims_str}]")
        if len(other_contexts) > 20:
            write(f, f"    ... 他 {len(other_contexts) - 20}件")

        # 6. PL概念セットとのマッチング
        write(f, "\n--- PL概念セット マッチング ---")
        ref = importlib.resources.files("edinet.xbrl.data").joinpath("pl_jgaap.json")
        with importlib.resources.as_file(ref) as path:
            pl_concepts = json.loads(path.read_text(encoding="utf-8"))
        known_pl = {d["concept"] for d in pl_concepts}
        write(f, f"  PL概念数: {len(known_pl)}")

        # PL概念に該当するFactを収集
        pl_facts = [fact for fact in parsed.facts if fact.local_name in known_pl]
        write(f, f"  PL該当Fact数: {len(pl_facts)}")

        # コンテキスト別にPL Factを分類
        context_pl_facts = {}
        for fact in pl_facts:
            context_pl_facts.setdefault(fact.context_ref, []).append(fact)

        write(f, f"\n  コンテキスト別 PL Fact分布:")
        for cid, facts in sorted(context_pl_facts.items()):
            ctx = structured.get(cid)
            if ctx:
                dims_str = ", ".join(f"{d.member.split('}')[1]}" for d in ctx.dimensions) if ctx.dimensions else "(なし)"
                write(f, f"    {cid}: {len(facts)}件, period={ctx.period}, dims={dims_str}")
                for fact in facts[:3]:
                    write(f, f"      {fact.local_name} = {fact.value_raw}")
                if len(facts) > 3:
                    write(f, f"      ... 他 {len(facts) - 3}件")

        # 7. 名前空間分布
        write(f, "\n--- 名前空間分布 ---")
        ns_counts = {}
        for fact in parsed.facts:
            # namespace URIからわかりやすいプレフィックスを抽出
            uri = fact.namespace_uri
            if "jppfs" in uri:
                prefix = "jppfs_cor"
            elif "jpcrp" in uri:
                prefix = "jpcrp_cor"
            elif "jpdei" in uri:
                prefix = "jpdei_cor"
            elif "ifrs" in uri.lower():
                prefix = "ifrs"
            else:
                parts = uri.rstrip("/").split("/")
                prefix = parts[-1] if parts else uri
            ns_counts[prefix] = ns_counts.get(prefix, 0) + 1
        for ns, count in sorted(ns_counts.items(), key=lambda x: -x[1]):
            write(f, f"  {ns}: {count}件")

        # 8. DurationPeriodのコンテキストでPL概念を持つものを詳細分析
        write(f, "\n--- DurationPeriod + PL概念 の詳細 ---")
        for cid, facts in sorted(context_pl_facts.items()):
            ctx = structured.get(cid)
            if ctx and isinstance(ctx.period, DurationPeriod):
                has_no_dim = len(ctx.dimensions) == 0
                has_noncons = any(d.member.endswith(_NONCONSOLIDATED_MEMBER_SUFFIX) for d in ctx.dimensions)
                has_cons_only = (
                    len(ctx.dimensions) > 0
                    and all(d.axis.endswith(_CONSOLIDATED_AXIS_SUFFIX) for d in ctx.dimensions)
                    and not has_noncons
                )

                if has_no_dim:
                    consol_label = "連結(dim無し)"
                elif has_cons_only:
                    consol_label = "連結(明示的)"
                elif has_noncons:
                    consol_label = "個別"
                else:
                    consol_label = "その他dim"

                write(f, f"\n  {cid}: [{consol_label}]")
                write(f, f"    期間: {ctx.period.start_date} ~ {ctx.period.end_date}")
                if ctx.dimensions:
                    write(f, f"    Dimensions: {[f'{d.axis.split(chr(125))[1]}={d.member.split(chr(125))[1]}' for d in ctx.dimensions]}")
                write(f, f"    PL Fact数: {len(facts)}")
                for fact in facts:
                    write(f, f"      {fact.local_name} = {fact.value_raw}")

        # 9. 全Factで dimension なし かつ DurationPeriod のものを確認
        write(f, "\n--- Dimension なし + DurationPeriod の全Fact ---")
        for cid, ctx in no_dim_contexts:
            if isinstance(ctx.period, DurationPeriod):
                facts_in_ctx = [fact for fact in parsed.facts if fact.context_ref == cid]
                write(f, f"\n  {cid}: {len(facts_in_ctx)}件")
                write(f, f"    期間: {ctx.period.start_date} ~ {ctx.period.end_date}")
                for fact in facts_in_ctx[:20]:
                    write(f, f"      [{fact.namespace_uri.split('/')[-1]}] {fact.local_name} = {fact.value_raw}")
                if len(facts_in_ctx) > 20:
                    write(f, f"      ... 他 {len(facts_in_ctx) - 20}件")

        write(f, "\n" + "=" * 70)
        write(f, "診断完了")
        write(f, f"結果は {OUTPUT_FILE} に保存")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    main()

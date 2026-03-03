"""Lane 6 調査: 実データのディメンション軸を全量スキャンする。

目的:
- Filing 内にどんなディメンション軸が存在するか
- 各軸の日本語・英語ラベルは TaxonomyResolver で解決可能か
- 地域セグメント軸 (GeographicAreasAxis?) は実在するか
- 各軸にどんなメンバーが紐付くか

使い方:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/lane6_dimension_probe.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

# ── edinet ライブラリ ──
import edinet
from edinet.api.documents import get_documents
from edinet.api.download import (
    DownloadFileType,
    download_document,
    extract_zip_member,
    list_zip_members,
)
from edinet.models.filing import Filing
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts
from edinet.xbrl.facts import build_line_items
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl._namespaces import (
    classify_namespace,
    is_standard_taxonomy,
)
from edinet.xbrl.linkbase.definition import parse_definition_linkbase


OUTPUT_PATH = Path("tools/lane6_dimension_probe_results.md")

# ── 設定 ──
# 大手 J-GAAP 企業が有報を出す日付を複数試す
PROBE_DATES = [
    "2025-06-27",  # 3月決算企業の有報提出ピーク
]
# 有価証券報告書の docTypeCode
ANNUAL_REPORT_CODE = "120"
MAX_FILINGS = 5  # 調査する Filing 数

# セグメントが豊富な大手企業を優先指定（E02144=トヨタ自動車は IFRS なので除外）
PRIORITY_EDINET_CODES = [
    "E02529",  # 日立製作所 (IFRS, 多角経営)
    "E01777",  # パナソニック (IFRS)
    "E04425",  # ソニーグループ (IFRS)
    "E00748",  # 三菱重工業 (J-GAAP, 多角)
    "E01737",  # NEC (J-GAAP)
    "E01624",  # NTT (J-GAAP)
    "E04837",  # ソフトバンクグループ (IFRS)
    "E02516",  # 住友商事 (IFRS)
]


def _extract_local(clark: str) -> str:
    """Clark notation → ローカル名。"""
    return clark.rsplit("}", 1)[-1] if "}" in clark else clark


def _extract_ns(clark: str) -> str:
    """Clark notation → 名前空間 URI。"""
    if clark.startswith("{"):
        return clark[1 : clark.index("}")]
    return ""


def probe_filing(filing: Filing, taxonomy_path: str, out: list[str]) -> None:
    """1件の Filing のディメンション軸を全量調査する。"""
    out.append(f"\n## {filing.filer_name} ({filing.edinet_code}) — {filing.doc_id}")
    out.append(f"- 書類種別: {filing.doc_description}")
    out.append(f"- 提出日: {filing.filing_date}")

    # ZIP ダウンロード
    zip_bytes = download_document(filing.doc_id, file_type=DownloadFileType.XBRL_AND_AUDIT)
    members = list_zip_members(zip_bytes)

    # XBRL パース
    xbrl_path = next((m for m in members if "PublicDoc/" in m and m.endswith(".xbrl")), None)
    if not xbrl_path:
        out.append("- **XBRL ファイルが見つかりません**")
        return
    xbrl_bytes = extract_zip_member(zip_bytes, xbrl_path)
    parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)

    # Context 構造化
    ctx_map = structure_contexts(parsed.contexts)

    # TaxonomyResolver セットアップ
    resolver = TaxonomyResolver(taxonomy_path)

    # 提出者ラベルロード
    lab_files = [m for m in members if m.endswith("_lab.xml") and "PublicDoc/" in m]
    lab_en_files = [m for m in members if m.endswith("_lab-en.xml") and "PublicDoc/" in m]
    xsd_files = [m for m in members if m.endswith(".xsd") and "PublicDoc/" in m]

    lab_bytes = extract_zip_member(zip_bytes, lab_files[0]) if lab_files else None
    lab_en_bytes = extract_zip_member(zip_bytes, lab_en_files[0]) if lab_en_files else None
    xsd_bytes = extract_zip_member(zip_bytes, xsd_files[0]) if xsd_files else None
    filer_label_count = resolver.load_filer_labels(
        lab_bytes, lab_en_bytes, xsd_bytes=xsd_bytes
    )
    out.append(f"- 提出者ラベル数: {filer_label_count}")

    # LineItem 構築
    items = build_line_items(parsed.facts, ctx_map, resolver)
    out.append(f"- LineItem 総数: {len(items)}")

    # ── ディメンション軸の全量収集 ──
    # axis_clark → { member_clark → [LineItem indices] }
    axis_members: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    items_with_dims = 0

    for idx, item in enumerate(items):
        if item.dimensions:
            items_with_dims += 1
            for dim in item.dimensions:
                axis_members[dim.axis][dim.member].append(idx)

    out.append(f"- ディメンション付き LineItem 数: {items_with_dims}")
    out.append(f"- ユニーク軸数: {len(axis_members)}")

    # ── 各軸の詳細 ──
    out.append("\n### ディメンション軸一覧\n")
    out.append("| # | 軸ローカル名 | 軸ラベル(ja) | 軸ラベル(en) | メンバー数 | LineItem数 | NS種別 |")
    out.append("|---|---|---|---|---|---|---|")

    axis_details: list[tuple[str, str, str, str, int, int, str]] = []

    for i, (axis_clark, member_dict) in enumerate(sorted(axis_members.items(), key=lambda x: -sum(len(v) for v in x[1].values())), 1):
        axis_local = _extract_local(axis_clark)
        axis_ns = _extract_ns(axis_clark)

        # ラベル解決
        try:
            label_ja = resolver.resolve_clark(axis_clark, lang="ja")
            ja_text = label_ja.text
            ja_source = label_ja.source.value
        except Exception as e:
            ja_text = f"ERROR: {e}"
            ja_source = "error"

        try:
            label_en = resolver.resolve_clark(axis_clark, lang="en")
            en_text = label_en.text
        except Exception:
            en_text = "(なし)"

        ns_info = classify_namespace(axis_ns)
        ns_type = f"{ns_info.category.value}"
        if ns_info.module_name:
            ns_type += f" ({ns_info.module_name})"

        member_count = len(member_dict)
        item_count = sum(len(v) for v in member_dict.values())

        out.append(f"| {i} | `{axis_local}` | {ja_text} [{ja_source}] | {en_text} | {member_count} | {item_count} | {ns_type} |")
        axis_details.append((axis_clark, axis_local, ja_text, en_text, member_count, item_count, ns_type))

    # ── セグメント関連軸のメンバー詳細 ──
    segment_keywords = ["Segment", "Geographic", "Area", "Region", "Product"]
    for axis_clark, axis_local, ja_text, en_text, member_count, item_count, ns_type in axis_details:
        # セグメント関連っぽい軸のメンバーを詳細出力
        if any(kw.lower() in axis_local.lower() for kw in segment_keywords) or member_count >= 3:
            member_dict = axis_members[axis_clark]
            out.append(f"\n### 軸: `{axis_local}` ({ja_text}) — メンバー詳細\n")
            out.append("| # | メンバーローカル名 | メンバーラベル(ja) | メンバーラベル(en) | LineItem数 | 標準/提出者 |")
            out.append("|---|---|---|---|---|---|")

            for j, (member_clark, item_indices) in enumerate(
                sorted(member_dict.items(), key=lambda x: -len(x[1])), 1
            ):
                m_local = _extract_local(member_clark)
                m_ns = _extract_ns(member_clark)

                try:
                    m_label_ja = resolver.resolve_clark(member_clark, lang="ja")
                    m_ja = m_label_ja.text
                    m_ja_src = m_label_ja.source.value
                except Exception:
                    m_ja = "(解決失敗)"
                    m_ja_src = "error"

                try:
                    m_label_en = resolver.resolve_clark(member_clark, lang="en")
                    m_en = m_label_en.text
                except Exception:
                    m_en = "(なし)"

                is_std = is_standard_taxonomy(m_ns)
                std_label = "標準" if is_std else "**提出者**"

                out.append(f"| {j} | `{m_local}` | {m_ja} [{m_ja_src}] | {m_en} | {len(item_indices)} | {std_label} |")

    # ── Definition Linkbase からの軸情報（あれば） ──
    def_files = [m for m in members if m.endswith("_def.xml") and "PublicDoc/" in m]
    if def_files:
        def_bytes = extract_zip_member(zip_bytes, def_files[0])
        def_trees = parse_definition_linkbase(def_bytes, source_path=def_files[0])

        out.append(f"\n### Definition Linkbase 軸情報 ({def_files[0]})\n")
        out.append("| role_uri (末尾) | Table | Axis | デフォルトメンバー | ドメインメンバー数 |")
        out.append("|---|---|---|---|---|")

        for role_uri, tree in def_trees.items():
            role_short = role_uri.rsplit("/", 1)[-1] if "/" in role_uri else role_uri
            for hc in tree.hypercubes:
                for axis in hc.axes:
                    domain_count = 0
                    if axis.domain:
                        # 再帰的にメンバー数をカウント
                        stack = [axis.domain]
                        while stack:
                            node = stack.pop()
                            domain_count += 1
                            stack.extend(node.children)
                    default = axis.default_member or "(なし)"
                    out.append(f"| `{role_short}` | `{hc.table_concept}` | `{axis.axis_concept}` | `{default}` | {domain_count} |")


def main() -> None:
    """メイン処理。"""
    api_key = os.environ.get("EDINET_API_KEY", "")
    taxonomy_path = os.environ.get("EDINET_TAXONOMY_ROOT", "")
    if not api_key or not taxonomy_path:
        print("EDINET_API_KEY と EDINET_TAXONOMY_ROOT を設定してください", file=sys.stderr)
        sys.exit(1)

    # WSL パス変換
    if taxonomy_path.startswith("C:"):
        taxonomy_path = "/mnt/c" + taxonomy_path[2:].replace("\\", "/")

    edinet.configure(api_key=api_key, taxonomy_path=taxonomy_path)

    out: list[str] = ["# Lane 6 ディメンション軸調査結果\n"]

    for probe_date in PROBE_DATES:
        out.append(f"\n# 調査日: {probe_date}\n")
        print(f"=== {probe_date} の書類を取得中... ===")

        result = get_documents(probe_date)

        # 有報 + XBRL あり + submitDateTime あり のみフィルタ
        raw_candidates = [
            doc for doc in result.get("results", [])
            if doc.get("docTypeCode") == ANNUAL_REPORT_CODE
            and doc.get("xbrlFlag") == "1"
            and doc.get("edinetCode")
            and doc.get("submitDateTime")
        ]
        out.append(f"- 有報候補数: {len(raw_candidates)}")

        # 優先企業を先頭に、残りはそのまま
        priority = [d for d in raw_candidates if d.get("edinetCode") in PRIORITY_EDINET_CODES]
        others = [d for d in raw_candidates if d.get("edinetCode") not in PRIORITY_EDINET_CODES]
        sorted_candidates = priority + others

        for raw_doc in sorted_candidates[:MAX_FILINGS]:
            try:
                filing = Filing.from_api_response(raw_doc)
                probe_filing(filing, taxonomy_path, out)
            except Exception as e:
                name = raw_doc.get("filerName", "?")
                out.append(f"\n## {name} — ERROR: {e}")
                import traceback
                out.append(f"```\n{traceback.format_exc()}```")

    # 結果出力
    OUTPUT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"\n結果を {OUTPUT_PATH} に出力しました。")


if __name__ == "__main__":
    main()

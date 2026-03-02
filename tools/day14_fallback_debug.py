"""FALLBACK が残っている書類の具体的な concept を特定する。"""

from __future__ import annotations

import os
import sys

import edinet

api_key = os.environ.get("EDINET_API_KEY")
if not api_key:
    print("ERROR: EDINET_API_KEY 環境変数を設定してください。")
    sys.exit(1)
edinet.configure(api_key=api_key)

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

TAXONOMY_ROOT = os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    "/mnt/c/Users/nezow/Downloads/ALL_20251101",
)

# スイープで FALLBACK が出た doc_id
TARGETS = [
    ("240 公開買付届出書", "S100XN7N"),   # FB=22.6%
    ("290 意見表明報告書", "S100XN88"),   # FB=11.1%
    ("350 大量保有報告書", "S100XLPV"),   # FB=5.0%
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


def main() -> int:
    """メイン関数。"""
    resolver = TaxonomyResolver(TAXONOMY_ROOT)

    for label, doc_id in TARGETS:
        print(f"\n{'=' * 70}")
        print(f"{label} (doc_id={doc_id})")
        print(f"{'=' * 70}")

        zip_bytes = download_document(doc_id, file_type="1")

        # ZIP 内のファイル一覧
        members = list_zip_members(zip_bytes)
        taxonomy_files = [m for m in members if "publicdoc" in m.lower().replace("\\", "/")]
        print(f"\nPublicDoc 内ファイル:")
        for m in sorted(taxonomy_files):
            print(f"  {m}")

        # XBRL
        primary = extract_primary_xbrl(zip_bytes)
        if primary is None:
            print("  XBRL なし")
            continue
        xbrl_path, xbrl_bytes = primary

        # 提出者タクソノミ
        filer_files = find_filer_taxonomy_files(zip_bytes)
        resolver.clear_filer_labels()
        print(f"\n提出者タクソノミ: lab={'lab' in filer_files}, lab_en={'lab_en' in filer_files}, xsd={'xsd' in filer_files}")
        if filer_files:
            loaded = resolver.load_filer_labels(
                lab_xml_bytes=filer_files.get("lab"),
                lab_en_xml_bytes=filer_files.get("lab_en"),
                xsd_bytes=filer_files.get("xsd"),
            )
            print(f"  filer labels loaded: {loaded}")

        # パイプライン
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        ctx_map = structure_contexts(parsed.contexts)
        items = build_line_items(parsed.facts, ctx_map, resolver)

        # FALLBACK の詳細
        fallback_items = [
            item for item in items if item.label_ja.source == LabelSource.FALLBACK
        ]
        print(f"\n全 LineItem: {len(items)}, FALLBACK: {len(fallback_items)}")

        if fallback_items:
            print(f"\nFALLBACK 一覧:")
            for item in fallback_items:
                print(
                    f"  ns={item.namespace_uri}"
                    f"\n    local_name={item.local_name}"
                    f"\n    label_ja.text={item.label_ja.text}"
                )

            # namespace 別集計
            from collections import Counter
            ns_counter = Counter(item.namespace_uri for item in fallback_items)
            print(f"\nFALLBACK の namespace 別集計:")
            for ns, cnt in ns_counter.most_common():
                print(f"  {cnt:3d}  {ns}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

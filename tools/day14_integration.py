"""Day 14 統合テスト — 実データでフルパイプラインを検証するスクリプト。

EDINET API → ZIP → parse → structure_contexts → build_line_items
のフルパイプラインを多様な企業・書類タイプで実行し、
エッジケースや問題点を洗い出す。

Usage:
    uv run python tools/day14_integration.py
"""

from __future__ import annotations

import os
import sys
import traceback
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

import edinet

api_key = os.environ.get("EDINET_API_KEY")
if not api_key:
    print("ERROR: EDINET_API_KEY 環境変数を設定してください。")
    sys.exit(1)
edinet.configure(api_key=api_key)

from edinet import documents
from edinet.api.download import (
    download_document,
    extract_primary_xbrl,
    list_zip_members,
    extract_zip_member,
)  # noqa: E402
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts
from edinet.xbrl.taxonomy import TaxonomyResolver, LabelSource
from edinet.xbrl.facts import build_line_items

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
TAXONOMY_ROOT = "/mnt/c/Users/nezow/Downloads/ALL_20251101"


@dataclass
class TestTarget:
    """テスト対象の定義。"""
    label: str
    date_str: str
    doc_type: str | None = None
    edinet_code: str | None = None
    filer_keyword: str | None = None
    doc_id: str | None = None


# 多様な企業・書類タイプのテストケース
TARGETS: list[TestTarget] = [
    # --- 有価証券報告書 (120) ---
    # 大企業（製造業）
    TestTarget(
        label="トヨタ自動車 有報",
        date_str="2025-06-25",
        doc_type="120",
        filer_keyword="トヨタ自動車",
    ),
    # 小規模企業
    TestTarget(
        label="小規模企業 有報",
        date_str="2025-06-25",
        doc_type="120",
    ),
    # IT 企業
    TestTarget(
        label="IT企業 有報",
        date_str="2025-06-27",
        doc_type="120",
    ),
    # --- 四半期報告書 (140) ---
    TestTarget(
        label="四半期報告書",
        date_str="2025-02-14",
        doc_type="140",
    ),
    # --- 半期報告書 (160) ---
    TestTarget(
        label="半期報告書",
        date_str="2025-03-14",
        doc_type="160",
    ),
    # --- 訂正報告書 ---
    TestTarget(
        label="訂正有報",
        date_str="2025-06-27",
        doc_type="130",
    ),
    # --- 大量保有報告書 (350) ---
    TestTarget(
        label="大量保有報告書",
        date_str="2025-06-25",
        doc_type="350",
    ),
]


def find_filer_taxonomy_files(zip_bytes: bytes) -> dict[str, bytes]:
    """ZIP 内から提出者別タクソノミファイルを探して返す。

    Returns:
        キーが種別名（"lab", "lab_en", "xsd"）、値が bytes の辞書。
    """
    members = list_zip_members(zip_bytes)
    result: dict[str, bytes] = {}

    for name in members:
        lower = name.lower()
        # 提出者の _lab.xml / _lab-en.xml / .xsd を探す
        if "publicdoc/" not in lower.replace("\\", "/"):
            continue
        if lower.endswith("_lab.xml") and "_lab-en" not in lower:
            result["lab"] = extract_zip_member(zip_bytes, name)
        elif lower.endswith("_lab-en.xml"):
            result["lab_en"] = extract_zip_member(zip_bytes, name)
        elif lower.endswith(".xsd") and "audit" not in lower:
            # 提出者の XSD（監査報告書のものは除外）
            if "xsd" not in result:
                result["xsd"] = extract_zip_member(zip_bytes, name)

    return result


def run_pipeline(target: TestTarget, resolver: TaxonomyResolver) -> dict:
    """1つのテストケースに対してフルパイプラインを実行する。

    Returns:
        テスト結果の辞書。
    """
    result = {
        "label": target.label,
        "status": "UNKNOWN",
        "error": None,
        "stats": {},
    }

    try:
        # 1. Filing の検索
        if target.doc_id:
            filings = documents(target.date_str, doc_type=target.doc_type)
            filing = next(
                (f for f in filings if f.doc_id == target.doc_id), None
            )
            if filing is None:
                result["status"] = "SKIP"
                result["error"] = f"doc_id={target.doc_id} not found"
                return result
        else:
            filings = documents(target.date_str, doc_type=target.doc_type)
            if not filings:
                result["status"] = "SKIP"
                result["error"] = "No filings found"
                return result

            # filer_keyword でフィルタ
            if target.filer_keyword:
                matched = [
                    f
                    for f in filings
                    if f.filer_name and target.filer_keyword in f.filer_name
                ]
                filing = matched[0] if matched else None
            else:
                # has_xbrl=True のものから最初の1件
                xbrl_filings = [f for f in filings if f.has_xbrl]
                filing = xbrl_filings[0] if xbrl_filings else None

            if filing is None:
                result["status"] = "SKIP"
                result["error"] = "No matching filing"
                return result

        result["stats"]["doc_id"] = filing.doc_id
        result["stats"]["filer_name"] = filing.filer_name
        result["stats"]["doc_type_code"] = filing.doc_type_code

        if not filing.has_xbrl:
            result["status"] = "SKIP"
            result["error"] = "has_xbrl=False"
            return result

        # 2. ZIP ダウンロード
        zip_bytes = download_document(filing.doc_id, file_type="1")

        # 3. 代表 XBRL 取得
        primary = extract_primary_xbrl(zip_bytes)
        if primary is None:
            result["status"] = "FAIL"
            result["error"] = "No primary XBRL found in ZIP"
            return result
        xbrl_path, xbrl_bytes = primary
        result["stats"]["xbrl_path"] = xbrl_path
        result["stats"]["xbrl_size"] = len(xbrl_bytes)

        # 4. 提出者タクソノミ取得
        filer_files = find_filer_taxonomy_files(zip_bytes)
        resolver.clear_filer_labels()
        if filer_files:
            loaded = resolver.load_filer_labels(
                lab_xml_bytes=filer_files.get("lab"),
                lab_en_xml_bytes=filer_files.get("lab_en"),
                xsd_bytes=filer_files.get("xsd"),
            )
            result["stats"]["filer_labels_loaded"] = loaded

        # 5. parse_xbrl_facts
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        result["stats"]["raw_facts"] = len(parsed.facts)
        result["stats"]["raw_contexts"] = len(parsed.contexts)
        result["stats"]["raw_units"] = len(parsed.units)

        # 6. structure_contexts
        ctx_map = structure_contexts(parsed.contexts)
        result["stats"]["structured_contexts"] = len(ctx_map)

        # 7. build_line_items
        items = build_line_items(parsed.facts, ctx_map, resolver)
        result["stats"]["line_items"] = len(items)

        # 8. 統計分析
        label_sources = Counter(item.label_ja.source for item in items)
        value_types = Counter(type(item.value).__name__ for item in items)
        ns_counts = Counter(item.namespace_uri for item in items)
        dimension_items = sum(1 for item in items if item.dimensions)
        nil_items = sum(1 for item in items if item.is_nil)

        result["stats"]["label_sources"] = {
            src.value: cnt for src, cnt in label_sources.items()
        }
        result["stats"]["value_types"] = dict(value_types)
        result["stats"]["namespace_count"] = len(ns_counts)
        result["stats"]["top_namespaces"] = [
            (ns.split("/")[-1] if "/" in ns else ns, cnt)
            for ns, cnt in ns_counts.most_common(5)
        ]
        result["stats"]["dimension_items"] = dimension_items
        result["stats"]["nil_items"] = nil_items

        # 9. サンプル出力（数値 Fact 上位 10 件）
        numeric_items = [
            item for item in items if isinstance(item.value, Decimal)
        ]
        result["stats"]["numeric_items"] = len(numeric_items)
        result["stats"]["text_items"] = sum(
            1 for item in items if isinstance(item.value, str)
        )
        result["stats"]["nil_count"] = sum(
            1 for item in items if item.value is None
        )

        # ラベル FALLBACK の割合
        total = len(items)
        fallback_count = label_sources.get(LabelSource.FALLBACK, 0)
        filer_count = label_sources.get(LabelSource.FILER, 0)
        _standard_count = label_sources.get(LabelSource.STANDARD, 0)  # noqa: F841
        result["stats"]["fallback_pct"] = (
            f"{fallback_count / total * 100:.1f}%"
            if total > 0
            else "N/A"
        )
        result["stats"]["filer_pct"] = (
            f"{filer_count / total * 100:.1f}%"
            if total > 0
            else "N/A"
        )

        result["status"] = "PASS"

        # サンプル出力
        result["samples"] = []
        for item in numeric_items[:5]:
            result["samples"].append(
                {
                    "label": item.label_ja.text,
                    "value": f"{item.value:>20,}",
                    "unit": item.unit_ref,
                    "decimals": item.decimals,
                    "source": item.label_ja.source.value,
                    "period": str(item.period),
                    "dims": len(item.dimensions),
                }
            )

    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()

    return result


def main():
    """メイン関数。"""
    print("=" * 80)
    print("Day 14 統合テスト — EDINET フルパイプライン検証")
    print("=" * 80)

    # TaxonomyResolver 初期化
    print(f"\nTaxonomyResolver 初期化: {TAXONOMY_ROOT}")
    resolver = TaxonomyResolver(TAXONOMY_ROOT)
    print(f"  version: {resolver.taxonomy_version}")

    results: list[dict] = []
    for i, target in enumerate(TARGETS, 1):
        print(f"\n{'─' * 60}")
        print(f"[{i}/{len(TARGETS)}] {target.label}")
        print(f"  date={target.date_str}, doc_type={target.doc_type}")
        if target.filer_keyword:
            print(f"  filer_keyword={target.filer_keyword}")

        result = run_pipeline(target, resolver)
        results.append(result)

        status_icon = {
            "PASS": "[OK]",
            "FAIL": "[NG]",
            "SKIP": "[--]",
        }.get(result["status"], "[??]")

        print(f"  {status_icon} {result['status']}", end="")
        if result["error"]:
            print(f" — {result['error']}")
        else:
            print()

        if result["status"] == "PASS":
            stats = result["stats"]
            print(f"  企業: {stats.get('filer_name', '?')}")
            print(f"  doc_id: {stats.get('doc_id', '?')}")
            print(
                f"  Fact: {stats['raw_facts']} → "
                f"LineItem: {stats['line_items']}"
            )
            print(
                f"  数値: {stats['numeric_items']}, "
                f"テキスト: {stats['text_items']}, "
                f"nil: {stats['nil_count']}"
            )
            print(
                f"  ラベル解決: STANDARD={stats['label_sources'].get('standard', 0)}, "
                f"FILER={stats['label_sources'].get('filer', 0)}, "
                f"FALLBACK={stats['label_sources'].get('fallback', 0)} "
                f"({stats['fallback_pct']})"
            )
            print(
                f"  Dimension付き: {stats['dimension_items']}, "
                f"名前空間数: {stats['namespace_count']}"
            )
            print(f"  上位NS: {stats['top_namespaces']}")

            if result.get("samples"):
                print("  --- サンプル数値 Fact ---")
                for s in result["samples"]:
                    print(
                        f"    {s['label']}: {s['value']} "
                        f"({s['unit']}, decimals={s['decimals']}, "
                        f"source={s['source']})"
                    )

        if result["status"] == "FAIL" and result.get("traceback"):
            print("  --- Traceback ---")
            for line in result["traceback"].splitlines()[-5:]:
                print(f"    {line}")

    # サマリー
    print(f"\n{'=' * 80}")
    print("サマリー")
    print(f"{'=' * 80}")
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")
    print(f"  PASS: {pass_count}, FAIL: {fail_count}, SKIP: {skip_count}")

    if fail_count > 0:
        print("\n  失敗したテスト:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    - {r['label']}: {r['error']}")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

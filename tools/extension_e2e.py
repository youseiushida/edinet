"""Extension モジュール E2E テスト（実データ）。

実際の EDINET API から Filing を取得し、
export_parquet → import_parquet のラウンドトリップを検証する。
"""

from __future__ import annotations

import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

# パス設定
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet
from edinet.extension import export_parquet, import_parquet

# 設定
API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_ROOT = os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    "/mnt/c/Users/nezow/Downloads/ALL_20251101",
)
TARGET_DATE = "2026-03-06"  # 適当な日付


def main() -> None:
    edinet.configure(api_key=API_KEY, taxonomy_path=TAXONOMY_ROOT)

    print(f"=== Extension E2E: {TARGET_DATE} ===")
    print()

    # 1. Filing 取得
    filings = edinet.documents(TARGET_DATE)
    print(f"取得 Filing 数: {len(filings)}")

    # has_xbrl=True を最大 5 件取得
    xbrl_filings = [f for f in filings if f.has_xbrl][:5]
    non_xbrl = [f for f in filings if not f.has_xbrl][:3]
    print(f"  XBRL あり: {len(xbrl_filings)} 件（テスト対象）")
    print(f"  XBRL なし: {len(non_xbrl)} 件（テスト対象）")
    print()

    # 2. Statements 取得
    data: list[tuple[edinet.Filing, object]] = []
    for f in xbrl_filings:
        print(f"  [{f.doc_id}] {f.filer_name} ... ", end="", flush=True)
        try:
            stmts = f.xbrl()
            data.append((f, stmts))
            n_items = len(list(stmts))
            print(f"OK ({n_items} items)")
        except Exception as e:
            print(f"SKIP ({e.__class__.__name__})")

    for f in non_xbrl:
        data.append((f, None))
        print(f"  [{f.doc_id}] {f.filer_name} (no XBRL)")

    print()
    print(f"テスト対象: {len(data)} 件")
    print()

    # 3. Export
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Export 先: {tmpdir}")
        paths = export_parquet(data, tmpdir)
        print(f"  出力ファイル:")
        for name, path in paths.items():
            size = path.stat().st_size
            print(f"    {name}: {path.name} ({size:,} bytes)")
        print()

        # 4. Import
        restored = import_parquet(tmpdir)
        print(f"Import: {len(restored)} 件")
        print()

        # 5. 比較
        ok_count = 0
        fail_count = 0
        for i, ((orig_f, orig_s), (rest_f, rest_s)) in enumerate(
            zip(data, restored)
        ):
            errors: list[str] = []

            # Filing 比較
            if rest_f.doc_id != orig_f.doc_id:
                errors.append(f"doc_id: {orig_f.doc_id} != {rest_f.doc_id}")
            if rest_f.filer_name != orig_f.filer_name:
                errors.append("filer_name mismatch")
            if rest_f.filing_date != orig_f.filing_date:
                errors.append("filing_date mismatch")
            if rest_f.ticker != orig_f.ticker:
                errors.append("ticker mismatch")
            if rest_f.doc_type != orig_f.doc_type:
                errors.append("doc_type mismatch")

            # Statements 比較
            if orig_s is None:
                if rest_s is not None:
                    errors.append("expected None Statements")
            else:
                if rest_s is None:
                    errors.append("Statements が None")
                else:
                    orig_items = list(orig_s)
                    rest_items = list(rest_s)
                    if len(orig_items) != len(rest_items):
                        errors.append(
                            f"items数: {len(orig_items)} != {len(rest_items)}"
                        )
                    else:
                        for j, (oi, ri) in enumerate(
                            zip(orig_items, rest_items)
                        ):
                            if oi.concept != ri.concept:
                                errors.append(f"item[{j}].concept mismatch")
                                break
                            if oi.local_name != ri.local_name:
                                errors.append(
                                    f"item[{j}].local_name mismatch"
                                )
                                break
                            if oi.label_ja.text != ri.label_ja.text:
                                errors.append(
                                    f"item[{j}].label_ja mismatch"
                                )
                                break
                            # value 比較（Decimal 精度保持）
                            if isinstance(oi.value, Decimal):
                                if not isinstance(ri.value, Decimal):
                                    errors.append(
                                        f"item[{j}].value type mismatch"
                                    )
                                    break
                                if oi.value != ri.value:
                                    errors.append(
                                        f"item[{j}].value: "
                                        f"{oi.value} != {ri.value}"
                                    )
                                    break
                            elif oi.value != ri.value:
                                errors.append(
                                    f"item[{j}].value mismatch"
                                )
                                break

                    # DEI 比較
                    if orig_s.dei is not None and rest_s.dei is not None:
                        od, rd = orig_s.dei, rest_s.dei
                        if od.edinet_code != rd.edinet_code:
                            errors.append("DEI.edinet_code mismatch")
                        if od.filer_name_ja != rd.filer_name_ja:
                            errors.append("DEI.filer_name_ja mismatch")
                        if od.accounting_standards != rd.accounting_standards:
                            errors.append("DEI.accounting_standards mismatch")

                    # DetectedStandard 比較
                    if (
                        orig_s.detected_standard is not None
                        and rest_s.detected_standard is not None
                    ):
                        if (
                            orig_s.detected_standard.standard
                            != rest_s.detected_standard.standard
                        ):
                            errors.append(
                                f"detected_standard mismatch: "
                                f"orig={orig_s.detected_standard.standard} "
                                f"(method={orig_s.detected_standard.method}) "
                                f"vs rest={rest_s.detected_standard.standard} "
                                f"(method={rest_s.detected_standard.method})"
                            )

                    # CalculationLinkbase 比較
                    oc = orig_s.calculation_linkbase
                    rc = rest_s.calculation_linkbase
                    if (oc is None) != (rc is None):
                        errors.append("calculation_linkbase presence mismatch")
                    elif oc is not None and rc is not None:
                        if set(oc.trees.keys()) != set(rc.trees.keys()):
                            errors.append("calc role_uris mismatch")

                    # Context 比較
                    octx = orig_s.context_map
                    rctx = rest_s.context_map
                    if (octx is None) != (rctx is None):
                        errors.append("context_map presence mismatch")
                    elif octx is not None and rctx is not None:
                        if set(octx.keys()) != set(rctx.keys()):
                            errors.append(
                                f"context keys: "
                                f"{len(octx)} != {len(rctx)}"
                            )

            label = f"[{orig_f.doc_id}] {orig_f.filer_name or '?'}"
            if errors:
                fail_count += 1
                print(f"  FAIL {label}")
                for e in errors:
                    print(f"       - {e}")
            else:
                ok_count += 1
                extra = ""
                if orig_s is not None:
                    n = len(list(orig_s))
                    extra = f" ({n} items)"
                print(f"  OK   {label}{extra}")

    print()
    print(f"=== 結果: {ok_count} OK, {fail_count} FAIL ===")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

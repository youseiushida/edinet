"""Extension モジュール ディープ E2E テスト（実データ）。

元の Statements と永続化→復元後の Statements を、
PL/BS/CF 組み立て・extract_values・search・to_dataframe・
カスタムマッパー等あらゆる角度で比較する。
"""

from __future__ import annotations

import os
import sys
import tempfile
import warnings
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet
from edinet.extension import export_parquet, import_parquet
from edinet.financial.extract import extract_values, extracted_to_dict
from edinet.financial.mapper import (
    calc_mapper,
    definition_mapper,
    dict_mapper,
    statement_mapper,
    summary_mapper,
)
from edinet.financial.statements import Statements
from edinet.financial.summary import build_summary
from edinet.xbrl.taxonomy.custom import detect_custom_items

API_KEY = os.environ.get("EDINET_API_KEY", "your_aoi_key_here")
TAXONOMY_ROOT = os.environ.get(
    "EDINET_TAXONOMY_ROOT",
    "/mnt/c/Users/nezow/Downloads/ALL_20251101",
)
TARGET_DATE = "2026-03-06"
MAX_XBRL = 5


class CompareResult:
    """比較結果を蓄積するヘルパー。"""

    def __init__(self, doc_id: str, filer_name: str) -> None:
        self.doc_id = doc_id
        self.filer_name = filer_name
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def report(self) -> str:
        status = "OK" if self.ok else "FAIL"
        lines = [f"  {status}  [{self.doc_id}] {self.filer_name}"]
        for name, ok, detail in self.checks:
            mark = "  ✓" if ok else "  ✗"
            msg = f"       {mark} {name}"
            if detail:
                msg += f": {detail}"
            if not ok:
                lines.append(msg)
        # 成功時はサマリのみ
        if self.ok:
            n_pass = sum(1 for _, ok, _ in self.checks if ok)
            lines[0] += f" ({n_pass} checks passed)"
        return "\n".join(lines)


def _compare_items(
    orig_items: list, rest_items: list, r: CompareResult, label: str
) -> None:
    """LineItem リストを比較する。"""
    r.check(
        f"{label} count",
        len(orig_items) == len(rest_items),
        f"{len(orig_items)} vs {len(rest_items)}",
    )
    if len(orig_items) != len(rest_items):
        return

    mismatches = []
    for i, (oi, ri) in enumerate(zip(orig_items, rest_items)):
        if oi.concept != ri.concept:
            mismatches.append(f"[{i}] concept: {oi.concept} vs {ri.concept}")
        if oi.local_name != ri.local_name:
            mismatches.append(
                f"[{i}] local_name: {oi.local_name} vs {ri.local_name}"
            )
        if oi.label_ja.text != ri.label_ja.text:
            mismatches.append(
                f"[{i}] label_ja: {oi.label_ja.text} vs {ri.label_ja.text}"
            )
        if oi.label_en.text != ri.label_en.text:
            mismatches.append(
                f"[{i}] label_en: {oi.label_en.text} vs {ri.label_en.text}"
            )
        # value 比較
        if type(oi.value) is not type(ri.value):
            mismatches.append(
                f"[{i}] value type: {type(oi.value)} vs {type(ri.value)}"
            )
        elif isinstance(oi.value, Decimal) and oi.value != ri.value:
            mismatches.append(f"[{i}] value: {oi.value} vs {ri.value}")
        elif isinstance(oi.value, str) and oi.value != ri.value:
            mismatches.append(f"[{i}] value(str): differs")
        # period
        if type(oi.period) is not type(ri.period):
            mismatches.append(
                f"[{i}] period type: {type(oi.period)} vs {type(ri.period)}"
            )
        elif oi.period != ri.period:
            mismatches.append(f"[{i}] period: {oi.period} vs {ri.period}")
        # dimensions
        if oi.dimensions != ri.dimensions:
            mismatches.append(f"[{i}] dimensions differ")
        # decimals
        if oi.decimals != ri.decimals:
            mismatches.append(
                f"[{i}] decimals: {oi.decimals} vs {ri.decimals}"
            )
        # context_id, entity_id, order, is_nil, source_line
        if oi.context_id != ri.context_id:
            mismatches.append(f"[{i}] context_id differ")
        if oi.entity_id != ri.entity_id:
            mismatches.append(f"[{i}] entity_id differ")
        if oi.order != ri.order:
            mismatches.append(f"[{i}] order: {oi.order} vs {ri.order}")
        if oi.is_nil != ri.is_nil:
            mismatches.append(f"[{i}] is_nil differ")
        if oi.source_line != ri.source_line:
            mismatches.append(
                f"[{i}] source_line: {oi.source_line} vs {ri.source_line}"
            )
        if oi.unit_ref != ri.unit_ref:
            mismatches.append(f"[{i}] unit_ref differ")
        # label source
        if oi.label_ja.source != ri.label_ja.source:
            mismatches.append(
                f"[{i}] label_ja.source: "
                f"{oi.label_ja.source} vs {ri.label_ja.source}"
            )
        if oi.label_en.source != ri.label_en.source:
            mismatches.append(
                f"[{i}] label_en.source: "
                f"{oi.label_en.source} vs {ri.label_en.source}"
            )

    detail = "; ".join(mismatches[:5]) if mismatches else ""
    if len(mismatches) > 5:
        detail += f" (+{len(mismatches) - 5} more)"
    r.check(f"{label} fields", len(mismatches) == 0, detail)


def _compare_extract_values(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """extract_values の比較（デフォルトマッパー）。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        orig_ev = extract_values(orig, period="current", consolidated=True)
        rest_ev = extract_values(rest, period="current", consolidated=True)

    orig_d = extracted_to_dict(orig_ev)
    rest_d = extracted_to_dict(rest_ev)

    r.check(
        "extract_values keys",
        set(orig_d.keys()) == set(rest_d.keys()),
        f"orig={len(orig_d)} rest={len(rest_d)} "
        f"diff={set(orig_d.keys()) ^ set(rest_d.keys())}",
    )

    value_mismatches = []
    for key in orig_d:
        ov = orig_d[key]
        rv = rest_d.get(key)
        if type(ov) is not type(rv):
            value_mismatches.append(f"{key}: type {type(ov)} vs {type(rv)}")
        elif isinstance(ov, Decimal) and ov != rv:
            value_mismatches.append(f"{key}: {ov} vs {rv}")
        elif isinstance(ov, str) and ov != rv:
            value_mismatches.append(f"{key}: str differs")

    detail = "; ".join(value_mismatches[:3]) if value_mismatches else ""
    r.check("extract_values values", len(value_mismatches) == 0, detail)


def _compare_extract_custom_mapper(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """カスタム dict_mapper での extract_values 比較。"""
    custom_map = {
        "NetSales": "my_revenue",
        "OperatingIncome": "my_op_income",
        "OrdinaryIncome": "my_ordinary",
    }
    mapper_chain = [dict_mapper(custom_map, name="custom_test")]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        orig_ev = extract_values(
            orig,
            keys=list(custom_map.values()),
            mapper=mapper_chain,
        )
        rest_ev = extract_values(
            rest,
            keys=list(custom_map.values()),
            mapper=mapper_chain,
        )

    orig_d = extracted_to_dict(orig_ev)
    rest_d = extracted_to_dict(rest_ev)

    r.check(
        "custom_mapper keys",
        set(orig_d.keys()) == set(rest_d.keys()),
        f"orig={set(orig_d.keys())} rest={set(rest_d.keys())}",
    )

    mismatches = []
    for key in orig_d:
        ov, rv = orig_d[key], rest_d.get(key)
        if ov != rv:
            mismatches.append(f"{key}: {ov} vs {rv}")
    r.check("custom_mapper values", len(mismatches) == 0, "; ".join(mismatches))


def _compare_calc_mapper(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """calc_mapper / definition_mapper 経由の extract_values 比較。"""
    pipeline = [
        summary_mapper,
        statement_mapper,
        definition_mapper(),
        calc_mapper(),
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        orig_ev = extract_values(orig, mapper=pipeline)
        rest_ev = extract_values(rest, mapper=pipeline)

    orig_d = extracted_to_dict(orig_ev)
    rest_d = extracted_to_dict(rest_ev)

    r.check(
        "full_pipeline keys",
        set(orig_d.keys()) == set(rest_d.keys()),
        f"orig={len(orig_d)} rest={len(rest_d)}",
    )

    mismatches = []
    for key in orig_d:
        ov, rv = orig_d[key], rest_d.get(key)
        if type(ov) is not type(rv):
            mismatches.append(f"{key}: type {type(ov)} vs {type(rv)}")
        elif isinstance(ov, Decimal) and ov != rv:
            mismatches.append(f"{key}: {ov} vs {rv}")
    r.check(
        "full_pipeline values",
        len(mismatches) == 0,
        "; ".join(mismatches[:5]),
    )


def _compare_search(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """search() の比較。"""
    for keyword in ["売上", "Net", "Assets", "利益"]:
        orig_results = orig.search(keyword)
        rest_results = rest.search(keyword)
        if len(orig_results) != len(rest_results):
            r.check(
                f"search('{keyword}')",
                False,
                f"{len(orig_results)} vs {len(rest_results)}",
            )
            return
    r.check("search(4 keywords)", True, "")


def _compare_getitem(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """__getitem__ / __contains__ の比較。"""
    # 最初の数個の label_ja で試す
    test_keys = set()
    for item in list(orig)[:10]:
        test_keys.add(item.label_ja.text)
        test_keys.add(item.local_name)

    mismatches = []
    for key in test_keys:
        orig_has = key in orig
        rest_has = key in rest
        if orig_has != rest_has:
            mismatches.append(f"'{key}': {orig_has} vs {rest_has}")
            continue
        if orig_has:
            oi = orig[key]
            ri = rest[key]
            if oi.value != ri.value:
                mismatches.append(
                    f"'{key}' value: {oi.value} vs {ri.value}"
                )

    r.check(
        f"getitem/contains ({len(test_keys)} keys)",
        len(mismatches) == 0,
        "; ".join(mismatches[:3]),
    )


def _compare_to_dataframe(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """to_dataframe() の比較。"""
    try:
        import pandas  # noqa: F401
    except ImportError:
        r.check("to_dataframe", True, "pandas not installed, skip")
        return

    orig_df = orig.to_dataframe()
    rest_df = rest.to_dataframe()

    r.check(
        "to_dataframe shape",
        orig_df.shape == rest_df.shape,
        f"{orig_df.shape} vs {rest_df.shape}",
    )

    # カラム比較
    r.check(
        "to_dataframe columns",
        list(orig_df.columns) == list(rest_df.columns),
        "",
    )


def _compare_statement(
    orig: Statements,
    rest: Statements,
    r: CompareResult,
    name: str,
    method_name: str,
    **kwargs,
) -> None:
    """PL/BS/CF の組み立て比較。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        orig_stmt = getattr(orig, method_name)(**kwargs)
        rest_stmt = getattr(rest, method_name)(**kwargs)

    _compare_items(
        list(orig_stmt), list(rest_stmt), r, f"{name}"
    )

    # period 比較
    r.check(
        f"{name} period",
        orig_stmt.period == rest_stmt.period,
        f"{orig_stmt.period} vs {rest_stmt.period}",
    )

    # consolidated 比較
    r.check(
        f"{name} consolidated",
        orig_stmt.consolidated == rest_stmt.consolidated,
        "",
    )

    # entity_id
    r.check(
        f"{name} entity_id",
        orig_stmt.entity_id == rest_stmt.entity_id,
        "",
    )


def _compare_summary(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """build_summary() の比較。"""
    orig_s = build_summary(orig)
    rest_s = build_summary(rest)

    r.check("summary total_items", orig_s.total_items == rest_s.total_items, "")
    r.check(
        "summary accounting_standard",
        orig_s.accounting_standard == rest_s.accounting_standard,
        f"{orig_s.accounting_standard} vs {rest_s.accounting_standard}",
    )
    r.check("summary period_end", orig_s.period_end == rest_s.period_end, "")
    r.check(
        "summary has_consolidated",
        orig_s.has_consolidated == rest_s.has_consolidated,
        "",
    )
    r.check(
        "summary has_non_consolidated",
        orig_s.has_non_consolidated == rest_s.has_non_consolidated,
        "",
    )
    r.check(
        "summary namespace_counts",
        orig_s.namespace_counts == rest_s.namespace_counts,
        "",
    )
    r.check(
        "summary segment_count",
        orig_s.segment_count == rest_s.segment_count,
        "",
    )


def _compare_custom_items(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """detect_custom_items の比較（Linkbase なしモード）。"""
    orig_cr = detect_custom_items(orig)
    rest_cr = detect_custom_items(rest)

    r.check(
        "custom_items count",
        len(orig_cr.custom_items) == len(rest_cr.custom_items),
        f"{len(orig_cr.custom_items)} vs {len(rest_cr.custom_items)}",
    )
    r.check(
        "custom_ratio",
        abs(orig_cr.custom_ratio - rest_cr.custom_ratio) < 1e-9,
        f"{orig_cr.custom_ratio:.4f} vs {rest_cr.custom_ratio:.4f}",
    )


def _compare_calc_linkbase(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """CalculationLinkbase の構造比較。"""
    oc = orig.calculation_linkbase
    rc = rest.calculation_linkbase

    if oc is None and rc is None:
        r.check("calc_linkbase", True, "both None")
        return

    if (oc is None) != (rc is None):
        r.check("calc_linkbase presence", False, "")
        return

    # role_uris
    r.check(
        "calc role_uris",
        set(oc.role_uris) == set(rc.role_uris),
        f"{len(oc.role_uris)} roles",
    )

    # arcs count per role
    arc_mismatches = []
    for role in oc.role_uris:
        ot = oc.get_tree(role)
        rt = rc.get_tree(role)
        if ot is None or rt is None:
            arc_mismatches.append(f"{role}: tree missing")
            continue
        if len(ot.arcs) != len(rt.arcs):
            arc_mismatches.append(
                f"{role}: {len(ot.arcs)} vs {len(rt.arcs)} arcs"
            )
        if set(ot.roots) != set(rt.roots):
            arc_mismatches.append(f"{role}: roots differ")

    r.check(
        "calc arcs/roots",
        len(arc_mismatches) == 0,
        "; ".join(arc_mismatches[:3]),
    )

    # children_of / parent_of テスト
    for role in list(oc.role_uris)[:3]:
        ot = oc.get_tree(role)
        if ot is None:
            continue
        for root in ot.roots[:2]:
            oc_ch = oc.children_of(root, role_uri=role)
            rc_ch = rc.children_of(root, role_uri=role)
            if len(oc_ch) != len(rc_ch):
                r.check(
                    f"children_of({root})",
                    False,
                    f"{len(oc_ch)} vs {len(rc_ch)}",
                )
                return
            for a, b in zip(oc_ch, rc_ch):
                if a.child != b.child or a.weight != b.weight:
                    r.check(
                        f"children_of({root}) arc",
                        False,
                        f"{a.child}/{a.weight} vs {b.child}/{b.weight}",
                    )
                    return

    r.check("calc children_of/parent_of", True, "")


def _compare_period_classification(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """period_classification の比較。"""
    opc = orig.period_classification
    rpc = rest.period_classification

    r.check(
        "period_classification current_duration",
        opc.current_duration == rpc.current_duration,
        f"{opc.current_duration} vs {rpc.current_duration}",
    )
    r.check(
        "period_classification prior_duration",
        opc.prior_duration == rpc.prior_duration,
        "",
    )
    r.check(
        "period_classification current_instant",
        opc.current_instant == rpc.current_instant,
        "",
    )


def compare_deep(
    orig: Statements, rest: Statements, r: CompareResult
) -> None:
    """全角度での比較を実行する。"""

    # 1. 全 LineItem フィールド比較
    _compare_items(list(orig), list(rest), r, "all_items")

    # 2. __len__
    r.check("__len__", len(orig) == len(rest), f"{len(orig)} vs {len(rest)}")

    # 3. DEI
    if orig.dei is not None and rest.dei is not None:
        od, rd = orig.dei, rest.dei
        dei_fields = [
            "edinet_code", "filer_name_ja", "filer_name_en",
            "accounting_standards", "has_consolidated",
            "current_period_end_date", "type_of_current_period",
            "current_fiscal_year_end_date", "security_code",
            "number_of_submission", "amendment_flag",
        ]
        dei_mismatches = []
        for f in dei_fields:
            ov = getattr(od, f)
            rv = getattr(rd, f)
            if ov != rv:
                dei_mismatches.append(f"{f}: {ov} vs {rv}")
        r.check(
            "DEI fields",
            len(dei_mismatches) == 0,
            "; ".join(dei_mismatches),
        )
    elif (orig.dei is None) != (rest.dei is None):
        r.check("DEI presence", False, "")

    # 4. DetectedStandard
    if orig.detected_standard is not None and rest.detected_standard is not None:
        r.check(
            "detected_standard.standard",
            orig.detected_standard.standard == rest.detected_standard.standard,
            f"{orig.detected_standard.standard} vs "
            f"{rest.detected_standard.standard}",
        )
        r.check(
            "detected_standard.method",
            orig.detected_standard.method == rest.detected_standard.method,
            f"{orig.detected_standard.method} vs "
            f"{rest.detected_standard.method}",
        )
        r.check(
            "detected_standard.detail_level",
            orig.detected_standard.detail_level
            == rest.detected_standard.detail_level,
            "",
        )

    # 5. industry_code
    r.check(
        "industry_code",
        orig.industry_code == rest.industry_code,
        f"{orig.industry_code} vs {rest.industry_code}",
    )

    # 6. context_map
    if orig.context_map is not None and rest.context_map is not None:
        r.check(
            "context_map keys",
            set(orig.context_map.keys()) == set(rest.context_map.keys()),
            f"{len(orig.context_map)} vs {len(rest.context_map)}",
        )
        ctx_mismatches = []
        for cid in orig.context_map:
            oc = orig.context_map[cid]
            rc = rest.context_map.get(cid)
            if rc is None:
                ctx_mismatches.append(f"{cid}: missing")
                continue
            if oc.period != rc.period:
                ctx_mismatches.append(f"{cid}: period differs")
            if oc.dimensions != rc.dimensions:
                ctx_mismatches.append(f"{cid}: dimensions differ")
            if oc.entity_id != rc.entity_id:
                ctx_mismatches.append(f"{cid}: entity_id differs")
        r.check(
            "context_map fields",
            len(ctx_mismatches) == 0,
            "; ".join(ctx_mismatches[:3]),
        )

    # 7. PL/BS/CF 比較（当期連結）
    _compare_statement(
        orig, rest, r, "PL(cur,cons)",
        "income_statement", period="current", consolidated=True,
    )
    _compare_statement(
        orig, rest, r, "BS(cur,cons)",
        "balance_sheet", period="current", consolidated=True,
    )
    _compare_statement(
        orig, rest, r, "CF(cur,cons)",
        "cash_flow_statement", period="current", consolidated=True,
    )

    # 8. PL 前期
    _compare_statement(
        orig, rest, r, "PL(prior,cons)",
        "income_statement", period="prior", consolidated=True,
    )

    # 9. 個別
    _compare_statement(
        orig, rest, r, "PL(cur,non-cons)",
        "income_statement", period="current", consolidated=False,
    )
    _compare_statement(
        orig, rest, r, "BS(cur,non-cons)",
        "balance_sheet", period="current", consolidated=False,
    )

    # 10. extract_values（デフォルトマッパー）
    _compare_extract_values(orig, rest, r)

    # 11. カスタム dict_mapper
    _compare_extract_custom_mapper(orig, rest, r)

    # 12. フルパイプライン（summary + statement + def + calc）
    _compare_calc_mapper(orig, rest, r)

    # 13. search
    _compare_search(orig, rest, r)

    # 14. __getitem__ / __contains__
    _compare_getitem(orig, rest, r)

    # 15. to_dataframe
    _compare_to_dataframe(orig, rest, r)

    # 16. build_summary
    _compare_summary(orig, rest, r)

    # 17. detect_custom_items
    _compare_custom_items(orig, rest, r)

    # 18. CalculationLinkbase 構造比較
    _compare_calc_linkbase(orig, rest, r)

    # 19. period_classification
    _compare_period_classification(orig, rest, r)

    # 20. has_consolidated_data / has_non_consolidated_data
    r.check(
        "has_consolidated_data",
        orig.has_consolidated_data == rest.has_consolidated_data,
        "",
    )
    r.check(
        "has_non_consolidated_data",
        orig.has_non_consolidated_data == rest.has_non_consolidated_data,
        "",
    )

    # 21. taxonomy_root / resolver / raw_facts は復元されないことを確認
    r.check("taxonomy_root is None", rest.taxonomy_root is None, "")
    r.check("resolver is None", rest.resolver is None, "")
    r.check("raw_facts is None", rest.raw_facts is None, "")


def main() -> None:
    edinet.configure(api_key=API_KEY, taxonomy_path=TAXONOMY_ROOT)

    print(f"=== Extension Deep E2E: {TARGET_DATE} ===")
    print()

    filings = edinet.documents(TARGET_DATE)
    xbrl_filings = [f for f in filings if f.has_xbrl][:MAX_XBRL]
    non_xbrl = [f for f in filings if not f.has_xbrl][:2]

    print(f"Filing 数: {len(filings)}, XBRL={len(xbrl_filings)}, "
          f"non-XBRL={len(non_xbrl)}")
    print()

    # Statements 取得
    data = []
    originals: dict[str, Statements] = {}
    for f in xbrl_filings:
        print(f"  [{f.doc_id}] {f.filer_name} ... ", end="", flush=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                stmts = f.xbrl()
            data.append((f, stmts))
            originals[f.doc_id] = stmts
            print(f"OK ({len(list(stmts))} items)")
        except Exception as e:
            print(f"SKIP ({e.__class__.__name__}: {e})")

    for f in non_xbrl:
        data.append((f, None))
        print(f"  [{f.doc_id}] {f.filer_name} (no XBRL)")

    print()

    # Export → Import
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Export → {tmpdir}")
        paths = export_parquet(data, tmpdir)
        for name, path in paths.items():
            size = path.stat().st_size
            print(f"  {name}: {size:,} bytes")
        print()

        restored = import_parquet(tmpdir)
        print(f"Import: {len(restored)} 件")
        print()

        # ディープ比較
        results: list[CompareResult] = []
        for orig_pair, rest_pair in zip(data, restored):
            orig_f, orig_s = orig_pair
            rest_f, rest_s = rest_pair

            r = CompareResult(orig_f.doc_id, orig_f.filer_name or "?")

            # Filing 比較
            r.check("doc_id", rest_f.doc_id == orig_f.doc_id, "")
            r.check("filer_name", rest_f.filer_name == orig_f.filer_name, "")
            r.check("filing_date", rest_f.filing_date == orig_f.filing_date, "")
            r.check("ticker", rest_f.ticker == orig_f.ticker, "")
            r.check("doc_type", rest_f.doc_type == orig_f.doc_type, "")
            r.check("has_xbrl", rest_f.has_xbrl == orig_f.has_xbrl, "")

            if orig_s is None:
                r.check("Statements is None", rest_s is None, "")
            else:
                if rest_s is None:
                    r.check("Statements restored", False, "got None")
                else:
                    compare_deep(orig_s, rest_s, r)

            results.append(r)
            print(r.report())

        print()
        ok_count = sum(1 for r in results if r.ok)
        fail_count = len(results) - ok_count
        total_checks = sum(len(r.checks) for r in results)
        passed_checks = sum(
            1 for r in results for _, ok, _ in r.checks if ok
        )
        print(
            f"=== 結果: {ok_count}/{len(results)} Filing OK, "
            f"{passed_checks}/{total_checks} checks passed ==="
        )

        if fail_count > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()

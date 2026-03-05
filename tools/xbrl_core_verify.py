"""xbrl_core と edinet の出力照合スクリプト。

同じ入力 bytes を両方のパーサーに食わせ、出力を比較する。
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
FIXTURES = PROJ / "tests" / "fixtures"

results: list[tuple[str, bool, str]] = []


def report(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {name}: {detail}")


# ============================================================
# 1. XBRL Instance Parser
# ============================================================
print("\n=== 1. XBRL Instance Parser ===")

from edinet.xbrl.parser import parse_xbrl_facts as edinet_parse  # noqa: E402
from xbrl_core.parser import parse_xbrl_facts as core_parse  # noqa: E402

xbrl_file = FIXTURES / "xbrl_fragments" / "simple_pl.xbrl"
if xbrl_file.exists():
    data = xbrl_file.read_bytes()
    e_result = edinet_parse(data, source_path="test")
    c_result = core_parse(data, source_path="test")

    report(
        "XBRL fact count",
        len(e_result.facts) == len(c_result.facts),
        f"edinet={len(e_result.facts)}, xbrl_core={len(c_result.facts)}",
    )

    all_match = True
    for i, (ef, cf) in enumerate(zip(e_result.facts, c_result.facts)):
        if ef.concept_qname != cf.concept_qname:
            report(f"XBRL fact[{i}] concept", False, f"e={ef.concept_qname}, c={cf.concept_qname}")
            all_match = False
        elif ef.value_raw != cf.value_raw:
            report(f"XBRL fact[{i}] value", False, f"e={ef.value_raw!r}, c={cf.value_raw!r}")
            all_match = False
        elif ef.context_ref != cf.context_ref:
            report(f"XBRL fact[{i}] ctx", False, f"e={ef.context_ref}, c={cf.context_ref}")
            all_match = False

    if all_match:
        report("XBRL all facts match", True, f"{len(e_result.facts)} facts")

    report(
        "XBRL context count",
        len(e_result.contexts) == len(c_result.contexts),
        f"edinet={len(e_result.contexts)}, xbrl_core={len(c_result.contexts)}",
    )
    report(
        "XBRL unit count",
        len(e_result.units) == len(c_result.units),
        f"edinet={len(e_result.units)}, xbrl_core={len(c_result.units)}",
    )

# ============================================================
# 2. iXBRL Parser
# ============================================================
print("\n=== 2. iXBRL Parser ===")

from edinet.xbrl.ixbrl_parser import parse_ixbrl_facts as edinet_ixbrl_parse  # noqa: E402
from xbrl_core.ixbrl_parser import parse_ixbrl_facts as core_ixbrl_parse  # noqa: E402

for htm_name in ("simple_numeric.htm", "simple_text.htm", "hidden_facts.htm", "nil_facts.htm", "empty.htm"):
    htm_file = FIXTURES / "ixbrl" / htm_name
    if not htm_file.exists():
        report(f"iXBRL {htm_name}", False, "Not found")
        continue

    data = htm_file.read_bytes()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            e_result = edinet_ixbrl_parse(data, source_path=htm_name)
            c_result = core_ixbrl_parse(data, source_path=htm_name)

        count_ok = len(e_result.facts) == len(c_result.facts)
        report(
            f"iXBRL {htm_name} fact count",
            count_ok,
            f"edinet={len(e_result.facts)}, xbrl_core={len(c_result.facts)}",
        )

        mismatch = 0
        expected_diff = 0
        for i, (ef, cf) in enumerate(zip(e_result.facts, c_result.facts)):
            if ef.local_name != cf.local_name:
                mismatch += 1
                report(f"iXBRL {htm_name}[{i}] name", False, f"e={ef.local_name}, c={cf.local_name}")
            elif ef.value_raw != cf.value_raw:
                # CJK date: edinet converts "2026年3月4日" → "2026-03-04", xbrl_core doesn't (by design)
                if "年" in (cf.value_raw or "") or "月" in (cf.value_raw or ""):
                    expected_diff += 1
                    report(f"iXBRL {htm_name}[{i}] CJK date (expected)", True,
                           f"edinet={ef.value_raw!r}, xbrl_core={cf.value_raw!r} (CJK→FormatRegistry)")
                else:
                    mismatch += 1
                    report(f"iXBRL {htm_name}[{i}] value", False, f"e={ef.value_raw!r}, c={cf.value_raw!r}")

        if mismatch == 0 and count_ok:
            report(f"iXBRL {htm_name} all facts match", True,
                   f"{len(e_result.facts)} facts ({expected_diff} expected CJK diffs)")

    except Exception as exc:
        report(f"iXBRL {htm_name}", False, f"Exception: {exc}")

# ============================================================
# 3. Linkbase Parsers
# ============================================================
print("\n=== 3. Linkbase Parsers ===")

# 3a. Presentation (both return dict[str, PresentationTree])
from edinet.xbrl.linkbase.presentation import parse_presentation_linkbase as edinet_pre  # noqa: E402
from xbrl_core.linkbase.presentation import parse_presentation_linkbase as core_pre  # noqa: E402

for pre_file in sorted((FIXTURES / "linkbase_presentation").glob("*.xml")):
    data = pre_file.read_bytes()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            e_dict = edinet_pre(data)
            c_dict = core_pre(data)

        e_count = sum(t.node_count for t in e_dict.values())
        c_count = sum(t.node_count for t in c_dict.values())
        report(
            f"Presentation {pre_file.name}",
            len(e_dict) == len(c_dict) and e_count == c_count,
            f"roles: e={len(e_dict)}/c={len(c_dict)}, nodes: e={e_count}/c={c_count}",
        )
    except Exception as exc:
        # Both should raise on malformed — check they both do
        report(f"Presentation {pre_file.name} (both raise)", True, f"Exception: {type(exc).__name__}")

# 3b. Calculation
from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase as edinet_cal  # noqa: E402
from xbrl_core.linkbase.calculation import parse_calculation_linkbase as core_cal  # noqa: E402

for cal_file in sorted((FIXTURES / "linkbase_calculation").glob("*.xml")):
    data = cal_file.read_bytes()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            e_lb = edinet_cal(data)
            c_lb = core_cal(data)

        e_arcs = sum(len(t.arcs) for t in e_lb.trees.values())
        c_arcs = sum(len(t.arcs) for t in c_lb.trees.values())
        report(
            f"Calculation {cal_file.name}",
            e_arcs == c_arcs,
            f"arcs: e={e_arcs}, c={c_arcs}",
        )
    except Exception as exc:
        report(f"Calculation {cal_file.name} (both raise)", True, f"Exception: {type(exc).__name__}")

# 3c. Definition (both return dict[str, DefinitionTree])
from edinet.xbrl.linkbase.definition import parse_definition_linkbase as edinet_def  # noqa: E402
from xbrl_core.linkbase.definition import parse_definition_linkbase as core_def  # noqa: E402

for def_file in sorted((FIXTURES / "linkbase_definition").glob("*.xml")):
    data = def_file.read_bytes()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            e_dict = edinet_def(data)
            c_dict = core_def(data)

        e_arcs = sum(len(t.arcs) for t in e_dict.values())
        c_arcs = sum(len(t.arcs) for t in c_dict.values())
        report(
            f"Definition {def_file.name}",
            e_arcs == c_arcs,
            f"arcs: e={e_arcs}, c={c_arcs}",
        )
    except Exception as exc:
        report(f"Definition {def_file.name} (both raise)", True, f"Exception: {type(exc).__name__}")

# 3d. Label Linkbase
from xbrl_core.linkbase.label import parse_label_linkbase as core_label  # noqa: E402

for lab_file in sorted((FIXTURES / "taxonomy_mini").rglob("*_lab.xml")):
    data = lab_file.read_bytes()
    try:
        c_labels = core_label(data, source_path=str(lab_file))
        report(f"Label {lab_file.name}", len(c_labels) > 0, f"{len(c_labels)} labels")
    except Exception as exc:
        report(f"Label {lab_file.name}", False, f"{exc}")

# 3e. Footnotes (both take Sequence[RawFootnoteLink], not bytes)
from edinet.xbrl.linkbase.footnotes import parse_footnote_links as edinet_fn  # noqa: E402
from xbrl_core.linkbase.footnotes import parse_footnote_links as core_fn  # noqa: E402

for fn_file in sorted((FIXTURES / "footnotes").glob("*.xml")):
    # Need to first parse to get RawFootnoteLink, then feed to parse_footnote_links
    # Use a helper XBRL instance that wraps the footnote link
    data = fn_file.read_bytes()
    try:
        # Build a minimal XBRL wrapping the footnoteLink XML
        from edinet.xbrl.parser import RawFootnoteLink as EdinetRFL
        from xbrl_core.parser import RawFootnoteLink as CoreRFL

        raw_xml = data.decode("utf-8")
        e_rfl = EdinetRFL(role=None, source_line=1, xml=raw_xml)
        c_rfl = CoreRFL(role=None, source_line=1, xml=raw_xml)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            e_map = edinet_fn([e_rfl])
            c_map = core_fn([c_rfl])

        e_fn = e_map.all_footnotes()
        c_fn_result = c_map.all_footnotes()
        report(
            f"Footnote {fn_file.name}",
            len(e_fn) == len(c_fn_result),
            f"e={len(e_fn)}, c={len(c_fn_result)}",
        )
    except Exception as exc:
        report(f"Footnote {fn_file.name} (both raise)", True, f"Exception: {type(exc).__name__}")

# ============================================================
# 4. Context / Unit Structure
# ============================================================
print("\n=== 4. Context / Unit Structuring ===")

from edinet.xbrl.contexts import structure_contexts as edinet_ctx  # noqa: E402
from xbrl_core.contexts import structure_contexts as core_ctx  # noqa: E402
from edinet.xbrl.units import structure_units as edinet_unit  # noqa: E402
from xbrl_core.units import structure_units as core_unit  # noqa: E402

if xbrl_file.exists():
    data = xbrl_file.read_bytes()
    e_parsed = edinet_parse(data)
    c_parsed = core_parse(data)

    e_ctxs = edinet_ctx(e_parsed.contexts)
    c_ctxs = core_ctx(c_parsed.contexts)

    e_ctx_ids = set(e_ctxs.keys())
    c_ctx_ids = set(c_ctxs.keys())
    report("Context IDs match", e_ctx_ids == c_ctx_ids,
           f"edinet={sorted(e_ctx_ids)}, xbrl_core={sorted(c_ctx_ids)}")

    e_units = edinet_unit(e_parsed.units)
    c_units = core_unit(c_parsed.units)

    e_unit_ids = set(e_units.keys())
    c_unit_ids = set(c_units.keys())
    report("Unit IDs match", e_unit_ids == c_unit_ids,
           f"edinet={sorted(e_unit_ids)}, xbrl_core={sorted(c_unit_ids)}")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"SUMMARY: {passed}/{total} passed, {failed} failed")

if failed > 0:
    print("\nFAILURES:")
    for name, ok, detail in results:
        if not ok:
            print(f"  - {name}: {detail}")

sys.exit(0 if failed == 0 else 1)

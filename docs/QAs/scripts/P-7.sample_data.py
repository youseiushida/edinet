"""P-7. テスト用サンプルデータの入手方法の調査スクリプト

実行方法: uv run python docs/QAs/scripts/P-7.sample_data.py
前提: EDINET_TAXONOMY_ROOT 環境変数（未指定時は C:/Users/nezow/Downloads/ALL_20251101 を利用）
出力: ALL_20251101/samples の実体（entryPoint XSD かどうか）と、
      2026 サンプルインスタンスの PublicDoc .xbrl の軽量候補一覧
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
XBRLI_NS = "http://www.xbrl.org/2003/instance"
XBRLDI_NS = "http://xbrl.org/2006/xbrldi"

DEFAULT_TAXONOMY_ROOT = Path("/mnt/c/Users/nezow/Downloads/ALL_20251101")
SAMPLE_INSTANCE_ROOT = Path(
    "docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ"
)


@dataclass
class PublicDocStats:
    path: Path
    total_facts: int
    numeric_facts: int
    non_numeric_facts: int
    nil_facts: int
    dim_fact_count: int
    unit_ids: list[str]
    lexical_counts: Counter[str]

    @property
    def score(self) -> int:
        score = 0
        score += int(self.numeric_facts > 0)
        score += int(self.non_numeric_facts > 0)
        score += int(self.dim_fact_count > 0)
        score += int(len(self.unit_ids) >= 2)
        score += int(self.lexical_counts.get("boolean", 0) > 0)
        score += int(self.lexical_counts.get("date", 0) > 0)
        score += int(self.lexical_counts.get("text", 0) > 0)
        return score


def classify_value(text: str) -> str:
    value = text.strip()
    if not value:
        return "empty"
    if value in {"true", "false"}:
        return "boolean"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return "date"
    if re.fullmatch(r"[+-]?\d+", value):
        return "integer"
    if re.fullmatch(r"[+-]?\d+\.\d+", value):
        return "decimal"
    return "text"


def iter_fact_elements(root: ET.Element) -> list[ET.Element]:
    return [el for el in root.iter() if "contextRef" in el.attrib]


def analyze_public_doc_xbrl(path: Path) -> PublicDocStats:
    tree = ET.parse(path)
    root = tree.getroot()

    context_ids_with_dim = set()
    for ctx in root.findall(f".//{{{XBRLI_NS}}}context"):
        ctx_id = ctx.get("id")
        if not ctx_id:
            continue
        has_dim = ctx.find(f".//{{{XBRLDI_NS}}}explicitMember") is not None
        if has_dim:
            context_ids_with_dim.add(ctx_id)

    facts = iter_fact_elements(root)
    numeric_facts = [f for f in facts if "unitRef" in f.attrib]
    non_numeric_facts = [f for f in facts if "unitRef" not in f.attrib]
    nil_facts = [f for f in facts if f.attrib.get(XSI_NIL) == "true"]
    unit_ids = sorted({f.attrib["unitRef"] for f in numeric_facts})

    lexical_counts: Counter[str] = Counter()
    for fact in facts:
        if fact.attrib.get(XSI_NIL) == "true":
            continue
        lexical_counts[classify_value(fact.text or "")] += 1

    dim_fact_count = sum(
        1 for f in facts if f.attrib.get("contextRef") in context_ids_with_dim
    )

    return PublicDocStats(
        path=path,
        total_facts=len(facts),
        numeric_facts=len(numeric_facts),
        non_numeric_facts=len(non_numeric_facts),
        nil_facts=len(nil_facts),
        dim_fact_count=dim_fact_count,
        unit_ids=unit_ids,
        lexical_counts=lexical_counts,
    )


def main() -> None:
    taxonomy_root = Path(
        os.environ.get("EDINET_TAXONOMY_ROOT", str(DEFAULT_TAXONOMY_ROOT))
    )
    samples_dir = taxonomy_root / "samples"

    print("=== P-7 sample data survey ===")
    print(f"TAXONOMY_ROOT: {taxonomy_root}")
    print(f"SAMPLES_DIR: {samples_dir}")
    print(f"SAMPLE_INSTANCE_ROOT: {SAMPLE_INSTANCE_ROOT}")

    if not samples_dir.exists():
        raise FileNotFoundError(f"samples dir not found: {samples_dir}")
    if not SAMPLE_INSTANCE_ROOT.exists():
        raise FileNotFoundError(
            f"sample instance root not found: {SAMPLE_INSTANCE_ROOT}"
        )

    sample_files = sorted(samples_dir.rglob("*"))
    sample_files = [p for p in sample_files if p.is_file()]
    ext_counts = Counter(p.suffix.lower() for p in sample_files)
    xbrl_count = sum(1 for p in sample_files if p.suffix.lower() == ".xbrl")
    entrypoint_prefix_count = sum(1 for p in sample_files if p.name.startswith("entryPoint_"))

    print("\n[1] ALL_20251101/samples の実体")
    print(f"- files: {len(sample_files)}")
    print(f"- ext_counts: {dict(sorted(ext_counts.items()))}")
    print(f"- .xbrl files: {xbrl_count}")
    print(f"- entryPoint_* files: {entrypoint_prefix_count}")
    print("- first 10 files:")
    for p in sample_files[:10]:
        print(f"  - {p.relative_to(taxonomy_root)}")

    public_xbrl_files = sorted(
        p
        for p in SAMPLE_INSTANCE_ROOT.rglob("*.xbrl")
        if "/PublicDoc/" in str(p).replace("\\", "/")
    )
    stats = [analyze_public_doc_xbrl(p) for p in public_xbrl_files]
    stats_sorted_by_size = sorted(stats, key=lambda s: s.total_facts)
    stats_sorted_by_score = sorted(stats, key=lambda s: (-s.score, s.total_facts))

    print("\n[2] 2026 サンプルインスタンス PublicDoc .xbrl の概要")
    print(f"- files: {len(stats)}")
    print("- smallest 10:")
    for s in stats_sorted_by_size[:10]:
        lexical = dict(sorted(s.lexical_counts.items()))
        print(
            f"  - facts={s.total_facts:4d}, numeric={s.numeric_facts:4d}, "
            f"non_numeric={s.non_numeric_facts:4d}, nil={s.nil_facts:4d}, "
            f"dim_facts={s.dim_fact_count:4d}, units={s.unit_ids}, "
            f"lexical={lexical} :: {s.path}"
        )

    print("\n[3] 多様性スコア上位 5（score 高 + facts 少 を優先）")
    for s in stats_sorted_by_score[:5]:
        lexical = dict(sorted(s.lexical_counts.items()))
        print(
            f"  - score={s.score}, facts={s.total_facts}, units={s.unit_ids}, "
            f"dim_facts={s.dim_fact_count}, lexical={lexical} :: {s.path}"
        )


if __name__ == "__main__":
    main()

"""Parquet 永続化・復元モジュール。

Filing + Statements を Parquet ファイルに永続化し、
高速なロード・横断分析を実現する。

公開 API:
    - ``export_parquet()``: ドメインオブジェクト → Parquet
    - ``import_parquet()``: Parquet → ドメインオブジェクト
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from edinet.financial.statements import Statements
from edinet.models.filing import Filing

from ._deserialize import (
    deserialize_calc_linkbase,
    deserialize_context,
    deserialize_dei,
    deserialize_detected_standard,
    deserialize_filing,
    deserialize_line_item,
    deserialize_statements,
)
from ._serialize import (
    serialize_calc_edges,
    serialize_context,
    serialize_dei,
    serialize_def_parents,
    serialize_filing,
    serialize_line_item,
)

__all__ = ["export_parquet", "import_parquet"]


def _require_pyarrow() -> Any:
    """pyarrow のインポートを試み、失敗時は日本語エラーを返す。"""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        return pa, pq
    except ImportError:
        msg = (
            "pyarrow がインストールされていません。"
            "pip install pyarrow でインストールしてください。"
        )
        raise ImportError(msg) from None


def export_parquet(
    data: Sequence[tuple[Filing, Statements | None]],
    output_dir: str | Path,
    *,
    prefix: str = "",
) -> dict[str, Path]:
    """Filing + Statements を Parquet ファイルにエクスポートする。

    Args:
        data: ``(Filing, Statements | None)`` ペアのシーケンス。
            ``Statements=None`` は has_xbrl=False の書類。
        output_dir: 出力先ディレクトリ。
        prefix: ファイル名プレフィックス（例: ``"2026-01-01_"``）。

    Returns:
        テーブル名 → 出力パスの辞書。

    Raises:
        ImportError: pyarrow がインストールされていない場合。
    """
    pa, pq = _require_pyarrow()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filing_rows: list[dict[str, Any]] = []
    line_item_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    dei_rows: list[dict[str, Any]] = []
    calc_rows: list[dict[str, Any]] = []
    def_rows: list[dict[str, Any]] = []

    for filing, stmts in data:
        doc_id = filing.doc_id
        filing_rows.append(serialize_filing(filing))

        if stmts is None:
            continue

        # LineItems
        for item in stmts:
            line_item_rows.append(serialize_line_item(item, doc_id))

        # Contexts
        ctx_map = stmts.context_map
        if ctx_map:
            for ctx in ctx_map.values():
                context_rows.append(serialize_context(ctx, doc_id))

        # DEI
        dei = stmts.dei
        if dei is not None:
            dei_rows.append(
                serialize_dei(
                    dei,
                    doc_id,
                    detected_standard=stmts.detected_standard,
                )
            )

        # CalculationLinkbase
        calc = stmts.calculation_linkbase
        if calc is not None:
            calc_rows.extend(serialize_calc_edges(calc, doc_id))

        # DefinitionLinkbase → parent_index
        defn = stmts.definition_linkbase
        if defn is not None:
            def_rows.extend(serialize_def_parents(defn, doc_id))

    result: dict[str, Path] = {}

    # 1. filings.parquet（必須）
    if filing_rows:
        path = output_dir / f"{prefix}filings.parquet"
        table = pa.Table.from_pylist(filing_rows)
        pq.write_table(table, path)
        result["filings"] = path

    # 2. line_items.parquet
    if line_item_rows:
        path = output_dir / f"{prefix}line_items.parquet"
        table = pa.Table.from_pylist(line_item_rows)
        pq.write_table(table, path)
        result["line_items"] = path

    # 3. contexts.parquet
    if context_rows:
        path = output_dir / f"{prefix}contexts.parquet"
        table = pa.Table.from_pylist(context_rows)
        pq.write_table(table, path)
        result["contexts"] = path

    # 4. dei.parquet
    if dei_rows:
        path = output_dir / f"{prefix}dei.parquet"
        table = pa.Table.from_pylist(dei_rows)
        pq.write_table(table, path)
        result["dei"] = path

    # 5. calc_edges.parquet
    if calc_rows:
        path = output_dir / f"{prefix}calc_edges.parquet"
        table = pa.Table.from_pylist(calc_rows)
        pq.write_table(table, path)
        result["calc_edges"] = path

    # 6. def_parents.parquet
    if def_rows:
        path = output_dir / f"{prefix}def_parents.parquet"
        table = pa.Table.from_pylist(def_rows)
        pq.write_table(table, path)
        result["def_parents"] = path

    return result


def import_parquet(
    input_dir: str | Path,
    *,
    prefix: str = "",
) -> list[tuple[Filing, Statements | None]]:
    """Parquet ファイルから Filing + Statements を復元する。

    Args:
        input_dir: 入力ディレクトリ。
        prefix: ファイル名プレフィックス。

    Returns:
        ``(Filing, Statements | None)`` ペアのリスト。

    Raises:
        ImportError: pyarrow がインストールされていない場合。
        FileNotFoundError: filings.parquet が存在しない場合。
    """
    pa, pq = _require_pyarrow()
    input_dir = Path(input_dir)

    # 1. filings.parquet（必須）
    filings_path = input_dir / f"{prefix}filings.parquet"
    if not filings_path.exists():
        msg = f"filings.parquet が見つかりません: {filings_path}"
        raise FileNotFoundError(msg)

    filings_table = pq.read_table(filings_path)
    filing_dicts = filings_table.to_pylist()
    filings = [deserialize_filing(row) for row in filing_dicts]

    # 2. line_items.parquet（オプション）
    items_by_doc: dict[str, list[Any]] = defaultdict(list)
    li_path = input_dir / f"{prefix}line_items.parquet"
    if li_path.exists():
        li_table = pq.read_table(li_path)
        for row in li_table.to_pylist():
            items_by_doc[row["doc_id"]].append(deserialize_line_item(row))

    # 3. contexts.parquet（オプション）
    contexts_by_doc: dict[str, dict[str, Any]] = defaultdict(dict)
    ctx_path = input_dir / f"{prefix}contexts.parquet"
    if ctx_path.exists():
        ctx_table = pq.read_table(ctx_path)
        for row in ctx_table.to_pylist():
            ctx = deserialize_context(row)
            contexts_by_doc[row["doc_id"]][ctx.context_id] = ctx

    # 4. dei.parquet（オプション）
    dei_by_doc: dict[str, Any] = {}
    detected_std_by_doc: dict[str, Any] = {}
    dei_path = input_dir / f"{prefix}dei.parquet"
    if dei_path.exists():
        dei_table = pq.read_table(dei_path)
        for row in dei_table.to_pylist():
            dei_by_doc[row["doc_id"]] = deserialize_dei(row)
            ds = deserialize_detected_standard(row)
            if ds is not None:
                detected_std_by_doc[row["doc_id"]] = ds

    # 5. calc_edges.parquet（オプション）
    calc_rows_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    calc_path = input_dir / f"{prefix}calc_edges.parquet"
    if calc_path.exists():
        calc_table = pq.read_table(calc_path)
        for row in calc_table.to_pylist():
            calc_rows_by_doc[row["doc_id"]].append(row)

    # 組み立て
    result: list[tuple[Filing, Statements | None]] = []
    for filing in filings:
        doc_id = filing.doc_id
        items = items_by_doc.get(doc_id)
        if items is None:
            # has_xbrl=False の書類
            result.append((filing, None))
            continue

        dei = dei_by_doc.get(doc_id)
        detected_std = detected_std_by_doc.get(doc_id)
        contexts = contexts_by_doc.get(doc_id) or None
        calc_rows_list = calc_rows_by_doc.get(doc_id)
        calc_lb = (
            deserialize_calc_linkbase(calc_rows_list)
            if calc_rows_list
            else None
        )

        stmts = deserialize_statements(
            tuple(items),
            dei=dei,
            detected_standard=detected_std,
            contexts=contexts,
            calculation_linkbase=calc_lb,
        )
        result.append((filing, stmts))

    return result

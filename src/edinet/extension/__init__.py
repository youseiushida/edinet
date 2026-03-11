"""Parquet 永続化・復元モジュール。

Filing + Statements を Parquet ファイルに永続化し、
高速なロード・横断分析を実現する。

公開 API:
    - ``export_parquet()``: ドメインオブジェクト → Parquet
    - ``import_parquet()``: Parquet → ドメインオブジェクト
    - ``adump_to_parquet()``: メモリ効率バッチ永続化（非同期）
    - ``DumpResult``: ``adump_to_parquet()`` の実行結果
"""

from __future__ import annotations

import asyncio
import gc
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date as DateType
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Sequence

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
from ._schema import SCHEMAS
from ._serialize import (
    is_text_block,
    serialize_calc_edges,
    serialize_context,
    serialize_dei,
    serialize_def_parents,
    serialize_filing,
    serialize_line_item,
)

if TYPE_CHECKING:
    from edinet.models.doc_types import DocType

__all__ = [
    "export_parquet",
    "import_parquet",
    "iter_parquet",
    "adump_to_parquet",
    "adump_to_parquet_thread_pool",
    "DumpResult",
]

logger = logging.getLogger(__name__)


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
    compression: str = "zstd",
) -> dict[str, Path]:
    """Filing + Statements を Parquet ファイルにエクスポートする。

    書類単位で row group を作成するため、``iter_parquet()`` による
    doc_id 単位の効率的な読み込みと互換性がある。

    Args:
        data: ``(Filing, Statements | None)`` ペアのシーケンス。
            ``Statements=None`` は has_xbrl=False の書類。
        output_dir: 出力先ディレクトリ。
        prefix: ファイル名プレフィックス（例: ``"2026-01-01_"``）。
        compression: 圧縮アルゴリズム。デフォルト ``"zstd"``。
            ``"snappy"``, ``"gzip"``, ``"none"`` なども指定可能。

    Returns:
        テーブル名 → 出力パスの辞書。

    Raises:
        ImportError: pyarrow がインストールされていない場合。
    """
    _require_pyarrow()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    writers = _ParquetWriters(output_dir, prefix, compression)
    try:
        for filing, stmts in data:
            doc_id = filing.doc_id
            writers.write_rows("filings", [serialize_filing(filing)])

            if stmts is None:
                continue

            # LineItems — TextBlock を分離
            li_rows: list[dict[str, Any]] = []
            tb_rows: list[dict[str, Any]] = []
            for item in stmts:
                row = serialize_line_item(item, doc_id)
                if is_text_block(item.local_name):
                    tb_rows.append(row)
                else:
                    li_rows.append(row)
            writers.write_rows("line_items", li_rows)
            writers.write_rows("text_blocks", tb_rows)

            # Contexts
            ctx_map = stmts.context_map
            if ctx_map:
                writers.write_rows(
                    "contexts",
                    [serialize_context(ctx, doc_id)
                     for ctx in ctx_map.values()],
                )

            # DEI
            dei = stmts.dei
            if dei is not None:
                writers.write_rows(
                    "dei",
                    [serialize_dei(
                        dei, doc_id,
                        detected_standard=stmts.detected_standard,
                        source_path=stmts.source_path,
                    )],
                )

            # CalculationLinkbase
            calc = stmts.calculation_linkbase
            if calc is not None:
                writers.write_rows(
                    "calc_edges",
                    serialize_calc_edges(calc, doc_id),
                )

            # DefinitionLinkbase → parent_index
            defn = stmts.definition_linkbase
            if defn is not None:
                writers.write_rows(
                    "def_parents",
                    serialize_def_parents(defn, doc_id),
                )
    finally:
        result = writers.close()

    return result


def _read_auxiliary_tables(
    input_dir: Path,
    prefix: str,
    doc_filter: list[tuple[str, str, list[str]]] | None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, str]],
]:
    """補助テーブル（DEI, contexts, calc_edges, def_parents）を一括読み込みする。

    Args:
        input_dir: 入力ディレクトリ。
        prefix: ファイル名プレフィックス。
        doc_filter: doc_id フィルタ。``None`` なら全件読み込み。

    Returns:
        (dei_by_doc, detected_std_by_doc, source_path_by_doc,
         contexts_by_doc, calc_rows_by_doc, def_parent_index_by_doc)
    """
    _, pq = _require_pyarrow()

    dei_by_doc: dict[str, Any] = {}
    detected_std_by_doc: dict[str, Any] = {}
    source_path_by_doc: dict[str, str] = {}
    dei_path = input_dir / f"{prefix}dei.parquet"
    if dei_path.exists():
        dei_table = pq.read_table(dei_path, filters=doc_filter)
        for row in dei_table.to_pylist():
            dei_by_doc[row["doc_id"]] = deserialize_dei(row)
            ds = deserialize_detected_standard(row)
            if ds is not None:
                detected_std_by_doc[row["doc_id"]] = ds
            sp = row.get("source_path")
            if sp is not None:
                source_path_by_doc[row["doc_id"]] = sp

    contexts_by_doc: dict[str, dict[str, Any]] = defaultdict(dict)
    ctx_path = input_dir / f"{prefix}contexts.parquet"
    if ctx_path.exists():
        ctx_table = pq.read_table(ctx_path, filters=doc_filter)
        for row in ctx_table.to_pylist():
            ctx = deserialize_context(row)
            contexts_by_doc[row["doc_id"]][ctx.context_id] = ctx

    calc_rows_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    calc_path = input_dir / f"{prefix}calc_edges.parquet"
    if calc_path.exists():
        calc_table = pq.read_table(calc_path, filters=doc_filter)
        for row in calc_table.to_pylist():
            calc_rows_by_doc[row["doc_id"]].append(row)

    def_parent_index_by_doc: dict[str, dict[str, str]] = defaultdict(dict)
    def_path = input_dir / f"{prefix}def_parents.parquet"
    if def_path.exists():
        def_table = pq.read_table(def_path, filters=doc_filter)
        for row in def_table.to_pylist():
            def_parent_index_by_doc[row["doc_id"]][
                row["child_concept"]
            ] = row["parent_standard_concept"]

    return (
        dei_by_doc,
        detected_std_by_doc,
        source_path_by_doc,
        contexts_by_doc,
        calc_rows_by_doc,
        def_parent_index_by_doc,
    )


class _LazyAuxiliaryTables:
    """補助テーブルを ParquetFile として保持し、バッチ単位で read_row_groups する。

    ``iter_parquet()`` 用。全件を Python dict に展開せず、バッチごとに
    ``_build_rg_mapping`` で得た RG インデックスから ``read_row_groups()``
    で該当分だけ I/O → ``to_pylist()`` する。
    年間データ（数千万行の calc_edges 等）でもメモリがバッチサイズに比例する。
    """

    def __init__(
        self,
        input_dir: Path,
        prefix: str,
    ) -> None:
        """補助 Parquet を ParquetFile として開き、RG マッピングを構築する。

        Args:
            input_dir: 入力ディレクトリ。
            prefix: ファイル名プレフィックス。
        """
        _, pq = _require_pyarrow()

        self._dei_pf, self._dei_rg = self._open(
            input_dir / f"{prefix}dei.parquet", pq,
        )
        self._ctx_pf, self._ctx_rg = self._open(
            input_dir / f"{prefix}contexts.parquet", pq,
        )
        self._calc_pf, self._calc_rg = self._open(
            input_dir / f"{prefix}calc_edges.parquet", pq,
        )
        self._def_pf, self._def_rg = self._open(
            input_dir / f"{prefix}def_parents.parquet", pq,
        )

    @staticmethod
    def _open(
        path: Path, pq: Any,
    ) -> tuple[Any | None, dict[str, list[int]]]:
        """Parquet ファイルを開き RG マッピングを構築する。

        Args:
            path: Parquet ファイルパス。
            pq: ``pyarrow.parquet`` モジュール。

        Returns:
            ``(ParquetFile | None, rg_map)``。ファイルが存在しなければ
            ``(None, {})``。
        """
        if not path.exists():
            return None, {}
        pf = pq.ParquetFile(path)
        rg = _build_rg_mapping(pf)
        return pf, rg

    @staticmethod
    def _collect_rg_indices(
        rg_map: dict[str, list[int]],
        doc_ids: list[str],
    ) -> list[int]:
        """doc_id リストから RG インデックスを収集・ソートする。

        Args:
            rg_map: ``_build_rg_mapping()`` の返り値。
            doc_ids: 対象 doc_id リスト。

        Returns:
            ソート済み RG インデックスリスト。
        """
        indices: list[int] = []
        for did in doc_ids:
            indices.extend(rg_map.get(did, []))
        indices.sort()
        return indices

    def filter_batch(
        self,
        doc_ids: list[str],
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, str],
        dict[str, dict[str, Any]],
        dict[str, list[dict[str, Any]]],
        dict[str, dict[str, str]],
    ]:
        """バッチ内の doc_id に対応する補助データを返す。

        ``_build_rg_mapping`` で構築した RG マッピングを使い、
        ``read_row_groups()`` でバッチ分だけ I/O して
        ``_assemble_statements()`` に渡せる形式で返す。

        Args:
            doc_ids: バッチ内の doc_id リスト。

        Returns:
            ``_read_auxiliary_tables()`` と同じ 6-tuple。
        """
        # DEI
        dei_by_doc: dict[str, Any] = {}
        detected_std_by_doc: dict[str, Any] = {}
        source_path_by_doc: dict[str, str] = {}
        if self._dei_pf is not None:
            rg_indices = self._collect_rg_indices(self._dei_rg, doc_ids)
            if rg_indices:
                for row in self._dei_pf.read_row_groups(
                    rg_indices,
                ).to_pylist():
                    dei_by_doc[row["doc_id"]] = deserialize_dei(row)
                    ds = deserialize_detected_standard(row)
                    if ds is not None:
                        detected_std_by_doc[row["doc_id"]] = ds
                    sp = row.get("source_path")
                    if sp is not None:
                        source_path_by_doc[row["doc_id"]] = sp

        # Contexts
        contexts_by_doc: dict[str, dict[str, Any]] = defaultdict(dict)
        if self._ctx_pf is not None:
            rg_indices = self._collect_rg_indices(self._ctx_rg, doc_ids)
            if rg_indices:
                for row in self._ctx_pf.read_row_groups(
                    rg_indices,
                ).to_pylist():
                    ctx = deserialize_context(row)
                    contexts_by_doc[row["doc_id"]][ctx.context_id] = ctx

        # calc_edges
        calc_rows_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if self._calc_pf is not None:
            rg_indices = self._collect_rg_indices(self._calc_rg, doc_ids)
            if rg_indices:
                for row in self._calc_pf.read_row_groups(
                    rg_indices,
                ).to_pylist():
                    calc_rows_by_doc[row["doc_id"]].append(row)

        # def_parents
        def_parent_index_by_doc: dict[str, dict[str, str]] = defaultdict(dict)
        if self._def_pf is not None:
            rg_indices = self._collect_rg_indices(self._def_rg, doc_ids)
            if rg_indices:
                for row in self._def_pf.read_row_groups(
                    rg_indices,
                ).to_pylist():
                    def_parent_index_by_doc[row["doc_id"]][
                        row["child_concept"]
                    ] = row["parent_standard_concept"]

        return (
            dei_by_doc,
            detected_std_by_doc,
            source_path_by_doc,
            dict(contexts_by_doc),
            dict(calc_rows_by_doc),
            dict(def_parent_index_by_doc),
        )


def _assemble_statements(
    doc_id: str,
    items: list[Any],
    dei_by_doc: dict[str, Any],
    detected_std_by_doc: dict[str, Any],
    source_path_by_doc: dict[str, str],
    contexts_by_doc: dict[str, dict[str, Any]],
    calc_rows_by_doc: dict[str, list[dict[str, Any]]],
    def_parent_index_by_doc: dict[str, dict[str, str]],
) -> Statements:
    """1 書類分の Statements を組み立てる。

    Args:
        doc_id: 書類 ID。
        items: 復元済み LineItem リスト。
        dei_by_doc: DEI マッピング。
        detected_std_by_doc: DetectedStandard マッピング。
        source_path_by_doc: source_path マッピング。
        contexts_by_doc: Context マッピング。
        calc_rows_by_doc: CalculationArc 行マッピング。
        def_parent_index_by_doc: DefinitionParentIndex マッピング。

    Returns:
        復元済み Statements。
    """
    dei = dei_by_doc.get(doc_id)
    detected_std = detected_std_by_doc.get(doc_id)
    contexts = contexts_by_doc.get(doc_id) or None
    calc_rows_list = calc_rows_by_doc.get(doc_id)
    calc_lb = (
        deserialize_calc_linkbase(calc_rows_list)
        if calc_rows_list
        else None
    )
    def_pi = def_parent_index_by_doc.get(doc_id) or None

    return deserialize_statements(
        tuple(items),
        dei=dei,
        detected_standard=detected_std,
        contexts=contexts,
        calculation_linkbase=calc_lb,
        definition_parent_index=def_pi,
        source_path=source_path_by_doc.get(doc_id),
    )


def import_parquet(
    input_dir: str | Path,
    *,
    prefix: str = "",
    include_text_blocks: bool = True,
    doc_ids: Sequence[str] | None = None,
    doc_type_codes: Sequence[str] | None = None,
    concepts: Sequence[str] | None = None,
) -> list[tuple[Filing, Statements | None]]:
    """Parquet ファイルから Filing + Statements を復元する。

    Args:
        input_dir: 入力ディレクトリ。
        prefix: ファイル名プレフィックス。
        include_text_blocks: ``True``（デフォルト）なら ``text_blocks.parquet``
            も読み込み ``line_items`` と統合する。``False`` なら数値 Fact のみの
            軽量ロード。旧形式（text_blocks 未分離）のデータも自動検出して読み込む。
        doc_ids: 読み込む doc_id のリスト。``None`` なら全件読み込み。
            PyArrow の predicate pushdown により対象行だけ読み込まれる。
        doc_type_codes: 読み込む書類種別コードのリスト
            （例: ``["120", "130"]`` で有報+半期報告書）。
            ``None`` なら全種別。filings 読み込み後にフィルタされ、
            該当 doc_id のみ他テーブルから読み込む。
        concepts: 読み込む科目の ``local_name`` リスト（例: ``["NetSales"]``）。
            ``None`` なら全科目。``line_items`` / ``text_blocks`` に適用される。

    Returns:
        ``(Filing, Statements | None)`` ペアのリスト。

    Raises:
        ImportError: pyarrow がインストールされていない場合。
        FileNotFoundError: filings.parquet が存在しない場合。
    """
    _, pq = _require_pyarrow()
    input_dir = Path(input_dir)

    # フィルタ構築
    doc_filter: list[tuple[str, str, list[str]]] | None = (
        [("doc_id", "in", list(doc_ids))] if doc_ids is not None else None
    )
    li_conditions: list[tuple[str, str, list[str]]] = []
    if doc_ids is not None:
        li_conditions.append(("doc_id", "in", list(doc_ids)))
    if concepts is not None:
        li_conditions.append(("local_name", "in", list(concepts)))
    li_filter = li_conditions or None

    # 1. filings.parquet（必須）
    filings_path = input_dir / f"{prefix}filings.parquet"
    if not filings_path.exists():
        msg = f"filings.parquet が見つかりません: {filings_path}"
        raise FileNotFoundError(msg)

    filings_table = pq.read_table(filings_path, filters=doc_filter)
    filings = [deserialize_filing(row) for row in filings_table.to_pylist()]

    # doc_type_codes フィルタ（filings 読み込み後、軽量な Python フィルタ）
    if doc_type_codes is not None:
        _allowed = set(doc_type_codes)
        filings = [f for f in filings if f.doc_type_code in _allowed]
        # フィルタ後の doc_id で他テーブルの読み込みを絞る
        if doc_ids is None:
            doc_ids = [f.doc_id for f in filings]
            doc_filter = [("doc_id", "in", list(doc_ids))]
            li_conditions = [("doc_id", "in", list(doc_ids))]
            if concepts is not None:
                li_conditions.append(("local_name", "in", list(concepts)))
            li_filter = li_conditions

    # 2. line_items.parquet（オプション）
    items_by_doc: dict[str, list[Any]] = defaultdict(list)
    li_path = input_dir / f"{prefix}line_items.parquet"
    if li_path.exists():
        li_table = pq.read_table(li_path, filters=li_filter)
        for row in li_table.to_pylist():
            items_by_doc[row["doc_id"]].append(deserialize_line_item(row))

    # 2b. text_blocks.parquet（オプション — TextBlock 分離テーブル）
    if include_text_blocks:
        tb_path = input_dir / f"{prefix}text_blocks.parquet"
        if tb_path.exists():
            tb_table = pq.read_table(tb_path, filters=li_filter)
            for row in tb_table.to_pylist():
                items_by_doc[row["doc_id"]].append(deserialize_line_item(row))

    # 3-6. 補助テーブル
    (
        dei_by_doc,
        detected_std_by_doc,
        source_path_by_doc,
        contexts_by_doc,
        calc_rows_by_doc,
        def_parent_index_by_doc,
    ) = _read_auxiliary_tables(input_dir, prefix, doc_filter)

    # 組み立て
    result: list[tuple[Filing, Statements | None]] = []
    for filing in filings:
        doc_id = filing.doc_id
        items = items_by_doc.get(doc_id)
        if items is None:
            result.append((filing, None))
            continue

        stmts = _assemble_statements(
            doc_id,
            items,
            dei_by_doc,
            detected_std_by_doc,
            source_path_by_doc,
            contexts_by_doc,
            calc_rows_by_doc,
            def_parent_index_by_doc,
        )
        result.append((filing, stmts))

    return result


def _build_rg_mapping(pf: Any) -> dict[str, list[int]]:
    """ParquetFile から doc_id → row_group_indices マッピングを構築する。

    1 書類 = 1 row group の不変条件を前提とし、各 row group の
    先頭行の doc_id だけを Python 文字列化する。全行の ``to_pylist()``
    を回避し、年間データ（数億行）でも数 KB のメモリで完結する。

    Args:
        pf: ``pq.ParquetFile`` インスタンス。

    Returns:
        ``{doc_id: [row_group_index, ...]}`` マッピング。
    """
    doc_id_col = pf.read(columns=["doc_id"]).column("doc_id")
    rg_map: dict[str, list[int]] = defaultdict(list)
    offset = 0
    for i in range(pf.metadata.num_row_groups):
        n = pf.metadata.row_group(i).num_rows
        did = doc_id_col[offset].as_py()
        rg_map[did].append(i)
        offset += n
    return dict(rg_map)


def _read_row_groups_filtered(
    pf: Any,
    rg_map: dict[str, list[int]],
    batch_filings: list[Filing],
    concepts_arr: Any | None,
) -> dict[str, list[Any]]:
    """バッチ内の Filing に対応する row group を読み込み、doc_id 別に分類する。

    Args:
        pf: ``pq.ParquetFile`` インスタンス。
        rg_map: ``_build_rg_mapping()`` の返り値。
        batch_filings: バッチ内の Filing リスト。
        concepts_arr: ``pa.array(concepts)`` または ``None``。

    Returns:
        ``{doc_id: [deserialized LineItem, ...]}`` マッピング。
    """
    rg_indices: list[int] = []
    for f in batch_filings:
        rg_indices.extend(rg_map.get(f.doc_id, []))
    if not rg_indices:
        return {}

    rg_indices.sort()
    table = pf.read_row_groups(rg_indices)

    # concepts フィルタ（行レベル）
    if concepts_arr is not None:
        import pyarrow.compute as pc

        mask = pc.is_in(
            table.column("local_name"), value_set=concepts_arr,
        )
        table = table.filter(mask)

    items_by_doc: dict[str, list[Any]] = defaultdict(list)
    for row in table.to_pylist():
        items_by_doc[row["doc_id"]].append(deserialize_line_item(row))
    return items_by_doc


def iter_parquet(
    input_dir: str | Path,
    *,
    prefix: str = "",
    include_text_blocks: bool = False,
    batch_size: int = 100,
    doc_ids: Sequence[str] | None = None,
    doc_type_codes: Sequence[str] | None = None,
    concepts: Sequence[str] | None = None,
) -> Iterator[tuple[Filing, Statements | None]]:
    """Parquet ファイルから Filing + Statements をイテレータで返す。

    ``import_parquet()`` と異なり、line_items / text_blocks を
    バッチ単位で読み込むため、メモリ使用量が件数に依存しない。
    数万件規模のデータに対して ``extract_values()`` を逐次実行する
    バッチ処理に最適。

    内部では ``ParquetFile`` を 1 回だけ開き、``doc_id → row_group``
    マッピングを構築して ``read_row_groups()`` で効率的に読む。

    Args:
        input_dir: 入力ディレクトリ。
        prefix: ファイル名プレフィックス。
        include_text_blocks: ``True`` なら ``text_blocks.parquet``
            も読み込む。大規模処理向けにデフォルト ``False``。
        batch_size: line_items を一度に読み込む書類数。
            デフォルト ``100``。
        doc_ids: 読み込む doc_id のリスト。``None`` なら全件。
        doc_type_codes: 読み込む書類種別コードのリスト
            （例: ``["120", "130"]`` で有報+半期報告書）。
            ``None`` なら全種別。filings 読み込み後にフィルタされるため、
            line_items 等の重いテーブルは該当書類分しか読まない。
        concepts: 読み込む科目の ``local_name`` リスト。``None`` なら全科目。

    Yields:
        ``(Filing, Statements | None)`` ペア。

    Raises:
        ImportError: pyarrow がインストールされていない場合。
        FileNotFoundError: filings.parquet が存在しない場合。
    """
    pa, pq = _require_pyarrow()
    input_dir = Path(input_dir)

    # フィルタ構築
    doc_filter: list[tuple[str, str, list[str]]] | None = (
        [("doc_id", "in", list(doc_ids))] if doc_ids is not None else None
    )

    # 1. filings.parquet（必須）
    filings_path = input_dir / f"{prefix}filings.parquet"
    if not filings_path.exists():
        msg = f"filings.parquet が見つかりません: {filings_path}"
        raise FileNotFoundError(msg)

    filings_table = pq.read_table(filings_path, filters=doc_filter)
    filings = [deserialize_filing(row) for row in filings_table.to_pylist()]

    # doc_type_codes フィルタ（filings 読み込み後、軽量な Python フィルタ）
    if doc_type_codes is not None:
        _allowed = set(doc_type_codes)
        filings = [f for f in filings if f.doc_type_code in _allowed]

    # 2. 補助テーブル（ParquetFile として保持、バッチごとに read_row_groups）
    aux = _LazyAuxiliaryTables(input_dir, prefix)

    # 3. line_items / text_blocks — ParquetFile を1回だけ開く
    li_path = input_dir / f"{prefix}line_items.parquet"
    tb_path = input_dir / f"{prefix}text_blocks.parquet"
    has_li = li_path.exists()
    has_tb = include_text_blocks and tb_path.exists()

    li_pf = pq.ParquetFile(li_path) if has_li else None
    tb_pf = pq.ParquetFile(tb_path) if has_tb else None
    li_rg_map = _build_rg_mapping(li_pf) if li_pf is not None else {}
    tb_rg_map = _build_rg_mapping(tb_pf) if tb_pf is not None else {}

    # concepts フィルタ用 Arrow 配列（1回だけ構築）
    concepts_arr = pa.array(list(concepts)) if concepts is not None else None

    for batch_start in range(0, len(filings), batch_size):
        batch_filings = filings[batch_start : batch_start + batch_size]

        # バッチ内 doc_id で補助テーブルをフィルタ
        batch_doc_ids = [f.doc_id for f in batch_filings]
        (
            dei_by_doc,
            detected_std_by_doc,
            source_path_by_doc,
            contexts_by_doc,
            calc_rows_by_doc,
            def_parent_index_by_doc,
        ) = aux.filter_batch(batch_doc_ids)

        items_by_doc: dict[str, list[Any]] = defaultdict(list)

        if li_pf is not None:
            for did, items in _read_row_groups_filtered(
                li_pf, li_rg_map, batch_filings, concepts_arr,
            ).items():
                items_by_doc[did].extend(items)

        if tb_pf is not None:
            for did, items in _read_row_groups_filtered(
                tb_pf, tb_rg_map, batch_filings, concepts_arr,
            ).items():
                items_by_doc[did].extend(items)

        for filing in batch_filings:
            doc_id = filing.doc_id
            items = items_by_doc.get(doc_id)
            if items is None:
                yield (filing, None)
                continue

            stmts = _assemble_statements(
                doc_id,
                items,
                dei_by_doc,
                detected_std_by_doc,
                source_path_by_doc,
                contexts_by_doc,
                calc_rows_by_doc,
                def_parent_index_by_doc,
            )
            yield (filing, stmts)


# ---------------------------------------------------------------------------
# adump_to_parquet — メモリ効率バッチ永続化
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DumpResult:
    """``adump_to_parquet()`` の実行結果。

    Attributes:
        paths: テーブル名 → 出力パスの辞書。
        total_filings: 書類一覧の総件数。
        xbrl_count: XBRL フラグが True の書類数。
        xbrl_ok: XBRL パースに成功した書類数。
        errors: XBRL パースエラー件数。
    """

    paths: dict[str, Path]
    total_filings: int
    xbrl_count: int
    xbrl_ok: int
    errors: int


class _ParquetWriters:
    """7テーブルの ParquetWriter をまとめて管理する。

    ドキュメント単位で即書き出しするためのコンテキストマネージャ。
    """

    _TABLE_NAMES = (
        "filings", "line_items", "text_blocks", "contexts", "dei",
        "calc_edges", "def_parents",
    )

    def __init__(
        self,
        output_dir: Path,
        prefix: str,
        compression: str,
    ) -> None:
        self._output_dir = output_dir
        self._prefix = prefix
        self._compression: str | None = (
            None if compression == "none" else compression
        )
        self._writers: dict[str, Any] = {}
        self._paths: dict[str, Path] = {}
        self._has_rows: set[str] = set()

    def _get_writer(self, name: str) -> Any:
        """テーブル名に対応する ParquetWriter を返す（遅延生成）。"""
        if name not in self._writers:
            _, pq = _require_pyarrow()
            schema_fn = SCHEMAS[name]
            path = self._output_dir / f"{self._prefix}{name}.parquet"
            self._writers[name] = pq.ParquetWriter(
                path, schema_fn(), compression=self._compression,
            )
            self._paths[name] = path
        return self._writers[name]

    def write_rows(self, name: str, rows: list[dict[str, Any]]) -> None:
        """dict 行リストを row group として即書き出しする。

        Args:
            name: テーブル名。
            rows: 書き出す行リスト。空リストの場合は何もしない。
        """
        if not rows:
            return
        pa, _ = _require_pyarrow()
        schema_fn = SCHEMAS[name]
        writer = self._get_writer(name)
        table = pa.Table.from_pylist(rows, schema=schema_fn())
        writer.write_table(table)
        self._has_rows.add(name)

    def close(self) -> dict[str, Path]:
        """全 Writer を閉じ、行が書かれたテーブルのパスを返す。"""
        for writer in self._writers.values():
            writer.close()
        return {
            name: self._paths[name]
            for name in self._has_rows
            if name in self._paths
        }


async def adump_to_parquet(
    date: str | DateType | None = None,
    *,
    # --- adocuments() と同じフィルタ引数 ---
    start: str | DateType | None = None,
    end: str | DateType | None = None,
    doc_type: DocType | str | None = None,
    edinet_code: str | None = None,
    on_invalid: Literal["skip", "error"] = "skip",
    # --- 出力設定 ---
    output_dir: str | Path = ".",
    prefix: str = "",
    compression: str = "zstd",
    # --- パース設定 ---
    concurrency: int = 8,
    taxonomy_path: str | None = None,
    strict: bool = False,
) -> DumpResult:
    """メモリ効率的な非同期バッチ Parquet 永続化。

    ``adocuments()`` で書類一覧を取得し、XBRL をドキュメント単位で
    ダウンロード → パース → Parquet 書き出し → 即解放する。
    Statements も dict 行もメモリに蓄積しない。

    Args:
        date: 単日指定（``YYYY-MM-DD`` 文字列または ``date``）。
        start: 範囲指定の開始日。
        end: 範囲指定の終了日。
        doc_type: ``DocType`` または ``docTypeCode`` 文字列。
        edinet_code: ``E`` + 5桁の提出者コード。
        on_invalid: 不正行の扱い（``"skip"`` or ``"error"``）。
        output_dir: 出力先ディレクトリ。
        prefix: ファイル名プレフィックス（例: ``"2026-01-01_"``）。
        compression: 圧縮アルゴリズム。デフォルト ``"zstd"``。
        concurrency: 同時パース並行数。デフォルト ``8``。
        taxonomy_path: EDINET タクソノミのルートパス。
        strict: ``False``（デフォルト）で警告降格。

    Returns:
        ``DumpResult``: パス・カウントを含む実行結果。

    Raises:
        ImportError: pyarrow がインストールされていない場合。
    """
    _require_pyarrow()

    from edinet.public_api import adocuments

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. 書類一覧を取得
    filings = await adocuments(
        date,
        start=start,
        end=end,
        doc_type=doc_type,
        edinet_code=edinet_code,
        on_invalid=on_invalid,
    )
    total_filings = len(filings)

    xbrl_filings = [f for f in filings if f.has_xbrl]
    non_xbrl_filings = [f for f in filings if not f.has_xbrl]
    xbrl_count = len(xbrl_filings)

    # 2. Writer を準備
    writers = _ParquetWriters(output_path, prefix, compression)

    try:
        # 3. non-XBRL → 即書き出し
        if non_xbrl_filings:
            writers.write_rows(
                "filings",
                [serialize_filing(f) for f in non_xbrl_filings],
            )

        # 4. XBRL をドキュメント単位で処理
        sem = asyncio.Semaphore(concurrency)
        xbrl_ok = 0
        errors = 0
        processed = 0

        async def _process_xbrl(filing: Filing) -> None:
            nonlocal xbrl_ok, errors, processed

            # ダウンロード + パース（並行）
            async with sem:
                doc_id = filing.doc_id
                stmts = None
                try:
                    stmts = await filing.axbrl(
                        taxonomy_path=taxonomy_path, strict=strict
                    )
                except Exception:
                    logger.warning(
                        "XBRL パース失敗: %s", filing.doc_id, exc_info=True
                    )
                    errors += 1

            # シリアライズ + 書き出し（同期、排他不要）
            writers.write_rows("filings", [serialize_filing(filing)])

            if stmts is not None:
                li_rows: list[dict[str, Any]] = []
                tb_rows: list[dict[str, Any]] = []
                for item in stmts:
                    row = serialize_line_item(item, doc_id)
                    if is_text_block(item.local_name):
                        tb_rows.append(row)
                    else:
                        li_rows.append(row)
                writers.write_rows("line_items", li_rows)
                writers.write_rows("text_blocks", tb_rows)

                ctx_map = stmts.context_map
                if ctx_map:
                    writers.write_rows(
                        "contexts",
                        [serialize_context(ctx, doc_id)
                         for ctx in ctx_map.values()],
                    )

                dei = stmts.dei
                if dei is not None:
                    writers.write_rows(
                        "dei",
                        [serialize_dei(
                            dei, doc_id,
                            detected_standard=stmts.detected_standard,
                            source_path=stmts.source_path,
                        )],
                    )

                calc = stmts.calculation_linkbase
                if calc is not None:
                    writers.write_rows(
                        "calc_edges",
                        serialize_calc_edges(calc, doc_id),
                    )

                defn = stmts.definition_linkbase
                if defn is not None:
                    writers.write_rows(
                        "def_parents",
                        serialize_def_parents(defn, doc_id),
                    )

                del stmts
                xbrl_ok += 1

            filing.clear_fetch_cache()
            processed += 1
            if processed % 20 == 0:
                gc.collect()

        await asyncio.gather(*[_process_xbrl(f) for f in xbrl_filings])

    finally:
        result_paths = writers.close()

    return DumpResult(
        paths=result_paths,
        total_filings=total_filings,
        xbrl_count=xbrl_count,
        xbrl_ok=xbrl_ok,
        errors=errors,
    )


async def adump_to_parquet_thread_pool(
    date: str | DateType | None = None,
    *,
    # --- adocuments() と同じフィルタ引数 ---
    start: str | DateType | None = None,
    end: str | DateType | None = None,
    doc_type: DocType | str | None = None,
    edinet_code: str | None = None,
    on_invalid: Literal["skip", "error"] = "skip",
    # --- 出力設定 ---
    output_dir: str | Path = ".",
    prefix: str = "",
    compression: str = "zstd",
    # --- パース設定 ---
    concurrency: int = 8,
    max_workers: int = 4,
    taxonomy_path: str | None = None,
    strict: bool = False,
) -> DumpResult:
    """ThreadPoolExecutor で XBRL パースをオフロードするバッチ Parquet 永続化。

    ``adump_to_parquet()`` と同じインターフェースだが、``_build_statements``
    を ``ThreadPoolExecutor`` でオフロードすることで DL とパースを真に
    並行化し、パイプライン全体のスループットを向上させる。

    パイプライン構造::

        Main thread (event loop):
          1. adocuments() → filings
          2. non-XBRL → 即 write
          3. XBRL: asyncio.gather([_process_xbrl(f, pool) for f in xbrl_filings])

        _process_xbrl(filing, pool):
          [main thread]  async with sem: await filing.afetch()
          [thread pool]  stmts = await loop.run_in_executor(pool, _build_statements, ...)
          [main thread]  serialize + writers.write_rows(...)
          [main thread]  filing.clear_fetch_cache()

    Args:
        date: 単日指定（``YYYY-MM-DD`` 文字列または ``date``）。
        start: 範囲指定の開始日。
        end: 範囲指定の終了日。
        doc_type: ``DocType`` または ``docTypeCode`` 文字列。
        edinet_code: ``E`` + 5桁の提出者コード。
        on_invalid: 不正行の扱い（``"skip"`` or ``"error"``）。
        output_dir: 出力先ディレクトリ。
        prefix: ファイル名プレフィックス（例: ``"2026-01-01_"``）。
        compression: 圧縮アルゴリズム。デフォルト ``"zstd"``。
        concurrency: 同時ダウンロード並行数。デフォルト ``8``。
        max_workers: ThreadPoolExecutor のワーカー数。デフォルト ``4``。
        taxonomy_path: EDINET タクソノミのルートパス。
        strict: ``False``（デフォルト）で警告降格。

    Returns:
        ``DumpResult``: パス・カウントを含む実行結果。

    Raises:
        ImportError: pyarrow がインストールされていない場合。
    """
    from concurrent.futures import ThreadPoolExecutor
    from functools import partial

    _require_pyarrow()

    from edinet.public_api import adocuments

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. 書類一覧を取得
    filings = await adocuments(
        date,
        start=start,
        end=end,
        doc_type=doc_type,
        edinet_code=edinet_code,
        on_invalid=on_invalid,
    )
    total_filings = len(filings)

    xbrl_filings = [f for f in filings if f.has_xbrl]
    non_xbrl_filings = [f for f in filings if not f.has_xbrl]
    xbrl_count = len(xbrl_filings)

    # 2. Writer を準備
    writers = _ParquetWriters(output_path, prefix, compression)
    loop = asyncio.get_running_loop()

    try:
        # 3. non-XBRL → 即書き出し
        if non_xbrl_filings:
            writers.write_rows(
                "filings",
                [serialize_filing(f) for f in non_xbrl_filings],
            )

        # 4. XBRL をドキュメント単位で処理（ThreadPool でパースオフロード）
        sem = asyncio.Semaphore(concurrency)
        xbrl_ok = 0
        errors = 0
        processed = 0

        async def _process_xbrl(filing: Filing, pool: ThreadPoolExecutor) -> None:
            nonlocal xbrl_ok, errors, processed

            doc_id = filing.doc_id
            stmts = None

            try:
                # DL（イベントループ上、セマフォで並行数制御）
                async with sem:
                    xbrl_path, xbrl_bytes = await filing.afetch()
                    resolved_tp = filing._resolve_taxonomy_path(taxonomy_path)

                # パース（ThreadPool へオフロード）
                stmts = await loop.run_in_executor(
                    pool,
                    partial(
                        filing._build_statements,
                        resolved_tp,
                        xbrl_path,
                        xbrl_bytes,
                        strict=strict,
                    ),
                )
            except Exception:
                logger.warning(
                    "XBRL パース失敗: %s", filing.doc_id, exc_info=True
                )
                errors += 1

            # シリアライズ + 書き出し（メインスレッド、_ParquetWriters は非スレッドセーフ）
            writers.write_rows("filings", [serialize_filing(filing)])

            if stmts is not None:
                li_rows: list[dict[str, Any]] = []
                tb_rows: list[dict[str, Any]] = []
                for item in stmts:
                    row = serialize_line_item(item, doc_id)
                    if is_text_block(item.local_name):
                        tb_rows.append(row)
                    else:
                        li_rows.append(row)
                writers.write_rows("line_items", li_rows)
                writers.write_rows("text_blocks", tb_rows)

                ctx_map = stmts.context_map
                if ctx_map:
                    writers.write_rows(
                        "contexts",
                        [serialize_context(ctx, doc_id)
                         for ctx in ctx_map.values()],
                    )

                dei = stmts.dei
                if dei is not None:
                    writers.write_rows(
                        "dei",
                        [serialize_dei(
                            dei, doc_id,
                            detected_standard=stmts.detected_standard,
                            source_path=stmts.source_path,
                        )],
                    )

                calc = stmts.calculation_linkbase
                if calc is not None:
                    writers.write_rows(
                        "calc_edges",
                        serialize_calc_edges(calc, doc_id),
                    )

                defn = stmts.definition_linkbase
                if defn is not None:
                    writers.write_rows(
                        "def_parents",
                        serialize_def_parents(defn, doc_id),
                    )

                del stmts
                xbrl_ok += 1

            filing.clear_fetch_cache()
            processed += 1
            if processed % 20 == 0:
                gc.collect()

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            await asyncio.gather(
                *[_process_xbrl(f, pool) for f in xbrl_filings]
            )

    finally:
        result_paths = writers.close()

    return DumpResult(
        paths=result_paths,
        total_filings=total_filings,
        xbrl_count=xbrl_count,
        xbrl_ok=xbrl_ok,
        errors=errors,
    )

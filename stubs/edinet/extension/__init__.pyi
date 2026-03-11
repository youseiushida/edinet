from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date as DateType
from edinet.financial.statements import Statements
from edinet.models.doc_types import DocType
from edinet.models.filing import Filing
from pathlib import Path
from typing import Any, Literal, Sequence

__all__ = ['export_parquet', 'import_parquet', 'iter_parquet', 'adump_to_parquet', 'adump_to_parquet_thread_pool', 'DumpResult']

def export_parquet(data: Sequence[tuple[Filing, Statements | None]], output_dir: str | Path, *, prefix: str = '', compression: str = 'zstd') -> dict[str, Path]:
    '''Filing + Statements を Parquet ファイルにエクスポートする。

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
    '''

class _LazyAuxiliaryTables:
    """補助テーブルを ParquetFile として保持し、バッチ単位で read_row_groups する。

    ``iter_parquet()`` 用。全件を Python dict に展開せず、バッチごとに
    ``_build_rg_mapping`` で得た RG インデックスから ``read_row_groups()``
    で該当分だけ I/O → ``to_pylist()`` する。
    年間データ（数千万行の calc_edges 等）でもメモリがバッチサイズに比例する。
    """
    def __init__(self, input_dir: Path, prefix: str) -> None:
        """補助 Parquet を ParquetFile として開き、RG マッピングを構築する。

        Args:
            input_dir: 入力ディレクトリ。
            prefix: ファイル名プレフィックス。
        """
    def filter_batch(self, doc_ids: list[str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, dict[str, str]]]:
        """バッチ内の doc_id に対応する補助データを返す。

        ``_build_rg_mapping`` で構築した RG マッピングを使い、
        ``read_row_groups()`` でバッチ分だけ I/O して
        ``_assemble_statements()`` に渡せる形式で返す。

        Args:
            doc_ids: バッチ内の doc_id リスト。

        Returns:
            ``_read_auxiliary_tables()`` と同じ 6-tuple。
        """

def import_parquet(input_dir: str | Path, *, prefix: str = '', include_text_blocks: bool = True, doc_ids: Sequence[str] | None = None, doc_type_codes: Sequence[str] | None = None, concepts: Sequence[str] | None = None) -> list[tuple[Filing, Statements | None]]:
    '''Parquet ファイルから Filing + Statements を復元する。

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
    '''
def iter_parquet(input_dir: str | Path, *, prefix: str = '', include_text_blocks: bool = False, batch_size: int = 100, doc_ids: Sequence[str] | None = None, doc_type_codes: Sequence[str] | None = None, concepts: Sequence[str] | None = None) -> Iterator[tuple[Filing, Statements | None]]:
    '''Parquet ファイルから Filing + Statements をイテレータで返す。

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
    '''

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
    def __init__(self, output_dir: Path, prefix: str, compression: str) -> None: ...
    def write_rows(self, name: str, rows: list[dict[str, Any]]) -> None:
        """dict 行リストを row group として即書き出しする。

        Args:
            name: テーブル名。
            rows: 書き出す行リスト。空リストの場合は何もしない。
        """
    def close(self) -> dict[str, Path]:
        """全 Writer を閉じ、行が書かれたテーブルのパスを返す。"""

async def adump_to_parquet(date: str | DateType | None = None, *, start: str | DateType | None = None, end: str | DateType | None = None, doc_type: DocType | str | None = None, edinet_code: str | None = None, on_invalid: Literal['skip', 'error'] = 'skip', output_dir: str | Path = '.', prefix: str = '', compression: str = 'zstd', concurrency: int = 8, taxonomy_path: str | None = None, strict: bool = False) -> DumpResult:
    '''メモリ効率的な非同期バッチ Parquet 永続化。

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
    '''
async def adump_to_parquet_thread_pool(date: str | DateType | None = None, *, start: str | DateType | None = None, end: str | DateType | None = None, doc_type: DocType | str | None = None, edinet_code: str | None = None, on_invalid: Literal['skip', 'error'] = 'skip', output_dir: str | Path = '.', prefix: str = '', compression: str = 'zstd', concurrency: int = 8, max_workers: int = 4, taxonomy_path: str | None = None, strict: bool = False) -> DumpResult:
    '''ThreadPoolExecutor で XBRL パースをオフロードするバッチ Parquet 永続化。

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
    '''

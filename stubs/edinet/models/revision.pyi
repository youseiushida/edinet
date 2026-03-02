from _typeshed import Incomplete
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from edinet.models.filing import Filing as Filing

logger: Incomplete

@dataclass(frozen=True, slots=True)
class RevisionChain:
    """訂正報告書チェーン。

    原本と全訂正版を ``submit_date_time`` 順で保持する。
    ``chain[0]`` が原本、``chain[-1]`` が最新版。

    Attributes:
        chain: 原本から最新版までの Filing タプル（時系列順）。

    利用例:
        >>> chain.original.doc_id        # 原本
        'S100ABC0'
        >>> chain.latest.doc_id          # 最新版
        'S100DEF2'
        >>> chain.is_corrected           # 訂正ありか
        True
        >>> chain.count                  # チェーン長（原本含む）
        3
        >>> for f in chain.chain:        # 時系列で走査
        ...     print(f.doc_id, f.submit_date_time)
    """
    chain: tuple[Filing, ...]
    def __post_init__(self) -> None:
        """チェーンの整合性を検証する。"""
    @property
    def original(self) -> Filing:
        """チェーンの先頭（最も古い）Filing を返す。

        通常は原本（``parent_doc_id is None``）。ただし原本が
        検索範囲外（365 日超前）で発見できなかった場合は、最古の
        訂正版が返る可能性がある。

        Returns:
            チェーン先頭の Filing。
        """
    @property
    def latest(self) -> Filing:
        """最新版 Filing を返す。

        チェーンの末尾要素（``submit_date_time`` が最も新しい Filing）。
        訂正がない場合は原本と同一。

        Returns:
            最新版 Filing。
        """
    @property
    def is_corrected(self) -> bool:
        """訂正があるかどうかを返す。

        チェーン長が 2 以上なら訂正あり。

        Returns:
            訂正ありなら True。
        """
    @property
    def count(self) -> int:
        """チェーン長（原本を含む）を返す。

        Returns:
            チェーン内の Filing 数。
        """
    def at_time(self, cutoff: date | datetime) -> Filing:
        """指定時点で入手可能だった最新版を返す。

        ``submit_date_time <= cutoff`` の Filing のうち最新のものを返す。
        バックテストで「あの時点で市場参加者が見ることができた版」を
        再現するために使う。

        Args:
            cutoff: 基準日時。``date`` または ``datetime`` を受け付ける。
                ``date`` を渡した場合はその日の終わり（23:59:59）として
                扱い、その日中に提出された Filing を含める。
                ``datetime`` を渡す場合は ``Filing.submit_date_time`` と
                同じく JST naive datetime で渡すこと。

        Returns:
            cutoff 時点で入手可能だった最新版 Filing。

        Raises:
            ValueError: cutoff 以前に提出された Filing が存在しない場合。

        利用例:
            >>> chain = build_revision_chain(filing, filings=all_filings)
            >>> # date で日付単位の指定（その日の終わりとして扱う）
            >>> snapshot = chain.at_time(date(2025, 6, 1))
            >>> # datetime で時刻単位の指定も可能
            >>> snapshot = chain.at_time(datetime(2025, 6, 1, 15, 0))
        """
    def __len__(self) -> int:
        """チェーン長を返す（``len(chain)`` サポート）。"""
    def __iter__(self) -> Iterator[Filing]:
        """チェーン内の Filing を iterate する。"""
    def __getitem__(self, index: int) -> Filing:
        """インデックスで Filing にアクセスする。"""

def build_revision_chain(filing: Filing, *, filings: list[Filing] | None = None) -> RevisionChain:
    '''Filing から訂正チェーンを構築する。

    原本でも訂正版でも、どの Filing から呼んでも同じ
    ``RevisionChain`` が構築される。

    Args:
        filing: 起点となる Filing（原本でも訂正版でも可）。
        filings: 検索対象の Filing リスト。省略時は
            ``filing.company.get_filings()`` で同一提出者の Filing を
            API から取得する。事前に取得済みのデータがある場合は
            渡すことで API 呼び出しを削減できる。

    Returns:
        ``RevisionChain``。訂正がない場合はチェーン長 1（原本のみ）。

    Raises:
        ValueError: ``filing`` の ``edinet_code`` が None で
            ``filings`` も未指定の場合（API 検索不可能）。

    Note:
        ``filings`` を省略すると EDINET API を日次で呼び出すため、
        30〜365 日分の API コールが発生します（目安: 30 日 → 約 30 秒、
        365 日 → 約 6 分）。バッチ処理では事前取得した Filing リスト
        を ``filings`` 引数に渡すことを強く推奨します。

    利用例:
        >>> # 推奨: 事前取得データを渡す（API 呼び出しなし）
        >>> all_filings = company.get_filings(start="2025-01-01", end="2025-12-31")
        >>> chain = build_revision_chain(filing, filings=all_filings)

        >>> # 利用可能だが低速（API コールが発生）
        >>> chain = build_revision_chain(filing)
        >>> print(chain.original.doc_id)
        >>> print(chain.latest.doc_id)
        >>> print(chain.count)
    '''

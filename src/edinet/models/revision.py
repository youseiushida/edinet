"""訂正報告書チェーンの構築・走査。

EDINET の訂正報告書（訂正有価証券報告書等）は全体再提出方式であり、
``parent_doc_id`` で原本を参照する。本モジュールは原本と全訂正版を
時系列で連結した ``RevisionChain`` を提供する。

利用例:
    >>> from edinet.models.revision import build_revision_chain
    >>> chain = build_revision_chain(filing)
    >>> chain.original.doc_id
    'S100ABC0'
    >>> chain.latest.doc_id
    'S100DEF2'
    >>> chain.count
    3
    >>> chain.is_corrected
    True

    バックテスト用の時点指定（date でも datetime でも可）:
    >>> from datetime import date
    >>> snapshot = chain.at_time(date(2025, 6, 1))
    >>> snapshot.doc_id  # 2025-06-01 時点で入手可能だった最新版
    'S100BCD1'
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.models.filing import Filing

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RevisionChain
# ---------------------------------------------------------------------------


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
        if len(self.chain) == 0:
            msg = "RevisionChain のチェーンが空です"
            raise ValueError(msg)
        # submit_date_time の昇順でソートされていることを検証
        for i in range(len(self.chain) - 1):
            if self.chain[i].submit_date_time > self.chain[i + 1].submit_date_time:
                msg = (
                    f"chain は submit_date_time の昇順でなければなりません "
                    f"(chain[{i}]={self.chain[i].submit_date_time} > "
                    f"chain[{i + 1}]={self.chain[i + 1].submit_date_time})"
                )
                raise ValueError(msg)

    @property
    def original(self) -> Filing:
        """チェーンの先頭（最も古い）Filing を返す。

        通常は原本（``parent_doc_id is None``）。ただし原本が
        検索範囲外（365 日超前）で発見できなかった場合は、最古の
        訂正版が返る可能性がある。

        Returns:
            チェーン先頭の Filing。
        """
        return self.chain[0]

    @property
    def latest(self) -> Filing:
        """最新版 Filing を返す。

        チェーンの末尾要素（``submit_date_time`` が最も新しい Filing）。
        訂正がない場合は原本と同一。

        Returns:
            最新版 Filing。
        """
        return self.chain[-1]

    @property
    def is_corrected(self) -> bool:
        """訂正があるかどうかを返す。

        チェーン長が 2 以上なら訂正あり。

        Returns:
            訂正ありなら True。
        """
        return len(self.chain) > 1

    @property
    def count(self) -> int:
        """チェーン長（原本を含む）を返す。

        Returns:
            チェーン内の Filing 数。
        """
        return len(self.chain)

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
        # date → datetime 変換（その日の終わりとして扱う）
        if isinstance(cutoff, date) and not isinstance(cutoff, datetime):
            cutoff = datetime(cutoff.year, cutoff.month, cutoff.day, 23, 59, 59)
        candidates = [f for f in self.chain if f.submit_date_time <= cutoff]
        if not candidates:
            msg = (
                f"cutoff {cutoff} 以前に提出された Filing がありません "
                f"(チェーン最古の提出日: {self.chain[0].submit_date_time})"
            )
            raise ValueError(msg)
        # chain は時系列順なので candidates[-1] が最新
        return candidates[-1]

    def __repr__(self) -> str:
        """デバッグ用の文字列表現。"""
        original_id = self.chain[0].doc_id
        latest_id = self.chain[-1].doc_id
        return (
            f"RevisionChain(original={original_id!r}, "
            f"latest={latest_id!r}, count={self.count})"
        )

    def __len__(self) -> int:
        """チェーン長を返す（``len(chain)`` サポート）。"""
        return self.count

    def __iter__(self) -> Iterator[Filing]:
        """チェーン内の Filing を iterate する。"""
        return iter(self.chain)

    def __getitem__(self, index: int) -> Filing:
        """インデックスで Filing にアクセスする。"""
        return self.chain[index]


# ---------------------------------------------------------------------------
# build_revision_chain
# ---------------------------------------------------------------------------


def build_revision_chain(
    filing: Filing,
    *,
    filings: list[Filing] | None = None,
) -> RevisionChain:
    """Filing から訂正チェーンを構築する。

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
    """
    # Step 1: 原本の doc_id を特定
    original_doc_id = _resolve_original_doc_id(filing)

    # Step 2: 検索対象の Filing リストを取得
    if filings is None:
        filings = _fetch_related_filings(filing, original_doc_id)

    # Step 3: 同一原本に属する Filing を収集 + フィルタリング
    chain_filings = _collect_chain_members(
        original_doc_id=original_doc_id,
        filings=filings,
        seed_filing=filing,
    )

    # Step 4: submit_date_time でソート
    chain_filings.sort(key=lambda f: f.submit_date_time)

    return RevisionChain(chain=tuple(chain_filings))


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _resolve_original_doc_id(filing: Filing) -> str:
    """Filing の原本 doc_id を返す。

    ``parent_doc_id`` が None の場合は Filing 自身が原本。
    ``parent_doc_id`` が非 None の場合はそれが原本の doc_id。

    Args:
        filing: 対象の Filing。

    Returns:
        原本の doc_id。
    """
    if filing.parent_doc_id is None:
        return filing.doc_id
    return filing.parent_doc_id


_SHORT_LOOKBACK_DAYS = 30
"""第 1 段階の検索範囲（日数）。訂正報告書の多くは原本から 30 日以内に提出される。"""

_LONG_LOOKBACK_DAYS = 365
"""第 2 段階の検索範囲（日数）。30 日以内に原本が見つからない場合に拡大する。"""


def _fetch_related_filings(
    filing: Filing,
    original_doc_id: str,
) -> list[Filing]:
    """API から同一提出者の Filing リストを取得する（2 段階検索）。

    訂正報告書は原本の数日後〜数ヶ月後に提出されるため、固定の検索範囲
    では原本を見逃す可能性がある。本関数は 2 段階で検索する:

    第 1 段階: 起点 Filing の提出日 - 30 日 〜 今日
        多くの訂正は原本から 30 日以内に提出されるため、まずこの範囲で試行。
        原本（``doc_id == original_doc_id``）が見つかれば即座に返す。

    第 2 段階: 起点 Filing の提出日 - 365 日 〜 (第 1 段階の start - 1 日)
        第 1 段階で原本が見つからなかった場合に拡大検索する。
        第 1 段階の結果と結合して返す。

    Note:
        ``Company.get_filings()`` は内部で ``documents()`` を呼び出し、
        ``documents()`` は ``start`` と ``end`` の **両方** を必須とする
        （片方のみ指定すると ``ValueError``）。そのため ``start`` と
        ``end`` を常に明示的に渡す。

        第 2 段階でも原本が見つからない場合（原本が 365 日超前に
        提出されたケース）、``_collect_chain_members`` が seed_filing
        のみでチェーンを構築する。

    Args:
        filing: 起点となる Filing。
        original_doc_id: 原本の doc_id（第 1 段階で原本の有無を判定するため）。

    Returns:
        同一提出者の Filing リスト。

    Raises:
        ValueError: ``filing.edinet_code`` が None の場合。
    """
    from datetime import timedelta

    from edinet.models.company import _today_jst

    company = filing.company
    if company is None:
        msg = (
            f"Filing {filing.doc_id!r} の edinet_code が None のため、"
            "関連 Filing を API から取得できません。"
            "filings 引数を指定してください。"
        )
        raise ValueError(msg)

    base_date = filing.submit_date_time.date()
    today = _today_jst()

    # --- 第 1 段階: 30 日ルックバック ---
    short_start = base_date - timedelta(days=_SHORT_LOOKBACK_DAYS)
    filings_short: list[Filing] = company.get_filings(start=short_start, end=today)

    # 原本が第 1 段階で見つかれば即返却
    if any(f.doc_id == original_doc_id for f in filings_short):
        return filings_short

    # 入力 Filing 自身が原本の場合（parent_doc_id=None）も即返却
    if filing.parent_doc_id is None:
        return filings_short

    # --- 第 2 段階: 365 日まで拡大 ---
    logger.info(
        "原本 %s が直近 %d 日以内に見つかりません。"
        "検索範囲を %d 日に拡大します。",
        original_doc_id,
        _SHORT_LOOKBACK_DAYS,
        _LONG_LOOKBACK_DAYS,
    )
    long_start = base_date - timedelta(days=_LONG_LOOKBACK_DAYS)
    long_end = short_start - timedelta(days=1)
    filings_long: list[Filing] = company.get_filings(start=long_start, end=long_end)

    if not any(f.doc_id == original_doc_id for f in filings_long):
        logger.warning(
            "原本 %s が %d 日間の検索範囲内に見つかりません。"
            "原本が %d 日超前に提出された可能性があります。",
            original_doc_id,
            _LONG_LOOKBACK_DAYS,
            _LONG_LOOKBACK_DAYS,
        )

    return filings_short + filings_long


def _collect_chain_members(
    *,
    original_doc_id: str,
    filings: list[Filing],
    seed_filing: Filing,
) -> list[Filing]:
    """原本と訂正版を収集する。

    以下の条件のいずれかを満たす Filing を収集:
    1. ``doc_id == original_doc_id``（原本自身）
    2. ``parent_doc_id == original_doc_id``（訂正版）

    取下げ済み（``withdrawal_status != "0"``）の Filing は除外する。

    ``seed_filing`` は ``filings`` リストに含まれていない場合に備えて
    明示的にチェックされる。

    Args:
        original_doc_id: 原本の doc_id。
        filings: 検索対象の Filing リスト。
        seed_filing: 起点の Filing（filings に含まれていない場合の保険）。

    Returns:
        チェーンに含まれる Filing のリスト（未ソート）。
    """
    seen_doc_ids: set[str] = set()
    chain_members: list[Filing] = []

    # filings リストから収集
    for f in filings:
        if f.doc_id in seen_doc_ids:
            continue
        if not _belongs_to_chain(f, original_doc_id):
            continue
        if not _is_active(f):
            logger.debug(
                "取下げ済み Filing を除外: %s (withdrawal_status=%s)",
                f.doc_id,
                f.withdrawal_status,
            )
            continue
        seen_doc_ids.add(f.doc_id)
        chain_members.append(f)

    # seed_filing が filings に含まれていなかった場合の保険
    if seed_filing.doc_id not in seen_doc_ids and _is_active(seed_filing):
        chain_members.append(seed_filing)
        seen_doc_ids.add(seed_filing.doc_id)

    # 原本すら見つからなかった場合（filings に原本が含まれていない）
    if not chain_members:
        # seed_filing を唯一のメンバーとして返す
        # （取下げ済みの場合も含める。チェーンが空になるのを防ぐ）
        logger.warning(
            "原本 %s が filings リスト内に見つかりません。"
            "起点 Filing %s のみでチェーンを構築します。",
            original_doc_id,
            seed_filing.doc_id,
        )
        chain_members.append(seed_filing)

    return chain_members


def _belongs_to_chain(filing: Filing, original_doc_id: str) -> bool:
    """Filing が指定された原本のチェーンに属するか判定する。

    Args:
        filing: 判定対象の Filing。
        original_doc_id: 原本の doc_id。

    Returns:
        チェーンに属する場合は True。
    """
    # 原本自身
    if filing.doc_id == original_doc_id:
        return True
    # 訂正版（parent_doc_id が原本を指す）
    if filing.parent_doc_id == original_doc_id:
        return True
    return False


def _is_active(filing: Filing) -> bool:
    """Filing が有効（取下げなし）かどうかを返す。

    EDINET API の ``withdrawalStatus`` は以下の 3 値を取る:
    - ``"0"``: 取下げなし（有効）
    - ``"1"``: 取下書が提出された
    - ``"2"``: 取り消し済み（親書類の取下げにより連動で無効化）

    ``"1"`` と ``"2"`` の両方を除外するために ``== "0"`` で判定する。

    Args:
        filing: 判定対象の Filing。

    Returns:
        ``withdrawal_status == "0"`` なら True。
    """
    return filing.withdrawal_status == "0"

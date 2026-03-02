"""訂正報告書チェーン（revision_chain）のテスト。

RevisionChain dataclass と build_revision_chain() 関数の外部的な
振る舞いをテストする。テスト内では Filing を直接インスタンス化し、
API 呼び出しは行わない（全テストで filings 引数を明示的に渡す）。
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from edinet.models.filing import Filing
from edinet.models.revision import RevisionChain, build_revision_chain


# ---------------------------------------------------------------------------
# テストヘルパー
# ---------------------------------------------------------------------------


def _make_filing(
    *,
    doc_id: str,
    parent_doc_id: str | None = None,
    submit_date_time: datetime | None = None,
    withdrawal_status: str = "0",
    edinet_code: str | None = "E00001",
    doc_type_code: str | None = "120",
) -> Filing:
    """テスト用の Filing を作成する。"""
    if submit_date_time is None:
        submit_date_time = datetime(2025, 4, 1, 10, 0, 0)
    return Filing(
        seq_number=1,
        doc_id=doc_id,
        doc_type_code=doc_type_code,
        ordinance_code="010",
        form_code="030000",
        edinet_code=edinet_code,
        sec_code=None,
        jcn=None,
        filer_name="テスト株式会社",
        fund_code=None,
        submit_date_time=submit_date_time,
        period_start=None,
        period_end=None,
        doc_description="有価証券報告書",
        issuer_edinet_code=None,
        subject_edinet_code=None,
        subsidiary_edinet_code=None,
        current_report_reason=None,
        parent_doc_id=parent_doc_id,
        ope_date_time=None,
        withdrawal_status=withdrawal_status,
        doc_info_edit_status="0",
        disclosure_status="0",
        has_xbrl=True,
        has_pdf=True,
        has_attachment=False,
        has_english=False,
        has_csv=False,
        legal_status="0",
    )


# ---------------------------------------------------------------------------
# RevisionChain プロパティ
# ---------------------------------------------------------------------------


class TestRevisionChainProperties:
    """RevisionChain の基本プロパティのテスト。"""

    def test_no_correction(self) -> None:
        """訂正なし: チェーン長 1、original == latest == 入力 filing。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        assert chain.count == 1
        assert chain.original is original
        assert chain.latest is original
        assert not chain.is_corrected

    def test_single_correction(self) -> None:
        """1 回訂正: チェーン長 2。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(original, filings=[original, corrected])
        assert chain.count == 2
        assert chain.original.doc_id == "S100A"
        assert chain.latest.doc_id == "S100B"
        assert chain.is_corrected

    def test_multiple_corrections(self) -> None:
        """複数回訂正: チェーン長 3+。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corr1 = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        corr2 = _make_filing(
            doc_id="S100C",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 5, 1),
        )
        chain = build_revision_chain(
            original, filings=[original, corr1, corr2]
        )
        assert chain.count == 3
        assert chain.original.doc_id == "S100A"
        assert chain.latest.doc_id == "S100C"

    def test_original_property(self) -> None:
        """original プロパティは chain[0] を返す。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        assert chain.original is chain.chain[0]

    def test_latest_property(self) -> None:
        """latest プロパティは chain[-1] を返す。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            corrected, filings=[original, corrected]
        )
        assert chain.latest is chain.chain[-1]

    def test_is_corrected_true(self) -> None:
        """is_corrected: 訂正ありの場合 True。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        assert chain.is_corrected is True

    def test_is_corrected_false(self) -> None:
        """is_corrected: 訂正なしの場合 False。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        assert chain.is_corrected is False

    def test_count_property(self) -> None:
        """count プロパティがチェーン長を返す。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corr1 = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            original, filings=[original, corr1]
        )
        assert chain.count == 2
        assert len(chain) == 2

    def test_empty_chain_raises_value_error(self) -> None:
        """空の chain で RevisionChain を構築すると ValueError。"""
        with pytest.raises(ValueError, match="空"):
            RevisionChain(chain=())

    def test_repr(self) -> None:
        """__repr__ がクラッシュせず有用な情報を含む。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        r = repr(chain)
        assert "S100A" in r
        assert "S100B" in r
        assert "count=2" in r


# ---------------------------------------------------------------------------
# at_time()
# ---------------------------------------------------------------------------


class TestAtTime:
    """at_time() メソッドのテスト（バックテスト用途）。"""

    def test_at_time_returns_latest_before_cutoff(self) -> None:
        """cutoff 以前の最新版を返す。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corr1 = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        corr2 = _make_filing(
            doc_id="S100C",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 5, 1),
        )
        chain = build_revision_chain(
            original, filings=[original, corr1, corr2]
        )
        # 第 1 回訂正直後・第 2 回訂正前の時点
        snapshot = chain.at_time(datetime(2025, 4, 20))
        assert snapshot.doc_id == "S100B"

    def test_at_time_returns_original_before_any_correction(self) -> None:
        """全訂正版より前の cutoff では原本を返す。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        snapshot = chain.at_time(datetime(2025, 4, 10))
        assert snapshot.doc_id == "S100A"

    def test_at_time_returns_latest_when_cutoff_is_after_all(self) -> None:
        """全 Filing より後の cutoff では latest と同じ。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        snapshot = chain.at_time(datetime(2025, 12, 31))
        assert snapshot.doc_id == "S100B"
        assert snapshot is chain.latest

    def test_at_time_accepts_date_object(self) -> None:
        """date オブジェクトを渡すとその日の終わりとして扱う。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1, 10, 0, 0),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15, 14, 30, 0),
        )
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        # date(2025, 4, 15) → 23:59:59 扱い → 14:30 提出の訂正版を含む
        snapshot = chain.at_time(date(2025, 4, 15))
        assert snapshot.doc_id == "S100B"

    def test_at_time_date_excludes_next_day(self) -> None:
        """date で前日を指定すると翌日提出の Filing は含まれない。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1, 10, 0, 0),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15, 14, 30, 0),
        )
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        # date(2025, 4, 14) → 23:59:59 扱い → 4/15 提出の訂正版は含まない
        snapshot = chain.at_time(date(2025, 4, 14))
        assert snapshot.doc_id == "S100A"

    def test_at_time_raises_when_cutoff_before_original(self) -> None:
        """原本より前の cutoff では ValueError。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        chain = build_revision_chain(original, filings=[original])
        with pytest.raises(ValueError, match="以前に提出された Filing がありません"):
            chain.at_time(datetime(2025, 3, 1))


# ---------------------------------------------------------------------------
# build_revision_chain()
# ---------------------------------------------------------------------------


class TestBuildRevisionChain:
    """build_revision_chain() 関数のテスト。"""

    def test_from_corrected_filing(self) -> None:
        """訂正版から構築しても正しいチェーンが得られる。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        # 訂正版から構築
        chain = build_revision_chain(
            corrected, filings=[original, corrected]
        )
        assert chain.original.doc_id == "S100A"
        assert chain.latest.doc_id == "S100B"
        assert chain.count == 2

    def test_chain_is_sorted_by_submission_date(self) -> None:
        """chain は submit_date_time の昇順でソートされている。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corr1 = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 5, 1),
        )
        corr2 = _make_filing(
            doc_id="S100C",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        # 意図的に順序をバラバラにして渡す
        chain = build_revision_chain(
            original, filings=[corr2, original, corr1]
        )
        for i in range(len(chain.chain) - 1):
            assert (
                chain.chain[i].submit_date_time
                <= chain.chain[i + 1].submit_date_time
            )

    def test_withdrawn_filing_excluded(self) -> None:
        """取下げ済み Filing はチェーンから除外される。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        withdrawn = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
            withdrawal_status="1",  # 取下げ済み
        )
        valid_corr = _make_filing(
            doc_id="S100C",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 5, 1),
        )
        chain = build_revision_chain(
            original, filings=[original, withdrawn, valid_corr]
        )
        assert chain.count == 2
        doc_ids = [f.doc_id for f in chain.chain]
        assert "S100B" not in doc_ids
        assert "S100A" in doc_ids
        assert "S100C" in doc_ids

    def test_cascaded_withdrawal_excluded(self) -> None:
        """連動取下げ (withdrawal_status='2') もチェーンから除外される。

        親書類が取下げられると子書類は自動的に
        withdrawal_status='2' になる。'1'（明示的取下げ）だけでなく
        '2'（連動無効化）も除外されることを確認する。
        """
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        cascaded = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
            withdrawal_status="2",  # 連動取下げ
        )
        valid_corr = _make_filing(
            doc_id="S100C",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 5, 1),
        )
        chain = build_revision_chain(
            original, filings=[original, cascaded, valid_corr]
        )
        assert chain.count == 2
        doc_ids = [f.doc_id for f in chain.chain]
        assert "S100B" not in doc_ids
        assert "S100A" in doc_ids
        assert "S100C" in doc_ids

    def test_filings_argument_avoids_api(self) -> None:
        """filings 引数を渡すと API 呼び出しなしでチェーンを構築。"""
        original = _make_filing(
            doc_id="S100A",
            edinet_code=None,  # edinet_code=None → API 不可能
        )
        # filings を渡すので ValueError にならない
        chain = build_revision_chain(original, filings=[original])
        assert chain.count == 1

    def test_no_filings_no_edinet_code_raises(self) -> None:
        """filings 未指定 + edinet_code=None の場合は ValueError。"""
        filing = _make_filing(doc_id="S100A", edinet_code=None)
        with pytest.raises(ValueError, match="edinet_code"):
            build_revision_chain(filing)

    def test_unrelated_filings_ignored(self) -> None:
        """チェーンに無関係な Filing は無視される。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        unrelated = _make_filing(
            doc_id="S100X",
            submit_date_time=datetime(2025, 4, 2),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            original, filings=[original, unrelated, corrected]
        )
        assert chain.count == 2
        doc_ids = [f.doc_id for f in chain.chain]
        assert "S100X" not in doc_ids


# ---------------------------------------------------------------------------
# エッジケース
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_same_submit_date_time_stable_sort(self) -> None:
        """同一 submit_date_time の Filing がある場合、ソートが安定。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corr1 = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15, 10, 0),
        )
        corr2 = _make_filing(
            doc_id="S100C",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15, 10, 0),  # 同一時刻
        )
        chain = build_revision_chain(
            original, filings=[original, corr1, corr2]
        )
        assert chain.count == 3
        # ソートが例外を出さないことを検証
        for i in range(len(chain.chain) - 1):
            assert (
                chain.chain[i].submit_date_time
                <= chain.chain[i + 1].submit_date_time
            )

    def test_original_not_in_filings_seed_only(self) -> None:
        """filings に原本が含まれず seed_filing のみでチェーン構築。

        365日超前に原本が提出されたケースを模擬。
        """
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        # filings に原本 S100A が含まれていない
        chain = build_revision_chain(
            corrected, filings=[corrected]
        )
        assert chain.count == 1
        assert chain.original.doc_id == "S100B"  # 訂正版が original になる
        assert not chain.is_corrected

    def test_post_init_rejects_unsorted_chain(self) -> None:
        """ソートされていない chain で直接構築すると ValueError。"""
        f1 = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        f2 = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        with pytest.raises(ValueError, match="昇順"):
            RevisionChain(chain=(f1, f2))

    def test_duplicate_filings_deduplicated(self) -> None:
        """filings に同一 doc_id が重複していても重複排除される。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        # 同一 Filing を複数回渡す
        chain = build_revision_chain(
            original, filings=[original, corrected, original, corrected]
        )
        assert chain.count == 2

    def test_seed_filing_not_in_filings_list(self) -> None:
        """filings に入力 filing が含まれていない場合も正しく構築。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        # filings に corrected が含まれていないが、seed_filing として追加される
        chain = build_revision_chain(
            corrected, filings=[original]
        )
        assert chain.count == 2
        assert chain.original.doc_id == "S100A"
        assert chain.latest.doc_id == "S100B"

    def test_all_filings_withdrawn_falls_back_to_seed(self) -> None:
        """全 Filing が取下げ済みの場合、seed_filing でチェーン構築。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
            withdrawal_status="1",
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
            withdrawal_status="1",
        )
        # seed_filing も取下げ済みだが、チェーンが空になるのを防ぐ
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        assert chain.count == 1

    def test_empty_filings_list_uses_seed(self) -> None:
        """空の filings リストでも seed_filing でチェーン構築。"""
        filing = _make_filing(doc_id="S100A")
        chain = build_revision_chain(filing, filings=[])
        assert chain.count == 1
        assert chain.original.doc_id == "S100A"


# ---------------------------------------------------------------------------
# イテレーションプロトコル
# ---------------------------------------------------------------------------


class TestRevisionChainIteration:
    """RevisionChain のイテレーションプロトコルのテスト。"""

    def test_iter(self) -> None:
        """RevisionChain は iterate 可能。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        filings_list = list(chain)
        assert len(filings_list) == 1
        assert filings_list[0] is original

    def test_getitem(self) -> None:
        """RevisionChain はインデックスアクセス可能。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corrected = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        chain = build_revision_chain(
            original, filings=[original, corrected]
        )
        assert chain[0].doc_id == "S100A"
        assert chain[1].doc_id == "S100B"

    def test_len(self) -> None:
        """len() がチェーン長を返す。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        corr1 = _make_filing(
            doc_id="S100B",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 4, 15),
        )
        corr2 = _make_filing(
            doc_id="S100C",
            parent_doc_id="S100A",
            submit_date_time=datetime(2025, 5, 1),
        )
        chain = build_revision_chain(
            original, filings=[original, corr1, corr2]
        )
        assert len(chain) == 3

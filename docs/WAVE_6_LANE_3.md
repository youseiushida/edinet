# Wave 6 / Lane 3 — revision_chain: 訂正報告書チェーンの構築

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 6 / Lane 3 を担当するエージェントです。
担当機能: revision_chain（訂正報告書チェーンの構築・走査）

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/models/revision.py` (新規)
   - `tests/test_models/test_revision.py` (新規)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - 既存の dataclass / class にフィールドを追加する場合は必ずデフォルト値を付与すること
   - 既存のフィールド名・型・関数シグネチャを変更してはならない
   - 既存の定数名を変更・削除してはならない（追加のみ可）

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリを作成すること

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.models.revision import build_revision_chain, RevisionChain` （OK）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_models/test_revision.py` に作成

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 5 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.models.filing` (Filing)
     - `edinet.models.company` (Company)
     - `edinet.models.doc_types` (DocType)
     - `edinet.exceptions` (EdinetError 等)
   - **L2（cache）が作成中の `api/cache.py` に依存してはならない**

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果を報告すること

---

# LANE 3 — revision_chain: 訂正報告書チェーンの構築

## 0. 位置づけ

### FEATURES.md との対応

Wave 6 Lane 3 は、FEATURES.md の **Revision Chain** セクションに対応する。EDINET の訂正報告書メカニズムを表現する `RevisionChain` dataclass と、チェーン構築関数 `build_revision_chain()` を提供する。FEATURES.md が明示する `latest()` と `at_time(date)` の両方を実装し、SCOPE.md の「訂正チェーンの解決（latest / at_time）」を満たす。

### 設計決定事項

| 決定 | 内容 | 根拠 |
|------|------|------|
| D4 | `build_revision_chain()` は standalone 関数 | 複数の入力（Filing + filings リスト）を組み合わせる処理、API 呼び出しを伴う |
| D4 | `RevisionChain.original` / `.latest` / `.at_time()` はプロパティ/メソッド | 単一属性の派生値、バックテスト用途 |
| D5 | `build_*` = 構築（raise 可）→ `RevisionChain` を返す | 命名規約 |
| D3 | Filing にフィールドを追加しない | God Object 防止。`filing.py` は L2（cache）の管轄 |

### WAVE_6.md での衝突管理

> L2 と L3: 元計画では両方 `filing.py` を変更するが、**L3 は `revision.py` に standalone 関数 `build_revision_chain()` として実装**し `filing.py` を触らない。統合タスクで `Filing.revisions()` メソッドを追加。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.models.filing` | `Filing` クラス（read-only） | read-only |
| `edinet.models.company` | `Company.get_filings()` 経由で同一提出者の Filing を取得 | read-only |
| `edinet.models.doc_types` | `DocType.is_correction` で訂正報告書を判定 | read-only |

他レーンとのファイル衝突なし（全て新規ファイル作成）。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| G-7 | **直接** | 訂正報告書のメカニズム全般 |
| D4 | 直接 | standalone 関数配置の決定 |
| D5 | 直接 | `build_*` 命名規約 |

---

## 1. 背景知識

### 1.1 EDINET の訂正報告書メカニズム（G-7.a.md より）

EDINET の訂正報告書には以下の特性がある:

#### 1. 全体再提出方式

訂正報告書は**全体を再提出**する方式であり、差分ではない。つまり、訂正後の完全な書類が新たに提出される。

#### 2. parent_doc_id は常に原本を指す

```
原本          (doc_id=S100A, parent_doc_id=None)
  ↑
  第 1 回訂正  (doc_id=S100B, parent_doc_id=S100A)  ← 原本を指す
  ↑
  第 2 回訂正  (doc_id=S100C, parent_doc_id=S100A)  ← 原本を指す（直前の訂正ではない！）
```

**重要**: `parent_doc_id` は直前の訂正ではなく、**常に原本の `doc_id`** を指す。これはチェーン走査の実装に直接影響する。

#### 3. NumberOfSubmissionDEI

DEI の `NumberOfSubmission` が提出回数を示す:
- 原本: `1`
- 第 1 回訂正: `2`
- 第 2 回訂正: `3`

#### 4. withdrawal_status

`Filing.withdrawal_status` で取下げ状態を判定:
- `"0"`: 取下げなし（有効）
- `"1"`: 取下げ済み
- `"2"`: 取り消し済み

#### 5. is_correction

`DocType.is_correction` プロパティで訂正報告書かどうかを判定可能。

### 1.2 Filing の関連フィールド（既存）

```python
class Filing(BaseModel):
    doc_id: str                        # 書類管理番号（一意）
    parent_doc_id: str | None          # 原本の doc_id（訂正の場合のみ）
    submit_date_time: datetime         # 提出日時
    withdrawal_status: str             # "0"=有効, "1"=取下げ, "2"=取消し
    edinet_code: str | None            # 提出者 EDINET コード
    doc_type_code: str | None          # 書類種別コード

    @computed_field
    @property
    def doc_type(self) -> DocType | None: ...

    @property
    def company(self) -> Company | None: ...
```

### 1.3 チェーン構築のアルゴリズム

入力: 1 つの Filing（原本でも訂正版でも可）
出力: `RevisionChain`（原本 + 全訂正版の時系列順タプル）

```
Step 1: 入力 Filing の原本 doc_id を特定
        - parent_doc_id が None → 入力自身が原本
        - parent_doc_id が非 None → parent_doc_id が原本の doc_id

Step 2: 同一原本に属する Filing 群を収集
        - filings 引数が提供されている場合はそこから検索
        - 提供されていない場合は Company.get_filings() で取得

Step 3: フィルタリング
        - original_doc_id == doc_id の Filing（原本自身）
        - parent_doc_id == original_doc_id の Filing（訂正版）
        - withdrawal_status == "0" の Filing のみ（取下げ済みを除外）

Step 4: submit_date_time でソート → chain タプルを構築
```

---

## 2. ゴール

1. `RevisionChain` frozen dataclass — 訂正チェーン全体を表現
2. `build_revision_chain(filing, *, filings=None) -> RevisionChain` — standalone 構築関数
3. `RevisionChain.original` — 原本 Filing
4. `RevisionChain.latest` — 最新版 Filing
5. `RevisionChain.at_time(cutoff)` — 指定時点で入手可能だった最新版 Filing（バックテスト用）
6. `RevisionChain.chain` — 時系列順の全 Filing タプル
7. `RevisionChain.is_corrected` — 訂正ありかどうか
8. `RevisionChain.count` — チェーン長

完了条件:

```python
from edinet.models.revision import build_revision_chain, RevisionChain

# 訂正なしの Filing
chain = build_revision_chain(original_filing, filings=all_filings)
assert chain.count == 1
assert chain.original is original_filing
assert chain.latest is original_filing
assert not chain.is_corrected

# 訂正ありの Filing（第 2 回訂正から構築）
chain = build_revision_chain(corrected_filing, filings=all_filings)
assert chain.count == 3  # 原本 + 第 1 回 + 第 2 回
assert chain.original.parent_doc_id is None
assert chain.latest.submit_date_time >= chain.original.submit_date_time
assert chain.is_corrected

# chain は submit_date_time 順
for i in range(len(chain.chain) - 1):
    assert chain.chain[i].submit_date_time <= chain.chain[i + 1].submit_date_time

# at_time: バックテスト用の時点指定（date でも datetime でも可）
from datetime import date, datetime
chain = build_revision_chain(corrected_filing, filings=all_filings)
# date で日付単位の指定
snapshot = chain.at_time(date(2025, 4, 20))
assert snapshot.doc_id == chain.chain[1].doc_id  # 第 1 回訂正まで
# datetime で時刻単位の指定も可能
snapshot2 = chain.at_time(datetime(2025, 4, 20, 12, 0))
```

---

## 3. スコープ / 非スコープ

### 3.1 スコープ

| # | 内容 |
|---|------|
| S1 | `RevisionChain` frozen dataclass |
| S2 | `build_revision_chain()` standalone 関数 |
| S3 | 原本から構築 |
| S4 | 訂正版から構築（原本を自動的に遡る） |
| S5 | 取下げ済み Filing の除外 |
| S6 | `filings` 引数による事前取得データの活用（API 呼び出し削減） |
| S7 | エッジケース: 原本のみ（訂正なし）、複数回訂正、取下げ |
| S8 | `RevisionChain.at_time(cutoff)` — バックテスト用の時点指定取得（FEATURES.md / SCOPE.md 要件） |

### 3.2 非スコープ

| # | 内容 | 理由 |
|---|------|------|
| N1 | `Filing.revisions()` メソッドの追加 | `filing.py` は L2（cache）管轄。統合タスクで追加 |
| N2 | DEI の `amendment_flag` / `number_of_submission` の検証 | XBRL パースが必要。本 Lane は Filing メタデータのみで完結 |
| N3 | 訂正前後の差分検出 | 全体再提出方式のため、差分は Statements レベルで比較が必要 |
| N4 | 非同期版 `abuild_revision_chain()` | v0.1.0 では不要。`filings` 引数で API 呼び出しを回避する設計 |
| N5 | 訂正理由（`current_report_reason`）の抽出 | Filing フィールドに存在するが、RevisionChain の責務外 |

---

## 4. 実装計画

### 4.1 revision.py（新規）

```python
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
```

### 4.2 RevisionChain dataclass

```python
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

        FEATURES.md:
            「バックテスト向けに ``at_time(date)`` で指定時点で入手可能
            だった版を取得可能にする（submit_date_time <= cutoff のフィルタ）」

        SCOPE.md:
            「訂正チェーンの解決（latest / at_time）」

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
        candidates = [
            f for f in self.chain if f.submit_date_time <= cutoff
        ]
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
```

### 4.3 build_revision_chain() 関数

```python
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
```

### 4.4 内部ヘルパー関数

```python
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

    注意:
        ``Company.get_filings()`` は内部で ``documents()`` を呼び出し、
        ``documents()`` は ``start`` と ``end`` の**両方**を必須とする
        （片方のみ指定すると ``ValueError``）。そのため ``start`` と
        ``end`` を常に明示的に渡す。

        第 2 段階でも原本が見つからない場合（原本が 365 日超前に
        提出されたケース）、``_collect_chain_members`` が seed_filing
        のみでチェーンを構築する。この場合 ``RevisionChain.original``
        は訂正版を返す。

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
    filings_short = company.get_filings(start=short_start, end=today)

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
    filings_long = company.get_filings(start=long_start, end=long_end)

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

    seed_filing は filings リストに含まれていない場合に備えて
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
    if seed_filing.doc_id not in seen_doc_ids:
        if _is_active(seed_filing):
            chain_members.append(seed_filing)
            seen_doc_ids.add(seed_filing.doc_id)

    # 原本すら見つからなかった場合（filings に原本が含まれていない）
    if not chain_members:
        # seed_filing を唯一のメンバーとして返す
        # （取下げ済みの場合も含める。チェーンが空になるのを防ぐ）
        logger.warning(
            "原本 %s がfilingsリスト内に見つかりません。"
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

    EDINET API の ``withdrawalStatus`` は以下の 3 値を取る（G-7.a.md §5）:
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
```

---

## 5. 実装の注意点

### 5.1 parent_doc_id の意味論

G-7.a.md で確認済み: `parent_doc_id` は**常に原本を指す**。直前の訂正版を指すのではない。

```
原本      (doc_id="A", parent_doc_id=None)
第 1 回訂正 (doc_id="B", parent_doc_id="A")     ← A を指す
第 2 回訂正 (doc_id="C", parent_doc_id="A")     ← A を指す（B ではない！）
```

この仕様により、チェーン構築は「同一の `parent_doc_id` を持つ Filing を収集する」だけでよい。ツリー走査は不要。

### 5.2 filings 引数の推奨と 2 段階検索

`filings` 引数を省略すると `_fetch_related_filings()` が `Company.get_filings(start=...)` を呼び、EDINET API に対して日ごとのリクエストが発生する（レート制限 1.0s/call）。

**2 段階検索の仕組み**:

訂正報告書は原本の数日後〜数ヶ月後に提出されるため、固定の短い検索範囲では原本を見逃す。`_fetch_related_filings()` は以下の 2 段階で検索する:

1. **第 1 段階** (30 日): 起点 Filing の提出日 - 30 日 〜 今日。多くの訂正はこの範囲で原本が見つかる。
2. **第 2 段階** (365 日): 第 1 段階で原本が見つからなかった場合のみ、起点 Filing の提出日 - 365 日 〜 (第 1 段階の start - 1 日) を追加検索。既に取得済みの範囲は重複しない。

```
例: 訂正報告書が 2025-11-15 に提出された場合

第 1 段階: 2025-10-16 〜 今日 → 原本なし → 第 2 段階へ
第 2 段階: 2024-11-15 〜 2025-10-15 → 原本 (2025-06-20) 発見！
```

**注意**: `Company.get_filings()` は内部で `documents()` を呼び出し、`documents()` は `start` と `end` の**両方が必須**（片方のみだと `ValueError`）。`_fetch_related_filings()` では `start` と `end` を常に明示的に渡す。

**365日超の限界**: 第 2 段階でも原本が見つからない場合（原本が 365 日超前に提出された極めてまれなケース）、`_collect_chain_members` が seed_filing のみでチェーンを構築する。この場合 `RevisionChain.original` は訂正版を返す。

バッチ処理では事前に取得した Filing リストを渡すことを推奨:

```python
# 推奨: 事前取得データを渡す（API 呼び出しなし）
all_filings = company.get_filings(start="2025-01-01", end="2025-12-31")
chain = build_revision_chain(filing, filings=all_filings)

# 利用可能だが低速（第 1 段階で最大 30 日分、第 2 段階で最大 335 日分の API コール）:
chain = build_revision_chain(filing)
```

### 5.3 seed_filing の保険

`filings` 引数に入力の `filing` 自身が含まれていない場合がある。例えば:
- ユーザーが期間を絞り込んで `get_filings()` を呼んだ
- 入力の `filing` がその期間外

この場合、`seed_filing` を明示的にチェーンに追加することで、少なくとも 1 つの Filing を持つ `RevisionChain` が返される。

### 5.4 取下げ済み Filing の扱い

`withdrawal_status != "0"` の Filing はチェーンから除外する。ただし、チェーンが完全に空になる（原本も取下げ済み）場合は、seed_filing を含めてチェーン長 1 で返す。

### 5.5 Filing の `filing.py` への依存（read-only）

本 Lane は `filing.py` を**変更しない**。`Filing` の既存フィールド（`doc_id`, `parent_doc_id`, `submit_date_time`, `withdrawal_status`, `edinet_code`）を読み取りのみで使用する。

統合タスクで `Filing.revisions()` メソッドを追加する際は以下のようになる（本 Lane の責務外）:

```python
# 統合タスクで追加（本 Lane では実装しない）
class Filing(BaseModel):
    def revisions(self, *, filings: list[Filing] | None = None) -> RevisionChain:
        from edinet.models.revision import build_revision_chain
        return build_revision_chain(self, filings=filings)
```

---

## 6. テスト計画

### 6.1 テストファイル

`tests/test_models/test_revision.py` に全テストを作成する。

### 6.2 テスト戦略

- Filing のモックオブジェクトを自前で作成する（Pydantic の `Filing` をインスタンス化）
- API 呼び出しは行わない（全テストで `filings` 引数を明示的に渡す）
- `Company.get_filings()` のモックは不要（`filings` 引数で回避）
- デトロイト派: RevisionChain の外部的な振る舞いのみをテスト

### 6.3 Filing テストヘルパー

テスト内で使用する Filing 作成ヘルパー:

```python
from datetime import datetime

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
```

### 6.4 テストケース一覧（~27 件）

```python
class TestRevisionChainProperties:
    def test_no_correction(self):
        """訂正なし: チェーン長 1、original == latest == 入力 filing。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        assert chain.count == 1
        assert chain.original is original
        assert chain.latest is original
        assert not chain.is_corrected

    def test_single_correction(self):
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

    def test_multiple_corrections(self):
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

    def test_original_property(self):
        """original プロパティは chain[0] を返す。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        assert chain.original is chain.chain[0]

    def test_latest_property(self):
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

    def test_is_corrected_true(self):
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

    def test_is_corrected_false(self):
        """is_corrected: 訂正なしの場合 False。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        assert chain.is_corrected is False

    def test_count_property(self):
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

    def test_empty_chain_raises_value_error(self):
        """空の chain で RevisionChain を構築すると ValueError。"""
        with pytest.raises(ValueError, match="空"):
            RevisionChain(chain=())

    def test_repr(self):
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


class TestAtTime:
    """at_time() メソッドのテスト（バックテスト用途）。"""

    def test_at_time_returns_latest_before_cutoff(self):
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

    def test_at_time_returns_original_before_any_correction(self):
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

    def test_at_time_returns_latest_when_cutoff_is_after_all(self):
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

    def test_at_time_accepts_date_object(self):
        """date オブジェクトを渡すとその日の終わりとして扱う。"""
        from datetime import date

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

    def test_at_time_date_excludes_next_day(self):
        """date で前日を指定すると翌日提出の Filing は含まれない。"""
        from datetime import date

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

    def test_at_time_raises_when_cutoff_before_original(self):
        """原本より前の cutoff では ValueError。"""
        original = _make_filing(
            doc_id="S100A",
            submit_date_time=datetime(2025, 4, 1),
        )
        chain = build_revision_chain(original, filings=[original])
        with pytest.raises(ValueError, match="以前に提出された Filing がありません"):
            chain.at_time(datetime(2025, 3, 1))


class TestBuildRevisionChain:
    def test_from_corrected_filing(self):
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

    def test_chain_is_sorted_by_submission_date(self):
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
            assert chain.chain[i].submit_date_time <= chain.chain[i + 1].submit_date_time

    def test_withdrawn_filing_excluded(self):
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

    def test_cascaded_withdrawal_excluded(self):
        """連動取下げ (withdrawal_status='2') もチェーンから除外される。

        G-7.a.md §5: 親書類が取下げられると子書類は自動的に
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

    def test_filings_argument_avoids_api(self):
        """filings 引数を渡すと API 呼び出しなしでチェーンを構築。"""
        original = _make_filing(
            doc_id="S100A",
            edinet_code=None,  # edinet_code=None → API 不可能
        )
        # filings を渡すので ValueError にならない
        chain = build_revision_chain(original, filings=[original])
        assert chain.count == 1

    def test_no_filings_no_edinet_code_raises(self):
        """filings 未指定 + edinet_code=None の場合は ValueError。"""
        filing = _make_filing(doc_id="S100A", edinet_code=None)
        with pytest.raises(ValueError, match="edinet_code"):
            build_revision_chain(filing)

    def test_unrelated_filings_ignored(self):
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


class TestEdgeCases:
    def test_same_submit_date_time_stable_sort(self):
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
            assert chain.chain[i].submit_date_time <= chain.chain[i + 1].submit_date_time

    def test_original_not_in_filings_seed_only(self):
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

    def test_post_init_rejects_unsorted_chain(self):
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


class TestRevisionChainIteration:
    def test_iter(self):
        """RevisionChain は iterate 可能。"""
        original = _make_filing(doc_id="S100A")
        chain = build_revision_chain(original, filings=[original])
        filings_list = list(chain)
        assert len(filings_list) == 1
        assert filings_list[0] is original

    def test_getitem(self):
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
```

---

## 7. 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `src/edinet/models/revision.py` | 新規 | `RevisionChain` dataclass（`at_time(date \| datetime)` 含む）、`build_revision_chain()` 関数、`_fetch_related_filings()`（2 段階検索）、内部ヘルパー 4 個 |
| `tests/test_models/test_revision.py` | 新規 | ~27 テストケース + ヘルパー関数 |

### 変更行数見積もり

| ファイル | 行数 |
|---------|------|
| `revision.py` | ~320 行（RevisionChain + __post_init__ソート検証 + at_time(date\|datetime) + build + 2 段階検索 + ヘルパー 4 個） |
| `test_revision.py` | ~580 行（27 テスト + Filing ヘルパー） |
| **合計** | **~900 行** |

---

## 8. エッジケースの処理

| ケース | 処理 |
|--------|------|
| 訂正なし（原本のみ） | チェーン長 1。`original == latest == filing` |
| 複数回訂正（3 回以上） | 全て `parent_doc_id == original.doc_id` で収集 |
| 取下げ済み Filing | `withdrawal_status != "0"`（`"1"` 取下げ / `"2"` 取消し）→ チェーンから除外 |
| 全 Filing が取下げ済み | seed_filing を含めてチェーン長 1 |
| filings に原本が含まれていない | seed_filing が原本の場合はそれを含める |
| filings に入力 filing が含まれていない | seed_filing として明示的に追加 |
| edinet_code=None + filings=None | ValueError を raise |
| 同一 doc_id の重複 Filing | seen_doc_ids で重複排除 |
| `at_time(cutoff)` で cutoff が原本より前 | ValueError を raise（該当 Filing なし） |
| `at_time(cutoff)` で cutoff がチェーン全体より後 | `latest` と同じ Filing を返す |
| `at_time(cutoff)` で cutoff がチェーン中間 | cutoff 以前で最も新しい Filing を返す |
| `at_time(cutoff)` に `date` を渡す | その日の 23:59:59 に変換し、その日中の提出を含める |
| 空の chain で RevisionChain を構築 | `__post_init__` で ValueError |
| ソートされていない chain で直接構築 | `__post_init__` で ValueError（昇順検証） |
| 同一 `submit_date_time` の Filing が複数 | ソートは安定（例外を出さない） |
| 原本が 365 日超前に提出 | 第 2 段階でも未発見 → seed_filing のみでチェーン構築。`original` は訂正版を返す |

---

## 9. 検証手順

1. `uv run pytest tests/test_models/test_revision.py -v` で全テスト PASS
2. `uv run pytest` で既存テストが壊れていないことを確認
3. `uv run ruff check src/edinet/models/revision.py tests/test_models/test_revision.py` でリント PASS

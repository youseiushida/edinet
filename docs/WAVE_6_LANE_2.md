# Wave 6 / Lane 2 — cache: 永続ディスクキャッシュ

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 6 / Lane 2 を担当するエージェントです。
担当機能: cache（ZIP ダウンロードの永続ディスクキャッシュ）

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
   - `src/edinet/api/cache.py` (新規)
   - `src/edinet/_config.py` (変更)
   - `src/edinet/models/filing.py` (変更)
   - `tests/test_api/test_cache.py` (新規)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。
   `src/edinet/api/download.py` は読み取り専用（import のみ）。

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
   - 例: `from edinet.api.cache import CacheStore` （OK）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_api/test_cache.py` に作成

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 5 以前に存在が確認されたモジュールのみ import 可能

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果を報告すること

---

# LANE 2 — cache: 永続ディスクキャッシュ

## 0. 位置づけ

### FEATURES.md との対応

Wave 6 Lane 2 は、FEATURES.md の **Cache** セクションに対応する。EDINET API からダウンロードした ZIP ファイルをディスクに永続化し、再実行時のネットワークアクセスを削減する。

### 設計決定事項

| 決定 | 内容 | 根拠 |
|------|------|------|
| D2 | 透過的キャッシュ。`fetch()` が自動的にディスクキャッシュを使用 | 既存 API を変更せずに恩恵を受けられる |
| D2 | キャッシュキー = `doc_id` | G-7.a.md で確認済み: 訂正報告書は別 doc_id。同一 doc_id の内容更新はない |
| D2 | `cache_dir=None`（デフォルト）でキャッシュ無効 | 明示的 opt-in |
| D2 | TTL なし。EDINET の開示書類は不変 | 取下げは `withdrawal_status` で判定 |
| D2 | `tempfile + os.rename` で原子的書き込み | 並行アクセスでの部分ファイル防止 |
| D5 | `clear_cache()` — 削除/リセット系は `clear_*` | 命名規約 |

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet._config` | `_Config` dataclass への `cache_dir` フィールド追加 | 変更 |
| `edinet.api.download` | `download_document()` の呼び出し（読み取りのみ） | read-only |
| `edinet.models.filing` | `Filing.fetch()` へのキャッシュ統合 | 変更 |

### ファイル衝突

- L3（revision_chain）は当初 `filing.py` を変更する計画だったが、D4 の決定により standalone 関数 `build_revision_chain()` を `revision.py` に配置するため、`filing.py` への変更は L2 のみ。衝突なし。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| H-9b | 直接 | 3 層キャッシュ構造の設計（インメモリ → ディスク → ネットワーク） |
| G-7 | 直接 | 訂正報告書は別 doc_id → キャッシュキー安全性の根拠 |
| D2 | 直接 | 透過的キャッシュの設計決定 |

### 参考パターン（既存実装）

`TaxonomyResolver` の pickle キャッシュが参考になる:
- `platformdirs.user_cache_dir("edinet")` でキャッシュディレクトリ取得
- pickle でシリアライズ→ディスク保存
- ファイル存在チェック→ヒット/ミスの判定

本 Lane はバイナリ（ZIP）をそのまま保存するため pickle は不要。

---

## 1. 背景知識

### 1.1 現在のキャッシュ階層

`Filing` の現在のキャッシュは **インメモリのみ**（`filing.py` L244-362）:

```python
class Filing(BaseModel):
    # インメモリキャッシュ（Pydantic PrivateAttr、frozen model）
    _zip_cache: bytes | None = PrivateAttr(default=None)
    _xbrl_cache: tuple[str, bytes] | None = PrivateAttr(default=None)

    def clear_fetch_cache(self) -> None:
        object.__setattr__(self, "_zip_cache", None)
        object.__setattr__(self, "_xbrl_cache", None)

    def fetch(self, *, refresh: bool = False) -> tuple[str, bytes]:
        # refresh=True → clear_fetch_cache() で両方クリア
        if refresh:
            self.clear_fetch_cache()
        if self._xbrl_cache is not None:
            return self._xbrl_cache
        if self._zip_cache is None:
            zip_bytes = download_document(self.doc_id, ...)
            object.__setattr__(self, "_zip_cache", zip_bytes)  # frozen model
        result = extract_primary_xbrl(self._zip_cache)
        # 失敗時: clear_fetch_cache() + raise EdinetParseError
        object.__setattr__(self, "_xbrl_cache", result)
        return result
```

**注意**: frozen Pydantic model のため `object.__setattr__` が必須。

問題点:
- `Filing` インスタンスが GC されるとキャッシュも消える
- 同一 `doc_id` でも新しい `Filing` インスタンスを作ると再ダウンロード
- 長時間のバッチ処理でメモリを圧迫する

### 1.2 目標のキャッシュ階層（3 層）

```
Layer 1: インメモリ（既存）  → _xbrl_cache / _zip_cache
Layer 2: ディスク（新規）    → {cache_dir}/downloads/{doc_id}.zip
Layer 3: ネットワーク（既存） → EDINET API download_document()
```

`fetch()` の探索順序:
1. `_xbrl_cache` ヒット → 即座に返す
2. `_zip_cache` ヒット → XBRL 抽出して返す
3. ディスクキャッシュ ヒット → ZIP 読み込み → `_zip_cache` に保存 → XBRL 抽出
4. ネットワーク → ダウンロード → ディスクに保存 → `_zip_cache` に保存 → XBRL 抽出

### 1.3 _config.py の現状

```python
@dataclass
class _Config:
    api_key: str | None = None
    base_url: str = "https://api.edinet-fsa.go.jp/api/v2"
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit: float = 1.0
    taxonomy_path: str | None = None
```

`cache_dir` フィールドは存在しない。

---

## 2. ゴール

1. `configure(cache_dir="~/.cache/edinet")` でディスクキャッシュを有効化
2. `Filing.fetch()` が透過的にディスクキャッシュを使用
3. `Filing.fetch(refresh=True)` でキャッシュを無視して再ダウンロード
4. `clear_cache()` で `downloads/` サブディレクトリを削除（cache_dir 直下の他ファイルは保護）
5. 原子的書き込み（`tempfile.NamedTemporaryFile` + `os.replace`）
6. `cache_dir=None`（デフォルト）でキャッシュ無効

完了条件:

```python
import edinet
from edinet.models.filing import Filing

# キャッシュ有効化
edinet.configure(cache_dir="/tmp/edinet_cache")

# 1 回目: ダウンロード → ディスク保存
path, xbrl = filing.fetch()
# /tmp/edinet_cache/downloads/{doc_id}.zip が作成される

# 2 回目: ディスクから読み込み（ネットワークアクセスなし）
path2, xbrl2 = filing.fetch()
assert xbrl == xbrl2

# 強制再ダウンロード
path3, xbrl3 = filing.fetch(refresh=True)

# キャッシュ全削除
from edinet.api.cache import clear_cache
clear_cache()
```

---

## 3. スコープ / 非スコープ

### 3.1 スコープ

| # | 内容 |
|---|------|
| S1 | `CacheStore` クラス（get/put/delete/clear/info） |
| S2 | `_config.py` に `cache_dir` フィールド追加 |
| S3 | `Filing.fetch()` にディスクキャッシュ層を統合 |
| S4 | `Filing.afetch()` にディスクキャッシュ層を統合 |
| S5 | `clear_cache()` 関数 |
| S6 | `cache_info()` 関数（統計情報: エントリ数、合計バイト数） |
| S7 | `_get_cache_store()` 内部ヘルパー（DRY + モック集約） |
| S8 | 原子的書き込み（tempfile + os.replace） |
| S9 | キャッシュディレクトリの自動作成 |

### 3.2 非スコープ

| # | 内容 | 理由 |
|---|------|------|
| N1 | HTTP ETag / If-Modified-Since | EDINET API がサポートしているか未確認。v0.2.0 以降 |
| N2 | LRU eviction（容量ベースの削除） | v0.1.0 ではユーザー責任。v0.2.0 以降で検討 |
| N3 | 容量制限 | 同上 |
| N4 | XBRL 解析結果のキャッシュ | ZIP のみキャッシュ。解析結果はインメモリキャッシュで対応 |
| N5 | ファイルロック（`fcntl.flock` 等） | 同一 doc_id は冪等。tempfile + rename で原子性保証 |
| N6 | キャッシュメタデータ（作成日時、サイズ等）の保存 | v0.1.0 では不要 |
| N7 | TTL（Time To Live） | EDINET の開示書類は不変。TTL 不要 |
| N8 | `file_type` をキャッシュキーに含める | 現在 `fetch()` は `XBRL_AND_AUDIT` 固定のため `doc_id` のみで安全。将来 `fetch_pdf` (FEATURES.md TODO) を追加する場合はキャッシュキーに `file_type` を含めるか、ディレクトリ構造を `downloads/{doc_id}/xbrl.zip` に変更する必要がある |

---

## 4. 実装計画

### 4.1 api/cache.py（新規）

`CacheStore` クラス、モジュールレベルの `clear_cache()` / `cache_info()` / `_get_cache_store()` を実装。

```python
"""EDINET ダウンロードファイルの永続ディスクキャッシュ。"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CacheInfo:
    """キャッシュの統計情報。``functools.lru_cache`` の ``cache_info()`` に倣ったパターン。

    利用例:
        >>> from edinet.api.cache import cache_info
        >>> info = cache_info()
        >>> print(f"{info.entry_count} entries, {info.total_bytes / 1024 / 1024:.1f} MB")
    """
    enabled: bool
    cache_dir: Path | None
    entry_count: int
    total_bytes: int


class CacheStore:
    """ZIP ダウンロードのディスクキャッシュストア。

    キャッシュキーは ``doc_id``（書類管理番号）。
    EDINET の開示書類は不変であり（訂正報告書は別の doc_id が付与される）、
    TTL や LRU eviction は不要。

    原子的書き込み:
        ``put()`` は ``tempfile.NamedTemporaryFile`` で一時ファイルに書き込み、
        ``os.replace()`` でアトミックにリネームする。プロセスクラッシュ時に
        中途半端なファイルが残ることを防止する。

    Args:
        cache_dir: キャッシュのルートディレクトリ。

    利用例:
        >>> store = CacheStore(Path("/tmp/edinet_cache"))
        >>> store.put("S100ABC0", zip_bytes)
        >>> data = store.get("S100ABC0")
        >>> assert data == zip_bytes
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._downloads_dir = cache_dir / "downloads"

    @property
    def cache_dir(self) -> Path:
        """キャッシュのルートディレクトリ。"""
        return self._cache_dir

    def cache_path(self, doc_id: str) -> Path:
        """doc_id に対応するキャッシュファイルのパスを返す。

        Args:
            doc_id: 書類管理番号。

        Returns:
            ``{cache_dir}/downloads/{doc_id}.zip``

        Note:
            現在は file_type=XBRL_AND_AUDIT 固定のため doc_id のみでキー化。
            fetch_pdf 対応時にキャッシュキーの拡張が必要（N8 参照）。
        """
        return self._downloads_dir / f"{doc_id}.zip"

    def get(self, doc_id: str) -> bytes | None:
        """キャッシュから ZIP バイナリを取得する。

        Args:
            doc_id: 書類管理番号。

        Returns:
            キャッシュヒット時は bytes。ミス時は None。
        """
        path = self.cache_path(doc_id)
        if not path.exists():
            return None
        try:
            data = path.read_bytes()
            logger.debug("キャッシュヒット: %s (%d bytes)", doc_id, len(data))
            return data
        except OSError:
            logger.warning("キャッシュ読み込み失敗: %s", doc_id, exc_info=True)
            return None

    def put(self, doc_id: str, data: bytes) -> None:
        """ZIP バイナリをキャッシュに保存する。

        原子的書き込み: tempfile に書き込み後、``os.replace()`` でリネーム。

        Note:
            ``os.fsync()`` は意図的に省略。キャッシュは最適化であり耐久ストレージ
            ではないため、クラッシュ時にエントリが消失しても再ダウンロードすれば
            よい。fsync 省略により HDD 環境でのパフォーマンスを維持する。

        Args:
            doc_id: 書類管理番号。
            data: ZIP バイナリ。
        """
        self._downloads_dir.mkdir(parents=True, exist_ok=True)
        target = self.cache_path(doc_id)
        tmp_name: str | None = None
        try:
            # 同一ディレクトリに一時ファイルを作成（os.replace のクロスデバイス問題を回避）
            fd = tempfile.NamedTemporaryFile(
                dir=self._downloads_dir,
                delete=False,
                suffix=".tmp",
            )
            tmp_name = fd.name
            try:
                fd.write(data)
                fd.flush()
            finally:
                fd.close()
            os.replace(tmp_name, target)
            tmp_name = None  # リネーム成功 → 掃除不要
            logger.debug("キャッシュ保存: %s (%d bytes)", doc_id, len(data))
        except OSError:
            # ディスク I/O エラー（容量不足、権限不足等）のみ吸収。
            # MemoryError 等の非 I/O エラーはここを通過して上位に伝播する。
            logger.warning("キャッシュ書き込み失敗: %s", doc_id, exc_info=True)
        finally:
            # 一時ファイルの掃除（リネーム前に例外が発生した場合）
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def delete(self, doc_id: str) -> None:
        """指定した doc_id のキャッシュを削除する。

        Args:
            doc_id: 書類管理番号。
        """
        path = self.cache_path(doc_id)
        try:
            path.unlink(missing_ok=True)
            logger.debug("キャッシュ削除: %s", doc_id)
        except OSError:
            logger.warning("キャッシュ削除失敗: %s", doc_id, exc_info=True)

    def clear(self) -> None:
        """``downloads/`` サブディレクトリを削除する。

        Note:
            ``cache_dir`` 直下ではなく ``downloads/`` のみを削除する。
            ``TaxonomyResolver`` の pickle キャッシュ等、同じ ``cache_dir``
            を共有する他のキャッシュを巻き込まないための安全策。
        """
        if self._downloads_dir.exists():
            shutil.rmtree(self._downloads_dir)
            logger.info("キャッシュ全削除: %s", self._downloads_dir)

    def info(self) -> CacheInfo:
        """キャッシュの統計情報を返す。

        Returns:
            ``CacheInfo`` dataclass。
        """
        if not self._downloads_dir.exists():
            return CacheInfo(
                enabled=True,
                cache_dir=self._cache_dir,
                entry_count=0,
                total_bytes=0,
            )
        entries = list(self._downloads_dir.glob("*.zip"))
        total = sum(f.stat().st_size for f in entries)
        return CacheInfo(
            enabled=True,
            cache_dir=self._cache_dir,
            entry_count=len(entries),
            total_bytes=total,
        )


def _get_cache_store() -> CacheStore | None:
    """キャッシュが有効なら ``CacheStore`` を返す。無効なら ``None``。

    ``Filing`` のヘルパーメソッドと ``clear_cache()`` / ``cache_info()`` が
    共通で使う内部関数。``get_config()`` + ``Path.expanduser()`` を 1 箇所に集約し、
    モック対象も 1 箇所にする。
    """
    from edinet._config import get_config
    config = get_config()
    if config.cache_dir is None:
        return None
    return CacheStore(Path(config.cache_dir).expanduser())


def clear_cache() -> None:
    """グローバル設定のダウンロードキャッシュを全削除する。

    ``configure(cache_dir=...)`` で設定されたキャッシュディレクトリ内の
    ``downloads/`` サブディレクトリを ``shutil.rmtree`` で削除する。
    ``cache_dir`` 直下の他のファイル（taxonomy pickle キャッシュ等）は
    保護される。キャッシュが無効の場合は何もしない。

    利用例:
        >>> import edinet
        >>> edinet.configure(cache_dir="/tmp/edinet_cache")
        >>> # ... 何らかの操作 ...
        >>> from edinet.api.cache import clear_cache
        >>> clear_cache()
    """
    store = _get_cache_store()
    if store is None:
        logger.debug("キャッシュ無効のため clear_cache() はスキップ")
        return
    store.clear()


def cache_info() -> CacheInfo:
    """キャッシュの統計情報を返す。

    ``functools.lru_cache`` の ``cache_info()`` に倣ったパターン。
    キャッシュ無効時は ``enabled=False`` で ``CacheInfo`` を返す。

    Returns:
        ``CacheInfo`` dataclass。

    利用例:
        >>> from edinet.api.cache import cache_info
        >>> info = cache_info()
        >>> info.entry_count
        42
    """
    store = _get_cache_store()
    if store is None:
        return CacheInfo(enabled=False, cache_dir=None, entry_count=0, total_bytes=0)
    return store.info()
```

### 4.2 _config.py への変更

`_Config` dataclass に `cache_dir` フィールドを追加する。

```python
@dataclass
class _Config:
    """ライブラリのグローバル設定。直接インスタンス化しない。"""
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.edinet-fsa.go.jp/api/v2"
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit: float = 1.0
    taxonomy_path: str | None = None
    cache_dir: str | None = None  # ← 新規追加（デフォルト None = 無効）

    # ... 既存メソッドは一切変更しない
```

`configure()` 関数のシグネチャに `cache_dir` を追加:

```python
def configure(
    *,
    api_key: str | None = _UNSET,
    base_url: str = _UNSET,
    timeout: float = _UNSET,
    max_retries: int = _UNSET,
    rate_limit: float = _UNSET,
    taxonomy_path: str | None = _UNSET,
    cache_dir: str | None = _UNSET,  # ← 新規追加
) -> None:
    """ライブラリのグローバル設定を更新する。"""
```

#### configure() 関数本体への変更

既存の `if taxonomy_path is not _UNSET:` ブロック（L60-61）の直後に以下を追加する:

```python
    if cache_dir is not _UNSET:
        updates["cache_dir"] = cache_dir
```

**注意**:
- `configure()` の既存パラメータのデフォルト値は `_UNSET` センチネルパターンで制御されている。`cache_dir` も同じパターンに従う（`cache_dir: str | None = _UNSET`）。既存パラメータの動作は一切変更しない。
- `_NOT_NONE` バリデーション集合（L66: `{"base_url", "timeout", "max_retries", "rate_limit"}`）に `cache_dir` を**追加しない**。`cache_dir=None` はキャッシュ無効化の正当な操作であるため。
- `_CLIENT_PARAMS`（L33: `{"base_url", "timeout"}`）に `cache_dir` を**追加しない**。`cache_dir` の変更は HTTP クライアントの再生成を必要としない。
- **エラーメッセージ更新**: `_config.py:69-72` のエラーメッセージ `"Only api_key and taxonomy_path can be cleared with None."` を `"Only api_key, taxonomy_path, and cache_dir can be cleared with None."` に更新すること。

### 4.3 filing.py への変更

`Filing.fetch()` と `Filing.afetch()` にディスクキャッシュ層を統合する。

**重要**: Filing は frozen Pydantic モデルのため、キャッシュフィールドへの代入には
`object.__setattr__(self, "_zip_cache", ...)` が必須。通常の `self._zip_cache = ...` は
`FrozenInstanceError` になる。

変更前の `fetch()` のフロー:

```
1. has_xbrl チェック → False なら EdinetAPIError
2. refresh=True なら clear_fetch_cache()
3. _xbrl_cache ヒット → return
4. _zip_cache が None なら download_document() → object.__setattr__ で _zip_cache に保存
5. extract_primary_xbrl() → 失敗時は clear_fetch_cache() + raise
6. object.__setattr__ で _xbrl_cache に保存 → return
```

変更後の `fetch()` のフロー:

```
1. has_xbrl チェック → False なら EdinetAPIError
2. refresh=True なら clear_fetch_cache()
3. _xbrl_cache ヒット → return
4. _zip_cache が None なら:
   4a. ディスクキャッシュ確認（新規）→ ヒットなら from_disk=True
   4b. ミスなら download_document() → ディスクに保存（新規）
   4c. object.__setattr__ で _zip_cache に保存
5. extract_primary_xbrl() → 失敗時は _delete_disk_cache()（新規）+ clear_fetch_cache() + raise
6. object.__setattr__ で _xbrl_cache に保存 → return
```

#### fetch() の変更差分（filing.py L299-362 ベース）

既存コードの構造を維持し、ディスクキャッシュ層を差し込む。行番号は変更前の `filing.py` を参照。

```python
    def fetch(self, *, refresh: bool = False) -> tuple[str, bytes]:
        """提出本文書 ZIP から代表 XBRL を取得する。"""
        from edinet.api.download import (
            DownloadFileType,
            download_document,
            extract_primary_xbrl,
        )
        from edinet.exceptions import EdinetAPIError, EdinetParseError

        if not self.has_xbrl:
            raise EdinetAPIError(
                0,
                f"書類に XBRL が含まれていません (doc_id={self.doc_id}, xbrlFlag=0)。",
            )

        if refresh:
            self.clear_fetch_cache()

        if self._xbrl_cache is not None:
            return self._xbrl_cache

        from_disk = False  # ← 新規: 破損キャッシュ回復用フラグ

        if self._zip_cache is None:
            # ── 新規: Layer 2 ディスクキャッシュ ──
            if not refresh:
                disk_data = self._get_from_disk_cache()
                if disk_data is not None:
                    object.__setattr__(self, "_zip_cache", disk_data)
                    from_disk = True
            # ── 新規ここまで ──

        if self._zip_cache is None:
            try:
                zip_bytes = download_document(
                    self.doc_id,
                    file_type=DownloadFileType.XBRL_AND_AUDIT,
                )
            except ValueError as exc:
                raise EdinetParseError(
                    f"XBRL ZIP のダウンロードに失敗しました "
                    f"(doc_id={self.doc_id!r}): {exc}",
                ) from exc
            object.__setattr__(self, "_zip_cache", zip_bytes)
            # ── 新規: ディスクに保存 ──
            self._save_to_disk_cache(zip_bytes)

        assert self._zip_cache is not None
        try:
            result = extract_primary_xbrl(self._zip_cache)
        except ValueError as exc:
            # ── 新規: ディスクキャッシュ由来なら当該エントリ削除 ──
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()  # 既存: インメモリキャッシュもクリア
            raise EdinetParseError(
                f"EDINET ZIP の解析に失敗しました (doc_id={self.doc_id})。",
            ) from exc

        if result is None:
            # ── 新規: ディスクキャッシュ由来なら当該エントリ削除 ──
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()  # 既存: インメモリキャッシュもクリア
            raise EdinetParseError(
                f"ZIP 内に主要な XBRL が見つかりません (doc_id={self.doc_id})。",
            )

        object.__setattr__(self, "_xbrl_cache", result)
        return result
```

**C1 対応**: 実コードの `object.__setattr__`、`ValueError` → `EdinetParseError` ラッピング、`DownloadFileType.XBRL_AND_AUDIT` を全て維持。
**C2 対応**: `_delete_disk_cache()` は `clear_fetch_cache()` の**前**に呼ぶ。既存の `clear_fetch_cache()` は削除しない。

#### ディスクキャッシュのヘルパーメソッド（`_get_cache_store` 共有パターン）

3つのヘルパーは全て `api/cache.py` の `_get_cache_store()` を使い、DRY にする:

```python
    def _get_from_disk_cache(self) -> bytes | None:
        """ディスクキャッシュから ZIP を読み込む。

        Returns:
            キャッシュヒット時は bytes。キャッシュ無効またはミス時は None。
        """
        from edinet.api.cache import _get_cache_store
        store = _get_cache_store()
        if store is None:
            return None
        return store.get(self.doc_id)

    def _save_to_disk_cache(self, data: bytes) -> None:
        """ZIP をディスクキャッシュに保存する。

        Args:
            data: 保存する ZIP バイナリ。
        """
        from edinet.api.cache import _get_cache_store
        store = _get_cache_store()
        if store is None:
            return
        store.put(self.doc_id, data)

    def _delete_disk_cache(self) -> None:
        """ディスクキャッシュの当該エントリを削除する。

        破損したキャッシュファイルによる無限ループを防止するために使用。
        ディスクキャッシュ由来の ZIP が解析に失敗した場合に呼ばれ、
        次回の fetch() でネットワークから再取得できるようにする。
        """
        from edinet.api.cache import _get_cache_store
        store = _get_cache_store()
        if store is None:
            return
        store.delete(self.doc_id)
```

**S3 対応**: `get_config()` + `Path.expanduser()` + `CacheStore()` の重複を `_get_cache_store()` に集約。モック対象も `"edinet.api.cache._get_cache_store"` の 1 箇所に統一される。

### 4.4 キャッシュディレクトリ構造

```
{cache_dir}/
  downloads/
    S100ABC0.zip
    S100DEF1.zip
    ...
```

- `cache_dir` はユーザーが `configure()` で指定する任意のパス
- `~` は `Path.expanduser()` で展開する
- `downloads/` サブディレクトリは `put()` 時に自動作成（`mkdir(parents=True, exist_ok=True)`）
- ファイル名は `{doc_id}.zip` 固定

### 4.5 refresh=True の動作

`refresh=True` が指定された場合:
1. インメモリキャッシュをスキップ
2. ディスクキャッシュをスキップ
3. ネットワークからダウンロード
4. ダウンロード結果でディスクキャッシュを上書き
5. インメモリキャッシュを更新

これにより、キャッシュの整合性が保たれる。

---

## 5. 実装の注意点

### 5.1 原子的書き込み

`os.replace()` は POSIX でアトミック、Windows でもファイル置換としてアトミック。`os.rename()` ではなく `os.replace()` を使う理由:
- `os.rename()` は Windows で宛先が存在すると失敗する
- `os.replace()` は宛先を上書きする（クロスプラットフォーム）

一時ファイルはキャッシュディレクトリと同じファイルシステムに作成する（`dir=self._downloads_dir`）。これにより `os.replace()` がクロスデバイス問題を回避できる。

### 5.2 エラーハンドリング

ディスクキャッシュの読み書きエラーはキャッチして `logger.warning()` で記録し、処理を続行する。キャッシュはあくまで最適化であり、キャッシュ失敗で API 呼び出しが止まってはならない。

```python
# キャッシュ読み込み失敗 → None を返し、ネットワークからダウンロード
# キャッシュ書き込み失敗 → 警告ログのみ、ダウンロード結果は正常に返す
```

### 5.3 `configure()` での `cache_dir` 変更

`configure(cache_dir="...")` は何度でも呼べる。`cache_dir` を変更すると、以降の `fetch()` は新しいディレクトリを参照する。古いディレクトリのファイルは自動的には削除されない。

`configure(cache_dir=None)` でキャッシュを無効化できる。

### 5.4 ログメッセージの言語

CLAUDE.md の指示「コメントやエラーメッセージは日本語」に従い、`CacheStore` のログメッセージは日本語で統一する。既存の `_http.py` / `download.py` のログは英語だが、これはユーザー向けではなくデバッグ用であり、キャッシュモジュールは利用者が `logging.DEBUG` で有効化して目にする可能性が高いため日本語を採用。

### 5.5 Filing.afetch() との整合

`afetch()` も同じディスクキャッシュ層を使う。ディスク I/O は同期的に行う（`aiofiles` 等の非同期ファイル I/O は使わない）。ZIP ファイルは最大数 MB 程度であり、同期ディスク I/O で十分。

`afetch()` の変更差分（filing.py L364-427 ベース）。`fetch()` と**完全に同じパターン**で、唯一の差分はネットワーク層が `await adownload_document()` であること:

```python
    async def afetch(self, *, refresh: bool = False) -> tuple[str, bytes]:
        """提出本文書 ZIP から代表 XBRL を非同期で取得する。"""
        from edinet.api.download import (
            DownloadFileType,
            adownload_document,
            extract_primary_xbrl,
        )
        from edinet.exceptions import EdinetAPIError, EdinetParseError

        if not self.has_xbrl:
            raise EdinetAPIError(
                0,
                f"書類に XBRL が含まれていません (doc_id={self.doc_id}, xbrlFlag=0)。",
            )

        if refresh:
            self.clear_fetch_cache()

        if self._xbrl_cache is not None:
            return self._xbrl_cache

        from_disk = False  # ← fetch() と同じ

        if self._zip_cache is None:
            if not refresh:
                disk_data = self._get_from_disk_cache()  # 同期 I/O で十分
                if disk_data is not None:
                    object.__setattr__(self, "_zip_cache", disk_data)
                    from_disk = True

        if self._zip_cache is None:
            try:
                zip_bytes = await adownload_document(  # ← 唯一の差分: await
                    self.doc_id,
                    file_type=DownloadFileType.XBRL_AND_AUDIT,
                )
            except ValueError as exc:
                raise EdinetParseError(
                    f"XBRL ZIP のダウンロードに失敗しました "
                    f"(doc_id={self.doc_id!r}): {exc}",
                ) from exc
            object.__setattr__(self, "_zip_cache", zip_bytes)
            self._save_to_disk_cache(zip_bytes)  # 同期 I/O で十分

        assert self._zip_cache is not None
        try:
            result = extract_primary_xbrl(self._zip_cache)
        except ValueError as exc:
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"EDINET ZIP の解析に失敗しました (doc_id={self.doc_id})。",
            ) from exc

        if result is None:
            if from_disk:
                self._delete_disk_cache()
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"ZIP 内に主要な XBRL が見つかりません (doc_id={self.doc_id})。",
            )

        object.__setattr__(self, "_xbrl_cache", result)
        return result
```

`_get_from_disk_cache()` / `_save_to_disk_cache()` / `_delete_disk_cache()` は `fetch()` と共有する。

---

## 6. テスト計画

### 6.1 テストファイル

`tests/test_api/test_cache.py` に全テストを作成する。

### 6.2 テスト戦略

- `CacheStore` のテストは `tmp_path` フィクスチャで一時ディレクトリを使用
- `Filing.fetch()` のキャッシュ統合テストは `monkeypatch` で `download_document` をモックし、ネットワーク呼び出しの有無を検証
- デトロイト派だが、ネットワーク呼び出しのモックは「外部依存の分離」として許容される
- **conftest.py の autouse fixture**: `_reset_config` fixture が全テスト後に `_reset_for_testing()` を呼び出し、`_Config()` を新規生成するため、`cache_dir` は自動的に `None` に戻る。テスト内で手動クリーンアップ（`edinet.configure(cache_dir=None)`）は不要
- **テスト用 ZIP の構築**: `conftest.py` の `_make_test_zip()` ヘルパーを使用して有効な ZIP を生成する
- **モック対象パス**: `download_document` は `Filing.fetch()` 内でローカル import されるため、モック対象は `"edinet.api.download.download_document"`（定義元）。`extract_primary_xbrl` も同様

### 6.2b テスト用 Filing ファクトリ

`Filing` は frozen Pydantic モデルで多数の必須フィールドを持つ。テストでは最小限の Filing インスタンスを生成するヘルパーを使う:

```python
from datetime import datetime
from typing import Any
from edinet.models.filing import Filing

def _make_filing(
    doc_id: str = "S100TEST",
    has_xbrl: bool = True,
    **overrides: Any,
) -> Filing:
    """テスト用の最小限 Filing を生成する。"""
    defaults = dict(
        seq_number=1,
        doc_id=doc_id,
        doc_type_code="120",
        ordinance_code="010",
        form_code="030000",
        edinet_code=None,
        sec_code=None,
        jcn=None,
        filer_name="テスト株式会社",
        fund_code=None,
        submit_date_time=datetime(2026, 1, 1, 9, 0),
        period_start=None,
        period_end=None,
        doc_description="テスト書類",
        issuer_edinet_code=None,
        subject_edinet_code=None,
        subsidiary_edinet_code=None,
        current_report_reason=None,
        parent_doc_id=None,
        ope_date_time=None,
        withdrawal_status="0",
        doc_info_edit_status="0",
        disclosure_status="0",
        has_xbrl=has_xbrl,
        has_pdf=False,
        has_attachment=False,
        has_english=False,
        has_csv=False,
        legal_status="0",
    )
    defaults.update(overrides)
    return Filing(**defaults)
```

### 6.3 テストケース一覧（~30 件）

```python
from pathlib import Path
from typing import Any
from edinet.api.cache import CacheStore, CacheInfo, cache_info, clear_cache


class TestCacheStore:
    def test_put_and_get(self, tmp_path: Path):
        """put() で保存したデータを get() で取得できる。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"dummy zip data")
        result = store.get("S100ABC0")
        assert result == b"dummy zip data"

    def test_get_miss(self, tmp_path: Path):
        """存在しない doc_id では None が返る。"""
        store = CacheStore(tmp_path)
        result = store.get("S100NOEXIST")
        assert result is None

    def test_delete(self, tmp_path: Path):
        """delete() でキャッシュを削除できる。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"data")
        store.delete("S100ABC0")
        assert store.get("S100ABC0") is None

    def test_delete_nonexistent(self, tmp_path: Path):
        """存在しないキーの delete() はエラーにならない。"""
        store = CacheStore(tmp_path)
        store.delete("S100NOEXIST")  # 例外が発生しない

    def test_clear(self, tmp_path: Path):
        """clear() で downloads/ サブディレクトリを削除する。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"data1")
        store.put("S100DEF1", b"data2")
        # cache_dir 直下に他のファイルを作成（taxonomy pickle 等を想定）
        (tmp_path / "other_cache.pkl").write_bytes(b"taxonomy")
        store.clear()
        assert store.get("S100ABC0") is None
        assert store.get("S100DEF1") is None
        assert not (tmp_path / "downloads").exists()
        # cache_dir 自体と他のファイルは保護される
        assert tmp_path.exists()
        assert (tmp_path / "other_cache.pkl").exists()

    def test_clear_empty(self, tmp_path: Path):
        """空のキャッシュで clear() してもエラーにならない。"""
        store = CacheStore(tmp_path / "nonexistent")
        store.clear()  # 例外が発生しない

    def test_cache_path_structure(self, tmp_path: Path):
        """キャッシュパスが {cache_dir}/downloads/{doc_id}.zip の形式。"""
        store = CacheStore(tmp_path)
        path = store.cache_path("S100ABC0")
        assert path == tmp_path / "downloads" / "S100ABC0.zip"

    def test_put_creates_directory(self, tmp_path: Path):
        """put() がディレクトリを自動作成する。"""
        cache_dir = tmp_path / "deep" / "nested"
        store = CacheStore(cache_dir)
        store.put("S100ABC0", b"data")
        assert store.get("S100ABC0") == b"data"

    def test_put_overwrite(self, tmp_path: Path):
        """同じ doc_id に対して put() を再実行すると上書きされる。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"old data")
        store.put("S100ABC0", b"new data")
        assert store.get("S100ABC0") == b"new data"

    def test_atomic_write_no_partial_file(self, tmp_path: Path):
        """正常書き込み後に .tmp ファイルが残らない。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"valid data")
        downloads_dir = tmp_path / "downloads"
        tmp_files = list(downloads_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_info(self, tmp_path: Path):
        """info() がエントリ数と合計バイト数を返す。"""
        store = CacheStore(tmp_path)
        assert store.info().entry_count == 0
        assert store.info().total_bytes == 0
        store.put("S100ABC0", b"x" * 100)
        store.put("S100DEF1", b"y" * 200)
        info = store.info()
        assert info.entry_count == 2
        assert info.total_bytes == 300
        assert info.enabled is True


class TestCacheConfig:
    def test_cache_disabled_by_default(self):
        """デフォルトでは cache_dir は None。"""
        from edinet._config import get_config
        config = get_config()
        assert config.cache_dir is None

    def test_configure_cache_dir(self, tmp_path: Path):
        """configure() で cache_dir を設定できる。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))
        from edinet._config import get_config
        assert get_config().cache_dir == str(tmp_path)
        # 手動クリーンアップ不要: conftest.py の autouse fixture が
        # _reset_for_testing() を呼び、cache_dir=None にリセットする

    def test_configure_cache_dir_none_disables(self):
        """cache_dir=None でキャッシュを無効化できる。"""
        import edinet
        edinet.configure(cache_dir="/tmp/test")
        edinet.configure(cache_dir=None)
        from edinet._config import get_config
        assert get_config().cache_dir is None


class TestFilingFetchWithCache:
    """Filing.fetch() のディスクキャッシュ統合テスト。

    ネットワーク呼び出し（download_document）はモックし、
    ディスクキャッシュ（CacheStore）は実物を使う（デトロイト派）。

    テスト用 ZIP は conftest.py の _make_test_zip() で構築する。
    """

    def test_cache_hit_no_download(self, tmp_path: Path, monkeypatch, make_test_zip):
        """ディスクキャッシュにヒットした場合、ダウンロードしない。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        # テスト用 ZIP を構築してディスクキャッシュに直接配置
        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        store = CacheStore(tmp_path)
        store.put("S100TEST", zip_bytes)

        # download_document が呼ばれたら AssertionError
        def must_not_call(*args, **kwargs):
            raise AssertionError("download_document が呼ばれた")
        monkeypatch.setattr(
            "edinet.api.download.download_document", must_not_call
        )

        filing = _make_filing(doc_id="S100TEST")
        path, data = filing.fetch()
        assert len(data) > 0  # XBRL が抽出された

    def test_cache_miss_triggers_download(self, tmp_path: Path, monkeypatch, make_test_zip):
        """ディスクキャッシュにミスした場合、ダウンロードする。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        call_count = 0

        def mock_download(doc_id, **kwargs):
            nonlocal call_count
            call_count += 1
            return zip_bytes
        monkeypatch.setattr(
            "edinet.api.download.download_document", mock_download
        )

        filing = _make_filing(doc_id="S100MISS")
        filing.fetch()
        assert call_count == 1

    def test_refresh_true_bypasses_cache(self, tmp_path: Path, monkeypatch, make_test_zip):
        """refresh=True の場合、キャッシュを無視してダウンロードする。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)

        # ディスクキャッシュに事前配置
        store = CacheStore(tmp_path)
        store.put("S100TEST", zip_bytes)

        call_count = 0
        def mock_download(doc_id, **kwargs):
            nonlocal call_count
            call_count += 1
            return zip_bytes
        monkeypatch.setattr(
            "edinet.api.download.download_document", mock_download
        )

        filing = _make_filing(doc_id="S100TEST")
        filing.fetch(refresh=True)
        assert call_count == 1  # キャッシュがあっても再ダウンロードされた

    def test_download_result_saved_to_cache(self, tmp_path: Path, monkeypatch, make_test_zip):
        """ダウンロード結果がディスクキャッシュに保存される。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document", lambda *a, **kw: zip_bytes
        )

        filing = _make_filing(doc_id="S100NEW")
        filing.fetch()

        # ディスクキャッシュにファイルが存在する
        store = CacheStore(tmp_path)
        cached = store.get("S100NEW")
        assert cached == zip_bytes

    def test_corrupted_cache_self_heals(self, tmp_path: Path, monkeypatch, make_test_zip):
        """破損したキャッシュファイルが自動的に削除される。"""
        import edinet
        from edinet.exceptions import EdinetParseError
        edinet.configure(cache_dir=str(tmp_path))

        # 破損データ（有効な ZIP ではない）をディスクキャッシュに直接配置
        store = CacheStore(tmp_path)
        store.put("S100CORRUPT", b"this is not a zip file")

        # ネットワークからも取得させない
        def must_not_call(*args, **kwargs):
            raise AssertionError("download_document が呼ばれた")
        monkeypatch.setattr(
            "edinet.api.download.download_document", must_not_call
        )

        filing = _make_filing(doc_id="S100CORRUPT")
        # 破損データで EdinetParseError が発生する
        import pytest
        with pytest.raises(EdinetParseError):
            filing.fetch()

        # ディスクキャッシュの当該エントリが削除されている
        assert store.get("S100CORRUPT") is None

    def test_cache_disabled_no_disk_io(self, monkeypatch, make_test_zip):
        """キャッシュ無効時にディスク I/O が発生しない。"""
        # cache_dir=None（デフォルト）のまま
        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document", lambda *a, **kw: zip_bytes
        )

        filing = _make_filing(doc_id="S100NOCACHE")
        path, data = filing.fetch()
        assert len(data) > 0  # 正常に取得できる（ディスクキャッシュなしで）

    def test_second_fetch_hits_memory_cache(self, tmp_path: Path, monkeypatch, make_test_zip):
        """2回目の fetch() は in-memory キャッシュにヒットし、disk にもアクセスしない。

        3層キャッシュ階層（memory → disk → network）の核心動作を検証する。
        """
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document", lambda *a, **kw: zip_bytes
        )

        filing = _make_filing(doc_id="S100MEM")
        filing.fetch()  # 1回目: network → disk → memory

        # ディスクキャッシュを削除しても 2 回目は成功する（in-memory から返る）
        CacheStore(tmp_path).delete("S100MEM")
        path, data = filing.fetch()  # 2回目: memory hit
        assert len(data) > 0

    def test_refresh_true_updates_disk_cache(self, tmp_path: Path, monkeypatch, make_test_zip):
        """refresh=True でダウンロードした結果がディスクキャッシュを上書きする。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        old_xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance">old</xbrl>'
        new_xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance">new</xbrl>'

        # 古い ZIP をディスクキャッシュに事前配置
        store = CacheStore(tmp_path)
        store.put("S100REF", make_test_zip(old_xbrl))

        new_zip = make_test_zip(new_xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document", lambda *a, **kw: new_zip
        )

        filing = _make_filing(doc_id="S100REF")
        filing.fetch(refresh=True)

        # ディスクキャッシュが新しい ZIP で上書きされた
        assert store.get("S100REF") == new_zip

    def test_cache_dir_change_uses_new_dir(self, tmp_path: Path, monkeypatch, make_test_zip):
        """cache_dir 変更後は新しいディレクトリを参照する。"""
        import edinet
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"

        edinet.configure(cache_dir=str(dir_a))
        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        call_count = 0

        def mock_download(doc_id, **kwargs):
            nonlocal call_count
            call_count += 1
            return zip_bytes
        monkeypatch.setattr(
            "edinet.api.download.download_document", mock_download
        )

        filing = _make_filing(doc_id="S100SWITCH")
        filing.fetch()
        assert CacheStore(dir_a).get("S100SWITCH") is not None
        assert call_count == 1

        # cache_dir 変更 → 新しいディレクトリにはキャッシュがない
        edinet.configure(cache_dir=str(dir_b))
        filing2 = _make_filing(doc_id="S100SWITCH")
        filing2.fetch()  # dir_b にキャッシュミス → 再ダウンロード
        assert call_count == 2
        assert CacheStore(dir_b).get("S100SWITCH") is not None


class TestFilingAfetchWithCache:
    """Filing.afetch() のディスクキャッシュ統合テスト（非同期版）。"""

    @pytest.mark.asyncio
    async def test_afetch_cache_hit(self, tmp_path: Path, monkeypatch, make_test_zip):
        """afetch() もディスクキャッシュを使用する。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        store = CacheStore(tmp_path)
        store.put("S100ASYNC", zip_bytes)

        async def must_not_call(*args, **kwargs):
            raise AssertionError("adownload_document が呼ばれた")
        monkeypatch.setattr(
            "edinet.api.download.adownload_document", must_not_call
        )

        filing = _make_filing(doc_id="S100ASYNC")
        path, data = await filing.afetch()
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_afetch_saves_to_disk(self, tmp_path: Path, monkeypatch, make_test_zip):
        """afetch() のダウンロード結果もディスクキャッシュに保存される。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)

        async def mock_adownload(doc_id, **kwargs):
            return zip_bytes
        monkeypatch.setattr(
            "edinet.api.download.adownload_document", mock_adownload
        )

        filing = _make_filing(doc_id="S100ASYNC2")
        await filing.afetch()

        # ディスクキャッシュにファイルが保存されている
        assert CacheStore(tmp_path).get("S100ASYNC2") == zip_bytes


class TestClearCache:
    def test_clear_cache_function(self, tmp_path: Path):
        """clear_cache() が downloads/ サブディレクトリを削除する。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"data")
        clear_cache()
        assert not (tmp_path / "downloads").exists()
        assert tmp_path.exists()  # cache_dir 自体は残る

    def test_clear_cache_when_disabled(self):
        """キャッシュ無効時の clear_cache() は何もしない。"""
        clear_cache()  # cache_dir=None（デフォルト）、例外が発生しない


class TestCacheInfo:
    def test_cache_info_when_disabled(self):
        """キャッシュ無効時は enabled=False を返す。"""
        info = cache_info()
        assert info.enabled is False
        assert info.entry_count == 0

    def test_cache_info_with_entries(self, tmp_path: Path):
        """キャッシュにエントリがある場合の統計情報。"""
        import edinet
        edinet.configure(cache_dir=str(tmp_path))
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"x" * 1000)
        store.put("S100DEF1", b"y" * 2000)
        info = cache_info()
        assert info.enabled is True
        assert info.entry_count == 2
        assert info.total_bytes == 3000
```

---

## 7. 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `src/edinet/api/cache.py` | 新規 | `CacheStore` クラス、`CacheInfo` dataclass、`_get_cache_store()` ヘルパー、`clear_cache()` / `cache_info()` 関数 |
| `src/edinet/_config.py` | 変更 | `_Config` に `cache_dir: str \| None = None` 追加、`configure()` に `cache_dir` パラメータ追加、エラーメッセージ更新 |
| `src/edinet/models/filing.py` | 変更 | `fetch()` / `afetch()` にディスクキャッシュ層を統合、`_get_from_disk_cache()` / `_save_to_disk_cache()` / `_delete_disk_cache()` ヘルパー追加 |
| `tests/test_api/test_cache.py` | 新規 | ~30 テストケース（同期 + 非同期） |

**読み取り専用** (import のみ):
- `src/edinet/api/download.py` — `download_document`, `adownload_document`, `extract_primary_xbrl` を import

### 変更行数見積もり

| ファイル | 追加行数 |
|---------|---------|
| `api/cache.py` | ~200 行（CacheStore + CacheInfo + _get_cache_store + clear_cache + cache_info） |
| `_config.py` | ~10 行（cache_dir フィールド + configure パラメータ + エラーメッセージ更新） |
| `models/filing.py` | ~60 行（ディスクキャッシュ層の統合 + ヘルパー 3 個 + 破損回復ロジック） |
| `test_cache.py` | ~500 行（30 テスト + Filing ファクトリ + 非同期テスト） |
| **合計** | **~770 行** |

---

## 8. エッジケースの処理

| ケース | 処理 |
|--------|------|
| `cache_dir` 配下にディスク容量がない | `put()` の OSError をキャッチ → warning ログ、処理続行 |
| `cache_dir` が読み取り専用 | `put()` の OSError をキャッチ → warning ログ、処理続行 |
| キャッシュファイルが破損（0 バイト等） | `get()` は bytes を返す。`fetch()` 内の XBRL 抽出で失敗した場合、`from_disk` フラグにより `_delete_disk_cache()` でディスクキャッシュの当該エントリを削除し、さらに既存の `clear_fetch_cache()` でインメモリキャッシュもクリアする。次回 `fetch()` 時にネットワークから再取得される。無限ループを防止 |
| `cache_dir` に `~` を含む | `Path.expanduser()` で展開 |
| `cache_dir` が相対パス | そのまま使用（カレントディレクトリ相対）。推奨は絶対パス |
| 同一 `doc_id` の並行ダウンロード | tempfile + os.replace で原子性保証。最後の書き込みが勝つ（冪等なので問題なし） |

---

## 9. 検証手順

1. `uv run pytest tests/test_api/test_cache.py -v` で全テスト PASS
2. `uv run pytest` で既存テストが壊れていないことを確認
3. `uv run ruff check src/edinet/api/cache.py src/edinet/_config.py src/edinet/models/filing.py tests/test_api/test_cache.py` でリント PASS
4. 手動確認: `configure(cache_dir=...)` → `Filing.fetch()` → キャッシュファイル生成を目視確認

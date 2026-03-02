# Day 7.5 — async API 追加（非破壊的並列化）

## 0. 位置づけ

Day 7 で同期公開 API の契約（例外・欠損行・テスト tier）が固定された。
Day 8 は XBRL 仕様読解に充てるため、その間に transport 層の async 化を完了させる。

ベンチマーク（Day 7）で同期 `fetch()` が **3.34s/件** であり、有報シーズン 2,576 件の
全件取得に **約 2.4 時間** かかることが判明。async + セマフォ並列化で **5〜10 倍**
（15〜30 分）への短縮を目指す。

**方針は「非破壊追加」**: 既存の同期 API は一切変更せず、`async def` 版を追加するだけ。
同期テストが 1 件も壊れないことを前提とする。

---

## 1. 現状の同期アーキテクチャ

```
edinet.documents()                  # 公開 API (public_api.py)
  └→ get_documents()                # API ラッパー (api/documents.py)
       └→ _http.get()               # HTTP 通信層 (_http.py)
            └→ httpx.Client.get()   # httpx 同期クライアント

Filing.fetch()                      # モデル層 (models/filing.py)
  └→ download_document()            # API ラッパー (api/download.py)
       └→ _http.get()               # 同上
```

async 化では各層に `async def` 版を追加し、末端を `httpx.AsyncClient` に差し替える:

```
edinet.adocuments()                 # 公開 async API (public_api.py)
  └→ aget_documents()               # async API ラッパー (api/documents.py)
       └→ _http.aget()              # async HTTP 通信層 (_http.py)
            └→ httpx.AsyncClient.get()

Filing.afetch()                     # async モデル層 (models/filing.py)
  └→ adownload_document()           # async API ラッパー (api/download.py)
       └→ _http.aget()              # 同上
```

---

## 2. スコープ / 非スコープ

### 2.1 Day 7.5 のスコープ

- `_http.py` に async クライアント管理 + `aget()` 追加
- `api/documents.py` に `aget_documents()` 追加
- `api/download.py` に `adownload_document()` 追加
- `public_api.py` に `adocuments()` 追加
- `models/filing.py` に `afetch()` 追加
- `__init__.py` に `adocuments`, `aclose` エクスポート追加
- 全層のテスト（`pytest-asyncio` 導入）
- stubs は `stubgen` で自動生成

### 2.2 Day 7.5 でやらないこと

- 既存同期 API の変更（一切触らない）
- `asyncio.gather` / `asyncio.TaskGroup` による並列実行ヘルパー（利用者側の責務）
- `aclose()` の自動呼び出し（`atexit` 等）— 利用者が明示的に呼ぶ設計
- `async_session()` コンテキストマネージャ（需要が出たら追加）
- XBRL パーサー（Day 9 以降）

---

## 3. 実装対象ファイル

| ファイル | 操作 | 目的 |
|---|---|---|
| `pyproject.toml` | 追記 | `pytest-asyncio` を dev 依存に追加 |
| `src/edinet/_http.py` | 追記 | `_get_async_client()`, `aget()`, `ainvalidate_client()`, `aclose()`, リトライ判定共通化 |
| `src/edinet/api/documents.py` | 追記 | `aget_documents()` |
| `src/edinet/api/download.py` | 追記 | `adownload_document()` |
| `src/edinet/public_api.py` | 追記 | `adocuments()` |
| `src/edinet/models/filing.py` | 追記 | `afetch()` |
| `src/edinet/__init__.py` | 追記 | `adocuments`, `aclose` を lazy export に追加 |
| `tests/test_http.py` | 追記 | `aget()` のテスト |
| `tests/test_api/test_documents.py` | 追記 | `aget_documents()` のテスト |
| `tests/test_api/test_download.py` | 追記 | `adownload_document()` のテスト |
| `tests/test_api/test_public_api.py` | 追記 | `adocuments()` のテスト |
| `tests/test_models/test_filing.py` | 追記 | `afetch()` のテスト |
| `tests/test_large/test_documents_smoke.py` | 追記 | async Large smoke |
| `bench_bulk_download.py` | 追記 | async ベンチマーク追加 |
| `docs/MEMO.md` | 追記 | Day 7.5 決定事項 |

**Note**: stubs は全て `uv run stubgen src/edinet --include-docstrings -o stubs` で
自動生成する。手書き追記はしない。

---

## 4. 層別の詳細設計

### 4-1. `src/edinet/_http.py` — async HTTP 通信層

#### a) リトライ判定の共通化（sync/async 二重メンテ防止）

同期版 `get()` と async 版 `aget()` のリトライロジック（約 60 行）がコピーになると、
同じバグを 2 箇所直す保守コストが生じる。レスポンス評価を純粋関数に抽出し、
IO 部分（`sleep` / `await asyncio.sleep`）だけを差し替える。

```python
@dataclass(frozen=True)
class _RetryDecision:
    """1 回のリクエスト結果からのリトライ判定。"""
    should_retry: bool
    wait_seconds: float
    exception: EdinetError | None

def _evaluate_response(
    response: httpx.Response | None,
    *,
    transport_error: httpx.TransportError | None,
    attempt: int,
    max_retries: int,
    path: str,
) -> _RetryDecision:
    """レスポンスまたは transport エラーを評価し、リトライ判定を返す。

    純粋関数のため sync/async 共通で使用する。

    Args:
        response: HTTP レスポンス（transport エラー時は None）。
        transport_error: transport 層の例外（正常時は None）。
        attempt: 現在の試行回数（1 始まり）。
        max_retries: 最大試行回数。
        path: リクエストパス（ログ用）。

    Returns:
        リトライ判定。
    """
    ...
```

これにより sync 版 / async 版はそれぞれ以下のように簡潔になる:

```python
# sync
def get(path, params=None):
    ...
    for attempt in range(1, max_retries + 1):
        _wait_for_rate_limit()
        _record_request_time()
        response, transport_err = None, None
        try:
            response = client.get(path, params=request_params)
        except httpx.TransportError as exc:
            transport_err = exc
        decision = _evaluate_response(
            response, transport_error=transport_err,
            attempt=attempt, max_retries=max_retries, path=path,
        )
        if not decision.should_retry:
            if decision.exception:
                raise decision.exception
            return response
        last_exception = decision.exception
        time.sleep(decision.wait_seconds)
    raise EdinetError(...)

# async — IO だけ違う
async def aget(path, params=None):
    ...
    for attempt in range(1, max_retries + 1):
        await _async_wait_for_rate_limit()
        _async_record_request_time()
        response, transport_err = None, None
        try:
            response = await client.get(path, params=request_params)
        except httpx.TransportError as exc:
            transport_err = exc
        decision = _evaluate_response(...)  # 同じ純粋関数
        if not decision.should_retry:
            ...
        await asyncio.sleep(decision.wait_seconds)
    ...
```

`_evaluate_response()` は純粋関数なので単体テストも書ける。

#### b) モジュールレベル状態の追加

```python
_async_client: httpx.AsyncClient | None = None
_async_last_request_time: float = 0.0
_async_rate_limit_lock: asyncio.Lock | None = None  # 遅延初期化
```

同期クライアントとは完全に別管理。グローバル変数は同期/async それぞれに独立させ、
相互干渉を防ぐ。

#### c) `_get_async_client() -> httpx.AsyncClient`

`_get_client()` のミラー。`httpx.AsyncClient` を返す。
設定（base_url, timeout, limits, headers）は同期版と完全に同じ。

#### d) レート制限に `asyncio.Lock`

複数コルーチンが同時にレート制限チェックに入ると、全員が同じ `elapsed` を読んで
短い sleep 後に同時リクエストを発行する。`asyncio.Lock` でシリアライズする。

```python
def _get_async_rate_limit_lock() -> asyncio.Lock:
    """asyncio.Lock の遅延初期化。

    モジュール読み込み時にはイベントループが存在しない可能性があるため、
    初回呼び出し時に生成する。
    """
    global _async_rate_limit_lock
    if _async_rate_limit_lock is None:
        _async_rate_limit_lock = asyncio.Lock()
    return _async_rate_limit_lock

async def _async_wait_for_rate_limit() -> None:
    """レート制限制御（async 版）。Lock で同時アクセスをシリアライズする。"""
    global _async_last_request_time
    config = get_config()
    async with _get_async_rate_limit_lock():
        now = time.monotonic()
        elapsed = now - _async_last_request_time
        if _async_last_request_time > 0 and elapsed < config.rate_limit:
            await asyncio.sleep(config.rate_limit - elapsed)
        # Lock 内でリクエスト時刻を記録 → 次のコルーチンが正しい elapsed を見る
        _async_last_request_time = time.monotonic()
```

**同期版との違い**: 同期版は GIL + シングルスレッド前提なので Lock 不要。
async 版はイベントループ内で複数コルーチンが競合するため Lock が必要。

#### e) `ainvalidate_client() -> None`

```python
async def ainvalidate_client() -> None:
    """既存の async クライアントを破棄し、レート制限状態もリセットする。"""
    global _async_client, _async_last_request_time, _async_rate_limit_lock
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
    _async_last_request_time = 0.0
    _async_rate_limit_lock = None
```

命名は `a` prefix に統一（`invalidate_async_client` ではなく `ainvalidate_client`）。

#### f) `aclose() -> None`

```python
async def aclose() -> None:
    """async HTTP クライアントを閉じる。"""
    await ainvalidate_client()
```

同期版 `close()` と対称。`__init__.py` からエクスポートし、利用者が明示的に
クリーンアップできるようにする。

### 4-2. `src/edinet/api/documents.py` — `aget_documents()`

```python
async def aget_documents(
    date: str, *, include_details: bool = True
) -> dict[str, Any]:
```

`get_documents()` と完全に同じロジック。差分は `_http.get()` → `await _http.aget()` のみ。
JSON パース・バリデーション・エラー解釈は同期と共通のヘルパー関数を再利用。

レスポンスの検証ロジック（JSON パース、401 形式検査、metadata.status 検査）は
同期版と共通化する:

```python
def _validate_documents_response(response: httpx.Response) -> dict[str, Any]:
    """get_documents / aget_documents 共通のレスポンス検証。

    Args:
        response: HTTP レスポンス。

    Returns:
        検証済みの API レスポンス dict。

    Raises:
        EdinetAPIError: レスポンスが不正な場合。
    """
    ...

def get_documents(date, *, include_details=True):
    response = _http.get(...)
    return _validate_documents_response(response)

async def aget_documents(date, *, include_details=True):
    response = await _http.aget(...)
    return _validate_documents_response(response)  # 同じ関数
```

### 4-3. `src/edinet/api/download.py` — `adownload_document()`

```python
async def adownload_document(
    doc_id: str,
    *,
    file_type: DownloadFileType | str = DownloadFileType.XBRL_AND_AUDIT,
) -> bytes:
```

差分は `_http.get()` → `await _http.aget()` のみ。
入力バリデーション・Content-Type 検証・ZIP サイズ制限は同じ。

`get_documents()` と同様、HTTP リクエスト後のレスポンス検証ロジックを共通化する:

```python
def _validate_and_normalize_download_params(
    doc_id: str, file_type: DownloadFileType | str,
) -> tuple[str, DownloadFileType]:
    """入力バリデーション（sync/async 共通）。"""
    ...

def _validate_download_response(
    response: httpx.Response, normalized_file_type: DownloadFileType,
) -> bytes:
    """レスポンス検証（sync/async 共通）。"""
    ...
```

ZIP ヘルパー（`list_zip_members`, `find_primary_xbrl_path`, `extract_zip_member`,
`extract_primary_xbrl`）は **async 化しない**。CPU バウンドでありメモリ上のバイト列を
処理するだけのため、async にする意味がない。

### 4-4. `src/edinet/public_api.py` — `adocuments()`

```python
async def adocuments(
    date: str | DateType | None = None,
    *,
    start: str | DateType | None = None,
    end: str | DateType | None = None,
    doc_type: DocType | str | None = None,
    edinet_code: str | None = None,
    on_invalid: Literal["skip", "error"] = "skip",
) -> list[Filing]:
```

同期版 `documents()` のミラー。差分:

| 同期版 | async 版 |
|---|---|
| `get_documents(...)` | `await aget_documents(...)` |
| `from edinet.api.documents import get_documents` | `from edinet.api.documents import aget_documents` |

日付ループ内の `_prepare_response_for_filing_parse()` と行ごとの
`Filing.from_api_response()` は CPU 処理のため同期のまま呼ぶ。

**注意**: `adocuments()` は日付範囲の各日を **逐次** `await` する。
日付範囲の並列化（`asyncio.gather` で複数日を同時取得）は利用者側の責務とし、
ライブラリ側では提供しない。理由:

1. 一覧取得のボトルネックは小さい（12 日分で 17 秒）。本当のボトルネックは `afetch()` の並列化
2. EDINET API のレート制限（1 秒間隔）により一覧取得の並列化効果は限定的
3. ライブラリが暗黙に `gather` すると、エラーハンドリングの制御が利用者から奪われる

### 4-5. `src/edinet/models/filing.py` — `afetch()`

```python
async def afetch(self, *, refresh: bool = False) -> tuple[str, bytes]:
```

同期版 `fetch()` のミラー。差分:

| 同期版 | async 版 |
|---|---|
| `download_document(...)` | `await adownload_document(...)` |

`_zip_cache`, `_xbrl_cache` は同期版と共有する。
キャッシュヒット時は `await` 不要で即座に返る。

### 4-6. `src/edinet/__init__.py` — エクスポート追加

`_LAZY_EXPORTS` に追加:

```python
"adocuments": ("edinet.public_api", "adocuments"),
"aclose": ("edinet._http", "aclose"),
```

`__all__` に `"adocuments"`, `"aclose"` を追加。
`if TYPE_CHECKING:` ブロックにも対応する import を追加。

---

## 5. テスト設計

### 5-1. `pytest-asyncio` 導入

`pyproject.toml` の dev 依存に追加:

```toml
[dependency-groups]
dev = [
    ...
    "pytest-asyncio>=0.25",
]
```

`pyproject.toml` に asyncio_mode 設定を追加:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### 5-2. テスト方針

各層の async 関数に対し、同期版と **対称的な** テストを書く。
全件コピーではなく、以下の観点に絞る:

- **正常系 1 件**: 同期版と同じ結果が返ること
- **エラー系 1 件**: 同期版と同じ例外が飛ぶこと
- **async 固有**: `await` で呼べること（型レベルの検証）

### 5-3. 各テストファイルの追加テスト

#### `tests/test_http.py`

| テスト名 | 内容 |
|---|---|
| `test_aget_returns_response` | `aget()` が正常レスポンスを返すこと |
| `test_aget_retries_on_transport_error` | TransportError でリトライすること |
| `test_aget_raises_on_client_error` | 4xx で即座に `EdinetAPIError` |
| `test_ainvalidate_client` | `ainvalidate_client()` でクライアントが破棄されること |
| `test_aget_429_retry_with_retry_after` | 429 リトライ + Retry-After ヘッダ解析 |
| `test_aclose_idempotent` | `aclose()` を 2 回呼んでもエラーにならないこと |
| `test_evaluate_response_unit` | `_evaluate_response()` 純粋関数の単体テスト |

#### `tests/test_api/test_documents.py`

| テスト名 | 内容 |
|---|---|
| `test_aget_documents_returns_dict` | 正常な dict を返すこと |
| `test_aget_documents_raises_on_api_error` | API エラーで `EdinetAPIError` |

#### `tests/test_api/test_download.py`

| テスト名 | 内容 |
|---|---|
| `test_adownload_document_returns_bytes` | 正常な bytes を返すこと |
| `test_adownload_document_raises_on_invalid_doc_id` | 不正 doc_id で `ValueError` |

#### `tests/test_api/test_public_api.py`

| テスト名 | 内容 |
|---|---|
| `test_adocuments_single_date` | 単日取得で `list[Filing]` を返すこと |
| `test_adocuments_on_invalid_skip` | `on_invalid="skip"` で warning + スキップ |
| `test_adocuments_on_invalid_error` | `on_invalid="error"` で `EdinetParseError` |

#### `tests/test_models/test_filing.py`

| テスト名 | 内容 |
|---|---|
| `test_afetch_downloads_primary_xbrl` | `afetch()` が XBRL を返すこと |
| `test_afetch_raises_when_has_xbrl_false` | XBRL なしで `EdinetAPIError` |
| `test_afetch_uses_cache` | キャッシュヒットで `await` が即座に返ること |

#### `tests/test_large/test_documents_smoke.py`

| テスト名 | 内容 |
|---|---|
| `test_adocuments_real_api_smoke` | 実 API で `adocuments()` が動くこと |

### 5-4. conftest.py の async teardown

`asyncio_mode = "auto"` では `async def` fixture は async テストでのみ実行される。
同期テストでも async クライアントの残骸をクリーンアップするため、
同期関数で強制リセットする **テスト専用** ヘルパーを `_http.py` に追加する:

```python
def _reset_async_state_for_testing() -> None:
    """async クライアントのグローバル状態を強制リセットする。

    テスト用。await なしでクライアントを破棄するため、
    本番コードでは使用しないこと。
    """
    global _async_client, _async_last_request_time, _async_rate_limit_lock
    if _async_client is not None:
        # イベントループが閉じている可能性があるため、
        # aclose() は呼ばず参照を切るだけにする。
        # テスト環境では GC に任せて問題ない。
        _async_client = None
    _async_last_request_time = 0.0
    _async_rate_limit_lock = None
```

`tests/conftest.py` の `_reset_config` fixture に追加:

```python
@pytest.fixture(autouse=True)
def _reset_config():
    yield
    _reset_for_testing()
    from edinet._http import invalidate_client, _reset_async_state_for_testing
    invalidate_client()
    _reset_async_state_for_testing()
```

### 5-5. monkeypatch の方針

async テストでも `monkeypatch.setattr` で同期版と同じ fake を差し込む。
`aget()` のテストでは `_http.aget` を `async def fake_aget(...)` に差し替える。

例:

```python
async def test_aget_documents_returns_dict(monkeypatch):
    async def fake_aget(path, params=None):
        return FakeResponse(200, json_data={...})

    monkeypatch.setattr("edinet._http.aget", fake_aget)
    result = await aget_documents("2026-02-07")
    assert isinstance(result, dict)
```

---

## 6. `bench_bulk_download.py` の async モード追加

`--mode sync|async` フラグを追加し、async 版 `afetch()` + `asyncio.Semaphore` で
並列ダウンロードする Phase 2a を追加。

**Note**: `--async` は Python 予約語と衝突し `args.async` でアクセスできないため
`--mode` を採用する。

```python
async def _fetch_one(sem, filing):
    async with sem:
        _, data = await filing.afetch()
        filing.clear_fetch_cache()
        return len(data)

async def bench_async(targets, concurrency=5):
    sem = asyncio.Semaphore(concurrency)
    tasks = [_fetch_one(sem, f) for f in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    ...
```

`--concurrency N` でセマフォ数を指定可能にする。デフォルトは 5（レート制限 1s の
EDINET API に対して、ネットワーク RTT + ダウンロード時間を考慮した安全値）。

---

## 7. 作業手順（チェックリスト）

**Phase 1: 依存追加**
1. `pyproject.toml` に `pytest-asyncio` 追加、`asyncio_mode = "auto"` 設定
2. `uv sync` で依存解決

**Phase 2: HTTP 層**
3. `_http.py` に `_RetryDecision` + `_evaluate_response()` 抽出（sync 版リファクタ）
4. `_http.py` に `_async_client`, `_get_async_client()`, `aget()`, `ainvalidate_client()`, `aclose()`, `_reset_async_state_for_testing()` 追加
5. `tests/test_http.py` に async テスト + `_evaluate_response` 単体テスト追加
6. `tests/conftest.py` に `_reset_async_state_for_testing()` 呼び出し追加

**Phase 3: API ラッパー層**
7. `api/documents.py` のレスポンス検証を `_validate_documents_response()` に抽出 + `aget_documents()` 追加 + テスト
8. `api/download.py` のバリデーションを共通関数に抽出 + `adownload_document()` 追加 + テスト

**Phase 4: 公開 API + モデル層**
9. `public_api.py` に `adocuments()` 追加 + テスト
10. `models/filing.py` に `afetch()` 追加 + テスト
11. `__init__.py` に `adocuments`, `aclose` エクスポート追加

**Phase 5: 検証**
12. `uv run pytest` — 全テスト通過（既存同期テスト + 新規 async テスト）
13. `uv run ruff check src tests` — All checks passed
14. `uv run stubgen src/edinet --include-docstrings -o stubs` — stubs 自動生成
15. `uv run pytest -m large` — async Large smoke 通過

**Phase 6: ベンチマーク + ドキュメント**
16. `bench_bulk_download.py` に `--mode async` + `--concurrency N` 追加
17. `docs/MEMO.md` に Day 7.5 決定事項追記

---

## 8. 受け入れ基準（Done の定義）

- 既存の同期テスト 234 件が **1 件も壊れていない**
- `aget()`, `aget_documents()`, `adownload_document()`, `adocuments()`, `afetch()` の各 async 関数にテストがある
- `_evaluate_response()` の単体テストがある
- `edinet.adocuments("2025-01-15")` が実 API で動作する（Large テスト）
- `bench_bulk_download.py --mode async --max-fetch 10` で同期版比で速度改善が確認できる
- `uv run ruff check src tests` が All checks passed
- stubs が `stubgen` 出力と一致
- `edinet.aclose()` が `__init__.py` からエクスポートされている

---

## 9. リスクと対策

| リスク | 対策 |
|---|---|
| 並列時にレート制限に引っかかる | `asyncio.Lock` でレート制限チェックをシリアライズ + 429 リトライが同期版と同じく動く |
| テストで event loop が正しく管理されない | `pytest-asyncio` の `asyncio_mode = "auto"` + conftest の `_reset_async_state_for_testing()` |
| 同期版との二重メンテコスト | `_evaluate_response()`, `_validate_documents_response()`, `_validate_download_response()` で判定ロジックを共通化。async 版は IO の差し替えのみ |
| `conftest.py` の teardown で async client が漏れる | `_reset_async_state_for_testing()` で同期的に強制リセット |
| Jupyter でイベントループ変更時に古いクライアントが残る | `ainvalidate_client()` / `aclose()` で明示クリーンアップ。`_get_async_client()` は毎回設定を確認し、必要なら再生成 |

---

## 10. Day 8 への引き継ぎ

- async transport 層が完成し、`adocuments()` / `afetch()` が使える状態
- Day 8 は XBRL 仕様読解に集中（async は使わない）
- Day 9 以降の XBRL パーサーは同期で実装し、大量取得時のみ async transport を活用
- ベンチマーク結果は `docs/MEMO.md` に記録済み
- 利用者の典型パターン:
  ```python
  # Phase 1: 一覧取得（同期 — 高速なので async 不要）
  filings = edinet.documents(start=..., end=..., doc_type="120")

  # Phase 2: XBRL 並列ダウンロード（async — ボトルネックはここ）
  async def download_all(filings, concurrency=5):
      sem = asyncio.Semaphore(concurrency)
      async def fetch_one(f):
          async with sem:
              return await f.afetch()
      return await asyncio.gather(*[fetch_one(f) for f in filings])

  results = asyncio.run(download_all(filings))

  # Phase 3: XBRL パース（同期 — CPU バウンド）
  for path, data in results:
      parsed = parse_xbrl(data)
  ```

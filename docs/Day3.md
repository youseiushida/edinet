# Day 3 — HTTP クライアント + 書類一覧 API（1.5h）

## 目標

Day 3 の終了時に以下が動くこと:

```python
from edinet._config import configure
from edinet.api.documents import get_documents

configure(api_key="your-api-key")
result = get_documents("2026-02-07")
print(result)  # → JSON レスポンスの dict が返る
```

edinet-tools の致命的欠陥（タイムアウトなし・レート制限なし・import 時副作用）を最初から回避する。

---

## 実装対象ファイル

| ファイル | 役割 | 行数目安 |
|----------|------|----------|
| `src/edinet/_version.py` | バージョン定義（1行） | 1行 |
| `src/edinet/_config.py` | 設定管理（副作用なし） | ~50行 |
| `src/edinet/_http.py` | HTTP クライアント（リトライ・レート制限・接続プーリング） | ~120行 |
| `src/edinet/api/documents.py` | 書類一覧 API ラッパー | ~60行 |

### `_version.py`（1行）

```python
__version__ = "0.1.0"
```

バージョンを 1 箇所で管理する。`_http.py` の User-Agent から参照する。

**バージョン single source of truth**:
現在 `pyproject.toml` にも `version = "0.1.0"` がある（二重管理）。
Day 3 の実装時に `pyproject.toml` を以下のように変更して `_version.py` を正とする:

現在の `pyproject.toml` には `[build-system]` が未指定。
`uv` はデフォルトで `hatchling` を使うので、実装時に以下を確認して設定する:

```toml
# [build-system] を確認し、hatchling なら:
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
dynamic = ["version"]

[tool.hatch.version]
path = "src/edinet/_version.py"
```

```toml
# setuptools の場合:
[tool.setuptools.dynamic]
version = {attr = "edinet._version.__version__"}
```

実装の最初の 1 分でビルドバックエンドを確認し、上記のどちらかを適用する。
これにより `_version.py` だけ更新すればバージョンが全体に反映される。

---

## 1. `_config.py` — 設定管理

### 設計方針

- **import 時の副作用ゼロ**: `import edinet` しただけで `.env` を読んだり warning を出したりしない。`configure()` を明示的に呼んで初めて設定が有効になる
- edinet-tools は `import` 時に `load_dotenv()` + `logging.warning()` が走る → これを完全に回避する
- API キーは `_config.py` 内でのみ保持し、ログや例外メッセージに絶対に混入させない

### クラス設計

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --- 例外クラス（_Config より先に定義する。可読性のため） ---

class EdinetError(Exception):
    """edinet ライブラリの基底例外。"""

class EdinetConfigError(EdinetError):
    """設定に関するエラー。"""

class EdinetAPIError(EdinetError):
    """EDINET API からのエラーレスポンス。"""
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"EDINET API error {status_code}: {message}")


# sentinel: 「引数が渡されなかった」と「None が渡された」を区別する
_UNSET: Any = object()


@dataclass
class _Config:
    """ライブラリのグローバル設定。直接インスタンス化しない。"""

    api_key: str | None = field(default=None, repr=False)  # repr=False: print時にキーを隠す
    base_url: str = "https://api.edinet-fsa.go.jp/api/v2"
    timeout: float = 30.0      # 秒
    max_retries: int = 3
    rate_limit: float = 1.0    # リクエスト間隔（秒）。デフォルトは保守的に1.0秒
    taxonomy_path: str | None = None  # Day 12 で使用

    def ensure_api_key(self) -> str:
        """API キーが設定されていなければ EdinetConfigError を送出。"""
        if self.api_key is None:
            raise EdinetConfigError(
                "API key is not configured. Call edinet.configure(api_key='...') first."
            )
        return self.api_key


# モジュールレベルのシングルトン（import 時に副作用なし）
_global_config = _Config()

# クライアントに影響するパラメータ。これらが変更されたらクライアントを無効化する
_CLIENT_PARAMS = {"base_url", "timeout"}


def configure(
    *,
    api_key: str | None = _UNSET,
    base_url: str = _UNSET,
    timeout: float = _UNSET,
    max_retries: int = _UNSET,
    rate_limit: float = _UNSET,
    taxonomy_path: str | None = _UNSET,
) -> None:
    """ライブラリのグローバル設定を更新する。

    引数を省略した場合はその項目を変更しない。
    api_key / taxonomy_path は None を渡すとクリアできる。
    base_url / timeout / max_retries / rate_limit は None 不可
    （httpx.Client 等が壊れるため）。

    呼び出し例:
        edinet.configure(api_key="your-api-key")
        edinet.configure(api_key="your-api-key", rate_limit=0.5)
        edinet.configure(api_key=None)  # API キーをクリア
    """
    global _global_config
    need_invalidate = False
    updates: dict[str, Any] = {}

    # 各引数を _UNSET でなければ更新対象に登録
    if api_key is not _UNSET:
        updates["api_key"] = api_key
    if base_url is not _UNSET:
        updates["base_url"] = base_url
    if timeout is not _UNSET:
        updates["timeout"] = timeout
    if max_retries is not _UNSET:
        updates["max_retries"] = max_retries
    if rate_limit is not _UNSET:
        updates["rate_limit"] = rate_limit
    if taxonomy_path is not _UNSET:
        updates["taxonomy_path"] = taxonomy_path

    # ランタイムバリデーション: 型ヒントだけでは Python は None を弾かない。
    # Day 6 以降どこから configure() が呼ばれても壊れた設定が入らないよう、
    # ここで実行時に検証する。
    _NOT_NONE = {"base_url", "timeout", "max_retries", "rate_limit"}
    for name in _NOT_NONE:
        if name in updates and updates[name] is None:
            raise EdinetConfigError(
                f"{name} must not be None. "
                f"Only api_key and taxonomy_path can be cleared with None."
            )
    if "timeout" in updates and updates["timeout"] <= 0:
        raise EdinetConfigError("timeout must be positive")
    if "max_retries" in updates and updates["max_retries"] < 1:
        raise EdinetConfigError("max_retries must be >= 1")
    if "rate_limit" in updates and updates["rate_limit"] < 0:
        raise EdinetConfigError("rate_limit must be >= 0")

    # 設定を反映し、_CLIENT_PARAMS に該当するものがあれば invalidate フラグを立てる
    for name, value in updates.items():
        setattr(_global_config, name, value)
        if name in _CLIENT_PARAMS:
            need_invalidate = True

    # base_url / timeout が変更された場合、既存の httpx.Client を破棄して
    # 次の get() で再生成する（古い設定のクライアントが残る事故を防止）
    # 注意: `from edinet import _http` はパッケージ __init__.py を経由するため、
    # Day 6 で __init__.py に configure を公開した瞬間に循環 import になる。
    # 相対 import で直接モジュールを指定して回避する。
    if need_invalidate:
        from ._http import invalidate_client
        invalidate_client()


def get_config() -> _Config:
    """現在のグローバル設定を返す（内部用）。"""
    return _global_config


def _reset_for_testing() -> None:
    """テスト用: グローバル設定をデフォルトに戻す。

    _Config() のデフォルト値を正とするため、conftest.py でデフォルト値を
    ハードコードする必要がない（二重管理を防止）。
    """
    global _global_config
    _global_config = _Config()
```

### sentinel パターンの解説

```python
# ❌ 旧: if api_key is not None: だと None でクリアできない
configure(api_key=None)  # → 何も起きない（バグ）

# ✅ 新: _UNSET sentinel で「渡されなかった」と「None を渡した」を区別
configure(api_key=None)  # → api_key が None にクリアされる
configure()              # → 何も変更されない（意図通り）
```

### None 許容ルール

```
None でクリアできる引数:
  api_key       → None = 未設定に戻す（テストのクリーンアップ等）
  taxonomy_path → None = パスをクリア

None を許可しない引数（渡すと httpx.Client 等が壊れる）:
  base_url      → str 必須（httpx.Client(base_url=None) はエラー）
  timeout       → float 必須（httpx.Timeout(None) はエラー）
  max_retries   → int 必須
  rate_limit    → float 必須

型ヒントで区別:
  api_key: str | None = _UNSET    ← None 許容
  base_url: str = _UNSET          ← None 不可

ランタイム検証（型ヒントだけでは Python は None を弾かないため）:
  configure(base_url=None)  → EdinetConfigError
  configure(timeout=-1)     → EdinetConfigError
  configure(max_retries=0)  → EdinetConfigError
  configure(rate_limit=-1)  → EdinetConfigError
```

### 例外クラス

※ 例外クラス（`EdinetError`, `EdinetConfigError`, `EdinetAPIError`）は `_Config` より上に定義済み。
`ensure_api_key()` が `EdinetConfigError` を参照するため、可読性の観点から先に定義する。

### 判断ポイント

| 項目 | 判断 | 理由 |
|------|------|------|
| dataclass vs Pydantic | dataclass | 設定は内部管理用。Pydantic はドメインモデルに使う。最低限のバリデーション（None 禁止・値域チェック）は `configure()` 側で行う |
| シングルトン vs DI | シングルトン | edgartools も同様。テスト時は `configure()` で切り替え可能 |
| `repr=False` on api_key | 採用 | `print(config)` で API キーが漏洩しない |
| 例外の定義場所 | `_config.py` に一旦置く | 将来 `_exceptions.py` に分離してもよいが、Day 3 時点ではファイル数を増やさない |

### チェックリスト

- [ ] `import edinet` で副作用が一切発生しないこと
- [ ] `configure()` を呼ばずに API を叩くと `EdinetConfigError` が出ること
- [ ] `print(_global_config)` で API キーが表示されないこと
- [ ] 全引数が keyword-only（`*` の後ろ）であること

---

## 2. `_http.py` — HTTP クライアント

### 設計方針

- **httpx.Client** を使う。`requests` ではなく `httpx` を選んだ理由: 同期/非同期の両対応が可能で、v0.2.0 で `asyncio` 化するときにインターフェースを維持できる
- edinet-tools は `urllib.request.urlopen()` にタイムアウトなし → 無限ハング。httpx ならデフォルトでタイムアウトが設定できる
- API キーはリクエストパラメータとして `Subscription-Key` に付与する（EDINET API 仕様書 §3-1-1 参照）

### EDINET API のリクエスト仕様（API 仕様書 §3-1-1 より）

```
書類一覧 API:
  GET https://api.edinet-fsa.go.jp/api/v2/documents.json
    ?date=YYYY-MM-DD
    &type=1|2
    &Subscription-Key=APIキー

書類取得 API（Day 5 で実装）:
  GET https://api.edinet-fsa.go.jp/api/v2/documents/{docID}
    ?type=1|2|3|4|5
    &Subscription-Key=APIキー
```

### リトライ仕様（PLAN.md §9 Day 3 より、固定で小さく保つ）

| ステータス | 挙動 | 理由 |
|-----------|------|------|
| **429** (Too Many Requests) | `Retry-After` ヘッダに従って待つ。ヘッダがなければ 60 秒待つ | レート制限。必ずリトライする |
| **5xx** (Server Error) | 指数バックオフ（1s → 2s → 4s）+ jitter で最大3回 | サーバー側の一時障害 |
| **4xx** (429 以外) | リトライしない。即座にエラー | クライアント側のミス（日付形式エラー等） |
| **ネットワークエラー** | 5xx と同じルールでリトライ | 一時的な接続障害 |

### レート制限

```
デフォルト: 1.0 秒間隔（保守的）
変更方法: configure(rate_limit=0.5) で利用者が調整可能
実装方式: 最後のリクエスト時刻を記録し、次のリクエスト前に time.sleep() で待つ
EDINET API の公式レート制限は非公開のため、安全寄りのデフォルト値
```

### 接続プーリング

```python
# httpx.Client のデフォルトプーリング設定を明示する
limits = httpx.Limits(
    max_connections=10,      # 同時接続数の上限
    max_keepalive_connections=5,  # keep-alive 接続の上限
)
```

### クラス設計

```python
from __future__ import annotations

import logging
import time
from random import uniform
from typing import Any

import httpx

from edinet._config import (
    EdinetAPIError,
    EdinetError,
    get_config,
)
from edinet._version import __version__

logger = logging.getLogger(__name__)

# モジュールレベルで保持するクライアントインスタンス
_client: httpx.Client | None = None
_last_request_time: float = 0.0


def _get_client() -> httpx.Client:
    """httpx.Client のシングルトンを返す。初回呼び出し時に生成。"""
    global _client
    config = get_config()
    if _client is None:
        _client = httpx.Client(
            base_url=config.base_url,
            # タイムアウトを connect/read/write/pool に分割して定義する。
            # 現時点では全て同じ値だが、将来「接続は短く、読み取りは長く」等の
            # 調整が必要になったとき、この形なら個別に変更できる。
            timeout=httpx.Timeout(
                connect=config.timeout,
                read=config.timeout,
                write=config.timeout,
                pool=config.timeout,
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
            # __version__ を参照して UA を生成（ハードコードだと公開時にズレる）
            headers={"User-Agent": f"edinet-python/{__version__}"},
        )
    return _client


def invalidate_client() -> None:
    """既存の httpx.Client を破棄し、レート制限状態もリセットする。

    configure() で base_url/timeout が変更された際に呼ばれる。
    次の get() 呼び出しで新しい設定のクライアントが自動再生成される。
    _last_request_time もリセットしないとテスト間で rate_limit の
    状態が残り、次テストの最初のリクエストで不要な sleep が発生する。
    """
    global _client, _last_request_time
    if _client is not None:
        _client.close()
        _client = None
    _last_request_time = 0.0


def _redact(text: str, secret: str) -> str:
    """文字列中の secret を '***' に置換する。API キー漏洩防止用。"""
    return text.replace(secret, "***") if secret else text


def _wait_for_rate_limit() -> None:
    """レート制限: 前回リクエストから rate_limit 秒が経過するまで待つ。"""
    global _last_request_time
    config = get_config()
    now = time.monotonic()
    elapsed = now - _last_request_time
    if _last_request_time > 0 and elapsed < config.rate_limit:
        sleep_time = config.rate_limit - elapsed
        logger.debug("Rate limit: sleeping %.2f seconds", sleep_time)
        time.sleep(sleep_time)


def _record_request_time() -> None:
    """リクエスト「開始」時刻を記録する。

    レスポンス受信後ではなく送信直前に記録することで、
    サーバーの応答時間に関わらず一定の「リクエスト開始間隔」を保つ。
    """
    global _last_request_time
    _last_request_time = time.monotonic()


def get(path: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """EDINET API に GET リクエストを送信する。

    - API キーは自動付与（利用者が触る必要なし）
    - レート制限・リトライを自動処理

    Args:
        path: API のパス（例: "/documents.json"）
        params: クエリパラメータ（date, type 等）

    Returns:
        httpx.Response

    Raises:
        EdinetConfigError: API キーが未設定
        EdinetAPIError: EDINET API がエラーレスポンスを返した
    """
    config = get_config()
    api_key = config.ensure_api_key()
    client = _get_client()

    # API キーをパラメータに付与
    request_params = dict(params or {})
    request_params["Subscription-Key"] = api_key

    # RULE: last_exception には必ず EdinetError / EdinetAPIError を入れる。
    # httpx の生の例外（TransportError 等）を保持しない。
    # 理由: httpx 例外の repr/str にはリクエスト URL（API キー入り）が含まれる
    # ことがあり、例外チェーンやログ経由でキーが漏洩するリスクがある。
    last_exception: EdinetError | None = None

    # NOTE: max_retries は「総試行回数」を意味する（初回含む）。
    # 例: max_retries=3 → 最大3回試行（初回 + リトライ2回）。
    # 一般的な「リトライ回数 = 追加試行回数」とは異なるので注意。
    # ⚠ PLAN.md L624 に「リトライ3回」L628 に「最大3回」の記述あり。
    # Day3.md では max_retries=3 を「総試行3回」と定義する。
    # PLAN.md の「リトライ3回」は「バックオフで最大3回試行」の意味で統一する。
    for attempt in range(1, config.max_retries + 1):
        _wait_for_rate_limit()

        try:
            # リクエスト「開始」間隔を制御する（_record_request_time の docstring 参照）
            _record_request_time()
            response = client.get(path, params=request_params)
        except httpx.TransportError as exc:
            # ネットワークエラー: リトライ
            # CRITICAL: キー漏洩ゼロを最優先し、例外メッセージは固定文言にする。
            # httpx の例外は str(exc) / repr(exc) にリクエスト URL（API キー入り）
            # を含む可能性があり、_redact() でも percent-encode 等で漏れうる。
            # logger にも URL / str(exc) を出さない。path + attempt + 例外クラス名のみ。
            logger.debug(
                "Transport error %s on %s (attempt %d/%d)",
                type(exc).__name__, path, attempt, config.max_retries,
            )
            # from exc を使わない → 元の例外（キー入り URL）がチェーンに残らない。
            last_exception = EdinetError("Network error")
            _sleep_before_retry(attempt, config.max_retries)
            continue

        # 成功
        if response.status_code == 200:
            return response

        # 429: Retry-After に従う
        # NOTE: Retry-After sleep 後、次ループで再び rate_limit sleep が入るため
        # 合計待ち時間は Retry-After + rate_limit になる可能性がある（安全側）。
        # Retry-After が十分長ければ rate_limit は実質ゼロコストだが、
        # 短い場合に二重待ちが発生する。これは「安全寄り」の設計判断として許容する。
        if response.status_code == 429:
            retry_after = _parse_retry_after(response)
            logger.warning(
                "Rate limited (429). Retrying after %d seconds (attempt %d/%d)",
                retry_after, attempt, config.max_retries,
            )
            time.sleep(retry_after)
            last_exception = EdinetAPIError(429, "Too Many Requests")
            continue

        # 5xx: 指数バックオフでリトライ
        if response.status_code >= 500:
            last_exception = EdinetAPIError(
                response.status_code,
                _safe_message(response),
            )
            _sleep_before_retry(attempt, config.max_retries)
            continue

        # 4xx (429以外): リトライしない、即座にエラー
        raise EdinetAPIError(
            response.status_code,
            _safe_message(response),
        )

    # 全リトライ失敗（from last_exception を使わない: 元例外に URL が含まれる可能性）
    raise EdinetError(
        f"Request failed after {config.max_retries} attempts: {last_exception}"
    )


def _sleep_before_retry(attempt: int, max_retries: int) -> None:
    """指数バックオフ + jitter で待つ。最後の試行後は待たない。"""
    if attempt >= max_retries:
        return
    base_delay = 2 ** (attempt - 1)  # 1s, 2s, 4s
    jitter = uniform(0, base_delay * 0.5)  # 最大50%のランダムジッタ
    delay = base_delay + jitter
    logger.debug(
        "Retrying in %.2f seconds (attempt %d/%d)",
        delay, attempt, max_retries,
    )
    time.sleep(delay)


def _parse_retry_after(response: httpx.Response) -> int:
    """Retry-After ヘッダを解析して秒数を返す。ヘッダがなければ60秒。

    制約: EDINET は秒数形式を想定。RFC 7231 で許容される HTTP-date 形式
    （例: "Fri, 31 Dec 2026 23:59:59 GMT"）には未対応。int 変換に失敗した
    場合はフォールバックとして 60 秒を返す。
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(1, int(retry_after))
        except ValueError:
            # HTTP-date 形式の可能性があるが、EDINET では発生しない想定。
            # 安全側として 60 秒を返す。
            pass
    return 60


def _safe_message(response: httpx.Response) -> str:
    """レスポンスからエラーメッセージを安全に抽出する。

    CRITICAL: API キーが含まれる URL をメッセージに入れない。
    """
    try:
        data = response.json()
        return str(data.get("metadata", {}).get("message", "Unknown error"))
    except Exception:  # noqa: BLE001
        # 意図的に広い except。EDINET がメンテナンス中/障害時に HTML (502/503)
        # を返すと json.JSONDecodeError になるが、それ以外の予期しない例外
        # （壊れた JSON 等）も安全に fallback させるため Exception で受ける。
        return f"HTTP {response.status_code}"


def close() -> None:
    """HTTP クライアントを閉じる。テストやシャットダウン時に使用。"""
    invalidate_client()
```

### API キー漏洩防止の設計

API キーがログや例外メッセージに混入しないように、以下のガードを設ける:

| 箇所 | 対策 |
|------|------|
| `_Config.api_key` | `repr=False` で `print()` 時に隠す |
| `_safe_message()` | レスポンスの URL（キー入り）を含めず、JSON の `message` フィールドのみ返す |
| `EdinetAPIError` | `status_code` + `message` のみ。URL は含めない |
| `TransportError` のキャッチ | 例外メッセージは固定文言 `"Network error"`。redact 済み詳細は `logger.debug` のみ。`from exc` は使わない（元例外にキー入り URL が残るため） |
| `last_exception` 変数 | 必ず `EdinetError` / `EdinetAPIError` に正規化してから保持。httpx の生の例外インスタンスは変数に残さない |
| ログ | `logger.debug()` でリクエスト URL をログに出さない |

### チェックリスト

- [ ] タイムアウト 30 秒が設定されていること
- [ ] 429 で `Retry-After` に従ってリトライすること
- [ ] 5xx で指数バックオフ（1s → 2s → 4s）+ jitter でリトライすること
- [ ] 4xx（429以外）でリトライせず即座にエラーになること
- [ ] ネットワークエラーでリトライすること
- [ ] レート制限（デフォルト1.0秒間隔）が動作すること
- [ ] API キーがログ・例外メッセージに混入しないこと（`TransportError` 経由含む）
- [ ] `User-Agent` ヘッダが設定されていること
- [ ] `configure(base_url=...)` でクライアントが自動再生成されること

---

## 3. `api/documents.py` — 書類一覧 API

### EDINET API レスポンス構造（API 仕様書 §3-1-2-2 より）

```json
{
  "metadata": {
    "title": "提出された書類を把握するための API",
    "parameter": {
      "date": "2023-04-03",
      "type": "2"
    },
    "resultset": {
      "count": 2
    },
    "processDateTime": "2023-04-03 13:01",
    "status": "200",
    "message": "OK"
  },
  "results": [
    {
      "seqNumber": 1,
      "docID": "S1000001",
      "edinetCode": "E10001",
      "secCode": "10000",
      "JCN": "6000012010023",
      "filerName": "エディネット株式会社",
      "fundCode": "G00001",
      "ordinanceCode": "030",
      "formCode": "04A000",
      "docTypeCode": "030",
      "periodStart": null,
      "periodEnd": null,
      "submitDateTime": "2023-04-03 12:34",
      "docDescription": "有価証券届出書（内国投資信託受益証券）",
      "issuerEdinetCode": null,
      "subjectEdinetCode": null,
      "subsidiaryEdinetCode": null,
      "currentReportReason": null,
      "parentDocID": null,
      "opeDateTime": null,
      "withdrawalStatus": "0",
      "docInfoEditStatus": "0",
      "disclosureStatus": "0",
      "xbrlFlag": "1",
      "pdfFlag": "1",
      "attachDocFlag": "1",
      "englishDocFlag": "0",
      "csvFlag": "1",
      "legalStatus": "1"
    }
  ]
}
```

### レスポンスフィールド一覧（API 仕様書 §3-1-2-2 の全40項目）

Day 3 の時点では **生の dict を返す**。Pydantic モデル（`Filing`）へのマッピングは Day 4 で行う。

理由: Day 3 の責務は「EDINET API と正しく通信できること」であり、「レスポンスをどうモデリングするか」は Day 4 の責務。責務を混ぜると両方が中途半端になる。

### 実装

```python
"""EDINET 書類一覧 API (documents API) のラッパー。

EDINET API 仕様書 §3-1 参照。
"""
from __future__ import annotations

from typing import Any

from edinet import _http
from edinet._config import EdinetAPIError


def get_documents(date: str, *, include_details: bool = True) -> dict[str, Any]:
    """指定日の提出書類一覧を取得する。

    Args:
        date: ファイル日付（YYYY-MM-DD 形式）。
              当日以前で、10年を経過していない日付。
              土日祝日も指定可能。
        include_details:
            True  → type=2「提出書類一覧及びメタデータ」を取得（デフォルト）
            False → type=1「メタデータのみ」を取得

    Returns:
        EDINET API のレスポンス JSON（dict）。

    Raises:
        EdinetConfigError: API キーが未設定。
        EdinetAPIError: EDINET API がエラーを返した（HTTP エラーまたは
                        レスポンス JSON の metadata.status が "200" 以外）。

    Examples:
        >>> result = get_documents("2026-02-07")
        >>> result["metadata"]["resultset"]["count"]
        42
        >>> result["results"][0]["docID"]
        'S100XXXX'
    """
    response = _http.get(
        "/documents.json",
        params={
            "date": date,
            "type": "2" if include_details else "1",
        },
    )

    # EDINET がメンテナンス中等に HTTP 200 + HTML を返すと
    # response.json() が JSONDecodeError になる。
    # ライブラリ利用者に httpx/json の生例外を見せず EdinetAPIError に変換する。
    try:
        data = response.json()
    except Exception:  # noqa: BLE001
        raise EdinetAPIError(
            response.status_code,
            f"Response is not valid JSON (HTTP {response.status_code})",
        )

    # 401 形式の検査（API 仕様書 §3-3 参照）。
    # 401 だけ JSON 構造が異なる: {"StatusCode": 401, "message": "..."} 。
    # metadata 構造ではないため、先に検査する。
    if "StatusCode" in data:
        raise EdinetAPIError(
            int(data["StatusCode"]),
            str(data.get("message", "Unknown error")),
        )

    # EDINET API は HTTP 200 を返しつつ JSON の metadata.status が
    # "200" 以外のケースがありうる。HTTP ステータスだけでは不十分なので
    # JSON レベルでもステータスを検査する。
    status = str(data.get("metadata", {}).get("status", ""))
    if status != "200":
        message = data.get("metadata", {}).get("message", "Unknown error")
        raise EdinetAPIError(int(status) if status.isdigit() else 0, str(message))

    return data
```

### 判断ポイント

| 項目 | 判断 | 理由 |
|------|------|------|
| 戻り値の型 | `dict[str, Any]`（生の JSON） | Day 4 で Pydantic モデル化する。Day 3 では通信レイヤーに集中 |
| `type` パラメータ | `include_details: bool` で抽象化 | `"1"` / `"2"` の魔法の数字を利用者に見せない |
| `date` のバリデーション | しない（Day 3 時点） | EDINET API がエラーを返すので二重チェック不要。Day 6 で `start`/`end` ヘルパーを作る際に日付バリデーションを入れる |
| API キーの `Subscription-Key` | `_http.get()` 内で自動付与 | 利用者が触る必要なし。漏洩防止も `_http.py` に一元化 |

---

## 4. EDINET API ステータスコード一覧（API 仕様書 §3-3 より）

| ステータスコード | メッセージ | 説明 |
|-----------------|-----------|------|
| 200 | OK | 正常終了 |
| 400 | Bad Request | パラメータ誤り |
| 404 | Not Found | リソースが見つからない |
| 500 | Internal Server Error | サーバーエラー |

これに加えて、実際の運用では **429 (Too Many Requests)** が返る可能性がある（仕様書に明記なし、実運用でレポートあり）。

---

## 5. テスト（Day 3 で最低限書くもの）

### テスト戦略（Day 3 vs Day 7 の切り分け）

```
Day 3（今回）:
  - pure function のユニットテスト（外部通信なし）
    - _config.py: configure() / get_config() / sentinel / バリデーション
    - _http.py: _redact() / キー秘匿の検証
  - 手動テスト: EDINET API 実通信で JSON が返ることを目視確認

Day 7（テスト本格整備）:
  - respx を使った HTTP シナリオテスト
    - 429 → Retry-After に従ってリトライ
    - 5xx → 指数バックオフでリトライ
    - TransportError → リトライ + 例外正規化
    - レート制限の待ち時間検証
  - pytest.mark.large: 実 API 通信テスト（CI では skip）
```

Day 7 でテストを本格整備するが、Day 3 の時点で「動く状態」を確認するために最低限のテストを書く。

### `tests/conftest.py`（グローバル設定のリセット）

```python
"""テスト共通の fixture。"""
import pytest

from edinet._config import _reset_for_testing


@pytest.fixture(autouse=True)
def _reset_config():
    """各テスト後にグローバル設定をデフォルトに戻す。

    テストが途中で失敗しても確実にクリーンアップされる。
    _reset_for_testing() は _Config() を新規生成するので、
    デフォルト値を conftest にハードコードする必要がない（二重管理防止）。
    """
    yield
    # teardown: 設定を初期状態に戻す
    _reset_for_testing()
    # HTTP クライアントも破棄（テスト間で状態が残らないようにする）
    from edinet._http import invalidate_client
    invalidate_client()
```

### `tests/test_config.py`（Small テスト）

```python
"""_config.py のテスト。"""
from edinet._config import _Config, configure, get_config, EdinetConfigError
import pytest


def test_default_config_has_no_api_key():
    """初期状態では API キーが未設定であること。"""
    config = _Config()
    assert config.api_key is None


def test_ensure_api_key_raises_when_not_set():
    """API キー未設定で ensure_api_key() を呼ぶと EdinetConfigError。"""
    config = _Config()
    with pytest.raises(EdinetConfigError):
        config.ensure_api_key()


def test_api_key_not_in_repr():
    """API キーが repr() に含まれないこと（漏洩防止）。"""
    config = _Config(api_key="secret-key-12345")
    assert "secret-key-12345" not in repr(config)


def test_configure_sets_api_key():
    """configure() で API キーが設定されること。"""
    configure(api_key="test-key")
    config = get_config()
    assert config.api_key == "test-key"
    # クリーンアップは conftest.py の autouse fixture が行う


def test_configure_clears_api_key_with_none():
    """configure(api_key=None) で API キーをクリアできること。"""
    configure(api_key="test-key")
    assert get_config().api_key == "test-key"
    configure(api_key=None)
    assert get_config().api_key is None


def test_configure_no_args_changes_nothing():
    """configure() を引数なしで呼んでも設定が変わらないこと。"""
    configure(api_key="test-key", rate_limit=0.5)
    configure()  # 引数なし → 何も変わらない
    config = get_config()
    assert config.api_key == "test-key"
    assert config.rate_limit == 0.5


def test_configure_sets_rate_limit():
    """configure() でレート制限が変更できること。"""
    configure(rate_limit=0.5)
    config = get_config()
    assert config.rate_limit == 0.5


# --- ランタイムバリデーション ---

def test_configure_rejects_none_for_base_url():
    """base_url に None を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(base_url=None)


def test_configure_rejects_none_for_timeout():
    """timeout に None を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(timeout=None)


def test_configure_rejects_negative_timeout():
    """timeout に負の値を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(timeout=-1)


def test_configure_rejects_zero_max_retries():
    """max_retries に 0 を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(max_retries=0)


def test_configure_rejects_negative_rate_limit():
    """rate_limit に負の値を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(rate_limit=-1)


# --- クライアント無効化 ---

def test_configure_invalidates_client_on_base_url_change():
    """base_url 変更時に httpx.Client が破棄されること。"""
    from edinet import _http

    # クライアントを生成させる（内部状態を作る）
    configure(api_key="dummy")
    _http._get_client()
    assert _http._client is not None

    # base_url を変更 → クライアントが破棄される
    configure(base_url="https://example.com")
    assert _http._client is None
```

### `tests/test_http.py`（Small テスト — キー秘匿の検証）

```python
"""_http.py のテスト（Day 3 時点はキー秘匿まわりのみ）。

リトライロジック全体の検証は Day 7 で respx を使って行う。
Day 3 ではキー秘匿という差別化ポイントにテストを付けて安心を得る。
"""
from edinet._http import _redact
from edinet._config import EdinetAPIError, EdinetError


def test_redact_hides_secret():
    """_redact() がシークレット文字列を伏字にすること。"""
    text = "GET https://api.edinet-fsa.go.jp/api/v2/documents.json?Subscription-Key=my-secret-key"
    result = _redact(text, "my-secret-key")
    assert "my-secret-key" not in result
    assert "***" in result


def test_redact_with_empty_secret():
    """_redact() にシークレットが空文字の場合、元テキストを返す。"""
    text = "some error message"
    assert _redact(text, "") == text


def test_redact_no_match():
    """_redact() にシークレットが含まれない場合、元テキストを変えない。"""
    text = "Connection refused"
    assert _redact(text, "my-secret-key") == text


def test_edinet_api_error_does_not_contain_key():
    """EdinetAPIError の文字列に API キーが含まれないこと。"""
    secret = "super-secret-key-12345"
    exc = EdinetAPIError(429, "Too Many Requests")
    assert secret not in str(exc)
    assert secret not in repr(exc)


def test_edinet_error_wrapping_hides_key():
    """EdinetError にラップしたメッセージにキーが含まれないこと。
    
    実装では固定文言 "Network error" を使うため、そもそも漏れない。
    ここではその設計意図が守られていることを確認する。
    """
    # 固定文言パターン（実装の本線）
    exc_fixed = EdinetError("Network error")
    secret = "super-secret-key-12345"
    assert secret not in str(exc_fixed)

    # redact 経由パターン（logger.debug 用の文字列も検証）
    raw_msg = f"Connection failed: https://api.example.com?Subscription-Key={secret}"
    sanitized = _redact(raw_msg, secret)
    assert secret not in sanitized
```

### 手動テスト（Day 3 の最終確認）

```python
# scratch.py（Git に含めない一時スクリプト）
from edinet._config import configure
from edinet.api.documents import get_documents

configure(api_key="your-api-key-here")

# 1. メタデータのみ
meta = get_documents("2026-02-07", include_details=False)
print(f"件数: {meta['metadata']['resultset']['count']}")

# 2. 提出書類一覧+メタデータ
result = get_documents("2026-02-07")
print(f"件数: {result['metadata']['resultset']['count']}")
for doc in result["results"][:5]:
    print(f"  {doc['docID']} | {doc['filerName']} | {doc['docDescription']}")
```

期待される出力:

```
件数: 42
件数: 42
  S100XXXX | トヨタ自動車株式会社 | 有価証券報告書 第85期...
  S100YYYY | ソニーグループ株式会社 | 四半期報告書 第3四半期...
  ...
```

---

## 6. 実装順序（時間配分）

| 順番 | 作業 | 時間 | 完了条件 |
|------|------|------|----------|
| 1 | `_config.py` 実装 | 20分 | `configure()` + `get_config()` + 例外クラスが動く |
| 2 | `_http.py` 実装 | 40分 | `_http.get()` がリトライ・レート制限付きでリクエストを送れる |
| 3 | `api/documents.py` 実装 | 10分 | `get_documents()` が dict を返す |
| 4 | 手動テスト（EDINET API 実通信） | 10分 | JSON レスポンスが正しく返ることを確認 |
| 5 | `tests/test_config.py` + `tests/test_http.py` 作成 | 15分 | `pytest tests/test_config.py tests/test_http.py` が全通過 |
| 6 | ruff リント + 修正 | 10分 | `ruff check` で warning ゼロ |

合計: **~100分（1.5h + バッファ）**

---

## 7. 技術的な補足

### httpx.Client の生存期間

```
httpx.Client はコネクションプーリングを持つため、リクエストごとに生成・破棄しない。
モジュールレベルのシングルトンとして保持し、close() で明示的に閉じる。

生成タイミング: 最初の _http.get() 呼び出し時（遅延生成）
破棄タイミング: edinet.close() 呼び出し時 or プロセス終了時

クライアント影響パラメータ:
  base_url, timeout → これらが configure() で変更されると invalidate_client() が
  自動的に呼ばれ、既存のクライアントを破棄する。次の get() で再生成される。
  rate_limit, api_key, taxonomy_path → クライアントに影響しないので無効化しない。
```

### time.monotonic() vs time.time()

```
レート制限の時刻計測には time.monotonic() を使う。
time.time() はシステムクロックの変更（NTP 同期等）に影響されるが、
time.monotonic() は単調増加が保証されている。
```

### jitter の範囲

```
指数バックオフの base_delay に対して 0〜50% のランダム jitter を加える。
例: base_delay=2s の場合、実際の待ち時間は 2.0s〜3.0s

目的: 複数のクライアントが同時にリトライした場合の「雷鳴効果」を防ぐ。
```

---

## 8. Day 4 との接続点

Day 3 の成果物（`get_documents()` が返す `dict`）を Day 4 でどう使うか:

```python
# Day 3: 生の dict
result = get_documents("2026-02-07")
doc = result["results"][0]
print(doc["docID"])  # "S100XXXX"

# Day 4: Pydantic モデルに変換
from edinet.models.filing import Filing
filing = Filing.from_api_response(doc)
print(filing.doc_id)  # "S100XXXX"
print(filing.doc_type)  # DocType.SECURITIES_REPORT
```

Day 3 で `dict` を返す設計にしておけば、Day 4 で `Filing.from_api_response()` を追加するだけで繋がる。

### Day 7 への接続点

- `respx` を dev dependencies に追加する（`uv add --dev respx`）
- respx を使って 429 / 5xx / TransportError のシナリオテストを書く
- ※ `pyproject.toml` の `[dependency-groups] dev` に `respx` が未記載なので Day 7 の冒頭で追加すること

---

## 9. edinet-tools の失敗との対応表

| edinet-tools の失敗 | Day 3 での防止策 | 確認方法 |
|--------------------|----------------|----------|
| `urllib` にタイムアウトなし → 無限ハング | `httpx.Timeout(connect/read/write/pool=30.0)` を明示 | コード上で確認 |
| `import` 時に `load_dotenv()` + warning | `configure()` を呼ばない限り何も起きない | `import edinet` だけ実行して副作用がないことを確認 |
| レート制限なし → API ban リスク | デフォルト 1.0 秒間隔のスロットリング | 連続リクエストで 1 秒以上間隔が空くことをログで確認 |
| API キーがログに混入 | `repr=False`, `_safe_message()`, URL をログに出さない | `print(config)`, `EdinetAPIError` の message を確認 |

---

## 10. 注意事項

1. **`scratch.py` は `.gitignore` に追加すること。** API キーが含まれるファイルを Git に入れない
2. **`.env` も `.gitignore` に含まれていることを確認。** Day 2 で `.gitignore` を作成済みだが、`.env` の行があるか要確認
3. **Day 3 の時点では `__init__.py` に公開 API を書かない。** 公開 API（`edinet.configure()`, `edinet.documents()`）は Day 6 で統合時に追加。Day 3 は内部モジュールとして実装する
4. **テストで実際の API を叩くものは書かない。** 手動テストのみ。Large テストは Day 7 で `pytest.mark.large` 付きで書く
5. **`_http.py` の `_client` はスレッドセーフではない。** v0.1.0 はシングルスレッド前提。マルチスレッド対応は v0.2.0 以降

---

## 11. 完了条件（Day 3 の「動く状態」）

以下が全て満たされていれば Day 3 は完了:

- [ ] `configure(api_key=...)` で API キーが設定できる
- [ ] `get_documents("2026-02-07")` が EDINET API にリクエストを送り、dict を返す
- [ ] `metadata.status` が `"200"` 以外の場合に `EdinetAPIError` が送出される
- [ ] `configure(api_key=None)` で API キーをクリアできる（sentinel 動作確認）
- [ ] タイムアウト 30 秒が設定されている
- [ ] リトライが 429 / 5xx / ネットワークエラーで正しく動作する（コード上で確認）
- [ ] レート制限 1.0 秒が動作する（連続リクエストで確認）
- [ ] `tests/test_config.py` + `tests/test_http.py`（キー秘匿テスト）が全通過
- [ ] `ruff check` で warning ゼロ
- [ ] API キーがログ・例外・repr に混入しない
- [ ] `close()` / `invalidate_client()` が pytest 実行後も例外なく呼べること

---

## 12. レビュー反映ログ（初版からの変更点と理由）

計画の初版に対してレビューを 2 回実施し、以下の修正を加えた。変更理由を残すことで「なぜこの設計にしたのか」を将来の自分やレビュアーが追えるようにする。

### 第 1 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `configure()` のデフォルト引数 | `None` → `_UNSET` sentinel | 旧設計では `if api_key is not None:` のため `configure(api_key=None)` でクリアできず、テストのクリーンアップが壊れる。sentinel で「渡されなかった」と「None を渡した」を区別できるようにした |
| 2 | `_http.py` の `TransportError` ハンドリング | `_redact()` 導入 + `from exc` 禁止 | `httpx.TransportError` の `str()` / `repr()` にはリクエスト URL（`Subscription-Key` 入り）が含まれることがある。例外チェーン経由で API キーが漏洩するリスクを潰すため |
| 3 | `configure()` → `invalidate_client()` 連携 | `base_url` / `timeout` 変更時にクライアント無効化 | シングルトンの `httpx.Client` は生成時の設定を保持するため、`configure()` で接続パラメータを変えても古い設定が残り続ける事故を防止 |
| 4 | `_record_request_time()` の docstring | 「リクエスト開始時刻を記録する」意図を明文化 | 読み手が「レスポンス後に更新すべきでは？」と迷う可能性があった。開始間隔を制御する設計意図をコメントで固定して改変事故を防ぐ |
| 5 | `get_documents()` の `include_details` docstring | `type=1` / `type=2` の仕様書用語を明記 | 仕様書の正式な表現（「メタデータのみ」「提出書類一覧及びメタデータ」）に合わせて誤解を防ぐ |
| 6 | `api/documents.py` に `metadata.status` 検査を追加 | HTTP 200 でも JSON レベルでステータスを検証 | EDINET API は HTTP 200 を返しつつ `metadata.status` がエラーを示すケースがある。`_http.get()` の HTTP ステータスチェックだけでは不十分 |

### 第 2 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `configure()` 内の import | `from edinet import _http` → `from ._http import invalidate_client` | `from edinet import _http` はパッケージ `__init__.py` を経由する。Day 6 で `__init__.py` に `configure` を公開した瞬間に循環 import が発生する。相対 import で直接モジュールを指定することで回避 |
| 2 | `last_exception` の型と方針コメント | `Exception` → `EdinetError` + RULE コメント追加 | httpx の生の例外インスタンスを変数に保持すると、どこかで `repr(exc)` が走り URL（キー入り）が漏れる。「httpx 例外そのものを保持しない」をルールとして明文化し最終防衛線にした |
| 3 | `_parse_retry_after()` の docstring | HTTP-date 未対応の制約を明記 | RFC 7231 では `Retry-After` は秒数だけでなく HTTP-date 形式もあり得る。EDINET は秒数想定だが、制約を書かないと将来「なぜ対応してないのか」が分からなくなる |
| 4 | `_version.py` 新設 + User-Agent 参照 | ハードコード `"0.1.0"` → `__version__` 変数参照 | バージョンをハードコードすると公開時に UA 更新忘れが起きる。`_version.py` で 1 箇所管理すれば自動的に追従する |
| 5 | `httpx.Timeout` の分割定義 | 単一値 → `connect` / `read` / `write` / `pool` 個別指定 | 実質同じ動作だが、将来「接続は短く、読み取りは長く」等の調整が必要になったとき、この形なら個別に変更できる。コスト 0 で柔軟性を得る |
| 6 | 429 処理ブロックにコメント追加 | 「Retry-After sleep 後に rate_limit sleep が入る」旨を明記 | 429 の Retry-After 待ち後、次ループで rate_limit sleep が再度走るため二重待ちになる可能性がある。これは安全側の設計判断として意図的であることを書かないと「バグでは？」と混乱する |
| 7 | `tests/test_http.py` にキー秘匿テスト追加 | `_redact()` + 例外メッセージの検証 5 テスト | 差別化ポイント（API キー秘匿）にテストが付いていないのは不安。Day 3 の Small テストで `_redact` の動作と例外へのキー非混入を確認すれば、respx なしでも秘匿の信頼性を担保できる |

### 第 3 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `configure()` の引数型 | `base_url: str \| None` → `base_url: str` 等（`timeout`, `max_retries`, `rate_limit` も同様） | `configure(base_url=None)` が通ると `httpx.Client(base_url=None)` で即死する。`api_key` と `taxonomy_path` だけが None クリア可能なパラメータであり、それ以外は型で None を弾くのが最もシンプルで安全 |
| 2 | `_CLIENT_PARAMS` の活用 | 手動 `need_invalidate = True` → `_CLIENT_PARAMS` を使った自動判定 | 定義だけして未使用だった。将来フィールド追加時に invalidate 漏れが起きるリスクを解消。`for name, value in updates.items()` ループで `_CLIENT_PARAMS` を実際に参照する形に変更 |
| 3 | `TransportError` の例外メッセージ | `_redact(str(exc), api_key)` を例外に入れる → 固定文言 `"Network error"` に変更 | `_redact()` は percent-encode 等で漏れうる。キー漏洩ゼロを最優先するなら例外メッセージは短く固定が最強。診断情報は `logger.debug` に redact 済みで出す（本番では通常 OFF） |
| 4 | 完了条件 | `close()` / `invalidate_client()` のテスト項目を追加 | pytest 実行後にクライアントが残って警告やハングする事故を防止。テストの `conftest.py` で teardown に入れる前提 |

### 第 4 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `configure()` にランタイムバリデーション追加 | `base_url` / `timeout` / `max_retries` / `rate_limit` に None が渡されたら `EdinetConfigError`。`timeout <= 0`, `max_retries < 1`, `rate_limit < 0` も即エラー | 第 3 回で型ヒントを `str | None` → `str` にしたが、Python は型ヒントをランタイムで強制しない。`configure(base_url=None)` は `setattr` でそのまま入り `httpx.Client` 生成時に死ぬ。壊れた設定で壊れ方が不明瞭になるのを防ぐため、入口で弾くのが正解。`max_retries=0` だとリトライループが 1 回しか回らない silent failure になる点も YAGNI ではなく実害がある |

### 第 5 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `logger.debug` の出力内容 | `_redact(str(exc), api_key)` → `type(exc).__name__` + `path` + `attempt` のみ | `_redact()` は exact match なので percent-encode 差で漏れうる。logger にも URL / `str(exc)` を一切出さないのがキー漏洩ゼロの最終形。診断には例外クラス名 + パス + 試行番号で十分 |
| 2 | `max_retries` の意味をコメントで固定 | 「総試行回数（初回含む）」であることを明記 | `max_retries=3` が「3回リトライ=4回試行」なのか「3回試行」なのか読み手が迷う。リネームはコスト高なのでコメントで意味を固定して将来の混乱を防ぐ |
| 3 | テスト戦略の明文化 | Day 3 = pure function テスト、Day 7 = respx シナリオテストの切り分けを追加 | 429/5xx の再現は実通信では困難。テスト範囲を明示しておくことで Day 3 に無理な完了条件を課さない |

### 第 6 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | 例外クラスの定義順 | `_Config` の後 → `_Config` の前に移動 | `ensure_api_key()` が `EdinetConfigError` を参照する。Python はメソッド本体を呼び出し時に解決するのでランタイムエラーにはならないが、定義順が逆だと読み手が混乱する。可読性のため参照先を先に定義する |
| 2 | `tests/conftest.py` に `autouse=True` fixture 追加 | 各テスト末尾の手動クリーンアップ → fixture の teardown で自動リセット | テストが途中で fail すると手動 `configure(api_key=None)` が実行されず、後続テストが汚れた状態で走る。`autouse=True` fixture なら yield 後の teardown が必ず実行される |

### 第 7 回レビュー（2 件同時）

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `test_config.py` に invalidate_client テスト追加 | `configure(base_url=...)` 後に `_http._client is None` を検証するテスト 1 本追加 | チェックリストに「クライアントが自動再生成されること」の項目はあったがテストコードがなかった。Small テストで検証可能な項目なので Day 3 で入れる |

### 第 8 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `_version.py` と `pyproject.toml` のバージョン管理 | `pyproject.toml` を `dynamic = ["version"]` にして `_version.py` を single source of truth にする方針を追記 | バージョンが 2 箇所（`_version.py` と `pyproject.toml`）に散在すると更新忘れが起きる。1 箇所管理が原則 |
| 2 | `_config.py` に `_reset_for_testing()` 追加 | `_global_config = _Config()` で新規インスタンスを作る内部関数を追加 | conftest.py でデフォルト値をハードコードすると `_Config` のデフォルト変更時に二重管理が腐る。`_Config()` のデフォルトを正とする関数を用意して conftest から呼ぶ |
| 3 | conftest.py を `_reset_for_testing()` 呼び出しに変更 | `configure(api_key=None, base_url=..., ...)` のハードコード → `_reset_for_testing()` 1 行に | 上記の二重管理解消 |
| 4 | `_safe_message()` の `except Exception` にコメント | 意図的に広い except であることを明記 | EDINET がメンテナンス中に HTML を返す等、`json.JSONDecodeError` 以外の例外もありうる。安全側に倒す設計意図をコメントで固定 |
| 5 | PLAN.md との `max_retries` 整合性 | PLAN.md L624/L628 との解釈差をコメントに明記 | PLAN.md の「リトライ3回」と Day3.md の「総試行3回」が矛盾しうる。Day3.md 側の定義を正として PLAN.md の意図を注記 |
| 6 | Day 7 への接続点に `respx` メモ追加 | `pyproject.toml` に `respx` 未記載の注意を追記 | Day 7 で respx を使う計画だが dev dependencies に入っていない。忘れ防止 |

### 第 9 回レビュー

| # | 変更箇所 | 何を変えたか | なぜ変えたか |
|---|----------|------------|------------|
| 1 | `get_documents()` に `JSONDecodeError` ガード追加 | `response.json()` を `try/except` で囲み `EdinetAPIError` に変換 | EDINET がメンテナンス中に HTTP 200 + HTML を返すと `JSONDecodeError` で落ちる。`_safe_message()` はエラーレスポンス用で正常系パスは無防備だった |
| 2 | `invalidate_client()` で `_last_request_time` もリセット | `_last_request_time = 0.0` を追加 | テスト間で rate_limit の状態が残り、次テストの最初のリクエストで不要な sleep が発生するテスト汚染を防止 |
| 3 | `pyproject.toml` のビルドバックエンド明確化 | `[build-system]` 未指定の注意と hatchling / setuptools の両パターンを追記 | `dynamic = ["version"]` はビルドバックエンドに依存する。未確認のまま実装すると 10 分のロスになる |

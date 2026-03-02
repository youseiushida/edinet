# Day 5 — ZIP 取得 + 解凍（書類取得 API）

## 0. 位置づけ

Day 4 で `DocType` / `Filing`、Day 4.5 で `OrdinanceCode` / `FormCode` / `FundCode` / `EdinetCode` を実装した。  
Day 5 は Week 1 の最終ピースとして、**書類取得 API (`/documents/{doc_id}`)** を実装し、Day 6 の `Filing.fetch()` につなぐ。

現状（2026-02-15 時点）:

- `src/edinet/api/download.py` は **0 byte（未実装）**
- `tests/test_api/` は **空**
- `Filing.fetch()` は未実装（Day 6 予定）

よって Day 5 では「ダウンロード関数 + ZIP 内 XBRL 特定ロジック + Small テスト」を完成させる。

---

## 1. 目標

Day 5 終了時に次が動くこと:

```python
from edinet._config import configure
from edinet.api.download import (
    DownloadFileType,
    download_document,
    extract_primary_xbrl,
)

configure(api_key="your-api-key")

# type=1（提出本文書及び監査報告書）を取得
zip_bytes = download_document("S100XXXX", file_type=DownloadFileType.XBRL_AND_AUDIT)

# ZIP 内の `*/PublicDoc/*.xbrl` を自動選択して取り出す
result = extract_primary_xbrl(zip_bytes)
if result is not None:
    xbrl_path, xbrl_bytes = result
    print(xbrl_path)
    print(len(xbrl_bytes))
```

この時点では XBRL パースは行わない（Day 8-10）。

---

## 2. スコープと非スコープ

### Day 5 のスコープ

1. 書類取得 API 呼び出しラッパー（`api/download.py`）
2. `type=1..5` の Enum 化（魔法の数字排除）
3. `Content-Type` ベースの成功/失敗判定
4. ZIP のインメモリ処理（`BytesIO` + `zipfile`）
5. `PublicDoc/` を含む `.xbrl` 特定（`PublicDoc/` と `XBRL/PublicDoc/` の両方を許容）
6. Small テスト追加（ネットワーク不要）

### Day 5 でやらないこと

1. `Filing.fetch()` 実装（Day 6）
2. XBRL XML の構造解析（Day 8-10）
3. タクソノミ解決（Day 12）
4. 非同期化（v0.2.0 以降）
5. `_http` のストリーミング受信上限実装（Day5では契約明確化を優先し、次段階で対応）

---

## 3. 実装対象ファイル

| ファイル | 役割 | 行数目安 |
|----------|------|----------|
| `src/edinet/api/_errors.py` | API エラー JSON 解釈の共通ヘルパー | ~60行 |
| `src/edinet/api/download.py` | 書類取得 API + ZIP ヘルパー実装 | ~220行 |
| `tests/test_api/test_download.py` | Day 5 の Small テスト | ~260行 |
| `tests/test_api/test_documents.py` | `documents.py` の回帰テスト（共通ヘルパー導入の安全網） | ~120行 |
| `tests/test_api/test_errors.py` | `_errors.py` 単体テスト（共通ヘルパー仕様固定） | ~120行 |
| `tests/conftest.py` | API テスト時の不要な重い import 抑制（警告リセットの遅延化） | ~20行差分 |
| `tests/fixtures/download/` (任意) | 固定再現が必要なケースだけ置く補助 fixture | 数ファイル |
| `tools/e2e_download_check.py` (任意) | Day5 手動確認用の独立 E2E スクリプト | ~80行 |

`src/edinet/api/__init__.py` は Day 5 では変更しない（Day 6 で公開 API を整備）。

---

## 4. `api/download.py` 設計

### 4.1 仕様根拠（EDINET API 仕様書）

書類取得 API:

- エンドポイント: `GET /documents/{doc_id}`
- パラメータ `type`:
1. `1` 提出本文書及び監査報告書（ZIP）
2. `2` PDF（PDF）
3. `3` 代替書面・添付文書（ZIP）
4. `4` 英文ファイル（ZIP）
5. `5` CSV（ZIP）

重要注意:

- 書類取得 API はエラー時でも HTTP 200 を返し得る
- 成否判定は `Content-Type` で行う必要がある
- 成功時:
1. ZIP: `application/octet-stream` / `application/zip` / `application/x-zip-compressed`
2. PDF: `application/pdf`
- 失敗時: `application/json; charset=utf-8`

### 4.2 公開 API（関数 I/F）

```python
class DownloadFileType(str, Enum):
    XBRL_AND_AUDIT = "1"
    PDF = "2"
    ATTACHMENT = "3"
    ENGLISH = "4"
    CSV = "5"

    @property
    def expected_content_types(self) -> tuple[str, ...]: ...

    @property
    def is_zip(self) -> bool: ...


def download_document(
    doc_id: str,
    *,
    file_type: DownloadFileType | str = DownloadFileType.XBRL_AND_AUDIT,
) -> bytes:
    """書類取得 API でバイナリを取得する。"""


def list_zip_members(zip_bytes: bytes) -> tuple[str, ...]:
    """ZIP 内のメンバー名一覧を返す。"""


def find_primary_xbrl_path(zip_bytes: bytes) -> str | None:
    """`PublicDoc/` を含む代表 XBRL パスを返す。見つからなければ None。"""


def extract_zip_member(zip_bytes: bytes, member_name: str) -> bytes:
    """ZIP 内の指定ファイルを bytes で返す。"""


def extract_primary_xbrl(zip_bytes: bytes) -> tuple[str, bytes] | None:
    """代表 XBRL を (path, bytes) で返す。見つからなければ None。"""
```

設計意図:

1. Day 5 は `Filing` と疎結合の関数 API にする
2. Day 6 で `Filing.fetch()` からこれらを呼ぶ
3. ZIP 展開時にディスクへ書かない

### 4.3 `download_document()` の振る舞い

1. `file_type = DownloadFileType(file_type)` で実行時に正規化（不正値は `ValueError`）
2. `_http.get(f"/documents/{doc_id}", params={"type": normalized_file_type.value})` を呼ぶ
3. レスポンス `Content-Type` を小文字化して判定
4. `application/json` 系なら `api/_errors.py` の共通ヘルパーで JSON を解釈して `EdinetAPIError` を送出
5. `type=1/3/4/5` で `application/pdf` が返った場合は、**不開示等の可能性**として明示メッセージ付き `EdinetAPIError` を送出
6. ZIP 系（`type=1/3/4/5`）は許容 Content-Type リストで検証（`application/octet-stream`, `application/zip`, `application/x-zip-compressed`）
7. PDF 系（`type=2`）は `application/pdf` 固定で検証
8. 一致時は `response.content` を返却

エラー JSON 解析ルール:

1. `{"StatusCode": 401, "message": "..."}` または `{"statusCode": 401, "message": "..."}`
2. `{"metadata": {"status": "404", "message": "Not Found"}}` 形式
3. 上記どちらでもなければ `status_code=0` として安全に失敗

### 4.3.1 エラー JSON 解釈の共通化

`download.py` と `documents.py` で同系統のエラー JSON 解釈を重複させない。  
Day 5 で `src/edinet/api/_errors.py` を新設し、両モジュールから利用する。

想定 I/F:

```python
def parse_api_error_response(response: Any, *, default_status_code: int = 0) -> tuple[int, str]:
    """EDINET API の JSON エラー構造を解釈し、(status_code, message) を返す。"""

def raise_for_api_error_response(response: Any, *, default_status_code: int = 0) -> None:
    """parse_api_error_response() の結果で EdinetAPIError を raise する。"""
```

対応形式:

1. `{"StatusCode": ...}`
2. `{"statusCode": ...}`
3. `{"metadata": {"status": ..., "message": ...}}`

責務分離ルール:

1. `parse_*` は例外を投げず、解析結果を返す責務に限定
2. `raise_*` は `parse_*` の結果で `EdinetAPIError` を投げる責務に限定
3. `documents.py` / `download.py` は `raise_*` を利用し、独自 JSON 解釈を実装しない
4. `documents.py` の成功判定（`metadata.status == "200"`）は既存契約どおり `documents.py` 側で行い、共通ヘルパーは「エラー解釈」のみに限定
5. `raise_for_api_error_response(...)` 呼び出し時は `default_status_code=response.status_code` を必須で渡す（診断品質維持）
6. `_http.py` は transport/retry と HTTP ステータス処理（非200）に責務を限定する
7. `_http._safe_message()` と `api/_errors.py` の責務差（best-effort 抽出 vs EDINET JSON 解釈）を文書化し、層ごとの役割差を許容する
8. Day5 では `_http.py` を `api/_errors.py` に統合しない（P2バックログとして分離管理）

### 4.3.2 Content-Type 判定ポリシー

1. ZIP 系: `application/octet-stream`, `application/zip`, `application/x-zip-compressed` を許容
2. PDF 系: `application/pdf` のみ許容
3. JSON 系: `application/json` で共通エラーヘルパーへ委譲
4. 上記以外: `EdinetAPIError`（Unexpected Content-Type）
5. 仕様外だが許容している ZIP 値（`application/zip`, `application/x-zip-compressed`）は受理時に **debug ログ**を残す
6. ログメッセージは `"Accepted non-spec ZIP Content-Type '%s' for type=%s"` に固定する

### 4.3.3 例外契約（Day6連携向け）

1. `ValueError`: 呼び出し側入力不正（空/不正 `doc_id` / 不正 `file_type`）または公開 ZIP ヘルパーへの不正 `zip_bytes` / 不正 `member_name`
2. `EdinetAPIError`: API 応答の業務異常（エラー JSON、Unexpected Content-Type、ZIP 応答サイズが `MAX_ZIP_BYTES` 超過）
3. `EdinetError`: `_http.get()` の再試行枯渇など通信層失敗（`download_document()` は握りつぶさず透過）
4. API 由来 ZIP（`download_document()` で取得した bytes）を上位で解析する際に `ValueError` が出た場合、公開 API 境界では `EdinetAPIError` へ正規化する
5. Day5 では ZIP ヘルパーの戻り値/例外型は維持し、正規化は Day6 の `Filing.fetch()` 境界で必須適用する

### 4.3.4 `doc_id` バリデーション方針（Day5で固定）

1. Day5 は**仕様固定（厳格）**を採用し、`doc_id` は英数字のみ許可する
2. 将来仕様変更が必要になった場合は、Day5 のテスト名・契約文言を同時更新してから緩和する
3. 目的は「曖昧入力の早期拒否」と「テストでの契約固定」
4. 根拠: Day5 時点で確認できる API 応答・既存運用では英数字 ID のみを扱っており、まずは現行運用の誤入力防止を優先する

### 4.4 ZIP ヘルパーの振る舞い

1. `zipfile.ZipFile(BytesIO(zip_bytes))` を毎回開く（関数内完結）
2. `zip_bytes` が bytes-like でない場合は `ValueError("zip_bytes must be bytes-like")`
3. 不正 ZIP は `ValueError("Invalid ZIP data ...")` に変換
4. パス区切りは ZIP 標準の `/` を前提に扱う
5. ディレクトリエントリは除外し、通常ファイルのみを対象

### 4.4.1 ZIP 安全上限（Day5で固定）

1. `MAX_ZIP_BYTES = 50 * 1024 * 1024`（50MB）
2. `MAX_MEMBER_COUNT = 2000`
3. `MAX_MEMBER_BYTES = 20 * 1024 * 1024`（20MB）
4. `MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024`（200MB）
5. `MAX_XBRL_SCAN_BYTES_TOTAL = 4 * 1024 * 1024`（4MB）

適用ルール:

1. `download_document()` 受信後に ZIP 系 `type` では `len(content)` を `MAX_ZIP_BYTES` で検査
2. 公開 ZIP ヘルパー（`list_zip_members` / `find_primary_xbrl_path` / `extract_zip_member` / `extract_primary_xbrl`）は `_open_zip()` で `len(zip_bytes)` を `MAX_ZIP_BYTES` 検査
3. ZIP 展開時は member 数を `MAX_MEMBER_COUNT` で検査
4. ZIP 展開時は `sum(ZipInfo.file_size)` を `MAX_TOTAL_UNCOMPRESSED_BYTES` で検査
5. 各 member の `ZipInfo.file_size` を `MAX_MEMBER_BYTES` で検査（`_validate_zip_limits()` に集約）
6. `find_primary_xbrl_path()` で先頭読み取りを行うとき、累積読み取り量を `MAX_XBRL_SCAN_BYTES_TOTAL` で検査
7. しきい値超過時:
   - API 応答（`download_document`）は `EdinetAPIError`
   - 公開 ZIP ヘルパー入力は `ValueError`
   - ZIP 内部上限（member件数/単体サイズ/総展開量/候補スキャン量）超過は `ValueError`
8. `extract_zip_member()` の `member_name` は `strip()` 後に非空を必須とし、不正時は `ValueError`

実装制約（明示）:

- 現行 `_http.get()` は `httpx.Client.get()` でレスポンスを全量受信してから返すため、`MAX_ZIP_BYTES` は受信後検査になる。
- Day5 では契約明確化と fail-fast を優先し、ストリーミング受信による厳密な事前メモリ防御は次段階（`_http` 拡張）で対応する。

### 4.5 `find_primary_xbrl_path()` の選択ヒューリスティック

候補抽出:

1. パスに `"/PublicDoc/"` を含む（`PublicDoc/` と `XBRL/PublicDoc/` を許容）
2. 拡張子 `.xbrl`（大文字小文字は無視）

候補が 0 件:

- `None` を返す

候補が 1 件:

- そのパスを返す

候補が複数件:

以下の優先順で安定選択する（同点時の決定性を保証）:

1. 先頭 64KB に `jppfs_cor` を含むものを優先
2. 次に `jpcrp_cor` を含むものを優先
3. 次にファイルサイズの大きいものを優先
4. 次にディレクトリ深さが浅いものを優先
5. 最後は辞書順昇順で固定

注:

- Day 5 では「完全な正解判定」より「壊れず安定して選ぶ」ことを優先
- 候補ヘッダ読み取り総量が `MAX_XBRL_SCAN_BYTES_TOTAL` を超える場合は安全側で `ValueError`
- Day 8-10 のパーサー実装後に、必要なら精緻化する

### 4.6 実装上の禁止事項

1. `str.split(",")` のようなフォーマット前提ハックは入れない
2. 一時ファイル保存（`tempfile.NamedTemporaryFile`）に逃げない
3. `except Exception: pass` を使わない
4. `doc_id` や API キーを例外文言に生で出さない

### 4.7 実装ドラフト（`src/edinet/api/download.py`）

以下は Day 5 で実際に置く想定の**実装ドラフト**。  
このブロックをそのまま `src/edinet/api/download.py` に置けば動くレベルまで具体化している。  
ただし実装後は `src/` 配下の実コードを正（single source of truth）とし、md は差分要点のみ同期する。

```python
"""EDINET 書類取得 API (download API) のラッパー。"""
from __future__ import annotations

from enum import Enum
from io import BytesIO
import logging
import re
from zipfile import BadZipFile, ZipFile

from edinet import _http
from edinet.exceptions import EdinetAPIError
from edinet.api._errors import raise_for_api_error_response

logger = logging.getLogger(__name__)

ZIP_CONTENT_TYPES: tuple[str, ...] = (
    "application/octet-stream",
    "application/zip",
    "application/x-zip-compressed",
)

MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_MEMBER_COUNT = 2000
MAX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_XBRL_SCAN_BYTES_TOTAL = 4 * 1024 * 1024


class DownloadFileType(str, Enum):
    """書類取得 API の必要書類 type パラメータ。"""

    XBRL_AND_AUDIT = "1"
    PDF = "2"
    ATTACHMENT = "3"
    ENGLISH = "4"
    CSV = "5"

    @property
    def expected_content_types(self) -> tuple[str, ...]:
        if self is DownloadFileType.PDF:
            return ("application/pdf",)
        return ZIP_CONTENT_TYPES

    @property
    def is_zip(self) -> bool:
        return self is not DownloadFileType.PDF


_DOC_ID_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


def download_document(
    doc_id: str,
    *,
    file_type: DownloadFileType | str = DownloadFileType.XBRL_AND_AUDIT,
) -> bytes:
    """書類取得 API でバイナリを取得する。

    Args:
        doc_id: 書類管理番号（例: "S100XXXX"）。
        file_type: 必要書類 type（`DownloadFileType` または `"1"`..`"5"`）。

    Returns:
        取得したファイルのバイト列。

    Raises:
        ValueError: doc_id が空/空白、英数字以外を含む、または file_type が不正。
        EdinetAPIError: API がエラー JSON を返した、Content-Type が不正、
            または ZIP 応答が `MAX_ZIP_BYTES` を超過した。
        EdinetError: 通信失敗等で `_http.get()` が再試行枯渇した。
    """
    normalized = doc_id.strip()
    if not normalized:
        raise ValueError("doc_id must not be empty")
    if not _DOC_ID_PATTERN.fullmatch(normalized):
        raise ValueError("doc_id must be alphanumeric only")
    try:
        normalized_file_type = DownloadFileType(file_type)
    except ValueError as exc:
        raise ValueError(f"Invalid file_type: {file_type!r}") from exc

    response = _http.get(
        f"/documents/{normalized}",
        params={"type": normalized_file_type.value},
    )
    content_type = _normalize_content_type(response.headers.get("Content-Type"))

    # 書類取得 API は HTTP 200 + JSON エラーを返し得るため、まず JSON 系を判定する。
    if content_type == "application/json":
        raise_for_api_error_response(response, default_status_code=response.status_code)

    if normalized_file_type.is_zip and content_type == "application/pdf":
        raise EdinetAPIError(
            response.status_code,
            "Received PDF for ZIP-type request. The document may be non-disclosed "
            "or XBRL/CSV download may be unavailable.",
        )

    if normalized_file_type.is_zip and content_type in {"application/zip", "application/x-zip-compressed"}:
        logger.debug(
            "Accepted non-spec ZIP Content-Type '%s' for type=%s",
            content_type,
            normalized_file_type.value,
        )

    if content_type not in normalized_file_type.expected_content_types:
        raise EdinetAPIError(
            response.status_code,
            f"Unexpected Content-Type '{content_type}' for type={normalized_file_type.value}. "
            f"Expected one of {normalized_file_type.expected_content_types}.",
        )

    if normalized_file_type.is_zip and len(response.content) > MAX_ZIP_BYTES:
        raise EdinetAPIError(
            response.status_code,
            f"ZIP payload too large: {len(response.content)} bytes",
        )
    return response.content


def list_zip_members(zip_bytes: bytes) -> tuple[str, ...]:
    """ZIP 内の通常ファイル名一覧を昇順で返す。"""
    with _open_zip(zip_bytes) as zf:
        infos = _iter_file_infos(zf)
        names = [info.filename for info in infos]
    return tuple(sorted(names))


def extract_zip_member(zip_bytes: bytes, member_name: str) -> bytes:
    """ZIP 内の指定メンバーを bytes で返す。

    Raises:
        ValueError: ZIP 不正、またはメンバーが存在しない。
    """
    if not isinstance(member_name, str):
        raise ValueError("member_name must be str")
    normalized_member_name = member_name.strip()
    if not normalized_member_name:
        raise ValueError("member_name must not be empty")

    with _open_zip(zip_bytes) as zf:
        _validate_zip_limits(zf)
        try:
            info = zf.getinfo(normalized_member_name)
        except KeyError as exc:
            raise ValueError(f"ZIP member not found: {normalized_member_name}") from exc
        if info.is_dir():
            raise ValueError(f"ZIP member is a directory: {normalized_member_name}")
        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError(
                f"ZIP member too large: {normalized_member_name} ({info.file_size} bytes)"
            )
        with zf.open(info, "r") as fp:
            return fp.read()


def find_primary_xbrl_path(zip_bytes: bytes) -> str | None:
    """`PublicDoc/` を含む代表 XBRL ファイルを選ぶ。

    優先順位:
    1) `jppfs_cor` を含む
    2) `jpcrp_cor` を含む
    3) ファイルサイズ大
    4) ディレクトリ深さ浅
    5) パス昇順
    """
    with _open_zip(zip_bytes) as zf:
        infos = _iter_file_infos(zf)
        candidates = [
            info for info in infos
            if "/publicdoc/" in f"/{info.filename.lower()}"
            and info.filename.lower().endswith(".xbrl")
        ]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0].filename

        ranked: list[tuple[tuple[int, int, int, int, str], str]] = []
        scanned_total = 0
        for info in candidates:
            remaining = MAX_XBRL_SCAN_BYTES_TOTAL - scanned_total
            if remaining <= 0:
                raise ValueError("XBRL head scan budget exceeded")
            head = _read_head_bytes(zf, info.filename, limit=min(65536, remaining)).lower()
            scanned_total += len(head)
            has_jppfs = b"jppfs_cor" in head
            has_jpcrp = b"jpcrp_cor" in head
            depth = info.filename.count("/")
            # 小さい順で sort できるように優先順を符号化する。
            key = (
                0 if has_jppfs else 1,
                0 if has_jpcrp else 1,
                -info.file_size,
                depth,
                info.filename,
            )
            ranked.append((key, info.filename))

        ranked.sort(key=lambda x: x[0])
        return ranked[0][1]


def extract_primary_xbrl(zip_bytes: bytes) -> tuple[str, bytes] | None:
    """代表 XBRL を (path, bytes) で返す。見つからなければ None。"""
    path = find_primary_xbrl_path(zip_bytes)
    if path is None:
        return None
    return path, extract_zip_member(zip_bytes, path)


def _normalize_content_type(raw: str | None) -> str:
    """Content-Type を比較可能な正規形にする。"""
    if not raw:
        return ""
    return raw.split(";", 1)[0].strip().lower()


def _read_head_bytes(zf: ZipFile, member_name: str, *, limit: int) -> bytes:
    """ZIP メンバーの先頭 limit bytes を読む（ヒューリスティック用）。"""
    info = zf.getinfo(member_name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"ZIP member too large for scan: {member_name} ({info.file_size} bytes)")
    with zf.open(member_name, "r") as fp:
        return fp.read(limit)


def _iter_file_infos(zf: ZipFile) -> list:
    """通常ファイルの ZipInfo 一覧を返す（ZIP 上限検証は共通関数へ委譲）。"""
    return _validate_zip_limits(zf)


def _validate_zip_limits(zf: ZipFile) -> list:
    infos = [info for info in zf.infolist() if not info.is_dir()]
    if len(infos) > MAX_MEMBER_COUNT:
        raise ValueError(f"ZIP has too many members: {len(infos)}")
    for info in infos:
        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError(f"ZIP member too large: {info.filename} ({info.file_size} bytes)")
    total_uncompressed = sum(info.file_size for info in infos)
    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise ValueError(f"ZIP total uncompressed bytes too large: {total_uncompressed}")
    return infos


def _open_zip(zip_bytes: bytes) -> ZipFile:
    """ZIP バイト列を ZipFile として開く。壊れている場合は ValueError。"""
    if not isinstance(zip_bytes, (bytes, bytearray, memoryview)):
        raise ValueError("zip_bytes must be bytes-like")
    raw = bytes(zip_bytes)
    if len(raw) > MAX_ZIP_BYTES:
        raise ValueError(f"ZIP payload too large for helper input: {len(raw)} bytes")
    try:
        return ZipFile(BytesIO(raw))
    except (BadZipFile, ValueError) as exc:
        raise ValueError("Invalid ZIP data") from exc
```

### 4.8 実装ドラフトの補足判断

1. `download_document()` は ZIP/PDF 両方を返せるように `bytes` 戻り値で統一。
2. Day 5 時点では `DownloadResult` などの追加クラスは作らない。
3. エラー JSON 解釈は `api/_errors.py` に共通化し、`download.py` / `documents.py` の重複を除去する。
4. 共通ヘルパーの責務は `parse_*`（解析）と `raise_*`（例外化）に分離する。
5. 共通ヘルパーで 401 のキー揺れ（`StatusCode` / `statusCode`）を両対応にする。
6. `type=1/3/4/5` で `application/pdf` が返る場合は「不開示の可能性」を示すエラーメッセージで失敗させる。
7. ZIP 系の Content-Type は許容リスト（`application/octet-stream`, `application/zip`, `application/x-zip-compressed`）で判定する。
8. `doc_id` は `strip()` 後に英数字のみ許可し、誤入力（空白・`/` 等）を早期に拒否する。
9. `file_type` は `DownloadFileType(file_type)` で実行時正規化し、不正値を早期に `ValueError` 化する。
10. ZIP 安全上限（`MAX_ZIP_BYTES`, `MAX_MEMBER_COUNT`, `MAX_MEMBER_BYTES`, `MAX_TOTAL_UNCOMPRESSED_BYTES`, `MAX_XBRL_SCAN_BYTES_TOTAL`）を Day5 で固定する。
11. `_open_zip()` はヘルパー化してエラーハンドリングを一箇所に集約。
12. `find_primary_xbrl_path()` は `PublicDoc/` / `XBRL/PublicDoc/` の両方を探索し、決定性を最優先。
13. 共通エラーヘルパー呼び出しでは `default_status_code=response.status_code` を必須とする。
14. ZIP 上限検証ロジックは `_validate_zip_limits()` に集約し、重複実装を避ける。
15. 仕様外だが許容する ZIP Content-Type は観測性確保のため debug ログを残す。
16. debug ログのレベルとメッセージ形式は固定し、テストで安定検証できるようにする。

---

## 5. テスト計画（Small中心）

### 5.1 テストファイル

新規: `tests/test_api/test_download.py`
新規: `tests/test_api/test_documents.py`
新規: `tests/test_api/test_errors.py`

### 5.2 テストケース一覧

1. `DownloadFileType` の値が仕様と一致（1..5）
2. `file_type` に `DownloadFileType` を渡した場合の挙動が正しい
3. `file_type` に `"1"`..`"5"` 文字列を渡しても正規化される
4. `file_type` に不正値（例: `"9"`）を渡すと `ValueError`
5. ZIP 系 type で `application/octet-stream` を許可
6. ZIP 系 type で `application/zip` / `application/x-zip-compressed` を許可
7. PDF type で `application/pdf` を許可
8. `Content-Type: application/json` のとき `EdinetAPIError` を送出
9. `Content-Type: Application/JSON ; charset=UTF-8` の揺れを正規化して JSON と判定できる
10. 401 形式 JSON（`StatusCode`）を正しく解釈
11. 401 形式 JSON（`statusCode`）を正しく解釈
12. metadata 形式 JSON（`metadata.status`）を正しく解釈
13. JSON だが `response.json()` が壊れているケースを `EdinetAPIError` に変換
14. `doc_id` が空/空白なら `ValueError`
15. `doc_id` が英数字以外を含む場合は `ValueError`
16. `doc_id` 前後空白は `strip()` 後に受理される
17. `Content-Type` ヘッダ欠落時に失敗（安全側）
18. 期待 `Content-Type` 不一致で失敗（安全側）
19. `type=1/3/4/5` で `application/pdf` の場合に「不開示の可能性」メッセージで失敗
20. `type=3/4/5` が正しく送信される
21. `_http.get()` が `EdinetError` を送出した場合、`download_document()` が握りつぶさず透過する
22. `list_zip_members()` が安定順でメンバー一覧を返す
23. `find_primary_xbrl_path()` が候補 0 件で `None`
24. 候補 1 件でそのパスを返す（`XBRL/PublicDoc/*.xbrl` も含む）
25. `.XBRL`（大文字拡張子）も候補として検出できる
26. 候補複数件でヒューリスティック通りに選ぶ
27. `extract_primary_xbrl()` が `(path, bytes)` を返す
28. `extract_zip_member()` の not found が `ValueError`
29. `extract_zip_member()` へ directory 名指定で `ValueError`
30. 不正 ZIP バイト列に対し `extract_zip_member()` が `ValueError`
31. 不正 ZIP バイト列に対し `list_zip_members()` が `ValueError`
32. 不正 ZIP バイト列に対し `find_primary_xbrl_path()` が `ValueError`
33. 不正 ZIP バイト列に対し `extract_primary_xbrl()` が `ValueError`
34. `get_documents()` 回帰: `include_details=True` で `type=2` を送る
35. `get_documents()` 回帰: `include_details=False` で `type=1` を送る
36. `get_documents()` 回帰: 正常系 / 401 / metadata エラー / 壊れた JSON / 非dict JSON
37. ZIP API 応答が `MAX_ZIP_BYTES` 超過時に `EdinetAPIError`
38. 公開 ZIP ヘルパー入力が `MAX_ZIP_BYTES` 超過時に `ValueError`
39. ZIP member 件数が `MAX_MEMBER_COUNT` 超過時に `ValueError`
40. ZIP member サイズが `MAX_MEMBER_BYTES` 超過時に `ValueError`
41. ZIP 総展開量が `MAX_TOTAL_UNCOMPRESSED_BYTES` 超過時に `ValueError`
42. XBRL 候補ヘッダ読み取り総量が `MAX_XBRL_SCAN_BYTES_TOTAL` 超過時に `ValueError`
43. `_errors.py` 単体: 非dict JSON / status 非数値 / `response.json()` 失敗の境界挙動固定
44. 壊れた JSON 応答時に `documents.py` / `download.py` の `EdinetAPIError.status_code` が HTTP status を保持することを固定
45. `zip_bytes` に非 bytes-like を渡した場合に `ValueError`
46. `extract_zip_member()` の `member_name` が空/空白の場合に `ValueError`
47. `extract_zip_member()` の `member_name` が `str` 以外の場合に `ValueError`
48. ZIP 系で `application/zip` / `application/x-zip-compressed` を受理したとき **debug** ログが出る
49. API 由来 ZIP の解析失敗（`ValueError`）を Day6 境界で `EdinetAPIError` に正規化する方針を契約テストで固定（Day6側）
50. `tests/conftest.py` が API テスト実行時に `form_code` / `fund_code` / `edinet_code` を不要 import しない

### 5.3 フィクスチャ方針（Git管理）

基本方針:

```
tests/test_api/test_download.py 内で zipfile によりインメモリ生成（常時実行）
```

補助方針（必要時のみ）:

```
tests/fixtures/download/  # 固定再現が必要な難ケースだけ置く
```

ルール:

1. 基本はインメモリ生成を使い、`tests/fixtures/download/` 依存を最小化する
2. fixture を置く場合もファイル名は ASCII のみ（日本語ファイル名禁止）
3. fixture を置く場合もサイズは最小（数 KB）に保つ
4. これにより再現性・可読性・冪等性を同時に満たす

### 5.4 HTTP モック方針

- 依存追加なしで `monkeypatch` により `edinet.api.download._http.get` を差し替える
- `DummyResponse`（最小モック）で `headers` / `content` / `json` 振る舞いを固定する

### 5.5 実装ドラフト（`tests/test_api/test_download.py`）

以下は Day 5 のテスト実装ドラフト。  
`download.py` ドラフトと対応する形で、失敗系を含めて仕様を固定する。

```python
"""download API の Small テスト。"""
from __future__ import annotations

from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from edinet.api import download
from edinet.exceptions import EdinetAPIError


class DummyResponse:
    """_http.get の戻り値を差し替えるための最小レスポンス。"""

    def __init__(
        self,
        *,
        content_type: str,
        content: bytes = b"",
        json_data: Any = None,
        status_code: int = 200,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self._json_data = json_data
        self.headers = {"Content-Type": content_type}

    def json(self) -> Any:
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_download_file_type_values() -> None:
    assert download.DownloadFileType.XBRL_AND_AUDIT.value == "1"
    assert download.DownloadFileType.PDF.value == "2"
    assert download.DownloadFileType.ATTACHMENT.value == "3"
    assert download.DownloadFileType.ENGLISH.value == "4"
    assert download.DownloadFileType.CSV.value == "5"


def test_download_document_accepts_zip_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        content_type="application/octet-stream",
        content=b"PK\\x03\\x04dummy",
    )
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(download._http, "get", fake_get)
    body = download.download_document("S100TEST")
    assert body.startswith(b"PK")
    assert called["path"] == "/documents/S100TEST"
    assert called["params"] == {"type": "1"}


def test_download_document_accepts_pdf_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(content_type="application/pdf", content=b"%PDF-1.7")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    body = download.download_document("S100TEST", file_type=download.DownloadFileType.PDF)
    assert body.startswith(b"%PDF")


def test_download_document_raises_on_pdf_for_zip_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(content_type="application/pdf", content=b"%PDF-1.7")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST", file_type=download.DownloadFileType.XBRL_AND_AUDIT)
    assert "non-disclosed" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    ("file_type", "expected_type"),
    [
        (download.DownloadFileType.XBRL_AND_AUDIT, "1"),
        (download.DownloadFileType.ATTACHMENT, "3"),
        (download.DownloadFileType.ENGLISH, "4"),
        (download.DownloadFileType.CSV, "5"),
    ],
)
def test_download_document_sends_type_param_for_non_pdf(
    monkeypatch: pytest.MonkeyPatch,
    file_type: download.DownloadFileType,
    expected_type: str,
) -> None:
    dummy = DummyResponse(content_type="application/octet-stream", content=b"PK\\x03\\x04")
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(download._http, "get", fake_get)
    download.download_document("S100TEST", file_type=file_type)
    assert called["path"] == "/documents/S100TEST"
    assert called["params"] == {"type": expected_type}


def test_download_document_raises_on_json_error_401(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        content_type="application/json; charset=utf-8",
        json_data={
            "StatusCode": 401,
            "message": "Access denied due to invalid subscription key.",
        },
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 401


def test_download_document_raises_on_json_error_401_lowercase_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(
        content_type="application/json",
        json_data={
            "statusCode": 401,
            "message": "Access denied due to invalid subscription key.",
        },
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 401


def test_download_document_raises_on_json_error_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        content_type="application/json",
        json_data={"metadata": {"status": "404", "message": "Not Found"}},
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 404


def test_download_document_raises_when_json_body_is_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(
        content_type="application/json",
        json_data=ValueError("broken json"),
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError):
        download.download_document("S100TEST")


def test_download_document_rejects_empty_doc_id() -> None:
    with pytest.raises(ValueError):
        download.download_document("")
    with pytest.raises(ValueError):
        download.download_document("   ")


def test_download_document_rejects_non_alnum_doc_id() -> None:
    with pytest.raises(ValueError):
        download.download_document("S100/TEST")
    with pytest.raises(ValueError):
        download.download_document("S100 TEST")


def test_download_document_accepts_doc_id_with_surrounding_spaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(content_type="application/octet-stream", content=b"PK\\x03\\x04")
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(download._http, "get", fake_get)
    download.download_document("  S100TEST  ")
    assert called["path"] == "/documents/S100TEST"


def test_download_document_raises_when_content_type_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(content_type="", content=b"PK\\x03\\x04")
    dummy.headers = {}
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError):
        download.download_document("S100TEST")


def test_download_document_raises_on_unexpected_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(content_type="text/plain", content=b"oops")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError):
        download.download_document("S100TEST")


def test_list_zip_members_returns_sorted_file_names() -> None:
    zip_bytes = _make_zip(
        {
            "z.txt": b"z",
            "PublicDoc/b.xbrl": b"<xbrl/>",
            "a.txt": b"a",
        }
    )
    assert download.list_zip_members(zip_bytes) == (
        "PublicDoc/b.xbrl",
        "a.txt",
        "z.txt",
    )


def test_find_primary_xbrl_path_returns_none_when_not_found() -> None:
    zip_bytes = _make_zip({"AttachDoc/readme.txt": b"hello"})
    assert download.find_primary_xbrl_path(zip_bytes) is None


def test_find_primary_xbrl_path_returns_single_candidate() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"<xbrli:xbrl/>"})
    assert download.find_primary_xbrl_path(zip_bytes) == "XBRL/PublicDoc/main.xbrl"


def test_find_primary_xbrl_path_accepts_uppercase_extension() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.XBRL": b"<xbrli:xbrl/>"})
    assert download.find_primary_xbrl_path(zip_bytes) == "XBRL/PublicDoc/main.XBRL"


def test_find_primary_xbrl_prefers_jppfs_cor() -> None:
    zip_bytes = _make_zip(
        {
            "XBRL/PublicDoc/notes.xbrl": b"<xbrli:xbrl><jpcrp_cor:Foo/></xbrli:xbrl>",
            "XBRL/PublicDoc/financials.xbrl": b"<xbrli:xbrl><jppfs_cor:NetSales/></xbrli:xbrl>",
        }
    )
    assert download.find_primary_xbrl_path(zip_bytes) == "XBRL/PublicDoc/financials.xbrl"


def test_extract_primary_xbrl_returns_path_and_bytes() -> None:
    body = b"<xbrli:xbrl><jppfs_cor:NetSales/></xbrli:xbrl>"
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": body})
    result = download.extract_primary_xbrl(zip_bytes)
    assert result is not None
    path, data = result
    assert path == "XBRL/PublicDoc/main.xbrl"
    assert data == body


def test_extract_zip_member_not_found_raises_value_error() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"<xbrli:xbrl/>"})
    with pytest.raises(ValueError):
        download.extract_zip_member(zip_bytes, "XBRL/PublicDoc/missing.xbrl")


def test_extract_zip_member_directory_raises_value_error() -> None:
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("XBRL/PublicDoc/", b"")
        zf.writestr("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>")
    zip_bytes = buf.getvalue()
    with pytest.raises(ValueError):
        download.extract_zip_member(zip_bytes, "XBRL/PublicDoc/")


def test_extract_zip_member_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError):
        download.extract_zip_member(b"not-a-zip", "XBRL/PublicDoc/main.xbrl")


def test_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError):
        download.list_zip_members(b"not-a-zip")


def test_find_primary_xbrl_path_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError):
        download.find_primary_xbrl_path(b"not-a-zip")


def test_extract_primary_xbrl_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError):
        download.extract_primary_xbrl(b"not-a-zip")
```

### 5.6 テスト実装の補足

1. `DummyResponse` で HTTP クライアント依存を完全に遮断する。
2. ZIP テストは全部メモリ内で完結し、OS/CI 差分を減らす。
3. `test_find_primary_xbrl_prefers_jppfs_cor` で Day 5 の最重要判断を固定する。
4. `StatusCode` / `statusCode` のキー揺れを両方テストで固定する。
5. 失敗系（空/非英数字 doc_id、不正 file_type、壊れた JSON、Content-Type 欠落/不一致、不正 ZIP、member not found）を先に固定する。
6. `type=3/4/5` の送信を明示テストし、パラメータ退行を防ぐ。
7. `doc_id` は Day5 では「仕様固定（厳格）」として扱い、緩和時はテスト名と契約文言を同時更新する。

### 5.7 `tests/test_api/test_documents.py` 回帰テスト（新規）

`documents.py` を共通ヘルパーへ差し替えるため、既存挙動の回帰を固定する。

必須ケース:

1. 正常系: `metadata.status == "200"` で dict を返す
2. 401 系: `StatusCode` / `statusCode` の両方を `EdinetAPIError` 化
3. metadata エラー: `metadata.status != "200"` を `EdinetAPIError` 化
4. 壊れた JSON: `response.json()` 例外を `EdinetAPIError` 化
5. `include_details=True` で `type=2` が送信される
6. `include_details=False` で `type=1` が送信される
7. 壊れた JSON でも `default_status_code=response.status_code` が使われ、HTTP status が診断情報に残る
8. 非dict JSON（list/str/int）でも `AttributeError` を漏らさず `EdinetAPIError` 化する

### 5.8 `tests/test_api/test_errors.py` 単体テスト（新規）

共通ヘルパーの直接テストで、`documents.py` / `download.py` の間接テストだけでは拾いにくい境界を固定する。

必須ケース:

1. `parse_api_error_response()` が `StatusCode` / `statusCode` を同値に扱う
2. `metadata.status` が非数値文字列のとき `default_status_code` へフォールバック
3. 非dict JSON（list/str/int）を安全に失敗扱いへ変換
4. `response.json()` 失敗時のメッセージと status code が契約どおり
5. `raise_for_api_error_response()` が `parse_*` 結果を正しく `EdinetAPIError` 化
6. `default_status_code` を指定しない場合は `0` にフォールバックする（I/F 契約確認）

### 5.9 `tests/conftest.py` 軽量化（P2）

API テスト追加時の独立性と実行時間を維持するため、`_reset_warned_codes` の重い import を抑制する。

方針:

1. `sys.modules` を見て、既に import 済みのモデルだけ warning state をリセットする
2. `form_code` / `fund_code` / `edinet_code` を fixture teardown で強制 import しない
3. 必要なテストでのみ対象モジュールを import する（テスト側の明示 import）

---

## 6. 実装順序（決定版）

### 6.0 品質最優先の段階分割（推奨）

Day5 の変更範囲は広いため、品質最優先では次の 3 段階で進める。

1. Stage A: `api/_errors.py` + `download.py` + `tests/test_api/test_download.py`
2. Stage B: `documents.py` + `tests/test_api/test_documents.py` / `tests/test_api/test_errors.py`
3. Stage C: 任意 E2E（`tools/e2e_download_check.py`）

各段階のテストゲート:

1. Stage A 完了条件:
   - `py -m pytest tests/test_api/test_download.py -q`（または `uv run pytest ...`）が通る
2. Stage B 完了条件:
   - `py -m pytest tests/test_api/test_documents.py -q` が通る
   - `py -m pytest tests/test_api/test_errors.py -q` が通る
3. Stage C 完了条件（任意）:
   - 候補抽出と書類取得確認が手順どおり完了する

優先度による止めどころ（P0/P1/P2）:

1. P0（最低限・ここで止めてよい）:
   - Stage A 完了
   - `download_document()` と ZIP ヘルパーの契約が固定
2. P1（推奨・Day5完了扱い）:
   - Stage B 完了
   - `documents.py` 回帰と `_errors.py` 単体が固定
3. P2（余力対応）:
   - Stage C（任意E2E）
   - `tests/conftest.py` の重い import 抑制
   - Day5.md の巨大ドラフト圧縮

### Step -1: 依存セットアップ（10分）

推奨（uv 非依存・Python 標準）:

```powershell
py -m pip install -e .
py -m pip install pytest ruff openpyxl
```

`uv` を使う場合（プロジェクト標準）:

```powershell
uv sync --dev
```

### Step 0: 事前確認（10分）

1. `PLAN.md` Day 5 要件の再確認
2. `docs/EDINETAPI仕様書.md` の 3-2 節確認
3. **提出書類ファイル仕様書（ESE140104.pdf）** の ZIP 構造部分確認（`PLAN.md` Day 5 要件）
4. `download.py` 未実装状態の確認
5. ベースラインテストを先に実行して現状安定性を記録

実行コマンド:

```powershell
$env:PYTHONPATH="src"
git status --short
rg -n "3-2 書類取得 API|Content-Type|type" docs/EDINETAPI仕様書.md
rg -n "提出書類ファイル仕様書|ESE140104|ZIP構造" docs/PLAN.md
# 推奨（uv 非依存）
py -m pytest tests/test_config.py tests/test_http.py tests/test_models/test_filing.py -q
py -m pytest tests -m "not slow and not data_audit" -q
# uv を使う場合
uv run pytest tests/test_config.py tests/test_http.py tests/test_models/test_filing.py -q
uv run pytest tests -m "not slow and not data_audit" -q
```

### Step 1: 共通エラー処理 + ダウンロード実装（45分）

編集対象:

- `src/edinet/api/_errors.py`
- `src/edinet/api/download.py`
- `src/edinet/api/documents.py`

実装:

1. `api/_errors.py` を新設し、エラー JSON 解釈を共通化
2. `documents.py` の JSON エラー解釈を共通ヘルパー利用へ置換
3. `DownloadFileType` Enum
4. `download_document()`（`file_type` 実行時正規化 + 共通ヘルパー利用）
5. ZIP/PDF の Content-Type 判定ポリシー実装（ZIP は許容リスト）
6. ZIP 安全上限（`MAX_ZIP_BYTES`, `MAX_MEMBER_COUNT`, `MAX_MEMBER_BYTES`, `MAX_TOTAL_UNCOMPRESSED_BYTES`, `MAX_XBRL_SCAN_BYTES_TOTAL`）実装
7. `raise_for_api_error_response(..., default_status_code=response.status_code)` 必須ルールを `download.py` / `documents.py` へ適用
8. 仕様外だが許容する ZIP Content-Type 受理時の観測ログ（debug）を実装
9. `_http` と `_errors` の責務境界コメントを `download.py` / `documents.py` に明示

### Step 2: ZIP ヘルパー実装（25分）

編集対象:

- `src/edinet/api/download.py`

実装:

1. `list_zip_members()`
2. `find_primary_xbrl_path()`
3. `extract_zip_member()`
4. `extract_primary_xbrl()`
5. `zip_bytes` bytes-like 検証と `member_name` 非空 `str` 検証を実装
6. ZIP 上限検証ロジックを `_validate_zip_limits()` に集約

### Step 3: テスト追加（45分）

編集対象:

- `tests/test_api/test_download.py`
- `tests/test_api/test_documents.py`
- `tests/test_api/test_errors.py`
- `tests/conftest.py`（P2: 軽量化を行う場合）
- `tests/fixtures/download/*`（必要な難ケースが出た場合のみ）

実装:

1. 5.2 の全テストケース
2. インメモリ ZIP 組み立てヘルパー
3. `documents.py` 回帰ケース（`include_details` type=2/1、正常系 / 401 / metadata エラー / 壊れた JSON / 非dict JSON）
4. `_errors.py` 単体ケース（非dict JSON / 非数値 status / JSON 破損 / default_status_code）
5. `monkeypatch` による HTTP モック
6. 入力防御ケース（非 bytes-like `zip_bytes`、空/非str `member_name`）を追加
7. 仕様外許容 Content-Type 受理時のログ出力を `caplog` 等で固定
8. P2: `tests/conftest.py` の重い import 抑制（`sys.modules` ベース）を適用

実行コマンド:

```powershell
$env:PYTHONPATH="src"
# 推奨（uv 非依存）
py -m pytest tests/test_api/test_download.py -q
py -m pytest tests/test_api/test_documents.py -q
py -m pytest tests/test_api/test_errors.py -q
# uv を使う場合
uv run pytest tests/test_api/test_download.py -q
uv run pytest tests/test_api/test_documents.py -q
uv run pytest tests/test_api/test_errors.py -q
```

### Step 4: 既存回帰確認（15分）

実行コマンド:

```powershell
$env:PYTHONPATH="src"
# 推奨（uv 非依存）
py -m pytest tests/test_config.py tests/test_http.py tests/test_models/test_filing.py -q
py -m pytest tests/test_api/test_documents.py -q
py -m pytest tests/test_api/test_errors.py -q
py -m pytest tests -m "not slow and not data_audit" -q
py -m ruff check src tests
# uv を使う場合
uv run pytest tests/test_config.py tests/test_http.py tests/test_models/test_filing.py -q
uv run pytest tests/test_api/test_documents.py -q
uv run pytest tests/test_api/test_errors.py -q
uv run pytest tests -m "not slow and not data_audit" -q
uv run ruff check src tests
```

### Step 5: 手動 E2E（任意だが推奨、20分）

固定 `doc_id` を直接指定せず、当日の提出一覧から候補を動的選択する。

選定条件:

1. `xbrlFlag == "1"`
2. `withdrawalStatus == "0"`
3. `docTypeCode` / `ordinanceCode` / `formCode` が `None` でない

既存 `src/script.py` を直接改修すると回帰リスクがあるため、Day5 は `tools/e2e_download_check.py` を新規追加して検証する。

`tools/e2e_download_check.py` の想定引数:

1. `--download-doc-id`
2. `--download-type`（`1..5`）
3. ZIP のメンバー数と primary xbrl path を表示

注:

既存 `src/script.py` を触る場合は、少なくとも引数パースの回帰テストを同時追加する。

実行例（候補抽出）:

```powershell
# 推奨（uv 非依存）
$env:PYTHONPATH="src"
py -c "from datetime import date,timedelta; import os; from edinet._config import configure; from edinet.api.documents import get_documents; configure(api_key=os.environ['EDINET_API_KEY']); docs=[((date.today()-timedelta(days=i)).isoformat(), get_documents((date.today()-timedelta(days=i)).isoformat()).get('results', [])) for i in range(7)]; cand=[(d,[x for x in rs if x.get('xbrlFlag')=='1' and x.get('withdrawalStatus')=='0' and x.get('docID')]) for d,rs in docs]; hit=next(((d,c[0]['docID'],len(c)) for d,c in cand if c), None); print(hit if hit else 'NO_CANDIDATE_LAST_7_DAYS')"
# uv を使う場合
$env:PYTHONPATH="src"
uv run python -c "from datetime import date,timedelta; import os; from edinet._config import configure; from edinet.api.documents import get_documents; configure(api_key=os.environ['EDINET_API_KEY']); docs=[((date.today()-timedelta(days=i)).isoformat(), get_documents((date.today()-timedelta(days=i)).isoformat()).get('results', [])) for i in range(7)]; cand=[(d,[x for x in rs if x.get('xbrlFlag')=='1' and x.get('withdrawalStatus')=='0' and x.get('docID')]) for d,rs in docs]; hit=next(((d,c[0]['docID'],len(c)) for d,c in cand if c), None); print(hit if hit else 'NO_CANDIDATE_LAST_7_DAYS')"
```

実行例（取得確認）:

```powershell
# 推奨（uv 非依存）
py tools/e2e_download_check.py --api-key "<YOUR_KEY>" --download-doc-id "<CANDIDATE_DOC_ID>" --download-type 1
# uv を使う場合
uv run python tools/e2e_download_check.py --api-key "<YOUR_KEY>" --download-doc-id "<CANDIDATE_DOC_ID>" --download-type 1
```

### Step 6: ドキュメント同期（10分）

1. 実装後は `src/` を正として `docs/Day5.md` の実装ドラフトとの差分を確認
2. 乖離があれば md には「実装確定差分」のみ追記し、コード全文は更新しない
3. Day5 実装完了時に、`4.7 実装ドラフト` と `5.5 テスト実装ドラフト` は I/F・ルール・受け入れ条件中心へ圧縮する

確認コマンド:

```powershell
git status --short
rg -n "実装ドラフト|single source of truth|第3回|第4回|第5回|第6回|第7回|第8回|第9回|第10回|第11回" docs/Day5.md
```

---

## 7. Day 6 への引き渡し I/F

Day 5 完了時点で Day 6 が前提にできるもの:

1. `download_document(doc_id, file_type=...) -> bytes`
2. `extract_primary_xbrl(zip_bytes) -> tuple[path, bytes] | None`
3. エラー時は `EdinetAPIError` / `ValueError` / `EdinetError` で判定可能
4. 例外分類は「API 応答異常 = `EdinetAPIError`」「入力/ZIP 不正 = `ValueError`」「通信層失敗 = `EdinetError`」
5. Day6 境界ルール: `download_document()` 由来 bytes の ZIP 解析 `ValueError` は `EdinetAPIError` に正規化する

Day 6 側で追加するもの:

1. `Filing.fetch()` から Day 5 API を呼ぶ
2. `Filing._zip_cache` による再ダウンロード回避
3. `Company` との統合経路

---

## 8. リスクと対策

1. リスク: 巨大 ZIP / ZIP bomb でメモリ・CPU を過剰消費する  
対策: `MAX_ZIP_BYTES` / `MAX_MEMBER_COUNT` / `MAX_MEMBER_BYTES` / `MAX_TOTAL_UNCOMPRESSED_BYTES` / `MAX_XBRL_SCAN_BYTES_TOTAL` を超えたら安全側で即失敗

2. リスク: `Content-Type` に `; charset=...` が付く  
対策: `split(";")[0].strip().lower()` で判定

3. リスク: ZIP 系でも `application/zip` など `application/octet-stream` 以外が返る  
対策: ZIP 系は許容リストで判定し、完全一致の偽陰性を回避

4. リスク: `type=1/3/4/5` でも `application/pdf` が返る（不開示関連）  
対策: 不開示示唆の明示メッセージ付き `EdinetAPIError` に統一し、利用者に次の調査軸（`disclosureStatus` 等）を提示

5. リスク: ZIP の構成が `PublicDoc/` 直下でなく `XBRL/PublicDoc/` になる  
対策: `"/publicdoc/"` を含む `.xbrl` を候補化し、両構成を吸収する

6. リスク: `.xbrl` が複数あり誤選択  
対策: 決定性のあるヒューリスティックを明文化し、テストで固定

7. リスク: 将来 API 仕様が変わる  
対策: Enum と Content-Type 判定を 1 モジュールに集約し、変更点を局所化

8. リスク: `documents.py` と `download.py` のエラー解釈ロジックが乖離する  
対策: `api/_errors.py` に共通化し、両モジュールの重複実装を禁止する

9. リスク: md の実装ドラフトと実コードがドリフトする  
対策: 実装後は `src/` を正とし、md には I/F・受け入れ条件・差分要約のみを残す

10. リスク: `_http.get()` が全量受信してから返すため、`MAX_ZIP_BYTES` が受信後検査になり瞬間メモリ使用を抑制しきれない  
対策: Day5 は契約明確化（fail-fast）までを対象とし、ストリーミング受信上限は `_http` 拡張タスクとして明示管理する

11. リスク: `doc_id` を英数字限定で固定すると将来仕様変更時に過剰拒否になる  
対策: Day5 は厳格契約を優先し、緩和時は正規表現・テスト名・契約文言を同時更新する

12. リスク: `tests/conftest.py` が API テストでも重いモデルを毎回 import して実行時間と独立性を悪化させる  
対策: P2 で `sys.modules` ベースの遅延リセットに変更し、未使用モジュールの強制 import を避ける

13. リスク: `_http._safe_message()` と `api/_errors.py` のメッセージ品質が層ごとにずれる  
対策: Day5 は責務境界を明文化し、必要なら P2 で `_http` 側を共通ヘルパー利用へ寄せる

---

## 9. 完了条件（Day 5 の「動く状態」）

判定ルール:

1. P0 は Stage A 完了時点
2. Day5 完了判定は P1（Stage B 完了）を基準
3. P2（E2E / conftest 軽量化 / ドラフト圧縮）は任意だが推奨

1. `src/edinet/api/download.py` が実装済み（0 byte でない）
2. `DownloadFileType` が `1..5` を正しく提供
3. `download_document()` が Content-Type で成功/失敗を判定
4. ZIP ヘルパーが `*/PublicDoc/*.xbrl`（`PublicDoc/` / `XBRL/PublicDoc/`）を選択可能
5. `py -m pytest tests/test_api/test_download.py -q`（または `uv run pytest ...`）が通る
6. `py -m pytest tests/test_api/test_documents.py -q`（または `uv run pytest ...`）が通る
7. `py -m pytest tests/test_api/test_errors.py -q`（または `uv run pytest ...`）が通る
8. 既存テスト回帰が通る（少なくとも `test_config` / `test_http` / `test_filing`）
9. `api/_errors.py` が追加され、`documents.py` / `download.py` の両方が共通ヘルパーを利用
10. `type=1/3/4/5` で `application/pdf` の場合に不開示示唆メッセージで失敗する
11. ZIP 安全上限（`MAX_ZIP_BYTES`, `MAX_MEMBER_COUNT`, `MAX_MEMBER_BYTES`, `MAX_TOTAL_UNCOMPRESSED_BYTES`, `MAX_XBRL_SCAN_BYTES_TOTAL`）が実装・テストで固定される
12. `get_documents(include_details=...)` の `type=2/1` 契約が回帰テストで固定される
13. 壊れた JSON 応答時に `EdinetAPIError.status_code` が HTTP status を保持する挙動が回帰テストで固定される
14. `ruff check` が通る
15. 作業開始時との差分で `git status` に未意図変更がない
16. 公開 ZIP ヘルパーの入力検証（`zip_bytes` bytes-like / `member_name` 非空 str）が実装・テストで固定される
17. 仕様外だが許容する ZIP Content-Type 受理時の観測ログ方針（debug固定）が実装・テストで固定される
18. `get_documents()` で非dict JSON 応答時に `AttributeError` を漏らさず `EdinetAPIError` 化される
19. 実装完了時に Day5.md の巨大ドラフトを圧縮し、`src/` を単一の正として維持する
20. Day6 境界で API 由来 ZIP 解析 `ValueError` を `EdinetAPIError` に正規化する契約が固定される
21. （P2）`tests/conftest.py` の重い import 抑制が適用される

---

## 10. 成果物チェックリスト

- [ ] `src/edinet/api/_errors.py` 実装（エラー JSON 解釈の共通化）
- [ ] `src/edinet/api/download.py` 実装
- [ ] `tests/test_api/test_download.py` 実装
- [ ] `tests/test_api/test_documents.py` 実装
- [ ] `tests/test_api/test_errors.py` 実装
- [ ] `tests/fixtures/download/` は必要時のみ追加（基本はインメモリ生成）
- [ ] ZIP 処理がすべてインメモリ（ディスク一時保存なし）
- [ ] ZIP 安全上限（`MAX_ZIP_BYTES` / `MAX_MEMBER_COUNT` / `MAX_MEMBER_BYTES` / `MAX_TOTAL_UNCOMPRESSED_BYTES` / `MAX_XBRL_SCAN_BYTES_TOTAL`）を実装
- [ ] JSON エラー判定が `StatusCode` / `statusCode` / `metadata` の3形式をカバー
- [ ] `documents.py` 側の JSON エラー解釈も共通ヘルパー利用に置換
- [ ] ZIP系 Content-Type は許容リストで判定
- [ ] `type=1/3/4/5` + `application/pdf` の不開示ハンドリング方針を実装・テストで固定
- [ ] `get_documents(include_details=...)` の `type=2/1` 契約を回帰テストで固定
- [ ] 壊れた JSON 応答時の `EdinetAPIError.status_code` 維持挙動を回帰テストで固定
- [ ] 複数 XBRL 選択がテストで固定されている
- [ ] Day 6 に渡す I/F が文書化されている
- [ ] 公開 ZIP ヘルパーの入力検証（`zip_bytes` bytes-like / `member_name` 非空 str）を実装・テストで固定
- [ ] 仕様外だが許容する ZIP Content-Type 受理時の観測ログ方針（debug固定）を実装・テストで固定
- [ ] `get_documents()` の非dict JSON 応答で `EdinetAPIError` 化を回帰テストで固定
- [ ] Day5 実装完了時に `4.7` / `5.5` の巨大ドラフトを圧縮
- [ ] Day6 境界で API 由来 ZIP 解析 `ValueError` を `EdinetAPIError` に正規化する契約を固定
- [ ] （P2）`tests/conftest.py` の重い import 抑制を適用

---

## 11. レビュー反映ログ

### 初版

1. `PLAN.md` Day 5 要件を現在の実装状態（`download.py` 未実装、`tests/test_api` 空）に合わせて具体化
2. 仕様書に基づく Content-Type 判定を最優先要件として明示
3. `PublicDoc/*.xbrl` 複数候補選択のヒューリスティックを決定性付きで固定
4. フィクスチャは Git 管理しつつ、ZIP 自体はテスト内生成にして冪等性と可読性を両立

### 第2回フィードバック反映（品質優先レビュー）

1. XBRL 候補探索を `PublicDoc/` 固定から `*/PublicDoc/*.xbrl` 許容へ変更（`XBRL/PublicDoc/` を含む）。
2. 401 JSON のキー揺れ対応を追記（`StatusCode` / `statusCode` の両対応）。
3. 例外契約を修正し、`EdinetError` も明示（`_http.get()` の再試行枯渇を反映）。
4. フィクスチャ方針を整理し、基本はインメモリ ZIP 生成、固定再現ケースのみ fixture 追加に統一。
5. HTTP モック方針を `DummyResponse + monkeypatch` に統一し、本文とドラフトの不一致を解消。
6. テストケースを拡張（空 doc_id、壊れた JSON、`statusCode`、`XBRL/PublicDoc` 検出、`extract_zip_member` 異常系）。
7. 実行コマンドに `.venv` 直接実行の代替例を追記し、PowerShell 環境差分に対応。

### 第3回フィードバック反映（再現性・保守性レビュー）

1. `download.py` と `documents.py` のエラー JSON 解釈重複を解消するため、`api/_errors.py` 共通化方針を追加。
2. 手動 E2E の固定 `doc_id` 依存を廃止し、`get_documents()` から当日候補を動的選択する手順へ変更。
3. 実行前の依存セットアップ手順（`uv sync --dev` + `py -m pip` 代替）を Step -1 として追加。
4. `doc_id` バリデーション契約を強化（空/空白に加えて英数字以外を拒否）。
5. 境界テストを追加（Content-Type 欠落、`type=3/4/5` 送信確認、不正 ZIP の `find_primary_xbrl_path` / `extract_primary_xbrl`）。
6. md 実装ドラフトのドリフト対策として「実装後は `src/` を正」とする同期ルールと Step 6 を追加。

### 第4回フィードバック反映（整合性・境界強化レビュー）

1. `documents.py` を共通ヘルパーへ差し替える計画に合わせ、`tests/test_api/test_documents.py` 回帰テストを計画へ追加。
2. `type=1/3/4/5` で `application/pdf` が返るケースを「不開示の可能性」として扱う明示ポリシーを追加。
3. Step 0 に提出書類ファイル仕様書（ESE140104.pdf, ZIP構造）確認を明記。
4. 共通エラーヘルパーの責務を `parse_*` と `raise_*` に分離し、適用ルールを追加。
5. 境界テストを追加（`extract_zip_member` の不正 ZIP、`.XBRL` 大文字拡張子、`doc_id` 前後空白 `strip` 受理）。
6. 手動 E2E の候補抽出日付を固定値から「当日起点の直近7日探索」に変更。

### 第5回フィードバック反映（安全性・実行基盤レビュー）

1. ZIP 安全上限（`MAX_ZIP_BYTES` / `MAX_MEMBER_COUNT` / `MAX_MEMBER_BYTES`）を Day5 計画へ明記し、テスト固定対象に追加。
2. `api/_errors.py` の直接ユニットテストを追加し、`response.json()` 失敗・非 dict JSON・`status` 非数値などの境界挙動を単体で固定。
3. ZIP 系 Content-Type を完全一致から許容リスト判定へ変更（`application/octet-stream` / `application/zip` / `application/x-zip-compressed`）。
4. 既存 `src/script.py` の回帰リスクを避けるため、Day5 の手動 E2E は `tools/e2e_download_check.py` で分離実施する方針に変更。
5. 実行手順を `.venv` 直接実行優先に改訂し、`uv` は代替手段として併記。
6. Step 0 にベースラインテスト実行を追加し、実装差分の切り分けを先に可能化。

### 第6回フィードバック反映（実装契約・再現性レビュー）

1. Step 0 のコマンドに `PYTHONPATH=src` と `py -m pytest` 経路を追加し、`uv` 非依存でも再現可能に修正。
2. `DownloadFileType` の公開 I/F 表記を `expected_content_types(self) -> tuple[str, ...]` に統一し、実装ドラフトとの不整合を解消。
3. 例外契約を明文化し、ZIP 応答サイズ超過は `EdinetAPIError`、公開 ZIP ヘルパー入力不正は `ValueError` として分類固定。
4. `_http.get()` 由来の `EdinetError` を `download_document()` が透過することをテスト計画に追加。
5. 5.1 のテストファイル一覧へ `tests/test_api/test_errors.py` を明記し、実行漏れリスクを解消。
6. `_normalize_content_type()` の大小文字/空白揺れ（例: `Application/JSON ; charset=UTF-8`）をテストケースへ追加。
7. 公開 ZIP ヘルパーの防御一貫性を強化し、`_open_zip()` で `MAX_ZIP_BYTES` 検査を適用する方針を追加。
8. 完了条件の `git status` 判定を「作業開始時との差分で未意図変更がない」に修正。

### 第7回フィードバック反映（運用堅牢性レビュー）

1. 実行コマンドを `py -m ...` と `uv ...` の対称形に統一し、`.venv\\Scripts\\...` 直指定を廃止。
2. `download_document()` の `file_type` を実行時正規化（`DownloadFileType(file_type)`）する契約を追加。
3. ZIP 安全上限を拡張（`MAX_TOTAL_UNCOMPRESSED_BYTES`, `MAX_XBRL_SCAN_BYTES_TOTAL`）し、ZIP bomb 耐性を強化。
4. `get_documents(include_details=...)` の `type=2/1` 契約を `test_documents.py` 必須回帰ケースに追加。
5. `raise_for_api_error_response(..., default_status_code=response.status_code)` の必須ルールを明文化し、回帰テスト対象へ追加。
6. `_http.get()` 全量受信の制約を明記し、Day5の範囲（契約明確化と fail-fast）と次段階課題（ストリーミング受信上限）を分離。

### 第8回フィードバック反映（入力防御・運用分割レビュー）

1. `ValueError` 契約に合わせ、`_open_zip()` の `zip_bytes` bytes-like 検証と `extract_zip_member()` の `member_name` 非空 `str` 検証を計画へ追加。
2. ZIP 上限検証ロジックの重複を解消する方針（`_validate_zip_limits()` へ集約）を実装ドラフトへ反映。
3. `doc_id` バリデーション方針を Day5 では「仕様固定（厳格）」と明文化し、緩和時の更新ルールを追記。
4. 仕様外だが許容する ZIP Content-Type（`application/zip`, `application/x-zip-compressed`）受理時の観測ログ方針を追加。
5. 品質最優先モードとして Stage A/B/C の段階分割と段階ごとのテストゲートを追加。

### 第9回フィードバック反映（整合性・保守性レビュー）

1. Stage 分割の依存矛盾を解消し、Stage A を `api/_errors.py` + `download.py` に修正。
2. ZIP 安全上限の仕様とドラフトを一致させ、`_validate_zip_limits()` で `MAX_MEMBER_BYTES` を検査し、`_read_head_bytes()` 経由でも member 個別サイズ上限を強制。
3. `doc_id` 厳格方針の根拠（現行運用優先）を追記し、方針を一本化。
4. テスト方針を実装詳細固定から挙動固定へ寄せ、`default_status_code` 直接検証ではなく「壊れた JSON 時に HTTP status を保持」を主要契約に変更。
5. 仕様外許容 Content-Type の観測ログ方針を `debug` 固定に統一し、テスト条件のぶれを解消。

### 第10回フィードバック反映（実行可能性・保守性レビュー）

1. `documents.py` の非dict JSON 経路を回帰対象に明示し、`AttributeError` を漏らさない契約を追加。
2. `test_documents.py` の必須ケースに非dict JSON を追加し、`EdinetAPIError` 化を固定。
3. Step 3 の実装項目へ非dict JSON ケースを追記し、実装漏れを防止。
4. Step 6 と完了条件/チェックリストに、Day5 実装完了後の「巨大ドラフト圧縮」作業を明記。

### 第11回フィードバック反映（スコープ管理・責務境界レビュー）

1. Stage A/B/C に加え、P0/P1/P2 の止めどころを明文化（P1 を Day5 完了基準に設定）。
2. 例外契約へ「API 由来 ZIP の解析 `ValueError` は Day6 境界で `EdinetAPIError` に正規化」を追記。
3. `_errors` と `_http` の責務分離（非200/transport は `_http`、200内JSON解釈は `_errors`）を明文化し、Day5では統合しない方針を追加。
4. `tests/conftest.py` の重い import 抑制を P2 項目として計画に追加（`sys.modules` ベースの遅延リセット）。
5. 完了条件・チェックリストに P0/P1 判定と P2 任意項目（conftest軽量化、境界正規化契約）を反映。

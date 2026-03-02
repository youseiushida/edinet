# Day 6 — Company + 統合（公開 API / `Filing.fetch()` / 日付範囲ヘルパー）

## 0. 位置づけ

Day 6 は、Day 3〜5 で作った「低レベル API 部品」を利用者向けの導線に接続する日。
実装済みの `get_documents()` / `download_document()` / ZIP ヘルパーを、`edinet.documents()` と `Filing.fetch()` に統合する。

Day 6 完了時点のマイルストーン:

```python
import os
from edinet import configure, documents

configure(api_key=os.environ["EDINET_API_KEY"])
filings = documents("2026-01-20", doc_type="120")
path, xbrl_bytes = filings[0].fetch()
print(filings[0].doc_id, path, len(xbrl_bytes))
```

---

## 1. 現在実装の確認結果（2026-02-16 時点）

現状コードを読み取った結果、Day 6 で埋めるべきギャップは次の通り:

| ファイル | 現状 | Day 6 で必要な変更 |
|---|---|---|
| `src/edinet/__init__.py` | **0 行（空）** | `configure` / `documents` の公開 API 実装 |
| `src/edinet/api/__init__.py` | **0 行（空）** | 低レベル API の再エクスポート |
| `src/edinet/models/company.py` | **0 行（空）** | `Company` モデル実装 |
| `src/edinet/models/filing.py` | モデル変換まで実装済み（`fetch` なし） | `company` プロパティ、`fetch`、キャッシュ追加 |
| `src/edinet/api/documents.py` | `get_documents(date, include_details)` 実装済み | Day6 側でラップ利用（本体は原則維持） |
| `src/edinet/api/download.py` | `download_document()` と ZIP ヘルパー実装済み | Day6 の `Filing.fetch()` で接続 |

既存テスト状況（要点）:

- `tests/test_api/test_documents.py`: 低レベル `get_documents()` 契約は固定済み
- `tests/test_api/test_download.py`: Day5 の ZIP 契約は固定済み
- `tests/test_models/test_filing.py`: 変換系テストはあるが `fetch`/`company` は未カバー

---

## 2. Day 6 のゴール

1. `Company` モデルを実装し、`Filing` から `filing.company` で参照可能にする  
2. `Filing.fetch()` を実装し、Day5 API を使って `(.xbrl path, bytes)` を返す  
3. `Filing.fetch()` に遅延評価 + キャッシュを入れ、同一インスタンスの再DLを防ぐ  
4. `edinet.documents()` を公開し、単日・日付範囲・`doc_type` フィルタを提供する  
5. `src/edinet/__init__.py` / `src/edinet/api/__init__.py` の公開導線を整備する  

---

## 3. スコープ / 非スコープ

### 3.1 Day 6 のスコープ

- `Company` モデル（`edinet_code`, `name_ja`, `sec_code`）
- `Filing.company` プロパティ
- `Filing.fetch()` + `clear_fetch_cache()`（ZIP + XBRL キャッシュ）
- `edinet.documents(date|start/end, doc_type, edinet_code)` 公開 API
- `Company.get_filings()`（`edinet_code` での絞り込み）
- 単体テスト追加（models / public api）

### 3.2 Day 6 でやらないこと

- `Company("7203")` の自動変換（証券コード→edinet_code）
- 企業名あいまい検索・ティッカー検索
- XBRL パース（`xbrl/parser.py` は Day9 以降）
- async 化（ただし将来 async 化しやすい日付ループ分離は行う）

`PLAN.md` の注意事項に合わせ、Day 6 は **edinet_code 直指定**を正とする。
サンプルは `Company(edinet_code="E02144")` を使う。

---

## 4. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/models/company.py` | 新規実装 | Company モデル |
| `src/edinet/_validators.py` | 新規実装 | `edinet_code` 正規化の共通ヘルパー |
| `src/edinet/models/filing.py` | 追記 | `company` / `fetch` / private cache |
| `src/edinet/exceptions.py` | 追記 | `EdinetParseError` 追加（解析失敗の責務分離） |
| `src/edinet/__init__.py` | 新規実装 | 公開 API (`configure`, `documents`) |
| `src/edinet/api/__init__.py` | 新規実装 | 低レベル API エクスポート |
| `src/edinet/models/__init__.py` | 追記 | `Company` を後方互換導線へ追加 |
| `tests/test_models/test_company.py` | 新規 | Company 単体テスト |
| `tests/test_models/test_validators.py` | 新規 | 共通バリデータ（`edinet_code`）テスト |
| `tests/test_models/test_filing.py` | 追記 | `company` / `fetch` テスト |
| `tests/test_api/test_public_api.py` | 新規 | `edinet.documents()` の公開契約テスト |
| `tests/test_api/test_errors.py` | 追記 | `EdinetParseError` の契約テスト |

---

## 5. 設計詳細

## 5.1 `Company` モデル

- `frozen=True` を維持（`Filing` と同じ不変モデル方針）
- `edinet_code` は `E` + 5桁に厳格一致（`Company` 単体でも早期検証）
- `ticker` は `sec_code[:4]` の computed field
- `Company.from_filing(filing)` で `Filing` との橋渡しを行う
- `Company.get_filings()` は `edinet.documents(..., edinet_code=...)` を呼び、raw `results` 先絞りを利用する
- `Company.get_filings()` は日付引数省略時 `date=today(JST)` で実行する（EDINET基準）
- JST 日付取得は `ZoneInfo("Asia/Tokyo")` を優先し、tzdb 未導入環境では UTC+9 固定でフォールバックする
- 運用では `tzdata` 依存を推奨（Windows / minimal container の再現性確保）

`edinet_code` は主キーなので `str` 必須。`Filing` 側で `None` のときは `company=None` とする。

## 5.2 `Filing.fetch()` の契約

戻り値:

- `tuple[str, bytes]` = `(primary_xbrl_path, primary_xbrl_bytes)`

例外契約:

1. `EdinetError`: 通信層失敗（`download_document` から透過）
2. `EdinetAPIError`: API業務エラー（`xbrlFlag=0`, HTTP/JSON エラー等）
3. `EdinetParseError`: ダウンロード済み ZIP の解析失敗、primary 不在、`download_document` 実行時 `ValueError`（入力不正や前提条件違反）を正規化したもの
4. `ValueError`: `Filing.fetch()` では原則外へ漏らさない（ZIP ヘルパー/`download_document` 由来は `EdinetParseError` に正規化）
5. `download_document` が送出する `EdinetError` / `EdinetAPIError` は `Filing.fetch()` でラップせず透過する

※ Day5 文書の「ZIP 解析失敗を `EdinetAPIError` へ正規化」方針は、責務分離を優先して Day6 で更新し、`EdinetParseError` へ一本化する。

キャッシュ方針:

- `Filing` は `frozen=True` を維持
- キャッシュは `PrivateAttr` で保持:
  - `_zip_cache: bytes | None`
  - `_xbrl_cache: tuple[str, bytes] | None`
- `refresh=True` で強制再取得
- `clear_fetch_cache()` で明示破棄

## 5.3 `edinet.documents()` 公開 API

入力パターン:

1. 単日: `documents("2026-02-07")`
2. 範囲: `documents(start="2026-02-01", end="2026-02-07")`
3. 型式絞り込み: `doc_type="120"` または `doc_type=DocType.ANNUAL_SECURITIES_REPORT`
4. 提出者絞り込み（`Company.get_filings()` 用）: `edinet_code="E02144"`

バリデーション:

- `date` と `start/end` は排他
- `start/end` は両方必須
- `start <= end` 必須
- 日付は `YYYY-MM-DD`（`date` オブジェクトのみ許容、`datetime` は拒否）
- `doc_type` 文字列は **公式コードに厳格一致**（`DocType` に変換できない値は即 `ValueError`）
- `doc_type` の正当性判定は Day4 で確定した `DocType`（EDINET API 仕様書 `ESE140206` 基準）を正とし、`FormCode` 定義（`ESE140327`）を参照しない
- 日付範囲は **最大366日**（誤指定による大量 API 呼び出しを防止）
- `edinet_code` 文字列は `E` + 5桁に厳格一致（不正値は `ValueError`）
- `edinet_code` は前後空白を除去し大文字へ正規化して判定（例: `" e02144 "` → `"E02144"`）
- `edinet_code` 検証は `normalize_edinet_code()`（共通ヘルパー）に一本化する
- 日付入力の型不正（例: int, datetime）や区切り不正（`"2026/02/07"`）は即 `ValueError`
- `edinet_code` の型不正（例: int）は `AttributeError` ではなく `ValueError` を返す

実装方針:

- 日付ループは `_iter_dates_inclusive(start, end)` に分離（将来 async 化の足場）
- 低レベル API (`get_documents`) は変更せず利用する
- 返り値は `list[Filing]` に統一
- 公開 `documents()` では `type=2`（提出書類一覧+メタデータ）を固定し、`include_details` は受けない
- メタデータのみ（`type=1`）が必要な場合は低レベル `edinet.api.get_documents(..., include_details=False)` を使う
- 日次レスポンスは `metadata.resultset.count` と `len(results)` の一致を検証し、不一致は fail-fast
- `doc_type` 指定時は **raw JSON (`docTypeCode`) で先に絞り込み、対象だけ `Filing` 化**する  
  （非対象書類の壊れデータで全体失敗しないようにする）
- `edinet_code` 指定時も **raw JSON (`edinetCode`) で先に絞り込み、対象だけ `Filing` 化**する
- フィルタ指定時は `results` 内の非dict行を無視し、対象行のみ `Filing` 化する
- フィルタ未指定時に `results` が `list[dict]` でない場合は `EdinetParseError` を返す
- `Filing.from_api_list()` が返す `ValueError` は `documents()` 境界で `EdinetParseError` に正規化する（`raise ... from exc`）
- 取り下げ済み (`withdrawalStatus="1"`) レコードで主要項目が `None` になる実データがあるため、`docTypeCode` / `ordinanceCode` / `formCode` / `filerName` / `docDescription` の欠損を許容したまま `Filing` 化する

`documents()` の例外契約:

1. `ValueError`: 呼び出し引数の不正（date/doc_type/edinet_code）
2. `EdinetError` / `EdinetAPIError`: `get_documents()` から透過
3. `EdinetParseError`: API レスポンス形状異常（`results` 型不正、`resultset.count` 不一致/不正など）および `Filing` 変換失敗の正規化

## 5.4 `api/__init__.py` の扱い

Day 6 で `api/__init__.py` を明示化し、低レベル API を再エクスポートする:

- `get_documents`
- `DownloadFileType`
- `download_document`
- `list_zip_members`
- `find_primary_xbrl_path`
- `extract_zip_member`
- `extract_primary_xbrl`

---

## 6. 実装ドラフト（コピペ用）

### 6.0 `src/edinet/_validators.py`

```python
"""モデル横断の入力バリデーションヘルパー。"""
from __future__ import annotations

import re

_EDINET_CODE_PATTERN = re.compile(r"^E\d{5}$")


def normalize_edinet_code(
    value: str | None,
    *,
    allow_none: bool = True,
) -> str | None:
    """edinet_code を正規化し、形式不正なら ValueError を送出する。"""
    if value is None:
        if allow_none:
            return None
        raise ValueError("edinet_code must not be None")

    if not isinstance(value, str):
        raise ValueError("edinet_code must be str or None")

    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("edinet_code must not be empty")
    if not _EDINET_CODE_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"Invalid edinet_code: {value!r}. Expected format like 'E02144'."
        )
    return normalized
```

### 6.1 `src/edinet/models/company.py`

```python
"""Company モデル（Day 6 実装）。"""
from __future__ import annotations

from datetime import date as DateType, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, computed_field, field_validator
from edinet._validators import normalize_edinet_code

if TYPE_CHECKING:
    from edinet.models.doc_types import DocType
    from edinet.models.filing import Filing

def _today_jst() -> DateType:
    """EDINET（JST）基準の日付を返す。tzdb 無し環境では UTC+9 でフォールバック。"""
    try:
        return datetime.now(ZoneInfo("Asia/Tokyo")).date()
    except ZoneInfoNotFoundError:
        # Windows / minimal container など tzdb 未導入環境向け
        return (datetime.now(timezone.utc) + timedelta(hours=9)).date()


class Company(BaseModel):
    """提出者（企業）の Day6 モデル。

    Day 6 では EDINET コードを主キーとして扱う。
    """

    model_config = ConfigDict(frozen=True)

    edinet_code: str
    name_ja: str | None = None
    sec_code: str | None = None

    @field_validator("edinet_code")
    @classmethod
    def _validate_edinet_code(cls, value: str) -> str:
        normalized = normalize_edinet_code(value, allow_none=False)
        assert isinstance(normalized, str)
        return normalized

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ticker(self) -> str | None:
        """証券コード4桁。"""
        if self.sec_code and len(self.sec_code) >= 4:
            return self.sec_code[:4]
        return None

    @classmethod
    def from_filing(cls, filing: Filing) -> Company | None:
        """Filing から Company を構築する。edinet_code が無ければ None。"""
        if filing.edinet_code is None:
            return None
        return cls(
            edinet_code=filing.edinet_code,
            name_ja=filing.filer_name,
            sec_code=filing.sec_code,
        )

    def get_filings(
        self,
        date: str | DateType | None = None,
        *,
        start: str | DateType | None = None,
        end: str | DateType | None = None,
        doc_type: DocType | str | None = None,
    ) -> list[Filing]:
        """この企業の Filing 一覧を返す（raw `edinetCode` 先絞り）。

        Note:
            date / start / end を全省略した場合は `date=today(JST)` とみなす。
        """
        from edinet import documents

        if date is None and start is None and end is None:
            date = _today_jst()

        return documents(
            date,
            start=start,
            end=end,
            doc_type=doc_type,
            edinet_code=self.edinet_code,
        )

    def __str__(self) -> str:
        name = self.name_ja or "(不明)"
        return f"Company({self.edinet_code} | {name} | {self.ticker})"
```

### 6.2 `src/edinet/models/filing.py`（追記差分）

#### 6.2.1 import 追記

```python
from pydantic import BaseModel, ConfigDict, PrivateAttr, computed_field
```

```python
if TYPE_CHECKING:
    from edinet.models.company import Company
    from edinet.models.form_code import FormCodeEntry
```

#### 6.2.2 `Filing` クラス内に PrivateAttr 追加（フィールド定義の直後）

```python
    # --- Day 6: fetch キャッシュ（frozen=True と両立させるため PrivateAttr を使用） ---
    _zip_cache: bytes | None = PrivateAttr(default=None)
    _xbrl_cache: tuple[str, bytes] | None = PrivateAttr(default=None)
```

#### 6.2.3 `Filing` クラス内に `company` / `fetch` / `clear_fetch_cache` を追加

```python
    @property
    def company(self) -> Company | None:
        """提出者 Company。edinet_code が無い場合は None。"""
        if self.edinet_code is None:
            return None
        from edinet.models.company import Company

        return Company(
            edinet_code=self.edinet_code,
            name_ja=self.filer_name,
            sec_code=self.sec_code,
        )

    def clear_fetch_cache(self) -> None:
        """fetch 用キャッシュを明示的に破棄する。"""
        self._zip_cache = None
        self._xbrl_cache = None

    def fetch(self, *, refresh: bool = False) -> tuple[str, bytes]:
        """提出本文書 ZIP から代表 XBRL を取得する。

        Returns:
            (xbrl_path, xbrl_bytes)
        """
        from edinet.api.download import (
            DownloadFileType,
            download_document,
            extract_primary_xbrl,
        )
        from edinet.exceptions import EdinetAPIError, EdinetParseError

        if not self.has_xbrl:
            raise EdinetAPIError(
                0,
                f"Document has no XBRL (doc_id={self.doc_id}, xbrlFlag=0).",
            )

        if refresh:
            self.clear_fetch_cache()

        if self._xbrl_cache is not None:
            return self._xbrl_cache

        if self._zip_cache is None:
            try:
                self._zip_cache = download_document(
                    self.doc_id,
                    file_type=DownloadFileType.XBRL_AND_AUDIT,
                )
            except ValueError as exc:
                raise EdinetParseError(
                    f"Failed to download XBRL ZIP for fetch "
                    f"(doc_id={self.doc_id!r}): {exc}",
                ) from exc

        try:
            result = extract_primary_xbrl(self._zip_cache)
        except ValueError as exc:
            # 壊れた ZIP キャッシュを保持しない（次回呼び出しで再取得可能にする）
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"Failed to parse EDINET ZIP for doc_id={self.doc_id}.",
            ) from exc

        if result is None:
            # has_xbrl=True なのに primary が見つからない場合も再試行余地を残す
            self.clear_fetch_cache()
            raise EdinetParseError(
                f"Primary XBRL not found in ZIP for doc_id={self.doc_id}.",
            )

        self._xbrl_cache = result
        return result
```

#### 6.2.4 `src/edinet/exceptions.py` 追記

```python
class EdinetParseError(EdinetError):
    """取得済みデータ（JSON/ZIP/XBRL）の解析に失敗した。"""
```

### 6.3 `src/edinet/__init__.py`

```python
"""edinet パッケージの公開 API。"""
from __future__ import annotations

from datetime import date as DateType, datetime as DateTimeType, timedelta
from typing import Any

from edinet._config import configure
from edinet.exceptions import EdinetParseError
from edinet.models.company import Company
from edinet.models.doc_types import DocType
from edinet.models.filing import Filing
from edinet._validators import normalize_edinet_code

MAX_DOCUMENT_RANGE_DAYS = 366


def documents(
    date: str | DateType | None = None,
    *,
    start: str | DateType | None = None,
    end: str | DateType | None = None,
    doc_type: DocType | str | None = None,
    edinet_code: str | None = None,
) -> list[Filing]:
    """提出書類を Filing のリストで返す（単日 or 日付範囲）。

    Note:
        - doc_type 文字列は DocType へ厳格変換する（未知コードは ValueError）
        - edinet_code 文字列は E + 5桁に厳格一致
        - 日付は date/`YYYY-MM-DD` のみ（datetime は ValueError）
        - 日付範囲は最大 366 日
        - API レスポンス形状異常（count 不一致など）は EdinetParseError
    """
    if date is not None and (start is not None or end is not None):
        raise ValueError("date and start/end are mutually exclusive")
    if date is None and (start is None or end is None):
        raise ValueError("Specify either date or both start/end")

    if date is not None:
        start_date = _coerce_date(date, field_name="date")
        end_date = start_date
    else:
        assert start is not None and end is not None
        start_date = _coerce_date(start, field_name="start")
        end_date = _coerce_date(end, field_name="end")
        if start_date > end_date:
            raise ValueError("start must be <= end")
    _validate_date_span(start_date, end_date)

    doc_type_code = _normalize_doc_type(doc_type)
    normalized_edinet_code = normalize_edinet_code(edinet_code)

    from edinet.api.documents import get_documents

    out: list[Filing] = []
    for current in _iter_dates_inclusive(start_date, end_date):
        api_response = get_documents(
            current.isoformat(),
            include_details=True,  # list[Filing] 公開 API は type=2 固定
        )
        parse_target = _prepare_response_for_filing_parse(
            api_response,
            doc_type_code=doc_type_code,
            edinet_code=normalized_edinet_code,
        )
        try:
            daily = Filing.from_api_list(parse_target)
        except ValueError as exc:
            raise EdinetParseError(
                "Failed to parse filings in documents() for "
                f"date={current.isoformat()}: {exc}",
            ) from exc
        out.extend(daily)
    return out


def _coerce_date(value: str | DateType, *, field_name: str) -> DateType:
    if isinstance(value, DateTimeType):
        raise ValueError(
            f"{field_name} must be YYYY-MM-DD date without time component"
        )
    if isinstance(value, DateType):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be YYYY-MM-DD string or date")
    try:
        return DateType.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be YYYY-MM-DD, got {value!r}",
        ) from exc


def _iter_dates_inclusive(start: DateType, end: DateType):
    """日付ループを独立関数化（将来の async 化準備）。"""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _validate_date_span(start: DateType, end: DateType) -> None:
    """日付範囲の上限を検証する。"""
    days = (end - start).days + 1
    if days > MAX_DOCUMENT_RANGE_DAYS:
        raise ValueError(
            f"Date range too large: {days} days. "
            f"Maximum is {MAX_DOCUMENT_RANGE_DAYS} days."
        )


def _validate_resultset_count(api_response: dict[str, Any]) -> list[Any]:
    """metadata.resultset.count と results 件数の一致を検証する。"""
    metadata = api_response.get("metadata")
    if not isinstance(metadata, dict):
        raise EdinetParseError("EDINET API response 'metadata' must be dict")

    resultset = metadata.get("resultset")
    if not isinstance(resultset, dict):
        raise EdinetParseError("EDINET API response 'metadata.resultset' must be dict")

    count_raw = resultset.get("count")
    try:
        declared_count = int(str(count_raw))
    except (TypeError, ValueError) as exc:
        raise EdinetParseError(
            "EDINET API response 'metadata.resultset.count' must be int-compatible",
        ) from exc

    raw_results = api_response.get("results")
    if not isinstance(raw_results, list):
        raise EdinetParseError("EDINET API response 'results' must be list")

    if declared_count != len(raw_results):
        raise EdinetParseError(
            f"EDINET API result count mismatch: metadata={declared_count}, "
            f"results={len(raw_results)}"
        )
    return raw_results


def _prepare_response_for_filing_parse(
    api_response: dict[str, Any],
    *,
    doc_type_code: str | None,
    edinet_code: str | None,
) -> dict[str, Any]:
    """doc_type / edinet_code 指定時は raw results を先に絞ってから Filing 化する。"""
    raw_results = _validate_resultset_count(api_response)

    if doc_type_code is None and edinet_code is None:
        if not all(isinstance(row, dict) for row in raw_results):
            raise EdinetParseError(
                "EDINET API response 'results' must be list[dict] "
                "when no filters are specified",
            )
        return api_response

    filtered_results = [
        row
        for row in raw_results
        if isinstance(row, dict)
        and (doc_type_code is None or row.get("docTypeCode") == doc_type_code)
        and (edinet_code is None or row.get("edinetCode") == edinet_code)
    ]
    response_for_parse = dict(api_response)
    response_for_parse["results"] = filtered_results
    metadata = api_response.get("metadata")
    if isinstance(metadata, dict):
        metadata_copy = dict(metadata)
        resultset = metadata_copy.get("resultset")
        if isinstance(resultset, dict):
            resultset_copy = dict(resultset)
            resultset_copy["count"] = str(len(filtered_results))
            metadata_copy["resultset"] = resultset_copy
            response_for_parse["metadata"] = metadata_copy
    return response_for_parse


def _normalize_doc_type(doc_type: DocType | str | None) -> str | None:
    if doc_type is None:
        return None
    if isinstance(doc_type, DocType):
        return doc_type.value
    if isinstance(doc_type, str):
        normalized = doc_type.strip()
        if not normalized:
            raise ValueError("doc_type must not be empty")
        try:
            return DocType(normalized).value
        except ValueError as exc:
            raise ValueError(
                f"Unknown doc_type: {doc_type!r}. "
                "Use valid docTypeCode such as '120' or DocType enum."
            ) from exc
    raise ValueError("doc_type must be DocType, str, or None")

__all__ = [
    "configure",
    "documents",
    "Company",
    "Filing",
    "DocType",
]
```

### 6.4 `src/edinet/api/__init__.py`

```python
"""edinet.api の公開エントリ。"""
from edinet.api.documents import get_documents
from edinet.api.download import (
    DownloadFileType,
    download_document,
    extract_primary_xbrl,
    extract_zip_member,
    find_primary_xbrl_path,
    list_zip_members,
)

__all__ = [
    "get_documents",
    "DownloadFileType",
    "download_document",
    "list_zip_members",
    "find_primary_xbrl_path",
    "extract_zip_member",
    "extract_primary_xbrl",
]
```

### 6.5 `src/edinet/models/__init__.py`（追記）

```python
from edinet.models.company import Company
```

```python
__all__ = [
    "Company",
    "DocType",
    "Filing",
    "OrdinanceCode",
    "FormCodeEntry",
    "get_form_code",
    "all_form_codes",
]
```

---

## 7. テスト計画（Small 中心）

## 7.1 新規テストファイル

1. `tests/test_models/test_company.py`（`from_filing` / `get_filings`）
2. `tests/test_models/test_validators.py`（`normalize_edinet_code`）
3. `tests/test_api/test_public_api.py`（`documents` の公開契約 + レスポンス整合チェック）
4. `tests/test_api/test_api_exports.py`（`edinet.api` 再エクスポート契約）

## 7.2 既存テスト追記

1. `tests/test_models/test_filing.py`（`company` / `fetch` / cache / no-XBRL 異常系 / 透過例外契約）
2. `tests/test_api/test_errors.py`（`EdinetParseError` 追加分）

## 7.3 実装ドラフト

### 7.3.1 `tests/test_models/test_company.py`

```python
"""company.py のテスト。"""
from __future__ import annotations

from datetime import date as DateType, datetime, timezone
from zoneinfo import ZoneInfoNotFoundError

import pytest

from edinet.models.doc_types import DocType
from edinet.models.company import Company
from edinet.models.filing import Filing


def _sample_doc(*, doc_id: str, edinet_code: str | None) -> dict:
    return {
        "seqNumber": 1,
        "docID": doc_id,
        "edinetCode": edinet_code,
        "secCode": "72030",
        "filerName": "トヨタ自動車株式会社",
        "docTypeCode": "120",
        "submitDateTime": "2025-06-26 15:00",
        "xbrlFlag": "1",
        "pdfFlag": "1",
        "attachDocFlag": "0",
        "englishDocFlag": "0",
        "csvFlag": "0",
    }


def test_ticker_property() -> None:
    company = Company(edinet_code="E02144", name_ja="トヨタ", sec_code="72030")
    assert company.ticker == "7203"


def test_company_normalizes_edinet_code() -> None:
    company = Company(edinet_code=" e02144 ")
    assert company.edinet_code == "E02144"


def test_company_rejects_invalid_edinet_code() -> None:
    with pytest.raises(ValueError, match="Invalid edinet_code"):
        Company(edinet_code="7203")


def test_from_filing_returns_company() -> None:
    filing = Filing.from_api_response(_sample_doc(doc_id="S100TEST", edinet_code="E02144"))
    company = Company.from_filing(filing)
    assert company is not None
    assert company.edinet_code == "E02144"
    assert company.name_ja == "トヨタ自動車株式会社"


def test_from_filing_returns_none_when_edinet_code_missing() -> None:
    filing = Filing.from_api_response(_sample_doc(doc_id="S100TEST", edinet_code=None))
    assert Company.from_filing(filing) is None


def test_get_filings_filters_by_edinet_code(monkeypatch: pytest.MonkeyPatch) -> None:
    company = Company(edinet_code="E02144", name_ja="トヨタ", sec_code="72030")
    called: dict[str, object] = {}

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        called["date"] = date
        called["start"] = start
        called["end"] = end
        called["doc_type"] = doc_type
        called["edinet_code"] = edinet_code
        return [Filing.from_api_response(_sample_doc(doc_id="S100T001", edinet_code="E02144"))]

    monkeypatch.setattr("edinet.documents", fake_documents)

    result = company.get_filings("2026-02-07", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    assert [f.doc_id for f in result] == ["S100T001"]
    assert called["edinet_code"] == "E02144"


def test_get_filings_forwards_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    company = Company(edinet_code="E02144")
    called: dict[str, object] = {}

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        called["date"] = date
        called["start"] = start
        called["end"] = end
        called["doc_type"] = doc_type
        called["edinet_code"] = edinet_code
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)

    company.get_filings(
        start="2026-02-01",
        end="2026-02-07",
        doc_type="120",
    )
    assert called == {
        "date": None,
        "start": "2026-02-01",
        "end": "2026-02-07",
        "doc_type": "120",
        "edinet_code": "E02144",
    }


def test_get_filings_defaults_to_today(monkeypatch: pytest.MonkeyPatch) -> None:
    company = Company(edinet_code="E02144")
    called: dict[str, object] = {}
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: DateType(2026, 2, 16))

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        called["date"] = date
        called["start"] = start
        called["end"] = end
        called["doc_type"] = doc_type
        called["edinet_code"] = edinet_code
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)

    company.get_filings()
    assert called == {
        "date": DateType(2026, 2, 16),
        "start": None,
        "end": None,
        "doc_type": None,
        "edinet_code": "E02144",
    }


def test_today_jst_falls_back_when_tzdb_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from edinet.models import company as company_module

    class FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return datetime(2026, 2, 16, 0, 0, 0)
            return datetime(2026, 2, 15, 15, 0, 0, tzinfo=timezone.utc)

    def fake_zone_info(_name: str):
        raise ZoneInfoNotFoundError("tzdb missing")

    monkeypatch.setattr(company_module, "datetime", FakeDateTime)
    monkeypatch.setattr(company_module, "ZoneInfo", fake_zone_info)

    # UTC 2026-02-15 15:00 + 9h = JST 2026-02-16 00:00
    assert company_module._today_jst() == DateType(2026, 2, 16)
```

### 7.3.1b `tests/test_models/test_validators.py`

```python
"""共通バリデータのテスト。"""
from __future__ import annotations

import pytest

from edinet._validators import normalize_edinet_code


def test_normalize_edinet_code_accepts_valid_value() -> None:
    assert normalize_edinet_code(" e02144 ") == "E02144"


def test_normalize_edinet_code_allows_none_when_configured() -> None:
    assert normalize_edinet_code(None) is None


def test_normalize_edinet_code_rejects_none_when_not_allowed() -> None:
    with pytest.raises(ValueError, match="must not be None"):
        normalize_edinet_code(None, allow_none=False)


def test_normalize_edinet_code_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="must be str or None"):
        normalize_edinet_code(7203)  # type: ignore[arg-type]
```

### 7.3.2 `tests/test_api/test_public_api.py`

```python
"""公開 API (`edinet.documents`) のテスト。"""
from __future__ import annotations

from datetime import date, datetime

import pytest

import edinet
from edinet.exceptions import EdinetParseError
from edinet.models.doc_types import DocType


def _api_doc(doc_id: str, *, doc_type_code: str = "120", edinet_code: str = "E02144") -> dict:
    return {
        "seqNumber": 1,
        "docID": doc_id,
        "edinetCode": edinet_code,
        "secCode": "72030",
        "filerName": "テスト株式会社",
        "docTypeCode": doc_type_code,
        "submitDateTime": "2026-02-07 12:00",
        "xbrlFlag": "1",
        "pdfFlag": "1",
        "attachDocFlag": "0",
        "englishDocFlag": "0",
        "csvFlag": "0",
    }


def _api_response(results: list[dict], *, count: int | str | None = None) -> dict:
    declared_count = len(results) if count is None else count
    return {
        "metadata": {
            "status": "200",
            "message": "OK",
            "resultset": {"count": str(declared_count)},
        },
        "results": results,
    }


def test_documents_single_date(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[tuple[str, bool]] = []

    def fake_get_documents(date_str: str, *, include_details: bool = True):
        called.append((date_str, include_details))
        return _api_response([_api_doc("S100A001")])

    monkeypatch.setattr("edinet.api.documents.get_documents", fake_get_documents)

    filings = edinet.documents("2026-02-07")
    assert [f.doc_id for f in filings] == ["S100A001"]
    assert called == [("2026-02-07", True)]


def test_documents_accepts_withdrawn_record_with_nullable_core_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _api_doc("S100XJNI")
    row["withdrawalStatus"] = "1"
    row["docTypeCode"] = None
    row["ordinanceCode"] = None
    row["formCode"] = None
    row["filerName"] = None
    row["docDescription"] = None

    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response([row]),
    )
    filings = edinet.documents("2026-02-07")
    assert len(filings) == 1
    assert filings[0].withdrawal_status == "1"
    assert filings[0].doc_type_code is None
    assert filings[0].filer_name is None
    assert filings[0].doc_description is None


def test_documents_date_object_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response([_api_doc("S100A001")]),
    )
    filings = edinet.documents(date(2026, 2, 7))
    assert len(filings) == 1


def test_documents_date_range_inclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    responses = {
        "2026-02-07": [_api_doc("S100A007")],
        "2026-02-08": [_api_doc("S100A008")],
        "2026-02-09": [_api_doc("S100A009")],
    }

    def fake_get_documents(date_str: str, *, include_details: bool = True):
        called.append(date_str)
        return _api_response(responses[date_str])

    monkeypatch.setattr("edinet.api.documents.get_documents", fake_get_documents)

    filings = edinet.documents(start="2026-02-07", end="2026-02-09")
    assert [f.doc_id for f in filings] == ["S100A007", "S100A008", "S100A009"]
    assert called == ["2026-02-07", "2026-02-08", "2026-02-09"]


def test_documents_filters_by_doc_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100A120", doc_type_code="120"),
                _api_doc("S100A140", doc_type_code="140"),
            ]
        ),
    )
    filings = edinet.documents("2026-02-07", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    assert [f.doc_id for f in filings] == ["S100A120"]


def test_documents_prefilters_raw_results_before_filing_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 非対象(140)が壊れていても、対象(120)だけで成功することを確認
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100A120", doc_type_code="120"),
                {"docTypeCode": "140", "broken": "missing required fields"},
            ]
        ),
    )
    filings = edinet.documents("2026-02-07", doc_type="120")
    assert [f.doc_id for f in filings] == ["S100A120"]


def test_documents_prefilters_raw_results_even_if_non_dict_row_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A120", doc_type_code="120"), "broken-row"],  # type: ignore[list-item]
            count=2,
        ),
    )
    filings = edinet.documents("2026-02-07", doc_type="120")
    assert [f.doc_id for f in filings] == ["S100A120"]


def test_documents_raises_parse_error_when_result_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A001")],
            count=99,  # 実件数と不一致
        ),
    )
    with pytest.raises(EdinetParseError, match="result count mismatch"):
        edinet.documents("2026-02-07")


def test_documents_normalizes_filing_parse_value_error_to_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [{"docTypeCode": "120", "broken": "missing required fields"}],
            count=1,
        ),
    )
    with pytest.raises(EdinetParseError, match="Failed to parse filings in documents\\(\\)"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_metadata_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {"results": []},
    )
    with pytest.raises(EdinetParseError, match="response 'metadata' must be dict"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_resultset_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {
            "metadata": {"status": "200", "message": "OK"},
            "results": [],
        },
    )
    with pytest.raises(EdinetParseError, match="response 'metadata.resultset' must be dict"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_result_count_is_not_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {
            "metadata": {
                "status": "200",
                "message": "OK",
                "resultset": {"count": "NaN"},
            },
            "results": [],
        },
    )
    with pytest.raises(EdinetParseError, match="count' must be int-compatible"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_results_is_not_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {
            "metadata": {"status": "200", "message": "OK", "resultset": {"count": "1"}},
            "results": {"not": "list"},
        },
    )
    with pytest.raises(EdinetParseError, match="response 'results' must be list"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_results_contains_non_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A001"), "broken"],  # type: ignore[list-item]
            count=2,
        ),
    )
    with pytest.raises(EdinetParseError, match="response 'results' must be list\\[dict\\]"):
        edinet.documents("2026-02-07")


def test_documents_prefilters_by_edinet_code_before_filing_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100T001", doc_type_code="120", edinet_code="E02144"),
                {"edinetCode": "E00001", "broken": "missing required fields"},
            ]
        ),
    )
    filings = edinet.documents("2026-02-07", edinet_code="E02144")
    assert [f.doc_id for f in filings] == ["S100T001"]


def test_documents_normalizes_edinet_code_for_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100T001", doc_type_code="120", edinet_code="E02144"),
                _api_doc("S100O001", doc_type_code="120", edinet_code="E00001"),
            ]
        ),
    )
    filings = edinet.documents("2026-02-07", edinet_code=" e02144 ")
    assert [f.doc_id for f in filings] == ["S100T001"]


def test_documents_rejects_invalid_doc_type_string() -> None:
    # O/I 混在の典型 typo。0件サイレントを防ぐ
    with pytest.raises(ValueError, match="Unknown doc_type"):
        edinet.documents("2026-02-07", doc_type="12O")


def test_documents_does_not_accept_include_details_argument() -> None:
    with pytest.raises(TypeError):
        edinet.documents("2026-02-07", include_details=False)  # type: ignore[call-arg]


def test_documents_rejects_invalid_edinet_code() -> None:
    with pytest.raises(ValueError, match="Invalid edinet_code"):
        edinet.documents("2026-02-07", edinet_code="7203")


def test_documents_rejects_non_string_edinet_code() -> None:
    with pytest.raises(ValueError, match="edinet_code must be str or None"):
        edinet.documents("2026-02-07", edinet_code=7203)  # type: ignore[arg-type]


def test_documents_rejects_invalid_date_format() -> None:
    with pytest.raises(ValueError, match="date must be YYYY-MM-DD"):
        edinet.documents("2026/02/07")


def test_documents_rejects_invalid_date_type() -> None:
    with pytest.raises(ValueError, match="date must be YYYY-MM-DD string or date"):
        edinet.documents(20260207)  # type: ignore[arg-type]


def test_documents_rejects_datetime_value() -> None:
    with pytest.raises(ValueError, match="without time component"):
        edinet.documents(datetime(2026, 2, 7, 12, 0, 0))


def test_documents_rejects_invalid_start_format() -> None:
    with pytest.raises(ValueError, match="start must be YYYY-MM-DD"):
        edinet.documents(start="2026/02/01", end="2026-02-07")


def test_documents_rejects_invalid_date_arguments() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        edinet.documents("2026-02-07", start="2026-02-01", end="2026-02-07")

    with pytest.raises(ValueError, match="Specify either date or both start/end"):
        edinet.documents()

    with pytest.raises(ValueError, match="Specify either date or both start/end"):
        edinet.documents(start="2026-02-01")

    with pytest.raises(ValueError, match="start must be <= end"):
        edinet.documents(start="2026-02-10", end="2026-02-01")


def test_documents_rejects_too_large_date_range() -> None:
    with pytest.raises(ValueError, match="Date range too large"):
        edinet.documents(start="2024-01-01", end="2026-02-07")
```

### 7.3.3 `tests/test_models/test_filing.py` 追加ケース

```python
def test_company_property_returns_company():
    filing = Filing.from_api_response(SAMPLE_DOC)
    company = filing.company
    assert company is not None
    assert company.edinet_code == "E02144"
    assert company.name_ja == "トヨタ自動車株式会社"
    assert company.sec_code == "72030"


def test_company_property_returns_none_when_edinet_code_missing():
    doc = {**SAMPLE_DOC, "edinetCode": None}
    filing = Filing.from_api_response(doc)
    assert filing.company is None


def test_fetch_raises_when_has_xbrl_false():
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response({**SAMPLE_DOC, "xbrlFlag": "0"})
    with pytest.raises(EdinetAPIError, match="Document has no XBRL"):
        filing.fetch()


def test_fetch_propagates_edinet_error_from_download(monkeypatch: pytest.MonkeyPatch):
    from edinet.exceptions import EdinetError

    filing = Filing.from_api_response(SAMPLE_DOC)

    def fake_download(doc_id: str, *, file_type):
        raise EdinetError("network timeout")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)

    with pytest.raises(EdinetError, match="network timeout"):
        filing.fetch()


def test_fetch_propagates_edinet_api_error_from_download(monkeypatch: pytest.MonkeyPatch):
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response(SAMPLE_DOC)

    def fake_download(doc_id: str, *, file_type):
        raise EdinetAPIError(503, "upstream unavailable")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)

    with pytest.raises(EdinetAPIError, match="EDINET API error 503"):
        filing.fetch()


def test_fetch_downloads_primary_xbrl(monkeypatch: pytest.MonkeyPatch):
    from edinet.api.download import DownloadFileType

    filing = Filing.from_api_response(SAMPLE_DOC)
    zip_bytes = b"PK\x03\x04dummy"
    expected = ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>")
    called = {"download": 0, "extract": 0}

    def fake_download(doc_id: str, *, file_type):
        called["download"] += 1
        assert doc_id == "S100TEST"
        assert file_type is DownloadFileType.XBRL_AND_AUDIT
        return zip_bytes

    def fake_extract(raw: bytes):
        called["extract"] += 1
        assert raw == zip_bytes
        return expected

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    assert filing.fetch() == expected
    assert called == {"download": 1, "extract": 1}


def test_clear_fetch_cache_forces_redownload(monkeypatch: pytest.MonkeyPatch):
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id: str, *, file_type):
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr(
        "edinet.api.download.extract_primary_xbrl",
        lambda raw: ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>"),
    )

    filing.fetch()
    filing.clear_fetch_cache()
    filing.fetch()
    assert called["download"] == 2


def test_fetch_uses_cache(monkeypatch: pytest.MonkeyPatch):
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0, "extract": 0}

    def fake_download(doc_id: str, *, file_type):
        called["download"] += 1
        return b"PK\x03\x04dummy"

    def fake_extract(raw: bytes):
        called["extract"] += 1
        return ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    first = filing.fetch()
    second = filing.fetch()
    assert first == second
    assert called == {"download": 1, "extract": 1}


def test_fetch_refresh_bypasses_cache(monkeypatch: pytest.MonkeyPatch):
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id: str, *, file_type):
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr(
        "edinet.api.download.extract_primary_xbrl",
        lambda raw: ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>"),
    )

    filing.fetch()
    filing.fetch(refresh=True)
    assert called["download"] == 2


def test_fetch_normalizes_zip_value_error_to_edinet_parse_error(monkeypatch: pytest.MonkeyPatch):
    from edinet.exceptions import EdinetParseError

    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id, *, file_type):
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr(
        "edinet.api.download.download_document",
        fake_download,
    )

    def fake_extract(_raw: bytes):
        raise ValueError("broken zip")

    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    with pytest.raises(EdinetParseError, match="Failed to parse EDINET ZIP") as exc_info:
        filing.fetch()
    assert isinstance(exc_info.value.__cause__, ValueError)

    # 失敗時に壊れた ZIP キャッシュを保持しないこと
    with pytest.raises(EdinetParseError, match="Failed to parse EDINET ZIP"):
        filing.fetch()
    assert called["download"] == 2


def test_fetch_normalizes_download_input_value_error_to_edinet_parse_error(
    monkeypatch: pytest.MonkeyPatch,
):
    from edinet.exceptions import EdinetParseError

    filing = Filing.from_api_response(SAMPLE_DOC)

    def fake_download(doc_id, *, file_type):
        raise ValueError("doc_id must be alphanumeric only")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)

    with pytest.raises(EdinetParseError, match="Failed to download XBRL ZIP for fetch") as exc_info:
        filing.fetch()
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "doc_id must be alphanumeric only" in str(exc_info.value)


def test_fetch_raises_when_primary_xbrl_not_found(monkeypatch: pytest.MonkeyPatch):
    from edinet.exceptions import EdinetParseError

    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id, *, file_type):
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr(
        "edinet.api.download.download_document",
        fake_download,
    )
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", lambda _raw: None)

    with pytest.raises(EdinetParseError, match="Primary XBRL not found"):
        filing.fetch()

    # 見つからないケースでもキャッシュを破棄し、次回は再DLされること
    with pytest.raises(EdinetParseError, match="Primary XBRL not found"):
        filing.fetch()
    assert called["download"] == 2
```

### 7.3.4 `tests/test_api/test_errors.py` 追加ケース

```python
def test_edinet_parse_error_is_edinet_error() -> None:
    from edinet.exceptions import EdinetError, EdinetParseError

    exc = EdinetParseError("broken zip")
    assert isinstance(exc, EdinetError)
    assert "broken zip" in str(exc)
```

### 7.3.5 `tests/test_api/test_api_exports.py`

```python
"""`edinet.api` の再エクスポート契約テスト。"""
from __future__ import annotations


def test_api_re_exports_low_level_symbols() -> None:
    from edinet.api import (
        DownloadFileType,
        download_document,
        extract_primary_xbrl,
        extract_zip_member,
        find_primary_xbrl_path,
        get_documents,
        list_zip_members,
    )

    assert callable(get_documents)
    assert callable(download_document)
    assert callable(list_zip_members)
    assert callable(find_primary_xbrl_path)
    assert callable(extract_zip_member)
    assert callable(extract_primary_xbrl)
    assert isinstance(DownloadFileType.XBRL_AND_AUDIT.value, int)
```

---

## 8. 実装順序（推奨）

### Step 0: 現状固定（5分）

```bash
git status --short
rg -n "class Filing|def fetch|company|__all__|def documents" src/edinet
```

### Step 1: `Company` + `Filing.company`（20分）

1. `src/edinet/_validators.py` 実装（`normalize_edinet_code`）
2. `src/edinet/models/company.py` 実装
3. `src/edinet/models/filing.py` に `company` 追加
4. `tests/test_models/test_company.py` / `tests/test_models/test_validators.py` 追加

### Step 2: `Filing.fetch()` + cache（25分）

1. `PrivateAttr` 追加
2. `exceptions.py` に `EdinetParseError` 追加
3. `fetch` / `clear_fetch_cache` 追加
4. `tests/test_models/test_filing.py` と `tests/test_api/test_errors.py` 追記

### Step 3: 公開 API（20分）

1. `src/edinet/__init__.py` 実装
2. `src/edinet/api/__init__.py` 実装
3. `src/edinet/models/__init__.py` に `Company` 追加
4. `tests/test_api/test_public_api.py` / `tests/test_api/test_api_exports.py` 追加

### Step 4: 静的解析 + テスト実行（15分）

```bash
uv run ruff check src tests
uv run pytest tests/test_models/test_company.py tests/test_models/test_validators.py tests/test_api/test_public_api.py tests/test_api/test_api_exports.py tests/test_models/test_filing.py tests/test_api/test_errors.py
uv run pytest
```

### Step 5: ドキュメント同期（10分）

```bash
# PLAN.md の Company 表記を機械的に同期（コード例・Mermaid 図を含む）
uv run python - <<'PY'
from pathlib import Path

path = Path("docs/PLAN.md")
text = path.read_text(encoding="utf-8")
text = text.replace('Company("7203")', 'Company(edinet_code="E02144")')
text = text.replace("Company(7203)", 'Company(edinet_code="E02144")')
path.write_text(text, encoding="utf-8")
PY

# 取りこぼし確認
rg -n -F 'Company("7203")' docs/PLAN.md
rg -n -F 'Company(7203)' docs/PLAN.md

# 置換差分を確認（意図しない説明文改変がないか）
git diff -- docs/PLAN.md
```

README 追記（未記載時のみ）:

```bash
rg -n -F "## Day6 Public API" README.md || cat <<'MD' >> README.md

## Day6 Public API

~~~python
from edinet import configure, documents

configure(api_key="YOUR_API_KEY")
filings = documents("2026-02-07", doc_type="120", edinet_code="E02144")
if filings and filings[0].has_xbrl:
    path, xbrl_bytes = filings[0].fetch()
~~~

- `edinet.documents()` は `type=2` 固定（提出書類一覧+メタデータ）
- `type=1` が必要な場合は `edinet.api.get_documents(..., include_details=False)` を使用
MD
```

---

## 9. 手動 E2E（任意だが推奨）

```bash
uv run python - <<'PY'
from datetime import datetime, timedelta, timezone
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from edinet import configure, documents

configure(api_key=os.environ["EDINET_API_KEY"])

# 直近7日から XBRL あり書類を1件探す
try:
    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()
except ZoneInfoNotFoundError:
    today_jst = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
for i in range(7):
    d = (today_jst - timedelta(days=i)).isoformat()
    filings = documents(d)
    candidates = [f for f in filings if f.has_xbrl and f.withdrawal_status == "0"]
    if candidates:
        f = candidates[0]
        path, xbrl = f.fetch()
        print("date=", d)
        print("doc_id=", f.doc_id)
        print("path=", path)
        print("bytes=", len(xbrl))
        break
else:
    print("NO_CANDIDATE_LAST_7_DAYS")
PY
```

---

## 10. リスクと対策

1. リスク: `frozen=True` とキャッシュが衝突する  
   対策: `PrivateAttr` のみを更新対象にし、公開フィールドは不変を維持

2. リスク: `documents()` に `include_details=False` 相当を許すと、0件を「該当なし」と誤認しやすい  
   対策: 公開 `documents()` は `type=2` 固定にし、`include_details` を受けない設計へ統一

3. リスク: `edinet.documents()` で `doc_type` typo がサイレント0件になる  
   対策: `doc_type` 文字列は `DocType` 変換を必須化し、未知コードは即 `ValueError`

4. リスク: 日付範囲誤指定で大量 API 呼び出しが発生する  
   対策: 取得日数に上限（`MAX_DOCUMENT_RANGE_DAYS = 366`）を設けて fail-fast

5. リスク: `Company.get_filings()` が全件パース後フィルタだと、非対象破損で全体失敗する  
   対策: `edinet_code` を raw `results` で先絞りしてから `Filing` 化する

6. リスク: Day5 の `ValueError` 契約が崩れる  
   対策: `Filing.fetch()` 境界でのみ `EdinetParseError` に正規化し、`raise ... from exc` を維持

7. リスク: ZIP 解析失敗後に壊れた `_zip_cache` が残り、復旧しづらい  
   対策: `extract_primary_xbrl` 失敗時は `clear_fetch_cache()` を呼んでから例外化する

8. リスク: package import 時に循環 import  
   対策: `Filing.fetch()` はローカル import、`_config.py` の相対 import 方針を維持

9. リスク: `PLAN.md` の複数箇所で `Company("7203")` / `Company(7203)` が残り、Day6 方針と不一致になる  
   対策: `rg -F` で両パターンを全件検出し（Mermaid 図も対象）、`Company(edinet_code="...")` に同期して取りこぼしゼロを確認する

10. リスク: `datetime` が `date` 判定をすり抜け、`YYYY-MM-DDTHH:MM:SS` を API へ送ってしまう  
   対策: `_coerce_date()` で `datetime` を明示拒否し、時刻なし入力のみ受け付ける

11. リスク: `edinet_code` の型不正で `AttributeError` が漏れ、例外契約が崩れる  
   対策: `normalize_edinet_code()`（共通ヘルパー）で型チェックを先に行い、`ValueError` に統一する

12. リスク: `download_document()` 由来 `ValueError` を固定文言に潰して診断しづらくなる  
   対策: `EdinetParseError` 文言へ元例外メッセージを含め、`raise ... from exc` で原因を追跡可能にする

13. リスク: `ZoneInfo("Asia/Tokyo")` が tzdb 未導入環境で失敗する  
   対策: `_today_jst()` に `ZoneInfoNotFoundError` フォールバック（UTC+9 固定）を実装し、`tzdata` 導入を推奨する

14. リスク: `download_document()` 由来 `EdinetError` / `EdinetAPIError` が将来ラップされ契約崩れする  
   対策: 透過契約の専用テスト（2ケース）を追加し、例外型を固定する

15. リスク: コピペ実装で lint 崩れ（未使用 import など）が混入する  
   対策: Day6 の品質ゲートに `uv run ruff check src tests` を追加する

16. リスク: API レスポンス形状異常を `ValueError` 扱いにすると、呼び出し側の例外分岐が不安定になる  
   対策: `_prepare_response_for_filing_parse()` / `_validate_resultset_count()` は `EdinetParseError` を返す

17. リスク: `edinet_code` 検証が Company 側と公開 API 側でドリフトする  
   対策: `src/edinet/_validators.py` の `normalize_edinet_code()` に一本化する

18. リスク: Step 5 が手作業寄りだと同期漏れ・README 反映漏れが起きる  
   対策: `uv run python` 置換コマンドと README 追記 heredoc を手順に明示して機械化する

19. リスク: 取り下げ済み書類の主要項目欠損（`None`）を必須扱いすると日次取得全体が失敗する  
   対策: 欠損許容フィールドは `None` のまま受け入れ、`test_documents_accepts_withdrawn_record_with_nullable_core_fields` で固定する

20. リスク: `Filing.from_api_list()` の `ValueError` が `documents()` から漏れ、例外契約と不一致になる  
   対策: `documents()` 境界で `ValueError` を `EdinetParseError` に正規化し、`raise ... from exc` で原因を保持する

21. リスク: Step 5 の全体置換で履歴説明文など意図しない箇所まで改変する  
   対策: 置換後に `git diff -- docs/PLAN.md` を必須確認し、意図しない差分は確定前に除外する

---

## 11. 完了条件（Day 6 の「動く状態」）

- [ ] `from edinet import configure, documents` が動作する
- [ ] `documents("YYYY-MM-DD")` が `list[Filing]` を返す
- [ ] `documents(start=..., end=..., doc_type=..., edinet_code=...)` が動作する
- [ ] 公開 `documents()` が `include_details` を受けない（`type=2` 固定）
- [ ] `documents(..., doc_type="12O")` のような typo で `ValueError` を返す
- [ ] `documents(start=..., end=...)` が 366 日超で `ValueError` を返す
- [ ] `documents(..., edinet_code="7203")` のような不正形式で `ValueError` を返す
- [ ] `documents(..., edinet_code=7203)` のような型不正で `ValueError` を返す（`AttributeError` にしない）
- [ ] `documents(..., edinet_code=" e02144 ")` のような入力が正規化されて動作する
- [ ] `documents(datetime(...))` のような時刻付き入力を `ValueError` で拒否する
- [ ] `doc_type` / `edinet_code` フィルタ指定時は `results` の非dict行を無視して対象行のみ返す
- [ ] 取り下げ済み書類（`withdrawalStatus=1`）で主要項目が `None` でも `documents()` が `Filing` 化できる
- [ ] `documents()` が API レスポンス形状異常（`results` 非list）で `EdinetParseError` を返す
- [ ] `documents()` が `metadata.resultset.count` と `results` の不一致で `EdinetParseError` を返す
- [ ] `documents()` が `metadata` 欠落 / `metadata.resultset` 欠落 / `resultset.count` 非数値で `EdinetParseError` を返す
- [ ] `documents()` が `Filing.from_api_list()` 由来 `ValueError` を `EdinetParseError` に正規化する
- [ ] `filing.company` が `Company | None` を返す
- [ ] `Company(edinet_code="7203")` がモデル生成時点で `ValueError` を返す
- [ ] `Company.get_filings()` は日付省略時 `date=today(JST)` で実行される
- [ ] `Company.get_filings()` の JST 日付取得が tzdb 未導入環境でもフォールバックで動作する
- [ ] `Company` / `documents()` の `edinet_code` 検証が `normalize_edinet_code()` に一本化されている
- [ ] `filing.fetch()` が `(path, bytes)` を返す
- [ ] `filing.has_xbrl=False` で `filing.fetch()` が `EdinetAPIError` を返す
- [ ] `download_document` が送出した `EdinetError` / `EdinetAPIError` が `filing.fetch()` から透過する（ラップされない）
- [ ] `filing.fetch()` 2回目で再DLしない（キャッシュが効く）
- [ ] `filing.fetch()` の ZIP解析失敗時にキャッシュが破棄され、次回は再DLされる
- [ ] ZIP解析 `ValueError` が `EdinetParseError` に正規化される
- [ ] `from edinet.api import get_documents, DownloadFileType, download_document, list_zip_members, find_primary_xbrl_path, extract_zip_member, extract_primary_xbrl` が成立する
- [ ] `docs/PLAN.md` の `Company("7203")` / `Company(7203)`（Mermaid 図を含む）が全件 `Company(edinet_code="...")` 形式へ同期される
- [ ] Step 5 実行後に `git diff -- docs/PLAN.md` で置換差分を確認し、意図しない置換がない
- [ ] `README.md` に `## Day6 Public API` が追記済み（既存記述がある場合は重複なし）
- [ ] `uv run ruff check src tests` が通る
- [ ] 追加テスト + 既存テストが通る

---

## 12. Day 7 への引き渡し

Day 6 完了時点で Day 7 が前提にできるもの:

1. 公開 API が `edinet.configure()` / `edinet.documents()` に統一済み
2. `Filing.fetch()` の遅延評価とキャッシュ契約が固定済み
3. Company 統合の最小導線（`filing.company`, `company.get_filings()`）が存在
4. `docs/PLAN.md` の `Company("7203")` / `Company(7203)`（Mermaid 図含む）が全件 `Company(edinet_code="...")` 形式に同期済み
5. Day7 は「回帰テスト拡充」と「week1 全体の品質確認」に集中できる

---

## 13. フィードバック反映ログ

| No | 指摘 | 対応 | 反映内容 | 理由 |
|---|---|---|---|---|
| 1 | P1: `doc_type` 文字列入力が無検証でサイレント失敗 | **採用** | `6.3` の `_normalize_doc_type()` を厳格化。`DocType` へ変換できない文字列（例: `"12O"`）は `ValueError`。`7.3.2` に `test_documents_rejects_invalid_doc_type_string` を追加 | 利用者の typo を即時検知し、0件サイレントを防ぐため |
| 2 | P1: `doc_type` フィルタが Filing 変換後で、非対象壊れデータで全体失敗 | **採用** | `6.3` に `_prepare_response_for_filing_parse()` を追加し、`doc_type` 指定時は raw `results` を `docTypeCode` で先絞りしてから `Filing.from_api_list()`。`7.3.2` に `test_documents_prefilters_raw_results_before_filing_parse` を追加 | 対象外データ破損の影響を局所化し、取得成功率を上げるため |
| 3 | P2: Day6スコープ機能のテスト不足（`Company.get_filings` / `has_xbrl=False`） | **採用** | `7.3.1` に `Company.get_filings` の絞り込み・引数透過テストを追加。`7.3.3` に `test_fetch_raises_when_has_xbrl_false` を追加 | Day6で追加した公開導線の回帰ポイントを先に固定するため |
| 4 | P2: 日付範囲ループが無制限で大量API呼び出しリスク | **採用** | `6.3` に `MAX_DOCUMENT_RANGE_DAYS = 366` と `_validate_date_span()` を追加。`7.3.2` に `test_documents_rejects_too_large_date_range` を追加 | 運用事故（誤指定による大量リクエスト）を fail-fast で防ぐため |
| 5 | P1: `include_details=False` を公開 `documents()` に残すと `list[Filing]` と不整合 | **採用** | 公開 `documents()` から `include_details` 引数を削除し、`type=2` 固定へ変更。`type=1` は低レベル `edinet.api.get_documents()` 利用を明記 | 0件と「該当なし」の誤認を避け、公開 API の型契約を単純化するため |
| 6 | P1: `Company.get_filings()` が全件パース後フィルタで壊れデータに弱い | **採用** | `documents(..., edinet_code=...)` を追加し、`_prepare_response_for_filing_parse()` で raw `edinetCode` 先絞りを実施。`Company.get_filings()` はその経路を利用 | `doc_type` 先絞りと同じ防御を company 絞り込みにも適用するため |
| 7 | P2: `Filing.fetch()` 失敗時に壊れた `_zip_cache` が残る | **採用** | `extract_primary_xbrl` の `ValueError` / `None` の両ケースで `clear_fetch_cache()` 後に例外化。再呼び出しで再DLされるテストを追加 | 利用者が `refresh=True` を知らなくても復旧可能にするため |
| 8 | P3: `PLAN.md` の `Company("7203")` 例と Day6 方針の不一致 | **採用** | 実装順序に `Step 5: ドキュメント同期` を追加し、`rg` で全件検出の上で同期する手順へ拡張 | 設計判断が正しくてもサンプル不整合が残ると利用者体験を損なうため |
| 9 | P1: Company の `edinet_code` 検証が `documents()` と不整合 | **採用** | `Company` に `field_validator` を追加して `E`+5桁を厳格検証（空白除去・大文字化）。`test_company_normalizes_edinet_code` / `test_company_rejects_invalid_edinet_code` を追加 | 失敗を遅延させず、モデル生成時に不正入力を止めるため |
| 10 | P1: `Company.get_filings()` の引数契約が曖昧 | **採用** | `date/start/end` 全省略時は `date=today(JST)` に寄せる契約へ統一。`test_get_filings_defaults_to_today` を追加 | 「見た目上呼べるのに即 ValueError」を避け、API 使用感を安定化するため |
| 11 | P1: ZIP解析失敗を `EdinetAPIError` に混在させると分類が曖昧 | **採用** | `EdinetParseError(EdinetError)` を追加し、`Filing.fetch()` の解析失敗/primary不在は `EdinetParseError` に正規化 | 呼び出し側が API エラーとローカル解析エラーを型で明確に分岐できるようにするため |
| 12 | P2: PLAN 同期対象が狭い（トップのみ） | **採用** | `Step 5` と完了条件を「`Company(\"7203\")` 全件同期」に更新し、取りこぼし確認コマンドを追加 | ドキュメント間の前提差分を残さないため |
| 13 | P2: 宣言したバリデーションに対する境界テスト不足 | **採用** | `test_documents_rejects_invalid_date_format` / `test_documents_rejects_invalid_date_type` / `test_documents_rejects_invalid_start_format` / `test_documents_normalizes_edinet_code_for_filter` を追加 | 仕様の強い部分ほど回帰しやすいため、境界を先に固定するため |
| 14 | P1: `today` の基準がローカル時刻で EDINET（JST）とズレる | **採用** | `Company.get_filings()` の省略時日付を `_today_jst()`（`ZoneInfo(\"Asia/Tokyo\")`）へ変更し、JST 固定にした | 米国環境でも日付ズレを防ぎ、EDINET の日付基準と一致させるため |
| 15 | P1: `Company(\"7203\")` 置換先が位置引数になる恐れ | **採用** | 同期手順と完了条件を `Company(edinet_code=\"...\")` 形式で明記し、置換時の誤変換を防止した | `BaseModel` の呼び出し契約に一致させるため |
| 16 | P2: `Filing.fetch()` の `download_document` 由来 `ValueError` 契約が曖昧 | **採用** | `download_document` 呼び出しの `ValueError` を `EdinetParseError` に正規化する分岐を追加して、契約と実装を一致させた | 例外契約を単純化し、呼び出し側の分岐ミスを防ぐため |
| 17 | P2: `Filing.fetch()` の重要契約テスト不足（`file_type`/`clear_fetch_cache`） | **採用** | `file_type` が `DownloadFileType.XBRL_AND_AUDIT` である検証と、`clear_fetch_cache()` 後の再DL専用テストを追加 | `fetch` の接続契約とキャッシュ挙動を明示的に固定するため |
| 18 | P1: `datetime` が `documents()` に通り、時刻付き日付を API へ送る恐れ | **採用** | `_coerce_date()` の先頭で `datetime` を明示拒否する分岐を追加し、`test_documents_rejects_datetime_value` を追加 | `date` のみ許容という契約を実装レベルで固定し、フォーマット事故を防ぐため |
| 19 | P1: `edinet_code` 非文字列入力で `AttributeError` が漏れる | **採用** | `normalize_edinet_code()` に型チェックを追加し、非文字列は `ValueError(\"edinet_code must be str or None\")`。`test_documents_rejects_non_string_edinet_code` を追加 | 公開 API の例外契約を `ValueError` に統一して、呼び出し側の扱いを単純化するため |
| 20 | P2: `Filing.fetch()` の `download_document` 由来 `ValueError` が誤分類されやすい | **採用** | 固定文言 `Invalid document id...` をやめ、`Failed to download XBRL ZIP for fetch ...: {exc}` に変更。`__cause__` と元メッセージをテストで検証 | 診断情報を維持しつつ `EdinetParseError` 契約を守るため |
| 21 | P3: Step 5 の `rg` パターンが不安定 | **採用** | 取りこぼし確認コマンドを `rg -n -F 'Company("7203")' docs/PLAN.md` に変更 | エスケープ依存をなくし、環境差なく確実にマッチさせるため |
| 22 | P1: JST 取得が `ZoneInfo("Asia/Tokyo")` 依存で環境により失敗する | **採用** | `_today_jst()` に `ZoneInfoNotFoundError` フォールバック（UTC+9 固定）を追加し、`tzdata` 推奨を明記。`test_today_jst_falls_back_when_tzdb_missing` を追加 | Windows / minimal container でも日付省略契約を壊さないため |
| 23 | P1: `Filing.fetch()` の透過例外契約（`EdinetError`/`EdinetAPIError`）の回帰テスト不足 | **採用** | `test_fetch_propagates_edinet_error_from_download` と `test_fetch_propagates_edinet_api_error_from_download` を追加し、ラップせず透過する契約を固定 | 例外ハンドリングの将来回帰を防ぎ、呼び出し側の分岐を安定化するため |
| 24 | P2: PLAN 同期検出が `Company("7203")` 固定で `Company(7203)` を取りこぼす | **採用** | Step 5 と完了条件を `Company("7203")` / `Company(7203)`（Mermaid 図を含む）へ拡張し、`rg -F` 2コマンドで確認する手順に更新 | 文書全体の前提不一致を残さず、完了判定の実効性を高めるため |
| 25 | P2: 品質ゲートが `pytest` のみで lint が未固定 | **採用** | Step 4 に `uv run ruff check src tests` を追加し、完了条件にも反映 | コピペ実装時の静的品質劣化（未使用 import/型崩れ）を早期検知するため |
| 26 | P1: `_prepare_response_for_filing_parse()` の外部データ異常が `ValueError` で契約ぶれする | **採用** | API レスポンス形状異常（`results` 型不正、`resultset.count` 不正/不一致）は `EdinetParseError` に統一。`test_documents_raises_parse_error_when_results_is_not_list` / `test_documents_raises_parse_error_when_results_contains_non_dict` を追加 | 入力不正と外部データ異常を分離し、呼び出し側の例外分岐を安定化するため |
| 27 | P1: `edinet_code` 検証ロジックが二重定義で将来ドリフトする | **採用** | `src/edinet/_validators.py` を追加し、`normalize_edinet_code()` を `Company` と `documents()` の両方で使用。`tests/test_models/test_validators.py` を追加 | 単一責務化により仕様変更時の修正漏れを防ぐため |
| 28 | P2: 日次集約で `metadata.resultset.count` と実件数の差分を検知できない | **採用** | `_validate_resultset_count()` を追加して日次レスポンス整合を検証。`test_documents_raises_parse_error_when_result_count_mismatch` を追加 | API 側仕様変更時のサイレント欠落を fail-fast で検知するため |
| 29 | P3: Step 5 が手作業寄りでコピペ完了度が低い | **採用** | `uv run python` 置換コマンドと README 追記 heredoc を具体化し、取りこぼし確認コマンドを明記 | 作業者依存を減らし、計画書だけで再現可能にするため |
| 30 | P1: `documents()` の例外契約と実装ドラフトが不一致（`Filing.from_api_list` の `ValueError` 漏れ） | **採用** | `6.3` の `documents()` で `Filing.from_api_list()` を `try/except ValueError` し、`EdinetParseError` に正規化（`raise ... from exc`）。`7.3.2` に `test_documents_normalizes_filing_parse_value_error_to_parse_error` を追加 | 公開契約（引数不正=`ValueError`、外部/解析異常=`EdinetParseError`）を崩さないため |
| 31 | P2: `metadata` / `resultset` / `count` 異常系テストが不足 | **採用** | `7.3.2` に `test_documents_raises_parse_error_when_metadata_is_missing` / `test_documents_raises_parse_error_when_resultset_is_missing` / `test_documents_raises_parse_error_when_result_count_is_not_int` を追加 | 形状異常ガードの未固定分を埋め、回帰耐性を上げるため |
| 32 | P2: `api/__init__.py` 再エクスポート契約の回帰テストがない | **採用** | `7.1` に `tests/test_api/test_api_exports.py` を追加し、`7.3.5` に具体テストを追加。`Step 3/4` の実装・実行手順も更新 | 公開導線の破壊を早期検知し、import 互換性を維持するため |
| 33 | P3: Step 5 の `PLAN.md` 一括置換が広すぎる | **採用** | Step 5 に `git diff -- docs/PLAN.md` を必須確認として追加し、完了条件にも反映 | 機械置換による意図しない説明文改変を検知して防ぐため |

補足:

- すべて「採用」にした。いずれも Day6 の品質・運用安全性に直結し、実装コストが低く効果が高い。
- 変更は公開 API の挙動を明確化する方向（厳格化）で統一した。曖昧に許容する設計は Day6 では採らない。

---

## 14. MEMO 反映ログ

| 出典 | メモ内容 | Day6への反映 | 理由 |
|---|---|---|---|
| `docs/MEMO.md` Day4 | `docTypeCode` の正しい情報源は EDINET API 仕様書（`ESE140206`）で、`ESE140327`（FormCode）ではない | `5.3` の `doc_type` バリデーション前提を明文化し、`DocType` 変換の厳格化方針に紐付けた | コード体系の取り違えによる誤フィルタ・誤実装を再発させないため |
| `docs/MEMO.md` Day4 | 取り下げ済み書類で主要項目が `None` になる実データがある | `5.3` に欠損許容方針を追記し、`7.3.2` に `test_documents_accepts_withdrawn_record_with_nullable_core_fields` を追加 | 実データ起因の回帰（必須化による日次取得失敗）を防ぐため |
| `docs/MEMO.md` Day5 | 低レベル例外の正規化時は `raise ... from exc` で原因追跡を維持する | `Filing.fetch()` の `EdinetParseError` 正規化で cause 維持を明記・テスト維持（`__cause__` 検証） | 例外契約の安定性とデバッグ容易性を両立するため |
| `docs/MEMO.md` Day4/Day5 | 例外クラスは `exceptions.py` に集約する | Day6 の `EdinetParseError` 追加先を `src/edinet/exceptions.py` に固定 | 公開例外の発見性と保守性を確保するため |

非反映（Day6スコープ外）:

- `DocType`/`FormCode` の生成方式詳細、タクソノミ略称変換の話題は Day6 スコープ外のため計画には取り込まない。

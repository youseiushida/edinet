# Day 4.5 — コード定義モデル（OrdinanceCode / FormCode / FundCode / EdinetCode）

## 0. 位置づけ

Day 4 で `DocType`（書類種別コード）と `Filing`（提出書類モデル）を完成させた。
Day 4.5 では MEMO.md で先送りにしていた **残りのコード定義モデル** を実装する。

PLAN.md §9 のスケジュールでは Day 5（ZIP 取得）の前に位置する挿入タスクだが、
Day 6（Company + 統合）で `Filing` と `EdinetCode` / `OrdinanceCode` / `FormCode` の
紐付けが必要になるため、**Day 5 より前に完了させる必要がある**。

また、Day 4 実装後に発覚した `Filing.from_api_response()` の不整合（Optional 化済みフィールドを
`data["key"]` で取得している問題）も本 Day で修正する。

---

## 1. ゴール

Day 4.5 終了時点で以下が完了していること：

0. `Filing.from_api_response()` の Optional フィールド不整合修正（Step 0）
1. `OrdinanceCode` — 府令コード Enum（手動定義）
2. `FormCode` — 様式コード Pydantic モデル（スクリプト自動生成）
3. `FundCode` — ファンドコード Pydantic モデル（スクリプト自動生成）
4. `EdinetCode` — EDINET コード Pydantic モデル（スクリプト自動生成）
5. 各モデルのテスト（Small テスト）
6. `Filing` から `OrdinanceCode` / `FormCode` への参照プロパティ追加

---

## 2. 事前調査結果のサマリー

### 2.1 ESE140327.xlsx（様式コードリスト）

- シート: `様式コードリスト` (416行, B-H列)
- ヘッダー (3行目): `府令コード | 様式コード（コード値） | 様式番号 | 様式名 | 書類種別 | 開示区分 | 備考`
- データ行: 4行目〜416行目 → **データ 413 行**
- 府令コード（B列）: `010, 015, 020, 030, 040, 050, 060` → **計 7 種**
- 様式コード（C列）: **326 種**（例: `010000`, `010001`, `01A000`, ...）
- 書類種別（F列）: **42 種**（DocType と一致）
- 開示区分（G列）: `開示`, `非開示` の **2 種**
- **重要**: 様式コードは*6桁文字列*（ゼロ埋め）。英字が含まれるケースあり（`01A000` 等）
- **🔴 重要（追加調査で判明）**: `form_code` は単独では一意でない。**55 件**の `form_code` が複数の `ordinance_code` に登場する（例: `010000` → `['010', '015', '020', '060']`）。ルックアップキーは `(ordinance_code, form_code)` にする必要がある

### 2.2 FundcodeDlInfo.csv（ファンドコードリスト）

- エンコーディング: **CP932**（chardet confidence=0.99）
- 改行: CRLF
- 区切り文字: カンマ
- 構造:
  - 0行目: メタ行 `ダウンロード実行日,2026年02月15日現在,件数,6377件` → **スキップ対象**
  - 1行目: ヘッダー `ファンドコード,証券コード,ファンド名,ファンド名（ヨミ）,特定有価証券区分名,特定期1,特定期2,ＥＤＩＮＥＴコード,発行者名`
  - 2行目〜: データ（全角引用符でクォート）→ **6,377 件**
- カラム: **9 列**（1行目のメタ行のみ4カラム）
- ファンドコード: `G01003` 〜 `G15821`（`G` + 5桁数字）

### 2.3 EdinetcodeDlInfo.csv（EDINET コードリスト）

- エンコーディング: **CP932**（chardet confidence=0.99）
- 改行: CRLF
- 区切り文字: カンマ
- 構造:
  - 0行目: メタ行 `ダウンロード実行日,2026年02月15日現在,件数,11223件` → **スキップ対象**
  - 1行目: ヘッダー `ＥＤＩＮＥＴコード,提出者種別,上場区分,連結の有無,資本金,決算日,提出者名,提出者名（英字）,提出者名（ヨミ）,所在地,提出者業種,証券コード,提出者法人番号`
  - 2行目〜: データ（全角引用符でクォート）→ **11,223 件**
- **注意**: カラム数が行によって 13/14/15 とブレる
  - 13 カラム: 8,446 行（基本形）
  - 14 カラム: 2,772 行（値中にカンマを含むケースか、未知の14列目が存在）
  - 15 カラム: 6 行（同上、さらにカンマ1つ多い）
  - → 原因: `提出者名（英字）` フィールド内に `, ` が含まれるレコードがある（例: `KANEKO SEEDS CO., LTD.`）。CSV は`""`でクォートされているため、**適切な CSV パーサーを使えば問題なし**。`str.split(",")` ではパースできない
- EDINET コード: `E00004` 〜 `E41469`（`E` + 5桁数字）
- **資本金の単位（追加調査で確定）**: **百万円単位**。トヨタ自動車（E02144）の CSV 値=635,401 と期待値=635,402 百万円が一致（比率=1.0000）。max=27,136,898（ウォルマート）、中央値=405。フィールド名に単位を含める（`capital_million_yen`）

---

## 3. 設計方針

### 3.1 MEMO.md の方針に従う

| コード | 定義方式 | 理由 |
|--------|----------|------|
| `OrdinanceCode` (府令コード) | **手動定義** (Enum) | 7種のみ。PDF 記載。変更頻度が極めて低い |
| `FormCode` (様式コード) | **スクリプト自動生成** | 326種。Excel 配布。改版あり |
| `FundCode` (ファンドコード) | **スクリプト自動生成** | 6,377件。CSV 配布。頻繁に更新 |
| `EdinetCode` (EDINETコード) | **スクリプト自動生成** | 11,223件。CSV 配布。頻繁に更新 |

### 3.2 自動生成ファイルの原則

1. 生成されたファイルの冒頭に `# AUTO-GENERATED — DO NOT EDIT` コメントを付与
2. 生成スクリプトは `tools/` に配置
3. 生成結果は `src/edinet/models/` に配置し、**Git 管理する**（ユーザーがスクリプトを実行しなくてもライブラリが使える状態を保つ）
4. ソースデータ（CSV/Excel）は `data/source/` に配置し、`.gitignore` で除外（配布ライセンス不明のため Git には含めない）

### 3.3 モデルの設計思想

- `FormCode` / `FundCode` / `EdinetCode` は件数が多いため **Enum にしない**
- 代わりに **Pydantic の `BaseModel (frozen=True)`** でレコードを定義し、全レコードを辞書で持つルックアップテーブルを提供する
- `OrdinanceCode` は 7 件のみなので `str, Enum` で定義する（`DocType` と同じパターン）
- ルックアップ失敗時は `None` を返し、`EdinetWarning` を出す（`DocType.from_code()` と一貫したパターン）

### 3.4 Lazy Import 方針

`edinet_code.py`（11,223件）と `fund_code.py`（6,377件）はファイルサイズが大きく、
インポート時に全件の Pydantic インスタンスを生成するコストがある。

- **`models/__init__.py` では `edinet_code` / `fund_code` をトップレベル import しない**
- 利用者が `from edinet.models.edinet_code import get_edinet_code` と明示的に import するまでロードしない
- `OrdinanceCode` と `FormCodeEntry` のみ `__init__.py` からエクスポートする（件数が少ない）
- v0.1.0 では辞書リテラル方式で進め、実際のインポート時間を計測するテストを追加する

---

## 4. ファイル構成

```
src/edinet/
  models/
    __init__.py               # ← OrdinanceCode を追加エクスポート
    doc_types.py              # 既存（変更なし）
    filing.py                 # ← computed_field 追加
    ordinance_code.py         # ★ 新規: 府令コード Enum（手動定義）
    form_code.py              # ★ 新規: 様式コードモデル（自動生成）
    fund_code.py              # ★ 新規: ファンドコードモデル（自動生成）
    edinet_code.py            # ★ 新規: EDINETコードモデル（自動生成）
    company.py                # 空ファイル（Day 6 で実装）
    financial.py              # 空ファイル（Day 10 で実装）

tools/
    generate_form_codes.py    # ★ 新規: ESE140327.xlsx → form_code.py
    generate_fund_codes.py    # ★ 新規: FundcodeDlInfo.csv → fund_code.py
    generate_edinet_codes.py  # ★ 新規: EdinetcodeDlInfo.csv → edinet_code.py
    temp.py                   # 調査用（Day 4.5 完了後は不要）

tests/
    test_models/
      test_doc_types.py       # 既存（変更なし）
      test_filing.py          # 既存（computed_field 追加分のテスト追加）
      test_ordinance_code.py  # ★ 新規
      test_form_code.py       # ★ 新規
      test_fund_code.py       # ★ 新規
      test_edinet_code.py     # ★ 新規
```

---

## 5. 実装詳細

### 5.1 `OrdinanceCode` — 府令コード Enum（手動定義）

**ファイル**: `src/edinet/models/ordinance_code.py`

```python
"""府令コード (ordinanceCode) の Enum 定義。

情報源: EDINET API 仕様書 Version 2 (ESE140206.pdf) + 様式コードリスト (ESE140327.xlsx)
"""
from __future__ import annotations

import warnings
from enum import Enum

from edinet.exceptions import EdinetWarning


class OrdinanceCode(str, Enum):
    """EDINET 府令コード。

    str を継承しているため、文字列として比較可能:
        OrdinanceCode.DISCLOSURE == "010"  # True
    """

    DISCLOSURE = "010"             # 企業内容等の開示に関する内閣府令
    INTERNAL_CONTROL = "015"     # 財務計算に関する書類その他の情報の適正性を確保するための体制に関する内閣府令
    FOREIGN_ISSUERS = "020"           # 外国債等の発行者の開示に関する内閣府令
    SPECIFIED_SECURITIES = "030"    # 特定有価証券の内容等の開示に関する内閣府令
    TENDER_OFFER = "040"     # 発行者以外の者による株券等の公開買付けの開示に関する内閣府令
    ISSUER_TENDER_OFFER = "050"   # 発行者による上場株券等の公開買付けの開示に関する内閣府令
    LARGE_SHAREHOLDING = "060"  # 株券等の大量保有の状況の開示に関する内閣府令

    # --- プロパティ ---

    @property
    def name_ja(self) -> str:
        """日本語名称。"""
        return _ORDINANCE_CODE_NAMES_JA[self.value]

    # --- ファクトリ ---

    @classmethod
    def from_code(cls, code: str) -> OrdinanceCode | None:
        """コード文字列から OrdinanceCode を返す。未知のコードは None + warning。"""
        try:
            return cls(code)
        except ValueError:
            if code not in _warned_unknown_ordinance_codes:
                _warned_unknown_ordinance_codes.add(code)
                warnings.warn(
                    f"Unknown ordinanceCode: '{code}'.",
                    category=EdinetWarning,
                    stacklevel=2,
                )
            return None


_warned_unknown_ordinance_codes: set[str] = set()

def _reset_warning_state() -> None:
    """テスト用: warning 抑制状態をリセットする。"""
    _warned_unknown_ordinance_codes.clear()


_ORDINANCE_CODE_NAMES_JA: dict[str, str] = {
    "010": "企業内容等の開示に関する内閣府令",
    "015": "財務計算に関する書類その他の情報の適正性を確保するための体制に関する内閣府令",
    "020": "外国債等の発行者の開示に関する内閣府令",
    "030": "特定有価証券の内容等の開示に関する内閣府令",
    "040": "発行者以外の者による株券等の公開買付けの開示に関する内閣府令",
    "050": "発行者による上場株券等の公開買付けの開示に関する内閣府令",
    "060": "株券等の大量保有の状況の開示に関する内閣府令",
}

OFFICIAL_CODES: tuple[str, ...] = tuple(sorted(_ORDINANCE_CODE_NAMES_JA.keys()))
```

**設計判断**:
- `DocType` と完全に同じパターン（`str, Enum` + `from_code()` + `name_ja` + `_warned_unknown_codes`）
- ESE140327.xlsx の B 列で確認した 7 種のみ定義
- `060` の日本語名は API 仕様書に明記なし。ESE140327.xlsx での用途（大量保有関連の基準日届出）から推定
- ⚠️ Enum メンバー名 `050` は `SPECIFIED_SECURITIES` とする（`PARENT_COMPANY` は `DocType.PARENT_COMPANY_STATUS_REPORT`（コード `200`）と紛らわしいため回避）

### 5.2 `FormCode` — 様式コードモデル（自動生成）

**生成元**: `data/source/ESE140327.xlsx` → シート「様式コードリスト」3行目ヘッダー、4行目以降データ

**生成先**: `src/edinet/models/form_code.py`

**モデル設計**:

```python
"""様式コード (formCode) のモデル定義。

AUTO-GENERATED by tools/generate_form_codes.py — DO NOT EDIT MANUALLY.
Source: data/source/ESE140327.xlsx
"""
from __future__ import annotations

import warnings
from pydantic import BaseModel, ConfigDict

from edinet.exceptions import EdinetWarning


class FormCodeEntry(BaseModel):
    """様式コードリストの1行。"""

    model_config = ConfigDict(frozen=True)

    ordinance_code: str        # 府令コード (例: "010")
    form_code: str             # 様式コード (例: "010000")
    form_number: str           # 様式番号 (例: "第一号様式")
    form_name: str             # 様式名 (例: "有価証券通知書")
    doc_type_name: str         # 書類種別 (例: "有価証券通知書")
    disclosure_type: str       # 開示区分 ("開示" or "非開示")
    note: str | None = None    # 備考

    def __str__(self) -> str:
        return f"FormCodeEntry({self.ordinance_code}/{self.form_code} | {self.form_name})"


# --- ルックアップテーブル ---
# 🔴 キー: (ordinance_code, form_code) のタプル
# form_code 単独では一意でない（55件が複数府令コードに登場するため）
_FORM_CODE_TABLE: dict[tuple[str, str], FormCodeEntry] = {
    # ここに自動生成スクリプトが全 413 行の辞書リテラルを書き込む
    ("010", "010000"): FormCodeEntry(
        ordinance_code="010",
        form_code="010000",
        form_number="第一号様式",
        form_name="有価証券通知書",
        doc_type_name="有価証券通知書",
        disclosure_type="非開示",
    ),
    # ... (以下、全 413 行)
}

_warned_unknown_form_codes: set[tuple[str, str]] = set()


def get_form_code(ordinance_code: str, form_code: str) -> FormCodeEntry | None:
    """府令コードと様式コードのペアから FormCodeEntry を返す。

    form_code は単独では一意でないため、ordinance_code とセットで検索する。
    未知のコードは None + warning。
    """
    key = (ordinance_code, form_code)
    entry = _FORM_CODE_TABLE.get(key)
    if entry is None and key not in _warned_unknown_form_codes:
        _warned_unknown_form_codes.add(key)
        warnings.warn(
            f"Unknown formCode: ordinance='{ordinance_code}', form='{form_code}'. "
            f"Update form_code.py with generate_form_codes.py.",
            category=EdinetWarning,
            stacklevel=2,
        )
    return entry


def all_form_codes() -> list[FormCodeEntry]:
    """全様式コードの一覧を返す。"""
    return list(_FORM_CODE_TABLE.values())


def _reset_warning_state() -> None:
    """テスト用。"""
    _warned_unknown_form_codes.clear()
```

**生成スクリプト** (`tools/generate_form_codes.py`) のロジック:

1. `openpyxl` で `ESE140327.xlsx` を開く
2. **ヘッダー行（3行目）をバリデーション** — 想定カラム名と一致しなければ即エラー
3. シート `様式コードリスト` の 4 行目〜 `max_row` を走査
4. B 列 (府令コード), C 列 (様式コード), D 列 (様式番号), E 列 (様式名), F 列 (書類種別), G 列 (開示区分), H 列 (備考) を取得
5. **`(ordinance_code, form_code)` の重複チェック** — 重複があれば即エラー
6. `FormCodeEntry` のコンストラクタ呼び出しを辞書リテラルとして文字列生成（キーはタプル）
7. テンプレート（docstring + import + クラス定義 + 辞書 + 関数）に埋め込んで出力
8. `black` or `ruff format` で整形（オプション）

### 5.3 `FundCode` — ファンドコードモデル（自動生成）

**生成元**: `data/source/FundcodeDlInfo.csv`（CP932, カンマ区切り, 0行目メタ行スキップ）

**生成先**: `src/edinet/models/fund_code.py`

**モデル設計**:

```python
"""ファンドコード (fundCode) のモデル定義。

AUTO-GENERATED by tools/generate_fund_codes.py — DO NOT EDIT MANUALLY.
Source: data/source/FundcodeDlInfo.csv
"""
from __future__ import annotations

import warnings
from pydantic import BaseModel, ConfigDict

from edinet.exceptions import EdinetWarning


class FundCodeEntry(BaseModel):
    """ファンドコードリストの1行。"""

    model_config = ConfigDict(frozen=True)

    fund_code: str             # ファンドコード (例: "G01003")
    sec_code: str | None       # 証券コード (空文字あり→None変換)
    fund_name: str             # ファンド名
    fund_name_yomi: str        # ファンド名（ヨミ）
    security_type: str         # 特定有価証券区分名
    period_1: str | None       # 特定期1 (例: "1月13日")
    period_2: str | None       # 特定期2 (空なら None)
    edinet_code: str           # EDINETコード (例: "E12422")
    issuer_name: str           # 発行者名

    def __str__(self) -> str:
        return f"FundCodeEntry({self.fund_code} | {self.fund_name})"


# --- ルックアップテーブル ---
_FUND_CODE_TABLE: dict[str, FundCodeEntry] = {
    # ここに自動生成スクリプトが全 6,377 件を書き込む
}

_warned_unknown_fund_codes: set[str] = set()

def get_fund_code(code: str) -> FundCodeEntry | None:
    """ファンドコードから FundCodeEntry を返す。未知は None + warning。"""
    entry = _FUND_CODE_TABLE.get(code)
    if entry is None and code not in _warned_unknown_fund_codes:
        _warned_unknown_fund_codes.add(code)
        warnings.warn(
            f"Unknown fundCode: '{code}'. Update fund_code.py with generate_fund_codes.py.",
            category=EdinetWarning,
            stacklevel=2,
        )
    return entry

def all_fund_codes() -> list[FundCodeEntry]:
    """全ファンドコードの一覧を返す。"""
    return list(_FUND_CODE_TABLE.values())

def _reset_warning_state() -> None:
    """テスト用。"""
    _warned_unknown_fund_codes.clear()
```

**生成スクリプト** (`tools/generate_fund_codes.py`) のロジック:

1. `csv.reader` で `FundcodeDlInfo.csv` を開く（encoding=`cp932`）
2. **0行目をスキップ**（メタ行: ダウンロード実行日…）
3. 1行目をヘッダーとして読み、**カラム名→インデックスのマッピングを構築**（`idx = {name: i for i, name in enumerate(header)}`）。想定カラム名と一致しなければ即エラー
4. 2行目以降をカラム名ベースでデータ取得（固定インデックスではなく `row[idx["ファンドコード"]]` 方式）
5. 全角文字列をそのまま保持（正規化はしない。EDINETが全角で返すため）
6. 空文字 `""` は `None` に変換（`sec_code`, `period_1`, `period_2`）
7. 辞書リテラルとしてファイルに書き出す

**注意**: 6,377 件の辞書リテラルを `.py` に書くとファイルサイズが大きくなる（推定 1-2MB）。
これは許容する（Python の辞書はインポート時に一度だけ構築される。メモリ使用量は約 5-10MB で問題ない）。

### 5.4 `EdinetCode` — EDINET コードモデル（自動生成）

**生成元**: `data/source/EdinetcodeDlInfo.csv`（CP932, カンマ区切り, 0行目メタ行スキップ）

**生成先**: `src/edinet/models/edinet_code.py`

**モデル設計**:

```python
"""EDINETコード (edinetCode) のモデル定義。

AUTO-GENERATED by tools/generate_edinet_codes.py — DO NOT EDIT MANUALLY.
Source: data/source/EdinetcodeDlInfo.csv
"""
from __future__ import annotations

import warnings
from pydantic import BaseModel, ConfigDict

from edinet.exceptions import EdinetWarning


class EdinetCodeEntry(BaseModel):
    """EDINETコードリストの1行。"""

    model_config = ConfigDict(frozen=True)

    edinet_code: str           # EDINETコード (例: "E00004")
    submitter_type: str        # 提出者種別 (例: "内国法人・組合")
    listing_status: str | None # 上場区分 ("上場" or "" → None)
    consolidated: str | None   # 連結の有無 ("有" / "無" / "" → None)
    capital_million_yen: int | None  # 資本金（百万円単位）(空なら None。調査により確定済み)
    fiscal_year_end: str | None  # 決算日 (例: "5月31日"、空なら None)
    submitter_name: str        # 提出者名
    submitter_name_en: str | None  # 提出者名（英字）
    submitter_name_yomi: str | None  # 提出者名（ヨミ）
    address: str | None        # 所在地
    industry: str | None       # 提出者業種
    sec_code: str | None       # 証券コード
    corporate_number: str | None  # 提出者法人番号

    def __str__(self) -> str:
        return f"EdinetCodeEntry({self.edinet_code} | {self.submitter_name} | {self.sec_code})"


# --- ルックアップテーブル ---
_EDINET_CODE_TABLE: dict[str, EdinetCodeEntry] = {
    # ここに自動生成スクリプトが全 11,223 件を書き込む
}

_warned_unknown_edinet_codes: set[str] = set()

def get_edinet_code(code: str) -> EdinetCodeEntry | None:
    """EDINETコードから EdinetCodeEntry を返す。未知は None + warning。"""
    entry = _EDINET_CODE_TABLE.get(code)
    if entry is None and code not in _warned_unknown_edinet_codes:
        _warned_unknown_edinet_codes.add(code)
        warnings.warn(
            f"Unknown edinetCode: '{code}'. Update edinet_code.py with generate_edinet_codes.py.",
            category=EdinetWarning,
            stacklevel=2,
        )
    return entry

def all_edinet_codes() -> list[EdinetCodeEntry]:
    """全EDINETコードの一覧を返す。"""
    return list(_EDINET_CODE_TABLE.values())

def _reset_warning_state() -> None:
    """テスト用。"""
    _warned_unknown_edinet_codes.clear()
```

**CSV パースの注意点**:

- `csv.reader` を使う（`str.split(",")` **厳禁**。英字名にカンマが含まれるため）
- `capital_million_yen` フィールド: 文字列 → `int` 変換。空文字は `None`。**百万円単位**（調査で確定: トヨタ E02144 の CSV 値=635,401 vs 実際の資本金≈635,402百万円、比率=1.0000）
- 空文字 `""` はすべて `None` に変換
- 全角文字列はそのまま保持

**生成スクリプト** (`tools/generate_edinet_codes.py`) のロジック:

1. `csv.reader` で開く（encoding=`cp932`）
2. 0行目をスキップ（メタ行）
3. 1行目をヘッダーとして読み、**カラム名→インデックスのマッピングを構築**（`idx = {name: i for i, name in enumerate(header)}`）。想定カラム名（`ＥＤＩＮＥＴコード`, `提出者種別`, ...）と一致しなければ即エラー
4. 2行目以降をカラム名ベースでデータ取得（`row[idx["ＥＤＩＮＥＴコード"]]` 方式。将来のカラム追加に対応可能）
5. **edinet_code の重複チェック** — 重複があれば即エラー
6. 辞書リテラルとして書き出す

### 5.5 `Filing.from_api_response()` の修正（Step 0）

**ファイル**: `src/edinet/models/filing.py`

MEMO.md で `docTypeCode`, `ordinanceCode`, `formCode`, `filerName`, `docDescription` を
`Optional[str]` に変更済みだが、`from_api_response()` ではまだ `data["key"]`（KeyError パターン）で
取得している。キーが存在しないケースでクラッシュするため、`data.get()` に統一する。

```python
# Before (現状 — KeyError で落ちる可能性)
doc_type_code=data["docTypeCode"],
ordinance_code=data["ordinanceCode"],
form_code=data["formCode"],
filer_name=data["filerName"],
doc_description=data["docDescription"],

# After (修正後 — None で安全に保持)
doc_type_code=data.get("docTypeCode"),
ordinance_code=data.get("ordinanceCode"),
form_code=data.get("formCode"),
filer_name=data.get("filerName"),
doc_description=data.get("docDescription"),
```

同時に、docstring の `Raises` セクションからこれらのフィールドを除外し、
`docID`, `seqNumber`, `submitDateTime` のみを必須（KeyError）として記載する。

既存テストコード（`test_from_api_response_missing_doc_type_code` 等）は KeyError を
期待しているため、これらを修正（None がセットされることを検証）または削除する必要がある。

### 5.6 `Filing` の `__str__` 改善

`filer_name` が `None` の場合（取り下げ書類など）、現在の `__str__` 実装では `Filing(ID | None | ...)` となり見づらい。
`self.filer_name or "(不明)"` のように `None` セーフな表示に改善する。

### 5.7 `Filing` への `@property` 追加

既存の `Filing` に以下の **`@property`**（`computed_field` ではない）を追加する：

```python
@property
def ordinance(self) -> OrdinanceCode | None:
    """府令コード Enum。ordinance_code が None なら None。"""
    if self.ordinance_code is None:
        return None
    return OrdinanceCode.from_code(self.ordinance_code)

@property
def form(self) -> FormCodeEntry | None:
    """様式コード情報。ordinance_code / form_code が None なら None。"""
    if self.ordinance_code is None or self.form_code is None:
        return None
    from edinet.models.form_code import get_form_code
    return get_form_code(self.ordinance_code, self.form_code)
```

**設計判断**:
- ⚠️ `computed_field` ではなく **`@property`** にする理由:
  - `computed_field` だと `model_dump()` に `FormCodeEntry` の全フィールドがネストされた dict として含まれ、出力が予想外に大きくなる
  - 既存の `doc_type` は軽量（文字列ベースの Enum）だが、`FormCodeEntry` は 7 フィールドを持つ重いオブジェクト
  - `@property` なら `model_dump()` に影響せず、利用者が明示的にアクセスした時だけ評価される
- `FormCodeEntry` の import は関数内で行う（循環 import 防止）
- `form` プロパティは `ordinance_code` と `form_code` の**両方**が必要（form_code 単独では一意でないため）
- `FundCode` / `EdinetCode` は `Filing` フィールドに直接対応するコードがないため、プロパティは追加しない。Day 6 で `Company` モデル経由でのアクセスを設計する

---

## 6. テスト計画

### 6.1 `test_ordinance_code.py`

| テスト | 内容 |
|--------|------|
| `test_all_7_ordinance_codes_defined` | OFFICIAL_CODES が 7 つであること |
| `test_from_code_known` | `010` → `OrdinanceCode.DISCLOSURE` |
| `test_from_code_unknown_returns_none` | `"999"` → `None` |
| `test_from_code_unknown_warns` | `"999"` → `EdinetWarning` |
| `test_from_code_unknown_warns_once` | 同じコードで2回呼んでも warning 1回 |
| `test_name_ja` | 各コードの日本語名称が非空文字列 |
| `test_string_comparison` | `OrdinanceCode.DISCLOSURE == "010"` → `True` |

### 6.2 `test_form_code.py`

| テスト | 内容 |
|--------|------|
| `test_form_code_count` | `all_form_codes()` の件数が **413 件**であること（厳密一致） |
| `test_get_form_code_known` | `("010", "010000")` → `FormCodeEntry(form_name="有価証券通知書")` |
| `test_get_form_code_unknown` | `("010", "999999")` → `None` + `EdinetWarning` |
| `test_form_code_entry_frozen` | `entry.form_name = "x"` → `ValidationError` |
| `test_form_code_ordinance_code_consistency` | 全 entry の `ordinance_code` が `OrdinanceCode` の OFFICIAL_CODES に含まれる |
| `test_disclosure_type_values` | 全 entry の `disclosure_type` が `"開示"` or `"非開示"` |
| `test_form_code_unique_keys` | `_FORM_CODE_TABLE` のキー（タプル）に重複がないことの検証 |

### 6.3 `test_fund_code.py`

| テスト | 内容 |
|--------|------|
| `test_fund_code_count` | `all_fund_codes()` の件数が **6,377 件**であること（厳密一致） |
| `test_get_fund_code_known` | `"G01003"` → 正しいエントリ |
| `test_get_fund_code_unknown` | `"G99999"` → `None` + warning |
| `test_fund_code_entry_has_edinet_code` | 全 entry の `edinet_code` が `E` + 5桁 |
| `test_fund_code_no_duplicate` | `fund_code` の重複がないことの検証 |

### 6.4 `test_edinet_code.py`

| テスト | 内容 |
|--------|------|
| `test_edinet_code_count` | `all_edinet_codes()` の件数が **11,223 件**であること（厳密一致） |
| `test_get_edinet_code_known` | `"E00004"` → `submitter_name="カネコ種苗株式会社"` |
| `test_get_edinet_code_unknown` | `"E99999"` → `None` + warning |
| `test_listed_company_has_sec_code` | `listing_status="上場"` の `sec_code` 欠損率がしきい値以内（**`@pytest.mark.data_audit`** で分離実行） |
| `test_edinet_code_no_duplicate` | 同一 `edinet_code` の重複がないことの検証 |
| `test_import_time_acceptable` | Lazy import 含め、モジュールインポートが 2 秒以内に完了する（**`@pytest.mark.slow`** で分離実行） |

### 6.5 `test_filing.py` への追加

| テスト | 内容 |
|--------|------|
| `test_filing_from_api_response_optional_fields_none` | Optional 5フィールドがキー欠落時に None で保持される（Step 0 の検証） |
| `test_filing_ordinance_property` | `ordinance_code="010"` → `filing.ordinance == OrdinanceCode.DISCLOSURE` |
| `test_filing_ordinance_none_when_code_none` | `ordinance_code=None` → `filing.ordinance is None` |
| `test_filing_form_property` | `ordinance_code="010"`, `form_code="010000"` → `filing.form.form_name == "有価証券通知書"` |
| `test_filing_form_none_when_code_none` | `form_code=None` → `filing.form is None` |
| `test_filing_ordinance_not_in_model_dump` | `filing.model_dump()` に `ordinance` キーが含まれない（`@property` であり `computed_field` ではないことの検証） |
| `test_filing_form_not_in_model_dump` | `filing.model_dump()` に `form` キーが含まれない |

### 6.6 `test_generate_scripts.py`

生成スクリプトの冪等性テスト。生成結果を Git 管理するため、CI で「スクリプト再実行で diff が出ない」ことを検証する必要がある。

**更新方針（第4回フィードバック反映）**:
- `data/source/` が存在する場合は実データでも確認する
- それとは別に、**テスト内で合成入力（temp CSV/XLSX）を生成して常時実行可能な冪等性テストを持つ**
- これにより、ソースデータ不在の CI でもスクリプト退行を検知できる

| テスト | 内容 |
|--------|------|
| `test_generate_form_codes_idempotent` | 合成 XLSX 入力で `generate_form_codes.py` を2回実行しても出力が同一 |
| `test_generate_fund_codes_idempotent` | 合成 CSV 入力で `generate_fund_codes.py` を2回実行しても出力が同一 |
| `test_generate_edinet_codes_idempotent` | 合成 CSV 入力で `generate_edinet_codes.py` を2回実行しても出力が同一 |

---

## 7. 実装順序

### Step 0: Filing.from_api_response() の修正（15分 → 25分）

1. `filing.py` の `from_api_response()` で `data["docTypeCode"]` 等 5 フィールドを `data.get()` に変更
2. `docstring` の `Raises` セクションを更新
3. `Filing.__str__` を `None` セーフに修正
4. `test_filing.py` の修正:
   - `test_filing_from_api_response_optional_fields_none` を追加
   - **既存の KeyError 期待テスト（`test_from_api_response_missing_*`）を修正**

### 準備: 開発環境セットアップ

1. **ソースディレクトリ作成**
   ```powershell
   New-Item -ItemType Directory -Force data/source | Out-Null
   New-Item -ItemType File -Force data/source/.gitkeep | Out-Null
   ```
   （`.gitignore` に `data/source/*` と `!data/source/.gitkeep` があることを確認）

2. **依存関係の追加 (`pyproject.toml`)**
   生成スクリプトで Excel ファイルを読み込むため、`openpyxl` を開発依存に追加する。

   ```powershell
   # uv を使用している場合
   uv add --dev openpyxl

   # または pip install
   pip install openpyxl
   ```

   `pyproject.toml` の `[dependency-groups.dev]` (または `[project.optional-dependencies]`) に `openpyxl` が追加されたことを確認。


### Step 1: OrdinanceCode 実装 + テスト（30分）

1. `src/edinet/models/ordinance_code.py` を作成（上記 §5.1 の通り）
2. `tests/test_models/test_ordinance_code.py` を作成・実行
3. `src/edinet/models/__init__.py` に `OrdinanceCode` を追加エクスポート

### Step 2: 生成スクリプト作成（60〜75分）

以下の3つのスクリプトを作成し、続く Step 3 で実行する。

1. `tools/generate_form_codes.py` — ESE140327.xlsx → `form_code.py`
   - ★ `(ordinance_code, form_code)` の重複チェックを含める
   - ★ ヘッダー行（3行目）のバリデーションを含める
2. `tools/generate_fund_codes.py` — FundcodeDlInfo.csv → `fund_code.py`
   - ★ ヘッダー行のカラム名→インデックスマッピングを構築
3. `tools/generate_edinet_codes.py` — EdinetcodeDlInfo.csv → `edinet_code.py`
   - ★ `edinet_code` の重複チェックを含める
   - ★ ヘッダー行のカラム名→インデックスマッピングを構築
   - ★ 全角クォート処理・空文字→None変換のエッジケースに注意

各スクリプトの共通仕様:
- `if __name__ == "__main__":` で実行
- 出力先は `src/edinet/models/{対象}.py`
- 相対パスではなく `Path(__file__)` ベースで解決
- 生成前にバリデーション（ヘッダーカラム名チェック、空行スキップ、キー重複チェック）
- **生成ヘッダーに日時を含めない**（冪等性確保のため。ソースファイル名のみ記載）
- 生成後に件数をコンソール出力

### Step 3: コード生成実行

```powershell
python tools/generate_form_codes.py
python tools/generate_fund_codes.py
python tools/generate_edinet_codes.py
```

### Step 4: 生成ファイルのテスト作成（45〜60分）

1. `tests/test_models/test_form_code.py`
2. `tests/test_models/test_fund_code.py`
3. `tests/test_models/test_edinet_code.py`
   - ★ 機能テストのみを含める（性能テストは `test_import_perf.py` に分離）
4. `tests/test_models/test_generate_scripts.py`
   - ★ 各生成スクリプトの冪等性テスト（必須）
5. `tests/test_models/test_import_perf.py`
   - ★ `@pytest.mark.slow` のインポート時間テスト
6. `tests/test_models/test_edinet_code_quality.py`
   - ★ `@pytest.mark.data_audit` のデータ品質監査テスト

### Step 5: Filing 拡張 + テスト（15分）

1. `filing.py` に `ordinance` / `form` **`@property`** を追加（`computed_field` ではない）
   - ★ `form` は `ordinance_code` と `form_code` の両方を渡す
   - ★ `model_dump()` に含まれないことをテストで検証
2. `test_filing.py` に対応テストを追加
3. `models/__init__.py` のエクスポートを更新
   - ★ `edinet_code` / `fund_code` は **トップレベル import しない**（Lazy import）

### Step 6: 全テスト実行 + 確認

```powershell
pytest tests/ -m "not slow and not data_audit" -v
pytest tests/ -m slow -v
pytest tests/ -m data_audit -v
```

---

## 8. 成果物チェックリスト

- [ ] `src/edinet/models/filing.py` — `from_api_response()` の Optional フィールド修正 (Step 0)
- [ ] `src/edinet/exceptions.py` — `EdinetWarning` / `EdinetError` 集約済みであることを確認
- [ ] `src/edinet/models/ordinance_code.py` — 7 件の府令コード Enum
- [ ] `tools/generate_form_codes.py` — 様式コード生成スクリプト（キー重複チェック付き）
- [ ] `tools/generate_fund_codes.py` — ファンドコード生成スクリプト
- [ ] `tools/generate_edinet_codes.py` — EDINET コード生成スクリプト（重複チェック付き）
- [ ] `src/edinet/models/form_code.py` — 413 行の様式コード（自動生成、キー=`(ordinance_code, form_code)`）
- [ ] `src/edinet/models/fund_code.py` — 6,377 件のファンドコード（自動生成）
- [ ] `src/edinet/models/edinet_code.py` — 11,223 件の EDINET コード（自動生成）
- [ ] `src/edinet/models/filing.py` — `ordinance` / `form` `@property` 追加
- [ ] `src/edinet/models/__init__.py` — エクスポート更新（edinet_code/fund_code は Lazy）
- [ ] `tests/test_models/test_ordinance_code.py`
- [ ] `tests/test_models/test_form_code.py`（一意性テスト含む）
- [ ] `tests/test_models/test_fund_code.py`（重複テスト含む）
- [ ] `tests/test_models/test_edinet_code.py`（機能テスト）
- [ ] `tests/test_models/test_import_perf.py`（`@pytest.mark.slow`）
- [ ] `tests/test_models/test_edinet_code_quality.py`（`@pytest.mark.data_audit`）
- [ ] `tests/test_models/test_generate_scripts.py`（冪等性テスト — 必須）
- [ ] `tests/test_models/test_filing.py` — Step 0 テスト + @property テスト + model_dump 検証
- [ ] `pytest tests/ -m "not slow and not data_audit" -v` 通過
- [ ] `pytest tests/ -m slow -v` 通過
- [ ] `pytest tests/ -m data_audit -v` 通過

---

## 9. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| 自動生成 `.py` が大きすぎてインポート遅延 | 起動時に数百ms〜数秒 | `models/__init__.py` で edinet_code/fund_code をトップレベル import しない（Lazy）。性能検証は `@pytest.mark.slow` で分離 |
| CSV のカラム数ブレ（EdinetcodeDlInfo.csv） | パース失敗 | `csv.reader` を使えば引用符内カンマは安全。`str.split()` は使わない |
| ESE140327.xlsx の改版でカラム位置が変わる | 生成スクリプト破損 | ヘッダー行（3行目）のバリデーションを入れ、不一致なら即エラー |
| 全角カンマ・全角数字の混在 | モデルの値が一貫しない | 正規化はしない（元データの全角をそのまま保持）。Day 6 以降で必要に応じて正規化ユーティリティを追加 |
| form_code 単独で一意でない | ルックアップミス | キーを `(ordinance_code, form_code)` タプルにし、生成スクリプト内で重複チェック |
| 生成ファイルの diff ノイズ | レビュー困難 | `.gitattributes` で `linguist-generated=true` を設定し、GitHub 上で diff を折りたたむ |
| 生成ファイルの Lint エラー | CI 失敗 | 必要に応じて `pyproject.toml` の `[tool.ruff.lint.per-file-ignores]` に生成ファイルを追加し、特定のルール（行長制限など）を緩和する |

---

## 10. MEMO.md への追記予定

Day 4.5 完了時に以下を追記:

- **府令コード `060` の名称について**: API 仕様書に明記なし。ESE140327.xlsx でのデータ用途から推定した名称を使用。公式に名前が判明したら更新すること
- **府令コードの件数**: MEMO.md (Day 4) で「6件」と記載していたが、ESE140327.xlsx の調査で **7件** と確認。`060` が漏れていた。修正する
- **自動生成ファイルのサイズについて**: `edinet_code.py` は推定 3-5MB。`models/__init__.py` からはトップレベル import せず、Lazy import とする。インポート時間テストで 2 秒以内を保証。将来的に JSON/pickle 化を検討する余地あり
- **EdinetcodeDlInfo.csv のカラム数ブレについて**: 英字名フィールド内のカンマが原因。`csv.reader` で正しくパースできることを確認済み
- **form_code の一意性について**: form_code は単独で一意ではない（55件が複数の ordinance_code に登場）。ルックアップキーは `(ordinance_code, form_code)` タプルとした
- **資本金の単位**: EdinetcodeDlInfo.csv の `capital` は**百万円単位**と確定（トヨタ E02144 の比率=1.0000）。フィールド名を `capital_million_yen` として単位を明示
- **`Filing.from_api_response()` の不整合修正**: MEMO.md (Day 4) で Optional 化した `docTypeCode` 等 5 フィールドが `data["key"]` のままだった問題を修正（`data.get()` に統一）
- **`OrdinanceCode.SPECIFIED_SECURITIES` の命名**: 当初 `PARENT_COMPANY` としていたが、`DocType.PARENT_COMPANY_STATUS_REPORT`（コード `200`）と紛らわしいため `SPECIFIED_SECURITIES` に変更
- **`ordinance` / `form` は `@property`**: `computed_field` だと `model_dump()` に `FormCodeEntry` の全フィールドがネスト展開されるため、`@property` にした。既存の `doc_type` は軽量（Enum）なので `computed_field` のまま
- **FormCodeEntry に `doc_type_code` フィールドを追加するか**: ESE140327.xlsx の「書類種別」列は `DocType` と対応するが、名称文字列でのマッチは脆い。v0.1.0 では YAGNI として先送り。Day 6 以降で `DocType` コードとの紐付けが必要になったら追加を検討
- **生成スクリプトの冪等性**: 生成日時をヘッダーに含めない設計とした。`test_generate_scripts.py` で冪等性を必須テストとして検証
- **CSV 生成スクリプトのカラムアクセス**: 固定インデックスではなくヘッダー行からカラム名→インデックスのマッピングを構築する方式に変更。将来のカラム追加に対しても堅牢

---

## 11. 時間見積もり

| Step | 内容 | 見積もり |
|------|------|----------|
| Step 0 | `from_api_response()` 修正 + **テスト修正** | **25分** |
| Step 1 | `OrdinanceCode` 実装 + テスト | 30分 |
| Step 2 | 生成スクリプト 3本 | **60〜75分** |
| Step 3 | コード生成実行 | 5分（ユーザー操作） |
| Step 4 | テスト作成（4ファイル + 冪等性） | **45〜60分** |
| Step 5 | Filing `@property` + テスト | 15分 |
| Step 6 | 全テスト実行 | 5分 |
| **合計** | | **約 3〜3.5 時間** |

※ Step 2 は当初 45分と見積もっていたが、`generate_edinet_codes.py` の全角クォート処理・空文字→None変換のエッジケースが多くデバッグに時間がかかる可能性があるため上方修正。Step 4 も 4 ファイル + 冪等性テストを含むため上方修正。

---

## 12. フィードバック対応ログ

Day 4.5 計画の策定にあたり、以下のフィードバックを受け、対応を行いました。

### 第1回・第2回 フィードバック

| 項目 | 内容 | 対応 | 理由 |
|---|---|---|---|
| **FormCode 一意性** | `form_code` は単独で一意でない（55件重複） | ✅ **対応済**。キーを `(ordinance, form)` 複合キーに変更 | 実データに基づく正しい設計が必要なため |
| **Lazy Import** | 生成ファイルが巨大で import が遅くなる懸念 | ✅ **対応済**。`__init__.py` でトップレベル import しない | アプリケーション起動時間の短縮 |
| **CSV パース** | カラム位置ズレやカンマのリスク | ✅ **対応済**。`csv.reader` 使用 + ヘッダーからインデックスマップ構築 | 将来の仕様変更（カラム追加）への堅牢性確保 |
| **資本金単位** | 単位が不明確 | ✅ **対応済**。調査により百万円と確定。フィールド名を `capital_million_yen` に変更 | 曖昧さを排除するため |
| **OrdinanceCode 060** | 命名 `LARGE_SHAREHOLDING_SPECIAL` への懸念 | ✅ **現状維持**。MEMO に由来を記載 | 現時点で公式な英語名が存在しないため、意味的に近い名称を採用しつつ記録を残す |

### 第3回 フィードバック

| 項目 | 内容 | 対応 | 理由 |
|---|---|---|---|
| **Step 0 テスト修正** | `from_api_response` 修正で既存の KeyErorr 期待テストが壊れる | ✅ **Step 0 に追加**。テスト修正をタスクに明記 | テストの整合性を保つため（Critical） |
| **CI での不具合** | ソースがない環境で冪等性テストが落ちる | ✅ **対応**。`skipif` でソース欠落時はスキップする設計に変更 | CI をグリーンに保つため |
| **レビュー困難** | 生成ファイル（数MB）の diff が巨大 | ✅ **対応**。`.gitattributes` 設定を追加 | レビュー効率向上のため |
| **Filing 表示** | `filer_name` が None の時の `__str__` が見づらい | ✅ **対応**。Step 0 で `__str__` 改善を追加 | デバッグビリティー向上のため |
| **EdinetCode 表示** | `__str__` に `sec_code` が欲しい | ✅ **対応**。`__str__` に追加 | デバッグ時に有用なため |
| **pyproject.toml** | 依存関係への言及が必要 | ✅ **対応**。準備ステップに `openpyxl` 追加手順を明記 | ツール実行に必要なため |

### 第4回 フィードバック

| 項目 | 内容 | 対応 | 理由 |
|---|---|---|---|
| **件数テストの閾値が広すぎる** | 400〜420 / 6000〜7000 / 10000〜12000 では異常を見逃す | ✅ **対応**。413 / 6377 / 11223 の厳密一致に変更 | 退行検知精度を上げるため |
| **性能/品質テストでCIが不安定** | import時間・データ品質が通常ユニットを不安定化 | ✅ **対応**。`slow` / `data_audit` マーカーで分離実行 | 通常ユニットの安定性を確保するため |
| **冪等性テストが skip 依存** | ソース不在 CI で退行検知できない | ✅ **対応**。合成入力を使う常時実行可能テストを追加 | CI で継続的に生成スクリプトを監視するため |
| **PowerShell 非互換コマンド** | `mkdir -p` が環境依存 | ✅ **対応**。PowerShell コマンドに変更 | 実行手順の再現性を上げるため |
| **exceptions 集約の可視化不足** | MEMO の懸念がチェックリストにない | ✅ **対応**。成果物チェックリストに `exceptions.py` 確認を追加 | 計画と実装方針を一致させるため |

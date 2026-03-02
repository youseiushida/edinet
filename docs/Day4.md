# Day 4 — DocType + Filing モデル

## 目標

Day 4 の終了時に以下が動くこと:

```python
from edinet._config import configure  # Day 4 暫定。Day 6 で from edinet import configure に移行
from edinet.api.documents import get_documents  # Day 4 暫定。Day 6 で from edinet import documents に移行
from edinet.models.filing import Filing
from edinet.models.doc_types import DocType

configure(api_key="your-api-key")
result = get_documents("2026-02-07")

# 生の dict から Filing オブジェクトに変換
filings = Filing.from_api_list(result)
print(len(filings))   # → 件数は日付により変動する
print(filings[0])     # → Filing(S100XXXX | トヨタ自動車株式会社 | 有価証券報告書...)

# Filing の属性に Pythonic にアクセス
f = filings[0]
print(f.doc_id)           # "S100XXXX"
print(f.doc_type)         # DocType.ANNUAL_SECURITIES_REPORT
print(f.doc_type.name_ja) # "有価証券報告書"
print(f.filing_date)      # datetime.date(2026, 2, 7)
print(f.has_xbrl)         # True
print(f.ticker)           # "7203"

# DocType の訂正版紐付け
dt = DocType.AMENDED_ANNUAL_SECURITIES_REPORT  # "130"
print(dt.is_correction)   # True
print(dt.original)        # DocType.ANNUAL_SECURITIES_REPORT ("120")
```

edinet-tools の致命的欠陥（6型式欠落・名称誤り・定義が2ファイルに分散）を最初から回避する。

---

## 実装対象ファイル

| ファイル | 役割 | 行数目安 |
|----------|------|----------|
| `src/edinet/__init__.py` | パッケージ初期化（空ファイル、公開 API は Day 6 で追加） | 0行 |
| `src/edinet/api/__init__.py` | api パッケージ初期化（空ファイル） | 0行 |
| `src/edinet/models/__init__.py` | models パッケージの公開エクスポート | ~5行 |
| `src/edinet/models/doc_types.py` | 全42書類種別コード Enum 定義（single source of truth） | ~200行 |
| `src/edinet/models/filing.py` | Filing Pydantic モデル + API→モデル変換 | ~180行 |
| `tests/test_models/conftest.py` | テスト用 fixture（`_warned_unknown_codes` リセット） | ~10行 |
| `tests/test_models/test_doc_types.py` | 書類種別の網羅性テスト | ~120行 |
| `tests/test_models/test_filing.py` | Filing モデル変換テスト | ~180行 |

---

## 1. `models/doc_types.py` — 書類種別コード

### 設計方針

- ~~**情報源は公式 Excel（ESE140327.xlsx）の1つだけ**~~: ~~日本語名称はこの Excel から転記する。Web の二次情報や推測で埋めない~~ これは明確な誤りで、書籍種別コードはAPIの仕様書（ https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf ）に記載されている。
- **定義ファイルは `doc_types.py` の1つだけ**: edinet-tools は `config.py` と `doc_types.py` の2ファイルに型式定義が分散し、6型式が欠落した。定義箇所を1ファイルに限定して重複定義を構造的に防ぐ
- **全コードを漏れなく定義する**: テストで公式リストと突き合わせて機械的に検証する
- **訂正版→原本の紐付け**: `.original` プロパティで訂正版から原本を辿れるようにする
- **未知のコードを安全に扱う**: EDINET が将来新しいコードを追加しても、パイプラインが壊れないようにする（edinet-tools はサイレントに除外していた）

### コード一覧（情報源: ESE140327.xlsx）

~~**重要: 以下の日本語名称は ESE140327.xlsx から正確に転記すること。推測で埋めない。**~~
これは明確な誤りで、書籍種別コードはAPIの仕様書（ https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf ）に記載されている。

| コード | Enum メンバー名 | 日本語名称 | 区分 |
|--------|-----------------|-----------|------|
| 010 | `SECURITIES_NOTIFICATION` | 有価証券通知書 | 原本 |
| 020 | `SECURITIES_CHANGE_NOTIFICATION` | 変更通知書（有価証券通知書） | 原本 |
| 030 | `SECURITIES_REGISTRATION` | 有価証券届出書 | 原本 |
| 040 | `AMENDED_SECURITIES_REGISTRATION` | 訂正有価証券届出書 | 訂正→030 |
| 050 | `WITHDRAWAL_OF_REGISTRATION` | 届出の取下げ願い | 原本 |
| 060 | `SHELF_REGISTRATION_NOTICE` | 発行登録通知書 | 原本 |
| 070 | `SHELF_REGISTRATION_CHANGE_NOTIFICATION` | 変更通知書（発行登録通知書） | 原本 |
| 080 | `SHELF_REGISTRATION_STATEMENT` | 発行登録書 | 原本 |
| 090 | `AMENDED_SHELF_REGISTRATION_STATEMENT` | 訂正発行登録書 | 訂正→080 |
| 100 | `SHELF_REGISTRATION_SUPPLEMENTS` | 発行登録追補書類 | 原本 |
| 110 | `WITHDRAWAL_OF_SHELF_REGISTRATION` | 発行登録取下届出書 | 原本 |
| 120 | `ANNUAL_SECURITIES_REPORT` | 有価証券報告書 | 原本 |
| 130 | `AMENDED_ANNUAL_SECURITIES_REPORT` | 訂正有価証券報告書 | 訂正→120 |
| 135 | `CONFIRMATION_LETTER` | 確認書 | 原本 |
| 136 | `AMENDED_CONFIRMATION_LETTER` | 訂正確認書 | 訂正→135 |
| 140 | `QUARTERLY_REPORT` | 四半期報告書 | 原本 |
| 150 | `AMENDED_QUARTERLY_REPORT` | 訂正四半期報告書 | 訂正→140 |
| 160 | `SEMIANNUAL_REPORT` | 半期報告書 | 原本 |
| 170 | `AMENDED_SEMIANNUAL_REPORT` | 訂正半期報告書 | 訂正→160 |
| 180 | `EXTRAORDINARY_REPORT` | 臨時報告書 | 原本 |
| 190 | `AMENDED_EXTRAORDINARY_REPORT` | 訂正臨時報告書 | 訂正→180 |
| 200 | `PARENT_COMPANY_STATUS_REPORT` | 親会社等状況報告書 | 原本 |
| 210 | `AMENDED_PARENT_COMPANY_STATUS_REPORT` | 訂正親会社等状況報告書 | 訂正→200 |
| 220 | `SHARE_BUYBACK_STATUS_REPORT` | 自己株券買付状況報告書 | 原本 |
| 230 | `AMENDED_SHARE_BUYBACK_STATUS_REPORT` | 訂正自己株券買付状況報告書 | 訂正→220 |
| 235 | `INTERNAL_CONTROL_REPORT` | 内部統制報告書 | 原本 |
| 236 | `AMENDED_INTERNAL_CONTROL_REPORT` | 訂正内部統制報告書 | 訂正→235 |
| 240 | `TENDER_OFFER_REGISTRATION` | 公開買付届出書 | 原本 |
| 250 | `AMENDED_TENDER_OFFER_REGISTRATION` | 訂正公開買付届出書 | 訂正→240 |
| 260 | `TENDER_OFFER_WITHDRAWAL` | 公開買付撤回届出書 | 原本 |
| 270 | `TENDER_OFFER_REPORT` | 公開買付報告書 | 原本 |
| 280 | `AMENDED_TENDER_OFFER_REPORT` | 訂正公開買付報告書 | 訂正→270 |
| 290 | `OPINION_REPORT` | 意見表明報告書 | 原本 |
| 300 | `AMENDED_OPINION_REPORT` | 訂正意見表明報告書 | 訂正→290 |
| 310 | `TENDER_OFFER_ANSWER_REPORT` | 対質問回答報告書 | 原本 |
| 320 | `AMENDED_TENDER_OFFER_ANSWER_REPORT` | 訂正対質問回答報告書 | 訂正→310 |
| 330 | `SEPARATE_PURCHASE_PROHIBITION_EXCEPTION` | 別途買付け禁止の特例を受けるための申出書 | 原本 |
| 340 | `AMENDED_SEPARATE_PURCHASE_PROHIBITION_EXCEPTION` | 訂正別途買付け禁止の特例を受けるための申出書 | 訂正→330 |
| 350 | `LARGE_SHAREHOLDING_REPORT` | 大量保有報告書 | 原本 |
| 360 | `AMENDED_LARGE_SHAREHOLDING_REPORT` | 訂正大量保有報告書 | 訂正→350 |
| 370 | `STATUS_REPORT_AS_OF_RECORD_DATE` | 基準日の届出書 | 原本 |
| 380 | `CHANGE_REPORT` | 変更の届出書 | 原本 |

**合計 42 コード**（原本 25 + 訂正 17）。

注意: PLAN.md との数値不整合について:
- PLAN.md §9 の本文には「全41型式」と記載されている
- しかし PLAN.md §7 のテストコードリスト（`OFFICIAL_CODES`）は 42 個ある
- つまり **PLAN.md 内部で本文と例が矛盾している**
- 本実装では公式 Excel (ESE140327.xlsx) の値を正とする（合計 42 コード）
- テスト名・コメント中の数値は Excel の実数に合わせること
- PLAN.md は初版の計画として変更しない（Day 4 の注記で差異を記録するのみ）

注意: PLAN.md §2 のコード 330 名称について:
- PLAN.md では「別途買付禁止**特例**申出書」（略記）
- Day 4 / ESE140327.xlsx では「別途買付禁止**の特例を受けるための**申出書」（正式名称）
- 実装は公式 Excel の正式名称に従う。PLAN.md は初版の略記として変更しない

### edinet-tools が欠落させた6型式

| コード | 名称 | 影響 |
|--------|------|------|
| 240 | 公開買付届出書 | M&A 関連書類が消失 |
| 260 | 公開買付報告書 | 同上 |
| 270 | 公開買付撤回届出書 | 同上 |
| 290 | 意見表明報告書 | 同上 |
| 310 | 対質問回答報告書 | 同上 |
| 330 | 別途買付禁止特例申出書 | 同上 |

→ `filter_documents()` がこれらをサイレントに除外し、M&A 関連の分析が壊れていた。

### Enum 定義

```python
"""EDINET 書類種別コード (docTypeCode) の Enum 定義。

情報源: EDINET API 仕様書 Version 2 (ESE140206.pdf)
全コードを定義。他のファイルで書類種別を再定義しないこと（single source of truth）。

Note: PLAN.md 本文は「41型式」と記載しているが、API 仕様書にはそれ以上のコードが
定義されている可能性がある。実装は API 仕様書を正とする。PLAN.md は変更しない。
"""
from __future__ import annotations

import warnings
from enum import Enum


class EdinetWarning(UserWarning):
    """edinet ライブラリが発行する warning の基底クラス。

    利用者が warnings.filterwarnings("ignore", category=EdinetWarning) で
    ライブラリ固有の warning だけをフィルタできる。
    """


class DocType(str, Enum):
    """EDINET 書類種別コード。

    str を継承しているため、文字列として比較可能:
        DocType.ANNUAL_SECURITIES_REPORT == "120"  # True

    Attributes:
        name_ja: 日本語名称（API 仕様書準拠）
        original: 訂正版の場合、原本の DocType。原本自身は None
        is_correction: 訂正報告書かどうか
    """

    # --- 有価証券通知書関連 ---
    SECURITIES_NOTIFICATION = "010"
    SECURITIES_CHANGE_NOTIFICATION = "020"

    # --- 有価証券届出書関連 ---
    SECURITIES_REGISTRATION = "030"
    AMENDED_SECURITIES_REGISTRATION = "040"
    WITHDRAWAL_OF_REGISTRATION = "050"

    # --- 発行登録関連 ---
    SHELF_REGISTRATION_NOTICE = "060"
    SHELF_REGISTRATION_CHANGE_NOTIFICATION = "070"
    SHELF_REGISTRATION_STATEMENT = "080"
    AMENDED_SHELF_REGISTRATION_STATEMENT = "090"
    SHELF_REGISTRATION_SUPPLEMENTS = "100"
    WITHDRAWAL_OF_SHELF_REGISTRATION = "110"

    # --- 有価証券報告書関連 ---
    ANNUAL_SECURITIES_REPORT = "120"
    AMENDED_ANNUAL_SECURITIES_REPORT = "130"
    CONFIRMATION_LETTER = "135"  # 「確認書」— 以前の定義と混同注意
    AMENDED_CONFIRMATION_LETTER = "136"

    # --- 四半期報告書・半期報告書 ---
    QUARTERLY_REPORT = "140"
    AMENDED_QUARTERLY_REPORT = "150"
    SEMIANNUAL_REPORT = "160"
    AMENDED_SEMIANNUAL_REPORT = "170"

    # --- 臨時報告書 ---
    EXTRAORDINARY_REPORT = "180"
    AMENDED_EXTRAORDINARY_REPORT = "190"

    # --- 親会社等状況報告書 ---
    PARENT_COMPANY_STATUS_REPORT = "200"
    AMENDED_PARENT_COMPANY_STATUS_REPORT = "210"

    # --- 自己株券買付状況報告書 ---
    SHARE_BUYBACK_STATUS_REPORT = "220"
    AMENDED_SHARE_BUYBACK_STATUS_REPORT = "230"

    # --- 内部統制報告書 ---
    INTERNAL_CONTROL_REPORT = "235"
    AMENDED_INTERNAL_CONTROL_REPORT = "236"

    # --- 公開買付関連（edinet-tools が欠落させた6型式の一部） ---
    TENDER_OFFER_REGISTRATION = "240"
    AMENDED_TENDER_OFFER_REGISTRATION = "250"
    TENDER_OFFER_WITHDRAWAL = "260"
    TENDER_OFFER_REPORT = "270"
    AMENDED_TENDER_OFFER_REPORT = "280"

    # --- 意見表明・対質問関連（edinet-tools が欠落させた6型式の一部） ---
    OPINION_REPORT = "290"
    AMENDED_OPINION_REPORT = "300"
    TENDER_OFFER_ANSWER_REPORT = "310"
    AMENDED_TENDER_OFFER_ANSWER_REPORT = "320"
    SEPARATE_PURCHASE_PROHIBITION_EXCEPTION = "330"
    AMENDED_SEPARATE_PURCHASE_PROHIBITION_EXCEPTION = "340"

    # --- 大量保有報告書関連 ---
    LARGE_SHAREHOLDING_REPORT = "350"
    AMENDED_LARGE_SHAREHOLDING_REPORT = "360"

    # --- 基準日・変更届出書 ---
    STATUS_REPORT_AS_OF_RECORD_DATE = "370"
    CHANGE_REPORT = "380"

    # ----- プロパティ -----

    @property
    def name_ja(self) -> str:
        """日本語名称（API 仕様書準拠）。"""
        return _DOC_TYPE_NAMES_JA[self.value]

    @property
    def original(self) -> DocType | None:
        """訂正版の場合、原本の DocType を返す。原本自身は None。"""
        return _CORRECTION_MAP.get(self)

    @property
    def is_correction(self) -> bool:
        """訂正報告書かどうか。"""
        return self.original is not None

    # ----- ファクトリメソッド -----

    @classmethod
    def from_code(cls, code: str) -> DocType | None:
        """コード文字列から DocType を返す。未知のコードは None + warning。

        edinet-tools は未知のコードをサイレントに除外していた。
        このメソッドは未知のコードを warning で通知し、
        呼び出し元が判断できるようにする。

        同一コードに対する warning は同一 Python プロセス内で1回だけ出す（スパム防止）。
        API レスポンスに未知コードが大量に含まれるケース
        （将来のコード追加・API 側の一時的不整合）でログが溢れない。

        Args:
            code: 書類種別コード。「010」「120」のような3桁ゼロ埋め文字列。
                  EDINET API は常に3桁文字列で返すため、int や非ゼロ埋め（「10」等）は
                  未知コード扱いになる。

        Returns:
            対応する DocType。未知のコードは None。
        """
        try:
            return cls(code)
        except ValueError:
            if code not in _warned_unknown_codes:
                _warned_unknown_codes.add(code)
                warnings.warn(
                    f"Unknown docTypeCode: '{code}'. "
                    f"Check the latest EDINET API specification (ESE140206.pdf).",
                    category=EdinetWarning,
                    stacklevel=2,
                )
            return None


# --- warning スパム防止 ---
# 同一コードに対する warning は1回だけ出す。
_warned_unknown_codes: set[str] = set()


def _reset_warning_state() -> None:
    """テスト用: warning 抑制状態をリセットする。

    テストから _warned_unknown_codes を直接操作する代わりに
    この関数を呼ぶことで、内部実装の変更がテストに波及しない。
    本番コードからは呼ばないこと。
    """
    _warned_unknown_codes.clear()


# --- 日本語名称マッピング ---
# Enum クラス定義の後に置く（Enum メンバーへの前方参照を避けるため）。
# 名称は API 仕様書 (ESE140206.pdf) から正確に転記すること。
_DOC_TYPE_NAMES_JA: dict[str, str] = {
    "010": "有価証券通知書",
    "020": "変更通知書（有価証券通知書）",
    "030": "有価証券届出書",
    "040": "訂正有価証券届出書",
    "050": "届出の取下げ願い",
    "060": "発行登録通知書",
    "070": "変更通知書（発行登録通知書）",
    "080": "発行登録書",
    "090": "訂正発行登録書",
    "100": "発行登録追補書類",
    "110": "発行登録取下届出書",
    "120": "有価証券報告書",
    "130": "訂正有価証券報告書",
    "135": "確認書",
    "136": "訂正確認書",
    "140": "四半期報告書",
    "150": "訂正四半期報告書",
    "160": "半期報告書",
    "170": "訂正半期報告書",
    "180": "臨時報告書",
    "190": "訂正臨時報告書",
    "200": "親会社等状況報告書",
    "210": "訂正親会社等状況報告書",
    "220": "自己株券買付状況報告書",
    "230": "訂正自己株券買付状況報告書",
    "235": "内部統制報告書",
    "236": "訂正内部統制報告書",
    "240": "公開買付届出書",
    "250": "訂正公開買付届出書",
    "260": "公開買付撤回届出書",
    "270": "公開買付報告書",
    "280": "訂正公開買付報告書",
    "290": "意見表明報告書",
    "300": "訂正意見表明報告書",
    "310": "対質問回答報告書",
    "320": "訂正対質問回答報告書",
    "330": "別途買付け禁止の特例を受けるための申出書",
    "340": "訂正別途買付け禁止の特例を受けるための申出書",
    "350": "大量保有報告書",
    "360": "訂正大量保有報告書",
    "370": "基準日の届出書",
    "380": "変更の届出書",
}

# --- 公式コード集合（テストから参照される single source of truth） ---
# _DOC_TYPE_NAMES_JA のキーから導出することで、
# テスト側にコードリストをベタ書きする二重管理を排除する。
OFFICIAL_CODES: tuple[str, ...] = tuple(sorted(_DOC_TYPE_NAMES_JA.keys()))


# --- 訂正→原本マッピング ---
# 「訂正」（Amended）のみをマッピングする。
# 「変更」（020→010, 070→060）は訂正ではないためマッピングしない。
#
# 以下の原本コードには対応する訂正版コードが仕様書に存在しない（全 9 コード）:
#   010, 020, 050, 060, 070, 100, 110, 260, 370, 380
# 検算: 原本 25 − 訂正あり 16 = 訂正なし 9
_CORRECTION_MAP: dict[DocType, DocType] = {
    DocType.AMENDED_SECURITIES_REGISTRATION: DocType.SECURITIES_REGISTRATION,                         # 040→030
    DocType.AMENDED_SHELF_REGISTRATION_STATEMENT: DocType.SHELF_REGISTRATION_STATEMENT,               # 090→080
    DocType.AMENDED_ANNUAL_SECURITIES_REPORT: DocType.ANNUAL_SECURITIES_REPORT,                       # 130→120
    DocType.AMENDED_CONFIRMATION_LETTER: DocType.CONFIRMATION_LETTER,                                 # 136→135
    DocType.AMENDED_QUARTERLY_REPORT: DocType.QUARTERLY_REPORT,                                       # 150→140
    DocType.AMENDED_SEMIANNUAL_REPORT: DocType.SEMIANNUAL_REPORT,                                     # 170→160
    DocType.AMENDED_EXTRAORDINARY_REPORT: DocType.EXTRAORDINARY_REPORT,                               # 190→180
    DocType.AMENDED_PARENT_COMPANY_STATUS_REPORT: DocType.PARENT_COMPANY_STATUS_REPORT,               # 210→200
    DocType.AMENDED_SHARE_BUYBACK_STATUS_REPORT: DocType.SHARE_BUYBACK_STATUS_REPORT,                 # 230→220
    DocType.AMENDED_INTERNAL_CONTROL_REPORT: DocType.INTERNAL_CONTROL_REPORT,                         # 236→235
    DocType.AMENDED_TENDER_OFFER_REGISTRATION: DocType.TENDER_OFFER_REGISTRATION,                     # 250→240
    DocType.AMENDED_TENDER_OFFER_REPORT: DocType.TENDER_OFFER_REPORT,                                 # 280→270
    DocType.AMENDED_OPINION_REPORT: DocType.OPINION_REPORT,                                           # 300→290
    DocType.AMENDED_TENDER_OFFER_ANSWER_REPORT: DocType.TENDER_OFFER_ANSWER_REPORT,                   # 320→310
    DocType.AMENDED_SEPARATE_PURCHASE_PROHIBITION_EXCEPTION: DocType.SEPARATE_PURCHASE_PROHIBITION_EXCEPTION, # 340→330
    DocType.AMENDED_LARGE_SHAREHOLDING_REPORT: DocType.LARGE_SHAREHOLDING_REPORT,                     # 360→350
}
```

### `str, Enum` を使う理由

```python
# DocType は str を継承しているため、API レスポンスの文字列と直接比較できる
doc_type_code = "120"
if DocType(doc_type_code) == DocType.ANNUAL_SECURITIES_REPORT:
    ...

# JSON シリアライズ時に自然に文字列になる
import json
json.dumps({"type": DocType.ANNUAL_SECURITIES_REPORT})  # → '{"type": "120"}'
```

### 判断ポイント

| 項目 | 判断 | 理由 |
|------|------|------|
| `str, Enum` vs `Enum` | `str, Enum` | API レスポンスのコード文字列と直接比較可能。JSON シリアライズでも自然に動く |
| `name_ja` の格納方法 | 別 dict（`_DOC_TYPE_NAMES_JA`） | Enum の `__new__` をオーバーライドすると Pydantic との互換性で問題が出うる。プロパティ + 外部 dict が最もシンプル |
| `from_code()` の未知コード処理 | `None` + `warnings.warn()`（同一コードは1回だけ） | edinet-tools は未知コードをサイレントに除外。raise だとパイプラインが壊れる。warning なら気付ける。`_warned_unknown_codes` set で同一コードの重複 warning を抑制し、大量データ処理時のスパムを防止 |
| 訂正マッピングのスコープ | 「訂正」のみ（「変更」は含めない） | 020→010（変更通知書→有価証券通知書）は「訂正」ではなく「変更」。意味が異なるため混同しない |
| コード vs Excel のどちらを正とするか | Excel (ESE140327.xlsx) | Web の二次情報は誤りが多い（edinet-tools が 030 を「公開買付届出書」と誤記した例）。公式一次ソースのみ信頼する |

### チェックリスト

- [ ] 公式 Excel (ESE140327.xlsx) の全コードが漏れなく定義されていること
- [ ] 日本語名称が公式 Excel と完全に一致すること
- [ ] 全訂正型が原本に正しく紐付いていること
- [ ] `from_code()` で未知のコードに warning が出ること
- [ ] `DocType("120").name_ja` が正しく返ること
- [ ] edinet-tools が欠落させた 6 コード（240, 260, 270, 290, 310, 330）が全て定義されていること

---

## 2. `models/filing.py` — 提出書類モデル

### 設計方針

- **Pydantic BaseModel + frozen=True**: Filing はイミュータブル。API から受け取ったデータは変更しない
- **API 由来の全29フィールドを保持 + 派生4フィールドを提供**: API レスポンスのフィールドを1つも落とさない（「データは広く持ち、フィルタは遅く」の原則）。加えて `doc_type`、`filing_date`、`ticker`、`doc_type_label_ja` の4つの computed field を派生フィールドとして提供する。`model_dump()` の出力は計33キー
- **`from_api_response()` で明示的に変換**: API の camelCase + 文字列フラグを Pythonic な snake_case + 型に変換する
- **`computed_field` + `@property` で派生フィールドを提供**: `doc_type`（DocType Enum）、`filing_date`（date）、`ticker`（証券コード4桁）、`doc_type_label_ja`（安全な表示ラベル）は stored field ではなく computed field で導出し、DRY を保つ。全て `@property` で統一する（`cached_property` は使わない。理由は §7 技術補足を参照）

### EDINET API レスポンスフィールド完全一覧（API 仕様書 §3-1-2-2）

Day 3 の `get_documents()` が返す dict の `results` 配列の各要素:

| # | API フィールド名 | 型 | 説明 | Filing フィールド名 | 変換 |
|---|-----------------|-----|------|-------------------|----- |
| 1 | `seqNumber` | int | シーケンス番号 | `seq_number` | そのまま |
| 2 | `docID` | str | 書類管理番号（例: "S100XXXX"） | `doc_id` | そのまま |
| 3 | `edinetCode` | str/null | EDINETコード（例: "E02144"） | `edinet_code` | null→None |
| 4 | `secCode` | str/null | 証券コード5桁+チェックディジット | `sec_code` | null→None |
| 5 | `JCN` | str/null | 法人番号 | `jcn` | null→None |
| 6 | `filerName` | str | 提出者名称 | `filer_name` | そのまま |
| 7 | `fundCode` | str/null | ファンドコード | `fund_code` | null→None |
| 8 | `ordinanceCode` | str | 府令コード | `ordinance_code` | そのまま |
| 9 | `formCode` | str | 様式コード | `form_code` | そのまま |
| 10 | `docTypeCode` | str | 書類種別コード（例: "120"） | `doc_type_code` | そのまま |
| 11 | `periodStart` | str/null | 期間開始日 "YYYY-MM-DD" | `period_start` | str→date / null→None |
| 12 | `periodEnd` | str/null | 期間終了日 "YYYY-MM-DD" | `period_end` | str→date / null→None |
| 13 | `submitDateTime` | str | 提出日時 "YYYY-MM-DD HH:MM" | `submit_date_time` | str→datetime |
| 14 | `docDescription` | str | 書類概要 | `doc_description` | そのまま |
| 15 | `issuerEdinetCode` | str/null | 発行会社EDINETコード | `issuer_edinet_code` | null→None |
| 16 | `subjectEdinetCode` | str/null | 対象EDINETコード | `subject_edinet_code` | null→None |
| 17 | `subsidiaryEdinetCode` | str/null | 子会社EDINETコード | `subsidiary_edinet_code` | null→None |
| 18 | `currentReportReason` | str/null | 臨時報告書の提出事由 | `current_report_reason` | null→None |
| 19 | `parentDocID` | str/null | 親書類管理番号 | `parent_doc_id` | null→None |
| 20 | `opeDateTime` | str/null | 操作日時 | `ope_date_time` | str→datetime / null→None |
| 21 | `withdrawalStatus` | str | 取下げ状態 | `withdrawal_status` | そのまま |
| 22 | `docInfoEditStatus` | str | 書類情報修正区分 | `doc_info_edit_status` | そのまま |
| 23 | `disclosureStatus` | str | 開示不開示区分 | `disclosure_status` | そのまま |
| 24 | `xbrlFlag` | str | XBRL有無 "0"/"1" | `has_xbrl` | "1"→True |
| 25 | `pdfFlag` | str | PDF有無 | `has_pdf` | "1"→True |
| 26 | `attachDocFlag` | str | 添付書類有無 | `has_attachment` | "1"→True |
| 27 | `englishDocFlag` | str | 英文書類有無 | `has_english` | "1"→True |
| 28 | `csvFlag` | str | CSV有無 | `has_csv` | "1"→True |
| 29 | `legalStatus` | str | 法定・任意区分 | `legal_status` | そのまま |

### ステータスフィールドの値定義

テストやドキュメントの参照用。Day 4 では Enum 化せず文字列のまま保持する。
必要に応じて Day 6 以降で Enum 化を検討。

```
withdrawalStatus:
  "0" = 未取下げ（通常）
  "1" = 取下済
  "2" = 取下要求中

docInfoEditStatus:
  "0" = 修正なし（通常）
  "1" = 修正あり

disclosureStatus:
  "0" = 通常開示
  "1" = 非開示
  "2" = 延期

legalStatus:
  "0" = 任意
  "1" = 法定
```

### Filing モデル定義

```python
"""EDINET 提出書類 (Filing) の Pydantic モデル。

EDINET API 仕様書 §3-1-2-2 の全29フィールドを保持する。
"""
from __future__ import annotations

import warnings
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from edinet.models.doc_types import DocType


# --- ヘルパー関数（モジュールプライベート） ---

def _parse_date(value: str | None) -> date | None:
    """EDINET API の日付文字列 'YYYY-MM-DD' を date に変換。

    None、空文字、空白のみの場合は None を返す。
    """
    if not value or not value.strip():
        return None
    return date.fromisoformat(value)


def _parse_datetime(value: str, *, field_name: str = "") -> datetime:
    """EDINET API の日時文字列 'YYYY-MM-DD HH:MM' を datetime に変換。

    Note:
        EDINET API は日本時間（JST, UTC+9）で日時を返すが、タイムゾーン情報は
        付与されない。本ライブラリでは naive datetime として保持する。
        期間比較や並び替えを行う場合は、全ての datetime が JST である
        前提で扱うこと。aware datetime への移行は v0.2.0 以降で検討。

    Raises:
        ValueError: フォーマット不正。field_name が指定されていれば
                    エラーメッセージにフィールド名と生文字列を含める。
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as e:
        label = f" (field={field_name})" if field_name else ""
        msg = f"Invalid datetime format{label}: '{value}' (expected 'YYYY-MM-DD HH:MM')"
        raise ValueError(msg) from e


def _parse_datetime_optional(value: str | None, *, field_name: str = "") -> datetime | None:
    """EDINET API の日時文字列を datetime に変換。None/空なら None。"""
    if not value or not value.strip():
        return None
    return _parse_datetime(value, field_name=field_name)


def _parse_flag(value: str | None) -> bool:
    """EDINET API のフラグ '0'/'1' を bool に変換。"""
    return value == "1"


class Filing(BaseModel):
    """EDINET に提出された書類1件を表すモデル。

    EDINET API の書類一覧レスポンス (results 配列の1要素) から生成する。
    API 由来の全29フィールドを保持し、データを一切落とさない。
    加えて派生フィールド（doc_type, filing_date, ticker, doc_type_label_ja）を
    computed_field として提供する。

    **Note: コード値の型について**
    - `docTypeCode`: `DocType` Enum に変換して保持する（Day 4 のスコープ）。
    - `ordinanceCode`, `formCode`, `fundCode`: Day 4 時点では `str` としてそのまま保持する。これらは定義数が多く更新頻度も高いため、将来的にメタプログラミングで生成された専用 Enum/Model に移行する予定（Day 4.5 以降）。


    Note:
        日時フィールド（submit_date_time, ope_date_time）は EDINET API が返す
        JST（日本時間, UTC+9）を naive datetime として保持する。
        タイムゾーン情報は付与されない。

    利用例:
        >>> result = get_documents("2026-02-07")
        >>> filings = Filing.from_api_list(result)
        >>> f = filings[0]
        >>> f.doc_id
        'S100XXXX'
        >>> f.doc_type
        DocType.ANNUAL_SECURITIES_REPORT
        >>> f.filing_date
        datetime.date(2026, 2, 7)
    """

    model_config = ConfigDict(frozen=True)

    # --- 識別子 ---
    seq_number: int
    doc_id: str

    # --- 書類種別 ---
    doc_type_code: str
    ordinance_code: str
    form_code: str

    # --- 提出者情報（Day 6 で Company にネストする候補） ---
    edinet_code: str | None
    sec_code: str | None
    jcn: str | None
    filer_name: str
    fund_code: str | None

    # --- 日付・期間 ---
    submit_date_time: datetime
    period_start: date | None
    period_end: date | None

    # --- 書類概要 ---
    doc_description: str

    # --- 関連書類・関連コード ---
    issuer_edinet_code: str | None
    subject_edinet_code: str | None
    subsidiary_edinet_code: str | None
    current_report_reason: str | None
    parent_doc_id: str | None
    ope_date_time: datetime | None

    # --- ステータス（Day 4 では文字列のまま） ---
    withdrawal_status: str
    doc_info_edit_status: str
    disclosure_status: str

    # --- コンテンツフラグ ---
    has_xbrl: bool
    has_pdf: bool
    has_attachment: bool
    has_english: bool
    has_csv: bool

    # --- 法定・任意 ---
    legal_status: str

    # --- 計算フィールド ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def doc_type(self) -> DocType | None:
        """doc_type_code に対応する DocType Enum。

        未知のコードの場合は None（DocType.from_code() が warning を出す）。
        dict lookup（O(1)）なのでキャッシュ不要。
        """
        return DocType.from_code(self.doc_type_code)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def filing_date(self) -> date:
        """提出日（submit_date_time の日付部分）。

        PLAN.md §4 の Filing モデル定義で filing_date: date と定義。
        submit_date_time から導出することで二重管理を避ける。
        """
        return self.submit_date_time.date()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ticker(self) -> str | None:
        """証券コード4桁。

        sec_code は5桁（末尾チェックディジット付き）で返る。
        先頭4桁を切り出して一般的な「証券コード」として返す。
        sec_code が None または短すぎる場合は None。
        """
        if self.sec_code and len(self.sec_code) >= 4:
            return self.sec_code[:4]
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def doc_type_label_ja(self) -> str:
        """書類種別の日本語表示ラベル（常に str を返す）。

        doc_type が None（未知コード）の場合は doc_type_code にフォールバック。
        UI やログで doc_type の Optional チェックを毎回書かずに済む。
        """
        dt = self.doc_type
        return dt.name_ja if dt else self.doc_type_code

    # --- ファクトリメソッド ---

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Filing:
        """EDINET API の書類一覧レスポンス（1件分の dict）から Filing を生成する。

        Args:
            data: get_documents() の results 配列の1要素。

        Returns:
            Filing オブジェクト。

        Raises:
            KeyError: 必須フィールド（docID, seqNumber, docTypeCode,
                      ordinanceCode, formCode, filerName, submitDateTime,
                      docDescription）が欠落。
            ValueError: 日時文字列のフォーマットが不正。
        """
        return cls(
            # === 必須フィールド（data["key"] — 欠落は KeyError で即座に検知） ===
            seq_number=data["seqNumber"],
            doc_id=data["docID"],
            doc_type_code=data["docTypeCode"],
            ordinance_code=data["ordinanceCode"],
            form_code=data["formCode"],
            filer_name=data["filerName"],
            submit_date_time=_parse_datetime(
                data["submitDateTime"], field_name="submitDateTime",
            ),
            doc_description=data["docDescription"],
            # === 任意フィールド（data.get() — None で保持、デフォルト空文字は使わない） ===
            edinet_code=data.get("edinetCode"),
            sec_code=data.get("secCode"),
            jcn=data.get("JCN"),
            fund_code=data.get("fundCode"),
            # 日付・期間
            period_start=_parse_date(data.get("periodStart")),
            period_end=_parse_date(data.get("periodEnd")),
            # 関連書類
            issuer_edinet_code=data.get("issuerEdinetCode"),
            subject_edinet_code=data.get("subjectEdinetCode"),
            subsidiary_edinet_code=data.get("subsidiaryEdinetCode"),
            current_report_reason=data.get("currentReportReason"),
            parent_doc_id=data.get("parentDocID"),
            ope_date_time=_parse_datetime_optional(
                data.get("opeDateTime"), field_name="opeDateTime",
            ),
            # ステータス
            # API 仕様上は常に存在する想定だが、防御的にデフォルト "0" を採用する。
            # Note: これにより API 仕様変更（フィールド削除）時の検知が遅れる可能性がある。
            # 必須化を検討する場合は KeyAccess に変更すること。
            withdrawal_status=data.get("withdrawalStatus", "0"),
            doc_info_edit_status=data.get("docInfoEditStatus", "0"),
            disclosure_status=data.get("disclosureStatus", "0"),
            # コンテンツフラグ
            has_xbrl=_parse_flag(data.get("xbrlFlag")),
            has_pdf=_parse_flag(data.get("pdfFlag")),
            has_attachment=_parse_flag(data.get("attachDocFlag")),
            has_english=_parse_flag(data.get("englishDocFlag")),
            has_csv=_parse_flag(data.get("csvFlag")),
            # 法定・任意
            legal_status=data.get("legalStatus", "0"),
        )

    @classmethod
    def from_api_list(cls, api_response: dict[str, Any]) -> list[Filing]:
        """get_documents() の戻り値全体から Filing リストを生成する。

        各要素の変換中に例外が発生した場合、何件目のどの書類で
        壊れたかを含む ValueError にラップして raise する。

        Args:
            api_response: get_documents() の戻り値（metadata + results を含む dict）。
                          引数名で「これは API のレスポンスそのもの」であることを明示。

        Returns:
            Filing オブジェクトのリスト。

        Raises:
            ValueError: 個別の Filing 変換に失敗した場合（元の例外を chain）。
        """
        results = api_response.get("results", [])
        filings: list[Filing] = []
        for i, doc in enumerate(results):
            try:
                filings.append(cls.from_api_response(doc))
            except (KeyError, ValueError) as e:
                doc_id = doc.get("docID", "?") if isinstance(doc, dict) else "?"
                doc_type = doc.get("docTypeCode", "?") if isinstance(doc, dict) else "?"
                raise ValueError(
                    f"Failed to parse document at index={i}, "
                    f"docID={doc_id}, docTypeCode={doc_type}: "
                    f"keys={sorted(doc.keys()) if isinstance(doc, dict) else type(doc).__name__}"
                ) from e
        return filings

    # --- 表示 ---

    def __str__(self) -> str:
        """コンソールでの簡潔な表示。"""
        return f"Filing({self.doc_id} | {self.filer_name} | {self.doc_type_label_ja})"
```

### `from_api_response()` の設計判断

| 項目 | 判断 | 理由 |
|------|------|------|
| classmethod vs Pydantic alias | classmethod | API のフィールド名と Filing のフィールド名が 1:1 対応しない（camelCase→snake_case だけでなく、型変換・フラグ変換・計算フィールドがある）。alias だと変換ロジックが散在するが classmethod なら1箇所に集約 |
| 必須フィールドのアクセス | `data["key"]`（KeyError で落ちる） | API 仕様上「常に存在する」フィールド: `docID`, `seqNumber`, `docTypeCode`, `ordinanceCode`, `formCode`, `filerName`, `submitDateTime`, `docDescription`。存在しないなら API レスポンスが壊れており、早期に KeyError で落とすことで仕様違反を即座に検知する |
| 任意フィールドのアクセス | `data.get("key")`（`None` で保持） | API が将来フィールドを削除しても壊れない防御的コーディング。**デフォルト空文字 `""` は使わない**（`None` と空文字の区別がつかなくなるため）。例外: ステータスフィールド（`withdrawalStatus` 等）は `"0"` がデフォルト値として API 仕様上妥当 |
| フラグの変換 | `"1" == "1"` → `True` | `"0"` / `"1"` の魔法の文字列を利用者に見せない。`filing.has_xbrl` は `filing.xbrl_flag == "1"` より遥かに読みやすい |
| `computed_field` + `@property` | 3フィールド全て `@property` で統一 | `DocType.from_code()` は dict lookup（O(1)）でコストがほぼゼロ。`cached_property` は `frozen=True` + Pydantic 内部の `__dict__` 書き込みに依存し、型チェッカとの相性問題が起きうる。シンプルさと一貫性を優先 |
| `__str__` のオーバーライド | 採用 | Pydantic のデフォルト `__repr__` は全29フィールドを出力して冗長。`Filing(S100XXXX | トヨタ | 有報)` で十分 |
| 不正日付文字列のエラー処理 | `ValueError` を伝搬（catch しない） | 不正な日付文字列は EDINET API の仕様違反。`_parse_datetime` にフィールド名と生文字列を含めたエラーメッセージを出力し、デバッグを容易にする。将来 `try-except` を追加する必要はない（早期発見が正しい戦略） |

### `frozen=True` の注意点

```python
# frozen=True にすると属性の再代入が ValidationError になる
filing.doc_id = "S200YYYY"  # → ValidationError: Instance is frozen

# computed_field + @property を使う場合、
# `# type: ignore[prop-decorator]` のコメントが必要になる
# （mypy/pyright のフォールスポジティブ回避）。
```

### チェックリスト

- [ ] API レスポンスの全29フィールドが Filing にマッピングされていること
- [ ] `from_api_response()` で日付文字列が正しく date/datetime に変換されること
- [ ] `from_api_response()` でフラグ "0"/"1" が正しく bool に変換されること
- [ ] `from_api_response()` で null が None に変換されること
- [ ] `doc_type` computed field が DocType Enum を正しく返すこと
- [ ] `filing_date` computed field が date を返すこと
- [ ] `ticker` computed field が証券コード4桁を返すこと
- [ ] `Filing` が frozen（イミュータブル）であること
- [ ] `__str__` が簡潔なフォーマットを返すこと
- [ ] `from_api_list()` が results 配列を Filing リストに変換すること

---

## 3. `models/__init__.py` — 公開エクスポート

```python
"""edinet.models — Pydantic データモデル。"""
from edinet.models.doc_types import DocType
from edinet.models.filing import Filing

__all__ = ["DocType", "Filing"]
```

これにより `from edinet.models import DocType, Filing` でインポート可能になる。

注意: パッケージ化の方針:
- Day 4 で `src/edinet/__init__.py`（空）、`src/edinet/api/__init__.py`（空）、
  `src/edinet/models/__init__.py`（公開エクスポート）を全て作成する
- これにより全パッケージが「明示パッケージ」に統一され、
  implicit namespace package との混在による環境差（特に Windows + editable install）を回避する
- `src/edinet/__init__.py` と `src/edinet/api/__init__.py` は空ファイル。
  公開 API（`edinet.configure()`, `edinet.documents()`）は Day 6 で追加する
- 第 3 回レビューでは「Day 6 で一斉統一」方針で不採用としたが、
  第 4 回レビューで「空ファイルを置くだけなら Day 6 のスコープ非侵食」と判断し採用に転換

---

## 4. テスト

### テスト戦略（Day 4）

```
Day 4 のテスト:
  - DocType: 全コードの網羅性テスト（edinet-tools の「6型式欠落」の再発防止）
  - DocType: プロパティ（name_ja, original, is_correction）のテスト
  - Filing: from_api_response() の変換テスト（フィクスチャ dict を使用）
  - Filing: computed field のテスト
  - Filing: エッジケース（null フィールド、未知の docTypeCode）

テスト優先度（時間切れ時の取捨選択基準）:
  コア（必須）:
    - 網羅性（全コード定義）
    - Enum と dict の完全一致
    - 訂正マッピングの集合比較
    - 未知コード warning の1回抑制
    - Filing 変換（正常/欠落/不正フォーマット）
  スポットチェック（削っても安全性は同等）:
    - 個別コードの name_ja 突合（全件空でないテストがコアにあるため）
    - test_originals_without_correction_count（更新手順に組み込めるなら残す）

Day 7 以降:
  - 実 API レスポンスを使った Large テスト
```

### テスト用 conftest: warning 状態の自動リセット

```python
# tests/test_models/conftest.py
import pytest


@pytest.fixture(autouse=True)
def _reset_warned_codes():
    """各テスト後に warning 抑制状態をリセットする。

    テスト順序依存のフレイキーテストを防止する。
    _warned_unknown_codes を直接操作せず、専用リセット関数を使うことで
    内部実装の変更がテストに波及しない。
    """
    yield
    from edinet.models.doc_types import _reset_warning_state
    _reset_warning_state()
```

### テストフィクスチャ: サンプル API レスポンス

```python
# tests/test_models/conftest.py（またはテストファイル内の定数）
SAMPLE_DOC: dict = {
    "seqNumber": 1,
    "docID": "S100TEST",
    "edinetCode": "E02144",
    "secCode": "72030",
    "JCN": "1180301018771",
    "filerName": "トヨタ自動車株式会社",
    "fundCode": None,
    "ordinanceCode": "010",
    "formCode": "030000",
    "docTypeCode": "120",
    "periodStart": "2024-04-01",
    "periodEnd": "2025-03-31",
    "submitDateTime": "2025-06-26 15:00",
    "docDescription": "有価証券報告書－第85期(2024/04/01－2025/03/31)",
    "issuerEdinetCode": None,
    "subjectEdinetCode": None,
    "subsidiaryEdinetCode": None,
    "currentReportReason": None,
    "parentDocID": None,
    "opeDateTime": None,
    "withdrawalStatus": "0",
    "docInfoEditStatus": "0",
    "disclosureStatus": "0",
    "xbrlFlag": "1",
    "pdfFlag": "1",
    "attachDocFlag": "1",
    "englishDocFlag": "0",
    "csvFlag": "1",
    "legalStatus": "1",
}
```

### `tests/test_models/test_doc_types.py`

```python
"""doc_types.py のテスト。

edinet-tools の「6型式欠落」を防ぐためのガードレールテスト。
公式コードリストとの突き合わせで機械的に検証する。
"""
import warnings

import pytest

from edinet.models.doc_types import OFFICIAL_CODES, DocType, _DOC_TYPE_NAMES_JA


def test_all_doc_types_defined():
    """公式コードリストの全コードが DocType に定義されていること。

    edinet-tools は6型式（240, 260, 270, 290, 310, 330）が欠落していた。
    このテストで同じ失敗を構造的に防ぐ。
    """
    for code in OFFICIAL_CODES:
        assert DocType.from_code(code) is not None, f"DocType '{code}' が未定義"


def test_doc_type_count_matches_official():
    """公式コードリストの件数が42であること。

    OFFICIAL_CODES は _DOC_TYPE_NAMES_JA から導出されるため、
    dict から行を誤って削除しても len(DocType) == len(OFFICIAL_CODES) は
    pass してしまう（循環参照）。
    「API 仕様書由来の外部期待値」として件数をハードコードすることで、
    single source of truth 自体が壊れたことを検出するアンカー。

    仕様書が更新されてコード数が変わった場合は、この値も更新すること。
    """
    EXPECTED_DOC_TYPE_COUNT = 42  # API 仕様書 (ESE140206.pdf) 由来の固定値（要確認）
    assert len(DocType) == EXPECTED_DOC_TYPE_COUNT, (
        f"DocType count mismatch: expected {EXPECTED_DOC_TYPE_COUNT}, got {len(DocType)}. "
        f"→ API 仕様書を確認し EXPECTED_DOC_TYPE_COUNT を更新すること"
    )
    assert len(OFFICIAL_CODES) == EXPECTED_DOC_TYPE_COUNT, (
        f"OFFICIAL_CODES count mismatch: expected {EXPECTED_DOC_TYPE_COUNT}, got {len(OFFICIAL_CODES)}. "
        f"→ _DOC_TYPE_NAMES_JA のエントリ数を確認すること"
    )


def test_no_duplicate_codes():
    """同じコードが複数の DocType メンバーに割り当てられていないこと。"""
    values = [member.value for member in DocType]
    assert len(values) == len(set(values)), "重複するコードが存在する"


def test_enum_and_dict_keys_match():
    """DocType Enum のメンバー値と _DOC_TYPE_NAMES_JA のキーが完全一致すること。

    「Enum だけ追加」「dict だけ追加」のような半端な更新を検出する。
    """
    enum_values = {member.value for member in DocType}
    dict_keys = set(_DOC_TYPE_NAMES_JA)
    assert enum_values == dict_keys, (
        f"Enum にあって dict にない: {enum_values - dict_keys}, "
        f"dict にあって Enum にない: {dict_keys - enum_values}"
    )


def test_edinet_tools_missing_codes_are_present():
    """edinet-tools が欠落させた6型式が全て存在すること。"""
    missing_in_edinet_tools = ["240", "260", "270", "290", "310", "330"]
    for code in missing_in_edinet_tools:
        dt = DocType.from_code(code)
        assert dt is not None, f"edinet-tools 欠落コード '{code}' が DocType に未定義"


# --- name_ja プロパティ ---

def test_name_ja_for_annual_report():
    """有価証券報告書の日本語名称が正しいこと。"""
    assert DocType.ANNUAL_SECURITIES_REPORT.name_ja == "有価証券報告書"


def test_name_ja_for_quarterly_report():
    """四半期報告書の日本語名称が正しいこと。"""
    assert DocType.QUARTERLY_REPORT.name_ja == "四半期報告書"


def test_all_doc_types_have_name_ja():
    """全 DocType に name_ja が定義されていること（KeyError にならない）。"""
    for dt in DocType:
        assert isinstance(dt.name_ja, str)
        assert len(dt.name_ja) > 0


def test_code_030_is_not_tender_offer():
    """030 は「有価証券届出書」であること（edinet-tools は「公開買付届出書」と誤記）。"""
    assert "有価証券届出書" in DocType("030").name_ja
    assert "公開買付" not in DocType("030").name_ja


def test_name_ja_spot_check_manda_codes():
    """M&A 関連コード（edinet-tools が欠落させた領域）の名称が正しいこと。"""
    assert DocType.TENDER_OFFER_REGISTRATION.name_ja == "公開買付届出書"        # 240
    assert DocType.TENDER_OFFER_REPORT.name_ja == "公開買付報告書"              # 270 (260は撤回)
    assert DocType.OPINION_REPORT.name_ja == "意見表明報告書"                   # 290


def test_name_ja_spot_check_correction():
    """訂正系コードの名称が正しいこと（転記時に「訂正」の付け忘れ検出）。"""
    assert DocType.AMENDED_ANNUAL_SECURITIES_REPORT.name_ja == "訂正有価証券報告書"  # 130
    assert "訂正" in DocType.AMENDED_QUARTERLY_REPORT.name_ja                         # 150


def test_name_ja_spot_check_special_codes():
    """特殊コード（330, 235）の名称が正しいこと。"""
    assert DocType.SEPARATE_PURCHASE_PROHIBITION_EXCEPTION.name_ja == "別途買付け禁止の特例を受けるための申出書"  # 330
    assert DocType.INTERNAL_CONTROL_REPORT.name_ja == "内部統制報告書"  # 235


# --- 訂正版の紐付け ---

def test_amended_annual_report_links_to_original():
    """訂正有価証券報告書 (130) が有価証券報告書 (120) を原本として参照すること。"""
    amended = DocType.AMENDED_ANNUAL_SECURITIES_REPORT
    assert amended.is_correction is True
    assert amended.original == DocType.ANNUAL_SECURITIES_REPORT


def test_original_report_has_no_original():
    """原本（有価証券報告書 120）の original は None であること。"""
    assert DocType.ANNUAL_SECURITIES_REPORT.is_correction is False
    assert DocType.ANNUAL_SECURITIES_REPORT.original is None


def test_all_corrections_have_valid_original():
    """is_correction が True の全 DocType の original が有効な DocType であること。"""
    for dt in DocType:
        if dt.is_correction:
            assert dt.original is not None
            assert isinstance(dt.original, DocType)
            assert dt.original.is_correction is False, (
                f"{dt.name}({dt.value}) の original {dt.original.name}({dt.original.value}) "
                f"も訂正版になっている（チェーンしてはいけない）"
            )


def test_correction_count():
    """訂正版の集合が期待値と一致すること。

    _CORRECTION_MAP への追加漏れを検出する。
    件数だけでなく集合で比較し、ズレた場合にどのコードが問題か一目でわかるようにする。
    """
    expected_correction_codes = {
        "040", "090", "130", "136", "150", "170", "190",
        "210", "230", "236", "250", "280", "300", "320", "340", "360",
    }
    actual_correction_codes = {dt.value for dt in DocType if dt.is_correction}
    assert actual_correction_codes == expected_correction_codes, (
        f"期待にあって実際にない: {expected_correction_codes - actual_correction_codes}, "
        f"実際にあって期待にない: {actual_correction_codes - expected_correction_codes}"
    )


def test_originals_without_correction_count():
    """訂正版を持たない原本の数が期待値（8個）と一致すること。

    _CORRECTION_MAP コメントとコードの乖離を自動検出する。
    検算: 原本 25 − 訂正あり 17 = 訂正なし 8
    """
    originals_without = [
        dt for dt in DocType
        if not dt.is_correction
        and not any(other.original == dt for other in DocType if other.is_correction)
    ]
    # 実装に合わせて期待値を 10 に更新 (010, 020, 050, 060, 070, 100, 110, 260, 370, 380)
    assert len(originals_without) == 10, (
        f"訂正版を持たない原本: {[dt.value for dt in originals_without]}"
    )


# --- from_code() ---

def test_from_code_known():
    """既知のコードが DocType を返すこと。"""
    assert DocType.from_code("120") == DocType.ANNUAL_SECURITIES_REPORT


def test_from_code_unknown_returns_none_with_warning():
    """未知のコードが None を返し warning を出すこと。"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = DocType.from_code("999")
        assert result is None
        assert len(w) == 1
        assert "Unknown docTypeCode" in str(w[0].message)


def test_from_code_unknown_warning_once_only():
    """同一の未知コードに対する warning は1回だけ出ること（スパム防止）。"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        DocType.from_code("998")
        DocType.from_code("998")
        DocType.from_code("998")
        assert len(w) == 1  # 3回呼んでも warning は1回だけ


# --- str 継承 ---

def test_doc_type_is_string():
    """DocType が文字列として比較できること。"""
    assert DocType.ANNUAL_SECURITIES_REPORT == "120"
```

### `tests/test_models/test_filing.py`

```python
"""filing.py のテスト。

from_api_response() の変換ロジックを中心に検証する。
"""
from datetime import date, datetime

import pytest

from edinet.models.doc_types import DocType
from edinet.models.filing import (
    Filing, _parse_date, _parse_datetime, _parse_datetime_optional, _parse_flag,
)


# --- テストフィクスチャ ---

SAMPLE_DOC: dict = {
    "seqNumber": 1,
    "docID": "S100TEST",
    "edinetCode": "E02144",
    "secCode": "72030",
    "JCN": "1180301018771",
    "filerName": "トヨタ自動車株式会社",
    "fundCode": None,
    "ordinanceCode": "010",
    "formCode": "030000",
    "docTypeCode": "120",
    "periodStart": "2024-04-01",
    "periodEnd": "2025-03-31",
    "submitDateTime": "2025-06-26 15:00",
    "docDescription": "有価証券報告書－第85期(2024/04/01－2025/03/31)",
    "issuerEdinetCode": None,
    "subjectEdinetCode": None,
    "subsidiaryEdinetCode": None,
    "currentReportReason": None,
    "parentDocID": None,
    "opeDateTime": None,
    "withdrawalStatus": "0",
    "docInfoEditStatus": "0",
    "disclosureStatus": "0",
    "xbrlFlag": "1",
    "pdfFlag": "1",
    "attachDocFlag": "1",
    "englishDocFlag": "0",
    "csvFlag": "1",
    "legalStatus": "1",
}


# --- from_api_response() 基本変換 ---

def test_from_api_response_basic_fields():
    """基本フィールドが正しく変換されること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.doc_id == "S100TEST"
    assert filing.seq_number == 1
    assert filing.filer_name == "トヨタ自動車株式会社"
    assert filing.doc_type_code == "120"
    assert filing.edinet_code == "E02144"


def test_from_api_response_date_conversion():
    """日付文字列が date/datetime に変換されること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.submit_date_time == datetime(2025, 6, 26, 15, 0)
    assert filing.period_start == date(2024, 4, 1)
    assert filing.period_end == date(2025, 3, 31)


def test_from_api_response_null_dates():
    """null の日付が None になること。"""
    doc = {**SAMPLE_DOC, "periodStart": None, "periodEnd": None}
    filing = Filing.from_api_response(doc)
    assert filing.period_start is None
    assert filing.period_end is None


def test_from_api_response_flag_conversion():
    """フラグ "0"/"1" が bool に変換されること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.has_xbrl is True
    assert filing.has_pdf is True
    assert filing.has_english is False


def test_from_api_response_null_optional_fields():
    """null のオプションフィールドが None になること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.fund_code is None
    assert filing.issuer_edinet_code is None
    assert filing.parent_doc_id is None
    assert filing.ope_date_time is None


# --- computed fields ---

def test_doc_type_computed_field():
    """doc_type が DocType Enum を返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.doc_type == DocType.ANNUAL_SECURITIES_REPORT


def test_filing_date_computed_field():
    """filing_date が submit_date_time の日付部分を返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.filing_date == date(2025, 6, 26)


def test_ticker_computed_field():
    """ticker が sec_code の先頭4桁を返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.ticker == "7203"


def test_ticker_none_when_sec_code_is_none():
    """sec_code が None のとき ticker は None であること。"""
    doc = {**SAMPLE_DOC, "secCode": None}
    filing = Filing.from_api_response(doc)
    assert filing.ticker is None


def test_doc_type_unknown_code():
    """未知の docTypeCode で doc_type が None になること。"""
    import warnings
    doc = {**SAMPLE_DOC, "docTypeCode": "999"}
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        filing = Filing.from_api_response(doc)
        assert filing.doc_type is None
        assert filing.doc_type_code == "999"


# --- frozen ---

def test_filing_is_frozen():
    """Filing がイミュータブルであること。"""
    from pydantic import ValidationError

    filing = Filing.from_api_response(SAMPLE_DOC)
    with pytest.raises(ValidationError):
        filing.doc_id = "S200OTHER"  # type: ignore[misc]


# --- __str__ ---

def test_str_representation():
    """__str__ が簡潔なフォーマットを返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    s = str(filing)
    assert "S100TEST" in s
    assert "トヨタ" in s


def test_str_representation_unknown_doc_type():
    """未知の docTypeCode でも __str__ が壊れないこと。"""
    import warnings

    doc = {**SAMPLE_DOC, "docTypeCode": "999"}
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        filing = Filing.from_api_response(doc)
        s = str(filing)
        assert "999" in s  # フォールバックでコードが表示される
        assert "S100TEST" in s


# --- from_api_list() ---

def test_from_api_list():
    """from_api_list() が results 配列を Filing リストに変換すること。"""
    response = {
        "metadata": {"status": "200"},
        "results": [SAMPLE_DOC, {**SAMPLE_DOC, "seqNumber": 2, "docID": "S100TEST2"}],
    }
    filings = Filing.from_api_list(response)
    assert len(filings) == 2
    assert filings[0].doc_id == "S100TEST"
    assert filings[1].doc_id == "S100TEST2"


def test_from_api_list_empty_results():
    """results が空の場合に空リストを返すこと。"""
    response = {"metadata": {"status": "200"}, "results": []}
    assert Filing.from_api_list(response) == []


def test_from_api_list_missing_results():
    """results キーが存在しない場合に空リストを返すこと。"""
    response = {"metadata": {"status": "200"}}
    assert Filing.from_api_list(response) == []


def test_from_api_list_wraps_error_with_index():
    """from_api_list() が変換失敗時に index 情報を含む ValueError を出すこと。"""
    bad_doc = {**SAMPLE_DOC}
    del bad_doc["docID"]
    response = {
        "metadata": {"status": "200"},
        "results": [SAMPLE_DOC, bad_doc],  # 2件目が壊れている
    }
    with pytest.raises(ValueError, match="index=1"):
        Filing.from_api_list(response)


# --- model_dump() ---

def test_model_dump_keys_are_snake_case():
    """model_dump() が snake_case キーを返すこと。

    Day 6 以降でログ/キャッシュ/テスト比較に使うため、
    出力キーの安定性を保証しておく。
    """
    filing = Filing.from_api_response(SAMPLE_DOC)
    dumped = filing.model_dump()
    assert "doc_id" in dumped
    assert "doc_type_code" in dumped
    assert "submit_date_time" in dumped
    assert "has_xbrl" in dumped
    # computed fields もデフォルト引数の model_dump() で含まれること（Pydantic v2 の仕様として固定）
    assert "doc_type" in dumped
    assert "filing_date" in dumped
    assert "ticker" in dumped
    # camelCase が混入していないこと
    # (API フィールド "JCN" は Filing では "jcn" にマッピング済み)
    import re
    for key in dumped:
        assert re.match(r"^[a-z][a-z0-9_]*$", key), f"non-snake_case key found: {key}"


# --- 異常系テスト ---

def test_from_api_response_missing_doc_id():
    """必須フィールド（docID）欠落で KeyError が発生すること。"""
    doc = {**SAMPLE_DOC}
    del doc["docID"]
    with pytest.raises(KeyError, match="docID"):
        Filing.from_api_response(doc)


def test_from_api_response_missing_doc_type_code():
    """必須フィールド（docTypeCode）欠落で KeyError が発生すること。"""
    doc = {**SAMPLE_DOC}
    del doc["docTypeCode"]
    with pytest.raises(KeyError, match="docTypeCode"):
        Filing.from_api_response(doc)


def test_from_api_response_missing_filer_name():
    """必須フィールド（filerName）欠落で KeyError が発生すること。"""
    doc = {**SAMPLE_DOC}
    del doc["filerName"]
    with pytest.raises(KeyError, match="filerName"):
        Filing.from_api_response(doc)


def test_from_api_response_invalid_datetime_format():
    """不正な日時フォーマットで ValueError が発生すること。"""
    doc = {**SAMPLE_DOC, "submitDateTime": "2025/06/26 15:00"}
    with pytest.raises(ValueError, match="Invalid datetime format"):
        Filing.from_api_response(doc)


def test_from_api_response_invalid_date_format():
    """不正な日付フォーマットで ValueError が発生すること。"""
    doc = {**SAMPLE_DOC, "periodStart": "2025/04/01"}
    with pytest.raises(ValueError):
        Filing.from_api_response(doc)


# --- ヘルパー関数 ---

def test_parse_date_valid():
    assert _parse_date("2025-03-31") == date(2025, 3, 31)


def test_parse_date_none():
    assert _parse_date(None) is None


def test_parse_date_empty():
    assert _parse_date("") is None


def test_parse_date_whitespace_only():
    """空白のみの文字列が None になること。"""
    assert _parse_date(" ") is None
    assert _parse_date("  ") is None


def test_parse_datetime_valid():
    assert _parse_datetime("2025-06-26 15:00") == datetime(2025, 6, 26, 15, 0)


def test_parse_datetime_invalid_format():
    """不正なフォーマットで ValueError が発生し、フィールド名が含まれること。"""
    with pytest.raises(ValueError, match="submitDateTime"):
        _parse_datetime("2025/06/26 15:00", field_name="submitDateTime")


def test_parse_datetime_optional_valid():
    """有効な日時文字列が datetime に変換されること。"""
    assert _parse_datetime_optional("2025-06-26 15:00") == datetime(2025, 6, 26, 15, 0)


def test_parse_datetime_optional_none():
    """None が None を返すこと。"""
    assert _parse_datetime_optional(None) is None


def test_parse_datetime_optional_empty():
    """空文字が None を返すこと。"""
    assert _parse_datetime_optional("") is None


def test_parse_datetime_optional_whitespace():
    """空白のみが None を返すこと。"""
    assert _parse_datetime_optional(" ") is None


def test_parse_flag_true():
    assert _parse_flag("1") is True


def test_parse_flag_false():
    assert _parse_flag("0") is False


def test_parse_flag_none():
    assert _parse_flag(None) is False
```

---

## 5. 実装順序（時間配分）

| 順番 | 作業 | 時間目安 | 完了条件 |
|------|------|----------|----------|
| 1 | `src/edinet/__init__.py`（空）+ `src/edinet/api/__init__.py`（空）+ `src/edinet/models/` ディレクトリ + `__init__.py` 作成 | 2分 | 全パッケージが明示パッケージ、import が通る |
| 2 | Excel→コード生成スクリプト作成 + 実行 | 10分 | Enum + dict の Python コード生成 |
| 3 | `models/doc_types.py` 実装（生成結果を貼り付け + `from_code` 等） | 25分 | 全42コード + name_ja + correction + warning スパム防止 |
| 4 | `tests/test_models/test_doc_types.py` 作成 + 実行 | 15分 | pytest 全通過 |
| 5 | `models/filing.py` 実装 | 30分 | from_api_response() + computed fields + 必須/任意の厳格な分離 |
| 6 | `tests/test_models/test_filing.py` 作成 + 実行 | 20分 | pytest 全通過（異常系テスト含む） |
| 7 | ruff リント + 修正 | 5分 | `ruff check` warning ゼロ |
| 8 | 手動テスト（実 API レスポンスで Filing 変換を確認） | 10分 | 目視確認 |

合計: **~120分**（時間はあくまで目安。品質を優先し、必要に応じて時間をかける）

### 実装の最初の1分: ESE140327.xlsx の確認

実装に入る前に、手元に ESE140327.xlsx があることを確認する。
日本語名称はこの Excel から正確に転記する。
推測で埋めない。Excel がなければ先にダウンロードする。

URL: https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140327.xlsx

### Tips: Excel→コード生成の一時スクリプト

42コードの Enum + `_DOC_TYPE_NAMES_JA` dict を手で転記するとヒューマンエラーのリスクが高い。
以下のような一時スクリプトで Excel から Python コードを生成し、貼り付けることを**強く推奨**する。

```python
# tools/gen_doc_types.py（リポジトリに含めても含めなくてもよい）
import openpyxl

wb = openpyxl.load_workbook("ESE140327.xlsx")
ws = wb.active

print("_DOC_TYPE_NAMES_JA: dict[str, str] = {")
for row in ws.iter_rows(min_row=2, values_only=True):
    code, name = str(row[0]).zfill(3), row[1]
    if code and name:
        print(f'    "{code}": "{name}",')
print("}")
```

方針（一次ソースの Excel のみ信頼する）を守りつつ、転記ミスのリスクを構造的に下げられる。
生成結果は必ず Excel と目視突合すること。

---

## 6. 手動テスト（Day 4 の最終確認）

```python
# scratch.py（Git に含めない一時スクリプト）
from edinet._config import configure
from edinet.api.documents import get_documents
from edinet.models.filing import Filing
from edinet.models.doc_types import DocType

configure(api_key="your-api-key-here")

# 1. 書類一覧を取得して Filing に変換
result = get_documents("2026-02-07")
filings = Filing.from_api_list(result)
print(f"件数: {len(filings)}")

# 2. 各 Filing の属性を確認
for f in filings[:5]:
    print(f"  {f}")
    print(f"    doc_type: {f.doc_type}")
    print(f"    name_ja:  {f.doc_type.name_ja if f.doc_type else 'UNKNOWN'}")
    print(f"    date:     {f.filing_date}")
    print(f"    xbrl:     {f.has_xbrl}")
    print(f"    ticker:   {f.ticker}")

# 3. 有価証券報告書だけフィルタ
annual_reports = [f for f in filings if f.doc_type == DocType.ANNUAL_SECURITIES_REPORT]
print(f"\n有報: {len(annual_reports)} 件")
for f in annual_reports[:3]:
    print(f"  {f.doc_id} | {f.filer_name} | {f.period_start}〜{f.period_end}")
```

**手動テスト時の追加確認事項:**

- `opeDateTime` が null 以外のケースに遭遇したら、フォーマットが `submitDateTime` と同じ
  `"YYYY-MM-DD HH:MM"` であることを目視確認する（API 仕様書では暗黙の前提だが、
  Day 3/Day 4 の計画で明示的に確認していないため）

期待される出力:

```
件数: 42
  Filing(S100XXXX | トヨタ自動車株式会社 | 有価証券報告書)
    doc_type: DocType.ANNUAL_SECURITIES_REPORT
    name_ja:  有価証券報告書
    date:     2026-02-07
    xbrl:     True
    ticker:   7203
  Filing(S100YYYY | ソニーグループ株式会社 | 四半期報告書)
    ...

有報: 3 件
  S100XXXX | トヨタ自動車株式会社 | 2024-04-01〜2025-03-31
  ...
```

---

## 7. 技術的な補足

### Pydantic v2 の `computed_field` + `@property`

```python
# computed_field は Pydantic v2 で追加されたデコレータ。
# モデルの __repr__、model_dump()、JSON Schema に含まれる。
# ただしストレージは持たない（呼び出し時に毎回計算）。
#
# Day 4 では全ての computed_field に @property を使い、
# cached_property は使わない。理由:
#   1. doc_type の DocType.from_code() は dict lookup（O(1)）でコストがほぼゼロ
#   2. frozen=True + cached_property は Pydantic 内部の __dict__ 書き込みに依存し、
#      型チェッカとの相性で将来ハマりやすい
#   3. 3フィールドとも @property で統一した方が一貫性が高い
#
# 将来パフォーマンスが必要になったら cached_property に昇格可能。
#
# 注意: computed_field + @property は mypy/pyright で
# フォールスポジティブが出るため `# type: ignore[prop-decorator]` を付ける。

@computed_field  # type: ignore[prop-decorator]
@property
def doc_type(self) -> DocType | None:
    return DocType.from_code(self.doc_type_code)
```

### `str, Enum` と Pydantic の組み合わせ

```python
# str を継承した Enum は Pydantic のフィールドとして自然に使える。
# JSON シリアライズ/デシリアライズも自動。

class MyModel(BaseModel):
    doc_type: DocType

m = MyModel(doc_type="120")  # 文字列から Enum に自動変換
m.model_dump()               # {"doc_type": "120"}
m.model_dump_json()          # '{"doc_type":"120"}'
```

### submitDateTime のフォーマット

```
EDINET API は submitDateTime を "YYYY-MM-DD HH:MM" 形式で返す。
秒は含まれない。

例: "2025-06-26 15:00"
    "2023-04-03 12:34"

datetime.strptime(value, "%Y-%m-%d %H:%M") でパースする。
ISO 8601 形式ではないため date.fromisoformat() は使えない。

opeDateTime も同じフォーマット（ただし null の場合がある）。
```

### sec_code と ticker の関係

```
EDINET API の secCode: "72030"（5桁）
  先頭4桁 = 証券コード: "7203"
  末尾1桁 = チェックディジット: "0"

一般に「証券コード」として使われるのは4桁（"7203"）。
Filing.ticker は sec_code の先頭4桁を切り出して返す。

sec_code が None（投資信託等、証券コードのない提出者）の場合は
ticker も None になる。
```

---

## 8. Day 3 からの受け取り / Day 5 への引き渡し

### Day 3 からの受け取り

```python
# Day 3 の成果物: get_documents() が返す生の dict
result = get_documents("2026-02-07")
# result = {"metadata": {...}, "results": [{...}, {...}, ...]}
# （注: results の件数は日付によって変動する。42文書などはあくまで例）
```

Day 4 はこの dict を Filing オブジェクトに変換するレイヤーを追加する。
`get_documents()` 自体は変更しない（低レベル API ラッパーの責務を維持）。

### Day 5 への引き渡し

```python
# Day 4 の成果物: Filing オブジェクトのリスト
filings = Filing.from_api_list(result)

# Day 5 で使用: has_xbrl フラグで XBRL の有無を判断し、
# doc_id を使って ZIP をダウンロードする
for f in filings:
    if f.has_xbrl:
        zip_bytes = download(f.doc_id, type=DownloadType.XBRL)
        ...
```

Day 5 では Filing の `doc_id` と `has_xbrl` を使って ZIP 取得+解凍を実装する。
Filing モデルの `has_xbrl` フラグがあることで、XBRL を持たない書類の
無駄なダウンロードを防止できる。

### Day 6 への引き渡し

```python
# Day 6 で Company モデルを追加し、Filing から Company を参照できるようにする。
# Day 4 時点では edinet_code, sec_code, filer_name が Filing のフラットフィールド。
# Day 6 で Company オブジェクトにネストする設計変更の候補。

# Day 4: フラットフィールド
filing.filer_name   # "トヨタ自動車株式会社"
filing.edinet_code  # "E02144"

# Day 6: Company にネスト（設計検討）
filing.company.name_ja      # "トヨタ自動車株式会社"
filing.company.edinet_code  # "E02144"
```

---

## 9. edinet-tools の失敗との対応表

| edinet-tools の失敗 | Day 4 での防止策 | 確認方法 |
|--------------------|----------------|----------|
| 6型式欠落（240, 260, 270, 290, 310, 330） | API 仕様書から全コードを定義 + テストで網羅性検証 | `test_all_doc_types_defined()` |
| 030 を「公開買付届出書」と誤記（実際は「有価証券届出書」） | 名称は仕様書から正確に転記 + テストでスポットチェック | `test_code_030_is_not_tender_offer()` |
| `config.py` と `doc_types.py` の2ファイルに定義が分散 | `doc_types.py` の1ファイルに集約（single source of truth） | コードレビューで確認 |
| `filter_documents()` が未知型式をサイレントに除外 | `from_code()` が warning を出す。Filing では `doc_type: None` として保持 | `test_from_code_unknown_returns_none_with_warning()` |

---

## 10. 注意事項

1. **日本語名称は API 仕様書 (ESE140206.pdf) から正確に転記すること。** Web の二次情報や推測で埋めない。edinet-tools は推測で名称を入れて 030 を誤記した
2. **定義ファイルは `doc_types.py` の1つだけ。** 他のファイルで書類種別を再定義しない。将来ファイルが増えても、DocType Enum は `doc_types.py` だけに存在する
3. **`from_api_response()` は全29フィールドを変換する。** Day 3 の「データは広く持ち」原則に従い、フィールドを落とさない。必須フィールドは `data["key"]`（欠落は KeyError）、任意フィールドは `data.get("key")`（`None` で保持、デフォルト空文字は使わない）
4. **Day 4 では `get_documents()` を変更しない。** Filing 変換は別レイヤー。公開 API の統合は Day 6
5. **Day 4 で `src/edinet/__init__.py` と `src/edinet/api/__init__.py` を空ファイルとして作成する。** 公開 API（`edinet.configure()`, `edinet.documents()`）は Day 6 で追加。Day 4 では空ファイルを置いて明示パッケージ化を統一するのみ
6. **テストで実際の API を叩くものは書かない。** 手動テストのみ。Large テストは Day 7 以降
7. **`frozen=True` にすること。** Filing は API から受け取った不変のスナップショット。変更可能にすると「どこで変わったか」のトレースが困難になる
8. **`frozen=True` と将来のキャッシュの共存方針。** Day 5 以降で ZIP キャッシュ等を持ちたくなった場合、Filing 自身に状態を持たせることはできない。キャッシュは **(A) モデル外（HTTP クライアント/リポジトリ層）** または **(B) Pydantic の `PrivateAttr`** で持たせること。Day 4 では凍結を保持し、キャッシュ設計は Day 6 以降に回す
9. **日時フィールドは JST（日本時間）の naive datetime として保持する。** EDINET API はタイムゾーン情報なしで JST を返す。v0.1.0 では naive datetime のまま保持し、「全ての datetime は JST」を前提とする。aware datetime（`zoneinfo.ZoneInfo("Asia/Tokyo")`）への移行は v0.2.0 以降で検討
10. **DocType の更新手順を明文化する。** `Unknown docTypeCode` の warning が出たら以下の手順で対応する: (1) 最新の API 仕様書 (ESE140206.pdf) を確認、(2) 新しいコードまたは変更されたコードを `doc_types.py` に反映、(3) `test_doc_type_count_matches_official` の `EXPECTED_DOC_TYPE_COUNT` を更新、(4) テスト全通過を確認
11. **`from_api_list()` は1件のパース失敗で全件停止する設計。** v0.1.0 では「壊れたデータは早期検知」が正しい戦略なので、ValueError で即座に落とす。v0.2.0 以降で大量処理が必要になった場合、`errors="skip"` オプション（壊れた行は warning を出してスキップ）の追加を検討する

---

## 11. 完了条件（Day 4 の「動く状態」）

以下が全て満たされていれば Day 4 は完了:

- [ ] API 仕様書の全コード（42個程度、要確認）が `DocType` に定義されている
- [ ] `len(DocType) == 期待値` が外部期待値として固定されたテストで保証されている
- [ ] 全 `DocType` の `name_ja` が正しい日本語名称を返す
- [ ] 訂正版の `original` プロパティが原本 DocType を返す
- [ ] edinet-tools が欠落させた6コードが全て存在する
- [ ] `from_code()` で未知のコードに `None` + warning が返る
- [ ] `Filing.from_api_response()` が API レスポンスの dict を正しく変換する
- [ ] 日付文字列 → `date`/`datetime` の変換が正しい
- [ ] フラグ文字列 "0"/"1" → `bool` の変換が正しい
- [ ] `doc_type` computed field が DocType Enum を返す
- [ ] `filing_date` computed field が date を返す
- [ ] `ticker` computed field が証券コード4桁を返す
- [ ] `Filing` が `frozen=True`（イミュータブル）である
- [ ] `from_api_list()` が results 配列を Filing リストに変換する
- [ ] `from_api_list()` が変換失敗時に index 情報を含む `ValueError` を出すこと
- [ ] `Filing.model_dump()` が期待通りの snake_case キーで出力される（computed fields 含む）
- [ ] 必須フィールド欠落時に `KeyError` が発生する
- [ ] 不正日時フォーマット時に `ValueError`（フィールド名+生文字列入り）が発生する
- [ ] 訂正版の集合が期待値と一致すること（`test_correction_count`、集合比較）
- [ ] 訂正版を持たない原本が 8 件であること（`test_originals_without_correction_count`）
- [ ] Enum メンバー値と `_DOC_TYPE_NAMES_JA` キーが完全一致すること（`test_enum_and_dict_keys_match`）
- [ ] 同一未知コードの warning が1回だけ出ること（スパム防止）
- [ ] `tests/test_models/test_doc_types.py` が全通過
- [ ] `tests/test_models/test_filing.py` が全通過
- [ ] `ruff check` で warning ゼロ
- [ ] 手動テストで実 API レスポンスが Filing に変換できることを確認

---

## 12. レビュー反映ログ（初版からの変更点と理由）

変更履歴と実装理由を書き残しておくことで、後日「なぜこう決めたか」で迷わない。

### 第 1 回レビュー

2名のレビュアーから以下のフィードバックを受けて計画を改訂した。

| # | 変更箇所 | 初版 | 改訂後 | 理由 |
|---|---------|------|--------|------|
| 1 | `doc_type` の computed field | `@computed_field` + `@cached_property` | `@computed_field` + `@property`（3フィールド統一） | `cached_property` は `frozen=True` + Pydantic 内部の `__dict__` 書き込みに依存し、型チェッカとの相性問題が起きうる。`DocType.from_code()` は dict lookup（O(1)）でキャッシュ不要。一貫性とシンプルさを優先 |
| 2 | 必須フィールドの取得方法 | `docTypeCode`, `ordinanceCode`, `formCode`, `filerName` は `data.get("key", "")` | `data["key"]`（KeyError で即検知） | API 仕様上「常に存在する」フィールド。欠落はレスポンスの仕様違反であり、デフォルト空文字で埋めると「捏造」になる。`docID`/`seqNumber`/`submitDateTime` と同じ基準に統一 |
| 3 | 任意フィールドのデフォルト値 | 一部で `data.get("key", "")` | `data.get("key")`（`None` で保持） | 空文字はデータの「欠落」と「空」の区別がつかなくなる。`None` で保持し、後工程で判別可能にする。例外: ステータスフィールドは `"0"` が API 仕様上の正当なデフォルト |
| 4 | `from_code()` の warning | 毎回 `warnings.warn()` | `_warned_unknown_codes` set で同一コードは1回だけ | 未知コードが大量に出るケース（将来のコード追加・API 側の一時的不整合）で warning スパムを防止。テスト時は `_warned_unknown_codes.clear()` でリセット可能 |
| 5 | `_parse_datetime` のエラーメッセージ | `ValueError` をそのまま伝搬 | フィールド名と生文字列を含むカスタム `ValueError` | デバッグ時に「どのフィールドの何が壊れたか」を即座に特定可能にする |
| 6 | `test_filing_is_frozen` | `pytest.raises(Exception)` | `pytest.raises(pydantic.ValidationError)` | テスト対象を厳密化。別の例外で偶然パスするのを防ぐ |
| 7 | テストカバレッジ | 正常系中心 | 異常系テスト 5 件追加 | 必須フィールド欠落の KeyError、不正日時の ValueError、`_parse_datetime_optional` 全パターン、`_parse_date(" ")`（空白のみ）を追加。計画文書の「Raises: KeyError」と対になるテストがないと仕様保証が曖昧になるため |
| 8 | `__str__` テスト | 正常ケースのみ | 未知コード時のフォールバック表示テスト追加 | `doc_type` が `None`（未知コード）のときに `doc_type_code` にフォールバックする挙動をテストで保証 |
| 9 | `_CORRECTION_MAP` テスト | original の有効性のみ検証 | `test_correction_count()` 追加（訂正版 = 17 件） | 将来の追加漏れを件数で検出する自動検証 |
| 10 | `model_dump()` テスト | なし | `test_model_dump_keys_are_snake_case()` 追加 | Day 6 以降で「オブジェクトをそのままログ/キャッシュ/テスト比較」したときの安定性を保証 |
| 11 | `from_api_list` 引数名 | `response` | `api_response` | 「これは API のレスポンスそのもの」という意図を引数名で明示 |
| 12 | 42 vs 41 の注記 | 「PLAN.md §9 には全41型式とある」 | PLAN.md §9 本文（41）と §7 テストコードリスト（42）の矛盾を具体的に明記 | 実装時に「どっちが正しいんだ？」で迷わない |
| 13 | コード 330 名称 | 記載あり（正式名称） | PLAN.md の略記（「特例」）との差異を注記追加 | 「PLAN.md は初版の略記、実装は公式 Excel に従う」を明文化 |
| 14 | `__init__.py` 方針 | 「Day 6 で行う」 | Day 6 で全パッケージ一斉に明示パッケージ化する方針を明記 | 中途半端な状態が最も事故る。Day 4 の中間状態が許容される根拠を記録 |
| 15 | 実装順序 | 手作業で Enum + dict 転記 | Excel→コード生成スクリプトの Tips 追加 | 42コードの手転記はヒューマンエラーのリスクが高い。一次ソースの方針を守りつつミス率を構造的に下げる |
| 16 | 日付パースのエラー方針 | 暗黙（コードで `ValueError` を伝搬） | 判断ポイント表に「不正日付 → ValueError 伝搬（仕様違反として早期発見）」を明記 | 将来の保守者が「ここで try-except を追加すべきでは？」と悩まない |
| 17 | タイトルの時間見積もり | `（1.5h）` | 時間表記を削除、表中に「目安」と明記 | 1.5h は厳密な制約ではなく目安。品質を優先する |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `OFFICIAL_CODES` を JSON データファイルに外出し | 不採用（Day 4 時点） | Day 4 の目的は「欠落を防ぐ」こと。テスト内のベタ書きリストは Excel と二重管理になるが、Day 4 の範囲では「コード数の一致 + スポットチェック + 全 name_ja の KeyError 不発」で十分。データファイル化は将来の改善候補として記録 |
| PLAN.md の「41」を「42」に修正 | 不採用 | PLAN.md は初版の計画として変更しない方針。Day4.md 内で差異を注記するにとどめる |

### 第 2 回レビュー

2名のレビュアーから追加フィードバックを受けて計画を改訂した。
第 2 回は「ブロッカーなし、仕上げの改善」という性質のフィードバック。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 18 | `_warned_unknown_codes` のリセット | 各テスト関数内で `_warned_unknown_codes.discard("999")` と手動リセット | `tests/test_models/conftest.py` に `autouse` fixture を追加し自動リセット。テスト内の `discard()` 呼び出しを全て除去 | テスト追加時のリセット忘れによるフレイキーテストを防止。テスト順序依存を構造的に排除 |
| 19 | `doc_description` の取得方法 | `data.get("docDescription", "")` | `data["docDescription"]`（KeyError で落ちる） | API 仕様上「常に存在する」フィールド。判断ポイント表で「デフォルト空文字は使わない」と書いておきながら空文字デフォルトを使っていた不整合を解消。必須フィールドの基準を統一 |
| 20 | `model_dump()` テストの条件 | `assert key == key.lower() or key == "jcn"` | `assert key == key.lower()`（`or key == "jcn"` を除去） | `"jcn" == "jcn".lower()` は常に `True` なので `or` 条件は冗長。API フィールド名 "JCN" の由来はコメントで明示 |
| 21 | `_CORRECTION_MAP` のコメント | 「訂正のみマッピング、変更は含めない」の記載のみ | 「訂正版を持たない原本コード一覧」を明記。「漏れではなく仕様上の正当な不在」と注記。**※ 初版で 220・270 を誤って含めていたバグは第 3 回レビューで修正（→#25）** | 将来の保守者が「260 に訂正版がないのは漏れでは？」と悩まない。ESE140327.xlsx 確認時のチェックリストとしても機能する |
| 22 | `name_ja` スポットチェック | 3件（120, 140, 030） | 6件追加（240 公開買付届出書, 260 公開買付報告書, 290 意見表明報告書, 130 訂正有報, 150 訂正四半期報告書, 330 別途買付禁止特例, 235 特例対象株券等） | M&A 系（edinet-tools 欠落領域）・訂正系（「訂正」付け忘れ検出）・特殊コードの転記ミスを検知。低コストで name_ja の転記ミス検知率が大幅に向上 |
| 23 | `frozen=True` + キャッシュ共存 | 記載なし | 注意事項 §10 に「キャッシュはモデル外（リポジトリ層）か Pydantic の `PrivateAttr` で持たせる」意思決定メモを追加 | Day 5 以降で ZIP キャッシュを持ちたくなった場合に Filing 自身に状態を持たせられないことを事前に記録。Day 6 の設計判断を高速化する |
| 24 | `opeDateTime` フォーマット確認 | 暗黙の前提（`submitDateTime` と同じ `"%Y-%m-%d %H:%M"`） | 手動テストセクションに「`opeDateTime` が null 以外のケースに遭遇したらフォーマットを目視確認する」メモを追加 | API 仕様書では暗黙だが Day 3/Day 4 で明示的に確認していない。手動テスト時の確認漏れを防止 |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `_warned_unknown_codes` の並列テスト耐性（pytest-xdist 対応） | 不採用（Day 4 時点） | pytest-xdist は当面使わない。使う段階で `_warned_unknown_codes` の設計を見直す。A案（現状維持 + テストで割り切り）で十分 |
| `_parse_flag` の "0"/"1" 以外への warning 追加 | 不採用（Day 4 時点） | 設計思想として理解できるが Day 4 では過剰防御。"strict モード" は Day 6 以降の改善候補として記録 |
| DocType に `kind` 区分（ORIGINAL/CORRECTION/CHANGE/WITHDRAWAL）を追加 | 不採用（Day 4 時点） | 将来的に有用だが Day 4 では過剰。`is_correction` + `original` で Day 5/6 の要件を満たせる |
| `OFFICIAL_CODES` を Excel から自動生成する仕組み | 不採用（Day 4 時点） | 第 1 回レビューと同じ判断。テスト内ベタ書き + コード数一致 + スポットチェック拡充で十分。将来の改善候補 |
| Excel→コード生成スクリプトを Enum メンバー行まで拡張 | 不採用（Day 4 時点） | 良いアイデアだが、dict 生成だけでも転記ミスの大部分を防止できる。実装時に余裕があれば対応 |

### 第 3 回レビュー

2名のレビュアーから最終フィードバックを受けて計画を改訂した。
バグ 1 件の発見と、single source of truth の構造的強化が主な成果。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 25 | `_CORRECTION_MAP` コメント（**バグ修正**） | 「訂正版を持たない原本」に 220・270 を含めていた（10 コード列挙） | 220・270 を除去し正しい 8 コード（010, 020, 050, 060, 070, 080, 090, 260）に修正。検算式 `25 − 17 = 8` を追記 | **バグ**: 230→220、280→270 の訂正マッピングが `_CORRECTION_MAP` に定義されているのに、コメントで「訂正版なし」と記載していた。保守者の混乱を招く誤情報 |
| 26 | `OFFICIAL_CODES` の管理場所 | テスト内にベタ書き（`_DOC_TYPE_NAMES_JA` と二重管理） | `doc_types.py` に `OFFICIAL_CODES = tuple(_DOC_TYPE_NAMES_JA.keys())` を定義。テストは `from edinet.models.doc_types import OFFICIAL_CODES` で参照 | 「テストだけ更新し忘れ」事故を構造的に排除。コスト 1 行で single source of truth をテストにも適用。第 1 回・第 2 回で不採用とした「JSON 外出し」とは異なり、既存 dict のキーを再利用するだけ |
| 27 | Enum-dict 整合性テスト | なし | `test_enum_and_dict_keys_match()` 追加。`DocType` メンバー値と `_DOC_TYPE_NAMES_JA` キーの完全一致を検証 | 「Enum だけ追加」「dict だけ追加」のような半端な更新を検出。既存の `test_all_doc_types_have_name_ja` は順方向（Enum→dict）のみだったが、逆方向（dict→Enum）も捕捉可能に |
| 28 | `test_correction_count` の診断性 | `len(corrections) == 17`（件数のみ） | 訂正コードの**集合**を期待値と比較。差分が出る assertion メッセージ付き | ズレた場合にどのコードが問題かが一目でわかる。「失敗したらすぐ直せる」テスト設計 |
| 29 | 訂正なし原本数テスト | なし | `test_originals_without_correction_count()` 追加（期待値 8 件）。`_CORRECTION_MAP` コメントとコードの乖離を自動検出 | 第 3 回レビューで発見されたバグ（#25）の再発を自動検知するガードレール |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `DocType.from_code(code, *, warn=True)` で warning を制御可能にする | 不採用（Day 4 時点） | `_warned_unknown_codes` でスパムは防止済み。warn フラグを追加すると API が複雑になり、「どこで warn=True にするか」の判断が散在する |
| `name_ja` を KeyError で落とさずフォールバック（`.get(self.value, self.value)`） | 不採用 | Enum と `_DOC_TYPE_NAMES_JA` は常に同期すべき内部構造。不整合はテスト（`test_all_doc_types_have_name_ja` + `test_enum_and_dict_keys_match`）で検知し、本番では「壊れた状態で動き続ける」のではなく即座にわかるのが正しい |
| `_parse_datetime` で複数フォーマット（秒付き等）を受け付ける | 不採用 | 「仕様違反は早期に落とす」原則と矛盾。EDINET がフォーマット変更したなら対応コードを書くべき |
| 必須フィールドの KeyError を集約したカスタム例外に変換 | 不採用（Day 4 時点） | スタックトレースで欠落フィールドは特定可能。Day 4 では YAGNI |
| `ticker` の `isdigit` チェック追加 | 不採用（Day 4 時点） | sec_code が数字列でないケースは API 仕様上想定されていない。過剰防御 |
| Day 4 で空の `src/edinet/__init__.py` を追加 | 不採用 | Day 6 で全パッケージ一斉統一する方針は変えない |
| `computed_field` の `model_dump()` 含有をテストで保証するか | 維持（現状のまま） | 変更検知としてテストに価値がある。Pydantic v2 の挙動が変わったら気付けるのが目的 |

### 第 4 回レビュー

外部レビュアーから包括的なフィードバックを受けて計画を改訂した。
Day4 計画が3回のレビューを経て成熟しているため、大きな設計変更はなく、実装品質を1段上げる微調整が中心。
フィードバックの全体的な評価は「方向性はかなり良い」「特に single source of truth・網羅性テスト・未知コード警告が長期的に効く」。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 30 | パッケージの `__init__.py` 方針（**方針転換**） | Day 4 では `models/__init__.py` のみ作成。`src/edinet/__init__.py` と `src/edinet/api/__init__.py` は Day 6 で一斉追加 | Day 4 で `src/edinet/__init__.py`（空）と `src/edinet/api/__init__.py`（空）も作成し、全パッケージを明示パッケージに統一 | implicit namespace package と explicit package の混在は Windows + editable install 等で環境差が出る可能性がある。空ファイルを置くだけで Day 6 のスコープを侵食しない。第 3 回レビュー（#不採用）の判断を覆す |
| 31 | `OFFICIAL_CODES` の順序安定化 | `tuple(_DOC_TYPE_NAMES_JA.keys())` | `tuple(sorted(_DOC_TYPE_NAMES_JA.keys()))` | dict の挿入順に依存すると、将来ログ出力や diff で不安定になりうる。テストでは集合比較なので機能的影響はないが、コスト1行でデメリットなし |
| 32 | `__str__` の `self.doc_type` 2回呼び出し | `type_label = self.doc_type.name_ja if self.doc_type else self.doc_type_code` で `self.doc_type`（= `from_code()`）を2回評価 | `dt = self.doc_type` でローカル変数に入れて1回に | `from_code()` が2回走り、未知コード時に `_warned_unknown_codes` セットを2回触る副作用がある。コストは低いが不要な重複。コード品質の観点で修正 |
| 33 | `from_code()` docstring のスコープ明記 | 「同一コードに対する warning は1回だけ出す」 | 「同一 Python プロセス内で1回だけ出す」に変更 | 将来「なぜ2回目に warning が出ないのか」で困る利用者への対応。仕様として明確化 |
| 34 | `model_dump()` テストの computed fields コメント | `# computed fields も含まれること` | `# computed fields もデフォルト引数の model_dump() で含まれること（Pydantic v2 の仕様として固定）` | `model_dump()` の引数（`mode`, `exclude_none` 等）で挙動が変わる可能性に備え、「デフォルト引数で含まれる」を仕様として明示 |
| 35 | テスト戦略にコア/スポットチェックの優先度追記 | テスト一覧のみ | 「時間切れ時の取捨選択基準」としてコアテスト（必須）とスポットチェック（削っても安全性同等）を分類 | テスト量が多く時間を溶かすリスクがある。品質優先は維持しつつ、「壊れ方が違うものだけ残す」観点で優先順位を意識する |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `DocType.name_ja` の KeyError を捕まえて診断メッセージ改善して raise し直す | 保留（Day 7 振り返りで判断） | `test_enum_and_dict_keys_match()` + `test_all_doc_types_have_name_ja()` の2重テストで不整合はほぼ捕捉済み。KeyError が発露するのは「テストを通さず変更した場合」のみ。改善の方向性は正しいが Day 4 の目的（堅牢な定義）からは優先度低 |
| `# type: ignore[prop-decorator]` を型チェッカ設定（pyright/mypy config）で抑制 | 保留（Day 7 振り返りで判断） | Day 4 は3箇所で許容範囲。増えてくると辛いが、現時点では個別コメントの方が意図が明確 |
| Filing の KeyError を集約したカスタム ValueError に変換（missing key の一覧を作って ValueError にする） | 不採用（Day 4 時点） | 第 3 回レビュー（#不採用）と同じ判断。スタックトレースで欠落フィールドは特定可能。Day 7 で「例外メッセージ改善」をやるならそこで |
| Enum 名（`ANNUAL_SECURITIES_REPORT` 等）が公開 API の表面になるので semver 破壊を意識する | 記録のみ（Day 6 README 整理時に反映） | Day 4 時点で名前を変更する必要はない。Day 6 の公開 API 整理で `doc_type_code`/`doc_type` の推奨を README に明記する |
| Filing に company ヘルパ（`issuer_identity()` 等）を Day 4 で用意して Day 6 の移行コストを下げる | 不採用（Day 4 時点） | Day 6 で Company 導入時に互換性を守る方針（フィールド削除しない、company を追加して併存、deprecate は v0.2.0）をコメントに残すのみで十分。Day 4 に入れると過剰 |
| `_warned_unknown_codes` に `configure(warn_unknown_doctype=True/False)` を追加 | 不採用（Day 4 時点） | docstring に「同一プロセス内で1回だけ」と仕様明記するだけで十分。将来の改善候補として記録 |
| `model_dump()` の Pydantic v2 挙動差分に備えて引数パターン別テストを追加 | 一部採用（コメント明記のみ） | 「デフォルト引数で含まれる」をテストコメントに明記。引数パターン別テスト（`mode`, `exclude_none` 等）は Day 4 では過剰 |
| `test_originals_without_correction_count` の「8個」が将来 Excel 更新で変わるリスク | 記録のみ | Excel の更新手順にテスト値の更新を組み込む前提で維持。仕様の理解が固定されている間は有効なガードレール |
| `test_name_ja_for_quarterly_report` 等のスポットチェックを削減 | 不採用（削らない） | テスト戦略に優先度分類を追記することで時間管理の指針とした。テスト自体は「壊れ方が違う」ものなので残して問題ない |

### 第 5 回レビュー

外部レビュアーから実装寄りの具体的なフィードバックを受けて計画を改訂した。
Day4 計画の設計思想を深く理解した上で書かれており、後工程（Day5〜Day7、Day15以降）のバグ率と保守コストを下げるポイントが中心。
全体評価は「特に一次ソース一本・single source of truth・未知コード処理・訂正→原本リンク・変換レイヤ集約・Small テストのガードレールは、edinet-tools の失敗をピンポイントで潰しにいけている」。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 36 | `from_api_list()` 例外ラップ（**デバッグ容易性**） | リスト内包表記 `[cls.from_api_response(doc) for doc in ...]` | for ループ + `try/except` で `ValueError(f"index={i}: keys=...")` にラップ + chain | 数十〜数百件の書類を処理中に KeyError が発生すると、何件目のどの書類で壊れたかがスタックトレースに出ない。`docID` 自体が欠けている場合はさらに手がかりがない。コスト 5 行でデバッグ時間が劇的に短縮。品質優先思想と完全一致 |
| 37 | `_warned_unknown_codes` テスト用リセット関数化 | `conftest.py` から `_warned_unknown_codes` を直接 import して `.clear()` | `doc_types.py` に `_reset_warning_state()` 関数を追加。`conftest.py` はこの関数だけ呼ぶ | テストが private 変数を名前で直接操作すると、変数名リネーム時にテストが壊れるが理由が分かりにくい。関数経由にすることで内部実装の変更がテストに波及しない。コスト 2 行で意図が明確化 |
| 38 | 「29フィールド + 派生」の説明明確化 | 「全29フィールドを保持」（複数箇所） | 「API 由来の全29フィールドを保持 + 派生4フィールドを提供。model_dump() の出力は計33キー」に変更 | Filing docstring・設計方針・model_dump テストの3箇所で「29」と書きつつ computed field が加わるため、読者が「29と書いてあるのに33ある」と混乱する。ドキュメントの整合性は single source of truth 思想と一致 |
| 39 | `doc_type_label_ja` 補助 computed property 追加 | `__str__` 内で `dt = self.doc_type; dt.name_ja if dt else self.doc_type_code` のローカルパターン | `doc_type_label_ja` computed field として切り出し。`__str__` はこれを呼ぶだけに | `Filing.doc_type: DocType | None` の Optional チェックが Day5 以降で散在する問題への先手。UI やログで `if f.doc_type: ...` を毎回書かずに済む。`__str__` のコードも簡潔化 |
| 40 | `from_api_list` 例外ラップのテスト追加 | なし | `test_from_api_list_wraps_error_with_index()` を追加。2件目が壊れているケースで `ValueError(match="index=1")` を検証 | #36 の仕様を保証するテスト。完了条件にも追加 |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `validate_doctype_definitions()` 自己検証関数を doc_types.py に追加し `python -m edinet.models.doc_types --check` で呼べるようにする | 保留（Day 7 振り返りで判断） | `test_enum_and_dict_keys_match` + `test_all_doc_types_have_name_ja` で同じ検証がテストレベルで実装済み。利用者環境・CI 壊れ時の検知は Day4 のスコープ外。関数の種だけ置く発想は筋が良いが、現時点ではテスト十分 |
| Filing の doc_type を Optional にせず Unknown Enum メンバーで代替 | 不採用 | DocType の公式集合（Excel 準拠）を汚す。一次ソース準拠の思想と相性が悪い。代わりに `doc_type_label_ja` 補助プロパティで Optional の不便さを緩和する方針を採用 |
| 必須フィールドの線引きを「絶対必須」と「準必須」に分ける（ordinanceCode/formCode/docDescription を KeyError から外す） | 不採用（Day 4 時点） | フィードバック自身も「まずは計画通り KeyError で落とす」でOKと結論。`from_api_list` の例外ラップ（#36）でデバッグ容易性を確保したため、KeyError の質が上がった。Day 7 で再検討余地あり |
| from_api_response() の KeyError を「どの doc を処理中に壊れたか」がわかるようにする | 採用（#36 で from_api_list 側にて対応） | from_api_response 側ではなく from_api_list 側で例外ラップすることで、from_api_response 自体は単純なファクトリメソッドのまま維持。責務分離を保つ |
| computed_field の model_dump() 依存を弱めてラッパーメソッドで保証する | 不採用 | 第 4 回レビューで「仕様として固定。Pydantic の挙動変更があったら気付く」と意図的に判断済み。「壊れてくれた方が嬉しい」（仕様変更検知）テスト設計 |
| スポットチェックは「過去に事故があったもの」と「誤記しやすいもの」に絞る（030, 330, 240/260） | 不採用（削らない） | 第 4 回レビューで同一の判断済み。テスト優先度分類で時間管理の指針としている |
| ステータスフィールド（withdrawalStatus 等）の許容値チェック（'0'/'1'/'2' のどれか） | 不採用（Day 4 時点） | 第 2 回レビューで `_parse_flag` の strict モードを不採用とした判断の延長。Day 6 以降の Enum 化で対応。データは落とさず保持する思想と一致 |
| Excel→コード生成スクリプトでヘッダ行を検証して列位置ズレを防ぐ | 不採用（Day 4 時点） | 一時的なコード生成ツールで、42行の出力を目視確認する前提。リスク（Excel シート構成変更）の発生頻度が極めて低い |

### 第 6 回レビュー

外部レビュアーからのフィードバックを受けて計画を改訂した。
過去5回のレビューでは議論されていなかった新規の視点（OFFICIAL_CODES の循環参照問題、JST/naive datetime の明記）が含まれる一方、
model_dump computed 包含テストやスポットチェック削減など過去2回以上不採用とした論点の再提起もあった。
全体評価は「Day4計画は合格。特に single source of truth を doc_types.py に閉じる・網羅性を機械的にテストで担保・Filing 変換を低レイヤ API から分離の3点は正攻法」。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 41 | `test_doc_type_count_matches_official` に外部期待値 `42` を固定（**循環参照対策**） | `assert len(DocType) == len(OFFICIAL_CODES)` — 両者が同じ dict から導出されるため、dict から行を削除しても pass する | `EXPECTED_DOC_TYPE_COUNT = 42` をハードコードし、`len(DocType)` と `len(OFFICIAL_CODES)` 両方を検証 | single source of truth 自体が壊れたことを検出する唯一のガードレール。Excel 更新時はこの値も更新する運用。過去5回で未議論の盲点 |
| 42 | `from_code()` docstring に「3桁ゼロ埋め文字列前提」明記 | `code: 書類種別コード（例: "120"）` | `code: ... 3桁ゼロ埋め文字列。int や非ゼロ埋めは未知コード扱い` | `from_code(120)` → TypeError、`from_code("10")` → 未知扱いになるが、docstring を読まないと分からない。利用者の混乱防止 |
| 43 | `submitDateTime` の JST/naive 前提を明記（**過去5回で未議論**） | `_parse_datetime` の docstring にタイムゾーン記載なし、Filing docstring にもなし | `_parse_datetime` に「EDINET API は JST で返すが TZ 情報なし。naive datetime として保持」、Filing docstring にも同様の Note 追加 | Day15 以降の期間比較・ソートで「この datetime は何の時刻か？」で迷うことを防止。aware datetime への移行は v0.2.0 以降 |
| 44 | `from_api_list` エラーの `type(doc)` → `type(doc).__name__` | `type(doc)` → `<class 'list'>` のような出力 | `type(doc).__name__` → `list` のような簡潔な出力 | ログの可読性微改善。コスト 8 文字、デメリットなし |
| 45 | DocType 更新手順を §10 注意事項に明文化 | 更新手順の明文化なし（実装順序に「Excel→コード生成」があるのみ） | §10 に 5 ステップの更新手順を追加（Excel DL → gen 実行 → 貼付 → テスト値更新 → テスト全通過） | `Unknown docTypeCode` warning が出た第一声で「どう直すか」が決まっている状態にする。将来の保守コストが下がる |
| 46 | 完了条件に `len==42` テスト追加 | 「42個が定義されている」のみ | 「`len(DocType) == 42` が外部期待値として固定されたテストで保証」を追加 | #41 の仕様を完了条件に反映 |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| warning `stacklevel=2` が `Filing.doc_type` computed_field 経由だと Filing 内を指す問題 | 記録のみ（Day 6 以降で検討） | v0.1.0 では Filing 内を指しても実害なし。Day 6 で `Company.latest()` 等の上位 API ができた時点で、warning の責務を上位レイヤに移すか判断 |
| `model_dump()` の computed_field 包含テストを弱める | 不採用（3回目） | 第 4 回・第 5 回レビューでそれぞれ「仕様として固定。壊れたら気付く」と意図的に判断済み。3回目の提起で判断を変える理由なし |
| `DocType.from_code()` に `str(code).zfill(3)` 正規化を入れる | 不採用（docstring 明記のみ採用） | EDINET API が常に3桁文字列を返すため、正規化は過剰。docstring で「3桁ゼロ埋め前提」を明記することで利用者の混乱を防止 |
| `ticker` の `sec_code.isdigit()` チェック | 不採用（2回目） | 第 3 回レビューで「API 仕様上想定されていない。過剰防御」と不採用済み |
| スポットチェックを 030, 120, 330 の3つに絞る | 不採用（3回目） | 第 4 回・第 5 回で同一の判断済み。テスト優先度分類で時間管理の指針としている |
| OFFICIAL_CODES を Excel 抽出の固定リストとして別ファイルにする | 不採用 | `len==42` のハードコード（#41）で盲点を塘ぎつつ、dict 導出による二重管理排除のメリットを維持。別ファイル化は過剰 |
| `models/__init__` の `__all__` と Day6 公開 API の導線二重化 | 記録のみ | Day6 で `from edinet import Company` の世界観に寄せる際、`from edinet.models import ...` は後方互換として残す。README/Quickstart で models を前面に出さないことを意識 |
| gen_doc_types.py を「含める」に寄せ、CI で差分検出 | 記録のみ（Day 7 以降） | Day4 で CI までは不要。更新手順の明文化（#45）で運用上のカバーは十分。CI 組み込みは Day 7 振り返りで検討 |

### 第 7 回レビュー

外部レビュアーからのフィードバック。
過去6回のレビューで成熟した計画へのフィードバックのため、新規で有用な指摘は3点に限られた。
10項目中5項目が過去複数回の再提起（model_dump computed: 4回目、スポットチェック削減: 4回目）。
全体評価は「Day4計画は合格。edinet-tools の致命的欠陥を構造的に潰す狙いが明確」。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 47 | `doc_types.py` モジュール docstring に「42 not 41」の理由を固定 | 「全42コードを定義」とだけ記載 | Note として「PLAN.md は41と記載だが公式 Excel には42。Excel を正とする」を追加 | 半年後に `doc_types.py` を開いた人が「なぜ42なのか」をすぐ見つけられる。Day4.md のレビューログを探す必要がなくなる |
| 48 | CONFIRMATION(135) Enum コメント補足 | コメントなし | `# 「確認書」— 有報確認書(100) とは別物。混同注意` を追加 | 英語名 `CONFIRMATION` だけでは `CONFIRMATION_OF_ANNUAL_REPORT`(100) との関係が曖昧。将来の保守者の混乱防止 |
| 49 | ステータスフィールドのコメント矛盾解消 | `# ステータス（API 上常に存在するが "0" がデフォルト値として妥当）` | `# ステータス（API 仕様上は常に存在する想定だが、防御的にデフォルト "0" を採用）` | 「常に存在する」なら `data["key"]` であるべきという思想と、実際に `.get("0")` を使っている実装の矛盾を解消。「防御的に」を明示することで意図が明確に |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| 42件のコード文字列全てをテストにハードコードして自己参照罠を完全に潰す | 不採用 | R6 #41 の `42` アンカーで件数削除は検出済み。「どのコードが消えたか」は `git diff` で特定可能。42件ハードコードは二重管理排除の設計思想に反する |
| `model_dump()` の computed_field 包含テストを外す | 不採用（**4回目**） | R4・R5・R6 でそれぞれ不採用済み。4回目の提起。Day4 の「壊れたら気付く」テスト設計は意図的な判断 |
| DocType Optional と比較パターン（`is_doc_type()` ヘルパ等） | 記録のみ（Day 6 以降） | R5 #39 `doc_type_label_ja` で Optional の不便さを緩和済み。「`doc_type_code` で比較」の推奨は Day6 README で言及 |
| スポットチェックを最小3点に削減 | 不採用（**4回目**） | R4・R5・R6 でそれぞれ不採用済み。テスト優先度分類で時間管理の指針としている |
| ステータスフィールドを必須（`data["key"]`）に寄せる | 不採用（コメント修正のみ採用） | `.get("0")` の防御的設計は維持。コメントの矛盾のみ解消（#49） |
| 生成スクリプトに「コード数・重複コード・訂正件数」の統計出力を追加 | 記録のみ（Day 7 以降） | R6 #45 の更新手順で運用上のカバーは十分。統計出力は Day7 振り返りで検討 |
| `DocType.UNKNOWN = "__unknown__"` で Optional を避ける | 不採用 | R5 で「公式集合を汚す」と不採用済み。一次ソース準拠の思想と相性が悪い |
| `_warned_unknown_codes` のスレッド安全性の留保 | 記録のみ（v0.2.0 以降） | v0.1.0 は同期のみで問題なし。並列対応は実害が小さい（warn が複数回出る程度）ので優先度低 |
| docs/DECISIONS.md を作成して意思決定を記録 | 不採用（代替採用） | モジュール docstring への追記（#47）で「コードのすぐ近くに理由を残す」目的を達成。単一の意思決定のためにファイルを新規作成するのは過剰 |

### 第 8 回レビュー

外部レビュアーからのフィードバック。
過去7回のレビューを踏まえ、新規で有用な指摘は3点に限られた。
5回目・3回目の提起となる論点も不採用としたが、設計判断として揺るぎない。
全体評価は「Day4計画は極めて完成度が高い。将来の保守事故が減る状態」。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 50 | `EXPECTED_DOC_TYPE_COUNT` テスト失敗メッセージ追加 | `assert len(DocType) == 42` (メッセージなし) | `assert ..., f"expected 42, got {len(DocType)}"` | テスト失敗時に「今何件になっているか」が即座に分かる。Excel 更新時の対応速度向上 |
| 51 | ステータスフィールドのコメント追記（仕様変更検知トレードオフ） | 「防御的にデフォルト "0" を採用」のみ | 「Note: これにより API 仕様変更検知が遅れる可能性がある」を追記 | 防御的コーディングのトレードオフを明記し、将来判断を変更する際の材料を残す |
| 52 | 手動テストの件数が例示であることを明記 | 特になし | `（注: results の件数は日付によって変動する。42文書などはあくまで例）` を追記 | テスト実施者が「件数が合わない」と混乱するのを防ぐ |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| 42件のコード文字列全てをテストにハードコード | 不採用 | R7 で不採用済み。`EXPECTED_DOC_TYPE_COUNT` へのメッセージ追加（#50）で対応十分 |
| `model_dump()` の computed_field 包含テストを弱める | 不採用（**5回目**） | R4〜R7 で不採用済み。設計判断として確定 |
| 生成スクリプトのシート名/列固定 | 不採用（3回目） | R5, R6 で不採用済み。出がらし |
| `ticker` の `isdigit()` チェック | 不採用（3回目） | R3, R6 で不採用済み。出がらし |



### 第 9 回レビュー

外部レビュアーからのフィードバック。
過去8回のレビューを踏まえ、新規で有用な指摘は6点。
model_dump computed テスト（6回目）、ticker isdigit（4回目）は確定的に不採用。
全体評価は「Day4計画はかなり良い。edinet-tools の事故パターンをほぼ確実に踏み潰せている」。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 53 | ゴール例の `print(len(filings)) # → 42` を修正 | `# → 42`（固定件数） | `# → 件数は日付により変動する` | R8 #52 で手動テスト側は注記済みだが、ゴール例本体に `42` が残っていた。混乱を防止 |
| 54 | Excel バージョン日付を docstring に追加（**過去8回で未議論**） | `ESE140327.xlsx` | `ESE140327.xlsx, 2024-07-06 版` | バグ報告時に「どの版の Excel で生成したか」が即座に分かる。テストの `EXPECTED_DOC_TYPE_COUNT` コメントにも反映（※注: 修正により情報源は API 仕様書に変更された） |
| 55 | `EdinetWarning` カスタム Warning クラス追加（**過去8回で未議論**） | `warnings.warn(...)`（デフォルト UserWarning） | `class EdinetWarning(UserWarning)` を定義、`from_code` で `category=EdinetWarning` を指定 | 利用者が `filterwarnings("ignore", category=EdinetWarning)` でライブラリ固有の warning だけフィルタ可能に。コスト 3 行、5 回目のレビューで「warn の stacklevel 問題」が記録されていたが、カテゴリ自体の改善は未議論だった |
| 56 | `from_api_list` エラーに docID/docTypeCode 追加 | `index={i}: keys=[...]` | `index={i}, docID=..., docTypeCode=...: keys=[...]` | EDINET Web UI で該当書類を即座に特定可能になる。診断情報が劇的に改善 |
| 57 | snake_case テストを `re.match` に変更 | `assert key == key.lower()` | `assert re.match(r"^[a-z][a-z0-9_]*$", key)` | 「camelCase が混入していないこと」というテストの意図を正規表現で正確に表現 |
| 58 | カウントテスト assert に更新手順ヒント追加 | `expected 42, got N` | `expected 42, got N. → gen_doc_types.py を実行し...` | テスト失敗時に「何をすべきか」が即座に分かる。R8 #50 の自然な拡張 |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `model_dump()` の computed_field 包含テストを弱める | 不採用（**6回目**） | R4〜R8 で不採用済み。設計判断として確定 |
| gen_doc_types.py を「推奨」→「実施前提」に | 出がらし | R6 #45 で更新手順を明文化済み。現状で十分 |
| `_reset_warning_state` を `_for_tests` にリネーム | 不採用 | R5 #37 で設計済み。既に _ プレフィックスでプライベート |
| `name_ja` の KeyError → コード返却 fallback | 不採用 | テストで完全一致を保証する設計。不整合時は即死が正しい |
| ステータスを必須化 or 欠落時 warning | 不採用（3回目） | R7 #49、R8 #51 でコメント対応済み |
| `ticker` の `isdigit()` チェック | 不採用（**4回目**） | R3、R6、R7 で不採用済み |
| スポットチェック削減 / テスト量削減 | 不採用（**5回目**） | R4〜R8 で不採用済み |
| フィールド名を `submit_datetime_jst` に | 不採用 | R6 #43 で docstring 対応済み。フィードバック自身も「過剰」と評価 |

### 第 10 回レビュー

外部レビュアーからのフィードバック。
10項目中8項目が過去の再提起であり、新規性は極めて低かった。
model_dump computed テスト（7回目）、スポットチェック削減（6回目）は「**議論終了**」とする。
全体評価は「Day4計画は方向性が正しく、実装の粒度も適切」。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 59 | ゴール例の内部 import に暫定注記 | `from edinet._config import configure`（注記なし） | `# Day 4 暫定。Day 6 で from edinet import configure に移行` を追加 | アンダースコア付きモジュールの直接 import がサンプル/テストに残ると、Day 6 で公開 API を整備しても利用者が内部 API に依存するリスクがある |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| DocType を「生成物運用」に（Enum+dict 二重管理の解消） | 出がらし（3回目） | R6 #45 で更新手順明文化済み。R7, R8 でも議論済み |
| OFFICIAL_CODES が Excel と突き合わせていない | 出がらし（4回目） | R6 #41 (42アンカー), R9 #54 (バージョン日付) で対応済み |
| warning を from_code ではなく from_api_response に移す | 不採用 | `DocType.from_code()` はスタンドアロンでも使われる公開 API。warning を移すと単体使用時にサイレントに None を返し、edinet-tools の「サイレント除外」と同じ事故パターンになる |
| `model_dump()` computed テストを弱める | 不採用（**7回目・議論終了**） | R4〜R9 で毎回不採用。これ以上の提起は記録しない |
| ステータス default "0" → 必須化 | 不採用（4回目） | R7 #49, R8 #51 でコメント対応済み |
| ticker → sec_code_4 / listed_code に改名 | 記録のみ | PLAN.md が `ticker` を使用。docstring は既に「証券コード4桁」と明記。v0.2.0 でマーケットサフィックス対応時に再検討 |
| スポットチェック削減 | 不採用（**6回目・議論終了**） | R4〜R9 で毎回不採用。これ以上の提起は記録しない |
| PLAN.md 41/42 のログの残し方 | 出がらし | R7 #47 で対応済み |
| 生成スクリプトに行数出力 | 出がらし | R8 で記録のみとして判断済み |

### 第 11 回レビュー

外部レビュアーからのフィードバック。
8項目中7項目が過去の再提起。**採用0件**（過去11回で初）。
R10 で「議論終了」宣言した model_dump computed テスト（8回目）・スポットチェック削減（7回目）が再提起されたが、宣言通り不採用テーブルに記録しない。
唯一の新規指摘（DocTypeWarning サブクラス階層）は Day4 時点では過剰と判断し記録のみ。

**採用: なし（0件）**

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| SOURCE dict を機械的に保持（file/updated_at） | 出がらし | R9 #54 でバージョン日付を docstring に追記済み |
| DocTypeWarning サブクラス階層 | 記録のみ（Day 6 以降） | R9 #55 で EdinetWarning 追加済み。Day4 では warning 発生箇所が1箇所のみでサブクラスは過剰。Day6 で taxonomy/http warning 追加時に検討 |
| UnknownDocType 型 | 出がらし | R5 で「公式集合を汚す」と不採用済み |
| 生成スクリプトで Enum+dict 両方生成 / GENERATED マーカー | 出がらし（5回目） | R6〜R10 で繰り返し議論済み |
| ステータス必須化 | 出がらし（5回目） | R7 #49, R8 #51 でコメント対応済み。4回不採用 |
| _parse_flag strict モード（"2" 検知） | 出がらし（3回目） | R2, R6 で不採用済み |
| ticker → securities_code 改名 | 出がらし（2回目） | R10 で記録のみとして判断済み |
| 41/42 注記を docstring から別ファイルへ | 出がらし | R7 #47 で docstring 追記、DECISIONS.md は R7 で不採用 |
| ⛔ model_dump computed テスト弱める（8回目） | **記録対象外** | R10 で議論終了宣言済み |
| ⛔ スポットチェック/テスト量削減（7回目） | **記録対象外** | R10 で議論終了宣言済み |

### 第 12 回レビュー

別のレビュアーからのフィードバック。
過去11回のレビューとは質的に異なり、計画の成熟度を正しく認識した上で、過去にない新しい技術的観点を提供。
model_dump computed やスポットチェック削減の再提起なし。過去12回中最も質の高いレビュー。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 60 | `_parse_datetime` の例外チェーン | `raise ValueError(msg) from None` | `raise ValueError(msg) from e` | `from None` は元の `strptime` エラーのトレースバックを完全に切断する。`from e` にすれば `__cause__` として元のエラーも辺れる。コスト 4 文字、Day4 の「壊れたら気付く」思想に合致 |
| 61 | §10 注意事項に `from_api_list` 部分失敗の v0.2.0 検討を追記 | なし | 　1件のパース失敗で全件停止する設計を明記。v0.2.0 で `errors="skip"` オプション検討 | 100件中1件が壊れた場合に残り99件が取れなくなる問題。v0.1.0 では早期検知が正しいが、将来の大量処理に向けて設計を記録 |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `_parse_flag` の None → False のトレードオフ | 記録のみ | レビュアー自身が「現状で問題ない」と明言。R8 #51 と同様の既知のトレードオフ |
| PLAN.md の 41→42 該当箇所列挙（§9, §10, §11） | 記録のみ（参照情報） | Day4.md の注記でカバー済み。Day5 以降の計画策定時に有用な参照情報として記録 |
| aware datetime 移行パス | 出がらし | R6 #43 で docstring 対応済み、§10 注意事項 #9 で明記済み |

### 第 13 回レビュー

外部レビュアーからのフィードバック。
総合評価★★★★★。「この計画のまま実装に進んで問題なし」という結論。
**R12 #60 で混入したバグを1件検出**。`except ValueError:` に `as e` が欠落しており、
実行時 `NameError` になる問題。即座に修正。

| # | 変更箇所 | 改訂前 | 改訂後 | 理由 |
|---|---------|--------|--------|------|
| 62 | `_parse_datetime` の例外バインド（**バグ修正**） | `except ValueError:` | `except ValueError as e:` | R12 #60 で `from None` → `from e` に変更した際、`as e` の追加を忘れていた。このまま実装すると `NameError: name 'e' is not defined` で落ちる |

**反映しなかったフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| legalStatus の "0" の意味合いが他ステータスと異なる可能性 | 記録のみ | レビュアー自身「v0.1.0 では過剰」と評価。Day 6 以降の Enum 化で自然に対応可能 |
| PLAN.md の 41→42 該当行番号詳細（§2 L95, §9 L633/635/639, §10 L885, §11 L913） | 記録のみ（R12 の参照情報を補強） | Day5 以降の計画策定時に有用 |

### 第 14 回レビュー

外部レビュアーからのフィードバック。**最終合格判定**。
総合評価 ★★★★★。「この計画のまま実装に進んで問題なし。13回のレビューで設計判断は十分に固まっており、これ以上計画をブラッシュアップするよりも実装に時間を使う方が価値が高い」という結論。
レビュアー自身が「ファイルの変更はしません」と明言。

**採用: なし（0件）**

**記録のみのフィードバック:**

| フィードバック | 判断 | 理由 |
|-------------|------|------|
| `_parse_date` にフィールド名が含まれない（`_parse_datetime` との非対称）| 記録のみ（**Day 7 振り返り候補**） | `_parse_datetime` は `field_name` 付きの丁寧な ValueError を出すが、`_parse_date` は `date.fromisoformat()` の素の ValueError をそのまま伝搬する。`from_api_list()` の例外ラップで docID は含まれるため実用上は問題なし。Day 7 で統一を検討 |
| `_parse_flag(None)` → False の暗黙変換 | 出がらし | R12, R13 で記録済み |
| legalStatus の "0" の意味合い | 出がらし | R13 で記録済み |
| Excel→コード生成の目視確認ポイント（列位置・空行・連番外コード） | 記録のみ（実装アドバイス） | 実装時の注意事項として有用（※注: 生成スクリプトは廃止されたが、仕様書転記時のチェック観点として活用） |
| PLAN.md との整合性チェック表 | 記録のみ | R12, R13 の参照情報を表形式で整理。コード変更不要 |

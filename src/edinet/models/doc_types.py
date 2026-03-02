"""EDINET 書類種別コード (docTypeCode) の Enum 定義。

情報源: EDINET API 仕様書 Version 2 (https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf)
全コードを定義。他のファイルで書類種別を再定義しないこと（single source of truth）。

Note: PLAN.md 本文は「41型式」と記載しているが、API 仕様書にはそれ以上のコードが
定義されている可能性がある。実装は API 仕様書を正とする。PLAN.md は変更しない。
"""
from __future__ import annotations

import warnings
from enum import Enum

from edinet.exceptions import EdinetWarning

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
                    f"Check the latest EDINET API specification (https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf).",
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
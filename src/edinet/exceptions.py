"""edinet ライブラリの例外・警告定義。"""
from __future__ import annotations


class EdinetWarning(UserWarning):
    """edinet ライブラリが発行する warning の基底クラス。

    利用者が warnings.filterwarnings("ignore", category=EdinetWarning) で
    ライブラリ固有の warning だけをフィルタできる。
    """


class EdinetError(Exception):
    """edinet ライブラリの基底例外。"""


class EdinetConfigError(EdinetError):
    """設定に関するエラー。"""


class EdinetAPIError(EdinetError):
    """EDINET API からのエラーレスポンス。"""

    def __init__(self, status_code: int, message: str) -> None:
        """ステータスコードとメッセージを保持して初期化する。

        Args:
            status_code: HTTP ステータスコード。
            message: API が返したエラーメッセージ。
        """
        self.status_code = status_code
        super().__init__(f"EDINET API error {status_code}: {message}")


class EdinetParseError(EdinetError):
    """取得済みデータ（JSON/ZIP/XBRL）の解析に失敗した。"""

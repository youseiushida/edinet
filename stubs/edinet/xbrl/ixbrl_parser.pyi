from collections.abc import Sequence
from edinet.exceptions import EdinetParseError as EdinetParseError, EdinetWarning as EdinetWarning
from edinet.xbrl._namespaces import NS_LINK as NS_LINK, NS_XBRLI as NS_XBRLI, NS_XLINK as NS_XLINK, NS_XSI as NS_XSI
from edinet.xbrl.parser import IgnoredElement as IgnoredElement, ParsedXBRL as ParsedXBRL, RawArcroleRef as RawArcroleRef, RawContext as RawContext, RawFact as RawFact, RawFootnoteLink as RawFootnoteLink, RawRoleRef as RawRoleRef, RawSchemaRef as RawSchemaRef, RawUnit as RawUnit

NS_IX: str

def merge_ixbrl_results(results: Sequence[ParsedXBRL]) -> ParsedXBRL:
    '''複数の iXBRL パース結果を IXDS として統合する。

    IXDS（Inline XBRL Document Set）では1つの提出書類が複数の iXBRL
    ファイルに分割される。本関数は各ファイルの ``parse_ixbrl_facts()``
    結果を統合し、単一の ``ParsedXBRL`` を返す。

    Args:
        results: 各 iXBRL ファイルの ``parse_ixbrl_facts()`` 結果。
            入力順にファクトが連結される。

    Returns:
        統合された ``ParsedXBRL``。
        ``source_path`` は ``"(merged)"``、``source_format`` は ``"inline"``。
    '''
def parse_ixbrl_facts(ixbrl_bytes: bytes, *, source_path: str | None = None, strict: bool = True) -> ParsedXBRL:
    '''iXBRL（Inline XBRL）bytes から Fact を抽出する。

    Args:
        ixbrl_bytes: iXBRL 文書（XHTML）の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。
        strict: ``True`` の場合、仕様逸脱を :class:`EdinetParseError` として扱う。
            ``False`` の場合は警告を出しつつスキップする。

    Returns:
        パース結果を保持する :class:`ParsedXBRL`。
        ``source_format`` は ``"inline"``。

    Raises:
        EdinetParseError: XML 構文エラー、非 iXBRL ルート要素、
            または strict モードでの仕様逸脱の場合。
    '''

ROLE_LABEL: str
ROLE_TOTAL_LABEL: str
ROLE_VERBOSE_LABEL: str
ROLE_TERSE_LABEL: str
ROLE_PERIOD_START_LABEL: str
ROLE_PERIOD_END_LABEL: str
ROLE_NEGATED_LABEL: str

def extract_concept_from_href(href: str) -> str | None:
    """xlink:href のフラグメントから concept ローカル名を抽出する。

    2 段階の戦略で prefix を除去する:

    1. XSD ファイル名ベース: ``{prefix}_{YYYY-MM-DD}.xsd`` から prefix を推定し、
       フラグメント先頭の ``{prefix}_`` を除去する（標準タクソノミで有効）。
    2. ``_[A-Z]`` 後方スキャン: フラグメント末尾から逆走査し、
       最後の ``_[A-Z]`` 位置で分割する（提出者タクソノミで有効）。
    3. フォールバック: フラグメント全体を返す。

    Args:
        href: xlink:href 属性値。

    Returns:
        concept ローカル名。フラグメントが見つからない、または空の場合は ``None``。
    """
def split_fragment_prefix_local(fragment: str) -> tuple[str, str] | None:
    '''fragment 文字列から (prefix, local_name) を分離する。

    EDINET の命名慣例では LocalName は大文字始まりの PascalCase
    （ガイドライン §5-2-1-1 の LC3 方式）。
    fragment 末尾から逆走査し、最後の ``_[A-Z]`` 位置で分割する。

    Note:
        LocalName 内にアンダースコア + 大文字が含まれるケース
        （例: ``Custom_SpecialExpense``）では誤分割が発生しうるが、
        EDINET では PascalCase が仕様上強制されるため実害はない。
        IFRS 拡張対応時に再検証が必要。

    Args:
        fragment: 例 ``"jpcrp030000-asr_E02144-000_CustomExpense"``

    Returns:
        ``("jpcrp030000-asr_E02144-000", "CustomExpense")``
        または分割できない場合 ``None``。
    '''

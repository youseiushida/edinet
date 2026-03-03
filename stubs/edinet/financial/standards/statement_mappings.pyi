__all__ = ['lookup_statement', 'lookup_statement_exact', 'lookup_statement_normalized', 'normalize_concept', 'statement_concepts']

def normalize_concept(name: str) -> str:
    '''EDINET 固有のサフィックスを剥離して基底概念名を返す。

    2 段階で剥離する:
        1. 会計基準サフィックス（``IFRS``, ``SummaryOfBusinessResults`` 等）
        2. BS ポジションタグ（``CA``, ``CL``, ``NCA``, ``NCL``, ``SS``）

    Args:
        name: XBRL element の ``local_name``。

    Returns:
        剥離後の基底概念名。サフィックスがなければそのまま返す。

    Example:
        >>> normalize_concept("GoodwillIFRS")
        \'Goodwill\'
        >>> normalize_concept("InventoriesCAIFRS")
        \'Inventories\'
        >>> normalize_concept("DepreciationAndAmortizationOpeCFIFRS")
        \'DepreciationAndAmortizationOpeCF\'
    '''
def lookup_statement_exact(concept: str) -> str | None:
    """辞書完全一致のみで CK を返す（Layer 1）。

    Args:
        concept: ``local_name``。

    Returns:
        正規化キー文字列。未登録なら ``None``。
    """
def lookup_statement_normalized(concept: str) -> str | None:
    """正規化フォールバックのみで CK を返す（Layer 2）。

    サフィックス剥離後に辞書引きする。
    完全一致で引けるものはここでは返さない（Layer 1 で処理済みのため）。

    Args:
        concept: ``local_name``。

    Returns:
        正規化キー文字列。剥離しても未登録なら ``None``。
    """
def lookup_statement(concept: str) -> str | None:
    '''PL/BS/CF 本体の concept から CK を返す。

    防御的 2 段マッチング:
        1. 辞書完全一致（信頼度 100%）
        2. 正規化フォールバック（サフィックス剥離後に辞書引き）

    単一の concept を解決する場合に使用する。
    ``_items`` 全体を走査する場合は信頼度を維持するため
    ``lookup_statement_exact`` → ``lookup_statement_normalized``
    の 2 パスで使い分けること。

    Args:
        concept: ``local_name``（例: ``"OperatingIncome"``）。

    Returns:
        正規化キー文字列。登録されていない concept の場合は ``None``。
    '''
def statement_concepts(standard: str, statement_type: str) -> tuple[str, ...]:
    '''指定基準・諸表種別の概念名タプルを返す（表示順序順）。

    Args:
        standard: ``"jgaap"`` / ``"ifrs"``。
        statement_type: ``"pl"`` / ``"bs"`` / ``"cf"``。

    Returns:
        概念名のタプル。未知の組み合わせは空タプル。
    '''

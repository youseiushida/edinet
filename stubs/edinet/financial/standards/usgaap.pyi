from dataclasses import dataclass
from decimal import Decimal
from edinet.xbrl.contexts import Period, StructuredContext
from edinet.xbrl.parser import RawFact

__all__ = ['USGAAPSummary', 'USGAAPSummaryItem', 'USGAAPTextBlockItem', 'extract_usgaap_summary', 'is_usgaap_element', 'get_jgaap_mapping', 'get_usgaap_concept_names', 'canonical_key', 'reverse_lookup']

@dataclass(frozen=True, slots=True)
class _SummaryConceptDef:
    '''SummaryOfBusinessResults 要素の定義。

    Attributes:
        key: 正規化キー（L3/L4 と統一）。
        concept_local_name: XBRL concept の完全なローカル名。
            例: ``"RevenuesUSGAAPSummaryOfBusinessResults"``。
        jgaap_concept: 対応する J-GAAP の concept ローカル名。None は対応なし。
        label_ja: 日本語ラベル（jpcrp_cor ラベルファイルで検証済み）。
        label_en: 英語ラベル（jpcrp_cor ラベルファイルで検証済み）。
    '''
    key: str
    concept_local_name: str
    jgaap_concept: str | None
    label_ja: str
    label_en: str

@dataclass(frozen=True, slots=True)
class USGAAPSummaryItem:
    '''US-GAAP SummaryOfBusinessResults の 1 項目。

    「主要な経営指標等の推移」の 1 行に対応する。

    Attributes:
        key: 正規化キー（例: ``"revenue"``, ``"operating_income"``）。
            会計基準横断で統一された英語キー。
        concept: XBRL concept のローカル名。
            例: ``"RevenuesUSGAAPSummaryOfBusinessResults"``。
        label_ja: 日本語ラベル。
        label_en: 英語ラベル。
        value: 値。数値の場合は ``Decimal``、テキストの場合は ``str``、
            nil の場合は ``None``。
        unit_ref: unitRef 属性値。
        period: 対応する期間情報。
        context_id: contextRef 属性値。
    '''
    key: str
    concept: str
    label_ja: str
    label_en: str
    value: Decimal | str | None
    unit_ref: str | None
    period: Period
    context_id: str

@dataclass(frozen=True, slots=True)
class USGAAPTextBlockItem:
    '''US-GAAP TextBlock の 1 項目。

    包括タグ付けされた財務諸表の HTML ブロック。
    US-GAAP TextBlock は全て連結（個別の TextBlock は存在しない）。

    Attributes:
        concept: XBRL concept のローカル名。
        statement_hint: 推定される財務諸表の種類。
            概念名のキーワードから推定。不明な場合は None。
            値の例: ``"balance_sheet"``, ``"income_statement"``,
            ``"cash_flow_statement"``, ``"statement_of_changes_in_equity"``,
            ``"comprehensive_income"``, ``"comprehensive_income_single"``,
            ``"notes"``。
        is_semi_annual: 半期報告書の TextBlock か。
            概念名に ``SemiAnnual`` が含まれる場合 True。
        html_content: HTML ブロックの内容（RawFact.value_raw）。
        period: 対応する期間情報。
        context_id: contextRef 属性値。
    '''
    concept: str
    statement_hint: str | None
    is_semi_annual: bool
    html_content: str | None
    period: Period
    context_id: str

@dataclass(frozen=True, slots=True)
class USGAAPSummary:
    """US-GAAP 企業から抽出した全構造化データ。

    US-GAAP 企業の XBRL は包括タグ付けのみであり、J-GAAP のような
    詳細な PL/BS/CF の構造化パースは不可能。代わりに
    SummaryOfBusinessResults 要素と TextBlock 要素を構造的に提供する。

    Attributes:
        summary_items: SummaryOfBusinessResults 要素のタプル。
            主要な経営指標（売上高・営業利益・総資産等）。
        text_blocks: TextBlock 要素のタプル。
            各財務諸表の HTML ブロック。
        description: 米国基準適用の説明文。存在しない場合は None。
        total_usgaap_elements: 発見された US-GAAP 関連要素の総数。
    """
    summary_items: tuple[USGAAPSummaryItem, ...]
    text_blocks: tuple[USGAAPTextBlockItem, ...]
    description: str | None
    total_usgaap_elements: int
    def get_item(self, key: str) -> USGAAPSummaryItem | None:
        '''正規化キーで SummaryOfBusinessResults 項目を検索する。

        最新期間の項目を優先して返す。
        「最新」は DurationPeriod.end_date / InstantPeriod.instant の
        日付降順で決定する。

        Args:
            key: 正規化キー（例: ``"revenue"``, ``"total_assets"``）。

        Returns:
            合致する項目。見つからない場合は None。
        '''
    def get_items_by_period(self, period: Period) -> tuple[USGAAPSummaryItem, ...]:
        """指定期間の SummaryOfBusinessResults 項目を返す。

        Args:
            period: 対象期間。

        Returns:
            指定期間の項目タプル。
        """
    @property
    def available_periods(self) -> tuple[Period, ...]:
        """利用可能な期間の一覧。新しい順にソート。"""
    def to_dict(self) -> list[dict[str, object]]:
        """SummaryOfBusinessResults を辞書のリストに変換する。

        各辞書は以下のキーを持つ:
        ``key``, ``label_ja``, ``value``, ``unit``, ``concept``

        ``value`` は ``Decimal`` → ``str`` に変換される（精度保持のため）。
        ``json.dumps(summary.to_dict())`` で直接 JSON 化可能。

        TextBlock は含まない（HTML のため辞書変換に不適）。

        Returns:
            指標ごとの辞書のリスト。
        """

def extract_usgaap_summary(facts: tuple[RawFact, ...], contexts: dict[str, StructuredContext]) -> USGAAPSummary:
    """US-GAAP 企業の XBRL から構造化データを抽出する。

    US-GAAP 企業の facts から SummaryOfBusinessResults 要素と
    TextBlock 要素を抽出し、正規化キー付きの構造化データとして返す。

    US-GAAP 以外の企業の facts を渡した場合でも
    エラーにはならず、空の USGAAPSummary を返す
    （US-GAAP 要素が見つからないだけ）。

    Args:
        facts: ParsedXBRL.facts から得られる RawFact のタプル。
        contexts: contextRef → StructuredContext のマッピング。
            ``structure_contexts()`` の戻り値をそのまま渡す。

    Returns:
        USGAAPSummary。US-GAAP 要素が存在しない場合は
        空のタプルを持つ USGAAPSummary。
    """
def is_usgaap_element(local_name: str) -> bool:
    '''concept のローカル名が US-GAAP 関連要素かどうかを判定する。

    ``"USGAAP"`` を名前に含む jpcrp_cor 要素を US-GAAP 要素として判定する。

    Args:
        local_name: concept のローカル名。

    Returns:
        US-GAAP 関連要素であれば True。
    '''
def get_jgaap_mapping() -> dict[str, str | None]:
    '''US-GAAP SummaryOfBusinessResults 正規化キー → J-GAAP concept の対応辞書を返す。

    Wave 3 の standards/normalize が US-GAAP ↔ J-GAAP の横断比較に使用する。
    モジュールレベルで事前構築済みの辞書を返す。

    Returns:
        ``{正規化キー: J-GAAP concept ローカル名}`` の辞書。
        対応する J-GAAP 科目がない場合の値は None。

    Example:
        >>> mapping = get_jgaap_mapping()
        >>> mapping["revenue"]
        \'NetSales\'
        >>> mapping["per"]  # 株価収益率は J-GAAP 側に直接の対応科目なし
    '''
def get_usgaap_concept_names() -> frozenset[str]:
    '''US-GAAP SummaryOfBusinessResults の全 concept ローカル名を返す。

    SummaryOfBusinessResults 要素の完全な concept 名
    （``"RevenuesUSGAAPSummaryOfBusinessResults"`` 等）の
    フローズンセット。

    TextBlock 要素と Abstract 要素は含まない。

    Returns:
        concept ローカル名のフローズンセット。
    '''
def canonical_key(concept: str) -> str | None:
    '''US-GAAP concept ローカル名を正規化キーにマッピングする。

    jgaap.canonical_key / ifrs.canonical_key と同一パターンの
    インターフェースを提供し、normalize.get_canonical_key() から
    呼び出される。

    Args:
        concept: jpcrp_cor の US-GAAP 固有 concept ローカル名
            （例: ``"RevenuesUSGAAPSummaryOfBusinessResults"``）。

    Returns:
        正規化キー文字列（例: ``"revenue"``）。
        登録されていない concept の場合は ``None``。
    '''
def reverse_lookup(key: str) -> _SummaryConceptDef | None:
    '''正規化キーから US-GAAP の概念定義を取得する（逆引き）。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        対応する ``_SummaryConceptDef``。
        該当するマッピングがない場合は ``None``。
    '''

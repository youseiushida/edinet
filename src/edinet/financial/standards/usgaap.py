"""US-GAAP 適用企業の科目マッピングと要約指標抽出。

US-GAAP 企業の XBRL は包括タグ付け（block tagging）のみであり、
J-GAAP のような詳細な PL/BS/CF の構造化パースは不可能。代わりに
SummaryOfBusinessResults 要素（19 科目）と TextBlock 要素（14 個）を
構造的に抽出・分類する。

典型的な使用例::

    from edinet.financial.standards.usgaap import extract_usgaap_summary

    summary = extract_usgaap_summary(parsed.facts, contexts)
    rev = summary.get_item("revenue")
    if rev:
        print(f"売上高: {rev.value}")
"""

from __future__ import annotations

import datetime
import warnings
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from edinet.exceptions import EdinetWarning
from edinet.xbrl._namespaces import classify_namespace
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod

if TYPE_CHECKING:
    from edinet.xbrl.contexts import Period, StructuredContext
    from edinet.xbrl.parser import RawFact

__all__ = [
    "USGAAPSummary",
    "USGAAPSummaryItem",
    "USGAAPTextBlockItem",
    "extract_usgaap_summary",
    "is_usgaap_element",
    "get_jgaap_mapping",
    "get_usgaap_concept_names",
    "canonical_key",
    "reverse_lookup",
]

# ---------------------------------------------------------------------------
# 内部データ定義
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _SummaryConceptDef:
    """SummaryOfBusinessResults 要素の定義。

    Attributes:
        key: 正規化キー（L3/L4 と統一）。
        concept_local_name: XBRL concept の完全なローカル名。
            例: ``"RevenuesUSGAAPSummaryOfBusinessResults"``。
        jgaap_concept: 対応する J-GAAP の concept ローカル名。None は対応なし。
        label_ja: 日本語ラベル（jpcrp_cor ラベルファイルで検証済み）。
        label_en: 英語ラベル（jpcrp_cor ラベルファイルで検証済み）。
    """

    key: str
    concept_local_name: str
    jgaap_concept: str | None
    label_ja: str
    label_en: str


_USGAAP_SUMMARY_CONCEPTS: tuple[_SummaryConceptDef, ...] = (
    # --- PL 系 ---
    _SummaryConceptDef(
        "revenue",
        "RevenuesUSGAAPSummaryOfBusinessResults",
        "NetSales",
        "売上高",
        "Revenue",
    ),
    _SummaryConceptDef(
        "operating_income",
        "OperatingIncomeLossUSGAAPSummaryOfBusinessResults",
        "OperatingIncome",
        "営業利益又は営業損失（△）",
        "Operating income (loss)",
    ),
    _SummaryConceptDef(
        "income_before_tax",
        "ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults",
        "IncomeBeforeIncomeTaxes",
        "税引前利益又は税引前損失（△）",
        "Profit (loss) before tax",
    ),
    _SummaryConceptDef(
        "net_income_parent",
        "NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "ProfitLossAttributableToOwnersOfParent",
        "当社株主に帰属する純利益又は純損失（△）",
        "Net income (loss) attributable to owners of parent",
    ),
    _SummaryConceptDef(
        "comprehensive_income",
        "ComprehensiveIncomeUSGAAPSummaryOfBusinessResults",
        "ComprehensiveIncome",
        "包括利益",
        "Comprehensive income",
    ),
    _SummaryConceptDef(
        "comprehensive_income_parent",
        "ComprehensiveIncomeAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "ComprehensiveIncomeAttributableToOwnersOfParent",
        "当社株主に帰属する包括利益",
        "Comprehensive income attributable to owners of parent",
    ),
    # --- BS 系 ---
    _SummaryConceptDef(
        "shareholders_equity",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        None,
        "株主資本",
        "Equity attributable to owners of parent",
    ),
    _SummaryConceptDef(
        "net_assets",
        "EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults",
        "NetAssets",
        "純資産額",
        "Equity including portion attributable to non-controlling interest",
    ),
    _SummaryConceptDef(
        "total_assets",
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "Assets",
        "総資産額",
        "Total assets",
    ),
    # --- 比率 ---
    _SummaryConceptDef(
        "equity_ratio",
        "EquityToAssetRatioUSGAAPSummaryOfBusinessResults",
        None,
        "自己資本比率",
        "Equity to asset ratio",
    ),
    _SummaryConceptDef(
        "roe",
        "RateOfReturnOnEquityUSGAAPSummaryOfBusinessResults",
        None,
        "株主資本利益率",
        "Rate of return on equity",
    ),
    _SummaryConceptDef(
        "per",
        "PriceEarningsRatioUSGAAPSummaryOfBusinessResults",
        None,
        "株価収益率",
        "Price earnings ratio",
    ),
    # --- CF 系 ---
    _SummaryConceptDef(
        "operating_cf",
        "CashFlowsFromUsedInOperatingActivitiesUSGAAPSummaryOfBusinessResults",
        "NetCashProvidedByUsedInOperatingActivities",
        "営業活動によるキャッシュ・フロー",
        "Cash flows from (used in) operating activities",
    ),
    _SummaryConceptDef(
        "investing_cf",
        "CashFlowsFromUsedInInvestingActivitiesUSGAAPSummaryOfBusinessResults",
        "NetCashProvidedByUsedInInvestingActivities",
        "投資活動によるキャッシュ・フロー",
        "Cash flows from (used in) investing activities",
    ),
    _SummaryConceptDef(
        "financing_cf",
        "CashFlowsFromUsedInFinancingActivitiesUSGAAPSummaryOfBusinessResults",
        "NetCashProvidedByUsedInFinancingActivities",
        "財務活動によるキャッシュ・フロー",
        "Cash flows from (used in) financing activities",
    ),
    _SummaryConceptDef(
        "cash_end",
        "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults",
        "CashAndCashEquivalents",
        "現金及び現金同等物",
        "Cash and cash equivalents",
    ),
    # --- 1株当たり ---
    _SummaryConceptDef(
        "eps",
        "BasicEarningsLossPerShareUSGAAPSummaryOfBusinessResults",
        None,
        "基本的１株当たり当社株主に帰属する利益又は損失（△）",
        "Basic earnings (loss) per share",
    ),
    _SummaryConceptDef(
        "eps_diluted",
        "DilutedEarningsLossPerShareUSGAAPSummaryOfBusinessResults",
        None,
        "希薄化後１株当たり当社株主に帰属する利益又は損失（△）",
        "Diluted earnings (loss) per share",
    ),
    _SummaryConceptDef(
        "bps",
        "EquityAttributableToOwnersOfParentPerShareUSGAAPSummaryOfBusinessResults",
        None,
        "１株当たり株主資本",
        "Equity attributable to owners of parent per share",
    ),
)

# concept ローカル名 → _SummaryConceptDef のルックアップテーブル
_CONCEPT_LOOKUP: dict[str, _SummaryConceptDef] = {
    d.concept_local_name: d for d in _USGAAP_SUMMARY_CONCEPTS
}

# concept 名のフローズンセット（get_usgaap_concept_names() 用）
_CONCEPT_NAMES: frozenset[str] = frozenset(_CONCEPT_LOOKUP)

# 正規化キー → J-GAAP concept の対応辞書（事前構築）
_JGAAP_MAPPING: dict[str, str | None] = {
    d.key: d.jgaap_concept for d in _USGAAP_SUMMARY_CONCEPTS
}

# 正規化キー → _SummaryConceptDef の逆引きテーブル
_KEY_LOOKUP: dict[str, _SummaryConceptDef] = {
    d.key: d for d in _USGAAP_SUMMARY_CONCEPTS
}

# ---------------------------------------------------------------------------
# レジストリ検証（モジュールロード時に実行）
# ---------------------------------------------------------------------------


def _validate_registry() -> None:
    """マッピングレジストリの整合性を検証する。

    モジュールロード時に呼び出され、データ定義のミスを早期に検出する。
    ``assert`` ではなく ``ValueError`` を使用し、``python -O`` でも動作する。

    Raises:
        ValueError: レジストリに不整合がある場合。
    """
    keys = [d.key for d in _USGAAP_SUMMARY_CONCEPTS]
    if len(keys) != len(set(keys)):
        duplicates = [k for k in keys if keys.count(k) > 1]
        raise ValueError(f"正規化キーが重複しています: {set(duplicates)}")

    concepts = [d.concept_local_name for d in _USGAAP_SUMMARY_CONCEPTS]
    if len(concepts) != len(set(concepts)):
        duplicates = [c for c in concepts if concepts.count(c) > 1]
        raise ValueError(
            f"concept_local_name が重複しています: {set(duplicates)}"
        )

    for d in _USGAAP_SUMMARY_CONCEPTS:
        if not d.key:
            raise ValueError(
                f"空の正規化キーが登録されています "
                f"(concept={d.concept_local_name!r})"
            )
        if not d.concept_local_name:
            raise ValueError("空の concept_local_name が登録されています")
        if not d.label_ja:
            raise ValueError(
                f"{d.key} の label_ja が空です"
            )


_validate_registry()

# TextBlock 分類マップ（最長一致用）
_TEXTBLOCK_STATEMENT_MAP: dict[str, tuple[str, bool]] = {
    # 年次（ConsolidatedXxxUSGAAPTextBlock）
    "ConsolidatedBalanceSheet": ("balance_sheet", False),
    "ConsolidatedStatementOfIncome": ("income_statement", False),
    "ConsolidatedStatementOfCashFlows": ("cash_flow_statement", False),
    "ConsolidatedStatementOfEquity": ("statement_of_changes_in_equity", False),
    "ConsolidatedStatementOfComprehensiveIncomeSingleStatement": (
        "comprehensive_income_single",
        False,
    ),
    "ConsolidatedStatementOfComprehensiveIncome": (
        "comprehensive_income",
        False,
    ),
    "NotesToConsolidatedFinancialStatements": ("notes", False),
    # 半期（SemiAnnualConsolidatedXxxUSGAAPTextBlock）
    "SemiAnnualConsolidatedBalanceSheet": ("balance_sheet", True),
    "SemiAnnualConsolidatedStatementOfIncome": ("income_statement", True),
    "SemiAnnualConsolidatedStatementOfCashFlows": (
        "cash_flow_statement",
        True,
    ),
    "SemiAnnualConsolidatedStatementOfComprehensiveIncomeSingleStatement": (
        "comprehensive_income_single",
        True,
    ),
    "SemiAnnualConsolidatedStatementOfComprehensiveIncome": (
        "comprehensive_income",
        True,
    ),
    "ConsolidatedSemiAnnualStatementOfEquity": (
        "statement_of_changes_in_equity",
        True,
    ),
    "NotesToSemiAnnualConsolidatedFinancialStatements": ("notes", True),
}

# 説明文要素の concept ローカル名
_DESCRIPTION_CONCEPT = (
    "DescriptionOfFactThatConsolidatedFinancialStatements"
    "HaveBeenPreparedInAccordanceWithUSGAAPFinancialInformation"
)

# ---------------------------------------------------------------------------
# 公開 dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class USGAAPSummaryItem:
    """US-GAAP SummaryOfBusinessResults の 1 項目。

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
    """

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
    """US-GAAP TextBlock の 1 項目。

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
    """

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
        """正規化キーで SummaryOfBusinessResults 項目を検索する。

        最新期間の項目を優先して返す。
        「最新」は DurationPeriod.end_date / InstantPeriod.instant の
        日付降順で決定する。

        Args:
            key: 正規化キー（例: ``"revenue"``, ``"total_assets"``）。

        Returns:
            合致する項目。見つからない場合は None。
        """
        best: USGAAPSummaryItem | None = None
        best_date: datetime.date | None = None
        for item in self.summary_items:
            if item.key != key:
                continue
            item_date = _period_sort_key(item.period)
            if best_date is None or item_date > best_date:
                best = item
                best_date = item_date
        return best

    def get_items_by_period(
        self,
        period: Period,
    ) -> tuple[USGAAPSummaryItem, ...]:
        """指定期間の SummaryOfBusinessResults 項目を返す。

        Args:
            period: 対象期間。

        Returns:
            指定期間の項目タプル。
        """
        return tuple(
            item for item in self.summary_items if item.period == period
        )

    @property
    def available_periods(self) -> tuple[Period, ...]:
        """利用可能な期間の一覧。新しい順にソート。"""
        seen: set[Period] = set()
        periods: list[Period] = []
        for item in self.summary_items:
            if item.period not in seen:
                seen.add(item.period)
                periods.append(item.period)
        periods.sort(key=_period_sort_key, reverse=True)
        return tuple(periods)

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
        result: list[dict[str, object]] = []
        for item in self.summary_items:
            value: str | None
            if isinstance(item.value, Decimal):
                value = str(item.value)
            elif isinstance(item.value, str):
                value = item.value
            else:
                value = None
            result.append(
                {
                    "key": item.key,
                    "label_ja": item.label_ja,
                    "value": value,
                    "unit": item.unit_ref,
                    "concept": item.concept,
                }
            )
        return result

    def __repr__(self) -> str:
        """REPL 向けの簡潔な表現。"""
        return (
            f"USGAAPSummary(summary_items={len(self.summary_items)}, "
            f"text_blocks={len(self.text_blocks)}, "
            f"total_elements={self.total_usgaap_elements})"
        )


# ---------------------------------------------------------------------------
# 内部ユーティリティ
# ---------------------------------------------------------------------------


def _is_jpcrp_namespace(uri: str) -> bool:
    """名前空間 URI が jpcrp_cor かどうかを判定する。

    US-GAAP 要素は全て jpcrp_cor 名前空間に属する。
    classify_namespace() を使用して DRY 原則を遵守する。
    """
    info = classify_namespace(uri)
    return info.module_group == "jpcrp"


def _parse_value(fact: RawFact) -> Decimal | str | None:
    """RawFact の値をパースする。

    数値として解釈可能なら Decimal、不可能なら str、nil なら None。
    数値が期待される fact（unit_ref が存在する）が Decimal に変換できない場合は
    EdinetWarning を発出する。
    """
    if fact.is_nil:
        return None
    if fact.value_raw is None:
        return None

    try:
        return Decimal(fact.value_raw)
    except (InvalidOperation, ValueError):
        if fact.unit_ref is not None:
            warnings.warn(
                f"数値が期待される fact '{fact.local_name}' の値 "
                f"'{fact.value_raw[:50]}' を Decimal に変換できません。",
                EdinetWarning,
                stacklevel=2,
            )
        return fact.value_raw


def _resolve_period(
    context_ref: str,
    contexts: dict[str, StructuredContext],
) -> Period | None:
    """contextRef から期間情報を解決する。

    contexts 辞書から StructuredContext を取得し、その period を返す。
    context_ref が見つからない場合は EdinetWarning を発出し None を返す。

    Args:
        context_ref: RawFact の contextRef 属性値。
        contexts: structure_contexts() の戻り値。

    Returns:
        Period。context_ref が見つからない場合は None。
    """
    ctx = contexts.get(context_ref)
    if ctx is not None:
        return ctx.period
    warnings.warn(
        f"contextRef '{context_ref}' が contexts 辞書に見つかりません。"
        f"当該 fact はスキップされます。",
        EdinetWarning,
        stacklevel=3,
    )
    return None


def _classify_text_block(
    local_name: str,
) -> tuple[str | None, bool]:
    """TextBlock の概念名から財務諸表種別と半期フラグを推定する。

    最長一致でキーワードをマッチさせ、最も具体的な分類を返す。
    """
    best_hint: str | None = None
    best_semi: bool = "SemiAnnual" in local_name
    best_length = 0

    for keyword, (hint, is_semi) in _TEXTBLOCK_STATEMENT_MAP.items():
        if keyword in local_name and len(keyword) > best_length:
            best_hint = hint
            best_semi = is_semi
            best_length = len(keyword)

    return (best_hint, best_semi)


def _period_sort_key(period: Period) -> datetime.date:
    """Period からソートキーとなる日付を取得する。

    DurationPeriod → end_date、InstantPeriod → instant。
    """
    if isinstance(period, InstantPeriod):
        return period.instant
    if isinstance(period, DurationPeriod):
        return period.end_date
    return datetime.date.min  # 型安全のためのフォールバック（到達しない）


def _extract_description(usgaap_facts: list[RawFact]) -> str | None:
    """米国基準適用の説明文を抽出する。

    同一 concept の fact が複数存在する場合は最初に見つかったものを返す。
    """
    for fact in usgaap_facts:
        if fact.local_name == _DESCRIPTION_CONCEPT and fact.value_raw:
            return fact.value_raw
    return None


def _extract_summary_items(
    usgaap_facts: list[RawFact],
    contexts: dict[str, StructuredContext],
) -> list[USGAAPSummaryItem]:
    """US-GAAP facts から SummaryOfBusinessResults 要素を抽出する。"""
    items: list[USGAAPSummaryItem] = []
    for fact in usgaap_facts:
        defn = _CONCEPT_LOOKUP.get(fact.local_name)
        if defn is None:
            continue

        period = _resolve_period(fact.context_ref, contexts)
        if period is None:
            continue

        value = _parse_value(fact)

        items.append(
            USGAAPSummaryItem(
                key=defn.key,
                concept=fact.local_name,
                label_ja=defn.label_ja,
                label_en=defn.label_en,
                value=value,
                unit_ref=fact.unit_ref,
                period=period,
                context_id=fact.context_ref,
            )
        )

    return items


def _extract_text_blocks(
    usgaap_facts: list[RawFact],
    contexts: dict[str, StructuredContext],
) -> list[USGAAPTextBlockItem]:
    """US-GAAP facts から TextBlock 要素を抽出する。"""
    items: list[USGAAPTextBlockItem] = []
    for fact in usgaap_facts:
        if "TextBlock" not in fact.local_name:
            continue

        statement_hint, is_semi_annual = _classify_text_block(fact.local_name)
        period = _resolve_period(fact.context_ref, contexts)
        if period is None:
            continue

        items.append(
            USGAAPTextBlockItem(
                concept=fact.local_name,
                statement_hint=statement_hint,
                is_semi_annual=is_semi_annual,
                html_content=fact.value_raw,
                period=period,
                context_id=fact.context_ref,
            )
        )

    return items


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def extract_usgaap_summary(
    facts: tuple[RawFact, ...],
    contexts: dict[str, StructuredContext],
) -> USGAAPSummary:
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
    # Step 1: jpcrp_cor 名前空間の facts をフィルタ
    jpcrp_facts = [f for f in facts if _is_jpcrp_namespace(f.namespace_uri)]

    # Step 2: US-GAAP 関連要素をローカル名でフィルタ
    usgaap_facts = [f for f in jpcrp_facts if "USGAAP" in f.local_name]
    total_elements = len(usgaap_facts)

    # Step 3: SummaryOfBusinessResults 要素を抽出
    summary_items = _extract_summary_items(usgaap_facts, contexts)

    # Step 4: TextBlock 要素を抽出
    text_blocks = _extract_text_blocks(usgaap_facts, contexts)

    # Step 5: 説明文要素を抽出
    description = _extract_description(usgaap_facts)

    return USGAAPSummary(
        summary_items=tuple(summary_items),
        text_blocks=tuple(text_blocks),
        description=description,
        total_usgaap_elements=total_elements,
    )


def is_usgaap_element(local_name: str) -> bool:
    """concept のローカル名が US-GAAP 関連要素かどうかを判定する。

    ``"USGAAP"`` を名前に含む jpcrp_cor 要素を US-GAAP 要素として判定する。

    Args:
        local_name: concept のローカル名。

    Returns:
        US-GAAP 関連要素であれば True。
    """
    return "USGAAP" in local_name


def get_jgaap_mapping() -> dict[str, str | None]:
    """US-GAAP SummaryOfBusinessResults 正規化キー → J-GAAP concept の対応辞書を返す。

    Wave 3 の standards/normalize が US-GAAP ↔ J-GAAP の横断比較に使用する。
    モジュールレベルで事前構築済みの辞書を返す。

    Returns:
        ``{正規化キー: J-GAAP concept ローカル名}`` の辞書。
        対応する J-GAAP 科目がない場合の値は None。

    Example:
        >>> mapping = get_jgaap_mapping()
        >>> mapping["revenue"]
        'NetSales'
        >>> mapping["per"]  # 株価収益率は J-GAAP 側に直接の対応科目なし
    """
    return _JGAAP_MAPPING


def get_usgaap_concept_names() -> frozenset[str]:
    """US-GAAP SummaryOfBusinessResults の全 concept ローカル名を返す。

    SummaryOfBusinessResults 要素の完全な concept 名
    （``"RevenuesUSGAAPSummaryOfBusinessResults"`` 等）の
    フローズンセット。

    TextBlock 要素と Abstract 要素は含まない。

    Returns:
        concept ローカル名のフローズンセット。
    """
    return _CONCEPT_NAMES


def canonical_key(concept: str) -> str | None:
    """US-GAAP concept ローカル名を正規化キーにマッピングする。

    jgaap.canonical_key / ifrs.canonical_key と同一パターンの
    インターフェースを提供し、normalize.get_canonical_key() から
    呼び出される。

    Args:
        concept: jpcrp_cor の US-GAAP 固有 concept ローカル名
            （例: ``"RevenuesUSGAAPSummaryOfBusinessResults"``）。

    Returns:
        正規化キー文字列（例: ``"revenue"``）。
        登録されていない concept の場合は ``None``。
    """
    d = _CONCEPT_LOOKUP.get(concept)
    return d.key if d is not None else None


def reverse_lookup(key: str) -> _SummaryConceptDef | None:
    """正規化キーから US-GAAP の概念定義を取得する（逆引き）。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        対応する ``_SummaryConceptDef``。
        該当するマッピングがない場合は ``None``。
    """
    return _KEY_LOOKUP.get(key)

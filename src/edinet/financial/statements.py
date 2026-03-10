"""XBRL 財務諸表構造ユーティリティ。

``build_line_items()`` が生成した :class:`~edinet.models.financial.LineItem` 群を
PL / BS / CF に分類し、選択ルール（期間・連結・dimension）を適用して
:class:`~edinet.models.financial.FinancialStatement` オブジェクトを組み立てる。

会計基準の判別は ``standards.detect`` で行い、概念セットの取得は
``standards.normalize`` 経由で各基準モジュールにディスパッチする。
"""

from __future__ import annotations

import dataclasses
import logging
import warnings
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from edinet.exceptions import EdinetWarning
from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
from edinet.xbrl.contexts import (
    DurationPeriod,
    InstantPeriod,
    Period,
    StructuredContext,
)
from edinet.xbrl.dei import AccountingStandard
from edinet.xbrl.parser import RawFact
from edinet.financial.standards.detect import (
    DetectedStandard,
    DetailLevel,
    detect_accounting_standard,
)
from edinet.financial.standards.normalize import (
    get_concept_order,
    get_known_concepts,
)

if TYPE_CHECKING:
    from edinet.xbrl.dei import DEI
    from edinet.xbrl.linkbase.calculation import CalculationLinkbase
    from edinet.xbrl.linkbase.definition import DefinitionTree
    from edinet.xbrl.taxonomy import TaxonomyResolver

__all__ = ["build_statements", "Statements"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_CONSOLIDATED_AXIS_SUFFIX = "ConsolidatedOrNonConsolidatedAxis"
_CONSOLIDATED_MEMBER_SUFFIX = "ConsolidatedMember"
_NONCONSOLIDATED_MEMBER_SUFFIX = "NonConsolidatedMember"


# ---------------------------------------------------------------------------
# 連結判定ヘルパー
# ---------------------------------------------------------------------------


def _is_consolidated(item: LineItem) -> bool:
    """連結 Fact か判定する。

    以下のいずれかの場合に True:
    - dimension なし（XBRL のデフォルト = 連結）
    - 連結軸の ConsolidatedMember が明示的に設定されている
      （他の軸を含まない場合のみ）

    XBRL では連結軸のデフォルト Member を明示的に設定する
    ケースがあり、その場合も連結として扱う。
    """
    if len(item.dimensions) == 0:
        return True
    return (
        all(
            dim.axis.endswith(_CONSOLIDATED_AXIS_SUFFIX)
            for dim in item.dimensions
        )
        and not _is_non_consolidated(item)
    )


def _is_non_consolidated(item: LineItem) -> bool:
    """NonConsolidatedMember を持つ = 個別。"""
    return any(
        dim.member.endswith(_NONCONSOLIDATED_MEMBER_SUFFIX)
        for dim in item.dimensions
    )


def _is_total(item: LineItem) -> bool:
    """連結軸以外の dimension がない全社合計。

    以下のいずれかの場合に True:
    - dimension なし（連結デフォルト）
    - 連結軸（ConsolidatedOrNonConsolidatedAxis）上の
      Member のみ（ConsolidatedMember / NonConsolidatedMember）

    セグメント軸等が含まれる場合は False（部分値であり全社合計ではない）。
    """
    if len(item.dimensions) == 0:
        return True
    return all(
        dim.axis.endswith(_CONSOLIDATED_AXIS_SUFFIX)
        for dim in item.dimensions
    )


# ---------------------------------------------------------------------------
# 期間フィルタ
# ---------------------------------------------------------------------------


def _select_latest_period(
    items: Sequence[LineItem],
    statement_type: StatementType,
) -> InstantPeriod | DurationPeriod | None:
    """最新期間を自動選択する。

    BS は InstantPeriod（instant が最新の日付）を選択する。
    PL / CF は DurationPeriod（end_date が最新の日付）を選択する。

    同一日付の instant と duration が混在する場合、statement_type に
    合致する期間タイプのみを候補とする。

    PL / CF で end_date が同値の場合は最長期間（start_date が最も古い）を
    選択する。ソートキーは ``(end_date DESC, start_date ASC)``。

    該当する periodType の Fact が 1 件も存在しない場合は ``None`` を返す。

    Args:
        items: 対象の LineItem シーケンス。
        statement_type: 財務諸表の種類。

    Returns:
        最新の期間。該当 periodType がなければ ``None``。
    """
    if statement_type == StatementType.BALANCE_SHEET:
        instant_periods = [
            item.period
            for item in items
            if isinstance(item.period, InstantPeriod)
        ]
        if not instant_periods:
            return None
        return max(instant_periods, key=lambda p: p.instant)
    else:
        # PL / CF: DurationPeriod を選択
        duration_periods = [
            item.period
            for item in items
            if isinstance(item.period, DurationPeriod)
        ]
        if not duration_periods:
            return None
        # end_date DESC, start_date ASC（最長期間優先）
        return max(
            duration_periods,
            key=lambda p: (p.end_date, -p.start_date.toordinal()),
        )


def _filter_by_period(
    items: Sequence[LineItem],
    period: InstantPeriod | DurationPeriod,
    statement_type: StatementType,
) -> list[LineItem]:
    """指定期間の Fact のみを返す。

    期間の一致判定は == 比較（完全一致）で行う。
    異なる periodType の Fact は型不一致で自然に除外される。

    Args:
        items: 対象の LineItem シーケンス。
        period: フィルタ対象の期間。
        statement_type: 財務諸表の種類（未使用、将来拡張用）。

    Returns:
        指定期間に一致する LineItem のリスト。
    """
    _ = statement_type  # v0.2.0 で periodType 検証等に使用予定
    return [item for item in items if item.period == period]


# ---------------------------------------------------------------------------
# 連結フィルタ
# ---------------------------------------------------------------------------


def _filter_consolidated_with_fallback(
    items: Sequence[LineItem],
    consolidated: bool,
) -> tuple[list[LineItem], bool]:
    """連結/個別フィルタ（フォールバック付き）。

    フォールバック判定は全社合計（``_is_total``）の Fact のみを対象とする。
    セグメント分解のみの個別 Fact（NonConsolidatedMember + SegmentAxis）が
    存在しても、全社合計の個別 Fact がなければフォールバックが発生する。

    consolidated=True の場合:
      1. 連結 Fact（dimension なし or 明示的 ConsolidatedMember）を優先
      2. 連結 Fact が 0 件なら、個別全社合計にフォールバック

    consolidated=False の場合:
      1. 個別全社合計（NonConsolidatedMember のみ）を優先
      2. 個別全社合計が 0 件なら、連結にフォールバック

    Args:
        items: 対象の LineItem シーケンス。
        consolidated: True なら連結優先、False なら個別。

    Returns:
        (フィルタ済み LineItem リスト, 実際に適用された連結/個別)。
        フォールバックが発生した場合、2 番目の値は引数と異なる。
    """
    if consolidated:
        # 連結 Fact は _is_consolidated で既に全社合計が保証される
        result = [item for item in items if _is_consolidated(item)]
        if result:
            return result, True
        # フォールバック: 個別全社合計のみ（セグメント分解は除外）
        result = [
            item
            for item in items
            if _is_non_consolidated(item) and _is_total(item)
        ]
        if result:
            return result, False
        # どちらも空: 要求されたモードを保持（フォールバックは発生していない）
        return [], True
    else:
        # 個別全社合計のみ（セグメント分解は除外）
        result = [
            item
            for item in items
            if _is_non_consolidated(item) and _is_total(item)
        ]
        if result:
            return result, False
        # フォールバック: 連結
        result = [item for item in items if _is_consolidated(item)]
        if result:
            return result, True
        # どちらも空: 要求されたモードを保持
        return [], False


# ---------------------------------------------------------------------------
# CF instant 吸収（期首/期末残高）
# ---------------------------------------------------------------------------


def _absorb_cf_instant_balances(
    fs: FinancialStatement,
    all_items: tuple[LineItem, ...],
    *,
    concept_set: object | None,
    taxonomy_root: Path | None,
) -> FinancialStatement:
    """CF に期首/期末の instant 残高を挿入するポストプロセス。

    Presentation Linkbase の ``preferredLabel`` が ``periodStartLabel`` /
    ``periodEndLabel`` である科目を CF ConceptSet から動的検出し、
    対応する instant Fact を期首残高（先頭）・期末残高（末尾）として挿入する。

    concept 名のハードコードを持たず、タクソノミ更新に自動追従する。

    期間対応ルール::

        CF: DurationPeriod(start=2024-04-01, end=2025-03-31) の場合
          期首 = InstantPeriod(2024-03-31)  ← start_date - 1日
          期末 = InstantPeriod(2025-03-31)  ← end_date

    Args:
        fs: ``_build_single_statement()`` で組み立て済みの CF。
        all_items: 全 LineItem（全期間・全 dimension）。
        concept_set: CF の ConceptSet。``None`` の場合は吸収スキップ。
        taxonomy_root: タクソノミルートパス。ラベル解決に使用。

    Returns:
        期首/期末を挿入した新しい FinancialStatement。
        挿入対象がなければ元の FinancialStatement をそのまま返す。
    """
    from edinet.xbrl._linkbase_utils import (
        ROLE_PERIOD_END_LABEL,
        ROLE_PERIOD_START_LABEL,
    )
    from edinet.xbrl.taxonomy import ConceptSet as _ConceptSet

    # ガード
    if fs.statement_type != StatementType.CASH_FLOW_STATEMENT:
        return fs
    if fs.period is None or not isinstance(fs.period, DurationPeriod):
        return fs
    if not fs.items:
        return fs
    if concept_set is None or not isinstance(concept_set, _ConceptSet):
        return fs

    # ConceptSet から期首/期末対象の concept 名を動的検出
    beginning_concepts: set[str] = set()
    end_concepts: set[str] = set()
    for entry in concept_set.concepts:
        if entry.preferred_label == ROLE_PERIOD_START_LABEL:
            beginning_concepts.add(entry.concept)
        elif entry.preferred_label == ROLE_PERIOD_END_LABEL:
            end_concepts.add(entry.concept)

    target_concepts = beginning_concepts | end_concepts
    if not target_concepts:
        return fs

    # 対象 instant 計算
    period_beginning = InstantPeriod(
        instant=fs.period.start_date - timedelta(days=1),
    )
    period_end = InstantPeriod(instant=fs.period.end_date)

    # 候補抽出
    beginning_candidates: dict[str, LineItem] = {}
    end_candidates: dict[str, LineItem] = {}

    for item in all_items:
        if item.local_name not in target_concepts:
            continue
        if not isinstance(item.value, Decimal) or item.is_nil:
            continue
        if not isinstance(item.period, InstantPeriod):
            continue
        # 連結/個別フィルタ
        if fs.consolidated:
            if not _is_consolidated(item):
                continue
        else:
            if not _is_non_consolidated(item):
                continue
        # 全社合計のみ
        if not _is_total(item):
            continue

        # 期首/期末判定（先頭1件採用 = 重複解決）
        if (
            item.local_name in beginning_concepts
            and item.period == period_beginning
        ):
            if item.local_name not in beginning_candidates:
                beginning_candidates[item.local_name] = item
        if (
            item.local_name in end_concepts
            and item.period == period_end
        ):
            if item.local_name not in end_candidates:
                end_candidates[item.local_name] = item

    if not beginning_candidates and not end_candidates:
        return fs

    # ラベル解決
    def _resolve_label(
        item: LineItem, is_beginning: bool,
    ) -> LineItem:
        """期首/期末ラベルを解決して新 LineItem を返す。"""
        from edinet.xbrl._linkbase_utils import ROLE_LABEL
        from edinet.xbrl.taxonomy import LabelInfo, LabelSource

        role = ROLE_PERIOD_START_LABEL if is_beginning else ROLE_PERIOD_END_LABEL
        label_ja: LabelInfo | None = None
        label_en: LabelInfo | None = None

        if taxonomy_root is not None:
            from edinet.xbrl.taxonomy import TaxonomyResolver

            resolver = TaxonomyResolver(taxonomy_root)
            info_ja = resolver.resolve_clark(item.concept, role=role, lang="ja")
            if info_ja.role == role:
                label_ja = info_ja
            info_en = resolver.resolve_clark(item.concept, role=role, lang="en")
            if info_en.role == role:
                label_en = info_en

        # local_name フォールバック
        if label_ja is None:
            label_ja = LabelInfo(
                text=item.local_name,
                role=ROLE_LABEL,
                lang="ja",
                source=LabelSource.FALLBACK,
            )
        if label_en is None:
            label_en = LabelInfo(
                text=item.local_name,
                role=ROLE_LABEL,
                lang="en",
                source=LabelSource.FALLBACK,
            )

        return dataclasses.replace(item, label_ja=label_ja, label_en=label_en)

    # 挿入用リスト構築
    beginning_items = [
        _resolve_label(item, is_beginning=True)
        for item in beginning_candidates.values()
    ]
    end_items = [
        _resolve_label(item, is_beginning=False)
        for item in end_candidates.values()
    ]

    new_items = (*beginning_items, *fs.items, *end_items)
    return dataclasses.replace(fs, items=new_items)


# ---------------------------------------------------------------------------
# 中核: 単一 Statement 組み立て
# ---------------------------------------------------------------------------


def _build_single_statement(
    items: tuple[LineItem, ...],
    statement_type: StatementType,
    known_concepts: frozenset[str],
    concept_order: dict[str, int],
    *,
    consolidated: bool = True,
    period: Period | None = None,
    strict: bool = False,
) -> FinancialStatement:
    """単一の財務諸表を組み立てる（内部関数）。

    選択ルールを順に適用する。

    Args:
        items: 全 LineItem（全期間・全 dimension）。
        statement_type: 財務諸表の種類。
        known_concepts: 該当基準の既知概念集合。
        concept_order: ``{concept_local_name: display_order}`` の辞書。
        consolidated: True なら連結優先、False なら個別。
        period: 対象期間。None なら最新期間を自動選択。
        strict: True の場合、要求した連結/個別データが存在しないとき
            フォールバックせず空の FinancialStatement を返す。

    Returns:
        組み立て済みの FinancialStatement。
    """
    issued_warnings: list[str] = []

    # 1. 数値 Fact のみ（テキスト、nil 除外）
    numeric_items = [
        item
        for item in items
        if isinstance(item.value, Decimal) and not item.is_nil
    ]

    # 2. 科目分類 — 既知概念集合に含まれる LineItem のみを抽出
    candidates = [
        item for item in numeric_items if item.local_name in known_concepts
    ]
    if not candidates:
        return FinancialStatement(
            statement_type=statement_type,
            period=period,
            items=(),
            consolidated=consolidated,
            entity_id="",
            warnings_issued=(),
        )

    if period is None:
        period = _select_latest_period(candidates, statement_type)
    if period is None:
        # 該当する periodType の Fact がない（例: BS なのに InstantPeriod がない）
        msg = (
            f"{statement_type.value}: "
            f"該当する periodType の Fact がありません"
        )
        issued_warnings.append(msg)
        warnings.warn(msg, EdinetWarning, stacklevel=3)
        return FinancialStatement(
            statement_type=statement_type,
            period=None,
            items=(),
            consolidated=consolidated,
            entity_id="",
            warnings_issued=tuple(issued_warnings),
        )
    period_filtered = _filter_by_period(candidates, period, statement_type)

    # 3. 連結フィルタ（フォールバック付き）
    consolidated_filtered, actual_consolidated = (
        _filter_consolidated_with_fallback(period_filtered, consolidated)
    )
    if actual_consolidated != consolidated:
        if strict:
            scope = "連結" if consolidated else "個別"
            msg = (
                f"{statement_type.value}: strict モード — "
                f"{scope}データが存在しません"
            )
            issued_warnings.append(msg)
            warnings.warn(msg, EdinetWarning, stacklevel=3)
            return FinancialStatement(
                statement_type=statement_type,
                period=period,
                items=(),
                consolidated=consolidated,
                entity_id="",
                warnings_issued=tuple(issued_warnings),
            )
        if consolidated:
            msg = f"{statement_type.value}: 連結データなし、個別にフォールバック"
        else:
            msg = f"{statement_type.value}: 個別データなし、連結にフォールバック"
        issued_warnings.append(msg)
        warnings.warn(msg, EdinetWarning, stacklevel=3)

    # 4. dimension フィルタ（全社合計のみ）
    total_items = [
        item for item in consolidated_filtered if _is_total(item)
    ]

    # 5. 重複解決
    concept_to_items: dict[str, list[LineItem]] = {}
    for item in total_items:
        concept_to_items.setdefault(item.local_name, []).append(item)

    selected: list[LineItem] = []
    for concept_name, concept_items in concept_to_items.items():
        if len(concept_items) > 1:
            logger.debug(
                "%s: %d候補中1件を採用（context_id=%r）",
                concept_name,
                len(concept_items),
                concept_items[0].context_id,
            )
        selected.append(concept_items[0])

    # 6. 並び順: display_order に従う
    max_order = max(concept_order.values()) if concept_order else 0

    def sort_key(item: LineItem) -> tuple[int, int]:
        order = concept_order.get(item.local_name)
        if order is not None:
            return (order, 0)
        return (max_order + 1, item.order)

    selected.sort(key=sort_key)

    entity_id = selected[0].entity_id if selected else ""

    logger.info(
        "%s を組み立て: %d 科目（候補 %d 件から選択）",
        statement_type.value,
        len(selected),
        len(items),
    )

    return FinancialStatement(
        statement_type=statement_type,
        period=period,
        items=tuple(selected),
        consolidated=actual_consolidated,
        entity_id=entity_id,
        warnings_issued=tuple(issued_warnings),
    )


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Statements:
    """財務諸表コンテナ。

    ``build_statements()`` 経由で構築すること。直接コンストラクトは非推奨。

    ``build_statements()`` の返り値。PL / BS / CF への
    アクセスメソッドを提供する。内部には全 LineItem を保持し、
    メソッド呼び出し時に選択ルールを適用する。

    会計基準の判別結果を ``_detected_standard`` に保持し、
    各メソッドで基準別の概念セットにディスパッチする。

    Attributes:
        _items: 全 LineItem（全期間・全 dimension）。
        _detected_standard: 判別された会計基準。
        _facts: 元の RawFact（テキストブロック抽出・会計基準判別用）。
        _contexts: コンテキストマッピング（テキストブロック抽出用）。
        _taxonomy_root: タクソノミルートパス。
        _industry_code: 業種コード（例: ``"bk1"``）。
            ``None`` は一般事業会社。
        _resolver: ラベル解決済みの TaxonomyResolver。
            パイプライン中に ``load_filer_labels()`` で提出者固有ラベルが
            ロードされた状態で保持される。セグメント分析等の
            事後ラベル解決に使用する。
    """

    _items: tuple[LineItem, ...]
    _detected_standard: DetectedStandard | None = None
    _facts: tuple[RawFact, ...] | None = None
    _contexts: dict[str, StructuredContext] | None = None
    _taxonomy_root: Path | None = None
    _industry_code: str | None = None
    _dei: DEI | None = None
    _resolver: TaxonomyResolver | None = None
    _calculation_linkbase: CalculationLinkbase | None = None
    _definition_linkbase: dict[str, DefinitionTree] | None = None
    _definition_parent_index: dict[str, str] | None = None
    _source_path: str | None = None

    @property
    def source_path(self) -> str | None:
        """元の XBRL ファイルパスを返す。

        ZIP 内のパス（例: ``"XBRL/PublicDoc/0101010_honbun.xbrl"``）。
        Parquet 復元時にも保持される。
        """
        return self._source_path

    @property
    def detected_standard(self) -> DetectedStandard | None:
        """判別された会計基準を返す。"""
        return self._detected_standard

    @property
    def dei(self) -> DEI | None:
        """DEI 情報を返す。"""
        return self._dei

    @property
    def context_map(self) -> dict[str, StructuredContext] | None:
        """コンテキストマッピングを返す。"""
        return self._contexts

    @property
    def resolver(self) -> TaxonomyResolver | None:
        """TaxonomyResolver を返す。"""
        return self._resolver

    @property
    def industry_code(self) -> str | None:
        """業種コードを返す。"""
        return self._industry_code

    @property
    def taxonomy_root(self) -> Path | None:
        """タクソノミルートパスを返す。"""
        return self._taxonomy_root

    @property
    def calculation_linkbase(self) -> CalculationLinkbase | None:
        """Calculation Linkbase を返す。"""
        return self._calculation_linkbase

    @property
    def definition_linkbase(self) -> dict[str, DefinitionTree] | None:
        """Definition Linkbase を返す。"""
        return self._definition_linkbase

    @property
    def definition_parent_index(self) -> dict[str, str] | None:
        """事前計算済みの definition parent index を返す。

        Parquet 復元時など、フル DefinitionTree を持たない場合に
        ``extract_values()`` の ``definition_mapper`` が使用する。
        """
        return self._definition_parent_index

    @property
    def raw_facts(self) -> tuple[RawFact, ...] | None:
        """元の RawFact タプルを返す。"""
        return self._facts

    def _get_standard_enum(self) -> AccountingStandard | None:
        """DetectedStandard から AccountingStandard enum を抽出する。"""
        if self._detected_standard is None:
            return None
        std = self._detected_standard.standard
        if isinstance(std, AccountingStandard):
            return std
        return None

    # -- Feature 2: consolidated detection properties -------------------------

    @property
    def has_consolidated_data(self) -> bool:
        """連結データが存在するかを返す。"""
        return any(
            _is_consolidated(item)
            for item in self._items
            if isinstance(item.value, Decimal) and not item.is_nil
        )

    @property
    def has_non_consolidated_data(self) -> bool:
        """個別データが存在するかを返す。"""
        return any(
            _is_non_consolidated(item)
            for item in self._items
            if isinstance(item.value, Decimal) and not item.is_nil
        )

    # -- Feature 3: period_variants -------------------------------------------

    @property
    def period_classification(self):
        """DEI ベースの期間分類結果を返す。

        Returns:
            PeriodClassification。DEI なしの場合は全フィールド None。
        """
        from edinet.financial.dimensions.period_variants import (
            PeriodClassification,
            classify_periods,
        )
        if self._dei is not None:
            return classify_periods(self._dei)
        return PeriodClassification(
            current_duration=None,
            prior_duration=None,
            current_instant=None,
            prior_instant=None,
        )

    def _resolve_period_variant(
        self,
        period: Period | Literal["current", "prior"] | None,
        statement_type: StatementType,
    ) -> Period | None:
        """文字列の期間指定を実際の Period に解決する。

        Args:
            period: 期間指定。文字列なら DEI ベースで解決。
            statement_type: 財務諸表の種類（BS は instant、PL/CF は duration）。

        Returns:
            解決済みの Period。解決できなければ None（auto-latest）。
        """
        if not isinstance(period, str):
            return period

        pc = self.period_classification
        is_bs = statement_type == StatementType.BALANCE_SHEET

        if period == "current":
            resolved = pc.current_instant if is_bs else pc.current_duration
        elif period == "prior":
            resolved = pc.prior_instant if is_bs else pc.prior_duration
        else:
            msg = f"不明な period 指定: {period!r}（'current' / 'prior' のみ有効）"
            warnings.warn(msg, EdinetWarning, stacklevel=4)
            return None

        if resolved is None:
            msg = (
                f"period={period!r} を解決できません"
                f"（DEI 情報が不足しています）"
            )
            warnings.warn(msg, EdinetWarning, stacklevel=4)
        return resolved

    def _build_for_type(
        self,
        statement_type: StatementType,
        *,
        consolidated: bool = True,
        period: Period | None = None,
        strict: bool = False,
    ) -> FinancialStatement:
        """指定 StatementType の財務諸表を組み立てる（内部共通メソッド）。

        会計基準の DetailLevel に応じてディスパッチする:
        - DETAILED (J-GAAP/IFRS): 概念セットベースの詳細組み立て
        - BLOCK_ONLY (US-GAAP): サマリー項目から組み立て
        - BLOCK_ONLY (JMIS 等): 空 + 警告

        Args:
            statement_type: 財務諸表の種類。
            consolidated: 連結/個別。
            period: 対象期間。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの FinancialStatement。
        """
        standard_enum = self._get_standard_enum()
        detail_level = (
            self._detected_standard.detail_level
            if self._detected_standard is not None
            else None
        )

        # BLOCK_ONLY の処理（US-GAAP / JMIS 等）
        # v0.2.0: US-GAAP も空 + 警告を返す。
        # extract_values(stmts, ...) で SummaryOfBusinessResults から取得すること。
        # US-GAAP 個別（consolidated=False）は J-GAAP の ConceptSet で処理する。
        if detail_level == DetailLevel.BLOCK_ONLY and consolidated:
            msg = (
                f"{statement_type.value}: {standard_enum} は BLOCK_ONLY のため"
                f"詳細な財務諸表を生成できません"
                f"（extract_values() で SummaryOfBusinessResults を使用してください）"
            )
            warnings.warn(msg, EdinetWarning, stacklevel=3)
            return FinancialStatement(
                statement_type=statement_type,
                period=period,
                items=(),
                consolidated=consolidated,
                entity_id="",
                warnings_issued=(msg,),
            )

        # DETAILED の処理（J-GAAP / IFRS / 未検出）
        # ConceptSet を1回だけ取得し、known / order を直接導出する
        concept_set = None
        if self._taxonomy_root is not None:
            from edinet.financial.standards.normalize import get_concept_set

            concept_set = get_concept_set(
                standard_enum, statement_type,
                self._taxonomy_root, self._industry_code,
            )
        if concept_set is not None:
            known = concept_set.non_abstract_concepts()
            # concepts タプルのインデックスを表示順に使用する。
            # e.order は同一親の兄弟間の相対順序であり、ツリー全体の
            # 通し番号ではない。concepts は DFS 順に格納されているため
            # タプルのインデックスがグローバルな表示順序となる。
            order = {
                e.concept: idx
                for idx, e in enumerate(concept_set.concepts)
                if not e.is_abstract
            }
        else:
            known = get_known_concepts(
                standard_enum, statement_type,
                taxonomy_root=self._taxonomy_root,
                industry_code=self._industry_code,
            )
            order = get_concept_order(
                standard_enum, statement_type,
                taxonomy_root=self._taxonomy_root,
                industry_code=self._industry_code,
            )
        fs = _build_single_statement(
            self._items,
            statement_type,
            known,
            order,
            consolidated=consolidated,
            period=period,
            strict=strict,
        )
        # CF instant 吸収（IFRS/JMIS は対象外: BS で表現）
        if (
            statement_type == StatementType.CASH_FLOW_STATEMENT
            and standard_enum not in (
                AccountingStandard.IFRS, AccountingStandard.JMIS,
            )
        ):
            fs = _absorb_cf_instant_balances(
                fs, self._items,
                concept_set=concept_set,
                taxonomy_root=self._taxonomy_root,
            )
        # ConceptSet を FinancialStatement に伝播（階層表示用）
        if concept_set is not None:
            fs = dataclasses.replace(
                fs,
                _concept_set=concept_set,
                _taxonomy_root=self._taxonomy_root,
            )
        return fs

    # -- dict-like プロトコル (DEFACTO-2) -------------------------------------

    def __getitem__(self, key: str) -> LineItem:
        """全科目から日本語ラベル・英語ラベル・local_name で検索する。

        照合順序:
          1. ``label_ja.text`` 完全一致
          2. ``label_en.text`` 完全一致
          3. ``local_name`` 完全一致

        最初にマッチした LineItem を返す。

        Args:
            key: 検索キー。

        Returns:
            マッチした LineItem。

        Raises:
            KeyError: 該当する科目が見つからない場合。
        """
        for item in self._items:
            if key in (item.label_ja.text, item.label_en.text, item.local_name):
                return item
        raise KeyError(key)

    def get(
        self, key: str, default: LineItem | None = None,
    ) -> LineItem | None:
        """科目を検索する。見つからなければ default を返す。

        Args:
            key: 検索キー（label_ja / label_en / local_name）。
            default: 見つからない場合の返却値。

        Returns:
            マッチした LineItem、または default。
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        """科目の存在確認。``"売上高" in stmts`` のように使う。

        Args:
            key: 検索キー。

        Returns:
            科目が存在すれば True。
        """
        if not isinstance(key, str):
            return False
        return self.get(key) is not None

    def __len__(self) -> int:
        """全科目数を返す。"""
        return len(self._items)

    def __iter__(self) -> Iterator[LineItem]:
        """全科目を順に返す。"""
        return iter(self._items)

    def search(self, keyword: str) -> list[LineItem]:
        """キーワードで部分一致検索する。

        ``label_ja.text``、``label_en.text``、``local_name`` のいずれかに
        keyword を含む全ての LineItem を返す。英語ラベル・local_name の
        照合は大文字小文字を区別しない。

        Args:
            keyword: 検索キーワード。

        Returns:
            マッチした LineItem のリスト（空の場合もある）。
        """
        keyword_lower = keyword.lower()
        results: list[LineItem] = []
        for item in self._items:
            if (
                keyword in item.label_ja.text
                or keyword_lower in item.label_en.text.lower()
                or keyword_lower in item.local_name.lower()
            ):
                results.append(item)
        return results

    # -- Feature 4 & 5: DataFrame 変換・エクスポート ----------------------------

    def to_dataframe(self):
        """全 LineItem を全カラム DataFrame に変換する。

        Returns:
            pandas DataFrame。全カラム（concept, label_ja, value 等）を含む。

        Raises:
            ImportError: pandas がインストールされていない場合。
        """
        from edinet.dataframe.facts import line_items_to_dataframe

        return line_items_to_dataframe(self._items)

    def to_csv(self, path: str | Path, **kwargs) -> None:
        """全 LineItem を CSV に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_csv()`` に渡す追加引数。
        """
        from edinet.dataframe.export import to_csv

        to_csv(self.to_dataframe(), path, **kwargs)

    def to_parquet(self, path: str | Path, **kwargs) -> None:
        """全 LineItem を Parquet に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_parquet()`` に渡す追加引数。
        """
        from edinet.dataframe.export import to_parquet

        to_parquet(self.to_dataframe(), path, **kwargs)

    def to_excel(self, path: str | Path, **kwargs) -> None:
        """全 LineItem を Excel に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_excel()`` に渡す追加引数。
        """
        from edinet.dataframe.export import to_excel

        to_excel(self.to_dataframe(), path, **kwargs)

    def __str__(self) -> str:
        """PL / BS / CF を連結して表示する。"""
        parts = [
            str(s)
            for s in (
                self.income_statement(),
                self.balance_sheet(),
                self.cash_flow_statement(),
            )
            if s.items
        ]
        return "\n\n".join(parts) if parts else "(財務諸表なし)"

    def income_statement(
        self,
        *,
        consolidated: bool = True,
        period: DurationPeriod | Literal["current", "prior"] | None = None,
        strict: bool = False,
    ) -> FinancialStatement:
        """損益計算書を組み立てる。

        選択ルール:
          1. period: None なら最新期間を選択
          2. consolidated: True なら連結を優先、連結がなければ個別にフォールバック
          3. dimensions: dimension なし（全社合計）の Fact のみを採用
          4. 重複: 同一 concept で上記ルール適用後も複数 Fact が残る場合は
             warnings.warn() で警告
          5. 並び順: display_order に従う

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの損益計算書。
        """
        resolved = self._resolve_period_variant(
            period, StatementType.INCOME_STATEMENT,
        )
        return self._build_for_type(
            StatementType.INCOME_STATEMENT,
            consolidated=consolidated,
            period=resolved,
            strict=strict,
        )

    def balance_sheet(
        self,
        *,
        consolidated: bool = True,
        period: InstantPeriod | Literal["current", "prior"] | None = None,
        strict: bool = False,
    ) -> FinancialStatement:
        """貸借対照表を組み立てる。

        BS は InstantPeriod（時点）を使用する。
        選択ルールは income_statement() と同一。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象時点。``"current"`` / ``"prior"`` で当期末/前期末を
                DEI ベースで自動選択。None なら最新時点を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの貸借対照表。
        """
        resolved = self._resolve_period_variant(
            period, StatementType.BALANCE_SHEET,
        )
        return self._build_for_type(
            StatementType.BALANCE_SHEET,
            consolidated=consolidated,
            period=resolved,
            strict=strict,
        )

    def cash_flow_statement(
        self,
        *,
        consolidated: bool = True,
        period: DurationPeriod | Literal["current", "prior"] | None = None,
        strict: bool = False,
    ) -> FinancialStatement:
        """キャッシュフロー計算書を組み立てる。

        選択ルールは income_statement() と同一。

        J-GAAP の場合、期首残高・期末残高（``CashAndCashEquivalents``、
        ``periodType="instant"``）が自動的に先頭・末尾に挿入される。

        Note:
            期首残高と期末残高は同一の ``local_name``
            (``"CashAndCashEquivalents"``) を持つため、
            ``cf["CashAndCashEquivalents"]`` は期首（先頭）のみ返す。
            期末残高は日本語ラベルで取得すること::

                ending = cf["現金及び現金同等物の期末残高"]

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みのキャッシュフロー計算書。
        """
        resolved = self._resolve_period_variant(
            period, StatementType.CASH_FLOW_STATEMENT,
        )
        return self._build_for_type(
            StatementType.CASH_FLOW_STATEMENT,
            consolidated=consolidated,
            period=resolved,
            strict=strict,
        )

    def equity_statement(
        self,
        *,
        consolidated: bool = True,
        period: DurationPeriod | Literal["current", "prior"] | None = None,
        strict: bool = False,
    ) -> FinancialStatement:
        """株主資本等変動計算書を組み立てる。

        ConceptSet（Presentation Linkbase 自動導出）により SS の
        全科目を取得する。taxonomy_root が未設定の場合は空を返す。

        Note:
            SS のタクソノミ定義は 5 業種（cai, edu, inv, liq, med）のみ。
            未定義の業種では空の FinancialStatement を返す。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの株主資本等変動計算書。
        """
        resolved = self._resolve_period_variant(
            period, StatementType.STATEMENT_OF_CHANGES_IN_EQUITY,
        )
        return self._build_for_type(
            StatementType.STATEMENT_OF_CHANGES_IN_EQUITY,
            consolidated=consolidated,
            period=resolved,
            strict=strict,
        )

    def comprehensive_income(
        self,
        *,
        consolidated: bool = True,
        period: DurationPeriod | Literal["current", "prior"] | None = None,
        strict: bool = False,
    ) -> FinancialStatement:
        """包括利益計算書を組み立てる。

        ConceptSet（Presentation Linkbase 自動導出）により CI の
        全科目を取得する。taxonomy_root が未設定の場合は空を返す。

        Note:
            CI のタクソノミ定義は 1 業種（cai）のみ。
            未定義の業種では空の FinancialStatement を返す。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの包括利益計算書。
        """
        resolved = self._resolve_period_variant(
            period, StatementType.COMPREHENSIVE_INCOME,
        )
        return self._build_for_type(
            StatementType.COMPREHENSIVE_INCOME,
            consolidated=consolidated,
            period=resolved,
            strict=strict,
        )


def build_statements(
    items: Sequence[LineItem],
    *,
    facts: tuple[RawFact, ...] | None = None,
    contexts: dict[str, StructuredContext] | None = None,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,
    resolver: TaxonomyResolver | None = None,
    calculation_linkbase: CalculationLinkbase | None = None,
    definition_linkbase: dict[str, DefinitionTree] | None = None,
    definition_parent_index: dict[str, str] | None = None,
    source_path: str | None = None,
) -> Statements:
    """LineItem 群から Statements コンテナを構築する。

    全 LineItem をそのまま保持し、``income_statement()`` 等の
    メソッド呼び出し時に選択ルールを適用する。

    Args:
        items: ``build_line_items()`` が返した LineItem のシーケンス。
        facts: 元の RawFact タプル（会計基準判別・US-GAAP 抽出用）。
        contexts: ``structure_contexts()`` の戻り値（US-GAAP 抽出用）。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード（例: ``"bk1"``）。
            ``None`` は一般事業会社として扱う。
        resolver: 提出者ラベルロード済みの TaxonomyResolver。
            セグメント分析等の事後ラベル解決に使用する。
        calculation_linkbase: 提出者の Calculation Linkbase。
            ``extract_values()`` の ``calc_mapper`` が使用する。
        definition_linkbase: 提出者の Definition Linkbase。
            ``extract_values()`` の ``definition_mapper`` が使用する。
        definition_parent_index: 事前計算済みの parent index。
            Parquet 復元時に ``_build_parent_index()`` の結果を直接渡す。
            ``None``（デフォルト）なら ``definition_linkbase`` から導出する。
        source_path: 元の XBRL ファイルパス（ZIP 内パス）。

    Returns:
        Statements コンテナ。
    """
    detected = detect_accounting_standard(facts) if facts else None
    dei = None
    if facts:
        from edinet.xbrl.dei import extract_dei

        dei = extract_dei(facts)
    return Statements(
        _items=tuple(items),
        _detected_standard=detected,
        _facts=facts,
        _contexts=contexts,
        _taxonomy_root=taxonomy_root,
        _industry_code=industry_code,
        _dei=dei,
        _resolver=resolver,
        _calculation_linkbase=calculation_linkbase,
        _definition_linkbase=definition_linkbase,
        _definition_parent_index=definition_parent_index,
        _source_path=source_path,
    )

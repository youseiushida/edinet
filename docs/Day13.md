# Day 13 — Fact → LineItem 変換

## 0. 位置づけ

Day 13 は、Day 9 で抽出した `RawFact` と Day 10 の `StructuredContext`、Day 12 の `TaxonomyResolver` を結合し、**型付き・ラベル付きの `LineItem` オブジェクトを生成する** 日。

Day 12 完了時点の状態:
- `parse_xbrl_facts()` が `ParsedXBRL` を返す（`RawFact` + `RawContext` + `RawUnit`）
- `structure_contexts()` が `dict[str, StructuredContext]` を返す（期間・Entity・Dimension を型付きで引ける）
- `TaxonomyResolver` が concept → `LabelInfo` を解決できる（標準 + 提出者ラベル）
- `facts.py` は 1 行の docstring のみ（未実装）
- `models/financial.py` は 1 行の docstring のみ（未実装）

Day 13 完了時のマイルストーン:

```python
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.facts import build_line_items

parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)
resolver = TaxonomyResolver("/path/to/ALL_20251101")
resolver.load_filer_labels(filer_lab_bytes, filer_lab_en_bytes, xsd_bytes=filer_xsd_bytes)

items = build_line_items(parsed.facts, ctx_map, resolver)

for item in items:
    print(f"{item.label_ja.text}: {item.value} {item.unit_ref}")
    # "売上高: 1000000000 JPY"
    print(f"  context={item.context_id}, period={item.period}")
    print(f"  dimensions={item.dimensions}")
    print(f"  source={item.label_ja.source}")  # LabelSource.STANDARD
```

CODESCOPE.md §4 で定義された責務（F-1〜F-4）を実装し、スコープ外（FN-1〜FN-3）は実装しない。

---

## 1. 現在実装の確認結果

| ファイル | 現状 | Day 13 で必要な変更 |
|---|---|---|
| `src/edinet/xbrl/facts.py` | 1 行 docstring のみ | 新規実装。`build_line_items()` + `_convert_value()` |
| `src/edinet/models/financial.py` | 1 行 docstring のみ | 新規実装。`LineItem` データモデル |
| `src/edinet/xbrl/__init__.py` | `parse_xbrl_facts`, `structure_contexts`, `TaxonomyResolver` をエクスポート | `build_line_items` を追加エクスポート |
| `tests/test_xbrl/test_facts.py` | 未作成 | 新規作成 |
| `tests/fixtures/xbrl_fragments/simple_pl.xbrl` | Context 4 件（Duration 2 件 + Instant 1 件 + Dimension 付き 1 件）、Fact 10 件（数値 6 + テキスト 2 + nil 2） | 変更なし（十分なカバレッジ） |
| `stubs/edinet/xbrl/facts.pyi` | 空（docstring のみ） | stubgen で生成 |
| `stubs/edinet/models/financial.pyi` | 空（docstring のみ） | stubgen で生成 |

補足:
- `RawFact` のフィールド一覧（parser.py L63-75）: `concept_qname`, `namespace_uri`, `local_name`, `context_ref`, `unit_ref`, `decimals`, `value_raw`, `is_nil`, `fact_id`, `xml_lang`, `source_line`, `order`, `value_inner_xml`（デフォルト `None`）。`value_inner_xml` は末尾にデフォルト値付きで定義されている（L75: `value_inner_xml: str | None = None`）。
- `simple_pl.xbrl` の Fact 一覧（Fact 番号 → context → type）:
  - Fact 1: `jppfs_cor:NetSales` → `CurrentYearDuration` → 数値（`1000000000`, decimals="-6"）
  - Fact 2: `jppfs_cor:OperatingIncome` → `CurrentYearDuration` → 数値（`-500000000`, decimals="-6", id="fact-002"）
  - Fact 3: `jppfs_cor:NumberOfSharesIssued` → `CurrentYearInstant` → 数値（`12345678`, decimals="INF"）
  - Fact 4: `jppfs_cor:ExtraordinaryLoss` → `CurrentYearDuration` → nil 数値
  - Fact 5: `jpdei_cor:FilerNameInJapaneseDEI` → `CurrentYearDuration` → テキスト（`"テスト株式会社"`）
  - Fact 6: `jpdei_cor:SecurityCodeDEI` → `CurrentYearDuration` → nil テキスト
  - Fact 7: `jppfs_cor:TotalAssets` → `CurrentYearInstant` → 数値（`9876543210`, decimals="0"）
  - Fact 8: `jpigp_cor:Revenue` → `CurrentYearDuration` → 数値（`2000000000`, decimals="-6"）
  - Fact 9: `jppfs_cor:NetSales` → `CurrentYearInstant` → 数値（`1100000000`, decimals="-6"）
  - Fact 10: `jppfs_cor:NotesRegarding...TextBlock` → `CurrentYearDuration` → テキスト（HTML 含む）
- `simple_pl.xbrl` には Dimension 付き Context `CurrentYearDuration_NonConsolidatedMember` が存在するが、この Context を参照する Fact は存在しない。P0-7（dimensions テスト）では in-memory で RawFact を構築する（§7.3 参照）
- `taxonomy_mini` は `jppfs_cor` のラベルのみ保持（targetNamespace: `2025-11-01`）。`jpdei_cor` / `jpigp_cor` のラベルは含まれないため、これらの concept は FALLBACK になる（テストで意識する）。**重要**: `simple_pl.xbrl` の namespace URI は `2023-11-01` であり `taxonomy_mini` の `2025-11-01` と不一致。in-memory テストでは `2025-11-01` を使い、統合テストでは FALLBACK を期待すること

---

## 2. ゴール

1. `RawFact` + `StructuredContext` + `TaxonomyResolver` から `LineItem` を生成する関数 `build_line_items()` を実装する
2. `LineItem` を `models/financial.py` に frozen dataclass として定義する
3. 数値 Fact（`unitRef` あり）は `value: Decimal` に変換する
4. テキスト Fact（`unitRef` なし）は `value: str` のまま保持する
5. nil Fact は `value: None` として保持する
6. 日本語・英語の `LabelInfo` をトレース可能な形で `LineItem` に保持する（`str` に潰さない）
7. `context_id` / `period` / `entity_id` / `dimensions` を保持し、選択根拠のトレーサビリティを確保する

---

## 3. スコープ / 非スコープ

### 3.1 Day 13 のスコープ

CODESCOPE.md §4 の処理する項目（F-1〜F-4）に対応:

| CODESCOPE | 内容 | Day 13 での実装 |
|---|---|---|
| F-1 | 数値変換 | `unitRef` がある非 nil Fact の `value_raw: str` → `Decimal` 変換。parser.py S-10 で lexical 妥当性は検証済みのため安全に成功する前提 |
| F-2 | ラベル付与 | `TaxonomyResolver.resolve_clark()` で日本語・英語ラベルを取得し `LabelInfo` として保持 |
| F-3 | context_id 保持 | `RawFact.context_ref` をそのまま `LineItem.context_id` に転写 |
| F-4 | dimensions 保持 | `StructuredContext.dimensions` を `LineItem.dimensions` に転写 |

### 3.2 Day 13 でやらないこと

CODESCOPE.md §4 のスコープ外（FN-1〜FN-3）:

| CODESCOPE | 内容 | やらない理由 |
|---|---|---|
| FN-1 | 日付型（dateItemType）の変換 | タクソノミ XSD の `type` 属性なしでは数値 Fact と日付テキスト Fact を区別できない（A-3.5）。`unitRef` の有無で数値は判別可能だが、日付はタクソノミ連携が必要 |
| FN-2 | Boolean 型（booleanItemType）の変換 | 同上 |
| FN-3 | テキスト Fact の型変換 | テキストはそのまま `str` で保持する。型変換はタクソノミ連携後（v0.2.0+）に行う |

Day 13 でやらないその他:
- `FinancialStatement` / `StatementType` の定義（→ Day 15）
- Fact 選択ルール（期間・連結フィルタ）の実装（→ Day 15）
- 科目の PL/BS/CF 分類（→ Day 15）
- `to_dataframe()` の実装（→ Day 16）
- ZIP から `_lab.xml` を自動抽出する導線（→ Day 17 E2E 統合）

---

## 4. QA 反映方針（Day 13 に直結するもの）

| QA | Day 13 への反映 |
|---|---|
| A-3 | Fact の値は常に円単位（百万円単位ではない）。`decimals="-6"` は精度ヒントであり、`value_raw` の数値がそのまま円の値。`LineItem.value` に `Decimal(value_raw)` をそのまま格納し、スケーリングはしない |
| A-3.3 | `xsi:nil="true"` の Fact は `is_nil=True`、`value_raw=None`。`LineItem` には `value=None` として保持 |
| A-3.6 | 非 nil 空値は parser.py S-9 で検証済み。Day 13 では到達しない前提 |
| A-3.8 | 数値の lexical 妥当性は parser.py S-10 で検証済み。`Decimal(value_raw)` は安全に成功する前提 |
| E-6 | 提出者拡張科目のラベルは `TaxonomyResolver.load_filer_labels()` で事前に読み込まれている前提。`resolve_clark()` で解決し、見つからなければ `LabelSource.FALLBACK` で `local_name` を返す |
| E-7 | 主要勘定科目（NetSales, OperatingIncome 等）の concept 名はテストフィクスチャで網羅的に検証する |
| C-5.5 | ラベル解決のフォールバック（指定 role → 標準ラベル → local name）は TaxonomyResolver 側の責務。Day 13 は `resolve_clark()` を呼ぶだけ |

---

## 5. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/models/financial.py` | 新規実装 | `LineItem` データモデル定義 |
| `src/edinet/xbrl/facts.py` | 新規実装 | `build_line_items()` + `_convert_value()` |
| `src/edinet/xbrl/__init__.py` | 追記 | `build_line_items` を追加エクスポート |
| `tests/test_xbrl/test_facts.py` | 新規作成 | Small/Unit + Medium/Integration テスト |
| `stubs/edinet/xbrl/facts.pyi` | 生成 | stubgen で自動生成 |
| `stubs/edinet/models/financial.pyi` | 生成 | stubgen で自動生成 |

---

## 6. データモデル設計

### 6.1 LineItem

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from edinet.xbrl.contexts import DimensionMember, Period  # Period は contexts.py __all__ に含まれている（L23、確認済み）
from edinet.xbrl.taxonomy import LabelInfo


@dataclass(frozen=True, slots=True)
class LineItem:
    """型付き・ラベル付きの XBRL Fact。

    RawFact + StructuredContext + TaxonomyResolver から生成される、
    下流（Day 15 の FinancialStatement 組み立て等）が消費する主要データ型。

    Attributes:
        concept: Clark notation の QName（例: ``"{ns}NetSales"``）。
            RawFact.concept_qname をそのまま引き継ぐ。
        namespace_uri: 名前空間 URI。
        local_name: ローカル名（例: ``"NetSales"``）。
        label_ja: 日本語ラベル情報。TaxonomyResolver から取得。
        label_en: 英語ラベル情報。TaxonomyResolver から取得。
        value: 変換済みの値。数値 Fact は ``Decimal``、テキスト Fact は ``str``、
            nil Fact は ``None``。テキスト Fact の値は ``RawFact.value_raw``
            （``itertext()`` によるタグ除去済みプレーンテキスト）を使用する。
            HTML タグを含む原文が必要な場合は ``RawFact.value_inner_xml`` を
            直接参照すること（TextBlock 等、v0.2.0 の ``text_blocks`` モジュールで対応予定）。
        unit_ref: unitRef 属性値。テキスト Fact は ``None``。
        decimals: decimals 属性値。``int`` / ``"INF"`` / ``None``。
        context_id: contextRef 属性値（トレーサビリティ用）。
        period: StructuredContext から転写した期間情報。
        entity_id: StructuredContext から転写した Entity ID。
        dimensions: StructuredContext から転写した Dimension 情報。
        is_nil: xsi:nil が真かどうか。
        source_line: 元 XML の行番号。
        order: 元文書内の出現順。
    """
    concept: str
    namespace_uri: str
    local_name: str
    label_ja: LabelInfo
    label_en: LabelInfo
    value: Decimal | str | None
    unit_ref: str | None
    decimals: int | Literal["INF"] | None
    context_id: str
    period: Period
    entity_id: str
    dimensions: tuple[DimensionMember, ...]
    is_nil: bool
    source_line: int | None
    order: int
```

### 6.2 設計判断

1. **`value` を `Decimal | str | None` の Union にする理由**: CODESCOPE.md §4 の方針に従い、`unitRef` の有無だけで数値/テキストを判別する。タクソノミ型情報なしでは dateItemType や booleanItemType を区別できない（FN-1〜FN-3）。Union にすることで Day 15 で `isinstance(item.value, Decimal)` による数値フィルタが自然にできる。v0.2.0 でタクソノミ型参照を導入し dateItemType / booleanItemType を区別する際、`value` の型を拡張する可能性がある（`Decimal | str | date | bool | None`）。frozen dataclass の Union フィールドなら後方互換で拡張可能

2. **`value` に `None` を許容する理由**: `xsi:nil="true"` の Fact は概念上「値なし」を明示的に表現している。CODESCOPE.md §5 SN-1 の「欠損科目の補填」とは異なり、「Fact は存在するが値がない」状態を型で表現する。Day 15 の Statement 組み立てでは `value is None` の LineItem はスキップする

3. **frozen dataclass にする理由**: PLAN.LIVING.md Day 13 で「Pydantic モデルは frozen=True を検討」と指示。LineItem は生成後に変更される理由がなく、イミュータブルにすることでハッシュ可能になり集合演算やキャッシュに使える。Pydantic ではなく plain dataclass を使う理由は、parser.py / contexts.py と統一するため（RawFact, StructuredContext も frozen dataclass）

4. **`label_ja` / `label_en` を `LabelInfo` 型で保持する理由**: PLAN.LIVING.md §4 および Day 13 の [信頼性] 指示で明確に「`str` に潰さない」「role と source を残すこと」と指定されている。TaxonomyResolver から受け取った LabelInfo をそのまま格納する

5. **`context_id` と `dimensions` を保持する理由**: PLAN.LIVING.md Day 13 の [信頼性] で「Fact → LineItem 変換時にこれらを落とすと、後から『なぜこの値なのか』が説明できなくなる」と明記。同一 concept に連結/個別/セグメント別で異なる値が存在するため、選択根拠のトレースは信頼性の根幹

6. **`period` と `entity_id` を LineItem に持たせる理由**: Day 15 の Statement 組み立てで期間フィルタが必要。`ctx_map[item.context_id].period` で毎回引くより、直接アクセスできる方が下流で扱いやすい。StructuredContext の情報を重複保持するが、frozen dataclass のフィールド追加はメモリコストが軽微。**注意**: `Period` は型エイリアス（`InstantPeriod | DurationPeriod`）であり runtime では `types.UnionType` オブジェクトになるため、`isinstance(item.period, Period)` は使えない。Day 15 で期間の種別判定が必要な場合は `isinstance(item.period, InstantPeriod)` のように具体型を使うこと

7. **`order` を保持する理由**: 元文書内の出現順は presentation linkbase がない v0.1.0 で、JSON 定義にない科目の並び順に使う（CODESCOPE.md §5 ST-3「JSON にない科目は末尾に出現順で追加」）

8. **`decimals` の型を `int | Literal["INF"] | None` にする理由**: RawFact.decimals と同一の型。`"INF"` を `float("inf")` に変換しない理由は、XBRL 仕様上 `decimals="INF"` は文字列リテラルであり、数学的な無限大とは概念が異なる。RawFact からの透過的な転写を優先する

9. **`__repr__` はデフォルトのまま**: dataclass のデフォルト `__repr__` は全フィールドを出力する。Clark notation の長い URI が混ざると REPL での視認性が落ちる可能性があるが、v0.1.0 ではデフォルトで十分。Day 16 の Rich 表示で `LineItem.__rich_repr__()` を検討する余地はあるが、Day 13 では不要（additive change）

10. **`value_inner_xml` を LineItem に持たせない理由**: RawFact には `value_inner_xml`（HTML タグを含む生の XML 断片）が存在するが、LineItem には不要。テキストブロックの HTML 保持は FEATURES.md の `text_blocks` モジュールの責務。LineItem は `value_raw`（`itertext()` によるタグ除去済みテキスト）を `str` として保持するだけで十分。v0.2.0 で `text_blocks` 実装時に `RawFact.value_inner_xml` を直接参照する導線を用意する。**注意**: TextBlock Fact では `value_raw`（プレーンテキスト）と `value_inner_xml`（HTML タグ付き原文）が異なるため、下流で HTML が必要な場合は `RawFact` を直接参照する必要がある

---

## 7. `build_line_items()` 関数設計

### 7.1 公開 I/F

```python
from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from edinet.exceptions import EdinetParseError
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import StructuredContext
from edinet.xbrl.parser import RawFact
from edinet.xbrl.taxonomy import TaxonomyResolver

logger = logging.getLogger(__name__)

__all__ = ["build_line_items"]


def build_line_items(
    facts: Sequence[RawFact],
    context_map: dict[str, StructuredContext],
    resolver: TaxonomyResolver,
) -> tuple[LineItem, ...]:
    """RawFact 群を LineItem 群に変換する。

    全 RawFact を LineItem に変換する。フィルタは行わない
    （「データは広く持ち、フィルタは遅く」の原則）。

    Args:
        facts: ``parse_xbrl_facts()`` が抽出した RawFact のシーケンス。
        context_map: ``structure_contexts()`` が返した Context 辞書。
        resolver: ラベル解決用の TaxonomyResolver。
            提出者ラベルは呼び出し側で事前に
            ``load_filer_labels()`` しておくこと。

    Returns:
        変換された LineItem のタプル。入力の facts と同じ順序を保持する。

    Raises:
        EdinetParseError: ``context_ref`` が ``context_map`` に
            見つからない RawFact が存在した場合。

    Note:
        - 数値 Fact（``unit_ref is not None`` かつ非 nil）は
          ``Decimal(value_raw)`` に変換する。parser.py S-10 で
          lexical 妥当性は検証済みのため安全に成功する前提。
        - テキスト Fact（``unit_ref is None``）は ``value_raw`` を
          そのまま ``str`` で保持する。
        - nil Fact は ``value=None`` となる。
    """
    ...
```

### 7.2 内部実装方針

```python
def build_line_items(facts, context_map, resolver):
    items: list[LineItem] = []
    for fact in facts:
        # 1. Context 解決
        ctx = context_map.get(fact.context_ref)
        if ctx is None:
            raise EdinetParseError(
                f"Fact '{fact.local_name}' (line {fact.source_line}): "
                f"context_ref '{fact.context_ref}' not found in context_map"
            )

        # 2. ラベル解決
        label_ja = resolver.resolve_clark(fact.concept_qname, lang="ja")
        label_en = resolver.resolve_clark(fact.concept_qname, lang="en")

        # 3. 値の変換
        value = _convert_value(fact)

        # 4. LineItem 構築
        item = LineItem(
            concept=fact.concept_qname,
            namespace_uri=fact.namespace_uri,
            local_name=fact.local_name,
            label_ja=label_ja,
            label_en=label_en,
            value=value,
            unit_ref=fact.unit_ref,
            decimals=fact.decimals,
            context_id=fact.context_ref,
            period=ctx.period,
            entity_id=ctx.entity_id,
            dimensions=ctx.dimensions,
            is_nil=fact.is_nil,
            source_line=fact.source_line,
            order=fact.order,
        )
        items.append(item)

    logger.info("LineItem を構築: %d 件（入力 Fact: %d 件）", len(items), len(facts))
    return tuple(items)


def _convert_value(fact: RawFact) -> Decimal | str | None:
    """RawFact の値を適切な型に変換する。

    Args:
        fact: 変換対象の RawFact。

    Returns:
        - nil Fact → ``None``
        - 数値 Fact（``unit_ref is not None``）→ ``Decimal``
        - テキスト Fact（``unit_ref is None``）→ ``str``

    Raises:
        EdinetParseError: 数値 Fact の値が Decimal に変換できない場合、
            または非 nil テキスト Fact の ``value_raw`` が ``None`` の場合。
            いずれも parser.py S-9/S-10 で保証済みのため、
            到達した場合は parser.py のバグ。
    """
    # nil Fact: 数値・テキストに関わらず None
    if fact.is_nil:
        return None

    # テキスト Fact: unit_ref がなければテキストとして扱う
    if fact.unit_ref is None:
        # parser.py S-9 により非 nil Fact の value_raw=None は到達しないはず。
        # 数値 Fact の Decimal 変換と同様に、parser.py のバグを検知するため
        # fail-fast で EdinetParseError にする。
        if fact.value_raw is None:
            raise EdinetParseError(
                f"Fact '{fact.local_name}' (line {fact.source_line}): "
                f"non-nil text fact has value_raw=None"
            )
        return fact.value_raw

    # 数値 Fact: Decimal に変換
    #   parser.py S-9 により非 nil Fact の value_raw=None は到達しないはず。
    #   テキスト Fact の防御チェックと対称に、明示的にチェックする。
    if fact.value_raw is None:
        raise EdinetParseError(
            f"Fact '{fact.local_name}' (line {fact.source_line}): "
            f"non-nil numeric fact has value_raw=None"
        )
    #   parser.py S-10 で lexical 妥当性検証済みのため
    #   InvalidOperation は発生しないはず。
    #   発生した場合は parser.py のバグとして EdinetParseError にする。
    try:
        return Decimal(fact.value_raw)
    except InvalidOperation as e:
        raise EdinetParseError(
            f"Fact '{fact.local_name}' (line {fact.source_line}): "
            f"failed to convert value to Decimal: {fact.value_raw!r}"
        ) from e
```

ロガー規約:
- `build_line_items()` では `logger.info()` で変換結果のサマリー（「LineItem を構築: N 件」）を出力する。parser.py は `logging` 未使用（`warnings.warn()` のみ）だが、contexts.py / taxonomy.py で `logging` パターンが確立されているため、facts.py もこれに従う
- `_convert_value()` 内部では logging は不要（1 件ずつのログは大量出力になるため）

### 7.3 変換ルール

```
入力: RawFact 1 件 + StructuredContext + TaxonomyResolver
出力: LineItem 1 件

1. Context 解決:
   context_map[fact.context_ref] → StructuredContext
   → 見つからない場合: EdinetParseError

2. ラベル解決:
   resolver.resolve_clark(fact.concept_qname, lang="ja") → label_ja
   resolver.resolve_clark(fact.concept_qname, lang="en") → label_en
   → resolve_clark() は内部で FALLBACK を返すためエラーにはならない

3. 値の変換:
   is_nil == True           → value = None
   unit_ref is not None     → value = Decimal(value_raw)
   unit_ref is None         → value = value_raw（str）
                              ※ 非 nil かつ value_raw=None は EdinetParseError（parser.py バグ検知）

4. フィールドマッピング:
   LineItem.concept        ← fact.concept_qname
   LineItem.namespace_uri  ← fact.namespace_uri
   LineItem.local_name     ← fact.local_name
   LineItem.label_ja       ← 手順 2 の結果
   LineItem.label_en       ← 手順 2 の結果
   LineItem.value          ← 手順 3 の結果
   LineItem.unit_ref       ← fact.unit_ref
   LineItem.decimals       ← fact.decimals
   LineItem.context_id     ← fact.context_ref
   LineItem.period         ← ctx.period
   LineItem.entity_id      ← ctx.entity_id
   LineItem.dimensions     ← ctx.dimensions
   LineItem.is_nil         ← fact.is_nil
   LineItem.source_line    ← fact.source_line
   LineItem.order          ← fact.order

※ order は parser.py 内で 0-indexed の文書出現順として付番される
  （_extract_facts() 内の `order = 0` から開始し、Fact 抽出のたびに +1）。
```

### 7.4 エラー処理方針

**Fail-fast 方針**: 1 つの Fact の変換失敗で `EdinetParseError` を raise し、残りの Fact も含め全体を失敗させる。best-effort で一部だけ返すと下流（Day 15 の Statement 組み立て等）が「一部の科目だけ欠落した PL」を生成するリスクがある。

メッセージの言語方針（contexts.py / taxonomy.py と同一）:
- **例外メッセージ**: 英語で統一する（`EdinetParseError` のメッセージ）
- **ログメッセージ**: 日本語で統一する（`logger.info()` 等。例: `"LineItem を構築: %d 件"`）

| 状況 | 処理 |
|---|---|
| `context_ref` が `context_map` に不在 | `EdinetParseError`（`"Fact 'NetSales' (line 44): context_ref 'XXX' not found in context_map"`）。parser.py S-5 で contextRef の存在は保証されているが、`structure_contexts()` のエラーで Context が欠落している可能性がある |
| `Decimal(value_raw)` が `InvalidOperation` | `EdinetParseError`（`"Fact 'NetSales' (line 44): failed to convert value to Decimal: 'abc'"`）。parser.py S-10 で検証済みのため到達しないはず。到達した場合は parser.py のバグ |
| 数値 Fact で `value_raw=None` | `EdinetParseError`（`"non-nil numeric fact has value_raw=None"`）。`Decimal()` 呼び出し前に明示チェック。テキスト Fact の防御チェックと対称。parser.py S-9 により到達しないはず |
| 非 nil テキスト Fact で `value_raw=None` | `EdinetParseError`（`"non-nil text fact has value_raw=None"`）。数値 Fact の防御チェックと対称。parser.py S-9 により到達しないはずだが、parser.py のバグを即座に検知する |
| `resolve_clark()` が FALLBACK を返す | 正常動作。エラーにしない。提出者拡張科目でラベル未登録の場合に `local_name` がラベルになる |
| 空の `facts` 入力 | 空の `tuple[()]` を返す。エラーにしない |

### 7.5 公開エクスポート方針

- `edinet.xbrl`（`__init__.py`）に `build_line_items` を追加エクスポート
- `LineItem` は `edinet.models.financial` からの明示 import でのみ利用可能とし、`edinet.xbrl` からは再エクスポートしない（models と xbrl の責務分離）
- `facts.py` に `__all__` を定義する:
  ```python
  __all__ = ["build_line_items"]
  ```
- `models/financial.py` にも `__all__` を定義する:
  ```python
  __all__ = ["LineItem"]
  ```

---

## 8. テスト計画

### 8.1 テスト用フィクスチャの方針

**テスト内で in-memory フィクスチャを生成する方式** を主とする。理由:
- `build_line_items()` の入力は `RawFact` / `StructuredContext` / `TaxonomyResolver` であり、XML ファイルではない
- RawFact / StructuredContext を直接構築することでテストの意図が明確になる
- 既存フィクスチャ（`simple_pl.xbrl`）の変更が不要で、test_parser.py / test_contexts.py への影響がない

加えて、`simple_pl.xbrl` を使ったフルパイプライン統合テスト（parse → structure → build）を P1 として配置する。

### 8.2 テスト用ヘルパー

```python
"""test_facts.py — build_line_items() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.exceptions import EdinetParseError
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
)
from edinet.xbrl.facts import build_line_items
from edinet.xbrl.parser import RawFact, parse_xbrl_facts
from edinet.xbrl.taxonomy import LabelSource, TaxonomyResolver

from .conftest import TAXONOMY_MINI_DIR, load_xbrl_bytes

# テスト用名前空間（taxonomy_mini の XSD targetNamespace と一致させること）
# ※ simple_pl.xbrl は 2023-11-01 を使用しているが、in-memory テストでは
#    taxonomy_mini（2025-11-01）に合わせないと resolver が FALLBACK になる。
#    統合テスト P1-7 では simple_pl.xbrl の namespace（2023-11-01）を使うため、
#    resolver が FALLBACK を返す点をテスト期待値に反映すること。
_NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
_NS_JPDEI = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2025-11-01/jpdei_cor"


def _make_fact(
    *,
    local_name: str = "NetSales",
    namespace_uri: str = _NS_JPPFS,
    context_ref: str = "CurrentYearDuration",
    unit_ref: str | None = "JPY",
    decimals: int | str | None = -6,
    value_raw: str | None = "1000000000",
    is_nil: bool = False,
    fact_id: str | None = None,
    xml_lang: str | None = None,
    source_line: int | None = 1,
    order: int = 0,
    value_inner_xml: str | None = None,
) -> RawFact:
    """テスト用 RawFact を構築するヘルパー。"""
    return RawFact(
        concept_qname=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=unit_ref,
        decimals=decimals,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=fact_id,
        xml_lang=xml_lang,
        source_line=source_line,
        order=order,
        value_inner_xml=value_inner_xml,
    )


def _make_ctx(
    *,
    context_id: str = "CurrentYearDuration",
    period: DurationPeriod | InstantPeriod | None = None,
    entity_id: str = "E00001",
    dimensions: tuple[DimensionMember, ...] = (),
    source_line: int | None = 1,
) -> StructuredContext:
    """テスト用 StructuredContext を構築するヘルパー。"""
    if period is None:
        period = DurationPeriod(
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
    return StructuredContext(
        context_id=context_id,
        period=period,
        entity_id=entity_id,
        dimensions=dimensions,
        source_line=source_line,
    )


def _make_ctx_map(
    *contexts: StructuredContext,
) -> dict[str, StructuredContext]:
    """テスト用 Context 辞書を構築するヘルパー。"""
    return {ctx.context_id: ctx for ctx in contexts}


@pytest.fixture()
def resolver() -> TaxonomyResolver:
    """taxonomy_mini フィクスチャを使った TaxonomyResolver。"""
    return TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)
```

### 8.3 テストケース（P0: 必須）

1. `test_numeric_fact_to_line_item` — 通常の数値 Fact（`NetSales`, `value_raw="1000000000"`, `decimals=-6`）が `Decimal("1000000000")` に変換されること。ラベル検証も包括的に行う: `label_ja.text == "売上高"`, `label_en.text == "Net sales"`, `label_ja.source == LabelSource.STANDARD`, `label_ja.role == ROLE_LABEL`, `label_ja.lang == "ja"`, `label_en.lang == "en"`。（旧 P0-11 の検証内容を統合）
2. `test_negative_numeric_value` — 負の数値（`value_raw="-500000000"`）が `Decimal("-500000000")` に正しく変換されること
3. `test_text_fact_to_line_item` — テキスト Fact（`unit_ref=None`, `value_raw="テスト株式会社"`）の `value` が `str` 型（`"テスト株式会社"`）のまま保持されること。`unit_ref` が `None`、`decimals` が `None` であること
4. `test_nil_numeric_fact` — `is_nil=True` + `unit_ref="JPY"` の Fact の `value` が `None` であること。`is_nil` が `True` であること
5. `test_nil_text_fact` — `is_nil=True` + `unit_ref=None` の Fact の `value` が `None` であること
6. `test_context_id_preserved` — `LineItem.context_id` が `RawFact.context_ref` と一致すること
7. `test_period_duration_from_context` — `DurationPeriod` の Context に紐づく Fact の `LineItem.period` が正しい `DurationPeriod` であること
8. `test_period_instant_from_context` — `InstantPeriod` の Context に紐づく Fact の `LineItem.period` が正しい `InstantPeriod` であること
9. `test_dimensions_from_context` — Dimension 付き Context（`NonConsolidatedMember`）に紐づく Fact の `LineItem.dimensions` が `(DimensionMember(axis=..., member=...),)` であること。in-memory で構築した RawFact + StructuredContext を使用する。**注意**: このテストは dimensions の転写を検証するものであり、ラベルの検証は行わない。in-memory の namespace URI が `_NS_JPPFS`（`2025-11-01`）であれば resolver は STANDARD を返すが、dimensions テストとしてはラベル検証は不要
10. `test_dimensions_empty_when_no_scenario` — Dimension なし Context の Fact の `LineItem.dimensions` が `()` であること
11. `test_order_preserved` — `build_line_items()` に 3 件の RawFact（`order=0, 1, 2`）を渡し、出力タプルの各要素が入力順を保持すること。検証は `[item.order for item in items] == [0, 1, 2]` かつ `items[i].order == i` で行い、出力タプルのインデックスと `order` フィールドの両方が入力順と一致することを確認する
12. `test_all_facts_converted_no_filter` — in-memory で 3 件程度（数値・テキスト・nil の混在）の RawFact を渡し、入力 Fact 数 = 出力 LineItem 数 であることを検証する。P1-7 の統合テスト（全 10 Fact）とは補完関係にあり、P0-12 は小規模な型混在の正確性、P1-7 はフル fixture でのパイプライン検証を担う
13. `test_entity_id_from_context` — `LineItem.entity_id` が対応する `StructuredContext.entity_id` と一致すること
14. `test_missing_context_raises` — `context_map` に存在しない `context_ref`（例: `"UnknownCtx"`）を持つ Fact で `EdinetParseError` が raise されること。`pytest.raises(match=r"UnknownCtx")` のように **固定値のみを match** し、メッセージ全体のフォーマットには依存しないこと（保守性のため）

### 8.4 テストケース（P1: 推奨）

1. `test_decimals_inf` — `decimals="INF"` が `LineItem.decimals` に `"INF"`（str）として保持されること
2. `test_decimals_zero` — `decimals=0` が `LineItem.decimals` に `0`（int）として保持されること
3. `test_fallback_label` — `TaxonomyResolver` がラベルを解決できない concept（`taxonomy_mini` に含まれない namespace）で `LabelSource.FALLBACK` になること。`label_ja.text` が `local_name` と一致すること。**前提確認済み**: `resolve_clark()` は `_ns_to_prefix` に namespace URI がない場合、`LabelInfo(text=local_name, source=LabelSource.FALLBACK)` を返す（taxonomy.py L276-280）
4. `test_empty_facts_returns_empty_tuple` — 空の `facts` を渡した場合、空の tuple `()` が返ること
5. `test_concept_and_namespace_preserved` — `LineItem.concept` が Clark notation（`"{ns}local"`）、`namespace_uri` / `local_name` がそれぞれ正しいこと
6. `test_source_line_preserved` — `LineItem.source_line` が `RawFact.source_line` と一致すること
7. `test_integration_with_simple_pl_fixture` — `simple_pl.xbrl` をフルパイプライン（`parse_xbrl_facts` → `structure_contexts` → `build_line_items`）で処理し、全 10 Fact が LineItem に変換されること。数値 Fact の `value` が `Decimal` 型、テキスト Fact が `str` 型であること。`@pytest.mark.medium` + `@pytest.mark.integration`。テスト内で前提条件を明示的に検証すること:
   ```python
   assert len(ctx_map) == 4  # 前提: structure_contexts() が全 4 Context をパース
   items = build_line_items(parsed.facts, ctx_map, resolver)
   assert len(items) == 10
   ```
   **注意**: `simple_pl.xbrl` の namespace URI は `2023-11-01` だが `taxonomy_mini` は `2025-11-01` のため、全ラベルが `LabelSource.FALLBACK` になる。このテストでは型変換と件数の検証を主眼とし、ラベルの source は FALLBACK を期待値とすること
8. `test_decimal_conversion_failure_raises` — `unit_ref` ありかつ `is_nil=False` なのに `value_raw` が数値でないケースで `EdinetParseError` が raise されること（parser.py S-10 のバグ検出テスト。in-memory で不正な RawFact を直接構築して検証）
9. `test_text_fact_value_raw_none_raises` — `unit_ref=None` かつ `is_nil=False` なのに `value_raw=None` のケースで `EdinetParseError` が raise されること（parser.py S-9 のバグ検出テスト。数値 Fact の防御チェックとの対称性を検証）

### 8.5 `pytest.mark.parametrize` の活用

以下のテストは `@pytest.mark.parametrize` で統合して関数増殖を防ぐ:

- P0-4 + P0-5 → `test_nil_fact_value_is_none` に **parametrize する**。ロジックが同一（`is_nil=True → value=None`）であり、parametrize が自然
- P0-7 + P0-8 → **個別に残す**。Context の構築（`DurationPeriod` vs `InstantPeriod`）が異なり、parametrize すると fixture が複雑化するため

### 8.6 marker 方針

- `small` + `unit`: in-memory RawFact / StructuredContext を使うテスト（P0 の全件、P1 の大半）
- `medium` + `integration`: `simple_pl.xbrl` fixture を使った 3 モジュール結合テスト（P1-7）
- P0 テストは全て `small` + `unit` で書ける（fixture ファイル不要）

---

## 9. 依存関係の確認

```
models/financial.py  ←  xbrl/facts.py  →  xbrl/parser.py (RawFact)
    (LineItem)              ↓                xbrl/contexts.py (StructuredContext, Period, DimensionMember)
                            ↓                xbrl/taxonomy.py (TaxonomyResolver, LabelInfo)
                     xbrl/__init__.py

新規依存: facts.py → {parser, contexts, taxonomy, models.financial}
既存モジュールへの変更: __init__.py へのエクスポート追加のみ
```

- `models/financial.py` は `contexts.py`（Period, DimensionMember）と `taxonomy.py`（LabelInfo）に依存する
- `facts.py` は `parser.py`（RawFact）、`contexts.py`（StructuredContext）、`taxonomy.py`（TaxonomyResolver）、`models/financial.py`（LineItem）に依存する
- 循環依存は発生しない（依存方向は一方通行: parser → contexts → facts → models）

---

## 10. 当日の作業手順（チェックリスト）

### Phase 1: データモデル（~15 分）

1. `src/edinet/models/financial.py` に `LineItem` frozen dataclass を定義する（§6.1）
2. `__all__ = ["LineItem"]` を定義する
3. docstring を Google Style（日本語）で書く
4. `from edinet.models.financial import LineItem` が成功することを確認する
5. `uv run ruff check src/edinet/models/financial.py` で lint pass を確認する

### Phase 2: 変換関数（~25 分）

1. `src/edinet/xbrl/facts.py` に `_convert_value()` を実装する（§7.2）
2. `build_line_items()` を実装する（§7.2）
3. `__all__ = ["build_line_items"]` を定義する
4. `logger = logging.getLogger(__name__)` を設定する
5. `src/edinet/xbrl/__init__.py` に `from edinet.xbrl.facts import build_line_items` を追加する
6. `from edinet.xbrl import build_line_items` が成功することを確認する
7. `uv run ruff check src/edinet/xbrl/facts.py` で lint pass を確認する

### Phase 3: テスト先行・実装（~40 分）

1. `tests/test_xbrl/test_facts.py` を作成する
2. テスト用ヘルパー（`_make_fact`, `_make_ctx`, `_make_ctx_map`, `resolver` fixture）を定義する（§8.2）
3. P0 テスト（§8.3、14 件）を実装する
4. `uv run pytest tests/test_xbrl/test_facts.py -v` で全件 pass を確認する
   - 失敗した場合: 実装を修正して再実行。P0 は全件 pass が必須
5. P1 テスト（§8.4、9 件）を実装する
6. `uv run pytest tests/test_xbrl/test_facts.py -v` で全件 pass を確認する

### Phase 4: 検証（~20 分）

1. `uv run pytest tests/test_xbrl/test_parser.py` — 既存テスト回帰なし
2. `uv run pytest tests/test_xbrl/test_contexts.py` — 既存テスト回帰なし
3. `uv run pytest tests/test_xbrl/test_taxonomy.py` — 既存テスト回帰なし
4. `uv run pytest` — 全テスト回帰なし
5. `uv run ruff check src tests` — 警告なし
6. `uv run stubgen src/edinet --include-docstrings -o stubs` — `.pyi` 生成
7. 生成された `stubs/edinet/xbrl/facts.pyi` と `stubs/edinet/models/financial.pyi` の diff を確認する
   - `facts.pyi` に `_convert_value` が含まれ**ない**ことを確認する（`__all__` が定義されていれば `stubgen` はそのメンバーのみを出力するため、`_` prefix の非公開関数は除外されるはず）
8. 手動スモーク: 実 filing 1 件で parse → structure → build の全パイプラインを実行し、LineItem の一覧が出力されることを確認する

```python
# 手動スモークのイメージ
# 注意: 日付は EDINET API で取得可能な過去の日付を使うこと
from edinet import documents
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.facts import build_line_items

filing = documents("2025-06-25", doc_type="120")[0]
path, xbrl_bytes = filing.fetch()
parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)
resolver = TaxonomyResolver("/path/to/ALL_20251101")

items = build_line_items(parsed.facts, ctx_map, resolver)

print(f"LineItem 数: {len(items)}")
for item in items[:10]:
    val = f"{item.value:>20,}" if isinstance(item.value, Decimal) else repr(item.value)
    print(f"  {item.label_ja.text}: {val} ({item.unit_ref}, decimals={item.decimals})")
    print(f"    concept={item.local_name}, period={item.period}, source={item.label_ja.source}")
```

9. REPL で `LineItem` の `repr()` を確認し、フィールドの視認性を目視チェックする（§6.2 設計判断 9 参照）

---

## 11. 受け入れ基準（Done の定義）

- `build_line_items()` が `RawFact` 群を受け取り `tuple[LineItem, ...]` を返す
- 数値 Fact（`unit_ref` あり）の `value` が `Decimal` 型になっている
- テキスト Fact（`unit_ref` なし）の `value` が `str` 型のまま保持されている
- nil Fact の `value` が `None` になっている
- `label_ja` / `label_en` が `LabelInfo` 型で、`role` / `source` / `lang` が正しい
- `context_id` が `RawFact.context_ref` と一致する
- `period` / `entity_id` / `dimensions` が `StructuredContext` から正しく転写されている
- 入力の Fact 数 = 出力の LineItem 数（フィルタなし）
- 出力の順序が入力の `facts` と同じ
- `context_ref` が `context_map` に不在の場合に `EdinetParseError` を返す
- P0 テスト（§8.3、14 件）が全て pass
- P1 テスト（§8.4、9 件）は同日完了が望ましい。特に P1-7（統合テスト）と P1-8（Decimal 変換失敗テスト）は堅牢性に重要
- 既存テストスイートが回帰なし
- ruff で警告なし
- `.pyi` が生成され LineItem / build_line_items の型情報が反映されている

---

## 12. 設計判断の記録（§6.2 からの再掲 + 追加）

1. **`build_line_items()` を関数として提供する理由**: parser.py の `parse_xbrl_facts()` と contexts.py の `structure_contexts()` に倣い、ステートレスな関数として提供する。クラスにする必要がない（状態を持たない純粋な変換）

2. **全 Fact を変換する理由**: PLAN.LIVING.md Day 15 の「データは広く持ち、フィルタは遅く」の原則に従う。PL/BS/CF のフィルタは Day 15 の Statement 組み立てで行う。`build_line_items()` では Fact を選別しない

3. **parser.py S-10 との関係**: parser.py が lexical 妥当性を検証済みなので、`Decimal(value_raw)` は安全に成功する前提。万一失敗した場合は parser.py のバグであり、`EdinetParseError` を raise する。`try-except` で握りつぶさない

4. **テキスト Fact も LineItem にする理由**: DEI 要素（企業名、証券コード等）もテキスト Fact として XBRL に含まれる。これらを LineItem として保持することで、Day 15 以降で DEI 情報を参照可能にする。テキスト Fact を無視すると DEI アクセスの導線がなくなる

5. **`context_ref` が `context_map` に不在の場合のエラー方針**: parser.py S-5 で contextRef の存在は保証されているが、`structure_contexts()` が特定の Context のパースに失敗した場合（日付フォーマット不正等）、`context_map` に含まれない可能性がある。この場合は `EdinetParseError` で明示的に失敗させる。警告 + スキップではなく、データの欠落を利用者に通知する

6. **`LineItem` を `models/financial.py` に配置する理由**: PLAN.LIVING.md のプロジェクト構造に合わせる。`xbrl/facts.py` は「変換ロジック」を担い、`models/financial.py` は「データ型定義」を担う。型定義とロジックの分離は、Day 15 で `FinancialStatement` / `StatementType` を `models/financial.py` に追加する際の自然な拡張点になる

7. **`Sequence[RawFact]` を引数型にする理由**: `tuple | list` の Union よりも `collections.abc.Sequence` の方が Python ライブラリの慣用パターン。contexts.py の `structure_contexts()` と同じ方針

---

## 13. Day 14 への引き継ぎ

Day 13 完了後、Day 14 以降は以下を前提に着手する:

1. `build_line_items()` が全 RawFact を `LineItem` に変換できる
2. `LineItem` は `Decimal` / `str` / `None` の値、`LabelInfo` のラベル、`Period` / `DimensionMember` の文脈情報を保持する
3. Day 14 は Week 2 の振り返り日。実際のトヨタの有報 `.xbrl` に対して Day 9-13 のコードを手動実行し、ラベル付き数値データ一覧が出力されることを確認する
4. §10 Phase 4 の手動スモークコードを `tools/` 配下にスクリプトとして配置することを検討する（Day 14 の振り返りでも同じコードを実行するため再利用性がある。Day 13 ではスコープを広げず、Day 14 で整理する）
5. Day 14 で確認すべき事項:
   - `isinstance(item.value, Decimal)` による数値フィルタが正しく動作するか
   - 提出者拡張科目が `LabelSource.FILER` で解決されるか（`load_filer_labels()` の動線確認）
   - FALLBACK になる科目がどの程度あるか（`_ns_to_prefix` の網羅性確認）
6. Day 15 では `LineItem` を消費して `FinancialStatement` を構築する:
   - `models/financial.py` に `FinancialStatement`, `StatementType` を追加する
   - `xbrl/statements.py` に Fact 選択ルール（期間・連結フィルタ）を実装する
   - PL の concept 集合は JSON データファイルとして外出しする（PLAN.LIVING.md Day 15 指示）

---

## 14. 実行コマンド（Day 13）

```bash
# Phase 1-2: 実装
uv run ruff check src/edinet/models/financial.py
uv run ruff check src/edinet/xbrl/facts.py

# Phase 3: テスト
uv run pytest tests/test_xbrl/test_facts.py -v

# Phase 4: 検証
uv run pytest tests/test_xbrl/test_parser.py
uv run pytest tests/test_xbrl/test_contexts.py
uv run pytest tests/test_xbrl/test_taxonomy.py
uv run pytest
uv run ruff check src tests
uv run stubgen src/edinet --include-docstrings -o stubs
```

---

## 更新履歴

- 2026-02-25: 初版作成
- 2026-02-25: フィードバック反映（Issue 1-6）
  - §6.1 `value` docstring に `value_raw` vs `value_inner_xml` の区別を明記
  - §6.2 判断 10 に TextBlock の注意事項追記
  - PLAN.LIVING.md L1207 の `dimensions` 型を `tuple[DimensionMember, ...]` に更新
  - P0-15 の match パターンを固定値ベースに変更
  - P1-3 に `resolve_clark()` の FALLBACK 経路確認済みの旨を追記
  - §7.3 に `order` の 0-indexed 付番方式を明記
- 2026-02-25: 第 2 ラウンドフィードバック反映（Issue 1-5）
  - §1 に RawFact フィールド一覧を明記（value_inner_xml は L75 にデフォルト None 付きで存在）
  - [Critical] §8.2 の _NS_JPPFS / _NS_JPDEI を 2023-11-01 → 2025-11-01 に修正（taxonomy_mini との一致）
  - §1 に simple_pl.xbrl（2023-11-01）と taxonomy_mini（2025-11-01）の namespace 不一致を明記
  - §7.2 _convert_value にテキスト Fact の value_raw=None 防御チェックを追加（数値パスとの対称性）
  - §7.4 エラー処理表にテキスト Fact の防御チェック行を追加
  - P0-9 dimensions テストで FALLBACK ラベルに関する注意を追記
  - P1-7 統合テストで全ラベルが FALLBACK になる点を明記
  - P1-9 テキスト Fact の value_raw=None テストを追加（P1: 8 → 9 件）
- 2026-02-25: 第 3 ラウンドフィードバック反映（Issue 1-9）
  - §6.1 に Period が contexts.py __all__ に含まれている旨を確認・記録
  - §10 Phase 4 に _convert_value が .pyi に含まれないことの確認手順を追加
  - §8.2 _make_fact ヘルパーに value_inner_xml パラメータを追加
  - P0-12 の検証方法を具体化（`[item.order for item in items] == [0, 1, 2]`）
  - P1-7 に前提条件 `assert len(ctx_map) == 4` を追加
  - §7.4 にログ（日本語）と例外（英語）の言語方針を明記
  - §8.5 parametrize の判断を確定（nil → parametrize、period → 個別）
  - P0-13 と P1-7 の補完関係を明記
  - §13 に手動スモークのスクリプト化を Day 14 で検討する旨を追記
- 2026-02-25: 第 4 ラウンドフィードバック反映（Issue 1-6）
  - §7.2 _convert_value の数値 Fact パスに value_raw=None の明示チェック追加（except から TypeError を除去し InvalidOperation のみに）
  - §6.2 設計判断 6 に Period 型エイリアスの isinstance 制約メモを追記（Day 15 参照）
  - P0-11（label_info_type_and_fields）を P0-1 に統合し、P0: 15 → 14 件に削減
  - §10 Phase 3 の時間見積りを ~30 分 → ~40 分に調整（テスト 23 件）

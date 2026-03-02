# Day 10 — Context 構造化 + Fact 結合

## 0. 位置づけ

Day 10 は、Day 9 で抽出した `RawContext`（XML 断片）を構造化し、`RawFact.context_ref` を実体解決して **期間・Entity・Dimension を型付きオブジェクトで引けるようにする** 日。

Day 9 完了時点の状態:
- `parse_xbrl_facts()` が `ParsedXBRL` を返す（`RawFact` + `RawContext` + `RawUnit`）
- `RawContext` は `xml: str` に XML 断片を保持しているだけで、period / entity / scenario は未パース
- `RawFact.context_ref` は文字列で `"CurrentYearDuration"` 等を保持しているが、それが何の期間かは解決されていない

Day 10 完了時のマイルストーン:

```python
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts

parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)

# Context の構造化データにアクセス
ctx = ctx_map["CurrentYearDuration"]
print(ctx.period)       # DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
print(ctx.entity_id)    # "X99001-000"
print(ctx.dimensions)   # ()  ← dimension なし = 連結（デフォルト）

ctx2 = ctx_map["CurrentYearDuration_NonConsolidatedMember"]
print(ctx2.dimensions)  # (DimensionMember(axis="{...}ConsolidatedOrNonConsolidatedAxis", member="{...}NonConsolidatedMember"),)

# Fact から Context を引く
fact = parsed.facts[0]
fact_ctx = ctx_map[fact.context_ref]
print(f"{fact.local_name}: period={fact_ctx.period}")
```

CODESCOPE.md §2 で定義された責務（C-1〜C-4）を実装し、スコープ外（CN-1〜CN-7）は実装しない。

---

## 1. 現在実装の確認結果

| ファイル | 現状 | Day 10 で必要な変更 |
|---|---|---|
| `src/edinet/xbrl/parser.py` | `RawContext(context_id, source_line, xml)` を抽出済み。XML 断片を名前空間宣言込みで保持 | 変更なし |
| `src/edinet/xbrl/contexts.py` | 未作成 | 新規作成。`structure_contexts()` + データモデル |
| `src/edinet/xbrl/__init__.py` | `parse_xbrl_facts` のみエクスポート | `structure_contexts` を追加エクスポート |
| `src/edinet/models/financial.py` | 1 行 docstring のみ | Day 10 では未着手（Day 13 の `LineItem` 導入時に使う）|
| `tests/test_xbrl/test_contexts.py` | 未作成 | 新規作成 |
| `tests/fixtures/xbrl_fragments/simple_pl.xbrl` | Context 2 件（`CurrentYearDuration`, `CurrentYearInstant`）、Unit 1 件（`JPY`）| 必要に応じて Dimension 付き Context を追加 |
| `stubs/edinet/xbrl/contexts.pyi` | 未作成 | stubgen で生成 |

補足:
- Day 9 の `RawContext.xml` は `lxml.etree.tostring()` で名前空間宣言を保持しているため、Day 10 で再パース可能。再パース方式は Day 9 §11.7 で確定済み。**ただし、ルート要素に宣言された名前空間（`xmlns:jppfs_cor` 等）が Context 要素の `nsmap` に含まれるかどうかは Phase 0 で実機確認する（§8 Phase 0 参照）**
- `models/financial.py` への `Fact` / `Period` 導入は Day 9 §11.3 で Day 10 の責務とされているが、CODESCOPE.md の責務フローに従い、Day 10 は **contexts モジュールの構造化に専念** する。`Fact` / `Period` の Pydantic モデルは Day 13（Fact → LineItem）で導入する
- Day 9 §11.5 の「RawFact → models.financial.Fact 変換アダプタ」も Day 13 に先送り。Day 10 は `RawFact.context_ref` で `StructuredContext` を引く `dict[str, StructuredContext]` の提供のみ

---

## 2. Day 10 のゴール

1. `RawContext.xml` から period / entity / dimensions を構造化する関数 `structure_contexts()` を実装する
2. Period を `InstantPeriod` / `DurationPeriod` として型付きで保持する
3. Entity identifier の値を抽出する
4. Scenario 内の `xbrldi:explicitMember` を `DimensionMember` として保持する
5. `dict[str, StructuredContext]` を返し、`RawFact.context_ref` から引けるようにする
6. 全期間（当期・前期・前々期）の Context を漏れなく構造化する（フィルタしない）

---

## 3. スコープ / 非スコープ

### 3.1 Day 10 のスコープ

CODESCOPE.md §2 の処理する項目（C-1〜C-4）に対応:

| CODESCOPE | 内容 | Day 10 での実装 |
|---|---|---|
| C-1 | Period パース | `instant` → `InstantPeriod(date)`, `duration` → `DurationPeriod(start_date, end_date)` |
| C-2 | Entity パース | `entity/identifier` のテキスト値を `entity_id: str` として抽出 |
| C-3 | Dimension パース | `scenario` 内の `xbrldi:explicitMember` を `DimensionMember(axis, member)` として抽出。axis・member は Clark notation |
| C-4 | Fact 結合 | `dict[str, StructuredContext]` を返す関数 `structure_contexts()` |

### 3.2 Day 10 でやらないこと

CODESCOPE.md §2 のスコープ外（CN-1〜CN-7）:

| CODESCOPE | 内容 | やらない理由 |
|---|---|---|
| CN-1 | 日付論理整合性（start < end） | EDINET データは金融庁検証済み。`date.fromisoformat()` でフォーマット検証は自然に行われる |
| CN-2 | Entity identifier フォーマット検証 | 値の抽出で十分。命名規則検証は EDINET 固有 |
| CN-3 | Entity scheme 検証 | 1 種類しかない（A-2.2） |
| CN-4 | Context ID 命名規則パース | period/scenario の XML 構造から直接取得する方が確実（A-2 推論2） |
| CN-5 | Typed Dimension | EDINET では Explicit Dimension のみ使用（A-2.5） |
| CN-6 | Segment 要素 | EDINET では scenario を使用し segment は不使用（A-2.3） |
| CN-7 | Dimension の意味解釈（連結/個別判定） | dimensions/ モジュール（FEATURES.md）の責務 |

Day 10 でやらないその他:
- `models/financial.py` への Pydantic モデル導入（→ Day 13）
- `RawFact` → `Fact` 変換（→ Day 13）
- Unit の構造化（CODESCOPE.md §3: 必要に応じて実装。Day 15 では `unitRef` 文字列で十分）
- タクソノミ連携（→ Day 12）
- 財務諸表の組み立て（→ Day 15）

---

## 4. QA 反映方針（Day 10 に直結するもの）

| QA | Day 10 への反映 |
|---|---|
| A-2.1 | Context ID は命名規則に依存しない。period XML 要素から直接日付を取得する |
| A-2.2 | Entity identifier の値を抽出する。`scheme` は常に `http://disclosure.edinet-fsa.go.jp` なので検証不要 |
| A-2.3 | EDINET は `<xbrli:scenario>` を使用し `<xbrli:segment>` は不使用。scenario のみ探索する |
| A-2.5 | Explicit Dimension のみ対応。Typed Dimension (`xbrldi:typedMember`) は EDINET で不使用 |
| A-2.8 | Context 総数は 1 filing あたり約 278 件（トヨタ実データ）。`dict[str, StructuredContext]` で十分 |
| A-2.9 | 日付は常に `YYYY-MM-DD`（`xs:date`）。タイムゾーン情報なし。`datetime.date` を使用。`<xbrli:forever/>` は EDINET で不使用 |
| E-2 | 連結/個別は `ConsolidatedOrNonConsolidatedAxis` で区別。dimension なし = 連結（デフォルト）。Day 10 は axis/member を Clark notation で保持するのみで、連結判定ロジックは実装しない |
| E-3 | 全期間（当期 `CurrentYear*`, 前期 `Prior1Year*`, 前々期 `Prior2Year*`, 中間期 `Interim*`, 提出日 `FilingDate*` 等）の Context を漏れなく構造化する。当期だけにフィルタしない |

---

## 5. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/xbrl/contexts.py` | 新規 | `StructuredContext`, `InstantPeriod`, `DurationPeriod`, `DimensionMember` + `structure_contexts()` |
| `src/edinet/xbrl/__init__.py` | 追記 | `structure_contexts` を再エクスポート |
| `tests/test_xbrl/test_contexts.py` | 新規 | Small/Unit + Medium/Unit テスト |
| `tests/fixtures/xbrl_fragments/simple_pl.xbrl` | 追記（検討） | Dimension 付き Context を追加する場合（後述 §7.5） |
| `stubs/edinet/xbrl/contexts.pyi` | 新規 | stubgen で生成 |
| `stubs/edinet/xbrl/__init__.pyi` | 更新 | エクスポート追従 |

---

## 6. contexts モジュール設計詳細

### 6.1 公開 I/F

```python
from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from edinet.xbrl.parser import RawContext


@dataclass(frozen=True, slots=True)
class InstantPeriod:
    """時点（instant）期間。

    Attributes:
        instant: 時点の日付。
    """
    instant: datetime.date


@dataclass(frozen=True, slots=True)
class DurationPeriod:
    """期間（duration）。

    Attributes:
        start_date: 開始日。
        end_date: 終了日。
    """
    start_date: datetime.date
    end_date: datetime.date


Period = InstantPeriod | DurationPeriod
"""期間の型エイリアス。下流モジュール（Day 13 LineItem, Day 15 statements）で
Union を毎回書かずに済むよう、contexts.py で定義し re-export する。

Runtime isinstance 注記:
  Python 3.10+ の ``X | Y`` 構文は ``types.UnionType`` を生成し、
  ``isinstance(obj, Period)`` は **正常に動作する** （``typing.Union`` とは異なる）。
  本プロジェクトは Python 3.12 なので ``isinstance(ctx.period, Period)`` で
  InstantPeriod / DurationPeriod の両方にマッチする判定が可能。
  ただし個別の型で分岐する場合は ``isinstance(ctx.period, InstantPeriod)`` を推奨。
"""


@dataclass(frozen=True, slots=True)
class DimensionMember:
    """Explicit Dimension のメンバー。

    Attributes:
        axis: 軸の Clark notation（例: ``"{http://...}ConsolidatedOrNonConsolidatedAxis"``）。
        member: メンバーの Clark notation（例: ``"{http://...}NonConsolidatedMember"``）。
    """
    axis: str
    member: str


@dataclass(frozen=True, slots=True)
class StructuredContext:
    """構造化された Context。

    Attributes:
        context_id: Context の ``id`` 属性値。
        period: 期間（InstantPeriod または DurationPeriod）。
        entity_id: ``entity/identifier`` のテキスト値（例: ``"X99001-000"``）。
        dimensions: 明示 Dimension のタプル。空 = 全て Dimension がデフォルト。
        source_line: 元 XML 文書の行番号（1-based）。取得不可時は ``None``。
    """
    context_id: str
    period: Period
    entity_id: str
    dimensions: tuple[DimensionMember, ...]
    source_line: int | None


def structure_contexts(
    raw_contexts: Sequence[RawContext],
) -> dict[str, StructuredContext]:
    """RawContext 群を構造化して辞書で返す。

    Args:
        raw_contexts: parser が返した RawContext のシーケンス。
            ``tuple`` / ``list`` いずれも受け付ける。

    Returns:
        Context ID をキーとする StructuredContext の辞書。

    Raises:
        EdinetParseError: Context の XML 断片が不正な場合
            （period 要素欠落、日付フォーマット不正等）。
    """
    ...
```

### 6.2 設計判断

1. **dataclass を使う理由**: CODESCOPE.md §2 の出力イメージに合わせる。Pydantic モデルは Day 13 で `LineItem` 導入時に必要になるが、contexts モジュールは parser.py と同レイヤーの「構造化」担当であり、バリデーション付きモデルは不要
2. **`dimensions` を `tuple[DimensionMember, ...]` にする理由**: CODESCOPE.md §2 の設計判断記録に明記。`dict[str, str]` だと Typed Dimension 拡張時に型変更が必要。`DimensionMember` dataclass なら `TypedDimensionMember` サブクラス追加で対応可能。加えて、`tuple` は hashable なので `StructuredContext` 自体が hashable になる利点もある（`frozen=True` + 全フィールド hashable）
3. **`InstantPeriod` / `DurationPeriod` を分ける理由**: BS は instant、PL/CF は duration。Union 型にすることで `isinstance` で分岐でき、型安全に期間を扱える。1 つの `Period` クラスに `start_date: date | None` を持たせるとフィールドの有無で分岐する羽目になる。Day 15 の Fact 選択で BS(instant) vs PL(duration) の分岐に直結する
4. **バリデーションを最小限にする理由**: CODESCOPE.md §2 の設計判断記録に明記。`date.fromisoformat()` がフォーマット検証を兼ねる。period 要素欠落や不正 XML は `EdinetParseError` に変換する（自然なエラーを正規化するだけ）
5. **引数型を `Sequence[RawContext]` にする理由**: `tuple | list` の Union よりも `collections.abc.Sequence` の方が Python ライブラリの慣用パターン。tuple / list のいずれも受け付ける意図がより明確になる
6. **名前空間定数を contexts.py 内に定義する理由**: parser.py の `_NS_XBRLI` は `_` prefix で private。Day 10 時点で `_namespaces.py` を切り出すと parser.py のリファクタリングが含まれスコープが膨らむ。Day 12（TaxonomyResolver）で namespace を多用する時点で切り出すのが自然
7. **`__repr__` はデフォルトのまま**: dataclass のデフォルト `__repr__` は全フィールドを出力するため、Clark notation の長い文字列が混ざると REPL での視認性が落ちる可能性がある。v0.1.0 ではデフォルトで十分だが、Day 15 で `FinancialStatement` と組み合わせた時に気になれば、カスタム `__repr__` を後付けする（additive change）
8. **Period 共通 `end_date` プロパティは YAGNI**: Day 15 で「この Context の期間終了日」を取りたい場面が確実に来る（`InstantPeriod.instant` / `DurationPeriod.end_date` を毎回 `isinstance` で分岐）。共通プロパティや Protocol を導入する選択肢はあるが、Day 10 では現状維持。Day 15 で `end_date` 取得が頻出したら、`@property end_date` を持つ基底クラスを追加する（additive change、既存コードは壊れない）
9. **`dimensions` の順序**: XML 出現順を保持する（`findall()` の返却順そのまま）。XBRL 仕様上 `explicitMember` の出現順に意味はないが、テストの安定性と再現性のため保持する。テストでは順序依存しないアサーション（`set()` 比較 or `sorted`）を推奨
10. **Entity `scheme` を保持しない理由**: EDINET では `scheme` は常に `http://disclosure.edinet-fsa.go.jp` の 1 種類のみ（A-2.2, CN-3）。v0.1.0 では `entity_id` のみ保持する。将来の IFRS 対応（v1.0.0）で scheme が変わる可能性はゼロではないが、EDINET が scheme を変える可能性は極めて低い（全企業共通の固定値）。必要になった時点で `entity_scheme: str` フィールドを追加する（additive change）
11. **名前空間定数の一時的重複**: parser.py の `_NS_XBRLI` と contexts.py の `NS_XBRLI` は同じ値の別定数になる。Day 12 の TaxonomyResolver 実装時に `_namespaces.py` に集約するリファクタリングで解消する。それまでの一時的重複であることをコード内コメントで明記する

### 6.3 内部実装方針

```python
def structure_contexts(raw_contexts, ...):
    result = {}
    for raw in raw_contexts:
        if raw.context_id is None:
            logger.debug("Skipping RawContext with context_id=None (line=%s)", raw.source_line)
            continue
        if raw.context_id in result:
            # parser.py strict=False 時に同一 context_id の RawContext が
            # 複数含まれうる。last-wins（後勝ち）で上書きし、デバッグログを出す。
            logger.debug(
                "Duplicate context_id=%r (line=%s), overwriting previous entry",
                raw.context_id, raw.source_line,
            )
        ctx = _parse_single_context(raw)
        result[ctx.context_id] = ctx
    return result


def _parse_single_context(raw: RawContext) -> StructuredContext:
    """1 つの RawContext を構造化する。

    エラーハンドリング方針: Fail-fast。
    1 つの Context のパース失敗で EdinetParseError を raise し、
    残りの Context も含め全体を失敗させる。
    parser.py が既にバリデーション済みの RawContext を受け取る立場のため、
    ここでのエラーは「想定外の XML 構造」を意味し、best-effort で
    一部だけ返すと下流が壊れるリスクがある。
    """
    # 1. raw.xml を再パース
    #    raw.xml は str 型（parser.py が encoding="unicode" で tostring()）。
    #    lxml.etree.fromstring() は bytes を要求するため、
    #    明示的に raw.xml.encode("utf-8") で変換する。
    #    XML 宣言なしの UTF-8 bytes となり、lxml は問題なく受け付ける。
    elem = etree.fromstring(raw.xml.encode("utf-8"))
    #
    # 2. period パース（2 段階チェック）:
    #    a. <xbrli:period> 要素自体の存在を確認:
    #       period_elem = elem.find(f"{{{NS_XBRLI}}}period")
    #       if period_elem is None:
    #           raise EdinetParseError(f"Context '{cid}': missing <xbrli:period> element")
    #
    #    b. period の子要素を判定:
    #       - xbrli:instant → InstantPeriod(date.fromisoformat(text.strip()))
    #       - xbrli:startDate + xbrli:endDate → DurationPeriod(...)
    #       - どちらもなければ EdinetParseError:
    #           raise EdinetParseError(
    #               f"Context '{cid}': <xbrli:period> must contain "
    #               f"<instant> or <startDate>+<endDate>"
    #           )
    #         これにより <xbrli:forever/> が存在する場合も
    #         「instant も startDate+endDate もない」と正確に伝わる。
    #         EDINET では forever は不使用（A-2.9）なのでエラーにするのは正しい。
    #
    #    注意: 日付テキストの前後空白を .strip() する。XML のインデントに
    #    より空白が混入するケースがあり、date.fromisoformat() は空白を
    #    受け付けないため。
    #
    # 3. entity/identifier のテキスト値を抽出
    #    - 欠落時は EdinetParseError
    #    - 要素は存在するがテキストが空 or 空白のみの場合も EdinetParseError:
    #      text = id_elem.text.strip() if id_elem.text else ""
    #      if not text:
    #          raise EdinetParseError(f"Context '{cid}': empty entity/identifier")
    #
    # 4. scenario 内の xbrldi:explicitMember を全て抽出:
    #    - dimension 属性（QName → Clark notation に解決）
    #    - テキスト値（QName → Clark notation に解決）
    #    - scenario がなければ dimensions = ()
    #    - findall() の返却順（= XML 出現順）を保持する
    #    - _resolve_qname に nsmap を渡す際、lxml の nsmap には
    #      デフォルト名前空間として {None: "http://..."} が含まれうるが、
    #      _resolve_qname は prefix 必須なので None キーは参照されない
    #
    # 5. source_line は raw.source_line をそのまま転写する
    #
    # 6. StructuredContext を返す
    ...
```

ロガー規約:
- contexts.py では `logger = logging.getLogger(__name__)` でモジュールロガーを定義し、`logger.debug()` で内部イベント（`context_id=None` スキップ、重複 `context_id` 上書き）を出力する
- **注意: parser.py は `logging` を使用しておらず、`warnings.warn(..., EdinetWarning)` で問題を通知している。** contexts.py で `logging.debug()` を導入するのは新しいパターンである。選択理由: `context_id=None` スキップや重複上書きはユーザー向け「警告」ではなく、デバッグ時にのみ必要な内部情報であり、`warnings.warn()` よりも `logging.debug()` の方が意味的に適切。ユーザー向けの問題通知（仕様違反等）が必要になった場合は parser.py と同様に `warnings.warn()` を使う

### 6.4 名前空間定数

```python
NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"
```

### 6.5 QName → Clark notation 解決

`xbrldi:explicitMember` の `dimension` 属性と要素テキストは `prefix:localName` 形式の QName で記述されている。Clark notation（`{namespace}localName`）に変換するには、要素のスコープ内の名前空間マッピングが必要。

```python
def _resolve_qname(qname_str: str, nsmap: dict[str | None, str]) -> str:
    """'prefix:localName' を '{namespace}localName' に変換する。

    XBRL Dimensions 仕様により、explicitMember の dimension 属性と
    テキスト値は常に prefixed QName（prefix:localName）である。
    prefix なしの QName は仕様違反として EdinetParseError にする。
    """
    qname_str = qname_str.strip()
    if ":" not in qname_str:
        # XBRL Dimensions 仕様上、explicitMember の QName は常に
        # prefixed であるべき。prefix なしは仕様違反。
        raise EdinetParseError(
            f"Dimension QName must be prefixed (prefix:localName), "
            f"got: {qname_str!r}"
        )
    prefix, local = qname_str.split(":", 1)
    ns = nsmap.get(prefix)
    if ns is None:
        raise EdinetParseError(
            f"Undefined namespace prefix: {prefix!r} "
            f"in QName {qname_str!r}"
        )
    return f"{{{ns}}}{local}"
```

重要:
- `RawContext.xml` は `lxml.etree.tostring()` で名前空間宣言を保持しているため、`fromstring()` で再パースすれば `element.nsmap` から prefix → namespace の解決が可能。ただし、提出者別タクソノミの namespace prefix（例: `jpcrp030000-asr_X99001-000`）がスコープ内にあるかは Phase 0 で実機確認する（§8 Phase 0 参照）。
- **lxml の `nsmap` の `None` キー**: `element.nsmap` にはデフォルト名前空間として `{None: "http://..."}` が含まれることがある。`_resolve_qname` に `nsmap` をそのまま渡しても、prefix 必須の設計（`":" not in qname_str` → error）により `None` キーが参照されることはない。ただし、実装時に `nsmap.get(prefix)` が意図せず `None` キーにヒットしないことを意識すること（`prefix` は `str` 型なので `None` キーとは衝突しない）。

### 6.6 エラー処理方針

**Fail-fast 方針**: 1 つの Context のパース失敗で `EdinetParseError` を raise し、残りの Context も含め全体を失敗させる。parser.py が既にバリデーション済みの `RawContext` を受け取る立場のため、ここでのエラーは「想定外の XML 構造」を意味し、best-effort で一部だけ返すと下流（Day 15 の Fact 選択等）が壊れるリスクがある。`context_id=None` のスキップのみが唯一の例外（parser.py の strict=False で既に警告済み）。

エラーメッセージは **英語** で統一する。PyPI 公開ライブラリとして国際的なディファクトスタンダードに合わせる（parser.py と同方針）。日本語はドキュメントと docstring にとどめる。

| 状況 | 処理 |
|---|---|
| `RawContext.context_id` が `None` | parser.py の S-3 で既にエラー/警告済み。Day 10 ではスキップし、`logging.debug()` でログ出力（黙って無視するとデバッグ時に困るため） |
| 同一 `context_id` の `RawContext` が複数存在 | parser.py strict=False 時に発生しうる（strict=False は warn するが RawContext リストには追加される）。last-wins で上書きし、`logging.debug()` でログ出力する。Fail-fast の例外ケース（エラーではなく許容される重複）|
| `<xbrli:period>` 要素自体が欠落 | `EdinetParseError`（`"Context '{id}': missing <xbrli:period> element"`） |
| `<xbrli:period>` はあるが `instant` も `startDate`+`endDate` もない（`<xbrli:forever/>` 含む） | `EdinetParseError`（`"Context '{id}': <xbrli:period> must contain <instant> or <startDate>+<endDate>"`） |
| instant / startDate / endDate の日付フォーマット不正 | `date.fromisoformat()` の `ValueError` → `EdinetParseError` に変換 |
| entity/identifier 欠落 | `EdinetParseError`（`"Context '{id}': missing entity/identifier element"`） |
| entity/identifier のテキストが空 or 空白のみ | `EdinetParseError`（`"Context '{id}': empty entity/identifier"`）。要素は存在するがテキストが空のケース。`.strip()` 後に空文字なら即エラー |
| dimension の QName 解決失敗（未定義 prefix） | `EdinetParseError`（§6.5 参照） |
| dimension の QName に prefix がない | `EdinetParseError`（§6.5 参照。XBRL Dimensions 仕様上、prefix 必須） |
| XML パースエラー（`RawContext.xml` が壊れている） | `EdinetParseError` に変換。通常は発生しない（parser.py が生成した XML 断片のため） |

### 6.7 公開エクスポート方針

- `edinet.xbrl`（`src/edinet/xbrl/__init__.py`）に `structure_contexts` を追加
- `StructuredContext`, `InstantPeriod`, `DurationPeriod`, `DimensionMember`, `Period` は `edinet.xbrl.contexts` からの明示 import でのみ利用可能とし、トップレベル再エクスポートしない
- Day 15 の statements モジュールが `structure_contexts()` を内部で呼ぶ想定
- `contexts.py` に `__all__` を定義する:
  ```python
  __all__ = [
      "InstantPeriod",
      "DurationPeriod",
      "Period",
      "DimensionMember",
      "StructuredContext",
      "structure_contexts",
  ]
  ```
  注: parser.py は `__all__` を定義していない（既存の不整合）。parser.py への `__all__` 追加は Day 10 のスコープ外（リファクタリングになるため）。contexts.py は新規モジュールなので最初から定義する

---

## 7. テスト計画（size/scope）

### 7.1 追加テストケース（P0: Day 10 必須）

1. `test_structure_contexts_parses_duration_period` — `startDate/endDate` → `DurationPeriod` の正常系
2. `test_structure_contexts_parses_instant_period` — `instant` → `InstantPeriod` の正常系
3. `test_structure_contexts_extracts_entity_id` — `entity/identifier` テキスト値の抽出
4. `test_structure_contexts_extracts_dimensions` — `scenario` 内 `explicitMember` → `DimensionMember` の抽出。axis/member が Clark notation であること
5. `test_structure_contexts_returns_empty_dimensions_when_no_scenario` — scenario なし → `dimensions=()`
6. `test_structure_contexts_returns_dict_keyed_by_context_id` — 返り値が `dict[str, StructuredContext]` であること
7. `test_structure_contexts_handles_multiple_contexts` — 複数 Context（instant + duration + dimension 付き）を一括処理
8. `test_structure_contexts_raises_on_missing_period` — period 要素欠落で `EdinetParseError`
9. `test_structure_contexts_raises_on_invalid_date` — 不正日付（例: `"2025-13-01"`）で `EdinetParseError`
10. `test_structure_contexts_raises_on_missing_entity` — entity/identifier 欠落で `EdinetParseError`
11. `test_structure_contexts_strips_whitespace_in_date` — `<xbrli:instant> 2025-03-31 </xbrli:instant>` のように日付テキストに前後空白が含まれるケースで正しくパースされること。`date.fromisoformat()` は空白を受け付けないため、`.strip()` が必要。XML のインデントにより実データで起こりうる
12. `test_structure_contexts_strips_whitespace_in_dimension_qname` — `<xbrldi:explicitMember dimension="..."> jppfs_cor:NonConsolidatedMember </xbrldi:explicitMember>` のように QName テキストに前後空白が含まれるケースで正しく Clark notation に解決されること
13. `test_structure_contexts_empty_input` — 空リスト `[]` を渡したときに空 dict `{}` が返ること（正常系の境界値）
14. `test_structure_contexts_last_wins_on_duplicate_context_id` — 同一 `context_id` を持つ 2 つの `RawContext`（例: period の日付が異なる）を渡し、後勝ちの `StructuredContext` が返ること。§6.3 の last-wins ロジックの検証。`structure_contexts()` 独自の処理（parser.py にはない）なので P0 で必須

### 7.2 追加テストケース（P1: Day 10 推奨）

1. `test_structure_contexts_resolves_qname_to_clark_notation` — `jppfs_cor:NonConsolidatedMember` → `{http://...}NonConsolidatedMember` の名前空間解決
2. `test_structure_contexts_handles_multiple_dimensions` — 連結軸 + セグメント軸の同時抽出。A-2.a.md の実例ベースで `ConsolidatedOrNonConsolidatedAxis` + `OperatingSegmentsAxis` の 2 dimension を持つ Context を検証（EDINET では実用上 1〜2 個が主流）
3. `test_structure_contexts_skips_context_without_id` — `context_id=None` の RawContext をスキップし、`logging.debug()` が出力されること
4. `test_structure_contexts_preserves_all_periods` — 当期・前期・前々期・提出日の全 Context が構造化されること（フィルタなし）
5. `test_structure_contexts_with_simple_pl_fixture` — `simple_pl.xbrl` から `parse_xbrl_facts()` → `structure_contexts()` の結合テスト
6. `test_structure_contexts_raises_on_undefined_prefix` — dimension の QName に未定義 prefix がある場合にエラー
7. `test_structure_contexts_resolves_submitter_namespace_qname` — 提出者別タクソノミの namespace prefix（`jpcrp030000-asr_X99001-000:CommunicationsEquipmentReportableSegmentMember` のようなパターン）が Clark notation に正しく解決されること。A-2.a.md の実例に基づく
8. `test_structure_contexts_raises_on_unprefixed_qname` — prefix なしの QName（XBRL Dimensions 仕様違反）で `EdinetParseError` になること

### 7.3 テスト用 fixture の方針

**インラインの RawContext 生成ヘルパー** を使い、ほとんどのテストを Small/Unit で書く。

```python
from edinet.xbrl.parser import RawContext

def _make_raw_context(
    context_id: str,
    xml: str,
    source_line: int | None = None,
) -> RawContext:
    return RawContext(context_id=context_id, source_line=source_line, xml=xml)

# 注意: インラインテスト用 XML の entity_id は "X99001-000" だが、
# simple_pl.xbrl fixture の entity_id は "E00001"。
# P1-5 の結合テスト（fixture 経由）では "E00001" でアサートすること。

# Duration Context のサンプル XML
DURATION_XML = """\
<xbrli:context id="CurrentYearDuration"
    xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:startDate>2024-04-01</xbrli:startDate>
    <xbrli:endDate>2025-03-31</xbrli:endDate>
  </xbrli:period>
</xbrli:context>"""

# Instant Context のサンプル XML
INSTANT_XML = """\
<xbrli:context id="CurrentYearInstant"
    xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:instant>2025-03-31</xbrli:instant>
  </xbrli:period>
</xbrli:context>"""

# Dimension 付き Context のサンプル XML
DIMENSION_XML = """\
<xbrli:context id="CurrentYearDuration_NonConsolidatedMember"
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:startDate>2024-04-01</xbrli:startDate>
    <xbrli:endDate>2025-03-31</xbrli:endDate>
  </xbrli:period>
  <xbrli:scenario>
    <xbrldi:explicitMember
      dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">jppfs_cor:NonConsolidatedMember</xbrldi:explicitMember>
  </xbrli:scenario>
</xbrli:context>"""
```

追加: 提出者別 namespace を含むテスト用 XML（P1-7 用）:

```python
# 提出者別タクソノミの namespace prefix を含む Context（A-2.a.md 実例ベース）
SUBMITTER_DIMENSION_XML = """\
<xbrli:context id="CurrentYearDuration_ReportableSegmentMember"
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    xmlns:jpcrp_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2023-11-01/jpcrp_cor"
    xmlns:jpcrp030000-asr_X99001-000="http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp030000-asr/X99001-000/2023-11-01/01/jpcrp030000-asr_X99001-000">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:startDate>2024-04-01</xbrli:startDate>
    <xbrli:endDate>2025-03-31</xbrli:endDate>
  </xbrli:period>
  <xbrli:scenario>
    <xbrldi:explicitMember
      dimension="jpcrp_cor:OperatingSegmentsAxis">jpcrp030000-asr_X99001-000:CommunicationsEquipmentReportableSegmentMember</xbrldi:explicitMember>
  </xbrli:scenario>
</xbrli:context>"""

# 複数 Dimension（連結軸 + セグメント軸）を持つ Context
MULTI_DIMENSION_XML = """\
<xbrli:context id="CurrentYearDuration_NonConsolidatedMember_ReportableSegment"
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor"
    xmlns:jpcrp_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2023-11-01/jpcrp_cor"
    xmlns:jpcrp030000-asr_X99001-000="http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp030000-asr/X99001-000/2023-11-01/01/jpcrp030000-asr_X99001-000">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:startDate>2024-04-01</xbrli:startDate>
    <xbrli:endDate>2025-03-31</xbrli:endDate>
  </xbrli:period>
  <xbrli:scenario>
    <xbrldi:explicitMember
      dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">jppfs_cor:NonConsolidatedMember</xbrldi:explicitMember>
    <xbrldi:explicitMember
      dimension="jpcrp_cor:OperatingSegmentsAxis">jpcrp030000-asr_X99001-000:CommunicationsEquipmentReportableSegmentMember</xbrldi:explicitMember>
  </xbrli:scenario>
</xbrli:context>"""
```

### 7.4 `pytest.mark.parametrize` の活用

以下のテストは `@pytest.mark.parametrize` で統合することを推奨する（テスト関数の増殖を防ぐ）:
- P0-8 + P0-9 → `test_structure_contexts_raises_on_bad_period` にまとめ、`pytest.param` で "missing period" と "invalid date" の 2 パターン化
- P0-11 + P0-12 → `test_structure_contexts_strips_whitespace` にまとめ、日付空白と QName 空白を parametrize
- P1-6 + P1-8 → `test_structure_contexts_raises_on_bad_qname` にまとめ、"undefined prefix" と "unprefixed QName" の 2 パターン化

ただし parametrize は可読性とのトレードオフ。個別テスト名で意図を明示する方が好ましい場合はそのまま残してよい。

### 7.5 marker 方針

- `small` + `unit`: インライン XML 文字列から `RawContext` を直接生成するテスト
- `medium` + `unit`: `simple_pl.xbrl` fixture を使うが単一モジュール内のテスト
- `medium` + `integration`: `simple_pl.xbrl` から `parse_xbrl_facts()` → `structure_contexts()` の 2 モジュールをまたぐ結合テスト（§7.2-5）
- P0 テストは全て `small` + `unit` で書ける（fixture ファイル不要）

### 7.6 既存 fixture への追記の検討

`simple_pl.xbrl` に Dimension 付き Context を追加するか？

**結論: 追加する。**

理由:
- §7.2-5 の結合テスト（`parse_xbrl_facts` → `structure_contexts`）で Dimension 付き Context が必要
- 既存テスト（`test_parser.py`）は Fact 数でアサートしているため、新しい Context を追加するだけなら影響しない（Context は Fact ではない）
- ただし、新しい Context を参照する Fact を追加する場合は既存テストの `fact_count` アサーションを更新する必要がある

追加内容:
```xml
<!-- 個別用 Context（NonConsolidatedMember） -->
<xbrli:context id="CurrentYearDuration_NonConsolidatedMember">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:startDate>2024-04-01</xbrli:startDate>
    <xbrli:endDate>2025-03-31</xbrli:endDate>
  </xbrli:period>
  <xbrli:scenario>
    <xbrldi:explicitMember
      dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">jppfs_cor:NonConsolidatedMember</xbrldi:explicitMember>
  </xbrli:scenario>
</xbrli:context>

<!-- 前期 Context -->
<xbrli:context id="Prior1YearDuration">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:startDate>2023-04-01</xbrli:startDate>
    <xbrli:endDate>2024-03-31</xbrli:endDate>
  </xbrli:period>
</xbrli:context>
```

変更箇所の明示:
1. **ルート要素** `<xbrli:xbrl ...>` に以下の名前空間宣言を追加:
   - `xmlns:xbrldi="http://xbrl.org/2006/xbrldi"`
   （`xmlns:jppfs_cor` はルート要素に既に宣言済みのはず。なければ追加）
2. 上記 2 つの Context 要素を、既存 Context の後に追加
3. **Fact は追加しない**（既存テスト非破壊）

---

## 8. 当日の作業手順（チェックリスト）

### Phase 0: 名前空間伝播の実機確認（〜5 分）

parser.py の `_serialize_outer_xml` が保持する名前空間宣言が、Context 要素の再パース時に Dimension の QName 解決に十分かどうかを確認する。**この確認が不合格なら、§6.5 の `_resolve_qname` の実装方針を修正する必要がある。**

Phase 0 は 2 段階に分ける:

**Phase 0a: 基本 nsmap 確認（Phase 1 の fixture 追加前に実行可能）**

```python
from lxml import etree

# simple_pl.xbrl を直接パースして確認
tree = etree.parse("tests/fixtures/xbrl_fragments/simple_pl.xbrl")
ctx = tree.find(".//{http://www.xbrl.org/2003/instance}context")
print("Context element nsmap:", ctx.nsmap)
# → jppfs_cor が含まれるか確認

# parser.py 経由で確認（RawContext.xml を再パース）
from edinet.xbrl.parser import parse_xbrl_facts
xbrl_bytes = open("tests/fixtures/xbrl_fragments/simple_pl.xbrl", "rb").read()
parsed = parse_xbrl_facts(xbrl_bytes)
raw_ctx = parsed.contexts[0]
elem = etree.fromstring(raw_ctx.xml.encode())
print("Re-parsed nsmap:", elem.nsmap)
# → ルート要素の名前空間宣言が伝播しているか確認
```

**Phase 0b: Dimension 付き Context の nsmap 確認（Phase 1 の fixture 追加後に実行）**

Phase 0a の時点では Dimension 付き Context が fixture にないため、`xbrldi` の nsmap 伝播は確認できない。Phase 1 で `simple_pl.xbrl` に Dimension 付き Context + `xmlns:xbrldi` を追加した後、以下を実行する:

```python
# Phase 1 の fixture 追加後に実行
xbrl_bytes = open("tests/fixtures/xbrl_fragments/simple_pl.xbrl", "rb").read()
parsed = parse_xbrl_facts(xbrl_bytes)
# Dimension 付き Context を取得（追加した 3 番目の Context）
for rc in parsed.contexts:
    elem = etree.fromstring(rc.xml.encode())
    print(f"context_id={rc.context_id}, nsmap keys={list(elem.nsmap.keys())}")
    # → xbrldi, jppfs_cor が含まれるか確認
```

確認ポイント:
1. ルート要素に宣言された `xmlns:jppfs_cor` が Context 要素の `nsmap` に含まれるか（Phase 0a）
2. `xmlns:xbrldi` が Dimension 付き Context の `nsmap` に含まれるか（Phase 0b）
3. 提出者別 namespace（`jpcrp030000-asr_X99001-000` 等）がスコープ内にあるか（実データで要確認）
4. `_serialize_outer_xml` が `element.nsmap` をコピーして `tostring()` に渡しているため、おそらく含まれるが、実機で確認する

万が一不合格だった場合のフォールバック:
- コード変更: `_serialize_outer_xml` の `nsmap` 引数を調整するか、ルート要素の `nsmap` を別途保存して `structure_contexts()` に渡す（parser.py の API 変更を伴う可能性）
- 確率: 非常に低い。parser.py は `element.nsmap`（lxml の全スコープ内 NS を含む辞書）をコピーしており、実装確認済み。ただし Phase 0 で必ず確認する

### Phase 1: テスト土台（〜20 分）

1. `tests/test_xbrl/test_contexts.py` を作成
2. テスト用の XML 文字列定数（§7.3）とヘルパーを定義
3. P0 テスト（§7.1）を先に書く（全て FAIL する状態）
4. `simple_pl.xbrl` に Dimension 付き Context + 前期 Context を追加（§7.5）
5. **fixture 変更後すぐに `uv run pytest tests/test_xbrl/test_parser.py` を実行し、既存テストが壊れないことを確認する**（`xmlns:xbrldi` 追加 + Context 追加は Fact 数に影響しないはずだが、Phase 1 の時点で早期に確認する）

### Phase 2: contexts モジュール実装（〜40 分）

1. `src/edinet/xbrl/contexts.py` を作成
2. データモデル（`InstantPeriod`, `DurationPeriod`, `DimensionMember`, `StructuredContext`）を定義
3. `_parse_single_context()` を実装:
   - a. `lxml.etree.fromstring()` で XML 断片を再パース
   - b. `xbrli:period` の子要素（`instant` / `startDate` + `endDate`）を探索し、`date.fromisoformat()` で変換
   - c. `xbrli:entity/xbrli:identifier` のテキスト値を取得
   - d. `xbrli:scenario/xbrldi:explicitMember` を全て取得し、`dimension` 属性と要素テキストを Clark notation に変換
4. `structure_contexts()` を実装（ループ + dict 構築）
5. エラーハンドリング（`ValueError` → `EdinetParseError` 変換）
6. 名前空間定数を parser.py から共有するか contexts.py に独立定義するか決定（推奨: `xbrl/_namespaces.py` を切り出すか、contexts.py 内に定義。Day 10 は後者で十分）

### Phase 3: 公開導線・型（〜10 分）

1. `xbrl/__init__.py` に `structure_contexts` を追加
2. `uv run stubgen src/edinet --include-docstrings -o stubs` で `.pyi` 生成
3. `.pyi` の diff を確認

### Phase 4: 検証（〜20 分）

1. `uv run pytest tests/test_xbrl/test_contexts.py` — P0 テスト全 pass
2. `uv run pytest tests/test_xbrl/test_parser.py` — 既存テスト回帰なし（fixture 変更の影響確認）
3. `uv run pytest` — 全テスト回帰なし
4. `uv run ruff check src tests` — 警告なし
5. P1 テスト（§7.2）を追加して pass 確認
6. 手動スモーク: 実 filing 1 件で `structure_contexts()` を実行し、Context 数と代表的な期間値を確認
7. REPL で `DimensionMember` / `StructuredContext` の `repr()` を確認し、Clark notation の長い文字列が混ざった時の視認性を目視チェックする。§6.2 設計判断 7 に従い v0.1.0 ではデフォルトで問題ないかの確認のみ（カスタム `__repr__` は必要になった時に追加）

```python
# 手動スモークのイメージ
# 注意: 日付は EDINET API で取得可能な過去の日付を使うこと
from edinet import documents
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.contexts import structure_contexts

filing = documents("2025-06-25", doc_type="120")[0]
path, xbrl_bytes = filing.fetch()
parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
ctx_map = structure_contexts(parsed.contexts)

print(f"Context 数: {len(ctx_map)}")
for cid, ctx in list(ctx_map.items())[:5]:
    print(f"  {cid}: period={ctx.period}, entity={ctx.entity_id}, dims={len(ctx.dimensions)}")
```

---

## 9. 受け入れ基準（Done の定義）

- `structure_contexts()` が `RawContext` 群を受け取り `dict[str, StructuredContext]` を返す
- `InstantPeriod` / `DurationPeriod` が正しく `datetime.date` を保持する
- `entity_id` が identifier テキスト値を保持する
- `DimensionMember` が axis / member を Clark notation で保持する
- scenario なし Context は `dimensions=()` になる
- 全期間の Context を漏れなく構造化する（当期だけにフィルタしない）
- period 欠落・日付フォーマット不正・entity 欠落で `EdinetParseError` を返す
- Dimension QName の prefix なしは `EdinetParseError` になる（XBRL Dimensions 仕様準拠）
- Phase 0 の名前空間伝播確認が完了し、結果が §8 Phase 0 の確認ポイントを満たす
- P0 テスト（§7.1）が全て pass
- P1 テスト（§7.2）は同日完了が望ましい（特に P1-7 提出者別 namespace テストは堅牢性に重要）。未完の場合は Day 11 冒頭で完了させる
- 既存テストスイートが回帰なし（特に `test_parser.py` の fixture 変更影響）
- ruff で警告なし
- `.pyi` が生成され contexts モジュールの型情報が反映されている

---

## 10. 実行コマンド（Day 10）

```bash
uv run pytest tests/test_xbrl/test_contexts.py
uv run pytest tests/test_xbrl/test_parser.py
uv run pytest
uv run ruff check src tests
uv run stubgen src/edinet --include-docstrings -o stubs
```

---

## 11. Day 11 への引き継ぎ

Day 10 完了後、Day 11 以降は以下を前提に着手する:

1. `structure_contexts()` が `dict[str, StructuredContext]` を安定供給できる
2. `RawFact.context_ref` で `StructuredContext` を引けるため、期間・連結/個別の情報にアクセス可能
3. Day 11 はタクソノミ構造の理解（コード書かない読解日）
4. Day 12 で TaxonomyResolver を実装し、concept → ラベル辞書を構築
5. Day 13 で `RawFact` + `StructuredContext` + `TaxonomyResolver` → `LineItem` 変換を実装
6. Day 15 で `LineItem` 群 → `FinancialStatement` 組み立てを実装。`structure_contexts()` が返す `StructuredContext` の `period` / `dimensions` が Fact 選択フィルタに直接使われる
7. Day 15 で Period の `end_date` 取得が頻出した場合（`isinstance` 分岐の繰り返し）、`InstantPeriod` / `DurationPeriod` に共通 `@property end_date` を持つ基底クラスを追加することを検討する（§6.2 設計判断 8 参照）

---

## 12. フィードバック反映記録

### Round 1

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| A-1 | 設計 | `_serialize_outer_xml` の名前空間伝播を実機確認すべき | Phase 0 を追加（§8）。提出者別 namespace の確認ポイントも明記 |
| A-2 | 設計 | `_resolve_qname` の prefix なしケースを `EdinetParseError` に | §6.5 を修正。XBRL Dimensions 仕様上 prefix 必須をコメントで明記 |
| A-3 | 設計 | 引数型を `Sequence[RawContext]` に | §6.1 を修正。設計判断 5 に理由を追記 |
| B-1 | テスト | 提出者別 namespace の QName 解決テスト追加 | P1-7 を追加（§7.2）。テスト用 XML を §7.3 に追記 |
| B-2 | テスト | 複数 Dimension テストを A-2.a.md 実例ベースに | P1-2 の説明を修正。`MULTI_DIMENSION_XML` を §7.3 に追記 |
| B-3 | テスト | simple_pl.xbrl のルート要素変更を明示 | §7.5 に変更箇所の明示リストを追加 |
| C-1 | 賛同 | InstantPeriod / DurationPeriod の分離 | 設計判断 3 に Day 15 との接続を補強 |
| C-2 | 賛同 | tuple[DimensionMember, ...] の hashable 利点 | 設計判断 2 に hashable の利点を追記 |
| C-3 | 賛同 | 名前空間定数を contexts.py 内に定義 | 設計判断 6 に Day 12 切り出しの方針を追記 |
| D-1 | 軽微 | エラーメッセージの日英方針 | §6.6 冒頭に英語統一方針を追記。メッセージ例を英語に変更 |
| D-2 | 軽微 | context_id=None スキップ時の logging | §6.6 の該当行に `logging.debug()` を追記。P1-3 テストにもログ確認を追記 |
| D-3 | 軽微 | 手動スモークの日付を実行可能な過去日付に | §8 Phase 4 のサンプルコードを更新 |
| E-1 | 将来 | `__repr__` の品質 | 設計判断 7 に認識と後付け方針を追記 |

### Round 2

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| R2-P0-1 | 設計 | `RawContext.xml` のエンコーディング注記 | §6.3 の擬似コードに `raw.xml.encode("utf-8")` を明示。str → bytes 変換の理由をコメントで記述 |
| R2-P0-2 | 設計 | nsmap の `None` キー問題 | §6.5 の「重要」に注記追加。`prefix` は `str` 型なので `None` キーとは衝突しないことを明記 |
| R2-P0-3 | 設計 | エラーハンドリング戦略（fail-fast vs best-effort） | §6.6 冒頭に fail-fast 方針を明記。§6.3 の `_parse_single_context` docstring にも理由を記述 |
| R2-P1-4 | 設計 | Period 共通 `end_date` プロパティの検討 | 設計判断 8 に YAGNI 判断を追記。§11 引き継ぎに Day 15 での再検討項目として追記 |
| R2-P1-5 | 設計 | `dimensions` の順序保証 | 設計判断 9 に追記。§6.3 擬似コードに `findall()` 出現順保持を明記。テストでは順序非依存アサーション推奨 |
| R2-P1-6 | 設計 | `source_line` の伝播 | §6.3 の擬似コードステップ 5 に `raw.source_line` 転写を明記 |
| R2-P2-7 | テスト | 空白処理・境界値テスト追加 | P0-11〜P0-13 を追加（日付空白、QName 空白、空入力）。特に日付空白は実データで起こりうるため P0 レベル |
| R2-P2-8 | テスト | P1-5 結合テストの marker | `medium` + `integration` に変更（2 モジュールをまたぐ結合テスト） |
| R2-P3-9 | 将来 | Entity `scheme` を保持しない理由の明記 | 設計判断 10 に追記。v1.0.0 IFRS 対応時の検討事項として記録 |
| R2-P3-10 | 将来 | 名前空間定数の一時的重複の明記 | 設計判断 11 に追記。Day 12 で `_namespaces.py` に集約する方針を明記 |

### Round 3（妥当性検証済み、補遺として反映）

| ID | カテゴリ | 内容 | 対応 | 検証メモ |
|---|---|---|---|---|
| R3-P0-1 | 設計 | `Period = InstantPeriod \| DurationPeriod` 型エイリアス | §6.1 に `Period` 定義を追加。`StructuredContext.period` の型を `Period` に変更 | 妥当。下流モジュールで Union を毎回書く手間を削減 |
| R3-P0-2 | 設計 | 同一 `context_id` の重複ハンドリング | §6.3 擬似コードに last-wins + `logger.debug()` を追加。§6.6 エラー表に行を追加 | 妥当。parser.py strict=False は warn するが RawContext リストには追加する実装のため、structure_contexts() 側で対処が必要 |
| R3-P0-3 | 設計 | Phase 0 フォールバック記載 | §8 Phase 0 の確認ポイント後にフォールバック方針を追記 | リスクは非常に低い（`_serialize_outer_xml` が `element.nsmap` をコピーする実装確認済み）が、万が一のための記載として妥当 |
| R3-P1-4 | テスト | `pytest.mark.parametrize` の活用 | §7.4 に parametrize 推奨セクションを追加。統合候補を具体的に列挙 | 妥当。可読性とのトレードオフは実装者に委ねる |
| R3-P1-5 | 設計 | `__all__` の定義 | §6.7 に `__all__` 定義を追加。parser.py が `__all__` 未定義であることを不整合として注記 | 妥当。新規モジュールなので最初から定義する方が良い |
| R3-P1-6 | 設計 | ロガー規約 | §6.3 にロガー規約セクションを追加 | **レビュアーの前提に修正あり**: parser.py は `logging` 未使用（`warnings.warn()` を使用）。contexts.py の `logging.debug()` は新パターンであることを明記。debug レベルの内部イベントには `logging` が適切 |
| R3-P2-7 | テスト | `xmlns:xbrldi` fixture 変更の影響確認 | §8 Phase 1 に fixture 変更後の即時テスト実行チェック項目を追加 | 妥当。実装確認で既存テストへの影響はないことを確認済みだが、Phase 1 での早期確認は良い慣行 |
| R3-P2-8 | テスト | `DimensionMember.__repr__` の REPL 確認 | §8 Phase 4 に REPL 確認項目を追加 | 妥当。設計判断 7 と整合。v0.1.0 では目視確認のみ |

### Round 4（妥当性検証済み）

| ID | カテゴリ | 内容 | 対応 | 検証メモ |
|---|---|---|---|---|
| R4-1 | テスト | P0 テストに「重複 context_id」ケースが欠落 | §7.1 に P0-14 `test_structure_contexts_last_wins_on_duplicate_context_id` を追加 | 妥当。`structure_contexts()` 独自ロジックなので P0 必須 |
| R4-2 | 設計 | `<xbrli:forever/>` 遭遇時のエラーメッセージが不明瞭 | §6.3 の period パースを 2 段階チェック（period 要素存在 → 子要素判定）に分離。§6.6 エラー表も 2 行に分割 | 妥当。コストほぼゼロでエラーメッセージの精度が向上 |
| R4-3 | 設計 | entity/identifier テキストが空文字のケース | §6.3 に空文字チェック（`.strip()` 後に空 → `EdinetParseError`）を追加。§6.6 エラー表にも行を追加 | 妥当。fail-fast 方針との整合性あり |
| R4-4 | 設計 | `Period` 型エイリアスの runtime `isinstance` | §6.1 の `Period` docstring に runtime isinstance の挙動を注記 | **レビュアーの前提が不正確**: Python 3.10+ の `X \| Y` は `types.UnionType` を生成し、`isinstance(obj, Period)` は正常に動作する（実機確認済み）。`typing.Union` との混同を防ぐ注記として反映 |
| R4-5 | 軽微 | simple_pl.xbrl の entity_id (`E00001`) とテスト用 XML (`X99001-000`) の不整合 | §7.3 のコメントに entity_id の違いを注記。結合テストでは `"E00001"` でアサートするよう明記 | 妥当 |
| R4-6 | 軽微 | Phase 0 の確認スクリプトを Dimension 付き Context で実行すべき | §8 Phase 0 を Phase 0a（基本 nsmap 確認）/ Phase 0b（fixture 追加後の xbrldi 確認）に分割 | 妥当。Phase 0a は現 fixture で即実行可能、Phase 0b は Phase 1 の fixture 追加後に実行 |

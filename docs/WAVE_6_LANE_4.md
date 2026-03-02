# 並列実装の安全ルール（必ず遵守）

あなたは Wave 6 / Lane 4 を担当するエージェントです。
担当機能: custom_detection

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/taxonomy/custom.py` (新規)
   - `tests/test_xbrl/test_custom_detection.py` (新規)
   - `tests/fixtures/custom_detection/` (新規ディレクトリ)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - 既存の dataclass / class にフィールドを追加する場合は必ずデフォルト値を付与すること
   - 既存のフィールド名・型・関数シグネチャを変更してはならない
   - 既存の定数名を変更・削除してはならない（追加のみ可）

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリを作成すること
     例: `tests/fixtures/custom_detection/`

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.taxonomy.custom import detect_custom_items` （OK）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_custom_detection.py` に作成

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 5 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.dei` (DEI, AccountingStandard, PeriodType, extract_dei)
     - `edinet.xbrl._namespaces` (NS_* 定数, classify_namespace, NamespaceInfo, NamespaceCategory, is_standard_taxonomy, is_filer_namespace 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl.linkbase.definition` (DefinitionArc, DefinitionTree, parse_definition_linkbase 等)
     - `edinet.xbrl.linkbase.calculation` (CalculationLinkbase 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果を報告すること

---

# LANE 4 — taxonomy/custom_detection: 標準/非標準科目の分類と親標準科目の推定

## 0. 位置づけ

### FEATURES.md との対応

Wave 6 Lane 4 は、FEATURES.md の **taxonomy/custom_detection** に対応する。各 LineItem が EDINET 標準タクソノミに属するか、提出者別タクソノミ（企業固有の拡張科目）に属するかを判別し、非標準科目については Definition Linkbase の general-special arcrole を用いて「どの標準科目の特殊化か」を推定する機能を提供する。

FEATURES.md の定義:

> - taxonomy/custom_detection: is_standard フラグ [TODO]
>   - detail: 各 Fact が標準タクソノミか提出者別タクソノミかを判別。is_standard フラグの基盤

### WAVE_6.md での位置

> Lane D: taxonomy/custom_detect → 新規 xbrl/taxonomy/custom.py（既存は読み取りのみ）

### 設計方針: D3 の遵守

D3（LineItem 拡張ポリシー）により、**LineItem にフィールドを追加しない**。`is_standard` のような判定結果は外部関数 `detect_custom_items()` が返す `CustomDetectionResult` dataclass に格納する。LineItem は XBRL Fact の忠実な表現に徹する（17フィールド固定）。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl._namespaces` | `classify_namespace()`, `is_standard_taxonomy()`, `NamespaceInfo`, `NamespaceCategory` | read-only |
| `edinet.financial.statements` | `Statements` (入力型) | read-only |
| `edinet.models.financial` | `LineItem` (入力型) | read-only |
| `edinet.xbrl.linkbase.definition` | `DefinitionArc`, `DefinitionTree`, `parse_definition_linkbase` | read-only (optional) |

他レーンとのファイル衝突なし（全て新規ファイル作成）。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| E-6 | 直接 | 拡張科目の実態調査。1社あたり4〜91個の拡張科目、3カテゴリ（domainItemType, monetaryItemType, textBlockItemType）|
| D-3 | 直接 | 会計基準判別に名前空間を利用可能。`is_standard_taxonomy()` の判定基盤 |
| A-1 | 関連 | 名前空間 URI の全パターン。標準タクソノミ vs 提出者別の判定ルール |
| H-2 | 関連 | プレフィックス名ではなく名前空間 URI で要素を識別すべき |

---

## 1. 背景知識

### 1.1 拡張科目の実態（E-6.a.md より）

EDINET の提出書類では、提出者（企業）が標準タクソノミに存在しない独自の勘定科目を定義できる。E-6 の調査結果:

| 観点 | 結果 |
|------|------|
| 拡張科目の数 | 1社あたり 4〜91 個（中央値は約 20〜30 個） |
| 主な種類 | `domainItemType`（ドメイン項目）、`monetaryItemType`（金額項目）、`textBlockItemType`（注記テキスト） |
| wider-narrower arcrole | **EDINET では使用されていない**（0 インスタンス） |
| general-special arcrole | 拡張科目と標準科目の関係定義に使用される |
| 標準科目の再定義 | 提出者が標準タクソノミの concept を再定義することはない |

### 1.2 判定ロジック

名前空間 URI による判定:

```
http://disclosure.edinet-fsa.go.jp/taxonomy/...  → 標準タクソノミ (is_standard = True)
http://disclosure.edinet-fsa.go.jp/jpcrp030000/...  → 提出者別タクソノミ (is_standard = False)
```

`_namespaces.py` の `is_standard_taxonomy(uri)` が既にこの判定を実装済み。本モジュールはこれを LineItem 単位で適用し、結果を構造化して返す。

### 1.3 general-special arcrole による親標準科目の推定

Definition Linkbase には `general-special` arcrole のアークが含まれる場合がある。これは「一般的な概念（general）から特殊な概念（special）への関係」を表す:

```
DefinitionArc(
    from_concept="OtherCA",           # 標準科目（general）
    to_concept="SomeCustomConcept",   # 拡張科目（special）
    arcrole="http://www.xbrl.org/2003/arcrole/general-special",
    ...
)
```

この関係を逆引きすることで、拡張科目の `parent_standard_concept`（「どの標準科目の特殊化か」）を推定できる。

**重要**: E-6.a.md の調査結果より、`wider-narrower` arcrole は EDINET で使用されていない（0 インスタンス）。したがって `general-special` のみを対象とする。

### 1.4 既存基盤の活用

| 既存API | 提供元 | 本モジュールでの用途 |
|---------|--------|---------------------|
| `is_standard_taxonomy(uri)` | `_namespaces.py` | LineItem が標準科目か判定 |
| `classify_namespace(uri)` | `_namespaces.py` | 名前空間の詳細情報取得（`NamespaceInfo`） |
| `DefinitionArc.arcrole` | `definition.py` | general-special 関係の判定 |
| `DefinitionArc.from_concept` / `to_concept` | `definition.py` | 親子関係の走査 |
| `DefinitionArc.from_href` / `to_href` | `definition.py` | XSD パスによる標準/非標準判定 |
| `Statements.__iter__()` | `statements.py` | 全 LineItem のイテレーション |

---

## 2. ゴール

### 2.1 機能要件

1. **`detect_custom_items()` 関数の実装**
   - 入力: `Statements`
   - 出力: `CustomDetectionResult`
   - 各 LineItem を標準/非標準に分類する
   - D3 に従い LineItem にフィールドを追加しない

2. **`CustomDetectionResult` dataclass の定義**
   - `custom_items`: 非標準科目の情報タプル
   - `standard_items`: 標準科目の LineItem タプル
   - `custom_ratio`: 非標準科目の割合（0.0〜1.0）
   - `total_count`: 全科目数

3. **`CustomItemInfo` dataclass の定義**
   - `item`: 元の LineItem への参照
   - `namespace_info`: `NamespaceInfo`（名前空間の詳細情報）
   - `parent_standard_concept`: 親標準科目のローカル名（推定結果、None の場合あり）

4. **DefinitionLinkbase 経由での parent_standard_concept 推定**（optional 引数）
   - DefinitionLinkbase が渡された場合、general-special arcrole を逆引きして親標準科目を推定
   - 渡されなかった場合は `parent_standard_concept = None`

### 2.2 非ゴール

- **wider-narrower arcrole の処理**: E-6.a.md で EDINET 未使用と確認済み。実装しない
- **shadowing_target の深い意味論分析**: 拡張科目が標準科目を「上書き」するケースは存在しない（E-6.a.md）
- **LineItem へのフィールド追加**: D3 により禁止
- **FinancialStatement 単位の分析**: 入力は `Statements` 全体。個別 statement の分析は利用者側

---

## 3. データモデル設計

### 3.1 CustomItemInfo (frozen dataclass)

```python
from __future__ import annotations

from dataclasses import dataclass
from edinet.models.financial import LineItem
from edinet.xbrl._namespaces import NamespaceInfo


@dataclass(frozen=True, slots=True)
class CustomItemInfo:
    """非標準（拡張）科目の分析結果。

    Attributes:
        item: 元の LineItem への参照。
        namespace_info: 名前空間の分類結果（カテゴリ、EDINET コード等）。
        parent_standard_concept: general-special arcrole で推定した
            親標準科目のローカル名。DefinitionLinkbase が未指定、
            または該当する関係がない場合は None。
    """
    item: LineItem
    namespace_info: NamespaceInfo
    parent_standard_concept: str | None
```

### 3.2 CustomDetectionResult (frozen dataclass)

```python
@dataclass(frozen=True, slots=True)
class CustomDetectionResult:
    """標準/非標準科目の分類結果。

    Attributes:
        custom_items: 非標準科目の分析結果タプル。
        standard_items: 標準科目の LineItem タプル。
        custom_ratio: 非標準科目の割合（0.0〜1.0）。
            全科目数が 0 の場合は 0.0。
        total_count: 全科目数（custom + standard）。
    """
    custom_items: tuple[CustomItemInfo, ...]
    standard_items: tuple[LineItem, ...]
    custom_ratio: float
    total_count: int
```

**設計根拠**:

- `custom_ratio` を算出済みフィールドとする理由: 利用者が最も頻繁に参照する指標であり、`len(custom_items) / total_count` の冗長な計算を省く
- `standard_items` を `tuple[LineItem, ...]` にする理由: 標準科目については `NamespaceInfo` の付加価値が薄い（`is_standard=True` であることは自明）
- `total_count` を含める理由: 空の Statements に対して `custom_ratio = 0.0` を返す際、「0件中0件」と「100件中0件」を区別できるようにする

---

## 4. 実装詳細

### 4.1 メイン関数: `detect_custom_items()`

```python
from edinet.xbrl._namespaces import classify_namespace, is_standard_taxonomy
from edinet.financial.statements import Statements
from edinet.xbrl.linkbase.definition import DefinitionArc, DefinitionTree


# general-special arcrole の定数
_ARCROLE_GENERAL_SPECIAL = "http://www.xbrl.org/2003/arcrole/general-special"


def detect_custom_items(
    statements: Statements,
    *,
    definition_linkbase: dict[str, DefinitionTree] | None = None,
) -> CustomDetectionResult:
    """各 LineItem を標準/非標準に分類する。

    Statements 内の全 LineItem について、名前空間 URI を基に
    標準タクソノミか提出者別タクソノミかを判定する。
    非標準科目については NamespaceInfo と、Definition Linkbase が
    利用可能な場合は親標準科目の推定結果を付与する。

    Note:
        本関数は XBRL インスタンス内の Fact（LineItem）のみを対象とする。
        タクソノミ定義上の abstract 要素（domainItemType のセグメント Member 等）は
        XBRL インスタンスに Fact として出現しないため検出対象外である。
        E-6.a.md によると拡張科目の最多カテゴリは domainItemType（ディメンション
        Member）であり、custom_ratio は「Fact として報告された拡張科目の割合」
        であって「タクソノミ定義上の全拡張要素の割合」ではないことに注意。

        同一 concept が複数の期間・次元に出現する場合、各 Fact は独立にカウント
        される。連結・個別の両方にデータがある場合も同様に、各 Fact は独立に
        カウントされる（is_standard の判定は連結/個別に依存しない）。
        custom_ratio は Fact 単位の割合であり、ユニーク concept 数ベース
        の割合ではない。concept レベルの割合が必要な場合は
        ``{ci.item.local_name for ci in result.custom_items}`` で重複除去すること。

    Args:
        statements: build_statements() で構築した Statements。
        definition_linkbase: parse_definition_linkbase() の戻り値。
            指定した場合、general-special arcrole を用いて
            拡張科目の親標準科目を推定する。None の場合は推定しない。

    Returns:
        CustomDetectionResult。
    """
    custom: list[CustomItemInfo] = []
    standard: list[LineItem] = []

    # DefinitionLinkbase から逆引きインデックスを構築（optional）
    parent_index = _build_parent_index(definition_linkbase)

    # Statements は __iter__ を実装しているため public protocol でアクセスする。
    # _items への直接アクセスはリファクタリング耐性を損なうため避ける。
    for item in statements:
        if is_standard_taxonomy(item.namespace_uri):
            standard.append(item)
        else:
            ns_info = classify_namespace(item.namespace_uri)
            parent = parent_index.get(item.local_name)
            custom.append(
                CustomItemInfo(
                    item=item,
                    namespace_info=ns_info,
                    parent_standard_concept=parent,
                )
            )

    total = len(custom) + len(standard)
    ratio = len(custom) / total if total > 0 else 0.0

    return CustomDetectionResult(
        custom_items=tuple(custom),
        standard_items=tuple(standard),
        custom_ratio=ratio,
        total_count=total,
    )
```

### 4.2 from_href による標準/非標準判定: `_is_standard_href()`

general-special チェーンを辿る際、各概念が標準タクソノミに属するか提出者別タクソノミに属するかを判定する必要がある。`DefinitionArc` の `from_href` / `to_href` フィールドには XSD パス（例: `../jppfs_cor_2025-11-01.xsd#NetSales`）が格納されており、これのファイル名パターンで判定できる。

```python
import re

# 提出者別タクソノミの XSD ファイル名パターン。
# 例: "jpcrp030000-asr-001_E02144-000.xsd"
#     "jpcrp030000-asr-001_E12345-000.xsd"
# EDINET の提出者別タクソノミは必ず "jpcrp" + 数字で始まる XSD を持つ。
_FILER_XSD_RE = re.compile(r"jpcrp\d+")


def _is_standard_href(href: str) -> bool:
    """DefinitionArc の href が標準タクソノミの XSD を参照しているか判定する。

    提出者別タクソノミの XSD ファイル名は ``jpcrp`` + 数字で始まるパターンを持つ
    （例: ``jpcrp030000-asr-001_E02144-000.xsd``）。このパターンに一致しなければ
    標準タクソノミと判定する。

    Args:
        href: ``DefinitionArc.from_href`` または ``to_href``。
            形式: ``"../jppfs_cor_2025-11-01.xsd#NetSales"`` 等。

    Returns:
        標準タクソノミの XSD を参照している場合 True。
    """
    # href からファイル名部分を抽出（"#" より前、最後の "/" より後）
    path_part = href.split("#")[0] if "#" in href else href
    filename = path_part.rsplit("/", 1)[-1] if "/" in path_part else path_part
    # Note: 空文字列やフラグメントのみの href は標準として扱う（保守的判定）。
    # 実データでは DefinitionArc.from_href が空になることはないが、
    # 防御的に「標準 = 安全側」に倒す。
    # re.match() は文字列の先頭からマッチするため、ファイル名抽出後の
    # 先頭一致判定として機能する。
    return not bool(_FILER_XSD_RE.match(filename))
```

**根拠**:

EDINET の XSD ファイル名パターン（A-1.a.md、E-6.a.md で確認）:

| 種類 | パターン例 | `_FILER_XSD_RE` |
|------|-----------|-----------------|
| 標準タクソノミ | `jppfs_cor_2025-11-01.xsd` | 不一致 → **True**（標準） |
| 標準タクソノミ | `jpcrp_cor_2025-11-01.xsd` | 不一致（`jpcrp_cor` は `jpcrp\d+` に一致しない） → **True** |
| 提出者別 | `jpcrp030000-asr-001_E02144-000.xsd` | 一致 → **False**（提出者） |

`jpcrp_cor`（標準）と `jpcrp030000`（提出者別）は先頭は似ているが、`\d+` の有無で区別される。`jpcrp_cor` は `jpcrp` の後に `_` が続き、数字が続かないため `_FILER_XSD_RE` に一致しない。

### 4.3 逆引きインデックス構築: `_build_parent_index()`

```python
def _build_parent_index(
    definition_linkbase: dict[str, DefinitionTree] | None,
) -> dict[str, str]:
    """DefinitionLinkbase の general-special arcrole から逆引きインデックスを構築する。

    general-special arc は from_concept（general/親）→ to_concept（special/子）の
    方向で定義される。これを逆引きし、to_concept → 最も近い標準タクソノミ親概念の
    マッピングを返す。

    親が標準タクソノミに属さない場合（提出者別同士の general-special）はさらに
    親を辿り、標準タクソノミに到達した最初の概念を返す（再帰的な走査）。

    標準/非標準の判定は ``DefinitionArc.from_href`` の XSD ファイル名パターンで
    行う。提出者別タクソノミの XSD は ``jpcrp030000-...`` のようなパターンを持ち、
    標準タクソノミの XSD は ``jppfs_cor_2025-11-01.xsd`` のようなパターンを持つ。
    この判定により、general-special チェーンの途中に標準科目が存在する場合でも
    「最も近い標準タクソノミ祖先」を正確に返すことができる。

    Note:
        同一 local_name が複数の role で異なる general-special 関係を
        持つ場合は、後に走査された role の結果が採用される（上書き）。
        E-6.a.md の調査結果より、拡張科目の local_name は提出者内で
        ユニークであるため実用上問題にならない。

        計算量は O(N * D)（N = general-special arc 数、D = チェーン最大深さ）。
        EDINET の実データでは N ≤ 数十、D ≤ 2〜3 であり性能上の問題はない。

    Args:
        definition_linkbase: parse_definition_linkbase() の戻り値。None の場合は空辞書を返す。

    Returns:
        to_concept → 最も近い標準タクソノミ親概念のローカル名。
    """
    if definition_linkbase is None:
        return {}

    # Step 1: general-special arc の情報を収集
    # child → [(parent_concept, parent_href), ...] の逆引きマップ
    child_to_parents: dict[str, list[tuple[str, str]]] = {}
    for tree in definition_linkbase.values():
        for arc in tree.arcs:
            if arc.arcrole == _ARCROLE_GENERAL_SPECIAL:
                child_to_parents.setdefault(arc.to_concept, []).append(
                    (arc.from_concept, arc.from_href),
                )

    # Step 2: 各 child について、標準タクソノミに属する最も近い祖先を探す
    result: dict[str, str] = {}
    for child in child_to_parents:
        ancestor = _find_standard_ancestor(child, child_to_parents)
        if ancestor is not None:
            result[child] = ancestor

    return result
```

### 4.4 標準タクソノミ祖先の探索: `_find_standard_ancestor()`

```python
def _find_standard_ancestor(
    concept: str,
    child_to_parents: dict[str, list[tuple[str, str]]],
    *,
    _visited: set[str] | None = None,
) -> str | None:
    """general-special 関係を辿り、標準タクソノミに属する最も近い祖先を返す。

    ``DefinitionArc.from_href`` の XSD ファイル名パターンで標準/非標準を判定し、
    最初に標準タクソノミと判定された親概念を返す。直接の親が全て非標準の場合は
    さらに祖先を再帰的に辿る。

    Args:
        concept: 起点の concept ローカル名。
        child_to_parents: 全体の逆引きマップ。
            各エントリは ``(parent_concept, parent_href)`` のタプルリスト。
        _visited: 循環検出用の内部引数。

    Returns:
        標準タクソノミに属する最も近い祖先のローカル名。見つからない場合は None。
    """
    if _visited is None:
        _visited = set()
    _visited.add(concept)

    parents = child_to_parents.get(concept, [])
    for parent_concept, parent_href in parents:
        if parent_concept in _visited:
            continue  # 循環防止

        # from_href の XSD パターンで標準/非標準を判定
        if _is_standard_href(parent_href):
            return parent_concept

        # 親も非標準の場合、さらに祖先を辿る
        result = _find_standard_ancestor(
            parent_concept, child_to_parents, _visited=_visited,
        )
        if result is not None:
            return result

    return None
```

**設計判断**: 旧版では「general-special チェーンのルート（親を持たない概念）は必ず標準科目である」というヒューリスティックを使用していた。このヒューリスティックは E-6.a.md の「提出者は標準科目を再定義しない」という事実に基づいており実用上は機能するが、以下の2点で正確性に劣る:

1. **最も近い標準親 vs ルート**: 標準科目間にも general-special 関係が存在しうる場合（`StandardA → StandardB → FilerExtC`）、ヒューリスティックは `StandardA`（ルート）を返すが、正確には `StandardB`（最も近い標準親）を返すべきである。
2. **孤立ループ**: 提出者別同士の循環参照（仕様違反だが防御が必要）の場合、ヒューリスティックではルートが見つからず `None` になるが、途中に標準科目が存在する可能性を検出できない。

`from_href` ベースの判定を採用することで、チェーン上の任意の位置で標準科目を正確に検出でき、「最も近い標準タクソノミ祖先」を確実に返す。`_FILER_XSD_RE` パターンは EDINET の XSD 命名規則（A-1.a.md で確認済み）に基づく安定した判定基準である。

---

## 5. 使用例

### 5.1 基本的な使い方

```python
from edinet.xbrl.taxonomy.custom import detect_custom_items

# Statements のみで分類（parent_standard_concept は常に None）
result = detect_custom_items(statements)

print(f"全科目数: {result.total_count}")
print(f"拡張科目数: {len(result.custom_items)}")
print(f"標準科目数: {len(result.standard_items)}")
print(f"拡張科目率: {result.custom_ratio:.1%}")

for ci in result.custom_items:
    print(f"  {ci.item.local_name}: {ci.namespace_info.category.value}")
```

### 5.2 DefinitionLinkbase との連携（親標準科目推定）

```python
from edinet.xbrl.linkbase.definition import parse_definition_linkbase
from edinet.xbrl.taxonomy.custom import detect_custom_items

# Definition Linkbase をパース
with open("path/to/_def.xml", "rb") as f:
    def_trees = parse_definition_linkbase(f.read())

# DefinitionLinkbase を指定して分類
result = detect_custom_items(statements, definition_linkbase=def_trees)

for ci in result.custom_items:
    if ci.parent_standard_concept:
        print(f"  {ci.item.local_name} → 親: {ci.parent_standard_concept}")
    else:
        print(f"  {ci.item.local_name} → 親: 推定不可")
```

### 5.3 NamespaceInfo の活用

```python
from edinet.xbrl._namespaces import NamespaceCategory

result = detect_custom_items(statements)

# EDINET コードの抽出（提出者別タクソノミの場合）
for ci in result.custom_items:
    if ci.namespace_info.category == NamespaceCategory.FILER_TAXONOMY:
        print(f"  EDINET コード: {ci.namespace_info.edinet_code}")
```

---

## 6. テスト設計

`tests/test_xbrl/test_custom_detection.py` に以下のテストを作成する。

テストでは `_make_statements()` ヘルパーで `build_statements()` 経由の最小限の `Statements` を作成する。`detect_custom_items()` は `Statements` の public iteration protocol（`__iter__`）でアクセスするため、テスト用 `Statements` の内部状態は最小限でよい。

### 6.1 テスト用ヘルパー

```python
from decimal import Decimal
from datetime import date

from edinet.models.financial import LineItem
from edinet.xbrl.contexts import DurationPeriod
from edinet.financial.statements import Statements, build_statements
from edinet.xbrl.taxonomy import LabelInfo, LabelSource


def _make_line_item(
    *,
    namespace_uri: str = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor",
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000000"),
    order: int = 0,
) -> LineItem:
    """テスト用の最小限 LineItem を生成する。"""
    return LineItem(
        concept=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        label_ja=LabelInfo(text=local_name, role="label", lang="ja", source=LabelSource.FALLBACK),
        label_en=LabelInfo(text=local_name, role="label", lang="en", source=LabelSource.FALLBACK),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearDuration",
        period=DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)),
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


def _make_statements(items: list[LineItem]) -> Statements:
    """テスト用の最小限 Statements を生成する。

    build_statements() を使用して内部フィールドの初期化を委譲する。
    detect_custom_items() は Statements の __iter__ 経由で LineItem に
    アクセスするため、_detected_standard 等の他フィールドは不要。
    """
    return build_statements(items)
```

### 6.2 テストケース一覧（20テスト）

```python
class TestDetectCustomItems:
    """detect_custom_items() の単体テスト群。"""

    # --- 基本分類 ---

    def test_all_standard_items(self):
        """全科目が標準タクソノミの場合。custom_items は空、custom_ratio は 0.0。"""

    def test_all_custom_items(self):
        """全科目が提出者別タクソノミの場合。standard_items は空、custom_ratio は 1.0。"""

    def test_mixed_standard_custom(self):
        """標準と拡張が混在する場合。正しく分類されること。"""

    def test_custom_ratio_calculation(self):
        """custom_ratio が正しく計算されること（例: 3 標準 + 2 拡張 → 0.4）。"""

    def test_empty_statements(self):
        """空の Statements の場合。total_count=0, custom_ratio=0.0。"""

    def test_total_count_equals_sum(self):
        """total_count == len(custom_items) + len(standard_items) であること。"""

    def test_same_concept_multiple_periods(self):
        """同一拡張科目が当期・前期の両方に存在する場合。
        custom_items に2件含まれ、custom_ratio は Fact 単位で計算されること。
        例: 拡張科目 CustomSales が当期・前期に1件ずつ + 標準科目1件 → ratio = 2/3。"""

    def test_same_concept_consolidated_and_individual(self):
        """同一拡張科目が連結・個別の両方に存在する場合。
        custom_items に2件含まれ、Fact 単位でカウントされること。
        is_standard の判定は連結/個別に依存しないことの確認。"""

    # --- CustomItemInfo フィールド ---

    def test_custom_item_info_fields(self):
        """CustomItemInfo の各フィールドが正しく設定されること。
        item が元の LineItem を参照、namespace_info が NamespaceInfo、
        parent_standard_concept が None（linkbase 未指定時）。"""

    def test_namespace_info_populated(self):
        """CustomItemInfo.namespace_info が正しく設定されること。
        FILER_TAXONOMY カテゴリ、edinet_code の抽出等。"""

    def test_multiple_custom_namespaces(self):
        """複数の異なる提出者別名前空間が混在する場合。
        それぞれの namespace_info が正しいこと。"""

    # --- 順序保持 ---

    def test_standard_items_preserve_order(self):
        """standard_items の並び順が Statements のイテレーション順と一致すること。"""

    def test_custom_items_preserve_order(self):
        """custom_items の並び順が Statements のイテレーション順と一致すること。"""

    # --- parent_standard_concept 推定 ---

    def test_parent_standard_concept_found(self):
        """DefinitionLinkbase を指定し、general-special arcrole で
        親標準科目が見つかる場合。parent_standard_concept が設定されること。
        from_href が標準タクソノミ XSD を参照していることで判定。"""

    def test_parent_standard_concept_none_without_linkbase(self):
        """DefinitionLinkbase を指定しない場合、
        全ての parent_standard_concept が None であること。"""

    def test_parent_standard_concept_chain(self):
        """general-special が2段以上のチェーン（拡張→拡張→標準）の場合。
        最も近い標準科目の祖先が返されること。
        例: StandardA → FilerB → FilerC の場合、FilerC の parent は StandardA、
        FilerB の parent も StandardA。"""

    def test_parent_standard_concept_mid_chain(self):
        """標準科目間の general-special を挟むチェーンの場合。
        最も近い標準科目が返されること。
        例: StandardA → StandardB → FilerC の場合、
        FilerC の parent は StandardB（StandardA ではなく最も近い標準親）。"""

    def test_definition_linkbase_no_general_special(self):
        """DefinitionLinkbase を指定するが general-special arc がない場合。
        全ての parent_standard_concept が None であること。"""

    # --- エッジケース ---

    def test_circular_general_special(self):
        """general-special の循環参照がある場合（仕様違反の防御）。
        _visited による循環検出で無限再帰せず None が返ること。"""

    def test_chain_no_standard_root(self):
        """全ノードが提出者別タクソノミの孤立チェーンの場合。
        標準科目に到達できず parent_standard_concept が None であること。
        例: FilerA → FilerB（from_href が全て提出者別 XSD を参照）。"""

    def test_empty_dict_definition_linkbase(self):
        """definition_linkbase={} の場合。
        None と同様に全ての parent_standard_concept が None であること。
        空の dict は有効な入力であり、エラーにならないこと。"""
```

### 6.3 テスト用 DefinitionTree の構築

```python
from edinet.xbrl.linkbase.definition import DefinitionArc, DefinitionTree

_ARCROLE_GS = "http://www.xbrl.org/2003/arcrole/general-special"

# テスト用の XSD パス定数。_is_standard_href() の判定を制御する。
_STANDARD_XSD = "../jppfs_cor_2025-11-01.xsd"   # 標準タクソノミ
_FILER_XSD = "jpcrp030000-asr-001_E02144-000.xsd"  # 提出者別タクソノミ


def _make_gs_tree(
    arcs: list[tuple[str, str]],
    *,
    filer_concepts: set[str] | None = None,
) -> dict[str, DefinitionTree]:
    """テスト用の general-special DefinitionTree を構築する。

    Args:
        arcs: (parent, child) タプルのリスト。
        filer_concepts: 提出者別タクソノミとして扱う concept 名の集合。
            指定しない場合、全ての from_href は標準タクソノミ XSD を参照する。
            指定した場合、集合に含まれる concept の href は提出者別 XSD を参照する。
    """
    if filer_concepts is None:
        filer_concepts = set()

    def _href_for(concept: str) -> str:
        xsd = _FILER_XSD if concept in filer_concepts else _STANDARD_XSD
        return f"{xsd}#{concept}"

    def_arcs = tuple(
        DefinitionArc(
            from_concept=parent,
            to_concept=child,
            from_href=_href_for(parent),
            to_href=_href_for(child),
            arcrole=_ARCROLE_GS,
            order=float(i),
        )
        for i, (parent, child) in enumerate(arcs)
    )
    tree = DefinitionTree(
        role_uri="http://example.com/role/test",
        arcs=def_arcs,
        hypercubes=(),
    )
    return {"http://example.com/role/test": tree}
```

### 6.4 テスト用 DefinitionTree の使用例

```python
# 基本: StandardParent → FilerChild（from_href が標準 XSD）
tree = _make_gs_tree(
    [("OtherCA", "FilerSpecificCA")],
    filer_concepts={"FilerSpecificCA"},
)
# → OtherCA の from_href = "../jppfs_cor_2025-11-01.xsd#OtherCA"（標準）
# → FilerSpecificCA の parent_standard_concept = "OtherCA"

# 2段チェーン: Standard → Filer → Filer
tree = _make_gs_tree(
    [("StandardA", "FilerB"), ("FilerB", "FilerC")],
    filer_concepts={"FilerB", "FilerC"},
)
# → FilerC の parent_standard_concept = "StandardA"
# → FilerB の parent_standard_concept = "StandardA"

# 標準間チェーン: StandardA → StandardB → FilerC
tree = _make_gs_tree(
    [("StandardA", "StandardB"), ("StandardB", "FilerC")],
    filer_concepts={"FilerC"},
)
# → FilerC の parent_standard_concept = "StandardB"（最も近い標準親）

# 孤立ループ（全て提出者別）
tree = _make_gs_tree(
    [("FilerA", "FilerB")],
    filer_concepts={"FilerA", "FilerB"},
)
# → FilerB の parent_standard_concept = None（標準に到達できない）
```

---

## 7. ファイル変更サマリ

| ファイル | 操作 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/taxonomy/custom.py` | **新規** | `detect_custom_items()`, `CustomDetectionResult`, `CustomItemInfo`, `_is_standard_href()`, `_build_parent_index()`, `_find_standard_ancestor()` — 約120〜170行 |
| `tests/test_xbrl/test_custom_detection.py` | **新規** | 上記テスト群（20テスト関数） |
| ~~`tests/fixtures/custom_detection/`~~ | **不要** | 現在のテスト設計はインメモリヘルパー（`_make_line_item`, `_make_gs_tree`）で完結するため作成しない |

### 既存モジュールへの影響

- **影響なし**: `_namespaces.py`, `statements.py`, `definition.py`, `financial.py` は全て read-only で利用
- 既存テスト: 一切変更なし
- `__init__.py`: 一切変更なし

---

## 8. 設計判断の記録

### Q: なぜ `Statements` 全体を入力にするのか？`FinancialStatement` 単位ではないのか？

**A**: `Statements` は `__iter__` で全期間・全 dimension の LineItem をイテレーションできる。拡張科目の判定は期間や連結/個別に依存しないため、全 LineItem を一括で処理する方が効率的。利用者が特定の FinancialStatement のみ分析したい場合は、`result.custom_items` をフィルタすればよい。

### Q: なぜ `Statements._items` ではなく `__iter__` でアクセスするのか？

**A**: `_items` はアンダースコア付きの内部属性であり、将来のリファクタリングで変更される可能性がある。`Statements` は `__iter__` と `__len__` の public protocol を提供しているため（`statements.py:1062,1066`）、これを使うことでリファクタリング耐性が向上する。CLAUDE.md の「リファクタリング耐性が高く内部実装が変わっても壊れにくい」方針とも整合する。

### Q: `definition_linkbase` の型が `dict[str, DefinitionTree]` である理由は？

**A**: `parse_definition_linkbase()` の戻り値型がそのまま `dict[str, DefinitionTree]` であるため。`CalculationLinkbase` のようなラッパークラスは DefinitionLinkbase には存在しない（`definition.py` は `DefinitionTree` の辞書を直接返す設計）。利用者は `parse_definition_linkbase()` の結果をそのまま渡せる。

### Q: wider-narrower arcrole を将来的にサポートする可能性は？

**A**: E-6.a.md の調査で EDINET では wider-narrower が使用されていないことが確認済み。EDINET は XBRL 2.1 の定義リンクベースのみを使用し、Dimensions 1.0 拡張の wider-narrower は仕様上存在するが実データでは使われていない。将来 EDINET の仕様が変更された場合に備え、`_ARCROLE_GENERAL_SPECIAL` を定数化して拡張しやすくしているが、現時点では実装しない。

### Q: なぜ `from_href` パターンで標準/非標準を判定するのか？ルートヒューリスティックではだめか？

**A**: 旧版の「general-special チェーンのルート（親を持たない概念）= 標準科目」というヒューリスティックは E-6.a.md の事実に基づき実用上は機能するが、正確性に劣る2つのケースがある:

1. **標準科目間の general-special**: `StandardA → StandardB → FilerC` のようなチェーンで、ルートヒューリスティックは `StandardA` を返すが、正確には最も近い標準親 `StandardB` を返すべき。
2. **孤立提出者チェーン**: 提出者別同士の `FilerA → FilerB` で、途中に標準科目がない場合の判定が不正確。

`from_href` の XSD ファイル名パターン（`jpcrp\d+` = 提出者別）による判定は、チェーン上の任意の位置で標準/非標準を正確に判定でき、品質と正確性の面で優れている。`_FILER_XSD_RE` パターンは EDINET の XSD 命名規則（A-1.a.md で確認済み）に基づく安定した判定基準であり、W3C XBRL 仕様レベルの変更がない限り保守不要。

### Q: `_find_standard_ancestor()` の循環検出は必要か？

**A**: 理論上、definition linkbase に循環が含まれることは仕様違反だが、実データの品質を信頼せず防御的に実装する。`_visited` セットで循環を検出し、無限再帰を防止する。`CalculationLinkbase.ancestors_of()` でも同様の循環検出を実装している。テストケース `test_circular_general_special` で検証する。

### Q: `custom_ratio` を property ではなくフィールドにする理由は？

**A**: `CustomDetectionResult` は frozen dataclass であり、構築時に値が確定する。property にすると毎回 `len(custom_items) / total_count` を計算するが、frozen なので結果は変わらない。フィールドにして構築時に一度だけ計算する方が効率的であり、シリアライズ時にも値が自然に含まれる。

---

## 9. 後続機能との接続点

| 利用先 | 利用方法 |
|--------|----------|
| **将来: taxonomy/standard_mapping** | `parent_standard_concept` を使って非標準科目の横断比較を実現 |
| **将来: display/statements** | 拡張科目にマーキング（「※」等）を付与するための判定基盤 |
| **将来: validation/required** | 必須科目の欠落チェック時に、標準科目のみを対象とする判定 |
| **利用者の分析コード** | `custom_ratio` でレポート品質の指標化、`CustomItemInfo` で拡張科目の詳細分析 |

Lane 4 が提供する `detect_custom_items()` は、D5 命名規約の `detect_*` パターンに従い、発見・判定の結果を result dataclass で返す standalone 関数として設計されている。

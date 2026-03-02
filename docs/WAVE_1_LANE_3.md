# エージェントが守るべきルール

```
# 並列実装の安全ルール（必ず遵守）

あなたは Wave 1 / Lane 3 を担当するエージェントです。
担当機能: definition（Definition Linkbase の解析）

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/linkbase/definition.py` (新規)
   - `tests/test_xbrl/test_definition.py` (新規)
   - `tests/fixtures/linkbase_definition/` (新規ディレクトリ)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - 既存の dataclass / class にフィールドを追加する場合は必ずデフォルト値を付与すること
   - 既存のフィールド名・型・関数シグネチャを変更してはならない
   - 既存の定数名を変更・削除してはならない（追加のみ可）

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/taxonomy_mini/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/xbrl_fragments/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリを作成すること
     例: `tests/fixtures/linkbase_definition/`

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.linkbase.definition import parse_definition_linkbase` （OK）
   - 例: `from edinet.xbrl import parse_definition_linkbase` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_definition.py` に作成
   - 既存のテストファイル（test_contexts.py, test_facts.py, test_statements.py 等）は変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 0 で事前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl._namespaces` (NS_* 定数)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること
```

---

# LANE 3: Definition Linkbase の解析 (`def_links`)

## 0. 位置づけ

Wave 1 Lane 3 は、XBRL Definition Linkbase (`_def.xml`) をパースし、**ハイパーキューブ構造**（Table → Axis → Domain → Member）を木構造として提供するモジュールを新規作成する。

**FEATURES.md 上の対応項目**: `def_links` — Definition Linkbase の解析

**FUTUREPLAN.tmp.md 上の位置**:
- Phase 1-3 ではなく、Wave 1 L3 として並列実装
- 下流の主な消費者:
  - `statements/equity`（Phase 6-2）: SS の 2 次元構造に必須（E-1c）
  - `dimensions/consolidated`（Phase 5-5）: デフォルトメンバー情報
  - `dimensions/segments`（Phase 5-6）: OperatingSegmentsAxis 構造
  - `taxonomy/custom_detection`（Phase 5-4）: 非標準科目の Dimension 位置づけ

**Wave 1 における他レーンとの関係**:
- L1 (pres_tree) / L2 (calc_tree) と同じ `xbrl/linkbase/` パッケージに配置
- 3 レーンは完全に独立（ファイル接触なし、入力も独立した XML ファイル群）
- L4 (contexts), L5 (namespaces) との依存もなし（_namespaces.py の定数を import するのみ）

---

## 1. 背景知識

### 1.1 Definition Linkbase とは

Definition Linkbase (`_def.xml`) は XBRL Dimensions 1.0 仕様に基づく**多次元構造の定義**を行うリンクベースである。EDINET では以下の 2 つの用途がある:

1. **ハイパーキューブ定義（詳細ツリー `_ac_` / `_an_` / `_sc-t2_` / `_sn-t2_`）**: `all`, `hypercube-dimension`, `dimension-domain`, `dimension-default`, `domain-member` の 5 種 arcrole を使用。財務諸表の多次元構造を定義
2. **科目一覧ツリー（`_cm_`）**: `general-special` arcrole のみを使用。概念の汎化-特化関係を定義（表示目的ではなく分類目的）

ファイルパターンと構造の対応:
| ファイルパターン | arcrole | ハイパーキューブ | 用途 |
|----------------|---------|----------------|------|
| `*_cm_*` | `general-special` のみ | なし | 科目一覧ツリー |
| `*_ac_*`, `*_an_*`, `*_sc-t2_*`, `*_sn-t2_*` | 5 種の dimension arcrole | あり | 詳細ツリー |

パーサーの実装はファイルパターンに依存しない（全パターンを統一的にパース）が、E2E テストやデバッグ時に「ファイル名から期待構造を推測」する際に有用。

### 1.2 EDINET で使用される arcrole（6 種）

C-8.a.md より:

| arcrole | URI prefix | 件数（サンプル） | 用途 |
|---------|-----------|---------|------|
| `general-special` | `http://www.xbrl.org/2003/arcrole/` | 7 | 科目一覧ツリー |
| `all` | `http://xbrl.org/int/dim/arcrole/` | 50 | ルート要素 → Table |
| `hypercube-dimension` | `http://xbrl.org/int/dim/arcrole/` | 58 | Table → Axis |
| `dimension-domain` | `http://xbrl.org/int/dim/arcrole/` | 133 | Axis → Domain |
| `dimension-default` | `http://xbrl.org/int/dim/arcrole/` | 38 | デフォルトメンバー |
| `domain-member` | `http://xbrl.org/int/dim/arcrole/` | 654 | メンバー間・表示項目間 |

**`notAll` は EDINET では不使用**（C-8.a.md [F6] で 0 件確認済み）。

### 1.3 ハイパーキューブの階層構造

C-8.a.md, C-10.a.md の実ファイル分析より:

```
Heading (ルート要素)
  ├── [all] Table (closed=true, contextElement=scenario)
  │     └── [hypercube-dimension] Axis
  │           ├── [dimension-domain] Domain (usable=false)
  │           │     └── [domain-member] Member1
  │           │           └── [domain-member] SubMember1a
  │           └── [dimension-default] DefaultMember
  └── [domain-member] LineItems
        └── [domain-member] AbstractConcept
              └── [domain-member] Concept1
```

### 1.4 EDINET の主要 Axis（C-8.a.md [F7]）

| Axis | 使用ロール数 | Default Member | 主な用途 |
|------|------------|---------------|---------|
| ConsolidatedOrNonConsolidatedAxis | 30 | ConsolidatedMember | 連結/個別区別 |
| SequentialNumbersAxis | 11 | なし | 表形式データの行番号 |
| OperatingSegmentsAxis | 7 | EntityTotalMember | セグメント情報 |
| DirectorsAndOtherOfficersAxis | 3 | DirectorsAndOtherOfficersMember | 役員情報 |
| ComponentsOfEquityAxis | 2 | NetAssetsMember | SS 純資産内訳列 |
| ClassesOfSharesAxis | 2 | TotalClassesOfSharesMember | 株式種別 |

### 1.5 マージに関する注意

C-11.a.md より:
- Definition Linkbase は EDINET では**リキャスト方式**（提出者が標準を参照せず独立して再構成する）
- `use="prohibited"` は Definition Linkbase では**禁止**（ガイドライン明記）
- したがって arc の priority/prohibited 解決ロジックは**不要**
- 提出者の `_def.xml` と標準タクソノミの `_def.xml` は別の role URI を使用するため衝突しない

### 1.6 ミラー構造

C-8.a.md [F5] より:
- Definition Linkbase の科目ツリー部分は Presentation Linkbase の `parent-child` ツリーの「ミラー」
- 相違点: (1) Definition には `dimension-default` がある、(2) Presentation には `preferredLabel` がある、(3) arcrole が異なる（definition: `domain-member`, presentation: `parent-child`）

---

## 2. ゴール

### 2.1 公開 API

```python
from edinet.xbrl.linkbase.definition import (
    parse_definition_linkbase,    # XML bytes → DefinitionTree
    DefinitionTree,               # ロール単位の定義ツリー
    DefinitionArc,                # 1 つの arc（from → to + arcrole + 属性）
    HypercubeInfo,                # ハイパーキューブの構造化情報
    AxisInfo,                     # Axis の構造化情報（domain, default, members）
    MemberNode,                   # ドメイン配下のメンバーツリーノード
)
```

### 2.2 データモデル

```python
@dataclass(frozen=True, slots=True)
class DefinitionArc:
    """Definition Linkbase の 1 本の arc。

    Attributes:
        from_concept: 親 concept のローカル名（例: ``"ConsolidatedBalanceSheetHeading"``）。
        to_concept: 子 concept のローカル名（例: ``"BalanceSheetTable"``）。
        from_href: 親 concept の xlink:href（XSD 相対パス + フラグメント）。
        to_href: 子 concept の xlink:href。
        arcrole: arcrole URI。
        order: 表示順。
        closed: xbrldt:closed 属性値。``all`` arcrole のアークでのみ設定される。
            それ以外のアークでは**常に** ``None``（XML に属性が存在しても無視される）。
        context_element: xbrldt:contextElement 属性値。``all`` arcrole のアークでのみ設定される。
            それ以外のアークでは**常に** ``None``。
        usable: usable 属性値（domain-member arc で false の場合あり）。
    """
    from_concept: str
    to_concept: str
    from_href: str
    to_href: str
    arcrole: str
    order: float
    closed: bool | None = None
    context_element: str | None = None
    usable: bool = True


@dataclass(frozen=True, slots=True)
class MemberNode:
    """ドメイン配下のメンバーノード（ツリー構造）。

    ドメインをルートとし、domain-member arc による階層を再帰的に保持する。
    SS の列ヘッダー構築等で階層情報と usable フラグが必要。

    Attributes:
        concept: メンバーのローカル名（例: ``"ShareholdersEquityAbstract"``）。
        href: xlink:href（XSD 相対パス + フラグメント）。
        usable: Fact を持ちうるか。``False`` の場合は表示専用（Abstract 等）。
        children: 子メンバーノードのタプル（order 順ソート済み）。
    """
    concept: str
    href: str
    usable: bool = True
    children: tuple["MemberNode", ...] = ()

    def __repr__(self) -> str:
        return (
            f"MemberNode(concept={self.concept!r}, "
            f"usable={self.usable}, children={len(self.children)})"
        )


@dataclass(frozen=True, slots=True)
class AxisInfo:
    """1 つの Axis（次元軸）の構造化情報。

    Attributes:
        axis_concept: Axis のローカル名（例: ``"ComponentsOfEquityAxis"``）。
        order: hypercube-dimension arc の order 値（複数 Axis の表示順序）。
        domain: ドメインのルートノード。子にメンバー階層を再帰的に持つ。
            ドメインが未定義の場合は None。
        default_member: デフォルトメンバーのローカル名。
            デフォルトがない場合は None。
    """
    axis_concept: str
    order: float = 0.0
    domain: MemberNode | None = None
    default_member: str | None = None


@dataclass(frozen=True, slots=True)
class HypercubeInfo:
    """ハイパーキューブの構造化情報。

    Attributes:
        table_concept: Table のローカル名。
        heading_concept: Heading（ルート要素）のローカル名。
        axes: ハイパーキューブに属する Axis の情報（``hypercube-dimension`` arc の order 昇順でソート済み）。
        closed: ハイパーキューブが closed かどうか。
        context_element: ``"segment"`` or ``"scenario"``。
        line_items_concept: LineItems のローカル名。
            LineItems がない場合は None。
    """
    table_concept: str
    heading_concept: str
    axes: tuple[AxisInfo, ...]
    closed: bool
    context_element: str
    line_items_concept: str | None = None

    def __repr__(self) -> str:
        axes = ", ".join(a.axis_concept for a in self.axes)
        return (
            f"HypercubeInfo(table={self.table_concept!r}, "
            f"axes=[{axes}])"
        )


@dataclass(frozen=True, slots=True)
class DefinitionTree:
    """1 つの role URI に対応する定義ツリー。

    Attributes:
        role_uri: ロール URI。
        arcs: 全 arc のタプル。認識されない arcrole の arc も含む。
        hypercubes: 構造化されたハイパーキューブ情報のタプル。
            ``arcs`` の部分集合（``all``, ``hypercube-dimension``,
            ``dimension-domain``, ``dimension-default``, ``domain-member``
            arcrole）を構造化したもの。``general-special`` のみの role では
            空タプル（``has_hypercube`` == False）。
    """
    role_uri: str
    arcs: tuple[DefinitionArc, ...]
    hypercubes: tuple[HypercubeInfo, ...]

    @property
    def has_hypercube(self) -> bool:
        """ハイパーキューブ構造を含むかどうか。"""
        return len(self.hypercubes) > 0

    def __repr__(self) -> str:
        return (
            f"DefinitionTree(role_uri={self.role_uri!r}, "
            f"arcs={len(self.arcs)}, hypercubes={len(self.hypercubes)})"
        )
```

### 2.3 パース関数

```python
def parse_definition_linkbase(
    xml_bytes: bytes,
    *,
    source_path: str | None = None,
) -> dict[str, DefinitionTree]:
    """Definition Linkbase の XML bytes をパースする。

    Args:
        xml_bytes: _def.xml の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。

    Returns:
        role_uri をキー、DefinitionTree を値とする辞書。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
```

### 2.4 完了条件

1. `parse_definition_linkbase()` が標準タクソノミの `_def.xml` と提出者別の `_def.xml` の両方をパースできる
2. 全 6 種の arcrole を正しく解析し、`DefinitionArc` として返す
3. ハイパーキューブ構造を `HypercubeInfo` + `AxisInfo` に構造化する
4. `general-special` arcrole のツリーも `DefinitionArc` として返す（構造化は不要）
5. `usable` 属性を正しく解析する（`domain-member` arc で `usable="false"` のケースに対応）
6. 同一 concept への 2 つ目の loc（`xlink:label` に `_2` サフィックス）を正しく処理する（href フラグメントからローカル名を抽出し、`_2` サフィックスを自然に解決する）
7. `MemberNode` ツリーにより、ドメイン配下のメンバー階層と `usable` フラグが保持される
8. `DefinitionTree.has_hypercube` プロパティにより、ハイパーキューブ構造の有無を判定できる
9. テストが全パスし、既存テストを壊さない

---

## 3. 入力データの詳細

### 3.1 標準タクソノミの _def.xml ファイル

`ALL_20251101/taxonomy/jppfs/2025-11-01/r/{業種}/jppfs_{業種}_{期間}_{日付}_def_{諸表}.xml`

- ファイル命名: `jppfs_{業種コード}_{期間区分}_{日付}_def_{諸表}.xml`
- 期間区分: `ac`(連結通期), `an`(個別通期), `sc-t2`(中間連結), `sn-t2`(中間個別), `cm`(科目一覧)
- 諸表: `bs`, `pl`, `ss`, `cf` 等
- 1 ファイルに 1 つの `link:definitionLink` 要素（= 1 つの role URI）

### 3.2 提出者別タクソノミの _def.xml ファイル

ZIP 内 `XBRL/PublicDoc/` 配下:
- `{prefix}_def.xml` — 提出者が定義する全 role の定義リンクベースを 1 ファイルに集約
- 1 ファイルに**複数の** `link:definitionLink` 要素（role URI ごと）

### 3.3 XML 構造（C-10.a.md より）

```xml
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
  xmlns:xbrldt="http://xbrl.org/2005/xbrldt"
  xmlns:xlink="http://www.w3.org/1999/xlink">

  <link:roleRef roleURI="..." xlink:type="simple" xlink:href="..."/>
  <link:arcroleRef arcroleURI="http://xbrl.org/int/dim/arcrole/all"
    xlink:type="simple" xlink:href="http://www.xbrl.org/2005/xbrldt-2005.xsd#all"/>
  <!-- ... 他の arcroleRef ... -->

  <link:definitionLink xlink:type="extended" xlink:role="{role_uri}">
    <link:loc xlink:type="locator"
      xlink:href="{relative_path}#{prefix}_{ConceptName}"
      xlink:label="{ConceptName}"/>

    <link:definitionArc xlink:type="arc"
      xlink:arcrole="{arcrole_uri}"
      xlink:from="{from_label}" xlink:to="{to_label}"
      order="{float}"
      xbrldt:closed="true"          <!-- all arc のみ -->
      xbrldt:contextElement="scenario"  <!-- all arc のみ -->
    />
  </link:definitionLink>
</link:linkbase>
```

### 3.4 loc の xlink:label 命名規則

C-10.a.md [F5] より:
- `xlink:label` は XSD フラグメント識別子の concept 名部分と 100% 一致
- 同一 `extendedLink` 内で同一 concept を複数回参照する場合は `_2`, `_3` ... サフィックス付与
- 例: `ConsolidatedMember` と `ConsolidatedMember_2`（`dimension-default` と `dimension-domain` の両方で使用）

---

## 4. 実装ステップ

### Step 1: テストフィクスチャの作成

`tests/fixtures/linkbase_definition/` 配下に以下を作成:

1. **`simple_bs.xml`** — 最小限の BS 用定義リンクベース
   - 1 つの `definitionLink`（BS ロール）
   - ハイパーキューブ: Heading → Table → Axis → Domain/Default
   - 科目ツリー: Heading → LineItems → 2-3 科目
   - arcrole: `all`, `hypercube-dimension`, `dimension-domain`, `dimension-default`, `domain-member`

2. **`simple_ss.xml`** — SS 用定義リンクベース（2 次元構造）
   - `ComponentsOfEquityAxis` に複数メンバー（2-3 階層）
   - `StatementOfChangesInEquityLineItems` に複数行
   - `usable="false"` のドメイン要素を含む
   - 具体構造:
   ```
   StatementOfChangesInEquityHeading
     ├── [all] StatementOfChangesInEquityTable (closed=true, contextElement=scenario)
     │     └── [hypercube-dimension] ComponentsOfEquityAxis (order=1.0)
     │           ├── [dimension-domain] ComponentsOfEquityDomain (usable=false)
     │           │     ├── [domain-member] ShareholdersEquityAbstract (usable=false)
     │           │     │     ├── [domain-member] ShareCapital (order=1.0)
     │           │     │     └── [domain-member] RetainedEarnings (order=2.0)
     │           │     └── [domain-member] AccumulatedOtherComprehensiveIncome (order=3.0)
     │           └── [dimension-default] NetAssetsMember
     └── [domain-member] StatementOfChangesInEquityLineItems
           ├── [domain-member] IssuanceOfNewSharesSCE (order=1.0)
           └── [domain-member] DividendsFromSurplusSCE (order=2.0)
   ```
   - テスト対象: `usable=false` のドメインルートと Abstract メンバー、2 階層のメンバーネスト（Domain → Abstract → 具体メンバー）、`dimension-default`、LineItems サブツリー

3. **`general_special.xml`** — 科目一覧ツリー
   - `general-special` arcrole のみ
   - 3-5 の概念を持つ最小構造

4. **`multi_role.xml`** — 複数 role を持つ定義リンクベース
   - 3 つの `definitionLink` 要素:
     - ロール 1: BS ハイパーキューブ（標準タクソノミ風 href: `#jppfs_cor_*`）
     - ロール 2: PL ハイパーキューブ（提出者タクソノミ風 href + 標準 href 混在）— `_extract_concept_from_href()` の Strategy 1 / Strategy 2 が同一パース内で両方動作することを検証
     - ロール 3: 科目一覧ツリー（`general-special` のみ）— ハイパーキューブとの共存テスト
   - 提出者タクソノミの構造を模擬
   - ロール 2 の具体 XML 例:
   ```xml
   <!-- 提出者 + 標準が混在 -->
   <link:loc xlink:href="jpcrp030000-asr-001_X99001-000.xsd#X99001-000_CustomBSTable"
             xlink:label="CustomBSTable"/>
   <link:loc xlink:href="../../jppfs_cor_2025-11-01.xsd#jppfs_cor_ConsolidatedOrNonConsolidatedAxis"
             xlink:label="ConsolidatedOrNonConsolidatedAxis"/>
   ```

5. **`duplicate_loc.xml`** — 同一 concept の重複 loc
   - `_2` サフィックスのケースを含む

### Step 2: データモデル定義

`src/edinet/xbrl/linkbase/definition.py` に以下を定義:
- `DefinitionArc`: 1 本の arc（ローカル名 + href）
- `MemberNode`: ドメイン配下のメンバーツリーノード
- `AxisInfo`: Axis の構造化情報（domain は MemberNode ツリー）
- `HypercubeInfo`: ハイパーキューブの構造化情報
- `DefinitionTree`: ロール単位のツリー
- arcrole 定数（`_ARCROLE_ALL`, `_ARCROLE_HYPERCUBE_DIMENSION` 等）

全て frozen dataclass (slots=True)。

### Step 3: XML パーサー実装

低レベル XML パース:
1. `lxml.etree.fromstring()` で XML bytes をパース。失敗時は `EdinetParseError` を送出
2. 名前空間定数（`NS_LINK`, `NS_XLINK` は `_namespaces.py` から import、`_NS_XBRLDT` は本モジュール内で定義）
   - `logger = logging.getLogger(__name__)` をモジュールレベルで定義
3. `link:definitionLink` を走査し、role URI ごとに処理
4. `link:loc` → `{xlink:label: (concept_local_name, href)}` マップを構築
5. `link:definitionArc` → `DefinitionArc` に変換

**`usable` 属性のパース方針**: `usable` 属性は全ての `definitionArc` の XML 属性から読み取り、`DefinitionArc.usable` に格納する（方式 A: XML の忠実な反映）。意味的に有効なのは `domain-member` arcrole のみであり、下流は `arcrole == _ARCROLE_DOMAIN_MEMBER` のアークの `usable` のみ参照すべき。意味的フィルタリングは下流の責務とするのが関心の分離の原則に適う。

**concept ローカル名の解決**（L1/L2/L3 共通アプローチ）:
- `xlink:href` のフラグメント識別子（`#` 以降）から prefix を除去してローカル名を抽出する
- 例: `../../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales` → ローカル名 `NetSales`、href はそのまま保持
- `_extract_concept_from_href()` をプライベート関数として definition.py 内に実装する
- `xlink:label` は loc マップのキーとしてのみ使用し、concept 名には伝播させない
- これにより `_2` サフィックス問題が自然に解決される（`ConsolidatedMember` と `ConsolidatedMember_2` は同じ href フラグメントを持ち、同一のローカル名 `ConsolidatedMember` に解決される）
- namespace 解決は本パーサーのスコープ外。下流の L5 (namespaces) や将来の統合レイヤーの責務とする

**`_extract_concept_from_href()` の擬似コード**（L2 と同一の 2 段階戦略）:

EDINET タクソノミの href パターン:
| パターン | href 例 | Strategy | prefix | concept |
|---------|---------|----------|--------|---------|
| 標準（jppfs） | `../../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales` | 1 | `jppfs_cor` | `NetSales` |
| 標準（jpcrp） | `../../jpcrp_cor_2025-11-01.xsd#jpcrp_cor_NetSalesSummaryOfBusinessResults` | 1 | `jpcrp_cor` | `NetSalesSummaryOfBusinessResults` |
| 提出者別 | `jpcrp030000-asr-001_X99001-000.xsd#X99001-000_ProvisionForBonuses` | 2 | `X99001-000` | `ProvisionForBonuses` |
| DEI | `../../jpdei_cor_2025-11-01.xsd#jpdei_cor_AccountingStandardsDEI` | 1 | `jpdei_cor` | `AccountingStandardsDEI` |

```python
# Strategy 1 用: 標準タクソノミの XSD ファイル名パターン
# 非貪欲 .+? でバックトラックし「最後の _{YYYY-MM-DD}.xsd」直前までを prefix とする
_XSD_PREFIX_RE = re.compile(r"^(.+?)_\d{4}-\d{2}-\d{2}\.xsd$")

def _extract_concept_from_href(href: str) -> str | None:
    """xlink:href のフラグメントから concept ローカル名を抽出する。

    L2 (calc_tree) と同一の 2 段階戦略:
    1. XSD ファイル名ベース（標準タクソノミで有効）
    2. _[A-Z] 後方スキャン（提出者タクソノミで有効）

    Returns:
        concept ローカル名。フラグメントが見つからない場合は ``None``。
    """
    if "#" not in href:
        return None
    path_part, fragment = href.rsplit("#", 1)
    basename = path_part.rsplit("/", 1)[-1]

    # Strategy 1: 標準タクソノミ {prefix}_{YYYY-MM-DD}.xsd
    m = _XSD_PREFIX_RE.match(basename)
    if m is not None:
        prefix = m.group(1)
        expected = prefix + "_"
        if fragment.startswith(expected):
            return fragment[len(expected):]

    # Strategy 2: _[A-Z] 後方スキャン（末尾から逆走査し最後の _[A-Z] で分割）
    for i in range(len(fragment) - 1, 0, -1):
        if (
            fragment[i - 1] == "_"
            and fragment[i].isascii()
            and fragment[i].isupper()
        ):
            return fragment[i:]

    return fragment  # 分離不能な場合はフラグメント全体を返す
```

この関数は L1/L2/L3 で**同一のロジック**。Wave 統合時に `_common.py` に抽出する前提で、3 レーンが擬似コードレベルで合意している。L2 §3.3 と同一の 2 段階戦略 + 後方スキャン + `.isascii()` チェック + `None` 返却を採用。

**ロギング**: 既存コードベース（`parser.py`, `facts.py`, `taxonomy/__init__.py`）と同様に `logging.getLogger(__name__)` を使用:
```python
logger = logging.getLogger(__name__)

# パース開始時
logger.debug("定義リンクベースをパース中: %d definitionLink 要素", count)
# ロール処理
logger.debug("ロール %s: %d loc, %d arc", role_uri, len(locs), len(arcs))
# 完了時
logger.info("定義リンクベースのパース完了: %d ロール, %d ハイパーキューブ", len(trees), total_hc)
```

### Step 3.5: エラーハンドリング

全ての `warnings.warn` は `EdinetWarning`（`edinet.exceptions` で定義）をカテゴリとして使用する。`stacklevel` は既存コードベース（`parser.py`, `statements.py` で `stacklevel=3`）と一貫させる。`parse_definition_linkbase()` → 内部ループ → `warnings.warn()` のコールスタック深度に応じて、利用者コードの行を指すように設定すること。内部ヘルパー関数からの呼び出しではコールスタックが深くなるため、実装時に呼び出しパスを確認し適切な値を設定する。

| エラー条件 | 対応 | メッセージ例 |
|-----------|------|-------------|
| XML パース失敗 | `EdinetParseError` 送出 | `"定義リンクベースの XML パースに失敗しました: {source_path}"` |
| `definitionLink` に `xlink:role` 未設定 | `EdinetWarning` + スキップ | `"定義リンク: xlink:role が未設定のためスキップします"` |
| `xlink:from`/`to` が loc_map に見つからない | `EdinetWarning` + スキップ | `"定義リンク: 不明なロケーター参照 '{label}' をスキップします"` |
| `order` が存在するが数値でない | `EdinetWarning` + デフォルト 0.0 | `"定義リンク: order 値 '{value}' が不正です。0.0 を使用します"` |
| `order` が存在しない | デフォルト 0.0（警告なし） | — |
| `_extract_concept_from_href()` → `None`（フラグメントなし） | `EdinetWarning` + その loc をスキップ | `"定義リンク: loc の href にフラグメントがありません: '{href}'"` |
| 認識されない arcrole（6 種以外） | `DefinitionArc` として保持（スキップしない） | — |
| 空の `_def.xml`（definitionLink なし） | 空辞書を返す（エラーにしない） | — |

認識されない arcrole を保持する理由：将来のタクソノミ拡張に対する前方互換性。`DefinitionTree.arcs` に含まれるが、`HypercubeInfo` の構造化からは除外される。

> **注意**: CLAUDE.md の指示「エラーメッセージは日本語」に準拠する。

### Step 4: ハイパーキューブ構造化

パースした `DefinitionArc` の集合から `HypercubeInfo` を構築:

Note: 同一 heading から複数の `all` arc が存在する場合、各 arc に対して独立した `HypercubeInfo` が生成される。

```
for arc in arcs where arcrole == _ARCROLE_ALL:
    heading = arc.from_concept
    table = arc.to_concept
    closed = arc.closed
    context_element = arc.context_element

    # 1. この table に属する axes を収集
    axes = [a for a in arcs
            where a.arcrole == _ARCROLE_HYPERCUBE_DIMENSION
            and a.from_concept == table]

    # 2. 各 axis の domain, default, members を収集
    for axis_arc in axes:
        axis = axis_arc.to_concept
        # dimension-domain → ドメインを特定し MemberNode ツリーのルートとする
        domain_arcs = [a for a in arcs
                       if a.arcrole == _ARCROLE_DIMENSION_DOMAIN and a.from_concept == axis]
        domain_node = None
        if domain_arcs:
            da = domain_arcs[0]
            domain_node = _build_member_tree(
                concept=da.to_concept,
                href=da.to_href,
                usable=da.usable,  # ドメインは通常 usable=false
                arcs=arcs,
                visited=set(),
            )
        # dimension-default arc → デフォルトメンバーを特定
        default_arc = find(arcs, arcrole=_ARCROLE_DIMENSION_DEFAULT, from=axis)

    # 3. heading から domain-member で接続される *LineItems を特定
    line_items_arcs = [a for a in arcs
                       where a.arcrole == _ARCROLE_DOMAIN_MEMBER
                       and a.from_concept == heading
                       and a.to_concept.endswith("LineItems")]
    line_items = min(line_items_arcs, key=order).to_concept if line_items_arcs else None

    hypercubes.append(HypercubeInfo(
        table_concept=table,
        heading_concept=heading,
        axes=tuple(sorted(axis_infos, key=lambda a: a.order)),
        closed=closed,
        context_element=context_element,
        line_items_concept=line_items,
    ))
```

詳細:
1. `all` arcrole の arc を走査し、各 `(heading, table)` ペアについて `HypercubeInfo` を構築
2. `hypercube-dimension` arcrole の arc → `table` から接続される `axis` を列挙
3. `dimension-domain` arcrole の arc → 各 `axis` のドメインを特定
4. `dimension-default` arcrole の arc → 各 `axis` のデフォルトメンバーを特定
5. `domain-member` arcrole の arc → ドメイン配下のメンバーを `_build_member_tree()` で `MemberNode` ツリーとして再帰的に構築（各ノードに `usable` フラグを保持）
6. **LineItems の特定**:
   - Heading concept（`all` arc の `from` 側で既に特定済み）から、`domain-member` arcrole で接続される arc を列挙する
   - その中で `to_concept` が `*LineItems` で終わるものを `line_items_concept` とする
   - 該当が 0 件の場合は `line_items_concept = None`
   - 該当が複数の場合は `order` が最小のものを採用する

**`_build_member_tree()` の再帰アルゴリズム**:

実装ヒント: EDINET 実データの規模（1 role あたり最大 ~200 arc）では全 arc 線形走査で問題ない。パフォーマンスが問題になる場合は `domain-member` arc を `from_concept → list[DefinitionArc]` の dict に事前索引化する最適化が可能だが、v0.1.0 では不要。

```python
def _build_member_tree(
    concept: str,
    href: str,
    usable: bool,
    arcs: list[DefinitionArc],
    visited: set[str],
) -> MemberNode:
    """domain-member arc を再帰的に辿り MemberNode ツリーを構築する。

    Args:
        concept: 現在のノードの concept ローカル名。
        href: 現在のノードの xlink:href。
        usable: 現在のノードの usable フラグ。
        arcs: 現在の role 内の全 DefinitionArc。
        visited: 祖先パス上の concept 名（循環検出用、コピー方式）。
    """
    visited = visited | {concept}  # 兄弟間独立のイミュータブルコピー

    # このconcept を起点とする domain-member arc を収集（order 昇順）
    child_arcs = sorted(
        [a for a in arcs
         if a.arcrole == _ARCROLE_DOMAIN_MEMBER and a.from_concept == concept],
        key=lambda a: a.order,
    )

    children: list[MemberNode] = []
    for arc in child_arcs:
        if arc.to_concept in visited:
            logger.warning(
                "定義リンク: domain-member 循環参照を検出: %s → %s",
                concept, arc.to_concept,
            )
            continue  # 循環はスキップ（EdinetParseError ではない）
        child_node = _build_member_tree(
            concept=arc.to_concept,
            href=arc.to_href,
            usable=arc.usable,
            arcs=arcs,
            visited=visited,
        )
        children.append(child_node)

    return MemberNode(
        concept=concept,
        href=href,
        usable=usable,
        children=tuple(children),
    )
```

**`visited` の設計判断**: `visited | {concept}` でイミュータブルコピーを使用（コピー方式）。
- XBRL Dimensions 仕様は DAG を許容するため、兄弟経由で同一 Member に到達するダイヤモンド構造が理論上可能
- コピー方式なら各パス独立でツリーを構築し、データ欠落を防止
- EDINET 実データでは厳密な木構造がほぼ確実（E-1c.a.md）だが、防御的にコピー方式を採用

### Step 5: テスト実装

`tests/test_xbrl/test_definition.py` に以下のテストを実装:

1. **基本パース**: `simple_bs.xml` → 全 arcrole タイプの arc が正しく抽出される
2. **loc 解決**: `simple_bs.xml` → concept ローカル名と href が正しく格納される
3. **`_2` サフィックス解決**: `duplicate_loc.xml` → 同一 concept への複数参照が同一ローカル名に解決される
4. **ハイパーキューブ構造化**: `simple_bs.xml` → `HypercubeInfo` が正しく構築される
5. **Axis 情報**: `simple_bs.xml` → `AxisInfo.domain` の `MemberNode` ツリー階層、デフォルトメンバー、order 値が正しい
6. **MemberNode ツリー**: `simple_ss.xml` → `ComponentsOfEquityAxis` の `MemberNode` 階層、`usable=False` のノード検証
7. **order ソート**: `simple_bs.xml` → `HypercubeInfo.axes` が `hypercube-dimension` arc の order 昇順でソートされる
8. **科目一覧ツリー**: `general_special.xml` → `general-special` arc のみ、`has_hypercube` == False
9. **複数ロール + 提出者 href + 共存**: `multi_role.xml` → role URI ごとに分離、提出者 href パターンの concept 抽出、general-special と hypercube の共存
10. **不正 XML**: 不正な XML bytes → `EdinetParseError`
11. **不明ロケーター参照**: `xlink:from` が未知ラベル → `EdinetWarning` + スキップ

---

## 5. 設計上の判断事項

### 5.1 concept の識別方法

**選択肢**:
- (A) Clark notation (`{namespace_uri}local_name`) — core の `parser.py` / `RawFact` と統一
- (B) ローカル名 + href 保持 — L1 (pres_tree) / L2 (calc_tree) と統一
- (C) xlink:href のフラグメント識別子そのまま

**判断: (B) ローカル名 + href 保持**

理由:
- linkbase の `loc` 要素からは namespace URI を**直接取得できない**（XSD の `targetNamespace` を読む必要がある）。Clark notation に変換するには外部情報が必須であり、パーサーの責務を超える
- L1 は `xlink:label` をそのまま concept 名として使用（href は別フィールド）
- L2 は `xlink:href` フラグメントから prefix を除去したローカル名を使用（href は別フィールド）
- L3 は L2 と同じアプローチを採用する（Definition Linkbase では `_2` サフィックスの解決が必須であり、href フラグメントからの抽出が最も堅牢）
- 3 つのリンクベースパーサー間で concept 識別方式を揃えることで、統合フェーズでの突き合わせが容易になる
- namespace 解決は L5 (namespaces) や将来の統合レイヤーの責務とする

### 5.2 `_2` サフィックスの解決

**問題**: Definition Linkbase では、同一 concept を複数の arcrole で参照する場合に `xlink:label` に `_2` サフィックスが付与される。例: `ConsolidatedMember`（dimension-domain の to）と `ConsolidatedMember_2`（dimension-default の to）。ハイパーキューブ構造化ではこれらを**同一 concept として突き合わせる必要がある**。

**解決策**: L1/L2/L3 共通アプローチ
- `_extract_concept_from_href()` プライベート関数を definition.py 内に実装する
- `xlink:href` のフラグメント識別子（`#jppfs_cor_ConsolidatedMember`）から prefix（`jppfs_cor_`）を除去してローカル名（`ConsolidatedMember`）を得る
- `xlink:label` は loc マップのキーとしてのみ使用し、`DefinitionArc.from_concept` / `to_concept` には href から抽出したローカル名を格納する
- `_2` サフィックスは `xlink:label` にのみ付与され、`xlink:href` フラグメントには付与されないため、href 抽出方式で自然に解決される

**3 レーン共通方針**: L1 (pres_tree), L2 (calc_tree), L3 (def_links) の 3 レーン全てが `xlink:href` フラグメントからの concept ローカル名抽出を採用。`xlink:label` はツリー構築時の内部キーとしてのみ使用する。Definition Linkbase では `_2` サフィックスがハイパーキューブ構造化に影響するため、href ベース方式が特に重要。この一致により、Wave 統合時の共通ユーティリティ（`_common.py`）抽出が容易になる。

### 5.3 `general-special` arcrole の扱い

**判断**: `DefinitionArc` として返すが、`HypercubeInfo` への構造化は行わない。

理由:
- 科目一覧ツリーは `general-special` のみで構成され、ハイパーキューブ構造とは無関係
- `DefinitionTree.hypercubes` は空タプルになる（`all` arcrole が存在しない）
- 下流の `taxonomy/custom_detection` が `general-special` arc を利用する場合は、`DefinitionTree.arcs` から arcrole でフィルタして取得

### 5.4 `usable` 属性の扱い

**判断**: `DefinitionArc.usable` フィールドとして保持する。デフォルト `True`。さらに、`MemberNode.usable` フィールドにも伝播させる。

理由:
- E-1c.a.md [F7] より、ドメインやメンバーが値を持たない場合 `usable="false"` が設定される
- SS の列ヘッダーで「表示するが Fact は存在しない」Member の区別に必要
- `MemberNode` ツリーの各ノードに `usable` フラグを持たせることで、下流が階層走査しながら usable/non-usable を区別できる

### 5.5 `_namespaces.py` との関係

現在の `_namespaces.py` には `NS_XBRLDT` が定義されていない（L5 が追加する可能性あるが並列のため依存不可）。

**判断**: `definition.py` 内に**プライベート**定数として定義する（L5 との衝突回避）。

```python
# NS_XBRLDI (http://xbrl.org/2006/xbrldi) — Instance 用: xbrli:context 内の explicitMember 等
# _NS_XBRLDT (http://xbrl.org/2005/xbrldt) — Taxonomy 用: definitionArc の closed/contextElement 等
_NS_XBRLDT = "http://xbrl.org/2005/xbrldt"
```

Wave 完了後の統合タスクで `_namespaces.py` の `NS_XBRLDT` に一本化し、definition.py からの import に切り替える。

### 5.6 arcrole 定数

6 種の arcrole URI を定数として definition.py 内に定義する。可読性向上とタイポ防止のため。

```python
_ARCROLE_ALL = "http://xbrl.org/int/dim/arcrole/all"
_ARCROLE_HYPERCUBE_DIMENSION = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
_ARCROLE_DIMENSION_DOMAIN = "http://xbrl.org/int/dim/arcrole/dimension-domain"
_ARCROLE_DIMENSION_DEFAULT = "http://xbrl.org/int/dim/arcrole/dimension-default"
_ARCROLE_DOMAIN_MEMBER = "http://xbrl.org/int/dim/arcrole/domain-member"
_ARCROLE_GENERAL_SPECIAL = "http://www.xbrl.org/2003/arcrole/general-special"
```

全てプライベート定数（`_` プレフィックス）。公開が必要になった場合は統合タスクで検討する。

### 5.7 クエリメソッドについて

`DefinitionTree` や `HypercubeInfo` にクエリメソッド（`find_axis()`, `get_default_member()` 等）を追加することで下流の利便性が向上する（L2 の `CalculationLinkbase.children_of()` と同様のパターン）。

**判断**: v0.1.0 では省略し、下流の消費パターンが明確になった時点で追加する。

理由:
- CRITICAL-2 で導入した `MemberNode` ツリーにより、直接的なツリー走査が可能になった
- `AxisInfo.domain.children` でトップレベルメンバーを列挙できる
- クエリメソッドの設計は、下流（`dimensions/consolidated`, `statements/equity`）の具体的なアクセスパターンに基づいて行う方が適切

`arcrole_summary` デバッグプロパティ（arcrole 別件数の `Counter`）も同様に v0.1.0 では省略。開発中のデバッグ効率向上に有用だが、下流の消費パターン確定後に検討する。

### 5.8 返り値の型について

L1 (pres_tree) は `dict[str, PresentationTree]` を返す。L2 (calc_tree) は `CalculationLinkbase` コンテナを返す（内部インデックス + `children_of`/`ancestors_of` メソッド付き）。L3 は L1 と同じ `dict` スタイルを採用する。

理由:
- L2 はクエリメソッド（`children_of`/`ancestors_of`）の利便性が高く、内部インデックスの恩恵が大きい
- L3 は下流の消費パターンが未確定であり、コンテナの設計が premature になるリスクがある
- `MemberNode` ツリーにより、下流は直接的なツリー走査が可能（インデックス不要）
- 統合時に 3 パーサーの返り値スタイルを揃える検討が必要（L2 FEEDBACK B-1 参照）

---

## 6. テスト設計の方針

### 6.1 デトロイト派（古典派）の原則

- 内部実装（`_parse_loc_map` 等の private 関数）をテストしない
- 公開 API (`parse_definition_linkbase`) の入出力のみをテスト
- XML フィクスチャを入力とし、返却される `DefinitionTree` の内容を検証

### 6.2 テストの分類

| カテゴリ | テスト | フィクスチャ |
|---------|--------|------------|
| 基本パース | arcrole 別 arc 抽出 | `simple_bs.xml` |
| 基本パース | loc 解決（ローカル名 + href） | `simple_bs.xml` |
| 基本パース | `_2` サフィックス解決 | `duplicate_loc.xml` |
| 構造化 | HypercubeInfo 構築 | `simple_bs.xml` |
| 構造化 | AxisInfo (domain, default, order) | `simple_bs.xml` |
| 構造化 | MemberNode ツリー階層 | `simple_ss.xml` |
| 構造化 | order ソート（`hypercube-dimension` arc の order 昇順） | `simple_bs.xml` |
| エッジケース | usable=false の MemberNode | `simple_ss.xml` |
| エッジケース | general-special のみ（`has_hypercube` == False） | `general_special.xml` |
| エッジケース | 複数 role URI の分離 + 提出者 href パターン + hypercube/general-special 共存 | `multi_role.xml` |
| エラー | 不正 XML → EdinetParseError | (inline bytes) |
| エラー | 不明ロケーター参照 → EdinetWarning | (inline bytes) |

合計: 約 12 テスト

---

## 7. 参照ドキュメント

| ドキュメント | 参照内容 |
|------------|---------|
| C-8.a.md | ハイパーキューブ構造、arcrole 一覧、主要 Axis 一覧 |
| C-10.a.md | XML 構造の詳細（loc / arc の属性）、4 種リンクベースの比較 |
| C-11.a.md | マージアルゴリズム（Definition はリキャスト → prohibited 不要） |
| E-1c.a.md | SS の 2 次元構造（Definition Linkbase の主要利用先） |
| E-2.a.md | 連結/個別の ConsolidatedOrNonConsolidatedAxis |
| J-2.q.md | セグメント情報の OperatingSegmentsAxis |

---

## 8. ファイル一覧

### 作成ファイル

| パス | 種別 | 説明 |
|------|------|------|
| `src/edinet/xbrl/linkbase/definition.py` | 新規 | Definition Linkbase パーサー本体 |
| `tests/test_xbrl/test_definition.py` | 新規 | テスト |
| `tests/fixtures/linkbase_definition/simple_bs.xml` | 新規 | BS フィクスチャ |
| `tests/fixtures/linkbase_definition/simple_ss.xml` | 新規 | SS フィクスチャ |
| `tests/fixtures/linkbase_definition/general_special.xml` | 新規 | 科目一覧ツリーフィクスチャ |
| `tests/fixtures/linkbase_definition/multi_role.xml` | 新規 | 複数ロールフィクスチャ |
| `tests/fixtures/linkbase_definition/duplicate_loc.xml` | 新規 | 重複 loc フィクスチャ |

### 変更ファイル

なし（全て新規作成）

### 読み取り専用参照

| パス | 参照内容 |
|------|---------|
| `src/edinet/xbrl/_namespaces.py` | `NS_LINK`, `NS_XLINK` 定数 |
| `src/edinet/exceptions.py` | `EdinetParseError`, `EdinetWarning` |

---

## 9. リスク・懸念事項

### 9.1 href フラグメントからのローカル名抽出の堅牢性

**リスク**: `_extract_concept_from_href()` は EDINET タクソノミの命名規則（`{prefix}_{ConceptName}` 形式のフラグメント識別子）に依存する。IFRS タクソノミ等の異なるパターンでは抽出が失敗する可能性がある。

**緩和策**:
- EDINET の J-GAAP タクソノミでは `{prefix}_{ConceptName}` 形式が 100% 一致確認済み（C-10.a.md [F5]）
- L2 と同一の 2 段階戦略（Strategy 1: XSD ファイル名ベース、Strategy 2: `_[A-Z]` 後方スキャン）により、標準・提出者両パターンに対応
- IFRS タクソノミの href パターンは v0.2.0 で対応する際に `_extract_concept_from_href()` を拡張する
- 抽出に完全に失敗した場合はフラグメント全体をフォールバックとして返す。`#` がない場合は `None` を返し、呼び出し側で `EdinetWarning` + loc スキップ

### 9.2 L1 (pres_tree) / L2 (calc_tree) との共通ロジック

**リスク**: 3 つのリンクベースパーサーで `_extract_concept_from_href()` と loc マップ構築ロジックが重複する。

**緩和策**: Wave 1 完了後の統合タスクで共通ユーティリティ（`xbrl/linkbase/_common.py`）に抽出する。Lane 3 の時点では definition.py 内に自己完結させる。L2 と同じアプローチを採用しているため、統合時の共通化は容易。

### 9.3 大規模ファイルのパフォーマンス

**リスク**: 標準タクソノミの全 `_def.xml` を処理する場合のパフォーマンス。cai 業種の SS は 172 loc / 171 arc（E-1c.a.md [F2]）と大きい。

**緩和策**: lxml の iterparse は不要（ファイルは数百行程度）。通常の `etree.fromstring()` で十分。

### 9.4 実データでの検証

**リスク**: テストフィクスチャは手作り XML のみであり、実タクソノミの微妙なパターンを見落とす可能性がある。

**緩和策**: Wave 1 完了後に `tools/` 配下に `EDINET_TAXONOMY_ROOT` を使った E2E テストスクリプトを用意し、標準タクソノミの全 `_def.xml` に対して `parse_definition_linkbase()` を実行して以下を確認する:
- 例外が出ないこと
- 全 `_def.xml` において、`all` arc の `from` 側 (heading) から `domain-member` で接続される concept のうち、`*LineItems` で終わるものが必ず 0 または 1 件であること（`line_items_concept` サフィックスマッチの妥当性検証）

ユニットテストフィクスチャのリポジトリサイズ制約上、実データの同梱は避ける。

---

## 10. 変更ログ（フィードバック反映）

WAVE_1_LANE_3_FEEDBACK.md のフィードバックに基づく変更記録。

### rev.1 (2026-02-28) — フィードバック全項目反映

| FB ID | 判定 | 変更内容 | 影響セクション |
|-------|------|---------|--------------|
| **CRITICAL-1** | 採用 | concept 識別子を Clark notation からローカル名 + href に変更。`ns_map` パラメータ削除、`base_uri` → `source_path` に変更 | §2.1, §2.2 (`DefinitionArc` に `from_href`/`to_href` 追加), §2.3 (関数シグネチャ), §5.1 (全面書き換え), §5.2 (全面書き換え), §4 Step 3 (パース方式変更) |
| **CRITICAL-2** | 採用 | `MemberNode` ツリー型を新規導入。`AxisInfo.members: tuple[str, ...]` → `AxisInfo.domain: MemberNode \| None` に変更。メンバー階層と `usable` フラグを保持 | §2.1 (import 追加), §2.2 (`MemberNode` 追加、`AxisInfo` 全面書き換え), §2.4 (完了条件 7 追加), §4 Step 2/4/5, §5.4, §6.2 |
| **IMPORTANT-1** | 採用 | `_2` サフィックスの除去方針を明記。`xlink:href` フラグメントからのローカル名抽出（L2 と同じアプローチ）で自然に解決 | §5.2 (新規セクション), §4 Step 3 (全面書き換え), §9.1 (リスク内容変更) |
| **IMPORTANT-2** | 後回し | クエリメソッド（`find_axis()` 等）は v0.1.0 では省略。`MemberNode` ツリー導入により直接走査が可能になったため緊急性低下 | §5.7 (新規セクション) |
| **MINOR-1** | 採用 | `AxisInfo.order: float` フィールドを追加。`hypercube-dimension` arc の order 値を保持 | §2.2 (`AxisInfo`), §4 Step 5 テスト 3 |
| **MINOR-2** | 代替策採用 | 実データフィクスチャは同梱せず、`tools/` 配下の E2E テストスクリプトで代替 | §9.4 (新規リスク項目) |
| **MINOR-3** | 採用 | `NS_XBRLDT` → `_NS_XBRLDT` に変更（L5 との衝突回避） | §5.5 (定数名修正) |
| **MINOR-4** | 採用 | 6 種の arcrole 定数（`_ARCROLE_ALL` 等）を definition.py 内に定義 | §5.6 (新規セクション), §4 Step 2 |
| **MINOR-5** | 採用 | `base_uri` パラメータを削除し、L1/L2 と一致する `source_path: str \| None = None` に変更 | §2.3 (関数シグネチャ) — CRITICAL-1 と同時に対応 |

### rev.2 (2026-02-28) — rev.3 フィードバック反映

| FB ID | 判定 | 変更内容 | 影響セクション |
|-------|------|---------|--------------|
| **CRITICAL-1** | 採用 | `_extract_concept_from_href()` の擬似コード（方式 A: `_`+大文字パターン）を §4 Step 3 に追記。EDINET href パターン表も追加 | §4 Step 3 (擬似コード追加) |
| **CRITICAL-2** | 採用 | `line_items_concept` 特定アルゴリズムを明確化（Heading から `domain-member` で `*LineItems` 終端を探索、0 件→None、複数→order 最小） | §4 Step 4 point 6 (全面書き換え) |
| **IMPORTANT-1** | 採用 | エラーハンドリング表を §4 Step 3.5 に追加（L2 §3.4 と同形式、8 条件） | §4 Step 3.5 (新規セクション) |
| **IMPORTANT-2** | 採用 | §5.2 の L1 方針記述を更新。3 レーン全てが href ベース抽出を採用している旨に修正 | §5.2 (末尾パラグラフ全面書き換え) |
| **IMPORTANT-3** | 採用 | `DefinitionTree.has_hypercube` プロパティを追加 | §2.2 (`DefinitionTree`), §2.4 (完了条件 8 追加) |
| **MINOR-1** | 採用 | `MemberNode.__repr__`, `HypercubeInfo.__repr__`, `DefinitionTree.__repr__` を追加（再帰爆発対策 + REPL 体験向上） | §2.2 (3 クラスに `__repr__` 追加) |
| **MINOR-2** | 採用 | `logging.getLogger(__name__)` のロギングを §4 Step 3 に追記。debug/info レベルのログ例を記載 | §4 Step 3 (ロギング追記) |
| **MINOR-3** | 採用 | §6.2 テスト分類表をフィクスチャ対応表に拡充（12 テスト） | §6.2 (全面書き換え) |
| **MINOR-4** | 採用 | `multi_role.xml` に提出者タクソノミ風 href パターンのロールを追加 | §4 Step 1 (`multi_role.xml` 説明拡充) |
| **MINOR-5** | 採用 | `HypercubeInfo.axes` docstring に「`hypercube-dimension` arc の order 昇順」と明記 | §2.2 (`HypercubeInfo.axes` docstring) |
| **MINOR-6** | 採用 | §5.5 に `NS_XBRLDI`（Instance 用）と `_NS_XBRLDT`（Taxonomy 用）の区別コメントを追加 | §5.5 (コメント追加) |
| **MINOR-7** | 採用 | §4 Step 4 にイテレーション擬似コードを追加（`for arc in arcs where arcrole == _ARCROLE_ALL` ループ構造） | §4 Step 4 (擬似コード追加) |
| **Q1** | 採用 | `multi_role.xml` に `general-special` のみのロールを 3 つ目として追加（hypercube との共存テスト） | §4 Step 1 (`multi_role.xml`), §4 Step 5 テスト 9, §6.2 |
| **Q2** | 後回し | `arcrole_summary` デバッグプロパティは v0.1.0 では省略。§5.7 に記載 | §5.7 (末尾に追記) |

### rev.3 (2026-02-28) — rev.4 フィードバック反映

| FB ID | 判定 | 変更内容 | 影響セクション |
|-------|------|---------|--------------|
| **C-1** | 採用 | `_extract_concept_from_href()` を L2 §3.3 と同一の 2 段階戦略（Strategy 1: XSD ファイル名ベース + Strategy 2: `_[A-Z]` 後方スキャン）に置換。`_XSD_PREFIX_RE` 正規表現追加。返り値を `str \| None` に変更。エラーハンドリング表の href フラグメント関連行を `None` 返却ベースに統一 | §4 Step 3 (擬似コード全面置換), §4 Step 3.5 (エラーハンドリング表更新) |
| **C-2** | 採用 | `_build_member_tree()` の再帰アルゴリズム擬似コードを追加。visited コピー方式（イミュータブル `\|` 演算）で循環検出。ドメインルート初期化の具体コードを Step 4 擬似コードに統合 | §4 Step 4 (ドメインルート初期化明示 + `_build_member_tree` 擬似コード追加) |
| **I-1** | 採用 | 返り値の型（`dict` vs コンテナ）の設計判断を §5.8 に明示。L1/L2/L3 の比較と理由を記載 | §5.8 (新規セクション) |
| **I-2** | 採用 | `simple_ss.xml` フィクスチャの具体的なメンバー階層構造（SS のツリー図）を Step 1 に追記 | §4 Step 1 (`simple_ss.xml` 説明拡充) |
| **M-1** | 採用 | `DefinitionArc.closed` / `context_element` の docstring を強化。`all` 以外では**常に** `None` である旨を明記 | §2.2 (`DefinitionArc` docstring) |
| **M-2** | 採用 | `multi_role.xml` ロール 2 の具体 XML（提出者 + 標準混在）を追記 | §4 Step 1 (`multi_role.xml` 具体 XML 追加) |
| **M-3** | 採用 | `*LineItems` サフィックスマッチの E2E 検証項目を §9.4 に追加 | §9.4 (検証項目追記) |
| **M-4** | 採用 | `DefinitionTree` docstring の `arcs` / `hypercubes` 属性説明を拡充。関係性を明記 | §2.2 (`DefinitionTree` docstring) |
| **M-5** | 採用 | エラーハンドリング表の `order` 行を 2 行に分割（存在+不正値 vs 不存在） | §4 Step 3.5 (エラーハンドリング表更新) |
| **M-6** | 採用 | ファイルパターン (`_cm_` vs `_ac_` 等) と構造の対応表を §1.1 に追加 | §1.1 (対応表追記) |

### rev.4 (2026-02-28) — rev.5 フィードバック反映

| FB ID | 判定 | 変更内容 | 影響セクション |
|-------|------|---------|--------------|
| **H-1** | 採用 | `warnings.warn` の `stacklevel` パラメータを明記。既存コードベース（`parser.py`, `statements.py` で `stacklevel=3`）との一貫性を指示 | §4 Step 3.5 (エラーハンドリング表の直前に追記) |
| **M-7** | 採用 | `usable` 属性のパース方針を明示。方式 A（全 arc 型から XML 属性を読み取り）を採用。意味的フィルタリングは下流の責務 | §4 Step 3 (point 5 の直後に追記) |
| **M-8** | 採用 | `_build_member_tree()` の arc フィルタリングに事前インデックスの実装ヒントを追記（計画変更なし） | §4 Step 4 (`_build_member_tree` 擬似コード直前に追記) |
| **L-1** | 実装時考慮 | `_extract_concept_from_href()` の空フラグメントケース。計画変更不要、実装時に `if not fragment: return None` を考慮 | — |
| **L-2** | 実装時考慮 | テストでの `pytest.warns(EdinetWarning, match=...)` パターンのヒント。計画変更不要 | — |
| **L-3** | 採用 | 同一 heading → 複数 `HypercubeInfo` のケースが正しく処理される旨を Step 4 に 1 行追記 | §4 Step 4 (擬似コード直前に Note 追記) |

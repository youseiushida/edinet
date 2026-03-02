# Wave 1 / Lane 2 — calc_tree（計算リンクベースの木構造解析）

---

## エージェントが守るべきルール

### 並列実装の安全ルール（必ず遵守）

あなたは Wave 1 / Lane 2 を担当するエージェントです。
担当機能: calculation（計算リンクベース）

#### 絶対禁止事項

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
   - `src/edinet/xbrl/linkbase/calculation.py` (新規)
   - `tests/test_xbrl/test_calculation.py` (新規)
   - `tests/fixtures/linkbase_calculation/` (新規ディレクトリ)
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
   - テスト用フィクスチャが必要な場合は、`tests/fixtures/linkbase_calculation/` を作成すること

#### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - 例: `from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase` （OK）
   - 例: `from edinet.xbrl import parse_calculation_linkbase` （NG）

7. **テストファイルの命名規則**
   - `tests/test_xbrl/test_calculation.py` に作成

8. **他モジュールの利用は import のみ**
   - Wave 0 で事前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl._namespaces` (NS_* 定数)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

## LANE 2: Calculation Linkbase パーサー

### 0. 位置づけ

FEATURES.md より:

> **calc_tree**: Calculation Linkbase の木構造解析 [TODO]
> - depends: facts, namespaces
> - detail: 科目間の計算関係（親子・加減・weight）を木構造で提供。weight は `1`（加算）または `-1`（減算）（C-7）。「売上高」の内訳として各社独自の科目がぶら下がる構造を辿れる

FUTUREPLAN.tmp.md より:

> Wave 1 / L2: calc_tree → 新: `xbrl/linkbase/calculation.py` — 衝突なし

### 1. 背景と仕様根拠

#### 1.1 計算リンクベースとは

計算リンクベース（`_cal.xml`）は、XBRL の科目間の **加減算関係** を定義するリンクベースである。
例: `営業利益 = 売上総利益(+1) + 販管費(-1)`

- arcrole は `http://www.xbrl.org/2003/arcrole/summation-item` の **1 種類のみ** (C-7.6)
- weight は `+1`（加算）と `-1`（減算）の **2 値のみ** (C-7.1, 実データ 185 アーク全てで確認)
- Role URI は Presentation と **同一** のものを使用 (C-7.3)
- Abstract 要素は **含まれない**（値を持つ科目のみ）(C-10.a.md)

#### 1.2 リキャスト方式

EDINET では計算リンクはリキャスト（再構成）方式で管理される (C-11.4):

- 提出者は標準タクソノミの `_cal.xml` を **直接修正せず**、独自の `_cal.xml` を新規作成する (C-7 F2)
- `use="prohibited"` は計算リンクでは **指定できない** (C-11 F7)
- よって、標準タクソノミと提出者タクソノミの `_cal.xml` は **独立したファイル** として扱う

これは L1 の Presentation リンクベースと同様のアプローチであり、マージアルゴリズムの実装が不要。

#### 1.3 XML 構造（C-10.a.md より）

```xml
<link:calculationLink xlink:type="extended"
  xlink:role="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedBalanceSheet">

  <!-- 親: 資産合計 -->
  <link:loc xlink:type="locator"
    xlink:href="../../jppfs_cor_2025-11-01.xsd#jppfs_cor_Assets"
    xlink:label="Assets"/>
  <!-- 子: 流動資産 -->
  <link:loc xlink:type="locator"
    xlink:href="../../jppfs_cor_2025-11-01.xsd#jppfs_cor_CurrentAssets"
    xlink:label="CurrentAssets"/>
  <link:calculationArc xlink:type="arc"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
    xlink:from="Assets" xlink:to="CurrentAssets"
    order="1.0" weight="1"/>
  ...
</link:calculationLink>
```

要素の構成:
- `link:calculationLink` — 拡張リンク要素。`xlink:role` で財務諸表の種類（BS/PL/CF/SS/CI）を区別
- `link:loc` — ロケーター。`xlink:href` で concept XSD を参照、`xlink:label` で arc から参照される
- `link:calculationArc` — アーク。`xlink:from`/`xlink:to` で親子関係を定義、`weight` で加減算を指定

属性の詳細:
| 属性 | 説明 | 値域 |
|------|------|------|
| `xlink:arcrole` | アークロール（固定値） | `http://www.xbrl.org/2003/arcrole/summation-item` |
| `xlink:from` | 親科目の `xlink:label` 値 | ロケーターの label 参照 |
| `xlink:to` | 子科目の `xlink:label` 値 | ロケーターの label 参照 |
| `weight` | 加減算の方向 | `"1"` (加算) / `"-1"` (減算) |
| `order` | 同一親の下での順序 | 0以上の小数（例: `1.0`, `2.0`） |

#### 1.4 periodType 制約

EDINET 固有の制約 (C-7 F3, F4):
- 計算リンクは **同一の periodType の科目間でのみ** 設定可能
- CF 計算書の「現金及び現金同等物の増加額(duration) + 期首残高(instant) = 期末残高(instant)」のような
  duration/instant 混在の関係は計算リンクの **対象外**
- この制約はパーサー側で検証する必要はない（タクソノミ作成側が遵守する）

#### 1.5 計算不一致と丸め許容 (C-7.5)

- XBRL 2.1 仕様により、`decimals` 属性に基づく丸め許容が定義されている
- 子科目の合計と親科目の値が `decimals` の精度範囲内で一致すればよい
- 不一致があっても Fact 値自体は提出者の報告値として信頼してよい
- → 検証ロジックは Phase 9 (`validation/calc_check`) で実装、本 Lane では木構造の構築まで

#### 1.6 下流の利用先

calc_tree の出力は以下の機能で利用される:
- **validation/calc_check** (Phase 9): 計算リンクに基づく Fact 値の整合性検証
- **taxonomy/standard_mapping** (Phase 5): 非標準科目→標準科目の祖先マッピング（計算リンクを遡行）
- **taxonomy/concept_sets** (Wave 2 L1): CF の concept セット導出（一般事業会社(cns)には _pre_cf が存在しないため、calc_tree からの導出が補完手段）

Wave 2 L1 での想定利用パターン（CF concept セット導出）:
```python
# calc_tree から CF の concept セットを自動導出
cf_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfCashFlows-indirect"
cf_tree = linkbase.get_tree(cf_role)
if cf_tree:
    cf_concepts = {arc.child for arc in cf_tree.arcs}
    cf_concepts |= {arc.parent for arc in cf_tree.arcs}
```

### 2. データモデル設計

#### 2.1 CalculationArc — 1 本の計算アーク

```python
from typing import Literal

@dataclass(frozen=True, slots=True)
class CalculationArc:
    """計算リンクベースの 1 本のアーク。

    親科目と子科目の加減算関係を表す。

    Attributes:
        parent: 親科目の concept 名（ローカル名。例: ``"GrossProfit"``）。
            ``xlink:href`` のフラグメント部分からプレフィックスを除去した値。
        child: 子科目の concept 名。同上の方式で取得。
        parent_href: 親科目の xlink:href（XSD 相対パス + フラグメント）。
        child_href: 子科目の xlink:href。
        weight: 加減算の方向。``1``（加算）または ``-1``（減算）。
        order: 同一親の下での表示順序。
        role_uri: このアークが属するロール URI。
    """
    parent: str
    child: str
    parent_href: str
    child_href: str
    weight: Literal[1, -1]
    order: float
    role_uri: str

    def __repr__(self) -> str:
        sign = "+" if self.weight == 1 else "-"
        return f"CalculationArc({self.parent} {sign}→ {self.child})"
```

**設計判断**:
- **concept 名の source of truth は `xlink:href` のフラグメント部分**（プレフィックスを除去したローカル名）。`xlink:label` は loc_map のルックアップキーとしてのみ使用する。これにより `_2` サフィックスの問題が根本解決される（`xlink:label` が `"NetSales_2"` でも、`xlink:href` の `#jppfs_cor_NetSales` から正しく `"NetSales"` が得られる）
- `parent_href` / `child_href` を保持する理由は、下流で namespace URI の解決（名前空間プレフィックスの特定）が必要な場合への対応
- `weight` は `Literal[1, -1]` 型。EDINET では `1` / `-1` の 2 値のみ (C-7.1, 実データ 185 アーク全てで確認)。型レベルで値域を制約し、パース時にランタイム検証も行う
- `order` は `float` 型。`1.0`, `2.5` 等の小数値を扱う
- `role_uri` を保持する理由は、`children_of(role_uri=None)` で全 role 横断検索した際に各アークの出自を追跡可能にするため

> **Lane 1 との concept 名解決方式の差異について**: Lane 1 は `xlink:label` をそのまま concept 名として使用し `_2` サフィックスの除去を行わない方針（Lane 1 §6.2）。Lane 2 は `xlink:href` 由来に統一する。この差異は Wave 完了後の統合タスクで、Lane 1 も href 由来に移行することで解消する。計算リンクでは `ancestors_of` 等の探索で concept 名の正確性が不可欠なため、Lane 2 では href 由来を採用する

#### 2.2 CalculationTree — 1 つの role 内の計算木

```python
@dataclass(frozen=True, slots=True)
class CalculationTree:
    """1 つの role URI に属する計算木。

    Attributes:
        role_uri: ロール URI（例: ``"http://...rol_std_ConsolidatedBalanceSheet"``）。
        arcs: このロールに属する全アーク。XML 文書内の出現順（パース順）を保持する。
        roots: 親を持たない（= 他のアークの child に現れない）ルート科目名のタプル。
            順序は XML 内での初出順（``arcs`` のイテレーション順で最初に parent として出現した順）。
    """
    role_uri: str
    arcs: tuple[CalculationArc, ...]
    roots: tuple[str, ...]  # XML 内での初出順（arcs イテレーション順で最初に parent として出現した順）

    def __repr__(self) -> str:
        return (
            f"CalculationTree(role_uri={self.role_uri!r}, "
            f"arcs={len(self.arcs)}, roots={self.roots!r})"
        )
```

**設計判断**:
- `roots` を事前計算して保持する理由は、ツリー走査の起点を高速に取得するため
- `arcs` はタプルで immutable 保証

#### 2.3 CalculationLinkbase — パース結果全体のコンテナ

```python
@dataclass(frozen=True, slots=True)
class CalculationLinkbase:
    """計算リンクベースのパース結果。

    1 つの _cal.xml ファイル全体、または複数ファイルのマージ結果を格納する。

    Attributes:
        source_path: パース元のファイルパス（任意）。
        trees: role URI をキーとする CalculationTree の辞書。
            **注意**: ``frozen=True`` により ``trees`` 属性自体の再代入は禁止されるが、
            辞書の中身（要素の追加・削除）は Python の制約上防止できない。
            利用者は辞書の内容を変更しないこと。
    """
    source_path: str | None
    trees: dict[str, CalculationTree]
    # 内部インデックス（__post_init__ で構築、外部公開しない）
    _children_index: dict[tuple[str, str], tuple[CalculationArc, ...]] = field(
        init=False, repr=False, compare=False,
    )
    _parent_index: dict[tuple[str, str], tuple[CalculationArc, ...]] = field(
        init=False, repr=False, compare=False,
    )

    def __post_init__(self) -> None:
        """内部インデックスを構築する。

        frozen=True のため object.__setattr__ で設定する。
        """
        object.__setattr__(self, "_children_index", self._build_children_index())
        object.__setattr__(self, "_parent_index", self._build_parent_index())

    def __repr__(self) -> str:
        return (
            f"CalculationLinkbase(roles={len(self.trees)}, "
            f"arcs={sum(len(t.arcs) for t in self.trees.values())})"
        )
```

**公開メソッド**:

```python
    def get_tree(self, role_uri: str) -> CalculationTree | None:
        """指定 role URI の計算木を返す。"""

    def children_of(
        self, parent: str, *, role_uri: str | None = None,
    ) -> tuple[CalculationArc, ...]:
        """指定親科目の子アーク一覧を返す。

        Args:
            parent: 親科目の concept 名。
            role_uri: フィルタする role URI。``None`` の場合は全 role を横断検索する。

        Returns:
            子アークのタプル（order 昇順）。role_uri=None 時は (role_uri, order) でソート。

        実装パターン:
            if role_uri is not None:
                return self._children_index.get((role_uri, parent), ())
            # 全 role 横断: O(R) 走査（R は典型的に 8 程度、実用上 O(1) と等価）
            result: list[CalculationArc] = []
            for tree in self.trees.values():
                result.extend(self._children_index.get((tree.role_uri, parent), ()))
            return tuple(sorted(result, key=lambda a: (a.role_uri, a.order)))
        """

    def parent_of(
        self, child: str, *, role_uri: str | None = None,
    ) -> tuple[CalculationArc, ...]:
        """指定子科目の親アーク一覧を返す。

        1つの子科目が複数の role に属する場合や、同一 role 内で
        複数の親を持つ場合（XBRL 2.1 仕様上は許容される）があるため、
        結果はタプル。

        Args:
            child: 子科目の concept 名。
            role_uri: フィルタする role URI。``None`` の場合は全 role を横断検索する。

        Returns:
            親アークのタプル。
        """

    def ancestors_of(
        self, concept: str, *, role_uri: str,
    ) -> tuple[str, ...]:
        """指定科目から根に至るまでの祖先科目名を返す。

        開始 concept 自体は結果に含まない。結果は直接の親から根に向かう順序。
        concept がルート科目（親を持たない科目）の場合は空タプル ``()`` を返す。

        taxonomy/standard_mapping で使用。
        例: ``ancestors_of("InterestIncomeNOI", role_uri=...)``
            → ``("NonOperatingIncome", "OrdinaryIncome", "IncomeBeforeIncomeTaxes", "ProfitLoss")``

        循環参照が検出された場合はそこで走査を打ち切る（防御的コーディング）。
        同一 role 内で子が複数の親を持つ場合は最初の親のみを辿る。

        アルゴリズム:
            result = []
            visited = {concept}
            current = concept
            while (role_uri, current) in _parent_index:
                arcs = _parent_index[(role_uri, current)]
                current = arcs[0].parent  # 複数親がある場合は最初の親を辿る
                if current in visited:
                    break  # 循環参照を検出、走査打ち切り
                visited.add(current)
                result.append(current)
            return tuple(result)
        """

    @property
    def role_uris(self) -> tuple[str, ...]:
        """全 role URI のタプルを返す。

        順序は XML パース時の出現順（Python 3.7+ の dict 挿入順保証に依拠）。
        """
```

**設計判断**:
- `children_of` / `parent_of` は最も頻繁に使用される走査操作であり、`CalculationLinkbase` に集約して内部でインデックスを持たせる
- `ancestors_of` は standard_mapping の中核ロジックの前段であり、ここで提供しておく。循環参照は XBRL 仕様上禁止 (C-7 F3) だが、実データのバグに備え visited set で防御する
- 検証（calc_check）用のメソッドは Phase 9 の責務とし、本 Lane では提供しない

### 3. パーサー実装

#### 3.1 公開関数

```python
def parse_calculation_linkbase(
    xml_bytes: bytes,
    *,
    source_path: str | None = None,
) -> CalculationLinkbase:
    """_cal.xml の bytes をパースして CalculationLinkbase を返す。

    Args:
        xml_bytes: _cal.xml ファイルの bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。

    Returns:
        パース結果の CalculationLinkbase。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
```

#### 3.2 パースアルゴリズム

```
入力: _cal.xml bytes
出力: CalculationLinkbase

1. lxml.etree.fromstring() で XML をパース
   → 失敗時 EdinetParseError("計算リンクベースの XML パースに失敗しました: {source_path}")

2. ルート要素 (link:linkbase) を確認

3. 全 link:calculationLink 要素をイテレーション:
   各 calculationLink について:
   a. xlink:role 属性からロール URI を取得
      → 未設定の場合 EdinetWarning("計算リンク: xlink:role が未設定のためスキップします") + スキップ

   b. link:loc 要素から loc_map を構築:
      loc_map: dict[str, tuple[str, str]]
      key = xlink:label 値（_2 サフィックスを含む生の値。ルックアップキーとしてのみ使用）
      value = (_extract_concept_from_href(xlink:href) で得た concept ローカル名, xlink:href)

      ※ concept 名の source of truth は xlink:href のフラグメント部分
      ※ xlink:label は arc からの参照解決（ルックアップ）にのみ使用する
      ※ これにより _2 サフィックスの問題が根本的に解決される:
        - xlink:label="NetSales_2" でも
        - xlink:href="...#jppfs_cor_NetSales" → concept名は "NetSales"

   c. link:calculationArc 要素をイテレーション:
      - arcrole の検証（`summation-item` 以外はスキップ）【T-2 反映】:
        ```python
        ARCROLE_SUMMATION = "http://www.xbrl.org/2003/arcrole/summation-item"

        arcrole = arc_elem.get(f"{{{NS_XLINK}}}arcrole")
        if arcrole != ARCROLE_SUMMATION:
            warnings.warn(EdinetWarning(
                f"計算リンク: 未知の arcrole '{arcrole}' をスキップします"
            ))
            continue
        ```
      - xlink:from → loc_map から親の (concept_name, href) を解決
        → loc_map に見つからない場合 EdinetWarning + スキップ
      - xlink:to → loc_map から子の (concept_name, href) を解決
        → loc_map に見つからない場合 EdinetWarning + スキップ
      - weight 属性を Literal[1, -1] に変換（xsd:decimal 表記に対応）:
        ```python
        # weight のパース: xsd:decimal 表記に対応
        # XBRL 2.1 Schema では weight は xsd:decimal 型のため、
        # "1" だけでなく "1.0", "1.00", "-1.0" も有効な表記。
        # weight は XLink 名前空間ではなく、XBRL 2.1 が定義した直接属性【T-1 反映】
        weight_str = arc_elem.get("weight")  # NOT f"{{{NS_XLINK}}}weight"
        try:
            w = float(weight_str)
        except (ValueError, TypeError):
            warnings.warn(...)  # スキップ
            continue
        if w == 1.0:
            weight: Literal[1, -1] = 1
        elif w == -1.0:
            weight = -1
        else:
            warnings.warn(...)  # スキップ
            continue
        ```
        → float 変換失敗または 1.0/-1.0 以外の場合 EdinetWarning + スキップ
      - order 属性を float に変換
        → order 属性が未設定の場合は `0.0` にフォールバック + `EdinetWarning`
        ```python
        # order と weight は XLink 名前空間ではなく、XBRL 2.1 が定義した直接属性【T-1 反映】
        order_str = arc_elem.get("order")  # NOT f"{{{NS_XLINK}}}order"
        if order_str is None:
            warnings.warn(EdinetWarning("計算リンク: order 属性が未設定のため 0.0 を使用します"))
            order = 0.0
        else:
            order = float(order_str)
        ```

   d. CalculationArc を生成（role_uri も設定）

   e. roots を算出: parent の集合 - child の集合（XML 内での初出順を保持）
      ```python
      # arcs のイテレーション順で最初に parent として出現した順序を保持
      seen: set[str] = set()
      child_set = {arc.child for arc in arcs}
      roots: list[str] = []
      for arc in arcs:
          if arc.parent not in seen and arc.parent not in child_set:
              seen.add(arc.parent)
              roots.append(arc.parent)
      ```

4. role URI → CalculationTree の dict を構築

5. CalculationLinkbase を返却
```

#### 3.3 concept 名の解決方式

**source of truth: `xlink:href` のフラグメント部分**

C-10.a.md の調査結果に基づく:

- `xlink:href` のフラグメント部分は `{prefix}_{ConceptName}` 形式（例: `jppfs_cor_NetSales`）
- `_extract_concept_from_href()` でプレフィックスを除去し、ローカル名（`NetSales`）を取得する
- `xlink:label` は通常 concept 名と 100% 一致する (C-10.a.md F5) が、同一 extendedLink 内で重複する場合は `_2`, `_3` サフィックスが付く
- **`xlink:label` は loc_map のルックアップキーとしてのみ使用**し、concept 名としては使わない

**実装方針**: `xlink:href` のフラグメント（`#` 以降）をパースして concept ローカル名を取得する `_extract_concept_from_href()` を `calculation.py` 内にプライベート関数として実装する。既存の `taxonomy/__init__.py` の `_extract_prefix_and_local()` と同等の **2段階戦略** を採用する。

```python
# Strategy 1 用: 標準タクソノミの XSD ファイル名パターン
# 既存の taxonomy/__init__.py と同一の greedy `.+` を使用し、
# 統合タスク時の差分を最小化する【T-3 反映（案A）】
# 例: "jppfs_cor_2025-11-01.xsd" → group(1) = "jppfs_cor"
# EDINET のファイル名体系では greedy/non-greedy で結果は等価。
_XSD_PREFIX_RE = re.compile(r"^(.+)_\d{4}-\d{2}-\d{2}\.xsd$")

def _extract_concept_from_href(href: str) -> str | None:
    """xlink:href のフラグメントから concept ローカル名を抽出する。

    既存の ``taxonomy/__init__.py`` の ``_extract_prefix_and_local()`` と
    同等の 2 段階戦略を使用する:

    1. **Strategy 1（XSD ファイル名ベース）**: href のパス部分から XSD
       ファイル名を取得し、``{prefix}_{YYYY-MM-DD}.xsd`` パターンで prefix を
       推定。フラグメント先頭の ``{prefix}_`` を除去して concept 名を得る。
       標準タクソノミ（``jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales``）で有効。

    2. **Strategy 2（``_[A-Z]`` 境界フォールバック）**: Strategy 1 が不一致の場合、
       フラグメント末尾から逆走査し、最後の ``_[A-Z]``（アンダースコア直後が
       ASCII 大文字）の位置で分割する。提出者タクソノミ
       （``X99001-000_ProvisionForBonuses``）で有効。EDINET の concept 名は
       PascalCase が仕様上強制される（ガイドライン §5-2-1-1 LC3 方式）。

    Args:
        href: ``"../../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales"`` のような文字列。

    Returns:
        ``"NetSales"`` のような concept ローカル名。
        フラグメントが見つからない場合は ``None``。

    具体例:
        | href | Strategy | 結果 |
        |------|----------|------|
        | ``../../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales`` | 1 | ``NetSales`` |
        | ``filer.xsd#X99001-000_ProvisionForBonuses`` | 2 | ``ProvisionForBonuses`` |
        | ``../../jppfs_cor_2025-11-01.xsd#jppfs_cor_LossOnSalesOfNoncurrentAssetsEL`` | 1 | ``LossOnSalesOfNoncurrentAssetsEL`` |
    """
    if "#" not in href:
        return None
    path_part, fragment = href.rsplit("#", 1)
    basename = path_part.rsplit("/", 1)[-1]

    # Strategy 1: 標準タクソノミパターン {prefix}_{YYYY-MM-DD}.xsd
    m = _XSD_PREFIX_RE.match(basename)
    if m is not None:
        prefix = m.group(1)
        expected = prefix + "_"
        if fragment.startswith(expected):
            return fragment[len(expected):]

    # Strategy 2: _[A-Z] 境界フォールバック
    for i in range(len(fragment) - 1, 0, -1):
        if (
            fragment[i - 1] == "_"
            and fragment[i].isascii()
            and fragment[i].isupper()
        ):
            return fragment[i:]
    return fragment  # 分離不能な場合は全体を返す
```

#### 3.4 エラーハンドリング

| エラー条件 | 対応 | メッセージ例 |
|-----------|------|-------------|
| XML パース失敗 | `EdinetParseError` を送出 | `"計算リンクベースの XML パースに失敗しました: {source_path}"` |
| `calculationArc` の `arcrole` が `summation-item` でない | `warnings.warn(EdinetWarning)` で警告し、そのアークをスキップ【T-2 反映】 | `"計算リンク: 未知の arcrole '{arcrole}' をスキップします"` |
| `xlink:from` / `xlink:to` が loc_map に見つからない | `warnings.warn(EdinetWarning)` で警告し、そのアークをスキップ | `"計算リンク: 不明なロケーター参照 '{from_label}' をスキップします"` |
| `weight` が `float()` 変換不能、または `1.0` / `-1.0` 以外 | `warnings.warn(EdinetWarning)` で警告し、そのアークをスキップ | `"計算リンク: 不正な weight 値 '{weight}' をスキップします（期待値: 1 または -1）"` |
| `calculationLink` に `xlink:role` が未設定 | `warnings.warn(EdinetWarning)` で警告し、そのリンクをスキップ | `"計算リンク: xlink:role が未設定のためスキップします"` |
| `xlink:href` にフラグメント（`#`）がない | `warnings.warn(EdinetWarning)` で警告し、その loc をスキップ | `"計算リンク: loc 要素の href にフラグメントがありません: '{href}'"` |
| `order` 属性が未設定 | `0.0` にフォールバック + `warnings.warn(EdinetWarning)` | `"計算リンク: order 属性が未設定のため 0.0 を使用します"` |
| `calculationLink` に `calculationArc` が 0 件 | 空の `CalculationTree(arcs=(), roots=())` を生成し `trees` に含める | — |
| 空の `_cal.xml`（calculationLink なし） | 空の `CalculationLinkbase` を返す（エラーにしない） | — |

> **注意**: CLAUDE.md の指示「エラーメッセージは日本語」に準拠する。

### 4. 内部インデックス

`CalculationLinkbase.__post_init__()` で以下の逆引きインデックスを構築し、`children_of` / `parent_of` / `ancestors_of` を O(1) 〜 O(depth) で返せるようにする。

`frozen=True, slots=True` 環境では `__post_init__` 内で `object.__setattr__()` を使用して設定する（セクション 2.3 の実装パターン参照）。

```python
# 内部インデックス（__post_init__ で構築、field(init=False, repr=False, compare=False)）
_children_index: dict[tuple[str, str], tuple[CalculationArc, ...]]
    # key = (role_uri, parent_concept), value = 子アーク一覧（order 昇順）
_parent_index: dict[tuple[str, str], tuple[CalculationArc, ...]]
    # key = (role_uri, child_concept), value = 親アーク一覧
    # XBRL 2.1 仕様上、同一 role 内で 1 子が複数親を持つことは禁止されていないため tuple で保持
    # 実データでは通常 1 件だが、サイレントなデータ欠落を防止する
```

構築ロジック:
```python
def _build_children_index(self) -> dict[tuple[str, str], tuple[CalculationArc, ...]]:
    index: dict[tuple[str, str], list[CalculationArc]] = {}
    for tree in self.trees.values():
        for arc in tree.arcs:
            key = (tree.role_uri, arc.parent)
            index.setdefault(key, []).append(arc)
    return {k: tuple(sorted(v, key=lambda a: a.order)) for k, v in index.items()}

def _build_parent_index(self) -> dict[tuple[str, str], tuple[CalculationArc, ...]]:
    # 同一子に複数親がある場合、tuple 内の順序は tree.arcs のイテレーション順（= XML パース順）。
    # ancestors_of は先頭の親（= XML 内で先に出現した arc の親）を辿る。
    index: dict[tuple[str, str], list[CalculationArc]] = {}
    for tree in self.trees.values():
        for arc in tree.arcs:
            key = (tree.role_uri, arc.child)
            index.setdefault(key, []).append(arc)
    return {k: tuple(v) for k, v in index.items()}
```

### 5. ファイル構成

```
src/edinet/xbrl/linkbase/
├── __init__.py              (既存、変更しない)
└── calculation.py           (新規)
    ├── CalculationArc       (dataclass)
    ├── CalculationTree       (dataclass)
    ├── CalculationLinkbase   (dataclass + メソッド)
    ├── parse_calculation_linkbase()  (公開関数)
    └── _extract_concept_from_href()  (プライベート)
    └── _parse_loc_map()              (プライベート)
    └── _parse_arcs()                 (プライベート)

tests/test_xbrl/
└── test_calculation.py      (新規)

tests/fixtures/linkbase_calculation/
├── standard_pl.xml          (連結PL計算リンクの最小XML)
├── standard_bs.xml          (連結BS計算リンクの最小XML)
├── filer_pl.xml             (提出者別PL計算リンク：拡張科目含む)
├── empty.xml                (空の計算リンクベース)
├── malformed.xml            (不正なXML)
└── circular.xml             (循環参照テスト用：A → B → A、自己参照：C → C)
```

#### 5.1 提出者独自科目フィクスチャの具体構造

`filer_pl.xml` は提出者の `_cal.xml` を再現する。標準科目と提出者独自科目が同一ツリー内に混在する構造:

```xml
<!-- 標準科目（jppfs_cor XSD 参照） -->
<link:loc xlink:href="../../jppfs_cor_2025-11-01.xsd#jppfs_cor_SellingGeneralAndAdministrativeExpenses"
          xlink:label="SellingGeneralAndAdministrativeExpenses"/>

<!-- 提出者独自科目（提出者 XSD 参照。プレフィックスが異なる） -->
<link:loc xlink:href="jpcrp030000-asr-001_X99001-000.xsd#X99001-000_ProvisionForBonuses"
          xlink:label="ProvisionForBonuses"/>

<link:calculationArc xlink:from="SellingGeneralAndAdministrativeExpenses"
    xlink:to="ProvisionForBonuses"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
    order="1.0" weight="1"/>
```

検証ポイント:
- `_extract_concept_from_href()` が提出者プレフィックス（`X99001-000_`）を正しく除去し `"ProvisionForBonuses"` を返すこと
- 標準科目と提出者科目の親子関係が正しく構築されること

### 6. テスト計画

テストは古典派（デトロイト派）に従い、内部実装に依存しない振る舞いベースで記述する。

#### 6.1 正常系テスト

| テスト | 内容 | 検証ポイント |
|--------|------|-------------|
| `test_parse_standard_pl` | 連結PL（NetSales, CostOfSales, GrossProfit 等）の計算木をパース | ツリー構造が正しいこと。roots が `ProfitLoss` であること。weight が正しいこと |
| `test_parse_standard_bs` | 連結BS（Assets = CurrentAssets + NoncurrentAssets + DeferredAssets）の計算木をパース | 全 weight が `1` であること（BS は加算のみ）。roots が `Assets`, `LiabilitiesAndNetAssets` であること |
| `test_children_of` | `children_of("GrossProfit")` が `[NetSales(+1), CostOfSales(-1)]` を order 昇順で返す | 正しい子アークが返ること、order でソートされていること |
| `test_parent_of` | `parent_of("NetSales")` が `GrossProfit` への weight=1 アークを返す | 正しい親アークが返ること |
| `test_ancestors_of` | `ancestors_of("InterestIncomeNOI", role_uri=...)` が `NonOperatingIncome → OrdinaryIncome → IncomeBeforeIncomeTaxes → ProfitLoss` の順で返す | 根まで正しく遡行できること |
| `test_multiple_roles` | 複数の role URI（連結BS + 連結PL）を含む _cal.xml（テスト内で bytes リテラルとして構築） | `role_uris` が 2 件返ること。各 role の `get_tree()` が正しいツリーを返すこと |
| `test_filer_custom_concepts` | 提出者独自科目（例: `ReserveForBonuses`）を含む計算ツリー | 拡張科目が標準科目の子として正しく位置づけられること |
| `test_order_sorting` | 同一親の子科目の order が `[1.0, 3.0, 5.0]` | `children_of` の結果が order 昇順であること |
| `test_negative_weight_pl` | PL の費用科目（`CostOfSales` = weight -1, `SellingGeneralAndAdministrativeExpenses` = weight -1） | 減算 weight が正しく保持されること |
| `test_children_of_cross_role` | `role_uri=None` で全 role を横断して子アークを検索 | 複数 role に跨るアークが全て返ること。ソートが `(role_uri, order)` であること |
| `test_parent_of_cross_role` | `role_uri=None` で同一 concept（例: `CurrentAssets`）が連結 BS と個別 BS の両方に出現 | 全 role のアークが返ること |
| `test_arc_has_role_uri` | パース結果の各 `CalculationArc` が正しい `role_uri` を保持すること | `arc.role_uri` がそのアークが属する `calculationLink` の `xlink:role` と一致 |
| `test_ancestors_of_root_concept` | ルート科目（`ProfitLoss`）の `ancestors_of` が空タプルを返すこと | `ancestors_of("ProfitLoss", role_uri=...)` → `()` |

#### 6.2 境界値・異常系テスト

| テスト | 内容 | 検証ポイント |
|--------|------|-------------|
| `test_empty_linkbase` | `calculationLink` 要素が 0 件の XML | 空の `CalculationLinkbase` が返ること（`trees` が空辞書） |
| `test_malformed_xml` | 不正な XML bytes | `EdinetParseError` が送出されること |
| `test_missing_loc_reference` | `xlink:from` が未知の label を参照する arc | `EdinetWarning` が発せられ、そのアークがスキップされること |
| `test_loc_with_suffix` | `xlink:label="NetSales_2"` のような重複ロケーター | href 由来の concept 名 `"NetSales"` が正しく解決されること（`_2` に影響されない） |
| `test_single_arc` | 1 件の arc のみの最小計算リンク | 正しくパースされること |
| `test_role_uri_missing` | `calculationLink` に `xlink:role` がない | `EdinetWarning` が発せられ、スキップされること |
| `test_ancestors_of_circular_reference` | `A → B → A` の循環参照と `C → C` の自己参照を含む計算リンク | `ancestors_of` が無限ループに陥らず、循環・自己参照を検出して打ち切ること |
| `test_invalid_weight_skipped_with_warning` | `weight="2"` のようなアークを含む XML | `EdinetWarning` が発せられ、そのアークがスキップされること |
| `test_href_without_fragment` | `xlink:href` に `#` がない loc 要素 | `EdinetWarning` が発せられ、その loc がスキップされること |

#### 6.3 フィクスチャ設計

**`standard_pl.xml`** — 連結 PL の最小計算ツリー（C-7.a.md F9 に基づく）:

```
ProfitLoss
├── IncomeBeforeIncomeTaxes (+1, order=1.0)
│   ├── OrdinaryIncome (+1, order=1.0)
│   │   ├── OperatingIncome (+1, order=1.0)
│   │   │   ├── GrossProfit (+1, order=1.0)
│   │   │   │   ├── NetSales (+1, order=1.0)
│   │   │   │   └── CostOfSales (-1, order=2.0)
│   │   │   └── SellingGeneralAndAdministrativeExpenses (-1, order=2.0)
│   │   ├── NonOperatingIncome (+1, order=2.0)
│   │   │   └── InterestIncomeNOI (+1, order=1.0)
│   │   └── NonOperatingExpenses (-1, order=3.0)
│   │       └── InterestExpensesNOE (+1, order=1.0)
│   ├── ExtraordinaryIncome (+1, order=2.0)
│   │   └── GainOnSalesOfInvestmentSecuritiesEI (+1, order=1.0)
│   └── ExtraordinaryLoss (-1, order=3.0)
│       ├── LossOnSalesOfNoncurrentAssetsEL (+1, order=1.0)
│       └── ImpairmentLossEL (+1, order=2.0)
└── IncomeTaxes (-1, order=2.0)
    ├── IncomeTaxesCurrent (+1, order=1.0)
    └── IncomeTaxesDeferred (+1, order=2.0)
```

> **注**: `ExtraordinaryLoss(-1)` の子が `(+1)` であるパターンは重要。費用科目の内訳は加算関係になる（「特別損失 = 固定資産売却損 + 減損損失」）。`IncomeTaxes(-1)` と併せて、中間ノードの `-1` weight パターンを 2 箇所でカバーしている。

**`standard_bs.xml`** — 連結 BS の最小計算ツリー:

```
Assets
├── CurrentAssets (+1, order=1.0)
│   ├── CashAndDeposits (+1, order=1.0)
│   └── Inventories (+1, order=2.0)
├── NoncurrentAssets (+1, order=2.0)
└── DeferredAssets (+1, order=3.0)

LiabilitiesAndNetAssets
├── Liabilities (+1, order=1.0)
│   └── CurrentLiabilities (+1, order=1.0)
└── NetAssets (+1, order=2.0)
```

### 7. 実装ステップ

| Step | 内容 | 所要目安 |
|------|------|---------|
| Step 1 | テストフィクスチャ XML の作成（`tests/fixtures/linkbase_calculation/` 配下） | — |
| Step 2 | データモデル定義（`CalculationArc`, `CalculationTree`, `CalculationLinkbase`） | — |
| Step 3 | `_extract_concept_from_href()` の実装 — `xlink:href` から concept ローカル名を抽出 | — |
| Step 4 | `parse_calculation_linkbase()` の実装 — XML パース → loc_map → arcs → CalculationTree | — |
| Step 5 | `CalculationLinkbase` のメソッド実装（`children_of`, `parent_of`, `ancestors_of`, `get_tree`） | — |
| Step 6 | 全テストの実行と合格確認 | — |
| Step 7 | `uv run ruff check src tests` でリントパス | — |
| Step 8 | 既存テスト全パス確認（`uv run pytest`） | — |

### 8. 依存関係

```
_namespaces.py (NS_LINK, NS_XLINK)  ←  calculation.py
exceptions.py (EdinetParseError, EdinetWarning)  ←  calculation.py
```

- 他の Wave 1 レーンへの依存: **なし**
- 他の Wave 1 レーンからの依存: **なし**（Wave 2 L1 concept_sets が利用開始）
- 既存コードへの変更: **なし**（全て新規ファイル）

### 9. 非スコープ（本 Lane でやらないこと）

- 計算リンクに基づく **Fact 値の検算**（validation/calc_check = Phase 9）
- 標準タクソノミと提出者タクソノミの計算リンクの **マージ**（リキャスト方式のため不要。必要があれば将来の統合タスクで対応）
- presentation / definition リンクベースのパース（それぞれ L1 / L3 の責務）
- `TaxonomyResolver` との統合（Wave 完了後の統合タスク）
- `_extract_concept_from_href()` は L1 (presentation) / L2 (calculation) / L3 (definition) で独立に実装される。Wave 完了後の統合タスクで `xbrl/_linkbase_utils.py` 等の共有ユーティリティに集約する（並列実装制約のため、現時点ではレーン内に閉じた実装とする）

### 10. 下流互換性の考慮

Wave 2 以降で以下の利用が想定される:

| 利用先 | 利用パターン | 互換性要件 |
|--------|------------|-----------|
| `taxonomy/concept_sets` (W2 L1) | CF の concept 導出で `children_of` を使用 | `children_of` が role_uri でフィルタ可能であること |
| `taxonomy/standard_mapping` (Phase 5) | 非標準→標準の祖先マッピングで `ancestors_of` を使用 | `ancestors_of` が根まで正しく遡行すること |
| `validation/calc_check` (Phase 9) | `CalculationTree.arcs` を走査し Fact 値と照合 | `arcs` が immutable tuple であること |

### 11. 実データでの規模感参考値（C-7.a.md, C-10.a.md より）

| 指標 | 値 |
|------|-----|
| サンプルの _cal.xml のロール数 | 8（連結/個別 × BS/PL/CI/SS/CF） |
| 総アーク数 | 185 |
| weight=+1 | 175 件 (94.6%) |
| weight=-1 | 10 件 (5.4%) |
| 最大ツリー深さ | 5（PL: ProfitLoss → ... → NetSales） |
| cna 業種 BS の loc 数 | 59 |
| cna 業種 BS の arc 数 | 57 |

---

### 12. 変更ログ（フィードバック反映）

#### 第1ラウンド（WAVE_1_LANE_2_FEEDBACK.md 初版）

| FB項番 | 判定 | 変更内容 | 修正箇所 |
|--------|------|---------|---------|
| **A-1** | 採用 | concept 名の source of truth を `xlink:href` フラグメント由来に変更。Lane 1 との不整合は統合タスクで解消する旨を注記 | §2.1 設計判断、§3.2 step b、§3.3 |
| **A-2** | 採用 | A-1 と同時解決。loc_map の value 定義を明確化（label=ルックアップキー、concept名=href由来） | §3.2 step b、§3.3 |
| **A-3** | 採用 | `frozen=True` + 内部インデックスの初期化パターンを `__post_init__` + `object.__setattr__` + `field(init=False)` で明記 | §2.3、§4 |
| **B-1** | 記録のみ | Lane 1 の `dict` 返却と Lane 2 のラッパーの差異を認識。Lane 2 のラッパー設計を維持。統合時に Lane 1 をアップグレード検討 | 変更なし |
| **B-2** | 部分採用 | `CalculationArc` に `role_uri` フィールドを追加。`children_of(role_uri=None)` の動作は維持（各アークの `role_uri` で追跡可能に） | §2.1 |
| **B-3** | 採用 | `ancestors_of` に擬似コードと visited set による循環防御ロジックを追加 | §2.3 メソッド docstring |
| **C-1** | 採用 | `standard_pl.xml` フィクスチャに `ExtraordinaryLoss(-1)` とその子（`LossOnSalesOfNoncurrentAssetsEL`, `ImpairmentLossEL`）を追加 | §6.3 |
| **C-2** | 採用 | `filer_pl.xml` の具体的な XML 構造（提出者 XSD href、プレフィックス `X99001-000_`）を追記 | §5.1（新規セクション） |
| **C-3** | 採用（低優先） | `circular.xml` フィクスチャと `test_ancestors_of_circular_reference` テストケースを追加 | §5 ファイル構成、§6.2 |
| **D-1** | 不採用 | `MappingProxyType` は過剰設計。Python 標準ライブラリも使用しない | — |
| **D-2** | 採用 | `weight` の型を `int` → `Literal[1, -1]` に変更 | §2.1 |
| **D-3** | 不採用 | `source_path` は現状の `str \| None` を維持。マージ不要（リキャスト方式）のため tuple 化の必要なし | — |
| **D-4** | 採用 | エラーハンドリング表に日本語メッセージ例を追加 | §3.4 |
| **E-1** | 採用 | Wave 2 L1 での CF concept セット導出の具体的コード例を追加 | §1.6 |
| **E-2** | 不採用 | `CalculationTree` への便利メソッド追加は YAGNI。必要になった時点で追加 | — |

#### 第2ラウンド（WAVE_1_LANE_2_FEEDBACK.md 第2版）

| FB項番 | 判定 | 変更内容 | 修正箇所 |
|--------|------|---------|---------|
| **H-1** | 採用 | `_extract_concept_from_href()` を既存 `taxonomy/__init__.py` の 2段階戦略（XSD ファイル名ベース + `_[A-Z]` 境界フォールバック）に精密化。`_XSD_PREFIX_RE` 正規表現と具体例付き擬似コードを追記 | §3.3 |
| **H-2** | 採用（案A） | `_parent_index` を `dict[..., CalculationArc]` → `dict[..., tuple[CalculationArc, ...]]` に変更。`ancestors_of` は最初の親のみ辿る旨を明記 | §2.3 メソッド docstring、§4 インデックス定義・構築ロジック |
| **H-3** | 採用（案B） | `children_of(role_uri=None)` の O(R) 走査パターンを実装擬似コードとして明記。`(role_uri, order)` ソートを指定 | §2.3 `children_of` docstring |
| **H-4** | 採用 | `CalculationArc.__repr__`（`+→`/`-→` 表記）、`CalculationTree.__repr__`（arcs数+roots）、`CalculationLinkbase.__repr__`（roles数+総arcs数）を追加 | §2.1、§2.2、§2.3 |
| **M-1** | 採用 | `test_children_of_cross_role`, `test_parent_of_cross_role`, `test_arc_has_role_uri` テストケースを追加 | §6.1 |
| **M-2** | 採用（案A） | `role_uris` プロパティの順序を「XMLパース時の出現順（dict挿入順保証）」と明記 | §2.3 `role_uris` docstring |
| **M-3** | 採用 | `ancestors_of` docstring に「開始 concept 自体は結果に含まない。結果は直接の親から根に向かう順序」を明記 | §2.3 `ancestors_of` docstring |
| **M-4** | 採用（案B） | `test_multiple_roles` のフィクスチャはテスト内 bytes リテラルで構築する旨を明記 | §6.1 |
| **M-5** | 採用 | `xlink:href` フラグメント不在時の `EdinetWarning` + スキップをエラーハンドリング表に追加 | §3.4 |
| **L-1** | 採用 | `role_uri=None` 横断検索時のソートを `(role_uri, order)` タプルソートと明記 | §2.3 `children_of` docstring |
| **L-2** | 採用 | `test_invalid_weight_skipped_with_warning`, `test_href_without_fragment` テストケースを追加 | §6.2 |

#### 第3ラウンド（WAVE_1_LANE_2_FEEDBACK.md 第3版）

| FB項番 | 判定 | 変更内容 | 修正箇所 |
|--------|------|---------|---------|
| **R-1** | 採用 | `weight` パースを `float()` 経由に変更。`xsd:decimal` 表記（`"1.0"`, `"-1.0"`）に対応。パースロジック擬似コードを追記 | §3.2 step c、§3.4 エラーハンドリング表 |
| **R-2** | 採用 | `CalculationTree.arcs` の順序仕様を「XML 文書内の出現順（パース順）」と明記。`_build_parent_index` に tuple 順序の注記を追加 | §2.2 arcs docstring、§4 構築ロジック |
| **R-3** | 採用 | `ancestors_of` docstring にルート科目→空タプルの挙動を明記。`test_ancestors_of_root_concept` テストケースを追加 | §2.3 ancestors_of docstring、§6.1 |
| **R-4** | 採用 | L1/L2/L3 間の `_extract_concept_from_href()` 重複の統合計画を §9 に追記 | §9 非スコープ |
| **R-5** | 採用 | `_XSD_PREFIX_RE` の非貪欲マッチ挙動の補足コメントを追記 | §3.3 |
| **R-6** | 採用 | `circular.xml` に自己参照（`C → C`）を追加。テストケースの内容を拡張 | §5 ファイル構成、§6.2 |
| **R-7** | 記録のみ | 実データ検証スクリプト `tools/lane2_verify.py` は計画の必須スコープ外。実装後に余裕があれば作成 | 変更なし |
| **R-8** | 採用 | `CalculationLinkbase.trees` の docstring に frozen + mutable dict の不整合について利用者向け注記を追加 | §2.3 trees docstring |

#### 第4ラウンド（WAVE_1_LANE_2_FEEDBACK.md 第4版）

| FB項番 | 判定 | 変更内容 | 修正箇所 |
|--------|------|---------|---------|
| **S-1** | 採用 | `order` 属性欠落時に `0.0` にフォールバック + `EdinetWarning` を追加。Lane 1 との一貫性を確保し、1 つの壊れた arc が他のアークのパースを妨げない設計を維持 | §3.2 step c、§3.4 エラーハンドリング表 |
| **S-2** | 採用（案A） | `roots` タプルの順序を「XML 内での初出順（arcs イテレーション順で最初に parent として出現した順）」と定義。`roots` 算出の具体的アルゴリズムを擬似コードで追記 | §2.2 roots docstring、§3.2 step e |
| **S-3** | 採用 | `calculationLink` に `calculationArc` が 0 件の場合、空の `CalculationTree(arcs=(), roots=())` を生成し `trees` に含める旨を追加 | §3.4 エラーハンドリング表 |
| **S-4** | 採用 | `standard_pl.xml` / `standard_bs.xml` フィクスチャの全ノードに order 値を明記。テスト期待値とフィクスチャの整合性を保証 | §6.3 |

#### 第5ラウンド（WAVE_1_LANE_2_FEEDBACK.md 第5版）

| FB項番 | 判定 | 変更内容 | 修正箇所 |
|--------|------|---------|---------|
| **T-1** | 採用 | `order` / `weight` は XLink 名前空間ではなく XBRL 2.1 の直接属性。擬似コードの `f"{{{NS_XLINK}}}order"` → `"order"`、`weight` も同様に修正。修正しないと全アークが `order=0.0` になり `children_of` のソートが壊れるサイレントバグを引き起こす | §3.2 step c（order / weight 取得コード） |
| **T-2** | 採用 | `calculationArc` の `arcrole` が `summation-item` であることを検証し、それ以外は `EdinetWarning` + スキップ。既存のエラーハンドリング（weight 検証、loc 参照不在等）と同粒度の防御的コーディング | §3.2 step c（arcrole 検証追加）、§3.4 エラーハンドリング表 |
| **T-3** | 採用（案A） | `_XSD_PREFIX_RE` の正規表現を既存 `taxonomy/__init__.py` と同一の greedy `.+` に統一。統合タスク時の差分を最小化する。EDINET のファイル名体系では greedy/non-greedy で結果は等価 | §3.3（正規表現 + コメント） |
| **T-4** | 記録のみ | `test_multiple_roles` の bytes リテラル規模感（50-80 行程度）。モジュールレベル定数として定義する等の工夫は実装エージェントの判断に委ねる | 変更なし |

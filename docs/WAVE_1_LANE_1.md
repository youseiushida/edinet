# 並列実装の安全ルール（必ず遵守）

あなたは Wave 1 / Lane 1 を担当するエージェントです。
担当機能: presentation (Presentation Linkbase パーサー)

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
   - `src/edinet/xbrl/linkbase/presentation.py` (新規)
   - `tests/test_xbrl/test_presentation.py` (新規)
   - `tests/fixtures/linkbase_presentation/` (新規ディレクトリ)
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
     例: `tests/fixtures/linkbase_presentation/`

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.linkbase.presentation import parse_presentation_tree` （OK）
   - 例: `from edinet.xbrl import parse_presentation_tree` （NG）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_presentation.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 0 で事前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl._namespaces` (NS_* 定数)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 1: Presentation Linkbase パーサー (`pres_tree`)

## 0. 位置づけ

Wave 1 Lane 1 は、XBRL Presentation Linkbase（`_pre.xml`）をパースし、科目の階層構造（親子関係・表示順・合計行識別）を木構造で提供するモジュールを新規実装する日。

**FUTUREPLAN.tmp.md での位置**: Phase 2-1 (pres_tree)。全 Wave の中で**最大のレバレッジポイント**。後続の `taxonomy/concept_sets`（Wave 2 L1）が本モジュールに依存し、手動 JSON（`pl_jgaap.json` 等）の全廃と 23 業種自動カバーの基盤となる。

**依存先**: `_namespaces.py` の NS 定数のみ（`NS_LINK`, `NS_XLINK`）。他の Wave 1 レーンとの依存なし。

**利用者** (Wave 2 以降):
- `taxonomy/concept_sets` — role URI ごとの concept セットを自動導出
- `display/statements` — 表示順・インデント・合計行のレンダリング
- `standards/normalize` — 会計基準横断の科目構造

---

## 1. 背景知識（QA サマリー）

### 1.1 Presentation Linkbase とは（C-6, C-10, I-2）

`_pre.xml` は XBRL の Presentation Linkbase であり、財務諸表の**科目の階層構造・表示順序**を定義する。

- **arc**: `link:presentationArc` のみ。`xlink:arcrole` は `http://www.xbrl.org/2003/arcrole/parent-child` 固定
- **属性**: `order`（表示順、0以上の小数可、必須）、`preferredLabel`（ラベルロール切替、合計行識別に使用）
- **loc**: `link:loc` の `xlink:label` は concept 名そのもの（例: `CashAndDeposits`）。`xlink:href` は相対パス + `#prefix_ConceptName`
- **prohibited/priority**: 表示リンクでは `use="prohibited"` は**禁止**。`priority` による arc 解決は不要（C-6.6, C-11.4）

### 1.2 ツリー構造（I-2, C-6.4）

```
{諸表名}Heading                       ← ルート（abstract）
├── {諸表名}Table                     ← Dimension ハイパーキューブ
│   └── ConsolidatedOrNonConsolidatedAxis
│       └── ConsolidatedMember
└── {諸表名}LineItems                 ← 科目ツリーの起点
    ├── AssetsAbstract                ← 見出し（abstract）
    │   ├── CurrentAssetsAbstract
    │   │   ├── CashAndDeposits       ← 具体的科目
    │   │   ├── Inventories
    │   │   └── CurrentAssets         ← 合計行 (preferredLabel=totalLabel)
    │   └── NoncurrentAssetsAbstract
    │       └── ...
    └── LiabilitiesAbstract
        └── ...
```

**dimension 関連中間ノード**（`Table`, `Axis`, `Member`, `LineItems`）は表示ツリーに含まれるが、財務諸表のインデント計算からはスキップすべき（I-2.3）。

### 1.3 Role URI と財務諸表の対応（I-1）

1 つの `_pre.xml` ファイル内に複数の `link:presentationLink` 要素が存在し、各々が `xlink:role` 属性で role URI を持つ。

主要な role URI（提出者用、`_std_` なし）:

| 諸表 | role ID 例 | ELR番号 |
|------|-----------|---------|
| BS 連結 | `rol_ConsolidatedBalanceSheet` | 310010 |
| BS 個別 | `rol_BalanceSheet` | 310040 |
| PL 連結 | `rol_ConsolidatedStatementOfIncome` | 321010 |
| PL 個別 | `rol_StatementOfIncome` | 321040 |
| CF 連結(間接法) | `rol_ConsolidatedStatementOfCashFlows-indirect` | 342010 |
| CF 連結(直接法) | `rol_ConsolidatedStatementOfCashFlows-direct` | 341010 |
| SS 連結 | `rol_ConsolidatedStatementOfChangesInEquity` | 330010 |
| CI 連結 | `rol_ConsolidatedStatementOfComprehensiveIncome` | 322010 |

半期・四半期・第一種中間のバリエーションあり（各々 `SemiAnnual`, `Quarterly`, `Type1SemiAnnual` プレフィックス付き）。

EDINET タクソノミ用（`rol_std_*`）と提出者用（`rol_*`、`_std_` なし）は別の role URI。パーサーは**両方**を処理できる必要がある。

### 1.4 提出者の _pre.xml とマージ（I-3, C-6.5, C-11）

- 表示リンクは「再構成（リキャスト）」方式。提出者は EDINET タクソノミの表示リンクを直接修正せず、**ゼロから独立したファイルを新規作成**する
- 提出者の `_pre.xml` **のみをパースすれば**当該提出書類の表示構造が完全に取得できる
- EDINET タクソノミの `_pre.xml` とのマージは**不要**
- ただし Wave 2 の `taxonomy/concept_sets` では**標準タクソノミの `_pre.xml`** もパースする必要がある（concept セットの自動導出のため）

### 1.5 バリアントファイルの分割（Z-2）

標準タクソノミ側では、PL が複数バリアントファイルに分割されている:
- `_pre_pl.xml` — 営業利益以降
- `_pre_pl-2-PL-01-Sales-1-Net.xml` — 売上高区分（Net方式）
- `_pre_pl-2-PL-04-SGA-1-ByAccount.xml` — 販管費区分（勘定科目別）
- etc.

完全な PL = メインファイル + 選択バリアントのマージ。**同一 role URI を共有**しているため、role URI 単位でのマージで統合可能。

一般事業会社(cns)の CF には `_pre_cf` が存在しない（Z-2.3）。

---

## 2. ゴール

### 2.1 機能要件

1. `_pre.xml` ファイル（bytes）をパースし、role URI ごとの `PresentationTree` を構築する
2. 複数の `_pre.xml` bytes を受け取り、同一 role URI のツリーをマージできる（バリアントファイル対応）
3. ツリーの各ノードに以下の情報を保持する:
   - concept 名（`xlink:href` フラグメントから正規化。`_2` サフィックス問題を回避）【F-1 反映】
   - XSD href（相対パス + fragment）
   - order 値
   - preferredLabel（完全 URI。設定されている場合）【F-3 反映】
   - 子ノードのリスト（order 順にソート済み）
   - ツリー上の深さ（depth、ルートからの絶対値）
   - `is_abstract` フラグ（`Abstract` / `Heading` 末尾）
   - `is_dimension_node` フラグ（`Table` / `Axis` / `Member` / `LineItems` / `Domain` 末尾）【F-2 反映】
4. role URI → `PresentationTree` の辞書を返す
5. `LineItems` 以下の科目サブツリーのみを取得するユーティリティを提供する（`is_dimension_node` フラグで探索）
6. ルートノード（`Heading`）の発見: parent として参照されるが child としては参照されないノード
7. パーサーは `_pre.xml` 内の**全 role URI** を無差別にパースし辞書に含める。財務諸表のフィルタリングは Wave 2 以降の責務であり、本パーサーは role URI の意味解釈を行わない【F-7 反映】
8. ツリー構築時に循環参照を検出し `EdinetParseError` を送出する（防御的プログラミング）【F-4 反映】

### 2.2 パフォーマンス要件

- 標準タクソノミ全体（641 `_pre.xml` ファイル）を処理する場合でも合理的な速度（目安: 全ファイル 10 秒以内）
- 提出者の `_pre.xml`（1ファイル、通常 64 role × 数千行）は 100ms 以内

### 2.3 非機能要件

- 入力は `bytes` のみ（ファイルパスは受け取らない。I/O はユーザー側の責務）
- `lxml` ベース（既存の `taxonomy/__init__.py` と同じ）
- 日本語 docstring（Google Style）
- 日本語エラーメッセージ
- frozen dataclass でイミュータブルなデータ構造

---

## 3. 設計

### 3.1 公開 API

```python
# src/edinet/xbrl/linkbase/presentation.py

_DIMENSION_SUFFIXES = ("Table", "Axis", "Member", "LineItems", "Domain")  # 【F-2】

# XBRL 標準ラベルロール URI 定数【I-4 反映】
ROLE_LABEL = "http://www.xbrl.org/2003/role/label"
ROLE_TOTAL_LABEL = "http://www.xbrl.org/2003/role/totalLabel"
ROLE_PERIOD_START_LABEL = "http://www.xbrl.org/2003/role/periodStartLabel"
ROLE_PERIOD_END_LABEL = "http://www.xbrl.org/2003/role/periodEndLabel"
ROLE_NEGATED_LABEL = "http://www.xbrl.org/2003/role/negatedLabel"
ROLE_VERBOSE_LABEL = "http://www.xbrl.org/2003/role/verboseLabel"


@dataclass(frozen=True, slots=True)
class PresentationNode:
    """Presentation ツリーの 1 ノード。

    Attributes:
        concept: 正規化済み concept 名（例: ``"CashAndDeposits"``）。
            ``xlink:href`` のフラグメント（``#jppfs_cor_CashAndDeposits``）から
            ``prefix_`` を除去して取得する。``xlink:label`` の ``_2`` サフィックス
            問題を回避する。【F-1 反映】
        href: XSD への相対参照（例: ``"../../jppfs_cor_2025-11-01.xsd#jppfs_cor_CashAndDeposits"``）。
        order: 兄弟ノード間の表示順序。
        preferred_label: ラベルロール URI（完全 URI）。合計行なら
            ``"http://www.xbrl.org/2003/role/totalLabel"``。
            ``None`` は標準ラベル（``http://www.xbrl.org/2003/role/label``）。【F-3 反映】
        depth: ルートからの深さ（0-based、絶対値）。
        children: 子ノードのタプル（order 順ソート済み）。
        is_abstract: concept 名が ``Abstract`` または ``Heading`` で終わる場合 ``True``。
        is_dimension_node: concept 名が ``Table``, ``Axis``, ``Member``,
            ``LineItems``, ``Domain`` のいずれかで終わる場合 ``True``。【F-2 反映】
    """
    concept: str
    href: str
    order: float
    preferred_label: str | None
    depth: int
    children: tuple["PresentationNode", ...]
    is_abstract: bool
    is_dimension_node: bool  # 【F-2】

    @property
    def is_total(self) -> bool:
        """合計行（preferredLabel が totalLabel）であるか。【F-3 反映】"""
        return self.preferred_label == ROLE_TOTAL_LABEL  # 【I-4 反映: 定数使用】

    def __repr__(self) -> str:
        """REPL 向けの簡潔な表現。【F-10 反映】"""
        return (
            f"PresentationNode(concept={self.concept!r}, "
            f"depth={self.depth}, children={len(self.children)})"
        )


@dataclass(frozen=True, slots=True)
class PresentationTree:
    """1 つの role URI に対応する Presentation ツリー。

    Attributes:
        role_uri: 拡張リンクロールの完全 URI。
        roots: ルートノードのタプル（通常 1 つだが複数の可能性あり）。
        node_count: ツリー内の総ノード数。
    """
    role_uri: str
    roots: tuple[PresentationNode, ...]
    node_count: int

    def line_items_roots(self) -> tuple[PresentationNode, ...]:
        """``*LineItems`` ノードを起点とするサブツリーのルートを返す。

        ルートノードの全子孫を DFS で走査し、concept 名が ``"LineItems"`` で
        終わるノードを収集する。見つからない場合はルートノード自体を返す。
        【G-1 反映: DFS + concept 名末尾マッチに明確化】

        Note:
            ``is_dimension_node`` フラグは探索条件ではなく、利用者が表示時に
            dimension ノードをスキップするためのフィルタ用。探索は単純に
            concept 名末尾マッチで行う。

        Returns:
            ``*LineItems`` ノードのタプル。見つからない場合はルートを返す。
        """

    def flatten(
        self,
        *,
        skip_abstract: bool = False,
        skip_dimension: bool = False,
    ) -> tuple[PresentationNode, ...]:
        """ツリーを深さ優先で平坦化する。

        Args:
            skip_abstract: ``True`` の場合、``is_abstract=True`` のノードを除外する。
            skip_dimension: ``True`` の場合、``is_dimension_node=True`` のノードを除外する。【H-3 反映】

        Returns:
            深さ優先順の全ノードのタプル。

        Note:
            同一 concept が複数の位置に出現する場合（例: dimension ノードと
            科目ツリーの両方に同じ concept が参照される場合）、返り値には
            同一 concept 名の異なるノードが含まれる。concept のユニーク
            集合が必要な場合は ``{n.concept for n in tree.flatten()}`` を使用する。
            【G-5 反映】
        """

    def __repr__(self) -> str:
        """REPL 向けの簡潔な表現。【F-10 反映】"""
        return (
            f"PresentationTree(role_uri={self.role_uri!r}, "
            f"roots={len(self.roots)}, nodes={self.node_count})"
        )


def parse_presentation_linkbase(
    xml_bytes: bytes,
    *,
    source_path: str | None = None,
) -> dict[str, PresentationTree]:
    """Presentation Linkbase の bytes をパースする。

    全 role URI を無差別にパースし辞書に含める。
    財務諸表のフィルタリングは利用側の責務。【F-7 反映】

    Args:
        xml_bytes: ``_pre.xml`` ファイルの bytes。
        source_path: エラーメッセージに含めるソースパス。

    Returns:
        ``{role_uri: PresentationTree}`` の辞書。

    Raises:
        EdinetParseError: XML パースに失敗した場合、または循環参照を検出した場合。
    """


def merge_presentation_trees(
    *tree_dicts: dict[str, PresentationTree],
) -> dict[str, PresentationTree]:
    """複数の Presentation ツリー辞書をマージする。

    同一 role URI のツリーは**再帰的に**子ノードを統合する。
    PL のバリアントファイル統合等に使用する。【F-6 反映: 再帰マージ】

    マージアルゴリズム:
    1. 同一 role URI の全ツリーを収集
    2. ルートが同一 concept → 再帰的に子をマージ
    3. 再帰マージ: 同一親の子を concept 名でグループ化
       - 片方にしかない → そのまま追加
       - 両方にある → その子を再帰的にマージ
    3b. 両方にある concept の属性解決: 全属性「先着採用」
        （``*tree_dicts`` の引数順が優先順）。子ノードのみ再帰マージ。
        親ノードの ``order``, ``preferred_label``, ``href``,
        ``is_abstract``, ``is_dimension_node`` は先着の値をそのまま使用する。【H-2 反映】
    4. 最終的に各レベルで order 順でソート（Python ``sorted()`` による安定ソート。
       同一 order の兄弟ノードは引数順 = 文書出現順を保持する）【H-5 反映】
    5. マージ後のルートから ``depth`` を 0 から再帰的に再計算して
       全ノードを再構築する【H-1 反映】
    6. ``_count_nodes(roots)`` で全ノード数を再カウントし
       ``PresentationTree`` を構築【G-4 反映】

    エッジケース【G-6 反映、I-6 反映】:
    - 引数なし（``merge_presentation_trees()``）→ 空辞書 ``{}`` を返す
    - 全て空辞書 → 空辞書を返す
    - 1 つの辞書のみ → 浅いコピー（``dict(tree_dict)``）を返す【I-6 反映】

    Note:
        マージは concept 名（local name）でグループ化するため、
        異なる namespace の同名 concept は同一として扱われる。
        PL バリアントファイル（同一タクソノミ内）のマージでは問題ないが、
        異なるタクソノミ間のマージには使用しないこと。【H-6 反映】

    Args:
        tree_dicts: マージ対象のツリー辞書群。引数の順序に意味がある
            （先に渡した辞書の属性値が優先される）。【H-2 反映】

    Returns:
        マージ済みの ``{role_uri: PresentationTree}`` 辞書。
    """
```

### 3.2 内部実装の方針

#### Step 1: XML パース（`_parse_links`）

```python
def _parse_links(root: etree._Element) -> dict[str, list[_RawArc]]:
    """XML ルートから role URI ごとの arc リストを抽出する。"""
```

1. `link:presentationLink` 要素を列挙
2. 各 `presentationLink` の `xlink:role` 属性で role URI を取得
3. 内部の `link:loc` をスキャン → `{xlink:label: href}` のマップ構築
4. 内部の `link:presentationArc` をスキャン → `_RawArc(from_label, to_label, order, preferred_label)` のリスト構築
5. role URI → `_RawArc` リストの辞書を返す

**EDINET 固有の簡略化**:
- `use="prohibited"` は表示リンクで使用不可（C-6.6）→ arc override 処理は不要
- `priority` 属性の解決も不要
- arcrole は `parent-child` の 1 種のみ → arcrole のフィルタ不要

**属性欠落時のフォールバック**【G-3 反映】:

`EdinetParseError` は XML 自体が壊れている場合（malformed XML）に限定する。属性欠落は `warnings.warn` + スキップで処理し、1 つの壊れた要素が他の正常なノードのパースを妨げないようにする。利用者は `warnings.filterwarnings` で制御可能。既存の `taxonomy/__init__.py` と同じパターン。

全ての `warnings.warn` は `EdinetWarning`（`edinet.exceptions` で定義、`UserWarning` サブクラス）をカテゴリとして使用する。`stacklevel=2` で呼び出し元を指す。【H-4 反映】

| 属性 | 欠落時の挙動 | パース失敗時の挙動 |
|------|-------------|-------------------|
| `order` on arc | `0.0` にフォールバック + `warnings.warn` | `0.0` にフォールバック + `warnings.warn`【I-1 反映】 |
| `xlink:href` on loc | その loc を無視 + `warnings.warn` | — |
| `xlink:from` / `xlink:to` on arc | その arc を無視 + `warnings.warn` | — |
| `xlink:role` on presentationLink | その presentationLink を丸ごとスキップ + `warnings.warn` | — |

#### Step 2: ツリー構築（`_build_tree`）

1. arc リストから `{parent_label: [(child_label, order, preferred_label), ...]}` の隣接リストを構築
2. ルートノードの発見: 「from に出現するが to には出現しない label」がルート
3. ルートから深さ優先で `PresentationNode` を再帰構築
4. **循環参照の検出**: 再帰構築時に visited set を保持し、循環を検出したら `EdinetParseError` を送出【F-4 反映】
5. 各階層の子ノードは `order` 順にソート（`sorted()` 安定ソート。同一 order のノードは XML 文書内の出現順を保持）【H-5 反映】
6. `is_abstract` は concept 名の末尾が `Abstract` または `Heading` で判定
7. `is_dimension_node` は concept 名の末尾が `_DIMENSION_SUFFIXES` のいずれかで判定【F-2 反映】

#### Step 3: concept 名と href の解決【F-1 反映: 全面改訂】

- loc の `xlink:label` → **ツリー構築時の内部キー**（`_2` サフィックスを含むためグラフ構築にのみ使用）
- loc の `xlink:href` → XSD 参照 + **正規 concept 名の抽出元**

`xlink:label` は概ね concept 名だが、同一 `extendedLink` 内で同一 concept が複数回参照される場合は `_2` サフィックスが付く（例: `ConsolidatedMember_2`）。`_2` をそのまま concept 名にすると Wave 2 の `concept_sets` で別 concept と誤認される。

**正規化ロジック**:
1. `xlink:href` のフラグメント（`#jppfs_cor_CashAndDeposits`）を取得
2. フラグメントから `#` を除去
3. **後方スキャンで最後の `_[A-Z]` 境界を探す** → prefix と concept 名を分離
   - 例: `jppfs_cor_CashAndDeposits` → 末尾から走査し `_C` の位置で分割 → `CashAndDeposits`
   - 例: `jpcrp030000-asr_E02144-000_CustomExpense` → `_C` の位置で分割 → `CustomExpense`
4. **`_[A-Z]` 境界が見つからない場合** → フラグメント全体を concept 名とする（フォールバック）【G-2 反映】
   - 例: `#ConsolidatedBalanceSheetHeading`（prefix なしの bare concept 名）→ `ConsolidatedBalanceSheetHeading`
   - 例: 全小文字フラグメント（非標準だが防御的に考慮）→ フラグメント全体を使用
5. これを `PresentationNode.concept` として使用
6. `xlink:label` はツリー構築時の隣接リストのキーとしてのみ使用（公開しない）

**注意**: prefix は `jppfs_cor` のようにアンダースコアを含むため、「最初の `_` で分割」では**誤分割**する。EDINET の命名規則（§5-2-1-1 LC3 method）により concept 名は必ず PascalCase（大文字始まり）であるため、最後の `_[A-Z]` 境界が正しい分割点になる。既存の `taxonomy/__init__.py` の `_split_fragment_prefix_local()` と同じアルゴリズム。ただし `taxonomy` モジュールへの依存は避け、同等のロジックを本モジュール内に軽量に再実装する。

**根拠**: C-10.a.md で `xlink:href` フラグメントが常に `{prefix}_{ConceptName}` 形式であることを確認済み。既存テスト（`test_taxonomy.py`）でハイフン含む prefix の分割が検証済み。

#### Step 4: マージ（`merge_presentation_trees`）【F-6 反映: 再帰マージに変更】

同一 role URI のツリーが複数の `_pre.xml` に分散する場合（PL バリアント等）、**再帰的に**子ノードを統合し order 順に再ソートする。

PL バリアントは Heading → LineItems の共通構造を持つため、ルートの子だけでなく LineItems 以下の孫ノードまでマージが必要。

再帰マージアルゴリズム:
1. 同一 role URI の全 `PresentationTree` を収集
2. 各ツリーのルートが同一 concept なら、再帰的に子をマージ
3. 再帰マージの各レベル:
   - 同一親の子ノードリストを concept 名でグループ化
   - concept が片方にしかない → そのまま追加
   - concept が両方にある → 親ノードの属性（`order`, `preferred_label`, `href`, `is_abstract`, `is_dimension_node`）は先着採用。子のみ再帰マージ【H-2 反映】
4. ルートが異なる場合は別々のルートとして保持
5. 最終的に各レベルで order 順にソート（`sorted()` 安定ソート。同一 order の兄弟は引数順 = 文書出現順を保持）【H-5 反映】
6. マージ後のルートから `depth` を 0 から再帰的に再計算して全ノードを再構築する【H-1 反映】
7. `_count_nodes(roots)` で再帰的に全ノードをカウントし、新しい `PresentationTree` を構築【G-4 反映】

エッジケースの処理【G-6 反映、I-6 反映】:
- 引数なし → 空辞書 `{}` を返す
- 全て空辞書 → 空辞書を返す
- 1 つの辞書のみ → 浅いコピー（`dict(tree_dict)`）を返す【I-6 反映】。`PresentationTree` は frozen なので浅いコピーで十分安全。利用者が返り値の dict を変更しても入力に影響しないことを保証する

### 3.3 データ型（内部）

```python
@dataclass(frozen=True, slots=True)
class _RawArc:
    """パース済み arc の中間表現。"""
    from_label: str   # xlink:label（内部キー、_2 サフィックスを含みうる）
    to_label: str     # xlink:label（内部キー）
    order: float
    preferred_label: str | None  # 完全 URI

@dataclass(frozen=True, slots=True)
class _LocInfo:
    """loc 要素の情報。"""
    label: str    # xlink:label（内部キー、ツリー構築用）
    href: str     # xlink:href（concept 名の抽出元）
    concept: str  # href フラグメントから正規化した concept 名【F-1 反映】
```

---

## 4. テスト計画

### 4.1 テストフィクスチャ

`tests/fixtures/linkbase_presentation/` ディレクトリに以下を作成:

| ファイル | 内容 | 用途 |
|---------|------|------|
| `simple_bs.xml` | 小さな BS プレゼンテーション（10 nodes 程度） | 基本パースのテスト |
| `multi_role.xml` | BS + PL の 2 role を含む | 複数 role URI のパース |
| `variant_pl_main.xml` | PL メインファイル（営業利益以降） | バリアントマージのテスト |
| `variant_pl_sales.xml` | PL Sales バリアント（売上高区分） | バリアントマージのテスト |
| `empty.xml` | 空の linkbase（presentationLink なし） | エッジケース |
| `missing_attrs.xml` | 一部の属性が欠落した XML（order 欠落、href 欠落など） | 属性欠落フォールバックのテスト【G-3】 |
| `malformed.xml` | 不正な XML | エラーハンドリング |

**フィクスチャ設計方針**: C-10.a.md の実タクソノミ XML 例（Presentation セクション）をベースに、namespace 宣言・roleRef・preferredLabel の実際の完全 URI 値を含めた現実的な XML を作成する。ノード数は最小限に抑えつつ、dimension 中間ノード（`Table`, `Axis`, `Member`, `LineItems`）を含めた実際の階層を維持する。【F-9 反映】

### 4.2 テストケース

```python
class TestParsePresentationLinkbase:
    """parse_presentation_linkbase() のテスト。"""

    def test_basic_tree_structure(self):
        """BS の基本ツリー構造がパースできること。"""
        # ルートが Heading、子に Table と LineItems がある

    def test_node_attributes(self):
        """各ノードの属性（concept, order, preferred_label, depth）が正しいこと。"""

    def test_order_sorting(self):
        """兄弟ノードが order 順にソートされること。"""

    def test_total_label_identification(self):
        """preferredLabel=totalLabel の合計行が識別できること。"""

    def test_abstract_identification(self):
        """Abstract/Heading 末尾の要素が is_abstract=True になること。"""

    def test_multiple_roles(self):
        """1 ファイル内の複数 role URI が別々の PresentationTree になること。"""

    def test_empty_linkbase(self):
        """presentationLink を含まないファイルが空辞書を返すこと。"""

    def test_malformed_xml_raises(self):
        """不正 XML で EdinetParseError が発生すること。"""

    def test_node_count(self):
        """PresentationTree.node_count がツリー内の全ノード数と一致すること。"""

    def test_concept_from_href_not_label(self):
        """concept 名が xlink:href フラグメントから正規化されること（_2 サフィックス除去）。【F-1 テスト】"""

    def test_preferred_label_full_uri(self):
        """preferredLabel が完全 URI で格納されること。【F-3 テスト】"""

    def test_is_total_property(self):
        """is_total が totalLabel 末尾の preferredLabel で True を返すこと。【F-3 テスト】"""

    def test_dimension_node_identification(self):
        """Table/Axis/Member/LineItems ノードが is_dimension_node=True になること。【F-2 テスト】"""

    def test_cyclic_arc_raises(self):
        """A → B → C → A のような循環参照で EdinetParseError を送出すること。【F-4 テスト】"""

    def test_concept_from_bare_fragment(self):
        """prefix なしの bare concept 名（#ConceptName）が正しく取得されること。【G-2 テスト】"""

    def test_missing_order_warns(self):
        """arc に order 属性がない場合 warnings.warn が発生し 0.0 にフォールバックすること。【G-3 テスト】"""

    def test_missing_href_skips_loc(self):
        """loc に xlink:href がない場合、その loc が無視されて残りが正常にパースされること。【G-3 テスト】"""

    def test_concept_from_standard_prefix(self):
        """標準 prefix（jppfs_cor）から concept 名が正しく分離されること。【I-2 テスト】"""
        # href="#jppfs_cor_CashAndDeposits" → concept="CashAndDeposits"

    def test_concept_from_hyphenated_prefix(self):
        """ハイフン含み prefix（jpcrp030000-asr_E02144-000）から concept 名が正しく分離されること。【I-2 テスト】"""
        # href="#jpcrp030000-asr_E02144-000_CustomExpense" → concept="CustomExpense"

    def test_concept_fallback_no_uppercase_boundary(self):
        """_[A-Z] 境界が見つからない fragment でフォールバック（G-2）が動作すること。【I-2 テスト】"""
        # href="#alllowercasefragment" → concept="alllowercasefragment"（フラグメント全体）

    def test_order_parse_failure_warns(self):
        """arc の order 属性が非数値の場合 warnings.warn が発生し 0.0 にフォールバックすること。【I-1 テスト】"""


class TestPresentationTree:
    """PresentationTree のメソッドテスト。"""

    def test_line_items_roots(self):
        """line_items_roots() が LineItems ノードを返すこと。"""

    def test_line_items_roots_no_lineitems(self):
        """LineItems がない場合にルートが返ること。"""

    def test_flatten_all(self):
        """flatten() が深さ優先順の全ノードを返すこと。"""

    def test_flatten_skip_abstract(self):
        """flatten(skip_abstract=True) で abstract ノードが除外されること。"""

    def test_flatten_skip_dimension(self):
        """flatten(skip_dimension=True) で dimension ノードが除外されること。【H-3 テスト】"""


class TestMergePresentationTrees:
    """merge_presentation_trees() のテスト。"""

    def test_merge_same_role(self):
        """同一 role URI のツリーがマージされること。"""

    def test_merge_different_roles(self):
        """異なる role URI はそれぞれ独立に保持されること。"""

    def test_merge_preserves_order(self):
        """マージ後も order 順が維持されること。"""

    def test_merge_single_dict(self):
        """1 つの辞書のみ渡した場合はそのまま返ること。"""

    def test_merge_deep_overlap(self):
        """ルートもLineItemsも同一の場合、LineItems以下の子が再帰的にマージされること。【F-6 テスト】"""

    def test_merge_preserves_depth(self):
        """マージ後のノードの depth がルートからの正しい絶対値であること。【H-1 テスト】"""

    def test_merge_attribute_precedence(self):
        """同一 concept のマージで先着辞書の preferred_label が優先されること。【H-2 テスト】"""

    def test_merge_no_args(self):
        """引数なしの場合に空辞書を返すこと。【G-6 テスト】"""

    def test_merge_empty_dicts(self):
        """全て空辞書の場合に空辞書を返すこと。【G-6 テスト】"""
```

### 4.3 テスト方針

- **Detroit 派**: モック不使用。実際の XML bytes をパースしてアサート
- **リファクタリング耐性**: 内部関数（`_parse_links`, `_build_tree`）はテストしない。公開 API のみテスト
- **フィクスチャ自己完結**: 外部ファイル（タクソノミ等）への依存なし

### 4.4 推奨: 実データスモークテスト【I-5 反映】

§4.3 の必須テスト（フィクスチャ自己完結）とは別カテゴリとして、実タクソノミに対するスモークテストを**推奨**する。計画の必須テストには含めないが、実装エージェントが余力があれば追加すること。

```python
@pytest.mark.skipif(
    not os.environ.get("EDINET_TAXONOMY_ROOT"),
    reason="EDINET_TAXONOMY_ROOT が設定されていません"
)
class TestRealTaxonomy:
    """実タクソノミに対するスモークテスト（CI では skip）。"""

    def test_parse_jppfs_pre(self):
        """jppfs の _pre.xml が例外なくパースできること。"""

    def test_parse_and_merge_pl_variants(self):
        """PL バリアントファイルのマージが動作すること。"""
```

handcrafted XML では再現しにくい特性（巨大な namespace 宣言群、BOM 付き UTF-8、深いネスト、数百ノード規模）の早期検出に有用。

---

## 5. 実装手順

### Step 1: フィクスチャ作成

1. `tests/fixtures/linkbase_presentation/` ディレクトリを作成
2. 実タクソノミの XML 構造（C-10.6 の例）を参考に、最小限のテスト XML を手書きで作成
3. BS 用（`simple_bs.xml`）: Heading → Table/LineItems → 3-4 科目 + 合計行
4. PL 用バリアント（`variant_pl_main.xml` + `variant_pl_sales.xml`）: role URI を共有

### Step 2: データモデル定義

1. `PresentationNode`, `PresentationTree` の frozen dataclass を定義
2. 内部型 `_RawArc`, `_LocInfo` を定義
3. `PresentationTree.line_items_roots()`, `flatten()` を実装

### Step 3: パーサー実装

1. `parse_presentation_linkbase()` を実装
2. 既存の `taxonomy/__init__.py` の `_parse_lab_xml_tree()` のパターンを参考に、`link:presentationLink` → `link:loc` + `link:presentationArc` の走査ロジックを実装
3. 名前空間定数は `_namespaces.py` の `NS_LINK`, `NS_XLINK` を import

### Step 4: マージ実装

1. `merge_presentation_trees()` を実装
2. 同一 role URI のツリーを子ノード結合 + order 再ソートで統合

### Step 5: テスト実行・修正

1. `uv run pytest tests/test_xbrl/test_presentation.py -v` で全テスト PASS を確認
2. `uv run pytest` で既存テスト含む全テスト PASS を確認
3. `uv run ruff check src/edinet/xbrl/linkbase/presentation.py tests/test_xbrl/test_presentation.py` でリント PASS を確認

---

## 6. 注意点・設計判断

### 6.1 href の扱いと concept 名の正規化【F-1 反映: 全面改訂】

`xlink:href` から prefix + local_name を抽出するロジックは既存の `taxonomy/__init__.py` に `_extract_prefix_and_local()` がある。しかし本モジュールは `taxonomy` に依存してはならない（他レーンのファイル）。

**方針**: `href` はそのまま文字列として保持する。加えて、`href` のフラグメント部分（`#` 以降）から `prefix_` を除去して正規 concept 名を抽出する。この抽出は軽量な文字列操作のみで `taxonomy` への依存は発生しない。

**技術的負債マーカー**【I-3 反映】: Wave 1 完了後の統合タスクで、`taxonomy/__init__.py` の `_split_fragment_prefix_local` と本モジュールの正規化ロジックを共通ユーティリティ（例: `edinet.xbrl._utils.split_fragment`）に抽出し、両モジュールからインポートする形に統一すること。同一ロジックの 2 箇所存在は DRY 違反であり、将来のバグ修正やエッジケース追加が片方にしか反映されないリスクがある。

**旧方針（破棄）**: ~~concept 名は `xlink:label` から直接取得する~~
**新方針**: concept 名は `xlink:href` フラグメントから正規化する。`xlink:label` はツリー構築時の内部キーとしてのみ使用する。

**根拠**: C-10.a.md で確認した通り、`xlink:label` には `_2` サフィックスが付くケースがあり（同一 `extendedLink` 内の同一 concept への複数参照）、これをそのまま concept 名にすると Wave 2 の `concept_sets` が別 concept と誤認する。`xlink:href` のフラグメントは常に `{prefix}_{ConceptName}` 形式で、真の concept 名を含む。

### 6.2 同一 concept の複数 loc（`_2` サフィックス）【F-1 連動で改訂】

同一 `extendedLink` 内で同一 concept が複数回参照される場合、`xlink:label` に `_2`, `_3` 等のサフィックスが付く。

**方針**: `xlink:label` は内部キー（隣接リスト構築用）としてのみ使用する。公開 API の `PresentationNode.concept` には `xlink:href` から抽出した正規化済み concept 名を格納する。これにより:
- Wave 2 の `concept_sets` が concept のユニーク集合を正しく導出できる
- Definition Linkbase（Lane 3）との concept 名突き合わせが正しく動作する
- `flatten()` の結果から concept のユニーク集合を取得する利用者が混乱しない

### 6.3 order の型【I-1 反映: G-3 原則に統一】

EDINET の order は `"1.0"`, `"2.0"` 等の文字列で格納される。

**方針**: `float` にパースする。整数値の場合も `float` で統一する。パース失敗時（非数値文字列等）は `0.0` にフォールバックし `warnings.warn("order 属性のパースに失敗しました: {value!r}, 0.0 にフォールバックします", EdinetWarning, stacklevel=2)` を発行する。

**根拠**: G-3 原則に従い、`EdinetParseError` は XML 自体が壊れている場合（malformed XML）に限定する。`order="abc"` は XML としては valid であり、属性値の異常は `warnings.warn` + フォールバックで処理する。1 つの arc の order 値が壊れているだけで全ファイルのパースが中断されるべきではない。

### 6.4 roleRef 要素

`link:roleRef` 要素は role URI → XSD 定義箇所のマッピングを提供するが、Presentation ツリーの構築自体には不要。

**方針**: `roleRef` はパースしない。`presentationLink` の `xlink:role` 属性のみを使用する。

### 6.5 roleType の definition テキスト

role URI から「連結貸借対照表」等の日本語名を取得するには `roleType` の `definition` 属性が必要だが、これは `*_rt_*.xsd` に定義されている。

**方針**: 本モジュールのスコープ外。role URI の意味解釈は Wave 2 以降の責務。本モジュールは role URI の文字列をそのまま返す。

### 6.6 depth の絶対値と相対値【F-8 反映: 設計判断の記載】

`PresentationNode.depth` はルートからの絶対深さ（0-based）を保持する。Wave 2 の `display/statements` では `LineItems` からの相対深さがインデントに使われる（I-2.3）。

**方針（案C）**: `depth` はそのまま絶対値を保持する。相対深さが必要な場合は利用側で `node.depth - line_items_node.depth` を計算する。理由: frozen dataclass のリベースは構造変更が必要で、YAGNI。利用側の計算コストも無視できる。

### 6.7 非財務 Role URI の扱い【F-7 反映】

提出者の `_pre.xml` には財務諸表以外の role URI（事業の状況、コーポレートガバナンス等の `jpcrp_cor` 系）も含まれる可能性がある。

**方針**: パーサーは `_pre.xml` 内の**全 role URI** を無差別にパースし、`dict[str, PresentationTree]` に含める。財務諸表のフィルタリングは Wave 2 の `concept_sets` / `taxonomy/labels` の責務であり、本パーサーは role URI の意味解釈を行わない。

---

## 7. マイルストーン完了条件

1. `parse_presentation_linkbase()` が実タクソノミの `_pre.xml` 構造（C-10.6 の XML 例）を正しくパースできる
2. concept 名が `xlink:href` フラグメントから正規化されている（`_2` サフィックス問題の回避を確認）【F-1】
3. `merge_presentation_trees()` で PL バリアントの**再帰マージ**が動作する（Heading → LineItems → 子の深い構造でも正しくマージ）【F-6】
4. マージ後のノードの `depth` がルートからの正しい絶対値である【H-1】
5. マージ時の属性競合が先着採用で解決される【H-2】
6. `PresentationTree.line_items_roots()` が DFS + concept 名末尾マッチで `LineItems` を返す【F-2, G-1】
7. `PresentationTree.flatten()` が深さ優先順にノードを返す。`skip_dimension` オプションが機能する【H-3】
8. `PresentationNode.is_total` が totalLabel 末尾の URI を正しく判定する【F-3】
9. 循環参照のある入力で `EdinetParseError` が送出される【F-4】
10. `warnings.warn` が `EdinetWarning` カテゴリで発行される【H-4】
11. `order` パース失敗時に `EdinetParseError` ではなく `warnings.warn` + `0.0` フォールバックで処理される【I-1】
12. concept 名正規化が標準 prefix、ハイフン含み prefix、`_[A-Z]` 境界なしフォールバックで正しく動作する【I-2】
13. ラベルロール URI 定数（`ROLE_TOTAL_LABEL` 等）が定義されている【I-4】
14. `merge_presentation_trees` が 1 辞書のみの場合に浅いコピーを返す【I-6】
15. テスト: 33+ テストケースが PASS（元の 16 + F系追加 5 + G系追加 5 + H系追加 3 + I系追加 4）
16. リント: ruff clean
17. 既存テスト: 全 PASS（破壊なし）

---

## 8. ファイル一覧

| 操作 | パス |
|------|------|
| 新規 | `src/edinet/xbrl/linkbase/presentation.py` |
| 新規 | `tests/test_xbrl/test_presentation.py` |
| 新規 | `tests/fixtures/linkbase_presentation/simple_bs.xml` |
| 新規 | `tests/fixtures/linkbase_presentation/multi_role.xml` |
| 新規 | `tests/fixtures/linkbase_presentation/variant_pl_main.xml` |
| 新規 | `tests/fixtures/linkbase_presentation/variant_pl_sales.xml` |
| 新規 | `tests/fixtures/linkbase_presentation/empty.xml` |
| 新規 | `tests/fixtures/linkbase_presentation/missing_attrs.xml` |
| 新規 | `tests/fixtures/linkbase_presentation/malformed.xml` |

全て新規ファイル。既存ファイルの変更なし。

---

## 9. QA 参照

| QA ID | タイトル | 本 Lane での利用 |
|-------|---------|-----------------|
| C-6 | プレゼンテーションリンクベースの詳細構造 | role URI, order, preferredLabel, abstract, prohibited の仕様根拠 |
| C-10 | リンクベースの XML 構造 | loc/arc の XML 属性・命名規則、完全な XML 例 |
| C-11 | リンクベースのマージアルゴリズム | 表示リンクでは prohibited/priority 不使用の根拠 |
| I-1 | Role URI と財務諸表の対応 | BS/PL/CF/SS/CI の role URI 完全リスト |
| I-1b | 提出者独自の roleType | サンプルでは独自 roleType なし。v0.1.0 では標準ロールで十分 |
| I-2 | Presentation ツリーの構造 | 階層関係、order 必須、depth、合計行識別の仕様 |
| I-3 | 提出者による Presentation のカスタマイズ | リキャスト方式。提出者の _pre.xml のみパースすればよい |
| Z-2 | 科目定義 JSON の自動生成可能性 | PL バリアント分割、CF の _pre 不在、23 業種同一構造 |
| H-8 | 実データの品質・エラー率 | 循環参照の可能性判断の根拠（F-4）|

---

## 10. フィードバック反映ログ

WAVE_1_LANE_1_FEEDBACK.md の全 12 項目を QA ドキュメント・既存実装と照合し、以下の判断を行った。

### 採用（計画に反映済み）

| ID | 優先度 | 変更内容 | 変更箇所 |
|----|--------|----------|----------|
| **F-1** | CRITICAL | concept 名を `xlink:href` フラグメントから正規化。`_2` サフィックス問題を回避。ただし `label_id` は公開フィールドとせず内部キーに留める（フィードバックから簡略化） | §2.1, §3.1 PresentationNode, §3.2 Step 3, §3.3 _LocInfo, §6.1, §6.2, テスト追加 |
| **F-2** | CRITICAL | `is_dimension_node: bool` フィールド追加。`_DIMENSION_SUFFIXES` 定数定義。`line_items_roots()` の探索を `is_dimension_node` ベースに明確化 | §2.1, §3.1 PresentationNode/PresentationTree, §3.2 Step 2, テスト追加 |
| **F-3** | CRITICAL | preferredLabel の docstring を完全 URI に修正。`is_total` プロパティ追加 | §3.1 PresentationNode, テスト追加 |
| **F-4** | HIGH | ツリー構築時の visited set による循環参照検出 + `EdinetParseError` 送出 | §2.1, §3.2 Step 2, テスト追加 |
| **F-6** | HIGH | マージアルゴリズムを浅い子結合から再帰マージに変更 | §3.1 merge_presentation_trees docstring, §3.2 Step 4, テスト追加 |
| **F-7** | HIGH | 全 role URI を無差別にパースする旨を明示 | §2.1, §3.1 parse_presentation_linkbase docstring, §6.7 新設 |
| **F-8** | MEDIUM | depth は絶対値のまま保持する設計判断を §6.6 に記載（案C 採用） | §6.6 新設 |
| **F-9** | MEDIUM | テストフィクスチャの設計方針に C-10.a.md の実 XML 例をベースとする旨を追記 | §4.1 |
| **F-10** | MEDIUM | `PresentationNode.__repr__` と `PresentationTree.__repr__` を REPL 向けにカスタマイズ | §3.1 |
| **F-11** | MEDIUM | テストケース 5 件追加（F-1, F-2, F-3×2, F-4, F-6 に対応） | §4.2 |

### 却下

| ID | 優先度 | 却下理由 |
|----|--------|----------|
| **F-5** | HIGH | YAGNI。ツリーは最大数百ノード程度であり `flatten()` + 線形探索で十分高速。Wave 2 で必要になった時点で追加すればよい。現時点での追加は scope creep |

### 変更不要

| ID | 優先度 | 理由 |
|----|--------|------|
| **F-12** | LOW | `order` の `float` 型は妥当。フィードバックも現状維持を支持 |

### フィードバックからの修正点

- **F-1 の簡略化**: フィードバックは `label_id` を公開フィールドとして追加することを提案したが、`label_id` の主要な用途はツリー構築時の内部キーであり、利用者にとっての価値は低い。同一 concept が同一ツリー内の異なる位置に出現するケースは dimension ノード（`ConsolidatedMember` 等）に限定され、これらは `is_dimension_node` フラグで識別可能。よって `label_id` は内部実装に留め、公開 API をシンプルに保つ

---

### 第2ラウンド（G-1〜G-8）

WAVE_1_LANE_1_FEEDBACK.md の第2ラウンド全 8 項目を QA ドキュメント・既存実装と照合し、以下の判断を行った。

#### 採用（計画に反映済み）

| ID | 優先度 | 変更内容 | 変更箇所 |
|----|--------|----------|----------|
| **G-1** | HIGH | `line_items_roots()` のアルゴリズムを DFS + concept 名末尾マッチ（`"LineItems"` 終端）に明確化。`is_dimension_node` は探索条件ではなくフィルタ用と位置づけ | §3.1 PresentationTree.line_items_roots() docstring |
| **G-2** | HIGH | href フラグメントの `_[A-Z]` 境界が見つからない場合のフォールバック（フラグメント全体を concept 名とする）を追加 | §3.2 Step 3 正規化ロジック |
| **G-3** | HIGH | 必須属性欠落時のフォールバック表を追加。`EdinetParseError` は malformed XML に限定し、属性欠落は `warnings.warn` + スキップ | §3.2 Step 1, テスト追加, フィクスチャ追加 |
| **G-4** | MEDIUM | マージ後の `node_count` 再計算（`_count_nodes(roots)` ヘルパー）を明記 | §3.1 merge docstring, §3.2 Step 4 |
| **G-5** | MEDIUM | `flatten()` の docstring に重複 concept に関する Note を追記 | §3.1 PresentationTree.flatten() docstring |
| **G-6** | MEDIUM | `merge_presentation_trees()` の引数なし・空辞書の仕様を明記。テスト 2 件追加 | §3.1 merge docstring, §3.2 Step 4, テスト追加 |

#### 変更不要（実装ヒント / 推奨）

| ID | 優先度 | 理由 |
|----|--------|------|
| **G-7** | LOW | frozen dataclass のツリー構築パターン。計画変更不要、実装エージェントへのヒントとして有用 |
| **G-8** | LOW | `__repr__` テストの追加推奨。計画の必須テストには含めないが、実装時に追加を推奨 |

#### 検証根拠

- **G-1**: I-2.a.md で `LineItems` はルート直下の兄弟ノードとして `Table` と並列。`is_dimension_node` は `Table` 分岐にも `True` であり、「dimension ノードを辿る」だけでは `Table → Axis → Member` の方向にも探索が進む。DFS + 末尾マッチが最も単純で正確
- **G-2**: 既存 `_split_fragment_prefix_local()` は境界未発見時に `None` を返す。filer の href に prefix なしの bare concept 名（例: `#ConsolidatedBalanceSheetHeading`）が実在することを C-10.xml_examples.py で確認
- **G-3**: `taxonomy/__init__.py` が `warnings.warn` + continue パターンを既に使用（L325, L351, L545）。H-8.a.md で GFM 例外 20+ 件あり属性欠落が稀に発生しうることを確認

---

### 第3ラウンド（H-1〜H-8）

WAVE_1_LANE_1_FEEDBACK.md の第3ラウンド全 8 項目を QA ドキュメント・既存実装と照合し、以下の判断を行った。

#### 採用（計画に反映済み）

| ID | 優先度 | 変更内容 | 変更箇所 |
|----|--------|----------|----------|
| **H-1** | HIGH | マージ後のノードの `depth` を 0 から再帰的に再計算するステップを明記 | §3.1 merge docstring Step 5, §3.2 Step 4 項番 6, テスト追加 |
| **H-2** | HIGH | マージ時の全属性競合解決ルールを「先着採用」に統一し明記。引数順序の意味をドキュメント化 | §3.1 merge docstring Step 3b + Args, §3.2 Step 4 項番 3, テスト追加 |
| **H-3** | MEDIUM | `flatten(skip_dimension=True)` パラメータ追加。`skip_abstract` と対称的な自然な拡張 | §3.1 PresentationTree.flatten() シグネチャ + docstring, テスト追加 |
| **H-4** | MEDIUM | `warnings.warn` のカテゴリを `EdinetWarning` に明示。`stacklevel=2`。import 対象リストにも反映 | §3.2 Step 1 フォールバック説明, §1 推奨事項 8 |
| **H-5** | MEDIUM | `sorted()` 安定ソートによる同一 order 時の出現順保持を明記 | §3.1 merge docstring Step 4, §3.2 Step 2 項番 5, §3.2 Step 4 項番 5 |
| **H-6** | MEDIUM | `merge_presentation_trees` の docstring に concept 名ベースグルーピングの既知制限（namespace 非考慮）を Note として追記 | §3.1 merge docstring Note |

#### 変更不要（実装ヒント / 推奨）

| ID | 優先度 | 理由 |
|----|--------|------|
| **H-7** | LOW | `__len__` / `__bool__` / `__contains__` の Pythonic プロトコル。計画変更不要、実装時の裁量に委ねる |
| **H-8** | LOW | テスト 5 件の追加推奨。計画の必須テストには含めないが、実装時に追加を推奨 |

#### 検証根拠

- **H-1**: frozen dataclass のマージでは全ノードを再構築する必要がある。PL バリアントファイルが異なるルート構造を持つ防御的シナリオで depth が不正になりうる。G-7 のボトムアップ構築パターンで自然に対処されるが、アルゴリズム記述として明示する価値がある
- **H-2**: PL バリアントマージの実用上は問題にならないが、API ドキュメントとして引数順序に意味があることを利用者に伝える必要がある
- **H-3**: Wave 2 の `concept_sets` が `flatten()` → concept 集合を取る利用パターンで頻繁に使用される。`skip_abstract` と対称的であり scope creep にならない。F-5（`find_concept`）の却下理由（YAGNI）とは異なり、既存パラメータの自然な拡張
- **H-4**: `edinet.exceptions.EdinetWarning` が `UserWarning` サブクラスとして実在（exceptions.py L5-10）。`taxonomy/__init__.py`, `parser.py`, `statements.py` 全てが `EdinetWarning` を使用していることを確認済み
- **H-5**: Python の `sorted()` は安定ソート（Timsort）。設計上の保証として文書化することで、同一 order 時の挙動が実装の偶然ではなくなる
- **H-6**: PL バリアントマージでは全て同一タクソノミ内であり実害なし。ただし Wave 2 で「提出者 _pre + 標準タクソノミ _pre」等の新しいユースケースが追加される可能性があり、事前に制限事項を明示する価値がある

---

### 第4ラウンド（I-1〜I-8）

WAVE_1_LANE_1_FEEDBACK.md の第4ラウンド全 8 項目を QA ドキュメント・既存実装と照合し、以下の判断を行った。

#### 採用（計画に反映済み）

| ID | 優先度 | 変更内容 | 変更箇所 |
|----|--------|----------|----------|
| **I-1** | HIGH | `order` パース失敗時の挙動を G-3 原則に統一。`EdinetParseError` → `warnings.warn` + `0.0` フォールバック | §6.3 全面改訂, テスト追加 |
| **I-2** | HIGH | concept 名正規化テスト 3 件追加（標準 prefix、ハイフン含み prefix、`_[A-Z]` 境界なしフォールバック） | §4.2 TestParsePresentationLinkbase に 3 件追加 |
| **I-3** | MEDIUM | `_split_fragment_prefix_local` 再実装の技術的負債マーカーを追記。Wave 1 統合タスクでの DRY 統一を確実にする | §6.1 に追記 |
| **I-4** | MEDIUM | `preferredLabel` の共通ラベルロール URI 定数 6 件を定義。`is_total` プロパティを定数参照に変更 | §3.1 モジュールレベル定数追加, `is_total` 改訂 |
| **I-6** | MEDIUM | `merge_presentation_trees` の single-dict 最適化を「常に浅いコピー」に変更。返り値変更時の入力汚染を防止 | §3.1 merge docstring G-6 エッジケース, §3.2 Step 4 エッジケース |

#### 推奨事項（計画の必須要件には含めない）

| ID | 優先度 | 内容 | 変更箇所 |
|----|--------|------|----------|
| **I-5** | MEDIUM | 実データスモークテスト（`EDINET_TAXONOMY_ROOT` 環境変数で CI skip）。handcrafted XML で再現不能な問題の早期検出に有用 | §4.4 新設 |

#### 変更不要

| ID | 優先度 | 理由 |
|----|--------|------|
| **I-7** | LOW | `is_abstract` 判定の限界の注記。計画変更不要。将来 XSD パース連携時に精度向上可能 |
| **I-8** | LOW | `__repr__` テストの追加推奨。G-8 推奨で既にカバー |

#### 検証根拠

- **I-1**: §3.2 Step 1 の G-3 原則（`EdinetParseError` は malformed XML に限定）と §6.3 の `order` パース失敗時の `EdinetParseError` 送出が矛盾していた。`order="abc"` は XML としては valid であり、G-3 の定義に従えば `warnings.warn` + フォールバックが正しい。既存コードの `warnings.warn` パターン（`taxonomy/__init__.py`, `parser.py`, `statements.py`）とも一貫。H-8 で確認された GFM 例外 20+ 件を考慮すると、1 つの arc の属性値異常で全パースが中断されるのは実用上問題
- **I-2**: F-1 は CRITICAL であり、Wave 2 の `concept_sets` の正確性に直結する最重要ロジック。既存の `_split_fragment_prefix_local` の Note に「IFRS 拡張対応時に再検証が必要」とあり、エッジケースのテスト網羅が特に重要。テスト 2 件では標準 prefix 分離・ハイフン含み prefix 分離・境界なしフォールバックがカバーされていなかった
- **I-3**: `taxonomy/__init__.py:419` の `_split_fragment_prefix_local` と本モジュールの正規化ロジックが同一アルゴリズム。Wave 1 の並列安全性制約上の重複だが、統合タスクでの一元化を文書で担保する
- **I-4**: 既存の `taxonomy/__init__.py` に `ROLE_LABEL`, `ROLE_VERBOSE`, `ROLE_TOTAL` が定義済み。presentation.py でも同等の定数を提供することで利用者の typo 防止と `is_total` の実装を定数参照に改善。Wave 1 統合タスクで I-3 と合わせて共通定数として一元化する
- **I-6**: `merge_presentation_trees` に 1 辞書のみ渡した場合、返り値が入力と同一オブジェクト（`is` で True）になる。`PresentationTree` は frozen だが dict コンテナは mutable であり、返り値への追加・削除操作が入力を汚染する footgun。浅いコピーのコスト（辞書エントリ数十件のポインタコピー）は無視できる。呼び出し頻度も低い（提出者あたり 1 回）

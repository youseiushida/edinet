# 並列実装の安全ルール（必ず遵守）

あなたは Wave 2 / Lane 1 を担当するエージェントです。
担当機能: concept_sets (Presentation Linkbase からの科目セット自動導出)

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
   - `src/edinet/xbrl/taxonomy/concept_sets.py` (新規)
   - `tests/test_xbrl/test_concept_sets.py` (新規)
   - `tests/fixtures/concept_sets/` (新規ディレクトリ)
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
   - `tests/fixtures/linkbase_presentation/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリを作成すること
     例: `tests/fixtures/concept_sets/`

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets` （OK）
   - 例: `from edinet.xbrl import derive_concept_sets` （NG）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_concept_sets.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 1 で実装済みのモジュールは import 可能:
     - `edinet.xbrl.linkbase.presentation` (PresentationTree, PresentationNode, parse_presentation_linkbase, merge_presentation_trees)
     - `edinet.xbrl._linkbase_utils` (extract_concept_from_href, ROLE_* 定数)
     - `edinet.xbrl._namespaces` (NS_* 定数)
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 1: Presentation Linkbase からの科目セット自動導出 (`taxonomy/concept_sets`)

## 0. 位置づけ

Wave 2 Lane 1 は、Wave 1 Lane 1 で実装された Presentation Linkbase パーサー（`pres_tree`）の出力を入力として、**財務諸表ごとの concept セット（科目リスト + 表示順序）を自動導出する**モジュールを新規実装する。

**FUTUREPLAN.tmp.md での位置**: Phase 2-2 (taxonomy/concept_sets)。Phase 2 の最大レバレッジポイントであり、**手動 JSON（`pl_jgaap.json` / `bs_jgaap.json` / `cf_jgaap.json`）の全廃**を実現する。23 業種の全 `_pre.xml` ファイルを 1 パーサーで自動カバーし、タクソノミ年次更新時の手動メンテを不要にする。

**依存先**:
- `edinet.xbrl.linkbase.presentation` — `PresentationTree`, `PresentationNode`, `parse_presentation_linkbase`, `merge_presentation_trees` (Wave 1 L1, 実装済み)

**利用者** (Wave 3 以降):
- `standards/normalize` — concept セットを会計基準横断で統合
- `statements.py` — `_load_concept_definitions()` を `concept_sets` 呼び出しに置換（Wave 3 L1）
- `display/statements` — 表示順・インデント構造の根拠

**解決する既知バグ**:
- **BUG-6**: PL に SS/CF の科目が混入する問題。現行は `DurationPeriod` で PL/CF を分類しているが、SS と CF も `DurationPeriod` を使用するため cross-contamination が発生。concept_sets は **role URI ベース**で諸表を識別するため、根本的に解決される

---

## 1. 背景知識（QA サマリー）

### 1.1 現行の手動 JSON の問題点

現在の `statements.py` は手動作成の JSON ファイルを使用:
- `pl_jgaap.json`: 16 concept（売上高〜非支配株主に帰属する当期純利益）
- `bs_jgaap.json`: 20 concept（流動資産〜負債純資産合計）
- `cf_jgaap.json`: 8 concept（営業CF〜現金及び現金同等物の期末残高）

問題:
1. **J-GAAP 一般事業会社のみ**。銀行業・保険業・証券業・建設業・鉄道業は PL 構造が根本的に異なるが未対応（E-5）
2. **タクソノミ年次更新に弱い**。concept 名の変更・追加・削除を手動追跡する必要がある
3. **concept 数が少なすぎる**。実際の標準タクソノミには数十〜数百の concept が存在するが、JSON は主要科目のみ
4. **表示順が手動管理**。Presentation Linkbase の `order` 属性と不整合のリスク

### 1.2 Presentation Linkbase の構造と role URI（I-1, I-2, C-6）

Presentation Linkbase（`_pre.xml`）は role URI ごとに科目の階層ツリーを定義する。role URI が **財務諸表の種類を一意に識別する唯一の信頼できる情報**。

主要な role URI（一般事業会社、提出者用）:

| 諸表 | role ID パターン | ELR番号 |
|------|-----------------|---------|
| BS 連結 | `rol_ConsolidatedBalanceSheet` | 310010 |
| BS 個別 | `rol_BalanceSheet` | 310040 |
| PL 連結 | `rol_ConsolidatedStatementOfIncome` | 321010 |
| PL 個別 | `rol_StatementOfIncome` | 321040 |
| CF 連結(間接法) | `rol_ConsolidatedStatementOfCashFlows-indirect` | 342010 |
| CF 連結(直接法) | `rol_ConsolidatedStatementOfCashFlows-direct` | 341010 |
| SS 連結 | `rol_ConsolidatedStatementOfChangesInEquity` | 330010 |
| CI 連結 | `rol_ConsolidatedStatementOfComprehensiveIncome` | 322010 |

半期・四半期・第一種中間のバリエーション（`SemiAnnual`, `Quarterly`, `Type1SemiAnnual` プレフィックス付き）もある。

### 1.3 標準タクソノミの _pre ファイル構造（Z-2）

標準タクソノミ側では _pre ファイルが以下のように分割されている:

**PL**（バリアントあり、同一 role URI を共有）:
- `_pre_pl.xml` — 営業利益以降
- `_pre_pl-2-PL-01-Sales-1-Net.xml` — 売上高区分（Net方式）
- `_pre_pl-2-PL-04-SGA-1-ByAccount.xml` — 販管費区分（勘定科目別）
- etc.

**BS**: `_pre_bs.xml`（バリアントなし）

**CF**: 一般事業会社(cns)には `_pre_cf.xml` が**存在しない**（Z-2.3）。業種別ディレクトリ（銀行業 bk1 等）には存在する。

**SS**: `_pre_ss.xml`（存在）

### 1.4 業種別タクソノミの同一構造（Z-2, E-5）

23 業種の全 `_pre.xml` ファイルは**同一 XML 構造**。パーサー 1 つで全業種をカバー可能。
ただし業種ごとに:
- 使用する concept subset が異なる（同じ `jppfs_cor` 名前空間内）
- PL の最上位科目が異なる（銀行: 経常収益、保険: 正味収入保険料、一般: 売上高）
- CF の存在有無が異なる

### 1.5 提出者 _pre.xml とのマージ不要（I-3, C-11）

- 提出者の _pre.xml は**リキャスト方式**で独立しており、提出者の _pre.xml のみで表示構造が完全に取得できる
- `concept_sets` は**標準タクソノミの `_pre.xml`** をパースして、「ある role URI に属する concept は何か」を網羅的に定義する
- 提出者の `_pre.xml` は拡張科目を含むが、標準タクソノミで定義される concept セットの**スーパーセット**

### 1.6 CF の _pre 不在への対応（Z-2.3）

一般事業会社(cns)の CF には `_pre_cf.xml` が存在しない。対応方針:

1. **業種別 _pre からの共通 concept 抽出**: 銀行業 (bk1) 等の CF _pre ファイルには CF の概念セットが含まれる。これらから CF 用の概念セットを導出する
2. **Calculation Linkbase からの導出**: `_cal_cf.xml`（一般事業会社にも存在する）から CF の概念を抽出する（Wave 1 L2 の calc_tree を使用）
3. **フォールバック JSON**: 導出に失敗した場合の安全弁として既存 JSON 形式も読み込み可能にする

本 Lane では方針 1 を主軸とし、方針 3 をフォールバックとして実装する。方針 2 は calc_tree が Wave 2 の同時レーンではないため依存に注意するが、Wave 1 で実装済みのため import 可能。

---

## 2. ゴール

### 2.1 機能要件

1. **標準タクソノミの `_pre.xml` ファイル群をパースし、role URI ごとの concept セットを自動導出する**
   - 入力: タクソノミルートパス（`EDINET_TAXONOMY_ROOT`）
   - 出力: `{role_uri: ConceptSet}` の辞書

2. **role URI → `StatementType` のマッピングを提供する**
   - role URI 文字列に含まれるキーワード（`BalanceSheet`, `StatementOfIncome`, `CashFlows`, `ChangesInEquity`, `ComprehensiveIncome`）でパターンマッチ
   - **標準タクソノミの `rol_std_*` パターンと提出者用の `rol_*` パターンの両方に対応する**（`std_` プレフィックスを除去してからマッチング）
   - 連結/個別、通期/半期/四半期のバリエーションを識別
   - 未知の role URI に対しては `None` を返す（非財務セクションの role URI は無視）

3. **ConceptSet は以下の情報を保持する**:
   - `statement_type`: `StatementType` (BS/PL/CF) + 将来の SS/CI 拡張
   - `role_uri`: 元の role URI 文字列
   - `concepts`: `tuple[ConceptEntry, ...]` — concept 名・表示順序・合計行フラグ・depth 情報
   - `is_consolidated`: 連結か個別か
   - `period_type`: `"instant"` or `"duration"`（BS=instant, PL/CF/SS=duration）
   - `source`: 導出元の情報（タクソノミパス、業種コード等）

4. **ConceptEntry は以下の情報を保持する**:
   - `concept`: 正規化済み concept 名（例: `"CashAndDeposits"`）
   - `order`: 表示順序（`float`、Presentation Linkbase の order 値）
   - `is_total`: 合計行か（`preferredLabel == totalLabel`）
   - `is_abstract`: 見出し行か。`PresentationNode.is_abstract` の値を転写する（実装では `Abstract` / `Heading` 末尾の両方を判定済み）
   - `depth`: LineItems からの相対深さ（インデント計算用、0-based）
   - `href`: 元の XSD href（将来のラベル解決用）

5. **PL バリアントファイルのマージ対応**:
   - 複数の `_pre_pl*.xml` を `merge_presentation_trees()` で統合してから concept セットを導出
   - 標準タクソノミ内の PL バリアントパターンを自動発見する

6. **23 業種の自動カバー**:
   - タクソノミルート配下の全業種ディレクトリ（`jpigp/2025-11-01/`, `jppfs/2025-11-01/` 等）を走査
   - 各業種の _pre ファイルから業種別 concept セットを導出
   - 業種コード → concept セットのレジストリを構築

7. **現行 JSON との互換性**:
   - `ConceptSet` から `list[dict[str, object]]` 形式（`{"concept": str, "order": int, "label_hint": str}`）への変換メソッドを提供
   - Wave 3 L1 での `statements.py` 統合時に `_load_concept_definitions()` を置換する際のブリッジ

8. **CF の _pre 不在への対応**:
   - 業種別ディレクトリから CF 概念を取得し、一般事業会社にも適用
   - フォールバック: 導出失敗時は既存の `cf_jgaap.json` 相当の概念を返す

### 2.2 パフォーマンス要件

- 全業種（23 ディレクトリ × 複数 _pre ファイル）のスキャンは 30 秒以内
- 結果を pickle キャッシュし、2 回目以降は 100ms 以内
- 単一業種の concept セット導出は 1 秒以内

### 2.3 非機能要件

- `lxml` ベース（既存パーサーと統一）
- 日本語 docstring（Google Style）
- 日本語エラーメッセージ
- frozen dataclass でイミュータブルなデータ構造
- タクソノミパスが設定されていない環境でもモジュール自体の import は可能（遅延初期化）

---

## 3. 設計

### 3.1 公開 API

```python
# src/edinet/xbrl/taxonomy/concept_sets.py

import enum
from dataclasses import dataclass
from edinet.models.financial import StatementType


class StatementCategory(enum.Enum):
    """財務諸表の分類（StatementType を拡張）。

    StatementType (PL/BS/CF) に SS/CI を追加した分類。
    concept_sets モジュール内での内部分類に使用する。

    Attributes:
        BALANCE_SHEET: 貸借対照表。
        INCOME_STATEMENT: 損益計算書。
        CASH_FLOW_STATEMENT: キャッシュフロー計算書。
        STATEMENT_OF_CHANGES_IN_EQUITY: 株主資本等変動計算書。
        COMPREHENSIVE_INCOME: 包括利益計算書。
    """
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW_STATEMENT = "cash_flow_statement"
    STATEMENT_OF_CHANGES_IN_EQUITY = "statement_of_changes_in_equity"
    COMPREHENSIVE_INCOME = "comprehensive_income"

    def to_statement_type(self) -> StatementType | None:
        """既存の StatementType に変換する。SS/CI は None。"""

    @classmethod
    def from_statement_type(cls, st: StatementType) -> "StatementCategory":
        """StatementType から StatementCategory に変換する。

        Args:
            st: 変換元の StatementType。

        Returns:
            対応する StatementCategory。
        """


@dataclass(frozen=True, slots=True)
class ConceptEntry:
    """concept セット内の 1 エントリ。

    Attributes:
        concept: 正規化済み concept ローカル名（例: ``"CashAndDeposits"``）。
        order: 表示順序。Presentation Linkbase の ``order`` 属性値。
            兄弟ノード間の相対順序。
        is_total: 合計行か。``preferredLabel`` が ``totalLabel`` の場合 ``True``。
        is_abstract: 見出し行か。``PresentationNode.is_abstract`` の値を転写する
            （実装では ``Abstract`` / ``Heading`` 末尾の両方を判定済み）。
        depth: LineItems ノードからの相対深さ（0-based）。
            インデント計算に使用する。
        href: 元の XSD href 文字列。将来のラベル解決に使用する。
    """
    concept: str
    order: float
    is_total: bool
    is_abstract: bool
    depth: int
    href: str


@dataclass(frozen=True, slots=True)
class ConceptSet:
    """1 つの role URI に対応する concept セット。

    Presentation Linkbase から自動導出された、ある財務諸表に属する
    全 concept の順序付きリスト。

    Attributes:
        role_uri: 元の拡張リンクロール URI。
        category: 財務諸表の分類。
        is_consolidated: 連結か個別か。
        concepts: concept エントリのタプル（表示順ソート済み）。
        source_info: 導出元情報（デバッグ用）。
    """
    role_uri: str
    category: StatementCategory
    is_consolidated: bool
    concepts: tuple[ConceptEntry, ...]
    source_info: str

    def concept_names(self) -> frozenset[str]:
        """全 concept 名のフローズンセットを返す。

        ``statements.py`` の ``known_concepts`` セット構築に使用する。
        abstract 科目を含む。フィルタが必要な場合は
        ``non_abstract_concepts()`` を使用する。

        Returns:
            concept ローカル名のフローズンセット。
        """

    def non_abstract_concepts(self) -> frozenset[str]:
        """abstract でない concept 名のフローズンセットを返す。

        Returns:
            ``is_abstract=False`` の concept ローカル名のフローズンセット。
        """

    def to_legacy_format(self) -> list[dict[str, object]]:
        """現行の JSON 互換形式に変換する。

        ``statements.py`` の ``_load_concept_definitions()`` が返す形式
        と同一:  ``[{"concept": str, "order": int, "label_hint": str}, ...]``

        ``label_hint`` には concept 名をそのまま設定する
        （ラベル解決は TaxonomyResolver の責務）。

        abstract 科目は除外する（現行 JSON に abstract は含まれない）。
        ``order`` は abstract 除外後の flatten 順で 1 から付番する（連番）。

        実装イメージ::

            non_abstract = [e for e in self.concepts if not e.is_abstract]
            return [
                {"concept": e.concept, "order": i + 1, "label_hint": e.concept}
                for i, e in enumerate(non_abstract)
            ]

        Returns:
            JSON 互換のリスト。
        """

    def __repr__(self) -> str:
        """REPL 向けの簡潔な表現。"""
        return (
            f"ConceptSet(role_uri={self.role_uri!r}, "
            f"category={self.category.name}, "
            f"concepts={len(self.concepts)})"
        )


# ----- role URI → StatementCategory マッピング -----

# role URI 文字列に含まれるキーワードでパターンマッチ
# 標準タクソノミ: "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedBalanceSheet"
# 提出者用:       "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
# classify_role_uri() では `rol_` 以降から `std_` を除去してからマッチングする。
_ROLE_PATTERNS: dict[str, tuple[StatementCategory, bool]] = {
    # (キーワード, (カテゴリ, 連結フラグ))
    # 連結 BS
    "ConsolidatedBalanceSheet": (StatementCategory.BALANCE_SHEET, True),
    # 個別 BS
    "BalanceSheet": (StatementCategory.BALANCE_SHEET, False),
    # ... (他のパターンも同様)
}


def classify_role_uri(
    role_uri: str,
) -> tuple[StatementCategory, bool] | None:
    """role URI から財務諸表カテゴリと連結/個別を推定する。

    role URI 文字列の末尾部分（``rol_*`` 以降）に含まれるキーワードで
    パターンマッチする。複数パターンにマッチする場合は最長一致を優先する。

    前処理として以下を除去してからマッチングする:
    - ``std_`` プレフィックス（標準タクソノミ用 ``rol_std_*`` → ``rol_*``）
    - 半期 (``SemiAnnual``)、四半期 (``Quarterly``)、
      第一種中間 (``Type1SemiAnnual``) のプレフィックス

    Note:
        EDINET タクソノミには 2 種類の role URI が存在する（I-1 QA [F8]）:
        - 標準タクソノミ用: ``rol_std_ConsolidatedBalanceSheet``（53件）
        - 提出者用: ``rol_ConsolidatedBalanceSheet``（952件）
        本関数は両方に対応する。

    Args:
        role_uri: 拡張リンクロールの完全 URI。

    Returns:
        ``(StatementCategory, is_consolidated)`` のタプル。
        財務諸表以外の role URI の場合は ``None``。
    """


@dataclass(frozen=True)
class ConceptSetRegistry:
    """全業種・全諸表の ConceptSet を保持するレジストリ。

    ``derive_concept_sets()`` の返り値。業種コード・諸表タイプ・
    連結/個別による効率的な検索を提供する。

    Attributes:
        _sets: 内部ストレージ。``{industry_code: {role_uri: ConceptSet}}``。
    """
    _sets: dict[str, dict[str, ConceptSet]]

    def get(
        self,
        statement_type: StatementType,
        *,
        consolidated: bool = True,
        industry_code: str = "cns",
    ) -> ConceptSet | None:
        """指定条件に合致する ConceptSet を 1 つ返す。

        Args:
            statement_type: 取得する財務諸表の種類 (PL/BS/CF)。
            consolidated: True なら連結、False なら個別。
            industry_code: 業種コード（``"cns"`` = 一般事業会社）。

        Returns:
            合致する ConceptSet。見つからない場合は ``None``。
        """

    def all_for_industry(self, industry_code: str) -> list[ConceptSet]:
        """指定業種の全 ConceptSet を返す。

        Args:
            industry_code: 業種コード。

        Returns:
            ConceptSet のリスト。業種が存在しない場合は空リスト。
        """

    def industries(self) -> frozenset[str]:
        """利用可能な業種コードの一覧を返す。

        Returns:
            業種コードのフローズンセット。
        """

    def statement_categories(
        self, industry_code: str = "cns",
    ) -> frozenset[StatementCategory]:
        """指定業種で利用可能な StatementCategory の一覧を返す。

        Args:
            industry_code: 業種コード。

        Returns:
            StatementCategory のフローズンセット。
        """


def derive_concept_sets(
    taxonomy_path: str | Path,
    *,
    use_cache: bool = True,
) -> ConceptSetRegistry:
    """標準タクソノミから concept セットを自動導出する。

    タクソノミルートパス配下の全業種ディレクトリの ``_pre*.xml`` を
    スキャンし、role URI ごとの concept セットを構築する。

    PL のバリアントファイル（``_pre_pl*.xml``）は自動マージされる。

    結果は pickle キャッシュされ、2 回目以降は高速に読み込まれる。

    Args:
        taxonomy_path: タクソノミのルートディレクトリパス
            （例: ``"/path/to/ALL_20251101"``）。
        use_cache: pickle キャッシュを使用するか。

    Returns:
        全業種・全諸表の ConceptSet を保持する ``ConceptSetRegistry``。

    Raises:
        EdinetConfigError: taxonomy_path が存在しない場合。
    """


def derive_concept_sets_from_trees(
    trees: dict[str, PresentationTree],
    *,
    source_info: str = "",
) -> list[ConceptSet]:
    """パース済み PresentationTree 辞書から concept セットを導出する。

    ``derive_concept_sets()`` の低レベル版。
    ``parse_presentation_linkbase()`` の出力を直接受け取る。
    テストや単一ファイルのアドホック解析に使用する。

    Args:
        trees: ``{role_uri: PresentationTree}`` の辞書。
        source_info: 導出元情報（デバッグ用文字列）。

    Returns:
        導出された ConceptSet のリスト。
        財務諸表以外の role URI は除外される。
    """


def get_concept_set(
    taxonomy_path: str | Path,
    statement_type: StatementType,
    *,
    consolidated: bool = True,
    industry_code: str = "cns",
    use_cache: bool = True,
) -> ConceptSet | None:
    """指定条件に合致する ConceptSet を 1 つ返す便利関数。

    ``derive_concept_sets()`` で ``ConceptSetRegistry`` を取得し、
    ``ConceptSetRegistry.get()`` に委譲するショートカット。
    ``statements.py`` の ``_load_concept_definitions()`` を将来置換する
    際のエントリーポイント。

    Args:
        taxonomy_path: タクソノミのルートディレクトリパス。
        statement_type: 取得する財務諸表の種類 (PL/BS/CF)。
        consolidated: True なら連結、False なら個別。
        industry_code: 業種コード（``"cns"`` = 一般事業会社）。
        use_cache: pickle キャッシュを使用するか。

    Returns:
        合致する ConceptSet。見つからない場合は ``None``。
    """
```

### 3.2 内部実装の方針

#### Step 1: role URI パターンの定義

```python
_ROLE_KEYWORDS: dict[str, tuple[StatementCategory, bool]] = {}
```

role URI 文字列の末尾から `rol_` 以降を抽出し、以下の前処理を行ってからキーワードマッチングする:

1. `rol_` 以降の文字列を抽出
2. `std_` プレフィックスを除去（標準タクソノミ対応: `rol_std_X` → `X`、提出者用: `rol_X` → `X`）
3. 半期/四半期/中間プレフィックスを除去
4. 残った文字列に対して最長一致でキーワードマッチング

マッチングキーワード:

| キーワードパターン | カテゴリ | 連結 |
|-------------------|---------|------|
| `ConsolidatedBalanceSheet` | BS | True |
| `BalanceSheet` (Consolidated なし) | BS | False |
| `ConsolidatedStatementOfIncome` | PL | True |
| `StatementOfIncome` (Consolidated なし) | PL | False |
| `ConsolidatedStatementOfCashFlows` | CF | True |
| `StatementOfCashFlows` (Consolidated なし) | CF | False |
| `ConsolidatedStatementOfChangesInEquity` | SS | True |
| `StatementOfChangesInEquity` (Consolidated なし) | SS | False |
| `ConsolidatedStatementOfComprehensiveIncome` | CI | True |
| `StatementOfComprehensiveIncome` (Consolidated なし) | CI | False |

**半期/四半期/中間対応**: role URI には `SemiAnnual`, `Quarterly`, `Type1SemiAnnual` のプレフィックスが付くバリエーションがある（例: `rol_SemiAnnualConsolidatedBalanceSheet`）。これらは基本パターンの前に付加されるため、プレフィックスを除去してからマッチングする。

**マッチング戦略**: `rol_` 以降の文字列に対して、キーワードの**最長一致**で判定する。`BalanceSheet` は `ConsolidatedBalanceSheet` のサブ文字列であるため、`Consolidated` 付きを先に判定する。

#### Step 2: PresentationTree から ConceptSet への変換

```python
def _tree_to_concept_set(
    role_uri: str,
    tree: PresentationTree,
    category: StatementCategory,
    is_consolidated: bool,
    source_info: str,
) -> ConceptSet:
```

1. `tree.line_items_roots()` で LineItems 以下のルートノード群を取得
2. 取得したルートノードを起点に、独自の深さ優先走査を行う
   - `flatten()` は使用しない（LineItems の外側のノードが混入するリスクを回避）
   - `line_items_roots()` の設計意図と合致するアプローチ
3. 走査中の各ノードから `ConceptEntry` を構築:
   - `concept`: `node.concept`
   - `order`: `node.order`（兄弟間の相対順序）
   - `is_total`: `node.is_total`
   - `is_abstract`: `node.is_abstract`（`PresentationNode` の値を転写。`Abstract` / `Heading` 末尾の両方を判定済み）
   - `depth`: `node.depth - base_depth`（LineItems ルートからの相対深さ、0-based）
   - `href`: `node.href`
4. dimension ノード（`is_dimension_node=True`）は除外する
5. ノードは深さ優先走査順で保持する

**エッジケース**:
- LineItems が見つからない場合: `line_items_roots()` が `roots` をそのまま返すため、ルートノードを起点とする
- 空のツリー（ノード 0 件）: 空の `concepts` タプルを持つ `ConceptSet` を返す

#### Step 3: タクソノミディレクトリの走査

```python
def _scan_taxonomy_directory(
    taxonomy_path: Path,
) -> dict[str, list[tuple[str, bytes]]]:
```

1. `taxonomy_path / "taxonomy" / "jppfs" / "*" / "r"` 配下のサブディレクトリを走査
2. 各サブディレクトリ名を業種コードとして認識（例: `r/cns/` → `"cns"`）
3. _pre ファイルのパターン: `*_pre*.xml`
4. ファイルを読み込み、`{業種コード: [(ファイル名, bytes), ...]}` を返す
5. `taxonomy_path / "taxonomy" / "jpigp"` 配下は IFRS 用として別途走査（将来拡張用）

**ディレクトリ構造（実態確認済み、Z-2 [F2][F3]）**:
```
taxonomy/
├── jppfs/2025-11-01/
│   └── r/                          # 全業種が r/ 配下に配置
│       ├── cns/                    # 一般事業会社
│       │   ├── jppfs_cns_ac_2025-11-01_pre_bs.xml
│       │   ├── jppfs_cns_ac_2025-11-01_pre_pl.xml
│       │   ├── jppfs_cns_ac_2025-11-01_pre_pl-2-PL-01-Sales-1-Net.xml  # PL バリアント
│       │   ├── jppfs_cns_ac_2025-11-01_pre_ss.xml
│       │   └── (CF の _pre なし)
│       ├── bk1/                    # 銀行業 第一種
│       │   ├── jppfs_bk1_ac_2025-11-01_pre_pl.xml
│       │   ├── jppfs_bk1_ac_2025-11-01_pre_cf-in-3-CF-03-Method-Indirect.xml  # CF あり
│       │   └── ...
│       ├── in1/                    # 保険業 第一種
│       └── ... (23 業種)
├── jpigp/2025-11-01/
│   └── r/
│       └── jpigp_ac_2025-11-01_pre_cf.xml  # IFRS 用
└── ...
```

**ファイル名パターン**: `jppfs_{業種}_{連結区分}_{日付}_{リンク種別}_{財務諸表種別}.xml`

#### Step 4: PL バリアントの自動マージ

```python
def _merge_pl_variants(
    pre_files: list[tuple[str, bytes]],
) -> dict[str, PresentationTree]:
```

1. ファイル名に `_pre_pl` を含むファイルを PL バリアント候補とする
2. 各ファイルを `parse_presentation_linkbase()` でパース
3. **同一 role URI** を持つツリーを `merge_presentation_trees()` でマージ
4. PL 以外のファイル（`_pre_bs`, `_pre_cf`, `_pre_ss` 等）は個別にパースして結果辞書に追加

**マージ順序**: メインファイル（`_pre_pl.xml`）を先頭、バリアント（`_pre_pl-2-*.xml`）を後続。先着採用ルール（H-2）により、メインファイルの属性が優先される。

#### Step 5: キャッシュ

```python
def _cache_path(taxonomy_path: Path) -> Path:
def _load_cache(path: Path) -> dict | None:
def _save_cache(data: dict, path: Path) -> None:
```

既存の `taxonomy/__init__.py` のキャッシュパターンと同じ:
- `platformdirs.user_cache_dir("edinet")` にキャッシュ
- pickle 形式
- キャッシュキー: `concept_sets_v{version}_{taxonomy_version}_{path_hash}.pkl`
- バージョン不一致・読み込みエラー時は自動再構築

**セキュリティ注記**: pickle キャッシュは `platformdirs.user_cache_dir()` 配下に保存される。このディレクトリは当該ユーザーのみが書き込み可能である前提とする。共有ファイルシステム上のキャッシュディレクトリは使用しないこと。キャッシュの読み込み時に `pickle.UnpicklingError` が発生した場合はキャッシュを破棄して再構築する（既存の `TaxonomyResolver` と同一方針）。

### 3.3 データ型（内部）

```python
@dataclass(frozen=True, slots=True)
class _IndustryInfo:
    """業種の情報。"""
    code: str        # "cns", "bk1", "in1" 等
    name: str        # ディレクトリ名から推定
    pre_files: tuple[tuple[str, bytes], ...]  # (ファイル名, bytes)
```

---

## 4. テスト計画

### 4.1 テストフィクスチャ

`tests/fixtures/concept_sets/` ディレクトリに以下を作成:

| ファイル | 内容 | 用途 |
|---------|------|------|
| `simple_bs_pre.xml` | BS のみの小さな _pre.xml（10 nodes 程度） | 基本 ConceptSet 導出テスト |
| `simple_pl_pre.xml` | PL のみの _pre.xml（15 nodes 程度） | PL 導出テスト |
| `pl_main.xml` | PL メインファイル（営業利益以降） | バリアントマージのテスト |
| `pl_variant_sales.xml` | PL Sales バリアント（売上高区分） | バリアントマージのテスト |
| `multi_statement.xml` | BS + PL + CF を含む | 複数諸表の同時導出テスト |
| `cf_pre.xml` | CF のみの _pre.xml | CF 概念セット導出テスト |
| `consolidated_and_nonconsolidated.xml` | 連結 + 個別 role を含む | 連結/個別分離テスト |
| `non_financial_roles.xml` | 非財務セクションの role URI のみ | フィルタリングテスト |
| `empty_pre.xml` | 空の linkbase | エッジケース |

**フィクスチャ設計方針**: Wave 1 L1 のフィクスチャ（`tests/fixtures/linkbase_presentation/`）の XML 構造をベースに、concept_sets テスト専用のファイルを作成する。実タクソノミの role URI、concept 名、階層構造を模した現実的な XML。

### 4.2 テストケース

```python
class TestClassifyRoleUri:
    """classify_role_uri() のテスト。"""

    def test_consolidated_bs(self):
        """連結 BS の role URI が正しく分類されること。"""

    def test_nonconsolidated_pl(self):
        """個別 PL の role URI が正しく分類されること。"""

    def test_consolidated_cf_indirect(self):
        """連結 CF（間接法）の role URI が正しく分類されること。"""

    def test_consolidated_cf_direct(self):
        """連結 CF（直接法）の role URI が正しく分類されること。"""

    def test_consolidated_ss(self):
        """連結 SS の role URI が正しく分類されること。"""

    def test_consolidated_ci(self):
        """連結 CI の role URI が正しく分類されること。"""

    def test_semi_annual_prefix(self):
        """半期 prefix 付き role URI が正しく分類されること。"""

    def test_quarterly_prefix(self):
        """四半期 prefix 付き role URI が正しく分類されること。"""

    def test_non_financial_role_returns_none(self):
        """非財務 role URI で None が返ること。"""

    def test_unknown_role_returns_none(self):
        """未知の role URI で None が返ること。"""

    def test_longest_match_priority(self):
        """ConsolidatedBalanceSheet が BalanceSheet より優先されること。"""

    def test_std_prefix_bs(self):
        """標準タクソノミの rol_std_ prefix 付き BS role URI が正しく分類されること。"""

    def test_std_prefix_pl(self):
        """標準タクソノミの rol_std_ prefix 付き PL role URI が正しく分類されること。"""

    def test_std_prefix_cf(self):
        """標準タクソノミの rol_std_ prefix 付き CF role URI が正しく分類されること。"""


class TestDeriveConceptSetsFromTrees:
    """derive_concept_sets_from_trees() のテスト。"""

    def test_bs_concepts_extracted(self):
        """BS の _pre.xml から concept セットが導出できること。"""

    def test_pl_concepts_extracted(self):
        """PL の _pre.xml から concept セットが導出できること。"""

    def test_concept_order_preserved(self):
        """Presentation Linkbase の order 順が保持されること。"""

    def test_total_items_identified(self):
        """preferredLabel=totalLabel の合計行が is_total=True であること。"""

    def test_abstract_items_identified(self):
        """Abstract/Heading の見出し行が is_abstract=True であること。"""

    def test_depth_relative_to_line_items(self):
        """depth が LineItems からの相対深さであること。"""

    def test_dimension_nodes_excluded(self):
        """Table/Axis/Member/Domain ノードが除外されること。"""

    def test_non_financial_roles_excluded(self):
        """非財務 role URI の PresentationTree が結果に含まれないこと。"""

    def test_empty_tree_produces_empty_concepts(self):
        """空のツリーから空の concepts が導出されること。"""

    def test_multiple_roles_produce_multiple_sets(self):
        """複数 role URI から複数の ConceptSet が導出されること。"""

    def test_consolidated_and_nonconsolidated_separated(self):
        """連結と個別が別々の ConceptSet になること。"""


class TestConceptSet:
    """ConceptSet のメソッドテスト。"""

    def test_concept_names_returns_frozenset(self):
        """concept_names() がフローズンセットを返すこと。"""

    def test_non_abstract_concepts_excludes_abstract(self):
        """non_abstract_concepts() が abstract を除外すること。"""

    def test_to_legacy_format_compatible(self):
        """to_legacy_format() が現行 JSON と同一形式であること。"""

    def test_to_legacy_format_excludes_abstract(self):
        """to_legacy_format() が abstract 科目を除外すること。"""

    def test_to_legacy_format_order_is_sequential(self):
        """to_legacy_format() の order が 1 始まりの連番であること。"""

    def test_repr_contains_role_and_count(self):
        """__repr__ が role_uri と concept 数を含むこと。"""


class TestConceptSetRegistry:
    """ConceptSetRegistry のメソッドテスト。"""

    def test_get_by_statement_type_and_industry(self):
        """業種コードと StatementType で ConceptSet を取得できること。"""

    def test_get_nonexistent_returns_none(self):
        """存在しない条件で None が返ること。"""

    def test_industries_returns_all_codes(self):
        """industries() が全業種コードを返すこと。"""

    def test_all_for_industry(self):
        """all_for_industry() が指定業種の全 ConceptSet を返すこと。"""

    def test_statement_categories(self):
        """statement_categories() が利用可能な StatementCategory を返すこと。"""


class TestPLVariantMerge:
    """PL バリアントファイルのマージテスト。"""

    def test_merged_concepts_superset(self):
        """マージ後の concept セットが各バリアントのスーパーセットであること。"""

    def test_main_file_order_priority(self):
        """メインファイルの concept order が優先されること。"""

    def test_depth_preserved_after_merge(self):
        """マージ後も depth が正しいこと。"""
```

### 4.3 テスト方針

- **Detroit 派**: モック不使用。実際の XML bytes をパースしてアサート
- **リファクタリング耐性**: 内部関数はテストしない。公開 API のみテスト
- **フィクスチャ自己完結**: 外部ファイル（タクソノミ等）への依存なし

### 4.4 推奨: 実データスモークテスト

```python
@pytest.mark.skipif(
    not os.environ.get("EDINET_TAXONOMY_ROOT"),
    reason="EDINET_TAXONOMY_ROOT が設定されていません"
)
class TestRealTaxonomy:
    """実タクソノミに対するスモークテスト（CI では skip）。"""

    def test_derive_from_jppfs(self):
        """jppfs の全 _pre ファイルから concept セットが導出できること。"""

    def test_bs_concepts_include_known_items(self):
        """BS の concept セットに既知の主要科目（CurrentAssets, Assets 等）が含まれること。"""

    def test_pl_concepts_include_known_items(self):
        """PL の concept セットに既知の主要科目（NetSales, OperatingIncome 等）が含まれること。"""

    def test_pl_variant_merge_produces_more_concepts(self):
        """PL バリアントマージ後に単体より concept 数が増えること。"""

    def test_legacy_format_covers_existing_json(self):
        """to_legacy_format() の concept 名が既存 JSON の concept を全てカバーすること。

        検証内容:
        1. PL: pl_jgaap.json の 16 concept が全て cns の PL ConceptSet に含まれること
        2. BS: bs_jgaap.json の 20 concept が全て cns の BS ConceptSet に含まれること
        3. CF: cf_jgaap.json の 8 concept が全て CF ConceptSet に含まれること
           （業種別から導出した場合も含む）
        Note: ConceptSet は JSON のスーパーセットであることが期待される。
        Note: PL は複数バリアントのマージ後にテストすること。
        """

    def test_all_industry_directories_parsed(self):
        """23 業種のディレクトリが全てパースできること（例外なし）。"""

    def test_cf_available_from_industry_specific(self):
        """業種別ディレクトリから CF concept セットが取得できること。"""
```

---

## 5. 実装手順

### Step 1: フィクスチャ作成

1. `tests/fixtures/concept_sets/` ディレクトリを作成
2. Wave 1 L1 のフィクスチャ XML 構造を参考に、concept_sets テスト用の XML を作成
3. role URI を実際の EDINET パターン（`http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_*`）に準拠させる

### Step 2: データモデル定義

1. `StatementCategory` enum を定義
2. `ConceptEntry` frozen dataclass を定義
3. `ConceptSet` frozen dataclass + メソッドを定義

### Step 3: role URI マッピング実装

1. `_ROLE_KEYWORDS` 辞書を定義
2. `classify_role_uri()` を実装
3. 半期/四半期/中間のプレフィックス除去ロジックを実装

### Step 4: PresentationTree → ConceptSet 変換実装

1. `_tree_to_concept_set()` を実装
2. `derive_concept_sets_from_trees()` を実装
3. `ConceptSet.to_legacy_format()` を実装

### Step 5: タクソノミディレクトリ走査実装

1. `_scan_taxonomy_directory()` を実装
2. PL バリアント検出・マージロジックを実装
3. `derive_concept_sets()` を実装

### Step 6: キャッシュ実装

1. `_cache_path()`, `_load_cache()`, `_save_cache()` を実装
2. 既存の `taxonomy/__init__.py` のキャッシュパターンを踏襲

### Step 7: 便利関数実装

1. `get_concept_set()` を実装（フィルタ付きの簡易アクセス）

### Step 8: テスト実行・修正

1. `uv run pytest tests/test_xbrl/test_concept_sets.py -v` で全テスト PASS を確認
2. `uv run pytest` で既存テスト含む全テスト PASS を確認
3. `uv run ruff check src/edinet/xbrl/taxonomy/concept_sets.py tests/test_xbrl/test_concept_sets.py` でリント PASS を確認

---

## 6. 注意点・設計判断

### 6.1 role URI マッピングの信頼性

role URI 文字列のキーワードマッチングはヒューリスティックであり、EDINET が role URI の命名規則を変更した場合に壊れる可能性がある。

**方針**: キーワードマッチングを主手段とし、マッチしない role URI は `warnings.warn()` で報告する。`classify_role_uri()` は `None` を返すため、利用者は未分類の role URI を安全に無視できる。将来的には `roleType` の `definition` 属性（日本語の財務諸表名）を用いた補助判定も検討するが、本 Lane のスコープ外。

### 6.2 CF の _pre 不在問題

一般事業会社(cns)に `_pre_cf.xml` が存在しないのは EDINET タクソノミの仕様。

**方針**:
1. 銀行業 (bk1) 等の業種別ディレクトリから CF の概念セットを取得
2. 一般事業会社が CF 概念セットを必要とする場合は、業種別から導出した概念セットを提供
3. 業種別 CF から一般事業会社用 CF を導出する際の業種固有 concept 除外:
   - ファイルパスから業種コードを判定し、導出元の業種を `source_info` に記録
   - CF の concept は `jppfs_cor` 名前空間で定義されるため基本的に業種横断で共通だが、業種固有 concept が混在する可能性がある（Z-2 [F6]）
   - 実装時に実際のデータを確認し、業種固有 concept が含まれる場合は除外パターンを定義する
   - 除外された concept の数を `warnings.warn()` で報告
4. 全業種に CF がない場合（想定外だが防御的に）、空の ConceptSet を返す

**根拠**: Z-2.3 より、業種別ディレクトリ（銀行業 bk1 等）には `_pre_cf.xml` が存在し、CF の概念は `jppfs_cor` 名前空間で定義されるため業種横断で共通。

### 6.3 order 値の扱い

Presentation Linkbase の `order` は兄弟ノード間の相対順序であり、**グローバルに一意ではない**。例えば BS の `CurrentAssets` (order=1) と PL の `NetSales` (order=1) は同じ order 値を持つ。

**方針**: `ConceptEntry.order` は元の Presentation Linkbase の `order` 値を保持する。`to_legacy_format()` では flatten 順序に基づく 1 始まりの連番に変換する。これにより現行 JSON との互換性を確保する。

### 6.4 depth の基準

`ConceptEntry.depth` は LineItems ノードからの相対深さ（0-based）を使用する。PresentationNode の `depth` はルートからの絶対値であるため、変換が必要。

**方針**: `line_items_node.depth` を基準深度とし、`entry.depth = node.depth - base_depth - 1` で計算する。`-1` は LineItems ノード自体を深さ 0 に含めないため。LineItems 直下の科目（`CurrentAssetsAbstract` 等）が depth=0 になる。

### 6.5 StatementCategory vs StatementType

既存の `StatementType` は PL/BS/CF のみだが、concept_sets では SS/CI も扱う必要がある。

**方針**: `StatementCategory` enum を concept_sets モジュール内で定義し、`to_statement_type()` メソッドで既存の `StatementType` に変換する。SS/CI は `None` を返す。将来 `StatementType` が拡張された際に統合可能。

### 6.6 提出者 _pre.xml の処理は対象外

本モジュールは**標準タクソノミの `_pre.xml`** のみを処理し、提出者の `_pre.xml` は対象外。提出者の _pre.xml からの概念セット導出は `display/statements`（Wave 3+）の責務。

**根拠**: 標準タクソノミの概念セットは「ある財務諸表に属する concept のマスターリスト」であり、提出者の _pre.xml はその拡張（追加科目・並び替え）に過ぎない。`statements.py` の `known_concepts` セットとして使うには標準タクソノミが適切。

### 6.7 業種コードの取得方法

タクソノミディレクトリの構造から業種コードを推定する:
- `taxonomy/jppfs/2025-11-01/r/cns/` → 一般事業会社 (`cns`)
- `taxonomy/jppfs/2025-11-01/r/bk1/` → 銀行業第一種 (`bk1`)
- `taxonomy/jppfs/2025-11-01/r/in1/` → 保険業第一種 (`in1`)

**方針**: `jppfs/.../r/` 配下のサブディレクトリ名をそのまま業種コードとして使用する（Z-2 [F3]）。全 23 業種が `r/` 配下に配置されている（P-6 [F7]）。業種コードの一覧は C-3 で定義されている。

### 6.8 同一 concept の複数 role 出現

同一 concept が複数の role URI に出現する場合がある（例: `NetSales` が PL と CI の両方に出現）。

**方針**: 各 role URI は独立した ConceptSet として扱う。同一 concept が複数の ConceptSet に属することは許容する。`statements.py` 統合時には `StatementCategory` でフィルタして使用する。

---

## 7. マイルストーン完了条件

1. `classify_role_uri()` が BS/PL/CF/SS/CI の連結・個別を正しく分類する
2. `classify_role_uri()` が `rol_std_*`（標準タクソノミ）と `rol_*`（提出者用）の両方に対応する
3. 半期/四半期/中間のプレフィックス付き role URI が正しく処理される
4. `derive_concept_sets_from_trees()` が PresentationTree から ConceptSet を導出できる
5. ConceptEntry の depth が LineItems からの相対深さである
6. dimension ノードが ConceptSet から除外されている
7. 合計行（`is_total`）と見出し行（`is_abstract`）が正しく識別される
8. PL バリアントファイルのマージ後に concept 数が増加する
9. `to_legacy_format()` が現行 JSON と同一形式を返す（abstract 除外後の 1 始まり連番）
10. `to_legacy_format()` の結果が既存の `pl_jgaap.json` / `bs_jgaap.json` の concept を全てカバーする
11. 非財務 role URI がフィルタリングされる
12. `derive_concept_sets()` が `ConceptSetRegistry` を返し、業種コードで O(1) 検索可能
13. `ConceptSetRegistry.get()` が `StatementType` + `consolidated` + `industry_code` で ConceptSet を返す
14. `StatementCategory.from_statement_type()` が正しく変換する
15. `derive_concept_sets()` がタクソノミディレクトリ（`r/{code}/` 構造）を走査して全業種をカバーする
16. pickle キャッシュが正常に動作する（保存・復元・バージョン不一致時の再構築）
17. テスト: 35+ テストケースが PASS
18. リント: ruff clean
19. 既存テスト: 全 PASS（破壊なし）

---

## 8. ファイル一覧

| 操作 | パス |
|------|------|
| 新規 | `src/edinet/xbrl/taxonomy/concept_sets.py` |
| 新規 | `tests/test_xbrl/test_concept_sets.py` |
| 新規 | `tests/fixtures/concept_sets/simple_bs_pre.xml` |
| 新規 | `tests/fixtures/concept_sets/simple_pl_pre.xml` |
| 新規 | `tests/fixtures/concept_sets/pl_main.xml` |
| 新規 | `tests/fixtures/concept_sets/pl_variant_sales.xml` |
| 新規 | `tests/fixtures/concept_sets/multi_statement.xml` |
| 新規 | `tests/fixtures/concept_sets/cf_pre.xml` |
| 新規 | `tests/fixtures/concept_sets/consolidated_and_nonconsolidated.xml` |
| 新規 | `tests/fixtures/concept_sets/non_financial_roles.xml` |
| 新規 | `tests/fixtures/concept_sets/empty_pre.xml` |

全て新規ファイル。既存ファイルの変更なし。

---

## 9. QA 参照

| QA ID | タイトル | 本 Lane での利用 |
|-------|---------|-----------------|
| Z-2 | 科目定義 JSON の自動生成可能性 | 本 Lane の最重要根拠。PL バリアント分割、CF の _pre 不在、23 業種同一構造の仕様確認 |
| I-1 | Role URI と財務諸表の対応 | role URI → StatementCategory マッピングの完全リスト |
| I-2 | Presentation ツリーの構造 | LineItems 以下の科目ツリー構造、depth 計算の根拠 |
| I-3 | 提出者による Presentation のカスタマイズ | リキャスト方式。標準タクソノミのみパースすれば概念セットが定義できる根拠 |
| C-6 | プレゼンテーションリンクベースの詳細構造 | role URI, order, preferredLabel の仕様 |
| C-3 | 業種カテゴリコードの一覧 | 23 業種のコード一覧 |
| E-1 | 財務諸表の種類と識別 | role URI による諸表分類が唯一の信頼できる手段である根拠 |
| E-5 | 業種別の財務諸表の差異 | 銀行・保険・証券の PL 構造差異 |
| D-3 | 会計基準の判別方法 | J-GAAP / IFRS / US-GAAP の判別（concept_sets は J-GAAP 対象） |

---

## 10. Wave 3 への接続点

本モジュールは以下の形で Wave 3 に接続する:

### Wave 3 L1 (`standards/normalize + statements.py 統合`)

`statements.py` の `_load_concept_definitions()` を以下のように置換:

```python
# Before (v0.1.0):
concept_defs = _load_concept_definitions(StatementType.INCOME_STATEMENT)
# → JSON ファイルを読み込み

# After (v0.2.0):
from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets
registry = derive_concept_sets(taxonomy_path)
concept_set = registry.get(StatementType.INCOME_STATEMENT, consolidated=True)
concept_defs = concept_set.to_legacy_format()
# → タクソノミから自動導出 + レジストリ検索 + レガシー形式変換

# あるいはショートカット:
from edinet.xbrl.taxonomy.concept_sets import get_concept_set
concept_set = get_concept_set(taxonomy_path, StatementType.INCOME_STATEMENT)
concept_defs = concept_set.to_legacy_format()
```

この段階的移行により:
1. `statements.py` の変更量を最小限に抑えられる
2. `to_legacy_format()` の互換性テストが安全弁として機能する
3. 将来的には `ConceptSet` を直接参照する形に移行可能

### BUG-6 の解決

concept_sets による role URI ベースの諸表分類により、`DurationPeriod` で PL/CF/SS を区別できない問題が根本解決される:
- PL の ConceptSet には PL の role URI に属する concept のみが含まれる
- CF の ConceptSet には CF の role URI に属する concept のみが含まれる
- SS の ConceptSet には SS の role URI に属する concept のみが含まれる

`statements.py` の `_build_single_statement()` で `known_concepts` フィルタにこの ConceptSet を使用すれば、cross-contamination は発生しない。

---

## 11. 変更ログ（フィードバック反映）

### 第2ラウンド（フィードバック WAVE_2_LANE_1_FEEDBACK.md 反映）

| 変更ID | 対応FB | 変更箇所 | 変更内容 |
|--------|--------|----------|----------|
| CHG-01 | **C-1** | §3.1 公開API | `derive_concept_sets()` の返り値を `dict[StatementCategory, list[ConceptSet]]` から `ConceptSetRegistry` に変更。`ConceptSetRegistry` クラスを新規追加（`get()`, `all_for_industry()`, `industries()`, `statement_categories()` メソッド）。`get_concept_set()` を `ConceptSetRegistry.get()` のショートカットに変更 |
| CHG-02 | **C-2** | §2.1項目2, §3.1 classify_role_uri, §3.2 Step1 | `rol_std_*` パターンへの対応を追加。`classify_role_uri()` で `std_` プレフィックスを除去してからマッチングする処理を明記。`_ROLE_PATTERNS` のキーを `"rol_ConsolidatedBalanceSheet"` から `"ConsolidatedBalanceSheet"` に変更 |
| CHG-03 | **H-1** | §2.1項目4, §3.1 ConceptEntry, §3.2 Step2 | `is_abstract` を `PresentationNode.is_abstract` の転写に限定。実装が `Abstract`/`Heading` 両方を判定済みであることを明記（stubs の docstring が不正確だったが実装は正しい）。`Heading` に関する独自判定ロジックは不要 |
| CHG-04 | **H-2** | §3.2 Step3 | ディレクトリ構造を実態（`jppfs/.../r/{業種コード}/`）に修正。走査ロジックを `taxonomy_path / "taxonomy" / "jppfs" / "*" / "r"` 配下のサブディレクトリ走査に変更。ファイル名パターンを明記 |
| CHG-05 | **H-3** | §6.2 | CF 対応方針に業種固有 concept 除外の方針を追加。除外された concept 数の `warnings.warn()` 報告を明記 |
| CHG-06 | **H-4** | §3.1 to_legacy_format docstring | abstract 除外後の flatten 順で 1 から付番する連番方式を明確化。実装イメージコードを追加 |
| CHG-07 | **H-5** | §3.2 Step2 | `flatten()` ベースのフィルタリングから `line_items_roots()` 起点の独自深さ優先走査に変更。理由: LineItems 外のノード混入リスクの回避 |
| CHG-08 | **M-1** | §3.1 StatementCategory | `from_statement_type()` classmethod を追加 |
| CHG-09 | **M-2** | §3.2 Step5 | pickle キャッシュのセキュリティ注記を追加 |
| CHG-10 | **M-4** | §4.2 TestClassifyRoleUri | `test_std_prefix_bs`, `test_std_prefix_pl`, `test_std_prefix_cf` テストケースを追加 |
| CHG-11 | **M-6** | §4.4 test_legacy_format_covers_existing_json | テストの検証内容を詳細化（PL 16概念、BS 20概念、CF 8概念の個別検証） |
| CHG-12 | — | §4.2 | `TestConceptSetRegistry` テストクラスを追加（5テストケース） |
| CHG-13 | — | §6.7 | 業種コード取得方法を `r/` 配下のサブディレクトリに修正 |
| CHG-14 | — | §7 | マイルストーン完了条件を更新（`rol_std_*` 対応、`ConceptSetRegistry`、`from_statement_type()`、テスト数 35+ に増加） |
| CHG-15 | — | §10 | Wave 3 接続点のコード例を `ConceptSetRegistry` ベースに更新 |

### フィードバックの却下・変更判断

| FB ID | 判断 | 理由 |
|-------|------|------|
| **H-1** | 推奨案Aを採用するが、根拠を修正 | フィードバックは「stubs で Heading 非対応」と主張したが、実装 (`presentation.py` L472) では `concept.endswith("Heading")` も判定済み。stubs の docstring が不正確なだけ。結論（案A: 転写で十分）は正しいが、理由が異なる |
| **H-3** | 方針を明記するが、具体的なサフィックスパターン(`/[A-Z]{2,3}$/`)は不採用 | 業種固有 concept が concept 名のサフィックスで区別されるかは未検証。実装時に実データを確認してから除外ロジックを決定する方が安全 |
| **M-3** | 計画変更なし | フィードバック自体が「計画変更不要」と判定済み |
| **M-5** | 計画変更なし | フィードバック自体が「計画変更の必要性は低い」と判定済み |
| **L-1〜L-4** | 計画変更なし | 全て「計画変更不要」と判定済み。L-4（prefix リストの完全性）は実装時に実データで確認する |

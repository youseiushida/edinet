# Wave 2 / Lane 5 — standards/usgaap: 米国基準の科目マッピングと要約指標抽出

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 2 / Lane 5 を担当するエージェントです。
担当機能: standards_usgaap

### 絶対禁止事項

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
   - `src/edinet/xbrl/standards/usgaap.py` (新規)
   - `tests/test_xbrl/test_standards_usgaap.py` (新規)
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

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.financial.standards.usgaap import extract_usgaap_summary` （OK）
   - 例: `from edinet.xbrl import extract_usgaap_summary` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_standards_usgaap.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - Wave 1 で完成したモジュールは import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.dei` (DEI, AccountingStandard, PeriodType, extract_dei)
     - `edinet.xbrl._namespaces` (NS_* 定数, classify_namespace, NamespaceInfo, NamespaceCategory 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning 等)
   - **他の Wave 2 レーンが作成中のモジュール**（concept_sets, detect, jgaap, ifrs）に依存してはならない

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 5 — standards/usgaap: 米国基準の科目マッピングと要約指標抽出

## 0. 位置づけ

Wave 2 Lane 5 は、FEATURES.md の **Accounting Standard Normalization > standards/usgaap** に対応する。US-GAAP 適用企業の XBRL インスタンスから、**利用可能な構造化データを最大限抽出する**モジュールを新規実装する。

FEATURES.md の定義:

> - standards/usgaap: 米国基準の科目マッピング [TODO]
>   - depends: facts, namespaces

FUTUREPLAN.tmp.md での位置:

> Phase 3-5: `standards/usgaap` → namespaces 依存

### 本 Lane の特殊性

US-GAAP は J-GAAP・IFRS と**根本的に異なるデータ構造**を持つ。D-2.a.md の調査結果より:

| 特性 | J-GAAP | IFRS | US-GAAP |
|------|--------|------|---------|
| タグ付け方式 | 詳細タグ付け | 詳細タグ付け | **包括タグ付け** |
| 専用タクソノミ | `jppfs_cor` | `jpigp_cor` | **なし**（`jpcrp_cor` 内） |
| 財務諸表の個別科目 | あり | あり | **なし**（HTML TextBlock） |
| 要素数 | 数千 | 数百 | **37 のみ** |
| PL/BS/CF 構造化 | 可能 | 可能 | **不可能** |

したがって `standards/jgaap`（L3）や `standards/ifrs`（L4）が「concept マッピング → 財務諸表構築」を担当するのに対し、本 Lane は:

1. **SummaryOfBusinessResults 要素の構造化抽出**（売上高・営業利益・総資産等の主要経営指標 19 科目）
2. **TextBlock 要素の識別と分類**（連結BS/PL/CF 等の HTML ブロック 14 個）
3. **US-GAAP 企業であることを明示する診断情報の提供**

を行う。詳細な PL/BS/CF の構造化パースは**スコープ外**（包括タグ付けのみのため不可能）。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.parser.RawFact` | 入力データ型 | read-only |
| `edinet.xbrl._namespaces` | `classify_namespace()`, `NamespaceInfo` | read-only |
| `edinet.xbrl.dei` | `AccountingStandard.US_GAAP` 定数の参照 | read-only |
| `edinet.exceptions` | `EdinetWarning` | read-only |

他レーンとのファイル衝突なし（新規ファイルのみ作成）。

### QA 参照

| QA | タイトル | 関連度 |
|----|---------|--------|
| D-2 | US-GAAP 適用企業の XBRL | **直接（設計の基盤）** — 37 要素の詳細分類、包括タグ付けのみの仕様確認 |
| D-3 | 会計基準の判別方法 | 直接（US-GAAP の名前空間判別不可能性） |
| D-1 | IFRS 適用企業の XBRL | 参考（IFRS との対比） |
| A-1 | 名前空間宣言の全体像 | 関連（`jpcrp_cor` 名前空間パターン） |
| E-7 | 主要勘定科目の concept 名辞書 | 関連（J-GAAP 科目との対応付け参考） |
| F-1 | DEI 要素の一覧 | 関連（AccountingStandardsDEI = "US GAAP"） |

---

## 1. 背景知識（QA サマリー）

### 1.1 US-GAAP の XBRL 構造（D-2.a.md）

EDINET における US-GAAP 企業の XBRL は **包括タグ付け（block tagging）** のみ。

**37 要素の内訳**（全て `jpcrp_cor` 名前空間）:

| 種別 | 件数 | 用途 | データ型 |
|------|------|------|----------|
| TextBlock | 14 | 財務諸表の HTML ブロック（包括タグ付け） | `textBlockItemType` |
| SummaryOfBusinessResults | 19 | 主要な経営指標等の推移 | `monetaryItemType`, `perShareItemType`, `percentItemType`, `decimalItemType` |
| Abstract | 3 | 見出し要素 | `stringItemType` |
| Description | 1 | 米国基準適用の説明文 | `stringItemType` |

### 1.2 SummaryOfBusinessResults 要素（D-2.a.md [F4], [F9]）

売上高・営業利益・総資産等の主要経営指標を個別に格納する要素。US-GAAP 企業から抽出可能な**唯一の構造化数値データ**。

これらは有報の「主要な経営指標等の推移」セクションに対応し、J-GAAP 企業の同セクションと同等の情報量を持つ。jquants 等で提供されるサマリーデータの原典。

**概念名と日本語ラベル（2025-11-01 タクソノミ XSD + ラベルファイルで直接検証済み）**:

| concept ローカル名 | ラベル | データ型 |
|-------------------|--------|----------|
| `RevenuesUSGAAPSummaryOfBusinessResults` | 売上高 | monetary |
| `OperatingIncomeLossUSGAAPSummaryOfBusinessResults` | 営業利益又は営業損失（△） | monetary |
| `ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults` | 税引前利益又は税引前損失（△） | monetary |
| `NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults` | 当社株主に帰属する純利益又は純損失（△） | monetary |
| `ComprehensiveIncomeUSGAAPSummaryOfBusinessResults` | 包括利益 | monetary |
| `ComprehensiveIncomeAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults` | 当社株主に帰属する包括利益 | monetary |
| `EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults` | 株主資本 | monetary |
| `EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults` | 純資産額 | monetary |
| `TotalAssetsUSGAAPSummaryOfBusinessResults` | 総資産額 | monetary |
| `EquityToAssetRatioUSGAAPSummaryOfBusinessResults` | 自己資本比率 | percent |
| `RateOfReturnOnEquityUSGAAPSummaryOfBusinessResults` | 株主資本利益率 | percent |
| `PriceEarningsRatioUSGAAPSummaryOfBusinessResults` | 株価収益率 | decimal |
| `CashFlowsFromUsedInOperatingActivitiesUSGAAPSummaryOfBusinessResults` | 営業活動によるキャッシュ・フロー | monetary |
| `CashFlowsFromUsedInInvestingActivitiesUSGAAPSummaryOfBusinessResults` | 投資活動によるキャッシュ・フロー | monetary |
| `CashFlowsFromUsedInFinancingActivitiesUSGAAPSummaryOfBusinessResults` | 財務活動によるキャッシュ・フロー | monetary |
| `CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults` | 現金及び現金同等物 | monetary |
| `BasicEarningsLossPerShareUSGAAPSummaryOfBusinessResults` | 基本的１株当たり当社株主に帰属する利益又は損失（△） | perShare |
| `DilutedEarningsLossPerShareUSGAAPSummaryOfBusinessResults` | 希薄化後１株当たり当社株主に帰属する利益又は損失（△） | perShare |
| `EquityAttributableToOwnersOfParentPerShareUSGAAPSummaryOfBusinessResults` | １株当たり株主資本 | perShare |

**残り 1 要素（説明文）**:
| concept ローカル名 | ラベル | データ型 |
|-------------------|--------|----------|
| `DescriptionOfFactThatConsolidatedFinancialStatementsHaveBeenPreparedInAccordanceWithUSGAAPFinancialInformation` | 連結財務諸表が米国基準に基づき作成されている旨の説明 | string |

### 1.3 TextBlock 要素（D-2.a.md [F3]、2025-11-01 タクソノミ XSD で直接検証済み）

財務諸表全体を HTML ブロックとして格納する 14 要素。個別勘定科目のタグ付けは行われない。
**全て連結**（個別の TextBlock は存在しない）。年次・半期の 2 バリアントがある。

**TextBlock 全 14 要素**:

| # | concept ローカル名 | 種別 |
|---|-------------------|------|
| 1 | `ConsolidatedBalanceSheetUSGAAPTextBlock` | 連結 BS（年次） |
| 2 | `ConsolidatedStatementOfIncomeUSGAAPTextBlock` | 連結 PL（年次） |
| 3 | `ConsolidatedStatementOfCashFlowsUSGAAPTextBlock` | 連結 CF（年次） |
| 4 | `ConsolidatedStatementOfEquityUSGAAPTextBlock` | 連結 SS（年次） |
| 5 | `ConsolidatedStatementOfComprehensiveIncomeUSGAAPTextBlock` | 連結 CI（年次） |
| 6 | `ConsolidatedStatementOfComprehensiveIncomeSingleStatementUSGAAPTextBlock` | 連結 CI 一計算書方式（年次） |
| 7 | `NotesToConsolidatedFinancialStatementsUSGAAPTextBlock` | 連結注記（年次） |
| 8 | `SemiAnnualConsolidatedBalanceSheetUSGAAPTextBlock` | 連結 BS（半期） |
| 9 | `SemiAnnualConsolidatedStatementOfIncomeUSGAAPTextBlock` | 連結 PL（半期） |
| 10 | `SemiAnnualConsolidatedStatementOfCashFlowsUSGAAPTextBlock` | 連結 CF（半期） |
| 11 | `SemiAnnualConsolidatedStatementOfComprehensiveIncomeUSGAAPTextBlock` | 連結 CI（半期） |
| 12 | `SemiAnnualConsolidatedStatementOfComprehensiveIncomeSingleStatementUSGAAPTextBlock` | 連結 CI 一計算書方式（半期） |
| 13 | `ConsolidatedSemiAnnualStatementOfEquityUSGAAPTextBlock` | 連結 SS（半期） |
| 14 | `NotesToSemiAnnualConsolidatedFinancialStatementsUSGAAPTextBlock` | 連結注記（半期） |

### 1.4 企業数と動向（D-2.a.md 推論 7）

- 歴史的に 10〜15 社程度（外資系企業子会社が中心）
- 近年は IFRS への移行が進み減少傾向
- 全上場企業に対する比率は極めて小さい

### 1.5 JMIS（修正国際基準）との類似性（D-2.a.md 補足）

JMIS も US-GAAP と同じパターン（TextBlock + SummaryOfBusinessResults、包括タグ付けのみ）。40 要素が確認されている。本 Lane で構築するアーキテクチャは JMIS にもそのまま適用可能。ただし JMIS は本 Lane のスコープ外とし、将来の `standards/jmis.py` で同様のパターンで対応する。

---

## 2. ゴール

### 2.1 機能要件

1. **SummaryOfBusinessResults の構造化抽出**
   - US-GAAP 企業の RawFact タプルから、SummaryOfBusinessResults 要素を抽出し、正規化キー付きの構造化データとして返す
   - 正規化キー（例: `"revenue"`, `"operating_income"`, `"total_assets"`）により、会計基準横断での比較を容易にする
   - 当期/前期の複数期間データを期間ごとに整理する

2. **TextBlock の識別と分類**
   - 14 個の US-GAAP TextBlock 要素を財務諸表種別（BS/PL/CF/SS/CI）で分類する
   - HTML 内容をそのまま保持する（テキスト抽出は `text_blocks/clean`（FEATURES.md）の責務）
   - 連結/個別の区分を付与する

3. **US-GAAP 企業の診断情報**
   - 発見された US-GAAP 要素数、SummaryOfBusinessResults 要素数、TextBlock 要素数を報告する
   - 「構造化パースは不可能（包括タグ付けのみ）」という明示的な情報を提供する

4. **正規化キー → J-GAAP concept の対応テーブル**
   - SummaryOfBusinessResults の各要素を J-GAAP の主要科目にマッピングする辞書を提供する
   - Wave 3 の `standards/normalize` が US-GAAP ↔ J-GAAP の横断比較に使用する

5. **JMIS 拡張ポイントの確保**
   - `_USGAAP_SUMMARY_CONCEPTS` のようなデータ構造を JMIS でも同パターンで再利用できる設計にする
   - ただし JMIS の実装自体は本 Lane のスコープ外

### 2.2 非ゴール（スコープ外）

- 詳細な PL/BS/CF の構造化パース → 包括タグ付けのため不可能
- TextBlock 内の HTML パース・テキスト抽出 → `text_blocks` モジュール（FEATURES.md Phase 7）の責務
- US-GAAP 企業の判別 → Wave 2 L2 (standards/detect) の責務
- `FinancialStatement` オブジェクトの生成 → 構造化データがないため不適切。代わりに専用の `USGAAPSummary` を返す
- JMIS 要素の実装 → 将来の `standards/jmis.py` で対応

---

## 3. データモデル設計

### 3.1 USGAAPSummaryItem: 要約指標の 1 項目

```python
from dataclasses import dataclass
from decimal import Decimal
from edinet.xbrl.contexts import Period

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
            ``jpcrp_cor`` のラベルファイルから取得。
            取得できない場合は concept 名をフォールバック。
        value: 値。数値の場合は ``Decimal``、テキストの場合は ``str``、
            nil の場合は ``None``。
        unit_ref: unitRef 属性値。
        period: 対応する期間情報。
        context_id: contextRef 属性値。
    """
    key: str
    concept: str
    label_ja: str
    value: Decimal | str | None
    unit_ref: str | None
    period: Period
    context_id: str
```

### 3.2 USGAAPTextBlockItem: TextBlock の 1 項目

```python
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
```

### 3.3 USGAAPSummary: US-GAAP 企業のデータ全体

```python
@dataclass(frozen=True, slots=True)
class USGAAPSummary:
    """US-GAAP 企業から抽出した全構造化データ。

    US-GAAP 企業の XBRL は包括タグ付けのみであり、J-GAAP のような
    詳細な PL/BS/CF の構造化パースは不可能。代わりに
    SummaryOfBusinessResults 要素と TextBlock 要素を構造的に提供する。

    Attributes:
        summary_items: SummaryOfBusinessResults 要素のタプル。
            主要な経営指標（売上高・営業利益・総資産等）。
            期間ごとに整理済み。
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
        「最新」は ``_period_sort_key()`` による日付降順で決定する
        （DurationPeriod は end_date、InstantPeriod は instant）。

        Args:
            key: 正規化キー（例: ``"revenue"``, ``"total_assets"``）。

        Returns:
            合致する項目。見つからない場合は None。
        """

    def get_items_by_period(
        self, period: Period,
    ) -> tuple[USGAAPSummaryItem, ...]:
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

    def __repr__(self) -> str:
        """REPL 向けの簡潔な表現。"""
        return (
            f"USGAAPSummary(summary_items={len(self.summary_items)}, "
            f"text_blocks={len(self.text_blocks)}, "
            f"total_elements={self.total_usgaap_elements})"
        )
```

### 3.4 正規化キーの定義

US-GAAP SummaryOfBusinessResults 要素を会計基準横断で比較可能にする正規化キー。

**正規化キーは L3（jgaap）/ L4（ifrs）と統一する**。L3/L4 で使用されるキー体系:
- 単数形・スネークケース（例: `revenue`, `operating_income`）
- CF 系は `operating_cf`, `investing_cf`, `financing_cf`
- KPI 系は `eps`, `eps_diluted`, `bps`, `roe`, `equity_ratio`, `per`

```python
@dataclass(frozen=True, slots=True)
class _SummaryConceptDef:
    """SummaryOfBusinessResults 要素の定義。

    Attributes:
        key: 正規化キー（L3/L4 と統一）。
        concept_local_name: XBRL concept の完全なローカル名。
            例: ``"RevenuesUSGAAPSummaryOfBusinessResults"``。
        jgaap_concept: 対応する J-GAAP の concept ローカル名。None は対応なし。
        label_ja: 日本語ラベル（jpcrp_cor ラベルファイルで検証済み）。
    """
    key: str
    concept_local_name: str
    jgaap_concept: str | None
    label_ja: str


_USGAAP_SUMMARY_CONCEPTS: tuple[_SummaryConceptDef, ...] = (
    # --- PL 系 ---
    _SummaryConceptDef("revenue", "RevenuesUSGAAPSummaryOfBusinessResults", "NetSales", "売上高"),
    _SummaryConceptDef("operating_income", "OperatingIncomeLossUSGAAPSummaryOfBusinessResults", "OperatingIncome", "営業利益又は営業損失（△）"),
    _SummaryConceptDef("income_before_tax", "ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults", "IncomeBeforeIncomeTaxes", "税引前利益又は税引前損失（△）"),
    _SummaryConceptDef("net_income_parent", "NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults", "ProfitLossAttributableToOwnersOfParent", "当社株主に帰属する純利益又は純損失（△）"),
    _SummaryConceptDef("comprehensive_income", "ComprehensiveIncomeUSGAAPSummaryOfBusinessResults", "ComprehensiveIncome", "包括利益"),
    _SummaryConceptDef("comprehensive_income_parent", "ComprehensiveIncomeAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults", "ComprehensiveIncomeAttributableToOwnersOfParent", "当社株主に帰属する包括利益"),
    # --- BS 系 ---
    _SummaryConceptDef("shareholders_equity", "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults", None, "株主資本"),
    _SummaryConceptDef("net_assets", "EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults", "NetAssets", "純資産額"),
    _SummaryConceptDef("total_assets", "TotalAssetsUSGAAPSummaryOfBusinessResults", "Assets", "総資産額"),
    # --- 比率 ---
    _SummaryConceptDef("equity_ratio", "EquityToAssetRatioUSGAAPSummaryOfBusinessResults", None, "自己資本比率"),
    _SummaryConceptDef("roe", "RateOfReturnOnEquityUSGAAPSummaryOfBusinessResults", None, "株主資本利益率"),
    _SummaryConceptDef("per", "PriceEarningsRatioUSGAAPSummaryOfBusinessResults", None, "株価収益率"),
    # --- CF 系 ---
    _SummaryConceptDef("operating_cf", "CashFlowsFromUsedInOperatingActivitiesUSGAAPSummaryOfBusinessResults", "NetCashProvidedByUsedInOperatingActivities", "営業活動によるキャッシュ・フロー"),
    _SummaryConceptDef("investing_cf", "CashFlowsFromUsedInInvestingActivitiesUSGAAPSummaryOfBusinessResults", "NetCashProvidedByUsedInInvestingActivities", "投資活動によるキャッシュ・フロー"),
    _SummaryConceptDef("financing_cf", "CashFlowsFromUsedInFinancingActivitiesUSGAAPSummaryOfBusinessResults", "NetCashProvidedByUsedInFinancingActivities", "財務活動によるキャッシュ・フロー"),
    _SummaryConceptDef("cash_end", "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults", "CashAndCashEquivalents", "現金及び現金同等物"),
    # --- 1株当たり ---
    _SummaryConceptDef("eps", "BasicEarningsLossPerShareUSGAAPSummaryOfBusinessResults", None, "基本的１株当たり当社株主に帰属する利益又は損失（△）"),
    _SummaryConceptDef("eps_diluted", "DilutedEarningsLossPerShareUSGAAPSummaryOfBusinessResults", None, "希薄化後１株当たり当社株主に帰属する利益又は損失（△）"),
    _SummaryConceptDef("bps", "EquityAttributableToOwnersOfParentPerShareUSGAAPSummaryOfBusinessResults", None, "１株当たり株主資本"),
)
```

**設計判断**: `concept_local_name` に XBRL concept の完全なローカル名を保持する（フィードバック T-2 対応）。`concept_suffix` + 構築ロジックの方式は JMIS でサフィックスパターンが異なる場合に再利用できないため、完全名方式を採用。JMIS 対応時は `_SummaryConceptDef("revenue", "RevenuesJMISSummaryOfBusinessResults", "NetSales")` のように同じ dataclass をそのまま使用可能。

### 3.5 TextBlock の分類定義

US-GAAP TextBlock は**全て連結**（個別の TextBlock は存在しない）。年次と半期の 2 バリアントがある。

```python
_TEXTBLOCK_STATEMENT_MAP: dict[str, tuple[str, bool]] = {
    # (概念名に含まれるキーワード, (statement_hint, is_semi_annual))
    # 年次（ConsolidatedXxxUSGAAPTextBlock）
    "ConsolidatedBalanceSheet": ("balance_sheet", False),
    "ConsolidatedStatementOfIncome": ("income_statement", False),
    "ConsolidatedStatementOfCashFlows": ("cash_flow_statement", False),
    "ConsolidatedStatementOfEquity": ("statement_of_changes_in_equity", False),
    "ConsolidatedStatementOfComprehensiveIncomeSingleStatement": ("comprehensive_income_single", False),
    "ConsolidatedStatementOfComprehensiveIncome": ("comprehensive_income", False),
    "NotesToConsolidatedFinancialStatements": ("notes", False),
    # 半期（SemiAnnualConsolidatedXxxUSGAAPTextBlock）
    "SemiAnnualConsolidatedBalanceSheet": ("balance_sheet", True),
    "SemiAnnualConsolidatedStatementOfIncome": ("income_statement", True),
    "SemiAnnualConsolidatedStatementOfCashFlows": ("cash_flow_statement", True),
    "SemiAnnualConsolidatedStatementOfComprehensiveIncomeSingleStatement": ("comprehensive_income_single", True),
    "SemiAnnualConsolidatedStatementOfComprehensiveIncome": ("comprehensive_income", True),
    "ConsolidatedSemiAnnualStatementOfEquity": ("statement_of_changes_in_equity", True),
    "NotesToSemiAnnualConsolidatedFinancialStatements": ("notes", True),
}
```

TextBlock の concept 名に含まれるキーワードで財務諸表の種類を推定する。最長一致で判定する（`ConsolidatedStatementOfComprehensiveIncomeSingleStatement` が `ConsolidatedStatementOfComprehensiveIncome` より優先）。

**注**: US-GAAP TextBlock は全て連結のため、旧来の `is_consolidated` フィールドは廃止し、代わりに `is_semi_annual: bool` フィールドを持つ（§3.2 参照）。

---

## 4. 公開 API

### 4.0 `__all__` の定義

```python
__all__ = [
    "USGAAPSummary",
    "USGAAPSummaryItem",
    "USGAAPTextBlockItem",
    "extract_usgaap_summary",
    "is_usgaap_element",
    "get_jgaap_mapping",
    "get_usgaap_concept_names",
]
```

### 4.1 `extract_usgaap_summary()`

```python
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
            期間情報は StructuredContext から取得する。

    Returns:
        USGAAPSummary。US-GAAP 要素が存在しない場合は
        空のタプルを持つ USGAAPSummary。
    """
```

### 4.2 `is_usgaap_element()`

```python
def is_usgaap_element(local_name: str) -> bool:
    """concept のローカル名が US-GAAP 関連要素かどうかを判定する。

    ``"USGAAP"`` を名前に含む jpcrp_cor 要素を US-GAAP 要素として判定する。

    Args:
        local_name: concept のローカル名。

    Returns:
        US-GAAP 関連要素であれば True。
    """
```

### 4.3 `get_jgaap_mapping()`

```python
def get_jgaap_mapping() -> dict[str, str | None]:
    """US-GAAP SummaryOfBusinessResults 正規化キー → J-GAAP concept の対応辞書を返す。

    Wave 3 の standards/normalize が US-GAAP ↔ J-GAAP の横断比較に使用する。

    Returns:
        ``{正規化キー: J-GAAP concept ローカル名}`` の辞書。
        対応する J-GAAP 科目がない場合の値は None。

    Example:
        >>> mapping = get_jgaap_mapping()
        >>> mapping["revenue"]
        'NetSales'
        >>> mapping["per"]  # 株価収益率は J-GAAP 側に直接の対応科目なし
        None
    """
```

### 4.4 `get_usgaap_concept_names()`

```python
def get_usgaap_concept_names() -> frozenset[str]:
    """US-GAAP SummaryOfBusinessResults の全 concept ローカル名を返す。

    SummaryOfBusinessResults 要素の完全な concept 名
    （``"RevenuesUSGAAPSummaryOfBusinessResults"`` 等）の
    フローズンセット。

    TextBlock 要素と Abstract 要素は含まない。

    Returns:
        concept ローカル名のフローズンセット。
    """
```

---

## 5. 内部アルゴリズム

### 5.1 メインフロー（extract_usgaap_summary）

```python
def extract_usgaap_summary(
    facts: tuple[RawFact, ...],
    contexts: dict[str, StructuredContext],
) -> USGAAPSummary:
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
```

### 5.2 SummaryOfBusinessResults 抽出ロジック

```python
def _extract_summary_items(
    usgaap_facts: list[RawFact],
    contexts: dict[str, StructuredContext],
) -> list[USGAAPSummaryItem]:
    # concept ローカル名 → _SummaryConceptDef のルックアップテーブルを構築
    concept_lookup: dict[str, _SummaryConceptDef] = {
        d.concept_local_name: d
        for d in _USGAAP_SUMMARY_CONCEPTS
    }

    items = []
    for fact in usgaap_facts:
        defn = concept_lookup.get(fact.local_name)
        if defn is None:
            continue  # SummaryOfBusinessResults でない US-GAAP 要素

        period = _resolve_period(fact.context_ref, contexts)
        if period is None:
            continue  # context_ref が見つからない場合はスキップ（警告は _resolve_period 内で発出）
        value = _parse_value(fact)

        items.append(USGAAPSummaryItem(
            key=defn.key,
            concept=fact.local_name,
            label_ja=defn.label_ja,
            value=value,
            unit_ref=fact.unit_ref,
            period=period,
            context_id=fact.context_ref,
        ))

    return items
```

### 5.3 TextBlock 抽出ロジック

```python
def _extract_text_blocks(
    usgaap_facts: list[RawFact],
    contexts: dict[str, StructuredContext],
) -> list[USGAAPTextBlockItem]:
    items = []
    for fact in usgaap_facts:
        if "TextBlock" not in fact.local_name:
            continue

        statement_hint, is_semi_annual = _classify_text_block(fact.local_name)
        period = _resolve_period(fact.context_ref, contexts)
        if period is None:
            continue  # context_ref が見つからない場合はスキップ

        items.append(USGAAPTextBlockItem(
            concept=fact.local_name,
            statement_hint=statement_hint,
            is_semi_annual=is_semi_annual,
            html_content=fact.value_raw,
            period=period,
            context_id=fact.context_ref,
        ))

    return items
```

### 5.4 TextBlock 分類ロジック

```python
def _classify_text_block(
    local_name: str,
) -> tuple[str | None, bool]:
    """TextBlock の概念名から財務諸表種別と半期フラグを推定する。

    最長一致でキーワードをマッチさせ、最も具体的な分類を返す。
    US-GAAP TextBlock は全て連結のため is_consolidated は不要。
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
```

### 5.5 説明文抽出ロジック（U-2 対応で追記）

```python
_DESCRIPTION_CONCEPT = (
    "DescriptionOfFactThatConsolidatedFinancialStatements"
    "HaveBeenPreparedInAccordanceWithUSGAAPFinancialInformation"
)

def _extract_description(usgaap_facts: list[RawFact]) -> str | None:
    """米国基準適用の説明文を抽出する。

    同一 concept の fact が複数存在する場合は最初に見つかったものを返す。
    複数期間の fact が混在する場合も文書順（RawFact.order）で最初の値を採用する。
    """
    for fact in usgaap_facts:
        if fact.local_name == _DESCRIPTION_CONCEPT and fact.value_raw:
            return fact.value_raw
    return None
```

### 5.6 値のパース

```python
def _parse_value(fact: RawFact) -> Decimal | str | None:
    """RawFact の値をパースする。

    数値として解釈可能なら Decimal、不可能なら str、nil なら None。
    数値が期待される fact（unit_ref が存在する）が Decimal に変換できない場合は
    EdinetWarning を発出する（T-8 対応）。
    """
    if fact.is_nil:
        return None
    if fact.value_raw is None:
        return None

    try:
        return Decimal(fact.value_raw)
    except Exception:
        if fact.unit_ref is not None:
            # unit_ref があるのに数値変換できない → 異常値の可能性
            warnings.warn(
                f"数値が期待される fact '{fact.local_name}' の値 "
                f"'{fact.value_raw[:50]}' を Decimal に変換できません。",
                EdinetWarning,
                stacklevel=2,
            )
        return fact.value_raw
```

### 5.7 期間の解決

```python
def _resolve_period(
    context_ref: str,
    contexts: dict[str, StructuredContext],
) -> Period | None:
    """contextRef から期間情報を解決する。

    contexts 辞書から StructuredContext を取得し、その period を返す。
    context_ref が見つからない場合は EdinetWarning を発出し None を返す。
    呼び出し元は None の場合に当該 fact をスキップする。

    Args:
        context_ref: RawFact の contextRef 属性値。
        contexts: structure_contexts() の戻り値。

    Returns:
        Period。context_ref が見つからない場合は None。
    """
    ctx = contexts.get(context_ref)
    if ctx is not None:
        return ctx.period
    # contexts に見つからない → 警告してスキップ
    warnings.warn(
        f"contextRef '{context_ref}' が contexts 辞書に見つかりません。"
        f"当該 fact はスキップされます。",
        EdinetWarning,
        stacklevel=3,
    )
    return None
```

**設計判断（C-16 Period 型の制約対応）**: 旧計画では `contexts=None` の場合に `_parse_period_from_context_ref()` で `InstantPeriod(instant=None)` / `DurationPeriod(start_date=None, end_date=None)` を返すフォールバックを設計していたが、**現在の型定義では `InstantPeriod.instant: datetime.date`（Not Optional）、`DurationPeriod.start_date/end_date: datetime.date`（Not Optional）のため型レベルで不可能**。`contexts` を必須パラメータに変更し、フォールバックを廃止した。Wave 1 L4 の `structure_contexts()` で常に contexts が取得可能なため、利用者への影響はない。

### 5.8 名前空間判定

```python
from edinet.xbrl._namespaces import classify_namespace

def _is_jpcrp_namespace(uri: str) -> bool:
    """名前空間 URI が jpcrp_cor かどうかを判定する。

    US-GAAP 要素は全て jpcrp_cor 名前空間に属する。
    classify_namespace() を使用して DRY 原則を遵守する（T-3 対応）。
    """
    info = classify_namespace(uri)
    return info.module_group == "jpcrp"
```

### 5.9 期間ソートキー（T-5, I-2 対応）

```python
import datetime

def _period_sort_key(period: Period) -> datetime.date:
    """Period からソートキーとなる日付を取得する。

    DurationPeriod → end_date、InstantPeriod → instant。
    contexts 必須化により日付は常に有効な datetime.date。
    """
    if isinstance(period, InstantPeriod):
        return period.instant
    if isinstance(period, DurationPeriod):
        return period.end_date
    return datetime.date.min  # 型安全のためのフォールバック（到達しない）
```

`USGAAPSummary.get_item()` と `available_periods` はこのキーを使用してソートする。`DurationPeriod` と `InstantPeriod` が混在した場合も `end_date` / `instant` の日付値で統一的に比較する。`contexts` 必須化（C-16）により、全 Period は有効な日付を持つことが保証される。

### 5.10 EdinetWarning の使用箇所（T-8 対応）

以下のケースで `warnings.warn(..., EdinetWarning)` を発出する:

| 箇所 | 条件 | メッセージ例 | 動作 |
|------|------|------------|------|
| `_resolve_period()` | `context_ref` が contexts 辞書に見つからない | `"contextRef 'xxx' が contexts 辞書に見つかりません"` | 当該 fact をスキップ |
| `_parse_value()` | 数値が期待される fact が文字列にフォールバック | `"数値が期待される fact '{concept}' の値 '{value}' を Decimal に変換できません"` | 文字列として保持 |

**注**: 未知の US-GAAP 要素パターン（タクソノミ更新時）は警告不要。`_USGAAP_SUMMARY_CONCEPTS` にない要素は単にスキップされるだけで、利用者に混乱を与えない。

---

## 6. 日本語ラベルの定義

SummaryOfBusinessResults 要素の日本語ラベルは `jpcrp_cor` のラベルファイル（`jpcrp_2025-11-01_lab.xml`）から直接検証済み。`_SummaryConceptDef.label_ja` フィールドに格納されているため、`_LABEL_JA_MAP` は `_USGAAP_SUMMARY_CONCEPTS` から動的に構築する（U-1 フィードバック対応: Single Source of Truth）。

```python
# _USGAAP_SUMMARY_CONCEPTS から動的構築（§3.4 が唯一のソース）
_LABEL_JA_MAP: dict[str, str] = {d.key: d.label_ja for d in _USGAAP_SUMMARY_CONCEPTS}
```

**設計判断**: ラベルのハードコードは一般的に避けるべきだが、US-GAAP 要素は全 37 個（SummaryOfBusinessResults は 19 個）と極めて少なく、EDINET タクソノミのバージョン間で安定している。ラベルファイルをランタイムで読み込むオーバーヘッドに対して、ハードコードの保守コストは十分に低い。将来ラベルが変更された場合は `_USGAAP_SUMMARY_CONCEPTS` の定数テーブルを更新するだけで済む。`_LABEL_JA_MAP` は `_USGAAP_SUMMARY_CONCEPTS` から自動導出されるため、二重管理のリスクはない。

---

## 7. テスト計画

### 7.1 テスト戦略

- **Detroit 派**: モック不使用。実際の RawFact を構築してアサート
- **リファクタリング耐性**: 内部関数はテストしない。公開 API のみテスト
- **フィクスチャ自己完結**: テストヘルパー関数で RawFact を構築。外部ファイル依存なし

### 7.2 テストヘルパー

```python
def _make_usgaap_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    context_ref: str = "CurrentYearDuration",
    unit_ref: str | None = "JPY",
    is_nil: bool = False,
) -> RawFact:
    """US-GAAP テスト用の RawFact を簡便に構築する。"""
    ns = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
    return RawFact(
        concept_qname=f"{{{ns}}}{local_name}",
        namespace_uri=ns,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=unit_ref,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )


def _make_jgaap_fact(
    local_name: str,
    value_raw: str | None = None,
) -> RawFact:
    """J-GAAP テスト用の RawFact（US-GAAP でないことの検証用）。"""
    ns = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
    return RawFact(
        concept_qname=f"{{{ns}}}{local_name}",
        namespace_uri=ns,
        local_name=local_name,
        context_ref="CurrentYearDuration",
        unit_ref="JPY",
        decimals=None,
        value_raw=value_raw,
        is_nil=False,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )
```

### 7.3 テストケース

#### P0（必須） — extract_usgaap_summary のメインフロー

| # | テスト名 | 概要 |
|---|---------|------|
| T1 | `test_extract_revenue` | SummaryOfBusinessResults の売上高が正規化キー `"revenue"` で抽出されること |
| T2 | `test_extract_all_summary_items` | 全 19 個の SummaryOfBusinessResults 要素が抽出されること |
| T3 | `test_summary_item_has_correct_key` | 各項目の正規化キーが定義通りであること |
| T4 | `test_summary_item_value_is_decimal` | 数値 Fact の value が `Decimal` であること |
| T5 | `test_summary_item_nil_value_is_none` | nil Fact の value が `None` であること |
| T6 | `test_text_block_extracted` | TextBlock 要素が抽出されること |
| T7 | `test_text_block_statement_hint` | TextBlock の statement_hint が正しく推定されること |
| T8 | `test_text_block_semi_annual_flag` | TextBlock の is_semi_annual フラグが正しいこと |
| T9 | `test_description_extracted` | 米国基準適用の説明文が抽出されること |
| T10 | `test_total_elements_count` | total_usgaap_elements が正しいこと |
| T11 | `test_empty_facts_returns_empty_summary` | 空の facts で空の USGAAPSummary が返ること |
| T12 | `test_jgaap_facts_returns_empty_summary` | J-GAAP の facts で空の USGAAPSummary が返ること |

#### P0 — USGAAPSummary のメソッド

| # | テスト名 | 概要 |
|---|---------|------|
| T13 | `test_get_item_by_key` | `get_item()` で正規化キーにより項目を取得できること |
| T14 | `test_get_item_returns_none_for_missing_key` | 存在しないキーで None が返ること |
| T15 | `test_get_items_by_period` | `get_items_by_period()` で期間ごとにフィルタできること |
| T16 | `test_available_periods` | `available_periods` が新しい順にソートされていること |
| T17 | `test_to_dict_format` | `to_dict()` が正しい辞書形式を返すこと |
| T18 | `test_to_dict_excludes_text_blocks` | `to_dict()` に TextBlock が含まれないこと |
| T19 | `test_repr` | `__repr__` が要素数を含むこと |

#### P0 — is_usgaap_element / ユーティリティ

| # | テスト名 | 概要 |
|---|---------|------|
| T20 | `test_is_usgaap_element_true` | `"RevenuesUSGAAPSummaryOfBusinessResults"` で True |
| T21 | `test_is_usgaap_element_false_for_jgaap` | `"NetSales"` で False |
| T22 | `test_is_usgaap_element_false_for_empty` | 空文字列で False |

#### P0 — get_jgaap_mapping / get_usgaap_concept_names

| # | テスト名 | 概要 |
|---|---------|------|
| T23 | `test_jgaap_mapping_revenue` | `"revenue"` → `"NetSales"` |
| T24 | `test_jgaap_mapping_none_for_ratio` | `"per"` → `None` |
| T25 | `test_jgaap_mapping_completeness` | 全 19 キーが辞書に含まれること |
| T26 | `test_concept_names_count` | 19 個の concept 名が返ること |
| T27 | `test_concept_names_frozenset` | 戻り値が frozenset であること |
| T28 | `test_concept_names_contains_revenues` | `"RevenuesUSGAAPSummaryOfBusinessResults"` が含まれること |

#### P0 — contexts 引数の動作（T-4 対応、C-16 修正）

| # | テスト名 | 概要 |
|---|---------|------|
| T29 | `test_extract_with_contexts_dict` | `contexts` 引数で StructuredContext の period が使われること |
| T30 | `test_extract_skips_unknown_context_ref` | contexts 辞書にない context_ref の fact がスキップされ EdinetWarning が発出されること |

#### P1（推奨） — エッジケース

| # | テスト名 | 概要 |
|---|---------|------|
| T31 | `test_multiple_periods_summary` | 当期・前期の SummaryOfBusinessResults が両方抽出されること |
| T32 | `test_text_block_unknown_type` | 未知の TextBlock パターンで statement_hint=None |
| T33 | `test_frozen_dataclass` | USGAAPSummary, USGAAPSummaryItem, USGAAPTextBlockItem が frozen であること |
| T34 | `test_mixed_usgaap_and_jgaap_facts` | US-GAAP と J-GAAP の facts が混在しても US-GAAP のみ抽出されること |
| T35 | `test_text_block_html_content_preserved` | HTML タグを含む TextBlock の内容がそのまま保持されること |
| T36 | `test_text_block_annual_vs_semi_annual` | 年次 BS と半期 BS の TextBlock が is_semi_annual で区別されること |
| T37 | `test_get_item_prefers_latest_period` | `get_item()` が最新期間を優先すること |
| T38 | `test_parse_value_warning_on_non_numeric` | unit_ref がある fact の値が非数値の場合に EdinetWarning が発出されること |

---

## 8. 実装手順

### Step 1: データモデル定義

1. `src/edinet/xbrl/standards/usgaap.py` を新規作成
2. `_SummaryConceptDef` 内部 dataclass を定義
3. `_USGAAP_SUMMARY_CONCEPTS` タプル定数を定義
4. `_TEXTBLOCK_STATEMENT_MAP` 辞書定数を定義
5. `_LABEL_JA_MAP` を `_USGAAP_SUMMARY_CONCEPTS` から動的構築
6. `USGAAPSummaryItem` frozen dataclass を定義
7. `USGAAPTextBlockItem` frozen dataclass を定義
8. `USGAAPSummary` frozen dataclass + メソッドを定義

### Step 2: 内部ユーティリティ実装

1. `_is_jpcrp_namespace()` を実装
2. `_parse_value()` を実装
3. `_resolve_period()` を実装（contexts 辞書参照、見つからない場合は警告 + None 返却）
4. `_classify_text_block()` を実装（最長一致キーワードマッチ）
5. `_period_sort_key()` を実装
6. `_extract_description()` を実装（`_DESCRIPTION_CONCEPT` 定数 + 最初のマッチを返す）

### Step 3: 公開 API 実装

1. `is_usgaap_element()` を実装
2. `get_jgaap_mapping()` を実装
3. `get_usgaap_concept_names()` を実装
4. `_extract_summary_items()` を実装
5. `_extract_text_blocks()` を実装
6. `extract_usgaap_summary()` を実装（`_extract_description()` は Step 2 で実装済み）

### Step 4: テスト実装

1. `tests/test_xbrl/test_standards_usgaap.py` を新規作成
2. テストヘルパー（`_make_usgaap_fact`, `_make_jgaap_fact`）を実装
3. P0 テスト（T1〜T28）を全て実装
4. P1 テスト（T29〜T35）を全て実装

### Step 5: 検証

1. `uv run ruff check src/edinet/xbrl/standards/usgaap.py tests/test_xbrl/test_standards_usgaap.py` — Lint チェック
2. `uv run pytest tests/test_xbrl/test_standards_usgaap.py -v` — usgaap テストのみ実行
3. `uv run pytest` — 全テスト実行（既存テストを壊していないことを確認）

---

## 9. 設計判断の記録

### Q: なぜ `FinancialStatement` ではなく `USGAAPSummary` という専用型を返すか？

**A**: US-GAAP 企業の XBRL は包括タグ付けのみであり、J-GAAP のような勘定科目単位の `LineItem` が存在しない。`FinancialStatement` は `tuple[LineItem, ...]` を `items` として保持するが、SummaryOfBusinessResults の 19 項目は「財務諸表」ではなく「経営指標のサマリー」であり、意味論的に異なる。既存の型に無理に押し込むと、利用者が「US-GAAP 企業の PL に 19 行しかない」と混乱するリスクがある。専用型にすることで「これは包括タグ付け企業のサマリーである」ことが型レベルで明示される。

### Q: `_SummaryConceptDef.jgaap_concept` は `standards/normalize` の責務ではないか？

**A**: 会計基準間の完全なマッピングは `standards/normalize` の責務だが、US-GAAP の 19 要素は数が少なく安定しているため、本 Lane でマッピング情報を提供しておくことが実用的。`standards/normalize` は本モジュールの `get_jgaap_mapping()` を利用して横断比較テーブルを構築できる。マッピングの管理責任は本モジュール側にあり、`normalize` はそれを消費するだけ。

### Q: `_is_jpcrp_namespace()` は `_namespaces.py` の `classify_namespace()` を使うべきでは？

**A**: Yes — `classify_namespace()` を使用する（T-3 フィードバック対応）。US-GAAP 企業は 10〜15 社、1 ファイルの facts は数百〜数千件であり、`classify_namespace()` の正規表現マッチコストは実測上無視できる水準。DRY 原則を優先し、将来 URI パターンが変更された場合の保守コストも `classify_namespace()` に一元化する。

### Q: JMIS は本 Lane でまとめて実装すべきでは？

**A**: D-2.a.md より JMIS も同じパターン（TextBlock + SummaryOfBusinessResults）であり、技術的には同一ファイルで実装可能。しかし:
1. FUTUREPLAN.tmp.md の Lane 割り当てに JMIS は含まれていない
2. JMIS の 40 要素の詳細調査（concept 名・ラベル・マッピング）が未了
3. JMIS のサフィックスパターンは `JMISSummaryOfBusinessResults` であり、`USGAAPSummaryOfBusinessResults` とは別の定数テーブルが必要
4. `_SummaryConceptDef` の `concept_local_name` フィールドに完全な concept 名を保持する設計（T-2 対応）により、JMIS は `_SummaryConceptDef("revenue", "RevenuesJMISSummaryOfBusinessResults", "NetSales")` のように同じ dataclass をそのまま再利用可能。構築ロジックの複製は不要

### Q: なぜ `contexts` パラメータを必須にしたか？（C-16）

**A**: 旧計画では `contexts: ... | None = None` とし、`None` の場合に `_parse_period_from_context_ref()` で contextRef 文字列から簡易パースするフォールバックを設計していた。しかし **`InstantPeriod.instant: datetime.date`（Not Optional）、`DurationPeriod.start_date/end_date: datetime.date`（Not Optional）** のため、日付未知の Period を構築することが型レベルで不可能であることが判明した。

代替案の検討:
1. **センチネル日付（`datetime.date.min`）**: 型は通過するが、利用者が「不明」と「最古」を区別できず誤用リスクが高い
2. **UnknownPeriod 型の追加**: `Period` 型の定義変更が必要だが、contexts.py は他レーン管理のため変更禁止
3. **`contexts` 必須化**: Wave 1 L4 の `structure_contexts()` で常に取得可能。フォールバック廃止

方針 3 が最もクリーン。US-GAAP 抽出は通常パイプラインの下流で使われ、contexts は既にパース済みであることが期待される。

### Q: タクソノミ依存データを JSON に外出しすべきか？（T-9 への回答）

**A**: いいえ。Python 定数テーブルを維持する。理由:

1. **スケールが小さすぎる**: US-GAAP は SummaryOfBusinessResults 19 要素 + TextBlock 14 要素 + Description 1 要素 = 計 34 要素。L3 の `pl_jgaap.json` 等（数百 concept）とはスケールが根本的に異なり、JSON 化による保守性向上は微小
2. **JSON のオーバーヘッド**: `importlib.resources` の読み込み機構、JSON バリデーション層、ファイル追加を伴い、34 要素には過剰なインフラ
3. **L3 JSON との非対称性**: L3 の手動 JSON は将来 `taxonomy/concept_sets` で自動導出に置換される（FEATURES.md L137-139）。US-GAAP は Presentation Linkbase がないため concept_sets の対象外だが、34 要素の手動管理は Python 定数で十分に管理可能
4. **隔年更新の実務**: タクソノミ更新時は Python 定数テーブルの 19 行を更新するだけ。`git diff` での確認も十分可能

**補足**: フィードバック T-9 が引用する FEATURES.md L112-115（「手動定義が不可避。主要指標 50-100 程度」）は**全会計基準合計**の cross-standard mapping を指しており、US-GAAP 単体の 19 要素ではない。Wave 3 の `standards/normalize` が全標準のマッピングを統合する段階で、データ管理方式の再検討が適切。

### Q: `_SummaryConceptDef.jgaap_concept` と `taxonomy/concept_sets` の関係は？（T-10 への回答）

**A**: `taxonomy/concept_sets`（W2 L1）が置換するのは「どの concept が PL/BS/CF に属するか」の JSON（`pl_jgaap.json` 等）のみであり、**会計基準間の cross-standard mapping**（`jgaap_concept` 相当）は対象外。cross-standard mapping は FEATURES.md L112-115 で「手動定義が不可避（主要指標 50-100 程度）」と明記されており、将来にわたり手動管理が残る。本モジュールの `get_jgaap_mapping()` はその手動管理データの一部として位置づけられる。US-GAAP は Presentation Linkbase が存在しないため、`concept_sets` の恩恵を一切受けない。

### Q: `extract_usgaap_summary()` は会計基準の判別を行うべきか？

**A**: いいえ。会計基準の判別は Wave 2 L2 (`standards/detect`) の責務であり、本モジュールはそれを前提としない。利用者は以下のフローで使用する:

```python
# Wave 3 での使用例
from edinet.financial.standards.detect import detect_accounting_standard, DetailLevel
from edinet.financial.standards.usgaap import extract_usgaap_summary
from edinet.xbrl.dei import AccountingStandard

detected = detect_accounting_standard(parsed.facts)

if detected.standard == AccountingStandard.US_GAAP:
    summary = extract_usgaap_summary(parsed.facts, contexts)
    rev = summary.get_item("revenue")
    if rev:
        print(f"売上高: {rev.value}")
```

本モジュールは J-GAAP の facts を渡されても空の `USGAAPSummary` を返すだけであり、判別なしで安全に呼び出せる。ただし、US-GAAP 以外の facts に対して呼び出すのは無意味なため、利用者側で `detect` の結果に基づいて呼び出しを制御することを推奨する。

### Q: タクソノミ更新時の回帰テスト手段は？（U-3 対応で追記）

**A**: 本 Lane では実装しないが、将来の保守手段として `tools/verify_usgaap_concepts.py` のようなタクソノミ検証スクリプトが有用。jpcrp_cor XSD から `USGAAP` を含む全 element を抽出し、`_USGAAP_SUMMARY_CONCEPTS` + `_TEXTBLOCK_STATEMENT_MAP` との差分を報告するスクリプトを想定。タクソノミ更新時（隔年）に `EDINET_TAXONOMY_ROOT=... uv run python tools/verify_usgaap_concepts.py` で実行し、追加・削除・リネームされた concept を検知できる。

---

## 10. 後続レーンとの接続点

### Wave 3 L1 (`standards/normalize + statements.py 統合`)

`standards/normalize` は各会計基準モジュールの出力を統合する:

```python
# normalize.py（Wave 3 L1）での使用イメージ
from edinet.financial.standards.usgaap import (
    extract_usgaap_summary,
    get_jgaap_mapping,
)

def normalize_facts(facts, detected_standard, contexts):
    if detected_standard.standard == AccountingStandard.US_GAAP:
        summary = extract_usgaap_summary(facts, contexts)
        mapping = get_jgaap_mapping()
        # summary_items を正規化キー経由で J-GAAP concept にマッピング
        for item in summary.summary_items:
            jgaap_concept = mapping.get(item.key)
            if jgaap_concept:
                # 横断比較可能な形式に変換
                ...
```

### FEATURES.md: text_blocks（Phase 7）

US-GAAP の TextBlock 内の HTML テキスト抽出は `text_blocks` モジュールの責務:

```python
# 将来の text_blocks モジュールでの使用イメージ
from edinet.financial.standards.usgaap import extract_usgaap_summary

summary = extract_usgaap_summary(facts, contexts)
for block in summary.text_blocks:
    if block.statement_hint == "income_statement":
        clean_text = clean_html(block.html_content)  # text_blocks/clean の機能
```

### JMIS 拡張

将来の `standards/jmis.py` は本モジュールと同じ設計パターンを使用:

```python
# 将来の jmis.py
_JMIS_SUMMARY_CONCEPTS: tuple[_SummaryConceptDef, ...] = (
    _SummaryConceptDef("revenue", "RevenuesJMISSummaryOfBusinessResults", "NetSales"),
    # ... JMIS 固有の 40 要素（concept_local_name に完全名を保持）
)
# extract_jmis_summary() も同様のフロー
```

---

## 11. マイルストーン完了条件

1. `extract_usgaap_summary()` が SummaryOfBusinessResults 要素を 19 個抽出できる
2. 各 SummaryOfBusinessResults 項目に正規化キー・日本語ラベルが付与される
3. TextBlock 要素が財務諸表種別で分類される
4. TextBlock の `is_semi_annual` フラグが正しく設定される
5. 説明文要素が抽出される
6. `total_usgaap_elements` が正確にカウントされる
7. `USGAAPSummary.get_item()` が正規化キーで検索できる
8. `USGAAPSummary.get_items_by_period()` が期間フィルタできる
9. `USGAAPSummary.to_dict()` が正しい辞書形式を返す
10. `is_usgaap_element()` が US-GAAP 要素を正しく判定する
11. `get_jgaap_mapping()` が 19 キー全てに対してマッピングを返す
12. `get_usgaap_concept_names()` が 19 個の concept 名を返す
13. J-GAAP の facts を渡しても空の USGAAPSummary が返る（エラーなし）（空の contexts dict を渡す）
14. 空の facts を渡してもエラーなし（空の contexts dict を渡す）
15a. contexts 辞書にない context_ref の fact は EdinetWarning を発出してスキップされる
15. 全 dataclass が frozen である
16. テスト: 38 テストケースが PASS
17. リント: ruff clean
18. 既存テスト: 全 PASS（破壊なし）

---

## 12. ファイル一覧

| 操作 | パス |
|------|------|
| 新規 | `src/edinet/xbrl/standards/usgaap.py` |
| 新規 | `tests/test_xbrl/test_standards_usgaap.py` |

全て新規ファイル。既存ファイルの変更なし。

---

## 13. 変更履歴（フィードバック反映ログ）

| 変更 # | 対応元 | 箇所 | 変更内容 |
|--------|--------|------|----------|
| C-1 | **独自発見（CRITICAL）** | §1.2, §3.4, §6 | **concept 名を 2025-11-01 タクソノミ XSD で直接検証し 7 箇所修正**。`NetAssetsUSGAAP...` → `EquityIncludingPortionAttributableToNonControllingInterestUSGAAP...`、`NetCashProvidedByUsedIn*` → `CashFlowsFromUsedIn*`、`DilutedEarningsPerShare` → `DilutedEarningsLossPerShare`、`BookValuePerShare` → `EquityAttributableToOwnersOfParentPerShare`。存在しない `NumberOfEmployees`・`DividendPaidPerShare` を削除、`ComprehensiveIncomeAttributableToOwnersOfParent`・`EquityAttributableToOwnersOfParent` を追加。日本語ラベルもラベルファイルで直接検証し修正 |
| C-2 | T-1 (CRITICAL) | §3.4 | **正規化キーを L3/L4 と統一**: `revenues`→`revenue`, `net_income`→`net_income_parent`, `operating_cash_flow`→`operating_cf`, `investing_cash_flow`→`investing_cf`, `financing_cash_flow`→`financing_cf`, `cash_equivalents`→`cash_end`, `eps_basic`→`eps`。新キー `comprehensive_income_parent`, `shareholders_equity` を追加 |
| C-3 | T-2 (HIGH) | §3.4, §5.2, §9 | `concept_suffix` → `concept_local_name`（完全な concept ローカル名を保持する方式に変更）。JMIS 拡張時の構築ロジック複製を不要にする |
| C-4 | T-3 (HIGH) | §5.7, §9 | `_is_jpcrp_namespace()` を `classify_namespace()` ベースに変更。DRY 原則を優先 |
| C-5 | T-4 (HIGH) | §5.6, §7.3 | `_parse_period_from_context_ref()` の実装詳細を追記。テスト T29/T30 を P0 に追加 |
| C-6 | T-5 (MEDIUM) | §3.3, §5.8（新設） | `_period_sort_key()` を定義し、`get_item()` の「最新」の定義を明確化 |
| C-7 | T-6 (MEDIUM) | §3.3 | `to_dict()` で `Decimal` → `str` 変換を行う方針を明記（精度保持のため `float` ではなく `str`） |
| C-8 | T-7 (MEDIUM) | §4.0（新設） | `__all__` の定義を追加 |
| C-9 | T-8 (MEDIUM) | §5.5, §5.6, §5.9（新設） | `EdinetWarning` の使用箇所を定義（`_parse_value()` での非数値フォールバック、`_resolve_period()` での context 不在） |
| C-10 | I-1 (LOW) | §1.3, §3.5 | TextBlock の全 14 要素の concept 名を列挙。`_TEXTBLOCK_STATEMENT_MAP` を全 14 パターンに拡充（半期バリアント + 注記を追加、存在しない非連結パターンを削除） |
| C-11 | I-1 (LOW) | §3.2 | `USGAAPTextBlockItem.is_consolidated` → `is_semi_annual` に変更（US-GAAP TextBlock は全て連結のため `is_consolidated` は常に True で無意味） |
| C-12 | I-2 (LOW) | §5.8（新設） | `available_periods` のソートキーを `_period_sort_key()` として定義 |
| C-13 | I-3 (LOW) | — | T-2（C-3）で `concept_local_name` 方式に変更したことで自然解決 |
| C-14 | — | §7.3 | テスト T36（年次 vs 半期 TextBlock 区別）、T37（最新期間優先）、T38（EdinetWarning 発出テスト）を追加。T29-T35 を T31-T37 にリナンバリング |
| C-15 | — | §10 | コード例の canonical key を修正（`"revenues"` → `"revenue"` 等） |
| C-16 | **独自発見（CRITICAL）** | §4.1, §5.1, §5.2, §5.3, §5.6, §5.8, §5.9, §7.3, §8, §9 | **`contexts` パラメータを必須化、`_parse_period_from_context_ref()` を廃止**。`InstantPeriod.instant: datetime.date`（Not Optional）、`DurationPeriod.start_date/end_date: datetime.date`（Not Optional）のため、日付未知の Period を構築するフォールバックが型レベルで不可能。Wave 1 L4 `structure_contexts()` で常に contexts 取得可能のため必須化。`_resolve_period()` は contexts から取得、見つからない場合は警告+スキップ。T30 を「フォールバック動作テスト」→「未知 context_ref スキップテスト」に変更 |
| C-17 | T-9 (HIGH) — **不採用** | §9 | JSON 外出しは不採用。34 要素ではスケールが小さすぎ、`importlib.resources` 機構のオーバーヘッドに見合わない。L3 JSON（数百 concept）とは根本的にスケールが異なる。設計判断を §9 に記録 |
| C-18 | T-10 (MEDIUM) | §9 | `taxonomy/concept_sets` と cross-standard mapping の関係を設計判断に明記。concept_sets が置換するのは PL/BS/CF 所属 JSON のみであり、会計基準間マッピングは対象外 |
| C-19 | U-1 (MEDIUM) | §3.4, §5.2, §6 | **`_SummaryConceptDef` に `label_ja` フィールドを追加し Single Source of Truth 化**。`_LABEL_JA_MAP` は `_USGAAP_SUMMARY_CONCEPTS` から動的構築に変更。`_extract_summary_items()` は `_LABEL_JA_MAP.get()` → `defn.label_ja` に変更。二重管理リスクを解消 |
| C-20 | U-2 (LOW) | §5.5（新設） | **`_extract_description()` の実装詳細を追記**。対象 concept 名 `_DESCRIPTION_CONCEPT` の定義、複数 fact 存在時の挙動（最初の 1 つを採用）を明記 |
| C-21 | U-3 (LOW) | §9 | **タクソノミ検証スクリプトの将来メモを追記**。`tools/verify_usgaap_concepts.py` として jpcrp_cor XSD との差分検出スクリプトの存在を保守者向けに記載 |
| C-22 | U-4 (LOW) | §3.4 | **`comprehensive_income` / `comprehensive_income_parent` の `jgaap_concept` にマッピング追加**（選択肢A）。`None` → `"ComprehensiveIncome"` / `"ComprehensiveIncomeAttributableToOwnersOfParent"`。jppfs_cor に同名 concept が存在することを確認済み。Wave 3 normalize での包括利益比較が可能に |

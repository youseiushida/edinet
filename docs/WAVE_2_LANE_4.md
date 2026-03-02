# Wave 2 / Lane 4 — standards/ifrs: IFRS の科目定義と J-GAAP 対応マッピング

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 2 / Lane 4 を担当するエージェントです。
担当機能: standards_ifrs

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
   - `src/edinet/xbrl/standards/ifrs.py` (新規)
   - `src/edinet/xbrl/data/pl_ifrs.json` (新規)
   - `src/edinet/xbrl/data/bs_ifrs.json` (新規)
   - `src/edinet/xbrl/data/cf_ifrs.json` (新規)
   - `tests/test_xbrl/test_standards_ifrs.py` (新規)
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
   - 例: `from edinet.financial.standards.ifrs import load_ifrs_pl_concepts` （OK）
   - 例: `from edinet.xbrl import load_ifrs_pl_concepts` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_standards_ifrs.py` に作成
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
   - **他の Wave 2 レーンが作成中のモジュール**（concept_sets, detect, jgaap, usgaap）に依存してはならない

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 4 — standards/ifrs: IFRS の科目定義と J-GAAP 対応マッピング

## 0. 位置づけ

Wave 2 Lane 4 は、FEATURES.md の **Accounting Standard Normalization > standards/ifrs** に対応する。IFRS（国際財務報告基準）適用企業が使用する `jpigp_cor` タクソノミの科目定義を提供し、J-GAAP との科目対応マッピングを定義するモジュール。

FEATURES.md の定義:

> - standards/ifrs: IFRS の科目マッピング [TODO]
>   - depends: facts, namespaces
>   - detail: IFRS には「経常利益」がない等の構造的差異を吸収

FUTUREPLAN.tmp.md での位置:

> Phase 3-4: `standards/ifrs` → L5 namespaces 依存

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl._namespaces` (Wave 1 L5) | `classify_namespace()`, `NamespaceInfo.module_group` | read-only |
| `edinet.models.financial.StatementType` | 財務諸表タイプ Enum | read-only |

他レーンとのファイル衝突なし（全て新規ファイル作成）。

### QA 参照

| QA | タイトル | 関連度 |
|----|---------|--------|
| D-1 | IFRS 適用企業の XBRL | **直接（設計の基盤）** — IFRS タクソノミの構造・concept 名・ラベル・Context 互換性 |
| D-3 | 会計基準の判別方法 | 直接（IFRS 判別手段の知見） |
| E-7 | 主要勘定科目の concept 名辞書 | 直接（J-GAAP 側のマッピング先） |
| E-1 | 財務諸表の種類と識別 | 関連（PL/BS/CF の分類基準） |
| E-5 | 業種別の財務諸表の差異 | 関連（業種固有科目の IFRS 対応） |
| C-7 | 計算リンクベースの詳細構造 | 関連（IFRS P/L 計算階層の根拠） |
| J-1 | 包括利益計算書 | 関連（IFRS の OCI 構造） |

---

## 1. ゴール

1. IFRS 適用企業（`jpigp_cor` 名前空間）の **PL / BS / CF 科目定義** を `IFRSConceptMapping` dataclass として提供する（Python コードが主データソース）
2. Lane 3 の `ConceptMapping` と**対称的な API** を提供し、`canonical_key` による会計基準横断の統一アクセスを可能にする
3. **レガシー互換用の JSON データファイル**（`pl_ifrs.json` 等）を既存 J-GAAP JSON と同一フォーマットで提供し、`statements.py` への段階的統合を支援する
4. **IFRS ↔ J-GAAP の科目マッピング** を `IFRSConceptMapping.jgaap_concept` として統合提供し、Wave 3 L1（`standards/normalize`）が会計基準間の概念対応を解決できるようにする
5. IFRS 固有の構造的差異（経常利益の不存在、金融収益/費用の独立表示等）を **明示的にモデル化** する
6. `StatementType`（`INCOME_STATEMENT` / `BALANCE_SHEET` / `CASH_FLOW_STATEMENT`）をキーにして IFRS 科目定義を取得する **ディスパッチ関数** を提供する

### 非ゴール（スコープ外）

- 会計基準の自動判別 → Wave 2 L2 (`standards/detect`) の責務
- `statements.py` への統合・切り替えロジック → Wave 3 L1 (`standards/normalize`) の責務
- タクソノミからの科目セット自動導出 → Wave 2 L1 (`taxonomy/concept_sets`) の責務（JSON は過渡的措置）
- ラベルリンクベースの読み込み → 既存の `TaxonomyResolver` および将来の `taxonomy/labels` で対応
- IFRS の包括利益計算書（CI）・株主資本等変動計算書（SS） → Phase 6 の `statements/comprehensive_income` / `statements/equity` で対応
- `canonical_key` の名称決定は Lane 3 §5.2-5.5 が権限を持つ。本レーンは Lane 3 で定義された値を使用する（共通科目）
- KPI（EPS / BPS / 配当等）の IFRS マッピング → Phase 6 または将来の拡張で対応。Lane 3 は KPI 8 概念（`statement_type=None`）を含むが、本レーンでは PL / BS / CF の主要科目に集中する

---

## 2. 背景知識（QA サマリー）

### D-1: IFRS 適用企業の XBRL

EDINET の IFRS タクソノミについて、D-1.a.md で以下が確認されている:

**タクソノミの構造**:
- IASB の `ifrs-full` 名前空間は EDINET では**使用されない**
- EDINET 独自の `jpigp_cor`（`http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/{version}/jpigp_cor`）が使用される
- `jpigp_cor_2025-11-01.xsd` は 1803 要素（684 abstract、1119 concrete）を含む
- 型別: `stringItemType`=668, `monetaryItemType`=606, `textBlockItemType`=505 等

**Concept 命名規則**:
- J-GAAP の概念名に `IFRS` サフィックスを付加するパターン（例: `NetSales` → `RevenueIFRS`）
- ただし概念自体が異なる場合は名称も変わる（`NetSales`=売上高 → `RevenueIFRS`=売上収益）

**P/L 計算階層**（calculation linkbase 解析結果）:
```
ProfitLossIFRS（当期純利益）
  └─ ProfitLossBeforeTaxIFRS（税引前当期利益）
       └─ OperatingProfitLossIFRS（営業利益）
            └─ GrossProfitIFRS（売上総利益）
                 ├─ RevenueIFRS（売上収益）  [+]
                 └─ CostOfSalesIFRS（売上原価）  [-]
       ├─ FinanceIncomeIFRS（金融収益）  [+]
       └─ FinanceCostsIFRS（金融費用）  [-]
```

**J-GAAP との構造的差異**:
- **経常利益（OrdinaryIncome）**: IFRS に該当 concept なし。`jpigp_cor` 全 1803 要素に "Ordinary" を含む要素は皆無
- **営業外収益/費用**: IFRS では独立カテゴリなし。金融収益/費用（`FinanceIncomeIFRS`/`FinanceCostsIFRS`）に再分類
- **特別利益/損失**: IFRS では独立カテゴリなし
- **税引前当期利益**: J-GAAP の `IncomeBeforeIncomeTaxes` の位置に `ProfitLossBeforeTaxIFRS` が対応。J-GAAP の「経常利益」に最も近い概念

**Context 構造**: J-GAAP と**完全に同一**。同じ identifier スキーム、同じ Context ID 命名規約（`FilingDateInstant`, `CurrentYearDuration` 等）、同じディメンション軸（`jppfs_cor:ConsolidatedOrNonConsolidatedAxis` 等）を使用。

**ラベル**: `ALL_20251101/taxonomy/jpigp/{日付}/label/jpigp_{日付}_lab.xml`（日本語）および `jpigp_{日付}_lab-en.xml`（英語）から取得。

**B/S の主要科目**:
- `TotalAssets` → IFRS の Presentation に存在（Calculation linkbase では直接の対応要素なし）
- `NetAssets` → `EquityIFRS`（IFRS では「純資産」ではなく「資本」）

### E-7: J-GAAP 主要勘定科目辞書

J-GAAP 側のマッピング先として以下の concept が確認されている:

- **PL**: `NetSales`, `CostOfSales`, `GrossProfit`, `OperatingIncome`, `OrdinaryIncome`, `IncomeBeforeIncomeTaxes`, `ProfitLoss`, `ProfitLossAttributableToOwnersOfParent`
- **BS**: `CurrentAssets`, `NoncurrentAssets`, `Assets`, `CurrentLiabilities`, `NoncurrentLiabilities`, `Liabilities`, `NetAssets`
- **CF**: `NetCashProvidedByUsedInOperatingActivities`, `NetCashProvidedByUsedInInvestmentActivities`, `NetCashProvidedByUsedInFinancingActivities`

全 PL 科目は `duration`（期間）、全 BS 科目は `instant`（時点）の periodType を持つ。

### D-3: 会計基準の判別

`jpigp_cor` の名前空間 URI の存在をもって IFRS 適用と推定可能（`NamespaceInfo.module_group == "jpigp"`）。IFRS 企業でも `jppfs_cor` は併用される（ディメンション軸用）。

---

## 3. データモデル設計

### 3.1 IFRSConceptMapping (frozen dataclass) — 主データモデル

IFRS 科目の正規化マッピング。Lane 3 の `ConceptMapping` と**対称的な構造**を持ち、Wave 3 の normalize が `canonical_key` で会計基準横断の統一アクセスを提供できるようにする。

```python
from dataclasses import dataclass
from edinet.models.financial import StatementType

@dataclass(frozen=True, slots=True)
class IFRSConceptMapping:
    """IFRS 科目の正規化マッピング。

    Lane 3 の ConceptMapping と対称的な構造を持つ。
    canonical_key を共通キーとして、Wave 3 の normalize が
    会計基準横断の統一アクセスを提供する。

    Attributes:
        concept: jpigp_cor の concept ローカル名（例: "RevenueIFRS"）。
            バージョン非依存（H-3）。
        canonical_key: 正規化キー（例: "revenue"）。
            会計基準間で共通の文字列識別子。Lane 3 §5.2-5.5 で定義
            された J-GAAP の正規化キーと同一値を使用する。
            IFRS 固有科目には新規キーを定義。小文字 snake_case。
        label_ja: 日本語ラベル（例: "売上収益"）。
        label_en: 英語ラベル（例: "Revenue"）。
        statement_type: 所属する財務諸表。INCOME_STATEMENT / BALANCE_SHEET /
            CASH_FLOW_STATEMENT。
        period_type: 期間型。``"instant"`` or ``"duration"``。
            BS 科目は ``"instant"``、PL/CF 科目は ``"duration"``。
            NOTE: CF の ``cash_beginning`` / ``cash_end`` は概念的には
            残高（instant）だが、EDINET XBRL では CF セクション全体が
            duration context で報告されるため ``"duration"`` とする。
        is_ifrs_specific: IFRS 固有の概念か。
            True の場合、J-GAAP に直接対応する概念がない。
            例: 金融収益（FinanceIncomeIFRS）、金融費用（FinanceCostsIFRS）。
        is_total: 合計・小計行か。
            例: AssetsIFRS（資産合計）、GrossProfitIFRS（売上総利益）。
        display_order: 標準的な表示順序。
            同一 statement_type 内での相対順序。1 始まり。
        jgaap_concept: J-GAAP 側の対応 concept ローカル名（例: "NetSales"）。
            IFRS 固有の科目（J-GAAP に対応なし）の場合は None。
        mapping_note: マッピングに関する補足説明。
            例: "IFRS 固有。J-GAAP の営業外収益の一部に相当"。
    """
    concept: str
    canonical_key: str
    label_ja: str
    label_en: str
    statement_type: StatementType
    period_type: str
    is_ifrs_specific: bool = False
    is_total: bool = False
    display_order: int = 0
    jgaap_concept: str | None = None
    mapping_note: str = ""
```

**設計根拠**:
- **Lane 3 (`ConceptMapping`) との対称性**: フィールド構成が Lane 3 と同等（`is_jgaap_specific` → `is_ifrs_specific`）。Wave 3 の normalize が `canonical_key` だけで両方のモジュールを統一的に扱える
- `canonical_key` は Lane 3 §5.2-5.5 で定義された値を使用し、IFRS 固有科目（`finance_income`, `finance_costs` 等）には新規キーを追加
- `frozen=True` により不変性を保証。`slots=True` でメモリ効率を最適化
- `label_en` を含める理由: 国際化対応の基盤。Lane 3 と同様
- `jgaap_concept` / `mapping_note` フィールドの追加理由: 旧 `IFRSMapping` dataclass の情報を統合。`ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` を `_ALL_MAPPINGS` から直接導出可能にし、二重管理を排除（第3版フィードバック H-1 A案）

### 3.2 IFRSProfile (frozen dataclass)

```python
@dataclass(frozen=True, slots=True)
class IFRSProfile:
    """IFRS 会計基準のプロファイル（概要情報）。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に保持し、ディスパッチに使用する。
    Lane 3 の JGAAPProfile と対称的な構造。

    Attributes:
        standard_id: 会計基準の識別子。``"ifrs"`` 固定。
        display_name_ja: 日本語表示名。
        display_name_en: 英語表示名。
        module_groups: この会計基準に**固有の**（他の会計基準では使用されない）
            タクソノミモジュールグループの集合。
            IFRS 企業でも jpcrp_cor / jpdei_cor は共通して使用されるが、
            jpigp_cor は IFRS 企業のみが使用するため、このフィールドには
            {"jpigp"} のみを含む。共通モジュール（jpcrp, jpdei）は含まない。
        canonical_key_count: 定義されている正規化キーの総数（PL + BS + CF）。
            KPI 概念は含まない（将来拡張予定）。
            Lane 3 は KPI 8 概念を含む 52 keys だが、本モジュールは
            PL + BS + CF の合計（M-1 対応で BS 拡張後に更新）。
        has_ordinary_income: 経常利益の概念を持つか（False: IFRS にはない）。
        has_extraordinary_items: 特別利益/特別損失の概念を持つか（False）。
    """
    standard_id: str
    display_name_ja: str
    display_name_en: str
    module_groups: frozenset[str]
    canonical_key_count: int
    has_ordinary_income: bool
    has_extraordinary_items: bool
```

---

## 4. データファイル設計（JSON — レガシー互換用）

> **位置づけ**: 主データソースはセクション 7 の Python コード（`_PL_MAPPINGS` 等の `IFRSConceptMapping` タプル）。JSON ファイルは `statements.py` の `_load_concept_definitions()` に直接投入するための**レガシー互換フォーマット**。`to_legacy_concept_list()` が Python データから同等の出力を生成するため、Wave 3 統合後は JSON ファイルへの依存はなくなる。

### 4.1 `src/edinet/xbrl/data/pl_ifrs.json`

IFRS 損益計算書の科目定義。D-1.a.md の Calculation Linkbase 解析結果に基づく。

```json
[
  {"concept": "RevenueIFRS", "order": 1, "label_hint": "売上収益"},
  {"concept": "CostOfSalesIFRS", "order": 2, "label_hint": "売上原価"},
  {"concept": "GrossProfitIFRS", "order": 3, "label_hint": "売上総利益"},
  {"concept": "SellingGeneralAndAdministrativeExpensesIFRS", "order": 4, "label_hint": "販売費及び一般管理費"},
  {"concept": "OtherIncomeIFRS", "order": 5, "label_hint": "その他の収益"},
  {"concept": "OtherExpensesIFRS", "order": 6, "label_hint": "その他の費用"},
  {"concept": "OperatingProfitLossIFRS", "order": 7, "label_hint": "営業利益（△損失）"},
  {"concept": "FinanceIncomeIFRS", "order": 8, "label_hint": "金融収益"},
  {"concept": "FinanceCostsIFRS", "order": 9, "label_hint": "金融費用"},
  {"concept": "ShareOfProfitLossOfInvestmentsAccountedForUsingEquityMethodIFRS", "order": 10, "label_hint": "持分法による投資損益"},
  {"concept": "ProfitLossBeforeTaxIFRS", "order": 11, "label_hint": "税引前当期利益"},
  {"concept": "IncomeTaxExpenseIFRS", "order": 12, "label_hint": "法人所得税費用"},
  {"concept": "ProfitLossIFRS", "order": 13, "label_hint": "当期利益（△損失）"},
  {"concept": "ProfitLossAttributableToOwnersOfParentIFRS", "order": 14, "label_hint": "親会社の所有者に帰属する当期利益"},
  {"concept": "ProfitLossAttributableToNonControllingInterestsIFRS", "order": 15, "label_hint": "非支配持分に帰属する当期利益"}
]
```

**注意**: 上記の concept 名は D-1.a.md の Calculation Linkbase 解析結果に基づく暫定値。実装時に `jpigp_cor_2025-11-01.xsd` の要素名を直接検証し、正確な concept 名で更新すること。特に:
- `SellingGeneralAndAdministrativeExpensesIFRS` の存在を XSD で確認
- `OtherIncomeIFRS` / `OtherExpensesIFRS` の存在を確認
- `ShareOfProfitLossOfInvestmentsAccountedForUsingEquityMethodIFRS` の正確な名称を確認
- `IncomeTaxExpenseIFRS` の正確な名称を確認
- 帰属利益の IFRS concept 名を確認

**検証方法**: 環境変数 `EDINET_TAXONOMY_ROOT` を設定し、`docs/QAs/scripts/D-1.ifrs_concepts.py` を実行して Calculation Linkbase の完全な階層を確認する。以下のコマンドで WSL から実行可能:

```bash
EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 uv run docs/QAs/scripts/D-1.ifrs_concepts.py
```

### 4.2 `src/edinet/xbrl/data/bs_ifrs.json`

IFRS 貸借対照表の科目定義。M-1 対応で Lane 3 と同程度の網羅性を目標:

```json
[
  {"concept": "CurrentAssetsIFRS", "order": 1, "label_hint": "流動資産"},
  {"concept": "NoncurrentAssetsIFRS", "order": 2, "label_hint": "非流動資産"},
  {"concept": "PropertyPlantAndEquipmentIFRS", "order": 3, "label_hint": "有形固定資産"},
  {"concept": "IntangibleAssetsIFRS", "order": 4, "label_hint": "無形資産"},
  {"concept": "AssetsIFRS", "order": 5, "label_hint": "資産合計"},
  {"concept": "CurrentLiabilitiesIFRS", "order": 6, "label_hint": "流動負債"},
  {"concept": "NoncurrentLiabilitiesIFRS", "order": 7, "label_hint": "非流動負債"},
  {"concept": "LiabilitiesIFRS", "order": 8, "label_hint": "負債合計"},
  {"concept": "IssuedCapitalIFRS", "order": 9, "label_hint": "資本金"},
  {"concept": "CapitalSurplusIFRS", "order": 10, "label_hint": "資本剰余金"},
  {"concept": "RetainedEarningsIFRS", "order": 11, "label_hint": "利益剰余金"},
  {"concept": "TreasurySharesIFRS", "order": 12, "label_hint": "自己株式"},
  {"concept": "EquityAttributableToOwnersOfParentIFRS", "order": 13, "label_hint": "親会社の所有者に帰属する持分"},
  {"concept": "NonControllingInterestsIFRS", "order": 14, "label_hint": "非支配持分"},
  {"concept": "EquityIFRS", "order": 15, "label_hint": "資本合計"}
]
```

**注意**: 上記は暫定値。M-1 で追加した明細行の concept 名は XSD 検証で確定すること。IFRS B/S は J-GAAP B/S と構造が異なる:
- J-GAAP の「固定資産」→ IFRS では「非流動資産」（`NoncurrentAssetsIFRS`）
- J-GAAP の「純資産」→ IFRS では「資本」（`EquityIFRS`）
- J-GAAP の「株主資本」/「その他の包括利益累計額」→ IFRS では「親会社の所有者に帰属する持分」
- J-GAAP の「繰延資産」→ IFRS に該当カテゴリなし

実装時に `jpigp_ac_2025-11-01_cal_bs.xml`（Calculation Linkbase）を解析して正確な concept 名を確認すること。

### 4.3 `src/edinet/xbrl/data/cf_ifrs.json`

IFRS キャッシュフロー計算書の科目定義:

```json
[
  {"concept": "CashFlowsFromUsedInOperatingActivitiesIFRS", "order": 1, "label_hint": "営業活動によるキャッシュ・フロー"},
  {"concept": "CashFlowsFromUsedInInvestingActivitiesIFRS", "order": 2, "label_hint": "投資活動によるキャッシュ・フロー"},
  {"concept": "CashFlowsFromUsedInFinancingActivitiesIFRS", "order": 3, "label_hint": "財務活動によるキャッシュ・フロー"},
  {"concept": "EffectOfExchangeRateChangesOnCashAndCashEquivalentsIFRS", "order": 4, "label_hint": "現金及び現金同等物に係る換算差額"},
  {"concept": "NetIncreaseDecreaseInCashAndCashEquivalentsIFRS", "order": 5, "label_hint": "現金及び現金同等物の純増減額"},
  {"concept": "CashAndCashEquivalentsAtBeginningOfPeriodIFRS", "order": 6, "label_hint": "現金及び現金同等物の期首残高"},
  {"concept": "CashAndCashEquivalentsAtEndOfPeriodIFRS", "order": 7, "label_hint": "現金及び現金同等物の期末残高"}
]
```

**注意**: 上記は暫定値。IFRS CF は J-GAAP CF と名称が異なる可能性がある。`jpigp_ac_2025-11-01_cal_cf.xml` を解析して正確な concept 名を確認すること。

### 4.4 JSON フォーマットの設計根拠

- 既存の `pl_jgaap.json` / `bs_jgaap.json` / `cf_jgaap.json` と**同一の `{"concept", "order", "label_hint"}` フォーマット**。これにより `statements.py` が JSON のロードと concept マッチングのロジックを J-GAAP / IFRS で共用可能
- **JSON は主データソースではない**: 主データソースは Python コード内の `IFRSConceptMapping` タプル（セクション 7）。JSON は `statements.py` への段階的統合用のレガシー互換フォーマット
- `to_legacy_concept_list()` が Python データから同等の出力を生成するため、JSON ファイルとの整合性はテスト（T29-T31）で検証する
- `data/` ディレクトリに配置する理由: 既存の J-GAAP JSON と同一ディレクトリに集約し、ディスカバリを容易にする

---

## 5. 公開 API

### 5.1 `__all__` 定義

```python
__all__ = [
    "IFRSConceptMapping",
    "IFRSProfile",
    "NAMESPACE_MODULE_GROUP",
    "lookup",
    "canonical_key",
    "reverse_lookup",
    "mappings_for_statement",
    "all_mappings",
    "all_canonical_keys",
    "ifrs_specific_concepts",
    "load_ifrs_pl_concepts",
    "load_ifrs_bs_concepts",
    "load_ifrs_cf_concepts",
    "get_ifrs_concept_set",
    "ifrs_to_jgaap_map",
    "jgaap_to_ifrs_map",
    "is_ifrs_module",
    "get_profile",
    "to_legacy_concept_list",
]
```

### 5.2 モジュール定数

```python
NAMESPACE_MODULE_GROUP: str = "jpigp"
"""IFRS 財務諸表の名前空間モジュールグループ。

Wave 1 L5 の classify_namespace() が返す NamespaceInfo.module_group
と照合して IFRS 科目かどうかを判定するために使用する。
"""

_IFRS_MODULE_GROUPS: frozenset[str] = frozenset({"jpigp"})
"""IFRS に関連するモジュールグループの集合。"""
```

### 5.3 ルックアップ関数（Lane 3 と対称）

```python
def lookup(concept: str) -> IFRSConceptMapping | None:
    """IFRS concept ローカル名からマッピング情報を取得する。

    Args:
        concept: jpigp_cor のローカル名（例: ``"RevenueIFRS"``）。

    Returns:
        IFRSConceptMapping。登録されていない concept の場合は None。
    """

def canonical_key(concept: str) -> str | None:
    """IFRS concept ローカル名を正規化キーにマッピングする。

    ``lookup()`` の簡易版。正規化キーのみを返す。

    Args:
        concept: jpigp_cor のローカル名。

    Returns:
        正規化キー文字列。登録されていない concept の場合は None。
    """

def reverse_lookup(key: str) -> IFRSConceptMapping | None:
    """正規化キーから IFRS の IFRSConceptMapping を取得する（逆引き）。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        IFRSConceptMapping。該当する IFRS concept がない場合は None。
    """
```

### 5.4 一覧取得関数

```python
def mappings_for_statement(
    statement_type: StatementType,
) -> tuple[IFRSConceptMapping, ...]:
    """指定した財務諸表タイプの IFRS マッピングを返す。

    display_order 順でソート済み。

    Args:
        statement_type: INCOME_STATEMENT / BALANCE_SHEET / CASH_FLOW_STATEMENT。

    Returns:
        IFRSConceptMapping のタプル（display_order 昇順）。
    """

def get_ifrs_concept_set(statement_type: StatementType) -> frozenset[str]:
    """指定された財務諸表タイプの IFRS concept 名の集合を返す。

    LineItem の concept 名がこの集合に含まれるかを高速に判定するために使用する。

    Args:
        statement_type: 財務諸表タイプ。

    Returns:
        concept ローカル名の frozenset。
    """
```

個別アクセス用の便利関数（`PL` / `BS` / `CF` 略称を使用。`StatementType` は `INCOME_STATEMENT` / `BALANCE_SHEET` / `CASH_FLOW_STATEMENT` だが、開発体験の向上のため略称で提供する）:

```python
def load_ifrs_pl_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 損益計算書の科目定義を返す。"""
    return mappings_for_statement(StatementType.INCOME_STATEMENT)

def load_ifrs_bs_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 貸借対照表の科目定義を返す。"""
    return mappings_for_statement(StatementType.BALANCE_SHEET)

def load_ifrs_cf_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS キャッシュフロー計算書の科目定義を返す。"""
    return mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)

def all_mappings() -> tuple[IFRSConceptMapping, ...]:
    """全 IFRSConceptMapping を返す（PL → BS → CF 順）。

    Returns:
        全 IFRSConceptMapping のタプル。
    """
    return _ALL_MAPPINGS

def all_canonical_keys() -> frozenset[str]:
    """定義されている全 canonical_key の集合を返す。

    「この key は IFRS で定義されているか」の高速判定に使用。
    モジュールレベルで事前構築済みの frozenset を返す。

    Returns:
        正規化キーのフローズンセット。
    """
    return _ALL_CANONICAL_KEYS

def ifrs_specific_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 固有の概念（J-GAAP に対応概念がないもの）を返す。

    対象科目: 金融収益（FinanceIncomeIFRS）、金融費用（FinanceCostsIFRS）、
    その他の収益（OtherIncomeIFRS）、その他の費用（OtherExpensesIFRS）等。

    Returns:
        ``is_ifrs_specific=True`` の IFRSConceptMapping のタプル。
    """
    return tuple(m for m in _ALL_MAPPINGS if m.is_ifrs_specific)
```

### 5.5 名前空間判定関数

```python
def is_ifrs_module(module_group: str) -> bool:
    """module_group が IFRS 固有のモジュールに属するかを判定する。

    注意: IFRS 企業でも jppfs_cor はディメンション要素等で
    併用されるため（D-1）、この関数の結果だけで会計基準を
    断定してはならない。会計基準の判別は standards/detect を使用すること。

    NOTE: jpdei / jpcrp は J-GAAP / IFRS 両方で使用される共通モジュール。
    Lane 3 の is_jgaap_module() は jpdei/jpcrp を True と判定するが、
    本関数は jpigp のみを True と判定する。この非対称性は Wave 3 の
    normalize で会計基準判別ロジックが吸収する。

    Args:
        module_group: _namespaces.classify_namespace() で取得した
            NamespaceInfo.module_group の値。

    Returns:
        IFRS 固有のモジュールグループであれば True。
    """
    return module_group in _IFRS_MODULE_GROUPS
```

### 5.6 プロファイル取得関数

```python
def get_profile() -> IFRSProfile:
    """IFRS 会計基準のプロファイルを返す。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に取得する際のエントリーポイント。Lane 3 の get_profile() と対称。

    Returns:
        IFRSProfile。
    """
```

### 5.7 レガシー互換関数

```python
def to_legacy_concept_list(
    statement_type: StatementType,
) -> list[dict[str, object]]:
    """現行 JSON 互換のフォーマットに変換する。

    ``statements.py`` の ``_load_concept_definitions()`` が返す形式
    と同一:  ``[{"concept": str, "order": int, "label_hint": str}, ...]``

    Wave 3 L1 での ``statements.py`` 統合時に
    ``_load_concept_definitions()`` を段階的に置換するためのブリッジ。
    Lane 3 の ``to_legacy_concept_list()`` と対称。

    Args:
        statement_type: INCOME_STATEMENT / BALANCE_SHEET / CASH_FLOW_STATEMENT。

    Returns:
        JSON 互換のリスト。display_order 順。
    """
```

### 5.8 IFRS ↔ J-GAAP マッピング（補助 API）

> **変更点（第3版フィードバック H-1 A案）**: `IFRSMapping` を廃止し、マッピング情報を `IFRSConceptMapping.jgaap_concept` / `.mapping_note` に統合した。`get_ifrs_jgaap_mappings()` は廃止。`ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` は `_ALL_MAPPINGS` から直接導出する。

```python
def ifrs_to_jgaap_map() -> dict[str, str | None]:
    """IFRS concept 名 → J-GAAP concept 名の辞書を返す（補助）。

    _ALL_MAPPINGS の jgaap_concept フィールドから自動生成。
    IFRS 固有の科目（J-GAAP に対応なし）は None にマッピングされる。

    Returns:
        IFRS concept 名をキー、J-GAAP concept 名（または None）を値とする辞書。

    Example:
        >>> m = ifrs_to_jgaap_map()
        >>> m["RevenueIFRS"]
        'NetSales'
        >>> m["FinanceIncomeIFRS"]
        None
    """
    return {m.concept: m.jgaap_concept for m in _ALL_MAPPINGS}

def jgaap_to_ifrs_map() -> dict[str, str | None]:
    """J-GAAP concept 名 → IFRS concept 名の辞書を返す（補助）。

    キーには以下が含まれる:
    - _ALL_MAPPINGS で jgaap_concept が定義されている J-GAAP concept
      （値は IFRS concept 名）
    - §7.8 の _JGAAP_ONLY_CONCEPTS に含まれる J-GAAP 固有科目
      （値は None）

    Lane 3 の KPI 概念（EPS / BPS 等）は含まない（§1 非ゴール参照）。

    Returns:
        J-GAAP concept 名をキー、IFRS concept 名（または None）を値とする辞書。

    Example:
        >>> m = jgaap_to_ifrs_map()
        >>> m["NetSales"]
        'RevenueIFRS'
        >>> m["OrdinaryIncome"]
        None
    """
```

**設計根拠**:
- **Lane 3 との API 対称性**: `lookup()` / `reverse_lookup()` / `mappings_for_statement()` パターンを Lane 3 と共有。Wave 3 の normalize が同一パターンで全会計基準モジュールを呼び出せる
- `canonical_key` が主要ルックアップ手段。`ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` は補助 API として維持
- `to_legacy_concept_list()` は Wave 3 での段階的移行ブリッジ（Lane 3 と同様）
- `tuple` で返す理由: immutable であり frozen dataclass のコンテナとして自然
- キャッシュ: 既存コードに合わせて `@functools.cache` を使用（`lru_cache` ではなく）
- `IFRSMapping` 廃止理由: `IFRSConceptMapping` に `jgaap_concept` / `mapping_note` を統合することで二重管理を排除（H-1 A案）

---

## 6. マッピングデータ

### 6.1 PL マッピング（canonical_key 付き）

D-1.a.md の「主要勘定科目の J-GAAP / IFRS 対応表」に基づく。`canonical_key` は Lane 3 §5.2 の J-GAAP 正規化キーと合意済みの値を使用。IFRS 固有科目には新規キーを追加。

| IFRS (`jpigp_cor`) | canonical_key | J-GAAP (`jppfs_cor`) | IFRS ラベル | J-GAAP ラベル | is_ifrs_specific | is_total | 備考 |
|---|---|---|---|---|---|---|---|
| `RevenueIFRS` | `revenue` | `NetSales` | 売上収益 | 売上高 | False | False | |
| `CostOfSalesIFRS` | `cost_of_sales` | `CostOfSales` | 売上原価 | 売上原価 | False | False | |
| `GrossProfitIFRS` | `gross_profit` | `GrossProfit` | 売上総利益 | 売上総利益 | False | **True** | |
| `SellingGeneralAndAdministrativeExpensesIFRS` | `sga_expenses` | `SellingGeneralAndAdministrativeExpenses` | 販売費及び一般管理費 | 販売費及び一般管理費 | False | False | |
| `OtherIncomeIFRS` | `other_income_ifrs` | _(なし)_ | その他の収益 | — | **True** | False | IFRS 固有 |
| `OtherExpensesIFRS` | `other_expenses_ifrs` | _(なし)_ | その他の費用 | — | **True** | False | IFRS 固有 |
| `OperatingProfitLossIFRS` | `operating_income` | `OperatingIncome` | 営業利益（△損失） | 営業利益 | False | **True** | IFRS は損失も含む |
| `FinanceIncomeIFRS` | `finance_income` | _(なし)_ | 金融収益 | — | **True** | False | IFRS 固有。J-GAAP の営業外収益の一部に相当 |
| `FinanceCostsIFRS` | `finance_costs` | _(なし)_ | 金融費用 | — | **True** | False | IFRS 固有。J-GAAP の営業外費用の一部に相当 |
| `ShareOfProfitLossOfInvestmentsAccountedForUsingEquityMethodIFRS` | `equity_method_income_ifrs` | _(なし)_ | 持分法による投資損益 | — | **True** | False | IFRS の PL 独自表示 |
| `ProfitLossBeforeTaxIFRS` | `income_before_tax` | `IncomeBeforeIncomeTaxes` | 税引前当期利益 | 税引前当期純利益 | False | **True** | J-GAAP の経常利益に最も近い |
| `IncomeTaxExpenseIFRS` | `income_taxes` | `IncomeTaxes` | 法人所得税費用 | 法人税等 | False | False | |
| `ProfitLossIFRS` | `net_income` | `ProfitLoss` | 当期利益（△損失） | 当期純利益 | False | **True** | |
| `ProfitLossAttributableToOwnersOfParentIFRS` | `net_income_parent` | `ProfitLossAttributableToOwnersOfParent` | 親会社の所有者に帰属する当期利益 | 親会社株主に帰属する当期純利益 | False | **True** | |
| `ProfitLossAttributableToNonControllingInterestsIFRS` | `net_income_minority` | `ProfitLossAttributableToNonControllingInterests` | 非支配持分に帰属する当期利益 | 非支配株主に帰属する当期純利益 | False | False | J-GAAP にも同名概念あり（M-2 修正） |
| _(なし)_ | `non_operating_income` | `NonOperatingIncome` | — | 営業外収益 | — | — | J-GAAP 固有 |
| _(なし)_ | `non_operating_expenses` | `NonOperatingExpenses` | — | 営業外費用 | — | — | J-GAAP 固有 |
| _(なし)_ | `ordinary_income` | `OrdinaryIncome` | — | 経常利益 | — | — | **J-GAAP 固有**。IFRS に該当概念なし |
| _(なし)_ | `extraordinary_income` | `ExtraordinaryIncome` | — | 特別利益 | — | — | J-GAAP 固有 |
| _(なし)_ | `extraordinary_loss` | `ExtraordinaryLoss` | — | 特別損失 | — | — | J-GAAP 固有 |
| _(なし)_ | `income_taxes_deferred` | `IncomeTaxesDeferred` | — | 法人税等調整額 | — | — | **IFRS 非対応**。IFRS では `IncomeTaxExpenseIFRS` に集約されるため独立行として存在しない。Lane 3 の `is_jgaap_specific=False` は J-GAAP タクソノミ内での標準性を示す（IFRS 対応の有無とは独立）（H-3 修正） |

### 6.2 BS マッピング（canonical_key 付き、M-1 対応で Lane 3 と同程度の網羅性を目標）

> **変更点（第3版フィードバック M-1 A案）**: Lane 3 BS は 20 concepts を定義している。IFRS BS も Lane 3 と同程度の網羅性を確保するため、明細行（有形固定資産、無形資産、資本金、利益剰余金等）を暫定的に追加する。concept 名は `jpigp_cor` XSD で要確認（暫定値）。

| IFRS (`jpigp_cor`) | canonical_key | J-GAAP (`jppfs_cor`) | IFRS ラベル | J-GAAP ラベル | is_total | 備考 |
|---|---|---|---|---|---|---|
| `CurrentAssetsIFRS` | `current_assets` | `CurrentAssets` | 流動資産 | 流動資産 | **True** | |
| `NoncurrentAssetsIFRS` | `noncurrent_assets` | `NoncurrentAssets` | 非流動資産 | 固定資産 | **True** | 用語が異なる |
| `PropertyPlantAndEquipmentIFRS` | `ppe` | `PropertyPlantAndEquipment` | 有形固定資産 | 有形固定資産 | **True** | **M-1 追加**。暫定 concept 名、XSD 要確認 |
| `IntangibleAssetsIFRS` | `intangible_assets` | `IntangibleAssets` | 無形資産 | 無形固定資産 | **True** | **M-1 追加**。IFRS では「無形資産」、暫定 concept 名 |
| `AssetsIFRS` | `total_assets` | `Assets` | 資産合計 | 資産合計 | **True** | IFRS では Assets = Liabilities + Equity |
| `CurrentLiabilitiesIFRS` | `current_liabilities` | `CurrentLiabilities` | 流動負債 | 流動負債 | **True** | |
| `NoncurrentLiabilitiesIFRS` | `noncurrent_liabilities` | `NoncurrentLiabilities` | 非流動負債 | 固定負債 | **True** | 用語が異なる |
| `LiabilitiesIFRS` | `total_liabilities` | `Liabilities` | 負債合計 | 負債合計 | **True** | |
| `IssuedCapitalIFRS` | `capital_stock` | `CapitalStock` | 資本金 | 資本金 | False | **M-1 追加**。暫定 concept 名、XSD 要確認 |
| `CapitalSurplusIFRS` | `capital_surplus` | `CapitalSurplus` | 資本剰余金 | 資本剰余金 | False | **M-1 追加**。暫定 concept 名、XSD 要確認 |
| `RetainedEarningsIFRS` | `retained_earnings` | `RetainedEarnings` | 利益剰余金 | 利益剰余金 | False | **M-1 追加**。暫定 concept 名、XSD 要確認 |
| `TreasurySharesIFRS` | `treasury_stock` | `TreasuryStock` | 自己株式 | 自己株式 | False | **M-1 追加**。暫定 concept 名、XSD 要確認 |
| `EquityAttributableToOwnersOfParentIFRS` | `equity_parent` | _(近似: `ShareholdersEquity`)_ | 親会社の所有者に帰属する持分 | — | **True** | J-GAAP「株主資本」に近いが等価ではない。IFRS には「株主資本」概念がない。近似対応は normalize の責務 |
| `NonControllingInterestsIFRS` | `minority_interests` | `NonControllingInterests` | 非支配持分 | 非支配株主持分 | False | |
| `EquityIFRS` | `net_assets` | `NetAssets` | 資本合計 | 純資産合計 | **True** | IFRS は「資本」、J-GAAP は「純資産」 |
| _(なし)_ | `deferred_assets` | `DeferredAssets` | — | 繰延資産 | — | J-GAAP 固有 |
| _(なし)_ | `investments_and_other` | `InvestmentsAndOtherAssets` | — | 投資その他の資産 | — | J-GAAP 固有の小計。IFRS では非流動資産の内訳として個別表示 |
| _(なし)_ | `shareholders_equity` | `ShareholdersEquity` | — | 株主資本合計 | — | J-GAAP 固有の小計 |
| _(なし)_ | `oci_accumulated` | `ValuationAndTranslationAdjustments` | — | その他の包括利益累計額 | — | J-GAAP 固有（IFRS は OCI を包括利益計算書で処理） |
| _(なし)_ | `stock_options` | `SubscriptionRightsToShares` | — | 新株予約権 | — | J-GAAP 固有 |
| _(なし)_ | `liabilities_and_net_assets` | `LiabilitiesAndNetAssets` | — | 負債純資産合計 | — | J-GAAP 固有。IFRS では `AssetsIFRS` がこれに相当（等式 A=L+E） |

> **NOTE（M-1）**: M-1 で追加した 5 concept（`PropertyPlantAndEquipmentIFRS`, `IntangibleAssetsIFRS`, `IssuedCapitalIFRS`, `CapitalSurplusIFRS`, `RetainedEarningsIFRS`, `TreasurySharesIFRS`）は暫定 concept 名である。実装 Phase 1 で `jpigp_cor_2025-11-01.xsd` を検証し、正確な名称に更新すること。存在しない concept があれば §11 に記録し BS テーブルから削除する。Lane 3 BS の `InvestmentsAndOtherAssets`（投資その他の資産）に対応する IFRS concept も XSD で確認すること。

### 6.3 CF マッピング（canonical_key 付き、全 7 エントリ）

| IFRS (`jpigp_cor`) | canonical_key | J-GAAP (`jppfs_cor`) | IFRS ラベル | J-GAAP ラベル | is_total | 備考 |
|---|---|---|---|---|---|---|
| `CashFlowsFromUsedInOperatingActivitiesIFRS` | `operating_cf` | `NetCashProvidedByUsedInOperatingActivities` | 営業活動によるキャッシュ・フロー | 営業活動によるキャッシュ・フロー | **True** | |
| `CashFlowsFromUsedInInvestingActivitiesIFRS` | `investing_cf` | `NetCashProvidedByUsedInInvestmentActivities` | 投資活動によるキャッシュ・フロー | 投資活動によるキャッシュ・フロー | **True** | |
| `CashFlowsFromUsedInFinancingActivitiesIFRS` | `financing_cf` | `NetCashProvidedByUsedInFinancingActivities` | 財務活動によるキャッシュ・フロー | 財務活動によるキャッシュ・フロー | **True** | |
| `EffectOfExchangeRateChangesOnCashAndCashEquivalentsIFRS` | `fx_effect_on_cash` | `EffectOfExchangeRateChangeOnCashAndCashEquivalents` | 現金及び現金同等物に係る換算差額 | 現金及び現金同等物に係る換算差額 | False | |
| `NetIncreaseDecreaseInCashAndCashEquivalentsIFRS` | `net_change_in_cash` | `NetIncreaseDecreaseInCashAndCashEquivalents` | 現金及び現金同等物の純増減額 | 現金及び現金同等物の増減額 | **True** | |
| `CashAndCashEquivalentsAtBeginningOfPeriodIFRS` | `cash_beginning` | `CashAndCashEquivalentsAtBeginningOfPeriod` | 現金及び現金同等物の期首残高 | 現金及び現金同等物の期首残高 | False | 概念的には instant（時点残高）だが duration として報告される |
| `CashAndCashEquivalentsAtEndOfPeriodIFRS` | `cash_end` | `CashAndCashEquivalentsAtEndOfPeriod` | 現金及び現金同等物の期末残高 | 現金及び現金同等物の期末残高 | **True** | 概念的には instant（時点残高）だが duration として報告される |

> **NOTE**: Lane 3 は CF に 8 concept を定義（`consolidation_scope_change_cash` を含む）。Lane 4 は 7 concept で、連結範囲変動に伴うキャッシュ増減に相当する IFRS 独立 concept を含めていない。実装時に `jpigp_cor` XSD で相当する concept（`IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeInScopeOfConsolidationIFRS` 等）の有無を確認すること。存在する場合は 8 番目のエントリとして追加する。存在しない場合は §11 の設計判断として記録する。

**注意**: 上記マッピングの concept 名は暫定値。実装時に `jpigp_cor` XSD のローカル名を直接検証し、正確な名称に更新すること。

---

## 7. 内部実装

### 7.1 マッピングレジストリ（Python コード）

Lane 3 と同様、全マッピングをモジュールレベルのタプルとして定義する（JSON ファイルではなく Python コードが主データソース）:

```python
import functools

_PL_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    IFRSConceptMapping(
        concept="RevenueIFRS",
        canonical_key="revenue",
        label_ja="売上収益",
        label_en="Revenue",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=1,
        jgaap_concept="NetSales",
    ),
    IFRSConceptMapping(
        concept="CostOfSalesIFRS",
        canonical_key="cost_of_sales",
        label_ja="売上原価",
        label_en="Cost of sales",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=2,
        jgaap_concept="CostOfSales",
    ),
    IFRSConceptMapping(
        concept="FinanceIncomeIFRS",
        canonical_key="finance_income",
        label_ja="金融収益",
        label_en="Finance income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_ifrs_specific=True,
        display_order=8,
        jgaap_concept=None,
        mapping_note="IFRS 固有。J-GAAP の営業外収益の一部に相当",
    ),
    # ... 全 15 概念を Section 6.1 に基づいて定義
    # jgaap_concept / mapping_note を各エントリに含める（H-1 A案）
)

_BS_MAPPINGS: tuple[IFRSConceptMapping, ...] = (...)  # 全 15 概念（M-1 拡張後）
_CF_MAPPINGS: tuple[IFRSConceptMapping, ...] = (...)  # 全 7 概念

_ALL_MAPPINGS: tuple[IFRSConceptMapping, ...] = (
    *_PL_MAPPINGS, *_BS_MAPPINGS, *_CF_MAPPINGS,
)

# M-5: モジュールレベルで事前構築
_ALL_CANONICAL_KEYS: frozenset[str] = frozenset(
    m.canonical_key for m in _ALL_MAPPINGS
)
```

### 7.2 インデックス辞書（Lane 3 と同パターン）

```python
# concept ローカル名 → IFRSConceptMapping
_CONCEPT_INDEX: dict[str, IFRSConceptMapping] = {
    m.concept: m for m in _ALL_MAPPINGS
}

# canonical_key → IFRSConceptMapping（逆引き）
_CANONICAL_INDEX: dict[str, IFRSConceptMapping] = {
    m.canonical_key: m for m in _ALL_MAPPINGS
}

# statement_type → tuple[IFRSConceptMapping, ...]
_STATEMENT_INDEX: dict[StatementType, tuple[IFRSConceptMapping, ...]] = {
    StatementType.INCOME_STATEMENT: _PL_MAPPINGS,
    StatementType.BALANCE_SHEET: _BS_MAPPINGS,
    StatementType.CASH_FLOW_STATEMENT: _CF_MAPPINGS,
}
```

### 7.3 整合性検証（ロード時実行）

Lane 3 と同じパターンで、`assert` ではなく `ValueError` を使用する。`python -O`（最適化モード）でもスキップされない:

```python
def _validate_registry() -> None:
    """マッピングレジストリの整合性を検証する。

    モジュールロード時に自動実行される。
    """
    if len(_CONCEPT_INDEX) != len(_ALL_MAPPINGS):
        raise ValueError("concept ローカル名に重複があります")
    if len(_CANONICAL_INDEX) != len(_ALL_MAPPINGS):
        raise ValueError("canonical_key に重複があります")
    for st, mappings in _STATEMENT_INDEX.items():
        orders = [m.display_order for m in mappings]
        if len(set(orders)) != len(orders):
            raise ValueError(f"{st.value} の display_order に重複があります")
    valid_period_types = {"instant", "duration"}
    for m in _ALL_MAPPINGS:
        if m.period_type not in valid_period_types:
            raise ValueError(
                f"{m.concept} の period_type が不正です: {m.period_type!r}"
            )

_validate_registry()
```

### 7.4 JSON データファイルの読み込み（レガシー互換用）

JSON ファイルは `statements.py` への直接投入用に残す。読み込みは `importlib.resources` パターンを使用（既存の `statements.py` と統一）:

```python
import importlib.resources
import json

@functools.cache
def _load_json(filename: str) -> list[dict[str, object]]:
    """JSON データファイルを importlib.resources 経由で読み込む。"""
    ref = importlib.resources.files("edinet.xbrl.data").joinpath(filename)
    with importlib.resources.as_file(ref) as path:
        return json.loads(path.read_text(encoding="utf-8"))
```

### 7.5 マッピングデータの統合（H-1 A案）

> **変更点（H-1 A案）**: 旧 §7.5 の `_IFRS_JGAAP_MAPPINGS`（`IFRSMapping` タプル）は廃止。マッピング情報は §7.1 の `IFRSConceptMapping` の `jgaap_concept` / `mapping_note` フィールドに統合済み。`ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` は `_ALL_MAPPINGS` から直接導出する。

### 7.6 to_legacy_concept_list の実装

```python
def to_legacy_concept_list(
    statement_type: StatementType,
) -> list[dict[str, object]]:
    mappings = _STATEMENT_INDEX.get(statement_type, ())
    return [
        {
            "concept": m.concept,
            "order": m.display_order,
            "label_hint": m.label_ja,
        }
        for m in mappings
    ]
```

### 7.7 IFRSProfile の構築

```python
_PROFILE = IFRSProfile(
    standard_id="ifrs",
    display_name_ja="国際財務報告基準",
    display_name_en="IFRS",
    module_groups=_IFRS_MODULE_GROUPS,
    canonical_key_count=len(_ALL_MAPPINGS),
    has_ordinary_income=False,
    has_extraordinary_items=False,
)
```

### 7.8 J-GAAP 固有科目リスト

```python
# SYNC: この集合は Lane 3 の is_jgaap_specific=True のデータと一致する必要がある。
# Wave 3 統合時に Lane 3 の jgaap.jgaap_specific_concepts() から自動生成に置換すること。
# 加えて、IFRS に独立 concept がないが J-GAAP タクソノミ内では標準的な科目
# （IncomeTaxesDeferred 等の「IFRS 非対応」科目）も含む。
_JGAAP_ONLY_CONCEPTS: frozenset[str] = frozenset({
    # Lane 3 is_jgaap_specific=True の 5 概念
    "OrdinaryIncome",
    "NonOperatingIncome",
    "NonOperatingExpenses",
    "ExtraordinaryIncome",
    "ExtraordinaryLoss",
    # IFRS 非対応（is_jgaap_specific=False だが IFRS に独立 concept なし）
    "IncomeTaxesDeferred",       # IFRS では IncomeTaxExpenseIFRS に内包
    # J-GAAP 固有の BS 構造
    "DeferredAssets",
    "ShareholdersEquity",
    "ValuationAndTranslationAdjustments",
    "SubscriptionRightsToShares",
    "LiabilitiesAndNetAssets",
    "InvestmentsAndOtherAssets",  # M-1 で追加（J-GAAP 固有の小計）
})
```

---

## 8. ファイル構成

### 作成ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/standards/ifrs.py` | **新規** | `IFRSConceptMapping`（`jgaap_concept`/`mapping_note` 統合済み）, `IFRSProfile` dataclass + `lookup()`, `canonical_key()`, `reverse_lookup()`, `mappings_for_statement()`, `get_ifrs_concept_set()`, `ifrs_to_jgaap_map()`, `jgaap_to_ifrs_map()`, `is_ifrs_module()`, `get_profile()`, `to_legacy_concept_list()`, `NAMESPACE_MODULE_GROUP` 定数, `__all__` |
| `src/edinet/xbrl/data/pl_ifrs.json` | **新規** | IFRS PL 科目定義（15 エントリ、3 フィールド形式: レガシー互換） |
| `src/edinet/xbrl/data/bs_ifrs.json` | **新規** | IFRS BS 科目定義（15 エントリ、M-1 拡張後。3 フィールド形式） |
| `src/edinet/xbrl/data/cf_ifrs.json` | **新規** | IFRS CF 科目定義（7 エントリ、3 フィールド形式） |
| `tests/test_xbrl/test_standards_ifrs.py` | **新規** | 単体テスト |

### 既存モジュールへの影響

- **影響なし**: 全て新規ファイル。既存の import 文・テスト・データファイルに一切変更を加えない
- 既存の `pl_jgaap.json` / `bs_jgaap.json` / `cf_jgaap.json` は変更しない
- `statements.py` は変更しない（IFRS 統合は Wave 3 L1 の責務）

---

## 9. テスト計画

テストは Detroit 派（古典派）のスタイルで、内部実装に依存せず公開 API のみをテストする。

### 9.1 テスト戦略

- JSON データファイルの存在・フォーマットをテスト
- `load_ifrs_concepts()` の戻り値型・フィールド値をテスト
- マッピングの双方向整合性をテスト
- IFRS 固有の構造的特徴（OrdinaryIncome の不存在等）をアサーション

### 9.2 テストケース

#### P0（必須）— ルックアップ・基本動作

| # | テスト名 | 概要 |
|---|---------|------|
| T1 | `test_lookup_revenue_ifrs` | `lookup("RevenueIFRS")` → `IFRSConceptMapping(canonical_key="revenue", ...)` |
| T2 | `test_lookup_operating_profit_loss_ifrs` | `lookup("OperatingProfitLossIFRS")` → `canonical_key="operating_income"` |
| T3 | `test_lookup_unknown_returns_none` | `lookup("UnknownConcept")` → `None` |
| T4 | `test_canonical_key_returns_string` | `canonical_key("RevenueIFRS")` → `"revenue"` |
| T5 | `test_canonical_key_unknown_returns_none` | `canonical_key("Unknown")` → `None` |
| T6 | `test_reverse_lookup_revenue` | `reverse_lookup("revenue")` → `IFRSConceptMapping(concept="RevenueIFRS", ...)` |
| T7 | `test_reverse_lookup_unknown_returns_none` | `reverse_lookup("unknown_key")` → `None` |

#### P0 — 一覧取得

| # | テスト名 | 概要 |
|---|---------|------|
| T8 | `test_mappings_for_pl` | `mappings_for_statement(INCOME_STATEMENT)` → 15 件 |
| T9 | `test_mappings_for_bs` | `mappings_for_statement(BALANCE_SHEET)` → 15 件（M-1 拡張後。XSD 検証で変動あり） |
| T10 | `test_mappings_for_cf` | `mappings_for_statement(CASH_FLOW_STATEMENT)` → 7 件 |
| T11 | `test_concept_names_are_unique_per_statement` | 同一 statement_type 内で concept 名が重複しない |
| T12 | `test_concepts_ordered_by_display_order` | 科目定義が display_order フィールドの昇順で並んでいる |

#### P0 — 科目セット

| # | テスト名 | 概要 |
|---|---------|------|
| T13 | `test_get_ifrs_concept_set_is_frozenset` | 戻り値が `frozenset[str]` |
| T14 | `test_ifrs_pl_concept_set_contains_revenue` | PL の concept セットに `RevenueIFRS` が含まれる |
| T15 | `test_ifrs_pl_concept_set_not_contains_ordinary_income` | PL の concept セットに `OrdinaryIncome` が含まれない |
| T16 | `test_ifrs_bs_concept_set_contains_equity` | BS の concept セットに EquityIFRS 相当の concept が含まれる |

#### P0 — IFRS ↔ J-GAAP マッピング（補助）

| # | テスト名 | 概要 |
|---|---------|------|
| T17 | `test_ifrs_to_jgaap_revenue` | `ifrs_to_jgaap_map()["RevenueIFRS"]` == `"NetSales"` |
| T18 | `test_ifrs_to_jgaap_finance_income_is_none` | `ifrs_to_jgaap_map()["FinanceIncomeIFRS"]` is `None` |
| T19 | `test_jgaap_to_ifrs_net_sales` | `jgaap_to_ifrs_map()["NetSales"]` == `"RevenueIFRS"` |
| T20 | `test_jgaap_to_ifrs_ordinary_income_is_none` | `jgaap_to_ifrs_map()["OrdinaryIncome"]` is `None` |
| T21 | `test_mapping_bidirectional_consistency` | `ifrs_to_jgaap(x) == y` なら `jgaap_to_ifrs(y) == x`（None でない場合）。加えて IFRS 固有科目（`ifrs_to_jgaap` の値が None）が `jgaap_to_ifrs` のキーに含まれないことも検証（L-3） |

#### P0 — 定数・プロファイル

| # | テスト名 | 概要 |
|---|---------|------|
| T22 | `test_namespace_module_group_is_jpigp` | `NAMESPACE_MODULE_GROUP == "jpigp"` |
| T23 | `test_is_ifrs_module_jpigp` | `is_ifrs_module("jpigp")` → `True` |
| T24 | `test_is_ifrs_module_jppfs` | `is_ifrs_module("jppfs")` → `False` |
| T25 | `test_profile_standard_id` | `get_profile().standard_id` → `"ifrs"` |
| T26 | `test_profile_has_ordinary_income_false` | `get_profile().has_ordinary_income` → `False` |
| T27 | `test_profile_has_extraordinary_items_false` | `get_profile().has_extraordinary_items` → `False` |

#### P0 — レガシー互換

| # | テスト名 | 概要 |
|---|---------|------|
| T28 | `test_legacy_pl_format_structure` | `to_legacy_concept_list(INCOME_STATEMENT)` の各要素が `{"concept": str, "order": int, "label_hint": str}` 構造 |
| T29 | `test_legacy_pl_matches_json` | `to_legacy_concept_list(INCOME_STATEMENT)` の各要素の全フィールド（`concept`, `order`, `label_hint`）が `pl_ifrs.json` と**完全一致**（L-4） |
| T30 | `test_legacy_bs_matches_json` | `to_legacy_concept_list(BALANCE_SHEET)` の各要素の全フィールドが `bs_ifrs.json` と**完全一致**（L-4） |
| T31 | `test_legacy_cf_matches_json` | `to_legacy_concept_list(CASH_FLOW_STATEMENT)` の各要素の全フィールドが `cf_ifrs.json` と**完全一致**（L-4） |

#### P1（推奨）— IFRS 構造的特徴

| # | テスト名 | 概要 |
|---|---------|------|
| T32 | `test_ifrs_pl_no_ordinary_income_concept` | IFRS PL に "Ordinary" を含む concept がないことを検証 |
| T33 | `test_ifrs_pl_no_extraordinary_concepts` | IFRS PL に "Extraordinary" を含む concept がないことを検証 |
| T34 | `test_ifrs_pl_has_finance_income_and_costs` | IFRS PL に金融収益/費用が存在（`is_ifrs_specific=True`） |
| T35 | `test_ifrs_pl_has_profit_before_tax` | IFRS PL に税引前利益が存在 |
| T36 | `test_ifrs_bs_uses_equity_not_net_assets` | IFRS BS に EquityIFRS 相当が存在し NetAssets は存在しない |

#### P1 — データ整合性

| # | テスト名 | 概要 |
|---|---------|------|
| T37 | `test_all_canonical_keys_unique` | 全 canonical_key がユニーク |
| T38 | `test_all_labels_not_empty` | 全 mapping の `label_ja` / `label_en` が空文字列でない |
| T39 | `test_period_type_bs_is_instant` | BS の全 mapping が `period_type="instant"` |
| T40 | `test_period_type_pl_is_duration` | PL の全 mapping が `period_type="duration"` |
| T41 | `test_display_order_unique_per_statement` | 各 statement_type 内で display_order がユニーク |
| T42 | `test_json_files_exist` | `pl_ifrs.json`, `bs_ifrs.json`, `cf_ifrs.json` が存在する |
| T43 | `test_json_format_matches_jgaap` | IFRS JSON と J-GAAP JSON が同一キー構造（concept, order, label_hint）を持つ |

#### P1 — parametrize テスト

| # | テスト名 | 概要 |
|---|---------|------|
| T44 | `test_mappings_for_all_statement_types` | `INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW_STATEMENT` の全てで正しく返される |
| T45 | `test_jgaap_only_concepts_map_to_none` | `jgaap_to_ifrs_map()` で J-GAAP 固有科目（`OrdinaryIncome`, `NonOperatingIncome`, `ExtraordinaryIncome` 等）が None にマッピングされる |

#### P1 — CF period_type（M-4 追加）

| # | テスト名 | 概要 |
|---|---------|------|
| T46 | `test_period_type_cf_is_duration` | CF の全 mapping が `period_type="duration"` |
| T47 | `test_cash_beginning_end_are_duration` | `cash_beginning` / `cash_end` が `period_type="duration"` であることを明示的に検証（「この科目が duration なのは意図的な設計判断」のドキュメンテーションテスト） |

合計: 47 テスト（旧 36 テストから T29/T30/T31/T34 を削除し、canonical_key / lookup / プロファイル / レガシー互換のテストを追加）

### 9.3 キャッシュクリアの fixture

`functools.cache` を使用する場合、テスト前のクリアのみで十分（yield 後の二重クリアは不要）:

```python
@pytest.fixture(autouse=True)
def _clear_ifrs_cache():
    """テスト間のキャッシュ汚染を防ぐ。"""
    _load_json.cache_clear()
    yield
```

注: `lookup()` / `reverse_lookup()` 等のインデックス辞書はモジュールロード時に構築される静的データのため、キャッシュクリアは不要。`_load_json` のみキャッシュクリア対象。

---

## 10. 後続レーンとの接続点

Lane 4 (standards/ifrs) の出力は以下のレーンで消費される:

| 利用先 | 消費する API | 用途 |
|--------|------------|------|
| **Wave 3 L1 (normalize + statements)** | `load_ifrs_concepts()`, `get_ifrs_concept_set()`, `NAMESPACE_MODULE_GROUP` | IFRS 企業に対する科目定義の選択・statement 組立 |
| **Wave 3 L1 (normalize)** | `ifrs_to_jgaap_map()`, `jgaap_to_ifrs_map()` | 会計基準間の統一表現への正規化 |
| **Wave 2 L2 (detect) [参照のみ]** | `NAMESPACE_MODULE_GROUP` | IFRS 判別の module_group 値の一致確認（実装上は detect が独自に "jpigp" を知っているため直接依存はしない） |

Wave 3 での使用例:

```python
from edinet.financial.standards.detect import detect_accounting_standard, DetailLevel
from edinet.financial.standards import ifrs, jgaap
from edinet.xbrl.dei import AccountingStandard
from edinet.models.financial import StatementType

detected = detect_accounting_standard(parsed.facts)

if detected.standard == AccountingStandard.IFRS:
    # canonical_key で統一アクセス（主要ルックアップ）
    revenue = ifrs.reverse_lookup("revenue")
    # revenue.concept == "RevenueIFRS"

    # 科目セットによるフィルタリング
    pl_concept_set = ifrs.get_ifrs_concept_set(StatementType.INCOME_STATEMENT)
    ifrs_items = [
        item for item in all_items
        if item.concept in pl_concept_set
    ]

    # 各 LineItem の正規化キーを取得
    for item in ifrs_items:
        key = ifrs.canonical_key(item.concept)
        # key == "revenue", "cost_of_sales", etc.

    # J-GAAP 対応の参考情報（補助 API）
    mapping = ifrs.ifrs_to_jgaap_map()
    jgaap_name = mapping.get("RevenueIFRS")  # → "NetSales"

# normalize (Wave 3) での会計基準横断アクセス
def normalize_concept(concept: str, standard: AccountingStandard) -> str | None:
    if standard == AccountingStandard.JAPAN_GAAP:
        return jgaap.canonical_key(concept)
    elif standard == AccountingStandard.IFRS:
        return ifrs.canonical_key(concept)
    return None
```

---

## 11. 設計判断の記録

### Q: なぜ JSON データファイルを新規作成するのか？ Wave 2 L1 (concept_sets) がタクソノミから自動導出するのでは？

**A**: Wave 2 L1 (`concept_sets`) は _pre ファイルからの自動導出を担当するが、Wave 2 の全レーンは並列実行されるため、L1 の成果物に依存してはならない。JSON ファイルは過渡的措置であり、L1 が完成した後に Wave 3 の統合タスクで自動導出結果に置換される。また、IFRS ↔ J-GAAP のマッピングはタクソノミから自動導出できない（概念的対応は人間の判断が必要）ため、マッピングデータは L4 固有の成果物として残る。

### Q: concept 名が D-1.a.md の暫定値のまま実装して問題ないか？

**A**: 実装時に `jpigp_cor_2025-11-01.xsd` の要素名を直接検証することを **必須要件** としている。D-1.a.md の Calculation Linkbase 解析スクリプト（`docs/QAs/scripts/D-1.ifrs_concepts.py`）を実行すれば全 concrete 要素名が得られる。計画書の concept 名はスキーマ構造の指針であり、XSD の実際の要素名が最終的な正解。

### Q: なぜ `IFRSConceptMapping` を独自 dataclass にするのか？ `dict` そのままでよいのでは？

**A**: (1) 型安全性: `entry["concpet"]` のようなタイポを型チェッカーで検出可能。(2) IDE 補完: `.concept`, `.canonical_key`, `.label_ja` 等のフィールド補完が効く。(3) frozen dataclass: 不変性を保証し、意図しない変更を防ぐ。(4) `slots=True`: メモリ効率が `dict` より良い。(5) Lane 3 の `ConceptMapping` と対称的な構造で Wave 3 統合が容易。

### Q: マッピングを JSON ではなく Python コードにハードコードする理由は？

**A**: 科目定義（PL/BS/CF の concept リスト）は「どの concept が存在するか」というデータであり JSON が適切。一方、マッピングは「概念的にどの科目が対応するか」という人間の判断であり、`IFRSMapping` の `note` フィールドや `jgaap_concept=None` のような意味的情報を含む。Python dataclass で定義することで型安全性と可読性を両立できる。また、マッピングの変更頻度は科目定義より低い（会計基準の対応関係は安定）。

### Q: `OrdinaryIncome` への fallback は提供すべきか？ 例えば `ProfitLossBeforeTaxIFRS` を代替として返す機能。

**A**: **このモジュールでは提供しない**。`ifrs_to_jgaap_map()` で `FinanceIncomeIFRS` → `None` を返すように、`jgaap_to_ifrs_map()` で `OrdinaryIncome` → `None` を返すのみ。代替概念のマッピング（「IFRS には経常利益がないので税引前利益で代替する」等）は `standards/normalize` の責務。このモジュールは**事実の記録**（対応がある/ない）に徹し、**解釈や変換**は上位レイヤーに委ねる。

### Q: `load_ifrs_pl_concepts()` のような便利関数は必要か？ `mappings_for_statement(StatementType.INCOME_STATEMENT)` で十分では？

**A**: 両方提供する。`mappings_for_statement(StatementType.INCOME_STATEMENT)` は汎用的で `StatementType` 変数をそのまま渡せる利点がある（Wave 3 のディスパッチロジックに最適）。`load_ifrs_pl_concepts()` は直接的で IDE 補完が効き、テストやドキュメント例に適する。実装コストはほぼゼロ（1 行のラッパー）。

### Q: B/S で `TotalAssetsIFRS` / `LiabilitiesAndNetAssetsIFRS` に相当する concept は存在するか？

**A**: D-1.a.md の調査では「`TotalAssets` → Presentation に存在」とあるが Calculation linkbase での直接対応は未確認。実装時に XSD と BS の Calculation Linkbase (`jpigp_ac_2025-11-01_cal_bs.xml`) を検証して確定すること。IFRS B/S は J-GAAP と異なり「負債純資産合計」ではなく「負債合計 + 資本合計 = 総資産」の等式で構成される（IFRS の基本等式: Assets = Liabilities + Equity）。

### Q: IFRS PL に `income_taxes_deferred`（法人税等調整額）に対応する concept がないのはなぜか？

**A**: IFRS PL では法人税の繰延影響が `IncomeTaxExpenseIFRS`（法人所得税費用）に内包されるケースがあり、独立行として表示されないことがある。Lane 3 PL は 16 概念（`IncomeTaxesDeferred` を含む）、Lane 4 PL は 15 概念。`income_taxes_deferred` は J-GAAP 固有行として §6.1 に記録し、`jgaap_to_ifrs_map()` で `None` を返す。

### Q: CF の `consolidation_scope_change_cash` に相当する IFRS concept は含めないのか？

**A**: Lane 3 は CF に 8 concept（`consolidation_scope_change_cash` を含む）を定義。Lane 4 は暫定的に 7 concept とする。実装時に `jpigp_cor` XSD で相当する concept の有無を確認し:
- 存在する場合 → 8 番目のエントリとして追加（`consolidation_scope_change_cash` キーを共用）
- 存在しない場合 → IFRS CF には連結範囲変動の独立 concept がないため 7 エントリとする旨を本セクションに追記

### Q: `EquityAttributableToOwnersOfParentIFRS` の canonical_key をなぜ `equity_parent` にするのか？

**A**: J-GAAP の `ShareholdersEquity`（株主資本合計）は `shareholders_equity` キーにマッピングされている（Lane 3 §5.3）。IFRS の「親会社の所有者に帰属する持分」は概念的に近いが等価ではない（IFRS には「株主資本」概念自体がない）。同じ canonical_key を使うと Wave 3 normalize で誤った等価性を暗示する。新規キー `equity_parent` を定義し、`equity_parent` ↔ `shareholders_equity` の近似対応は normalize の責務とする。

### Q: `is_jgaap_specific` と「IFRS 非対応」の違いは？（H-3 追加）

**A**: `is_jgaap_specific=True` は「この概念が J-GAAP の構造に固有であり、他の会計基準に概念的な対応物が存在しない」ことを意味する（例: 経常利益 `OrdinaryIncome`）。一方「IFRS 非対応」は「IFRS タクソノミに独立の concept がないが、他の concept に内包される形で表現可能」なケースを含む（例: 法人税等調整額 `IncomeTaxesDeferred` → `IncomeTaxExpenseIFRS` に内包）。両者は異なる概念であり、normalize レイヤーで区別して処理する。

### Q: なぜ `IFRSMapping` を廃止して `IFRSConceptMapping` に統合するのか？（H-1 追加）

**A**: 第3版フィードバックの分析により、`IFRSMapping` の全情報は `IFRSConceptMapping` + `jgaap_concept` フィールドから導出可能であることが判明。`IFRSMapping` を独立して維持すると二重管理が発生し、片方の更新漏れがバグの温床になる。A案（統合）を採用し、`jgaap_concept: str | None = None` と `mapping_note: str = ""` を `IFRSConceptMapping` に追加することで、`ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` を `_ALL_MAPPINGS` から直接生成できるようにした。

---

## 12. 実行チェックリスト

### Phase 1: データ検証（推定 20 分）

1. `docs/QAs/scripts/D-1.ifrs_concepts.py` を実行し、IFRS concept の正確な名称を確認
   ```bash
   EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 uv run docs/QAs/scripts/D-1.ifrs_concepts.py
   ```
2. Calculation Linkbase の PL/BS/CF 階層から JSON ファイルの concept 名を確定
3. XSD の要素名と照合し、暫定値を修正

### Phase 2: データファイル作成（推定 15 分）

4. `src/edinet/xbrl/data/pl_ifrs.json` を作成（検証済み concept 名で）
5. `src/edinet/xbrl/data/bs_ifrs.json` を作成
6. `src/edinet/xbrl/data/cf_ifrs.json` を作成

### Phase 3: モジュール実装（推定 30 分）

7. `src/edinet/xbrl/standards/ifrs.py` を新規作成
   - `IFRSConceptMapping` / `IFRSProfile` frozen dataclass（`IFRSMapping` は廃止、H-1 A案）
   - `__all__` 定義（`IFRSMapping` / `get_ifrs_jgaap_mappings` を除外）
   - `NAMESPACE_MODULE_GROUP` 定数
   - `_PL_MAPPINGS` / `_BS_MAPPINGS` / `_CF_MAPPINGS`（検証済み `IFRSConceptMapping` タプル、`jgaap_concept` / `mapping_note` 含む）
   - `_ALL_CANONICAL_KEYS`（モジュールレベル事前構築、M-5）
   - `_CONCEPT_INDEX` / `_CANONICAL_INDEX` / `_STATEMENT_INDEX`（インデックス辞書）
   - `_validate_registry()` 整合性検証関数（ValueError raise、assert 不使用）
   - `lookup()` / `canonical_key()` / `reverse_lookup()` / `mappings_for_statement()`
   - `all_mappings()` / `all_canonical_keys()` / `ifrs_specific_concepts()`
   - `load_ifrs_pl_concepts()` / `load_ifrs_bs_concepts()` / `load_ifrs_cf_concepts()`
   - `get_ifrs_concept_set()`
   - `is_ifrs_module()` / `get_profile()` / `to_legacy_concept_list()`
   - `_JGAAP_ONLY_CONCEPTS`（SYNC コメント付き、H-2）
   - `ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()`（`_ALL_MAPPINGS` から直接導出）

### Phase 4: テスト作成（推定 30 分）

8. `tests/test_xbrl/test_standards_ifrs.py` を新規作成
   - autouse fixture（`_load_json` キャッシュクリア）
   - P0 テスト（T1〜T31）を全て実装
   - P1 テスト（T32〜T47）を全て実装（M-4 で T46/T47 追加）

### Phase 5: 検証（推定 10 分）

9. `uv run ruff check src/edinet/xbrl/standards/ifrs.py tests/test_xbrl/test_standards_ifrs.py` — Lint チェック
10. `uv run pytest tests/test_xbrl/test_standards_ifrs.py -v` — ifrs テストのみ実行
11. `uv run pytest` — 全テスト実行（既存テストを壊していないことを確認）

### 完了条件

- [ ] `D-1.ifrs_concepts.py` の実行結果に基づき concept 名を確定した
- [ ] `pl_ifrs.json` / `bs_ifrs.json` / `cf_ifrs.json` が正しいフォーマットで作成された
- [ ] JSON ファイルの concept 名が `jpigp_cor` XSD の実際の要素名と一致する
- [ ] `IFRSConceptMapping` / `IFRSProfile` が frozen dataclass として定義されている（`IFRSMapping` は廃止: H-1）
- [ ] `IFRSConceptMapping` に `jgaap_concept` / `mapping_note` フィールドが含まれている（H-1 A案）
- [ ] `__all__` が定義され、全公開 API を含んでいる（`IFRSMapping` / `get_ifrs_jgaap_mappings` は除外）
- [ ] `lookup()` / `canonical_key()` / `reverse_lookup()` が正しく動作する
- [ ] `mappings_for_statement()` が全 `StatementType`（`INCOME_STATEMENT` / `BALANCE_SHEET` / `CASH_FLOW_STATEMENT`）で正しく動作する
- [ ] `all_mappings()` / `all_canonical_keys()` / `ifrs_specific_concepts()` が正しく動作する
- [ ] `all_canonical_keys()` がモジュールレベル事前構築の `_ALL_CANONICAL_KEYS` を返す（M-5）
- [ ] `get_ifrs_concept_set()` が frozenset を返す
- [ ] `is_ifrs_module()` / `get_profile()` が正しく動作する
- [ ] `is_ifrs_module()` の docstring に Lane 3 との非対称性を注記している（L-2）
- [ ] `to_legacy_concept_list()` の出力が対応する JSON ファイルの内容（全フィールド: concept, order, label_hint）と完全一致する（L-4）
- [ ] `canonical_key` が Lane 3 の同名キーと合意済みの値を使用している
- [ ] IFRS PL に `OrdinaryIncome` / `ExtraordinaryIncome` / `ExtraordinaryLoss` が含まれないことをテストで検証
- [ ] IFRS PL に `FinanceIncomeIFRS` / `FinanceCostsIFRS` が含まれることをテストで検証
- [ ] `ifrs_to_jgaap_map()` と `jgaap_to_ifrs_map()` が `_ALL_MAPPINGS` から直接導出されている（H-1 A案）
- [ ] `ifrs_to_jgaap_map()` と `jgaap_to_ifrs_map()` の双方向整合性がテストで検証されている（L-3 拡張含む）
- [ ] `OrdinaryIncome` → `None` のマッピングがテストで検証されている
- [ ] `ProfitLossAttributableToNonControllingInterestsIFRS` の J-GAAP 対応が `ProfitLossAttributableToNonControllingInterests` に設定されている（M-2）
- [ ] JSON フォーマットが既存の J-GAAP JSON（`pl_jgaap.json` 等）と同一構造
- [ ] `_validate_registry()` 整合性検証関数（ValueError raise、assert 不使用）がモジュールロード時に実行される
- [ ] `EquityAttributableToOwnersOfParentIFRS` の canonical_key が `equity_parent` に設定されている
- [ ] §6.2 BS テーブルに `ValuationAndTranslationAdjustments`, `SubscriptionRightsToShares` が J-GAAP 固有行として含まれている
- [ ] BS concepts が Lane 3 と同程度の網羅性（XSD 検証で追加/削除した結果を記録）（M-1）
- [ ] CF の `consolidation_scope_change_cash` 相当 IFRS concept の有無を XSD で確認し結果を §11 に記録した
- [ ] `_JGAAP_ONLY_CONCEPTS` に SYNC コメントが付与されている（H-2）
- [ ] `_JGAAP_ONLY_CONCEPTS` の全要素が Lane 3 §5.2-5.4 の `is_jgaap_specific=True` と一致することを手動確認した（H-2）
- [ ] §6.1 の `IncomeTaxesDeferred` が「IFRS 非対応」と表記されている（「J-GAAP 固有」ではない）（H-3）
- [ ] §11 に `is_jgaap_specific` と「IFRS 非対応」の概念的区別が記録されている（H-3）
- [ ] `IFRSProfile.module_groups` の docstring に「固有モジュール」の意味が明記されている（L-1）
- [ ] `jgaap_to_ifrs_map()` の docstring にキー範囲が明記されている（M-3）
- [ ] T45 が公開 API のみを使用している（`_JGAAP_ONLY_CONCEPTS` を直接参照しない）
- [ ] CF の period_type テスト（T46, T47）が含まれている（M-4）
- [ ] P0 テスト全件 PASS（T1〜T31）
- [ ] P1 テスト全件 PASS（T32〜T47）
- [ ] 既存テスト全件 PASS
- [ ] ruff Clean

---

## 変更ログ（フィードバック反映）

以下は `WAVE_2_LANE_4_FEEDBACK.md` のフィードバックに基づく計画書修正の記録。

### 変更日: 2026-02-28

| # | フィードバック | 重要度 | 変更箇所 | 変更内容 |
|---|------------|--------|---------|---------|
| C-1 | `StatementType.PL` は存在しない。実際は `INCOME_STATEMENT` 等 | CRITICAL | §1, §5, §6, §9, §12 全体 | `StatementType.PL` → `INCOME_STATEMENT`, `BS` → `BALANCE_SHEET`, `CF` → `CASH_FLOW_STATEMENT` に全て修正 |
| C-2 | `IFRSConceptDef` (3 フィールド) が Lane 3 `ConceptMapping` (9 フィールド) と非対称 | CRITICAL | §3.1 | `IFRSConceptDef` → `IFRSConceptMapping` に改名。9 フィールド（concept, canonical_key, label_ja, label_en, statement_type, period_type, is_ifrs_specific, is_total, display_order）に拡張。Lane 3 と対称的な構造 |
| C-3 | `canonical_key` が `IFRSConceptDef` に含まれていない | CRITICAL | §3.1, §5.3, §6, §7 | `IFRSConceptMapping` に `canonical_key` フィールドを追加。`lookup()` / `canonical_key()` / `reverse_lookup()` 関数を新設。マッピングテーブルに `canonical_key` 列を追加 |
| H-1 | JSON ロードに `Path(__file__)` を使用（`importlib.resources` を使うべき） | HIGH | §7.4 | `importlib.resources.files("edinet.xbrl.data").joinpath(filename)` に変更。既存の `statements.py` と統一 |
| H-2 | `@lru_cache(maxsize=4)` を使用（既存は `@functools.cache`） | HIGH | §5, §7.4 | `@functools.cache` に変更。既存コードとの一貫性を確保 |
| H-3 | concept 名にバージョン日付を含めている（バージョン非依存にすべき） | HIGH | §3.1 docstring | `IFRSConceptMapping.concept` の docstring に「バージョン非依存（H-3）」と明記 |
| H-4 | CF マッピングが 3 科目のみ（換算差額・増減額・期首/期末残高が欠落） | HIGH | §4.3, §6.3 | CF エントリを 3 → 7 に拡張（EffectOfExchangeRate, NetIncreaseDecrease, CashBeginning, CashEnd を追加） |
| M-1 | `IFRSProfile` が不足（Lane 3 には `JGAAPProfile` がある） | MEDIUM | §3.3 | `IFRSProfile` dataclass を新設。`get_profile()` 関数を追加（§5.6）。構築コードを追加（§7.7） |
| M-2 | テストが frozen/cache 等の Python 言語機能をテストしている | MEDIUM | §9.2 | T29（frozen テスト）、T30（slots テスト）、T31（cache テスト）を削除。T34（日本語ラベル完全一致テスト）を非空チェックに変更。canonical_key / lookup / profile テストを追加 |
| M-3 | キャッシュクリア fixture が yield 後にも二重クリアしている | MEDIUM | §9.3 | yield 後のクリアを削除。テスト前のクリアのみに簡素化 |
| M-4 | `to_legacy_concept_list()` が不足（Lane 3 にはある） | MEDIUM | §5.7, §7.6 | `to_legacy_concept_list()` 関数を追加。JSON 互換フォーマット `{"concept", "order", "label_hint"}` を出力 |
| M-5 | `__all__` が未定義 | MEDIUM | §5.1 | `__all__` を追加し全公開シンボルを列挙 |
| L-1 | BS に `LiabilitiesAndNetAssets` の対応情報がない | LOW | §6.2 | BS マッピングテーブルに J-GAAP 固有行として追加。§7.8 の `_JGAAP_ONLY_CONCEPTS` にも追加 |
| L-2 | テストファイル命名について class vs flat の方針記載がない | LOW | §9 テスト戦略 | Detroit 派（古典派）のスタイルであることを明記。テスト構造は実装者裁量とする |

### 追加の改善（フィードバック外）

| 変更箇所 | 変更内容 | 根拠 |
|---------|---------|------|
| §1（ゴール） | JSON を「主データソース」から「レガシー互換」に位置づけ変更 | Python コードが主データソースとなったため。Lane 3 と同じアプローチ |
| §1（ゴール） | ゴール 6 に `StatementType` の正確な値を記載 | C-1 対応の一環 |
| §4 セクションタイトル | 「データファイル設計（JSON）」→「データファイル設計（JSON — レガシー互換用）」 | 位置づけの明確化 |
| §4.4 | 設計根拠を「JSON が主」から「Python が主、JSON は互換用」に書き換え | データモデル変更に伴う整合性確保 |
| §7.1-7.3 | マッピングレジストリ + インデックス辞書 + 整合性アサーションを新設 | Lane 3 と同パターンの Python-centric アプローチ |
| §7.7 | `IFRSProfile` 構築コードを追加 | M-1 対応の実装詳細 |
| §7.8 | J-GAAP 固有科目リストに `LiabilitiesAndNetAssets` を追加 | L-1 対応 |
| §8 | ファイル構成テーブルの内容欄を更新 | 新 API（lookup, canonical_key, profile 等）の追加を反映 |
| §10 | Wave 3 使用例を canonical_key ベースのアクセスパターンに更新 | C-3 対応。canonical_key が主要ルックアップ手段であることを示す |
| §11 Q3 | `IFRSConceptDef` → `IFRSConceptMapping` に改名、説明を更新 | C-2 対応 |
| §11 Q5 | `StatementType.PL` → `StatementType.INCOME_STATEMENT` に修正 | C-1 対応 |
| §12 Phase 3 | チェックリストを新 API に合わせて更新 | 全体的な整合性 |
| §12 完了条件 | 新 API（`__all__`, lookup, canonical_key, profile, to_legacy 等）の条件を追加 | フィードバック反映後の新要件 |
| 非ゴール | `canonical_key` の名称決定権限が Lane 3 にあることを明記 | Lane 間の責務分担の明確化 |

### 変更日: 2026-02-28（第2版フィードバック反映）

| # | フィードバック | 重要度 | 変更箇所 | 変更内容 |
|---|------------|--------|---------|---------|
| H-1 | `EquityAttributableToOwnersOfParentIFRS` の canonical_key が未決定 | HIGH | §6.2 | `_(新規検討)_` → `equity_parent` に確定。近似対応（`shareholders_equity`）は normalize の責務。§11 に設計判断を追加 |
| H-2 | `assert` による整合性検証は `python -O` で無効化される | HIGH | §7.3 | `assert` → `_validate_registry()` 関数（`ValueError` raise）に変更。Lane 3 §6.3 と同一パターン。`period_type` の値検証も追加 |
| H-3 | §6.2 BS テーブルと `_JGAAP_ONLY_CONCEPTS` の不整合 | HIGH | §6.2 | `ValuationAndTranslationAdjustments`（`oci_accumulated`）と `SubscriptionRightsToShares`（`stock_options`）を J-GAAP 固有行として追加。Lane 3 §5.3 の row 16, 17 と整合 |
| M-1 | Lane 3 にある API 関数が Lane 4 に欠けている | MEDIUM | §5.1, §5.4 | `all_mappings()`, `all_canonical_keys()`, `ifrs_specific_concepts()` を `__all__` と §5.4 に追加。Wave 3 normalize での対称呼び出しを保証 |
| M-2 | CF の `cash_beginning` / `cash_end` の period_type 注記がない | MEDIUM | §3.1, §6.3 | `IFRSConceptMapping.period_type` の docstring に「cash_beginning / cash_end は概念的に instant だが duration として報告される」旨を追加。§6.3 テーブルの備考列にも追記 |
| M-3 | CF の `consolidation_scope_change_cash` 相当の IFRS concept が未検討 | MEDIUM | §6.3, §11 | §6.3 に NOTE を追加（実装時に XSD を確認する指示）。§11 に設計判断 Q&A を追加 |
| M-4 | KPI のスコープ外宣言が明示されていない | MEDIUM | §1 非ゴール | 「KPI（EPS / BPS / 配当等）の IFRS マッピング → Phase 6 または将来の拡張で対応」を追加 |
| M-5 | `income_taxes_deferred` の IFRS 対応が不明 | MEDIUM | §6.1, §11 | §6.1 PL テーブルに J-GAAP 固有行として `IncomeTaxesDeferred` を追加（Lane 3 PL 16 vs Lane 4 PL 15 の差分を明示）。§11 に設計判断を追加 |
| L-1 | T45 が内部実装 `_JGAAP_ONLY_CONCEPTS` を参照 | LOW | §9.2 | T45 を公開 API（`jgaap_to_ifrs_map()` の結果から `None` にマッピングされる J-GAAP 概念を検証）に変更 |
| L-2 | `IFRSProfile.canonical_key_count` の値が不明確 | LOW | §3.3 | `canonical_key_count` の docstring に「KPI 概念は含まない。Lane 3 は 52 keys、本モジュールは 31 keys」を追記 |
| L-3 | `is_total` フラグの設定基準が不明 | LOW | §6.1, §6.2, §6.3 | 全マッピングテーブルに `is_total` 列を追加。各 concept の合計/小計判定を明示 |

### 変更日: 2026-02-28（第3版フィードバック反映）

| # | フィードバック | 重要度 | 変更箇所 | 変更内容 |
|---|------------|--------|---------|---------|
| H-1 | `IFRSMapping` の冗長性 — `IFRSConceptMapping` に情報が集約されたため役割不明瞭 | HIGH | §3.1, §3.2(削除), §5.1, §5.8, §7.1, §7.5(削除), §8, §11, §12 | **A案採用**: `IFRSMapping` を廃止し `IFRSConceptMapping` に `jgaap_concept: str \| None = None` と `mapping_note: str = ""` を追加。`get_ifrs_jgaap_mappings()` 廃止。`ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` は `_ALL_MAPPINGS` から直接導出。二重管理を完全排除 |
| H-2 | `_JGAAP_ONLY_CONCEPTS` が Lane 3 と二重管理になる | HIGH | §7.7(旧7.8), §12 | SYNC コメントを追加。§12 に「全要素が Lane 3 の `is_jgaap_specific=True` と一致することを手動確認」チェック項目を追加。Wave 3 統合タスクで自動生成に切り替える旨を明記 |
| H-3 | `IncomeTaxesDeferred` の `is_jgaap_specific` フラグが Lane 3 と矛盾する可能性 | HIGH | §6.1, §11, §12 | §6.1 の「J-GAAP 固有」表記を「**IFRS 非対応**」に修正。§11 に `is_jgaap_specific` と「IFRS 非対応」の概念的区別を Q&A として追加 |
| M-1 | BS の概念数が少なすぎる（9 vs Lane 3 の 20） | MEDIUM | §4.2, §6.2, §7.1, §8, §9.2(T9), §12 | **A案採用**: 暫定的に 6 concept（PropertyPlantAndEquipment, IntangibleAssets, IssuedCapital, CapitalSurplus, RetainedEarnings, TreasuryShares）を追加。BS JSON を 9→15 エントリに拡張。実装 Phase 1 の XSD 検証で確定 |
| M-2 | `ProfitLossAttributableToNonControllingInterestsIFRS` の J-GAAP 対応が不明瞭 | MEDIUM | §6.1 | J-GAAP 列を「—」から `ProfitLossAttributableToNonControllingInterests` に修正。J-GAAP ラベル「非支配株主に帰属する当期純利益」を追加 |
| M-3 | `jgaap_to_ifrs_map()` の J-GAAP 側キー範囲の仕様が不十分 | MEDIUM | §5.8 | docstring にキー範囲（§6.1-6.3 の J-GAAP concept + §7.7 の `_JGAAP_ONLY_CONCEPTS`）を明記。Lane 3 KPI は含まない旨を記載 |
| M-4 | CF の `period_type` テストが不足 | MEDIUM | §9.2 | T46（CF 全 mapping が duration）と T47（cash_beginning/cash_end が duration であるドキュメンテーションテスト）を追加。テスト合計 45→47 |
| M-5 | `all_canonical_keys()` の戻り値がキャッシュされない | MEDIUM | §5.4, §7.1 | モジュールレベルで `_ALL_CANONICAL_KEYS` を事前構築。`all_canonical_keys()` はそれを返すだけに変更 |
| L-1 | `IFRSProfile.module_groups` の意味が曖昧 | LOW | §3.2(旧3.3) | `module_groups` の docstring を「この会計基準に**固有の**モジュールグループ」と明確化。共通モジュール（jpcrp, jpdei）は含まない旨を記載 |
| L-2 | `is_ifrs_module()` の docstring と Lane 3 `is_jgaap_module()` の非対称性 | LOW | §5.5 | docstring に NOTE を追加。Lane 3 の `is_jgaap_module("jpdei")=True` との非対称性を明記し、Wave 3 normalize で吸収する旨を記載 |
| L-3 | T21（双方向整合性）の検証範囲が限定的 | LOW | §9.2(T21) | T21 の検証範囲を拡張。IFRS 固有科目（`ifrs_to_jgaap` の値が None）が `jgaap_to_ifrs` のキーに含まれないことも検証するよう記載 |
| L-4 | JSON の `label_hint` と `IFRSConceptMapping.label_ja` の同期保証 | LOW | §9.2(T29-T31), §12 | T29-T31 のテスト仕様を「concept 一覧の一致」から「各要素の全フィールド（concept, order, label_hint）の完全一致」に変更 |

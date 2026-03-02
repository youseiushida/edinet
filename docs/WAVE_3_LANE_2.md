# Wave 3 / Lane 2 — sector/banking: 銀行業の業種固有マッピング

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 3 / Lane 2 を担当するエージェントです。
担当機能: sector_banking

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/xbrl/sector/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/sector/banking.py` (新規)
   - `tests/test_xbrl/test_sector_banking.py` (新規)
   - `tests/fixtures/sector_banking/` (新規ディレクトリ)
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
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリ `tests/fixtures/sector_banking/` を作成すること

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.financial.sector.banking import lookup, canonical_key` （OK）
   - 例: `from edinet.financial.sector import banking` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_sector_banking.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - Wave 1〜2 で完成したモジュールは import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.dei` (DEI, AccountingStandard, PeriodType, extract_dei)
     - `edinet.xbrl._namespaces` (NS_* 定数, classify_namespace, NamespaceInfo 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl.taxonomy.concept_sets` (ConceptSetRegistry, ConceptSet, StatementCategory)
     - `edinet.financial.standards.detect` (DetectedStandard, detect_accounting_standard)
     - `edinet.financial.standards.jgaap` (ConceptMapping, lookup, canonical_key 等)
     - `edinet.financial.standards.ifrs` (IFRSConceptMapping, ifrs_lookup 等)
     - `edinet.financial.standards.usgaap` (USGAAPSummaryMapping 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning 等)
   - **他の Wave 3 レーンが作成中のモジュール**（normalize, sector/insurance, sector/construction 等）に依存してはならない

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 2 — sector/banking: 銀行業の業種固有マッピング

## 0. 位置づけ

Wave 3 Lane 2 は、FEATURES.md の **Sector-Specific > sector/banking** に対応する。銀行業（業種コード `bk1`, `bk2`）は一般事業会社（`cai`: 一般商工業）と PL/BS の勘定科目体系が根本的に異なるため、専用の canonical_key マッピングを提供するモジュール。

> **用語の注意**: 一般事業会社のタクソノミ業種コードは **`cai`**（Commercial And Industrial）。`cns` は**建設業**（Construction）であり、一般事業会社ではない（QA C-3.a.md 参照）。

FEATURES.md の定義:

> - sector/banking: 銀行業 [TODO]
>   - detail: 経常収益、経常費用、資金運用収支、役務取引等収支、特定取引収支、その他業務収支

FUTUREPLAN.tmp.md での位置:

> Wave 3 L2: sector/banking → L1 concept_sets 依存

TEMP.md（Wave 3 引き継ぎ）課題 4 の該当箇所:

> **銀行業の標準科目**: `FeesAndCommissionsOIBNK`（役務取引等収益）は jppfs_cor の正規科目。
> 計算リンクで遡及しても `OrdinaryIncomeOfBusinessBNK`（経常収益）に辿り着くだけで、
> 一般事業の `NetSales`（売上高）にはならない。構造が根本的に異なる。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.financial.standards.jgaap` (Wave 2 L3) | `ConceptMapping` dataclass を参照、J-GAAP 一般事業との整合性検証 | read-only |
| `edinet.xbrl.taxonomy.concept_sets` (Wave 2 L1) | `ConceptSetRegistry`, `StatementCategory` — 銀行業 ConceptSet の取得 | read-only |
| `edinet.models.financial.StatementType` | 財務諸表タイプ Enum | read-only |

他レーンとのファイル衝突なし（全て新規ファイル作成）。

### QA 参照

| QA | タイトル | 関連度 |
|----|---------|--------|
| E-5 | 業種別の財務諸表の差異 | **直接（設計の基盤）** — 業種間の PL/BS 構造差異 |
| C-3 | 業種カテゴリコードの一覧 | 直接（bk1/bk2 の識別、cai の確認） |
| E-7 | 主要勘定科目の concept 名辞書 | 関連（一般事業の canonical_key 参照） |
| E-1 | 財務諸表の種類と識別 | 関連（PL/BS/CF の分類基準） |
| I-1 | Role URI と財務諸表の対応 | 関連（role URI ベースの ConceptSet 分類） |
| C-7 | 計算リンクベースの詳細構造 | 関連（銀行業 PL の計算階層） |

---

## 1. ゴール

1. 銀行業（`bk1`, `bk2`）の **PL / BS / CF 主要科目の canonical_key マッピング** を `BankingConceptMapping` として提供する
2. J-GAAP 一般事業会社（`cai`）の `ConceptMapping` と**対称的な API**（`lookup`, `canonical_key`, `reverse_lookup` 等）を提供する
3. 銀行業固有科目と一般事業科目の**クロスマッピング**（「経常収益 ≈ 売上高」等）を `general_equivalent` フィールドで明示的に定義する
4. Wave 3 L1（`standards/normalize`）が**業種を意識せずに** canonical_key で統一アクセスできるための入力データを提供する
5. `bk1`（普通銀行）と `bk2`（特定取引勘定設置銀行 = 大手銀行）の差異を吸収する

---

## 2. 背景: 銀行業と一般事業の構造差異

### 2.1 PL（損益計算書）の構造差異

銀行業の PL は一般事業と根本的に異なる。「売上高」「売上原価」「売上総利益」「販管費」「営業利益」の概念が存在しない。

```
一般事業会社 (cai) PL:
  売上高 (NetSales)                           ← 最上位
  売上原価 (CostOfSales)
  売上総利益 (GrossProfit)                     [TOTAL]
  販管費 (SellingGeneralAndAdministrativeExpenses)
  営業利益 (OperatingIncome)                   [TOTAL]
  営業外収益 / 営業外費用
  経常利益 (OrdinaryIncome)                    [TOTAL]
  ...

銀行業 (bk1/bk2) PL:
  経常収益 (OrdinaryIncomeBNK)                 ← 最上位（一般事業の「売上高」に相当）
    資金運用収益 (InterestIncomeOIBNK)
      貸出金利息 (InterestOnLoansAndDiscountsOIBNK)
      有価証券利息配当金 (InterestAndDividendsOnSecuritiesOIBNK)
      ...
    役務取引等収益 (FeesAndCommissionsOIBNK)
    特定取引収益 (TradingIncomeOIBNK)          ← bk2（特定取引勘定設置）で使用
    その他業務収益 (OtherOrdinaryIncomeOIBNK)
    その他経常収益 (OtherIncomeOIBNK)
  経常費用 (OrdinaryExpensesBNK)
    資金調達費用 (InterestExpensesOEBNK)
    役務取引等費用 (FeesAndCommissionsPaymentsOEBNK)
    特定取引費用 (TradingExpensesOEBNK)        ← bk2（特定取引勘定設置）で使用
    その他業務費用 (OtherOrdinaryExpensesOEBNK)
    営業経費 (GeneralAndAdministrativeExpensesOEBNK)
    その他経常費用 (OtherExpensesOEBNK)
  経常利益 (OrdinaryIncome)                    [TOTAL] ← ここは共通
  特別利益 (ExtraordinaryIncome)
  特別損失 (ExtraordinaryLoss)
  税引前当期純利益 (IncomeBeforeIncomeTaxes)
  ...当期純利益 (ProfitLoss)
```

**重要な観察**: 経常利益 (`OrdinaryIncome`) 以下の構造は銀行業と一般事業で共通。差異が生じるのは「経常利益より上」の部分のみ。

### 2.2 BS（貸借対照表）の構造差異

銀行業の BS も大きく異なる。

```
一般事業会社 (cai) BS:
  資産の部
    流動資産 (CurrentAssets)
      現金及び預金 (CashAndDeposits)
      受取手形及び売掛金 (NotesAndAccountsReceivableTrade)
      棚卸資産 (Inventories)
      ...
    固定資産 (NoncurrentAssets)
      ...

銀行業 (bk1/bk2) BS:
  資産の部
    現金預け金 (CashAndDueFromBanksAssetsBNK)
    コールローン及び買入手形 (CallLoansAndBillsBoughtAssetsBNK)
    買現先勘定 (ReceivablesUnderResaleAgreementsAssetsBNK)
    ...
    有価証券 (SecuritiesAssetsBNK)
    貸出金 (LoansAndBillsDiscountedAssetsBNK)
    ...
    有形固定資産 (PropertyPlantAndEquipment)    ← 一般事業と共通
    無形固定資産 (IntangibleAssets)              ← 一般事業と共通
    ...
  負債の部
    預金 (DepositsLiabilitiesBNK)               ← 銀行固有
    コールマネー (CallMoneyAndBillsSoldLiabilitiesBNK)
    ...
```

### 2.3 CF（キャッシュフロー計算書）の構造差異

銀行業の CF は**直接法**が標準的に使用される（一般事業会社のほぼ全てが間接法）。銀行業の間接法 CF も存在するが、営業 CF のスタート項目が異なる。**直接法と間接法で概念が異なるため、マッピングを分離して管理する。**

```
銀行業 CF（直接法）:
  営業活動
    貸出金の回収による収入 (CollectionOfLoansReceivableOpeCFBNK)
    預金の払戻による支出 (PaymentsForWithdrawalOfDepositsOpeCFBNK)
    貸出金の利息による収入 (ProceedsFromInterestOnLoansOpeCFBNK)
    ...

銀行業 CF（間接法）:
  営業活動
    税引前当期純利益 (IncomeBeforeIncomeTaxes)   ← ここは共通
    貸倒引当金の増減額 (IncreaseDecreaseInAllowanceForLoanLossesOpeCFBNK) ← 銀行固有
    資金運用収益 (GainOnFundManagementOpeCFBNK) ← 銀行固有
    ...
```

### 2.4 ConceptSet からの実測データ

`concept_sets.py` の `derive_concept_sets()` から実際に導出済みの銀行業データ:

| 業種コード | 連結 PL (non-abstract) | 個別 PL | 連結 BS | 個別 BS | CF 直接法 | CF 間接法 |
|-----------|----------------------|--------|--------|--------|---------|----------|
| bk1 | 60 | 79 | 69 | 133 | 23(連結)/20(個別) | 29(連結)/26(個別) |
| bk2 | — (連結テンプレートなし) | 87 | — | 142 | — | — |
| cai (比較) | 65 | — | — | — | — | — |

**bk1 と cai の PL 科目重複**: 19 概念が共通（`OrdinaryIncome`, `IncomeBeforeIncomeTaxes`, `ProfitLoss`, CI 系等。経常利益以下の構造が共通であることを裏付ける）。

### 2.5 bk1 vs bk2 の違い（QA C-3.a.md に基づく）

- **bk1**: **銀行・信託業**（普通銀行）。特定取引勘定を設置しない一般銀行。連結・個別両方の全 statement（PL/BS/CF/CI 含む）のテンプレートを持つ。
  - 企業例: みずほ銀行、SBI新生銀行、あおぞら銀行
- **bk2**: **銀行・信託業（特定取引勘定設置銀行）**。特定取引（トレーディング）勘定を設置する大手銀行。bk1 と同等の科目体系に加え、特定取引収益/費用（`TradingIncomeOIBNK` / `TradingExpensesOEBNK`）が重要な位置を占める。
  - 企業例: 三菱UFJ銀行、三井住友銀行
  - タクソノミ上は個別のみ（連結テンプレートなし）だが、企業レベルでは連結を提出する bk2 企業も存在しうる

> **注意**: bk1/bk2 の区分は**タクソノミのテンプレート構造**の違いであり、企業の規模の大小とは直接対応しない。ただし実務上、特定取引勘定を設置する銀行は都市銀行等の大手が中心。

---

## 3. 設計方針

### 3.1 J-GAAP jgaap.py との対称性

`sector/banking.py` は `standards/jgaap.py` の**銀行業版**として設計する。API は `jgaap.py` と完全対称。

> **設計判断: 独自型 `BankingConceptMapping` を使用する理由**
> 本レーンは並列安全ルール（§推奨事項8）により Lane 4 の `_base.py` に依存できないため、独自の `BankingConceptMapping` を定義する。Wave 3 統合時に Lane 4 の `SectorConceptMapping` へのマイグレーションを行う（Section 11 参照）。フィールド構成を意図的に `SectorConceptMapping` に近似させ、統合コストを最小化する。

| jgaap.py | banking.py | 備考 |
|----------|------------|------|
| `ConceptMapping` | `BankingConceptMapping` | 同一構造 + `general_equivalent` / `mapping_note` フィールド |
| `lookup("NetSales")` | `lookup("OrdinaryIncomeBNK")` | ローカル名 → マッピング |
| `canonical_key("NetSales")` | `canonical_key("OrdinaryIncomeBNK")` | ローカル名 → canonical_key |
| `reverse_lookup("revenue")` | `reverse_lookup("ordinary_revenue_bnk")` | canonical_key → マッピング |
| `all_mappings()` | `all_mappings()` | 全マッピングのタプル |
| `mappings_for_statement(PL)` | `mappings_for_statement(PL)` | PL/BS/CF 別 |
| `is_jgaap_module("jppfs")` | `is_banking_concept("...BNK")` | 銀行業固有科目の判定 |

### 3.2 canonical_key の設計原則

銀行業固有科目の canonical_key は以下の命名規則に従う:

1. **一般事業と意味的に等価な科目** → 一般事業と同じ canonical_key を使用
   - 例: `OrdinaryIncome` (銀行業 PL) → `ordinary_income`（一般事業でも同じ）
   - 例: `ProfitLoss` → `net_income`（共通科目）
   - 例: `IncomeBeforeIncomeTaxes` → `income_before_tax`（共通科目）

2. **一般事業に存在しない銀行業固有科目** → `_bnk` サフィックスを付与
   - 例: `OrdinaryIncomeBNK` → `ordinary_revenue_bnk`（経常**収益**。売上高に相当するが概念が異なる）
   - 例: `InterestIncomeOIBNK` → `interest_income_bnk`（資金運用収益）

   > **命名上の注意**: `OrdinaryIncomeBNK`（経常**収益**）と `OrdinaryIncome`（経常**利益**）は名前が似ているが意味が全く異なる。混同を防ぐため、canonical_key では前者を `ordinary_revenue_bnk`、後者を `ordinary_income` とする。

3. **共通科目** → `general_equivalent` に canonical_key と同一値を設定する（`canonical_key == general_equivalent`）
   - 情報量はゼロだが、`banking_to_general_map()` が共通科目も含めて返すことで normalize レイヤーに一貫した API を提供する
   - 「この科目には一般事業の等価概念がある」ことを明示するメタデータとしても価値がある

4. **概念的に対応するが 1:1 マッピングではない科目** → `general_equivalent` フィールドで対応を示す
   - 例: `OrdinaryIncomeBNK` の `general_equivalent = "revenue"`（売上高に相当するが完全な等価ではない）
   - normalize レイヤーが「銀行の売上高相当は？」に応答する際の根拠
   - `general_equivalent` には **canonical_key 文字列**を格納する（concept 名ではない）

### 3.3 マッピング対象の選定

concept_sets.py が自動導出した全科目（bk1 連結 PL: 60 概念等）を全てマッピングする必要はない。

**マッピング対象とする基準**:
- PL の第 1〜2 階層の主要科目（経常収益・経常費用・各カテゴリの小計等）
- BS の主要区分（銀行固有の資産・負債科目の大分類）
- CF の主要区分合計（直接法・間接法それぞれ）
- 銀行業と一般事業で共通の科目（`OrdinaryIncome`, `IncomeBeforeIncomeTaxes` 等）

**マッピング対象外**:
- PL の第 3 階層以下の明細（`InterestOnLoansAndDiscountsOIBNK` 等の個別利息内訳）
- BS の詳細項目（`GovernmentBondsInvestmentSecuritiesAssetsBNK` 等の有価証券内訳）
- これらは計算リンク遡及（`taxonomy/standard_mapping` [TODO]）で親科目に辿る方が適切

### 3.4 マッピング数の見積もり

| 財務諸表 | 科目数 | 備考 |
|---------|-------|------|
| PL（銀行固有） | ~13 | 経常収益/費用の主要内訳 |
| PL（共通科目） | ~7 | 経常利益以下（OrdinaryIncome, IncomeBeforeIncomeTaxes, ProfitLoss 等） |
| BS（銀行固有） | ~12 | 銀行固有の資産/負債大分類 |
| BS（共通科目） | ~3 | 純資産の部（NetAssets, TotalAssets 等） |
| CF 直接法（銀行固有） | ~4 | 直接法の営業 CF 主要科目 |
| CF 間接法（銀行固有） | ~4 | 間接法の営業 CF 銀行固有調整項目 |
| CF（共通科目） | ~3 | 営業/投資/財務 CF 合計 |
| **合計** | **~46** | jgaap.py の 52 と同規模 |

---

## 4. データモデル

### 4.1 BankingConceptMapping

```python
# jgaap.py と同じ型エイリアスを使用
PeriodType = Literal["instant", "duration"]

@dataclass(frozen=True, slots=True)
class BankingConceptMapping:
    """銀行業 concept の正規化マッピング。

    Attributes:
        concept: jppfs_cor のローカル名（例: "OrdinaryIncomeBNK"）。
        canonical_key: 正規化キー（例: "ordinary_revenue_bnk"）。
        label_ja: 日本語ラベル（例: "経常収益"）。
        label_en: 英語ラベル（例: "Ordinary revenue (banking)"）。
        statement_type: 所属する財務諸表。PL / BS / CF。
        period_type: 期間型。"instant" or "duration"。
        is_total: 合計・小計行か。
        display_order: 表示順序。statement_type 内で 1 始まりの連番。
        general_equivalent: 一般事業会社 (cai) の対応する canonical_key。
            概念的に対応する一般事業科目がある場合にのみ設定。
            例: ordinary_revenue_bnk → "revenue"（経常収益 ≈ 売上高）。
            格納する値は **canonical_key 文字列**（concept 名ではない）。
            完全な等価ではないが、クロスセクター比較の出発点。
            対応する概念がない場合は None。
        industry_codes: この科目が使用される業種コードの集合。
            frozenset({"bk1", "bk2"}) のように複数可。
        mapping_note: クロスセクター比較の根拠・注意事項。
            例: "経常収益は売上高に相当するが、構造が根本的に異なる"。
    """
    concept: str
    canonical_key: str
    label_ja: str
    label_en: str
    statement_type: StatementType | None
    period_type: PeriodType
    is_total: bool = False
    display_order: int = 0
    general_equivalent: str | None = None
    industry_codes: frozenset[str] = frozenset({"bk1", "bk2"})
    mapping_note: str = ""
```

### 4.2 BankingProfile

```python
@dataclass(frozen=True, slots=True)
class BankingProfile:
    """銀行業のプロファイル情報。

    Attributes:
        industry_code: 業種コード（"bk1" or "bk2"）。
        name_ja: 業種名（日本語）。タクソノミ設定規約書に準拠。
        name_en: 業種名（英語）。
        has_consolidated_template: タクソノミに連結テンプレートが存在するか。
            bk1=True, bk2=False。企業レベルの連結有無とは異なる。
        cf_method: 標準的な CF 手法。情報提供用フィールド。
            `mappings_for_statement(CF)` のフィルタリングには使用しない
            （直接法・間接法の両方が常に返される）。
            将来の CF 表示機能で分岐条件として使用する想定。
    """
    industry_code: str
    name_ja: str
    name_en: str
    has_consolidated_template: bool
    cf_method: Literal["direct", "indirect", "both"]
```

---

## 5. 公開 API 設計

### 5.1 Core API（jgaap.py と対称）

```python
def lookup(concept: str) -> BankingConceptMapping | None:
    """concept ローカル名 → BankingConceptMapping。"""

def canonical_key(concept: str) -> str | None:
    """concept ローカル名 → canonical_key 文字列。"""

def reverse_lookup(key: str) -> BankingConceptMapping | None:
    """canonical_key → BankingConceptMapping。"""

def all_mappings() -> tuple[BankingConceptMapping, ...]:
    """全マッピングのタプル。

    返却順序: PL銀行固有 → PL共通 → BS銀行固有 → BS共通
    → CF直接法 → CF間接法 → CF共通。
    display_order の statement_type 内連番と整合する。
    """

def mappings_for_statement(
    statement_type: StatementType,
) -> tuple[BankingConceptMapping, ...]:
    """指定 StatementType のマッピングのみ。"""

def all_canonical_keys() -> frozenset[str]:
    """全 canonical_key の集合。"""
```

### 5.2 銀行業固有 API

```python
def is_banking_concept(concept: str) -> bool:
    """concept が銀行業固有科目かどうか。

    銀行固有マッピングタプル（_PL_BANKING_MAPPINGS, _BS_BANKING_MAPPINGS,
    _CF_DIRECT_MAPPINGS, _CF_INDIRECT_MAPPINGS）に登録されている concept のみ True。
    共通科目（_COMMON_PL_MAPPINGS, _COMMON_BS_MAPPINGS 等）は False。
    """

def general_equivalent(concept: str) -> str | None:
    """銀行業 concept に対応する一般事業の canonical_key。

    例: "OrdinaryIncomeBNK" → "revenue"
    対応がない場合は None。
    """

def banking_to_general_map() -> dict[str, str]:
    """銀行業 → 一般事業の canonical_key マッピング辞書。

    general_equivalent が設定されている科目のみ。
    key: 銀行業の canonical_key, value: 一般事業の canonical_key。
    """

def get_profile(industry_code: str) -> BankingProfile | None:
    """業種コードから BankingProfile を取得。

    "bk1" or "bk2" のみ受け付ける。
    """

# 業種コード判定
BANKING_INDUSTRY_CODES: frozenset[str] = frozenset({"bk1", "bk2"})

def is_banking_industry(code: str) -> bool:
    """業種コードが銀行業かどうか。"""
```

---

## 6. マッピングデータ（Python タプル定義）

### 6.1 PL マッピング（銀行業固有）

銀行業 PL の経常利益より上の主要科目。全て銀行固有。

```python
_PL_BANKING_MAPPINGS: tuple[BankingConceptMapping, ...] = (
    # --- 経常収益（銀行業固有: 一般事業の「売上高」に相当） ---
    BankingConceptMapping(
        concept="OrdinaryIncomeBNK",
        canonical_key="ordinary_revenue_bnk",  # "income" ではなく "revenue"（経常収益≠経常利益）
        label_ja="経常収益",
        label_en="Ordinary revenue (banking)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,  # 内訳（資金運用収益+役務取引等収益+...）の合計行
        display_order=1,
        general_equivalent="revenue",  # 売上高に相当（完全等価ではない）
        industry_codes=frozenset({"bk1", "bk2"}),
        mapping_note="経常収益は売上高に相当するが、内訳構造（資金運用/役務取引/特定取引/その他）が根本的に異なる",
    ),
    BankingConceptMapping(
        concept="InterestIncomeOIBNK",
        canonical_key="interest_income_bnk",
        label_ja="資金運用収益",
        label_en="Interest income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=2,
        general_equivalent=None,  # 一般事業に対応なし
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    BankingConceptMapping(
        concept="FeesAndCommissionsOIBNK",
        canonical_key="fees_and_commissions_income_bnk",
        label_ja="役務取引等収益",
        label_en="Fees and commissions (income)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=3,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    BankingConceptMapping(
        concept="TradingIncomeOIBNK",
        canonical_key="trading_income_bnk",
        label_ja="特定取引収益",
        label_en="Trading income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=4,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
        # bk2（特定取引勘定設置銀行）で特に重要だが、bk1 のタクソノミにも存在する
    ),
    BankingConceptMapping(
        concept="OtherOrdinaryIncomeOIBNK",
        canonical_key="other_ordinary_income_bnk",
        label_ja="その他業務収益",
        label_en="Other ordinary income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=5,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    BankingConceptMapping(
        concept="OtherIncomeOIBNK",
        canonical_key="other_income_bnk",
        label_ja="その他経常収益",
        label_en="Other income (banking)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=6,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    # --- 経常費用（銀行業固有） ---
    BankingConceptMapping(
        concept="OrdinaryExpensesBNK",
        canonical_key="ordinary_expenses_bnk",
        label_ja="経常費用",
        label_en="Ordinary expenses (banking)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,  # 内訳（資金調達費用+役務取引等費用+...）の合計行
        display_order=7,
        general_equivalent=None,  # 売上原価+販管費に広く対応するため 1:1 にしない
        industry_codes=frozenset({"bk1", "bk2"}),
        mapping_note="売上原価+販管費の合計に概念的に近いが、内訳構造が全く異なるため等価なし",
    ),
    BankingConceptMapping(
        concept="InterestExpensesOEBNK",
        canonical_key="interest_expenses_bnk",
        label_ja="資金調達費用",
        label_en="Interest expenses",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=8,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    BankingConceptMapping(
        concept="FeesAndCommissionsPaymentsOEBNK",
        canonical_key="fees_and_commissions_expenses_bnk",
        label_ja="役務取引等費用",
        label_en="Fees and commissions (expenses)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=9,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    BankingConceptMapping(
        concept="TradingExpensesOEBNK",
        canonical_key="trading_expenses_bnk",
        label_ja="特定取引費用",
        label_en="Trading expenses",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=10,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    BankingConceptMapping(
        concept="OtherOrdinaryExpensesOEBNK",
        canonical_key="other_ordinary_expenses_bnk",
        label_ja="その他業務費用",
        label_en="Other ordinary expenses",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=11,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
    BankingConceptMapping(
        concept="GeneralAndAdministrativeExpensesOEBNK",
        canonical_key="general_admin_expenses_bnk",
        label_ja="営業経費",
        label_en="General and administrative expenses (banking)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=12,
        general_equivalent="sga_expenses",  # 販管費に相当
        industry_codes=frozenset({"bk1", "bk2"}),
        mapping_note="一般事業の販管費に概念的に近い（人件費・物件費・税金を含む営業経費）",
    ),
    BankingConceptMapping(
        concept="OtherExpensesOEBNK",
        canonical_key="other_expenses_bnk",
        label_ja="その他経常費用",
        label_en="Other expenses (banking)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=13,
        general_equivalent=None,
        industry_codes=frozenset({"bk1", "bk2"}),
    ),
)
```

### 6.2 PL 共通科目マッピング

経常利益以下の共通科目。canonical_key は jgaap.py と**必ず同一**。

```python
_COMMON_PL_MAPPINGS: tuple[BankingConceptMapping, ...] = (
    # jgaap.py: OrdinaryIncome → "ordinary_income"
    BankingConceptMapping(
        concept="OrdinaryIncome",
        canonical_key="ordinary_income",
        label_ja="経常利益",
        label_en="Ordinary income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=14,
        general_equivalent="ordinary_income",  # 完全等価
    ),
    # jgaap.py: ExtraordinaryIncome → "extraordinary_income"
    BankingConceptMapping(
        concept="ExtraordinaryIncome",
        canonical_key="extraordinary_income",
        ...
        display_order=15,
    ),
    # jgaap.py: ExtraordinaryLoss → "extraordinary_loss"
    BankingConceptMapping(
        concept="ExtraordinaryLoss",
        canonical_key="extraordinary_loss",
        ...
        display_order=16,
    ),
    # jgaap.py: IncomeBeforeIncomeTaxes → "income_before_tax"
    BankingConceptMapping(
        concept="IncomeBeforeIncomeTaxes",
        canonical_key="income_before_tax",
        ...
        is_total=True,
        display_order=17,
    ),
    # jgaap.py: ProfitLoss → "net_income"
    BankingConceptMapping(
        concept="ProfitLoss",
        canonical_key="net_income",
        ...
        is_total=True,
        display_order=18,
    ),
    # jgaap.py: ProfitLossAttributableToOwnersOfParent → "net_income_parent"
    BankingConceptMapping(
        concept="ProfitLossAttributableToOwnersOfParent",
        canonical_key="net_income_parent",
        ...
        is_total=True,
        display_order=19,
    ),
    # jgaap.py: ProfitLossAttributableToNonControllingInterests → "net_income_minority"
    BankingConceptMapping(
        concept="ProfitLossAttributableToNonControllingInterests",
        canonical_key="net_income_minority",
        ...
        display_order=20,
    ),
)
```

### 6.3 BS マッピング（銀行業固有 + 共通）

```python
_BS_BANKING_MAPPINGS: tuple[BankingConceptMapping, ...] = (
    # --- 資産の部（銀行固有） ---
    BankingConceptMapping(
        concept="CashAndDueFromBanksAssetsBNK",
        canonical_key="cash_due_from_banks_bnk",
        label_ja="現金預け金",
        label_en="Cash and due from banks",
        ...,
        display_order=1,
        general_equivalent=None,  # 現金及び預金に近いが内訳が異なる
        mapping_note="一般事業の現金及び預金に近いが、預け金（他行預け）を含むため完全等価ではない",
    ),
    BankingConceptMapping(
        concept="SecuritiesAssetsBNK",
        canonical_key="securities_bnk",
        label_ja="有価証券",
        label_en="Securities (banking)",
        ...,
        display_order=2,
    ),
    BankingConceptMapping(
        concept="LoansAndBillsDiscountedAssetsBNK",
        canonical_key="loans_bnk",
        label_ja="貸出金",
        label_en="Loans and bills discounted",
        ...,
        display_order=3,
        general_equivalent=None,  # 一般事業に対応なし（銀行の本業資産）
    ),
    # ... CallLoans, ReceivablesUnderResaleAgreements 等の主要資産
    # --- 負債の部（銀行固有） ---
    BankingConceptMapping(
        concept="DepositsLiabilitiesBNK",
        canonical_key="deposits_bnk",
        label_ja="預金",
        label_en="Deposits",
        ...,
        general_equivalent=None,  # 一般事業に対応なし（銀行の本業負債）
    ),
    # ... CallMoney, BorrowedMoney 等
)

_COMMON_BS_MAPPINGS: tuple[BankingConceptMapping, ...] = (
    # --- 純資産の部（一般事業と共通） ---
    # jgaap.py: Assets → "total_assets"
    BankingConceptMapping(
        concept="Assets",
        canonical_key="total_assets",
        ...
    ),
    # jgaap.py: Liabilities → "total_liabilities"
    # jgaap.py: NetAssets → "net_assets"
    # 等
)
```

### 6.4 CF マッピング（直接法・間接法分離）

```python
_CF_DIRECT_MAPPINGS: tuple[BankingConceptMapping, ...] = (
    # 銀行業 CF 直接法固有の営業活動科目
    BankingConceptMapping(
        concept="CollectionOfLoansReceivableOpeCFBNK",
        canonical_key="collection_of_loans_bnk",
        label_ja="貸出金の回収による収入",
        label_en="Collection of loans receivable",
        statement_type=StatementType.CASH_FLOW_STATEMENT,
        period_type="duration",
        display_order=1,
    ),
    # ... 他の直接法主要科目
)

_CF_INDIRECT_MAPPINGS: tuple[BankingConceptMapping, ...] = (
    # 銀行業 CF 間接法固有の営業活動調整項目
    # display_order は直接法の続き（直接法 1-4, 間接法 5-8）で衝突を回避
    BankingConceptMapping(
        concept="IncreaseDecreaseInAllowanceForLoanLossesOpeCFBNK",
        canonical_key="change_in_loan_loss_allowance_bnk",
        label_ja="貸倒引当金の増減額",
        label_en="Increase/decrease in allowance for loan losses",
        statement_type=StatementType.CASH_FLOW_STATEMENT,
        period_type="duration",
        display_order=5,  # 直接法の最大値(4)の次から開始
    ),
    # ... 他の間接法主要調整科目 (display_order=6, 7, 8)
)

_COMMON_CF_MAPPINGS: tuple[BankingConceptMapping, ...] = (
    # display_order は間接法の続き（直接法 1-4, 間接法 5-8, 共通 9-11）
    # jgaap.py: NetCashProvidedByUsedInOperatingActivities → "operating_cf"  (display_order=9)
    # jgaap.py: NetCashProvidedByUsedInInvestingActivities → "investing_cf"  (display_order=10)
    # jgaap.py: NetCashProvidedByUsedInFinancingActivities → "financing_cf"  (display_order=11)
)
```

**`mappings_for_statement(CF)` の振る舞い**: 直接法・間接法の両方を返す。将来の CF 表示機能で使い分ける（本レーンのスコープ外）。

---

## 7. 内部アーキテクチャ

### 7.1 ファイル構成

```
src/edinet/xbrl/sector/
├── __init__.py          ← 既存（変更しない）
└── banking.py           ← 新規作成

tests/
├── test_xbrl/
│   └── test_sector_banking.py  ← 新規作成
└── fixtures/
    └── sector_banking/  ← 新規ディレクトリ（必要に応じて）
```

### 7.2 banking.py の内部構造

```python
# 1. 型エイリアス + データモデル定義
#    - PeriodType = Literal["instant", "duration"]
#    - BankingConceptMapping (frozen dataclass)
#    - BankingProfile (frozen dataclass)

# 2. マッピングタプル（Python ハードコード = Single Source of Truth）
#    銀行固有:
#    - _PL_BANKING_MAPPINGS   (~13 エントリ)
#    - _BS_BANKING_MAPPINGS   (~12 エントリ)
#    - _CF_DIRECT_MAPPINGS    (~4 エントリ)
#    - _CF_INDIRECT_MAPPINGS  (~4 エントリ)
#    共通（jgaap.py と同じ canonical_key）:
#    - _COMMON_PL_MAPPINGS    (~7 エントリ)
#    - _COMMON_BS_MAPPINGS    (~3 エントリ)
#    - _COMMON_CF_MAPPINGS    (~3 エントリ)

# 3. _validate_registry()（モジュールロード時に 1 回実行）
#    - concept の重複なし
#    - canonical_key の重複なし
#    - display_order が statement_type 内で一意
#    - period_type が有効値（"instant" or "duration"）
#    - concept, canonical_key, label_ja, label_en が空でない

# 4. インデックス構築（モジュールロード時に 1 回だけ）
#    - _CONCEPT_INDEX: dict[str, BankingConceptMapping]
#    - _KEY_INDEX: dict[str, BankingConceptMapping]
#    - _ALL_MAPPINGS: tuple[BankingConceptMapping, ...]
#    - _ALL_CANONICAL_KEYS: frozenset[str]
#    - _BANKING_SPECIFIC_CONCEPTS: frozenset[str]
#      （is_banking_concept() 用。銀行固有タプルの concept のみ。共通科目を含まない）

# 5. 公開 API 関数
#    - lookup(), canonical_key(), reverse_lookup() 等

# 6. プロファイル定義
#    - _PROFILES: dict[str, BankingProfile]
```

### 7.3 共通科目の扱い

銀行業と一般事業で共通する科目（`OrdinaryIncome`, `ProfitLoss` 等）は、`_COMMON_*_MAPPINGS` として banking.py 内にも重複定義する。

**理由**:
- `banking.py` は `jgaap.py` に依存しない独立モジュールとする（並列実装の安全ルール遵守）
- 共通科目の canonical_key は jgaap.py と**必ず同一**にする（`ordinary_income`, `net_income` 等）
- Wave 3 L1 の normalize レイヤーが「銀行業でも `canonical_key="net_income"` で当期純利益を取れる」ことを保証する

### 7.4 _validate_registry() の仕様

jgaap.py の `_validate_registry()` と同等の検証をモジュールロード時に実行する。
**ただし `general_equivalent` の jgaap 存在チェックはロード時に行わない**（banking.py が jgaap.py への実行時依存を持たないようにするため）。jgaap との整合性検証はテスト側（`test_general_equivalent_exists_in_jgaap`）で保証する。

```python
def _validate_registry() -> None:
    """レジストリの整合性を検証する。

    banking.py 内部の整合性のみを検証する。
    jgaap.py への実行時依存は持たない（独立モジュールの設計方針）。
    general_equivalent と jgaap.py の整合性はテスト側で保証する。

    以下をチェック:
    - concept の重複がないこと
    - canonical_key の重複がないこと
    - period_type が "instant" or "duration" であること
    - concept, canonical_key, label_ja, label_en が空文字列でないこと
    - display_order が同一 statement_type 内で一意であること

    Raises:
        ValueError: 整合性違反が検出された場合。
    """
```

### 7.5 normalize との連携ポイント

Wave 3 L1 の `standards/normalize.py` が banking.py を使う想定フロー:

```
1. detect_accounting_standard() → J-GAAP
2. 企業の業種コードを取得（EDINET コード一覧 or schemaRef から推定）
3. 業種コードが bk1/bk2 → banking.lookup(concept) で canonical_key 取得
4. 業種コードが cai 等 → jgaap.lookup(concept) で canonical_key 取得
5. canonical_key で統一アクセス
```

**重要**: normalize.py への統合は L1 の責務。本レーン（L2）はデータ（マッピング）と API を提供するのみ。

---

## 8. テスト設計

### 8.1 テストカテゴリと優先度

| カテゴリ | テスト数 | 優先度 | 内容 |
|---------|---------|--------|------|
| P0: Core API | 12 | 必須 | lookup, canonical_key, reverse_lookup の基本動作 |
| P0: マッピング整合性 | 8 | 必須 | canonical_key の一意性、general_equivalent の整合性、statement_type の正しさ |
| P0: 共通科目の一致 | 5 | 必須 | jgaap.py と同じ canonical_key が使われていることの検証 |
| P1: プロファイル | 4 | 推奨 | BankingProfile の取得と bk1/bk2 の差異 |
| P1: エッジケース | 5 | 推奨 | 存在しない concept, None 返却, 空文字列 |
| P1: CF 直接法/間接法 | 3 | 推奨 | CF マッピングの分離が正しいこと |
| **合計** | **~37** | | |

### 8.2 P0 テスト詳細

```python
# --- Core API テスト ---
def test_lookup_banking_specific():
    """銀行固有科目が lookup できる。"""
    m = lookup("OrdinaryIncomeBNK")
    assert m is not None
    assert m.canonical_key == "ordinary_revenue_bnk"
    assert m.label_ja == "経常収益"

def test_lookup_common_concept():
    """共通科目（経常利益等）が lookup できる。"""
    m = lookup("OrdinaryIncome")
    assert m is not None
    assert m.canonical_key == "ordinary_income"

def test_lookup_unknown():
    """銀行マッピングに登録されていない科目は None。"""
    assert lookup("NetSales") is None  # NetSales は銀行マッピングに未登録

def test_canonical_key_returns_string():
    """canonical_key() は文字列を返す。"""
    assert canonical_key("OrdinaryIncomeBNK") == "ordinary_revenue_bnk"

def test_canonical_key_unknown():
    """未登録 concept は None。"""
    assert canonical_key("UnknownConcept") is None

def test_reverse_lookup():
    """canonical_key からの逆引き。"""
    m = reverse_lookup("ordinary_revenue_bnk")
    assert m is not None
    assert m.concept == "OrdinaryIncomeBNK"

def test_all_mappings_not_empty():
    """全マッピングが空でない。"""
    assert len(all_mappings()) > 0

def test_mappings_for_income_statement():
    """PL マッピングが取得できる。"""
    pl = mappings_for_statement(StatementType.INCOME_STATEMENT)
    assert len(pl) > 0
    assert all(m.statement_type == StatementType.INCOME_STATEMENT for m in pl)

# --- マッピング整合性テスト ---
def test_canonical_keys_unique():
    """canonical_key は全マッピングでユニーク。"""
    keys = [m.canonical_key for m in all_mappings()]
    assert len(keys) == len(set(keys))

def test_concepts_unique():
    """concept 名は全マッピングでユニーク。"""
    concepts = [m.concept for m in all_mappings()]
    assert len(concepts) == len(set(concepts))

def test_general_equivalent_exists_in_jgaap():
    """general_equivalent が設定されている場合、
    jgaap.py にその canonical_key が存在する。

    NOTE: jgaap.py のマッピング変更時はこのテストも影響を受ける。
    これは意図された振る舞い（cross-module 整合性の保証）。
    """
    from edinet.financial.standards.jgaap import all_canonical_keys as jgaap_keys
    jgaap = jgaap_keys()
    for m in all_mappings():
        if m.general_equivalent is not None:
            assert m.general_equivalent in jgaap, (
                f"{m.concept} の general_equivalent={m.general_equivalent!r} が "
                f"jgaap.py に存在しない"
            )

def test_common_concepts_match_jgaap_canonical_keys():
    """共通科目の canonical_key が jgaap.py と一致する。

    NOTE: jgaap.py のマッピング変更時はこのテストも影響を受ける。
    """
    from edinet.financial.standards.jgaap import canonical_key as jgaap_ck
    # 共通科目リスト（PL 下部）— jgaap.py から実値を確認済み
    common = {
        "OrdinaryIncome": "ordinary_income",
        "IncomeBeforeIncomeTaxes": "income_before_tax",
        "ProfitLoss": "net_income",
    }
    for concept, expected_ck in common.items():
        banking_ck = canonical_key(concept)
        jgaap_result = jgaap_ck(concept)
        assert banking_ck == jgaap_result == expected_ck, (
            f"{concept}: banking={banking_ck}, jgaap={jgaap_result}, expected={expected_ck}"
        )

def test_display_order_positive():
    """display_order は全て正の整数。"""
    for m in all_mappings():
        assert m.display_order > 0

def test_display_order_unique_within_statement():
    """display_order は statement_type 内でユニーク。"""
    from collections import defaultdict
    by_st: dict[StatementType | None, list[int]] = defaultdict(list)
    for m in all_mappings():
        by_st[m.statement_type].append(m.display_order)
    for st, orders in by_st.items():
        assert len(orders) == len(set(orders)), (
            f"statement_type={st} で display_order に重複あり: {orders}"
        )

def test_period_type_matches_statement():
    """PL/CF は duration、BS は instant。"""
    for m in all_mappings():
        if m.statement_type == StatementType.BALANCE_SHEET:
            assert m.period_type == "instant", f"{m.concept}"
        elif m.statement_type in (
            StatementType.INCOME_STATEMENT,
            StatementType.CASH_FLOW_STATEMENT,
        ):
            assert m.period_type == "duration", f"{m.concept}"

# --- 銀行固有科目の判定テスト ---
def test_is_banking_concept_true_for_bnk():
    """銀行固有科目は is_banking_concept() == True。"""
    assert is_banking_concept("OrdinaryIncomeBNK") is True

def test_is_banking_concept_false_for_common():
    """共通科目は銀行固有ではない（banking.py に登録されていても False）。"""
    assert is_banking_concept("ProfitLoss") is False
    assert is_banking_concept("OrdinaryIncome") is False

def test_banking_to_general_map_not_empty():
    """クロスマッピングが空でない。"""
    mapping = banking_to_general_map()
    assert len(mapping) > 0
    assert "ordinary_revenue_bnk" in mapping
    assert mapping["ordinary_revenue_bnk"] == "revenue"
```

### 8.3 P1 テスト

```python
def test_get_profile_bk1():
    """bk1 プロファイルが取得できる。"""
    p = get_profile("bk1")
    assert p is not None
    assert p.has_consolidated_template is True
    assert "銀行" in p.name_ja

def test_get_profile_bk2():
    """bk2 プロファイルが取得できる。"""
    p = get_profile("bk2")
    assert p is not None
    assert p.has_consolidated_template is False
    assert "特定取引" in p.name_ja

def test_get_profile_unknown():
    """銀行以外の業種は None。"""
    assert get_profile("cai") is None
    assert get_profile("cns") is None

def test_is_banking_industry():
    """bk1, bk2 は銀行業。"""
    assert is_banking_industry("bk1") is True
    assert is_banking_industry("bk2") is True
    assert is_banking_industry("cai") is False
    assert is_banking_industry("in1") is False

def test_cf_direct_and_indirect_both_in_cf():
    """CF マッピングに直接法・間接法の両方が含まれる。"""
    cf = mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)
    keys = {m.canonical_key for m in cf}
    # 直接法固有
    assert "collection_of_loans_bnk" in keys
    # 間接法固有
    assert "change_in_loan_loss_allowance_bnk" in keys
```

---

## 9. 完了条件

| # | 条件 | 検証方法 |
|---|------|---------|
| 1 | `lookup("OrdinaryIncomeBNK")` が `BankingConceptMapping` を返す | ユニットテスト |
| 2 | `canonical_key("OrdinaryIncomeBNK")` が `"ordinary_revenue_bnk"` を返す | ユニットテスト |
| 3 | `reverse_lookup("ordinary_revenue_bnk")` が `BankingConceptMapping` を返す | ユニットテスト |
| 4 | 全 canonical_key がユニーク | テスト `test_canonical_keys_unique` |
| 5 | 共通科目の canonical_key が `jgaap.py` と一致（`ProfitLoss` → `net_income` 等） | テスト `test_common_concepts_match_jgaap_canonical_keys` |
| 6 | `general_equivalent` が設定されている場合、`jgaap.py` に存在 | テスト `test_general_equivalent_exists_in_jgaap` |
| 7 | PL マッピング: 銀行固有 ~13 + 共通 ~7 = ~20 科目 | `mappings_for_statement(PL)` の len |
| 8 | BS マッピング: 銀行固有 ~12 + 共通 ~3 = ~15 科目 | `mappings_for_statement(BS)` の len |
| 9 | CF マッピング: 直接法 ~4 + 間接法 ~4 + 共通 ~3 = ~11 科目 | `mappings_for_statement(CF)` の len |
| 10 | `_validate_registry()` がモジュールロード時にエラーなく完了 | import 成功 |
| 11 | `is_banking_concept()` が共通科目で False、銀行固有で True | ユニットテスト |
| 12 | `uv run pytest` が全テストパス（既存テスト含む） | CI |
| 13 | `uv run ruff check src tests` がクリーン | CI |
| 14 | 既存テストに影響なし | 既存テスト全パス |

---

## 10. 実装順序

```
Step 1: データモデル定義
  - PeriodType 型エイリアス
  - BankingConceptMapping dataclass
  - BankingProfile dataclass
  - 型アノテーション、docstring

Step 2: PL マッピングタプル
  - **事前検証**: `concept_sets.derive_concept_sets()` を `industry_code="bk1"` で実行し、
    PL の実際の concept 名リストを取得。計画書記載の concept 名との突合を実施する
  - _PL_BANKING_MAPPINGS (~13 銀行固有科目)
  - _COMMON_PL_MAPPINGS (~7 共通科目)
  - 共通科目の canonical_key は jgaap.py を参照して正確に転記

Step 3: BS マッピングタプル
  - **事前検証**: タクソノミの `r/bk1/` ディレクトリの Presentation Linkbase から
    BS の実際の concept 名を確認。~12 科目の見積もりが妥当かを検証する
  - _BS_BANKING_MAPPINGS (~12 銀行固有科目)
  - _COMMON_BS_MAPPINGS (~3 共通科目)

Step 4: CF マッピングタプル
  - _CF_DIRECT_MAPPINGS (~4 直接法銀行固有科目)
  - _CF_INDIRECT_MAPPINGS (~4 間接法銀行固有科目)
  - _COMMON_CF_MAPPINGS (~3 共通科目)

Step 5: _validate_registry() 実装
  - concept 重複なし
  - canonical_key 重複なし
  - display_order が statement_type 内で一意
  - period_type が valid
  - 空文字列チェック
  - モジュールロード時に呼び出し

Step 6: インデックス構築 + 公開 API
  - _CONCEPT_INDEX, _KEY_INDEX
  - _ALL_MAPPINGS, _ALL_CANONICAL_KEYS
  - _BANKING_SPECIFIC_CONCEPTS（銀行固有タプルの concept 集合）
  - lookup(), canonical_key(), reverse_lookup() 等

Step 7: プロファイル定義
  - _PROFILES: {"bk1": BankingProfile(...), "bk2": BankingProfile(...)}
  - get_profile(), is_banking_industry()
  - bk1: "銀行・信託業", has_consolidated_template=True, cf_method="both"
  - bk2: "銀行・信託業（特定取引勘定設置銀行）", has_consolidated_template=False, cf_method="both"
    ※ bk2 の個別 CF テンプレートの直接法/間接法の有無はタクソノミデータで未確認。
      デフォルト "both" として実装し、タクソノミ確認後に確定する。

Step 8: 銀行業固有 API
  - is_banking_concept()（_BANKING_SPECIFIC_CONCEPTS で O(1) 判定）
  - general_equivalent()
  - banking_to_general_map()

Step 9: テスト作成
  - P0 テスト ~25 件
  - P1 テスト ~12 件

Step 10: リント・検証
  - ruff check
  - 既存テスト全パス確認
```

---

## 11. 将来の拡張ポイント（本レーンのスコープ外）

| 拡張 | 担当 | 備考 |
|------|------|------|
| normalize.py への統合 | Wave 3 L1 | banking.lookup() を業種判定で呼び分ける |
| ConceptSet との連携 | Wave 3 L1 | `registry.get(PL, industry_code="bk1")` でフィルタ |
| `general_to_banking_map()` の追加 | 将来 | 逆方向マッピング（general → banking）。normalize が「銀行の売上高相当は？」に応答する際に必要 |
| 銀行業の display/statements | Wave 4+ | 経常収益/経常費用の階層表示 |
| 信用金庫・信用組合 | 将来 | bk1/bk2 以外の金融業種 |
| 業種の自動判定 | 将来 | schemaRef + EDINET コード一覧から業種コードを推定 |
| Lane 3 (insurance) との `general_equivalent` 統一 | Wave 3 統合 | 現在 insurance は `general_business_concept` に concept 名を格納する設計。統合時に canonical_key 格納に統一すべき。また `NetIncomeINS.general_equivalent="profit"` は jgaap.py の `"net_income"` と不一致のため `"net_income"` に修正が必要 |
| Lane 4 との `cai_equivalent` → `general_equivalent` 統一 | Wave 3 統合 | Lane 4 は `cai_equivalent` フィールド名を使用。`cai` は業種コード固有の略語でユーザーに不透明。`general_equivalent` の方が「一般事業会社との対応」という意味を正確に伝える。Wave 3 統合タスクで Lane 4 側を修正する |
| JSON コード生成スクリプト | 将来 | sector モジュールが増えた場合の保守性向上（tools/ に配置） |
| canonical_key サフィックス方針の統一 | Wave 3 統合 | Lane 2 は `_bnk` サフィックスを使用（`ordinary_revenue_bnk`）、Lane 4 はサフィックスなし（`operating_revenue`）。グローバル一意性と自己文書化の観点から Lane 2 方式が優れるが、統一方針の最終決定は統合タスクに委ねる |

---

## 12. フィードバック反映サマリー

| フィードバック | 分類 | 対処 |
|--------------|------|------|
| M-1: cns は建設業 | MUST | `cns` → `cai` に全修正。フィールド名を `general_equivalent` に改名 |
| M-2: cns_equivalent のセマンティクス不一致 | MUST | `general_equivalent`（canonical_key 格納）に統一。Lane 3 との統合は将来タスク |
| M-3: bk1/bk2 の説明が逆 | MUST | C-3.a.md に基づき正確に修正。bk1=普通銀行、bk2=特定取引勘定設置銀行 |
| M-4: 共通科目の canonical_key 不一致 | MUST | jgaap.py 実コード確認: ProfitLoss→`net_income`, IncomeBeforeIncomeTaxes→`income_before_tax` |
| S-1: フィールド統一 | SHOULD | `PeriodType` alias、`mapping_note` 追加、デフォルト値付与 |
| S-2: ordinary_income_bnk 混同リスク | SHOULD | `ordinary_revenue_bnk` に改名 |
| S-3: is_banking_concept 仕様曖昧 | SHOULD | 方式(C): 銀行固有タプルの concept のみ True、共通科目は False |
| S-4: has_consolidated 不適切 | SHOULD | `has_consolidated_template` に改名。タクソノミテンプレートの有無を示す |
| S-5: _validate_registry 未記載 | SHOULD | Section 7.4 に仕様追加、Step 5 に実装追加 |
| C-4: display_order の設計 | CONSIDER | statement_type 内で 1 始まり連番と明記 |
| C-5: CF 直接法/間接法の分離 | CONSIDER | `_CF_DIRECT_MAPPINGS` / `_CF_INDIRECT_MAPPINGS` に分離 |
| L-1: docstring の INS サフィックス | 軽微 | 削除 |
| L-2: test_lookup_unknown のコメント | 軽微 | 正確な表現に修正 |
| L-3: BankingProfile の name_ja | 軽微 | タクソノミ設定規約書に準拠した正式名称を使用 |

### 第2回フィードバック反映

| フィードバック | 分類 | 対処 |
|--------------|------|------|
| M-1(R2): _validate_registry の jgaap 依存除去 | MUST | Section 7.4 修正: `general_equivalent` の jgaap 存在チェックをロード時から除去。テスト側で保証する設計に変更。banking.py は jgaap.py への実行時依存ゼロ |
| S-1(R2): Lane 4 との general_equivalent/cai_equivalent 不一致 | SHOULD | Section 11 に統合タスクとして追記 |
| S-2(R2): bk2 の cf_method 根拠不明 | SHOULD | Step 7 修正: `cf_method="both"` をデフォルトに変更。タクソノミ確認後に確定する旨を注記 |
| S-3(R2): mapping_note の活用不十分 | SHOULD | 実装時に主要科目（InterestIncomeOIBNK, DepositsLiabilitiesBNK 等）に追加 |
| S-4(R2): Lane 3 の general_equivalent 不整合 | SHOULD | Section 11 に Lane 3 の NetIncomeINS.general_equivalent 修正タスクを追記 |
| C-1(R2): 共通科目の general_equivalent 冗長性 | CONSIDER | 方針(B) 現状維持を採用。Section 3.2 に根拠を明記 |
| C-2(R2): is_banking_concept 構築方法 | CONSIDER | 既に Section 7.2 項目4 で十分明確。対応不要 |
| C-3(R2): テストの jgaap 依存明記 | CONSIDER | 既に docstring の NOTE で明記済み。対応不要 |
| C-4(R2): CF display_order 衝突 | CONSIDER | Section 6.4 修正: 直接法 1-4, 間接法 5-8, 共通 9-11 の連番に変更 |
| L-1(R2): 省略部分の注記 | 軽微 | 実装時に全フィールドを記述 |
| L-2(R2): BS 概念リスト | 軽微 | 実装時にタクソノミ XSD で確認 |
| L-3(R2): 完了条件のレンジ表記 | 軽微 | ~表記のまま。概算が適切（実装時に微調整ありうるため） |

### 第3回フィードバック反映

| フィードバック | 分類 | 対処 |
|--------------|------|------|
| S-1(R3): canonical_key サフィックス方針の Lane 4 との不整合 | SHOULD | Section 11 に統合タスクとして追記。Lane 2 の `_bnk` サフィックス方針を維持 |
| S-2(R3): all_mappings() の返却順序未定義 | SHOULD | Section 5.1 の `all_mappings()` docstring に連結順序を明記（PL銀行固有→PL共通→BS銀行固有→BS共通→CF直接法→CF間接法→CF共通） |
| S-3(R3): cf_method の使途不明 | SHOULD | Section 4.2 の `BankingProfile` docstring に情報提供用フィールドである旨を明記 |
| C-1(R3): from_general_key 逆引き API | CONSIDER | Section 11 に既に記載済み。対応不要 |
| C-2(R3): is_banking_concept と lookup の非対称性 | CONSIDER | 意図された設計。テストで検証済み。実装時に docstring で明確化 |
| C-3(R3): SectorRegistry パターンとの統合コスト | CONSIDER | 低コストの書き換え。対応不要 |
| C-4(R3): 共通科目の industry_codes デフォルト値 | CONSIDER | 現状維持 (A)。banking.py 内での意味として正しい |
| L-1(R3): 共通 PL の general_equivalent 省略 | 軽微 | 実装時に全共通科目で general_equivalent=canonical_key を設定 |
| L-2(R3): テスト数合計の ±3 ずれ | 軽微 | 想定内。対応不要 |

### 第4回フィードバック反映

| フィードバック | 分類 | 対処 |
|--------------|------|------|
| S-1(R4): Lane 4 `SectorConceptMapping` との型統一方針の欠如 | SHOULD | Section 3.1 に設計判断根拠を追記。並列安全ルールにより独自型を使う理由を明記 |
| S-2(R4): `to_legacy_concept_list()` 互換 API の検討 | SHOULD | 対応不要の確認。banking は JSON レガシーを持たないためブリッジ API 不要 |
| S-3(R4): BS マッピングの具体的 concept 名リスト不足 | SHOULD | Step 3 にタクソノミ Presentation Linkbase からの concept 名確認ステップを追記 |
| C-1(R4): `is_total` の `OrdinaryIncomeBNK`/`OrdinaryExpensesBNK` への設定 | CONSIDER | 採用。両科目に `is_total=True` を設定（内訳の合計行であるため） |
| C-2(R4): CF `display_order` の番号空間 | CONSIDER | 現状維持 (A)。表示順序の最適化は display 機能の責務 |
| C-3(R4): concept 名の正確性保証 | CONSIDER | Step 2 冒頭にタクソノミからの concept 名確認ステップを追記 |
| L-1(R4): `TradingIncomeOIBNK` の注釈整合 | 軽微 | Section 6.1 のコメントが正確。対応不要 |
| L-2(R4): 業種コード取得方法 | 軽微 | banking.py 側は受け取るだけ。対応不要 |

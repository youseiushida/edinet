# Wave 3 / Lane 4 — sector/construction + sector/railway + sector/securities: 特定業種の科目マッピング

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 3 / Lane 4 を担当するエージェントです。
担当機能: sector_others（建設業・鉄道業・証券業の業種固有科目マッピング）

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
   - `src/edinet/xbrl/sector/_base.py` (新規)
   - `src/edinet/xbrl/sector/construction.py` (新規)
   - `src/edinet/xbrl/sector/railway.py` (新規)
   - `src/edinet/xbrl/sector/securities.py` (新規)
   - `tests/test_xbrl/test_sector_construction.py` (新規)
   - `tests/test_xbrl/test_sector_railway.py` (新規)
   - `tests/test_xbrl/test_sector_securities.py` (新規)
   - `tests/test_xbrl/test_sector_base.py` (新規)
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
     例: `tests/fixtures/sector_construction/`, `tests/fixtures/sector_securities/` 等

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.financial.sector.construction import lookup` （OK）
   - 例: `from edinet.financial.sector import construction` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_sector_*.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - Wave 1・Wave 2 で完成したモジュールは import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.dei` (DEI, AccountingStandard, PeriodType, extract_dei)
     - `edinet.xbrl._namespaces` (NS_* 定数, classify_namespace, NamespaceInfo 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl.taxonomy.concept_sets` (ConceptSet, ConceptSetRegistry, derive_concept_sets 等)
     - `edinet.financial.standards.detect` (DetectedStandard, detect_accounting_standard 等)
     - `edinet.financial.standards.jgaap` (ConceptMapping, lookup, canonical_key 等)
     - `edinet.financial.standards.ifrs` (IFRSConceptMapping 等)
     - `edinet.financial.standards.usgaap` (USGAAPSummary 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning 等)
   - **他の Wave 3 レーンが作成中のモジュール**（normalize, sector/banking, sector/insurance）に依存してはならない

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 4 — sector/construction + sector/railway + sector/securities

## 0. 位置づけ

### FEATURES.md との対応

Wave 3 Lane 4 は、FEATURES.md の **Sector-Specific** セクションに対応する。建設業・鉄道業・証券業の 3 業種について、業種固有の勘定科目を `canonical_key` にマッピングし、一般事業会社の科目体系との対応関係を提供するモジュール群。

FEATURES.md の定義:

> - sector/construction: 建設業 [TODO]
>   - detail: 完成工事高、完成工事原価、完成工事総利益
> - sector/railway: 鉄道業 [TODO]
>   - detail: 運輸収入、運輸雑収、運輸外収入
> - sector/securities: 証券業 [TODO]
>   - detail: 受入手数料、トレーディング損益、金融収益

### FUTUREPLAN.tmp.md での位置

> Wave 3 L4: sector/construction + railway + securities → L1 concept_sets 依存

### なぜ 3 業種を 1 Lane にまとめるか

| 業種 | concept 数（概数） | 複雑度 | 理由 |
|------|-------------------|--------|------|
| 銀行 (BNK) | 245 | 高 | PL 構造が根本的に異なる。Lane 2 で単独 |
| 保険 (INS) | 229 | 高 | PL 構造が根本的に異なる。Lane 3 で単独 |
| 証券 (SEC) | 96 | 中 | PL に独自構造あるが概念数は適度 |
| 建設 (cns) | ~30-40 | 低 | PL の上位 3 科目が異なるのみ |
| 鉄道 (rwy) | ~30-40 | 低 | PL の収益区分が異なるのみ |

証券は中程度、建設・鉄道は低複雑度。3 業種合わせても銀行 1 業種より小さいため、1 Lane で並列実装可能。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.taxonomy.concept_sets` (Wave 2 L1) | ConceptSetRegistry, ConceptSet | read-only |
| `edinet.financial.standards.jgaap` (Wave 2 L3) | ConceptMapping データ型、canonical_key 命名規約 | read-only |
| `edinet.models.financial.StatementType` | 財務諸表タイプ Enum | read-only |

他レーンとのファイル衝突なし（全て新規ファイル作成）。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| E-5 | 直接 | 業種別 PL/BS 構造、concept サフィックス規約（BNK/INS/SEC）、業種固有 concept 一覧 |
| C-3 | 直接 | 23 業種カテゴリコード一覧、`cns`=建設業・`rwy`=鉄道・`sec`=証券の確認 |
| I-1 | 関連 | Role URI と財務諸表の対応、業種別 role URI は ListOfAccounts のみ |
| E-1 | 関連 | 財務諸表の種類と識別（PL/BS/CF/SS/CI） |
| E-1d | 関連 | CF の直接法/間接法の識別 |

---

## 1. 背景知識

### 1.1 業種サフィックス規約（E-5.a.md より）

`jppfs_cor` 名前空間内で、業種固有の concept は名前末尾にサフィックスを持つ:

| サフィックス | 業種 | concept 数 | Lane |
|-------------|------|-----------|------|
| `BNK` | 銀行・信託業 (bk1/bk2) | 245 | L2 |
| `INS` | 生命/損害保険業 (in1/in2) | 229 | L3 |
| `SEC` | 第一種金融商品取引業 (sec) | 96 | **L4** |
| （サフィックスなし） | 建設業 (cns) | ~30-40 | **L4** |
| （サフィックスなし） | 鉄道業 (rwy) | ~30-40 | **L4** |

**重要**: 建設業・鉄道業の concept は明示的なサフィックス（BNK や SEC のような接尾辞）を持たない。代わりに concept 名自体が業種固有の意味を持つ（例: `CompletedConstructionContracts`）。実装時にタクソノミ XSD で正確な concept 名を確認すること。

### 1.2 証券業 (SEC) の PL 構造（E-5.a.md より）

```
OperatingRevenueSEC（営業収益）
  ├── CommissionReceivedORSEC（受入手数料）
  │     ├── CommissionToConsigneesORSEC（委託手数料）
  │     └── OtherFeesReceivedORSEC（その他の受入手数料）
  ├── NetTradingIncomeORSEC（トレーディング損益）
  │     ├── NetTradingIncomeFromSecuritiesORSEC（有価証券等トレーディング損益）
  │     └── NetTradingIncomeFromBondsORSEC（債券等トレーディング損益）
  ├── FinancialRevenueORSEC（金融収益）
  └── ...
FinancialExpensesSEC（金融費用）
NetOperatingRevenueSEC（純営業収益）= 営業収益 - 金融費用
SellingGeneralAndAdministrativeExpensesSEC（販売費・一般管理費）
OperatingProfitSEC（営業利益）
```

**特徴**: 「純営業収益」（営業収益 - 金融費用）が証券業固有の中間利益概念。

### 1.3 証券業 (SEC) の BS 構造（E-5.a.md より）

| 科目 | concept 名 | 一般事業会社での対応 |
|------|-----------|-------------------|
| トレーディング商品(資産) | `TradingProductsCASEC` | 対応なし |
| トレーディング商品(負債) | `TradingProductsCLSEC` | 対応なし |
| 信用取引資産 | `MarginTransactionAssetsCASEC` | 対応なし |
| 信用取引負債 | `MarginTransactionLiabilitiesCLSEC` | 対応なし |
| 預託金 | `CashSegregatedAsDepositsCASEC` | 対応なし（顧客資産分別管理） |
| 金融商品取引責任準備金 | `ReserveForFinancialProductsTransaction...SEC` | 対応なし |

### 1.4 建設業 (cns) の PL 構造（FEATURES.md + タクソノミより）

建設業は一般事業会社の PL 構造をベースとするが、上位 3 科目が建設業固有:

```
一般事業 PL:        建設業 PL:
  売上高              完成工事高
  売上原価            完成工事原価
  売上総利益          完成工事総利益
  販管費              販管費（同じ）
  営業利益            営業利益（同じ）
  ...                 ...（以下同じ）
```

concept 名（タクソノミ XSD で要確認）:
- `NetSalesOfCompletedConstructionContracts` → 完成工事高
- `CostOfSalesOfCompletedConstructionContracts` → 完成工事原価
- `GrossProfitOnCompletedConstructionContracts` → 完成工事総利益

**設計ポイント**: 営業利益以下は一般事業と同じ。建設業固有の `canonical_key` は上位 3 概念のみ。一般事業の `revenue` / `cost_of_sales` / `gross_profit` と同じ canonical_key を振ることで、「売上高に相当する概念」としてクロスセクター比較を可能にする。

### 1.5 鉄道業 (rwy) の PL 構造（FEATURES.md + タクソノミより）

鉄道業は収益を運輸事業と兼業事業に区分:

```
鉄道業 PL:
  運輸収入（鉄道事業営業収益）
  運輸雑収（鉄道事業営業雑収）
  ＝ 鉄道事業営業収益合計
  兼業事業営業収益
  ＝ 営業収益合計
  運輸費
  ＝ 鉄道事業営業費用
  兼業事業営業費用
  ＝ 営業費用合計
  営業利益
```

concept 名（タクソノミ XSD で要確認）:
- `RailwayBusinessOperatingRevenues` / 類似名 → 鉄道事業営業収益
- `TransportationRevenues` / 類似名 → 運輸収入
- `RailwayBusinessOperatingExpenses` / 類似名 → 鉄道事業営業費用

**設計ポイント**: 「運輸収入」を `revenue` にマッピングするか「営業収益合計」をマッピングするかは設計判断。一般事業の「売上高」に最も近い概念は「営業収益合計」のため、それを `revenue` にマッピングする。

### 1.6 ConceptSetRegistry との関係

`concept_sets.derive_concept_sets()` は**既に全 23 業種の概念セットを自動導出済み**。

```python
registry = derive_concept_sets(taxonomy_path)

# cns（建設業）の PL 概念セット
cns_pl = registry.get(StatementType.INCOME_STATEMENT, industry_code="cns")
# → ConceptSet: role_uri, category, concepts のタプル

# sec（証券業）の PL 概念セット
sec_pl = registry.get(StatementType.INCOME_STATEMENT, industry_code="sec")

# rwy（鉄道業）の PL 概念セット
rwy_pl = registry.get(StatementType.INCOME_STATEMENT, industry_code="rwy")
```

**concept_sets が提供するもの**: 「どの concept が PL/BS/CF に属するか」のリスト。
**sector モジュールが追加するもの**: 各 concept の `canonical_key` / ラベル / 一般事業会社との対応関係。

concept_sets は「概念の集合」、sector は「概念の意味付け」。両方が必要。

### 1.7 一般事業会社の canonical_key との対応

sector モジュールの核心は「この業種固有科目は、一般事業会社のどの科目に相当するか」を定義すること。

| 対応パターン | 例 | 方針 |
|-------------|------|------|
| **直接対応** | 建設 `完成工事高` ≈ 一般 `売上高` | `general_equivalent` で一般事業の `canonical_key` を指定 |
| **部分対応** | 証券 `受入手数料` ≈ 一般 `売上高` の一部 | 業種固有 `canonical_key` + `general_equivalent` |
| **対応なし** | 証券 `純営業収益` | 業種固有 `canonical_key` のみ |
| **共通科目** | 全業種 `営業利益` | `standards/jgaap.py` の `canonical_key` をそのまま使用（サフィックスなし） |

---

## 2. ゴール

### 2.1 機能要件

1. **SectorConceptMapping データクラスの定義**（`_base.py`）
   - `ConceptMapping`（jgaap.py）と同型の frozen dataclass
   - 追加フィールド: `industry_codes`（対応する業種コード集合）、`general_equivalent`（一般事業会社の対応 canonical_key）
   - **L4 の 3 業種（建設・鉄道・証券）用の共有基底型**。L2（banking）・L3（insurance）は並列安全ルール（ルール 8）により本モジュールに依存できないため、Wave 3 完了後の統合タスクで全 sector モジュールの共通基底型として統一する（§12.3 参照）

2. **建設業モジュール**（`construction.py`）
   - 業種コード: `cns`
   - PL 固有科目のマッピング（完成工事高、完成工事原価、完成工事総利益 等）
   - BS 固有科目のマッピング（未成工事支出金、工事損失引当金 等）
   - `lookup()` / `canonical_key()` / `reverse_lookup()` API

3. **鉄道業モジュール**（`railway.py`）
   - 業種コード: `rwy`
   - PL 固有科目のマッピング（運輸収入、運輸費 等）
   - BS 固有科目のマッピング（鉄道施設関連 等）
   - `lookup()` / `canonical_key()` / `reverse_lookup()` API

4. **証券業モジュール**（`securities.py`）
   - 業種コード: `sec`
   - PL 固有科目の全マッピング（営業収益、受入手数料、トレーディング損益、金融収益、純営業収益 等）
   - BS 固有科目のマッピング（トレーディング商品、信用取引資産/負債、預託金 等）
   - `lookup()` / `canonical_key()` / `reverse_lookup()` API

5. **一般事業会社マッピング**
   - 各業種固有科目 → 一般事業会社の `canonical_key` への対応表
   - `general_equivalent` フィールドで「この科目は一般事業のどの科目に相当するか」を提供

### 2.2 非ゴール（スコープ外）

- **banking / insurance の実装**: Lane 2・Lane 3 が担当
- **normalize への統合**: Wave 3 L1（normalize_integration）が担当
- **statements.py の変更**: Wave 3 L1 が担当
- **ConceptSetRegistry の変更**: 既存の concept_sets モジュールは変更しない
- **業種自動判別**: filer XSD の schemaRef から業種コードを推定する機能は別課題
- **全 23 業種の対応**: 本レーンは建設・鉄道・証券の 3 業種のみ。残り（水運 `wat`、高速道路 `hwy`、電気通信 `elc`、電気 `ele`、ガス `gas`、リース `lea` 等）は将来レーンで対応
- **`validate_against_concept_set()` ヘルパー**: concept_sets との突合検証は E2E テスト（§11）の責務とする。単体テストではハードコード値の正しさは自明であり、実タクソノミとの整合は E2E で検証する方が適切（§7.6 のテスト原則と整合）

### 2.3 非機能要件

- 全 API がモジュールレベルで事前構築されたデータを返す（O(1) ルックアップ）
- frozen dataclass のみ使用（不変データ）
- type hint 完備
- Google Style docstring（日本語）
- テストは Detroit 派（モック不使用、実データ型でテスト）

---

## 3. データモデル設計

### 3.1 SectorConceptMapping（`_base.py`）

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from edinet.models.financial import StatementType

# dei.py / jgaap.py と同一の型エイリアス。
# sector モジュールは dei に依存しない独立モジュールとするため再定義。
PeriodType = Literal["instant", "duration"]


@dataclass(frozen=True, slots=True)
class SectorConceptMapping:
    """業種固有 concept の正規化マッピング。

    jgaap.ConceptMapping と同型の構造を持ち、追加で業種コードと
    一般事業会社との対応関係を保持する。

    現時点では L4 の 3 業種（建設・鉄道・証券）用の共有基底型。
    Wave 3 完了後の統合タスクで L2（banking）・L3（insurance）の
    データクラスもこの型に統一する予定（§12.3 参照）。

    Attributes:
        concept: jppfs_cor のローカル名（例: "OperatingRevenueSEC"）。
        canonical_key: 業種内正規化キー（例: "operating_revenue_sec"）。
            同業種内で一意。小文字 snake_case。
            業種固有科目には業種サフィックス（_sec/_cns/_rwy）を付与する。
            一般事業会社と完全に同じ概念には jgaap.py と同じキーを使う
            （例: 営業利益 → "operating_income"）。
        label_ja: 日本語ラベル（例: "営業収益"）。
        label_en: 英語ラベル（例: "Operating revenue"）。
        statement_type: 所属する財務諸表。PL / BS / CF。
        period_type: 期間型。"instant" or "duration"。
        industry_codes: この concept を使用する業種コードの集合。
            例: frozenset({"sec"})。bk1/bk2 のように複数コードが
            同じ concept を使う場合は複数要素。
        general_equivalent: 一般事業会社の対応 canonical_key。
            一般事業会社に直接対応する概念がない場合は None。
            例: 建設 "完成工事高" → general_equivalent="revenue"。
            **注**: canonical_key を格納する（concept ローカル名ではない）。
            L2（banking）・L3（insurance）の同名フィールドと同じセマンティクス。
        display_order: 同一 statement_type 内での表示順序。**必須フィールド**。
            1 以上の値。同一 statement_type 内で一意でなければならない。
        is_total: 合計・小計行か。
        mapping_note: マッピングに関する補足説明。
    """

    concept: str
    canonical_key: str
    label_ja: str
    label_en: str
    statement_type: StatementType
    period_type: PeriodType
    industry_codes: frozenset[str]
    display_order: int
    general_equivalent: str | None = None
    is_total: bool = False
    mapping_note: str = ""
```

### 3.2 SectorProfile（`_base.py`）

```python
@dataclass(frozen=True, slots=True)
class SectorProfile:
    """業種プロファイル（静的メタデータ）。

    概念数などの動的な導出値は含まない。
    動的な値は SectorRegistry のプロパティとして提供する。

    Attributes:
        sector_id: 業種の識別子（例: "securities"）。
        display_name_ja: 日本語表示名（例: "第一種金融商品取引業"）。
        display_name_en: 英語表示名（例: "Type I Financial Instruments Business"）。
        industry_codes: EDINET タクソノミの業種コード集合（例: {"sec"}）。
        concept_suffix: concept 名のサフィックス（例: "SEC"）。
            サフィックスを持たない業種（建設業・鉄道業等）では空文字列。
        pl_structure_note: PL 構造の特徴の短い説明。
    """

    sector_id: str
    display_name_ja: str
    display_name_en: str
    industry_codes: frozenset[str]
    concept_suffix: str
    pl_structure_note: str
```

### 3.3 SectorRegistry（`_base.py`）

各 sector モジュール共通の API（lookup, canonical_key, reverse_lookup 等）を集約するレジストリクラス。
3 モジュール × 10 関数のボイラープレートを排除し、データ定義のみに集中できるようにする。

```python
class SectorRegistry:
    """業種固有マッピングのレジストリ。

    データタプル（_PL_MAPPINGS 等）と SectorProfile を受け取り、
    lookup / canonical_key / reverse_lookup 等の共通 API を提供する。
    各 sector モジュールはこのクラスのインスタンスを作成し、
    モジュールレベル関数として公開する。

    初期化時に _validate() を呼び出し、以下を検証する。
    検証エラー時は `ValueError` を送出する（データ定義の検証であり、
    パース処理ではないため `EdinetParseError` ではなく `ValueError` が適切）。
    エラーメッセージには `self.profile.sector_id` を含める:

    - concept の重複なし
    - canonical_key の重複なし
    - period_type が "instant" / "duration" のいずれか
    - 空の concept / canonical_key / label がない
    - industry_codes が空でないこと
    - industry_codes が profile.industry_codes の部分集合であること
    - display_order が同一 statement_type 内で一意であること
    - display_order > 0 であること（全件）

    **注**: general_equivalent が jgaap.py に存在するかの検証はロード時に行わない。
    sector モジュールは jgaap.py への実行時依存を持たない独立モジュールとする
    （L2 banking と同じ設計方針）。jgaap との整合性検証はテスト側で保証する。

    Attributes:
        profile: 業種プロファイル。
    """

    def __init__(
        self,
        mappings: tuple[SectorConceptMapping, ...],
        profile: SectorProfile,
    ) -> None: ...

    def __repr__(self) -> str:
        """REPL での表示用。"""

    def lookup(self, concept: str) -> SectorConceptMapping | None:
        """業種固有 concept 名からマッピング情報を取得する。"""

    def canonical_key(self, concept: str) -> str | None:
        """業種固有 concept 名を正規化キーにマッピングする。"""

    def reverse_lookup(self, key: str) -> SectorConceptMapping | None:
        """正規化キーから SectorConceptMapping を取得する（逆引き）。"""

    def mappings_for_statement(
        self, statement_type: StatementType,
    ) -> tuple[SectorConceptMapping, ...]:
        """指定した財務諸表タイプのマッピングを返す。display_order 順。"""

    def __len__(self) -> int:
        """マッピング数を返す。canonical_key_count と同値。"""

    def all_mappings(self) -> tuple[SectorConceptMapping, ...]:
        """全マッピングを返す。引数 mappings のタプル定義順を保持する。
        呼び出し側が PL + BS + CF の順で渡すことを期待する。"""

    def all_canonical_keys(self) -> frozenset[str]:
        """定義されている全正規化キーの集合を返す。"""

    @property
    def canonical_key_count(self) -> int:
        """定義されている正規化キーの総数を返す。"""

    def get_profile(self) -> SectorProfile:
        """この業種のプロファイルを返す。"""

    def to_general_key(self, sector_key: str) -> str | None:
        """業種固有 canonical_key → 一般事業会社の canonical_key へ変換する。"""

    def from_general_key(self, general_key: str) -> SectorConceptMapping | None:
        """一般事業会社の canonical_key → この業種の最も代表的な対応概念を取得する。

        タプル定義順で最初にマッチした概念を返す。
        複数候補が必要な場合は mappings_for_statement() + general_equivalent フィルタで
        取得すること。
        """

    def known_concepts(self) -> frozenset[str]:
        """マッピング済みの全 concept 名の集合を返す。"""
```

**内部実装の要点:**

```python
def __init__(self, mappings, profile):
    self._all = mappings
    self._by_concept = {m.concept: m for m in mappings}
    self._by_key = {m.canonical_key: m for m in mappings}
    # _by_general: 最初に出現するエントリを優先（= 最も包括的な概念）
    self._by_general: dict[str, SectorConceptMapping] = {}
    for m in mappings:
        if m.general_equivalent and m.general_equivalent not in self._by_general:
            self._by_general[m.general_equivalent] = m
    self._known = frozenset(self._by_concept)
    self._all_keys = frozenset(self._by_key)
    self._by_stmt = {
        st: tuple(m for m in mappings if m.statement_type == st)
        for st in StatementType
    }
    self.profile = profile
    self._validate()

def __repr__(self) -> str:
    return (
        f"SectorRegistry(sector_id={self.profile.sector_id!r}, "
        f"mappings={len(self._all)}, "
        f"industry_codes={self.profile.industry_codes})"
    )

def __len__(self) -> int:
    return len(self._all)

@property
def canonical_key_count(self) -> int:
    return len(self._all)

def _validate(self) -> None:
    sid = self.profile.sector_id
    seen_concepts: set[str] = set()
    for m in self._all:
        if m.concept in seen_concepts:
            raise ValueError(f"{sid}: concept が重複: {m.concept}")
        seen_concepts.add(m.concept)
    # ... 他のチェックも同様に sid をプレフィックスに含める
```

### 3.4 設計根拠

**なぜ `ConceptMapping`（jgaap.py）を継承/再利用せず新データクラスを定義するか:**

1. `ConceptMapping` は `is_jgaap_specific` フィールドを持つ — 業種固有モジュールでは不適切
2. 業種固有科目には `industry_codes` と `general_equivalent` が必要 — `ConceptMapping` にない
3. frozen dataclass は継承で新フィールドを追加できない（slots 制約）
4. 構造は同型なので、normalize レイヤーでの変換は容易

**なぜ `SectorRegistry` クラスを導入するか:**

1. 3 モジュール × 10 関数 = 600 行のほぼ同一コードを排除できる
2. 各 sector モジュールがデータ定義のみに集中できる（各モジュール 30-50 行の削減）
3. API の一貫性が構造的に保証される
4. `_validate()` を `__init__` 内で一度書けば全モジュールに適用
5. 将来 L2/L3 統合時にも同じ `SectorRegistry` を使える（§12.3 の統合コスト大幅削減）

**なぜ `general_equivalent` を持たせるか:**

クロスセクター比較の核心。ユーザーが「全業種の売上高相当を取得したい」と言ったとき、
一般事業の `revenue` = 建設の `completed_construction_revenue_cns` = 証券の `operating_revenue_sec`
という対応関係を sector モジュールが提供する。normalize レイヤーがこの情報を使って横断集約を行う。

**`general_equivalent` には canonical_key を格納する**（concept ローカル名ではない）。
L2（banking）・L3（insurance）の同名フィールドと同じセマンティクス・同じフィールド名。

**`canonical_key` と `general_equivalent` が同一の場合がある。** これは「この業種固有科目が一般事業の同名概念と完全に等価である」ことを意味する（例: 証券業の営業利益 = 一般事業の営業利益。`canonical_key="operating_income"`, `general_equivalent="operating_income"`）。正常な状態であり、`to_general_key("operating_income")` → `"operating_income"` という自明な変換が発生するが問題ない。

**canonical_key に業種サフィックス（`_sec`/`_cns`/`_rwy`）を付与する理由:**
L2（`_bnk`）・L3（`_ins`）と同じ方針。グローバル一意性の確保、自己文書化（キー名だけで業種が判別可能）、normalize の逆引き安全性が理由。ただし一般事業と完全等価な概念（例: `operating_income`）にはサフィックスを付けない。

**`statement_type` を `StatementType | None` にしない理由（YAGNI）:**
現時点では sector モジュールに KPI は不要。将来的に業種固有 KPI（例: 証券業の自己資本規制比率）を追加する場合は `StatementType | None` に変更する必要があるが、現時点での先取りは不要。

---

## 4. API 設計

### 4.1 共通 API パターン（全 sector モジュール共通）

各 sector モジュール（construction.py, railway.py, securities.py）は `SectorRegistry`（§3.3）のインスタンスを通じて以下の共通 API を提供する。API は `SectorRegistry` のメソッドとして定義され、各モジュールがモジュールレベル関数として公開する。

API 一覧（詳細は §3.3 の `SectorRegistry` docstring を参照）:

| 分類 | 関数名 | 戻り値型 |
|------|--------|---------|
| ルックアップ | `lookup(concept)` | `SectorConceptMapping \| None` |
| ルックアップ | `canonical_key(concept)` | `str \| None` |
| ルックアップ | `reverse_lookup(key)` | `SectorConceptMapping \| None` |
| 一覧取得 | `mappings_for_statement(statement_type)` | `tuple[SectorConceptMapping, ...]` |
| 一覧取得 | `all_mappings()` | `tuple[SectorConceptMapping, ...]` |
| 一覧取得 | `all_canonical_keys()` | `frozenset[str]` |
| プロファイル | `get_profile()` | `SectorProfile` |
| プロパティ | `canonical_key_count` | `int` |
| 一般事業対応 | `to_general_key(sector_key)` | `str \| None` |
| 一般事業対応 | `from_general_key(general_key)` | `SectorConceptMapping \| None` |
| ConceptSet 突合 | `known_concepts()` | `frozenset[str]` |

**`from_general_key()` の 1:N 対応ルール:**
同一の `general_equivalent` を持つ複数のマッピングがある場合（例: 建設業で「完成工事高」と「不動産事業等売上高」が両方 `general_equivalent="revenue"` を持つ場合）、`_PL_MAPPINGS` / `_BS_MAPPINGS` のタプル定義順で**最初に出現するもの**を返す。この規約により、**最も包括的な概念をタプルの先頭に配置する**ことが各モジュールの義務となる。複数候補が必要な場合は `mappings_for_statement() + general_equivalent` フィルタで取得する。

### 4.2 実装パターン

全 sector モジュールは以下の内部パターンで実装する:

```python
__all__ = [
    "lookup",
    "canonical_key",
    "reverse_lookup",
    "mappings_for_statement",
    "all_mappings",
    "all_canonical_keys",
    "get_profile",
    "to_general_key",
    "from_general_key",
    "known_concepts",
]

# --- 内部データ定義（モジュールレベル） ---
# ★ タプル定義順の規約: 同一 general_equivalent を持つ概念が複数ある場合、
#   最も包括的な概念を先頭に配置すること（from_general_key() が先頭を返すため）

_PL_MAPPINGS: tuple[SectorConceptMapping, ...] = (
    SectorConceptMapping(
        concept="OperatingRevenueSEC",
        canonical_key="operating_revenue_sec",
        label_ja="営業収益",
        label_en="Operating revenue",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        industry_codes=frozenset({"sec"}),
        display_order=1,
        general_equivalent="revenue",
        is_total=True,
    ),
    # ...
)

_BS_MAPPINGS: tuple[SectorConceptMapping, ...] = (...)
_CF_MAPPINGS: tuple[SectorConceptMapping, ...] = (...)  # CF が業種固有の場合のみ

# --- SectorRegistry を使った API 公開 ---

_ALL_MAPPINGS = _PL_MAPPINGS + _BS_MAPPINGS + _CF_MAPPINGS

_PROFILE = SectorProfile(
    sector_id="securities",
    display_name_ja="第一種金融商品取引業",
    display_name_en="Type I Financial Instruments Business",
    industry_codes=frozenset({"sec"}),
    concept_suffix="SEC",
    pl_structure_note="純営業収益（営業収益 - 金融費用）が固有の中間利益概念",
)

_registry = SectorRegistry(mappings=_ALL_MAPPINGS, profile=_PROFILE)

# モジュールレベル関数として公開（jgaap.py と同じパターン）
lookup = _registry.lookup
canonical_key = _registry.canonical_key
reverse_lookup = _registry.reverse_lookup
mappings_for_statement = _registry.mappings_for_statement
all_mappings = _registry.all_mappings
all_canonical_keys = _registry.all_canonical_keys
get_profile = _registry.get_profile
to_general_key = _registry.to_general_key
from_general_key = _registry.from_general_key
known_concepts = _registry.known_concepts
```

**注**: `SectorRegistry.__init__` 内で `_validate()` が自動実行されるため、モジュールロード時にデータ定義のミスが即座に検出される。各モジュールに個別の `_validate_registry()` 呼び出しは不要。

**注**: `sector/__init__.py` の変更は不要。`from edinet.financial.sector._base import SectorRegistry` による直接 import で `_base.py` にアクセス可能。

**注**: `_base.py` にも `__all__` を定義する:
```python
__all__ = [
    "SectorConceptMapping",
    "SectorProfile",
    "SectorRegistry",
]
```

---

## 5. 業種別 Concept マッピング

### 5.1 証券業 (SEC) — PL マッピング

E-5.a.md で確認済みの concept を使用。

| # | concept | canonical_key | label_ja | general_equivalent | period_type | is_total | display_order |
|---|---------|---------------|----------|-------------------|-------------|----------|---------------|
| 1 | `OperatingRevenueSEC` | `operating_revenue_sec` | 営業収益 | `revenue` | duration | True | 1 |
| 2 | `CommissionReceivedORSEC` | `commission_received_sec` | 受入手数料 | None | duration | False | 2 |
| 3 | `NetTradingIncomeORSEC` | `net_trading_income_sec` | トレーディング損益 | None | duration | False | 3 |
| 4 | `FinancialRevenueORSEC` | `financial_revenue_sec` | 金融収益 | None | duration | False | 4 |
| 5 | `FinancialExpensesSEC` | `financial_expenses_sec` | 金融費用 | None | duration | False | 5 |
| 6 | `NetOperatingRevenueSEC` | `net_operating_revenue_sec` | 純営業収益 | `gross_profit` | duration | True | 6 |
| 7 | `SellingGeneralAndAdministrativeExpensesSEC` | `sga_expenses` | 販売費・一般管理費 | `sga_expenses` | duration | False | 7 |
| 8 | `OperatingProfitSEC` | `operating_income` | 営業利益 | `operating_income` | duration | True | 8 |

**注**: 証券業の「純営業収益」は一般事業の「売上総利益」に相当する中間利益概念（= 営業収益 - 金融費用）。
**注**: 一般事業と完全等価な概念（販管費・営業利益）にはサフィックスを付けない。
**注**: #7 および #8 は concept 名に SEC サフィックスがあるが、`canonical_key` には業種サフィックスを付けない。意味的に一般事業の同名概念と完全等価であるため（§9.4 のルール「一般事業と完全等価な概念にはサフィックス不要」に基づく）。jgaap.py にも `sga_expenses` / `operating_income` が存在することを確認済み。

### 5.2 証券業 (SEC) — BS マッピング

| # | concept | canonical_key | label_ja | general_equivalent | period_type | is_total | display_order |
|---|---------|---------------|----------|-------------------|-------------|----------|---------------|
| 1 | `TradingProductsCASEC` | `trading_products_assets_sec` | トレーディング商品(資産) | None | instant | False | 1 |
| 2 | `TradingProductsCLSEC` | `trading_products_liab_sec` | トレーディング商品(負債) | None | instant | False | 2 |
| 3 | `MarginTransactionAssetsCASEC` | `margin_transaction_assets_sec` | 信用取引資産 | None | instant | False | 3 |
| 4 | `MarginTransactionLiabilitiesCLSEC` | `margin_transaction_liab_sec` | 信用取引負債 | None | instant | False | 4 |
| 5 | `CashSegregatedAsDepositsCASEC` | `cash_segregated_sec` | 預託金 | None | instant | False | 5 |

**注**: BS の主要合計科目（総資産、純資産等）は一般事業と共通の concept を使用するため、sector モジュールでは業種固有の科目のみをマッピングする。共通科目は `standards/jgaap.py` の `canonical_key` がそのまま使われる。

### 5.3 建設業 (cns) — PL マッピング

**concept 名は実装時にタクソノミ XSD で要確認**。以下は推定名。**推定値であり、Step 1 のタクソノミ調査結果で §9.2 の方針に基づき変更の可能性あり**。特に `general_equivalent` の割り当て先（完成工事高 → `revenue` or 営業収益合計 → `revenue`）は実際のタクソノミ構造を確認してから最終決定すること。

| # | concept（推定） | canonical_key | label_ja | general_equivalent | period_type | is_total | display_order |
|---|----------------|---------------|----------|-------------------|-------------|----------|---------------|
| 1 | `NetSalesOfCompletedConstructionContracts` | `completed_construction_revenue_cns` | 完成工事高 | `revenue` | duration | False | 1 |
| 2 | `CostOfSalesOfCompletedConstructionContracts` | `completed_construction_cost_cns` | 完成工事原価 | `cost_of_sales` | duration | False | 2 |
| 3 | `GrossProfitOnCompletedConstructionContracts` | `completed_construction_gross_profit_cns` | 完成工事総利益 | `gross_profit` | duration | True | 3 |

**設計ポイント**:
- 営業利益以下は一般事業と同じ concept を使用（`OperatingIncome` 等）
- 建設業は `cns` ディレクトリの presentation linkbase で科目構成が定義される
- BS は未成工事支出金（`AdvancesReceivedOnUncompleted...`）等の建設固有科目がある可能性

### 5.4 建設業 (cns) — BS マッピング（推定）

| # | concept（推定） | canonical_key | label_ja | general_equivalent | period_type | is_total | display_order |
|---|----------------|---------------|----------|-------------------|-------------|----------|---------------|
| 1 | `CostsOnUncompletedConstructionContracts` | `uncompleted_construction_costs_cns` | 未成工事支出金 | None | instant | False | 1 |
| 2 | `AdvancesReceivedOnUncompletedConstructionContracts` | `advances_received_construction_cns` | 未成工事受入金 | None | instant | False | 2 |
| 3 | `ProvisionForLossOnConstructionContracts` | `provision_loss_construction_cns` | 工事損失引当金 | None | instant | False | 3 |

**注**: 未成工事支出金は概念的には棚卸資産に近いが、jgaap.py の現行 canonical_key に `inventories` が存在しないため `general_equivalent=None` とする。将来 jgaap.py に `inventories` が追加された場合に設定を検討する。

### 5.5 建設業 (cns) — CF マッピング

TEMP.md の E2E 結果で `cns CF=29 (non-abstract)` が確認済み。ただし 29 の CF concept の大半は一般事業と同じ concept（`NetCashProvidedByUsedInOperatingActivities` 等）である可能性が高い。

**方針**: Step 1 の調査で一般事業の CF concept と差分を比較し、建設業固有の CF concept（一般事業に存在しない concept）のみを `_CF_MAPPINGS` に含める。差分がゼロの場合は `_CF_MAPPINGS = ()` とし、共通 CF は jgaap.py にフォールバックさせる。

### 5.6 鉄道業 (rwy) — PL マッピング（推定）

**concept 名は実装時にタクソノミ XSD で要確認**。

| # | concept（推定） | canonical_key | label_ja | general_equivalent | period_type | is_total | display_order |
|---|----------------|---------------|----------|-------------------|-------------|----------|---------------|
| 1 | `RailwayOperatingRevenues` | `railway_operating_revenue_rwy` | 鉄道事業営業収益 | None | duration | True | 1 |
| 2 | `TransportationRevenues` | `transportation_revenue_rwy` | 運輸収入 | None | duration | False | 2 |
| 3 | `OtherRailwayOperatingRevenues` | `other_railway_revenue_rwy` | 運輸雑収 | None | duration | False | 3 |
| 4 | `IncidentalBusinessRevenues` | `incidental_business_revenue_rwy` | 兼業事業営業収益 | None | duration | False | 4 |
| 5 | `OperatingRevenues` | `total_operating_revenue_rwy` | 営業収益合計 | `revenue` | duration | True | 5 |
| 6 | `RailwayOperatingExpenses` | `railway_operating_expenses_rwy` | 鉄道事業営業費用 | None | duration | False | 6 |
| 7 | `OperatingExpenses` | `total_operating_expenses_rwy` | 営業費用合計 | `cost_of_sales` | duration | True | 7 |

**注意**: 鉄道業の concept 名は実データで確認が必要。タクソノミ `r/rwy/` ディレクトリの `_pre_pl.xml` を参照すること。

### 5.7 Concept 名の確認手順（実装時）

建設業・鉄道業の正確な concept 名は、タクソノミの presentation linkbase から導出する:

```bash
# 環境変数設定
EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101

# 建設業 PL の概念一覧
ls $EDINET_TAXONOMY_ROOT/taxonomy/jppfs/2025-11-01/r/cns/

# 鉄道業 PL の概念一覧
ls $EDINET_TAXONOMY_ROOT/taxonomy/jppfs/2025-11-01/r/rwy/
```

または concept_sets を使用:

```python
from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets
from edinet.models.financial import StatementType

registry = derive_concept_sets("/mnt/c/Users/nezow/Downloads/ALL_20251101")

# 建設業 PL
cns_pl = registry.get(StatementType.INCOME_STATEMENT, industry_code="cns")
for entry in cns_pl.concepts:
    print(f"{entry.concept:50s} depth={entry.depth} abstract={entry.is_abstract}")

# 鉄道業 PL
rwy_pl = registry.get(StatementType.INCOME_STATEMENT, industry_code="rwy")
for entry in rwy_pl.concepts:
    print(f"{entry.concept:50s} depth={entry.depth} abstract={entry.is_abstract}")
```

この出力結果に基づいて、§5.3〜5.5 の推定 concept 名を確定し、`_PL_MAPPINGS` / `_BS_MAPPINGS` タプルを完成させること。

---

## 6. Wave 3 L1 (normalize) との接続設計

### 6.1 normalize レイヤーとの契約

Wave 3 L1 が `standards/normalize.py` を実装する際、sector モジュールは以下の形で利用される:

```python
# normalize.py（L1 の実装。L4 は参照のみ）

# 一般事業会社の場合
mapping = jgaap.lookup(concept_name)

# 証券業の場合
from edinet.financial.sector.securities import lookup as sec_lookup
mapping = sec_lookup(concept_name)
if mapping and mapping.general_equivalent:
    # 一般事業会社の canonical_key に変換
    general_key = mapping.general_equivalent
```

### 6.2 L4 が提供すべきインターフェース

normalize レイヤーが sector モジュールを利用するために、各モジュールが提供する API:

1. `lookup(concept) → SectorConceptMapping | None`: concept 名から業種固有マッピングを取得
2. `to_general_key(sector_key) → str | None`: 業種固有 key → 一般事業の key
3. `known_concepts() → frozenset[str]`: 「この concept は業種固有か」の高速判定
4. `get_profile() → SectorProfile`: 業種メタデータ

### 6.3 normalize が使わないもの（L4 の内部用 / ユーザー向け）

- `from_general_key()`: 逆引き。normalize ではなくユーザー向け探索用
- `_PL_MAPPINGS` 等の内部タプル: 直接アクセスしない

---

## 7. テスト設計

### 7.1 テストファイル構成

> **注**: FUTUREPLAN.temp.md では `test_sector_others.py` 1 ファイルとされているが、3 業種 + 基底型で 4 ファイルに分割する。各業種が独立してテスト・デバッグ可能なため。

```
tests/test_xbrl/
  ├── test_sector_base.py           # SectorConceptMapping / SectorProfile のデータ型テスト
  ├── test_sector_construction.py   # 建設業のマッピングテスト
  ├── test_sector_railway.py        # 鉄道業のマッピングテスト
  └── test_sector_securities.py     # 証券業のマッピングテスト
```

### 7.2 test_sector_base.py

| ID | テスト | 内容 |
|----|--------|------|
| T1 | `test_sector_concept_mapping_frozen` | SectorConceptMapping が frozen であること |
| T2 | `test_sector_concept_mapping_required_fields` | 必須フィールドが全て設定されていること |
| T3 | `test_sector_profile_frozen` | SectorProfile が frozen であること |
| T4 | `test_sector_concept_mapping_defaults` | デフォルト値（is_total=False, general_equivalent=None, mapping_note="" 等）が正しいこと。display_order は必須フィールドであり、省略時に TypeError が送出されること |
| T4b | `test_sector_registry_validate_detects_duplicate_concept` | SectorRegistry が concept 重複でエラーを出すこと |
| T4c | `test_sector_registry_validate_detects_duplicate_key` | SectorRegistry が canonical_key 重複でエラーを出すこと |
| T4d | `test_sector_registry_validate_detects_empty_industry_codes` | SectorRegistry が空の industry_codes でエラーを出すこと |
| T4e | `test_sector_registry_canonical_key_count_property` | SectorRegistry.canonical_key_count プロパティがマッピング数を返すこと |
| T4f | `test_sector_registry_validate_detects_duplicate_display_order` | SectorRegistry が同一 statement_type 内の display_order 重複でエラーを出すこと |
| T4g | `test_sector_registry_repr` | SectorRegistry の __repr__ が有用な情報を含むこと |
| T4h | `test_sector_registry_len` | `len(registry)` が `canonical_key_count` と同値であること |
| T4i | `test_sector_registry_validate_raises_valueerror` | `_validate()` のエラーが `ValueError` であり、エラーメッセージに `sector_id` が含まれること |

### 7.3 test_sector_securities.py

| ID | テスト | 内容 |
|----|--------|------|
| T5 | `test_lookup_known_concept` | `lookup("OperatingRevenueSEC")` が正しい SectorConceptMapping を返す |
| T6 | `test_lookup_unknown_concept` | `lookup("NonExistentConcept")` が None を返す |
| T7 | `test_canonical_key_known` | `canonical_key("OperatingRevenueSEC")` → `"operating_revenue_sec"` |
| T8 | `test_canonical_key_unknown` | `canonical_key("NonExistentConcept")` → None |
| T9 | `test_reverse_lookup_known` | `reverse_lookup("operating_revenue_sec")` が正しいマッピングを返す |
| T10 | `test_reverse_lookup_unknown` | `reverse_lookup("nonexistent")` → None |
| T11 | `test_mappings_for_statement_pl` | PL マッピングが display_order 順で返る |
| T12 | `test_mappings_for_statement_bs` | BS マッピングが返る |
| T13 | `test_all_mappings_order` | PL → BS → CF の順で返る |
| T14 | `test_all_canonical_keys_type` | frozenset[str] が返る |
| T15 | `test_to_general_key_with_equivalent` | `to_general_key("operating_revenue_sec")` → `"revenue"` |
| T16 | `test_to_general_key_without_equivalent` | `to_general_key("net_trading_income_sec")` → None |
| T17 | `test_from_general_key_known` | `from_general_key("revenue")` → 営業収益のマッピング |
| T18 | `test_from_general_key_unknown` | `from_general_key("nonexistent")` → None |
| T19 | `test_get_profile` | SectorProfile の全フィールドが正しいこと |
| T20 | `test_known_concepts_type` | frozenset[str] が返る |
| T21 | `test_no_duplicate_canonical_keys` | canonical_key の重複がないこと |
| T22 | `test_no_duplicate_concepts` | concept 名の重複がないこと |
| T23 | `test_industry_codes_correct` | 全マッピングの industry_codes に "sec" が含まれること |
| T24 | `test_net_operating_revenue_is_sec_specific` | 純営業収益が証券業固有の概念であること |
| T25 | `test_general_equivalent_exists_in_jgaap` | general_equivalent が設定されている場合、jgaap.all_canonical_keys() に存在すること |

### 7.4 test_sector_construction.py

| ID | テスト | 内容 |
|----|--------|------|
| T30 | `test_lookup_completed_construction_revenue` | 完成工事高のルックアップ |
| T31 | `test_general_equivalent_revenue` | 完成工事高 → general_equivalent = "revenue" |
| T32 | `test_general_equivalent_cost` | 完成工事原価 → general_equivalent = "cost_of_sales" |
| T33 | `test_general_equivalent_gross_profit` | 完成工事総利益 → general_equivalent = "gross_profit" |
| T34 | `test_from_general_key_returns_most_comprehensive` | `from_general_key("revenue")` が営業収益合計（タプル先頭で最も包括的な概念）を返すこと（併営時の複数対応テスト） |
| T35 | `test_to_general_key_known` | `to_general_key("completed_construction_revenue_cns")` → `"revenue"` |
| T36 | `test_to_general_key_unknown` | `to_general_key("nonexistent")` → None |
| T37 | `test_all_mappings_non_empty` | マッピングが空でないこと |
| T38 | `test_get_profile_industry_codes` | profile.industry_codes == {"cns"} |
| T39 | `test_no_duplicate_canonical_keys` | canonical_key の重複なし |
| T40 | `test_industry_codes_cns` | 全マッピングの industry_codes に "cns" が含まれること |
| T41 | `test_general_equivalent_exists_in_jgaap` | general_equivalent が設定されている場合、jgaap.all_canonical_keys() に存在すること |

### 7.5 test_sector_railway.py

| ID | テスト | 内容 |
|----|--------|------|
| T50 | `test_lookup_transportation_revenue` | 運輸収入のルックアップ |
| T51 | `test_total_operating_revenue_general_equivalent` | 営業収益合計 → general_equivalent = "revenue" |
| T52 | `test_to_general_key_known` | `to_general_key("total_operating_revenue_rwy")` → `"revenue"` |
| T53 | `test_to_general_key_unknown` | `to_general_key("nonexistent")` → None |
| T54 | `test_from_general_key_known` | `from_general_key("revenue")` → 営業収益合計のマッピング |
| T55 | `test_all_mappings_non_empty` | マッピングが空でないこと |
| T56 | `test_get_profile_industry_codes` | profile.industry_codes == {"rwy"} |
| T57 | `test_no_duplicate_canonical_keys` | canonical_key の重複なし |
| T58 | `test_industry_codes_rwy` | 全マッピングの industry_codes に "rwy" が含まれること |
| T59 | `test_general_equivalent_exists_in_jgaap` | general_equivalent が設定されている場合、jgaap.all_canonical_keys() に存在すること |

### 7.6 テストの原則

- **モック不使用（Detroit 派）**: SectorConceptMapping の実オブジェクトを直接テスト
- **外部依存なし**: タクソノミファイルや API に依存しない。マッピングデータはモジュールにハードコードされているため、純粋な単体テスト
- **concept_sets との突合テストは E2E で実施**: 単体テストでは concept 名の正しさは自明（ハードコード値）。実タクソノミとの整合は E2E テストスクリプトで検証
- **テスト時依存**: T25/T41/T59 の `jgaap.all_canonical_keys()` 検証はテスト時依存であり、sector モジュール本体の実行時依存ではない。テストは検証のための特権コードとして jgaap モジュールを import する

---

## 8. 実装手順

### Step 1: タクソノミ概念の確認（調査フェーズ）

1. タクソノミ `r/cns/` ディレクトリの presentation linkbase を読み、建設業固有の **PL/BS/CF** concept 名を確定する。CF については一般事業 CF concept との差分を比較し、業種固有の CF concept のみをマッピング対象とする（§5.5 参照）
2. タクソノミ `r/rwy/` ディレクトリの presentation linkbase を読み、鉄道業固有の PL 概念名を確定する。**BS/CF についても `_pre_bs.xml`, `_pre_cf.xml` の有無を確認**し、業種固有の BS/CF 科目があれば追加マッピング対象とする
3. タクソノミ `r/sec/` ディレクトリで `_pre_cf.xml` の有無を確認し、証券業固有の CF 科目の要否を判断する
4. `concept_sets.derive_concept_sets()` で cns/rwy/sec の概念セットを取得し、マッピング対象を洗い出す。**`is_abstract=True` のエントリは sector マッピング対象から除外する**（abstract concept は XBRL インスタンスに値を持たない）。**業種コード名も確認すること**（C-3.q.md では建設業が `cna` と記載されており、`cns` と異なる可能性がある。`derive_concept_sets()` の実際の返り値で正式コードを確定する）
5. §5 の推定 concept 名を確定値で更新する。**推定 concept 名が不存在の場合は §9.5 の手順に従うこと**

### Step 2: _base.py の実装

1. `SectorConceptMapping` dataclass を定義
2. `SectorProfile` dataclass を定義
3. `SectorRegistry` クラスを定義（`_validate()` 含む）
4. テスト（test_sector_base.py: T1-T4i）を作成・実行

### Step 3: securities.py の実装

1. `_PL_MAPPINGS` / `_BS_MAPPINGS` タプルを定義（E-5.a.md の確認済み concept 名を使用）
2. `_PROFILE` を定義
3. `_registry = SectorRegistry(mappings=..., profile=_PROFILE)` を作成
4. モジュールレベル関数として公開（`lookup = _registry.lookup` 等）
5. `__all__` を定義
6. テスト（test_sector_securities.py: §7.3 T5-T25）を作成・実行

### Step 4: construction.py の実装

1. Step 1 で確定した concept 名で `_PL_MAPPINGS` / `_BS_MAPPINGS` タプルを定義。CF が業種固有の場合は `_CF_MAPPINGS` も定義
2. `_PROFILE` を定義、`_registry = SectorRegistry(...)` を作成
3. モジュールレベル関数として公開、`__all__` を定義
4. テスト（test_sector_construction.py: §7.4 T30-T41）を作成・実行

### Step 5: railway.py の実装

1. Step 1 で確定した concept 名で `_PL_MAPPINGS` タプルを定義（BS/CF 固有科目があれば `_BS_MAPPINGS` / `_CF_MAPPINGS` も）
2. `_PROFILE` を定義、`_registry = SectorRegistry(...)` を作成
3. モジュールレベル関数として公開、`__all__` を定義
4. テスト（test_sector_railway.py: §7.5 T50-T59）を作成・実行

### Step 6: 全体テスト

1. `uv run pytest tests/test_xbrl/test_sector_*.py -v` で全テスト通過を確認
2. `uv run pytest` で既存テストが壊れていないことを確認
3. `uv run ruff check src tests` でリントエラーがないことを確認

---

## 9. エッジケースと設計判断

### 9.1 同一 concept が複数業種で使われる場合

例: `OperatingIncome`（営業利益）は一般事業・建設業・鉄道業・証券業の全てで使用される。

**方針**: 共通 concept は `standards/jgaap.py` が担当。sector モジュールは**業種固有の concept のみ**をマッピングする。normalize レイヤーは、まず sector モジュールで検索し、見つからなければ jgaap.py にフォールバックする。

### 9.2 建設業の「不動産事業等」併営

大手建設会社は建設事業以外に不動産事業を併営していることが多い。この場合:
- 完成工事高（建設事業の売上）と不動産事業等売上高が並立
- 営業収益 = 完成工事高 + 不動産事業等売上高 + ...

**方針**: Step 1（タクソノミ調査）の結果で最終判断する。考慮すべき選択肢:
- **(A)** 営業収益合計を `general_equivalent="revenue"` にマッピングし、完成工事高・不動産事業等売上高は個別の `canonical_key` で `general_equivalent=None` とする
- **(B)** 完成工事高を `general_equivalent="revenue"` にマッピングする（§5.3 の現状の推定値）

選択は「営業収益合計」という concept がタクソノミに存在するかで決まる。存在する場合は (A)、存在しない場合は (B) を採用する。§5.3 のテーブルは推定値であり、Step 1 の調査結果で変更の可能性あり。

### 9.3 証券業の CF

証券業の CF 構造が一般事業と異なるかは、タクソノミ `r/sec/` の `_pre_cf.xml` の有無で判断する。CF が業種共通構造の場合、`_CF_MAPPINGS` は空タプルとし、共通 CF（jgaap.py）にフォールバックさせる。

### 9.4 canonical_key の命名規約

| 規約 | 例 |
|------|-----|
| 小文字 snake_case | `operating_revenue_sec` |
| 業種固有科目には業種サフィックスを付与 | `operating_revenue_sec`, `completed_construction_revenue_cns`, `transportation_revenue_rwy` |
| 一般事業と完全等価な概念にはサフィックス不要 | 建設の営業利益 → `operating_income`（jgaap.py と同じ） |
| 業種固有概念には説明的な名前 + サフィックス | `net_operating_revenue_sec`（証券固有の「純営業収益」） |

**理由**: L2（`_bnk`）・L3（`_ins`）と統一した方針。
- **グローバル一意性**: 将来の他業種追加時にキー衝突を防止
- **自己文書化**: canonical_key だけで業種が判別可能（デバッグ・ログで有用）
- **normalize の逆引き安全性**: canonical_key → 業種の特定が O(1) で可能
- 業種の追加メタデータは `industry_codes` フィールドが担う

### 9.5 推定 concept 名が不存在の場合

§5.3〜5.5 の concept 名は推定であり、タクソノミ XSD に存在しない可能性がある。

| ケース | 対処 |
|--------|------|
| 類似名で存在する | 正確な名前に置換。`mapping_note` に推定名からの変更を記録 |
| 概念自体が存在しない | マッピング対象から除外。`mapping_note` にその旨を記録 |
| 業種ディレクトリ（`r/cns/`, `r/rwy/`）自体が存在しない | 当該業種のモジュール全体をスタブ化し、空マッピング（`_PL_MAPPINGS = ()`）で提供。`get_profile()` の `pl_structure_note` に「タクソノミに業種ディレクトリ未検出」と記載 |

### 9.6 補足: 他業種の業種コードバリアント

銀行業（Lane 2 が担当）では bk1（銀行・信託業）と bk2（特定取引勘定設置銀行）が同じ BNK サフィックスの concept を共有しつつ、bk2 は追加の concept（特定取引勘定関連）を持つ。本レーンの 3 業種で同様のバリアント（同一 concept サフィックスを共有する複数の業種コード）が存在しないか、Step 1 のタクソノミ調査で確認すること。

---

## 10. 作成/変更ファイル一覧

| ファイル | 操作 | 行数（概算） |
|----------|------|-------------|
| `src/edinet/xbrl/sector/_base.py` | 新規 | 180-220（SectorRegistry クラス含む） |
| `src/edinet/xbrl/sector/construction.py` | 新規 | 80-100（データ定義のみ。API は SectorRegistry 委譲） |
| `src/edinet/xbrl/sector/railway.py` | 新規 | 70-90（データ定義のみ） |
| `src/edinet/xbrl/sector/securities.py` | 新規 | 100-130（データ定義のみ） |
| `tests/test_xbrl/test_sector_base.py` | 新規 | 80-100（SectorRegistry 検証含む） |
| `tests/test_xbrl/test_sector_construction.py` | 新規 | 80-100 |
| `tests/test_xbrl/test_sector_railway.py` | 新規 | 60-80 |
| `tests/test_xbrl/test_sector_securities.py` | 新規 | 150-180 |

**合計**: 新規 8 ファイル、約 800-1000 行。
**既存ファイルの変更なし。**

SectorRegistry の導入により `_base.py` が大きくなるが、各 sector モジュールは 30-50 行ずつ削減される（合計で元計画とほぼ同等の行数だが、重複コードが大幅に減少）。

---

## 11. E2E テスト計画（Wave 3 完了後）

### 11.1 E2E テストスクリプト

Wave 3 全レーン完了後に作成する `tools/wave3_e2e_sector.py`:

```python
# 建設業: 大林組 (E00073) or 鹿島建設 (E00060) の有報で完成工事高の存在を確認
#          大和ハウス工業 (E01164) — 不動産事業比率が高く §9.2 の併営ケース検証に最適
# 証券業: 大和証券グループ (E03773) の有報で受入手数料等の存在を確認（J-GAAP）
#          ※ Step 1 で AccountingStandardsDEI を確認し、J-GAAP であることを事前検証すること
#          ※ 野村HD (E03752) は US-GAAP のため DEI 確認のみ
#          SBI ホールディングス等も候補
# 鉄道業: JR東日本 (E04147) の有報で運輸収入の存在を確認
```

### 11.2 E2E で検証する事項

1. `concept_sets` で取得した業種固有概念セットと sector モジュールの `known_concepts()` の交差が空でないこと。定量カバレッジを出力する:
   ```python
   concept_set = registry.get(StatementType.INCOME_STATEMENT, industry_code="sec")
   sec_known = sec_module.known_concepts()
   overlap = sec_known & {e.concept for e in concept_set.concepts if not e.is_abstract}
   coverage = len(overlap) / len(sec_known)
   print(f"SEC PL coverage: {coverage:.0%} ({len(overlap)}/{len(sec_known)})")
   ```
2. 実 XBRL データから抽出した Fact の concept 名が sector モジュールで `lookup()` 可能であること
3. `to_general_key()` で一般事業への変換が正しく動作すること

---

## 12. 将来拡張ポイント

### 12.1 残り業種の追加

本レーンと同じパターンで以下の業種を追加可能:

| 業種 | コード | 複雑度 | 備考 |
|------|--------|--------|------|
| 水運 | `wat` | 低 | 運輸収入系。鉄道と類似構造 |
| 高速道路 | `hwy` | 低 | 料金収入系 |
| 電気通信 | `elc` | 低 | 営業収益系 |
| 電気事業 | `ele` | 中 | 電気事業営業収益/費用 |
| ガス事業 | `gas` | 中 | ガス事業営業収益/費用 |
| リース | `lea` | 低 | リース売上系 |

### 12.2 normalize レイヤーとの最終統合

Wave 3 L1 の `normalize.py` が完成した後:

```python
# normalize.py が sector モジュールを使う想定フロー:
# 1. detect() で会計基準を判別
# 2. industry_code を取得（DEI or schemaRef から）
# 3. industry_code に対応する sector モジュールを動的 import
# 4. sector.lookup(concept) でマッピング取得
# 5. sector.to_general_key() で一般事業の canonical_key に変換
# 6. 見つからない concept は jgaap.lookup() にフォールバック
```

### 12.3 Wave 3 完了後の sector モジュール統一ロードマップ

現状、L2/L3/L4 がそれぞれ独自のデータクラスを定義している。フィールド名は `general_equivalent` で統一済み（L2/L3/L4 共通）。格納する値も canonical_key で統一:

| Lane | データクラス | フィールド名 | 格納する値 | `statement_type` の型 |
|------|------------|------------|-----------|---------------------|
| L2 (banking) | `BankingConceptMapping` | `general_equivalent` | canonical_key | `StatementType \| None` |
| L3 (insurance) | `InsuranceConceptMapping` | `general_equivalent` | canonical_key | `StatementType \| None` |
| L4 (本計画) | `SectorConceptMapping` | `general_equivalent` | canonical_key | `StatementType`（None 不可） |

**注**: L4 は §3.4 で YAGNI を根拠に `StatementType | None` にしない判断をしている。L2/L3 の KPI 概念（`statement_type=None`）の吸収は統合タスク項目 2 で対処する。

L4 が先に完了した場合でも、L2/L3 は並列安全ルール 8 に基づき `_base.py` に依存しない。統合タスクで L2/L3 を `SectorRegistry` パターンに置換する際、L4 の `_base.py` をそのまま使用する。

Wave 3 完了後の統合タスクで以下を実施する:

```
1. _base.py の SectorConceptMapping + SectorRegistry を全 sector モジュールの共通基底型とする
2. SectorConceptMapping.statement_type を StatementType | None に拡張する
   - L2/L3 の KPI 概念（statement_type=None）を吸収するために必要
   - L4 の 3 業種は KPI を持たないため、L4 単体では影響なし
3. BankingConceptMapping → SectorConceptMapping に統一
   - フィールド名・セマンティクスは既に一致（general_equivalent）
   - banking.py 内の手書き API 関数群を削除し、_registry = SectorRegistry(...) + 委譲パターンに置換
4. InsuranceConceptMapping → SectorConceptMapping に統一
   - フィールド名は既に一致（general_equivalent）
   - insurance_sub_type → SectorConceptMapping に追加するか、別途メタデータとして分離
   - insurance.py 内の手書き API 関数群を SectorRegistry 委譲に置換
5. L2 の general_equivalent(concept) は to_general_key(canonical_key(concept)) の 2 ステップに
   分解される。引数の型が concept 名 vs canonical_key で異なるため、ラッパー関数が必要になる
   可能性がある。L3 の insurance_to_general_map() / insurance_specific_concepts() も同様に
   SectorRegistry の to_general_key() / known_concepts() に読み替える
6. SectorRegistry の _validate() が全モジュールに自動適用されることを確認
7. sector/__init__.py を更新してモジュール一覧を公開
8. PeriodType = Literal["instant", "duration"] の 3 重再定義
   （dei.py / jgaap.py / _base.py）を共有モジュール（edinet.xbrl._types 等）に集約
9. jgaap.py の `display_order: int = 0`（デフォルト値あり）を必須フィールドに変更し、
   SectorConceptMapping と統一する（L4 は `display_order > 0` を検証するため必須）
```

**SectorRegistry の利点**: L2/L3 統合時、データクラスの変更 + `_registry = SectorRegistry(...)` の 1 行追加だけで API の一貫性が構造的に保証される。手書きの 10 関数を 3 モジュール分書き換える必要がない。

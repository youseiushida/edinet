# Wave 3 / Lane 3 — sector/insurance: 保険業の科目定義とマッピング

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 3 / Lane 3 を担当するエージェントです。
担当機能: sector_insurance

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
   - `src/edinet/xbrl/sector/insurance.py` (新規)
   - `tests/test_xbrl/test_sector_insurance.py` (新規)
   - `tests/fixtures/sector_insurance/` (新規ディレクトリ — 必要な場合のみ)
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
     例: `tests/fixtures/sector_insurance/`

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.financial.sector.insurance import lookup` （OK）
   - 例: `from edinet.xbrl import insurance_lookup` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_sector_insurance.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - Wave 1・Wave 2 で完成したモジュールは import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.dei` (DEI, AccountingStandard, PeriodType, extract_dei)
     - `edinet.xbrl._namespaces` (NS_* 定数, classify_namespace, NamespaceInfo 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl.taxonomy.concept_sets` (ConceptSet, ConceptSetRegistry, derive_concept_sets 等)
     - `edinet.financial.standards.jgaap` (ConceptMapping, lookup, canonical_key 等)
     - `edinet.financial.standards.ifrs` (IFRSConceptMapping 等)
     - `edinet.financial.standards.detect` (detect_standard, DetectedStandard 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning 等)
   - **他の Wave 3 レーンが作成中のモジュール**（normalize, banking, sector_others）に依存してはならない

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 3 — sector/insurance: 保険業の科目定義とマッピング

## 0. 位置づけ

Wave 3 Lane 3 は、FEATURES.md の **Sector-Specific > sector/insurance** に対応する。保険業（生命保険 `in1`、損害保険 `in2`）が使用する `jppfs_cor` タクソノミ内の INS サフィックス付き科目を体系的に定義し、一般事業会社（`cai`）科目との canonical_key マッピングを提供するモジュール。

FEATURES.md の定義:

> - sector/insurance: 保険業 [TODO]
>   - detail: 正味収入保険料、保険引受利益、資産運用収益

FUTUREPLAN.tmp.md での位置:

> Wave 3 L3: `sector/insurance` → L1 concept_sets 依存

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.taxonomy.concept_sets` (Wave 2 L1) | ConceptSet の業種別データ（`in1`, `in2`）参照 | read-only |
| `edinet.financial.standards.jgaap` (Wave 2 L3) | ConceptMapping パターン参照、canonical_key 体系の共有 | read-only |
| `edinet.models.financial.StatementType` | 財務諸表タイプ Enum | read-only |

他レーンとのファイル衝突なし（全て新規ファイル作成）。

### QA 参照

| QA | タイトル | 関連度 |
|----|---------|--------|
| E-5 | 業種別の財務諸表の差異 | **直接（設計の基盤）** — 保険業 PL/BS の科目構造・concept 名・INS サフィックスの規約 |
| C-3 | 業種カテゴリコードの一覧 | 直接 — `in1`(生命保険業) / `in2`(損害保険業) の定義、23 業種体系 |
| E-1 | 財務諸表の種類と識別 | 関連 — role URI による PL/BS/CF の識別 |
| E-7 | 主要勘定科目の concept 名辞書 | 関連 — 一般事業会社側のマッピング先 |
| D-3 | 会計基準の判別方法 | 関連 — 保険業でも会計基準は J-GAAP |
| I-1 | Role URI と財務諸表の対応 | 関連 — 業種共通の role URI 体系 |

---

## 1. 背景知識

### 1.1 保険業の PL 構造（E-5.a.md より）

保険業の PL は一般事業会社の「売上高 → 売上原価 → 売上総利益 → 販管費 → 営業利益」構造とは**根本的に異なる**。「経常収益/経常費用」の 2 区分構造を取り、保険引受と資産運用の 2 本柱で構成される。

```
OperatingIncomeINS（経常収益）
  ├── InsurancePremiumsAndOtherOIINS（保険引受収益）
  │     ├── InsurancePremiumsOIINS（保険料等収入）
  │     └── ...
  ├── InvestmentIncomeOIINS（資産運用収益）
  │     ├── InterestDividendsAndOtherIncomeOIINS（利息及び配当金等収入）
  │     ├── GainOnSalesOfSecuritiesOIINS（有価証券売却益）
  │     └── ...
  └── OtherOrdinaryIncomeOIINS（その他経常収益）
OperatingExpensesINS（経常費用）
  ├── InsuranceClaimsAndOtherOEINS（保険引受費用）
  │     ├── InsuranceClaimsOEINS（保険金等支払金）
  │     ├── BenefitsOEINS（満期保険金）
  │     ├── SurrenderBenefitsOEINS（解約返戻金）
  │     └── ...
  ├── ProvisionOfPolicyReserveAndOtherOEINS（責任準備金等繰入額）
  │     ├── ProvisionOfPolicyReserveOEINS（支払備金繰入額）
  │     └── ProvisionOfOutstandingClaimsOEINS（責任準備金繰入額）
  ├── InvestmentExpensesOEINS（資産運用費用）
  ├── CommissionsAndCollectionFeesOEINS（事業費）
  └── ...
OrdinaryProfitINS（経常利益）
ExtraordinaryIncomeINS（特別利益）
ExtraordinaryLossINS（特別損失）
IncomeBeforeIncomeTaxesINS（税引前当期純利益）
NetIncomeINS（当期純利益）
```

### 1.2 保険業の BS 構造（E-5.a.md より）

保険業の BS にも固有の科目が多数存在する:

| 科目 | concept 名 | 特徴 |
|------|-----------|------|
| 保険契約準備金 | `ReserveForInsurancePolicyLiabilitiesLiabilitiesINS` | 保険固有の最大負債 |
| 支払備金 | `OutstandingClaimsLiabilitiesINS` | 保険金支払準備 |
| 責任準備金 | `PolicyReserveLiabilitiesINS` | 将来の保険金支払原資 |
| 保険約款貸付金 | `PolicyLoansAssetsINS` | 契約者貸付 |
| 有価証券 | `SecuritiesAssetsINS` | 保険業固有の有価証券区分 |

### 1.3 業種コードと INS サフィックス（C-3.a.md, E-5.a.md より）

- `in1`: 生命保険業（生命保険会社 — 日本生命、第一生命 等）
- `in2`: 損害保険業（損害保険会社 — 東京海上日動、損害保険ジャパン 等）
- 語彙層では `INS` で統一、関係層で `in1` / `in2` に分割
- `jppfs_cor` 名前空間内に 229 件の INS サフィックス付き concept が定義（E-5.a.md [F2]）
- `in1` と `in2` は同じ INS サフィックス concept を共有するが、プレゼンテーションリンクの構造が一部異なる可能性がある（生保と損保の財務諸表形式の差異）

### 1.4 role URI は業種共通（E-5.a.md [F8], I-1.a.md）

財務諸表本表の role URI は業種を問わず共通（例: `rol_ConsolidatedStatementOfIncome`）。業種差異は role URI 内のプレゼンテーションリンクで使用される concept セットの違いとして表現される。つまり保険業でも一般事業会社と同じ role URI を使用するが、その中に並ぶ concept が INS 固有のものになる。

### 1.5 concept_sets による自動導出（Wave 2 L1）

`taxonomy/concept_sets.py` の `ConceptSetRegistry` は、`derive_concept_sets()` で全 23 業種のプレゼンテーションリンクをスキャンし、業種コード → ConceptSet のマッピングを保持している。`registry.get(StatementType.INCOME_STATEMENT, industry_code="in1")` で保険業の PL 概念セットが取得できる。

**本モジュールの役割**: concept_sets が「どの concept が PL に属するか」の**集合**を提供するのに対し、本モジュールは各 concept に対して:
- `canonical_key`（保険業固有 + 一般事業会社との対応関係）
- 日本語/英語ラベル
- 合計行/保険固有フラグ等のメタデータ

を付与する。つまり concept_sets が「何があるか」、本モジュールが「それは何を意味するか」を担う。

---

## 2. ゴール

### 2.1 機能要件

1. **保険業 PL の主要科目マッピング**を `InsuranceConceptMapping` dataclass として定義する
   - 経常収益（OperatingIncomeINS）以下の収益構造
   - 経常費用（OperatingExpensesINS）以下の費用構造
   - 経常利益（OrdinaryProfitINS）以下の利益構造
   - 30-40 科目程度（主要科目 + 重要な中間合計）

2. **保険業 BS の主要科目マッピング**を定義する（INS サフィックス付きのみ）
   - 保険契約準備金、支払備金、責任準備金等の保険固有負債
   - 保険約款貸付金、有価証券等の保険固有資産
   - TotalAssets, NetAssets 等の共通科目（INS サフィックスなし）は **jgaap.py にフォールバック**で解決
   - 15-25 科目程度

3. **保険業 CF の主要科目マッピング**を定義する（INS サフィックス付きのみ）
   - 営業活動/投資活動/財務活動の 3 区分は一般事業会社と構造が共通
   - 保険固有の CF INS サフィックス付き科目があれば含める
   - 0-10 科目程度（INS 付き CF 科目が存在しない場合は 0 件で正常）

4. **canonical_key による一般事業会社との対応付け**を提供する
   - 保険業の OrdinaryProfitINS ≈ 一般事業会社の OrdinaryIncome → `ordinary_income`（jgaap.py 実値）
   - 保険業固有の科目には `_ins` サフィックス付きの canonical_key を新設（例: `insurance_premiums_ins`, `underwriting_income_ins`）
   - 双方向マッピング: 保険 concept → canonical_key、canonical_key → 保険 concept

5. **`in1`（生命保険）と `in2`（損害保険）の差異を明示的にモデル化する**
   - 共通の INS concept は `industry_codes=frozenset({"in1", "in2"})` で表現（デフォルト）
   - 生保固有の concept は `industry_codes=frozenset({"in1"})`、損保固有は `frozenset({"in2"})`
   - banking.py の同名フィールドと同じパターンで統一

6. **standards/jgaap.py と対称的な公開 API**を提供する
   - `lookup()`, `canonical_key()`, `reverse_lookup()`, `mappings_for_statement()`, `all_mappings()`, `all_canonical_keys()`
   - `get_profile()` で保険業プロファイルを返す
   - `insurance_specific_concepts()` で保険業固有科目を返す
   - `insurance_to_general_map()` で保険 canonical_key → 一般事業会社 canonical_key の辞書を返す

### 2.2 非機能要件

- `lxml` への依存なし（静的データ定義のため）
- 日本語 docstring（Google Style）
- 日本語エラーメッセージ
- frozen dataclass でイミュータブルなデータ構造
- モジュール読み込み時にレジストリのバリデーション実行（重複 concept 検出等）

### 2.3 スコープ外

- concept_sets からの自動導出（concept_sets は Wave 2 L1 の責務。本モジュールは人手定義のマッピングを提供）
- タクソノミ XML のパース（本モジュールは静的データ定義）
- 生保と損保の PL 構造の網羅的な差分調査（実装時に確認し、主要な差異のみモデル化。詳細は将来の拡張に委ねる）
- `to_legacy_concept_list()` 相当のレガシー JSON 互換 API（【H-3 第4回反映】新規モジュールのため JSON 二重管理の歴史がない。jgaap.py の `to_legacy_concept_list()` は Wave 2 以前の JSON データソースとの互換性のために存在するが、insurance.py にはその必要がない）

---

## 3. 設計

### 3.1 データモデル

```python
# src/edinet/xbrl/sector/insurance.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from edinet.models.financial import StatementType


PeriodType = Literal["instant", "duration"]

# 【M-1 第3回反映】業種コード定数をモジュールレベルで切り出し
INSURANCE_INDUSTRY_CODES: frozenset[str] = frozenset({"in1", "in2"})

# 【H-3 第3回反映】__all__ を明示的に定義
__all__ = [
    "INSURANCE_INDUSTRY_CODES",
    "InsuranceConceptMapping",
    "InsuranceProfile",
    "PeriodType",
    "all_canonical_keys",
    "all_mappings",
    "canonical_key",
    "get_profile",
    "insurance_specific_concepts",
    "insurance_to_general_map",
    "is_insurance_industry",
    "lookup",
    "mappings_for_statement",
    "reverse_lookup",
]

# InsuranceSubType enum は不要（YAGNI）。
# 生保固有/損保固有/共通の区分は industry_codes: frozenset[str] で表現する。
# banking.py と同じパターンで統一。
#   共通:     frozenset({"in1", "in2"})
#   生保固有: frozenset({"in1"})
#   損保固有: frozenset({"in2"})


@dataclass(frozen=True, slots=True)
class InsuranceConceptMapping:
    """保険業 concept の正規化マッピング。

    1 つの jppfs_cor 保険業固有 concept（INS サフィックス付き）について、
    正規化キーとメタデータを保持する。

    standards/jgaap.py の ConceptMapping と対称的な構造を持ち、
    canonical_key を共通キーとして Wave 3 L1 の normalize が
    会計基準横断・業種横断の統一アクセスを提供する。

    Attributes:
        concept: jppfs_cor のローカル名（例: ``"OperatingIncomeINS"``）。
            INS サフィックス付き。バージョン非依存。
        canonical_key: 正規化キー（例: ``"ordinary_income"``）。
            一般事業会社の canonical_key と共通のものは同一値を使用。
            保険業固有の科目には新規キーを定義。小文字 snake_case。
        label_ja: 日本語ラベル（例: ``"経常収益"``）。
        label_en: 英語ラベル（例: ``"Ordinary income"``）。
        statement_type: 所属する財務諸表。PL / BS / CF / None。
            KPI 科目等、特定の財務諸表に属さない場合は None。
            jgaap.py / banking.py と同じ ``StatementType | None`` 型。
        period_type: 期間型。``"instant"`` or ``"duration"``。
        industry_codes: この concept が使われる業種コードの集合。
            ``frozenset({"in1", "in2"})`` で生保・損保共通（デフォルト）、
            ``frozenset({"in1"})`` で生保固有、``frozenset({"in2"})`` で損保固有。
            banking.py の同名フィールドと同じパターン。
        is_total: 合計・小計行か。
        display_order: 標準的な表示順序。同一 statement_type 内の相対順序。
            1 始まり。ギャップあり（将来の挿入を許容するため）。
            セクターモジュール共通の方式（C-2 第3回反映: ギャップ方式をセクター標準とする）。
        general_equivalent: 一般事業会社（cai）の対応する canonical_key。
            概念的に等価な一般事業科目の canonical_key を格納する。
            対応がない保険業固有科目の場合は ``None``。
            banking.py の同名フィールドと同じセマンティクス。
        mapping_note: マッピングの補足情報。「近いが同一ではない」対応関係の根拠等を記載。
            banking.py の同名フィールドと対称（H-4 第3回反映）。
            使用しない場合はデフォルト空文字。
    """
    concept: str
    canonical_key: str
    label_ja: str
    label_en: str
    statement_type: StatementType | None  # 【C-1 第3回反映】jgaap.py / banking と型統一
    period_type: PeriodType
    industry_codes: frozenset[str] = frozenset({"in1", "in2"})
    is_total: bool = False
    display_order: int = 0
    general_equivalent: str | None = None
    mapping_note: str = ""  # 【H-4 第3回反映】banking.py と対称。重要なマッピングには根拠を記載
```

### 3.2 マッピングデータ定義

#### PL マッピング（30-40 件）

```python
_PL_MAPPINGS: tuple[InsuranceConceptMapping, ...] = (
    # ===== 経常収益 =====
    # display_order にギャップを設けている（1,2,3,...7, 10,...15, 20,...25）。
    # 将来の科目挿入を許容するための設計意図。
    # 【C-2 第3回反映】ギャップ方式をセクターモジュールの標準方式とする。
    # banking.py にもギャップ方式への移行を提案する。
    # 理由: セクターモジュールは業種固有科目の追加が将来的に予想されるため。
    InsuranceConceptMapping(
        concept="OperatingIncomeINS",
        # タクソノミ名は "Operating" だが意味は「経常収益」≠ 一般事業の OperatingIncome（営業利益）
        canonical_key="ordinary_revenue_ins",  # 【C-2, H-4反映】"income" ではなく "revenue"（経常収益≠経常利益）。banking の ordinary_revenue_bnk と統一
        label_ja="経常収益",
        label_en="Ordinary revenue (insurance)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=1,
        general_equivalent="revenue",  # 売上高に相当（完全等価ではない）。banking と同じパターン
        mapping_note="経常収益は売上高に相当するが、保険引受収益+資産運用収益+その他で構成される保険業固有の構造。",
    ),
    InsuranceConceptMapping(
        concept="InsurancePremiumsAndOtherOIINS",
        canonical_key="underwriting_income_ins",  # 【M-1反映】全固有科目に _ins サフィックス
        label_ja="保険引受収益",
        label_en="Underwriting income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=2,
    ),
    InsuranceConceptMapping(
        concept="InsurancePremiumsOIINS",
        canonical_key="insurance_premiums_ins",  # 【M-1反映】_ins サフィックス
        label_ja="保険料等収入",
        label_en="Insurance premiums",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=3,
    ),
    InsuranceConceptMapping(
        concept="InvestmentIncomeOIINS",
        canonical_key="investment_income_ins",  # 【M-1反映】_ins サフィックス
        label_ja="資産運用収益",
        label_en="Investment income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=4,
    ),
    InsuranceConceptMapping(
        concept="InterestDividendsAndOtherIncomeOIINS",
        canonical_key="interest_dividends_income_ins",  # 【M-1反映】_ins サフィックス
        label_ja="利息及び配当金等収入",
        label_en="Interest, dividends and other income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=5,
    ),
    InsuranceConceptMapping(
        concept="GainOnSalesOfSecuritiesOIINS",
        canonical_key="gain_on_sales_of_securities_ins",  # 【M-1反映】_ins サフィックス
        label_ja="有価証券売却益",
        label_en="Gain on sales of securities",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=6,
    ),
    InsuranceConceptMapping(
        concept="OtherOrdinaryIncomeOIINS",
        canonical_key="other_ordinary_income_ins",  # _ins あり（元から）
        label_ja="その他経常収益",
        label_en="Other ordinary income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=7,
    ),

    # ===== 経常費用 =====
    InsuranceConceptMapping(
        concept="OperatingExpensesINS",
        canonical_key="ordinary_expenses_ins",  # _ins あり（元から）
        label_ja="経常費用",
        label_en="Ordinary expenses (insurance)",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=10,
    ),
    InsuranceConceptMapping(
        concept="InsuranceClaimsAndOtherOEINS",
        canonical_key="underwriting_expenses_ins",  # 【M-1反映】_ins サフィックス
        label_ja="保険引受費用",
        label_en="Underwriting expenses",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=11,
    ),
    InsuranceConceptMapping(
        concept="InsuranceClaimsOEINS",
        canonical_key="insurance_claims_ins",  # 【M-1反映】_ins サフィックス
        label_ja="保険金等支払金",
        label_en="Insurance claims",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=12,
    ),
    InsuranceConceptMapping(
        concept="ProvisionOfPolicyReserveAndOtherOEINS",
        canonical_key="provision_policy_reserve_ins",  # 【M-1反映】_ins サフィックス
        label_ja="責任準備金等繰入額",
        label_en="Provision of policy reserve and other",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=13,
    ),
    InsuranceConceptMapping(
        concept="InvestmentExpensesOEINS",
        canonical_key="investment_expenses_ins",  # 【M-1反映】_ins サフィックス
        label_ja="資産運用費用",
        label_en="Investment expenses",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=14,
    ),
    InsuranceConceptMapping(
        concept="CommissionsAndCollectionFeesOEINS",
        canonical_key="business_expenses_ins",  # 【M-2反映】operating_expenses_ins → business_expenses_ins。「事業費」は保険業固有概念
        label_ja="事業費",
        label_en="Business expenses",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=15,
        general_equivalent="sga_expenses",  # 一般事業の販管費に相当。jgaap.py 実値確認済み
        mapping_note="保険業の「事業費」は一般事業の販管費に機能的に相当するが、構成要素が異なる（代理店手数料・集金費等を含む）。",
    ),

    # ===== 利益 =====
    InsuranceConceptMapping(
        concept="OrdinaryProfitINS",
        # 【C-3 第3回反映】保険業では営業利益が存在せず、経常収益 - 経常費用 = 経常利益の直接計算。
        # 一般事業の OrdinaryIncome と概念的に同一だが算出過程が異なる。
        # 一般事業: 営業利益 + 営業外収益 - 営業外費用 = 経常利益
        # 保険業:   経常収益 - 経常費用 = 経常利益（営業利益の概念が存在しない）
        canonical_key="ordinary_income",  # 【C-2反映】jgaap.py の OrdinaryIncome と同一 canonical_key
        label_ja="経常利益",
        label_en="Ordinary profit",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=20,
        general_equivalent="ordinary_income",  # 【C-2反映】jgaap.py の実 canonical_key
        mapping_note="保険業では営業利益が存在せず、経常収益-経常費用=経常利益の直接計算。一般事業のOrdinaryIncomeと概念的に同一だが算出過程が異なる。",
    ),
    InsuranceConceptMapping(
        concept="ExtraordinaryIncomeINS",
        canonical_key="extraordinary_income",  # jgaap.py 実値確認済み
        label_ja="特別利益",
        label_en="Extraordinary income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=21,
        general_equivalent="extraordinary_income",  # jgaap.py 実値確認済み
    ),
    InsuranceConceptMapping(
        concept="ExtraordinaryLossINS",
        canonical_key="extraordinary_loss",  # jgaap.py 実値確認済み
        label_ja="特別損失",
        label_en="Extraordinary loss",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=22,
        general_equivalent="extraordinary_loss",  # jgaap.py 実値確認済み
    ),
    InsuranceConceptMapping(
        concept="IncomeBeforeIncomeTaxesINS",
        canonical_key="income_before_tax",  # jgaap.py 実値確認済み
        label_ja="税引前当期純利益",
        label_en="Income before income taxes",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=23,
        general_equivalent="income_before_tax",  # jgaap.py 実値確認済み
    ),
    InsuranceConceptMapping(
        concept="NetIncomeINS",
        canonical_key="net_income",
        label_ja="当期純利益",
        label_en="Net income",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        is_total=True,
        display_order=25,
        general_equivalent="net_income",  # 【C-1反映】jgaap.py の ProfitLoss → "net_income"。"profit" は存在しない
    ),
    # ... 残りは実装時に実タクソノミ XSD から確定
)
```

**注意**: 上記は代表的なマッピングの例示。実装時に `jppfs_cor_2025-11-01.xsd` の INS 概念 229 件を精査し、主要科目 30-40 件を選定する。概念名は XSD から正確に転記すること。

#### BS マッピング（15-25 件）

**INS-only ポリシー**: 本モジュールは INS サフィックス付き concept のみを管理する。TotalAssets, NetAssets 等の一般事業会社と共通の concept（INS サフィックスなし）は jgaap.py にフォールバックして解決する。normalize レイヤーが `insurance.lookup() → None → jgaap.lookup()` のフォールバックチェーンを実装する。

```python
_BS_MAPPINGS: tuple[InsuranceConceptMapping, ...] = (
    # ===== 資産 =====
    InsuranceConceptMapping(
        concept="SecuritiesAssetsINS",
        canonical_key="securities_ins",  # banking の securities_bnk と統一パターン
        label_ja="有価証券",
        label_en="Securities (insurance)",
        statement_type=StatementType.BALANCE_SHEET,
        period_type="instant",
        display_order=1,
    ),
    InsuranceConceptMapping(
        concept="PolicyLoansAssetsINS",
        canonical_key="policy_loans_ins",  # 【M-1反映】_ins サフィックス
        label_ja="保険約款貸付金",
        label_en="Policy loans",
        statement_type=StatementType.BALANCE_SHEET,
        period_type="instant",
        display_order=2,
    ),
    # ===== 負債 =====
    InsuranceConceptMapping(
        concept="ReserveForInsurancePolicyLiabilitiesLiabilitiesINS",
        canonical_key="policy_reserve_total_ins",  # 【M-1反映】_ins サフィックス
        label_ja="保険契約準備金",
        label_en="Reserve for insurance policy liabilities",
        statement_type=StatementType.BALANCE_SHEET,
        period_type="instant",
        is_total=True,
        display_order=10,
        # 保険業最大の負債項目。一般事業会社に対応科目なし
    ),
    InsuranceConceptMapping(
        concept="OutstandingClaimsLiabilitiesINS",
        canonical_key="outstanding_claims_ins",  # 【M-1反映】_ins サフィックス
        label_ja="支払備金",
        label_en="Outstanding claims",
        statement_type=StatementType.BALANCE_SHEET,
        period_type="instant",
        display_order=11,
    ),
    InsuranceConceptMapping(
        concept="PolicyReserveLiabilitiesINS",
        canonical_key="policy_reserve_ins",  # 【M-1反映】_ins サフィックス
        label_ja="責任準備金",
        label_en="Policy reserve",
        statement_type=StatementType.BALANCE_SHEET,
        period_type="instant",
        display_order=12,
    ),
    # ===== 共通科目（TotalAssets, NetAssets 等）は INS サフィックスなし =====
    # → jgaap.py にフォールバックで解決。本モジュールには含めない。
    # ... 残りの INS サフィックス付き科目は実装時に実タクソノミ XSD から確定
)
```

#### CF マッピング（0-10 件）

CF は一般事業会社と構造が概ね共通。保険業の CF に INS サフィックス付き concept が存在するかを実タクソノミで確認する。

**CF = 0 件のケースを許容**: 保険業の CF が全て一般事業と同一 concept（INS サフィックスなし）で構成される場合、`_CF_MAPPINGS` は空タプルとなる。この場合、CF の全科目は jgaap.py へのフォールバックで解決される。これは正しい結果であり、マイルストーン完了条件を満たす。

```python
_CF_MAPPINGS: tuple[InsuranceConceptMapping, ...] = (
    # CF は営業/投資/財務の 3 区分は一般事業と構造が共通。
    # 保険業固有の CF INS サフィックス付き科目が存在するかは
    # 実タクソノミで確認する。存在しない場合は空タプル（= 正常）。
    # ... 実装時に確定
)
```

### 3.3 レジストリとインデックス

```python
# モジュールレベルで構築
_ALL_MAPPINGS: tuple[InsuranceConceptMapping, ...] = (
    *_PL_MAPPINGS, *_BS_MAPPINGS, *_CF_MAPPINGS
)

# concept → InsuranceConceptMapping
_CONCEPT_INDEX: dict[str, InsuranceConceptMapping] = {
    m.concept: m for m in _ALL_MAPPINGS
}

# canonical_key → InsuranceConceptMapping
_CANONICAL_INDEX: dict[str, InsuranceConceptMapping] = {
    m.canonical_key: m for m in _ALL_MAPPINGS
}

# StatementType → tuple[InsuranceConceptMapping, ...]
_STATEMENT_INDEX: dict[StatementType, tuple[InsuranceConceptMapping, ...]] = {
    st: tuple(m for m in _ALL_MAPPINGS if m.statement_type == st)
    for st in StatementType
}
```

### 3.4 バリデーション

```python
def _validate_registry() -> None:
    """モジュール読み込み時にレジストリの整合性を検証する。

    concept 名と canonical_key の意味的乖離は保険業タクソノミの命名慣習による
    ものであり、バリデーションでは検出しない（セクション 7.7 参照）。

    検証項目:
    - concept の重複がないこと
    - canonical_key の重複がないこと
    - display_order が statement_type 内で一意であること
    - display_order > 0 であること（0 はデフォルト値であり、設定忘れを示す）【M-2 第4回反映】
    - 同一 statement_type 内で display_order が昇順であること（タプル定義順との整合性）【M-2 第4回反映】
    - 全 concept が INS サフィックスを持つこと（sanity check）
    - period_type が "instant" or "duration" であること

    Raises:
        ValueError: 整合性違反がある場合。
            assert ではなく ValueError を使用する。
            python -O（最適化モード）でも常に実行されるため。
            jgaap.py と同じ方式。
    """

_validate_registry()  # モジュール読み込み時に実行
```

### 3.5 公開 API

```python
def lookup(concept: str) -> InsuranceConceptMapping | None:
    """保険業 concept ローカル名からマッピング情報を取得する。

    Args:
        concept: jppfs_cor の保険業 concept ローカル名
            （例: ``"OperatingIncomeINS"``）。

    Returns:
        InsuranceConceptMapping。登録されていない concept の場合は None。
    """

def canonical_key(concept: str) -> str | None:
    """保険業 concept ローカル名を正規化キーにマッピングする。

    Args:
        concept: jppfs_cor の保険業 concept ローカル名。

    Returns:
        正規化キー文字列。登録されていない concept の場合は None。
    """

def reverse_lookup(key: str) -> InsuranceConceptMapping | None:
    """正規化キーから保険業の InsuranceConceptMapping を取得する（逆引き）。

    Args:
        key: 正規化キー（例: ``"insurance_premiums"``）。

    Returns:
        InsuranceConceptMapping。該当する保険業 concept がない場合は None。
    """

def mappings_for_statement(
    statement_type: StatementType,
) -> tuple[InsuranceConceptMapping, ...]:
    """指定した財務諸表タイプの保険業マッピングを返す。

    display_order 順でソート済み。

    Args:
        statement_type: PL / BS / CF。

    Returns:
        InsuranceConceptMapping のタプル（display_order 昇順）。
    """

def all_mappings() -> tuple[InsuranceConceptMapping, ...]:
    """全ての保険業マッピングを返す（PL → BS → CF 順）。"""

def all_canonical_keys() -> frozenset[str]:
    """保険業で定義されている全正規化キーの集合を返す。"""

def insurance_specific_concepts() -> tuple[InsuranceConceptMapping, ...]:
    """一般事業会社に対応 concept がない保険業固有の科目を返す。

    Returns:
        general_equivalent が None の InsuranceConceptMapping のタプル。
        ソート順は ``_ALL_MAPPINGS`` の定義順（PL → BS → CF）を維持する。
        【L-1 第4回反映】
    """

def is_insurance_industry(industry_code: str) -> bool:
    """業種コードが保険業に該当するかを判定する。

    内部で ``INSURANCE_INDUSTRY_CODES`` 定数を参照する（M-1 第3回反映）。

    Args:
        industry_code: 業種コード（``"in1"``, ``"in2"`` 等）。

    Returns:
        保険業コード（``in1`` or ``in2``）であれば True。
    """

def insurance_to_general_map() -> dict[str, str]:
    """保険業 canonical_key → 一般事業会社 canonical_key の辞書を返す。

    general_equivalent が設定されている科目のみを含む。
    banking.py の ``banking_to_general_map()`` と対称的な API。

    Returns:
        保険業 canonical_key をキー、一般事業会社 canonical_key を値とする辞書。
    """

def get_profile() -> InsuranceProfile:
    """保険業のプロファイルを返す。

    Returns:
        InsuranceProfile。
    """
```

### 3.6 InsuranceProfile

```python
@dataclass(frozen=True, slots=True)
class InsuranceProfile:
    """保険業のプロファイル（概要情報）。

    Wave 3 L1 の normalize が全業種のプロファイルを
    並列に保持し、ディスパッチに使用する。

    banking.py の BankingProfile と共通フィールドを揃える。
    ``has_underwriting`` / ``has_investment_income`` は常に True であり
    情報量ゼロのため削除。保険業の判定は ``sector_id == "insurance"`` で十分。

    Attributes:
        sector_id: 業種セクターの識別子。``"insurance"`` 固定。
        name_ja: 日本語表示名。
        name_en: 英語表示名。
        industry_codes: 対応する業種コードの集合。
        canonical_key_count: 定義されている正規化キーの総数。
    """
    sector_id: str
    name_ja: str       # 【H-2反映】display_name_ja → name_ja に改名。banking の name_ja と統一
    name_en: str       # 【H-2反映】display_name_en → name_en に改名。banking の name_en と統一
    industry_codes: frozenset[str]
    canonical_key_count: int
```

**`_PROFILE` キャッシュインスタンスの構築パターン**（【H-2 第4回反映】）:

```python
# モジュールレベルで構築。初期化順序: _ALL_MAPPINGS → _CANONICAL_INDEX → _PROFILE
_PROFILE = InsuranceProfile(
    sector_id="insurance",
    name_ja="保険業",
    name_en="Insurance",
    industry_codes=INSURANCE_INDUSTRY_CODES,
    canonical_key_count=len(_CANONICAL_INDEX),
)

def get_profile() -> InsuranceProfile:
    """保険業のプロファイルを返す。"""
    return _PROFILE
```

`_CANONICAL_INDEX` はモジュールレベルで `_ALL_MAPPINGS` から構築されるため、依存順序は `_ALL_MAPPINGS` → `_CANONICAL_INDEX` → `_PROFILE` で問題ない。jgaap.py の `_PROFILE = JGAAPProfile(...)` パターンと同一。

**`get_profile()` が引数なしである理由**（H-1 設計判断）:

- insurance: `in1`（生命保険）と `in2`（損害保険）はプロファイルレベルの差異がない（語彙層で INS を共有し、概念セット・canonical_key マッピングも共通）。したがって引数不要で 1 つの InsuranceProfile を返す。
- banking: `bk1` と `bk2` は `has_consolidated_template` と `cf_method` が異なるため、業種コード引数が必要。
- normalize（L1）側の統一的ハンドリング（引数あり/なしの差異吸収）は L1 の責務として明確化する。

**`mapping_note` フィールドについて**（H-4 第3回反映）:

- 【変更】insurance.py にも `mapping_note: str = ""` を追加。banking.py と対称にする。
- 重要なマッピング（`OrdinaryProfitINS`, `CommissionsAndCollectionFeesOEINS`, `OperatingIncomeINS` 等）には根拠を記載する。
- normalize は `mapping_note` を参照しない設計のため、必須ではないが、保守者向けのドキュメンテーションとして有用。

---

## 4. canonical_key 設計方針

### 4.1 一般事業会社と共通の canonical_key（jgaap.py 実値で検証済み）

保険業固有だが、概念として一般事業会社の科目と等価なものは**同一の canonical_key**を使用し、`general_equivalent` に対応する一般事業会社の canonical_key を格納する。

**全 general_equivalent 値は jgaap.py の `all_canonical_keys()` 実値と突合済み**（C-3 対応）:

| 保険業 concept | canonical_key | general_equivalent | jgaap.py の対応 concept | 備考 |
|---------------|--------------|-------------------|----------------------|------|
| `OrdinaryProfitINS` | `ordinary_income` | `"ordinary_income"` | `OrdinaryIncome` → `"ordinary_income"` | 経常利益。同一概念 |
| `ExtraordinaryIncomeINS` | `extraordinary_income` | `"extraordinary_income"` | `ExtraordinaryIncome` → `"extraordinary_income"` | 特別利益 |
| `ExtraordinaryLossINS` | `extraordinary_loss` | `"extraordinary_loss"` | `ExtraordinaryLoss` → `"extraordinary_loss"` | 特別損失 |
| `IncomeBeforeIncomeTaxesINS` | `income_before_tax` | `"income_before_tax"` | `IncomeBeforeIncomeTaxes` → `"income_before_tax"` | 税引前利益 |
| `NetIncomeINS` | `net_income` | `"net_income"` | `ProfitLoss` → `"net_income"` | 当期純利益 |
| `CommissionsAndCollectionFeesOEINS` | `business_expenses_ins` | `"sga_expenses"` | `SellingGeneralAndAdministrativeExpenses` → `"sga_expenses"` | 事業費 ≈ 販管費 |
| `OperatingIncomeINS` | `ordinary_revenue_ins` | `"revenue"` | `NetSales` → `"revenue"` | 経常収益 ≈ 売上高 |

注: `general_equivalent` が `canonical_key` と同一になるケースが多いが、冗長ではない。normalize レイヤーで「この保険概念は一般事業の何に相当するか？」の問いに統一的に答えるために必要。banking.py と同じパターン。

### 4.2 保険業固有の canonical_key（新規定義）

一般事業会社に対応概念がない科目には保険業固有の canonical_key を新設する。**全固有科目に `_ins` サフィックスを付与する**（M-1: banking の `_bnk` パターンと統一）:

| 保険業 concept | canonical_key | 理由 |
|---------------|--------------|------|
| `OperatingIncomeINS` | `ordinary_revenue_ins` | 保険業の経常収益。一般事業の売上高とは構造が異なる。banking の `ordinary_revenue_bnk` と統一 |
| `InsurancePremiumsAndOtherOIINS` | `underwriting_income_ins` | 保険引受収益。保険業固有 |
| `InsurancePremiumsOIINS` | `insurance_premiums_ins` | 保険料等収入。保険業固有 |
| `InvestmentIncomeOIINS` | `investment_income_ins` | 資産運用収益。保険業固有 |
| `InsuranceClaimsAndOtherOEINS` | `underwriting_expenses_ins` | 保険引受費用。保険業固有 |
| `InsuranceClaimsOEINS` | `insurance_claims_ins` | 保険金等支払金。保険業固有 |
| `ProvisionOfPolicyReserveAndOtherOEINS` | `provision_policy_reserve_ins` | 責任準備金等繰入額。保険業固有 |
| `InvestmentExpensesOEINS` | `investment_expenses_ins` | 資産運用費用。保険業固有 |
| `CommissionsAndCollectionFeesOEINS` | `business_expenses_ins` | 事業費。保険業固有（general_equivalent あり） |
| `ReserveForInsurancePolicyLiabilitiesLiabilitiesINS` | `policy_reserve_total_ins` | 保険契約準備金。保険業最大の負債 |
| `PolicyLoansAssetsINS` | `policy_loans_ins` | 保険約款貸付金。保険業固有 |

### 4.3 命名規則（M-1 反映: banking と統一）

- **一般事業会社と共通の科目**: jgaap.py で定義された canonical_key をそのまま使用（`_ins` サフィックスなし）
  - 例: `OrdinaryProfitINS` → `ordinary_income`（jgaap.py と同一キー）
- **保険業固有の科目**: 全て `_ins` サフィックスを付与（banking の `_bnk` パターンと統一）
  - 例: `underwriting_income_ins`, `insurance_premiums_ins`, `policy_reserve_total_ins`
- **ルール**: 固有科目は必ずサフィックス。共通科目はサフィックスなし。判定基準が明確で例外がない

**banking と統一するメリット**:
1. normalize で `key.endswith("_ins")` / `key.endswith("_bnk")` のような業種フィルタリングが可能
2. 将来の証券業 (`_sec`)、建設業 (`_con`) 等との統一パターンが自然に拡張可能
3. ルールが明確で、新規科目追加時に迷わない

---

## 5. テスト計画

### 5.1 テストケース

```python
class TestInsuranceConceptMapping:
    """InsuranceConceptMapping dataclass のテスト。"""

    def test_frozen_dataclass(self):
        """InsuranceConceptMapping が frozen であること。"""

    def test_default_values(self):
        """デフォルト値（industry_codes={"in1","in2"}, is_total=False 等）が正しいこと。"""


class TestLookup:
    """lookup() / canonical_key() / reverse_lookup() のテスト。"""

    def test_lookup_known_concept(self):
        """既知の保険業 concept が lookup できること。"""

    def test_lookup_unknown_returns_none(self):
        """未登録の concept で None が返ること。"""

    def test_lookup_empty_string_returns_none(self):
        """空文字で None が返ること。"""

    def test_canonical_key_known(self):
        """既知 concept の canonical_key が返ること。"""

    def test_canonical_key_unknown_returns_none(self):
        """未登録 concept で None が返ること。"""

    def test_canonical_key_with_non_ins_concept(self):
        """INS サフィックスなしの concept 名で None が返ること。"""

    def test_reverse_lookup_known_key(self):
        """既知 canonical_key から reverse_lookup できること。"""

    def test_reverse_lookup_unknown_returns_none(self):
        """未登録 canonical_key で None が返ること。"""


class TestMappingsForStatement:
    """mappings_for_statement() のテスト。"""

    def test_pl_mappings_not_empty(self):
        """PL マッピングが空でないこと。"""

    def test_bs_mappings_not_empty(self):
        """BS マッピングが空でないこと。"""

    def test_cf_mappings_may_be_empty(self):
        """CF マッピングが空タプルでも正常であること。
        保険業 CF が全て一般事業と同一 concept の場合、空が正しい結果。
        """

    def test_display_order_sorted(self):
        """各 statement_type 内で display_order 昇順であること。"""


class TestAllMappings:
    """all_mappings() / all_canonical_keys() のテスト。"""

    def test_all_mappings_count(self):
        """全マッピング数が期待値に一致すること。"""

    def test_all_canonical_keys_unique(self):
        """全 canonical_key が一意であること。"""

    def test_all_concepts_unique(self):
        """全 concept が一意であること。"""


class TestInsuranceSpecific:
    """insurance_specific_concepts() のテスト。"""

    def test_insurance_specific_has_no_general_equivalent(self):
        """保険固有科目の general_equivalent が全て None であること。"""

    def test_underwriting_is_insurance_specific(self):
        """保険引受収益が保険固有科目として返ること。"""


class TestIsInsuranceIndustry:
    """is_insurance_industry() のテスト。"""

    def test_in1_is_insurance(self):
        """in1（生命保険）が保険業と判定されること。"""

    def test_in2_is_insurance(self):
        """in2（損害保険）が保険業と判定されること。"""

    def test_cai_is_not_insurance(self):
        """cai（一般商工業）が保険業でないと判定されること。"""

    def test_bk1_is_not_insurance(self):
        """bk1（銀行業）が保険業でないと判定されること。"""

    def test_empty_string_is_not_insurance(self):
        """空文字で False が返ること。"""


class TestInsuranceToGeneralMap:
    """insurance_to_general_map() のテスト。"""

    def test_ordinary_income_maps_to_ordinary_income(self):
        """ordinary_income → ordinary_income のマッピングが存在すること。"""

    def test_insurance_specific_not_in_map(self):
        """保険固有科目（general_equivalent=None）が辞書に含まれないこと。"""

    def test_all_values_exist_in_jgaap(self):
        """辞書の全 value が jgaap.all_canonical_keys() に含まれること。
        注: jgaap.py のマッピング変更時はこのテストも影響を受ける（意図的）。
        """


class TestInsuranceProfile:
    """get_profile() のテスト。"""

    def test_sector_id(self):
        """sector_id が "insurance" であること。"""

    def test_industry_codes(self):
        """industry_codes が {"in1", "in2"} であること。"""

    def test_canonical_key_count_matches(self):
        """canonical_key_count が all_canonical_keys() の件数と一致すること。"""


class TestCanonicalKeyConsistency:
    """canonical_key の一般事業会社との整合性テスト。"""

    def test_shared_keys_match_jgaap(self):
        """一般事業会社と共通の canonical_key が jgaap.py に存在すること。

        クロスモジュール整合性テスト。jgaap.py のマッピング変更時にも
        意図的に影響を受ける。CI で失敗した場合は insurance.py と
        jgaap.py の両方を確認すること。（M-3 第3回反映）

        general_equivalent が None でないマッピングについて、
        general_equivalent の値が jgaap.all_canonical_keys() に含まれることを検証。
        """

    def test_insurance_specific_keys_not_in_jgaap(self):
        """保険固有の canonical_key が jgaap.py に存在しないこと。

        【M-3 第4回反映】判定基準: ``canonical_key`` が ``_ins`` サフィックスで
        終わるマッピングのみを対象とする。これらは保険業固有の新規キーであり、
        jgaap.py に同名のキーが存在してはならない。
        ``_ins`` サフィックスなしの共通 canonical_key（``ordinary_income`` 等）は
        jgaap.py にも存在するのが正しいため、対象外。
        """


class TestINSSuffix:
    """INS サフィックスの整合性テスト。"""

    def test_all_concepts_end_with_ins(self):
        """全登録 concept が INS サフィックスを持つこと。

        保険業モジュールが管理する concept は全て jppfs_cor の
        INS サフィックス付き concept であるべき。
        （INS-only ポリシー: 共通科目は jgaap.py にフォールバック）
        """


class TestRegistryValidation:
    """レジストリのバリデーションテスト。"""

    def test_no_duplicate_concepts(self):
        """concept の重複がないこと。"""

    def test_no_duplicate_canonical_keys(self):
        """canonical_key の重複がないこと。"""
```

### 5.2 推奨: 実データスモークテスト

```python
@pytest.mark.skipif(
    not os.environ.get("EDINET_TAXONOMY_ROOT"),
    reason="EDINET_TAXONOMY_ROOT が設定されていません"
)
class TestRealTaxonomy:
    """実タクソノミに対するスモークテスト（CI では skip）。"""

    def test_all_concepts_exist_in_xsd(self):
        """全登録 concept が jppfs_cor XSD に定義されていること。

        jppfs_cor_2025-11-01.xsd を lxml でパースし、
        全登録 concept のローカル名が xs:element として存在することを確認。
        """

    def test_concept_set_coverage(self):
        """concept_sets の in1 PL ConceptSet に対するカバレッジ。

        taxonomy/concept_sets で導出された in1 の PL concept セットのうち、
        本モジュールに登録されている割合を計測。
        主要科目（合計行）のカバレッジが 80% 以上であることを確認。
        """
```

### 5.3 テスト方針

- **Detroit 派**: モック不使用。静的データ定義のテストなので、データの正確性と API の振る舞いを直接テスト
- **リファクタリング耐性**: 公開 API のみテスト。`_PL_MAPPINGS` 等の内部タプルは直接参照しない
- **フィクスチャ不要**: 本モジュールは静的データ定義のため、XML フィクスチャは不要。jgaap.py への import のみ

---

## 6. 実装手順

### Step 1: 実タクソノミの精査

1. `jppfs_cor_2025-11-01.xsd` から INS サフィックス付き concept を全件抽出（229 件）
2. `in1` の PL プレゼンテーションリンクベース（`jppfs_in1_ac_2025-11-01_pre_pl.xml`）で PL の科目階層を確認
3. `in1` の BS プレゼンテーションリンクベース（`jppfs_in1_ac_2025-11-01_pre_bs.xml`）で BS の科目階層を確認
4. `in1` と `in2` のプレゼンテーションリンクベースの差異を確認（共通性の検証）
5. CF リンクベースの有無と内容を確認
6. 【H-1 第3回反映】`ProfitLossAttributableToOwnersOfParentINS` / `ProfitLossAttributableToNonControllingInterestsINS` の存在確認。存在すれば `_PL_MAPPINGS` に追加（`general_equivalent="net_income_parent"` / `"net_income_minority"`）
7. 【H-2 第3回反映】INS サフィックス付き BS 合計科目（`TotalAssetsINS`, `TotalLiabilitiesINS`, `NetAssetsINS`）の有無確認。存在する場合は `_BS_MAPPINGS` に追加し `general_equivalent="total_assets"` 等を設定
8. 【H-5 第3回反映】「保険引受利益」に相当する INS サフィックス付き concept の存在確認。存在すれば `_PL_MAPPINGS` に追加。存在しなければ「計算で求める科目であり、タクソノミに独立 concept がない」とコメントに記載
9. 【M-2 第3回反映】損保（`in2`）固有の科目候補を確認:
   - `NetPremiumsWrittenOIINS`（正味収入保険料）— 損保の代表的収益指標。`in2` 固有か共通か？
   - `NetClaimsPaidOEINS`（正味支払保険金）— 損保の代表的費用指標
   - 損保固有の BS 科目（例: 再保険関連の資産/負債）
   - `in1` 固有の科目（例: 生保特有の「個人年金保険」関連の収益科目）

**成果物**: 主要科目リスト（PL 20-40 件、BS 15-25 件、CF 0-10 件）の確定。INS サフィックス付き concept のみを対象とする。上記確認項目 6-9 の結果を含む。Step 1 の成果物はコード内のマッピングタプルそのものとして直接反映する。調査過程のメモは不要（実装が真実のソース）。【L-3 第4回反映】

### Step 2: データモデル定義

1. `InsuranceConceptMapping` frozen dataclass を定義（`industry_codes: frozenset[str]` パターン）
2. `InsuranceProfile` frozen dataclass を定義（共通フィールドのみ、定数フラグなし）

### Step 3: マッピングデータ入力

1. Step 1 で確定した科目リストに基づき `_PL_MAPPINGS` を定義
2. `_BS_MAPPINGS` を定義
3. `_CF_MAPPINGS` を定義
4. `_ALL_MAPPINGS` を結合
5. `_CONCEPT_INDEX`, `_CANONICAL_INDEX`, `_STATEMENT_INDEX` を構築
6. `_validate_registry()` を実装

### Step 4: 公開 API 実装

1. `lookup()`, `canonical_key()`, `reverse_lookup()` を実装
2. `mappings_for_statement()`, `all_mappings()`, `all_canonical_keys()` を実装
3. `insurance_specific_concepts()` を実装
4. `is_insurance_industry()` を実装
5. `insurance_to_general_map()` を実装（canonical_key → canonical_key の辞書）
6. `get_profile()` を実装

### Step 5: テスト実装・実行

1. テストファイルを作成
2. `uv run pytest tests/test_xbrl/test_sector_insurance.py -v` で全テスト PASS
3. `uv run pytest` で既存テスト含む全テスト PASS
4. `uv run ruff check src/edinet/xbrl/sector/insurance.py tests/test_xbrl/test_sector_insurance.py` でリント PASS

### Step 6: 実データスモークテスト（オプション）

1. `EDINET_TAXONOMY_ROOT` 環境変数を設定
2. 実タクソノミに対するスモークテストを実行
3. カバレッジと正確性を確認

---

## 7. 注意点・設計判断

### 7.1 in1 と in2 の差異

生命保険（`in1`）と損害保険（`in2`）は語彙層では同一の `INS` サフィックス concept を共有するが、関係層（プレゼンテーションリンク）の構造が異なる可能性がある。

**方針**:
- `InsuranceConceptMapping` の `industry_codes: frozenset[str]` フィールドで生保固有/損保固有/共通を区別する
  - 共通: `frozenset({"in1", "in2"})` （デフォルト）
  - 生保固有: `frozenset({"in1"})`
  - 損保固有: `frozenset({"in2"})`
- banking.py の同名フィールドと同じパターン（`InsuranceSubType` enum は不採用 — YAGNI）
- 初期実装では大多数の concept を共通（デフォルト値）として扱い、明確に差異がある場合のみサブセットを設定
- 差異の網羅的調査は将来の拡張に委ねる

### 7.2 一般事業会社 concept との二重定義の回避

保険業の PL 下位（経常利益以降: 特別利益、特別損失、税引前利益、当期純利益）は一般事業会社と概念的に同一だが、concept 名が異なる（例: `ExtraordinaryIncomeINS` vs `ExtraordinaryIncome`）。

**方針**:
- 保険業 concept は全て `insurance.py` で管理する（`jgaap.py` には含めない）
- `general_equivalent` フィールドに一般事業会社側の **canonical_key** を格納する（concept 名ではない）
  - banking.py と同じセマンティクス（L2 フィードバック M-2 の統一方針）
  - normalize レイヤーが業種横断で統一アクセスする際のキーは canonical_key であるため
- `canonical_key` を共有することで、normalize レイヤーでの横断アクセスを実現

### 7.3 concept 数の選定基準と INS-only ポリシー

**INS-only ポリシー**: 本モジュールは INS サフィックス付き concept のみを管理する。INS サフィックスなしの共通科目（TotalAssets, NetAssets, ProfitLoss 等）は jgaap.py にフォールバックして解決する。normalize レイヤーが `insurance.lookup() → None → jgaap.lookup()` のフォールバックチェーンを実装する。

INS サフィックス付き 229 件のうち、本モジュールで canonical_key を付与するのは主要科目 35-65 件程度。

**選定基準**:
1. PL/BS/CF の合計行・小計行は必ず含める
2. 直下の内訳（1 階層目）は含める
3. 詳細内訳（2 階層目以降）は重要度が高いもののみ
4. 一般事業会社との対応付けが可能な科目は優先的に含める

**選定しないもの**:
- INS サフィックスなしの共通科目（jgaap.py にフォールバック）
- 計算リンクで親科目に遡及可能な詳細科目
- TextBlock（HTML テキスト）
- Abstract（見出し行）

### 7.4 銀行業モジュール（Wave 3 L2）との整合性

銀行業モジュール（`sector/banking.py`）も並列で開発される。両者は独立したモジュールだが、設計パターンを統一する必要がある。

**統一済みのフィールド名・セマンティクス**（L2/L3 フィードバック反映）:

| フィールド | insurance.py | banking.py | セマンティクス |
|-----------|-------------|-----------|-------------|
| 業種コード | `industry_codes: frozenset[str]` | `industry_codes: frozenset[str]` | 共通 |
| 一般事業対応 | `general_equivalent: str \| None` | `general_equivalent: str \| None` | canonical_key を格納 |
| period_type | `PeriodType` (= `Literal[...]`) | `PeriodType` (= `Literal[...]`) | 共通 |
| 一般事業マップ | `insurance_to_general_map()` | `banking_to_general_map()` | `*_to_general_map()` パターン |
| Profile 名前 | `name_ja` / `name_en` | `name_ja` / `name_en` | 共通（H-2 反映） |
| Profile 識別子 | `sector_id: str` ("insurance") | `industry_code: str` ("bk1"/"bk2") | insurance は複数コードを束ねるため sector_id |
| 固有科目サフィックス | `_ins` | `_bnk` | 全固有科目に付与（M-1 反映） |
| `mapping_note` | `str = ""`（H-4 第3回反映で追加） | `str = ""` | 「近いが同一ではない」マッピングの根拠記載用。banking と対称 |
| `display_order` | ギャップ方式 | 連番方式 → ギャップ方式に移行推奨（C-2 第3回反映） | セクターモジュール標準: ギャップ方式。業種固有科目の将来追加に対応 |
| `is_total` | `bool = False` | `bool = False` | 共通。合計行・小計行に True（【L-2 第4回反映】） |
| バリデーション | `ValueError` | `ValueError` | assert 不使用 |

**【H-1 第4回反映】`is_jgaap_specific` 相当フラグについて**: insurance.py は `is_jgaap_specific` に相当するフィールドを持たない。全マッピングが INS サフィックス付きであり、常に `True` 相当のため情報量ゼロで不要。normalize が `is_sector_specific` 的なフラグを duck-typing で参照する場合は、L1 側で `True` 定数を注入する。

**【H-4 第4回反映】Profile の識別フィールドの非対称性について**: insurance は `sector_id: str = "insurance"` で in1/in2 を束ねる構造。banking は `industry_code: str = "bk1"/"bk2"` で CF method が異なるため個別プロファイル。この命名・型の非対称は設計意図であり、統一的アクセスのアダプテーション（`profile.sector_id` vs `profile.industry_code`）は L1 normalize の責務。

**方針**: `standards/jgaap.py` のパターンを両モジュールで忠実に踏襲する。データ型の共通化（基底クラスの抽出等）は Wave 3 完了後のリファクタリングで検討。初期実装では各モジュールが独立した dataclass を持つ。

### 7.5 Wave 3 L1 (normalize + statements.py 統合) との接続

Wave 3 L1 が `statements.py` を書き換える際、保険業企業の財務諸表生成に本モジュールが使用される。

**接続パス**:
```
1. detect() で会計基準を判別 → J-GAAP
2. 業種コードを判定 → in1 or in2
3. concept_sets で保険業の PL/BS/CF 概念セットを取得
4. insurance.py の _MAPPINGS で canonical_key / label を付与
5. FinancialStatement を構築して返却
```

本モジュールが提供するもの:
- `is_insurance_industry(industry_code)` → 業種コードの判定
- `lookup(concept)` → 概念情報の取得
- `mappings_for_statement(StatementType.INCOME_STATEMENT)` → PL 科目リスト
- `insurance_to_general_map()` → 一般事業会社との対応表（canonical_key ベース）

### 7.6 業種コードの判定方法

保険業の判定は、Filing の提出者別 XSD の import チェーンから業種コードを推定する必要があるが、これは本モジュールの責務ではない（normalize / statements.py 側の責務）。

本モジュールは `is_insurance_industry(code: str) -> bool` という判定関数のみを提供し、業種コードの取得方法は呼び出し側に委ねる。

### 7.7 保険業タクソノミの命名上の注意（【M-1 第4回反映】）

保険業タクソノミでは `Operating` が「経常」（ordinary）の意味で使用される。これは一般事業の `OperatingIncome`（営業利益）とは異なる概念であるにもかかわらず、同一の英語接頭辞が使われている。本モジュールの `canonical_key` はタクソノミの concept 名ではなく**経済的意味**に基づいて命名している（例: `OperatingIncomeINS` → `ordinary_revenue_ins`）ため、concept 名との乖離が生じる。**保守時に concept 名だけを見て canonical_key を推測しないこと。**

### 7.8 `is_total` の付与基準（【M-4 第4回反映】）

プレゼンテーションリンクベースで合計行（= 子要素の集約行）として表示される concept に `is_total=True` を設定する。保険業では以下が該当:
- `OperatingIncomeINS`（経常収益）: 保険引受収益+資産運用収益+その他の合計
- `OperatingExpensesINS`（経常費用）: 保険引受費用+責任準備金+資産運用費用+事業費+その他の合計
- `OrdinaryProfitINS`（経常利益）: 経常収益-経常費用の差引合計
- `IncomeBeforeIncomeTaxesINS`（税引前当期純利益）: 経常利益+特別利益-特別損失の合計
- `NetIncomeINS`（当期純利益）: 最終利益の合計
- BS の合計行（`ReserveForInsurancePolicyLiabilitiesLiabilitiesINS` 等）

一般事業会社の `NetSales`（売上高）には `is_total=False` が設定されているが、これは売上高が合計行ではなく単独の収益科目として扱われるため。保険業の `OperatingIncomeINS`（経常収益）は構造的に合計行であるため `True`。

---

## 8. マイルストーン完了条件

1. `InsuranceConceptMapping` が `frozen=True, slots=True` の dataclass として定義されている
2. `statement_type: StatementType | None` 型で jgaap.py / banking.py と統一されている（C-1 第3回反映）
3. `mapping_note: str = ""` フィールドが banking.py と対称に定義されている（H-4 第3回反映）
4. `industry_codes: frozenset[str]` フィールドで生保/損保/共通を区別できる（`InsuranceSubType` enum は不使用）
5. PL マッピングが 20 件以上定義されている（経常収益/経常費用/利益の主要科目）
6. BS マッピングが 15 件以上定義されている（保険固有の資産・負債。INS サフィックス付きのみ）
7. CF マッピングが 0 件以上定義されている（INS サフィックス付き CF 科目が存在しない場合は 0 件で正常）
8. 全 concept が INS サフィックスを持つ（INS-only ポリシー。共通科目は jgaap.py にフォールバック）
9. canonical_key が全て一意
10. 一般事業会社と共通の canonical_key（ordinary_income, net_income 等）が jgaap.py の canonical_key と一致する（jgaap.py 実値で検証済み）
11. `general_equivalent` が正しく設定されている（対応ありの場合は一般事業会社の **canonical_key**、なしの場合は None）
12. `lookup()`, `canonical_key()`, `reverse_lookup()` が正しく動作する
13. `mappings_for_statement()` が display_order 昇順で返す
14. `insurance_specific_concepts()` が general_equivalent=None の科目を返す
15. `is_insurance_industry()` が in1/in2 を True、他を False と判定する。`INSURANCE_INDUSTRY_CODES` 定数を内部で参照する（M-1 第3回反映）
16. `insurance_to_general_map()` が general_equivalent 設定済み科目のみの辞書を返す（canonical_key → canonical_key）
17. `get_profile()` が InsuranceProfile を返す（`has_underwriting` / `has_investment_income` フィールドなし）
18. `__all__` が明示的に定義されている（H-3 第3回反映）
19. `_validate_registry()` がモジュール読み込み時に ValueError なく完了する（assert 不使用）
20. Step 1 の実タクソノミ精査で H-1/H-2/H-5/M-2 の確認項目を全て実施済み
21. テスト: 28+ テストケースが PASS（edge case テスト含む）
22. リント: ruff clean
23. 既存テスト: 全 PASS（破壊なし）

---

## 9. ファイル一覧

| 操作 | パス |
|------|------|
| 新規 | `src/edinet/xbrl/sector/insurance.py` |
| 新規 | `tests/test_xbrl/test_sector_insurance.py` |

全て新規ファイル。既存ファイルの変更なし。

---

## 10. Wave 3 L1 への接続点

**注**: 以下は L1 での使用イメージの例示であり、L1 の実装詳細は L1 計画に委ねる（L-1 第3回反映）。

本モジュールは Wave 3 L1（`standards/normalize + statements.py 統合`）から以下のように使用される:

```python
# Wave 3 L1 の normalize.py 内:
from edinet.financial.sector.insurance import (
    is_insurance_industry,
    lookup as insurance_lookup,
    mappings_for_statement as insurance_mappings,
    get_profile as insurance_profile,
)
from edinet.financial.standards import jgaap

def _dispatch_sector(industry_code: str, statement_type: StatementType):
    """業種コードに基づいて適切なセクターモジュールにディスパッチする。"""
    if is_insurance_industry(industry_code):
        return insurance_mappings(statement_type)
    # elif is_banking_industry(industry_code):  # Wave 3 L2
    #     return banking_mappings(statement_type)
    else:
        return jgaap.mappings_for_statement(statement_type)  # 一般事業会社

# Wave 3 L1 の statements.py 内:
# 保険業企業の場合:
concept_set = registry.get(StatementType.INCOME_STATEMENT, industry_code="in1")
# concept セットの各 concept に対して:
mapping = insurance_lookup(concept_name)
if mapping is None:
    # INS-only ポリシー: INS サフィックスなしの共通科目は jgaap にフォールバック
    mapping = jgaap.lookup(concept_name)
if mapping:
    key = mapping.canonical_key
    label_ja = mapping.label_ja
    # → LineItem に付与
```

### Milestone A/B/C との関係

- **Milestone A（3 会計基準対応）**: Wave 3 L1 で達成。本 Lane は直接関与しない
- **Milestone B（保険・銀行以外の全銘柄）**: Wave 3 L1 + concept_sets で達成。本 Lane は直接関与しない
- **Milestone C（全銘柄対応）**: **本 Lane（L3: 保険）+ L2（銀行）の完成で達成**。保険業と銀行業の canonical_key マッピングが完成し、normalize からのディスパッチが実装されることで、全業種の財務諸表が出力可能になる

---

## 11. フィードバック反映サマリー

### 第 2 回フィードバック反映

| フィードバック | 分類 | 対処 |
|--------------|------|------|
| C-1: `NetIncomeINS` の general_equivalent | CRITICAL | `"profit"` → `"net_income"` に修正。jgaap.py 実値確認済み |
| C-2: `OrdinaryProfitINS` の canonical_key | CRITICAL | `"ordinary_profit"` → `"ordinary_income"` に修正。jgaap.py の OrdinaryIncome と同一 |
| C-3: 全 general_equivalent の jgaap 突合 | CRITICAL | 全 7 件を jgaap.py の `all_canonical_keys()` 実値と突合し、セクション 4.1 に検証結果テーブルを追加 |
| H-1: get_profile() の引数設計差異 | HIGH | セクション 3.6 に設計判断の理由を明記 |
| H-2: Profile フィールド名統一 | HIGH | `display_name_ja` → `name_ja`, `display_name_en` → `name_en` に改名 |
| H-3: mapping_note の L2 との非対称 | HIGH | セクション 3.6 に注記追加。統合フェーズで解消予定 |
| H-4: ordinary_income_ins → ordinary_revenue_ins | HIGH | 修正。banking の `ordinary_revenue_bnk` と統一。「経常収益」は revenue |
| M-1: _ins サフィックスを全固有科目に付与 | MEDIUM | Option A 採用。全固有科目に `_ins` を付与。banking の `_bnk` と統一 |
| M-2: operating_expenses_ins → business_expenses_ins | MEDIUM | 修正。「事業費」は保険業固有概念 |
| L-1: コメント重複除去 | LOW | 修正 |
| L-2: OperatingIncomeINS の意味混同防止コメント | LOW | 追加 |

### 第 3 回フィードバック反映

| フィードバック | 分類 | 対処 |
|--------------|------|------|
| C-1: `statement_type` の型統一 | CRITICAL | `StatementType` → `StatementType \| None` に変更。jgaap.py / banking.py と型統一。セクション 3.1 修正 |
| C-2: `display_order` ギャップ方式の標準化 | CRITICAL | Option A 採用。ギャップ方式をセクターモジュール標準とする。banking への移行提案を注記追加。セクション 3.2, 7.4 修正 |
| C-3: `OrdinaryProfitINS` の PL 構造差異コメント | CRITICAL | `_PL_MAPPINGS` 内に営業利益不在・算出過程差異のコメントと `mapping_note` を追加。セクション 3.2 修正 |
| H-1: `net_income_parent` / `net_income_minority` INS版 | HIGH | Step 1 の確認項目 6 に追加。存在確認後 `_PL_MAPPINGS` に追加。セクション 6 修正 |
| H-2: BS 合計科目の INS版存在確認 | HIGH | Step 1 の確認項目 7 に追加。セクション 6 修正 |
| H-3: `__all__` の定義 | HIGH | セクション 3.1 に `__all__` 定義を追加。マイルストーン条件 18 に追加 |
| H-4: `mapping_note` の L2 との対称化 | HIGH | Option A 採用。`mapping_note: str = ""` を追加。重要マッピング 3 件に根拠記載。セクション 3.1, 3.6 修正 |
| H-5: 「保険引受利益」中間合計の確認 | HIGH | Step 1 の確認項目 8 に追加。セクション 6 修正 |
| M-1: 業種コード定数の切り出し | MEDIUM | `INSURANCE_INDUSTRY_CODES` をモジュールレベル定数として定義。`__all__` にも追加。セクション 3.1 修正 |
| M-2: 損保固有科目の候補リスト | MEDIUM | Step 1 の確認項目 9 に具体的候補を追加。セクション 6 修正 |
| M-3: クロスモジュールテスト docstring | MEDIUM | `test_shared_keys_match_jgaap` の docstring にクロスモジュール依存を明示。セクション 5.1 修正 |
| M-4: `_STATEMENT_INDEX` の将来拡張 | MEDIUM | 現状維持で OK。追加対応なし |
| L-1: セクション 10 のコード例が L1 を制約 | LOW | 「例示であり L1 の実装詳細は L1 計画に委ねる」注記を追加。セクション 10 修正 |
| L-2: `InsuranceProfile` キャッシュ | LOW | 現状維持。実装時の自然な選択 |
| L-3: テストクラス粒度 | LOW | 現状維持で OK |

### 第 4 回フィードバック反映

| フィードバック | 分類 | 対処 |
|--------------|------|------|
| H-1: `is_jgaap_specific` 相当フラグの不在 | HIGH | Option A 採用。不要理由をセクション 7.4 に明記（全マッピングが INS 固有のため情報量ゼロ） |
| H-2: `_PROFILE` キャッシュ構築パターンが未記載 | HIGH | セクション 3.6 に `_PROFILE` 構築コードと初期化順序の説明を追記 |
| H-3: `to_legacy_concept_list()` 不要の理由が未記載 | HIGH | セクション 2.3（スコープ外）に不要理由を追記 |
| H-4: `sector_id` vs `industry_code` の非対称性の影響考察 | HIGH | セクション 7.4 に設計意図と L1 normalize の責務として注記追加 |
| M-1: concept 名と canonical_key の乖離に対する保守者向け警告 | MEDIUM | セクション 7.7 を新設。`Operating` = 「経常」の命名慣習と canonical_key との乖離を明記 |
| M-2: `display_order > 0` と昇順整合性のバリデーション | MEDIUM | セクション 3.4 の検証項目に `display_order > 0` と昇順チェックを追加 |
| M-3: `test_insurance_specific_keys_not_in_jgaap` のスコープ明確化 | MEDIUM | テスト docstring に `_ins` サフィックスを判定基準とする旨を明記 |
| M-4: `is_total` の付与基準の文書化 | MEDIUM | セクション 7.8 を新設。プレゼンテーションリンクの合計行に基づく付与基準を明記 |
| L-1: `insurance_specific_concepts()` のソート順 | LOW | `_ALL_MAPPINGS` の定義順（PL → BS → CF）を維持する方針を API docstring に追記 |
| L-2: 統一テーブルに `is_total` 行不足 | LOW | セクション 7.4 のテーブルに `is_total` 行を追加 |
| L-3: Step 1 成果物フォーマット | LOW | 「成果物はコード内のマッピングタプルそのもの」と追記 |

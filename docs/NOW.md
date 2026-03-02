# NOW.md — 現在地の完全な記録

> **作成日**: 2026-03-02
> **対象バージョン**: Wave 3 完了直後
> **目的**: アーキテクチャ・実装状況・設計判断の経緯を、初見者が理解できる形で記録する

---

## 目次

- [Part 1: アーキテクチャ整理](#part-1-アーキテクチャ整理)
  - [1.1 全体パイプライン](#11-全体パイプライン)
  - [1.2 オブジェクト階層の全貌](#12-オブジェクト階層の全貌)
  - [1.3 concept_sets.py の仕組み](#13-concept_setspy-の仕組み)
  - [1.4 jgaap.py / ifrs.py / sector/ の役割](#14-jgaappy--ifrspy--sector-の役割)
  - [1.5 名寄せロジックの介入箇所](#15-名寄せロジックの介入箇所)
  - [1.6 自動化可能な部分と不可能な部分](#16-自動化可能な部分と不可能な部分)
  - [1.7 FUTUREPLAN.tmp.md の Free Rider 問題](#17-futureplanstmpmd-の-free-rider-問題)
  - [1.8 EDINET DB との競合比較](#18-edinet-db-との競合比較)
- [Part 2: Q&A 記録](#part-2-qa-記録)
  - [Q1: なぜ jgaap.py や sector の保守運用が必要なのか？](#q1)
  - [Q2: Wave Rider はどの Lane にも属さなかったのか？](#q2)
  - [Q3: 自動化できないものの本質は何か？](#q3)
  - [Q4: 名寄せロジックはパイプラインのどこに介入しているか？](#q4)
  - [Q5: 業種は 23 種あるが全部対応が必要か？](#q5)
  - [Q6: concept_sets はタクソノミ変更に追従不要か？](#q6)
- [Part 3: ハードコード検証結果](#part-3-ハードコード検証結果)
  - [3.1 ハードコード 4 項目](#31-concept_setspy-のハードコード-4-項目)
  - [3.2 実データ検証 (2023-2025)](#32-実データ検証-edinet-api)
  - [3.3 タクソノミ実物検証](#33-タクソノミ実物検証-2025-11-01)
  - [3.4 cns→cai バグ修正](#34-cns--cai-バグ修正)
  - [3.5 結論](#35-結論)
- [Part 4: 保守運用・名寄せ設計 Q&A](#part-4-保守運用名寄せ設計に関する-qa)
  - [Q7: 年次保守は統一キーの名寄せだけで OK か？](#q7-now-の内容を実装したら年次保守は統一キーの名寄せだけで-ok-か表示項目を増やす場合はどうなる)
  - [Q8: general_equivalent の役割](#q8-general_equivalent-の役割がわからない)
  - [Q9: standards/ と sector/ は競合しないか](#q9-standards-の名寄せと-sector-の-general_equivalent-は競合しないのか)
  - [Q10: 23 業種と一般企業の関係](#q10-業種-23-種のうち一般企業は何か)
  - [Q11: canonical_key と sector_key の命名分離](#q11-canonical_key-が同じ名前なのに意味が違うのはおかしくないかsector_key-に分けるべきでは)

---

# Part 1: アーキテクチャ整理

## 1.1 全体パイプライン

```
Filing.fetch() → ZIP bytes
       │
       │  .xbrl(taxonomy_path) → Statements
       │
       ▼
     ParsedXBRL ──────────────────────────────────────────
       ├── facts: tuple[RawFact, ...]        ← XBRL から直接パース
       ├── contexts: tuple[RawContext, ...]      人間の知識は一切不要
       └── units: tuple[RawUnit, ...]
             │
             ▼
     structure_contexts()  →  dict[str, StructuredContext]
     structure_units()     →  dict[str, StructuredUnit]
     TaxonomyResolver      →  ラベル解決（タクソノミから自動）
             │
             ▼
     build_line_items() ──────────────────────────────────
             │
             ▼
       LineItem                        ← ここまで名寄せ不要
         ├── concept: str                 全てタクソノミ駆動
         ├── local_name: str
         ├── label_ja: LabelInfo          ← taxonomy/labels から自動
         ├── label_en: LabelInfo          ← taxonomy/labels から自動
         ├── value: Decimal | str | None
         ├── period: Period
         ├── dimensions: tuple[DimensionMember, ...]
         └── order: int
             │
             │  ★★★ ここで名寄せロジックが介入 ★★★
             │
             │  build_statements(items, industry_code=...)
             │    ├── normalize.get_known_concepts(standard, PL)
             │    │     → 「この LineItem は PL に表示すべきか？」
             │    │     ※ concept_sets.py で代替可能（DONE）
             │    │
             │    └── normalize.get_concept_order(standard, PL)
             │          → 「PL 内でどの順番で表示するか？」
             │          ※ pres_tree で代替可能（DONE）
             │
             ▼
       Statements ────────────────────────────────────────
         ├── .income_statement()    → FinancialStatement
         ├── .balance_sheet()       → FinancialStatement
         └── .cash_flow_statement() → FinancialStatement
               │
               ▼
         FinancialStatement
           ├── items: tuple[LineItem, ...]
           ├── .to_dict()
           └── .to_dataframe()
```

### パイプライン内での `_build_single_statement()` の処理

`build_statements()` が呼ばれた後、各財務諸表の取得時に以下の 7 ステップが実行される:

1. **数値フィルタ**: Decimal 値のみ保持、nil 除外
2. **concept フィルタ**: `known_concepts` に含まれる科目のみ保持 ← **ここが名寄せ依存**
3. **期間選択**: 最新期間を自動選択（BS=max instant, PL/CF=max duration）
4. **連結/個別フィルタ**: 連結優先、なければ個別にフォールバック
5. **次元フィルタ**: セグメント次元なし（全社合計）のみ保持
6. **重複排除**: 同一 concept は最初の出現を保持
7. **ソート**: `concept_order` に基づく表示順 ← **ここが名寄せ依存**

**名寄せが介入するのは Step 2 と Step 7 のみ。** 他の 5 ステップは完全に自動。

---

## 1.2 オブジェクト階層の全貌

### Company → Filing

```
Company
  ├── edinet_code: str
  ├── name_ja: str | None
  ├── sec_code: str | None
  ├── ticker: str | None  (4桁証券コード)
  └── .get_filings() / .latest() → Filing

Filing
  ├── doc_id: str
  ├── edinet_code: str | None
  ├── filer_name: str | None
  ├── period_start / period_end: date | None
  ├── has_xbrl: bool
  ├── doc_type: DocType | None
  ├── .fetch()  → (xbrl_path, xbrl_bytes)
  └── .xbrl(taxonomy_path) → Statements
```

### ParsedXBRL（XBRL パース結果）

```
ParsedXBRL
  ├── facts: tuple[RawFact, ...]
  │     ├── concept_qname: str       (Clark notation)
  │     ├── namespace_uri: str
  │     ├── local_name: str
  │     ├── context_ref: str
  │     ├── unit_ref: str | None
  │     ├── value_raw: str | None
  │     ├── is_nil: bool
  │     └── order: int
  │
  ├── contexts: tuple[RawContext, ...]
  ├── units: tuple[RawUnit, ...]
  ├── schema_refs: tuple[RawSchemaRef, ...]
  └── footnote_links: tuple[RawFootnoteLink, ...]
```

### 構造化されたコンテキスト・ユニット

```
StructuredContext
  ├── context_id: str
  ├── period: InstantPeriod | DurationPeriod
  │     InstantPeriod:  instant: date
  │     DurationPeriod: start_date: date, end_date: date
  ├── entity_id: str
  ├── dimensions: tuple[DimensionMember, ...]
  │     DimensionMember: axis: str, member: str
  ├── is_consolidated: bool
  └── has_extra_dimensions: bool

StructuredUnit
  ├── unit_id: str
  ├── measure: SimpleMeasure | DivideMeasure
  ├── is_monetary / is_pure / is_shares / is_per_share: bool
  └── currency_code: str | None
```

### LineItem（構造化された 1 行）

```
LineItem (frozen dataclass)
  ├── concept: str           (Clark notation)
  ├── namespace_uri: str
  ├── local_name: str
  ├── label_ja: LabelInfo    (text + source + role + lang)
  ├── label_en: LabelInfo
  ├── value: Decimal | str | None
  ├── unit_ref: str | None
  ├── decimals: int | 'INF' | None
  ├── context_id: str
  ├── period: Period
  ├── entity_id: str
  ├── dimensions: tuple[DimensionMember, ...]
  ├── is_nil: bool
  └── order: int
```

### Statements / FinancialStatement（最終出力）

```
Statements (frozen dataclass)
  ├── _items: tuple[LineItem, ...]    (全期間・全次元)
  ├── _detected_standard: DetectedStandard | None
  ├── _facts: tuple[RawFact, ...]     (US-GAAP 抽出用)
  ├── _contexts: dict[str, StructuredContext]
  ├── _taxonomy_root: Path | None
  ├── _industry_code: str | None
  ├── .income_statement()    → FinancialStatement
  ├── .balance_sheet()       → FinancialStatement
  └── .cash_flow_statement() → FinancialStatement

FinancialStatement (frozen dataclass)
  ├── statement_type: StatementType
  ├── period: Period | None
  ├── items: tuple[LineItem, ...]
  ├── consolidated: bool
  ├── entity_id: str
  ├── warnings_issued: tuple[str, ...]
  ├── __getitem__("売上高")   → label_ja で引く
  ├── .to_dict()              → list[dict]
  └── .to_dataframe()         → pd.DataFrame
```

### DEI（書類及び企業情報）

```
DEI (frozen dataclass, 27 fields)
  ├── edinet_code / security_code / filer_name_ja / filer_name_en
  ├── accounting_standards: AccountingStandard | str | None
  │     AccountingStandard: JAPAN_GAAP / IFRS / US_GAAP / JMIS
  ├── has_consolidated: bool | None
  ├── industry_code_consolidated: str | None   ← 業種コード
  ├── industry_code_non_consolidated: str | None
  ├── current_fiscal_year_start_date / current_period_end_date
  └── type_of_current_period: PeriodType (FY / HY)
```

### NamespaceInfo（名前空間分類）

```
NamespaceInfo (frozen dataclass)
  ├── uri: str
  ├── category: STANDARD_TAXONOMY / FILER_TAXONOMY / XBRL_INFRASTRUCTURE / OTHER
  ├── is_standard: bool
  ├── module_name: str | None     (例: "jppfs_cor")
  ├── module_group: str | None    (例: "jppfs", "jpigp")
  ├── taxonomy_version: str | None (例: "2025-11-01")
  └── edinet_code: str | None
```

---

## 1.3 concept_sets.py の仕組み

### 何をするモジュールか

タクソノミの Presentation Linkbase（`_pre*.xml`）を自動解析し、**23 業種全ての PL/BS/CF/SS/CI に属する concept セットを動的に導出する。** 手動定義は一切不要。

### データ構造

```
ConceptSetRegistry
  └── _sets: {industry_code: {role_uri: ConceptSet}}

ConceptSet
  ├── role_uri: str
  ├── category: StatementCategory (BS/PL/CF/SS/CI)
  ├── is_consolidated: bool
  ├── cf_method: "direct" | "indirect" | None
  └── concepts: tuple[ConceptEntry, ...]
        ConceptEntry
          ├── concept: str     (local_name)
          ├── order: float     (表示順)
          ├── is_total: bool
          ├── is_abstract: bool
          ├── depth: int
          └── href: str
```

### 処理フロー

```
taxonomy_path
    │
    ▼
_scan_taxonomy_directory()
    │  taxonomy/jppfs/*/r/{industry}/ を走査
    │  *_pre*.xml を収集
    ▼
_group_pre_files()
    │  ファイル名の正規表現 _pre_(bs|pl|cf|ss|ci) でグルーピング
    ▼
_parse_and_merge_group()
    │  parse_presentation_linkbase() → PresentationTree
    │  同一 role URI のツリーをマージ
    ▼
classify_role_uri()
    │  role URI から StatementCategory + 連結/個別 + CF method を判定
    ▼
_tree_to_concept_set()
    │  DFS で全 concept を収集（dimension ノードはスキップ）
    ▼
_apply_cf_fallback()
    │  cns に CF がなければ他業種から補完
    ▼
ConceptSetRegistry (pickle キャッシュ)
```

### 全 23 業種の自動導出結果（2025-11-01 タクソノミ）

```
業種コード   PL   BS   CF    業種名
─────────────────────────────────────────
bk1          60   69   29    銀行・信託業
bk2           0    0    0    銀行（特定取引勘定設置）
cai          65   88   48    一般商工業
cmd          55   71   50    商品先物取引業
cna          61   61    0    建設保証業
cns          65   68   29    建設業
edu           0    0    0    学校法人
elc          61  141    0    電気通信事業
ele          84   97    0    電気事業
fnd           0    0    0    投資信託受益証券
gas          46   84    0    ガス事業
hwy          39   77   60    高速道路事業
in1          74   66   64    生命保険業
in2          76   62   58    損害保険業
inv           0    0    0    投資業
ivt          65   66    0    投資運用業
lea          71   82   65    リース事業
liq           0    0    0    資産流動化業
med           0    0    0    社会医療法人
rwy          50   58    0    鉄道事業
sec          49  112    0    第一種金融商品取引業
spf          64   66    0    特定金融業
wat          62   63    0    海運事業
```

※ 数値は `non_abstract_concepts()` の件数。
※ `0` の業種は _pre ファイルが存在しない（提出者なし or 別体系）。

### concept_sets.py のハードコード箇所（全 4 箇所）

| 箇所 | 内容 | 依存先 | 変更頻度 |
|---|---|---|---|
| `_STATEMENT_KEYWORDS`（9 個） | role URI のキーワードマッチ | XBRL 2.1 + EDINET 命名規則 | 極めて低い |
| `_STMT_RE` | `_pre_(bs\|pl\|cf\|ss\|ci)` 正規表現 | EDINET 設定規約書 | 極めて低い |
| `taxonomy/jppfs/*/r` | ディレクトリ走査パス | EDINET ディレクトリ構造 | 極めて低い |
| `"cns"` | CF フォールバック元 | 業種コード体系 | 極めて低い |

**concept 名は一切ハードコードされていない。** 個別科目名（`NetSales`, `CashAndDeposits` 等）はコードに登場しない。タクソノミ更新（例: 2025→2026）でコード変更は不要。

---

## 1.4 jgaap.py / ifrs.py / sector/ の役割

### 現在の jgaap.py が持っている情報

```python
ConceptMapping(
    concept="NetSales",              # concept ローカル名
    canonical_key="revenue",         # 会計基準横断の統一キー
    label_ja="売上高",               # 日本語ラベル
    label_en="Net sales",            # 英語ラベル
    statement_type=PL,               # 所属する財務諸表
    period_type="duration",          # instant / duration
    is_jgaap_specific=False,         # J-GAAP 固有か
    is_total=False,                  # 合計行か
    display_order=1,                 # 表示順序
)
```

### 各フィールドの自動化可能性

| フィールド | 自動化 | 代替手段 | 状態 |
|---|:---:|---|---|
| `concept` | — | — | concept 名そのもの |
| `canonical_key` | **不可能** | 人間の知識が必要 | 手動必須 |
| `label_ja` | **可能** | taxonomy/labels | TODO |
| `label_en` | **可能** | taxonomy/labels | TODO |
| `statement_type` | **済** | concept_sets.py | DONE |
| `period_type` | **可能** | XSD の periodType 属性 | TODO |
| `is_jgaap_specific` | **不可能** | 人間の知識が必要 | 手動必須 |
| `is_total` | **済** | pres_tree の preferredLabel | DONE |
| `display_order` | **済** | pres_tree の order | DONE |

### 本来 jgaap.py に必要なのは以下だけ

```python
# canonical_key マッピングのみ（ラベル・順序・業種分類なし）
_CANONICAL_KEYS: dict[str, str] = {
    "NetSales": "revenue",
    "CostOfSales": "cost_of_sales",
    "OperatingIncome": "operating_income",
    ...
}

_CROSS_STANDARD: dict[str, str] = {
    "NetSales": "RevenueIFRS",      # J-GAAP → IFRS
    "RevenueIFRS": "NetSales",      # IFRS → J-GAAP
    ...
}
```

### sector/ モジュールの状況

sector/ は jgaap.py と同じ問題を業種レベルで再現している:

```python
# sector/banking.py（手動定義の例）
SectorConceptMapping(
    concept="OrdinaryIncomeBNK",
    canonical_key="ordinary_income_banking",
    label_ja="経常収益",               # ← labels で自動化可能
    display_order=1,                    # ← pres_tree で自動化可能
    general_equivalent="NetSales",      # ← 銀行→一般の名寄せ（比較用）
)
```

sector/ の `general_equivalent` は「銀行の経常収益 ≒ 一般事業の売上高」という人間の知識。**ただし銀行の財務諸表をそのまま表示するだけなら不要**（concept_sets が銀行の PL を自動導出済み）。

---

## 1.5 名寄せロジックの介入箇所

パイプライン全体で名寄せが介入するのは **`build_statements()` の 1 箇所だけ**:

```
RawFact → LineItem:            名寄せ不要（全自動）
LineItem → FinancialStatement:  ★ ここだけ ★
FinancialStatement → 表示:      名寄せ不要
```

`build_statements()` 内で jgaap.py / ifrs.py を参照しているのは 2 処理:

| # | 処理 | 現在の参照元 | 自動化代替 |
|---|------|-------------|---|
| 1 | concept フィルタ（PL/BS/CF 分類） | jgaap.py の `_PL_MAPPINGS` 等 | concept_sets.py（DONE） |
| 2 | ソート順（表示順序） | jgaap.py の `display_order` | pres_tree の order（DONE） |

### canonical_key は現時点で誰にも使われていない

```python
# FinancialStatement.__getitem__ の実装
def __getitem__(self, key: str) -> LineItem:
    # label_ja.text で検索
    # label_en.text で検索
    # local_name で検索
    # → canonical_key による検索は未実装
```

canonical_key を使っている箇所:
- `normalize.py` の `cross_standard_lookup()` — 実装済みだが **呼び出し元なし**
- `sector/` の `general_equivalent` — 実装済みだが **呼び出し元なし**

---

## 1.6 自動化可能な部分と不可能な部分

### 全体マトリクス

```
taxonomy/labels + concept_sets + pres_tree（全部実装済み or 実装可能）
  → 単体企業の財務諸表表示: 全自動化可能

standards/ の canonical_key + 会計基準間マッピング（手動必須）
  → 会計基準をまたぐ比較: J-GAAP 企業と IFRS 企業を同じキーで並べる

sector/ の general_equivalent（手動必須）
  → 業種をまたぐ比較: 銀行と製造業を同じキーで並べる
```

### standards/ の本質

```
canonical_key (統一キー)  1 ── 多  各会計基準の concept
─────────────────────────────────────────────────
"revenue"              →  J-GAAP:  "NetSales"
                       →  IFRS:    "RevenueIFRS"
                       →  US-GAAP: (BLOCK_ONLY)

"operating_income"     →  J-GAAP:  "OperatingIncome"
                       →  IFRS:    "OperatingProfitLossIFRS"

"ordinary_income"      →  J-GAAP:  "OrdinaryIncome"
                       →  IFRS:    (存在しない)  ← この「存在しない」も人間の知識
```

### sector/ の本質

```
sector concept (業種固有)  →  general_equivalent (一般事業の対応概念)
──────────────────────────────────────────────────────
"OrdinaryIncomeBNK"        →  "NetSales"     (経常収益 ≈ 売上高)
"OrdinaryExpensesBNK"      →  "CostOfSales"  (経常費用 ≈ 売上原価)
```

この「銀行の経常収益は一般事業の売上高に相当する」はタクソノミのどこにも書かれていない人間の知識。

### いつ名寄せが必要か

| やりたいこと | standards/ 名寄せ | sector/ 名寄せ |
|---|:---:|:---:|
| 任天堂（J-GAAP）の PL を表示 | 不要 | 不要 |
| ソニー（IFRS）の PL を表示 | 不要 | 不要 |
| みずほ（銀行）の PL を表示 | 不要 | 不要 |
| 任天堂とソニーの売上を比較 | **必要** | 不要 |
| みずほとトヨタの売上を比較 | **必要** | **必要** |
| みずほ 30 社の経常収益を比較 | 不要 | 不要 |

**「比較」が不要なら名寄せは一切不要。**

---

## 1.7 FUTUREPLAN.tmp.md の Free Rider 問題

### 計画上の Wave 2 構成

**Lane テーブル（担当あり、全て実行された）:**

| Lane | Feature | 状態 |
|---|---|---|
| L1 | taxonomy/concept_sets | DONE |
| L2 | standards/detect | DONE |
| L3 | standards/jgaap | DONE |
| L4 | standards/ifrs | DONE |
| L5 | standards/usgaap | DONE |

**Free Rider（Lane テーブルの外に記載、オーナーなし）:**

| Feature | 依存先 | 状態 |
|---|---|---|
| taxonomy/labels | namespaces (W1 DONE) | **未実装** |
| taxonomy/versioning | namespaces (W1 DONE) | **未実装** |
| taxonomy/standard_mapping | calc_tree (W1 DONE) | **未実装** |
| dimensions/consolidated | contexts + def_links (W1 DONE) | **未実装** |

### 何が起きたか

Free Rider は「依存が充足されているからいつでも実装可能」と記載されていたが、**どの Lane にも割り当てられなかった。** 結果:

1. Wave 2 の 5 Lane が全て完了しても Free Rider は誰も実装しなかった
2. Wave 3 に進み、L3 (jgaap) / L4 (ifrs) は taxonomy/labels が存在しない前提で実装
3. ラベル・表示順序を全て Python にハードコードする結果になった

### 影響

| 計画 | 実際 | 影響 |
|---|---|---|
| Wave 2 Free Rider で taxonomy/labels 実装 | スキップ | ラベルを jgaap.py にハードコード |
| Wave 2 Free Rider で taxonomy/versioning 実装 | スキップ | 過去タクソノミの concept 変更に対応不可 |
| jgaap.py は canonical_key のみ保持 | 全情報をハードコード | 保守コスト増、単一年度固定 |

### jgaap.py が「太った」原因

現在の jgaap.py は 2025-11-01 タクソノミのスナップショットをハードコードしている:

```python
ConceptMapping(
    concept="CashAndDeposits",  # ← 2025-11-01 の concept 名
    label_ja="現金及び預金",     # ← 2025-11-01 のラベル
    display_order=101,           # ← 2025-11-01 の表示順序
)
```

**問題点:**
- 2023 年の有報を読むとき、ラベルや表示順序が 2025 年版のまま
- deprecated された concept は認識できない
- taxonomy/labels を実装していれば、渡されたタクソノミから動的に取得できたはず

### あるべき姿

```
concept_sets.py  → PL/BS/CF 分類（DONE、タクソノミから自動）
pres_tree        → 表示順序（DONE、タクソノミから自動）
taxonomy/labels  → ラベル（TODO、タクソノミから自動取得すべき）
jgaap.py         → canonical_key + 会計基準間マッピングのみ（手動必須）
```

### 計画の構造的な問題

**Free Rider = オーナーなし = 実行されない。**

---

## 1.8 EDINET DB との競合比較

EDINET DB（edinetdb.jp）は 69 指標 × 約 3,800 社の財務 API。任天堂 (E02367) の 2025-03 期データで比較。

### 指標レベルの網羅率

| 区分 | EDINET DB 指標数 | edinet ライブラリ | 網羅率 |
|---|:---:|:---:|:---:|
| PL | 9 | 9 + 追加 7 | **100%** |
| BS | 15 | 15 (修正後) | **100%** |
| CF | 4 | 3 | 75% (capex 未対応) |
| 算出指標 (ROE, PER 等) | 41 | 1 (減価償却のみ) | 2% |

### BS 修正の詳細（本セッションで実施）

**jgaap.py に追加した 4 concepts:**

| concept | canonical_key | display_order |
|---|---|:---:|
| `CashAndDeposits` | `cash_and_deposits` | 101 |
| `NotesAndAccountsReceivableTrade` | `trade_receivables` | 102 |
| `Inventories` | `inventories` | 103 |
| `NotesAndAccountsPayableTrade` | `trade_payables` | 501 |

**ifrs.py に追加した 3 concepts:**

| concept | canonical_key | display_order |
|---|---|:---:|
| `TradeAndOtherReceivablesCAIFRS` | `trade_receivables` | 101 |
| `InventoriesCAIFRS` | `inventories` | 102 |
| `TradeAndOtherPayablesCLIFRS` | `trade_payables` | 601 |

※ `CashAndCashEquivalentsIFRS` は既存（display_order を 16→103 に変更）。

### タクソノミ実在検証

全 28 テスト通過（`EDINET_TAXONOMY_ROOT` 設定時）:

| 対象 | テスト数 | 結果 |
|---|:---:|:---:|
| J-GAAP (PL16 + BS24 + CF35 + 全体) | 4 | ALL PASSED |
| IFRS (PL15 + BS19 + CF16 + 全体) | 4 | ALL PASSED |
| Sector (banking/insurance/construction/railway/securities) | 20 | ALL PASSED |

### 算出指標のギャップ

EDINET DB の算出指標（ROE, PER, BPS, EPS, 配当利回り等 41 個）は `jpcrp_cor` 名前空間の `*SummaryOfBusinessResults` concept として XBRL に存在する（任天堂の実データで 21 concepts 確認済み）。ただし FEATURES.md にこの機能は未定義。

---

# Part 2: Q&A 記録

以下は 2026-03-02 のセッションでの Q&A をほぼ忠実に記録したもの。

---

<a id="q1"></a>
## Q1: なぜ jgaap.py や sector の保守運用が必要なのか？

> **質問**: なんで jgaap.py や sector ごとの保守運用が必要なの？以下の機能は実際に実装されてないの？こいつら実装しても保守運用必要なん？役割の違いは？（calc_tree, pres_tree, def_links, taxonomy/versioning, taxonomy/standard_mapping, taxonomy/concept_sets を列挙）

### 回答

各機能の実装状況:

| 機能 | 実装状態 | jgaap.py 保守への関係 |
|---|---|---|
| **concept_sets** | **DONE** | 「PL に属する concept 一覧」を自動導出。だが canonical_key は知らない |
| **pres_tree** | **DONE（解析）** | concept_sets の内部で使用済み。表示順序の自動取得に使っている |
| **calc_tree** | **DONE（解析のみ）** | 将来の計算検証（Phase 9）用。standard_mapping の基盤 |
| **def_links** | **DONE（解析のみ）** | SS/CI の 2 次元テーブル構築用。保守運用とは無関係 |
| **taxonomy/versioning** | **TODO** | 年度横断で concept 名が変わった際の自動マッピング。保守運用軽減に直結 |
| **taxonomy/standard_mapping** | **TODO** | calc_tree を遡って非標準→標準の集約先を推論。保守運用を本質的に減らす |

**concept_sets は「分類」はできるが「意味づけ」ができない:**

```
concept_sets.py が知っていること:
  "NetSales は PL に属する概念で、order=1"

jgaap.py が知っていること:
  "NetSales の canonical_key は 'revenue'"
  "NetSales の IFRS 対応は 'RevenueIFRS'"
  "NetSales の日本語ラベルは '売上高'"
  "NetSales は J-GAAP 固有ではない"
```

### 全部実装したら保守不要になるか？

3 段階で変化する:

| Phase | 状態 | jgaap.py の保守範囲 |
|---|---|---|
| **Phase A（現在）** | labels/versioning 未実装 | 全フィールド手動保守 |
| **Phase B** | taxonomy/labels 実装後 | label_ja / label_en が不要に |
| **Phase C** | labels + pres_tree 接続後 | display_order も不要に |

**canonical_key だけは自動化が本質的に困難。** 「J-GAAP の経常利益は IFRS に存在しない」「IFRS の Revenue は J-GAAP の NetSales に対応する」という知識はリンクベースのどこにも書かれていない。

---

<a id="q2"></a>
## Q2: Wave Rider はどの Lane にも属さなかったのか？

> **質問**: Wave Rider はどの Lane にも属さなかったってこと？

### 回答

そう。FUTUREPLAN.tmp.md の Wave 2 セクション:

**Lane テーブル（L1-L5: 担当あり）:**
```
L1  taxonomy/concept_sets
L2  standards/detect
L3  standards/jgaap
L4  standards/ifrs
L5  standards/usgaap
```

**Free Rider（Lane テーブルの外に記載）:**
```
Free Rider（依存が W1 で充足済み、新規ファイルのみ）:
- taxonomy/labels → L5 namespaces
- taxonomy/versioning → L5 namespaces
- taxonomy/standard_mapping → L2 calc_tree
- dimensions/consolidated → L4 contexts + L3 def_links
- footnotes → 新規
- text_blocks → 新規
```

**どの Lane にも割り当てられていない。** 「依存は充足されているからいつでもやれる」と書いてあるだけで、誰がやるかは未定義だった。

結果として Wave 2 の 5 Lane が全部完了しても Free Rider は誰も拾わず、Wave 3 に進んだ。Wave 3 の L3 (jgaap) / L4 (ifrs) は taxonomy/labels が存在しない前提で実装せざるを得ず、ラベル・表示順序を全部 Python にハードコードした。

**計画の構造的な問題: Free Rider = オーナーなし = 実行されない。**

---

<a id="q3"></a>
## Q3: 自動化できないものの本質は何か？

> **質問**: 自動化できないのは src/edinet/xbrl/standards/ に書かれているものが対応し、本質的には会計基準間の差異を埋めるための統一キー 1→多 各会計基準のそのコンセプト でいい？あと sector についてはどう？

### 回答

そう。standards/ の本質は:

```
canonical_key (統一キー)  1 ── 多  各会計基準の concept
─────────────────────────────────────────────────
"revenue"              →  J-GAAP:  "NetSales"
                       →  IFRS:    "RevenueIFRS"

"ordinary_income"      →  J-GAAP:  "OrdinaryIncome"
                       →  IFRS:    (存在しない)
```

sector も本質は同じ構造で `general_equivalent` フィールドを持つ:

```
sector concept (業種固有)  →  general_equivalent (一般事業の対応概念)
──────────────────────────────────────────────────────
"OrdinaryIncomeBNK"        →  "NetSales"     (経常収益 ≈ 売上高)
```

**ただし sector は standards より自動化余地が大きい:**

| 情報 | standards/ | sector/ |
|---|---|---|
| PL/BS/CF 分類 | 自動化済 | 自動化済 |
| 表示順序 | 自動化可能 | 自動化可能 |
| ラベル | 自動化可能 | 自動化可能 |
| **canonical_key** | **手動必須** | 不要（会計基準間の話） |
| **会計基準間マッピング** | **手動必須** | 不要（sector は全て J-GAAP 内） |
| **general_equivalent** | 不該当 | **手動必須**（業種↔一般の対応） |

---

<a id="q4"></a>
## Q4: 名寄せロジックはパイプラインのどこに介入しているか？

> **質問**: つまり Company からはじまって Fact に根差す現在の概念のどこの部分がその名寄せロジックを必要としている？全概念示したうえで教えて

### 回答

（[1.1 全体パイプライン](#11-全体パイプライン) と [1.2 オブジェクト階層の全貌](#12-オブジェクト階層の全貌) に記載済み）

結論:

```
名寄せロジックが介入する箇所:  build_statements() 内の 2 処理
  ├── concept フィルタ  → concept_sets.py で代替可能（DONE）
  └── ソート順          → pres_tree で代替可能（DONE）

canonical_key が必要な箇所:  現時点でゼロ
  ├── cross_standard_lookup() → 実装済みだが呼び出し元なし
  └── FinancialStatement["revenue"] → 未実装
```

**jgaap.py / ifrs.py / sector/ が `build_statements()` に介入しているのは、concept_sets + pres_tree を直接使う接続がまだ書かれていないから。** 既存の自動化手段に切り替えれば、単体企業の財務諸表表示に名寄せは一切不要。

---

<a id="q5"></a>
## Q5: 業種は 23 種あるが全部対応が必要か？

> **質問**: 業種って 23 種くらいあるんだっけ？銀行や保険、証券会社だけ対応すればいいのではないの？これらは名寄せが本当に必要？

### 回答

concept_sets は既に全 23 業種を完全にカバーしている（[1.3 の表](#全-23-業種の自動導出結果2025-11-01-タクソノミ) 参照）。

銀行の PL は `OrdinaryIncomeBNK`（経常収益）から始まり、一般事業は `NetSales`（売上高）から始まる。**この違いは concept_sets が Presentation Linkbase から自動で読み取っている。**

名寄せが本当に必要なケースの整理:

| やりたいこと | sector 名寄せ必要？ |
|---|:---:|
| 銀行の財務諸表を表示する | **不要** |
| 銀行の PL で「経常収益」「経常費用」を正しく出す | **不要**（concept_sets + labels で自動） |
| 銀行と製造業の売上を同じキーで比較する | **必要** |
| 銀行 30 社の経常収益を横断比較する | **不要**（同じ業種内は同じ concept） |

**sector/ モジュール（banking.py, insurance.py 等）を手動で書く必要はなかった。** concept_sets + taxonomy/labels + pres_tree で全 23 業種の財務諸表表示は完全に自動化できる。手動の sector/ が必要になるのは「業種をまたぐ canonical_key 比較」を実装するときだけ。

---

<a id="q6"></a>
## Q6: concept_sets はタクソノミ変更に追従不要か？

> **質問**: concept_sets はタクソノミ変更しても追従不要な堅牢な実装ですか？

### 回答

concept_sets.py のハードコードは全 4 箇所のみ（全て EDINET の仕様レベルに依存）:

| ハードコード | 内容 | 壊れるケース |
|---|---|---|
| `_STATEMENT_KEYWORDS`（9 個） | role URI キーワード | XBRL 仕様変更 |
| `_STMT_RE` | ファイル名正規表現 | 設定規約書の命名規則変更 |
| `taxonomy/jppfs/*/r` | ディレクトリパス | ディレクトリ構造変更 |
| `"cns"` | CF フォールバック元 | 業種コード体系変更 |

**concept 名は一切ハードコードされていない。**

タクソノミが 2025-11-01 → 2026-11-01 に更新された場合:
- concept が追加/削除されても → **コード変更不要**（自動追従）
- 表示順序が変わっても → **コード変更不要**（自動追従）
- 業種が追加されても → **コード変更不要**（ディレクトリを自動走査）
- キャッシュは taxonomy_path のハッシュで区別 → **自動無効化**

**壊れるケース:** EDINET が role URI の命名規則やディレクトリ構造を根本変更したとき。これは EDINET の設定規約書改訂（数年に一度レベル）でしか起こらない。

---

# Part 3: ハードコード検証結果

> **検証日**: 2026-03-02
> **検証スクリプト**: `tools/hardcode_verification.py`

## 3.1 concept_sets.py のハードコード 4 項目

concept_sets.py には 4 つのハードコード要素がある。それぞれが EDINET 仕様書に明記されているか、実データで動作するかを検証した。

### ハードコード一覧

| # | 何がハードコードか | 実際の値 | 用途 |
|---|---|---|---|
| 1 | `_STATEMENT_KEYWORDS` | 11 キーワード | role URI → BS/PL/CF/SS/CI の分類 |
| 2 | `_STMT_RE` | `_pre_(bs\|pl\|cf\|ss\|ci)` | ファイル名 → 財務諸表種別の分類 |
| 3 | ディレクトリ glob | `taxonomy/jppfs/*/r` | タクソノミファイルの所在 |
| 4 | デフォルト業種 | `"cai"` (一般商工業) | パイプラインのデフォルト |

### 仕様書の根拠

| # | 仕様書 | 該当箇所 | 判定 |
|---|---|---|---|
| 1 | 設定規約書 | 図表3-2-35 (L.1441-1462) — role URI 命名規則 | **仕様準拠** |
| 2 | 設定規約書 | 図表1-4-11 (L.549-563) — 略称 5 種の閉集合, 図表3-3-1 (L.1652-1661) | **仕様準拠** |
| 3 | 設定規約書別紙 | 別紙3-1 (L.169, 400-510) — ディレクトリ構造 | **仕様準拠** |
| 4 | 設定規約書 | 図表1-4-6 (L.469-474) — 23 業種コード一覧 | **バグ修正済** (cns→cai) |

## 3.2 実データ検証 (EDINET API)

### 検証範囲の制約

- **EDINET API は約 3 年分のデータしか保持しない**
- 2019-2022 は全て 404 → **検証不可能**
- 2023-2025 の 3 年分で検証を実施

### 検証結果

```
Year | 企業名               | roleURI分類 | _preパターン | Pipeline | PL | BS | CF
-----|---------------------|-----------|-----------|---------|----|----|---
2023 | 日本観光ゴルフ         | OK        | OK        | OK      | 11 | 16 | 14
2024 | 中外炉工業            | OK        | OK        | OK      | 15 | 19 | 23
2025 | 日本甜菜製糖          | OK        | OK        | OK      | 15 | 18 | 22
```

各年について以下を検証:
1. **roleURI 分類**: XBRL instance 内の全 roleURI を `classify_role_uri()` で分類。`/rol_` を含む財務諸表 roleURI が全て分類可能かチェック → 3 年とも **OK**
2. **_pre パターン**: ZIP 内の `_pre` ファイル名が `_pre_(bs|pl|cf|ss|ci)` で正しく分類可能か → 提出者 _pre (分類不要) のみ存在、**正常**
3. **full pipeline**: `parse_xbrl_facts → build_line_items → build_statements → income_statement()/balance_sheet()/cash_flow_statement()` を通しで実行 → 3 年とも **OK**

### 2023 の補足

日本観光ゴルフは個別のみ (連結なし) の小規模企業で、PL=11, BS=16, CF=14。連結ありの企業 (2024, 2025) より概念数が少ないが正常。

## 3.3 タクソノミ実物検証 (2025-11-01)

手元の `ALL_20251101` タクソノミの全 `_pre_(bs|pl|cf|ss|ci)` ファイル (646 ファイル) から roleURI を抽出して `classify_role_uri()` で分類テスト:

```
全 82 ユニーク roleURI
├── 財務諸表 (rol_ を含む): 41 件
│   ├── classify_role_uri で分類可能: 39 件
│   └── 未分類: 2 件 (jpigp = IFRS、jppfs スコープ外)
│       ├── rol_std_ConsolidatedStatementOfFinancialPositionIFRS
│       └── rol_std_ConsolidatedStatementOfProfitOrLossIFRS
└── ラベル系 (label/totalLabel/periodLabel): 41 件 → 対象外
```

未分類の 2 件は `jpigp` (IFRS タクソノミ) のみに存在し、concept_sets.py は `jppfs` のみ処理するため **スコープ外で問題なし**。

## 3.4 `cns` → `cai` バグ修正

### 発見経緯

仕様書検証中に、デフォルト業種コード `"cns"` が建設業であることが判明。一般商工業は `"cai"`。

### 影響

- `cns` は CF の Presentation Linkbase を持たず、bk1 (銀行業) から fallback 補完していた
- `cai` は自前の CF を持つ (48 concepts) ため、fallback 不要

### 修正箇所

| ファイル | 修正内容 |
|---|---|
| `concept_sets.py` | `ConceptSetRegistry.get()`, `statement_categories()`, `get_concept_set()` のデフォルト引数 |
| `concept_sets.py` | `_apply_cf_fallback()` のドキュメントと変数名 |
| `concept_sets.pyi` | 対応するスタブ (3 箇所) |
| `test_concept_sets.py` | テストフィクスチャの業種コード (6 箇所) |

## 3.5 結論

| 項目 | 判定 |
|---|---|
| ハードコード 4 項目は全て EDINET 仕様書に明記 | **堅牢** |
| 3 年分の実データ (2023-2025) で全検証パス | **堅牢** |
| タクソノミ実物 (jppfs) で 100% カバー | **堅牢** |
| 過去タクソノミ (2019-2024) での実検証 | **不可** (手元になし) |

過去タクソノミ未検証のリスクは、EDINET 仕様書で命名規則・ディレクトリ構造が規定されており後方互換が維持される設計であることから、**実質的に低い**。

---

# Part 4: 保守運用・名寄せ設計に関する Q&A

> Part 3 の検証完了後、保守運用の範囲と canonical_key の設計について議論した記録。

---

## Q7: NOW の内容を実装したら年次保守は統一キーの名寄せだけで OK か？表示項目を増やす場合はどうなる？

### 回答: ほぼ YES。ただし前提条件がある。

jgaap.py / ifrs.py に手書きされている項目のうち、自動化できるものとできないもの:

| 項目 | 自動化可能? | 根拠 |
|---|---|---|
| concept 名 (例: `NetSales`) | **自動** | concept_sets が pres linkbase から導出済 |
| canonical_key (例: `"revenue"`) | **手動** | 会計基準間の人間の知識 |
| label_ja / label_en | **自動** | taxonomy label linkbase から取れる (未実装) |
| display_order | **自動** | pres linkbase の order 属性 (concept_sets が既に持つ) |
| period_type | **自動** | taxonomy XSD の periodType 属性 (未実装) |
| is_jgaap_specific | **手動** | 会計基準の設計知識 |

#### 年次タクソノミ更新 (`ALL_20261101` が出たとき) にやること

```
1. タクソノミ ZIP を差し替える               → ファイル入替のみ
2. concept_sets のキャッシュクリア            → 自動 (パスハッシュで無効化)
3. 新規追加された concept があれば
   canonical_key を standards/ に追加        → 手動 (唯一の作業)
4. テスト実行                              → uv run pytest
```

sector/ について: 単一企業の表示には不要。複数業種の横断比較をする場合のみ `general_equivalent` マッピングの保守が必要。

#### 表示項目を増やす場合

**パターン A: 企業が提出した全項目を表示したい**

コード変更不要。concept_sets が pres linkbase から全 concept を自動導出しているので、企業が XBRL で報告したものは全て表示できる。statements.py の参照先を concept_sets に切り替えるだけ。

**パターン B: 正規化された統一項目を増やしたい**

例: 「研究開発費」を PL の統一表示項目に追加する場合、jgaap.py と ifrs.py の両方に canonical_key を追加する。これは「名寄せの拡張」そのもの。

#### 保守対象まとめ

```
                          年次タクソノミ更新    表示項目の追加
                          ─────────────    ──────────
concept_sets (自動)        変更不要           変更不要
standards/ (canonical_key) 新概念の追加のみ     追加したい概念を登録
sector/ (general_equiv)    不要 (横断比較のみ)  不要
statements.py              変更不要           変更不要
```

---

## Q8: general_equivalent の役割がわからない

### 回答: 業種固有の科目を一般事業会社の科目に「翻訳」するためのキー。

業種によって PL の構造が根本的に違う:

```
一般事業会社 (cai)          銀行業 (bk1)
─────────────            ──────────
売上高     (NetSales)      経常収益   (OrdinaryIncomeBNK)
売上原価   (CostOfSales)   資金運用収益 (InterestIncomeOIBNK)
営業利益   (OperatingIncome) 経常費用   (OrdinaryExpensesBNK)
経常利益   (OrdinaryIncome)  経常利益   (OrdinaryProfitBNK)
```

general_equivalent が橋渡しする:

```python
SectorConceptMapping(
    concept="OrdinaryIncomeBNK",           # 銀行の concept 名
    canonical_key="ordinary_revenue_bnk",   # 銀行業内での正規化キー
    general_equivalent="revenue",           # ← 一般事業会社の canonical_key
)
```

これにより:
- トヨタ (一般): `NetSales` → canonical_key = `"revenue"`
- 三菱UFJ (銀行): `OrdinaryIncomeBNK` → general_equivalent = `"revenue"`
- 同じ `"revenue"` で紐づく → **異業種間で比較可能**

#### いつ必要か

| ユースケース | general_equivalent 必要? |
|---|---|
| 1 社の財務諸表を表示 | **不要** |
| 同業種の比較 (銀行 vs 銀行) | **不要** (canonical_key で十分) |
| **異業種の比較** (銀行 vs 一般) | **必要** |
| スクリーニング (全上場企業の売上高ランキング) | **必要** |

---

## Q9: standards/ の名寄せと sector/ の general_equivalent は競合しないのか？

### 回答: 競合しない。2 つの異なる軸の正規化。

```
                    会計基準の軸 (standards/)
                    ─────────────────────→
                    J-GAAP        IFRS         US-GAAP

業  一般事業会社     NetSales      RevenueIFRS   Revenues
種                     ↓              ↓            ↓
の                  canonical_key = "revenue" (全部同じ)
軸
(sector/)
    銀行業          OrdinaryIncomeBNK
                        ↓
                    canonical_key = "ordinary_revenue_bnk"
                        ↓ general_equivalent
                    "revenue" ← ここで standards/ と合流
```

- **standards/**: 横の軸。同じ業種で会計基準が違う → 同じキーに
- **sector/**: 縦の軸。同じ会計基準で業種が違う → general_equivalent で合流

衝突しない理由: jgaap.py に銀行固有の concept は登録されていない。banking.py に一般事業会社の concept は登録されていない。**担当範囲が排他的**。

---

## Q10: 業種 23 種のうち「一般企業」は何か？

### 回答: `cai` (一般商工業) が一般企業。上場企業の大多数がこれ。

23 業種は「東証の業種分類」ではなく、**財務諸表の様式が違うかどうか**で分けた EDINET 独自の分類:

```
cai (一般商工業)  ← トヨタ、ソニー、任天堂、製造業、サービス業 ... 大多数
cns (建設業)      ← 大和ハウス、住友林業
bk1 (銀行)        ← みずほ、あおぞら
bk2 (特定取引銀行) ← 三菱UFJ、三井住友
sec (証券)        ← 野村證券、大和証券
in1 (生命保険)    ← 日本生命、第一生命
rwy (鉄道)        ← JR東日本、東急
ele (電気事業)    ← 東京電力、関西電力
... 他
```

東証の「電気機器」「機械」「化学」「小売業」「卸売業」等は PL/BS の様式が同じなので、EDINET タクソノミでは全て `cai` に集約される。

standards/ は **cai 専用**。cai 以外の 22 業種は sector/ が担当する設計。

---

## Q11: canonical_key が同じ名前なのに意味が違うのはおかしくないか？sector_key に分けるべきでは？

### 回答: その通り。分けるべき。

現状の問題:

```python
# jgaap.py
canonical_key="revenue"              # ← 全体の共通語

# banking.py
canonical_key="ordinary_revenue_bnk" # ← 銀行内ローカル ← 同じフィールド名!
general_equivalent="revenue"          # ← 全体の共通語を参照
```

`canonical_key` というフィールド名が 2 つの異なるスコープで使われている。

#### 改善案

```python
# standards/jgaap.py
ConceptMapping(
    concept="NetSales",
    canonical_key="revenue",         # 全体の lingua franca (変更なし)
)

# sector/banking.py
SectorConceptMapping(
    concept="OrdinaryIncomeBNK",
    sector_key="ordinary_revenue_bnk",   # 名前変更: 銀行内ローカル
    general_equivalent="revenue",         # lingua franca への参照 (変更なし)
)
```

| フィールド名 | スコープ | 定数化 |
|---|---|---|
| `canonical_key` | 全体共通 (cai 基準) | する (`CanonicalKey.REVENUE`) |
| `sector_key` | 業種内ローカル | しない (1 ファイル内で閉じる) |
| `general_equivalent` | sector → canonical_key への翻訳 | する (値は `CanonicalKey.*`) |

#### マジックストリング対策

canonical_key は現状ただの文字列リテラルで、3 ファイル以上にバラバラに散っている:

```python
# 現状: typo しても静かに壊れる
canonical_key="revenue"              # jgaap.py
canonical_key="revenue"              # ifrs.py
general_equivalent="revenue"          # banking.py
```

定数化すれば:

```python
# 改善後: typo → AttributeError (即座に検出)
canonical_key=CanonicalKey.REVENUE    # jgaap.py
canonical_key=CanonicalKey.REVENUE    # ifrs.py
general_equivalent=CanonicalKey.REVENUE # banking.py
```

実データ検証 (2026-03-02 時点):
- jgaap の canonical_key: 83 個
- ifrs の canonical_key: 55 個
- jgaap ∩ ifrs (会計基準間で名寄せ済): **45 個**
- sector の general_equivalent: 18 個 → **全て jgaap に存在** (テストで保証済)

現状テスト (`test_sector_cross_validation.py`) で general_equivalent → jgaap の整合性は検証されているが、jgaap ↔ ifrs 間の整合性テストは暗黙的。定数化すればこの問題も解消する。

#### sector_key を定数化しない理由

`"ordinary_revenue_bnk"` は banking.py と test_banking.py の中でしか使われない。複数ファイルをまたがないのでマジックストリング問題が発生しない。

---


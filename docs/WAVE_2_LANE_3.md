# Wave 2 / Lane 3 — standards/jgaap: J-GAAP 科目の正規化マッピング

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 2 / Lane 3 を担当するエージェントです。
担当機能: standards_jgaap

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
   - `src/edinet/xbrl/standards/jgaap.py` (新規)
   - `tests/test_xbrl/test_standards_jgaap.py` (新規)
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
   - 例: `from edinet.financial.standards.jgaap import lookup_canonical` （OK）
   - 例: `from edinet.xbrl import lookup_canonical` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_standards_jgaap.py` に作成
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
   - **他の Wave 2 レーンが作成中のモジュール**（concept_sets, detect, ifrs, usgaap）に依存してはならない

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 3 — standards/jgaap: J-GAAP 科目の正規化マッピング

## 0. 位置づけ

Wave 2 Lane 3 は、FEATURES.md の **Accounting Standard Normalization > standards/jgaap** に対応する。J-GAAP（日本基準）に固有の科目知識をカプセル化し、**会計基準横断の正規化**（Wave 3 `standards/normalize`）の基盤データを提供するモジュールである。

FEATURES.md の定義:

> - standards/jgaap: 日本基準の科目マッピング [TODO]
>   - depends: facts, namespaces
>   - detail: jppfs_cor 系タクソノミの全科目対応

FUTUREPLAN.tmp.md での位置:

> Phase 3-2: `standards/jgaap` → namespaces 依存

### 本モジュールの核心的価値

EDINET ライブラリの最終目標は「`売上高` を指定すれば会計基準に依存せず値を取得できる抽象レイヤー」（FEATURES.md `standards/normalize`）の実現である。その根幹は、各会計基準の科目を**正規化キー（canonical key）**にマッピングすることにある。

本モジュールは J-GAAP 側のマッピングを担当する:

```
J-GAAP: jppfs_cor:NetSales           → canonical key "revenue"
IFRS:   jpigp_cor:Revenue (Lane 4)   → canonical key "revenue"
US-GAAP: (TextBlock のみ, Lane 5)     → N/A
```

### 依存関係

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl._namespaces` (Wave 1 L5) | `classify_namespace()`, `NamespaceInfo.module_group` | read-only |
| `edinet.models.financial.StatementType` | 財務諸表種類の Enum | read-only |
| `edinet.exceptions.EdinetWarning` | 警告カテゴリ | read-only |

他レーンとのファイル衝突なし（新規ファイルのみ作成）。

### レイヤー構造における位置

```
[構造レイヤー]                          [意味レイヤー]

concept_sets (Lane 1)                   standards/detect (Lane 2)
  "PL に属する 200 concept"                "この Filing は J-GAAP"
  "BS に属する 150 concept"                         │
           │                                        │
           │ (概念の構造的所属)                       │ (会計基準の判定)
           │                                        │
           └──────────────┐    ┌────────────────────┘
                          ▼    ▼
                   standards/normalize (Wave 3)
                     ├── standards/jgaap (本 Lane) ← 正規化マッピング
                     ├── standards/ifrs (Lane 4)
                     └── standards/usgaap (Lane 5)
                          │
                          ▼
                   「売上高」→ 値を返す（会計基準不問）
```

concept_sets (Lane 1) が **構造的に** どの concept がどの諸表に属するかを定義し、standards/jgaap が **意味的に** その concept が正規化キーの何に対応するかを定義する。両者は相補的であり重複しない。

### QA 参照

| QA | タイトル | 関連度 |
|----|---------|--------|
| D-3 | 会計基準の判別方法 | 関連（J-GAAP の名前空間判別） |
| E-5 | 業種別の財務諸表の差異 | 直接（J-GAAP 業種間の差異） |
| E-6 | 提出者独自の拡張科目 | 関連（標準/非標準の区別） |
| E-7 | 主要勘定科目の concept 名辞書 | **直接（マッピング設計の基盤）** |
| C-1 | タクソノミモジュール体系 | 関連（jppfs_cor の位置づけ） |
| H-3 | タクソノミバージョニング | 関連（バージョン非依存の設計） |

---

## 1. 背景知識

### 1.1 正規化マッピングとは

FEATURES.md `standards/normalize` の note より:

> 会計基準間マッピング（J-GAAP `jppfs_cor:NetSales` ↔ IFRS `ifrs-full:Revenue` 等）は公式データが存在せず手動定義が不可避。主要指標 50-100 程度のため一度作成すれば年次メンテは軽微

本モジュールは J-GAAP 側の「手動定義」を担う。正規化キーは会計基準間で共通の文字列識別子であり、normalize (Wave 3) が各基準のマッピングを突き合わせる。

### 1.2 J-GAAP の特徴（他会計基準との差異）

E-7, E-5 より J-GAAP は以下の特徴を持つ:

| 特徴 | J-GAAP | IFRS | US-GAAP |
|------|--------|------|---------|
| 経常利益 | **あり** (OrdinaryIncome) | なし | なし |
| 特別利益/特別損失 | **あり** | 限定的 | 限定的 |
| 表示区分 | 営業外収益/費用を明示 | 営業利益の定義が異なる | — |
| 純資産の呼称 | 純資産 (NetAssets) | 資本 (Equity) | Stockholders' Equity |
| PL 最下行 | 親会社株主に帰属する当期純利益 | 親会社の所有者に帰属する当期利益 | — |
| タグ付け詳細度 | DETAILED（個別勘定科目） | DETAILED | BLOCK_ONLY |
| 業種別 PL 構造 | 23 業種で異なる（E-5） | 業種差なし | — |

### 1.3 現行の手動 JSON（置換対象）

現在の `statements.py` は以下の JSON ファイルで J-GAAP 科目を定義:

| ファイル | concept 数 | 内容 |
|---------|-----------|------|
| `pl_jgaap.json` | 16 | 売上高〜非支配株主利益 |
| `bs_jgaap.json` | 20 | 流動資産〜負債純資産合計 |
| `cf_jgaap.json` | 8 | 営業CF〜現金期末残高 |

これらは「表示順序 + concept 名 + ラベルヒント」のみ。本モジュールが追加する付加価値:

1. **正規化キー**: 会計基準横断の一意識別子
2. **英語ラベル**: 国際化対応の基盤
3. **J-GAAP 固有フラグ**: 経常利益・特別損益等の識別
4. **階層情報**: 合計行・内訳の親子関係
5. **期間型**: instant / duration の明示
6. **型安全**: frozen dataclass による構造化

### 1.4 J-GAAP の名前空間モジュール

_namespaces.py の `module_group` 値に基づく:

| module_group | モジュール名 | 用途 |
|-------------|------------|------|
| `"jppfs"` | jppfs_cor | 財務諸表本表（PL/BS/CF/SS） |
| `"jpcrp"` | jpcrp_cor | 企業内容等開示（経営指標、DEI 以外のメタ情報） |
| `"jpdei"` | jpdei_cor | DEI（書類・企業情報） |

**注意**: IFRS 企業でも `jppfs` はディメンション要素等で併用される（D-1）。`jppfs` の存在だけでは J-GAAP と断定できない。会計基準の判別は `standards/detect` (Lane 2) の責務であり、本モジュールは「J-GAAP であることが確定した Filing」に対してマッピングを提供する。

### 1.5 concept の識別方式

本モジュールでは concept を**ローカル名**（例: `"NetSales"`）で識別する。

理由:
- `jppfs_cor` タクソノミのバージョン（2024-11-01, 2025-11-01 等）が名前空間 URI に含まれるため、Clark notation はバージョンごとに異なる値になる（H-3）
- ローカル名はバージョン間で安定している（バージョン間での concept リネームは deprecated/代替で管理される）
- 既存の JSON ファイル（`pl_jgaap.json` 等）もローカル名で定義している
- Wave 1 のリンクベースパーサー（L1/L2/L3）もローカル名を使用

ローカル名が `jppfs_cor` に属するかどうかの判定は、呼び出し側が `_namespaces.classify_namespace()` で行う前提とする。

---

## 2. ゴール

### 2.1 機能要件

1. **J-GAAP 主要科目の正規化マッピングを提供する**（50-70 科目）
   - PL: 売上高〜非支配株主利益（16 + α）
   - BS: 流動資産〜負債純資産合計（20 + α）
   - CF: 営業CF〜現金期末残高（8 + α）
   - その他: EPS/BPS/ROE 等の主要経営指標

2. **各マッピングに豊富なメタデータを付与する**
   - 正規化キー（`canonical_key`）: 会計基準横断の一意識別子
   - 日本語ラベル（`label_ja`）: 表示用
   - 英語ラベル（`label_en`）: 国際化用
   - 財務諸表種類（`statement_type`）: PL / BS / CF
   - 期間型（`period_type`）: `"instant"` / `"duration"`
   - J-GAAP 固有フラグ（`is_jgaap_specific`）: 他会計基準に対応概念がない場合
   - 合計行フラグ（`is_total`）: 合計・小計行
   - 表示順序（`display_order`）: 標準的な表示順

3. **検索・ルックアップ関数を提供する**
   - concept ローカル名 → マッピング情報
   - 正規化キー → concept ローカル名（逆引き）
   - 財務諸表種類ごとのマッピング一覧

4. **J-GAAP 名前空間の識別ヘルパーを提供する**
   - module_group が J-GAAP に属するか判定する便利関数

5. **現行 JSON との後方互換性を維持する**
   - `to_legacy_concept_list()` で現行 JSON と同一形式に変換可能

### 2.2 非ゴール（スコープ外）

| # | 内容 | 理由 |
|---|------|------|
| NG-1 | 会計基準の判別 | `standards/detect` (Lane 2) の責務 |
| NG-2 | 全 jppfs_cor concept の網羅的カタログ | concept_sets (Lane 1) が pres_tree から自動導出 |
| NG-3 | 提出者独自科目のマッピング | `taxonomy/custom_detection` (Phase 5) の責務 |
| NG-4 | statements.py の統合変更 | Wave 3 L1 (normalize + statements 統合) の責務 |
| NG-5 | IFRS / US-GAAP のマッピング | Lane 4, Lane 5 の責務 |
| NG-6 | 業種固有科目（銀行: 経常収益等） | Phase 4 (sector/*) の責務 |
| NG-7 | `__init__.py` の更新 | Wave 完了後の統合タスク |
| NG-8 | SS（株主資本等変動計算書）の科目マッピング | SS は 2 次元構造（行=資本項目、列=変動要因）を持ち（E-1c）、単純な concept→canonical_key マッピングでは表現できない。`statements/equity` (Phase 6) で別途設計 |
| NG-9 | CI（包括利益計算書）の科目マッピング | `statements/comprehensive_income` (Phase 6) で別途設計。将来の追加候補: `ComprehensiveIncome`, `OtherComprehensiveIncomeLossNetOfTax` 等 |

---

## 3. データモデル設計

### 3.1 ConceptMapping

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from edinet.models.financial import StatementType

PeriodType = Literal["instant", "duration"]
"""期間型。BS 科目は ``"instant"``、PL/CF 科目は ``"duration"``。"""


@dataclass(frozen=True, slots=True)
class ConceptMapping:
    """J-GAAP concept の正規化マッピング。

    1 つの jppfs_cor / jpcrp_cor concept について、正規化キーと
    メタデータを保持する。standards/normalize (Wave 3) が
    会計基準横断の統一アクセスを提供する際の入力データ。

    Attributes:
        concept: jppfs_cor / jpcrp_cor のローカル名
            （例: ``"NetSales"``）。
            バージョン非依存（H-3）。
        canonical_key: 正規化キー（例: ``"revenue"``）。
            会計基準間で共通の文字列識別子。
            IFRS の Revenue も同じ ``"revenue"`` キーにマッピングされる。
            小文字 snake_case。
        label_ja: 日本語ラベル（例: ``"売上高"``）。
            タクソノミの標準ラベルに準拠。
        label_en: 英語ラベル（例: ``"Net sales"``）。
        statement_type: 所属する財務諸表。PL / BS / CF。
            複数に属する場合は主たる所属先。
            主要経営指標（EPS 等）は None。
        period_type: 期間型。``"instant"`` or ``"duration"``。
            BS 科目は ``"instant"``、PL/CF 科目は ``"duration"``。
            ``Literal`` 型により IDE 補完・型チェッカーでの検証が可能。
        is_jgaap_specific: J-GAAP 固有の概念か。
            True の場合、IFRS / US-GAAP に直接対応する概念がない。
            例: 経常利益（OrdinaryIncome）、特別利益（ExtraordinaryIncome）。
        is_total: 合計・小計行か。
            True の場合、この科目は他の科目の集約結果として算出される。
            例: 売上総利益 = 売上高 - 売上原価、営業利益 = 売上総利益 - 販管費。
            Calculation Linkbase の親ノードに該当する科目。
        display_order: 標準的な表示順序。
            同一 statement_type 内での相対順序。1 始まり。
    """
    concept: str
    canonical_key: str
    label_ja: str
    label_en: str
    statement_type: StatementType | None
    period_type: PeriodType
    is_jgaap_specific: bool = False
    is_total: bool = False
    display_order: int = 0
```

### 3.2 JGAAPProfile

```python
@dataclass(frozen=True, slots=True)
class JGAAPProfile:
    """J-GAAP 会計基準のプロファイル（概要情報）。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に保持し、ディスパッチに使用する。

    Attributes:
        standard_id: 会計基準の識別子。``"japan_gaap"`` 固定。
        display_name_ja: 日本語表示名。
        display_name_en: 英語表示名。
        module_groups: この会計基準に関連する EDINET
            タクソノミモジュールグループの集合。
        canonical_key_count: 定義されている正規化キーの総数。
        has_ordinary_income: 経常利益の概念を持つか（J-GAAP 固有）。
        has_extraordinary_items: 特別利益/特別損失の概念を持つか。
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

## 4. 公開 API

### 4.1 ルックアップ関数

```python
def lookup(concept: str) -> ConceptMapping | None:
    """J-GAAP concept ローカル名からマッピング情報を取得する。

    Args:
        concept: jppfs_cor / jpcrp_cor のローカル名
            （例: ``"NetSales"``）。

    Returns:
        ConceptMapping。登録されていない concept の場合は None。
    """


def canonical_key(concept: str) -> str | None:
    """J-GAAP concept ローカル名を正規化キーにマッピングする。

    ``lookup()`` の簡易版。正規化キーのみを返す。

    Args:
        concept: jppfs_cor / jpcrp_cor のローカル名。

    Returns:
        正規化キー文字列。登録されていない concept の場合は None。
    """


def reverse_lookup(key: str) -> ConceptMapping | None:
    """正規化キーから J-GAAP の ConceptMapping を取得する（逆引き）。

    一般事業会社の主要科目に限定した 1:1 マッピング。
    銀行業・保険業等の業種固有科目は Phase 4 で sector/ モジュールとして
    別途マッピングされるため、本関数の対象外。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        ConceptMapping。該当する J-GAAP concept がない場合は None。
    """
```

### 4.2 一覧取得関数

```python
def mappings_for_statement(
    statement_type: StatementType,
) -> tuple[ConceptMapping, ...]:
    """指定した財務諸表タイプの J-GAAP マッピングを返す。

    display_order 順でソート済み。
    ``statement_type=None`` の ConceptMapping（主要経営指標）は
    本関数では取得できない。``all_mappings()`` を使用すること。

    Args:
        statement_type: PL / BS / CF。

    Returns:
        ConceptMapping のタプル（display_order 昇順）。
        未登録の StatementType の場合は空タプル。
    """


def all_mappings() -> tuple[ConceptMapping, ...]:
    """全ての J-GAAP マッピングを返す。

    PL → BS → CF → その他（statement_type=None）の順、
    各グループ内は display_order 昇順。

    Returns:
        全 ConceptMapping のタプル。
    """


def all_canonical_keys() -> frozenset[str]:
    """J-GAAP で定義されている全正規化キーの集合を返す。

    Returns:
        正規化キーのフローズンセット。
    """


def jgaap_specific_concepts() -> tuple[ConceptMapping, ...]:
    """J-GAAP 固有の概念（他会計基準に対応概念がないもの）を返す。

    対象科目: 営業外収益（NonOperatingIncome）、営業外費用（NonOperatingExpenses）、
    経常利益（OrdinaryIncome）、特別利益（ExtraordinaryIncome）、
    特別損失（ExtraordinaryLoss）。

    Returns:
        ``is_jgaap_specific=True`` の ConceptMapping のタプル。
    """
```

### 4.3 名前空間判定関数

```python
_JGAAP_MODULE_GROUPS: frozenset[str] = frozenset({"jppfs", "jpcrp", "jpdei"})


def is_jgaap_module(module_group: str) -> bool:
    """module_group が J-GAAP に属するかどうかを判定する。

    J-GAAP に関連するモジュールグループ: ``"jppfs"``, ``"jpcrp"``, ``"jpdei"``。

    注意: IFRS 企業でも jppfs はディメンション要素等で併用される
    ため（D-1）、この関数の結果だけで会計基準を断定してはならない。
    会計基準の判別は standards/detect (Lane 2) を使用すること。

    Args:
        module_group: _namespaces.classify_namespace() で取得した
            NamespaceInfo.module_group の値。

    Returns:
        J-GAAP に関連するモジュールグループであれば True。
    """
    return module_group in _JGAAP_MODULE_GROUPS
```

### 4.4 プロファイル取得関数

```python
def get_profile() -> JGAAPProfile:
    """J-GAAP 会計基準のプロファイルを返す。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に取得する際のエントリーポイント。

    Returns:
        JGAAPProfile。
    """
```

### 4.5 レガシー互換関数

```python
def to_legacy_concept_list(
    statement_type: StatementType,
) -> list[dict[str, object]]:
    """現行 JSON 互換のフォーマットに変換する。

    ``statements.py`` の ``_load_concept_definitions()`` が返す形式
    と同一:  ``[{"concept": str, "order": int, "label_hint": str}, ...]``

    Wave 3 L1 での ``statements.py`` 統合時に
    ``_load_concept_definitions()`` を段階的に置換するためのブリッジ。

    Args:
        statement_type: PL / BS / CF。

    Returns:
        JSON 互換のリスト。display_order 順。
    """
```

---

## 5. 正規化キー（canonical key）の設計

### 5.1 命名規則

- 小文字 snake_case
- 会計基準に依存しない中立的な名称
- IFRS の英語名を主に参考（ただし J-GAAP 固有概念は独自）
- 簡潔さと明確さのバランス

### 5.2 PL（損益計算書）の正規化キー

| # | concept (J-GAAP) | canonical_key | label_ja | label_en | is_jgaap_specific | is_total |
|---|-----------------|---------------|----------|----------|-------------------|----------|
| 1 | `NetSales` | `revenue` | 売上高 | Net sales | False | False |
| 2 | `CostOfSales` | `cost_of_sales` | 売上原価 | Cost of sales | False | False |
| 3 | `GrossProfit` | `gross_profit` | 売上総利益 | Gross profit | False | True |
| 4 | `SellingGeneralAndAdministrativeExpenses` | `sga_expenses` | 販売費及び一般管理費 | SGA expenses | False | False |
| 5 | `OperatingIncome` | `operating_income` | 営業利益又は営業損失（△） | Operating income (loss) | False | True |
| 6 | `NonOperatingIncome` | `non_operating_income` | 営業外収益 | Non-operating income | **True** | False |
| 7 | `NonOperatingExpenses` | `non_operating_expenses` | 営業外費用 | Non-operating expenses | **True** | False |
| 8 | `OrdinaryIncome` | `ordinary_income` | 経常利益又は経常損失（△） | Ordinary income (loss) | **True** | True |
| 9 | `ExtraordinaryIncome` | `extraordinary_income` | 特別利益 | Extraordinary income | **True** | False |
| 10 | `ExtraordinaryLoss` | `extraordinary_loss` | 特別損失 | Extraordinary loss | **True** | False |
| 11 | `IncomeBeforeIncomeTaxes` | `income_before_tax` | 税引前当期純利益又は税引前当期純損失（△） | Income before income taxes | False | True |
| 12 | `IncomeTaxes` | `income_taxes` | 法人税、住民税及び事業税 | Income taxes - current | False | False |
| 13 | `IncomeTaxesDeferred` | `income_taxes_deferred` | 法人税等調整額 | Income taxes - deferred | False | False |
| 14 | `ProfitLoss` | `net_income` | 当期純利益又は当期純損失（△） | Profit (loss) | False | True |
| 15 | `ProfitLossAttributableToOwnersOfParent` | `net_income_parent` | 親会社株主に帰属する当期純利益又は親会社株主に帰属する当期純損失（△） | Profit attributable to owners of parent | False | True |
| 16 | `ProfitLossAttributableToNonControllingInterests` | `net_income_minority` | 非支配株主に帰属する当期純利益又は非支配株主に帰属する当期純損失（△） | Profit attributable to non-controlling interests | False | False |

全 16 concept。period_type は全て `"duration"`。

### 5.3 BS（貸借対照表）の正規化キー

| # | concept (J-GAAP) | canonical_key | label_ja | label_en | is_total |
|---|-----------------|---------------|----------|----------|----------|
| 1 | `CurrentAssets` | `current_assets` | 流動資産 | Current assets | True |
| 2 | `NoncurrentAssets` | `noncurrent_assets` | 固定資産 | Non-current assets | True |
| 3 | `PropertyPlantAndEquipment` | `ppe` | 有形固定資産 | Property, plant and equipment | True |
| 4 | `IntangibleAssets` | `intangible_assets` | 無形固定資産 | Intangible assets | True |
| 5 | `InvestmentsAndOtherAssets` | `investments_and_other` | 投資その他の資産 | Investments and other assets | True |
| 6 | `DeferredAssets` | `deferred_assets` | 繰延資産 | Deferred assets | True |
| 7 | `Assets` | `total_assets` | 資産合計 | Total assets | True |
| 8 | `CurrentLiabilities` | `current_liabilities` | 流動負債 | Current liabilities | True |
| 9 | `NoncurrentLiabilities` | `noncurrent_liabilities` | 固定負債 | Non-current liabilities | True |
| 10 | `Liabilities` | `total_liabilities` | 負債合計 | Total liabilities | True |
| 11 | `CapitalStock` | `capital_stock` | 資本金 | Capital stock | False |
| 12 | `CapitalSurplus` | `capital_surplus` | 資本剰余金 | Capital surplus | False |
| 13 | `RetainedEarnings` | `retained_earnings` | 利益剰余金 | Retained earnings | False |
| 14 | `TreasuryStock` | `treasury_stock` | 自己株式 | Treasury stock | False |
| 15 | `ShareholdersEquity` | `shareholders_equity` | 株主資本合計 | Total shareholders' equity | True |
| 16 | `ValuationAndTranslationAdjustments` | `oci_accumulated` | その他の包括利益累計額 | Accumulated other comprehensive income | True |
| 17 | `SubscriptionRightsToShares` | `stock_options` | 新株予約権 | Stock acquisition rights | False |
| 18 | `NonControllingInterests` | `minority_interests` | 非支配株主持分 | Non-controlling interests | False |
| 19 | `NetAssets` | `net_assets` | 純資産合計 | Total net assets | True |
| 20 | `LiabilitiesAndNetAssets` | `liabilities_and_net_assets` | 負債純資産合計 | Total liabilities and net assets | True |

全 20 concept。period_type は全て `"instant"`。is_jgaap_specific は全て `False`（BS 構造は会計基準間で類似）。

### 5.4 CF（キャッシュフロー計算書）の正規化キー

| # | concept (J-GAAP) | canonical_key | label_ja | label_en | is_total |
|---|-----------------|---------------|----------|----------|----------|
| 1 | `NetCashProvidedByUsedInOperatingActivities` | `operating_cf` | 営業活動によるキャッシュ・フロー | Cash flows from operating activities | True |
| 2 | `NetCashProvidedByUsedInInvestmentActivities` | `investing_cf` | 投資活動によるキャッシュ・フロー | Cash flows from investing activities | True |
| 3 | `NetCashProvidedByUsedInFinancingActivities` | `financing_cf` | 財務活動によるキャッシュ・フロー | Cash flows from financing activities | True |
| 4 | `EffectOfExchangeRateChangeOnCashAndCashEquivalents` | `fx_effect_on_cash` | 現金及び現金同等物に係る換算差額 | Effect of exchange rate changes | False |
| 5 | `NetIncreaseDecreaseInCashAndCashEquivalents` | `net_change_in_cash` | 現金及び現金同等物の増減額（△は減少） | Net increase (decrease) in cash | True |
| 6 | `IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeInScopeOfConsolidation` | `consolidation_scope_change_cash` | 連結範囲の変動に伴う現金及び現金同等物の増減額 | Cash changes from consolidation scope | False |
| 7 | `CashAndCashEquivalentsAtBeginningOfPeriod` | `cash_beginning` | 現金及び現金同等物の期首残高 | Cash at beginning of period | False |
| 8 | `CashAndCashEquivalentsAtEndOfPeriod` | `cash_end` | 現金及び現金同等物の期末残高 | Cash at end of period | True |

全 8 concept。period_type は全て `"duration"`。is_jgaap_specific は全て `False`。

> **NOTE**: `CashAndCashEquivalentsAtBeginningOfPeriod` / `CashAndCashEquivalentsAtEndOfPeriod` は概念的には残高（instant）だが、EDINET XBRL では CF セクション全体が duration context で報告されるため `period_type="duration"` とする。実装時にもこの旨をコメントとして記載すること。

### 5.5 主要経営指標（statement_type=None）

PL/BS/CF に属さないが、`jpcrp_cor` や `jppfs_cor` で定義される主要経営指標:

| # | concept (jpcrp_cor / jppfs_cor) | canonical_key | label_ja | label_en | period_type |
|---|-------------------------------|---------------|----------|----------|-------------|
| 1 | `BasicEarningsLossPerShare` | `eps` | 1株当たり当期純利益 | Earnings per share - basic | duration |
| 2 | `DilutedEarningsPerShare` | `eps_diluted` | 潜在株式調整後1株当たり当期純利益 | Earnings per share - diluted | duration |
| 3 | `NetAssetsPerShare` | `bps` | 1株当たり純資産額 | Book value per share | instant |
| 4 | `DividendPerShare` | `dps` | 1株当たり配当額 | Dividend per share | duration |
| 5 | `EquityToAssetRatio` | `equity_ratio` | 自己資本比率 | Equity ratio | instant |
| 6 | `RateOfReturnOnEquity` | `roe` | 自己資本利益率 | Return on equity | duration |
| 7 | `PriceEarningsRatio` | `per` | 株価収益率 | Price earnings ratio | duration |
| 8 | `NumberOfEmployees` | `employees` | 従業員数 | Number of employees | instant |

全 8 concept。

### 5.6 合計

| カテゴリ | concept 数 |
|---------|-----------|
| PL | 16 |
| BS | 20 |
| CF | 8 |
| 主要経営指標 | 8 |
| **合計** | **52** |

FEATURES.md の「50-100 程度」の範囲内。将来的に追加が必要になった場合は `ConceptMapping` を追加するだけでよい。

### 5.7 正規化キーの Wave 2 並列レーン間合意

Lane 3 (J-GAAP), Lane 4 (IFRS), Lane 5 (US-GAAP) が並列実装されるため、正規化キーの文字列値を**計画レベルで合意する**必要がある。**本計画書（Lane 3）で定義した正規化キー（§5.2-5.5）が権威的リファレンスであり、Lane 4 / Lane 5 はこれに準拠する。**

#### 現状の不整合と解消方針

他レーンの計画を確認した結果、以下の不整合が確認されている:

| 問題 | Lane 3 (本計画) | Lane 4 (IFRS) | Lane 5 (US-GAAP) |
|------|----------------|---------------|------------------|
| canonical_key フィールド | `ConceptMapping.canonical_key` | **canonical_key フィールドなし**（`IFRSMapping` は直接マッピング方式） | `_SummaryConceptDef.key`（同等だが命名が異なる） |
| 売上高のキー名 | `"revenue"` | — | **`"revenues"`**（複数形で不一致） |
| ルックアップ API | `lookup(concept)` → `ConceptMapping` | `ifrs_to_jgaap_map()` → 辞書 | `get_item(key)` → `USGAAPSummaryItem` |

**解消方針（案 A を採用: Lane 3 の canonical key を全レーンの共通契約とする）**:

1. **Lane 4 への要求**: `IFRSMapping` または `IFRSConceptDef` に `canonical_key: str` フィールドを追加し、本計画の §5.2-5.5 のキー値を使用する
2. **Lane 5 への要求**: `_SummaryConceptDef.key` の値を本計画と統一する（`"revenues"` → `"revenue"` 等）
3. **Wave 3 L1 (normalize)** が全レーンの canonical key を突き合わせる際に最終調整を行う。本計画のキー値が変更される可能性はあるが、その場合は normalize が一括で変更する

#### Lane 5 との整合性の重要度

Lane 5 は包括タグ付けのみ（`DetailLevel.BLOCK_ONLY`）のため、normalize の構造化パースパスでは使用されない。canonical key の整合性は Wave 3 統合時に最終調整すれば足り、Lane 3 の実装をブロックしない。

#### canonical key の命名規則（全レーン共通）

- 小文字 snake_case
- **単数形**（`"revenue"` であり `"revenues"` ではない）
- 会計基準に依存しない中立的な名称
- IFRS の英語名を主に参考（ただし J-GAAP 固有概念は独自）

---

## 6. 内部実装の方針

### 6.1 マッピングレジストリ

全マッピングをモジュールレベルのタプルとして定義する:

```python
_PL_MAPPINGS: tuple[ConceptMapping, ...] = (
    ConceptMapping(
        concept="NetSales",
        canonical_key="revenue",
        label_ja="売上高",
        label_en="Net sales",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=1,
    ),
    ConceptMapping(
        concept="CostOfSales",
        canonical_key="cost_of_sales",
        label_ja="売上原価",
        label_en="Cost of sales",
        statement_type=StatementType.INCOME_STATEMENT,
        period_type="duration",
        display_order=2,
    ),
    # ... 全 16 概念
)

_BS_MAPPINGS: tuple[ConceptMapping, ...] = (...)  # 全 20 概念
_CF_MAPPINGS: tuple[ConceptMapping, ...] = (...)  # 全 8 概念
_KPI_MAPPINGS: tuple[ConceptMapping, ...] = (...)  # 全 8 概念

_ALL_MAPPINGS: tuple[ConceptMapping, ...] = (
    *_PL_MAPPINGS, *_BS_MAPPINGS, *_CF_MAPPINGS, *_KPI_MAPPINGS,
)
```

### 6.2 インデックス辞書

ルックアップ性能を確保するため、モジュールロード時にインデックスを構築する:

```python
# concept ローカル名 → ConceptMapping
_CONCEPT_INDEX: dict[str, ConceptMapping] = {
    m.concept: m for m in _ALL_MAPPINGS
}

# canonical_key → ConceptMapping（逆引き）
_CANONICAL_INDEX: dict[str, ConceptMapping] = {
    m.canonical_key: m for m in _ALL_MAPPINGS
}

# statement_type → tuple[ConceptMapping, ...]
_STATEMENT_INDEX: dict[StatementType, tuple[ConceptMapping, ...]] = {
    StatementType.INCOME_STATEMENT: _PL_MAPPINGS,
    StatementType.BALANCE_SHEET: _BS_MAPPINGS,
    StatementType.CASH_FLOW_STATEMENT: _CF_MAPPINGS,
}
```

### 6.3 整合性検証

モジュールロード時に以下を検証する。`assert` ではなく検証関数を使用し、`python -O`（最適化モード）でも検証がスキップされないようにする:

```python
def _validate_registry() -> None:
    """マッピングレジストリの整合性を検証する。

    モジュールロード時に自動実行される。
    """
    # 1. concept ローカル名がユニーク
    if len(_CONCEPT_INDEX) != len(_ALL_MAPPINGS):
        raise ValueError("concept ローカル名に重複があります")

    # 2. canonical_key がユニーク
    if len(_CANONICAL_INDEX) != len(_ALL_MAPPINGS):
        raise ValueError("canonical_key に重複があります")

    # 3. display_order が各 statement_type 内でユニーク
    for st, mappings in _STATEMENT_INDEX.items():
        orders = [m.display_order for m in mappings]
        if len(set(orders)) != len(orders):
            raise ValueError(f"{st.value} の display_order に重複があります")

    # 4. period_type の値が "instant" or "duration" のみ
    valid_period_types = {"instant", "duration"}
    for m in _ALL_MAPPINGS:
        if m.period_type not in valid_period_types:
            raise ValueError(
                f"{m.concept} の period_type が不正です: {m.period_type!r}"
            )


_validate_registry()
```

`assert` ではなく `ValueError` を使用する理由: ディファクトスタンダードなライブラリでは、ユーザーが `python -O`（Docker の本番イメージ等）で実行するケースがある。`assert` は最適化モードでスキップされるが、`ValueError` は常に実行される。52 エントリの検証コストは無視可能。

### 6.4 JGAAPProfile の構築

```python
_PROFILE = JGAAPProfile(
    standard_id="japan_gaap",
    display_name_ja="日本基準",
    display_name_en="Japan GAAP",
    module_groups=_JGAAP_MODULE_GROUPS,
    canonical_key_count=len(_ALL_MAPPINGS),
    has_ordinary_income=True,
    has_extraordinary_items=True,
)
```

### 6.5 to_legacy_concept_list の実装

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

**検証**: `to_legacy_concept_list(StatementType.INCOME_STATEMENT)` の出力が `pl_jgaap.json` の内容と一致することをテストで確認する。

---

## 7. ファイル構成

### 作成ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/standards/jgaap.py` | 新規 | `ConceptMapping` / `JGAAPProfile` dataclass, マッピングレジストリ, ルックアップ関数, 名前空間判定関数 |
| `tests/test_xbrl/test_standards_jgaap.py` | 新規 | 単体テスト |

### `src/edinet/xbrl/standards/jgaap.py` の構成

```
jgaap.py
├── __all__
├── PeriodType (Literal["instant", "duration"])  # 期間型エイリアス
├── ConceptMapping(frozen dataclass)      # マッピング型
├── JGAAPProfile(frozen dataclass)        # プロファイル型
├── _JGAAP_MODULE_GROUPS                  # 名前空間判定用定数
├── _PL_MAPPINGS, _BS_MAPPINGS, etc.      # マッピングレジストリ
├── _ALL_MAPPINGS                         # 全マッピングの結合
├── _CONCEPT_INDEX, _CANONICAL_INDEX      # インデックス辞書
├── _STATEMENT_INDEX                      # 諸表別インデックス
├── assert (整合性検証)                    # ロード時アサーション
├── _PROFILE                              # プロファイルインスタンス
├── lookup()                              # concept → ConceptMapping
├── canonical_key()                       # concept → canonical_key
├── reverse_lookup()                      # canonical_key → ConceptMapping
├── mappings_for_statement()              # StatementType → 一覧
├── all_mappings()                        # 全マッピング一覧
├── all_canonical_keys()                  # 全正規化キーの集合
├── jgaap_specific_concepts()             # J-GAAP 固有概念
├── is_jgaap_module()                     # module_group 判定
├── get_profile()                         # プロファイル取得
└── to_legacy_concept_list()              # レガシー互換変換
```

### `__all__` 定義

```python
__all__ = [
    "PeriodType",
    "ConceptMapping",
    "JGAAPProfile",
    "lookup",
    "canonical_key",
    "reverse_lookup",
    "mappings_for_statement",
    "all_mappings",
    "all_canonical_keys",
    "jgaap_specific_concepts",
    "is_jgaap_module",
    "get_profile",
    "to_legacy_concept_list",
]
```

---

## 8. テスト計画

### 8.1 テスト方針

- **Detroit 派**: 内部実装に依存せず公開 API の入出力でテスト
- テストフィクスチャは不要（マッピングデータはモジュール内に定義済み）
- `RawFact` を構築してパースする必要もない（マッピングは静的データ）
- 既存の `pl_jgaap.json`, `bs_jgaap.json`, `cf_jgaap.json` との互換性を重点的に検証

### 8.2 テストケース

#### P0（必須）— マッピングの基本動作

| # | テスト名 | 概要 |
|---|---------|------|
| T1 | `test_lookup_net_sales` | `lookup("NetSales")` → `ConceptMapping(canonical_key="revenue", ...)` |
| T2 | `test_lookup_operating_income` | `lookup("OperatingIncome")` → `canonical_key="operating_income"` |
| T3 | `test_lookup_unknown_returns_none` | `lookup("UnknownConcept")` → `None` |
| T4 | `test_canonical_key_returns_string` | `canonical_key("NetSales")` → `"revenue"` |
| T5 | `test_canonical_key_unknown_returns_none` | `canonical_key("Unknown")` → `None` |
| T6 | `test_reverse_lookup_revenue` | `reverse_lookup("revenue")` → `ConceptMapping(concept="NetSales", ...)` |
| T7 | `test_reverse_lookup_unknown_returns_none` | `reverse_lookup("unknown_key")` → `None` |

#### P0 — 一覧取得

| # | テスト名 | 概要 |
|---|---------|------|
| T8 | `test_mappings_for_pl` | `mappings_for_statement(PL)` → 16 件 |
| T9 | `test_mappings_for_bs` | `mappings_for_statement(BS)` → 20 件 |
| T10 | `test_mappings_for_cf` | `mappings_for_statement(CF)` → 8 件 |
| T11 | `test_all_mappings_count` | `all_mappings()` → 52 件 |
| T12 | `test_all_canonical_keys_unique` | `all_canonical_keys()` → 52 個のユニークなキー |
| T13 | `test_mappings_sorted_by_display_order` | `mappings_for_statement(PL)` が display_order 昇順 |

#### P0 — J-GAAP 固有概念

| # | テスト名 | 概要 |
|---|---------|------|
| T14 | `test_ordinary_income_is_jgaap_specific` | `lookup("OrdinaryIncome").is_jgaap_specific` → `True` |
| T15 | `test_net_sales_is_not_jgaap_specific` | `lookup("NetSales").is_jgaap_specific` → `False` |
| T16 | `test_jgaap_specific_concepts_includes_ordinary_income` | `jgaap_specific_concepts()` に `OrdinaryIncome` が含まれる |
| T17 | `test_jgaap_specific_count` | `jgaap_specific_concepts()` → 5 件（NonOperatingIncome/Expenses, OrdinaryIncome, ExtraordinaryIncome/Loss） |

#### P0 — レガシー互換

| # | テスト名 | 概要 |
|---|---------|------|
| T18 | `test_legacy_pl_matches_json` | `to_legacy_concept_list(PL)` の concept 一覧が `pl_jgaap.json` と完全一致 |
| T19 | `test_legacy_bs_matches_json` | `to_legacy_concept_list(BS)` の concept 一覧が `bs_jgaap.json` と完全一致 |
| T20 | `test_legacy_cf_matches_json` | `to_legacy_concept_list(CF)` の concept 一覧が `cf_jgaap.json` と完全一致 |
| T21 | `test_legacy_format_structure` | `to_legacy_concept_list()` の各要素が `{"concept": str, "order": int, "label_hint": str}` 構造 |
| T22 | `test_legacy_order_sequential` | `to_legacy_concept_list(PL)` の order が 1 始まりの連番 |

#### P0 — 名前空間判定

| # | テスト名 | 概要 |
|---|---------|------|
| T23 | `test_is_jgaap_module_jppfs` | `is_jgaap_module("jppfs")` → `True` |
| T24 | `test_is_jgaap_module_jpcrp` | `is_jgaap_module("jpcrp")` → `True` |
| T25 | `test_is_jgaap_module_jpigp` | `is_jgaap_module("jpigp")` → `False`（IFRS） |
| T26 | `test_is_jgaap_module_unknown` | `is_jgaap_module("unknown")` → `False` |

#### P0 — プロファイル

| # | テスト名 | 概要 |
|---|---------|------|
| T27 | `test_profile_standard_id` | `get_profile().standard_id` → `"japan_gaap"` |
| T28 | `test_profile_has_ordinary_income` | `get_profile().has_ordinary_income` → `True` |
| T29 | `test_profile_canonical_key_count` | `get_profile().canonical_key_count` → `52` |

#### P1（推奨）— データ整合性

| # | テスト名 | 概要 |
|---|---------|------|
| T30 | `test_all_concepts_unique` | 全 concept ローカル名がユニーク |
| T31 | `test_all_canonical_keys_not_empty` | 全 canonical_key が空文字列でない |
| T32 | `test_period_type_bs_is_instant` | BS の全 mapping が `period_type="instant"` |
| T33 | `test_period_type_pl_is_duration` | PL の全 mapping が `period_type="duration"` |
| T34 | `test_period_type_cf_is_duration` | CF の全 mapping が `period_type="duration"` |
| T35 | `test_concept_mapping_frozen` | `ConceptMapping` が frozen dataclass |
| T36 | `test_profile_frozen` | `JGAAPProfile` が frozen dataclass |
| T37 | `test_all_mappings_have_labels` | 全 mapping の `label_ja` / `label_en` が空文字列でない |
| T38 | `test_display_order_unique_per_statement` | 各 statement_type 内で display_order がユニーク |
| T39 | `test_kpi_statement_type_is_none` | 主要経営指標の `statement_type` が `None` |

#### P1 — 順序保証

| # | テスト名 | 概要 |
|---|---------|------|
| T40 | `test_all_mappings_order` | `all_mappings()` が PL → BS → CF → KPI の順で返されることを検証 |

合計: 40 テスト

### 8.3 レガシー互換テストの詳細

T18〜T20 は、実際の JSON ファイルを読み込んで比較する:

```python
import json
from pathlib import Path

def test_legacy_pl_matches_json(self):
    """to_legacy_concept_list(PL) の concept 一覧が pl_jgaap.json と完全一致。"""
    json_path = Path(__file__).parent.parent.parent / "src" / "edinet" / "xbrl" / "data" / "pl_jgaap.json"
    with open(json_path) as f:
        expected = json.load(f)

    result = to_legacy_concept_list(StatementType.INCOME_STATEMENT)

    # concept 名の一致を検証
    expected_concepts = [e["concept"] for e in expected]
    result_concepts = [r["concept"] for r in result]
    assert result_concepts == expected_concepts

    # order 値の一致を検証
    expected_orders = [e["order"] for e in expected]
    result_orders = [r["order"] for r in result]
    assert result_orders == expected_orders

    # label_hint の一致を検証（C-2 フィードバック対応）
    expected_hints = [e["label_hint"] for e in expected]
    result_hints = [r["label_hint"] for r in result]
    assert result_hints == expected_hints
```

この互換性テストにより、本モジュールが既存の JSON ファイルの**完全な上位互換**であることを保証する。concept 名・order 値・label_hint の 3 フィールド全てで完全一致を検証する。

> **推奨**: JSON ファイルのパス解決は `Path(__file__).parent...` でも動作するが、`importlib.resources` を使用する方が堅牢（テストディレクトリ構造の変更に耐性がある）。実装者の判断に委ねる。

---

## 9. 設計判断の記録

### Q1: なぜ正規化キーを Enum ではなく文字列にするか？

**A**: Lane 3 (J-GAAP), Lane 4 (IFRS), Lane 5 (US-GAAP) が並列実装されるため、共通の Enum を定義する場所がない（`__init__.py` は変更禁止、新ファイルの作成も Wave 内の制約がある）。文字列を使用し、計画書レベルでキー値を合意する。normalize (Wave 3) が全キーの公式レジストリを定義する際に Enum 化を検討する。

### Q2: なぜ concept_sets (Lane 1) と役割が重複しないのか？

**A**: concept_sets は **構造的分類**（pres_tree の role URI から「この concept は PL に属する」を機械的に導出）を担い、本モジュールは **意味的マッピング**（「NetSales は会計基準横断で revenue に対応する」という人間の知識のコード化）を担う。concept_sets は ~200 concept を構造的に網羅し、本モジュールは ~50 の主要概念に意味的メタデータを付与する。

| | concept_sets (Lane 1) | standards/jgaap (本 Lane) |
|---|---|---|
| データソース | pres_tree（XML 自動導出） | 手動定義（人間の会計知識） |
| カバー範囲 | 全 concept（200+） | 主要 concept（52） |
| メタデータ | 表示順序、depth、is_abstract | canonical_key、ラベル、J-GAAP 固有フラグ |
| 用途 | statements.py の概念フィルタ | normalize の会計基準横断マッピング |

### Q3: なぜ 52 concept なのか？ もっと増やすべきか？

**A**: FEATURES.md が「主要指標 50-100 程度」と定義しており、52 はその下限に近い。現行の JSON（PL: 16, BS: 20, CF: 8 = 44 concept）に主要経営指標（8 concept）を追加した構成。必要に応じて以下を追加候補とするが、v0.1.0 では YAGNI:

- BS 詳細科目: `CashAndDeposits`, `NotesAndAccountsReceivableTrade`, `Inventories` 等
- PL 詳細科目: `InterestIncome`, `InterestExpenses` 等
- CF 内訳: `DepreciationAndAmortization` 等

追加は `_PL_MAPPINGS` 等に `ConceptMapping` を追加するだけでよく、API 変更は不要。

### Q4: `is_jgaap_module("jpigp")` が False なのはなぜか？

**A**: `jpigp` は IFRS 適用企業のためのタクソノミモジュールグループ（D-1: "EDINET では IASB の ifrs-full は使用されない。独自の jpigp_cor が使われる"）。J-GAAP 企業は `jpigp` を使用しないため、`is_jgaap_module()` では `False` を返す。

### Q5: statement_type=None の主要経営指標は必要か？

**A**: EPS/BPS/ROE 等は PL/BS/CF のいずれにも直接属さないが、`jpcrp_cor:SummaryOfBusinessResults` セクションで頻出する主要指標。normalize (Wave 3) が「ROE を取得」のようなクエリに応答するために必要。`statement_type=None` とすることで、PL/BS/CF の一覧取得（`mappings_for_statement()`）からは除外されるが、`lookup("EquityToAssetRatio")` で個別取得可能。

### Q6: `to_legacy_concept_list()` はなぜ必要か？

**A**: Wave 3 L1 での `statements.py` 統合時に、`_load_concept_definitions()` を段階的に置換するための**移行ブリッジ**。既存のテスト（`test_statements.py`）を壊さずに、JSON → jgaap.py への切り替えを行える:

```python
# Before (v0.1.0):
concept_defs = _load_concept_definitions(StatementType.INCOME_STATEMENT)

# After (v0.2.0, Step 1 — ブリッジ):
from edinet.financial.standards.jgaap import to_legacy_concept_list
concept_defs = to_legacy_concept_list(StatementType.INCOME_STATEMENT)

# After (v0.2.0, Step 2 — 完全移行):
from edinet.financial.standards.jgaap import mappings_for_statement
mappings = mappings_for_statement(StatementType.INCOME_STATEMENT)
```

### Q7: ロード時の整合性検証は適切か？

**A**: Python のベストプラクティスとして、定数データの整合性検証にはロード時検証が適切。テストでの検証（P1 テスト T30, T38）も行うが、ロード時検証はテスト実行外でも保護を提供する。`python -O`（最適化モード）でもスキップされないよう、`assert` ではなく `ValueError` を使用する検証関数方式を採用（§6.3 参照）。

### Q8: 各レーンの Profile 型は共通インターフェースを持つべきか？

**A**: Wave 3 normalize が定義する `AccountingStandardProfile` Protocol に準拠することで統一する。現時点では各レーンが独自の Profile 型を定義し、Wave 3 で共通フィールド（`standard_id`, `display_name_ja`, `display_name_en`, `canonical_key_count`）を Protocol として切り出す。Lane 4 (IFRS) / Lane 5 (US-GAAP) の計画には Profile 型が定義されていないが、Wave 3 統合時に追加される想定。`JGAAPProfile` の J-GAAP 固有フィールド（`has_ordinary_income`, `has_extraordinary_items`）は Protocol の共通フィールドには含まれず、J-GAAP 固有のアクセスパスで取得する。

### Q9: `ConceptMapping` と `IFRSConceptMapping` を統一すべきか？

**A**: 現時点では各レーンが独自の型を定義する。理由:
1. `is_jgaap_specific` / `is_ifrs_specific` は会計基準固有のセマンティクスを持ち、単一フラグに統合すると意味が曖昧になる
2. 並列実装の制約上、共通型の定義場所がない（`__init__.py` 変更禁止）
3. Wave 3 normalize で共通 Protocol（`canonical_key`, `concept`, `label_ja`, `statement_type` を持つ型）を定義すれば、Union 型を避けつつ両方を統一的に扱える

**Wave 3 での解決策**: `CanonicalMapping` Protocol を定義し、`ConceptMapping` と `IFRSConceptMapping` の両方がこれを満たすことで、normalize は Protocol 型のみを扱う。

---

## 10. 後続レーンとの接続点

### Wave 2 Lane 4 (standards/ifrs) との関係

Lane 4 は IFRS の科目を同じ正規化キー（`"revenue"`, `"operating_income"` 等）にマッピングする。Lane 3 と Lane 4 は並列実装であり依存関係はないが、正規化キーの文字列値を計画レベルで合意する。

IFRS で対応する概念がない正規化キー（`"ordinary_income"`, `"extraordinary_income"` 等）は Lane 4 のマッピングに含まれない。normalize (Wave 3) はマッピング不在を「該当なし」として扱う。

### Wave 2 Lane 5 (standards/usgaap) との関係

US-GAAP は包括タグ付けのみ（`DetailLevel.BLOCK_ONLY`）のため、Lane 5 のマッピングは非常に少数（`SummaryOfBusinessResults` 内の項目のみ）。正規化キーの共有は限定的。

### Wave 3 L1 (normalize + statements 統合) での使用

```python
# normalize.py (Wave 3) での使用例
from edinet.financial.standards import jgaap, ifrs, usgaap
from edinet.financial.standards.detect import detect_accounting_standard, DetailLevel
from edinet.xbrl.dei import AccountingStandard

def normalize_concept(concept: str, standard: AccountingStandard) -> str | None:
    """concept ローカル名を正規化キーにマッピングする。"""
    if standard == AccountingStandard.JAPAN_GAAP:
        return jgaap.canonical_key(concept)
    elif standard == AccountingStandard.IFRS:
        return ifrs.canonical_key(concept)
    elif standard == AccountingStandard.US_GAAP:
        return usgaap.canonical_key(concept)
    return None


def get_value(filing, key: str) -> Decimal | None:
    """正規化キーで値を取得する。会計基準を問わない。"""
    detected = detect_accounting_standard(filing.facts)

    if detected.detail_level == DetailLevel.BLOCK_ONLY:
        return None  # US-GAAP/JMIS は構造化パース不可

    if detected.standard == AccountingStandard.JAPAN_GAAP:
        mapping = jgaap.reverse_lookup(key)
    elif detected.standard == AccountingStandard.IFRS:
        mapping = ifrs.reverse_lookup(key)
    else:
        return None

    if mapping is None:
        return None

    # mapping.concept を使って LineItem から値を検索
    ...
```

### JSON 全廃のロードマップ

```
v0.1.0 (現在): pl_jgaap.json 等が直接使用されている
     ↓
Wave 2 L3:     jgaap.py が同じデータを型安全に提供
     ↓
Wave 3 L1:     statements.py が jgaap.to_legacy_concept_list() を呼ぶ
               （JSON ファイルへの直接参照を削除）
     ↓
Wave 3+:       to_legacy_concept_list() を廃止し、
               ConceptMapping を直接使用する完全移行
     ↓
最終:          pl_jgaap.json 等の JSON ファイルを削除
```

---

## 11. 実行チェックリスト

### Phase 1: 実装（推定 40 分）

1. `src/edinet/xbrl/standards/jgaap.py` を新規作成
   - `ConceptMapping` / `JGAAPProfile` frozen dataclass 定義
   - `_PL_MAPPINGS` / `_BS_MAPPINGS` / `_CF_MAPPINGS` / `_KPI_MAPPINGS` 定義（§5.2-5.5 の全 52 concept）
   - `_ALL_MAPPINGS` 結合
   - `_CONCEPT_INDEX` / `_CANONICAL_INDEX` / `_STATEMENT_INDEX` 構築
   - `_validate_registry()` 整合性検証関数（ユニーク性検証、`python -O` 耐性）
   - `lookup()` / `canonical_key()` / `reverse_lookup()` 実装
   - `mappings_for_statement()` / `all_mappings()` / `all_canonical_keys()` / `jgaap_specific_concepts()` 実装
   - `is_jgaap_module()` 実装
   - `get_profile()` 実装
   - `to_legacy_concept_list()` 実装
   - `__all__` 定義

### Phase 2: テスト（推定 30 分）

2. `tests/test_xbrl/test_standards_jgaap.py` を新規作成
   - P0 テスト（T1〜T29）を全て実装
   - P1 テスト（T30〜T39）を全て実装
   - レガシー互換テスト（T18〜T20）で実際の JSON ファイルを読み込み比較

### Phase 3: 検証（推定 10 分）

3. `uv run ruff check src/edinet/xbrl/standards/jgaap.py tests/test_xbrl/test_standards_jgaap.py` — Lint チェック
4. `uv run pytest tests/test_xbrl/test_standards_jgaap.py -v` — jgaap テストのみ実行
5. `uv run pytest` — 全テスト実行（既存テストを壊していないことを確認）

### 完了条件

- [ ] 全 52 concept の ConceptMapping が定義済み
- [ ] `lookup()` が登録済み concept に対して正しい ConceptMapping を返す
- [ ] `canonical_key()` が正規化キー文字列を返す
- [ ] `reverse_lookup()` が逆引きに対応する
- [ ] `mappings_for_statement()` が PL: 16, BS: 20, CF: 8 件を返す
- [ ] `all_canonical_keys()` が 52 個のユニークなキーを返す
- [ ] `jgaap_specific_concepts()` が 5 件（NonOperatingIncome/Expenses, OrdinaryIncome, ExtraordinaryIncome/Loss）を返す
- [ ] `is_jgaap_module()` が jppfs/jpcrp/jpdei で True、jpigp で False を返す
- [ ] `get_profile()` が正しい JGAAPProfile を返す
- [ ] `to_legacy_concept_list(PL)` が `pl_jgaap.json` と完全互換（concept, order, label_hint の 3 フィールド全て一致）
- [ ] `to_legacy_concept_list(BS)` が `bs_jgaap.json` と完全互換（同上）
- [ ] `to_legacy_concept_list(CF)` が `cf_jgaap.json` と完全互換（同上）
- [ ] 全 ConceptMapping が frozen dataclass
- [ ] PL の全 mapping が `period_type="duration"`
- [ ] BS の全 mapping が `period_type="instant"`
- [ ] P0 テスト全件 PASS
- [ ] P1 テスト全件 PASS
- [ ] 既存テスト全件 PASS
- [ ] ruff Clean

---

## 変更ログ（フィードバック反映）

### Rev.1 (2026-02-28) — WAVE_2_LANE_3_FEEDBACK.md の反映

全フィードバック項目を妥当と判断し、以下を修正。

| # | FB ID | 優先度 | 変更箇所 | 変更内容 |
|---|-------|--------|----------|----------|
| 1 | C-1 | CRITICAL | §5.7 | canonical key の全レーン合意セクションを大幅強化。Lane 3 の canonical key を「権威的リファレンス」として位置づけ、Lane 4/5 との具体的な不整合と解消方針（案 A 採用）を明記。命名規則（単数形・snake_case）を全レーン共通として定義 |
| 2 | C-2 | CRITICAL | §5.2 | PL 2 concept の `label_ja` を既存 JSON の `label_hint` と完全一致するよう修正。`ProfitLossAttributableToOwnersOfParent`: 「親会社株主に帰属する当期純利益」→「親会社株主に帰属する当期純利益又は親会社株主に帰属する当期純損失（△）」。`ProfitLossAttributableToNonControllingInterests` も同様 |
| 3 | H-1 | HIGH | §5.4 | CF の `period_type` について NOTE を追加。期首/期末残高が概念的 instant だが EDINET 上 duration である事実を明記 |
| 4 | H-2 | HIGH | §4.1 | `reverse_lookup()` の docstring を変更。1:1 前提が一般事業会社に限定されること、業種固有科目は Phase 4 sector/ で別途マッピングされることを明記 |
| 5 | H-3 | HIGH | §9 | 設計判断 Q8 を追加。各レーンの Profile 型の共通インターフェースについて、Wave 3 normalize が Protocol として切り出す方針を記録 |
| 6 | M-1 | MEDIUM | §2.2 | 非ゴール NG-8 を追加: SS（株主資本等変動計算書）の科目マッピングがスコープ外である理由（2 次元構造、Phase 6 で対応） |
| 7 | M-2 | MEDIUM | §2.2 | 非ゴール NG-9 を追加: CI（包括利益計算書）の科目マッピングがスコープ外である理由（Phase 6 で対応）。将来の追加候補も記載 |
| 8 | M-3 | MEDIUM | §6.3 | モジュールロード時の `assert` を `_validate_registry()` 検証関数に置換。`python -O` でもスキップされない `ValueError` 方式を採用 |
| 9 | M-4 | MEDIUM | §8.3 | レガシー互換テスト T18-T20 のコード例に `label_hint` の一致検証を追加。concept, order, label_hint の 3 フィールド全てで完全一致を保証 |
| 10 | M-5 | MEDIUM | §4.3 | `is_jgaap_module()` の docstring にモジュールグループの具体値（`"jppfs"`, `"jpcrp"`, `"jpdei"`）を列挙 |
| 11 | L-2 | LOW | §4.2 | `mappings_for_statement()` の docstring に `statement_type=None` の ConceptMapping（主要経営指標）は本関数で取得できない旨を追記 |
| 12 | — | — | §11 | 実行チェックリストの「整合性 assert」→「`_validate_registry()` 整合性検証関数」に修正。完了条件の JSON 互換性チェックに label_hint を追加 |
| 13 | — | — | §9 Q7 | Q7 の回答を `_validate_registry()` 方式に合わせて更新 |

### 未対応（対応不要と判断）

| FB ID | 優先度 | 理由 |
|-------|--------|------|
| L-1 | LOW | `canonical_key()` は最頻出ユーティリティであり短い名前の方が開発者体験が良い。現状維持 |
| L-3 | LOW | `display_order` のスコープは §3.1 の docstring で「同一 statement_type 内での相対順序」と記載済み。追加の明記は不要 |
| L-4 | LOW | テスト数 39 は適切。個別テスト名が明確な方がデバッグ時に有利。parametrize 化は実装者の判断に委ねる |

### Rev.2 (2026-02-28) — WAVE_2_LANE_3_FEEDBACK.md Rev.2 の反映

フィードバック Rev.2 の全項目の妥当性を判断し、以下を修正。

| # | FB ID | 優先度 | 判定 | 変更箇所 | 変更内容 |
|---|-------|--------|------|----------|----------|
| 1 | H-1 | HIGH | 妥当・採用 | §5.7 | 「Lane 5 との整合性の重要度」セクションを追加。US-GAAP は BLOCK_ONLY のため Lane 3 をブロックしない旨を明記 |
| 2 | H-2 | HIGH | 妥当・採用 | §9 | 設計判断 Q9 を追加。`ConceptMapping` と `IFRSConceptMapping` の型分離について、Wave 3 で `CanonicalMapping` Protocol による統一を方針として記録 |
| 3 | M-1 | MEDIUM | 妥当・採用 | §3.1, §6.3, §7 | `period_type: str` → `period_type: PeriodType`（`Literal["instant", "duration"]`）に変更。`PeriodType` 型エイリアスを追加。`_validate_registry()` に `period_type` 値検証を追加。`__all__` に `PeriodType` を追加 |
| 4 | M-2 | MEDIUM | 妥当・採用 | §8.2 | テストケース T40 `test_all_mappings_order` を追加（PL → BS → CF → KPI の順序検証）。テスト総数 39 → 40 |
| 5 | M-3 | MEDIUM | 妥当・採用 | §3.1 | `is_total` の docstring を補強。「他の科目の集約結果」「Calculation Linkbase の親ノード」との関係を明記 |
| 6 | L-1 | LOW | 妥当・推奨に留める | §8.3 | `importlib.resources` の使用を推奨する NOTE を追記。ただし実装者の判断に委ねる |
| 7 | L-2 | LOW | 対応不要（合意） | — | フィードバック自身が対応不要と述べている |
| 8 | L-3 | LOW | 妥当・採用 | §4.2 | `jgaap_specific_concepts()` の docstring に具体的な 5 科目名（NonOperatingIncome, NonOperatingExpenses, OrdinaryIncome, ExtraordinaryIncome, ExtraordinaryLoss）を列挙 |

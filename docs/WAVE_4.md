# Wave 4: 自動化統合 & スリム化

> **作成日**: 2026-03-02
> **最終更新**: 2026-03-02（第 1 回フィードバック反映）
> **前提**: Wave 1–3 完了（1,342 テスト）、NOW.md の設計判断
> **目的**: concept_sets + TaxonomyResolver をパイプラインに接続し、jgaap.py / ifrs.py / sector/ を canonical_key のみの薄いレイヤーにスリム化する

---

## 0. 全体像

NOW.md §1.7「あるべき姿」を実現する:

```
concept_sets.py  → PL/BS/CF 分類 + 表示順序（タクソノミから自動）
taxonomy/labels  → ラベル（TaxonomyResolver が既に実装済み）
jgaap.py         → canonical_key + 会計基準間マッピングのみ
ifrs.py          → canonical_key + 会計基準間マッピングのみ
sector/          → sector_key + general_equivalent のみ
```

### 依存関係

```
Part 1a (concept_sets IFRS 新規実装)
  │
  └──→ Part 1b (normalize + statements 接続)
         │
         ├──→ Part 2 (jgaap.py / ifrs.py スリム化)
         │
         ├──→ Part 3 (sector/ スリム化 + sector_key リネーム)
         │
         └──→ Part 4 (CanonicalKey 定数化) ← Part 2, 3 完了後
```

Part 1a → 1b が土台。Part 2/3 は Part 1b 完了後に並列実行可能。Part 4 は最後。

### 変更対象ファイル一覧

| Part | 変更ファイル | 新規ファイル |
|------|------------|------------|
| 1a | `concept_sets.py` | テスト追加 |
| 1b | `normalize.py`, `statements.py` | `tests/test_xbrl/test_concept_sets_integration.py` |
| 2 | `jgaap.py`, `ifrs.py`, `test_standards_jgaap.py`, `test_standards_ifrs.py` | — |
| 3 | `sector/_base.py`, `sector/banking.py`, `sector/insurance.py`, `sector/construction.py`, `sector/railway.py`, `sector/securities.py`, テスト群 | — |
| 4 | `jgaap.py`, `ifrs.py`, `sector/*.py`, テスト群 | `src/edinet/xbrl/standards/canonical_keys.py`, `tests/test_xbrl/test_canonical_keys.py` |
| 統合 | `__init__.py` 群, `stubs/` | — |

### 行数概算（削減方向）

| ファイル | 現在 | Part 完了後 | 差分 |
|---------|:----:|:--------:|:----:|
| jgaap.py | 1,201 | ~350 | **-850** |
| ifrs.py | 1,155 | ~350 | **-805** |
| sector/_base.py | 446 | ~250 | **-196** |
| sector/banking.py | 733 | ~200 | **-533** |
| sector/insurance.py | 807 | ~200 | **-607** |
| sector/construction.py | 351 | ~100 | **-251** |
| sector/railway.py | 229 | ~80 | **-149** |
| sector/securities.py | 265 | ~80 | **-185** |
| normalize.py | 320 | ~200 | **-120** |
| concept_sets.py | +新規実装 | +~80 | +80 |
| canonical_keys.py | 新規 | ~150 | +150 |
| **合計** | **5,507** | **~2,010** | **-3,497** |

---

# Part 1a: concept_sets IFRS 新規実装

## 1a.1 背景・課題

現在の `concept_sets.py` は `jppfs`（J-GAAP）モジュールのみをスキャンする。IFRS（`jpigp` モジュール）の Presentation Linkbase は存在するが（実機確認済み）、concept_sets.py には `jpigp` の文字列もパラメータも **一切存在しない**。本 Part は新規ロジックの追加である。

### 実機確認結果

```
taxonomy/jpigp/2025-11-01/r/
├── jpigp_ac_2025-11-01_pre_bs.xml   ← _pre_(bs|pl|cf|ss|ci) パターンに合致
├── jpigp_ac_2025-11-01_pre_cf.xml
├── jpigp_ac_2025-11-01_pre_ci.xml
├── jpigp_ac_2025-11-01_pre_pl.xml
├── jpigp_ac_2025-11-01_pre_ss.xml
├── jpigp_610010-001_2025-11-01_pre.xml  ← 個別開示の _pre（分類不要）
└── ...
```

### IFRS concept 名の名前空間（重要な調査結果）

jpigp の _pre ファイルは **`jpigp_cor_*` ローカル名を参照する**（`jppfs_cor_*` ではない）:

```xml
<!-- jpigp_ac_2025-11-01_pre_pl.xml の loc 要素 -->
<link:loc xlink:href="../jpigp_cor_2025-11-01.xsd#jpigp_cor_RevenueIFRS"/>
<link:loc xlink:href="../jpigp_cor_2025-11-01.xsd#jpigp_cor_CostOfSalesIFRS"/>
<link:loc xlink:href="../jpigp_cor_2025-11-01.xsd#jpigp_cor_GrossProfitIFRS"/>
```

実際の IFRS 企業のインスタンスでも Fact は `<jpigp_cor:RevenueIFRS>` を使用する。つまり concept_sets で jpigp をスキャンすれば、IFRS インスタンスの Fact の `local_name` と正しくマッチする。

例外: jppfs_cor が参照される箇所は `ConsolidatedOrNonConsolidatedAxis` / `ConsolidatedMember`（構造メタデータ）のみで、財務科目ではない。

J-GAAP との違い:
- J-GAAP: `jppfs/*/r/{industry}/` 以下に業種別サブディレクトリ
- IFRS: `jpigp/*/r/` 直下にフラット配置、業種コードの概念なし

## 1a.2 設計

`derive_concept_sets()` に `module_group` パラメータを追加:

```python
def derive_concept_sets(
    taxonomy_path: str | Path,
    *,
    use_cache: bool = True,
    module_group: str = "jppfs",   # 新規: "jppfs" or "jpigp"
) -> ConceptSetRegistry:
```

- `module_group="jppfs"`: 現行動作（`jppfs/*/r/{industry}/` をスキャン）
- `module_group="jpigp"`: `jpigp/*/r/` 直下をスキャン、業種コードは `"ifrs"` 固定

ディレクトリスキャン関数 `_scan_taxonomy_directory()` を拡張し、jpigp の場合は:
1. `taxonomy/{module_group}/*/r/` でバージョンディレクトリを走査
2. `_pre_(bs|pl|cf|ss|ci)` パターンのファイルを収集
3. 業種別サブディレクトリがないため、全ファイルを業種コード `"ifrs"` に紐づけ

キャッシュ: 既存の pickle キャッシュに `module_group` をキャッシュキーに追加。

### jpigp ディレクトリが存在しない場合の挙動

`taxonomy_root` が渡されても `jpigp/` ディレクトリが存在しない場合（J-GAAP 専用のタクソノミ等）は **空の `ConceptSetRegistry` を返す**（エラーではない）。呼び出し元が空の registry を受け取った場合はフォールバック動作に遷移する。

## 1a.3 テスト計画

| ID | テスト内容 | ファイル |
|----|----------|--------|
| T01 | concept_sets の jpigp 対応: IFRS _pre ファイルから PL/BS/CF/CI/SS を導出 | test_concept_sets.py |
| T02 | concept_sets の jpigp: role URI 分類が正しい | test_concept_sets.py |
| T03 | jpigp の _pre loc 要素が jpigp_cor ローカル名を参照していることの検証 | test_concept_sets.py |
| T04 | jpigp ディレクトリが存在しない場合に空 ConceptSetRegistry を返す | test_concept_sets.py |
| T05 | jppfs + jpigp を同時に derive した場合、互いに干渉しない | test_concept_sets.py |
| T06 | 回帰: 既存の全テスト（1,342 件）がパス | 全体 |

## 1a.4 実装ステップ

1. **concept_sets.py** — `module_group` パラメータ追加、`_scan_taxonomy_directory()` の jpigp 分岐
2. **キャッシュキー** — `module_group` をファイル名に含める
3. **テスト** — T01–T06
4. **回帰テスト**

---

# Part 1b: normalize + statements パイプライン接続

## 1b.1 背景

Part 1a で concept_sets が J-GAAP（全 23 業種）と IFRS の両方をカバーするようになった後、`normalize.py` の `get_known_concepts()` / `get_concept_order()` を concept_sets ベースに切り替える。

## 1b.2 キャッシュ戦略

**現在の問題**: `normalize.py` の `get_known_concepts()` / `get_concept_order()` は `@functools.lru_cache(maxsize=32)` で装飾されている。`taxonomy_root: Path` と `industry_code: str` を追加すると:
- 23 業種 × 3 諸表 × 2 基準 = 138 パターン → `maxsize=32` が不足
- Path の同一性が OS 依存（WSL パス正規化等）

**解決策**: `lru_cache` を外す。理由:
- `derive_concept_sets()` 側に pickle キャッシュが既にあり、2 回目以降の呼び出しはデシリアライズのみ
- `ConceptSetRegistry.get()` は内部 dict lookup のみ（O(n) だが n ≤ 数十で実質無料）
- `lru_cache` のメリット（関数呼び出しの memoize）は、上流のキャッシュで十分代替される

## 1b.3 normalize.py の書き換え

### `get_known_concepts()` と `get_concept_order()` の統合

sector 専用関数 `get_known_concepts_for_sector()` / `get_concept_order_for_sector()` は **統合する**（非推奨ラッパーではなく、シグネチャ変更）。理由: これらは内部 API であり、外部ユーザー向けの互換性は不要。`statements.py` の呼び出し箇所（L671–679）も同時に変更する。

```python
# 変更後（lru_cache 除去、taxonomy_root / industry_code 追加）
def get_known_concepts(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    *,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,
) -> frozenset[str]:
    """指定基準・諸表種別の既知概念集合を返す。

    taxonomy_root が指定されている場合、concept_sets（Presentation Linkbase 動的導出）を
    優先的に使用する。指定がない場合は jgaap/ifrs のハードコードにフォールバック。
    industry_code が指定されている場合、業種別の concept_sets を使用する。
    """
    if taxonomy_root is not None:
        cs = _get_concept_set(standard, statement_type, taxonomy_root, industry_code)
        if cs is not None:
            return cs.non_abstract_concepts()
    # レガシーフォールバック
    return _get_known_concepts_legacy(standard, statement_type)
```

```python
def get_concept_order(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    *,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,
) -> dict[str, int]:
    if taxonomy_root is not None:
        cs = _get_concept_set(standard, statement_type, taxonomy_root, industry_code)
        if cs is not None:
            return {
                e.concept: int(e.order)
                for e in cs.concepts
                if not e.is_abstract
            }
    return _get_concept_order_legacy(standard, statement_type)
```

共通ヘルパー:

```python
def _standard_to_module_group(standard: AccountingStandard | None) -> str:
    """会計基準 → module_group を返す。"""
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return "jpigp"
    return "jppfs"

def _get_concept_set(
    standard, statement_type, taxonomy_root, industry_code,
) -> ConceptSet | None:
    """concept_sets から ConceptSet を取得する共通ヘルパー。"""
    module_group = _standard_to_module_group(standard)
    registry = derive_concept_sets(taxonomy_root, module_group=module_group)
    ind = industry_code or ("ifrs" if module_group == "jpigp" else "cai")
    return registry.get(statement_type, consolidated=True, industry_code=ind)
```

### レガシーフォールバック関数

lru_cache なしで既存ロジックをそのまま内部関数化:

```python
def _get_known_concepts_legacy(standard, statement_type) -> frozenset[str]:
    """taxonomy_root なしの場合の従来動作。"""
    if standard in (AccountingStandard.JAPAN_GAAP, None):
        return frozenset(m.concept for m in jgaap.mappings_for_statement(statement_type))
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return frozenset(m.concept for m in ifrs.mappings_for_statement(statement_type))
    if standard == AccountingStandard.US_GAAP:
        return frozenset()
    return frozenset(m.concept for m in jgaap.mappings_for_statement(statement_type))
```

### `get_known_concepts_for_sector` / `get_concept_order_for_sector` の削除

内部 API のため、非推奨ラッパーではなく **削除**。`statements.py` の呼び出し元を `get_known_concepts(..., industry_code=...)` に一本化する。

## 1b.4 statements.py の変更

`_build_for_type()` を簡素化:

```python
# 変更前: sector 分岐あり
if self._industry_code is not None:
    known = get_known_concepts_for_sector(standard_enum, statement_type, self._industry_code)
    order = get_concept_order_for_sector(standard_enum, statement_type, self._industry_code)
else:
    known = get_known_concepts(standard_enum, statement_type)
    order = get_concept_order(standard_enum, statement_type)

# 変更後: 統一呼び出し
known = get_known_concepts(
    standard_enum, statement_type,
    taxonomy_root=self._taxonomy_root,
    industry_code=self._industry_code,
)
order = get_concept_order(
    standard_enum, statement_type,
    taxonomy_root=self._taxonomy_root,
    industry_code=self._industry_code,
)
```

import 文も `get_known_concepts_for_sector` / `get_concept_order_for_sector` を削除。

## 1b.5 テスト計画

| ID | テスト内容 | ファイル |
|----|----------|--------|
| T07 | normalize: taxonomy_root ありで concept_sets 経由の known_concepts を返す | test_normalize.py |
| T08 | normalize: taxonomy_root ありで concept_sets 経由の concept_order を返す | test_normalize.py |
| T09 | normalize: taxonomy_root なしで従来のレガシーフォールバック動作 | test_normalize.py |
| T10 | normalize: IFRS + taxonomy_root で jpigp の concept_sets を使う | test_normalize.py |
| T11 | normalize: industry_code 指定で業種別 concept_sets を使う | test_normalize.py |
| T12 | normalize: taxonomy_root はあるが jpigp ディレクトリがない IFRS → レガシーフォールバック | test_normalize.py |
| T13 | statements: _build_for_type が taxonomy_root / industry_code を normalize に伝搬 | test_statements.py |
| T14 | statements: 旧 sector 分岐が統一呼び出しに置き換わっている | test_statements.py |
| T15 | 回帰: 既存の全テスト（1,342 件）がパス | 全体 |

## 1b.6 実装ステップ

1. **normalize.py 書き換え** — lru_cache 除去、シグネチャ変更、レガシーフォールバック、sector 関数削除
2. **statements.py 変更** — `_build_for_type` の統一呼び出し、import 整理
3. **テスト** — T07–T15
4. **回帰テスト**

---

# Part 2: jgaap.py / ifrs.py スリム化

## 2.1 背景

Part 1b で concept_sets がパイプラインに接続された後、jgaap.py / ifrs.py から以下のフィールドが不要になる:

| フィールド | 理由 | 代替元 |
|-----------|------|-------|
| `label_ja` | TaxonomyResolver が提供 | taxonomy label linkbase |
| `label_en` | TaxonomyResolver が提供 | taxonomy label linkbase |
| `display_order` | concept_sets が提供 | pres_tree の order |
| `period_type` | concept_sets + XSD で導出可能 | 未使用（除去しても影響なし） |
| `is_total` | concept_sets の `preferredLabel` | pres_tree |

### 残すもの

```python
# jgaap.py の最終形
@dataclass(frozen=True, slots=True)
class ConceptMapping:
    concept: str                          # ローカル名
    canonical_key: str                    # 統一キー
    statement_type: StatementType | None  # レガシーフォールバック用（※後述）
    is_jgaap_specific: bool = False       # J-GAAP 固有か
```

**`statement_type` を残す理由**: normalize.py のレガシーフォールバック（`taxonomy_root=None` の場合）が `mappings_for_statement(statement_type)` を呼び、各 ConceptMapping を `statement_type` でフィルタして既知概念集合を構築する。`statement_type` がないとフォールバック自体が動かない。また US-GAAP パスの `_build_usgaap_statement()` も `reverse_lookup(si.key) → jm.statement_type` で PL/BS/CF を判別している。

```python
# ifrs.py の最終形
@dataclass(frozen=True, slots=True)
class IFRSConceptMapping:
    concept: str                          # ローカル名
    canonical_key: str                    # 統一キー
    statement_type: StatementType | None  # レガシーフォールバック用
    is_ifrs_specific: bool = False        # IFRS 固有か
    jgaap_concept: str | None = None      # J-GAAP 対応
    mapping_note: str = ""                # 備考
```

## 2.2 変更内容

### jgaap.py

**削除するフィールド**: `label_ja`, `label_en`, `period_type`, `is_total`, `display_order`

**削除する型**: `PeriodType`

**API 維持**: `lookup`, `canonical_key`, `reverse_lookup`, `mappings_for_statement`, `all_mappings`, `all_canonical_keys`, `jgaap_specific_concepts`, `is_jgaap_module`, `get_profile` — 全て維持。

**マッピングデータの変更例**:

```python
# Before (9 フィールド)
ConceptMapping(
    concept="NetSales",
    canonical_key="revenue",
    label_ja="売上高",
    label_en="Net sales",
    statement_type=StatementType.INCOME_STATEMENT,
    period_type="duration",
    is_jgaap_specific=False,
    is_total=False,
    display_order=1,
)

# After (4 フィールド)
ConceptMapping(
    concept="NetSales",
    canonical_key="revenue",
    statement_type=StatementType.INCOME_STATEMENT,
    is_jgaap_specific=False,
)
```

**JGAAPProfile**: 変更なし（基準判別のプロファイル情報は維持）

**バリデーション**: `display_order` 一意性チェック、`period_type` 検証を削除。concept / canonical_key の一意性チェックは維持。

### ifrs.py

同様に `label_ja`, `label_en`, `period_type`, `is_total`, `display_order` を削除。`jgaap_concept` と `mapping_note` は残す。

### normalize.py のレガシーフォールバック調整

`_get_concept_order_legacy()` は `display_order` が削除されるため、`mappings_for_statement()` が返すタプルのインデックス順序をそのまま order として使う:

```python
def _get_concept_order_legacy(standard, statement_type) -> dict[str, int]:
    """taxonomy_root なしの場合の従来表示順序。

    display_order フィールド削除後は、mappings_for_statement() の
    タプル順序（定義順）をそのまま表示順序とする。
    """
    if standard in (AccountingStandard.JAPAN_GAAP, None):
        mappings = jgaap.mappings_for_statement(statement_type)
    elif standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        mappings = ifrs.mappings_for_statement(statement_type)
    else:
        return {}
    return {m.concept: i for i, m in enumerate(mappings)}
```

これにより `taxonomy_root=None` の場合でも、jgaap.py / ifrs.py のタプル定義順（現在 `display_order` 昇順と同一）がそのまま表示順序として使われる。`order=0` で全項目が同一優先度になる問題を回避。

## 2.3 テスト計画

| ID | テスト内容 |
|----|----------|
| T16 | jgaap ConceptMapping の新フィールド構成で構築可能 |
| T17 | jgaap lookup / canonical_key / reverse_lookup が従来通り動作 |
| T18 | jgaap mappings_for_statement が正しい concept セットを返す |
| T19 | jgaap all_canonical_keys が全キーを返す |
| T20 | jgaap jgaap_specific_concepts が J-GAAP 固有のみを返す |
| T21 | ifrs IFRSConceptMapping の新フィールド構成で構築可能 |
| T22 | ifrs lookup / canonical_key / reverse_lookup が従来通り動作 |
| T23 | ifrs ifrs_to_jgaap_map / jgaap_to_ifrs_map が動作 |
| T24 | normalize レガシーフォールバック: taxonomy_root=None で定義順の order を返す |
| T25 | normalize レガシーフォールバック: order が 0, 1, 2, ... の連番 |
| T26 | 回帰: 全テストパス |

## 2.4 実装ステップ

1. **ConceptMapping / IFRSConceptMapping** のフィールド削除
2. **マッピングデータ** の全エントリを新フォーマットに書き換え（タプル定義順は現在の display_order 順を維持）
3. **バリデーション関数** の更新（display_order / period_type チェック削除）
4. **normalize.py** の `_get_concept_order_legacy()` をインデックス順ベースに変更
5. **テスト更新** — 削除されたフィールドを参照するテストを修正
6. **回帰テスト**

---

# Part 3: sector/ スリム化 + sector_key リネーム

## 3.1 背景

NOW.md §Q11 の設計判断:
- `SectorConceptMapping.canonical_key` → `sector_key` にリネーム（スコープの混同を防ぐ）
- `label_ja`, `label_en`, `display_order`, `statement_type`, `period_type`, `is_total` を削除（concept_sets + TaxonomyResolver で自動化）

Part 1b で concept_sets が全 23 業種をカバーするため、sector/ の手動 concept リストは **科目分類・表示順序の目的では不要**。残す役割は:

1. `sector_key` — 業種内ローカルの正規化キー
2. `general_equivalent` — 一般事業会社の canonical_key への翻訳
3. `industry_codes` — 適用業種コード

## 3.2 sector_key リネームの波及範囲

**リネーム対象の全箇所**（調査結果）:

| 対象 | 変更内容 |
|------|---------|
| `SectorConceptMapping.canonical_key` フィールド | → `sector_key` |
| `SectorRegistry.canonical_key()` メソッド | → `SectorRegistry.sector_key()` |
| `SectorRegistry._key_index` | キーが sector_key に |
| `SectorRegistry.canonical_key_count` プロパティ | → `sector_key_count` |
| `SectorRegistry.all_canonical_keys()` メソッド | → `all_sector_keys()` |
| 各業種モジュールのモジュールレベル関数 `canonical_key = registry.canonical_key` | → `sector_key = registry.sector_key` |
| `normalize.py` の `get_canonical_key_for_sector()` 内部 | `reg.canonical_key()` → `reg.sector_key()` |
| 各テストファイル | フィールド名・メソッド名の参照を更新 |

**破壊的変更**: これは公開 API の変更。互換性は気にしない方針のため、deprecated wrapper は置かず **一気に変更** する。

## 3.3 データモデル変更

```python
# Before
@dataclass(frozen=True, slots=True)
class SectorConceptMapping:
    concept: str
    canonical_key: str          # ← 業種内ローカルキー（名前が misleading）
    label_ja: str
    label_en: str
    statement_type: StatementType | None
    period_type: PeriodType
    industry_codes: frozenset[str]
    display_order: int
    general_equivalent: str | None = None
    is_total: bool = False
    mapping_note: str = ""

# After
@dataclass(frozen=True, slots=True)
class SectorConceptMapping:
    concept: str
    sector_key: str             # ← リネーム: 業種内ローカルキー
    industry_codes: frozenset[str]
    general_equivalent: str | None = None   # canonical_key への翻訳
    mapping_note: str = ""
```

**削除**: `label_ja`, `label_en`, `statement_type`, `period_type`, `display_order`, `is_total`, `canonical_key`（→ `sector_key` にリネーム）

## 3.4 SectorRegistry の変更

内部インデックスの変更:

| インデックス | Before | After |
|------------|--------|-------|
| `_concept_index` | `{concept → mapping}` | 維持 |
| `_key_index` | `{canonical_key → mapping}` | `{sector_key → mapping}` |
| `_statement_index` | `{StatementType → mappings}` | **削除** |
| `_general_index` | `{general_equivalent → mappings}` | 維持 |

削除する SectorRegistry メソッド・プロパティ:
- `mappings_for_statement()` — concept_sets で代替（Part 1b で normalize の sector フォールバックも `_get_concept_set()` ベースに変更済みのため安全に削除可能）
- `known_concepts` プロパティ — concept_sets で代替（normalize.py は Part 1b で既にこのプロパティを呼ばなくなっている）
- `canonical_key()` メソッド → `sector_key()` にリネーム
- `canonical_key_count` プロパティ → `sector_key_count` にリネーム
- `all_canonical_keys()` → `all_sector_keys()` にリネーム

維持する SectorRegistry メソッド:
- `lookup(concept)` → SectorConceptMapping
- `sector_key(concept)` → str | None（旧 `canonical_key()`）
- `reverse_lookup(sector_key)` → SectorConceptMapping
- `to_general_key(concept)` → str | None
- `from_general_key(canonical_key)` → list[SectorConceptMapping]
- `to_general_map()` → dict[str, str]
- `get_profile()` → SectorProfile

### normalize.py の sector 関連関数

`get_canonical_key_for_sector()` は維持するが、内部で `reg.canonical_key()` → `reg.sector_key()` に変更:

```python
def get_canonical_key_for_sector(local_name, standard=None, industry_code=None):
    # ...
    if reg is not None:
        key = reg.sector_key(local_name)  # ← リネーム
        if key is not None:
            return key
    return get_canonical_key(local_name, standard)
```

## 3.5 各業種モジュールの変更

| ファイル | 現在行数 | 変更後行数 | 主な変更 |
|---------|:------:|:--------:|--------|
| banking.py | 733 | ~200 | マッピングを 4 フィールドに、モジュールレベル関数のリネーム |
| insurance.py | 807 | ~200 | 同上 |
| construction.py | 351 | ~100 | 同上 |
| railway.py | 229 | ~80 | 同上 |
| securities.py | 265 | ~80 | 同上 |

## 3.6 テスト計画

| ID | テスト内容 |
|----|----------|
| T27 | SectorConceptMapping の新フィールド構成で構築可能 |
| T28 | SectorRegistry の sector_key() / reverse_lookup() が動作 |
| T29 | SectorRegistry の to_general_key() / from_general_key() が動作 |
| T30 | banking: 全マッピングが新フォーマットで構築可能 |
| T31 | insurance: 同上 |
| T32 | construction / railway / securities: 同上 |
| T33 | normalize の get_canonical_key_for_sector が sector_key() 経由で動作 |
| T34 | cross_validation: general_equivalent が jgaap の canonical_key に存在 |
| T35 | 回帰: 全テストパス |

## 3.7 実装ステップ

1. **SectorConceptMapping** のフィールド変更（_base.py）
2. **SectorRegistry** のインデックス・メソッド変更（_base.py）— `mappings_for_statement()` / `known_concepts` 削除、リネーム
3. **各業種モジュール** のマッピングデータ書き換え（banking → insurance → construction → railway → securities）
4. **normalize.py** の `get_canonical_key_for_sector()` 内部変更
5. **テスト更新**
6. **回帰テスト**

---

# Part 4: CanonicalKey 定数化

## 4.1 背景

NOW.md §Q11:

```python
# 現状: typo しても静かに壊れる
canonical_key="revenue"              # jgaap.py
canonical_key="revenue"              # ifrs.py
general_equivalent="revenue"         # banking.py

# 改善後: typo → AttributeError（即座に検出）
canonical_key=CK.REVENUE             # jgaap.py
canonical_key=CK.REVENUE             # ifrs.py
general_equivalent=CK.REVENUE        # banking.py
```

## 4.2 設計

新規ファイル `src/edinet/xbrl/standards/canonical_keys.py`:

```python
"""会計基準横断の正規化キー定数。

jgaap.py, ifrs.py, sector/*.py が共有する canonical_key の
文字列リテラルを定数化し、typo を防止する。
"""

from __future__ import annotations

from enum import StrEnum


class CK(StrEnum):
    """CanonicalKey 定数群。

    StrEnum を使用。CK.REVENUE == "revenue" が True（.value 不要）。
    isinstance(CK.REVENUE, str) も True のため dict[str, ...] にそのまま使える。

    naming convention: 大文字スネークケース。
    値: 小文字スネークケースの文字列。

    セクション:
        PL — 損益計算書の科目
        BS — 貸借対照表の科目
        CF — キャッシュフロー計算書の科目
        KPI — 主要経営指標
    """

    # --- PL ---
    REVENUE = "revenue"
    COST_OF_SALES = "cost_of_sales"
    GROSS_PROFIT = "gross_profit"
    SGA_EXPENSES = "sga_expenses"
    OPERATING_INCOME = "operating_income"
    # ... 全 canonical_key を列挙

    # --- BS ---
    CASH_AND_DEPOSITS = "cash_and_deposits"
    # ...

    # --- CF ---
    CF_OPERATING = "cf_operating"
    # ...

    # --- KPI ---
    EPS = "eps"
    # ...
```

**StrEnum を採用する理由**（Python >= 3.12 が要件のため使用可能）:
- `CK.REVENUE == "revenue"` が True（`.value` 不要）
- `isinstance(CK.REVENUE, str)` が True（dict キーにそのまま使える）
- `CK("revenue")` で逆引き可能
- `list(CK)` で全定数列挙可能
- IDE のオートコンプリートが効く

セクションコメント（`# --- PL ---` / `# --- BS ---` 等）で整理し、将来 SS/CI が追加されても見通しを維持する。

### 定数化の対象

2026-03-02 時点の実データ:
- jgaap の canonical_key: 83 個
- ifrs の canonical_key: 55 個
- jgaap ∩ ifrs（基準間で共有）: 45 個
- sector の general_equivalent: 18 個（全て jgaap に存在）

合計ユニーク数: **93 個程度**（jgaap 83 + ifrs only 10）

## 4.3 変更内容

1. `canonical_keys.py` 新規作成（`CK` StrEnum + 全定数、PL/BS/CF/KPI セクション分け）
2. `jgaap.py` の全 `canonical_key=` 文字列を `CK.*` に置換
3. `ifrs.py` の全 `canonical_key=` 文字列を `CK.*` に置換
4. `sector/*.py` の全 `general_equivalent=` 文字列を `CK.*` に置換
5. テストで `CK.*` と文字列値の一致を検証

## 4.4 テスト計画

| ID | テスト内容 |
|----|----------|
| T36 | CK の全定数が小文字 snake_case の文字列 |
| T37 | CK の定数値に重複なし |
| T38 | jgaap の全 canonical_key が CK に存在 |
| T39 | ifrs の全 canonical_key が CK に存在 |
| T40 | sector の全 general_equivalent が CK に存在 |
| T41 | jgaap ↔ ifrs の canonical_key 整合性（同じ CK 定数を使っている） |
| T42 | CK("revenue") で逆引き可能（StrEnum 特性） |
| T43 | list(CK) で全定数列挙可能 |
| T44 | 回帰: 全テストパス |

## 4.5 実装ステップ

1. **canonical_keys.py** 作成 — jgaap.py / ifrs.py から全 canonical_key を抽出して StrEnum 定数化（PL/BS/CF/KPI セクション分け）
2. **jgaap.py 置換** — 文字列リテラル → `CK.*`
3. **ifrs.py 置換** — 同上
4. **sector/*.py 置換** — `general_equivalent=` の文字列を `CK.*` に
5. **テスト** — T36–T44
6. **回帰テスト**

---

# 統合タスク（全 Part 完了後）

1. `__init__.py` の更新（必要に応じて re-export を追加）
2. `uv run stubgen src/edinet --include-docstrings -o stubs` でスタブ再生成
3. `uv run ruff check src tests` でリントチェック
4. 全テスト実行 → 既存 1,342 件 + 新規テスト全パス確認
5. stubs/ のコミット

---

# フィードバック反映サマリー（第 1 回）

| # | 指摘 | 判定 | 対応 |
|---|------|------|------|
| 1 | module_group="jpigp" は新規実装 | **妥当** | 「拡張」→「新規実装」に修正、Part 1a として分離 |
| 2 | jpigp パスの存在確認 | **確認済み** | 実機で `taxonomy/jpigp/2025-11-01/r/` の存在と _pre ファイルを確認 |
| 3 | jpigp → jppfs_cor マッピングの検証 | **調査完了: 指摘と異なる結果** | jpigp _pre ファイルは `jpigp_cor_*` ローカル名を参照。IFRS インスタンスの Fact も `jpigp_cor:*` を使用。マッチする。T03 にテスト追加 |
| 4 | lru_cache と新パラメータの衝突 | **妥当** | lru_cache を外し、derive_concept_sets() の pickle キャッシュに委ねる設計に変更 |
| 5 | sector 関数の非推奨化タイミング | **妥当** | 内部 API のため非推奨ではなく「削除」（シグネチャ統合）と明記 |
| 6 | display_order 削除で表示順が壊れる | **妥当** | タプル定義順（enumerate）をそのまま order として使う方式に変更 |
| 7 | statement_type 残留理由の再検討 | **妥当** | 理由を「US-GAAP パス」→「レガシーフォールバック + US-GAAP パス」に修正 |
| 8 | sector_key リネームの波及範囲 | **妥当** | 全波及箇所を列挙。deprecated wrapper は置かず一気に変更 |
| 9 | mappings_for_statement() 削除順序 | **妥当** | Part 1b で normalize が concept_sets ベースに移行した後、Part 3 で削除する順序を明記 |
| 10 | StrEnum の検討 | **採用** | Python >= 3.12 のため StrEnum が使える。CK を StrEnum に変更 |
| 11 | 93 定数の管理 | **妥当** | PL/BS/CF/KPI セクションコメントで整理する方針を明記 |
| 12 | Part 1 の分割 | **妥当** | Part 1a（concept_sets IFRS 新規実装）→ Part 1b（normalize + statements 接続）に分離 |
| 13 | 部分タクソノミのテスト | **妥当** | T04（jpigp なしで空 registry）、T12（IFRS で jpigp なしの場合のフォールバック）を追加 |

---

# エージェントが守るべきルール

あなたは Wave 4 を担当するエージェントです。
担当機能: 自動化統合 & スリム化

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/sector/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は統合タスクが一括で行う

2. **Part の順序を守ること**
   Part 1a → Part 1b → (Part 2 | Part 3) → Part 4 の依存関係を守る。

3. **既存のテストフィクスチャを変更しないこと**
   - `tests/fixtures/taxonomy_mini/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/linkbase_*` 配下の既存ファイルを変更してはならない

4. **`stubgen` を実行しないこと**
   統合タスクで一括実行する。

## 推奨事項

5. 各 Part 完了時に `uv run pytest` を実行し全テストパスを確認すること
6. 各 Part 完了時に変更ファイル一覧を報告すること
7. Part 1b 完了時に E2E テスト（taxonomy_root あり/なし）を実行して動作確認すること

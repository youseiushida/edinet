# Wave 4 / Part 1a — `taxonomy/concept_sets`: IFRS (jpigp) 対応

# エージェントが守るべきルール

あなたは Wave 4 / Part 1a を担当するエージェントです。
担当機能: concept_sets の IFRS (jpigp) 対応

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/sector/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他 Part が担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/taxonomy/concept_sets.py` (既存・変更)
   - `tests/test_xbrl/test_concept_sets.py` (既存・変更)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - `derive_concept_sets()` の既存シグネチャを維持すること（パラメータ追加はデフォルト値付きで可）
   - `ConceptSetRegistry`, `ConceptSet`, `ConceptEntry`, `StatementCategory`, `classify_role_uri` の既存インターフェースを維持すること
   - `get_concept_set()` の既存シグネチャを維持すること

4. **`stubgen` を実行しないこと**
   統合タスクで一括実行する。

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/taxonomy_mini/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/concept_sets/` 配下の既存ファイルを変更してはならない

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets` (OK)

7. **テストファイルの命名規則**
   - 既存の `tests/test_xbrl/test_concept_sets.py` に追加する
   - IFRS 固有のテストクラス名は `TestIFRS*` プレフィックスを使う

8. **他モジュールの利用は import のみ**
   - 以下のモジュールのみ import 可能:
     - `edinet.xbrl.linkbase.presentation` (PresentationTree, parse_presentation_linkbase 等)
     - `edinet.models.financial` (StatementType)
     - `edinet.exceptions` (EdinetConfigError, EdinetWarning)
     - `edinet._version` (__version__)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# PART 1a — `taxonomy/concept_sets`: IFRS (jpigp) 対応

## 0. 位置づけ

### WAVE_4.md との対応

WAVE_4.md §Part 1a:

> Part 1a で concept_sets が J-GAAP（全 23 業種）と IFRS の両方をカバーするようになった後、Part 1b で normalize.py / statements.py に接続する。

### 依存先

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `linkbase/presentation.py` (Wave 1 L1) | PresentationTree パース | import |
| `concept_sets.py` 既存実装 (Wave 2 L1) | J-GAAP 導出ロジックの拡張 | 変更対象 |

### 他 Part とのファイル衝突

なし。本 Part は `concept_sets.py` と `test_concept_sets.py` のみを変更する。Part 1b 以降は `normalize.py` / `statements.py` を変更するが、本 Part では触れない。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| C-1b | 高 | IFRS 企業の concept 名前空間 (jpigp_cor)、命名パターン [F5][F6] |
| D-1 | 高 | IFRS タクソノミの構造 |
| I-1 | 中 | ELR 番号体系（5桁=IFRS 本表、連単識別） |
| NOW.md §1.3 | 高 | concept_sets の既存設計 |
| NOW.md §3.3 | 中 | jpigp の _pre ファイルが jppfs スコープ外だった背景 |

---

## 1. 背景知識

### 1.1 現状の concept_sets.py

`concept_sets.py` (788 行) は `jppfs` モジュール（J-GAAP）の Presentation Linkbase のみをスキャンし、23 業種の PL/BS/CF/SS/CI concept セットを動的に導出する。`jpigp` の文字列やパラメータは一切存在しない。

スキャン対象ディレクトリ構造:

```
{taxonomy_root}/taxonomy/jppfs/{version}/r/{industry_code}/
  ├── *_pre_pl*.xml
  ├── *_pre_bs*.xml
  ├── *_pre_cf*.xml
  └── ...
```

### 1.2 IFRS タクソノミの構造（実機調査結果）

```
{taxonomy_root}/taxonomy/jpigp/{version}/r/
  ├── jpigp_ac_2025-11-01_pre_bs.xml     ← _pre_(bs|pl|cf|ss|ci) パターンに合致
  ├── jpigp_ac_2025-11-01_pre_cf.xml
  ├── jpigp_ac_2025-11-01_pre_ci.xml
  ├── jpigp_ac_2025-11-01_pre_pl.xml
  ├── jpigp_ac_2025-11-01_pre_ss.xml
  ├── jpigp_610010-001_2025-11-01_pre.xml  ← 個別開示の _pre（分類不要）
  ├── jpigp_500000-000_2025-11-01_pre.xml  ← 表紙の _pre（分類不要）
  └── ...
```

J-GAAP との構造的な違い:

| 項目 | J-GAAP (jppfs) | IFRS (jpigp) |
|------|---------------|-------------|
| ディレクトリ | `jppfs/{ver}/r/{industry}/` | `jpigp/{ver}/r/` (フラット) |
| 業種サブディレクトリ | あり（23 業種） | **なし** |
| `_pre_(bs\|pl\|cf)` ファイル | 業種ディレクトリ内 | `r/` 直下 |
| ファイル名プレフィックス | `jppfs_{industry}_*` | `jpigp_ac_*` |
| concept 名前空間 | `jppfs_cor_*` | `jpigp_cor_*` |

### 1.3 IFRS の concept ローカル名（重要）

jpigp の _pre ファイルの `link:loc` 要素は **`jpigp_cor_*` ローカル名を参照する**:

```xml
<!-- jpigp_ac_2025-11-01_pre_pl.xml -->
<link:loc xlink:href="../jpigp_cor_2025-11-01.xsd#jpigp_cor_RevenueIFRS"/>
<link:loc xlink:href="../jpigp_cor_2025-11-01.xsd#jpigp_cor_CostOfSalesIFRS"/>
<link:loc xlink:href="../jpigp_cor_2025-11-01.xsd#jpigp_cor_GrossProfitIFRS"/>
```

実際の IFRS 企業のインスタンスでも Fact は `<jpigp_cor:RevenueIFRS>` を使用する。よって concept_sets で jpigp をスキャンすれば、IFRS インスタンスの Fact の `local_name` と正しくマッチする。

例外: `jppfs_cor` が参照される箇所は `ConsolidatedOrNonConsolidatedAxis` / `ConsolidatedMember`（連結軸のメタデータ）のみで、財務科目ではない。

### 1.4 IFRS の role URI と classify_role_uri() の問題（実機調査結果）

jpigp _pre ファイルの role URI:

| ファイル | role URI |
|---------|---------|
| _pre_pl | `rol_std_ConsolidatedStatementOfProfitOrLossIFRS` |
| _pre_bs | `rol_std_ConsolidatedStatementOfFinancialPositionIFRS` |
| _pre_cf | `rol_std_ConsolidatedStatementOfCashFlowsIFRS` |
| _pre_ci | `rol_std_ConsolidatedStatementOfComprehensiveIncomeIFRS` |
| _pre_ss | `rol_std_ConsolidatedStatementOfChangesInEquityIFRS` |

現在の `classify_role_uri()` での分類結果:

| role URI | 現在の結果 | 期待される結果 |
|---------|-----------|-------------|
| `...StatementOfProfitOrLossIFRS` | **`None`** | `(INCOME_STATEMENT, True, None)` |
| `...StatementOfFinancialPositionIFRS` | **`None`** | `(BALANCE_SHEET, True, None)` |
| `...StatementOfCashFlowsIFRS` | `(CF, True, None)` | OK |
| `...StatementOfComprehensiveIncomeIFRS` | `(CI, True, None)` | OK |
| `...StatementOfChangesInEquityIFRS` | `(SS, True, None)` | OK |

**PL と BS が分類できていない。** 原因: `_STATEMENT_KEYWORDS` に以下が欠けている:

- `"StatementOfProfitOrLoss"` → `INCOME_STATEMENT`（IFRS 用。J-GAAP は `"StatementOfIncome"`）
- `"StatementOfFinancialPosition"` → `BALANCE_SHEET`（IFRS 用。J-GAAP は `"BalanceSheet"`）

CF / CI / SS は既存キーワード (`StatementOfCashFlows`, `StatementOfComprehensiveIncome`, `StatementOfChangesInEquity`) で先頭一致するため分類可能。`IFRS` サフィックスは startswith マッチの対象外。

---

## 2. ゴール

1. `derive_concept_sets()` に `module_group` パラメータを追加し、`"jpigp"` を指定すると IFRS の Presentation Linkbase からの導出を行えるようにする
2. `classify_role_uri()` に IFRS 固有のキーワード 2 つを追加し、IFRS の PL / BS を正しく分類する
3. IFRS の concept セット導出結果を `ConceptSetRegistry` として返し、`industry_code="ifrs"` で取得できるようにする
4. jpigp ディレクトリが存在しない場合は空の `ConceptSetRegistry` を返す（エラーではない）

### 非ゴール（スコープ外）

- `normalize.py` / `statements.py` への接続 → Part 1b の責務
- jgaap.py / ifrs.py のスリム化 → Part 2 の責務
- 個別（非連結）の IFRS テンプレート対応 → 将来 Wave
  - 補足: 2025-11-01 タクソノミでは `_pre_(bs|pl|cf|ss|ci)` の 5 ファイルは全て `Consolidated*` role URI であり、非連結ロールは存在しない。ただし `classify_role_uri()` は `Consolidated` プレフィックスの有無で連結/個別を判定するため、将来非連結ロール（例: `rol_std_StatementOfProfitOrLossIFRS`）が追加された場合は `is_consolidated=False` として自動的に正しく分類される。Part 1a ではテスト対象外とする。

### 非機能要件

- 既存の J-GAAP テスト（全 1,342 件）が壊れないこと
- `module_group` 未指定（デフォルト `"jppfs"`）で既存動作が完全に維持されること
- pickle キャッシュが `module_group` ごとに分離されること

---

## 3. 設計

### 3.1 `_STATEMENT_KEYWORDS` への追加

```python
_STATEMENT_KEYWORDS: list[tuple[str, StatementCategory]] = [
    # 既存 (J-GAAP 向け)
    ("StatementOfComprehensiveIncome", StatementCategory.COMPREHENSIVE_INCOME),
    ("StatementOfChangesInEquity", StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY),
    ("StatementOfChangesInNetAssets", StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY),
    ("StatementOfUnitholdersEquity", StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY),
    ("StatementOfMembersEquity", StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY),
    ("StatementOfIncomeAndRetainedEarnings", StatementCategory.INCOME_STATEMENT),
    ("StatementOfCashFlows", StatementCategory.CASH_FLOW_STATEMENT),
    # ★ 追加 (IFRS 向け) — 順序が重要: StatementOfIncome より前に配置
    ("StatementOfProfitOrLoss", StatementCategory.INCOME_STATEMENT),
    ("StatementOfFinancialPosition", StatementCategory.BALANCE_SHEET),
    # 既存 (J-GAAP 向け)
    ("StatementOfIncome", StatementCategory.INCOME_STATEMENT),
    ("BalanceSheet", StatementCategory.BALANCE_SHEET),
]
```

**順序の根拠**: `startswith` で先頭一致するため、`"StatementOfIncome"` より `"StatementOfIncomeAndRetainedEarnings"` を先に置く既存パターンに従う。`"StatementOfProfitOrLoss"` は `"StatementOfIncome"` と prefix が異なるため順序問題はないが、意味的に近いもの同士をグループ化する。

### 3.2 `_scan_taxonomy_directory()` の拡張

現在の関数は `taxonomy/jppfs/*/r/{industry}/` をスキャンする。IFRS では `taxonomy/jpigp/*/r/` 直下にファイルがある。

新しいスキャン関数 `_scan_taxonomy_directory_flat()` を追加:

```python
def _scan_taxonomy_directory_flat(
    taxonomy_path: Path,
    module_group: str,
    industry_code: str,
) -> dict[str, list[Path]]:
    """フラット構造のタクソノミディレクトリを走査する。

    jpigp のように業種サブディレクトリがない場合に使用。
    r/ 直下の _pre ファイルを収集し、指定の industry_code に紐づける。

    Args:
        taxonomy_path: タクソノミのルートパス。
        module_group: モジュールグループ名（例: ``"jpigp"``）。
        industry_code: 割り当てる業種コード（例: ``"ifrs"``）。

    Returns:
        ``{industry_code: [pre_file_paths]}`` 辞書。
        ディレクトリが存在しなければ空辞書。
    """
    r_dirs = sorted(taxonomy_path.glob(f"taxonomy/{module_group}/*/r"))
    if not r_dirs:
        return {}  # ← jppfs と違いエラーではなく空辞書を返す
    result_files: list[Path] = []
    for r_dir in r_dirs:
        # _pre_*.xml で収集（_pre.xml サフィックスなしを除外）。
        # J-GAAP 側は業種ディレクトリ内で *_pre*.xml を使うが、
        # jpigp の r/ 直下には jpigp_500000-000_*_pre.xml（表紙）や
        # jpigp_610010-001_*_pre.xml（注記）など _pre_(bs|pl|cf|ss|ci)
        # パターンに合致しないファイルが多い。_pre_*.xml に絞ることで
        # _group_pre_files() で弾かれる無駄なファイル読み込みを抑制する。
        result_files.extend(sorted(r_dir.glob("*_pre_*.xml")))
    if not result_files:
        return {}
    return {industry_code: result_files}
```

### 3.3 `derive_concept_sets()` の変更

```python
def derive_concept_sets(
    taxonomy_path: str | Path,
    *,
    use_cache: bool = True,
    module_group: str = "jppfs",   # ★ 新規パラメータ
) -> ConceptSetRegistry:
    """タクソノミディレクトリから全業種の ConceptSet を導出する。

    Args:
        taxonomy_path: タクソノミのルートパス。
        use_cache: キャッシュを使用するかどうか。
        module_group: スキャン対象のモジュールグループ。
            ``"jppfs"``（デフォルト）: J-GAAP、23 業種。
            ``"jpigp"``: IFRS、業種コード ``"ifrs"`` 固定。

    Returns:
        ConceptSetRegistry インスタンス。

    Raises:
        EdinetConfigError: パスが存在しない場合。
        EdinetConfigError: module_group="jppfs" で jppfs/*/r が見つからない場合。
    """
```

主要な変更点:
1. `module_group` パラメータ追加（デフォルト `"jppfs"` で後方互換）
2. キャッシュパスに `module_group` を含める（後述）
3. `module_group == "jppfs"` の場合は既存の `_scan_taxonomy_directory()` を使用
4. `module_group == "jpigp"` の場合は新しい `_scan_taxonomy_directory_flat()` を使用
5. jpigp の場合、`_apply_cf_fallback()` はスキップ（IFRS は CF を持つため不要）

### 3.4 キャッシュキーの変更

```python
def _cache_path(taxonomy_path: Path, module_group: str = "jppfs") -> Path:
    """キャッシュファイルのパスを構築する。"""
    path_hash = hashlib.sha256(str(taxonomy_path).encode()).hexdigest()[:8]
    version = taxonomy_path.name
    cache_dir = Path(platformdirs.user_cache_dir("edinet"))
    return (
        cache_dir
        / f"concept_sets_v{_CACHE_VERSION}_{__version__}_{module_group}_{version}_{path_hash}.pkl"
        #                                                 ^^^^^^^^^^^^^^ 追加
    )
```

`module_group` をファイル名に含めることで、jppfs と jpigp のキャッシュが衝突しない。

### 3.5 `get_concept_set()` の変更

```python
def get_concept_set(
    taxonomy_path: str | Path,
    statement_type: StatementType,
    *,
    consolidated: bool = True,
    industry_code: str = "cai",
    use_cache: bool = True,
    cf_method: str | None = None,
    module_group: str = "jppfs",   # ★ 新規
) -> ConceptSet | None:
```

`module_group` を `derive_concept_sets()` に伝搬するだけ。

**注意**: `industry_code` のデフォルト値は `"cai"` のまま。`module_group="jpigp"` の場合、利用者は `industry_code="ifrs"` を明示的に指定する必要がある。Part 1b で `normalize.py` が `_standard_to_module_group()` に基づいて `industry_code="ifrs"` を自動設定するため、エンドユーザーが直接 `get_concept_set()` を呼ぶ場合のみ注意が必要。docstring にこの点を注記する。

---

## 4. 変更内容の詳細

### 4.1 `concept_sets.py` の変更箇所

| 箇所 | 行番号 | 変更内容 |
|------|--------|---------|
| `_STATEMENT_KEYWORDS` | L162-199 | 2 キーワード追加 |
| `_scan_taxonomy_directory_flat()` | 新規 | IFRS 用フラットスキャン関数 |
| `_cache_path()` | L606-621 | `module_group` パラメータ追加、ファイル名に含める |
| `derive_concept_sets()` | L686-754 | `module_group` パラメータ追加、分岐ロジック |
| `get_concept_set()` | L762- | `module_group` パラメータ追加（伝搬のみ）+ docstring 注記 |

**変更不要のもの**: `derive_concept_sets_from_trees()` はディレクトリスキャンに関与せず、role URI → ConceptSet 変換のみを行う関数のため、変更不要。

### 4.2 追加するキーワードの仕様書根拠

| キーワード | role URI の例 | 根拠 |
|-----------|-------------|------|
| `StatementOfProfitOrLoss` | `rol_std_ConsolidatedStatementOfProfitOrLossIFRS` | IFRS の PL 名称（IAS 1）。EDINET タクソノミ実物で確認済み |
| `StatementOfFinancialPosition` | `rol_std_ConsolidatedStatementOfFinancialPositionIFRS` | IFRS の BS 名称（IAS 1）。EDINET タクソノミ実物で確認済み |

### 4.3 `derive_concept_sets()` の分岐ロジック

```python
def derive_concept_sets(taxonomy_path, *, use_cache=True, module_group="jppfs"):
    path = Path(taxonomy_path)
    if not path.exists():
        raise EdinetConfigError(f"タクソノミパスが存在しません: {path}")

    if use_cache:
        cached = _load_cache(_cache_path(path, module_group))
        if cached is not None:
            return cached

    t0 = time.perf_counter()

    # ★ module_group による分岐
    if module_group == "jppfs":
        industry_files = _scan_taxonomy_directory(path)
    else:
        industry_files = _scan_taxonomy_directory_flat(
            path, module_group, industry_code="ifrs",
        )
        if not industry_files:
            # jpigp ディレクトリが存在しない → 空レジストリを返す
            return ConceptSetRegistry(_sets={})

    registry_data: dict[str, dict[str, ConceptSet]] = {}

    for code, pre_files in industry_files.items():
        groups = _group_pre_files(pre_files)
        sets_for_industry: dict[str, ConceptSet] = {}
        for stmt_key, group_files in groups.items():
            merged = _parse_and_merge_group(group_files)
            for role_uri, tree in merged.items():
                classification = classify_role_uri(role_uri)
                if classification is None:
                    continue
                category, is_consolidated, cf_method = classification
                cs = _tree_to_concept_set(
                    role_uri, tree, category, is_consolidated,
                    f"{module_group}/{code}/{stmt_key}",  # ★ source_info にモジュール名
                    cf_method=cf_method,
                )
                sets_for_industry[role_uri] = cs
        registry_data[code] = sets_for_industry

    # ★ CF フォールバックは jppfs のみ
    if module_group == "jppfs":
        _apply_cf_fallback(registry_data)

    # ... (ログ出力, キャッシュ保存は既存と同一)
    registry = ConceptSetRegistry(_sets=registry_data)
    if use_cache:
        _save_cache(registry, _cache_path(path, module_group))
    return registry
```

---

## 5. IFRS 導出結果の期待値

### 5.1 2025-11-01 タクソノミでの期待結果

| 項目 | 値 |
|------|---|
| `registry.industries()` | `frozenset({"ifrs"})` |
| `registry.statement_categories("ifrs")` | `{BS, PL, CF, SS, CI}` |

### 5.2 PL の概念一覧（実機調査結果）

jpigp_ac _pre_pl.xml から導出される `jpigp_cor` ローカル名:

| 概念 | ローカル名 |
|------|----------|
| 売上収益 | `RevenueIFRS` |
| 売上原価 | `CostOfSalesIFRS` |
| 売上総利益 | `GrossProfitIFRS` |
| 販管費 | `SellingGeneralAndAdministrativeExpensesIFRS` |
| その他の収益 | `OtherIncomeIFRS` |
| その他の費用 | `OtherExpensesIFRS` |
| 営業利益 | `OperatingProfitLossIFRS` |
| 金融収益 | `FinanceIncomeIFRS` |
| 金融費用 | `FinanceCostsIFRS` |
| 持分法による投資利益 | `ShareOfProfitLossOfInvestmentsAccountedForUsingEquityMethodIFRS` |
| 税引前利益 | `ProfitLossBeforeTaxIFRS` |
| 法人所得税費用 | `IncomeTaxExpenseIFRS` |
| 当期利益 | `ProfitLossIFRS` |
| 親会社所有者帰属 | `ProfitLossAttributableToOwnersOfParentIFRS` |
| 非支配持分帰属 | `ProfitLossAttributableToNonControllingInterestsIFRS` |
| 基本的 EPS | `BasicEarningsLossPerShareIFRS` |
| 希薄化後 EPS | `DilutedEarningsLossPerShareIFRS` |

※ abstract 含む全 23 loc 要素のうち、非 abstract が 15–17 個（実装時に正確な数値を確認）。

### 5.3 BS / CF の概念（抜粋）

BS: `CashAndCashEquivalentsIFRS`, `TradeAndOtherReceivablesCAIFRS`, `CurrentAssetsIFRS`, `PropertyPlantAndEquipmentIFRS`, `AssetsIFRS`, `TotalCurrentLiabilitiesIFRS`, `EquityIFRS` 等。

CF: `StatementOfCashFlowsIFRS` の role URI で導出。`CashFlowsFromOperatingActivitiesIFRS` 等。

---

## 6. テスト計画

### 6.1 テスト原則

- Detroit 派（古典派）: モック不使用、実際の XML bytes → アサート
- 既存テストクラスの隣に IFRS 用テストクラスを追加
- タクソノミ実物テスト (`EDINET_TAXONOMY_ROOT` 環境変数) は `@pytest.mark.skipif` で条件付き

### 6.2 テスト一覧

`tests/test_xbrl/test_concept_sets.py` に追加:

| ID | テスト名 | 内容 | 種別 |
|----|---------|------|------|
| T01 | `test_classify_role_uri_ifrs_pl` | `...StatementOfProfitOrLossIFRS` → `(INCOME_STATEMENT, True, None)` | 単体 |
| T02 | `test_classify_role_uri_ifrs_bs` | `...StatementOfFinancialPositionIFRS` → `(BALANCE_SHEET, True, None)` | 単体 |
| T03 | `test_classify_role_uri_ifrs_pl_without_suffix` | `...StatementOfProfitOrLoss` (IFRS サフィックスなし) → PL | 単体 |
| T04 | `test_classify_role_uri_ifrs_bs_without_suffix` | `...StatementOfFinancialPosition` (IFRS サフィックスなし) → BS | 単体 |
| T05 | `test_classify_role_uri_existing_jgaap_unaffected` | 既存の J-GAAP role URI が変わらないことの回帰テスト | 回帰 |
| T06 | `test_derive_concept_sets_default_module_group` | `module_group` 未指定で既存動作が維持されること | 回帰 |
| T07 | `test_derive_concept_sets_jpigp_empty_when_no_dir` | jpigp ディレクトリなしで空 ConceptSetRegistry | 単体 |
| T08 | `test_derive_concept_sets_jpigp_returns_ifrs_industry` | jpigp 導出結果の `industries()` が `{"ifrs"}` | タクソノミ実物 |
| T09 | `test_derive_concept_sets_jpigp_has_pl_bs_cf` | jpigp 導出結果が PL/BS/CF を含む | タクソノミ実物 |
| T10 | `test_derive_concept_sets_jpigp_pl_has_known_ifrs_concepts` | PL に既知の IFRS 概念（`RevenueIFRS`, `ProfitLossIFRS` 等）が含まれること | タクソノミ実物 |
| T11 | `test_derive_concept_sets_jpigp_no_jppfs_cor_in_non_abstract` | 非 abstract 概念に `jppfs_cor` 由来がないこと | タクソノミ実物 |
| T12 | `test_derive_concept_sets_jppfs_and_jpigp_independent` | jppfs と jpigp を同時に derive しても互いに干渉しないこと | タクソノミ実物 |
| T13 | `test_cache_path_includes_module_group` | キャッシュパスに `module_group` が含まれること | 単体 |
| T14 | `test_cache_jppfs_and_jpigp_separate_files` | jppfs と jpigp のキャッシュファイルが別であること | 単体 |
| T15 | `test_get_concept_set_with_module_group_jpigp` | `get_concept_set(..., module_group="jpigp")` が動作すること | タクソノミ実物 |

### 6.3 テストの実装パターン

**T01–T05: classify_role_uri の単体テスト**

```python
class TestClassifyRoleURIIFRS:
    """IFRS role URI の分類テスト。"""

    def test_classify_role_uri_ifrs_pl(self) -> None:
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jpigp/"
            "rol_std_ConsolidatedStatementOfProfitOrLossIFRS"
        )
        assert result is not None
        category, is_consolidated, cf_method = result
        assert category == StatementCategory.INCOME_STATEMENT
        assert is_consolidated is True
        assert cf_method is None

    def test_classify_role_uri_ifrs_bs(self) -> None:
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jpigp/"
            "rol_std_ConsolidatedStatementOfFinancialPositionIFRS"
        )
        assert result is not None
        category, is_consolidated, cf_method = result
        assert category == StatementCategory.BALANCE_SHEET
        assert is_consolidated is True
        assert cf_method is None

    def test_classify_role_uri_existing_jgaap_unaffected(self) -> None:
        """既存の J-GAAP role URI が影響を受けないことを確認。"""
        # PL
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/"
            "rol_ConsolidatedStatementOfIncome"
        )
        assert result is not None
        assert result[0] == StatementCategory.INCOME_STATEMENT

        # BS
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/"
            "rol_ConsolidatedBalanceSheet"
        )
        assert result is not None
        assert result[0] == StatementCategory.BALANCE_SHEET
```

**T07: jpigp ディレクトリなし**

```python
class TestDeriveConceptSetsIFRS:
    """IFRS (jpigp) 導出のテスト。"""

    def test_derive_concept_sets_jpigp_empty_when_no_dir(
        self, tmp_path: Path,
    ) -> None:
        """jpigp ディレクトリが存在しない場合に空レジストリを返す。"""
        # jppfs は存在するが jpigp は存在しないタクソノミルート
        (tmp_path / "taxonomy" / "jppfs" / "2025-11-01" / "r" / "cai").mkdir(
            parents=True,
        )
        registry = derive_concept_sets(
            tmp_path, use_cache=False, module_group="jpigp",
        )
        assert registry.industries() == frozenset()
```

**T08–T12: タクソノミ実物テスト**

```python
_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_skip_no_taxonomy = pytest.mark.skipif(
    _TAXONOMY_ROOT is None,
    reason="EDINET_TAXONOMY_ROOT が未設定",
)

class TestDeriveConceptSetsIFRSReal:
    """タクソノミ実物を使った IFRS 導出テスト。"""

    @_skip_no_taxonomy
    def test_derive_concept_sets_jpigp_returns_ifrs_industry(self) -> None:
        registry = derive_concept_sets(
            _TAXONOMY_ROOT, use_cache=False, module_group="jpigp",
        )
        assert "ifrs" in registry.industries()

    @_skip_no_taxonomy
    def test_derive_concept_sets_jpigp_has_pl_bs_cf(self) -> None:
        registry = derive_concept_sets(
            _TAXONOMY_ROOT, use_cache=False, module_group="jpigp",
        )
        cats = registry.statement_categories("ifrs")
        assert StatementCategory.INCOME_STATEMENT in cats
        assert StatementCategory.BALANCE_SHEET in cats
        assert StatementCategory.CASH_FLOW_STATEMENT in cats

    @_skip_no_taxonomy
    def test_derive_concept_sets_jpigp_pl_has_known_ifrs_concepts(self) -> None:
        """PL に既知の IFRS 概念が含まれることを確認。

        実機調査で PL の jpigp_cor 非 abstract 概念は全て *IFRS サフィックスを
        持つことを確認済み（2025-11-01 タクソノミ）。ただし将来のタクソノミで
        サフィックスなしの概念が追加される可能性を考慮し、既知概念の存在確認
        として検証する。
        """
        registry = derive_concept_sets(
            _TAXONOMY_ROOT, use_cache=False, module_group="jpigp",
        )
        cs = registry.get(
            StatementType.INCOME_STATEMENT,
            consolidated=True,
            industry_code="ifrs",
        )
        assert cs is not None
        concepts = cs.non_abstract_concepts()
        assert len(concepts) > 0
        # 既知の IFRS PL 概念が含まれていること
        expected = {"RevenueIFRS", "ProfitLossIFRS", "OperatingProfitLossIFRS"}
        assert expected.issubset(concepts), (
            f"期待される概念が不足: {expected - concepts}"
        )
```

---

## 7. 実装手順

### Step 1: `_STATEMENT_KEYWORDS` にキーワード追加

1. `concept_sets.py` L162-199 の `_STATEMENT_KEYWORDS` リストに 2 エントリを追加
2. 配置位置: `"StatementOfCashFlows"` の直後（`"StatementOfIncome"` の前）。§3.1 のコード例参照
3. テスト実行: T01–T05 がパスすることを確認

```bash
uv run pytest tests/test_xbrl/test_concept_sets.py -k "IFRS" -v
```

### Step 2: `_scan_taxonomy_directory_flat()` を追加

1. `_scan_taxonomy_directory()` の直後（L497 付近）に新関数を追加
2. テスト: T07 がパスすることを確認

### Step 3: `_cache_path()` に `module_group` を追加

1. 既存の `_cache_path()` に `module_group` パラメータ追加
2. キャッシュファイル名に `module_group` を挿入
3. テスト: T13, T14 がパスすることを確認

### Step 4: `derive_concept_sets()` を拡張

1. `module_group` パラメータ追加（デフォルト `"jppfs"`）
2. `module_group` による分岐ロジック
3. jpigp の場合は `_apply_cf_fallback()` スキップ
4. テスト: T06（回帰）、T08–T12（タクソノミ実物）がパスすることを確認

```bash
EDINET_TAXONOMY_ROOT=/mnt/c/Users/nezow/Downloads/ALL_20251101 uv run pytest tests/test_xbrl/test_concept_sets.py -v
```

### Step 5: `get_concept_set()` を拡張

1. `module_group` パラメータ追加（伝搬のみ）
2. テスト: T15 がパスすることを確認

### Step 6: 全テスト回帰確認

```bash
uv run pytest
```

全 1,342 件 + 新規テストがパスすることを確認。

---

## 8. 作成・変更ファイル一覧

| ファイル | 操作 | 行数概算（差分） |
|---------|------|:------:|
| `src/edinet/xbrl/taxonomy/concept_sets.py` | 変更 | +40–60 |
| `tests/test_xbrl/test_concept_sets.py` | 変更 | +120–160 |

既存ファイルの削除なし。新規ファイルの作成なし。

---

## 9. 設計判断の記録

### Q1: なぜ `module_group` パラメータを追加するのか？別関数にしないのか？

**A**: `derive_concept_sets_jpigp()` のような別関数にすると:
- 戻り値の型 (`ConceptSetRegistry`) が同じ
- 内部ロジック（パース、マージ、キャッシュ）が 95% 共通
- Part 1b で `normalize.py` から呼ぶ際に分岐が必要

パラメータ追加の方が DRY 原則に合致する。デフォルト値 `"jppfs"` で完全に後方互換。

### Q2: jpigp の業種コードを `"ifrs"` 固定にする理由は？

**A**: IFRS タクソノミには業種別サブディレクトリが存在しない。全 IFRS 企業が同じ PL/BS テンプレートを使う。`"ifrs"` は J-GAAP の 23 業種コード（`cai`, `bk1`, etc.）と衝突しない。

### Q3: `_scan_taxonomy_directory()` を修正せず新関数を作る理由は？

**A**: 既存関数は `jppfs/*/r/{industry}/` のディレクトリ階層を前提とし、`EdinetConfigError` を raise する。jpigp では:
1. ディレクトリ構造がフラット
2. ディレクトリが存在しなくてもエラーではない（空レジストリを返す）

これらの違いを 1 関数に混ぜるとエラーハンドリングが複雑になる。責務を分離した方が保守性が高い。

### Q4: CF フォールバックを jpigp でスキップする理由は？

**A**: `_apply_cf_fallback()` は「cai が CF Presentation Linkbase を持たない」問題への対処。jpigp は `_pre_cf.xml` を持ち、自前の CF 概念セットを導出可能。フォールバックは不要。

### Q5: classify_role_uri() の既存キーワードに影響はないか？

**A**: 実機確認済み。`_STATEMENT_KEYWORDS` は `startswith` でマッチするため:
- `"StatementOfProfitOrLoss"` は既存の `"StatementOfIncome"` と prefix が異なり干渉しない
- `"StatementOfFinancialPosition"` は既存のどのキーワードとも prefix が異なり干渉しない
- J-GAAP の全 82 ユニーク role URI（NOW.md §3.3）の分類結果が変わらないことをテスト T05 で確認

---

## 10. 実行チェックリスト

- [ ] `_STATEMENT_KEYWORDS` に 2 キーワード追加
- [ ] `_scan_taxonomy_directory_flat()` 新規関数追加
- [ ] `_cache_path()` に `module_group` パラメータ追加
- [ ] `derive_concept_sets()` に `module_group` パラメータ追加 + 分岐ロジック
- [ ] `get_concept_set()` に `module_group` パラメータ追加
- [ ] T01–T05: classify_role_uri IFRS テスト追加 + パス
- [ ] T06: derive_concept_sets デフォルト回帰テスト + パス
- [ ] T07: jpigp ディレクトリなしテスト + パス
- [ ] T08–T12: タクソノミ実物テスト + パス
- [ ] T13–T14: キャッシュ分離テスト + パス
- [ ] T15: get_concept_set jpigp テスト + パス
- [ ] 既存テスト全 1,342 件がパス
- [ ] `uv run ruff check src/edinet/xbrl/taxonomy/concept_sets.py` クリーン

---

## フィードバック反映サマリー（第 1 回）

| # | 指摘 | 重要度 | 判定 | 対応 |
|---|------|:------:|------|------|
| 1 | glob パターン `*_pre*.xml` が広すぎる | 中 | **妥当** | `_scan_taxonomy_directory_flat()` の glob を `*_pre_*.xml` に変更。`_pre.xml`（サフィックスなし）を除外し、無駄な読み込みを抑制。J-GAAP 側は業種ディレクトリ内で問題ないため `*_pre*.xml` を維持。差異の理由をコメントで明記 |
| 2 | IFRS 非連結ロールの考察が欠落 | 中 | **妥当（ただし現時点で非連結ロールは存在しない）** | 実機調査で 2025-11-01 タクソノミの `_pre_(bs\|pl\|cf\|ss\|ci)` 5 ファイルが全て `Consolidated*` role URI であることを確認。将来追加時は `classify_role_uri()` が `is_consolidated=False` を自動で返す旨を非ゴールに追記 |
| 3 | T10 `endswith("IFRS")` が強すぎる | 中 | **妥当（ただし PL では実際に全概念が *IFRS）** | 実機調査で PL の jpigp_cor 非 abstract 概念は全て `*IFRS` サフィックスを確認。BS は 44/46 が `*IFRS`、残り 2 つは `jppfs_cor` の dimension 要素。将来のタクソノミ変更リスクを考慮し、T10 を「既知 IFRS 概念（`RevenueIFRS`, `ProfitLossIFRS` 等）が含まれること」に変更 |
| 4 | キーワード挿入位置の記述不整合 | 軽微 | **妥当** | Step 1 の説明を §3.1 と統一 |
| 5 | `derive_concept_sets_from_trees()` 未言及 | 軽微 | **妥当** | §4.1 に「変更不要」と明記 |
| 6 | `get_concept_set()` の `industry_code` デフォルト | 軽微 | **妥当** | §3.5 に docstring 注記の方針を追加。Part 1b で normalize.py が自動設定するため Part 1a では注記のみ |

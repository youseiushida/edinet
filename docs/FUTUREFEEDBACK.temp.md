# FUTUREPLAN 並列実装計画の安全性分析

## Wave 1（7 Lanes）の分析

計画で示されたファイル接触:

| Lane | Feature | ファイル操作 | 計画上の衝突 |
|------|---------|-------------|-------------|
| L1 | pres_tree | 新: `xbrl/linkbase/presentation.py` | なし |
| L2 | calc_tree | 新: `xbrl/linkbase/calculation.py` | なし |
| L3 | def_links | 新: `xbrl/linkbase/definition.py` | なし |
| L4 | contexts | 変更: `xbrl/contexts.py` | 唯一の変更者 |
| L5 | namespaces | 変更: `xbrl/_namespaces.py` | 唯一の変更者 |
| L6 | dei | 新: `xbrl/dei.py` | なし |
| L7 | units | 新: `xbrl/units.py` | なし |

### 発見された問題点

---

### CRITICAL-1: `xbrl/__init__.py` の書き込み衝突

**計画に記載なし。実際は複数レーンが変更する必要がある。**

現在の `xbrl/__init__.py`:
```python
from edinet.xbrl.contexts import structure_contexts
from edinet.xbrl.facts import build_line_items
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.financial.statements import Statements, build_statements
from edinet.xbrl.taxonomy import TaxonomyResolver

__all__ = [
    "parse_xbrl_facts", "structure_contexts", "TaxonomyResolver",
    "build_line_items", "build_statements", "Statements",
]
```

新モジュールを公開APIとして提供する場合、以下のレーンが `__init__.py` を変更する必要がある:
- **L1/L2/L3**: linkbase パッケージの公開
- **L4**: contexts の新しいエクスポート（新機能追加時）
- **L6**: dei モジュールの公開
- **L7**: units モジュールの公開

**衝突確率: 高**

**緩和策**: Wave 1 の全レーンが `__init__.py` を変更しないルールとし、Wave 1 完了後に統合タスクとして一括で `__init__.py` を更新する。あるいは各モジュールは `edinet.xbrl.dei` のように直接インポートさせ、`__init__.py` の再エクスポートは後回しにする。

---

### CRITICAL-2: `xbrl/linkbase/__init__.py` の競合作成

L1/L2/L3 が全て新ディレクトリ `xbrl/linkbase/` にファイルを作成する。

- **L1** が `xbrl/linkbase/presentation.py` を作成
- **L2** が `xbrl/linkbase/calculation.py` を作成
- **L3** が `xbrl/linkbase/definition.py` を作成

3つのレーンのうち、**誰が `xbrl/linkbase/__init__.py` を作成するか**が決まっていない。全員が作成しようとすると衝突する。また、各レーンが自分のモジュールだけを `__init__.py` にインポートすると、マージ時に内容が衝突する。

**衝突確率: 高**

**緩和策**: Wave 1 開始前に空の `xbrl/linkbase/__init__.py` を事前に作成しておく。各レーンは自分の `.py` ファイルのみを作成し、`__init__.py` は触らない。

---

### CRITICAL-3: `xbrl/taxonomy.py` → パッケージ化の未対応

**Wave 2 で致命的な問題を引き起こす。**

現在 `xbrl/taxonomy.py` は**単一ファイルモジュール**（`TaxonomyResolver` を含む）。

Wave 2 の計画では:
- L1: `xbrl/taxonomy/concept_sets.py` を新規作成

これは `taxonomy` をファイルからパッケージ（ディレクトリ）に変換する必要があることを意味する:
```
# 現在
xbrl/taxonomy.py  (ファイル)

# Wave 2 で必要
xbrl/taxonomy/         (ディレクトリ)
├── __init__.py        (TaxonomyResolver を再エクスポート)
├── _resolver.py       (旧 taxonomy.py の内容を移動)
└── concept_sets.py    (新規)
```

この変換は:
1. 既存の全 import（`from edinet.xbrl.taxonomy import TaxonomyResolver`）に影響
2. テスト（`test_taxonomy.py`, `test_facts.py`, `test_statements.py`）に影響
3. `stubs/edinet/xbrl/taxonomy.pyi` にも影響

**計画にこの変換タスクが一切記載されていない。**

**衝突確率: 確実に問題になる**

**緩和策**: Wave 1 の事前準備として `taxonomy.py` → `taxonomy/` パッケージ化を実施する。`__init__.py` で既存の公開インターフェースを全て再エクスポートし、テストが壊れないことを確認してから Wave 1 を開始する。

---

### HIGH-1: テストフィクスチャの書き込み衝突

`tests/fixtures/taxonomy_mini/` は複数テストから共有されている:

```
tests/fixtures/taxonomy_mini/
├── filer/
│   ├── filer.xsd
│   ├── filer_lab.xml
│   └── filer_lab-en.xml
└── taxonomy/jppfs/2025-11-01/
    ├── jppfs_cor_2025-11-01.xsd
    └── label/
        ├── jppfs_2025-11-01_lab.xml
        └── jppfs_2025-11-01_lab-en.xml
```

各レーンが新機能のテストを書く際:
- **L1 (pres_tree)**: Presentation linkbase のテスト用 XML フィクスチャが必要
- **L2 (calc_tree)**: Calculation linkbase のテスト用 XML フィクスチャが必要
- **L3 (def_links)**: Definition linkbase のテスト用 XML フィクスチャが必要
- **L4 (contexts)**: contexts テストの拡充 → `test_contexts.py` 変更

新規フィクスチャの追加は衝突しにくいが、**既存の `filer.xsd` の変更**（新しいリンクベースファイルの参照追加等）は衝突リスクがある。

**衝突確率: 中〜高**（共有フィクスチャの変更次第）

**緩和策**: 各レーンは独自のフィクスチャディレクトリを使用する（例: `tests/fixtures/linkbase_pres/`, `tests/fixtures/linkbase_calc/`）。共有フィクスチャは変更しない。

---

### HIGH-2: L4 (contexts) の変更が他モジュールのテストを破壊

`StructuredContext` dataclass は以下から import されている:

| ファイル | 使い方 |
|---------|--------|
| `xbrl/facts.py` | `build_line_items()` の引数 |
| `xbrl/statements.py` | 期間フィルタリングに使用 |
| `models/financial.py` | `LineItem.period` の型 |
| `test_contexts.py` | 直接テスト |
| `test_facts.py` | テストで使用 |
| `test_statements.py` | テストで使用 |
| `test_financial_display.py` | テストで使用 |

L4 が `StructuredContext` にフィールドを追加したり、`DimensionMember` の構造を変えたりすると、**L4 以外のレーンが触っていない**テストが壊れる。

**衝突確率: 中**（後方互換性を保てば問題なし）

**緩和策**: L4 は既存フィールドを変更せず、**追加のみ**行う。`StructuredContext` の既存インターフェースは frozen dataclass なので、フィールド追加でデフォルト値を付ければ後方互換性を保てる。

---

### HIGH-3: `xbrl/standards/` ディレクトリの競合（Wave 2）

Wave 2 の L2〜L5 が全て新ディレクトリ `xbrl/standards/` にファイルを作成。
CRITICAL-2 と同じ問題 — `xbrl/standards/__init__.py` の競合作成。

---

### MEDIUM-1: `_namespaces.py` の変更影響

L5 が `_namespaces.py` を変更する。現在このファイルを import しているのは:
- `parser.py` — 全 NS 定数を使用
- `contexts.py` (L4) — `NS_XBRLI`, `NS_XBRLDI`
- `taxonomy.py` — `NS_XLINK`, `NS_LINK`

L5 が定数を**追加するだけ**なら安全。**既存定数の名前変更やリネーム**は L4 と衝突する。

**緩和策**: L5 は追加のみ。既存定数のリネームは禁止。

---

### MEDIUM-2: `models/financial.py` の暗黙的影響

`LineItem` と `FinancialStatement` は Wave 1 のどのレーンの変更対象にも**明示的に含まれていない**が、L4 (contexts) や L7 (units) の結果として型定義の変更が必要になる可能性がある。

現在の `LineItem`:
- `period: InstantPeriod | DurationPeriod` — contexts.py 由来
- `dimensions: tuple[DimensionMember, ...]` — contexts.py 由来

L4 がこれらの型を変更すると、`models/financial.py` と `test_financial_display.py` にも影響。

---

### LOW-1: stubs ディレクトリの不整合

CLAUDE.md に「並列稼働中は `stubgen` を使用しない」とあるが、`.pyi` が source と乖離する期間が長引く。Wave 1 完了後に一括で `stubgen` を実行する統合タスクが必要。

---

## Wave 2（5 Lanes）の追加リスク

Wave 1 の問題に加え:

| リスク | 詳細 |
|--------|------|
| CRITICAL-3 再掲 | `taxonomy.py` → パッケージ化が前提条件 |
| HIGH-3 | `xbrl/standards/__init__.py` の競合 |
| Free Rider 問題 | `taxonomy/labels`, `taxonomy/versioning` 等が既存 `taxonomy.py` を変更する可能性 |

---

## Wave 3（4 Lanes）の評価

Wave 3 は比較的安全:
- L1 のみが `statements.py` を変更（正しく設計されている）
- L2〜L4 は全て新規ファイル
- ただし L1 の `statements.py` 変更は test_statements.py に影響 → テスト更新も L1 の責務に含めるべき

---

## 総合評価

```
安全度 (5段階):

Wave 1: ★★★☆☆ (3/5) — 3つの CRITICAL 問題
Wave 2: ★★☆☆☆ (2/5) — taxonomy パッケージ化未解決 + 新ディレクトリ競合
Wave 3: ★★★★☆ (4/5) — 概ね安全、L1 の責務が明確
```

---

## 推奨される事前準備タスク（Wave 0）

並列実装を開始する**前に**、以下を単一エージェントで実施すべき:

1. **`xbrl/taxonomy.py` → `xbrl/taxonomy/` パッケージ化**
   - `taxonomy.py` → `taxonomy/_resolver.py` に移動
   - `taxonomy/__init__.py` で全公開APIを再エクスポート
   - 全テストが通ることを確認

2. **空のディレクトリ構造を事前作成**
   ```
   xbrl/linkbase/__init__.py   (空)
   xbrl/standards/__init__.py  (空)
   ```

3. **ルール文書の作成**
   - 各レーンは `xbrl/__init__.py` を変更しない
   - 各レーンは既存の `__init__.py` を変更しない
   - 各レーンは独自のテストフィクスチャディレクトリを使用
   - L4/L5 は既存インターフェースへの**追加のみ**、変更・削除は禁止
   - Wave 完了後に「統合レーン」が `__init__.py` 更新 + `stubgen` 実行

4. **テストの分離確認**
   - `uv run pytest` が全パスすることを baseline として記録

これらを実施すれば、Wave 1 の安全度は ★★★★☆ (4/5) に改善できます。

---

## Wave 0 実施後の Wave 2 安全度改善

### 各リスクの解消状況

| リスク | 深刻度 | Wave 0 で解消? | 理由 |
|--------|--------|---------------|------|
| CRITICAL-3: `taxonomy.py` → パッケージ化 | 致命的 | **完全解消** | Wave 0 の項目1で実施済みになる |
| HIGH-3: `standards/__init__.py` 競合 | 高 | **完全解消** | Wave 0 の項目2で空ファイル事前作成 |
| Free Rider: `taxonomy/labels` 等 | 中 | **概ね解消** | taxonomy/ がパッケージ化済みなので新ファイル追加は安全。ただし `__init__.py` 変更禁止ルールの遵守が前提 |
| Free Rider: `dimensions/consolidated` | 中 | **未解消** | `xbrl/dimensions/` ディレクトリが Wave 0 の事前作成リストに**含まれていない** |

### 残存リスク

Wave 0 を実施しても残る問題が1つある。

Wave 2 の Free Rider に `dimensions/consolidated → L4 contexts + L3 def_links` が記載されている。これを Wave 2 で実行する場合、新ディレクトリ `xbrl/dimensions/` とその `__init__.py` が必要になるが、Wave 0 の事前作成リストに入っていない。

**対策**: Wave 0 の項目2に `xbrl/dimensions/__init__.py` も追加すれば解消。

### Wave 0 実施後の改善評価

```
Wave 0 なし:                   ★★☆☆☆ (2/5) — 致命的問題あり、そのままでは実行不可
Wave 0 あり:                   ★★★★☆ (4/5) — CRITICAL 全解消、実行可能
Wave 0 + dimensions/ 追加:     ★★★★☆ (4/5) — Free Rider も安全
```

満点にならない理由は、各エージェントが「`__init__.py` を変更しない」というルールを**確実に守る保証がない**点にある。エージェントへのプロンプトに明記すれば実用上は問題ないが、構造的な保証（ファイルロック等）ではないため ★5 にはしていない。

### 改善版 Wave 0 事前作成リスト

上記を踏まえ、項目2の事前作成リストを以下に更新する:

```
xbrl/linkbase/__init__.py      (空)
xbrl/standards/__init__.py     (空)
xbrl/dimensions/__init__.py    (空)   ← 追加
```

### Wave 0 実施後の全 Wave 安全度まとめ

```
安全度 (5段階):

Wave 1: ★★★★☆ (4/5) — CRITICAL 全解消、ルール遵守が前提
Wave 2: ★★★★☆ (4/5) — CRITICAL 全解消、taxonomy パッケージ化済み
Wave 3: ★★★★☆ (4/5) — 元から概ね安全、変更なし
```

---

## エージェント用システムプロンプト（コピペ用）

以下を各レーンのエージェントのシステムプロンプトに追加する。
`{{LANE_ID}}`, `{{WAVE_ID}}`, `{{FEATURE_NAME}}`, `{{YOUR_FILES}}` は起動時に置換すること。

---

```
# 並列実装の安全ルール（必ず遵守）

あなたは Wave {{WAVE_ID}} / Lane {{LANE_ID}} を担当するエージェントです。
担当機能: {{FEATURE_NAME}}

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
   {{YOUR_FILES}}
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
     例: `tests/fixtures/linkbase_presentation/`, `tests/fixtures/dei/` 等

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.dei import extract_dei` （OK）
   - 例: `from edinet.xbrl import extract_dei` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_{{FEATURE_NAME}}.py` に作成
   - 既存のテストファイル（test_contexts.py, test_facts.py, test_statements.py 等）は
     自レーンの担当機能のテストでない限り変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 0 で事前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl._namespaces` (NS_* 定数)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること
```

---

### Wave 1 レーン別 `{{YOUR_FILES}}` 置換表

| Lane | `{{FEATURE_NAME}}` | `{{YOUR_FILES}}` |
|------|---------------------|-------------------|
| L1 | presentation | `src/edinet/xbrl/linkbase/presentation.py` (新規), `tests/test_xbrl/test_presentation.py` (新規), `tests/fixtures/linkbase_presentation/` (新規ディレクトリ) |
| L2 | calculation | `src/edinet/xbrl/linkbase/calculation.py` (新規), `tests/test_xbrl/test_calculation.py` (新規), `tests/fixtures/linkbase_calculation/` (新規ディレクトリ) |
| L3 | definition | `src/edinet/xbrl/linkbase/definition.py` (新規), `tests/test_xbrl/test_definition.py` (新規), `tests/fixtures/linkbase_definition/` (新規ディレクトリ) |
| L4 | contexts | `src/edinet/xbrl/contexts.py` (変更), `tests/test_xbrl/test_contexts.py` (変更) |
| L5 | namespaces | `src/edinet/xbrl/_namespaces.py` (変更) |
| L6 | dei | `src/edinet/xbrl/dei.py` (新規), `tests/test_xbrl/test_dei.py` (新規), `tests/fixtures/dei/` (新規ディレクトリ) |
| L7 | units | `src/edinet/xbrl/units.py` (新規), `tests/test_xbrl/test_units.py` (新規), `tests/fixtures/units/` (新規ディレクトリ) |

### Wave 2 レーン別 `{{YOUR_FILES}}` 置換表

| Lane | `{{FEATURE_NAME}}` | `{{YOUR_FILES}}` |
|------|---------------------|-------------------|
| L1 | concept_sets | `src/edinet/xbrl/taxonomy/concept_sets.py` (新規), `tests/test_xbrl/test_concept_sets.py` (新規), `tests/fixtures/concept_sets/` (新規ディレクトリ) |
| L2 | standards_detect | `src/edinet/xbrl/standards/detect.py` (新規), `tests/test_xbrl/test_standards_detect.py` (新規) |
| L3 | standards_jgaap | `src/edinet/xbrl/standards/jgaap.py` (新規), `tests/test_xbrl/test_standards_jgaap.py` (新規) |
| L4 | standards_ifrs | `src/edinet/xbrl/standards/ifrs.py` (新規), `tests/test_xbrl/test_standards_ifrs.py` (新規) |
| L5 | standards_usgaap | `src/edinet/xbrl/standards/usgaap.py` (新規), `tests/test_xbrl/test_standards_usgaap.py` (新規) |

### Wave 3 レーン別 `{{YOUR_FILES}}` 置換表

| Lane | `{{FEATURE_NAME}}` | `{{YOUR_FILES}}` |
|------|---------------------|-------------------|
| L1 | normalize_integration | `src/edinet/xbrl/standards/normalize.py` (新規), `src/edinet/xbrl/statements.py` (変更), `tests/test_xbrl/test_statements.py` (変更), `tests/test_xbrl/test_normalize.py` (新規) |
| L2 | sector_banking | `src/edinet/xbrl/sector/banking.py` (新規), `tests/test_xbrl/test_sector_banking.py` (新規) |
| L3 | sector_insurance | `src/edinet/xbrl/sector/insurance.py` (新規), `tests/test_xbrl/test_sector_insurance.py` (新規) |
| L4 | sector_others | `src/edinet/xbrl/sector/construction.py` (新規), `src/edinet/xbrl/sector/railway.py` (新規), `src/edinet/xbrl/sector/securities.py` (新規), `tests/test_xbrl/test_sector_others.py` (新規) |


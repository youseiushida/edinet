# Wave 2 / Lane 2 — standards/detect: 会計基準の自動判別

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 2 / Lane 2 を担当するエージェントです。
担当機能: standards_detect

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
   - `src/edinet/xbrl/standards/detect.py` (新規)
   - `tests/test_xbrl/test_standards_detect.py` (新規)
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
   - 例: `from edinet.financial.standards.detect import detect_accounting_standard` （OK）
   - 例: `from edinet.xbrl import detect_accounting_standard` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_standards_detect.py` に作成
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
   - **他の Wave 2 レーンが作成中のモジュール**（concept_sets, jgaap, ifrs, usgaap）に依存してはならない

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 2 — standards/detect: 会計基準の自動判別

## 0. 位置づけ

Wave 2 Lane 2 は、FEATURES.md の **Accounting Standard Normalization > standards/detect** に対応する。XBRL インスタンスから会計基準（J-GAAP / IFRS / US-GAAP / JMIS）を自動判別し、後続の `standards/jgaap`（L3）、`standards/ifrs`（L4）、`standards/usgaap`（L5）へのディスパッチの入力データとなる基盤モジュール。

FEATURES.md の定義:

> - standards/detect: 会計基準の自動判別 [TODO]
>   - depends: dei, namespaces
>   - detail: DEI 要素（`AccountingStandardsDEI`）を第一手段、名前空間（`jppfs_cor` → J-GAAP、`ifrs-full` → IFRS）をフォールバックとして判別（D-3）
>
> ※ FEATURES.md の `ifrs-full` は不正確。D-1.a.md で確認済みの通り、EDINET は IASB の ifrs-full ではなく独自の `jpigp_cor`（`http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/{version}/jpigp_cor`）を使用する。本計画の実装（§5.3）は正しく `jpigp` を使用している。FEATURES.md の修正は Wave 完了後の統合タスクで行う。

FUTUREPLAN.tmp.md での位置:

> Phase 3-1: `standards/detect` → dei + namespaces 依存

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.dei` (Wave 1 L6) | `DEI.accounting_standards` 値の取得 | read-only |
| `edinet.xbrl.dei.AccountingStandard` (Wave 1 L6) | 会計基準 Enum | read-only |
| `edinet.xbrl._namespaces` (Wave 1 L5) | `classify_namespace()`, `NamespaceInfo.module_group` | read-only |
| `edinet.xbrl.parser.RawFact` | 入力データ型 | read-only |
| `edinet.exceptions.EdinetWarning` | 警告カテゴリ | read-only |

他レーンとのファイル衝突なし（新規ファイルのみ作成）。

### QA 参照

| QA | タイトル | 関連度 |
|----|---------|--------|
| D-3 | 会計基準の判別方法 | **直接（設計の基盤）** |
| D-1 | IFRS 適用企業の XBRL | 直接（IFRS 判別の名前空間知見） |
| D-2 | US-GAAP 適用企業の XBRL | 直接（US-GAAP の特殊性） |
| F-1 | DEI 要素の一覧 | 関連（AccountingStandardsDEI の定義） |
| E-2 | 連結/個別の区別 | 関連（連結有無の DEI 判定） |
| A-1 | 名前空間宣言の全体像 | 関連（名前空間パターン） |
| H-3 | タクソノミバージョニング | 関連（名前空間 URI のバージョン部分） |

---

## 1. ゴール

1. XBRL インスタンスの facts から会計基準を自動判別する関数 `detect_accounting_standard()` を実装する
2. 判別結果を `DetectedStandard` frozen dataclass として返す（判別手段・信頼度を含む）
3. **2 段階のフォールバック判別ロジック** を実装する:
   - **第一手段**: DEI 要素 `AccountingStandardsDEI` の値（最も確実）
   - **第二手段**: 名前空間 URI のパターンマッチ（DEI が存在しない書類タイプ向け）
4. Wave 3 L1（`standards/normalize` + `statements.py` 統合）が `detect_accounting_standard()` の結果に基づいて処理パスを分岐できるインターフェースを提供する
5. 各会計基準の「利用可能な詳細度」情報を返す（US-GAAP / JMIS は包括タグ付けのみ）

### 非ゴール（スコープ外）

- 会計基準ごとの科目マッピング → Wave 2 L3〜L5 の責務
- 会計基準に基づく `Statements` の処理分岐 → Wave 3 L1 の責務
- schemaRef から提出者別タクソノミを辿って間接的に判別する手段 → 複雑性に対して利得が少ない。DEI + 名前空間の 2 段階で十分
- Filing モデルとの統合（`Filing.standard` プロパティ等） → Wave 完了後の統合タスク

---

## 2. 背景知識（QA サマリー）

### D-3: 会計基準の判別方法

3 つの判別手段が調査された:

1. **DEI 要素（第一手段）**: `jpdei_cor:AccountingStandardsDEI` の取りうる値は `"Japan GAAP"`, `"IFRS"`, `"US GAAP"`, `"JMIS"` の 4 種。`xsi:nil="true"` は「該当なし」（経理の状況を記載しない書類）。**最も確実で公式な判別方法**
2. **名前空間による推定（第二手段）**: `jpigp_cor` の存在 → IFRS と推定可能。ただし IFRS 企業でも `jppfs_cor` は併用されるため `jppfs_cor` の存在だけでは J-GAAP とは断定できない。US-GAAP には専用名前空間がなく名前空間では判別不可
3. **schemaRef（非採用）**: 提出者別タクソノミを参照するのみで会計基準を直接示さない。間接的に推定可能だが複雑性に見合わない

### D-1: IFRS の名前空間

- EDINET では IASB の `ifrs-full` は使用されない。独自の `jpigp_cor`（`http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/{version}/jpigp_cor`）が使われる
- `jpigp_cor` の存在をもって IFRS 適用と推定可能
- ただし IFRS 企業でも `jppfs_cor`（ディメンション要素用）は併用される
- IFRS は詳細タグ付け（個別勘定科目レベル）が行われる

### D-2: US-GAAP / JMIS の特殊性

- US-GAAP 専用タクソノミモジュールは**存在しない**。US-GAAP 関連要素は `jpcrp_cor` 内に定義（37 要素のみ）
- US-GAAP は**包括タグ付けのみ**（TextBlock + SummaryOfBusinessResults）。個別勘定科目の詳細タグ付けは行われない
- JMIS も同様（40 要素、包括タグ付けのみ）
- 名前空間での判別は不可能 → DEI が唯一の判別手段

### E-2: 連結/個別

- DEI の `WhetherConsolidatedFinancialStatementsArePreparedDEI` で連結有無を判定可能
- この情報は `detect` の直接的な判別対象ではないが、`DetectedStandard` に連結情報を含めることで後続レーンの利便性が向上する

---

## 3. データモデル設計

### 3.1 DetectionMethod 列挙型

判別に使用された手段を記録する。後続レーンやデバッグ時に判別の信頼度を評価するため。

```python
import enum

class DetectionMethod(enum.Enum):
    """会計基準の判別に**成功した**手段。

    判別を「試みたが結果が得られなかった」場合も UNKNOWN となる。
    例: DEI を参照したが AccountingStandardsDEI が nil だった場合も UNKNOWN。

    Attributes:
        DEI: DEI 要素 (AccountingStandardsDEI) から判別。最も確実。
        NAMESPACE: 名前空間 URI のパターンマッチから推定。
            DEI が存在しない書類タイプ（大量保有報告書等）で使用。
        UNKNOWN: いずれの手段でも判別に成功しなかった。
    """
    DEI = "dei"
    NAMESPACE = "namespace"
    UNKNOWN = "unknown"
```

### 3.2 DetailLevel 列挙型

会計基準ごとの XBRL データの詳細度を表す。

```python
class DetailLevel(enum.Enum):
    """XBRL データの詳細度（タグ付けレベル）。

    会計基準によって XBRL の構造化レベルが大きく異なる。
    J-GAAP と IFRS は個別勘定科目レベルの詳細タグ付けが行われるが、
    US-GAAP と JMIS は包括タグ付け（TextBlock）のみ。

    Attributes:
        DETAILED: 個別勘定科目レベルの詳細タグ付け。
            財務諸表の各勘定科目が独立した Fact として存在する。
            PL/BS/CF の構造化パースが可能。
        BLOCK_ONLY: 包括タグ付けのみ。
            財務諸表は TextBlock（HTML ブロック）として格納され、
            個別勘定科目の Fact は存在しない。
            SummaryOfBusinessResults 要素で主要経営指標のみ取得可能。
    """
    DETAILED = "detailed"
    BLOCK_ONLY = "block_only"
```

**設計根拠**: D-2.a.md より US-GAAP と JMIS は包括タグ付けのみであることが確認されている。後続レーン（Wave 3 の `statements.py` 統合）が、包括タグ付けのみの会計基準に対して PL/BS/CF の構造化パースを試みないよう、この情報を判別結果に含める。これにより「US-GAAP の企業で PL が空になる」という混乱を事前に防ぐ。

### 3.3 DetectedStandard frozen dataclass

判別結果を保持する。

```python
import datetime
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class DetectedStandard:
    """会計基準の判別結果。

    Attributes:
        standard: 判別された会計基準。
            既知の 4 値は AccountingStandard Enum、未知の値は str。
            判別不能の場合は None。
        method: 判別に使用された手段。
        detail_level: XBRL データの詳細度。
            standard が確定していない場合（None）は None。
        has_consolidated: 連結財務諸表の有無。
            DEI の WhetherConsolidatedFinancialStatementsArePreparedDEI 値。
            DEI から取得できない場合は None（不明）。
        period_type: 報告期間の種類（通期/半期）。
            DEI の TypeOfCurrentPeriodDEI 値。
            DEI から取得できない場合は None。
        namespace_modules: 検出された標準タクソノミモジュールグループの集合。
            名前空間フォールバック判別のデバッグ用。
            DEI ベースの判別が成功した場合は空（frozenset()）となる。
            名前空間フォールバック時のみ有意な値が設定される。
            必要に応じて detect_from_namespaces() を別途呼び出すことで
            DEI 成功時にも名前空間情報を取得可能。
            例: {"jppfs", "jpcrp", "jpdei"} (J-GAAP),
                {"jppfs", "jpcrp", "jpdei", "jpigp"} (IFRS)
    """
    standard: AccountingStandard | str | None
    method: DetectionMethod
    detail_level: DetailLevel | None = None
    has_consolidated: bool | None = None
    period_type: PeriodType | str | None = None
    namespace_modules: frozenset[str] = frozenset()
```

**設計判断**:
- `standard` の型を `AccountingStandard | str | None` にする理由: Wave 1 L6 (DEI) で `DEI.accounting_standards` が同じ型で定義されているため一貫性を保つ。`AccountingStandard` は `str` のサブクラスなので、利用者は文字列比較も Enum 比較も可能
- `has_consolidated` / `period_type` を含める理由: これらは DEI から簡単に取得でき、後続レーン（standards/normalize, dimensions/consolidated）で即座に使われる情報。detect 関数が DEI を読む時点で取得済みのため、二重に DEI を走査させるのは非効率
- `namespace_modules` を含める理由: 名前空間フォールバック判別の透明性を確保する。利用者が「なぜ IFRS と判定されたか」を検証できる。`frozenset` を使用し frozen dataclass との整合性を保つ
- `detail_level` を `None` 許容にする理由: `standard` が `None`（判別不能）の場合、詳細度も不明

### 3.4 会計基準 → DetailLevel のマッピング

```python
from edinet.xbrl.dei import AccountingStandard

_DETAIL_LEVEL_MAP: dict[AccountingStandard, DetailLevel] = {
    AccountingStandard.JAPAN_GAAP: DetailLevel.DETAILED,
    AccountingStandard.IFRS: DetailLevel.DETAILED,
    AccountingStandard.US_GAAP: DetailLevel.BLOCK_ONLY,
    AccountingStandard.JMIS: DetailLevel.BLOCK_ONLY,
}
```

**根拠**:
- J-GAAP: `jppfs_cor` で全勘定科目が個別にタグ付けされる
- IFRS: `jpigp_cor` で個別勘定科目がタグ付けされる（D-1.a.md）
- US-GAAP: TextBlock + SummaryOfBusinessResults のみ（D-2.a.md）
- JMIS: US-GAAP と同様のパターン（D-2.a.md 補足）

---

## 4. 公開 API

### 4.1 `detect_accounting_standard()`

```python
def detect_accounting_standard(
    facts: tuple[RawFact, ...],
    *,
    dei: DEI | None = None,
) -> DetectedStandard:
    """XBRL インスタンスから会計基準を自動判別する。

    2 段階のフォールバックロジックで会計基準を判別する:

    1. **DEI（第一手段）**: facts から DEI を抽出し、
       AccountingStandardsDEI の値で判別する。
       最も確実で公式な判別方法。

    2. **名前空間（第二手段）**: DEI に AccountingStandardsDEI が
       含まれない場合（大量保有報告書等の書類タイプ）、
       facts の名前空間 URI パターンから会計基準を推定する。

    Args:
        facts: ParsedXBRL.facts から得られる RawFact のタプル。
        dei: extract_dei() で取得済みの DEI。省略時は内部で抽出する。
            既に DEI を抽出済みの場合に渡すことで二重走査を回避できる。

    Returns:
        DetectedStandard。判別不能の場合でもエラーにはせず、
        standard=None, method=UNKNOWN で返す。
    """
```

### 4.2 `detect_from_dei()`

DEI が既に抽出済みの場合のショートカット。

```python
def detect_from_dei(dei: DEI) -> DetectedStandard:
    """DEI オブジェクトから会計基準を判別する。

    extract_dei() が既に呼ばれている場合に使用する。
    名前空間フォールバックは行わない（DEI ベースの判別のみ）。

    Args:
        dei: extract_dei() で取得済みの DEI オブジェクト。

    Returns:
        DetectedStandard。DEI に AccountingStandardsDEI が
        含まれない場合は standard=None, method=UNKNOWN で返す。
    """
```

**設計根拠**:
- `detect_accounting_standard(facts, dei=dei)` で DEI 二重走査を回避しつつ名前空間フォールバック付きの完全な判別が可能。Wave 3 の統合コードでは `dei = extract_dei(facts)` を先に呼び、他の目的にも使いつつ `detect_accounting_standard(facts, dei=dei)` で判別する想定
- `detect_from_dei(dei)` は名前空間フォールバックなしの DEI のみ判別。テスタビリティと「DEI の結果だけ見たい」ユースケースに対応
- 3 つの関数を分けることで、「完全判別（DEI + フォールバック）」「DEI のみ」「名前空間のみ」の 3 つのパスを明示的に提供する

### 4.3 `detect_from_namespaces()`

名前空間のみで判別するユーティリティ。

```python
def detect_from_namespaces(
    facts: tuple[RawFact, ...],
) -> DetectedStandard:
    """facts の名前空間 URI パターンから会計基準を推定する。

    DEI が利用できない場合のフォールバック手段。
    大量保有報告書（350）等、DEI に AccountingStandardsDEI が
    含まれない書類タイプで使用される。

    判別ルール:
        1. jpigp_cor (jpigp) の存在 → IFRS
        2. jppfs_cor (jppfs) のみ存在（jpigp なし） → J-GAAP
        3. 上記に該当しない → 判別不能 (None)

    US-GAAP / JMIS は名前空間では判別不可能（専用タクソノミが
    存在しないため、D-2.a.md 参照）。

    Args:
        facts: ParsedXBRL.facts から得られる RawFact のタプル。

    Returns:
        DetectedStandard (method=NAMESPACE)。
    """
```

**設計根拠**:
- 公開 API として分離する理由: テスタビリティ。DEI 判別と名前空間判別を独立にテスト可能にする
- D-3.a.md の知見に基づくルール:
  - `jpigp_cor` は IFRS 専用タクソノミ → 存在すれば IFRS と確定
  - `jppfs_cor` は J-GAAP 財務諸表本表だが IFRS 企業でも併用される → `jpigp` がなければ J-GAAP と推定
  - US-GAAP / JMIS は `jpcrp_cor` 内の要素のみで専用名前空間がない → 名前空間では判別不可
- 判別不可能な場合のエラーではなく None 返却: 呼び出し側が「判別不能」を明示的にハンドリングできる

---

## 5. 内部アルゴリズム

### 5.1 メインフロー（detect_accounting_standard）

```python
def detect_accounting_standard(
    facts: tuple[RawFact, ...],
    *,
    dei: DEI | None = None,
) -> DetectedStandard:
    # Step 1: DEI から判別を試みる（既に抽出済みならそのまま使用）
    if dei is None:
        dei = extract_dei(facts)
    result = detect_from_dei(dei)

    # Step 2: DEI で判別できた場合はそのまま返す
    if result.standard is not None:
        return result

    # Step 3: 名前空間フォールバック
    ns_result = detect_from_namespaces(facts)

    # Step 4: 名前空間で判別できた場合、DEI の補助情報を統合
    if ns_result.standard is not None:
        return DetectedStandard(
            standard=ns_result.standard,
            method=ns_result.method,
            detail_level=ns_result.detail_level,
            has_consolidated=dei.has_consolidated,  # DEI から取得済み
            period_type=dei.type_of_current_period,  # DEI から取得済み
            namespace_modules=ns_result.namespace_modules,
        )

    # Step 5: 両方失敗 → UNKNOWN
    return DetectedStandard(
        standard=None,
        method=DetectionMethod.UNKNOWN,
        has_consolidated=dei.has_consolidated,
        period_type=dei.type_of_current_period,
        namespace_modules=ns_result.namespace_modules,
    )
```

**ポイント**:
- DEI が `AccountingStandardsDEI` を含まなくても、`has_consolidated` や `type_of_current_period` は含む場合がある。これらの補助情報は名前空間フォールバック結果にも統合する
- UNKNOWN の場合でも DEI から取得可能な情報は保持する（部分的な情報でも後続レーンに有用）

### 5.2 DEI ベースの判別（detect_from_dei）

```python
def detect_from_dei(dei: DEI) -> DetectedStandard:
    standard = dei.accounting_standards

    if standard is None:
        # DEI に AccountingStandardsDEI が存在しないか xsi:nil
        return DetectedStandard(
            standard=None,
            method=DetectionMethod.UNKNOWN,
            has_consolidated=dei.has_consolidated,
            period_type=dei.type_of_current_period,
        )

    # AccountingStandard Enum に変換済みの場合
    if isinstance(standard, AccountingStandard):
        detail_level = _DETAIL_LEVEL_MAP.get(standard)
    else:
        # 未知の文字列の場合（Enum 変換失敗時）
        detail_level = None
        warnings.warn(
            f"未知の会計基準 '{standard}' が検出されました。"
            f"DetailLevel を判定できません。",
            EdinetWarning,
            stacklevel=2,
        )

    return DetectedStandard(
        standard=standard,
        method=DetectionMethod.DEI,
        detail_level=detail_level,
        has_consolidated=dei.has_consolidated,
        period_type=dei.type_of_current_period,
    )
```

**ポイント**:
- `dei.accounting_standards` は Wave 1 L6 で `AccountingStandard | str | None` 型。`AccountingStandard` は `str` のサブクラスなので `isinstance` チェックで Enum かどうかを判別
- 未知の文字列（将来の新基準等）の場合は `detail_level=None` + 警告。値自体はそのまま伝搬する

### 5.3 名前空間ベースの判別（detect_from_namespaces）

```python
def detect_from_namespaces(facts: tuple[RawFact, ...]) -> DetectedStandard:
    # 全 facts のユニークな名前空間 URI を収集
    module_groups: set[str] = set()

    seen_uris: set[str] = set()
    for fact in facts:
        uri = fact.namespace_uri
        if uri in seen_uris:
            continue
        seen_uris.add(uri)

        info = classify_namespace(uri)
        if info.module_group is not None:
            module_groups.add(info.module_group)

    frozen_modules = frozenset(module_groups)

    # 判別ルール
    if "jpigp" in module_groups:
        # jpigp_cor（IFRS タクソノミ）が存在 → IFRS
        return DetectedStandard(
            standard=AccountingStandard.IFRS,
            method=DetectionMethod.NAMESPACE,
            detail_level=DetailLevel.DETAILED,
            namespace_modules=frozen_modules,
        )

    if "jppfs" in module_groups:
        # jppfs_cor のみ存在（jpigp なし） → J-GAAP と推定
        return DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.NAMESPACE,
            detail_level=DetailLevel.DETAILED,
            namespace_modules=frozen_modules,
        )

    # US-GAAP / JMIS は名前空間で判別不可
    return DetectedStandard(
        standard=None,
        method=DetectionMethod.UNKNOWN,
        namespace_modules=frozen_modules,
    )
```

**ポイント**:
- `classify_namespace()` は `lru_cache` 付きのため、同一 URI の重複解析は避けられる。さらに `seen_uris` セットで facts レベルの重複スキップを行い、不要な関数呼び出し自体を削減する
- `module_group` は Wave 1 L5 の `NamespaceInfo` から取得。`"jppfs"`, `"jpigp"`, `"jpcrp"`, `"jpdei"` 等の値
- 判別順序: `jpigp`（IFRS）を先にチェックする。IFRS 企業でも `jppfs` は存在するため、`jppfs` を先にすると IFRS を J-GAAP と誤判定する
- US-GAAP / JMIS が名前空間で判別不可な理由: 専用タクソノミモジュールが存在せず、`jpcrp_cor` 内に要素が定義されている（D-2.a.md）。`jpcrp` は全書類で共通のため会計基準の判別材料にならない

---

## 6. ファイル構成

### 作成ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/standards/detect.py` | 新規 | `DetectionMethod` / `DetailLevel` Enum, `DetectedStandard` dataclass, `detect_accounting_standard()` / `detect_from_dei()` / `detect_from_namespaces()` |
| `tests/test_xbrl/test_standards_detect.py` | 新規 | 単体テスト |

### `src/edinet/xbrl/standards/detect.py` の構成

```
detect.py
├── DetectionMethod(Enum)           # 判別手段の列挙型
├── DetailLevel(Enum)               # タグ付け詳細度の列挙型
├── DetectedStandard(frozen dataclass)  # 判別結果（6 フィールド）
├── _DETAIL_LEVEL_MAP               # AccountingStandard → DetailLevel マッピング
├── detect_accounting_standard()     # 公開 API（メインエントリポイント）
├── detect_from_dei()                # 公開 API（DEI ベース判別）
└── detect_from_namespaces()         # 公開 API（名前空間ベース判別）
```

---

## 7. テスト計画

テストは Detroit 派（古典派）のスタイルで、内部実装に依存せず公開 API のみをテストする。

### 7.1 テスト戦略

- `RawFact` を直接構築してテストする（XBRL パーサーに依存しない）
- Wave 1 L6 のテストヘルパーと同様の `_make_fact()` ヘルパーを作成
- DEI 用の Fact と財務諸表用の Fact を組み合わせたテストシナリオを用意
- `extract_dei()` は Wave 1 L6 でテスト済みのため、detect のテストでは DEI 抽出の正確性ではなく判別ロジックの正確性に集中

### 7.2 テストヘルパー

```python
def _make_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    namespace_uri: str = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor",
    is_nil: bool = False,
) -> RawFact:
    """テスト用の RawFact を簡便に構築する。"""
    return RawFact(
        concept_qname=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref="CurrentYearDuration",
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )


def _make_dei_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    is_nil: bool = False,
) -> RawFact:
    """DEI 用の RawFact を簡便に構築する。"""
    ns = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor"
    return RawFact(
        concept_qname=f"{{{ns}}}{local_name}",
        namespace_uri=ns,
        local_name=local_name,
        context_ref="FilingDateInstant",
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )
```

### 7.3 テストケース

#### P0（必須）— detect_accounting_standard のメインフロー

| # | テスト名 | 概要 |
|---|---------|------|
| T1 | `test_detect_japan_gaap_from_dei` | DEI に `"Japan GAAP"` → standard=JAPAN_GAAP, method=DEI, detail=DETAILED |
| T2 | `test_detect_ifrs_from_dei` | DEI に `"IFRS"` → standard=IFRS, method=DEI, detail=DETAILED |
| T3 | `test_detect_us_gaap_from_dei` | DEI に `"US GAAP"` → standard=US_GAAP, method=DEI, detail=BLOCK_ONLY |
| T4 | `test_detect_jmis_from_dei` | DEI に `"JMIS"` → standard=JMIS, method=DEI, detail=BLOCK_ONLY |
| T5 | `test_detect_dei_nil_falls_back_to_namespace` | DEI の AccountingStandardsDEI が nil → 名前空間フォールバック |
| T6 | `test_detect_no_dei_falls_back_to_namespace` | facts に jpdei_cor 名前空間の Fact が 1 つも含まれない（大量保有報告書等）→ extract_dei は全フィールド None の DEI を返す → 名前空間フォールバック、has_consolidated=None, period_type=None |

#### P0 — detect_from_dei

| # | テスト名 | 概要 |
|---|---------|------|
| T7 | `test_from_dei_with_standard` | AccountingStandard Enum が設定された DEI → 正しい DetectedStandard |
| T8 | `test_from_dei_without_standard` | accounting_standards=None の DEI → standard=None, method=UNKNOWN |
| T9 | `test_from_dei_unknown_string` | 未知の文字列（例: "NewStandard"）→ standard="NewStandard", detail=None, 警告 |
| T10 | `test_from_dei_preserves_consolidated` | DEI の has_consolidated が結果に反映される |
| T11 | `test_from_dei_preserves_period_type` | DEI の type_of_current_period が結果に反映される |

#### P0 — detect_from_namespaces

| # | テスト名 | 概要 |
|---|---------|------|
| T12 | `test_namespace_jppfs_only_is_jgaap` | jppfs_cor のみ → J-GAAP |
| T13 | `test_namespace_jpigp_present_is_ifrs` | jpigp_cor が存在 → IFRS（jppfs_cor も同時に存在しても IFRS） |
| T14 | `test_namespace_no_standard_taxonomy` | 標準タクソノミなし → standard=None |
| T15 | `test_namespace_jpcrp_only_is_unknown` | jpcrp_cor のみ（jppfs も jpigp もなし）→ standard=None（US-GAAP/JMIS 判別不可） |
| T16 | `test_namespace_modules_populated` | namespace_modules に検出されたモジュールグループが含まれる |

#### P1（推奨）— エッジケースと統合

| # | テスト名 | 概要 |
|---|---------|------|
| T17 | `test_detect_dei_takes_priority_over_namespace` | DEI=IFRS + 名前空間=jppfs のみ → DEI の IFRS が優先（method=DEI） |
| T18 | `test_detect_empty_facts` | 空の facts タプル → standard=None, method=UNKNOWN |
| T19 | `test_detect_consolidation_info_in_fallback` | DEI に has_consolidated はあるが accounting_standards がない → 名前空間フォールバック結果に has_consolidated が統合される |
| T20 | `test_detected_standard_frozen` | DetectedStandard が frozen であり変更不可 |
| T21 | `test_detail_level_map_completeness` | 全 AccountingStandard 値に対して DetailLevel がマッピングされている |
| T22 | `test_namespace_different_taxonomy_versions` | 異なるバージョンの jppfs_cor URI でも正しく判別される（H-3 の要件） |
| T23 | `test_namespace_filer_taxonomy_ignored` | 提出者別タクソノミ名前空間は module_groups に含まれない |
| T24 | `test_detect_parametrize_all_standards` | 4 会計基準すべてを parametrize でテスト（DEI 経由）。各基準について以下をアサート: standard == 期待する AccountingStandard 値、method == DetectionMethod.DEI、detail_level == 期待する DetailLevel（J-GAAP/IFRS → DETAILED, US-GAAP/JMIS → BLOCK_ONLY） |
| T25 | `test_detect_unknown_standard_no_namespace_fallback` | DEI に未知の文字列（例: "NewStandard"）→ メインフロー経由で standard="NewStandard", method=DEI（`is not None` により名前空間フォールバックに入らない） |
| T26 | `test_detect_with_preextracted_dei` | `detect_accounting_standard(facts, dei=dei)` で事前抽出済み DEI を渡した場合、DEI 再抽出なしで正しく判別される |

---

## 8. 後続レーンとの接続点

Lane 2 (standards/detect) の出力は以下のレーンで消費される:

| 利用先 | 消費するフィールド | 用途 |
|--------|-------------------|------|
| **Wave 2 L3 (standards/jgaap)** | `detected.standard == JAPAN_GAAP` | J-GAAP 用処理パスの選択 |
| **Wave 2 L4 (standards/ifrs)** | `detected.standard == IFRS` | IFRS 用処理パスの選択 |
| **Wave 2 L5 (standards/usgaap)** | `detected.standard == US_GAAP` | US-GAAP 用処理パスの選択 |
| **Wave 3 L1 (normalize + statements)** | `detected.standard`, `detected.detail_level` | ディスパッチ + 包括タグ付けスキップ |
| **Free Rider (dimensions/consolidated)** | `detected.has_consolidated` | 連結/個別判定の入力 |
| **Free Rider (dimensions/fiscal_year)** | `detected.period_type` | 通期/半期の判定 |

Wave 3 での使用例:

```python
from edinet.financial.standards.detect import (
    detect_accounting_standard,
    DetailLevel,
)
from edinet.xbrl.dei import AccountingStandard, extract_dei

# DEI を先に抽出し、他の目的にも使いつつ detect に渡す
dei = extract_dei(parsed.facts)
detected = detect_accounting_standard(parsed.facts, dei=dei)

if detected.detail_level == DetailLevel.BLOCK_ONLY:
    # US-GAAP / JMIS: 構造化パースをスキップし、
    # SummaryOfBusinessResults 要素のみ抽出する
    ...
elif detected.standard == AccountingStandard.IFRS:
    # IFRS: jpigp_cor の科目マッピングを使用
    ...
elif detected.standard == AccountingStandard.JAPAN_GAAP:
    # J-GAAP: jppfs_cor の科目マッピングを使用（現行の動作）
    ...
else:
    # 判別不能: J-GAAP にフォールバック（警告付き）
    ...
```

---

## 9. 設計判断の記録

### Q: なぜ 3 つの API（`detect_accounting_standard` / `detect_from_dei` / `detect_from_namespaces`）を提供するか？

**A**: Wave 3 の統合コードでは、DEI の他のフィールド（`edinet_code`, `current_period_end_date` 等）も利用する。`detect_accounting_standard(facts, dei=dei)` で事前抽出済み DEI を渡すことで、名前空間フォールバック付きの完全判別を DEI 二重走査なしで実行できる。`detect_from_dei(dei)` は名前空間フォールバックなしの DEI のみ判別、`detect_from_namespaces(facts)` は名前空間のみ判別のショートカットで、テスタビリティと個別ユースケースに対応する。

### Q: US-GAAP / JMIS の名前空間フォールバック判別はなぜ実装しないか？

**A**: D-2.a.md より、US-GAAP と JMIS は専用タクソノミモジュールを持たない。`jpcrp_cor` 内の要素名に "USGAAP" / "JMIS" を含むが、これらは名前空間 URI ではなく concept のローカル名に含まれる。concept 名によるパターンマッチは脆弱（提出者が同名の拡張科目を定義する可能性がある）であり、DEI の方が遥かに確実。US-GAAP / JMIS 適用企業は有報・半期報告書を提出するため、必ず DEI を含む。DEI がない書類タイプ（大量保有報告書等）で US-GAAP / JMIS が必要になるユースケースは存在しない。

### Q: `DetectedStandard` に `namespace_modules` を含めるのはやりすぎではないか？

**A**: 最小限のコストで大きなデバッグ価値を提供する。名前空間フォールバック判別は推定であり、誤判定の可能性がある。利用者が `result.namespace_modules` を確認することで「この企業は jpigp を使っているから IFRS と判定された」と検証できる。`frozenset` なのでメモリオーバーヘッドは無視できる。

### Q: `detail_level` は本当に detect の責務か？ standards/jgaap 等の責務ではないか？

**A**: `detail_level` は会計基準と 1:1 で対応する静的な情報であり、科目マッピングロジック（standards/jgaap 等）とは独立している。detect の段階で確定することで、後続レーンが「この会計基準は包括タグ付けのみか」を即座に判定でき、不要なパース処理を回避できる。これは性能面でもユーザー体験面でも重要（「US-GAAP 企業の PL が空になる」という混乱を事前に防ぐ）。

### Q: `has_consolidated` / `period_type` を含めることは SRP（単一責任原則）に反しないか？

**A**: detect の主責務は「会計基準の判別」だが、判別プロセスで DEI を読む以上、`has_consolidated` / `period_type` は「既に手元にある情報を捨てない」というデータ保全の観点。別途 `extract_dei()` を呼べば取得可能だが、利用者に二重走査を強いるのは設計として劣る。frozen dataclass の追加フィールドなのでインターフェースの複雑性も最小限。

### Q: DEI と名前空間の不整合チェックは detect の責務か？

**A**: detect の責務外。DEI が `"Japan GAAP"` なのに `jpigp_cor` が存在する等の不整合は、FEATURES.md `validation/required_items` の検証項目として将来実装する。detect は最も信頼性の高い情報源（DEI）を優先し、判別結果の一貫性を保証する。利用者は必要に応じて `detect_from_namespaces(facts)` を別途呼んで自前で比較することも可能。

---

## 10. 実行チェックリスト

### Phase 1: 実装（推定 30 分）

1. `src/edinet/xbrl/standards/detect.py` を新規作成
   - `DetectionMethod` / `DetailLevel` Enum 定義
   - `DetectedStandard` frozen dataclass 定義（6 フィールド）
   - `_DETAIL_LEVEL_MAP` 定数
   - `detect_from_dei()` 関数
   - `detect_from_namespaces()` 関数
   - `detect_accounting_standard()` 関数（メインエントリポイント）

### Phase 2: テスト（推定 30 分）

2. `tests/test_xbrl/test_standards_detect.py` を新規作成
   - テストヘルパー（`_make_fact`, `_make_dei_fact`）
   - P0 テスト（T1〜T16）を全て実装
   - P1 テスト（T17〜T26）を全て実装

### Phase 3: 検証（推定 10 分）

3. `uv run ruff check src/edinet/xbrl/standards/detect.py tests/test_xbrl/test_standards_detect.py` — Lint チェック
4. `uv run pytest tests/test_xbrl/test_standards_detect.py -v` — detect テストのみ実行
5. `uv run pytest` — 全テスト実行（既存テストを壊していないことを確認）

### 完了条件

- [ ] `detect_accounting_standard()` が `dei` optional パラメータを受け取り、事前抽出済み DEI でも正しく動作する
- [ ] `detect_accounting_standard()` が 4 会計基準 + nil/未知値を正しく判別する
- [ ] DEI ベースの判別（第一手段）が正しく動作する
- [ ] 名前空間フォールバック（第二手段）が DEI 判別不能時に正しく動作する
- [ ] `DetectedStandard` に `detail_level`, `has_consolidated`, `period_type`, `namespace_modules` が正しく格納される
- [ ] US-GAAP / JMIS の `detail_level` が `BLOCK_ONLY` である
- [ ] J-GAAP / IFRS の `detail_level` が `DETAILED` である
- [ ] 未知の会計基準文字列に対して `EdinetWarning` が出る
- [ ] DEI が存在しない場合に名前空間フォールバックが正しく動作する
- [ ] 空の facts でエラーにならず UNKNOWN が返る
- [ ] `DetectedStandard` が frozen dataclass である
- [ ] P0 テスト全件 PASS
- [ ] P1 テスト全件 PASS
- [ ] 既存テスト全件 PASS
- [ ] ruff Clean

---

## 11. 変更ログ

### Rev 2（フィードバック反映）

WAVE_2_LANE_2_FEEDBACK.md のフィードバックを検証し、以下を反映した。

| ID | 判定 | 変更内容 |
|----|------|----------|
| **H-1** | ACCEPT | §4.1: `detect_accounting_standard()` に `dei: DEI \| None = None` パラメータ追加。§5.1: アルゴリズム冒頭に `if dei is None: dei = extract_dei(facts)` を追加。§4.2: 設計根拠を 3 関数体制に更新。§8: Wave 3 使用例を `dei=dei` パターンに更新。§9: Q&A を更新。§10: 完了条件に `dei` パラメータのテスト追加。P1 テストに T26 追加 |
| **H-2** | ACCEPT | §0: FEATURES.md の `ifrs-full` 引用の直後に注記を追加。EDINET は `jpigp_cor` を使用する旨を明記 |
| **M-1** | ACCEPT | §7.3 P1 テストに T25 追加: 未知文字列のメインフロー経由テスト |
| **M-2** | ACCEPT (A) | §3.3: `namespace_modules` の docstring に「DEI 判別成功時は空になる」旨を補足 |
| **M-3** | ACCEPT | §7.3 T24: parametrize テストのアサーション項目（standard, method, detail_level）を明記 |
| **M-4** | DEFER | 計画変更なし。Detroit 派テスト原則との矛盾。実装エージェントの判断に委ねる |
| **M-5** | ACCEPT | §3.1: `DetectionMethod` の docstring を「判別に**成功した**手段」に修正。UNKNOWN の説明を補足 |
| **L-1〜L-4** | ACKNOWLEDGE | 計画変更不要。実装ヒントとして参照 |

### Rev 3（Rev 2 フィードバック反映）

WAVE_2_LANE_2_FEEDBACK.md (Rev 2) のフィードバックを検証し、以下を反映した。

| ID | 判定 | 変更内容 |
|----|------|----------|
| **M-1** | ACCEPT (A) | §9: Q&A「DEI と名前空間の不整合チェックは detect の責務か？」を追加。detect の責務は判別のみであり、データ品質検証は `validation/required_items` の将来の責務とすることを明記 |
| **M-2** | PARTIALLY ACCEPT | §7.3 T6: 「DEI 要素が存在しない」の説明を「facts に jpdei_cor 名前空間の Fact が 1 つも含まれない（大量保有報告書等）→ extract_dei は全フィールド None の DEI を返す → has_consolidated=None, period_type=None」に具体化。**T27 は不採用**: 既存の T19 (`test_detect_consolidation_info_in_fallback`) が「DEI に has_consolidated はあるが accounting_standards がない → 名前空間フォールバック結果に has_consolidated が統合される」を既にカバーしており、追加は重複となるため |
| **M-3** | ACKNOWLEDGE | 計画変更なし。推奨 (A) のとおり現状維持。警告メッセージに値が含まれるため `stacklevel` のずれは実用上無害。実装エージェントの判断に委ねる |
| **L-1〜L-4** | ACKNOWLEDGE | 計画変更不要。実装ヒントとして参照 |

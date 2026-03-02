# 並列実装の安全ルール（必ず遵守）

あなたは Wave 1 / Lane 5 を担当するエージェントです。
担当機能: namespaces

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
   - `src/edinet/xbrl/_namespaces.py` (変更)
   - `tests/test_xbrl/test_namespaces.py` (新規)
   - `tests/fixtures/namespaces/` (新規ディレクトリ — フィクスチャが必要な場合)
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
     例: `tests/fixtures/namespaces/`

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl._namespaces import classify_namespace` （OK）
   - 例: `from edinet.xbrl import classify_namespace` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_namespaces.py` に作成
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

---

# LANE 5 — namespaces: 名前空間の解決

## 0. 位置づけ

Wave 1 / Lane 5 は、FEATURES.md の **XBRL Core > namespaces** に対応する。
各 Fact の名前空間 URI を解析し、**標準タクソノミ vs 提出者別タクソノミの判別基盤** を提供する。

FEATURES.md の定義:

> - namespaces: 名前空間の解決 [TODO]
>   - depends: facts
>   - detail: 各 Fact が標準タクソノミ（jppfs_cor, jpdei_cor, ifrs 等）か提出者別タクソノミかを判別。`is_standard` フラグの基盤。名前空間 URI にはタクソノミバージョン（年度）が含まれる点に注意（H-3）

FUTUREPLAN.tmp.md での位置:

> Phase 1-2: `namespaces` は `standards/*` と `taxonomy/*` の前提条件

### 現在の実装状態

`src/edinet/xbrl/_namespaces.py` は **XML インフラ用の 6 定数のみ**:

```python
NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"
NS_LINK = "http://www.xbrl.org/2003/linkbase"
NS_XLINK = "http://www.w3.org/1999/xlink"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_XML = "http://www.w3.org/XML/1998/namespace"
```

利用箇所:
- `parser.py` → `NS_LINK`, `NS_XBRLI`, `NS_XSI`, `NS_XLINK`, `NS_XML`
- `contexts.py` → `NS_XBRLI`, `NS_XBRLDI`
- `taxonomy/__init__.py` → `NS_LINK`, `NS_XLINK`, `NS_XML`

テスト: なし（定数のみのためテスト不要だった）

### Lane 5 完了時のマイルストーン

```python
from edinet.xbrl._namespaces import (
    # 既存の XML インフラ定数（そのまま維持）
    NS_XBRLI, NS_XBRLDI, NS_LINK, NS_XLINK, NS_XSI, NS_XML,
    # 新規: EDINET URI ベースパス
    EDINET_BASE,
    EDINET_TAXONOMY_BASE,
    # 新規: 追加のXBRL標準名前空間
    NS_ISO4217, NS_XBRLDT,
    # 新規: 名前空間分類
    NamespaceCategory,
    NamespaceInfo,
    classify_namespace,
    is_standard_taxonomy,
    is_filer_namespace,
    extract_taxonomy_module,
    extract_taxonomy_version,
)

# 使用例: RawFact の名前空間を分類
info = classify_namespace("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor")
assert info.category == NamespaceCategory.STANDARD_TAXONOMY
assert info.module_name == "jppfs_cor"
assert info.module_group == "jppfs"
assert info.taxonomy_version == "2025-11-01"
assert info.is_standard is True

# 提出者別名前空間の判定
info2 = classify_namespace("http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18")
assert info2.category == NamespaceCategory.FILER_TAXONOMY
assert info2.is_standard is False
assert info2.edinet_code == "E02144"

# XBRL インフラ名前空間
info3 = classify_namespace(NS_XBRLI)
assert info3.category == NamespaceCategory.XBRL_INFRASTRUCTURE
assert info3.is_standard is False  # 「標準タクソノミ」ではない（XBRL基盤）

# 便利関数（すべて classify_namespace に委譲し、キャッシュの恩恵を受ける）
assert is_standard_taxonomy("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor") is True
assert is_filer_namespace("http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18") is True
assert extract_taxonomy_module("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor") == "jppfs_cor"
assert extract_taxonomy_version("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor") == "2025-11-01"
```

---

## 1. 根拠資料

この Lane の設計は以下の QA 調査に基づく:

| QA | 関連知見 |
|----|----------|
| A-1 | 名前空間宣言の全体像。標準タクソノミは `http://disclosure.edinet-fsa.go.jp/taxonomy/` で始まる。提出者別は `http://disclosure.edinet-fsa.go.jp/` で始まるが `/taxonomy/` を含まない |
| H-2 | プレフィックス名ではなく名前空間 URI で要素を識別すべき。Clark notation で処理 |
| H-3 | 名前空間 URI にはバージョン日付が含まれる（例: `jppfs/2025-11-01/jppfs_cor`）。同一 concept でもバージョンが異なれば URI が異なる |
| D-3 | 会計基準判別に名前空間を利用可能。`jpigp_cor` の存在 → IFRS と推定可能 |

### 名前空間 URI の全パターン（A-1.a.md より）

**標準タクソノミ**（`/taxonomy/` を含む）:
| モジュール | URI パターン | 備考 |
|-----------|-------------|------|
| jppfs_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/{version}/jppfs_cor` | 日本基準 財務諸表本表 |
| jpcrp_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/{version}/jpcrp_cor` | 有報固有の報告項目 |
| jpdei_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor` | DEI（バージョン固定） |
| jpigp_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/{version}/jpigp_cor` | IFRS 財務諸表 |
| jpctl_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jpctl/{version}/jpctl_cor` | 内部統制報告書 |
| jpsps_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/{version}/jpsps_cor` | 特定有価証券 |
| jplvh_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jplvh/{version}/jplvh_cor` | 大量保有報告書 |
| jptoi_cor | `http://disclosure.edinet-fsa.go.jp/taxonomy/jptoi/{version}/jptoi_cor` | 公開買付関連 |

**提出者別タクソノミ**（`/taxonomy/` を含まない）:
```
http://disclosure.edinet-fsa.go.jp/{form_code}/{report_abbr}/{seq}/{edinet_code}-{branch}/{period_end}/{submission_num}/{filing_date}
```

例:
- `http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18`

**判定ルール**:
1. `http://disclosure.edinet-fsa.go.jp/taxonomy/` で始まる → 標準タクソノミ
2. `http://disclosure.edinet-fsa.go.jp/` で始まるが `/taxonomy/` を含まない → 提出者別
3. `http://www.xbrl.org/` で始まる → XBRL インフラ
4. その他 → 未知

---

## 2. データモデル設計

### 2.1 NamespaceCategory (enum)

名前空間の分類カテゴリ。

```python
import enum

class NamespaceCategory(enum.Enum):
    """名前空間の分類カテゴリ。"""
    STANDARD_TAXONOMY = "standard_taxonomy"
    """EDINET 標準タクソノミ（jppfs_cor, jpcrp_cor, jpdei_cor, jpigp_cor 等）。"""

    FILER_TAXONOMY = "filer_taxonomy"
    """提出者別タクソノミ（企業固有の拡張科目）。"""

    XBRL_INFRASTRUCTURE = "xbrl_infrastructure"
    """XBRL 標準の基盤名前空間（xbrli, xlink, link, xbrldi 等）。"""

    OTHER = "other"
    """上記に該当しない名前空間（iso4217、XML Schema 等を含む）。"""
```

### 2.2 NamespaceInfo (frozen dataclass)

名前空間 URI の解析結果を保持する。

```python
@dataclass(frozen=True, slots=True)
class NamespaceInfo:
    """名前空間 URI の解析結果。

    Attributes:
        uri: 元の名前空間 URI。
        category: 分類カテゴリ。
        is_standard: EDINET 標準タクソノミであれば True。
            STANDARD_TAXONOMY の場合のみ True。XBRL_INFRASTRUCTURE は False。
        module_name: タクソノミモジュール名（例: "jppfs_cor"）。
            STANDARD_TAXONOMY の場合のみ値を持つ。
        module_group: タクソノミモジュールグループ（例: "jppfs"）。
            STANDARD_TAXONOMY かつ正規表現マッチ時のみ値を持つ。
            後続レーン（standards/detect 等）での会計基準分岐に使用。
        taxonomy_version: タクソノミバージョン日付（例: "2025-11-01"）。
            STANDARD_TAXONOMY の場合のみ値を持つ。
        edinet_code: EDINET コード（例: "E02144"）。
            FILER_TAXONOMY の場合のみ値を持つ。
    """
    uri: str
    category: NamespaceCategory
    is_standard: bool
    module_name: str | None = None
    module_group: str | None = None
    taxonomy_version: str | None = None
    edinet_code: str | None = None
```

**設計根拠**:
- `is_standard` を独立フィールドにする理由: 後続レーン（taxonomy/custom_detection 等）が `fact.namespace_info.is_standard` で即座にアクセスできるようにするため。`category == STANDARD_TAXONOMY` の冗長性は許容する
- `module_name` は Clark notation のローカル名部分ではなく、URI パスから抽出したモジュール識別子。これにより `{jppfs/2025-11-01/jppfs_cor}NetSales` と `{jppfs/2024-11-01/jppfs_cor}NetSales` を同一モジュールとして扱える（H-3 の要件）
- `module_group` は正規表現ですでにキャプチャしている `module_group` グループをそのまま公開する。後続レーン（Wave 2 L2: standards/detect 等）が `info.module_group == "jppfs"` で会計基準分岐するため、`module_name.split("_")[0]` のような文字列操作を利用者に強いない設計
- `edinet_code` は提出者別名前空間からのみ抽出可能（A-1 の知見）

---

## 3. 実装ステップ

### Step 1: 定数の追加（追加のみ、変更・削除なし）

既存の 6 定数は **一切変更しない**。以下を追加する:

```python
# --- 追加: XBRL 標準名前空間 ---
# ISO 4217 通貨コード
NS_ISO4217 = "http://www.xbrl.org/2003/iso4217"
# XBRL Dimensions Taxonomy
NS_XBRLDT = "http://xbrl.org/2005/xbrldt"
# XBRL 数値型（DTR: Data Type Registry）
NS_NUM = "http://www.xbrl.org/dtr/type/numeric"
# XBRL 非数値型（DTR: Data Type Registry）
NS_NONNUM = "http://www.xbrl.org/dtr/type/non-numeric"

# --- 追加: EDINET URI ベースパス ---
EDINET_BASE = "http://disclosure.edinet-fsa.go.jp/"
"""EDINET の名前空間 URI のベースドメイン。標準タクソノミ・提出者別タクソノミの両方がこのプレフィックスで始まる。"""

EDINET_TAXONOMY_BASE = "http://disclosure.edinet-fsa.go.jp/taxonomy/"
"""EDINET 標準タクソノミの名前空間 URI はこのプレフィックスで始まる。"""
```

**MF-1 対応**: 旧 `EDINET_FILER_BASE` は `EDINET_BASE` にリネームした。元の名称は「提出者用ベース」と読めるが、実際には標準タクソノミ URI も同じプレフィックスで始まるため誤解を招く。`EDINET_BASE` はドメイン全体のベースとして正確な命名である。

**MF-2 対応**: `NS_NUM` / `NS_NONNUM` は XBRL の Data Type Registry（DTR）名前空間であり、Fact の `type` 属性値の定義に使われる。XBRL 仕様の一部ではあるが、XBRL インスタンスの構造定義（xbrli, link 等）とは性質が異なるため `OTHER` に分類する。現行パーサーでは使用していないが、後続レーン（units 等）で必要になる可能性があるため定数として追加しておく。

**制約**: 既存の `NS_XBRLI`, `NS_XBRLDI`, `NS_LINK`, `NS_XLINK`, `NS_XSI`, `NS_XML` は名前・値ともに変更しない。`parser.py`, `contexts.py`, `taxonomy/__init__.py` が import しているため。

### Step 2: 既知の XBRL インフラ名前空間セットの定義

名前空間分類で使用する内部定数:

```python
_XBRL_INFRASTRUCTURE_URIS: frozenset[str] = frozenset({
    NS_XBRLI,
    NS_XBRLDI,
    NS_LINK,
    NS_XLINK,
    NS_XBRLDT,
})
"""XBRL インフラストラクチャに分類される名前空間 URI のセット。"""
```

### Step 3: 名前空間 URI パーサーの実装

標準タクソノミ URI のパターン:
```
http://disclosure.edinet-fsa.go.jp/taxonomy/{module_group}/{version}/{module_name}
```

正規表現で分解:

```python
import re

_STANDARD_TAXONOMY_PATTERN = re.compile(
    r"^http://disclosure\.edinet-fsa\.go\.jp/taxonomy/"
    r"(?P<module_group>[a-z]+)/"
    r"(?P<version>\d{4}-\d{2}-\d{2})/"
    r"(?P<module_name>[a-z_]+)$"
)
"""標準タクソノミ URI のパターン。

例: http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor
→ module_group="jppfs", version="2025-11-01", module_name="jppfs_cor"
"""
```

提出者別タクソノミ URI のパターン:
```
http://disclosure.edinet-fsa.go.jp/{form_code}/{report_abbr}/{seq}/{edinet_code}-{branch}/{period_end}/{submission_num}/{filing_date}
```

```python
_FILER_TAXONOMY_PATTERN = re.compile(
    r"^http://disclosure\.edinet-fsa\.go\.jp/"
    r"(?!taxonomy/)"  # /taxonomy/ を含まない
    r"[^/]+/[^/]+/[^/]+/"
    r"(?P<edinet_code>[A-Z0-9]+)-(?P<branch>\d+)/"
)
"""提出者別タクソノミ URI のパターン。

例: http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18
→ edinet_code="E02144", branch="000"
"""
```

### Step 4: 分類関数の実装

```python
def classify_namespace(uri: str) -> NamespaceInfo:
    """名前空間 URI を解析し、分類結果を返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        解析結果の NamespaceInfo。
    """
```

分類ロジック（MF-4 対応: フォールバック分岐を明示）:
1. `_STANDARD_TAXONOMY_PATTERN` にマッチ → `STANDARD_TAXONOMY`（`module_name`, `module_group`, `taxonomy_version` あり）
1b. `EDINET_TAXONOMY_BASE` で始まるが正規表現に不一致 → `STANDARD_TAXONOMY`（`module_name=None`, `module_group=None`, `taxonomy_version=None`）。将来の URI フォーマット変更に対する安全側設計
2. `EDINET_BASE` で始まり `EDINET_TAXONOMY_BASE` で始まらない → `FILER_TAXONOMY`（`_FILER_TAXONOMY_PATTERN` でマッチすれば `edinet_code` を抽出、不一致でも `FILER_TAXONOMY` として `edinet_code=None`）
3. `_XBRL_INFRASTRUCTURE_URIS` に含まれる → `XBRL_INFRASTRUCTURE`
4. その他 → `OTHER`

### Step 5: 便利関数の実装

**SF-1 対応**: すべての便利関数は内部で `classify_namespace()` に委譲する。これにより `lru_cache` の恩恵を受け、同一 URI に対する重複パースを避ける。独自にパースしてはならない。

```python
def is_standard_taxonomy(uri: str) -> bool:
    """名前空間 URI が EDINET 標準タクソノミかどうかを返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        標準タクソノミであれば True。
    """
    return classify_namespace(uri).is_standard

def is_filer_namespace(uri: str) -> bool:
    """名前空間 URI が提出者別タクソノミかどうかを返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        提出者別タクソノミであれば True。
    """
    return classify_namespace(uri).category == NamespaceCategory.FILER_TAXONOMY

def extract_taxonomy_module(uri: str) -> str | None:
    """名前空間 URI からタクソノミモジュール名を抽出する。

    Args:
        uri: 名前空間 URI。

    Returns:
        モジュール名（例: "jppfs_cor"）。標準タクソノミでない場合 None。
    """
    return classify_namespace(uri).module_name

def extract_taxonomy_version(uri: str) -> str | None:
    """名前空間 URI からタクソノミバージョン日付を抽出する。

    Args:
        uri: 名前空間 URI。

    Returns:
        バージョン日付（例: "2025-11-01"）。標準タクソノミでない場合 None。
    """
    return classify_namespace(uri).taxonomy_version
```

**パフォーマンス考慮**: `classify_namespace` は同一 URI に対して繰り返し呼ばれる可能性がある（1つの Filing で数百〜数千の Fact が同じ名前空間を持つ）。`functools.lru_cache` を適用してメモ化する。

```python
from functools import lru_cache

@lru_cache(maxsize=256)
def classify_namespace(uri: str) -> NamespaceInfo:
    ...
```

---

## 4. テスト設計

`tests/test_xbrl/test_namespaces.py` に以下のテストを作成する。

### 4.1 既存定数の不変性テスト

```python
def test_existing_constants_unchanged():
    """既存の 6 定数が変更されていないことを確認する。"""
    assert NS_XBRLI == "http://www.xbrl.org/2003/instance"
    assert NS_XBRLDI == "http://xbrl.org/2006/xbrldi"
    assert NS_LINK == "http://www.xbrl.org/2003/linkbase"
    assert NS_XLINK == "http://www.w3.org/1999/xlink"
    assert NS_XSI == "http://www.w3.org/2001/XMLSchema-instance"
    assert NS_XML == "http://www.w3.org/XML/1998/namespace"
```

### 4.2 標準タクソノミの分類テスト

```python
@pytest.mark.parametrize("uri,expected_module,expected_group,expected_version", [
    # J-GAAP 財務諸表
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor", "jppfs_cor", "jppfs", "2025-11-01"),
    # 有報固有
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor", "jpcrp_cor", "jpcrp", "2025-11-01"),
    # DEI（バージョン固定）
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor", "jpdei_cor", "jpdei", "2013-08-31"),
    # IFRS
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor", "jpigp_cor", "jpigp", "2025-11-01"),
    # 旧バージョン（H-3: バージョン横断テスト）
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor", "jppfs_cor", "jppfs", "2024-11-01"),
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2022-11-01/jppfs_cor", "jppfs_cor", "jppfs", "2022-11-01"),
    # 大量保有報告書
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jplvh/2025-11-01/jplvh_cor", "jplvh_cor", "jplvh", "2025-11-01"),
    # 公開買付
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jptoi/2025-11-01/jptoi_cor", "jptoi_cor", "jptoi", "2025-11-01"),
    # 内部統制
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jpctl/2025-11-01/jpctl_cor", "jpctl_cor", "jpctl", "2025-11-01"),
    # 特定有価証券
    ("http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2025-11-01/jpsps_cor", "jpsps_cor", "jpsps", "2025-11-01"),
])
def test_standard_taxonomy_classification(uri, expected_module, expected_group, expected_version):
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.STANDARD_TAXONOMY
    assert info.is_standard is True
    assert info.module_name == expected_module
    assert info.module_group == expected_group
    assert info.taxonomy_version == expected_version
```

### 4.3 提出者別タクソノミの分類テスト

```python
@pytest.mark.parametrize("uri,expected_edinet_code", [
    # J-GAAP サンプル（A-1.a.md [F4]）
    (
        "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/X99001-000/2026-03-31/01/2026-06-12",
        "X99001",
    ),
    # IFRS サンプル（A-1.a.md [F5]）
    (
        "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/X99002-000/2026-03-31/01/2026-06-12",
        "X99002",
    ),
    # トヨタ実データ（A-1.a.md [F6]）
    (
        "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18",
        "E02144",
    ),
])
def test_filer_taxonomy_classification(uri, expected_edinet_code):
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.FILER_TAXONOMY
    assert info.is_standard is False
    assert info.edinet_code == expected_edinet_code
```

### 4.4 XBRL インフラ名前空間の分類テスト

```python
@pytest.mark.parametrize("uri", [
    NS_XBRLI,
    NS_XBRLDI,
    NS_LINK,
    NS_XLINK,
    NS_XBRLDT,
])
def test_xbrl_infrastructure_classification(uri):
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.XBRL_INFRASTRUCTURE
    assert info.is_standard is False
```

### 4.5 その他の名前空間の分類テスト

MF-2 対応: `NS_NUM`, `NS_NONNUM` を含める。MF-3 対応: `NS_XSI`, `NS_XML` が `OTHER` である理由は Section 7 に記載。

```python
@pytest.mark.parametrize("uri", [
    NS_XSI,       # W3C 汎用名前空間（XBRL 固有ではない）
    NS_XML,       # W3C 汎用名前空間（XBRL 固有ではない）
    NS_ISO4217,   # 通貨コード（XBRL DTR 関連）
    NS_NUM,       # XBRL Data Type Registry: 数値型
    NS_NONNUM,    # XBRL Data Type Registry: 非数値型
    "http://example.com/unknown",
    "",
])
def test_other_namespace_classification(uri):
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.OTHER
    assert info.is_standard is False
```

### 4.5b 標準タクソノミのフォールバック分類テスト（MF-4 対応）

`EDINET_TAXONOMY_BASE` で始まるが既知の正規表現パターンに合わない URI。

```python
@pytest.mark.parametrize("uri", [
    "http://disclosure.edinet-fsa.go.jp/taxonomy/unknown/format",
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/invalid-date/jppfs_cor",
    "http://disclosure.edinet-fsa.go.jp/taxonomy/",
])
def test_standard_taxonomy_unknown_format(uri):
    """EDINET_TAXONOMY_BASE で始まるが既知パターンに合わない URI は STANDARD_TAXONOMY に分類される。"""
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.STANDARD_TAXONOMY
    assert info.is_standard is True
    assert info.module_name is None
    assert info.module_group is None
    assert info.taxonomy_version is None
```

### 4.6 便利関数のテスト

```python
def test_is_standard_taxonomy():
    assert is_standard_taxonomy("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor") is True
    assert is_standard_taxonomy(NS_XBRLI) is False
    assert is_standard_taxonomy("http://example.com/foo") is False

def test_is_filer_namespace():
    assert is_filer_namespace("http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18") is True
    assert is_filer_namespace("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor") is False

def test_extract_taxonomy_module():
    assert extract_taxonomy_module("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor") == "jppfs_cor"
    assert extract_taxonomy_module("http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor") == "jpigp_cor"
    assert extract_taxonomy_module(NS_XBRLI) is None

def test_extract_taxonomy_version():
    assert extract_taxonomy_version("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor") == "2025-11-01"
    assert extract_taxonomy_version("http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor") == "2013-08-31"
    assert extract_taxonomy_version(NS_XBRLI) is None
```

### 4.7 バージョン横断テスト（H-3 の要件）

```python
def test_same_module_different_versions():
    """同一モジュールの異なるバージョンが同一モジュール名を返すことを確認する。"""
    versions = ["2020-11-01", "2021-11-01", "2022-11-01", "2023-12-01", "2024-11-01", "2025-11-01"]
    for ver in versions:
        uri = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/{ver}/jppfs_cor"
        assert extract_taxonomy_module(uri) == "jppfs_cor"
        assert extract_taxonomy_version(uri) == ver
        assert is_standard_taxonomy(uri) is True
```

### 4.8 キャッシュの動作テスト

SF-2 考慮: `is` テストは frozen dataclass + lru_cache の組み合わせによる意図的な設計保証であり、リファクタリング耐性の観点では議論の余地がある。ただし、frozen dataclass がキャッシュと組み合わせて同一オブジェクトを返すことは後続レーンでの identity 比較やメモリ効率に影響するため、設計判断として残す。

SF-4 対応: テスト間のキャッシュ汚染を防ぐため、autouse fixture で `cache_clear()` を実行する。

```python
@pytest.fixture(autouse=True)
def _clear_namespace_cache():
    """テスト間のキャッシュ汚染を防ぐ。"""
    classify_namespace.cache_clear()
    yield
    classify_namespace.cache_clear()

def test_classify_returns_identical_object_for_same_uri():
    """同一 URI に対する呼び出しが同一オブジェクトを返すことを確認する。

    frozen dataclass + lru_cache の組み合わせによる意図的な設計保証。
    """
    uri = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
    result1 = classify_namespace(uri)
    result2 = classify_namespace(uri)
    assert result1 == result2  # 等値性
    assert result1 is result2  # 同一オブジェクト（キャッシュヒット）
```

---

## 5. ファイル変更サマリ

| ファイル | 操作 | 内容 |
|---------|------|------|
| `src/edinet/xbrl/_namespaces.py` | **変更** | 定数追加（4個）+ ベースURL定数（2個）+ enum（1個）+ dataclass（1個、`module_group` フィールド含む）+ 関数（5個）+ 内部正規表現（2個）|
| `tests/test_xbrl/test_namespaces.py` | **新規** | 上記テスト群（約 10 テスト関数、parametrize で約 35 ケース）+ autouse fixture |

### 既存モジュールへの影響

- **影響なし**: 既存の 6 定数は名前・値・型すべて不変。新しい定数と関数は**追加のみ**
- `parser.py`: import 文変更不要（既存の `NS_*` のみ使用）
- `contexts.py`: import 文変更不要（既存の `NS_XBRLI`, `NS_XBRLDI` のみ使用）
- `taxonomy/__init__.py`: import 文変更不要（既存の `NS_LINK`, `NS_XLINK`, `NS_XML` のみ使用）
- 既存テスト: 一切変更なし

---

## 6. 後続レーンとの接続点

Lane 5 の出力は以下のレーンで利用される:

| 利用先 | 利用方法 |
|--------|----------|
| **Wave 2 L2: standards/detect** | `classify_namespace()` + DEI の `AccountingStandardsDEI` 値で会計基準を判別 |
| **Wave 2 L3-5: standards/jgaap, ifrs, usgaap** | `extract_taxonomy_module()` でモジュール名を取得し、対応する standards 処理を選択 |
| **Wave 2 Free Rider: taxonomy/labels** | `extract_taxonomy_version()` でラベル辞書のキー設計に使用 |
| **Wave 2 Free Rider: taxonomy/versioning** | `extract_taxonomy_version()` でバージョン間マッピング |
| **Wave 2 Free Rider: taxonomy/custom_detection** | `is_standard_taxonomy()` で `is_standard` フラグ付与 |

Lane 5 が提供する API は Wave 2 の **5 つ以上のレーン/Free Rider** で使われる基盤であり、インターフェースの安定性が極めて重要。

---

## 7. 設計判断の記録

### Q: なぜ新しいモジュール（`namespace_resolver.py` 等）を作らず `_namespaces.py` に集約するか？

**A**: FUTUREPLAN.tmp.md の Wave 1 ファイル割り当てで L5 のスコープは `_namespaces.py` の変更と定められている。新モジュールを作ると並列安全性計画との不整合が生じる。また、名前空間分類は純粋関数 + 定数であり、ファイルサイズも 200 行程度に収まるため、既存ファイルへの追加で十分。

### Q: `classify_namespace` の結果を `RawFact` に埋め込まないのか？

**A**: `RawFact` は `parser.py` が生成する frozen dataclass であり、L5 のスコープ外。RawFact にフィールドを追加する場合は統合タスクで行う。Lane 5 は純粋な名前空間分類ユーティリティを提供し、呼び出し側（後続レーン）が `classify_namespace(fact.namespace_uri)` で使う設計とする。

### Q: 正規表現パターンに合わない EDINET URI をどう扱うか？

**A**: `EDINET_TAXONOMY_BASE` で始まるが正規表現に合わない URI は `STANDARD_TAXONOMY` として扱い、`module_name`, `module_group`, `taxonomy_version` を `None` にする。将来のタクソノミ URI フォーマット変更に対する安全側の設計。提出者判定は `EDINET_BASE` 開始 + `EDINET_TAXONOMY_BASE` 非開始の 2 条件で行うため、正規表現の部分マッチ失敗でも分類自体は正しく動作する。

### Q: `lru_cache` のサイズ 256 は適切か？

**A**: 1 つの Filing に出現する名前空間 URI のユニーク数は通常 10 前後（A-1 の調査より J-GAAP で約 10、IFRS で約 11）。複数 Filing を処理する場合でもバージョン違いの URI を含めて 50〜100 種類以内に収まるため、256 は十分なマージン。

### Q: なぜ `NS_XSI` / `NS_XML` を `XBRL_INFRASTRUCTURE` ではなく `OTHER` に分類するか？（MF-3）

**A**: `NS_XSI`（`http://www.w3.org/2001/XMLSchema-instance`）と `NS_XML`（`http://www.w3.org/XML/1998/namespace`）は W3C が定める汎用 XML 名前空間であり、XBRL 固有ではない。HTML、SVG、SOAP 等あらゆる XML 応用で使われる。一方、`_XBRL_INFRASTRUCTURE_URIS` に含めている `NS_XBRLI`, `NS_XBRLDI`, `NS_LINK`, `NS_XLINK`, `NS_XBRLDT` は XBRL 仕様が定義する名前空間である。`NS_XLINK` は W3C 仕様だが XBRL リンクベースで本質的に使用されるため XBRL インフラに含めた。

後続レーンの開発者が `NS_XSI` を `XBRL_INFRASTRUCTURE` と期待する可能性があるが、分類の一貫性（XBRL 仕様に由来するか否か）を優先する。

### Q: なぜ `NS_NUM` / `NS_NONNUM` を `XBRL_INFRASTRUCTURE` ではなく `OTHER` に分類するか？（MF-2）

**A**: `NS_NUM`（`http://www.xbrl.org/dtr/type/numeric`）と `NS_NONNUM`（`http://www.xbrl.org/dtr/type/non-numeric`）は XBRL の Data Type Registry（DTR）の名前空間であり、Fact の `type` 属性値の型定義に使われる。XBRL 仕様の一部ではあるが、Fact の名前空間 URI として出現するものではなく（`xbrli:xbrl` のルート要素の名前空間宣言には通常含まれない — A-1.a.md [F4] 参照）、パーサーのコンテキストでは「インフラストラクチャ」として分類する必要性が薄い。現行パーサーでは使用しておらず、後続レーン（units 等）で使用する可能性があるため定数としてのみ追加する。

### Q: 提出者別 EDINET コードの正規表現パターンはなぜ緩い `[A-Z0-9]+` を使うか？（SF-3）

**A**: EDINET コードは現時点では `E` + 5桁数字（例: `E02144`）または `X` + 5桁数字（サンプル用、例: `X99001`）のパターンだが、将来のコード体系変更に備えて `[A-Z0-9]+` と緩く定義する。より厳密な `[A-Z]\d{5}` にするとフォーマット変更時にパーサーが壊れるリスクがある。このライブラリの責務は「名前空間 URI の分類」であり、EDINET コードのバリデーションではないため、寛容なパターンが適切。

### Q: EDINET の IFRS 企業は IASB の `ifrs-full` 名前空間を使わないのか？（C-2）

**A**: A-1.a.md [F10], D-3.a.md の知見より、EDINET では IASB の `ifrs-full`（`http://xbrl.ifrs.org/taxonomy/...`）名前空間は使用されない。代わりに EDINET 独自の `jpigp_cor`（`http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/...`）が使われる。したがって本モジュールでは `ifrs-full` の分類ルールは不要であり、`jpigp_cor` の存在をもって IFRS 適用を推定する。この情報は後続の Wave 2 L2 `standards/detect` の実装で重要。

### Q: `_XBRL_INFRASTRUCTURE_URIS` の将来拡張性は？（C-3）

**A**: `frozenset` を使用しているため、将来の名前空間追加は新しい frozenset を再構築するか、モジュール定数を追加する形で対応可能。XBRL Formula 関連名前空間（`http://xbrl.org/2008/formula` 等、FEATURES.md C-12 で `[v0.2.0+]` として記載）は現時点では追加しないが、同様のパターンで拡張できる。

### Q: `classify_namespace(None)` や不正な型の入力に対するエラーハンドリングは？（C-4）

**A**: 型アノテーション `str` を信頼し、ランタイムのガード（`isinstance` チェック等）は追加しない。Python のダックタイピングの方針に従い、不正な型が渡された場合は自然に `TypeError` / `AttributeError` が発生する。このモジュールは内部 API であり、呼び出し元（後続レーン）は型チェッカーによって正しい型を保証される。

---

## 8. フィードバック反映記録

WAVE_1_LANE_5_FEEDBACK.md の各指摘に対する対応結果:

| ID | 種別 | 対応 | 変更箇所 |
|----|------|------|----------|
| MF-1 | MUST FIX | **採用**: `EDINET_FILER_BASE` → `EDINET_BASE` にリネーム | Step 1, マイルストーン |
| MF-2 | MUST FIX | **採用**: `NS_NUM`/`NS_NONNUM` を `OTHER` に分類、テスト追加 | Step 1, テスト 4.5, Section 7 |
| MF-3 | MUST FIX | **採用**: `NS_XSI`/`NS_XML` が `OTHER` である理由を明記 | Section 7 |
| MF-4 | MUST FIX | **採用**: フォールバック分岐（Step 1b, 2b）を明示化、テスト追加 | Step 4, テスト 4.5b |
| SF-1 | SHOULD FIX | **採用**: 便利関数は `classify_namespace` に委譲する旨を明記 | Step 5 |
| SF-2 | SHOULD FIX | **一部採用**: `is` テストは残しつつ等値テストも併記、設計判断として注記 | テスト 4.8 |
| SF-3 | SHOULD FIX | **文書のみ**: 正規表現は緩いパターンを維持、理由を Section 7 に追記 | Section 7 |
| SF-4 | SHOULD FIX | **採用**: autouse fixture で `cache_clear()` を追加 | テスト 4.8 |
| C-1 | CONSIDER | **採用**: `module_group` フィールドを `NamespaceInfo` に追加 | Section 2.2, マイルストーン, テスト 4.2 |
| C-2 | CONSIDER | **採用**: IFRS の `jpigp_cor` に関する注記を Section 7 に追加 | Section 7 |
| C-3 | CONSIDER | **採用**: `_XBRL_INFRASTRUCTURE_URIS` の将来拡張性を注記 | Section 7 |
| C-4 | CONSIDER | **採用**: エラーハンドリング方針を Section 7 に追加 | Section 7 |

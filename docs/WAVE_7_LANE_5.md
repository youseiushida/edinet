# Wave 7 / Lane 5 — Taxonomy: 非標準科目 → 標準科目マッピング (B5)

# エージェントが守るべきルール

## 実行順序

**Lane 5 は全レーン中で最後に実行する。**
他の全レーン（L1〜L4, L6〜L8）が完了した後に開始すること。
これにより `custom.py` を直接拡張でき、一時モジュール + 統合 merge が不要になる。

## 安全ルール（必ず遵守）

あなたは Wave 7 / Lane 5 を担当するエージェントです。
担当機能: Calculation Linkbase ベースの非標準科目 → 標準科目マッピング

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/financial/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **変更・作成してよいファイル**
   本レーンは最後に実行するため、`custom.py` を直接拡張する:
   - `src/edinet/xbrl/taxonomy/custom.py` (変更: CalculationLinkbase 対応追加)
   - `tests/test_xbrl/test_custom_detection.py` (変更: 新テストケース追加)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - `CustomItemInfo` への新フィールドは必ずデフォルト値を付与（後方互換）
   - `detect_custom_items()` への新引数は keyword-only + デフォルト None
   - 既存のフィールド名・型・関数シグネチャを変更してはならない
   - 既存の定数名を変更・削除してはならない（追加のみ可）

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/taxonomy_mini/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/xbrl_fragments/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/linkbase_calculation/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャは XML ファイルではなく、テストファイル内で
     `CalculationLinkbase` / `CalculationTree` / `CalculationArc` を
     直接構築するインメモリヘルパーを使用すること（既存の `_make_gs_tree()` パターンに準拠）

### 推奨事項

6. **テストケースの追加方針**
   - `tests/test_xbrl/test_custom_detection.py` に新テストクラスを追加
   - 既存テストクラス・テストメソッドは変更しないこと
   - 新テストクラス名: `TestCalculationMapping`, `TestFindCustomConcepts`, `TestIsStandardHrefIntegration`
   - テスト用の `CalculationLinkbase` は `_make_calc_linkbase()` ヘルパーで
     インメモリ構築する（既存の `_make_gs_tree()` と同じパターン）

7. **他モジュールの利用は import のみ**
   - Wave 6 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.linkbase.calculation` (CalculationLinkbase, CalculationArc, CalculationTree)
     - `edinet.xbrl._linkbase_utils` (split_fragment_prefix_local 等)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

8. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 5 — Taxonomy: 非標準科目 → 標準科目マッピング (B5)

## 0. 位置づけ

### 設計方針: `custom.py` への統合

**`standard_mapping.py` は作成しない。** `custom.py` を直接拡張する。

理由:
- `custom.py` は既に「非標準科目を検出し、標準科目の対応関係を推定する」モジュール
- DefinitionLinkbase (general-special) による推定が実装済み
- CalculationLinkbase (summation-item) による推定は**同じユーザーゴールの別データソース**
- 別モジュールにすると「同じ問いに答える 2 つの API」が生じ、ライブラリとして混乱の元
- `_is_standard_href()` の重複定義・private import ハックも不要になる

### FEATURES.md との対応

| Feature Key | 内容 |
|-------------|------|
| `taxonomy/standard_mapping` | 非標準科目 → 標準科目の祖先マッピング |

Calculation Linkbase の祖先走査により、提出者独自の拡張科目が「どの標準科目の配下にあるか」を逆引きする。クロス企業比較の基盤。

### SCOPE.md との関係

SCOPE.md が定める「1件の XBRL → 構造化オブジェクト」変換パイプラインの一部。拡張科目の標準科目への正規化は、企業間比較可能な DataFrame 構築に必要。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.linkbase.calculation` | `CalculationLinkbase.parent_of()` で 1 段ずつ祖先走査、`CalculationArc.parent_href` で href 取得 | read-only import |
| `edinet.xbrl.taxonomy.custom` (自身) | `_is_standard_href()` — 同一ファイル内の既存関数をそのまま利用 | 同一ファイル |

**注意**: `_namespaces.is_standard_taxonomy()` は **名前空間 URI** を受け付ける関数であり、`CalculationArc` の href（XSD 相対パス + フラグメント形式）には使用できない。href ベースの判定には同一ファイル内の `_is_standard_href()` をそのまま利用する。

### 保守影響 (MAINTENANCE.md)

**増加なし。** 追加されるコードは全て既存の CalculationLinkbase を動的に走査するアルゴリズムであり、新たなハードコード（concept 名、URI パターン、定数）はゼロ。`_FILER_XSD_RE`（L56）と `_is_standard_href()`（L182-200）をそのまま再利用するため、タクソノミ年次更新でも追加の保守は発生しない。MAINTENANCE.md の変更は不要。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| E-6 | **直接** | 拡張科目の実態。1社あたり 4〜91 個。種類: monetaryItemType, domainItemType, textBlockItemType |
| C-7 | **直接** | Calculation Linkbase の木構造。weight は 1/-1 のみ。arcrole は summation-item のみ |

---

## 1. 背景知識

### 1.1 拡張科目の実態 (E-6 より)

全ての提出者が拡張科目を使用。サンプル調査結果:

| 提出者 | 拡張科目数 | 主な種類 |
|--------|-----------|---------|
| トヨタ自動車 | 91 | monetaryItemType, domainItemType |
| ベルーナ | 25 | monetaryItemType, textBlockItemType |
| 大容テクノ | 4 | monetaryItemType |
| 三菱UFJ FG | 82 | monetaryItemType, domainItemType |
| 識学 | 28 | monetaryItemType, textBlockItemType |

**monetaryItemType**（金額型）の拡張科目が最も重要。これらは Calculation Linkbase 上で標準科目の子として配置される。

例: `受注損失引当金繰入額`（提出者独自）→ `販売費及び一般管理費`（標準）→ `営業利益`（標準）

### 1.2 Calculation Linkbase の木構造 (C-7 より)

| 特性 | 値 |
|------|-----|
| weight 属性 | **1 と -1 のみ**（185 arc 検証済み） |
| arcrole | `summation-item` のみ |
| 木構造 | 親 = 集約科目、子 = 構成要素。weight=1 は加算、weight=-1 は減算 |
| 循環 | CalculationLinkbase が循環検出済み（`ancestors_of()` で visited 防御） |

### 1.3 既存 API

`CalculationLinkbase` が既に提供する祖先走査 API:

```python
# 直接の親
parents = calc_linkbase.parent_of("CustomExpense", role_uri=role_uri)
# → tuple[CalculationArc, ...]
# CalculationArc.parent_href から標準/非標準を O(1) 判定可能
```

**重要**: `ancestors_of()` は **ローカル名のみ** を返し href 情報を持たないため、標準/非標準判定には使用できない。`parent_of()` で 1 段ずつ辿り、各ステップの `CalculationArc.parent_href` から判定する。

### 1.4 既存の `custom.py` が提供する基盤

`custom.py` は既に以下を実装済み:

| 既存機能 | 内容 | Lane 5 での利用 |
|---|---|---|
| `_is_standard_href(href)` | XSD ファイル名の `jpcrp\d+` 先頭一致で提出者/標準を判定 | **そのまま利用**（同一ファイル内） |
| `_find_standard_ancestor()` | DefinitionLinkbase の general-special を辿り標準親を推定 | 参考（CalculationLinkbase 版を同じパターンで実装） |
| `_build_parent_index()` | general-special arc の逆引きインデックス構築 | 参考（CalculationLinkbase 版を同じパターンで実装） |
| `detect_custom_items()` | Statements 内の非標準科目を分類 | **拡張**（`calculation_linkbase` 引数を追加） |
| `CustomItemInfo` | 非標準科目の分析結果 | **拡張**（Calculation 由来のフィールドを追加） |

### 1.5 2 つの Linkbase が提供する異なる情報

| | DefinitionLinkbase (既存) | CalculationLinkbase (Lane 5 追加) |
|---|---|---|
| arcrole | `general-special` | `summation-item` |
| 意味 | 「X は Y の**特殊化**」（意味的分類） | 「X は Y の**内訳**」（計算関係） |
| 例 | 受注損失引当金 → 引当金繰入額 | 受注損失引当金 → 販管費合計 |
| カバレッジ | general-special arc がある科目 | 計算関係がある科目 |
| ユースケース | 概念の意味的な対応を知りたいとき | 財務諸表上の位置（どの集計科目の下か）を知りたいとき |

**両方を統合して提供する**ことで、ユーザーは `detect_custom_items()` 一発で全情報を得られる。

---

## 2. ゴール

完了条件:

```python
from edinet.xbrl.taxonomy.custom import detect_custom_items, find_custom_concepts

# 典型的なワークフロー: detect_custom_items() に CalculationLinkbase を渡す
result = detect_custom_items(
    statements,
    definition_linkbase=def_trees,      # 既存: general-special
    calculation_linkbase=calc_linkbase,  # 新規: summation-item
)

# 既存フィールド（後方互換）
ci = result.custom_items[0]
ci.parent_standard_concept          # general-special 由来（既存）

# 新規フィールド
ci.calculation_ancestor             # summation-item 由来の最近接標準科目
ci.calculation_path                 # 計算階層の経路（custom → ... → standard）
ci.calculation_role_uri             # マッピングが特定された role URI

# calculation_linkbase を渡さない場合は新フィールドが全て None（後方互換）
result2 = detect_custom_items(statements)
assert result2.custom_items[0].calculation_ancestor is None

# find_custom_concepts(): CalculationLinkbase から非標準科目を自動検出
custom_names = find_custom_concepts(calc_linkbase)
# → ("CustomExpenseA", "CustomRevenueB", ...)  重複除去・ソート済み
```

---

## 3. スコープ / 非スコープ

### 3.1 スコープ

| # | 内容 | 対応 |
|---|------|------|
| S1 | Calculation Linkbase の祖先走査で最も近い標準科目を特定 | `detect_custom_items(calculation_linkbase=...)` |
| S2 | 非標準 → 標準の経路（path）の記録 | `CustomItemInfo.calculation_path` |
| S3 | 複数の role URI をまたいだマッピング | role_uri 未指定で全 role 横断 |
| S4 | 標準科目が見つからない場合のグレースフル処理 | フィールド値が `None` |
| S5 | CalculationLinkbase 内の全非標準科目の自動検出 | `find_custom_concepts()` |
| S6 | detect_custom_items() の既存動作を完全に維持 | 新引数は全て keyword-only + デフォルト None |

### 3.2 非スコープ

| # | 内容 | 理由 |
|---|------|------|
| N1 | Presentation Linkbase ベースのマッピング | Calculation の方が意味的に正確（加減算関係） |
| N2 | wider-narrower arcrole | EDINET では使用されない (E-6) |
| N3 | domainItemType の拡張科目マッピング | セグメントメンバー等。Lane 6 が担当 |
| N4 | textBlockItemType の拡張科目マッピング | テキストブロック。Lane 1 が担当 |
| N5 | クロス企業の概念名マッチング | SCOPE.md: 年度横断集約はスコープ外 |

---

## 4. 実装計画

### 4.1 CustomItemInfo の拡張

既存フィールドはそのまま維持し、3 フィールドを追加（全てデフォルト `None` で後方互換）:

```python
@dataclass(frozen=True, slots=True)
class CustomItemInfo:
    """非標準（拡張）科目の分析結果。"""

    # --- 既存フィールド（変更なし） ---
    item: LineItem
    namespace_info: NamespaceInfo
    parent_standard_concept: str | None  # general-special 由来

    # --- 新規フィールド（Lane 5 追加） ---
    calculation_ancestor: str | None = None
    """Calculation Linkbase (summation-item) 由来の最近接標準科目のローカル名。

    CalculationLinkbase が未指定、または該当する計算関係がない場合は None。
    """

    calculation_path: tuple[str, ...] | None = None
    """custom → ... → standard_ancestor の経路（ローカル名のタプル）。

    先頭が非標準科目、末尾が calculation_ancestor。
    calculation_ancestor が None の場合はルートまでの経路、
    または CalculationLinkbase が未指定の場合は None。
    """

    calculation_role_uri: str | None = None
    """マッピングが特定された Calculation Linkbase の role URI。"""
```

### 4.2 detect_custom_items() の拡張

keyword-only 引数 `calculation_linkbase` を追加:

```python
def detect_custom_items(
    statements: Statements,
    *,
    definition_linkbase: dict[str, DefinitionTree] | None = None,
    calculation_linkbase: CalculationLinkbase | None = None,  # 新規
) -> CustomDetectionResult:
```

**内部処理の追加**:

1. 既存の `_build_parent_index(definition_linkbase)` で general-special 逆引きインデックスを構築（既存処理）
2. **新規**: `_build_calculation_index(calculation_linkbase)` で summation-item 逆引きインデックスを構築
3. 各 LineItem の処理時に、general-special の `parent_standard_concept`（既存）に加えて、summation-item の `calculation_ancestor` / `calculation_path` / `calculation_role_uri`（新規）を付与

### 4.3 _build_calculation_index() 新規内部関数

```python
@dataclass(frozen=True, slots=True)
class _CalcMappingResult:
    """CalculationLinkbase ベースのマッピング結果（内部用）。"""
    ancestor: str | None
    path: tuple[str, ...]
    role_uri: str

def _build_calculation_index(
    calculation_linkbase: CalculationLinkbase | None,
) -> dict[str, _CalcMappingResult]:
    """CalculationLinkbase の summation-item を辿り、全非標準科目のマッピングを構築する。

    Args:
        calculation_linkbase: パース済みの CalculationLinkbase。None の場合は空辞書を返す。

    Returns:
        非標準科目ローカル名 → _CalcMappingResult の辞書。
    """
```

**アルゴリズム**（`parent_of()` による 1-pass 走査）:

`ancestors_of()` はローカル名のみを返し href 情報を持たないため使用しない。
代わりに `parent_of()` で 1 段ずつ辿り、各ステップの `CalculationArc.parent_href` から
`_is_standard_href()` で直接判定する。標準科目が見つかった時点で早期終了する。

```
if calculation_linkbase is None:
    return {}

# Step 1: 全非標準科目を検出（child_href / parent_href を走査）
custom_concepts = _find_custom_in_calc(calculation_linkbase)

# Step 2: 各非標準科目について、最も近い標準科目を特定
result = {}
for concept in custom_concepts:
    for role_uri in calculation_linkbase.role_uris:
        path = [concept]
        standard_ancestor = None
        current = concept
        visited = {concept}

        while True:
            parent_arcs = calculation_linkbase.parent_of(current, role_uri=role_uri)
            if not parent_arcs:
                break  # ルートに到達
            arc = parent_arcs[0]
            parent = arc.parent
            if parent in visited:
                break  # 循環検出
            visited.add(parent)
            path.append(parent)

            if _is_standard_href(arc.parent_href):  # 同一ファイル内の既存関数
                standard_ancestor = parent
                break  # 最も近い標準科目で停止

            current = parent

        if standard_ancestor is not None or len(path) > 1:
            result[concept] = _CalcMappingResult(
                ancestor=standard_ancestor,
                path=tuple(path),
                role_uri=role_uri,
            )
            if standard_ancestor is not None:
                break  # 最初に標準科目が見つかった role を採用

return result
```

**`_find_standard_ancestor()` (general-special) との設計比較**:

| | `_find_standard_ancestor()` (既存) | `_build_calculation_index()` (新規) |
|---|---|---|
| データソース | DefinitionLinkbase の arc | CalculationLinkbase.parent_of() |
| 走査方法 | pre-built index + 再帰 | parent_of() + while ループ |
| href 判定 | `_is_standard_href()` | `_is_standard_href()` **（同一関数）** |
| 循環防止 | `_visited` set | `visited` set |
| 付加情報 | ancestor のみ | ancestor + path + role_uri |

### 4.4 _find_custom_in_calc() 内部関数

`_build_calculation_index()` の Step 1 および `find_custom_concepts()` が内部的に使用する。
全 `CalculationArc` の `parent_href` と `child_href` の**両方**を走査し、
`_is_standard_href()` で非標準と判定された concept を収集する。

```python
def _find_custom_in_calc(calc_linkbase: CalculationLinkbase) -> set[str]:
    """CalculationLinkbase 内の全非標準科目を検出する（内部用）。

    全ロールの全 CalculationArc を走査し、child_href / parent_href が
    提出者タクソノミの XSD を参照している concept を収集する。

    Args:
        calc_linkbase: パース済みの CalculationLinkbase。

    Returns:
        非標準科目ローカル名の集合。
    """
    custom: set[str] = set()
    for tree in calc_linkbase.trees.values():
        for arc in tree.arcs:
            if not _is_standard_href(arc.child_href):
                custom.add(arc.child)
            if not _is_standard_href(arc.parent_href):
                custom.add(arc.parent)
    return custom
```

**注意**: 非標準科目がサブトータル（親側のみ出現）の場合でも `parent_href` の走査で検出される。

### 4.5 find_custom_concepts() 公開関数

```python
def find_custom_concepts(
    calc_linkbase: CalculationLinkbase,
) -> tuple[str, ...]:
    """Calculation Linkbase 内の全非標準科目を自動検出する。

    全 CalculationArc の parent/child の href を走査し、
    提出者タクソノミに属する concept を抽出する。

    Args:
        calc_linkbase: パース済みの CalculationLinkbase。

    Returns:
        非標準科目ローカル名のタプル（重複除去・ソート済み）。
    """
    return tuple(sorted(_find_custom_in_calc(calc_linkbase)))
```

内部的には `_find_custom_in_calc()` を呼び、ソート + タプル化する薄いラッパー。

**ユースケース**: Statements なしで CalculationLinkbase だけからの非標準科目探索。タクソノミ分析ツール向け。

### 4.6 href 判定 — 既存 `_is_standard_href()` をそのまま利用

`custom.py` L182-200 の既存関数をそのまま使う。新規の正規表現は追加しない:

```python
_FILER_XSD_RE = re.compile(r"jpcrp\d+")  # 既存（L56）

def _is_standard_href(href: str) -> bool:  # 既存（L182-200）
    path_part = href.split("#")[0] if "#" in href else href
    filename = path_part.rsplit("/", 1)[-1] if "/" in path_part else path_part
    return not bool(_FILER_XSD_RE.match(filename))
```

**href パターン例**:

| href パス部分 | ファイル名先頭 | 判定 |
|---|---|---|
| `jppfs_cor_2025-11-01.xsd` | `jppfs_cor_...` → `jpcrp\d+` 不一致 | 標準 |
| `jpcrp_cor_2025-11-01.xsd` | `jpcrp_cor_...` → `jpcrp\d+` 不一致（`_cor` は数字でない） | 標準 |
| `jpigp_cor_2025-11-01.xsd` | `jpigp_cor_...` → `jpcrp\d+` 不一致 | 標準 |
| `jpbki_cor_2025-11-01.xsd` | `jpbki_cor_...` → `jpcrp\d+` 不一致 | 標準 |
| `jpcrp030000-asr_E02144-000.xsd` | `jpcrp030000...` → `jpcrp\d+` **一致** | 非標準 |
| `jpcrp030000-asr_X99001-000_2025-11-01.xsd` | `jpcrp030000...` → `jpcrp\d+` **一致** | 非標準 |

---

## 5. 実装の注意点

### 5.1 後方互換性の維持

**最重要事項**。既存ユーザーのコードが一切壊れないこと:

```python
# 既存コード（変更前と同じ結果を返す）
result = detect_custom_items(statements)
result = detect_custom_items(statements, definition_linkbase=def_trees)

# 新フィールドはデフォルト None
assert result.custom_items[0].calculation_ancestor is None
assert result.custom_items[0].calculation_path is None
assert result.custom_items[0].calculation_role_uri is None
```

### 5.2 複数 role URI の扱い

同一の非標準科目が複数の role URI に出現する場合がある（BS と注記等）。この場合、最初に標準科目が見つかった role のマッピングを採用する。

role URI の優先順位は定義しない（`CalculationLinkbase.role_uris` の順序 = `dict` の挿入順 = XML パース時の `calculationLink` 要素出現順に依存）。

**テストへの影響**: マルチ role テストでは「どの role が返っても正しい」形のアサーション（`assert result.calculation_role_uri in {role_a, role_b}`）を使い、特定の role を期待するテストは単一 role フィクスチャで行う。

### 5.3 ルートまで標準科目がない場合

提出者が独自のルート科目を定義し、その配下に標準科目が一切ない場合は `calculation_ancestor = None`。`calculation_path` にはルートまでの経路が記録される。

### 5.4 Calculation Linkbase が存在しない場合

空の `CalculationLinkbase`（`trees={}`）に対しては空のインデックスが返り、全 `CustomItemInfo` の calculation フィールドが `None` になる。

### 5.5 parent_of() の複数親への対応

`parent_of(child, role_uri=...)` が複数の arc を返す場合は先頭（`arcs[0]`）を辿る。これは既存の `_find_standard_ancestor()` の再帰戦略（「最初に見つかった親を辿る」）と同じ方針。

### 5.6 非標準サブトータル（親のみ出現）の扱い

非標準科目が Calculation Linkbase で**親としてのみ出現**する場合（例: 非標準のサブトータル科目が標準科目を子に持つ）、`_find_custom_in_calc()` は `parent_href` 走査で検出するが、`_build_calculation_index()` の `parent_of()` は空を返す（この科目は child として登場しないため）。

結果として `path = (concept,)` のみ（長さ 1）、フィルタ条件 `len(path) > 1` を満たさないため `_build_calculation_index()` の結果 dict に**含まれない**。`detect_custom_items()` では `calc_index.get()` が `None` を返し、`calculation_ancestor = None` になる。

これは意図された動作: サブトータルの非標準科目は「どの標準科目の配下か」という問いに答えられないため `None` が適切。`find_custom_concepts()` では検出される。

### 5.7 detect_custom_items() の処理順序

```
1. _build_parent_index(definition_linkbase)          # 既存: general-special インデックス
2. _build_calculation_index(calculation_linkbase)     # 新規: summation-item インデックス
3. for item in statements:                            # 既存ループ
       if is_standard_taxonomy(item.namespace_uri):
           standard_items.append(item)
       else:
           parent = parent_index.get(item.local_name)           # 既存
           calc = calc_index.get(item.local_name)               # 新規
           custom_items.append(CustomItemInfo(
               item=item,
               namespace_info=classify_namespace(item.namespace_uri),
               parent_standard_concept=parent,                   # 既存
               calculation_ancestor=calc.ancestor if calc else None,       # 新規
               calculation_path=calc.path if calc else None,               # 新規
               calculation_role_uri=calc.role_uri if calc else None,       # 新規
           ))
```

---

## 6. テスト計画

### 6.1 テストファイル

`tests/test_xbrl/test_custom_detection.py` に新テストクラスを**追加**する。
既存テストクラス・テストメソッドは一切変更しない。

### 6.2 テストフィクスチャ — インメモリ構築パターン

**XML フィクスチャファイルは作成しない。** 既存の `_make_gs_tree()` パターンに準拠し、
テストファイル内で `CalculationLinkbase` / `CalculationTree` / `CalculationArc` を
直接構築するヘルパー関数を使用する。

**理由**:
- デトロイト派の原則: `detect_custom_items()` のテストが `parse_calculation_linkbase()` のパース成功に依存しない
- 既存テストとの一貫性: `_make_gs_tree()` と同じアプローチ
- 保守コスト削減: XML フィクスチャ 5 ファイル（~200 行）が不要

```python
# テスト用定数
_STANDARD_CAL_XSD = "jppfs_cor_2025-11-01.xsd"
_FILER_CAL_XSD = "jpcrp030000-asr-001_E02144-000.xsd"

def _make_calc_linkbase(
    arcs: list[tuple[str, str]],
    *,
    filer_concepts: set[str] | None = None,
    role_uri: str = "http://example.com/role/test",
) -> CalculationLinkbase:
    """テスト用の CalculationLinkbase をインメモリ構築する。

    Args:
        arcs: (parent, child) タプルのリスト。
        filer_concepts: 提出者別タクソノミとして扱う concept 名の集合。
            指定しない場合、全ての href は標準タクソノミ XSD を参照する。
            指定した場合、集合に含まれる concept の href は提出者別 XSD を参照する。
        role_uri: ロール URI。
    """
    if filer_concepts is None:
        filer_concepts = set()

    def _href_for(concept: str) -> str:
        xsd = _FILER_CAL_XSD if concept in filer_concepts else _STANDARD_CAL_XSD
        return f"{xsd}#{concept}"

    calc_arcs = tuple(
        CalculationArc(
            parent=parent, child=child,
            parent_href=_href_for(parent), child_href=_href_for(child),
            weight=1, order=float(i), role_uri=role_uri,
        )
        for i, (parent, child) in enumerate(arcs)
    )
    parents = []
    children = set()
    seen = set()
    for p, c in arcs:
        if p not in seen:
            seen.add(p)
            parents.append(p)
        children.add(c)
    roots = tuple(p for p in parents if p not in children)

    tree = CalculationTree(role_uri=role_uri, arcs=calc_arcs, roots=roots)
    return CalculationLinkbase(source_path=None, trees={role_uri: tree})
```

### 6.3 テストケース一覧（26 件）

```python
class TestCalculationMapping:
    """detect_custom_items() の calculation_linkbase 引数に関するテスト。"""

    def test_single_custom_to_standard(self):
        """非標準科目 1 つが直接の標準親にマッピングされる。"""

    def test_deep_custom_to_standard(self):
        """非標準科目が 2 段階上の標準科目にマッピングされる。"""

    def test_path_includes_intermediates(self):
        """calculation_path が custom → intermediate → standard の完全な経路を含む。"""

    def test_no_standard_ancestor(self):
        """ルートまで標準科目がない場合 calculation_ancestor が None、path はルートまで。"""

    def test_multiple_custom_concepts(self):
        """複数の非標準科目がそれぞれマッピングされる。"""

    def test_role_uri_preserved(self):
        """calculation_role_uri にマッピング元の role URI が記録される。"""

    def test_without_calculation_linkbase(self):
        """calculation_linkbase 未指定時は全 calculation フィールドが None（後方互換）。"""

    def test_with_both_linkbases(self):
        """definition_linkbase と calculation_linkbase を同時に渡した場合、
        parent_standard_concept と calculation_ancestor が独立に設定される。"""

    def test_empty_calculation_linkbase(self):
        """空の CalculationLinkbase で calculation フィールドが全て None。"""

    def test_concept_not_in_calculation(self):
        """CalculationLinkbase に存在しない非標準科目は calculation フィールドが None。"""

    def test_custom_parent_only(self):
        """非標準科目が親（サブトータル）としてのみ出現する場合。
        calculation_ancestor は None であること（§5.6）。"""

    def test_existing_fields_unchanged_with_calc(self):
        """calculation_linkbase を渡しても custom_ratio, total_count 等の
        既存フィールドが calculation_linkbase なしの場合と同一であること。"""

    def test_multi_role_any_role_accepted(self):
        """同一非標準科目が複数 role に出現する場合。
        calculation_role_uri がいずれかの role URI であること（順序非依存）。"""


class TestFindCustomConcepts:
    """find_custom_concepts() のテスト。"""

    def test_find_all_custom(self):
        """非標準科目が正しく検出される。"""

    def test_standard_concepts_excluded(self):
        """標準科目が結果に含まれない。"""

    def test_no_duplicates(self):
        """重複した非標準科目名が除去される。"""

    def test_sorted_result(self):
        """結果がソート済み。"""

    def test_empty_linkbase(self):
        """空の CalculationLinkbase で空タプルが返る。"""

    def test_all_standard_concepts(self):
        """全て標準科目の CalculationLinkbase で空タプルが返る。"""

    def test_filer_with_date_suffix(self):
        """jpcrp030000-asr_X99001-000_2025-11-01.xsd 形式が非標準として検出される。

        filer_pl.xml フィクスチャとの整合性確認。
        """


class TestIsStandardHrefIntegration:
    """_is_standard_href() の統合確認（find_custom_concepts 経由）。"""

    def test_standard_jppfs_excluded(self):
        """jppfs_cor_2025-11-01.xsd の概念が non-custom として除外される。"""

    def test_standard_jpcrp_cor_excluded(self):
        """jpcrp_cor_2025-11-01.xsd（標準 jpcrp_cor）が除外される。"""

    def test_filer_custom_e_code_detected(self):
        """jpcrp030000-asr_E02144-000.xsd の概念が非標準として検出される。"""

    def test_filer_custom_with_date_suffix_detected(self):
        """jpcrp030000-asr_X99001-000_2025-11-01.xsd が非標準として検出される。"""

    def test_standard_jpbki_excluded(self):
        """jpbki_cor_2025-11-01.xsd（銀行業）が除外される。"""

    def test_standard_jpigp_excluded(self):
        """jpigp_cor_2025-11-01.xsd（IFRS）が除外される。"""
```

---

## 7. 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `src/edinet/xbrl/taxonomy/custom.py` | **変更** | `CustomItemInfo` に 3 フィールド追加、`detect_custom_items()` に `calculation_linkbase` 引数追加、`_build_calculation_index()` / `_find_custom_in_calc()` / `find_custom_concepts()` 追加 |
| `tests/test_xbrl/test_custom_detection.py` | **変更** | `TestCalculationMapping` (13件), `TestFindCustomConcepts` (7件), `TestIsStandardHrefIntegration` (6件) クラス追加（既存テストは不変） |

### 変更行数見積もり

| ファイル | 行数 |
|---------|------|
| `custom.py` への追加 | ~120 行（新関数 + フィールド追加） |
| テスト追加 | ~450 行（ヘルパー `_make_calc_linkbase()` 含む） |
| **合計** | **~570 行** |

### 作らないもの

| ファイル | 理由 |
|---------|------|
| `standard_mapping.py` | `custom.py` に統合。別モジュールにすると同じ問いに 2 つの API が生じる |
| `StandardMapping` dataclass | `CustomItemInfo` のフィールドとして統合 |
| `tests/fixtures/standard_mapping/` | XML フィクスチャ不要。テスト内でインメモリ構築する |

---

## 8. 検証手順

1. `uv run pytest tests/test_xbrl/test_custom_detection.py -v` で全テスト PASS（既存 + 新規）
2. `uv run pytest` で全テスト PASS（既存テスト破壊なし）
3. `uv run ruff check src/edinet/xbrl/taxonomy/custom.py tests/test_xbrl/test_custom_detection.py` でリント PASS

### 後方互換性チェックリスト

- [ ] `detect_custom_items(statements)` が従来と同じ結果を返す
- [ ] `detect_custom_items(statements, definition_linkbase=...)` が従来と同じ結果を返す
- [ ] 新フィールド `calculation_ancestor`, `calculation_path`, `calculation_role_uri` がデフォルト `None`
- [ ] 既存の全テスト（655 行）が変更なしで PASS
- [ ] `CustomDetectionResult` のフィールド（`custom_items`, `standard_items`, `custom_ratio`, `total_count`）に変更なし

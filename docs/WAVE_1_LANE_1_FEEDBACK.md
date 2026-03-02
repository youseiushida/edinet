# WAVE 1 LANE 1 フィードバック（第4ラウンド）: Presentation Linkbase パーサー

## 総評

3ラウンドのフィードバック反映を経て、計画は**実装即着手可能な水準**に達している。以下の点で業界水準のライブラリ設計書として優秀:

- **QA トレーサビリティ**: 全設計判断に QA ID が根拠付きで紐づいている
- **フィードバック反映の透明性**: 3ラウンド分の採用/却下/変更不要の判断理由が完全に記録されている
- **エッジケースの網羅**: 属性欠落、循環参照、空入力、bare fragment、複数ルート等が全て定義済み
- **並列安全性**: ファイル接触範囲の制限、`__init__.py` 非接触ルールが徹底されている
- **後続 Wave への配慮**: Wave 2 `concept_sets` の利用パターンを見据えた API 設計（`flatten(skip_dimension=True)` 等）

**総合判定: 実装開始して問題ない。** 以下は「ディファクトスタンダード」品質を最終確認する観点からの残存課題。前ラウンドに比べ重大度はさらに下がっており、HIGH 項目も「実装エージェントが見落とすと微妙なバグになる」程度。

---

## HIGH（実装時にバグ/不整合を生むリスクがある）

### I-1. `order` のパース失敗時の挙動が G-3 原則と矛盾している

**現状（§6.3）**: 「パース失敗時は `EdinetParseError` を送出する」

**問題**: §3.2 Step 1 で確立した G-3 原則は「`EdinetParseError` は XML 自体が壊れている場合（malformed XML）に限定する。属性欠落は `warnings.warn` + スキップで処理」。

`order="abc"`（非数値文字列）は XML としては valid であり malformed ではない。これは「属性値の異常」であり、G-3 の定義に従えば `warnings.warn` + フォールバック（`0.0`）が正しい。`EdinetParseError` を送出すると、**1つの arc の order 値が壊れているだけで全ファイルのパースが中断される**。H-8 で確認された通り実データには GFM 例外が 20+ 件あり、属性値の異常は稀に発生しうる。

**提案**: §6.3 を以下に変更:

```
order は float にパースする。整数値の場合も float で統一する。
パース失敗時（非数値文字列等）は 0.0 にフォールバックし
warnings.warn("order 属性のパースに失敗しました: {value!r}, 0.0 にフォールバックします",
              EdinetWarning, stacklevel=2) を発行する。
```

これにより G-3 のフォールバック表と完全に一貫する:

| 属性 | 欠落時の挙動 | パース失敗時の挙動 |
|------|-------------|-------------------|
| `order` on arc | `0.0` にフォールバック + `warnings.warn` | `0.0` にフォールバック + `warnings.warn`（**追加**） |

---

### I-2. concept 名正規化（F-1 CRITICAL）のテストケースが不足

**現状（§4.2）**: concept 名正規化に関するテストは以下の 2 件のみ:
- `test_concept_from_href_not_label` — `_2` サフィックス除去
- `test_concept_from_bare_fragment` — prefix なし bare concept 名

**問題**: concept 名正規化は本モジュールで**最もクリティカルなロジック**（F-1 CRITICAL）であり、後続の Wave 2 `concept_sets` の正確性に直結する。しかしテストケースが 2 件では以下のエッジケースがカバーされていない:

| パターン | 入力 fragment | 期待される concept 名 | テスト有無 |
|----------|---------------|----------------------|-----------|
| 標準 prefix | `jppfs_cor_CashAndDeposits` | `CashAndDeposits` | **なし** |
| ハイフン含む prefix | `jpcrp030000-asr_E02144-000_CustomExpense` | `CustomExpense` | **なし** |
| 数字始まりの concept | `jppfs_cor_1702RecognizedAsLoss` | 不明（_[A-Z] 境界なし） | **なし** |
| bare fragment (prefix なし) | `ConsolidatedBalanceSheetHeading` | `ConsolidatedBalanceSheetHeading` | あり |
| `_2` サフィックス回避 | `xlink:label` の `_2` が concept に漏れない | — | あり |

**特に重要**: 既存の `_split_fragment_prefix_local` の Note に「IFRS 拡張対応時に再検証が必要」と記載がある。EDINET の concept 名は PascalCase が仕様上強制されるため `_[A-Z]` 境界で分割可能だが、**数字始まりの concept 名**（`1702RecognizedAsLoss` のようなケース）が存在する場合、`_[A-Z]` 境界が見つからずフォールバックに落ちる。実在するかは QA で未確認だが、フォールバック（G-2）が正しく動作することをテストで保証すべき。

**提案**: `TestParsePresentationLinkbase` に以下のテストケースを追加（計 3 件）:

```python
def test_concept_from_standard_prefix(self):
    """標準 prefix（jppfs_cor）から concept 名が正しく分離されること。"""

def test_concept_from_hyphenated_prefix(self):
    """ハイフン含み prefix（jpcrp030000-asr_E02144-000）から concept 名が正しく分離されること。"""

def test_concept_fallback_no_uppercase_boundary(self):
    """_[A-Z] 境界が見つからない fragment でフォールバック（G-2）が動作すること。"""
```

---

## MEDIUM（API 品質・メンテナビリティの改善）

### I-3. `_split_fragment_prefix_local` の再実装に対する技術的負債マーカーの追加

**現状（§6.1）**: 「`taxonomy` モジュールへの依存は避け、同等のロジックを本モジュール内に軽量に再実装する」

**問題**: これは Wave 1 の並列安全性制約上やむを得ないが、**同一ロジックが 2 箇所に存在する**ことは明確な DRY 違反。既存の `taxonomy/__init__.py:419` の実装にはすでに Note（「IFRS 拡張対応時に再検証が必要」）があり、将来のバグ修正やエッジケース追加が片方にしか反映されないリスクがある。

**提案**: §6.1 に以下を追記:

```
技術的負債: Wave 1 完了後の統合タスクで、`taxonomy/__init__.py` の
`_split_fragment_prefix_local` と本モジュールの正規化ロジックを
共通ユーティリティ（例: `edinet.xbrl._utils.split_fragment`）に
抽出し、両モジュールからインポートする形に統一すること。
```

これにより統合タスクの担当者が見落とさなくなる。

---

### I-4. `preferredLabel` の共通ロール定数を定義すべき

**現状（§3.1）**: `preferred_label: str | None` で完全 URI を保持。`is_total` プロパティで `totalLabel` のみ判定可能。

**問題**: 利用者が totalLabel 以外のラベルロール（`periodStartLabel`, `periodEndLabel`, `negatedLabel` 等）を判定する際、毎回生の URI 文字列を書く必要がある。これは typo の温床であり、ディファクトスタンダードのライブラリとしては定数を提供すべき。

```python
# 利用者コードの現状（typo リスクあり）
if node.preferred_label == "http://www.xbrl.org/2003/role/periodStartLabel":
    ...
```

**提案**: `presentation.py` のモジュールレベルに以下の定数を追加:

```python
# XBRL 標準ラベルロール URI 定数
ROLE_LABEL = "http://www.xbrl.org/2003/role/label"
ROLE_TOTAL_LABEL = "http://www.xbrl.org/2003/role/totalLabel"
ROLE_PERIOD_START_LABEL = "http://www.xbrl.org/2003/role/periodStartLabel"
ROLE_PERIOD_END_LABEL = "http://www.xbrl.org/2003/role/periodEndLabel"
ROLE_NEGATED_LABEL = "http://www.xbrl.org/2003/role/negatedLabel"
ROLE_VERBOSE_LABEL = "http://www.xbrl.org/2003/role/verboseLabel"
```

**注意**: 既存の `taxonomy/__init__.py` にも `ROLE_LABEL`, `ROLE_VERBOSE`, `ROLE_TOTAL` が定義されている。I-3 と同様に、Wave 1 統合タスクで共通定数として一元化すること。Wave 1 の間は重複を許容する。

**コスト**: 6 行の定数定義のみ。テスト変更不要。

---

### I-5. 実データスモークテストの推奨

**現状（§4.1）**: テストフィクスチャは全て handcrafted XML。

**問題**: handcrafted XML はエッジケースのテストに最適だが、実タクソノミの `_pre.xml` は handcrafted では再現しにくい特性を持つ:
- 巨大な namespace 宣言群
- BOM 付き UTF-8
- 深いネスト（depth 10+）
- 数百ノード規模のツリー
- 予期せぬ空白・改行の混入

**提案**: §4.2 に以下の optional テストを追加:

```python
@pytest.mark.skipif(
    not os.environ.get("EDINET_TAXONOMY_ROOT"),
    reason="EDINET_TAXONOMY_ROOT が設定されていません"
)
class TestRealTaxonomy:
    """実タクソノミに対するスモークテスト（CI では skip）。"""

    def test_parse_jppfs_pre(self):
        """jppfs の _pre.xml が例外なくパースできること。"""
        # EDINET_TAXONOMY_ROOT/taxonomy/jppfs/2025-11-01 以下の
        # _pre*.xml を全てパースし、PresentationTree が空でないことを確認

    def test_parse_and_merge_pl_variants(self):
        """PL バリアントファイルのマージが動作すること。"""
        # _pre_pl.xml + _pre_pl-2-*.xml をマージし、
        # LineItems 以下の concept 数が単体より増えていることを確認
```

これは §4.3 のテスト方針（フィクスチャ自己完結）とは別カテゴリのテストとして位置づける。CI ではスキップ、ローカル開発時の実データ検証用。計画の必須テストには含めないが、**実装エージェントへの推奨事項**とする。

---

### I-6. `merge_presentation_trees` の single-dict 最適化の副作用を docstring に明記

**現状（§3.1 merge docstring G-6）**: 「1 つの辞書のみ → そのまま返す（コピーなし）」

**問題**: 「コピーなし」は性能最適化としては正しいが、返り値の dict への変更操作が入力を汚染する:

```python
original = parse_presentation_linkbase(xml)
merged = merge_presentation_trees(original)
assert merged is original  # True!
merged["new_role"] = some_tree  # original も変更される!
```

`PresentationTree` 自体は frozen なので安全だが、dict コンテナは mutable。利用者が返り値を自由に変更できると思って追加・削除すると、元の辞書が壊れる。

**提案**: docstring の G-6 エッジケース記述に以下を追記:

```
Note:
    1 つの辞書のみ渡した場合、返り値は入力と同一オブジェクトである
    （浅いコピーも行わない）。返り値の dict を変更すると入力にも
    影響するため、変更が必要な場合は利用者側で dict() コピーを
    取ること。
```

**代替案**: 常に `dict(tree_dict)` で浅いコピーを返す。PresentationTree は frozen なので浅いコピーで十分。性能コストは辞書のエントリ数分のポインタコピーのみ（数十件程度）。

**推奨**: 代替案（常に浅いコピー）の方が安全。`merge_presentation_trees(*tree_dicts)` の呼び出し頻度は低く（提出者あたり 1 回）、浅いコピーのコストは無視できる。G-6 の「コピーなし」を「浅いコピーを返す」に変更し、利用者が返り値を安全に変更できることを保証する方が、ディファクトスタンダードの API 品質として適切。

---

## LOW（計画変更不要、実装時の参考）

### I-7. `PresentationNode.is_abstract` の判定基準をもう少し厳密に

**現状**: concept 名の末尾が `Abstract` または `Heading` で判定。

**補足**: 本来 abstract 判定は XSD の `abstract="true"` 属性に基づくべきだが、本モジュールは XSD をパースしない（Presentation Linkbase のみ）。concept 名末尾による推定は EDINET の命名慣例では十分に信頼できるが、**注記の提出者拡張科目**（`jpcrp_cor` 系）で末尾が `Abstract` でない abstract 要素が稀に存在しうる。

現行の判定方法は実用上問題ないため計画変更不要。ただし、将来 XSD パースと連携する場合に精度向上が可能であることを注記として残しておくと良い。

---

### I-8. テスト: `__repr__` の文字列に含まれるべき情報

H-8 推奨の `__repr__` テスト（G-8）に加え、以下を確認するとよい:

```python
def test_node_repr_contains_concept(self):
    """PresentationNode.__repr__ が concept 名を含むこと。"""
    assert "CashAndDeposits" in repr(node)

def test_tree_repr_contains_role_uri(self):
    """PresentationTree.__repr__ が role_uri を含むこと。"""
    assert "rol_ConsolidatedBalanceSheet" in repr(tree)
```

REPL での探索時に `repr()` が有用な情報を提供することを保証する。計画の必須テストには含めない。

---

## 前回フィードバック（H-1〜H-8）の反映確認

| ID | 判断 | 確認結果 |
|----|------|---------|
| H-1 | 採用 | マージ後の depth 再計算を §3.1 merge docstring Step 5、§3.2 Step 4 に明記。テスト追加。適切 |
| H-2 | 採用 | 全属性「先着採用」を §3.1 merge docstring Step 3b に明記。引数順の意味をドキュメント化。適切 |
| H-3 | 採用 | `flatten(skip_dimension=True)` 追加。§3.1 シグネチャ + docstring に反映。テスト追加。適切 |
| H-4 | 採用 | `EdinetWarning` カテゴリ + `stacklevel=2` を §3.2 Step 1 に明記。import 対象にも反映。適切 |
| H-5 | 採用 | `sorted()` 安定ソートの保証を §3.1, §3.2 の複数箇所に明記。適切 |
| H-6 | 採用 | concept 名ベースグルーピングの既知制限を merge docstring Note に追記。適切 |
| H-7 | 変更不要 | Pythonic プロトコル。実装時の裁量。妥当 |
| H-8 | 変更不要 | テスト推奨。計画変更なし。妥当 |

**全 8 項目の反映状況は適切。**

---

## 今回のフィードバック優先度まとめ

| ID | 優先度 | 概要 | 影響 |
|----|--------|------|------|
| I-1 | **HIGH** | `order` パース失敗を G-3 に合わせ warn + フォールバックに変更 | 不正 order 値で全パースが中断するバグを防止 |
| I-2 | **HIGH** | concept 名正規化テストを 3 件追加 | F-1 CRITICAL ロジックのテスト網羅性向上 |
| I-3 | MEDIUM | `_split_fragment` 再実装の技術的負債マーカーを追記 | Wave 統合時の DRY 統一を確実にする |
| I-4 | MEDIUM | `preferredLabel` の共通ロール定数を定義 | typo 防止、利用者体験向上 |
| I-5 | MEDIUM | 実データスモークテストの推奨 | handcrafted XML で再現不能な問題の早期検出 |
| I-6 | MEDIUM | merge single-dict の浅いコピー化を推奨 | 返り値変更時の入力汚染を防止 |
| I-7 | LOW | `is_abstract` 判定の限界の注記 | 計画変更不要 |
| I-8 | LOW | `__repr__` テストの追加推奨 | 計画変更不要 |

---

## 総合判定

**計画は HIGH 項目（I-1, I-2）を反映すれば完成。実装開始の障害はない。**

I-1（order パース失敗の挙動）は §6.3 の 1 文を書き換えるだけで済む。I-2（テスト追加）は §4.2 に 3 件のテスト定義を追加するのみ。

MEDIUM 項目（I-3〜I-6）は「ディファクトスタンダード」品質を一段引き上げる改善。特に I-4（ラベルロール定数）と I-6（merge の浅いコピー）は実装コストが極めて低い（数行の変更）のに対し、利用者体験への寄与が大きい。

4ラウンドのフィードバックを経て、設計の成熟度は**量産型ライブラリ設計書として完成**している。これ以上のフィードバックラウンドは収穫逓減であり、**実装に移行すべきフェーズ**。

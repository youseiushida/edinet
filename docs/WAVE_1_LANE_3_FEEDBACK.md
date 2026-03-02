# WAVE_1_LANE_3_FEEDBACK — Definition Linkbase パーサー 実装レビュー

## 総評

**計画の完成度: ★★★★★ (5/5)**
**実装の完成度: ★★★★☆ (4.5/5)**

計画は 5 ラウンドのフィードバックを経て非常に高い成熟度に達しており、実装はその計画に忠実に従っている。14 テスト全パス、ruff クリーン、既存テストへの影響なし。Wave 1 全レーンの中で**計画と実装の整合性が最も高い**レーンである。

### 特に優れている点

1. **データモデルの設計品質**: `MemberNode` ツリーの再帰的構造が下流（SS 列ヘッダー、セグメント構造）の全ユースケースをカバー。`usable` フラグの伝播、`visited | {concept}` コピー方式による DAG 耐性、循環検出の logger.warning まで実装済み
2. **テストフィクスチャの充実度**: 5 つのフィクスチャが計画通りの構造を持ち、各テストが明確に 1 つの機能を検証している。`simple_ss.xml` の 3 階層メンバーツリー（Domain → Abstract → 具体メンバー）は SS の実構造を忠実に再現
3. **エラーハンドリングの網羅性**: 不正 XML → `EdinetParseError`、不明ロケーター → `EdinetWarning` + スキップ、空リンクベース → 空辞書。計画の 8 条件エラー表に忠実
4. **L2 (calculation.py) との構造的一貫性**: `_extract_concept_from_href()` の 2 段階戦略、loc マップ構築、`warnings.warn` パターンが L2 とほぼ同一で、Wave 統合時の `_common.py` 抽出が容易
5. **`__repr__` の設計**: `MemberNode` の再帰爆発対策（`children=` にカウントのみ表示）、`HypercubeInfo` の axis 名列挙、`DefinitionTree` の arcs/hypercubes カウント — REPL デバッグ体験が優れている

---

## CRITICAL（修正すべき）

なし。

---

## HIGH（実装品質に影響する）

### H-1. `_XSD_PREFIX_RE` の non-greedy/greedy 不一致（L2 との差異）

**現状**:
- L3 (definition.py:37): `_XSD_PREFIX_RE = re.compile(r"^(.+?)_\d{4}-\d{2}-\d{2}\.xsd$")` — **non-greedy** `.+?`
- L2 (calculation.py:43): `_XSD_PREFIX_RE = re.compile(r"^(.+)_\d{4}-\d{2}-\d{2}\.xsd$")` — **greedy** `.+`

**影響**: 現行の EDINET タクソノミ命名規則（`jppfs_cor_2025-11-01.xsd` 等）では、`$` アンカーにより両者は同一の結果を返す。しかし「L2 と同一の 2 段階戦略」と明記されているにもかかわらず正規表現が異なるのは統合時の混乱の原因になる。

**提案**: L2 に合わせて greedy `.+` に統一するか、両レーンの統合時に `_common.py` で 1 つに決定する。現時点では実害なし。

---

## MEDIUM（API 品質・開発者体験の改善）

### M-1. `logging.debug` が 2 回呼ばれている（loc 構築後 + arc 変換後）

**現状** (definition.py:437-441 と 514-518):
```python
# 1回目（loc マップ構築直後）
logger.debug("ロール %s: %d loc", role_uri, len(loc_map))
# 2回目（arc 変換後）
logger.debug("ロール %s: %d loc, %d arc", role_uri, len(loc_map), len(arc_list))
```

**問題**: 計画 §4 Step 3 のロギング仕様は `"ロール %s: %d loc, %d arc"` の 1 回のみ。1 回目は arc 数が不明な段階で出力されるため情報量が限定的。

**提案**: 1 回目を削除し、arc 変換後の 2 回目のみ残す。デバッグ時に loc 数だけ知りたいケースはまれ。

### M-2. `source_path` パラメータのテスト欠如

**現状**: `test_invalid_xml_raises_parse_error` は `source_path` なしのケースのみテスト。

**問題**: `source_path` 指定時にエラーメッセージにパスが含まれることは、利用者のデバッグ体験に直結する。

**提案**: テスト追加（必須ではないが推奨）:
```python
def test_invalid_xml_includes_source_path(self) -> None:
    with pytest.raises(EdinetParseError, match="test_file.xml"):
        parse_definition_linkbase(b"<bad>", source_path="test_file.xml")
```

### M-3. 不正 `order` 値の `EdinetWarning` テスト欠如

**現状**: 計画 §4 Step 3.5 のエラーハンドリング表に「order 値が不正 → EdinetWarning + デフォルト 0.0」が定義されているが、テストがない。

**提案**: インライン XML で `order="abc"` を含むフィクスチャを使ったテスト追加を推奨。

### M-4. L1 (presentation.py) との `_extract_concept_from_href()` 実装差異

**現状**: 計画では「3 レーン全てが href ベース抽出を採用」と記載。

**実態**:
- L1: `_CONCEPT_SPLIT_RE = re.compile(r"^(?:[A-Za-z0-9\-]+_[A-Za-z0-9\-]+_)?(.+)$")` による正規表現ベース
- L2/L3: 2 段階戦略（XSD ファイル名ベース + `_[A-Z]` 後方スキャン）

**影響**: Wave 統合の `_common.py` 抽出時に L1 の実装を L2/L3 方式に統一する必要がある。L3 自体の問題ではないが、統合計画に明記すべき。

---

## LOW（微細な改善、対応は任意）

### L-1. `_build_hypercubes` のデフォルト値の明示性

**現状** (definition.py:291-292):
```python
closed = arc.closed if arc.closed is not None else True
context_element = arc.context_element if arc.context_element else "scenario"
```

**観察**: `context_element` の falsy チェック（`if arc.context_element`）は空文字列 `""` も `None` も同様に `"scenario"` にフォールバックする。`arc.context_element` は `all` arc でのみ設定されるため実害はないが、`is not None` を使う方が意図が明確（`closed` の行と一貫）。

### L-2. `DefinitionArc.usable` の docstring 補足

**現状**: docstring に「domain-member arc で false の場合あり」とあるが、計画 §4 Step 3 の M-7 反映（「全 arc 型から XML 属性を読み取る。意味的に有効なのは domain-member のみ」）の記載がない。

**提案**: docstring に以下を追記（任意）:
```
全 arc 型の XML 属性から読み取るが、意味的に有効なのは
``domain-member`` arcrole のみ。
```

### L-3. `findall` の使用は正しいが `iter` との差異を意識

**現状**: L3 は `root.findall()` と `def_link.findall()`、L1 は `root.iter()`。

**観察**: `findall` は直接子要素のみ、`iter` は全子孫を探索。Definition Linkbase の XML 構造では `definitionLink` は `linkbase` の直接子、`loc`/`definitionArc` は `definitionLink` の直接子であるため、`findall` が正確かつ高速。L3 の選択は正しい。

### L-4. テストクラスの `@pytest.mark.unit` マーカー

**現状**: 全テストクラスに `@pytest.mark.unit` が付与されている。

**観察**: 既存の L2 テスト（`test_calculation.py`）にも `@pytest.mark.unit` が使われているか確認すると良い。統一されているなら問題なし。

---

## 他レーンとの比較・統合に向けた所見

| 項目 | L1 (presentation) | L2 (calculation) | L3 (definition) |
|------|-------------------|------------------|-----------------|
| 返り値 | `dict[str, PresentationTree]` | `CalculationLinkbase` (コンテナ) | `dict[str, DefinitionTree]` |
| concept 抽出 | 正規表現ベース | 2 段階 (greedy) | 2 段階 (non-greedy) |
| `_XSD_PREFIX_RE` | なし | greedy `.+` | non-greedy `.+?` |
| ツリー構築 | 再帰 DFS + `visited` (discard 方式) | なし（フラット arc のみ） | 再帰 DFS + `visited` (コピー方式) |
| `warnings.warn` stacklevel | 4 | 2 | 2 |
| `logging` | なし | あり | あり |
| マージ機能 | `merge_presentation_trees` あり | なし | なし |
| クエリメソッド | `flatten()`, `line_items_roots()` | `children_of()`, `parent_of()`, `ancestors_of()` | なし（v0.1.0 では省略） |
| `__repr__` | あり | あり | あり |

**統合時の推奨アクション**:
1. `_extract_concept_from_href()` を `xbrl/linkbase/_common.py` に抽出（L2/L3 方式を採用）
2. L1 の `_extract_concept_from_href()` を L2/L3 方式に統一
3. `_XSD_PREFIX_RE` の greedy/non-greedy を統一
4. `stacklevel` を各パーサーのコールスタック深度に応じて調整

---

## 計画 → 実装の忠実度チェック

| 計画の完了条件 (§2.4) | 実装状況 |
|----------------------|---------|
| 1. 標準 + 提出者の _def.xml パース | ✅ `multi_role.xml` で両パターンテスト済み |
| 2. 全 6 種 arcrole 解析 | ✅ `test_arcrole_extraction` で 5 種確認、`general_special.xml` で 6 種目確認 |
| 3. HypercubeInfo 構造化 | ✅ `test_hypercube_construction` |
| 4. general-special は DefinitionArc のみ | ✅ `test_general_special_only` |
| 5. usable 属性 | ✅ `test_member_tree_with_usable_false` |
| 6. `_2` サフィックス解決 | ✅ `test_duplicate_loc_suffix` |
| 7. MemberNode ツリー | ✅ `test_member_tree_with_usable_false`, `test_domain_member_tree_under_axis` |
| 8. has_hypercube プロパティ | ✅ `test_hypercube_construction`, `test_general_special_only` |
| 9. テスト全パス | ✅ 14/14 passed |

**全 9 条件を満たしている。**

---

## フィードバック一覧

| ID | 優先度 | 種別 | 概要 |
|----|--------|------|------|
| H-1 | HIGH | 不一致 | `_XSD_PREFIX_RE` の non-greedy/greedy 不一致（L2 との差異） |
| M-1 | MEDIUM | 冗長 | `logging.debug` が 2 回呼ばれている |
| M-2 | MEDIUM | テスト | `source_path` パラメータのテスト欠如 |
| M-3 | MEDIUM | テスト | 不正 `order` 値の `EdinetWarning` テスト欠如 |
| M-4 | MEDIUM | 統合 | L1 との `_extract_concept_from_href()` 実装差異（統合時要注意） |
| L-1 | LOW | 一貫性 | `context_element` の falsy チェック vs `is not None` |
| L-2 | LOW | docstring | `DefinitionArc.usable` の意味的有効範囲の記載 |
| L-3 | LOW | 情報 | `findall` vs `iter` の選択は正しい |
| L-4 | LOW | 慣習 | テストマーカーの統一確認 |

---

## 総合判定

**実装は高品質であり、Wave 1 L3 として完成と判断する。**

H-1（正規表現の不一致）は実害がなく、Wave 統合時に `_common.py` で一本化する際に自然に解消される。M-1〜M-3 は「あれば品質が 1 段上がる」レベルの改善であり、修正は推奨するが必須ではない。

計画の完了条件 9 項目を全て満たし、14 テストが全パスし、既存テストへの影響なし。フィクスチャの設計、データモデルの frozen dataclass + slots、`__repr__` のデバッグ配慮、エラーハンドリングの網羅性、いずれもディファクトスタンダードのライブラリとして十分な品質。

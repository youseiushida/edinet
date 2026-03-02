# WAVE 1 LANE 4 フィードバック (Rev 4)

## 総合評価

Rev 3 は実装着手可能な品質に十分到達している。3 回のフィードバックサイクルを経て、MUST レベルの未解決事項はゼロ。設計判断の根拠（§10.1〜§10.7）は全て明確に言語化されており、特に以下の点が優れている:

- **`statements.py` との差異の明示化**（§4.2）: `is_consolidated` と `_is_consolidated()` の挙動差をケース別に表形式で整理し、Wave 3 統合時の混乱を事前防止。これは他レーンの計画にない水準の丁寧さ
- **「やらないこと」の明確化**（§2.2）: CTX-N1〜N7 の 7 項目を理由付きで列挙。スコープの膨張を防止
- **テスト用 XML ヘルパー**（§8.5）: `_make_context_xml()` の導入判断は、20件超の新テストを支えるインフラとして適切
- **One Way to Do It 原則の徹底**（§10.5）: `filter_*()` メソッドへの統一は、ディファクトスタンダードを目指すライブラリとして正しい判断
- **網羅性の明記**（§4.2）: `filter_consolidated() ∪ filter_non_consolidated() = 全件` を保証する旨の記述はユーザーの不安を払拭する

---

## MUST（対応必須）

なし。Rev 3 の時点で MUST レベルの問題は全て解消済み。

---

## SHOULD（対応推奨）

### S-1: `ContextCollection` の内部フィルタメソッドでの不要コピーの回避方針

§5.1 で `__init__` が `dict(contexts)` で浅いコピーを取る設計は正しいが、`filter_consolidated()` 等のフィルタメソッドが内部で新しい dict を構築してからさらに `__init__` でコピーされると、メソッドチェーン `coll.filter_consolidated().filter_no_extra_dimensions().filter_duration()` で 3 回の不要コピーが発生する。

Context 数が最大 278 個（§10.6）のため**実用上の問題はゼロ**だが、実装者が「これは無駄では？」と感じてフィルタメソッド内で `__init__` をバイパスしようとすると設計の一貫性が崩れる。

**対応案**: §5.1 の設計方針に以下の一文を追記:

> フィルタメソッド内で構築した dict も `__init__` 経由で渡す（コピーが二重になるが、Context 数 ≤ 300 で無視できる）。将来パフォーマンスが問題になった場合に限り `_from_trusted_dict()` のようなプライベートコンストラクタを検討する。

これにより実装者が「コピーの二重化は意図的である」と理解でき、不要な最適化を避けられる。

### S-2: `_make_context_xml` ヘルパーの `dimensions` パラメータの具体的な使用例

§8.5 のシグネチャ定義は良いが、`dimensions: list[tuple[str, str, str]]` の `(ns, axis, member)` がテスト XML にどう展開されるかの具体例が1つあると、実装者が迷わない。

**対応案**: §8.5 に以下の使用例を追記:

```python
# 連結軸 + セグメント軸の2つの dimension を持つ Context
xml = _make_context_xml(
    "ctx_multi",
    start_date="2024-04-01",
    end_date="2025-03-31",
    dimensions=[
        (_JPPFS_NS, "ConsolidatedOrNonConsolidatedAxis", "NonConsolidatedMember"),
        (_JPPFS_NS, "BusinessSegmentsAxis", "ReportableSegmentsMember"),
    ],
)
# → xmlns の prefix は自動生成（ns0, ns1 等）で structure_contexts() 経由の
#   Clark notation 解決には影響しない
```

### S-3: テスト #42（結合テスト `test_collection_from_simple_pl_fixture`）の検証項目の補足

§8.6 の結合テスト #42 は `parse_xbrl_facts → structure_contexts → ContextCollection` のパイプラインをテストするが、検証項目が「パイプラインが動作する」以上の具体的アサーションを列挙していない。この fixture は 4 Context（CurrentYearDuration, CurrentYearInstant, CurrentYearDuration_NonConsolidatedMember, Prior1YearDuration）を含む（既存テスト `test_with_simple_pl_fixture` から確認）。

**対応案**: 以下の検証を追加すると、`ContextCollection` の実用性を端的に示せる:

```python
def test_collection_from_simple_pl_fixture(self):
    # ... parse & create collection ...
    assert len(coll) == 4
    assert len(coll.filter_consolidated()) == 3  # NonConsolidatedMember 以外
    assert len(coll.filter_non_consolidated()) == 1
    assert coll.latest_duration_period == DurationPeriod(
        start_date=datetime.date(2024, 4, 1),
        end_date=datetime.date(2025, 3, 31),
    )
    assert coll.latest_instant_period == InstantPeriod(
        instant=datetime.date(2025, 3, 31),
    )
```

これにより「実データ（に近いフィクスチャ）で ContextCollection が期待通り動作する」ことの End-to-End 証明になる。

---

## MAY（検討事項・任意）

### Y-1: `ContextCollection` に `__repr__` だけでなく `_repr_html_` を将来検討

FEATURES.md に `display/html` が TODO として記載されている。`ContextCollection` は REPL / Jupyter での探索的データ分析の起点になりうるため、将来的には `_repr_html_` で Context の一覧をテーブル表示できると開発体験が向上する。ただし L4 のスコープではなく、`display/html` 実装時のタスクとして記録する程度でよい。

### Y-2: `has_dimension()` メソッドと `get_dimension_member()` メソッドの axis 引数における local_name 対応の将来パス

§5.2 の `filter_by_dimension()` の Note に local_name 版の将来検討が記載されているが、`StructuredContext.has_dimension(axis)` / `get_dimension_member(axis)` にも同じ問題がある。これらも Clark notation を要求するため、タクソノミバージョンを含む完全な namespace を知らないと使えない。

**将来的な対応案**: `has_dimension("ConsolidatedOrNonConsolidatedAxis")` のように local_name のみで検索できるオーバーロード。ただし L4 のスコープ外であり、現時点では`endswith` ベースの `is_consolidated` プロパティで主要ユースケースがカバーされているため不要。認識だけしておけば十分。

---

## 前回フィードバック（Rev 3）反映の確認

| 前回 FB# | 反映状況 | コメント |
|---|---|---|
| S-1 | 適切に反映 | #32 `test_collection_getitem_missing_raises_keyerror` を P0 に追加。`__getitem__` の error contract が明確化 |
| S-2 | 適切に反映 | `endswith` 方式を §4.3 に明記。`statements.py` との方式統一により Wave 3 の差異を最小化 |
| S-3 | 適切に反映 | §0 マイルストーンにレシピ 3 パターンを追記。`statements.py` の内部ロジック開放としての位置づけが明確 |
| S-4 | 適切に反映 | 網羅性を §4.2 に1行追記。`filter_consolidated() ∪ filter_non_consolidated() = 全件` |
| Y-1 | 採用 | `Mapping` 非準拠の Note を class docstring に追記 |
| Y-2 | 不採用 | `__or__` は YAGNI。適切な判断 |
| Y-3 | 不採用 | #28 で暗黙カバー。独立テストは冗長。適切な判断 |
| NEW-9 | 採用 | #32 として P0 に追加（S-1 に含む） |

全項目が適切に反映されている。

---

## まとめ

| 区分 | 件数 | 重要項目 |
|------|------|----------|
| MUST | 0 | — |
| SHOULD | 3 | S-1: 内部コピーの意図的許容を明記、S-2: ヘルパーの使用例追記、S-3: 結合テストの検証項目補足 |
| MAY | 2 | Y-1: `_repr_html_` 将来メモ、Y-2: local_name 検索の将来パス |

**結論**: 計画は実装着手可能。MUST 未解決なし。SHOULD 3 件は全て「計画ドキュメントへの数行追記」で対応可能な軽微な改善提案であり、実装品質に直接影響するものではない。3 回のフィードバックサイクルを経て、データモデル・API 設計・テスト計画・後方互換性・設計判断の根拠がいずれも十分な水準に達しており、**このまま実装に着手して問題ない**。

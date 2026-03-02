# WAVE 1 LANE 5 フィードバック

## 総合評価

**★★★★☆ (4/5)** — 非常に高品質な計画。QA 調査の引用が正確で、データモデル設計もシンプルかつ拡張性がある。以下の指摘を反映すれば ★5 相当。

---

## MUST FIX（実装前に修正すべき）

### MF-1: `EDINET_FILER_BASE` の命名が誤解を招く

`EDINET_FILER_BASE = "http://disclosure.edinet-fsa.go.jp/"` は EDINET ドメイン全体のベース URL であり、標準タクソノミ URI も同じプレフィックスで始まる。「FILER 用ベース」という名前は不正確。

**修正案**: 定数を2つに分けるか、名前を変える。

```python
# 案A: ドメイン全体のベースとして定義
EDINET_BASE = "http://disclosure.edinet-fsa.go.jp/"
"""EDINET の名前空間 URI のベースドメイン。"""

EDINET_TAXONOMY_BASE = "http://disclosure.edinet-fsa.go.jp/taxonomy/"
"""EDINET 標準タクソノミの名前空間 URI はこのプレフィックスで始まる。"""

# 案B: FILER_BASE を削除し、判定ロジックのみで処理
# classify_namespace 内で EDINET_BASE.startswith + not TAXONOMY_BASE で判定
```

案A を推奨。`EDINET_FILER_BASE` は「提出者用ベース」と読めるが、実際には標準タクソノミも含むプレフィックスなので、後続レーンの開発者が混乱する可能性がある。

### MF-2: `NS_NUM` / `NS_NONNUM` の分類が未定義

Step 1 で `NS_NUM` と `NS_NONNUM` を追加しているが、これらが `_XBRL_INFRASTRUCTURE_URIS` に含まれるのか `OTHER` に分類されるのかが明示されていない。テスト設計（4.4, 4.5）にも登場しない。

**修正案**: 明示的に分類を決定し、テストに含める。`NS_NUM`/`NS_NONNUM` は XBRL の Data Type Registry の名前空間であり、Fact の type 属性に使われる。`XBRL_INFRASTRUCTURE` に含めるのが自然。ただし現行パーサーでは使用していないので `OTHER` でも可。いずれにせよ意図を明記すること。

### MF-3: `_XBRL_INFRASTRUCTURE_URIS` に `NS_XSI` / `NS_XML` を含めない理由の明示

テスト 4.5 で `NS_XSI` と `NS_XML` が `OTHER` に分類されることが期待されているが、なぜ `XBRL_INFRASTRUCTURE` ではないのかの根拠が欠けている。W3C の汎用名前空間であり XBRL 固有ではないから、という理由なら Section 7 に記載すべき。

後続レーンの開発者が `NS_XSI` を `XBRL_INFRASTRUCTURE` と期待する可能性がある。

### MF-4: Step 4 のフォールバック分岐の実装詳細が曖昧

Section 7 Q3 で「`EDINET_TAXONOMY_BASE` で始まるが正規表現に合わない URI は `STANDARD_TAXONOMY` として扱い、`module_name` と `taxonomy_version` を `None` にする」と述べている。しかし Step 4 の分類ロジック:

> 1. `_STANDARD_TAXONOMY_PATTERN` にマッチ → `STANDARD_TAXONOMY`
> 2. `EDINET_FILER_BASE` で始まり、`EDINET_TAXONOMY_BASE` で始まらない → `FILER_TAXONOMY`

ではフォールバックパスが明示されていない。正規表現にマッチしないが `EDINET_TAXONOMY_BASE` で始まる URI はステップ2でも捕捉されず、ステップ4の `OTHER` に落ちてしまう。

**修正案**: ステップ間に明示的なフォールバックを追加:

```
1. _STANDARD_TAXONOMY_PATTERN にマッチ → STANDARD_TAXONOMY (module_name, taxonomy_version あり)
1b. EDINET_TAXONOMY_BASE で始まるが正規表現不一致 → STANDARD_TAXONOMY (module_name=None, taxonomy_version=None)
2. EDINET_BASE で始まり EDINET_TAXONOMY_BASE で始まらない → FILER_TAXONOMY
3. _XBRL_INFRASTRUCTURE_URIS に含まれる → XBRL_INFRASTRUCTURE
4. その他 → OTHER
```

テストにもこのフォールバックケースを追加すべき:

```python
def test_standard_taxonomy_unknown_format():
    """EDINET_TAXONOMY_BASE で始まるが既知パターンに合わない URI。"""
    uri = "http://disclosure.edinet-fsa.go.jp/taxonomy/unknown/format"
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.STANDARD_TAXONOMY
    assert info.is_standard is True
    assert info.module_name is None
    assert info.taxonomy_version is None
```

---

## SHOULD FIX（品質向上のために推奨）

### SF-1: 便利関数は `classify_namespace` に委譲すべきことを明記

`is_standard_taxonomy`, `is_filer_namespace`, `extract_taxonomy_module`, `extract_taxonomy_version` の実装が `classify_namespace` を内部で呼ぶのか、独自にパースするのかが不明。

キャッシュの恩恵を受けるために、すべて `classify_namespace` に委譲すべき:

```python
def is_standard_taxonomy(uri: str) -> bool:
    return classify_namespace(uri).is_standard

def extract_taxonomy_module(uri: str) -> str | None:
    return classify_namespace(uri).module_name
```

これを明記すれば実装エージェントの誤解を防げる。

### SF-2: テスト 4.8 (`test_classify_is_cached`) はデトロイト派の観点で議論の余地あり

`result1 is result2` によるキャッシュの内部実装テストは、実装詳細への依存が強い。CLAUDE.md の「リファクタリング耐性が高いテスト」の方針とやや矛盾する。

**代替案**: キャッシュの存在は性能テストとして別途検証するか、あるいは「同一入力に対して等しい結果を返す」ことだけをテストする。

```python
def test_classify_returns_equal_results_for_same_uri():
    """同一 URI に対する呼び出しが同一結果を返すことを確認する。"""
    uri = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
    result1 = classify_namespace(uri)
    result2 = classify_namespace(uri)
    assert result1 == result2
```

ただし、frozen dataclass + lru_cache は安定した実装パターンなので、`is` テストを残すこと自体は許容範囲。判断は実装者に委ねて良い。

### SF-3: 提出者別 EDINET コードの正規表現パターンの堅牢性

`_FILER_TAXONOMY_PATTERN` の `(?P<edinet_code>[A-Z0-9]+)` は大文字英数字のみを想定しているが、EDINET コードは実際には `E` + 5桁数字（例: `E02144`）または `X` + 5桁数字（サンプル用）のパターン。

より厳密にするなら:

```python
r"(?P<edinet_code>[A-Z]\d{5})"
```

ただし将来のコード体系変更を考慮すると現行の緩いパターンでも可。設計判断として Section 7 に記載すると良い。

### SF-4: `lru_cache` のテスト間汚染対策

`lru_cache` を使うと、テスト間でキャッシュが共有される。テストの独立性を確保するために `classify_namespace.cache_clear()` を `conftest.py` の autouse fixture か各テストの setup で呼ぶべき。

```python
@pytest.fixture(autouse=True)
def clear_namespace_cache():
    classify_namespace.cache_clear()
    yield
    classify_namespace.cache_clear()
```

これがないと、テスト実行順序によって `is` テスト（4.8）の挙動が変わる可能性がある。

---

## CONSIDER（検討事項・より良い設計のためのヒント）

### C-1: `NamespaceInfo` に `module_group` フィールドの追加を検討

現在 `module_name` は `jppfs_cor` のような値を持つ。しかし後続レーン（特に Wave 2 の `standards/detect`）では `jppfs`（module_group）単位で分岐する場面が多い。

```python
# 現在の設計で module_group を取得するには文字列操作が必要
module_group = info.module_name.split("_")[0] if info.module_name else None

# module_group フィールドがあれば直接アクセスできる
assert info.module_group == "jppfs"
```

正規表現ですでに `module_group` をキャプチャしているので、コスト0で追加可能。追加するならデフォルト値 `None` で後方互換性を維持。

### C-2: IFRS の名前空間に関する明示的な注記

A-1.a.md によると、EDINET の IFRS 企業は IASB の `ifrs-full` 名前空間ではなく `jpigp_cor`（EDINET 独自）を使用する。この事実を Section 7 に Design Decision として記載すると、後続の `standards/detect`（Wave 2 L2）開発者が「なぜ `ifrs-full` の分類がないのか」と疑問に思うのを防げる。

### C-3: XBRL Formula 関連名前空間の将来拡張

FEATURES.md の C-12 に XBRL Formula / Assertion Linkbase が `[v0.2.0+]` として記載されている。Formula 関連の名前空間（`http://xbrl.org/2008/formula` 等）は現時点で定数を追加しなくても良いが、`_XBRL_INFRASTRUCTURE_URIS` が将来拡張されることを前提とした設計（frozenset で良い）であることを注記しておくと親切。

### C-4: エラーハンドリング方針

`classify_namespace(None)` や `classify_namespace(123)` のような不正入力に対する挙動が未定義。`TypeError` を投げるのか、`OTHER` として扱うのか。

推奨: 型アノテーション `str` を信頼し、ランタイムのガードは不要。Python のダックタイピング方針と一致。ただし方針を Section 7 に一言書いておくと良い。

---

## 他レーン計画との整合性チェック

| チェック項目 | 結果 |
|-------------|------|
| L4 (contexts) との衝突 | **問題なし** — L4 は `contexts.py` のみ変更、L5 は `_namespaces.py` のみ変更 |
| L4 が import する `NS_XBRLI`, `NS_XBRLDI` | **問題なし** — 既存定数は不変 |
| L1-3 (linkbase) が import する `NS_LINK`, `NS_XLINK` | **問題なし** — 既存定数は不変 |
| L6 (dei) との連携 | **問題なし** — L6 は `_namespaces.py` を読み取り専用で利用 |
| Wave 2 L2 (standards/detect) への接続 | **良好** — `classify_namespace()` + `extract_taxonomy_module()` で会計基準判別に必要な情報を提供 |
| テストフィクスチャの衝突 | **問題なし** — L5 はフィクスチャを使用しない（純粋関数のテストのみ） |

---

## まとめ

Lane 5 は Wave 1 の中で最もスコープが明確で、衝突リスクが低いレーン。計画の品質は高く、MF-1〜MF-4 の修正を反映すれば実装に直接入れる完成度。特に MF-4（フォールバック分岐の明示）は後続レーンのロバスト性に直結するため必ず対応すべき。

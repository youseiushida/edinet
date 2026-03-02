# Wave 3 / Lane 1 — 実装レビュー結果

## 総合評価: 合格（統合可能）

計画書の完了条件 7 項目すべてを満たしています。全 1252 テスト PASSED、ruff All checks passed。既存テストへの回帰なし。

---

## テスト結果

- `uv run pytest` — **1252 passed**, 6 skipped, 7 deselected
- `uv run ruff check` — **All checks passed**
- 既存テストへの回帰: **なし**

---

## 完了条件チェック

| # | 条件 | 状態 | 備考 |
|---|------|------|------|
| 1 | 全会計基準で財務諸表が出る | OK | J-GAAP/IFRS/US-GAAP/JMIS/UNKNOWN すべてテスト済み |
| 2 | 後方互換性が維持される | OK | `build_statements(items)` のみの呼び出し全テスト PASS |
| 3 | JSON 二重管理が解消される | OK | `data/*.json` 6 ファイル削除済み、レガシー関数残留 0 件 |
| 4 | テスト | OK | 全 PASS、ruff PASS |
| 5 | normalize API が使える | OK | T01-T21 全 PASS |
| 6 | IFRS マッピング拡張 | OK | 35 → 41 (KPI 2 + CI 3 + BS 1) |
| 7 | `detected_standard` プロパティ | OK | T-S03, T-S04, T-S05 で検証済み |

---

## レーンルール遵守

| ルール | 状態 |
|--------|------|
| `__init__.py` 未変更 | OK |
| 他レーンファイル未変更 | OK |
| 公開インターフェース不変 | OK |
| `stubgen` 未実行 | OK |
| テストフィクスチャ未変更 | OK |

---

## 良い点

### 設計

1. **normalize.py のファサード設計が適切**: `get_known_concepts` / `get_concept_order` / `cross_standard_lookup` の 3 関数が Single Source of Truth として機能しており、`statements.py` の JSON 依存を完全に排除。`@lru_cache` による再呼び出しコスト排除も良い。

2. **detail_level ベースのディスパッチが堅牢**: `_build_for_type()` による DRY 解消が綺麗。BLOCK_ONLY / DETAILED の二分岐でコードの見通しが良い。将来の JMIS DETAILED 化にも対応可能。

3. **US-GAAP のサマリー変換が丁寧**: `_build_usgaap_statement()` が `jgaap.reverse_lookup(si.key)` → `statement_type` フィルタ → `LineItem` 変換という明確なパイプライン。期間フィルタリング（`_select_latest_usgaap_period`）も BS/PL/CF の期間型の違いを正しく扱っている。

4. **後方互換が完璧**: `build_statements(items)` のみの既存呼び出しは `facts=None` → `detected=None` → J-GAAP フォールバックと、全パスが維持。

5. **JSON → Python 統一の移行が安全**: Step 1 → Step 2 → Step 3 の段階的アプローチで各ステップ間でテストが通る状態を維持。

### テスト

6. **Detroit 派のテスト設計**: 全テストが公開 API のみをテストしており、内部実装の変更に対して堅牢。

7. **安全ネットテスト (T19-T21) が優れている**: 将来の `_MAPPINGS` 追加時に canonical_key 忘れや PL/BS/CF 間の重複を防ぐメタテスト。

### コード品質

8. **Docstring が Google Style + 日本語で統一**: CLAUDE.md の規約に完全準拠。

9. **`__all__` が正確に定義**: normalize.py の公開 API が明確。

---

## 指摘事項

### H（高: 修正推奨）

なし

### M（中: 改善推奨）

#### M-1: `_build_usgaap_statement` の `namespace_uri=""` と `concept=si.concept` が計画と乖離

`statements.py:482-483` で `namespace_uri=""` / `concept=si.concept` としているが、計画書 (セクション 2.5.2) では `namespace_uri=NS_JPCRP_COR` / `concept=f"{{{NS_JPCRP_COR}}}{si.concept}"` (Clark notation) とする設計だった。

現時点では LineItem の namespace_uri/concept を参照する下流コードがないため実害はないが、将来の DataFrame 変換や display で正しい名前空間が期待される可能性がある。

**判定**: 計画書からの乖離。US-GAAP サマリーのユースケースが限定的なので優先度は低いが、将来の統合時に修正推奨。

#### M-2: `_select_latest_usgaap_period` のシグネチャが計画と異なる

計画書では `available_periods: tuple[Period, ...]` を受け取る設計だったが、実装では `items: Sequence[_USGAAPSummaryItemType]` を受け取り内部で `.period` を抽出する形。これ自体は合理的な変更。

**判定**: 実装の方が合理的。計画書更新のみで OK。

### L（低: 将来の改善候補）

#### L-1: `detail_level_for_standard()` が未使用

`normalize.py:196-212` の `detail_level_for_standard()` は `statements.py` から使われていない。`statements.py` では `self._detected_standard.detail_level` を直接参照。

**判定**: 将来の拡張ポイントとして残すか、YAGNI として削除するか。どちらでもよい。

#### L-2: T-S06, T-S11, T-S12（US-GAAP サマリーテスト）が未実装

計画書に列挙された US-GAAP の `_build_usgaap_statement` パスのユニットテストが欠如。E2E テスト（実データ依存）でカバーする方針なら許容できるが、ユニットテストとしても最低限のパスを通すテストがあると安心。

**判定**: US-GAAP 企業が 6 社と少数なので E2E カバーで実用上は問題ない。将来テスト追加を推奨。

#### L-3: テストクラス名に "JSON" が残存

`TestJsonOnlyFiltering` や docstring の "JSON に定義されていない" 等の表現が残っている。JSON は廃止されたので名前を更新する方がコードの意図が明確になる。

**判定**: コスメティック。

---

## バグ解決状況

| BUG | 状態 | 備考 |
|-----|------|------|
| BUG-2~5 | 解決 | IFRS/US-GAAP ディスパッチが実装され正しい概念セットが使用される |
| BUG-6 | 解決 | `mappings_for_statement(PL)` が PL 概念のみを返すため SS/CF 混入が排除 |
| BUG-1 | 解決 | `canonical_key` 経由の正規化マッピングに置換 |
| BUG-7 | 改善 | 概念セットの厳密化により候補数が適正化 |

---

## まとめ

| 優先度 | 件数 | 概要 |
|--------|------|------|
| HIGH | 0 | - |
| MEDIUM | 2 | US-GAAP の namespace_uri/concept の計画乖離、period 選択シグネチャの計画乖離 |
| LOW | 3 | 未使用ヘルパー関数、US-GAAP ユニットテスト不足、テスト名の JSON 残存 |

**HIGH 指摘なし。このまま統合して問題ありません。** MEDIUM 2件は将来の統合時に修正すれば十分。LOW 3件は余力があれば対応。

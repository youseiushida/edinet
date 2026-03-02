# Wave 3 / Lane 4 フィードバック（第7回）

## 総評

第6回フィードバックで「実装開始可能」と判断された計画に対し、L2/L3 の計画、既存 jgaap.py の実装（ConceptMapping / API パターン / `_validate_registry()`）、E-5/C-3 の QA、TEMP.md、SCOPE.md、FEATURES.md、および FUTUREFEEDBACK.temp.md の並列安全ルールとの突合を行い、最終レビューを実施した。

**結論: 実装開始可能。前回判断を支持。以下は品質向上のための補足指摘。**

6回のフィードバックを経て極めて高品質な計画であり、アーキテクチャ（SectorRegistry パターン）、並列安全性、テスト設計、normalize 接続設計のいずれも十分に練られている。

---

## MUST（修正必須）

なし。

---

## SHOULD（強く推奨）

### S-1: `display_order` と `industry_codes` のフィールド位置による dataclass コンストラクタの使い勝手

**問題**: §3.1 の `SectorConceptMapping` では `display_order: int` が `industry_codes` の後、`general_equivalent` の前に配置されている。これにより全 8 フィールドが必須の位置引数になる。一方、jgaap.py の `ConceptMapping` では `display_order: int = 0` とデフォルト値を持つ。

**影響**: L4 の設計判断として `display_order` を必須にすること自体は正当（§3.3 で `> 0` を検証するため）。しかしフィールドの位置が `industry_codes` → `display_order` → `general_equivalent`（デフォルトあり）となっているため、`industry_codes` を同一タプル内の全エントリで反復記述する必要がある。例えば証券業の全マッピングで `industry_codes=frozenset({"sec"})` を 13 回以上書くことになる。

**対処案**: これは実装時のエルゴノミクスの問題であり、計画修正は不要。実装時に `_sec = frozenset({"sec"})` のようなモジュールレベル定数を定義してタイピングを省力化すれば十分。§4.2 のコード例で既にこのパターンを示唆している。確認のみ。

### S-2: 前回 S-1 の §12.3 追記が反映済みであることの確認

**確認結果**: §12.3 に `statement_type` 型不整合の注記が追記されている（行1147-1149: 「L2/L3 の KPI 概念（statement_type=None）を吸収するために必要」「L4 の 3 業種は KPI を持たないため、L4 単体では影響なし」）。**対処済み。**

また、前回 C-1 の L2/L3 との API 表面差異も §12.3 の項目 5 として追記されている（行1157-1160）。**こちらも対処済み。**

---

## CONSIDER（検討推奨）

### C-1: jgaap.py の `ConceptMapping` との `display_order` デフォルト値の非対称性

**現状**:
- jgaap.py: `display_order: int = 0`（デフォルトあり）
- L4: `display_order: int`（デフォルトなし、必須）

L4 のバリデーション（`_validate()` で `display_order > 0` を検証）からすれば `display_order` を必須にするのは合理的。しかし jgaap.py 側は `display_order = 0` を許容しているため、将来 SectorRegistry で jgaap.py の ConceptMapping を扱おうとした場合に不整合が生じる。

**対処**: 現時点では問題なし。SectorConceptMapping と ConceptMapping は意図的に別型であり、統合は §12.3 で対処する設計。ただし統合時に jgaap.py 側の `display_order` デフォルト値も `0` → 必須に変更する必要があることを §12.3 に 1 行追記するとよい。**ブロッキングではない。**

### C-2: `_validate()` の `industry_codes ⊆ profile.industry_codes` 検証の意義

**観察**: L4 の 3 業種はそれぞれ単一の業種コード（`cns` / `rwy` / `sec`）を持つため、`industry_codes ⊆ profile.industry_codes` のバリデーションは自明（常に `frozenset({"sec"}) ⊆ frozenset({"sec"})` で True）。

**一方**: L2（banking）では `bk1` と `bk2` があり、特定のマッピングが `bk2` のみに適用される場合にこの検証が有効になる。SectorRegistry は L2/L3 統合後に銀行業・保険業でも使われるため、この検証は将来の正しさを先取りしている。

**対処**: 現状で正しい。確認のみ。

### C-3: 鉄道業の concept 名の不確実性が他2業種より高い

**観察**: §5.1（証券業）は E-5.a.md で確認済みの concept 名を使用しており信頼性が高い。§5.3（建設業）は推定だが概念が明確（完成工事高/原価/総利益）。一方 §5.6（鉄道業）は推定 concept 名が 7 件あり、`TransportationRevenues`, `RailwayOperatingRevenues`, `IncidentalBusinessRevenues` 等が実際のタクソノミ XSD に存在するかは未確認。

**リスク**: Step 1 調査で大幅な concept 名変更が発生した場合、鉄道業モジュールのスコープが変わる可能性がある。

**対処**: §9.5 のフォールバック手順が整備されているため計画修正不要。Step 1 調査を最優先で実施し、3 業種の中で鉄道業を最後（Step 5）に実装する設計は正しい。

---

## 軽微（MINOR）

### L-1: `PeriodType` の再定義について

§3.1 で `PeriodType = Literal["instant", "duration"]` を `_base.py` で再定義している。理由として「sector モジュールは dei に依存しない独立モジュールとするため」と説明されている。これは dei.py / jgaap.py に続く 3 箇所目の定義になる。

§12.3 の統合タスク項目 8 で「共有モジュール（`edinet.xbrl._types` 等）に集約」と記載済みであり、現時点では問題なし。ただし、Python の `Literal["instant", "duration"]` は型エイリアスであり実行時の等価性には影響しないため、3 重定義は技術的に無害。確認のみ。

### L-2: §7.3 T25 / §7.4 T41 / §7.5 T59 の jgaap テスト時依存

`general_equivalent` が jgaap の `all_canonical_keys()` に存在するかを検証するテストが 3 箇所に分散している。DRY の観点からは `conftest.py` にヘルパーを置くか、パラメタライズで共通化する余地がある。

**対処**: テストの独立性（各ファイルが単独で実行可能）を優先するなら分散で正しい。Detroit 派のテスト原則にも合致する。**対処不要。**

### L-3: §10 の行数概算の妥当性

`_base.py` が 180-220 行という概算だが、`SectorRegistry` クラスの `_validate()` メソッドが 8 項目のバリデーションを含み、`__repr__` / `__len__` / 10 API メソッドを持つため、docstring を Google Style 日本語で書くと 250-280 行になる可能性がある。

**対処**: 概算の精度は実装品質に影響しないため問題なし。

---

## フィードバックサマリー

| ID | 分類 | 要約 | ブロッキング |
|----|------|------|------------|
| S-1 | SHOULD | `industry_codes` 反復記述のエルゴノミクス（実装時定数で対処可） | No |
| S-2 | SHOULD | 前回 S-1/C-1 の反映確認 → 対処済み | No |
| C-1 | CONSIDER | jgaap `display_order=0` との非対称性を §12.3 に追記推奨 | No |
| C-2 | CONSIDER | `industry_codes ⊆ profile.industry_codes` 検証の将来的意義 | No |
| C-3 | CONSIDER | 鉄道業 concept 名の不確実性（§9.5 で対処済み） | No |
| L-1 | MINOR | `PeriodType` 3重再定義（§12.3 で統合予定、問題なし） | No |
| L-2 | MINOR | jgaap テスト時依存の分散（DRY vs 独立性、現状で正しい） | No |
| L-3 | MINOR | `_base.py` 行数概算のずれ（影響なし） | No |

## 全体所見

**計画は実装開始可能な状態を維持している。第7回で新たなブロッキング事項は発見されなかった。**

7 回のフィードバックサイクルを通じて確認された品質:

1. **SectorRegistry パターン**: L4 の核心的な設計判断であり、3 モジュールの API 一貫性を構造的に保証する。jgaap.py の手書き API パターン（`_CONCEPT_INDEX` / `_CANONICAL_INDEX` / `_STATEMENT_INDEX` の 3 辞書 + 関数群）を `SectorRegistry.__init__` で集約しており、DRY 原則に忠実
2. **L2/L3 との互換性**: `general_equivalent` のセマンティクス（canonical_key を格納）が L2/L3 と統一されている。統合ロードマップ（§12.3）が 8 項目で具体的であり、統合タスクの担当者が迷わない
3. **テスト設計**: Detroit 派を貫徹。T25/T41/T59 の jgaap テスト時依存は「テストは検証のための特権コード」として明示的に許容されており、設計意図が明確
4. **推定値の柔軟性**: §5.3-5.6 の推定 concept 名に対し、§9.2/§9.5 の fallback 手順が整備済み。Step 1 調査結果に応じて柔軟に対応できる
5. **並列安全性**: 全て新規ファイル作成であり、他レーンとのファイル衝突リスクはゼロ

**結論: 即座に実装を開始してよい。SHOULD / CONSIDER の指摘は全て実装時に自然に対処可能な軽微な改善提案であり、計画の修正を待つ必要はない。**

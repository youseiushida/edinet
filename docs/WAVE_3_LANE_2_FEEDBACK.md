# Wave 3 / Lane 2 フィードバック（第4回）

## 総合評価

計画は3回のフィードバックを経て**非常に高い完成度**に達している。Section 12 のフィードバック反映サマリーが3回分すべて整理されており、変更の経緯が追跡可能。前回の SHOULD 3件（S-1: canonical_key サフィックス、S-2: all_mappings() 順序、S-3: cf_method 使途）も全て本文に反映済み。

以下は、Lane 1/3/4 の計画書および jgaap.py の実コードとの最終突合、および「ディファクトスタンダードなライブラリ」としての品質基準に照らした残存指摘。

---

## MUST: 修正が必要

なし。計画は実装着手可能。

---

## SHOULD: 強く推奨する改善点

### S-1. Lane 4 の `SectorRegistry` / `SectorConceptMapping` との型統一方針の欠如

**問題**: Lane 4 の計画書では `_base.py` に `SectorConceptMapping`（`ConceptMapping` の業種拡張版）と `SectorRegistry`（lookup/canonical_key 等の共通ロジック）を定義し、Lane 3 (insurance) もこれを利用する設計になっている。一方、Lane 2 は独自の `BankingConceptMapping` を定義し、手書きの公開 API 関数群を持つ。

**現状の問題点**:
- `BankingConceptMapping` と Lane 4 の `SectorConceptMapping` はほぼ同一のフィールド構成だが**別の型**
- Lane 1 (normalize.py) が業種ディスパッチする際、銀行業だけ戻り値の型が異なる
- `is_jgaap_specific` (jgaap.py) に相当するフィールドが banking.py にはない（`is_banking_concept()` 関数で代替）が、Lane 4 は `industry_codes` フィールドで表現

Section 11 に統合タスクとして記載済みだが、**初回実装の時点で `SectorConceptMapping` を使わない理由**が計画書に明記されていない。

**推奨**: Section 3.1 に以下の設計判断根拠を追記:

> 本レーンは並列安全ルール（§推奨事項8）により Lane 4 の `_base.py` に依存できないため、
> 独自の `BankingConceptMapping` を定義する。Wave 3 統合時に `SectorConceptMapping` への
> マイグレーションを行う（Section 11 参照）。フィールド構成を意図的に近似させ、統合コストを最小化する。

### S-2. jgaap.py に存在する `to_legacy_concept_list()` 互換 API の検討

**問題**: jgaap.py には `to_legacy_concept_list(statement_type)` という JSON 互換ブリッジ API が存在する。これは Wave 3 L1 が statements.py を書き換える際の移行パスとして使われる。

banking.py にはこの API がないが、L1 が銀行業の statements を構築する際に同等のデータが必要になる可能性がある。

**推奨**: 現時点では対応不要。L1 の計画書を確認したところ、L1 は `lookup()` / `canonical_key()` / `mappings_for_statement()` の API 経由でデータを取得する設計であり、`to_legacy_concept_list()` は JSON 廃止の移行期のみ使用する。banking.py は JSON レガシーを持たないため、このブリッジ API は不要。ただし、L1 の実装時に banking 統合で追加 API が必要になった場合は柔軟に対応すること。

### S-3. BS マッピングの具体的な concept 名リストの不足

**問題**: Section 6.3 の BS マッピングは概要のみ（3つの具体例 + `# ...` で省略）。PL マッピング（Section 6.1）が13科目全て具体的に記載されているのに対し、BS は ~12 科目の詳細が不明。

具体的に以下の点が未確定:
1. BS 銀行固有科目の正確な concept ローカル名（タクソノミ XSD での確認が必要）
2. `general_equivalent` の設定方針（`CashAndDueFromBanksAssetsBNK` → 一般事業の `CashAndDeposits` に近いが完全等価ではない、等の判断）
3. 負債の部の主要科目リスト（`DepositsLiabilitiesBNK` 以外）

**推奨**: 実装 Step 3 で BS マッピングを定義する際に、タクソノミの `r/bk1/` ディレクトリの Presentation Linkbase から実際の concept 名を確認すること。計画書への BS 全科目リストの追記は不要（実装時に確定すれば十分）だが、**科目数の見積もり ~12 が妥当かをタクソノミで検証すること**を Step 3 の作業内容に明記するとよい。

---

## CONSIDER: 検討を推奨する点

### C-1. `BankingConceptMapping` の `is_total` フィールドの活用方針

**問題**: Section 4.1 で `is_total: bool = False` が定義されている。PL マッピング（Section 6.1-6.2）では `OrdinaryIncome` に `is_total=True`、`IncomeBeforeIncomeTaxes` に `is_total=True` が設定されているが、銀行固有科目の `OrdinaryIncomeBNK`（経常収益）に `is_total` が設定されていない。

`OrdinaryIncomeBNK` は PL の最上位合計行であり、`is_total=True` とするのが自然ではないか。同様に `OrdinaryExpensesBNK`（経常費用）も合計行。

jgaap.py では `NetSales` に `is_total=False`（売上高は合計ではなく出発点）、`GrossProfit` に `is_total=True` としている。銀行業の経常収益は一般事業の売上高に相当する出発点だが、内訳（資金運用収益 + 役務取引等収益 + ...）の合計でもある。

**推奨**: 以下の科目に `is_total=True` を設定することを検討:
- `OrdinaryIncomeBNK`（経常収益 = 資金運用収益 + 役務取引等収益 + ... の合計）
- `OrdinaryExpensesBNK`（経常費用 = 資金調達費用 + 役務取引等費用 + ... の合計）

ただし jgaap.py の `NetSales` との対称性を重視するなら `is_total=False` のままでもよい。実装者の判断に委ねる。

### C-2. `display_order` の CF 直接法/間接法番号空間の分離 vs 統合

**問題**: Section 6.4 で CF の `display_order` を「直接法 1-4, 間接法 5-8, 共通 9-11」の連番にしている。これにより `mappings_for_statement(CF)` の結果を `display_order` でソートすると、直接法→間接法→共通の順になる。

しかし、実際に CF を表示する際は「直接法のみ」または「間接法のみ」のどちらか一方 + 共通科目を使う。直接法ユースケースでは `display_order` が 1, 2, 3, 4, 9, 10, 11 と飛び番になる。

**選択肢**:
- (A) 現状維持（連番）。表示時のフィルタリングは将来の display 機能の責務
- (B) 直接法と間接法で独立した `display_order` 空間を持つ（両方 1 始まり）。`_validate_registry` の一意性チェックを「同一 statement_type かつ直接法/間接法のグループ内で一意」に緩和

**推奨**: (A) 現状維持。計画の Section 6.4 の設計で問題ない。(B) は `_validate_registry` の複雑化を招き、銀行業 CF のためだけの特殊ロジックになる。表示順序の最適化は display 機能の責務。

### C-3. テストにおける concept 名の正確性の保証

**問題**: テストコード（Section 8.2-8.3）に記載された concept 名（`OrdinaryIncomeBNK`, `InterestIncomeOIBNK` 等）が**タクソノミの実際の concept 名と一致しているかの検証手段**が計画に記載されていない。

jgaap.py の場合、concept 名は jppfs_cor の XSD に定義されたものを使用しており、E2E テスト（Wave 2）で実データとの突合が行われている。banking.py の concept 名も同様にタクソノミ XSD で確認する必要がある。

**推奨**: 実装 Step 2 の前に、`concept_sets.derive_concept_sets()` を `industry_code="bk1"` で実行し、PL/BS/CF の実際の concept 名リストを取得すること。これにより計画書に記載された concept 名の正確性を検証できる。このステップは計画書 Step 2 の冒頭に「タクソノミからの concept 名確認」として追記するとよい。

---

## 軽微な指摘

### L-1. Section 2.1 の構造図における `TradingIncomeOIBNK` の注釈

> `特定取引収益 (TradingIncomeOIBNK)          ← bk2（特定取引勘定設置）で使用`

とあるが、Section 2.5 で「bk1 のタクソノミにも存在する」とも述べており、Section 6.1 では `industry_codes=frozenset({"bk1", "bk2"})` としている。Section 2.1 の注釈は「bk2 で**特に重要**」に修正するか、Section 6.1 のコメントと整合させるとよい。既に Section 6.1 のコメント `# bk2（特定取引勘定設置銀行）で特に重要だが、bk1 のタクソノミにも存在する` が正確な記述になっているため、実装上の問題はない。

### L-2. Section 7.5 の normalize 連携フローにおける業種コード取得

> `2. 企業の業種コードを取得（EDINET コード一覧 or schemaRef から推定）`

業種コードの取得方法は Lane 1 (normalize.py) の責務だが、**どのモジュールが業種コードを提供するか**が Lane 1 の計画書でもまだ未確定。banking.py 側としては `is_banking_industry(code)` の入力として業種コードを受け取れれば十分であり、取得方法への依存はない。記載として問題なし。

---

## まとめ

| 分類 | 件数 | 内容 |
|------|------|------|
| MUST | 0 | なし。実装着手可能 |
| SHOULD | 3 | SectorConceptMapping との型統一方針の明記、to_legacy 不要の確認、BS concept 名のタクソノミ検証 |
| CONSIDER | 3 | is_total の設定方針、CF display_order 空間、concept 名の正確性保証 |
| 軽微 | 2 | 注釈の整合性、業種コード取得方法 |

**結論**: 計画は**実装着手可能**。SHOULD の3件はいずれも計画書への注記追加レベルまたは実装時の作業手順確認であり、ブロッキングではない。3回のフィードバックで設計の核心（canonical_key 命名、共通科目の扱い、CF 直接法/間接法分離、_validate_registry の jgaap 非依存）が全て固まっている。

唯一の横断的懸念は **Lane 4 の `SectorConceptMapping` / `SectorRegistry` との型統一**だが、これは並列安全ルールにより Wave 3 実装中は解決不可能であり、統合タスクで対処する設計（Section 11）が正しい。計画書に「なぜ初回から SectorConceptMapping を使わないのか」の設計判断根拠を1文追記すれば完璧。

# EDINET ライブラリ ストレステスト総合レポート

実行日: 2026-03-03
テスト件数: 4スクリプト (breadth/depth/edge/targeted)
総実行時間: ~1,030秒 (約17分)
対象バージョン: v0.1.0相当

---

## エグゼクティブサマリー

### 総合評価: **実用段階に到達（J-GAAP中心。IFRS一部可。US-GAAPは限定的）**

| 観点 | 評価 | 詳細 |
|------|------|------|
| J-GAAP一般事業会社 | ★★★★☆ | PL/BS/CF全て正常動作。科目数も妥当 |
| J-GAAPセクター別（銀行・保険・建設） | ★★★★☆ | セクター固有科目を含めて正しくパース |
| IFRS | ★★★☆☆ | パース可能だがPLが10行（詳細科目がフィルタされている） |
| US-GAAP | ★★☆☆☆ | BLOCK_ONLY検出。PL3行/BS2行（SummaryOfBusinessResultsのみ） |
| 開発体験(DX) | ★★★★☆ | APIは直感的。一部関数のインターフェースに課題 |
| パフォーマンス | ★★★☆☆ | 1件パース平均3s。to_dataframe()初回20s問題あり |
| 堅牢性 | ★★★★★ | 1,354件中エラー2件(0.15%)。古いデータも問題なし |
| データ品質 | ★★★★☆ | 型安全。Decimal精度。ラベル日英完備 |

---

## 1. テスト対象企業と結果

### 1.1 会計基準別

| 基準 | 企業 | items数 | PL行 | BS行 | CF行 | 結果 |
|------|------|---------|------|------|------|------|
| J-GAAP | 日本甜菜製糖 | 1,939 | 29 | 38 | 28 | PASS |
| J-GAAP | 鹿島建設(建設) | 2,471 | 34 | 45 | 34 | PASS |
| J-GAAP | 東京海上日動(保険) | 1,515 | 45 | 44 | 42 | PASS |
| J-GAAP | みずほ信託銀行(銀行) | 89 | 4 | 8 | 1 | PASS |
| IFRS | ソフトバンクG | 2,246 | 10 | 38 | 20 | PASS(要改善) |
| US-GAAP | 野村HD | 1,604 | 3 | 2 | 3 | PASS(BLOCK_ONLY) |

### 1.2 セクター別固有科目

| セクター | 固有科目検出 | 例 |
|----------|-------------|-----|
| 建設業 | ○ | 完成工事未収入金、未成工事支出金、完成工事補償引当金 |
| 保険業 | ○ | 経常収益(INS)、資産運用収益、支払備金繰入額、正味収入保険料 |
| 銀行業 | ○ | 営業利益(PL4行のみ。銀行勘定科目は要確認) |

### 1.3 docType別

| docType | 件数(6/26) | パース | 備考 |
|---------|-----------|--------|------|
| 有価証券報告書(120) | 459件(XBRL452) | ○ | メイン対象 |
| 訂正有価証券報告書(130) | 16件 | ○ | parent_doc_idも正常 |
| 半期報告書(160) | 10件 | ○ | |
| 発行登録書(080) | 1件 | ○ | |
| 大量保有報告書(350) | 37件 | ○ | |

### 1.4 年代別

| 年度 | 日付 | 件数 | パース | 備考 |
|------|------|------|--------|------|
| 2019 | 2019-06-26 | 479件 | ○ | タクソノミバージョン違いでも問題なし |
| 2020 | 2020-06-26 | 721件 | ○ | |
| 2024 | 2024-06-26 | 485件 | ○ | |
| 2025 | 2025-06-26 | 452件 | ○ | |

---

## 2. 機能別テスト結果

### 2.1 コア機能（全PASS）

| 機能 | 結果 | 実行時間 | 備考 |
|------|------|----------|------|
| documents() | PASS | 0.2-10s | 日付範囲OK。休日=空リスト |
| Filing.xbrl() | PASS | 3-10s | ZIP→XBRL→Statementsの全パイプライン |
| income_statement() | PASS | 0.08-0.14s | 連結/個別/当期/前期 全て |
| balance_sheet() | PASS | 0.08s | |
| cash_flow_statement() | PASS | 0.44s | |
| search() | PASS | 即時 | 日本語/英語/local_name対応 |
| to_dataframe() | PASS | 0.01-0.05s | PL/BS単体は高速 |
| to_csv() | PASS | 0.12s | UTF-8-sig |
| to_parquet() | PASS | 0.69s | |
| to_excel() | PASS | 11.17s | openpyxl依存で低速 |
| to_dict() | PASS | 即時 | LLM/RAG向けフォーマット |
| build_summary() | PASS | 即時 | 会計基準/標準比率/セグメント数 |
| detect_custom_items() | PASS | 即時 | カスタム科目2.0%(日本甜菜製糖) |
| diff_periods() | PASS | 即時 | concept/label/old/new/difference |
| list_dimension_axes() | PASS | 即時 | 8次元(事業セグメント/役員/大株主等) |
| extract_segments() | PASS | 即時 | 9セグメント正しく抽出 |
| extract_employee_info() | PASS | 即時 | 従業員数/平均年齢/平均給与 |
| extract_text_blocks() | PASS | 即時 | 193ブロック |
| parse_footnote_links() | PASS | 0.01s | 89脚注リンク、8ユニーク脚注 |
| to_html() | PASS | 0.07s | table/tr生成OK |
| fetch_pdf() | PASS | 1.2s | 702KB PDF取得 |
| cache (2nd parse) | PASS | 0.26s | 1回目5.37s→2回目0.26s(20x高速化) |

### 2.2 失敗した機能

| 機能 | エラー | 原因 | 重要度 |
|------|--------|------|--------|
| validate_calculations(pl) | TypeError: missing calc_linkbase | 第2引数にCalcLinkbaseが必要だがStatementsから取得する手段がない | HIGH |
| detect_fiscal_year(stmts) | AttributeError | DEIオブジェクトが必要だがStatementsを渡している | HIGH |
| build_section_map(tbs) | TypeError: missing resolver | TaxonomyResolverが必要 | MEDIUM |

### 2.3 警告・非致命的問題

| 問題 | 発生頻度 | 影響 |
|------|----------|------|
| labelArc use='prohibited'警告 | 多くの企業 | 表示に影響なし（v0.1.0制約） |
| IFRS/US-GAAP Filing未対応警告 | IFRS/US-GAAP企業 | jppfs_cor以外のFactで発火 |
| N件の不正行をスキップ | ほぼ毎日 | 未知のdocTypeコードをスキップ |
| income_statement: 連結データなし、個別にフォールバック | 個別のみの企業 | 正常動作 |
| period='prior'を解決できません | DEI情報不足の企業 | 投資信託等 |

---

## 3. パフォーマンス分析

### 3.1 パース速度

| 処理 | 時間 | 備考 |
|------|------|------|
| documents() 1日分 | 0.2-1.0s | API応答時間依存 |
| documents() 日付範囲(89日) | 84s | 1日ずつ逐次APIコール |
| Filing.xbrl() (初回) | 3-10s | ZIP DL + XBRL parse + タクソノミ解決 |
| Filing.xbrl() (2回目) | 0.26s | キャッシュ効果大 |
| 10件バッチ (初回) | 29.55s | 平均2.96s/件 |
| 20件バッチ (初回) | 64.04s | 平均3.37s/件 |

### 3.2 ボトルネック

| 箇所 | 問題 | 重要度 |
|------|------|--------|
| **Statements.to_dataframe() 初回** | **20.68s (1,939 items)** | **CRITICAL** |
| Statements.to_dataframe() 2回目 | 0.04s (キャッシュ後) | OK |
| FinancialStatement.to_dataframe() | 0.005s (29 items) | OK |
| to_excel() | 11.17s | LOW (openpyxl依存) |
| documents() 大範囲 | 84s (89日) | MEDIUM |

> **注**: `Statements.to_dataframe()`の初回20sは、全1,939 LineItemのラベル解決が走るため。
> 2回目以降はキャッシュにより高速。FinancialStatement単体のto_dataframe()は常に高速。

### 3.3 エラー率

| スコープ | 対象 | エラー | エラー率 |
|----------|------|--------|----------|
| 6/26 全XBRL | 1,354件 | 2件 | 0.15% |
| 20件バッチ | 20件 | 1件 | 5% |
| 古いデータ(2019-2024) | 3件 | 0件 | 0% |

エラーケース: 野村アセットマネジメントの特定ZIP構造(doc_id: S100VP7L, S100VP7I)

---

## 4. API設計の課題

### 4.1 CRITICAL: validate_calculations() のインターフェース

```python
# 現状: calc_linkbaseを別途取得して渡す必要がある
calc = parse_calculation_linkbase(...)
result = edinet.validate_calculations(pl, calc)

# 期待: Statementsから直接検証できるべき
result = edinet.validate_calculations(pl)  # TypeError!
```

### 4.2 CRITICAL: detect_fiscal_year() のインターフェース

```python
# 現状: DEIオブジェクトが必要
dei = extract_dei(parsed.facts)
fy = edinet.detect_fiscal_year(dei)

# 期待: Statementsを渡せるべき
fy = edinet.detect_fiscal_year(stmts)  # AttributeError!
```

### 4.3 HIGH: Company属性名の不一致

```python
# Filing: f.filer_name
# Company: c.name_ja  (filer_nameは存在しない!)
# → 統一されていない
```

### 4.4 MEDIUM: IFRS PLの行数が少ない

```python
# IFRSのPLが10行しかない（ソフトバンクG）
# Revenue/NetSalesが PL に含まれていない
# search('Revenue') では14件見つかるのに PL フィルタで除外されている
```

### 4.5 MEDIUM: US-GAAP BLOCK_ONLY の限界

```python
# US-GAAP: PL 3行、BS 2行、CF 3行
# SummaryOfBusinessResultsのみ
# → 仕様通りだが、ユーザーへの説明が必要
```

---

## 5. 開発体験(DX)評価

### 5.1 良い点

1. **直感的なAPI**: `filing.xbrl()` → `stmts.income_statement()` のチェーンが自然
2. **日本語アクセス**: `pl["売上高"]` で科目にアクセスできる
3. **search()が強力**: 日本語/英語/local_nameでの部分一致検索
4. **to_dict()が便利**: LLM/RAG向けの構造化出力
5. **型安全**: Decimal, LabelInfo, Period等の型がしっかり
6. **キャッシュ効果**: 2回目パースが20x高速
7. **エラーメッセージが日本語**: `EdinetParseError: EDINET ZIP の解析に失敗しました`
8. **DocType enum**: name_ja/original/is_correctionが便利

### 5.2 改善点

1. **validate_calculations / detect_fiscal_year / build_section_map**: Statementsオブジェクトから直接呼べない
2. **extract_segments / list_dimension_axes**: 低レベルオブジェクト(items, context_map, resolver)が必要
3. **Company.name_ja vs Filing.filer_name**: 属性名の不統一
4. **to_dataframe()初回が遅い**: 20秒はJupyterでのインタラクティブ利用で致命的
5. **未来の日付で404**: 空リストを返すべき
6. **ResourceWarning**: SSLSocketが閉じられていない

---

## 6. 堅牢性評価

### 6.1 壊れないケース

- 休日の日付 → 空リスト
- 不正な日付形式 → ValueError（明確なメッセージ）
- 投資信託（非事業会社） → パース成功、PLなしは正常
- 訂正報告書 → parent_doc_id付きで正常パース
- 古いデータ(2019年〜) → タクソノミバージョン違いでも正常
- 大量保有報告書・発行登録書 → パース成功
- 12月決算企業 → 期間が正しく検出

### 6.2 壊れるケース

- 特定のZIP構造（野村アセットマネジメント一部ファイル）: 0.15%
- 未来の日付: 404エラー（空リストが望ましい）

---

## 7. データ品質チェック

### 7.1 LineItem品質

```
concept: {http://...jppfs_cor}NetSales
local_name: NetSales
label_ja: LabelInfo(text='売上高', role='.../label', lang='ja', source=STANDARD)
label_en: LabelInfo(text='Net sales', role='.../label', lang='en', source=STANDARD)
value: 64796000000 (Decimal)
unit_ref: JPY
decimals: -6
context_id: CurrentYearDuration
period: DurationPeriod(2024-04-01 ~ 2025-03-31)
entity_id: E00355-000
dimensions: ()
is_nil: False
source_line: 3975
order: 610
```

- 全数値がDecimal型（精度保証）
- 日英ラベル完備
- period/context/unit全て構造化
- source_lineでXBRL原文参照可能

### 7.2 diff品質

```python
DiffItem(
    concept='ComprehensiveIncome',
    label_ja=LabelInfo(text='包括利益', ...),
    label_en=LabelInfo(text='Comprehensive income', ...),
    old_value=Decimal('6053000000'),
    new_value=Decimal('2994000000'),
    difference=Decimal('-3059000000')
)
```

- concept/label/old/new/difference全て揃っている

---

## 8. 推奨改善事項（優先度順）

### P0 (即座に対応すべき)

1. **Statements.to_dataframe() 初回20秒問題**: ラベル解決のキャッシュ戦略見直し
2. **validate_calculations()**: Statementsを受け取るオーバーロード追加
3. **detect_fiscal_year()**: Statementsを受け取るオーバーロード追加

### P1 (次リリースまでに)

4. **IFRS PLの行数**: Revenue等の主要科目がフィルタされている問題の調査
5. **Company.name_ja → Filing.filer_nameとの統一**
6. **未来の日付で空リスト返却**: 404をキャッチして空リスト化
7. **build_section_map()**: resolverなしでも動作するようにする

### P2 (将来)

8. **US-GAAP BLOCK_ONLY時のユーザーガイダンス**: 「US-GAAPはSummaryOfBusinessResultsのみ」の説明
9. **ResourceWarning修正**: aclose()の自動呼び出し
10. **documents()大範囲のパフォーマンス**: 並列APIコール検討

---

## 9. テスト実行詳細

| テスト | PASS | FAIL | WARN | 時間 |
|--------|------|------|------|------|
| breadth (幅広カバレッジ) | 3 | 0 | 4 | 151s |
| depth (全機能深堀り) | 22 | 4 | 0 | 54s |
| edge (エッジケース) | 14 | 1 | 1 | 397s |
| targeted (弱点集中) | 5 | 0 | 0 | 427s |
| **合計** | **44** | **5** | **5** | **~1,029s** |

FAIL 5件の内訳:
- validate_calculations() ×2 (calc_linkbaseパラメータ不足)
- detect_fiscal_year() ×1 (Statementsではなく DEI が必要)
- build_section_map() ×1 (resolverパラメータ不足)
- 未来の日付 ×1 (404エラー)

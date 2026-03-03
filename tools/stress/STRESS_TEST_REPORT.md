# EDINET Library ストレステスト総合レポート
**実施日**: 2026-03-03
**テスト対象**: edinet ライブラリ (v0.1.x)
**テスト環境**: WSL2 on Windows, Python 3.x
**テスト企業**: 鹿島建設(J-GAAP), MUFG(J-GAAP銀行), トヨタ(IFRS), 野村HD(US-GAAP), JR東日本(J-GAAP鉄道), SOMPO HD(IFRS保険), ソフトバンクG, ソニー, ホンダ, 日産

---

## 1. 総合評価

| 評価項目 | 評価 | 概要 |
|---------|------|------|
| **堅牢性** | B | クラッシュせず動作。エラーハンドリング良好。ただし結果が不完全 |
| **DX（開発体験）** | D | 基本的な項目検索がほぼ全企業で失敗。使い方が分からない |
| **パフォーマンス** | D | 1社の有報取得に5-6分。実用に耐えない |
| **データ正確性** | C | 取れるデータは正確だが、取れない項目が多すぎる |
| **カバレッジ** | C | J-GAAP一般業種は良好。IFRS/US-GAAPは不完全 |

---

## 2. 致命的問題（Critical）

### CRITICAL-1: get()による基本項目検索がほぼ全企業で失敗

**影響**: ライブラリの中核機能が実質的に使えない

```python
pl = statements.income_statement(consolidated=True)
pl.get("営業利益")       # → None (実際のラベルは「営業利益又は営業損失（△）」)
pl.get("当期純利益")     # → None (実際は「当期純利益又は当期純損失（△）」)
pl.get("経常利益")       # → None (実際は「経常利益又は経常損失（△）」)
bs.get("資産合計")       # → None (実際は「資産」)
bs.get("純資産合計")     # → None (実際は「純資産」)
```

**テスト結果**:

| 企業 | 基準 | 売上高 | 営業利益 | 純利益 | 総資産 |
|------|------|--------|---------|--------|--------|
| 鹿島建設 | J-GAAP | `売上高`で取得可 | `営業利益`で取得不可 | 取得不可 | 取得不可 |
| MUFG | J-GAAP銀行 | `経常収益`で取得不可 | N/A | 取得不可 | 取得不可 |
| トヨタ | IFRS | `売上収益`で取得不可 | `営業利益`で取得不可 | 取得不可 | 取得不可 |
| 野村HD | US-GAAP | 3項目のみ(BLOCK_ONLY) | N/A | 取得不可 | 取得不可 |
| JR東日本 | J-GAAP | `営業収益`で取得不可 | 取得不可 | 取得不可 | 取得不可 |
| SOMPO | IFRS | PLに売上がない | 取得不可 | 取得不可 | 取得不可 |

**実際のラベル名（鹿島建設J-GAAP）**:
- `営業利益又は営業損失（△）` ← `営業利益` では見つからない
- `経常利益又は経常損失（△）` ← `経常利益` では見つからない
- `当期純利益又は当期純損失（△）` ← `当期純利益` では見つからない
- `親会社株主に帰属する当期純利益又は親会社株主に帰属する当期純損失（△）`
- BS: `資産` ← `資産合計` では見つからない
- BS: `純資産` ← `純資産合計` では見つからない

**実際のラベル名（トヨタIFRS）**:
- `営業利益（△損失）` ← `営業利益` では見つからない
- `当期利益（△損失）` ← `当期利益`や`当期純利益` では見つからない
- `親会社の所有者` ← ラベルが意味不明（親会社帰属純利益のこと）
- **売上収益がPLに存在しない**（9項目のみ）

**実際のラベル名（野村HD US-GAAP）**:
- PL全体で**たった3項目**（BLOCK_ONLY）
- BS全体で**たった2項目**
- `総資産額` ← `資産合計` では見つからない
- `純資産額` ← `純資産合計` では見つからない

### CRITICAL-2: latest()の所要時間が5-6分

**影響**: 実用ワークフローが成立しない

```python
company.latest(doc_type="有価証券報告書", start="2025-01-01", end="2025-12-31")
# → 345秒（5分45秒）!!
```

**原因**: EDINET APIが日次ベースのみ → 1年分 = ~250営業日のAPIコール at 1コール/秒

| 期間 | API呼び出し回数 | 所要時間 |
|------|---------------|---------|
| 1日 | 1 | 0.7-5.6秒 |
| 1ヶ月 | ~22 | 28秒 |
| 3ヶ月 | ~65 | 85秒 |
| 6ヶ月 | ~130 | 176秒 |
| 1年 | ~250 | **350秒** |

**自動車3社の比較分析に実際にかかった時間**: **1,457秒（24分）**

---

## 3. 重大問題（Major）

### MAJOR-1: Company.search()の全角/半角問題

```python
edinet.Company.search("三菱UFJ")    # → 0件（半角UFJ）
edinet.Company.search("三菱ＵＦＪ")  # → 12件（全角ＵＦＪ）
```

DB上の企業名は全角表記（「三菱ＵＦＪ」）のため、半角で検索すると見つからない。
英語検索は大文字小文字不問で動作する（`toyota` = `TOYOTA` = 5件）。

### MAJOR-2: by_industry()の部分一致が効かない

```python
edinet.Company.by_industry("銀行")    # → 0件
edinet.Company.by_industry("銀行業")  # → 5件（正確な名称が必要）
edinet.Company.by_industry("証券")    # → 0件
edinet.Company.by_industry("保険")    # → 0件
edinet.Company.by_industry("鉄道")    # → 0件
```

「銀行業」「建設業」のように「業」を付けないとヒットしない。証券・保険・鉄道は何を指定しても0件。

### MAJOR-3: IFRS企業のPL項目が極端に少ない

| 基準 | PL項目数 | 例 |
|------|---------|-----|
| J-GAAP | 30-41項目 | 鹿島建設: 34, JR東日本: 32 |
| IFRS | **9-11項目** | トヨタ: 9, SOMPO: 11 |
| US-GAAP | **3項目** | 野村HD: 3（BLOCK_ONLY） |

IFRSのトヨタでは**売上収益がPLに含まれない**。

### MAJOR-4: DetectedStandard の str() が冗長

```python
str(statements.detected_standard)
# → "DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>,
#    method=<DetectionMethod.DEI: 'dei'>, detail_level=..."
```

期待されるのは `"J-GAAP"` のような短い文字列。

### MAJOR-5: 大量の「不正行スキップ」警告

日付範囲クエリで毎日のように「N件の不正行をスキップ」という警告が出る。
1年分のクエリでは**数百の警告**が出力され、ログが汚染される。

---

## 4. 軽微な問題（Minor）

### MINOR-1: 日付範囲366日上限の境界
```python
edinet.documents(start="2025-01-01", end="2026-01-01")  # 366日 → OK（81,293件）
edinet.documents(start="2025-01-01", end="2026-01-02")  # 367日 → ValueError
```
境界チェック自体は正確だが、366日上限は知らないと罠にはまる。エラーメッセージは明瞭。

### MINOR-2: 不正日付のエラーメッセージ
```python
edinet.documents(date="not-a-date")
# → ValueError: date must be YYYY-MM-DD, got 'not-a-date'
```
明瞭で良い。

### MINOR-3: 存在しないキーのエラー
```python
pl["存在しない項目"]  # → KeyError（期待通り）
pl.get("存在しない項目")  # → None（期待通り）
```
辞書型インターフェースは適切に動作。

---

## 5. 良い点（Positive Findings）

### GOOD-1: 堅牢なエラーハンドリング
- 不正なEDINETコード → `None`を返却（クラッシュしない）
- 不正な証券コード → `None`を返却
- 空文字列検索 → 0件（クラッシュしない）
- 1000文字の検索 → 0件（クラッシュしない）
- 未来の日付 → `EdinetAPIError 404`
- 適切な例外階層（`EdinetError` → `EdinetAPIError`, `EdinetParseError`）

### GOOD-2: DocType文字列指定の柔軟性
```python
edinet.documents(doc_type="有価証券報告書")     # 日本語名
edinet.documents(doc_type="120")                # コード文字列
edinet.documents(doc_type=DocType.ANNUAL_SECURITIES_REPORT)  # enum
# → 全て同じ489件を返す
```

### GOOD-3: 証券コード4桁/5桁の両対応
```python
edinet.Company.from_sec_code("7203")   # → トヨタ自動車株式会社
edinet.Company.from_sec_code("72030")  # → トヨタ自動車株式会社（同一企業）
```

### GOOD-4: XBRLキャッシュの効果
```
1回目: 8.12秒
2回目: 0.31秒（キャッシュ）
高速化倍率: 26.2x
```

### GOOD-5: 前期/当期分離の正常動作
```python
pl_current = statements.income_statement(period="current")  # 当期: 34項目
pl_prior = statements.income_statement(period="prior")      # 前期: 34項目
# 大成建設: 当期売上高 2.62兆, 前期売上高 2.33兆（正しい値）
```

### GOOD-6: 連結/個別の正常動作
```python
statements.income_statement(consolidated=True)   # 連結PL
statements.income_statement(consolidated=False)  # 個別PL（41項目, 売上1.66兆）
```

### GOOD-7: DataFrame/CSV出力
- デフォルト5列、full=Trueで18列
- CSV出力は高速（0.1秒）
- 列名が適切

### GOOD-8: all_listed()の速度
```python
edinet.Company.all_listed()  # → 3,885社, 0.07秒
```

---

## 6. パフォーマンス詳細

| 操作 | 所要時間 | 備考 |
|------|---------|------|
| `documents(date=...)` | 0.7-5.6秒 | 日によって書類数が異なる |
| `documents(start, end)` 1ヶ月 | 28秒 | ~22 API calls |
| `documents(start, end)` 3ヶ月 | 85秒 | ~65 API calls |
| `documents(start, end)` 6ヶ月 | 176秒 | ~130 API calls |
| `documents(start, end)` 1年 | 350秒 | ~250 API calls |
| `company.latest()` 1年 | 345秒 | = documents(1年) + フィルタ |
| `filing.xbrl()` 初回 | 2.7-12.1秒 | ダウンロード + 解析 |
| `filing.xbrl()` 2回目 | 0.3秒 | キャッシュ |
| `Company.all_listed()` | 0.07秒 | メモリ内データ |
| `Company.search()` | 3.3秒 | 初回（コードリスト取得含む） |
| `pl.to_csv()` | 0.1秒 | |
| PL全項目イテレーション | <0.01秒 | |

---

## 7. 会計基準別カバレッジ

### J-GAAP（一般事業会社）
- **PL**: 30-34項目。売上高から包括利益まで。ただしget()でのラベル検索が困難
- **BS**: 39-45項目。主要科目が揃っている
- **CF**: 25-34項目
- **評価**: データは取れるが、ラベルの「又は...損失（△）」問題で実用的に使いにくい

### J-GAAP（銀行業）
- **PL**: 20項目。銀行特有の勘定科目（経常収益等）がget()で取得不能
- **BS**: 29項目
- **CF**: 25項目
- **評価**: 銀行業特有の科目名の対応が不十分

### IFRS
- **PL**: **9-11項目のみ**。売上収益がトヨタのPLに含まれない
- **BS**: 17-34項目
- **CF**: 18-28項目
- **評価**: IFRS対応は進行中だが、項目数が少なすぎて実用に耐えない

### US-GAAP
- **PL**: **3項目のみ**（BLOCK_ONLY）
- **BS**: **2項目のみ**
- **CF**: 3項目
- **評価**: 実質的に未対応。サマリーレベルのブロックデータのみ

---

## 8. 改善提案（優先度順）

### P0: get()の部分一致・エイリアス対応
`get("営業利益")` で `"営業利益又は営業損失（△）"` にマッチさせる。
最も簡単な方法: `in` 演算子で前方一致 or 部分一致チェック。

### P1: latest()の高速化
日付範囲の後ろから検索する（有報は6月に集中）、または有報提出期日から逆算して探索範囲を絞る。

### P2: IFRS/US-GAAP のPL項目数改善
IFRSの詳細タグ（not just summary blocks）を取得対象に含める。

### P3: Company.search()の全角半角正規化
検索時にUnicode正規化（NFKC）を適用する。

### P4: by_industry()の部分一致対応
`"銀行"` で `"銀行業"` にマッチさせる。

### P5: 不正行警告の抑制
日付範囲クエリ時の「N件の不正行をスキップ」警告を集約表示にする。

### P6: DetectedStandard.__str__()の改善
`"J-GAAP"` のような短い文字列を返すようにする。

---

## 9. テストスクリプト一覧

| ファイル | 内容 | 所要時間 |
|---------|------|---------|
| `r1_v2_all.py` | 6社×全基準カバレッジ | 2,164秒 |
| `r1_v3_itemdump.py` | 全項目名ダンプ | ~1,050秒 |
| `r2_edge_cases.py` | エッジケース10種 | 1,414秒 |
| `r3_performance.py` | パフォーマンス7種 | 1,606秒 |
| `r4_practical.py` | 実用シナリオ6種 | 1,457秒 |

全テスト合計: 約**7,700秒（約2時間8分）**

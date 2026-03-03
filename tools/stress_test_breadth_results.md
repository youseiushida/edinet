# ストレステスト: 幅広カバレッジ

実行日時: 2026-03-03

```

======================================================================
  1. 書類一覧取得 (documents API)
======================================================================
  2025-06-26 有報: 全459件, XBRL付き452件 (9.57s)
  日付範囲(6/25-27): 5332件 (2.90s)
  2025-11-14 半期報告書: 751件 (0.91s)

======================================================================
  2. J-GAAP 一般事業会社
======================================================================
  対象(フォールバック): 日本甜菜製糖株式会社 (doc_id=S100W4MW)
  [PASS] xbrl()パース  (7.44s)
    会計基準: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    連結データあり: True
    個別データあり: True
    全アイテム数: 1939
    PL: 29 行
      売上高: 64796000000
    BS: 38 行
    CF: 28 行
    PL(前期): 28 行
    DataFrame: 1939 行 × 18 列
    search('利益'): 136 件
    サマリー: Japan GAAP, 標準比率=98.0%, セグメント=103
    CSV: 10276 bytes
    Parquet: 14993 bytes
    DataFrame(full): 29行 × 18列

======================================================================
  3. IFRS企業
======================================================================
  対象: ソフトバンクグループ株式会社 (doc_id=S100W4HN) (5.33s)
    会計基準: DetectedStandard(standard=<AccountingStandard.IFRS: 'IFRS'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    連結データあり: True
    個別データあり: True
    全アイテム数: 2246
    PL: 10 行
    BS: 38 行
    CF: 20 行
    PL(前期): 10 行
    DataFrame: 2246 行 × 18 列
    search('利益'): 224 件
    サマリー: IFRS, 標準比率=87.4%, セグメント=99
    CSV: 3771 bytes
    Parquet: 13326 bytes
    DataFrame(full): 10行 × 18列

======================================================================
  4. US-GAAP企業
======================================================================
  → 6/26にはUS-GAAP企業なし。別日を試行...
  対象: 野村アセットマネジメント株式会社 (2025-03-27) (doc_id=S100V768)
    会計基準: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    連結データあり: True
    個別データあり: True
    全アイテム数: 168
    PL: 3 行
    BS: 6 行
    CF: なし（業種によっては正常）
    PL(前期): 3 行
    DataFrame: 168 行 × 18 列
    search('利益'): 8 件
    サマリー: Japan GAAP, 標準比率=99.4%, セグメント=1

======================================================================
  5. 銀行業（セクター別）
======================================================================
  [WARN] 銀行業企業が見つからず

======================================================================
  6. 建設業（セクター別）
======================================================================
  [WARN] 建設業企業が見つからず

======================================================================
  7. 鉄道業（セクター別）
======================================================================
  対象: 世紀東急工業株式会社 (doc_id=S100W69L)
  [PASS] 鉄道業パース  (4.15s)
    会計基準: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    連結データあり: True
    個別データあり: True
    全アイテム数: 1555
    PL: 28 行
      売上高: 99358000000
    BS: 38 行
    CF: 25 行
    PL(前期): 28 行
    DataFrame: 1555 行 × 18 列
    search('利益'): 140 件
    サマリー: Japan GAAP, 標準比率=98.2%, セグメント=72

======================================================================
  8. 半期報告書テスト
======================================================================
  対象: Ｔ＆Ｄアセットマネジメント株式会社 (doc_id=S100WVRO)
  [PASS] 半期報告書パース  (3.82s)
    会計基準: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.NAMESPACE: 'namespace'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=None, period_type=None, namespace_modules=frozenset({'jppfs', 'jpsps'}))
    連結データあり: False
    個別データあり: True
    全アイテム数: 79
    PL: 3 行
    BS: 6 行
    CF: なし（業種によっては正常）
    PL(前期): 3 行
    DataFrame: 79 行 × 18 列
    search('利益'): 8 件
    サマリー: Japan GAAP, 標準比率=100.0%, セグメント=1

======================================================================
  9. パフォーマンス: 複数企業連続パース
======================================================================
  10件連続パース: 29.55s (平均2.96s/件, 成功10, エラー0)

======================================================================
  10. Company API
======================================================================
  Company.search('トヨタ'): 5件
  [WARN] Company.search: 'Company' object has no attribute 'filer_name'
  [WARN] Company.from_sec_code: 'Company' object has no attribute 'filer_name'
  Company.by_industry('銀行'): 0件

======================================================================
  テスト結果サマリー
======================================================================
  PASS: 3
  FAIL: 0
  WARN: 4
  総実行時間: 150.6s
```

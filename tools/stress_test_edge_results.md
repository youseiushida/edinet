# ストレステスト: エッジケース

実行日時: 2026-03-03

```

======================================================================
  1. エラーハンドリング
======================================================================
  [FAIL] 未来の日付 (2026-04-02)  (6.55s)
         EdinetAPIError: EDINET API error 404: Not Found
  [PASS] 休日の日付 (2025-06-29 = 日曜)  (0.85s)
  [PASS] 空の日付範囲  (1.10s)
  [PASS] 不正な日付形式: 期待通りのエラー (0.00s)
         ValueError: date must be YYYY-MM-DD, got '2025/06/26'
  [PASS] 不正な日付形式2: 期待通りのエラー (0.00s)
         ValueError: date must be YYYY-MM-DD, got 'not-a-date'

======================================================================
  2. 訂正報告書
======================================================================
  訂正有価証券報告書: 16件
    月島ホールディングス株式会社 (doc_id=S100W666, parent=S100W02L)
  [PASS] 訂正報告書パース (月島ホールディングス株式会社)  (8.24s)
      items: 1789
    三菱ＵＦＪ信託銀行株式会社 (doc_id=S100W6P9, parent=S100VN0L)
    日本調剤株式会社 (doc_id=S100W697, parent=S100R1YS)
  [PASS] 訂正報告書パース (日本調剤株式会社)  (5.28s)
      items: 1457

======================================================================
  3. 投資信託・ETF（非事業会社）
======================================================================
  対象: 野村アセットマネジメント株式会社 (doc_type=DocType.AMENDED_SECURITIES_REGISTRATION)
  [PASS] 投資信託パース  (6.60s)
    items: 264
    standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    PL: 3行 (投信でPLが取れるのは意外)

======================================================================
  4. PDF取得
======================================================================
  PDF付き有報: 459件
  [PASS] fetch_pdf(): 702329 bytes (1.20s)
    PDF header: b'%PDF-1.5\r\n%\xe2\xe3\xcf\xd3\r\n1 0'

======================================================================
  5. 大量保有報告書
======================================================================
  大量保有報告書: 37件
    対象: 株式会社九州リースサービス
  [PASS] 大量保有報告書パース  (1.75s)
      items: 119

======================================================================
  6. 有価証券届出書
======================================================================
  有価証券届出書: 1件
    対象: 飯野海運株式会社
  [PASS] 有価証券届出書パース  (1.67s)
      items: 59

======================================================================
  7. 古い年代のデータ
======================================================================
  2020-06-26: 全731件, XBRL721件 (0.24s)
  [PASS] パース (2020-06-26, 株式会社タダノ)  (5.12s)
    items: 1801, standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
  2019-06-26: 全483件, XBRL479件 (0.29s)
  [PASS] パース (2019-06-26, 株式会社タダノ)  (4.75s)
    items: 1779, standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
  2024-06-26: 全492件, XBRL485件 (0.25s)
  [PASS] パース (2024-06-26, シンデン・ハイテックス株式会社)  (3.47s)
    items: 1257, standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())

======================================================================
  8. キャッシュ動作
======================================================================
  [PASS] cache_info()  (0.00s)
    CacheInfo(enabled=False, cache_dir=None, entry_count=0, total_bytes=0)
  1回目パース: 5.37s
  2回目パース: 0.26s
  [PASS] キャッシュ効果あり (5%)

======================================================================
  9. 型安全性チェック
======================================================================
  [PASS] Filing.doc_id: str = 'S100W4MW'
  [PASS] Filing.filer_name: str = '日本甜菜製糖株式会社'
  [PASS] Filing.edinet_code: str = 'E00355'
  [PASS] Filing.sec_code: str = '21080'
  [PASS] Filing.has_xbrl: bool = True
  [PASS] Filing.has_pdf: bool = True
  [WARN] Filing.submit_date_time: 型不一致 (期待=(<class 'str'>, <class 'NoneType'>), 実際=datetime)
  [PASS] LineItem.value type: Decimal
  [PASS] LineItem.value type: Decimal
  [PASS] LineItem.value type: Decimal

======================================================================
  10. 日付範囲制限（90日）
======================================================================
  [PASS] 89日範囲  (84.06s)
  [INFO] 180日範囲: 42163件（エラーにならず）

======================================================================
  11. 多様なdocType
======================================================================
  有価証券報告書: 全459件, XBRL452件 (0.32s)
  半期報告書: 全10件, XBRL10件 (0.42s)
  発行登録書: 全1件, XBRL1件 (0.43s)
  大量保有報告書: 全37件, XBRL37件 (0.50s)

======================================================================
  12. パフォーマンス限界: 20件連続パース
======================================================================
  19件パース完了:
    合計: 64.04s
    平均: 3.37s
    最小: 1.38s
    最大: 5.42s
    平均アイテム数: 1164
    エラー: 1件

======================================================================
  テスト結果サマリー
======================================================================
  PASS: 14
  FAIL: 1
  WARN: 1
  総実行時間: 397.3s
```

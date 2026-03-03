# ストレステスト: 深堀りテスト

実行日時: 2026-03-03

```

======================================================================
  0. 対象企業の選定
======================================================================
  候補: 452件
  対象: 日本甜菜製糖株式会社 (doc_id=S100W4MW)
        submit: 2025-06-26 09:00:00
        edinet_code: E00355
        sec_code: 21080
        doc_type: DocType.ANNUAL_SECURITIES_REPORT
        has_xbrl: True

======================================================================
  1. fetch + parse
======================================================================
  [PASS] Filing.xbrl()  (9.52s)
    detected_standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    has_consolidated: True
    has_non_consolidated: True
    total items: 1939
    period_classification: PeriodClassification(current_duration=DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31)), prior_duration=DurationPeriod(start_date=datetime.date(2023, 4, 1), end_date=datetime.date(2024, 3, 31)), current_instant=InstantPeriod(instant=datetime.date(2025, 3, 31)), prior_instant=InstantPeriod(instant=datetime.date(2024, 3, 31)))

======================================================================
  2. 財務諸表組み立て
======================================================================
  [PASS] income_statement(consolidated=True)  (0.14s)
    PL行数: 29
    statement_type: StatementType.INCOME_STATEMENT
    period: DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31))
    consolidated: True
    warnings: ()
    イテレーション: 29件
    pl['売上高']: 64796000000 (concept=NetSales)
    pl['売上原価']: 51575000000 (concept=CostOfSales)
    pl['販売費及び一般管理費']: 12684000000 (concept=SellingGeneralAndAdministrativeExpenses)
    to_dict(): 29件
      先頭: {'label_ja': '売上高', 'label_en': 'Net sales', 'value': Decimal('64796000000'), 'unit': 'JPY', 'concept': 'NetSales'}
  [PASS] income_statement(consolidated=False)  (0.08s)
    個別PL行数: 19
  [PASS] balance_sheet(consolidated=True)  (0.08s)
    BS行数: 38
    bs['流動資産']: 51318000000
    bs['固定資産']: 49896000000
  [PASS] cash_flow_statement(consolidated=True)  (0.44s)
    CF行数: 28
  [PASS] income_statement(period='prior')  (0.11s)
    前期PL行数: 28
  [PASS] strict=True: 29行

======================================================================
  3. search API
======================================================================
    search('利益'): 136件
    search('資産'): 296件
    search('売上'): 79件
    search('負債'): 33件
    search('純資産'): 142件
    search('キャッシュ'): 23件
    search('配当'): 46件

======================================================================
  4. DataFrame変換
======================================================================
  [PASS] Statements.to_dataframe()  (20.68s)
    shape: (1939, 18)
    columns: ['concept', 'namespace_uri', 'local_name', 'label_ja', 'label_en', 'value', 'unit_ref', 'decimals', 'context_id', 'period_type', 'period_start', 'period_end', 'entity_id', 'consolidated', 'dimensions_str', 'is_nil', 'source_line', 'order']
    dtypes:
concept               str
namespace_uri         str
local_name            str
label_ja              str
label_en              str
value              object
unit_ref              str
decimals          float64
context_id            str
period_type           str
period_start       object
period_end         object
entity_id             str
consolidated       object
dimensions_str        str
is_nil               bool
source_line         int64
order               int64
  [PASS] PL.to_dataframe()  (0.00s)
    PL DataFrame shape: (29, 5)
  [PASS] PL.to_dataframe(full=True)  (0.00s)
    PL DataFrame(full) shape: (29, 18)
    columns: ['concept', 'namespace_uri', 'local_name', 'label_ja', 'label_en', 'value', 'unit_ref', 'decimals', 'context_id', 'period_type', 'period_start', 'period_end', 'entity_id', 'consolidated', 'dimensions_str', 'is_nil', 'source_line', 'order']

======================================================================
  5. エクスポート
======================================================================
  [PASS] PL.to_csv()  (0.12s)
    CSV size: 10276 bytes
    CSV行数: 30 (ヘッダ含む)
  [PASS] PL.to_parquet()  (0.69s)
    Parquet size: 14993 bytes
  [PASS] PL.to_excel()  (11.17s)
    Excel size: 8760 bytes
  [PASS] Statements.to_csv()  (0.42s)
    全体CSV size: 4573659 bytes

======================================================================
  6. diff (前期 vs 当期)
======================================================================
  [PASS] diff_periods(prior, current)  (0.00s)
    has_changes: True
    added: 1
    removed: 0
    modified: 28
    unchanged_count: 0
    total_compared: 29
    summary: 追加: 1, 削除: 0, 変更: 28, 変更なし: 0
      変更: ?: 6053000000 → 2994000000 (差額: -3059000000)
      変更: ?: 6053000000 → 2994000000 (差額: -3059000000)
      変更: ?: 55515000000 → 51575000000 (差額: -3940000000)
      変更: ?: 9000000 → -12000000 (差額: -21000000)
      変更: ?: 103000000 → 112000000 (差額: 9000000)

======================================================================
  7. サマリー (build_summary)
======================================================================
  [PASS] build_summary()  (0.00s)
    total_items: 1939
    accounting_standard: Japan GAAP
    period_start: 2024-04-01
    period_end: 2025-03-31
    period_type: FY
    has_consolidated: True
    has_non_consolidated: True
    standard_item_count: 1901
    custom_item_count: 38
    standard_item_ratio: 98.0%
    namespace_counts: {'jpdei': 27, 'jpcrp': 1001, 'jppfs': 873, 'その他': 38}
    segment_count: 103

======================================================================
  8. カスタム科目検出 (detect_custom_items)
======================================================================
  [PASS] detect_custom_items()  (0.00s)
    custom_items: 38
    standard_items: 1901
    custom_ratio: 2.0%
    total_count: 1939
      カスタム: IdleAssetExpensesNOE (label=遊休資産諸費用)
      カスタム: IdleAssetExpensesNOE (label=遊休資産諸費用)
      カスタム: LossOnFireEL (label=火災損失)
      カスタム: LossOnFireEL (label=火災損失)
      カスタム: LossOnFireOpeCF (label=火災損失)

======================================================================
  9. 計算リンク検証 (validate_calculations)
======================================================================
  [FAIL] validate_calculations(PL)  (0.00s)
         TypeError: validate_calculations() missing 1 required positional argument: 'calc_linkbase'
  [FAIL] validate_calculations(BS)  (0.00s)
         TypeError: validate_calculations() missing 1 required positional argument: 'calc_linkbase'

======================================================================
  10. 決算期判定 (detect_fiscal_year)
======================================================================
  [FAIL] detect_fiscal_year()  (0.00s)
         AttributeError: 'Statements' object has no attribute 'current_fiscal_year_start_date'

======================================================================
  11. セグメント (extract_segments / list_dimension_axes)
======================================================================
  [PASS] list_dimension_axes()  (0.00s)
    次元数: 8
      SequentialNumbersAxis: 連番 (standard=True, members=26, items=246)
      OperatingSegmentsAxis: 事業セグメント (standard=True, members=9, items=165)
      DirectorsAndOtherOfficersAxis: 役員 (standard=True, members=13, items=132)
      ComponentsOfEquityAxis: 純資産の内訳項目 (standard=True, members=9, items=80)
      MajorShareholdersAxis: 大株主 (standard=True, members=10, items=40)
  [PASS] extract_segments()  (0.00s)
    セグメント数: 9
      SugarReportableSegments: items=22, depth=0
      GroceryReportableSegments: items=21, depth=0
      FeedReportableSegments: items=22, depth=0
      AgriculturalMaterialsReportableSegments: items=21, depth=0
      RealEstateReportableSegments: items=20, depth=0

======================================================================
  12. 従業員情報
======================================================================
  [PASS] extract_employee_info()  (0.00s)
    従業員数: 747
    平均年齢: 43.5
    平均勤続年数: None
    平均年間給与: 6734184

======================================================================
  13. テキストブロック
======================================================================
  [PASS] extract_text_blocks()  (0.00s)
    テキストブロック数: 193
      PlaceForPublicInspectionCoverPageTextBlock: 316 chars
      BusinessResultsOfGroupTextBlock: 65066 chars
      BusinessResultsOfReportingCompanyTextBlock: 76376 chars
      CompanyHistoryTextBlock: 26600 chars
      DescriptionOfBusinessTextBlock: 6911 chars
  [FAIL] build_section_map()  (0.00s)
         TypeError: build_section_map() missing 1 required positional argument: 'resolver'

======================================================================
  14. 脚注 (footnotes)
======================================================================
  [PASS] parse_footnote_links()  (0.01s)
    脚注数: 89
    全脚注: 8件
      footnote: ※2...
      footnote: ※4...
      footnote: ※1...

======================================================================
  15. HTML表示
======================================================================
  [PASS] to_html(PL)  (0.07s)
    HTML length: 3253 chars
    <table>: True
    <tr>: 30

======================================================================
  16. DocType 全種
======================================================================
    010: 有価証券通知書 (original=None, correction=False)
    020: 変更通知書（有価証券通知書） (original=None, correction=False)
    030: 有価証券届出書 (original=None, correction=False)
    040: 訂正有価証券届出書 (original=DocType.SECURITIES_REGISTRATION, correction=True)
    050: 届出の取下げ願い (original=None, correction=False)
    060: 発行登録通知書 (original=None, correction=False)
    070: 変更通知書（発行登録通知書） (original=None, correction=False)
    080: 発行登録書 (original=None, correction=False)
    090: 訂正発行登録書 (original=DocType.SHELF_REGISTRATION_STATEMENT, correction=True)
    100: 発行登録追補書類 (original=None, correction=False)
    110: 発行登録取下届出書 (original=None, correction=False)
    120: 有価証券報告書 (original=None, correction=False)
    130: 訂正有価証券報告書 (original=DocType.ANNUAL_SECURITIES_REPORT, correction=True)
    135: 確認書 (original=None, correction=False)
    136: 訂正確認書 (original=DocType.CONFIRMATION_LETTER, correction=True)
    140: 四半期報告書 (original=None, correction=False)
    150: 訂正四半期報告書 (original=DocType.QUARTERLY_REPORT, correction=True)
    160: 半期報告書 (original=None, correction=False)
    170: 訂正半期報告書 (original=DocType.SEMIANNUAL_REPORT, correction=True)
    180: 臨時報告書 (original=None, correction=False)
    190: 訂正臨時報告書 (original=DocType.EXTRAORDINARY_REPORT, correction=True)
    200: 親会社等状況報告書 (original=None, correction=False)
    210: 訂正親会社等状況報告書 (original=DocType.PARENT_COMPANY_STATUS_REPORT, correction=True)
    220: 自己株券買付状況報告書 (original=None, correction=False)
    230: 訂正自己株券買付状況報告書 (original=DocType.SHARE_BUYBACK_STATUS_REPORT, correction=True)
    235: 内部統制報告書 (original=None, correction=False)
    236: 訂正内部統制報告書 (original=DocType.INTERNAL_CONTROL_REPORT, correction=True)
    240: 公開買付届出書 (original=None, correction=False)
    250: 訂正公開買付届出書 (original=DocType.TENDER_OFFER_REGISTRATION, correction=True)
    260: 公開買付撤回届出書 (original=None, correction=False)
    270: 公開買付報告書 (original=None, correction=False)
    280: 訂正公開買付報告書 (original=DocType.TENDER_OFFER_REPORT, correction=True)
    290: 意見表明報告書 (original=None, correction=False)
    300: 訂正意見表明報告書 (original=DocType.OPINION_REPORT, correction=True)
    310: 対質問回答報告書 (original=None, correction=False)
    320: 訂正対質問回答報告書 (original=DocType.TENDER_OFFER_ANSWER_REPORT, correction=True)
    330: 別途買付け禁止の特例を受けるための申出書 (original=None, correction=False)
    340: 訂正別途買付け禁止の特例を受けるための申出書 (original=DocType.SEPARATE_PURCHASE_PROHIBITION_EXCEPTION, correction=True)
    350: 大量保有報告書 (original=None, correction=False)
    360: 訂正大量保有報告書 (original=DocType.LARGE_SHAREHOLDING_REPORT, correction=True)
    370: 基準日の届出書 (original=None, correction=False)
    380: 変更の届出書 (original=None, correction=False)

======================================================================
  17. LineItem 詳細チェック
======================================================================
    concept: {http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor}NetSales
    namespace_uri: http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor
    local_name: NetSales
    label_ja: LabelInfo(text='売上高', role='http://www.xbrl.org/2003/role/label', lang='ja', source=<LabelSource.STANDARD: 'standard'>)
    label_en: LabelInfo(text='Net sales', role='http://www.xbrl.org/2003/role/label', lang='en', source=<LabelSource.STANDARD: 'standard'>)
    value: 64796000000 (type=Decimal)
    unit_ref: JPY
    decimals: -6
    context_id: CurrentYearDuration
    period: DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31))
    entity_id: E00355-000
    dimensions: ()
    is_nil: False
    source_line: 3975
    order: 610
    数値アイテム: 29 / 29
    文字列アイテム: 0
    nilアイテム: 0
    value=None(non-nil): 0

======================================================================
  テスト結果サマリー
======================================================================
  対象企業: 日本甜菜製糖株式会社
  PASS: 22
  FAIL: 4
  WARN: 0
  総実行時間: 54.0s
```

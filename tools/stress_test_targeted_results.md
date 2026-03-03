# ストレステスト: ターゲットテスト (Wave2)

実行日時: 2026-03-03

```

======================================================================
  1. Company API 詳細チェック
======================================================================
  Company.search('トヨタ'): 5件
    vars: {'edinet_code': 'E00540', 'name_ja': 'トヨタ紡織株式会社', 'sec_code': '31160'}
    dir (public): ['all_listed', 'by_industry', 'construct', 'copy', 'dict', 'edinet_code', 'from_edinet_code', 'from_filing', 'from_orm', 'from_sec_code', 'get_filings', 'json', 'latest', 'model_computed_fields', 'model_config', 'model_construct', 'model_copy', 'model_dump', 'model_dump_json', 'model_extra', 'model_fields', 'model_fields_set', 'model_json_schema', 'model_parametrized_name', 'model_post_init', 'model_rebuild', 'model_validate', 'model_validate_json', 'model_validate_strings', 'name_ja', 'parse_file', 'parse_obj', 'parse_raw', 'schema', 'schema_json', 'search', 'sec_code', 'ticker', 'update_forward_refs', 'validate']
    edinet_code: str = 'E00540'
    model_computed_fields: dict = {'ticker': ComputedFieldInfo(wrapped_property=<property object at 0x7d0c485438d0
    model_config: dict = {'frozen': True}
    model_extra: NoneType = None
    model_fields: dict = {'edinet_code': FieldInfo(annotation=str, required=True), 'name_ja': FieldInfo(a
    model_fields_set: set = {'name_ja', 'edinet_code', 'sec_code'}
    name_ja: str = 'トヨタ紡織株式会社'
    sec_code: str = '31160'
    ticker: str = '3116'
  from_sec_code('7203'): {'edinet_code': 'E02144', 'name_ja': 'トヨタ自動車株式会社', 'sec_code': '72030'}
  from_sec_code('72030'): {'edinet_code': 'E02144', 'name_ja': 'トヨタ自動車株式会社', 'sec_code': '72030'}
  from_edinet_code('E02144'): {'edinet_code': 'E02144', 'name_ja': 'トヨタ自動車株式会社', 'sec_code': '72030'}

======================================================================
  2. US-GAAP企業テスト
======================================================================
  Company.search('野村ホールディングス'): {'edinet_code': 'E03752', 'name_ja': '野村ホールディングス株式会社', 'sec_code': '86040'}
    最新有報: S100VXTD (野村ホールディングス株式会社)
  [PASS] US-GAAP パース (野村ホールディングス)  (7.04s)
      standard: DetectedStandard(standard=<AccountingStandard.US_GAAP: 'US GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.BLOCK_ONLY: 'block_only'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      ★★★ US-GAAP確認! ★★★

  --- US-GAAP: 野村ホールディングス ---
    standard: DetectedStandard(standard=<AccountingStandard.US_GAAP: 'US GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.BLOCK_ONLY: 'block_only'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    items: 1604
    consolidated: True
    non_consolidated: True
    PL: 3行, type=StatementType.INCOME_STATEMENT, period=DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31))
      RevenuesUSGAAPSummaryOfBusinessResults               4736743000000  売上高
      ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults         471964000000  税引前利益又は税引前損失（△）
      NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults         340736000000  当社株主に帰属する純利益又は純損失（△）
    BS: 2行
    CF: 3行

======================================================================
  3. IFRS大企業の深堀り
======================================================================
  [PASS] IFRS パース (SBG)  (5.58s)

  --- IFRS: ソフトバンクG ---
    standard: DetectedStandard(standard=<AccountingStandard.IFRS: 'IFRS'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    items: 2246
    consolidated: True
    non_consolidated: True
    PL: 10行, type=StatementType.INCOME_STATEMENT, period=DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31))
      ProfitLossAttributableToOwnersOfParentIFRS           1153332000000  親会社の所有者
      BasicEarningsLossPerShareIFRS                               780.82  基本的１株当たり当期利益（△損失）
      CostOfSalesIFRS                                      3489549000000  売上原価
      ProfitLossAttributableToNonControllingInterestsIFRS         449776000000  非支配持分
      DilutedEarningsLossPerShareIFRS                             779.40  希薄化後１株当たり当期利益（△損失）
      GrossProfitIFRS                                      3754203000000  売上総利益
      SellingGeneralAndAdministrativeExpensesIFRS          3024409000000  販売費及び一般管理費
      ProfitLossBeforeTaxIFRS                              1704721000000  税引前利益（△損失）
      IncomeTaxExpenseIFRS                                  101613000000  法人所得税費用
      ProfitLossIFRS                                       1603108000000  当期利益（△損失）
    BS: 38行
      Equity: 13953026000000
      Assets: 45013756000000
      Liabilities: 31060730000000
    CF: 20行

    --- IFRS PL 詳細分析 ---
    行数が少ない理由を調査:
      detail_level: DetailLevel.DETAILED
      search('Revenue'): 14件
      search('Profit'): 125件
      search('EBITDA'): 0件
      search('売上収益'): 5件
      search('営業利益'): 2件
      search('税引前'): 25件
      search('親会社'): 37件
      search('包括利益'): 77件

    --- サマリー ---
    standard_item_ratio: 87.4%
    namespace_counts: {'jpdei': 27, 'jpcrp': 849, 'その他': 282, 'jpigp': 658, 'jppfs': 430}
    segment_count: 99

======================================================================
  4. 銀行業セクター
======================================================================
  みずほ: {'edinet_code': 'E03628', 'name_ja': 'みずほ信託銀行株式会社', 'sec_code': None}
  [PASS] 銀行業パース (みずほ)  (3.55s)

  --- 銀行業: みずほ ---
    standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    items: 89
    consolidated: True
    non_consolidated: True
    PL: 4行, type=StatementType.INCOME_STATEMENT, period=DurationPeriod(start_date=datetime.date(2024, 9, 20), end_date=datetime.date(2025, 3, 19))
      OperatingIncome                                         9336000000  営業利益又は営業損失（△）
      OrdinaryIncome                                          9336000000  経常利益又は経常損失（△）
      IncomeBeforeIncomeTaxes                                 9336000000  税引前当期純利益又は税引前当期純損失（△）
      ProfitLoss                                              9336000000  当期純利益又は当期純損失（△）
    BS: 8行
      NetAssets: 1207497000000
      Assets: 1219888000000
      Liabilities: 12391000000
    CF: 1行

======================================================================
  5. 建設業セクター
======================================================================
  [PASS] 建設業パース (鹿島建設)  (8.96s)

  --- 建設業: 鹿島建設 ---
    standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    items: 2471
    consolidated: True
    non_consolidated: True
    PL: 34行, type=StatementType.INCOME_STATEMENT, period=DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31))
      NetSales                                             2911816000000  売上高
      InterestIncomeNOI                                      16858000000  受取利息
      InterestExpensesNOE                                    22016000000  支払利息
      GainOnSalesOfNoncurrentAssetsEI                         5826000000  固定資産売却益
      LossOnSalesOfNoncurrentAssetsEL                            4000000  固定資産売却損
      ProfitLossAttributableToNonControllingInterests            637000000  非支配株主に帰属する当期純利益又は非支配株主に帰属する当期純損失（△）
      ValuationDifferenceOnAvailableForSaleSecuritiesNetOfTaxOCI         -39199000000  その他有価証券評価差額金
      ComprehensiveIncomeAttributableToOwnersOfTheParent         124661000000  親会社株主に係る包括利益
      CostOfSales                                          2588619000000  売上原価
      DividendsIncomeNOI                                      6986000000  受取配当金
      ImpairmentLossEL                                         621000000  減損損失
      ProfitLossAttributableToOwnersOfParent                125817000000  親会社株主に帰属する当期純利益又は親会社株主に帰属する当期純損失（△）
      DeferredGainsOrLossesOnHedgesNetOfTaxOCI                -468000000  繰延ヘッジ損益
      ComprehensiveIncomeAttributableToNonControllingInterests           2125000000  非支配株主に係る包括利益
      GrossProfit                                           323197000000  売上総利益又は売上総損失（△）
      ExtraordinaryIncome                                    19843000000  特別利益
      ForeignCurrencyTranslationAdjustmentNetOfTaxOCI          38055000000  為替換算調整勘定
      EquityInEarningsOfAffiliatesNOI                         2815000000  持分法による投資利益
      ExtraordinaryLoss                                       4406000000  特別損失
      RemeasurementsOfDefinedBenefitPlansNetOfTaxOCI           2169000000  退職給付に係る調整額
      SellingGeneralAndAdministrativeExpenses               171314000000  販売費及び一般管理費
      NonOperatingIncome                                     37397000000  営業外収益
      NonOperatingExpenses                                   28616000000  営業外費用
      ShareOfOtherComprehensiveIncomeOfAssociatesAccountedForUsingEquityMethodOCI            378000000  持分法適用会社に対する持分相当額
      OperatingIncome                                       151882000000  営業利益又は営業損失（△）
      OtherComprehensiveIncome                                 332000000  その他の包括利益
      OrdinaryIncome                                        160663000000  経常利益又は経常損失（△）
      IncomeBeforeIncomeTaxes                               176100000000  税引前当期純利益又は税引前当期純損失（△）
      IncomeTaxesCurrent                                     53656000000  法人税、住民税及び事業税
      IncomeTaxesDeferred                                    -4010000000  法人税等調整額
      IncomeTaxes                                            49645000000  法人税等
      ProfitLoss                                            126454000000  当期純利益又は当期純損失（△）
      ComprehensiveIncome                                   126787000000  包括利益
      AmortizationOfGoodwillSGA                                845000000  のれん償却額
    BS: 45行
      NetAssets: 1277988000000
      Assets: 3454592000000
      Liabilities: 2176603000000
    CF: 34行
      search('完成工事'): 23件
        NotesReceivableAccountsReceivableFromCompletedConstructionContractsAndOtherCNS: 940304000000 (受取手形・完成工事未収入金等)
        NotesReceivableAccountsReceivableFromCompletedConstructionContractsAndOtherCNS: 1061540000000 (受取手形・完成工事未収入金等)
        ProvisionForWarrantiesForCompletedConstruction: 11763000000 (完成工事補償引当金)
      search('受注'): 0件
      search('工事'): 49件
        NotesReceivableAccountsReceivableFromCompletedConstructionContractsAndOtherCNS: 940304000000 (受取手形・完成工事未収入金等)
        NotesReceivableAccountsReceivableFromCompletedConstructionContractsAndOtherCNS: 1061540000000 (受取手形・完成工事未収入金等)
        CostsOnUncompletedConstructionContractsCNS: 8356000000 (未成工事支出金)

======================================================================
  6. 保険業セクター
======================================================================
  東京海上: {'edinet_code': 'E03823', 'name_ja': '東京海上日動火災保険株式会社', 'sec_code': None}
  [PASS] 保険業パース (東京海上)  (9.71s)

  --- 保険業: 東京海上 ---
    standard: DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
    items: 1515
    consolidated: True
    non_consolidated: True
    PL: 45行, type=StatementType.INCOME_STATEMENT, period=DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31))
      OperatingIncomeINS                                   7917258000000  経常収益
      OtherOtherOperatingIncomeOIINS                        107830000000  その他の経常収益
      ProvisionOfOutstandingClaimsOEINS                     188980000000  支払備金繰入額
      InterestExpensesOEINS                                  27086000000  支払利息
      OtherOtherOperatingExpensesOEINS                        4597000000  その他の経常費用
      ProvisionOfReserveForPriceFluctuationELINS              6296000000  価格変動準備金繰入額
      ValuationDifferenceOnAvailableForSaleSecuritiesNetOfTaxOCI       -1066102000000  その他有価証券評価差額金
      ComprehensiveIncomeAttributableToOwnersOfTheParent         381401000000  親会社株主に係る包括利益
      InvestmentIncomeOIINS                                1857588000000  資産運用収益
      GainFromMoneyHeldInTrustOIINS                                    0  金銭の信託運用益
      OperatingExpensesINS                                 6514424000000  経常費用
      ProvisionOfPolicyReserveAndOtherOEINS                 339638000000  責任準備金等繰入額
      ImpairmentLossEL                                        1185000000  減損損失
      DeferredGainsOrLossesOnHedgesNetOfTaxOCI                -491000000  繰延ヘッジ損益
      ComprehensiveIncomeAttributableToNonControllingInterests          15175000000  非支配株主に係る包括利益
      GainOnTradingSecuritiesOIINS                          144228000000  売買目的有価証券運用益
      OtherOperatingIncomeOIINS                             110160000000  その他経常収益
      InvestmentExpensesOEINS                               288242000000  資産運用費用
      OrdinaryIncome                                       1402833000000  経常利益又は経常損失（△）
      ProvisionOfReservesUnderTheSpecialLawsEL                6296000000  特別法上の準備金繰入額
      ForeignCurrencyTranslationAdjustmentNetOfTaxOCI         439542000000  為替換算調整勘定
      GainOnSalesOfSecuritiesOIINS                          835118000000  有価証券売却益
      LossOnSalesOfSecuritiesOEINS                           63240000000  有価証券売却損
      ExtraordinaryIncome                                     4306000000  特別利益
      RemeasurementsOfDefinedBenefitPlansNetOfTaxOCI           8462000000  退職給付に係る調整額
      GainOnRedemptionOfSecuritiesOIINS                       2014000000  有価証券償還益
      LossOnValuationOfSecuritiesOEINS                        1077000000  有価証券評価損
      OtherOperatingExpensesOEINS                            33724000000  その他経常費用
      ExtraordinaryLoss                                      14353000000  特別損失
      OtherEL                                                  602000000  その他
      ShareOfOtherComprehensiveIncomeOfAssociatesAccountedForUsingEquityMethodOCI            677000000  持分法適用会社に対する持分相当額
      LossOnRedemptionOfSecuritiesOEINS                       2882000000  有価証券償還損
      OtherComprehensiveIncome                             -616846000000  その他の包括利益
      NetDerivativeFinancialInstrumentsLossOEINS             62855000000  金融派生商品費用
      IncomeBeforeIncomeTaxes                              1392786000000  税引前当期純利益又は税引前当期純損失（△）
      IncomeTaxesCurrentConsolidatedINS                     397295000000  法人税及び住民税等
      OtherInvestmentIncomeOIINS                             18538000000  その他運用収益
      ProvisionOfAllowanceForDoubtfulAccountsOEINS            1478000000  貸倒引当金繰入額
      IncomeTaxesDeferred                                   -17933000000  法人税等調整額
      IncomeTaxes                                           379362000000  法人税等
      ProfitLoss                                           1013423000000  当期純利益又は当期純損失（△）
      OtherInvestmentExpensesOEINS                          158186000000  その他運用費用
      ProfitLossAttributableToNonControllingInterests            -96000000  非支配株主に帰属する当期純利益又は非支配株主に帰属する当期純損失（△）
      ProfitLossAttributableToOwnersOfParent               1013520000000  親会社株主に帰属する当期純利益又は親会社株主に帰属する当期純損失（△）
      ComprehensiveIncome                                   396577000000  包括利益
    BS: 44行
      NetAssets: 4794351000000
      Assets: 22820558000000
      Liabilities: 18026207000000
    CF: 42行
      search('保険'): 81件
      search('収入保険料'): 15件
      search('保険引受'): 16件

======================================================================
  7. diff出力の品質チェック
======================================================================
  diff結果: added=1, removed=0, modified=28, unchanged=0
  DiffItem attrs: ['__annotations__', '__class__', '__dataclass_fields__', '__dataclass_params__', '__delattr__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__getstate__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__match_args__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__setstate__', '__sizeof__', '__slots__', '__str__', '__subclasshook__', 'concept', 'difference', 'label_en', 'label_ja', 'new_value', 'old_value']
    concept: str = 'ComprehensiveIncome'
    difference: Decimal = Decimal('-3059000000')
    label_en: LabelInfo = LabelInfo(text='Comprehensive income', role='http://www.xbrl.org/2003/role/label', lang='en', source
    label_ja: LabelInfo = LabelInfo(text='包括利益', role='http://www.xbrl.org/2003/role/label', lang='ja', source=<LabelSource.ST
    new_value: Decimal = Decimal('2994000000')
    old_value: Decimal = Decimal('6053000000')
  追加: LineItem(concept='{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor}GainOnSalesOfNoncurrentAssetsEI', namespace_uri='http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor', local_name='GainOnSalesOfNoncurrentAssetsEI', label_ja=LabelInfo(text='固定資産売却益', role='http://www.xbrl.org/2003/role/label', lang='ja', source=<LabelSource.STANDARD: 'standard'>), label_en=LabelInfo(text='Gain on sale of non-current assets', role='http://www.xbrl.org/2003/role/label', lang='en', source=<LabelSource.STANDARD: 'standard'>), value=Decimal('7707000000'), unit_ref='JPY', decimals=-6, context_id='CurrentYearDuration', period=DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31)), entity_id='E00355-000', dimensions=(), is_nil=False, source_line=4011, order=646)

======================================================================
  8. to_dataframe() パフォーマンス
======================================================================
  Statements.to_dataframe(): (1939, 18) in 21.05s
    items: 1939
    items/sec: 92
  PL.to_dataframe(full): (29, 18) in 0.0050s

  複数企業でのto_dataframe()時間:
    日本甜菜製糖株式会社: 1939items → (1939, 18) in 0.04s (54086 items/s)
    ＯＵＧホールディングス株式会社: 1752items → (1752, 18) in 0.02s (81303 items/s)
    株式会社ｉｓｐａｃｅ: 1277items → (1277, 18) in 0.02s (68112 items/s)
    野村アセットマネジメント株式会社: 166items → (166, 18) in 0.01s (20757 items/s)
    ＳＥＭＩＴＥＣ株式会社: 1339items → (1339, 18) in 0.01s (105339 items/s)

======================================================================
  9. パースエラーケースの特定
======================================================================
  6/26の全XBRL Filing: 1354件

  パースエラー: 2件
  野村アセットマネジメント株式会社 (S100VP7L): EdinetParseError: EDINET ZIP の解析に失敗しました (doc_id=S100VP7L)。
  野村アセットマネジメント株式会社 (S100VP7I): EdinetParseError: EDINET ZIP の解析に失敗しました (doc_id=S100VP7I)。

  警告: 24件 (上位10件)
  株式会社ジャパンディスプレイ (S100W6JR): Filing S100W6JR: jppfs_cor 名前空間の Fact がありません。IFRS / US-GAAP の Filing は v0.1.0 では未対応です。
  株式会社大真空 (S100W5YH): labelArc に use='prohibited' または priority 属性が検出されました。v0.1.0 では arc override の完全処理は行いません

======================================================================
  10. 12月決算企業テスト（3月提出）
======================================================================
  2025-03-27: 153件
    楽天投信投資顧問株式会社: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 6, 28), end_date=datetime.date(2024, 12, 27))
      ★ 12月決算確認
    野村アセットマネジメント株式会社: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 1, 10), end_date=datetime.date(2025, 1, 6))
    株式会社東計電算: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31))
      ★ 12月決算確認
  2025-03-28: 208件
    野村アセットマネジメント株式会社: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 7, 9), end_date=datetime.date(2025, 1, 6))
    株式会社タダノ: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31))
      ★ 12月決算確認
    大和アセットマネジメント株式会社: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.NAMESPACE: 'namespace'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=None, period_type=None, namespace_modules=frozenset({'jpsps', 'jppfs'}))
      period: None
  2025-03-31: 108件
    株式会社サイプレスクラブ: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31))
      ★ 12月決算確認
    松山観光ゴルフ株式会社: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=False, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31))
      ★ 12月決算確認
    株式会社セルシス: standard=DetectedStandard(standard=<AccountingStandard.JAPAN_GAAP: 'Japan GAAP'>, method=<DetectionMethod.DEI: 'dei'>, detail_level=<DetailLevel.DETAILED: 'detailed'>, has_consolidated=True, period_type=<PeriodType.FY: 'FY'>, namespace_modules=frozenset())
      period: DurationPeriod(start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31))
      ★ 12月決算確認

======================================================================
  テスト結果サマリー
======================================================================
  PASS: 5
  FAIL: 0
  WARN: 0
  総実行時間: 427.3s
```

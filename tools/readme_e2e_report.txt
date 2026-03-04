README.md E2E Test Report
Date: 2026-03-04 20:52:55.232648
PASS: 69/70, FAIL: 0/70, WARN: 1/70

[PASS] configure(): 
[PASS] documents(): 459 filings found
[PASS] 三表取得: PL=29科目, BS=38科目, CF=28科目
[PASS] search(売上): 売上高=54792000000
[PASS] extract_values(): 営業利益=910000000, 総資産=97392000000
[PASS] Company.search(): トヨタ自動車株式会社, ticker=7203
[PASS] Company.from_sec_code(): ソニーグループ株式会社
[PASS] Company.from_edinet_code(): トヨタ自動車株式会社
[WARN] Company.latest(): 最新有報が見つからなかった（期間外の可能性）
[PASS] DocType properties: 
[PASS] DocType.original: 訂正有価証券報告書 → 有価証券報告書
[PASS] PL item access: 売上高
[PASS] stmts.search(): 20 hits: 営業利益又は営業損失（△）
[PASS] stmts.get(売上高): 54792000000
[PASS] income_statement(prior): 28 科目
[PASS] income_statement(solo): 19 科目
[PASS] pl[売上高]: value=64796000000
[PASS] pl[Net sales]: 
[PASS] pl[NetSales]: 
[PASS] pl.get(not_found): None returned correctly
[PASS] detected_standard: J-GAAP
[PASS] extract_values(default): 2 found
[PASS] extract_values(current/consol): 
[PASS] extract_values(prior): 
[PASS] extract_values(solo): 
[PASS] ExtractedValue fields: 
[PASS] mapper filter: 1 items via summary_mapper
[PASS] extract_values(summary only): 
[PASS] extracted_to_dict(): {'revenue': Decimal('64796000000'), 'operating_income': Decimal('535000000'), 'net_income': Decimal('2703000000'), 'total_assets': Decimal('101215000000')}
[PASS] dict_mapper(): 72 found
[PASS] to_dataframe(): shape=(29, 5)
[PASS] to_dataframe(full): shape=(29, 18), cols=['concept', 'namespace_uri', 'local_name', 'label_ja', 'label_en']...
[PASS] to_csv(): size=10276
[PASS] to_parquet(): size=14960
[PASS] to_excel(): size=8730
[PASS] stmts.to_dataframe(): shape=(1939, 18)
[PASS] extract_text_blocks(): 193 blocks
[PASS] build_section_map(): 125 sections: ('縦覧に供する場所', '連結経営指標等', '提出会社の経営指標等', '沿革', '事業の内容')...
[PASS] clean_html(事業等のリスク): 2352 chars: ３ 【事業等のリスク】有価証券報告書に記載した事業の状況、経理の状況等に関する事項のうち、経営者が連結会社の財政状態、経営成績及びキャッシュ・フローの状況に重要...
[PASS] TaxonomyResolver.resolve(): 売上高, source=LabelSource.STANDARD
[PASS] parse_presentation_linkbase(): 51 roles
[PASS] parse_calculation_linkbase(): 8 roles
[PASS] parse_definition_linkbase(): 46 roles
[PASS] derive_concept_sets(): 74 concepts in PL/cai
[PASS] validate_calculations(): valid=False, checked=14, issues=7
[PASS] build_revision_chain(): corrected=False, count=1
[PASS] chain.at_time(): snapshot=S100W4MW
[PASS] diff_periods(): 追加: 1, 削除: 0, 変更: 28, 変更なし: 0
[PASS] list_dimension_axes(): 8 axes
[PASS] extract_segments(): 26 segments
[PASS] detect_custom_items(): standard=1901, custom=38 (2.0%)
[PASS] find_custom_concepts(): 7 concepts
[PASS] detect_fiscal_year(): months=12, irregular=False
[PASS] extract_employee_info(): count=747, salary=6734184
[PASS] build_summary(): standard=Japan GAAP, items=1939, ratio=0.98
[PASS] adocuments(): 1818 filings
[PASS] axbrl(): PL=29 items
[PASS] aclose(): 
[PASS] classify_periods(): current=DurationPeriod(start_date=datetime.date(2024, 4, 1), end_date=datetime.date(2025, 3, 31))
[PASS] cache_info(): entries=2, bytes=1210647
[PASS] clear_cache(): skipped (non-destructive)
[PASS] parse_xbrl_facts(): 1939 facts
[PASS] extract_dei(): 日本甜菜製糖株式会社
[PASS] structure_contexts(): 290 contexts
[PASS] structure_units(): 4 units
[PASS] filter chain: 11 consolidated contexts
[PASS] Exception classes: all exist and inherit correctly
[PASS] fetch_pdf(): 549350 bytes
[PASS] rate_limit=1.0: 
[PASS] rate_limit=0: 

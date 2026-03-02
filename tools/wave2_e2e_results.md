# Wave 2 E2E テスト結果サマリー

実施日: 2026-03-01

## テスト一覧と結果

### #1 wave2_e2e_detect.py: 会計基準検出 (8/8 PASSED)
| Test | 企業 | 結果 | 備考 |
|------|------|------|------|
| DETECT-1 | J-GAAP DEI (ソフトバンクG) | ✓ | JAPAN_GAAP, DEI, DETAILED |
| DETECT-2 | J-GAAP namespace (ソフトバンクG) | ✓ | jppfs/jpcrp/jpdei 検出 |
| DETECT-3 | J-GAAP canonical_key | ✓ | 39概念マッピング |
| DETECT-4 | IFRS DEI (日立) | ✓ | IFRS, DEI, DETAILED |
| DETECT-5 | IFRS namespace (日立) | ✓ | jpigp 検出 |
| DETECT-6 | IFRS canonical_key | ✓ | 33概念マッピング |
| DETECT-7 | US-GAAP DEI (野村HD) | ✓ | US_GAAP, DEI, BLOCK_ONLY |
| DETECT-8 | US-GAAP extract_summary | ✓ | 80 items, 6 blocks |

### #2 wave2_e2e_edge.py: エッジケース (8/8 PASSED)
| Test | 内容 | 結果 | 備考 |
|------|------|------|------|
| EDGE-A1 | 大量保有報告書 → UNKNOWN | ✓ | DEI nil, jplvh のみ |
| EDGE-B1 | IFRS→jgaap cross-standard safety | ✓ | 全て None |
| EDGE-B2 | J-GAAP→ifrs cross-standard safety | ✓ | 全て None |
| EDGE-C1 | J-GAAP 銀行業検出 | ✓ | 検出OK, jppfs hit少ない |
| EDGE-D1 | 双方向マッピング整合性 | ✓ | 0 mismatch |
| EDGE-E1 | J-GAAP canonical key 一意性 | ✓ | 52 unique keys |
| EDGE-E2 | IFRS canonical key 一意性 | ✓ | 35 unique keys |
| EDGE-F1 | 共通 canonical key | ✓ | 29 common, 主要4指標共通 |

### #3 wave2_e2e_concept_sets.py: ConceptSet自動導出 (5/5 PASSED)
| Test | 内容 | 結果 | 備考 |
|------|------|------|------|
| CS-1 | classify_role_uri | ✓ | 連結/個別正常判定 |
| CS-2 | derive_concept_sets | ✓ | 23業種, 26.7s→0.048s(cached) |
| CS-3 | cns BS/PL/CF 存在 | ✓ | BS=68, PL=65, CF=29 (non-abstract) |
| CS-4 | get_concept_set | ✓ | legacy format 変換OK |
| CS-5 | Fact ↔ ConceptSet 照合 | ✓ | BS=37, PL=34, CF=14 overlap |

### #4 wave2_e2e_usgaap_deep.py: US-GAAP 詳細 (5/5 PASSED)
| Test | 内容 | 結果 | 備考 |
|------|------|------|------|
| USGAAP-1 | 全6社検出+summary | ✓ | 全社 80-85 items |
| USGAAP-2 | to_dict 変換 | ✓ | 80 entries |
| USGAAP-3 | get_jgaap_mapping | ✓ | 19 entries |
| USGAAP-4 | is_usgaap_element | ✓ | 正常判定 |
| USGAAP-5 | text_blocks HTML | ✓ | 6/6 with content |

### #5 wave2_e2e_ifrs_deep.py: IFRS 詳細 (4/5 PASSED)
| Test | 内容 | 結果 | 備考 |
|------|------|------|------|
| IFRS-1 | 日立カバレッジ | ✓ | 33/189 (17.5%) |
| IFRS-2 | IFRS特有概念 | ✓ | 5/5 found |
| IFRS-3 | cross-mapping | ✓ | 28 concepts mapped |
| IFRS-4 | NTT検出 | ✗ | EDINETコード誤り (テスト側) |
| IFRS-5 | 武田薬品検出 | ✓ | IFRS, 33 mapped |

## 全体結果: 30/31 PASSED (1件はテストデータ誤り)

## 発見事項

### 正常動作を確認
1. **会計基準検出**: J-GAAP/IFRS/US-GAAP の DEI 検出が3基準とも正常
2. **Namespace fallback**: J-GAAP(jppfs), IFRS(jpigp) で正常検出
3. **Cross-standard safety**: 他基準のコンセプトが誤マッピングされない
4. **ConceptSet 自動導出**: 23業種から BS/PL/CF/SS/CI を自動分類
5. **US-GAAP summary**: 全6社で80-85件の summary + 6 text blocks 抽出
6. **双方向マッピング**: IFRS↔J-GAAP で 0 mismatch

### 注意事項 (バグではないが認識すべき)
1. **IFRS canonical_key カバレッジ**: 17.5% (主要項目のみ設計通り)
   - 未マッピング: 詳細BS項目, SS変動項目, TextBlock, CI, 注記関連
   - Wave 3 以降で必要に応じて拡張
2. **ConceptSet SS**: StatementType enum に SS がないため `to_statement_type()=None`
   - Wave 3 で StatementType 拡張時に対応予定
3. **ConceptSet Fact 照合**: 180 unique 中 BS=37, PL=34, CF=14 overlap
   - 残り = SS/CI/注記/提出者独自概念 → 正常
4. **銀行業の jppfs canonical_key**: 一般事業会社ほどヒットしない (3件)
   - 銀行は jppfs の使い方が異なる → 業種別マッピングが今後必要
5. **大量保有報告書**: standard=None, method=UNKNOWN → 仕様通り
6. **US-GAAP get_jgaap_mapping**: EPS/BPS/PER/ROE は None (ratio概念のため)

### テストデータの誤り (要修正)
- NTT の EDINET コード: E00734 は「平賀」。NTT は別のコード。

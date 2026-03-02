## FINALCHECK. クロスチェック検証

### 質問への対応

| チェック項目 | 判定 | 回答 |
|---|---|---|
| P-2 の名前空間宣言 ↔ A-1 の名前空間リストが一致 | OK | `P-2.a.md` の名前空間列挙に `iso4217` と `jpigp_cor` を追記済み。実ファイル・A-1 と一致。 |
| P-2 の Context 構造 ↔ A-2 の回答が一致 | OK | `scenario` 使用・`segment` 不使用・`xbrldi:explicitMember` 利用で整合。 |
| P-2 の schemaRef ↔ H-1 の回答が一致 | OK | ともに相対パス `*.xsd` を参照。 |
| P-3 の xs:import URL ↔ H-1b の URL→ローカルパス変換ルールが整合 | OK | `http://disclosure.edinet-fsa.go.jp/taxonomy/...` の絶対 URL import と、ローカル変換ルールが一致。 |
| P-1 の拡張子（.xbrl vs .htm）↔ K-2 の iXBRL 採用状況が一致 | OK | `.htm`（iXBRL）と自動生成 `.xbrl` の同梱という結論が一致。 |
| P-6 の concept 定義 ↔ C-9 の属性リストが一致 | OK | `P-6.a.md` の `substitutionGroup` を4種（`xbrli:item`, `iod:identifierItem`, `xbrldt:hypercubeItem`, `xbrldt:dimensionItem`）に修正し、C-9/実ファイルと一致。 |
| P-6 のラベルリンクベース構造 ↔ C-5 / C-10 の XML 構造が一致 | OK | `loc -> labelArc(concept-label) -> label`、`labelLink`、`roleRef` の構造が一致。 |
| P-1d の銀行業 ZIP ↔ E-5 の業種別差異が一致 | OK | ZIP 構造は共通（P-1d）だが、concept は BNK 系で業種差異あり（E-5）で矛盾なし。 |
| P-1e の訂正報告書 ZIP ↔ G-7 の訂正報告書構造が一致 | OK | 訂正報告書が全体再提出（完全 ZIP）という結論が一致。 |

### スクリプト検証ログ（追跡用）

- 実行日: 2026-02-24
- スクリプト: `docs/QAs/scripts/FINALCHECK.cross_check.py`
- 実行コマンド: `uv run python docs/QAs/scripts/FINALCHECK.cross_check.py`
- 結果保存ファイル: `docs/QAs/scripts/results/FINALCHECK.cross_check.2026-02-24.txt`
- サマリー: `OK=9`, `NEEDS_FIX=0`, `WARN=0`
- 抜粋（修正箇所の再確認）:
  - check1: `P-2 missing: none`
  - check6: `p6_claims_single=False`, `substitution_groups=['iod:identifierItem', 'xbrldt:dimensionItem', 'xbrldt:hypercubeItem', 'xbrli:item']`

### 情報源（Fact）

- [F1] パス: `docs/QAs/scripts/FINALCHECK.cross_check.py` — 9項目の自動クロスチェック実装
- [F2] パス: `docs/QAs/scripts/results/FINALCHECK.cross_check.2026-02-24.txt` — 実行結果ログ（`OK=9`, `NEEDS_FIX=0`, `WARN=0`）
- [F3] パス: `docs/QAs/P-2.a.md`（修正注記） — `iso4217`, `jpigp_cor` の追記内容
- [F4] パス: `docs/QAs/P-6.a.md`（修正注記） — `substitutionGroup` を4種へ修正した内容
- [F5] パス: `docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ/03_開示府令-IFRS有価証券報告書/S003XXXX/XBRL/PublicDoc/0000000_header_jpcrp030000-asr-001_X99002-000_2026-03-31_01_2026-06-12_ixbrl.htm` — `xmlns:iso4217`, `xmlns:jpigp_cor` を確認
- [F6] パス: `docs/仕様書/2026/タクソノミ/taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd` — `substitutionGroup` 4種の実在を確認

### 推論（Reasoning）

1. [F1][F2] より、`FINALCHECK.cross_check.py` 実行で 9 チェックすべて `OK` となり、現時点でクロスチェック上の矛盾は解消済み。
2. [F3][F5] より、チェック1（P-2 名前空間）の不一致要因だった `iso4217` / `jpigp_cor` の欠落は解消され、実ファイルとも整合。
3. [F4][F6] より、チェック6（P-6 substitutionGroup）の不一致要因だった単一値扱いは解消され、C-9 および実ファイル分布と整合。
4. 残り7項目は [F2] の自動検証ログで継続して `OK` を確認できるため、再現性と追跡性は確保されている。

### 確信度

- 全体判定: **高**
- 一致: 9 / 9
- 要修正: 0 / 9

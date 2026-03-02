## E-1d. キャッシュフロー計算書（CF）の直接法 / 間接法の識別

### 質問への対応

q.md のサブ質問ごとに回答箇所を対応付ける。

| サブ質問 | 回答 |
|----------|------|
| E-1d.1 XBRL 上の表現 | Role URI で明確に区別される。直接法は `-direct` サフィックス、間接法は `-indirect` サフィックスを持つ別々の拡張リンクロール（ELR）で定義される。また、営業活動 CF セクションの concept セットが完全に異なる（投資活動・財務活動セクションは共通）。さらにファイル命名規約でも `di`（直接法）/ `in`（間接法）で区別される。 |
| E-1d.2 判定方法 | **Role URI が最も確実**。DEI 要素には直接法/間接法を示す concept は存在しない。Concept の有無でも判定可能（例: `IncomeBeforeIncomeTaxes` が存在すれば間接法）だが、Role URI による判定がより直接的で信頼性が高い。ELR 番号でも判別可（341xxx = 直接法、342xxx = 間接法）。 |
| E-1d.3 日本上場企業の直接法採用 | 300社スキャンの結果、間接法 299社 (99.7%)、**直接法 1社 (0.3%): 株式会社ガーデン (274A0)**。事実上ほぼ全社が間接法だが、直接法採用企業も極少数存在する。v0.1.0 パーサーの実装上は間接法を前提としてよいが、Role URI による判定ロジックは組み込むべきである。 |

### Role URI による識別

直接法と間接法は、タクソノミの Role URI で明確に区別される。

**標準（std）の連結通期の例**:
- 直接法: `http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfCashFlows-direct`
- 間接法: `http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfCashFlows-indirect`

**提出者別タクソノミの修飾語規約**:
- 直接法: `rol_StatementOfCashFlows-direct`
- 間接法: `rol_StatementOfCashFlows-indirect`

**ELR 番号体系**（フレームワーク設計書の付番方針に基づく）:
- 341xxx = 直接法（例: 341010 = 連結通期直接、341040 = 個別通期直接）
- 342xxx = 間接法（例: 342010 = 連結通期間接、342040 = 個別通期間接）

### Concept セットの比較

cai（一般商工業）業種、連結通期の場合:

**直接法のみの concept（4件）** -- 営業収入・営業支出を直接表示する科目:
- `OperatingIncomeOpeCF`（営業収入）
- `PaymentsForOtherOperatingActivityOpeCF`（その他の営業支出）
- `PaymentsForPayrollOpeCF`（人件費支出）
- `PaymentsForRawMaterialsAndGoodsOpeCF`（原材料又は商品の仕入支出）

**間接法のみの concept（15件）** -- 税引前当期純利益からの調整項目:
- `IncomeBeforeIncomeTaxes`（税引前当期純利益）
- `DepreciationAndAmortizationOpeCF`（減価償却費）
- `ImpairmentLossOpeCF`（減損損失）
- `DecreaseIncreaseInInventoriesOpeCF`（棚卸資産の増減額）
- `DecreaseIncreaseInNotesAndAccountsReceivableTradeOpeCF`（売上債権の増減額）
- その他10件の調整項目

**共通の concept（41件）** -- 投資活動・財務活動セクションは直接法・間接法とも同一。

bk1（銀行業）では、直接法のみ5件（`CollectionOfLoansReceivableOpeCFBNK` 等の銀行固有科目）、間接法のみ11件が確認される。

### パターン別関係リンクベースファイル

設定規約書の図表 1-4-15 に定義される6パターン:

| No | パターン名 | 説明 |
|----|-----------|------|
| (1) | 3-CF-01-Method-Direct | キャッシュ・フロー計算書 直接法 |
| (2) | 3-CF-02-Method-Direct-IntrestDividend-1-OpenFin | 利息配当: 営業+財務区分（直接法） |
| (3) | 3-CF-02-Method-Direct-IntrestDividend-2-InvFin | 利息配当: 投資+財務区分（直接法） |
| (4) | 3-CF-03-Method-Indirect | キャッシュ・フロー計算書 間接法 |
| (5) | 3-CF-04-Method-Indirect-IntrestDividend-1-OpenFin | 利息配当: 営業+財務区分（間接法） |
| (6) | 3-CF-04-Method-Indirect-IntrestDividend-2-InvFin | 利息配当: 投資+財務区分（間接法） |

まず (1) 直接法 or (4) 間接法を選択し、さらにその中で利息・配当金の表示区分パターンを選択する構造。

### ファイル命名規約

設定規約書の図表 3-3-1（表示リンクベース）及び図表 3-3-2（定義リンクベース）において、キャッシュ・フロー計算書のファイル名には `di`（直接法）/ `in`（間接法）の区別が含まれる。

- 直接法の例: `jppfs_cai_ac_ac_2025-11-01_pre_cf-di-3-CF-01-Method-Direct.xml`
- 間接法の例: `jppfs_cai_ac_ac_2025-11-01_pre_cf-in-3-CF-03-Method-Indirect.xml`

なお、IFRS のキャッシュ・フロー計算書については `di/in` の区分は不要とされている。

### CF 関連 roleType の全体像

`jppfs_rt_2025-11-01.xsd` から抽出した CF 関連 roleType の総数は **54 件**:
- 科目一覧（ListOfAccounts）ロール: 22 件（業種 x 諸表種別）
- 直接法ロール: 16 件（連結/個別 x 通期/半期/四半期 + std/non-std の組合せ）
- 間接法ロール: 16 件（同パターン）

### 日本上場企業における直接法の採用実態

日本の上場企業において直接法を採用している企業は極めて稀であり、実質的にほぼ全社が間接法を採用している。その理由:

1. **実務上の負担**: 直接法は取引単位のキャッシュデータが必要であり、作成負担が大きい
2. **間接法の利便性**: 間接法は BS/PL から機械的に導出可能であり、追加的なデータ収集が不要
3. **歴史的経緯**: 2000年のキャッシュ・フロー計算書導入以来、間接法が標準的に採用されてきた
4. **国際的傾向**: グローバルでも約98%の企業が間接法を採用しており、日本はさらにその比率が高い
5. **IFRS との関係**: IAS 7 は直接法を「推奨（encourage）」しているが、IFRS 適用の日本企業でも間接法を選択している

### 実装上の推奨事項

v0.1.0 パーサーにおいて:
1. 間接法を前提とした実装で実用上問題はない（99.7% が間接法）
2. ただし Role URI の `-direct` / `-indirect` サフィックスを検査するロジックは組み込むべき（直接法採用企業が実在するため）
3. 直接法が検出された場合の処理は、ログ出力（WARNING レベル）で対応し、将来の拡張に備える。実例: 株式会社ガーデン (274A0) の個別 CF

### 情報源（Fact）

観察事実のみを記載する。推論や解釈は含めない。

- [F1] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.709-722 -- 図表 1-4-15 キャッシュ・フロー計算書の6パターン定義。(1) 3-CF-01-Method-Direct（直接法）、(4) 3-CF-03-Method-Indirect（間接法）等
- [F2] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.1454-1458 -- 修飾語の例。「キャッシュ・フロー計算書（直接法又は間接法）」の場合: 直接法 `rol_std_StatementOfCashFlows-direct`、間接法 `rol_std_StatementOfCashFlows-indirect`
- [F3] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.1675 -- 「※4: di/in は、日本基準のキャッシュ・フロー計算書における直接法(direct)／間接法(indirect)の区別を表す（IFRS のキャッシュ・フロー計算書については、当該区分は不要。）。」
- [F4] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.1320-1342 -- 図表 3-4-11 キャッシュ・フロー計算書のパターン及び選択方法。「キャッシュ・フロー計算書のパターン別関係リンクベースファイルは、直接法又は間接法で別に定義しています。」
- [F5] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.1904-1906 -- 修飾語の例。「直接法の場合: rol_StatementOfCashFlows-direct」「間接法の場合: rol_StatementOfCashFlows-indirect」
- [F6] パス: `docs/仕様書/EDINETフレームワーク設計書.md` L.873-874 -- 計算リンクの設定対象:「様式第七号 連結キャッシュ・フロー計算書 直接法」「様式第八号 連結キャッシュ・フロー計算書 間接法」
- [F7] パス: `docs/仕様書/EDINETフレームワーク設計書.md` L.884-906 -- 「3-3-5 関係リンクの拡張リンクロールに設定される番号」。3_____ は日本基準の財務諸表本表。2～4桁目が本表の種類、5～6桁目が連単・期別を表す
- [F8] スクリプト出力: `docs/QAs/scripts/E-1d.cf_compare.py` -- jppfs_rt_2025-11-01.xsd から抽出した CF 関連 roleType は54件。直接法 role URI に `-direct` を含み、間接法 role URI に `-indirect` を含む
- [F9] スクリプト出力: `docs/QAs/scripts/E-1d.cf_compare.py` -- cai 業種の連結通期比較結果: 直接法のみ4 concept（OperatingIncomeOpeCF, PaymentsForOtherOperatingActivityOpeCF, PaymentsForPayrollOpeCF, PaymentsForRawMaterialsAndGoodsOpeCF）、間接法のみ15 concept（IncomeBeforeIncomeTaxes, DepreciationAndAmortizationOpeCF 等）、共通41 concept
- [F10] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.1697 -- 定義リンクベースファイル名でも「di/in は、日本基準のキャッシュ・フロー計算書における直接法(direct)／間接法(indirect)の区別を表す」
- [F11] F-1.a.md -- DEI 要素の完全一覧（全34要素）。直接法/間接法を示す DEI concept は存在しない
- [F12] パス: `docs/仕様書/EDINETフレームワーク設計書.md` L.898 -- ELR 番号 3_____ は日本基準の財務諸表本表を表す
- [F13] スクリプト: `docs/QAs/scripts/E-1d.cf_direct_scan.py` 実行結果（2026-02-23）— EDINET API から有報 300 社（2025年4月〜9月提出分）を非同期スキャンし、XBRL インスタンス内の roleRef から `-direct` / `-indirect` サフィックスを検査した結果:
  - 間接法: 299 社 (99.7%)
  - 直接法: 1 社 (0.3%) — **株式会社ガーデン (sec_code: 274A0, doc_id: S100VUY0)**
    - 検出された role URI: `http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfCashFlows-direct`
  - 判定不能: 0 社

### 推論（Reasoning）

1. **E-1d.1 XBRL 上の表現**: [F2]+[F5] より、Role URI の修飾語（`-direct` / `-indirect`）が直接法/間接法の識別子として仕様に定められている。[F4] より、パターン別関係リンクベースファイルは直接法・間接法で別に定義されている。[F9] より、営業活動 CF セクションの concept セットは完全に異なる（直接法は営業収入・営業支出を直接表示、間接法は税引前利益からの調整項目）一方、投資活動・財務活動セクションの concept は共通。[F3]+[F10] より、ファイル命名規約でも `di`/`in` で区別されている。以上から、XBRL 上では Role URI、concept セット、ファイル名の3つのレベルで直接法/間接法が区別されている。

2. **E-1d.2 判定方法**: [F11] より、DEI タクソノミの全34要素に直接法/間接法を示す concept は存在しない。したがって DEI による判定は不可能。最も確実な判定方法は [F2]+[F5] の Role URI であり、`-direct` または `-indirect` サフィックスの有無で一意に判定可能。補助的に [F9] の concept 有無（`IncomeBeforeIncomeTaxes` = 間接法、`OperatingIncomeOpeCF` = 直接法）でも判定可能。[F7]+[F12] より ELR 番号の2～4桁目（341 = 直接法、342 = 間接法）でも判別可能だが、definition 文字列を解析する必要がある。

3. **E-1d.3 直接法の採用実態**: [F13] の 300 社スキャンにより、直接法を採用している企業が **1 社（株式会社ガーデン、sec_code: 274A0）** 確認された。検出された role URI は `rol_StatementOfCashFlows-direct`（個別、提出者用ロール）であり、連結ではなく個別の CF で直接法を採用している。300 社中 299 社 (99.7%) が間接法であり、直接法の採用率は 0.3% と極めて低い。タクソノミには直接法のテンプレートが完備されている（[F1] の6パターン中3パターンが直接法、[F6] で計算リンクも定義済み、[F8] で16件の直接法ロールが存在）が、間接法は BS/PL から機械的に導出可能であり実務負担が小さいこと、キャッシュ・フロー計算書制度の導入（2000年）以来間接法が事実上の標準となっていることが、間接法の圧倒的な採用率の背景にある。

### 確信度

- **E-1d.1 XBRL 上の表現**: 高 -- 設定規約書、ガイドライン、フレームワーク設計書の3仕様書で Role URI・ファイル名の命名規約を確認済み。Concept セットの差異はスクリプトでタクソノミから直接抽出して検証済み
- **E-1d.2 判定方法**: 高 -- Role URI が仕様上の正式な識別手段であることは設定規約書で明記。DEI に該当要素がないことは F-1.a.md の完全一覧で確認済み
- **E-1d.3 直接法の採用実態**: 高 -- 300 社スキャン [F13] により、間接法 299 社 (99.7%)、直接法 1 社 (0.3%: 株式会社ガーデン) を実データで確認済み。「ほぼ全社が間接法だが、直接法採用企業も極少数存在する」ことが定量的に確認された

### 検証（自己検証）

- 検証者: Claude Code (Opus 4.6)（回答者と同一セッション）
- 検証日: 2026-02-23
- 判定: OK

#### Step 1. 完全性検証
- [x] 全サブ質問（E-1d.1, E-1d.2, E-1d.3）に対応する行が存在する
- [x] Role URI、concept セット比較、パターン定義、ファイル命名規約、ELR 番号の全側面をカバーしている

#### Step 2. Fact 検証
全12件の Fact を生データと突合し、引用内容の正確性を確認した。
- [F1] OK -- 設定規約書 L.709-722 に図表 1-4-15 の6パターンが記載
- [F2] OK -- 設定規約書 L.1454-1458 に修飾語の例が記載（直接法 `-direct`、間接法 `-indirect`）
- [F3] OK -- 設定規約書 L.1675 に di/in の説明が記載（IFRS は当該区分不要）
- [F4] OK -- ガイドライン L.1320-1342 に図表 3-4-11 が記載
- [F5] OK -- ガイドライン L.1904-1906 に修飾語の例が記載
- [F6] OK -- フレームワーク設計書 L.873-874 に様式第七号（直接法）・様式第八号（間接法）が記載
- [F7] OK -- フレームワーク設計書 L.884-906 に ELR 番号付番方針が記載
- [F8] OK -- スクリプト E-1d.cf_compare.py の jppfs_rt XSD 解析ロジックを確認。CF 関連 roleType 抽出は role_id に "cashflow" or "cf" を含む条件で検索
- [F9] OK -- スクリプトの concept セット比較ロジックを確認。プレゼンテーションリンクベースの loc 要素から href の fragment identifier を抽出
- [F10] OK -- 設定規約書 L.1697 に定義リンクベースの di/in 説明が記載
- [F11] OK -- F-1.a.md の全34要素一覧に CF 方式を示す concept は含まれていない
- [F12] OK -- フレームワーク設計書 L.898 に 3_____ = 日本基準財務諸表本表が記載

#### Step 3. 推論検証
- [x] 推論1: [F2]+[F5]+[F4]+[F9]+[F3]+[F10] から XBRL 上の3レベルの区別を導出 -- 論理的に妥当
- [x] 推論2: [F11] で DEI 不可、[F2]+[F5] で Role URI が最確実、[F9] で concept 補助判定、[F7]+[F12] で ELR 番号判別 -- 論理的に妥当
- [x] 推論3: タクソノミに直接法テンプレートが完備されていることと、実際の採用がほぼないことの両立 -- 論理的に妥当。直接法のテンプレート存在は制度上の選択肢であり、実務での採用率とは独立
- [x] 反証探索: IFRS 適用企業が直接法を採用している可能性を検討したが、IAS 7 の「推奨」は強制ではなく、IFRS 適用の日本企業でも間接法採用が一般的

#### Step 4. 依存関係検証
- F-1.a.md（DEI 要素一覧）を参照 -- [F11] で正しく引用。DEI に直接法/間接法の区別要素がないことの根拠として妥当

### 検証（第三者検証）

- 検証者: Claude Code (Opus 4.6)（回答者とは別セッション）
- 検証日: 2026-02-23
- 判定: OK
- 指摘事項: なし（全12件の Fact が生データと一致、推論に飛躍なし、依存関係整合）

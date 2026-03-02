## C-1b. jpigp（国際会計基準タクソノミ）の使われ方

### 質問への対応

q.md のサブ質問ごとに回答箇所を対応付ける。

| サブ質問 | 回答 |
|----------|------|
| C-1b.1 `jpigp_cor` 名前空間の要素はインスタンス文書内で直接使われるのか。それとも `jppfs_cor` のラベルを業種別に上書きするだけか | **直接使われる**。jpigp_cor は jppfs_cor とは完全に独立した要素体系を持ち、IFRS 適用企業のインスタンス文書では `jpigp_cor:RevenueIFRS` のように jpigp_cor 名前空間の要素が直接タグ付けに使用される。ラベル上書きではない。要素名の重複は 0 件 |
| C-1b.2 企業の ZIP 内の `.xsd` が `jpigp` を import するパターンはあるか | **ある**。IFRS 適用企業（ソニー E01777、トヨタ E02144）の提出者別 XSD は `jpigp_cor_{タクソノミ日付}.xsd` と `jpigp_rt_{タクソノミ日付}.xsd` を import する。同時に `jppfs_cor` も import するが、これはディメンション軸（ConsolidatedOrNonConsolidatedAxis 等）の参照のみに使用される |
| C-1b.3 `jpigp` と `jppfs` の業種カテゴリ（C-3）の関係は何か | jppfs は日本基準用で 23 業種サブディレクトリ（`r/cai/`, `r/bk1/` 等）を持つ。jpigp は IFRS 用で業種サブディレクトリを**持たない**（`r/` 直下に 57 ファイルがフラットに配置）。設定規約書では IFRS の府令略号は "igp" であり、jppfs の業種コード体系とは独立している。jpigp は全 IFRS 適用企業に共通の単一セットを提供する |

### 情報源（Fact）

観察事実のみを記載する。推論や解釈は含めない。

- [F1] スクリプト: `docs/QAs/scripts/C-1b.jpigp_analysis.py` 実行結果 -- jpigp モジュール構造: `taxonomy/jpigp/2025-11-01/` 配下に `jpigp_cor_2025-11-01.xsd`（517,164 bytes）、`jpigp_rt_2025-11-01.xsd`（138,131 bytes）、`deprecated/`、`label/`、`r/` ディレクトリが存在
- [F2] 同スクリプト -- jpigp_cor XSD 分析: namespace = `http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor`、要素数 = 1,803（abstract=true: 684, abstract=false: 1,119）
- [F3] 同スクリプト -- jppfs_cor との要素名重複分析: jpigp 要素 1,803 個と jppfs 要素 4,139 個の間で **重複要素は 0 件**。完全に独立した要素体系である
- [F4] 同スクリプト -- IFRS サフィックス除去後の概念的重複: jpigp の要素名から末尾の "IFRS" を除去すると jppfs と 76 件の概念的重複がある。例: `jppfs:CostOfSales` と `jpigp:CostOfSalesIFRS`、`jppfs:Assets` と `jpigp:AssetsIFRS`
- [F5] 同スクリプト -- jpigp の命名パターン: IFRS サフィックス付き 614 件、Heading サフィックス付き 513 件、その他（TextBlock, Abstract 等）676 件
- [F6] 同スクリプト -- jpigp `r/` ディレクトリ: **サブディレクトリなし**（業種別分割なし）。57 ファイルがフラットに配置。リンクベース種別: cal 6 件、def 36 件、pre 15 件。ファイル名パターンには `jpigp_ac_*_cal_bs.xml`（科目一覧）、`jpigp_cm_*_def_bs-cu.xml`（cu/lq 区分）等がある
- [F7] 同スクリプト -- 比較: jppfs `r/` ディレクトリには 23 業種サブディレクトリ（bk1, bk2, cai, cmd, cna, cns, edu, elc, ele, fnd, gas, hwy, in1, in2, inv, ivt, lea, liq, med, rwy, sec, spf, wat）が存在
- [F8] 同スクリプト -- jpigp_cor XSD の import: `xbrl-instance`, `numeric`, `non-numeric`, `iod`（common の identificationAndOrdering）, `xbrldt` の 5 件。jppfs_cor は import していない
- [F9] P-4.a.md [F2] -- ソニーの XBRL インスタンス文書の名前空間宣言に `jpigp_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"` が存在。`ifrs-full` 名前空間は宣言されていない
- [F10] P-4.a.md [F4] -- ソニーの提出者別 XSD の import 文: `jpigp_cor_2024-11-01.xsd` + `jpigp_rt_2024-11-01.xsd` を import。同時に `jppfs_cor_2024-11-01.xsd` + `jppfs_rt_2024-11-01.xsd` も import（ディメンション軸用）
- [F11] P-3.a.md [F3] -- トヨタ（E02144, IFRS 適用企業）の提出者別 XSD も同じく `jpigp_cor_2024-11-01.xsd` + `jpigp_rt_2024-11-01.xsd` を import
- [F12] パス: `docs/仕様書/EDINETフレームワーク設計書.md` L.1059-1076 -- 図表 3-4-1「提出者別タクソノミで国際会計基準タクソノミを利用するための仕組み」:「利用する要素: 国際会計基準タクソノミの要素を利用するが、セグメント軸及び連結単体軸とそのメンバーのみはそれぞれ開示府令タクソノミ、財務諸表本表タクソノミの要素を利用する」「財務諸表本表のタグ付け: IFRS財務諸表の本表は、国際会計基準タクソノミの要素を用い金額ごとにタグ付けをする」
- [F13] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.293 -- 図表 1-4-1 府令略号 No.9:「IFRS 財務諸表 | igp」
- [F14] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.1695-1699 -- 「※3: IFRS 財務諸表の場合、jppfs が jpigp となる点を除き同様。」「※5: IFRS 財務諸表の場合、jppfs が jpigp となる。cu/lq は、IFRS の財政状態計算書科目一覧における流動・非流動区分法(current/non-current)／流動性配列法(order of liquidity)の別を表す」
- [F15] パス: `docs/仕様書/EDINETタクソノミの概要説明.md` L.964 -- 図表 2-3-7 No.2:「jpigp | 国際会計基準 | IFRS 財務諸表に係るタクソノミ要素を含みます。なお、本タクソノミの要素は、IFRS の財務諸表本表及び注記事項中の主要勘定の内訳開示で用いることができます。」

### 推論（Reasoning）

1. **C-1b.1（直接利用かラベル上書きか）について**: [F3] より、jpigp_cor と jppfs_cor の間で要素名が完全に一致する要素は **0 件** である。これは jpigp_cor がラベル上書きではなく、独立した要素体系であることを決定的に示す。[F4] より、概念的に対応する要素（例: `CostOfSales` / `CostOfSalesIFRS`）は存在するが、名前空間が異なる別要素として定義されている。[F12] の仕様書でも「IFRS財務諸表の本表は、国際会計基準タクソノミの要素を用い金額ごとにタグ付けをする」と明記されており、jpigp_cor 要素がインスタンス文書内で直接使用されることが確認できる。[F9] の実データ（ソニー）でも jpigp_cor 名前空間が宣言されており、実際にタグ付けに使用されている。

2. **C-1b.2（ZIP 内 XSD の import パターン）について**: [F10] + [F11] より、ソニー（E01777）とトヨタ（E02144）の 2 社の IFRS 適用企業で、提出者別 XSD が `jpigp_cor` + `jpigp_rt` を import するパターンが確認された。同時に `jppfs_cor` + `jppfs_rt` も import されるが、[F12] の仕様書記述「セグメント軸及び連結単体軸とそのメンバーのみはそれぞれ開示府令タクソノミ、財務諸表本表タクソノミの要素を利用する」から、jppfs_cor の import はディメンション軸の参照目的であると判断できる。つまり IFRS 企業の提出者別 XSD は jpigp_cor（IFRS 勘定科目用）と jppfs_cor（ディメンション軸用）の両方を import する。

3. **C-1b.3（jpigp と jppfs の業種カテゴリの関係）について**: [F6] + [F7] より、jppfs の `r/` ディレクトリは 23 業種サブディレクトリ（bk1, cai, cns 等）を持つが、jpigp の `r/` ディレクトリは業種サブディレクトリを持たず、57 ファイルがフラットに配置されている。[F13] より、設定規約書の府令略号表で IFRS は "igp" という単一の略号が割り当てられており、jppfs のような業種別分割は定義されていない。[F14] の「IFRS 財務諸表の場合、jppfs が jpigp となる」という記述は、ファイル命名規約において jppfs を jpigp に読み替えることを意味するが、業種サブディレクトリの分割は行わないことを意味する。これは IFRS では日本基準のような業種別の財務諸表様式の違い（銀行業の特殊勘定科目等）がないためと考えられる。

4. [F6] より、jpigp の `r/` 配下のファイル名には `jpigp_cm_*_def_bs-cu.xml` / `jpigp_cm_*_def_bs-lq.xml` という cu/lq パターンが見られる。[F14] の仕様書記述「cu/lq は、IFRS の財政状態計算書科目一覧における流動・非流動区分法(current/non-current)／流動性配列法(order of liquidity)の別を表す」と一致する。これは jpigp 固有の分類であり、jppfs には存在しないパターンである（jppfs は代わりに di/in = 直接法/間接法のキャッシュ・フロー計算書区分を持つ）。

5. [F8] より、jpigp_cor XSD は jppfs_cor を import していない。つまりスキーマレベルでの依存関係はない。jpigp と jppfs は完全に並行する独立したモジュールであり、IFRS 企業のインスタンス文書が jppfs のディメンション要素を参照するのは、提出者別タクソノミの import チェーンを通じてである（jpigp_cor 自体の import ではない）。

### 確信度

- **高**（仕様書に明記 + 実ファイル確認 + 実データ（ソニー・トヨタ）で裏付け済み）
- C-1b.1: 要素名重複 0 件という事実は決定的。仕様書の「国際会計基準タクソノミの要素を用い金額ごとにタグ付けをする」[F12] とも完全に整合
- C-1b.2: ソニー・トヨタの 2 社で同一パターンを確認。仕様書の図表 3-4-1 [F12] とも整合
- C-1b.3: r/ ディレクトリの構造差異は実ファイルで直接確認済み。設定規約書の igp 略号 [F13] とも整合

### E-1c. 株主資本等変動計算書（SS）の2次元構造

SS は本質的に2次元テーブル（行 = 資本金・資本剰余金等、列 = 当期首残高・変動額・当期末残高）である:

1. SS の2次元構造は XBRL 上どう表現されるか。列方向の区別は Context の period（instant vs duration）で行うのか、dimension で行うのか
2. presentation linkbase だけで SS を組み立てられるか。definition linkbase の dimension が必要か
3. H-7 の Table Linkbase が SS の組み立てに必須か
4. SS の行・列ヘッダーの取得方法（ラベルリンクベース? プレゼンテーションリンクベース?）
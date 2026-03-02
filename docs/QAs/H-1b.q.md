### H-1b. DTS（Discoverable Taxonomy Set）解決アルゴリズム ★パーサーのアーキテクチャに直結

タクソノミ参照の解決方法の具体的な詳細:

1. **提出者 `.xsd` 内の `xs:import` 要素の `schemaLocation`**: 相対パスか絶対 URL か
2. **URL → ローカルパスの変換規則**: 標準タクソノミの参照先が `http://disclosure.edinet-fsa.go.jp/taxonomy/...` のような URL の場合、ローカルの `ALL_20251101/` へのマッピングルールは何か。**具体的な URL 5〜10 個**とそれに対応する `ALL_20251101/` 内のローカルパスを列挙してください。例:
   ```
   http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd
   → ALL_20251101/taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd
   ```
   のような対応を、主要モジュール（jppfs, jpcrp, jpdei, jpigp, common 等）について示してください
3. **import の連鎖の深さ**: 提出者 `.xsd` → `jpcrp_cor.xsd` → `jppfs_cor.xsd` → `xbrl-instance.xsd` のような import 連鎖は何段階あるか。実際の提出者 `.xsd` の `xs:import` 要素を全て列挙した例を示してください
4. **各 import で参照される `.xsd` の `ALL_20251101/` 内での対応パス**: 具体的なパスマッピングの一覧
5. **URL のベース部分**: `http://disclosure.edinet-fsa.go.jp/taxonomy/` が固定プレフィックスで、これを `ALL_20251101/taxonomy/` に置換すれば全て解決できるか。例外はあるか（XBRL International の標準スキーマ等）
6. **XBRL International 標準スキーマの所在**: 提出者 `.xsd` の import 連鎖を辿ると、最終的に XBRL International の標準スキーマ（`http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd`, `http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd`, `http://www.xbrl.org/2003/xl-2003-12-31.xsd`, `http://www.xbrl.org/2005/xbrldt-2005.xsd` 等）および W3C スキーマ（`http://www.w3.org/2001/xml.xsd`）に到達する。これらは `ALL_20251101` 内に同梱されているか。同梱されている場合のローカルパスは。同梱されていない場合、オフライン環境での DTS 解決方法は。`lxml` の `no_network=True` 相当の設定で動作可能か。`ALL_20251101` に OASIS XML Catalog（`META-INF/catalog.xml`）は存在するか
7. **タクソノミパッケージ準拠**: `ALL_20251101` は XBRL Taxonomy Package 仕様（`META-INF/taxonomyPackages.xml`）に準拠しているか。準拠していれば `catalog.xml` で URL → ローカルパスの変換が自動解決でき、H-1b.2 の手動マッピングが不要になる可能性がある

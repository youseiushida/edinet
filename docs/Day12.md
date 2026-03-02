# Day 12 — TaxonomyResolver 実装

## 0. 位置づけ

Day 12 は、XBRL の concept（例: `jppfs_cor:NetSales`）から人間が読めるラベル（例: 「売上高」）を解決する **TaxonomyResolver** を実装する日。

Day 10 完了時点の状態:
- `parse_xbrl_facts()` が `ParsedXBRL` を返す（`RawFact` + `RawContext` + `RawUnit`）
- `structure_contexts()` が `dict[str, StructuredContext]` を返す（期間・Entity・Dimension を型付きで引ける）
- `taxonomy.py` は 1 行の docstring のみ（未実装）

Day 12 完了時のマイルストーン:

```python
from edinet.xbrl.taxonomy import TaxonomyResolver

# 標準タクソノミからラベル辞書を構築（初回: ~3秒、2回目以降: ~50ms via キャッシュ）
resolver = TaxonomyResolver("/path/to/ALL_20251101")

# concept → ラベル解決
label = resolver.resolve("jppfs_cor", "NetSales")
print(label.text)     # "売上高"
print(label.role)     # "http://www.xbrl.org/2003/role/label"
print(label.source)   # LabelSource.STANDARD

# 英語ラベル
label_en = resolver.resolve("jppfs_cor", "NetSales", lang="en")
print(label_en.text)  # "Net sales"

# 提出者タクソノミのラベルを追加（ZIP 内の _lab.xml）
resolver.load_filer_labels(filer_lab_xml_bytes, filer_lab_en_xml_bytes)
label_ext = resolver.resolve("jpcrp030000-asr_X99001-000", "SomeCustomItem")
print(label_ext.source)  # LabelSource.FILER

# バージョン情報
print(resolver.taxonomy_version)  # "ALL_20251101"
```

CODESCOPE.md の関連:
- §4 facts→LineItem の F-2「ラベル付与」の基盤
- FEATURES.md の taxonomy/labels に対応

---

## 1. 現在実装の確認結果

| ファイル | 現状 | Day 12 で必要な変更 |
|---|---|---|
| `src/edinet/xbrl/taxonomy.py` | 1 行 docstring のみ | 新規実装。`TaxonomyResolver` + `LabelInfo` + `LabelSource` |
| `src/edinet/xbrl/contexts.py` | 完成済み。名前空間定数 `NS_XBRLI`, `NS_XBRLDI` を内部定義 | 名前空間定数を `_namespaces.py` に移動（Day 10 §6.2 設計判断 11 の合意事項） |
| `src/edinet/xbrl/parser.py` | 完成済み。`_NS_XBRLI` 等を private 定数で定義 | `_namespaces.py` からインポートするよう変更 |
| `src/edinet/xbrl/__init__.py` | `parse_xbrl_facts`, `structure_contexts` をエクスポート | `TaxonomyResolver` を追加エクスポート |
| `src/edinet/_config.py` | `taxonomy_path: str | None = None` が既に存在 | 変更なし |
| `tests/test_xbrl/test_taxonomy.py` | 未作成 | 新規作成 |
| `tests/fixtures/taxonomy_mini/` | 未作成 | 新規作成。主要 ~20 concept 分の軽量 `_lab.xml` / `_lab-en.xml` |
| `stubs/edinet/xbrl/taxonomy.pyi` | 空 | stubgen で生成 |

---

## 2. ゴール

1. 標準タクソノミの `_lab.xml` / `_lab-en.xml` をパースして `{ (prefix, local_name): LabelInfo }` 辞書を構築する
2. 提出者タクソノミの `_lab.xml` を追加で読み込み、拡張科目のラベルを追加する
3. pickle キャッシュで初回 ~3 秒 → 2 回目以降 ~50ms を実現する
4. タクソノミバージョン情報（例: `ALL_20251101`）を保持する
5. `LabelInfo` 型でラベルの `role` と `source` を保持する（`str` に潰さない）

---

## 3. スコープ / 非スコープ

### 3.1 Day 12 のスコープ

| 機能 | 詳細 |
|---|---|
| ラベル辞書の構築 | `_lab.xml` / `_lab-en.xml` をパースし、concept → LabelInfo のマッピングを作成 |
| 多言語対応 | `lang="ja"` / `lang="en"` でラベルを切り替え |
| 複数ロール対応 | 標準ラベル（label）、冗長ラベル（verboseLabel）、合計ラベル（totalLabel）等を role 指定で取得 |
| 提出者ラベルの追加 | ZIP 内の提出者 `_lab.xml` bytes を渡して拡張科目のラベルを追加 |
| pickle キャッシュ | `platformdirs.user_cache_dir` 配下に pickle 保存。ライブラリバージョン + タクソノミバージョン + パスハッシュをキーに含む |
| バージョン情報 | `resolver.taxonomy_version` でタクソノミバージョンを取得可能 |
| 名前空間定数の集約 | `_namespaces.py` を新設し、parser.py / contexts.py の重複定数を統合 |

### 3.2 Day 12 でやらないこと

| 内容 | やらない理由 |
|---|---|
| Concept 辞書（L1: type, periodType, balance 等） | H-9b の L1 は必要になった時点（Day 15 or v0.2.0）で追加。Day 12 はラベル辞書（L2）のみ |
| Presentation / Calculation / Definition ツリー | リキャスト方式のため filing ごとのパースが必要。FEATURES.md の別モジュール（calc_tree, pres_tree, def_links）の責務 |
| arc override の完全実装（prohibited） | C-5.4: 日本語ラベルの上書きは不可。英語ラベルの prohibited は実データでサンプルに 0 件（H-9b [F5]）。v0.1.0 では提出者ラベルの単純追加（ChainMap パターン）で十分。ただし `labelArc` に `use="prohibited"` または `priority` 属性が出現した場合は `warnings.warn()` で検出を通知する（サイレントな誤ラベル化の防止）  <!-- R5-FB2 追加: prohibited/priority 検出時 warning --> |
| preferredLabel の解決 | presentationArc の preferredLabel 解決は pres_tree モジュールの責務。TaxonomyResolver は指定された role のラベルを返すのみ |
| gla.xml のパース | roleType の英語ラベル専用。concept ラベルとは無関係（C-5.3） |
| 全モジュール横断の一括ロード | v0.1.0 では必要なモジュールのみ読む（jppfs, jpcrp, jpdei 等）。全 18 モジュールの一括ロードは v0.2.0 以降 |
| ZIP から `_lab.xml` を抽出する導線 | `load_filer_labels()` は bytes を受け取る設計。ZIP からの `_lab.xml` 抽出は呼び出し側の責務。現状の `Filing.fetch()` は代表 `.xbrl` のみ返すため、ZIP 内の任意ファイルアクセス API は Day 13 以降で整備する |
| lang 方向のフォールバック | `resolve(role=ROLE_TOTAL, lang="en")` で英語 totalLabel がない場合に「日本語の totalLabel」にフォールバックする機能。C-5.6 により標準タクソノミでは日英ラベル数が完全一致で発生しないが、提出者ラベルでは理論上起こりうる。v0.2.0 以降で需要が出た場合に検討する  <!-- R5-3 追加: lang フォールバック非スコープ明記 --> |

---

## 4. QA 反映方針（Day 12 に直結するもの）

| QA | Day 12 への反映 |
|---|---|
| C-5.1 | ラベルロールは XBRL 標準 10 種 + EDINET 固有 72 種。TaxonomyResolver は任意の role URI を受け付ける。デフォルトは `http://www.xbrl.org/2003/role/label`（標準ラベル） |
| C-5.4 | 日本語ラベル上書き不可、英語ラベル上書き可。v0.1.0 では提出者ラベルを `ChainMap` で上書き（prohibited の完全処理は省略するが、`labelArc` に `use="prohibited"` / `priority` 属性が出現した場合は `warnings.warn()` で通知する）  <!-- R5-FB2 修正: prohibited 検出 warning を明記 --> |
| C-5.5 | ラベル解決アルゴリズム: ① 指定 role + 指定 lang で検索 → ② 標準ラベル role にフォールバック → ③ local name にフォールバック |
| C-5.6 | 全 concept に標準ラベル + 冗長ラベルが存在。日英で 9,169 件ずつ完全一致。フォールバック（local name）は到達しないはずだが念のため実装 |
| C-10 | _lab.xml の構造: `link:loc`（concept 参照）→ `link:labelArc`（arcrole=concept-label）→ `link:label`（テキスト）。loc の `xlink:href` から concept の prefix + local_name を抽出 |
| H-9 | 全タクソノミ ~21MB。ラベル ~13.5MB。メモリに余裕あり |
| H-9b | 3 層キャッシュ構造のうち L2（ラベル辞書）を実装。pickle でシリアライズ。提出者分はデルタ追加 |
| E-7 | 主要勘定科目の concept 名辞書が整備済み。テストのフィクスチャに使用 |

---

## 5. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/xbrl/_namespaces.py` | 新規 | 名前空間定数の集約。parser.py / contexts.py / taxonomy.py で共用 |
| `src/edinet/xbrl/taxonomy.py` | 新規 | `TaxonomyResolver`, `LabelInfo`, `LabelSource` |
| `src/edinet/xbrl/parser.py` | 修正 | private 名前空間定数を `_namespaces.py` からインポートに変更 |
| `src/edinet/xbrl/contexts.py` | 修正 | 同上 |
| `src/edinet/xbrl/__init__.py` | 追記 | `TaxonomyResolver` を追加エクスポート |
| `tests/test_xbrl/test_taxonomy.py` | 新規 | Small/Unit + Medium テスト |
| `tests/fixtures/taxonomy_mini/` | 新規 | 軽量タクソノミフィクスチャ |
| `stubs/edinet/xbrl/taxonomy.pyi` | 生成 | stubgen で自動生成 |
| `stubs/edinet/xbrl/_namespaces.pyi` | 生成 | 同上 |

---

## 6. taxonomy モジュール設計詳細

### 6.1 公開 I/F

```python
from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path


class LabelSource(enum.Enum):
    """ラベルの情報源。

    Attributes:
        STANDARD: EDINET 標準タクソノミ由来。
        FILER: 提出者別タクソノミ由来。
        FALLBACK: ラベルが見つからず local name を使用。
    """
    STANDARD = "standard"
    FILER = "filer"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class LabelInfo:
    """解決されたラベル情報。

    Attributes:
        text: ラベルテキスト（例: ``"売上高"``）。
        role: ラベルロール URI。
        lang: 言語コード（``"ja"`` / ``"en"``）。
        source: ラベルの情報源。
    """
    text: str
    role: str
    lang: str
    source: LabelSource


# 標準ラベルロール
ROLE_LABEL = "http://www.xbrl.org/2003/role/label"
ROLE_VERBOSE = "http://www.xbrl.org/2003/role/verboseLabel"
ROLE_TOTAL = "http://www.xbrl.org/2003/role/totalLabel"


class TaxonomyResolver:
    """EDINET タクソノミのラベル解決を行うクラス。

    標準タクソノミの ``_lab.xml`` / ``_lab-en.xml`` をパースし、
    concept → ラベルの辞書を構築する。初回パース結果は pickle で
    キャッシュされ、2 回目以降は高速に読み込まれる。

    Attributes:
        taxonomy_version: タクソノミバージョン（例: ``"ALL_20251101"``）。
        taxonomy_path: タクソノミのルートパス。

    Example:
        >>> resolver = TaxonomyResolver("/path/to/ALL_20251101")
        >>> label = resolver.resolve("jppfs_cor", "NetSales")
        >>> print(label.text)
        売上高
    """

    def __init__(
        self,
        taxonomy_path: str | Path,
        *,
        use_cache: bool = True,
    ) -> None:
        """TaxonomyResolver を初期化する。

        Args:
            taxonomy_path: タクソノミのルートディレクトリパス。
                ``ALL_20251101`` 等の最上位ディレクトリを指定する。
            use_cache: pickle キャッシュを使用するか。
                ``False`` の場合は毎回パースする（テスト用）。

        Raises:
            EdinetConfigError: taxonomy_path が存在しない場合。
        """
        ...

    @property
    def taxonomy_version(self) -> str:
        """タクソノミバージョン文字列（例: ``"ALL_20251101"``）。"""
        ...

    @property
    def taxonomy_path(self) -> Path:
        """タクソノミのルートパス。"""
        ...

    def resolve(
        self,
        prefix: str,
        local_name: str,
        *,
        role: str = ROLE_LABEL,
        lang: str = "ja",
    ) -> LabelInfo:
        """concept のラベルを解決する。

        Args:
            prefix: 名前空間プレフィックス（例: ``"jppfs_cor"``）。
            local_name: ローカル名（例: ``"NetSales"``）。
            role: ラベルロール URI。デフォルトは標準ラベル。
            lang: 言語コード。``"ja"`` または ``"en"``。

        Returns:
            解決された LabelInfo。ラベルが見つからない場合は
            指定 role → 標準ラベル → local name の順でフォールバック。

        Note:
            フォールバック時の LabelInfo は ``source=LabelSource.FALLBACK``、
            ``text=local_name`` となる。
        """
        ...

    def resolve_clark(
        self,
        concept_qname: str,
        *,
        role: str = ROLE_LABEL,
        lang: str = "ja",
    ) -> LabelInfo:
        """Clark notation の concept QName からラベルを解決する。

        Args:
            concept_qname: Clark notation の QName
                （例: ``"{http://...jppfs_cor}NetSales"``）。
            role: ラベルロール URI。
            lang: 言語コード。

        Returns:
            解決された LabelInfo。
        """
        ...

    def load_filer_labels(
        self,
        lab_xml_bytes: bytes | None = None,
        lab_en_xml_bytes: bytes | None = None,
        *,
        xsd_bytes: bytes | None = None,  # R4-1 追加
    ) -> int:
        """提出者別タクソノミのラベルを追加読み込みする。

        提出者の ``_lab.xml`` をパースし、拡張科目のラベルを
        ``_filer_labels`` に追加する。``xsd_bytes`` が渡された場合、
        XSD の ``targetNamespace`` から namespace URI → prefix
        マッピングを ``_ns_to_prefix`` に追加する。これにより
        ``resolve_clark()`` が提出者拡張科目の Clark notation を
        正しく解決できる。

        Args:
            lab_xml_bytes: 提出者の ``_lab.xml``（日本語）の bytes。
            lab_en_xml_bytes: 提出者の ``_lab-en.xml``（英語）の bytes。
            xsd_bytes: 提出者の ``.xsd`` の bytes。渡された場合、
                ``targetNamespace`` を抽出して ``_ns_to_prefix`` に
                追加する。省略時は ``resolve_clark()`` での提出者
                拡張科目の解決が FALLBACK になる。

        Returns:
            追加されたラベル数。

        Warns:
            EdinetWarning: ``_filer_labels`` が空でない状態で呼ばれた場合、
                前回の提出者ラベルがクリアされていない旨を警告する。
                処理自体は続行し、既存の提出者ラベルに追加される。
                <!-- R5-FB4 追加: クリア忘れ防御 -->
        """
        ...

    def clear_filer_labels(self) -> None:
        """提出者別ラベルをクリアし、提出者由来の ``_ns_to_prefix`` エントリも除去する。

        次の filing を処理する前に呼び出す。
        """
        ...
```

### 6.2 設計判断

1. **`resolve()` の引数を `(prefix, local_name)` にする理由**: RawFact は `namespace_uri` と `local_name` を持つが、`_lab.xml` の `link:loc` の `xlink:href` は `../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales` のように `prefix_localName` 形式。namespace URI からの逆引きよりも、prefix ベースの方が `_lab.xml` の構造と自然に対応する。ただし Clark notation からの解決需要も高いため `resolve_clark()` も提供する
2. **`LabelInfo` を dataclass にする理由**: PLAN.LIVING.md Day 12/13 で「`str` に潰さない」と明記。role と source を保持することで「なぜこの表示名か」が追跡可能
3. **`LabelSource` を enum にする理由**: 文字列リテラル `"standard"` / `"filer"` だとタイポが実行時まで検出されない。enum なら静的解析で検出可能
4. **`load_filer_labels()` / `clear_filer_labels()` の設計**: filing ごとに異なる提出者ラベルを、標準ラベル辞書とは独立して管理する。H-9b の ChainMap パターンに対応。`clear_filer_labels()` を呼ばないと前の filing のラベルが残る（明示的なライフサイクル管理）。**`load_filer_labels()` を `_filer_labels` が空でない状態で呼び出した場合は `warnings.warn("前回の filer ラベルがクリアされていません。clear_filer_labels() を先に呼んでください")` を出す**（R4-6 で Day 13 送りだった防御を Day 12 に前倒し）  <!-- R5-FB4 変更: クリア忘れ防御を Day 12 に前倒し -->
5. **`use_cache=True` のデフォルト**: 本番用途ではキャッシュが必須（3秒→50ms）。テストでは `use_cache=False` で毎回パースさせてキャッシュの影響を排除
6. **コンストラクタで全ラベルをロードする理由**: lazy loading にするとプロパティアクセスのたびに「初回ロードか否か」のチェックが入り、コードが複雑化する。コンストラクタで全ロードすれば `resolve()` は純粋な辞書引きで O(1)

### 6.3 内部データ構造

```python
# ラベル辞書のキー: (prefix, local_name, role, lang)
# 例: ("jppfs_cor", "NetSales", "http://.../label", "ja") → "売上高"
type _LabelKey = tuple[str, str, str, str]  # Python 3.12+ type statement。モジュールレベル定義。_ prefix のため __all__ には含めない（内部型）  <!-- R4-7 変更: TypeAlias を明示 --> <!-- R6-3 追記: 配置と公開範囲を明示 -->

# 標準タクソノミラベル（イミュータブル、全 filing 共通）
_standard_labels: dict[_LabelKey, str]

# 提出者ラベル（filing ごとにクリア）
_filer_labels: dict[_LabelKey, str]

# namespace URI → prefix の逆引き辞書
# 標準タクソノミ分はコンストラクタで構築。
# 提出者分は load_filer_labels() で追加、clear_filer_labels() で除去。
_ns_to_prefix: dict[str, str]
# 提出者由来のエントリを clear 時に除去するため、追加したキーを記録:
_filer_ns_keys: set[str]
```

resolve() のアルゴリズム:
```
1. _filer_labels[(prefix, local, role, lang)] を検索
   → 見つかれば LabelInfo(source=FILER) を返す
2. _standard_labels[(prefix, local, role, lang)] を検索
   → 見つかれば LabelInfo(source=STANDARD) を返す
3. role != ROLE_LABEL の場合、ROLE_LABEL でフォールバック（手順 1-2 を lang を変更せず再実行）  <!-- R3-3 追加: lang 引き継ぎを明記 -->
4. いずれも見つからなければ LabelInfo(text=local_name, source=FALLBACK) を返す
```

### 6.4 `_lab.xml` パース方針

C-10.a.md の XML 構造に基づく:

```xml
<link:labelLink xlink:role="http://www.xbrl.org/2003/role/link" ...>
  <!-- loc: concept 参照 -->
  <link:loc xlink:label="NetSales"
    xlink:href="../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales"/>

  <!-- label リソース -->
  <link:label xlink:label="label_NetSales"
    xlink:role="http://www.xbrl.org/2003/role/label"
    xml:lang="ja">売上高</link:label>

  <!-- labelArc -->
  <link:labelArc xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"
    xlink:from="NetSales" xlink:to="label_NetSales"/>
</link:labelLink>
```

パース手順:
1. `link:loc` を収集し、`xlink:label`（キー）→ `xlink:href` から抽出した `(prefix, local_name)` のマッピングを構築
   - **重要: `xlink:label` 属性の値そのものからではなく、`xlink:href` から `_extract_prefix_and_local()` で抽出する。** `xlink:label` は arc 接続用のキーであり、concept 名との対応は仕様上保証されない（C-10 参照）。同一 concept が同一 `labelLink` 内で重複参照される場合、`xlink:label` に `_2` 等のサフィックスが付く  <!-- R5-5 変更: loc→arc→label 接続の正確さを強調 -->
   - `xlink:href` の fragment（`#` 以降）から prefix + local_name を抽出: `jppfs_cor_NetSales` → `("jppfs_cor", "NetSales")`
   - fragment のフォーマット: `{prefix}_{local_name}`。prefix 自体に `_` を含みうるため、XSD ファイル名から prefix を逆引きするか、既知の prefix リストで照合する
2. `link:label` を収集し、`xlink:label`（キー）→ `(role, lang, text)` のマッピングを構築
3. `link:labelArc` を辿り、`xlink:from`（loc のキー）→ `xlink:to`（label のキー）を接続。**`use="prohibited"` または `priority` 属性が存在する arc を検出した場合は `warnings.warn()` で通知する**（完全な arc override 処理は v0.1.0 非スコープだが、サイレントな誤ラベル化を防止する）  <!-- R5-FB2 追加: prohibited/priority 検出 warning -->
4. 最終的に `(prefix, local_name, role, lang) → text` の辞書を構築

擬似コード:  <!-- R5-5 追加: 実装時のミス防止のため擬似コードを具体化 -->

**前提（実データで確認済み）:**  <!-- R6-1, R6-2 追加 -->
- `link:label` の `xlink:label` は同一 `labelLink` 内で 100% ユニーク（実タクソノミ全モジュールで 13,308 個確認）。そのため `label_map` は `dict[str, tuple]`（1:1）で安全。1 つの loc に対して複数の labelArc が接続されるが、各 arc の `xlink:to` は異なる label キーを指す（例: `label_CashAndDeposits`, `label_CashAndDeposits_2`, ...）
- EDINET 標準タクソノミの全モジュール、および提出者タクソノミでも `labelLink` は通常 1 つ。`root.iter()` でフラット収集しても `xlink:label` キーの labelLink 間衝突は発生しない。万一提出者 `_lab.xml` で複数 `labelLink` が出現した場合に備え、v0.2.0 で `labelLink` 単位の処理に切り替える余地を残す

```python
def _parse_lab_xml(lab_path: Path) -> dict[_LabelKey, str]:
    tree = etree.parse(str(lab_path))
    root = tree.getroot()

    # Step 1: loc のキー → (prefix, local_name)
    loc_map: dict[str, tuple[str, str]] = {}
    for loc in root.iter(f"{{{NS_LINK}}}loc"):
        key = loc.get(f"{{{NS_XLINK}}}label")   # arc 接続用キー
        href = loc.get(f"{{{NS_XLINK}}}href")    # concept 参照
        if key is None or href is None:
            continue
        result = _extract_prefix_and_local(href)  # ★ href から抽出
        if result is not None:
            loc_map[key] = result

    # Step 2: label のキー → (role, lang, text)
    # 前提: xlink:label は labelLink 内でユニーク（実データ確認済み）
    # そのため 1:1 の dict で安全。後勝ちは発生しない  <!-- R6-1 -->
    label_map: dict[str, tuple[str, str, str]] = {}
    for label in root.iter(f"{{{NS_LINK}}}label"):
        key = label.get(f"{{{NS_XLINK}}}label")
        role = label.get(f"{{{NS_XLINK}}}role")
        lang = label.get(f"{{{NS_XML}}}lang")
        text = label.text or ""
        if key and role and lang:
            label_map[key] = (role, lang, text.strip())

    # Step 3: labelArc で接続
    result: dict[_LabelKey, str] = {}
    for arc in root.iter(f"{{{NS_LINK}}}labelArc"):
        # prohibited/priority 検出  <!-- R5-FB2 -->
        if arc.get("use") == "prohibited" or arc.get("priority") is not None:
            warnings.warn(...)  # 省略
        from_key = arc.get(f"{{{NS_XLINK}}}from")  # loc のキー
        to_key = arc.get(f"{{{NS_XLINK}}}to")      # label のキー
        if from_key in loc_map and to_key in label_map:
            prefix, local = loc_map[from_key]
            role, lang, text = label_map[to_key]
            result[(prefix, local, role, lang)] = text

    logger.info("ラベルをロード: %s (%d 件)", lab_path.name, len(result))  # <!-- R6-7 追加: パース概要は info -->
    return result
```

**パース時の logging 方針**:  <!-- R6-7 追加 -->
- パースの概要（「jppfs: 9,169 ラベルをロード」等）は `logger.info()` — ユーザーにとって進捗が分かる情報
- 個別の loc/arc/label 処理の詳細は `logger.debug()` — 開発者向けデバッグ情報
- §6.6 のキャッシュ logging 方針（R3-5）と同じルール: 「ユーザーに伝えるべき状態変化は info、内部処理詳細は debug」

**prefix 抽出の注意点**:

`xlink:href` fragment の `jppfs_cor_NetSales` から prefix と local_name を分離するには工夫が必要。prefix に `_` が含まれるケース（例: `jppfs_cor`）やハイフンを含むケース（例: `jpcrp030000-asr`）があるため、単純な `rsplit("_", 1)` では不十分。

解決方法: `xlink:href` の XSD ファイル名部分から正規表現で prefix を抽出し、fragment から prefix + `_` を除去して local_name を得る。

```python
import re

# XSD ファイル名パターン: {prefix}_{YYYY-MM-DD}.xsd
# prefix は英数字・ハイフン・アンダースコアを含みうる（例: jppfs_cor, jpcrp030000-asr_X99001-000）
# 貪欲マッチ (.+) + 末尾固定 ($) により、最後の _YYYY-MM-DD.xsd だけが日付部分に
# マッチし、prefix 内の _ やハイフンを正しく保持する。  <!-- R3-2 変更: (.+?) → (.+)$ で意図を明示 -->
_XSD_PREFIX_RE = re.compile(r"(.+)_(\d{4}-\d{2}-\d{2})\.xsd$")

def _extract_prefix_and_local(href: str) -> tuple[str, str] | None:
    """xlink:href から (prefix, local_name) を抽出する。

    Args:
        href: 例 ``"../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales"``

    Returns:
        ``("jppfs_cor", "NetSales")`` または抽出失敗時 ``None``。
    """
    if "#" not in href:
        return None
    path_part, fragment = href.rsplit("#", 1)
    basename = path_part.rsplit("/", 1)[-1]  # パス部分は不要、ファイル名のみ
    m = _XSD_PREFIX_RE.match(basename)
    if m is None:
        return None
    prefix = m.group(1)
    # fragment: "{prefix}_{local_name}" → prefix + "_" を除去
    expected_prefix = prefix + "_"
    if not fragment.startswith(expected_prefix):
        return None
    local_name = fragment[len(expected_prefix):]
    return (prefix, local_name)
```

検証例:
- `"../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales"` → `("jppfs_cor", "NetSales")`
- `"../jpcrp030000-asr_X99001-000_2025-11-01.xsd#jpcrp030000-asr_X99001-000_SomeCustomItem"` → `("jpcrp030000-asr_X99001-000", "SomeCustomItem")`
- パスの相対深度（`../`, `../../` 等）は `rsplit("/", 1)[-1]` で無視されるため影響しない

### 6.4a `_ns_to_prefix` の構築方針  <!-- R4-1 新設 -->

`resolve_clark()` が Clark notation（`{namespace_uri}local_name`）から prefix を逆引きするには `_ns_to_prefix: dict[str, str]` が必要。`_lab.xml` 内には namespace URI が存在しないため、参照先の XSD ファイルから `targetNamespace` を読み取って構築する。

**標準タクソノミの場合**:

`_lab.xml` パース時に `link:loc` の `xlink:href`（例: `../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales`）から XSD のパス部分を収集し、ユニークな XSD ごとに `targetNamespace` を読む。

```python
def _read_target_namespace(xsd_path: Path) -> str | None:
    """XSD ファイルの targetNamespace 属性を読み取る。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        targetNamespace の値。取得できなければ None。
    """
    try:
        tree = etree.parse(str(xsd_path))  # noqa: S320
        return tree.getroot().get("targetNamespace")
    except Exception:
        logger.debug("XSD の targetNamespace 読み取りに失敗: %s", xsd_path)
        return None
```

構築手順:
1. `_lab.xml` パース中に `link:loc` の `xlink:href` からユニークな XSD 相対パスを収集
2. 各 XSD パスを `_lab.xml` の親ディレクトリからの相対パスとして解決
3. `_read_target_namespace()` で `targetNamespace` を取得
4. `_extract_prefix_and_local()` で得た prefix と組み合わせて `{targetNamespace: prefix}` を登録

例:
- `_lab.xml`: `taxonomy/jppfs/2025-11-01/label/jppfs_2025-11-01_lab.xml`
- `xlink:href`: `../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales`
- 解決先: `taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd`
- `targetNamespace`: `http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor`
- 登録: `{"http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor": "jppfs_cor"}`

標準タクソノミ全体で参照される XSD はモジュールあたり 1〜2 個、合計 ~20 個程度。各 XSD の読み取りはルート要素の属性 1 つだけなので実質的なコストはゼロに等しい。

**提出者タクソノミの場合**:

`load_filer_labels()` は `_lab.xml` を bytes で受け取るため、`xlink:href` の相対パスをファイルシステム上で解決できない。提出者 XSD の `targetNamespace` を得るために、オプション引数 `xsd_bytes` を追加する:

```python
def load_filer_labels(
    self,
    lab_xml_bytes: bytes | None = None,
    lab_en_xml_bytes: bytes | None = None,
    *,
    xsd_bytes: bytes | None = None,  # R4-1 追加
) -> int:
```

`xsd_bytes` が渡された場合、`targetNamespace` を抽出して `_ns_to_prefix` に追加する。`xsd_bytes` が `None` の場合、prefix ベースの `resolve()` は機能するが、`resolve_clark()` は提出者拡張科目に対して FALLBACK を返す（`_ns_to_prefix` にエントリがないため）。これは許容可能なデグレーションであり、呼び出し側（Day 13 以降）が XSD bytes を渡せるようになった時点で完全動作する。

### 6.5 タクソノミファイルの探索

`ALL_20251101` のディレクトリ構造（C-1.a.md より）:

```
ALL_20251101/
  taxonomy/
    jppfs/2025-11-01/
      label/
        jppfs_2025-11-01_lab.xml       ← 日本語ラベル
        jppfs_2025-11-01_lab-en.xml    ← 英語ラベル
    jpcrp/2025-11-01/
      label/
        jpcrp_2025-11-01_lab.xml
        jpcrp_2025-11-01_lab-en.xml
    jpdei/2025-11-01/
      label/
        ...
```

**v0.1.0 での探索範囲**: `taxonomy/` 配下の全サブディレクトリを走査し、`label/` ディレクトリ内の `*_lab.xml` / `*_lab-en.xml` を全て読む。Glob パターン: `taxonomy/*/[0-9]*/label/*_lab.xml` + `taxonomy/*/[0-9]*/label/*_lab-en.xml`

### 6.6 キャッシュ戦略

PLAN.LIVING.md の指定に準拠:

```python
cache_path = (
    platformdirs.user_cache_dir("edinet")
    / f"taxonomy_labels_v{__version__}_{taxonomy_version}_{path_hash8}.pkl"
)
```

- `__version__`: ライブラリバージョン（`0.1.0`）。データ構造変更時にキャッシュ無効化
- `taxonomy_version`: タクソノミバージョン（`ALL_20251101`）。タクソノミ更新時にキャッシュ無効化
- `path_hash8`: `taxonomy_path` の SHA256 先頭 8 文字。異なるパスのタクソノミ混在時の誤ヒット防止
- ロード失敗時（pickle 互換性エラー等）は `warnings.warn()` で警告して再構築

キャッシュ対象: 標準タクソノミの `_standard_labels` と `_ns_to_prefix`（標準タクソノミ分）の両方。提出者ラベルは filing ごとに異なるためキャッシュしない。`_ns_to_prefix` をキャッシュに含めないと、キャッシュ復元後に `resolve_clark()` が全て FALLBACK になるサイレントバグが発生する。  <!-- R3-1 変更: _ns_to_prefix をキャッシュ対象に追加 -->

pickle のシリアライズ形式:
```python
# キャッシュデータ構造
cache_data = {
    "labels": _standard_labels,       # dict[_LabelKey, str]
    "ns_to_prefix": _ns_to_prefix,    # dict[str, str]（標準タクソノミ分のみ）
}
```

```python
import hashlib
import pickle
import time
import warnings
from pathlib import Path

import platformdirs

from edinet._version import __version__
from edinet.exceptions import EdinetWarning


def _cache_path(taxonomy_path: Path, taxonomy_version: str) -> Path:
    """キャッシュファイルのパスを構築する。"""
    path_hash = hashlib.sha256(str(taxonomy_path).encode()).hexdigest()[:8]
    cache_dir = Path(platformdirs.user_cache_dir("edinet"))
    return cache_dir / f"taxonomy_labels_v{__version__}_{taxonomy_version}_{path_hash}.pkl"


def _load_cache(path: Path) -> dict | None:
    """pickle キャッシュを読み込む。失敗時は None。"""
    if not path.exists():
        return None
    try:
        t0 = time.perf_counter()
        with path.open("rb") as f:
            data = pickle.load(f)  # noqa: S301
        elapsed = time.perf_counter() - t0
        # R3-5 注記: キャッシュ読み書きは logger.debug() ではなく logger.info() を使用する。
        # 既存モジュール（parser.py / contexts.py）は内部処理の詳細を debug で出力するが、
        # キャッシュの読み書きはユーザーが「なぜ遅い/速い」を理解するための状態変化であり
        # INFO が適切。方針: ライブラリ内部の処理詳細は debug、ユーザーに伝えるべき状態変化は info。
        logger.info("タクソノミキャッシュを読み込みました (%.3f秒, %s)", elapsed, path)
        return data
    except Exception:
        warnings.warn(
            f"タクソノミキャッシュの読み込みに失敗しました。再構築します: {path}",
            EdinetWarning,
            stacklevel=2,
        )
        return None


def _save_cache(data: dict, path: Path) -> None:
    """pickle キャッシュを保存する。失敗時は警告して続行。"""  # R4-2 修正: §6.9 の表と整合
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        with path.open("wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        elapsed = time.perf_counter() - t0
        logger.info("タクソノミキャッシュを保存しました (%.3f秒, %s)", elapsed, path)
    except Exception:
        warnings.warn(
            f"タクソノミキャッシュの保存に失敗しました: {path}",
            EdinetWarning,
            stacklevel=2,
        )
```

### 6.7 `_namespaces.py` の設計

```python
"""XBRL 関連の名前空間定数。

parser.py / contexts.py / taxonomy.py で共用する。
"""

# XBRL Instance
NS_XBRLI = "http://www.xbrl.org/2003/instance"
# XBRL Dimensions
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"
# XBRL Linkbase
NS_LINK = "http://www.xbrl.org/2003/linkbase"
# XLink
NS_XLINK = "http://www.w3.org/1999/xlink"
# XML Schema Instance
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
# XML (xml:lang 等の属性用)  <!-- R5-1 追加: parser.py の _NS_XML を集約 -->
NS_XML = "http://www.w3.org/XML/1998/namespace"
```

parser.py / contexts.py の変更:
- `_NS_XBRLI` / `NS_XBRLI` を `from edinet.xbrl._namespaces import NS_XBRLI` に置き換え
- `_namespaces.py` 自体が private モジュール（`_` prefix ファイル名）なので、中の定数は public name（`NS_XBRLI`）で統一する。parser.py で `import NS_XBRLI as _NS_XBRLI` のようなリネームは冗長なので行わず、そのまま `NS_XBRLI` を使用する  <!-- R4-4 追加: 命名方針を明示 -->
- 外部の振る舞いは一切変更なし（内部リファクタリングのみ）

### 6.8 `resolve_clark()` の実装

`RawFact.concept_qname` は Clark notation（`{http://...jppfs_cor}NetSales`）。namespace URI からの prefix 逆引きが必要:

```python
# namespace URI → prefix の逆引き辞書（_lab.xml パース時に構築）
_ns_to_prefix: dict[str, str]
# 例: {"http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor": "jppfs_cor"}

def resolve_clark(self, concept_qname: str, *, role=ROLE_LABEL, lang="ja") -> LabelInfo:
    # 入力バリデーション: Clark notation でなければ FALLBACK  <!-- R4-3 追加 -->
    if not concept_qname.startswith("{") or "}" not in concept_qname:
        return LabelInfo(text=concept_qname, role=role, lang=lang, source=LabelSource.FALLBACK)
    # "{http://...}NetSales" → namespace_uri, local_name に分解
    ns, local = concept_qname[1:].split("}", 1)
    prefix = self._ns_to_prefix.get(ns)
    if prefix is None:
        return LabelInfo(text=local, role=role, lang=lang, source=LabelSource.FALLBACK)
    return self.resolve(prefix, local, role=role, lang=lang)
```

namespace URI → prefix マッピングの構築には、`_lab.xml` 内の情報だけでは不十分である。`_lab.xml` の `link:loc` の `xlink:href` からは prefix と local_name は抽出できるが、namespace URI（例: `http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor`）は `_lab.xml` 内に存在しない。namespace URI は参照先 XSD の `targetNamespace` 属性に記載されているため、XSD ファイルを読む必要がある。詳細は §6.4a を参照。  <!-- R4-1 修正: 「自然に構築される」は誤り。XSD targetNamespace の読み取りが必要 -->

### 6.9 エラー処理方針

| 状況 | 処理 |
|---|---|
| `taxonomy_path` が存在しない | `EdinetConfigError`（コンストラクタ） |
| `taxonomy_path/taxonomy/` が存在しない | `EdinetConfigError`（コンストラクタ） |
| `_lab.xml` の XML パースエラー | `EdinetParseError` |
| `_lab.xml` 内に labelLink がない | 空辞書として処理（エラーにしない）。後続のモジュールの `_lab.xml` は正常かもしれない |
| `resolve()` でラベルが見つからない | フォールバック（`LabelSource.FALLBACK`）。エラーにしない |
| pickle キャッシュ読み込み失敗 | `EdinetWarning` を出して再構築 |
| pickle キャッシュ保存失敗 | `EdinetWarning` を出して続行（キャッシュなしで動作可能） |
| 提出者 `_lab.xml` の XML パースエラー | `EdinetParseError`（`load_filer_labels()` 内） |
| `labelArc` に `use="prohibited"` または `priority` 属性が出現 | `EdinetWarning` で通知して続行。v0.1.0 では arc override の完全処理は行わないが、検出は通知する  <!-- R5-FB2 追加 --> |
| `load_filer_labels()` を `_filer_labels` 非空の状態で呼び出し | `EdinetWarning` で `clear_filer_labels()` の呼び忘れを通知して続行（追加動作は継続）  <!-- R5-FB4 追加 --> |
| `load_filer_labels()` の `xsd_bytes` の XML パースエラー | `EdinetWarning` を出して `_ns_to_prefix` 未追加で続行。`resolve()` は機能するが `resolve_clark()` は該当提出者科目で FALLBACK になる（許容可能なデグレーション）  <!-- R6-5 追加 --> |

### 6.10 公開エクスポート方針

- `edinet.xbrl`（`__init__.py`）に `TaxonomyResolver` を追加エクスポート
- `LabelInfo`, `LabelSource`, `ROLE_LABEL`, `ROLE_VERBOSE`, `ROLE_TOTAL` は `edinet.xbrl.taxonomy` からの明示 import でのみ利用可能
- `taxonomy.py` に `__all__` を定義:

```python
__all__ = [
    "LabelInfo",
    "LabelSource",
    "TaxonomyResolver",
    "ROLE_LABEL",
    "ROLE_VERBOSE",
    "ROLE_TOTAL",
]
```

---

## 7. テスト計画

### 7.1 テストフィクスチャ: `tests/fixtures/taxonomy_mini/`

E-7.a.md の主要勘定科目辞書から ~20 concept を選び、最小限の `_lab.xml` / `_lab-en.xml` を作成する。

ディレクトリ構造:
```
tests/fixtures/taxonomy_mini/
  taxonomy/
    jppfs/2025-11-01/
      jppfs_cor_2025-11-01.xsd          ← XSD スタブ（targetNamespace のみ）
      label/
        jppfs_2025-11-01_lab.xml        ← 日本語ラベル（~20 concept）
        jppfs_2025-11-01_lab-en.xml     ← 英語ラベル（~20 concept）
```

注: XSD スタブは `_ns_to_prefix` 構築のために必要（R4-1）。`targetNamespace` 属性のみの最小ファイル（2 行）で十分。concept 定義や import は不要:  <!-- R4-1 修正: R2-2 の「XSD 不要」を撤回 -->

```xml
<xsd:schema targetNamespace="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema"/>
```

含める concept（E-7.a.md ベース）:
- BS: `CurrentAssets`, `Assets`, `CurrentLiabilities`, `Liabilities`, `NetAssets`
- PL: `NetSales`, `CostOfSales`, `GrossProfit`, `OperatingIncome`, `OrdinaryIncome`, `ProfitLoss`
- CF: `NetCashProvidedByUsedInOperatingActivities`, `CashAndCashEquivalents`
- その他: `CashAndDeposits`（BS 先頭科目）

各 concept に標準ラベル + 冗長ラベルを設定（実タクソノミと同じ構造）。加えて、少なくとも 1 concept（例: `Assets`）に `ROLE_TOTAL` の totalLabel も設定する（P1-2 `test_resolve_total_label` で使用）。  <!-- R6-8 追加: totalLabel フィクスチャ -->

提出者ラベル用フィクスチャ:
```
tests/fixtures/taxonomy_mini/
  filer/
    filer.xsd            ← XSD スタブ（targetNamespace のみ。load_filer_labels() の xsd_bytes テスト用）
    filer_lab.xml        ← 拡張科目 2-3 個のラベル
    filer_lab-en.xml
```

### 7.2 テストケース（P0: 必須）

1. `test_resolver_init_with_valid_path` — 正常パスで初期化成功。`taxonomy_version` が `"taxonomy_mini"` のようにディレクトリ名が取得されること
2. `test_resolver_init_raises_on_invalid_path` — 存在しないパスで `EdinetConfigError`
3. `test_resolve_japanese_standard_label` — `resolve("jppfs_cor", "NetSales")` → `LabelInfo(text="売上高", source=STANDARD)`
4. `test_resolve_english_standard_label` — `resolve("jppfs_cor", "NetSales", lang="en")` → `LabelInfo(text="Net sales", source=STANDARD)`
5. `test_resolve_verbose_label` — `resolve(..., role=ROLE_VERBOSE)` → 冗長ラベルが返ること
6. `test_resolve_fallback_to_standard_role` — 存在しない role を指定 → 標準ラベルにフォールバック
7. `test_resolve_fallback_to_local_name` — 存在しない concept → `LabelInfo(text="UnknownConcept", source=FALLBACK)`
8. `test_resolve_clark_notation` — `resolve_clark("{http://...jppfs_cor}NetSales")` → `resolve("jppfs_cor", "NetSales")` と同結果。このテストが pass するには XSD スタブの `targetNamespace` が `_ns_to_prefix` に正しく反映されていることが前提であり、`_ns_to_prefix` 構築の間接的検証も兼ねる  <!-- R6-6 追記: XSD スタブ依存の明示 -->
9. `test_load_filer_labels` — `load_filer_labels()` で提出者ラベルが追加されること。source=FILER
10. `test_filer_labels_take_priority` — 提出者ラベルが標準ラベルより優先されること
11. `test_clear_filer_labels` — `clear_filer_labels()` 後に提出者ラベルが消えること
12. `test_cache_saves_and_loads` — `use_cache=True` で 2 回目の初期化がキャッシュ読み込みになること。キャッシュファイルが存在するだけでなく、復元後の `resolve()` と `resolve_clark()` の結果がキャッシュなし時と同一であることを検証する（`_ns_to_prefix` のキャッシュ漏れ検出を含む）。`monkeypatch` で `platformdirs.user_cache_dir` を `tmp_path` に差し替え、テスト間のキャッシュ干渉を防止する  <!-- R3-4 + R4-5: キャッシュ復元検証 + monkeypatch 方針 -->
13. `test_cache_disabled` — `use_cache=False` でキャッシュファイルが作成されないこと
14. `test_resolve_clark_after_load_filer_labels` — `load_filer_labels()` 後に提出者拡張科目の Clark notation で `resolve_clark()` を呼び、`LabelSource.FILER` のラベルが返ること（`FALLBACK` にならないこと）。`_ns_to_prefix` への提出者 namespace 追加を検証する
15. `test_prefix_extraction_with_hyphen` — `jpcrp030000-asr` のようなハイフン入り prefix が `_extract_prefix_and_local()` で正しく抽出されること。§6.4 の `_XSD_PREFIX_RE` の検証

### 7.3 テストケース（P1: 推奨）

1. `test_resolve_multiple_modules` — jppfs + jpcrp 等、複数モジュールのラベルが解決可能
2. `test_resolve_total_label` — `ROLE_TOTAL` で合計ラベルが返ること
3. `test_load_filer_returns_count` — `load_filer_labels()` の返り値が追加ラベル数であること
4. `test_resolver_performance_cached` — キャッシュ読み込みが 1 秒以内であること（実タクソノミ使用、`@pytest.mark.large`）
5. `test_resolver_with_real_taxonomy` — 実タクソノミ `ALL_20251101` で初期化し、主要 concept のラベルが正しく解決されること（`@pytest.mark.large`）
6. `test_resolve_after_clear_and_reload` — `load_filer_labels()` → `clear_filer_labels()` → 再度 `load_filer_labels()` のサイクルが正しく動作すること（ステートマシンとしてのライフサイクル検証）
7. `test_multiple_roles_same_concept` — 同一 concept に標準ラベル + 冗長ラベル + 合計ラベルが共存する場合に、role 指定でそれぞれ正しく取得できること
8. `test_empty_lab_xml` — `labelLink` が存在しない空の `_lab.xml` をパースしてもエラーにならず、空辞書として処理されること（§6.9 のエラー処理方針の検証）  <!-- R3-6 追加: 空 _lab.xml テスト -->
9. `test_parse_lab_xml_loc_arc_label_connection` — 内部パースロジック `_parse_lab_xml()` の直接テスト。loc→arc→label の接続が正しく行われ、`xlink:label` 値ではなく `xlink:href` から concept が抽出されていることを検証する。loc の `xlink:label` に `_2` サフィックスが付くケース（同一 concept の重複参照）も含める  <!-- R5-8 追加: 内部パースの直接テスト -->
10. `test_prohibited_arc_warns` — `labelArc` に `use="prohibited"` を含む `_lab.xml` をパースした際に `EdinetWarning` が発行されること（`pytest.warns()` で検証）  <!-- R5-FB2 追加: prohibited 検出テスト -->
11. `test_load_filer_labels_warns_without_clear` — `load_filer_labels()` を 2 回連続で呼び出した際に `EdinetWarning` が発行されること（クリア忘れ検出）  <!-- R5-FB4 追加: クリア忘れ検出テスト -->

### 7.4 marker 方針

- `small` + `unit`: `taxonomy_mini` フィクスチャを使うテスト（P0 の大半）
- `medium` + `unit`: キャッシュ動作のテスト（tmpdir を使う）
- `large`: 実タクソノミを使う統合テスト（CI では除外）

---

## 8. 当日の作業手順

### Phase 0: _namespaces.py 切り出し（~10 分）

1. `src/edinet/xbrl/_namespaces.py` を作成（§6.7）
2. `contexts.py` の `NS_XBRLI`, `NS_XBRLDI` を `from edinet.xbrl._namespaces import ...` に変更。**`# Day 12 で集約` コメント（L31-32）も削除する**
3. `parser.py` の `_NS_XBRLI` 等を `from edinet.xbrl._namespaces import ...` に変更
4. `uv run pytest` で既存テスト全 pass を確認
5. `uv run ruff check src tests`

### Phase 1: フィクスチャ作成（~15 分）

1. **既存の `tests/fixtures/taxonomy_mini/jppfs/cor/` を削除する**（Day 10 以前の不要なスタブ。§7.1 の構造 `taxonomy/jppfs/2025-11-01/label/...` とは不整合のため）  <!-- R5-4 追加: 既存ディレクトリのクリーンアップ -->
2. `tests/fixtures/taxonomy_mini/` ディレクトリを §7.1 の構造で再作成
3. XSD スタブを作成（`targetNamespace` 属性のみの 2 行ファイル）。`_lab.xml` の `xlink:href` から相対パス解決できる位置に配置する  <!-- R4-1 追加 -->
4. `_lab.xml` / `_lab-en.xml` を作成（~20 concept 分）。実タクソノミの構造を参考に `link:loc` の `xlink:href` を実際と同じ形式にする（§6.4 の prefix 抽出ロジックの入力となるため）
5. 提出者ラベル用フィクスチャを作成（2-3 concept。ハイフン入り prefix を含める。XSD スタブも同梱）
6. `.gitignore` でフィクスチャが除外されていないことを確認

### Phase 2: テスト先行（~15 分）

1. `tests/test_xbrl/test_taxonomy.py` を作成
2. P0 テスト（§7.2）を先に書く（全て FAIL する状態）
3. フィクスチャの conftest.py にヘルパーを追加

### Phase 3: TaxonomyResolver 実装（~50 分）

1. `_lab.xml` パースロジックを実装（§6.4）
   - `link:loc` → `(prefix, local_name)` マッピング
   - `link:label` → `(role, lang, text)` マッピング
   - `link:labelArc` → 接続
   - XSD `targetNamespace` 読み取りによる `_ns_to_prefix` 構築（§6.4a）  <!-- R4-1 追加 -->
2. ファイル探索ロジックを実装（§6.5）
3. `resolve()` / `resolve_clark()` を実装（§6.3 アルゴリズム）
4. `load_filer_labels()` / `clear_filer_labels()` を実装
5. **ここまででキャッシュ関連以外の P0 テスト全 pass を確認する**（キャッシュなしで正しく動く状態を先に確保）  <!-- R3-7 追加: キャッシュ前のグリーン確認を明示 -->
6. キャッシュロジックを実装（§6.6）
7. P0 テスト全 pass を確認（キャッシュ関連テスト含む）

### Phase 4: 公開導線・品質（~15 分）

1. `xbrl/__init__.py` に `TaxonomyResolver` を追加
2. `uv run stubgen src/edinet --include-docstrings -o stubs`
3. `uv run ruff check src tests`
4. `uv run pytest` — 全テスト回帰なし
5. P1 テストを追加

### Phase 5: 手動スモーク（~10 分）

```python
from edinet.xbrl.taxonomy import TaxonomyResolver

resolver = TaxonomyResolver(r"C:\Users\nezow\Downloads\ALL_20251101")
print(f"Version: {resolver.taxonomy_version}")

# 主要科目のラベル確認
for concept in ["NetSales", "OperatingIncome", "Assets", "CashAndCashEquivalents"]:
    label = resolver.resolve("jppfs_cor", concept)
    print(f"  {concept}: {label.text} ({label.source.value})")

# 英語ラベル
for concept in ["NetSales", "ProfitLoss"]:
    label = resolver.resolve("jppfs_cor", concept, lang="en")
    print(f"  {concept} (en): {label.text}")

# キャッシュ効果の計測
import time
t0 = time.perf_counter()
resolver2 = TaxonomyResolver(r"C:\Users\nezow\Downloads\ALL_20251101")
print(f"2回目: {time.perf_counter() - t0:.3f}秒")

# モジュール間 XSD 参照の検証  <!-- R5-6 追加 -->
# jpcrp の _lab.xml が jppfs の concept を参照するケースで
# 相対パス（../../jppfs/...）が正しく解決されるか確認
for prefix, local in [("jpcrp_cor", "NetSales"), ("jppfs_cor", "Assets")]:
    label = resolver.resolve(prefix, local)
    print(f"  {prefix}:{local}: {label.text} ({label.source.value})")
```

---

## 9. 受け入れ基準

- `TaxonomyResolver` がタクソノミパスから初期化でき、`taxonomy_version` を返す
- `resolve()` が日本語/英語の標準ラベル・冗長ラベルを返す
- `resolve()` のフォールバック（指定 role → 標準ラベル → local name）が正しく動作する
- `resolve_clark()` が Clark notation から正しくラベルを解決する
- `load_filer_labels()` で提出者ラベルが追加され、`resolve()` で優先的に返される
- `clear_filer_labels()` で提出者ラベルがクリアされる
- pickle キャッシュが `platformdirs.user_cache_dir("edinet")` 配下に作成される
- 2 回目の初期化がキャッシュ読み込みで高速化される（1 秒以内を目安）
- `_namespaces.py` 切り出し後に既存テスト全 pass
- P0 テスト（§7.2）が全て pass
- `uv run ruff check src tests` で警告なし
- `.pyi` が生成されている

---

## 10. 実行コマンド

```bash
uv run pytest tests/test_xbrl/test_taxonomy.py -v
uv run pytest tests/test_xbrl/test_parser.py
uv run pytest tests/test_xbrl/test_contexts.py
uv run pytest
uv run ruff check src tests
uv run stubgen src/edinet --include-docstrings -o stubs
```

---

## 11. Day 13 への引き継ぎ

Day 12 完了後、Day 13 以降は以下を前提に着手する:

1. `TaxonomyResolver` が `resolve(prefix, local_name)` → `LabelInfo` を安定供給できる
2. `resolve_clark(concept_qname)` で `RawFact.concept_qname` から直接ラベルを解決できる
3. Day 13 は `RawFact` + `StructuredContext` + `TaxonomyResolver` → `LineItem` 変換を実装
4. `LineItem.label_ja` / `label_en` は `LabelInfo` 型で保持する（PLAN.LIVING.md Day 13 の指示）
5. Day 15 で `income_statement()` を組み立てる際、`TaxonomyResolver` はメソッド内で使用される
6. `load_filer_labels()` の呼び忘れ防止: `_filer_labels` が空でない状態で `load_filer_labels()` を呼ぶと `EdinetWarning` が発行される防御を Day 12 で実装済み（R5-FB4 で Day 12 に前倒し）。Day 13 で複数 filing を処理する導線を作る際は、`clear_filer_labels()` → `load_filer_labels()` の呼び出し順序を徹底すること  <!-- R5-FB4 変更: Day 12 実装済みに更新 -->

---

## 12. フィードバック反映記録

### Round 1

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| R1-1 | 設計 | `load_filer_labels()` が `_ns_to_prefix` を更新しない → `resolve_clark()` で提出者拡張科目が黙って FALLBACK になるサイレントバグ | §6.1 `load_filer_labels()` docstring に `_ns_to_prefix` 更新を明記。§6.3 内部データ構造に `_filer_ns_keys` を追加（clear 時の除去用）。§6.1 `clear_filer_labels()` docstring にも `_ns_to_prefix` エントリ除去を明記。§7.2 に P0-14 `test_resolve_clark_after_load_filer_labels` を追加 |

### Round 2

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| R2-1 | 設計 | §6.4 の prefix 抽出が概念のみで実装パスが曖昧。ハイフン入り prefix（`jpcrp030000-asr`）のエッジケースもカバーすべき | §6.4 に `_XSD_PREFIX_RE` 正規表現と `_extract_prefix_and_local()` の具体的な実装を追加。検証例にハイフン入りケースを含める |
| R2-2 | テスト | §7.1 の XSD スケルトンは `_lab.xml` パースに不要（XSD ファイルを実際に開かない） | §7.1 フィクスチャ構造から XSD を削除。「XSD 不要」の理由を注記。§8 Phase 1 からもスケルトン作成手順を削除。**⚠ R4-1 で撤回: `_ns_to_prefix` 構築に XSD `targetNamespace` 読み取りが必要と判明。XSD スタブ（2 行）をフィクスチャに復活** |
| R2-3 | スコープ | `load_filer_labels()` は bytes を受け取るが、ZIP から `_lab.xml` を抽出する導線が Day 12 スコープ外であることが不明確 | §3.2 非スコープに「ZIP からの `_lab.xml` 抽出は Day 13 以降」と明記 |
| R2-4 | テスト | ハイフン入り prefix テスト、ライフサイクルテスト、複数ロール同一 concept テストが不足 | §7.2 P0-15 `test_prefix_extraction_with_hyphen` を追加。§7.3 P1-6 `test_resolve_after_clear_and_reload`、P1-7 `test_multiple_roles_same_concept` を追加 |
| R2-5 | 軽微 | contexts.py L31-32 の `# Day 12 で集約` コメントを Phase 0 で確実に削除すべき | §8 Phase 0 手順 2 に明示的な削除指示を追加 |

### Round 3

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| R3-1 | 設計 | `_ns_to_prefix`（標準タクソノミ分）がキャッシュ対象外 → キャッシュ復元後に `resolve_clark()` が全て FALLBACK になるサイレントバグ | §6.6 キャッシュ対象を `_standard_labels` + `_ns_to_prefix` に拡張。pickle シリアライズ形式を `{"labels": ..., "ns_to_prefix": ...}` に変更 |
| R3-2 | 設計 | `_XSD_PREFIX_RE` の `(.+?)` 最小マッチはバックトラック依存で意図が暗黙的 | §6.4 正規表現を `(.+)_(\d{4}-\d{2}-\d{2})\.xsd$`（貪欲マッチ + 末尾固定）に変更し、コメントに意図を明記 |
| R3-3 | 設計 | `resolve()` の role フォールバック時に `lang` が引き継がれることが明記されていない | §6.3 アルゴリズムのステップ 3 に「`lang` を変更せず再実行」を追記 |
| R3-4 | テスト | P0-12 `test_cache_saves_and_loads` がキャッシュファイルの存在確認のみで、復元後のラベル一致を検証していない（R3-1 のバグを検出できない） | P0-12 を拡張し、キャッシュ復元後に `resolve()` と `resolve_clark()` の結果が同一であることを検証 |
| R3-5 | 設計 | §6.6 のキャッシュコードが `logger.info()` を使用しているが、既存モジュール（parser.py / contexts.py）は `logger.debug()` で不整合 | logging レベル方針を §6.6 に注記。ライブラリ内部処理は `debug`、ユーザーに伝えるべき状態変化（キャッシュ読み書き）は `info` |
| R3-6 | テスト | §6.9 に「labelLink がない → 空辞書」と明記されているが対応テストがない | §7.3 P1-8 `test_empty_lab_xml` を追加 |
| R3-7 | 手順 | Phase 3 のキャッシュ実装を最後に回すことが暗黙的で、テストの通し方が曖昧 | §8 Phase 3 にキャッシュ前のグリーン確認ステップ（手順 5）を明示的に追加 |
| R3-8 | 確認 | `platformdirs` が pyproject.toml に含まれているか → 確認済み。L10 に `"platformdirs>=4.0"` が存在 | 対応不要 |

### Round 4

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| R4-1 | 設計 | `_ns_to_prefix` の構築メカニズムが未定義。`_lab.xml` 内に namespace URI は存在せず、「自然に構築される」（旧§6.8）は誤り。XSD `targetNamespace` の読み取りが必要 | §6.4 末尾の誤記述を修正。§6.4a を新設し XSD `targetNamespace` 読み取り方針を具体化。`load_filer_labels()` に `xsd_bytes` パラメータを追加。§7.1 フィクスチャに XSD スタブ（2 行）を追加（R2-2 の「XSD 不要」判断を撤回）。§8 Phase 1 に XSD スタブ作成手順を追加 |
| R4-2 | 設計 | `_save_cache` の実装コードに try/except がなく、§6.9 のエラー処理表（「保存失敗 → EdinetWarning で続行」）と矛盾。読み取り専用環境でクラッシュする | §6.6 の `_save_cache` コードに try/except + `EdinetWarning` を追加 |
| R4-3 | 設計 | `resolve_clark()` の入力バリデーション不足。Clark notation でない文字列で不可解なエラーになる | §6.8 の `resolve_clark()` 冒頭に `startswith("{")` / `"}" in` のガードを追加。不正入力は FALLBACK を返す |
| R4-4 | 設計 | `_namespaces.py` 切り出し時に定数名を private (`_NS_XBRLI`) にするか public (`NS_XBRLI`) にするかが未明示 | §6.7 に方針を追記。`_namespaces.py` は private モジュールなので中身は public name で統一。parser.py でのリネームは不要 |
| R4-5 | テスト | P0-12 `test_cache_saves_and_loads` で `use_cache=True` 時に実キャッシュディレクトリに書き込まれ、テスト間干渉が発生する | P0-12 に `monkeypatch` で `platformdirs.user_cache_dir` を `tmp_path` に差し替える旨を追記 |
| R4-6 | 引き継ぎ | `load_filer_labels()` を `clear_filer_labels()` なしで 2 回連続呼び出すと前の filing のラベルが残る。ユーザーが忘れやすい | §11 Day 13 引き継ぎに防御的 `warnings.warn()` の検討を記載。Day 12 スコープ外 |
| R4-7 | 設計 | `_LabelKey` 型エイリアスが docstring 内説明かモジュールレベル定義か曖昧 | §6.3 を Python 3.12+ の `type` 文に変更して明示化 |

### Round 5

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| R5-1 | 設計 | `_namespaces.py` の定数リストに `NS_XML`（`xml:lang` 属性用）が漏れている。parser.py の `_NS_XML` を集約するなら含めるべき | §6.7 に `NS_XML = "http://www.w3.org/XML/1998/namespace"` を追加 |
| R5-3 | スコープ | `resolve()` の role フォールバック時に lang 方向のフォールバック（例: 英語 totalLabel がない → 日本語 totalLabel）を行わない仕様の非スコープ明記 | §3.2 非スコープに lang フォールバック非対応を追記。C-5.6 で標準タクソノミは日英完全一致のため実害なし |
| R5-4 | テスト | `tests/fixtures/taxonomy_mini/jppfs/cor/`（Day 10 以前の不要スタブ）が §7.1 の構造と不整合 | §8 Phase 1 冒頭に既存ディレクトリのクリーンアップ手順を追加 |
| R5-5 | 設計 | §6.4 パース手順で `link:loc` の `xlink:label` 値そのものからではなく `xlink:href` から concept を抽出すべきことが暗黙的。同一 concept の重複参照時に `_2` サフィックスが付く点も要注意 | §6.4 パース手順 1 に注意書きを追加。擬似コード `_parse_lab_xml()` を具体化して loc→arc→label 接続の正確さを明示 |
| R5-6 | テスト | モジュール間の相互参照（jpcrp の `_lab.xml` が jppfs の XSD を `../../jppfs/...` で参照するケース）で相対パス解決が正しく動くか未検証 | §8 Phase 5 スモークテストにモジュール間 XSD 参照の検証項目を追加 |
| R5-8 | テスト | P0 テストが全て公開 API 経由で、内部の loc→arc→label 接続ロジックの直接テストがない | §7.3 P1-9 `test_parse_lab_xml_loc_arc_label_connection` を追加 |
| R5-FB2 | 設計 | `prohibited` / `priority` を v0.1.0 で省略する判断は妥当だが、検出時に warning を出さないとサイレントな誤ラベル化のリスクがある | §3.2 非スコープの prohibited 行に検出時 warning を追記。§4 C-5.4 行を修正。§6.4 パース手順 3 に prohibited/priority 検出を追加。§6.9 エラー処理表に行追加。§7.3 P1-10 `test_prohibited_arc_warns` を追加 |
| R5-FB4 | 設計 | `clear_filer_labels()` 必須の手動ライフサイクルは利用者ミスを誘発。R4-6 で Day 13 送りだった防御を Day 12 に前倒しすべき | §6.2 設計判断 4 に `_filer_labels` 非空時の `EdinetWarning` を追記。§6.1 `load_filer_labels()` docstring に Warns を追加。§6.9 エラー処理表に行追加。§7.3 P1-11 `test_load_filer_labels_warns_without_clear` を追加。§11 引き継ぎを「Day 12 実装済み」に更新 |

**不採用:**

| ID | 出典 | 不採用理由 |
|---|---|---|
| R5-2 | セット1 | `_LabelKey` の `type` 文が Python 3.12+ 限定との指摘だが、`pyproject.toml` で `requires-python = ">=3.12"` のため問題なし |
| R5-7 | セット1 | pickle protocol を 5 に固定すべきとの指摘だが、同上の理由で `HIGHEST_PROTOCOL` で問題なし |
| セット2-1 | セット2 | `resolve()` の主 API を `namespace_uri + local_name` にすべきとの提案。`_lab.xml` 内に namespace URI は存在せず（R4-1 確認済み）、ラベル辞書のキーは必然的に prefix ベース。namespace_uri を主 API にすると全呼び出しで `_ns_to_prefix` 逆引きが必須になり複雑化する。Clark notation からの解決は `resolve_clark()` で提供済み。§6.2 設計判断 1 の判断を維持 |
| セット2-3 | セット2 | キャッシュキーに mtime/manifest hash を追加すべきとの提案。タクソノミは金融庁が年 1 回公開する公式パッケージで同一パス内の内容差し替えは想定外。mtime 集約は全 `_lab.xml` スキャンが必要で 50ms 目標を毀損する。万一の更新時は `use_cache=False` で対応可能。過剰防御として見送り |

### Round 6

| ID | カテゴリ | 内容 | 対応 |
|---|---|---|---|
| R6-1 | 設計 | §6.4 擬似コードの `label_map` が 1:1 マッピングで、後勝ち上書きのリスクがあるとの指摘。ただし実タクソノミ確認で `link:label` の `xlink:label` は同一 `labelLink` 内で 100% ユニーク（13,308 個中重複なし）。1 つの loc に複数 arc が接続されるが、各 arc の `xlink:to` は異なる label キーを指すため `label_map` のキー衝突は発生しない | §6.4 擬似コードの前提として実データ確認結果をコメントに追記。データ構造の変更は不要 |
| R6-2 | 設計 | `root.iter()` で全 `link:loc` / `link:label` / `link:labelArc` をフラット収集すると、複数 `labelLink` が存在する場合に `xlink:label` キーが衝突する可能性があるとの指摘。実タクソノミ全モジュールで `labelLink` は 1 つのみ（確認済み）。提出者タクソノミでも通常 1 つ | §6.4 擬似コードの前提に「labelLink は通常 1 つ」を明記。v0.2.0 で labelLink 単位処理に切り替える余地を残す旨を追記 |
| R6-3 | 設計 | `_LabelKey` の `type` 文がモジュールレベル定義かクラス内定義か不明確 | §6.3 のコメントに「モジュールレベル定義、`__all__` には含めない（内部型）」を追記 |
| R6-5 | 設計 | `load_filer_labels()` の `xsd_bytes` パースエラーが §6.9 エラー処理表に未記載 | §6.9 に「`xsd_bytes` パースエラー → `EdinetWarning` + `_ns_to_prefix` 未追加で続行」を追加 |
| R6-6 | テスト | P0-8 `test_resolve_clark_notation` が XSD スタブの `targetNamespace` に暗黙的に依存している | P0-8 の記述に「XSD スタブの `_ns_to_prefix` 反映の間接的検証でもある」旨を注記 |
| R6-7 | 設計 | `_parse_lab_xml` のログレベルが未定義。パース概要は info か debug か | §6.4 に logging 方針を追記。パース概要（ラベル件数等）は `info`、個別の loc/arc 処理は `debug`。擬似コード末尾に `logger.info()` を追加 |
| R6-8 | テスト | §7.1 のフィクスチャに `ROLE_TOTAL` の totalLabel が含まれていない。P1-2 `test_resolve_total_label` が動かない | §7.1 に「少なくとも 1 concept に totalLabel を設定」を追記 |

**不採用:**

| ID | 出典 | 不採用理由 |
|---|---|---|
| R6-4 | Round 6 | Glob パターン `taxonomy/*/[0-9]*/label/*_lab.xml` が common モジュールにマッチする懸念。実タクソノミで確認した結果、common モジュールには `_lab.xml` が存在せず（`.xsd` のみ）、`label/` ディレクトリ自体がないため空振りする。対応不要 |

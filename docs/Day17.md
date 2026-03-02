# Day 17 — E2E 統合（`Filing.xbrl()` + `Company.latest()`）

## 0. 位置づけ

Day 17 は、Day 9〜16 で個別に構築した全モジュールを **1 本のパイプラインに繋ぐ** 日。
PLAN.LIVING.md の Day 17:

> **Day 17 (2h) — E2E 統合 ★最重要マイルストーン**
> - Filing.xbrl() メソッド: ZIP展開 → パース → ラベル解決 → Statement 組み立てを繋ぐ
> - Company.latest() メソッド追加
> - [パフォーマンス] E2E の所要時間を計測
> - [注意] 各接続点でデータの型が一致しているか確認

Day 16 完了時点の状態:
- `parse_xbrl_facts()` → `ParsedXBRL`（RawFact + RawContext + RawUnit）
- `structure_contexts()` → `dict[str, StructuredContext]`
- `TaxonomyResolver` → concept → `LabelInfo` のラベル解決
- `build_line_items()` → `tuple[LineItem, ...]`
- `build_statements()` → `Statements`（`income_statement()`, `balance_sheet()`, `cash_flow_statement()`）
- `FinancialStatement`: `__str__`, `__rich_console__`, `to_dataframe()`, `to_dict()` 実装済み
- `Filing.fetch()` → `(xbrl_path, xbrl_bytes)` 実装済み
- `Company.get_filings()` → `list[Filing]` 実装済み
- `extract_zip_member()`, `list_zip_members()` — ZIP からの任意ファイル抽出が可能
- `TaxonomyResolver.load_filer_labels()` — 提出者別ラベルの追加読み込みが可能
- `configure(taxonomy_path=...)` — タクソノミパスのグローバル設定が可能
- pytest 472/476 collected（4 deselected = large テスト）、ruff Clean

Day 17 完了時のマイルストーン:

```python
from edinet import Company, configure

configure(api_key="...", taxonomy_path=r"C:\Users\nezow\Downloads\ALL_20251101")

toyota = Company(edinet_code="E02144", name_ja="トヨタ自動車株式会社", sec_code="72030")

# Company.latest() で最新の有報を取得
filing = toyota.latest("有価証券報告書")

# Filing.xbrl() で ZIP → パース → ラベル → Statement を一気通貫
stmts = filing.xbrl()

# PL
pl = stmts.income_statement()
print(pl)
df = pl.to_dataframe()

# BS
bs = stmts.balance_sheet()
print(bs)

# CF
cf = stmts.cash_flow_statement()
print(cf)

# Statements 一括表示（Day 16 で __str__ 追加済み）
print(stmts)
```

---

## 1. 現在実装の確認結果

| ファイル | 現状 | Day 17 で必要な変更 |
|---|---|---|
| `src/edinet/models/filing.py` | ~370行。`fetch()` / `afetch()` 実装済み。`_zip_cache` / `_xbrl_cache` あり。`xbrl()` なし | `xbrl()` / `axbrl()` メソッドを追加 |
| `src/edinet/models/company.py` | ~115行。`get_filings()` 実装済み。`latest()` なし | `latest()` メソッドを追加 |
| `src/edinet/api/download.py` | ~300行。`extract_zip_member()`, `list_zip_members()` 実装済み | 変更なし |
| `src/edinet/xbrl/__init__.py` | 全パイプライン関数のエクスポート完了 | 変更なし |
| `src/edinet/_config.py` | `taxonomy_path: str | None` フィールドあり | 変更なし |
| `tests/test_models/test_filing.py` | `fetch()` のテスト実装済み | `xbrl()` のテストを追加 |
| `tests/test_models/test_company.py` | `get_filings()` のテスト実装済み | `latest()` のテストを追加 |
| `tools/day14_integration.py` | `find_filer_taxonomy_files()` で ZIP から提出者ファイルを抽出するパターンが確立 | `Filing.xbrl()` がこのパターンを内蔵する |
| `stubs/edinet/models/filing.pyi` | 177行。`xbrl()` なし | stubgen で再生成 |
| `stubs/edinet/models/company.pyi` | 43行。`latest()` なし | stubgen で再生成 |

補足:
- `Filing` は `ConfigDict(frozen=True)` の Pydantic BaseModel。メソッド追加は frozen 制約と矛盾しない（フィールドを変更しないため）
- `Filing._zip_cache` は `fetch()` で取得した ZIP bytes をキャッシュする。`xbrl()` はこのキャッシュを再利用できる
- `tools/day14_integration.py` の `find_filer_taxonomy_files()` は PublicDoc 内の `_lab.xml`, `_lab-en.xml`, `.xsd` を探索するロジック。これを `Filing.xbrl()` 内に取り込む
- `Company` も `ConfigDict(frozen=True)` なのでメソッド追加のみ。新フィールドは不要

---

## 2. ゴール

1. `Filing.xbrl()` — ZIP 展開 → パース → ラベル解決 → Statement 組み立てを繋ぐメソッド
2. `Filing.axbrl()` — `xbrl()` の非同期版
3. `Company.latest()` — `get_filings()` を使って最新の Filing を返すメソッド
4. E2E テスト — 上記が正しく動くことを Unit / Medium テストで検証
5. 手動スモーク — 実 filing でゴールコードが動くことを確認

**Day 17 の核心**: 新規のビジネスロジックはほぼゼロ。既存モジュールの**接続**が主作業。各接続点でデータの型が一致しているかの確認が最重要。

---

## 3. スコープ / 非スコープ

### 3.1 Day 17 のスコープ

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| D17-1 | Filing.xbrl() | ZIP → parse → labels → statements のパイプラインメソッド | PLAN.LIVING.md Day 17 |
| D17-2 | Filing.axbrl() | xbrl() の非同期版 | async_support 方針（FEATURES.md） |
| D17-3 | Company.latest() | 最新 Filing の取得 | PLAN.LIVING.md Day 17 |
| D17-4 | 提出者ラベル抽出 | ZIP 内の `_lab.xml` / `_lab-en.xml` / `.xsd` の自動抽出 | Filing.xbrl() の内部ステップ |
| D17-5 | taxonomy_path の自動解決 | `configure(taxonomy_path=...)` から自動取得 | E2E の利便性 |
| D17-6 | E2E テスト | Filing.xbrl(), Company.latest() の Unit/Medium テスト | PLAN.LIVING.md Day 17 |
| D17-7 | doc_type 日本語マッチング | `_normalize_doc_type()` で日本語文字列（`"有価証券報告書"` 等）を受け付ける | ゴールコード `latest("有価証券報告書")` を動かすため |

### 3.2 Day 17 でやらないこと

| # | カテゴリ | 内容 | やらない理由 |
|---|---------|------|-------------|
| D17N-1 | Company コンストラクタの糖衣構文 | `Company("7203")` でティッカーから構築 | PLAN.LIVING.md §6 注記: v0.2.0 で CSV ベースの検索を実装。Day 17 は `Company(edinet_code=...)` 直指定 |
| D17N-2 | xbrl() の結果キャッシュ | `_statements_cache` でパース結果を保持 | v0.1.0 では毎回パースで十分。キャッシュは v0.2.0 で検討（§4.9） |
| D17N-3 | iXBRL (Inline XBRL) 対応 | `.htm` / `.xhtml` のパース | PLAN.LIVING.md §5: v0.1.0 は従来型 XBRL のみ。K-2 参照 |
| D17N-4 | TaxonomyResolver の自動構築 | taxonomy_path なしでも動くフォールバック | タクソノミパスは利用者が明示的に指定する設計。自動ダウンロードは v0.2.0 |
| D17N-5 | Company.filings プロパティ | `company.filings` で過去全Filing を遅延取得 | FEATURES.md company/filings → v0.2.0。`get_filings()` で十分 |
| D17N-6 | 訂正報告書のチェーン解決 | `filing.latest()` で最終版を返す | FEATURES.md revision_chain → v0.2.0 |
| D17N-7 | Filing.__repr__ の更新 | xbrl() 追加に伴う repr の変更 | 既存の Pydantic 由来の repr で十分 |
| D17N-8 | DEI 要素の自動抽出 | 会計基準の判定等 | FEATURES.md dei → v0.2.0。v0.1.0 は J-GAAP 前提 |
| D17N-9 | Large テスト | 実 EDINET API を叩く E2E テスト | Day 18 のスコープ |
| D17N-10 | パフォーマンス計測の自動化 | ベンチマークスクリプト | 手動スモークで計測。CI 組み込みは Day 18+ |

---

## 4. `Filing.xbrl()` の設計

### 4.1 シグネチャ

```python
def xbrl(self, *, taxonomy_path: str | None = None) -> Statements:
    """XBRL を解析し財務諸表コンテナを返す。

    ZIP ダウンロード → XBRL パース → Context 構造化 → ラベル解決 →
    LineItem 生成 → Statement 組み立てのフルパイプラインを実行する。

    Args:
        taxonomy_path: EDINET タクソノミのルートパス
            （例: ``"/path/to/ALL_20251101"``）。
            省略時は ``configure(taxonomy_path=...)`` で設定された値を使用する。

    Returns:
        Statements コンテナ。``income_statement()`` / ``balance_sheet()`` /
        ``cash_flow_statement()`` でアクセスする。

    Raises:
        EdinetAPIError: 当該書類に XBRL が無い場合。
        EdinetConfigError: taxonomy_path が未設定の場合。
        EdinetParseError: XBRL パースに失敗した場合。
        EdinetError: 通信層の失敗。

    Note:
        v0.1.0 は **J-GAAP の一般事業会社** のみ対応。IFRS / US-GAAP 企業の
        XBRL を渡した場合、科目がマッチせず空または不完全な Statement が返り、
        ``UserWarning`` を発行する。スレッドセーフではない。

    Examples:
        >>> filing = documents("2025-06-25", doc_type="120")[0]
        >>> stmts = filing.xbrl()
        >>> pl = stmts.income_statement()
        >>> print(pl)
    """
```

### 4.2 実装

```python
def xbrl(self, *, taxonomy_path: str | None = None) -> Statements:
    # 1. taxonomy_path の解決
    resolved_taxonomy_path = self._resolve_taxonomy_path(taxonomy_path)

    # 2. XBRL bytes の取得（fetch() のキャッシュを活用）
    xbrl_path, xbrl_bytes = self.fetch()

    # 3〜8. パイプライン実行（IFRS/US-GAAP 検知の警告もここで発行）
    stmts = self._build_statements(resolved_taxonomy_path, xbrl_path, xbrl_bytes)

    return stmts
```

### 4.3 `Filing.axbrl()` — 非同期版

```python
async def axbrl(self, *, taxonomy_path: str | None = None) -> Statements:
    """XBRL を非同期で解析し財務諸表コンテナを返す。

    ``xbrl()`` の非同期版。ネットワーク I/O（ZIP ダウンロード）のみ
    非同期で、パース処理は同期的に実行する。

    Args:
        taxonomy_path: EDINET タクソノミのルートパス。
            省略時は ``configure(taxonomy_path=...)`` で設定された値を使用する。

    Returns:
        Statements コンテナ。

    Raises:
        EdinetAPIError: 当該書類に XBRL が無い場合。
        EdinetConfigError: taxonomy_path が未設定の場合。
        EdinetParseError: XBRL パースに失敗した場合。
        EdinetError: 通信層の失敗。
    """
    # 1. taxonomy_path の解決
    resolved_taxonomy_path = self._resolve_taxonomy_path(taxonomy_path)

    # 2. XBRL bytes の取得（afetch() で非同期ダウンロード）
    xbrl_path, xbrl_bytes = await self.afetch()

    # 3〜8. パイプライン実行（IFRS/US-GAAP 検知の警告もここで発行）
    stmts = self._build_statements(resolved_taxonomy_path, xbrl_path, xbrl_bytes)

    return stmts
```

### 4.3b `Filing._resolve_taxonomy_path()` — taxonomy_path 解決

```python
def _resolve_taxonomy_path(self, taxonomy_path: str | None) -> str:
    """taxonomy_path を解決する。引数 > configure() の優先順位。

    Args:
        taxonomy_path: 明示指定されたパス。None の場合は configure() から取得。

    Returns:
        解決されたタクソノミパス。

    Raises:
        EdinetConfigError: どちらも未設定の場合。
    """
    from edinet._config import get_config
    from edinet.exceptions import EdinetConfigError

    resolved = taxonomy_path or get_config().taxonomy_path
    if resolved is None:
        raise EdinetConfigError(
            "taxonomy_path is required. "
            "Pass it to xbrl(taxonomy_path=...) or "
            "set it globally with configure(taxonomy_path=...)."
        )
    return resolved
```

### 4.3c `Filing._build_statements()` — パイプライン本体

```python
def _build_statements(
    self,
    taxonomy_path: str,
    xbrl_path: str,
    xbrl_bytes: bytes,
) -> Statements:
    """ZIP キャッシュからパイプラインを実行する（同期）。

    xbrl() / axbrl() の共通パイプライン。I/O 完了後の
    ステップ 3〜8 を担当する。警告（ステップ 9）は呼び出し元で行う。

    Args:
        taxonomy_path: 解決済みタクソノミパス。
        xbrl_path: XBRL ファイルのパス（トレース用）。
        xbrl_bytes: XBRL ファイルのバイト列。

    Returns:
        Statements コンテナ。

    Raises:
        EdinetParseError: パイプラインの各ステップで失敗した場合。
    """
    import logging

    from edinet.exceptions import EdinetError, EdinetParseError
    from edinet.xbrl import (
        TaxonomyResolver,
        build_line_items,
        build_statements,
        parse_xbrl_facts,
        structure_contexts,
    )

    logger = logging.getLogger(__name__)

    try:
        # 3. 提出者タクソノミファイルの抽出
        filer_files = _extract_filer_taxonomy_files(self._zip_cache)

        # 4. XBRL パース
        # TODO(v0.2.0): iXBRL の場合は parse_ixbrl_facts() に分岐
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        logger.debug("step 4: parsed %d facts, %d contexts", len(parsed.facts), len(parsed.contexts))

        # 4b. J-GAAP 名前空間チェック（IFRS/US-GAAP 検知）
        #     is_all_empty() ではなく namespace で判定する理由:
        #     extras 収集により IFRS 科目も FinancialStatement に含まれるため
        #     is_all_empty() は False を返し、警告が発火しない（Rev.5 P1-1）
        namespaces = {
            f.concept_qname.split("}")[0]
            for f in parsed.facts
            if "}" in f.concept_qname
        }
        if not any("jppfs" in ns for ns in namespaces):
            import warnings

            warnings.warn(
                f"Filing {self.doc_id}: jppfs_cor 名前空間の Fact がありません。"
                "IFRS / US-GAAP の Filing は v0.1.0 では未対応です。",
                stacklevel=3,  # user → xbrl()/axbrl() → _build_statements()
            )

        # 5. Context 構造化
        ctx_map = structure_contexts(parsed.contexts)
        logger.debug("step 5: structured %d contexts", len(ctx_map))

        # 6. ラベル解決
        resolver = TaxonomyResolver(taxonomy_path)
        resolver.load_filer_labels(
            lab_xml_bytes=filer_files.get("lab"),
            lab_en_xml_bytes=filer_files.get("lab_en"),
            xsd_bytes=filer_files.get("xsd"),
        )

        # 7. LineItem 生成
        items = build_line_items(parsed.facts, ctx_map, resolver)
        logger.debug("step 7: built %d line items", len(items))

        # 8. Statement 組み立て
        stmts = build_statements(items)
    except EdinetError:
        raise
    except Exception as exc:
        raise EdinetParseError(
            f"Filing {self.doc_id}: unexpected error in XBRL pipeline"
        ) from exc

    return stmts
```

### 4.4 `_extract_filer_taxonomy_files()` — 提出者タクソノミ抽出

```python
def _extract_filer_taxonomy_files(zip_bytes: bytes | None) -> dict[str, bytes]:
    """ZIP 内から提出者別タクソノミファイルを抽出する。

    PublicDoc 配下の ``_lab.xml``（日本語ラベル）、``_lab-en.xml``（英語ラベル）、
    ``.xsd``（スキーマ、監査報告書を除く）を探索して返す。

    Args:
        zip_bytes: ZIP のバイト列。None の場合は空辞書を返す。

    Returns:
        キーが ``"lab"`` / ``"lab_en"`` / ``"xsd"``、値が bytes の辞書。
        対応するファイルが存在しない場合はキーが含まれない。
    """
    if zip_bytes is None:
        return {}

    import logging

    from edinet.api.download import extract_zip_member, list_zip_members

    logger = logging.getLogger(__name__)
    members = list_zip_members(zip_bytes)
    result: dict[str, bytes] = {}

    for name in members:
        lower = name.lower()
        if "publicdoc/" not in lower.replace("\\", "/"):
            continue
        # PublicDoc/ 内の監査報告書 XSD（jpaud_...xsd 等）を除外する。
        # AuditDoc/ 配下は上の publicdoc チェックで既に除外済み。
        if lower.endswith("_lab.xml") and "_lab-en" not in lower:
            if "lab" not in result:  # 先勝ち（XSD と統一）
                result["lab"] = extract_zip_member(zip_bytes, name)
        elif lower.endswith("_lab-en.xml"):
            if "lab_en" not in result:  # 先勝ち
                result["lab_en"] = extract_zip_member(zip_bytes, name)
        elif lower.endswith(".xsd") and "audit" not in lower:
            if "xsd" not in result:  # 先勝ち
                result["xsd"] = extract_zip_member(zip_bytes, name)

    logger.debug("filer taxonomy files found: %s", list(result.keys()))
    return result
```

### 4.5 `_extract_filer_taxonomy_files()` の配置

`_extract_filer_taxonomy_files()` は `src/edinet/models/filing.py` のモジュールレベル関数として定義する。理由:
- `Filing.xbrl()` と `Filing.axbrl()` の両方から使う
- ZIP の構造知識（PublicDoc、ファイルサフィックスの命名規則）はダウンロードモジュールの責務に近いが、`download.py` は汎用的な ZIP 操作に特化しており、XBRL 固有のセマンティクス（`_lab.xml` がラベルファイルであること等）は持たない
- `Filing` がパイプラインを統合するオーケストレーターとして、この知識を持つのが自然

### 4.6 設計判断

1. **`TaxonomyResolver` を毎回 new する理由**: `TaxonomyResolver` は pickle キャッシュを持つため、2 回目以降のインスタンス化は ~50ms（Day 12 実装）。`Filing` に resolver を保持すると frozen model を崩す。`clear_filer_labels()` の呼び忘れリスクも回避できる。毎回 new + `load_filer_labels()` の方がステートレスで安全
2. **`_zip_cache` の再利用**: `self.fetch()` が `_zip_cache` を設定済みなので、`_extract_filer_taxonomy_files()` は追加のダウンロードなしで ZIP からファイルを抽出できる。`_zip_cache` は `Filing` の private 属性であり、モジュール内からのアクセスは正当
3. **taxonomy_path の引数優先**: `xbrl(taxonomy_path=...)` > `configure(taxonomy_path=...)` の優先順位。利用者が異なるバージョンのタクソノミで試したいケースに対応。ただし大半のケースでは `configure()` で一度設定すれば済む
4. **`xbrl()` がキャッシュしない理由**: `xbrl()` の戻り値 `Statements` はイミュータブル（frozen dataclass）だが、Filing の frozen model にキャッシュフィールドを追加すると `object.__setattr__` が必要になり、型チェッカーとの整合性が悪化する。`fetch()` は ZIP ダウンロード（高コスト I/O）をキャッシュしているため、`xbrl()` の再呼び出しコストは CPU パース処理（~100ms）のみ。v0.2.0 でプロファイル結果に基づいてキャッシュを検討する（D17N-2）
5. **パイプラインを `_build_statements()` に抽出する理由**: `xbrl()` と `axbrl()` の I/O 後のステップ 3〜9 が完全に同一であるため、`_build_statements()` プライベートメソッドに抽出する。v0.2.0 で iXBRL 分岐や DEI 抽出が追加された際に 2 箇所の同期が不要になる。`_build_statements()` 内部のステップはフラットに記述し、(a) デバッガでのステップ実行が容易、(b) フック挿入の容易さ を維持する。`_resolve_taxonomy_path()` も同様に共通化する
6. **`_extract_filer_taxonomy_files()` が `zip_bytes: None` を許容する理由**: `fetch()` が `_zip_cache` を設定するため通常は None にならないが、テスト時に `_xbrl_cache` を直接設定して `fetch()` をスキップするパターンで `_zip_cache` が None になりうる。defensive coding として空辞書を返す（提出者ラベルなしでもパイプラインは動く。標準ラベルのみで解決される）
7. **`axbrl()` のステップ 3〜8 が同期な理由**: XBRL パース、Context 構造化、ラベル解決、LineItem 生成、Statement 組み立てはすべて CPU バウンド処理。`asyncio.to_thread()` でオフロードする代替案はあるが、v0.1.0 では処理時間が ~100ms のため不要。大量 Filing の並列処理（v0.2.0）で必要になれば追加する
8. **`_extract_filer_taxonomy_files()` で全ファイルを先勝ちにする理由**: ZIP 内には監査報告書の XSD も含まれうる。`"audit" not in lower` でフィルタし、最初にマッチした非 audit XSD を採用する。`_lab.xml` / `_lab-en.xml` も同様に先勝ち（`if key not in result:`）で統一する。EDINET の ZIP 構造では提出者の主 XSD / `_lab.xml` は各 1 ファイル（B-1, B-2）。複数ファイルが存在するエッジケースは v0.2.0 で調査する
9. **IFRS/US-GAAP 検知に `is_all_empty()` ではなく namespace チェックを使う理由**: `_collect_extra_items()` は JSON 定義にない concept を extras として末尾に追加する（CODESCOPE.md SN-2）。IFRS 企業の `ifrs-full:Revenue` 等は extras として拾われるため、`FinancialStatement` は items 非空（全て extras）になり `is_all_empty()` は `False` を返す。namespace レベルで `jppfs` の有無をチェックする方が確実であり、`Statements` クラスへの変更もゼロで済む

### 4.7 D17-7: `_normalize_doc_type()` への日本語文字列マッチング追加

ゴールコード `latest("有価証券報告書")` を動かすために必要。現在の `_normalize_doc_type()` (`public_api.py:373-401`) は `DocType(normalized)` による Enum 構築のみで、日本語文字列 `"有価証券報告書"` は `ValueError` になる。

`DocType` Enum は `name_ja` プロパティを持ち（`doc_types.py:98-101`）、`_DOC_TYPE_NAMES_JA` 辞書が全 41 型式を網羅している。逆引き辞書を構築して `DocType(normalized)` 失敗時にフォールバックする。

```python
# src/edinet/public_api.py に追加

# DocType の name_ja から逆引き辞書を構築（モジュールレベル）
def _build_ja_to_doc_type() -> dict[str, DocType]:
    """日本語名称 → DocType の逆引き辞書を構築する。"""
    from edinet.models.doc_types import DocType, _DOC_TYPE_NAMES_JA

    return {name_ja: DocType(code) for code, name_ja in _DOC_TYPE_NAMES_JA.items()}


def _normalize_doc_type(doc_type: DocType | str | None) -> str | None:
    from edinet.models.doc_types import DocType

    if doc_type is None:
        return None
    if isinstance(doc_type, DocType):
        return doc_type.value
    if isinstance(doc_type, str):
        normalized = doc_type.strip()
        if not normalized:
            raise ValueError("doc_type must not be empty")
        # 既存: コード文字列 ("120" 等) → DocType
        try:
            return DocType(normalized).value
        except ValueError:
            pass
        # 新規: 日本語文字列 ("有価証券報告書" 等) → DocType
        ja_map = _build_ja_to_doc_type()
        matched = ja_map.get(normalized)
        if matched is not None:
            return matched.value
        raise ValueError(
            f"Unknown doc_type: {doc_type!r}. "
            "Use valid docTypeCode such as '120', DocType enum, "
            "or Japanese name such as '有価証券報告書'.",
        )
    raise ValueError("doc_type must be DocType, str, or None")
```

設計判断:
- **逆引き辞書を毎回構築する理由**: `_build_ja_to_doc_type()` はモジュールレベルでキャッシュしない。`_DOC_TYPE_NAMES_JA` は 41 エントリのため構築コストは無視できる（~0.01ms）。モジュールレベル変数にすると import 時に `DocType` の循環参照リスクがある
- **`ValueError` のメッセージに日本語名の例を追記**: 利用者が日本語指定が可能であることを発見できるようにする
- **部分一致は行わない理由**: `"有報"` → `"有価証券報告書"` のような曖昧マッチは意図しない結果を返すリスクがある。完全一致のみ

---

## 5. `Company.latest()` の設計

### 5.1 シグネチャ

```python
def latest(
    self,
    doc_type: DocType | str | None = None,
    *,
    start: str | DateType | None = None,
    end: str | DateType | None = None,
) -> Filing | None:
    """この企業の最新の Filing を返す。

    ``get_filings()`` で書類一覧を取得し、``submit_date_time`` の降順で
    最初の Filing を返す。該当なしの場合は ``None``。

    ``start`` / ``end`` を省略した場合、過去 90 日間を検索する。
    これにより ``latest("有価証券報告書")`` が日付指定なしで動く。
    最大 90 回の API コール（レート制限 1.0s/call で約 1.5 分）が
    発生する。期間の目安:

    - 30 日指定: 約 30 秒（四半期報告書の取得に十分）
    - 90 日（デフォルト）: 約 1.5 分
    - 365 日指定: 約 6 分（有価証券報告書を確実に拾う場合）

    Args:
        doc_type: 書類種別フィルタ。日本語文字列（``"有価証券報告書"``）
            または ``DocType`` Enum、コード文字列（``"120"``）を指定可能。
        start: 検索範囲の開始日。省略時は今日から 90 日前。
            ``end`` のみ指定した場合は ``end - 90日`` が自動設定される。
        end: 検索範囲の終了日。省略時は今日。
            ``start`` のみ指定した場合は今日が自動設定される。

    Returns:
        最新の Filing。見つからない場合は ``None``。

    Note:
        v0.1.0 は **J-GAAP の一般事業会社** のみ対応。

    Examples:
        >>> toyota = Company(edinet_code="E02144", name_ja="トヨタ自動車")
        >>> filing = toyota.latest("有価証券報告書")
        >>> filing.doc_id
        'S100XXXX'
    """
```

### 5.2 実装

`_today_jst()` は `company.py` 内の既存ヘルパー（`get_filings()` でも使用）を再利用する。

```python
def latest(
    self,
    doc_type: DocType | str | None = None,
    *,
    start: str | DateType | None = None,
    end: str | DateType | None = None,
) -> Filing | None:
    from datetime import timedelta

    # start/end の自動補完（利便性メソッドとして片方指定を許容する）
    if start is None and end is None:
        end = _today_jst()
        start = end - timedelta(days=90)
    elif start is not None and end is None:
        end = _today_jst()
    elif start is None and end is not None:
        if isinstance(end, str):
            from datetime import date as _date
            end = _date.fromisoformat(end)
        start = end - timedelta(days=90)

    filings = self.get_filings(start=start, end=end, doc_type=doc_type)
    if not filings:
        return None
    return max(filings, key=lambda f: f.submit_date_time)
```

### 5.3 設計判断

1. **`doc_type` を第一位置引数にする理由**: `company.latest("有価証券報告書")` という最も頻出するパターンを最短で書けるようにする。`get_filings()` では `doc_type` はキーワード引数だが、`latest()` は「1 件だけ欲しい」ユースケースに特化するため位置引数として許容する
2. **日本語文字列での指定を許容する理由**: `DocType` Enum は `name_ja` プロパティを持つ。ただし `_normalize_doc_type()` は現状コード文字列（`"120"` 等）と `DocType` Enum のみ受け付け、日本語文字列のマッチングは**未実装**。ゴールコード `latest("有価証券報告書")` を動かすため、D17-7 として `_normalize_doc_type()` に日本語文字列 → `DocType` の逆引きを追加する。`_DOC_TYPE_NAMES_JA` の逆引き辞書を構築し、`DocType(normalized)` 失敗時にフォールバックする
3. **`max()` で `submit_date_time` を使う理由**: `get_filings()` は API 順序（submit_date_time 降順）を保持するが、保証はされない。明示的に `submit_date_time` で `max()` することで最新を確実に取得する。`filing_date`（date 型）だと同日に複数 filing がある場合に非決定的になるため、時刻まで含む `submit_date_time`（datetime 型）を使う
4. **`start` / `end` 未指定時に過去 90 日を検索する理由**: `get_filings()` は `start`/`end` 未指定時に当日のみを検索する。`latest("有価証券報告書")` は年 1 回の提出であり、当日に提出がない限り `None` が返ってゴールコードが動かない。`latest()` は「最新の 1 件を簡単に取得する」利便性メソッドであるため、`start`/`end` 未指定時のみデフォルトで過去 90 日間を検索する。`get_filings()` の挙動は変更しない。90 日で四半期報告書・半期報告書を確実に拾える。有価証券報告書（年 1 回）を確実に拾うには `start` を明示的に指定する。docstring に期間ごとの目安時間を記載する
5. **`None` を返す理由（例外を投げない）**: 「見つからない」は異常ではなく正常な結果。EDINET API が期間外で空リストを返すケースは頻出する。利用者が `if filing is None:` で分岐するのが自然
6. **`start`/`end` 片方指定時に自動補完する理由**: `latest()` は利便性メソッドであり、`start` のみ指定（「この日以降の最新」）や `end` のみ指定（「この日までの最新」）は自然なユースケース。`get_filings()` / `documents()` は `start`/`end` ペアを要求するため、片方のみ指定だと `ValueError` が発生する。利便性メソッドとしてこの制約を吸収する。`start` のみ → `end = _today_jst()`、`end` のみ → `start = end - 90日`

---

## 6. QA 反映方針（Day 17 に直結するもの）

| QA | Day 17 への反映 |
|---|---|
| B-1 | ZIP 内のディレクトリ構造。`_extract_filer_taxonomy_files()` は `PublicDoc/` 配下を探索する。B-1 の知見（`_lab.xml` / `_lab-en.xml` / `.xsd` の配置）をそのまま適用 |
| B-2 | 提出者別タクソノミスキーマ（`.xsd`）。`load_filer_labels(xsd_bytes=...)` で提出者の namespace を登録する。B-2 の「`targetNamespace` を抽出して namespace → prefix マッピングに追加」が実装済み |
| H-10 | パーサーの入力インターフェース制約。`parse_xbrl_facts()` は `bytes` を受け取る。`fetch()` が `bytes` を返すので型は一致する。ファイルシステムのパスは `source_path` 引数でトレース用に渡す |
| H-11 | パース処理のブートストラップ順序。Day 17 のパイプラインは H-11 の推奨順序に従う: XBRL パース → Context 構造化 → ラベル解決 → LineItem → Statement |
| K-2 | iXBRL。v0.1.0 は従来型 XBRL のみ。`fetch()` が `.xbrl` を返し、`parse_xbrl_facts()` が処理する。`.htm` / `.xhtml` は Day 17 のスコープ外（D17N-3） |
| D-3 | 会計基準判別。v0.1.0 は J-GAAP 前提のため DEI ベースの自動判別は実装しない（D17N-8）。JSON データファイルが J-GAAP の concept を定義 |

---

## 7. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/models/filing.py` | 追記 | `xbrl()`, `axbrl()`, `_resolve_taxonomy_path()`, `_build_statements()`, `_extract_filer_taxonomy_files()` |
| `src/edinet/models/company.py` | 追記 | `latest()` |
| `src/edinet/public_api.py` | 修正 | `_normalize_doc_type()` に日本語文字列マッチングを追加（D17-7） |
| `src/edinet/__init__.py` | 追記 | `Statements`, `FinancialStatement`, `LineItem` のトップレベルエクスポート追加 |
| `tests/test_models/test_filing.py` | 追記 | `xbrl()` テスト |
| `tests/test_models/test_company.py` | 追記 | `latest()` テスト |
| `tests/test_e2e/__init__.py` | 新規作成 | E2E テストパッケージ |
| `tests/test_e2e/test_pipeline.py` | 新規作成 | フルパイプライン Medium テスト |
| `stubs/edinet/models/filing.pyi` | 再生成 | stubgen |
| `stubs/edinet/models/company.pyi` | 再生成 | stubgen |

注: `src/edinet/xbrl/statements.py` への変更は不要。Rev.4 で追加予定だった `Statements.is_all_empty()` は namespace ベースの検知（§4.3c ステップ 4b）に置き換えたため不要になった（Rev.5 P1-1）。

---

## 8. テスト計画

### 8.1 テスト方針

Day 17 のテストは **2 層** に分ける:

1. **Unit テスト**（`test_filing.py`, `test_company.py` に追記）: モック / パッチで外部依存を遮断し、接続ロジックの正しさを検証
2. **Medium テスト**（`test_e2e/test_pipeline.py`）: `tests/fixtures/` のフィクスチャを使い、パイプライン全体を通すテスト。ネットワークなし、ファイルシステム参照あり

Large テスト（実 API 呼び出し）は Day 18 のスコープ。

### 8.2 テスト用フィクスチャの方針

フィクスチャ用の最小 ZIP を新規作成する:
- `tests/fixtures/xbrl_fragments/` に既存の XBRL フラグメントがある
- `tests/fixtures/taxonomy_mini/` に最小タクソノミがある
- Day 17 では **既存フィクスチャを ZIP に固めたテスト用 ZIP** を動的に生成する（`io.BytesIO` + `zipfile.ZipFile`）
- テストヘルパー `_make_test_zip()` で PublicDoc 配下に `.xbrl`, `_lab.xml`, `_lab-en.xml`, `.xsd` を含む ZIP を構築
- **重要**: Medium テスト（X-1, X-2, E-1〜E-3）で `build_statements()` が非空の `FinancialStatement` を返すには、XBRL 内の Fact の concept が JSON データファイル（`pl_jgaap.json` 等）にマッチする必要がある。既存の `tests/fixtures/xbrl_fragments/` のフラグメントがこの条件を満たすか実装時に確認すること。不十分な場合は `jppfs_cor:NetSales` + `jppfs_cor:OperatingIncome` を含む最小 XBRL を fixtures に追加する

### 8.3 テストケース — `Filing.xbrl()`

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| X-1 | `test_xbrl_returns_statements` | `xbrl()` が `Statements` を返すこと | medium, integration |
| X-2 | `test_xbrl_income_statement_has_items` | `stmts.income_statement()` が空でない `FinancialStatement` を返すこと | medium, integration |
| X-3 | `test_xbrl_uses_taxonomy_path_arg` | `xbrl(taxonomy_path=...)` の引数が `configure()` より優先されること | small, unit |
| X-4 | `test_xbrl_raises_without_taxonomy_path` | taxonomy_path 未設定で `EdinetConfigError` が発生すること | small, unit |
| X-5 | `test_xbrl_raises_for_no_xbrl` | `has_xbrl=False` の Filing で `EdinetAPIError` が発生すること | small, unit |
| X-6 | `test_xbrl_reuses_zip_cache` | `fetch()` 済みの Filing で `xbrl()` が追加ダウンロードしないこと | small, unit |
| X-7 | `test_xbrl_loads_filer_labels` | 提出者ラベルが正しく読み込まれること（標準ラベルと異なるラベルが LineItem に反映されること）。**注意**: テスト時に `_xbrl_cache` だけでなく `_zip_cache` も明示的に設定すること。`_zip_cache` が None だと `_extract_filer_taxonomy_files()` が空辞書を返し、提出者ラベル抽出がスキップされる | medium, integration |
| X-8 | `test_xbrl_warns_on_non_jgaap_namespace` | XBRL 内の Fact に `jppfs_cor` 名前空間が含まれない場合に `UserWarning` が発生すること（IFRS/US-GAAP Filing の検知） | small, unit |
| X-9 | `test_xbrl_wraps_unexpected_error_with_doc_id` | パイプライン内の予期しない例外が `EdinetParseError` にラップされ、`doc_id` がメッセージに含まれること | small, unit |

### 8.4 テストケース — `Filing.axbrl()`

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| AX-1 | `test_axbrl_returns_statements` | `axbrl()` が `Statements` を返すこと（`asyncio.run()` で検証） | medium, integration |
| AX-2 | `test_axbrl_raises_without_taxonomy_path` | taxonomy_path 未設定で `EdinetConfigError` が発生すること | small, unit |

### 8.5 テストケース — `Company.latest()`

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| L-1 | `test_latest_returns_filing` | `latest()` が Filing を返すこと | small, unit |
| L-2 | `test_latest_returns_newest` | 複数 Filing がある場合に `submit_date_time` が最新のものを返すこと | small, unit |
| L-3 | `test_latest_with_doc_type_filter` | `doc_type` フィルタが `get_filings()` に渡されること | small, unit |
| L-4 | `test_latest_returns_none_when_empty` | Filing がない場合に `None` を返すこと | small, unit |
| L-5 | `test_latest_with_start_end` | `start` / `end` 引数が `get_filings()` に渡されること | small, unit |
| L-6 | `test_latest_default_range_90_days` | `start` / `end` 未指定時に過去 90 日間が `get_filings()` に渡されること | small, unit |
| L-7 | `test_latest_auto_completes_partial_range` | `start` のみ指定 → `end = _today_jst()`、`end` のみ指定 → `start = end - 90日` が自動補完されること | small, unit |

### 8.6 テストケース — `_extract_filer_taxonomy_files()`

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| F-1 | `test_extract_filer_files_from_zip` | PublicDoc 配下の `_lab.xml`, `_lab-en.xml`, `.xsd` が正しく抽出されること | small, unit |
| F-2 | `test_extract_filer_files_excludes_audit` | `AuditDoc/` 配下の `.xsd` が除外されること | small, unit |
| F-3 | `test_extract_filer_files_none_zip` | `zip_bytes=None` で空辞書が返ること | small, unit |
| F-4 | `test_extract_filer_files_no_filer_files` | 提出者ファイルがない ZIP で空辞書が返ること | small, unit |

### 8.7 テストケース — `_normalize_doc_type()` 日本語マッチング（D17-7）

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| N-1 | `test_normalize_doc_type_japanese_name` | `"有価証券報告書"` → `"120"` に正規化されること | small, unit |
| N-2 | `test_normalize_doc_type_japanese_correction` | `"訂正有価証券報告書"` → `"130"` に正規化されること | small, unit |
| N-3 | `test_normalize_doc_type_unknown_japanese` | 存在しない日本語名で `ValueError` が発生すること | small, unit |
| N-4 | `test_normalize_doc_type_code_still_works` | 既存の `"120"` 等のコード文字列が引き続き動作すること | small, unit |

### 8.8 テストケース — E2E パイプライン（Medium）

| # | テスト名 | 検証内容 | marker |
|---|---------|---------|--------|
| E-1 | `test_pipeline_xbrl_to_pl` | フィクスチャ ZIP → `parse_xbrl_facts` → `structure_contexts` → `build_line_items` → `build_statements` → `income_statement()` で `FinancialStatement` が得られ、`items` が非空であること | medium, integration |
| E-2 | `test_pipeline_pl_to_dataframe` | E-1 の `FinancialStatement` を `to_dataframe()` で DataFrame に変換し、カラムと行数が正しいこと | medium, integration |
| E-3 | `test_pipeline_pl_str_output` | E-1 の `FinancialStatement` を `str()` で変換し、科目名が含まれること | medium, integration |

### 8.9 テストヘルパー

```python
"""tests/conftest.py — 共通テストヘルパー（_make_test_zip を追記）。

_make_test_zip() は test_models/test_filing.py（F-1〜F-4）と
test_e2e/test_pipeline.py（E-1〜E-3）の両方から利用するため、
ルート conftest に配置する。
"""

import io
import zipfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
TAXONOMY_MINI_DIR = FIXTURES_DIR / "taxonomy_mini"


def _make_test_zip(
    xbrl_bytes: bytes,
    xbrl_name: str = "PublicDoc/jpcrp030000-asr-001_E00001_2025-03-31.xbrl",
    filer_lab_bytes: bytes | None = None,
    filer_lab_en_bytes: bytes | None = None,
    filer_xsd_bytes: bytes | None = None,
    filer_xsd_name: str = "PublicDoc/jpcrp030000-asr-001_E00001.xsd",
) -> bytes:
    """テスト用の最小 ZIP を構築する。

    Args:
        xbrl_bytes: XBRL インスタンスのバイト列。
        xbrl_name: ZIP 内での XBRL ファイルパス。
        filer_lab_bytes: 提出者 _lab.xml のバイト列。
        filer_lab_en_bytes: 提出者 _lab-en.xml のバイト列。
        filer_xsd_bytes: 提出者 .xsd のバイト列。
        filer_xsd_name: ZIP 内での XSD ファイルパス。

    Returns:
        ZIP のバイト列。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(xbrl_name, xbrl_bytes)
        if filer_lab_bytes is not None:
            lab_name = filer_xsd_name.replace(".xsd", "_lab.xml")
            zf.writestr(lab_name, filer_lab_bytes)
        if filer_lab_en_bytes is not None:
            lab_en_name = filer_xsd_name.replace(".xsd", "_lab-en.xml")
            zf.writestr(lab_en_name, filer_lab_en_bytes)
        if filer_xsd_bytes is not None:
            zf.writestr(filer_xsd_name, filer_xsd_bytes)
    return buf.getvalue()
```

### 8.10 marker 方針

- `small` + `unit`: モック/パッチで外部を遮断する in-memory テスト（X-3〜X-6, X-8, AX-2, L-1〜L-7, F-1〜F-4, N-1〜N-4）
- `medium` + `integration`: `tests/fixtures/` のファイルを使う統合テスト（X-1, X-2, X-7, AX-1, E-1〜E-3）
- `large` + `e2e`: 実 EDINET API を使うテスト（Day 18 のスコープ、Day 17 では書かない）

---

## 9. 依存関係の確認

```
Day 17 の依存構造:

Filing.xbrl()
  ├─ _resolve_taxonomy_path()  → str                  [新規]
  │    └─ get_config()                                [既存: _config.py]
  ├─ fetch()               → (xbrl_path, xbrl_bytes)  [既存]
  └─ _build_statements()   → Statements               [新規]
       ├─ _extract_filer_taxonomy_files()
       │    ├─ list_zip_members()     [既存: api/download.py]
       │    └─ extract_zip_member()   [既存: api/download.py]
       ├─ parse_xbrl_facts()    → ParsedXBRL              [既存: xbrl/parser.py]
       ├─ structure_contexts()  → dict[str, StructuredContext]  [既存: xbrl/contexts.py]
       ├─ TaxonomyResolver()    → ラベル辞書構築           [既存: xbrl/taxonomy.py]
       │    └─ load_filer_labels()                         [既存]
       ├─ build_line_items()    → tuple[LineItem, ...]     [既存: xbrl/facts.py]
       └─ build_statements()   → Statements               [既存: xbrl/statements.py]

Filing.axbrl()
  ├─ _resolve_taxonomy_path()  （xbrl() と共通）
  ├─ afetch()              → (xbrl_path, xbrl_bytes)  [既存]
  └─ _build_statements()   （xbrl() と共通）

Company.latest()
  └─ get_filings()         → list[Filing]             [既存: models/company.py]

get_config().taxonomy_path → str | None              [既存: _config.py]
```

- 新規の依存関係は発生しない
- `Filing.xbrl()` は 既存の全モジュールを import して呼び出すだけ
- `Company.latest()` は既存の `get_filings()` をラップするだけ
- 循環 import は発生しない（`filing.py` → `xbrl/` は一方通行、`company.py` → `filing.py` は既存）

---

## 10. CODESCOPE.md への追記

Day 17 の内容を §8 として追記する:

```markdown
## 8. E2E 統合 — Filing.xbrl() / Company.latest()（Day 17）

### 責務

Filing → Statements のフルパイプラインを提供する **オーケストレーター**。
新規のビジネスロジックは持たず、既存モジュール（§1〜§7）の接続のみを行う。

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| INT-1 | Filing.xbrl() | ZIP → parse → labels → statements のパイプライン | PLAN.LIVING.md Day 17 |
| INT-2 | Filing.axbrl() | xbrl() の非同期版 | async_support 方針 |
| INT-3 | Company.latest() | 最新 Filing の取得 | PLAN.LIVING.md Day 17 |
| INT-4 | 提出者ラベル抽出 | ZIP 内の _lab.xml / _lab-en.xml / .xsd の自動抽出 | Filing.xbrl() の内部ステップ |

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| INTN-1 | Company("7203") 糖衣構文 | ティッカーからの Company 構築 | EDINET コード一覧 CSV ベースの検索 → v0.2.0 |
| INTN-2 | xbrl() キャッシュ | パース結果の Filing 内キャッシュ | v0.1.0 では不要（fetch() の ZIP キャッシュで十分） |
| INTN-3 | iXBRL 対応 | .htm/.xhtml のパース | v0.2.0 |

### 設計判断の記録

- **Filing がパイプラインのオーケストレーターである理由**: Filing は ZIP をダウンロードし、XBRL bytes を持つ主体。
  パイプラインの入力（ZIP）と出力（Statements）を繋ぐのは Filing の責務として自然
- **TaxonomyResolver を xbrl() 内で毎回 new する理由**: pickle キャッシュにより 2 回目以降 ~50ms。
  ステートレスで提出者ラベルの漏洩を防ぐ
- **`_extract_filer_taxonomy_files()` のスコープ**: PublicDoc 配下のみ探索。監査報告書 XSD（`jpaud` 系）は
  `"audit" not in lower` で除外。ラベルファイル / XSD とも先勝ち（最初にマッチしたファイルを採用）
- **`xbrl()` の戻り値が Statements である理由**: PLAN.LIVING.md §3 では `XBRLDocument` 中間層を想定するが、
  v0.1.0 では Statements 直返しで十分。v0.2.0 で `ParsedFiling`（Statements のスーパーセット）に変更し、
  `facts` / `dei` 等を追加する際も `stmts.income_statement()` の呼び出し側コードは壊れない
```

---

## 11. 当日の作業手順（チェックリスト）

### Phase 0: 前提確認（~5 分）

既存フィクスチャの concept が JSON データファイルにマッチするか事前確認する。Phase 4 の Medium テストで `build_statements()` が非空の `FinancialStatement` を返すには、XBRL 内の Fact の concept が `pl_jgaap.json` / `bs_jgaap.json` / `cf_jgaap.json` にマッチする必要がある。

```bash
uv run python -c "
from pathlib import Path
import json

concepts = set()
for f in ['pl_jgaap.json', 'bs_jgaap.json', 'cf_jgaap.json']:
    data = json.loads((Path('src/edinet/xbrl/data') / f).read_text())
    concepts.update(item['concept'] for item in data)

# 既存フィクスチャの XBRL フラグメントを確認
for xbrl_file in Path('tests/fixtures/xbrl_fragments/').glob('*.xbrl'):
    content = xbrl_file.read_text(errors='ignore')
    matched = [c for c in concepts if c.split(':')[1] in content]
    print(f'{xbrl_file.name}: マッチ {len(matched)} 件')
    if matched:
        print(f'  例: {matched[:5]}')

if not matched:
    print('WARNING: フィクスチャに jppfs_cor 科目が不足。最小 XBRL の追加が必要')
"
```

不十分な場合は `jppfs_cor:NetSales` + `jppfs_cor:OperatingIncome` を含む最小 XBRL を `tests/fixtures/xbrl_fragments/` に追加する。

### Phase 0b: D17-7 `_normalize_doc_type()` の実装（~5 分）

1. `src/edinet/public_api.py` の `_normalize_doc_type()` に日本語文字列マッチングを追加（§4.7）
2. `uv run ruff check src/edinet/public_api.py` で lint pass を確認
3. N-1〜N-4 のテストを追加・実行

### Phase 1: `Company.latest()` の実装（~10 分）

1. `src/edinet/models/company.py` に `latest()` メソッドを追加（§5.2）
2. `uv run ruff check src/edinet/models/company.py` で lint pass を確認
3. `tests/test_models/test_company.py` に L-1〜L-5 のテストを追加
4. `uv run pytest tests/test_models/test_company.py -v` で pass を確認

### Phase 2: `_extract_filer_taxonomy_files()` の実装（~10 分）

1. `src/edinet/models/filing.py` に `_extract_filer_taxonomy_files()` を追加（§4.4）
2. `uv run ruff check src/edinet/models/filing.py` で lint pass を確認
3. F-1〜F-4 のテストを `tests/test_models/test_filing.py` に追加
4. `uv run pytest tests/test_models/test_filing.py -v -k filer` で pass を確認

### Phase 3: `Filing.xbrl()` / `Filing.axbrl()` の実装（~30 分）

1. `src/edinet/models/filing.py` に `xbrl()` を追加（§4.2）
2. `src/edinet/models/filing.py` に `axbrl()` を追加（§4.3）
3. `uv run ruff check src/edinet/models/filing.py` で lint pass を確認
4. X-3〜X-6, AX-2 の Unit テストを `tests/test_models/test_filing.py` に追加
5. `uv run pytest tests/test_models/test_filing.py -v -k xbrl` で pass を確認

### Phase 4: E2E Medium テスト（~30 分）

1. `tests/test_e2e/__init__.py` を空ファイルで作成
2. `tests/test_e2e/conftest.py` を作成（§8.8 のヘルパー）
3. `tests/test_e2e/test_pipeline.py` を作成（E-1〜E-3）
4. X-1, X-2, X-7, AX-1 の Medium テストを追加
5. `uv run pytest tests/test_e2e/ tests/test_models/ -v -m "not large"` で全件 pass を確認

### Phase 5: 検証（~20 分）

1. `uv run pytest` — 全テスト回帰なし（472 + 新規テスト）
2. `uv run ruff check src tests` — 警告なし
3. `uv run stubgen src/edinet --include-docstrings -o stubs` — `.pyi` 再生成
4. 生成された `stubs/edinet/models/filing.pyi` に `xbrl()` / `axbrl()` があることを確認
5. 生成された `stubs/edinet/models/company.pyi` に `latest()` があることを確認
6. CODESCOPE.md に §8 を追記（§10）
7. 手動スモーク: 実 filing 1 件で E2E を実行

**前提確認**: `has_xbrl=True` の Filing に対して `fetch()` が従来型 `.xbrl` ファイルを返せることを最初に確認する。K-2 で指摘の通り、iXBRL のみの Filing では `fetch()` が `ValueError` を raise する可能性がある。この確認が失敗した場合、Day 17 の根本的な前提が崩れるため、iXBRL 対応を前倒しする必要がある。

```python
import edinet
edinet.configure(
    api_key="your_api_key",
    taxonomy_path=r"C:\Users\nezow\Downloads\ALL_20251101",
)

from edinet import documents

# 0. fetch() の動作確認（iXBRL only でないことの確認）
filings_check = documents("2025-06-25", doc_type="120")
f0 = [f for f in filings_check if f.has_xbrl][0]
xbrl_path, _ = f0.fetch()
print(f"fetch() OK: {xbrl_path}")  # .xbrl で終わることを確認
assert xbrl_path.endswith(".xbrl"), f"iXBRL only? path={xbrl_path}"

# 1. documents で Filing を取得
filings = documents("2025-06-25", doc_type="120")
filing = [f for f in filings if f.filer_name and "トヨタ" in f.filer_name][0]
print(f"Filing: {filing.doc_id} - {filing.filer_name}")

# 2. Filing.xbrl() のフルパイプライン
import time
t0 = time.perf_counter()
stmts = filing.xbrl()
t1 = time.perf_counter()
print(f"xbrl() elapsed: {t1 - t0:.2f}s")

# 3. PL
pl = stmts.income_statement()
print(pl)
print(f"PL items: {len(pl)}")

# 4. BS
bs = stmts.balance_sheet()
print(bs)
print(f"BS items: {len(bs)}")

# 5. CF
cf = stmts.cash_flow_statement()
print(cf)
print(f"CF items: {len(cf)}")

# 6. Statements 一括表示
print(stmts)

# 7. DataFrame
df = pl.to_dataframe()
print(df)
print(df.dtypes)

# 8. Rich 表示
from rich.console import Console
Console().print(pl)

# 9. 2 回目呼び出し（ZIP キャッシュ活用）
t2 = time.perf_counter()
stmts2 = filing.xbrl()
t3 = time.perf_counter()
print(f"xbrl() 2nd call elapsed: {t3 - t2:.2f}s (no download)")

# 10. Company.latest() のテスト
from edinet import Company
company = filing.company
if company:
    latest = company.latest("120", start="2025-06-01", end="2025-06-30")
    if latest:
        print(f"Latest: {latest.doc_id} - {latest.filer_name}")
```

期待パフォーマンス:
- 初回 `xbrl()`: 3〜8 秒（ZIP ダウンロード: 1〜5s + パース: 0.1〜0.5s + ラベル解決: 0.05〜0.5s）
- 2 回目 `xbrl()`: 0.1〜0.5 秒（ZIP キャッシュ活用、パース + ラベル解決のみ）

---

## 12. Day 18 への引き継ぎ事項

Day 17 完了後、Day 18（テスト仕上げ）で以下を実施する:

1. **Large テスト**: 実 EDINET API を使った E2E テスト。`@pytest.mark.large` で分離
2. **`git clone → pip install -e ".[dev]" → pytest` の完走確認**: Day 18 のメイン作業
3. **エッジケース補完**: IFRS 企業、has_xbrl=False、空の Filing 等のエラーハンドリング強化

Day 16 からの引き継ぎ（Day 17 で対応予定だったが Day 17 スコープ外として延期した項目）:
- `to_dict()` / `to_records()`: Day 16 の Rev.8 で P1 として記録。確認結果: `to_dict()` は Day 16 で実装済み（`models/financial.py`）。引き継ぎ完了
- `Statements.__str__()`: Day 16 の Rev.8 で P2 として記録。確認結果: Day 16 で実装済み（`stubs/edinet/xbrl/statements.pyi` に `__str__` あり）。引き継ぎ完了

Day 17 レビューからの引き継ぎ:
- **パフォーマンスプロファイル**: 手動スモークで計測した各ステップの所要時間を記録し、Day 18 のベンチマーク設計に反映
- **エラーメッセージの品質**: `xbrl()` で発生しうるエラー（taxonomy_path 不正、ZIP 内に XBRL なし等）のメッセージが利用者にとって十分 actionable か確認。パイプライン例外の `doc_id` 付与は `_build_statements()` の try/except で Day 17 にて対応済み
- **`Company.alatest()` 非同期版**: `latest()` の非同期版。`aget_filings()` が前提となるため v0.2.0 で対応
- **エラーメッセージの日本語化**: CLAUDE.md の指示（「エラーメッセージは日本語」）と既存コードの英語エラーメッセージの矛盾を解消する。Day 17 は既存コードの英語に合わせたが、Day 18 以降で既存エラーメッセージの日本語化を一括検討する

---

## 13. v0.2.0 拡張性の評価

Day 17 の設計が v0.2.0 の機能拡張に対してどの程度容易かを評価する。

| v0.2.0 機能 | 拡張の容易さ | コメント |
|---|---|---|
| `xbrl()` のキャッシュ (D17N-2) | 容易 | `_statements_cache` を `object.__setattr__` で追加。`fetch()` と同パターン |
| iXBRL 対応 (D17N-3) | 中程度 | `xbrl()` 内で `.xbrl` / `.htm` を分岐。`parse_ixbrl_facts()` の追加が必要 |
| DEI 自動判別 (D17N-8) | 中程度 | `xbrl()` 内で `parsed.facts` から DEI 要素を抽出するステップを追加。ただし DEI 情報を利用者に返すには `xbrl()` の戻り値型を `Statements` から `ParsedFiling`（Statements のスーパーセット）等に変更する必要がある。`Statements` のメソッド群はそのまま `ParsedFiling` に移植でき、`stmts.income_statement()` の呼び出し側コードは壊れないため実質 non-breaking にできる |
| Company("7203") 糖衣構文 (D17N-1) | 容易 | `Company.__init__` に `__init_subclass__` または `__init__` のオーバーロードで対応 |
| 訂正チェーン (D17N-6) | 容易 | `Company.latest()` に `include_corrections=True` パラメータを追加 |
| `Filing.xbrl()` のフック | 容易 | パイプラインがフラットなので、任意のステップ間にログ / プロファイリングを挿入可能 |

`Filing.xbrl()` のフラットなパイプライン設計と `Company.latest()` のシンプルなラッパー設計により、全機能が既存 API を壊さずに追加可能。

**v0.2.0 `ParsedFiling` の実装方針**: `xbrl()` の戻り値を `Statements` → `ParsedFiling` に変更する際、2 つの選択肢がある:

| 方式 | API の見え方 | 利点 | 欠点 |
|---|---|---|---|
| 継承: `ParsedFiling(Statements)` | `stmts.income_statement()` がそのまま動く | コード変更が最小。`isinstance(x, Statements)` も True | Statements の責務が曖昧になる |
| 委譲: `ParsedFiling.statements -> Statements` | `stmts.income_statement()` は動かない（`stmts.statements.income_statement()` が必要） | 責務分離が明確 | v0.1.0 の呼び出し側コードが壊れる（breaking change） |

**推奨**: 継承方式。v0.1.0 の `stmts.income_statement()` がそのまま動き、`stmts.facts` / `stmts.dei` が追加される形で non-breaking にできる。

---

## 14. 改訂ログ

本セクションは計画の変更履歴を記録する。§4〜§5 本文は常に最終版を反映する。

- **Rev.1（初版）**: 作成
- **Rev.2（レビュー反映）**: 以下のフィードバックを反映
  - **P0**: `Company.latest()` の `start`/`end` 未指定時のデフォルトを過去 365 日に変更（§5.1〜§5.3）。ゴールコードが日付指定なしで動く状態にした
  - **P1**: `max()` の sort key を `filing_date` → `submit_date_time` に変更（§5.2〜§5.3）。同日 filing での非決定性を排除
  - **P1**: `axbrl()` の未使用 import（`extract_zip_member`, `list_zip_members`）を削除（§4.3）
  - **P2**: `_lab.xml` / `_lab-en.xml` の抽出ロジックを先勝ちに統一。XSD と整合（§4.4, §4.6）
  - **P2**: `_make_test_zip()` の配置をルート conftest に変更（§8.8）。`test_models/` と `test_e2e/` の両方から利用するため
  - **P2**: audit フィルタの意図をコメントで明確化（§4.4）
  - **P3**: `xbrl()` の戻り値型の v0.2.0 拡張パスを §13 に補記。DEI 統合は戻り値型変更が必要だが non-breaking にできる
  - **P3**: J-GAAP only 制限を `xbrl()` / `latest()` の docstring に明記（§4.1, §5.1）
  - **P3**: iXBRL 分岐点の TODO コメントを `xbrl()` / `axbrl()` に追加（§4.2, §4.3）
  - **P3**: CODESCOPE.md §8 に `_extract_filer_taxonomy_files()` のスコープと戻り値型の設計判断を追記（§10）
  - **P3**: Day 18 引き継ぎに IFRS silent failure 対策、エラーメッセージの doc_id 付与を追記（§12）
  - テストケース L-6 追加（`latest()` デフォルト範囲の検証）
  - 見送り: パイプラインエラーの doc_id 付与（v0.1.0 では 1 件処理のため不要。Day 18 引き継ぎに記載）
- **Rev.3（追加レビュー反映）**: 以下のフィードバックを反映
  - **P0-1**: `latest()` のデフォルト範囲を 365 → 90 日に変更（§5.1〜§5.3）。90 日で ~1.5 分、365 日の ~6 分は UX 破綻。docstring に期間ごとの目安時間を記載
  - **P0-2**: PLAN.LIVING.md §1 のゴールコード（`filing.xbrl().statements.income_statement()`）と Day 17 の API（`filing.xbrl().income_statement()`）の齟齬を認識。Day 17 のゴールコードは既に正しい形。PLAN.LIVING.md §1 は v0.1.0 完了時に更新する
  - **P1-1**: `xbrl()` 内で全財務諸表が空の場合に `UserWarning` を発行（§4.3c）。IFRS / US-GAAP Filing の silent failure を防止。テストケース X-8 追加
  - **P1-2**: `xbrl()` / `axbrl()` の重複コード（ステップ 3〜9）を `_build_statements()` プライベートメソッドに抽出（§4.2, §4.3, §4.3b, §4.3c）。taxonomy_path 解決も `_resolve_taxonomy_path()` に共通化。§4.6 point 5 を更新
  - **P1-3**: パイプライン例外に `doc_id` コンテキストを付与する try/except を `_build_statements()` に組み込み（§4.3c）。テストケース X-9 追加。§12 の「Day 18 引き継ぎ」から削除（Day 17 で対応済み）
  - **P1-4**: `_extract_filer_taxonomy_files()` に `logging.debug()` を追加（§4.4）。探索結果を DEBUG レベルで記録
  - **P2-1**: §8.2 にフィクスチャの concept マッチング確認の注記を追加。XBRL 内の concept が JSON データファイルにマッチすることの確認が必要
  - **P2-2**: §12 に `Company.alatest()` 非同期版を追記（`aget_filings()` が前提、v0.2.0）
  - **P2-3**: CODESCOPE.md §8 の ID prefix を "E-" → "INT-" に変更。FEATURES.md の "E-" カテゴリとの衝突を回避
  - **P3-1**: §11 手動スモークに `fetch()` の動作確認ステップを追加。iXBRL only Filing でないことの確認が Day 17 の前提
  - **P3-2**: §13 に `ParsedFiling` の実装方式（継承 vs 委譲）の pros/cons を追記。継承方式を推奨
  - **P3-3**: §8.3 X-7 テストに `_zip_cache` 設定の注記を追加
  - 見送り: `DocTypeSpec` 型エイリアス（P2-4）— docstring で十分。Day 17 スコープ外
- **Rev.4（最終レビュー反映）**: P0 なし（実装可能状態）。以下の P1/P2/P3 を反映
  - **P1-1**: `_build_statements()` のエラーメッセージを英語に統一。既存コード全体が英語
  - **P1-2**: 空 Statements 警告の `stacklevel` 問題を解消。`_build_statements()` から `xbrl()`/`axbrl()` 側に移動し `stacklevel=2` で固定。`Statements.is_all_empty()` ヘルパーを追加（§7）
  - **P1-3**: §5.2 に「`_today_jst()` は company.py 内の既存ヘルパーを再利用」を補記
  - **P1-4**: `Statements` / `FinancialStatement` / `LineItem` のトップレベルエクスポートを §7 に追加。`from edinet import Statements` を可能にする
  - **P2-1→採用**: パイプライン各ステップのデバッグログを `_build_statements()` に追加。`logging.debug()` でステップ 4/5/7 の件数を記録
  - **P2-3→P1 昇格**: `_normalize_doc_type()` が日本語文字列（`"有価証券報告書"` 等）を受け付けない問題を発見。D17-7 として `_DOC_TYPE_NAMES_JA` 逆引きを `_normalize_doc_type()` に追加するスコープを設定（§3.1, §5.3, §7）。§5.3 point 2 の「実装済み」の誤記を修正
  - **P3-4**: `xbrl()` の docstring に「スレッドセーフではない」を追記（§4.1）
  - 見送り: PublicDoc 判定の厳密化（P2-2）— 実害なし、`_make_test_zip()` 配置（P2-4）— conftest で十分、`xbrl()` メソッド名（P2-5）— 許容範囲
  - 記録: XBRLDocument スキップの妥当性（P3-1）、フィクスチャ concept マッチング（P3-2）、パフォーマンス計測粒度（P3-3）、`clear_fetch_cache()` スレッドセーフティ（P3-4）
- **Rev.5（レビュー反映）**: 以下のフィードバックを反映
  - **P1-1→採用**: IFRS/US-GAAP 検知を `is_all_empty()` から namespace ベースに変更（§4.2, §4.3, §4.3c, §4.6 point 9）。`_collect_extra_items()` が IFRS 科目を extras として拾うため `is_all_empty()` は `False` を返し警告が発火しない問題を修正。`_build_statements()` のステップ 4b で `parsed.facts` の namespace に `jppfs` が含まれるか走査する方式に変更。`Statements.is_all_empty()` メソッドは不要になり、`statements.py` への変更がゼロに。§7 から `statements.py` を削除。テストケース X-8 を `test_xbrl_warns_on_non_jgaap_namespace` に更新
  - **P1-2→採用**: D17-7 `_normalize_doc_type()` への日本語文字列マッチングの具体的な実装設計を §4.7 として追加。`_DOC_TYPE_NAMES_JA` の逆引き辞書で完全一致マッチ。テストケース N-1〜N-4 を §8.7 として追加。§11 に Phase 0b を追加
  - **P1-3→一部採用**: Day 17 新規コードは既存の英語に合わせる（Rev.4 判断を維持）。日本語化は Day 18 引き継ぎに追記（§12）
  - **P1-4→採用**: `latest()` の `start`/`end` 片方指定時の自動補完を追加（§5.1, §5.2, §5.3 point 6）。`start` のみ → `end = _today_jst()`、`end` のみ → `start = end - 90日`。テストケース L-7 を追加
  - **P2-2→採用**: §11 に Phase 0 を追加。既存フィクスチャの concept が JSON データファイルにマッチするか事前確認する手順を記載
  - 見送り: `__init__.py` エクスポート詳細（P2-1）— 実装時に判断で十分、例外ラップの削除（P2-3）— `from exc` でチェーン保持されており実害小、`int` 型 doc_type（P2-4）— Day 17 スコープ外

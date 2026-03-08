"""Presentation Linkbase から科目セット (ConceptSet) を自動導出するモジュール。

手動 JSON ファイル (pl_jgaap.json 等) に代わり、タクソノミの ``_pre*.xml``
をパースして role URI ごとの科目リスト・表示順序・インデント深度を導出する。
23 業種を 1 パーサーでカバーし、BUG-6 (PL/CF/SS の cross-contamination) を
根本解決する。
"""

from __future__ import annotations

import enum
import hashlib
import logging
import pickle
import re
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import platformdirs

from edinet._version import __version__
from edinet.exceptions import EdinetConfigError, EdinetWarning
from edinet.models.financial import StatementType
from edinet.xbrl.linkbase.presentation import (
    PresentationNode,
    PresentationTree,
    merge_presentation_trees,
    parse_presentation_linkbase,
)

__all__ = [
    "ConceptEntry",
    "ConceptSet",
    "ConceptSetRegistry",
    "StatementCategory",
    "classify_role_uri",
    "derive_concept_sets",
    "derive_concept_sets_from_trees",
    "get_concept_set",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


class StatementCategory(enum.Enum):
    """財務諸表カテゴリ。

    ``StatementType`` (PL/BS/CF の 3 値) よりも広く、
    株主資本等変動計算書 (SS) や包括利益計算書 (CI) を含む。
    """

    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW_STATEMENT = "cash_flow_statement"
    STATEMENT_OF_CHANGES_IN_EQUITY = "statement_of_changes_in_equity"
    COMPREHENSIVE_INCOME = "comprehensive_income"

    def to_statement_type(self) -> StatementType | None:
        """対応する ``StatementType`` を返す。"""
        return _CATEGORY_TO_STATEMENT_TYPE.get(self)

    @classmethod
    def from_statement_type(cls, st: StatementType) -> StatementCategory:
        """``StatementType`` から変換する。

        Args:
            st: 変換元の StatementType。

        Returns:
            対応する StatementCategory。
        """
        return _STATEMENT_TYPE_TO_CATEGORY[st]


_CATEGORY_TO_STATEMENT_TYPE: dict[StatementCategory, StatementType] = {
    StatementCategory.BALANCE_SHEET: StatementType.BALANCE_SHEET,
    StatementCategory.INCOME_STATEMENT: StatementType.INCOME_STATEMENT,
    StatementCategory.CASH_FLOW_STATEMENT: StatementType.CASH_FLOW_STATEMENT,
    StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY: StatementType.STATEMENT_OF_CHANGES_IN_EQUITY,
    StatementCategory.COMPREHENSIVE_INCOME: StatementType.COMPREHENSIVE_INCOME,
}

_STATEMENT_TYPE_TO_CATEGORY: dict[StatementType, StatementCategory] = {
    StatementType.BALANCE_SHEET: StatementCategory.BALANCE_SHEET,
    StatementType.INCOME_STATEMENT: StatementCategory.INCOME_STATEMENT,
    StatementType.CASH_FLOW_STATEMENT: StatementCategory.CASH_FLOW_STATEMENT,
    StatementType.STATEMENT_OF_CHANGES_IN_EQUITY: StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY,
    StatementType.COMPREHENSIVE_INCOME: StatementCategory.COMPREHENSIVE_INCOME,
}


@dataclass(frozen=True, slots=True)
class ConceptEntry:
    """科目セット内の 1 エントリ。

    Attributes:
        concept: ローカル名 (例: ``"CashAndDeposits"``)。
        order: Presentation order。
        is_total: ``preferredLabel`` が totalLabel であるかどうか。
        is_abstract: Abstract 科目かどうか。
        depth: LineItems からの相対深さ (0-based)。
        href: 元 XSD href。
        preferred_label: ``presentationArc`` の ``preferredLabel`` 属性値。
            ``None`` は標準ラベル。``periodStartLabel`` / ``periodEndLabel``
            等の特殊ロールを保持し、CF 期首/期末残高の動的検出に使用する。
    """

    concept: str
    order: float
    is_total: bool
    is_abstract: bool
    depth: int
    href: str
    preferred_label: str | None = None


@dataclass(frozen=True, slots=True)
class ConceptSet:
    """1 つの role URI に対応する科目セット。

    Attributes:
        role_uri: XBRL role URI。
        category: 財務諸表カテゴリ。
        is_consolidated: 連結かどうか。
        concepts: 科目エントリのタプル (表示順)。
        source_info: 導出元情報 (デバッグ用)。
        cf_method: CF の作成方法。``"direct"`` / ``"indirect"`` / ``None``。
            CF 以外は ``None``。
    """

    role_uri: str
    category: StatementCategory
    is_consolidated: bool
    concepts: tuple[ConceptEntry, ...]
    source_info: str
    cf_method: str | None = None

    def concept_names(self) -> frozenset[str]:
        """全科目名 (abstract 含む) の集合を返す。"""
        return frozenset(e.concept for e in self.concepts)

    def non_abstract_concepts(self) -> frozenset[str]:
        """非 abstract 科目名の集合を返す。"""
        return frozenset(e.concept for e in self.concepts if not e.is_abstract)

    def __repr__(self) -> str:
        role_short = self.role_uri.rsplit("/", 1)[-1] if self.role_uri else ""
        cat = self.category.name
        cons = "連結" if self.is_consolidated else "個別"
        n = len(self.concepts)
        n_na = len(self.non_abstract_concepts())
        return (
            f"ConceptSet({role_short}, {cat}, {cons}, "
            f"concepts={n}, non_abstract={n_na}, "
            f"source={self.source_info!r})"
        )


# ---------------------------------------------------------------------------
# role URI 分類
# ---------------------------------------------------------------------------

_STATEMENT_KEYWORDS: list[tuple[str, StatementCategory]] = [
    (
        "StatementOfComprehensiveIncome",
        StatementCategory.COMPREHENSIVE_INCOME,
    ),
    (
        "StatementOfChangesInEquity",
        StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY,
    ),
    (
        "StatementOfChangesInNetAssets",
        StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY,
    ),
    (
        "StatementOfUnitholdersEquity",
        StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY,
    ),
    (
        "StatementOfMembersEquity",
        StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY,
    ),
    (
        "StatementOfIncomeAndRetainedEarnings",
        StatementCategory.INCOME_STATEMENT,
    ),
    (
        "StatementOfCashFlows",
        StatementCategory.CASH_FLOW_STATEMENT,
    ),
    # IFRS 向け（IAS 1 の財務諸表名称）
    (
        "StatementOfProfitOrLoss",
        StatementCategory.INCOME_STATEMENT,
    ),
    (
        "StatementOfFinancialPosition",
        StatementCategory.BALANCE_SHEET,
    ),
    (
        "StatementOfIncome",
        StatementCategory.INCOME_STATEMENT,
    ),
    (
        "BalanceSheet",
        StatementCategory.BALANCE_SHEET,
    ),
]


def classify_role_uri(
    role_uri: str,
) -> tuple[StatementCategory, bool, str | None] | None:
    """role URI から財務諸表カテゴリと連結/個別を判定する。

    Args:
        role_uri: XBRL role URI 文字列。

    Returns:
        ``(StatementCategory, is_consolidated, cf_method)`` のタプル。
        ``cf_method`` は CF の場合 ``"direct"`` / ``"indirect"`` / ``None``、
        CF 以外は ``None``。
        財務諸表に該当しない場合は ``None``。
    """
    # 1. "rol_" 以降を抽出
    idx = role_uri.rfind("rol_")
    if idx < 0:
        return None
    tail = role_uri[idx + 4 :]

    # 2. "std_" prefix 除去 (標準タクソノミ対応)
    if tail.startswith("std_"):
        tail = tail[4:]

    # 3. 半期/中間 prefix 除去 (longest first)
    for prefix in ("Type1SemiAnnual", "SemiAnnual"):
        if tail.startswith(prefix):
            tail = tail[len(prefix) :]
            break

    # 4. "Consolidated" 検出・除去
    is_consolidated = tail.startswith("Consolidated")
    if is_consolidated:
        tail = tail[len("Consolidated") :]

    # 5. キーワードマッチ (startswith で suffix を許容: -indirect, -direct 等)
    for keyword, category in _STATEMENT_KEYWORDS:
        if tail.startswith(keyword):
            # 6. CF の direct/indirect 検出
            cf_method: str | None = None
            if category == StatementCategory.CASH_FLOW_STATEMENT:
                suffix = tail[len(keyword) :]
                if "-indirect" in suffix:
                    cf_method = "indirect"
                elif "-direct" in suffix:
                    cf_method = "direct"
            return (category, is_consolidated, cf_method)

    return None


# ---------------------------------------------------------------------------
# PresentationTree → ConceptSet 変換
# ---------------------------------------------------------------------------


def _tree_to_concept_set(
    role_uri: str,
    tree: PresentationTree,
    category: StatementCategory,
    is_consolidated: bool,
    source_info: str,
    cf_method: str | None = None,
) -> ConceptSet:
    """PresentationTree を ConceptSet に変換する。

    ``line_items_roots()`` で取得した科目に加え、マージによって
    トップレベルに独立した LineItems ルート (variant 由来) の
    children も収集する。

    Args:
        role_uri: role URI。
        tree: パース済み PresentationTree。
        category: 財務諸表カテゴリ。
        is_consolidated: 連結かどうか。
        source_info: 導出元情報。

    Returns:
        ConceptSet インスタンス。
    """
    roots = tree.line_items_roots()
    if not roots:
        roots = tree.roots

    # マージ後に variant 由来の LineItems がトップレベルルートとして
    # 存在する場合、その children も走査対象に追加する。
    # line_items_roots() は最初に見つけた LineItems の children のみ
    # 返すため、別ルートの LineItems children は漏れる。
    roots_set = set(roots)
    for r in tree.roots:
        if r.concept.endswith("LineItems") and r.children:
            for child in r.children:
                if child not in roots_set:
                    roots_set.add(child)
    all_roots = tuple(roots_set)

    base_depth = min((r.depth for r in all_roots), default=0)

    entries: list[ConceptEntry] = []
    seen: set[tuple[str, str | None]] = set()

    def _dfs(node: PresentationNode) -> None:
        if node.is_dimension_node:
            return
        key = (node.concept, node.preferred_label)
        if key not in seen:
            seen.add(key)
            entries.append(
                ConceptEntry(
                    concept=node.concept,
                    order=node.order,
                    is_total=node.is_total,
                    is_abstract=node.is_abstract,
                    depth=node.depth - base_depth,
                    href=node.href,
                    preferred_label=node.preferred_label,
                )
            )
        for child in node.children:
            _dfs(child)

    # 元の roots を先に走査し（主要科目の順序を優先）、
    # その後に追加分を走査する
    extra = [r for r in all_roots if r not in roots]
    for root in roots:
        _dfs(root)
    for root in extra:
        _dfs(root)

    return ConceptSet(
        role_uri=role_uri,
        category=category,
        is_consolidated=is_consolidated,
        concepts=tuple(entries),
        source_info=source_info,
        cf_method=cf_method,
    )


# ---------------------------------------------------------------------------
# パース済みツリーから直接導出 (テスト・アドホック用)
# ---------------------------------------------------------------------------


def derive_concept_sets_from_trees(
    trees: dict[str, PresentationTree],
    *,
    source_info: str = "",
) -> list[ConceptSet]:
    """パース済み PresentationTree dict から ConceptSet を導出する。

    テストやアドホック解析向けの便利関数。
    ディレクトリ走査やキャッシュは行わない。

    Args:
        trees: ``{role_uri: PresentationTree}`` 辞書。
        source_info: 導出元情報 (デバッグ用)。

    Returns:
        導出された ConceptSet のリスト。
        非財務 role URI はスキップされる。
    """
    result: list[ConceptSet] = []
    for role_uri, tree in trees.items():
        classification = classify_role_uri(role_uri)
        if classification is None:
            continue
        category, is_consolidated, cf_method = classification
        cs = _tree_to_concept_set(
            role_uri, tree, category, is_consolidated, source_info,
            cf_method=cf_method,
        )
        result.append(cs)
    return result


# ---------------------------------------------------------------------------
# ConceptSetRegistry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConceptSetRegistry:
    """業種別の ConceptSet レジストリ。

    Attributes:
        _sets: ``{industry_code: {role_uri: ConceptSet}}`` の辞書。
    """

    _sets: dict[str, dict[str, ConceptSet]]

    def get(
        self,
        statement_type: StatementType,
        *,
        consolidated: bool = True,
        industry_code: str = "cai",
        cf_method: str | None = None,
    ) -> ConceptSet | None:
        """指定条件に合致する ConceptSet を取得する。

        同一条件で複数の ConceptSet がある場合（例: CF の
        indirect/direct）、concepts 数が最大のものを返す。

        Args:
            statement_type: 財務諸表種別。
            consolidated: 連結かどうか。
            industry_code: 業種コード（デフォルト ``"cai"`` = 一般商工業）。
            cf_method: CF の作成方法でフィルタする。
                ``"indirect"`` / ``"direct"`` を指定するとその方法のみ返す。
                ``None``（デフォルト）は全候補から最大を返す。

        Returns:
            合致する ConceptSet。見つからない場合は ``None``。
        """
        target = StatementCategory.from_statement_type(statement_type)
        industry_sets = self._sets.get(industry_code, {})
        candidates = [
            cs
            for cs in industry_sets.values()
            if cs.category == target and cs.is_consolidated == consolidated
        ]
        if cf_method is not None:
            candidates = [
                cs for cs in candidates if cs.cf_method == cf_method
            ]
        if not candidates:
            return None
        return max(candidates, key=lambda cs: len(cs.concepts))

    def all_for_industry(
        self, industry_code: str
    ) -> dict[str, ConceptSet]:
        """指定業種の全 ConceptSet を返す。

        Args:
            industry_code: 業種コード。

        Returns:
            ``{role_uri: ConceptSet}`` 辞書。存在しなければ空辞書。
        """
        return dict(self._sets.get(industry_code, {}))

    def industries(self) -> frozenset[str]:
        """登録済み業種コードの集合を返す。"""
        return frozenset(self._sets.keys())

    def statement_categories(
        self, industry_code: str = "cai"
    ) -> frozenset[StatementCategory]:
        """指定業種で利用可能な StatementCategory の集合を返す。

        Args:
            industry_code: 業種コード。

        Returns:
            利用可能な StatementCategory の frozenset。
        """
        industry_sets = self._sets.get(industry_code, {})
        return frozenset(cs.category for cs in industry_sets.values())


# ---------------------------------------------------------------------------
# ディレクトリ走査・パース・マージ
# ---------------------------------------------------------------------------

_STMT_RE = re.compile(r"_pre_(bs|pl|cf|ss|ci)[\-.]")


def _scan_taxonomy_directory(
    taxonomy_path: Path,
) -> dict[str, list[Path]]:
    """タクソノミディレクトリを走査し、業種別の _pre ファイル一覧を返す。

    Args:
        taxonomy_path: タクソノミのルートパス。

    Returns:
        ``{industry_code: [pre_file_paths]}`` 辞書。

    Raises:
        EdinetConfigError: jppfs/*/r が見つからない場合。
    """
    r_dirs = sorted(taxonomy_path.glob("taxonomy/jppfs/*/r"))
    if not r_dirs:
        raise EdinetConfigError(
            f"jppfs/*/r が見つかりません: {taxonomy_path}"
        )
    result: dict[str, list[Path]] = {}
    for r_dir in r_dirs:
        for industry_dir in sorted(r_dir.iterdir()):
            if not industry_dir.is_dir():
                continue
            pre_files = sorted(industry_dir.glob("*_pre*.xml"))
            if pre_files:
                result[industry_dir.name] = pre_files
    return result


def _scan_taxonomy_directory_flat(
    taxonomy_path: Path,
    module_group: str,
    industry_code: str,
) -> dict[str, list[Path]]:
    """フラット構造のタクソノミディレクトリを走査する。

    jpigp のように業種サブディレクトリがない場合に使用。
    ``r/`` 直下の ``_pre`` ファイルを収集し、指定の ``industry_code`` に紐づける。

    Args:
        taxonomy_path: タクソノミのルートパス。
        module_group: モジュールグループ名（例: ``"jpigp"``）。
        industry_code: 割り当てる業種コード（例: ``"ifrs"``）。

    Returns:
        ``{industry_code: [pre_file_paths]}`` 辞書。
        ディレクトリが存在しなければ空辞書。
    """
    r_dirs = sorted(taxonomy_path.glob(f"taxonomy/{module_group}/*/r"))
    if not r_dirs:
        return {}
    result_files: list[Path] = []
    for r_dir in r_dirs:
        # _pre_*.xml で収集（_pre.xml サフィックスなしを除外）。
        # J-GAAP 側は業種ディレクトリ内で *_pre*.xml を使うが、
        # jpigp の r/ 直下には jpigp_500000-000_*_pre.xml（表紙）や
        # jpigp_610010-001_*_pre.xml（注記）など _pre_(bs|pl|cf|ss|ci)
        # パターンに合致しないファイルが多い。_pre_*.xml に絞ることで
        # _group_pre_files() で弾かれる無駄なファイル読み込みを抑制する。
        result_files.extend(sorted(r_dir.glob("*_pre_*.xml")))
    if not result_files:
        return {}
    return {industry_code: result_files}


def _group_pre_files(
    pre_files: list[Path],
) -> dict[str, list[Path]]:
    """ファイル名から stmt キー (bs/pl/cf/ss/ci) でグルーピングする。

    Args:
        pre_files: _pre ファイルのリスト。

    Returns:
        ``{stmt_key: [file_paths]}`` 辞書。
    """
    groups: dict[str, list[Path]] = {}
    for p in pre_files:
        m = _STMT_RE.search(p.name)
        if m:
            groups.setdefault(m.group(1), []).append(p)
    return groups


def _parse_and_merge_group(
    files: list[Path],
) -> dict[str, PresentationTree]:
    """複数ファイルをパースし、同一 role URI のツリーをマージする。

    Args:
        files: パース対象ファイルのリスト。

    Returns:
        ``{role_uri: PresentationTree}`` 辞書。
    """
    sorted_files = sorted(files, key=lambda p: len(p.name))
    tree_dicts: list[dict[str, PresentationTree]] = []
    for f in sorted_files:
        try:
            trees = parse_presentation_linkbase(
                f.read_bytes(), source_path=str(f)
            )
            tree_dicts.append(trees)
        except Exception:
            warnings.warn(
                f"_pre ファイルのパースに失敗: {f}",
                EdinetWarning,
                stacklevel=2,
            )
    if not tree_dicts:
        return {}
    if len(tree_dicts) == 1:
        return tree_dicts[0]
    return merge_presentation_trees(*tree_dicts)


def _apply_cf_fallback(
    registry_data: dict[str, dict[str, ConceptSet]],
) -> None:
    """cai に CF がない場合、他業種から全バリアントを補完する。

    一般商工業 (cai) は CF の Presentation Linkbase を持たないため、
    他業種（通常 bk1 = 銀行業第一種）から CF を借用する。

    Args:
        registry_data: 業種別レジストリデータ (in-place 変更)。
    """
    cai_sets = registry_data.get("cai", {})
    has_cf = any(
        cs.category == StatementCategory.CASH_FLOW_STATEMENT
        for cs in cai_sets.values()
    )
    if has_cf:
        return

    for code, sets in registry_data.items():
        if code == "cai":
            continue
        cf_sets = {
            uri: cs
            for uri, cs in sets.items()
            if cs.category == StatementCategory.CASH_FLOW_STATEMENT
        }
        if not cf_sets:
            continue
        for role_uri, cs in cf_sets.items():
            fallback = ConceptSet(
                role_uri=cs.role_uri,
                category=cs.category,
                is_consolidated=cs.is_consolidated,
                concepts=cs.concepts,
                source_info=f"fallback from {code}",
                cf_method=cs.cf_method,
            )
            cai_sets[role_uri] = fallback
            logger.info(
                "CF ConceptSet を %s から cai に補完しました "
                "(連結=%s, role=%s)",
                code,
                cs.is_consolidated,
                role_uri.rsplit("/", 1)[-1],
            )
        return  # 1 業種分で十分


# ---------------------------------------------------------------------------
# キャッシュ
# ---------------------------------------------------------------------------

_CACHE_VERSION = 2


def _cache_path(
    taxonomy_path: Path,
    module_group: str = "jppfs",
) -> Path:
    """キャッシュファイルのパスを構築する。

    Args:
        taxonomy_path: タクソノミのルートパス。
        module_group: モジュールグループ名。キャッシュファイル名に含まれる。

    Returns:
        キャッシュファイルの Path。
    """
    path_hash = hashlib.sha256(str(taxonomy_path).encode()).hexdigest()[:8]
    version = taxonomy_path.name
    cache_dir = Path(platformdirs.user_cache_dir("edinet"))
    return (
        cache_dir
        / f"concept_sets_v{_CACHE_VERSION}_{__version__}_{module_group}_{version}_{path_hash}.pkl"
    )


def _load_cache(path: Path) -> ConceptSetRegistry | None:
    """pickle キャッシュを読み込む。失敗時は None。

    Args:
        path: キャッシュファイルのパス。

    Returns:
        キャッシュされた ConceptSetRegistry。失敗時は None。
    """
    if not path.exists():
        return None
    try:
        t0 = time.perf_counter()
        with path.open("rb") as f:
            data = pickle.load(f)  # noqa: S301
        elapsed = time.perf_counter() - t0
        logger.info(
            "ConceptSet キャッシュを読み込みました (%.3f秒, %s)",
            elapsed,
            path,
        )
        return data  # type: ignore[no-any-return]
    except Exception:
        warnings.warn(
            f"ConceptSet キャッシュの読み込みに失敗しました。再構築します: {path}",
            EdinetWarning,
            stacklevel=2,
        )
        return None


def _save_cache(registry: ConceptSetRegistry, path: Path) -> None:
    """pickle キャッシュを保存する。失敗時は警告して続行。

    Args:
        registry: 保存する ConceptSetRegistry。
        path: キャッシュファイルのパス。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        with path.open("wb") as f:
            pickle.dump(registry, f, protocol=pickle.HIGHEST_PROTOCOL)
        elapsed = time.perf_counter() - t0
        logger.info(
            "ConceptSet キャッシュを保存しました (%.3f秒, %s)",
            elapsed,
            path,
        )
    except Exception:
        warnings.warn(
            f"ConceptSet キャッシュの保存に失敗しました: {path}",
            EdinetWarning,
            stacklevel=2,
        )


# ---------------------------------------------------------------------------
# メインオーケストレーション
# ---------------------------------------------------------------------------

# プロセス内キャッシュ。ConceptSetRegistry は frozen dataclass なので
# 同一引数であれば安全に使い回せる。毎回 pickle.load() を避ける。
_memory_cache: dict[tuple[str, str], ConceptSetRegistry] = {}


def derive_concept_sets(
    taxonomy_path: str | Path,
    *,
    use_cache: bool = True,
    module_group: str = "jppfs",
) -> ConceptSetRegistry:
    """タクソノミディレクトリから全業種の ConceptSet を導出する。

    Args:
        taxonomy_path: タクソノミのルートパス。
        use_cache: キャッシュを使用するかどうか。
        module_group: スキャン対象のモジュールグループ。
            ``"jppfs"``（デフォルト）: J-GAAP、23 業種。
            ``"jpigp"``: IFRS、業種コード ``"ifrs"`` 固定。

    Returns:
        ConceptSetRegistry インスタンス。

    Raises:
        EdinetConfigError: パスが存在しない場合。
        EdinetConfigError: ``module_group="jppfs"`` で
            ``jppfs/*/r`` が見つからない場合。
    """
    path = Path(taxonomy_path)
    if not path.exists():
        raise EdinetConfigError(
            f"タクソノミパスが存在しません: {path}"
        )

    mem_key = (str(path.resolve()), module_group)

    # Layer 1: プロセス内メモリキャッシュ
    if use_cache:
        mem_cached = _memory_cache.get(mem_key)
        if mem_cached is not None:
            return mem_cached

    # Layer 2: ディスク pickle キャッシュ
    if use_cache:
        cached = _load_cache(_cache_path(path, module_group))
        if cached is not None:
            _memory_cache[mem_key] = cached
            return cached

    t0 = time.perf_counter()

    if module_group == "jppfs":
        industry_files = _scan_taxonomy_directory(path)
    else:
        industry_files = _scan_taxonomy_directory_flat(
            path, module_group, industry_code="ifrs",
        )
        if not industry_files:
            return ConceptSetRegistry(_sets={})

    registry_data: dict[str, dict[str, ConceptSet]] = {}

    for code, pre_files in industry_files.items():
        groups = _group_pre_files(pre_files)
        sets_for_industry: dict[str, ConceptSet] = {}
        for stmt_key, group_files in groups.items():
            merged = _parse_and_merge_group(group_files)
            for role_uri, tree in merged.items():
                classification = classify_role_uri(role_uri)
                if classification is None:
                    continue
                category, is_consolidated, cf_method = classification
                cs = _tree_to_concept_set(
                    role_uri,
                    tree,
                    category,
                    is_consolidated,
                    f"{module_group}/{code}/{stmt_key}",
                    cf_method=cf_method,
                )
                sets_for_industry[role_uri] = cs
        registry_data[code] = sets_for_industry

    if module_group == "jppfs":
        _apply_cf_fallback(registry_data)

    elapsed = time.perf_counter() - t0
    total_sets = sum(len(s) for s in registry_data.values())
    logger.info(
        "ConceptSet を導出しました (%s): %d 業種, %d セット (%.3f秒)",
        module_group,
        len(registry_data),
        total_sets,
        elapsed,
    )

    registry = ConceptSetRegistry(_sets=registry_data)
    if use_cache:
        _memory_cache[(str(path.resolve()), module_group)] = registry
        _save_cache(registry, _cache_path(path, module_group))
    return registry


# ---------------------------------------------------------------------------
# 便利関数
# ---------------------------------------------------------------------------


def get_concept_set(
    taxonomy_path: str | Path,
    statement_type: StatementType,
    *,
    consolidated: bool = True,
    industry_code: str = "cai",
    use_cache: bool = True,
    cf_method: str | None = None,
    module_group: str = "jppfs",
) -> ConceptSet | None:
    """ショートカット: 指定条件の ConceptSet を 1 つ取得する。

    Args:
        taxonomy_path: タクソノミのルートパス。
        statement_type: 財務諸表種別。
        consolidated: 連結かどうか。
        industry_code: 業種コード（デフォルト ``"cai"`` = 一般商工業）。
        use_cache: キャッシュを使用するかどうか。
        cf_method: CF の作成方法でフィルタする。
        module_group: スキャン対象のモジュールグループ。
            ``"jpigp"`` を指定する場合は ``industry_code="ifrs"`` を
            明示的に渡すこと（デフォルト ``"cai"`` では IFRS の概念セットに
            マッチしない）。

    Returns:
        合致する ConceptSet。見つからない場合は ``None``。
    """
    registry = derive_concept_sets(
        taxonomy_path, use_cache=use_cache, module_group=module_group,
    )
    return registry.get(
        statement_type,
        consolidated=consolidated,
        industry_code=industry_code,
        cf_method=cf_method,
    )

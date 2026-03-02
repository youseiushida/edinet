"""業種固有タクソノミの共通基盤。

``SectorConceptMapping`` / ``SectorProfile`` / ``SectorRegistry`` を提供し、
建設業・鉄道業・証券業など複数の業種固有モジュールが同じ API 構造を持てるようにする。

``sector/banking.py`` はフラットモジュール関数 API で先行実装済みのため
``_base.py`` を直接利用しないが、本モジュールは Wave 3 の新規業種モジュール
（construction / railway / securities）で統一的に使用される。

典型的な使用例::

    from edinet.financial.sector._base import (
        SectorConceptMapping,
        SectorProfile,
        SectorRegistry,
    )

    # 業種モジュール側で Registry を構築
    registry = SectorRegistry(
        profile=my_profile,
        mappings=my_mappings,
    )

    # lookup / reverse_lookup / sector_key など banking.py 互換の API
    m = registry.lookup("OperatingRevenueSEC")
    assert m is not None
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "SectorConceptMapping",
    "SectorProfile",
    "SectorRegistry",
]

# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SectorConceptMapping:
    """業種固有 concept の正規化マッピング。

    ``sector/banking.py`` の ``BankingConceptMapping`` と同等のフィールドを持つが、
    複数の業種モジュールで再利用できるよう汎用化している。

    Attributes:
        concept: タクソノミのローカル名
            （例: ``"OperatingRevenueSEC"``）。
        sector_key: 正規化キー（例: ``"operating_revenue_sec"``）。
        industry_codes: この科目が適用される業種コードの集合。
        general_equivalent: 一般事業会社の canonical_key への対応。
            対応がない場合は None。
        mapping_note: マッピングに関する補足情報。空文字列で省略可。
    """

    concept: str
    sector_key: str
    industry_codes: frozenset[str]
    general_equivalent: str | None = None
    mapping_note: str = ""


@dataclass(frozen=True, slots=True)
class SectorProfile:
    """業種プロファイル（概要情報）。

    業種ごとの特性を保持する。``standards/normalize`` (Wave 3) が
    業種判別とディスパッチに使用する。

    Attributes:
        sector_id: 業種識別子（例: ``"securities"``）。
        display_name_ja: 日本語表示名。
        display_name_en: 英語表示名。
        industry_codes: 対象業種コードの集合。
        concept_suffix: タクソノミ concept のサフィックス
            （例: ``"SEC"``、``"CNS"``、``"RWY"``）。
        pl_structure_note: PL 構造に関する補足説明。
        has_consolidated_template: 連結テンプレートの有無。
            None は未設定。
        cf_method: CF の作成方法
            （例: ``"both"``、``"indirect"``）。None は未設定。
    """

    sector_id: str
    display_name_ja: str
    display_name_en: str
    industry_codes: frozenset[str]
    concept_suffix: str
    pl_structure_note: str = ""
    has_consolidated_template: bool | None = None
    cf_method: str | None = None


# ---------------------------------------------------------------------------
# レジストリ
# ---------------------------------------------------------------------------


class SectorRegistry:
    """業種固有マッピングのレジストリ。

    ``sector/banking.py`` のフラットモジュール関数群と同等の API を
    クラスベースで提供する。各業種モジュールが本クラスのインスタンスを
    1 つ生成し、モジュールレベル関数にデリゲートする。

    Args:
        profile: 業種プロファイル。
        mappings: マッピングのタプル。

    Raises:
        ValueError: レジストリに不整合がある場合。

    典型的な使用例::

        registry = SectorRegistry(profile=my_profile, mappings=my_mappings)
        m = registry.lookup("OperatingRevenueSEC")
    """

    def __init__(
        self,
        profile: SectorProfile,
        mappings: tuple[SectorConceptMapping, ...],
    ) -> None:
        self._profile = profile
        self._mappings = mappings

        # concept → SectorConceptMapping
        self._concept_index: dict[str, SectorConceptMapping] = {
            m.concept: m for m in mappings
        }
        # sector_key → SectorConceptMapping
        self._key_index: dict[str, SectorConceptMapping] = {
            m.sector_key: m for m in mappings
        }
        # general_equivalent → list[SectorConceptMapping]
        self._general_index: dict[str, list[SectorConceptMapping]] = {}
        for m in mappings:
            if m.general_equivalent is not None:
                self._general_index.setdefault(
                    m.general_equivalent, []
                ).append(m)

        # 全正規化キーの集合
        self._all_sector_keys = frozenset(self._key_index)

        self._validate()

    # -----------------------------------------------------------------------
    # バリデーション
    # -----------------------------------------------------------------------

    def _validate(self) -> None:
        """マッピングレジストリの整合性を検証する。

        モジュールロード時に呼び出され、データ定義のミスを早期に検出する。

        Raises:
            ValueError: レジストリに不整合がある場合。
        """
        sid = self._profile.sector_id

        # concept の重複
        concepts = [m.concept for m in self._mappings]
        seen_concepts: set[str] = set()
        dup_concepts: set[str] = set()
        for c in concepts:
            if c in seen_concepts:
                dup_concepts.add(c)
            seen_concepts.add(c)
        if dup_concepts:
            raise ValueError(
                f"[{sid}] concept が重複しています: {dup_concepts}"
            )

        # sector_key の重複
        keys = [m.sector_key for m in self._mappings]
        seen_keys: set[str] = set()
        dup_keys: set[str] = set()
        for k in keys:
            if k in seen_keys:
                dup_keys.add(k)
            seen_keys.add(k)
        if dup_keys:
            raise ValueError(
                f"[{sid}] sector_key が重複しています: {dup_keys}"
            )

        # 各マッピングのフィールド検証
        for m in self._mappings:
            if not m.concept:
                raise ValueError(
                    f"[{sid}] 空の concept が登録されています"
                )
            if not m.sector_key:
                raise ValueError(
                    f"[{sid}] {m.concept} の sector_key が空です"
                )
            if not m.industry_codes:
                raise ValueError(
                    f"[{sid}] {m.concept} の industry_codes が空です"
                )
            if not m.industry_codes <= self._profile.industry_codes:
                extra = m.industry_codes - self._profile.industry_codes
                raise ValueError(
                    f"[{sid}] {m.concept} の industry_codes が "
                    f"プロファイルに含まれていません: {extra}"
                )

    # -----------------------------------------------------------------------
    # 公開 API
    # -----------------------------------------------------------------------

    def lookup(self, concept: str) -> SectorConceptMapping | None:
        """concept ローカル名からマッピング情報を取得する。

        Args:
            concept: タクソノミのローカル名。

        Returns:
            SectorConceptMapping。登録されていない concept の場合は None。
        """
        return self._concept_index.get(concept)

    def sector_key(self, concept: str) -> str | None:
        """concept ローカル名を正規化キーにマッピングする。

        Args:
            concept: タクソノミのローカル名。

        Returns:
            正規化キー文字列。登録されていない concept の場合は None。
        """
        m = self._concept_index.get(concept)
        return m.sector_key if m is not None else None

    def reverse_lookup(self, key: str) -> SectorConceptMapping | None:
        """正規化キーから SectorConceptMapping を取得する（逆引き）。

        Args:
            key: 正規化キー。

        Returns:
            SectorConceptMapping。該当するマッピングがない場合は None。
        """
        return self._key_index.get(key)

    def all_mappings(self) -> tuple[SectorConceptMapping, ...]:
        """全マッピングを返す。

        Returns:
            全 SectorConceptMapping のタプル。
        """
        return self._mappings

    def all_sector_keys(self) -> frozenset[str]:
        """全正規化キーの集合を返す。

        Returns:
            正規化キーのフローズンセット。
        """
        return self._all_sector_keys

    def get_profile(self) -> SectorProfile:
        """業種プロファイルを返す。

        Returns:
            SectorProfile インスタンス。
        """
        return self._profile

    def to_general_key(self, concept: str) -> str | None:
        """業種固有 concept の一般事業会社 canonical_key を返す。

        Args:
            concept: タクソノミのローカル名。

        Returns:
            一般事業会社の canonical_key。対応がない場合は None。
        """
        m = self._concept_index.get(concept)
        if m is None:
            return None
        return m.general_equivalent

    def from_general_key(
        self,
        general_key: str,
    ) -> tuple[SectorConceptMapping, ...]:
        """一般事業会社の canonical_key から業種固有マッピングを逆引きする。

        同一の general_equivalent に複数の概念が対応しうるため、
        タプルを返す。定義順（挿入順）を維持する。

        Args:
            general_key: 一般事業会社の canonical_key
                （例: ``"revenue"``）。

        Returns:
            対応する SectorConceptMapping のタプル。
            対応がなければ空タプル。
        """
        mappings = self._general_index.get(general_key, [])
        return tuple(mappings)

    def to_general_map(self) -> dict[str, str]:
        """業種固有 sector_key → 一般事業会社 canonical_key のマッピング辞書を返す。

        ``general_equivalent`` が設定されているマッピングのみを含む。

        Returns:
            ``{sector_key: general_canonical_key}`` の辞書。
        """
        return {
            m.sector_key: m.general_equivalent
            for m in self._mappings
            if m.general_equivalent is not None
        }

    @property
    def sector_key_count(self) -> int:
        """登録済み sector_key の数を返す。"""
        return len(self._key_index)

    def __len__(self) -> int:
        """登録済みマッピングの数を返す。"""
        return len(self._mappings)

    def __repr__(self) -> str:
        """デバッグ用の文字列表現を返す。"""
        return (
            f"SectorRegistry("
            f"sector_id={self._profile.sector_id!r}, "
            f"mappings={len(self._mappings)})"
        )

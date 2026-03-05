from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from edinet.financial.standards.detect import DetectedStandard
from edinet.models.financial import FinancialStatement, LineItem
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod, StructuredContext
from edinet.xbrl.dei import DEI
from edinet.xbrl.linkbase.calculation import CalculationLinkbase
from edinet.xbrl.linkbase.definition import DefinitionTree
from edinet.xbrl.parser import RawFact
from edinet.xbrl.taxonomy import TaxonomyResolver
from pathlib import Path
from typing import Literal

__all__ = ['build_statements', 'Statements']

@dataclass(frozen=True, slots=True, kw_only=True)
class Statements:
    '''財務諸表コンテナ。

    ``build_statements()`` 経由で構築すること。直接コンストラクトは非推奨。

    ``build_statements()`` の返り値。PL / BS / CF への
    アクセスメソッドを提供する。内部には全 LineItem を保持し、
    メソッド呼び出し時に選択ルールを適用する。

    会計基準の判別結果を ``_detected_standard`` に保持し、
    各メソッドで基準別の概念セットにディスパッチする。

    Attributes:
        _items: 全 LineItem（全期間・全 dimension）。
        _detected_standard: 判別された会計基準。
        _facts: 元の RawFact（テキストブロック抽出・会計基準判別用）。
        _contexts: コンテキストマッピング（テキストブロック抽出用）。
        _taxonomy_root: タクソノミルートパス。
        _industry_code: 業種コード（例: ``"bk1"``）。
            ``None`` は一般事業会社。
        _resolver: ラベル解決済みの TaxonomyResolver。
            パイプライン中に ``load_filer_labels()`` で提出者固有ラベルが
            ロードされた状態で保持される。セグメント分析等の
            事後ラベル解決に使用する。
    '''
    @property
    def detected_standard(self) -> DetectedStandard | None:
        """判別された会計基準を返す。"""
    @property
    def dei(self) -> DEI | None:
        """DEI 情報を返す。"""
    @property
    def context_map(self) -> dict[str, StructuredContext] | None:
        """コンテキストマッピングを返す。"""
    @property
    def resolver(self) -> TaxonomyResolver | None:
        """TaxonomyResolver を返す。"""
    @property
    def industry_code(self) -> str | None:
        """業種コードを返す。"""
    @property
    def taxonomy_root(self) -> Path | None:
        """タクソノミルートパスを返す。"""
    @property
    def calculation_linkbase(self) -> CalculationLinkbase | None:
        """Calculation Linkbase を返す。"""
    @property
    def definition_linkbase(self) -> dict[str, DefinitionTree] | None:
        """Definition Linkbase を返す。"""
    @property
    def raw_facts(self) -> tuple[RawFact, ...] | None:
        """元の RawFact タプルを返す。"""
    @property
    def has_consolidated_data(self) -> bool:
        """連結データが存在するかを返す。"""
    @property
    def has_non_consolidated_data(self) -> bool:
        """個別データが存在するかを返す。"""
    @property
    def period_classification(self):
        """DEI ベースの期間分類結果を返す。

        Returns:
            PeriodClassification。DEI なしの場合は全フィールド None。
        """
    def __getitem__(self, key: str) -> LineItem:
        """全科目から日本語ラベル・英語ラベル・local_name で検索する。

        照合順序:
          1. ``label_ja.text`` 完全一致
          2. ``label_en.text`` 完全一致
          3. ``local_name`` 完全一致

        最初にマッチした LineItem を返す。

        Args:
            key: 検索キー。

        Returns:
            マッチした LineItem。

        Raises:
            KeyError: 該当する科目が見つからない場合。
        """
    def get(self, key: str, default: LineItem | None = None) -> LineItem | None:
        """科目を検索する。見つからなければ default を返す。

        Args:
            key: 検索キー（label_ja / label_en / local_name）。
            default: 見つからない場合の返却値。

        Returns:
            マッチした LineItem、または default。
        """
    def __contains__(self, key: object) -> bool:
        '''科目の存在確認。``"売上高" in stmts`` のように使う。

        Args:
            key: 検索キー。

        Returns:
            科目が存在すれば True。
        '''
    def __len__(self) -> int:
        """全科目数を返す。"""
    def __iter__(self) -> Iterator[LineItem]:
        """全科目を順に返す。"""
    def search(self, keyword: str) -> list[LineItem]:
        """キーワードで部分一致検索する。

        ``label_ja.text``、``label_en.text``、``local_name`` のいずれかに
        keyword を含む全ての LineItem を返す。英語ラベル・local_name の
        照合は大文字小文字を区別しない。

        Args:
            keyword: 検索キーワード。

        Returns:
            マッチした LineItem のリスト（空の場合もある）。
        """
    def to_dataframe(self):
        """全 LineItem を全カラム DataFrame に変換する。

        Returns:
            pandas DataFrame。全カラム（concept, label_ja, value 等）を含む。

        Raises:
            ImportError: pandas がインストールされていない場合。
        """
    def to_csv(self, path: str | Path, **kwargs) -> None:
        """全 LineItem を CSV に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_csv()`` に渡す追加引数。
        """
    def to_parquet(self, path: str | Path, **kwargs) -> None:
        """全 LineItem を Parquet に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_parquet()`` に渡す追加引数。
        """
    def to_excel(self, path: str | Path, **kwargs) -> None:
        """全 LineItem を Excel に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_excel()`` に渡す追加引数。
        """
    def income_statement(self, *, consolidated: bool = True, period: DurationPeriod | Literal['current', 'prior'] | None = None, strict: bool = False) -> FinancialStatement:
        '''損益計算書を組み立てる。

        選択ルール:
          1. period: None なら最新期間を選択
          2. consolidated: True なら連結を優先、連結がなければ個別にフォールバック
          3. dimensions: dimension なし（全社合計）の Fact のみを採用
          4. 重複: 同一 concept で上記ルール適用後も複数 Fact が残る場合は
             warnings.warn() で警告
          5. 並び順: display_order に従う

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの損益計算書。
        '''
    def balance_sheet(self, *, consolidated: bool = True, period: InstantPeriod | Literal['current', 'prior'] | None = None, strict: bool = False) -> FinancialStatement:
        '''貸借対照表を組み立てる。

        BS は InstantPeriod（時点）を使用する。
        選択ルールは income_statement() と同一。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象時点。``"current"`` / ``"prior"`` で当期末/前期末を
                DEI ベースで自動選択。None なら最新時点を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの貸借対照表。
        '''
    def cash_flow_statement(self, *, consolidated: bool = True, period: DurationPeriod | Literal['current', 'prior'] | None = None, strict: bool = False) -> FinancialStatement:
        '''キャッシュフロー計算書を組み立てる。

        選択ルールは income_statement() と同一。

        J-GAAP の場合、期首残高・期末残高（``CashAndCashEquivalents``、
        ``periodType="instant"``）が自動的に先頭・末尾に挿入される。

        Note:
            期首残高と期末残高は同一の ``local_name``
            (``"CashAndCashEquivalents"``) を持つため、
            ``cf["CashAndCashEquivalents"]`` は期首（先頭）のみ返す。
            期末残高は日本語ラベルで取得すること::

                ending = cf["現金及び現金同等物の期末残高"]

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みのキャッシュフロー計算書。
        '''
    def equity_statement(self, *, consolidated: bool = True, period: DurationPeriod | Literal['current', 'prior'] | None = None, strict: bool = False) -> FinancialStatement:
        '''株主資本等変動計算書を組み立てる。

        ConceptSet（Presentation Linkbase 自動導出）により SS の
        全科目を取得する。taxonomy_root が未設定の場合は空を返す。

        Note:
            SS のタクソノミ定義は 5 業種（cai, edu, inv, liq, med）のみ。
            未定義の業種では空の FinancialStatement を返す。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの株主資本等変動計算書。
        '''
    def comprehensive_income(self, *, consolidated: bool = True, period: DurationPeriod | Literal['current', 'prior'] | None = None, strict: bool = False) -> FinancialStatement:
        '''包括利益計算書を組み立てる。

        ConceptSet（Presentation Linkbase 自動導出）により CI の
        全科目を取得する。taxonomy_root が未設定の場合は空を返す。

        Note:
            CI のタクソノミ定義は 1 業種（cai）のみ。
            未定義の業種では空の FinancialStatement を返す。

        Args:
            consolidated: True なら連結、False なら個別。
            period: 対象期間。``"current"`` / ``"prior"`` で当期/前期を
                DEI ベースで自動選択。None なら最新期間を自動選択。
            strict: True の場合、要求した連結/個別データが存在しないとき
                フォールバックせず空を返す。

        Returns:
            組み立て済みの包括利益計算書。
        '''

def build_statements(items: Sequence[LineItem], *, facts: tuple[RawFact, ...] | None = None, contexts: dict[str, StructuredContext] | None = None, taxonomy_root: Path | None = None, industry_code: str | None = None, resolver: TaxonomyResolver | None = None, calculation_linkbase: CalculationLinkbase | None = None, definition_linkbase: dict[str, DefinitionTree] | None = None) -> Statements:
    '''LineItem 群から Statements コンテナを構築する。

    全 LineItem をそのまま保持し、``income_statement()`` 等の
    メソッド呼び出し時に選択ルールを適用する。

    Args:
        items: ``build_line_items()`` が返した LineItem のシーケンス。
        facts: 元の RawFact タプル（会計基準判別・US-GAAP 抽出用）。
        contexts: ``structure_contexts()`` の戻り値（US-GAAP 抽出用）。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード（例: ``"bk1"``）。
            ``None`` は一般事業会社として扱う。
        resolver: 提出者ラベルロード済みの TaxonomyResolver。
            セグメント分析等の事後ラベル解決に使用する。
        calculation_linkbase: 提出者の Calculation Linkbase。
            ``extract_values()`` の ``calc_mapper`` が使用する。
        definition_linkbase: 提出者の Definition Linkbase。
            ``extract_values()`` の ``definition_mapper`` が使用する。

    Returns:
        Statements コンテナ。
    '''

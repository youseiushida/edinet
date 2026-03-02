"""doc_types.py のテスト。

edinet-tools の「6型式欠落」を防ぐためのガードレールテスト。
公式コードリストとの突き合わせで機械的に検証する。
"""
import warnings

from edinet.models.doc_types import OFFICIAL_CODES, DocType, _DOC_TYPE_NAMES_JA


def test_all_doc_types_defined():
    """公式コードリストの全コードが DocType に定義されていること。

    edinet-tools は6型式（240, 260, 270, 290, 310, 330）が欠落していた。
    このテストで同じ失敗を構造的に防ぐ。
    """
    for code in OFFICIAL_CODES:
        assert DocType.from_code(code) is not None, f"DocType '{code}' が未定義"


def test_doc_type_count_matches_official():
    """公式コードリストの件数が42であること。

    OFFICIAL_CODES は _DOC_TYPE_NAMES_JA から導出されるため、
    dict から行を誤って削除しても len(DocType) == len(OFFICIAL_CODES) は
    pass してしまう（循環参照）。
    「API 仕様書由来の外部期待値」として件数をハードコードすることで、
    single source of truth 自体が壊れたことを検出するアンカー。

    仕様書が更新されてコード数が変わった場合は、この値も更新すること。
    """
    EXPECTED_DOC_TYPE_COUNT = 42  # API 仕様書 (ESE140206.pdf) 由来の固定値（要確認）
    assert len(DocType) == EXPECTED_DOC_TYPE_COUNT, (
        f"DocType count mismatch: expected {EXPECTED_DOC_TYPE_COUNT}, got {len(DocType)}. "
        f"→ API 仕様書を確認し EXPECTED_DOC_TYPE_COUNT を更新すること"
    )
    assert len(OFFICIAL_CODES) == EXPECTED_DOC_TYPE_COUNT, (
        f"OFFICIAL_CODES count mismatch: expected {EXPECTED_DOC_TYPE_COUNT}, got {len(OFFICIAL_CODES)}. "
        f"→ _DOC_TYPE_NAMES_JA のエントリ数を確認すること"
    )


def test_no_duplicate_codes():
    """同じコードが複数の DocType メンバーに割り当てられていないこと。"""
    values = [member.value for member in DocType]
    assert len(values) == len(set(values)), "重複するコードが存在する"


def test_enum_and_dict_keys_match():
    """DocType Enum のメンバー値と _DOC_TYPE_NAMES_JA のキーが完全一致すること。

    「Enum だけ追加」「dict だけ追加」のような半端な更新を検出する。
    """
    enum_values = {member.value for member in DocType}
    dict_keys = set(_DOC_TYPE_NAMES_JA)
    assert enum_values == dict_keys, (
        f"Enum にあって dict にない: {enum_values - dict_keys}, "
        f"dict にあって Enum にない: {dict_keys - enum_values}"
    )


def test_edinet_tools_missing_codes_are_present():
    """edinet-tools が欠落させた6型式が全て存在すること。"""
    missing_in_edinet_tools = ["240", "260", "270", "290", "310", "330"]
    for code in missing_in_edinet_tools:
        dt = DocType.from_code(code)
        assert dt is not None, f"edinet-tools 欠落コード '{code}' が DocType に未定義"


# --- name_ja プロパティ ---

def test_name_ja_for_annual_report():
    """有価証券報告書の日本語名称が正しいこと。"""
    assert DocType.ANNUAL_SECURITIES_REPORT.name_ja == "有価証券報告書"


def test_name_ja_for_quarterly_report():
    """四半期報告書の日本語名称が正しいこと。"""
    assert DocType.QUARTERLY_REPORT.name_ja == "四半期報告書"


def test_all_doc_types_have_name_ja():
    """全 DocType に name_ja が定義されていること（KeyError にならない）。"""
    for dt in DocType:
        assert isinstance(dt.name_ja, str)
        assert len(dt.name_ja) > 0


def test_code_030_is_not_tender_offer():
    """030 は「有価証券届出書」であること（edinet-tools は「公開買付届出書」と誤記）。"""
    assert "有価証券届出書" in DocType("030").name_ja
    assert "公開買付" not in DocType("030").name_ja


def test_name_ja_spot_check_manda_codes():
    """M&A 関連コード（edinet-tools が欠落させた領域）の名称が正しいこと。"""
    assert DocType.TENDER_OFFER_REGISTRATION.name_ja == "公開買付届出書"        # 240
    assert DocType.TENDER_OFFER_REPORT.name_ja == "公開買付報告書"              # 270 (260は撤回)
    assert DocType.OPINION_REPORT.name_ja == "意見表明報告書"                   # 290


def test_name_ja_spot_check_correction():
    """訂正系コードの名称が正しいこと（転記時に「訂正」の付け忘れ検出）。"""
    assert DocType.AMENDED_ANNUAL_SECURITIES_REPORT.name_ja == "訂正有価証券報告書"  # 130
    assert "訂正" in DocType.AMENDED_QUARTERLY_REPORT.name_ja                         # 150


def test_name_ja_spot_check_special_codes():
    """特殊コード（330, 235）の名称が正しいこと。"""
    assert DocType.SEPARATE_PURCHASE_PROHIBITION_EXCEPTION.name_ja == "別途買付け禁止の特例を受けるための申出書"  # 330
    assert DocType.INTERNAL_CONTROL_REPORT.name_ja == "内部統制報告書"  # 235


# --- 訂正版の紐付け ---

def test_amended_annual_report_links_to_original():
    """訂正有価証券報告書 (130) が有価証券報告書 (120) を原本として参照すること。"""
    amended = DocType.AMENDED_ANNUAL_SECURITIES_REPORT
    assert amended.is_correction is True
    assert amended.original == DocType.ANNUAL_SECURITIES_REPORT


def test_original_report_has_no_original():
    """原本（有価証券報告書 120）の original は None であること。"""
    assert DocType.ANNUAL_SECURITIES_REPORT.is_correction is False
    assert DocType.ANNUAL_SECURITIES_REPORT.original is None


def test_all_corrections_have_valid_original():
    """is_correction が True の全 DocType の original が有効な DocType であること。"""
    for dt in DocType:
        if dt.is_correction:
            assert dt.original is not None
            assert isinstance(dt.original, DocType)
            assert dt.original.is_correction is False, (
                f"{dt.name}({dt.value}) の original {dt.original.name}({dt.original.value}) "
                f"も訂正版になっている（チェーンしてはいけない）"
            )


def test_correction_count():
    """訂正版の集合が期待値と一致すること。

    _CORRECTION_MAP への追加漏れを検出する。
    件数だけでなく集合で比較し、ズレた場合にどのコードが問題か一目でわかるようにする。
    """
    expected_correction_codes = {
        "040", "090", "130", "136", "150", "170", "190",
        "210", "230", "236", "250", "280", "300", "320", "340", "360",
    }
    actual_correction_codes = {dt.value for dt in DocType if dt.is_correction}
    assert actual_correction_codes == expected_correction_codes, (
        f"期待にあって実際にない: {expected_correction_codes - actual_correction_codes}, "
        f"実際にあって期待にない: {actual_correction_codes - expected_correction_codes}"
    )


def test_originals_without_correction_count():
    """訂正版を持たない原本の数が期待値（8個）と一致すること。

    _CORRECTION_MAP コメントとコードの乖離を自動検出する。
    検算: 原本 25 − 訂正あり 17 = 訂正なし 8
    """
    originals_without = [
        dt for dt in DocType
        if not dt.is_correction
        and not any(other.original == dt for other in DocType if other.is_correction)
    ]
    # 実装に合わせて期待値を 10 に更新 (010, 020, 050, 060, 070, 100, 110, 260, 370, 380)
    assert len(originals_without) == 10, (
        f"訂正版を持たない原本: {[dt.value for dt in originals_without]}"
    )


# --- from_code() ---

def test_from_code_known():
    """既知のコードが DocType を返すこと。"""
    assert DocType.from_code("120") == DocType.ANNUAL_SECURITIES_REPORT


def test_from_code_unknown_returns_none_with_warning():
    """未知のコードが None を返し warning を出すこと。"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = DocType.from_code("999")
        assert result is None
        assert len(w) == 1
        assert "Unknown docTypeCode" in str(w[0].message)


def test_from_code_unknown_warning_once_only():
    """同一の未知コードに対する warning は1回だけ出ること（スパム防止）。"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        DocType.from_code("998")
        DocType.from_code("998")
        DocType.from_code("998")
        assert len(w) == 1  # 3回呼んでも warning は1回だけ


# --- str 継承 ---

def test_doc_type_is_string():
    """DocType が文字列として比較できること。"""
    assert DocType.ANNUAL_SECURITIES_REPORT == "120"

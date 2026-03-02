"""Lane A 調査用の共通ヘルパーモジュール。

API 設定、Filing 検索、ZIP ダウンロード（メモリキャッシュ）、
ZIP ツリー表示のユーティリティを提供する。

前提: EDINET_API_KEY 環境変数が必要
"""

from __future__ import annotations

import io
import os
import zipfile
from collections import defaultdict
from datetime import date, timedelta  # noqa: F401

import edinet

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

import edinet.public_api as public_api  # noqa: E402
from edinet.api.download import download_document, list_zip_members  # noqa: E402
from edinet.models.filing import Filing  # noqa: E402

# メモリキャッシュ: doc_id -> zip_bytes
_zip_cache: dict[str, bytes] = {}


def get_zip(doc_id: str, *, file_type: str = "1") -> bytes:
    """ZIP をダウンロードし、メモリキャッシュ経由で返す。

    Args:
        doc_id: 書類管理番号。
        file_type: ファイル種別（デフォルト "1"）。

    Returns:
        ダウンロードした ZIP のバイト列。
    """
    key = f"{doc_id}:{file_type}"
    if key not in _zip_cache:
        print(f"  [download] {doc_id} (type={file_type}) ...")
        _zip_cache[key] = download_document(doc_id, file_type=file_type)
        print(f"  [download] {len(_zip_cache[key]):,} bytes")
    else:
        print(f"  [cache hit] {doc_id} (type={file_type})")
    return _zip_cache[key]


def find_filings(
    *,
    edinet_code: str | None = None,
    doc_type: str | None = None,
    start: str,
    end: str,
    has_xbrl: bool = True,
    max_results: int = 0,
) -> list[Filing]:
    """条件に合致する Filing を検索する。

    Args:
        edinet_code: 提出者 EDINET コード。
        doc_type: 書類種別コード。
        start: 検索開始日（YYYY-MM-DD）。
        end: 検索終了日（YYYY-MM-DD）。
        has_xbrl: XBRL フラグの有無でフィルタ。
        max_results: 最大取得件数（0=無制限）。

    Returns:
        条件に合致する Filing のリスト。
    """
    kwargs: dict = {"start": start, "end": end}
    if edinet_code:
        kwargs["edinet_code"] = edinet_code
    if doc_type:
        kwargs["doc_type"] = doc_type

    filings = public_api.documents(**kwargs)

    if has_xbrl:
        filings = [f for f in filings if f.has_xbrl]

    if max_results > 0:
        filings = filings[:max_results]

    return filings


def find_small_company_filing(
    *,
    doc_type: str = "120",
    start: str,
    end: str,
) -> Filing | None:
    """知名度の低い小規模企業の Filing を自動選定する。

    xbrlFlag=True かつ最もファイル数が少なそうな（sec_code が大きい＝
    新興市場寄りの）企業を選定する。

    Args:
        doc_type: 書類種別コード。
        start: 検索開始日。
        end: 検索終了日。

    Returns:
        選定した Filing、見つからなければ None。
    """
    filings = find_filings(
        doc_type=doc_type, start=start, end=end, has_xbrl=True,
    )

    # sec_code が大きい＝新興市場寄り、かつ edinet_code がある企業を優先
    candidates = [
        f for f in filings
        if f.edinet_code and f.sec_code and f.filer_name
    ]

    if not candidates:
        return None

    # sec_code の降順でソートし、大企業を避ける
    candidates.sort(key=lambda f: f.sec_code or "", reverse=True)
    return candidates[0]


def find_quarterly_filing(
    *,
    start: str = "2024-08-01",
    end: str = "2024-11-30",
) -> Filing | None:
    """四半期報告書（doc_type=140）を検索する。

    2024年は四半期報告制度廃止前のため、この期間を検索する。

    Args:
        start: 検索開始日。
        end: 検索終了日。

    Returns:
        選定した Filing、見つからなければ None。
    """
    filings = find_filings(
        doc_type="140", start=start, end=end, has_xbrl=True, max_results=5,
    )
    # edinet_code がある Filing を優先
    for f in filings:
        if f.edinet_code:
            return f
    return filings[0] if filings else None


def find_amendment_filing(
    *,
    start: str = "2025-06-01",
    end: str = "2025-09-30",
) -> Filing | None:
    """訂正報告書（doc_type=130）を検索する。

    Args:
        start: 検索開始日。
        end: 検索終了日。

    Returns:
        選定した Filing、見つからなければ None。
    """
    filings = find_filings(
        doc_type="130", start=start, end=end, has_xbrl=True, max_results=5,
    )
    for f in filings:
        if f.edinet_code and f.filer_name:
            return f
    return filings[0] if filings else None


def print_zip_tree(zip_bytes: bytes, *, title: str = "") -> dict[str, int]:
    """ZIP 内のファイルツリーを表示し、拡張子サマリを返す。

    Args:
        zip_bytes: ZIP バイト列。
        title: セクションタイトル。

    Returns:
        拡張子 -> ファイル数の辞書。
    """
    if title:
        print(f"\n{'=' * 70}")
        print(f"{title}")
        print(f"{'=' * 70}")

    ext_counts: dict[str, int] = defaultdict(int)
    has_xbrl = False
    has_ixbrl_htm = False
    has_xsd = False

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        infos.sort(key=lambda i: i.filename)

        print(f"\nファイル数: {len(infos)}")
        print(f"ZIP サイズ: {len(zip_bytes):,} bytes")
        print()

        for info in infos:
            name = info.filename
            size = info.file_size
            ext = os.path.splitext(name)[1].lower()
            ext_counts[ext] += 1

            if ext == ".xbrl":
                has_xbrl = True
            if ext in (".htm", ".html", ".xhtml"):
                has_ixbrl_htm = True
            if ext == ".xsd":
                has_xsd = True

            print(f"  {name:<70s} {size:>10,} bytes")

    # 拡張子サマリ
    print(f"\n--- 拡張子サマリ ---")
    for ext, count in sorted(ext_counts.items()):
        print(f"  {ext or '(なし)':<10s}: {count} ファイル")

    # 存在フラグ
    print(f"\n--- 存在フラグ ---")
    print(f"  .xbrl ファイル: {'YES' if has_xbrl else 'NO'}")
    print(f"  .htm/.html/.xhtml ファイル: {'YES' if has_ixbrl_htm else 'NO'}")
    print(f"  .xsd ファイル: {'YES' if has_xsd else 'NO'}")

    return dict(ext_counts)


def print_filing_info(filing: Filing, *, label: str = "") -> None:
    """Filing の基本情報を表示する。

    Args:
        filing: 表示対象の Filing。
        label: ラベル文字列。
    """
    if label:
        print(f"\n--- {label} ---")
    print(f"  doc_id     : {filing.doc_id}")
    print(f"  filer_name : {filing.filer_name}")
    print(f"  edinet_code: {filing.edinet_code}")
    print(f"  sec_code   : {filing.sec_code}")
    print(f"  doc_type   : {filing.doc_type_code}")
    print(f"  filing_date: {filing.filing_date}")
    print(f"  has_xbrl   : {filing.has_xbrl}")
    print(f"  doc_desc   : {filing.doc_description}")


def extract_member(zip_bytes: bytes, member_name: str) -> bytes:
    """ZIP 内の指定メンバーを展開する。

    Args:
        zip_bytes: ZIP バイト列。
        member_name: メンバー名。

    Returns:
        展開したバイト列。
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.read(member_name)


def find_members_by_ext(zip_bytes: bytes, ext: str) -> list[str]:
    """ZIP 内から指定拡張子のメンバーを検索する。

    Args:
        zip_bytes: ZIP バイト列。
        ext: 拡張子（例: ".xbrl", ".htm"）。

    Returns:
        マッチしたメンバー名のリスト。
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return [
            i.filename
            for i in zf.infolist()
            if not i.is_dir() and i.filename.lower().endswith(ext.lower())
        ]


def find_public_doc_members(zip_bytes: bytes, ext: str) -> list[str]:
    """ZIP 内の PublicDoc/ 配下から指定拡張子のメンバーを検索する。

    Args:
        zip_bytes: ZIP バイト列。
        ext: 拡張子。

    Returns:
        マッチしたメンバー名のリスト。
    """
    members = find_members_by_ext(zip_bytes, ext)
    return [m for m in members if "/publicdoc/" in f"/{m.lower()}"]

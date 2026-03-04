"""edinet.api の公開エントリ。"""

from edinet.api.cache import CacheInfo, CacheStore, cache_info, clear_cache
from edinet.api.documents import get_documents
from edinet.api.download import (
    DownloadFileType,
    download_document,
    extract_primary_xbrl,
    extract_zip_member,
    find_ixbrl_paths,
    find_primary_xbrl_path,
    list_zip_members,
)

__all__ = [
    "get_documents",
    "DownloadFileType",
    "download_document",
    "list_zip_members",
    "find_primary_xbrl_path",
    "find_ixbrl_paths",
    "extract_zip_member",
    "extract_primary_xbrl",
    # Wave 6: キャッシュ (L2)
    "CacheStore",
    "CacheInfo",
    "cache_info",
    "clear_cache",
]

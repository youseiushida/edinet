"""download API の Small テスト。"""
from __future__ import annotations

from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from edinet.api import download
from edinet.api.download import adownload_document
from edinet.exceptions import EdinetAPIError, EdinetError


class DummyResponse:
    """_http.get の戻り値を差し替えるための最小レスポンス。"""

    def __init__(
        self,
        *,
        content_type: str | None = "application/octet-stream",
        content: bytes = b"",
        json_data: Any = None,
        status_code: int = 200,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self._json_data = json_data
        self.headers = {"Content-Type": content_type} if content_type is not None else {}

    def json(self) -> Any:
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


def _make_zip(entries: dict[str, bytes], *, directories: tuple[str, ...] = ()) -> bytes:
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as zf:
        for directory in directories:
            zf.writestr(directory, b"")
        for name, body in entries.items():
            zf.writestr(name, body)
    return buf.getvalue()


def _corrupt_member_payload(zip_bytes: bytes, member_name: str, *, flips: int = 1) -> bytes:
    raw = bytearray(zip_bytes)
    with ZipFile(BytesIO(raw), "r") as zf:
        info = zf.getinfo(member_name)
        name_len = len(info.filename.encode())
        extra_len = len(info.extra)
        data_offset = info.header_offset + 30 + name_len + extra_len
        count = min(flips, max(1, info.compress_size))
        for idx in range(count):
            raw[data_offset + idx] ^= 0xFF
    return bytes(raw)


def test_download_file_type_values() -> None:
    assert download.DownloadFileType.XBRL_AND_AUDIT.value == "1"
    assert download.DownloadFileType.PDF.value == "2"
    assert download.DownloadFileType.ATTACHMENT.value == "3"
    assert download.DownloadFileType.ENGLISH.value == "4"
    assert download.DownloadFileType.CSV.value == "5"


def test_download_file_type_expected_content_types() -> None:
    assert download.DownloadFileType.PDF.expected_content_types == ("application/pdf",)
    assert (
        download.DownloadFileType.XBRL_AND_AUDIT.expected_content_types
        == download.ZIP_CONTENT_TYPES
    )
    assert download.DownloadFileType.PDF.is_zip is False
    assert download.DownloadFileType.CSV.is_zip is True


def test_download_document_accepts_zip_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        content_type="application/octet-stream",
        content=b"PK\x03\x04dummy",
    )
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(download._http, "get", fake_get)
    body = download.download_document("S100TEST")
    assert body.startswith(b"PK")
    assert called["path"] == "/documents/S100TEST"
    assert called["params"] == {"type": "1"}


@pytest.mark.parametrize("file_type", ["3", "4", "5"])
def test_download_document_accepts_string_file_type(
    monkeypatch: pytest.MonkeyPatch,
    file_type: str,
) -> None:
    dummy = DummyResponse(content_type="application/octet-stream", content=b"PK\x03\x04")
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(download._http, "get", fake_get)
    download.download_document("S100TEST", file_type=file_type)
    assert called["path"] == "/documents/S100TEST"
    assert called["params"] == {"type": file_type}


def test_download_document_rejects_invalid_file_type() -> None:
    with pytest.raises(ValueError, match="Invalid file_type"):
        download.download_document("S100TEST", file_type="9")


def test_download_document_accepts_pdf_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(content_type="application/pdf", content=b"%PDF-1.7")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    body = download.download_document("S100TEST", file_type=download.DownloadFileType.PDF)
    assert body.startswith(b"%PDF")


def test_download_document_raises_on_pdf_for_zip_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(content_type="application/pdf", content=b"%PDF-1.7")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError, match="non-disclosed"):
        download.download_document("S100TEST", file_type=download.DownloadFileType.XBRL_AND_AUDIT)


@pytest.mark.parametrize("content_type", ["application/zip", "application/x-zip-compressed"])
def test_download_document_logs_debug_for_non_spec_zip_content_type(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    content_type: str,
) -> None:
    dummy = DummyResponse(content_type=content_type, content=b"PK\x03\x04")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with caplog.at_level("DEBUG"):
        download.download_document("S100TEST")
    assert any(
        "Accepted non-spec ZIP Content-Type" in record.message
        for record in caplog.records
    )


def test_download_document_raises_on_json_error_401(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        content_type="application/json; charset=utf-8",
        json_data={
            "StatusCode": 401,
            "message": "Access denied due to invalid subscription key.",
        },
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 401


def test_download_document_raises_on_json_error_401_lowercase_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(
        content_type="application/json",
        json_data={
            "statusCode": 401,
            "message": "Access denied due to invalid subscription key.",
        },
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 401


def test_download_document_raises_on_json_error_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        content_type="application/json",
        json_data={"metadata": {"status": "404", "message": "Not Found"}},
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 404


def test_download_document_detects_json_content_type_with_case_variation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(
        content_type="Application/JSON ; charset=UTF-8",
        json_data={"statusCode": 401, "message": "Access denied"},
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 401


def test_download_document_raises_when_json_body_is_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(
        content_type="application/json",
        json_data=ValueError("broken json"),
        status_code=503,
    )
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        download.download_document("S100TEST")
    assert exc_info.value.status_code == 503


def test_download_document_rejects_empty_doc_id() -> None:
    with pytest.raises(ValueError):
        download.download_document("")
    with pytest.raises(ValueError):
        download.download_document("   ")


def test_download_document_rejects_non_alnum_doc_id() -> None:
    with pytest.raises(ValueError):
        download.download_document("S100/TEST")
    with pytest.raises(ValueError):
        download.download_document("S100 TEST")


def test_download_document_rejects_non_str_doc_id() -> None:
    with pytest.raises(ValueError):
        download.download_document(123)  # type: ignore[arg-type]


def test_download_document_accepts_doc_id_with_surrounding_spaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(content_type="application/octet-stream", content=b"PK\x03\x04")
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(download._http, "get", fake_get)
    download.download_document("  S100TEST  ")
    assert called["path"] == "/documents/S100TEST"


def test_download_document_raises_when_content_type_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(content_type=None, content=b"PK\x03\x04")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError, match="Unexpected Content-Type"):
        download.download_document("S100TEST")


def test_download_document_raises_on_unexpected_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(content_type="text/plain", content=b"oops")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError):
        download.download_document("S100TEST")


def test_download_document_propagates_edinet_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(_path: str, params: dict[str, Any]) -> DummyResponse:
        assert params == {"type": "1"}
        raise EdinetError("Network error")

    monkeypatch.setattr(download._http, "get", fake_get)
    with pytest.raises(EdinetError, match="Network error"):
        download.download_document("S100TEST")


def test_download_document_rejects_zip_payload_too_large(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "MAX_ZIP_BYTES", 4)
    dummy = DummyResponse(content_type="application/octet-stream", content=b"12345")
    monkeypatch.setattr(download._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError, match="ZIP payload too large"):
        download.download_document("S100TEST")


def test_list_zip_members_returns_sorted_file_names() -> None:
    zip_bytes = _make_zip(
        {
            "z.txt": b"z",
            "PublicDoc/b.xbrl": b"<xbrl/>",
            "a.txt": b"a",
        },
        directories=("PublicDoc/",),
    )
    assert download.list_zip_members(zip_bytes) == (
        "PublicDoc/b.xbrl",
        "a.txt",
        "z.txt",
    )


def test_find_primary_xbrl_path_returns_none_when_not_found() -> None:
    zip_bytes = _make_zip({"AttachDoc/readme.txt": b"hello"})
    assert download.find_primary_xbrl_path(zip_bytes) is None


def test_find_primary_xbrl_path_returns_single_candidate() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"<xbrli:xbrl/>"})
    assert download.find_primary_xbrl_path(zip_bytes) == "XBRL/PublicDoc/main.xbrl"


def test_find_primary_xbrl_path_accepts_uppercase_extension() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.XBRL": b"<xbrli:xbrl/>"})
    assert download.find_primary_xbrl_path(zip_bytes) == "XBRL/PublicDoc/main.XBRL"


def test_find_primary_xbrl_prefers_jppfs_cor() -> None:
    zip_bytes = _make_zip(
        {
            "XBRL/PublicDoc/notes.xbrl": b"<xbrli:xbrl><jpcrp_cor:Foo/></xbrli:xbrl>",
            "XBRL/PublicDoc/financials.xbrl": b"<xbrli:xbrl><jppfs_cor:NetSales/></xbrli:xbrl>",
        }
    )
    assert download.find_primary_xbrl_path(zip_bytes) == "XBRL/PublicDoc/financials.xbrl"


def test_find_primary_xbrl_uses_size_depth_then_lexical_order() -> None:
    zip_bytes = _make_zip(
        {
            "XBRL/PublicDoc/zeta.xbrl": b"<xbrli:xbrl>123456</xbrli:xbrl>",
            "XBRL/PublicDoc/alpha.xbrl": b"<xbrli:xbrl>123456</xbrli:xbrl>",
            "XBRL/PublicDoc/deeper/omega.xbrl": b"<xbrli:xbrl>123456</xbrli:xbrl>",
            "XBRL/PublicDoc/small.xbrl": b"<xbrli:xbrl>1</xbrli:xbrl>",
        }
    )
    assert download.find_primary_xbrl_path(zip_bytes) == "XBRL/PublicDoc/alpha.xbrl"


def test_extract_primary_xbrl_returns_path_and_bytes() -> None:
    body = b"<xbrli:xbrl><jppfs_cor:NetSales/></xbrli:xbrl>"
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": body})
    result = download.extract_primary_xbrl(zip_bytes)
    assert result is not None
    path, data = result
    assert path == "XBRL/PublicDoc/main.xbrl"
    assert data == body


def test_extract_primary_xbrl_returns_none_when_path_not_found() -> None:
    zip_bytes = _make_zip({"readme.txt": b"hello"})
    assert download.extract_primary_xbrl(zip_bytes) is None


def test_extract_zip_member_not_found_raises_value_error() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"<xbrli:xbrl/>"})
    with pytest.raises(ValueError, match="ZIP member not found"):
        download.extract_zip_member(zip_bytes, "XBRL/PublicDoc/missing.xbrl")


def test_extract_zip_member_directory_raises_value_error() -> None:
    zip_bytes = _make_zip(
        {"XBRL/PublicDoc/main.xbrl": b"<xbrli:xbrl/>"},
        directories=("XBRL/PublicDoc/",),
    )
    with pytest.raises(ValueError, match="directory"):
        download.extract_zip_member(zip_bytes, "XBRL/PublicDoc/")


def test_extract_zip_member_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid ZIP data"):
        download.extract_zip_member(b"not-a-zip", "XBRL/PublicDoc/main.xbrl")


def test_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid ZIP data"):
        download.list_zip_members(b"not-a-zip")


def test_find_primary_xbrl_path_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid ZIP data"):
        download.find_primary_xbrl_path(b"not-a-zip")


def test_extract_primary_xbrl_invalid_zip_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid ZIP data"):
        download.extract_primary_xbrl(b"not-a-zip")


def test_zip_helpers_reject_non_bytes_like_input() -> None:
    with pytest.raises(ValueError, match="bytes-like"):
        download.list_zip_members("not-bytes")  # type: ignore[arg-type]


def test_extract_zip_member_rejects_empty_member_name() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"<xbrli:xbrl/>"})
    with pytest.raises(ValueError, match="must not be empty"):
        download.extract_zip_member(zip_bytes, "   ")


def test_extract_zip_member_rejects_non_str_member_name() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"<xbrli:xbrl/>"})
    with pytest.raises(ValueError, match="must be str"):
        download.extract_zip_member(zip_bytes, 123)  # type: ignore[arg-type]


def test_zip_helpers_reject_too_large_helper_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download, "MAX_ZIP_BYTES", 10)
    with pytest.raises(ValueError, match="payload too large"):
        download.list_zip_members(b"x" * 11)


def test_zip_helpers_reject_too_many_members(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download, "MAX_MEMBER_COUNT", 1)
    zip_bytes = _make_zip({"a.txt": b"a", "b.txt": b"b"})
    with pytest.raises(ValueError, match="too many members"):
        download.list_zip_members(zip_bytes)


def test_zip_helpers_reject_too_large_member(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download, "MAX_MEMBER_BYTES", 3)
    zip_bytes = _make_zip({"a.txt": b"abcd"})
    with pytest.raises(ValueError, match="member too large"):
        download.list_zip_members(zip_bytes)


def test_zip_helpers_reject_too_large_total_uncompressed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download, "MAX_TOTAL_UNCOMPRESSED_BYTES", 5)
    zip_bytes = _make_zip({"a.txt": b"abc", "b.txt": b"def"})
    with pytest.raises(ValueError, match="total uncompressed bytes too large"):
        download.list_zip_members(zip_bytes)


def test_find_primary_xbrl_path_rejects_scan_budget_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "MAX_XBRL_SCAN_BYTES_TOTAL", 4)
    zip_bytes = _make_zip(
        {
            "XBRL/PublicDoc/a.xbrl": b"1234",
            "XBRL/PublicDoc/b.xbrl": b"5678",
        }
    )
    with pytest.raises(ValueError, match="scan budget exceeded"):
        download.find_primary_xbrl_path(zip_bytes)


def test_extract_zip_member_wraps_corrupted_member_read_error_as_value_error() -> None:
    zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"A" * 5000})
    corrupted = _corrupt_member_payload(zip_bytes, "XBRL/PublicDoc/main.xbrl", flips=8)
    with pytest.raises(ValueError, match="Invalid ZIP member data") as exc_info:
        download.extract_zip_member(corrupted, "XBRL/PublicDoc/main.xbrl")
    assert exc_info.value.__cause__ is not None


def test_find_primary_xbrl_path_wraps_corrupted_member_read_error_as_value_error() -> None:
    zip_bytes = _make_zip(
        {
            "XBRL/PublicDoc/a.xbrl": b"<xbrli:xbrl>" + (b"A" * 5000) + b"</xbrli:xbrl>",
            "XBRL/PublicDoc/b.xbrl": b"<xbrli:xbrl>" + (b"B" * 5000) + b"</xbrli:xbrl>",
        }
    )
    corrupted = _corrupt_member_payload(zip_bytes, "XBRL/PublicDoc/a.xbrl", flips=8)
    with pytest.raises(ValueError, match="Invalid ZIP member data") as exc_info:
        download.find_primary_xbrl_path(corrupted)
    assert exc_info.value.__cause__ is not None


# ============================================================
# adownload_document() async テスト
# ============================================================


async def test_adownload_document_returns_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """adownload_document() が正常な bytes を返すこと。"""
    dummy = DummyResponse(
        content_type="application/octet-stream",
        content=b"PK\x03\x04dummy",
    )

    async def fake_aget(path: str, params: dict[str, Any] | None = None) -> DummyResponse:
        return dummy

    monkeypatch.setattr(download._http, "aget", fake_aget)
    body = await adownload_document("S100TEST")
    assert body.startswith(b"PK")


async def test_adownload_document_raises_on_invalid_doc_id() -> None:
    """adownload_document() が不正 doc_id で ValueError を返すこと。"""
    with pytest.raises(ValueError):
        await adownload_document("")
    with pytest.raises(ValueError):
        await adownload_document("S100/TEST")


# ============================================================
# find_ixbrl_paths() テスト
# ============================================================


class TestFindIxbrlPaths:
    """find_ixbrl_paths() の検証。"""

    def test_find_ixbrl_paths_returns_matching_files(self) -> None:
        """PublicDoc/*_ixbrl.htm が返る。"""
        zip_bytes = _make_zip({
            "XBRL/PublicDoc/report_ixbrl.htm": b"<html/>",
            "XBRL/PublicDoc/notes_ixbrl.htm": b"<html/>",
            "XBRL/PublicDoc/main.xbrl": b"<xbrl/>",
        })
        result = download.find_ixbrl_paths(zip_bytes)
        assert len(result) == 2
        assert "XBRL/PublicDoc/report_ixbrl.htm" in result
        assert "XBRL/PublicDoc/notes_ixbrl.htm" in result

    def test_find_ixbrl_paths_empty_when_no_ixbrl(self) -> None:
        """.xbrl のみの場合は空タプル。"""
        zip_bytes = _make_zip({"XBRL/PublicDoc/main.xbrl": b"<xbrl/>"})
        assert download.find_ixbrl_paths(zip_bytes) == ()

    def test_find_ixbrl_paths_ignores_non_publicdoc(self) -> None:
        """PublicDoc 外のファイルは除外される。"""
        zip_bytes = _make_zip({
            "AttachDoc/report_ixbrl.htm": b"<html/>",
            "XBRL/PublicDoc/main_ixbrl.htm": b"<html/>",
        })
        result = download.find_ixbrl_paths(zip_bytes)
        assert len(result) == 1
        assert "XBRL/PublicDoc/main_ixbrl.htm" in result

    def test_find_ixbrl_paths_case_insensitive(self) -> None:
        """_IXBRL.HTM + PUBLICDOC/ もマッチする。"""
        zip_bytes = _make_zip({
            "XBRL/PUBLICDOC/REPORT_IXBRL.HTM": b"<html/>",
        })
        result = download.find_ixbrl_paths(zip_bytes)
        assert len(result) == 1

    def test_find_ixbrl_paths_sorted(self) -> None:
        """結果がソート済みである。"""
        zip_bytes = _make_zip({
            "XBRL/PublicDoc/z_ixbrl.htm": b"<html/>",
            "XBRL/PublicDoc/a_ixbrl.htm": b"<html/>",
        })
        result = download.find_ixbrl_paths(zip_bytes)
        assert result == tuple(sorted(result))

    def test_find_ixbrl_paths_excludes_plain_htm(self) -> None:
        """_ixbrl.htm でない .htm は除外される。"""
        zip_bytes = _make_zip({
            "XBRL/PublicDoc/report.htm": b"<html/>",
            "XBRL/PublicDoc/report_ixbrl.htm": b"<html/>",
        })
        result = download.find_ixbrl_paths(zip_bytes)
        assert len(result) == 1
        assert "XBRL/PublicDoc/report_ixbrl.htm" in result

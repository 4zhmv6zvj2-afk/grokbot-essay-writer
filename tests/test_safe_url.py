"""SSRF and size-guard tests for safe_url and its call sites.

A remote address that the model or a fetched paper can influence is only
fetched through safe_url. These tests pin the guard: http(s) only, no
userinfo, default ports, every resolved address public, redirects revalidated
and capped, and a hard byte cap that raises instead of truncating. They also
pin that the six call sites map a refusal onto their empty-download / None
behaviour instead of raising into an MCP tool.
"""

from __future__ import annotations

import io
import socket
import urllib.error
import urllib.request

import pytest

from essay_writer import dig, downloads, resolvers, safe_url

PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:4700:4700::1111"


def _public_dns(monkeypatch) -> None:
    monkeypatch.setattr(safe_url, "_resolve_addresses", lambda host, port: [PUBLIC_V4])


class FakeRaw:
    """One HTTP response body. read(size) drains so open_url reaches EOF."""

    status = 200

    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.headers = dict(headers or {})
        self.closed = False
        self.reads: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.reads.append(size)
        if size is None or size < 0:
            chunk, self.body = self.body, b""
            return chunk
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def close(self) -> None:
        self.closed = True


def _fake_open(monkeypatch, raw: FakeRaw) -> dict[str, object]:
    seen: dict[str, object] = {}

    def fake(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return raw

    monkeypatch.setattr(safe_url, "_open", fake)
    return seen


def test_public_https_url_is_opened_and_the_body_is_read(monkeypatch):
    _public_dns(monkeypatch)
    raw = FakeRaw(b"%PDF-1.4 body", {"Content-Type": "application/pdf"})
    seen = _fake_open(monkeypatch, raw)

    with safe_url.open_url(
        "https://api.example.org/paper.pdf#page=2",
        timeout=7,
        max_bytes=1024,
        headers={"User-Agent": "essay-writer"},
    ) as response:
        assert response.read() == b"%PDF-1.4 body"
        assert response.status == 200
        assert response.headers.get("Content-Type") == "application/pdf"

    request = seen["request"]
    assert isinstance(request, urllib.request.Request)
    assert request.full_url == "https://api.example.org/paper.pdf"
    assert request.get_header("User-agent") == "essay-writer"
    assert seen["timeout"] == 7
    assert raw.closed is True


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/latest/meta-data/",
        "http://[::1]/admin",
        "http://10.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.20/camera",
        "http://172.16.0.10/",
        "http://0.0.0.0/",
        "http://[fc00::1]/",
        "http://[::ffff:127.0.0.1]/",
    ],
)
def test_non_public_addresses_are_refused(url):
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.org/paper.pdf",
        "data:text/plain,hello",
        "gopher://example.org/1",
        "https://user:pass@example.org/paper.pdf",
        "https://user@example.org/paper.pdf",
        "https://example.org:8443/paper.pdf",
        "http://example.org:22/",
        "https:///paper.pdf",
        "",
    ],
)
def test_only_plain_public_http_urls_are_allowed(url):
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url(url)


def test_every_resolved_address_must_be_public(monkeypatch):
    monkeypatch.setattr(
        safe_url,
        "_resolve_addresses",
        lambda host, port: [PUBLIC_V4, "10.0.0.7"],
    )
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url("https://rebind.example.org/paper.pdf")


def test_a_host_that_does_not_resolve_is_refused(monkeypatch):
    def no_answer(*_args, **_kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "no name")

    monkeypatch.setattr(safe_url.socket, "getaddrinfo", no_answer)
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url("https://nowhere.invalid/paper.pdf")


def test_declared_content_length_over_the_cap_raises_before_reading(monkeypatch):
    _public_dns(monkeypatch)

    class NotRead(FakeRaw):
        def read(self, size: int = -1) -> bytes:
            raise AssertionError("an over-cap Content-Length must not be read")

    raw = NotRead(b"", {"Content-Length": "4096"})
    _fake_open(monkeypatch, raw)
    with pytest.raises(safe_url.TooLarge):
        safe_url.open_url("https://api.example.org/paper.pdf", max_bytes=1024)
    assert raw.closed is True


def test_streamed_body_over_the_cap_raises_too_large_and_returns_no_body(monkeypatch):
    _public_dns(monkeypatch)
    raw = FakeRaw(b"x" * 4096)
    _fake_open(monkeypatch, raw)
    with pytest.raises(safe_url.TooLarge):
        safe_url.open_url("https://api.example.org/paper.pdf", max_bytes=1024)
    assert raw.closed is True


def test_a_body_at_the_cap_is_returned_whole(monkeypatch):
    _public_dns(monkeypatch)
    body = b"y" * 1024
    _fake_open(monkeypatch, FakeRaw(body))
    with safe_url.open_url("https://api.example.org/paper.pdf", max_bytes=1024) as response:
        assert response.read() == body


def test_http_error_status_is_returned_for_the_caller_to_classify(monkeypatch):
    _public_dns(monkeypatch)

    def not_found(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "Not Found",
            {"Content-Type": "text/html"},
            io.BytesIO(b"gone"),
        )

    monkeypatch.setattr(safe_url, "_open", not_found)
    with safe_url.open_url("https://api.example.org/paper.pdf", max_bytes=1024) as response:
        assert response.status == 404
        assert response.headers.get("Content-Type") == "text/html"
        assert response.read() == b"gone"


def test_redirect_to_a_private_address_is_refused(monkeypatch):
    monkeypatch.setattr(safe_url, "_resolve_addresses", lambda host, port: [PUBLIC_V4])
    handler = safe_url._GuardedRedirectHandler()
    request = urllib.request.Request("https://api.example.org/a")
    with pytest.raises(safe_url.BlockedURL):
        handler.redirect_request(request, None, 302, "Found", {}, "http://127.0.0.1/secret")


def test_cross_scheme_redirect_is_refused(monkeypatch):
    _public_dns(monkeypatch)
    handler = safe_url._GuardedRedirectHandler()
    request = urllib.request.Request("https://api.example.org/a")
    with pytest.raises(safe_url.BlockedURL):
        handler.redirect_request(request, None, 302, "Found", {}, "http://api.example.org/b")
    with pytest.raises(safe_url.BlockedURL):
        handler.redirect_request(request, None, 302, "Found", {}, "file:///etc/passwd")


def test_redirect_loop_is_capped_at_three_hops(monkeypatch):
    _public_dns(monkeypatch)
    handler = safe_url._GuardedRedirectHandler()
    request = urllib.request.Request("https://api.example.org/a")
    request._safe_url_redirects = safe_url.MAX_REDIRECTS
    with pytest.raises(safe_url.BlockedURL):
        handler.redirect_request(request, None, 302, "Found", {}, "https://api.example.org/b")


def test_a_valid_same_host_redirect_is_followed_once(monkeypatch):
    _public_dns(monkeypatch)
    handler = safe_url._GuardedRedirectHandler()
    request = urllib.request.Request("https://api.example.org/a")
    new = handler.redirect_request(request, None, 302, "Found", {}, "/b")
    assert new is not None
    assert new.full_url == "https://api.example.org/b"
    assert new._safe_url_redirects == 1


def test_a_cross_host_redirect_drops_sensitive_headers(monkeypatch):
    _public_dns(monkeypatch)
    handler = safe_url._GuardedRedirectHandler()
    request = urllib.request.Request(
        "https://api.example.org/a",
        headers={
            "Authorization": "Bearer secret",
            "X-Api-Key": "key",
            "User-Agent": "essay-writer",
        },
    )
    new = handler.redirect_request(request, None, 302, "Found", {}, "https://cdn.example.org/b")
    assert new is not None
    lowered = {key.casefold() for key in new.headers}
    assert "authorization" not in lowered
    assert "x-api-key" not in lowered
    assert "user-agent" in lowered


def test_the_private_opener_carries_the_guarded_redirect_handler(monkeypatch):
    monkeypatch.setattr(safe_url, "_DEFAULT_OPENER", None)
    opener = safe_url._opener()
    guarded = [
        handler
        for handler in opener.handlers
        if isinstance(handler, safe_url._GuardedRedirectHandler)
    ]
    assert guarded


def test_downloads_map_a_blocked_url_to_an_empty_download():
    assert downloads.fetch_url("http://127.0.0.1/paper.pdf") == (0, None, b"")
    assert downloads.fetch_url("file:///etc/passwd") == (0, None, b"")


def test_downloads_keep_an_http_error_status_like_before(monkeypatch):
    _public_dns(monkeypatch)

    def not_found(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "Not Found",
            {"Content-Type": "text/html"},
            io.BytesIO(b"gone"),
        )

    monkeypatch.setattr(safe_url, "_open", not_found)
    assert downloads.fetch_url("https://api.example.org/paper.pdf") == (404, "text/html", b"gone")


def test_downloads_map_an_oversize_paper_to_an_empty_download(monkeypatch):
    _public_dns(monkeypatch)
    monkeypatch.setattr(downloads, "MAX_PAPER_BYTES", 8)
    _fake_open(monkeypatch, FakeRaw(b"z" * 64))
    assert downloads.fetch_url("https://api.example.org/paper.pdf") == (0, None, b"")


def test_dig_maps_a_blocked_url_to_none():
    assert dig._get_json("http://169.254.169.254/latest/meta-data/") is None


def test_dig_maps_an_oversize_lookup_to_none(monkeypatch):
    _public_dns(monkeypatch)
    monkeypatch.setattr(dig, "MAX_API_BYTES", 8)
    _fake_open(monkeypatch, FakeRaw(b'{"results": []}'))
    assert dig._get_json("https://api.openalex.org/works?search=x") is None


def test_resolvers_map_a_blocked_or_oversize_lookup_to_none(monkeypatch):
    assert resolvers._lookup_json("http://10.0.0.1/") is None
    _public_dns(monkeypatch)
    monkeypatch.setattr(resolvers, "MAX_LOOKUP_BYTES", 8)
    _fake_open(monkeypatch, FakeRaw(b'{"message": {"items": []}}'))
    assert resolvers._lookup_json("https://api.crossref.org/works?q=x") is None


def test_a_url_with_a_query_email_is_not_userinfo(monkeypatch):
    _public_dns(monkeypatch)
    raw = FakeRaw(b"{}")
    seen = _fake_open(monkeypatch, raw)
    clean = safe_url.validate_url("https://api.unpaywall.org/v2/10.1%2Fx?email=reader@example.org")
    assert clean == "https://api.unpaywall.org/v2/10.1%2Fx?email=reader@example.org"
    with safe_url.open_url(clean, max_bytes=1024):
        pass
    assert seen["request"].full_url == clean

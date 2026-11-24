"""Security regression checks for the address boundary and the debug export.

Each test is one property. Draws and clocks are not used. Nothing here opens
a network socket except the local resolver for an address literal.
"""

from __future__ import annotations

import io
import socket
import urllib.request
import zipfile
from typing import Any

import pytest

from essay_writer import safe_url
from essay_writer.debug_log import (
    EXPORT_FILENAME,
    debug_log_path,
    essay_debug_export,
    note_call,
    redact_text,
)

PUBLIC = "93.184.216.34"
SECRET_LINES = {
    "CONSENSUS_API_KEY": "consensus-value-aaa",
    "ESSAY_WRITER_UNPAYWALL_EMAIL": "reader@example.com",
    "OPENALEX_API_KEY": "openalex-value-bbb",
    "password": "password-value-iii",
    "secret": "secret-value-jjjj",
    "token": "token-value-eeee",
    "access_token": "access-value-ffff",
    "refresh_token": "refresh-value-gggg",
    "api_key": "apikey-value-cccc",
    "apikey": "apikeyplain-dddd",
    "authorization": "auth-value-hhhhh",
    "bearer": "bearer-value-kkkk",
    "email": "mailbox-token-llll",
}


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://10.1.2.3/",
        "http://192.168.1.20/",
        "http://172.16.0.10/",
        "http://169.254.1.1/",
        "http://[fe80::1]/",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_loopback_private_link_local_and_metadata_addresses_are_blocked(url: str) -> None:
    """Loopback, private, link-local, and the metadata address are refused."""
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url(url)


def test_trusted_egress_is_honored_only_when_opted_in(monkeypatch) -> None:
    """A trusted CIDR allows its range only after the opt-in. Other private ranges stay blocked."""
    monkeypatch.delenv(safe_url.TRUSTED_EGRESS_ENV, raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)
    monkeypatch.setattr(safe_url, "_resolve_addresses", lambda host, port: ["198.18.0.1"])
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url("https://api.example.org/works")

    monkeypatch.setenv(safe_url.TRUSTED_EGRESS_ENV, "198.18.0.0/15")
    assert safe_url.validate_url("https://api.example.org/works").startswith("https://")

    monkeypatch.setattr(safe_url, "_resolve_addresses", lambda host, port: ["10.0.0.1"])
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url("https://api.example.org/works")


def _resolve(host: str, port: int) -> list[str]:
    if host in {"api.example.org", "cdn.example.org"}:
        return [PUBLIC]
    return [host]


def test_every_redirect_is_revalidated(monkeypatch) -> None:
    """Each hop is checked. A later hop to a private address is refused."""
    monkeypatch.setattr(safe_url, "_resolve_addresses", _resolve)
    handler = safe_url._GuardedRedirectHandler()
    first = urllib.request.Request("https://api.example.org/a")
    second = handler.redirect_request(first, None, 302, "Found", {}, "https://cdn.example.org/b")
    assert second is not None
    assert second.full_url == "https://cdn.example.org/b"
    with pytest.raises(safe_url.BlockedURL):
        handler.redirect_request(second, None, 302, "Found", {}, "https://10.0.0.1/secret")
    with pytest.raises(safe_url.BlockedURL):
        handler.redirect_request(first, None, 302, "Found", {}, "https://169.254.169.254/latest")


class _Socket:
    def __init__(self, payload: bytes) -> None:
        self.sent = bytearray()
        self._payload = io.BytesIO(payload)

    def setsockopt(self, *args: object, **kwargs: object) -> None:
        return None

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def sendall(self, data: bytes, *args: object, **kwargs: object) -> None:
        self.sent.extend(data)

    def send(self, data: bytes, *args: object, **kwargs: object) -> int:
        self.sent.extend(data)
        return len(data)

    def makefile(self, *args: object, **kwargs: object) -> io.BytesIO:
        return self._payload

    def close(self) -> None:
        return None


def test_a_body_over_the_cap_is_refused(monkeypatch, workspace) -> None:
    """A body one byte over the cap raises, and the caller receives no bytes."""
    assert workspace.is_dir()
    monkeypatch.setattr(safe_url, "_resolve_addresses", lambda host, port: [PUBLIC])

    class Raw:
        def __init__(self) -> None:
            self.closed = False
            self.headers = {"Content-Type": "application/octet-stream"}

        def read(self, size: int = -1) -> bytes:
            return b"x" * 32

        def close(self) -> None:
            self.closed = True

    raw = Raw()
    monkeypatch.setattr(safe_url, "_open", lambda request, timeout: raw)
    with pytest.raises(safe_url.TooLarge):
        safe_url.open_url("https://api.example.org/paper.pdf", max_bytes=16)
    assert raw.closed is True


def test_a_dns_rebind_is_rejected(monkeypatch) -> None:
    """A second lookup that returns loopback is not the connection target.

    One answer that already mixes a public address with loopback is refused
    before a connection is opened.
    """
    monkeypatch.setattr(safe_url, "_DEFAULT_OPENER", None)
    calls = {"n": 0}

    def lookup(host, port, *args, **kwargs):
        calls["n"] += 1
        family = socket.AF_INET
        kind = socket.SOCK_STREAM
        if calls["n"] == 1:
            sockaddr = (PUBLIC, port)
        else:
            sockaddr = ("127.0.0.1", port)
        return [(family, kind, 6, "", sockaddr)]

    seen: dict[str, Any] = {}
    payload = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
    sock = _Socket(payload)

    def connect(address, timeout, source_address=None):
        seen.setdefault("addresses", []).append(address)
        return sock

    monkeypatch.setattr(safe_url.socket, "getaddrinfo", lookup)
    monkeypatch.setattr(safe_url, "_tcp_connect", connect)
    monkeypatch.setattr(safe_url, "_wrap_tls", lambda context, raw, server_hostname: sock)
    with safe_url.open_url("https://api.example.org/works", max_bytes=100) as response:
        assert response.read() == b"ok"
    assert seen["addresses"] == [(PUBLIC, 443)]
    assert all(address[0] != "127.0.0.1" for address in seen["addresses"])

    monkeypatch.setattr(
        safe_url,
        "_resolve_addresses",
        lambda host, port: [PUBLIC, "127.0.0.1"],
    )
    with pytest.raises(safe_url.BlockedURL):
        safe_url.validate_url("https://rebind.example.org/works")


def _planted_log() -> str:
    lines = [f"{name}={value}" for name, value in SECRET_LINES.items()]
    lines.append('{"api_key": "apikey-value-cccc", "password": "password-value-iii"}')
    return "\n".join(lines) + "\n"


def test_debug_export_redacts_every_secret_value(workspace, monkeypatch) -> None:
    """Every secret name's value is absent from the zip. The value is never printed."""
    assert workspace.is_dir()
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    debug_log_path().write_text(_planted_log(), encoding="utf-8")
    exported = essay_debug_export()
    assert exported["ok"] is True
    archive_path = workspace / EXPORT_FILENAME
    with zipfile.ZipFile(archive_path) as archive:
        blob = b"\n".join(archive.read(name) for name in archive.namelist())
    text = blob.decode("utf-8")
    for value in SECRET_LINES.values():
        assert value not in text
    assert "CONSENSUS_API_KEY" in text
    assert "[redacted]" in text


def test_a_debug_log_line_does_not_print_a_secret_value(workspace, monkeypatch) -> None:
    """A logged call keeps the field name and drops the value of every secret name."""
    assert workspace.is_dir()
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    note_call(
        "essay.setup",
        dict(SECRET_LINES),
        result={
            "ok": False,
            "refused": "setup",
            "reason": "echo " + " ".join(SECRET_LINES.values()),
        },
    )
    text = debug_log_path().read_text(encoding="utf-8")
    for value in SECRET_LINES.values():
        assert value not in text
    assert "[redacted]" in text


def test_redaction_does_not_put_a_secret_value_back() -> None:
    """Redacting an already redacted line does not restore a value."""
    once = redact_text(_planted_log())
    twice = redact_text(once)
    for value in SECRET_LINES.values():
        assert value not in once
        assert value not in twice

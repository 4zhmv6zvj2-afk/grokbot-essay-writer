"""SSRF and download-size guard for every remote URL this package opens.

The six URL opens in downloads, dig, and resolvers go through open_url.
Only http and https are allowed. The host must resolve, and every address it
resolves to must be public: loopback, private, link-local, reserved,
multicast, unspecified, and IPv6 ULA addresses are refused before a
connection is made. An operator may opt in to subnets of the fake-IP range
198.18.0.0/15. One invalid or wider network disables that opt-in. A private opener re-validates every redirect Location
with the same rules, refuses a cross-scheme redirect, and allows at most
three redirects. A response is read whole up to max_bytes; a declared
Content-Length or a streamed body over the cap raises TooLarge instead of
returning a truncated payload. Callers map a refusal onto their existing
empty download / None behaviour, so nothing here reaches an MCP tool as an
exception.

Residual risk: the host is resolved once for validation and again when the
connection is made, so a DNS answer that changes between those two lookups
could still reach a private address. The https certificate check stays on.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

HTTP_SCHEMES = frozenset({"http", "https"})
DEFAULT_PORTS = {"http": 80, "https": 443}
MAX_REDIRECTS = 3
MAX_URL_LENGTH = 4096
DEFAULT_TIMEOUT = 20.0
TRUSTED_EGRESS_ENV = "ESSAY_WRITER_TRUSTED_EGRESS"
_FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")
_READ_CHUNK = 64 * 1024
_SENSITIVE_HEADERS = frozenset({"authorization", "proxy-authorization", "x-api-key", "cookie"})


class Refused(urllib.error.URLError):
    """A fetch this module refuses. Subclasses URLError so callers catch it."""


class BlockedURL(Refused):
    """The URL or one of its redirect hops is not a public http(s) address."""


class TooLarge(Refused):
    """The response is larger than the caller's byte cap. No truncated body."""


class Response:
    """A fully read response. Callers keep their ``with ... as response`` shape."""

    def __init__(self, status: int, headers: Any, body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.code = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _trusted_networks() -> tuple[ipaddress.IPv4Network, ...]:
    """Subnets of 198.18.0.0/15, the standard proxy fake-IP range.

    Empty by default. Set ESSAY_WRITER_TRUSTED_EGRESS (environment or the
    setup secrets file) only on a host whose proxy or DNS is trusted. A
    token that is not a subnet of that range, including a supernet, a
    private range, or text that is not a network, disables the opt-in.
    """
    raw = os.environ.get(TRUSTED_EGRESS_ENV, "").strip()
    if not raw:
        try:
            from essay_writer.setup import read_setup_secret
        except ImportError:
            raw = ""
        else:
            try:
                raw = (read_setup_secret(TRUSTED_EGRESS_ENV) or "").strip()
            except Exception:  # noqa: BLE001 - a missing setting is not fatal
                raw = ""
    if not raw:
        return ()
    networks: list[ipaddress.IPv4Network] = []
    for part in re.split(r"[,\s]+", raw):
        if not part:
            continue
        try:
            network = ipaddress.ip_network(part, strict=False)
        except ValueError:
            return ()
        if not isinstance(network, ipaddress.IPv4Network) or not network.subnet_of(
            _FAKE_IP_NETWORK
        ):
            return ()
        networks.append(network)
    return tuple(networks)


def _fake_ip_hint(address: str) -> str:
    """Tell the operator how to opt in when the blocked address is fake-IP."""
    try:
        parsed: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(address)
    except ValueError:
        return ""
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    if parsed not in _FAKE_IP_NETWORK:
        return ""
    return (
        " If this host uses a trusted proxy with fake-IP DNS in 198.18.0.0/15, "
        "set ESSAY_WRITER_TRUSTED_EGRESS to a subnet of that range. "
        "Other ranges are not accepted."
    )


def _public_address(
    raw: str,
    trusted: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (),
) -> bool:
    """True when a resolved address is public, or in a trusted egress network."""
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped
        if mapped is not None:
            address = mapped
    if any(address.version == network.version and address in network for network in trusted):
        return True
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
        or not address.is_global
    ):
        return False
    return True


def _resolve_addresses(host: str, port: int) -> list[str]:
    """Every address the host resolves to. A host that does not resolve is refused."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        raise BlockedURL("the host did not resolve") from None
    found: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if not isinstance(sockaddr, tuple) or not sockaddr:
            continue
        raw = sockaddr[0]
        if not isinstance(raw, str) or not raw:
            continue
        found.append(raw.split("%", 1)[0])
    if not found:
        raise BlockedURL("the host did not resolve")
    return found


def validate_url(url: object) -> str:
    """Return the URL with its fragment removed, or raise BlockedURL.

    Only http(s), a default port, a host with no userinfo, and a host whose
    every resolved address is public are allowed.
    """
    if not isinstance(url, str) or not url.strip():
        raise BlockedURL("the address is empty")
    raw = url.strip()
    if len(raw) > MAX_URL_LENGTH:
        raise BlockedURL("the address is too long")
    for character in raw:
        if ord(character) <= 0x20 or ord(character) == 0x7F:
            raise BlockedURL("the address contains a control character")
    try:
        parts = urllib.parse.urlsplit(raw)
        port = parts.port
        host = parts.hostname
    except ValueError:
        raise BlockedURL("the address could not be parsed") from None
    scheme = parts.scheme.casefold()
    if scheme not in HTTP_SCHEMES:
        raise BlockedURL("only http and https are allowed")
    if "@" in parts.netloc:
        raise BlockedURL("an address with userinfo is not allowed")
    if not host:
        raise BlockedURL("the address has no host")
    default_port = DEFAULT_PORTS[scheme]
    if port is None:
        port = default_port
    elif port != default_port:
        raise BlockedURL("only the default port is allowed")
    trusted = _trusted_networks()
    for address in _resolve_addresses(host, port):
        if _public_address(address, trusted):
            continue
        hint = _fake_ip_hint(address)
        raise BlockedURL(f"the host resolves to a non-public address ({address}).{hint}")
    return urllib.parse.urlunsplit((scheme, parts.netloc, parts.path, parts.query, ""))


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect hop. Same scheme only, at most MAX_REDIRECTS."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        followed = getattr(req, "_safe_url_redirects", 0)
        if not isinstance(followed, int) or followed < 0:
            followed = 0
        if followed >= MAX_REDIRECTS:
            raise BlockedURL("too many redirects")
        base = urllib.parse.urlsplit(req.full_url)
        try:
            target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        except ValueError:
            raise BlockedURL("the redirect target could not be parsed") from None
        if target.scheme.casefold() != base.scheme.casefold():
            raise BlockedURL("a cross-scheme redirect is not allowed")
        clean = validate_url(urllib.parse.urlunsplit(target))
        new = super().redirect_request(req, fp, code, msg, headers, clean)
        if new is not None:
            if (target.hostname or "").casefold() != (base.hostname or "").casefold():
                for key in list(new.headers):
                    if key.casefold() in _SENSITIVE_HEADERS:
                        del new.headers[key]
            new._safe_url_redirects = followed + 1  # type: ignore[attr-defined]
        return new


_DEFAULT_OPENER: urllib.request.OpenerDirector | None = None
_SSL_CONTEXT: ssl.SSLContext | None = None
_CA_FALLBACKS = (
    "/etc/ssl/cert.pem",  # macOS system bundle
    "/etc/pki/tls/certs/ca-bundle.crt",  # Red Hat family
    "/etc/ssl/certs/ca-certificates.crt",  # Debian family
)


def _certifi_bundle() -> str | None:
    """The certifi bundle when that optional package is installed."""
    try:
        import certifi  # noqa: PLC0415 - optional, not a runtime dependency
    except ImportError:
        return None
    try:
        found = certifi.where()
    except Exception:  # noqa: BLE001 - a broken certifi is not fatal
        return None
    return found if found and os.path.isfile(found) else None


def _ca_bundle() -> str | None:
    """A readable CA bundle. None means the interpreter's own defaults."""
    found = _certifi_bundle()
    if found:
        return found
    # A python.org framework build ships no CA file until "Install
    # Certificates.command" is run. The OS bundle is the same trust store.
    for candidate in (os.environ.get("SSL_CERT_FILE"), *_CA_FALLBACKS):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _ssl_context() -> ssl.SSLContext:
    """The HTTPS trust store. Certificates still verify; the check stays on."""
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        bundle = _ca_bundle()
        _SSL_CONTEXT = (
            ssl.create_default_context(cafile=bundle) if bundle else ssl.create_default_context()
        )
    return _SSL_CONTEXT


def _opener() -> urllib.request.OpenerDirector:
    """One private opener with the guarded redirect handler. Tests patch this."""
    global _DEFAULT_OPENER
    if _DEFAULT_OPENER is None:
        _DEFAULT_OPENER = urllib.request.build_opener(
            _GuardedRedirectHandler(),
            urllib.request.HTTPSHandler(context=_ssl_context()),
        )
    return _DEFAULT_OPENER


def _open(request: urllib.request.Request, timeout: float) -> Any:
    """Network seam. Tests patch this instead of the callers' urllib names."""
    return _opener().open(request, timeout=timeout)


def _header(headers: Any, name: str) -> str | None:
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    value = getter(name)
    if value is None:
        value = getter(name.casefold())
    if value is None:
        return None
    return str(value)


def _declared_too_large(headers: Any, max_bytes: int) -> bool:
    declared = _header(headers, "Content-Length")
    if declared is None:
        return False
    try:
        length = int(declared.strip())
    except ValueError:
        return False
    return length > max_bytes


def _read_capped(raw: Any, headers: Any, max_bytes: int) -> bytes:
    """Read the whole body. Raise TooLarge rather than return a short read."""
    if _declared_too_large(headers, max_bytes):
        raise TooLarge("the response declares more bytes than the cap")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = raw.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise TooLarge("the response is larger than the cap")
        chunks.append(chunk)
    return b"".join(chunks)


def _read_error_body(exc: urllib.error.HTTPError, max_bytes: int) -> bytes:
    try:
        return _read_capped(exc, exc.headers, max_bytes)
    finally:
        try:
            exc.close()
        except OSError:
            pass


def _close(raw: Any) -> None:
    closer = getattr(raw, "close", None)
    if callable(closer):
        try:
            closer()
        except OSError:
            pass


def open_url(
    url: object,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int,
    headers: dict[str, str] | None = None,
) -> Response:
    """GET a public http(s) address. The body is read whole or TooLarge is raised.

    An HTTP error status is returned as a Response, so callers keep their own
    status handling. Network failures and refusals raise Refused subclasses.
    """
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    clean = validate_url(url)
    request = urllib.request.Request(  # noqa: S310 - the scheme and host are validated above
        clean,
        headers=dict(headers or {}),
        method="GET",
    )
    try:
        raw = _open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        return Response(int(exc.code or 0), exc.headers, _read_error_body(exc, max_bytes))
    try:
        status = int(getattr(raw, "status", 200) or 200)
        response_headers = getattr(raw, "headers", None)
        body = _read_capped(raw, response_headers, max_bytes)
    finally:
        _close(raw)
    return Response(status, response_headers, body)

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

The connection is opened to an address that passed that check. TLS SNI and
the HTTP Host header stay the original hostname, including when the address
is in the trusted fake-IP range. The https certificate check stays on.
"""

from __future__ import annotations

import errno
import http.client
import ipaddress
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

HTTP_SCHEMES = frozenset({"http", "https"})
DEFAULT_PORTS = {"http": 80, "https": 443}
MAX_REDIRECTS = 3
MAX_URL_LENGTH = 4096
DEFAULT_TIMEOUT = 20.0
READ_ATTEMPTS = 3
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
TIMEOUT_COPY = "The look-up timed out. Try this look-up again."
RATE_COPY = "The look-up is busy. Try this look-up again."
SERVER_COPY = "The look-up service failed. Try this look-up again."
DNS_COPY = "The host did not resolve. Check the address and try again."
OFFLINE_COPY = "The look-up did not answer. Try this look-up again."
REDIRECT_COPY = "The address redirected too many times. Use a direct link."
TOO_LARGE_COPY = "The file is larger than the cap. Use a smaller file."
TRUSTED_EGRESS_ENV = "ESSAY_WRITER_TRUSTED_EGRESS"
_FAKE_IP_NETWORK = ipaddress.IPv4Network("198.18.0.0/15")
_READ_CHUNK = 64 * 1024
_SENSITIVE_HEADERS = frozenset({"authorization", "proxy-authorization", "x-api-key", "cookie"})


class Refused(urllib.error.URLError):
    """A fetch this module refuses. Subclasses URLError so callers catch it."""

    def __str__(self) -> str:
        if isinstance(self.reason, str):
            return self.reason
        return super().__str__()


class BlockedURL(Refused):
    """The URL or one of its redirect hops is not a public http(s) address."""


class TooLarge(Refused):
    """The response is larger than the caller's byte cap. No truncated body."""


class GaveUp(Refused):
    """A read failed after its bounded attempts. The body was not returned."""


class Clock:
    """Monotonic time. A test clock records sleep and does not wait on the wall."""

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


_CLOCK = Clock()
_RESOLVE_CLOCK: Clock | None = None
Transport = Callable[[urllib.request.Request, float], Any]


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


def _note_read(code: str, *, disposition: str) -> None:
    from essay_writer.incident import note

    severity = "info" if disposition == "retry" else "warn"
    note(code, severity=severity, disposition=disposition, tool="read", step="fetch")


def _pause(clock: Clock, attempt: int) -> None:
    """Bounded backoff. The jitter comes from the clock, so a fake clock stays put."""
    base = 0.05 * (2**attempt)
    jitter = clock.now() % 0.01
    clock.sleep(base + jitter)


def _retryable(exc: BaseException) -> bool:
    """True for a timeout, a DNS error, or a dropped connection. A refusal is not."""
    if isinstance(exc, Refused):
        return False
    if isinstance(exc, (TimeoutError, socket.timeout, socket.gaierror)):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, BaseException):
            return _retryable(reason)
        return True
    return isinstance(exc, OSError)


def _failure_copy(exc: BaseException) -> str:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return TIMEOUT_COPY
    if isinstance(exc, socket.gaierror):
        return DNS_COPY
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, BaseException):
        return _failure_copy(exc.reason)
    return OFFLINE_COPY


def _status_copy(status: int) -> str:
    if status == 429:
        return RATE_COPY
    return SERVER_COPY


def _resolve_addresses(host: str, port: int) -> list[str]:
    """Every address the host resolves to. A host that does not resolve is refused."""
    clock = _RESOLVE_CLOCK
    timer = clock or _CLOCK
    attempts = READ_ATTEMPTS if clock is not None else 1
    infos: list[Any] | None = None
    for attempt in range(attempts):
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            break
        except (OSError, UnicodeError):
            if clock is not None and attempt + 1 < attempts:
                _note_read("read-retry", disposition="retry")
                _pause(timer, attempt)
                continue
            if clock is not None:
                _note_read("read-dns", disposition="fallback")
            raise BlockedURL(DNS_COPY) from None
    if not infos:
        if clock is not None:
            _note_read("read-dns", disposition="fallback")
        raise BlockedURL(DNS_COPY)
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
        if clock is not None:
            _note_read("read-dns", disposition="fallback")
        raise BlockedURL(DNS_COPY)
    return found


def _checked_url(url: object) -> tuple[str, tuple[str, ...]]:
    """The fragment-free URL and the addresses that passed validation."""
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
    addresses = tuple(_resolve_addresses(host, port))
    for address in addresses:
        if _public_address(address, trusted):
            continue
        hint = _fake_ip_hint(address)
        raise BlockedURL(f"the host resolves to a non-public address ({address}).{hint}")
    clean = urllib.parse.urlunsplit((scheme, parts.netloc, parts.path, parts.query, ""))
    return clean, addresses


def validate_url(url: object) -> str:
    """Return the URL with its fragment removed, or raise BlockedURL.

    Only http(s), a default port, a host with no userinfo, and a host whose
    every resolved address is public are allowed.
    """
    clean, _addresses = _checked_url(url)
    return clean


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
            raise BlockedURL(REDIRECT_COPY)
        base = urllib.parse.urlsplit(req.full_url)
        try:
            target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        except ValueError:
            raise BlockedURL("the redirect target could not be parsed") from None
        if target.scheme.casefold() != base.scheme.casefold():
            raise BlockedURL("a cross-scheme redirect is not allowed")
        clean, addresses = _checked_url(urllib.parse.urlunsplit(target))
        new = super().redirect_request(req, fp, code, msg, headers, clean)
        if new is not None:
            new._safe_url_addresses = addresses  # type: ignore[attr-defined]
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


def _tcp_connect(
    address: tuple[str, int],
    timeout: Any,
    source_address: Any = None,
) -> socket.socket:
    """Open the TCP connection. Tests replace this with a local socket double."""
    return socket.create_connection(address, timeout, source_address)


def _wrap_tls(context: ssl.SSLContext, sock: socket.socket, server_hostname: str) -> socket.socket:
    """TLS with the original hostname as SNI. The certificate check stays on."""
    return context.wrap_socket(sock, server_hostname=server_hostname)


def _pin_targets(connection: http.client.HTTPConnection) -> tuple[str, ...]:
    """Addresses from validation. The hostname is only a fallback."""
    addresses = getattr(connection, "_safe_url_addresses", ())
    if isinstance(addresses, tuple) and addresses:
        return addresses
    return (connection.host,)


def _set_tcp_nodelay(sock: socket.socket) -> None:
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError as exc:
        if exc.errno != errno.ENOPROTOOPT:
            raise


def _open_pinned_socket(connection: http.client.HTTPConnection) -> None:
    """Connect to a validated address. Do not look the hostname up again."""
    port = connection.port
    if not isinstance(port, int):
        raise OSError("the host has no port")
    error: OSError | None = None
    for target in _pin_targets(connection):
        try:
            connect_timeout = getattr(connection, "_connect_timeout", connection.timeout)
            sock = _tcp_connect(
                (target, port),
                connect_timeout,
                getattr(connection, "source_address", None),
            )
        except OSError as exc:
            error = exc
            continue
        _set_tcp_nodelay(sock)
        read_timeout = getattr(connection, "_read_timeout", connection.timeout)
        sock.settimeout(read_timeout)
        connection.sock = sock
        return
    raise error if error is not None else OSError("the host did not connect")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTP connection pinned to the addresses stored on the request."""

    _safe_url_addresses: tuple[str, ...] = ()
    _connect_timeout: float | None = None
    _read_timeout: float | None = None

    def connect(self) -> None:
        _open_pinned_socket(self)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to the validated address. SNI stays the hostname."""

    _safe_url_addresses: tuple[str, ...] = ()
    _connect_timeout: float | None = None
    _read_timeout: float | None = None

    def connect(self) -> None:
        _open_pinned_socket(self)
        context = getattr(self, "_context", None)
        if not isinstance(context, ssl.SSLContext):
            raise OSError("the https connection has no TLS context")
        sock = self.sock
        if sock is None:
            raise OSError("the host did not connect")
        # No proxy CONNECT tunnel. A fake-IP proxy is reached by connecting to
        # the validated address while SNI stays the original hostname.
        self.sock = _wrap_tls(context, sock, self.host)


def _bind_pin(
    connection: _PinnedHTTPConnection | _PinnedHTTPSConnection,
    request: urllib.request.Request,
) -> None:
    addresses = getattr(request, "_safe_url_addresses", ())
    if isinstance(addresses, tuple):
        connection._safe_url_addresses = addresses
    connection._connect_timeout = getattr(request, "_connect_timeout", connection.timeout)
    connection._read_timeout = getattr(request, "_read_timeout", connection.timeout)


class _PinningHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request) -> Any:
        def factory(host: str, **kwargs: Any) -> _PinnedHTTPConnection:
            connection = _PinnedHTTPConnection(host, **kwargs)
            _bind_pin(connection, req)
            return connection

        return self.do_open(factory, req)


class _PinningHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context: ssl.SSLContext) -> None:
        super().__init__(context=context)
        self._pin_context = context

    def https_open(self, req: urllib.request.Request) -> Any:
        def factory(host: str, **kwargs: Any) -> _PinnedHTTPSConnection:
            kwargs["context"] = self._pin_context
            connection = _PinnedHTTPSConnection(host, **kwargs)
            _bind_pin(connection, req)
            return connection

        return self.do_open(factory, req, context=self._pin_context)


def _opener() -> urllib.request.OpenerDirector:
    """One private opener with the guarded redirect handler. Tests patch this."""
    global _DEFAULT_OPENER
    if _DEFAULT_OPENER is None:
        _DEFAULT_OPENER = urllib.request.build_opener(
            _GuardedRedirectHandler(),
            _PinningHTTPHandler(),
            _PinningHTTPSHandler(context=_ssl_context()),
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
        raise TooLarge(TOO_LARGE_COPY)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = raw.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise TooLarge(TOO_LARGE_COPY)
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
    transport: Transport | None = None,
    clock: Clock | None = None,
    connect_timeout: float | None = None,
    read_timeout: float | None = None,
    method: str = "GET",
) -> Response:
    """Read a public http(s) address. The body is whole or TooLarge is raised.

    Connect and read each have a timeout. The default uses ``timeout`` for both.
    A GET or HEAD retries a timeout, a dropped connection, a 429, or a 5xx
    up to READ_ATTEMPTS. Any other method tries once. A retry waits on
    ``clock``. An HTTP status that is not retried is returned as a Response.
    """
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    verb = method.upper()
    idempotent = verb in {"GET", "HEAD"}
    attempts = READ_ATTEMPTS if idempotent else 1
    timer = clock or _CLOCK
    opener = transport or _open
    connect = timeout if connect_timeout is None else connect_timeout
    read = timeout if read_timeout is None else read_timeout
    global _RESOLVE_CLOCK
    previous_clock = _RESOLVE_CLOCK
    _RESOLVE_CLOCK = timer
    try:
        clean, addresses = _checked_url(url)
    finally:
        _RESOLVE_CLOCK = previous_clock
    request = urllib.request.Request(  # noqa: S310 - the scheme and host are validated above
        clean,
        headers=dict(headers or {}),
        method=verb,
    )
    request._safe_url_addresses = addresses  # type: ignore[attr-defined]
    request._connect_timeout = connect  # type: ignore[attr-defined]
    request._read_timeout = read  # type: ignore[attr-defined]
    last_status = 0
    for attempt in range(attempts):
        raw: Any = None
        try:
            try:
                raw = opener(request, connect)
            except urllib.error.HTTPError as exc:
                status = int(exc.code or 0)
                if status in _RETRY_STATUSES and attempt + 1 < attempts:
                    _close(exc)
                    _note_read("read-retry", disposition="retry")
                    _pause(timer, attempt)
                    continue
                if status in _RETRY_STATUSES:
                    _close(exc)
                    _note_read("read-fallback", disposition="fallback")
                    raise GaveUp(_status_copy(status)) from None
                return Response(status, exc.headers, _read_error_body(exc, max_bytes))
            status = int(getattr(raw, "status", 200) or 200)
            last_status = status
            if status in _RETRY_STATUSES and attempt + 1 < attempts:
                _close(raw)
                raw = None
                _note_read("read-retry", disposition="retry")
                _pause(timer, attempt)
                continue
            if status in _RETRY_STATUSES:
                _close(raw)
                raw = None
                _note_read("read-fallback", disposition="fallback")
                raise GaveUp(_status_copy(status)) from None
            response_headers = getattr(raw, "headers", None)
            body = _read_capped(raw, response_headers, max_bytes)
            return Response(status, response_headers, body)
        except GaveUp:
            raise
        except Refused as exc:
            if isinstance(exc, TooLarge):
                _note_read("read-too-large", disposition="fallback")
            elif isinstance(exc, BlockedURL) and str(exc) == REDIRECT_COPY:
                _note_read("read-redirect", disposition="fallback")
            raise
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            if attempt + 1 < attempts and _retryable(exc):
                _note_read("read-retry", disposition="retry")
                _pause(timer, attempt)
                continue
            if _retryable(exc):
                _note_read("read-fallback", disposition="fallback")
                raise GaveUp(_failure_copy(exc)) from exc
            raise
        finally:
            if raw is not None:
                _close(raw)
    _note_read("read-fallback", disposition="fallback")
    raise GaveUp(_status_copy(last_status) if last_status else OFFLINE_COPY)

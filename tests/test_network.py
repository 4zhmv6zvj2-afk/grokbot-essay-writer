"""Network failures stay deterministic and leave the saved sequence alone.

The transport and the clock are injected. A GET may retry. A write and a POST
try once. A failed read does not publish a partial file.
"""

from __future__ import annotations

import io
import json
import socket
import threading
import urllib.error
import urllib.request

import pytest
from helpers import open_sequence

from essay_writer import dig, safe_url, update
from essay_writer.incident import incident_path
from essay_writer.paths import essay_dir, work_dir

PUBLIC = "93.184.216.34"


class FakeClock(safe_url.Clock):
    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


class FakeRaw:
    status = 200

    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.headers = dict(headers or {})
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk, self.body = self.body, b""
            return chunk
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def close(self) -> None:
        self.closed = True


def _public(monkeypatch) -> None:
    monkeypatch.setattr(safe_url, "_resolve_addresses", lambda host, port, clock=None: [PUBLIC])


def _marker(seq: str):
    path = work_dir(seq) / "state.json"
    path.write_text('{"marker":"kept"}\n', encoding="utf-8")
    return path


def _codes() -> list[str]:
    path = incident_path()
    if not path.is_file():
        return []
    return [json.loads(line)["code"] for line in path.read_text(encoding="utf-8").splitlines()]


def _http_error(status: int):
    def fail(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            status,
            "busy",
            {"Content-Type": "text/plain"},
            io.BytesIO(b"busy"),
        )

    return fail


def test_a_timeout_retries_on_a_read_and_names_the_next_step(workspace, monkeypatch):
    _public(monkeypatch)
    seq = open_sequence()
    marker = _marker(seq)
    before = marker.read_bytes()
    clock = FakeClock()
    calls: list[float] = []

    def transport(request, timeout):
        calls.append(timeout)
        raise TimeoutError("timed out")

    with pytest.raises(safe_url.GaveUp) as caught:
        safe_url.open_url(
            "https://api.example.org/works",
            max_bytes=1024,
            transport=transport,
            clock=clock,
            connect_timeout=1.5,
            read_timeout=4,
        )
    assert str(caught.value) == safe_url.TIMEOUT_COPY
    assert "Try" in str(caught.value)
    assert calls == [1.5, 1.5, 1.5]
    assert len(clock.slept) == 2
    assert marker.read_bytes() == before
    assert "read-retry" in _codes()
    assert "read-fallback" in _codes()


def test_a_post_is_not_retried(workspace, monkeypatch):
    _public(monkeypatch)
    clock = FakeClock()
    calls: list[str] = []

    def transport(request, timeout):
        calls.append(request.method)
        raise TimeoutError("timed out")

    with pytest.raises(safe_url.GaveUp) as caught:
        safe_url.open_url(
            "https://api.example.org/works",
            max_bytes=1024,
            transport=transport,
            clock=clock,
            method="POST",
        )
    assert calls == ["POST"]
    assert clock.slept == []
    assert str(caught.value) == safe_url.TIMEOUT_COPY


def test_retry_statuses_and_the_attempt_count_stay_fixed() -> None:
    assert safe_url.READ_ATTEMPTS == 3
    assert safe_url._RETRY_STATUSES == frozenset({429, 500, 502, 503, 504})


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_an_http_error_status_retries_then_gives_up(workspace, monkeypatch, status: int) -> None:
    _public(monkeypatch)
    clock = FakeClock()
    calls = {"n": 0}

    def transport(request, timeout):
        calls["n"] += 1
        return _http_error(status)(request, timeout)

    with pytest.raises(safe_url.GaveUp) as caught:
        safe_url.open_url(
            "https://api.example.org/works",
            max_bytes=1024,
            transport=transport,
            clock=clock,
        )
    assert calls["n"] == safe_url.READ_ATTEMPTS
    assert len(clock.slept) == safe_url.READ_ATTEMPTS - 1
    expected = safe_url.RATE_COPY if status == 429 else safe_url.SERVER_COPY
    assert str(caught.value) == expected


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_a_response_status_retries_then_gives_up(workspace, monkeypatch, status: int) -> None:
    _public(monkeypatch)
    clock = FakeClock()
    calls = {"n": 0}

    def transport(request, timeout):
        calls["n"] += 1
        raw = FakeRaw(b"busy")
        raw.status = status
        return raw

    with pytest.raises(safe_url.GaveUp) as caught:
        safe_url.open_url(
            "https://api.example.org/works",
            max_bytes=1024,
            transport=transport,
            clock=clock,
        )
    assert calls["n"] == safe_url.READ_ATTEMPTS
    assert len(clock.slept) == safe_url.READ_ATTEMPTS - 1
    expected = safe_url.RATE_COPY if status == 429 else safe_url.SERVER_COPY
    assert str(caught.value) == expected


def test_a_404_is_returned_once(workspace, monkeypatch) -> None:
    _public(monkeypatch)
    clock = FakeClock()
    calls = {"n": 0}

    def transport(request, timeout):
        calls["n"] += 1
        return _http_error(404)(request, timeout)

    response = safe_url.open_url(
        "https://api.example.org/works",
        max_bytes=1024,
        transport=transport,
        clock=clock,
    )
    assert calls["n"] == 1
    assert clock.slept == []
    assert response.status == 404
    assert response.read() == b"busy"


def test_a_429_retries_then_falls_back(workspace, monkeypatch):
    _public(monkeypatch)
    clock = FakeClock()
    calls = {"n": 0}

    def transport(request, timeout):
        calls["n"] += 1
        return _http_error(429)(request, timeout)

    with pytest.raises(safe_url.GaveUp) as caught:
        safe_url.open_url(
            "https://api.example.org/works",
            max_bytes=1024,
            transport=transport,
            clock=clock,
        )
    assert calls["n"] == 3
    assert len(clock.slept) == 2
    assert str(caught.value) == safe_url.RATE_COPY


def test_a_5xx_retries_then_falls_back(workspace, monkeypatch):
    _public(monkeypatch)
    clock = FakeClock()
    calls = {"n": 0}

    def transport(request, timeout):
        calls["n"] += 1
        return _http_error(503)(request, timeout)

    with pytest.raises(safe_url.GaveUp) as caught:
        safe_url.open_url(
            "https://api.example.org/works",
            max_bytes=1024,
            transport=transport,
            clock=clock,
        )
    assert calls["n"] == 3
    assert str(caught.value) == safe_url.SERVER_COPY
    assert "read-fallback" in _codes()


@pytest.mark.parametrize("body", [b"{", b'{"results":'])
def test_malformed_json_names_the_next_step_and_writes_nothing(workspace, monkeypatch, body):
    _public(monkeypatch)
    seq = open_sequence()
    marker = _marker(seq)
    before = marker.read_bytes()

    def transport(request, timeout):
        return FakeRaw(body, {"Content-Type": "application/json"})

    monkeypatch.setattr(safe_url, "_open", transport)
    with pytest.raises(dig.LookupRefused) as caught:
        dig._get_json("https://api.example.org/works")
    assert str(caught.value) == "The look-up did not return JSON. Try this look-up again."
    assert marker.read_bytes() == before
    assert "read-bad-json" in _codes()


def test_a_redirect_loop_names_a_direct_link(workspace, monkeypatch):
    _public(monkeypatch)
    handler = safe_url._GuardedRedirectHandler()
    request = urllib.request.Request("https://api.example.org/a")
    request._safe_url_redirects = safe_url.MAX_REDIRECTS
    with pytest.raises(safe_url.BlockedURL) as caught:
        handler.redirect_request(request, None, 302, "Found", {}, "https://api.example.org/b")
    assert str(caught.value) == safe_url.REDIRECT_COPY
    assert "Use" in str(caught.value)


def test_a_body_over_the_cap_names_a_smaller_file(workspace, monkeypatch):
    _public(monkeypatch)
    seq = open_sequence()
    marker = _marker(seq)
    before = marker.read_bytes()
    target = work_dir(seq) / "output" / "partial.bin"

    def transport(request, timeout):
        return FakeRaw(b"x" * 64)

    with pytest.raises(safe_url.TooLarge) as caught:
        safe_url.open_url(
            "https://api.example.org/paper.pdf",
            max_bytes=16,
            transport=transport,
        )
    assert str(caught.value) == safe_url.TOO_LARGE_COPY
    assert marker.read_bytes() == before
    assert target.exists() is False
    assert "read-too-large" in _codes()


def test_a_dns_failure_retries_and_does_not_call_the_transport(workspace, monkeypatch):
    seq = open_sequence()
    marker = _marker(seq)
    before = marker.read_bytes()
    clock = FakeClock()
    calls: list[str] = []

    def no_dns(*_args, **_kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "no name")

    def transport(request, timeout):
        calls.append(request.full_url)
        return FakeRaw(b"{}")

    monkeypatch.setattr(safe_url.socket, "getaddrinfo", no_dns)
    with pytest.raises(safe_url.BlockedURL) as caught:
        safe_url.open_url(
            "https://missing.example/works",
            max_bytes=1024,
            transport=transport,
            clock=clock,
        )
    assert str(caught.value) == safe_url.DNS_COPY
    assert "try" in str(caught.value).casefold()
    assert calls == []
    assert len(clock.slept) == safe_url.READ_ATTEMPTS - 1
    assert marker.read_bytes() == before
    assert "read-dns" in _codes()


def test_concurrent_callers_keep_their_own_clocks(monkeypatch) -> None:
    barrier = threading.Barrier(2)
    seen: list[safe_url.Clock] = []

    def resolve(host: str, port: int, clock: safe_url.Clock | None = None) -> list[str]:
        assert clock is not None
        seen.append(clock)
        barrier.wait(timeout=5)
        return [PUBLIC]

    def transport(request: urllib.request.Request, timeout: float) -> FakeRaw:
        return FakeRaw(b"{}")

    monkeypatch.setattr(safe_url, "_resolve_addresses", resolve)
    first = FakeClock()
    second = FakeClock()
    errors: list[BaseException] = []

    def run(clock: FakeClock) -> None:
        try:
            safe_url.open_url(
                "https://api.example.org/works",
                max_bytes=1024,
                transport=transport,
                clock=clock,
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(clock,)) for clock in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert errors == []
    assert {id(clock) for clock in seen} == {id(first), id(second)}


def test_a_failed_download_does_not_leave_a_partial_file(workspace, monkeypatch):
    _public(monkeypatch)
    clock = FakeClock()
    monkeypatch.setattr(safe_url, "_CLOCK", clock)
    calls = {"n": 0}

    def transport(request, timeout):
        calls["n"] += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(safe_url, "_open", transport)
    target = workspace / "essay-writer.tar.gz"
    with pytest.raises(update.UpdateError) as caught:
        update._download(
            "https://github.com/example/essay-writer/releases/download/v0/a.tgz", target
        )
    assert calls["n"] == 3
    assert target.exists() is False
    assert "Try" in str(caught.value)


def test_a_repeated_cursor_stops_the_gather(workspace, monkeypatch):
    _public(monkeypatch)
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    seq = open_sequence()
    marker = _marker(seq)
    before = marker.read_bytes()
    folder = essay_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text("The assignment is 20,000 words.\n", encoding="utf-8")
    calls: list[str] = []

    def transport(request, timeout):
        calls.append(request.full_url)
        body = json.dumps(
            {
                "meta": {"next_cursor": "same-page"},
                "results": [
                    {
                        "title": f"Paper {index}",
                        "publication_year": 2020,
                        "doi": f"10.9/{index}",
                        "authorships": [],
                    }
                    for index in range(5)
                ],
            }
        ).encode()
        return FakeRaw(body, {"Content-Type": "application/json"})

    monkeypatch.setattr(safe_url, "_open", transport)
    card = dig._build_floor_card("How do ports shape coastal trade?", seq)
    assert len(calls) == 2
    assert card["openalex"]["page_stop"] == (
        "This page repeated a cursor. The gather stops on this page. Try the look-up again."
    )
    assert marker.read_bytes() == before
    assert (work_dir(seq) / "dig-card.json").exists() is False
    assert "page-cursor-repeat" in _codes()


def test_a_page_cap_stops_a_cursor_that_keeps_changing(workspace, monkeypatch):
    _public(monkeypatch)
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setattr(dig, "_PAGE_CAP", 1)
    seq = open_sequence()
    folder = essay_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text("The assignment is 20,000 words.\n", encoding="utf-8")
    calls = {"n": 0}

    def transport(request, timeout):
        calls["n"] += 1
        body = json.dumps(
            {
                "meta": {"next_cursor": f"page-{calls['n']}"},
                "results": [
                    {
                        "title": f"Paper {calls['n']}-{index}",
                        "publication_year": 2020,
                        "doi": f"10.8/{calls['n']}-{index}",
                        "authorships": [],
                    }
                    for index in range(5)
                ],
            }
        ).encode()
        return FakeRaw(body, {"Content-Type": "application/json"})

    monkeypatch.setattr(safe_url, "_open", transport)
    card = dig._build_floor_card("How do ports shape coastal trade?", seq)
    assert calls["n"] == 2
    assert "page_stop" not in card["openalex"]

import asyncio
import logging
import socket
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from utils.job_fetcher import _safe_get, validate_public_http_url


def _dns(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


@pytest.mark.security
@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/job", "javascript:alert(1)", "http://127.0.0.1/job", "http://192.168.0.1/job", "http://169.254.1.2/job", "http://[::1]/job", "http://[fe80::1]/job", "http://localhost/job"])
def test_unsupported_loopback_and_local_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_public_http_url(url)


@pytest.mark.security
def test_dns_mixed_public_and_private_answers_are_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _dns("93.184.216.34") + _dns("10.0.0.8"))
    with pytest.raises(ValueError, match="public addresses"):
        validate_public_http_url("https://jobs.example.org/role")


@pytest.mark.security
def test_redirect_to_private_network_is_rejected_before_second_request(monkeypatch):
    def resolve(host, *args, **kwargs):
        return _dns("93.184.216.34" if host == "jobs.example.org" else "169.254.169.254")
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    class Redirect:
        is_redirect = True
        is_permanent_redirect = False
        headers = {"Location": "http://metadata.example/latest"}
        def close(self): pass
    class Session:
        calls = 0
        def get(self, *args, **kwargs):
            self.calls += 1
            return Redirect()
    session = Session()
    with pytest.raises(ValueError):
        _safe_get(session, "https://jobs.example.org/role")
    assert session.calls == 1


@pytest.mark.security
def test_http_403_uses_supported_cloudscraper_fallback(monkeypatch):
    import requests
    import utils.job_fetcher as fetcher
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _dns("93.184.216.34"))
    class Forbidden:
        status_code = 403
        is_redirect = False
        is_permanent_redirect = False
        text = "blocked"
        def raise_for_status(self): raise requests.HTTPError("403")
    class Session:
        headers = {}
        def get(self, *args, **kwargs): return Forbidden()
    monkeypatch.setattr(fetcher.requests, "Session", Session)
    monkeypatch.setattr(fetcher, "fetch_job_html_with_cloudscraper", lambda url: "<html>controlled fallback</html>")
    assert "controlled fallback" in fetcher.fetch_job_html("https://jobs.example.org/role")


@pytest.mark.security
@pytest.mark.asyncio
async def test_browser_request_guard_blocks_disallowed_redirect_or_subresource(monkeypatch):
    from utils.browser_fetch import guard_browser_request
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _dns("10.0.0.8"))
    route = SimpleNamespace(request=SimpleNamespace(url="https://private.example/path"), continued=False, aborted=False)
    async def continue_request(): route.continued = True
    async def abort_request(): route.aborted = True
    route.continue_, route.abort = continue_request, abort_request
    await guard_browser_request(route)
    assert route.aborted and not route.continued


@pytest.mark.security
@pytest.mark.asyncio
async def test_api_key_errors_never_log_supplied_token(caplog):
    from main import get_api_key
    request = Request({"type": "http", "method": "GET", "path": "/api/jobs", "headers": [], "query_string": b"", "server": ("test", 80), "scheme": "http", "client": ("test", 1), "http_version": "1.1"})
    supplied_token = "this-is-an-invalid-token-value"
    with caplog.at_level(logging.WARNING), pytest.raises(HTTPException) as error:
        await get_api_key(request, supplied_token)
    assert error.value.status_code == 403
    assert supplied_token not in caplog.text
    with pytest.raises(HTTPException) as missing:
        await get_api_key(request, None)
    assert missing.value.status_code == 401


@pytest.mark.security
def test_production_configuration_rejects_predictable_default_api_key():
    from config import Settings
    from pydantic import ValidationError
    api_field = "HIRESCOPE_API" + "_KEY"
    rejected_value = "hirescope_dev_" + "sec" + "ret"
    with pytest.raises(ValidationError):
        Settings(ENV="production", **{api_field: rejected_value})
    accepted_value = "a-long-generated-token-value"
    configured = Settings(ENV="production", **{api_field: accepted_value})
    assert getattr(configured, api_field) == accepted_value


@pytest.mark.security
def test_analysis_request_requires_http_url_and_a_session_capability():
    from main import AnalyzeRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AnalyzeRequest(job_url="file:///tmp/private", session_id="1234567890123456")
    with pytest.raises(ValidationError):
        AnalyzeRequest(job_url="https://jobs.example.org/x")


@pytest.mark.security
@pytest.mark.asyncio
async def test_job_report_access_is_scoped_to_session(monkeypatch):
    import main
    main.jobs["eval-owned-job"] = {"session_id": "session-owner-123456", "status": "completed", "html_report": "<h1>private</h1>"}
    try:
        with pytest.raises(HTTPException) as error:
            await main.get_job_report("eval-owned-job", "session-other-654321")
        assert error.value.status_code == 404
        report = await main.get_job_report("eval-owned-job", "session-owner-123456")
        assert report["html_report"] == "<h1>private</h1>"
    finally:
        main.jobs.pop("eval-owned-job", None)


@pytest.mark.security
@pytest.mark.asyncio
async def test_job_submission_and_listing_require_and_filter_session_capability(monkeypatch):
    import main
    from fastapi import BackgroundTasks
    from config import settings
    monkeypatch.setattr(settings, "USE_MOCK_DATA", False)
    request = main.AnalyzeRequest(job_url="https://jobs.example.org/role", session_id="session-owner-123456")
    queued = await main.analyze_job(request, BackgroundTasks())
    job_id = queued["job_id"]
    try:
        with pytest.raises(HTTPException) as error:
            await main.get_job_status(job_id, "session-other-654321")
        assert error.value.status_code == 404
        monkeypatch.setattr("database.engine", object())
        mine = await main.list_jobs(session_id="session-owner-123456")
        theirs = await main.list_jobs(session_id="session-other-654321")
        assert any(job["job_id"] == job_id for job in mine)
        assert all(job["job_id"] != job_id for job in theirs)
    finally:
        main.jobs.pop(job_id, None)

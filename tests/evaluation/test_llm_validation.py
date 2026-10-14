import asyncio
import json
import sys
import types

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import wait_none

from utils import llm


class StrictResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(ge=0)
    label: str


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "gemini", "anthropic"])
async def test_json_output_validates_schema_for_every_provider(monkeypatch, provider):
    async def raw(*args, **kwargs):
        return '{"count": 3, "label": "ok"}'
    monkeypatch.setattr(llm, "llm_generate", raw)
    assert await llm.llm_generate_json("prompt", provider=provider, response_schema=StrictResult) == {"count": 3, "label": "ok"}


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["", "not json", '{"count":"wrong","label":"x"}', '{"count":1}', '{"count":1,"label":"x","extra":true}'])
async def test_malformed_missing_wrong_and_additional_output_fails_closed(monkeypatch, raw):
    async def response(*args, **kwargs):
        return raw
    monkeypatch.setattr(llm, "llm_generate", response)
    with pytest.raises((json.JSONDecodeError, ValidationError, IndexError)):
        await llm.llm_generate_json("prompt", response_schema=StrictResult)


@pytest.mark.asyncio
async def test_openai_uses_json_mode_and_anthropic_response_is_parsed_and_validated(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "offline-test-key")
    calls = {}
    async def openai_create(**kwargs):
        calls.update(kwargs)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"count":1,"label":"openai"}'))])
    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=openai_create)))
    monkeypatch.setattr(llm, "_get_openai_client", lambda: client)
    assert json.loads(await llm._generate_openai("json prompt", 30, 0, StrictResult))["label"] == "openai"
    assert calls["response_format"] == {"type": "json_object"}

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "offline-test-key")
    async def anthropic_create(**kwargs):
        return types.SimpleNamespace(content=[types.SimpleNamespace(text='{"count":2,"label":"anthropic"}')])
    monkeypatch.setattr(llm, "_get_anthropic_client", lambda: types.SimpleNamespace(messages=types.SimpleNamespace(create=anthropic_create)))
    assert json.loads(await llm._generate_anthropic("json prompt", 30, 0))["label"] == "anthropic"


@pytest.mark.asyncio
async def test_gemini_requests_json_mime_type_with_schema(monkeypatch):
    captured = {}
    class GenerationConfig:
        def __init__(self, **kwargs): captured.update(kwargs)
    genai = types.ModuleType("google.generativeai")
    genai.types = types.SimpleNamespace(GenerationConfig=GenerationConfig)
    google = types.ModuleType("google")
    google.__path__ = []
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai)
    async def generate_content_async(prompt, generation_config):
        return types.SimpleNamespace(text='{"count":2,"label":"gemini"}')
    monkeypatch.setattr(llm, "_get_gemini_model", lambda: types.SimpleNamespace(generate_content_async=generate_content_async))
    assert json.loads(await llm._generate_gemini("json prompt", 30, 0, StrictResult))["label"] == "gemini"
    assert captured["response_mime_type"] == "application/json"


@pytest.mark.asyncio
async def test_transient_provider_errors_retry_boundedly_and_bad_request_does_not(monkeypatch):
    from tenacity import stop_after_attempt
    attempts = {"timeout": 0, "rate_limit": 0, "bad": 0}
    async def timeout(*args, **kwargs):
        attempts["timeout"] += 1
        raise TimeoutError("temporary")
    async def bad(*args, **kwargs):
        attempts["bad"] += 1
        error = RuntimeError("invalid request")
        error.status_code = 400
        raise error
    async def rate_limit(*args, **kwargs):
        attempts["rate_limit"] += 1
        error = RuntimeError("rate limited")
        error.status_code = 429
        raise error
    monkeypatch.setattr(llm, "_generate_openai", timeout)
    old_wait, old_stop = llm.llm_generate.retry.wait, llm.llm_generate.retry.stop
    llm.llm_generate.retry.wait, llm.llm_generate.retry.stop = wait_none(), stop_after_attempt(2)
    try:
        with pytest.raises(TimeoutError):
            await llm.llm_generate("prompt", provider="openai")
        assert attempts["timeout"] == 2
        monkeypatch.setattr(llm, "_generate_openai", rate_limit)
        with pytest.raises(RuntimeError):
            await llm.llm_generate("prompt", provider="openai")
        assert attempts["rate_limit"] == 2
        monkeypatch.setattr(llm, "_generate_openai", bad)
        with pytest.raises(RuntimeError):
            await llm.llm_generate("prompt", provider="openai")
        assert attempts["bad"] == 1
    finally:
        llm.llm_generate.retry.wait, llm.llm_generate.retry.stop = old_wait, old_stop

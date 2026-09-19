"""Codex cache routing must match the actual SDK body without changing backend identity."""
import json

import httpx
import pytest
from openai import OpenAI

from agent.chat_completion_helpers import build_api_kwargs
from agent.codex_responses_adapter import classify_responses_route
from agent.transports.codex import ResponsesApiTransport


@pytest.mark.parametrize("model", ["gpt-5.4", "openrouter/openai/gpt-oss-20b", "ollama/llama3.1:8b"])
def test_opencdx_runtime_headers_follow_cache_scope_on_wire(tmp_path, model):
    from hermes_cli.config import save_config
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from hermes_state import SessionDB
    from run_agent import AIAgent

    save_config({"model": {"provider": "opencdx", "default": model}, "providers": {
        "opencdx": {"base_url": "http://127.0.0.1:17464/v1", "api_key": "local-test",
                    "api_mode": "codex_responses", "discover_models": False,
                    "extra_headers": {"Session-Id": "stale", "THREAD-ID": "stale",
                                      "X-Client-Request-Id": "stale", "session_id": "legacy"}}}})
    runtime = resolve_runtime_provider(requested="opencdx")
    assert runtime["provider"] == "custom"
    db = SessionDB(db_path=tmp_path / "state.db")
    db.create_session("root", source="cli", model=model)
    agent = AIAgent(model=model, provider=runtime["provider"], requested_provider="opencdx",
                    base_url=runtime["base_url"], api_key=runtime["api_key"], api_mode=runtime["api_mode"],
                    enabled_toolsets=[], quiet_mode=True, skip_context_files=True, skip_memory=True,
                    session_id="root", max_tokens=123)
    agent._session_db = db
    captured = []
    def capture(request):
        captured.append((request.headers, json.loads(request.content)))
        return httpx.Response(200, json={"id": "resp_test", "object": "response", "output": [],
                                       "status": "completed", "model": model, "created_at": 0})
    try:
        with OpenAI(api_key="local-test", base_url=runtime["base_url"],
                    default_headers=agent._client_kwargs.get("default_headers"),
                    http_client=httpx.Client(transport=httpx.MockTransport(capture))) as client:
            messages = [{"role": "system", "content": "Stable instructions"}, {"role": "user", "content": "First"}]
            for sid in ("root", "root", "rotated"):
                if sid == "rotated":
                    db.end_session("root", "compression")
                    db.create_session(sid, source="cli", model=model, parent_session_id="root")
                agent.session_id = sid
                kwargs = build_api_kwargs(agent, messages, [])
                assert not classify_responses_route(agent).is_codex_backend
                assert "context_management" not in kwargs
                assert kwargs["max_output_tokens"] == 123
                client.responses.create(**agent._get_transport().preflight_kwargs(kwargs))
                messages += [{"role": "assistant", "content": "Answer"}, {"role": "user", "content": "Next"}]
        for (headers, body), sid in zip(captured, ("root", "root", "rotated")):
            assert headers.get_list("session-id") == [body["prompt_cache_key"]]
            assert headers.get_list("thread-id") == headers.get_list("x-client-request-id") == [sid]
            assert headers["thread-id"] == headers["x-client-request-id"] == sid
            assert "session_id" not in headers
        assert len({body["prompt_cache_key"] for _, body in captured}) == 1
    finally:
        db.close()


@pytest.mark.parametrize("provider,requested,codex,enabled", [
    ("openai-codex", "openai-codex", True, True),
    ("custom", "opencdx", False, True),
    ("opencdx", None, False, True),
    ("custom", "other", False, False),
    ("openrouter", "opencdx", False, False),
])
@pytest.mark.parametrize("override,top_level", [("k" * 80, "top"), ("café", "top"), ("a\nb", "top"), ("", None), (None, None)])
def test_affinity_activation_and_effective_override(provider, requested, codex, enabled, override, top_level):
    overrides = {"prompt_cache_key": top_level, "extra_body": {"prompt_cache_key": override},
                 "extra_headers": {"Session-Id": "stale", "Thread-Id": "stale", "X-Test": "keep"}}
    transport = ResponsesApiTransport()
    kwargs = transport.build_kwargs(model="gpt-5.4", messages=[{"role": "user", "content": "Hi"}],
                                    session_id="physical", cache_scope_id="logical", provider=provider,
                                    requested_provider=requested, is_codex_backend=codex,
                                    request_overrides=overrides)
    captured = []
    def capture(request):
        captured.append((request.headers, json.loads(request.content)))
        return httpx.Response(200, json={"id": "resp_test", "object": "response", "output": [],
                                       "status": "completed", "model": "gpt-5.4", "created_at": 0})
    with OpenAI(api_key="test", base_url="https://endpoint.invalid/v1",
                http_client=httpx.Client(transport=httpx.MockTransport(capture))) as client:
        client.responses.create(**transport.preflight_kwargs(kwargs))
    headers, body = captured[0]
    assert headers["x-test"] == "keep"
    if enabled:
        if "prompt_cache_key" in body:
            assert headers.get_list("session-id") == [body["prompt_cache_key"]]
            assert len(body["prompt_cache_key"]) <= 64
        else:
            assert "session-id" not in headers
        assert headers["thread-id"] == headers["x-client-request-id"] == "physical"
    else:
        assert headers["session-id"] == "stale"
        assert "x-client-request-id" not in headers

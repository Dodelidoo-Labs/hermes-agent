"""Auxiliary Responses must retain the same cache/header contract as main turns."""
import json

import httpx
import pytest
from openai import OpenAI

from agent import auxiliary_client as aux


@pytest.mark.parametrize("provider,base,expected", [
    ("opencdx", "http://127.0.0.1:17464/v1", True),
    ("custom", "http://127.0.0.1:17464/v1", True),
    ("custom", "http://127.0.0.1:17464/other/v1", False),
    ("custom", "https://chatgpt.com/backend-api/codex", True),
])
def test_auxiliary_resolver_affinity_is_endpoint_scoped(provider, base, expected):
    from hermes_cli.config import save_config
    save_config({"model": {"provider": "opencdx", "default": "gpt-5.4"}, "providers": {
        "opencdx": {"base_url": "http://127.0.0.1:17464/v1", "api_key": "local-test",
                    "api_mode": "codex_responses", "discover_models": False,
                    "extra_headers": {"Session-Id": "stale", "Thread-Id": "stale"}}}})
    token = aux.set_runtime_main("custom", "gpt-5.4", requested_provider="opencdx",
                                base_url="http://127.0.0.1:17464/v1", session_id="thread",
                                cache_scope="stable-scope")
    wrapper = None
    try:
        wrapper, _ = aux.resolve_provider_client(provider, model="gpt-5.4", explicit_base_url=base,
                                                 explicit_api_key="local-test", api_mode="codex_responses")
        assert isinstance(wrapper, aux.CodexAuxiliaryClient)
        payload, _, _ = wrapper.chat.completions._build_responses_kwargs({
            "messages": [{"role": "system", "content": "Stable instructions"},
                         {"role": "user", "content": "Summarize"}]})
        seen = []
        def capture(request):
            seen.append((request.headers, json.loads(request.content)))
            return httpx.Response(200, json={"id": "resp_test", "object": "response", "output": [],
                                           "status": "completed", "model": "gpt-5.4", "created_at": 0})
        with OpenAI(api_key="local-test", base_url=base,
                    default_headers=wrapper._real_client._custom_headers,
                    http_client=httpx.Client(transport=httpx.MockTransport(capture))) as client:
            client.responses.create(**payload)
        headers, body = seen[0]
        if expected:
            assert headers.get_list("session-id") == [body["prompt_cache_key"]]
            assert headers.get_list("thread-id") == headers.get_list("x-client-request-id") == ["thread"]
        else:
            assert "session-id" not in headers
            assert "thread-id" not in headers
        assert "context_management" not in body
    finally:
        if wrapper is not None:
            wrapper.close()
        aux.reset_runtime_main(token)

"""Custom endpoint discovery must refresh membership and capabilities as one catalog."""
import io
import json
from unittest.mock import patch

from hermes_cli import models
from hermes_cli.inventory import _apply_capabilities
from hermes_cli.model_switch_providers import _finalize_picker_rows
from hermes_cli.models_endpoint_catalog import EndpointModels


def test_live_catalog_changes_reach_picker_and_request_metadata(monkeypatch, tmp_path):
    from hermes_cli.config import save_config
    from hermes_cli.config_providers import get_custom_provider_context_length
    from hermes_cli.inventory import load_picker_context, build_models_payload
    from agent.transports.codex import _profile_declared_efforts

    state = [{'id': 'old', 'context_length': 1000,
              'reasoning': {'supported_efforts': ['low', 'high'], 'default_effort': 'low'}}]
    calls = []
    class Response(io.BytesIO):
        headers = {'Cache-Control': 'private, no-cache'}
    def request(req, **kwargs):
        calls.append(req.get_header('Authorization'))
        return Response(json.dumps({'object': 'list', 'data': state}).encode())
    monkeypatch.setattr(models, '_urlopen_model_catalog_request', request)
    cfg = {'model': {'provider': 'relay', 'default': 'old'}, 'providers': {
        'relay': {'base_url': 'http://127.0.0.1:9876/v1', 'api_mode': 'codex_responses',
                  'key_cmd': "printf '%s' '{\"access_token\":\"local-token\",\"expires_in\":300}'"}}}
    save_config(cfg)
    def picker():
        payload = build_models_payload(load_picker_context(), explicit_only=True, capabilities=True,
                                       probe_current_custom_provider=True, non_blocking_catalogs=True)
        return next(r for r in payload['providers'] if r['slug'] == 'relay')
    first = picker()
    assert first['models'] == ['old']
    assert first['capabilities']['old']['supported_efforts'] == ['low', 'high']
    assert get_custom_provider_context_length('old', 'http://127.0.0.1:9876/v1', config=cfg) == 1000
    assert _profile_declared_efforts('custom', 'old', 'http://127.0.0.1:9876/v1') == ('low', 'high')
    state[:] = [{'id': 'new', 'context_length': 2000,
                 'reasoning': {'supported_efforts': ['medium'], 'default_effort': 'medium'}}]
    second = picker()
    assert second['models'] == ['new']  # selected "old" must not be resurrected
    assert set(second['capabilities']) == {'new'}
    assert second['capabilities']['new']['supported_efforts'] == ['medium']
    assert get_custom_provider_context_length('new', 'http://127.0.0.1:9876/v1', config=cfg) == 2000
    state[0]['reasoning'] = {'supported_efforts': ['none'], 'default_effort': 'none'}
    third = picker()
    assert third['capabilities']['new']['reasoning'] is False
    state.clear()
    assert picker()['models'] == []
    assert calls and all(c == 'Bearer local-token' for c in calls)
    assert 'models' not in cfg['providers']['relay']


def test_catalog_cache_keeps_metadata_scoped_to_credentials(monkeypatch):
    catalog = EndpointModels([{'id': 'a', 'reasoning': {'supported_efforts': ['high']}}], 60)
    fetch = lambda key, *a, **kw: catalog if key == 'tenant-a' else EndpointModels([], 60)
    monkeypatch.setattr(models, 'fetch_api_models', fetch)
    a = models.cached_fetch_api_models('tenant-a', 'https://relay.invalid/v1')
    b = models.cached_fetch_api_models('tenant-b', 'https://relay.invalid/v1')
    assert a == ['a'] and b == []
    monkeypatch.setattr(models, 'fetch_api_models', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('unexpected fetch')))
    cached = models.cached_fetch_api_models('tenant-a', 'https://relay.invalid/v1')
    assert cached.metadata == a.metadata
    assert models.cached_fetch_api_models('tenant-b', 'https://relay.invalid/v1') == []

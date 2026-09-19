"""Preserve custom endpoint catalog metadata alongside its credential-scoped ID cache."""
from __future__ import annotations

import json
import re


class CatalogJSON(dict):
    def __init__(self, value: dict, cache_control: str = ''):
        super().__init__(value)
        self.cache_ttl_seconds = None
        if isinstance(cache_control, str):
            if re.search(r'(?:^|,)\s*(?:no-cache|no-store)\b', cache_control):
                self.cache_ttl_seconds = 0
            elif match := re.search(r'(?:^|,)\s*max-age=(\d+)', cache_control):
                self.cache_ttl_seconds = int(match[1])


def read_catalog_response(response):
    value = json.loads(response.read().decode())
    if isinstance(value, dict):
        return CatalogJSON(value, getattr(response, 'headers', {}).get('Cache-Control', ''))
    return value


class EndpointModels(list):
    """Successful /models result, including an authoritative empty catalog."""
    def __init__(self, items: list, cache_ttl_seconds=None):
        fields = ('id', 'name', 'context_length', 'reasoning', 'supported_reasoning_levels',
                  'default_reasoning_level', 'service_tiers', 'default_service_tier', 'input_modalities')
        self.metadata = {
            item['id']: {key: item[key] for key in fields if key in item}
            for item in items if isinstance(item, dict) and isinstance(item.get('id'), str) and item['id']
        }
        super().__init__(self.metadata)
        self.cache_ttl_seconds = cache_ttl_seconds


def catalog_capabilities(metadata: dict) -> dict:
    """Only explicit declarations override generic heuristics; no invented effort levels."""
    caps = {}
    reasoning = metadata.get('reasoning')
    efforts = reasoning.get('supported_efforts') if isinstance(reasoning, dict) else None
    if isinstance(efforts, list) and all(isinstance(e, str) for e in efforts):
        caps.update(reasoning=any(e != 'none' for e in efforts),
                    supported_efforts=efforts, can_disable_reasoning='none' in efforts)
        default = reasoning.get('default_effort')
        if isinstance(default, str) and default in efforts:
            caps['default_effort'] = default
    if isinstance(metadata.get('service_tiers'), list):
        caps['fast'] = any(t == 'priority' or (isinstance(t, dict) and t.get('id') == 'priority')
                           for t in metadata['service_tiers'])
    return caps


def endpoint_model_metadata(model: str, base_url: str, config: dict | None = None):
    """Read the route's live catalog using the same profile/credential cache as its picker."""
    from hermes_cli.config import get_compatible_custom_providers
    from hermes_cli.model_switch_providers import _entry_credentials, _entry_api_mode
    from hermes_cli.model_switch import _extra_headers_from_config, _scoped_key_env
    from hermes_cli.models import cached_fetch_api_models
    if not model or not base_url:
        return None
    entries = [entry for entry in get_compatible_custom_providers(config)
               if str(entry.get('base_url') or '').rstrip('/') == str(base_url).rstrip('/')]
    # A URL alone cannot choose between tenants with different credentials.
    if len(entries) != 1:
        return None
    for entry in entries:
        if entry.get('discover_models', True) is False:
            continue
        key, env, _ = _entry_credentials(entry, 'key_env', 'api_key_env')
        models = cached_fetch_api_models(key or _scoped_key_env(env), base_url,
                                        api_mode=_entry_api_mode(entry),
                                        headers=_extra_headers_from_config(entry) or None)
        return models.metadata.get(model) if isinstance(models, EndpointModels) else None
    return None

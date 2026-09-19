# Hermes and live model discovery

The local helper exposes authenticated `GET /v1/models` alongside the Responses
API. It reads the atomically synchronized catalog on every request. Model IDs,
context windows, advertised reasoning levels and defaults, modalities, and
service tiers come from the same catalog Codex reads. Hidden models are omitted.
No model list needs to be copied into another application's configuration.

The helper synchronizes with the router every minute. Discovery reflects the
latest completed synchronization; provider refresh intervals on the router
still apply. The endpoint returns an ETag that also changes for metadata-only
updates and `Cache-Control: private, no-cache`. Missing or invalid catalogs
return `503`; an empty catalog returns an empty `data` array. Discovery does not
count as inference activity or usage.

## Configuration

```yaml
model:
  provider: opencdx
  default: gpt-6-astra
providers:
  opencdx:
    base_url: http://127.0.0.1:17464/v1
    api_mode: codex_responses
    discover_models: true
    key_cmd: >-
      "/Applications/OpenCDX Router.app/Contents/Resources/router-helper" token --json
```

Select an available default model. Do not add a `models:` snapshot. The token
command returns `access_token` and `expires_in`; Hermes can renew credentials
before expiry. The helper's default `token` output remains a bare token for
Codex command authentication. No provider API key is stored in Hermes.

## Maintained Hermes compatibility

Hermes revision `1879088d3fadb885d04035f5fa658b6efc08a7a1` supports Responses
and command credentials, but its custom endpoint discovery discards model
metadata. Its Desktop picker uses a generic reasoning ladder and can reinsert
the selected model after discovery removes it. Its endpoint Test button also
does not use saved command credentials.

The maintained `main` branch implements these client behaviors for custom endpoints:

- Cache model IDs and metadata together, scoped to endpoint and credentials;
  respect the endpoint's cache lifetime.
- Treat successful discovery as authoritative, including empty catalogs and
  removals of the selected model.
- Use advertised effort lists, defaults, service tiers, and context limits in
  the picker and Responses request path.
- Refresh the Desktop picker each minute while mounted.
- Use saved credentials for endpoint validation only when its destination
  matches the saved endpoint.
- Send official Codex affinity headers on native Codex and the named `opencdx`
  Responses route, including auxiliary requests (compression and memory work).
  `session-id` matches the effective body `prompt_cache_key`; `thread-id` and
  `x-client-request-id` carry the physical conversation ID. Cache scope survives
  Hermes compression rotation. The router keeps account selection separate from
  upstream cache affinity; upstream cache reuse is still determined by the provider.
- Keep OpenRouter/Ollama backend classification unchanged. Auxiliary requests
  inherit the main openCDX route identity only when their complete endpoints match;
  an explicitly selected `opencdx` auxiliary provider also enables the headers.
- Prevent stale mixed-case configured headers from creating duplicate affinity
  fields in the OpenAI SDK. Explicit body overrides remain authoritative, keys
  unsafe for HTTP headers are hashed consistently, and omitting a body key also
  omits its cache-affinity header.

These are source changes maintained in [Dodelidoo-Labs/hermes-agent](https://github.com/Dodelidoo-Labs/hermes-agent/tree/main), not a patch stored in OpenCDX.
See [fork maintenance](../FORK_MAINTENANCE.md) for tested upstream integration and update behavior.
Desktop picker changes require rebuilding Desktop; Python-only header changes
need a backend restart so an already running backend imports the new code.

## Verification

The helper regression test replaces a catalog while serving requests and checks
additions, removals (including the final model), metadata-only ETag changes,
authentication, and invalid-file handling. Hermes tests cover the discovery-to-
picker-to-request path, credential cache isolation, an empty live catalog,
endpoint validation credentials, and rendered reasoning option changes.

Cache-header tests exercise isolated configuration and real runtime resolution,
AIAgent request construction, preflight, and OpenAI SDK HTTP serialization. They
cover follow-up turns, compression rotation, all three openCDX model families,
auxiliary route isolation, explicit body overrides, and stale mixed-case headers.
They use a local HTTP transport stub and do not spend inference tokens; they prove
request compatibility, not a particular production cache-hit rate.

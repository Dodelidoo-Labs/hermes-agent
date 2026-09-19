#!/usr/bin/env bash
set -euo pipefail
scripts/run_tests.sh -j 2 \
  tests/agent/test_codex_affinity_headers.py \
  tests/agent/test_auxiliary_codex_affinity.py \
  tests/agent/test_prompt_cache_scope.py \
  tests/agent/transports/test_codex_transport.py \
  tests/agent/test_codex_responses_adapter.py \
  tests/agent/test_run_agent_codex_responses.py \
  tests/agent/test_auxiliary_user_default_headers.py \
  tests/agent/test_auxiliary_named_custom_providers.py \
  tests/hermes_cli/test_endpoint_catalog_metadata.py \
  tests/hermes_cli/test_endpoint_command_validation.py \
  tests/hermes_cli/test_model_switch_custom_providers.py \
  tests/hermes_cli/test_cached_fetch_api_models.py \
  tests/hermes_cli/test_inventory_reasoning_caps.py \
  tests/tui_gateway/contracts/test_generated.py \
  tests/hermes_cli/test_opencdx_update_branch.py \
  tests/hermes_cli/test_maintained_update_preservation.py \
  tests/scripts/test_opencdx_release.py

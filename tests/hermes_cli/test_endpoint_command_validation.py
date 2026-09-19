"""Desktop endpoint tests use saved command credentials only at their saved destination."""
import pytest
from hermes_cli.web_models import CustomEndpointUpdate
from hermes_cli.web_routers import config_env


@pytest.mark.asyncio
async def test_probe_uses_saved_command_only_for_matching_url(monkeypatch):
    from hermes_cli.config import save_config
    url = 'http://127.0.0.1:9876/v1'
    save_config({'providers': {'relay': {'base_url': url, 'api_mode': 'codex_responses',
                 'key_cmd': "printf '%s' '{\"access_token\":\"command-token\",\"expires_in\":300}'"}}})
    sent=[]
    class Response:
        status_code=200
        is_success=True
        def json(self): return {'data': [{'id': 'model'}]}
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, target, headers):
            sent.append((target, headers.copy()))
            return Response()
    monkeypatch.setattr(config_env,'_endpoint_probe_client',lambda *args: Client())
    for target in [url, 'https://different.invalid/v1']:
        result=await config_env.validate_custom_endpoint(CustomEndpointUpdate(id='relay',name='relay',base_url=target,model='model'))
        assert result['ok']
    assert sent[0][1]['Authorization']=='Bearer command-token'
    assert 'Authorization' not in sent[1][1]

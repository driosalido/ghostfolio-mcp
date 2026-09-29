"""Portfolio tools resolve tag and account names to IDs for Ghostfolio's filters."""

import httpx2
import pytest
from fastmcp import FastMCP

from ghostfolio_mcp import ghostfolio_client as client_module
from ghostfolio_mcp.ghostfolio_client import GhostfolioClient
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.tools import register_tools

BASE_URL = "https://ghostfolio.test:3333"
AUTH_PATH = "/api/v1/auth/anonymous/"
USER = {
    "id": "u",
    "accounts": [
        {"id": "acc-indexa", "name": "Indexa Capital"},
        {"id": "acc-ibkr", "name": "Interactive Brokers"},
    ],
    "tags": [
        {"id": "tag-bolsa", "name": "BOLSA"},
        {"id": "tag-pp", "name": "PLAN_PENSIONES"},
    ],
}


@pytest.fixture
def server():
    config = GhostfolioConfig(ghostfolio_url=BASE_URL, token="api-token")
    mcp = FastMCP(name="test")
    register_tools(mcp, config)

    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == AUTH_PATH:
            return httpx2.Response(200, json={"authToken": "jwt"})
        if request.url.path == "/api/v1/user/":
            return httpx2.Response(200, json=USER)
        requests.append(request)
        return httpx2.Response(200, json={})

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
    client = client_module.get_ghostfolio_client(config)
    client.client = httpx2.AsyncClient(
        base_url=client.base_url, transport=httpx2.MockTransport(handler)
    )

    yield mcp, requests

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None


async def call(mcp: FastMCP, name: str, **arguments):
    tool = await mcp.get_tool(name)
    return await tool.run(arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    [
        "get_portfolio_details",
        "get_portfolio_holdings",
        "get_portfolio_performance",
        "get_investments",
        "get_dividends",
    ],
)
async def test_names_resolve_to_ids(server, name):
    mcp, requests = server
    await call(
        mcp,
        name,
        accounts=["Indexa Capital"],
        tags=["BOLSA", "tag-pp"],
        asset_classes=["EQUITY", "FIXED_INCOME"],
    )
    params = requests[0].url.params
    assert params["accounts"] == "acc-indexa"
    assert params["tags"] == "tag-bolsa,tag-pp"
    assert params["assetClasses"] == "EQUITY,FIXED_INCOME"


@pytest.mark.asyncio
async def test_no_filters_sends_no_filter_params(server):
    mcp, requests = server
    await call(mcp, "get_portfolio_holdings")
    params = requests[0].url.params
    assert dict(params) == {"range": "max"}


@pytest.mark.asyncio
async def test_asset_class_alone_skips_the_user_lookup(server):
    mcp, requests = server
    await call(mcp, "get_portfolio_holdings", asset_classes=["LIQUIDITY"])
    assert [r.url.path for r in requests] == ["/api/v1/portfolio/holdings/"]


@pytest.mark.asyncio
async def test_unknown_account_fails_before_the_request(server):
    mcp, requests = server
    with pytest.raises(Exception, match=r"Unknown account 'Indexa'.*Indexa Capital"):
        await call(mcp, "get_portfolio_holdings", accounts=["Indexa"])
    assert requests == []

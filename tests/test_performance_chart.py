"""get_portfolio_performance drops the daily chart unless asked for it."""

import httpx2
import pytest
from fastmcp import FastMCP

from ghostfolio_mcp import ghostfolio_client as client_module
from ghostfolio_mcp.ghostfolio_client import GhostfolioClient
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.tools import register_tools

BASE_URL = "https://ghostfolio.test:3333"
AUTH_PATH = "/api/v1/auth/anonymous/"
PERFORMANCE = {
    "chart": [{"date": "2026-09-28", "netWorth": 1.0}],
    "performance": {"currentValueInBaseCurrency": 1.0},
    "hasErrors": False,
}


@pytest.fixture
def mcp():
    config = GhostfolioConfig(ghostfolio_url=BASE_URL, token="api-token")
    server = FastMCP(name="test")
    register_tools(server, config)

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == AUTH_PATH:
            return httpx2.Response(200, json={"authToken": "jwt"})
        return httpx2.Response(200, json=PERFORMANCE)

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
    client = client_module.get_ghostfolio_client(config)
    client.client = httpx2.AsyncClient(
        base_url=client.base_url, transport=httpx2.MockTransport(handler)
    )

    yield server

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None


async def performance(mcp: FastMCP, **arguments) -> dict:
    tool = await mcp.get_tool("get_portfolio_performance")
    result = await tool.run(arguments)
    return result.structured_content


@pytest.mark.asyncio
async def test_chart_is_dropped_by_default(mcp):
    result = await performance(mcp)
    assert "chart" not in result
    assert result["performance"] == {"currentValueInBaseCurrency": 1.0}


@pytest.mark.asyncio
async def test_chart_is_kept_when_requested(mcp):
    result = await performance(mcp, include_chart=True)
    assert result["chart"] == PERFORMANCE["chart"]

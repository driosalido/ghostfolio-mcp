"""create_activity resolves tag names to IDs before posting."""

import json

import httpx2
import pytest
from fastmcp import FastMCP

from ghostfolio_mcp import ghostfolio_client as client_module
from ghostfolio_mcp.ghostfolio_client import GhostfolioClient
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.tools import register_tools

BASE_URL = "https://ghostfolio.test:3333"
AUTH_PATH = "/api/v1/auth/anonymous/"
USER_TAGS = [
    {"id": "tag-bolsa", "name": "BOLSA", "userId": "u"},
    {"id": "tag-pp", "name": "PLAN_PENSIONES", "userId": "u"},
]


@pytest.fixture
def server():
    config = GhostfolioConfig(ghostfolio_url=BASE_URL, token="api-token")
    mcp = FastMCP(name="test")
    register_tools(mcp, config)

    posted: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == AUTH_PATH:
            return httpx2.Response(200, json={"authToken": "jwt"})
        if request.url.path == "/api/v1/user/":
            return httpx2.Response(200, json={"id": "u", "tags": USER_TAGS})
        if request.method == "POST" and request.url.path == "/api/v1/activities":
            posted.append(json.loads(request.content))
            return httpx2.Response(201, json={"id": "new"})
        return httpx2.Response(404)

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
    client = client_module.get_ghostfolio_client(config)
    client.client = httpx2.AsyncClient(
        base_url=client.base_url, transport=httpx2.MockTransport(handler)
    )

    yield mcp, posted

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None


ACTIVITY = {
    "type": "BUY",
    "symbol": "SPPW.DE",
    "date": "2026-10-01",
    "quantity": 1,
    "unit_price": 47.0,
    "currency": "EUR",
    "data_source": "YAHOO",
    "account_id": "acc",
}


async def create(mcp: FastMCP, **extra):
    tool = await mcp.get_tool("create_activity")
    return await tool.run({**ACTIVITY, **extra})


@pytest.mark.asyncio
async def test_tag_names_and_ids_are_sent_as_ids(server):
    mcp, posted = server
    await create(mcp, tags=["BOLSA", "tag-pp"])
    assert posted[0]["tags"] == ["tag-bolsa", "tag-pp"]


@pytest.mark.asyncio
async def test_unknown_tag_fails_before_posting(server):
    mcp, posted = server
    with pytest.raises(Exception, match=r"Unknown tag 'bolsa'.*BOLSA, PLAN_PENSIONES"):
        await create(mcp, tags=["bolsa"])
    assert posted == []


@pytest.mark.asyncio
async def test_no_tags_leaves_body_unchanged(server):
    mcp, posted = server
    await create(mcp)
    assert "tags" not in posted[0]


@pytest.mark.asyncio
async def test_get_tags_lists_id_and_name(server):
    mcp, _ = server
    tool = await mcp.get_tool("get_tags")
    result = await tool.run({})
    assert result.structured_content["result"] == [
        {"id": "tag-bolsa", "name": "BOLSA"},
        {"id": "tag-pp", "name": "PLAN_PENSIONES"},
    ]

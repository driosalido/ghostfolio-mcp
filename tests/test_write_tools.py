"""GHOSTFOLIO_WRITE_TOOLS re-enables named tools on top of read-only mode.

server.py configures visibility at import time from the environment, so each
case imports it in a fresh interpreter.
"""

import json
import os
import subprocess
import sys

LIST_TOOLS = (
    "import asyncio, json\n"
    "from ghostfolio_mcp.server import mcp\n"
    "print(json.dumps(sorted(t.name for t in asyncio.run(mcp.list_tools()))))\n"
)


def visible_tools(**env: str) -> set[str]:
    ambient = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {"READ_ONLY_MODE", "GHOSTFOLIO_WRITE_TOOLS", "GHOSTFOLIO_DISABLED_TAGS"}
    }
    full_env = {
        **ambient,
        "GHOSTFOLIO_URL": "https://ghostfolio.test",
        "GHOSTFOLIO_TOKEN": "t",
        "LOG_LEVEL": "ERROR",
        **env,
    }
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", LIST_TOOLS],
        env=full_env,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(json.loads(out.stdout.strip().splitlines()[-1]))


def test_read_only_hides_every_write_tool():
    tools = visible_tools(READ_ONLY_MODE="true")
    assert "get_portfolio_performance" in tools
    assert "create_activity" not in tools
    assert "delete_activity" not in tools


def test_write_tools_allowlist_adds_only_named_tools():
    tools = visible_tools(
        READ_ONLY_MODE="true", GHOSTFOLIO_WRITE_TOOLS="create_activity"
    )
    assert "create_activity" in tools
    assert "get_tags" in tools
    for destructive in (
        "delete_activity",
        "delete_account",
        "create_account",
        "import_transactions",
        "create_account_balance",
    ):
        assert destructive not in tools

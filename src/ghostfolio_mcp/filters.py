"""Resolve human-friendly tag and account names to the IDs Ghostfolio filters on.

Ghostfolio's portfolio and activity endpoints take ``accounts``, ``tags`` and
``assetClasses`` as comma-separated query parameters, and the first two expect
IDs. Several values of one filter combine as OR; different filters as AND.
"""

from typing import Annotated
from typing import Any

from pydantic import Field

AccountsFilter = Annotated[
    list[str] | None,
    Field(
        default=None,
        description="Optional account names or IDs to restrict to (see get_accounts)",
    ),
]
TagsFilter = Annotated[
    list[str] | None,
    Field(
        default=None,
        description="Optional tag names or IDs to restrict to (see get_tags), e.g. ['BOLSA']",
    ),
]
AssetClassesFilter = Annotated[
    list[str] | None,
    Field(
        default=None,
        description="Optional asset classes, e.g. ['EQUITY', 'FIXED_INCOME', 'LIQUIDITY']",
    ),
]


async def get_user_tags(client: Any) -> list[dict[str, Any]]:
    """Return the user's tags as [{"id", "name"}] from GET /v1/user."""
    user = await client.get("user")
    return [{"id": t["id"], "name": t["name"]} for t in user.get("tags", [])]


def _resolve(kind: str, values: list[str], known: list[dict[str, Any]]) -> list[str]:
    """Map names or IDs to IDs, failing on any unknown value.

    Failing here with the valid names beats sending a name where Ghostfolio
    expects an ID and silently getting back the wrong subset.
    """
    by_id = {k["id"]: k["id"] for k in known}
    by_name = {k["name"]: k["id"] for k in known}
    resolved = []
    for value in values:
        resolved_id = by_id.get(value) or by_name.get(value)
        if resolved_id is None:
            available = ", ".join(sorted(by_name)) or "none"
            raise ValueError(f"Unknown {kind} {value!r}. Available: {available}")
        resolved.append(resolved_id)
    return resolved


async def resolve_tag_ids(client: Any, tags: list[str]) -> list[str]:
    """Map tag names or IDs to IDs, failing on any unknown tag."""
    return _resolve("tag", tags, await get_user_tags(client))


async def filter_params(
    client: Any,
    accounts: list[str] | None = None,
    tags: list[str] | None = None,
    asset_classes: list[str] | None = None,
) -> dict[str, str]:
    """Build Ghostfolio's filter query parameters, resolving names to IDs."""
    params: dict[str, str] = {}
    if accounts or tags:
        user = await client.get("user")
        if accounts:
            known = [
                {"id": a["id"], "name": a["name"]} for a in user.get("accounts", [])
            ]
            params["accounts"] = ",".join(_resolve("account", accounts, known))
        if tags:
            known = [{"id": t["id"], "name": t["name"]} for t in user.get("tags", [])]
            params["tags"] = ",".join(_resolve("tag", tags, known))
    if asset_classes:
        params["assetClasses"] = ",".join(asset_classes)
    return params

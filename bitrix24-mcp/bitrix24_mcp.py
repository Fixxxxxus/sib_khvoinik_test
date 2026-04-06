"""Bitrix24 MCP Server — connects Claude Code to Bitrix24 REST API."""

import os
import json
from typing import Any

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

WEBHOOK_URL = os.environ["BITRIX24_WEBHOOK_URL"].rstrip("/")

mcp = FastMCP(
    "Bitrix24",
    description="CRM, tasks, forms, events, and mailings via Bitrix24 REST API",
)

_client = httpx.AsyncClient(timeout=30.0)


async def _call_b24(method: str, params: dict[str, Any] | None = None) -> Any:
    """Call Bitrix24 REST API method. Auto-paginates list responses."""
    url = f"{WEBHOOK_URL}/{method}.json"
    body = params or {}

    resp = await _client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        return {"error": data["error"], "error_description": data.get("error_description", "")}

    # Auto-paginate: Bitrix24 returns max 50 items per request
    result = data.get("result", data)
    if isinstance(result, list) and "next" in data:
        all_items = list(result)
        while "next" in data:
            body["start"] = data["next"]
            resp = await _client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                break
            page = data.get("result", [])
            if isinstance(page, list):
                all_items.extend(page)
            else:
                break
        return all_items

    return result


# ── Tools will be added below ──


if __name__ == "__main__":
    mcp.run()

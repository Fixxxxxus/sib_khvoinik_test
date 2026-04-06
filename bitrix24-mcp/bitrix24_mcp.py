"""Bitrix24 MCP Server — connects Claude Code to Bitrix24 REST API."""

import os
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


# ── CRM: Leads ──────────────────────────────────────────────


@mcp.tool
async def b24_lead_list(
    filter: dict[str, Any] | None = None,
    select: list[str] | None = None,
    order: dict[str, str] | None = None,
) -> Any:
    """List CRM leads with optional filter, select, and order."""
    params: dict[str, Any] = {}
    if filter:
        params["filter"] = filter
    if select:
        params["select"] = select
    if order:
        params["order"] = order
    return await _call_b24("crm.lead.list", params)


@mcp.tool
async def b24_lead_get(id: int) -> Any:
    """Get a CRM lead by ID."""
    return await _call_b24("crm.lead.get", {"ID": id})


@mcp.tool
async def b24_lead_add(fields: dict[str, Any]) -> Any:
    """Create a new CRM lead. Pass fields like TITLE, NAME, PHONE, etc."""
    return await _call_b24("crm.lead.add", {"fields": fields})


@mcp.tool
async def b24_lead_update(id: int, fields: dict[str, Any]) -> Any:
    """Update a CRM lead by ID."""
    return await _call_b24("crm.lead.update", {"ID": id, "fields": fields})


# ── CRM: Deals ──────────────────────────────────────────────


@mcp.tool
async def b24_deal_list(
    filter: dict[str, Any] | None = None,
    select: list[str] | None = None,
    order: dict[str, str] | None = None,
) -> Any:
    """List CRM deals with optional filter, select, and order."""
    params: dict[str, Any] = {}
    if filter:
        params["filter"] = filter
    if select:
        params["select"] = select
    if order:
        params["order"] = order
    return await _call_b24("crm.deal.list", params)


@mcp.tool
async def b24_deal_get(id: int) -> Any:
    """Get a CRM deal by ID."""
    return await _call_b24("crm.deal.get", {"ID": id})


@mcp.tool
async def b24_deal_add(fields: dict[str, Any]) -> Any:
    """Create a new CRM deal. Pass fields like TITLE, STAGE_ID, CONTACT_ID, etc."""
    return await _call_b24("crm.deal.add", {"fields": fields})


@mcp.tool
async def b24_deal_update(id: int, fields: dict[str, Any]) -> Any:
    """Update a CRM deal by ID."""
    return await _call_b24("crm.deal.update", {"ID": id, "fields": fields})


# ── CRM: Contacts ───────────────────────────────────────────


@mcp.tool
async def b24_contact_list(
    filter: dict[str, Any] | None = None,
    select: list[str] | None = None,
    order: dict[str, str] | None = None,
) -> Any:
    """List CRM contacts with optional filter, select, and order."""
    params: dict[str, Any] = {}
    if filter:
        params["filter"] = filter
    if select:
        params["select"] = select
    if order:
        params["order"] = order
    return await _call_b24("crm.contact.list", params)


@mcp.tool
async def b24_contact_get(id: int) -> Any:
    """Get a CRM contact by ID."""
    return await _call_b24("crm.contact.get", {"ID": id})


@mcp.tool
async def b24_contact_add(fields: dict[str, Any]) -> Any:
    """Create a new CRM contact. Pass fields like NAME, LAST_NAME, PHONE, EMAIL, etc."""
    return await _call_b24("crm.contact.add", {"fields": fields})


@mcp.tool
async def b24_contact_update(id: int, fields: dict[str, Any]) -> Any:
    """Update a CRM contact by ID."""
    return await _call_b24("crm.contact.update", {"ID": id, "fields": fields})


# ── CRM: Companies ──────────────────────────────────────────


@mcp.tool
async def b24_company_list(
    filter: dict[str, Any] | None = None,
    select: list[str] | None = None,
    order: dict[str, str] | None = None,
) -> Any:
    """List CRM companies with optional filter, select, and order."""
    params: dict[str, Any] = {}
    if filter:
        params["filter"] = filter
    if select:
        params["select"] = select
    if order:
        params["order"] = order
    return await _call_b24("crm.company.list", params)


@mcp.tool
async def b24_company_get(id: int) -> Any:
    """Get a CRM company by ID."""
    return await _call_b24("crm.company.get", {"ID": id})


@mcp.tool
async def b24_company_add(fields: dict[str, Any]) -> Any:
    """Create a new CRM company. Pass fields like TITLE, INDUSTRY, PHONE, etc."""
    return await _call_b24("crm.company.add", {"fields": fields})


@mcp.tool
async def b24_company_update(id: int, fields: dict[str, Any]) -> Any:
    """Update a CRM company by ID."""
    return await _call_b24("crm.company.update", {"ID": id, "fields": fields})


if __name__ == "__main__":
    mcp.run()

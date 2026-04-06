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


# ── Tasks ────────────────────────────────────────────────────


@mcp.tool
async def b24_task_list(
    filter: dict[str, Any] | None = None,
    select: list[str] | None = None,
    order: dict[str, str] | None = None,
) -> Any:
    """List tasks with optional filter, select, and order."""
    params: dict[str, Any] = {}
    if filter:
        params["filter"] = filter
    if select:
        params["select"] = select
    if order:
        params["order"] = order
    return await _call_b24("tasks.task.list", params)


@mcp.tool
async def b24_task_get(task_id: int) -> Any:
    """Get a task by ID."""
    return await _call_b24("tasks.task.get", {"taskId": task_id})


@mcp.tool
async def b24_task_add(fields: dict[str, Any]) -> Any:
    """Create a new task. Required fields: TITLE, RESPONSIBLE_ID. Optional: DESCRIPTION, DEADLINE, PRIORITY, etc."""
    return await _call_b24("tasks.task.add", {"fields": fields})


@mcp.tool
async def b24_task_update(task_id: int, fields: dict[str, Any]) -> Any:
    """Update a task by ID."""
    return await _call_b24("tasks.task.update", {"taskId": task_id, "fields": fields})


@mcp.tool
async def b24_task_comment_list(task_id: int) -> Any:
    """List comments on a task."""
    return await _call_b24("task.commentitem.getlist", {"TASKID": task_id})


@mcp.tool
async def b24_task_comment_add(task_id: int, text: str) -> Any:
    """Add a comment to a task."""
    return await _call_b24("task.commentitem.add", {"TASKID": task_id, "FIELDS": {"POST_MESSAGE": text}})


# ── CRM Forms ────────────────────────────────────────────────


@mcp.tool
async def b24_form_list() -> Any:
    """List all CRM web forms."""
    return await _call_b24("crm.webform.list")


@mcp.tool
async def b24_form_get(id: int) -> Any:
    """Get a CRM web form by ID."""
    return await _call_b24("crm.webform.get", {"ID": id})


@mcp.tool
async def b24_form_add(fields: dict[str, Any]) -> Any:
    """Create a new CRM web form."""
    return await _call_b24("crm.webform.add", {"fields": fields})


@mcp.tool
async def b24_form_update(id: int, fields: dict[str, Any]) -> Any:
    """Update a CRM web form by ID."""
    return await _call_b24("crm.webform.update", {"ID": id, "fields": fields})


# ── Events / Webhooks ────────────────────────────────────────


@mcp.tool
async def b24_event_list() -> Any:
    """List all available Bitrix24 events and active subscriptions."""
    return await _call_b24("event.get")


@mcp.tool
async def b24_event_bind(event: str, handler: str) -> Any:
    """Subscribe to a Bitrix24 event. Provide event name (e.g. 'ONCRMLEADADD') and handler URL."""
    return await _call_b24("event.bind", {"event": event, "handler": handler})


@mcp.tool
async def b24_event_unbind(event: str, handler: str) -> Any:
    """Unsubscribe from a Bitrix24 event."""
    return await _call_b24("event.unbind", {"event": event, "handler": handler})


# ── Mailings (sender module) ────────────────────────────────


@mcp.tool
async def b24_mailing_list(filter: dict[str, Any] | None = None) -> Any:
    """List email campaigns/mailings."""
    params: dict[str, Any] = {}
    if filter:
        params["filter"] = filter
    return await _call_b24("sender.letter.list", params)


@mcp.tool
async def b24_mailing_get(id: int) -> Any:
    """Get mailing campaign details by ID."""
    return await _call_b24("sender.letter.get", {"ID": id})


@mcp.tool
async def b24_mailing_add(fields: dict[str, Any]) -> Any:
    """Create a new mailing campaign."""
    return await _call_b24("sender.letter.add", {"fields": fields})


@mcp.tool
async def b24_mailing_update(id: int, fields: dict[str, Any]) -> Any:
    """Update a mailing campaign."""
    return await _call_b24("sender.letter.update", {"ID": id, "fields": fields})


@mcp.tool
async def b24_mailing_start(id: int) -> Any:
    """Start sending a mailing campaign."""
    return await _call_b24("sender.letter.send", {"ID": id})


@mcp.tool
async def b24_mailing_pause(id: int) -> Any:
    """Pause a mailing campaign."""
    return await _call_b24("sender.letter.pause", {"ID": id})


@mcp.tool
async def b24_mailing_stop(id: int) -> Any:
    """Stop a mailing campaign."""
    return await _call_b24("sender.letter.stop", {"ID": id})


@mcp.tool
async def b24_mailing_message_add(letter_id: int, fields: dict[str, Any]) -> Any:
    """Add content/message to a mailing campaign."""
    return await _call_b24("sender.message.add", {"LETTER_ID": letter_id, "fields": fields})


@mcp.tool
async def b24_mailing_message_update(id: int, fields: dict[str, Any]) -> Any:
    """Update content/message in a mailing campaign."""
    return await _call_b24("sender.message.update", {"ID": id, "fields": fields})


if __name__ == "__main__":
    mcp.run()

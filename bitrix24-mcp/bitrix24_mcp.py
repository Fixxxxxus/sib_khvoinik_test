"""Bitrix24 MCP Server — connects Claude Code to Bitrix24 REST API."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

WEBHOOK_URL = os.environ.get("BITRIX24_WEBHOOK_URL", "").rstrip("/")
if not WEBHOOK_URL:
    raise RuntimeError("BITRIX24_WEBHOOK_URL is not set. Create a .env file from .env.example.")

mcp = FastMCP(
    "Bitrix24",
    instructions="CRM, tasks, forms, events, and mailings via Bitrix24 REST API",
)

_client = httpx.AsyncClient(timeout=30.0)

MAX_PAGES = 200  # 200 pages × 50 items = 10,000 max


async def _call_b24(method: str, params: dict[str, Any] | None = None) -> Any:
    """Call Bitrix24 REST API method. Auto-paginates list responses."""
    url = f"{WEBHOOK_URL}/{method}.json"
    body = dict(params) if params else {}

    resp = await _client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        return {"error": data["error"], "error_description": data.get("error_description", "")}

    # Auto-paginate: Bitrix24 returns max 50 items per request
    result = data.get("result", data)
    if isinstance(result, list) and "next" in data:
        all_items = list(result)
        page_count = 0
        while "next" in data and page_count < MAX_PAGES:
            page_count += 1
            body["start"] = data["next"]
            resp = await _client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                return {"partial_results": all_items, "error": data["error"], "error_description": data.get("error_description", "")}
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
    result = await _call_b24("tasks.task.list", params)
    if isinstance(result, dict) and "tasks" in result:
        return result["tasks"]
    return result


@mcp.tool
async def b24_task_get(task_id: int) -> Any:
    """Get a task by ID."""
    result = await _call_b24("tasks.task.get", {"taskId": task_id})
    if isinstance(result, dict) and "task" in result:
        return result["task"]
    return result


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


# ── IM: Task chats and messages ──────────────────────────────


@mcp.tool
async def b24_im_recent(limit: int = 50) -> Any:
    """List recent IM chats for the webhook user. Returns chat_id, title and entity binding (e.g. TASKS_TASK/1177)."""
    result = await _call_b24("im.recent.get", {"LIMIT": limit})
    items = result.get("items", result) if isinstance(result, dict) else result
    if not isinstance(items, list):
        return result
    return [
        {
            "id": it.get("id"),
            "title": (it.get("chat") or {}).get("name") or it.get("title"),
            "entity_type": (it.get("chat") or {}).get("entity_type"),
            "entity_id": (it.get("chat") or {}).get("entity_id"),
        }
        for it in items
    ]


@mcp.tool
async def b24_task_chat_messages(task_id: int, limit: int = 100) -> Any:
    """Fetch messages from the IM chat attached to a task. Finds the chat via im.recent.get by ENTITY_TYPE=TASKS_TASK."""
    recent = await _call_b24("im.recent.get", {"LIMIT": 200})
    items = recent.get("items", recent) if isinstance(recent, dict) else recent
    chat_id = None
    if isinstance(items, list):
        for it in items:
            ch = it.get("chat") or {}
            if ch.get("entity_type") == "TASKS_TASK" and str(ch.get("entity_id")) == str(task_id):
                chat_id = it.get("id")
                break
    if not chat_id:
        return {"error": "chat_not_found", "task_id": task_id}
    msgs = await _call_b24("im.dialog.messages.get", {"DIALOG_ID": chat_id, "LIMIT": limit})
    messages = msgs.get("messages", []) if isinstance(msgs, dict) else []
    users_raw = msgs.get("users", []) if isinstance(msgs, dict) else []
    users = (
        {int(k): (v.get("name") if isinstance(v, dict) else v) for k, v in users_raw.items()}
        if isinstance(users_raw, dict)
        else {u["id"]: u.get("name", "?") for u in users_raw}
    )
    return {
        "chat_id": chat_id,
        "count": len(messages),
        "messages": [
            {
                "id": m.get("id"),
                "date": m.get("date"),
                "author_id": m.get("author_id"),
                "author": users.get(m.get("author_id"), "СИСТЕМА" if m.get("author_id") == 0 else None),
                "text": m.get("text"),
            }
            for m in messages
        ],
    }


@mcp.tool
async def b24_im_dialog_messages(dialog_id: str, limit: int = 100) -> Any:
    """Fetch messages from any IM dialog by DIALOG_ID (e.g. 'chat3005' or user id as string)."""
    return await _call_b24("im.dialog.messages.get", {"DIALOG_ID": dialog_id, "LIMIT": limit})


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
    """List events this webhook is currently subscribed to."""
    return await _call_b24("event.get")


@mcp.tool
async def b24_event_bind(event: str, handler: str) -> Any:
    """Subscribe to a Bitrix24 event. Provide event name (e.g. 'ONCRMLEADADD') and handler URL."""
    return await _call_b24("event.bind", {"event": event, "handler": handler})


@mcp.tool
async def b24_event_unbind(event: str, handler: str) -> Any:
    """Unsubscribe from a Bitrix24 event."""
    return await _call_b24("event.unbind", {"event": event, "handler": handler})


if __name__ == "__main__":
    mcp.run(transport="stdio")

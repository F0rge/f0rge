"""Run one catalogued API route in-process and translate its response for MCP."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from app.services.mcp_action_types import RouteCall

logger = logging.getLogger(__name__)

# A result lands in the caller's model context twice, as text and as structured content.
# 128 KB is about 32,000 tokens per copy, the most a model can usefully take from one call.
MAX_RESULT_BYTES = 128 * 1024
ROUTE_TIMEOUT_SECONDS = 30
_MAX_ERROR_CHARS = 2000
_MAX_RECEIPT_TEXT = 200
# Unreserved URL characters only: a value can never add a path segment, query or escape.
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_~-][A-Za-z0-9._~-]*\Z")

UNAVAILABLE = "This action is unavailable with your current access"
READ_FAILED = "Firstout could not complete this action. Try again later."
UNKNOWN_OUTCOME = (
    "Firstout could not confirm the outcome of this request. Look it up with "
    "operations_lookup. If it stays unknown, check the record in Firstout before "
    "retrying with a new request ID."
)


@dataclass(frozen=True)
class RouteOutcome:
    audit: Literal["success", "denied", "failed"]
    # None when the route gave no usable answer, so a write may or may not have happened.
    status: int | None = None
    # The route's JSON answer. None for a write whose answer is over the size limit.
    result: dict[str, Any] | None = None
    error: str | None = None
    # What a completed write saves for replays.
    receipt: dict[str, Any] | None = None


def no_answer(route: RouteCall) -> str:
    return READ_FAILED if route.method == "GET" else UNKNOWN_OUTCOME


def route_path(route: RouteCall, values: dict[str, Any]) -> str:
    """Fill the route's own path template with validated values."""
    path = route.path
    for name in route.path_params:
        segment = str(values[name])
        if not _SAFE_SEGMENT.fullmatch(segment):
            raise ValueError(name)
        path = path.replace("{" + name + "}", segment)
    return path


def _refusal(status: int, payload: Any) -> str:
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if status == 422 and isinstance(detail, list):
        # Include only schema locations and error codes, never input values.
        return "Invalid arguments: " + ", ".join(
            f"{'.'.join(str(part) for part in issue.get('loc', ()))} ({issue.get('type')})"
            for issue in detail[:5]
            if isinstance(issue, dict)
        )
    if isinstance(detail, dict) and isinstance(detail.get("message"), str) and detail["message"]:
        # A coded refusal ({"code", "message", ...}): the sentence is what a client can act on.
        detail = detail["message"]
    text = detail if isinstance(detail, str) else json.dumps(detail, separators=(",", ":"))
    if detail is None or len(text) > _MAX_ERROR_CHARS:
        return f"Firstout refused this request (HTTP {status})"
    return text


def receipt_fields(status: int, payload: Any) -> dict[str, Any]:
    """The HTTP status and the response's top-level identifiers, never names or contact details.

    Kept forever for replays, so only `id`, `status`, `number` and `*_id` / `*_number` scalars.
    """
    fields = {
        key: value
        for key, value in (payload.items() if isinstance(payload, dict) else ())
        if (key in ("id", "status", "number") or key.endswith(("_id", "_number")))
        # Tax and company registration numbers identify a party, not the record written.
        and key not in ("vat_number", "cipc_number")
        and (
            value is None
            or isinstance(value, (bool, int, float))
            or (isinstance(value, str) and len(value) <= _MAX_RECEIPT_TEXT)
        )
    }
    return {**fields, "http_status": status}


async def run_route(route: RouteCall, args: BaseModel, body: Any) -> RouteOutcome:
    """The caller sets the acting staff member and holds no database transaction."""
    values = args.model_dump(mode="json", exclude_unset=True, exclude={"body"})
    try:
        path = route_path(route, values)
    except ValueError as exc:
        return RouteOutcome("failed", 422, error=f"Invalid arguments: {exc} (unsafe_path_value)")
    query = {
        alias: values[name] for name, alias in route.query_params if values.get(name) is not None
    }
    try:
        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=route.app),
                base_url="http://firstout.mcp",
            ) as client,
            asyncio.timeout(ROUTE_TIMEOUT_SECONDS),
        ):
            # No Authorization or caller header is sent. The route trusts only the actor.
            response = await client.request(
                route.method, path, params=query, **({} if body is None else {"json": body})
            )
    except Exception:
        # Includes a timeout and an error the API does not handle. Never show the cause.
        logger.exception("MCP route %s %s did not answer", route.method, route.path)
        return RouteOutcome("failed", error=no_answer(route))
    status = response.status_code
    try:
        payload = response.json() if response.content else None
    except ValueError:
        payload = None
    if status >= 500:
        logger.error("MCP route %s %s answered %s", route.method, route.path, status)
        return RouteOutcome("failed", error=no_answer(route))
    if status in (401, 403):
        return RouteOutcome("denied", status, error=UNAVAILABLE)
    if status >= 300:
        return RouteOutcome("failed", status, error=_refusal(status, payload))
    fits = len(response.content) <= MAX_RESULT_BYTES
    if isinstance(payload, dict):
        result = payload
    else:
        # Tool results are objects, so a bare list or value is wrapped.
        wrapped = {"items" if isinstance(payload, list) else "value": payload}
        result = {} if payload is None else wrapped
    if route.method != "GET":
        # The change is made, so an answer over the limit is left out, never reported as failure.
        return RouteOutcome(
            "success", status, result if fits else None, receipt=receipt_fields(status, payload)
        )
    if not fits:
        return RouteOutcome(
            "failed",
            status,
            error=(
                f"This result is {len(response.content) // 1024} KB and the limit is "
                f"{MAX_RESULT_BYTES // 1024} KB. Narrow it with the action's filters or "
                "limit, or use the matching *_find action."
            ),
        )
    return RouteOutcome("success", status, result)

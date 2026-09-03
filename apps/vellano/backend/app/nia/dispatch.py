from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError as PydanticValidationError
from pydantic_ai import ApprovalRequired, RunContext
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError

from app.nia.actions import (
    action_allowed,
    hitl_body,
    missing_permission_message,
    redact_mapping,
)
from app.nia.agent import NiaDeps, nia_agent
from app.nia.catalog import CATALOG, CATALOG_BY_ID
from app.nia.fields import (
    FIELDS_ASSISTANT_TEXT,
    build_needs_fields_payload,
    should_emit_fields_form,
)
from app.schemas.location import LocationResponse
from app.schemas.user import UserResponse


# In-process services only — never HTTP-to-self against /api/v1 from this package.


def _serialize(value: Any) -> Any:
    if value is None:
        return {"ok": True}
    if isinstance(value, BaseModel):
        return redact_mapping(value.model_dump(mode="json"))
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, UserResponse) or isinstance(value, LocationResponse):
        return redact_mapping(value.model_dump(mode="json"))
    type_name = type(value).__name__
    if type_name in {"User", "Location"}:
        if type_name == "User":
            return redact_mapping(UserResponse.model_validate(value).model_dump(mode="json"))
        return LocationResponse.model_validate(value).model_dump(mode="json")
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return redact_mapping(value)
    return str(value)


def _format_pydantic_errors(exc: PydanticValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", ()))
        msg = err.get("msg", "invalid")
        if loc:
            parts.append(f"{loc}: {msg}")
        else:
            parts.append(str(msg))
    return "Missing or invalid fields: " + "; ".join(parts)


@nia_agent.tool
async def list_nia_actions(ctx: RunContext[NiaDeps]) -> list[dict[str, Any]]:
    """List catalogue actions this login may run. Call when unsure what you can do."""
    visible: list[dict[str, Any]] = []
    for action in CATALOG:
        if action_allowed(action, ctx.deps.permissions):
            visible.append({"id": action.id, "title": action.title, "write": action.write})
    return visible


@nia_agent.tool
async def run_nia_action(
    ctx: RunContext[NiaDeps],
    action_id: str,
    args: dict[str, Any],
) -> Any:
    """Run a catalogue action by id. Writes need approval. Pass args as a JSON object. When the user also asked for a chart or ranking, call the chart tool in the same turn before this write."""
    action = CATALOG_BY_ID.get(action_id)
    if action is None:
        return f"Unknown action: {action_id}"

    if not action_allowed(action, ctx.deps.permissions):
        return missing_permission_message(action, ctx.deps.permissions)

    try:
        data = action.args_model.model_validate(args or {})
    except PydanticValidationError as exc:
        if should_emit_fields_form(action):
            # Keep deps.canvas_spec — a chart published this turn must survive the fields card.
            ctx.deps.last_structured_payload = build_needs_fields_payload(
                action,
                args or {},
                exc,
            )
            return FIELDS_ASSISTANT_TEXT
        return _format_pydantic_errors(exc)

    if action.write and not ctx.tool_call_approved:
        raise ApprovalRequired(
            metadata={
                "kind": "needs_ok",
                "title": action.title,
                "body": hitl_body(action, data),
            }
        )

    try:
        result = await action.handler(ctx.deps, data)
    except (ValidationError, NotFoundError, ConflictError) as exc:
        detail = getattr(exc, "detail", None)
        return str(detail) if detail else str(exc)

    return _serialize(result)

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator, Optional

from ag_ui.core import RunAgentInput
from fastapi import Request
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.config import settings
from app.exceptions import NiaLlmUnconfiguredError
from app.models.nia import NiaMessageRole
from app.nia.agent import NiaDeps, build_nia_model, nia_agent
from app.services.nia_caps import check_nia_budget
from app.services.nia_threads import NiaThreadsService
from app.services.nia_usage import NiaUsageService
from app.services.permissions import PermissionService
from f0rge_core.exceptions import ValidationError


def _parse_optional_uuid(value: Any) -> Optional[uuid.UUID]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    text = str(value).strip()
    if not text:
        return None
    return uuid.UUID(text)


def _page_path_from_forwarded(forwarded_props: Any) -> str:
    if not isinstance(forwarded_props, dict):
        return ""
    page = forwarded_props.get("page")
    if not isinstance(page, dict):
        return ""
    path = page.get("path")
    return str(path) if path is not None else ""


def _entity_ids_from_forwarded(forwarded_props: Any) -> dict[str, Optional[uuid.UUID]]:
    if not isinstance(forwarded_props, dict):
        return {
            "invoice_id": None,
            "customer_id": None,
            "sku_id": None,
        }
    return {
        "invoice_id": _parse_optional_uuid(forwarded_props.get("invoice_id")),
        "customer_id": _parse_optional_uuid(forwarded_props.get("customer_id")),
        "sku_id": _parse_optional_uuid(forwarded_props.get("sku_id")),
    }


def _last_user_message_text(run_input: RunAgentInput) -> str:
    for message in reversed(run_input.messages):
        role = getattr(message, "role", None)
        if role != "user":
            continue
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                text = getattr(part, "text", None)
                if text:
                    parts.append(str(text))
            return "\n".join(parts)
    return ""


def build_run_input(body: bytes, thread_id: uuid.UUID) -> RunAgentInput:
    """Accept AG-UI RunAgentInput JSON or convenience ``{message, page?}``."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise ValidationError("Expected JSON object")

    if "threadId" not in payload and "message" in payload:
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValidationError("message is required")
        page = payload.get("page")
        forwarded_props: dict[str, Any] = {}
        if isinstance(page, dict):
            forwarded_props["page"] = page
        for key in ("invoice_id", "customer_id", "sku_id"):
            if key in payload:
                forwarded_props[key] = payload[key]
        return RunAgentInput(
            thread_id=str(thread_id),
            run_id=str(uuid.uuid4()),
            messages=[
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message.strip(),
                }
            ],
            tools=[],
            context=[],
            forwarded_props=forwarded_props,
        )

    if "threadId" not in payload:
        payload = {**payload, "threadId": str(thread_id)}
    return AGUIAdapter.build_run_input(json.dumps(payload).encode("utf-8"))


class NiaRunService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.threads = NiaThreadsService(db)
        self.usage = NiaUsageService(db)
        self.permissions = PermissionService(db)

    async def dispatch_run(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        request: Request,
    ) -> Response:
        await self.threads.get_thread(user_id, thread_id)

        body = await request.body()
        run_input = build_run_input(body, thread_id)

        if not settings.openrouter_api_key.strip():
            raise NiaLlmUnconfiguredError()

        await check_nia_budget(self.db, user_id)

        permission_keys = await self.permissions.keys_for_user(user_id)
        page_path = _page_path_from_forwarded(run_input.forwarded_props)
        entity_ids = _entity_ids_from_forwarded(run_input.forwarded_props)
        deps = NiaDeps(
            user_id=user_id,
            permissions=permission_keys,
            page_path=page_path,
            invoice_id=entity_ids["invoice_id"],
            customer_id=entity_ids["customer_id"],
            sku_id=entity_ids["sku_id"],
        )

        user_text = _last_user_message_text(run_input)
        model_name = settings.openrouter_model

        async def on_complete(result: Any) -> AsyncIterator[Any]:
            assistant_text = str(result.output)
            if user_text:
                await self.threads.append_message(
                    user_id,
                    thread_id,
                    NiaMessageRole.USER.value,
                    user_text,
                )
            if assistant_text:
                await self.threads.append_message(
                    user_id,
                    thread_id,
                    NiaMessageRole.ASSISTANT.value,
                    assistant_text,
                )
            usage = result.usage
            await self.usage.record_usage(
                user_id=user_id,
                thread_id=thread_id,
                model=model_name,
                prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            )
            if False:
                yield

        adapter = AGUIAdapter(nia_agent, run_input)
        return adapter.streaming_response(
            adapter.run_stream(
                deps=deps,
                model=build_nia_model(),
                on_complete=on_complete,
            )
        )

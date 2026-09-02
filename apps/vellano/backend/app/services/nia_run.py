from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator, Optional, Union

from ag_ui.core import RunAgentInput
from fastapi import Request
from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolDenied
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.exceptions import NiaLlmUnconfiguredError
import app.nia  # noqa: F401 — register Nia tools on the agent
from app.models.nia import NiaMessageRole
from app.nia.agent import NiaDeps, build_nia_model, nia_agent
from app.nia.hitl import (
    CANCELLED_ASSISTANT_TEXT,
    NEEDS_OK_ASSISTANT_TEXT,
    dump_agent_messages,
    load_agent_messages,
    pending_from_deferred,
)
from app.nia.tools import PROPOSE_TRANSFER_TOOL
from app.schemas.nia import NiaResumeRequest
from app.services.nia_audit import NiaAuditService, extract_tool_args
from app.services.nia_caps import check_nia_budget
from app.services.nia_threads import NiaThreadsService
from app.services.nia_usage import NiaUsageService
from app.services.permissions import PermissionService
from f0rge_core.exceptions import ConflictError, ValidationError


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


def _assistant_text_from_output(output: Any) -> str:
    if isinstance(output, DeferredToolRequests):
        return NEEDS_OK_ASSISTANT_TEXT
    return str(output)


class NiaRunService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.threads = NiaThreadsService(db)
        self.usage = NiaUsageService(db)
        self.permissions = PermissionService(db)
        self.audit = NiaAuditService(db)

    async def _build_deps(self, user_id: uuid.UUID, run_input: RunAgentInput) -> NiaDeps:
        permission_keys = await self.permissions.keys_for_user(user_id)
        page_path = _page_path_from_forwarded(run_input.forwarded_props)
        entity_ids = _entity_ids_from_forwarded(run_input.forwarded_props)
        return NiaDeps(
            user_id=user_id,
            permissions=permission_keys,
            page_path=page_path,
            db=self.db,
            invoice_id=entity_ids["invoice_id"],
            customer_id=entity_ids["customer_id"],
            sku_id=entity_ids["sku_id"],
        )

    async def _persist_run_result(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        user_text: str,
        result: Any,
        deps: NiaDeps,
    ) -> None:
        output = result.output
        assistant_text = _assistant_text_from_output(output)
        structured_payload: Optional[dict[str, Any]] = None
        pending_tools: Optional[dict[str, Any]] = None
        agent_messages = dump_agent_messages(result.all_messages())

        if isinstance(output, DeferredToolRequests):
            pending_tools = pending_from_deferred(output)
            structured_payload = pending_tools
        else:
            pending_tools = None
            if deps.last_structured_payload is not None:
                structured_payload = deps.last_structured_payload

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
                structured_payload=structured_payload,
            )
        await self.threads.save_agent_state(
            user_id,
            thread_id,
            agent_messages=agent_messages,
            pending_tools=pending_tools,
        )

    async def _record_usage(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        usage: Any,
    ) -> None:
        await self.usage.record_usage(
            user_id=user_id,
            thread_id=thread_id,
            model=settings.openrouter_model,
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )

    async def _persist_resume_result(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        result: Any,
        deps: NiaDeps,
    ) -> None:
        output = result.output
        assistant_text = _assistant_text_from_output(output)
        structured_payload: Optional[dict[str, Any]] = None
        pending_tools: Optional[dict[str, Any]] = None
        agent_messages = dump_agent_messages(result.all_messages())

        if isinstance(output, DeferredToolRequests):
            pending_tools = pending_from_deferred(output)
            structured_payload = pending_tools
        else:
            pending_tools = None
            if deps.last_structured_payload is not None:
                structured_payload = deps.last_structured_payload

        if assistant_text:
            await self.threads.append_message(
                user_id,
                thread_id,
                NiaMessageRole.ASSISTANT.value,
                assistant_text,
                structured_payload=structured_payload,
            )
        await self.threads.save_agent_state(
            user_id,
            thread_id,
            agent_messages=agent_messages,
            pending_tools=pending_tools,
        )

    async def _record_resume_audit(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        decision: str,
        pending: dict[str, Any],
        agent_messages: Optional[list[Any]],
        deps: NiaDeps,
    ) -> None:
        tool_name = str(pending.get("tool_name") or "unknown")
        tool_call_id = pending.get("tool_call_id")
        args = extract_tool_args(agent_messages, tool_call_id)

        if decision == "accept":
            payload = deps.last_structured_payload or {}
            if tool_name == PROPOSE_TRANSFER_TOOL and payload.get("kind") == "transfer_draft":
                transfer_id = _parse_optional_uuid(payload.get("transfer_id"))
                await self.audit.record(
                    user_id=user_id,
                    thread_id=thread_id,
                    tool_name=tool_name,
                    args=args,
                    decision="accept",
                    entity_type="transfer",
                    entity_id=transfer_id,
                )
            return

        await self.audit.record(
            user_id=user_id,
            thread_id=thread_id,
            tool_name=tool_name,
            args=args,
            decision=decision,
        )

    def _streaming_response(
        self,
        *,
        run_input: RunAgentInput,
        deps: NiaDeps,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        user_text: str,
        message_history: Optional[list] = None,
        deferred_tool_results: Optional[DeferredToolResults] = None,
        resume_decision: Optional[str] = None,
        pending_snapshot: Optional[dict[str, Any]] = None,
        agent_messages_snapshot: Optional[list[Any]] = None,
    ) -> Response:
        async def on_complete(result: Any) -> AsyncIterator[Any]:
            if message_history is None:
                await self._persist_run_result(
                    user_id=user_id,
                    thread_id=thread_id,
                    user_text=user_text,
                    result=result,
                    deps=deps,
                )
            else:
                await self._persist_resume_result(
                    user_id=user_id,
                    thread_id=thread_id,
                    result=result,
                    deps=deps,
                )
                if resume_decision and pending_snapshot:
                    await self._record_resume_audit(
                        user_id=user_id,
                        thread_id=thread_id,
                        decision=resume_decision,
                        pending=pending_snapshot,
                        agent_messages=agent_messages_snapshot,
                        deps=deps,
                    )
            await self._record_usage(
                user_id=user_id,
                thread_id=thread_id,
                usage=result.usage,
            )
            if False:
                yield

        adapter = AGUIAdapter(nia_agent, run_input)
        stream_kwargs: dict[str, Any] = {
            "deps": deps,
            "model": build_nia_model(),
            "on_complete": on_complete,
        }
        if message_history is not None:
            stream_kwargs["message_history"] = message_history
        if deferred_tool_results is not None:
            stream_kwargs["deferred_tool_results"] = deferred_tool_results
        return adapter.streaming_response(adapter.run_stream(**stream_kwargs))

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

        deps = await self._build_deps(user_id, run_input)
        user_text = _last_user_message_text(run_input)

        return self._streaming_response(
            run_input=run_input,
            deps=deps,
            user_id=user_id,
            thread_id=thread_id,
            user_text=user_text,
        )

    async def dispatch_resume(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        body: NiaResumeRequest,
    ) -> Union[Response, JSONResponse]:
        thread = await self.threads.get_owned_thread(user_id, thread_id)
        pending = thread.pending_tools
        if not pending:
            raise ConflictError("No pending approval")

        tool_call_id = body.tool_call_id or pending.get("tool_call_id")
        if not tool_call_id:
            raise ValidationError("tool_call_id is required")

        if body.decision == "cancel":
            await self.audit.record(
                user_id=user_id,
                thread_id=thread_id,
                tool_name=str(pending.get("tool_name") or "unknown"),
                args=extract_tool_args(thread.agent_messages, tool_call_id),
                decision="cancel",
            )
            await self.threads.clear_pending_tools(user_id, thread_id)
            await self.threads.append_message(
                user_id,
                thread_id,
                NiaMessageRole.ASSISTANT.value,
                CANCELLED_ASSISTANT_TEXT,
            )
            return JSONResponse(content={"ok": True})

        if not settings.openrouter_api_key.strip():
            raise NiaLlmUnconfiguredError()

        await check_nia_budget(self.db, user_id)

        deferred_results = DeferredToolResults()
        if body.decision == "accept":
            deferred_results.approvals[tool_call_id] = True
        else:
            deferred_results.approvals[tool_call_id] = ToolDenied("declined")

        run_input = RunAgentInput(
            thread_id=str(thread_id),
            run_id=str(uuid.uuid4()),
            messages=[],
            tools=[],
            context=[],
            forwarded_props={},
        )
        deps = await self._build_deps(user_id, run_input)
        message_history = load_agent_messages(thread.agent_messages)

        return self._streaming_response(
            run_input=run_input,
            deps=deps,
            user_id=user_id,
            thread_id=thread_id,
            user_text="",
            message_history=message_history,
            deferred_tool_results=deferred_results,
            resume_decision=body.decision,
            pending_snapshot=dict(pending),
            agent_messages_snapshot=thread.agent_messages,
        )

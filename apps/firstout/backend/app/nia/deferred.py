from __future__ import annotations

from app.nia.agent import nia_agent


@nia_agent.tool_plain(requires_approval=True)
def demo_echo_approval(text: str) -> str:
    """Echo text after the user approves. Demo HITL card only — no stock mutation."""
    return f"approved: {text}"

from __future__ import annotations

REASON_MISSING_PARTS = "missing_parts"
REASON_SPLIT_PICK = "split_pick"


def kit_pick_message(name: str, code: str, location_name: str, reason: str) -> str:
    """Plain-English till block. Names the kit and the showroom."""
    if reason == REASON_MISSING_PARTS:
        return (
            f"{name} ({code}) is a kit and some of its parts aren't in stock at "
            f"{location_name} or anywhere else. Receive the missing parts before "
            "this kit can be sold."
        )
    return (
        f"{name} ({code}) is a kit and some of its parts aren't in stock at "
        f"{location_name}. Create a pick so the warehouse knows where the parts "
        "come from, then complete the sale."
    )

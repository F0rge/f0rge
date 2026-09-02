"""Nia agent package (PydanticAI + AG-UI)."""

from app.nia import deferred as _deferred  # noqa: F401 — registers deferred tools
from app.nia import tools as _tools  # noqa: F401 — registers service tools

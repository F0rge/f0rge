# Agent Memory — fastapi-backend

- [Feature matrix column conventions](project_feature_matrix.md) — STATIC_COLUMNS ordering rules, derived column encoding, and null-row behaviour
- [Thin routers — non-negotiable](feedback_thin_routers.md) — FastAPI routers are 1-3 lines, no `if`/`raise`/logic; pre-existing violations don't excuse new ones
- [Obsidian renderer conventions](project_obsidian_conventions.md) — meal_time as (HH:MM) inline with embed; omit-when-zero for alcohol/caffeine in frontmatter + summary table
- [Photos router refactor — patterns and gotchas](project_photos_refactor.md) — monkeypatch targets after logic moves to service; test migration from router calls to service calls; DB-before-filesystem delete order

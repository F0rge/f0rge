> Canonical decisions: [`docs/adr/README.md`](../../adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

# Shared Libraries (`libs/`)

The Python and TypeScript libraries below are the current shared code. New shared plumbing is the small Rust set in the ADR index. Do not move app business rules into either place. The import ban (libs do not import apps) stays.

Genuinely generic code lives here. Apps import from libs — never the reverse.

## Inventory

| Lib | Import | Contents |
|-----|--------|----------|
| `libs/backend/core` | `f0rge_core` | `DomainError` tree, `register_exception_handlers(app)` |
| `libs/backend/db` | `f0rge_db` | Engine/session/get_db factories, auth context, tenant/RLS mechanism, `unit_of_work`, `BaseCRUD`, mixins (`UUIDPk`, `Timestamp`, `UserOwned`) |
| `libs/backend/storage` | `f0rge_storage` | `ObjectStorageConfig` + client, `resize_image` |
| `libs/backend/testing` | `f0rge_testing` | pgvector testcontainer fixture, savepoint-session fixture factories |
| `libs/ui` | `@f0rge/ui`, `@f0rge/ui/api`, `@f0rge/ui/forms` (when added) | 12 shadcn primitives, `cn`, date formatters, hooks, `fetch-error`, API client; Storybook catalogue in `libs/ui` |

Resolve library primaries and reviewers with `node scripts/agents/agents.mjs route <repo-relative-path...>`. The [manifest](../manifest.json) owns routing, including the shared test-harness exception; this table is an inventory. Follow the [shared protocol](../protocol.md).

**Deferred:** `f0rge-llm` — extract when a second LLM consumer exists. Parser duplication in `lab_extraction_prompt.py` / `vision_prompt.py` is known debt.

## Hard rules

1. **Libs never import app code** — no `from app.`, no `@/` paths that resolve to `apps/`. CI enforces: `! grep -rn "from ['\"].*apps/" libs/`.
2. **A lib change affects every consumer** — tag-driven CI (`platform:py` / `platform:ts`) runs lib + app tests when libs change.
3. **Never create a root `uv.lock`** — `@nxlv/python`'s UVProvider checks `fs.existsSync(<root>/uv.lock)` and silently flips to workspace mode. Always `uv --project <dir>`.
4. **Apps own domain code** — `Base` instance, `USER_OWNED_TABLES`, LLM prompts, domain schemas, brand tokens (`--marrow-*`), `CatalogItemCRUD`, `use-autosave-entry`.

## Python lib conventions

- `uv init --lib` src layout: `libs/backend/<name>/src/f0rge_<name>/`
- Own `pyproject.toml`, `uv.lock`, `project.json` with tags `["platform:py", "scope:shared"]`
- Ruff: marrow config + TID + `flake8-tidy-imports.banned-api` banning `"app"`
- Apps consume via `[tool.uv.sources]` editable path deps
- Each lib needs its own `project.json` (plugin has no createNodes)

## TypeScript lib conventions (`libs/ui`)

- Package name: `@f0rge/ui`
- Exports map pointing at `src/*.ts` (internal-package pattern, no build step)
- `react` / `react-dom` / `next` as peerDependencies
- Apps: `transpilePackages: ["@f0rge/ui"]`, `globals.css` `@source` for Tailwind 4 scanning
- **Semantic tokens only** in lib components (`var(--primary)`, `text-muted-foreground`) — never `--marrow-*` brand vars
- shadcn CLI additions land in `libs/ui`, never `apps/`
- New primitive → Storybook story required when `libs/ui/.storybook` exists (see `docs/agents/rules/ui-kit.md`)
- `libs/ui/src/styles/extras.css` is the only documented override file for kit-level CSS tweaks

## New project checklist

Every new lib or app project must have:

1. `project.json` with correct tags (see `docs/agents/rules/nx.md`):
   - Python lib: `["platform:py", "scope:shared"]`
   - TS lib: `["platform:ts", "scope:shared"]`
   - App backend: `["platform:py", "scope:<app>"]`
   - App frontend: `["platform:ts", "scope:<app>"]`
   - Exception: `marrow-ios` — `["scope:marrow"]` only (no `platform:`)
2. Nx targets: inferred lint/test preferred; Python needs `lint`, `test`, `format-check`
3. Without `platform:` tags, CI silently ignores the project (guard: `.github/scripts/check-nx-projects.sh`)
4. TS projects import `eslint/nx-boundaries.mjs` for `@nx/enforce-module-boundaries`

# Marrow MCP — Database Schema Overview

Reference for agents querying Leo's health tracker via MCP tools (`read_sql`, `search_health_data`, etc.).

## Tenancy and RLS

Every user-owned table has a `user_id` column (UUID FK to `users`). **Row Level Security (RLS)** is enabled with `FORCE ROW LEVEL SECURITY`. The `tenant_isolation` policy restricts rows to `user_id = current_setting('app.user_id')::uuid`.

MCP read paths set `app.user_id` from the Bearer token before each query. Cross-tenant reads are impossible under normal roles.

## Read-only MCP role (`healthtracker_ro`)

The MCP server uses a dedicated Postgres role **`healthtracker_ro`** for tool queries (configured via `MCP_READONLY_DATABASE_URL`). That role has `SELECT` only on user data tables and inherits the same RLS policies as the app role. Arbitrary `read_sql` runs under a **10s statement timeout**.

Write operations are not available through MCP.

## Core table groups

| Group | Tables | Notes |
| --- | --- | --- |
| Daily check-in | `entries` | One row per user per calendar date; symptoms in `symptoms_json` |
| Meals & photos | `meals`, `photos`, `photo_analyses`, `photo_ingredients` | Photos link to entries via `entry_id`; analysis is per `meal_id` |
| Labs | `labs`, `lab_markers`, `lab_marker_catalog`, `lab_marker_aliases` | Marker values reference per-user catalog rows |
| Treatments | `treatments`, `treatment_logs` | Supplements, medications, protocols |
| Catalogs | `dietary_ingredients`, `ingredient_aliases`, `symptom_catalog`, … | Per-user; seeded from reference user on signup |
| Embeddings | `embedding_queue`, `embeddings` | Async worker; see `marrow://meta/embedding-sources` |

## Stable MCP resource URIs

| URI | When to load |
| --- | --- |
| `marrow://schema/overview` | This document — start here for RLS and role context |
| `marrow://schema/entries` | Before interpreting entry columns, `symptoms_json`, or diet flags |
| `marrow://schema/photos` | Before joining photos to analyses or ingredients |
| `marrow://catalog/lab-markers` | Canonical lab marker names and units (reference catalog) |
| `marrow://catalog/dietary-ingredients` | User's ingredient catalog for histamine/FODMAP scoring |
| `marrow://meta/embedding-sources` | Which tables are embedded and chunk format for semantic search |

## Date and time conventions

- `entries.date` — `DATE`, one row per day
- `entries.entry_time`, `photos.meal_time` — `TIMESTAMP WITHOUT TIME ZONE` (naive UTC)
- Symptom severities in `symptoms_json` are integers keyed by catalog `key` (e.g. `"vss": 6`)

## Diet flags (entries)

`entries.diet_risk` is a legacy CSV of user-added flags. **Effective diet flags** for an entry combine photo-derived flags (`compute_photo_signal`) with user-added flags (`parse_diet_risk_csv`). Vocabulary: `high-histamine`, `high-fodmap`, `gluten`, `dairy`. Load `marrow://schema/entries` for column-level detail.

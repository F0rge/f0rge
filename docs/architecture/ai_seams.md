# AI seams — OpenRouter contracts

Source of truth for default models, embedding dimensions, and BYOK resolution in the Marrow backend.

## Default LLM

| Setting | Value |
| --- | --- |
| Config field | `settings.openrouter_model` in `apps/marrow/backend/app/config.py` |
| Default slug | `google/gemini-3-flash-preview` |
| Env var | `OPENROUTER_MODEL` (mirrored in `.env.example`) |

Do **not** use `google/gemini-2.0-flash` — OpenRouter rejects it. Preview-suffixed models may be deprecated without notice; verify on OpenRouter before changing the default.

## Default embedding model

| Setting | Value |
| --- | --- |
| Constant | `DEFAULT_EMBEDDING_MODEL` in `app/services/llm/factory.py` |
| Default slug | `openai/text-embedding-3-small` |
| Required dimension | `1024` (locked to `embedding.embedding VECTOR(1024)`) |

Every embedding request must pass `dimensions=1024`. The Postgres column is fixed at 1024 floats.

## BYOK resolution

All LLM and embedding call sites must use:

- `resolve_llm_credentials(db)` — returns `(api_key, model)` for vision/chat
- `resolve_embedding_credentials(db)` — returns `(api_key, model)` for embeddings

Resolution order (both):

1. User's encrypted `llm_api_key_encrypted` in `user_settings` (if set)
2. User's custom `llm_model` / `embedding_model` override (if set)
3. `OPENROUTER_API_KEY` env var
4. Default model slug from config/constants above

Never read `settings.openrouter_api_key` directly in service code.

## OpenRouter response shapes

### Embeddings

Access vectors via `response["data"][i]["embedding"]`. OpenRouter adds extra top-level keys (`provider`, `id`) compared to vanilla OpenAI — do not assert on the full key set.

### Chat / vision completions

Use the standard OpenAI-compatible completions endpoint. Model capability checks for lab extraction live in `app/services/lab_extraction_prompt.py`.

## Related files

- `app/services/llm/openrouter.py` — HTTP client
- `app/services/llm/factory.py` — credential resolution + client builders
- `app/services/food_analysis_orchestrator.py` — food photo vision
- `app/services/lab_extraction.py` — lab PDF/image extraction
- `app/embedding_pipeline/` — background embedding worker

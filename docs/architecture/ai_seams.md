# AI Seams

## Why this doc exists

This document is the single contract for every AI feature shipped in health-tracker. Any sub-agent implementing an LLM call, an embedding pipeline, a retrieval step, or a future notification/scheduling service must read this first. It defines the chosen defaults, the verified endpoint shapes, the abstract interfaces (ABCs), and the extensibility rules so that no future agent has to rediscover these facts from the code or re-verify them against OpenRouter.

---

## Default models

- **LLM**: `google/gemini-2.5-flash` via OpenRouter (configured in `user_settings.openrouter_model`; BYOK UI lets the user override per-session)
- **Embedding**: `openai/text-embedding-3-small` via OpenRouter with `dimensions=1024`
- **Vector dimension**: 1024 — locked into `embedding.embedding VECTOR(1024)`; changing this requires a destructive migration
- **Verified 2026-05-16**: curl to `POST https://openrouter.ai/api/v1/embeddings` with `{"model":"openai/text-embedding-3-small","input":"hello world","dimensions":1024}` returned `dim: 1024` and top-level keys `['object', 'data', 'model', 'usage', 'provider', 'id']`

---

## OpenRouter endpoint shapes

### Chat completions (already in use)

```
POST /api/v1/chat/completions
Authorization: Bearer <OPENROUTER_API_KEY>
Content-Type: application/json

Request body:
{
  "model": "<model_id>",
  "messages": [{"role": "user"|"assistant"|"system", "content": "..."}],
  "response_format": {"type": "json_object"},  // optional
  "temperature": 0.0,                           // optional
  "max_tokens": 8192                            // optional
}

Response (abbreviated):
{
  "choices": [{"message": {"content": "..."}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N},
  "model": "<model_id_echo>",
  "id": "<request_id>"
}
```

### Embeddings (new — verified 2026-05-16)

```
POST /api/v1/embeddings
Authorization: Bearer <OPENROUTER_API_KEY>
Content-Type: application/json

Request body:
{
  "model": "openai/text-embedding-3-small",
  "input": "<text>",          // str or list[str]
  "dimensions": 1024,         // Matryoshka truncation; required for non-default dim
  "encoding_format": "float"  // optional; default float
}

Response shape (top-level keys: object, data, model, usage, provider, id):
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [<1024 floats>],
      "index": 0
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {"prompt_tokens": N, "total_tokens": N},
  "provider": "OpenAI",     // NOTE: extra field vs vanilla OpenAI — safe to ignore
  "id": "<request_id>"      // NOTE: extra field vs vanilla OpenAI — safe to ignore
}
```

**Difference from vanilla OpenAI**: OpenRouter adds `provider` and `id` at the top level. The `data[0]` shape is identical. Do not assert on `len(response.keys()) == 4` — use explicit field access.

---

## `LLMClient` contract

Abstract base class. Location: `apps/marrow/backend/app/services/llm/base.py` (to be created by the backend agent).

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

class LLMClient(ABC):
    """Stateless chat-completion client."""

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, str] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> str:
        """Return the assistant message content as a string."""
        ...

    @abstractmethod
    def complete_with_image(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
    ) -> str:
        """
        Multimodal variant.  messages must contain at least one image_url content part.
        model overrides the default for callers that need a vision-capable model
        regardless of what the user has configured.
        """
        ...
```

Concrete implementation: `OpenRouterLLMClient` wraps the existing `food_analysis.py` call shape. The existing code path is not broken — it is absorbed into the concrete class.

---

## `EmbeddingClient` contract

Abstract base class. Location: `apps/marrow/backend/app/services/llm/base.py` (same file as `LLMClient`).

```python
class EmbeddingClient(ABC):
    """Stateless embedding client.  Returns vectors at the configured dimension."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single string.  Returns a list of floats of length == dim."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple strings in a single API call where the backend supports it.
        Returns a list of vectors in the same order as input.
        """
        ...
```

Concrete implementation: `OpenRouterEmbeddingClient` posts to `/api/v1/embeddings`, passes `dimensions=1024`, and extracts `response["data"][i]["embedding"]`. Access fields explicitly — do not destructure top-level key count.

---

## Polymorphic embedding table

The `embedding` table stores chunks from any source (daily logs, photos, food entries) via a loose foreign key pattern. No hard FK constraints — sources can be deleted without cascading.

```
embedding
  id                UUID primary key
  source_table      TEXT not null       -- e.g. "health_log", "food_photo", "symptom_entry"
  source_id         UUID not null       -- PK of the row in source_table
  chunk_index       INTEGER not null    -- 0-based position within the source document
  chunk_text        TEXT not null       -- the actual text that was embedded
  embedding         VECTOR(1024) not null
  embedding_model   TEXT not null       -- e.g. "openai/text-embedding-3-small"
  created_at        TIMESTAMPTZ default now()

UNIQUE (source_table, source_id, chunk_index, embedding_model)
INDEX  hnsw_cosine ON embedding USING hnsw (embedding vector_cosine_ops)
```

The `embedding_model` column is the discriminator that allows old and new model embeddings to coexist. When the user switches models, new chunks are stored under the new model name; old chunks remain valid until a re-embedding script is run (out of scope for this issue).

This table is created by the Phase 2.1 migration. **It is empty by design for this issue — no embedding population is performed.**

---

## Chunking strategy (future RAG concern, documented here)

Chunking is implemented by the backend agent when `RAGService` is built. The contract below is the spec for that implementation.

1. **Markdown-aware H2 split**: split the source document on `\n## ` boundaries first. Each H2 section becomes a candidate chunk.
2. **Overflow fallback**: if a section exceeds 800 tokens, apply a fixed-window split with 100-token overlap within that section.
3. **Token estimation**: use a `len(text) / 4` character heuristic. Do not pin to `tiktoken` in this contract — the implementing agent may choose the tokeniser. The heuristic is intentionally rough; 800-token target gives headroom.
4. **Overlap**: 100 tokens (by the same heuristic) carried forward from the end of chunk N into the start of chunk N+1, within the same H2 section only. No overlap across H2 boundaries.
5. **chunk_index**: sequential 0-based integer assigned after all splitting is complete for a given source document.

---

## Candidate models for the UI dropdown

The BYOK settings UI exposes two dropdowns. These lists are the authoritative defaults for the frontend and backend validation.

### LLM models

| Model ID | Label | Notes |
|---|---|---|
| `google/gemini-2.5-flash` | Gemini 2.5 Flash | Fast, cheap, multimodal — verified working on OpenRouter 2026-05-16 |
| `anthropic/claude-haiku-4-5` | Claude Haiku 4.5 | Good structured output |
| `anthropic/claude-sonnet-4-6` | Claude Sonnet 4.6 | Higher quality, slower |
| `openai/gpt-4o-mini` | GPT-4o Mini | Fallback for OpenAI users |
| *(free-form)* | Custom model | User-entered string; no validation |

### Embedding models

| Model ID | Dim | Label | Notes |
|---|---|---|---|
| `openai/text-embedding-3-small` | 1024 (Matryoshka) | text-embedding-3-small (default) | Verified via curl 2026-05-16 |
| `openai/text-embedding-3-large` | 1024 (Matryoshka) | text-embedding-3-large | Higher quality at same dim cost |
| `google/gemini-embedding-2-preview` | 1024 (flexible output) | Gemini Embedding 2 Preview | Multimodal — enables image embedding |
| `baai/bge-m3` | 1024 (native) | BGE-M3 | Cheapest option; no `dimensions` param needed |
| *(free-form)* | — | Custom embedding model | User-entered; backend assumes dim=1024 |

All embedding models in this list produce 1024-dimensional vectors. The schema never needs to change when switching between them — only `embedding_model` discriminates rows.

---

## Future `RAGService` retrieval contract

Not implemented in this issue. The interface below is the target for the agent that ships RAG.

```
RAGService.retrieve(
    question_text: str,
    top_k: int = 5,
    source_table: str | None = None,   // None = search all sources
) -> list[RetrievalResult]

RetrievalResult:
    chunk_text:          str
    source_table:        str
    source_id:           UUID
    distance:            float          // cosine distance; lower = more similar
    source_row_snapshot: dict           // the full source row at time of retrieval
```

Steps the implementation must follow:
1. Embed `question_text` via `EmbeddingClient.embed()`.
2. Run `SELECT ... ORDER BY embedding <=> query_vec LIMIT top_k` against the `embedding` table, optionally filtered by `source_table` and `embedding_model` matching the current user setting.
3. For each hit, fetch the source row from `source_table` by `source_id` and include it as `source_row_snapshot`.
4. Return results ordered by ascending distance.

---

## Future `NotificationDispatcher` contract

Not implemented in this issue. ABC only.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

@dataclass
class NotificationEvent:
    channel: Literal["email"]   // "telegram" and "in_app" are out of scope for now
    payload: dict
    priority: Literal["low", "normal", "high"] = "normal"

class NotificationDispatcher(ABC):
    @abstractmethod
    async def dispatch(self, event: NotificationEvent) -> None: ...
```

Channels not listed in the `Literal` type are explicitly out of scope for this issue.

---

## Future `SchedulerService` contract

Not implemented in this issue. ABC only.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import Callable

class SchedulerService(ABC):
    @abstractmethod
    def schedule(
        self,
        name: str,
        cron_expr: str,
        callable: Callable,
        idempotency_key: str,
    ) -> None:
        """
        Register a recurring job.
        idempotency_key prevents duplicate registrations across restarts.
        Concrete implementation will likely wrap APScheduler.
        """
        ...
```

---

## Multimodal upgrade path

When the user switches `user_settings.embedding_model` to `google/gemini-embedding-2-preview`:

1. No schema change required — dim=1024 is maintained via the model's flexible output parameter.
2. New chunks are stored with `embedding_model = "google/gemini-embedding-2-preview"`. Old chunks remain under `"openai/text-embedding-3-small"`.
3. `RAGService.retrieve()` should filter by the current user's active embedding model to avoid cross-model distance comparisons (vectors from different models are not comparable).
4. Re-embedding old chunks is a separate one-off script (out of scope); until then, old chunks are simply not retrieved when the model has changed.
5. Image embedding becomes possible: `gemini-embedding-2-preview` accepts image content parts, enabling retrieval over food photos. The `EmbeddingClient.embed()` contract would need a `content` overload at that point — tracked as a future ticket, not here.

---

## Future Cohere integration

Cohere's embedding models are not on OpenRouter (only Cohere's chat + rerank models are routed there). Adding Cohere requires a dedicated client.

- **File**: `apps/marrow/backend/app/services/llm/cohere.py`
- **Class**: `CohereEmbeddingClient(EmbeddingClient)`
- **Endpoint**: `POST https://api.cohere.com/v2/embed`
- **Model**: `cohere/embed-v4` supports Matryoshka at dim=1024 — drop-in compatible with the schema
- **Provider discriminator**: add `provider="cohere"` as a new value in `user_settings.embedding_provider`; the `EmbeddingClient` factory dispatches to `CohereEmbeddingClient` when provider is `"cohere"`
- **Secret**: `COHERE_API_KEY` env var (separate from `OPENROUTER_API_KEY`)

The ABC contract does not change. Only the factory and the concrete class are new.

---

## Non-goals (for this issue)

- No `RAGService` implementation — table is empty by design
- No `NotificationDispatcher` or `SchedulerService` implementations — ABCs only
- No embedding population — the `embedding` table ships empty
- No chat UI or retrieval UI
- No Cohere client — tracked as a future ticket
- No re-embedding script for model migrations

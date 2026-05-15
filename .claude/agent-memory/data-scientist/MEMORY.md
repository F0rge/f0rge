# Data Scientist Memory

## Vision Model

- **Model**: `google/gemini-3-flash-preview` via OpenRouter
- **Provider**: OpenRouter (EU servers, cache-friendly)
- **Cost**: ~$0.50/month at 10 photos/day, ~5x cheaper than Claude Sonnet
- **Latency**: 3-8s end-to-end for photo upload → analysis complete

## Pipeline

1. Photo upload → FastAPI BackgroundTask → `trigger_analysis_background(photo_id)`
2. `food_analysis.py` reads photo bytes, calls OpenRouter with structured prompt from `vision_prompt.py`
3. Response parsed via `parse_vision_response` (handles direct JSON, code blocks, brace extraction, fallback)
4. Each ingredient looked up via `IngredientLookupService` against dietary reference DB
5. Status flips through pending → analyzing → complete (or failed)
6. Frontend polls `/photos/{id}/analysis` every 2s while non-terminal

## Vision response schema (Pydantic models in `vision_prompt.py`)

```python
class VisionIngredient(BaseModel):
    name: str
    visible: bool = True
    confidence: float

class VisionResult(BaseModel):
    dish_name: str
    cuisine: Optional[str] = None
    confidence: float
    ingredients: list[VisionIngredient]
```

## Prompting strategy

- Image-before-text ordering
- Chain-of-thought: identify dish → list visible ingredients → infer hidden ingredients from common recipes
- Normalized ingredient names (lowercase, singular)
- Confidence scores per ingredient, mark `visible=false` for inferred items
- Fallback for non-food images: `dish_name="unknown"`, `confidence=0`, empty ingredients

## Dietary tag sources

| Tag | Source | Format |
|-----|--------|--------|
| Histamine (0-3 SIGHI score) | `data/sighi_histamine.json` | Curated JSON |
| FODMAP (oligos/fructose/polyols/lactose, low/moderate/high) | `data/fodmap_list.json` | Monash-derived |
| Gluten / Dairy (boolean flags) | `data/allergens.json` | Curated JSON |

## Known challenges

- Mixed dishes (curries, stews) — ingredients hidden, accuracy drops
- Sauces / marinades invisible to vision models
- Cultural specificity: non-Western cuisines have lower benchmark accuracy
- LLMs hallucinate ingredients — confidence thresholds needed
- No single API covers all four dietary categories → merged local lookup table

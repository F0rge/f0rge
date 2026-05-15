# Data Scientist Memory

## Vision Model Decision

- **Model**: Gemini 3 Flash via OpenRouter
- **Why**: ~5x cheaper than Claude Sonnet ($0.50/$3 per MTok vs $3/$15), strong vision, good structured output
- **Provider**: OpenRouter (EU trusted servers, good cache hit rate requested)
- **Cost estimate**: ~$0.50/month at 10 photos/day

## Image Analysis Pipeline Design

- **Flow**: Photo upload -> background analysis -> results appear in UI -> user reviews/edits -> save
- **Timing**: Async/background (not blocking upload)
- **User review**: Show parsed ingredients + tags, editable before confirm; auto-confirm on check-in submit if not reviewed
- **Output schema target**:
  ```json
  {
    "dish_name": "string",
    "cuisine": "string | null",
    "confidence": 0.0-1.0,
    "ingredients": [
      {"name": "normalized name", "visible": true/false, "confidence": 0.0-1.0}
    ]
  }
  ```

## Dietary Tag Sources

| Tag | Source | Format | Coverage |
|-----|--------|--------|----------|
| Histamine (0-3) | SIGHI list | PDF -> ETL needed | ~500 foods |
| FODMAP (oligos/fructose/polyols/lactose) | fodmap_list GitHub JSON | Ready to use | Community-curated |
| Gluten | Open Food Facts allergens | REST API | 4M+ products |
| Dairy | Open Food Facts allergens | REST API | 4M+ products |

## Prompting Strategy

- Image-before-text ordering
- Chain-of-thought: identify dish -> list visible ingredients -> infer hidden ingredients
- Structured JSON output via schema definition
- Confidence scores per ingredient
- Flag uncertainty rather than hallucinate

## Known Challenges

- Mixed dishes (curries, stews) — ingredients hidden, accuracy drops
- Sauces/marinades invisible to vision models
- Non-Western cuisines have lower benchmark accuracy
- LLMs hallucinate ingredients — confidence thresholds needed
- No single API covers all four dietary categories — need merged lookup table

## Obsidian Output Requirements

- Both frontmatter tags (for Dataview queries) AND inline details under each photo
- Frontmatter: histamine_risk, fodmap_risk, contains_gluten, contains_dairy
- Inline: ingredient list with dietary flags per photo

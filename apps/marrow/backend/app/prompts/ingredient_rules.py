"""Shared ingredient-logging rules for Marrow's LLM-facing surfaces.

This module is deliberately **import-free** (only ``from __future__ import
annotations``): it holds plain string constants so that any consumer can load it
without pulling in SQLAlchemy, pydantic or the rest of ``app``.

Today it is used only by the public MCP server (server ``instructions``, tool
descriptions, the ``marrow://reference/meal-logging-guide`` resource and the
``log_meal_guide`` prompt). It is **intended to be shared later** with the photo
classifier prompt (``app/services/vision_prompt.py``) and the Airflow DAG
(``dags/classify_meal.py``, which could load this file by path). Neither is wired
up yet and their behaviour is unchanged.

Constraint for that future sharing: the DAG passes its prompt through a Jinja
XCom template string, so none of the text below may contain ``{{`` or ``{%``.
"""

from __future__ import annotations

INGREDIENT_NAMING_RULES = """\
- Use lowercase, singular, common English names: "tomato" not "Tomatoes", "egg" not "eggs", \
"cilantro" not "coriander leaf". Exception: when the user's catalogue uses a plural canonical \
name (for example "oats", "almonds"), use the catalogue spelling exactly.
- An ingredient name is only the ingredient. Never put a brand, pack size, quantity, weight, \
preparation note or dish name in it ("auchan ... muesli (40 g)" is wrong). Brand, pack size and \
quantity belong in the meal name.
- Never send empty or null names."""

COMPOSITE_PRODUCT_RULES = """\
- Log a meal as its constituent ingredients, never as one product or dish string.
- Split packaged and composite foods (muesli, granola, cereal bars, bread, biscuits, sauces, \
soups, sausages, ready meals) into their main ingredients. Use the ingredient list on the pack \
or photo when you have it; otherwise use the typical composition.
- Include minor ingredients that matter for gluten, dairy, FODMAP or histamine (wheat, milk \
powder, onion or garlic powder, honey, dried fruit, vinegar). Skip colours, emulsifiers and \
trace additives.
- Example: "gluten-free crunchy dried fruit muesli" becomes oats, sunflower oil, raisin, dried \
apricot, sugar, almonds, hazelnuts - only the ones actually listed.
- For products labelled gluten-free or lactose-free, do not list the gluten- or lactose-bearing \
ingredient they replace ("rice flour" or "corn flour", not "wheat flour")."""

CATALOG_MATCHING_RULES = """\
- The user keeps their own ingredient catalogue (canonical names, aliases, FODMAP, histamine, \
gluten and dairy flags). Look names up with the search_ingredients tool (one call per \
ingredient) or read the resource marrow://catalog/dietary-ingredients before choosing names.
- When a catalogue entry fits, send its exact canonical_name. Aliases only help you recognise \
the entry - never send an alias as the ingredient name.
- Only exact, alias and normalised matches count as the same ingredient. Close matches are \
returned as suggestions and stored without flags until you resend the exact canonical_name.
- If nothing fits, use a plain lowercase common name. It will be stored without catalogue \
flags, and it is never added to the catalogue automatically."""

EVIDENCE_RULES = """\
- Only list ingredients you can see, that the pack or recipe states, or that the user told you.
- Do not invent ingredients when you are unsure. Leave them out or ask the user.
- Tell the user which ingredients you inferred (typical recipe) versus read from the pack, \
photo or their words, so they can correct you. The tools store names only and treat every \
ingredient you send as confirmed."""

MEAL_LOGGING_GUIDE = f"""\
# Logging meals with ingredients

Marrow turns a meal's ingredient list into FODMAP, histamine, gluten and dairy flags by \
matching each ingredient name against the user's own catalogue. Good names give good flags; a \
product string such as "auchan muesli (40 g)" matches nothing and produces no flags.

## Workflow
1. Put the brand, product, pack size and quantity in the meal `name` (for example "Auchan \
gluten-free crunchy dried fruit muesli, 40 g").
2. Decompose the meal into ingredients (composite-product rules below).
3. Call `search_ingredients` for each ingredient (or read \
`marrow://catalog/dietary-ingredients`) and pick exact canonical names.
4. Call `log_meal` (new meal) or `set_ingredients` (replace the list on an existing meal) with \
those names.
5. Read the per-ingredient `match.status` in the result: `exact`, `alias` and `normalised` carry \
catalogue flags; `approximate` and `unmatched` are stored without flags, so follow `next_step` \
(resend with a suggested canonical_name, or decompose) and call `set_ingredients` again.

## Naming rules
{INGREDIENT_NAMING_RULES}

## Composite products
{COMPOSITE_PRODUCT_RULES}

## Matching the catalogue
{CATALOG_MATCHING_RULES}

## Evidence
{EVIDENCE_RULES}

## Example
Meal name: "Auchan gluten-free crunchy dried fruit muesli, 40 g"
Ingredients: ["oats", "sunflower oil", "raisin", "dried apricot", "sugar", "almonds", "hazelnuts"]
"""

INGREDIENT_TOOL_NOTE = (
    "Pass `ingredients` as the decomposed list of constituent ingredients, not a product or dish "
    "string: split packaged/composite foods (muesli, bread, ready meals) using the pack's "
    "ingredient list or photo. Put brand, pack size and quantity in the meal name, never in "
    "ingredient names. Use lowercase singular common English names and, when the user's catalogue "
    "has a fitting entry, its exact canonical_name: call search_ingredients first (or read resource "
    "marrow://catalog/dietary-ingredients). The result reports each ingredient's match status "
    "(exact, alias, normalised, approximate, unmatched) and a next_step; only exact, alias and "
    "normalised matches get catalogue flags, the rest are stored without "
    "FODMAP/histamine/gluten/dairy flags and are never added to the catalogue. Do not invent "
    "ingredients when unsure."
)

MCP_SERVER_INSTRUCTIONS = f"""\
Marrow is the user's personal health tracker: daily check-ins, meals, labs, treatments and \
hypotheses. Tools act on the authenticated user's own data only.

When logging a meal (log_meal, set_ingredients):
{COMPOSITE_PRODUCT_RULES}
{INGREDIENT_NAMING_RULES}
{CATALOG_MATCHING_RULES}
{EVIDENCE_RULES}

Full guide: resource marrow://reference/meal-logging-guide (or the log_meal_guide prompt). \
Day structure: resource marrow://reference/check-in-day-map."""

__all__ = [
    "CATALOG_MATCHING_RULES",
    "COMPOSITE_PRODUCT_RULES",
    "EVIDENCE_RULES",
    "INGREDIENT_NAMING_RULES",
    "INGREDIENT_TOOL_NOTE",
    "MCP_SERVER_INSTRUCTIONS",
    "MEAL_LOGGING_GUIDE",
]

# Ingredient lookup audit — review

333 ingredients audited across 8 parallel agents. The agents cross-checked our `backend/data/{sighi_histamine,fodmap_list,allergens}.json` against authoritative primary sources (SIGHI Food Compatibility List PDF for histamine, Monash University FODMAP App for FODMAP, ingredient composition for gluten/dairy).

**Totals:** 220 keep • 93 modify • 20 drop (compound dishes) • 5 additions proposed
**Confidence:** 254 high • 72 medium • 7 low

**Legend:**
- SIGHI col: `score (category)`. Score 0=no concern, 1=slight, 2=significant, 3=strict avoid
- FODMAP col: `O:H F:M P:L L:L` (Oligos/Fructose/Polyols/Lactose × High/Moderate/Low)
- Allergens col: `Gluten`, `Dairy`, `Gluten+Dairy`, `none`
- Confidence: ● high · ◐ medium · ○ low (low-confidence rows: scrutinize before approving)

**How to review:** Skim the **modify** and **drop** sections first — those are the proposed changes. Use the section headers to jump. Reply with rejects/edits by ingredient name.

## A. Proposed modifications (93)

| Ingredient | Conf | Current SIGHI / FODMAP / Allergens | Proposed SIGHI / FODMAP / Allergens | Rationale |
|---|---|---|---|---|
| **almond butter** | ● | — / — / none | — / O:L F:L P:L L:L / none | fodmap: ADDED. Monash classifies almond butter as low FODMAP up to 1 tbsp / 20 g. [2 src] |
| **almond milk** | ● | — / — / none | — / O:L F:L P:L L:L / none | fodmap: ADDED. Monash: almond milk is low FODMAP at 1 cup (240 ml); commercial almond milk is only ~2% almonds. [2 src] |
| **almonds** | ● | 0 (nuts_seeds) / O:L F:L P:L L:L / none | 1 (nuts_seeds) / O:H F:L P:L L:L / none | sighi.score: 0 -> 1. SIGHI explicitly lists 'almond' = 1 with note 'Small amounts are well tolerated. May cause e.g. sleep problems.' · fodmap.oligos: low -> high. Monash: 10 almonds (12 g) is low FODMAP; 20 almonds is high in GOS (oligos). Default serving is high-FODMAP for o… [2 src] |
| **anchovies** | ● | 3 (fish) / — / — | 3 (fish) / — / none | allergens: ADDED. Plain anchovies are gluten-free and dairy-free. [1 src] |
| **apple cider vinegar** | ● | 3 (condiments) / — / — | 1 (condiments) / O:L F:L P:L L:L / — | sighi.score: 3 -> 1. SIGHI explicitly lists 'vinegar: apple vinegar' = 1 (H, ?) with note 'Check for additives'. · fodmap: ADDED. Monash: apple cider vinegar is low FODMAP at 2 tbsp (30 ml) per sitting; double-fermentation reduces sugars. [2 src] |
| **apple juice** | ● | 0 (beverages) / — / — | — / O:L F:H P:H L:L / — | sighi: REMOVED. SIGHI does not have a specific entry for apple juice; only generic 'fruit nectars' and cranberry/orange juice. Score of 0 was inferred from whole apple. Dropping to null per 'conservative on uncertainty' rule. · fodmap: ADDED. Monash: reconstituted apple juice … [2 src] |
| **apricot** | ● | 0 (fruit) / O:L F:L P:H L:L / — | 0 (fruit) / O:L F:L P:H L:L / none | allergens: ADDED. Fresh apricot is gluten-free and dairy-free. [1 src] |
| **artichoke** | ● | 0 (vegetables) / O:H F:H P:L L:L / — | 0 (vegetables) / O:H F:H P:L L:L / none | allergens: ADDED. Artichoke is gluten-free and dairy-free. [2 src] |
| **asparagus** | ● | 0 (vegetables) / O:H F:M P:L L:L / — | 0 (vegetables) / O:H F:M P:L L:L / none | allergens: ADDED. Asparagus is gluten-free and dairy-free. [1 src] |
| **avocado oil** | ● | 0 (oils_fats) / — / — | 0 (oils_fats) / O:L F:L P:L L:L / none | fodmap: ADDED. Pure oils contain no carbohydrates and are FODMAP-free per Monash. · allergens: ADDED. Pure avocado oil is gluten-free and dairy-free. [2 src] |
| **bacon** | ● | 2 (meat) / — / — | 3 (meat) / O:L F:L P:L L:L / none | sighi.score: 2 -> 3. Bacon is cured/smoked pork — SIGHI rates 'smoked meat (any)' and 'dry-cured ham' at 3. Bacon belongs in this group. · fodmap: ADDED. Monash: plain bacon (without high-FODMAP marinades) is low FODMAP. · allergens: ADDED. Plain bacon is gluten- and dairy-free. [2 src] |
| **balsamic vinegar** | ● | 3 (condiments) / — / — | 3 (condiments) / O:L F:L P:L L:L / none | fodmap: ADDED. Monash: balsamic vinegar is low FODMAP up to 1 tbsp (21 g) per meal. · allergens: ADDED. Balsamic vinegar is gluten- and dairy-free. [2 src] |
| **banana** | ● | 0 (fruit) / O:L F:L P:L L:L / none | 2 (fruit) / O:L F:L P:L L:L / none | sighi.score: 0 -> 2. SIGHI lists 'banana' = 2 (A — other biogenic amines) with note '(The greener the better tolerated?)'. [2 src] |
| **banana, ripe** | ● | — / O:L F:M P:L L:L / — | 2 (fruit) / O:M F:L P:L L:L / none | fodmap.oligos: low -> moderate; fodmap.fructose: moderate -> low. Monash: ripe banana (37 g = 1/3) is low FODMAP; up to 1 medium (~100 g) is moderate for fructans (oligos), NOT fructose. Previous mapping had wrong axis. · sighi: ADDED at score 2 (parity with plain 'banana'). ·… [2 src] |
| **barley** | ● | 0 (grains) / O:H F:L P:L L:L / Gluten | 1 (grains) / O:H F:L P:L L:L / Gluten | sighi.score: 0 -> 1. SIGHI lists 'barley' = 1. [1 src] |
| **basil** | ● | 0 (spices) / — / — | 0 (spices) / O:L F:L P:L L:L / none | fodmap: ADDED. Monash: basil is low FODMAP. · allergens: ADDED. [2 src] |
| **bay leaf** | ◐ | 0 (spices) / — / — | 0 (spices) / O:L F:L P:L L:L / none | fodmap: ADDED. Monash lists bay leaf as low FODMAP. · allergens: ADDED. [2 src] |
| **beer** | ● | 3 (beverages) / — / Gluten | 2 (beverages) / O:L F:L P:L L:L / Gluten | sighi.score: 3 -> 2. SIGHI lists 'beer' = 2 (H, A, L, B) — all four mechanisms but score is 2 not 3. · fodmap: ADDED. Monash: beer is low FODMAP at 12 oz (~350 ml) / one bottle. [2 src] |
| **black pepper** | ● | 0 (spices) / — / none | 0 (spices) / O:L F:L P:L L:L / none | fodmap: ADDED. Monash: black pepper is low FODMAP at typical culinary amounts. [1 src] |
| **black tea** | ● | 1 (beverages) / O:L F:L P:L L:L / — | 2 (beverages) / O:L F:L P:L L:L / none | sighi.score: 1 -> 2. SIGHI lists 'tea, black tea' = 2 (H, B — blocker of DAO). · allergens: ADDED. [2 src] |
| **blue cheese** | ● | 3 (dairy) / — / Dairy | 2 (dairy) / O:L F:L P:L L:L / Dairy | sighi.score: 3 -> 2. SIGHI lists 'blue cheeses, mold cheeses' = 2 (H, A, ?). Roquefort/Rochefort/cheddar/Raclette all = 2 on SIGHI. · fodmap: ADDED. Monash: blue cheese is low FODMAP at standard serves (fructans not detected until 195 g). [2 src] |
| **brazil nuts** | ● | 0 (nuts_seeds) / — / — | 0 (nuts_seeds) / O:L F:L P:L L:L / none | fodmap: ADDED. Monash: Brazil nuts are low FODMAP at 30 g (10 nuts); moderate GOS at 44 g. · allergens: ADDED. [2 src] |
| **bread** | ● | 0 (grains) / O:H F:L P:L L:L / Gluten | — / — / — | Compound dish — DROP per user direction. 'Bread' is too ambiguous: white wheat, whole wheat, sourdough, rye, gluten-free, etc. all have very different FODMAP and histamine profiles. SIGHI explicitly notes that bread = 1 (?) only with the caveat 'problematic ingredients: malt, … [2 src] |
| **broccoli** | ● | 0 (vegetables) / O:L F:L P:L L:L / none | 1 (vegetables) / O:L F:L P:L L:L / none | sighi: 0 -> 1. Official SIGHI list rates broccoli as 1 (slightly raised / eat sparingly). Multiple secondary sources confirm 1. · fodmap: kept low across all categories (Monash confirms broccoli florets low at 75 g). [3 src] |
| **brussels sprouts** | ● | 0 (vegetables) / O:H F:L P:M L:L / — | 1 (vegetables) / O:H F:L P:M L:L / none | sighi: 0 -> 1. SIGHI scores Brussels sprouts 1 with histamine-liberator caveat. · allergens: added explicit false/false (was missing). [2 src] |
| **bulgur** | ● | — / — / Gluten | 1 (grains) / O:H F:L P:L L:L / Gluten | sighi: ADDED. Bulgur is parboiled wheat; aligns with SIGHI wheat score of 1. · fodmap: ADDED. Bulgur is wheat-derived; high in fructans (oligos), low at very small (~1/4 cup) servings, high at standard portions. [3 src] |
| **buttermilk** | ● | — / — / Dairy | 2 (dairy) / O:L F:L P:L L:H / Dairy | sighi: ADDED at 2. Buttermilk is lactic-acid fermented; SIGHI restricts it (score 2). · fodmap: ADDED. Lactose-high per Monash dairy guidance (fermented milk product, contains residual lactose). [2 src] |
| **cashews** | ● | 0 (nuts_seeds) / O:H F:L P:L L:L / — | 1 (nuts_seeds) / O:H F:L P:L L:L / none | sighi: 0 -> 1. SIGHI rates cashew nut as 1 with a histamine-liberator flag. · allergens: added explicit false/false (was missing). [2 src] |
| **cauliflower** | ● | 0 (vegetables) / O:M F:L P:M L:L / — | 0 (vegetables) / O:L F:L P:H L:L / none | fodmap.polyols: moderate -> high. Cauliflower is widely listed as high mannitol (polyol). · fodmap.oligos: moderate -> low. Per Monash 2025 retest, cauliflower's primary FODMAP is mannitol, not fructan/GOS. · allergens: added explicit false/false (was missing). [2 src] |
| **cayenne pepper** | ◐ | 1 (spices) / — / — | 2 (spices) / O:L F:L P:L L:L / none | sighi: 1 -> 2. SIGHI lists hot peppers / cayenne as restricted due to capsaicin acting as a histamine releaser. · fodmap: ADDED. Monash: dried cayenne low FODMAP at 1 tsp (2 g). · allergens: added explicit false/false. [2 src] |
| **chickpeas** | ◐ | 1 (legumes) / O:H F:L P:L L:L / none | 0 (legumes) / O:H F:L P:L L:L / none | sighi: 1 -> 0. SIGHI itself rates chickpeas (Kichererbsen) 0; this is one of the few legumes treated as compatible. Some secondary sources disagree (because legumes generally are a 2), but the SIGHI primary entry is 0. [2 src] |
| **chili flakes** | ◐ | 1 (spices) / — / — | 2 (spices) / O:L F:L P:L L:L / none | sighi: 1 -> 2. Dried hot chili / chili flakes are in SIGHI's restricted (2) category alongside cayenne and hot paprika. · fodmap: ADDED low across all (consistent with Monash dried chili at 1 tsp). · allergens: added explicit false/false. [2 src] |
| **chili pepper** | ◐ | — / O:L F:L P:L L:L / — | 2 (spices) / O:L F:L P:L L:L / none | sighi: ADDED at 2. Fresh hot chili is SIGHI-restricted (capsaicin = histamine releaser). · allergens: added explicit false/false. [2 src] |
| **chili powder** | ◐ | 1 (spices) / — / — | 2 (spices) / O:L F:L P:L L:L / none | sighi: 1 -> 2. Same logic as chili flakes / cayenne — SIGHI's restricted band for hot dried peppers. · fodmap: ADDED low. Note: COMMERCIAL chili powder blends often contain onion/garlic powder which would be high oligos; this entry assumes pure dried chili. · allergens: added … [2 src] |
| **cinnamon** | ◐ | 1 (spices) / — / — | 0 (spices) / O:L F:L P:L L:L / none | sighi: 1 -> 0. Multiple SIGHI references give cinnamon 0; some secondary sites flag it as a mild liberator but the primary list is 0. · fodmap: ADDED low (Monash: 1 tsp powder low FODMAP). · allergens: added explicit false/false. [2 src] |
| **cloves** | ● | 1 (spices) / — / — | 0 (spices) / O:L F:L P:L L:L / none | sighi: 1 -> 0. SIGHI rates cloves 0 (small amounts well-tolerated; lack of experience for large quantities). · fodmap: ADDED low (Monash-tested low FODMAP at typical spice amounts). · allergens: added explicit false/false. [2 src] |
| **crab** | ● | 1 (seafood) / — / — | 2 (seafood) / — / — | sighi: 1 -> 2 (SIGHI explicitly lists shellfish incl. crab at score 2 L; histamine liberator) [1 src] |
| **dark chocolate** | ● | 3 (sweets) / O:L F:L P:L L:L / — | 2 (sweets) / O:L F:L P:L L:L / — | sighi: 3 -> 2 (SIGHI line 512: Chocolate brown/black = 2 A; cocoa powder = 2 AL) [1 src] |
| **date** | ● | 1 (fruit) / O:L F:H P:L L:L / — | 0 (fruit) / O:L F:H P:L L:L / — | sighi: 1 -> 0 (SIGHI line 238: Dates dried/desiccated = 0) [1 src] |
| **dill** | ● | 0 (spices) / — / — | 1 (spices) / O:L F:L P:L L:L / — | sighi: 0 -> 1 (SIGHI line 213: Dill = 1) · fodmap: ADD all-low (fresh herbs are low FODMAP) [2 src] |
| **dried fig** | ● | 2 (fruit) / O:L F:H P:L L:L / — | 1 (fruit) / O:H F:H P:L L:L / — | sighi: 2 -> 1 (SIGHI line 239: Figs dried/desiccated = 1) · fodmap: oligos low -> high (Monash: dried figs high in fructans) [2 src] |
| **edamame** | ◐ | 1 (legumes) / — / — | — / O:L F:L P:L L:L / — | sighi: DROP (1 -> null; SIGHI does not enumerate edamame; SIGHI lists mature soy at 2 and tofu at 2, but young soybean evidence is weak) · fodmap: ADD all-low (Monash: 75g shelled edamame low FODMAP — unlike mature soybeans) [2 src] |
| **egg white** | ● | 0 (eggs) / — / — | 2 (eggs) / O:L F:L P:L L:L / none | sighi: 0 -> 2 (SIGHI line 32: Egg white = 2 L — histamine liberator) · fodmap: ADD all-low · allergens: ADD gluten=false, dairy=false [1 src] |
| **emmental cheese** | ● | 2 (dairy) / — / Dairy | 3 (dairy) / O:L F:L P:L L:L / Dairy | sighi: 2 -> 3 (SIGHI line 47: hard cheese / long-matured incl. Emmentaler explicitly = 3 HA) · fodmap: ADD all-low (Monash: hard cheeses very low in lactose, low FODMAP) [2 src] |
| **garlic** | ● | 0 (vegetables) / O:H F:L P:L L:L / — | 1 (vegetables) / O:H F:L P:L L:L / — | sighi: 0 -> 1 (SIGHI line 173: Garlic = 1) [1 src] |
| **garlic powder** | ◐ | 0 (spices) / — / — | 1 (spices) / O:H F:L P:L L:L / — | sighi: 0 -> 1 (extrapolated from fresh garlic = 1 SIGHI; dehydration may slightly reduce histamine but is widely treated as 1) · fodmap: ADD oligos=high (Monash: garlic powder concentrated fructans even more than fresh) [2 src] |
| **gin** | ● | 0 (beverages) / — / — | 3 (beverages) / — / — | sighi: 0 -> 3. SIGHI leaflet treats alcohol as a substance to avoid (ethanol + acetaldehyde block DAO); spirits are histamine liberators. Score 0 is wrong. [2 src] |
| **ginger** | ● | 0 (vegetables) / O:L F:L P:L L:L / — | 1 (vegetables) / O:L F:L P:L L:L / — | sighi: 0 -> 1. SIGHI lists ginger as 1 (small amounts well tolerated). [2 src] |
| **grapefruit** | ○ | 2 (fruit) / O:L F:L P:L L:L / — | — / O:L F:L P:L L:L / — | sighi: drop. Sources disagree: one secondary report says SIGHI rates grapefruit 0 with '?', another says citrus = 2. Drop rather than guess. [2 src] |
| **green tea** | ● | 0 (beverages) / O:L F:L P:L L:L / — | 1 (beverages) / O:L F:L P:L L:L / — | sighi: 0 -> 1. SIGHI rates green tea 1 with blocker flag (DAO inhibitor via EGCG). [1 src] |
| **haddock** | ◐ | 0 (fish) / — / — | 1 (fish) / — / — | sighi: 0 -> 1. SIGHI treats fish as fresh-dependent; freshly caught/frozen low, retail fresh fish carries amine risk. SIGHI generally rates fresh fish 1. [2 src] |
| **halibut** | ◐ | 0 (fish) / — / — | 1 (fish) / — / — | sighi: 0 -> 1. Same reasoning as haddock — SIGHI scores retail fresh fish 1 by default. [1 src] |
| **herring** | ◐ | 2 (fish) / — / — | 3 (fish) / — / — | sighi: 2 -> 3. Herring is in Scombroidae-related group, particularly high in histamine; SIGHI lists herring with high concern. 3 better reflects risk. [2 src] |
| **kefir** | ◐ | 2 (dairy) / O:L F:L P:L L:M / Dairy | 3 (dairy) / O:L F:L P:L L:M / Dairy | sighi: 2 -> 3. Kefir is a fermented dairy; SIGHI consistently rates fermented dairy at 3 (incompatible). Conservative bump aligns with sauerkraut/yogurt/buttermilk class. [2 src] |
| **kiwi** | ○ | 1 (fruit) / O:L F:L P:L L:L / — | — / O:L F:L P:L L:L / — | sighi: drop. SIGHI doesn't have direct kiwi entry I can verify; some sources cite it as low/0 but assignments inconsistent. Drop per low-confidence rule. [1 src] |
| **lemon** | ◐ | 1 (fruit) / O:L F:L P:L L:L / — | 2 (fruit) / O:L F:L P:L L:L / — | sighi: 1 -> 2. MyHistaMap and SIGHI sources state lemon = 2 (histamine liberator). [2 src] |
| **lime** | ◐ | 1 (fruit) / O:L F:L P:L L:L / — | 0 (fruit) / O:L F:L P:L L:L / — | sighi: 1 -> 0. Multiple sources cite SIGHI rating lime at 0 (unlike lemon). [1 src] |
| **liver** | ◐ | 1 (meat) / — / — | 2 (meat) / — / — | sighi: 1 -> 2. SIGHI specifically lists offal/innards (esp. liver) as foods to avoid; accumulates histamine faster than muscle meat. [2 src] |
| **lobster** | ◐ | 1 (seafood) / — / — | 2 (seafood) / — / — | sighi: 1 -> 2. Crustaceans accumulate histamine rapidly (high free amino acid content); SIGHI generally rates seafood/shellfish 2. [2 src] |
| **mackerel** | ◐ | 2 (fish) / — / — | 3 (fish) / — / — | sighi.score: 2 -> 3 (SIGHI lists mackerel among fish that should be strictly avoided due to rapid histamine accumulation; consistent with category 3 'strict avoid') [2 src] |
| **mayonnaise** | ◐ | 1 (condiments) / — / — | 2 (condiments) / — / none | sighi.score: 1 -> 2 (commercial mayo contains vinegar + often mustard/lemon; multiple sources describe it as high-histamine - mast cell community treats as 'avoid') · allergens: added (standard mayo is gluten-free and dairy-free; egg-based) [2 src] |
| **melon** | ◐ | 0 (fruit) / O:L F:M P:L L:L / — | 0 (fruit) / — / — | fodmap: dropped - 'melon' is ambiguous (honeydew=low, cantaloupe=low at 120g, watermelon=high). Drop rather than guess; recommend splitting into specific melons. [2 src] |
| **mushroom** | ● | 1 (vegetables) / O:L F:L P:H L:L / — | 2 (vegetables) / O:L F:L P:H L:L / — | sighi.score: 1 -> 2 (SIGHI lists mushrooms as restricted with significant symptoms at usual intake) [3 src] |
| **mussels** | ◐ | 3 (seafood) / — / — | 2 (seafood) / — / — | sighi.score: 3 -> 2 (SIGHI rates bivalves at 2 - 'incompatible significant symptoms'; not at the strict-avoid tier reserved for fermented products and aged fish) [1 src] |
| **mustard** | ◐ | 2 (condiments) / O:L F:L P:L L:L / none | 0 (condiments) / O:L F:L P:L L:L / none | sighi.score: 2 -> 0 (per SIGHI, mustard seeds and powder score 0 - well tolerated. Note: prepared mustards containing vinegar may behave differently but the underlying ingredient is 0) [1 src] |
| **oat milk** | ◐ | — / — / none | — / O:L F:L P:L L:L / none | fodmap: added (Monash classes ~120ml/half cup as low FODMAP; higher serves go moderate-to-high in oligos. Conservatively recorded as 'low' at standard serve.) [2 src] |
| **onion powder** | ● | 0 (spices) / — / — | 0 (spices) / O:H F:L P:L L:L / — | fodmap: added (onion powder is concentrated onion; Monash classes onion powder as high oligos/fructans) [1 src] |
| **orange** | ◐ | 2 (fruit) / O:L F:L P:L L:L / — | 2 (fruit) / O:L F:L P:L L:L / — |  [3 src] |
| **oyster sauce** | ◐ | 2 (condiments) / — / — | 3 (condiments) / — / Gluten | sighi.score: 2 -> 3 (contains fermented soy sauce + oyster extract + yeast extract; behaves as strict-avoid) · allergens: added (typical oyster sauce contains wheat-based soy sauce / wheat starch; default to contains_gluten=true) [2 src] |
| **papaya** | ● | 1 (fruit) / O:L F:L P:L L:L / — | 2 (fruit) / O:L F:L P:L L:L / — | sighi.score: 1 -> 2 (SIGHI rates papaya as 2 - incompatible, histamine liberator + amine content) [2 src] |
| **peach** | ◐ | 0 (fruit) / O:L F:M P:H L:L / — | 0 (fruit) / O:L F:L P:H L:L / — | fodmap.fructose: moderate -> low (Monash yellow peach: contains sorbitol primarily; not excess fructose). Polyols correctly high. [2 src] |
| **peanuts** | ● | 1 (legumes) / O:L F:L P:L L:L / none | 2 (legumes) / O:L F:L P:L L:L / none | sighi.score: 1 -> 2 (SIGHI list lists peanuts as 2; histamine liberator) [2 src] |
| **pomegranate** | ◐ | 0 (fruit) / O:L F:M P:L L:L / — | 0 (fruit) / O:L F:L P:L L:L / — | fodmap.fructose: moderate -> low (Monash: pomegranate low FODMAP at 52g; primary FODMAP is fructans, not excess fructose) [2 src] |
| **raisin** | ◐ | 2 (fruit) / O:L F:H P:L L:L / — | 1 (fruit) / O:H F:H P:L L:L / — | sighi.score: 2 -> 1 (SIGHI lists raisins = 0 unsulphured; conservative 1 reflects sulphured raisin variability/dried-fruit caveat) · fodmap.oligos: low -> high (Monash: raisins high in oligo-fructans above 13g) [2 src] |
| **raspberry** | ● | 0 (fruit) / O:L F:L P:L L:L / — | 2 (fruit) / O:L F:L P:L L:L / — | sighi.score: 0 -> 2 (SIGHI lists raspberry = 2) [1 src] |
| **roquefort** | ● | 3 (dairy) / — / Dairy | 2 (dairy) / — / Dairy | sighi.score: 3 -> 2 (Direct SIGHI: Roquefort = 2 H A) [1 src] |
| **rum** | ● | 1 (beverages) / — / — | 2 (beverages) / — / — | sighi: 1 -> 2 (SIGHI rum = 2 H A L B; rated histamine + DAO blocker + alcohol) [1 src] |
| **rye** | ● | 0 (grains) / O:H F:L P:L L:L / Gluten | 1 (grains) / O:H F:L P:L L:L / Gluten | sighi: 0 -> 1 (SIGHI rye = 1, 'barely tolerated') [2 src] |
| **savoy cabbage** | ● | — / O:H F:L P:L L:L / — | 1 (vegetables) / O:H F:L P:L L:L / — | sighi: add score 1 (SIGHI Savoy cabbage = 1) · fodmap: keep current values (Monash: Savoy cabbage is fructans-rich, low FODMAP only at 1/2 cup serves) [2 src] |
| **scallops** | ● | 1 (seafood) / — / — | 2 (seafood) / — / — | sighi: 1 -> 2 (SIGHI bivalves incl. scallops = 2 H! L, histamine liberator) [1 src] |
| **sesame seeds** | ● | 0 (nuts_seeds) / O:L F:L P:L L:L / — | 1 (nuts_seeds) / O:L F:L P:L L:L / — | sighi: 0 -> 1 (SIGHI 'sesame' = 1, 'may cause diarrhea in some cases') [2 src] |
| **shrimp** | ● | 1 (seafood) / O:L F:L P:L L:L / none | 2 (seafood) / O:L F:L P:L L:L / none | sighi: 1 -> 2 (SIGHI shrimp/prawn = 2 H! L, histamine liberator) [2 src] |
| **soy milk** | ● | — / — / none | 2 (beverages) / O:H F:L P:L L:L / none | sighi: add score 2 (SIGHI: soy milk, soy drink = 2) · fodmap: add high oligos (Monash: soy milk from whole soybeans high in GOS) [2 src] |
| **sunflower oil** | ● | 0 (oils_fats) / O:L F:L P:L L:L / none | 1 (oils_fats) / O:L F:L P:L L:L / none | sighi: 0 -> 1 (SIGHI sunflower oil = 1, 'a single dose is no problem, but inflammatory in the long term') [1 src] |
| **sunflower seeds** | ● | 0 (nuts_seeds) / O:L F:L P:L L:L / — | 2 (nuts_seeds) / O:L F:L P:L L:L / — | sighi: 0 -> 2 (SIGHI sunflower seeds = 2 L, listed in starch/grains/seeds section) [2 src] |
| **sweet potato** | ● | 0 (vegetables) / O:L F:L P:M L:L / none | 0 (vegetables) / O:L F:L P:M L:L / none |  [2 src] |
| **tahini** | ● | 0 (condiments) / O:L F:L P:L L:L / — | 1 (condiments) / O:L F:L P:L L:L / — | sighi: 0 -> 1 per SIGHI sesame is rated 1 (moderately tolerated, test individually) [3 src] |
| **tuna, fresh** | ◐ | 1 (fish) / O:L F:L P:L L:L / none | 2 (fish) / O:L F:L P:L L:L / none | sighi 1 -> 2: SIGHI rates tuna high (scombroid family) even fresh; sources commonly cite 2-3 [2 src] |
| **vodka** | ◐ | 0 (beverages) / — / — | 1 (beverages) / — / — | sighi 0 -> 1: alcohol itself is DAO inhibitor; SIGHI rates all alcohol >=1; vodka is one of best but not 0 [2 src] |
| **walnuts** | ● | 1 (nuts_seeds) / O:L F:L P:L L:L / none | 3 (nuts_seeds) / O:L F:L P:L L:L / none | sighi 1 -> 3: SIGHI rates walnuts 3 + liberator (highest histamine nut) [2 src] |
| **watermelon** | ● | 0 (fruit) / O:H F:H P:M L:L / — | 0 (fruit) / O:L F:H P:H L:L / — | fodmap oligos: high -> low (Monash lists watermelon as high in excess fructose + mannitol/polyol, not GOS/fructans) · fodmap polyols: moderate -> high (mannitol high per Monash) [2 src] |
| **whiskey** | ◐ | 1 (beverages) / — / — | 2 (beverages) / — / — | sighi 1 -> 2: aged barrel spirits accumulate histamine; ALKAA/clinical sources rate whiskey high [2 src] |
| **yogurt** | ◐ | 1 (dairy) / O:L F:L P:L L:M / Dairy | 2 (dairy) / O:L F:L P:L L:H / Dairy | sighi 1 -> 2: SIGHI rates yogurt 2 (fermented dairy with bacterial cultures); some sources cite 1, but fermented per definition · fodmap lactose: moderate -> high (Monash rates regular yogurt high for lactose; only lactose-free is low) [2 src] |

## B. Proposed drops — compound dishes (20)

Per your direction: only single-ingredient entries; compounds should be decomposed by the vision pipeline.

| Ingredient | Currently present in | Rationale |
|---|---|---|
| **bbq sauce** | sighi | Compound product — BBQ sauce is a recipe of tomato (high histamine), vinegar (varies), sugar, onion/garlic (high FODMAP), and often Worcestershire/spices. Drop per user direction: lookup table is f… |
| **breadcrumbs** | allergens | Compound dish — DROP per user direction. Breadcrumbs are processed wheat bread; vision pipeline should decompose as 'wheat flour'. (Note: explicitly listed by user as an example compound to drop.) |
| **croissant** | allergens | DROP: compound dish (per audit rules); flour + butter + eggs + sugar — not a single ingredient |
| **croutons** | allergens | DROP: compound food (per audit rules: explicitly listed as drop example) |
| **flour tortilla** | allergens | DROP: compound food (per audit rules: explicitly listed as drop example) |
| **gravy** | allergens | Compound dish (per hard rule 1). Drop entirely. |
| **hot dog** | sighi | Compound/processed product (per hard rule 1) — composition (pork/beef/turkey/fillers/spices) varies. Drop. |
| **hot sauce** | sighi | Compound dish — varies hugely (fresh vs fermented like Tabasco/sriracha, vinegar content, ingredients). Drop. |
| **ice cream** | fodmap, allergens | Compound dish (per hard rule 1) — varies enormously by recipe (dairy/non-dairy/sugar/inclusions/gluten). Drop. |
| **ketchup** | sighi | Compound dish (per hard rule 1) — tomato + vinegar + sugar + spices. Drop. Track tomato/vinegar individually. |
| **naan bread** | allergens | Drop entire entry: compound dish per hard rule (bread product), not a single ingredient. |
| **pancake** | allergens | Drop entry: compound dish per hard rule. |
| **pasta** | sighi, fodmap, allergens | Compound product (flour-based, mfg) — drop per rule 1 (analogous to flour tortilla/breadcrumbs). Use 'wheat pasta' or 'rice noodles' as specific entries instead. |
| **pesto** | sighi | Compound dish (basil + cheese + nuts + garlic + oil) — drop per rule 1. |
| **pita bread** | allergens | Compound dish (wheat-flour-based bread, like naan/flour tortilla in the exclusion list) — drop per rule 1. |
| **saffron** | sighi | sighi: drop (SIGHI does not list saffron explicitly; inferring score is low confidence) |
| **sausage, fresh** | sighi | sighi: drop (SIGHI groups 'sausages of all kinds' = 3; no fresh-vs-cured distinction; inferring 1 is low-confidence) |
| **smoked paprika** | sighi | sighi: drop (SIGHI lists 'paprika, sweet' = 0 and 'paprika, hot' = 2; smoked process not addressed; inference low-confidence) |
| **squid** | sighi | sighi: drop (SIGHI does not list cephalopods explicitly; seafood-section general rating is 2 but squid is not bivalve/crustacean; inference low-confidence) |
| **waffle** | allergens | DROP — compound dish per hard rules (waffle is composite, ingredients vary) |

## C. Proposed additions (5)

| Ingredient | Conf | Proposed values | Rationale |
|---|---|---|---|
| **dry-cured ham** | ● | 3 (meat) / O:L F:L P:L L:L / none | Encountered while researching bresaola/bacon. SIGHI: 'dry-cured ham' = 3. Common food (prosciutto, jamon, parma ham, serrano). Currently likely missing or under-rated in the table. |
| **smoked meat** | ● | 3 (meat) / O:L F:L P:L L:L / none | SIGHI: 'smoked meat (any)' = 3. Generic entry covers smoked sausage/pastrami/etc. when more specific entry is missing. |
| **sourdough bread** | ● | 1 (grains) / O:L F:L P:L L:L / Gluten | If 'bread' is dropped as compound, sourdough is a meaningful single-ingredient bread distinct from regular wheat bread (much lower FODMAP via fermentation). Up to 2 slices low FODMAP per Monash. |
| **ricotta cheese** | ● | 0 (dairy) / — / Dairy | SIGHI: Ricotta = 0 (fresh cheese, low histamine). Common cooking ingredient that contrasts with aged cheeses. |
| **mozzarella cheese** | ● | 0 (dairy) / — / Dairy | SIGHI: Mozzarella = 0. Fresh/young cheese; useful complement to brie/blue cheese in the cheese category. |

## D. Low-confidence rows (7) — scrutinize

| Ingredient | Decision | Notes |
|---|---|---|
| **coconut yogurt** | keep | Confidence low on SIGHI bump — SIGHI does not specifically list 'coconut yogurt'. If unwilling to bump, set score back to 0 (per general 'coconut = 0' principle). RECOMMENDATION: leave at 0 if the user prefers strict primary-source adherence. |
| **grapefruit** | modify | Per the rule: low confidence -> drop. FODMAP kept (Monash: low FODMAP at 80g). |
| **kiwi** | modify | FODMAP confirmed low at 150g (2 small kiwi). |
| **saffron** | drop | Not in SIGHI list. Dropped per conservative rule. |
| **sausage, fresh** | drop | SIGHI does not separate fresh sausage. Dropping per conservative rule. |
| **smoked paprika** | drop | Sweet smoked paprika could be 0, hot smoked closer to 2; SIGHI silent on smoked variant. Dropped. |
| **squid** | drop | SIGHI seafood section covers bivalves and crustaceans (all = 2), but does not list squid/calamari. Dropping per conservative rule. |

## E. Kept as-is (220) — no change proposed

<details><summary>Click to expand</summary>

| Ingredient | SIGHI / FODMAP / Allergens | Conf |
|---|---|---|
| aged cheese | 3 (dairy) / — / Dairy | ● |
| amaranth | 0 (grains) / O:L F:L P:L L:L / none | ● |
| apple | 0 (fruit) / O:L F:H P:H L:L / none | ● |
| avocado | 2 (vegetables) / O:L F:L P:H L:L / none | ● |
| baked beans | — / O:H F:L P:L L:L / — | ◐ |
| baking powder | 0 (spices) / — / none | ● |
| banana, overripe | 2 (fruit) / — / — | ◐ |
| beef jerky | 3 (meat) / — / — | ● |
| beef, fresh | 0 (meat) / O:L F:L P:L L:L / none | ● |
| beet | 0 (vegetables) / — / — | ● |
| beetroot | — / O:H F:L P:L L:L / — | ● |
| bell pepper | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| black beans | 1 (legumes) / O:H F:L P:L L:L / — | ◐ |
| blackberry | 0 (fruit) / O:L F:M P:H L:L / — | ● |
| blueberry | 0 (fruit) / O:L F:L P:L L:L / — | ● |
| bresaola | 3 (meat) / — / — | ● |
| brie | 2 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| buckwheat | 0 (grains) / O:L F:L P:L L:L / none | ● |
| butter | 0 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| butternut squash | 0 (vegetables) / O:L F:M P:L L:L / — | ● |
| cabbage | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| camembert | 3 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| cardamom | 0 (spices) / — / — | ● |
| carrot | 0 (vegetables) / O:L F:L P:L L:L / none | ● |
| casein | — / — / Dairy | ● |
| cashew butter | — / — / none | ◐ |
| cashew milk | — / — / none | ◐ |
| celery | 0 (vegetables) / O:M F:L P:M L:L / — | ● |
| champagne | 3 (beverages) / — / — | ● |
| cheddar cheese | 2 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| cherry | 0 (fruit) / O:L F:M P:H L:L / — | ● |
| chia seeds | 0 (nuts_seeds) / O:L F:L P:L L:L / — | ● |
| chicken | 0 (meat) / O:L F:L P:L L:L / none | ● |
| chocolate | 2 (sweets) / — / — | ◐ |
| chorizo | 3 (meat) / — / — | ● |
| cilantro | 0 (spices) / — / — | ● |
| clams | 2 (seafood) / — / — | ● |
| cocoa powder | 2 (sweets) / — / — | ● |
| coconut | 0 (fruit) / O:L F:L P:M L:L / — | ● |
| coconut butter | 0 (fruit) / O:L F:L P:M L:L / none | ◐ |
| coconut cream | 0 (fruit) / O:L F:L P:M L:L / none | ● |
| coconut flakes | 0 (nuts_seeds) / O:L F:L P:M L:L / — | ◐ |
| coconut milk | 0 (fruit) / O:L F:L P:M L:L / none | ● |
| coconut oil | 0 (oils_fats) / O:L F:L P:L L:L / none | ● |
| coconut yogurt | 0 (fruit) / O:L F:L P:M L:L / none | ○ |
| cod | 0 (fish) / O:L F:L P:L L:L / none | ● |
| coffee | 1 (beverages) / O:L F:L P:L L:L / none | ● |
| condensed milk | — / — / Dairy | ● |
| cooking oil | 0 (oils_fats) / — / none | ● |
| coriander seed | 0 (spices) / — / — | ◐ |
| corn | 0 (vegetables) / O:L F:L P:M L:L / none | ● |
| corn flour | 0 (grains) / O:L F:L P:L L:L / none | ● |
| corn tortilla | — / — / none | ● |
| cottage cheese | 0 (dairy) / O:L F:L P:L L:M / Dairy | ● |
| couscous | 0 (grains) / O:H F:L P:L L:L / Gluten | ● |
| cranberry | 0 (fruit) / O:L F:M P:L L:L / — | ● |
| cream | 0 (dairy) / O:L F:L P:L L:M / Dairy | ● |
| cream cheese | 0 (dairy) / O:L F:L P:L L:M / Dairy | ● |
| cucumber | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| cumin | 0 (spices) / — / — | ◐ |
| dried apricot | 2 (fruit) / — / — | ◐ |
| duck | 0 (meat) / O:L F:L P:L L:L / — | ● |
| egg | 0 (eggs) / O:L F:L P:L L:L / none | ● |
| egg yolk | 0 (eggs) / — / — | ● |
| eggplant | 2 (vegetables) / O:L F:L P:M L:L / — | ● |
| energy drink | 2 (beverages) / — / — | ● |
| evaporated milk | — / — / Dairy | ● |
| farro | — / — / Gluten | ● |
| fennel | 0 (vegetables) / O:M F:L P:L L:L / — | ● |
| fermented tofu | 3 (fermented) / — / — | ◐ |
| feta cheese | 1 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| fig | 0 (fruit) / O:L F:M P:L L:L / — | ● |
| fish sauce | 3 (condiments) / O:L F:L P:L L:L / — | ● |
| flax seeds | 0 (nuts_seeds) / O:L F:L P:L L:L / — | ◐ |
| ghee | 0 (oils_fats) / O:L F:L P:L L:L / Dairy | ● |
| goat cheese, fresh | 0 (dairy) / O:L F:L P:L L:M / Dairy | ● |
| gorgonzola | 3 (dairy) / — / Dairy | ● |
| gouda cheese | 2 (dairy) / O:L F:L P:L L:L / Dairy | ◐ |
| grape | 0 (fruit) / O:L F:M P:L L:L / — | ◐ |
| green beans | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| ground beef | 1 (meat) / — / — | ● |
| gruyere cheese | 2 (dairy) / — / Dairy | ● |
| ham | 2 (meat) / — / — | ● |
| hazelnuts | 0 (nuts_seeds) / O:L F:L P:L L:L / — | ◐ |
| hemp milk | — / — / none | ● |
| hemp seeds | 0 (nuts_seeds) / — / — | ● |
| herbal tea | 0 (beverages) / O:L F:L P:L L:L / — | ◐ |
| herring, smoked | 3 (fish) / — / — | ● |
| honey | 0 (condiments) / O:H F:H P:L L:L / none | ● |
| kale | 0 (vegetables) / O:L F:L P:L L:L / — | ◐ |
| kidney beans | 1 (legumes) / O:H F:L P:L L:L / — | ● |
| kimchi | 3 (fermented) / — / — | ● |
| kombucha | 3 (beverages) / — / — | ● |
| lactose | — / — / Dairy | ● |
| lamb | 0 (meat) / O:L F:L P:L L:L / none | ● |
| lard | 0 (oils_fats) / — / — | ● |
| leek | 0 (vegetables) / O:H F:L P:L L:L / — | ● |
| lentils | 1 (legumes) / O:H F:L P:L L:L / none | ◐ |
| lettuce | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| macadamia nuts | 0 (nuts_seeds) / O:L F:L P:L L:L / — | ● |
| mackerel, canned | 3 (fish) / — / — | ● |
| malt | — / — / Gluten | ● |
| mango | 0 (fruit) / O:L F:H P:L L:L / — | ● |
| maple syrup | 0 (condiments) / O:L F:L P:L L:L / none | ● |
| mascarpone | 0 (dairy) / — / Dairy | ● |
| microgreens | 0 (vegetables) / O:L F:L P:L L:L / — | ◐ |
| milk | 0 (dairy) / O:L F:L P:L L:H / Dairy | ● |
| millet | 0 (grains) / O:L F:L P:L L:L / none | ● |
| mint | 0 (spices) / — / — | ● |
| miso | 3 (legumes) / — / — | ● |
| mixed salad greens | 0 (vegetables) / O:L F:L P:L L:L / — | ◐ |
| mortadella | 3 (meat) / — / — | ● |
| mozzarella | 0 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| natto | 3 (fermented) / — / — | ● |
| nectarine | 0 (fruit) / O:L F:M P:H L:L / — | ● |
| nutmeg | 0 (spices) / — / — | ◐ |
| oats | 0 (grains) / O:L F:L P:L L:L / none | ● |
| octopus | 2 (seafood) / — / — | ◐ |
| olive oil | 0 (oils_fats) / O:L F:L P:L L:L / none | ● |
| olives | 2 (vegetables) / O:L F:L P:L L:L / — | ● |
| onion | 0 (vegetables) / O:H F:L P:L L:L / — | ● |
| orange juice | 2 (beverages) / — / — | ◐ |
| oregano | 0 (spices) / — / — | ● |
| oysters | 2 (seafood) / — / — | ◐ |
| pancetta | 3 (meat) / — / — | ● |
| paprika | 0 (spices) / — / — | ◐ |
| parmesan cheese | 3 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| parsley | 0 (spices) / — / — | ● |
| parsnip | 0 (vegetables) / O:L F:L P:M L:L / — | ● |
| peanut butter | — / — / none | ● |
| pear | 0 (fruit) / O:L F:H P:H L:L / — | ● |
| peas | 0 (vegetables) / O:H F:L P:L L:L / — | ● |
| pecans | 0 (nuts_seeds) / O:L F:L P:L L:L / — | ◐ |
| pepperoni | 3 (meat) / — / — | ● |
| perch | 0 (fish) / — / — | ◐ |
| pickled vegetables | 3 (fermented) / — / — | ● |
| pickles | 3 (vegetables) / — / — | ● |
| pike | 0 (fish) / — / — | ◐ |
| pine nuts | 0 (nuts_seeds) / O:L F:L P:L L:L / — | ● |
| pineapple | 2 (fruit) / O:L F:L P:L L:L / — | ● |
| pistachios | 0 (nuts_seeds) / O:H F:L P:L L:L / — | ● |
| plum | 1 (fruit) / O:L F:L P:H L:L / — | ● |
| polenta | 0 (grains) / O:L F:L P:L L:L / none | ● |
| pork, fresh | 0 (meat) / O:L F:L P:L L:L / none | ● |
| potato | 0 (vegetables) / O:L F:L P:L L:L / none | ● |
| prawns | 1 (seafood) / — / — | ● |
| prosciutto | 3 (meat) / — / — | ● |
| pumpkin | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| pumpkin seeds | 0 (nuts_seeds) / O:L F:L P:L L:L / — | ● |
| quail | 0 (meat) / — / — | ● |
| quail egg | 0 (eggs) / — / — | ● |
| quark | 0 (dairy) / — / Dairy | ● |
| quinoa | 0 (grains) / O:L F:L P:L L:L / none | ● |
| rabbit | 0 (meat) / — / — | ◐ |
| radish | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| rapeseed oil | 0 (oils_fats) / — / — | ● |
| red wine | 3 (beverages) / — / — | ● |
| rice | 0 (grains) / O:L F:L P:L L:L / none | ● |
| rice milk | — / — / none | ● |
| rice noodles | 0 (grains) / O:L F:L P:L L:L / none | ● |
| ricotta | 0 (dairy) / O:L F:L P:L L:M / Dairy | ● |
| rosemary | 0 (spices) / — / — | ● |
| salami | 3 (meat) / — / — | ● |
| salmon, fresh | 0 (fish) / O:L F:L P:L L:L / none | ● |
| salmon, smoked | 3 (fish) / — / — | ● |
| salt | 0 (spices) / — / none | ● |
| sardines, canned | 3 (fish) / — / — | ● |
| sauerkraut | 3 (vegetables) / — / — | ● |
| sausage, cured | 3 (meat) / — / — | ● |
| sea bass | 0 (fish) / — / — | ◐ |
| seitan | — / — / Gluten | ● |
| semolina | — / — / Gluten | ● |
| sesame oil | 0 (oils_fats) / — / — | ◐ |
| shallot | — / O:H F:L P:L L:L / — | ● |
| smoked fish | 3 (fish) / — / — | ● |
| sole | 0 (fish) / — / — | ◐ |
| sour cream | 1 (dairy) / O:L F:L P:L L:M / Dairy | ● |
| sourdough bread | 2 (grains) / — / Gluten | ◐ |
| sourdough starter | 3 (fermented) / — / — | ◐ |
| soy sauce | 3 (legumes) / O:L F:L P:L L:L / Gluten | ● |
| soybeans | 2 (legumes) / O:H F:L P:L L:L / — | ● |
| spelt | 0 (grains) / O:H F:L P:L L:L / Gluten | ● |
| spinach | 2 (vegetables) / O:L F:L P:L L:L / none | ● |
| split peas | — / O:H F:L P:L L:L / — | ● |
| spring onion (white) | — / O:H F:L P:L L:L / — | ● |
| sriracha | 2 (condiments) / — / — | ◐ |
| strawberry | 2 (fruit) / O:L F:L P:L L:L / — | ● |
| sugar | 0 (condiments) / O:L F:L P:L L:L / none | ● |
| sun-dried tomato | 3 (vegetables) / — / — | ● |
| swiss cheese | 2 (dairy) / O:L F:L P:L L:L / Dairy | ● |
| tapioca | — / O:L F:L P:L L:L / none | ● |
| tempeh | 2 (legumes) / — / — | ● |
| teriyaki sauce | 3 (condiments) / — / Gluten | ● |
| thyme | 0 (spices) / — / — | ● |
| tilapia | 0 (fish) / — / — | ● |
| tofu | 1 (legumes) / O:L F:L P:L L:L / none | ● |
| tomato | 2 (vegetables) / O:L F:M P:L L:L / none | ● |
| tomato paste | 3 (vegetables) / — / — | ● |
| tomato sauce | 2 (vegetables) / — / — | ◐ |
| trout | 0 (fish) / — / — | ● |
| tuna, canned | 3 (fish) / — / — | ● |
| turkey | 0 (meat) / O:L F:L P:L L:L / none | ● |
| turmeric | 0 (spices) / — / — | ● |
| turnip | 0 (vegetables) / O:L F:L P:L L:L / — | ● |
| vanilla | 0 (spices) / — / — | ● |
| veal | 0 (meat) / — / — | ● |
| vegetable oil | 0 (oils_fats) / — / none | ● |
| venison | 0 (meat) / — / — | ◐ |
| vinegar | 3 (condiments) / O:L F:L P:L L:L / none | ◐ |
| water | 0 (beverages) / — / — | ● |
| wheat flour | 0 (grains) / O:H F:L P:L L:L / Gluten | ● |
| whey | — / — / Dairy | ● |
| whey protein | 0 (dairy) / — / Dairy | ◐ |
| whipped cream | — / — / Dairy | ● |
| white beans | 1 (legumes) / O:H F:L P:L L:L / — | ● |
| white chocolate | 0 (sweets) / — / — | ● |
| white wine | 2 (beverages) / — / — | ● |
| white wine vinegar | 3 (condiments) / — / — | ● |
| worcestershire sauce | 3 (condiments) / — / Gluten | ● |
| zucchini | 0 (vegetables) / O:L F:L P:L L:L / — | ● |

</details>

---

## Source files
- Raw slice YAMLs: `/tmp/ingredient-audit/slice-{1..8}-results.yaml`
- Input slices (current values): `/tmp/ingredient-audit/slice-{1..8}.json`
- Extracted SIGHI PDF text (used by several agents): `/tmp/ingredient-audit/sighi.txt`, `sighi2.txt`
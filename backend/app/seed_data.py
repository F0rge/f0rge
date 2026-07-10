from __future__ import annotations

# Default catalog rows shared by migrations (which insert them) and the
# test fixture (which needs the same rows on a create_all-built test DB,
# since testcontainers never runs the migration chain). Plain data — no ORM
# imports here, so migrations can import this module without binding to a
# model definition that might drift.
#
# IMPORTANT: DEFAULT_SUPPLEMENTS / DEFAULT_MEDICATIONS below are read LIVE by
# already-applied migrations 009 / 010 at `upgrade()` time (see
# migrations/versions/009_seed_default_catalogs.py and 010_*.py). Migrations
# must be frozen-in-time — do NOT append new rows to these two lists, and do
# NOT remove/relabel existing entries, or a fresh `alembic upgrade head` will
# silently change what 009/010 insert. New catalog rows and the vitamin_d_k2
# split live in their own constants below, consumed only by migration 011.

DEFAULT_SUPPLEMENTS: list[tuple[str, str]] = [
    ("nac", "NAC"),
    ("fish_oil", "Fish Oil"),
    ("magnesium", "Magnesium"),
    ("beef_organs", "Beef Organs"),
    ("allicin", "Allicin"),
    ("oregano", "Oregano Oil"),
    ("vitamin_d_k2", "D3 + K2"),
    ("dao", "DAO"),
    ("creatine", "Creatine"),
]

DEFAULT_SYMPTOMS: list[tuple[str, str]] = [
    ("vss", "Visual Snow"),
    ("tinnitus", "Tinnitus"),
    ("fasciculations", "Fasciculations"),
    ("photophobia", "Photophobia"),
    ("fight_flight", "Fight-or-Flight"),
    ("brain_fog", "Brain Fog"),
    ("pem", "Post-Exertional Malaise"),
]

# Seeded by migration 010 (create_medication_catalog), same convention as
# DEFAULT_SUPPLEMENTS/DEFAULT_SYMPTOMS above.
DEFAULT_MEDICATIONS: list[tuple[str, str]] = [
    ("ibuprofen", "Ibuprofen"),
    ("paracetamol", "Paracetamol"),
    ("aspirin", "Aspirin"),
    ("antihistamine", "Antihistamine"),
    ("antacid", "Antacid"),
    ("imodium", "Imodium"),
]

# Seeded by migration 007 (create_diet_tag_catalog). Keys use hyphens — do NOT
# normalise to underscores; historical entry.diet_risk CSV values depend on it.
DEFAULT_DIET_TAGS: list[tuple[str, str]] = [
    ("high-histamine", "High-histamine"),
    ("high-fodmap", "High-FODMAP"),
    ("gluten", "Gluten"),
    ("dairy", "Dairy"),
]

# Seeded by migration 006 (add_trackers). Each tuple is
# (name, kind, icon, unit, position).
DEFAULT_TRACKERS: list[tuple[str, str, str, str | None, int]] = [
    ("Alcohol units", "counter", "wine", "units", 0),
    ("Caffeine servings", "counter", "coffee", "servings", 1),
    ("Sick", "binary", "thermometer", None, 2),
    ("Hot shower", "binary", "droplets", None, 3),
]


def supplement_seed_rows() -> list[tuple[str, str, bool, int]]:
    """Return (key, label, archived, sort_order) matching migrations 009 + 011."""
    rows: list[tuple[str, str, bool, int]] = []
    for sort_order, (key, label) in enumerate(DEFAULT_SUPPLEMENTS):
        archived = key == "vitamin_d_k2"
        rows.append((key, label, archived, sort_order))
    offset = len(DEFAULT_SUPPLEMENTS)
    for index, (key, label) in enumerate(SPLIT_VITAMIN_D_K2):
        rows.append((key, label, False, offset + index))
    offset += len(SPLIT_VITAMIN_D_K2)
    for index, (key, label) in enumerate(BULK_SUPPLEMENTS):
        rows.append((key, label, True, offset + index))
    return rows


def medication_seed_rows() -> list[tuple[str, str, bool, int]]:
    """Return (key, label, archived, sort_order) matching migrations 010 + 011."""
    rows: list[tuple[str, str, bool, int]] = [
        (key, label, False, sort_order)
        for sort_order, (key, label) in enumerate(DEFAULT_MEDICATIONS)
    ]
    offset = len(DEFAULT_MEDICATIONS)
    for index, (key, label) in enumerate(BULK_MEDICATIONS):
        rows.append((key, label, True, offset + index))
    return rows


# ---------------------------------------------------------------------------
# Migration 011 — vitamin_d_k2 split + exhaustive supplement/medication lists
# ---------------------------------------------------------------------------
# vitamin_d_k2 (DEFAULT_SUPPLEMENTS above) is retired in favour of two
# separate active entries. Both are ACTIVE (archived=false) — they replace
# the combined item on the daily picker.
SPLIT_VITAMIN_D_K2: list[tuple[str, str]] = [
    ("vitamin_d", "Vitamin D"),
    ("vitamin_k2", "Vitamin K2"),
]

# Bulk supplement/medication reference data. Seeded ARCHIVED (archived=true)
# by migration 011 — these exist so the user can find and activate whatever
# they actually take via /customize/catalogs search, without flooding the
# daily check-in picker (which only shows active items). Ordered for
# sort_order clustering: vitamins -> minerals -> amino acids -> fatty acids
# -> herbs/adaptogens -> probiotics/gut -> other. Generic names, one entry
# per commonly-recognized item (not per salt/ester variant).
BULK_SUPPLEMENTS: list[tuple[str, str]] = [
    # --- Vitamins ---
    ("vitamin_a", "Vitamin A"),
    ("vitamin_b1", "Vitamin B1 (Thiamine)"),
    ("vitamin_b2", "Vitamin B2 (Riboflavin)"),
    ("vitamin_b3", "Vitamin B3 (Niacin)"),
    ("vitamin_b5", "Vitamin B5 (Pantothenic Acid)"),
    ("vitamin_b6", "Vitamin B6 (Pyridoxine)"),
    ("vitamin_b7", "Vitamin B7 (Biotin)"),
    ("vitamin_b9", "Vitamin B9 (Folate)"),
    ("vitamin_b12", "Vitamin B12 (Cobalamin)"),
    ("vitamin_b_complex", "Vitamin B Complex"),
    ("vitamin_c", "Vitamin C"),
    ("vitamin_e", "Vitamin E"),
    ("vitamin_k1", "Vitamin K1"),
    ("multivitamin", "Multivitamin"),
    ("choline", "Choline"),
    ("inositol", "Inositol"),
    ("coq10", "CoQ10 (Ubiquinone)"),
    ("pqq", "PQQ"),
    ("alpha_gpc", "Alpha-GPC"),
    # --- Minerals ---
    ("calcium", "Calcium"),
    ("zinc", "Zinc"),
    ("iron", "Iron"),
    ("potassium", "Potassium"),
    ("selenium", "Selenium"),
    ("iodine", "Iodine"),
    ("copper", "Copper"),
    ("manganese", "Manganese"),
    ("chromium", "Chromium"),
    ("molybdenum", "Molybdenum"),
    ("boron", "Boron"),
    ("electrolytes", "Electrolytes"),
    # --- Amino acids / protein ---
    ("l_glutamine", "L-Glutamine"),
    ("l_carnitine", "L-Carnitine"),
    ("acetyl_l_carnitine", "Acetyl-L-Carnitine"),
    ("l_theanine", "L-Theanine"),
    ("l_tyrosine", "L-Tyrosine"),
    ("l_arginine", "L-Arginine"),
    ("l_lysine", "L-Lysine"),
    ("l_ornithine", "L-Ornithine"),
    ("taurine", "Taurine"),
    ("glycine", "Glycine"),
    ("bcaa", "BCAAs"),
    ("collagen", "Collagen"),
    ("whey_protein", "Whey Protein"),
    ("hmb", "HMB"),
    # --- Fatty acids ---
    ("omega_3", "Omega-3"),
    ("cod_liver_oil", "Cod Liver Oil"),
    ("krill_oil", "Krill Oil"),
    ("evening_primrose_oil", "Evening Primrose Oil"),
    ("mct_oil", "MCT Oil"),
    ("cla", "CLA (Conjugated Linoleic Acid)"),
    # --- Herbs / adaptogens ---
    ("ashwagandha", "Ashwagandha"),
    ("rhodiola", "Rhodiola"),
    ("turmeric", "Turmeric (Curcumin)"),
    ("ginger", "Ginger"),
    ("echinacea", "Echinacea"),
    ("elderberry", "Elderberry"),
    ("ginseng", "Ginseng"),
    ("ginkgo_biloba", "Ginkgo Biloba"),
    ("milk_thistle", "Milk Thistle"),
    ("valerian_root", "Valerian Root"),
    ("chamomile", "Chamomile"),
    ("st_johns_wort", "St. John's Wort"),
    ("saw_palmetto", "Saw Palmetto"),
    ("holy_basil", "Holy Basil (Tulsi)"),
    ("maca_root", "Maca Root"),
    ("licorice_root", "Licorice Root"),
    ("cinnamon", "Cinnamon"),
    ("garlic", "Garlic"),
    ("cranberry", "Cranberry"),
    ("green_tea_extract", "Green Tea Extract"),
    ("black_cohosh", "Black Cohosh"),
    ("bilberry", "Bilberry"),
    ("astragalus", "Astragalus"),
    ("reishi_mushroom", "Reishi Mushroom"),
    ("lions_mane_mushroom", "Lion's Mane Mushroom"),
    ("cordyceps", "Cordyceps"),
    ("hawthorn", "Hawthorn"),
    ("feverfew", "Feverfew"),
    ("passionflower", "Passionflower"),
    # --- Probiotics / gut ---
    ("probiotic", "Probiotic"),
    ("prebiotic_fiber", "Prebiotic Fiber"),
    ("psyllium_husk", "Psyllium Husk"),
    ("digestive_enzymes", "Digestive Enzymes"),
    ("slippery_elm", "Slippery Elm"),
    ("apple_cider_vinegar", "Apple Cider Vinegar"),
    ("betaine_hcl", "Betaine HCl"),
    ("colostrum", "Colostrum"),
    ("aloe_vera", "Aloe Vera"),
    # --- Other ---
    ("melatonin", "Melatonin"),
    ("glucosamine", "Glucosamine"),
    ("chondroitin", "Chondroitin"),
    ("msm", "MSM"),
    ("hyaluronic_acid", "Hyaluronic Acid"),
    ("alpha_lipoic_acid", "Alpha Lipoic Acid"),
    ("nad_precursor", "NMN/NR (NAD+ Precursor)"),
    ("quercetin", "Quercetin"),
    ("resveratrol", "Resveratrol"),
    ("lutein_zeaxanthin", "Lutein & Zeaxanthin"),
    ("spirulina", "Spirulina"),
    ("chlorella", "Chlorella"),
    ("beta_alanine", "Beta-Alanine"),
    ("citrulline", "Citrulline"),
    ("berberine", "Berberine"),
    ("sam_e", "SAM-e"),
    ("five_htp", "5-HTP"),
    ("gaba", "GABA"),
    ("phosphatidylserine", "Phosphatidylserine"),
    ("activated_charcoal", "Activated Charcoal"),
    ("bee_pollen", "Bee Pollen"),
    ("dhea", "DHEA"),
    ("beta_carotene", "Beta-Carotene"),
    ("astaxanthin", "Astaxanthin"),
    ("folic_acid", "Folic Acid"),
    ("magnesium_glycinate", "Magnesium Glycinate"),
]

BULK_MEDICATIONS: list[tuple[str, str]] = [
    # --- Analgesics / anti-inflammatory ---
    ("naproxen", "Naproxen"),
    ("diclofenac", "Diclofenac"),
    ("codeine", "Codeine"),
    ("tramadol", "Tramadol"),
    ("morphine", "Morphine"),
    ("celecoxib", "Celecoxib"),
    ("prednisone", "Prednisone"),
    ("sumatriptan", "Sumatriptan"),
    ("colchicine", "Colchicine"),
    # --- Antihistamines / allergy ---
    ("loratadine", "Loratadine"),
    ("cetirizine", "Cetirizine"),
    ("fexofenadine", "Fexofenadine"),
    ("diphenhydramine", "Diphenhydramine (Benadryl)"),
    ("chlorphenamine", "Chlorphenamine"),
    ("promethazine", "Promethazine"),
    ("epinephrine", "Epinephrine (EpiPen)"),
    # --- Gastrointestinal ---
    ("omeprazole", "Omeprazole"),
    ("esomeprazole", "Esomeprazole"),
    ("lansoprazole", "Lansoprazole"),
    ("ranitidine", "Ranitidine"),
    ("famotidine", "Famotidine"),
    ("simethicone", "Simethicone"),
    ("bisacodyl", "Bisacodyl"),
    ("senna", "Senna"),
    ("lactulose", "Lactulose"),
    ("macrogol", "Macrogol (Polyethylene Glycol)"),
    ("ondansetron", "Ondansetron"),
    ("metoclopramide", "Metoclopramide"),
    ("hyoscine_butylbromide", "Hyoscine Butylbromide (Buscopan)"),
    ("mesalazine", "Mesalazine"),
    ("domperidone", "Domperidone"),
    # --- Respiratory ---
    ("salbutamol", "Salbutamol (Albuterol)"),
    ("dextromethorphan", "Dextromethorphan"),
    ("guaifenesin", "Guaifenesin"),
    ("pseudoephedrine", "Pseudoephedrine"),
    ("phenylephrine", "Phenylephrine"),
    ("beclometasone_nasal", "Beclometasone Nasal Spray"),
    ("fluticasone_nasal", "Fluticasone Nasal Spray"),
    ("montelukast", "Montelukast"),
    ("ipratropium", "Ipratropium"),
    ("budesonide", "Budesonide"),
    # --- Antibiotics / antifungals / antivirals ---
    ("amoxicillin", "Amoxicillin"),
    ("amoxicillin_clavulanate", "Amoxicillin/Clavulanate (Co-amoxiclav)"),
    ("azithromycin", "Azithromycin"),
    ("doxycycline", "Doxycycline"),
    ("ciprofloxacin", "Ciprofloxacin"),
    ("cephalexin", "Cephalexin"),
    ("clindamycin", "Clindamycin"),
    ("metronidazole", "Metronidazole"),
    ("nitrofurantoin", "Nitrofurantoin"),
    ("trimethoprim", "Trimethoprim"),
    ("fluconazole", "Fluconazole"),
    ("clotrimazole", "Clotrimazole"),
    ("aciclovir", "Aciclovir"),
    # --- Cardiovascular ---
    ("amlodipine", "Amlodipine"),
    ("lisinopril", "Lisinopril"),
    ("losartan", "Losartan"),
    ("atenolol", "Atenolol"),
    ("bisoprolol", "Bisoprolol"),
    ("propranolol", "Propranolol"),
    ("atorvastatin", "Atorvastatin"),
    ("simvastatin", "Simvastatin"),
    ("warfarin", "Warfarin"),
    ("clopidogrel", "Clopidogrel"),
    ("furosemide", "Furosemide"),
    ("hydrochlorothiazide", "Hydrochlorothiazide"),
    ("digoxin", "Digoxin"),
    ("nitroglycerin", "Nitroglycerin"),
    ("verapamil", "Verapamil"),
    # --- Endocrine / metabolic ---
    ("metformin", "Metformin"),
    ("levothyroxine", "Levothyroxine"),
    ("insulin", "Insulin"),
    ("gliclazide", "Gliclazide"),
    # --- CNS / mental health / neuro ---
    ("sertraline", "Sertraline"),
    ("fluoxetine", "Fluoxetine"),
    ("citalopram", "Citalopram"),
    ("escitalopram", "Escitalopram"),
    ("venlafaxine", "Venlafaxine"),
    ("mirtazapine", "Mirtazapine"),
    ("amitriptyline", "Amitriptyline"),
    ("diazepam", "Diazepam"),
    ("lorazepam", "Lorazepam"),
    ("zolpidem", "Zolpidem"),
    ("zopiclone", "Zopiclone"),
    ("gabapentin", "Gabapentin"),
    ("pregabalin", "Pregabalin"),
    ("levetiracetam", "Levetiracetam"),
    ("carbamazepine", "Carbamazepine"),
    ("valproic_acid", "Valproic Acid"),
    ("melatonin_med", "Melatonin (Medicinal)"),
    # --- Dermatological ---
    ("hydrocortisone_cream", "Hydrocortisone Cream"),
    ("clobetasol_cream", "Clobetasol Cream"),
    ("benzoyl_peroxide", "Benzoyl Peroxide"),
    ("adapalene", "Adapalene"),
    ("permethrin", "Permethrin"),
    ("miconazole", "Miconazole"),
    ("calamine", "Calamine Lotion"),
    ("salicylic_acid", "Salicylic Acid"),
    # --- Ophthalmological ---
    ("artificial_tears", "Artificial Tears"),
    ("chloramphenicol_eye_drops", "Chloramphenicol Eye Drops"),
    ("timolol_eye_drops", "Timolol Eye Drops"),
    # --- Other ---
    ("naloxone", "Naloxone"),
    ("activated_charcoal_med", "Activated Charcoal (Medicinal)"),
]

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

# Onboarding / customize search templates — not seeded to DB (no global tracker table).
# Positions start at 4 (after DEFAULT_TRACKERS). Icons must match KNOWN_ICONS in
# frontend/components/checkin/cards/components/IconPicker.tsx.
BULK_TRACKERS: list[tuple[str, str, str, str | None, int]] = [
    ("Water glasses", "counter", "droplet", "glasses", 4),
    ("Exercise minutes", "counter", "activity", "minutes", 5),
    ("Steps", "counter", "footprints", "steps", 6),
    ("Meditation", "counter", "brain", "minutes", 7),
    ("Screen time", "counter", "tv", "hours", 8),
    ("Sleep hours", "counter", "moon", "hours", 9),
    ("Sugar servings", "counter", "cookie", "servings", 10),
    ("Cannabis", "binary", "flame", None, 11),
    ("Nicotine", "binary", "pill", None, 12),
    ("Fasting", "binary", "clock", None, 13),
    ("Travel day", "binary", "bike", None, 14),
    ("Period", "binary", "droplets", None, 15),
    ("Sauna", "binary", "flame", None, 16),
    ("Cold exposure", "binary", "thermometer", None, 17),
    ("Social outing", "binary", "smile", None, 18),
    ("Work from home", "binary", "bookopen", None, 19),
    ("Stressful day", "binary", "zap", None, 20),
    ("Migraine day", "binary", "frown", None, 21),
    ("Meal prep", "binary", "utensils", None, 22),
    ("Outdoor time", "counter", "sun", "hours", 23),
    ("Reading", "counter", "bookopen", "minutes", 24),
    ("Music practice", "counter", "music", "minutes", 25),
    ("Strength training", "counter", "dumbbell", "minutes", 26),
    ("Cardio", "counter", "heartpulse", "minutes", 27),
    ("Supplements taken", "binary", "pill", None, 28),
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

# Bulk symptom reference data for onboarding search. Seeded ARCHIVED (archived=true)
# by migration 029 for the reference user — discoverable via search without flooding
# the daily picker. DEFAULT_SYMPTOMS keys are excluded (they are the curated chips).
BULK_SYMPTOMS: list[tuple[str, str]] = [
    # --- Head / neurological ---
    ("headache", "Headache"),
    ("migraine", "Migraine"),
    ("dizziness", "Dizziness"),
    ("vertigo", "Vertigo"),
    ("lightheadedness", "Lightheadedness"),
    ("brain_zaps", "Brain Zaps"),
    ("numbness_tingling", "Numbness / Tingling"),
    ("weakness", "Weakness"),
    ("tremor", "Tremor"),
    ("seizure", "Seizure"),
    ("aphasia", "Aphasia / Word-Finding"),
    ("memory_issues", "Memory Issues"),
    ("concentration_issues", "Concentration Issues"),
    ("aphantasia_episode", "Aphantasia Episode"),
    ("visual_aura", "Visual Aura"),
    ("ocular_migraine", "Ocular Migraine"),
    ("double_vision", "Double Vision"),
    ("blurred_vision", "Blurred Vision"),
    ("eye_pain", "Eye Pain"),
    ("dry_eyes", "Dry Eyes"),
    ("hearing_loss", "Hearing Loss"),
    ("hyperacusis", "Hyperacusis"),
    ("ear_fullness", "Ear Fullness"),
    ("ear_pain", "Ear Pain"),
    ("neuro_symptoms", "Neuro symptoms"),
    # --- Chronic illness / dysautonomia / MCAS ---
    ("orthostatic_intolerance", "Orthostatic Intolerance"),
    ("pots_flare", "POTS Flare"),
    ("dysautonomia", "Dysautonomia"),
    ("mcas_reaction", "MCAS Reaction"),
    ("histamine_flare", "Histamine Flare"),
    ("mast_cell_activation", "Mast Cell Activation"),
    ("anaphylaxis", "Anaphylaxis"),
    ("allergic_reaction", "Allergic Reaction"),
    ("crash", "Crash / Flare"),
    ("flare", "General Flare"),
    ("relapse", "Relapse"),
    ("overstimulation", "Overstimulation"),
    ("sensory_overload", "Sensory Overload"),
    ("adrenaline_surge", "Adrenaline Surge"),
    ("autonomic_dysfunction", "Autonomic Dysfunction"),
    ("heat_intolerance", "Heat Intolerance"),
    ("cold_intolerance", "Cold Intolerance"),
    ("temperature_dysregulation", "Temperature Dysregulation"),
    ("blood_pressure_spike", "Blood Pressure Spike"),
    ("blood_pressure_drop", "Blood Pressure Drop"),
    ("tachycardia", "Tachycardia"),
    ("bradycardia", "Bradycardia"),
    ("palpitations", "Palpitations"),
    ("syncope", "Syncope / Fainting"),
    ("near_syncope", "Near-Syncope"),
    # --- Pain / musculoskeletal ---
    ("joint_pain", "Joint pain / crepitus"),
    ("muscle_pain", "Muscle Pain"),
    ("myalgia", "Myalgia"),
    ("back_pain", "Back Pain"),
    ("neck_pain", "Neck Pain"),
    ("chest_pain", "Chest Pain"),
    ("abdominal_pain", "Abdominal Pain"),
    ("pelvic_pain", "Pelvic Pain"),
    ("nerve_pain", "Nerve Pain"),
    ("neuropathy", "Neuropathy"),
    ("fibromyalgia_flare", "Fibromyalgia Flare"),
    ("cramping", "Cramping"),
    ("stiffness", "Stiffness"),
    ("spasms", "Muscle Spasms"),
    # --- GI ---
    ("nausea", "Nausea"),
    ("vomiting", "Vomiting"),
    ("diarrhea", "Diarrhea"),
    ("constipation", "Constipation"),
    ("bloating", "Bloating"),
    ("gas", "Gas"),
    ("heartburn", "Heartburn"),
    ("reflux", "Acid Reflux"),
    ("indigestion", "Indigestion"),
    ("appetite_loss", "Appetite Loss"),
    ("appetite_increase", "Increased Appetite"),
    ("food_intolerance", "Food Intolerance Reaction"),
    ("early_satiety", "Early Satiety"),
    ("abdominal_cramping", "Abdominal Cramping"),
    # --- Respiratory / ENT ---
    ("shortness_of_breath", "Shortness of Breath"),
    ("cough", "Cough"),
    ("congestion", "Congestion"),
    ("sinus_pressure", "Sinus Pressure"),
    ("sore_throat", "Sore Throat"),
    ("hoarse_voice", "Hoarse Voice"),
    ("runny_nose", "Runny Nose"),
    ("post_nasal_drip", "Post-Nasal Drip"),
    # --- Skin / allergic ---
    ("rash", "Rash"),
    ("hives", "Hives"),
    ("itching", "Itching"),
    ("flushing", "Flushing"),
    ("eczema_flare", "Eczema Flare"),
    ("acne_flare", "Acne Flare"),
    ("swelling", "Swelling"),
    ("angioedema", "Angioedema"),
    # --- Sleep / fatigue ---
    ("insomnia", "Insomnia"),
    ("hypersomnia", "Hypersomnia"),
    ("unrefreshing_sleep", "Unrefreshing Sleep"),
    ("night_sweats", "Night Sweats"),
    ("fatigue", "Fatigue"),
    ("exhaustion", "Exhaustion"),
    ("wired_tired", "Wired but Tired"),
    ("daytime_sleepiness", "Daytime Sleepiness"),
    # --- Mental health / mood ---
    ("anxiety", "Anxiety"),
    ("panic_attack", "Panic Attack"),
    ("depression", "Depression"),
    ("irritability", "Irritability"),
    ("mood_swings", "Mood Swings"),
    ("brain_fog_severe", "Severe Brain Fog"),
    ("dissociation", "Dissociation"),
    ("depersonalization", "Depersonalization"),
    ("emotional_lability", "Emotional Lability"),
    # --- Endocrine / metabolic ---
    ("hypoglycemia", "Hypoglycemia"),
    ("blood_sugar_spike", "Blood Sugar Spike"),
    ("thirst", "Excessive Thirst"),
    ("frequent_urination", "Frequent Urination"),
    # --- Immune / infection ---
    ("fever", "Fever"),
    ("chills", "Chills"),
    ("lymph_node_swelling", "Lymph Node Swelling"),
    ("sore_muscles_viral", "Body Aches (Viral)"),
    ("post_viral_symptoms", "Post-Viral Symptoms"),
    # --- Reproductive / hormonal ---
    ("period_cramps", "Period Cramps"),
    ("pms", "PMS"),
    ("hot_flashes", "Hot Flashes"),
    ("hormone_flare", "Hormone Flare"),
    # --- Other ---
    ("hair_loss", "Hair Loss"),
    ("weight_gain", "Weight Gain"),
    ("weight_loss", "Weight Loss"),
    ("edema", "Edema / Water Retention"),
    ("restless_legs", "Restless Legs"),
    ("jaw_pain", "Jaw Pain / TMJ"),
    ("tooth_pain", "Tooth Pain"),
    ("bruising", "Easy Bruising"),
    ("cognitive_fatigue", "Cognitive Fatigue"),
    ("speech_difficulty", "Speech Difficulty"),
    ("balance_issues", "Balance Issues"),
    ("coordination_issues", "Coordination Issues"),
]


def symptom_seed_rows() -> list[tuple[str, str, bool, int]]:
    """Return (key, label, archived, sort_order) matching migrations 009 + 029."""
    rows: list[tuple[str, str, bool, int]] = [
        (key, label, False, sort_order) for sort_order, (key, label) in enumerate(DEFAULT_SYMPTOMS)
    ]
    offset = len(DEFAULT_SYMPTOMS)
    for index, (key, label) in enumerate(BULK_SYMPTOMS):
        rows.append((key, label, True, offset + index))
    return rows

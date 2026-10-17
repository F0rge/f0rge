"""Model key and comparable-listing groups shared by the tracker and the MCP server.

Reference price is the median ask of at least three other live listings in the same
brand + model group (wheels also split by brake and rim; bikes also require model year ±1).
"""

from __future__ import annotations

import collections
import json
import re

STOPB = set(
    "road gravel bike bicycle disc disk di2 etap axs ultegra dura ace dura-ace 105 grx sram shimano campagnolo rival force red apex tiagra sora claris super record chorus centaur ekar potenza edition team limited the and with carbon alu aluminium aluminum frameset complete new mechanical hydraulic hrd ltd 1x 2x 11 12 speed 12s 11s rim custom size cm".split()
)
STOPW = set(
    "complete wheels wheel wheelset wheelsets laufradsatz laufräder laufrad set pair paire de roues ruote coppia par ruedas disc disk disco brake brakes rim rims carbon carbone carbono alloy aluminium aluminum alu tubeless tubular clincher tle tl cl centerlock center centre lock 6-bolt 6 bolt 700c 700 28 29 27.5 650b 26 zoll inch mm thru axle ta qr shimano sram hg xdr xd 11s 12s 11 12 speed road gravel mtb new with and for the front rear tyres tires tyre tire freehub hub hubs body only".split()
)
WBR = {"1430": "disc", "1431": "rim"}
WMAT = {"1433": "carbon", "1432": "aluminium", "1434": "steel"}
WSYS = {"1435": "tubeless", "1436": "tubular", "1437": "clincher"}


def model_key(kind, name, brand):
    b = brand.lower()
    n = " " + name.lower() + " "
    for w in b.split():
        n = re.sub(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", " ", n)
    n = re.sub(r"\b(19|20)\d\d\b", " ", n)
    n = re.sub(r"(\d+)\s*mm\b", r"\1", n)
    toks = [w for w in re.findall(r"[a-z0-9.+-]+", n) if w not in (STOPW if kind == "wheels" else STOPB) and w.strip(".-+")]
    return " ".join(toks[: 3 if kind == "wheels" else 2])


def annotate(row: dict, kind: str) -> bool:
    """Attach model-key fields. Return False for wheel rows the dashboard skips."""
    spec = json.loads(row["spec"] or "{}")
    details = spec.get("spec") or {}
    if kind == "wheels" and details.get("wheel-type") not in ("1372", None):
        return False
    row["mk"] = model_key(kind, row["name"], row["brand"])
    row["bk"] = row["brand"].lower()
    row["brake"] = WBR.get(details.get("complete-wheels-brakes-type"), "") if kind == "wheels" else ""
    row["mat"] = WMAT.get(details.get("rim-material"), "") if kind == "wheels" else ""
    row["wsys"] = WSYS.get(details.get("wheel-system"), "") if kind == "wheels" else ""
    row["cat"] = spec.get("cat") or ""
    row["comp"] = spec.get("comp") or ""
    return True


def _same_cohort(kind: str, row: dict, other: dict) -> bool:
    if other["id"] == row["id"]:
        return False
    if kind == "wheels" or row["year"] is None or other["year"] is None:
        return True
    return abs(other["year"] - row["year"]) <= 1


def comparable_listings(listings: list, kind: str) -> dict:
    """Map each listing id to the other live listings that form its reference cohort."""
    groups = collections.defaultdict(list)
    for row in listings:
        if not row["gone_at"] and row["mk"]:
            groups[(row["bk"], row["mk"], row["brake"], row["mat"])].append(row)
    out = {}
    for row in listings:
        group = groups.get((row["bk"], row["mk"], row["brake"], row["mat"]), [])
        out[row["id"]] = [other for other in group if _same_cohort(kind, row, other)]
    return out

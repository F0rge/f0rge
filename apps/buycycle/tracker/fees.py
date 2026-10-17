"""Dashboard resale-cost assumptions. One config for the dashboards, alerts, and MCP.

Numbers are the Cost assumptions tab defaults (buycycle EU fee page, checked 17 Oct 2026).
The formula matches the dashboard calc():

    sale = reference * (1 - haircut/100)
    cost = price * (1 + bp/100) + bpf + price * pay/100 + shipin + pack + repair + buffer
    net  = sale * (1 - sellfee/100) - shipout - relist - cost
    roi  = net / cost * 100

Net margin is an estimate: the expected resale is the comps median minus the haircut.
"""

from __future__ import annotations

from typing import Optional

# Key order is the dashboard Cost assumptions form.
ASSUMPTIONS = {
    "bikes": {
        "bp": 2.5,
        "bpf": 0,
        "pay": 0,
        "shipin": 125,
        "pack": 0,
        "repair": 50,
        "buffer": 75,
        "haircut": 5,
        "sellfee": 6.95,
        "shipout": 0,
        "relist": 0,
    },
    "wheels": {
        "bp": 6,
        "bpf": 1,
        "pay": 0,
        "shipin": 25,
        "pack": 10,
        "repair": 0,
        "buffer": 20,
        "haircut": 5,
        "sellfee": 0,
        "shipout": 0,
        "relist": 0,
    },
}


def estimate_net_margin(kind: str, price: float, reference: Optional[float]) -> Optional[dict]:
    """Estimated net profit and ROI for a listing, or None when there is no reference price.

    The returned dict always includes margin_label "estimate". Amounts are unrounded;
    callers round for display.
    """
    if reference is None:
        return None
    costs = ASSUMPTIONS[kind]
    sale = reference * (1 - costs["haircut"] / 100.0)
    cost = price * (1 + costs["bp"] / 100.0) + costs["bpf"] + price * costs["pay"] / 100.0 + costs["shipin"] + costs["pack"] + costs["repair"] + costs["buffer"]
    net = sale * (1 - costs["sellfee"] / 100.0) - costs["shipout"] - costs["relist"] - cost
    roi = (net / cost * 100.0) if cost else None
    return {
        "net_margin_eur": net,
        "roi_pct": roi,
        "margin_label": "estimate",
        "reference_eur": reference,
    }

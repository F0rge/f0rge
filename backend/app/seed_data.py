from __future__ import annotations

# Default catalog rows shared by migration 009 (which inserts them) and the
# test fixture (which needs the same rows on a create_all-built test DB,
# since testcontainers never runs the migration chain). Plain data — no ORM
# imports here, so migrations can import this module without binding to a
# model definition that might drift.

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

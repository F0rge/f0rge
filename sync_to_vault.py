"""
Sync health-tracker entries from the Pi API to the local Obsidian vault.
Runs on Mac, pulls data from the Pi, writes markdown + photos to the vault.

Usage:
    python3 sync_to_vault.py                  # sync all entries
    python3 sync_to_vault.py --date 2026-03-31  # sync a specific date
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

API_BASE = os.getenv("HEALTH_TRACKER_API", "https://health.leo-figueiredo.com/api/v1")
VAULT_PATH = os.getenv(
    "VAULT_PATH",
    os.path.expanduser(
        "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Brain"
    ),
)
PIN = os.getenv("HEALTH_TRACKER_PIN", "1234")

OVERALL_LABELS = {1: "Very Poor", 2: "Standard", 3: "Very Good"}
BLOATING_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}
JOINT_PAIN_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}
NEURO_LABELS = {-1: "Worse than usual", 0: "Baseline", 1: "Better than usual"}
SLEEP_LABELS = {1: "Poor", 2: "OK", 3: "Good"}
STRESS_LABELS = {1: "Low", 2: "Medium", 3: "High"}
SUPPLEMENT_LABELS = {
    "nac": "NAC",
    "fish_oil": "Fish Oil",
    "magnesium": "Magnesium",
    "beef_organs": "Beef Organs",
    "allicin": "Allicin",
    "oregano": "Oregano Oil",
    "vitamin_d_k2": "Vitamin D+K2",
    "dao": "DAO Enzyme",
    "creatine": "Creatine",
}


class HealthTrackerSync:
    def __init__(self):
        self.session_cookie = None
        self.logs_dir = Path(VAULT_PATH) / "Daily" / "Health-Logs"
        self.attachments_dir = Path(VAULT_PATH) / "attachments"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

    def _request(self, path: str, method: str = "GET", data: Optional[dict] = None) -> dict:
        url = f"{API_BASE}{path}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "HealthTrackerSync/1.0",
        }
        if self.session_cookie:
            headers["Cookie"] = self.session_cookie

        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)

        try:
            resp = urlopen(req)
            cookie = resp.headers.get("Set-Cookie")
            if cookie and "ht_session" in cookie:
                self.session_cookie = cookie.split(";")[0]
            return json.loads(resp.read().decode())
        except URLError as e:
            print(f"  API error: {e}")
            sys.exit(1)

    def _download(self, path: str, dest: Path) -> None:
        url = f"{API_BASE}{path}"
        headers = {"User-Agent": "HealthTrackerSync/1.0"}
        if self.session_cookie:
            headers["Cookie"] = self.session_cookie
        req = Request(url, headers=headers)
        try:
            resp = urlopen(req)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(resp.read())
        except URLError as e:
            print(f"  Photo download error: {e}")

    def login(self):
        result = self._request("/auth/login", method="POST", data={"pin": PIN})
        if not result.get("authenticated"):
            print("Login failed")
            sys.exit(1)
        print("Logged in to health-tracker API")

    def get_entries(self, month: Optional[str] = None) -> list:
        path = "/entries"
        if month:
            path += f"?month={month}"
        return self._request(path)

    def get_entry(self, date: str) -> Optional[dict]:
        try:
            return self._request(f"/entries/{date}")
        except SystemExit:
            return None

    def get_weather(self, date: str) -> Optional[dict]:
        try:
            result = self._request_safe(f"/weather/{date}")
            return result
        except Exception:
            return None

    def get_health_metrics(self, date: str) -> Optional[dict]:
        try:
            result = self._request_safe(f"/health-metrics/{date}")
            return result
        except Exception:
            return None

    def _request_safe(self, path: str) -> Optional[dict]:
        """Like _request but returns None on 404 instead of exiting."""
        url = f"{API_BASE}{path}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "HealthTrackerSync/1.0",
        }
        if self.session_cookie:
            headers["Cookie"] = self.session_cookie
        req = Request(url, headers=headers, method="GET")
        try:
            resp = urlopen(req)
            return json.loads(resp.read().decode())
        except URLError:
            return None

    def format_supplements(self, supplements_str: str) -> str:
        if not supplements_str:
            return "None"
        taken = [s.strip() for s in supplements_str.split(",") if s.strip()]
        labels = [SUPPLEMENT_LABELS.get(s, s) for s in taken]
        return ", ".join(labels) if labels else "None"

    def render_markdown(self, entry: dict, weather: Optional[dict] = None, health: Optional[dict] = None) -> str:
        date_str = entry["date"]
        stool_str = "true" if entry["stool_normal"] else "false"
        sick_str = "true" if entry["sick"] else "false"
        photos = entry.get("photos", [])

        lines = [
            "---",
            "created-by: health-tracker",
            f"created: {date_str}",
            "modified-by: health-tracker",
            f"modified: {datetime.utcnow().strftime('%Y-%m-%d')}",
            "tags:",
            "  - daily-check-in",
            "  - symptom-log",
            f"overall: {entry['overall']}",
            f"bloating: {entry['bloating']}",
            f"stool-normal: {stool_str}",
            f"stool-type: {entry.get('stool_type', '') or ''}",
            f"joint-pain: {entry['joint_pain']}",
            f"neuro: {entry['neuro']}",
            f"sleep-quality: {entry['sleep_quality']}",
            f"stress: {entry['stress']}",
            f"diet-risk: {entry['diet_risk']}",
            f"supplements: {entry['supplements']}",
            f"sick: {sick_str}",
            "---",
            "",
            f"# Daily Check-in: {date_str}",
            "",
            "## Summary",
            "",
            "| Category | Value |",
            "|----------|-------|",
            f"| Overall day | {OVERALL_LABELS.get(entry['overall'], str(entry['overall']))} ({entry['overall']}/3) |",
            f"| Bloating | {BLOATING_LABELS.get(entry['bloating'], str(entry['bloating']))} |",
            f"| Stool | {'Normal' if entry['stool_normal'] else 'Abnormal' + (' (' + entry.get('stool_type', '') + ')' if entry.get('stool_type') else '')} |",
            f"| Joint pain | {JOINT_PAIN_LABELS.get(entry['joint_pain'], str(entry['joint_pain']))} |",
            f"| Neuro | {NEURO_LABELS.get(entry['neuro'], str(entry['neuro']))} |",
            f"| Sleep quality | {SLEEP_LABELS.get(entry['sleep_quality'], str(entry['sleep_quality']))} |",
            f"| Stress | {STRESS_LABELS.get(entry['stress'], str(entry['stress']))} |",
            f"| Diet risk | {entry['diet_risk']} |",
            f"| Supplements | {self.format_supplements(entry['supplements'])} |",
            f"| Sick | {sick_str} |",
            "",
            "## Notes",
            "",
            entry["notes"] if entry.get("notes") else "No notes recorded.",
            "",
        ]

        if photos:
            lines.append("## Photos")
            lines.append("")
            for photo in photos:
                lines.append(f"![[attachments/{photo['filename']}]]")
                if photo.get("label"):
                    lines.append(f"*{photo['label']}*")
                lines.append("")

        if health:
            lines.append("## Apple Watch Data")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            if health.get("hrv_mean") is not None:
                lines.append(f"| HRV | {health['hrv_mean']} ms (std {health.get('hrv_std', 'N/A')}) |")
            if health.get("resting_hr") is not None:
                lines.append(f"| Resting HR | {health['resting_hr']} bpm |")
            if health.get("sleep_hours") is not None:
                lines.append(f"| Sleep | {health['sleep_hours']} hours |")
            if health.get("sleep_deep_min") is not None:
                lines.append(f"| Deep sleep | {health['sleep_deep_min']} min ({health.get('sleep_deep_pct', 'N/A')}%) |")
            if health.get("sleep_rem_min") is not None:
                lines.append(f"| REM sleep | {health['sleep_rem_min']} min ({health.get('sleep_rem_pct', 'N/A')}%) |")
            if health.get("sleep_core_min") is not None:
                lines.append(f"| Core sleep | {health['sleep_core_min']} min |")
            if health.get("sleep_awake_min") is not None:
                lines.append(f"| Awake in bed | {health['sleep_awake_min']} min |")
            if health.get("sleep_efficiency") is not None:
                lines.append(f"| Sleep efficiency | {health['sleep_efficiency']}% |")
            if health.get("sleep_start"):
                lines.append(f"| Bedtime | {health['sleep_start']} |")
            if health.get("sleep_end"):
                lines.append(f"| Wake time | {health['sleep_end']} |")
            if health.get("steps") is not None:
                lines.append(f"| Steps | {health['steps']} |")
            if health.get("spo2") is not None:
                lines.append(f"| SpO2 | {health['spo2']}% |")
            if health.get("active_minutes") is not None:
                lines.append(f"| Active energy | {health['active_minutes']} kcal |")
            lines.append("")

        if weather:
            lines.append("## Weather (Luxembourg)")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Temperature | {weather.get('temp_min', 'N/A')} - {weather.get('temp_max', 'N/A')} C (mean {weather.get('temp_mean', 'N/A')}) |")
            lines.append(f"| Pressure | {weather.get('pressure_mean', 'N/A')} hPa |")
            if weather.get("pressure_delta_24h") is not None:
                lines.append(f"| Pressure delta (24h) | {weather['pressure_delta_24h']} hPa |")
            lines.append(f"| Humidity | {weather.get('humidity_mean', 'N/A')}% |")
            lines.append(f"| Readings | {weather.get('reading_count', 0)} |")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(
            "[[Projects/Health-Diagnostic/Symptoms-Master]] | "
            "[[Projects/Health-Diagnostic/CURRENT-HYPOTHESIS]]"
        )
        lines.append("")
        lines.append("---")
        lines.append("*Logged via health-tracker*")
        lines.append("")

        return "\n".join(lines)

    def sync_entry(self, entry: dict) -> bool:
        date_str = entry["date"]
        md_path = self.logs_dir / f"{date_str}.md"
        photos = entry.get("photos", [])

        # Fetch enrichment data
        weather = self.get_weather(date_str)
        health = self.get_health_metrics(date_str)

        # Render markdown
        content = self.render_markdown(entry, weather=weather, health=health)

        # Check if file needs updating
        if md_path.exists():
            existing = md_path.read_text(encoding="utf-8")
            # Compare content ignoring the modified date line (changes every sync)
            existing_hash = hashlib.md5(
                "\n".join(l for l in existing.splitlines() if not l.startswith("modified:")).encode()
            ).hexdigest()
            new_hash = hashlib.md5(
                "\n".join(l for l in content.splitlines() if not l.startswith("modified:")).encode()
            ).hexdigest()
            if existing_hash == new_hash:
                return False  # No changes

        # Write atomically
        fd, tmp_path = tempfile.mkstemp(dir=str(self.logs_dir), suffix=".md.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(md_path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        # Sync photos
        for photo in photos:
            photo_path = self.attachments_dir / photo["filename"]
            if not photo_path.exists():
                print(f"  Downloading photo: {photo['filename']}")
                self._download(f"/photos/{photo['id']}/file", photo_path)

        return True

    def sync_all(self):
        # Get all entries (fetch recent months)
        all_entries = []
        now = datetime.utcnow()
        for months_back in range(12):  # Last 12 months
            year = now.year
            month = now.month - months_back
            while month <= 0:
                month += 12
                year -= 1
            month_str = f"{year}-{month:02d}"
            entries = self.get_entries(month=month_str)
            if entries:
                all_entries.extend(entries)
            if not entries and months_back > 1:
                break  # No more data

        if not all_entries:
            print("No entries found")
            return

        print(f"Found {len(all_entries)} entries")
        updated = 0
        for entry in all_entries:
            if self.sync_entry(entry):
                print(f"  Synced: {entry['date']}")
                updated += 1

        print(f"Done. {updated} files updated, {len(all_entries) - updated} unchanged.")

    def sync_date(self, date: str):
        entry = self.get_entry(date)
        if not entry:
            print(f"No entry for {date}")
            return
        if self.sync_entry(entry):
            print(f"Synced: {date}")
        else:
            print(f"No changes: {date}")


def main():
    parser = argparse.ArgumentParser(description="Sync health-tracker to Obsidian vault")
    parser.add_argument("--date", help="Sync a specific date (YYYY-MM-DD)")
    args = parser.parse_args()

    sync = HealthTrackerSync()
    sync.login()

    if args.date:
        sync.sync_date(args.date)
    else:
        sync.sync_all()


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EntityResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str, n: int = 1) -> None:
        self.skipped += n
        self.reasons[reason] = self.reasons.get(reason, 0) + n

    def note(self, reason: str, n: int = 1) -> None:
        """Record a fact that is not a skipped row."""
        self.reasons[reason] = self.reasons.get(reason, 0) + n

    @property
    def migrated(self) -> int:
        return self.created + self.updated + self.unchanged


@dataclass
class ImportReport:
    dry_run: bool
    entities: dict[str, EntityResult] = field(default_factory=dict)
    filled_down: dict[str, int] = field(default_factory=dict)
    customer_rows_realigned: int = 0
    supplier_rows_realigned: int = 0
    assumptions: list[str] = field(default_factory=list)
    price_changes: dict[str, int] = field(default_factory=dict)
    warnings: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    barcode_replacements: list[dict[str, str]] = field(default_factory=list)

    def entity(self, name: str) -> EntityResult:
        if name not in self.entities:
            self.entities[name] = EntityResult()
        return self.entities[name]


def format_report(report: ImportReport) -> str:
    mode = "dry-run" if report.dry_run else "committed"
    lines = [
        f"Cin7 import ({mode})",
        "",
        f"{'entity':<24} {'migrated':>10} {'created':>10} {'updated':>10} "
        f"{'unchanged':>10} {'skipped':>10}",
    ]
    for name, result in report.entities.items():
        lines.append(
            f"{name:<24} {result.migrated:>10} {result.created:>10} {result.updated:>10} "
            f"{result.unchanged:>10} {result.skipped:>10}"
        )
        for reason, count in result.reasons.items():
            lines.append(f"  {count} {reason}")
    if report.filled_down:
        lines.append("")
        lines.append("blank SKU/name cells carried down")
        for name, count in report.filled_down.items():
            lines.append(f"  {name}: {count}")
    lines.append("")
    lines.append(
        f"customer rows realigned: {report.customer_rows_realigned}; "
        f"supplier rows realigned: {report.supplier_rows_realigned}"
    )
    if report.price_changes:
        lines.append("")
        lines.append("price changes")
        for tier, count in report.price_changes.items():
            lines.append(f"  {tier}: {count}")
    if report.warnings or report.errors:
        lines.append("")
        lines.append(f"warnings: {len(report.warnings)}; errors: {len(report.errors)}")
    if report.assumptions:
        lines.append("")
        lines.append("assumptions")
        for item in report.assumptions:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"

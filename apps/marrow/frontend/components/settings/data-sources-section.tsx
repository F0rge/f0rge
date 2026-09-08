// Static info card — no icon in header, no state, no mutations.
export function DataSourcesSection() {
  return (
    <div className="rounded-xl border border-border p-4 space-y-2">
      <h2 className="font-semibold">Data Sources</h2>
      <ul className="space-y-1 text-sm text-muted-foreground">
        <li>Weather: one Open-Meteo snapshot when a check-in lands</li>
        <li>Health data: CSV or JSON import in Settings (Apple Health on iPhone later)</li>
        <li>Check-in: manual daily entry</li>
      </ul>
    </div>
  )
}

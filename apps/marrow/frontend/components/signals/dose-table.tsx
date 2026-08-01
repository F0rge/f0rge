import type { DoseBin } from '@/lib/api/types/signals'

interface Props {
  rows: DoseBin[]
}

export function DoseTable({ rows }: Props) {
  if (rows.length === 0) {
    return <p className="text-xs text-muted-foreground">No dose bins.</p>
  }

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-left text-muted-foreground">
          <th className="pb-1 font-medium">Dose</th>
          <th className="pb-1 font-medium">n</th>
          <th className="pb-1 font-medium">Mean</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label} className="border-t border-border/50">
            <td className="py-1">{row.label}</td>
            <td className="py-1 tabular-nums">{row.n}</td>
            <td className="py-1 tabular-nums">
              {row.mean != null ? row.mean.toFixed(2) : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

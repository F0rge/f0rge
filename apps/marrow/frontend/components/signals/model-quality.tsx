import type { SignalsModel } from '@/lib/api/types/signals'

interface Props {
  model: SignalsModel
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold tabular-nums">{value}</p>
    </div>
  )
}

export function ModelQuality({ model }: Props) {
  const skill =
    model.skill != null ? `${(model.skill * 100).toFixed(0)}%` : '—'
  const mae = model.mae != null ? model.mae.toFixed(2) : '—'
  const noise =
    model.noise_floor_mae != null ? model.noise_floor_mae.toFixed(2) : '—'

  return (
    <section aria-label="Model quality">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Model
      </h2>
      <div className="rounded-xl bg-card p-3 ring-1 ring-foreground/10">
        {model.relearning && model.relearning_message ? (
          <p className="mb-3 text-xs text-amber-600 dark:text-amber-400">
            {model.relearning_message}
          </p>
        ) : null}
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Skill" value={skill} />
          <Stat label="MAE" value={mae} />
          <Stat label="Noise floor" value={noise} />
        </div>
      </div>
    </section>
  )
}

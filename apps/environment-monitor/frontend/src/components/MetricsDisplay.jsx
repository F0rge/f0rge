import React from 'react';
import {
  COMFORT_HUMIDITY_MAX,
  COMFORT_HUMIDITY_MIN,
  COMFORT_TEMP_MAX,
  COMFORT_TEMP_MIN,
} from '../comfort';
import {
  FAR_BEYOND_HUMIDITY_PCT,
  FAR_BEYOND_TEMP_C,
  HUMIDITY_SCALE_PAD,
  TEMP_SCALE_PAD,
  layoutMetricBar,
} from '../range-bar';

function edgeLabel(value, unit) {
  const n = Number.isInteger(value) ? String(value) : value.toFixed(1);
  return unit === '°C' ? `${n}°` : `${n}%`;
}

function RangeBar({
  min, max, average, comfortMin, comfortMax, far, pad, unit,
}) {
  const layout = layoutMetricBar({
    min, max, average, comfortMin, comfortMax, far, pad,
  });
  const unitText = unit === '°C' ? '°C' : '%';
  const title = `${min.toFixed(1)}–${max.toFixed(1)}${unitText}, average ${average.toFixed(1)}${unitText}. Comfort ${comfortMin}–${comfortMax}${unitText}. Amber within ${far}${unitText} of the band, red beyond.`;

  return (
    <div className="range-bar" role="img" aria-label={title} title={title}>
      <div className="range-track" aria-hidden="true">
        <div
          className="range-band"
          style={{ left: `${layout.bandLeft}%`, width: `${layout.bandWidth}%` }}
        />
        {layout.pieces.map((piece) => (
          <div
            key={`${piece.tone}-${piece.left}`}
            className={`range-fill range-fill--${piece.tone}`}
            style={{ left: `${piece.left}%`, width: `${piece.width}%` }}
          />
        ))}
      </div>
      <div
        className="range-mark"
        style={{ left: `${layout.averageLeft}%` }}
        aria-hidden="true"
      />
      <span className="range-edge" style={{ left: `${layout.bandLeft}%` }} aria-hidden="true">
        {edgeLabel(comfortMin, unit)}
      </span>
      <span
        className="range-edge"
        style={{ left: `${layout.bandLeft + layout.bandWidth}%` }}
        aria-hidden="true"
      >
        {edgeLabel(comfortMax, unit)}
      </span>
    </div>
  );
}

function ComfortBar({ percent }) {
  const shown = Math.min(100, Math.max(0, Number(percent.toFixed(0))));
  const title = `${shown}% of readings inside ${COMFORT_TEMP_MIN}–${COMFORT_TEMP_MAX}°C and ${COMFORT_HUMIDITY_MIN}–${COMFORT_HUMIDITY_MAX}%`;
  return (
    <div className="range-bar range-bar--comfort" role="img" aria-label={title} title={title}>
      <div className="range-track" aria-hidden="true">
        <div className="range-fill range-fill--success" style={{ left: 0, width: `${shown}%` }} />
      </div>
    </div>
  );
}

function trendLabel(trend) {
  if (trend === 'rising') return 'Rising';
  if (trend === 'falling') return 'Falling';
  return 'Stable';
}

function MetricsDisplay({ metrics }) {
  return (
    <div className="d-flex flex-wrap gutter-condensed mt-3">
      <div className="col-12 col-md-4 mb-2">
        <div className="f6 color-fg-muted text-bold">Average</div>
        <div className="f3 metrics-value">{metrics.temperature_average.toFixed(1)}<span className="f5 color-fg-muted">°C</span></div>
        <div className="f6 color-fg-muted text-mono mt-1">
          Min {metrics.temperature_min.toFixed(1)}° · Max {metrics.temperature_max.toFixed(1)}°
        </div>
        <RangeBar
          min={metrics.temperature_min}
          max={metrics.temperature_max}
          average={metrics.temperature_average}
          comfortMin={COMFORT_TEMP_MIN}
          comfortMax={COMFORT_TEMP_MAX}
          far={FAR_BEYOND_TEMP_C}
          pad={TEMP_SCALE_PAD}
          unit="°C"
        />
        <div className="f6 color-fg-muted text-mono mt-1">σ ±{metrics.temperature_std_dev.toFixed(2)}° · {trendLabel(metrics.temperature_trend)}</div>
      </div>

      <div className="col-12 col-md-4 mb-2">
        <div className="f6 color-fg-muted text-bold">Average</div>
        <div className="f3 metrics-value">{metrics.humidity_average.toFixed(1)}<span className="f5 color-fg-muted">%</span></div>
        <div className="f6 color-fg-muted text-mono mt-1">
          Min {metrics.humidity_min.toFixed(1)}% · Max {metrics.humidity_max.toFixed(1)}%
        </div>
        <RangeBar
          min={metrics.humidity_min}
          max={metrics.humidity_max}
          average={metrics.humidity_average}
          comfortMin={COMFORT_HUMIDITY_MIN}
          comfortMax={COMFORT_HUMIDITY_MAX}
          far={FAR_BEYOND_HUMIDITY_PCT}
          pad={HUMIDITY_SCALE_PAD}
          unit="%"
        />
        <div className="f6 color-fg-muted text-mono mt-1">σ ±{metrics.humidity_std_dev.toFixed(2)}% · {trendLabel(metrics.humidity_trend)}</div>
      </div>

      <div className="col-12 col-md-4 mb-2">
        <div className="f6 color-fg-muted text-bold">Comfort</div>
        <div className="f3 metrics-value color-fg-success">{metrics.time_in_optimal_range.toFixed(0)}<span className="f5 color-fg-muted">%</span></div>
        <ComfortBar percent={metrics.time_in_optimal_range} />
        <div className="f6 color-fg-muted text-mono mt-1">in both bands</div>
        <div className="f6 color-fg-muted text-mono">{metrics.data_points.toLocaleString()} data points</div>
      </div>
    </div>
  );
}

export default MetricsDisplay;

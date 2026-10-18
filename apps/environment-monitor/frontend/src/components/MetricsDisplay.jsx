import React from 'react';

const clamp = (v) => Math.min(100, Math.max(0, v));

function Range({ left, width, tone }) {
  return (
    <span className="Progress Progress--small" aria-hidden="true">
      <span
        className={`Progress-item color-bg-${tone}-emphasis`}
        style={{ width: `${width}%`, marginLeft: `${left}%`, flex: 'none' }}
      />
    </span>
  );
}

function MetricsDisplay({ metrics }) {
  const tempLeft = clamp(((metrics.temperature_min - 15) / 20) * 100);
  const tempRight = clamp(((metrics.temperature_max - 15) / 20) * 100);
  const tempWidth = Math.max(0, tempRight - tempLeft);
  const humLeft = clamp(((metrics.humidity_min - 20) / 60) * 100);
  const humRight = clamp(((metrics.humidity_max - 20) / 60) * 100);
  const humWidth = Math.max(0, humRight - humLeft);
  const tempTrend = metrics.temperature_trend === 'rising' ? 'Rising' : metrics.temperature_trend === 'falling' ? 'Falling' : 'Stable';
  const humTrend = metrics.humidity_trend === 'rising' ? 'Rising' : metrics.humidity_trend === 'falling' ? 'Falling' : 'Stable';

  return (
    <div className="d-flex flex-wrap gutter-condensed mt-3">
      <div className="col-12 col-md-4 mb-2">
        <div className="f6 color-fg-muted text-bold">Average</div>
        <div className="f3 metrics-value">{metrics.temperature_average.toFixed(1)}<span className="f5 color-fg-muted">°C</span></div>
        <div className="f6 color-fg-muted text-mono mt-1">
          Min {metrics.temperature_min.toFixed(1)}° · Max {metrics.temperature_max.toFixed(1)}°
        </div>
        <Range left={tempLeft} width={tempWidth} tone="success" />
        <div className="f6 color-fg-muted text-mono mt-1">σ ±{metrics.temperature_std_dev.toFixed(2)}° · {tempTrend}</div>
      </div>

      <div className="col-12 col-md-4 mb-2">
        <div className="f6 color-fg-muted text-bold">Average</div>
        <div className="f3 metrics-value">{metrics.humidity_average.toFixed(1)}<span className="f5 color-fg-muted">%</span></div>
        <div className="f6 color-fg-muted text-mono mt-1">
          Min {metrics.humidity_min.toFixed(1)}% · Max {metrics.humidity_max.toFixed(1)}%
        </div>
        <Range left={humLeft} width={humWidth} tone="accent" />
        <div className="f6 color-fg-muted text-mono mt-1">σ ±{metrics.humidity_std_dev.toFixed(2)}% · {humTrend}</div>
      </div>

      <div className="col-12 col-md-4 mb-2">
        <div className="f6 color-fg-muted text-bold">Comfort</div>
        <div className="f3 metrics-value color-fg-success">{metrics.time_in_optimal_range.toFixed(0)}<span className="f5 color-fg-muted">%</span></div>
        <div className="f6 color-fg-muted text-mono mt-1">{metrics.data_points.toLocaleString()} data points</div>
      </div>
    </div>
  );
}

export default MetricsDisplay;

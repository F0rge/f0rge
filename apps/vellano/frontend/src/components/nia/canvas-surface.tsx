"use client";

import { Tile } from "@carbon/react";

import { NiaSpreadsheet } from "@/components/nia/nia-spreadsheet";
import type {
  CanvasBarLineComponent,
  CanvasComponent,
  CanvasSpec,
} from "@/lib/nia-canvas-types";

const CHART_COLORS = [
  "var(--cds-support-info)",
  "var(--cds-support-success)",
  "var(--cds-support-warning)",
  "var(--cds-support-error)",
  "var(--cds-link-primary)",
];

function formatChartNumber(value: number): string {
  return value.toLocaleString("en-ZA", { maximumFractionDigits: 2 });
}

function validSeries(component: CanvasBarLineComponent) {
  return component.series.filter(
    (entry) => entry.values.length === component.categories.length,
  );
}

function BarChart({ component }: { component: CanvasBarLineComponent }) {
  const series = validSeries(component);
  if (series.length === 0 || component.categories.length === 0) {
    return null;
  }

  const maxValue = Math.max(
    ...series.flatMap((entry) => entry.values),
    1,
  );

  return (
    <div className="vellano-canvas-chart">
      <p className="cds--type-heading-compact-01">{component.title}</p>
      <div className="vellano-canvas-chart__legend">
        {series.map((entry, index) => (
          <span key={entry.name} className="vellano-canvas-chart__legend-item">
            <span
              className="vellano-canvas-chart__swatch"
              style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
            />
            {entry.name}
          </span>
        ))}
      </div>
      <div className="vellano-canvas-chart__bars">
        {component.categories.map((category, categoryIndex) => (
          <div key={`${component.id}-${category}`} className="vellano-canvas-chart__group">
            <p className="vellano-canvas-chart__category">{category}</p>
            {series.map((entry, seriesIndex) => {
              const value = entry.values[categoryIndex] ?? 0;
              const widthPct = Math.max(0, (value / maxValue) * 100);
              return (
                <div key={`${entry.name}-${category}`} className="vellano-canvas-chart__bar-row">
                  <span className="vellano-canvas-chart__bar-label">{entry.name}</span>
                  <div className="vellano-canvas-chart__bar-track">
                    <div
                      className="vellano-canvas-chart__bar-fill"
                      style={{
                        width: `${widthPct}%`,
                        backgroundColor: CHART_COLORS[seriesIndex % CHART_COLORS.length],
                      }}
                    />
                  </div>
                  <span className="vellano-canvas-chart__bar-value">{formatChartNumber(value)}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function LineChart({ component }: { component: CanvasBarLineComponent }) {
  const series = validSeries(component);
  if (series.length === 0 || component.categories.length === 0) {
    return null;
  }

  const width = 640;
  const height = 220;
  const padding = { top: 16, right: 16, bottom: 32, left: 16 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(...series.flatMap((entry) => entry.values), 1);
  const pointCount = component.categories.length;
  const xStep = pointCount > 1 ? plotWidth / (pointCount - 1) : 0;

  return (
    <div className="vellano-canvas-chart">
      <p className="cds--type-heading-compact-01">{component.title}</p>
      <div className="vellano-canvas-chart__legend">
        {series.map((entry, index) => (
          <span key={entry.name} className="vellano-canvas-chart__legend-item">
            <span
              className="vellano-canvas-chart__swatch"
              style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
            />
            {entry.name}
          </span>
        ))}
      </div>
      <svg
        className="vellano-canvas-chart__line-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={component.title}
      >
        {series.map((entry, seriesIndex) => {
          const points = entry.values
            .map((value, index) => {
              const x = padding.left + index * xStep;
              const y = padding.top + plotHeight - (value / maxValue) * plotHeight;
              return `${x},${y}`;
            })
            .join(" ");
          return (
            <polyline
              key={entry.name}
              fill="none"
              stroke={CHART_COLORS[seriesIndex % CHART_COLORS.length]}
              strokeWidth={2}
              points={points}
            />
          );
        })}
      </svg>
      <div className="vellano-canvas-chart__axis">
        {component.categories.map((category) => (
          <span key={category} className="vellano-canvas-chart__axis-label">
            {category}
          </span>
        ))}
      </div>
    </div>
  );
}

function TableChart({ component }: { component: Extract<CanvasComponent, { type: "table" }> }) {
  return (
    <div className="vellano-canvas-chart">
      <NiaSpreadsheet
        title={component.title}
        headers={component.headers}
        rows={component.rows}
        readOnly
      />
    </div>
  );
}

function MetricTile({ component }: { component: Extract<CanvasComponent, { type: "metric" }> }) {
  return (
    <Tile className="vellano-canvas-metric">
      <p className="cds--type-label-01">{component.label}</p>
      <p className="vellano-canvas-metric__value">{component.value}</p>
    </Tile>
  );
}

function CanvasComponentView({ component }: { component: CanvasComponent }) {
  if (component.type === "bar") {
    return <BarChart component={component} />;
  }
  if (component.type === "line") {
    return <LineChart component={component} />;
  }
  if (component.type === "table") {
    return <TableChart component={component} />;
  }
  if (component.type === "metric") {
    return <MetricTile component={component} />;
  }
  return null;
}

type CanvasSurfaceProps = {
  spec: CanvasSpec;
};

export function CanvasSurface({ spec }: CanvasSurfaceProps) {
  return (
    <div className="vellano-canvas-surface">
      {spec.components.map((component) => (
        <section key={component.id} className="vellano-canvas-surface__block">
          <CanvasComponentView component={component} />
        </section>
      ))}
    </div>
  );
}

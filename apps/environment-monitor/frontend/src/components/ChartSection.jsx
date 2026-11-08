import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler, TimeScale
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import zoomPlugin from 'chartjs-plugin-zoom';
import MetricsDisplay from './MetricsDisplay';
import { inComfortZone } from '../comfort';

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler, TimeScale, zoomPlugin
);

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function mix(color, pct) {
  return `color-mix(in srgb, ${color} ${pct}%, transparent)`;
}

function useScheme() {
  const dark = () => window.matchMedia('(prefers-color-scheme: dark)').matches;
  const [scheme, setScheme] = useState(dark() ? 'dark' : 'light');
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setScheme(mq.matches ? 'dark' : 'light');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return scheme;
}

const comfortZonePlugin = {
  id: 'comfortZone',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    const labels = chart.data.labels;
    const temps = chart.data.datasets.find(d => d.label === 'Temp °C')?.data;
    const hums = chart.data.datasets.find(d => d.label === 'Humidity %')?.data;
    if (!labels || !temps || !hums || labels.length === 0) return;
    const inZone = i => inComfortZone(temps[i], hums[i]);
    ctx.save();
    ctx.fillStyle = mix(cssVar('--bgColor-success-emphasis') || '#1f883d', 16);
    let start = null;
    for (let i = 0; i < labels.length; i++) {
      if (inZone(i)) {
        if (start === null) start = i;
      } else if (start !== null) {
        const x1 = scales.x.getPixelForValue(labels[start]);
        const x2 = scales.x.getPixelForValue(labels[i - 1]);
        ctx.fillRect(x1, chartArea.top, Math.max(1, x2 - x1), chartArea.bottom - chartArea.top);
        start = null;
      }
    }
    if (start !== null) {
      const x1 = scales.x.getPixelForValue(labels[start]);
      const x2 = scales.x.getPixelForValue(labels[labels.length - 1]);
      ctx.fillRect(x1, chartArea.top, Math.max(1, x2 - x1), chartArea.bottom - chartArea.top);
    }
    ctx.restore();
  }
};

const crosshairPlugin = {
  id: 'crosshair',
  afterDatasetsDraw(chart) {
    const active = chart.tooltip?.getActiveElements?.();
    if (!active || active.length === 0) return;
    const { ctx, chartArea } = chart;
    const x = active[0].element.x;
    ctx.save();
    ctx.strokeStyle = mix(cssVar('--fgColor-muted') || '#656d76', 55);
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.stroke();
    ctx.restore();
  }
};

const CHART_PLUGINS = [crosshairPlugin, comfortZonePlugin];

// Order matters: index + 1 is the keyboard shortcut for each timeframe.
const TIMEFRAMES = [
  { id: '5m', label: '5M', title: '5 Minutes' },
  { id: '1h', label: '1H', title: '1 Hour' },
  { id: '6h', label: '6H', title: '6 Hours' },
  { id: '1d', label: '1D', title: '1 Day' },
  { id: '1w', label: '1W', title: '1 Week' },
  { id: 'ytd', label: 'YTD', title: 'Year to date' },
  { id: 'all', label: 'All', title: 'All data' }
];

function ChartSection({ historicalData, averageMetrics, currentRange, onTimeframeChange, loading, lastUpdate }) {
  const chartRef = useRef(null);
  const [zoomed, setZoomed] = useState(false);
  const scheme = useScheme();
  // useCallback so the keydown listener below subscribes once, not per render.
  const handleResetZoom = useCallback(() => { chartRef.current?.resetZoom(); setZoomed(false); }, []);

  // Range switch remounts <Line/> (loading branch), so just clear the stale flag.
  useEffect(() => {
    setZoomed(false);
  }, [currentRange]);

  // Desktop shortcuts: 1-7 pick a timeframe, R resets zoom, E exports CSV.
  useEffect(() => {
    const onKeyDown = (e) => {
      // Never shadow browser/OS chords — Cmd+R must still reload, Cmd+E etc.
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target;
      if (t?.isContentEditable || t?.tagName === 'INPUT' || t?.tagName === 'TEXTAREA') return;

      const tf = TIMEFRAMES[Number(e.key) - 1];
      if (tf) onTimeframeChange(tf.id);
      else if (e.key === 'r' || e.key === 'R') handleResetZoom();
      // Content-Disposition: attachment, so this downloads without navigating away.
      else if (e.key === 'e' || e.key === 'E') window.location.href = '/api/download-data';
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onTimeframeChange, handleResetZoom]);

  // Memoized so App's 3s/5s polling re-renders don't hand react-chartjs-2 fresh
  // data/options objects — that forced a full re-parse + update() every poll and
  // clobbered the zoom plugin's scale window.
  const chartData = useMemo(() => {
    const hasBands = historicalData.length > 0 && historicalData[0].temperature_min !== undefined;
    const temp = cssVar('--fgColor-success') || '#1a7f37';
    const hum = cssVar('--fgColor-accent') || '#0969da';

    const baseDatasets = [
      {
        label: 'Temp °C',
        data: historicalData.map(item => item.temperature),
        borderColor: temp,
        backgroundColor: mix(temp, 16),
        borderWidth: 2,
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 4,
        yAxisID: 'y'
      },
      {
        label: 'Humidity %',
        data: historicalData.map(item => item.humidity),
        borderColor: hum,
        backgroundColor: mix(hum, 14),
        borderWidth: 2,
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 4,
        yAxisID: 'y1'
      }
    ];

    const bandDatasets = hasBands ? [
      {
        label: 'Temp band',
        data: historicalData.map(item => item.temperature_max),
        borderColor: 'transparent',
        backgroundColor: mix(temp, 12),
        borderWidth: 0,
        fill: '+1',
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 0,
        yAxisID: 'y'
      },
      {
        label: 'Temp min',
        data: historicalData.map(item => item.temperature_min),
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        borderWidth: 0,
        fill: false,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 0,
        yAxisID: 'y'
      }
    ] : [];

    return {
      labels: historicalData.map(item => new Date(item.timestamp)),
      datasets: [...bandDatasets, ...baseDatasets]
    };
  }, [historicalData, scheme]);

  const chartOptions = useMemo(() => {
    const fg = cssVar('--fgColor-default') || '#1f2328';
    const muted = cssVar('--fgColor-muted') || '#656d76';
    const canvas = cssVar('--bgColor-default') || '#ffffff';
    const border = cssVar('--borderColor-muted') || '#d1d9e0';
    const accent = cssVar('--fgColor-accent') || '#0969da';
    const font = cssVar('--fontStack-system') || 'sans-serif';
    const mono = cssVar('--fontStack-monospace') || 'ui-monospace, monospace';
    return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        align: 'start',
        labels: {
          color: muted,
          font: { size: 11, weight: '500', family: font },
          usePointStyle: true,
          padding: 14,
          boxWidth: 6,
          boxHeight: 6,
          filter: (item) => item.text !== 'Temp band' && item.text !== 'Temp min'
        }
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: canvas,
        titleColor: fg,
        bodyColor: muted,
        borderColor: border,
        borderWidth: 1,
        cornerRadius: 6,
        padding: 12,
        titleFont: { size: 12, weight: '600', family: font },
        bodyFont: { size: 12, family: mono },
        filter: (item) => item.dataset.label !== 'Temp band' && item.dataset.label !== 'Temp min',
        callbacks: {
          title: ctx => new Date(ctx[0].parsed.x).toLocaleString(),
          label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}`
        }
      },
      zoom: {
        pan: { enabled: true, mode: 'x', modifierKey: 'shift', onPanComplete: () => setZoomed(true) },
        zoom: {
          drag: { enabled: true, backgroundColor: mix(accent, 16), borderColor: mix(accent, 55), borderWidth: 1 },
          wheel: { enabled: true, speed: 0.1 },
          pinch: { enabled: true },
          mode: 'x',
          onZoomComplete: () => setZoomed(true)
        },
        limits: { x: { minRange: 60000 } }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: { displayFormats: { minute: 'HH:mm', hour: 'HH:mm', day: 'MMM dd' } },
        grid: { color: border, drawBorder: false },
        border: { display: false },
        // 10 for the wide desktop canvas; autoSkip still drops what doesn't fit.
        ticks: { color: muted, font: { size: 10, family: font }, maxTicksLimit: 10 }
      },
      y: {
        type: 'linear', display: true, position: 'left',
        grid: { color: border, drawBorder: false },
        border: { display: false },
        ticks: { color: muted, font: { size: 10, family: font }, maxTicksLimit: 6, callback: v => v.toFixed(1) + '°' }
      },
      y1: {
        type: 'linear', display: true, position: 'right',
        grid: { drawOnChartArea: false },
        border: { display: false },
        ticks: { color: muted, font: { size: 10, family: font }, maxTicksLimit: 6, callback: v => v.toFixed(0) + '%' }
      }
    },
    interaction: { mode: 'nearest', axis: 'x', intersect: false },
    animation: { duration: 350, easing: 'easeOutCubic' }
  };
  }, [scheme]);

  const isEmpty = !loading && historicalData.length === 0;
  const firstReadingAt = lastUpdate
    ? new Date(lastUpdate).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <section className="Box chart">
      <div className="Box-header">
        <div className="d-flex flex-wrap flex-items-center flex-justify-between">
          <h2 className="Box-title mb-0">History</h2>
          <div className="d-flex flex-wrap flex-items-center">
            <ul className="SegmentedControl SegmentedControl--small timeframes" role="list" aria-label="Time range">
              {TIMEFRAMES.map((tf, i) => (
                <li
                  key={tf.id}
                  className={`SegmentedControl-item${currentRange === tf.id ? ' SegmentedControl-item--selected' : ''}`}
                  role="listitem"
                >
                  <button
                    type="button"
                    className="Button Button--invisible Button--small"
                    aria-current={currentRange === tf.id ? 'true' : 'false'}
                    title={`${tf.title} (press ${i + 1})`}
                    onClick={() => onTimeframeChange(tf.id)}
                  >
                    <span className="Button-content"><span className="Button-label">{tf.label}</span></span>
                  </button>
                </li>
              ))}
            </ul>
            {zoomed && (
              <button type="button" className="Button Button--secondary Button--small ml-2" title="Reset zoom (press R)" onClick={handleResetZoom}>
                <span className="Button-content"><span className="Button-label">Reset zoom</span></span>
              </button>
            )}
          </div>
        </div>
        <p className="f6 color-fg-muted mt-2 mb-0 d-none d-lg-block">Drag to zoom · Shift-drag to pan · Double-click to reset</p>
      </div>
      <div className="Box-body chart-body">
        <div className="chart-canvas" onDoubleClick={handleResetZoom}>
          {loading ? (
            <div className="chart-loading f6 color-fg-muted">Loading</div>
          ) : isEmpty ? (
            <div className="chart-empty">
              <span className="f5 text-semibold">No data yet</span>
              {firstReadingAt && (
                <span className="f6 color-fg-muted text-mono">First reading at {firstReadingAt}</span>
              )}
            </div>
          ) : (
            <Line ref={chartRef} data={chartData} options={chartOptions} plugins={CHART_PLUGINS} />
          )}
        </div>
        {averageMetrics && <MetricsDisplay metrics={averageMetrics} />}
      </div>
    </section>
  );
}

export default ChartSection;

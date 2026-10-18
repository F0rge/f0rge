import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';

const LIVE_POLL_MS = 3000; // matches App's /api/live-reading poll interval
const LIVE_TICK_MS = 20;

// Split one value into a composable pair: big = TRUNCATED to 1 decimal, small =
// decimals 2-3 FLOORED, so big+small always reads back as the value itself
// (27.9994 -> "27.9"+"99", 28.0006 -> "28.0"+"00", 27.95 -> "27.9"+"50", never
// rounded up). Integer thousandths + epsilon absorb float representation error.
const composeTemp = (v) => {
  const t = Math.floor(Math.abs(v) * 1000 + 1e-6);
  const big = (v < 0 ? '-' : '') + (Math.floor(t / 100) / 10).toFixed(1);
  return [big, String(t % 100).padStart(2, '0')];
};

// Display-only 50Hz ticker driving the WHOLE hero numeral (big part + two small
// digits) from one interpolated raw value: previous reading -> latest reading
// over the poll interval, written straight to textContent — React never
// re-renders on the 20ms tick.
// ponytail: no hysteresis; add a ±0.005 band if the big digit ever chatters at a .1 boundary
function LiveNumeral({ raw }) {
  const bigRef = useRef(null);
  const digitsRef = useRef(null);
  const anim = useRef({ from: raw, to: raw, t0: 0 });

  const writeNow = () => {
    const a = anim.current;
    const p = Math.min(1, (performance.now() - a.t0) / LIVE_POLL_MS);
    const [big, digits] = composeTemp(a.from + (a.to - a.from) * p);
    if (bigRef.current && bigRef.current.textContent !== big) bigRef.current.textContent = big;
    if (digitsRef.current && digitsRef.current.textContent !== digits) digitsRef.current.textContent = digits;
  };

  // Layout effect so the numeral is painted on mount — no empty-frame flash.
  useLayoutEffect(() => {
    const a = anim.current;
    const now = performance.now();
    const p = Math.min(1, (now - a.t0) / LIVE_POLL_MS);
    a.from = a.from + (a.to - a.from) * p; // continue from the displayed value, no jump
    a.to = raw;
    a.t0 = now;
    writeNow();
  }, [raw]);

  useEffect(() => {
    const id = setInterval(writeNow, LIVE_TICK_MS); // writeNow only touches refs — stable
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <span ref={bigRef} className="hero-temp" />
      <span
        ref={digitsRef}
        className="live-indicator"
        title="Live raw sensor reading (unsmoothed, not persisted)"
        aria-label="Live raw sensor reading"
      />
      <span className="hero-unit">°C</span>
    </>
  );
}

const moodLabel = {
  Extreme: 'danger',
  Hot: 'severe',
  Warm: 'attention',
  Mild: 'success',
  Cool: 'accent',
  Muggy: 'done',
  Dry: 'attention',
  Comfortable: 'success',
};

function SensorCard({
  temperature, humidity, liveTemperature, mood, feelsLike, dewPoint,
  connectionStatus, lastUpdate,
}) {
  const computeAgo = () => {
    if (!lastUpdate) return null;
    const secs = Math.floor((Date.now() - new Date(lastUpdate).getTime()) / 1000);
    if (secs < 5) return 'just now';
    if (secs < 60) return `${secs}s ago`;
    return `${Math.floor(secs / 60)}m ago`;
  };
  const [timeSinceUpdate, setTimeSinceUpdate] = useState(computeAgo);
  useEffect(() => {
    setTimeSinceUpdate(computeAgo());
    const id = setInterval(() => setTimeSinceUpdate(computeAgo()), 10000);
    return () => clearInterval(id);
  }, [lastUpdate]);

  const tempStr = temperature !== null ? temperature.toFixed(1) : '--';
  const humStr = humidity !== null ? Math.round(humidity) : '--';

  const statusText = connectionStatus === 'connected' ? 'Live' : connectionStatus === 'error' ? 'Offline' : 'Connecting';
  const statusVariant = connectionStatus === 'connected' ? 'success' : connectionStatus === 'error' ? 'danger' : 'secondary';

  return (
    <section className="Box hero">
      <div className="Box-header d-flex flex-items-center flex-justify-between">
        <h2 className="Box-title">Now</h2>
        <span className={`Label Label--${statusVariant}`}>{statusText}</span>
      </div>

      <div className="Box-body hero-body">
        <div className="hero-reading">
          <div>
            <div className="hero-temp-wrap">
              {typeof liveTemperature === 'number' ? (
                <LiveNumeral raw={liveTemperature} />
              ) : (
                <>
                  <span className="hero-temp">{tempStr}</span>
                  <span className="hero-unit">°C</span>
                </>
              )}
            </div>
            {mood && (
              <div className="mt-2">
                <span className={`Label Label--${moodLabel[mood] || 'secondary'}`}>{mood}</span>
              </div>
            )}
          </div>

          <div className="hero-secondary">
            <div>
              <div className="f6 color-fg-muted">Humidity</div>
              <div className="hero-metric-value">{humStr}<span className="f5 color-fg-muted">%</span></div>
            </div>
            {feelsLike !== null && (
              <div>
                <div className="f6 color-fg-muted">Feels like</div>
                <div className="hero-metric-value">{feelsLike}<span className="f5 color-fg-muted">°</span></div>
              </div>
            )}
            {dewPoint !== null && (
              <div>
                <div className="f6 color-fg-muted">Dew point</div>
                <div className="hero-metric-value">{dewPoint}<span className="f5 color-fg-muted">°</span></div>
              </div>
            )}
          </div>
        </div>

        {timeSinceUpdate && (
          <p className="f6 color-fg-muted mb-0">Updated {timeSinceUpdate}</p>
        )}
      </div>
    </section>
  );
}

export default SensorCard;

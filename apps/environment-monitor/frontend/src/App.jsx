import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import SensorCard from './components/SensorCard';
import ChartSection from './components/ChartSection';
import StatusBar from './components/StatusBar';
import { computeMood } from './comfort';

// Dev requests go through the vite proxy (see vite.config.js), which targets
// BACKEND_URL or localhost:5001 — no baseURL override needed in either mode.

function computeFeelsLike(temp, humidity) {
  // Heat Index (NWS Rothfusz regression) is only valid above ~80°F / 26.6°C.
  if (temp === null || humidity === null || temp <= 26.6) return null;
  const HI = -8.784695 + 1.61139411 * temp + 2.338549 * humidity
    + -0.14611605 * temp * humidity + -0.012308094 * temp * temp
    + -0.016424828 * humidity * humidity + 0.002211732 * temp * temp * humidity
    + 0.00072546 * temp * humidity * humidity + -0.000003582 * temp * temp * humidity * humidity;
  return Math.round(HI * 10) / 10;
}

function computeDewPoint(temp, humidity) {
  if (temp === null || humidity === null) return null;
  const a = 17.27, b = 237.7;
  const gamma = (a * temp) / (b + temp) + Math.log(humidity / 100);
  const dp = (b * gamma) / (a - gamma);
  return Math.round(dp * 10) / 10;
}

function describeAxiosError(error, label) {
  const detail = error?.response?.data?.detail
    || error?.response?.statusText
    || error?.message
    || 'Unknown error';
  const code = error?.response?.status ? ` (${error.response.status})` : '';
  return `${label}${code}: ${detail}`;
}

// Matches the backend's ~30s write-batch cadence; 5m uses faster silent refresh.
const CHART_REFRESH_MS = 30000;
const CHART_REFRESH_5M_MS = 5000;

function App() {
  const [sensorData, setSensorData] = useState({
    temperature: null, humidity: null, lastUpdate: null, status: 'connecting'
  });
  const [liveTemperature, setLiveTemperature] = useState(null);
  const [historicalData, setHistoricalData] = useState([]);
  const [averageMetrics, setAverageMetrics] = useState(null);
  const [currentRange, setCurrentRange] = useState('6h');
  const [loading, setLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [apiError, setApiError] = useState(null);

  const updateSensorData = useCallback(async () => {
    try {
      const response = await axios.get('/api/sensor-data');
      const data = response.data;
      setSensorData({
        temperature: parseFloat(data.temperature),
        humidity: parseFloat(data.humidity),
        lastUpdate: data.last_update,
        status: data.status || 'operational'
      });
      setConnectionStatus('connected');
      setApiError(null);
    } catch (error) {
      console.error('Error fetching sensor data:', error);
      setConnectionStatus('error');
      setApiError(describeAxiosError(error, 'Sensor data'));
    }
  }, []);

  const updateLiveReading = useCallback(async () => {
    try {
      const response = await axios.get('/api/live-reading');
      const t = response.data?.temperature;
      setLiveTemperature(typeof t === 'number' ? t : null);
    } catch (error) {
      // Don't surface as a banner — the live feed is best-effort.
      setLiveTemperature(null);
    }
  }, []);

  const loadHistoricalData = useCallback(async (range, signal, { silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const response = await axios.get(`/api/historical-data?range=${range}`, { signal });
      setHistoricalData(response.data);
      setApiError(null);
      if (!silent) setLoading(false);
    } catch (error) {
      if (axios.isCancel(error) || error.code === 'ERR_CANCELED') return;
      console.error('Error loading historical data:', error);
      setApiError(describeAxiosError(error, 'Historical data'));
      if (!silent) setLoading(false);
    }
  }, []);

  const loadAverageMetrics = useCallback(async (range, signal) => {
    try {
      const response = await axios.get(`/api/average-metrics?range=${range}`, { signal });
      setAverageMetrics(response.data);
      setApiError(null);
    } catch (error) {
      if (axios.isCancel(error) || error.code === 'ERR_CANCELED') return;
      console.error('Error loading average metrics:', error);
      setApiError(describeAxiosError(error, 'Metrics'));
    }
  }, []);

  const handleTimeframeChange = useCallback((range) => {
    setCurrentRange(range);
  }, []);

  // 5s polling for current reading — independent of range changes.
  useEffect(() => {
    updateSensorData();
    const interval = setInterval(updateSensorData, 5000);
    return () => clearInterval(interval);
  }, [updateSensorData]);

  // Faster 3s poll for the raw live-precision reading (not persisted).
  useEffect(() => {
    updateLiveReading();
    const interval = setInterval(updateLiveReading, 3000);
    return () => clearInterval(interval);
  }, [updateLiveReading]);

  // On 5m, append/replace a live tip from the smoothed sensor poll so the
  // chart line tracks between historical refreshes without remounting.
  const chartHistoricalData = useMemo(() => {
    if (currentRange !== '5m') return historicalData;
    const { lastUpdate, temperature, humidity } = sensorData;
    if (!lastUpdate || temperature === null || humidity === null) return historicalData;

    const tip = { timestamp: lastUpdate, temperature, humidity };
    if (historicalData.length === 0) return [tip];

    const lastPoint = historicalData[historicalData.length - 1];
    const tipTs = new Date(lastUpdate).getTime();
    const lastTs = new Date(lastPoint.timestamp).getTime();
    if (tipTs < lastTs) return historicalData;
    if (tipTs === lastTs) {
      return [...historicalData.slice(0, -1), { ...lastPoint, ...tip }];
    }
    return [...historicalData, tip];
  }, [currentRange, historicalData, sensorData]);

  // Load chart + metrics on range change, then silently refresh so the
  // series keeps moving without remounting the chart (preserves zoom).
  useEffect(() => {
    const rangeController = new AbortController();
    loadHistoricalData(currentRange, rangeController.signal);
    loadAverageMetrics(currentRange, rangeController.signal);

    const refreshMs = currentRange === '5m' ? CHART_REFRESH_5M_MS : CHART_REFRESH_MS;
    let refreshController = null;
    const interval = setInterval(() => {
      if (document.visibilityState === 'hidden') return;
      refreshController?.abort();
      refreshController = new AbortController();
      loadHistoricalData(currentRange, refreshController.signal, { silent: true });
      loadAverageMetrics(currentRange, refreshController.signal);
    }, refreshMs);

    return () => {
      rangeController.abort();
      refreshController?.abort();
      clearInterval(interval);
    };
  }, [currentRange, loadHistoricalData, loadAverageMetrics]);

  // Live reading in the tab title — readable from a pinned desktop tab.
  // parseFloat can yield NaN, so test for finite rather than non-null.
  useEffect(() => {
    document.title = Number.isFinite(sensorData.temperature)
      ? `${sensorData.temperature.toFixed(1)}°C · Room Monitor`
      : 'Room Monitor';
  }, [sensorData.temperature]);

  // Auto-dismiss the error banner after 10s.
  useEffect(() => {
    if (!apiError) return undefined;
    const id = setTimeout(() => setApiError(null), 10000);
    return () => clearTimeout(id);
  }, [apiError]);

  const mood = computeMood(sensorData.temperature, sensorData.humidity);
  const feelsLike = computeFeelsLike(sensorData.temperature, sensorData.humidity);
  const dewPoint = computeDewPoint(sensorData.temperature, sensorData.humidity);

  return (
    <div className="app">
      {apiError && (
        <div className="flash flash-error" role="alert">
          <button
            type="button"
            className="flash-close"
            onClick={() => setApiError(null)}
            aria-label="Dismiss error"
          >×</button>
          {apiError}
        </div>
      )}
      <header className="color-bg-subtle border-bottom px-3 px-md-4 py-2">
        <h1 className="f4 text-semibold m-0">Room Monitor</h1>
        <p className="f6 color-fg-muted m-0">Temperature and humidity</p>
      </header>
      <main className="app-main">
        <SensorCard
          temperature={sensorData.temperature}
          humidity={sensorData.humidity}
          liveTemperature={liveTemperature}
          mood={mood}
          feelsLike={feelsLike}
          dewPoint={dewPoint}
          connectionStatus={connectionStatus}
          lastUpdate={sensorData.lastUpdate}
        />

        <ChartSection
          historicalData={chartHistoricalData}
          averageMetrics={averageMetrics}
          currentRange={currentRange}
          onTimeframeChange={handleTimeframeChange}
          loading={loading}
          lastUpdate={sensorData.lastUpdate}
        />

        <StatusBar
          connectionStatus={connectionStatus}
          lastUpdate={sensorData.lastUpdate}
        />
      </main>
    </div>
  );
}

export default App;
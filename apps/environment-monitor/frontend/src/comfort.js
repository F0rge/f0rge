// Keep in sync with backend/config.py — single comfort / mood source of truth.

export const COMFORT_TEMP_MIN = 20.0;
export const COMFORT_TEMP_MAX = 24.0;
export const COMFORT_HUMIDITY_MIN = 40.0;
export const COMFORT_HUMIDITY_MAX = 60.0;

export const MOOD_TEMP_MILD_ABOVE = 25.0;
export const MOOD_TEMP_WARM_ABOVE = 27.0;
export const MOOD_TEMP_HOT_ABOVE = 29.0;
export const MOOD_TEMP_EXTREME_ABOVE = 32.0;

export function computeMood(temp, humidity) {
  if (temp === null || humidity === null) return '';
  if (temp > MOOD_TEMP_EXTREME_ABOVE) return 'Extreme';
  if (temp > MOOD_TEMP_HOT_ABOVE) return 'Hot';
  if (temp > MOOD_TEMP_WARM_ABOVE) return 'Warm';
  if (temp > MOOD_TEMP_MILD_ABOVE) return 'Mild';
  if (temp < COMFORT_TEMP_MIN) return 'Cool';
  if (humidity > COMFORT_HUMIDITY_MAX) return 'Muggy';
  if (humidity < COMFORT_HUMIDITY_MIN) return 'Dry';
  return 'Comfortable';
}

export function inComfortZone(temp, humidity) {
  return (
    temp != null &&
    humidity != null &&
    temp >= COMFORT_TEMP_MIN &&
    temp <= COMFORT_TEMP_MAX &&
    humidity >= COMFORT_HUMIDITY_MIN &&
    humidity <= COMFORT_HUMIDITY_MAX
  );
}

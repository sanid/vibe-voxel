// Solar position for Berlin (NOAA-style approximation: declination and equation of time).
// Accurate to about a tenth of a degree, which is well inside what the eye can see here.

export const BERLIN = { lat: 52.52, lon: 13.405 };

// EU daylight saving: from the last Sunday of March to the last Sunday of October (01:00 UTC).
function lastSunday(year, month) {
  const d = new Date(Date.UTC(year, month + 1, 0, 1)); // last day of month, 01:00 UTC
  d.setUTCDate(d.getUTCDate() - d.getUTCDay());
  return d;
}

export function berlinOffsetHours(date) {
  const y = date.getUTCFullYear();
  const start = lastSunday(y, 2);
  const end = lastSunday(y, 9);
  return date >= start && date < end ? 2 : 1;
}

// date: a Date at local midnight in Berlin (as produced by parseBerlinDate); hour: clock time 0..24.
export function sunAt(dayUtcMidnight, clockHour, offsetHours) {
  const doy = Math.floor((dayUtcMidnight - Date.UTC(dayUtcMidnight.getUTCFullYear(), 0, 0)) / 86400000);
  const g = (2 * Math.PI / 365) * (doy - 1 + (clockHour - 12) / 24);
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g)
    - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const eot = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
    - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g)); // minutes
  const solarHours = clockHour - offsetHours + (BERLIN.lon / 15) + eot / 60;
  const H = (solarHours - 12) * (Math.PI / 12);
  const phi = BERLIN.lat * Math.PI / 180;
  const sinEl = Math.sin(phi) * Math.sin(decl) + Math.cos(phi) * Math.cos(decl) * Math.cos(H);
  const el = Math.asin(Math.max(-1, Math.min(1, sinEl)));
  // azimuth measured westward from south (NOAA convention)
  const azS = Math.atan2(Math.sin(H), Math.cos(H) * Math.sin(phi) - Math.tan(decl) * Math.cos(phi));
  const east = -Math.sin(azS) * Math.cos(el);
  const north = -Math.cos(azS) * Math.cos(el);
  return { elevation: el, east, north, up: Math.sin(el) };
}

// "2026-06-21" -> Date at 00:00 UTC on that calendar day (used only for the day number).
export function parseDay(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

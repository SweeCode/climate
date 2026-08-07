/** Money and number formatting. Underwriters read magnitudes, not digits. */

export function eur(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `€${(value / 1e9).toFixed(2)}bn`;
  if (abs >= 1e6) return `€${(value / 1e6).toFixed(1)}m`;
  if (abs >= 1e3) return `€${(value / 1e3).toFixed(0)}k`;
  return `€${value.toFixed(0)}`;
}

export function count(value: number): string {
  return value.toLocaleString("en-GB");
}

export function pct(value: number): string {
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)}%`;
}

/** Colour ramp for per-location loss ratio, matching the hazard ramp in styles.css. */
export function heatColour(ratio: number): [number, number, number] {
  const stops: [number, number, number][] = [
    [91, 143, 201],
    [255, 237, 160],
    [254, 178, 76],
    [252, 78, 42],
    [189, 0, 38],
  ];
  const t = Math.max(0, Math.min(1, ratio)) * (stops.length - 1);
  const i = Math.floor(t);
  const j = Math.min(i + 1, stops.length - 1);
  const f = t - i;
  return [
    Math.round(stops[i][0] + (stops[j][0] - stops[i][0]) * f),
    Math.round(stops[i][1] + (stops[j][1] - stops[i][1]) * f),
    Math.round(stops[i][2] + (stops[j][2] - stops[i][2]) * f),
  ];
}

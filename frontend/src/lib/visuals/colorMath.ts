/**
 * Hue angle (0-360) for a hex color, or null for achromatic colors
 * (black/white/grey) that have no meaningful hue.
 *
 * Threshold is 0.12 (~30/255 channel spread) — matches colors.py's
 * `_hex_to_hue` on the backend. A near-black navy (#20262F, spread=15) or a
 * beige-grey (#AEACA0, spread=14) technically aren't pure grayscale but read
 * as neutral to a human eye; at a looser threshold they'd still plot on the
 * wheel as if they were a real "Blue"/"Yellow" hue.
 */
export function hexToHue(hex: string): number | null {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return null;
  const r = parseInt(clean.slice(0, 2), 16) / 255;
  const g = parseInt(clean.slice(2, 4), 16) / 255;
  const b = parseInt(clean.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  if (delta < 0.12) return null;
  let hue: number;
  if (max === r) hue = ((g - b) / delta) % 6;
  else if (max === g) hue = (b - r) / delta + 2;
  else hue = (r - g) / delta + 4;
  hue *= 60;
  if (hue < 0) hue += 360;
  return hue;
}

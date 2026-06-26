export const PALETTE = [
  "#5CFE50", // secondary-green
  "#3233F5", // secondary-blue
  "#f59e0b", // warning / amber
  "#ef4444", // error / red
  "#a78bfa", // violet
  "#fb923c", // orange
  "#38bdf8", // sky
];

/**
 * Returns the brand color for a competitor if available, otherwise falls back
 * to the palette by index. Always call with `allCompanies` sorted so the
 * index is stable across renders.
 */
export function getCompetitorColor(
  company: string,
  allCompanies: string[],
  brandColors: Record<string, string> = {}
): string {
  if (brandColors[company]) return brandColors[company];
  const idx = allCompanies.indexOf(company);
  return PALETTE[Math.max(idx, 0) % PALETTE.length];
}
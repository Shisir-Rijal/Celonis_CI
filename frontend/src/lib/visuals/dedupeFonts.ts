import type { FontInfo } from "./types";

// Mirrors backend/app/agents/visualbranding/nodes/fonts.py's
// _font_family_base script/weight suffix lists — kept in sync conceptually,
// not imported, since this is a display-only concern for the raw branding
// cards. The Fonts section's analysis keeps reading every scraped variant
// (name, weights, sizes) untouched via the backend's own normalization.
const SCRIPT_SUFFIXES = [
  "Arabic", "Hebrew", "Devanagari", "Thai", "Korean", "Japanese",
  "JP", "KR", "SC", "TC", "HK", "Armenian", "Georgian", "Bengali",
  "Tamil", "Gujarati", "Gurmukhi", "Kannada", "Malayalam", "Oriya",
  "Sinhala", "Telugu", "Khmer", "Lao", "Myanmar", "Looped", "Naskh",
];
const WEIGHT_SUFFIXES = [
  "Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold",
  "DemiBold", "Bold", "ExtraBold", "Black", "Heavy", "Italic", "Oblique",
];
const scriptSuffixRe = new RegExp(`\\s+(?:${SCRIPT_SUFFIXES.join("|")})$`, "i");
const weightSuffixRe = new RegExp(`[\\s-]+(?:${WEIGHT_SUFFIXES.join("|")})$`, "i");

/**
 * Strip trailing script/language and weight/style qualifiers so family
 * variants of the same typeface collapse to one display name, e.g.
 * "ServiceNow Sans Bold" -> "ServiceNow Sans", "IBM Plex Sans Arabic" ->
 * "IBM Plex Sans". Applied repeatedly to unwind compound suffixes.
 */
export function fontFamilyBase(name: string): string {
  let base = name.trim();
  for (let i = 0; i < 3; i++) {
    const stripped = base.replace(weightSuffixRe, "").replace(scriptSuffixRe, "").trim();
    if (stripped === base) break;
    base = stripped;
  }
  return base;
}

/**
 * One representative entry per distinct base family — used only to decide
 * what name/count to *display* in the raw branding cards (e.g. show
 * "ServiceNow Sans" once instead of it, "...Bold", and "...Light" as three
 * separate entries). Never used to drive the Fonts section's analysis.
 */
export function dedupeFontsForDisplay(fonts: FontInfo[]): FontInfo[] {
  const byKey = new Map<string, FontInfo>();
  for (const font of fonts) {
    if (!font.name) continue;
    const base = fontFamilyBase(font.name);
    const key = base.replace(/[\s-]+/g, "").toLowerCase();
    const existing = byKey.get(key);
    if (!existing) {
      byKey.set(key, { ...font, name: base });
    } else if (base.includes(" ") && !existing.name.includes(" ")) {
      byKey.set(key, { ...existing, name: base });
    }
  }
  return [...byKey.values()];
}

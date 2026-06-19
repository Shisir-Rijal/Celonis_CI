"use client";

import { useEffect } from "react";

const injected = new Set<string>();

/**
 * Scraped font names sometimes carry a "Type: Name" prefix (e.g. from
 * Brandfetch's `{type}: {name}` formatting) or an "Adobe Fonts (xxx)" label —
 * strip those down to the bare family name used for CSS font-family / Google
 * Fonts lookups.
 */
export function cleanFontName(raw: string): string {
  const withoutType = raw.includes(": ") ? raw.slice(raw.indexOf(": ") + 2) : raw;
  return withoutType.replace(/\s*\([^)]*\)\s*$/, "").trim();
}

/**
 * Best-effort: dynamically load each font family from Google Fonts so a
 * live sample can be rendered in its actual typeface. Fonts that aren't on
 * Google Fonts simply fail to load and fall back to the browser default —
 * harmless, just less accurate.
 */
export function useGoogleFonts(fontNames: string[]) {
  useEffect(() => {
    for (const name of fontNames) {
      if (!name || injected.has(name)) continue;
      injected.add(name);
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name).replace(/%20/g, "+")}:wght@400;700&display=swap`;
      document.head.appendChild(link);
    }
  }, [fontNames]);
}

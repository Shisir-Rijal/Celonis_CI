/**
 * Placeholder data for the branding agent's font interpretation.
 *
 * Mirrors `dummyColorInsights.ts` — swap the queryFn in `hooks.ts` for a real
 * `/branding/font-insights` call once the agent produces this, no component
 * changes needed.
 */

import type { FontInsights } from "./types";

export const DUMMY_FONT_INSIGHTS: FontInsights = {
  similarFonts: [
    {
      companies: ["IBM", "ServiceNow", "Signavio"],
      sharedFontFamily: "Geometric sans-serif",
      sampleFontName: "Inter",
      note: "All three lean on a clean geometric grotesk for body copy — the safe, highly legible default for enterprise software UI.",
    },
    {
      companies: ["OpenAI", "Anthropic"],
      sharedFontFamily: "Humanist sans-serif",
      sampleFontName: "Söhne",
      note: "Softer, more humanist letterforms than the enterprise cluster — reads less corporate, fitting for consumer-facing AI products.",
    },
    {
      companies: ["Databricks", "UiPath"],
      sharedFontFamily: "Bold display sans-serif",
      sampleFontName: "Manrope",
      note: "Both use a heavier-weight sans for headlines, matching their high-energy red-orange brand color with equally assertive type.",
    },
  ],
  generatedAt: null,
};

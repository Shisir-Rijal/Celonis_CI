/**
 * Placeholder data for the branding agent's high-level trend summary.
 *
 * Same swap-later pattern as `dummyColorInsights.ts` — replace the queryFn
 * in `hooks.ts` once `/branding/visual-trends` exists.
 */

import type { VisualTrends } from "./types";

export const DUMMY_VISUAL_TRENDS: VisualTrends = {
  trends: [
    {
      element: "Color",
      direction: "up",
      summary: "Blue is gaining ground — three competitors shifted toward corporate blue in the last two scrapes.",
    },
    {
      element: "Font",
      direction: "flat",
      summary: "Typeface choices have been stable; most competitors stayed on the same geometric sans-serif family.",
    },
    {
      element: "Logo",
      direction: "down",
      summary: "Fewer wordmark variants in circulation — competitors are consolidating to a single primary logo.",
    },
    {
      element: "Imagery",
      direction: "up",
      summary: "Product-screenshot imagery is replacing stock photography across most tracked landing pages.",
    },
  ],
  generatedAt: null,
};

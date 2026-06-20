import type { LogoDimensionBreakdown } from "./types";

/**
 * Placeholder for the (not-yet-built) branding agent's per-logo
 * classification output. Swap `useLogoDimensions`'s queryFn for a real
 * `/branding/logo-dimensions` call once that endpoint exists.
 */
export const DUMMY_LOGO_DIMENSIONS: LogoDimensionBreakdown = {
  dimensions: [
    {
      key: "type",
      label: "Type",
      categories: [
        { category: "Wordmark", pct: 48, companies: ["Celonis", "ServiceNow", "SAP"] },
        { category: "Combination mark", pct: 33, companies: ["Microsoft", "UiPath"] },
        { category: "Icon-only", pct: 19, companies: ["Apromore", "ARIS"] },
      ],
    },
    {
      key: "color",
      label: "Color",
      categories: [
        { category: "Colored", pct: 71, companies: ["Celonis", "Microsoft", "UiPath", "SAP"] },
        { category: "Monochrome", pct: 29, companies: ["ServiceNow", "ARIS", "Apromore"] },
      ],
    },
    {
      key: "shapeStyle",
      label: "Shape Style",
      categories: [
        { category: "Rounded", pct: 52, companies: ["Celonis", "UiPath", "Apromore"] },
        { category: "Angular", pct: 31, companies: ["SAP", "ARIS"] },
        { category: "Mixed", pct: 17, companies: ["Microsoft", "ServiceNow"] },
      ],
    },
    {
      key: "signalShape",
      label: "Signal Shape",
      categories: [
        { category: "Circle", pct: 38, companies: ["Celonis", "UiPath"] },
        { category: "Square", pct: 27, companies: ["Microsoft", "SAP"] },
        { category: "Abstract / Custom", pct: 21, companies: ["ARIS", "Apromore"] },
        { category: "None — typographic only", pct: 14, companies: ["ServiceNow"] },
      ],
    },
  ],
  generatedAt: null,
};

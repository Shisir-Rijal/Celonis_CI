import type { ImageryDimensionBreakdown } from "./types";

/**
 * Placeholder for the (not-yet-built) branding agent's per-image
 * classification output across five interpretive dimensions. Swap
 * `useImageryDimensions`'s queryFn for a real `/branding/imagery-dimensions`
 * call once that endpoint exists — every component consuming this shape
 * keeps working unchanged.
 */
export const DUMMY_IMAGERY_DIMENSIONS: ImageryDimensionBreakdown = {
  dimensions: [
    {
      key: "style",
      label: "Style",
      categories: [
        { category: "Photorealistic", pct: 46, companies: ["Microsoft", "SAP", "ServiceNow"] },
        { category: "Illustrative", pct: 33, companies: ["Apromore", "ARIS", "Celonis"] },
        { category: "Abstract", pct: 21, companies: ["Celonis", "UiPath"] },
      ],
    },
    {
      key: "effect",
      label: "Effect",
      categories: [
        { category: "Informative", pct: 41, companies: ["SAP", "ARIS", "Apromore"] },
        { category: "Emotional", pct: 32, companies: ["Microsoft", "ServiceNow"] },
        { category: "Aspirational", pct: 27, companies: ["Celonis", "UiPath"] },
      ],
    },
    {
      key: "subject",
      label: "Subject Matter",
      categories: [
        { category: "Industries", pct: 38, companies: ["SAP", "ServiceNow", "ARIS"] },
        { category: "People", pct: 35, companies: ["Microsoft", "ServiceNow", "UiPath"] },
        { category: "Landscape / Environment", pct: 27, companies: ["Celonis", "Apromore"] },
      ],
    },
    {
      key: "lookFeel",
      label: "Look & Feel",
      categories: [
        { category: "Clean", pct: 44, companies: ["Celonis", "SAP", "Apromore"] },
        { category: "Bold / Colorful", pct: 30, companies: ["Celonis", "UiPath"] },
        { category: "Playful", pct: 26, companies: ["UiPath", "ServiceNow"] },
      ],
    },
    {
      key: "colorScheme",
      label: "Color Scheme",
      categories: [
        { category: "Brand-aligned palette", pct: 39, companies: ["Celonis", "ServiceNow", "SAP"] },
        { category: "Saturated", pct: 28, companies: ["UiPath", "Celonis"] },
        { category: "Pastel", pct: 19, companies: ["Microsoft", "Apromore"] },
        { category: "Monochrome", pct: 14, companies: ["ARIS"] },
      ],
    },
  ],
  generatedAt: null,
};

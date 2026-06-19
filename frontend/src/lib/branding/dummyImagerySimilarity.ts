import type { ImagerySimilarity } from "./types";

/**
 * Placeholder for the (not-yet-built) branding agent's cross-competitor
 * imagery similarity scoring (cosine similarity over the style/effect/
 * subject/look & feel/color scheme classification, or similar). Swap
 * `useImagerySimilarity`'s queryFn for a real `/branding/imagery-similarity`
 * call once that endpoint exists.
 */
export const DUMMY_IMAGERY_SIMILARITY: ImagerySimilarity = {
  nodes: [
    { company: "Celonis", imageCount: 173 },
    { company: "ServiceNow", imageCount: 80 },
    { company: "UiPath", imageCount: 64 },
    { company: "Microsoft", imageCount: 58 },
    { company: "SAP", imageCount: 71 },
    { company: "Apromore", imageCount: 42 },
    { company: "ARIS", imageCount: 35 },
  ],
  links: [
    { source: "Celonis", target: "UiPath", similarity: 0.72 },
    { source: "Celonis", target: "ServiceNow", similarity: 0.41 },
    { source: "ServiceNow", target: "SAP", similarity: 0.58 },
    { source: "ServiceNow", target: "Microsoft", similarity: 0.63 },
    { source: "SAP", target: "Microsoft", similarity: 0.55 },
    { source: "Apromore", target: "ARIS", similarity: 0.69 },
    { source: "Apromore", target: "Celonis", similarity: 0.38 },
    { source: "ARIS", target: "SAP", similarity: 0.34 },
    { source: "UiPath", target: "Microsoft", similarity: 0.31 },
  ],
  generatedAt: null,
};

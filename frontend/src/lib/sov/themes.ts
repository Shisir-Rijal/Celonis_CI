/**
 * Frontend mirror of the SoV theme + region vocabularies.
 *
 * Single source of truth for filter UI and chart labels.
 * Keep in sync with backend/app/agents/sov/themes.py and the Region literal
 * in backend/app/agents/sov/state.py.
 */

import type { SovRegion } from "./types";

export const THEMES: string[] = [
  "Process Mining",
  "Process Intelligence",
  "AI & GenAI",
  "Agentic AI",
  "Automation",
  "Digital Transformation",
  "Supply Chain",
  "ERP & SAP",
  "Other",
];

export const REGIONS: SovRegion[] = [
  "DACH",
  "Europe",
  "NA",
  "APAC",
  "Global",
];

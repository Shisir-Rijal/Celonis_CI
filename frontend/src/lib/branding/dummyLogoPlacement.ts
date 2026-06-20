import type { LogoPlacement } from "./types";

/**
 * Placeholder for the (not-yet-built) branding agent's logo-placement
 * detection across scraped marketing imagery. Swap `useLogoPlacement`'s
 * queryFn for a real `/branding/logo-placement` call once that endpoint exists.
 */
export const DUMMY_LOGO_PLACEMENT: LogoPlacement = {
  positions: [
    { position: "top-left", pct: 34, companies: ["Celonis", "ServiceNow", "SAP"] },
    { position: "top-center", pct: 9, companies: ["Apromore"] },
    { position: "top-right", pct: 14, companies: ["Microsoft", "UiPath"] },
    { position: "center", pct: 6, companies: ["ARIS"] },
    { position: "bottom-left", pct: 8, companies: [] },
    { position: "bottom-center", pct: 5, companies: [] },
    { position: "bottom-right", pct: 11, companies: ["UiPath"] },
    { position: "not-present", pct: 13, companies: ["ARIS", "Apromore"] },
  ],
  generatedAt: null,
};

/**
 * Types for the (not-yet-built) branding agent's color-interpretation output.
 *
 * These mirror the response shape the future `/branding/color-insights`
 * endpoint should return. Until that endpoint exists, `hooks.ts` resolves
 * `DUMMY_COLOR_INSIGHTS` instead — swap the hook's queryFn for a real
 * `apiFetch` call and every component below keeps working unchanged.
 */

/**
 * Generic four-bucket usage scale. Used for the color spectrum today;
 * intended to be reused for fonts, imagery, etc. once those get their own
 * "how common is this element across competitors" breakdown.
 */
export type UsageLabel = "Very common" | "Common" | "Occasional" | "Rare";

export type CompetitorColorUsage = {
  company: string;
  hex: string;
  colorType: "primary" | "secondary";
};

export type ColorSpectrumEntry = {
  /** Hue family the agent clustered this color into, e.g. "Blue", "Terracotta". */
  colorFamily: string;
  /** A representative swatch for the family (not necessarily any single competitor's exact hex). */
  representativeHex: string;
  usageLabel: UsageLabel;
  /** How many tracked competitors use a color in this family. */
  usageCount: number;
  usedBy: CompetitorColorUsage[];
  /** Agent-generated psychological/brand association text, or null if not yet interpreted. */
  association: string | null;
};

export type CompetitorHueGroup = {
  /** Hue family this group of exact brand colors was clustered into, e.g. "Blue". */
  hueFamily: string;
  /** The competitor's exact hex codes that fall into this hue family. */
  colors: string[];
};

export type CompetitorColorDiversity = {
  company: string;
  /** This competitor's palette, grouped by distinct hue family. `hues.length` = diversity count. */
  hues: CompetitorHueGroup[];
};

export type WarmCoolSplit = {
  warmPct: number;
  coolPct: number;
  neutralPct: number;
  warmCompanies: string[];
  coolCompanies: string[];
  neutralCompanies: string[];
};

export type ColorInsights = {
  /** All hue families, any usage label — group by `usageLabel` to render the 4-column spectrum. */
  spectrum: ColorSpectrumEntry[];
  diversity: CompetitorColorDiversity[]; // sorted most -> least diverse
  warmCoolSplit: WarmCoolSplit;
  /** When the branding agent last produced this analysis, or null if never run. */
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Fonts (reuses the "similar groups" pattern from colors)
// ---------------------------------------------------------------------------

export type SimilarFontGroup = {
  companies: string[];
  /** Descriptive cluster label, e.g. "Geometric sans-serif". */
  sharedFontFamily: string;
  /** An actual Google Fonts family name used to render a live preview for this cluster. */
  sampleFontName: string;
  /** Agent-generated explanation of the similarity, or null. */
  note: string | null;
};

export type FontInsights = {
  similarFonts: SimilarFontGroup[];
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Visual trends — high-level "where is this element heading" summary
// ---------------------------------------------------------------------------

export type TrendDirection = "up" | "down" | "flat";

export type VisualElementTrend = {
  element: "Color" | "Font" | "Logo" | "Imagery";
  direction: TrendDirection;
  /** Short agent-generated note on where this element is trending and why. */
  summary: string;
};

export type VisualTrends = {
  trends: VisualElementTrend[];
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Imagery archetypes — visual style clusters competitors' imagery falls into
// ---------------------------------------------------------------------------

export type ImageryArchetype = {
  name: string;
  /** Agent-generated explanation of what defines this visual style cluster. */
  description: string;
  /** A representative image URL illustrating this archetype's style. */
  image: string;
  companies: string[];
};

export type ImageryArchetypes = {
  archetypes: ImageryArchetype[];
  generatedAt: string | null;
};

/** Generic category + usage-share + who-uses-it bucket, reused across every "how do tracked
 * competitors break down on X" dimension (imagery style/effect/..., logo type/color/...). */
export type DimensionCategory = {
  /** e.g. "Photorealistic", "Wordmark", "Rounded", "Circle". */
  category: string;
  pct: number;
  companies: string[];
};

// ---------------------------------------------------------------------------
// Imagery dimensions — Style / Effect / Subject / Look & Feel / Color scheme
// ---------------------------------------------------------------------------

export type ImageryDimensionKey = "style" | "effect" | "subject" | "lookFeel" | "colorScheme";

export type ImageryDimension = {
  key: ImageryDimensionKey;
  label: string;
  categories: DimensionCategory[];
};

export type ImageryDimensionBreakdown = {
  dimensions: ImageryDimension[];
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Imagery similarity — which competitors' imagery style clusters together
// ---------------------------------------------------------------------------

export type ImagerySimilarityNode = {
  company: string;
  /** Number of analyzed images this competitor contributes — used to size the node. */
  imageCount: number;
};

export type ImagerySimilarityLink = {
  source: string;
  target: string;
  /** 0-1 similarity score across style/effect/subject/look & feel/color scheme. */
  similarity: number;
};

export type ImagerySimilarity = {
  nodes: ImagerySimilarityNode[];
  links: ImagerySimilarityLink[];
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Logo dimensions — Type / Color / Shape style / Signal shape
// ---------------------------------------------------------------------------

export type LogoDimensionKey = "type" | "color" | "shapeStyle" | "signalShape";

export type LogoDimension = {
  key: LogoDimensionKey;
  label: string;
  categories: DimensionCategory[];
};

export type LogoDimensionBreakdown = {
  dimensions: LogoDimension[];
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Logo placement — where competitors place their logo on marketing imagery
// ---------------------------------------------------------------------------

export type LogoPlacementPosition =
  | "top-left"
  | "top-center"
  | "top-right"
  | "center"
  | "bottom-left"
  | "bottom-center"
  | "bottom-right"
  | "not-present";

export type LogoPlacementEntry = {
  position: LogoPlacementPosition;
  pct: number;
  companies: string[];
};

export type LogoPlacement = {
  positions: LogoPlacementEntry[];
  generatedAt: string | null;
};

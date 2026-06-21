/**
 * Types for the branding agent's interpretation output.
 *
 * Mirror the response shapes returned by the `/branding/*` endpoints
 * (backend/app/api/visualbranding.py adapts the agent's Pydantic models into
 * these exact shapes).
 */

// ---------------------------------------------------------------------------
// Brand archetypes — holistic cross-dimension synthesis (one per company or
// company group, not gated to a single visual dimension)
// ---------------------------------------------------------------------------

export type BrandArchetype = {
  name: string;
  /** Short single-word vibe descriptors, e.g. ["Bold", "Technical", "Disruptive"]. */
  keywords: string[];
  vibe: string;
  typography: string;
  coloring: string;
  /** Representative image URL, or null if nothing scraped yet for this archetype. */
  image: string | null;
  /** Can be a single company — not every archetype needs 2+ members. */
  companies: string[];
};

export type BrandArchetypes = {
  archetypes: BrandArchetype[];
  generatedAt: string | null;
};

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

export type FontArchetype = {
  name: string;
  description: string;
  sampleFontName: string;
  companies: string[];
};

export type FontDimensionKey = "classification" | "weight_emphasis" | "personality";

export type FontDimension = {
  key: FontDimensionKey;
  label: string;
  categories: DimensionCategory[];
};

export type FontInsights = {
  similarFonts: SimilarFontGroup[];
  archetypes: FontArchetype[];
  dimensions: FontDimension[];
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Cross-dimension change alerts — what changed since each node's last run
// ---------------------------------------------------------------------------

export type BrandingAlerts = {
  color: string[] | null;
  font: string[] | null;
  logo: string[] | null;
  image: string[] | null;
  video: string[] | null;
  trend: string[] | null;
};

// ---------------------------------------------------------------------------
// Visual trends — high-level "where is this element heading" summary
// ---------------------------------------------------------------------------

export type TrendDirection = "up" | "down" | "flat";

export type VisualElementTrend = {
  element: "Color" | "Font" | "Logo" | "Imagery" | "Video";
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
  /** {company: logo image URL} — lets the UI show the actual logo behind any company name. */
  logoUrls: Record<string, string>;
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
  /** {company: logo image URL} — lets the UI show the actual logo behind any company name. */
  logoUrls: Record<string, string>;
  generatedAt: string | null;
};

// ---------------------------------------------------------------------------
// Video — format / effect / length / presence + named archetypes + usage
// ---------------------------------------------------------------------------

export type VideoArchetype = {
  name: string;
  description: string;
  /** Representative thumbnail (or video URL) illustrating this style cluster. */
  thumbnail: string;
  companies: string[];
};

export type VideoDimensionKey = "format" | "effect" | "length" | "presence";

export type VideoDimension = {
  key: VideoDimensionKey;
  label: string;
  categories: DimensionCategory[];
};

export type VideoUsageEntry = {
  company: string;
  count: number;
  avgDurationSeconds: number | null;
};

export type VideoInsights = {
  archetypes: VideoArchetype[];
  dimensions: VideoDimension[];
  usage: VideoUsageEntry[];
  generatedAt: string | null;
};

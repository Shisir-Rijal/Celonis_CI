/**
 * TypeScript types mirroring the backend VisualsItem/VisualsResponse from
 * `app/api/visuals.py`.
 */

export type FontInfo = {
  name: string;
  type: string | null;
  weights: string[] | null;
  sizes: string[] | null;
};

export type ImageCategory = "diagram" | "screenshot" | "photo" | "illustration" | "other";

export type SourcedAsset = {
  url: string;
  source_page: string | null;
  /** images only — null for videos, or for images scraped before this field existed */
  category: ImageCategory | null;
};

export type VisualsItem = {
  company: string;
  url: string | null;
  title: string | null;
  logo: string[];
  /** semantic: hex -> what it's for, e.g. "success" | "error" | "warning" | "info" | "disabled" */
  colors: { primary?: string[]; secondary?: string[]; semantic?: Record<string, string> };
  fonts: FontInfo[] | null;
  images: SourcedAsset[] | null;
  videos: SourcedAsset[];
  icons: Record<string, string> | null;
  run_at: string | null;
};

export type VisualsResponse = {
  visuals: VisualsItem[];
  total: number;
  latest_run_at: string | null;
};

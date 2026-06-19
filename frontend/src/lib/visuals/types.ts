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

export type SourcedAsset = {
  url: string;
  source_page: string | null;
};

export type VisualsItem = {
  company: string;
  url: string | null;
  title: string | null;
  logo: string[];
  colors: { primary?: string[]; secondary?: string[] };
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

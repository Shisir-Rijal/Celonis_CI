/**
 * TypeScript types mirroring backend Pydantic schemas in `app/api/brand.py`.
 * Keep in sync when backend response shapes change.
 */

// ---------------------------------------------------------------------------
// Zone 1 + 2 — GET /brand/geo-intelligence/{company}
// ---------------------------------------------------------------------------

export type KpiDeltas = {
  visibility_pct: number | null;
  geo_score: number | null;
  active_recommendation_pct: number | null;
  gap_count: number | null;
};

export type KpiBlock = {
  visibility_pct: number;
  geo_score: number;
  active_recommendation_pct: number;
  gap_count: number;
  deltas: KpiDeltas | null;
};

export type TrendPoint = {
  run_at: string;
  visibility_pct: number;
  geo_score: number;
};

export type LlmComparisonPoint = {
  llm: string;
  mention_rate: number;
};

export type TrendsBlock = {
  series: TrendPoint[];
  llm_comparison: LlmComparisonPoint[];
};

export type GeoIntelligenceResponse = {
  company: string;
  latest_run_at: string;
  kpis: KpiBlock;
  trends: TrendsBlock;
};

// ---------------------------------------------------------------------------
// Zone 3 — GET /brand/geo-intelligence/{company}/share-of-voice
// ---------------------------------------------------------------------------

export type SovEntry = {
  company: string;
  is_target: boolean;
  mention_count: number;
  mention_rate: number;
};

export type SovTier = {
  tier: string;
  label: string;
  total_keywords: number;
  entries: SovEntry[];
};

export type ShareOfVoiceResponse = {
  company: string;
  run_at: string;
  tiers: SovTier[];
};

// ---------------------------------------------------------------------------
// Zone 4 — GET /brand/geo-intelligence/{company}/strategic-maps
// ---------------------------------------------------------------------------

export type PeerNode = {
  id: string;
  is_target: boolean;
  weight: number;
};

export type PeerLink = {
  source: string;
  target: string;
  weight: number;
  distance: number;
};

export type PeerNetworkBlock = {
  nodes: PeerNode[];
  links: PeerLink[];
  primary_peer_group: string[];
};

export type HeatmapCell = {
  x: string;
  y: number;
};

export type HeatmapRow = {
  id: string;
  data: HeatmapCell[];
};

export type TerritoryOwner = {
  tier: string;
  competitors: { name: string; count: number }[];
};

export type TerritoryMapBlock = {
  rows: HeatmapRow[];
  owned_territories: string[];
  contested_territories: string[];
  absent_territories: string[];
  territory_owners: TerritoryOwner[];
};

export type StrategicMapsResponse = {
  company: string;
  run_at: string;
  peer_network: PeerNetworkBlock;
  territory_map: TerritoryMapBlock;
};

// ---------------------------------------------------------------------------
// Zone 5 — GET /brand/geo-intelligence/{company}/deep-dive
// ---------------------------------------------------------------------------

export type AlertCards = {
  critical_gap: string | null;
  framing_gap: string | null;
  counter_positioning: string | null;
};

export type KeywordRow = {
  keyword: string;
  tier: string;
  mentioned: boolean;
  framing: string | null;
  recommendation_strength: string | null;
  use_case_context: string | null;
  counter_positioning: string | null;
  exact_quote: string | null;
};

export type DeepDiveResponse = {
  company: string;
  run_at: string;
  alerts: AlertCards;
  keyword_rows: KeywordRow[];
  full_briefing: string | null;
};

/**
 * TypeScript types mirroring backend EventItem from
 * `app/agents/research/state.py`.
 */

export type EventItem = {
  company: string;
  name: string | null;
  title: string | null;
  event_date: string | null;
  end_date: string | null;
  location: string | null;
  event_topic: string | null;
  organized_by: string | null;
  sponsors: string[] | null;
  speakers: string[] | null;
  summary: string | string[] | null;
  source_link: string | null;
  image: string | null;
  attendees: number | null;
  source_type: string | null;
  date: string;
  url: string;
};

export type EventsResponse = {
  events: EventItem[];
  total: number;
  latest_run_at: string | null;
};
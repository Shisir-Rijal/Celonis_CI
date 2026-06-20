// frontend/lib/news/types.ts
// Mirrors backend Pydantic models in app/api/news.py

export interface NewsArticle {
  heading: string | null;
  text: string | null;
  summary: string | null;
  url: string;
  title: string | null;
  image: string | null;
  author: string | null;
  published_date: string | null;
  source_type: string | null;
}

export interface CompanyNews {
  company: string; // domain, e.g. "celonis.com"
  name: string; // display name, e.g. "Celonis"
  run_at: string;
  article_count: number;
  frequency: Record<string, number>;
  articles: NewsArticle[];
}

export interface NewsListResponse {
  companies: CompanyNews[];
}
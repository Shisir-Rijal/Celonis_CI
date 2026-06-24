/**
 * Hook for generating competitive intelligence reports.
 * Calls POST /reports/generate and returns the markdown string.
 */

import { useState } from "react";
import { apiFetch } from "@/lib/api";

interface ReportRequest {
  topic: string;
  companies?: string[] | null;
}

interface ReportResponse {
  topic: string;
  companies: string[] | null;
  markdown: string;
}

interface UseReportGenerationResult {
  generate: (req: ReportRequest) => Promise<void>;
  markdown: string | null;
  isLoading: boolean;
  error: string | null;
  reset: () => void;
}

export function useReportGeneration(): UseReportGenerationResult {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(req: ReportRequest) {
    setIsLoading(true);
    setError(null);
    setMarkdown(null);

    try {
      const res = await apiFetch<ReportResponse>("/reports/generate", {
        method: "POST",
        body: JSON.stringify(req),
      });
      setMarkdown(res.markdown);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed.");
    } finally {
      setIsLoading(false);
    }
  }

  function reset() {
    setMarkdown(null);
    setError(null);
    setIsLoading(false);
  }

  return { generate, markdown, isLoading, error, reset };
}
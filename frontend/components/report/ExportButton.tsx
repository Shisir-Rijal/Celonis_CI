/**
 * Export button used across all dashboard pages.
 * Triggers report generation for the given topic and selected companies,
 * then opens ReportModal to display the result.
 */

"use client";

import { useState } from "react";
import { useReportGeneration } from "@/lib/report/hooks";
import ReportModal from "./ReportModal";

interface ExportButtonProps {
  topic: "news" | "events" | "geo" | "branding" | "sov";
  companies?: string[];
}

export default function ExportButton({ topic, companies }: ExportButtonProps) {
  const { generate, markdown, isLoading, error, reset } = useReportGeneration();
  const [modalOpen, setModalOpen] = useState(false);

  async function handleClick() {
    setModalOpen(true);
    await generate({
      topic,
      companies: companies && companies.length > 0 ? companies : null,
    });
  }

  function handleClose() {
    setModalOpen(false);
    reset();
  }

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        disabled={isLoading}
        className="text-xs tracking-[0.16em] uppercase font-medium text-primary-black hover:opacity-70 transition-opacity cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "Generating…" : "Report ↗"}
      </button>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          {isLoading && (
            <div className="text-sm text-neutral-grey-20 animate-pulse">
              Generating report…
            </div>
          )}
          {error && (
            <div className="bg-neutral-grey-90 border border-neutral-grey-30 rounded-xl px-8 py-6 flex flex-col gap-4 max-w-sm w-full">
              <span className="text-sm text-red-400">{error}</span>
              <button
                type="button"
                onClick={handleClose}
                className="text-xs tracking-widest uppercase text-neutral-grey-20 hover:text-primary-white transition-colors"
              >
                Close
              </button>
            </div>
          )}
          {markdown && (
            <ReportModal topic={topic} markdown={markdown} onClose={handleClose} />
          )}
        </div>
      )}
    </>
  );
}
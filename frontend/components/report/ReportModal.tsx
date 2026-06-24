/**
 * Modal that displays a generated markdown report.
 * Renders markdown as formatted HTML and provides a plain-text download.
 */

"use client";

import { useEffect, useRef } from "react";

interface ReportModalProps {
  topic: string;
  markdown: string;
  onClose: () => void;
}

function markdownToHtml(md: string): string {
  return md
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-medium text-primary-white mt-6 mb-2">$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-medium text-primary-white mt-4 mb-1">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-primary-white">$1</strong>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-neutral-grey-20">$1</li>')
    .replace(/\n\n/g, '</p><p class="text-sm text-neutral-grey-20 leading-relaxed mb-3">')
    .replace(/^(?!<)(.+)$/gm, '<p class="text-sm text-neutral-grey-20 leading-relaxed mb-3">$1</p>');
}

function handleDownload(topic: string, markdown: string) {
  const printContent = `
    <!DOCTYPE html>
    <html>
      <head>
        <title>${topic} — Competitive Intelligence Report</title>
        <style>
          body { font-family: sans-serif; max-width: 720px; margin: 40px auto; color: #111; line-height: 1.7; }
          h2 { font-size: 18px; font-weight: 600; margin-top: 32px; margin-bottom: 8px; }
          h3 { font-size: 15px; font-weight: 600; margin-top: 24px; margin-bottom: 6px; }
          p { font-size: 14px; margin-bottom: 12px; }
          li { font-size: 14px; margin-bottom: 6px; margin-left: 20px; list-style: disc; }
          strong { font-weight: 600; }
        </style>
      </head>
      <body>
        <h1 style="font-size:22px;font-weight:700;margin-bottom:4px;text-transform:capitalize">${topic} — Competitive Intelligence Report</h1>
        <p style="color:#666;font-size:13px;margin-bottom:32px">${new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}</p>
        ${markdownToHtml(markdown)}
      </body>
    </html>
  `;

  const iframe = document.createElement("iframe");
  iframe.style.display = "none";
  document.body.appendChild(iframe);
  iframe.contentDocument!.write(printContent);
  iframe.contentDocument!.close();
  iframe.contentWindow!.focus();
  iframe.contentWindow!.print();
  setTimeout(() => document.body.removeChild(iframe), 1000);
}

export default function ReportModal({ topic, markdown, onClose }: ReportModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Close on overlay click
  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
    >
      <div className="relative w-full max-w-2xl max-h-[80vh] flex flex-col bg-neutral-grey-90 border border-neutral-grey-30 rounded-xl overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-grey-30 shrink-0">
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] tracking-[0.18em] uppercase text-neutral-grey-20 font-medium">
              Competitive Intelligence Report
            </span>
            <span className="text-base font-medium text-primary-white capitalize">
              {topic}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => handleDownload(topic, markdown)}
              className="text-xs tracking-[0.16em] uppercase font-medium text-neutral-grey-20 hover:text-secondary-green transition-colors cursor-pointer"
            >
              Save as PDF →
            </button>
            <button
              type="button"
              onClick={onClose}
              className="text-xs tracking-[0.16em] uppercase font-medium text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
            >
              Close ✕
            </button>
          </div>
        </div>

        {/* Content */}
        <div
          className="overflow-y-auto px-6 py-6 text-sm text-neutral-grey-20 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: markdownToHtml(markdown) }}
        />
      </div>
    </div>
  );
}
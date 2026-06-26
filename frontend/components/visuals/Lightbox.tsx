"use client";

import { useEffect } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, X } from "lucide-react";

// ---------------------------------------------------------------------------
// Lightbox — full-screen overlay with prev/next navigation through a gallery
// ---------------------------------------------------------------------------

export type GalleryItem = { url: string; source?: string | null };

export type Gallery = {
  items: GalleryItem[];
  index: number;
  alt: string;
  /** "white" — solid white panel (product images). "light" — subtle translucent
   * panel, just enough to keep dark/monochrome logos visible without the stark
   * white background images get. Omit for no background. */
  bg?: "white" | "light";
};

export function Lightbox({
  gallery,
  onClose,
  onIndexChange,
}: {
  gallery: Gallery;
  onClose: () => void;
  onIndexChange: (index: number) => void;
}) {
  const { items, index, alt, bg } = gallery;
  const current = items[index];

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") onIndexChange((index + 1) % items.length);
      if (e.key === "ArrowLeft") onIndexChange((index - 1 + items.length) % items.length);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [index, items.length, onClose, onIndexChange]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
      onClick={onClose}
    >
      {current.source && (
        <a
          href={current.source}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          title={current.source}
          className="absolute top-5 right-16 flex items-center gap-1.5 text-xs text-white/70 hover:text-white transition-colors"
        >
          <ExternalLink size={14} />
          Source
        </a>
      )}

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        aria-label="Close"
        className="absolute top-5 right-5 text-white/70 hover:text-white transition-colors cursor-pointer"
      >
        <X size={28} />
      </button>

      {items.length > 1 && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onIndexChange((index - 1 + items.length) % items.length);
          }}
          aria-label="Previous"
          className="absolute left-5 text-white/70 hover:text-white transition-colors cursor-pointer"
        >
          <ChevronLeft size={36} />
        </button>
      )}

      <div
        onClick={(e) => e.stopPropagation()}
        className={
          bg === "white"
            ? "inline-flex bg-white rounded-md p-6 max-w-[85vw] max-h-[85vh]"
            : bg === "light"
              ? "inline-flex bg-white/90 rounded-md p-6 max-w-[85vw] max-h-[85vh]"
              : "inline-flex max-w-[85vw] max-h-[85vh]"
        }
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={current.url}
          alt={alt}
          className={
            bg
              ? "max-w-[75vw] max-h-[75vh] object-contain"
              : "max-w-[85vw] max-h-[85vh] object-contain rounded-md"
          }
        />
      </div>

      {items.length > 1 && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onIndexChange((index + 1) % items.length);
          }}
          aria-label="Next"
          className="absolute right-5 text-white/70 hover:text-white transition-colors cursor-pointer"
        >
          <ChevronRight size={36} />
        </button>
      )}

      {items.length > 1 && (
        <span className="absolute bottom-5 text-xs text-white/60">
          {index + 1} / {items.length}
        </span>
      )}
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ExternalLink, Play } from "lucide-react";

import DashboardCard from "@components/geo/DashboardCard";
import type { ImageCategory, VisualsItem } from "@/lib/visuals/types";
import { useGoogleFonts, cleanFontName } from "@/lib/visuals/useGoogleFonts";
import type { GalleryItem } from "./Lightbox";

const IMAGE_CATEGORY_LABELS: Record<ImageCategory, string> = {
  diagram: "Diagrams",
  screenshot: "Screenshots",
  photo: "Photos",
  illustration: "Illustrations",
  other: "Other",
};
const IMAGE_CATEGORY_ORDER: ImageCategory[] = ["screenshot", "diagram", "photo", "illustration", "other"];

export const ELEMENT_OPTIONS = [
  { value: "colors", label: "Colors" },
  { value: "logos", label: "Logos" },
  { value: "fonts", label: "Fonts" },
  { value: "images", label: "Images" },
  { value: "icons", label: "Icons" },
  { value: "videos", label: "Videos" },
] as const;

export type Element = (typeof ELEMENT_OPTIONS)[number]["value"];

// ---------------------------------------------------------------------------
// Pieces
// ---------------------------------------------------------------------------

function ColorSwatch({ hex }: { hex: string }) {
  return (
    <span className="relative group/swatch">
      <span
        aria-label={hex}
        className="block w-7 h-7 rounded-full border border-white/15 shrink-0 cursor-default"
        style={{ backgroundColor: hex }}
      />
      <span
        className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap
          rounded-sm border border-white/10 bg-neutral-grey-30 px-2 py-1 text-[11px] text-primary-white
          opacity-0 shadow-lg transition-opacity z-10 group-hover/swatch:opacity-100"
      >
        {hex}
      </span>
    </span>
  );
}

function videoLabel(url: string): string {
  try {
    const { hostname } = new URL(url);
    return hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

export function CompetitorBrandingCard({
  item,
  elements,
  accent,
  onOpenGallery,
}: {
  item: VisualsItem;
  elements: Element[];
  accent: string;
  onOpenGallery: (items: GalleryItem[], index: number, alt: string, bg?: "white" | "light") => void;
}) {
  const showColors = elements.includes("colors");
  const showLogos = elements.includes("logos");
  const showFonts = elements.includes("fonts");
  const showImages = elements.includes("images");
  const showIcons = elements.includes("icons");
  const showVideos = elements.includes("videos");

  const primary = [...new Set(item.colors?.primary ?? [])];
  const secondary = [...new Set(item.colors?.secondary ?? [])].filter((c) => !primary.includes(c));
  const semanticEntries = Object.entries(item.colors?.semantic ?? {});
  const [showSemantic, setShowSemantic] = useState(false);
  const fonts = item.fonts ?? [];
  const images = item.images ?? [];
  const iconEntries = Object.entries(item.icons ?? {});
  const videos = item.videos ?? [];

  // Some scraped URLs fail to actually render (dead/blocked/corrupt) — hide
  // those instead of leaving a blank white thumbnail in the grid.
  const [brokenUrls, setBrokenUrls] = useState<Set<string>>(new Set());
  const markBroken = (url: string) =>
    setBrokenUrls((prev) => (prev.has(url) ? prev : new Set(prev).add(url)));

  const visibleLogos = item.logo.filter((src) => !brokenUrls.has(src));
  const visibleImages = images.filter((img) => !brokenUrls.has(img.url));
  const visibleIconEntries = iconEntries.filter(([src]) => !brokenUrls.has(src));
  const visibleIconUrls = visibleIconEntries.map(([url]) => url);

  const [imageCategoryFilter, setImageCategoryFilter] = useState<ImageCategory | "all">("all");
  const presentImageCategories = IMAGE_CATEGORY_ORDER.filter((cat) =>
    visibleImages.some((img) => img.category === cat)
  );
  const filteredImages =
    imageCategoryFilter === "all"
      ? visibleImages
      : visibleImages.filter((img) => img.category === imageCategoryFilter);

  const fontNames = useMemo(() => fonts.map((f) => cleanFontName(f.name)), [fonts]);
  useGoogleFonts(fontNames);

  return (
    <DashboardCard className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: accent }} />
          <h4 className="text-lg font-medium text-primary-white truncate">{item.company}</h4>
        </div>
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            title={item.url}
            className="flex items-center gap-1 text-[11px] text-neutral-grey-20 hover:text-primary-white transition-colors shrink-0"
          >
            <ExternalLink size={12} />
          </a>
        )}
      </div>

      {showColors && (primary.length > 0 || secondary.length > 0 || semanticEntries.length > 0) && (
        <div className="flex flex-col gap-3">
          <span className="text-[11px] text-neutral-grey-20 uppercase tracking-widest">
            Colors
          </span>
          {primary.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] text-neutral-grey-20">Primary</span>
              <div className="flex flex-wrap gap-2">
                {primary.map((c) => (
                  <ColorSwatch key={c} hex={c} />
                ))}
              </div>
            </div>
          )}
          {secondary.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] text-neutral-grey-20">Secondary</span>
              <div className="flex flex-wrap gap-2">
                {secondary.map((c) => (
                  <ColorSwatch key={c} hex={c} />
                ))}
              </div>
            </div>
          )}
          {semanticEntries.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <button
                type="button"
                onClick={() => setShowSemantic((v) => !v)}
                aria-expanded={showSemantic}
                className="flex items-center gap-1 text-[10px] text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer w-fit"
              >
                <ChevronDown
                  size={12}
                  className={`transition-transform ${showSemantic ? "" : "-rotate-90"}`}
                />
                Semantic colors ({semanticEntries.length})
              </button>
              {showSemantic && (
                <div className="flex flex-wrap gap-3 pl-1">
                  {semanticEntries.map(([hex, label]) => (
                    <span key={hex} className="flex items-center gap-1.5">
                      <ColorSwatch hex={hex} />
                      <span className="text-[10px] text-neutral-grey-20 capitalize">{label}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {showLogos && visibleLogos.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[11px] text-neutral-grey-20 uppercase tracking-widest">
            Logos
          </span>
          <div className="flex flex-wrap gap-2">
            {visibleLogos.slice(0, 4).map((src, i) => (
              <button
                key={src}
                type="button"
                onClick={() =>
                  onOpenGallery(
                    visibleLogos.map((url) => ({ url })),
                    i,
                    `${item.company} logo`,
                    "light"
                  )
                }
                className="w-16 h-16 rounded-md bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden cursor-pointer hover:border-white/25 transition-colors"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={src}
                  alt={`${item.company} logo`}
                  className="max-w-full max-h-full object-contain"
                  onError={() => markBroken(src)}
                />
              </button>
            ))}
          </div>
        </div>
      )}

      {showFonts && fonts.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[11px] text-neutral-grey-20 uppercase tracking-widest">
            Fonts
          </span>
          <div className="flex flex-wrap gap-2">
            {fonts.slice(0, 6).map((f, i) => {
              const details = [
                f.weights?.length ? `${f.weights.join("/")}` : null,
                f.sizes?.length ? `${f.sizes.join(", ")}` : null,
              ].filter(Boolean);
              return (
                <div
                  key={f.name}
                  title={details.length ? details.join(" · ") : undefined}
                  className="flex flex-col items-center gap-1 px-3 py-2 rounded-sm bg-white/5 border border-white/10"
                >
                  <span
                    style={{ fontFamily: `"${fontNames[i]}", sans-serif` }}
                    className="text-base text-primary-white leading-none"
                  >
                    Sample
                  </span>
                  <span className="text-[10px] text-neutral-grey-20 truncate max-w-[100px]">
                    {f.name}
                  </span>
                  {details.length > 0 && (
                    <span className="text-[9px] text-neutral-grey-20/70 truncate max-w-[100px]">
                      {details.join(" · ")}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {showImages && images.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-neutral-grey-20 uppercase tracking-widest">
              Images
            </span>
            <span className="text-[10px] text-neutral-grey-20">{filteredImages.length}</span>
          </div>
          {presentImageCategories.length > 1 && (
            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                onClick={() => setImageCategoryFilter("all")}
                className={`text-[10px] px-2 py-0.5 rounded-full transition-colors cursor-pointer ${
                  imageCategoryFilter === "all"
                    ? "bg-secondary-green text-primary-black font-medium"
                    : "bg-white/5 border border-white/10 text-neutral-grey-20 hover:text-primary-white"
                }`}
              >
                All
              </button>
              {presentImageCategories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setImageCategoryFilter(cat)}
                  className={`text-[10px] px-2 py-0.5 rounded-full transition-colors cursor-pointer ${
                    imageCategoryFilter === cat
                      ? "bg-secondary-green text-primary-black font-medium"
                      : "bg-white/5 border border-white/10 text-neutral-grey-20 hover:text-primary-white"
                  }`}
                >
                  {IMAGE_CATEGORY_LABELS[cat]}
                </button>
              ))}
            </div>
          )}
          <div className="grid grid-cols-4 gap-1.5">
            {filteredImages.slice(0, 4).map((img, i) => (
              <button
                key={img.url}
                type="button"
                onClick={() =>
                  onOpenGallery(
                    filteredImages.map((im) => ({ url: im.url, source: im.source_page })),
                    i,
                    `${item.company} image`,
                    "white"
                  )
                }
                className="aspect-square rounded-sm bg-white/5 border border-white/10 overflow-hidden cursor-pointer hover:border-white/25 transition-colors"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={img.url}
                  alt=""
                  className="w-full h-full object-cover"
                  onError={() => markBroken(img.url)}
                />
              </button>
            ))}
          </div>
        </div>
      )}

      {showIcons && iconEntries.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-neutral-grey-20 uppercase tracking-widest">
              Icons
            </span>
            <span className="text-[10px] text-neutral-grey-20">{iconEntries.length}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {visibleIconEntries.slice(0, 8).map(([src, label], i) => (
              <button
                key={src}
                type="button"
                title={label}
                onClick={() =>
                  onOpenGallery(
                    visibleIconUrls.map((url) => ({ url })),
                    i,
                    label || `${item.company} icon`
                  )
                }
                className="w-10 h-10 rounded-md bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden cursor-pointer hover:border-white/25 transition-colors"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={src}
                  alt={label || `${item.company} icon`}
                  className="max-w-full max-h-full object-contain"
                  onError={() => markBroken(src)}
                />
              </button>
            ))}
          </div>
        </div>
      )}

      {showVideos && videos.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-neutral-grey-20 uppercase tracking-widest">
              Videos
            </span>
            <span className="text-[10px] text-neutral-grey-20">{videos.length}</span>
          </div>
          <div className="flex flex-col gap-1.5">
            {videos.slice(0, 3).map((v) => (
              <div
                key={v.url}
                className="flex items-center gap-2 text-xs px-2 py-1.5 rounded-sm bg-white/5 border border-white/10 text-neutral-grey-10"
              >
                <a
                  href={v.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 min-w-0 flex-1 hover:text-primary-white transition-colors truncate"
                >
                  <Play size={12} className="shrink-0 text-neutral-grey-20" />
                  <span className="truncate">{videoLabel(v.url)}</span>
                </a>
                {v.source_page && (
                  <a
                    href={v.source_page}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`Source: ${v.source_page}`}
                    className="shrink-0 text-neutral-grey-20 hover:text-primary-white transition-colors"
                  >
                    <ExternalLink size={12} />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </DashboardCard>
  );
}

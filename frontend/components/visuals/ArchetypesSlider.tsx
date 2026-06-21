"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useBrandArchetypes } from "@/lib/branding/hooks";
import { ArchetypeCard } from "./ArchetypeCard";

const TRACK_GAP_PX = 16; // matches the track's gap-4

export function ArchetypesSlider() {
  const { data, isLoading, isError, error } = useBrandArchetypes();
  const [index, setIndex] = useState(0);
  const [offsetPx, setOffsetPx] = useState(0);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);

  const count = data?.archetypes.length ?? 0;

  useEffect(() => {
    const offset = cardRefs.current
      .slice(0, index)
      .reduce((sum, el) => sum + (el ? el.offsetWidth + TRACK_GAP_PX : 0), 0);
    setOffsetPx(offset);
  }, [index, count]);

  if (isLoading) {
    return (
      <div className="flex gap-4 overflow-x-hidden">
        {Array.from({ length: 3 }).map((_, i) => (
          <ZoneSkeleton key={i} height={280} />
        ))}
      </div>
    );
  }
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.archetypes.length === 0) {
    return <ZoneEmpty message="No brand archetype analysis available yet." />;
  }

  const canPrev = index > 0;
  const canNext = index < count - 1;

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-hidden">
        <div
          className="flex gap-4 transition-transform duration-300 ease-out"
          style={{ transform: `translateX(-${offsetPx}px)` }}
        >
          {data.archetypes.map((archetype, i) => (
            <div
              key={archetype.name}
              ref={(el) => {
                cardRefs.current[i] = el;
              }}
            >
              <ArchetypeCard archetype={archetype} />
            </div>
          ))}
        </div>
      </div>

      {count > 1 && (
        <div className="flex items-center justify-between gap-6">
          <div className="flex items-center gap-1.5 flex-1">
            {data.archetypes.map((archetype, i) => (
              <button
                key={archetype.name}
                type="button"
                onClick={() => setIndex(i)}
                aria-label={`Go to ${archetype.name}`}
                aria-current={i === index}
                className={`h-0.75 flex-1 rounded-full transition-colors cursor-pointer ${
                  i === index ? "bg-secondary-green" : "bg-white/15 hover:bg-white/30"
                }`}
              />
            ))}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setIndex((v) => Math.max(0, v - 1))}
              disabled={!canPrev}
              aria-label="Previous archetype"
              className="w-8 h-8 rounded-full border border-white/15 flex items-center justify-center text-neutral-grey-10 hover:border-white/30 hover:text-primary-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              <ArrowLeft size={14} />
            </button>
            <button
              type="button"
              onClick={() => setIndex((v) => Math.min(count - 1, v + 1))}
              disabled={!canNext}
              aria-label="Next archetype"
              className="w-8 h-8 rounded-full border border-white/15 flex items-center justify-center text-neutral-grey-10 hover:border-white/30 hover:text-primary-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

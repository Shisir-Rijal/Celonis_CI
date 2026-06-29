"use client";

import { useState } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";

type DeltaDirection = "up" | "down" | "flat";

type KpiTileProps = {
  label: string;
  value: string | number;
  suffix?: string;
  subtitle?: string;
  tooltip?: string;
  delta?: {
    value: number;
    direction?: DeltaDirection;
    label?: string;
  } | null;
  highlight?: boolean;
};

function inferDirection(value: number): DeltaDirection {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

const directionStyles: Record<DeltaDirection, string> = {
  up: "text-success",
  down: "text-error",
  flat: "text-neutral-grey-20",
};

const directionIcons: Record<DeltaDirection, React.ReactNode> = {
  up: <ArrowUp size={12} strokeWidth={2.5} />,
  down: <ArrowDown size={12} strokeWidth={2.5} />,
  flat: <Minus size={12} strokeWidth={2.5} />,
};

export default function KpiTile({
  label,
  value,
  suffix,
  subtitle,
  tooltip,
  delta,
  highlight = false,
}: KpiTileProps) {
  const [tipOpen, setTipOpen] = useState(false);

  const direction = delta
    ? delta.direction ?? inferDirection(delta.value)
    : null;

  return (
    <div
      className={twMerge(
        clsx(
          "relative rounded-sm border-2 border-neutral-grey-30 p-6",
          "flex flex-col gap-2 min-h-[170px]"
        )
      )}
    >
      {highlight ? (
        <div className="absolute top-0 left-0 right-0 h-[3px] bg-secondary-green" />
      ) : null}

      {/* Label row — with optional info icon */}
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          {label}
        </span>
        {tooltip ? (
          <span className="relative flex items-center">
            <button
              type="button"
              className="w-3.5 h-3.5 rounded-full border border-neutral-grey-20 flex items-center justify-center text-[8px] font-semibold text-neutral-grey-20 hover:border-neutral-grey-10 hover:text-neutral-grey-10 transition-colors cursor-default leading-none"
              onMouseEnter={() => setTipOpen(true)}
              onMouseLeave={() => setTipOpen(false)}
              aria-label={`Info: ${label}`}
            >
              i
            </button>
            {tipOpen && (
              <div
                className="absolute bottom-full left-0 mb-2 z-50 w-60 rounded-lg border border-white/10 bg-neutral-grey-00 px-3 py-2.5 shadow-xl"
                style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" }}
              >
                <p className="text-[11px] text-primary-black leading-relaxed">
                  {tooltip}
                </p>
              </div>
            )}
          </span>
        ) : null}
      </div>

      {/* Value + suffix */}
      <div className="flex items-baseline gap-1">
        <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
          {value}
        </span>
        {suffix ? (
          <span className="text-lg text-neutral-grey-20 font-normal">
            {suffix}
          </span>
        ) : null}
      </div>

      {subtitle ? (
        <span className="text-xs text-neutral-grey-20">{subtitle}</span>
      ) : null}

      {/* Delta */}
      {delta && direction ? (
        <div className="mt-auto pt-3">
          <div
            className={twMerge(
              clsx(
                "inline-flex items-center gap-1 text-xs font-medium",
                directionStyles[direction]
              )
            )}
          >
            {directionIcons[direction]}
            <span>
              {delta.value > 0 ? "+" : ""}
              {delta.value}
              {delta.label ? (
                <span className="text-neutral-grey-20 font-normal">
                  {" "}
                  {delta.label}
                </span>
              ) : null}
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

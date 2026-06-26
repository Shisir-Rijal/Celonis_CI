"use client";

import { useMemo, useState } from "react";

import { ZoneEmpty } from "@components/geo/ZoneState";
import { isHomeCompany } from "@/lib/competitors/highlight";
import { hexToHue } from "@/lib/visuals/colorMath";
import type { ColorSpectrumEntry } from "@/lib/branding/types";

type ColorTypeFilter = "primary" | "secondary";

// True hue-angle gradient (not approximate named CSS colors) so every band
// lines up exactly with the dots, which are placed by the same 0-360 hue
// value. `from 90deg` accounts for the dots' angle convention starting at
// the 3 o'clock position (cos/sin with hue=0) instead of conic-gradient's
// default 12 o'clock start.
const HUE_WHEEL_GRADIENT =
  "conic-gradient(from 90deg, hsl(0,75%,50%), hsl(60,75%,50%), hsl(120,75%,50%), hsl(180,75%,50%), hsl(240,75%,50%), hsl(300,75%,50%), hsl(360,75%,50%))";

export function HueWheel({ spectrum }: { spectrum: ColorSpectrumEntry[] }) {
  const [colorType, setColorType] = useState<ColorTypeFilter>("primary");

  const points = useMemo(() => {
    return spectrum
      .flatMap((entry) =>
        entry.usedBy
          .filter((u) => u.colorType === colorType)
          .map((u) => ({ company: u.company, hex: u.hex }))
      )
      .map((p) => ({ ...p, hue: hexToHue(p.hex) }))
      .filter((p): p is { company: string; hex: string; hue: number } => p.hue !== null);
  }, [spectrum, colorType]);

  const radius = 170;
  const labelGap = 16;
  const size = radius * 2 + 220;
  const center = size / 2;

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex items-center gap-1 bg-black border border-white/10 rounded-full p-0.5">
        {(["primary", "secondary"] as ColorTypeFilter[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setColorType(t)}
            className={`text-[11px] px-3 py-1 rounded-full capitalize transition-colors cursor-pointer ${
              colorType === t
                ? "bg-secondary-green text-primary-black font-medium"
                : "text-neutral-grey-20 hover:text-primary-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {!points.length ? (
        <ZoneEmpty message={`No chromatic ${colorType} colors to plot yet.`} />
      ) : (
        <div className="relative" style={{ width: size, height: size }}>
          <div
            className="absolute rounded-full opacity-25"
            style={{
              left: center - radius,
              top: center - radius,
              width: radius * 2,
              height: radius * 2,
              background: HUE_WHEEL_GRADIENT,
            }}
          />
          <div
            className="absolute rounded-full bg-black"
            style={{
              left: center - radius + 16,
              top: center - radius + 16,
              width: (radius - 16) * 2,
              height: (radius - 16) * 2,
            }}
          />
          {points.map((p, i) => {
            const angleRad = (p.hue * Math.PI) / 180;
            const cos = Math.cos(angleRad);
            const sin = Math.sin(angleRad);
            const x = center + radius * cos;
            const y = center + radius * sin;
            const labelX = center + (radius + labelGap) * cos;
            const labelY = center + (radius + labelGap) * sin;
            const home = isHomeCompany(p.company);
            const rightHalf = cos >= 0;

            return (
              <span key={`${p.company}-${i}`}>
                <span
                  title={`${p.company} · ${p.hex}`}
                  className={`absolute rounded-full shrink-0 ${
                    home ? "ring-2 ring-secondary-green" : "border border-white/30"
                  }`}
                  style={{ backgroundColor: p.hex, width: 14, height: 14, left: x - 7, top: y - 7 }}
                />
                <span
                  className={`absolute whitespace-nowrap text-[11px] ${
                    home ? "text-secondary-green font-medium" : "text-neutral-grey-10"
                  }`}
                  style={{
                    left: labelX,
                    top: labelY,
                    transform: rightHalf ? "translate(0, -50%)" : "translate(-100%, -50%)",
                  }}
                >
                  {p.company}
                </span>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

"use client";

import "leaflet/dist/leaflet.css";

import { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";

import type { EventItem } from "@/lib/events/types";
import { getCompetitorColor } from "@/lib/competitors/colors";

// ---------------------------------------------------------------------------
// Geocoding — city/country → [lat, lng]
// Keys ordered longest-first so "san francisco" matches before "san"
// ---------------------------------------------------------------------------

const CITY_COORDS: [string, [number, number]][] = [
  // North America — cities
  ["san francisco", [37.775, -122.419]],
  ["los angeles", [34.052, -118.244]],
  ["new york city", [40.713, -74.006]],
  ["mexico city", [19.433, -99.133]],
  ["salt lake city", [40.761, -111.891]],
  ["washington dc", [38.907, -77.037]],
  ["washington d.c", [38.907, -77.037]],
  ["san diego", [32.716, -117.162]],
  ["san jose", [37.338, -121.886]],
  ["new york", [40.713, -74.006]],
  ["las vegas", [36.175, -115.136]],
  ["chicago", [41.878, -87.630]],
  ["houston", [29.760, -95.370]],
  ["seattle", [47.606, -122.332]],
  ["toronto", [43.651, -79.347]],
  ["atlanta", [33.749, -84.388]],
  ["boston", [42.361, -71.058]],
  ["denver", [39.739, -104.984]],
  ["dallas", [32.777, -96.797]],
  ["austin", [30.267, -97.743]],
  ["miami", [25.774, -80.194]],
  ["phoenix", [33.448, -112.074]],
  ["portland", [45.523, -122.676]],
  ["montreal", [45.502, -73.569]],
  ["vancouver", [49.283, -123.121]],
  ["calgary", [51.048, -114.070]],
  ["ottawa", [45.421, -75.690]],
  // South America
  ["são paulo", [-23.550, -46.634]],
  ["sao paulo", [-23.550, -46.634]],
  ["buenos aires", [-34.603, -58.382]],
  ["rio de janeiro", [-22.906, -43.172]],
  ["bogotá", [4.710, -74.073]],
  ["bogota", [4.710, -74.073]],
  ["lima", [-12.046, -77.043]],
  ["santiago", [-33.459, -70.649]],
  ["montevideo", [-34.901, -56.165]],
  ["medellín", [6.252, -75.564]],
  // Europe
  ["amsterdam", [52.367, 4.904]],
  ["frankfurt", [50.110, 8.682]],
  ["barcelona", [41.387, 2.170]],
  ["stockholm", [59.333, 18.065]],
  ["copenhagen", [55.676, 12.568]],
  ["edinburgh", [55.953, -3.188]],
  ["brussels", [50.846, 4.352]],
  ["budapest", [47.498, 19.040]],
  ["helsinki", [60.169, 24.935]],
  ["zurich", [47.376, 8.541]],
  ["zürich", [47.376, 8.541]],
  ["lisbon", [38.717, -9.138]],
  ["hamburg", [53.551, 9.993]],
  ["münchen", [48.137, 11.576]],
  ["munich", [48.137, 11.576]],
  ["warsaw", [52.230, 21.012]],
  ["madrid", [40.417, -3.703]],
  ["london", [51.507, -0.128]],
  ["berlin", [52.520, 13.405]],
  ["vienna", [48.208, 16.373]],
  ["wien", [48.208, 16.373]],
  ["paris", [48.857, 2.351]],
  ["prague", [50.075, 14.438]],
  ["oslo", [59.913, 10.752]],
  ["rome", [41.902, 12.496]],
  ["milan", [45.465, 9.188]],
  ["geneva", [46.204, 6.143]],
  ["athens", [37.983, 23.727]],
  ["dublin", [53.350, -6.266]],
  // Asia Pacific
  ["kuala lumpur", [3.140, 101.687]],
  ["ho chi minh", [10.762, 106.660]],
  ["new zealand", [-40.900, 174.886]],
  ["hong kong", [22.320, 114.170]],
  ["bangalore", [12.971, 77.594]],
  ["bengaluru", [12.971, 77.594]],
  ["singapore", [1.352, 103.820]],
  ["shanghai", [31.228, 121.474]],
  ["beijing", [39.906, 116.391]],
  ["jakarta", [-6.208, 106.846]],
  ["bangkok", [13.756, 100.502]],
  ["auckland", [-36.866, 174.769]],
  ["sydney", [-33.869, 151.209]],
  ["mumbai", [19.076, 72.878]],
  ["tokyo", [35.690, 139.692]],
  ["taipei", [25.032, 121.565]],
  ["osaka", [34.693, 135.502]],
  ["seoul", [37.566, 126.978]],
  ["delhi", [28.614, 77.202]],
  // Middle East & Africa
  ["abu dhabi", [24.453, 54.377]],
  ["tel aviv", [32.085, 34.782]],
  ["cape town", [-33.926, 18.424]],
  ["addis ababa", [8.996, 38.763]],
  ["johannesburg", [-26.195, 28.034]],
  ["casablanca", [33.588, -7.612]],
  ["riyadh", [24.688, 46.722]],
  ["istanbul", [41.015, 28.980]],
  ["nairobi", [-1.292, 36.822]],
  ["dubai", [25.204, 55.270]],
  ["cairo", [30.044, 31.236]],
  ["lagos", [6.455, 3.385]],
  ["doha", [25.286, 51.533]],
  // Countries (fallback)
  ["germany", [51.165, 10.452]],
  ["france", [46.603, 1.888]],
  ["united kingdom", [55.378, -3.436]],
  ["netherlands", [52.132, 5.291]],
  ["sweden", [60.128, 18.643]],
  ["norway", [60.472, 8.469]],
  ["denmark", [56.263, 9.502]],
  ["finland", [61.924, 25.748]],
  ["switzerland", [46.818, 8.228]],
  ["austria", [47.516, 14.550]],
  ["spain", [40.463, -3.749]],
  ["italy", [41.872, 12.567]],
  ["poland", [51.920, 19.145]],
  ["portugal", [39.400, -8.225]],
  ["belgium", [50.503, 4.470]],
  ["ireland", [53.412, -8.244]],
  ["greece", [39.074, 21.824]],
  ["australia", [-25.275, 133.775]],
  ["canada", [56.130, -106.347]],
  ["brazil", [-14.235, -51.925]],
  ["india", [20.594, 78.963]],
  ["china", [35.862, 104.195]],
  ["japan", [36.205, 138.253]],
  ["singapore", [1.352, 103.820]],
  ["malaysia", [4.211, 101.976]],
  ["indonesia", [-0.789, 113.922]],
  ["south africa", [-30.559, 22.938]],
  ["nigeria", [9.082, 8.675]],
  ["kenya", [-0.023, 37.906]],
  ["turkey", [38.964, 35.243]],
  ["israel", [31.047, 34.852]],
  ["uae", [23.424, 53.848]],
  ["usa", [37.090, -95.713]],
  ["united states", [37.090, -95.713]],
  ["mexico", [23.635, -102.553]],
  ["argentina", [-38.416, -63.617]],
  ["colombia", [4.571, -74.297]],
];

export function getCoordinates(location: string | null): [number, number] | null {
  if (!location) return null;
  const lower = location.toLowerCase();
  for (const [key, coords] of CITY_COORDS) {
    if (lower.includes(key)) return coords;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Region bounds for auto-zoom
// ---------------------------------------------------------------------------

export const REGION_BOUNDS: Record<string, LatLngBoundsExpression> = {
  "Online / Virtual": [[-60, -160], [75, 165]],
  "Europe":           [[34,  -12], [71,  44]],
  "North America":    [[14, -170], [76, -50]],
  "South America":    [[-57,  -84], [16, -32]],
  "Asia Pacific":     [[-48,   92], [58, 180]],
  "Middle East & Africa": [[-36, -20], [43, 66]],
  "Other":            [[-60, -160], [75, 165]],
};

// ---------------------------------------------------------------------------
// Map controller — handles programmatic zoom via useMap()
// ---------------------------------------------------------------------------

function MapController({ region }: { region: string }) {
  const map = useMap();
  const prevRegion = useRef("");

  useEffect(() => {
    if (region === prevRegion.current) return;
    prevRegion.current = region;
    if (region && REGION_BOUNDS[region]) {
      map.fitBounds(REGION_BOUNDS[region], { padding: [30, 30], maxZoom: 6 });
    } else {
      map.setView([20, 10], 2);
    }
  }, [region, map]);

  return null;
}

// ---------------------------------------------------------------------------
// Popup dark-theme CSS injected once
// ---------------------------------------------------------------------------

const POPUP_CSS = `
  .leaflet-popup-content-wrapper {
    background: #1D1D1D;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    color: #f5f5f5;
    padding: 0;
  }
  .leaflet-popup-content { margin: 0; }
  .leaflet-popup-tip { background: #1D1D1D; }
  .leaflet-popup-close-button { color: #767676 !important; top: 8px !important; right: 8px !important; }
  .leaflet-popup-close-button:hover { color: #f5f5f5 !important; }
`;

// ---------------------------------------------------------------------------
// EventsMapCore — the actual Leaflet map (no SSR)
// ---------------------------------------------------------------------------

type EventsMapCoreProps = {
  events: EventItem[];
  allCompanies: string[];
  brandColors: Record<string, string>;
  region: string;
};

export default function EventsMapCore({ events, allCompanies, brandColors, region }: EventsMapCoreProps) {
  // Inject popup CSS once
  useEffect(() => {
    const style = document.createElement("style");
    style.textContent = POPUP_CSS;
    document.head.appendChild(style);
    return () => style.remove();
  }, []);

  // Build positioned events (skip those with no resolvable coordinates)
  type PositionedEvent = { event: EventItem; lat: number; lng: number };
  const positioned: PositionedEvent[] = [];

  // Tiny jitter for events at identical coordinates
  const seen: Record<string, number> = {};
  for (const event of events) {
    const coords = getCoordinates(event.location);
    if (!coords) continue;
    const key = `${coords[0]},${coords[1]}`;
    const count = seen[key] ?? 0;
    seen[key] = count + 1;
    const jitter = count * 0.18;
    positioned.push({
      event,
      lat: coords[0] + jitter * Math.cos(count),
      lng: coords[1] + jitter * Math.sin(count),
    });
  }

  return (
    <MapContainer
      center={[20, 10]}
      zoom={2}
      minZoom={1}
      maxZoom={14}
      maxBounds={[[-85, -180], [85, 180]]}
      maxBoundsViscosity={1.0}
      style={{ height: "100%", width: "100%", background: "#1D1D1D" }}
      className="rounded-b-lg"
    >
      {/* Dark CartoDB tiles — no API key required */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        subdomains="abcd"
        maxZoom={19}
      />

      <MapController region={region} />

      {positioned.map(({ event, lat, lng }, i) => {
        const color = getCompetitorColor(event.company, allCompanies, brandColors);
        return (
          <CircleMarker
            key={`${event.company}-${event.event_date ?? i}-${i}`}
            center={[lat, lng]}
            radius={7}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: 0.85,
              weight: 1.5,
            }}
          >
            <Popup minWidth={200} maxWidth={280}>
              <div className="p-3 flex flex-col gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className="text-[10px] tracking-[0.12em] uppercase font-medium px-2 py-0.5 rounded-sm"
                    style={{ backgroundColor: `${color}25`, color }}
                  >
                    {event.company}
                  </span>
                  {event.event_topic && (
                    <span className="text-[10px] text-neutral-grey-20">
                      {event.event_topic}
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium text-primary-white leading-snug">
                  {event.name ?? event.title ?? "Untitled"}
                </p>
                {event.event_date && (
                  <p className="text-[11px] text-neutral-grey-20">
                    {new Date(event.event_date + "T12:00:00").toLocaleDateString("en-US", {
                      month: "short", day: "numeric", year: "numeric",
                    })}
                    {event.location ? ` · ${event.location}` : ""}
                  </p>
                )}
                {event.source_link && (
                  <a
                    href={event.source_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium"
                    style={{ color: "#5CFE50" }}
                  >
                    View event →
                  </a>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
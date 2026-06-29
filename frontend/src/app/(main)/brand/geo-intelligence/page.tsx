import NextDynamic from "next/dynamic";

export const dynamic = "force-dynamic";

const GeoIntelligenceClient = NextDynamic(
  () => import("./GeoIntelligenceClient"),
  { ssr: false }
);

export default function Page() {
  return <GeoIntelligenceClient />;
}

import DashboardCard from "./DashboardCard";

/**
 * Loading skeleton — a softly pulsing grey block inside the standard card
 * surface. Sized to match the chart area it replaces so the layout doesn't
 * jump when data arrives.
 */
export function ZoneSkeleton({ height = 200 }: { height?: number }) {
  return (
    <DashboardCard className="animate-pulse">
      <div
        style={{ height }}
        className="w-full rounded-md bg-neutral-grey-00"
      />
    </DashboardCard>
  );
}

/**
 * Error block — quiet by design. The full error is logged via apiFetch
 * already; the user just needs to know the section didn't load.
 */
export function ZoneError({ message }: { message?: string }) {
  return (
    <DashboardCard>
      <div className="flex flex-col gap-1.5 text-sm">
        <span className="text-error font-medium">
          Could not load this section.
        </span>
        {message ? (
          <span className="text-neutral-grey-20">{message}</span>
        ) : null}
      </div>
    </DashboardCard>
  );
}

/**
 * Empty state — distinct from an error. Used when no pipeline runs exist
 * yet for the requested company.
 */
export function ZoneEmpty({ message }: { message: string }) {
  return (
    <DashboardCard>
      <div className="text-sm text-neutral-grey-20">{message}</div>
    </DashboardCard>
  );
}

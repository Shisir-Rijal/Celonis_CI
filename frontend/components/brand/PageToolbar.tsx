import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type PageToolbarProps = {
  runtime?: string;
  updatedAt?: string;
  agentsRunning?: number;
  className?: string;
};

/**
 * Compact freshness + activity indicator. Sits in the page header opposite
 * the title. The green pulse is the only motion on the page above the fold,
 * intentional — it signals liveness without distracting from the numbers.
 */
export default function PageToolbar({
  runtime,
  updatedAt,
  agentsRunning,
  className,
}: PageToolbarProps) {
  return (
    <div
      className={twMerge(
        clsx("flex items-center gap-6 text-sm", className)
      )}
    >
      {runtime ? (
        <div className="flex items-center gap-1.5 text-neutral-grey-20">
          <span className="text-xs">Runs</span>
          <span className="text-primary-white font-medium">{runtime}</span>
        </div>
      ) : null}

      {updatedAt ? (
        <div className="flex items-center gap-1.5 text-neutral-grey-20">
          <span className="text-xs">Updated</span>
          <span className="text-primary-white font-medium">{updatedAt}</span>
        </div>
      ) : null}

      {agentsRunning !== undefined ? (
        <div className="flex items-center gap-2 text-neutral-grey-20">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full rounded-full bg-secondary-green opacity-60 animate-ping" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-secondary-green" />
          </span>
          <span>
            <span className="text-primary-white font-medium">
              {agentsRunning}
            </span>{" "}
            {agentsRunning === 1 ? "agent" : "agents"} running
          </span>
        </div>
      ) : null}
    </div>
  );
}

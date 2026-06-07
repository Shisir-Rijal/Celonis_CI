import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type SectionHeaderProps = {
  label: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
};

/**
 * Section header — title above each dashboard zone. The title is set in
 * sentence case (not uppercase eyebrow) so it carries enough weight to
 * anchor the zone. Optional description sits right under it; optional
 * action (link, button) is right-aligned.
 */
export default function SectionHeader({
  label,
  description,
  action,
  className,
}: SectionHeaderProps) {
  return (
    <div
      className={twMerge(
        clsx(
          "flex items-end justify-between w-full mb-5 gap-4",
          className
        )
      )}
    >
      <div className="flex flex-col">
        <h3 className="text-lg font-medium text-primary-black leading-tight">
          {label}
        </h3>
        {description ? (
          <p className="mt-1 text-sm text-neutral-grey-20">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

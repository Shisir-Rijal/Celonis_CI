import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type DerivationNoteProps = {
  title: string;
  children: React.ReactNode;
  className?: string;
};

/**
 * The grey-bar footnote under a chart that interprets what the numbers
 * mean. Bold title with em-dash, then one or two sentences of analytical
 * interpretation — gives the chart meaning without pushing the user to
 * read a paragraph elsewhere.
 */
export default function DerivationNote({
  title,
  children,
  className,
}: DerivationNoteProps) {
  return (
    <div
      className={twMerge(
        clsx(
          "border-l-2 border-neutral-grey-10 pl-4 mt-5 text-sm text-neutral-grey-20",
          className
        )
      )}
    >
      <span className="font-medium text-primary-black">{title} —</span>{" "}
      {children}
    </div>
  );
}

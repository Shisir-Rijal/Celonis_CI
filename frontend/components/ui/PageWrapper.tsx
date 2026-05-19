import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type PageWrapperProps = {
  children: React.ReactNode;
};

export default function PageWrapper({
  children,
}: PageWrapperProps) {
  return (
    <div
      className={twMerge(
        clsx(
          "flex flex-col gap-24 px-16 py-22 justify-start items-start",
        )
      )}
    >
      {children}
    </div>
  );
}

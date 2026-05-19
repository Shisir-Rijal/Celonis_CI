import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type SectionWrapperProps = {
  variant?: "white" | "grey";
  size?: "full" | "half" | "drittel" | "zweidrittel";
  children: React.ReactNode;
  heading: string;
};

const variantStyles = {
  white: "bg-primary-white text-primary-black",
  grey: "bg-neutral-grey-00 text-primary-black p-16",
};

const sizeStyles = {
  full: "w-full",
  half: "w-1/2",
  drittel: "w-1/3",
  zweidrittel: "w-2/3",
};

export default function SectionWrapper({
  variant = "white",
  size = "full",
  children,
  heading,
}: SectionWrapperProps) {
  return (
    <section
      className={twMerge(
        clsx(
          "flex flex-col gap-4 rounded py-6",
          sizeStyles[size],
          variantStyles[variant]
        )
      )}
    >
      <h2>{heading}</h2>
      {children}
    </section>
  );
}

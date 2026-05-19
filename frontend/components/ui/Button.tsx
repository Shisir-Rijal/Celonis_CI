import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type ButtonProps = {
  variant?: "primary" | "secondary";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
};

const variantStyles = {
  primary:
    "bg-primary-black text-primary-white hover:opacity-90 active:opacity-80",
  secondary:
    "bg-primary-white text-primary-black hover:bg-natural-20 hover:text-primary-white",
};

const sizeStyles = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-base",
  lg: "px-7 py-3.5 text-lg",
};

export default function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  children,
  onClick,
  type = "button",
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={twMerge(
        clsx(
          "inline-flex items-center justify-center rounded font-sans transition-opacity cursor-pointer w-fit",
          variantStyles[variant],
          sizeStyles[size],
          disabled && "opacity-40 cursor-not-allowed pointer-events-none"
        )
      )}
    >
      {children}
    </button>
  );
}

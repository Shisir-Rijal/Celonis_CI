"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ReactNode } from "react";

type NavButtonProps = {
  text?: string;
  href: string;
  icon?: ReactNode;
  onClick?: () => void;
};

export default function NavButton({
  text,
  href,
  icon,
  onClick,
}: NavButtonProps) {
  const pathname = usePathname();
  const isActive = pathname === href;

  return (
    <Link
      href={href}
      onClick={onClick}
      title={text}
      className={twMerge(
        clsx(
          "flex items-center px-4 py-2 font-sans text-sm transition-colors cursor-pointer border-b",
          isActive
            ? "border-secondary-green text-secondary-green"
            : "border-transparent text-neutral-grey-20 hover:text-primary-white hover:border-neutral-grey-20"
        )
      )}
    >
      {icon}
      <h4>{text}</h4>
    </Link>
  );
}

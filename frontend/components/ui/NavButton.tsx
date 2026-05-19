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
          "flex items-center gap-8 w-full px-2 py-2 font-sans text-sm transition-colors cursor-pointer border-b",
          isActive
            ? "border-transparent text-secondary-green"
            : "border-transparent text-neutral-grey-10 hover:border-primary-white"
        )
      )}
    >
      {icon}
      <h4>{text}</h4>
    </Link>
  );
}

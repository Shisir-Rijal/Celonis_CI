"use client";

import { useState } from "react";
import Image from "next/image";
import { usePathname, useSearchParams } from "next/navigation";
import NavButton from "./NavButton";
import MobileMenu from "./MobileMenu";
import { Menu } from "lucide-react";
import ExportButton from "@components/report/ExportButton";

const TOPIC_MAP: Record<string, "news" | "events" | "geo" | "branding" | "sov"> = {
  "/news": "news",
  "/events": "events",
  "/brand/geo-intelligence": "geo",
  "/branding": "branding",
  "/sov": "sov",
};

export default function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const topic = TOPIC_MAP[pathname] ?? null;

  const companies = topic && searchParams.get("companies")
    ? searchParams.get("companies")!.split(",").filter(Boolean)
    : [];

  return (
    <>
      <nav className="hidden lg:flex flex-row items-center bg-primary-black text-primary-white h-16 px-16 fixed top-0 left-0 right-0 z-20">
        <div className="flex-shrink-0">
          <Image
            src="/celonis_logo.png"
            alt="Celonis Logo"
            width={120}
            height={40}
            className="h-8 w-auto object-contain"
          />
        </div>

        <div className="flex flex-row flex-1 justify-center gap-2">
          <NavButton text="Home" href="/" />
          <NavButton text="Branding" href="/branding" />
          <NavButton text="GEO" href="/brand/geo-intelligence" />
          <NavButton text="Events" href="/events" />
          <NavButton text="News" href="/news" />
          <NavButton text="SoV" href="/sov" />
          <NavButton text="Chatbot" href="/chatbot" />
          <NavButton text="Settings" href="/settings" />
        </div>

        {topic ? (
          <div className="bg-secondary-green text-primary-black px-4 py-2 text-sm font-medium rounded-sm flex-shrink-0">
            <ExportButton topic={topic} companies={companies} />
          </div>
        ) : (
          <button
            disabled
            className="bg-secondary-green text-primary-black px-4 py-2 text-sm font-medium rounded-sm opacity-40 cursor-not-allowed flex-shrink-0"
          >
            Report ↗
          </button>
        )}
      </nav>

      <header className="lg:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between bg-primary-black text-primary-white px-4 py-3">
        <Image
          src="/celonis_logo.png"
          alt="Celonis Logo"
          width={80}
          height={80}
          className="h-8 w-auto object-contain"
        />
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          className="text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
          aria-label="Menü öffnen"
        >
          <Menu size={24} />
        </button>
      </header>

      <MobileMenu isOpen={menuOpen} onClose={() => setMenuOpen(false)} />
    </>
  );
}

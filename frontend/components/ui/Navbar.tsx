"use client";

import { useState } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import NavButton from "./NavButton";
import MobileMenu from "./MobileMenu";
import { Menu } from "lucide-react";

export default function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();
  const showExport = pathname !== "/chatbot";

  return (
    <>
      {/* Desktop topbar — visible on lg+ */}
      <nav className="hidden lg:flex flex-row items-center bg-primary-black text-primary-white h-16 px-16 fixed top-0 left-0 right-0 z-20">
        {/* Logo left */}
        <div className="flex-shrink-0">
          <Image
            src="/celonis_logo.png"
            alt="Celonis Logo"
            width={120}
            height={40}
            className="h-8 w-auto object-contain"
          />
        </div>

        {/* Nav links center */}
        <div className="flex flex-row flex-1 justify-center gap-2">
          <NavButton text="Home" href="/" />
          <NavButton text="Branding" href="/branding" />
          <NavButton text="GEO" href="/brand/geo-intelligence" />
          <NavButton text="Events" href="/events" />
          <NavButton text="News" href="/news" />
          <NavButton text="Chatbot" href="/chatbot" />
          <NavButton text="Settings" href="/settings" />
        </div>

        {/* Export button right */}
        {showExport ? (
          <button className="bg-secondary-green text-primary-black px-4 py-2 text-sm font-medium rounded-sm cursor-pointer hover:opacity-90 transition-opacity flex-shrink-0">
            Export
          </button>
        ) : (
          <div className="w-[88px] flex-shrink-0" aria-hidden />
        )}
      </nav>

      {/* Mobile topbar — visible on md and below */}
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

      {/* Mobile slide-in menu */}
      <MobileMenu isOpen={menuOpen} onClose={() => setMenuOpen(false)} />
    </>
  );
}

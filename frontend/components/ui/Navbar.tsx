"use client";

import { useState } from "react";
import Image from "next/image";
import NavButton from "./NavButton";
import MobileMenu from "./MobileMenu";
import { Menu } from "lucide-react";

export default function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar — visible on lg+ */}
      <nav className="hidden lg:flex flex-col bg-primary-black text-primary-white h-screen w-36 px-6 py-6 fixed left-0 top-0 z-20">
        <div className="mb-8 w-full">
          <Image
            src="/celonis_logo.png"
            alt="Celonis Logo"
            width={160}
            height={160}
            className="w-full h-auto object-contain"
          />
        </div>

        <div className="flex flex-col gap-1 flex-1">
          <NavButton text="Home" href="/" />
          <NavButton text="GEO" href="/brand/geo-intelligence" />
          <NavButton text="News" href="/news" />
          <NavButton text="Chatbot" href="/chatbot" />
        </div>

        <div className="flex flex-col gap-2">
          <NavButton text="Settings" href="/settings" />
        </div>
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

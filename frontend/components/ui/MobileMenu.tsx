"use client";

import Image from "next/image";
import NavButton from "./NavButton";

type MobileMenuProps = {
  isOpen: boolean;
  onClose: () => void;
};

export default function MobileMenu({ isOpen, onClose }: MobileMenuProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-300"
        style={{ opacity: isOpen ? 1 : 0, pointerEvents: isOpen ? "auto" : "none" }}
      />

      {/* Slide-in panel */}
      <div
        className="fixed top-0 left-0 z-50 flex flex-col h-screen w-56 bg-primary-black text-primary-white px-6 py-6 transition-transform duration-300 ease-in-out"
        style={{ transform: isOpen ? "translateX(0)" : "translateX(-100%)" }}
      >
        {/* Logo + Close */}
        <div className="flex items-center justify-between mb-8 w-full">
          <Image
            src="/celonis_logo.png"
            alt="Celonis Logo"
            width={100}
            height={100}
            className="h-auto object-contain"
          />
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-grey-10 hover:text-primary-white transition-colors cursor-pointer"
            aria-label="Menü schließen"
          >
            ✕
          </button>
        </div>

        {/* Nav Items */}
        <div className="flex flex-col gap-1 flex-1">
          <NavButton text="Home" href="/" onClick={onClose} />
          <NavButton text="GEO" href="/brand/geo-intelligence" onClick={onClose} />
          <NavButton text="News" href="/news" onClick={onClose} />
          <NavButton text="SoV" href="/sov" onClick={onClose} />
          <NavButton text="Chatbot" href="/chatbot" onClick={onClose} />
        </div>

        {/* Bottom */}
        <div className="flex flex-col gap-2">
          <NavButton text="Settings" href="/settings" onClick={onClose} />
        </div>
      </div>
    </>
  );
}

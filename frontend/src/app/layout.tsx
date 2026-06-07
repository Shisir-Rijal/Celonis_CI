import type { Metadata } from "next";
import { poppins } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Celonis Competitor Dashboard",
  description: "Internal Celonis Competitor Comparison Dashboard using AI agents",
};

/**
 * Root layout — HTML shell only, no NavBar.
 * NavBar lives in (main)/layout.tsx so /login stays clean.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${poppins.variable} h-full antialiased`}
    >
      <body className="min-h-screen">
        {children}
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { poppins } from "@/lib/fonts";
import "./globals.css";
import NavBar from "../../components/ui/Navbar";
import PageWrapper from "../../components/ui/PageWrapper";

export const metadata: Metadata = {
  title: "Celonis Competitor Dashboard",
  description: "Internal Celonis Competitor Comparison Dashboard using AI agents",
};

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
      <body className="min-h-full flex flex-row">
        <NavBar/>
        <PageWrapper
          children={children}
        />
      </body>
    </html>
  );
}

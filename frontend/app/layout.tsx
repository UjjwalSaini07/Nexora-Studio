import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "NEXORA Ops Dashboard",
  description: "Live operations dashboard for the NEXORA merchant engagement engine.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-nexora-bg text-nexora-text relative overflow-x-hidden">
        {/* Background Ambient Glow Orbs */}
        <div className="absolute top-[-100px] left-[-200px] glow-orb-1 pointer-events-none" />
        <div className="absolute top-[30%] right-[-200px] glow-orb-2 pointer-events-none" />
        <div className="absolute bottom-[-100px] left-[15%] glow-orb-3 pointer-events-none" />

        <NavBar />
        <main className="flex-1 mx-auto w-full max-w-7xl px-6 py-8 relative z-10">{children}</main>
      </body>
    </html>
  );
}

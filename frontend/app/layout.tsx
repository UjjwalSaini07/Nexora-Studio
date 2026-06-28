import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";
import { Footer } from "@/components/Footer";
import { Preloader } from "@/components/Preloader";

export const metadata: Metadata = {
  title: "NEXORA Ops Dashboard",
  description: "Live operations, diagnostics, and SLA monitoring dashboard for the NEXORA merchant engagement engine.",
  authors: [{ name: "Ujjwal Saini", url: "https://ujjwalsaini.vercel.app" }],
  creator: "Ujjwal Saini",
  publisher: "NEXORA Engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased overflow-y-auto overflow-x-hidden" suppressHydrationWarning>
      <body className="min-h-screen flex flex-col bg-nexora-bg text-nexora-text relative">
        <Preloader />
        
        <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
          <div className="absolute top-[-100px] left-[-200px] glow-orb-1" />
          <div className="absolute top-[30%] right-[-200px] glow-orb-2" />
          <div className="absolute bottom-[-100px] left-[15%] glow-orb-3" />
        </div>

        <NavBar />
        
        <main className="flex-1 mx-auto w-full max-w-7xl px-6 py-8 relative z-10">
          {children}
        </main>

        <Footer />
      </body>
    </html>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/conversations", label: "Conversations" },
  { href: "/contexts", label: "Contexts" },
  { href: "/simulator", label: "Simulator" },
  { href: "/scores", label: "Scores" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="glass-header sticky top-0 z-30">
      <div className="mx-auto max-w-7xl px-6 flex items-center justify-between h-16">
        <Link href="/" className="flex items-center gap-2 shrink-0 group">
          <div className="flex items-center ">
            <img src="/nexoraLogo.png" alt="NEXORA AI Logo" className="w-16 h-16 object-contain shrink-0" />
            <div>
              <span className="font-mono text-md font-bold tracking-wider text-white transition-all duration-300 group-hover:text-indigo-400 group-hover:[text-shadow:0_0_12px_rgba(99,102,241,0.5)]">
                NEXORA AI
              </span>
              <span className="text-[9px] ml-2 uppercase tracking-widest font-extrabold text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded px-1.5 py-0.5 shadow-[0_0_8px_rgba(99,102,241,0.1)]">
                ops
              </span>
            </div>
          </div>
        </Link>
        <nav className="flex items-center gap-1.5">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-250 border ${
                  active
                    ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/25 shadow-[0_0_15px_rgba(99,102,241,0.15)]"
                    : "text-slate-400 hover:text-white hover:bg-white/5 border-transparent"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

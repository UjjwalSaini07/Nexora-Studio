// frontend/components/NavBar.tsx
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
    <header className="border-b border-nexora-border bg-nexora-surface/80 backdrop-blur sticky top-0 z-30">
      <div className="mx-auto max-w-7xl px-6 flex items-center gap-8 h-14">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-sm font-bold tracking-tight text-nexora-text-bright">NEXORA</span>
          <span className="text-[10px] uppercase tracking-wider text-nexora-muted border border-nexora-border rounded px-1.5 py-0.5">
            ops
          </span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 rounded-md transition-colors ${
                  active
                    ? "bg-nexora-accent/15 text-nexora-accent font-medium"
                    : "text-nexora-muted hover:text-nexora-text hover:bg-nexora-surface-raised"
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

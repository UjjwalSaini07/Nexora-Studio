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
    <header className="border-b border-vera-border bg-vera-surface/80 backdrop-blur sticky top-0 z-30">
      <div className="mx-auto max-w-7xl px-6 flex items-center gap-8 h-14">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-sm font-bold tracking-tight text-vera-text-bright">VERA</span>
          <span className="text-[10px] uppercase tracking-wider text-vera-muted border border-vera-border rounded px-1.5 py-0.5">
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
                    ? "bg-vera-accent/15 text-vera-accent font-medium"
                    : "text-vera-muted hover:text-vera-text hover:bg-vera-surface-raised"
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

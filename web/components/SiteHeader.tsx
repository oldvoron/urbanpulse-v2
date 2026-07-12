"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PlaceholderModalProvider, AuthButtons } from "./PlaceholderAuthModal";

const NAV = [
  { href: "/", label: "Analyze" },
  { href: "/compare", label: "Compare" },
  { href: "/history", label: "History" },
  { href: "/pricing", label: "Pricing" },
  { href: "/account", label: "Account" },
];

export default function SiteHeader() {
  const pathname = usePathname();
  if (pathname?.startsWith("/embed/")) return null; // chrome-less embeds

  return (
    <PlaceholderModalProvider>
      <header className="border-b border-edge bg-panel/60 backdrop-blur sticky top-0 z-40">
        <div className="mx-auto max-w-[1600px] px-4 h-12 flex items-center gap-6">
          <Link href="/" className="flex items-baseline gap-2 shrink-0">
            <span className="font-mono font-bold tracking-tight text-ink">
              URBAN<span className="text-accent-transport">PULSE</span>
            </span>
            <span className="font-mono text-[10px] text-ink-faint">v2</span>
          </Link>
          <nav className="flex items-center gap-1 text-sm flex-1">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-1.5 rounded transition-colors ${
                  pathname === item.href
                    ? "text-accent-transport bg-accent-transport/10"
                    : "text-ink-dim hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <AuthButtons />
        </div>
      </header>
    </PlaceholderModalProvider>
  );
}

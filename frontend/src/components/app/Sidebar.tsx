"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "Overview", href: "/app/overview", icon: "⊡" },
  { label: "Calls", href: "/app/calls", icon: "◎" },
  { label: "Agents", href: "/app/agents", icon: "↗" },
  { label: "Teams", href: "/app/teams", icon: "⊛" },
  { label: "Upload", href: "/app/upload", icon: "↑" },
  { label: "Rubrics", href: "/app/rubrics", icon: "◻", placeholder: true },
  { label: "Search", href: "/app/search", icon: "⌕", placeholder: true },
  { label: "Settings", href: "/app/settings", icon: "⌇", placeholder: true },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex h-14 items-center border-b border-border px-5">
        <span className="font-display text-lg font-bold italic text-foreground">
          CallLens
        </span>
      </div>

      <nav className="flex flex-col gap-0.5 p-3 text-sm">
        {navItems.map(({ label, href, icon, placeholder }) => {
          const isActive =
            href === "/app/overview"
              ? pathname === "/app/overview"
              : href === "/app/calls"
                ? pathname.startsWith("/app/calls")
                : href === "/app/agents"
                  ? pathname.startsWith("/app/agents")
                  : href === "/app/teams"
                    ? pathname.startsWith("/app/teams")
                    : href === "/app/upload"
                      ? pathname === "/app/upload"
                      : pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
                placeholder && !isActive && "opacity-50"
              )}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="text-base leading-none">{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

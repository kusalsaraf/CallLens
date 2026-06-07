"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { type UserOut } from "@/lib/api/auth";
import { useAuth } from "@/providers/AuthProvider";

interface TopBarProps {
  user: UserOut;
}

export function TopBar({ user }: TopBarProps) {
  const { logout } = useAuth();
  const [dark, setDark] = useState(false);

  const toggleDark = useCallback(() => {
    setDark((d) => {
      const next = !d;
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  }, []);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-6">
      <Link
        href="/app/upload"
        className="inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
      >
        + Upload recording
      </Link>
      <div className="flex items-center gap-3">
        <button
          onClick={toggleDark}
          aria-label="Toggle dark mode"
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          {dark ? "☀" : "☾"}
        </button>

        <div className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{user.name}</span>
        </div>

        <Button variant="outline" size="sm" onClick={logout}>
          Log out
        </Button>
      </div>
    </header>
  );
}

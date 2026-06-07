export function Footer() {
  return (
    <footer className="border-t border-border px-6 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 md:flex-row md:items-center">
        <div>
          <p className="font-display text-lg font-bold italic text-foreground">
            CallLens
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            AI-powered call quality analytics
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} CallLens. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

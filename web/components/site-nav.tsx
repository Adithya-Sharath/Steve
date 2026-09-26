"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { LlmToggle } from "@/components/llm-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/listen", label: "Listen" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/eval", label: "Evaluation" },
  { href: "/check", label: "Check (teach-back)" },
];

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("font-display text-2xl leading-none", className)}>
      Steve
    </span>
  );
}

export function SiteNav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  if (path.startsWith("/r/")) return null; // reader page: calm, no chrome
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <nav aria-label="Main" className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="rounded-md" aria-label="Steve home">
          <Logo />
        </Link>
        <ul className="ml-4 hidden items-center gap-1 md:flex">
          {LINKS.map((l) => {
            const active = path === l.href || path.startsWith(l.href + "/");
            return (
              <li key={l.href}>
                <Link
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-sm transition-colors hover:bg-muted",
                    active ? "bg-muted font-medium text-foreground" : "text-muted-foreground",
                  )}
                >
                  {l.label}
                </Link>
              </li>
            );
          })}
        </ul>
        <div className="ml-auto flex items-center gap-2">
          <LlmToggle className="hidden sm:flex" />
          <ThemeToggle />
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </nav>
      {open && (
        <div className="border-t border-border bg-background px-4 pb-4 pt-2 md:hidden">
          <ul className="flex flex-col">
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2.5 text-sm hover:bg-muted">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
          <LlmToggle className="mt-3 px-3" />
        </div>
      )}
    </header>
  );
}

export function SiteFooter() {
  const path = usePathname();
  if (path.startsWith("/r/")) return null;
  return (
    <footer className="mt-24 border-t border-border/70">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>
          <Logo className="mr-2 text-lg text-foreground" /> Decodes what you hear into plain English. Text only; nothing you say or paste is stored. Not legal advice.
        </p>
        <p>
          Built for BitNBuild&apos;26 ·{" "}
          <a className="underline underline-offset-4 hover:text-foreground" href="https://github.com/Adithya-Sharath/Steve">
            GitHub
          </a>
        </p>
      </div>
    </footer>
  );
}

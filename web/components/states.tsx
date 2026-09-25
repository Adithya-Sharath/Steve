"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  body,
  action,
  icon,
  className,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("card-soft mx-auto flex max-w-lg flex-col items-center px-6 py-12 text-center", className)}
    >
      <div className="relative mb-5 grid size-20 place-items-center" aria-hidden>
        <svg viewBox="0 0 80 80" className="absolute inset-0 text-teal-soft" fill="currentColor">
          <path d="M40 4c17 0 34 10 36 28s-8 34-28 40S8 66 4 46 22 4 40 4Z" />
        </svg>
        <span className="relative text-primary">{icon ?? <Inbox className="size-8" />}</span>
      </div>
      <h2 className="font-display text-3xl">{title}</h2>
      <p className="mt-2 max-w-sm text-muted-foreground">{body}</p>
      {action && <div className="mt-6 flex flex-wrap justify-center gap-2">{action}</div>}
    </motion.div>
  );
}

export function ErrorState({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("card-soft mx-auto flex max-w-lg flex-col items-center px-6 py-10 text-center", className)}>
      <span className="mb-4 grid size-12 place-items-center rounded-full bg-wrong-soft text-wrong-ink">
        <AlertTriangle className="size-6" aria-hidden />
      </span>
      <h2 className="font-display text-2xl">Something went wrong</h2>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button className="mt-5" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function CardSkeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("card-soft p-5", className)} aria-hidden>
      <div className="shimmer h-5 w-2/5 rounded" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="shimmer mt-3 h-3 rounded" style={{ width: `${88 - i * 14}%` }} />
      ))}
    </div>
  );
}

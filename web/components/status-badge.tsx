"use client";

import { motion } from "framer-motion";
import { STATUS_META } from "@/lib/status";
import type { Status } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Never colour alone: every status has an icon AND a text label. */
export function StatusBadge({
  status,
  size = "md",
  className,
  animate = true,
}: {
  status: Status;
  size?: "sm" | "md" | "lg";
  className?: string;
  animate?: boolean;
}) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  return (
    <motion.span
      key={status}
      initial={animate ? { scale: 0.6, opacity: 0 } : false}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 520, damping: 22 }}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border font-medium",
        meta.chip,
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-2.5 py-1 text-xs",
        size === "lg" && "px-3.5 py-1.5 text-sm",
        className,
      )}
    >
      <Icon className={size === "lg" ? "size-4" : "size-3.5"} aria-hidden strokeWidth={2.5} />
      {meta.label}
    </motion.span>
  );
}

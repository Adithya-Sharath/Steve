"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { useAdminKey } from "@/lib/admin-key";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 20_000, retry: false });
}

/**
 * The "wrapper test" switch: with the LLM OFF the whole product must keep working.
 * It changes the LLM for EVERYONE, so it is admin-only: shown only when the server has an ADMIN_KEY (health says so)
 * AND this browser holds that key (entered on /admin). Everyone else never sees it (D30).
 */
export function LlmToggle({ className, label = true }: { className?: string; label?: boolean }) {
  const qc = useQueryClient();
  const { data } = useHealth();
  const adminKey = useAdminKey();
  const m = useMutation({
    mutationFn: (v: boolean) => api.setLlm(v, adminKey),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["health"] });
      toast(r.llm_enabled ? "LLM helper on" : "LLM off: everything still works", {
        description: r.llm_enabled
          ? "Gemini may suggest facts. It never judges a reply."
          : "Facts are extracted by rules, replies are checked by our engine.",
      });
    },
    onError: (e: Error) =>
      toast.error(e instanceof ApiError && e.status === 403 ? "The server did not accept that admin key" : "Could not reach the server"),
  });
  const on = data?.llm_switch ?? false;
  if (!data?.admin_toggle_available || !adminKey) return null;
  return (
    <label className={cn("flex cursor-pointer items-center gap-2 text-sm", className)}>
      <Sparkles className="size-4 text-muted-foreground" aria-hidden />
      {label && <span className="text-muted-foreground">LLM helper</span>}
      <Switch
        size="sm"
        checked={on}
        disabled={!data || m.isPending}
        onCheckedChange={(v) => m.mutate(Boolean(v))}
        aria-label="Toggle the optional LLM helper (wrapper test)"
      />
    </label>
  );
}

export function LlmOffBadge({ className }: { className?: string }) {
  const { data } = useHealth();
  if (!data || data.llm_enabled) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground",
        className,
      )}
      title="No LLM is involved in this result. The engine is deterministic code."
    >
      <span className="size-1.5 rounded-full bg-muted-foreground/60" aria-hidden />
      LLM off
    </span>
  );
}

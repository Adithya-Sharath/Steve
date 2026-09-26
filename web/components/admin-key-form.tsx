"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useHealth } from "@/components/llm-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { setAdminKey, useAdminKey } from "@/lib/admin-key";

export function AdminKeyForm() {
  const stored = useAdminKey();
  const { data } = useHealth();
  const [value, setValue] = useState("");

  return (
    <form
      className="card-soft mt-8 space-y-4 p-6"
      onSubmit={(e) => {
        e.preventDefault();
        const key = value.trim();
        if (!key) return;
        setAdminKey(key);
        setValue("");
        toast.success("Admin key saved in this browser");
      }}
    >
      <div className="space-y-2">
        <label htmlFor="admin-key" className="text-sm font-medium">
          Admin key
        </label>
        <Input
          id="admin-key"
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={stored ? "A key is saved (paste a new one to replace it)" : "Paste ADMIN_KEY"}
        />
      </div>
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {data === undefined
          ? "Checking the server…"
          : data.admin_toggle_available
            ? stored
              ? "The LLM switch is now shown in the top bar."
              : "This server has an admin key set. Paste it above to show the switch."
            : "This server has no ADMIN_KEY set, so the LLM switch is disabled and LLM_ENABLED decides."}
      </p>
      <div className="flex gap-3">
        <Button type="submit" disabled={!value.trim()}>
          Save key
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!stored}
          onClick={() => {
            setAdminKey("");
            toast("Admin key removed from this browser");
          }}
        >
          Forget key
        </Button>
      </div>
    </form>
  );
}

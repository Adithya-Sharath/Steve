import type { Metadata } from "next";
import { AdminKeyForm } from "@/components/admin-key-form";

export const metadata: Metadata = { title: "Admin", robots: { index: false, follow: false } };

/** Not linked anywhere. The operator pastes ADMIN_KEY here once per browser to unlock the global LLM switch. */
export default function AdminPage() {
  return (
    <div className="mx-auto max-w-xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl">Operator access</h1>
      <p className="mt-3 text-muted-foreground">
        Only the person running this server needs this. The admin key unlocks the switch that turns the optional LLM helper on or off for
        everyone. It is kept in this browser only.
      </p>
      <AdminKeyForm />
    </div>
  );
}

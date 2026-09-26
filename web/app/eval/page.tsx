"use client";

import { useState } from "react";
import { CheckEval } from "@/components/check-eval";
import { DecodeEval } from "@/components/decode/decode-eval";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function EvalPage() {
  const [tab, setTab] = useState<string>("decode");
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">Evaluation</p>
      <h1 className="mt-1 max-w-3xl font-display text-4xl leading-[1.05] sm:text-6xl">What we measured, and what we did not.</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
        Every number below carries its label. None of it comes from real workers: it is public read speech and synthetic, author-written data.
      </p>
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))} className="mt-8">
        <TabsList className="group-data-horizontal/tabs:h-12 w-full sm:w-fit">
          <TabsTrigger value="decode" className="px-4 text-base text-foreground/80 dark:text-foreground/80">Decode</TabsTrigger>
          <TabsTrigger value="check" className="px-4 text-base text-foreground/80 dark:text-foreground/80">Check mode</TabsTrigger>
        </TabsList>
        <TabsContent value="decode" className="pt-5"><DecodeEval /></TabsContent>
        <TabsContent value="check" className="pt-2"><CheckEval /></TabsContent>
      </Tabs>
    </div>
  );
}

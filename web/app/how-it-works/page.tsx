"use client";

import { useState } from "react";
import { CheckInspector } from "@/components/check-inspector";
import { DecodeInspector } from "@/components/decode/inspector";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function HowItWorks() {
  const [tab, setTab] = useState<string>("decode");
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">How it works</p>
      <h1 className="mt-1 max-w-3xl font-display text-4xl leading-[1.05] sm:text-6xl">Six stages. No language model in the decision.</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
        Type any message and watch Steve decode it, stage by stage: the words, the local phrases, the spots that matter, the candidates and their scores, and why it rewrote, asked or left a word alone.
        Everything here is deterministic code you can read and test.
      </p>
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))} className="mt-8">
        <TabsList className="group-data-horizontal/tabs:h-12 w-full sm:w-fit">
          <TabsTrigger value="decode" className="px-4 text-base text-foreground/80 dark:text-foreground/80">Decode</TabsTrigger>
          <TabsTrigger value="check" className="px-4 text-base text-foreground/80 dark:text-foreground/80">Check mode</TabsTrigger>
        </TabsList>
        <TabsContent value="decode" className="pt-5"><DecodeInspector /></TabsContent>
        <TabsContent value="check" className="pt-2"><CheckInspector /></TabsContent>
      </Tabs>
    </div>
  );
}

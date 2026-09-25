import Link from "next/link";
import { HeroDemo } from "@/components/hero-demo";
import { FinalCta, HowSteps, Languages, NotAWrapper, ProblemStats, SectionHead, WhyNotTranslate } from "@/components/landing-sections";
import { Playground } from "@/components/playground";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Landing() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6">
      {/* hero */}
      <section className="grid items-center gap-12 pb-20 pt-14 lg:grid-cols-[1.05fr_1fr] lg:pt-24">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            <span className="size-1.5 rounded-full bg-primary" aria-hidden /> Teach-back for Manglish · Hinglish · Arabizi · Taglish
          </p>
          <h1 className="mt-5 font-display text-[clamp(2.9rem,7vw,5.4rem)] leading-[0.98]">
            “ok 👍” isn&apos;t <em className="text-primary">understanding.</em>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground">
            Send an important instruction. The reader explains it back in their own words, by voice or text, in any language mix and any spelling.
            We check every key fact, exactly, and show you which ones didn&apos;t land.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/demo" className={cn(buttonVariants({ size: "lg" }), "h-11 px-5 text-base")}>Try the demo</Link>
            <Link href="/how-it-works" className={cn(buttonVariants({ size: "lg", variant: "outline" }), "h-11 px-5 text-base")}>How it works</Link>
          </div>
          <p className="mt-5 text-sm text-muted-foreground">No translation. No scores shown to the reader. No API keys needed.</p>
        </div>
        <HeroDemo />
      </section>

      <section className="py-16" aria-labelledby="problem">
        <SectionHead
          eyebrow="The problem"
          title={<span id="problem">The last mile of every instruction is a guess.</span>}
          body="Teach-back works. The research just left out the people who switch tongues mid-sentence and write one language in another’s script."
        />
        <ProblemStats />
      </section>

      <section className="py-16" aria-labelledby="how">
        <SectionHead eyebrow="How it works" title={<span id="how">Four steps. The reader only sees a thank-you.</span>} />
        <HowSteps />
      </section>

      <section className="py-16" aria-labelledby="translate">
        <SectionHead
          eyebrow="Why not just translate?"
          title={<span id="translate">Because translation is the thing the problem statement criticises.</span>}
          body="Converting mixed language into clean English forces people back into the one official version. We fix the response instead."
        />
        <WhyNotTranslate />
      </section>

      <section className="py-16" aria-labelledby="wrapper">
        <SectionHead
          eyebrow="Not an AI wrapper"
          title={<span id="wrapper">An LLM never decides whether a fact was understood.</span>}
          body="Numbers, doses, dates, durations and negations are decided by deterministic, tested code. LLMs are optional helpers."
        />
        <NotAWrapper />
      </section>

      <section className="py-16" aria-labelledby="langs">
        <SectionHead eyebrow="Languages" title={<span id="langs">Spelled by ear, understood by rule.</span>} body="Sound-key matching, suffix rules (dalawa+ng) and per-language negation scope. Vocabulary is unverified until native speakers sign it off." />
        <Languages />
      </section>

      <section className="py-16" aria-labelledby="play">
        <SectionHead eyebrow="Live playground" title={<span id="play">Type any reply. Watch the facts resolve.</span>} body="This calls the real engine, the same one behind the dashboard." />
        <div className="mt-10">
          <Playground />
        </div>
      </section>

      <section className="py-16">
        <FinalCta />
      </section>
    </div>
  );
}

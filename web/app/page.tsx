import Link from "next/link";
import { LiveExample } from "@/components/decode/live-example";
import { buttonVariants } from "@/components/ui/button-variants";
import { INTRO } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** `/` opens the Decode demo: a one-screen intro and a big "Try it". The Check-mode pitch lives at /check. */
export default function Home() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center px-4 pb-16 pt-12 text-center sm:px-6 sm:pt-20">
      <h1 className="font-display text-[clamp(2.4rem,8vw,4.6rem)] leading-[1.02]">{INTRO.headline}</h1>
      <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground">{INTRO.line1}</p>
      <p className="mt-3 max-w-xl text-lg leading-relaxed">{INTRO.line2}</p>
      <Link href="/listen" className={cn(buttonVariants({ size: "lg" }), "mt-8 h-14 w-full max-w-xs px-8 text-xl")} data-testid="try-it">
        {INTRO.cta}
      </Link>
      <p className="mt-3 text-sm text-muted-foreground">Text only. No account. Nothing you say or paste is stored.</p>
      <LiveExample />
      <nav aria-label="More" className="mt-10 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm">
        <Link href="/how-it-works" className="min-h-11 py-2 underline underline-offset-4">How it works</Link>
        <Link href="/eval" className="min-h-11 py-2 underline underline-offset-4">Evaluation</Link>
        <Link href="/check" className="min-h-11 py-2 underline underline-offset-4">Check mode (teach-back)</Link>
      </nav>
    </div>
  );
}

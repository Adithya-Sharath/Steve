"use client";

import { useMutation } from "@tanstack/react-query";
import { Ear, Languages, Loader2, MicOff } from "lucide-react";
import { useRef, useState } from "react";
import { DecodedCardView } from "@/components/decode/decoded-card";
import { LanguagePicker } from "@/components/decode/language-picker";
import { OtherPersonNotice } from "@/components/decode/other-person-notice";
import { useDecodeHealth } from "@/components/decode/warmup";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { VoiceRecorder } from "@/components/voice-recorder";
import { api } from "@/lib/api";
import { ACCENTS, languageInfo } from "@/lib/languages";
import type { AccentHint, DecodeResponse, ReplyLanguage } from "@/lib/types";
import { withWake } from "@/lib/waking";
import { setAccent, setLanguage, useAccent, useLanguage } from "@/lib/worker";

/**
 * The audio showcase: one screen. Tap the big button, let someone speak, tap again: Steve decodes what was said into where / when / what / how much,
 * asks a question when it is not sure, and can show the card in another language. Text only; nothing said is stored.
 */
export function Showcase() {
  const stored = useLanguage();
  const accent = useAccent();
  const [changingLang, setChangingLang] = useState(false);
  const [recording, setRecording] = useState(false);
  const [micProblem, setMicProblem] = useState<"denied" | "unavailable" | null>(null);
  const [result, setResult] = useState<{ n: number; data: DecodeResponse } | null>(null);
  const lastBlob = useRef<Blob | null>(null);

  const health = useDecodeHealth();
  const voiceOff = health.data ? !health.data.voice : false;
  const language: ReplyLanguage | undefined = stored === undefined ? undefined : (stored ?? "en"); // English until a language is chosen

  const decode = useMutation({
    mutationFn: (blob: Blob) => {
      lastBlob.current = blob;
      const opts = { accent_hint: (accent || undefined) as AccentHint | undefined, reply_language: language && language !== "en" ? language : undefined };
      return withWake(() => api.decodeAudio(blob, opts));
    },
    onSuccess: (data) => setResult((r) => ({ n: (r?.n ?? 0) + 1, data })),
  });
  const answer = useMutation({
    mutationFn: (b: { index: number; choice: string }) =>
      withWake(() => api.clarify({ decode_id: result!.data.decode_id!, question_index: b.index, choice: b.choice })),
    onSuccess: (data) => setResult((r) => ({ n: (r?.n ?? 0) + 1, data })),
  });

  if (language === undefined) return <div className="mx-auto max-w-md px-4 py-16" aria-busy="true" />;
  if (changingLang)
    return (
      <LanguagePicker
        current={language}
        onPick={(l: ReplyLanguage) => {
          setLanguage(l);
          setResult(null);
          setChangingLang(false);
        }}
      />
    );

  const info = languageInfo(language);
  const busy = decode.isPending || answer.isPending;

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5 px-4 pb-16 pt-6">
      {recording && <OtherPersonNotice />}

      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-4xl leading-none">Listen</h1>
        <Button
          variant="outline"
          className="h-12 px-4 text-base"
          onClick={() => setChangingLang(true)}
          aria-label={`Show the answer in: ${info.english}. Change language`}
        >
          <Languages aria-hidden /> <span lang={info.bcp47} dir={info.dir}>{info.native}</span>
        </Button>
      </header>

      <div>
        <label htmlFor="accent" className="text-sm font-medium text-muted-foreground">Who is speaking? (optional)</label>
        <select
          id="accent"
          value={accent}
          onChange={(e) => setAccent(e.target.value as AccentHint | "")}
          className="mt-1 block h-12 w-full rounded-xl border-2 border-input bg-card px-3 text-base"
        >
          {ACCENTS.map((a) => (
            <option key={a.id} value={a.id}>{a.label}</option>
          ))}
        </select>
      </div>

      {micProblem && (
        <p role="alert" data-testid="mic-problem" className="flex gap-3 rounded-2xl bg-missing-soft px-4 py-4 text-base text-missing-ink">
          <MicOff className="mt-0.5 size-5 shrink-0" aria-hidden />
          <span>
            {micProblem === "denied"
              ? "The microphone is blocked. Allow it for this site in your browser settings, then tap the button again."
              : "This device or page can't use the microphone (it needs a secure connection or localhost)."}
          </span>
        </p>
      )}

      {voiceOff ? (
        <p className="rounded-2xl bg-missing-soft px-4 py-4 text-base text-missing-ink" role="status" data-testid="voice-off">
          Voice isn&apos;t available right now (the speech service is not configured or has reached its daily limit).
        </p>
      ) : (
        <div className="card-soft px-4 py-6">
          <VoiceRecorder
            autoSend
            busy={busy}
            onRecordingChange={(r) => {
              setRecording(r);
              if (r) {
                setMicProblem(null);
                setResult(null);
                decode.reset();
                answer.reset();
              }
            }}
            onMicError={setMicProblem}
            onSend={(blob) => decode.mutate(blob)}
            idleText="Tap the big button, let them speak, tap again to decode. Up to 30 seconds."
          />
        </div>
      )}

      {busy && (
        <p role="status" aria-live="polite" className="flex items-center justify-center gap-2 py-4 text-lg text-muted-foreground" data-testid="decoding">
          <Loader2 className="size-5 animate-spin motion-reduce:animate-none" aria-hidden /> <span aria-hidden>🎧</span> decoding…
        </p>
      )}

      {(decode.isError || answer.isError) && !busy && (
        <ErrorState
          message={((decode.error ?? answer.error) as Error).message}
          onRetry={() => (answer.isError ? answer.reset() : lastBlob.current && decode.mutate(lastBlob.current))}
        />
      )}

      {!busy && !decode.isError && !answer.isError && result && result.data.card && (
        <DecodedCardView key={result.n} data={result.data} language={language} busy={busy} onAnswer={(index, choice) => answer.mutate({ index, choice })} />
      )}

      {!busy && !decode.isError && result && !result.data.card && (
        <div data-testid="no-card">
          {result.data.notes.some((n) => /voice/i.test(n)) ? (
            <p role="status" className="rounded-2xl bg-missing-soft px-4 py-4 text-base text-missing-ink">{result.data.notes.join(" ")}</p>
          ) : (
            <EmptyState title="Nothing to decode" body="I couldn't find anything to decode. Try again." icon={<Ear className="size-8" />} />
          )}
        </div>
      )}
    </div>
  );
}

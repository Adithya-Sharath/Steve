"use client";

import { useMutation } from "@tanstack/react-query";
import { ClipboardPaste, Ear, Languages, Loader2, Mic, MicOff } from "lucide-react";
import { useRef, useState } from "react";
import { DecodedCardView } from "@/components/decode/decoded-card";
import { ExampleChips } from "@/components/decode/example-chips";
import { LanguagePicker } from "@/components/decode/language-picker";
import { OtherPersonNotice } from "@/components/decode/other-person-notice";
import { useDecodeHealth } from "@/components/decode/warmup";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { VoiceRecorder } from "@/components/voice-recorder";
import { api } from "@/lib/api";
import { ACCENTS, languageInfo } from "@/lib/languages";
import type { AccentHint, DecodeExample, DecodeResponse, ReplyLanguage } from "@/lib/types";
import { withWake } from "@/lib/waking";
import { getAccent, setAccent, setLanguage, useAccent, useLanguage } from "@/lib/worker";

type Job = { kind: "audio"; blob: Blob } | { kind: "text"; text: string; accent?: AccentHint | "" };
type TabId = "listen" | "paste";

const VOICE_TROUBLE = /voice/i; // every voice-problem note from the API mentions "voice"

/**
 * /listen: the Decode demo. Tap to listen in person, or paste a message, or tap an example. Text-only card; clarifying questions are answered in place.
 * Nothing typed or heard is stored here. States: loading, API waking up (app-wide banner), mic denied, voice unavailable, network error, empty result.
 */
export function ListenScreen() {
  const language = useLanguage();
  const accent = useAccent();
  const [changingLang, setChangingLang] = useState(false);
  const [userTab, setUserTab] = useState<TabId | null>(null);
  const [recording, setRecording] = useState(false);
  const [micProblem, setMicProblem] = useState<"denied" | "unavailable" | null>(null);
  const [text, setText] = useState("");
  const [result, setResult] = useState<{ n: number; data: DecodeResponse } | null>(null);
  const lastJob = useRef<Job | null>(null);

  const health = useDecodeHealth();
  const voiceOff = health.data ? !health.data.voice : false;
  const tab: TabId = userTab ?? (voiceOff ? "paste" : "listen"); // voice unavailable: start on Paste, with the reason shown

  const decode = useMutation({
    mutationFn: (job: Job) => {
      lastJob.current = job;
      const hint = (job.kind === "text" && job.accent !== undefined ? job.accent : getAccent()) || undefined;
      const opts = { accent_hint: hint as AccentHint | undefined, reply_language: language && language !== "en" ? language : undefined };
      return withWake(() => (job.kind === "audio" ? api.decodeAudio(job.blob, opts) : api.decodeText({ text: job.text, ...opts })));
    },
    onSuccess: (data) => {
      setResult((r) => ({ n: (r?.n ?? 0) + 1, data }));
      if (!data.card && VOICE_TROUBLE.test(data.notes.join(" "))) setUserTab("paste"); // voice did not work: continue by typing
    },
  });
  const answer = useMutation({
    mutationFn: (b: { index: number; choice: string }) =>
      withWake(() => api.clarify({ decode_id: result!.data.decode_id!, question_index: b.index, choice: b.choice })),
    onSuccess: (data) => setResult((r) => ({ n: (r?.n ?? 0) + 1, data })),
  });

  if (language === undefined) return <div className="mx-auto max-w-md px-4 py-16" aria-busy="true" />;
  if (language === null || changingLang)
    return (
      <LanguagePicker
        current={language}
        onPick={(l: ReplyLanguage) => {
          setLanguage(l);
          setChangingLang(false);
        }}
      />
    );

  const info = languageInfo(language);
  const busy = decode.isPending || answer.isPending;
  const voiceProblem = result && !result.data.card && VOICE_TROUBLE.test(result.data.notes.join(" "));

  const pickExample = (ex: DecodeExample) => {
    setUserTab("paste");
    setText(ex.request.text);
    setAccent(ex.request.accent_hint ?? "");
    decode.mutate({ kind: "text", text: ex.request.text, accent: ex.request.accent_hint ?? "" });
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5 px-4 pb-16 pt-5">
      {recording && <OtherPersonNotice />}

      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-4xl leading-none">Listen</h1>
        <Button variant="outline" className="h-12 px-4 text-base" onClick={() => setChangingLang(true)} aria-label={`Language: ${info.english}. Change language`}>
          <Languages aria-hidden /> <span lang={info.bcp47} dir={info.dir}>{info.native}</span>
        </Button>
      </header>

      <ExampleChips onPick={pickExample} disabled={busy} />

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

      <Tabs value={tab} onValueChange={(v) => setUserTab(v as TabId)}>
        <TabsList className="group-data-horizontal/tabs:h-14 w-full">
          <TabsTrigger value="listen" className="text-base text-foreground/80 dark:text-foreground/80"><Mic aria-hidden /> Listen</TabsTrigger>
          <TabsTrigger value="paste" className="text-base text-foreground/80 dark:text-foreground/80"><ClipboardPaste aria-hidden /> Paste a message</TabsTrigger>
        </TabsList>

        <TabsContent value="listen" className="pt-4">
          {micProblem && (
            <p role="alert" data-testid="mic-problem" className="mb-3 flex gap-3 rounded-2xl bg-missing-soft px-4 py-4 text-base text-missing-ink">
              <MicOff className="mt-0.5 size-5 shrink-0" aria-hidden />
              <span>
                {micProblem === "denied"
                  ? "The microphone is blocked. Allow it for this site in your browser settings to use Listen, or paste the message instead."
                  : "This device or page can't use the microphone (it needs a secure connection). You can paste the message instead."}
              </span>
            </p>
          )}
          {voiceOff ? (
            <p className="rounded-2xl bg-missing-soft px-4 py-4 text-base text-missing-ink" role="status" data-testid="voice-off">
              Voice isn&apos;t available right now. You can paste or type the message instead.
            </p>
          ) : (
            <div className="card-soft px-4 py-6">
              <VoiceRecorder
                autoSend
                busy={busy}
                onRecordingChange={setRecording}
                onMicError={(kind) => {
                  setMicProblem(kind);
                  setUserTab("paste");
                }}
                onSend={(blob) => decode.mutate({ kind: "audio", blob })}
                idleText="Tap the big button, let them speak, tap again to decode. Up to 30 seconds."
              />
            </div>
          )}
        </TabsContent>

        <TabsContent value="paste" className="pt-4">
          {micProblem && userTab === "paste" && (
            <p role="alert" data-testid="mic-problem" className="mb-3 flex gap-3 rounded-2xl bg-missing-soft px-4 py-4 text-base text-missing-ink">
              <MicOff className="mt-0.5 size-5 shrink-0" aria-hidden />
              <span>
                {micProblem === "denied"
                  ? "The microphone is blocked. Allow it for this site in your browser settings to use Listen, or paste the message here."
                  : "This device or page can't use the microphone (it needs a secure connection). Paste the message here instead."}
              </span>
            </p>
          )}
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) decode.mutate({ kind: "text", text: text.trim() });
            }}
          >
            <label htmlFor="msg" className="text-sm font-medium text-muted-foreground">Paste or type the message</label>
            <Textarea id="msg" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} className="min-h-40 text-lg" placeholder="For example: yalla habibi come to the barking gate tree" />
            <Button type="submit" className="h-12 w-full text-lg" disabled={busy || !text.trim()}>
              <Ear aria-hidden /> Decode
            </Button>
          </form>
        </TabsContent>
      </Tabs>

      {busy && (
        <p role="status" aria-live="polite" className="flex items-center justify-center gap-2 py-4 text-lg text-muted-foreground" data-testid="decoding">
          <Loader2 className="size-5 animate-spin motion-reduce:animate-none" aria-hidden /> <span aria-hidden>🎧</span> decoding…
        </p>
      )}

      {(decode.isError || answer.isError) && !busy && (
        <ErrorState
          message={((decode.error ?? answer.error) as Error).message}
          onRetry={() => (answer.isError ? answer.reset() : lastJob.current && decode.mutate(lastJob.current))}
        />
      )}

      {!busy && !decode.isError && !answer.isError && result && result.data.card && (
        <DecodedCardView key={result.n} data={result.data} language={language} busy={busy} onAnswer={(index, choice) => answer.mutate({ index, choice })} />
      )}

      {!busy && !decode.isError && result && !result.data.card && (
        <div data-testid="no-card">
          {voiceProblem ? (
            <p role="status" className="rounded-2xl bg-missing-soft px-4 py-4 text-base text-missing-ink">{result.data.notes.join(" ")}</p>
          ) : (
            <EmptyState title="Nothing to decode" body="I couldn't find anything to decode. Try again or paste the message." icon={<Ear className="size-8" />} />
          )}
        </div>
      )}

      <p className="pt-2 text-center text-sm text-muted-foreground">Steve does not save voice notes or messages. Your language choice stays on this phone.</p>
    </div>
  );
}

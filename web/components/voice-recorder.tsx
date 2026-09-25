"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Mic, RotateCcw, Send, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Waveform } from "@/components/waveform";
import { Button } from "@/components/ui/button";
import { blobToWav } from "@/lib/wav";
import { cn } from "@/lib/utils";

const MAX_SECONDS = 30; // the speech service accepts up to ~30 s per request

type Phase = "idle" | "recording" | "recorded";

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Huge record button + live waveform + timer. Stop, listen back, re-record, send. Audio is converted to WAV in the browser. */
export function VoiceRecorder({ onSend, busy }: { onSend: (wav: Blob) => void; busy: boolean }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [seconds, setSeconds] = useState(0);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [converting, setConverting] = useState(false);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stream = useRef<MediaStream | null>(null);
  const actx = useRef<AudioContext | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanupAudio = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    actx.current?.close().catch(() => {});
    stream.current = null;
    actx.current = null;
    setAnalyser(null);
  }, []);

  useEffect(() => () => cleanupAudio(), [cleanupAudio]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  const stop = useCallback(() => {
    if (rec.current && rec.current.state !== "inactive") rec.current.stop();
  }, []);

  const start = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      stream.current = s;
      const ctx = new AudioContext();
      actx.current = ctx;
      const src = ctx.createMediaStreamSource(s);
      const an = ctx.createAnalyser();
      an.fftSize = 128;
      src.connect(an);
      setAnalyser(an);
      const mr = new MediaRecorder(s);
      rec.current = mr;
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = () => {
        const b = new Blob(chunks.current, { type: mr.mimeType || "audio/webm" });
        setBlob(b);
        setUrl(URL.createObjectURL(b));
        setPhase("recorded");
        cleanupAudio();
      };
      mr.start();
      setSeconds(0);
      setPhase("recording");
      timer.current = setInterval(() => setSeconds((v) => v + 1), 1000);
    } catch {
      toast.error("We couldn't use the microphone. You can type your answer instead.");
    }
  };

  useEffect(() => {
    if (phase === "recording" && seconds >= MAX_SECONDS) stop();
  }, [phase, seconds, stop]);

  const reset = () => {
    setBlob(null);
    setUrl(null);
    setPhase("idle");
    setSeconds(0);
  };

  const send = async () => {
    if (!blob) return;
    setConverting(true);
    try {
      onSend(await blobToWav(blob));
    } catch {
      toast.error("Could not prepare that recording. Please try again or type your answer.");
    } finally {
      setConverting(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-5">
      <div className="relative grid size-40 place-items-center">
        <AnimatePresence>
          {phase === "recording" &&
            [0, 1].map((i) => (
              <motion.span
                key={i}
                aria-hidden
                className="absolute inset-0 rounded-full bg-wrong/25"
                initial={{ scale: 0.8, opacity: 0.6 }}
                animate={{ scale: 1.35, opacity: 0 }}
                transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.9, ease: "easeOut" }}
              />
            ))}
        </AnimatePresence>
        <motion.button
          type="button"
          whileTap={{ scale: 0.94 }}
          onClick={phase === "recording" ? stop : phase === "idle" ? start : undefined}
          disabled={phase === "recorded" || busy}
          aria-label={phase === "recording" ? "Stop recording" : "Start recording"}
          className={cn(
            "relative grid size-32 place-items-center rounded-full text-primary-foreground shadow-[0_18px_40px_-14px_color-mix(in_oklch,var(--primary)_70%,transparent)] transition-colors focus-visible:outline-offset-4 disabled:opacity-60",
            phase === "recording" ? "bg-wrong" : "bg-primary",
          )}
        >
          {phase === "recording" ? <Square className="size-10 fill-current" /> : <Mic className="size-12" />}
        </motion.button>
      </div>
      <div className="w-full max-w-xs">
        <Waveform analyser={analyser} active={phase === "recording"} />
      </div>
      <p className="font-mono text-lg tabular-nums" aria-live="off">
        {fmt(seconds)} <span className="text-sm text-muted-foreground">/ {fmt(MAX_SECONDS)}</span>
      </p>
      {phase === "idle" && <p className="text-sm text-muted-foreground">Tap to speak. Up to {MAX_SECONDS} seconds.</p>}
      {phase === "recording" && <p className="text-sm text-muted-foreground" role="status">Listening… tap the square when you&apos;re done.</p>}
      {phase === "recorded" && url && (
        <div className="flex w-full flex-col items-center gap-3">
          <audio src={url} controls className="w-full max-w-xs" aria-label="Your recording" />
          <div className="flex gap-2">
            <Button variant="outline" size="lg" onClick={reset} disabled={busy || converting}><RotateCcw /> Record again</Button>
            <Button size="lg" onClick={send} disabled={busy || converting}><Send /> Send</Button>
          </div>
        </div>
      )}
    </div>
  );
}

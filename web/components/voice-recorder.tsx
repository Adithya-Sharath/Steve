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

/**
 * Huge record button + live waveform + timer. Stop, listen back, re-record, send. Audio is converted to WAV in the browser.
 * `autoSend` (the Decode Listen screen): tapping stop sends straight away, no play-back step. `onRecordingChange` tells the page when the mic is live.
 */
export function VoiceRecorder({
  onSend,
  busy,
  autoSend = false,
  onRecordingChange,
  idleText,
}: {
  onSend: (wav: Blob) => void;
  busy: boolean;
  autoSend?: boolean;
  onRecordingChange?: (recording: boolean) => void;
  idleText?: string;
}) {
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
  const haloRef = useRef<HTMLSpanElement>(null);

  // the halo breathes with the ACTUAL microphone level (skipped for reduced motion)
  useEffect(() => {
    const halo = haloRef.current;
    if (!halo || !analyser || phase !== "recording") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const buf = new Uint8Array(analyser.fftSize);
    let raf = 0;
    let smooth = 0;
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const level = Math.min(1, Math.sqrt(sum / buf.length) * 5);
      smooth += (level - smooth) * 0.25;
      halo.style.setProperty("--level", smooth.toFixed(3));
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [analyser, phase]);

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
        cleanupAudio();
        onRecordingChange?.(false);
        if (autoSend) {
          setPhase("idle");
          setSeconds(0);
          void sendBlob(b);
          return;
        }
        setBlob(b);
        setUrl(URL.createObjectURL(b));
        setPhase("recorded");
      };
      mr.start();
      setSeconds(0);
      setPhase("recording");
      onRecordingChange?.(true);
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

  const sendBlob = async (b: Blob) => {
    setConverting(true);
    try {
      onSend(await blobToWav(b));
    } catch {
      toast.error("Could not prepare that recording. Please try again or type your answer.");
    } finally {
      setConverting(false);
    }
  };
  const send = () => (blob ? sendBlob(blob) : undefined);

  return (
    <div className="flex flex-col items-center gap-5">
      <div className="relative grid size-44 place-items-center">
        {/* 30 s progress ring (decorative: the timer below is the accessible readout) */}
        <svg aria-hidden viewBox="0 0 176 176" className="pointer-events-none absolute inset-0 -rotate-90">
          <circle cx="88" cy="88" r="82" fill="none" stroke="var(--border)" strokeWidth="4" />
          <circle
            cx="88" cy="88" r="82" fill="none" strokeWidth="4" strokeLinecap="round"
            stroke={seconds >= MAX_SECONDS - 5 ? "var(--missing)" : "var(--wrong)"}
            strokeDasharray={2 * Math.PI * 82}
            strokeDashoffset={2 * Math.PI * 82 * (1 - (phase === "idle" ? 0 : Math.min(seconds, MAX_SECONDS) / MAX_SECONDS))}
            style={{ transition: "stroke-dashoffset 1s linear, stroke 0.3s" }}
          />
        </svg>
        <AnimatePresence>
          {phase === "recording" && (
            <>
              <span
                ref={haloRef}
                aria-hidden
                className="absolute inset-4 rounded-full bg-wrong/25 transition-transform duration-75"
                style={{ transform: "scale(calc(1 + var(--level, 0) * 0.5))" }}
              />
              <motion.span
                aria-hidden
                className="absolute inset-4 rounded-full bg-wrong/20"
                initial={{ scale: 0.9, opacity: 0.6 }}
                animate={{ scale: 1.3, opacity: 0 }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
              />
            </>
          )}
        </AnimatePresence>
        <Button
          type="button"
          onClick={phase === "recording" ? stop : phase === "idle" ? start : undefined}
          disabled={phase === "recorded" || busy || converting}
          aria-label={phase === "recording" ? "Stop recording" : "Start recording"}
          className={cn(
            "size-32 rounded-full p-0 [--lip:7px] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
            phase === "recording" && "btn-record",
            phase === "idle" && "record-breathe",
          )}
        >
          {phase === "recording" ? <Square className="size-10 fill-current" /> : <Mic className="size-12" />}
        </Button>
      </div>
      <div className="w-full max-w-xs">
        <Waveform analyser={analyser} active={phase === "recording"} />
      </div>
      <p className="font-mono text-lg tabular-nums" aria-live="off">
        {fmt(seconds)} <span className="text-sm text-muted-foreground">/ {fmt(MAX_SECONDS)}</span>
      </p>
      {phase === "idle" && <p className="text-sm text-muted-foreground">{idleText ?? `Tap to speak. Up to ${MAX_SECONDS} seconds.`}</p>}
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

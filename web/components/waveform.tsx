"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/** Bars that react to live mic input (an AnalyserNode). With no analyser it draws a calm idle line. */
export function Waveform({
  analyser,
  active,
  bars = 36,
  className,
}: {
  analyser: AnalyserNode | null;
  active: boolean;
  bars?: number;
  className?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    const data = new Uint8Array(analyser?.frequencyBinCount ?? 0);
    const color = getComputedStyle(canvas).color;
    let raf = 0;
    let t = 0;
    const draw = () => {
      t += 0.05;
      ctx.clearRect(0, 0, w, h);
      if (analyser && active) analyser.getByteFrequencyData(data);
      const gap = 3;
      const bw = (w - gap * (bars - 1)) / bars;
      for (let i = 0; i < bars; i++) {
        let v = 0.06;
        if (analyser && active) {
          const idx = Math.floor((i / bars) * data.length * 0.6);
          v = Math.max(0.06, data[idx] / 255);
        } else if (!reduce) {
          v = 0.06 + 0.03 * Math.sin(t + i * 0.5);
        }
        const bh = Math.max(3, v * h);
        ctx.fillStyle = color;
        ctx.globalAlpha = active ? 0.35 + v * 0.65 : 0.35;
        ctx.beginPath();
        ctx.roundRect(i * (bw + gap), (h - bh) / 2, bw, bh, bw / 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [analyser, active, bars]);
  return <canvas ref={ref} aria-hidden className={cn("h-16 w-full text-primary", className)} />;
}

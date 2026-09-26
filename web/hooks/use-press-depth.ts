"use client";

import { useCallback, useEffect, useRef } from "react";
import type * as React from "react";

/**
 * Press-with-depth behaviour, adapted from the 21st.dev "Press Depth" component by ddoemonn
 * (https://21st.dev/r/ddoemonn/press-depth). What we kept: the pointer-origin maths (the press tilts TOWARD where you
 * touch), "the press cancels when the pointer slides off the button", and keyboard (Space/Enter) support.
 * What we changed: it writes `data-pressed` and two CSS variables (--tilt-x / --tilt-y) instead of using React state
 * and motion springs, so there are no re-renders and the visuals come from our tokens in globals.css (.btn-raised).
 * `prefers-reduced-motion`: the press still registers, but the tilt is never applied.
 */
const TILT_DEG = 6;

type Handlers = {
  onPointerDown?: React.PointerEventHandler<HTMLElement>;
  onKeyDown?: React.KeyboardEventHandler<HTMLElement>;
  onKeyUp?: React.KeyboardEventHandler<HTMLElement>;
  onBlur?: React.FocusEventHandler<HTMLElement>;
};

export function usePressDepth(disabled: boolean, theirs: Handlers = {}) {
  const node = useRef<HTMLElement | null>(null);
  const pointer = useRef<number | null>(null);
  const cleanup = useRef<(() => void) | null>(null);

  const setPressed = useCallback((on: boolean) => {
    const el = node.current;
    if (!el) return;
    if (on) el.setAttribute("data-pressed", "");
    else {
      el.removeAttribute("data-pressed");
      el.style.removeProperty("--tilt-x");
      el.style.removeProperty("--tilt-y");
    }
  }, []);

  const stop = useCallback(() => {
    pointer.current = null;
    cleanup.current?.();
    cleanup.current = null;
    setPressed(false);
  }, [setPressed]);

  useEffect(() => () => stop(), [stop]);
  useEffect(() => {
    if (disabled) stop();
  }, [disabled, stop]);

  const ref = useCallback((el: HTMLElement | null) => {
    node.current = el;
  }, []);

  const onPointerDown = (e: React.PointerEvent<HTMLElement>) => {
    theirs.onPointerDown?.(e);
    if (disabled || (e.pointerType === "mouse" && e.button !== 0)) return;
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width) * 2 - 1));
    const y = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height) * 2 - 1));
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.style.setProperty("--tilt-x", reduced ? "0deg" : `${(-y * TILT_DEG).toFixed(2)}deg`);
    el.style.setProperty("--tilt-y", reduced ? "0deg" : `${(x * TILT_DEG).toFixed(2)}deg`);
    pointer.current = e.pointerId;
    setPressed(true);

    const inside = (ev: PointerEvent) => {
      const b = el.getBoundingClientRect();
      return ev.clientX >= b.left && ev.clientX <= b.right && ev.clientY >= b.top && ev.clientY <= b.bottom;
    };
    const move = (ev: PointerEvent) => {
      if (ev.pointerId === pointer.current) setPressed(inside(ev));
    };
    const up = (ev: PointerEvent) => {
      if (ev.pointerId === pointer.current) stop();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    window.addEventListener("blur", stop);
    cleanup.current = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      window.removeEventListener("blur", stop);
    };
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
    theirs.onKeyDown?.(e);
    if (!disabled && !e.repeat && (e.key === " " || e.key === "Enter")) setPressed(true);
  };
  const onKeyUp = (e: React.KeyboardEvent<HTMLElement>) => {
    theirs.onKeyUp?.(e);
    if (e.key === " " || e.key === "Enter" || e.key === "Escape") setPressed(false);
  };
  const onBlur = (e: React.FocusEvent<HTMLElement>) => {
    theirs.onBlur?.(e);
    setPressed(false);
  };

  return { ref, handlers: { onPointerDown, onKeyDown, onKeyUp, onBlur } };
}

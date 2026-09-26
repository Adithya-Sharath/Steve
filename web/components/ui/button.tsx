"use client";

import { Button as ButtonPrimitive } from "@base-ui/react/button";
import type { VariantProps } from "class-variance-authority";
import { usePressDepth } from "@/hooks/use-press-depth";
import { cn } from "@/lib/utils";
import { buttonVariants } from "./button-variants";

/**
 * Same props as before. Raised variants (default / outline / secondary / destructive) get a physical press: the
 * lip lifts on hover, the button sinks and tilts toward the pointer on press (see hooks/use-press-depth.ts and
 * .btn-raised in globals.css). `ghost` and `link` stay flat.
 */
function Button({
  className,
  variant = "default",
  size = "default",
  disabled,
  onPointerDown,
  onKeyDown,
  onKeyUp,
  onBlur,
  ref,
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  const raised = variant !== "ghost" && variant !== "link";
  const press = usePressDepth(!raised || !!disabled, {
    onPointerDown: onPointerDown as never,
    onKeyDown: onKeyDown as never,
    onKeyUp: onKeyUp as never,
    onBlur: onBlur as never,
  });
  const setRef = (el: HTMLElement | null) => {
    press.ref(el);
    if (typeof ref === "function") ref(el as never);
    else if (ref && typeof ref === "object") (ref as { current: unknown }).current = el;
  };
  return (
    <ButtonPrimitive
      data-slot="button"
      ref={setRef as never}
      disabled={disabled}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
      {...(raised ? (press.handlers as never) : { onPointerDown, onKeyDown, onKeyUp, onBlur })}
    />
  );
}

export { Button, buttonVariants };

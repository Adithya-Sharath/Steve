import { cva, type VariantProps } from "class-variance-authority";

/**
 * Button styling lives here (no "use client") so Server Components and plain <Link>/<a> elements can use it too.
 * The physical feel ("depth": a lip that lifts on hover and sinks on press) is pure CSS in globals.css (.btn-raised),
 * driven by design tokens, so it works in light/dark and for links as well as buttons.
 */
export const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "btn-raised btn-primary rounded-lg",
        outline: "btn-raised btn-outline rounded-lg",
        secondary: "btn-raised btn-secondary rounded-lg",
        destructive: "btn-raised btn-danger rounded-lg",
        ghost: "btn-soft rounded-lg",
        link: "text-primary underline-offset-4 hover:underline rounded-lg",
      },
      size: {
        default: "h-8 gap-1.5 px-2.5 [--lip:3px] has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs [--lip:2px] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] [--lip:2px] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 [--lip:3px] has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8 [--lip:3px]",
        "icon-xs": "size-6 rounded-[min(var(--radius-md),10px)] [--lip:2px] [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-7 rounded-[min(var(--radius-md),12px)] [--lip:2px]",
        "icon-lg": "size-9 [--lip:3px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export type ButtonVariantProps = VariantProps<typeof buttonVariants>;

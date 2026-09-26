import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import { WakingBanner, WarmUp } from "@/components/decode/warmup";
import { Providers } from "@/components/providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const display = Instrument_Serif({ variable: "--font-display", subsets: ["latin"], weight: "400", style: ["normal", "italic"] });

export const metadata: Metadata = {
  title: { default: "Steve: you know the language, you still miss the message", template: "%s · Steve" },
  description:
    "Steve Decode turns what you hear (accents, local slang, borrowed words) into plain English: where, when, what to do and how much. It asks when it is not sure. Text only.",
  openGraph: {
    type: "website",
    siteName: "Steve",
    title: "Steve: you know the language, you still miss the message",
    description: "Where, when, what to do and how much, from accented or mixed speech. Text only, nothing stored.",
  },
  twitter: {
    card: "summary",
    title: "Steve: you know the language, you still miss the message",
    description: "Where, when, what to do and how much, from accented or mixed speech. Text only, nothing stored.",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f5ef" },
    { media: "(prefers-color-scheme: dark)", color: "#14181f" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} ${display.variable}`}>
      <body>
        <Providers>
          <div id="app-root">
            <a
              href="#main"
              className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
            >
              Skip to content
            </a>
            <WakingBanner />
            <WarmUp />
            <main id="main">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}

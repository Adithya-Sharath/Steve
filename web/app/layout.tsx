import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import { Providers } from "@/components/providers";
import { SiteFooter, SiteNav } from "@/components/site-nav";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const display = Instrument_Serif({ variable: "--font-display", subsets: ["latin"], weight: "400", style: ["normal", "italic"] });

export const metadata: Metadata = {
  title: { default: "Steve: did they really understand?", template: "%s · Steve" },
  description:
    "Steve checks that an important message actually got through. The reader explains it back in their own mix of languages, and Steve checks every dose, date and warning.",
  openGraph: {
    type: "website",
    siteName: "Steve",
    title: "Steve: did they really understand?",
    description: "“ok 👍” isn't understanding. Steve checks every dose, date and warning in the reader's own words.",
  },
  twitter: {
    card: "summary",
    title: "Steve: did they really understand?",
    description: "“ok 👍” isn't understanding. Steve checks every dose, date and warning in the reader's own words.",
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
            <SiteNav />
            <main id="main">{children}</main>
            <SiteFooter />
          </div>
        </Providers>
      </body>
    </html>
  );
}

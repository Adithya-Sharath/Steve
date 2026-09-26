import type { Metadata } from "next";
import { Showcase } from "@/components/decode/showcase";

export const metadata: Metadata = {
  title: "Steve",
  description: "Tap to listen. Steve decodes accents and local phrases into plain English: where, when, what to do and how much. Text only.",
};

/** The whole app is this one screen (showcase branch). */
export default function Home() {
  return <Showcase />;
}

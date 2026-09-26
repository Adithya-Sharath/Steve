import type { Metadata } from "next";
import { ListenScreen } from "@/components/decode/listen-screen";

export const metadata: Metadata = {
  title: "Listen",
  description: "Tap to listen or paste a message. Steve decodes accents and local phrases into plain English, as text.",
};

export default function ListenPage() {
  return <ListenScreen />;
}

import type { AccentHint, ReplyLanguage } from "./types";

/** Language names in their own scripts (the first-run picker), plus the English name for screen readers. */
export const LANGUAGES: { id: ReplyLanguage; native: string; english: string; dir: "ltr" | "rtl"; bcp47: string }[] = [
  { id: "ml", native: "മലയാളം", english: "Malayalam", dir: "ltr", bcp47: "ml" },
  { id: "hi", native: "हिंदी", english: "Hindi", dir: "ltr", bcp47: "hi" },
  { id: "ur", native: "اردو", english: "Urdu", dir: "rtl", bcp47: "ur" },
  { id: "tl", native: "Tagalog", english: "Tagalog", dir: "ltr", bcp47: "tl" },
  { id: "bn", native: "বাংলা", english: "Bengali", dir: "ltr", bcp47: "bn" },
  { id: "en", native: "English", english: "English", dir: "ltr", bcp47: "en" },
];

export const languageInfo = (id: ReplyLanguage) => LANGUAGES.find((l) => l.id === id) ?? LANGUAGES[LANGUAGES.length - 1];

/** Who is speaking (optional): picks the accent pack. Not a judgement about anyone: it only tells Steve which sound patterns to expect. */
export const ACCENTS: { id: AccentHint | ""; label: string }[] = [
  { id: "", label: "Not sure" },
  { id: "ar", label: "Arabic speaker" },
  { id: "hi", label: "Hindi / Urdu speaker" },
  { id: "ml", label: "Malayalam speaker" },
  { id: "tl", label: "Filipino speaker" },
];

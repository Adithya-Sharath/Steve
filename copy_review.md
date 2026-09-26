# Copy review sheet (native speakers and a lawyer: please check)

Everything below was written by the developers, **none of it has been checked by a native speaker or a lawyer**. Until it is, treat it as a draft.
Every accent rule (`ACCENT_REVIEW.md`), glossary entry (`GLOSSARY_REVIEW.md`) and lexicon entry (`LEXICON_REVIEW.md`) is `verified: false` for the same reason.

## 1. The notice shown to the other person while the microphone is on (`/listen`)

| Language | Text | Status |
|---|---|---|
| English | 🎧 Steve is helping me understand. Nothing is recorded. | needs review |
| Arabic | ستيف يساعدني على الفهم. لا يتم تسجيل أي شيء. | **needs native review: written by the developers, unverified**; check grammar, tone and whether "Steve" should be transliterated as "ستيف" |

**Accuracy question for legal review:** "Nothing is recorded" is the owner's wording. What actually happens: the browser records a short clip (30 s at most), sends it to the
speech-to-text service (Sarvam), and the server drops the audio as soon as the transcript comes back; Steve stores no audio and no message text (only an open
clarifying question keeps the text in memory for 10 minutes). The audio does pass through a third-party service, so "nothing is recorded" may be too strong. Please
decide whether to say "Steve does not save recordings" instead, and whether recording a colleague's or a manager's speech in person needs consent in the UAE (this is not
legal advice, and the app makes no legal claim).

## 2. "Say it back" phrases (English, shown as large text for the worker to show to the other person)

| Phrase | When | Status |
|---|---|---|
| Sorry, parking or barking? | built from an open question's first two options | wording generated from the question; check tone |
| Can you say that again slowly, please? | always available | needs review |
| Can you write it down for me, please? | when a question is still open | needs review |

## 3. Messages shown by the app (English)

| Message | Where |
|---|---|
| Voice isn't available right now, please type or paste the message. | voice off |
| Voice is busy for today, please type or paste the message. | daily voice limit reached |
| I couldn't listen to that voice note, please try again or type the message. | speech service failed |
| I couldn't find anything to decode. Try again or paste the message. | nothing was heard |
| That's fine. You can show the other person the phrase below and ask again. | worker chose "Not sure" |
| Translation isn't available right now, showing English. | no translation provider |
| Translation is busy for today, showing English. | daily translation limit |
| The translation didn't pass the number check, so I'm showing English. | number check failed |
| Steve does not save voice notes or messages. Your language choice stays on this phone. | footer of `/listen` |

All of these avoid words like "wrong", "incorrect" or "bad English"; a test scans the API responses for them.

## 4. Language names in the first-run picker

മലയാളം (Malayalam) · हिंदी (Hindi) · اردو (Urdu) · Tagalog · বাংলা (Bengali) · English. The interface around the card is in English for now; only the card
content is translated (machine translation, not reviewed). Please tell us whether the buttons should also carry a short instruction in each language.

## 5. Translations of the card itself

Produced by Sarvam (`sarvam-translate`) or Gemini, checked only for numbers (a translation that changes a number is dropped). **Nobody has checked that a negation
("do not pay") survives translation into Malayalam, Hindi, Urdu, Bengali or Tagalog.** A native speaker should test a set of negated instructions before anyone relies on
the translated card; until then the English card is one tap away ("Show English") and WhatsApp replies offer "Reply EN for English".

## 6. WhatsApp messages (English; only the privacy line is translated)

| Message | Where |
|---|---|
| Hello! I'm Steve. I help you understand what people say to you. Choose your language: reply with a number. 1 മലയാളം ... 6 English | first message from a new number |
| I delete your voice notes after listening. Your boss can't see this chat. | onboarding, translated into the chosen language (machine translation, unreviewed) |
| Here is an example. Someone says: ... | onboarding sample |
| Now forward me a voice note (up to 30 seconds) or send me a message. Reply HELP any time. | onboarding |
| Steve helps you understand what people say. - Forward or send a voice note... Steve does not save your voice notes or messages. | `HELP` |
| I can read voice notes and text for now. | an image or other file |
| That voice note is too long. Please send one up to 30 seconds. / I couldn't listen to that voice note. Please try again, or type the message. | voice problems |
| I couldn't find anything to decode. Try again or send the message as text. | nothing heard |
| That question has expired. Please send the message again. | a number sent after 10 minutes |
| You've sent a lot of messages. Please try again in a little while. | per-number limit (sent once an hour) |
| I couldn't finish that. Please try again in a moment. | unexpected problem |

**Accuracy question (needs a lawyer, and depends on your Twilio settings):** the onboarding sentence "I delete your voice notes after listening. Your boss can't see this chat."
is the owner's wording. Steve drops the audio from memory after one speech-to-text call and stores no audio and no text, but **Twilio keeps its own logs and media** unless you
delete them, and Sarvam receives the audio to transcribe it. Please decide whether the sentence is true enough as written. The WhatsApp commands (`HELP`, `LANGUAGE`, `EN`) are
English words for now; the prompt asked for commands "in any language", but no verified translations of them exist here, so none were invented.

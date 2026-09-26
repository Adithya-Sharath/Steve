# Demo video script (≤ 2:00)

**Before recording:** `make dev` (or the two commands in README), open <http://localhost:3000/demo> once (it seeds the data),
have the reader page open on a phone (deployed URL or LAN address; the microphone needs HTTPS or localhost).
If speech-to-text is slow or off, use the **preset reply buttons**: nothing in the demo depends on the mic.

| Time | On screen | Say |
|---|---|---|
| **0:00–0:15** | Landing hero, animation looping: message → Manglish voice reply → chips light up | "About 19% of answers about prescription labels are wrong. Teach-back fixes most of it, but the research excluded people with language barriers. In the UAE, that is millions of people who switch tongues mid-sentence." |
| **0:15–0:45** | `/app/new`. Pick **Pharmacy**, click the *Pharmacy* example, **Find key facts**. Chips animate in. Edit one, toggle *Critical*. **Confirm & get link**: QR + WhatsApp text appear | "A pharmacist writes the message. No LLM needed: rules pull out the key facts, and she confirms them." |
| **0:45–1:10** | Phone: reader page. Record (or type): *"randu gulika, food kazhinju, raavile vaikittu, oru week"*. Thank-you screen | "The patient explains it back in Manglish, spelled however they like. They never see a score." |
| **1:10–1:35** | Laptop `/app/m/…` updates live. Cards flip from shimmer to status. **Duration: Wrong** ("oru week = 7 days ≠ 5 days"); **Stop if rash: Missing**. Hover a card → its words light up in the transcript. Click **Draft follow-up** | "Duration is wrong: 'oru week' is seven days, not five. And the rash warning was never mentioned. She re-explains only what failed." |
| **1:35–1:50** | Flip **LLM helper** off (nav). Repeat a preset reply from the sender page: still works. Cut to `/eval`: false "understood" tile | "Turn the LLM off and nothing changes: the judge is deterministic code. The number we care about is false 'understood'." |
| **1:50–2:00** | Landing headline, repo URL | "'ok 👍' isn't understanding. Steve." |

**Honest-numbers reminder for the eval shot:** say "on our development data" if you quote a number; the eval page's caveat box is on screen.

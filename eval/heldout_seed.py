"""BLIND held-out replies. Written AFTER the engine was frozen for this round, gold labelled by reading them, and
evaluated once. They are deliberately messier than the development set: words outside the lexicon, questions,
half-answers, wrong actions, typos. Author: developer/assistant, NOT native speakers (needs native review).

Gold shorthand as in handwritten_seed.py.
"""

from __future__ import annotations

import json

from handwritten_seed import L

ROWS: list[tuple[str, str, str, str, str]] = [
    ("pharmacy", "manglish", "doctor njan randu tablet kazhikkum, food kazhinju, rand neram, 5 day, rash undayal medicine nirthum", "u", ""),
    ("pharmacy", "hinglish", "sir main do goli lunga khana khane ke baad, subah aur shaam, pura hafta", "u", "dur=w rash=m"),
    ("pharmacy", "hinglish", "dawai din mein 2 baar leni hai, khane ke baad, 5 din tak, rash ho jaye to doctor ko dikhana", "u", "dose=m rash=m"),
    ("pharmacy", "arabizi", "akhod ithnain habba ba3d el akl, marratain fi el yom, khamsa ayyam, w law sar 7asasiya awaqqif", "u", ""),
    ("pharmacy", "arabizi", "ithnain habba mara wa7da bel yom ba3d el akl 5 ayyam", "u", "freq=w rash=m"),
    ("pharmacy", "taglish", "iinom ko po yung gamot 2 tabs after meals, dalawang beses sa isang araw, 5 days, tapos kung magka-rash titigil po ako", "u", ""),
    ("pharmacy", "taglish", "sir 2 tablets bago kumain, 2x a day, 5 days", "u", "timing=w rash=m"),
    ("pharmacy", "english", "Just to confirm: two pills, after food, twice a day, five days. If a rash shows up I keep taking them and call you", "u", "rash=w"),
    ("pharmacy", "english", "ok got it", "m", ""),
    ("pharmacy", "hinglish", "goli khane se pehle leni hai ya baad mein?", "m", ""),
    ("child-syrup", "hinglish", "bachche ko 5 ml syrup din mein teen baar, ek hafta, bukhar aaye to clinic ko phone karna", "u", ""),
    ("child-syrup", "manglish", "kuttikku anju ml moonu neram, oru aazhcha, pani vannal clinic vilikkanam", "u", ""),
    ("child-syrup", "english", "5 mls thrice daily for a week, ring the clinic if temperature", "u", ""),
    ("child-syrup", "taglish", "limang ml, tatlong beses, isang linggo. kapag lagnat, huwag tumawag", "u", "fever=n"),
    ("child-syrup", "hinglish", "5 ml subah dopahar shaam, 10 din", "u", "dur=w fever=m"),
    ("site-safety", "hinglish", "har ghante ek bottle pani, dopahar saade barah baje 15 min ka break, chakkar aaye to supervisor ko batana", "u", "dizzy=m"),
    ("site-safety", "english", "one bottle of water every hour, 15 min break under shade at 12:30, stop work if dizzy", "u", ""),
    ("site-safety", "taglish", "kada oras isang bote ng tubig, 12:30 break ng 15 minuto, kung nahihilo tumigil sa trabaho", "u", ""),
    ("site-safety", "arabizi", "kul sa3a bottle, 12:30 istiraha 15 daqiqa, ida dokha wagif shughl", "u", ""),
    ("site-safety", "english", "drink water and take break in the shade around noon", "m", ""),
    ("visa-hr", "english", "2 passport photos and the copy by Thursday, fee 150 AED, and no travelling until the visa is stamped", "u", ""),
    ("visa-hr", "hinglish", "2 photo aur copy guruvaar tak, 150 rupaye fees, visa aane tak bahar mat jana", "u", "fee=w"),
    ("visa-hr", "taglish", "dalawang photo sa huwebes, 150 AED, pwede na akong bumiyahe", "u", "no_travel=n"),
    ("visa-hr", "manglish", "randu photo, vyazham vare, 150 dirham, visa stamp cheythittu mathram yathra", "u", ""),
    ("visa-hr", "arabizi", "thalatha photo, jum3a, 150 dirham", "u", "photos=w deadline=w no_travel=m"),
    ("school-trip", "english", "Trip Monday. Pay 30 dirhams and bring signed form Friday. Water bottle for the kids", "u", ""),
    ("school-trip", "hinglish", "somvaar ko trip hai, 30 dirham aur form shukravaar tak, bacchon ko paani ki bottle dena", "u", ""),
    ("school-trip", "manglish", "monday-kku trip, friday-kku munpu 30 dirham, form, bottle", "u", ""),
    ("school-trip", "taglish", "lunes ang field trip, 30 dirham at form sa biyernes, magdala ng bote ng tubig", "u", ""),
    ("school-trip", "english", "trip is on Tuesday, 30 dirham, form by Friday", "u", "trip=w bottle=m"),
    ("child-rash-med", "english", "1 tablet after food, 2 times a day, 3 days, and if there is any rash I will stop giving it", "u", "rash=m"),
    ("child-rash-med", "hinglish", "ek goli khane ke baad, subah shaam, teen din, rash aaye to turant call karna", "u", ""),
    ("payslip", "english", "salary 2500 dirham on Thursday, form by Monday", "u", ""),
    ("payslip", "hinglish", "2500 aed guruvaar ko, form somvaar tak dena hai", "u", ""),
    ("clinic-followup", "english", "friday I come back, medicine three times a day for five days, not travelling", "u", ""),
    ("clinic-followup", "hinglish", "shukravaar ko aana hai, din mein do baar, paanch din, safar theek hai", "u", "freq=w no_travel=n"),
    ("inhaler", "english", "2 puffs twice daily, if I feel dizzy I keep using it", "u", "dizzy=w"),
    ("eye-drops", "hinglish", "ek ek boond dono aankh mein, din mein teen baar, das din", "u", ""),
    ("eye-drops", "manglish", "randu thulli randu neram pathu divasam", "u", "dose=w freq=w"),
]


def heldout_rows(messages: dict[str, dict], start: int = 1) -> list[dict]:
    out = []
    for i, (mid, lang, text, default, over) in enumerate(ROWS, start):
        gold = {f["id"]: L[default] for f in messages[mid]["facts"]}
        for tok in over.split():
            k, v = tok.split("=")
            assert k in gold, (mid, k)
            gold[k] = L[v]
        out.append(
            {
                "reply_id": f"ho-{i:03d}",
                "message_id": mid,
                "lang_mix": lang,
                "reply_text": text,
                "gold_labels": json.dumps(gold, ensure_ascii=False),
                "author": "heldout-blind (assistant-drafted; needs native review)",
                "synthetic": "false",
            }
        )
    return out

"""Seed set of natural, hand-written replies with gold labels decided by a human reading them (not by the engine).

IMPORTANT: these were drafted by the developer/assistant, NOT by native speakers. They exist so the eval has a
non-synthetic slice from day one. Teammates: replace/extend them with real replies in your own languages, in
data/replies.csv (see README "Adding real replies"). Several rows are deliberately hard (words outside the lexicon,
unusual phrasing) so the eval can show where the engine is weak.

Gold shorthand: u=understood w=wrong m=missing n=negated. `default` applies to every fact not listed.
"""

from __future__ import annotations

import json

L = {"u": "understood", "w": "wrong", "m": "missing", "n": "negated", "c": "unclear"}

# (message_id, lang_mix, reply, default, overrides)
ROWS: list[tuple[str, str, str, str, str]] = [
    # --- pharmacy (dose, timing, freq, dur, rash->stop) -------------------------------------------------
    ("pharmacy", "manglish", "randu gulika, food kazhinju, raavile vaikittu, oru week", "u", "dur=w rash=m"),
    ("pharmacy", "manglish", "doctor, randu tablet food kazhinju, randu neram, anju divasam, rash vannal stop cheyyam", "u", ""),
    ("pharmacy", "manglish", "5 days randu neram randu gulika, rash vannalum nirthanda", "u", "timing=m rash=n"),
    ("pharmacy", "manglish", "ath randu gulika undu, food kazhinju kazhikkanam, randu neram, anju divasam", "u", "rash=m"),
    ("pharmacy", "manglish", "moonu gulika food kazhinju randu neram anju divasam", "u", "dose=w rash=m"),
    ("pharmacy", "hinglish", "do goli khane ke baad, subah shaam, paanch din. rash aaye to band kar dena", "u", ""),
    ("pharmacy", "hinglish", "mujhe subah aur raat ko khane ke baad 2 goli leni hai 5 din tak", "u", "rash=m"),
    ("pharmacy", "hinglish", "teen goli din mein do baar khane ke baad paanch din", "u", "dose=w rash=m"),
    ("pharmacy", "hinglish", "khane se pehle do goli, subah shaam, 5 din", "u", "timing=w rash=m"),
    ("pharmacy", "hinglish", "goli khane ke baad leni hai, paanch din, subah shaam", "u", "dose=m rash=m"),
    ("pharmacy", "hinglish", "twice a day, 2 goli, khane ke baad, one week", "u", "dur=w rash=m"),
    ("pharmacy", "arabizi", "ithnain habba ba3d al akl marratain 5 ayyam, law sar 7asasiya waqqif el dawa", "u", ""),
    ("pharmacy", "arabizi", "khamsa ayyam ithnain habba marratain gabl al akl", "u", "timing=w rash=m"),
    ("pharmacy", "arabizi", "ithnain habba ba3d al akl marratain sab3a ayyam", "u", "dur=w rash=m"),
    ("pharmacy", "taglish", "dalawang tableta pagkatapos kumain, dalawang beses, limang araw. kapag may rash, huwag itigil", "u", "rash=n"),
    ("pharmacy", "taglish", "2 tablets after kumain po, twice a day, 5 days lang", "u", "rash=m"),
    ("pharmacy", "taglish", "isang tableta lang po pagkatapos kumain, dalawang beses, limang araw", "u", "dose=w rash=m"),
    ("pharmacy", "english", "I take two tablets after eating, twice daily for five days and stop if I get a rash", "u", ""),
    ("pharmacy", "english", "ok will take medicine after food", "m", "timing=u"),
    ("pharmacy", "english", "ok sir noted 👍", "m", ""),
    ("pharmacy", "english", "understood thank you", "m", ""),
    # --- child-syrup (dose 5ml, freq 3, dur 7, fever->call) ---------------------------------------------
    ("child-syrup", "english", "5 ml three times a day for 7 days, call if fever", "u", ""),
    ("child-syrup", "hinglish", "paanch ml din mein teen baar, saat din, bukhar ho to call karo", "u", ""),
    ("child-syrup", "manglish", "anju ml moonu neram, oru week, fever vannal vilikkanam", "u", ""),
    ("child-syrup", "arabizi", "khamsa ml thalatha marrat sab3a ayyam, law 7ma ittasil", "u", ""),
    ("child-syrup", "english", "5 ml twice a day for 7 days", "u", "freq=w fever=m"),
    ("child-syrup", "english", "5 ml 3 times a day 7 days, no need to call", "u", "fever=n"),
    # --- site-safety (water 1 bottle, hourly, break 15 min, at 12:30, dizzy->stop) -----------------------
    ("site-safety", "english", "drink one bottle of water every hour, 15 minute break at 12:30, if dizzy stop work", "u", ""),
    ("site-safety", "hinglish", "har ghante ek bottle paani, saadhe barah baje 15 minute break, chakkar aaye to kaam band kar dena", "u", ""),
    ("site-safety", "manglish", "oru bottle vellam ellaa manikkoorum, 12:30 nu 15 minute break, dizzy aayal work nirthanam", "u", ""),
    ("site-safety", "taglish", "kada oras isang bottle, 12:30 ng 20 minuto na break, kapag dizzy itigil ang trabaho", "u", "break_len=w"),
    ("site-safety", "arabizi", "kul sa3a bottle wa7ed, 12:30 rest 15 daqiqa, law dokha la waqqif", "u", "dizzy=n"),
    ("site-safety", "english", "one bottle every hour and rest at 12:30", "u", "break_len=m dizzy=m"),
    ("site-safety", "hinglish", "har ghante paani peena hai, 12:30 par break", "u", "water=m break_len=m dizzy=m"),
    ("site-safety", "english", "drink water often and take rest in the shade", "m", ""),
    # --- visa-hr (2 photos, thursday, 150 AED, no travel) ---------------------------------------------------
    ("visa-hr", "hinglish", "2 photo aur guruvaar tak passport copy jama karna, fees 150 dirham, visa lagne tak safar mat karna", "u", ""),
    ("visa-hr", "english", "2 photos by Thursday, 150 dirham fee, no travel till visa", "u", ""),
    ("visa-hr", "manglish", "randu photo, vyazham-kku munpu, 150 dirham, visa varunnathu vare yathra pokaruthu", "u", ""),
    ("visa-hr", "taglish", "dalawang photo, sa huwebes, 150 dirham, huwag bumiyahe hangga't walang visa", "u", ""),
    ("visa-hr", "arabizi", "ithnain photo, youm al jum3a, 150 dirham, la safar", "u", "deadline=w"),
    ("visa-hr", "english", "2 photos Thursday 115 AED don't travel", "u", "fee=w"),
    ("visa-hr", "taglish", "dalawang photo, huwebes, hindi 150 AED, huwag bumiyahe", "u", "fee=n"),
    ("visa-hr", "hinglish", "2 photo guruvaar tak dena hai", "u", "fee=m no_travel=m"),
    # --- school-trip (trip monday, 30 AED, due friday, 1 form, 1 bottle) -------------------------------------
    ("school-trip", "manglish", "monday trip aanu. friday-kku 30 dirham um oru signed form um kodukkanam. oru water bottle konduvaranam", "u", ""),
    ("school-trip", "hinglish", "somvaar ko trip hai, shukravaar tak 30 dirham aur ek form dena, ek bottle laana", "u", ""),
    ("school-trip", "hinglish", "trip somvaar ko hai, shukravaar tak 20 dirham aur ek form dena, ek bottle laana", "u", "money=w"),
    ("school-trip", "taglish", "lunes ang trip, biyernes 30 dirham at isang form, huwag magdala ng isang bottle", "u", "bottle=n"),
    ("school-trip", "english", "trip on monday, 30 aed and signed form on friday, water bottle", "u", ""),
    ("school-trip", "english", "trip is monday, pay 30 AED", "u", "due=m form=m bottle=m"),
    # --- child-rash-med (1 tablet, after food, twice, 3 days, rash->call) --------------------------------------
    ("child-rash-med", "hinglish", "bachche ko ek goli khane ke baad din mein do baar teen din, rash ho to call karo", "u", ""),
    ("child-rash-med", "manglish", "oru gulika food kazhinju randu neram moonu divasam, rash vannal vilikkanam", "u", ""),
    ("child-rash-med", "taglish", "isang tableta pagkatapos kumain, dalawang beses, tatlong araw, tumawag kapag may rash", "u", ""),
    ("child-rash-med", "english", "1 tablet after food 2 times 5 days call if rash", "u", "dur=w"),
    ("child-rash-med", "english", "1 tablet after food twice a day 3 days, don't call if rash", "u", "rash=n"),
    # --- payslip / others ------------------------------------------------------------------------------------
    ("payslip", "english", "2500 AED on Thursday and form by Monday", "u", ""),
    ("payslip", "hinglish", "3500 dirham guruvaar ko, form somvaar tak", "u", "salary=w"),
    ("bp-tablet", "hinglish", "subah khane se pehle ek goli, 30 din", "u", ""),
    ("bp-tablet", "english", "1 tablet in the morning after food for 30 days", "u", "timing=w"),
    ("eye-drops", "english", "1 drop 3 times a day for 10 days", "u", ""),
    ("eye-drops", "manglish", "oru thulli moonu neram pathu divasam", "u", ""),
    ("eye-drops", "taglish", "isang patak, tatlong beses, sampung araw", "u", ""),
    ("inhaler", "english", "2 puffs twice a day, if dizzy stop and come back", "u", ""),
    ("bedtime-tablet", "english", "1 tablet at bedtime 14 days, call if rash", "u", ""),
    ("bedtime-tablet", "hinglish", "sone se pehle ek goli, chaudah din", "u", "rash=m"),
    ("shift-start", "english", "6:00 Sunday, 2 photos", "u", ""),
    ("shift-start", "hinglish", "ravivaar ko 6:00 baje aur 2 photo", "u", ""),
    ("visa-medical", "hinglish", "mangalvaar ko 9:30 par, 4 photo, 320 dirham", "u", ""),
    ("visa-medical", "arabizi", "4 photo, 320 dirham, tuesday 9:30", "u", ""),
    ("school-fee", "english", "450 AED by Wednesday, school opens Monday", "u", ""),
    ("school-fee", "taglish", "450 piso sa miyerkules, lunes ang balik", "u", "fee=w"),
    ("clinic-followup", "english", "come back friday, 3 times a day for 5 days, don't travel", "u", ""),
    ("clinic-followup", "hinglish", "shukravaar ko wapas aana, din mein teen baar, paanch din, safar mat karna", "u", ""),
]


def seed_rows(messages: dict[str, dict]) -> list[dict]:
    out = []
    for i, (mid, lang, text, default, over) in enumerate(ROWS, 1):
        ids = [f["id"] for f in messages[mid]["facts"]]
        gold = {fid: L[default] for fid in ids}
        for tok in over.split():
            k, v = tok.split("=")
            assert k in gold, (mid, k)
            gold[k] = L[v]
        out.append(
            {
                "reply_id": f"hw-{i:03d}",
                "message_id": mid,
                "lang_mix": lang,
                "reply_text": text,
                "gold_labels": json.dumps(gold, ensure_ascii=False),
                "author": "claude-draft (needs native-speaker review)",
                "synthetic": "false",
            }
        )
    return out

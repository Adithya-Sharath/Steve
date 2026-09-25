"""Hand-written phrase banks used to expand messages into labelled synthetic replies.

Gold labels come from CONSTRUCTION (we know which fact we made correct / wrong / negated / omitted), never from
running the engine. The banks are written by the team, with their own spelling variety, but they lean on words the
lexicon already knows, so synthetic accuracy OVERESTIMATES real-world accuracy. The report keeps synthetic and
hand-written results separate for that reason.
"""

from __future__ import annotations

import random

LANGS = ["manglish", "hinglish", "arabizi", "taglish", "english"]

NUM: dict[str, dict[int, list[str]]] = {
    "manglish": {1: ["onnu", "oru"], 2: ["randu", "rendu", "rndu", "randhu"], 3: ["moonu", "munnu", "moonnu"], 4: ["naalu", "nalu"], 5: ["anju", "anchu"], 6: ["aaru", "aru"], 7: ["ezhu", "elu"], 8: ["ettu"], 9: ["ombathu"], 10: ["pathu", "padhu"]},
    "hinglish": {1: ["ek"], 2: ["do"], 3: ["teen", "tin"], 4: ["chaar", "char"], 5: ["paanch", "panch", "paach"], 6: ["chhe", "chhah"], 7: ["saat"], 8: ["aath"], 9: ["nau"], 10: ["das", "dus"]},
    "arabizi": {1: ["wa7ed", "wahed", "wahid"], 2: ["ithnain", "ethnain", "itnen"], 3: ["thalatha", "tlatha", "thlatha"], 4: ["arba3a", "arbaa"], 5: ["khamsa", "5amsa", "khamse"], 6: ["sitta", "sita"], 7: ["sab3a", "saba3a"], 8: ["thamanya", "tmanya"], 9: ["tis3a", "tesaa"], 10: ["3ashra", "ashra"]},
    "taglish": {1: ["isa"], 2: ["dalawa"], 3: ["tatlo"], 4: ["apat"], 5: ["lima"], 6: ["anim"], 7: ["pito"], 8: ["walo"], 9: ["siyam"], 10: ["sampu"]},
    "english": {1: ["one"], 2: ["two"], 3: ["three"], 4: ["four"], 5: ["five"], 6: ["six"], 7: ["seven"], 8: ["eight"], 9: ["nine"], 10: ["ten"]},
}
TL_LINK = {"isa": "isang", "dalawa": "dalawang", "tatlo": "tatlong", "lima": "limang", "pito": "pitong", "walo": "walong", "sampu": "sampung"}

UNIT: dict[str, dict[str, list[str]]] = {
    "tablet": {"manglish": ["gulika", "tablet"], "hinglish": ["goli", "tablet", "tab"], "arabizi": ["habba", "7abba", "tablet"], "taglish": ["tableta", "tablet"], "english": ["tablet", "tablets", "pills"]},
    "ml": {k: ["ml"] for k in LANGS},
    "puff": {k: ["puff", "puffs"] for k in LANGS},
    "drop": {"manglish": ["thulli", "drop"], "hinglish": ["boond", "drop"], "arabizi": ["drops"], "taglish": ["patak", "drop"], "english": ["drop", "drops"]},
    "bottle": {k: ["bottle"] for k in LANGS},
    "photo": {k: ["photo", "photos"] for k in LANGS},
    "form": {k: ["form"] for k in LANGS},
}

DAYWORD = {"manglish": ["divasam"], "hinglish": ["din"], "arabizi": ["ayyam"], "taglish": ["araw"], "english": ["days"]}
MINWORD = {"manglish": ["minute", "minittu"], "hinglish": ["minute"], "arabizi": ["daqiqa", "minute"], "taglish": ["minuto", "minute"], "english": ["minutes"]}

FREQ_EVERY_HOUR = {"manglish": ["every hour"], "hinglish": ["har ghante"], "arabizi": ["kul sa3a"], "taglish": ["kada oras"], "english": ["every hour"]}
FREQ: dict[str, list[str]] = {  # {n} is replaced by a number word/digit
    "manglish": ["{n} neram", "{n} thavana", "dinavum {n} neram"],
    "hinglish": ["din mein {n} baar", "{n} baar", "roz {n} baar"],
    "arabizi": ["{n} marrat"],
    "taglish": ["{n} beses", "{n} beses sa isang araw", "{n} beses isang araw"],
    "english": ["{n} times a day", "{n} times daily"],
}
FREQ_FIXED = {
    "arabizi": {1: ["marra"], 2: ["marratain"]},
    "english": {1: ["once a day", "once daily"], 2: ["twice a day", "twice daily"], 3: ["thrice a day"]},
}

TIMING = {
    "after_food": {"manglish": ["food kazhinju", "bhakshanam kazhinju"], "hinglish": ["khane ke baad", "khana khane ke baad", "khane k baad"], "arabizi": ["ba3d al akl", "ba3d el akl"], "taglish": ["pagkatapos kumain", "pagkatapos ng kain"], "english": ["after food", "after meals", "after eating"]},
    "before_food": {"manglish": ["food munpu"], "hinglish": ["khane se pehle", "khane ke pehle"], "arabizi": ["gabl al akl", "qabl el akl"], "taglish": ["bago kumain"], "english": ["before food", "before meals"]},
    "morning": {"manglish": ["raavile", "ravile"], "hinglish": ["subah"], "arabizi": ["sabah"], "taglish": ["umaga"], "english": ["in the morning", "morning"]},
    "night": {"manglish": ["raathri", "rathri"], "hinglish": ["raat"], "arabizi": ["lail"], "taglish": ["gabi"], "english": ["at night", "night"]},
    "bedtime": {"manglish": ["bedtime"], "hinglish": ["sone se pehle", "bedtime"], "arabizi": ["bedtime"], "taglish": ["bedtime"], "english": ["at bedtime", "before bed"]},
}
TIMING_WRONG = {"after_food": "before_food", "before_food": "after_food", "morning": "night", "night": "morning", "bedtime": "morning"}

WEEKDAY = {
    "manglish": {"monday": ["thinkal", "monday"], "tuesday": ["chovva", "tuesday"], "wednesday": ["budhan", "wednesday"], "thursday": ["vyazham", "thursday"], "friday": ["velli", "friday"], "saturday": ["saturday"], "sunday": ["njayar", "sunday"]},
    "hinglish": {"monday": ["somvaar", "monday"], "tuesday": ["mangalvaar", "tuesday"], "wednesday": ["budhvaar", "wednesday"], "thursday": ["guruvaar", "thursday"], "friday": ["shukravaar", "friday"], "saturday": ["shanivaar"], "sunday": ["ravivaar", "sunday"]},
    "arabizi": {"monday": ["monday"], "tuesday": ["tuesday"], "wednesday": ["wednesday"], "thursday": ["khamis", "youm al khamis"], "friday": ["jum3a", "youm al jum3a"], "saturday": ["sabt"], "sunday": ["ahad"]},
    "taglish": {"monday": ["lunes"], "tuesday": ["martes"], "wednesday": ["miyerkules"], "thursday": ["huwebes"], "friday": ["biyernes"], "saturday": ["sabado"], "sunday": ["domingo"]},
    "english": {d: [d, d.capitalize()] for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

CURRENCY = {"AED": ["dirham", "AED", "dhs"]}

SYMPTOM = {
    "rash": {"manglish": ["rash"], "hinglish": ["rash"], "arabizi": ["rash"], "taglish": ["rash", "pantal"], "english": ["rash"]},
    "fever": {"manglish": ["fever"], "hinglish": ["bukhar", "fever"], "arabizi": ["fever"], "taglish": ["lagnat", "fever"], "english": ["fever"]},
    "dizzy": {"manglish": ["dizzy"], "hinglish": ["chakkar", "dizzy"], "arabizi": ["dokha", "dizzy"], "taglish": ["dizzy"], "english": ["dizzy"]},
    "travel": {k: ["travel"] for k in LANGS},
}

# (action, polarity) -> lang -> templates with {t} = trigger word
COND: dict[tuple[str, str], dict[str, list[str]]] = {
    ("stop", "correct"): {"manglish": ["{t} vannal nirthanam", "{t} vannaal nirthu"], "hinglish": ["{t} ho to band kar dena", "{t} aaye to rok do", "{t} ho toh band karo"], "arabizi": ["{t} waqqif", "law {t} wagif"], "taglish": ["kapag may {t}, itigil", "pag {t} tigil"], "english": ["if {t}, stop", "stop if {t}", "stop taking it if {t}"]},
    ("stop", "negated"): {"manglish": ["{t} vannalum nirthanda", "{t} vannal nirthanam venda"], "hinglish": ["{t} ho to band mat karo", "{t} aaye to rok mat do"], "arabizi": ["{t} la waqqif"], "taglish": ["kapag may {t}, huwag itigil"], "english": ["if {t}, don't stop", "do not stop if {t}"]},
    ("stop", "wrong"): {"manglish": ["{t} vannal continue"], "hinglish": ["{t} ho to continue karo"], "arabizi": ["{t} continue"], "taglish": ["kapag {t} ituloy"], "english": ["if {t}, continue"]},
    ("call", "correct"): {"manglish": ["{t} vannal vilikkanam"], "hinglish": ["{t} ho to call karo"], "arabizi": ["{t} ittasil"], "taglish": ["kapag {t} tumawag"], "english": ["if {t}, call", "call if {t}"]},
    ("call", "negated"): {"manglish": ["{t} vannal vilikkanam venda"], "hinglish": ["{t} ho to call mat karo"], "arabizi": ["{t} la ittasil"], "taglish": ["kapag {t} huwag tumawag"], "english": ["if {t}, don't call"]},
    ("avoid", "correct"): {"manglish": ["yathra pokaruthu"], "hinglish": ["safar mat karo", "travel mat karo"], "arabizi": ["la safar"], "taglish": ["huwag bumiyahe"], "english": ["do not travel", "don't travel"]},
    ("avoid", "wrong"): {k: ["I can travel"] for k in LANGS},  # says the opposite; gold = negated
}
NEG_AROUND = {"manglish": ("", "venda"), "hinglish": ("nahi", ""), "arabizi": ("mub", ""), "taglish": ("hindi", ""), "english": ("not", "")}

CHATTER = ["ok", "ok sir", "theek hai", "sheri", "noted", "haan ji", "okay okay", "👍", "ji", "alright", "tamam", "opo"]
JOINERS = [", ", ", ", " ", " . ", ", "]


def pick(rng: random.Random, xs: list[str]) -> str:
    return xs[rng.randrange(len(xs))]


def num_word(lang: str, n: int, rng: random.Random, linker: bool = False) -> str:
    """Digit sometimes, word when we have one. `linker` applies Tagalog -ng when a noun follows."""
    if n > 10 or rng.random() < 0.3:
        return str(n)
    w = pick(rng, NUM[lang][n])
    if lang == "taglish" and linker:
        w = TL_LINK.get(w, w)
    return w


def typo(word: str, rng: random.Random, p: float = 0.07) -> str:
    if len(word) < 5 or rng.random() > p:
        return word
    i = rng.randrange(1, len(word) - 1)
    return word[:i] + word[i + 1 :] if rng.random() < 0.5 else word[:i] + word[i] + word[i:]


def noisy(text: str, rng: random.Random) -> str:
    return " ".join(typo(w, rng) if w.isalpha() else w for w in text.split(" "))

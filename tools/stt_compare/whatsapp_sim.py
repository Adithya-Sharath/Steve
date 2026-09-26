"""WhatsApp-like degradation of clean speech: background noise at a chosen SNR, phone-quality downsampling, Opus at ~16 kbps in an Ogg container
(what a WhatsApp voice note is). A SIMULATION: it does not capture real handsets, real rooms, real network handling or real voices (D42).

Noise comes from DEMAND ("Diverse Environments Multichannel Acoustic Noise Database", Thiemann, Ito and Vincent, 2013), Zenodo record 1227121,
licence **CC BY 4.0** (attribution required; see DECISIONS D42). We use channel 1 of the 16 kHz versions of STRAFFIC (street traffic), PSTATION (a
crowded railway station) and TBUS (a bus, a steady engine-like hum; DEMAND has no fan recording).

    python tools/stt_compare/whatsapp_sim.py fetch          # download the three noise sets into the gitignored cache (about 370 MB)

Everything is written to gitignored folders; nothing here calls a speech provider.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audio as audio_tools  # noqa: E402

NOISE_DIR = HERE / ".cache" / "noise"
NOISE_SETS = ("STRAFFIC", "PSTATION", "TBUS")
NOISE_URL = "https://zenodo.org/records/1227121/files/{name}_16k.zip?download=1"
SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class Profile:
    name: str
    snr_db: float
    phone_rate: int = 8000  # narrowband "phone quality": a pessimistic reading of WhatsApp (real voice notes are often wideband)
    bitrate: str = "16k"
    noises: tuple[str, ...] = NOISE_SETS

    @property
    def folder(self) -> str:
        return f"l2arctic-scripted-{self.name}"


PROFILES = {
    "whatsapp-snr15": Profile("whatsapp-snr15", 15.0),
    "whatsapp-snr10": Profile("whatsapp-snr10", 10.0),
    "whatsapp-snr5": Profile("whatsapp-snr5", 5.0),
}


class SimError(Exception):
    pass


def _ffmpeg() -> str:
    exe = audio_tools.ffmpeg()
    if not exe:
        raise SimError("ffmpeg was not found (install it or set FFMPEG_DIR).")
    return exe


def decode(data: bytes, rate: int = SAMPLE_RATE) -> np.ndarray:
    """Any audio bytes -> float32 mono at `rate` (via ffmpeg)."""
    out = subprocess.run([_ffmpeg(), "-v", "error", "-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", str(rate), "pipe:1"],
                         input=data, capture_output=True, timeout=120, check=False)
    if out.returncode != 0 or not out.stdout:
        raise SimError(f"ffmpeg could not decode the audio: {out.stderr.decode(errors='replace')[:160]}")
    return np.frombuffer(out.stdout, dtype="<f4").copy()


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.0


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float, offset: int = 0) -> np.ndarray:
    """speech + a noise excerpt scaled so that 20*log10(rms(speech)/rms(noise part)) == snr_db; peak-limited so it cannot clip."""
    if len(noise) < len(speech):
        noise = np.tile(noise, len(speech) // max(len(noise), 1) + 1)
    start = offset % max(len(noise) - len(speech), 1)
    part = noise[start : start + len(speech)]
    ps, pn = rms(speech), rms(part)
    if ps == 0 or pn == 0:
        return speech.copy()
    part = part * (ps / (pn * 10 ** (snr_db / 20)))
    mixed = speech + part
    peak = float(np.max(np.abs(mixed)))
    return mixed / peak * 0.97 if peak > 0.97 else mixed


def encode_opus(x: np.ndarray, phone_rate: int, bitrate: str) -> bytes:
    """float32 16 kHz mono -> Opus in Ogg at `bitrate`, downsampled to `phone_rate` first (a WhatsApp-like voice note)."""
    out = subprocess.run(
        [_ffmpeg(), "-v", "error", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "pipe:0", "-ar", str(phone_rate),
         "-c:a", "libopus", "-b:a", bitrate, "-application", "voip", "-vbr", "on", "-f", "ogg", "pipe:1"],
        input=x.astype("<f4").tobytes(), capture_output=True, timeout=120, check=False)
    if out.returncode != 0 or not out.stdout:
        raise SimError(f"ffmpeg could not encode Opus: {out.stderr.decode(errors='replace')[:160]}")
    return out.stdout


def stable_int(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16)


def degrade(wav: bytes, noise: np.ndarray, profile: Profile, key: str) -> bytes:
    speech = decode(wav)
    return encode_opus(mix_at_snr(speech, noise, profile.snr_db, stable_int(profile.name, key)), profile.phone_rate, profile.bitrate)


def load_noise(name: str, cache: Path = NOISE_DIR) -> np.ndarray:
    """Channel 1 of a DEMAND 16 kHz set as float32 (the zip holds 16 channel wavs)."""
    zpath = cache / f"{name}_16k.zip"
    if not zpath.exists():
        raise SimError(f"{zpath.name} not found in {cache}. Run: python tools/stt_compare/whatsapp_sim.py fetch")
    with zipfile.ZipFile(zpath) as z:
        member = next((n for n in sorted(z.namelist()) if n.lower().endswith("ch01.wav")), None)
        if member is None:
            raise SimError(f"{zpath.name} has no ch01.wav")
        return decode(z.read(member))


def noise_for(profile: Profile, index: int, noises: dict[str, np.ndarray]) -> tuple[str, np.ndarray]:
    name = profile.noises[index % len(profile.noises)]
    return name, noises[name]


def fetch(cache: Path = NOISE_DIR) -> None:
    import urllib.request

    cache.mkdir(parents=True, exist_ok=True)
    for n in NOISE_SETS:
        dst = cache / f"{n}_16k.zip"
        if dst.exists() and dst.stat().st_size > 10_000_000:
            print("have", dst.name)
            continue
        print("downloading", dst.name, "(CC BY 4.0, DEMAND, Zenodo 1227121)")
        with urllib.request.urlopen(NOISE_URL.format(name=n), timeout=120) as r, dst.with_suffix(".part").open("wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        dst.with_suffix(".part").replace(dst)


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        fetch()
    else:
        print(__doc__)

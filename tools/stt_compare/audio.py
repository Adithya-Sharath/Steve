"""Audio helpers: which files Sarvam takes as they are (WhatsApp voice notes included), and conversion for the rest.

WhatsApp voice notes are Opus in an Ogg container, saved as `.ogg` (sometimes `.opus`). Sarvam's REST endpoint accepts OGG and OPUS
directly (docs.sarvam.ai, checked 2026-09-26), so they are sent unchanged. Formats it does not list (`.oga`, `.3gp`, `.caf`, `.mka`, `.mov`, ...)
are converted with ffmpeg to 16 kHz mono WAV in `.cache/converted/` (gitignored); the original file is never modified.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

SUPPORTED = {".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".opus", ".webm", ".flac", ".aac", ".aif", ".aiff", ".amr", ".wma"}
CONVERTIBLE = {".oga", ".3gp", ".3g2", ".caf", ".mka", ".mkv", ".mov", ".m4b", ".mpga", ".mpeg"}
MAX_SECONDS = 30.0  # Sarvam REST limit per request


class AudioError(Exception):
    pass


def _tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for base in (os.getenv("FFMPEG_DIR", ""), r"C:\ffmpeg\bin"):
        cand = Path(base) / (name + (".exe" if os.name == "nt" else ""))
        if base and cand.exists():
            return str(cand)
    return None


def ffmpeg() -> str | None:
    return _tool("ffmpeg")


def ffprobe() -> str | None:
    return _tool("ffprobe")


def allowed_extension(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED | CONVERTIBLE


def needs_conversion(name: str) -> bool:
    return Path(name).suffix.lower() in CONVERTIBLE


def duration_seconds(path: Path) -> float | None:
    """Length via ffprobe; None when ffprobe is not installed or cannot read the file."""
    probe = ffprobe()
    if not probe:
        return None
    try:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                             capture_output=True, text=True, timeout=30, check=False)
        return float(out.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


def to_wav(src: Path, cache: Path) -> Path:
    """16 kHz mono WAV copy of `src` in `cache` (reused when it already exists). Raises AudioError with a clear message."""
    exe = ffmpeg()
    if not exe:
        raise AudioError(f"{src.name} needs converting but ffmpeg was not found. Install ffmpeg (or set FFMPEG_DIR) or convert it to .wav/.ogg/.mp3 first.")
    key = hashlib.sha256(src.read_bytes()).hexdigest()[:24]
    dst = cache / f"{key}.wav"
    if dst.exists():
        return dst
    cache.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.wav")
    proc = subprocess.run([exe, "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(tmp)],
                          capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise AudioError(f"ffmpeg could not convert {src.name}: {proc.stderr.strip()[:200]}")
    tmp.replace(dst)
    return dst


def prepare(path: Path, cache: Path) -> tuple[str, bytes]:
    """-> (file name to send, bytes to send). Supported formats are sent untouched; convertible ones as a WAV copy."""
    if needs_conversion(path.name):
        wav = to_wav(path, cache)
        return path.stem + ".wav", wav.read_bytes()
    return path.name, path.read_bytes()

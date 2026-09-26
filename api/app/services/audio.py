"""Audio facts we can know without decoding it: how long a WAV or Ogg-Opus/Vorbis upload is (D45).

The API never stores audio and never decodes it; it only needs to refuse clips over the length cap before paying for speech-to-text.
WAV (what the web recorder sends, `web/lib/wav.ts`) is exact; Ogg is read from its last page's granule position. For other containers (webm, mp3, m4a...)
the length is unknown (`None`): the byte cap still applies and Sarvam itself refuses more than about 30 s per request.
"""

from __future__ import annotations

import struct


def wav_seconds(data: bytes) -> float | None:
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos, rate, size = 12, 0, None
    while pos + 8 <= len(data):
        cid, clen = data[pos : pos + 4], struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        body = pos + 8
        if cid == b"fmt " and body + 16 <= len(data):
            _fmt, _ch, rate, byte_rate, _block, _bits = struct.unpack("<HHIIHH", data[body : body + 16])
            if byte_rate:
                rate = byte_rate  # bytes per second
        elif cid == b"data":
            size = min(clen, len(data) - body) if clen != 0xFFFFFFFF else len(data) - body
            break
        pos = body + clen + (clen & 1)
    if size is None or not rate:
        return None
    return size / rate


def ogg_seconds(data: bytes) -> float | None:
    if data[:4] != b"OggS":
        return None
    last = data.rfind(b"OggS")
    if last < 0 or last + 14 > len(data):
        return None
    granule = struct.unpack("<q", data[last + 6 : last + 14])[0]
    if granule <= 0:
        return None
    rate = 48_000  # Opus always counts in 48 kHz; for Vorbis read the rate from the identification header
    if b"OpusHead" not in data[:200]:
        i = data.find(b"\x01vorbis", 0, 200)
        if i < 0 or i + 16 > len(data):
            return None
        rate = struct.unpack("<I", data[i + 12 : i + 16])[0] or 0
        if not rate:
            return None
    return granule / rate


def duration_seconds(data: bytes) -> float | None:
    """Seconds of audio if we can tell from the container, else None."""
    return wav_seconds(data) or ogg_seconds(data)

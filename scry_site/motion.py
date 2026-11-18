"""A demo's moving picture: the file's size and frame times, the tube it fills, and its moments lit
in time with it."""

from __future__ import annotations

import html
import struct
from dataclasses import dataclass
from pathlib import Path

from scry_site.sources import Invalid

STILL, LOOP = "screen.png", "loop.webp"
#: A full screen is shown 4:3, as on the monitor it was made for. A picture wider than a 16:10
#: screen is a band cut from one, and keeps that screen's pixel shape: 320 x 144 out of 320 x 200.
FULL, WIDEST = 4 / 3, 16 / 10


@dataclass(frozen=True)
class Clip:
    width: int
    height: int
    frames_ms: tuple[int, ...]

    @property
    def ms(self) -> int:
        return sum(self.frames_ms)

    @property
    def aspect(self) -> float:
        return max(FULL, self.width / self.height * FULL / WIDEST)

    def length(self) -> str:
        s = round(self.ms / 1000)
        return f"{s // 60}:{s % 60:02d}"


def clip(path: Path, where: str) -> Clip:
    """The canvas and the frame durations of an animated WebP, read from its chunks."""
    try:
        data = path.read_bytes()
    except OSError as e:
        raise Invalid(f"cannot read {where}: {e}") from e
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise Invalid(f"{where} is not a WebP file")
    width = height = 0
    frames: list[int] = []
    at = 12
    while at + 8 <= len(data):
        tag, size = data[at:at + 4], struct.unpack("<I", data[at + 4:at + 8])[0]
        body = data[at + 8:at + 8 + size]
        if tag == b"VP8X" and len(body) >= 10:
            width = 1 + int.from_bytes(body[4:7], "little")
            height = 1 + int.from_bytes(body[7:10], "little")
        elif tag == b"ANMF" and len(body) >= 15:
            frames.append(int.from_bytes(body[12:15], "little"))
        at += 8 + size + (size & 1)
    if not width or not frames or not sum(frames):
        raise Invalid(f"{where} is not an animated WebP: {len(frames)} frames read")
    return Clip(width, height, tuple(frames))


def picture(base: str, c: Clip, alt: str, *, tape: bool = False, lazy: bool = False) -> str:
    """The clip in its tube, its still in its place for a reader who asks for less motion. The
    tube never grows past the file's own width."""
    cls = "crt tape" if tape else "crt"
    pad = (0.75 - 1 / c.aspect) / 2 * 100
    style = f"--ar:{c.aspect:.4f};--pad:{pad:.2f}%;max-width:{c.width}px"
    load = ' loading="lazy"' if lazy else ""
    return (f'<div class="{cls}" style="{style}"><picture>'
            f'<source media="(prefers-reduced-motion: reduce)" srcset="{base}{STILL}">'
            f'<img src="{base}{LOOP}" width="{c.width}" height="{c.height}"{load} '
            f'alt="{html.escape(alt)}"></picture></div>')


def osd(name: str, c: Clip) -> str:
    return (f'<p class="osd" aria-hidden="true"><span class="rec">&#9654; PLAY</span>'
            f"<span>{html.escape(name.upper())} {c.length()}</span></p>")


def keyframes(c: Clip, ms: tuple[int, ...], where: str) -> str:
    """One pair of keyframes a moment: its sentence lit, and its numeral, while it plays."""
    if sum(ms) != c.ms:
        raise Invalid(f"{where}: the moments last {sum(ms)} ms and the picture {c.ms} ms")
    rules = []
    start = 0
    for i, d in enumerate(ms, 1):
        a, b = start / c.ms * 100, (start + d) / c.ms * 100
        start += d
        on_text, off_text = "color:var(--fg)", "color:var(--muted)"
        on_mark = "color:var(--red);text-shadow:0 0 10px rgba(var(--glow),.8)"
        off_mark = "color:var(--edge);text-shadow:none"
        for name, on, off in (("take", on_text, off_text), ("mark", on_mark, off_mark)):
            steps = [f"0%{{{on if a == 0 else off}}}", f"{a:.2f}%{{{on}}}"]
            if b < 100:
                steps.append(f"{b:.2f}%{{{off}}}")
            steps.append(f"100%{{{on if b >= 100 else off}}}")
            rules.append(f"@keyframes {name}-{i}{{{''.join(steps)}}}")
        rules.append(f".live .takes li:nth-child({i}){{animation:take-{i} {c.ms}ms step-end "
                     "infinite}")
        rules.append(f".live .takes li:nth-child({i})::before{{animation:mark-{i} {c.ms}ms "
                     "step-end infinite}")
    return "\n".join(rules)

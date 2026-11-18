"""Panes (a call, a reply, a shell line) and the one shape of an example: ask, call, reply."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass

from scry_site.sources import Invalid, paragraphs

_JSON = re.compile(r'"(?:[^"\\]|\\.)*"(?:(?=(?P<key>\s*:)))?|-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b'
                   r"|\b(?:true|false|null)\b")
_CALL = re.compile(r"\A(\w+)\(")
_FLAG = re.compile(r"(?<![\w-])(--?[A-Za-z][\w-]*)")


def _spans(text: str, pattern: re.Pattern[str], cls: Callable[[re.Match[str]], str]) -> str:
    """`text` escaped, each match of `pattern` in a span of the class `cls` names."""
    out, at = [], 0
    for m in pattern.finditer(text):
        out += [html.escape(text[at:m.start()])]
        name = cls(m)
        piece = html.escape(m[0])
        out += [f'<span class="{name}">{piece}</span>' if name else piece]
        at = m.end()
    return "".join(out) + html.escape(text[at:])


def _json_class(m: re.Match[str]) -> str:
    if m["key"]:
        return "k"
    if m[0] == '"ok"':
        return "ok"
    if m[0] == '"INVALID"':
        return "bad"
    return "" if m[0].startswith('"') else "n"


def json_code(code: str) -> str:
    return _spans(code, _JSON, _json_class)


def call_code(code: str) -> str:
    m = _CALL.match(code)
    if not m:
        return html.escape(code)
    return f'<span class="c">{m[1]}</span>' + html.escape(code[m.end(1):])


def shell_code(code: str) -> str:
    """Each command a line that hangs under itself, after a prompt the copy leaves out; a
    `--flag` never breaks between its hyphens."""
    lines = []
    for line in code.split("\n"):
        if line.lstrip().startswith("#"):
            lines.append(f'<span class="l d">{html.escape(line)}</span>')
            continue
        body = _spans(line, _FLAG, lambda m: "nb")
        lines.append(f'<span class="l"><span class="p">$ </span>{body}</span>')
    return "".join(lines)


def pane(language: str, code: str, *, label: str = "", copy: bool | None = None) -> str:
    """A fenced block as a pane: a title strip, then the code, wrapped at every width."""
    code = code.rstrip("\n")
    if language in ("sh", "shell", "console"):
        body, name, copy = shell_code(code), label or "Shell", copy is not False
    elif language == "json":
        body, name = json_code(code), label or "JSON"
    elif language == "text" and _CALL.match(code):
        body, name = call_code(code), label or "Call"
    else:
        body = html.escape(code)
        name = label or ("Text" if language in ("", "text") else html.escape(language.upper()))
    attr = " data-copy" if copy else ""
    return (f'<div class="pane"><div class="pane-h">{name}</div><pre{attr}><code>{body}</code>'
            "</pre></div>")


@dataclass(frozen=True)
class Call:
    then: str
    call: str
    fields: str
    reply: str


@dataclass(frozen=True)
class Example:
    where: str
    ask: str
    calls: tuple[Call, ...]
    reads: str
    whole: str


def _fenced(block: str, language: str, where: str) -> str:
    m = re.fullmatch(rf"```{language}\n(.*?)\n?```", block, re.S)
    if not m:
        raise Invalid(f"{where}: a ```{language} block was expected, found {block[:60]!r}")
    return m[1]


def parse(md: str, where: str, *, located: bool) -> Example:
    """An example as the reference and the demo guides write it: (a sentence saying where it can
    be tried, when `located`), `Ask:` and its quote, then one or two `Call:` and `Reply, N of M
    fields:` pairs, the second introduced by one line, then the sentence that reads the reply
    and the whole reply folded."""
    blocks = _whole_details(paragraphs(md))
    shape = "where, " if located else ""
    fail = Invalid(f"{where}: the example is not {shape}'Ask:', a quote, one or two 'Call:' and "
                   "'Reply...' pairs, a reading sentence and a '<details>'")
    at = 0
    place = ""
    if located:
        if not blocks:
            raise fail
        place, at = blocks[0], 1
    if blocks[at:at + 1] != ["Ask:"] or len(blocks) < at + 2 or not blocks[at + 1].startswith(">"):
        raise fail
    ask = " ".join(line.removeprefix(">").strip() for line in blocks[at + 1].split("\n"))
    at += 2
    calls = []
    then = ""
    while at + 3 < len(blocks) and blocks[at] == "Call:":
        fields = re.fullmatch(r"Reply(?:, (.+))?:", blocks[at + 2])
        if not fields:
            raise fail
        calls.append(Call(then, _fenced(blocks[at + 1], "text", where), fields[1] or "",
                          _fenced(blocks[at + 3], "json", where)))
        at += 4
        then = ""
        if at + 1 < len(blocks) and blocks[at + 1] == "Call:":
            then, at = blocks[at], at + 1
    rest = blocks[at:]
    if not 1 <= len(calls) <= 2 or len(rest) != 2 or not rest[1].startswith("<details>"):
        raise fail
    return Example(place, ask, tuple(calls), rest[0], rest[1])


def _whole_details(blocks: list[str]) -> list[str]:
    """`blocks` with a `<details>` and everything to its `</details>` as one block."""
    out: list[str] = []
    open_ = False
    for b in blocks:
        if open_:
            out[-1] += "\n\n" + b
        else:
            out.append(b)
        if b.startswith("<details>"):
            open_ = True
        if open_ and b.rstrip().endswith("</details>"):
            open_ = False
    return out


def ask_html(inline_html: str) -> str:
    return f'<div class="ask" data-copy><span class="tag">Ask</span><p>{inline_html}</p></div>'


def render(ex: Example, *, caption: str, inline: Callable[[str], str],
           block: Callable[[str], str]) -> str:
    """The example as a figure: `caption` heads it, `inline` and `block` render markdown."""
    parts = [ask_html(inline(ex.ask))]
    for c in ex.calls:
        if c.then:
            parts.append(f'<p class="then">{inline(c.then)}</p>')
        small = f" <small>{html.escape(c.fields)}</small>" if c.fields else ""
        parts.append(
            '<div class="pair">'
            f'<div class="pane"><div class="pane-h">Call</div><pre><code>{call_code(c.call)}'
            "</code></pre></div>"
            f'<div class="pane"><div class="pane-h">Reply{small}</div><pre><code>'
            f"{json_code(c.reply)}</code></pre></div></div>")
    parts.append(f'<p class="reads">{inline(ex.reads)}</p>')
    parts.append(block(ex.whole))
    return (f'<figure class="try"><figcaption>{caption}</figcaption>'
            f'<div class="steps">{"".join(parts)}</div></figure>')

"""One headless Chrome, driven over its DevTools port with the standard library alone: a page
loaded at a width, then a script's answer. No window opens, and the profile is thrown away."""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from types import TracebackType
from typing import Any

MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def binary() -> str | None:
    """`SCRY_SITE_CHROME`, else a Chrome or Chromium on the `PATH`, else the Mac's."""
    named = os.environ.get("SCRY_SITE_CHROME")
    if named:
        return named
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if found := shutil.which(name):
            return found
    return MAC if Path(MAC).is_file() else None


class Broken(Exception):
    """Chrome or its socket could not be used: nothing was measured."""


class _Socket:
    def __init__(self, url: str) -> None:
        host, rest = url[len("ws://"):].split("/", 1)
        name, port = host.split(":")
        self.s = socket.create_connection((name, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{rest} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                        "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            byte = self.s.recv(1)
            if not byte:
                raise Broken("Chrome closed the socket during the handshake")
            head += byte
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise Broken(f"no websocket upgrade: {head[:80]!r}")
        self.n = 0

    def _read(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            chunk = self.s.recv(n - len(out))
            if not chunk:
                raise Broken("Chrome closed the socket")
            out += chunk
        return out

    def _send(self, text: str) -> None:
        data, mask = text.encode(), os.urandom(4)
        head = bytes([0x81])
        if len(data) < 126:
            head += bytes([0x80 | len(data)])
        elif len(data) < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", len(data))
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", len(data))
        self.s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _recv(self) -> str:
        whole = b""
        while True:
            a, b = self._read(2)
            n = b & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)
            if a & 0x0F == 8:
                raise Broken("Chrome closed the socket")
            if a & 0x0F == 9:
                continue
            whole += data
            if a & 0x80:
                return whole.decode()

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        self.n += 1
        self._send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self._recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise Broken(f"{method}: {msg['error']}")
                result: dict[str, Any] = msg["result"]
                return result


class Chrome:
    def __init__(self, path: str) -> None:
        self.profile = tempfile.mkdtemp(prefix="scry-site-chrome-")
        port_file = Path(self.profile) / "DevToolsActivePort"
        self.log = Path(self.profile) / "stderr.log"
        self.err = self.log.open("wb")
        self.process = subprocess.Popen(
            [path, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
             "--no-default-browser-check", f"--user-data-dir={self.profile}",
             "--remote-debugging-port=0", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=self.err)
        try:
            for _ in range(200):
                if port_file.exists() and port_file.read_text().strip():
                    break
                time.sleep(0.05)
            else:
                said = self.log.read_text(errors="replace").strip()[-600:]
                raise Broken(f"Chrome wrote no DevToolsActivePort; it said: {said or 'nothing'}")
            port = port_file.read_text().split("\n")[0]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=30) as r:
                pages = json.load(r)
            page = next((p for p in pages if p["type"] == "page"), None)
            if not page:
                raise Broken("Chrome holds no page")
            self.ws = _Socket(page["webSocketDebuggerUrl"])
            self.ws.call("Page.enable")
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Chrome:
        return self

    def __exit__(self, kind: type[BaseException] | None, value: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.err.close()
        shutil.rmtree(self.profile, ignore_errors=True)

    def load(self, url: str, width: int, height: int) -> None:
        self.ws.call("Emulation.setDeviceMetricsOverride", width=width, height=height,
                     deviceScaleFactor=1, mobile=False)
        self.ws.call("Page.navigate", url=url)
        for _ in range(400):
            if self.answer("document.readyState==='complete' && "
                           "document.fonts.status==='loaded'"):
                return
            time.sleep(0.025)
        raise Broken(f"the page never finished loading: {url}")

    def answer(self, js: str) -> Any:
        r = self.ws.call("Runtime.evaluate", expression=js, returnByValue=True)
        if "exceptionDetails" in r:
            raise Broken(f"the script failed: {r['exceptionDetails']}")
        return r["result"].get("value")

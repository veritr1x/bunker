"""Pod Programs on a computer: the Android tools runtime, beside bunker-server.

    python desktop_runtime.py --data <save folder> --assets <game files folder>
        --tools <folder for Pod Programs' own files> --control <bunker-server's control URL>
        [--port N] [--original-master <unpatched master data>]

The control token is read from BUNKER_CONTROL_TOKEN. Run Python in UTF-8 mode
(PYTHONUTF8=1): the tools write text files without naming an encoding. Saves are edited by the
server's own code, through its control endpoint (cmd/bunker-server/control.go):
the server stops around a change and starts again after it, sending the game
back to its title screen when the change needs it.

Prints {"url": ..., "token": ...} on one line once the pages are served, then
runs until standard input closes. The pages want the cookie lunar_tools=<token>.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import android_runtime

_control = ""
_token = ""
# One request to the server at a time: an edit never overlaps a pause or resume.
_lock = threading.Lock()


def _call(path, body=None, method="POST"):
    """One control request. The answer as text, or raises OSError."""
    request = urllib.request.Request(_control + path, data=body if body is not None else (b"" if method == "POST" else None),
                                     method=method, headers={"X-Bunker-Token": _token})
    with _lock, urllib.request.urlopen(request, timeout=600) as response:
        return response.read().decode()


def _result(path, body=None):
    """A control request that answers {"ok", "error"}: "" or the error."""
    try:
        answer = json.loads(_call(path, body))
    except (OSError, ValueError) as error:
        return f"The server did not answer: {error}"
    return "" if answer.get("ok") else str(answer.get("error") or "The server refused.")


def _edit(data_root, asset_root, request):
    # The server uses its own save and game files: the two roots are not sent.
    try:
        return _call("/edit", request.encode())
    except OSError as error:
        return json.dumps({"ok": False, "error": f"The server did not answer: {error}"})


def _live():
    try:
        return json.loads(_call("/status", method="GET")).get("state") == "running"
    except (OSError, ValueError):
        return False


def _texture(bundle, target, size):
    return _result("/texture", json.dumps({"bundle": str(bundle), "target": str(target), "size": int(size)}).encode())


def start(data_root, asset_root, tools_root, original_master="", port=0):
    """Prepare the editors and serve them on loopback. Returns the url and token."""
    patcher = Path(tools_root) / "patcher"
    patcher.mkdir(parents=True, exist_ok=True)
    origin = patcher / "origin.bin.e"
    if not origin.exists() and original_master and Path(original_master).is_file():
        pending = patcher / "origin.pending"
        shutil.copyfile(original_master, pending)
        os.replace(pending, origin)
    config = android_runtime.configure(data_root, asset_root, tools_root, _edit, lambda message: print(message, file=sys.stderr, flush=True))
    config.SHIM_LUNAR_TEAR_REF = "bunker-server"
    android_runtime.TEXTURE = _texture
    # A computer's window can also fill its screen without a border (the player's --fullscreen).
    import android_display
    android_display.WINDOW_MODE = android_display.WINDOW_MODE[:1] + android_display.WINDOW_MODE_DESKTOP
    # The data tools print what they wrote; standard output is kept for the one line main() prints.
    with contextlib.redirect_stdout(sys.stderr):
        android_runtime.prepare_data()
    android_runtime.game_live = _live
    # A change the game reads only as it starts cannot be made while the game is open here.
    android_runtime.close_game = lambda: "Close the game, make this change from the Bunker, then start the game again."
    android_runtime.pause_game = lambda: _result("/pause")
    android_runtime.resume_game = lambda title=True: _result("/resume?title=" + ("1" if title else "0"))
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", int(port)))
    url = "http://127.0.0.1:" + str(sock.getsockname()[1])
    token = secrets.token_urlsafe(32)
    app = android_runtime.create_app(token, url)
    app.state.desktop_pods = True
    server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False, loop="asyncio", http="h11", lifespan="off"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), name="lunar-tools", daemon=True)
    thread.start()
    for _ in range(500):
        if server.started:
            return {"url": url, "token": token}
        if not thread.is_alive():
            break
        time.sleep(.02)
    sock.close()
    raise RuntimeError("Pod Programs did not start.")


def main():
    global _control, _token
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--tools", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--original-master", default="")
    args = parser.parse_args()
    # Progress messages hold text a Windows console code page cannot encode.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    _control = args.control.rstrip("/")
    _token = os.environ.get("BUNKER_CONTROL_TOKEN", "")
    if not _token:
        parser.error("BUNKER_CONTROL_TOKEN is not set")
    print(json.dumps(start(args.data, args.assets, args.tools, args.original_master, args.port)), flush=True)
    sys.stdin.read()


if __name__ == "__main__":
    main()

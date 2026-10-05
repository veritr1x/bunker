"""Images for the Archive: textures decoded from asset bundles once, then kept as PNG files."""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

SIZES = {"thumb": 360, "view": 1400, "full": 0}
# Bump when decoding changes: older PNGs are deleted and browsers fetch the new ones.
VERSION = 2


class Textures:
    """decode(bundle, target, max_side) -> "" or an error, supplied by the host (the native library on a phone)."""

    def __init__(self, assetbundle: Path, cache: Path, decode):
        self.assetbundle, self.cache, self.decode = Path(assetbundle), Path(cache) / f"v{VERSION}", decode
        if Path(cache).is_dir():
            for old in Path(cache).glob("v*"):
                if old != self.cache:
                    shutil.rmtree(old, ignore_errors=True)
        self.locks: dict[str, threading.Lock] = {}
        self.guard = threading.Lock()

    def png(self, path: str, size: str) -> Path:
        """The PNG for a bundle path under assetbundle/, decoding it on first use."""
        if size not in SIZES or not self.decode:
            raise FileNotFoundError(path)
        bundle = (self.assetbundle / path).resolve()
        if self.assetbundle.resolve() not in bundle.parents or bundle.suffix != ".assetbundle" or not bundle.is_file():
            raise FileNotFoundError(path)
        target = self.cache / size / Path(path).with_suffix(".png")
        if target.is_file():
            return target
        with self.guard:
            lock = self.locks.setdefault(str(target), threading.Lock())
        with lock:  # one decode per image, however many pages ask at once
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                error = str(self.decode(str(bundle), str(target), SIZES[size]) or "")
                if error:
                    raise ValueError(error)
        return target

    def size(self) -> int:
        return sum(f.stat().st_size for f in self.cache.rglob("*.png")) if self.cache.is_dir() else 0

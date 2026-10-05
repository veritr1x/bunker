"""Images and sounds for the Archive: converted from asset bundles once, then kept as files."""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

SIZES = {"thumb": 360, "view": 1400, "full": 0}
# Bump when conversion changes: older files are deleted and browsers fetch the new ones.
VERSION = 2


class Converted:
    """Files made from bundles under assetbundle/ by a host-supplied convert function (the native library on a phone)."""

    suffix = ""

    def __init__(self, assetbundle: Path, cache: Path, convert):
        self.assetbundle, self.cache, self.convert = Path(assetbundle), Path(cache) / f"v{VERSION}", convert
        if Path(cache).is_dir():
            for old in Path(cache).glob("v*"):
                if old != self.cache:
                    shutil.rmtree(old, ignore_errors=True)
        self.locks: dict[str, threading.Lock] = {}
        self.guard = threading.Lock()

    def file(self, path: str, *variant) -> Path:
        """The converted file for a bundle path, made on first use; a variant names a subfolder."""
        bundle = (self.assetbundle / path).resolve()
        if not self.convert or self.assetbundle.resolve() not in bundle.parents or bundle.suffix != ".assetbundle" or not bundle.is_file():
            raise FileNotFoundError(path)
        target = self.cache.joinpath(*variant) / Path(path).with_suffix(self.suffix)
        if target.is_file():
            return target
        with self.guard:
            lock = self.locks.setdefault(str(target), threading.Lock())
        with lock:  # one conversion per file, however many pages ask at once
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                error = str(self.convert(str(bundle), str(target), *self.arguments(*variant)) or "")
                if error:
                    raise ValueError(error)
        return target

    def arguments(self, *variant):
        return ()

    def size(self) -> int:
        return sum(f.stat().st_size for f in self.cache.rglob("*" + self.suffix)) if self.cache.is_dir() else 0


class Textures(Converted):
    """convert(bundle, target, max_side) -> "" or an error, writing a PNG."""

    suffix = ".png"

    def png(self, path: str, size: str) -> Path:
        if size not in SIZES:
            raise FileNotFoundError(path)
        return self.file(path, size)

    def arguments(self, size):
        return (SIZES[size],)


class Sounds(Converted):
    """convert(bundle, target) -> "" or an error, writing Ogg Vorbis."""

    suffix = ".ogg"

    def ogg(self, path: str) -> Path:
        return self.file(path)

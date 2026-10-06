"""Images, sounds, models and motions for the Archive: converted from asset bundles once, then kept as files."""
from __future__ import annotations

import re
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


class Models:
    """convert(actor_folder, target_glb) -> "" or an error: a costume or weapon as glTF, made on first use."""

    def __init__(self, assetbundle: Path, cache: Path, convert):
        self.actors = Path(assetbundle) / "3d" / "actor"
        self.files = Converted(assetbundle, cache, convert)  # versioned folder and per-file locks

    def glb(self, asset: str) -> Path:
        if not self.files.convert or not self.has(asset):
            raise FileNotFoundError(asset)
        target = self.files.cache / f"{asset}.glb"
        if target.is_file():
            return target
        with self.files.guard:
            lock = self.files.locks.setdefault(str(target), threading.Lock())
        with lock:
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                error = str(self.files.convert(str(self.actors / asset), str(target)) or "")
                if error:
                    raise ValueError(error)
        return target

    def has(self, asset: str) -> bool:
        """A costume (ch008001) or weapon (wp001002) with a skeleton, or a weapon variant's own prefab."""
        if not re.fullmatch(r"(ch|wp)\d{6}", asset):
            return False
        mesh = self.actors / asset / "mesh"
        return (mesh / f"sk_{asset}.assetbundle").is_file() or (asset.startswith("wp") and (mesh / f"{asset}.assetbundle").is_file())


class Motions:
    """convert(clip_bundle, actor_folder, target_json) -> "" or an error: a motion as three.js clip JSON for one costume."""

    def __init__(self, assetbundle: Path, cache: Path, convert):
        self.root = Path(assetbundle)
        self.files = Converted(assetbundle, cache, convert)

    def json(self, asset: str, clip: str) -> Path:
        family = asset[:5]
        if not self.files.convert or not re.fullmatch(r"ch\d{6}", asset) or not re.fullmatch(rf"anim_(tw|bt)_{family}_[a-z0-9_]+", clip):
            raise FileNotFoundError(clip)
        bundle = self.root / "3d" / "motion" / family / "general" / f"{clip}.assetbundle"
        actor = self.root / "3d" / "actor" / asset
        if not bundle.is_file() or not (actor / "mesh" / f"sk_{asset}.assetbundle").is_file():
            raise FileNotFoundError(clip)
        target = self.files.cache / asset / f"{clip}.json"
        if target.is_file():
            return target
        with self.files.guard:
            lock = self.files.locks.setdefault(str(target), threading.Lock())
        with lock:
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                error = str(self.files.convert(str(bundle), str(actor), str(target)) or "")
                if error:
                    raise ValueError(error)
        return target

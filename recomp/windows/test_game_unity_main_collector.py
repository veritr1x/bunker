#!/usr/bin/env python3
"""Windows component qualification using unchanged retained original GC code.

No game launch, original heap scanner, or reclamation is performed. Initial GC
registry data and the interrupted helper-shaped caller are explicit test inputs.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXTRACTION_SHA = "ace8c5cd9da8460c110d6a8da6dd91e4a31a36cfc4ed598cd256ab9bcd222f3a"
OBJECT_SHA = "c353c4bb96e6fba4081c522215771a563eb1f1680c23251b902f7ab5ecc4b8e0"
DEFAULT_SHA = "3d158a1ecd39e512d3c125e389b3db65cbbd394ca0c5ce70d24642f7411cb3cc"
OWNED = ["windows/game_unity_main_collector.h", "windows/game_unity_main_collector_test.cpp", "windows/test_game_unity_main_collector.py"]
COMPILE = ["windows/game_unity_main_collector_test.cpp", "windows/pthread_host.cpp", "windows/signal_host.cpp", "windows/signal_delivery.cpp", "windows/signal_nanosleep.cpp", "windows/signal_sleep.cpp", "windows/semaphore_host.cpp", "windows/filesystem.cpp", "windows/growdown_memory.cpp", "whole/format.cpp", "whole/runtime.cpp", "whole/signal_frame.cpp", "whole/cooperative_poll.cpp"]

def sha(path):
    return hashlib.file_digest(Path(path).open("rb"), "sha256").hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, default=Path("C:/mingw64/bin/g++.exe"))
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("This qualification requires the actual Windows Pthreads provider")
    repo = Path(__file__).resolve().parents[1]
    work = (repo / "work").resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands = []
    evidence = {}
    def pin(path, expected=None):
        path = Path(path).resolve()
        digest = sha(path)
        if expected is not None and digest != expected:
            raise RuntimeError(f"input changed: {path}")
        evidence[str(path)] = digest
        return digest
    def run(name, command):
        commands.append({"name": name, "command": list(map(str, command)), "cwd": str(out)})
        write(out / "commands.json", commands)
        result = subprocess.run(list(map(str, command)), cwd=out, capture_output=True, timeout=180 if name == "compile" else 60)
        (out / (name + ".stdout.log")).write_bytes(result.stdout)
        (out / (name + ".stderr.log")).write_bytes(result.stderr)
        if result.returncode:
            raise RuntimeError(f"{name} failed: {result.returncode}; see preserved logs")
        return result
    try:
        extraction = work / "original-gc-protocol-extract1/extraction.json"
        pin(extraction, EXTRACTION_SHA)
        original = work / "original-gc-protocol-extract1/windows.o"
        pin(original, OBJECT_SHA)
        default = work / "default-nanosleep-external-regression1/acceptance.json"
        pin(default, DEFAULT_SHA)
        default_data = json.loads(default.read_text())
        if default_data.get("passed") is not True:
            raise RuntimeError("default NanoSleep regression is not passing")
        for name, digest in default_data["owned_sources"].items():
            pin(repo / name, digest)
        source_hashes = {}
        def freeze(path):
            path = path.resolve()
            name = path.relative_to(repo).as_posix()
            if name in source_hashes:
                return
            source_hashes[name] = pin(path)
            copied = out / "source" / name
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, copied)
            for include in re.findall(r'^\s*#include\s+"([^"]+)"', path.read_text(), re.M):
                child = path.parent / include
                if child.is_file():
                    freeze(child)
        for name in COMPILE + OWNED:
            freeze(repo / name)
        write(out / "source-hashes.json", source_hashes)
        shutil.copyfile(original, out / "original-handlers.o")
        include = work / "remill-src/include"
        for header in (include / "remill").rglob("*.h"):
            pin(header)
        pin(args.compiler)
        command = [args.compiler, "-std=c++17", "-O2", "-DADDRESS_SIZE_BITS=64", "-isystem", include]
        command += [out / "source" / name for name in COMPILE]
        command += [out / "original-handlers.o", "-static", "-pthread", "-latomic", "-ladvapi32", "-lbcrypt", "-o", out / "original-main-gc.exe"]
        run("compile", command)
        cases = {}
        for mode in ("disabled", "enabled"):
            result = run("run-" + mode, [out / "original-main-gc.exe", mode])
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
            match = re.search(r"EXTERNAL-UNITYMAIN-ORIGINAL-GC-SUCCESS cycles=2 posts=4 stops=2 restarts=(\d+) checks=(\d+)", stdout)
            if not match or int(match[1]) < 2:
                raise RuntimeError("missing exact genuine two-cycle success witness: " + mode)
            if stderr.count("physical main roots") != 4 or stderr.count("genuine stop returned") != 2:
                raise RuntimeError("missing normal physical-root or original-stop witnesses: " + mode)
            alternate = re.search(r"EXTERNAL-UNITYMAIN-ALTSTACK mode=(\S+) size=(\d+) acquires=(\d+) lease-guards=(\d+) canaries=unchanged configuration=preserved normal-root-frames=4", stdout)
            if not alternate:
                raise RuntimeError("missing actual alternate-stack preservation witness: " + mode)
            label, size, acquires, guards = alternate[1], int(alternate[2]), int(alternate[3]), int(alternate[4])
            if mode == "enabled":
                assert label == "enabled-inactive" and size == 262144 and acquires >= 2 + int(match[1]) and guards == 8
            else:
                assert label == "disabled" and size == acquires == guards == 0
            cases[mode] = {"cycles": 2, "actual_posts": 4, "stop_deliveries": 2, "nested_restarts": int(match[1]), "checks": int(match[2]), "alternate_size": size, "actual_mapping_acquires": acquires, "lease_mutation_guards": guards, "configuration_preserved": True, "alternate_canaries_unchanged": True, "normal_physical_root_frames": 4, "stdout": stdout, "stderr": stderr}
        for name, digest in source_hashes.items():
            pin(repo / name, digest)
        for path, digest in list(evidence.items()):
            pin(path, digest)
        for path in out.rglob("*"):
            if path.is_file():
                pin(path)
        receipt = {"passed": True, "scope": "Two fresh Windows processes: disabled alternate control and actual FileSystem-owned262144byte enabled inactive alternate; genuine retained original stop/resume coordinators and handlers perform two cycles each with normal-stack31GPR32Q roots and unchanged exact no-SA_ONSTACK dispositions. Enabled alternate tuple/epoch/generation and all canaries preserved; real core mapping leases reject unmap/protection while original normal-stack frames run", "limitations": ["TEST initial registry/globals and helper-shaped interrupted caller; no game or original scanner execution, heap scan, reclamation or first-frame claim", "Same-epoch duplicate zero-post delivery is deferred and not qualified", "Enabled alternate is registered and inactive; actual SA_ONSTACK switching is not admitted by this main collector profile"], "owned_sources": {name: source_hashes[name] for name in OWNED}, "source_hashes": source_hashes, "cases": cases, "case_count": 2, "cycles": 4, "actual_posts": 8, "stop_deliveries": 4, "nested_restarts": sum(c["nested_restarts"] for c in cases.values()), "checks": sum(c["checks"] for c in cases.values()), "default_nanosleep_receipt": {"path": str(default), "sha256": DEFAULT_SHA}, "original_extraction": {"path": str(extraction), "sha256": EXTRACTION_SHA, "windows_object_sha256": OBJECT_SHA}, "evidence": evidence}
        write(out / "acceptance.json", receipt)
        print(f"PASS {out / 'acceptance.json'} sha256={sha(out / 'acceptance.json')}")
    except BaseException as exc:
        write(out / "failure.json", {"passed": False, "error": str(exc), "commands": commands, "evidence": evidence})
        raise

if __name__ == "__main__":
    main()

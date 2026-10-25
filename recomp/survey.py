"""Survey the game's ARM64 libraries for static recompilation to x86_64.

Extracts lib/arm64-v8a/*.so from the game APK and counts, per library, what a
recompiler has to handle: code size, imported functions (each needs a bridge to
the x86_64 side), indirect branches, SIMD, exclusive atomics, system
instructions and unwind tables.

    python3 recomp/survey.py --apk inputs/game-3.7.1.apk [--lib libFastAES.so]
"""
import argparse
import json
import os
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
NDK = Path(os.environ.get("ANDROID_NDK_HOME", Path.home() / "Library/Android/sdk/ndk/27.2.12479018"))
BIN = next((NDK / "toolchains/llvm/prebuilt").glob("*/bin"), None)

# Mnemonic classes, matched on the llvm-objdump mnemonic.
INDIRECT = {"br", "blr", "braa", "brab", "blraa", "blrab", "braaz", "brabz", "blraaz", "blrabz"}
EXCLUSIVE = re.compile(r"^(ld|st)(a)?xr|^(ld|st)(a)?xp|^ldaxr|^stlxr")
LSE_ATOMIC = re.compile(r"^(ldadd|ldclr|ldeor|ldset|ldsmax|ldsmin|ldumax|ldumin|swp|cas)")
SYSTEM = {"mrs", "msr", "svc", "dmb", "dsb", "isb", "hint", "brk", "hlt"}
# A vector/FP register operand (v0.4s, q1, d2 with lanes) marks SIMD use.
VECTOR_OPERAND = re.compile(r"\bv\d+\.|\bq\d+\b")


def tool(name):
    if BIN is None or not (BIN / name).exists():
        raise SystemExit(f"Missing {name}: set ANDROID_NDK_HOME to an NDK")
    return str(BIN / name)


def extract(apk):
    out = WORK / "lib"
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk) as z:
        for name in z.namelist():
            if name.startswith("lib/arm64-v8a/") and name.endswith(".so"):
                target = out / Path(name).name
                if not target.exists() or target.stat().st_size != z.getinfo(name).file_size:
                    target.write_bytes(z.read(name))
    return sorted(out.glob("*.so"))


def sections(lib):
    text = subprocess.run([tool("llvm-readelf"), "-SW", str(lib)], capture_output=True, text=True, check=True).stdout
    sizes, code = {}, 0
    for line in text.splitlines():
        m = re.match(r"\s*\[\s*\d+\]\s+(\S+)\s+\S+\s+[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+[0-9a-f]+\s+(\S*)", line)
        if m:
            sizes[m.group(1)] = int(m.group(2), 16)
            # IL2CPP puts the game's code in its own "il2cpp" section, so count every executable one.
            if "X" in m.group(3):
                code += int(m.group(2), 16)
    sizes["code"] = code
    return sizes


def dynamic(lib):
    needed = re.findall(r"\(NEEDED\)\s+Shared library: \[(.+?)\]",
                        subprocess.run([tool("llvm-readelf"), "-d", str(lib)], capture_output=True, text=True, check=True).stdout)
    nm = lambda flag: subprocess.run([tool("llvm-nm"), "-D", flag, str(lib)], capture_output=True, text=True, check=True).stdout.split("\n")
    imports = sorted({line.split()[-1] for line in nm("--undefined-only") if line.strip()})
    exports = sorted({line.split()[-1] for line in nm("--defined-only") if line.strip() and line.split()[1] in "TtWw"})
    return needed, imports, exports


def instructions(lib):
    """Counts mnemonics over the code sections, streaming objdump's output."""
    counts, total, vector = Counter(), 0, 0
    proc = subprocess.Popen([tool("llvm-objdump"), "-d", "--no-show-raw-insn", "--no-leading-addr", str(lib)],
                            stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in proc.stdout:
        if not line.startswith(("\t", " ")):
            continue
        parts = line.split(None, 1)
        if not parts:
            continue
        mnemonic = parts[0].lower()
        if mnemonic.startswith("<") or mnemonic.endswith(":"):
            continue
        total += 1
        operands = parts[1] if len(parts) > 1 else ""
        if mnemonic in INDIRECT:
            counts["indirect_branch"] += 1
        elif mnemonic == "ret":
            counts["ret"] += 1
        elif mnemonic in ("bl", "b"):
            counts["direct_" + mnemonic] += 1
        if EXCLUSIVE.match(mnemonic):
            counts["exclusive_atomic"] += 1
        if LSE_ATOMIC.match(mnemonic):
            counts["lse_atomic"] += 1
        if mnemonic in SYSTEM:
            counts["system:" + mnemonic] += 1
        if VECTOR_OPERAND.search(operands):
            vector += 1
        if mnemonic == "udf" or mnemonic == "<unknown>":
            counts["undecodable"] += 1
    proc.wait()
    counts["total"], counts["simd"] = total, vector
    return dict(counts)


def survey(lib):
    size = sections(lib)
    needed, imports, exports = dynamic(lib)
    return {
        "library": lib.name,
        "file_mb": round(lib.stat().st_size / 1048576, 1),
        "code_mb": round(size["code"] / 1048576, 2),
        "relocations": size.get(".rela.dyn", 0) // 24,
        "eh_frame_kb": round((size.get(".eh_frame", 0) + size.get(".eh_frame_hdr", 0)) / 1024),
        "gcc_except_table_kb": round(size.get(".gcc_except_table", 0) / 1024),
        "init_array_entries": size.get(".init_array", 0) // 8,
        "needed": needed,
        "imports": len(imports),
        "exports": len(exports),
        "instructions": instructions(lib),
        "import_names": imports,
        "export_names": exports,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apk", type=Path, required=True, help="Original ARM64 game 3.7.1 APK")
    parser.add_argument("--lib", action="append", help="Only these libraries (repeatable)")
    args = parser.parse_args()
    libs = [l for l in extract(args.apk) if not args.lib or l.name in args.lib]
    results = []
    for lib in libs:
        print(f"Surveying {lib.name}…", flush=True)
        results.append(survey(lib))
    (WORK / "survey.json").write_text(json.dumps(results, indent=1))
    header = (f"{'library':30} {'code MB':>8} {'insns':>11} {'indirect':>9} {'simd':>9} {'atomics':>8} "
              f"{'imports':>8} {'relocs':>10} {'eh KB':>7}")
    print("\n" + header + "\n" + "-" * len(header))
    for r in results:
        i = r["instructions"]
        print(f"{r['library']:30} {r['code_mb']:8.2f} {i['total']:11,} {i.get('indirect_branch', 0):9,} {i['simd']:9,} "
              f"{i.get('exclusive_atomic', 0) + i.get('lse_atomic', 0):8,} {r['imports']:8,} {r['relocations']:10,} "
              f"{r['eh_frame_kb']:7,}")
    print(f"\nFull results: {WORK / 'survey.json'}")


if __name__ == "__main__":
    main()

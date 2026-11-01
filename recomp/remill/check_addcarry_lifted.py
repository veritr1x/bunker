"""Lift ADC/ADCS samples, compile them for x86_64, and check against x86 hardware.

Run from x86_64 Linux/WSL after building Remill. Requires the fork's add/carry
changes. --lift and --cxx allow using a native build instead of the dev image.
"""
import argparse
import os
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "work/remill-src"
WORK = HERE.parent / "work/addcarry-lifted"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lift", type=Path)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
    args = parser.parse_args()
    if platform.machine() != "x86_64":
        parser.error("This check requires an x86_64 Linux host.")
    lift = args.lift
    if lift is None:
        candidates = sorted((SRC / "build-dev/bin/lift").glob("remill-lift-*"))
        if not candidates:
            parser.error("Build Remill first, or specify --lift.")
        lift = candidates[0]
    lift = lift.resolve()
    WORK.mkdir(parents=True, exist_ok=True)
    variants = [("normal", 9, 0, 1), ("lhs_overlap", 0, 0, 1),
                ("rhs_overlap", 1, 0, 1), ("zero_lhs", 9, 31, 1),
                ("zero_rhs", 9, 0, 31), ("discard", 31, 0, 1)]
    declarations, entries, objects = [], [], []
    for bits in (32, 64):
        for flags in (False, True):
            for name, dst, lhs, rhs in variants:
                symbol = f"lift_{'adcs' if flags else 'adc'}{bits}_{name}"
                # A64 add/subtract-with-carry encoding: sf, S, Rm, Rn, Rd.
                word = 0x1A000000 | ((bits == 64) << 31) | (flags << 29)
                word |= (rhs << 16) | (lhs << 5) | dst
                code = word.to_bytes(4, "little") + bytes.fromhex("c0035fd6")
                ir = WORK / f"{symbol}.ll"
                subprocess.run([str(lift), "--arch", "aarch64", "--os", "linux",
                                "--bytes", code.hex(), "--address", "268435456",
                                "--ir_out", str(ir)], check=True, capture_output=True)
                text = ir.read_text()
                if "@__remill_error(" in text or "@sub_10000000(" not in text:
                    raise RuntimeError(f"{symbol} did not lift successfully")
                ir.write_text(text.replace("@sub_10000000(", f"@{symbol}("))
                obj = WORK / f"{symbol}.o"
                subprocess.run([args.cxx, "-target", "x86_64-linux-gnu", "-O2",
                                "-Wno-override-module", "-c", str(ir), "-o", str(obj)], check=True)
                objects.append(str(obj))
                declarations.append(f'extern "C" Memory *{symbol}(State &, addr_t, Memory *);')
                entries.append(f'  {{{symbol}, "{symbol}", {bits}, {dst}, {lhs}, {rhs}, {str(flags).lower()}}},')
    (WORK / "lifted-addcarry.h").write_text("\n".join(
        declarations + ["static const LiftedCase kLiftedCases[] = {"] + entries + ["};", ""]))
    binary = WORK / "check-lifted"
    subprocess.run([args.cxx, "-std=c++17", "-O2", "-DADDRESS_SIZE_BITS=64",
                    "-DCHECK_LIFTED_ADDCARRY", "-ffunction-sections", "-fdata-sections",
                    "-Wl,--gc-sections", f"-I{SRC / 'include'}", f"-I{SRC}", f"-I{WORK}",
                    str(HERE / "check_addcarry.cpp"), *objects, "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()

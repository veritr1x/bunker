"""Measures how much of a library's code a Remill build can lift.

Groups the library's instructions into forms (mnemonic plus operand shape:
register classes, vector arrangements, immediates collapsed), takes one sample
of each, and lifts every sample as its own function (`insn; ret`, reached by a
`bl`). A lifted function that ends in __remill_error marks an unsupported form.
Results are weighted by how often each form occurs in the library.

    python3 recomp/coverage.py prepare --lib libFastAES.so      # host: disassemble, write chunks
    docker run --rm -v "$PWD/recomp:/recomp" <remill image> /recomp/coverage_lift.sh libFastAES.so <tag>
    python3 recomp/coverage.py report --lib libFastAES.so --tag <tag>

Control flow (branches, calls, returns) is left out: a sample would leave its
slot. Those forms are counted and listed separately.
"""
import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from survey import WORK, tool

BASE = 0x10000000
CHUNK = 4000  # Forms per lift; keeps the hex argument under Linux's 128 KiB per-argument limit.
CONTROL = re.compile(r"^(b|bl|br|blr|ret|cbz|cbnz|tbz|tbnz|b\..+|bc\..+|braa|brab|blraa|blrab|braaz|brabz|blraaz|blrabz|"
                     r"retaa|retab|eret)$")
SIMD = re.compile(r"\bv\d+\.|\bq\d+\b|\{")
LINE = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2}|[0-9a-f]{8})\s+(\S+)\s*(.*)$")


def form(mnemonic, operands):
    ops = operands.split("//")[0]
    ops = re.sub(r"<[^>]*>", "", ops)
    ops = re.sub(r"#?-?0x[0-9a-f]+|#-?\d+(\.\d+)?(e[+-]?\d+)?", "#I", ops)
    ops = re.sub(r"\b[xw]\d+\b", lambda m: m.group()[0].upper(), ops)
    ops = re.sub(r"\bv\d+\.", "V.", ops)
    ops = re.sub(r"\b([bhsdq])\d+\b", lambda m: m.group(1).upper(), ops)
    ops = re.sub(r"\[\d+\]", "[I]", ops)
    ops = re.sub(r"\b\d+\b", "I", ops)  # Bare numbers left over (shift amounts, sizes).
    return f"{mnemonic} {' '.join(ops.split())}".strip()


def word(raw):
    """objdump prints AArch64 code as one big-endian-looking word, or as four bytes in memory order."""
    if " " in raw:
        return bytes.fromhex(raw.replace(" ", ""))
    return int(raw, 16).to_bytes(4, "little")


def scan(lib):
    forms, control, unknown = {}, Counter(), 0
    proc = subprocess.Popen([tool("llvm-objdump"), "-d", str(lib)], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in proc.stdout:
        m = LINE.match(line)
        if not m:
            continue
        addr, raw, mnemonic, operands = m.groups()
        mnemonic = mnemonic.lower()
        if mnemonic == "<unknown>" or mnemonic.startswith(".") or mnemonic == "udf":
            unknown += 1
            continue
        key = form(mnemonic, operands)
        if CONTROL.match(mnemonic):
            control[key] += 1
            continue
        entry = forms.setdefault(key, {"count": 0, "word": word(raw).hex(), "addr": addr,
                                       "simd": bool(SIMD.search(operands))})
        entry["count"] += 1
    proc.wait()
    return forms, control, unknown


def bl(src, dst):
    offset = (dst - src) // 4
    return (0x94000000 | (offset & 0x3ffffff)).to_bytes(4, "little")


RET = bytes.fromhex("c0035fd6")


def prepare(lib_name):
    lib = WORK / "lib" / lib_name
    out = WORK / "coverage" / lib_name
    out.mkdir(parents=True, exist_ok=True)
    forms, control, unknown = scan(lib)
    names = sorted(forms, key=lambda k: -forms[k]["count"])
    chunks = [names[i:i + CHUNK] for i in range(0, len(names), CHUNK)]
    for old in out.glob("chunk_*"):
        old.unlink()
    index = {}
    for c, chunk in enumerate(chunks):
        # Layout: one `bl` per sample, a `ret`, then 8-byte slots of `sample; ret`.
        slots = BASE + 4 * len(chunk) + 4
        blob = bytearray()
        for i in range(len(chunk)):
            blob += bl(BASE + 4 * i, slots + 8 * i)
        blob += RET
        for i, name in enumerate(chunk):
            blob += bytes.fromhex(forms[name]["word"]) + RET
            index[f"{c}:{slots + 8 * i:x}"] = name
        (out / f"chunk_{c}.hex").write_text(blob.hex())
    (out / "forms.json").write_text(json.dumps({"forms": forms, "control": control, "unknown": unknown,
                                                "index": index}, indent=0))
    total = sum(f["count"] for f in forms.values())
    print(f"{lib_name}: {total:,} instructions in {len(forms):,} forms, {len(chunks)} chunks; "
          f"{sum(control.values()):,} control flow in {len(control)} forms; {unknown:,} undecodable or data")


def failed_slots(ll_text):
    """Addresses of lifted functions that call __remill_error."""
    failed, current = set(), None
    for line in ll_text.splitlines():
        if line.startswith("define"):
            m = re.search(r"@sub_([0-9a-f]+)\(", line)
            current = m.group(1) if m else None
        elif current and "@__remill_error(" in line and "call" in line:
            failed.add(current)
        elif line.startswith("}"):
            current = None
    return failed


def report(lib_name, tag):
    out = WORK / "coverage" / lib_name
    data = json.loads((out / "forms.json").read_text())
    forms, index = data["forms"], data["index"]
    failed, lifted = set(), set()
    for ll in sorted(out.glob(f"chunk_*.{tag}.ll")):
        c = ll.name.split("_")[1].split(".")[0]
        text = ll.read_text()
        lifted |= {f"{c}:{a}" for a in re.findall(r"^define .*@sub_([0-9a-f]+)\(", text, re.M)}
        failed |= {f"{c}:{a}" for a in failed_slots(text)}
    missing = {k for k in index if k not in lifted}  # Never lifted at all: the chunk failed.
    bad = {index[k] for k in failed | missing}
    total = sum(f["count"] for f in forms.values())
    simd_total = sum(f["count"] for f in forms.values() if f["simd"])
    bad_count = sum(forms[n]["count"] for n in bad)
    bad_simd = sum(forms[n]["count"] for n in bad if forms[n]["simd"])
    print(f"{lib_name} [{tag}]: {len(forms) - len(bad):,} of {len(forms):,} forms lift "
          f"({len(missing)} not lifted at all)")
    print(f"  instructions covered: {100 * (1 - bad_count / total):.2f}% of {total:,}")
    if simd_total:
        print(f"  SIMD instructions covered: {100 * (1 - bad_simd / simd_total):.2f}% of {simd_total:,}")
    print("  most common unsupported forms:")
    for name in sorted(bad, key=lambda n: -forms[n]["count"])[:25]:
        f = forms[name]
        print(f"    {f['count']:>9,}  {name}   (e.g. {f['word']} at 0x{f['addr']})")
    summary = {"library": lib_name, "tag": tag, "forms": len(forms), "unsupported_forms": len(bad),
               "instructions": total, "unsupported_instructions": bad_count, "simd": simd_total,
               "unsupported_simd": bad_simd,
               "unsupported": sorted(({"form": n, **forms[n]} for n in bad), key=lambda f: -f["count"])}
    (out / f"report.{tag}.json").write_text(json.dumps(summary, indent=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["prepare", "report"])
    parser.add_argument("--lib", required=True, help="Library name under recomp/work/lib (run survey.py first)")
    parser.add_argument("--tag", default="remill", help="Name for this Remill build's results")
    args = parser.parse_args()
    prepare(args.lib) if args.step == "prepare" else report(args.lib, args.tag)


if __name__ == "__main__":
    main()

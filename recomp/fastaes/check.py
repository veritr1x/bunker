"""Compares the recompiled x86_64 output with the ARM64 reference, and both with OpenSSL.

    python3 recomp/fastaes/check.py   (after run.sh all)
"""
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent / "work" / "fastaes"


def parse(path):
    calls = []
    for line in path.read_text().splitlines():
        op, *fields = line.split()
        calls.append((op, dict(f.split("=", 1) for f in fields)))
    return calls


def openssl_cbc(key, iv, data):
    cipher = f"aes-{len(key) * 8}-cbc"
    return subprocess.run(["openssl", "enc", f"-{cipher}", "-K", key.hex(), "-iv", iv.hex(), "-nopad"],
                          input=data, capture_output=True, check=True).stdout


def expected(enc):
    """What AES-CBC should give: full blocks encrypted, PKCS#7 with padding 2, a partial tail dropped otherwise."""
    key, iv, data = (bytes.fromhex(enc[k]) for k in ("key", "iv", "in"))
    if enc["padding"] == "2":
        pad = 16 - len(data) % 16
        data += bytes([pad]) * pad
    else:
        data = data[:len(data) // 16 * 16]
    return openssl_cbc(key, iv, data)


def main():
    ref, recomp = parse(WORK / "ref.txt"), parse(WORK / "recomp.txt")
    problems = []
    if len(ref) != len(recomp):
        problems.append(f"call count differs: ARM64 {len(ref)}, x86_64 {len(recomp)}")
    for i, ((op, r), (_, x)) in enumerate(zip(ref, recomp)):
        if r != x:
            problems.append(f"call {i} ({op}) differs between ARM64 and x86_64")
        if op == "enc" and bytes.fromhex(r["out"]) != expected(r):
            problems.append(f"call {i} (enc key_len={r['key_len']} len={r['len']}) differs from OpenSSL")
        if op == "dec":
            plain = ref[i - 1][1]["in"]
            want = plain if r["padding"] == "2" else plain[:len(plain) // 32 * 32]
            if r["out"] != want:
                problems.append(f"call {i} (dec) does not give back the plaintext")
    for p in problems:
        print("FAIL", p)
    print(f"{len(ref)} calls compared: {'all match' if not problems else f'{len(problems)} problems'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

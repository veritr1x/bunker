"""Removes generated `return false` decoder stubs from Remill's AArch64 Decode.cpp,
so a real implementation in Arch.cpp can take the symbol.

    python3 recomp/remill/unstub.py FADD_ASIMDSAME_ONLY FMUL_ASIMDSAME_ONLY ...
"""
import re
import sys
from pathlib import Path

DECODE = Path(__file__).resolve().parents[1] / "work/remill-src/lib/Arch/AArch64/Decode.cpp"


def main(names):
    text = DECODE.read_text()
    for name in names:
        stub = re.compile(r"bool TryDecode%s\(const InstData &, Instruction &\) \{\n  return false;\n\}\n" % name)
        text, n = stub.subn("", text)
        print(f"{name}: {'removed stub' if n else 'no stub (already implemented?)'}")
    DECODE.write_text(text)


if __name__ == "__main__":
    main(sys.argv[1:])

"""Reproduce the verified ReflectionHelper interface declarations in one catalog."""
import argparse
import hashlib
import json
from pathlib import Path

PARENT_SHA = "cac2f4fe2cb7cd2d29bcdb891e77a1aec7e9f00d0f2d1cc40d58ee0c41c2e383"
OUTPUT_SHA = "6516d02411aa51376b90f23fff08d2c55ec9797c92c4b369fd9fd97c97f2a29d"


def prepare(parent, output):
    raw = parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("Expected the exact qualified parent Java catalog")
    if output.exists():
        raise ValueError("Output directory must be fresh")
    text = raw.decode("utf-8")
    old_interface = ('  host.DefineClass("com/unity3d/player/ReflectionHelper$b",{\n'
                     '    {"a","(JZ)V",false,false},\n  });\n')
    if text.count(old_interface) != 1:
        raise ValueError("Interface declaration differs")
    new_interface = old_interface.replace("host.DefineClass", "host.DefineInterface").replace("  });\n", "  },false);\n")
    start = text.index('  host.DefineClass("com/unity3d/player/ReflectionHelper$1",{')
    end = text.index('  host.DefineClass("com/unity3d/player/ReflectionHelper$a",{', start)
    old_handler = text[start:end]
    if not old_handler.endswith("  });\n"):
        raise ValueError("Handler declaration differs")
    new_handler = old_handler[:-len("  });\n")] + ('  },"java/lang/Object",false,'
                    '{"java/lang/reflect/InvocationHandler","com/unity3d/player/ReflectionHelper$b"});\n')
    derived = text.replace(old_interface, "", 1).replace(old_handler, new_interface + new_handler, 1).encode("utf-8")
    if hashlib.sha256(derived).hexdigest() != OUTPUT_SHA:
        raise ValueError("Output differs from the independently reviewed catalog")
    output.mkdir(parents=True)
    target = output / "unity_bootstrap_data.h"
    target.write_bytes(derived)
    receipt = {"parent_sha256": PARENT_SHA, "derived_sha256": OUTPUT_SHA,
               "bytes": len(derived), "guest_code_changed": False,
               "requires_fresh_bootstrap": True, "first_frame_claim": False}
    (output / "acceptance.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.parent.resolve(), args.out.resolve())))

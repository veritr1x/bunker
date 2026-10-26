"""Stop the game's text builder from writing past its buffer (iOS UnityFramework).

Applibot.Text.ArtStringBuilder checks for space before writing formatted text:

    if (position + needed > buffer.Length) Array.Resize(ref buffer, buffer.Length * 2)

It doubles only once, so text more than twice the buffer's size runs past its
end into the next object. The summon confirmation does this soon after the game
starts and the next asset unload crashes on the damaged text (the summon crash,
also on Android; see android/app/src/main/cpp/text_buffer.c). Each of the 58
checks now grows to buffer.Length + position + needed: "lsl w1, wLen, #1"
becomes "add w1, wLen, wNeeded".

Offsets are file offsets in the 3.7.1 UnityFramework (its __TEXT starts at file
offset 0, address 0), from the game's IL2CPP metadata. Every word is checked
first; on any unknown instruction nothing is changed.
"""
from pathlib import Path
import struct

SITES = (
    (0x1A6CE80, 0x531F7941, 0x0B0B0141),  # Append
    (0x1A6D110, 0x531F7941, 0x0B0B0141),  # Append
    (0x1A6D9C8, 0x531F7901, 0x0B090101),  # CheckCapacity
    (0x1A6DD94, 0x531F7901, 0x0B090101),  # CachedOrGenerateBuilder
    (0x2D68284, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument1<bool>>
    (0x2D68428, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument1<short>>
    (0x2D685CC, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument1<int>>
    (0x2D68770, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument1<long>>
    (0x2D68914, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument1<object>>
    (0x2D68AB8, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument1<float>>
    (0x2D68C5C, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument2<short, byte>>
    (0x2D68E00, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument2<int, bool>>
    (0x2D68FA4, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument2<int, int>>
    (0x2D69148, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument2<int, object>>
    (0x2D692EC, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument2<object, int>>
    (0x2D69490, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument2<object, object>>
    (0x2D69634, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument3<int, int, int>>
    (0x2D697D8, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument3<int, object, object>>
    (0x2D6997C, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument3<object, int, int>>
    (0x2D69B20, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument3<object, int, object>>
    (0x2D69CC4, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument3<object, object, int>>
    (0x2D69E68, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument3<object, object, object>>
    (0x2D6A00C, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument4<int, int, int, int>>
    (0x2D6A1B0, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument4<int, int, object, object>>
    (0x2D6A354, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument4<object, int, int, int>>
    (0x2D6A4F8, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument4<object, int, object, int>>
    (0x2D6A69C, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument4<object, object, object, int>>
    (0x2D6A840, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument4<object, object, object, object>>
    (0x2D6A9E4, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument6<object, int, object, int, object, int>>
    (0x2D6AB88, 0x531F7941, 0x0B0B0141),  # AppendArguments<Argument6<object, object, object, object, object, object>>
    (0x2D6AD2C, 0x531F7941, 0x0B0B0141),  # AppendArguments<object>
    (0x2DF760C, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument1<bool>>
    (0x2DF8148, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument1<short>>
    (0x2DF8C84, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument1<int>>
    (0x2DF97C0, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument1<long>>
    (0x2DFA2FC, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument1<object>>
    (0x2DFAE38, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument1<float>>
    (0x2DFB974, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument2<short, byte>>
    (0x2DFC4B0, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument2<int, bool>>
    (0x2DFCFEC, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument2<int, int>>
    (0x2DFDB38, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument2<int, object>>
    (0x2DFE684, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument2<object, int>>
    (0x2DFF1D0, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument2<object, object>>
    (0x2DFFD3C, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument3<int, int, int>>
    (0x2E008A8, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument3<int, object, object>>
    (0x2E013F4, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument3<object, int, int>>
    (0x2E01F60, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument3<object, int, object>>
    (0x2E02ACC, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument3<object, object, int>>
    (0x2E03638, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument3<object, object, object>>
    (0x2E04184, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument4<int, int, int, int>>
    (0x2E04CF0, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument4<int, int, object, object>>
    (0x2E0585C, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument4<object, int, int, int>>
    (0x2E063A0, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument4<object, int, object, int>>
    (0x2E06EE4, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument4<object, object, object, int>>
    (0x2E07A28, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument4<object, object, object, object>>
    (0x2E08594, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument6<object, int, object, int, object, int>>
    (0x2E09100, 0x531F7921, 0x0B0A0121),  # AppendBlock<Argument6<object, object, object, object, object, object>>
    (0x2E09BF4, 0x531F7921, 0x0B0A0121),  # AppendBlock<object>
)


def patch_words(path, sites, unsupported):
    """Patches 32-bit words of the file at path where it lies, reading only those words.

    sites are (offset, original, patched); every word is checked first, so on any
    other value nothing changes and RuntimeError(unsupported) is raised. Returns
    how many words changed."""
    with open(path, "r+b") as handle:
        found = []
        for offset, original, patched in sites:
            handle.seek(offset)
            raw = handle.read(4)
            now = struct.unpack("<I", raw)[0] if len(raw) == 4 else None
            if now not in (original, patched):
                raise RuntimeError(unsupported.format(offset=offset))
            found.append(now)
        changed = 0
        for (offset, _, patched), now in zip(sites, found):
            if now != patched:
                handle.seek(offset)
                handle.write(struct.pack("<I", patched))
                changed += 1
    return changed


def patch_text_buffer(path, sites=SITES):
    """Patches the binary at path in place. Returns how many words changed; raises on an unknown binary."""
    return patch_words(path, sites, "Unsupported UnityFramework at 0x{offset:X}; text builder fix not applied")

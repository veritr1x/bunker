# Reached Unity worker-state switch entries

build_unity_worker_state_entries_overlay.py recovers the eight legitimate case
entries reached by original run25 after its real 180-frame observation.
The parent is the frozen windows-first-frame-thread-exit1 build
57430fa2285cb1bc9400e82ea3c1ed296e49ff28498cf4709ce0524e95643581.
It retains the selected 52-module Unity numeric-minmax refresh and all 4,661
existing objects, including the containing object450, byte-for-byte.

The original function is 0x70ddd510..0x70dddc20 (1,808 bytes). It loads the
unsigned selector from [X19+0x300], checks W8 <= 7, and uses signed 32-bit
offsets from the original table at 0x70fef300. The eight legitimate targets are
70ddd5a0, 70ddd614, 70ddd634, 70ddd648, 70ddd934, 70ddd998,
70ddda64, and 70dddac8. The actual failure was the first case, with
LR=70ddd54c preserved from the earlier BL70df4058.
The sealed boundary is work/runtime25-unresolved-switch-frontier1/acceptance.json
(45d4ccac1abbb53b8a73e6d6534ee99e020eacc8c938c199567720c0839dcb48).

The default producer invocation is read-only. --execute authorizes exactly one
eight-entry sparse qualification job, using the already qualified lifter
73a1d6cfâ€¦ and semantics24e908b3â€¦. It physically hashes all old objects before
and after, checks State1200/alignment16, the original guest-reference closure,
cooperative polling and pre-inlining guest-call guards, and emits one append at
object index4661. No old object or full original function is relifted/replaced.

The unselected packet is work/unity-worker-state-entry-packet1/acceptance.json;
it proposes 4,662 objects and 595,564 trace heads. The generated trace header
adds exactly eight declarations and eight rows; deleting those 16 lines must
recover the complete original header. The other three generated headers stay
exact. component_entries.h uses namespace bunker::unity_worker_state_entries.

The original guard/signed-table successor fixture is a separate qualification.
Its bounded entry/observer checks do not execute the full 1,808-byte function or
the eight case suffixes. The candidate packet itself is static code generation,
not selection, a full-host build, an original game run or a clean-shutdown claim.
No broad ISA change, future 62-module refresh selection, input fabrication or
unrelated FMOD modification belongs to this producer.

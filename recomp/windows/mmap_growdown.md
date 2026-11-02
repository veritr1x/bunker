# Recognized MAP_GROWSDOWN capability boundary

The original Unity alternate-stack allocation calls mmap with flags0x20122:
MAP_PRIVATE0x2 | MAP_ANONYMOUS0x20 | MAP_GROWSDOWN0x100 | MAP_STACK0x20000.
The old FileSystem allowed-bit mask omitted0x100 and returned EINVAL before any
native allocation. Unity interpreted that as ordinary allocation failure and
skipped its real sigaltstack install. The preceding disabled query did not prove
that an alternate stack had been installed.

The provider now recognizes the exact ARM64 `map_growdown` constant. After the
existing common length/protection/type/offset/unknown-bit checks, otherwise valid
private anonymous growth requests stop explicitly with
`unsupported mmap MAP_GROWSDOWN: owned downward expansion is not implemented`.
This happens before native allocation, owner/pin/generation publication, tracked
memory changes or Android errno mutation. Linux-invalid shared/file growth and
unaligned NOREPLACE addresses retain their existing EINVAL behavior. Aligned zero
with NOREPLACE reaches the named unsupported growth boundary: it is not a
malformed address and is not falsely translated to EINVAL or host EPERM. Other mmap
profiles are unchanged. This is a narrow boundary; it does not claim a new
general Linux errno-precedence implementation for every descriptor/flag mixture.

GROWSDOWN is a real VM capability. Android's ARM64 fault handler expands a
VM_GROWSDOWN VMA below its initial low address, subject to resource limits and
neighbor guard policy. Merely permitting or dropping the bit while allocating a
fixed Windows buffer would silently lose that behavior. MAP_STACK is a separate
hint and does not provide growth. No Windows expansion, signal polling, production
delivery or collector capability is added by this correction.

The read-only audit in `work/growdown-audit` retains pinned Android13-5.15 and
QEMU8.2.2 primary sources, ARM64 NDK constants, actual original disassembly and
independent native/QEMU probes. Both accepted the exact original allocation and
installed it as an alternate stack; both physically expanded a controlled
mapping on a below-start store. QEMU's synthesized `/proc/self/maps` omitted the
growth, while raw `/proc/thread-self/maps` showed the real host expansion.
The old frozen Windows provider's real NDK call returned the false EINVAL.

`test_mmap_growdown.py --out <fresh-directory>` freezes accepted host944a091 plus
five exact provider/fixture/runner overlays. A real strict NDK caller sends the
original0x20122 request and must hit the named fatal boundary, without returning
MAP_FAILED into Unity's allocation-failure path. Focused checks verify common
malformed errors through NDK calls; true native free-address state; unchanged
errno/owner/lease/generation state; ordinary allocation after rejection; and no
exclusive-reservation epoch change across a real native worker's rejected call.
File-growth EINVAL is tested with an actual valid readable descriptor. Existing
MappingUse and FS116 gates are then run once against the exact frozen FS overlay,
including all three active-pin fatal boundaries. Failed candidate1 is preserved:
its test started a real Windows thread before asserting a deliberately freed
address stayed available; the OS could reuse/cache that address for the new stack.
Candidate2 checks address availability before starting that helper thread.

Accepted candidate2 passed54 focused checks, the actual original NDK fatal
boundary, all128 mapping races (72 acquire wins /56 mutation wins;469 dynamic
checks), the three expected active-pin fatal boundaries and FS116. MappingUse's
check count varies with the real race outcomes; it is not a fixed522-check gate.
`work/mmap-growdown2/acceptance.json` records the exact944a091 support source,
overlay/toolchain/objects/binary hashes, logs and immutable old fixture checks.
Root review then found the zero-address NOREPLACE test incorrectly labelled a
Linux EINVAL. Independent native/QEMU probes both measure EPERM at zero and
EINVAL at address1; the growth-only candidate3 fixes that classification and adds
an actual NDK zero-NOREPLACE boundary. Ordinary mmap/MappingUse paths are unchanged,
so candidate2's once-run regressions remain applicable; their original executed
provider hashes remain recorded rather than presented as candidate3 executions.
Candidate3 passes54 focused checks and both actual NDK named boundaries. Its
runner asserts that removing zero from that growth-only predicate is the entire
provider delta from candidate2, and pins the prior regression acceptance hash.

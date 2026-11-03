# Selected FCSEL transport repair

The current Windows startup still faults before EGL/GL. Several selected
legacy scalar FCSEL implementations interpret the selected floating-point
bits as a native address and load from it. Original FCSEL copies register
bits and does not read memory. See [the startup record](../windows/first_frame.md).

The selected-code inventory covers 556 objects, 2,164 functions and 5,766
faulty copies. Its second manifest corrects 261 operand-metadata windows
that extended into a following instruction. Each correction comes from
the selected value's own SSA source cone; all original bodies, opcode
candidates and old windows remain available as evidence.

Freshly lifting whole functions can introduce unrelated compiler-context
changes. The full proposal pass generated all 556 modules and held 304
function comparisons; no proposal was selected. The separate qualified
repair uses an exact local transport rewrite:

* Keep the existing selected numeric value, predicate, source snapshots,
  destination, upper-vector clear, PC, memory token and control flow.
* Keep the original `inttoptr` definition as an unused pure operation.
  Replace only its scalar load with `trunc i64 ... to i32` for S, or
  `add i64 ..., 0` for D. This preserves numbered SSA definitions.
* Bind each edit to the captured selected body and original FCSEL opcode
  and operands. Check original condition alternatives explicitly.
* Recover the original body by reversing the exact line edits. Retain
  every other module byte, definition and existing qualified overlay.

This is a separate proof mode. It does not claim that the result equals a
fresh whole-function lift. The existing strict fresh-body comparison
remains available unchanged.

The local verifier passes 32 focused checks, including real S and multi-site
D modules parsed by LLVM18. Its previous strict comparator is an exact
unchanged source prefix. The independent original-condition audit checks
all 5,766 sites against all 16 NZCV combinations: 92,256 evaluations with
zero unknowns. It preserves the original candidate lists and explicitly
records matching and nonmatching condition alternatives. Flag inputs are
fresh within the same instruction block, with no intervening write,
opaque call or atomic operation; runtime compare hooks are pinned
identities. The numeric rule also reuses the qualified 58,112-record
ARM/Linux/Windows FCSEL family gate.

All 2,164 captured function candidates pass the exact-line and inverse
checks, and all 556 objects compile. The native checks are byte-exact for
unmodified functions except seven in object2598: nine RIP-relative `.rdata`
addends move with the constant pool. Their resolved reads retain the same
five 16-byte sign masks and four 4-byte `1.0f` constants, with required
alignment. All other instruction bytes, calls and sizes match. A separate
saved-object check admits that one case without recompilation, preserving
the initial failed comparison record. Raw and polled IR identity remains
exact for every unmodified function.

Final native admission requires the saved-COFF complete-byte audit and its
symbol-boundary supplement. The shared historical `native_projection`
parser can omit the final byte of certain long instructions before a tab;
its recorded projections remain historical diagnostics. The complete-byte
audit checks every instruction byte against the actual COFF section,
includes relocation positions/types/symbols/addends, and confirms whole
code-section coverage through real symbol boundaries.

The complete 3,576-object cohort passes final validation, with 687 guard
cases per language in Python and PowerShell. The selected Windows build
`windows-first-frame-fcsel-batch1` links successfully. Its original muted
startup exits native3/controller1 at reported PC `70752174`, following
original `70752170` (`4c008d40`, ST2 through X10). That instruction belongs
to the existing qualified ST2 family, but its retained function has not
yet been refreshed. There are no EGL/GL calls or frame witness. The earlier
FCSEL access violation does not recur; a game frame remains unverified.

Current artifacts under `work/`:

* `selected-fcsel-inventory2/batch-manifest.json`: corrected selected-code inventory.
* `fcsel-transport-mode-qualification2/acceptance.json`: local verifier tests.
* `fcsel-condition-qualification1/acceptance.json`: original-condition checks.
* `selected-fcsel-transport1/plan.json`: frozen tools and input pins.
* `selected-fcsel-transport1/proofs/acceptance.json`: all exact-line proofs.
* `selected-fcsel-transport1/compiled/`: candidate objects and preservation checks.
* `selected-fcsel-transport-resolved2598-1/acceptance.json`: complete admitted vector.
* `fcsel-transport-object2598-audit1/evidence.json`: exact constant-pool relocation proof.
* `fcsel-native-fullbytes-postcheck1/acceptance.json`: complete saved-native-byte comparison.
* `fcsel-native-fullbytes-postcheck1/boundaries.json`: native span and section coverage.
* `first-frame-fcsel-batch-cooperative-cohort1/acceptance.json`: complete v8 cohort.
* `cohort-v8-validation2/acceptance.json`: final Python and PowerShell guard checks.

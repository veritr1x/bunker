# Original Unity decoder automatic environment

Original run20 stops before saving an unregistered `setjmp` environment at
`23877e3bca0`, with return PC `70a8aa1c`. The address lies inside the thread's
owned stack, but that reservation alone does not prove this automatic object's
lifetime. The static proof is `work/runtime20-setjmp-frontier1/acceptance.json`.

The original ELF has two relevant FDEs. Outer `70a8a5c4..70a8a9fc` is 1,080
bytes and allocates a `0x42a0`-byte frame. Its automatic environment begins at
post-prologue `SP+0x10`. At `70a8a8ac`, it calls inner `70a8aa08..70a8aa64`,
passing that environment and returning to `70a8a8b0`. The 92-byte inner creates
a further `0x20`-byte frame and calls the genuine setjmp PLT at `70a8aa18`, with
return PC `70a8aa1c`. Its saved SP is therefore `environment-0x30`.

The buffer belongs to the outer invocation, while the saved continuation belongs
to the inner invocation. `GameUnityDecodeEnvironments` records both. Only the
exact entries, original callsite, frame sizes and environment address establish
ownership. Both records carry the owner instance, thread token/generation and
fresh invocation generation. An outer object alone cannot authorize a save.

Each inner return forgets its saved context before retiring its invocation,
even while the outer object remains live. The original outer loop may then call
the inner again with the same buffer; that receives a fresh continuation
generation. A second simultaneous inner for the same outer is rejected. Nested
outer invocations retain separate buffers and saves. Both normal return and
native exception escape retire bookkeeping; exception escape remains failure.

The trace table, both exact linker wrappers and the static guest-call fast path
select these owners. The original guest bodies remain unchanged. The link adds
`-Wl,--wrap=sub_70a8a5c4` and `-Wl,--wrap=sub_70a8aa08`. The old IL2CPP and font
cmap owners remain intact. No arbitrary stack range is admitted, and the existing
guard against unimplemented guest longjmp transfers remains in place.

The focused fixture links the byte-exact selected shard377 object and executes
its original inner function under the real runtime call protocol. Six normal
paths compare against the unchanged 92-byte ARM function with genuine Android
Bionic setjmp. Decoder and cleanup callbacks are explicit test boundaries.
An outer test harness models the proved frame and callsite; this does not claim
execution of the complete original outer function or a complete decoder.

Owner checks cover repeated and nested invocations, expiration between inner
calls while the outer remains live, same-outer reentry, wrong owners/threads/
generations/geometry, invalid returns and native exception retirement. Synthetic
guard-negative cases stay outside lifted nounwind calls. The old font owner's
267 checks also run against the new detail header.

`work/unity-decode-owner-qualification4/acceptance.json` admits 720 owner checks,
38 negative cases and the six matching native/Windows paths. Its original runner
failed after all 13 subprocesses succeeded because it expected the font test's
last-case save counter to be 14 instead of 2. The failed runner and failure
receipt remain intact. Saved-artifact admission rechecks the held inputs and
outputs and proves a one-literal correction to the runner; it recompiles and
executes nothing. Original startup integration remains separate. These fixture
results do not establish a visible frame or working gameplay.

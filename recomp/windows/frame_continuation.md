The Windows bootstrap accepts a final `--run-frames N` or
`--run-until-close` argument after the explicit muted collector first-frame
profile. `N` must be a positive decimal uint64. The default first-frame
diagnostic still stops at its first verified image and holds the window for
ten seconds.

Continuation uses the existing lifecycle's `PollFrame` and `RequestNextFrame`
on the same UnityMain worker. It invokes nativeResume once. Real focus loss
pauses requests; a real window close or a false original nativeRender result
ends the sequence. The bounded mode stops after N returned renders, regardless
of when the first-frame witness succeeds. It skips the diagnostic hold.

For N greater than one, render N-1 queues `later-frame.png` through the
[snapshot API](../whole/frame_snapshot.md). Only a subsequent successful
original presentation can fulfill that request. The initial capture and
witness remain separate. Until-close mode does not request a later snapshot.

The policy/parser and selected real lifecycle/JNI implementation pass 969
component checks in `work/game-frame-continuation-qualification2/acceptance.json`
(SHA256 `5fa9d776d35f7e4a530cdce25161f97801924704f9647dc42ba2abe97a30ab82`).
These cover 180 returned fixture callbacks, default stop at three, close at
17, false return at seven, twenty parser negatives, focus interruption and
one nativeResume per case. Transparent callbacks stand in for original game
entries in this component test; it does not establish sustained game rendering.

The subsequent original run24 completes all 180 renders and captures the
publisher/developer splash. See [the original execution result](first_frame.md)
for its actual build, image and audit pins and the remaining shutdown failure.

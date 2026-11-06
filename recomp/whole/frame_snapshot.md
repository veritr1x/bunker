The optional frame snapshot API queues one absolute new PNG path from the
requesting thread. It makes no GL calls there. The render thread reads the
owned window's default framebuffer at the next eligible presentation entry;
only the matching native thread, display, context, surface, extent and actual
`EGL_TRUE` return can publish that image. Failed or mismatched swaps consume
their tickets and leave the request queued for another genuine presentation.

`RequestFrameSnapshot` returns a monotonically increasing request serial.
`DescribeFrameSnapshot` reports its pending/completed state, attempts, exact
presentation ticket and native identities, path, dimensions, nonuniform flag
and failure independently of `FrameDiagnostics`. A second pending request,
relative path, existing output or first-frame witness path is rejected.
Readback and PNG output preserve GL pack/PBO/read-FBO state, original GL
errors and the calling thread's errno, LastError and floating-point environment.
Uniform content is saved as-is. There is no brightness or image adjustment.

The selected first-frame witness logic remains the default. A later snapshot
does not replace its PNG, ticket, capture attempts, presentation identity or
failure status. Draw and clear counters continue to count real calls.

The focused native test and independent Python PNG decoder passed in
`work/frame-snapshot-qualification1/acceptance.json` (SHA256
`0ee4a45823d3896a349881fb9b356e90b58498f3e65426c949d6383d83d99107`).
Its 278 checks preserve the old 242-check capture fixture, then cover a UI
thread request, retry/consumption controls, unmodified later nonuniform and
uniform pixels, output failure isolation, and the unchanged original witness.
All other providers and headers were copied from the selected frozen
`windows-first-frame-gl-draw1` parent manifest `382957667390947ffe8e7af58c38a980ea53bacf4221fb802ebf9cd74b1760e5`.
This is synthetic component qualification; it does not claim an original
Unity/game run or a later game screenshot.

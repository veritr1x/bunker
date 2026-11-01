# Real Win32 window / ANativeWindow subset

`NativeWindows` supplies actual HWNDs and initialized host-owned Java Surface
objects. Six imported Android APIs are implemented through checked opaque
window tokens: fromSurface, acquire/release, getWidth/getHeight and
setBuffersGeometry. JNI references and native references retain the same
resource independently. Tokens are never reused and allocation is bounded
before the next provider's namespace. Unknown/double/expired references fail.

Each window owns a native UI message thread. Its procedure queues resize,
focus and close events; it never calls guest code. WM_CLOSE requests are
deferred until the lifecycle owner retires EGL resources and calls Close.
Last-reference cleanup destroys the HWND and joins its UI thread outside
registry locks. Queued commands use nonowning captures to avoid last-reference
destruction/join on the UI thread itself.

Window size means client pixels. The UI thread uses per-monitor DPI awareness,
measures the resulting native client and corrects nonclient sizing. Hidden
windows need an explicit initial client measurement before WM_SIZE arrives.
`WindowDpiScope` temporarily matches a calling worker to the HWND's DPI context
for EGL/Win32 geometry queries, then restores its previous thread context.
Windows can enforce minimum tracking sizes; unachievable requested client
dimensions fail with the actual observed size rather than returning invented
dimensions. Create/ResizeClient configure the physical view, not buffer scaling.

The installed NDK's `android/native_window.h` specifies that buffer geometry is
independent of physical window geometry, and zero restores base values. This
provider follows that distinction. Base RGBA8888 geometry tracks actual client
pixels. Any nondefault format or fixed buffer size requires an ApplyGeometry
renderer callback which actually honors the request. Even a fixed size equal
to today's client size needs that callback because future client resizing must
preserve the fixed-buffer contract. Without one, the API returns -ENOSYS;
invalid shapes/formats return -EINVAL. Failed backend changes leave metadata
unchanged. No successful scaling implementation is implied.

The native Windows gate passed **291 checks** through eight translated NDK
traces with zero unsupported instructions. It verifies all six imports,
pixel geometry, transactional geometry failures, typed/invalid Java objects,
concurrent native references, resize/close events, deferred close, lifetime
after Java references drop, and final-reference HWND/thread retirement.
Its windows are hidden; real EGL draw/swap is a separate integration gate.

```sh
python recomp/windows/test_native_window.py --ndk /path/to/ndk \
  --lift /path/to/remill-lift-18 --remill /path/to/remill-src
```

Use the disjoint [guest identifier namespaces](guest_addresses.md) when
combining providers. The actual game lifecycle, rendering, input/audio and
nondefault buffer-size scaling remain separate work.

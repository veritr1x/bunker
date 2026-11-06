# Queued Win32 input capture

NativeWindows observes mouse and key messages dequeued for its own HWND. The UI
thread appends ordinary events; it does not invoke guest/JNI callbacks. The four
existing lifecycle kind ordinals and their aggregate fields are preserved, and
the existing resize/focus/close/destroy WndProc is unchanged.

Mouse records retain signed client coordinates, raw Win32 button flags, changed
button identity, X-button ID and signed wheel delta/direction. Wheel messages
also retain their original signed screen point and convert it using the actual
window's ScreenToClient. A failed conversion is explicitly marked invalid; it
does not become a fabricated point at the origin.

Key down/up includes ordinary and system-key messages. Records retain virtual
key, repeat count, scan code, extended bit, Alt context, previous-key state and
transition bit. The raw message ID and wrapping 32-bit MSG.time are retained.
No fresh clock is substituted for the timestamp of a queued message.

TranslateMessage and DispatchMessage still run normally. Capture does not set
focus, capture the pointer, change DPI/global OS settings, generate double-click
messages, inject input into another window or synthesize Android events. Native
Windows coalescing and default system-key behavior remain in place. This layer
observes queued messages, not direct SendMessage calls, and does not assert that
a message originated in physical hardware. Text/IME and Unity input delivery
are separate work.

The focused fixture creates its own hidden HWND, temporarily observes that
window's procedure, and posts explicit test messages only to that window. A
fixture-only barrier delays dequeue so independent WndProc GetMessageTime
observations can distinguish original queued timestamps from later dispatch
time. It checks signed bounds, button identities/state, wheel screen-to-client
conversion, key metadata/order and unchanged resize/close behavior. It never
calls SetFocus, SetCapture, SetForegroundWindow or SendInput.

The qualification runner copies supporting runtime/JNI/loader sources and
headers exclusively from frozen thread-exit build57430, then replaces only
native_window.cpp/h. The matching existing native-window fixture is separately
recompiled against the same provider objects and its byte-exact saved NDK guest
objects. No original game, Unity injection entry or playable-input claim is
part of this component qualification.

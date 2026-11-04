# Bionic calendar APIs using Windows timezone rules

The original timezone-discovery caller `82556d90..82557138` starts a
standard-time January1 conversion, then uses localtime, gmtime, difftime
and `strftime("%Z")` to discover offsets and names. The original imports
require eight APIs: time, mktime, localtime/localtime_r, gmtime/gmtime_r,
strftime and difftime. Boundary receipt:
`work/guest-calendar-boundary1/acceptance.json`, SHA256
`1d19eed3c9e49e2bc1457e4e9263d202e7104efb5b5433a7b9526f0fe0adff8b`.

The provider uses signed64 timestamps and Bionic's56-byte/alignment8 `tm`.
Checked Gregorian arithmetic and real year-specific Windows timezone rules
handle negative epochs, normalization and DST selection. A CRT-only bridge
would reject valid values: local midnight1970 in the current India timezone
is UTC timestamp−19800. Zone strings remain valid, and formatting uses the
represented C/C.UTF-8 locale. Native process timezone settings are not changed.
Guest TZ overrides are explicitly outside this host-zone profile.

Actual static NDK Bionic execution supplies the behavioral oracle. It
corrects source-only assumptions: gmtime/localtime use distinct buffers,
gmtoff hints are ignored, mktime sets EOVERFLOW for even a valid−1 result,
and strftime's internal `%s` conversion has different errno behavior.
The implementation follows these observed rules, including DST folds/gaps
and short-buffer formatting. Reference:
`work/calendar-bionic-reference6/acceptance.json`, SHA256
`d61971be9b822ea81168ea5928fe157a7b40f6b7994df902a7476319f6986687`.

The Windows gate passes96 conversion and100 formatting comparisons, plus
26 actual translated NDK calls across all eight APIs. It checks the real
host timezone, negative epochs, large difftime values, buffers, native
environment preservation and two library bad-pointer fault controls.
Earlier controller/compilation failures remain preserved. Final collection
reuses the verified positive executable and records the two fault exits
through native Windows, avoiding WSL's truncated status5.

Qualification: `work/calendar-host-qualification6/acceptance.json`, SHA256
`611e4631bcb737b89294dfd6b2cc837d0468d8a02f42663d99bae37a7cb26617`.
Independent peer: `work/calendar-provider-peer1/acceptance.json`, SHA256
`49a0f0e16a6ff53e2983592aef33863b0398f02464aca641e0c3dbc76e78077d`.
All prior LibC marker addresses, method bodies and its class header/layout
are preserved. The eight bindings are appended.

Local timezone conversion is bounded by the Windows calendar profile
(years1601..30827); unsupported ranges fail explicitly. New non-Windows
local-zone behavior remains ENOSYS, with no Linux runtime qualification.
Game startup and rendering remain separate integration gates.

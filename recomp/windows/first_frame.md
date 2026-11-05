# Native Windows first-frame status

The target is the original game running as a standalone Windows x86_64
executable. A presented game image and working gameplay remain unverified.

Latest completed candidate: `work/windows-first-frame-main-nanosleep-sites1`,
manifest `2c16ac72a336ae5e3c0707d3a600503e77423547dfad27cae3f0a8bb596c3d11`,
EXE `ffb787231957682a7f4f4840f25bea9d722140d49539001fbfa16699d00f9a8f`.
Four renders return with no sleep-routing abort, but the next render naturally
exits native3 at reported PC `7033b784`: missing integer `CNT V0.8B,V0.8B`
at `7033b780`, immediately followed by missing `UADDLV H0,V0.8B`.
The source FDE `7033b734..7033b868` counts bits over seven64-bit words before
calling its real helpers. There is no draw, swap or image; all pre/post checks
pass. The new backoff LR was not observed in this run, so its live exercise
is not claimed. Formatter-case execution is not instrumented or inferred.

Boundary `work/main-nanosleep-sites1-unliftable-boundary1/acceptance.json`,
SHA256 `a8635773b57f0c7c8fccaee761b6da57d92bc15971864aeac0968fe629cbe04e`.
The proposed coherent repair updates nine functions in containers72/119/125/333
for this same integer pair. [vector_cnt_8b.md](../whole/vector_cnt_8b.md)
records13,056 exact ARM/raw-Windows/polled-kernel cases, including the actual
helper-free56-byte loop prefix. It does not claim whole-function execution of
the nine helper-using functions. The initial rough inventory incorrectly
excluded `7033bdac`; canonical function extraction and original instruction
bytes prove the same pair there, so it is included before integration.
Original integration remains pending.

Preceding completed candidate: `work/windows-first-frame-il2cpp-format1`, manifest
`d55512b91b677f412427cf993e7f62e4b5b844120287c61916e6b4a7559589c4`,
EXE `63e71d95ae2bf8725fad51c86c1e644c9aba7673317e58a306744c689aa1dfe2`.
The twelve formatter entries are selected (4657 objects,595470 heads), but
this run ends earlier: two renders return, then an adapter guard aborts at
ordinary original IL2CPP backoff `nanosleep`, LR `825a7230`, before request
copying. The owned-main wrapper routed every sleep into a phase accepting
only Unity LR `70383878`. This proves a routing/site mismatch; neither a race
nor a formatter regression is established. All input and parent pre/post
checks pass, with no draw, successful swap or image.

Causal receipt `work/il2cpp-format1-nanosleep-boundary1/final-acceptance.json`,
SHA256 `921062afb49cad80e0563623f78e0fbd9fd615702359120626bff2e66e2fb8ef`.
The proposed fix qualifies the original64-byte IL2CPP backoff frame alongside
the old32-byte Unity frame and routes other sleeps through the real ordinary
provider, preserving pending collector signals. Four fresh test processes pass
550 checks and eight original stop/restart signal cycles, including physical
register roots. This does not claim a complete heap collection, whole backoff
helper execution or original-game progression. Next integration remains pending.

Preceding completed candidate: `work/windows-first-frame-neg4s1`, manifest
`b41a7a2c5933e532e252b9c42e3bd59f13d77823f4b9dd80da1b043244ae66ed`,
EXE `493a97e6d9adf241e65992abd9b0f9b8fc6ccc6d8f64ba564f6b61f9c185717b`.
Both reached integer NEG repairs now progress. Four original renders return;
the fifth naturally exits native3 at missing indirect entry `849b02c0`,
LR `849af378`. There is no draw, successful swap or PNG. All child/runtime
and original-parent pre/post checks pass.

The missing address is an interior target in selected IL2CPP FDE
`849b021c..849b0490`. Its caller makes a genuine direct call at `849af374`;
two guarded signed-offset tables dispatch to twelve unselected interior
entries. Boundary `work/neg4s1-il2cpp-indirect-boundary1/acceptance.json`,
SHA256 `171de3d47bdeeb3fe5f6d64b851834c01bb58f52264149597a4657c7c579fb9b`.
The proposed coherent append preserves all4656 existing objects and1011 host
sources, adds one17974-byte object and twelve trace entries (595458 to595470).
Its raw/polled code has no unsupported instructions and the trace header has
an exact24-line inverse. Finite valid-capacity execution now passes84 exact
records on original ARM, raw Windows and the exact polled entry object;
all twelve entries execute. The next original integration remains pending.
Resize/null-buffer/bounds-exception paths are excluded from this gate.
No original frame is claimed.

Preceding completed candidate: `work/windows-first-frame-neg2s1`, manifest
`a07beb8c0288020ee409532fe07a243dd58154585b5e4c1dd30559f9e3f5b1d4`,
EXE `2129104189f65440d4d2768f1699c215073343b190c32ade45be483ae3b7d895`.
The reached NEG.2S function now progresses. This run naturally exits native3
at reported PC `7065185c`, following integer `NEG V17.4S,V17.4S` at
`70651858`, in recursive FDE `7065175c..70651884`. Four renders return,
with no draw, successful swap or PNG; all input and parent pre/post checks pass.
Boundary: `work/neg2s1-unliftable-boundary1/acceptance.json`, SHA256
`00ef152859e731d6de5420cc4f8e610be0978023c69e18b282c40617fa28bb40`.

The isolated four-lane addition passes8704 exact original-ARM/raw-Windows/
polled-kernel records, including the two-lane regression. It is documented in
[vector_neg_4s.md](../whole/vector_neg_4s.md). The proposed single container231
repair preserves the prior `70652c68` FMAXNM body. Its other127 raw/polled
bodies remain exact. Native code has122 exact projections and five whose ten
constant-pool relocation words move by32 bytes; an exact whole-pool inverse
and unchanged referenced payloads prove this data placement, with no COFF edits.
The kernel gate does not claim dynamic execution of the whole recursive
function. Integration and the first frame remain pending.

Preceding completed candidate: `work/windows-first-frame-gl-mapping-batch1`, manifest
`01869d0f314745be2c5d19d5836b5fef23a74e2defca40c43427e440b63c96f9`,
EXE `f475d8a42a69712cc8197a1d2d9bf2cf668e34c45c39e53cda78fc7ab41d10f5`.
It passes the previous null map call twice and then naturally exits native3 at
reported PC `70161a7c`: unsupported integer SIMD `NEG V0.2S,V0.2S` at
`70161a78`, inside FDE `70161998..70162b00`, selected object30. Four renders
return, with no draw, successful swap or PNG. All child/runtime and parent
pre/post checks pass. Boundary receipt
`work/gl-mapping-batch1-unliftable-boundary1/acceptance.json`, SHA256
`2c5eda9e7eec37ab6b62238cb8edbbc0f2e83889ce0ee3cb7bc6820c5c9e777f`.
The real mapping family and four bounded numeric leaves are selected; a narrow
integer NEG.2S decoder/semantics repair is next. Other NEG-family functions
remain unselected. The mapping's component gate is documented in
[gl_mapping.md](gl_mapping.md); its GPU triangle is not an original-game frame.

Preceding completed candidate: `work/windows-first-frame-leaf-rounding1`, manifest
`29eb3b23864ea4d3a8dd0dfa19694c6716f09613148f864919f07e9fe90b6088`,
EXE `76ad6ff29b3d70843f87ae9161baa27c12ad1c2a64960bd555fa8043d3faf468`.
The original UnityChoreographer constructor and recurring callbacks work, four
nativeRender calls return, and both reached numeric leaves (`70167bbc` and
`70167fc4`) progress. Exhaustive synchronization/JNI logging retires after the
fourth actual render returns. The fifth render naturally exits native3 at a
null graphics procedure; all child/runtime and original-parent postchecks pass.
There is no original draw, successful presentation or PNG yet.

The null procedure is proved to be `glMapBufferRange`: loader `70473024`
requested the core name and stored zero at context offset `0x5e0`; wrapper
`70490250` branches through that slot at `704902fc`, retaining LR `7046fdfc`.
The live arguments are target `0x8f37` (COPY_WRITE_BUFFER), offset0, length96,
access `0x36`. The earlier recorded Raise returned before this GL progress.
Boundary receipt: `work/leaf-rounding1-null-call-boundary1/acceptance.json`,
SHA256 `bf7adc7519412b88f3d392a9088e5a1b4f3685ffbb31dddafce0bfd023470b03`.
Its successor supplies real ANGLE map/flush/unmap operations and their actual
buffer/share-group lifetimes. Native GPU qualification passed and the original
run above progresses beyond the old null call. Four additional bounded
numeric-leaf repairs are also selected in that composite.

The preceding scanner build completed three actual `(%u)` assignments, then
naturally stopped on render5 at reported unliftable PC `70167c1c`: the retained
error stub is for preceding FMINNM `70167c18`. The final completed-run receipt is
`work/paren-scan1-fp-boundary1/final-acceptance.json`, SHA256
`a6f646f55f58102fbd183c165d082166385a2bfbd83c3b243ed20a2af7d81fc9`.
All child/runtime and original-parent pre/post checks pass; no image exists.
Rendering had paused after render3 on a real focus loss and continued on the
same process when the user brought Bunker forward.

[The repaired function's qualification](frame_rounding.md) covers only a
predefined normal/zero geometry domain, with336 exact ARM/raw/polled records
and1344 exact ARM/production-polled records across16FPCR configurations.
All96 broader edge-case mismatches remain preserved. Live operands/FPCR are
unknown; universal floating-point equivalence is not claimed. Exhaustive
per-call tracing was also observed beyond render4; its overhead is suspected,
not established as the cause of the long fifth render.

Diagnostic `work/windows-first-frame-main-observe1` was manually ended with its
fourth original nativeRender pending. The missing Handler.Callback class leaves a
pending JNI exception, preventing the original constructor from queueing its
initialization message. UnityChoreographer then waits with its ready payload
still null at LR `704372c8`. The causal audit is
`work/main-observe1-cond-boundary1/final-acceptance.json`.

The replacement implements real asynchronous HandlerThread queues, the
registered JNIBridge native callback route and an owned UnityMain Looper.
It preserves original native initialization and condition signaling. Six
recovered original entries append to the existing guest cohort. The native
UnityMain FIFO passes294 checks; combined syntax passes. Final framework
qualification passes880 focused checks,180 actual NDK calls and11 registered
TEST native invocations, plus237 existing proxy and11125 JNI numeric checks.
The separate original-constructor component remains pending; the actual game
execution is the integration test. No first frame is claimed.

Replacement `work/windows-first-frame-choreographer1` is linked and independently
reviewed with53 checks. Its manifest is
`35707ea61acfe2f6664da876041f66fc66c4ad8362dfbda5e5eeac93e22d9814`,
executable `b62f233d7ba31bfa748a1b6374b2fa97b86dd53d3d388de3f0ffb3b1b56d8d46`.
Its one fresh controlled original run naturally exits native3/controller1
at untranslated indirect entry `7022c0ec`, LR `7022c0b8`, on render5. The real
UnityChoreographer initialization message dispatches on its actual child,
the constructor condition wait returns0, render4 returns continue=true, and
the original FrameCallback repeatedly posts itself. Startup is repaired.
There is still no draw, presentation or PNG. The actual boundary receipt is
`work/choreographer1-original-boundary1/acceptance.json`, SHA256
`5afb3e81c1b8536a29a4ce2130bb5dc8f9eb16786ff55f67c8c86b22afd7f3e6`.
All overlay/runtime pins and original-parent pre/post checks pass.

The next repair recovers the coherent four-way guarded table in original FDE
`7022c0a4..7022c188`: entries `7022c0d8`, `7022c0ec`, `7022c104`, `7022c158`.
The current4655 objects and595454 heads are preserved as the exact prefix;
the proposed single object adds four heads. Qualification and selection are
pending. The isolated638-function fixture is incomplete at a setup-only
dynamic dependency; it is not represented as passed or as a production defect.

That table repair is now selected in `work/windows-first-frame-frame-pacing1`,
manifest `a54c0b321938144b620cd0ca38b5df37cdf81b41177f443f95d67866db31c745`,
EXE `152a5cad0e925bdb0b5db8fbcf06d08bb68083ed3735f209b696d29827f60ad2`.
Its36 finite cases per originalARM/rawWindows/exactpolled platform match.
The controlled original run progresses beyond the old indirect entry and
naturally exits native3/controller1 on render5 at unsupported exact scanner
format `(%u)`, LR `701b61c0`. Four renders return, with no presented image.
All child/runtime and original-parent pre/post checks pass. The actual boundary
is `work/frame-pacing1-paren-boundary1/acceptance.json`, SHA256
`3a9c1261006789ea3eff416d1abd2087099df43312bfeb47c0cf08ef9767760e`.

The single-file scanner repair is committed as `42506d7` and qualified in
[libc_paren_scan.md](libc_paren_scan.md). Its318 Bionic differential records
match exactly; old scanner regressions pass. Host integration and the next
original execution remain pending. No input value or first frame is inferred.

The build's pending-runtime fields remain historical; the separate
`runtime-admission.json` records the actual generic gate and integration scope.

The previous run's native255/controller1 records manual termination, with all
overlay pins and original-parent pre/post checks passing. It completed three
renders with zero drawing/presentation/image. Audit SHA256
`e4a2d6d94518d17b50b5e5bed96f0b9a3c7708a6ce8c213d9276e2e743ab9b2a`;
manual-stop receipt `work/main-observe1-manual-stop1/receipt.json`, SHA256
`f34b9326df555393adacdd6f7cc69f450020fd76de2b401503f97cfc4d6d566f`.

## Earlier execution evidence

Latest completed controlled execution: `work/windows-first-frame-http-scan1`,
source `2a74491`, was manually ended with its fourth nativeRender pending. Its three
completed renders return continue=true and draw zero times. There is no
successful presentation or captured image. The actual HTTP scanner now returns
three assignments at LR `70b5680c`; execution proceeds beyond the previous stop.

The log also records a missing `android/os/Handler$Callback` lookup immediately
after entering frame four. That is a confirmed compatibility gap, not a proved
cause of the wait. The last GC epoch38 completes before render3. A worker's
read entry is followed by a dispatcher futex entry on the same thread; an
outstanding network read is not established. Windows WCT reports one blocked
thread node for UnityMain and two workers, with no wait object or owner.
The causal wait and UnityMain continuation remain unresolved.

Input overlay SHA256
`32293ce23aacf1be89a89b1bbe4ff2639a423efe090de945f01e1540e7e68a21`;
EXE `283b2c91f6d91ed0393bc09098aae6cc74c84cde936475b8dad8901d824550b2`.
Built-input review: `work/http-scanner-built-peer1/acceptance.json`, SHA256
`57859a4094c6200b509c6377c8748d0482457d0ebb914cd0de303ac5c34c29b6`.
Actual PID282764, module base `7ff6afbd0000`, image1055412224 bytes.
The stalled process was manually terminated only after its preserved evidence
and the replacement diagnostic executable passed review. Controller/native
status1/255 records that intervention, not a natural game failure. All overlay
pins and original-parent pre/post checks pass. Run audit:
`work/windows-first-frame-http-scan1/game-frame-muted-gc-audit.json`, SHA256
`22771b5b797a628863343b2953e909c560ec2856acabbdb0b8b45d17a2892c90`;
log `1cf4f4c77cb64af6cb4e71da156bc95c740e18da17224c52309e9ef50a525f78`.
Explicit manual-stop record: `work/http-scan1-manual-stop1/receipt.json`, SHA256
`a9a88faf578b783e533e77587c54ca45e559fbf4097f1775d707eb48f813d3a9`.

Read-only evidence:
`work/http-scan1-wait-boundary1/acceptance.json`, SHA256
`68e4c8ac85c5029348609689ba42b2686a0b25133b70b63d7e589cb0f1f38df2`;
`work/http-scan1-live-waits1/receipt.json`, SHA256
`a1a6b8e5e89c6853a1eb29c67141403c07199e91a6f5f02375637a23fc72fbff`.
The preserved live log and corrected67-thread snapshot are in
`work/http-scan1-live-preservation1`; use `live-threads2.json` (SHA256
`4dca366655800acc44b04cffb91b4c267cfd32281e6afb7879893d275475ed0a`).
The initial `live.json` lacks a valid thread collection; the corrected file
records that limitation.

The next executable adds observation only: actual UnityMain JNI entry,
body-return and completion, plus unsampled real main-thread synchronization
entry/return from the fourth render onward. It does not add Handler support,
change guest calls or return values, wake a waiter, or control process lifetime.
Strict syntax and an eight-check independent source review pass. Source proof:
`work/main-observe-source-preparation1/source-proof.json`, SHA256
`907577df40c2e28da84ef52f0502d31d6a1455dbbf4f8b26d7d951fc82e28b53`.
The diagnostic executable is built in `work/windows-first-frame-main-observe1`,
source `18100cf`. Overlay SHA256
`44dca262a816f33738a90cfd3a968083affb0c5e5b2bedf8daec93fb9a906c46`;
EXE `da5c66522df28e4817858b3ffdc59b599de182baed831ce8b725ed9784ff402c`;
bootstrap `ffc370ac150a67ad0f54aed870bdc3f5bf159930f269af2b87c1394dea3874b3`.
Its independent42-check built-input review passes:
`work/main-observe-built-peer1/acceptance.json`, SHA256
`ed45e424f671671bc1295abe9f531c41063901c0dcb2caada217b443257c4507`.
The diagnostic original-run controller is launched; its new game execution
remains pending launch integrity checks.

Preceding original execution: `work/windows-first-frame-socket-tls1`, source
`41e47bb`, selects Windows public-root export and the 40 recovered original
computed-table entries. The snapshot has 1007 source files: three changed,
two added, and 1002 byte-exact from socket1. Bootstrap and all 46 host sources
are freshly compiled. All 4653 prior guest objects remain exact, with one
qualified object appended; the header has 595448 entry heads.

The original caller now executes getDefaultAlgorithm, getInstance, init,
getTrustManagers, getAcceptedIssuers and 60 getEncoded calls. The default
Windows reader supplies 60 public DER certificates. The prior missing-class,
Curl51 and unresolved `70b4c100` failures do not recur. This is actual CA-export
and later network-path evidence, not proof of a successful peer/hostname
verification or an authenticated backend connection. The runtime hostname,
input status line and parsed status remain unlogged.

The three original render calls return continue=true with zero draws.
There is no successful swap, PNG or first-frame witness. Native exit3,
controller1 stops at the actual `sscanf` format ` HTTP/%d.%d %d` (including
its leading ASCII space), LR `70b5680c`: outside the qualified scanner profiles.
The next work implements that original HTTP status parser with Bionic-compatible
numeric conversion and verifies it with actual Android/Windows callers.

The connected four-format HTTP/RTSP caller cohort is now implemented in one
LibC source change. Its 208 complete Android/Windows records match exactly,
including errno and output canaries, without normalization. Focused checks
pass1384 with228 actual NDK calls; the existing scanner regression passes387
checks with51 calls. See [the scanner qualification](libc_http_scan.md).
Source receipt `work/http-scanner-source-preparation2/source-proof.json`, SHA256
`f6071fcd7b1275877769c897c1c05c134666bb4ef08f3d2d18d6b1eab547478b`,
binds that one-file inverse to the immutable parent. The next full executable
and original-game scanner result remain pending.

Overlay SHA256 `25d625c39abe4f9e67826d53fcd4275d645e9e48227a4ce1564db9311184e162`;
EXE `61bfcf119594fb42e7abb8b27623a3a874b568c0aaafd53861b7e79ef092c1cd`;
bootstrap `9477fcecda97b4a9f7512d456efc84dd70416331fbe52dc01f1903bdc9daa76b`;
log `72f8dbd8ea066575ab9bd02523d648938ffc8238f7d874acfabb0ae2875ea3db`.
Actual module: PID243356, base `7ff6c0900000`, image1055412224 bytes.
The process has exited and its controller session is collected. All overlay
pins and original-parent pre/post verification pass. Run audit:
`work/windows-first-frame-socket-tls1/game-frame-muted-gc-audit.json`, SHA256
`934f6b710fc5458e5cc622a971c3794f899a78f38f0ce80299d6c83b31bc49d4`.
Independent built-input review passes48 checks:
`work/socket-tls-built-peer1/acceptance.json`, SHA256
`6e632446b1fcdef0bcba4beb3b911d7b41e1e0fd9d3080697730e2b254934a9a`.

Preceding original execution: `work/windows-first-frame-socket1`, source
`79df7fe`, selects the qualified connected-client and collector-wait cohort.
Its 1005-file snapshot changes six parent files and adds six; the other 993
remain exact. Bootstrap and all 45 host/runtime sources are freshly compiled.
All 4,653 guest objects, 595,408 heads and four generated headers are unchanged.

Original execution reaches socket creation, inet_ntop, options, fcntl, connect,
poll, send and recv. The actual caller is a prepared Unity-worker lifetime,
token `7ffa00000006`, native TID 147340. This identifies the lifetime, not an
inferred GC record. No new network-wait physical-root marker is observed in
this run; that admission remains proved by its separate native component gate.
Operation entry logs alone do not certify every return value or a working
client/backend connection.

The third original render now returns continue=true, still with zero draws.
There are no successful presentations, PNGs or first-frame witness. The TLS
path records NoClassDefFoundError for `javax/net/ssl/TrustManagerFactory`
after Env slot 6 at LR `70ab5478` and slot 13 at `70ab524c`, then reports
Curl error 51 / `UNITYTLS_X509VERIFY_FLAG_NOT_TRUSTED`. The hostname, chain
and destination remain unlogged; an expired or otherwise invalid peer is not
inferred from this error alone.

Native exit 3/controller 1 stops at unresolved original Unity target
`70b4c100`, StatePC `70b4c100`, LR `70b47730`, SP `2028daa0c00`.
The subsequent composite build combines two qualified changes. The bounded original
computed-table recovery adds 40 original entry points in one object, with all
240 seeded executions agreeing across original ARM, raw Windows and the
selected polled Windows object. Its trace header adds 80 lines and preserves
all 4,653 prior objects. See [the entry audit](../whole/unity_curl_computed_entries.md).

The reached Java path exports CA certificates to original UnityTLS; it does
not ask Java to verify the peer. The new adapter supplies the actual
TrustManagerFactory, manager/interface and Certificate.getEncoded call path
using public Windows roots. Its default reader exports 60 eligible DER roots,
matching an independent native oracle: 84 enumerated, 16 excluded by usage,
eight by cached explicit distrust. No trust-store changes or accept-all path
are introduced. Original UnityTLS continues peer verification; complete Windows
trust-policy equivalence is not claimed. See [the adapter scope](java_tls_trust.md).

TLS qualification passes 6,630 focused checks with 1,420 actual NDK entries,
direct/V/A call forms and complete DER-byte comparison, plus 237 existing JNI
interface-proxy regression checks. Receipt:
`work/java-tls-trust-qualification3/acceptance.json`, SHA256
`3df59e64ee17277eee80e224649e84f316b359f89797534900749906f5c64efb`.
Those qualified changes are selected in the latest original executable above.
Neither component gate establishes a first frame or successful peer verification.

Overlay SHA256 `cfea157227771b0774a03f0c6ab952c07d6c603a9e979815aa53df6e009cc1c3`;
EXE `dbb5180987a4b95bf2c045f2a201d3b9b75070ba3a2948afa6857a239ef9fbaa`;
bootstrap `9c521bd28d1a10ca74cf86dc3a1571d1a3a07555092b5399d644ee8483a67dde`;
log `7395f3cdbc388ea200466391f54fc35f3ae468d75c7925f2791c738633df2c27`.
Actual module: PID 147544, base `7ff7c0ed0000`, image size 1,055,354,880.
All overlay pins and parent pre/post checks pass; the process exited and its
controller session was collected. Run audit:
`work/windows-first-frame-socket1/game-frame-muted-gc-audit.json`, SHA256
`fce727bf2a8cbbbdf1bde214ab7523b8d926ad784a60778ede67dd025a043425`.
Independent build peer: `work/socket-built-peer1/acceptance.json`, SHA256
`f9b67fe370ed279c1e32c38ad1a415e57c929295e54d311a8f81e4ddfca6e1ec`.

Preceding original execution: `work/windows-first-frame-resolver1`, source
`f546d51`, includes getaddrinfo/freeaddrinfo/gai_strerror. Its 999-file
snapshot changes libc.cpp and libc.h and adds the resolver detail header;
the other 996 parent files, all 4,653 guest objects and all four generated
headers remain exact. Bootstrap and all 44 host/runtime sources are freshly
compiled against the changed LibC class layout.

The previous getaddrinfo failure does not recur. Native exit 3/controller 1
now stops at missing libunity.so `socket`, PC `7ffc000000e0`, LR `70b4a1b8`,
x0=2 (Android AF_INET), x1=1 (SOCK_STREAM). The protocol argument is unlogged.
Two original renders return continue=true with zero draws; no successful swap,
PNG or first-frame witness exists. All overlay pins and parent pre/post checks
pass. The original process exited and its controller session was collected.
Real game socket connectivity and complete initialization remain unverified.

The next work is a coherent real socket/connected-client path, including
readiness and socket-aware shared descriptor dispatch. An independent socket
namespace would conflict with files, and raw Windows SOCKET values are not
Android int descriptors. Existing file descriptors start at 1000, whereas
Android fd_set has only 1024 bits; socket allocation and select need a
coordinated namespace. Preparation only:
`work/socket-transport-design-preparation1/acceptance.json`, SHA256
`b77ce30c74f8120ce5f00d7bf8a2ef84a85d930a3d4bb9a8df09e25eceed4fa0`.
Actual connected callsites and needed flags are being audited before selection.

The connected-client cohort is implemented and qualified, and is selected in
the latest original-game executable above. SocketTransport adds 23 imports
and shares one descriptor table with FileSystem. Native SOCKET values stay
owned and pinned behind Android int descriptors. Real Winsock TCP/UDP and
address formatting, nonblocking controls, options, endpoint queries, vectored
transfers and mixed readiness are exercised by actual NDK callers. Pipes use
an owned bounded byte queue with real host synchronization and PIPE_BUF
atomicity, rather than claiming a TCP stream has pipe atomicity.

Functional qualification: `work/socket-transport-qualification6/acceptance.json`,
SHA256 `100f7e8857e4163c0d9f53dd02527ca192038bca95836aa5ba2d5dac12e58061`.
It passes 3,913 focused checks and 445 actual NDK entries across 29 APIs and
both call forms, including 324 canonical entries and 124 comparison records.
Real native peers verify bulk TCP and vectored I/O plus blocking and concurrent
pipe transfers. The existing file regressions pass 14,187 duplication/OFD/race
checks and 116 file ABI/stdio/mapping checks. Raw QEMU observations are retained:
six F_GETFL results contain an emulator-injected target-invalid flag. Only
three named Bionic record types remove that proven emulator bit; Windows flags
remain exact. An additional invalid socket-flag case uses primary kernel
evidence instead of reproducing QEMU's dropped-flag error. See
[the transport qualification](socket_transport.md) for precise comparison limits.

The separate network-wait collector gate preserves the existing lifetime,
record and epoch owners while adding a certified socket-provider phase. Its
actual NDK poll waits pass 157 checks across three roles, six genuine GC cycles,
12 original posts and 12 physical GPR31/Q32 root frames, including late-pending
handoff and negative admission controls. Receipt:
`work/socket-wait-collector-qualification2/acceptance.json`, SHA256
`02f9ca52206b5703a0cd8768462ea100ce8b8c5607087328eedbe69f8b5b78cc`.
Three unchanged legacy native processes also pass 350 checks:
`work/socket-collector-regressions1/acceptance.json`, SHA256
`0d711835d0f01c5ad34587feead382af4588f4fddacf8e1eb3f2f39c40774a97`.
The three old collector headers change only by insertions; their previous
branch bytes remain exact. This is not a new standalone native qualification
of the old finalizer-condition profile. Actual socket caller role, protocol,
destination and optional branches still require the next original execution.

Bootstrap now retains its filesystem interceptor by value so worker shutdown
cannot call a destroyed local std::function. Providers and collector owners
outlive Drain. The broken-pipe policy queries the actual guest disposition:
SIG_IGN returns EPIPE, unblocked SIG_DFL terminates with explicit Windows-adapter
status 141, and custom or blocked-default delivery remains an unsupported
diagnostic. Its ten isolated child processes exercise both NDK call forms,
including ignored blocked13, unblocked default termination, MSG_NOSIGNAL,
and unchanged disposition/mask with no queued signal on rejected profiles.
Receipt: `work/socket-sigpipe-qualification5/acceptance.json`, SHA256
`04be97622981c7873fce9be9a81b8cf5453b29a47a66a396bde53addfd32d6ed`.
The combined 12-source proof binds six existing-file inverses and six added
files, all component receipts and the final collector-enabled bootstrap syntax:
`work/socket-source-preparation1/source-proof.json`, SHA256
`225d76f4736d27266f7221247c0f0beb30c01b1890fae0bf3f906886d08b9ba7`.
The selected snapshot has 1005 files (993 unchanged), one new host CPP and fresh
bootstrap/all-45-host compilation. Its full build and original-game execution
are recorded above; no original frame or complete networking is established.

Reproducibility/package work remains open: the canonical preparation/build
scripts still describe the historical guest cohort and omit newer host
providers. The next exploratory controller must explicitly freeze the current
4,653-object cohort and add the new host source. Its success alone will not
establish a portable release build or package.

Overlay SHA256 `ce1fb4c1f02193f86b9d8e0626f0b9e25a5417e8f1048060c251f8f9da2f5e53`;
EXE `d6a86afc537f958bf13866e66810aa1d9721822db8e736bc215d2b23782ffc01`;
bootstrap `de09f6fb08e19862eb6507409f85a6f76170cbd62b7916532091dbc5cb585b9c`;
log `a5c490a42fbb23058dce9c96e99a475416a9734eceea2975b09b88403bb6067b`.
Actual module: PID 62704, base `7ff657a50000`, image size 1,055,219,712.
Built peer: `work/resolver-overlay-preparation1/built-peer-acceptance.json`, SHA256
`844f8bf0ec820d8e63b4c33d97e5260577456e93f925aa489ddccf8934ea66a9`.
Run audit: `work/windows-first-frame-resolver1/game-frame-muted-gc-audit.json`,
SHA256 `c3260a146af99660e10ccc49b3f2717e9f830ac562a0f33bf8024bbd7e75cd30`.

Preceding original execution: `work/windows-first-frame-inet-pton1`, source
`a248584`, includes the qualified numeric address converter. Only libc.cpp
changes among 998 source files; the other 997, all guest objects and all
generated headers remain exact. Bootstrap and all 44 host/runtime sources
are freshly compiled. The actual URL scanner and manual proxy query complete
again, and the previous inet_pton failure does not recur.

Native exit 3/controller 1 now stops at missing libunity.so `getaddrinfo`,
PC `7ffc00000178`, LR `70e16b00`, x0=`1e8936e5d10`, x1=`1e894940f9c`.
The actual hostname, service, hints and output contents are unlogged.
The required next boundary is genuine name/service resolution with Android
LP64 address structures, Windows flag/error mapping and correct result ownership.
Two original renders return continue=true with zero draws; no successful
swap, PNG or first-frame witness exists. All overlay and parent pre/post
checks pass. The root run session was collected to terminal state.

Overlay SHA256 `6bccc12990895589b468c3dd3b0b2a775ed600b889eb71f03d85833690bab6c1`;
EXE `d506c0556fca56fcf0c16f0b0e544e7d986541fc05476505d45cbe7cbed1ebec`;
bootstrap `fa07455a786f41b72add015e1b001551ac42f38c2f30c31c752168859e271a23`;
log `c1232ab5a2054a80ae99f25ec8d1a6e86f234a94553cf6591234f96fa2e4b40d`.
Actual module: PID 24512, base `7ff621e80000`, image size 1,055,191,040.
Built peer: `work/inet-pton-admission-peer1/built-acceptance.json`, SHA256
`3f8f4d8d609597a3bf5e3154b9a92fb26a00bbe9483faa97464e8f3dac8d9a3d`.
Run audit: `work/windows-first-frame-inet-pton1/game-frame-muted-gc-audit.json`,
SHA256 `10fabeb3b6677b924b9a2010bec8272c1396423ebbba1f17a1af2060adbf5a72`.

The real resolver family is now implemented and qualified: getaddrinfo,
freeaddrinfo and gai_strerror. Windows uses checked Winsock startup and the
native resolver, with owned Android-layout chains, explicit family/flag/error
conversion and native-list cleanup. Valid suffix release and cross-thread
freeing are supported. The qualification passes 2,100 checks and 304 actual
NDK calls: 272 differential calls plus 32 concurrent calls. Complete sorted
chain/status/canonical/error-string records, failure errno and free errno
match actual static Bionic. Only unspecified successful-result errno is
normalized; the raw logs retain the one first-strdup errno 22 versus 0
observation and isolated probes. No warmup or synthetic errno was added.
Real Windows localhost resolution is checked separately; external DNS,
socket connectivity and actual game networking remain unverified.
Qualification: `work/libc-getaddrinfo-qualification3/acceptance.json`, SHA256
`e3efad6f2b0b36389fa3cae45303353a6b3cc509b06aa0d911496e6609785f9a`.
Source inverses/append-only imports and added header:
`work/resolver-source-preparation1/source-proof.json`, SHA256
`755e7d082b8a29fe9f467d95bbc88a55f8e7e8b8985e0ba61dcefa76bec34998`.
The full resolver host build and original-game execution are recorded above.
Original-callsite audit: `work/inet-pton1-getaddrinfo-boundary1/acceptance.json`,
SHA256 `0c5c28e3cf2f6fb53c5af2031a46cc181083240fafd5a12b31def2d9edc7c021`.
The reached wrapper reads the qualified 48-byte Bionic layout, copies usable
IPv4 results into its own allocations, then calls freeaddrinfo. Static callers
do not establish the latest execution's unlogged hostname or hints values.

The user restarted Windows before this build. The boot changed to
2026-11-05 10:07:52 +05:30 and available RAM recovered to about 44 GiB;
it remained above 38 GiB during compilation. Read-only receipt:
`work/memory-cleanup-20261105-1/after-restart.json`, SHA256
`f1f7a6dfe52cd571b452c20a4569e9aa175eab53723dfe2c3ae096519a49d333`.
No Windows service, audio setting or user application was changed.

Preceding original execution: `work/windows-first-frame-sscanf1`, source
`dd11a78`, includes the qualified scanner and six-GP bridge. Its 998-file
snapshot changes libc.cpp, libc.h and bootstrap; the other 995 files and all
guest objects, trace heads and metadata headers remain exact. Bootstrap and
all 44 host/runtime sources are freshly compiled.

The original URL parser now returns normal scanf assignment counts: two at
LR `70b624b4`, three at `70b625a0`, and zero at `70b630f8`. The HTTPS proxy
query also completes with null manual properties and unresolved automatic
configuration. No input URL or character-buffer contents are logged.

Native exit 3/controller 1 stops at missing import `inet_pton` in libunity.so,
PC `7ffc000000f0`, LR `70b4b574`, x0=2 (Android AF_INET),
x1=`2778ad8b890`. The next work is real IPv4/IPv6 text-to-binary conversion,
with exact status, address-family, errno and output semantics. No network
request is needed to implement this conversion. Two original renders return
continue=true without draws; no successful swap, PNG or first-frame witness
exists. All overlay and parent pre/post checks pass.

Overlay SHA256 `81c3f665efd4f36524ef4825c94478714be3cb31d4f8a4056cf81cd722906875`;
EXE `84670b7fd400a94b4b0180fcf86fad15b7ca6493760b5dc956ce1f257aa73f99`;
bootstrap `fa07455a786f41b72add015e1b001551ac42f38c2f30c31c752168859e271a23`;
log `5414397834884903b445f3a38afb513d6d0ec71eb8081b6367c61211c04e304a`.
Actual module: PID 2713104, base `7ff6bff70000`, image size 1,055,186,944.
Run peer: `work/sscanf1-run-peer1/acceptance.json`, SHA256
`9f5de0677030969a064f64e268a46816b0be26876e4e91d540951c459862eb35`.

The real address-conversion adapter now passes 1,344 Windows checks and 190
genuine NDK calls, with all complete status/errno/output records matching
actual static Bionic. IPv4 decimal leading zeroes are normalized, preserving
the original four-character limit on the first IPv6 dotted-tail component.
Windows maps Android AF_INET6=10 to its native 23; output is staged and only
four or sixteen network-order bytes are published after successful conversion.
There is no DNS, socket startup or network request. Qualification:
`work/libc-inet-pton-qualification2/acceptance.json`, SHA256
`f1cc2ed3f046fbef0e8b15243180da22484fc822da5ceda8c11a5eb13a06df69`.
Source inverse/unchanged header/import-ordinal proof:
`work/inet-pton-source-preparation1/source-proof.json`, SHA256
`7904761ac914e0beaf6f729bfa4c41da7a57ef6aefef8ce6f5dfff48ca36881d`.
The full host build and original-game run are recorded above. At the user's
request, host memory cleanup preceded that build: idle WSL was shut down and a signed
RAMMap capture saved under `work/memory-cleanup-20261105-1`. It records about
20.4 GiB of page tables and 22.4 GiB of active unclassified pages. No application
or network service was terminated, and no original game/compiler remains live.

Preceding original execution: `work/windows-first-frame-sched-yield1`, source
`62b3992`, adds the qualified real scheduler-yield binding. Its 998-file
snapshot changes only libc.cpp; the other 997 files, all headers, guest objects
and trace heads remain exact. Bootstrap and all 44 host/runtime sources are
freshly compiled. The unchanged bootstrap produces the same object hash.

The original game now calls the proxy adapter: HTTPS, reader used, no manual
host, Java null result, autoDetect=true, explicit PAC URL absent. This is a
manual-property result, not a resolved direct route. The previous missing
proxy-method dispatch does not recur. The run stops at bootstrap's narrow
sscanf adapter: LR `70b624b4`, format outside its sole `%llu` profile. Two
original renders return continue=true without draws; there is no successful
swap, PNG or first-frame witness. Overlay and parent pre/post checks pass.

The exact first format at the original callsite is `%15[^:]:%[^\n]`, with
two char-buffer outputs. It belongs to URL/scheme parsing. The actual input
URL is unobserved. The next work is correct scanset/character conversion and
matching variadic argument/output handling; the existing uint64-only bridge
and audit must both change, rather than treating these buffers as integers.
The same original function contains three additional URL/IPv6 scan profiles;
their exact formats, output ABI and buffer provenance are sealed in
`work/sched-yield1-sscanf-boundary1/acceptance.json`, SHA256
`62e95990002c9e28e210c528277844bba65bdbccefeefad87546296b3a36a7d2`.

The scanner and bootstrap bridge now implement all four audited string formats
while retaining the existing `%llu` conversion. The Windows qualification
passes 387 checks and 51 genuine NDK calls; all 51 complete output/status/errno
records match actual static Bionic byte for byte. Native scanning uses owned
temporary buffers and checked, sequential publication of assigned outputs.
The six-GP bridge handles all four possible output pointers; the character
audit logs escaped formats/counts without reading outputs as integers.
Qualification: `work/libc-scan-profiles-qualification3/acceptance.json`, SHA256
`7e10534c3ebd9a92eeb400f1b311637092409dab38d4ba1783e14f8829d8c57b`.
Integration/source inverses: `work/sscanf-integration1/proof.json`, SHA256
`688f0457b05e5a0cace2413b2721d77e4cc8ed023d137aaae0ed4d7cbeb5b80c`.
Q1's invalid-input fixture assumption and canceled Q2 remain preserved;
valid readable C input/format strings are required. The latest original-game
run executes the scanner profiles before reaching the inet_pton boundary.

Overlay SHA256 `9176b71822793a8d6a44e70e44ff5bd9e332db3c8a46282f97a34202f5ff9f04`;
EXE `8e7dac13b19d5c45b37e10b74ed193f300d5cf60b9406e83f191e0fc124c2995`;
log `257bc10c2ebd4a879c59d3594257efac6a201fa873e70928bfc6a73202906e88`.
Actual module: PID 2694608, base `7ff7a1d10000`, image size 1,055,162,368.
Run peer: `work/sched-yield1-run-peer1/acceptance.json`, SHA256
`4e266258df4c6d96c70ca7fcf8a427e1342de1c3b51cd57f6da2126cb694611d`.

Preceding original execution: `work/windows-first-frame-network-proxy1`, source
`6277fe4`, includes the qualified manual-proxy adapter and JNI 1.1 rejection.
Bootstrap and all 44 host/runtime sources are freshly compiled against one
998-file snapshot: bootstrap and loader version policy change, two proxy
sources are added, and the other 994 parent files remain exact. All 4,653 guest
objects, 595,408 trace heads and metadata headers are unchanged.

Native exit 3/controller 1 now stops at unsupported import `sched_yield` in
libil2cpp.so, PC `7ffc00000358`, LR `825a720c`, x0=0,
x1=`155c97f9a94`. Two original renders return continue=true without draws;
there is no successful swap, PNG or first-frame witness. The run makes no
proxy-method call before stopping, so it does not establish that the preceding
proxy boundary has been cleared. All overlay and parent pre/post checks pass.
The next work is genuine host scheduler-yield support, preserving guest errno
and the caller's native environment.

Overlay SHA256 `5257bdda6b5c69cabbce77def06b61c487521ce29bddb366d905995d4e040c34`;
EXE `701032fee96bd94e6f54ffc589ea09ee0b383fad5dec5c03aba47057bdacaee2`;
bootstrap object `51e259ad576303fd8f83be30ad274fb017c46ce17048c8abefa919db38029cc7`;
log `0b13b44056a7c5e18d5bf8e6c24b3bef47ae4e96a19049bf7103b4a20e7aec08`.
Actual module: PID 2686744, base `7ff6b3210000`, image size 1,055,162,368.
Run peer: `work/network-proxy1-run-peer1/acceptance.json`, SHA256
`2ba2219c4e9077d7349edc02ad38f7168dbbbcc06fdad4837ae3d4069c248758`.

The scheduler binding now passes 436 Windows checks and 48 translated NDK
calls on the main thread and two native workers. The same NDK caller object
also makes 16 successful calls through actual static Bionic under QEMU.
Windows calls SwitchToThread once; Linux uses native sched_yield. Success
preserves guest errno, and the callback preserves native errno, LastError
and floating state. No sleep, fairness or forced context-switch claim is made.
Qualification: `work/libc-sched-yield-qualification1/acceptance.json`, SHA256
`6872178a0f7cfcb3f67023e9e31cba0a8afbb8ed1d63fabb886c59d6403f8aed`.
Exact source inverse/import-ordinal proof:
`work/sched-yield-source-preparation1/source-proof.json`, SHA256
`0b484657e1ad20cabae628c54d40696a2a254bd85de34fac0e3edb183791ca5c`.
It is included in the latest original-game execution described above.

Preceding original execution: `work/windows-first-frame-java-string-loader1`,
source `2b8477c`, builds String byte/charset construction and encoding plus
the closed Java native-library loader. Its 996-file snapshot has five changed
parent files, three additions and 988 unchanged source files. Bootstrap and
all 43 host/runtime source files are freshly compiled; the same 4,653 guest
objects, 595,408 trace heads and metadata headers remain selected.

The String-constructor and loadLibrary dispatch failures do not recur.
Bootstrap's original Unity JNI_OnLoad returns `0x10006` once; the loader
adopts that completed load without reopening or replaying it. The actual
subsequent request is `FirebaseCppApp-9_6_0`, which returns false because it
is outside the registered translated catalog. That library is present in
the frozen APK: 5,502,344 bytes, SHA256
`b233de431376efde3ba16be810e4d63c65f9be98d0285c4f330d8b0bb0332ce1`,
JNI_OnLoad RVA `16011c`, 8,468 FDEs. This is an untranslated dependency,
not evidence of a missing APK file; it is not the recorded fatal boundary.
Inventory: `work/firebase-native-boundary1/acceptance.json`, SHA256
`09412cca74538d8a05017a160380b16c38e87b38395abf1ea03f2239c912c057`.

Native exit 3/controller 1 stops at Env slot 35, missing instance method
`UnityPlayer.getNetworkProxySettings(Ljava/lang/String;)Ljava/lang/String;`.
The diagnostic at log line 19247 captures PC `7ff000000118`, LR `7040efa8`,
SP `2a391820a30`, x1 `7ff100000051`, x2 `7ff200000160`,
x3 `2a391820ae0`, x4 `17a`, pendingBefore=0. Later EGL output is another
thread's interleaved/inflight tail, not the fatal cause. Three renders enter,
two return continue=true, and there are zero draws, clears, swaps, PNGs or
first-frame witnesses. All overlay pin checks and parent pre/post checks pass.

Actual module snapshot: PID 2660276, base `7ff786910000`,
image size 1,055,125,504 bytes. Overlay SHA256
`b4a1135732548721ca235cd79b8a4c288af936fa1725fed5ef6a7e4b24aa198f`;
EXE SHA256 `372d222b9d8c6552ca6b20330b41d8e749f3f5e5aca21a85342281e82d87b9cf`;
log SHA256 `29d523240260767a413a32d443324c6f73ba5eeb29a94e992c02da8cfc09ead2`.
Run peer: `work/java-string-loader1-run-peer1/peer.json`, SHA256
`cac8f44b0f7ae8a9845c20677c9e9343efafae5dda6acadd888449703152eafe`.
The specific `java_string_loader_host_revision` identifies current code;
inherited revision fields explicitly describe historical parent layers.

The next method is pure property formatting: case-sensitive `http:`/`https:`,
their proxyHost/proxyPort, and raw `http.nonProxyHosts` for both. Missing or
empty host returns Java null; otherwise the result is host, optional colon
and port, then optional newline and bypass string. It does no URL-host parsing,
bypass matching or PAC resolution. The current URL is unobserved. Windows has
no explicit manual proxy but auto-detection is enabled: that does not prove
an effective direct route. Implement the property's real data source and
formatting without an unconditional null or invented PAC result.
Audit: `work/java-string-loader1-proxy-boundary1/acceptance.json`, SHA256
`f77a58c170ea58530dc9b0da59bf7710c6518bbb1a18f03be8ffcd8730e4643e`.

The manual-property adapter and bootstrap binding are now implemented. The
focused Windows qualification passes 789 checks and 151 genuine translated
NDK calls across direct/V/A JNI forms, with nine traces, one object and no
unsupported or unresolved targets. It independently compares the live manual
settings and automatic-configuration metadata to WinHTTP; no network request
or automatic proxy resolution occurs. Qualification:
`work/unity-network-proxy-qualification3/acceptance.json`, SHA256
`140eb112eed1346d26891262063001cf98c85d8f57fa0ef16db5f2f6ffee291a`.
Q1's path-conversion and Q2's repeated fixture-mapping failures are preserved;
Q3 fixes only the harness. The provider uses real Windows manual settings,
preserves the DEX null/empty distinction and fails explicitly on unsupported
manual configuration forms. The bootstrap binding outlives worker draining
and installs before initJni. Integration proof:
`work/network-proxy-integration1/proof.json`, SHA256
`44532ffde0dfa5301048e71a9f6c24c97bd25cf5d684e09fa3811e395bafdb94`.
The new executable includes it, but its run stops before the first proxy call.

After this run, source `7f18d15` corrects the loader's version predicate to
reject JNI 1.1 as ART does. Fresh Windows/Linux NDK tests verify the 1.1
failure cache and adoption rejection; Unity's observed 1.6 is unaffected.
This correction is absent from java-string-loader1 and included in
network-proxy1. Qualification:
`work/java-native-loader-qualification2/acceptance.json`, SHA256
`3ef616702480fa7ef7f9e930169f201135c6aeca178f4e2e1da49d530696ccc4`.

For subsequent edits, mutable workspace inputs referenced by the completed
manifest were copied byte-exact after successful postverification and before
editing. `work/java-string-loader1-frozen-workspace-inputs1/relocation.json`
(SHA256 `cb54e8431f4cd17cc531624857c64ac99078d36198016104c1b80ac6d69f9409`)
records 11 unchanged path/hash/byte relocations. Future child verification
must verify those immutable copies, not weaken hashes or rewrite this run.

Preceding original execution: `work/windows-first-frame-jni-byte-array1`, source
commit `e348a02`, recompiles bootstrap and all 42 host/runtime sources against
the new JNI Host header. Its 993-file snapshot changes only JNI cpp/header
and the failure-only bootstrap diagnostic; the other 990 source files, all
4,653 guest objects, 595,408 trace heads and metadata headers remain exact.
The selected bootstrap is the newly compiled object, SHA256
`2cf99b9f3f6c765112a71addc34ce12a172c36c5937cb710fc30215ec957958e`.

Native exit 3/controller 1 now reaches a constructor lookup error
`<init>([BLjava/lang/String;)V` at Env slot 33, return `70ab5d38`, then stops
at Env slot 38: missing host implementation of instance
`com/unity3d/player/UnityPlayer.loadLibrary(Ljava/lang/String;)Z`.
The failure diagnostic captures PC `7ff000000130`, LR `70410910`,
SP `23639370100`, x1 `7ff10000004b`, x2 `7ff200000169`,
x3 `236393701b0`, x4 `17a`, pendingBefore=1. The requested library name is
not observed, and this is not evidence of a failed native library load.
The preceding `android.util.Log` lookup failure also remains.

Three renders enter and two return continue=true; there are zero draws,
clears, successful presentations, PNGs or first-frame witnesses. Parent
pre/post verification and all overlay pins pass. The module observer records
PID 2641144, actual base `7ff612b10000`, image size 1,055,068,160 bytes.
Overlay SHA256 `57a0fafc5da0f8cdd09fa21d5c06ef314c4f9fd96c6f435b2ff2635249396ba4`;
executable SHA256 `9fec88180d8605cefd32be581b0aa4ddc4d70dee2f784ef69fcfd8ab95dce7c8`;
log SHA256 `4c78e13a185bc3825198dd90f06a24689d3d3d1231dda60a463927d99928d472`.
Run peer: `work/jni-byte-array1-run-peer1/peer.json`, SHA256
`7569748245c367ed8c0706427179c0b5f442033396fbc951220b695d1797e432`.
There is no direct return log for the six byte-array APIs in this game run;
their successful component tests do not prove each original call executed.

The next work is the real byte-array/charset String constructor and native
library loading. Seven direct callers of native constructor wrapper
`70ad4060` statically supply `UTF-8`; this does not identify the live failing
caller or its charset. The byte builder copies an explicit length, preserving
embedded NUL. The existing generic constructor factory rejects a String-kind
result, so adding a declaration alone would still fail. JDK 24 is installed
for a real reference profile; malformed input behavior must not be claimed
as ART equivalence. String audit:
`work/jni-byte-array1-string-boundary1/acceptance.json`, SHA256
`fd2bc77d0eef777f7b278556368e166df8965ee26e47fe4ba3806957ae812b54`.

The original DEX loadLibrary wrapper returns true only after
System.loadLibrary succeeds; native module constructors alone are insufficient.
It needs Java loader ownership, cached JNI_OnLoad results and adoption of the
Unity JNI_OnLoad already executed by bootstrap, so that entry is not replayed.
See `work/jni-byte-array1-native-library-boundary1/acceptance.json`, SHA256
`78d821624d258baea4db09d3d6578d26362c414dccb8f3016f7da829c0d48dd9`.

Preceding original execution: `work/windows-first-frame-clock1` includes the
qualified `clock_getres` provider for native realtime and monotonic clocks.
All 4,653 guest objects, 595,408 trace heads and compiled bootstrap remain
unchanged. Native exit 3/controller 1 now stops at unsupported JNIEnv slot
176, after a pending `android.util.Log` ClassNotFoundException reported at
Env slot 13, return `70ab524c`. Two renders return continue=true; there is
no successful presentation, first-frame witness or PNG. The later frontier
does not directly trace the clock query's return value.

Parent pre/post verification and all overlay pin checks pass. The read-only
observer captured PID 2621080, actual image base `7ff657980000` and image
size 1,055,059,968 bytes. Overlay SHA256
`15853dd7e5927263cec89dca65eefdcb01320dc40736d93339fd6017f0e0e6fa`;
executable SHA256 `17f6bf2fcac142dcbfd863b82d653ea5cde999c12c992b348af964e26ed225d7`;
log SHA256 `296313d46db15dd1e9cbb065315b96c54276a08ad9ec3eb7daf51b99520115ec`.
Run peer: `work/clock1-run-peer1/peer.json`, SHA256
`f954a9f3e0adca7251cac9549ac94e32963080e788abc5cdea7f76283193b4ed`.
It confirms zero draw/clear/swap submissions and no clock-return log.

The [clock provider](pthread_clock.md) passes 66 actual translated NDK calls
and 12 calls against actual static Bionic under QEMU. Its first Windows test
caught a native LastError preservation bug before current-thread lookup;
the new import now preserves the complete callback boundary. Existing thread
and clock-sampling methods remain unchanged. Qualification:
`work/pthread-clock-qualification2/acceptance.json`, SHA256
`942155e2ac5c7c7036a4eecb2f912487d03b13d8e1cdd72101dcd4775a3b6408`.
The reached JNI byte-array family is now implemented in source commit
`e348a02`. Slots 171/176/184/192/200/208 pass 132 actual NDK caller invocations
on each of Windows and Linux, including copy/commit/abort, tracked retirement,
reference ownership, primitive/reference-array identity and State/Memory ABI
checks. These are host component checks, not an ART runtime comparison or an
original frame. See [the JNI byte-array contract](jni_byte_array.md).
Qualification: `work/jni-byte-array-qualification2/acceptance.json`, SHA256
`02e9a49e53b996fc4923cdeeb82d18a05901297f2c3f2c16e8500b09a1eb5dbf`.

The new dedicated lease map changes the Host class layout. The next executable
must recompile bootstrap and all 42 host/runtime source files against one new
header snapshot; retaining the old bootstrap object would be invalid. The
original 4,653 guest objects and trace/metadata headers stay unchanged. The
bootstrap also gains failure-only JNI PC/LR/SP/argument diagnostics because
the last slot-176 error omitted the actual caller and requested length.
That consistent rebuild and original startup are recorded above. The missing
Java constructor/library behavior is the next boundary; no preceding class
lookup or library load is treated as successful without implementation.

Preceding original execution: `work/windows-first-frame-calendar1` includes the
qualified eight-API calendar provider, preserving all 4,653 guest objects,
595,408 trace heads and the compiled bootstrap. Native exit 3/controller 1
now stops at missing `clock_getres` in libil2cpp, PC `7ffc000005a0`,
LR `8255441c`, clock ID 1 (`CLOCK_MONOTONIC`), output `879a5588`.
Three renders enter and two return continue=true; there are no original
draws, clears, successful presentations, first-frame witness or PNG.
Parent pre/post verification and every overlay pin recheck pass. A read-only
observer captured PID 2609892, actual image base `7ff77f250000` and image
size 1,055,055,872 bytes. The log does not directly record calendar returns;
the later frontier does not establish execution of every calendar API.

Overlay SHA256 `b549ddd070222a30fc5d1a7b25e106eef09839b819d2fbf5c1fd91c0262bf963`;
executable SHA256 `de61c6428368b045b680b9da0ad097065101e9a7205829385fe123b05983a52b`;
log SHA256 `50821a670b2c8318cc8f27c4a04f81a9bd73eda764aa9d874b73a917d5d1389b`.
Run peer: `work/calendar1-run-peer1/peer.json`, SHA256
`c73ee0811ffe9c12924be2f69f98eece4d5b85833b403fc79e69522a1d25af34`.
The next step is the matching clock-resolution provider and another original
startup attempt after its focused ABI and error-path checks.

Preceding original execution: `work/windows-first-frame-uname-indirect1` appends
the complete four-entry computed-table group, retaining all4652 prior guest
objects and rebuilding unchanged bootstrap source against595408 sorted trace
heads. Native exit3/controller1 now stops at missing `mktime` in libil2cpp,
PC `7ffc00000480`, LR `82556df0`, input pointer `1f42b920178`. Two renders
return continue=true; there is no draw, presentation, witness or PNG. Parent
pre/post verification and all overlay pin checks pass. No direct trace of
each new entry or the `uname` return was captured. The observed process
exited before the external module-base query; no actual base is inferred.

Overlay SHA256 `bd4182d36e63a265501e8b5862e6f0815a0b356eee1cb5d4c3e819b35632fb01`;
executable SHA256 `6417a5098fcee963eafbed3783b53b9c3f42414c04a64adf68e23ba67c8c8d02`;
log SHA256 `bca37ddaa884ee6fb0609ab7d77dae2e6d40fe9b66bb41d07929951838bac42b`.
See [the computed-entry gate](../whole/il2cpp_computed_entries.md).

The reached caller `82556d90..82557138` discovers timezone rules using
`mktime`, `time`, `localtime`, `gmtime`, `difftime` and `strftime("%Z")`;
the original Unity imports also require the two reentrant variants.
The group needs Bionic's56-byte `tm`, signed64 timestamps, consistent DST
normalization and real host timezone data. A Windows CRT-only `mktime`
wrapper rejects valid negative epochs required by the caller. The calendar
family now passes96 Bionic conversion comparisons,100 formatting comparisons
and26 actual translated NDK calls. Original startup now reaches the later
clock-resolution boundary described above;
see [the calendar qualification](libc_calendar.md). Boundary audit SHA256
`1d19eed3c9e49e2bc1457e4e9263d202e7104efb5b5433a7b9526f0fe0adff8b`.

Preceding original execution: `work/windows-first-frame-uname1`, source patch
`15f6b158864cc740c6993b181ef15d41f597d496`, includes the qualified Windows
`uname` provider. Native exit3/controller1 reaches unresolved indirect
target `83f373c4`, StatePC equal to that target, LR `83f37378`, and
SP `24ebde30290`. Two original renders return continue=true; there is no
draw, clear, successful presentation, first-frame witness or PNG. Parent
pre/post verification and every overlay pin recheck pass. The log contains
no direct observation of the `uname` return.

Overlay SHA256 `1705a37df835e42b545ae8a4e2ad7e3589996991863550260f5e44049161ac2f`;
executable SHA256 `38e20d80a87794b2fd80c95f2e1b3fdec7266d72dff8e4ab9c10ea56e89952a7`;
log SHA256 `736f11e2a52bea832745967224dabd0c5caeb720b852b40b20ec2398958b5d5bb79`.
Terminal peer SHA256
`19e8b81ea347ba086bb2a7b4e6b49fe8703042f53446ee9de186b5c4f89cf862`.

The original FDE `83f372b8..83f374cc` has two bounded four-entry signed-offset
jump tables. Its first table, `85a84938`, is guarded by `(W26-1)<=3` and
dispatches at `83f373a4`. All four case heads are absent:
`83f373a8`, `83f373bc`, `83f373c4`, `83f3745c`. The second table's four heads
already exist. Selected raw/polled/optimized IR stores the computed target
and correctly calls `__remill_jump`; this is missing entry coverage, rather
than a lost return. The next integration adds the complete missing group.
Audit: `work/uname1-indirect-boundary1/acceptance.json`, SHA256
`2575e245ed586caba98838dc16169a54c54f2c3fec612531996c2dfef18142df`.

Preceding original execution: `work/windows-first-frame-numeric-minmax1` uses an
explicit sparse diagnostic overlay over host
`4b08f113d6d694dfabccbd7f2db276cf8dad30b8`. One qualified function replaces
`709a1280` in object343; all127 neighboring native function projections and
the other4651 guest objects are preserved. The final link changes only that
object token and the output executable path. The unchanged runtime source
is recompiled with the original frozen compiler flags. This overlay does
not claim new production v17/v18 admission; its retained903 header count is
a conservative upper bound on902 actual remaining unsupported heads.

Native exit3/controller1 now stops at missing `uname` in libil2cpp,
PC `7ffc000005f0`, LR `825520f0`. Two original renders return continue=true;
there is no draw, successful swap, first-frame witness or PNG. Parent
verification passes before/after, and all overlay pins reverify. The new
frontier differs from the preceding run; no direct dynamic observation of
the repaired instruction's PC is claimed.

Overlay SHA256 `238fc27780c871885511bf6682089f4ee47b8d35795dbbb718d5f87236f65311`;
executable SHA256 `13152b76ba8c2a1d94eb810b3878760c13b9c936dd464c5ae28f7ad53a4b9cc0`;
log SHA256 `a2e8dbcc26d57608525183e072bc9849ab24f0ad6f49207f21397610b5d5bb79`.
The20-check terminal peer passes, SHA256
`6ec09e1f9b9f229ed7b91293f00357b99e27266d4ce9ecd1c8b16edd8abe87ae`.
See [the numeric minimum/maximum gate](../whole/fp_numeric_minmax.md).
The reached system-information query now has a qualified implementation
using actual Windows host facts and the original Bionic output ABI. Its
219-check Windows gate executes24 NDK calls and eight layout checks;
the next step is the original game integration run. See
[the uname gate](libc_uname.md).

Preceding original execution: `work/windows-first-frame-guest-transfer1`, host
`4b08f113d6d694dfabccbd7f2db276cf8dad30b8`, uses the complete freshly
compiled guest-transfer cohort. Native startup reaches original OpenGL
texture creation and uploads, then exits3 at an unliftable-instruction
report at `709a12c4`. Two original `nativeRender` calls return continue=true;
there is no successful presentation, first-frame witness or PNG. All frozen
inputs and selected original objects reverify after execution. The next
step is translating the original `FMINNM S0,S0,S1` at `709a12c0`
(bytes `0078211e`). In the selected function `709a1280`, the invalid-instruction
path advances PC before reporting the error; `709a12c4` is the following
instruction, which was not executed. The owning FDE ends at `709a12ec`.
Raw, polled and optimized IR plus selected object343 establish this boundary:
`work/first-frame-guest-transfer-frontier1/acceptance.json`, SHA256
`d9a42f9b7ea1a9dca1789f1c04c4130a1373943af7eded2651edd83c3b1cba0c`.

Inputs SHA256 `6bab47988c2023ed73fae9430cba3b796d1b0805d0e7cf0f02ac4905a6828006`;
executable SHA256 `eaf86037272300df2bde1b59207d65ae088d36e9cf5512b07bd79a28c298943c`;
log SHA256 `5eb5fab0286035ed2d031376199ac9fbbfd62f866221e1730a7da06828531420`.
The controller exits1 and preserves the failed attempt without retry.
The terminal peer passes26 checks, SHA256
`6a981c01c2e09abd15a6ff6ddc58d8e6f7f8a021cd63108354ff4a57386f93d4`.
The actual Raise return again selects `83f4275c` and restores SP by0x100;
the log does not directly observe catch dispatch or completion.

Preceding original execution: `work/windows-first-frame-raise1`, host
`64a5ba3bda612c56953c51cf1f1cbfd6bb0d6b5f`, confirms the EH-return failure.
Original Raise enters with LR `8260d5a0`, SP `1e559d70780`, X21/header
`1e811ca2a80`, and unwind object `1e811ca2ae0`. It returns with StatePC/X30
`83f4275c`, SP `1e559d70880`, and X21 `8799a000`. The same original header
remains initialized before/after: exception class `434c4e47432b2b00`, typeinfo
`87205830`, bounded name `22Il2CppExceptionWrapper`, and terminate handler
`82610b88`. The host caller then incorrectly enters its failure continuation,
using restored X21 as a header, and reaches the same null-target abort.
This establishes destination loss rather than corruption of the original
exception record. In that build, landing pad `83f4275c` is absent from the
compiled trace table; its original LSDA identifies an actual catch path.

The complete original EH metadata audit finds 138,657 absent landing-pad heads
(496 Unity, 138,161 IL2CPP), with zero encoding/coverage errors across all
435,292 FDEs and 213,718 callsite rows. Adding them to the current selection
would produce 595,390 heads. The call-lowering correction must run before
Remill's guest-function inliner; cached raw IR already contains guest inlining.
The tested runtime correction and pre-inliner pass are now in `whole/runtime.*`
and `whole/GuestCallLowering.*`. Actual AArch64 rewritten-RET cases match on
Windows/Linux (eight cases, 520 checks each); six genuine C++ EH cases match
the ARM reference on both hosts, raw and polled (24 executions). These execute
original C++ ABI, personality, unwind, and emutls code. Unsupported cold paths
and ordinary platform boundaries remain explicit in the fixture receipts.
The repository runtime unit runner passes both hosts (15 cases, 220 checks,
seven fail-closed controls each).

The complete fresh rebuild is now statically admitted. Optimized-IR guard checks
now account for compiler call merging and private native shadow-slot cleanup;
native callback counts are telemetry under the qualified LLVM backend.
An earlier stopped build exposed nine missing direct-call targets in Unity
function `705b985c`. All nine are original executable helpers without symbols
or FDE coverage. The 595,390-head metadata union needed a reachable
direct-call closure pass before another complete native build. Failed builds
and completed shards remain preserved.
That architectural preflight now passes across 16,497,957 original
instructions, with zero invalid decodes, unknown controls or out-of-executable
edges. It adds the nine Unity helpers and five IL2CPP import stubs, producing
595,404 heads in 4,652 objects. The focused native build of all 14 additions
and the previous 128-head failing batch passes its direct-reference and
optimized-IR guard checks. The full fresh build `work/guest-eh-candidate5`
completed all 4,652 objects, controlled by `work/guest-eh-rebuild-preparation10`.
Its complete inventory and Windows-readable object copies pass static admission
in `work/first-frame-guest-transfer-cohort1`, SHA256
`d832d715b89815bcbe3052c6ab4ded47a0951ecb47f3f1d60d79572c0348aab6`.
There are 903 traces with explicit unsupported paths (866 Unity, 37 IL2CPP);
the startup landing pad `83f4275c` has none. The v17 Python and PowerShell
guards pass 17 actual positive versions and 34 rejection cases each, and the
complete current host passes the static default/collector syntax gates.
Freezing and linking this Windows game build subsequently pass; its original
execution is recorded above.
The host now interposes the explicit call facade for the original automatic
save helper. Its caller and helper share one new object, where the older
callee-symbol wrap misses the local reference. The Windows host fixture
reproduces that bypass, then checks same-object, cross-object and dynamic
routing through the unchanged ownership helper, live nonlocal registration
and revocation, all State/token bytes and native environment forwarding.
The adapter passes 91 checks; the complete host's default and collector
source/syntax gates also pass. Qualification:
`work/guest-call-routing-qualification1`, SHA256
`6bd1f85fd5c507131ed1b89f34e16a281c299544d6c2073e1efca2330ab6f195`.
The promoted runtime also passes the original Windows collector regression
(three processes, 350 checks, six stop/restart cycles). The static source
gate admits this exact runtime pair through its pinned runtime and collector
qualifications while retaining the historical diagnostic-source checks.
The latest run selects this corrected game cohort and landing-pad code.
No original draw, successful swap or PNG is observed. Real C++ EH receipt:
`work/guest-eh-reference-translation1/qualification1`, SHA256
`897837d9ab05d50e517820e59e55d96590806cb8af72cfe29a93d2eeed5d68f2`.

Inputs SHA256 `97c6546a5b9e8d3db41490f823c84c8b29fcd72ea45c45f48e67d9bff6bfab20`;
executable SHA256 `14adf7d0ce6e67111029c31b6bf60d8691049a82f843e1308e86a265a92821ab`;
log SHA256 `eb591c8a56c593b0e6a249db9f5f5c7d456787ee357383779eb95b17ce2c9b68`.
Native exit3/controller1; posthashes match. Terminal peer SHA256
`2100124edde2b1ee4cafb27d754d189b139ba3bb2bd4ab9a2225cecd55f73b18`.
Landing-pad audit SHA256
`4912d35b0a18d32ca899753feb58c7cc8f21616facafab0ba3331b5f6d5746b5`.

Preceding original execution: `work/windows-first-frame-exception1`, host
`af73a50918170e995488850bada1d9c12e7c5626`, captures the same null-target
failure without changing the translated objects or continuing past it.
The live GOT entry `87408e50` contains `87985200`, whose handler is correctly
`82610b88`. The exact original wrapper frame saves caller LR `8260d628`,
followed by `8260d5a8`, `8457a074`, and `8250bf3c`. This identifies the path
through the failed-raise helper `8260d608`, rather than the global fallback.
X19 and X8 both contain `8799a000`; two bounded 128-byte reads there return
all zero words. RTTI is unreadable at0, so no exception type is established.
Why the exception-record area is zero remains under investigation.

The native/IR audit finds a concrete exception-transfer gap: successful
`_Unwind_RaiseException` can restore catch-frame registers and rewrite its
guest RET destination to a landing pad. `__remill_function_return` simply
returns its memory token to the host caller, whose lifted throw then enters
the post-call failure helper unconditionally. Consequently the observed X21
may be a restored caller register rather than the original exception header.
`8799a000` also matches an original managed caller's BSS page; the emergency
exception arena is elsewhere. This run has not yet measured the actual Raise
entry/return PC or success branch. The next diagnostic must capture those
values and the original header before/after, preserving the current failure.
Audit: `work/exception1-zero-header-boundary1`, SHA256
`ed163a817b30c883b20b01e5c7427aa426686d14fadf4062535ee884eade1667`.

Main epoch6 and four worker collector cycles complete; two renders return
continue=true. There is no original draw, clear, swap, PNG or soft-input native
report. Native exit3/controller1 and posthash verification match.
Inputs SHA256 `80cf214c7660c0881b2b202c381f5913360eb37f2756e1c40d37f61e49f31f46`;
executable SHA256 `723df4a6f82ae004fe8f57b72172587bcd02db5874d355f3093546ec59aa52b0`;
log SHA256 `0231673635785be16582597c6da0f740b9b1ff654340ff55e4d487b94999e46b`.
Terminal peer: `work/exception1-run-peer1`, SHA256
`f954914cc3e8261059d63fe14c6ce0f71e80d1a106c5d2ccd14b25195bdce477`.
The terminal observer passes 40 Windows checks over three TEST snapshots;
these prove read-only state/environment preservation and fault-safe bounded
reads, not original exception handling or a rendered game frame.

Preceding original execution: `work/windows-first-frame-unwind1`, host
`28bbc4fb706b31168f990299a544676410ce6cdb`, gets past the missing unwind
target with the appended object. Twelve original program-header callbacks
complete. Execution stops at indirect target0, StatePC0, LR `8260df44`;
the original BLR X0 at `8260df40` calls a null terminate-handler argument.
The current log does not establish whether that argument came from a saved
exception header or the global fallback. Main epoch6 and worker epochs8/10/12/14
complete. Three render entries and two continue=true returns are observed;
there is no original draw, clear, swap, PNG or soft-input native report.
Native exit3/controller1; frozen input and executable posthashes match.

Inputs SHA256 `2695e1352e43696dbd5a031b745475a1a70eb27f19d5946e096af07eb017a9be`;
executable SHA256 `f44a54813ffa4b35838658dc173ef51ffc236c12f9384a60510cdf55f79ba24d`;
log SHA256 `5df4c808399b6940e2ed741e78c42f40e875901e11a2c216ae69bf2fdd75c467`.
Terminal peer: `work/unwind1-run-peer1`, SHA256
`e5c0048917c9856b874003d82056ff9bc431abd82ae9eb8e450210fc0165d9ff`.
The v16 admission passes 218 cases per language (16 positive, 202 negative),
and the collector macro syntax gate passes. This run does not qualify the
complete unwinder or exception handling. The next diagnostic must identify
the null handler's source and the exception leading to termination.

Preceding original execution: `work/windows-first-frame-phdr1`, host
`a15fc1c16752eb4e6549c8db12bb2fe49af216e1`, executes the original program-header
callback with real modern64 records: Unity returns0, IL2CPP returns1, and
dl_iterate_phdr returns1 at LR `82628130`. This is not a complete-unwind result.
Execution subsequently stops at unresolved indirect target `82625f08`, caller
LR `82625eb4`. Main epoch6 and four ordinary-worker collector cycles complete.
Two renders return continue=true; no original draw, clear, swap, PNG or
soft-input native report is observed. Native exit3/controller1; frozen inputs
and original objects reverify.

Inputs SHA256 `41a52d658e5a5a92ac0bbb713cb3a313f9c61e8d68b48294540a83c45a9ec229`;
executable SHA256 `1736fb560bd3ee4600488b0d657ce3f331a2635e6c47e918073076cb8f878687`;
log SHA256 `aa52fd9da5d2c3206003d7044a5505d477078df23169ec2d5a5143068bf64213`.
The reached target belongs to a register-rule computed branch. An inventory
of its expression helpers finds 27 missing destinations across three tables;
the other 38 unique destinations across six tables are already compiled.
The additive candidate appends one object and preserves all 3,578 old objects.
Its expression suffixes retain the existing unsupported LDURSH instructions
at `82625a98` and `82625d78`. These valid ISA omissions are not repaired or
bypassed; the successful table-case qualification excludes their paths.

The 27-head candidate passes 55 original-code cases on ARM and translated
Linux/Windows, each both raw and polled. All 800-byte architectural snapshots
and context/memory effects match ARM; complete 1,200-byte host states match
between raw and polled runs. Every new head executes in each translated mode,
including the exact prospective Windows object. One abort-prefix case captures
before the original abort body. These are component results, not a complete
unwind or original game frame. Receipt: `work/unwind-entries-qualification2`,
SHA256 `77addfe3cca4122a5283354684476dd9c3dbd12f26cb10064727af44dab7af3a`.

Preceding original execution: `work/windows-first-frame-worker-futex1`, host
`12ceb5d2e686acdb18c938472d6fcabfe388452b`, completes four genuine worker19
stop/restart cycles at epochs8/10/12/14. Eight physical 31-GPR/32-Q root checks,
eight original posts and four timed-futex EINTR returns are observed. Main
epoch6 also completes. Execution later stops on missing `dl_iterate_phdr` in
libil2cpp, LR `82628130`, callback `82627024`. Two renders return continue=true;
no original draw, clear, swap, PNG or soft-input native report is observed.
Native exit3/controller1; frozen inputs and original objects reverify.

Inputs SHA256 `099b15b831cf800fd635fa7ae870deb3e8f02545234c9a412e0eada6f3691c6c`;
executable SHA256 `ea58082c3f3bfa27bb2a8fa697ff51158f3b6d89f0bc11f36e40e96fc5f988de`;
log SHA256 `8b6634be9b6db197a38441bcfa4b172136c455eb64f4500498c5ddd1051a1e35`.
The callback performs original unwind/FDE lookup using PT_LOAD,
PT_GNU_EH_FRAME and PT_DYNAMIC. The next port must expose the real mapped
program headers of active guest ELFs in load-generation order. The chosen
Android13 profile requires the 64-byte info record with real load/unload
counters. Both current game ELFs have no PT_TLS; no synthetic Android/PE module
or empty enumeration is used to bypass lookup.

The correction passes 183 focused checks, eight real NDK calls and ten genuine
original FDE queries over both mapped game ELFs. The retained original callback
fixture includes all 22 polled heads within ten audited helper families and
both complete indirect decoder tables. Live load order, reentrant load/unload,
counters, early termination and unsupported TLS/catalog controls pass, alongside
22 existing registry and 843 retained dladdr checks. Old seven method bodies,
five markers and all 27 protected sources remain exact. Original game execution
above validates original program-header enumeration. Complete stack unwinding
remains unqualified.

Preceding original execution: `work/windows-first-frame-soft-input1`, host
`13f50c04038e11ebe04afe92690eaa49898ae195`, passes the missing hideSoftInput
binding and reaches collector epoch8. The original stop30 at LR `825b2d1c`
targets a real Unity-created worker (`token19`, entry `70383624`), which the
captured-finalizer profile rejects. Its last observed syscall is timed private
futex WAIT at LR `708f2f14`; the log alone does not prove its blocking phase or
unrecorded collector fields. Main epoch6 completes its genuine stop/restart
cycle. Two renders return continue=true; there are no original draws, clears,
swaps, PNGs or executed soft-input native reports before the failure.
Native exit3/controller1; frozen inputs and original objects reverify.

Inputs SHA256 `da7cd13f417536774740f133f4a975556a544a49db6eefd8e52f6c800768f5d2`;
executable SHA256 `df430038ea1e5fa69d092a0816a662ea8afaa84f5c50433c7c27e61f0e4b7b11`;
log SHA256 `6973c03d23620629b2af3e618da317205a48b14294ca39b7f3a48d199c9097d8`.
The next correction must validate the worker's real ownership, ordinary GC
record and complete physical roots at an exact enrolled futex boundary, then
execute the original stop/restart handlers and posts. Callback naming is not
required for this bounded stack contract. No host acknowledgment is substituted.

The correction passes 111 checks on a real prepared Pthreads worker: two
original stop/restart cycles, four original posts, four physical 31-GPR/32-Q
root frames and actual predecessor poll-binding restoration at retirement.
Four ordinary wait controls preserve short/invalid/mismatched requests and
retained restart signals. An optional futex dispatcher preserves the provider's
ticket, fixed deadline and wake/timeout precedence; focused Windows/Linux tests
and the retained 38 timed/23 untimed NDK records pass. The lifecycle composition
recovers the entire old header and preserves sixteen finalizer method bodies
byte-for-byte. Other 26 protected sources remain exact. These are component
results. The subsequent execution above validates four ordinary-worker stop
cycles; original scanner/reclamation completeness is not inferred from them.

Preceding original execution: `work/windows-first-frame-image-uniform1`, host
`3ef041dc3e4c858aaa8602e101fcafcfab5f0a31`, passes image-uniform reflection
for programs 2, 4, 6 and 8. It then stops at the missing Java implementation
`com/unity3d/player/UnityPlayer.hideSoftInput()V` (JNI environment slot62).
The main epoch6 collector cycle returns normally; two original renders return
continue=true. Native exit3/controller1; frozen inputs and original objects
reverify. No original draw, clear, swap or PNG exists.

Inputs SHA256 `3e5aba6cdf5e39d2edac6bf10f706fb0ae94949ff572870326ab12645ffa6c7a`;
executable SHA256 `0f1d8d338da48cd002df601c3bd8ad3f0262326cbf38c6ffcb6ccfbd7bf9a5c6`;
log SHA256 `da2abc82465fcdc57f024e9e71e41b57f4fd43a6d3914f47140a41fc32912f5c`.
This qualifies passage of the reached image getters, not GPU image dispatch
or a presented frame. The next repair must preserve hideSoftInput's original
UI scheduling and keyboard area/visibility callbacks even when its dialog is
null; a generic no-op implementation is insufficient.

The correction ports that initial-null-dialog path with an always-deferred UI
post, then ordered native area(0,0,0,0) and visibility(false) reports at the
original NEXT_FRAME GL-job drain point on the attached UnityMain. Native-loaded
and finishing gates are explicit lifecycle state; a nonnull keyboard dialog
remains unsupported. The focused Windows gate passes 260 checks, 17 actual NDK
JNI calls and 15 TEST native reports. The render FIFO gate passes 279 checks,
including ordering, continuation and failure propagation. These component
callbacks do not execute the original native report bodies. The subsequent run
above installs the binding; its queued report-native execution remains blocked
by the next collector frontier.

Preceding original execution: `work/windows-first-frame-program-resource1`, host
`973ab9e8c362319f5d9cf63fb7064d1b34464f44`, passes the original resource
Interfaceiv call and continues to uniform reflection. The existing GetUniformiv
width classifier then rejects `GL_IMAGE_3D` (`904e`) at LR `7047f904`, before
native value transfer. The main epoch6 collector cycle returns normally; two
original renders return continue=true. Native exit3/controller1; frozen inputs
and original objects reverify. No original draw, clear, swap or PNG exists.

Inputs SHA256 `0cd41723a46d900bc95435b9eb0bcd5ca2508e9186cf7014fa33cc8e8cf093bc`;
executable SHA256 `7736bd5e4978e67581d7201ee433666d212e64d6cec77117ec2ace5ff8c3e48c`;
log SHA256 `294146c183efd49b73c1acb25ad7f6648008e738e066bce7e06b85be4f3395b0`.
The correction recognizes the twelve core ES3.1 image types as one GLint32 getter
component per real scalar/array-element location. ES3.1 forbids all Uniform*
image assignments; existing sampler, vector, matrix and setter helpers remain
byte-exact. The native-driver gate passes 2,286 checks/517 NDK calls across all
twelve types, 108 guarded getters and 324 write-rejection controls, plus retained
uniform-query/draw regressions. Namespace139 and capabilities remain unchanged.
The subsequent execution above passes the reached image getter calls; no image
binding or GPU dispatch behavior is added or claimed.

Preceding original execution: `work/windows-first-frame-uniform-block1`, host
`37a23e6e5ee02c81168ed2af3f5364e58dca25c7`, executes two new Blockiv calls
and one BlockName call past the previous shader-reflection failure. It later
stops at another null indirect call, LR `7047f550`. The real external-main
epoch6 collector cycle returns with two posts; two original renders return
continue=true. Native exit3/controller1; frozen inputs and original objects
reverify. There is no original draw, clear, swap or PNG.

Inputs SHA256 `008a9ac0a1d7b0cc14fa9728972cfd23a24733ecb061e608d417cd62bda8150d`;
executable SHA256 `da82014522b96550e7b197f6ad9467ce830646755865cb882c0528abe16464f5`;
log SHA256 `570d50dc5a5d716892a1a5939cd2cf8b801a7997616eeaccb04a53d9d146b449`.
The next call is `glGetProgramInterfaceiv` for GL_ATOMIC_COUNTER_BUFFER and
GL_ACTIVE_RESOURCES. A complete inventory of the original reflection FDE finds
21 indirect call sites and 13 GL names. Exactly three remain missing:
Interfaceiv, ResourceName and Resourceiv. Their real-driver bridge passes 638
checks and 158 NDK calls, plus the prior uniform-block and draw regressions.
The eight-argument Resourceiv transport, variable/truncated output, aliases,
names, atomic bindings and SSBO layout match the native driver. The independent
std430 accessed extent is 28 bytes; BUFFER_DATA_SIZE remains the driver's
implementation-dependent minimum, not a portable rounded aggregate size.
All 136 old markers remain exact and the three new commands are appended.
Original game execution of this correction is pending. No compute dispatch or
capability suppression is needed to fix this metadata-query frontier.

Preceding original execution: `work/windows-first-frame-main-altstack1`, host
`4848f6d69cca97822b25aebabbdbd5e0e3935bd1`, completes the real external
UnityMain epoch6 stop/restart cycle: both normal-stack 31 GPR/32 Q checks,
two original posts, genuine handler return and NanoSleep EINTR. Two original
renders return continue=true; the third later fails at a null indirect call,
LR `7047f360`. No original draw, clear, swap or PNG is produced. Native
exit3/controller1; frozen inputs and original objects reverify.

Inputs SHA256 `91b8a0e6aae4933eea94c80065b2bb7e3efa1e6883b5e88fc05abe025fa65099`;
executable SHA256 `5dc915f704d9702f575b376c2ad3c5786ab7e1949395f61f56757150b7294da8`;
log SHA256 `3c9ede46e337ca050c89a343db519da1f28bcc6ee22a6b2077a732c4eaeab913`.
The reached API is `glGetActiveUniformBlockiv`, proven by the original call's
dispatch slot, resolver string and actual null lookup. Its first pname is
GL_UNIFORM_BLOCK_BINDING. The same original reflection function directly uses
five previously missing uniform-block APIs. The typed real-driver correction
passes 534 focused checks and 139 NDK calls, plus 597 existing draw checks.
Independent std140 expectations and native comparisons cover dynamic output,
names, bindings, aliasing and error handling. All 131 existing command markers
remain exact and the five new commands are appended. Capabilities, capture and
other bindings remain unchanged. Game use of this correction remains pending.
Original compute-shader creation is observed in
this run, alongside 95 textures and no frame witness. This does not qualify
original heap scanning/reclamation or complete initialization.

Preceding original execution: `work/windows-first-frame-yield1`, host
`5eded1608599a5ce49712bee74cd2155d0c00293`, returns two original renders with
continue=true and enters the third. The first NanoSleep then fails the external
profile's disabled-only alternate-stack check, before copying its request or
delivering a collector signal. Native exit3/controller1; all frozen inputs and
original objects reverify. There are 29 texture allocations and no original draw,
clear, swap or PNG.

Inputs SHA256 `fcb8123a819d912d5e708a4e9750594719c0a2afb4523c830153690465f6a629`;
executable SHA256 `81fd7e7873c3993bdbd4aee12ab87871542d67ddb9ba658bcd0a99d962686f65`;
log SHA256 `d0afbfc81ca693f1546fd8155d9d4b41301b9673d86d7bf0d951325794502a3f`.
Original Unity successfully enables a mapped 262,144-byte alternate signal stack
with flags0 at LR `7040ee98`. The original collector stop/restart dispositions do
not request SA_ONSTACK, and the interrupted SP is on the owned normal stack.
The profile correction preserves that enabled configuration and its real mapping
lease while keeping collector frames and roots on the normal stack. Disabled
and enabled-inactive controls pass two genuine original stop/resume cycles each,
with eight original posts in total. The enabled case preserves all 262,144 bytes
and its configuration/generation, acquires five real mapping leases and rejects
eight mapping mutations while delivery is active. The core providers remain
unchanged. Original game execution of this correction remains pending.

Preceding original execution: `work/windows-first-frame-external-main1`, host
`44b0184010c431b8da5f40613a503f7bc9b097eb`, stops at an unliftable original
instruction at `703835e8`. No nativeRender call returns, external-main collector
send is observed, or original draw/swap/PNG is produced. Native exit3/controller1;
all frozen inputs and original objects reverify. This execution does not exercise
the new external-main delivery path.

Inputs SHA256 `72f72bd803ba63f1ad63ac3b62a2097d9f94c21e0a2f287bb10757d4102bee8c`;
executable SHA256 `a6cdf5a09b6492ed70b73e6093c62aea8b2e41e70d88610af5de83fe8bf3f118`;
log SHA256 `44ddef2369555194260a0c6668facb924503cb006cc67296b403ed2644b837af`.
The exact original fault is valid `YIELD` at `703835e4` (`3f2003d5`). The rejected
decode advances PC before reporting the error; `703835e8` contains a valid branch.
The selected object is shard129, head `703835a0`. The qualified repair adds normal
fall-through hint decoding and existing no-op semantics, then rebuilds that one
function while preserving its original branch/loop and 127 neighboring functions.

The YIELD fixture passes 16 cases on each of ARM, Linux raw/polled and Windows
raw/polled translations. It executes the original YIELD/branch interval, with a
reversible capture before the following lock operations. All 1,264 prior compiled
semantic functions and 1,424 prior selectors remain exact; only one selector is
added. The v15 cohort changes only object129, preserving the other 3,577 objects,
all 456,706 heads and existing polling. This does not claim full lock-function
execution, native exclusive-monitor testing, scheduler fairness or a game frame.

The external-main component qualification passes two genuine original stop/resume
cycles with four original posts, three nested restarts and 97 checks. It validates
physical 31 GPR/32 Q roots and retained late30/24 delivery through the next original
epoch/nested wait. TEST registry initialization and a helper-shaped caller do not
qualify original heap scanning, reclamation, arbitrary pending-signal shutdown or
a game frame. Default NanoSleep passes 30 records each on Windows and Linux with
the optional dispatcher unset; original ARM24/nativeLinux30 references are reused.

All recompilation sources now live on `recomp-x86_64` in the managed worktree
`C:\Users\user\.codex\worktrees\bunker-recomp-native\bunker`; the shared
`recomp/work` junction retains the frozen builds, test artifacts and assets.

Preceding original execution: `work/windows-first-frame-gc-owner1`, host
`bfa4e8e650408d740e861b10e4c2bebaf26d0aa0`, stops at the existing collector
guard `nonzero send has no real worker owner`. Two original render calls return
continue=true; the third has no returned result. No draw, clear, swap or PNG.
The diagnostic identifies stop signal30 from the original Boehm sender
LR `825b2d1c`, targeting the real external UnityMain token `7ffa00000002`.
Its original registry traversal points at the static main record `879a7330`.

Inputs SHA256 `b9146952cf27d3605119f5651154df1b091598ebe75f0216fbfc1dbdcd1f8e1e`;
executable SHA256 `4dd7b855c346b0760a79af2d28e8a3f123c7c70a9ad42e1d4132604b5eae39a1`;
log SHA256 `d4a8900bcef11a5ce87528535d118ac299c4dec686413cf6039f52fbe44ec442`.
Frozen inputs and original objects reverify. Sampled wait observations remain
nonexhaustive and do not establish blocked thread state.

The additive external-main profile attaches to that actual thread and admits
collector delivery only in the original job-drain helper's nanosleep boundary.
It requires the original stop/restart handlers, epoch writes and semaphore
posts, and physical saved GPR/vector registers inside the original scanner's
stack range. Main flags6 select the global upper bound at `879a6ac0`, rather
than the ordinary child record's `+28` field. No guest collector record or
acknowledgment is fabricated. Existing child-finalizer delivery stays separate.
Focused qualification and the next original execution must establish whether
this integration gets past the observed collector stop; no frame is claimed.

The preceding original execution `work/windows-first-frame-nanosleep1`, host
`ebeef029afc8e128bae67a3b9e47de457b5c8bb9`, completes two original render calls
and reaches `glCreateShader(GL_COMPUTE_SHADER)` in the third. The graphics host
rejects that stage before calling the driver: stage `91b9`, guest LR `7048c838`.
Native exit3/controller1; no original draw, clear, swap or PNG. The run has3577
GL calls,2788 balanced EGL calls and95 texture allocations.

All1765 observed nanosleep calls return0 after copying a valid request of
0 seconds/9999000 nanoseconds with a null remainder. Their elapsed durations
are not established by those logs. A read-only stack sample and original code
identify a Unity job-drain loop; the separate background worker progresses into
IL2CPP code before the later shader-stage stop.

Inputs SHA256 `21bab761d2d3b7cb464ced0a8ff2d8033ecd458659385399ac9b9ae88b655e94`;
executable SHA256 `100143ece506f616231e242efac497cb5f30d0f27077c1e92675d81792da4f96`;
log SHA256 `a272f5bb5fc810e833f450df525bf0e7a808cb7a065d8e3c997fc72518238514`.
Frozen inputs and original objects reverify.

The next repair delegates typed shader creation to the real driver for compute
stages too. Its component gate passes592 checks, including actual NDK creation,
compilation, linking and queries alongside the existing vertex/fragment draw
tests. Compute dispatch remains a separate unsupported operation. See
[shader-stage qualification](gl_draw.md). The first-frame diagnostic also bounds
repeated mutex/rwlock/once observations to the first64 calls and each4096th call
per native thread/import. Other waits remain fully observed. This reduces log
output without changing provider calls or collector hooks; speedup is unmeasured.
A fresh original execution is still required to pass shader creation.

The preceding original execution `work/windows-first-frame-continuation1`, host
`df179927722c32566e881497247ea853904849f4`, completes two original render calls
with `continue=true` on the same UnityMain. The third call stops at unsupported
`nanosleep`, PC `7ffc000000a0`, LR `70383878`, request pointer `1f4620b0f50`
and null remainder. The actual requested duration was not captured in that run.
There is still no original draw, clear, swap or PNG. The next change supplies
the genuine interruptible timer operation, preserving the existing collector
admission policy. Its input snapshot must be logged before waiting.

Inputs SHA256 `ddf84544acc9617915e1fc7f03fc8e09a346a9faeae766ba4e39ed0bf56f1ae3`;
executable SHA256 `ac35027011d99c5424de7cbbb67311d131a99c4c2bf52a2502cfe6713da26dda`;
log SHA256 `6cef4ad510f9fb93d0ca5647f52631c3ed3f223d0474307bed76a861ec21a7e0`.
Native exit3/controller1; frozen inputs and original objects reverify.
The saved audit's legacy `native_render_returned=false` only recognizes a final
summary that this fatal run did not reach. Its ordered log explicitly records
both returns. The updated runner records ordered returns, including actual
false results, while preserving legacy summaries and the existing completion
checks. Seven focused parsing cases pass; the saved run remains unchanged.

The separate [nanosleep provider](signal_nanosleep.md) now passes30 call records
on each translated host, with292 Windows checks and290 Linux checks. Its24
supported ARM/Bionic records and all30 native Linux records match within their
documented scopes. The existing protected27-source map remains exact and the
game admits no new signal-delivery phase. Receipt
`work/nanosleep-qualification2/acceptance.json`, SHA256
`596efcd8c20d899f4783d97b8fbef7ca1aee352fe0e464a3c7f2a0117b16aa09`.
The subsequent original run above passes the reached timer import; its later
shader-stage frontier still prevents a presented frame.

The preceding execution `work/windows-first-frame-launch-url1`, host
`ab351e2314be540c52ea7c5dea5dbd7261393d50`, passes the launch-URL callback and
returns from original `nativeRender` with `continue=true`. It submits no draw,
clear or swap and produces no PNG. The existing one-frame diagnostic then
requests finishing PAUSE; that cleanup fails at the missing static Java body
`ReflectionHelper.endUnityLaunch()V`. This is diagnostic-requested shutdown,
not evidence that the original game requested exit.

Inputs SHA256 `f6256539018e656bccb5e4fa308510b490e8314c3cf1253def6aafd224942be2`;
executable SHA256 `9af0e50d5e46f77dc603ffa66c490b3b045365272f4e78fef56c123c96a11b25`;
log SHA256 `ab6d91497084fd0cb51576918434627b666f6240770feeb129103e090878ac66`.
Native exit3/controller1; all frozen inputs and original objects reverify.
The returned render has1749 GL calls and2761 EGL calls;22 additional GL calls
are cleanup. There is still no presented game frame.

The next change keeps the same UnityMain, window, guest stack and TLS, requesting
another original render only after the prior call returns true and actual focus
and surface prerequisites are satisfied. Window events must continue to be
pumped while a call is pending. Frame proof must pair a captured image with that
same original swap's successful result; an earlier unrelated successful swap
cannot validate a later failed capture. Component qualification now passes;
a fresh original execution is still required. See
[continuation and capture checks](first_frame_continuation.md).

The preceding sensor and FMOD/audio-enabled frontiers are retained below.
The preceding actual build
`work/windows-first-frame-plane-switch1`, host
`ad6c6d71225ca4859e64c769a48f0279d3046eb8`, executable
`b3db46519430b8d7c43ae6abbb2b5b3097515b135a0e3ee18be441c5d74f8224`,
passes the repaired plane dispatcher. It then reports target/StatePC
`70b3bd90`, LR `70ae87b0`, SP `1c63e3df410`. This is a genuine six-instruction
FMOD callback: it rebases its owner pointer, stores the supplied user value and
returns0. The descriptor has16 missing callbacks; six complete call-free
bodies are the bounded next repair. Ten nonleaf callbacks and their six
additional JNI/device helpers remain explicit requirements. Audit:
`work/plane-switch1-jni-audio-boundary1/summary.json`, SHA256
`a55c585d45e97ffa91fbaeeeca6887daec4b9df9858e15d69afdd28bc9310263`.
The six-entry candidate and original callback gate pass35 records on ARM,
Linux raw/polled and Windows raw/polled. All800 architectural and65536 memory
bytes match, with independent full1200-State/token checks, aliases, optional
output guards, ARM-defined SDIV edge cases and unsigned ring arithmetic.
Windows-polled executes the actual six-function COFF. Receipt:
`work/unity-fmod-pure-qualification1/acceptance.json`, SHA256
`b1f943a722126baa3687c8a9c85bb9adf193e3f823460a27221725b76b0bcb40`.
The v14 cohort is sealed at
`work/first-frame-fmod-callbacks-cooperative-cohort1/acceptance.json`, SHA256
`0496c62a7a1db0e6325c94b946c93fca8427847c4972cc6748dbc85a673b3f30`;
source plan SHA256
`d506ef966942e3858c3f8b991f33d6a91c0a4390a07c26d3aff65d67bbb50bbe`.
All3577 old objects remain exact; index3577 adds6 entries. Totals3578 objects,
456706 heads/79438 references,578826 polls/122120 cuts and1433 unsupported
heads. Only six declarations and dispatch rows change in the trace header.
The focused v14 guard campaign passes169 cases in each language (15 positive,
154 negative), plus actual source-I/O guards. All1334 historical payloads/order
are retained, including old focus probes;1320 historical negatives are not
claimed as rerun. Receipt `work/cohort-v14-validation1/acceptance.json`, SHA256
`2dcfb3ab45a0bf36fbec2bb72f0732eac19fa9a0df54b30838950f1fe7d9b10c`.
The source-I/O selectors now identify the unique actual Python/PowerShell AST
plan guards, allowing each new version to be tested without copied version lists.
The selected build `work/windows-first-frame-fmod-callbacks1` uses host
`62b20a57225487edf00e2dc5709c3e8580bb2f2b`, executable SHA256
`c4b64d5db2e7c1cc5559b3af054bb259615177a0c6873d365770b3534d71af4e`.
Its original startup passes the repaired `70b3bd90` callback and stops at
another descriptor callback, `70b3bd80`, LR `70ae5df8`, SP `1dd4fcbf1c0`.
That callback rebases the owner and tail-calls original helper `70b3c1e8`;
it is one of the ten explicitly excluded nonleaf callbacks. Native exit is3,
controller exit1, with all frozen inputs and original objects reverified.
Inputs SHA256 `142c71c93037ad37664af50ee6c97de7eade14e69d496348363de2353e9ff287`;
log SHA256 `ba4e556b542ce4ebc763cbef0343dac6fb11012a04b764dd4d10c6cfca477b70`.
There is still no original draw, successful swap, nativeRender return or PNG.
The remaining nonleaf descriptor callbacks and their helpers are audited as
a group; none is selected by the audio-disabled diagnostic below.
Late JNI diagnostics also report missing Context.AUDIO_SERVICE,
android/media/AudioManager, checkCallingOrSelfPermission(String)I and a null
reference. Their causal relationship to the final stop is not assumed.
The explicit-muted option calls original nativeMuteMasterAudio(true); it does
not disable FMOD initialization. A read-only audit found no established original
no-sound launch option; no guessed flags or OS audio changes are used.
The next diagnostic instead uses the engine's serialized
`AudioManager.m_DisableAudio` project setting. Its separate, verified asset
variant changes one byte from0 to1; every DEX/native entry remains identical.
The original deserializer stores the flag at owner+`359`, and original
`701fd66c/701fd670` exits before creating FMOD when it is set. This exercises
the game's genuine audio-disabled path, without replacing a callback or
reporting a successful audio device. See [asset-only input derivation](asset_pack_wrapper.md).
Both generated APK hashes and the bounded PlayCore profile must match the new
exact APK hash; a fresh relink is required. Existing guest objects and collector
behavior remain selected. Both APK profiles pass209 wrapper checks and eight
rejection boundaries per Windows/Linux host. The next original execution is
`work/windows-first-frame-audio-disabled1` runs with host
`d52821f908ecb2cabb0669160b48e13caa2a7ee9`, executable SHA256
`21eb25d16ca1aedc01dbfb550a476c0c8d8b2644ff526bbbd54c3d9834dc6217`.
It passes the earlier FMOD frontier and reaches sensor initialization, where
`ASensorManager_getInstance` is unsupported (PC `7ffc00000120`, LR `70411a24`).
Native exit3/controller1; all frozen inputs/objects reverify. There is still no
original draw, swap, nativeRender return or PNG. Input SHA256
`65e496475e6d14b6abb8e4bcfed10ffba88a5e9701f30a8435defa64d7016aae`;
log SHA256 `4b266b93cfeb58fc36419feb22c16ba1f0d5f3c2f8cce26e79a76b7492cf0ea0`.
A missing Context.POWER_SERVICE field is a separate preceding JNI diagnostic;
causality is not inferred. The next bounded change qualifies the original
[unavailable sensor-service branch](sensor_service.md) as an explicit desktop
port capability policy, with Android hardware/service behavior left unclaimed.
That gate now passes four original cases across ARM and Windows/Linux raw/polled
execution, including post-null capability queries and translated NDK callers.
The next original startup is `work/windows-first-frame-sensors1`, retaining
the same audio-disabled APK, guest objects, collector and graphics code.
That original build runs under host `14aa64f0a0f2e67e7066aca1f5a9531086f31c59`,
executable SHA256 `bfe77469edcc8c4a39a44f7a379d2e8aad7fed7465ab6506e2f794592f4ebc66`.
It passes the sensor frontier and stops at JNI Env35 because
`com/unity3d/player/UnityPlayer.getLaunchURL()Ljava/lang/String;` has no host body.
No native caller LR/register tuple is logged for this failure or inferred.
Native exit3/controller1; all frozen inputs/objects reverify; no draw, successful
swap, nativeRender return or PNG. Inputs SHA256
`633ddda7238d6733a1a52e751415f0a5a7a5b42d2af7499b3f495b47b4e13da7`;
log SHA256 `3c1d011dac17dcf94f97b2b340d9553b90a794ac4469b0f55a653c491749d74c`.
Earlier cleared JNI diagnostics name POWER_SERVICE, InputDevice,
InputDeviceListener and AUDIO_SERVICE; they are not the final fatal callback.
The next change qualifies the [retained launch-URL getter](unity_launch_url.md)
and constructor snapshot against the original APK method.
The launch-URL/JNI binding gate now passes1262 checks per Windows/Linux host,
including the retained URI behavior and existing Intent/AR/JNI frame regressions.
The next original build is `work/windows-first-frame-launch-url1`, after the
collector source guard admits the exact qualified JNI wrapper additions.
The preceding plane-switch run exits native3/controller1; all frozen inputs
and original objects reverify.
There is still no original draw, successful swap, nativeRender return or PNG.
Inputs SHA256 `00ea9cacd474e9d389bf147ae844c6d12cd9024545ff5c9c653f46da4d9c2849`;
log SHA256 `88fd2bfc0cffe3a9a0cd9993e44d0f312555e64ac41fdff0e28e141649d67761`.

The preceding execution frontier was an unresolved indirect original-code target.
Actual build `work/windows-first-frame-ushll-mask1`, host
`c58d7a149e3e100d91bc513af37fa4f8db9d3208`, executable
`08877479365ecf5b0cb98170fb2e1c6a13d36ed40f7d0ecec46e18c7a006a3b1`,
passes the mask initializer and reaches texture labels through id20. It then
reports target/StatePC `70ae3f84`, LR `70ae3a44`, SP `20175a0f470`.
The original caller at `70ae3a40` calls dispatcher `70ae3f04` with mode2.
Its signed-relative table at `70fab758` has13 guarded slots and11 distinct
case entries; all11 are missing from the selected dispatch set. The logical
dispatcher region is `70ae3f04..70ae443c`, with sole RET at4438 and epilogue
at4428. This region has no covering .eh_frame FDE; these are control-flow
bounds. Audit `work/ushll-mask1-indirect-boundary1/summary.json`, SHA256
`c72430414b2e20e17b50000c192b9aeda64a78ac1a04df74b545d03683a46448`.
The next batch adds those11 original case entries and checks all13 slots,
unsigned out-of-range and disabled-object controls through the real dispatcher.
Its real rebuild helper `70ae31f0` in object466 also retains an unsupported
scalar FADDP S0,V0.2S at `70ae33bc`. That finite-input path is included in the
repair scope, with separate instruction-family and original-dispatch checks;
it is not replaced by a successful helper stub or excluded as a sqrt fallback.
All3575 other old objects will remain exact; the case object is additive.
The completed combined dispatcher gate matches16 cases across original ARM,
Linux raw/polled and Windows raw/polled: all13 slots, unsigned out-of-range
and disabled-object controls, full64KiB object/canaries and the defined
return/callee-saved ABI. The optional resource pointer is NULL; the excluded
sqrtf fallback is never reached. Windows-polled testing executes the actual
new11-entry COFF and actual106-function helper COFF. Other105 helper functions
are statically byte-exact, without a claim that the fixture executes them.
The old helper returns normally for mode2 but reproduces unsupported
`70ae33c0` for mode3; that same mode3 passes with the repair. Receipt
`work/unity-plane-dispatch-qualification1/acceptance.json`, SHA256
`a0f5edc580780807c0e5b6050ef514f25825b45194691a1614a333c563e39659`.
The scalar instruction gate separately passes16384 records per ARM/Linux/
Windows host,2057 decoder checks and8 independent full1200-State checks per
host. See [scalar FADDP](../whole/faddp_scalar.md). One new LLVM signed-max
declaration uses an unchanged attribute group; removing that exact line and
restoring the target recovers the old helper module. The saved successful
lift is reused, with no second lift for that declaration follow-up.
The sealed v13 cohort is
`work/first-frame-plane-switch-cooperative-cohort1/acceptance.json`, SHA256
`02d5545fd8da4a4103e3e64e364786d2fc8629f84fb88a855ada5afee8dfd16a`,
source plan SHA256
`2dac17b452eab5e5d01419a5ca8c80fb201641724f1a24213bf84312a678aebb`.
It contains3577 objects/456700 heads and79438 direct references; poll sites
578820/cycle cuts122120, with1433 retained unsupported heads. Only old object
466 changes, preserving105 neighboring functions; index3576 adds11 entries.
The focused v13 production-guard campaign passes205 cases per language
(14 positive/191 negative), including every historical positive, new-version
policy/shape/type/ancestry/tamper cases and actual source-I/O guards. All1142
historical case payloads/order remain exact;1129 unchanged historical negatives
are preserved as prior evidence and are explicitly not claimed as rerun.
Receipt `work/cohort-v13-validation2/acceptance.json`, SHA256
`b6f19ff58bc05ff095d5e2930844fe583c259dd5ba8a4d552748f1c652a3266d`.
The first guard campaign stopped in its test-only plan selector, which still
listed versions only through12. The corrected selector uses the actual
production AST node; production Python/PowerShell predicates and all native
fixture/candidate bytes are unchanged. That failed campaign remains saved.
Next startup: `work/windows-first-frame-plane-switch1`.
Native exit3/controller1; all frozen inputs and original objects reverify.
There is still no original draw, successful swap, nativeRender return or PNG.
Inputs SHA256 `fbbbbda1ebb959f32333eae42359a2f058345c37df57f6756367b573cb0ad857`;
log SHA256 `4fa82c01b9750f13a0d3675b0c1671806a56ba4bb29ad08ce2ad7d5329c36bad`.

The preceding execution frontier was a retained older translation of an unsigned vector
widening operation. Actual build `work/windows-first-frame-texture3d1`, host
`7248183ae21f621f1a48f255602933ede177e2a9`, executable
`0cf9861508368f249d69d4a31e6d62d4a8479124cc883dfd723bb8744f282a6c`,
passes eight observed glTexSubImage3D calls (3D, array and cube-array targets)
and texture labels through id17. It reports unliftablePC `702b3ec0`, the next
PC after USHLL V2.8H,V1.8B,#0 at `702b3ebc`, word `2f08a422`.
Original FDE `702b3d34..702b4034`, selected object94, contains fourteen
USHLL/USHLL2 operations across all six widening forms. Existing qualified
semantics already support these; no new instruction semantics are required.
The current compiled six selectors and their complete functions match the
previous ARM/Linux/Windows-qualified pair exactly. That source-only proof is
`work/ushll-current-pair-identity1/proof.json`, SHA256
`d2918f90adb54fa2d720b9ca9a6e7c776fed66bb0fe58af54ad5065feb7899b8`.
The next repair applies this existing support to the one retained function,
preserving its neighboring functions and checking actual original behavior.
The candidate passes full static preservation of all127 neighboring functions,
including six earlier FCSEL repairs, in raw/polled IR and complete COFF bytes.
No declaration or direct guest reference changes; the target gains two cycle
polls. Candidate `work/unity-ushll-mask-overlay1/candidate.json`, SHA256
`03b57f5e4a16488f364975e9f79c406308454fafe46f5a47056a5f30caedeebf`;
new object SHA256
`c28559fea099d8d2091ec876061345fd7b6aa80e6740745cf30586e9930ea5d5`.
The exact original block `702b3e98..702b3f78` and readonly16-byte table match
16 records across ARM, Linux raw/polled and Windows raw/polled. All800
architectural bytes and256 output bytes agree; an independent integer model
also checks full1200-byte host State, memory token and allocation canaries.
All16 initial NZCV patterns, four FPCR modes and sticky FPSR cases pass.
Receipt `work/unity-ushll-mask-block-qualification1/acceptance.json`, SHA256
`be35d41e14bd385469ddb11778e1cb4ff2a22936765b658d83b4a0d7824fbecd`.
The fixture captures before original BL70346214; preceding platform calls,
the helper body and full-FDE return are excluded from this dynamic claim.
The whole selected COFF is statically compared, not executed by the fixture.
The v12 cohort is sealed at
`work/first-frame-ushll-mask-cooperative-cohort1/acceptance.json`, SHA256
`34a41fc3f8fa21e5df3d23d702d455e52805bfd21a6f33161b5176245d241601`;
source plan SHA256
`0385129c17c6b2db060aa938127edf2993490b78b4adcbd551d24840fa006aea`.
It retains456689 heads and79438 direct references. The one changed function
removes one unsupported head (1435 to1434), and poll sites/cycle cuts rise
by two to578791/122102. All3575 other objects remain exact.
The actual Python and PowerShell guards pass1142 cases each (13 positive,
1129 negative), including real v12 ancestry and source-I/O checks. All1023
historical case payloads/order and pass/fail/returned-version results stay
exact; the old v11 mutation to version12 now rejects under the known version's
qualification checks. Receipt `work/cohort-v12-validation1/acceptance.json`,
SHA256 `cf86f1301e9bb7bc4152773f4e5f837bc11650eb7f3139e13ecb5ea2c5d6b582`.
Next startup: `work/windows-first-frame-ushll-mask1`.
Native exit3/controller1; all frozen inputs and original objects reverify.
There is still no original draw, successful swap, nativeRender return or PNG.
Inputs SHA256 `66faf4355d6283e097c2ee440b5e6e877ef4e607b67bbf5cb26b2bd44de36adb`;
log SHA256 `44b7b316dfe191fc807ef8b29e2141d254e8d4ead17d262c4b4754406c332a34`.

The preceding execution frontier was missing 3D texture upload at a shared indirect seam.
Actual build `work/windows-first-frame-st3-1`, host
`dd47b9b677ebf6956d0ff291b5f0c09a543d0de9`, executable
`2ec4502664c0ee53b7511d938b701a3613a9dffe44b55e15cb2b74e4502508f9`,
passes ST3 initialization, reaches texture labels through id12, then allocates
texture id13 at GL_TEXTURE_3D through glTexStorage3D. It stops at target0/
StatePC0, LR `7048f26c`. The shared BLR `7048f268` can load slot `0x518`
(glTexSubImage3D) or `0x550` (glCompressedTexSubImage3D); the fatal LR cannot
distinguish them. Both lookups returned0. The next batch covers exactly
those two uploads and the observed mutable glTexImage3D fallback, with real
row/image/slice strides and CPU/PBO transfer distinctions. Native exit3/
controller1; still no original draw, successful swap, nativeRender return
or game image. Inputs SHA256
`3f621f5a8f935dd44a5e2f7e975f63541caa912fc46107298f49666931884e56`;
log SHA256 `673a774e88edc254511b10eca169f9ef1f3d6ec5020119a5814b1602aa82ab32`.
Bounded audit: `work/st3-1-texture3d-boundary1/summary.json`, SHA256
`e297533046db2e137c1a1b7f271375d36bee8558dc369e4119ddf5c07e0ca574`.
Existing OES fallback guards retain a valid core slot, so no alias bridge is
required. The 11-argument uploads place format/type-or-size/pixels at guest
SP/SP+8/SP+16; the full64-bit pointer/offset must survive that stack transfer.
The first3D transfer gate passes900 checks/46 NDK calls/45 records through8
heads and2 objects. Actual GPU3D/array layers, packedRGB565 and ETC2 sampling
match native calls; row/image/slice skips, overlap, inaccessible padding,
tight compressed imageSize, CPU/PBO offsets0/32/high64, NULL/zero/native
errors and old128 markers all pass. Native PBO validation retains real unpack
state even though compressedCPU decoding uses tight default unpack. Existing
2D helpers and every v11/collector/affinity/Runtime source remain exact.
Receipt: `work/gl-texture3d-qualification1/acceptance.json`, SHA256
`b7ab35fa4821deadf0d3eff636060786f26f683df3a55f47c665d98f657d247a`.
Next startup: `work/windows-first-frame-texture3d1`.

The preceding execution frontier was an unsupported ST3 multiple-structure store in the
recompiler. Actual build `work/windows-first-frame-label2`, host
`eeb2abf184e065c4a434a849f5a2efb00fe67f89`, executable
`6f28b19fa35fe750991d6d851497b9d918ea6b3077b02029aadd09199efa1e41`,
passes real focus, resumes/mutes, initializes IL2CPP and returns from four
observed texture-label calls. It then reports unliftablePC `704fdb3c`.
The selected body proves this is NEXT_PC after word `4c004154` at `704fdb38`:
ST3 {V20.16B,V21.16B,V22.16B},[X10]. Exact head `704fd850`, FDE end `704fdb60`,
global selected object200; the following B.NE is not the missing instruction.
Native exit3/controller1; no original draw, successful swap, nativeRender
return or game image. Inputs SHA256
`9b8728fa851ec2dca5dd7f3bc52ae4020857f6573a6d2133de5e48f1eafcadbf`;
log SHA256 `36d64de5b2e3b68191a3539591f1dbce3a8b441d607c4fcb799f70a09c89c26c`.
Bounded audit: `work/label2-st3-boundary1/summary.json`, SHA256
`2f45df77786639df19fa4daa7f0fc1e198f6783797f3710c39a0d73928986821`.
The focused ST3 family passes1152 identical ARM/QEMU/Linux/Windows records,
687 decoder controls and72 full1200-State/token/memory controls per host.
Receipt: `work/st3-qualification1/acceptance.json`, SHA256
`15404cfbfca518caa3393c428e9585d0456086232892ff95e75b73d6cfabfa98`.
Remill commit `cda2d3f2b9ff89260f4db997b24e47e40d2b86cc` adds three decoder
delegates and21 selectors; all1248 old compiled functions/1401 selectors and
the State ABI remain exact. The actual original prefix and the one-object
replacement are qualified separately, preserving3575 other objects.
The v11 cohort is sealed: `work/first-frame-st3-store-cooperative-cohort1/acceptance.json`,
SHA256 `64498bd829e9b92c7f4867a6fe3a1fc5a8a162c6b937a4cfdd23aa9404ae969e`.
It preserves456689 heads/79438 direct references and replaces one function
while127 other definitions in object200 stay exact in raw/polled IR and full
native bytes/relocations. Poll sites578789 and cycle cuts122100 each rise1;
unsupported heads fall1436→1435. Actual new polled COFF SHA256
`cddd5852024875161cef458b8b3d1e825721a32965ad79f66fc7157d92ab53b6`.
The exact original prefix through its real helper call matches16 records on
ARM and Linux/Windows raw+polled projections: all800 architectural bytes,
64KiB global/index/output/canary memory and64-byte saved frame. Receipt:
`work/unity-st3-block-qualification2/acceptance.json`, SHA256
`4f6bfd4533f5c04514e433fb6ddef2592823d403454f32aa17ff465589c68b25`.
This captures before helper execution, not a full-FDE return or execution of
the full selected128-function COFF. Q1 preserves a fixture FPSR-packing bug;
Q2 uses the same six-field architecture packing as MRS FPSR, with unchanged
candidate code. The mandatory next helper is already lifted without errors.
The one new Runtime barrier declaration uses the existing unchanged fence
implementation; the overlay whole-file inverse includes that declaration.
The actual v11 consumer guards pass1023 cases per language (12 positive,
1011 negative), Python36 and PowerShell47 source-I/O controls. All907 old
case payloads/order and pass/fail/returned-version results remain exact;
ten old mutations to version11 now reject under the known-but-unqualified
version's shape/hash checks. Receipt: `work/cohort-v11-validation1/acceptance.json`,
SHA256 `4104a0e1264482dc5697116b96a56df5c5603651fa521b2432cd95fb04eea52d`.
Next startup: `work/windows-first-frame-st3-1`.

The preceding execution frontier was the real foreground/focus prerequisite, before
nativeRender. Actual build `work/windows-first-frame-label1`, host
`cbfd33b57ee3653e2f1605861a7256828b64e5ac`, executable
`f5d07ac77d283cd763d07caa3503fb16bec2c8074d6a1b5660ca2db1bf0b24f5`,
logs SetForegroundWindow accepted0, then exits after the three-second wait
without a real HWND focus event. Native exit1/controller1, IL2CPPctors0;
the new label calls and original nativeRender were not reached. No draw,
swap or game image. Inputs SHA256
`689884e86c3bf9f8a1ab541ac14c1b57ebf7f29bebcdf2ccf785fed895007bed`;
log SHA256 `3e22d5c3f8a495767062fd3a38cdf5778d5b836054b4f5ba0dcc6919a7148fd1`.
The next diagnostic increases only --first-frame's observed-focus wait to
60 seconds, retaining the default three seconds and every real focus check.
The same qualified GL/collector/affinity sources and all27 receipts remain
unchanged. An actual window activation can then deliver the OS focus event;
no guest focus is synthesized. Next startup: `work/windows-first-frame-label2`.

The preceding execution frontier was a missing native graphics object-label setter.
Actual build `work/windows-first-frame-storage1`, host
`86e55e87e0310f27e3b2635f97a9c21ddba370c7`, executable
`2225f47d4997c41d89fc7c3756a16f971f339f95454d51a317f8a53521105531`,
passes glTexStorage2D and uploads its first texture through glTexSubImage2D.
It stops at target0/StatePC0, LR `7047b1c4`. The outer function calls the label
helper, which restores its frame and tail-branches through slot `0x340`
(glObjectLabel, core/KHR) or `0x360` (glLabelObjectEXT). Both reached lookup
names returned0. The two APIs copy label text with different length rules;
the next batch adds exactly those setters, using native getter oracles only
in the component test. Native exit3/controller1; still no original draw,
successful swap, nativeRender return or game image. Inputs SHA256
`72400b52457eafd0c7d63873365f250dfc4e694fac936dddeb688a71a271a6fd`;
log SHA256 `d97188caad1f9c301e8750b2786df53f7a31a48f1b67efcc530a791e585289a2`.
Bounded audit: `work/storage1-next-texture-boundary1/summary.json`, SHA256
`d96bb6081f7202fabfc1b291af10c4ef0ad555e3acd7aaa483e869a4adb22a1b`.
Because the helper tail-branches after restoring its frame, the fatal LR
cannot establish which of the two label slots was selected at runtime.
The first label component gate passes653 checks/56 NDK calls/53 records
through7 heads and2 objects. Both setters match native byte/length and error
oracles, including NULL/explicit/NUL conventions, embedded NULs, guard edges,
copy lifetime, invalid-object-before-copy ordering and duplicate pending
errors. Actual native maximum label length is1024. Old126 markers remain
exact and two setters append to128; no label getter or unobserved alias is
exposed to the guest. Receipt: `work/gl-label-qualification1/acceptance.json`,
SHA256 `95afb7768194d0c319c5c28846f795e2df0c16bcdf87aef62ecfed22e5d3d6b8`.
The next actual startup is `work/windows-first-frame-label1`.

The preceding execution frontier was missing `glTexStorage2D` during texture creation.
Actual build `work/windows-first-frame-getaffinity1`, host
`f9506de773d3ebca8796802c18627d8278db9b69`, executable
`9cac123d3243ecd24092409cb4250f27a03b4653b237a957f289bbb2186c8ba3`,
passes public sched_getaffinity and both observed worker sched_setaffinity
calls with result0. It then creates a native texture and configures swizzles,
filters and mip bounds before unresolved target0, StatePC0, LR `7048e8e4`.
Original FDE `7048e20c..7048e8e8`, BLR `7048e8e0`, loads slot `0x520`;
both core and EXT-alias lookups for that slot returned0. The same FDE contains
the related TexStorage3D/2DMultisample/3DMultisample calls. The next batch
adds those four pointer-free native storage APIs in a separate typed table,
preserving all122 old marker indices and143 query rows. Native exit3/controller1;
still no original draw, successful
swap, nativeRender return or game image. Inputs SHA256
`b162795ca33e24d571f5a548baff806c7bcfa881f65f9bf915be2b50d199f711`;
log SHA256 `60771f392b31b59d841420a88cac94850df34169d591a2ad081172cc1ba792b8`.
Bounded audit: `work/getaffinity-texture-creation-boundary1/summary.json`, SHA256
`aa09808757057f8841968866ae6762442970be95e6cbb7c76298a51ab853838c`.
Optional EXT lookups are skipped when the core pointer is valid, and null
EXT results never replace a stored pointer; no alias bridges are required.
The first storage component gate passes858 checks/61 NDK calls/42 records
through10 heads and2 objects. The actual native context is GLES3.2; all four
families have positive allocations, with mip/sample/immutable metadata and
initialized FBO pixels/MS resolve checked against direct native calls.
Low8-bit boolean ABI, invalid arguments, poisoned unpack/PBO state, pending
errors and all122 old markers also pass. This is component QA, not a game
frame. Receipt: `work/gl-storage-qualification1/acceptance.json`, SHA256
`ed195460a007e66e52cd3cbf912276fb54986b01be8ca9fd5ae13153c07bc873`.
The next actual startup is `work/windows-first-frame-storage1`.

The preceding execution frontier was the missing public Bionic
`sched_getaffinity` import. Actual build `work/windows-first-frame-window-manager1`, host
`51046016c712835c3f6fdebec6a14e7be59639fc`, executable
`cda0ecb26b831df800b4623d300fc6cdc079e54699543f8d3470453c3d75bbbd`,
passes the repaired Activity/WindowManager/Display chain and reads the actual
associated output at3840x2160,224 DPI and120/1 Hz. It then stops at
`sched_getaffinity`, captured LR `708f173c`, PID `0x1bf95c`, size128.
Native exit3/controller1; still no original draw, successful swap,
nativeRender return or game image. Frozen inputs SHA256
`6e317a725626bd74f403602812e70b70b542a66fb27b1d09f07d08a267614adf`;
log SHA256 `cd20d800694b82efc794c87450832a965a7f9e0c369d13c18dd7a7e72ead30e1`.
The bounded caller zeroes128 bytes atSP, calls the public getter for the
current native TID, ignores its return and scans for the first clear CPU bit.
Its count is a trailing-one prefix, not a popcount; no dense mask or CPU count
may be fabricated. The next addition is an owned-thread Windows affinity
query with the public Bionic return and output-buffer contract. The immediate
worker caller also conditionally reaches the adjacent public128-byte
`sched_setaffinity` helper, BL `708f17d8`. That companion is included in the
same build with actual native mutation and readback; its execution has not
yet been observed. The existing raw four-byte affinity syscall stays exact.
The public Get/Set gate passes599 Windows checks and28 records through8 NDK
heads, with26 Bionic return/errno records matched. The existing Windows raw
setter regression passes158 checks/32 records against the new provider.
Receipt: `work/affinity-public-qualification2/acceptance.json`, SHA256
`d53e2045cba776791bf684e17674cc8020dfd9eb03e4b3b0d190932a163deb26`.
Q1 retains a fixture assumption failure about partial copies; Q2 compares
effects with an independent same-size native copy. Provider sources stay
unchanged. The next actual startup is `work/windows-first-frame-getaffinity1`.

The preceding execution frontier was the absent legacy Android display JNI chain.
Actual build `work/windows-first-frame-vao-query1`, host
`5525d90ef65ab7576a9f11ce43ceb1fab9514659`, executable
`12c64eddda4740428140ce8e5af1a08131183ce6be5e7b4982e09c305c9e5e17`,
passes VAO setup and creates/uploads native GPU buffers. Missing NativeActivity
and WindowManager metadata leads to null method/receiver errors in the
Activity.getWindowManager → WindowManager.getDefaultDisplay → Display refresh
chain. Native exit5/controller1 is a null8-byte read in __remill_read_memory_64;
the exact final guest instruction is not proven. Original static teardown can
leave a JavaVM field null when that display setup fails. There is still no
draw, swap, nativeRender return or game image. Pinned audits:
`work/first-frame-vao-display-jni-boundary1/summary.json` (`bede3e4b…f7628a`)
and `work/vao-query-native-av-audit1/summary.json` (`21f2fd75…a9eb4c`).
The next build adds the two real JNI methods and NativeActivity inheritance
metadata, using the existing Windows display provider and a weak reader for
the actual owned HWND. Its monitor/device selects the existing Display object;
no primary-display assumption or invented hardware values are used. Existing
topology, caching, refresh, SDR and host-scheduling policies remain exact.
Reader qualification passes300 checks; display-chain qualification passes165
checks through19 NDK heads and observes one native associated output at120/1 Hz.
Receipts: `work/native-window-reader-qualification2/acceptance.json`, SHA256
`9c3d4e4e09613cebecdfc1316253f60e112e47b0cd4ae02055f2ab849f402e0c`,
and `work/activity-window-display-qualification2/acceptance.json`, SHA256
`3f4ed33364a5562c36c9e4d1e430fceeb8df33732189b330fb2ea39215e94781`.
ReaderQ1 preserves a minimum-window-size fixture failure, fixed only by using
supported320x240 test windows. DisplayQ1 preserves a new callback error-path
bug; Q2 reports Java errors for invalid/closed/expired backing. No original
guest function, Runtime, JNI core or GL command changes are included. The next
actual startup is `work/windows-first-frame-window-manager1`.

The preceding execution frontier was missing `glIsVertexArray`, original BLR
`70490734`, captured State LR `70490738`. Actual build
`work/windows-first-frame-renderer-state1`, host
`1c5c247fa310e3a567b959181148490a5fc56ee3`, executable
`165c5098c93ea05bcc75ade8d247930e0102a7abc383b9df804a7b1eb6869521`,
advances through sampler/indexed-buffer reset and texture/framebuffer state.
Native exit3/controller1; still no draw, swap, nativeRender return or image.
Loader slot `0x610` and its zero dlsym result identify the captured call.
The exact wrapper FDE returns a GLboolean for a GLuint name. Its bounded
continuation uses existing Gen/BindVertexArrays and DisableVertexAttribArray;
no other missing name was found before initialization returns. The actual
queried name, context values and result remain unobserved.
Audit: `work/renderer-state-vao-query-followup1/summary.json`, SHA256
`08a9a654b1e4d0d443a00fa1f50d7e1e13f1b141b7f237e40151bdfa4120cd82`.
The next addition is that native boolean query, tested within the existing
draw fixture. Its first gate passes544 checks,33 NDK boolean calls and10
lifecycle records, including native zero/reserved/bound/unbound/deleted/
arbitrary/context-local behavior, function-pointer/procedure paths, narrow
return ABI and pending errors. Existing draw/readback/guard/sharing/tracked
write controls also pass. Receipt:
`work/gl-vao-query-qualification1/acceptance.json`, SHA256
`ffe5f99b0e8c37f23b44b0780eacc4219d2eb66961f90c2cabe442150cd1d8f5`.
The next actual startup is `work/windows-first-frame-vao-query1`; the
component's synthetic draw is not an original game frame.

The preceding execution frontier was missing `glBindSampler`, original BLR `70491348`,
captured State LR `7049134c`. Actual build
`work/windows-first-frame-internalformat1`, host
`e1ad2955559b3281883a41c43d0d553f3280b16c`, executable
`3193cc0e58701a0cb226a5b9c6291111c326041adadcb65d1a24dd6caa76c514`,
passes internal-format initialization and reaches VAO creation and renderer
depth/blend/stencil/cull state. The new failure diagnostic reports target0,
StatePC0 and LR `7049134c`; original loader slot `0x738` maps to the observed
zero-result `glBindSampler` lookup. Native exit3/controller1; still no draw,
swap, nativeRender return or game image. The exact bounded audit is
`work/internalformat-renderer-state-followup1/summary.json`, SHA256
`efb2b72a996b10aa616457af98dc9f50e967738fa9bdc4fc3679ec56de486048`.
The same FDE has four later guarded `glBindBufferBase` sites with a zero
lookup. Other subsequent GL slots in that FDE resolve nonzero. Their later
execution is not claimed. The next batch covers the four observed sampler
APIs and that indexed-buffer binding API. Both first driver gates pass:
samplers301 checks/39 NDK calls and indexed buffers947 checks/110 NDK calls.
Receipts are `work/gl-sampler-qualification1/acceptance.json`, SHA256
`421eb25c3a54ee71897b8f92e17fb7dcd92db68c52b7b513ee762034bad787b5`,
and `work/gl-buffer-indexed-qualification1/acceptance.json`, SHA256
`bce4fc573e6eccecd8aa1dbe313b933cd6d13561e03b2e4c8732b9df8d54d2e7`.
Both compile the same held composition, preserve the old116 marker prefix
and143 query rows, and append five markers to121. The existing indexed
guest-query whitelist and Runtime remain unchanged. The next original
startup build is `work/windows-first-frame-renderer-state1`.

The preceding execution frontier was unresolved indirect target0 after the default
framebuffer properties query. Actual build
`work/windows-first-frame-platform-query1`, host
`87bc34552f720aeab334e13ca51684597eb25697`, executable
`7c2f5051f61cf3e7d192e7ac9bcfc9eff9be947eeed32ca40596606de1d6b1e6`,
records231 GL entry attempts and2758 paired EGL calls. Its final eight
queries are RGBA/depth/stencil bits and SAMPLES/SAMPLE_BUFFERS; the final
logged original return is `7048db74`. The previous ID/RELEASE/INCREMENTAL
missing-field errors are absent. Native exit3/controller1, with no draw,
swap, nativeRender return or frame PNG. The fatal diagnostic does not
capture guest State PC/LR/SP, so its exact null caller remains unattributed.
Saved audit: `work/first-frame-platform-query-null-boundary1/summary.json`,
SHA256 `2ed82eb5087f2acea9119d913e0c98dc84010e0c679f1904ffc1acbe6f0723b3`.
The next build adds one failure-only Runtime line printing target and State
PC/LR/SP before the existing unresolved-target abort. Exact inverse proof
recovers the previous Runtime byte for byte, and runtime.h is unchanged.
Linux and Windows each pass97 prior checks, five prior fatal cases and
two new zero/nonzero target cases. Qualification:
`work/runtime-unresolved-diagnostic1/qualification4/acceptance.json`, SHA256
`ca33662cafb9743a433972d84be2aaedbb0a698581115cf3b9f2ae5e66dc91cd`.
The corresponding source-pin supersession passes19 cases, including16
tamper rejections; old receipts and archives remain unchanged. State PC
may be a next-PC value and does not itself identify a failing instruction.
The bounded static caller walk identifies `glGetInternalformativ` as the
next candidate: its loader result is zero at slot `0x758`, and the subsequent
format-init path calls that slot at `7048c114`, using GL_RENDERBUFFER,
GL_SAMPLES and capacity8. This is static attribution, not a captured fatal LR.
The new appended marker115 bridges only GL_NUM_SAMPLE_COUNTS/GL_SAMPLES,
using native validation and exact bounded output publication. It passes384
real ANGLE checks,61 NDK calls and48 native-oracle records, including the
old115 marker prefix, typed service/procedure lookup, guards and tracked writes.
Receipt: `work/gl-internalformat-qualification2/acceptance.json`, SHA256
`e8bbd6d2674bbed4d8d74491ce6794e6ce44083ad0c6ffb2ec2ce8176338babe`.
The first component attempt is preserved; its assertion incorrectly required
a zero-count format on this driver. The corrected fixture reports native
count3 for all three formats and does not claim that branch was exercised.
Capacity-zero and truncated/full-output paths are covered. Production code
is unchanged between those component attempts. The next actual startup is
`work/windows-first-frame-internalformat1`.

The preceding execution frontier was `glGetIntegerv(GL_RED_BITS=0x0d52)`, original
return `7048dafc`, is rejected before native forwarding because its width
is absent. Actual build `work/windows-first-frame-gles-core1`, host
`981cea5f75ba130ec746d0aef8f0a72ab5b38ccd`, executable
`62caf1fafe673db1abe4a56f90e3f55d4d490b600c44b3db60d006a34f53f03a`,
records224 typed GL attempts and2758 paired EGL calls. It advances through
the three indexed workgroup-size queries at indices0/1/2 and past the
capability scan. Native exit3/controller1; no draw, swap, nativeRender
return or game PNG. Saved audit:
`work/first-frame-gles-core-bit-width-boundary1/summary.json`, SHA256
`33d5898978d47cf7e9d5e3cdba7c85a62fdecb7422839b4b3c50124c538c9fcc`.
The six adjacent original queries are RGBA/depth/stencil bit counts.
Their additive width repair passes1190 actual NDK/ANGLE checks,
137 old rows preserved as a prefix of143; all graphics implementations
and fragments are unchanged. Receipt:
`work/gl-framebuffer-bit-width-qualification1/acceptance.json`, SHA256
`656d489a557627e538b6193cf1b78a06de7072d4cbf28006c972fd9abc1f057f`.
This run also requests static String fields RELEASE, ID and INCREMENTAL;
each missing-field exception is cleared before the terminal GL query.
The qualified profile now supplies `Build.ID`, `Build$VERSION.RELEASE` and
`Build$VERSION.INCREMENTAL` using each property's AOSP absent-value default
`"unknown"`. It reuses the existing VERSION class and retains SDK33 and its
field identity. The first actual NDK/JNI gate passes89 checks on each of
Linux and Windows, including old MODEL/MANUFACTURER behavior, class/type
ownership, UTF8 lifetime and the negative BRAND probe. Receipt:
`work/build-info-qualification1/acceptance.json`, SHA256
`7bab3d58a32c84b8840abdb982a0622f9fd37c6e45549a9031a22b6022bca2e2`.
No Android release or device identity is inferred. The next actual startup
build combines both repairs: `work/windows-first-frame-platform-query1`.

The preceding execution frontier was unresolved indirect graphics target0 after
`glGetIntegerv(0x90eb)`, original return `70488458`. Build
`work/windows-first-frame-gles-query-width1`, host
`d781f6afddefd2bdf61e5d5c15a6f42e4be8d726`, executable
`c47520ea749abf5377b5d0874a497c160a76f7a202eb0a6be026957fe9057990`,
passes the previously rejected three scalar SSBO widths and records204
GL entry attempts and2758 paired EGL calls. Native exit3/controller1;
there is no swap, frame PNG or nativeRender return. Static following
BLR at `70488474` loads table slot `0x5f8` with enum `0x91bf`, index0,
then repeats indices1/2. The runtime did not capture the failing guest
PC/LR; attribution of this null target remains a static inference.
Read-only audit: `work/first-frame-gles-query-width-boundary1`, summary
SHA256 `951857451feae6b4a5455791465b97e040c22bd4bb13be6138979d81ff9ddde2`.
The next provider batch covers51 observed missing GLES2 core names and
the narrow indexed compute-limit getter, appended after the old63 markers.
All six real ANGLE/NDK component gates pass: textures270 checks,
uniforms1923, framebuffer/renderbuffer168, miscellaneous290,
indexed limits88 and the expanded115-export service module192.
Receipts are `work/gl-texture-qualification2`,
`work/gl-uniform-qualification1`, `work/gl-framebuffer-qualification1`,
`work/gl-misc-qualification1`, `work/gl-indexed-qualification1` and
`work/gl-core-module-qualification1`, each `acceptance.json`.
Texture qualification1 is preserved: it expected a poisoned compressed-PBO
upload to succeed, while actual ANGLE rejects it. Qualification2 corrects
only that fixture expectation with a native error oracle and a separate
valid upload/texel comparison; production code is unchanged.
The central source projection preserves every old implementation and
query row. Source proof: `work/gl-core-composition-preparation1/source-proof.json`,
SHA256 `05c093adcb92d5f6b455d61e3b84fce1fe0467816bfdf409abf2cb91d8c1cf4d`.
These gates establish component behavior, not an original game frame.
The next actual startup build is `work/windows-first-frame-gles-core1`.

The preceding execution frontier was missing scalar query width for
`glGetIntegerv(0x90d9)`, original return `70488370`. Actual build
`work/windows-first-frame-gles-procedure1`, host
`367977430191d3e04b619c815d6e334b9cc30530`, executable
`eec19b0e2967dd01f24eb919132539d9412bed972abf4d0c747a97f665dc0df0`,
returns null from all27 optional procedure lookups and reaches the
capability scan. It records2758 paired EGL calls and201 GL dispatch
attempts; the terminal query is rejected before native forwarding.
There is no presentation, nativeRender return or frame PNG. The bounded
audit is `work/first-frame-gles-procedure-width-boundary1`.

The four identified scalar query entries are now qualified against real
ANGLE:1142 checks,137 enum rows and all three typed getter widths. The
old133 rows are an exact prefix and all other GL source bytes are exact.
Receipt `work/gl-query-width-qualification1/acceptance.json` has SHA256
`d57dc87c9210b6802c9b133315c5001cbf4b33959a6bea4a46f2a3ff61392515`.
One terminal runner CR was normalized after execution with exact AST and
single-byte proof; no functional test was replayed or claimed for that
format-only change. That repair is exercised by the build above.

The preceding execution frontier was the configured EGL procedure resolver throwing
on `glDebugMessageControl`. Actual build
`work/windows-first-frame-gles-module1`, host
`0bf472dc4f45a9ae929fe540a88685eccd4fdbd1`, executable
`84263022c5c5ce94346665dbb97b1d8e9960b4eddf5bb64f417839e890fce04e`,
now resolves the GLES module and dispatches188 real typed GL queries
(one GetString, one GetIntegerv and186 GetStringi calls). It stops at
`eglGetProcAddress`, with no drawing, swap, nativeRender return or PNG.
Original `7047363c` explicitly accepts a null result before storing the
optional debug pointer. The next repair makes the configured typed lookup
return zero for unsupported names, consistent with the
[EGL procedure-lookup contract](https://registry.khronos.org/EGL/specs/eglspec.1.5.withchanges.pdf),
while preserving known markers and the default unconfigured-resolver fence.
No debug API or callback is replaced with successful stub behavior.
The extended actual NDK/ANGLE component passes140 checks, including
known GL/EGL markers, null optional results, unchanged default fence
and pending-error behavior. The previous registry22-case results per
host are source-hash-verified and reused rather than rerun. Receipt:
`work/gl-nullable-proc-qualification1/acceptance.json`, SHA256
`71c3725f9d88db882a122a132b4292ae7ec2c77acee41410e1d00d53a4a364c9`.
The next build is `work/windows-first-frame-gles-procedure1`.

The preceding execution frontier was guest `dlopen("libGLESv2.so",2)` and its
three `dlsym` requests return zero, followed by an unresolved indirect
target0. The graphics provider already has typed `glGetString`,
`glGetIntegerv` and `glGetStringi`; the module-loader path does not yet
expose them. The final indirect caller/State was not captured, so its
exact consumer is not attributed.

Actual build `work/windows-first-frame-build-model1`, host
`7c1ecf9519cc5d5bafb180a4bf55afdfb42d9819`, executable
`49306b94f1bee1b2a836df1db9008f13bb8e3163f2580f1948a970323ec607f9`,
records2731 paired original EGL calls, including successful context and
window-surface creation, MakeCurrent and SwapInterval. There is no guest
GL dispatch, eglSwapBuffers, successful presentation, nativeRender return
or PNG. The next repair registers the existing typed GLES functions as
an explicit service module, preserving real ELF ownership/dladdr rules.
The exact run audit is `work/first-frame-build-model-gles-boundary1`.
The typed-service repair now passes130 real Windows ANGLE/NDK loader
checks, plus the unchanged22-case registry suite on Linux and Windows.
It exposes the existing63 GL markers, preserves Open/Symbol/Close, and
keeps typed-service markers outside ELF address ownership. The ordinary
incomplete-ELF catalog guard remains active. The receipt is
`work/gl-module-qualification1/acceptance.json`, SHA256
`a0e4d39898323a00760f3a118ccdec1471859cfd20849a151f78b1a17178793d`.
No GL implementations or guest objects are changed by this repair.
The next build is `work/windows-first-frame-gles-module1`.

The preceding execution frontier was missing static `android/os/Build.MODEL`
String. Build `work/windows-first-frame-fcvtzu-fixed1`, host
`3fc7304f51b6a78d9cd182a049f5f8ac4de9bc8a`, executable
`28048f7ca5104cb3f43bb7b7e32387c7cdc3539881dd819d913e94aa5e574ec0`,
reaches original native window width/height queries without an unliftable
instruction diagnostic; a direct entry/return witness for the preceding
repaired function was not captured. Actual startup exits native3/controller1
after `NoSuchFieldError: MODEL:Ljava/lang/String;` and guest `strlen`
rejects null X0, with recorded return `700f4ecc`. Original master mute
returns and9 IL2CPP constructors execute. There are still no EGL/GL calls,
nativeRender return, successful presentation or frame PNG. This requires
the reached typed Build field in the explicit absent-product-property
profile, followed by another original execution. That additive profile
extension now passes45 checks each on Linux and Windows through actual
NDK JNI callers, including typed field lookup, static String/UTF8 and
lifetime checks, MANUFACTURER regression and retained SDK33. Its receipt
is `work/build-model-qualification1/acceptance.json`, SHA256
`5d8357b570a0c4acc984d8d2f6f2e95c7d9c8acad991c7005d7bb27912fa8b83`.
The next build is `work/windows-first-frame-build-model1`; its guest code
and v10 cohort remain unchanged. The exact preceding-run audit is
`work/first-frame-fcvtzu-model-boundary2`.

The preceding execution frontier was `FCVTZU X9,S0,#10` at `70362a44`,
word `9e19d809`, reports the following PC `70362a48`. It is in original
function `70362a2c..70362a8c`, selected object123. The frozen Windows
executable `c40327523b766606112244abd7e15208d6f030704ac828d977e72c7adb71c23c`
includes the global FCSEL transport repairs and both qualified ST2
initializer repairs. Its actual muted execution passes the real focus
event gate and returns from original master mute, then exits
native3/controller1 at this conversion. There are no EGL/GL calls,
returned nativeRender, successful presentation or PNG. The four unsigned
fixed-point scalar conversion forms are now implemented, qualified and
selected in the build above. Existing
FCSEL repairs in object123 remain exact. The same function also
contains unscaled `FCVTZU X8,S0` at `70362a5c`, word `9e390008`.
Actual pinned compiled semantics dereference its numeric float carrier.
The bounded toolchain repair therefore includes numeric transport for
the four unsigned unscaled S/D-to-W/X forms, retaining the existing
integer conversion and exception helper byte for byte. Signed forms,
FP16 and vector conversions remain outside this repair.

The [conversion family gate](../whole/fcvtzu_fixed.md) matches43,008
records per ARM/Linux/Windows platform and passes531 decoder checks.
The [original-function gate](../whole/unity_fcvtzu_fixed_function.md)
matches16 cases on ARM and Windows/Linux raw/polled variants, with full
architectural captures and independent host State checks. Its zero-result
path calling real `703631a8` remains explicitly outside the dynamic gate.
Only `70362a2c` in object123 is replaced; all127 neighboring IR/native
bodies, including the existing FCSEL repair, remain exact. The v10 cohort
retains456689 heads and3576 objects and removes only this unsupported head.
Component results do not establish nativeRender return or a game image.
Both production build/runner guards pass907 cases each, including the
actual parent and new-plan file-integrity checks, in
`work/cohort-v10-validation2`. The first validation attempt preserved all
907 predicate results but stopped at a stale test-driver plan locator;
the corrected fresh run passes completely. The frozen v10 cohort is
`work/first-frame-fcvtzu-fixed-cooperative-cohort1`, acceptance
`0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5`.
The actual Windows build and execution are recorded above; these
component checks alone did not establish that outcome.

The first display-enabled build is `work/windows-first-frame-attempt1`,
host commit `e48ee60b1e920c9079fa744bddce851a39121a24`. It includes the
Windows display adapter, explicit AOSP unknown-manufacturer profile, JNI
instance long returns, and opt-in EGL/GL diagnostics and PNG capture.
The native build and focused component checks pass. Its actual muted
collector startup exits with access violation C0000005 before EGL or GL;
no image or successful presentation was recorded.

One debugger execution of that exact executable, preserved under
`work/first-frame-native-av-debug1`, identifies the failure. The original
refresh-rate wrapper `70acc13c` calls `Display.getRefreshRate()F` through
JNI slot56. It receives the actual Windows refresh rate120.0f. Original
instruction `70abccbc` (`1e281c08`, `FCSEL S8,S0,S8,NE`) selects float bits
without accessing memory. The retained generated body instead performs
`select -> inttoptr -> load i32`. It dereferences the selected120.0f bits,
`42f00000`, and faults. The frozen native fault is
`sub_70acc13c+4020`; the captured module base and native instruction agree.
This diagnoses a retained legacy FCSEL translation, not a JNI object or
long-return mismatch.

The repair reuses the already qualified FCSEL translator documented in
[fcsel.md](../whole/fcsel.md), regenerates the complete original refresh
wrapper, and replaces that body in Unity shard459. Other definitions,
guest inputs, State layout, host providers and lifecycle behavior must
remain unchanged. A focused check must cover the exact instruction with
120.0f/zero inputs and both selection outcomes before another original
startup is run. Passing that check alone does not prove game rendering.

The repaired refresh wrapper is selected in
`work/windows-first-frame-fcsel1`, host `0d019faba9514fdd09e7215592c5e2f33ec3a84e`.
Its four directed complete-wrapper cases pass on Windows and Linux in raw
and polled form, alongside the original ARM opcode check. Both build
consumers pass302 cases each. The native executable builds successfully.
The original muted startup still exits5 before any EGL/GL call and has no
frame witness or image. Its external read-only module snapshot records
actual base `7ff6bd160000`; native fault `7ff6bfcdb2ee` maps to RVA
`2b7b2ee`, `sub_704238f4+942`, after the corrected wrapper call.

That second fault maps to original `70423960`,
`FCSEL S0,S1,S0,MI`, in constructor FDE `7042377c..70423a24`.
The retained native body again dereferences selected float bits. No
register context or accessed address was captured for this run; a value
for the faulting native R8 is not inferred. The same original instruction
appears in five selected shard161 bodies: `7042377c`, `704238f4`,
`70423908`, `70423918`, and `70423928`. The next repair covers all five
together and retains the refresh-wrapper repair. A bounded inventory of
the13 declared display/metrics wrapper heads finds no remaining instance
of this legacy scalar-selection dereference there.

The five-constructor candidate preserves123 other functions in raw,
polled and native form. Its directed test executes all five selected
entries with120/0/10 inputs, checking stored refresh bits, the normal
return path, preserved registers/stack and the remaining SDK33 result
fields. Fifteen records match on Windows/Linux, raw/polled. Three
independent ARM opcode checks cover the same selection outcomes.
These use labelled controlled getter/SDK seams and establish the
candidate behavior; the next integrated startup remains necessary.

The combined repair is selected in `work/windows-first-frame-fcsel2`,
host `36db3922df5dbd0fd0fe16695f9c2918473cde9a`, executable SHA256
`50674f04a6e5d13d807e313a2cd266196107164cf75d61dd0c364ff6e896626e`.
The native build and412-case checks for each consumer pass. Its actual
startup exits native3/controller1 at `unliftable instruction707bb4bc`.
Neither earlier native access violation recurs. There are still no
EGL/GL calls, successful presentations, returned nativeRender or frame PNG.

The reported PC is the next PC after original `707bb4b8`, word `4c008d80`,
`ST2 {V0.2D,V1.2D},[X12]`. The decoder currently rejects this multiple-
structure store; the latest qualified toolchain has no matching selector.
Original FDE `707bb458..707bb55c` initializes a0x498-byte object with a
finite interleaving loop and no calls. Only head `707bb458` is selected
in shard270. The run has no captured dynamic caller/thread context for
this instruction, so a returned display constructor is not inferred.
Proper ST2 translation and ARM memory/writeback reference checks are the
next prerequisite. The original bytes and read-only attribution are in
`work/first-frame-st2-audit1`.

ST2 is now implemented and qualified for the seven valid multiple-structure
arrangements and three addressing modes. The family gate matches1120 ARM,
Linux and Windows records,685 decoder checks and70 raw full-State checks
per host. The original object initializer matches16 cases across ARM and
Windows/Linux raw/polled execution. Only its body in shard270 is replaced;
the other127 functions remain exact. See [the ST2 gate](../whole/st2.md)
and [the original initializer gate](../whole/unity_st2_object.md).

The selected build `work/windows-first-frame-st2-1` uses host
`f8298953bace6cd5ea97c5f3a9278c09c3ce48a1`, executable SHA256
`44215a6da838aedbfecea888c0db554d08e40152350d9f8d2ea0b631f6b91bdc`.
Its native build and520-case checks per consumer pass. Original startup
still exits native5/controller1 with no EGL/GL calls, nativeRender return
or PNG. The earlier unliftable ST2 record does not recur. Actual base
`7ff6d8d70000` maps fault `7ff6e47125fe` to RVA`b9a25fe`,
`sub_70a01d00+3198`. The current fault is another retained FCSEL lowering:
original `70a01e34`, `FCSEL S0,S2,S1,EQ`, in FDE
`70a01d00..70a01e6c`, shard353. Native R12/accessed address and a dynamic
caller stack were not captured; their values are not inferred.

The next repair inventories remaining selected FCSEL implementations as a
group. Each proposed body must prove a FCSEL-only delta against its current
selected body, with existing ST2/EXT/prefetch repairs and neighboring code
preserved. A single batch replaces admitted bodies; unrelated differences
remain excluded. This addresses the common legacy defect across the
selected code rather than fixing only the newest caller.

The completed inventory identifies 5,766 faulty copies in 2,164 functions
across 556 objects. A full fresh-proposal pass generates all 556 modules but
holds 304 function comparisons; none is selected. The separate
[exact transport repair](../whole/fcsel_batch.md) changes only each
erroneous scalar-load line, retaining the original predicate, SSA names,
upper clear and all other bytes. Its 32 focused checks and real LLVM module
parses pass. All 5,766 original conditions pass evaluation for all 16 NZCV
combinations (92,256 checks, zero unknowns), and all 2,164 candidates pass
their inverse checks. All 556 objects compile. Native preservation is
byte-exact except nine constant-pool relocation addends in seven unchanged
functions of object2598. A separate saved-object check proves identical
resolved data, required alignment and every other instruction byte; the
original failed comparison remains preserved. Raw and polled neighboring
bodies stay exact. Final cohort validation and integrated startup remain
separate gates; these results do not establish a frame.

That batch is selected in `work/windows-first-frame-fcsel-batch1`, host
`55056035c9f77e52c4bb5de27d1bfec8278e85fb`, executable SHA256
`d3f499bfa14c59a7d8827695098edb986a687bfb0c7a96df5fc9181d0fbf075c`.
Its actual original startup exits native3/controller1 at reported
`70752174`, with the first-frame witness false. The original previous word
is `4c008d40` at `70752170`: ST2 2D/base through X10, already supported by
the held ST2 tool pair. The following instruction is a supported B.NE.
The next prerequisite is applying the existing translation to this
retained original function, with current FCSEL repairs preserved. The
exact reached word still needs its function-specific execution check;
no repeat of the generic ST2 family campaign is required.

The constructor repair is now qualified in
[the original-function gate](../whole/unity_st2_constructor.md). It
replaces only `707520c4` in object 249 and preserves all 127 neighboring
functions in raw, polled and complete native code. Sixteen cases match
across the untouched ARM64/Bionic function and Linux/Windows raw/polled
translations, including genuine memset effects, every object byte,
allocation canaries, normal return and the declared ABI-defined register
subset. The current FCSEL vector remains selected. Its new loop adds one
cooperative poll site; the complete cohort retains 456689 heads and removes
only this unsupported head. All 794 v9 guard cases pass in each of Python
and PowerShell. Build `work/windows-first-frame-st2-2` links successfully
under host `089a79354540b707fff7c53057749c3ace72470f`. Its first execution
times out waiting for a real Windows focus event before engine resume;
that execution alone does not establish progress through the repaired
constructor. A fresh observational run of the same frozen binary and
inputs, `work/windows-first-frame-st2-focus1`, passes the real focus gate
and reaches the fixed-point FCVTZU frontier above. It completes417 Unity
constructors/JNI and9 IL2CPP constructors; original master mute returns.
The earlier unsupported ST2 no longer terminates this execution. The
exact frontier audit is `work/first-frame-st2-focus-fcvtzu-boundary2`.

The next host build also expands only the native Crash handler's logging
to include the actual module base, thread, accessed address/operation and
x64 register context. Its MinGW syntax check passes, and reversing that
single function span recovers the previous source byte for byte. This
supports diagnosis from the next original execution without assuming a
faulting register's value.

First-frame acceptance requires an image captured from the original GL
window framebuffer, original drawing activity, a successful original
`eglSwapBuffers`, and a returned original `nativeRender`. A synthetic
triangle or clear-only surface is not evidence of a game frame. The
`--first-frame` diagnostic preserves the image and holds the real window
for ten seconds when its witness succeeds. Audio stays explicitly muted
while the HDMI endpoint is unavailable.

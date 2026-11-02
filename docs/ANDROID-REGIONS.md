# Android 3.7.1 regions

The CLI and web builder use the same region profiles in
`android/tools/game_patch.py`. Region selection is automatic: the APK's compiled
manifest supplies its package and version, then SHA-256 identifies both original
`libil2cpp.so` and `global-metadata.dat`. An unknown or mixed pair is refused
before an output APK is written. Renaming an APK does not affect detection.

| Client | Package | Status |
| --- | --- | --- |
| Global, English/Korean | `com.square_enix.android_googleplay.nierspww` | Korean gameplay, notices, ten-pull and broad menu smoke test checked on emulator |
| Japanese | `com.square_enix.android_googleplay.nierspjp` | Experimental; gameplay, ten-pull, Arena battle and broad menu smoke test checked on emulator |

Both inspected APKs report version **3.7.1**, version code **152**, ARM64.
The [Korean/English QooApp listing](https://m-apps.qoo-app.com/en-US/app/17449)
identifies the same `nierspww` package as the global release. A separate
`nierspkr` binary has not been found or assumed. Choosing Korean in the global
client uses the global patch profile. This change does not translate Bunker's UI
or its recovered English notices.

## Checked binaries

| SHA-256 | Global | Japanese |
| --- | --- | --- |
| `libil2cpp.so` | `ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522` | `37a0335eb3eef53610c0cfab41ee4e210d5f1eb363d3ddd417845996e2643cda` |
| `global-metadata.dat` | `7ae75b594082b3a603a82f68d497d6c3aea30881b94496b2c11d8de71f8321d2` | `6004b4008cbe633b4391f8c86327564e337995a1336e4f35c98e1cc849acc048` |

The [Japanese 3.7.1 listing on APKMirror](https://www.apkmirror.com/apk/square-enix-co-ltd/nier-reincarnation-2/nier-reincarnation-2-3-7-1-release/nier-reincarnation-3-7-1-android-apk-download/)
reports APK SHA-256 `25b6326c610290dd1f581fc3b41e60efb1126172aae45804d5345caa0b653609`.
Players still supply their own APK, master data and resources. None of these
private inputs or the IL2CPP dumps are included in Git or the published builder.

## Changes

- Regional RVAs cover gRPC credentials, encryption passthrough, Octo plain
  lists, purchase checks, the title menu, all three gRPC-port overrides and
  offline reachability. Writes map RVAs through executable ELF load segments.
- Force the API hostname getter to use the patched metadata default. Japanese
  serializes `api.app.nierreincarnation.jp` in a Unity asset, which otherwise
  overrides that default and sends login to the original server. Patch the
  original port getter instead of its four-byte branch wrapper, preserving the
  adjacent method and supporting callers of either getter.
- Endpoint edits operate on whole IL2CPP string literals. Japanese `.jp`
  addresses, including its credential-bearing web literal, become loopback
  URLs without retaining or logging the credentials. All four required endpoint
  kinds must be found. Port offsets work on both profiles.
- Binary manifests preserve the source package, resolve relative and unqualified
  launcher activities against it, and use its package for provider authorities.
  Updates repeat this operation from the preserved original manifest.
- Native display, frame timing, story-event, scrolling, text-buffer and
  remaining-day patches use 98 Japanese RVA mappings. Runtime region selection
  checks the `il2cpp_init` export RVA before applying game patches; individual
  instruction checks still apply. Seven patch entries require region-specific
  original or replacement words.
- Japanese has no `IronSource` methods in the decoded method map. The global
  roulette-ad hook is skipped on Japanese, rather than touching unrelated code.
  Japanese roulette behavior remains unverified. Facebook Android telemetry
  methods are also absent in the Japanese method map; its seven Unity
  Analytics, Crashlytics and Adjust entry points have separately checked guards.
- `GAME_PATCH` is 2. Builds with the previous patch revision require rebuilding
  through the web builder before later in-place updates.
- Merged APKs use the Bunker label and emblem icon, including component
  overrides. The direct binary builder adds a drawable type to the existing
  game resource package, preserving original IDs, strings and styles. Keeping
  the icon in that package matters: Firebase discovers its resource package
  from the application icon, and a separate icon package breaks startup.
- CLI builds fetch the pinned notice pack when absent; web builds require it
  and fail clearly if it cannot be downloaded. Both packaging paths record its
  hash for later updates. Launcher bundles carry their game-patch revision so
  a new builder cannot silently embed an outdated on-device updater.

Method addresses were resolved with [Il2CppDumper 6.7.46](https://github.com/Perfare/Il2CppDumper/releases/tag/v6.7.46),
matching method name and full signature (normalizing generated MethodInfo RVA
suffixes). Purchase branch sites were disassembled in both binaries: the
initialization checks, null-store cancellation and alert-skip targets retain the
same control flow. Japanese BattleUpdate adds two instructions before the
hooked tail; its actual matching four-word sequence is at `0x29AFF7C`, not the
same offset within the method. The event collision fields used by the runtime
hooks retain the same offsets in both dumps. Unity's `dlsym` and
`eglGetProcAddress` relocations are at the same checked GOT offsets in both
libraries; Firebase's library hash is identical.

To reproduce the runtime map, put each original library, metadata file and
Il2CppDumper `dump/script.json` in separate private directories, then run:

```sh
python android/tools/derive_region_rvas.py --global-dir /private/global \
  --jp-dir /private/jp --output /tmp/game_region.h
```

## Validation and remaining work

Build validation:

- Regional tests passed against both original APKs, including default ports,
  offset 30000 and maximum offset 57455, manifest identity, runtime instruction
  guards, signing, and updates preserving the patched game files.
- The web build driver completed under **Pyodide 0.28.3**, the worker's pinned
  runtime, using both real APKs, the original `20240404193219.bin.e`, the pinned
  notice pack and a complete launcher/server built from this branch. Both APKs passed ZIP
  CRC checks, Android `apksigner` v2 verification and `zipalign -c -P 16 4`.
- Android `assembleDebug` and `lintDebug` passed. Thirty-four Android Python tests passed,
  including private-input regional build/update checks, resource branding and
  missing-notice rejection and the existing updater suite. Seventeen release-script
  tests and the generated site's local import closure also passed.
- The native library compiled with `-Wall -Wextra -Werror` using the available
  Android NDK 30 ARM64 compiler. The release build remains pinned to NDK 27.
- Web bundle import checks passed, including the shared patch module. Release
  unit tests include the synthetic regional tests; private-input checks are
  opt-in.

Run the private-input tests with:

```sh
export BUNKER_GLOBAL_APK=/private/global-3.7.1.apk
export BUNKER_JP_APK=/private/jp-3.7.1.apk
cd android/tools
python -m unittest test_game_regions -v
```

## Emulator validation, November 3, 2026

ADB testing on the existing BlueStacks Pie64 / Android 9 installation exposed
two problems not caught by packaging checks: Japanese's serialized API hostname
still reached the original server, and the old eight-byte port patch overwrote
the first instruction of the adjacent getter. The shared patcher now fixes both;
the private-input tests check the exact host branch and preservation of the
four-byte port wrapper. Both APKs were rebuilt through Pyodide after the fix.

Japanese then completed local registration, loaded the global master data and
revision-0 resource list, accepted a test player name, loaded Japanese text and
the opening sequence, rendered the first 3D scene, responded to ADB movement,
and advanced quest scene progress from 3 to 4. Restarting in 60 fps mode reported
`display.status=ok` and resumed that scene. This checks applying the mode, not
a measured sustained frame rate. These checks used the normal native library;
temporary startup tracing was removed before validation.

The global APK also completed local login and loaded the opening sequence. To
check its Korean path, Android's locale was temporarily set to `ko-KR` and only
the test player's saved text/voice language choices were reset, allowing the
client's normal system-language detection to run. The title menu and opening
story rendered Korean; ADB movement advanced the 3D scene from 3 to 4, and
`CheckBeforeGamePlay` reported `textLang=23` and
`voiceLang=23`. The Japanese client reported language 22. Both APKs use the same
original global master and revision-0 resource dump in this test.

During resource loading and gameplay, an Android OUTPUT rule blocked the test
app UID's non-loopback traffic. The rule recorded rejected packets while local
game requests continued. BlueStacks presents its virtual Ethernet as connected
Wi-Fi even with airplane mode set, so this is an app-level Internet-blocking
test, not proof of a physical phone's radio state.

The existing global save and preferences were backed up before installation
and restored afterward; all 15 restored file hashes match the original backup.
The test save is retained separately. The temporary firewall rules, Korean
Android locale and Japanese 60 fps override were removed after testing, and
airplane mode was restored to off.
Game resources were shared read-only by application convention from the existing
host folder; no second 21 GB import was needed. Screenshots, PID-filtered logs,
the private backup and rebuilt APKs remain under `.build/regions/`, outside Git.

Still required before promoting Japanese out of experimental: physical-device
radio-off checks, extended story/battle/purchase/summon testing at 30 and higher
frame rates, and coverage of regional content differences. These smoke tests
do not establish full campaign compatibility.

## Unlocked-save screen audit

The original saves and preferences were backed up before creating test copies.
The test players received gems, cleared main-quest flags and completed tutorial
flags so the menus could be opened without playing the campaign. First-time
guides and announcements were marked seen in the later fixtures. These are
modified test saves, not evidence that natural campaign progression unlocks
every screen correctly. The emulator now retains these unlocked test saves;
the original directories remain under each app's `screen-tests-original/`,
with additional host tar backups under `.build/regions/screens/`.

- Japanese's initial screen audit covered premium/character/event summons,
  rates and box-prize details, organization/equipment, character and weapon
  enhancement lists, story/sub/EX quest selection, Subjugation, Arena,
  Exploration, map, library/collection, profile/settings/help, gifts, missions,
  pass, friends and all three shop lists. A ten-pull added ten weapons and spent
  3,000 free gems; a full Arena battle returned a loss result and updated rank.
  This initial broad pass used the previously published launcher/server with
  this branch's game/native patches, before the packaging audit.
- The packaging audit found the missing optional notice pack, unchanged game
  branding, and the ability to mix a newer builder with an old embedded updater.
  Those paths are fixed. Both APKs were then rebuilt through Pyodide with the
  complete launcher/server from this branch, and installed through ADB.
- Japanese's full-build pass rendered the notice list and an article image from
  both the title menu and game menu. A refreshed unlocked fixture copied from
  the Korean test player, with Japanese authentication identity retained, opened
  Mama's menu and completed another premium ten-pull. Organization, enhancement,
  quest selection, Subjugation, library and Missions were checked again. The
  draw added ten weapons (13 to 23), spent 3,000 free gems, left paid gems
  unchanged and passed SQLite integrity checking afterward. The
  older modified Japanese fixture had unreliable Mama-menu navigation; the
  refreshed fixture passed on the same APK. Keep natural-progression testing
  separate from these manually constructed saves.
- Korean's full-build pass rendered notices, thumbnails and an article image
  in the game's WebView. Premium ten-pull 59/592 added ten weapons (3 to 13),
  spent 3,000 free gems and left paid gems unchanged. The global-only offline
  roulette also completed and awarded 50 gems. Organization, weapon details,
  enhancement materials, quests, Subjugation, Arena, Exploration, map, library,
  menu/profile, missions, gifts, friends and item shop rendered Korean text.
  SQLite integrity passed after these transactions.
- The Bunker emblem icon rendered for both installed packages on BlueStacks'
  home screen. Its existing shortcuts retained their cached `NieR` titles;
  APK application and component labels are `Bunker`.
- Both clients' Pod Programs loaded; Japanese listed the active test player. Archive
  opened and began indexing the resource dump; full Archive browsing was not
  tested in this pass. Temporary app-UID network rules were removed after
  gameplay checks, and both test saves were archived again on the host.

Remaining visible gaps: Subjugation's season label is `unknown` in both Japanese
and Korean. Japanese also showed `unknown` in the Arena result heading and the
fourth Missions tab (Korean renders that tab as Collection Bonus). These text
gaps are not fixed by the regional binary patches. Notices are the recovered
English archive, not Japanese/Korean translations. Exploration was opened but
its minigames were not played; shop lists were opened without purchases. The
screen smoke tests do not cover every quest, event, draw type or transaction.

## Rebased 1.7.0 verification

Rebased onto `1db7b5f` from `origin/main`, preserving its streaming APK writer,
privacy patches and newer native features. Japanese has seven guarded privacy
sites; the Facebook Android and IronSource methods patched in Global are absent
from the Japanese binary. All 98 native RVA mappings and seven instruction
overrides were derived from the matching original 3.7.1 binaries.

The in-game Bunker button initially disabled itself on Japanese because Unity's
two-argument `ImageConversion.LoadImage` wrapper was stripped. Both clients
retain the three-argument overload; the button now calls that overload with
`markNonReadable=false`. ADB confirmed the emblem and button in Japanese and
that tapping it opens the launcher.

The final companion passed Android assembly and lint. The Android tooling suite
ran 67 tests with seven skips; release/version/notice tests ran 18 tests, and the
web import test passed. Real original Japanese and Global APK fixtures were
supplied to the regional packaging tests. Both complete APKs were rebuilt with
Pyodide 0.28.3 through both file and streaming output paths, including the pinned
notice archive and Bunker branding. Both passed APK v2 signature and 16 KiB
alignment checks and were reinstalled through ADB for a final login, notices,
summons-menu and Bunker-button smoke test. The broader screen/transaction audit
above remains a separate earlier pass; this verification does not establish
full campaign compatibility.

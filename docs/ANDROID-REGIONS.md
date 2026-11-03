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
The Korean/English release uses the same `nierspww` package as the global
release. A separate `nierspkr` binary has not been found or assumed. Choosing Korean in the global
client uses the global patch profile. This change does not translate Bunker's UI
or its recovered English notices.

## Checked binaries

| SHA-256 | Global | Japanese |
| --- | --- | --- |
| `libil2cpp.so` | `ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522` | `37a0335eb3eef53610c0cfab41ee4e210d5f1eb363d3ddd417845996e2643cda` |
| `global-metadata.dat` | `7ae75b594082b3a603a82f68d497d6c3aea30881b94496b2c11d8de71f8321d2` | `6004b4008cbe633b4391f8c86327564e337995a1336e4f35c98e1cc849acc048` |

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
- `GAME_PATCH` stays 1. For Global, the shared patcher differs from the old one
  only at the port getter (now patched without touching the next method) and
  the API host branch (Japanese only needs it); both old builds keep working,
  and in-place updates re-apply the privacy patches, so Global and iOS
  players update in the app.
- CLI builds fetch the pinned notice pack when absent; web builds require it
  and fail clearly if it cannot be downloaded. Both packaging paths record its
  hash for later updates. Launcher bundles carry their game-patch revision so
  a new builder cannot silently embed an outdated on-device updater.

Method addresses were resolved with Il2CppDumper 6.7.46,
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

## Known gaps

Japanese support is experimental: login, opening gameplay, summons, an Arena
battle, notices and the main menus were checked on an emulator, not a full
campaign or a physical phone with its radios off. Subjugation's season label
shows `unknown` in Japanese and Korean, as do Japanese's Arena result heading
and fourth Missions tab. Notices are the recovered English archive, not
Japanese or Korean translations. Japanese has no video-ad roulette hook; its
roulette behaviour is unverified.

## Japanese master-data missions

Mission rules are selected from the loaded master data, independently of the
client's language or package. The Japanese `20240405123139.bin.e` reuses some
Global mission IDs for different conditions. The server checks the condition
type, counter group and both filter groups before applying a rule. It reuses a
counter's rule only when its filters are unambiguous, and supplies verified
Japanese variants for the shifted costume/weapon skills, mission-pass quests,
Flying Mama scores and seven Japanese-only stamina missions.

When a rule changes, unclaimed progress from the previous interpretation is
reset before it can pay a reward. State-based missions are evaluated again from
the save; counted actions start from zero because the old counter cannot prove
which actions satisfied the new condition. Received rewards remain received.
The save records these revisions so reopening the game does not reset valid
new progress, including after changing master-data regions.

The Japanese master has no Collection Bonus mission rows. Loading it does not
restore that feature. The Japanese client also omits the Collection Bonus
list code retained by Global; Global master data can expose its `unknown` tab
in Japanese without making the collection list work. Japanese profile-comment
mission 7011 remains unsupported: its option 394 has no verified required
phrase in the rule source, so it does not inherit Global's English option 392.

With Everything open, both masters still expose 21 historical stamina missions
worth 3 million coins each. This can pay 63 million coins once. Regional rule
selection does not change those original rewards or their patched dates.

## Tests

Run the private-input tests with:

```sh
export BUNKER_GLOBAL_APK=/private/global-3.7.1.apk
export BUNKER_JP_APK=/private/jp-3.7.1.apk
cd android/tools
python -m unittest test_game_regions -v
```

For server mission tests against the private master files (neither is modified):

```sh
export BUNKER_TEST_JP_MASTER=/private/20240405123139.bin.e
export BUNKER_TEST_GLOBAL_MASTER=/private/20240404193219.bin.e
python scripts/prepare.py
cd server
go test ./internal/missions ./internal/store ./internal/userdata ./internal/interceptor ./internal/service
```

The November 3, 2026 checks exercised the supplied Japanese master, its normal
content patch and a patched Global control on a copied Japanese emulator save.
The real local gRPC server returned mission and inventory diffs, the weapon
level no longer completed Japanese costume mission 1166, the 63-million payout
remained one-time, and SQLite integrity passed. These server checks do not
establish game UI or full campaign compatibility with Japanese master data.

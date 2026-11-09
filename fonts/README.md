# Fonts

Letters the game's own fonts lack, added to them when Bunker is built
(`android/tools/game_fonts.py`; the APK, IPA and browser builders all do it).

- `noto/`: subsets of Noto Sans, Noto Serif and Noto Sans SC, under the SIL
  Open Font License 1.1 (`noto/OFL.txt`). `noto/sources.json` names the
  google/fonts commit and the hash of each file they were made from.
  - `NotoSans-400.ttf`, `NotoSans-600.ttf`, `NotoSerif-400.ttf`: Latin
    Extended (Polish, Czech, Turkish, Vietnamese…), Greek and Cyrillic. They
    replace the game's own glyphs for these letters, so Cyrillic and Greek get
    normal widths.
  - `NotoSansSC-400.ttf`, `NotoSansSC-600.ttf`: the Simplified Chinese
    characters Japanese does not use. Characters shared with Japanese keep the
    game's glyphs.

Regenerate them with `python3 scripts/make_noto_subsets.py` (add `--commit SHA`
to move to another google/fonts commit). No game file is kept here.

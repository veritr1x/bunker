# Translations

Text for playing the game, and using Bunker, in languages the game never had.

## What is here

- `game/<area>/`: the game's own text, split by area (`ui`, `skill`, `ability`,
  `possession`, `quest`, `mission`, `shop`, `library`, `story_main`, `story_sub`,
  `story_side`).
- `master/`: a few texts from the game's master data (the shop mascot's
  lines, cut-ins, gift messages, mission titles and flavour). Bunker puts them
  into the game data when the language is chosen, and takes them out again for
  English. Bunker's own Gift Box sender ("From Bunker, with love.") is
  `pods.gift.sender_in_game` in `bunker/`.
- `bunker/`: Bunker's own screens, Pod Programs and the Archive (see
  "Bunker's own screens" below).

In each folder:

- `en.json` is the English text, the template you translate from. In `game/`
  and `master/` it is generated from the game files by
  `scripts/export_translations.py`; never edit it by hand.
- `ja.json` and `ko.json` are the game's own Japanese and Korean text, kept for
  context. They are not translations to work on.
- `<language>.json` (for example `pt-BR.json`, `pl.json`) is a translation.

## Translating

A translation file is flat JSON: the same keys as `en.json`, each with its text
in your language.

```json
{
  "gift.comment.3": "Enviado pela administração.",
  "ui.Outgame.Footer.Quest": "Missões"
}
```

- Leave out a key, or leave it empty, and the game shows the English text.
  A partial translation is fine.
- Keep these exactly as they are in the English (their order may change):
  - tags such as `<i>`, `</i>`, `<br>` and `<align="right">`,
  - placeholders such as `{0}`, and any other `{` or `}`.
- Line breaks in `game/` files: put them where your language needs them,
  written as `\\n` (two backslashes in the file, as in `en.json`). A single `\n`
  would put a real line break in the text, which the game cannot use.
  `master/` texts are different: they use real line breaks (`\n`, as in their
  `en.json`).
- Never edit `en.json`, `ja.json` or `ko.json`: they are made from the game.
- Keep translations about as long as the English where you can: the game's
  menus have little room.
- The game can only show letters its fonts have; others appear as empty boxes.
  Latin (including Polish, Czech, Turkish and Vietnamese), Cyrillic, Greek and
  Simplified Chinese work. The check names any character the fonts cannot show.
  Type accented letters as single characters (as most keyboards do): an accent
  typed as a separate mark after its letter shows beside it, and the check
  refuses it.
  Scripts written right to left or with joined letters (Arabic, Hebrew, Thai,
  Hindi) are not supported yet.

## Bunker's own screens

`bunker/en.json` holds the words of Pod Programs, the Archive and the Android
and iOS launchers, written by Bunker's developers. Translate it into `bunker/<language>.json` like the other
folders, with a few differences:

- Keys say where a text is shown: `pods.<page>.<name>` (Pod Programs),
  `archive.<page>.<name>` (the Archive), `launcher.<area>.<name>` (both
  launchers: their screens, ⋮ menus, dialogs and notification;
  `launcher.ios.<area>.<name>` is shown on iPhone and iPad only), `common.<name>`
  (words all of them use, such as Save or Close), `ingame.<page>.<name>` (pages
  Bunker's server shows inside the game: the summon details, the notices' tabs
  and labels, the panel mission sheets). A key ending in `_info` is
  the explanation behind an "i" icon.
- The notices themselves (their titles and articles, recovered from the
  original game) stay in English; only the words around them are translated.
- Write labels in normal case ("Game files"): where a screen shows capitals,
  Bunker capitalises them the way your language does (Turkish "İ").
- Placeholders are names in braces, such as `{name}` or `{n}`: keep each one,
  in whatever place your language needs it. `{n}` is a number, already
  written your language's way ("1.200" in German, "1 200" in French) from the
  pack's `language`; a `%` sign in a text is yours to place ("45 %").
- Keys ending in `.one` and `.other` are a counted text: "{n} costume",
  "{n} costumes". Give every form your language uses for whole numbers, using
  the plural categories of the Unicode CLDR (`zero`, `one`, `two`, `few`,
  `many`, `other`): Polish needs `.one`, `.few` and `.many`; Russian `.one`,
  `.few` and `.many`; Arabic all six; Japanese only `.other`. A form may leave
  out `{n}` ("one costume"). If a form your language needs is missing, the
  English text is shown for every count.
- These texts are shown with the phone's own fonts, so any script works.
- Keep them short: buttons, menu entries and labels have little room.
- A missing or broken translation (a placeholder dropped or misspelled) shows
  the English text instead.
- The lines "End of transmission // Glory to mankind" and "Operator link //
  Standing by", and the launchers' captions such as "LUNAR TEAR // 127.0.0.1",
  are not in the catalogue: they stay in English.

## Sending your translation

1. Fork the repository and add or edit `<language>.json` files in the folders
   you translate. Only add keys that are in that folder's `en.json`.
2. A new language also goes in `languages.json`, with its own name and
   `"ship": false`:

   ```json
   {"pt-BR": {"name": "Português (Brasil)", "ship": false}}
   ```

   The maintainer sets `"ship": true` when the language goes into a Bunker
   release.
3. Check your files before you send them:

   ```sh
   python3 scripts/check_translations.py
   ```

   It prints one line per problem (file, key, what is wrong), or
   "Translations OK". The same check runs on every pull request.
4. Send a pull request.

To try a translation in the game before it ships, build its language pack:

```sh
python3 scripts/language_packs.py pt-BR
```

That writes `pt-BR-pack.json`. Copy it to your phone and load it in Bunker's
Pod Programs › Language › Load a pack, choose it, and keep the game itself set
to English.

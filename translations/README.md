# Translations

Text for playing the game, and using Bunker, in languages the game never had.

## What is here

- `game/<area>/`: the game's own text, split by area (`ui`, `skill`, `ability`,
  `possession`, `quest`, `mission`, `shop`, `library`, `story_main`, `story_sub`,
  `story_side`).
- `master/`: a few texts from the game's master data (gift messages,
  announcements and similar).

In each folder:

- `en.json` is the English text, the template you translate from. It is
  generated from the game files by `scripts/export_translations.py`; never edit
  it by hand.
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
- Keep these exactly as they are in the English:
  - `\\n` as it appears in the file: the game's line break. In the JSON it is
    written with two backslashes; a single `\n` would put a real line break in
    the text, which the game cannot use,
  - tags such as `<i>`, `</i>` and `<align="right">`,
  - placeholders such as `{0}`.
- Keep translations about as long as the English where you can: the game's
  menus have little room.
- Letters the game's fonts cannot show appear as empty boxes. Latin, Cyrillic
  and Greek letters work; support for more letters is being added. Scripts
  written right to left or with joined letters (Arabic, Hebrew, Thai, Hindi) are
  not supported yet.

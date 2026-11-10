# Contributing a translation

NieR Re[in]carnation only ever spoke English, Japanese and Korean. Bunker can
show it in any language whose letters the game's fonts have, and everything
needed is a set of plain text files in [`translations/`](translations/). You
don't need to build anything or know how to code: if you can edit a text file
and use GitHub, you can translate.

This page walks you through it. The rules for the files themselves (which keys,
placeholders, plural forms, line breaks) are in
[`translations/README.md`](translations/README.md); read it before you start.

## 1. Say what you are working on

Open an issue titled `Translation: <language>` (for example
`Translation: Português (Brasil)`) and say which parts you plan to do. Someone
may already be working on that language: an issue lets you share the work
instead of doing it twice, and agree on how to say the game's recurring words
(see "Keep it consistent" below).

## 2. Pick where to start

Each folder is a part of the game, and you can send them one at a time. A
partial translation is fine: anything you leave out stays in English.

| Folder | What it is | Size |
|---|---|---|
| `bunker/` | Bunker's own screens: launcher, Pod Programs, the Archive, pages inside the game | about 1,800 texts |
| `game/ui/` | The game's menus, buttons, help titles and messages | about 5,500 |
| `master/` | Mama's lines in the shop, cut-ins, gift messages, mission titles | about 1,600 |
| `game/possession/` | Names and descriptions of costumes, weapons and items | about 9,600 |
| `game/mission/`, `game/quest/` | Missions and quests | about 11,600 |
| `game/library/`, `game/story_*/` | The Library and the story | about 24,000 |
| `game/shop/`, `game/ability/`, `game/skill/` | The shop, abilities and skills (much of it repeats with other numbers) | about 92,000 |

A good first pull request is `bunker/` or the menus in `game/ui/`: small, and
seen on every screen.

## 3. Translate

A translation is a file named after your language next to the English one: for
example `translations/game/ui/pt-BR.json` next to `translations/game/ui/en.json`.
It holds the keys you translated, each with your text:

```json
{
  "ui.Outgame.Footer.Gacha": "Invocações",
  "ui.Outgame.Footer.Library": "Biblioteca"
}
```

Use a language code such as `pl`, `de`, `pt-BR` or `zh-Hans`. In `game/` and
`master/`, `ja.json` and `ko.json` beside `en.json` are the game's own Japanese
and Korean: use them for context when the English is unclear. Don't edit them,
or any `en.json`.

**In the browser, with no tools:** open the folder on GitHub, choose
**Add file › Create new file** (or open your existing file and press the pencil
to edit it), and paste your text. GitHub makes a copy of the project for you
(a fork) and offers to open a pull request when you save.

**With git:** fork the repository, clone your fork, add or edit the files, and
push to a branch.

The first time you add a language, also add it to
[`translations/languages.json`](translations/languages.json) with its name in
its own language and `"ship": false`:

```json
"pl": {"name": "Polski", "ship": false}
```

## 4. Check it

Every pull request that touches `translations/` is checked automatically. You
get one line per problem: the file, the key, and what is wrong (a placeholder
missing, a tag left out, a plural form your language needs, a letter the game's
fonts can't show). Fix those lines and push again; the check runs again.

To check before you send, with Python 3.11 or newer:

```sh
python3 scripts/check_translations.py
```

## 5. See it in the game

You can try your translation before it ships:

1. Build a language pack: `python3 scripts/language_packs.py pt-BR` writes
   `pt-BR-pack.json`. (If you can't run Python, say so in your pull request and
   a maintainer will send you the pack.)
2. Copy the file to your phone.
3. In Bunker, open **Pod Programs › Language › Load a pack**, then choose it.
4. Keep the game itself set to **English**: a pack replaces the English text.
5. Start the game. It downloads the translated text from Bunker, on the phone.

Look for text that is too long for its box, wrong line breaks, and words that
read oddly in context. Screenshots in your pull request help reviewers.

## 6. Send the pull request

Title it `Translation: <language> — <folders>` (for example
`Translation: Polski — bunker, game/ui`). In the description, say what you
translated, and anything you weren't sure of. A reviewer who speaks the
language may suggest changes in the pull request; it is merged when the check
passes and it reads well.

A language goes into a Bunker release when a maintainer sets `"ship": true`
for it, usually once its menus and Bunker's screens are done. Until then
players can load its pack themselves.

## Keep it consistent

- **Recurring words:** agree in your issue how to say the game's own words
  (Mama, The Cage, Memoirs, Dark Scarecrows, Exalt) and use the same word
  everywhere. Character names usually stay as they are.
- **Length:** the game's menus have little room. Prefer the shortest natural
  word; check long ones in the game.
- **Tone:** Mama is warm and a little teasing; the story is quiet and sad.
  Translate the voice, not word for word.
- **What stays English:** the NieR flavour lines such as "LUNAR TEAR //
  127.0.0.1", "Operator link // Standing by" and "End of transmission // Glory
  to mankind" are not in the files; they stay in English in every language.

## What can't be translated yet

- The text inside each **Help** page: each page is its own game asset with its
  words built in, not in the text files. The Help screen's titles can be
  translated.
- The **notices'** articles, recovered from the original game. Their tabs and
  labels can be translated.
- Languages written **right to left** or with **joined letters** (Arabic,
  Hebrew, Thai, Hindi): the game's text engine doesn't lay them out yet.

## Questions

Open an issue. Mention the file and key you are asking about, for example
`game/ui/ui.Outgame.Footer.Gacha`.

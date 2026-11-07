# Pod Programs on a phone on its side

## Why

On a phone held sideways, Pod Programs shows only a few lines of each page. On the
emulator (914 × 411 dp) the page gets 864 × 311: the status bar (27 dp), the app's own
"POD PROGRAMS / CLOSE" bar (48 dp), the gesture bar (24 dp) and a black strip beside
the camera hole (50 dp) take the rest. Every page then stacks title, intro, controls and
content, so the content starts at the bottom of the first screen while the width is
half empty. Approved with the mockup in the session (local, not published).

## Goals

- The page gets the whole screen, and each page uses the width: what it shows before its
  content stays beside the content instead of above it.
- No black bar beside a camera hole or notch; only what would sit under it steps aside.
- Portrait, tablets and unfolded phones look as they do today.

## Non-goals

- The Archive (its own pages and base template) keeps its current layout.
- No change to what any page does; only where things sit.

## When it applies

A phone on its side: landscape and less than 600 dp tall. On Android, ToolsActivity's
existing `compact` test (`ORIENTATION_LANDSCAPE && screenHeightDp < 600`); on iOS a
compact vertical size class; in the pages `@media (orientation: landscape) and
(max-height: 599px)`, which replaces the 540 px query (the page's height is the screen's
once the bars are gone, so the two agree).

## The app (Android ToolsActivity, iOS LTToolsViewController for Pod Programs only)

- The top bar is not shown; the WebView fills the screen.
- The status and navigation/gesture bars are hidden; a swipe from the edge shows them
  for a moment (Android `BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE`, iOS
  `prefersStatusBarHidden` and `prefersHomeIndicatorAutoHidden`).
- The window draws into the camera cutout (Android `LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES`;
  iOS: the web view is pinned to the view's edges, not the safe area).
- The page learns where the hole is: `{side: "left"|"right", top, bottom, depth}` in CSS px.
  Android reads `DisplayCutout.getBoundingRects()` and gives it through a JavaScript
  interface (`BunkerShell.cutout()`, JSON). iOS has no API for the notch's shape: it gives
  the safe-area depth on that side and a band centred on the edge, 210 pt tall (a notch;
  the Dynamic Island is shorter), through a document-start script (`window.bunkerCutout`).
- `/bunker/close` is the page's Close: the app intercepts that navigation and closes Pod
  Programs exactly as its Close button does.

## The pages (shared CSS, base template, small script)

- **Tab column** (148 px): "POD PROGRAMS" and CLOSE at its top, then the tabs. Tabs that
  pass beside a hole on the left are indented past it while the column scrolls; a hole on
  the right pads the page's right edge instead.
- **Live-game notice:** a short line at the foot of the tab column ("● Game running ·
  changes send it back to its title screen") instead of the banner at the top of each page.
- **Split pages:** a page marks the elements that belong beside its content with
  `data-side`. On a phone on its side a script moves them, in order, into a side column
  (228 px, stays put, scrolls by itself) and the rest into the main column; turning the
  phone back puts every element back where it was. In portrait nothing moves.
- **Intro text** in the side column (`data-side="intro"`): three lines and "more".
- **Jump links:** headers marked `data-toc` are listed under the side column as links.
- **Density:** smaller titles and gaps, panels 10/12 px padding, controls 34 px tall.
- **Rows:** settings put name and note on the left and the control on the right; short
  records (`data-grid2` container) go two across; grant rows fit the main column with
  container queries (the main column is narrower than the viewport).
- **Programs:** two columns. **Deck Builder:** the controls and Filters in the side column,
  two decks across.

Per page (what goes beside):

| Page | Side column | Jump links |
|---|---|---|
| Content | Today (New day), current | section headers |
| Users | intro, New player | — |
| Save Data | note, Create backup | — |
| Display | the closing note, Save | section headers |
| Summon Rates | presets, the note | section headers |
| Mods | intro, Preset, credit | group headers |
| Gift | intro, Send, Waiting in the Gift Box | — |
| Deck Builder | intro, the controls | — |
| Item Editor | back link, title, gifts notice, intro, the category tabs | — |
| Costume / Weapon Editor | back link, title, gifts notice, intro, filter, counts, bulk buttons | group headers |
| Upgrade Manager | back link, title, intro | section headers |
| Memoir Editor | back link, title, intro, Build a set | section headers |

## Decided by me

- The split is done by a script moving marked elements rather than new wrapper markup, so
  portrait order and spacing stay exactly as they are; the cost is a script that must run
  before the first paint (it runs inline right after `main`).
- The iOS notch band is an estimate (210 pt); a page item beside the notch can end up
  indented when it would have fitted.

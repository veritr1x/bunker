# Native summon UI artwork

This pass exports all 1,961 checked English `ui/gacha/*/banner` and
`ui/gacha/*/mom_banner` bundles from the preserved Android resource tree.
The exports contain 1,068 distinct PNG payloads. The source family is distinct
from the character, weapon, companion and consumable-item image libraries.
It is not an export of every UI family, regional variant, title logo or appeal
panel.

Open `inputs/native-summon-ui/index.html` for the searchable gallery.
`inputs/bunker-native-summon-ui.zip` provides the portable collection. The
working export keeps 1,961 image filenames; the ZIP stores the 1,068 native PNG
payloads once and rewrites image references in its HTML and JSON. Every source
bundle and object record remains in the manifest, including aliases that share
one PNG. The count is not a count of new illustrations.

Every image is exported from a native Sprite, or a Texture2D when no Sprite
exists. The manifest records the source bundle path and SHA-256, object name,
object ID, dimensions, PNG SHA-256 and decoded RGBA hash. No game code was run
and no artwork was synthesized.

## Notice comparison

The earlier linked-banner extraction did not cover every native summon design.
This broader pass compared its unique images with the 22 preserved thumbnails
available for the 45 stand-in notices without mapped game artwork. Perceptual
similarity was used to select candidates for review, not to assign matches
automatically.

Native `step_up_556001/banner` matches the characters, wording and composition
of notice 998, **Resolute Dress Multi-Step Summons On Now**. It is a small
234-by-118 UI image. The preserved original thumbnail and native image are
shown together on `notice-comparisons.html`. This establishes a native
thumbnail-design counterpart; it does not recover the larger original website
banner or prove original website file-byte identity. The existing candidate
notice ZIP was not changed.

The closest weekly-summon candidate, `limited_10094`, was rejected for notices
739 and 817 because its featured character and shard portraits differ. A
shared banner template is insufficient evidence for a substitution.

All 1,961 bundle exports completed without errors. Both reader pages have 2,146
checked local references and no broken local links. All exported image paths
were fully decoded and hash-checked before packaging. The portable validator
checks the rewritten references, all distinct packet image paths, dimensions
and decoded RGBA hashes after extraction. The ZIP also preserves three reused
original comparison-thumbnail files.

The HTML reader needs only a browser. `tools/validate_remaining_ui_packet.py`
requires Python and Pillow; use `--kind native --folder .` after extracting the
ZIP. Capture helpers retain working-session paths and require configuration
and UnityPy to run against a resource dump.

No exact missing original website image was recovered in this pass. The
764-path gap, 951-notice candidate and 197 supplemental native-icon records
remain unchanged.

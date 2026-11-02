"""Compose notice thumbnails from preserved native UI layers and full textures.

Sprite exports can be trimmed. Reading the 102px Texture2D preserves the native
padding, rather than stretching a trimmed portrait or weapon across the frame.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WEAPON_TYPES = {1: 'sword', 2: 'spear', 3: 'bigsword', 4: 'fist', 5: 'staff', 6: 'gun'}
ELEMENTS = {1: 'dark', 2: 'fire', 3: 'light', 5: 'water', 6: 'wind'}
RARITIES = {10: 'bronze', 20: 'silver', 30: 'gold', 40: 'rainbow', 50: 'rainbow'}


class NativeNoticeIcons:
    def __init__(self, library):
        self.lib = library
        self.root = ROOT / 'inputs/historical-apks/artwork/1.5.7'
        manifest = json.loads((self.root / 'manifest.json').read_text(encoding='utf-8'))
        self.layers = {r['name']: r for r in manifest['images']}
        self.layer_cache = {}
        self.cache = {}

    def layer(self, name):
        if name not in self.layer_cache:
            r = self.layers[name]
            path = self.root / r['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == r['sha256']
            self.layer_cache[name] = Image.open(path).convert('RGBA')
        return self.layer_cache[name]

    @staticmethod
    def compose(art, background, frame, weapon_badge, element_badge=None):
        assert art.size == (102, 102), 'Use the untrimmed native thumbnail texture'
        assert background.size == frame.size == (110, 110)
        # Published notice icons bake the background RGB into an opaque square;
        # the in-game sprite's 70% alpha would darken it on the notice page.
        icon = background.copy()
        icon.putalpha(255)
        icon.alpha_composite(art, (4, 4))
        icon.alpha_composite(frame)
        if element_badge is not None:
            icon.alpha_composite(element_badge, (0, 0))
            icon.alpha_composite(weapon_badge, (0, 34))
        else:
            icon.alpha_composite(weapon_badge, (0, 0))
        return icon

    def icon(self, family, ident):
        key = (family, ident)
        if key in self.cache:
            return self.cache[key]
        r = self.lib.master['Costume' if family == 'costumes' else 'Weapon'][ident]
        rarity = RARITIES[r['RarityType']]
        ty = r['SkillfulWeaponType'] if family == 'costumes' else r['WeaponType']
        asset = (f"ch{r['ActorSkeletonId']:03d}{r['AssetVariationId']:03d}" if family == 'costumes'
                 else f"wp{r['WeaponType']:03d}{r['AssetVariationId']:03d}")
        relative = f"ui/{'costume' if family == 'costumes' else 'weapon'}/{asset}/{asset}_standard.assetbundle"
        path = self.lib.asset_root / relative
        if not path.exists() or ty not in WEAPON_TYPES:
            return self.lib.icon(family, asset)
        names = [f'thumbnail_bg_{rarity}_a', f'thumbnail_frame_{rarity}', f'weapon_icon_{WEAPON_TYPES[ty]}']
        if family == 'weapons':
            names.append('attribute_' + ELEMENTS.get(r['AttributeType'], 'none'))
        raw = path.read_bytes()
        source = {
            'recipe': 'native-notice-thumbnail-v1', 'family': family, 'native_id': ident,
            'asset': asset, 'rarity_type': r['RarityType'], 'weapon_type': ty,
            'attribute_type': r.get('AttributeType'),
            'art_bundle': relative, 'art_bundle_sha256': hashlib.sha256(raw).hexdigest(),
            'native_layers': [{**self.layers[n], 'source_png': str(self.root / self.layers[n]['file'])} for n in names],
            'art_offset': [4, 4], 'element_offset': [0, 0] if family == 'weapons' else None,
            'weapon_type_offset': [0, 34] if family == 'weapons' else [0, 0],
            'background_alpha': 255,
        }
        signature = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
        composite_key = f'notice-icon:{family}:{ident}'
        cached = self.lib.reuse_image(composite_key, signature)
        if cached:
            self.cache[key] = cached
            return cached
        import UnityPy
        from export_asset_images import unmask
        env = UnityPy.load(unmask(raw, relative))
        textures = [o for o in env.objects if o.type.name == 'Texture2D']
        assert len(textures) == 1, relative
        art = textures[0].read().image.convert('RGBA')
        im = self.compose(art, *(self.layer(n) for n in names))
        member = self.lib.add_image(im, {**source, 'composite_key': composite_key,
                                        'source_composition_sha256': signature})
        self.cache[key] = member
        return member

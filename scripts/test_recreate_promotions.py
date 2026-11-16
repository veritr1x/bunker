#!/usr/bin/env python3
"""recreate_promotions.py: a Mama's News image's title text swapped for another language's."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import cv2  # noqa: F401
    import numpy as np
except ImportError:  # pragma: no cover - the image tools are optional
    cv2 = None


@unittest.skipIf(cv2 is None, "needs numpy and opencv-python")
class SwapTitle(unittest.TestCase):
    def picture(self, text_rows):
        image = np.full((365, 720, 4), (40, 35, 30, 255), np.uint8)
        image[30:150, 300:420, :3] = 230  # the ghost, above the title: never touched
        for x in range(100, 600, 12):  # lettering: thin strokes, as the game's titles are drawn
            image[text_rows[0]:text_rows[1], x:x + 3, :3] = 250
        return image

    def test_the_title_is_replaced_and_the_rest_kept(self):
        import recreate_promotions as rp
        target, donor = self.picture((250, 270)), self.picture((290, 330))
        out = rp.swap_title(target, donor)
        self.assertEqual(out.shape, target.shape)
        self.assertTrue((out[30:150, 300:420, :3] == 230).all())  # the ghost
        self.assertLess(out[255:265, 100:600, :3].max(), 120)    # the old title is gone
        self.assertGreater(out[300:320, 100:103, :3].mean(), 200)  # the new one is in
        self.assertTrue((out[..., 3] == 255).all())


if __name__ == "__main__":
    unittest.main()

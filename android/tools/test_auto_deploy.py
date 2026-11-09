"""The launcher's ⋮ menu: Auto deploy. On (the default) starts Lunar Tear and the game when the launcher opens, as
before; off leaves the launcher open until DEPLOY is tapped."""
import re
import unittest
from pathlib import Path

MAIN = (Path(__file__).resolve().parents[2] / "android/app/src/main/java/org/veritr1x/bunker/MainActivity.java").read_text()


class AutoDeploy(unittest.TestCase):
    def test_a_setting_on_by_default(self):
        self.assertIn('static boolean autoDeploy(Context c){return c.getSharedPreferences("launcher",MODE_PRIVATE).getBoolean("autoDeploy",true);}', MAIN)

    def test_the_menu_toggles_it(self):
        self.assertIn('option(panel,menu,15,autoDeploy(this)?Texts.t(this,"launcher.menu.auto_deploy_on"):Texts.t(this,"launcher.menu.auto_deploy_off"),true);', MAIN)
        self.assertRegex(MAIN, r'case 15: \{boolean on=!autoDeploy\(this\);getSharedPreferences\("launcher",MODE_PRIVATE\)\.edit\(\)\.putBoolean\("autoDeploy",on\)\.apply\(\);')

    def test_off_opens_like_manage(self):
        # opened from the icon or brought back: off stays on the launcher, as "manage" does
        self.assertEqual(len(re.findall(r'boolean manage=[^;]*getBooleanExtra\("manage",false\)\|\|!autoDeploy\(this\);', MAIN)), 2)


if __name__ == "__main__":
    unittest.main()
